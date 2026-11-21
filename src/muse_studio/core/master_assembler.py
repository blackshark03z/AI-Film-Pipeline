"""
Master Film Assembler & Cinema v4 Post-Production Engine (Khâu 6 -> Khâu 7)
- Cắt 2 đầu theo Faster-Whisper (`trim_in_s -> trim_out_s`) + micro-fade chống tiếng bụp.
- DI Color Match liên cảnh (Luma + RGB White-Balance ±0.08) + Mood Color Grade + 35mm Film Grain.
- Nâng chuẩn 1920x1080 @ 24fps (Lanczos + unsharp) + Slow Push-in 4% cho cảnh cao trào.
- Tag nhân vật Glassmorphism thông minh tránh khuôn mặt (Face-Aware) xuất hiện ĐÚNG 1 LẦN toàn phim.
- Dialogue Denoise/EQ/Comp + Voice Timbre Consistency Lock theo nhân vật + J/L-Cut êm ái.
- Hòa âm 4 Tầng (Dialogue/VO + Location Ambience + 12-Class Foley + Dynamic Mood Score Auto-Ducking).
- Chuẩn hóa EBU R128 2-Pass (-16.0 LUFS, True Peak <= -1.5 dBTP, Stereo 48kHz 192kbps),
  xuất kèm M&E Stem, Dialogue Stem, Netflix-Spec `.srt`, `.i18n_template.json`, FFMETADATA Chapters,
  CapCut Desktop Draft Project và Commercial Promo Delivery Kit.
- Toàn bộ PNG overlay và file âm thanh truyền qua `-i` (không nhúng đường dẫn Windows vào filter).
"""

import json
import math
import os
import re
import subprocess
import tempfile
import wave
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

try:
    import cv2
except Exception:  # pragma: no cover
    cv2 = None  # type: ignore

import numpy as np
from PIL import Image, ImageDraw, ImageFont, ImageStat

try:
    from .cinema_audio_engine import CinemaAudioEngine, VoiceTimbreMatcher
    from .delivery_packager import DeliveryPackager
except ImportError:
    from core.cinema_audio_engine import CinemaAudioEngine, VoiceTimbreMatcher
    from core.delivery_packager import DeliveryPackager


class MasterAssembler:
    """Bộ hậu kỳ điện ảnh hoàn chỉnh từ clips đã qua 5-Gate QC -> Final 1080p Master."""

    ROLE_COLORS = {
        "CAPTAIN": (234, 179, 8, 255),     # Vàng kim phi công
        "FIRST OFFICER": (234, 179, 8, 255),
        "ATTENDANT": (220, 38, 38, 255),   # Đỏ cảnh báo
        "POLICE": (59, 130, 246, 255),     # Xanh cảnh sát
        "DIRECTOR": (59, 130, 246, 255),
        "JUDGE": (168, 85, 247, 255),
        "CEO": (148, 163, 184, 255),
        "REPORTER": (14, 165, 233, 255),
        "MOTHER": (245, 158, 11, 255),
        "SUPERVISOR": (148, 163, 184, 255),  # Xám điều phối
    }

    @staticmethod
    def format_srt_time(seconds: float) -> str:
        return DeliveryPackager.format_srt_time(seconds)

    @staticmethod
    def _probe_duration(media_path: Path) -> float:
        cmd = [
            "ffprobe", "-v", "error",
            "-show_entries", "format=duration",
            "-of", "default=noprint_wrappers=1:nokey=1",
            str(media_path),
        ]
        out = subprocess.check_output(cmd, text=True).strip()
        return float(out) if out else 0.0

    @staticmethod
    def _probe_has_audio(media_path: Path) -> bool:
        cmd = [
            "ffprobe", "-v", "error",
            "-select_streams", "a:0",
            "-show_entries", "stream=codec_type",
            "-of", "default=noprint_wrappers=1:nokey=1",
            str(media_path),
        ]
        res = subprocess.run(cmd, capture_output=True, text=True)
        return bool(res.stdout.strip())

    @staticmethod
    def _measure_clip_color_stats(clip_path: Path) -> Tuple[float, float, float, float]:
        """Đo trung bình (Y, R, G, B) trong dải 0..255 trên 3 khung hình đại diện của clip (in-memory OpenCV ưu tiên, fallback FFmpeg)."""
        dur = max(1.0, MasterAssembler._probe_duration(clip_path))
        samples = sorted([0.3, dur * 0.5, max(0.4, dur - 0.3)])
        ys: List[float] = []
        rs: List[float] = []
        gs: List[float] = []
        bs: List[float] = []

        if cv2 is not None:
            cap = cv2.VideoCapture(str(clip_path))
            if cap.isOpened():
                try:
                    fps = cap.get(cv2.CAP_PROP_FPS) or 24.0
                    if dur <= 15.0:
                        targets = [max(0, int(round(ts * fps))) for ts in samples]
                        t_ptr = 0
                        f_idx = 0
                        while t_ptr < len(targets) and cap.grab():
                            if f_idx >= targets[t_ptr]:
                                ok, frame = cap.retrieve()
                                if ok and frame is not None:
                                    small = cv2.resize(frame, (160, 90), interpolation=cv2.INTER_AREA)
                                    # OpenCV BGR -> B, G, R
                                    b_m = float(small[:, :, 0].mean())
                                    g_m = float(small[:, :, 1].mean())
                                    r_m = float(small[:, :, 2].mean())
                                    y_m = 0.299 * r_m + 0.587 * g_m + 0.114 * b_m
                                    while t_ptr < len(targets) and f_idx >= targets[t_ptr]:
                                        ys.append(y_m)
                                        rs.append(r_m)
                                        gs.append(g_m)
                                        bs.append(b_m)
                                        t_ptr += 1
                            f_idx += 1
                    else:
                        for ts in samples:
                            cap.set(cv2.CAP_PROP_POS_MSEC, ts * 1000.0)
                            ok, frame = cap.read()
                            if ok and frame is not None:
                                small = cv2.resize(frame, (160, 90), interpolation=cv2.INTER_AREA)
                                b_m = float(small[:, :, 0].mean())
                                g_m = float(small[:, :, 1].mean())
                                r_m = float(small[:, :, 2].mean())
                                y_m = 0.299 * r_m + 0.587 * g_m + 0.114 * b_m
                                ys.append(y_m)
                                rs.append(r_m)
                                gs.append(g_m)
                                bs.append(b_m)
                finally:
                    cap.release()

        if not ys:
            with tempfile.TemporaryDirectory() as td:
                for idx, ts in enumerate(samples):
                    fp = Path(td) / f"s_{idx}.png"
                    subprocess.run(
                        ["ffmpeg", "-y", "-ss", f"{ts:.2f}", "-i", str(clip_path), "-vframes", "1", str(fp)],
                        stdout=subprocess.DEVNULL,
                        stderr=subprocess.DEVNULL,
                    )
                    if fp.exists() and fp.stat().st_size > 0:
                        with Image.open(fp) as im:
                            rgb_im = im.convert("RGB")
                            r_m, g_m, b_m = ImageStat.Stat(rgb_im).mean[:3]
                            y_m = float(ImageStat.Stat(rgb_im.convert("L")).mean[0])
                            ys.append(y_m)
                            rs.append(float(r_m))
                            gs.append(float(g_m))
                            bs.append(float(b_m))

        if not ys:
            return (110.0, 110.0, 110.0, 110.0)
        n = float(len(ys))
        return (sum(ys) / n, sum(rs) / n, sum(gs) / n, sum(bs) / n)

    @classmethod
    def _measure_clip_luma(cls, clip_path: Path) -> float:
        """Đo độ sáng trung bình Y (0..255) trên 3 khung hình đại diện của clip."""
        return cls._measure_clip_color_stats(clip_path)[0]

    @staticmethod
    def _build_di_grade_vf(
        clip_stats: Tuple[float, float, float, float],
        scene_med: Tuple[float, float, float, float],
        mood: str,
        enable_film_grain: bool,
        add_fade_in: bool,
        add_fade_out: bool = False,
        clip_dur: float = 3.0,
    ) -> str:
        """Tạo chuỗi filter DI Color Match + Mood LUT/Parametric Grade + 35mm Film Grain."""
        y_c, r_c, g_c, b_c = clip_stats
        y_m, r_m, g_m, b_m = scene_med

        delta_y = (y_m - y_c) * 0.6
        b_shift = max(-0.06, min(0.06, delta_y / 255.0))

        # Cân bằng trắng khử lệch sắc độ giữa các batch (trần ±0.08)
        dy_raw = y_m - y_c
        wb_rm = max(-0.08, min(0.08, ((r_m - r_c) - dy_raw) * 0.65 / 128.0))
        wb_gm = max(-0.08, min(0.08, ((g_m - g_c) - dy_raw) * 0.65 / 128.0))
        wb_bm = max(-0.08, min(0.08, ((b_m - b_c) - dy_raw) * 0.65 / 128.0))

        mood_key = (mood or "cinematic_neutral").lower()
        if mood_key == "warm_flashback":
            rs, gs, bs = 0.04, 0.01, -0.05
            rm_m, gm_m, bm_m = 0.04, 0.02, -0.04
            rh, bh = 0.03, -0.03
            contrast, sat = 0.98, 0.88
        elif mood_key == "cold_thriller":
            rs, gs, bs = -0.04, -0.01, 0.05
            rm_m, gm_m, bm_m = -0.02, 0.00, 0.03
            rh, bh = -0.01, 0.02
            contrast, sat = 1.04, 0.93
        else:  # cinematic_neutral
            rs, gs, bs = -0.02, 0.00, 0.02
            rm_m, gm_m, bm_m = 0.00, 0.00, 0.00
            rh, bh = 0.02, -0.02
            contrast, sat = 1.02, 1.01

        rm_tot = max(-0.12, min(0.12, wb_rm + rm_m))
        gm_tot = max(-0.12, min(0.12, wb_gm + gm_m))
        bm_tot = max(-0.12, min(0.12, wb_bm + bm_m))

        parts = [
            f"eq=brightness={b_shift:.4f}:contrast={contrast:.3f}:saturation={sat:.3f}",
            (
                f"colorbalance=rs={rs:.3f}:gs={gs:.3f}:bs={bs:.3f}:"
                f"rm={rm_tot:.4f}:gm={gm_tot:.4f}:bm={bm_tot:.4f}:"
                f"rh={rh:.3f}:bh={bh:.3f}"
            ),
            "unsharp=3:3:0.25",
        ]
        if enable_film_grain:
            parts.append("noise=c0s=3:c0f=t+u")
        parts.append("fps=24")
        if add_fade_in:
            parts.append("fade=t=in:st=0:d=0.45")
        if add_fade_out and clip_dur >= 1.2:
            fo_st = max(0.1, clip_dur - 0.38)
            parts.append(f"fade=t=out:st={fo_st:.2f}:d=0.35")
        return ",".join(parts)

    @staticmethod
    def _build_virtual_camera_vf(shot: Dict[str, Any], clip_dur: float, di_tail_vf: str) -> str:
        """
        Virtual Camera Rig (Post-Production Optical Dolly / Slider / Easyrig):
        Tạo chuyển động máy mượt mà (cosine ease-in-out) cho các cảnh khóa máy tĩnh khi gen,
        xóa bỏ cảm giác khung hình chết cứng mà không làm méo khẩu hình AI.
        """
        if clip_dur < 1.8 or bool(shot.get("allow_camera_motion")):
            return (
                f"scale=1920:1080:flags=lanczos:force_original_aspect_ratio=increase,"
                f"crop=1920:1080,{di_tail_vf}"
            )

        raw_post = str(shot.get("post_camera_motion") or "").strip().lower()
        if not raw_post:
            raw_post = "push_in" if shot.get("is_climax_closeup") else "static"

        dur_s = max(1.8, float(clip_dur))
        if raw_post in ("push_in", "push_in_slow", "dolly_in", "zoom_in"):
            return (
                f"scale=w='trunc(1920*(1+0.045*(0.5-0.5*cos(3.14159*t/{dur_s:.2f})))/2)*2':"
                f"h='trunc(1080*(1+0.045*(0.5-0.5*cos(3.14159*t/{dur_s:.2f})))/2)*2':eval=frame:flags=lanczos,"
                f"crop=1920:1080,{di_tail_vf}"
            )
        if raw_post in ("pull_out", "pull_out_slow", "dolly_out", "reveal"):
            return (
                f"scale=w='trunc(1920*(1.045-0.045*(0.5-0.5*cos(3.14159*t/{dur_s:.2f})))/2)*2':"
                f"h='trunc(1080*(1.045-0.045*(0.5-0.5*cos(3.14159*t/{dur_s:.2f})))/2)*2':eval=frame:flags=lanczos,"
                f"crop=1920:1080,{di_tail_vf}"
            )
        if raw_post in ("drift_right", "pan_right", "slider_right"):
            return (
                f"scale=2000:1126:flags=lanczos:force_original_aspect_ratio=increase,"
                f"crop=1920:1080:x='(iw-1920)*(0.5-0.5*cos(3.14159*t/{dur_s:.2f}))':y='(ih-1080)/2',{di_tail_vf}"
            )
        if raw_post in ("drift_left", "pan_left", "slider_left"):
            return (
                f"scale=2000:1126:flags=lanczos:force_original_aspect_ratio=increase,"
                f"crop=1920:1080:x='(iw-1920)*(0.5+0.5*cos(3.14159*t/{dur_s:.2f}))':y='(ih-1080)/2',{di_tail_vf}"
            )
        if raw_post in ("handheld_subtle", "handheld", "breathing"):
            return (
                f"scale=1976:1112:flags=lanczos:force_original_aspect_ratio=increase,"
                f"crop=1920:1080:x='(iw-1920)*(0.5+0.38*sin(1.65*t))':y='(ih-1080)*(0.5+0.35*cos(1.25*t))',{di_tail_vf}"
            )
        return (
            f"scale=1920:1080:flags=lanczos:force_original_aspect_ratio=increase,"
            f"crop=1920:1080,{di_tail_vf}"
        )

    @classmethod
    def create_character_tag_png(
        cls,
        name: str,
        role: str,
        output_path: Path,
        accent_color: Optional[Tuple[int, int, int, int]] = None,
    ) -> Path:
        """Tạo thẻ định danh nhân vật glassmorphism độ phân giải nét cho khung 1080p."""
        if accent_color is None:
            role_up = (role or "").upper()
            accent_color = (234, 179, 8, 255)
            for key, col in cls.ROLE_COLORS.items():
                if key in role_up:
                    accent_color = col
                    break

        try:
            font_name = ImageFont.truetype("arialbd.ttf", 32)
            font_title = ImageFont.truetype("arial.ttf", 22)
        except Exception:
            font_name = ImageFont.load_default()
            font_title = ImageFont.load_default()

        dummy = Image.new("RGBA", (1, 1))
        draw = ImageDraw.Draw(dummy)
        pad_x, pad_y = 28, 16
        nb = draw.textbbox((0, 0), name.upper(), font=font_name)
        rb = draw.textbbox((0, 0), role, font=font_title)
        tw = max(nb[2] - nb[0], rb[2] - rb[0])
        th = (nb[3] - nb[1]) + (rb[3] - rb[1]) + 10
        box_w = tw + pad_x * 2 + 16
        box_h = th + pad_y * 2

        img = Image.new("RGBA", (box_w, box_h), (0, 0, 0, 0))
        d = ImageDraw.Draw(img)
        d.rounded_rectangle(
            [0, 0, box_w - 1, box_h - 1],
            radius=10,
            fill=(15, 23, 42, 218),
            outline=(255, 255, 255, 85),
            width=2,
        )
        d.rounded_rectangle([12, 14, 18, box_h - 14], radius=3, fill=accent_color)

        tx = 32
        ty = pad_y - 2
        d.text((tx, ty), name.upper(), font=font_name, fill=(255, 255, 255, 255))
        d.text((tx, ty + (nb[3] - nb[1]) + 10), role, font=font_title, fill=(203, 213, 225, 235))

        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        img.save(output_path)
        return output_path

    @staticmethod
    def create_scene_card_png(title: str, output_path: Path) -> Path:
        """Tạo thẻ địa điểm/bối cảnh tinh gọn ở góc dưới trái cho cảnh mở chuyển bối cảnh."""
        try:
            font = ImageFont.truetype("arialbd.ttf", 24)
        except Exception:
            font = ImageFont.load_default()
        dummy = Image.new("RGBA", (1, 1))
        d0 = ImageDraw.Draw(dummy)
        tb = d0.textbbox((0, 0), title, font=font)
        w = (tb[2] - tb[0]) + 44
        h = (tb[3] - tb[1]) + 24
        img = Image.new("RGBA", (w, h), (0, 0, 0, 0))
        d = ImageDraw.Draw(img)
        d.rounded_rectangle(
            [0, 0, w - 1, h - 1],
            radius=6,
            fill=(15, 23, 42, 195),
            outline=(234, 179, 8, 170),
            width=1,
        )
        d.text((22, 11), title, font=font, fill=(248, 250, 252, 245))
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        img.save(output_path)
        return output_path

    @staticmethod
    def _write_stereo_wav(
        path: Path,
        samples_l: np.ndarray,
        samples_r: Optional[np.ndarray] = None,
        sr: int = 48000,
    ) -> Path:
        if samples_r is None:
            samples_r = samples_l
        stereo = np.stack([samples_l, samples_r], axis=1)
        stereo = np.clip(stereo, -0.98, 0.98)
        pcm = (stereo * 32767.0).astype(np.int16)
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        with wave.open(str(path), "wb") as wf:
            wf.setnchannels(2)
            wf.setsampwidth(2)
            wf.setframerate(sr)
            wf.writeframes(pcm.tobytes())
        return path

    @classmethod
    def synthesize_room_tone_wav(cls, duration_s: float, output_path: Path, sr: int = 48000) -> Path:
        """Tạo dải Room Tone liên tục (cabin/terminal hum êm ái, không gắt) chạy xuyên cảnh."""
        return CinemaAudioEngine.build_scene_ambience_track(
            [(0.0, max(1.0, float(duration_s)), "LOC_CABIN")],
            output_path=output_path,
            total_duration_s=duration_s,
            sr=sr,
        )

    @classmethod
    def synthesize_tension_bgm_wav(cls, duration_s: float, output_path: Path, sr: int = 48000) -> Path:
        """Tạo lớp nhạc nền căng thẳng điện ảnh đa hợp âm khi chưa có BGM ngoài."""
        return CinemaAudioEngine.build_dynamic_score_track(
            [(0.0, max(1.0, float(duration_s)), "tension")],
            output_path=output_path,
            total_duration_s=duration_s,
            sr=sr,
        )

    @classmethod
    def synthesize_foley_sfx_track(
        cls,
        duration_s: float,
        sfx_events: List[Tuple[float, str]],
        output_path: Path,
        sr: int = 48000,
    ) -> Path:
        """Tổng hợp dải Stem 3 Foley SFX 12 lớp theo các mốc thời gian hành động thực trên timeline."""
        return CinemaAudioEngine.build_foley_track(duration_s, sfx_events, output_path, sr=sr)

    @staticmethod
    def _generate_edge_tts(text: str, output_mp3: Path, voice: str = "en-US-ChristopherNeural") -> bool:
        cmd = ["edge-tts", "--text", text.strip(), "--voice", voice, "--write-media", str(output_mp3)]
        res = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        return res.returncode == 0 and output_mp3.exists() and output_mp3.stat().st_size > 0

    @classmethod
    def _loudnorm_two_pass(cls, input_media: Path, output_media: Path, has_video: bool = True) -> Dict[str, Any]:
        """Chạy FFmpeg loudnorm 2-Pass chuẩn EBU R128: -16.0 LUFS, TP <= -1.5 dB."""
        pass1_cmd = [
            "ffmpeg", "-y", "-i", str(input_media),
            "-af", "loudnorm=I=-16:TP=-1.5:LRA=11:print_format=json",
            "-f", "null", "-",
        ]
        p1 = subprocess.run(pass1_cmd, capture_output=True, text=True, check=True)
        stderr = p1.stderr
        json_matches = re.findall(r"\{[^{}]*\"input_i\"[^{}]*\}", stderr, re.DOTALL)

        v_args = ["-c:v", "copy"] if has_video else ["-vn"]
        if not json_matches:
            subprocess.run(
                [
                    "ffmpeg", "-y", "-i", str(input_media),
                    *v_args,
                    "-af", "loudnorm=I=-16:TP=-1.5:LRA=11",
                    "-c:a", "aac", "-b:a", "192k", "-ar", "48000", "-ac", "2",
                    "-movflags", "+faststart",
                    str(output_media),
                ],
                check=True,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            return {"mode": "1-pass-fallback"}

        stats = json.loads(json_matches[-1])
        inp_i = str(stats.get("input_i", "-24.0"))
        if "-inf" in inp_i.lower():
            subprocess.run(
                [
                    "ffmpeg", "-y", "-i", str(input_media),
                    *v_args,
                    "-c:a", "aac", "-b:a", "192k", "-ar", "48000", "-ac", "2",
                    "-movflags", "+faststart",
                    str(output_media),
                ],
                check=True,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            return {"mode": "silent-passthrough"}

        af_pass2 = (
            f"loudnorm=I=-16:TP=-1.5:LRA=11:"
            f"measured_I={stats['input_i']}:"
            f"measured_TP={stats['input_tp']}:"
            f"measured_LRA={stats['input_lra']}:"
            f"measured_thresh={stats['input_thresh']}:"
            f"offset={stats['target_offset']}:linear=true"
        )
        subprocess.run(
            [
                "ffmpeg", "-y", "-i", str(input_media),
                *v_args,
                "-af", af_pass2,
                "-c:a", "aac", "-b:a", "192k", "-ar", "48000", "-ac", "2",
                "-movflags", "+faststart",
                str(output_media),
            ],
            check=True,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        return {"mode": "2-pass", "measured_pass1": stats}

    @classmethod
    def measure_ebur128(cls, media_path: Path) -> Dict[str, Any]:
        """Đo thực tế Integrated Loudness (LUFS) & True Peak (dBTP) trên file xuất xưởng."""
        cmd = [
            "ffmpeg", "-i", str(media_path),
            "-af", "ebur128=framelog=verbose",
            "-f", "null", "-",
        ]
        res = subprocess.run(cmd, capture_output=True, text=True)
        text = res.stderr
        i_match = re.findall(r"I:\s*(-?\d+(?:\.\d+)?)\s*LUFS", text)
        tp_match = re.findall(r"Peak:\s*(-?\d+(?:\.\d+)?)\s*dBFS", text)
        return {
            "integrated_lufs": float(i_match[-1]) if i_match else None,
            "true_peak_dbfs": float(tp_match[-1]) if tp_match else None,
        }

    @staticmethod
    def _discover_assets_audio_dir(output_mp4: Path, first_clip: Path) -> Optional[Path]:
        for anchor in (output_mp4.parent, output_mp4.parent.parent, first_clip.parent, first_clip.parent.parent):
            cand = anchor / "assets" / "audio"
            if cand.exists() and cand.is_dir():
                return cand
        return None

    @classmethod
    def assemble_project(
        cls,
        shots_manifest: Dict[str, Any],
        clip_paths_by_shot: Dict[str, Path],
        output_mp4: Path,
        story_bible: Optional[Dict[str, Any]] = None,
        qc_reports: Optional[Dict[str, Dict[str, Any]]] = None,
        bgm_path: Optional[Path] = None,
        room_tone_path: Optional[Path] = None,
        work_dir: Optional[Path] = None,
        capcut_draft: bool = False,
        color_mood: str = "cinematic_neutral",
        enable_film_grain: bool = True,
        enable_voice_timbre_lock: bool = True,
        enable_j_l_cuts: bool = True,
        with_titles: bool = False,
        export_stems: bool = True,
        build_promo_kit: bool = False,
    ) -> Dict[str, Any]:
        """
        Hậu kỳ & xuất bản Master 1920x1080 @ 24fps hoàn chỉnh:
        - Zero Hardsub, xuất kèm `.srt` chuẩn Netflix (`<= 42` ký tự/dòng, tối đa 2 dòng) & `.i18n_template.json`.
        - Tag nhân vật Face-Aware lần đầu xuất hiện toàn phim.
        - DI Color Match liên cảnh + Mood Color Grade + 35mm Film Grain + Slow Push-in 4% cảnh cao trào.
        - Dialogue Cleanup + Voice Timbre Lock theo nhân vật + J/L-Cuts + 4-Stem Cinema Mix + EBU R128 2-pass.
        """
        output_mp4 = Path(output_mp4)
        output_mp4.parent.mkdir(parents=True, exist_ok=True)
        work_dir = Path(work_dir) if work_dir else (output_mp4.parent / f"_build_{output_mp4.stem}")
        work_dir.mkdir(parents=True, exist_ok=True)
        norm_dir = work_dir / "normalized_clips"
        tags_dir = work_dir / "tags"
        audio_dir = work_dir / "audio"
        norm_dir.mkdir(parents=True, exist_ok=True)
        tags_dir.mkdir(parents=True, exist_ok=True)
        audio_dir.mkdir(parents=True, exist_ok=True)

        char_map: Dict[str, Dict[str, Any]] = {}
        loc_name_map: Dict[str, str] = {}
        if story_bible:
            for c in story_bible.get("characters", []):
                char_map[c["id"]] = c
            for lc in story_bible.get("locations", []):
                if lc.get("id"):
                    loc_name_map[lc["id"]] = str(lc.get("name") or lc["id"])

        project_title = (
            (story_bible or {}).get("project_title")
            or shots_manifest.get("project_title")
            or output_mp4.stem
        )
        project_subtitle = str((story_bible or {}).get("subtitle") or "")

        shots = shots_manifest.get("shots", [])
        usable_shots = [
            s for s in shots
            if s.get("shot_id") in clip_paths_by_shot and Path(clip_paths_by_shot[s["shot_id"]]).exists()
        ]
        if not usable_shots:
            raise ValueError("Không tìm thấy clip hợp lệ nào để dựng Master!")

        assets_audio_dir = cls._discover_assets_audio_dir(
            output_mp4, Path(clip_paths_by_shot[usable_shots[0]["shot_id"]])
        )

        # 1. Đo (Y, R, G, B) theo từng cảnh (chapter_id + location) để cân bằng DI Color Match (song song đa luồng)
        color_by_shot: Dict[str, Tuple[float, float, float, float]] = {}
        color_by_scene: Dict[Tuple[str, str], List[Tuple[float, float, float, float]]] = {}
        color_workers = min(6, max(1, os.cpu_count() or 2), max(1, len(usable_shots)))
        if color_workers > 1:
            with ThreadPoolExecutor(max_workers=color_workers) as pool:
                measured_stats = list(
                    pool.map(
                        lambda sh: cls._measure_clip_color_stats(Path(clip_paths_by_shot[sh["shot_id"]])),
                        usable_shots,
                    )
                )
        else:
            measured_stats = [
                cls._measure_clip_color_stats(Path(clip_paths_by_shot[sh["shot_id"]]))
                for sh in usable_shots
            ]
        for s, stats_yrgb in zip(usable_shots, measured_stats):
            sid = s["shot_id"]
            color_by_shot[sid] = stats_yrgb
            sc_key = (s.get("chapter_id", "CH01"), s.get("location", "LOC"))
            color_by_scene.setdefault(sc_key, []).append(stats_yrgb)

        scene_color_medians: Dict[Tuple[str, str], Tuple[float, float, float, float]] = {}
        for sc_k, vals in color_by_scene.items():
            arr = np.asarray(vals, dtype=np.float64)
            med = np.median(arr, axis=0)
            scene_color_medians[sc_k] = (float(med[0]), float(med[1]), float(med[2]), float(med[3]))

        # Nếu with_titles=True, dựng Opening Title Card trước để neo chính xác timeline_cursor_s
        concat_files: List[Path] = []
        capcut_clip_segments: List[Dict[str, Any]] = []
        timeline_cursor_s = 0.0

        if with_titles:
            opening_mp4 = norm_dir / "00_opening_title.mp4"
            DeliveryPackager.render_slate_clip(
                opening_mp4,
                kind="opening",
                title=str(project_title),
                subtitle=project_subtitle,
                duration_s=2.5,
            )
            open_dur = cls._probe_duration(opening_mp4)
            concat_files.append(opening_mp4)
            capcut_clip_segments.append({"path": opening_mp4, "start_s": 0.0, "duration_s": open_dur})
            timeline_cursor_s += open_dur

        # 2. Chuẩn hóa từng shot (DI Color + Grain + 1080p24 + Face-Aware Tag + Dialogue Cleanup + Timbre Lock)
        tagged_characters: Set[str] = set()
        normalized_files: List[Path] = []
        srt_shot_specs: List[Dict[str, Any]] = []
        sfx_events: List[Tuple[float, str]] = []
        ambience_segments: List[Tuple[float, float, str]] = []
        score_segments: List[Tuple[float, float, str]] = []
        dialogue_seg_specs: List[Dict[str, Any]] = []
        chapter_spans: List[Dict[str, Any]] = []
        voice_profiles_by_char: Dict[str, np.ndarray] = {}

        if with_titles and timeline_cursor_s > 0.0:
            first_loc = str(usable_shots[0].get("location") or "LOC_CABIN")
            first_mood = CinemaAudioEngine.infer_segment_mood(usable_shots[0])
            ambience_segments.append((0.0, timeline_cursor_s, first_loc))
            score_segments.append((0.0, timeline_cursor_s, first_mood))

        # Phase A: Chuẩn bị tuần tự Audio/Tag/Timbre/J-L Cut (bảo toàn thứ tự nhân vật & hồ sơ giọng)
        norm_jobs: List[Dict[str, Any]] = []
        for shot_idx, s in enumerate(usable_shots):
            sid = s["shot_id"]
            raw_clip = Path(clip_paths_by_shot[sid])
            raw_dur = max(0.5, cls._probe_duration(raw_clip))
            qc_entry = (qc_reports or {}).get(sid, {})
            qc_m = qc_entry.get("metrics", {})
            tw = qc_m.get("trim_window", {})

            trim_in = float(tw.get("trim_in_s", 0.0))
            trim_out = float(tw.get("trim_out_s", min(raw_dur, s.get("target_trim_duration_s") or raw_dur)))
            if trim_out <= trim_in + 0.5:
                trim_in = 0.0
                trim_out = raw_dur
            clip_dur = max(0.5, min(raw_dur - trim_in, trim_out - trim_in))

            # Kiểm tra HYBRID_VO nếu có voiceover_text
            vo_file: Optional[Path] = None
            if s.get("audio_mode") == "HYBRID_VO" and s.get("voiceover_text"):
                cand_vo = audio_dir / f"vo_{sid}.mp3"
                if cls._generate_edge_tts(s["voiceover_text"], cand_vo):
                    vo_dur = cls._probe_duration(cand_vo)
                    vo_file = cand_vo
                    clip_dur = min(raw_dur - trim_in, max(clip_dur, vo_dur + 0.4))

            # DI Color Match + Mood Grade + 35mm Grain + Smooth Transition Fade-in/out + Virtual Camera Rig
            sc_key = (s.get("chapter_id", "CH01"), s.get("location", "LOC"))
            med_yrgb = scene_color_medians.get(sc_key, color_by_shot[sid])
            shot_mood = "warm_flashback" if s.get("is_flashback") else str(s.get("color_mood") or color_mood)
            add_fade_in = bool(s.get("is_flashback") or s.get("transition_in") in ("fade_in", "dissolve"))
            next_shot = usable_shots[shot_idx + 1] if (shot_idx + 1 < len(usable_shots)) else None
            add_fade_out = bool(
                s.get("transition_out") in ("fade_out", "dissolve")
                or (
                    next_shot is not None
                    and (
                        bool(next_shot.get("is_flashback")) != bool(s.get("is_flashback"))
                        or next_shot.get("transition_in") in ("fade_in", "dissolve")
                    )
                )
            )
            di_tail_vf = cls._build_di_grade_vf(
                color_by_shot[sid],
                med_yrgb,
                mood=shot_mood,
                enable_film_grain=enable_film_grain,
                add_fade_in=add_fade_in,
                add_fade_out=add_fade_out,
                clip_dur=clip_dur,
            )
            base_vf = cls._build_virtual_camera_vf(s, clip_dur=clip_dur, di_tail_vf=di_tail_vf)

            # Kiểm tra Tag nhân vật lần đầu tiên trong toàn bộ bộ phim (Face-Aware X placement)
            tag_png: Optional[Path] = None
            primary_cid = s.get("primary_character_id")
            if primary_cid and primary_cid not in tagged_characters and clip_dur >= 3.2 and char_map.get(primary_cid):
                c_info = char_map[primary_cid]
                c_name = c_info.get("name", primary_cid)
                c_role = c_info.get("role", "").split(",")[0].strip() or "Cast"
                tag_png = tags_dir / f"tag_{primary_cid}.png"
                cls.create_character_tag_png(c_name, c_role, tag_png)
                tagged_characters.add(primary_cid)

            card_png: Optional[Path] = None
            if s.get("scene_card_overlay") and clip_dur >= 2.5:
                card_png = tags_dir / f"card_{sid}.png"
                cls.create_scene_card_png(s["scene_card_overlay"], card_png)

            # Chuẩn bị luồng thoại sạch (Dialogue Isolation + Voice Timbre Consistency Lock)
            dlg_wav = audio_dir / f"dlg_{sid}.wav"
            pre_lap_wav: Optional[Path] = None
            post_lap_wav: Optional[Path] = None
            has_raw_audio = cls._probe_has_audio(raw_clip)

            if vo_file is not None:
                af_vo = (
                    f"{CinemaAudioEngine.build_dialogue_cleanup_af(clip_dur=clip_dur)},"
                    f"apad=whole_dur={clip_dur:.3f},atrim=0:{clip_dur:.3f}"
                )
                subprocess.run(
                    ["ffmpeg", "-y", "-i", str(vo_file), "-af", af_vo, "-ar", "48000", "-ac", "2", str(dlg_wav)],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    check=True,
                )
            elif has_raw_audio:
                af_dlg = CinemaAudioEngine.build_dialogue_cleanup_af(clip_dur=clip_dur)
                subprocess.run(
                    [
                        "ffmpeg", "-y",
                        "-ss", f"{trim_in:.3f}", "-t", f"{clip_dur:.3f}", "-i", str(raw_clip),
                        "-vn", "-af", af_dlg, "-ar", "48000", "-ac", "2", str(dlg_wav),
                    ],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    check=True,
                )
                if enable_j_l_cuts:
                    if trim_in >= 0.12:
                        pre_st = max(0.0, trim_in - 0.26)
                        pre_d = trim_in - pre_st
                        cand_pre = audio_dir / f"pre_{sid}.wav"
                        subprocess.run(
                            [
                                "ffmpeg", "-y", "-ss", f"{pre_st:.3f}", "-t", f"{pre_d:.3f}", "-i", str(raw_clip),
                                "-vn", "-af", "aformat=sample_rates=48000:channel_layouts=stereo,highpass=f=80,afftdn=nf=-24",
                                "-ar", "48000", "-ac", "2", str(cand_pre),
                            ],
                            stdout=subprocess.DEVNULL,
                            stderr=subprocess.DEVNULL,
                            check=False,
                        )
                        if cand_pre.exists() and cand_pre.stat().st_size > 200:
                            pre_lap_wav = cand_pre
                    rem_tail = raw_dur - (trim_in + clip_dur)
                    if rem_tail >= 0.12:
                        post_d = min(0.26, rem_tail)
                        cand_post = audio_dir / f"post_{sid}.wav"
                        subprocess.run(
                            [
                                "ffmpeg", "-y",
                                "-ss", f"{trim_in + clip_dur:.3f}", "-t", f"{post_d:.3f}", "-i", str(raw_clip),
                                "-vn", "-af", "aformat=sample_rates=48000:channel_layouts=stereo,highpass=f=80,afftdn=nf=-24",
                                "-ar", "48000", "-ac", "2", str(cand_post),
                            ],
                            stdout=subprocess.DEVNULL,
                            stderr=subprocess.DEVNULL,
                            check=False,
                        )
                        if cand_post.exists() and cand_post.stat().st_size > 200:
                            post_lap_wav = cand_post

                if enable_voice_timbre_lock and primary_cid:
                    if primary_cid not in voice_profiles_by_char:
                        prof = VoiceTimbreMatcher.extract_voice_profile(dlg_wav)
                        if prof is not None:
                            voice_profiles_by_char[primary_cid] = prof
                    else:
                        matched_wav = audio_dir / f"dlg_matched_{sid}.wav"
                        sts_cmd = (char_map.get(primary_cid) or {}).get("voice_converter_cmd")
                        VoiceTimbreMatcher.apply_voice_timbre_match(
                            dlg_wav,
                            voice_profiles_by_char[primary_cid],
                            matched_wav,
                            strength=0.65,
                            voice_converter_cmd=sts_cmd,
                        )
                        dlg_wav = matched_wav
            else:
                n_sil = max(4800, int(round(clip_dur * 48000)))
                cls._write_stereo_wav(dlg_wav, np.zeros(n_sil, dtype=np.float32), sr=48000)

            norm_out = norm_dir / f"norm_{sid}.mp4"
            cmd_norm: List[str] = [
                "ffmpeg", "-y",
                "-ss", f"{trim_in:.3f}", "-t", f"{clip_dur:.3f}", "-i", str(raw_clip),
                "-i", str(dlg_wav),
            ]
            # Input 0 = raw video, Input 1 = cleaned/matched stereo WAV
            extra_inputs = 1
            filter_chains: List[str] = [f"[0:v]{base_vf}[v0]"]
            v_cur = "[v0]"

            if tag_png is not None:
                extra_inputs += 1
                t_idx = extra_inputs
                cmd_norm.extend(["-loop", "1", "-t", f"{clip_dur:.3f}", "-i", str(tag_png)])

                fb = (
                    qc_entry.get("face_boxes")
                    or qc_m.get("face_boxes")
                    or qc_m.get("faces")
                    or (qc_m.get("actor_consistency") or {}).get("face_boxes")
                )
                if fb:
                    _, raw_w, _ = DeliveryPackager._probe_video_info(raw_clip)
                    tag_x = DeliveryPackager.choose_face_aware_tag_x(
                        fb, ref_width=raw_w, default_gaze=s.get("gaze") or ""
                    )
                else:
                    det_fb, raw_w = DeliveryPackager.extract_clip_face_boxes(
                        raw_clip, sample_ts=trim_in + min(1.0, clip_dur * 0.35)
                    )
                    tag_x = DeliveryPackager.choose_face_aware_tag_x(
                        det_fb, ref_width=raw_w, default_gaze=s.get("gaze") or ""
                    )
                tag_y = 210
                filter_chains.append(
                    f"[{t_idx}:v]format=rgba,fade=in:st=0.35:d=0.3:alpha=1,fade=out:st=3.05:d=0.3:alpha=1[tagv]"
                )
                filter_chains.append(f"{v_cur}[tagv]overlay={tag_x}:{tag_y}:enable='between(t,0.35,3.35)'[vtag]")
                v_cur = "[vtag]"

            if card_png is not None:
                extra_inputs += 1
                c_idx = extra_inputs
                cmd_norm.extend(["-loop", "1", "-t", f"{clip_dur:.3f}", "-i", str(card_png)])
                filter_chains.append(
                    f"[{c_idx}:v]format=rgba,fade=in:st=0.25:d=0.25:alpha=1,fade=out:st=2.55:d=0.3:alpha=1[cardv]"
                )
                filter_chains.append(f"{v_cur}[cardv]overlay=90:920:enable='between(t,0.25,2.85)'[vcard]")
                v_cur = "[vcard]"

            filter_chains.append(
                f"[1:a]aformat=sample_rates=48000:channel_layouts=stereo,"
                f"apad=whole_dur={clip_dur:.3f},atrim=0:{clip_dur:.3f}[aout]"
            )

            cmd_norm.extend([
                "-filter_complex", ";".join(filter_chains),
                "-map", v_cur,
                "-map", "[aout]",
                "-c:v", "libx264", "-profile:v", "high", "-preset", "medium", "-crf", "18",
                "-threads", "2",
                "-pix_fmt", "yuv420p", "-r", "24", "-video_track_timescale", "12288",
                "-c:a", "aac", "-b:a", "192k", "-ar", "48000", "-ac", "2",
                str(norm_out),
            ])
            norm_jobs.append({
                "shot": s,
                "shot_id": sid,
                "trim_in": trim_in,
                "dlg_wav": dlg_wav,
                "pre_lap_wav": pre_lap_wav,
                "post_lap_wav": post_lap_wav,
                "cmd_norm": cmd_norm,
                "norm_out": norm_out,
                "qc_m": qc_m,
            })

        # Phase B: Encode normalize đa luồng FFmpeg song song
        def _run_norm_job(job: Dict[str, Any]) -> float:
            subprocess.run(job["cmd_norm"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)
            return cls._probe_duration(job["norm_out"])

        norm_workers = min(4, max(1, (os.cpu_count() or 4) // 2), max(1, len(norm_jobs)))
        if norm_workers > 1:
            with ThreadPoolExecutor(max_workers=norm_workers) as pool:
                norm_durs = list(pool.map(_run_norm_job, norm_jobs))
        else:
            norm_durs = [_run_norm_job(job) for job in norm_jobs]

        # Phase C: Cộng dồn timeline tuần tự theo đúng thứ tự shot
        for job, actual_seg_dur in zip(norm_jobs, norm_durs):
            s = job["shot"]
            sid = job["shot_id"]
            trim_in = job["trim_in"]
            dlg_wav = job["dlg_wav"]
            pre_lap_wav = job["pre_lap_wav"]
            post_lap_wav = job["post_lap_wav"]
            norm_out = job["norm_out"]
            qc_m = job["qc_m"]

            normalized_files.append(norm_out)
            concat_files.append(norm_out)
            capcut_clip_segments.append({
                "path": norm_out,
                "start_s": timeline_cursor_s,
                "duration_s": actual_seg_dur,
            })

            dialogue_seg_specs.append({
                "wav_path": dlg_wav,
                "start_s": timeline_cursor_s,
                "duration_s": actual_seg_dur,
                "pre_lap_wav": pre_lap_wav,
                "post_lap_wav": post_lap_wav,
            })

            loc_id = str(s.get("location") or "LOC_CABIN")
            ambience_segments.append((timeline_cursor_s, actual_seg_dur, loc_id))
            score_segments.append((timeline_cursor_s, actual_seg_dur, CinemaAudioEngine.infer_segment_mood(s)))

            # 12-Class Foley Detection
            sfx_events.extend(
                CinemaAudioEngine.detect_foley_events(
                    str(s.get("action_summary") or ""),
                    start_s=timeline_cursor_s,
                    duration_s=actual_seg_dur,
                )
            )

            # Chương (Chapters)
            ch_id = str(s.get("chapter_id") or "CH01")
            loc_label = loc_name_map.get(loc_id, loc_id)
            if not chapter_spans or chapter_spans[-1]["chapter_id"] != ch_id:
                ch_start = 0.0 if not chapter_spans else timeline_cursor_s
                chapter_spans.append({
                    "chapter_id": ch_id,
                    "start_s": ch_start,
                    "end_s": timeline_cursor_s + actual_seg_dur,
                    "title": f"{ch_id}: {loc_label}",
                })
            else:
                chapter_spans[-1]["end_s"] = timeline_cursor_s + actual_seg_dur

            # Thông tin phụ đề SRT chuẩn Netflix khớp từng từ
            sub_text = s.get("dialogue") or s.get("narration")
            if sub_text:
                qc_words = (qc_m.get("dialogue_qc") or {}).get("words") or []
                srt_shot_specs.append({
                    "shot_id": sid,
                    "speaker": s.get("speaker"),
                    "text": sub_text,
                    "timeline_start_s": timeline_cursor_s,
                    "seg_dur_s": actual_seg_dur,
                    "trim_in_s": trim_in,
                    "words": qc_words,
                })

            timeline_cursor_s += actual_seg_dur

        if with_titles:
            credits_mp4 = norm_dir / "99_end_credits.mp4"
            DeliveryPackager.render_slate_clip(
                credits_mp4,
                kind="credits",
                title=str(project_title),
                characters=(story_bible or {}).get("characters", []),
                duration_s=3.0,
            )
            cred_dur = cls._probe_duration(credits_mp4)
            concat_files.append(credits_mp4)
            capcut_clip_segments.append({
                "path": credits_mp4,
                "start_s": timeline_cursor_s,
                "duration_s": cred_dur,
            })
            score_segments.append((timeline_cursor_s, cred_dur, "emotional_resolution"))
            if ambience_segments:
                ambience_segments.append((timeline_cursor_s, cred_dur, ambience_segments[-1][2]))
            if chapter_spans:
                chapter_spans[-1]["end_s"] = timeline_cursor_s + cred_dur
            timeline_cursor_s += cred_dur

        # 3. Nối toàn bộ các clip đã chuẩn hóa (+ Slates nếu có)
        concat_txt = work_dir / "concat_list.txt"
        concat_txt.write_text(
            "\n".join(f"file '{str(p.resolve()).replace(chr(92), '/')}'" for p in concat_files),
            encoding="utf-8",
        )
        concat_mp4 = work_dir / "concat_video.mp4"
        subprocess.run(
            [
                "ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", str(concat_txt),
                "-c:v", "copy", "-c:a", "copy", str(concat_mp4),
            ],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            check=True,
        )

        total_dur = max(1.0, cls._probe_duration(concat_mp4))

        # 4. Chuẩn bị 4-Stem Audio (J/L-Cut Dialogue + Scene Ambience + 12-Class Foley + Dynamic Score)
        dialogue_wav = audio_dir / "dialogue_stem.wav"
        CinemaAudioEngine.build_dialogue_stem_with_jl_cuts(
            dialogue_seg_specs,
            total_duration_s=total_dur,
            output_wav=dialogue_wav,
            enable_j_l_cuts=enable_j_l_cuts,
        )

        if room_tone_path and Path(room_tone_path).exists():
            room_wav = Path(room_tone_path)
        else:
            room_wav = audio_dir / "scene_ambience.wav"
            CinemaAudioEngine.build_scene_ambience_track(
                ambience_segments,
                output_path=room_wav,
                total_duration_s=total_dur + 0.5,
                assets_audio_dir=assets_audio_dir,
            )

        foley_wav = audio_dir / "foley_sfx.wav"
        CinemaAudioEngine.build_foley_track(
            total_dur + 0.5,
            sfx_events,
            output_path=foley_wav,
            assets_audio_dir=assets_audio_dir,
        )

        if bgm_path and Path(bgm_path).exists():
            bgm_wav = Path(bgm_path)
        else:
            bgm_wav = audio_dir / "dynamic_score.wav"
            CinemaAudioEngine.build_dynamic_score_track(
                score_segments,
                output_path=bgm_wav,
                total_duration_s=total_dur + 0.5,
                assets_audio_dir=assets_audio_dir,
            )

        mixed_mp4 = work_dir / "mixed_pre_loudnorm.mp4"
        # Mọi audio stem truyền qua -i: 0=concat_video, 1=dialogue_stem, 2=ambience, 3=foley, 4=score
        mix_fc = (
            "[1:a]aformat=sample_rates=48000:channel_layouts=stereo,asplit=2[dlg_main][dlg_sc];"
            "[2:a]aformat=sample_rates=48000:channel_layouts=stereo,volume=0.28[room];"
            "[3:a]aformat=sample_rates=48000:channel_layouts=stereo,volume=0.65[foley];"
            "[4:a]aformat=sample_rates=48000:channel_layouts=stereo,volume=0.35[bgm_raw];"
            "[bgm_raw][dlg_sc]sidechaincompress=threshold=0.03:ratio=6:attack=25:release=350[bgm_ducked];"
            f"[dlg_main][room][foley][bgm_ducked]amix=inputs=4:duration=first:normalize=0,atrim=0:{total_dur:.3f}[a_mixed]"
        )
        subprocess.run(
            [
                "ffmpeg", "-y",
                "-i", str(concat_mp4),
                "-i", str(dialogue_wav),
                "-stream_loop", "-1", "-i", str(room_wav),
                "-i", str(foley_wav),
                "-stream_loop", "-1", "-i", str(bgm_wav),
                "-filter_complex", mix_fc,
                "-map", "0:v",
                "-map", "[a_mixed]",
                "-c:v", "copy",
                "-c:a", "aac", "-b:a", "192k", "-ar", "48000", "-ac", "2",
                "-shortest",
                str(mixed_mp4),
            ],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            check=True,
        )

        # 5. Chuẩn hóa âm lượng EBU R128 2-pass -> Master MP4
        ln_meta = cls._loudnorm_two_pass(mixed_mp4, output_mp4, has_video=True)

        # 6. Xuất phụ đề Netflix-Spec .srt rời + .i18n_template.json + nhúng Chapters FFMETADATA1
        srt_entries, i18n_cues = DeliveryPackager.build_srt_entries(srt_shot_specs)
        srt_out = output_mp4.with_suffix(".srt")
        srt_out.write_text("\n".join(srt_entries), encoding="utf-8")

        i18n_out = output_mp4.with_name(f"{output_mp4.stem}.i18n_template.json")
        DeliveryPackager.export_i18n_template(i18n_cues, i18n_out, project_title=str(project_title))

        chapters_txt = DeliveryPackager.embed_chapters_and_export_txt(
            target_mp4=output_mp4,
            chapters=chapter_spans,
            project_title=str(project_title),
        )

        # 7. Xuất M&E Stem & Dialogue Stem rời (khi export_stems=True)
        dialogue_stem_m4a: Optional[Path] = None
        me_stem_m4a: Optional[Path] = None
        if export_stems:
            dialogue_stem_m4a = output_mp4.with_name(f"{output_mp4.stem}.dialogue_stem.m4a")
            subprocess.run(
                [
                    "ffmpeg", "-y",
                    "-i", str(dialogue_wav),
                    "-t", f"{total_dur:.3f}",
                    "-vn", "-c:a", "aac", "-b:a", "192k", "-ar", "48000", "-ac", "2",
                    "-movflags", "+faststart",
                    str(dialogue_stem_m4a),
                ],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                check=True,
            )

            me_pre = work_dir / "me_pre_loudnorm.m4a"
            me_fc = (
                "[0:a]aformat=sample_rates=48000:channel_layouts=stereo,volume=0.32[room];"
                "[1:a]aformat=sample_rates=48000:channel_layouts=stereo,volume=0.70[foley];"
                "[2:a]aformat=sample_rates=48000:channel_layouts=stereo,volume=0.40[bgm];"
                f"[room][foley][bgm]amix=inputs=3:duration=longest:normalize=0,atrim=0:{total_dur:.3f}[me_out]"
            )
            subprocess.run(
                [
                    "ffmpeg", "-y",
                    "-stream_loop", "-1", "-t", f"{total_dur:.3f}", "-i", str(room_wav),
                    "-t", f"{total_dur:.3f}", "-i", str(foley_wav),
                    "-stream_loop", "-1", "-t", f"{total_dur:.3f}", "-i", str(bgm_wav),
                    "-filter_complex", me_fc,
                    "-map", "[me_out]",
                    "-vn", "-c:a", "aac", "-b:a", "192k", "-ar", "48000", "-ac", "2",
                    str(me_pre),
                ],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                check=True,
            )
            me_stem_m4a = output_mp4.with_name(f"{output_mp4.stem}.me_stem.m4a")
            cls._loudnorm_two_pass(me_pre, me_stem_m4a, has_video=False)

        loudness = cls.measure_ebur128(output_mp4)
        master_dur = cls._probe_duration(output_mp4)

        report: Dict[str, Any] = {
            "success": True,
            "master_mp4": str(output_mp4),
            "sidecar_srt": str(srt_out),
            "chapters_txt": str(chapters_txt),
            "i18n_template": str(i18n_out),
            "shots_assembled": len(normalized_files),
            "tagged_characters": sorted(tagged_characters),
            "duration_s": round(master_dur, 2),
            "size_bytes": output_mp4.stat().st_size,
            "loudnorm": ln_meta,
            "ebur128": loudness,
            "capcut_draft_requested": capcut_draft,
        }

        if export_stems and me_stem_m4a and dialogue_stem_m4a:
            report["me_stem"] = str(me_stem_m4a)
            report["dialogue_stem"] = str(dialogue_stem_m4a)

        if capcut_draft:
            draft_meta = output_mp4.with_suffix(".capcut_manifest.json")
            draft_meta.write_text(
                json.dumps(
                    {
                        "master_video": str(output_mp4),
                        "sidecar_srt": str(srt_out),
                        "clips": [str(p) for p in normalized_files],
                        "stems": {
                            "dialogue": str(dialogue_stem_m4a or dialogue_wav),
                            "me_stem": str(me_stem_m4a) if me_stem_m4a else None,
                            "room_tone": str(room_wav),
                            "foley": str(foley_wav),
                            "bgm": str(bgm_wav),
                        },
                    },
                    indent=2,
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )
            report["capcut_manifest"] = str(draft_meta)

            cc_dir = DeliveryPackager.export_capcut_draft_project(
                output_mp4=output_mp4,
                clip_segments=capcut_clip_segments,
                dialogue_stem_path=dialogue_stem_m4a or dialogue_wav,
                me_stem_path=me_stem_m4a or bgm_wav,
                subtitle_cues=i18n_cues,
            )
            report["capcut_draft_dir"] = str(cc_dir)

        if build_promo_kit:
            report["promo_kit"] = DeliveryPackager.build_delivery_kit(
                output_mp4=output_mp4,
                normalized_clips=normalized_files,
                shots=usable_shots,
                project_title=str(project_title),
                qc_reports=qc_reports,
            )

        return report
