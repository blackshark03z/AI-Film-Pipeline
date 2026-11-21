"""
Animatic Previs Builder (Pre-Production Storyboard Timeline)
Builds a lightweight 1280x720 @ 12fps MP4 animatic + sidecar SRT from `shots_manifest.json`:
- Uses existing `first_frame_path` or synthesizes a clean PIL storyboard slate per shot.
- Renders a Director HUD top bar purely via Pillow (`shot_id | chapter_id | framing | speaker | dur`).
- Generates a soft 48kHz stereo cue click/beep at each shot start + silence, encodes with `-preset ultrafast`,
  concatenates segments cleanly, and verifies output specs via `ffprobe`.
"""

import json
import os
import subprocess
import tempfile
import textwrap
import wave
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
from PIL import Image, ImageDraw, ImageFont


class AnimaticBuilder:
    """Renders pre-production storyboard animatics before full AI video generation."""

    FRAME_W = 1280
    FRAME_H = 720
    SAMPLE_RATE = 48000

    @staticmethod
    def _load_font(size: int, bold: bool = False) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
        candidates = ["arialbd.ttf", "segoeuib.ttf", "consolab.ttf"] if bold else ["arial.ttf", "segoeui.ttf", "consola.ttf"]
        for name in candidates:
            try:
                return ImageFont.truetype(name, size)
            except Exception:
                continue
        return ImageFont.load_default()

    @staticmethod
    def _format_srt_timestamp(seconds: float) -> str:
        seconds = max(0.0, float(seconds))
        h = int(seconds // 3600)
        m = int((seconds % 3600) // 60)
        s = int(seconds % 60)
        ms = int(round((seconds - int(seconds)) * 1000))
        if ms >= 1000:
            s += 1
            ms -= 1000
            if s >= 60:
                m += 1
                s -= 60
                if m >= 60:
                    h += 1
                    m -= 60
        return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"

    @classmethod
    def _synthesize_storyboard_slate(
        cls,
        shot: Dict[str, Any],
        loc_fallback: str = "UNKNOWN LOCATION",
    ) -> Image.Image:
        img = Image.new("RGB", (cls.FRAME_W, cls.FRAME_H), (22, 28, 40))
        draw = ImageDraw.Draw(img)

        # Subtle rule-of-thirds composition grid and safe-action border
        grid_color = (40, 50, 68)
        for gx in (cls.FRAME_W // 3, (cls.FRAME_W * 2) // 3):
            draw.line([(gx, 52), (gx, cls.FRAME_H - 28)], fill=grid_color, width=1)
        for gy in (cls.FRAME_H // 3, (cls.FRAME_H * 2) // 3):
            draw.line([(60, gy), (cls.FRAME_W - 60, gy)], fill=grid_color, width=1)
        draw.rectangle([60, 66, cls.FRAME_W - 60, cls.FRAME_H - 36], outline=(68, 86, 115), width=2)

        font_title = cls._load_font(30, bold=True)
        font_meta = cls._load_font(21, bold=False)
        font_body = cls._load_font(22, bold=False)

        shot_id = str(shot.get("shot_id") or "SHOT")
        loc_name = str(shot.get("location_name") or shot.get("location") or loc_fallback)
        framing = str(shot.get("framing") or "Medium Shot")
        gaze = str(shot.get("gaze") or "looking screen-right")
        action = str(shot.get("action_summary") or "")

        draw.text((96, 104), f"STORYBOARD SLATE  //  {shot_id}", fill=(238, 244, 252), font=font_title)
        draw.text((96, 156), f"LOCATION: {loc_name}", fill=(148, 197, 255), font=font_meta)
        draw.text((96, 192), f"FRAMING:  {framing}    |    AXIS GAZE: {gaze}", fill=(185, 205, 228), font=font_meta)

        y_cursor = 256
        draw.text((96, y_cursor), "ACTION:", fill=(234, 179, 8), font=font_meta)
        y_cursor += 34
        for line in textwrap.wrap(action, width=68)[:5]:
            draw.text((96, y_cursor), line, fill=(226, 232, 240), font=font_body)
            y_cursor += 32

        dlg = (shot.get("dialogue") or shot.get("narration") or "").strip()
        if dlg:
            y_cursor += 18
            speaker = shot.get("speaker") or "VO"
            draw.text((96, y_cursor), f"{speaker.upper()}:", fill=(125, 211, 252), font=font_meta)
            y_cursor += 30
            for line in textwrap.wrap(f'"{dlg}"', width=68)[:4]:
                draw.text((96, y_cursor), line, fill=(203, 213, 225), font=font_body)
                y_cursor += 30

        return img

    @classmethod
    def _render_frame_with_hud(
        cls,
        shot: Dict[str, Any],
        project_dir: Path,
        dur_s: float,
        loc_map: Dict[str, str],
    ) -> Image.Image:
        ff_raw = shot.get("first_frame_path")
        base_img: Optional[Image.Image] = None
        if ff_raw:
            cand = Path(ff_raw)
            if not cand.is_absolute() and not cand.exists():
                cand = project_dir / ff_raw
            if cand.exists() and cand.is_file():
                try:
                    with Image.open(cand) as im:
                        base_img = im.convert("RGB").resize(
                            (cls.FRAME_W, cls.FRAME_H), Image.Resampling.LANCZOS
                        )
                except Exception:
                    base_img = None

        if base_img is None:
            loc_id = str(shot.get("location") or "")
            base_img = cls._synthesize_storyboard_slate(
                shot, loc_fallback=loc_map.get(loc_id, loc_id or "SET")
            )

        draw = ImageDraw.Draw(base_img)
        hud_h = 46
        draw.rectangle([0, 0, cls.FRAME_W, hud_h], fill=(14, 18, 26))
        draw.line([(0, hud_h), (cls.FRAME_W, hud_h)], fill=(59, 130, 246), width=2)

        shot_id = str(shot.get("shot_id") or "SHOT")
        chapter_id = str(shot.get("chapter_id") or "CH01")
        framing = str(shot.get("framing") or "MCU")
        speaker = str(shot.get("speaker") or ("VO" if shot.get("narration") else "SILENT"))
        hud_line = f"{shot_id} | {chapter_id} | {framing} | {speaker} | {dur_s:.1f}s"
        if shot.get("is_flashback"):
            hud_line += " | FLASHBACK"

        font_hud = cls._load_font(18, bold=True)
        draw.text((18, 12), hud_line, fill=(241, 245, 249), font=font_hud)
        return base_img

    @classmethod
    def _write_click_plus_silence_wav(cls, wav_path: Path, duration_s: float) -> Path:
        total_samples = max(int(round(duration_s * cls.SAMPLE_RATE)), 2400)
        samples = np.zeros(total_samples, dtype=np.float32)

        # Soft 880Hz sine cue marker over first 40ms with smooth Hann fade envelope
        beep_len = min(int(0.04 * cls.SAMPLE_RATE), total_samples)
        if beep_len > 0:
            t = np.arange(beep_len, dtype=np.float32) / cls.SAMPLE_RATE
            envelope = np.hanning(beep_len).astype(np.float32)
            samples[:beep_len] = 0.12 * np.sin(2.0 * np.pi * 880.0 * t) * envelope

        pcm_mono = np.clip(samples * 32767.0, -32768, 32767).astype(np.int16)
        pcm_stereo = np.column_stack((pcm_mono, pcm_mono)).ravel()

        with wave.open(str(wav_path), "wb") as wf:
            wf.setnchannels(2)
            wf.setsampwidth(2)
            wf.setframerate(cls.SAMPLE_RATE)
            wf.writeframes(pcm_stereo.tobytes())
        return wav_path

    @classmethod
    def build_animatic(
        cls,
        project_dir: Path,
        output_mp4: Optional[Path] = None,
        fps: int = 12,
    ) -> Dict[str, Any]:
        """Build a 1280x720 animatic preview MP4 and sidecar SRT from `shots_manifest.json`."""
        project_dir = Path(project_dir)
        manifest_path = project_dir / "shots_manifest.json"
        if not manifest_path.exists():
            raise FileNotFoundError(f"Không tìm thấy shots_manifest.json tại {manifest_path}")

        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        shots: List[Dict[str, Any]] = manifest.get("shots") or []
        if not shots:
            raise ValueError("shots_manifest.json không có shot nào để dựng animatic.")

        bible_path = project_dir / "story_bible.json"
        loc_map: Dict[str, str] = {}
        if bible_path.exists():
            try:
                bible = json.loads(bible_path.read_text(encoding="utf-8"))
                loc_map = {
                    str(loc.get("id")): str(loc.get("name") or loc.get("id"))
                    for loc in bible.get("locations", [])
                    if loc.get("id")
                }
            except Exception:
                loc_map = {}

        fps = max(1, int(fps))
        out_mp4 = Path(output_mp4) if output_mp4 else (project_dir / "ANIMATIC" / "animatic_preview.mp4")
        out_mp4.parent.mkdir(parents=True, exist_ok=True)
        srt_out = out_mp4.with_suffix(".srt")

        srt_blocks: List[str] = []
        cur_time = 0.0

        with tempfile.TemporaryDirectory(prefix="muse_animatic_") as tmp_dir:
            tmp_p = Path(tmp_dir)
            seg_jobs: List[Tuple[List[str], Path]] = []

            for idx, shot in enumerate(shots, start=1):
                raw_trim = shot.get("target_trim_duration_s")
                dur = float(raw_trim) if raw_trim else min(float(shot.get("duration_s", 4.0)), 4.0)
                dur = max(0.5, dur)

                frame_img = cls._render_frame_with_hud(shot, project_dir, dur, loc_map)
                frame_png = tmp_p / f"frame_{idx:03d}.png"
                frame_img.save(frame_png, format="PNG")

                wav_p = cls._write_click_plus_silence_wav(tmp_p / f"audio_{idx:03d}.wav", dur)
                seg_mp4 = tmp_p / f"seg_{idx:03d}.mp4"

                cmd_seg = [
                    "ffmpeg", "-y",
                    "-loop", "1",
                    "-framerate", str(fps),
                    "-t", f"{dur:.3f}",
                    "-i", str(frame_png),
                    "-i", str(wav_p),
                    "-c:v", "libx264",
                    "-preset", "ultrafast",
                    "-threads", "2",
                    "-pix_fmt", "yuv420p",
                    "-r", str(fps),
                    "-vf", "scale=1280:720:flags=bilinear,format=yuv420p",
                    "-c:a", "aac",
                    "-ar", str(cls.SAMPLE_RATE),
                    "-ac", "2",
                    "-b:a", "128k",
                    "-t", f"{dur:.3f}",
                    str(seg_mp4),
                ]
                seg_jobs.append((cmd_seg, seg_mp4))

                # Build SRT cue for this shot
                start_ts = cls._format_srt_timestamp(cur_time)
                end_ts = cls._format_srt_timestamp(cur_time + dur)
                cur_time += dur

                dlg = (shot.get("dialogue") or "").strip()
                narr = (shot.get("narration") or shot.get("voiceover_text") or "").strip()
                spk = (shot.get("speaker") or "").strip()
                if dlg:
                    cue_line = f"[{spk}] {dlg}" if spk else dlg
                elif narr:
                    cue_line = f"[VO] {narr}"
                else:
                    cue_line = f"[{shot.get('shot_id', f'S{idx:03d}')}] {shot.get('action_summary') or ''}".strip()

                srt_blocks.append(f"{idx}\n{start_ts} --> {end_ts}\n{cue_line}\n")

            def _encode_seg(job: Tuple[List[str], Path]) -> Path:
                cmd_seg, seg_mp4 = job
                subprocess.run(cmd_seg, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, check=True)
                return seg_mp4

            seg_workers = min(4, max(1, os.cpu_count() or 2), max(1, len(seg_jobs)))
            if seg_workers > 1:
                with ThreadPoolExecutor(max_workers=seg_workers) as pool:
                    seg_files = list(pool.map(_encode_seg, seg_jobs))
            else:
                seg_files = [_encode_seg(job) for job in seg_jobs]

            concat_txt = tmp_p / "concat_list.txt"
            concat_txt.write_text(
                "\n".join(f"file '{p.resolve().as_posix()}'" for p in seg_files) + "\n",
                encoding="utf-8",
            )
            cmd_concat = [
                "ffmpeg", "-y",
                "-f", "concat",
                "-safe", "0",
                "-i", str(concat_txt),
                "-c", "copy",
                "-movflags", "+faststart",
                str(out_mp4),
            ]
            subprocess.run(cmd_concat, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, check=True)

        srt_out.write_text("\n".join(srt_blocks), encoding="utf-8")

        probe = json.loads(
            subprocess.check_output(
                ["ffprobe", "-v", "error", "-show_streams", "-show_format", "-of", "json", str(out_mp4)],
                text=True,
            )
        )
        streams = probe.get("streams", [])
        v_stream = next((s for s in streams if s.get("codec_type") == "video"), None)
        a_stream = next((s for s in streams if s.get("codec_type") == "audio"), None)
        if not v_stream or not a_stream:
            raise RuntimeError(f"Animatic MP4 thiếu luồng video hoặc audio: {out_mp4}")

        probed_dur = float(probe.get("format", {}).get("duration") or cur_time)
        return {
            "success": True,
            "animatic_mp4": str(out_mp4),
            "animatic_srt": str(srt_out),
            "shots_count": len(shots),
            "duration_s": round(probed_dur, 3),
        }
