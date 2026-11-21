"""
Cinema Delivery Packager (v4 Post-Production):
- Opening Title & End Credits 1080p24 Slate Renderer (`render_slate_clip`)
- Word-Accurate Netflix-Spec SRT (`<= 42` chars/line, max 2 lines) & i18n JSON (`build_srt_entries`, `export_i18n_template`)
- Lossless FFMETADATA1 Chapter Muxing & YouTube `.chapters.txt` (`embed_chapters_and_export_txt`)
- CapCut Desktop Draft Project Exporter (`export_capcut_draft_project`)
- Commercial Promo & Distribution Kit: Trailer, Face-Centered 9:16 Vertical Shorts & 1080p Poster (`build_delivery_kit`)
"""

import json
import os
import shutil
import subprocess
import tempfile
import time
import uuid
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple

import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFont


class DeliveryPackager:
    """Renders broadcast slates, Netflix-spec subtitles, chapters, CapCut drafts, and promo kits."""

    @staticmethod
    def format_srt_time(seconds: float) -> str:
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

    @staticmethod
    def _probe_video_info(media_path: Path) -> Tuple[float, int, int]:
        cmd = [
            "ffprobe", "-v", "error",
            "-select_streams", "v:0",
            "-show_entries", "stream=width,height:format=duration",
            "-of", "json",
            str(media_path),
        ]
        res = subprocess.run(cmd, capture_output=True, text=True, check=False)
        if res.returncode != 0 or not res.stdout.strip():
            return 0.0, 1920, 1080
        data = json.loads(res.stdout)
        dur = float((data.get("format") or {}).get("duration") or 0.0)
        streams = data.get("streams") or []
        w = int(streams[0].get("width") or 1920) if streams else 1920
        h = int(streams[0].get("height") or 1080) if streams else 1080
        return dur, w, h

    @staticmethod
    def _load_font(size: int, bold: bool = False) -> ImageFont.ImageFont:
        names = ("arialbd.ttf", "segoeuib.ttf") if bold else ("arial.ttf", "segoeui.ttf")
        for fn in names:
            try:
                return ImageFont.truetype(fn, size)
            except Exception:
                continue
        return ImageFont.load_default()

    # ----------------- 1. OPENING TITLE & END CREDITS SLATES -----------------
    @classmethod
    def render_slate_clip(
        cls,
        output_mp4: Path,
        kind: str = "opening",
        title: str = "UNTITLED PRODUCTION",
        subtitle: str = "",
        characters: Optional[Sequence[Dict[str, Any]]] = None,
        production_credit: str = "A Muse Studio Cinema v4 Production",
        duration_s: Optional[float] = None,
    ) -> Path:
        """
        Generates a 1920x1080 @ 24fps yuv420p MP4 slate clip with 48kHz stereo silence
        and smooth video fade-in / fade-out.
        """
        output_mp4 = Path(output_mp4)
        output_mp4.parent.mkdir(parents=True, exist_ok=True)
        dur = float(duration_s) if duration_s is not None else (2.5 if kind == "opening" else 3.0)

        img = Image.new("RGB", (1920, 1080), (10, 14, 22))
        draw = ImageDraw.Draw(img)

        if kind == "opening":
            f_title = cls._load_font(68, bold=True)
            f_sub = cls._load_font(30, bold=False)
            t_text = (title or "UNTITLED PRODUCTION").upper()
            tb = draw.textbbox((0, 0), t_text, font=f_title)
            tw, th = tb[2] - tb[0], tb[3] - tb[1]
            tx = (1920 - tw) // 2
            ty = 460 - th // 2
            draw.text((tx, ty), t_text, font=f_title, fill=(248, 250, 252))
            rule_w = min(680, max(240, tw // 2))
            draw.rectangle(
                [(1920 - rule_w) // 2, ty + th + 28, (1920 + rule_w) // 2, ty + th + 31],
                fill=(234, 179, 8),
            )
            if subtitle:
                sb = draw.textbbox((0, 0), subtitle, font=f_sub)
                sw = sb[2] - sb[0]
                draw.text(((1920 - sw) // 2, ty + th + 54), subtitle, font=f_sub, fill=(186, 198, 216))
        else:
            f_hdr = cls._load_font(38, bold=True)
            f_cast = cls._load_font(28, bold=False)
            f_cred = cls._load_font(22, bold=False)

            hdr = "CAST"
            hb = draw.textbbox((0, 0), hdr, font=f_hdr)
            hw = hb[2] - hb[0]
            draw.text(((1920 - hw) // 2, 160), hdr, font=f_hdr, fill=(234, 179, 8))
            draw.rectangle([760, 214, 1160, 216], fill=(71, 85, 105))

            y_cur = 255
            chars = list(characters or [])[:9]
            for c in chars:
                c_name = str(c.get("name") or c.get("id") or "Cast")
                c_role = str(c.get("role") or "Featured Role").split(",")[0].strip()
                line = f"{c_name}   —   {c_role}"
                lb = draw.textbbox((0, 0), line, font=f_cast)
                lw = lb[2] - lb[0]
                draw.text(((1920 - lw) // 2, y_cur), line, font=f_cast, fill=(241, 245, 249))
                y_cur += 54

            if production_credit:
                cb = draw.textbbox((0, 0), production_credit, font=f_cred)
                cw = cb[2] - cb[0]
                draw.text(((1920 - cw) // 2, 930), production_credit, font=f_cred, fill=(148, 163, 184))

        with tempfile.TemporaryDirectory() as td:
            slate_png = Path(td) / "slate.png"
            img.save(slate_png, format="PNG")
            fade_out_st = max(0.1, dur - 0.50)
            vf = (
                f"scale=1920:1080:flags=lanczos,fps=24,format=yuv420p,"
                f"fade=t=in:st=0:d=0.40,fade=t=out:st={fade_out_st:.3f}:d=0.45"
            )
            cmd = [
                "ffmpeg", "-y",
                "-loop", "1", "-t", f"{dur:.3f}", "-i", str(slate_png),
                "-f", "lavfi", "-t", f"{dur:.3f}", "-i", "anullsrc=channel_layout=stereo:sample_rate=48000",
                "-vf", vf,
                "-c:v", "libx264", "-profile:v", "high", "-preset", "fast", "-crf", "18",
                "-pix_fmt", "yuv420p", "-r", "24", "-video_track_timescale", "12288",
                "-c:a", "aac", "-b:a", "192k", "-ar", "48000", "-ac", "2",
                "-shortest", str(output_mp4),
            ]
            subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)

        return output_mp4

    # ----------------- 2. WORD-ACCURATE NETFLIX-SPEC SRT -----------------
    @staticmethod
    def _wrap_lines_42(text: str, max_chars: int = 42) -> List[str]:
        tokens = text.strip().split()
        if not tokens:
            return []
        lines: List[str] = []
        cur = ""
        for tok in tokens:
            while len(tok) > max_chars:
                if cur:
                    lines.append(cur)
                    cur = ""
                lines.append(tok[:max_chars])
                tok = tok[max_chars:]
            if not cur:
                cur = tok
            elif len(cur) + 1 + len(tok) <= max_chars:
                cur = f"{cur} {tok}"
            else:
                lines.append(cur)
                cur = tok
        if cur:
            lines.append(cur)
        return lines

    @classmethod
    def build_srt_entries(
        cls,
        timeline_shots: Sequence[Dict[str, Any]],
        max_line_chars: int = 42,
        max_lines: int = 2,
    ) -> Tuple[List[str], List[Dict[str, Any]]]:
        """
        Builds Netflix-spec SRT blocks (`<= 42` chars/line, max 2 lines) accounting for `trim_in_s`
        and Whisper word timestamps when available.
        Returns `(srt_blocks, i18n_cues)`.
        """
        srt_blocks: List[str] = []
        i18n_cues: List[Dict[str, Any]] = []
        cue_idx = 1

        for item in timeline_shots:
            raw_text = str(item.get("text") or item.get("dialogue") or item.get("narration") or "").strip()
            if not raw_text:
                continue

            sid = str(item.get("shot_id") or f"SH_{cue_idx:03d}")
            speaker = str(item.get("speaker") or "").strip()
            speaker_prefix = f"{speaker}: " if speaker else ""
            tl_start = float(item.get("timeline_start_s", 0.0))
            seg_dur = max(0.4, float(item.get("seg_dur_s", 3.0)))
            trim_in = float(item.get("trim_in_s", 0.0))
            words = list(item.get("words") or [])

            src_tokens = raw_text.split()
            if words and src_tokens:
                n_w = len(words)
                n_t = len(src_tokens)
                timed_tokens: List[Tuple[str, float, float]] = []
                for ti, tok in enumerate(src_tokens):
                    wi_st = min(n_w - 1, int(round(ti * (n_w - 1) / max(1, n_t - 1)))) if n_t > 1 else 0
                    wi_en = min(n_w - 1, int(round((ti + 1) * n_w / n_t)) - 1) if n_t > 1 else (n_w - 1)
                    wi_en = max(wi_st, wi_en)
                    w_st_rel = max(0.0, min(seg_dur, float(words[wi_st].get("start", 0.0)) - trim_in))
                    w_en_rel = max(w_st_rel + 0.04, min(seg_dur, float(words[wi_en].get("end", w_st_rel + 0.2)) - trim_in))
                    timed_tokens.append((tok, tl_start + w_st_rel, tl_start + w_en_rel))

                groups: List[Tuple[str, float, float]] = []
                cur_toks: List[str] = []
                cur_st = timed_tokens[0][1]
                cur_en = timed_tokens[0][2]
                first_group = True

                for ti, (tok, t_st, t_en) in enumerate(timed_tokens):
                    pref = speaker_prefix if first_group else ""
                    cand_text = pref + (" ".join(cur_toks + [tok]))
                    cand_lines = cls._wrap_lines_42(cand_text, max_chars=max_line_chars)
                    pause_gap = (t_st - cur_en) if cur_toks else 0.0
                    punct_break = bool(cur_toks and cur_toks[-1].endswith((".", "!", "?", ";")) and pause_gap >= 0.45)

                    if cur_toks and (len(cand_lines) > max_lines or punct_break):
                        grp_text = (speaker_prefix if first_group else "") + " ".join(cur_toks)
                        groups.append((grp_text, cur_st, cur_en))
                        first_group = False
                        cur_toks = [tok]
                        cur_st = t_st
                        cur_en = t_en
                    else:
                        if not cur_toks:
                            cur_st = t_st
                        cur_toks.append(tok)
                        cur_en = max(cur_en, t_en)

                if cur_toks:
                    grp_text = (speaker_prefix if first_group else "") + " ".join(cur_toks)
                    groups.append((grp_text, cur_st, cur_en))
            else:
                # Fallback to segment bounds when Whisper word timestamps are unavailable
                ut_st = tl_start + 0.15
                ut_en = tl_start + max(0.8, seg_dur - 0.15)
                if ut_en <= ut_st:
                    ut_st = tl_start
                    ut_en = tl_start + seg_dur

                chunks_text: List[str] = []
                cur_toks = []
                first_group = True
                for tok in src_tokens:
                    pref = speaker_prefix if first_group else ""
                    cand = pref + " ".join(cur_toks + [tok])
                    if cur_toks and len(cls._wrap_lines_42(cand, max_chars=max_line_chars)) > max_lines:
                        chunks_text.append((speaker_prefix if first_group else "") + " ".join(cur_toks))
                        first_group = False
                        cur_toks = [tok]
                    else:
                        cur_toks.append(tok)
                if cur_toks:
                    chunks_text.append((speaker_prefix if first_group else "") + " ".join(cur_toks))

                total_chars = max(1, sum(len(c) for c in chunks_text))
                span = max(0.2, ut_en - ut_st)
                cursor = ut_st
                groups = []
                for ci, c_txt in enumerate(chunks_text):
                    c_dur = span * (len(c_txt) / total_chars)
                    c_end = ut_en if ci == len(chunks_text) - 1 else (cursor + c_dur)
                    groups.append((c_txt, cursor, c_end))
                    cursor = c_end

            for grp_text, g_st, g_en in groups:
                lines = cls._wrap_lines_42(grp_text, max_chars=max_line_chars)[:max_lines]
                if not lines:
                    continue
                g_en = max(g_st + 0.20, g_en)
                st_srt = cls.format_srt_time(g_st)
                en_srt = cls.format_srt_time(g_en)
                formatted_body = "\n".join(lines)
                srt_blocks.append(f"{cue_idx}\n{st_srt} --> {en_srt}\n{formatted_body}\n")
                i18n_cues.append({
                    "cue_id": cue_idx,
                    "shot_id": sid,
                    "speaker": speaker or None,
                    "start_s": round(g_st, 3),
                    "end_s": round(g_en, 3),
                    "start_srt": st_srt,
                    "end_srt": en_srt,
                    "source_text": grp_text,
                    "formatted_lines": lines,
                    "translations": {},
                })
                cue_idx += 1

        return srt_blocks, i18n_cues

    @staticmethod
    def export_i18n_template(
        cues: Sequence[Dict[str, Any]],
        output_json: Path,
        project_title: str = "",
        source_language: str = "en",
    ) -> Path:
        output_json = Path(output_json)
        output_json.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "project_title": project_title,
            "source_language": source_language,
            "target_languages": ["vi", "es", "fr", "de", "ja"],
            "cues": list(cues),
        }
        output_json.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
        return output_json

    # ----------------- 3. FFMETADATA1 CHAPTERS & YOUTUBE CHAPTERS -----------------
    @staticmethod
    def _escape_ffmeta(val: str) -> str:
        out = str(val or "").replace("\\", "\\\\")
        for ch in ("=", ";", "#"):
            out = out.replace(ch, f"\\{ch}")
        return out.replace("\n", " ")

    @staticmethod
    def _format_yt_time(seconds: float) -> str:
        s_int = max(0, int(round(seconds)))
        h = s_int // 3600
        m = (s_int % 3600) // 60
        s = s_int % 60
        if h > 0:
            return f"{h:02d}:{m:02d}:{s:02d}"
        return f"{m:02d}:{s:02d}"

    @classmethod
    def embed_chapters_and_export_txt(
        cls,
        target_mp4: Path,
        chapters: Sequence[Dict[str, Any]],
        project_title: str = "",
        output_mp4: Optional[Path] = None,
    ) -> Path:
        """
        Writes `<stem>.chapters.txt` (`00:00 - CH01: Location`) and losslessly muxes
        `FFMETADATA1` `[CHAPTER]` markers into `output_mp4` (or `target_mp4` in-place).
        """
        target_mp4 = Path(target_mp4)
        dest_mp4 = Path(output_mp4) if output_mp4 else target_mp4
        chapters_txt = dest_mp4.with_name(f"{dest_mp4.stem}.chapters.txt")

        clean_chaps: List[Dict[str, Any]] = []
        for idx, ch in enumerate(chapters):
            st = 0.0 if idx == 0 else max(0.0, float(ch.get("start_s", 0.0)))
            en = max(st + 0.1, float(ch.get("end_s", st + 1.0)))
            title = str(ch.get("title") or f"CH{idx + 1:02d}")
            clean_chaps.append({"start_s": st, "end_s": en, "title": title})

        if not clean_chaps:
            dur, _, _ = cls._probe_video_info(target_mp4)
            clean_chaps = [{"start_s": 0.0, "end_s": max(1.0, dur), "title": "CH01: Opening"}]

        yt_lines = [f"{cls._format_yt_time(c['start_s'])} - {c['title']}" for c in clean_chaps]
        chapters_txt.parent.mkdir(parents=True, exist_ok=True)
        chapters_txt.write_text("\n".join(yt_lines) + "\n", encoding="utf-8")

        meta_lines = [";FFMETADATA1"]
        if project_title:
            meta_lines.append(f"title={cls._escape_ffmeta(project_title)}")
        meta_lines.append("")

        for c in clean_chaps:
            st_ms = int(round(c["start_s"] * 1000))
            en_ms = max(st_ms + 100, int(round(c["end_s"] * 1000)))
            meta_lines.extend([
                "[CHAPTER]",
                "TIMEBASE=1/1000",
                f"START={st_ms}",
                f"END={en_ms}",
                f"title={cls._escape_ffmeta(c['title'])}",
                "",
            ])

        with tempfile.TemporaryDirectory() as td:
            ffmeta_p = Path(td) / "ffmeta.txt"
            ffmeta_p.write_text("\n".join(meta_lines), encoding="utf-8")
            tmp_out = Path(td) / "muxed_chapters.mp4"
            subprocess.run(
                [
                    "ffmpeg", "-y",
                    "-i", str(target_mp4),
                    "-f", "ffmetadata", "-i", str(ffmeta_p),
                    "-map", "0",
                    "-map_metadata", "1",
                    "-c", "copy",
                    "-movflags", "+faststart",
                    str(tmp_out),
                ],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                check=True,
            )
            dest_mp4.parent.mkdir(parents=True, exist_ok=True)
            shutil.move(str(tmp_out), str(dest_mp4))

        return chapters_txt

    # ----------------- 4. CAPCUT DESKTOP DRAFT PROJECT -----------------
    @classmethod
    def export_capcut_draft_project(
        cls,
        output_mp4: Path,
        clip_segments: Sequence[Dict[str, Any]],
        dialogue_stem_path: Optional[Path] = None,
        me_stem_path: Optional[Path] = None,
        subtitle_cues: Optional[Sequence[Dict[str, Any]]] = None,
    ) -> Path:
        """
        Generates CapCut Desktop Draft directory `<output_mp4.parent>/capcut_draft_<output_mp4.stem>`
        with `draft_content.json` and `draft_meta_info.json`.
        """
        output_mp4 = Path(output_mp4)
        draft_dir = output_mp4.parent / f"capcut_draft_{output_mp4.stem}"
        draft_dir.mkdir(parents=True, exist_ok=True)

        def _uid() -> str:
            return str(uuid.uuid4()).upper()

        videos_mat: List[Dict[str, Any]] = []
        audios_mat: List[Dict[str, Any]] = []
        texts_mat: List[Dict[str, Any]] = []
        video_segs: List[Dict[str, Any]] = []

        cursor_us = 0
        has_separate_dlg = bool(dialogue_stem_path and Path(dialogue_stem_path).exists())

        for seg in clip_segments:
            c_path = Path(seg["path"]).resolve()
            dur_s = max(0.1, float(seg.get("duration_s", 1.0)))
            dur_us = int(round(dur_s * 1_000_000))
            mat_id = _uid()
            videos_mat.append({
                "id": mat_id,
                "type": "video",
                "path": str(c_path),
                "material_name": c_path.name,
                "width": 1920,
                "height": 1080,
                "duration": dur_us,
                "has_audio": True,
            })
            video_segs.append({
                "id": _uid(),
                "material_id": mat_id,
                "source_timerange": {"start": 0, "duration": dur_us},
                "target_timerange": {"start": cursor_us, "duration": dur_us},
                "speed": 1.0,
                "volume": 0.0 if has_separate_dlg else 1.0,
                "visible": True,
                "render_index": 0,
                "extra_material_refs": [],
            })
            cursor_us += dur_us

        total_us = max(cursor_us, 1_000_000)
        tracks: List[Dict[str, Any]] = [
            {"id": _uid(), "type": "video", "attribute": 0, "flag": 0, "segments": video_segs}
        ]

        audio_layer = 0
        for stem_label, stem_p in (("Dialogue Stem", dialogue_stem_path), ("M&E Stem", me_stem_path)):
            if stem_p and Path(stem_p).exists():
                sp = Path(stem_p).resolve()
                mat_id = _uid()
                audios_mat.append({
                    "id": mat_id,
                    "type": "music",
                    "path": str(sp),
                    "name": stem_label,
                    "duration": total_us,
                })
                tracks.append({
                    "id": _uid(),
                    "type": "audio",
                    "attribute": 0,
                    "flag": 0,
                    "segments": [{
                        "id": _uid(),
                        "material_id": mat_id,
                        "source_timerange": {"start": 0, "duration": total_us},
                        "target_timerange": {"start": 0, "duration": total_us},
                        "speed": 1.0,
                        "volume": 1.0,
                        "visible": True,
                        "render_index": audio_layer,
                        "extra_material_refs": [],
                    }],
                })
                audio_layer += 1

        text_segs: List[Dict[str, Any]] = []
        last_txt_end_us = 0
        for idx, cue in enumerate(subtitle_cues or []):
            lines = cue.get("formatted_lines") or [str(cue.get("source_text") or "")]
            txt_val = "\n".join(lines).strip()
            if not txt_val:
                continue
            st_us = max(last_txt_end_us, int(round(float(cue.get("start_s", 0.0)) * 1_000_000)))
            en_us = max(st_us + 200_000, int(round(float(cue.get("end_s", 1.0)) * 1_000_000)))
            dur_us = en_us - st_us
            last_txt_end_us = en_us

            mat_id = _uid()
            texts_mat.append({
                "id": mat_id,
                "type": "subtitle",
                "content": json.dumps({
                    "text": txt_val,
                    "styles": [{
                        "fill": {"content": {"solid": {"color": [1.0, 1.0, 1.0]}}},
                        "size": 7.0,
                        "range": [0, len(txt_val)],
                    }],
                }, ensure_ascii=False),
            })
            text_segs.append({
                "id": _uid(),
                "material_id": mat_id,
                "source_timerange": {"start": 0, "duration": dur_us},
                "target_timerange": {"start": st_us, "duration": dur_us},
                "speed": 1.0,
                "volume": 1.0,
                "visible": True,
                "render_index": 14000 + idx,
                "extra_material_refs": [],
            })

        tracks.append({
            "id": _uid(),
            "type": "text",
            "attribute": 0,
            "flag": 0,
            "segments": text_segs,
        })

        draft_id = _uid()
        draft_content = {
            "id": draft_id,
            "version": 360000,
            "fps": 24.0,
            "duration": total_us,
            "canvas_config": {"width": 1920, "height": 1080, "ratio": "16:9"},
            "materials": {
                "videos": videos_mat,
                "audios": audios_mat,
                "texts": texts_mat,
                "speeds": [],
                "canvases": [],
                "effects": [],
                "transitions": [],
                "animations": [],
                "stickers": [],
                "sound_channel_mappings": [],
                "vocal_separations": [],
            },
            "tracks": tracks,
        }

        now_us = int(time.time() * 1_000_000)
        draft_meta = {
            "draft_id": draft_id,
            "draft_name": output_mp4.stem,
            "draft_fold_path": str(draft_dir.resolve()),
            "draft_root_path": str(draft_dir.parent.resolve()),
            "tm_draft_create": now_us,
            "tm_draft_modified": now_us,
            "tm_duration": total_us,
            "draft_materials": [
                {
                    "type": 0,
                    "value": [
                        {"file_Path": m["path"], "duration": m["duration"], "width": 1920, "height": 1080}
                        for m in videos_mat
                    ],
                }
            ],
        }

        (draft_dir / "draft_content.json").write_text(
            json.dumps(draft_content, indent=2, ensure_ascii=False), encoding="utf-8"
        )
        (draft_dir / "draft_meta_info.json").write_text(
            json.dumps(draft_meta, indent=2, ensure_ascii=False), encoding="utf-8"
        )
        return draft_dir

    # ----------------- 5. FACE DETECTION & PROMO DELIVERY KIT -----------------
    @staticmethod
    def detect_face_boxes(bgr_img: Optional[np.ndarray]) -> List[List[int]]:
        """
        Detects actor face/head bounding boxes `[x, y, w, h]` in pixel coordinates.
        Uses OpenCV Haar CascadeClassifier if present in the build, with a clean YCrCb
        skin-region connected-components fallback for OpenCV 5.x builds without legacy objdetect.
        """
        if bgr_img is None or bgr_img.size == 0:
            return []

        h, w = bgr_img.shape[:2]
        cascade_cls = getattr(cv2, "CascadeClassifier", None)
        cv2_data = getattr(cv2, "data", None)
        haar_dir = getattr(cv2_data, "haarcascades", "") if cv2_data else ""
        xml_path = os.path.join(haar_dir, "haarcascade_frontalface_default.xml") if haar_dir else ""

        if cascade_cls is not None and xml_path and os.path.exists(xml_path):
            try:
                det = cascade_cls(xml_path)
                if not det.empty():
                    gray = cv2.cvtColor(bgr_img, cv2.COLOR_BGR2GRAY)
                    faces = det.detectMultiScale(gray, scaleFactor=1.1, minNeighbors=4, minSize=(40, 40))
                    if len(faces) > 0:
                        return [[int(x), int(y), int(fw), int(fh)] for (x, y, fw, fh) in faces]
            except Exception:
                pass

        # OpenCV 5.x fallback: YCrCb skin-chroma head candidate detection in upper 75% of frame
        ycrcb = cv2.cvtColor(bgr_img, cv2.COLOR_BGR2YCrCb)
        mask = cv2.inRange(ycrcb, np.array([35, 133, 77], dtype=np.uint8), np.array([245, 177, 127], dtype=np.uint8))
        mask[int(h * 0.78) :, :] = 0
        kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (7, 7))
        mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, kernel)
        mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel)

        num_labels, _, stats, _ = cv2.connectedComponentsWithStats(mask, connectivity=8)
        frame_area = float(w * h)
        boxes: List[List[int]] = []
        for lbl in range(1, num_labels):
            bx = int(stats[lbl, cv2.CC_STAT_LEFT])
            by = int(stats[lbl, cv2.CC_STAT_TOP])
            bw = int(stats[lbl, cv2.CC_STAT_WIDTH])
            bh = int(stats[lbl, cv2.CC_STAT_HEIGHT])
            area = float(stats[lbl, cv2.CC_STAT_AREA])
            if area < frame_area * 0.0025 or area > frame_area * 0.22:
                continue
            ar = bw / max(1.0, float(bh))
            fill_ratio = area / max(1.0, float(bw * bh))
            if 0.45 <= ar <= 1.55 and fill_ratio >= 0.42:
                boxes.append([bx, by, bw, bh])

        boxes.sort(key=lambda b: b[2] * b[3], reverse=True)
        return boxes[:4]

    @classmethod
    def extract_clip_face_boxes(cls, clip_path: Path, sample_ts: float = 0.6) -> Tuple[List[List[int]], int]:
        dur, w, _ = cls._probe_video_info(clip_path)
        ts = min(max(0.1, sample_ts), max(0.1, dur * 0.5))
        with tempfile.TemporaryDirectory() as td:
            fp = Path(td) / "f.png"
            subprocess.run(
                ["ffmpeg", "-y", "-ss", f"{ts:.2f}", "-i", str(clip_path), "-vframes", "1", str(fp)],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                check=False,
            )
            if fp.exists() and fp.stat().st_size > 0:
                bgr = cv2.imread(str(fp))
                if bgr is not None:
                    return cls.detect_face_boxes(bgr), int(bgr.shape[1])
        return [], w

    @staticmethod
    def _parse_normalized_centers_and_areas(
        face_boxes: Sequence[Any],
        ref_width: int = 1920,
    ) -> List[Tuple[float, float]]:
        out: List[Tuple[float, float]] = []
        rw = max(1.0, float(ref_width))
        for b in face_boxes or []:
            if isinstance(b, dict):
                x = float(b.get("x_norm", b.get("x", 0.0)))
                w = float(b.get("w_norm", b.get("w", b.get("width", 0.0))))
                h = float(b.get("h_norm", b.get("h", b.get("height", w))))
            elif isinstance(b, (list, tuple)) and len(b) >= 4:
                x, _, w, h = float(b[0]), float(b[1]), float(b[2]), float(b[3])
            else:
                continue
            if max(abs(x), abs(w)) <= 1.05:
                cx = x + 0.5 * w
                area = max(1e-4, w * h)
            else:
                cx = (x + 0.5 * w) / rw
                area = max(1.0, w * h) / (rw * rw)
            out.append((max(0.0, min(1.0, cx)), area))
        return out

    @classmethod
    def choose_face_aware_tag_x(
        cls,
        face_boxes: Optional[Sequence[Any]],
        ref_width: int = 1920,
        default_gaze: str = "",
    ) -> int:
        """
        Selects character tag X (`180` left vs `1220` right on 1080p canvas) on whichever
        screen half has fewer/smaller detected faces so tags never cover a second actor.
        """
        parsed = cls._parse_normalized_centers_and_areas(face_boxes or [], ref_width=ref_width)
        if parsed:
            left_faces = [a for cx, a in parsed if cx < 0.5]
            right_faces = [a for cx, a in parsed if cx >= 0.5]
            if len(left_faces) < len(right_faces):
                return 180
            if len(right_faces) < len(left_faces):
                return 1220
            if sum(left_faces) <= sum(right_faces):
                return 180
            return 1220

        return 1220 if "screen-right" in (default_gaze or "").lower() else 180

    @classmethod
    def build_delivery_kit(
        cls,
        output_mp4: Path,
        normalized_clips: Sequence[Path],
        shots: Sequence[Dict[str, Any]],
        project_title: str = "MUSE FEATURE FILM",
        qc_reports: Optional[Dict[str, Dict[str, Any]]] = None,
    ) -> Dict[str, str]:
        """
        Generates `<output_mp4.parent>/DELIVERY_KIT/` containing:
          1. `trailer_1080p.mp4` (Opening Title + top climax/key clips trimmed <= 2.5s)
          2. `shorts_vertical_9x16.mp4` (`1080x1920` vertical smart-cropped around actor face X-center)
          3. `poster_1080p.png` (`1920x1080` hero frame with vignette, letterbox bars & bold title)
        """
        output_mp4 = Path(output_mp4)
        kit_dir = output_mp4.parent / "DELIVERY_KIT"
        kit_dir.mkdir(parents=True, exist_ok=True)

        trailer_mp4 = kit_dir / "trailer_1080p.mp4"
        shorts_mp4 = kit_dir / "shorts_vertical_9x16.mp4"
        poster_png = kit_dir / "poster_1080p.png"

        pairs = list(zip(shots, normalized_clips)) if shots and len(shots) == len(normalized_clips) else [
            ({"shot_id": f"SH_{i:02d}"}, p) for i, p in enumerate(normalized_clips)
        ]
        if not pairs:
            pairs = [({"shot_id": "MASTER"}, output_mp4)]

        # Prioritize climax shots + key narrative beats (up to 4 highlights)
        climax_pairs = [pr for pr in pairs if pr[0].get("is_climax_closeup")]
        other_pairs = [pr for pr in pairs if not pr[0].get("is_climax_closeup")]
        selected = (climax_pairs + other_pairs)[:4]

        with tempfile.TemporaryDirectory() as td:
            tmp = Path(td)
            # 1. Trailer 1080p (Opening Card <= 2.0s + trimmed highlight clips <= 2.2s each)
            t_open = cls.render_slate_clip(
                tmp / "tr_open.mp4",
                kind="opening",
                title=project_title,
                subtitle="OFFICIAL TRAILER",
                duration_s=2.0,
            )
            tr_parts: List[Path] = [t_open]
            v_parts: List[Path] = []

            for idx, (s_meta, c_path) in enumerate(selected):
                c_path = Path(c_path)
                c_dur, c_w, _ = cls._probe_video_info(c_path)
                seg_len = min(2.2, max(0.8, c_dur))
                st_off = max(0.0, (c_dur - seg_len) * 0.5)
                fo_st = max(0.05, seg_len - 0.18)

                tr_seg = tmp / f"tr_{idx:02d}.mp4"
                subprocess.run(
                    [
                        "ffmpeg", "-y", "-ss", f"{st_off:.3f}", "-t", f"{seg_len:.3f}", "-i", str(c_path),
                        "-vf", f"scale=1920:1080:flags=lanczos,fps=24,format=yuv420p,fade=t=in:st=0:d=0.15,fade=t=out:st={fo_st:.3f}:d=0.18",
                        "-af", f"aformat=sample_rates=48000:channel_layouts=stereo,afade=t=in:st=0:d=0.05,afade=t=out:st={fo_st:.3f}:d=0.10",
                        "-c:v", "libx264", "-profile:v", "high", "-preset", "fast", "-crf", "19",
                        "-pix_fmt", "yuv420p", "-r", "24", "-video_track_timescale", "12288",
                        "-c:a", "aac", "-b:a", "192k", "-ar", "48000", "-ac", "2",
                        str(tr_seg),
                    ],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    check=True,
                )
                tr_parts.append(tr_seg)

                # Determine face X-center (0..1) for 9:16 vertical crop
                sid = str(s_meta.get("shot_id") or "")
                qc_entry = (qc_reports or {}).get(sid, {})
                qc_metrics = qc_entry.get("metrics") or {}
                fb = (
                    qc_entry.get("face_boxes")
                    or qc_metrics.get("face_boxes")
                    or (qc_metrics.get("actor_consistency") or {}).get("face_boxes")
                )
                ref_w = c_w
                if not fb:
                    fb, ref_w = cls.extract_clip_face_boxes(c_path)
                parsed_faces = cls._parse_normalized_centers_and_areas(fb or [], ref_width=ref_w)
                if parsed_faces:
                    total_a = sum(a for _, a in parsed_faces) or 1.0
                    cx_norm = sum(cx * a for cx, a in parsed_faces) / total_a
                else:
                    cx_norm = 0.5

                # Scale 16:9 -> 3414x1920 and crop 1080x1920 centered around cx_norm
                scaled_w = 3414
                crop_x = int(round(cx_norm * scaled_w - 540))
                crop_x = max(0, min(scaled_w - 1080, crop_x))
                crop_x -= crop_x % 2

                v_seg = tmp / f"vert_{idx:02d}.mp4"
                subprocess.run(
                    [
                        "ffmpeg", "-y", "-ss", f"{st_off:.3f}", "-t", f"{seg_len:.3f}", "-i", str(c_path),
                        "-vf", f"scale={scaled_w}:1920:flags=lanczos,crop=1080:1920:{crop_x}:0,fps=24,format=yuv420p",
                        "-af", f"aformat=sample_rates=48000:channel_layouts=stereo,afade=t=in:st=0:d=0.05,afade=t=out:st={fo_st:.3f}:d=0.08",
                        "-c:v", "libx264", "-profile:v", "high", "-preset", "fast", "-crf", "19",
                        "-pix_fmt", "yuv420p", "-r", "24", "-video_track_timescale", "12288",
                        "-c:a", "aac", "-b:a", "192k", "-ar", "48000", "-ac", "2",
                        str(v_seg),
                    ],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    check=True,
                )
                v_parts.append(v_seg)

            tr_list = tmp / "tr_concat.txt"
            tr_list.write_text(
                "\n".join(f"file '{str(p.resolve()).replace(chr(92), '/')}'" for p in tr_parts),
                encoding="utf-8",
            )
            subprocess.run(
                [
                    "ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", str(tr_list),
                    "-c", "copy", "-movflags", "+faststart", str(trailer_mp4),
                ],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                check=True,
            )

            v_list = tmp / "v_concat.txt"
            v_list.write_text(
                "\n".join(f"file '{str(p.resolve()).replace(chr(92), '/')}'" for p in v_parts),
                encoding="utf-8",
            )
            subprocess.run(
                [
                    "ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", str(v_list),
                    "-c", "copy", "-movflags", "+faststart", str(shorts_mp4),
                ],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                check=True,
            )

            # 3. Hero Poster 1920x1080 PNG
            hero_clip = Path(selected[0][1])
            h_dur, _, _ = cls._probe_video_info(hero_clip)
            hero_raw = tmp / "hero_raw.png"
            subprocess.run(
                [
                    "ffmpeg", "-y", "-ss", f"{max(0.2, h_dur * 0.5):.2f}",
                    "-i", str(hero_clip), "-vframes", "1", str(hero_raw),
                ],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                check=True,
            )
            with Image.open(hero_raw) as im:
                base_rgb = im.convert("RGB").resize((1920, 1080), Image.Resampling.LANCZOS)

            arr = np.asarray(base_rgb, dtype=np.float32)
            yy = np.linspace(-1.0, 1.0, 1080, dtype=np.float32)[:, None]
            xx = np.linspace(-1.0, 1.0, 1920, dtype=np.float32)[None, :]
            rad2 = xx * xx + yy * yy
            vignette = np.clip(1.0 - 0.38 * rad2, 0.35, 1.0)
            # Darken lower quarter softly for title legibility
            bottom_grad = np.clip(1.0 - 0.55 * np.maximum(0.0, (yy - 0.35) / 0.65), 0.35, 1.0)
            graded = np.clip(arr * (vignette * bottom_grad)[:, :, None], 0.0, 255.0).astype(np.uint8)

            poster = Image.fromarray(graded, mode="RGB")
            draw = ImageDraw.Draw(poster)
            # Cinematic 2.39:1 letterbox bars
            bar_h = 88
            draw.rectangle([0, 0, 1920, bar_h], fill=(8, 10, 15))
            draw.rectangle([0, 1080 - bar_h, 1920, 1080], fill=(8, 10, 15))

            f_poster = cls._load_font(74, bold=True)
            p_title = (project_title or "MUSE FEATURE FILM").upper()
            tb = draw.textbbox((0, 0), p_title, font=f_poster)
            tw, th = tb[2] - tb[0], tb[3] - tb[1]
            tx = (1920 - tw) // 2
            ty = 1080 - bar_h - th - 48
            draw.text((tx + 3, ty + 3), p_title, font=f_poster, fill=(0, 0, 0))
            draw.text((tx, ty), p_title, font=f_poster, fill=(248, 250, 252))
            poster.save(poster_png, format="PNG")

        return {
            "kit_dir": str(kit_dir),
            "trailer_mp4": str(trailer_mp4),
            "shorts_mp4": str(shorts_mp4),
            "poster_png": str(poster_png),
        }
