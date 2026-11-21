"""
Screenplay & Story Bible Compiler (Khâu 1 -> Khâu 3)
Biên dịch Story Bible + Beats (hoặc SRT) thành `shots_manifest.json` và `shots_manifest.csv` chuẩn 5-Aspect:
- Khóa duy nhất anchor từng nhân vật (cấm 2 vai dùng chung 1 ảnh mỏ neo).
- Bảo toàn 100% mô tả nhân vật (`look_verbatim`), bối cảnh (`loc_desc` + `set_facts`), và trạng thái đạo cụ (`props_ledger`).
- Hỗ trợ 2 chế độ âm lời: `native_drama` (mặc định: 100% Live-Action, chuyển beat dẫn chuyện thành cảnh hành động gọn 3.0-3.8s + thẻ địa điểm) và `hybrid_narrated` (sinh VO qua Edge-TTS cho beat dẫn chuyện).
- Bảo toàn trục 180° và khóa giải phẫu bàn tay (loại bỏ hành động ngón tay rủi ro).
"""

import csv
import hashlib
import json
import math
import unicodedata
import re
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

try:
    from .staging import plan_staging
except ImportError:
    from core.staging import plan_staging


class StoryBibleError(ValueError):
    pass


class ScreenplayCompiler:
    """Biên dịch kịch bản chuẩn hóa điện ảnh 5-Aspect Taxonomy cho Muse."""

    HAZARDOUS_FINGER_REPLACEMENTS = (
        (r"\btap(?:s|ping)?\s+(?:the\s+|on\s+)?screen\b", "holds the smartphone steadily in palm"),
        (r"\btype(?:s|ing)?\s+(?:on\s+)?(?:the\s+)?keyboard\b", "rests hands steadily at the console"),
        (r"\bflick(?:s|ing)?\s+fingers?\b", "gestures calmly with open palm"),
        (r"\bintertwined\s+fingers\b", "hands resting naturally side by side"),
    )

    HAND_KEYWORDS = (
        "hand", "finger", "phone", "smartphone", "cellphone", "telephone", "badge", "clipboard", "tablet", "lever",
        "throttle", "hold", "grip", "snatch", "intercom", "touch", "pocket",
    )
    # Opening states that keep the hands hidden must not turn on the "both hands visible" guard.
    HANDS_HIDDEN_RE = re.compile(
        r"\bhands?\b[^.]*\b(hidden|out of (?:frame|view|sight)|not visible|tucked|"
        r"in (?:his|her|their) pockets|behind (?:his|her|their) back)\b"
        r"|\b(hides|hidden|tucks|tucked)\b[^.]*\bhands?\b",
        re.I,
    )
    HAND_GUARD = "Both hands clearly visible with five distinct fingers each, no extra fingers, no fused digits."

    LEGACY_PROP_SYNONYMS = {
        "badge": ("badge", "credential", "card"),
        "intercom": ("intercom", "pa", "handset"),
        "phone": ("phone", "smartphone", "cellphone", "call"),
        "throttle": ("throttle", "thrust", "takeoff"),
    }

    PROP_STOPWORDS = {
        "prop", "props", "the", "and", "for", "with", "from", "into",
        "that", "this", "his", "her", "its", "item",
    }

    MUST_SHOW_STOPWORDS = {
        "the", "and", "for", "with", "from", "into", "that", "this",
        "his", "her", "its", "shot", "scene", "show", "cảnh", "chi",
        "tiết", "của", "trong", "trên",
    }

    DEFAULT_AMBIENT_BY_LOC = {
        "LOC_JETBRIDGE_B14": "quiet enclosed airport jetbridge corridor ventilation hum",
        "LOC_AIRCRAFT_GALLEY": "quiet commercial airplane cabin ventilation hum",
        "LOC_COCKPIT_737": "subtle Boeing 737 cockpit avionics cooling fan hum",
        "LOC_GATE_CONCOURSE": "distant muted airport terminal concourse ambient murmur",
    }

    @staticmethod
    def _sha256_file(path: Path) -> Optional[str]:
        if not path.exists() or not path.is_file():
            return None
        h = hashlib.sha256()
        with open(path, "rb") as f:
            while chunk := f.read(65536):
                h.update(chunk)
        return h.hexdigest()

    @classmethod
    def sanitize_hand_action(cls, text: str) -> str:
        out = text or ""
        for pat, repl in cls.HAZARDOUS_FINGER_REPLACEMENTS:
            out = re.sub(pat, repl, out, flags=re.IGNORECASE)
        return out

    # Planning rate for native dialogue; B14 Todd measured ~2.2 words/s incl. one sentence pause.
    SPEECH_WORDS_PER_S = 2.4
    SENTENCE_PAUSE_S = 0.3
    SPEECH_START_S = 0.5
    SPEECH_TAIL_S = 1.0

    @classmethod
    def estimate_dialogue_timing(cls, dialogue: str, clip_s: float = 10.0) -> Dict[str, Any]:
        """Estimate spoken length so the prompt window and the fit check follow the actual line."""
        words = 0
        # NFC + straight apostrophes, so curly apostrophes and decomposed (NFD) accents time like their plain forms.
        text = unicodedata.normalize("NFC", dialogue or "").replace("\u2019", "'").replace("\u2018", "'")
        # Unicode letters (plus any leftover combining marks), so accented words count as one word each.
        letter = r"(?:[^\W_]|[\u0300-\u036f])"
        for token in re.findall(rf"\d+(?:[.,]\d+)*|{letter}+(?:'{letter}+)*", text):
            digits = re.sub(r"\D", "", token)
            # A number like 1128 or 1,128 is read as several words ("eleven twenty-eight").
            is_number = bool(re.fullmatch(r"\d+(?:[.,]\d+)*", token))
            words += max(1, math.ceil(len(digits) / 2)) if is_number else 1
        # Terminal punctuation followed by space or end, so the "." in "1.5" is not a sentence pause.
        sentences = len([s for s in re.split(r"[.!?]+(?=\s|$)", text) if s.strip()])
        est = round(words / cls.SPEECH_WORDS_PER_S + cls.SENTENCE_PAUSE_S * max(0, sentences - 1), 2)
        capacity = round(clip_s - cls.SPEECH_START_S - cls.SPEECH_TAIL_S, 2)
        end = round(min(cls.SPEECH_START_S + est, clip_s - cls.SPEECH_TAIL_S), 1)
        return {
            "spoken_words": words,
            "est_speech_s": est,
            "capacity_s": capacity,
            "speech_window_s": [cls.SPEECH_START_S, end],
            "status": "OVER_CAPACITY" if est > capacity else "FITS",
        }

    @classmethod
    def validate_story_bible(
        cls,
        bible: Dict[str, Any],
        anchors_dir: Optional[Path] = None,
        strict_files: bool = False
    ) -> List[str]:
        """Kiểm tra Story Bible: cấm thiếu look_verbatim và cấm 2 nhân vật dùng chung 1 ảnh anchor."""
        errors: List[str] = []
        chars = bible.get("characters", [])
        if not chars:
            errors.append("EMPTY_CHARACTERS: story_bible.json thiếu danh sách characters.")
            return errors

        seen_anchor_names: Dict[str, str] = {}
        seen_anchor_hashes: Dict[str, str] = {}

        for ch in chars:
            cid = ch.get("id", "UNKNOWN")
            if not ch.get("look_verbatim"):
                errors.append(f"MISSING_LOOK_VERBATIM: Nhân vật {cid} thiếu mô tả look_verbatim.")
            anchor_ref = ch.get("anchor_image")
            if not anchor_ref:
                errors.append(f"MISSING_ANCHOR_REF: Nhân vật {cid} thiếu trường anchor_image.")
                continue

            anchor_key = Path(anchor_ref).name.lower()
            if anchor_key in seen_anchor_names:
                errors.append(
                    f"DUPLICATE_CHARACTER_ANCHOR: {cid} dùng trùng anchor_image '{anchor_ref}' với {seen_anchor_names[anchor_key]}."
                )
            else:
                seen_anchor_names[anchor_key] = cid

            if anchors_dir:
                resolved = Path(anchor_ref) if Path(anchor_ref).is_absolute() else (anchors_dir / anchor_ref)
                if not resolved.exists():
                    if strict_files:
                        errors.append(f"MISSING_ANCHOR_FILE: Không tìm thấy ảnh mỏ neo {resolved} cho {cid}.")
                else:
                    fhash = cls._sha256_file(resolved)
                    if fhash:
                        if fhash in seen_anchor_hashes:
                            errors.append(
                                f"DUPLICATE_ANCHOR_HASH: Ảnh của {cid} trùng nội dung byte (SHA-256) với {seen_anchor_hashes[fhash]}."
                            )
                        else:
                            seen_anchor_hashes[fhash] = cid

        for loc in bible.get("locations", []):
            lid = loc.get("id", "UNKNOWN_LOC")
            if not loc.get("look_verbatim"):
                errors.append(f"MISSING_LOC_VERBATIM: Bối cảnh {lid} thiếu look_verbatim.")

        return errors

    @staticmethod
    def _match_character(speaker_name: Optional[str], chars_present: List[str], char_map: Dict[str, Dict[str, Any]]) -> Dict[str, Any]:
        if speaker_name:
            s_low = speaker_name.strip().lower()
            for cid, c in char_map.items():
                if s_low in c.get("name", "").lower() or s_low in cid.lower():
                    return c
        if chars_present:
            first_cid = chars_present[0]
            if first_cid in char_map:
                return char_map[first_cid]
        return next(iter(char_map.values()), {})

    @staticmethod
    def _is_multi_person_shot(framing: str, chars_present: List[str]) -> bool:
        f_low = (framing or "").lower()
        return len(chars_present) >= 2 and any(
            k in f_low for k in ("wide", "two", "over-the-shoulder", "ots", "group", "across", "standoff")
        )

    @staticmethod
    def _infer_lens_and_depth(framing: str, explicit_lens: Optional[str]) -> Tuple[int, str]:
        """Tự động chọn tiêu cự điện ảnh (Lens Psychology) và chiều sâu trường ảnh theo cỡ cảnh."""
        f_low = (framing or "").lower()
        if explicit_lens and explicit_lens.isdigit():
            mm = int(explicit_lens)
        elif any(k in f_low for k in ("insert", "macro", "extreme close")):
            mm = 100
        elif "close" in f_low:
            mm = 85
        elif any(k in f_low for k in ("over-the-shoulder", "ots", "profile")):
            mm = 50
        elif "wide" in f_low or "establishing" in f_low:
            mm = 24
        else:
            mm = 35

        if mm >= 85:
            dof_note = "shallow depth of field with creamy background bokeh isolating facial emotion"
        elif mm >= 50:
            dof_note = "natural cinematic depth with soft foreground/background separation"
        elif mm <= 28:
            dof_note = "deep architectural focus capturing full spatial geography and parallax"
        else:
            dof_note = "classic 35mm cinema depth balancing subject presence and lived-in environment"
        return mm, dof_note

    @staticmethod
    def _resolve_post_camera_motion(
        beat: Dict[str, Any],
        framing: str,
        is_climax: bool,
        allow_native_motion: bool,
        raw_cam_motion: str,
        shot_idx: int,
    ) -> str:
        """
        Quyết định chuyển động Virtual Camera Rig ở hậu kỳ (`MasterAssembler`) cho các shot khóa máy khi gen,
        giúp xóa bỏ cảm giác khung hình tĩnh chết cứng mà vẫn giữ Lip-Sync tuyệt đối ổn định.
        """
        explicit_post = (beat.get("post_camera_motion") or "").strip().lower()
        if explicit_post:
            return explicit_post

        if allow_native_motion:
            # Đã có chuyển động camera thật từ AI engine -> không chồng thêm zoom/pan số ở hậu kỳ
            return "static"

        mot_low = (raw_cam_motion or "").lower()
        if mot_low not in ("", "static", "locked", "locked-off", "none"):
            if any(k in mot_low for k in ("pull", "out", "back", "reveal")):
                return "pull_out"
            if any(k in mot_low for k in ("pan right", "drift right", "track right", "slider right")):
                return "drift_right"
            if any(k in mot_low for k in ("pan left", "drift left", "track left", "slider left")):
                return "drift_left"
            if any(k in mot_low for k in ("handheld", "breath", "float")):
                return "handheld_subtle"
            return "push_in"

        if is_climax:
            return "push_in"

        f_low = (framing or "").lower()
        if "wide" in f_low or "establishing" in f_low:
            return "drift_right" if shot_idx % 2 == 1 else "drift_left"
        if any(k in f_low for k in ("over-the-shoulder", "ots", "two-shot", "two shot")):
            return "handheld_subtle"
        if "close-up" in f_low and "medium" not in f_low:
            return "push_in" if shot_idx % 2 == 1 else "handheld_subtle"
        if shot_idx % 3 == 0:
            return "drift_right" if (shot_idx // 3) % 2 == 0 else "drift_left"
        return "static"

    @staticmethod
    def _match_window_key(win_key: str, chapter_id: Optional[str], beat_id: Optional[str]) -> Tuple[bool, bool]:
        """Return (beat_matched, chapter_matched) for a state_tracking or chapter-range key."""
        wk = (win_key or "").strip()
        if not wk:
            return False, False

        is_beat_key = bool(re.match(r"^(?:beat|b)[_\-\s]*\d+", wk, flags=re.IGNORECASE))
        if beat_id:
            bid = beat_id.strip()
            if wk.upper() == bid.upper():
                return True, False
            if is_beat_key:
                b_m = re.search(r"\d+", bid)
                nums = [int(x) for x in re.findall(r"\d+", wk)]
                if b_m and nums:
                    b_num = int(b_m.group(0))
                    if nums[0] <= b_num <= nums[-1]:
                        return True, False

        if not is_beat_key and chapter_id:
            cid = chapter_id.strip()
            if wk.upper() == cid.upper():
                return False, True
            ch_m = re.search(r"\d+", cid)
            nums = [int(x) for x in re.findall(r"\d+", wk)]
            if ch_m and nums:
                ch_num = int(ch_m.group(0))
                if nums[0] <= ch_num <= nums[-1]:
                    return False, True

        return False, False

    @classmethod
    def _resolve_chapter_wardrobe(cls, char_info: Dict[str, Any], chapter_id: str) -> Optional[str]:
        w_map = char_info.get("wardrobe_by_chapter") or {}
        if not isinstance(w_map, dict) or not w_map:
            return None
        if chapter_id in w_map and w_map[chapter_id]:
            return str(w_map[chapter_id]).strip()
        for wk, val in w_map.items():
            if not val:
                continue
            _, ch_matched = cls._match_window_key(str(wk), chapter_id=chapter_id, beat_id=None)
            if ch_matched:
                return str(val).strip()
        return None

    @classmethod
    def _match_props(
        cls,
        chapter_id: str,
        combined_text: str,
        props_ledger: List[Dict[str, Any]],
        beat_id: Optional[str] = None,
    ) -> Tuple[str, str]:
        if not props_ledger:
            return "", "default"

        act_low = (combined_text or "").lower()
        notes: List[str] = []
        primary_specific_slug: Optional[str] = None
        fallback_chapter_slug: Optional[str] = None

        for prop in props_ledger:
            raw_id = str(prop.get("id") or "")
            raw_name = str(prop.get("name") or "")
            desc = str(prop.get("description") or raw_name or raw_id).strip()

            explicit_kws = [str(k).strip().lower() for k in (prop.get("keywords") or []) if str(k).strip()]
            auto_tokens = [
                tok
                for tok in re.findall(r"[a-z0-9]+", f"{raw_id} {raw_name}".lower())
                if len(tok) >= 3 and tok not in cls.PROP_STOPWORDS and not tok.isdigit()
            ]
            search_terms: List[str] = list(dict.fromkeys(explicit_kws + auto_tokens))
            id_name_low = f"{raw_id} {raw_name}".lower()
            for leg_key, leg_syns in cls.LEGACY_PROP_SYNONYMS.items():
                if leg_key in id_name_low or leg_key in search_terms:
                    for syn in leg_syns:
                        if syn not in search_terms:
                            search_terms.append(syn)

            text_matched = False
            for kw in search_terms:
                if " " in kw:
                    if kw in act_low:
                        text_matched = True
                        break
                elif re.search(rf"\b{re.escape(kw)}(?:es|s)?\b", act_low):
                    text_matched = True
                    break

            beat_state_note = ""
            ch_state_note = ""
            beat_matched = False
            ch_matched = False
            for win_key, val in (prop.get("state_tracking") or {}).items():
                bm, cm = cls._match_window_key(str(win_key), chapter_id=chapter_id, beat_id=beat_id)
                if bm and not beat_matched:
                    beat_matched = True
                    beat_state_note = str(val)
                if cm and not ch_matched:
                    ch_matched = True
                    ch_state_note = str(val)

            if not (text_matched or beat_matched or ch_matched):
                continue

            slug_src = re.sub(r"^prop_", "", (raw_id or raw_name).lower())
            slug = re.sub(r"[^a-z0-9]+", "_", slug_src).strip("_") or "default"
            if (text_matched or beat_matched) and primary_specific_slug is None:
                primary_specific_slug = slug
            elif ch_matched and fallback_chapter_slug is None:
                fallback_chapter_slug = slug

            state_note = beat_state_note if beat_matched else ch_state_note
            if state_note:
                notes.append(f"Prop continuity ({desc}): {state_note}.")
            elif desc:
                notes.append(f"Prop detail: {desc}.")

        prop_tag = primary_specific_slug or fallback_chapter_slug or "default"
        return " ".join(notes), prop_tag

    @classmethod
    def _extract_relevant_props(
        cls,
        chapter_id: str,
        action_text: str,
        props_ledger: List[Dict[str, Any]],
        beat_id: Optional[str] = None,
        dialogue: Optional[str] = None,
        narration: Optional[str] = None,
    ) -> str:
        combined = " ".join(x for x in (action_text, dialogue, narration) if x)
        notes, _ = cls._match_props(chapter_id, combined, props_ledger, beat_id=beat_id)
        return notes

    @classmethod
    def compile_shots(
        cls,
        bible: Dict[str, Any],
        beats: List[Dict[str, Any]],
        audio_mode: str = "native_drama",
        anchors_dir: Optional[Path] = None,
        keyframes_map: Optional[Dict[str, str]] = None,
        strict_bible: bool = True,
        cinematic_cutaways: bool = False,
    ) -> Dict[str, Any]:
        """
        Biên dịch toàn bộ beats + story_bible thành `shots_manifest`.
        audio_mode: 'native_drama' (mặc định) hoặc 'hybrid_narrated'.
        """
        if audio_mode not in ("native_drama", "hybrid_narrated"):
            raise ValueError(f"audio_mode không hợp lệ: {audio_mode}")

        bible_errors = cls.validate_story_bible(bible, anchors_dir=anchors_dir, strict_files=False)
        if strict_bible and bible_errors:
            raise StoryBibleError("Story Bible có lỗi nghiêm trọng: " + " | ".join(bible_errors))

        beats, staging_review = plan_staging(bible, beats, include_optional=cinematic_cutaways)
        char_map: Dict[str, Dict[str, Any]] = {c["id"]: c for c in bible.get("characters", [])}
        loc_map: Dict[str, Dict[str, Any]] = {loc["id"]: loc for loc in bible.get("locations", [])}
        props_ledger: List[Dict[str, Any]] = bible.get("props_ledger", [])
        visual_style = bible.get("world_rules", {}).get(
            "visual_style",
            "cinematic photorealistic 35mm film, realistic lighting, natural film grain"
        )

        shots: List[Dict[str, Any]] = []
        prev_chapter = None
        prev_location = None

        for idx, b in enumerate(beats, start=1):
            chapter_id = b.get("chapter_id") or "CH01"
            beat_id = b.get("beat_id")
            shot_id = b.get("shot_id") or f"SHOT_{idx:03d}_{chapter_id}"
            loc_id = b.get("location") or next(iter(loc_map.keys()), "LOC_DEFAULT")
            loc_info = loc_map.get(loc_id, {})
            loc_name = loc_info.get("name", loc_id)
            loc_desc = loc_info.get("look_verbatim", "realistic modern interior")
            set_facts = loc_info.get("set_facts", [])
            set_facts_str = ("Set layout lock: " + "; ".join(set_facts) + ".") if set_facts else ""

            chars_present = b.get("characters_present") or []
            speaker = b.get("speaker")
            stage = b.get("staging_plan") or {}
            state_insert = stage.get("kind") == "state_insert"
            source_action = stage.get("kind") == "source_action"
            listener_reaction = stage.get("kind") == "reaction"
            primary_char = char_map[stage["character_id"]] if stage.get("character_id") else cls._match_character(
                speaker, chars_present, char_map
            )
            primary_cid = primary_char.get("id") or (chars_present[0] if chars_present else "CHAR_DEFAULT")
            if state_insert:
                primary_char, primary_cid = {}, None
            char_desc = primary_char.get("look_verbatim", "a realistic adult character")
            wardrobe = (b.get("wardrobe_override") or "").strip() or cls._resolve_chapter_wardrobe(primary_char, chapter_id)
            if wardrobe:
                sep = " " if char_desc.rstrip().endswith(".") else ". "
                char_desc = f"{char_desc.rstrip()}{sep}Current scene wardrobe: {wardrobe.rstrip('.')}."

            voice_prof = primary_char.get("voice_profile", "calm, natural measured English voice")
            # Ưu tiên hướng nhìn DOP dàn dựng riêng theo cảnh (b["gaze"]), fallback về axis_gaze mặc định của nhân vật
            locked_gaze = b.get("gaze") or primary_char.get("axis_gaze") or "looking screen-right"

            framing = b.get("framing") or "Medium Shot"
            is_multi = cls._is_multi_person_shot(framing, chars_present)
            dialogue = b.get("dialogue")
            narration = b.get("narration")
            action_raw = b.get("action_summary") or "Character maintains composed presence in the scene."
            action_safe = action_raw if source_action else cls.sanitize_hand_action(action_raw)
            subtext_note = (b.get("subtext") or b.get("acting_note") or "").strip()
            foreground_elem = (b.get("foreground_element") or "").strip()
            shot_role = (b.get("shot_role") or "").strip() or (
                "establishing" if "wide" in framing.lower() else ("dialogue" if dialogue else "reaction_or_action")
            )
            cutaway_type = b.get("cutaway_type")
            is_prop_insert = cutaway_type == "prop_insert"
            if is_prop_insert and not stage:
                action_safe = action_safe.replace(
                    "A hand moves into frame and gently rests on ",
                    "The hovering hand lowers and the fingertips gently rest on ",
                    1,
                )
            combined_beat_text = f"{action_safe} {dialogue or ''} {narration or ''}"
            prop_notes, prop_tag = cls._match_props(
                chapter_id=chapter_id,
                combined_text=combined_beat_text,
                props_ledger=props_ledger,
                beat_id=b.get("prop_source_beat_id") or beat_id,
            )
            if state_insert or source_action:
                prop_tag = re.sub(r"[^a-z0-9]+", "_", stage["prop_id"].lower()).strip("_")
                prop_notes = f"Prop: {stage['prop_description']}."
                if state_insert:
                    prop_notes += f" Established state: {stage['state']}."
            elif listener_reaction:
                prop_notes, prop_tag = "", "default"
            ambient = loc_info.get("ambient_sound") or cls.DEFAULT_AMBIENT_BY_LOC.get(
                loc_id, "quiet realistic interior ambient tone"
            )

            # Camera / Lens / Lighting / Flashback metadata
            lens_raw = b.get("lens_mm")
            lens_clean = str(lens_raw).strip().lower().replace("mm", "").strip() if lens_raw is not None else None
            resolved_lens_mm, dof_clause = cls._infer_lens_and_depth(framing, lens_clean)
            if state_insert:
                dof_clause = "shallow macro depth of field with the stationary prop in focus"
            elif is_prop_insert:
                dof_clause = "shallow macro depth of field with the prop and fingers in focus"
            camera_angle = (b.get("camera_angle") or "").strip() or None
            lighting_mood = (b.get("lighting_mood") or loc_info.get("lighting_mood") or "").strip() or None
            raw_cam_motion = (b.get("camera_motion") or "static").strip()
            is_static_motion = raw_cam_motion.lower() in ("", "static", "locked", "locked-off", "none")
            force_native_cam = bool(b.get("force_native_camera_motion"))
            allow_camera_motion = (not is_static_motion) and ((not bool(dialogue)) or force_native_cam)

            is_flashback = bool(b.get("is_flashback")) or ("flashback" in (b.get("chapter_title") or "").lower())
            color_mood = b.get("color_mood") or (
                "warm_flashback" if is_flashback else loc_info.get("color_mood", "cinematic_neutral")
            )
            transition_in = b.get("transition_in") or (
                "dissolve" if is_flashback else ("fade_in" if idx == 1 else "cut")
            )

            cinematography_extras: List[str] = [
                f"Shot on {lens_clean or resolved_lens_mm}mm cinema lens, {dof_clause}."
            ]
            if camera_angle:
                cinematography_extras.append(f"Camera angle: {camera_angle}.")
            if foreground_elem:
                cinematography_extras.append(f"Foreground depth layer: {foreground_elem.rstrip('.')}.")
            if lighting_mood:
                cinematography_extras.append(f"Lighting: {lighting_mood.rstrip('.')}.")
            cinema_extra_str = " ".join(cinematography_extras)

            # Xác định nhu cầu giải phẫu tay
            opening_state = b.get("opening_state")
            opening_state = " ".join(opening_state.split()) if isinstance(opening_state, str) else ""
            # The authored opening state is held in frame, so a visible hand in it needs the guard too;
            # a "hands hidden" opening must not demand both hands visible.
            opening_hands_hidden = bool(opening_state and cls.HANDS_HIDDEN_RE.search(opening_state))
            opening_for_hands = "" if opening_hands_hidden else opening_state
            combined_for_hands = f"{action_safe} {prop_notes} {opening_for_hands}".lower()
            # Word-start match: "hands"/"holding" count, a name like "Chandler" does not.
            needs_hand_guard = any(re.search(rf"\b{k}", combined_for_hands) for k in cls.HAND_KEYWORDS)
            hand_clause = cls.HAND_GUARD if needs_hand_guard else "Hands stay naturally out of frame or relaxed at sides."
            if opening_hands_hidden and not needs_hand_guard:
                hand_clause = "Hands stay hidden exactly as in the opening state."
            if listener_reaction and not needs_hand_guard:
                hand_clause = "Keep hands out of frame for this reaction."
            # Authored mouth movement ("mouths", "jaw drops") or an open-mouth opening must not be forbidden;
            # appearance words such as "jawline" or "mouthwash" do not count.
            mouth_action = bool(re.search(r"\b(mouth(?:s|ed|ing)?|lips?|jaws?)\b",
                                          f"{action_safe} {opening_state}", flags=re.I))

            # Xác định khung thời lượng & chế độ âm lời
            is_new_scene = (chapter_id != prev_chapter) or (loc_id != prev_location)
            scene_card_overlay = None
            char_desc_punct = char_desc if char_desc.endswith(".") else f"{char_desc}."

            dialogue_timing = None
            if dialogue:
                shot_duration_s = 10.0
                target_trim_s = None
                dialogue_timing = cls.estimate_dialogue_timing(dialogue, shot_duration_s)
                speech_end = dialogue_timing["speech_window_s"][1]
                shot_audio_mode = "NATIVE_DIALOGUE"
                voiceover_text = None
                cast_clause = (
                    "Both characters stay in their locked screen sides facing each other across the space."
                    if is_multi
                    else "Only this character in frame, same cast and wardrobe as the reference."
                )
                # Ghép mô tả đa nhân vật nếu là Two-Shot/OTS
                if is_multi:
                    other_cids = [c for c in chars_present if c != primary_cid]
                    other_desc = char_map.get(other_cids[0], {}).get("look_verbatim", "") if other_cids else ""
                    subject_block = (
                        f"Primary speaker: {char_desc} ({locked_gaze}). "
                        + (f"Other character present across the axis: {other_desc}." if other_desc else "")
                    )
                else:
                    subject_block = f"Subject: {char_desc_punct}"

                dlg_cam_clause = (
                    f"Controlled stabilized camera motion ({raw_cam_motion}) from fluid cinema dolly rig of exactly 10 seconds, "
                    f"in exactly 16:9 aspect ratio: smooth continuous {raw_cam_motion} with zero jitter and zero abrupt zoom."
                    if allow_camera_motion
                    else (
                        "Locked-off static tripod shot of exactly 10 seconds, in exactly 16:9 aspect ratio: "
                        "the camera does not move, pan, tilt or zoom, and framing stays identical from first frame to last."
                    )
                )
                subtext_clause = f"; emotional subtext: {subtext_note}" if subtext_note else ""

                prompt = (
                    f"Image 1 is the exact first frame of the shot, {framing}, {locked_gaze}. "
                    f"Start exactly from image 1. {dlg_cam_clause} "
                    f"Single continuous unedited take, zero scene cuts, zero camera angle changes. "
                    f"Visual style: {visual_style}. {cinema_extra_str} "
                    f"Setting ({loc_name}): {loc_desc}. {set_facts_str} "
                    f"{subject_block} {prop_notes} "
                    f"[0-0.5s] Subtle pre-speech listening reaction and natural breath, clear view of lips, {locked_gaze}. "
                    f"[0.5-{speech_end:g}s] Speaking directly in English ({voice_prof}{subtext_clause}), the character says verbatim: \"{dialogue}\" "
                    f"{action_safe} Natural eye blinks, authentic brow micro-expressions, and grounded upper-body presence without exaggerated head bobbing. {hand_clause} "
                    f"[{speech_end:g}-{shot_duration_s:g}s] Mouth closes cleanly and lingering gaze holds quiet emotional weight. "
                    f"No further words from anyone after the line. "
                    f"Sound design: {ambient}, no background music. "
                    f"{cast_clause} "
                    f"No new lettering. No on-screen text, subtitles, watermarks, or logos. Nobody looks into the lens."
                ).strip()
            else:
                # Beat không có thoại trực tiếp (chỉ có narration hoặc hành động chuyển cảnh)
                if audio_mode == "hybrid_narrated" and narration:
                    shot_duration_s = 10.0
                    target_trim_s = 7.5
                    shot_audio_mode = "HYBRID_VO"
                    voiceover_text = narration
                else:
                    # native_drama: giữ nhịp cảnh ngắn gọn 5s -> hậu kỳ cắt 3.0-3.8s, thêm thẻ bối cảnh nếu mở cảnh mới
                    shot_duration_s = 5.0
                    try:
                        target_trim_s = float(b.get("target_trim_duration_s", 3.5))
                    except (TypeError, ValueError):
                        target_trim_s = 3.5
                    if not 0.0 < target_trim_s <= shot_duration_s:
                        target_trim_s = 3.5
                    if source_action:
                        target_trim_s = shot_duration_s
                    shot_audio_mode = "SILENT_ACTION"
                    voiceover_text = None
                    if is_new_scene:
                        scene_card_overlay = f"{loc_name.upper()}"

                cast_clause = (
                    "Keep exact spatial positions of characters in frame as established in Image 1."
                    if is_multi
                    else "Only this character in frame, same cast and wardrobe as the reference."
                )
                dur_int = int(shot_duration_s)
                if allow_camera_motion:
                    cam_motion_clause = (
                        f"Controlled stabilized camera motion ({raw_cam_motion}) from fluid tripod rig of exactly {dur_int} seconds, "
                        f"the clip must end after {dur_int} seconds, in exactly 16:9 aspect ratio: "
                        f"smooth continuous {raw_cam_motion} with zero jitter, zero whip-pan, and zero abrupt zoom."
                    )
                else:
                    cam_motion_clause = (
                        f"Locked-off static tripod shot of exactly {dur_int} seconds, the clip must end after {dur_int} seconds, in exactly 16:9 aspect ratio: "
                        f"the camera does not move, pan, tilt or zoom, and framing stays identical from first frame to last."
                    )

                if state_insert:
                    opening = f"Image 1 is the exact first frame of the shot, {framing}, on the stationary prop. "
                    subject = prop_notes
                    timeline = "Hold on this state for the full take. Keep the prop in the same position and orientation. "
                    cast_clause = "Keep all people, hands and faces out of frame."
                elif source_action:
                    opening = f"Image 1 is the exact first frame of the shot, {framing}. "
                    subject = f"{prop_notes} Preserve the visible performer and wardrobe from Image 1."
                    timeline = (
                        f"Opening state: {stage['before_state']}. "
                        f"One continuous action: {action_safe.rstrip('.')}."
                        f" Closing state: {stage['after_state']}. "
                        "Any visible hand has five distinct fingers, no fused or extra digits. "
                    )
                    cast_clause = "Keep the prop and the acting hands in frame and all faces out of frame."
                elif is_prop_insert:
                    opening = f"Image 1 is the exact first frame of the shot, {framing}, showing only the hand and prop. "
                    timeline = (
                        "[0-0.5s] Keep the hand hovering with a visible air gap above the prop, without touching it. "
                        f"[0.5-1.5s] {action_safe} "
                        f"[1.5-{dur_int}s] The hand settles and the prop stays in the same position. "
                        "The visible hand has five distinct fingers, no fused or extra digits. "
                    )
                    subject = f"Subject: The prop and one hand with the wardrobe sleeve matching Image 1. {prop_notes}"
                    cast_clause = "Keep all faces out of frame for the entire take."
                else:
                    opening = f"Image 1 is the exact first frame of the shot, {framing}, {locked_gaze}. "
                    silence_clause = (
                        "No words and no speech sound; any mouth movement stays silent."
                        if mouth_action
                        else "Lips remain completely closed, no speaking, no lip movement."
                    )
                    hold_clause = (
                        f"Hold the exact opening state of image 1: {opening_state.rstrip('.')}."
                        if opening_state
                        else "Hold exact opening posture and gaze, lips completely closed."
                    )
                    timeline = (
                        f"[0-0.5s] {hold_clause} "
                        f"[0.5-{dur_int - 0.5:.1f}s] {action_safe} {silence_clause} {hand_clause} "
                        f"[{dur_int - 0.5:.1f}-{dur_int}s] Posture settles naturally. No head nodding or shaking. "
                    )
                    subject = f"Subject: {char_desc_punct} {prop_notes}"

                prompt = (
                    f"{opening}"
                    f"Start exactly from image 1. {cam_motion_clause} "
                    f"Single continuous unedited take, zero scene cuts, zero camera angle changes. "
                    f"Visual style: {visual_style}. {cinema_extra_str} "
                    f"Setting ({loc_name}): {loc_desc}. {set_facts_str} "
                    f"{subject} {timeline}"
                    f"Sound design: {ambient}, no background music, no speech. "
                    f"{cast_clause} "
                    f"No new lettering. No on-screen text, subtitles, watermarks, or logos. Nobody looks into the lens."
                ).strip()

            # Làm sạch khoảng trắng thừa
            prompt = re.sub(r"\s+", " ", prompt)

            # Xác định keyframe key chống va chạm đa nhân vật / phục trang theo hồi / góc đặt máy / flashback
            framing_slug = re.sub(r"[^a-z0-9]+", "_", framing.lower()).strip("_")
            other_cids_for_kf = [c for c in chars_present if c != primary_cid]
            cast_slug = f"{primary_cid}_{other_cids_for_kf[0]}" if (is_multi and other_cids_for_kf) else (primary_cid or "prop_only")
            ctx_parts: List[str] = []
            if wardrobe:
                w_slug = re.sub(r"[^a-z0-9]+", "_", wardrobe.lower()).strip("_")[:18].strip("_")
                if w_slug:
                    ctx_parts.append(f"w_{w_slug}")
            if camera_angle and camera_angle.lower() not in ("eye-level", "eye level", "neutral"):
                a_slug = re.sub(r"[^a-z0-9]+", "_", camera_angle.lower()).strip("_")[:14].strip("_")
                if a_slug:
                    ctx_parts.append(f"ang_{a_slug}")
            if is_flashback:
                ctx_parts.append("fb")
            if shot_role == "insert" or "insert" in framing.lower():
                ctx_parts.append(f"ins{idx:03d}")
            if stage:
                ctx_parts.append(f"st_{stage['fingerprint']}")
            if opening_state:
                # os2_ on two-shots: older two-shot stills under os_ were drawn without the opening state.
                os_tag = "os2_" if is_multi else "os_"
                ctx_parts.append(os_tag + hashlib.sha256(opening_state.encode("utf-8")).hexdigest()[:8])
            ctx_suffix = ("__" + "__".join(ctx_parts)) if ctx_parts else ""
            kf_key = f"{loc_id}__{framing_slug}__{cast_slug}{ctx_suffix}__{prop_tag}"

            anchor_file = primary_char.get("anchor_image", "")
            if keyframes_map and shot_id in keyframes_map:
                resolved_first_frame = keyframes_map[shot_id]
            elif keyframes_map and kf_key in keyframes_map:
                resolved_first_frame = keyframes_map[kf_key]
            elif is_prop_insert:
                resolved_first_frame = ""
            elif anchors_dir and anchor_file:
                cand = anchors_dir / Path(anchor_file).name
                resolved_first_frame = str(cand)
            else:
                resolved_first_frame = anchor_file

            # Thu thập ảnh tham chiếu phụ (nhân vật thứ 2 trong OTS/Two-Shot + Master Location Plate nếu có)
            extra_refs: List[str] = []
            if anchors_dir and is_multi and other_cids_for_kf:
                sec_anchor = (char_map.get(other_cids_for_kf[0]) or {}).get("anchor_image")
                if sec_anchor:
                    sec_p = anchors_dir / Path(sec_anchor).name
                    if sec_p.exists() and str(sec_p) != str(resolved_first_frame):
                        extra_refs.append(str(sec_p))
            if anchors_dir:
                plate_cand = anchors_dir.parent / "setups" / f"{loc_id}__master_plate.png"
                if plate_cand.exists() and str(plate_cand) != str(resolved_first_frame):
                    extra_refs.append(str(plate_cand))

            is_climax = (
                "Close-up" in framing or "Extreme Close-up" in framing
            ) and bool(dialogue) and (len(dialogue) >= 40 or dialogue.rstrip().endswith("!"))

            post_cam_motion = cls._resolve_post_camera_motion(
                beat=b,
                framing=framing,
                is_climax=is_climax,
                allow_native_motion=allow_camera_motion,
                raw_cam_motion=raw_cam_motion,
                shot_idx=idx,
            )

            cam_base = f"Controlled {raw_cam_motion}" if allow_camera_motion else "Locked-off static tripod"
            angle_label = camera_angle or "eye-level"
            lens_label = f", {lens_clean or resolved_lens_mm}mm"
            camera_desc = f"{cam_base}, {angle_label}{lens_label}, 16:9"

            shots.append({
                "shot_id": shot_id,
                "order": idx,
                "beat_id": beat_id,
                "chapter_id": chapter_id,
                "location": loc_id,
                "location_name": loc_name,
                "characters_present": chars_present,
                "primary_character_id": primary_cid,
                "duration_s": shot_duration_s,
                "target_trim_duration_s": target_trim_s,
                "framing": framing,
                "shot_role": shot_role,
                "is_multi_person": is_multi,
                "is_climax_closeup": is_climax,
                "camera": camera_desc,
                "camera_motion": raw_cam_motion if allow_camera_motion else "static",
                "post_camera_motion": post_cam_motion,
                "allow_camera_motion": allow_camera_motion,
                "lens_mm": int(lens_clean) if (lens_clean and lens_clean.isdigit()) else (lens_raw or resolved_lens_mm),
                "camera_angle": camera_angle,
                "foreground_element": foreground_elem or None,
                "subtext": subtext_note or None,
                "wardrobe_resolved": wardrobe or None,
                "lighting_mood": lighting_mood,
                "is_flashback": is_flashback,
                "color_mood": color_mood,
                "transition_in": transition_in,
                "gaze": locked_gaze,
                "speaker": speaker,
                "dialogue": dialogue,
                "narration": narration,
                "voiceover_text": voiceover_text,
                "audio_mode": shot_audio_mode,
                "scene_card_overlay": scene_card_overlay,
                "action_summary": action_safe,
                "keyframe_key": kf_key,
                "anchor_ref": Path(anchor_file).name if anchor_file else "",
                "first_frame_path": resolved_first_frame,
                "extra_refs": extra_refs,
                "source_start_s": b.get("source_start_s"),
                "source_end_s": b.get("source_end_s"),
                "source_reference": b.get("source_reference"),
                "compiled_prompt": prompt,
            })
            if cutaway_type:
                shots[-1]["cutaway_type"] = cutaway_type
            if is_prop_insert:
                shots[-1]["prop_continuity"] = prop_notes
            if stage:
                shots[-1]["staging"] = stage
            if dialogue_timing:
                shots[-1]["dialogue_timing"] = dialogue_timing
            if opening_state:
                shots[-1]["opening_state"] = opening_state

            prev_chapter = chapter_id
            prev_location = loc_id

        coverage_warnings = cls.audit_coverage(shots, bible=bible)
        coverage_warnings.extend(
            f"DIALOGUE_OVER_CAPACITY ({s['shot_id']}): ~{s['dialogue_timing']['est_speech_s']}s estimated speech "
            f"exceeds {s['dialogue_timing']['capacity_s']}s; split the line at a sentence boundary before render."
            for s in shots if (s.get("dialogue_timing") or {}).get("status") == "OVER_CAPACITY"
        )
        coverage_warnings.extend(
            f"STAGING_{row['outcome'].upper()} ({row['source_beat_id']}): {row['reason']}"
            for row in staging_review if row["outcome"] == "invalid"
        )
        return {
            "project_title": bible.get("project_title", "AI Film Project"),
            "audio_mode": audio_mode,
            "total_shots": len(shots),
            "target_duration_s": sum(s["duration_s"] for s in shots),
            "bible_warnings": bible_errors,
            "coverage_warnings": coverage_warnings,
            "staging_review": staging_review,
            "shots": shots,
        }

    @classmethod
    def audit_coverage(cls, shots: List[Dict[str, Any]], bible: Optional[Dict[str, Any]] = None) -> List[str]:
        """Kiểm tra độ phủ góc máy theo từng chương, ping-pong hội thoại (D2) & chi tiết bắt buộc must_show (D6)."""
        warnings: List[str] = []
        by_ch: Dict[str, List[Dict[str, Any]]] = {}
        for s in shots:
            by_ch.setdefault(s["chapter_id"], []).append(s)

        for ch, ch_shots in by_ch.items():
            has_establishing = any(
                "wide" in s["framing"].lower() or s.get("is_multi_person") for s in ch_shots
            )
            if not has_establishing:
                warnings.append(f"{ch}: Thiếu Wide Shot hoặc Two-Shot thiết lập không gian.")

            # D2: Dialogue Ping-Pong warning
            dlg_shots = [s for s in ch_shots if (s.get("dialogue") or "").strip()]
            dlg_speakers = {
                (s.get("speaker") or s.get("primary_character_id") or "").strip().lower()
                for s in dlg_shots
                if (s.get("speaker") or s.get("primary_character_id") or "").strip()
            }
            has_multi_shot = any(bool(s.get("is_multi_person")) for s in ch_shots)
            if len(dlg_shots) >= 3 and len(dlg_speakers) >= 2 and not has_multi_shot:
                warnings.append(
                    f"{ch}: Cảnh hội thoại đa nhân vật thiếu góc chung (Two-Shot/OTS) để neo trục không gian."
                )

            consec_cu = 0
            prev_ch_shot: Optional[Dict[str, Any]] = None
            for s in ch_shots:
                f_low = (s.get("framing") or "").lower()
                is_tight_cu = ("close-up" in f_low or "closeup" in f_low) and ("medium" not in f_low)
                if is_tight_cu:
                    consec_cu += 1
                    if consec_cu > 2:
                        warnings.append(
                            f"{ch} ({s['shot_id']}): Quá 2 shot cận cảnh đặc tả (Close-up) liên tiếp ({consec_cu}) — gây ngộp thị giác."
                        )
                elif "close" in f_low:
                    # Medium Close-up: cảnh báo nếu chuỗi MCU + CU kéo dài quá 3 shot liên tiếp
                    consec_cu += 1
                    if consec_cu > 3:
                        warnings.append(
                            f"{ch} ({s['shot_id']}): Quá 3 shot cận/cận vừa liên tiếp ({consec_cu}) — cần chèn Medium/OTS/Wide giải phóng không gian."
                        )
                else:
                    consec_cu = 0

                # Quy tắc 30 độ / Chống Jump-Cut cùng nhân vật + cùng cỡ cảnh + cùng góc máy
                if prev_ch_shot is not None:
                    same_loc = (s.get("location") or "") == (prev_ch_shot.get("location") or "")
                    same_char = (
                        bool(s.get("primary_character_id"))
                        and s.get("primary_character_id") == prev_ch_shot.get("primary_character_id")
                        and not s.get("is_multi_person")
                        and not prev_ch_shot.get("is_multi_person")
                    )
                    same_scale = (s.get("framing") or "").strip().lower() == (prev_ch_shot.get("framing") or "").strip().lower()
                    same_angle = (s.get("camera_angle") or "eye-level").strip().lower() == (prev_ch_shot.get("camera_angle") or "eye-level").strip().lower()
                    if same_loc and same_char and same_scale and same_angle:
                        warnings.append(
                            f"JUMP_CUT_30_DEG_WARNING ({ch}, {prev_ch_shot['shot_id']} -> {s['shot_id']}): "
                            f"Cùng nhân vật {s.get('primary_character_id')} giữ nguyên '{s.get('framing')}' liên tiếp — cần đổi cỡ cảnh hoặc góc máy >= 30°."
                        )
                prev_ch_shot = s

        # Ngân sách cỡ cảnh toàn phim (Pyramid Shot-Scale Budget) khi phim có >= 6 shots
        if len(shots) >= 6:
            tight_cu_cnt = sum(
                1 for s in shots
                if ("close" in (s.get("framing") or "").lower()) and ("medium" not in (s.get("framing") or "").lower())
            )
            all_cu_cnt = sum(1 for s in shots if "close" in (s.get("framing") or "").lower())
            if tight_cu_cnt / len(shots) > 0.30:
                warnings.append(
                    f"CLOSEUP_BUDGET_EXCEEDED: Tỷ lệ Close-up đặc tả chiếm {tight_cu_cnt}/{len(shots)} ({tight_cu_cnt * 100 // len(shots)}% > 30%)."
                )
            if all_cu_cnt / len(shots) > 0.50:
                warnings.append(
                    f"MCU_CU_OVERLOAD: Tổng MCU + Close-up chiếm {all_cu_cnt}/{len(shots)} ({all_cu_cnt * 100 // len(shots)}% > 50%) — thiếu trung cảnh/OTS/toàn cảnh."
                )

        # D6: must_show Plant/Payoff warning
        for item in (bible or {}).get("must_show", []) or []:
            if isinstance(item, str):
                item = {"what": item}
            if not isinstance(item, dict):
                continue
            what = str(item.get("what") or item.get("description") or "").strip()
            if not what:
                continue
            ch_scope = str(item.get("chapter_id") or "").strip() or None
            if ch_scope:
                scope_shots = [
                    s for s in shots
                    if s.get("chapter_id") == ch_scope
                    or cls._match_window_key(ch_scope, chapter_id=s.get("chapter_id"), beat_id=None)[1]
                ]
            else:
                scope_shots = shots

            explicit_kws = [str(k).strip().lower() for k in (item.get("keywords") or []) if str(k).strip()]
            if explicit_kws:
                terms = explicit_kws
            else:
                terms = [
                    tok
                    for tok in re.findall(r"[\w]+", what.lower())
                    if len(tok) >= 3 and tok not in cls.MUST_SHOW_STOPWORDS
                ] or [what.lower()]

            covered = False
            for s in scope_shots:
                haystack = f"{s.get('action_summary') or ''} {s.get('compiled_prompt') or ''}".lower()
                if any(
                    (t in haystack) if (" " in t) else bool(re.search(rf"\b{re.escape(t)}(?:es|s)?\b", haystack))
                    for t in terms
                ):
                    covered = True
                    break

            if not covered:
                warnings.append(
                    f"MUST_SHOW_UNCOVERED ({ch_scope or 'GLOBAL'}): Chưa có shot hiển thị chi tiết '{what}'."
                )

        return warnings

    @classmethod
    def compile_project_dir(
        cls,
        project_dir: Path,
        story_bible_path: Optional[Path] = None,
        beats_path: Optional[Path] = None,
        audio_mode: str = "native_drama",
        strict_bible: bool = True,
        cinematic_cutaways: bool = False,
    ) -> Tuple[Path, Path, Dict[str, Any]]:
        """Biên dịch từ thư mục dự án, lưu `shots_manifest.json` và `shots_manifest.csv`."""
        project_dir = Path(project_dir)
        sb_path = story_bible_path or (project_dir / "story_bible.json")
        canonical_beats = project_dir / "beats.json"
        if not beats_path and canonical_beats.is_file():
            beats_path = canonical_beats
        if not beats_path:
            candidates = sorted(project_dir.glob("*beats*.json"))
            chosen = None
            for cand in candidates:
                try:
                    parsed = json.loads(cand.read_text(encoding="utf-8"))
                    if (isinstance(parsed, list) and parsed) or (isinstance(parsed, dict) and isinstance(parsed.get("beats"), list) and parsed["beats"]):
                        chosen = cand
                        break
                except Exception:
                    continue
            if not chosen:
                raise FileNotFoundError(f"Không tìm thấy file beats JSON chứa danh sách beats trong {project_dir}")
            beats_path = chosen

        bible = json.loads(Path(sb_path).read_text(encoding="utf-8"))
        raw_beats = json.loads(Path(beats_path).read_text(encoding="utf-8"))
        beats = raw_beats if isinstance(raw_beats, list) else raw_beats.get("beats", [])

        anchors_dir = project_dir / "assets" / "anchors"
        kf_index_path = project_dir / "assets" / "keyframes" / "keyframes_index.json"
        keyframes_map = None
        if kf_index_path.exists():
            keyframes_map = json.loads(kf_index_path.read_text(encoding="utf-8"))

        manifest = cls.compile_shots(
            bible=bible,
            beats=beats,
            audio_mode=audio_mode,
            anchors_dir=anchors_dir if anchors_dir.exists() else None,
            keyframes_map=keyframes_map,
            strict_bible=strict_bible,
            cinematic_cutaways=cinematic_cutaways,
        )

        json_out = project_dir / "shots_manifest.json"
        csv_out = project_dir / "shots_manifest.csv"
        json_out.write_text(json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8")

        with open(csv_out, "w", newline="", encoding="utf-8-sig") as f:
            writer = csv.writer(f)
            writer.writerow(["shot_id", "chapter_id", "speaker", "audio_mode", "text", "first_frame_path", "prompt"])
            for s in manifest["shots"]:
                writer.writerow([
                    s["shot_id"],
                    s["chapter_id"],
                    s.get("speaker") or "Narration",
                    s["audio_mode"],
                    s.get("dialogue") or s.get("narration") or "",
                    s.get("first_frame_path") or "",
                    s["compiled_prompt"],
                ])

        return json_out, csv_out, manifest
