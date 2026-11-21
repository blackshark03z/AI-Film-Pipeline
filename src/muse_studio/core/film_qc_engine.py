#!/usr/bin/env python3
"""
Film QA/QC Engine for Muse Studio & AI Filmmaking Pipeline (Preflight + 5-Gate Postflight).
1. Preflight QA:
   - Prompt 5-Aspect (16:9, locked-off static tripod), Hand Anatomy Guard
   - Keyframe integrity & anti-hardsub check (KeyframeComposer)
   - Story-level 180-degree axis lock, dialogue vs silent consistency & duplicate anchor detection
2. Post-Generation 5-Gate QC:
   - Gate 1: FFprobe specs & full FFmpeg stream decode (`-v error -f null -`)
   - Gate 2: Windowed temporal motion energy (4fps) & freeze-frame / blackout detection
   - Gate 3: Flicker / luma-jump detection (`> 60.0`) + Optical Flow camera drift & head motion
   - Gate 4: Hand ROI anomaly scan + Defensive Trim Point + 4-frame Contact Strip generation
   - Gate 5: Faster-Whisper ASR (`base.en` int8) WER <= 15% + exact `trim_in_s` / `trim_out_s`
"""

import json
import re
import subprocess
import tempfile
import threading
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import cv2
import numpy as np
from PIL import Image, ImageDraw

try:
    from .keyframe_composer import KeyframeComposer
    from .staging import is_legacy_generated_cutaway
except ImportError:
    from core.keyframe_composer import KeyframeComposer
    from core.staging import is_legacy_generated_cutaway


class FilmQCEngine:
    """Bộ máy kiểm định chất lượng điện ảnh toàn diện (Preflight & Postflight 5-Gate)."""

    _whisper_model = None
    _whisper_lock = threading.Lock()
    _whisper_transcribe_lock = threading.Lock()

    @classmethod
    def get_whisper_model(cls, model_size: str = "base.en"):
        """Singleton cache an toàn đa luồng cho model Faster-Whisper để tối ưu hóa tốc độ CPU."""
        if cls._whisper_model is None:
            with cls._whisper_lock:
                if cls._whisper_model is None:
                    try:
                        from faster_whisper import WhisperModel
                        cls._whisper_model = WhisperModel(model_size, device="cpu", compute_type="int8")
                    except Exception as e:
                        print(f"[!] Warning: Cannot initialize Faster-Whisper model: {e}")
                        cls._whisper_model = False
        return cls._whisper_model if cls._whisper_model is not False else None

    # ----------------- 1. TIỀN KIỂM (PREFLIGHT QA) -----------------
    @staticmethod
    def validate_shot_preflight(shot: Dict[str, Any], prev_shot: Optional[Dict[str, Any]] = None) -> Tuple[bool, List[str]]:
        """Kiểm định trước khi gen cho từng shot: prompt 5-Aspect, ảnh đầu, trục & an toàn bàn tay."""
        errors: List[str] = []
        if is_legacy_generated_cutaway(shot):
            errors.append("LEGACY_STAGING_CUTAWAY: Recompile the project to resolve the source beat before rendering.")
        prompt = shot.get("prompt") or shot.get("compiled_prompt") or ""

        if not prompt or len(prompt.strip()) < 30:
            errors.append("PROMPT_TOO_SHORT: Prompt mô tả cảnh quá ngắn hoặc để trống.")

        p_lower = prompt.lower()
        if "16:9" not in p_lower and "aspect ratio" not in p_lower:
            errors.append("MISSING_ASPECT_RATIO: Prompt thiếu khai báo tỉ lệ 16:9 bắt buộc.")

        if shot.get("allow_camera_motion") is not True:
            if "locked-off" not in p_lower and "static" not in p_lower and "tripod" not in p_lower:
                errors.append("UNLOCKED_CAMERA: Thiếu quy tắc khóa máy tĩnh 'locked-off static tripod'.")

        # Kiểm tra ảnh tham chiếu đầu vào + độ sạch chữ
        refs = list(shot.get("reference_images") or [])
        ff_path = shot.get("first_frame_path")
        if ff_path and str(ff_path) not in [str(r) for r in refs]:
            refs.insert(0, str(ff_path))

        for r in refs:
            if not r:
                continue
            p_r = Path(r)
            if not p_r.exists():
                errors.append(f"MISSING_REF_FILE: File ảnh tham chiếu không tồn tại: {r}")
            elif p_r.stat().st_size < 1024:
                errors.append(f"CORRUPTED_REF_FILE: File ảnh tham chiếu rỗng hoặc hỏng: {r}")
            else:
                ok_img, img_errs, _ = KeyframeComposer.verify_keyframe_image(p_r)
                if not ok_img:
                    errors.extend([f"KEYFRAME_DEFECT ({p_r.name}): {ie}" for ie in img_errs])

        # Kiểm tra thứ tự & trục 180° với cảnh kề trước
        if prev_shot:
            curr_order = shot.get("order", 1)
            prev_order = prev_shot.get("order", 1)
            if curr_order != prev_order + 1:
                errors.append(f"NON_CONSECUTIVE_ORDER: Thứ tự cảnh không liên tục ({prev_order} -> {curr_order}).")

            # Khóa hướng nhìn cùng nhân vật trong cùng chương/bối cảnh
            if (
                shot.get("chapter_id") == prev_shot.get("chapter_id")
                and shot.get("location") == prev_shot.get("location")
                and shot.get("primary_character_id")
                and shot.get("primary_character_id") == prev_shot.get("primary_character_id")
                and shot.get("gaze")
                and prev_shot.get("gaze")
                and shot.get("gaze") != prev_shot.get("gaze")
            ):
                errors.append(
                    f"AXIS_JUMP_180: Nhân vật {shot.get('primary_character_id')} đổi hướng nhìn giữa 2 shot liên tiếp ({prev_shot.get('gaze')} -> {shot.get('gaze')})."
                )

        # Kiểm tra mâu thuẫn thoại vs im lặng
        has_dialogue = bool((shot.get("dialogue") or "").strip())
        if has_dialogue and any(c in p_lower for c in ("lips stay closed", "nobody speaks", "lips remain completely closed")):
            errors.append("DIALOGUE_SILENT_CONTRADICTION: Shot có lời thoại nhưng prompt lại khóa ngậm miệng.")
        if not has_dialogue and "says in english" in p_lower:
            errors.append("INVENTED_SPEECH: Shot không có thoại nhưng prompt lại ra lệnh nói.")

        # Khóa an toàn giải phẫu bàn tay (bỏ qua nếu tay được khóa rõ là nằm ngoài khung hình)
        hands_hidden = ("out of frame" in p_lower) or ("below frame" in p_lower)
        hand_keywords = ["hand", "finger", "phone", "badge", "hold", "touch", "pocket", "grip", "clipboard", "tablet", "throttle"]
        if any(w in p_lower for w in hand_keywords):
            hazardous_actions = ["tap screen", "type on", "flick finger", "intertwined fingers"]
            if any(h in p_lower for h in hazardous_actions):
                errors.append(
                    "HAZARDOUS_FINGER_ACTION: Prompt yêu cầu chuyển động ngón tay tinh vi (tap screen/type), cần chuyển sang tư thế cầm chắc chắn (firm grip)."
                )
            if not hands_hidden and "five finger" not in p_lower and "five distinct finger" not in p_lower and "hand anatomy" not in p_lower:
                errors.append(
                    "MISSING_HAND_ANATOMY_GUARD: Cảnh có tương tác bàn tay/đồ vật nhưng thiếu câu khóa giải phẫu 'five distinct fingers each, no extra fingers, no fused digits'."
                )

        return len(errors) == 0, errors

    @classmethod
    def validate_manifest_preflight(cls, manifest: Dict[str, Any]) -> Tuple[bool, List[Dict[str, Any]]]:
        """Tiền kiểm toàn bộ `shots_manifest` (từng shot + trục 180° toàn cảnh)."""
        findings: List[Dict[str, Any]] = []
        shots = manifest.get("shots", [])
        prev_shot = None
        seen_gaze_by_scene_char: Dict[Tuple[str, str], str] = {}

        for shot in shots:
            sid = shot.get("shot_id") or shot.get("id") or "?"
            ok, errs = cls.validate_shot_preflight(shot, prev_shot=prev_shot)
            for e in errs:
                findings.append({"shot_id": sid, "severity": "HARD", "error": e})

            ch = shot.get("chapter_id") or "CH01"
            cid = shot.get("primary_character_id")
            gaze = shot.get("gaze")
            if cid and gaze:
                key = (ch, cid)
                if key in seen_gaze_by_scene_char and seen_gaze_by_scene_char[key] != gaze:
                    findings.append({
                        "shot_id": sid,
                        "severity": "HARD",
                        "error": f"SCENE_AXIS_VIOLATION: {cid} trong {ch} đổi hướng nhìn ({seen_gaze_by_scene_char[key]} -> {gaze})."
                    })
                else:
                    seen_gaze_by_scene_char[key] = gaze

            prev_shot = shot

        return len(findings) == 0, findings

    # ----------------- 2. HẬU KIỂM KỸ THUẬT & QUANG HỌC (GATE 1-4) -----------------
    @staticmethod
    def probe_clip(clip_path: Path) -> Tuple[Optional[Dict[str, Any]], Optional[str]]:
        """Phân tích luồng video & audio qua ffprobe."""
        p = Path(clip_path)
        if not p.is_file() or p.stat().st_size == 0:
            return None, "File video không tồn tại hoặc có dung lượng 0 bytes."

        cmd = [
            "ffprobe", "-v", "error",
            "-show_entries", "format=duration,size,bit_rate",
            "-show_streams",
            "-print_format", "json",
            str(p)
        ]
        try:
            res = subprocess.run(cmd, capture_output=True, text=True, check=True)
            data = json.loads(res.stdout)
            v_stream = next((s for s in data.get("streams", []) if s.get("codec_type") == "video"), None)
            a_stream = next((s for s in data.get("streams", []) if s.get("codec_type") == "audio"), None)
            if not v_stream:
                return None, "Không tìm thấy luồng video (Video stream missing)."

            info: Dict[str, Any] = {
                "size_bytes": p.stat().st_size,
                "duration": float(data.get("format", {}).get("duration", 0)),
                "codec": v_stream.get("codec_name"),
                "width": int(v_stream.get("width", 0)),
                "height": int(v_stream.get("height", 0)),
                "fps": v_stream.get("r_frame_rate", "24/1"),
                "has_audio": a_stream is not None,
            }
            if a_stream:
                info["audio_codec"] = a_stream.get("codec_name")
                info["audio_sample_rate"] = int(a_stream.get("sample_rate", 0))
                info["audio_channels"] = int(a_stream.get("channels", 1))
            return info, None
        except Exception as e:
            return None, f"Lỗi ffprobe: {e}"

    @staticmethod
    def verify_full_decode(clip_path: Path) -> Tuple[bool, str]:
        """Gate 1: Giải mã 100% luồng video qua FFmpeg để phát hiện rách frame / corrupt stream."""
        cmd = ["ffmpeg", "-v", "error", "-i", str(clip_path), "-f", "null", "-"]
        res = subprocess.run(cmd, capture_output=True, text=True)
        if res.returncode == 0 and not res.stderr.strip():
            return True, "Giải mã luồng sạch sẽ, không có lỗi stream."
        return False, f"Lỗi giải mã: {res.stderr.strip()}"

    @staticmethod
    def analyze_temporal_motion_and_freeze(
        clip_path: Path,
        sample_fps: int = 4,
        has_dialogue: bool = False
    ) -> Dict[str, Any]:
        """Gate 2 & Gate 3 (Luma): Giải mã trực tiếp trên RAM ở 4fps đo chuyển động trượt, blackout, flicker & jump-cut."""
        cap = cv2.VideoCapture(str(clip_path))
        if not cap.isOpened():
            return {
                "is_frozen": True,
                "partial_freeze_speech": False,
                "has_flicker": False,
                "avg_motion_energy": 0.0,
                "max_motion_energy": 0.0,
                "max_luma_jump": 0.0,
                "error": "Không thể mở video để phân tích chuyển động.",
            }

        fps = cap.get(cv2.CAP_PROP_FPS) or 24.0
        if fps <= 0:
            fps = 24.0
        step = max(1, int(round(fps / float(max(1, sample_fps)))))

        diffs: List[float] = []
        luma_means: List[float] = []
        hand_roi_diffs: List[float] = []
        hist_corrs: List[float] = []
        black_frames = 0
        sampled_count = 0
        prev_gray = None
        prev_roi = None
        prev_hist = None
        frame_idx = 0

        try:
            while cap.grab():
                if frame_idx % step == 0:
                    ok, bgr = cap.retrieve()
                    if not ok or bgr is None:
                        frame_idx += 1
                        continue
                    sampled_count += 1
                    small_hsv = cv2.cvtColor(
                        cv2.resize(bgr, (320, 180), interpolation=cv2.INTER_AREA),
                        cv2.COLOR_BGR2HSV,
                    )
                    hist = cv2.calcHist([small_hsv], [0, 1], None, [24, 24], [0, 180, 0, 256])
                    cv2.normalize(hist, hist, 0, 1, cv2.NORM_MINMAX)
                    if prev_hist is not None:
                        corr = float(cv2.compareHist(prev_hist, hist, cv2.HISTCMP_CORREL))
                        hist_corrs.append(corr)
                    prev_hist = hist

                    gray = cv2.cvtColor(bgr, cv2.COLOR_BGR2GRAY)
                    h, w = gray.shape[:2]
                    mean_y = float(cv2.mean(gray)[0])
                    luma_means.append(mean_y)
                    if mean_y < 5.0:
                        black_frames += 1

                    roi = gray[int(h * 0.45) : int(h * 0.95), int(w * 0.15) : int(w * 0.85)]

                    if prev_gray is not None:
                        diffs.append(float(cv2.mean(cv2.absdiff(gray, prev_gray))[0]))
                    if prev_roi is not None and roi.shape == prev_roi.shape and roi.size > 0:
                        hand_roi_diffs.append(float(cv2.mean(cv2.absdiff(roi, prev_roi))[0]))
                    prev_gray = gray
                    prev_roi = roi
                frame_idx += 1
        finally:
            cap.release()

        if sampled_count < 2:
            return {
                "is_frozen": True,
                "partial_freeze_speech": False,
                "has_flicker": False,
                "avg_motion_energy": 0.0,
                "max_motion_energy": 0.0,
                "max_luma_jump": 0.0,
                "error": "Quá ít khung hình để phân tích chuyển động.",
            }

        avg_energy = sum(diffs) / len(diffs) if diffs else 0.0
        max_energy = max(diffs) if diffs else 0.0
        luma_jumps = [abs(luma_means[i] - luma_means[i - 1]) for i in range(1, len(luma_means))]
        max_luma_jump = max(luma_jumps) if luma_jumps else 0.0

        early_idx = int(1.25 * sample_fps)
        early_corrs = hist_corrs[:early_idx]
        stable_corrs = hist_corrs[early_idx:] if len(hist_corrs) > early_idx else hist_corrs
        min_early_corr = min(early_corrs) if early_corrs else 1.0
        min_stable_corr = min(stable_corrs) if stable_corrs else min_early_corr
        early_transition_cut_s = 1.25 if (min_early_corr < 0.72 and min_stable_corr >= 0.55) else None

        # Kiểm tra đơ trong cửa sổ thoại (0.5s -> 4.5s) nếu clip có thoại
        partial_freeze = False
        if has_dialogue and len(diffs) >= int(4.5 * sample_fps):
            start_i = int(0.5 * sample_fps)
            end_i = min(len(diffs), int(4.5 * sample_fps))
            speech_window = diffs[start_i:end_i]
            if speech_window and (sum(speech_window) / len(speech_window)) < 0.22:
                partial_freeze = True

        # Phát hiện biến động đột biến vùng tay ở nửa sau clip (giật tay / biến dạng cục bộ)
        hand_spike_time_s = None
        if len(hand_roi_diffs) >= 8:
            med_roi = float(np.median(hand_roi_diffs))
            for idx_r, val_r in enumerate(hand_roi_diffs):
                t_sec = (idx_r + 1) / float(sample_fps)
                if t_sec >= 3.5 and val_r > max(14.0, med_roi * 4.5):
                    hand_spike_time_s = round(t_sec, 2)
                    break

        return {
            "total_frames_sampled": sampled_count,
            "sample_fps": sample_fps,
            "avg_motion_energy": round(avg_energy, 3),
            "max_motion_energy": round(max_energy, 3),
            "max_luma_jump": round(max_luma_jump, 2),
            "min_hist_corr": round(min_stable_corr, 3),
            "min_early_hist_corr": round(min_early_corr, 3),
            "early_transition_cut_s": early_transition_cut_s,
            "is_frozen": avg_energy < 0.4,
            "partial_freeze_speech": partial_freeze,
            "has_flicker": max_luma_jump > 60.0,
            "has_internal_cut": False,
            "has_black_out": black_frames > sampled_count * 0.3,
            "black_frames_count": black_frames,
            "hand_spike_time_s": hand_spike_time_s,
        }

    @staticmethod
    def analyze_spatial_continuity(
        clip_path: Path,
        has_dialogue: bool,
        speech_start_s: Optional[float] = None,
        speech_end_s: Optional[float] = None,
        min_duration_s: float = 3.0,
        is_walking_shot: bool = False,
        allow_camera_motion: bool = False,
    ) -> Dict[str, Any]:
        """Kiểm tra tính liên tục bố cục không gian 3x3 HSV và tìm đoạn ổn định sạch (auto-settle trim)."""
        cap = cv2.VideoCapture(str(clip_path))
        fps = cap.get(cv2.CAP_PROP_FPS) or 24.0
        step = max(1, int(round(fps / 4.0)))
        hs: List[List[np.ndarray]] = []
        ts: List[float] = []
        idx = 0
        while cap.grab():
            if idx % step == 0:
                ok, frame = cap.retrieve()
                if not ok or frame is None:
                    idx += 1
                    continue
                small = cv2.cvtColor(cv2.resize(frame, (160, 90)), cv2.COLOR_BGR2HSV)
                cells: List[np.ndarray] = []
                for ry in range(3):
                    for rx in range(3):
                        patch = small[ry * 30 : (ry + 1) * 30, rx * 53 : (rx + 1) * 53]
                        h = cv2.calcHist([patch], [0, 1], None, [12, 12], [0, 180, 0, 256])
                        cv2.normalize(h, h, 0, 1, cv2.NORM_MINMAX)
                        cells.append(h)
                hs.append(cells)
                ts.append(round(idx / fps, 2))
            idx += 1
        cap.release()

        if len(hs) < 2:
            return {
                "has_internal_cut": False,
                "span_grid_corr": 1.0,
                "settled_in_s": None,
                "settled_out_s": None,
            }

        def _gcorr(i: int, j: int) -> float:
            return float(np.mean([cv2.compareHist(a, b, cv2.HISTCMP_CORREL) for a, b in zip(hs[i], hs[j])]))

        adj = [_gcorr(k, k + 1) for k in range(len(hs) - 1)]

        if has_dialogue:
            pre_speech_cut_s: Optional[float] = None
            speech_bound = (speech_start_s or 0.0) + 0.10
            for k, val in enumerate(adj):
                if val < 0.72 and ts[k + 1] <= speech_bound:
                    pre_speech_cut_s = round(ts[k + 1] + 0.15, 2)

            t_ref = max(1.25, (speech_start_s or 0.8) + 0.25, pre_speech_cut_s or 0.0)
            t_end = max(t_ref + 0.5, min(ts[-1] - 0.35, speech_end_s or (ts[-1] - 0.8)))
            t_mid = 0.5 * (t_ref + t_end)
            ir = min(range(len(ts)), key=lambda k: abs(ts[k] - t_ref))
            im = min(range(len(ts)), key=lambda k: abs(ts[k] - t_mid))
            ie = min(range(len(ts)), key=lambda k: abs(ts[k] - t_end))

            span_corr = min(_gcorr(ir, im), _gcorr(ir, ie))
            min_speech_adj = min(adj[ir:ie]) if ie > ir else 1.0
            if allow_camera_motion:
                # Khi cho phép dolly/pan mượt trong thoại, chỉ bắt lỗi cắt cảnh đột ngột giữa 2 mẫu kề nhau
                has_internal_cut = min_speech_adj < 0.58
            else:
                has_internal_cut = (span_corr < 0.48) or (min_speech_adj < 0.62)
            return {
                "has_internal_cut": has_internal_cut,
                "span_grid_corr": round(span_corr, 3),
                "min_speech_adj_corr": round(min_speech_adj, 3),
                "settled_in_s": pre_speech_cut_s,
                "settled_out_s": None,
            }

        dynamic_camera_ok = bool(is_walking_shot or allow_camera_motion)
        cuts = [0] + [k + 1 for k, val in enumerate(adj) if val < 0.70] + [len(hs)]
        best_a, best_b, best_dur = 0, len(hs) - 1, -1.0
        for j in range(len(cuts) - 1):
            a = cuts[j]
            b = cuts[j + 1] - 1
            if b <= a:
                continue
            ref_b = max(a, b - 1)
            if not dynamic_camera_ok and _gcorr(a, ref_b) < 0.60:
                for k in range(a + 1, ref_b):
                    if _gcorr(k, ref_b) >= 0.65:
                        a = min(ref_b, k + 1)
                        break
            seg_dur = ts[b] - ts[a]
            if seg_dur > best_dur:
                best_a, best_b, best_dur = a, b, seg_dur

        if best_dur < 0:
            best_a, best_b = 0, len(hs) - 1
            best_dur = ts[best_b] - ts[best_a]

        req_seg_s = max(min_duration_s, 4.5 if ts[-1] >= 7.5 else min_duration_s)
        end_corr = _gcorr(best_a, max(best_a, best_b - 1))
        has_internal_cut = (best_dur < req_seg_s) or (not dynamic_camera_ok and end_corr < 0.48)
        return {
            "has_internal_cut": has_internal_cut,
            "span_grid_corr": round(end_corr, 3),
            "clean_seg_duration_s": round(best_dur, 2),
            "settled_in_s": ts[best_a],
            "settled_out_s": ts[best_b],
        }

    @staticmethod
    def analyze_optical_flow(clip_path: Path, top_frac: float = 0.6) -> Dict[str, Any]:
        """Gate 3 (Optical Flow + PhaseCorrelate): Đo dịch chuyển phông nền tĩnh (2 góc trên) và biên độ đầu."""
        cap = cv2.VideoCapture(str(clip_path))
        ok, first = cap.read()
        if not ok or first is None:
            cap.release()
            return {"valid": False, "camera_drift_px": 0.0, "nod_range_pct": 0.0, "shake_range_pct": 0.0}

        h, w = first.shape[:2]
        fps = cap.get(cv2.CAP_PROP_FPS) or 24.0
        flow_step = max(1, int(round(fps / 8.0))) if fps >= 14.0 else 1
        g0 = cv2.cvtColor(first, cv2.COLOR_BGR2GRAY)
        scale_half = w >= 960
        flow_w = max(1, w // 2) if scale_half else w
        flow_h = max(1, h // 2) if scale_half else h
        min_dist = 4 if scale_half else 6
        lk_win = (13, 13) if scale_half else (19, 19)
        mag_thresh = 0.20 if scale_half else 0.35

        g0_flow = cv2.resize(g0, (flow_w, flow_h), interpolation=cv2.INTER_AREA) if scale_half else g0
        pts = cv2.goodFeaturesToTrack(g0_flow[: int(flow_h * top_frac)], 140, 0.01, min_dist)
        if pts is None or len(pts) < 8:
            cap.release()
            return {"valid": True, "camera_drift_px": 0.0, "nod_range_pct": 0.0, "shake_range_pct": 0.0, "frames": 1}

        cw = max(64, int(w * 0.22))
        ch = max(48, int(h * 0.22))
        corner_pairs: List[Tuple[np.ndarray, np.ndarray]] = [
            (g0[0:ch, 0:cw].copy(), g0[0:ch, w - cw : w].copy())
        ]

        cy = [0.0]
        cx = [0.0]
        prev = g0_flow
        p0 = pts
        f_idx = 1

        while cap.grab():
            if f_idx % flow_step != 0:
                f_idx += 1
                continue
            ok, frame = cap.retrieve()
            f_idx += 1
            if not ok or frame is None:
                continue
            g = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            corner_pairs.append((g[0:ch, 0:cw].copy(), g[0:ch, w - cw : w].copy()))
            g_flow = cv2.resize(g, (flow_w, flow_h), interpolation=cv2.INTER_AREA) if scale_half else g

            p1, st, _ = cv2.calcOpticalFlowPyrLK(prev, g_flow, p0, None, winSize=lk_win, maxLevel=2)
            if p1 is None or st is None:
                break
            good = st.ravel() == 1
            if good.sum() < 8:
                p0 = cv2.goodFeaturesToTrack(g_flow[: int(flow_h * top_frac)], 140, 0.01, min_dist)
                prev = g_flow
                if p0 is None:
                    break
                cy.append(cy[-1])
                cx.append(cx[-1])
                continue

            d = (p1[good] - p0[good]).reshape(-1, 2)
            mag = np.hypot(d[:, 0], d[:, 1])
            mv = mag > mag_thresh
            if mv.sum() >= 8:
                cy.append(cy[-1] + float(np.median(d[mv, 1])))
                cx.append(cx[-1] + float(np.median(d[mv, 0])))
            else:
                cy.append(cy[-1])
                cx.append(cx[-1])

            prev = g_flow
            p0 = (
                p1[good].reshape(-1, 1, 2)
                if good.sum() > 28
                else cv2.goodFeaturesToTrack(g_flow[: int(flow_h * top_frac)], 140, 0.01, min_dist)
            )
            if p0 is None:
                break

        cap.release()
        cy_arr = np.array(cy)
        cx_arr = np.array(cx)
        k = min(48 // flow_step, max(3, len(cy_arr) // 2))

        def _hp(arr: np.ndarray) -> np.ndarray:
            if len(arr) <= k:
                return arr - np.mean(arr)
            m = np.convolve(arr, np.ones(k) / k, mode="same")
            return arr - m

        ry = float(np.ptp(_hp(cy_arr)) / max(1, flow_h) * 100.0)
        rx = float(np.ptp(_hp(cx_arr)) / max(1, flow_w) * 100.0)

        # Đo trôi camera thật bằng phaseCorrelate trên 2 góc nền trên cùng (tránh vai/mặt diễn viên)
        drift_px = 0.0
        n_f = len(corner_pairs)
        if n_f >= 4:
            hann = cv2.createHanningWindow((cw, ch), cv2.CV_32F)
            ref_idx = min(n_f - 1, max(1, 6 // flow_step))
            tl0_u8, tr0_u8 = corner_pairs[ref_idx]
            tl0 = tl0_u8.astype(np.float32)
            tr0 = tr0_u8.astype(np.float32)
            tl_shifts = []
            tr_shifts = []
            for tidx in sorted({n_f // 2, max(0, n_f - max(2, 6 // flow_step))}):
                tl_t_u8, tr_t_u8 = corner_pairs[tidx]
                s_tl, r_tl = cv2.phaseCorrelate(tl0, tl_t_u8.astype(np.float32), hann)
                s_tr, r_tr = cv2.phaseCorrelate(tr0, tr_t_u8.astype(np.float32), hann)
                if r_tl > 0.15:
                    tl_shifts.append(float(np.hypot(s_tl[0], s_tl[1])))
                if r_tr > 0.15:
                    tr_shifts.append(float(np.hypot(s_tr[0], s_tr[1])))
            if tl_shifts and tr_shifts:
                drift_px = min(max(tl_shifts), max(tr_shifts))

        return {
            "valid": True,
            "frames": len(cy_arr),
            "camera_drift_px": round(drift_px, 2),
            "nod_range_pct": round(ry, 2),
            "shake_range_pct": round(rx, 2),
        }

    @staticmethod
    def generate_qc_strip(
        clip_path: Path,
        output_path: Path,
        timestamps: Optional[List[float]] = None,
        label_prefix: str = ""
    ) -> Optional[Path]:
        """Xuất dải 4 khung hình kiểm chứng (0.5s, mid, end, tail) trên RAM để Gemini Agent duyệt thị giác."""
        clip_path = Path(clip_path)
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        ts_list = timestamps or [0.5, 2.5, 5.0, 7.5]

        thumbs: List[Tuple[float, Image.Image]] = []
        cap = cv2.VideoCapture(str(clip_path))
        if cap.isOpened():
            try:
                fps = cap.get(cv2.CAP_PROP_FPS) or 24.0
                if ts_list and max(ts_list) <= 20.0 and ts_list == sorted(ts_list):
                    targets = [(float(ts), max(0, int(round(max(0.0, float(ts)) * fps)))) for ts in ts_list]
                    t_ptr = 0
                    f_idx = 0
                    last_frame = None
                    while t_ptr < len(targets) and cap.grab():
                        if f_idx >= targets[t_ptr][1]:
                            ok, frame = cap.retrieve()
                            if ok and frame is not None:
                                last_frame = frame
                                rgb = cv2.cvtColor(
                                    cv2.resize(frame, (426, 240), interpolation=cv2.INTER_AREA),
                                    cv2.COLOR_BGR2RGB,
                                )
                                while t_ptr < len(targets) and f_idx >= targets[t_ptr][1]:
                                    thumbs.append((targets[t_ptr][0], Image.fromarray(rgb)))
                                    t_ptr += 1
                        f_idx += 1
                    # If clip slightly shorter than tail ts, clamp last valid frame for remaining tail markers
                    if t_ptr < len(targets) and last_frame is not None:
                        rgb = cv2.cvtColor(
                            cv2.resize(last_frame, (426, 240), interpolation=cv2.INTER_AREA),
                            cv2.COLOR_BGR2RGB,
                        )
                        while t_ptr < len(targets):
                            thumbs.append((targets[t_ptr][0], Image.fromarray(rgb)))
                            t_ptr += 1
                else:
                    for ts in ts_list:
                        cap.set(cv2.CAP_PROP_POS_MSEC, max(0.0, float(ts)) * 1000.0)
                        ok, frame = cap.read()
                        if ok and frame is not None:
                            rgb = cv2.cvtColor(
                                cv2.resize(frame, (426, 240), interpolation=cv2.INTER_AREA),
                                cv2.COLOR_BGR2RGB,
                            )
                            thumbs.append((ts, Image.fromarray(rgb)))
            finally:
                cap.release()

        if not thumbs:
            with tempfile.TemporaryDirectory() as tmpdir:
                tmp = Path(tmpdir)
                for idx, ts in enumerate(ts_list):
                    fp = tmp / f"t_{idx}.png"
                    subprocess.run(
                        ["ffmpeg", "-y", "-ss", str(max(0.0, ts)), "-i", str(clip_path), "-vframes", "1", str(fp)],
                        stdout=subprocess.DEVNULL,
                        stderr=subprocess.DEVNULL,
                    )
                    if fp.exists() and fp.stat().st_size > 0:
                        with Image.open(fp) as im:
                            thumbs.append((ts, im.convert("RGB").resize((426, 240), Image.Resampling.LANCZOS)))

        if not thumbs:
            return None

        strip = Image.new("RGB", (426 * len(thumbs), 270), (16, 20, 28))
        draw = ImageDraw.Draw(strip)
        for idx, (ts, im) in enumerate(thumbs):
            x = idx * 426
            strip.paste(im, (x, 0))
            draw.rectangle([x, 240, x + 426, 270], fill=(28, 34, 46))
            draw.text((x + 10, 248), f"{label_prefix} t={ts:.2f}s".strip(), fill=(235, 240, 245))
        strip.save(output_path, quality=90)
        return output_path

    @classmethod
    def _detect_face_rects(cls, frame_bgr: np.ndarray) -> List[Tuple[int, int, int, int]]:
        """Dò khung mặt qua CascadeClassifier (nếu có) hoặc fallback phân vùng da mặt YCrCb trên OpenCV 5+."""
        cascade_cls = getattr(cv2, "CascadeClassifier", None)
        if cascade_cls is not None:
            try:
                haar_dir = getattr(getattr(cv2, "data", None), "haarcascades", "") or ""
                cascade = cascade_cls(haar_dir + "haarcascade_frontalface_default.xml")
                if not hasattr(cascade, "empty") or not cascade.empty():
                    gray = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2GRAY)
                    rects = cascade.detectMultiScale(gray, scaleFactor=1.1, minNeighbors=4, minSize=(30, 30))
                    if rects is not None and len(rects) > 0:
                        return [(int(x), int(y), int(bw), int(bh)) for (x, y, bw, bh) in rects]
                    return []
            except Exception:
                pass

        fh, fw = frame_bgr.shape[:2]
        ycrcb = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2YCrCb)
        mask = cv2.inRange(
            ycrcb,
            np.array([25, 142, 77], dtype=np.uint8),
            np.array([245, 177, 118], dtype=np.uint8),
        )
        mask[int(fh * 0.78) :, :] = 0
        kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (7, 7))
        mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, kernel)
        mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel)
        contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        min_area = max(900.0, fh * fw * 0.004)
        max_area = fh * fw * 0.35
        detected: List[Tuple[int, int, int, int]] = []
        for cnt in contours:
            x, y, bw, bh = cv2.boundingRect(cnt)
            area = float(bw * bh)
            aspect = bw / max(1.0, float(bh))
            if min_area <= area <= max_area and 0.50 <= aspect <= 1.55 and bw >= 30 and bh >= 30:
                detected.append((int(x), int(y), int(bw), int(bh)))
        return detected

    @classmethod
    def analyze_actor_visual_consistency(
        cls,
        clip_path: Path,
        reference_image_path: Optional[Path] = None,
    ) -> Dict[str, Any]:
        """Gate 4B: Lấy mẫu tối đa 3 khung hình, dò mặt Haar Cascade và đo độ tương đồng HSV + LAB so với ảnh gốc."""
        cap = cv2.VideoCapture(str(clip_path))
        total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0)
        sampled_bgr: List[np.ndarray] = []

        if total_frames >= 3:
            indices = sorted({
                min(total_frames - 1, max(0, int(total_frames * 0.10))),
                min(total_frames - 1, int(total_frames * 0.50)),
                min(total_frames - 1, max(0, int(total_frames * 0.85))),
            })[:3]
            for f_idx in indices:
                cap.set(cv2.CAP_PROP_POS_FRAMES, f_idx)
                ok, frm = cap.read()
                if ok and frm is not None:
                    sampled_bgr.append(frm)

        if not sampled_bgr:
            cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
            all_read: List[np.ndarray] = []
            while True:
                ok, frm = cap.read()
                if not ok or frm is None:
                    break
                all_read.append(frm)
            if len(all_read) <= 3:
                sampled_bgr = all_read
            else:
                sampled_bgr = [
                    all_read[int(len(all_read) * 0.10)],
                    all_read[int(len(all_read) * 0.50)],
                    all_read[int(len(all_read) * 0.85)],
                ]
        cap.release()

        if not sampled_bgr:
            return {
                "frames_sampled": 0,
                "face_boxes": [],
                "max_faces_detected": 0,
                "hsv_hist_corr": None,
                "lab_similarity": None,
                "identity_similarity": None,
            }

        per_frame_boxes: List[List[Dict[str, float]]] = []
        for frm in sampled_bgr:
            fh, fw = frm.shape[:2]
            boxes: List[Dict[str, float]] = []
            rects = cls._detect_face_rects(frm)
            for (x, y, bw, bh) in rects:
                boxes.append({
                    "x_norm": round(float(np.clip(x / max(1, fw), 0.0, 1.0)), 4),
                    "y_norm": round(float(np.clip(y / max(1, fh), 0.0, 1.0)), 4),
                    "w_norm": round(float(np.clip(bw / max(1, fw), 0.0, 1.0)), 4),
                    "h_norm": round(float(np.clip(bh / max(1, fh), 0.0, 1.0)), 4),
                })
            per_frame_boxes.append(boxes)

        max_faces = max((len(b) for b in per_frame_boxes), default=0)
        if per_frame_boxes[0]:
            primary_boxes = per_frame_boxes[0]
        elif len(per_frame_boxes) >= 2 and per_frame_boxes[1]:
            primary_boxes = per_frame_boxes[1]
        else:
            primary_boxes = []

        hsv_corr_val: Optional[float] = None
        lab_sim_val: Optional[float] = None
        identity_sim_val: Optional[float] = None

        if reference_image_path is not None and Path(reference_image_path).is_file():
            try:
                with Image.open(reference_image_path) as pil_ref:
                    ref_rgb = np.array(pil_ref.convert("RGB"))
                ref_bgr = cv2.cvtColor(ref_rgb, cv2.COLOR_RGB2BGR)

                ref_hsv = cv2.cvtColor(cv2.resize(ref_bgr, (160, 90)), cv2.COLOR_BGR2HSV)
                ref_hist = cv2.calcHist([ref_hsv], [0, 1], None, [12, 12], [0, 180, 0, 256])
                ref_hist = cv2.GaussianBlur(ref_hist, (3, 3), 0.8)
                cv2.normalize(ref_hist, ref_hist, 0, 1, cv2.NORM_MINMAX)

                ref_lab = cv2.cvtColor(cv2.resize(ref_bgr, (64, 36)), cv2.COLOR_BGR2LAB).astype(np.float32)

                hsv_corrs: List[float] = []
                lab_sims: List[float] = []
                for frm in sampled_bgr:
                    frm_hsv = cv2.cvtColor(cv2.resize(frm, (160, 90)), cv2.COLOR_BGR2HSV)
                    frm_hist = cv2.calcHist([frm_hsv], [0, 1], None, [12, 12], [0, 180, 0, 256])
                    frm_hist = cv2.GaussianBlur(frm_hist, (3, 3), 0.8)
                    cv2.normalize(frm_hist, frm_hist, 0, 1, cv2.NORM_MINMAX)
                    corr = float(np.clip(cv2.compareHist(ref_hist, frm_hist, cv2.HISTCMP_CORREL), -1.0, 1.0))
                    hsv_corrs.append(corr)

                    frm_lab = cv2.cvtColor(cv2.resize(frm, (64, 36)), cv2.COLOR_BGR2LAB).astype(np.float32)
                    mean_de = float(np.mean(np.linalg.norm(ref_lab - frm_lab, axis=2)))
                    lab_sims.append(float(np.clip(1.0 - (mean_de / 65.0), -1.0, 1.0)))

                hsv_corr_val = round(float(np.mean(hsv_corrs)), 4)
                lab_sim_val = round(float(np.mean(lab_sims)), 4)
                identity_sim_val = round(
                    float(np.clip(0.55 * hsv_corr_val + 0.45 * lab_sim_val, -1.0, 1.0)),
                    4,
                )
            except Exception:
                pass

        return {
            "frames_sampled": len(sampled_bgr),
            "face_boxes": primary_boxes,
            "max_faces_detected": max_faces,
            "hsv_hist_corr": hsv_corr_val,
            "lab_similarity": lab_sim_val,
            "identity_similarity": identity_sim_val,
        }

    @classmethod
    def analyze_audio_signal_and_lipsync(
        cls,
        clip_path: Path,
        has_dialogue: bool,
        speech_start_s: Optional[float] = None,
        speech_end_s: Optional[float] = None,
    ) -> Dict[str, Any]:
        """Gate 5B: Giải mã PCM 16kHz đo biên độ/clipping và đo chuyển động khẩu hình vùng mặt trung tâm."""
        res = subprocess.run(
            [
                "ffmpeg", "-v", "error", "-i", str(clip_path),
                "-vn", "-ac", "1", "-ar", "16000", "-f", "s16le", "-",
            ],
            capture_output=True,
        )
        raw_bytes = res.stdout[: (len(res.stdout) // 2) * 2] if res.stdout else b""
        if len(raw_bytes) >= 2:
            samples = np.frombuffer(raw_bytes, dtype=np.int16).astype(np.float32) / 32768.0
            rms = float(np.sqrt(np.mean(np.square(samples))))
            peak = float(np.max(np.abs(samples)))
            rms_dbfs = round(float(20.0 * np.log10(max(rms, 1e-5))), 2)
            peak_dbfs = round(float(20.0 * np.log10(max(peak, 1e-5))), 2)
            clipping_ratio = round(float(np.mean(np.abs(samples) >= 0.995)), 5)
        else:
            rms_dbfs = -100.0
            peak_dbfs = -100.0
            clipping_ratio = 0.0

        mouth_motion_energy: Optional[float] = None
        if has_dialogue:
            win_start = float(speech_start_s if speech_start_s is not None else 0.5)
            win_end = float(speech_end_s if speech_end_s is not None else 3.0)
            if win_end <= win_start + 0.15:
                win_end = win_start + 0.5

            cap = cv2.VideoCapture(str(clip_path))
            fps = cap.get(cv2.CAP_PROP_FPS) or 24.0
            step = max(1, int(round(fps / 12.0)))
            roi_diffs: List[float] = []
            prev_roi: Optional[np.ndarray] = None
            idx = 0
            while True:
                ok, frm = cap.read()
                if not ok or frm is None:
                    break
                t_s = idx / fps
                if t_s > win_end + (1.0 / fps):
                    break
                if t_s >= max(0.0, win_start) and (idx % step == 0):
                    gray = cv2.cvtColor(frm, cv2.COLOR_BGR2GRAY)
                    fh, fw = gray.shape[:2]
                    roi = gray[
                        int(fh * 0.20) : int(fh * 0.65),
                        int(fw * 0.25) : int(fw * 0.75),
                    ].astype(np.float32)
                    if prev_roi is not None and prev_roi.shape == roi.shape:
                        roi_diffs.append(float(np.mean(np.abs(roi - prev_roi))))
                    prev_roi = roi
                idx += 1
            cap.release()
            mouth_motion_energy = round(float(np.mean(roi_diffs)), 4) if roi_diffs else 0.0

        return {
            "rms_dbfs": rms_dbfs,
            "peak_dbfs": peak_dbfs,
            "clipping_ratio": clipping_ratio,
            "mouth_motion_energy": mouth_motion_energy,
        }

    # ----------------- 3. HẬU KIỂM LỜI THOẠI NATIVE (GATE 5: ASR SPEECH QC) -----------------
    @staticmethod
    def _int_to_words(n: int) -> str:
        ones = [
            "zero", "one", "two", "three", "four", "five", "six", "seven", "eight", "nine",
            "ten", "eleven", "twelve", "thirteen", "fourteen", "fifteen", "sixteen", "seventeen", "eighteen", "nineteen",
        ]
        tens = ["", "", "twenty", "thirty", "forty", "fifty", "sixty", "seventy", "eighty", "ninety"]
        if n < 20:
            return ones[n]
        if n < 100:
            return tens[n // 10] + ("" if n % 10 == 0 else " " + ones[n % 10])
        if n < 1000:
            rem = n % 100
            return ones[n // 100] + " hundred" + ("" if rem == 0 else " " + FilmQCEngine._int_to_words(rem))
        if n < 10000:
            hi, lo = n // 100, n % 100
            if lo == 0 and n % 1000 == 0:
                return ones[n // 1000] + " thousand"
            return FilmQCEngine._int_to_words(hi) + " " + (FilmQCEngine._int_to_words(lo) if lo else "hundred")
        if n < 1000000:
            hi, lo = n // 1000, n % 1000
            return FilmQCEngine._int_to_words(hi) + " thousand" + ("" if lo == 0 else " " + FilmQCEngine._int_to_words(lo))
        return str(n)

    @classmethod
    def _normalize_asr_text(cls, text: str) -> str:
        """Chuẩn hóa chữ thường, từ tương đương Anh-Mỹ, từ ghép và số nguyên sang chữ tiếng Anh."""
        s = (text or "").lower()
        s = re.sub(r"(\d),(\d)", r"\1\2", s)
        s = re.sub(r"([a-z])(\d)", r"\1 \2", s)
        s = re.sub(r"(\d)([a-z])", r"\1 \2", s)
        s = re.sub(r"[^\w\s]", " ", s)
        replacements = {
            r"\bmum\b": "mom",
            r"\bniner\b": "nine",
            r"\bhundred and\b": "hundred",
            r"\bbe con(?:nective|active)\b": "beacon active",
            r"\bwalkaround\b": "walk around",
            r"\bpreflight\b": "pre flight",
            r"\boccrew\b": "occ crew",
            r"\bstanddown\b": "stand down",
            r"\bpiloting\b": "pilot in",
            r"\bmaam\b": "ma am",
            r"\bim\b": "i m",
            r"\bill\b": "i ll",
            r"\byoure\b": "you re",
            r"\bdont\b": "don t",
        }
        for pat, rep in replacements.items():
            s = re.sub(pat, rep, s)
        s = re.sub(r"\b(\d{1,6})\b", lambda m: cls._int_to_words(int(m.group(1))), s)
        return " ".join(s.split())

    @classmethod
    def _to_digit_stream(cls, text: str) -> str:
        """Chuyển các chữ số & số đọc từng chữ số (seven-eight-one-niner-four / 781-904) về chuỗi từng chữ số."""
        s = (text or "").lower()
        s = re.sub(r"(\d),(\d)", r"\1\2", s)
        s = re.sub(r"[^\w\s]", " ", s)
        digit_words = {
            "zero": "0", "oh": "0", "one": "1", "two": "2", "three": "3", "four": "4",
            "five": "5", "six": "6", "seven": "7", "eight": "8", "nine": "9", "niner": "9",
        }
        out_toks: List[str] = []
        for tok in s.split():
            if tok in digit_words:
                out_toks.append(digit_words[tok])
            elif tok.isdigit():
                out_toks.extend(list(tok))
            else:
                out_toks.append(tok)
        return " ".join(out_toks)

    @classmethod
    def verify_native_dialogue(
        cls,
        clip_path: Path,
        expected_dialogue: str,
        max_wer: float = 0.15
    ) -> Dict[str, Any]:
        """Dùng Faster-Whisper ASR đo WER <= 15%, chặn lỗi đọc nhầm chỉ dẫn sân khấu & trích word timestamps."""
        model = cls.get_whisper_model()
        if not model:
            return {
                "passed": False,
                "error": "Faster-Whisper unavailable on this machine.",
                "wer": 1.0,
                "pauses": [],
                "words": [],
            }

        try:
            with cls._whisper_transcribe_lock:
                segments_gen, _ = model.transcribe(
                    str(clip_path),
                    beam_size=5,
                    word_timestamps=True,
                    language="en"
                )
                segments = list(segments_gen)

            all_words: List[Dict[str, Any]] = []
            transcript_parts: List[str] = []
            pauses: List[Dict[str, Any]] = []
            prev_word_end = 0.0

            for seg in segments:
                transcript_parts.append(seg.text.strip())
                if seg.words:
                    for w in seg.words:
                        clean_w = w.word.strip()
                        all_words.append({
                            "word": clean_w,
                            "start": round(w.start, 3),
                            "end": round(w.end, 3),
                            "probability": round(w.probability, 3)
                        })
                        if prev_word_end > 0.0:
                            gap = w.start - prev_word_end
                            if gap > 1.0:
                                pauses.append({
                                    "start": round(prev_word_end, 3),
                                    "end": round(w.start, 3),
                                    "gap_duration": round(gap, 3)
                                })
                        prev_word_end = w.end

            full_transcript = " ".join(transcript_parts).strip()

            import jiwer
            ref = cls._normalize_asr_text(expected_dialogue)
            hyp = cls._normalize_asr_text(full_transcript)
            if not ref:
                wer = 0.0
            elif not hyp:
                wer = 1.0
            else:
                word_wer = float(jiwer.wer(ref, hyp))
                d_ref = cls._to_digit_stream(expected_dialogue)
                d_hyp = cls._to_digit_stream(full_transcript)
                digit_wer = float(jiwer.wer(d_ref, d_hyp)) if (d_ref and d_hyp) else word_wer
                wer = round(min(word_wer, digit_wer), 3)

                if wer > max_wer and pauses:
                    for p in pauses:
                        if p["gap_duration"] < 1.8:
                            continue
                        prefix_words = [w for w in all_words if w["end"] <= p["start"] + 0.05]
                        if len(prefix_words) < 4:
                            continue
                        prefix_text = " ".join(
                            (w.get("word") or w.get("text") or "").strip()
                            for w in prefix_words
                            if (w.get("word") or w.get("text") or "").strip()
                        )
                        p_hyp = cls._normalize_asr_text(prefix_text)
                        if not p_hyp:
                            continue
                        p_word_wer = float(jiwer.wer(ref, p_hyp))
                        pd_hyp = cls._to_digit_stream(prefix_text)
                        p_digit_wer = float(jiwer.wer(d_ref, pd_hyp)) if (d_ref and pd_hyp) else p_word_wer
                        p_wer = round(min(p_word_wer, p_digit_wer), 3)
                        if p_wer <= max_wer:
                            wer = p_wer
                            all_words = prefix_words
                            full_transcript = prefix_text
                            hyp = p_hyp
                            break

            # Kiểm tra lỗi AI đọc thành tiếng chỉ dẫn sân khấu ("brief pause", "short pause", ...)
            stage_leak_phrases = ("brief pause", "short pause", "point three", "natural breath")
            spoken_stage_direction = any(ph in hyp and ph not in ref for ph in stage_leak_phrases)

            speech_start = all_words[0]["start"] if all_words else None
            speech_end = all_words[-1]["end"] if all_words else None

            return {
                "passed": (wer <= max_wer) and (not spoken_stage_direction),
                "spoken_stage_direction": spoken_stage_direction,
                "transcript": full_transcript,
                "expected": expected_dialogue,
                "wer": wer,
                "word_count": len(all_words),
                "words": all_words,
                "speech_start_s": speech_start,
                "speech_end_s": speech_end,
                "pauses": pauses,
                "has_long_pause": len(pauses) > 0,
            }
        except Exception as e:
            return {
                "passed": False,
                "error": f"Lỗi Faster-Whisper ASR: {e}",
                "wer": 1.0,
                "pauses": [],
                "words": [],
            }

    # ----------------- 4. TỔNG HỢP & PHÁN QUYẾT QC 5 CỔNG (VERDICT) -----------------
    @classmethod
    def evaluate_generated_clip(
        cls,
        clip_path: Path,
        shot_spec: Dict[str, Any],
        min_duration_s: float = 3.0,
        strip_output_path: Optional[Path] = None
    ) -> Dict[str, Any]:
        """Hậu kiểm toàn diện 1 clip qua 5 Gate, trả về verdict + cửa sổ cắt tối ưu `[trim_in_s, trim_out_s]`."""
        clip_path = Path(clip_path)
        defects: List[str] = []
        warnings: List[str] = []
        metrics: Dict[str, Any] = {}

        # Gate 1A: FFprobe specs
        probe_info, probe_err = cls.probe_clip(clip_path)
        if probe_err:
            return {
                "verdict": "REJECT",
                "defect_code": "PROBE_FAILED",
                "defects": [probe_err],
                "warnings": [],
                "metrics": {"quality_score": 0.0},
            }

        metrics["probe"] = probe_info
        duration = float(probe_info["duration"])

        if probe_info["size_bytes"] < 100 * 1024:
            defects.append(f"DEFECT_TINY_FILE: File quá nhỏ ({probe_info['size_bytes']} bytes), nghi ngờ clip rỗng.")
        if duration < min_duration_s:
            defects.append(f"DEFECT_DURATION_SHORT: Thời lượng video quá ngắn ({duration:.2f}s < {min_duration_s:.2f}s).")
        aspect = probe_info["width"] / max(1, probe_info["height"])
        if abs(aspect - (16.0 / 9.0)) > 0.05:
            defects.append(f"DEFECT_ASPECT_RATIO: Tỉ lệ khung hình không chuẩn 16:9 ({probe_info['width']}x{probe_info['height']}).")

        # Gate 1B: Full Stream Decode
        decode_ok, decode_msg = cls.verify_full_decode(clip_path)
        if not decode_ok:
            defects.append(f"DEFECT_CORRUPT_STREAM: {decode_msg}")

        expected_dialogue = (shot_spec.get("dialogue") or shot_spec.get("dialogue_text") or "").strip()
        has_dialogue = len(expected_dialogue) > 3
        staging_kind = (shot_spec.get("staging") or {}).get("kind")

        # Gate 2 & Gate 3 (Luma / Freeze / Flicker)
        motion_res: Dict[str, Any] = {}
        try:
            motion_res = cls.analyze_temporal_motion_and_freeze(clip_path, sample_fps=4, has_dialogue=has_dialogue)
            metrics["motion"] = motion_res
            if motion_res.get("is_frozen") and (staging_kind != "state_insert" or motion_res.get("error")):
                defects.append("DEFECT_FROZEN_VIDEO: Video bị đơ thành ảnh tĩnh (năng lượng chuyển động < 0.4).")
            if motion_res.get("partial_freeze_speech"):
                defects.append("DEFECT_PARTIAL_FREEZE: Nhân vật đơ cứng trong cửa sổ thoại (0.5s-4.5s).")
            if motion_res.get("has_flicker"):
                defects.append(
                    f"DEFECT_FLICKER_OR_JUMPCUT: Phát hiện nhảy sáng / giật cắt cảnh đột ngột (delta Y={motion_res.get('max_luma_jump')} > 60)."
                )
            if motion_res.get("has_internal_cut"):
                defects.append(
                    f"DEFECT_INTERNAL_SCENE_CUT: Phát hiện cắt nhảy bối cảnh nội bộ trong 1 shot (hist_corr={motion_res.get('min_hist_corr')} < 0.55)."
                )
            if motion_res.get("has_black_out"):
                defects.append("DEFECT_BLACK_FRAMES: Phát hiện quá nhiều khung hình đen trong clip.")
        except Exception as me:
            metrics["motion_error"] = str(me)

        # Gate 3B: Optical Flow (Camera drift trên góc nền trên & head motion cho cảnh tĩnh)
        action_lower = (shot_spec.get("action_summary") or "").lower()
        has_body_motion_verb = any(
            v in action_lower for v in ("walk", "step", "fasten", "lift", "turn", "stand", "snatch", "nod", "shake", "enter", "exit", "pull", "push")
        )
        try:
            flow_res = cls.analyze_optical_flow(clip_path)
            metrics["optical_flow"] = flow_res
            if flow_res.get("camera_drift_px", 0.0) > 28.0 and (shot_spec.get("allow_camera_motion") is not True):
                defects.append(
                    f"DEFECT_CAMERA_DRIFT: Camera tự lia/trôi nền quá ngưỡng khóa máy ({flow_res['camera_drift_px']}px > 28px)."
                )
            if not has_dialogue and not has_body_motion_verb and (
                flow_res.get("nod_range_pct", 0.0) > 25.0 or flow_res.get("shake_range_pct", 0.0) > 25.0
            ):
                defects.append(
                    f"DEFECT_UNLICENSED_HEAD_MOTION: Đầu lắc/gật bất thường ở cảnh tĩnh (nod={flow_res['nod_range_pct']}%, shake={flow_res['shake_range_pct']}%)."
                )
        except Exception as fe:
            metrics["optical_flow_error"] = str(fe)

        # Gate 4B: Actor Visual Consistency & Face Detection
        try:
            ff_raw = shot_spec.get("first_frame_path")
            ref_p = Path(ff_raw) if ff_raw and Path(ff_raw).is_file() else None
            actor_res = cls.analyze_actor_visual_consistency(clip_path, reference_image_path=ref_p)
            metrics["actor_consistency"] = actor_res
            id_sim = actor_res.get("identity_similarity")
            if id_sim is not None:
                if id_sim < 0.20:
                    warnings.append(
                        f"VISUAL_IDENTITY_DRIFT_WARNING: Độ tương đồng thị giác thấp so với ảnh gốc (identity_similarity={id_sim:.3f} < 0.20)."
                    )
                if (shot_spec.get("enforce_identity_qc") is True) and id_sim < 0.25:
                    defects.append(
                        f"DEFECT_VISUAL_IDENTITY_DRIFT: Nhân vật/bối cảnh lệch nghiêm trọng so với ảnh tham chiếu (identity_similarity={id_sim:.3f} < 0.25)."
                    )
        except Exception as ae:
            metrics["actor_consistency_error"] = str(ae)

        # Gate 5: Faster-Whisper ASR (chạy trước Gate 4 trim để biết chính xác speech_end_s)
        speech_start_s = None
        speech_end_s = None
        if has_dialogue:
            asr_res = cls.verify_native_dialogue(clip_path, expected_dialogue)
            metrics["dialogue_qc"] = asr_res
            speech_start_s = asr_res.get("speech_start_s")
            speech_end_s = asr_res.get("speech_end_s")
            if asr_res.get("spoken_stage_direction"):
                defects.append("DEFECT_SPOKEN_STAGE_DIRECTION: AI đọc thành tiếng chỉ dẫn sân khấu ('brief pause'/'short pause').")
            elif not asr_res.get("passed", False):
                wer_val = asr_res.get("wer", 1.0)
                defects.append(f"DEFECT_DIALOGUE_MISMATCH: Lời thoại nhận diện không khớp kịch bản (WER {wer_val * 100:.1f}% > 15%).")

        # Gate 5B: Audio Signal Quality & Ventriloquist Lip-Sync Check
        try:
            audio_res = cls.analyze_audio_signal_and_lipsync(
                clip_path,
                has_dialogue=has_dialogue,
                speech_start_s=speech_start_s,
                speech_end_s=speech_end_s,
            )
            metrics["audio_lipsync"] = audio_res
            clip_ratio = float(audio_res.get("clipping_ratio", 0.0))
            if clip_ratio > 0.05:
                warnings.append(f"AUDIO_CLIPPING_WARNING: Tín hiệu âm thanh bị quá tải/xén đỉnh (clipping_ratio={clip_ratio:.3f}).")
            if clip_ratio > 0.20:
                defects.append(f"DEFECT_AUDIO_CLIPPING: Tín hiệu âm thanh bị vỡ nghiêm trọng (clipping_ratio={clip_ratio:.3f} > 0.20).")

            if has_dialogue:
                rms_val = float(audio_res.get("rms_dbfs", -100.0))
                if rms_val < -55.0:
                    defects.append(
                        f"DEFECT_SILENT_DIALOGUE_TRACK: Clip có lời thoại nhưng luồng âm thanh câm (rms_dbfs={rms_val:.2f} < -55.0 dBFS)."
                    )
                mouth_e = audio_res.get("mouth_motion_energy")
                if mouth_e is not None and float(mouth_e) < 0.15:
                    warnings.append("VENTRILOQUIST_LIPSYNC_WARNING: Có tiếng thoại nhưng vùng mặt/khẩu hình gần như bất động")
                    if shot_spec.get("enforce_lipsync_qc") is True:
                        defects.append(
                            f"DEFECT_LIPSYNC_FROZEN_MOUTH: Khẩu hình bất động trong cửa sổ thoại (mouth_motion_energy={float(mouth_e):.3f} < 0.15)."
                        )
        except Exception as ale:
            metrics["audio_lipsync_error"] = str(ale)

        # Gate 4: Giải phẫu bàn tay & Defensive Cut Point
        prompt_text = (shot_spec.get("prompt") or shot_spec.get("compiled_prompt") or shot_spec.get("text") or "").lower()
        has_hand_action = any(w in prompt_text for w in ["hand", "finger", "phone", "badge", "hold", "touch", "grip", "throttle", "intercom"])
        defensive_trim_out_s = None

        if has_hand_action:
            metrics["hand_audit_required"] = True
            if shot_spec.get("has_hand_defect") or shot_spec.get("reject_hand"):
                defects.append("DEFECT_ANATOMICAL_HAND_MUTATION: Phát hiện dị tật ngón tay/ngón dính/ngón thừa trong tương tác đồ vật.")
            spike_t = motion_res.get("hand_spike_time_s")
            if spike_t is not None:
                if speech_end_s is not None and spike_t > speech_end_s + 0.35:
                    defensive_trim_out_s = round(max(speech_end_s + 0.45, spike_t - 0.15), 2)
                    warnings.append(f"DEFENSIVE_TRIM_APPLIED: Phát hiện biến động vùng tay tại {spike_t}s sau thoại, cắt bảo vệ tại {defensive_trim_out_s}s.")
                else:
                    warnings.append(f"HAND_SPIKE_DETECTED: Biến động mạnh vùng tương tác tay tại {spike_t}s — cần kiểm tra contact strip.")

        # Gate 3C: Spatial Continuity 3x3 HSV Grid & Auto-Settle Trim (chạy sau ASR để biết speech_start/end)
        dyn_text = f"{action_lower} {(shot_spec.get('narration') or '').lower()}"
        is_walking_shot = any(
            w in dyn_text
            for w in (
                "walk", "enter", "exit", "corridor", "concourse", "step", "pace",
                "lift", "sky", "cloud", "applause", "cheer", "watch", "crowd",
                "graduation ring", "gleaming",
            )
        )
        spatial_res: Dict[str, Any] = {}
        try:
            spatial_res = cls.analyze_spatial_continuity(
                clip_path,
                has_dialogue=has_dialogue,
                speech_start_s=speech_start_s,
                speech_end_s=speech_end_s,
                min_duration_s=min_duration_s,
                is_walking_shot=is_walking_shot,
                allow_camera_motion=bool(shot_spec.get("allow_camera_motion")),
            )
            metrics["spatial_continuity"] = spatial_res
            if spatial_res.get("has_internal_cut"):
                defects.append(
                    f"DEFECT_INTERNAL_SCENE_CUT: Phát hiện cắt nhảy/biến đổi bố cục nội bộ (span_grid_corr={spatial_res.get('span_grid_corr')})."
                )
        except Exception as se:
            metrics["spatial_continuity_error"] = str(se)

        # Tính toán cửa sổ cắt tối ưu cho hậu kỳ (khử khoảng chết 2 đầu)
        if staging_kind == "source_action":
            trim_in, trim_out = 0.0, duration
        elif has_dialogue and speech_end_s is not None:
            trim_in = max(0.0, round((speech_start_s or 0.0) - 0.25, 2))
            trim_out = min(duration, round(speech_end_s + 0.60, 2))
            if defensive_trim_out_s is not None:
                trim_out = min(trim_out, defensive_trim_out_s)
            trim_out = max(trim_in + 1.5, trim_out)
        else:
            target_dur = float(shot_spec.get("target_trim_duration_s") or (3.5 if duration <= 5.5 else 7.5))
            trim_in = 0.0
            trim_out = min(duration, target_dur)

        early_cut_s = motion_res.get("early_transition_cut_s")
        if staging_kind != "source_action" and early_cut_s is not None and (
            not has_dialogue or speech_start_s is None or speech_start_s >= 1.10
        ):
            trim_in = max(trim_in, float(early_cut_s))
            trim_out = min(duration, max(trim_in + 1.5, trim_out))
            warnings.append("EARLY_TRANSITION_TRIMMED: Cắt bỏ chuyển trạng thái đầu clip trước 1.25s.")

        if has_dialogue:
            if spatial_res.get("settled_in_s") is not None:
                trim_in = max(trim_in, float(spatial_res["settled_in_s"]))
                trim_out = min(duration, max(trim_in + 1.5, trim_out))
        elif staging_kind != "source_action":
            if (
                spatial_res.get("settled_in_s") is not None
                and spatial_res.get("settled_out_s") is not None
                and not spatial_res.get("has_internal_cut")
            ):
                s_in = float(spatial_res["settled_in_s"])
                s_out = float(spatial_res["settled_out_s"])
                trim_in = s_in
                trim_out = min(duration, s_out, s_in + target_dur)
                if s_in > 0.25:
                    warnings.append(f"AUTO_SETTLE_TRIM: Đã cắt bỏ chuyển trạng thái đầu clip [0..{s_in:.2f}s].")

        metrics["trim_window"] = {
            "trim_in_s": round(trim_in, 2),
            "trim_out_s": round(trim_out, 2),
            "defensive_trim_out_s": defensive_trim_out_s,
            "trimmed_duration_s": round(max(0.1, trim_out - trim_in), 2),
        }

        if strip_output_path is not None:
            ts_points = [
                max(0.2, trim_in + 0.3),
                round((trim_in + trim_out) * 0.5, 2),
                max(0.4, trim_out - 0.3),
                max(0.5, duration - 0.4),
            ]
            strip_p = cls.generate_qc_strip(
                clip_path,
                strip_output_path,
                timestamps=ts_points,
                label_prefix=str(shot_spec.get("shot_id") or shot_spec.get("id") or ""),
            )
            if strip_p:
                metrics["qc_strip"] = str(strip_p)

        verdict = "PASS" if len(defects) == 0 else "REJECT"
        result: Dict[str, Any] = {
            "verdict": verdict,
            "shot_id": shot_spec.get("shot_id") or shot_spec.get("id"),
            "allow_camera_motion": bool(shot_spec.get("allow_camera_motion")),
            "defects_count": len(defects),
            "defects": defects,
            "warnings": warnings,
            "metrics": metrics,
        }
        metrics["quality_score"] = round(cls.compute_take_quality_score(result), 2)
        return result

    @staticmethod
    def compute_take_quality_score(qc_result: Dict[str, Any]) -> float:
        """Chấm điểm chất lượng định lượng 0.0..100.0 cho take đạt PASS (Multi-Take Best-of-N)."""
        if qc_result.get("verdict") != "PASS":
            return 0.0

        metrics = qc_result.get("metrics") or {}
        warnings = qc_result.get("warnings") or []
        allow_motion = bool(qc_result.get("allow_camera_motion"))

        if "dialogue_qc" in metrics and metrics["dialogue_qc"] is not None:
            wer = float(metrics["dialogue_qc"].get("wer", 0.0))
            wer_score = (1.0 - min(1.0, max(0.0, wer))) * 40.0
        else:
            wer_score = 40.0

        spatial = metrics.get("spatial_continuity")
        if spatial is not None:
            span_grid_corr = float(spatial.get("span_grid_corr", 0.0))
            if allow_motion and not spatial.get("has_internal_cut"):
                span_grid_corr = max(span_grid_corr, 0.88)
        else:
            span_grid_corr = 1.0
        spatial_score = max(0.0, min(1.0, span_grid_corr)) * 25.0

        flow = metrics.get("optical_flow") or {}
        if allow_motion:
            jitter = max(float(flow.get("nod_range_pct", 0.0)), float(flow.get("shake_range_pct", 0.0)))
            camera_score = 20.0 if jitter <= 25.0 else max(0.0, 20.0 - (jitter - 25.0) * 0.8)
        else:
            camera_drift_px = max(0.0, float(flow.get("camera_drift_px", 0.0)))
            camera_score = max(0.0, 20.0 - camera_drift_px * 0.6)

        bonus_score = max(0.0, 15.0 - 3.0 * len(warnings))

        total = wer_score + spatial_score + camera_score + bonus_score
        return round(float(np.clip(total, 0.0, 100.0)), 2)

    @classmethod
    def select_best_candidate(
        cls,
        candidate_paths: List[Path],
        shot_spec: Dict[str, Any],
        min_duration_s: float = 3.0,
        strip_output_path: Optional[Path] = None,
    ) -> Tuple[Optional[Path], Dict[str, Any], List[Dict[str, Any]]]:
        """Chấm toàn bộ các ứng viên hiện có, chọn take PASS điểm cao nhất và sinh Contact Strip cho bản được chọn."""
        existing = [Path(p) for p in (candidate_paths or []) if p is not None and Path(p).is_file()]
        if not existing:
            empty_res: Dict[str, Any] = {
                "verdict": "REJECT",
                "defect_code": "NO_CANDIDATES",
                "shot_id": shot_spec.get("shot_id") or shot_spec.get("id"),
                "defects_count": 1,
                "defects": ["Không tìm thấy file ứng viên video nào tồn tại trên ổ đĩa."],
                "warnings": [],
                "metrics": {"quality_score": 0.0},
            }
            return None, empty_res, []

        evaluated: List[Tuple[Path, Dict[str, Any]]] = []
        all_results: List[Dict[str, Any]] = []
        for cand_p in existing:
            res = cls.evaluate_generated_clip(
                cand_p,
                shot_spec=shot_spec,
                min_duration_s=min_duration_s,
                strip_output_path=None,
            )
            res["candidate_path"] = str(cand_p)
            evaluated.append((cand_p, res))
            all_results.append(res)

        passed = [(p, r) for p, r in evaluated if r.get("verdict") == "PASS"]
        if passed:
            winner_path, chosen_res = max(
                passed,
                key=lambda item: float((item[1].get("metrics") or {}).get("quality_score", 0.0)),
            )
            strip_target_clip = winner_path
        else:
            winner_path = None
            strip_target_clip, chosen_res = evaluated[-1]

        if strip_output_path is not None:
            m = chosen_res.get("metrics") or {}
            probe = m.get("probe") or {}
            if probe:
                dur = float(probe.get("duration", 0.0))
                tw = m.get("trim_window") or {}
                trim_in = float(tw.get("trim_in_s", 0.0))
                trim_out = float(tw.get("trim_out_s", dur))
                ts_points = [
                    max(0.2, trim_in + 0.3),
                    round((trim_in + trim_out) * 0.5, 2),
                    max(0.4, trim_out - 0.3),
                    max(0.5, dur - 0.4),
                ]
                strip_p = cls.generate_qc_strip(
                    strip_target_clip,
                    Path(strip_output_path),
                    timestamps=ts_points,
                    label_prefix=str(shot_spec.get("shot_id") or shot_spec.get("id") or ""),
                )
                if strip_p:
                    chosen_res.setdefault("metrics", {})["qc_strip"] = str(strip_p)

        return winner_path, chosen_res, all_results
