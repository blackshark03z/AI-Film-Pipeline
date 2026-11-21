"""
Closed-Loop Semantic Prompt Repair Agent (Khâu 5 -> Tự chữa lỗi trước Retry).
Đọc danh sách mã lỗi `defects` từ `FilmQCEngine` và tự động viết lại / gia cố `compiled_prompt`,
`framing`, `dialogue`, `action_summary` của các shot bị `QC_REJECT` trước vòng render tiếp theo,
đồng thời bảo toàn tuyệt đối các bất biến Preflight (`16:9`, `Locked-off static tripod`, `180° gaze`).
"""

import copy
import re
from typing import Any, Dict, List


class PromptRepairAgent:
    """Tác tử tự chữa prompt theo nguyên nhân lỗi 5-Gate QC."""

    STAGE_DIRECTION_PAT = re.compile(r"\([^)]*\)|\[[^\]]*\]")
    TIMECODE_TAG_PAT = re.compile(r"^\s*\d+(?:\.\d+)?\s*-\s*\d+(?:\.\d+)?s\s*$", re.IGNORECASE)
    PAREN_STAGE_CUE_PAT = re.compile(
        r"\b(?:pause|sighs?|sighing|breath|beat|whispers?|whispering|coughs?|chuckles?|laughs?|clears?\s+throat|hesitates?|hesitating)\b",
        re.IGNORECASE,
    )

    @classmethod
    def clean_spoken_dialogue(cls, dialogue: str) -> str:
        if not dialogue:
            return dialogue
        cleaned = cls.STAGE_DIRECTION_PAT.sub(" ", dialogue)
        cleaned = re.sub(
            r"\b(?:brief pause|short pause|natural breath|beat)\b[.,;:\-\s]*",
            " ",
            cleaned,
            flags=re.IGNORECASE,
        )
        return re.sub(r"\s+", " ", cleaned).strip()

    @classmethod
    def _clean_prompt_stage_leaks(cls, prompt: str) -> str:
        """Loại bỏ chỉ dẫn sân khấu rò rỉ (`[sighs]`, `(brief pause)`) nhưng bảo toàn `[0.5-9s]` và `(looking screen-right)`."""
        if not prompt:
            return prompt

        def _repl_bracket(m: re.Match) -> str:
            inner = m.group(1)
            if cls.TIMECODE_TAG_PAT.match(inner):
                return m.group(0)
            return " "

        def _repl_paren(m: re.Match) -> str:
            inner = m.group(1)
            if cls.PAREN_STAGE_CUE_PAT.search(inner):
                return " "
            return m.group(0)

        out = re.sub(r"\[([^\]]*)\]", _repl_bracket, prompt)
        out = re.sub(r"\(([^)]*)\)", _repl_paren, out)
        out = re.sub(r"\b(?:brief pause|short pause)\b[.,;:\-\s]*", " ", out, flags=re.IGNORECASE)
        return out

    @classmethod
    def repair_shot(cls, shot: Dict[str, Any], defects: List[str]) -> Dict[str, Any]:
        updated = copy.deepcopy(shot)
        blob = " | ".join(defects or []).upper()
        prompt = updated.get("compiled_prompt") or updated.get("prompt") or ""
        applied_fixes: List[str] = []
        directed_prop = (updated.get("staging") or {}).get("kind") in ("state_insert", "source_action")

        # 1. Lỗi dị tật bàn tay / ngón tay -> Đổi sang Chest-up Medium Close-up và giấu tay dưới khung hình
        if not directed_prop and ("HAND_MUTATION" in blob or "HAND_SPIKE" in blob or "FINGER" in blob):
            old_framing = updated.get("framing") or "Medium Shot"
            new_framing = "Medium Close-up, chest-up framing"
            updated["framing"] = new_framing
            updated["action_summary"] = "Character remains composed from the chest up; hands stay below frame."
            if old_framing in prompt:
                prompt = prompt.replace(old_framing, new_framing, 1)
            prompt = re.sub(
                r"Both hands clearly visible with five distinct fingers each[^.]*\.",
                "Hands remain completely below frame and out of frame.",
                prompt,
                flags=re.IGNORECASE,
            )
            if "out of frame" not in prompt.lower() and "below frame" not in prompt.lower():
                prompt = f"{prompt.rstrip()} Hands remain completely below frame and out of frame."
            applied_fixes.append("HIDE_HANDS_CHEST_UP")

        # 2. Lỗi ASR / Đọc nhầm chỉ dẫn sân khấu / Câm tiếng / Nói bụng -> Tước ngoặc & ép khẩu hình + âm lượng rõ chữ
        if not directed_prop and (
            "SPOKEN_STAGE_DIRECTION" in blob
            or "DIALOGUE_MISMATCH" in blob
            or "SILENT_DIALOGUE_TRACK" in blob
            or "LIPSYNC_FROZEN_MOUTH" in blob
            or "AUDIO_CLIPPING" in blob
        ):
            old_dlg = updated.get("dialogue") or ""
            clean_dlg = cls.clean_spoken_dialogue(old_dlg)
            if clean_dlg and old_dlg and old_dlg != clean_dlg:
                prompt = prompt.replace(old_dlg, clean_dlg)
                updated["dialogue"] = clean_dlg
            prompt = cls._clean_prompt_stage_leaks(prompt)
            if "articulating every english word clearly" not in prompt.lower():
                prompt = (
                    f"{prompt.rstrip()} Character speaks facing steady forward-diagonal axis, "
                    f"articulating every English word clearly and unhurriedly with crisp audible voice and visible lip synchronization."
                )
            applied_fixes.append("CLARIFY_ASR_LIPSYNC")

        # 2B. Lỗi lệch nhân dạng / bối cảnh so với ảnh gốc -> Siết neo vào Image 1
        if not directed_prop and "VISUAL_IDENTITY_DRIFT" in blob:
            if "exact facial structure and wardrobe from image 1" not in prompt.lower():
                prompt = (
                    f"{prompt.rstrip()} Strictly preserve the exact facial structure and wardrobe from Image 1 "
                    f"and exact background geometry throughout."
                )
            applied_fixes.append("REINFORCE_REFERENCE_IDENTITY")

        # 3. Lỗi đơ hình / đơ trong thoại -> Bổ sung chuyển động vi biểu cảm & nhịp thở tự nhiên
        if not directed_prop and ("FROZEN_VIDEO" in blob or "PARTIAL_FREEZE" in blob):
            if "natural expressive facial" not in prompt.lower():
                prompt = (
                    f"{prompt.rstrip()} Natural expressive facial micro-movements, subtle breathing, "
                    f"and gentle organic upper-body presence throughout."
                )
            applied_fixes.append("BOOST_ORGANIC_MICRO_MOTION")

        # 4. Lỗi trôi camera / giật cắt nội bộ / lắc đầu -> Siết khóa chân máy & phơi sáng bất biến
        if (
            "CAMERA_DRIFT" in blob
            or "INTERNAL_SCENE_CUT" in blob
            or "FLICKER" in blob
            or "UNLICENSED_HEAD_MOTION" in blob
        ):
            if "zero background translation" not in prompt.lower():
                steady_pose = "" if directed_prop else "steady head posture, "
                prompt = (
                    f"{prompt.rstrip()} Rigid locked-off static tripod mount with zero background translation, "
                    f"constant lighting exposure, {steady_pose}single unbroken 16:9 take."
                )
            applied_fixes.append("REINFORCE_STATIC_TRIPOD_CONTINUITY")

        # Đảm bảo 2 bất biến Preflight không bao giờ bị mất
        if "16:9" not in prompt.lower():
            prompt = f"{prompt.rstrip()} Framed in exactly 16:9 aspect ratio."
        if (updated.get("allow_camera_motion") is not True) and ("locked-off" not in prompt.lower() and "static tripod" not in prompt.lower()):
            prompt = f"Locked-off static tripod shot. {prompt}"

        prompt = re.sub(r"\s+", " ", prompt).strip()
        updated["compiled_prompt"] = prompt
        updated["repair_attempts"] = int(updated.get("repair_attempts") or 0) + 1
        history = list(updated.get("repair_history") or [])
        history.append({"attempt": updated["repair_attempts"], "fixes": applied_fixes, "defects": list(defects or [])})
        updated["repair_history"] = history
        return updated

    @classmethod
    def repair_manifest_shots(
        cls,
        manifest: Dict[str, Any],
        defects_by_shot_id: Dict[str, List[str]],
    ) -> Dict[str, Any]:
        """Sửa trực tiếp các shot bị lỗi trong `manifest` và trả về báo cáo số shot đã chữa."""
        repaired_ids: List[str] = []
        new_shots: List[Dict[str, Any]] = []
        for s in manifest.get("shots", []):
            sid = s.get("shot_id")
            if sid and sid in defects_by_shot_id and defects_by_shot_id[sid]:
                new_shots.append(cls.repair_shot(s, defects_by_shot_id[sid]))
                repaired_ids.append(sid)
            else:
                new_shots.append(s)
        manifest["shots"] = new_shots
        return {"repaired_count": len(repaired_ids), "repaired_shot_ids": repaired_ids}
