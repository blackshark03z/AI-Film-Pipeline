"""
Zero-Talk Script / Prose / SRT Ingestor, Story Bible Synthesizer & DOP Staging Engine.
Chuyển đổi trực tiếp kịch bản thô (.txt, .md, .fountain, .srt) thành:
  1. `story_bible.json` (khóa duy nhất `anchor_image`, `look_verbatim`, `axis_gaze` 180°, `set_facts`, `props_ledger`)
  2. `beats.json` (dàn dựng sẵn cỡ cảnh theo Ngữ pháp Điện ảnh DOP: mở cảnh bằng Wide/Two-Shot,
     luân phiên OTS / Medium / Medium Close-up, giới hạn Close-up liên tiếp <= 2, bảo toàn 100% lời thoại).
Hỗ trợ cả LLM (`google-genai` hoặc `llm_callable`) lẫn Local Deterministic Parser (offline / zero-talk).
"""

import json
import os
import re
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Set, Tuple

try:
    from .staging import plan_staging
    from .srt_diarizer import parse_srt
    from .srt_normalizer import SRTNormalizer
except ImportError:
    from core.staging import plan_staging
    from core.srt_diarizer import parse_srt
    from core.srt_normalizer import SRTNormalizer


DIRECTOR_PRESETS: Dict[str, Dict[str, Any]] = {
    "drama_35mm": {
        "audio_mode": "native_drama",
        "visual_style": (
            "cinematic photorealistic 35mm film, realistic motivated lighting, "
            "natural film grain, subdued realistic color palette, no CGI glow"
        ),
        "aspect_ratio": "16:9",
    },
    "thriller_noir": {
        "audio_mode": "native_drama",
        "visual_style": (
            "tense neo-noir photorealistic cinema, high-contrast tungsten and neon practicals, "
            "crisp 35mm depth of field, authentic skin texture, no artificial gloss"
        ),
        "aspect_ratio": "16:9",
    },
    "hybrid_docu": {
        "audio_mode": "hybrid_narrated",
        "visual_style": (
            "naturalistic documentary cinema, realistic daylight and practical interior lighting, "
            "grounded textures, zero CGI artifacts"
        ),
        "aspect_ratio": "16:9",
    },
}


class ScriptIngestor:
    """Đọc kịch bản/văn xuôi/SRT và tổng hợp `story_bible.json` + `beats.json` đạt chuẩn Preflight."""

    SCENE_HEADING_RE = re.compile(
        r"^\s*(?:(?:#{1,3}\s*)?(?:SCENE\s+\d+\s*[:\-–]\s*)?)"
        r"((?:INT\.|EXT\.|INT/EXT\.|I/E\.)\s*.+?)\s*$",
        re.IGNORECASE,
    )
    TITLE_RE = re.compile(r"^\s*(?:TITLE\s*:\s*|#\s+)(.+?)\s*$", re.IGNORECASE)
    COLON_SPEAKER_RE = re.compile(r"^\s*([A-Z][A-Z0-9 _\-\.]{1,28})\s*:\s*(.+?)\s*$")
    CUED_NAME_STOPWORDS = {
        "INT", "EXT", "NIGHT", "DAY", "DAWN", "DUSK", "MORNING", "EVENING",
        "CUT TO", "FADE IN", "FADE OUT", "DISSOLVE TO", "TITLE", "THE END",
        "CONTINUOUS", "LATER", "MOMENTS LATER",
    }

    WARDROBE_ARCHETYPES = [
        ("officer", "dark navy police uniform shirt with metallic badge, neat utility belt"),
        ("captain", "crisp white commercial airline captain shirt with four gold shoulder stripes and dark tie"),
        ("pilot", "crisp aviation uniform shirt with gold epaulets and navy blazer"),
        ("first officer", "crisp white pilot shirt with three gold stripes and dark navy tie"),
        ("doctor", "clean white medical coat over slate-blue clinical scrubs"),
        ("detective", "charcoal wool coat over a muted collared shirt and dark tie"),
    ]

    PROP_HINTS = [
        ("pin", "PROP_SILVER_PIN", "aged sterling silver military pin with four polished stars"),
        ("badge", "PROP_METAL_BADGE", "official metallic identification badge in leather holder"),
        ("phone", "PROP_SMARTPHONE", "matte black smartphone held firmly in palm"),
        ("tablet", "PROP_DISPATCH_TABLET", "rugged black flight dispatch tablet"),
        ("throttle", "PROP_THROTTLE_QUADRANT", "commercial cockpit twin-engine throttle lever console"),
        ("intercom", "PROP_CABIN_INTERCOM", "wall-mounted gray cabin intercom handset"),
    ]

    @staticmethod
    def _slug(text: str, prefix: str = "", max_len: int = 28) -> str:
        clean = re.sub(r"[^a-zA-Z0-9]+", "_", (text or "").strip()).strip("_").upper()
        if not clean:
            clean = "DEFAULT"
        clean = clean[:max_len].strip("_")
        return f"{prefix}_{clean}" if prefix else clean

    @classmethod
    def _infer_char_profile(cls, raw_name: str, idx: int, context_text: str = "") -> Dict[str, Any]:
        clean_name = re.sub(r"\s*\(.*?\)\s*", "", raw_name or "").strip()
        title_name = clean_name.title() if clean_name.isupper() else clean_name
        cid = cls._slug(title_name, "CHAR")
        anchor_stem = re.sub(r"[^a-z0-9]+", "_", title_name.lower()).strip("_") or f"char_{idx + 1}"
        gaze = "looking screen-right" if idx % 2 == 0 else "looking screen-left"

        low_ctx = f"{title_name} {context_text}".lower()
        wardrobe = (
            "dark olive canvas utility jacket over a muted henley shirt"
            if idx % 2 == 0
            else "structured charcoal blazer over a crispslate button-down shirt"
        )
        for kw, w_desc in cls.WARDROBE_ARCHETYPES:
            if kw in low_ctx:
                wardrobe = w_desc
                break

        age = 52 if idx == 0 else (34 if idx == 1 else 40 + (idx * 5) % 20)
        female_hints = ("brianna", "bri", "alice", "sarah", "valerie", "patrice", "elena", "maya", "she", "her", "wife", "woman")
        is_female = any(re.search(rf"\b{h}\b", low_ctx) for h in female_hints[:8])
        gender = "female" if is_female else "male"
        noun = "woman" if is_female else "man"
        hair = "neatly styled dark hair" if is_female else ("short salt-and-pepper hair" if age >= 48 else "short neat dark hair")

        look_verbatim = (
            f"A {age}-year-old realistic {noun} ({title_name}) with natural skin texture, "
            f"composed expressive eyes, {hair}, wearing {wardrobe}, grounded natural posture"
        )
        voice_profile = (
            "calm, clear, measured English voice"
            if idx % 2 == 0
            else "crisp, grounded, natural English voice"
        )
        return {
            "id": cid,
            "name": title_name,
            "age": age,
            "gender": gender,
            "look_verbatim": look_verbatim,
            "voice_profile": voice_profile,
            "anchor_image": f"{anchor_stem}.png",
            "axis_gaze": gaze,
        }

    @classmethod
    def _infer_location_profile(cls, heading: str, context_text: str = "") -> Dict[str, Any]:
        raw = (heading or "INTERIOR ROOM - NIGHT").strip()
        tod = "night" if "NIGHT" in raw.upper() else ("dawn" if "DAWN" in raw.upper() else "day")
        is_ext = raw.upper().startswith("EXT")
        base_name = re.sub(r"^(?:INT\.|EXT\.|INT/EXT\.|I/E\.)\s*", "", raw, flags=re.IGNORECASE)
        base_name = re.sub(r"\s*[-–]\s*(?:DAY|NIGHT|DAWN|DUSK|MORNING|EVENING|CONTINUOUS|LATER).*$", "", base_name, flags=re.IGNORECASE).strip()
        if not base_name:
            base_name = "Primary Scene Location"
        lid = cls._slug(base_name, "LOC")

        space_kind = "realistic urban exterior environment" if is_ext else "realistic architectural interior room"
        lighting = (
            "practical warm tungsten and muted fluorescent night lighting"
            if tod == "night"
            else ("cool early dawn sky and soft practical lighting" if tod == "dawn" else "natural diffused daylight")
        )
        ctx_snippet = re.sub(r"\s+", " ", (context_text or "").strip())[:140]
        look_verbatim = (
            f"{space_kind} ({base_name.title()}) during {tod}, {lighting}, "
            f"grounded lived-in surfaces and realistic depth"
            + (f", featuring {ctx_snippet}" if ctx_snippet and len(ctx_snippet) > 15 else "")
        )
        return {
            "id": lid,
            "name": base_name.title(),
            "look_verbatim": look_verbatim,
            "time_of_day_lock": tod,
            "set_facts": [
                f"Consistent spatial geometry across all angles inside {base_name.title()}",
                "Primary characters remain on locked sides of the 180-degree camera axis",
            ],
        }

    @staticmethod
    def _split_long_dialogue(text: str, max_words: int = 26) -> List[str]:
        cleaned = re.sub(r"\s+", " ", (text or "").strip()).strip('"“”')
        words = cleaned.split()
        if len(words) <= max_words:
            return [cleaned] if cleaned else []

        sentences = [s.strip() for s in re.split(r"(?<=[.!?])\s+", cleaned) if s.strip()]
        if len(sentences) <= 1:
            chunks = []
            for i in range(0, len(words), max_words):
                chunks.append(" ".join(words[i : i + max_words]))
            return chunks

        grouped: List[str] = []
        buf: List[str] = []
        buf_count = 0
        for sent in sentences:
            wc = len(sent.split())
            if buf and (buf_count + wc > max_words):
                grouped.append(" ".join(buf))
                buf = [sent]
                buf_count = wc
            else:
                buf.append(sent)
                buf_count += wc
        if buf:
            grouped.append(" ".join(buf))
        return grouped

    @classmethod
    def _parse_text_or_screenplay(cls, raw_text: str, default_title: str) -> Tuple[Dict[str, Any], List[str]]:
        """Phân tích kịch bản Fountain / Hội thoại dấu hai chấm / Văn xuôi có lời thoại trong ngoặc kép."""
        lines = raw_text.splitlines()
        project_title = default_title
        extracted_source_dialogues: List[str] = []

        scenes: List[Dict[str, Any]] = []
        current_scene = {
            "chapter_id": "CH01",
            "heading": "INT. MAIN SETTING - NIGHT",
            "events": [],
            "desc_hint": "",
        }
        scenes.append(current_scene)
        scene_counter = 1

        i = 0
        n = len(lines)
        while i < n:
            line = lines[i].strip()
            if not line:
                i += 1
                continue

            m_title = cls.TITLE_RE.match(line)
            if m_title and i < 5:
                project_title = m_title.group(1).strip()
                i += 1
                continue

            m_scene = cls.SCENE_HEADING_RE.match(line)
            if m_scene:
                heading = m_scene.group(1).strip()
                if current_scene["events"]:
                    scene_counter += 1
                    current_scene = {
                        "chapter_id": f"CH{scene_counter:02d}",
                        "heading": heading,
                        "events": [],
                        "desc_hint": "",
                    }
                    scenes.append(current_scene)
                else:
                    current_scene["heading"] = heading
                i += 1
                continue

            # Dạng 1: SPEAKER: Dialogue trên 1 dòng
            m_colon = cls.COLON_SPEAKER_RE.match(line)
            if m_colon and m_colon.group(1).strip().upper() not in cls.CUED_NAME_STOPWORDS:
                spk = re.sub(r"\s*\(.*?\)\s*", "", m_colon.group(1)).strip()
                dlg = m_colon.group(2).strip().strip('"“”')
                extracted_source_dialogues.append(dlg)
                for part in cls._split_long_dialogue(dlg):
                    current_scene["events"].append({
                        "type": "dialogue",
                        "speaker": spk,
                        "dialogue": part,
                        "action": f"{spk.title()} speaks with composed focus.",
                    })
                i += 1
                continue

            # Dạng 2: Fountain / Screenplay cue (Dòng tên IN HOA ngắn, dòng kế tiếp là thoại)
            cue_clean = re.sub(r"\s*\(.*?\)\s*$", "", line).strip()
            is_upper_cue = (
                1 <= len(cue_clean.split()) <= 4
                and len(cue_clean) <= 28
                and cue_clean.isupper()
                and re.search(r"[A-Z]", cue_clean) is not None
                and not cue_clean.endswith((".", "!", "?", ":"))
                and cue_clean not in cls.CUED_NAME_STOPWORDS
                and i + 1 < n
                and bool(lines[i + 1].strip())
            )
            if is_upper_cue:
                spk = cue_clean
                i += 1
                parenthetical = ""
                dlg_parts: List[str] = []
                while i < n and lines[i].strip():
                    sub_l = lines[i].strip()
                    if cls.SCENE_HEADING_RE.match(sub_l):
                        break
                    if sub_l.startswith("(") and sub_l.endswith(")"):
                        parenthetical = sub_l.strip("() ").strip()
                    else:
                        dlg_parts.append(sub_l.strip('"“”'))
                    i += 1
                full_dlg = " ".join(dlg_parts).strip()
                if full_dlg:
                    extracted_source_dialogues.append(full_dlg)
                    act_note = (
                        f"{spk.title()} speaks ({parenthetical})."
                        if parenthetical
                        else f"{spk.title()} delivers the line steadily."
                    )
                    for part in cls._split_long_dialogue(full_dlg):
                        current_scene["events"].append({
                            "type": "dialogue",
                            "speaker": spk,
                            "dialogue": part,
                            "action": act_note,
                        })
                continue

            # Dạng 3: Đoạn văn xuôi (có thể chứa lời thoại trong dấu ngoặc kép "..." hoặc hành động thuần)
            para_lines = [line]
            i += 1
            while i < n and lines[i].strip():
                nxt = lines[i].strip()
                if cls.SCENE_HEADING_RE.match(nxt) or cls.COLON_SPEAKER_RE.match(nxt):
                    break
                nxt_cue = re.sub(r"\s*\(.*?\)\s*$", "", nxt).strip()
                if (
                    1 <= len(nxt_cue.split()) <= 4
                    and nxt_cue.isupper()
                    and nxt_cue not in cls.CUED_NAME_STOPWORDS
                    and i + 1 < n
                    and bool(lines[i + 1].strip())
                ):
                    break
                para_lines.append(nxt)
                i += 1

            paragraph = " ".join(para_lines).strip()
            if not current_scene["desc_hint"]:
                current_scene["desc_hint"] = paragraph

            # Tìm các đoạn trích dẫn "..." trong đoạn văn xuôi
            quote_matches = list(re.finditer(r'["“]([^"”]{2,})["”]', paragraph))
            if quote_matches:
                last_end = 0
                for qm in quote_matches:
                    before_txt = paragraph[last_end : qm.start()].strip()
                    after_txt = paragraph[qm.end() : min(len(paragraph), qm.end() + 90)].strip()
                    spoken_txt = qm.group(1).strip()
                    extracted_source_dialogues.append(spoken_txt)

                    # Suy luận người nói từ văn cảnh ngay sau hoặc ngay trước dấu ngoặc kép
                    spk = cls._guess_prose_speaker(before_txt, after_txt)
                    act_context = before_txt if len(before_txt) > 12 else (after_txt or f"{spk} speaks calmly.")
                    for part in cls._split_long_dialogue(spoken_txt):
                        current_scene["events"].append({
                            "type": "dialogue",
                            "speaker": spk,
                            "dialogue": part,
                            "action": act_context,
                        })
                    last_end = qm.end()
            else:
                current_scene["events"].append({
                    "type": "action",
                    "speaker": None,
                    "dialogue": None,
                    "narration": paragraph,
                    "action": paragraph,
                })

        raw_struct = cls._assemble_raw_structure_from_scenes(project_title, scenes, raw_text)
        return raw_struct, extracted_source_dialogues

    @staticmethod
    def _guess_prose_speaker(before_txt: str, after_txt: str) -> str:
        speech_verbs = r"(?:said|asked|replied|whispered|answered|murmured|called|added|told|spoke)"
        m_after = re.search(
            rf"^\s*(?:,\s*)?(?:(?:Captain|Officer|First Officer|Detective|Doctor|Dr\.)\s+)?([A-Z][a-zA-Z0-9_\-]+)\s+{speech_verbs}\b",
            after_txt,
        )
        if m_after:
            return m_after.group(1)
        m_after_inv = re.search(
            rf"^\s*(?:,\s*)?{speech_verbs}\s+(?:(?:Captain|Officer|First Officer|Detective|Doctor|Dr\.)\s+)?([A-Z][a-zA-Z0-9_\-]+)\b",
            after_txt,
        )
        if m_after_inv:
            return m_after_inv.group(1)
        # Tìm tên riêng cuối cùng ở mệnh đề phía trước
        proper_before = re.findall(
            r"\b(?:Captain|Officer|First Officer|Detective|Doctor)?\s*([A-Z][a-z]{2,20})\b",
            before_txt,
        )
        filtered = [
            p for p in proper_before
            if p.upper() not in {"INSIDE", "OUTSIDE", "THE", "WHEN", "THEN", "AFTER", "BEFORE", "WHILE", "DAWN", "NIGHT"}
        ]
        if filtered:
            return filtered[-1]
        return "PROTAGONIST"

    @classmethod
    def _assemble_raw_structure_from_scenes(
        cls,
        project_title: str,
        scenes: List[Dict[str, Any]],
        full_text: str,
    ) -> Dict[str, Any]:
        # Thu thập danh sách nhân vật xuất hiện
        speaker_order: List[str] = []
        for sc in scenes:
            for ev in sc["events"]:
                spk = ev.get("speaker")
                if spk:
                    norm = spk.strip().upper()
                    if norm not in speaker_order:
                        speaker_order.append(norm)

        # Tìm thêm nhân vật được nhắc tên trong phần mô tả nếu mới có < 2 nhân vật
        if len(speaker_order) < 2:
            titled = re.findall(r"\b(?:Officer|Captain|Detective|Doctor)\s+([A-Z][a-z]{2,18})\b", full_text)
            for t in titled:
                if t.upper() not in speaker_order:
                    speaker_order.append(t.upper())
        if not speaker_order:
            speaker_order.append("PROTAGONIST")

        characters: List[Dict[str, Any]] = []
        spk_to_cid: Dict[str, str] = {}
        for idx, spk_key in enumerate(speaker_order):
            prof = cls._infer_char_profile(spk_key, idx, context_text=full_text)
            characters.append(prof)
            spk_to_cid[spk_key] = prof["id"]

        locations: List[Dict[str, Any]] = []
        seen_locs: Dict[str, Dict[str, Any]] = {}
        beats: List[Dict[str, Any]] = []
        beat_idx = 0

        for sc in scenes:
            if not sc["events"]:
                continue
            loc_prof = cls._infer_location_profile(sc["heading"], sc.get("desc_hint", ""))
            lid = loc_prof["id"]
            if lid not in seen_locs:
                seen_locs[lid] = loc_prof
                locations.append(loc_prof)

            # Xác định các nhân vật có mặt trong cảnh này
            scene_cids: List[str] = []
            sc_blob = " ".join(
                f"{e.get('speaker') or ''} {e.get('action') or ''} {e.get('dialogue') or ''}"
                for e in sc["events"]
            ).lower()
            for ch in characters:
                if ch["name"].lower() in sc_blob or ch["id"].replace("CHAR_", "").lower() in sc_blob:
                    scene_cids.append(ch["id"])
            if not scene_cids:
                scene_cids = [characters[0]["id"]]

            for ev in sc["events"]:
                beat_idx += 1
                spk = ev.get("speaker")
                primary_cid = spk_to_cid.get(spk.strip().upper(), scene_cids[0]) if spk else scene_cids[0]
                ordered_present = [primary_cid] + [c for c in scene_cids if c != primary_cid]
                beats.append({
                    "beat_id": f"B{beat_idx:03d}",
                    "chapter_id": sc["chapter_id"],
                    "location": lid,
                    "speaker": spk.title() if spk else None,
                    "characters_present": ordered_present,
                    "action_summary": ev.get("action") or "Character holds steady composure in the scene.",
                    "dialogue": ev.get("dialogue"),
                    "narration": ev.get("narration"),
                })

        # Trích xuất đạo cụ nổi bật
        props_ledger: List[Dict[str, Any]] = []
        low_full = full_text.lower()
        for kw, pid, pdesc in cls.PROP_HINTS:
            if re.search(rf"\b{kw}s?\b", low_full):
                props_ledger.append({
                    "id": pid,
                    "description": pdesc,
                    "state_tracking": {"CH01-CH99": f"{pdesc} kept consistent across continuity"},
                })

        return {
            "project_title": project_title,
            "characters": characters,
            "locations": locations,
            "props_ledger": props_ledger,
            "beats": beats,
        }

    @classmethod
    def _parse_srt_input(cls, srt_path: Path, chapters_path: Optional[Path] = None) -> Tuple[Dict[str, Any], List[str]]:
        cues = SRTNormalizer.clean_srt_cues(parse_srt(srt_path), strip_youtube_cta=True)
        total_dur = max((c.end_s for c in cues), default=10.0)
        chapters = SRTNormalizer.parse_chapters_file(chapters_path, total_duration_s=total_dur)

        speakers_seen: List[str] = []
        parsed_turns: List[Dict[str, Any]] = []
        extracted_dialogues: List[str] = []

        for c in cues:
            txt = c.text.strip()
            if not txt:
                continue
            m_spk = cls.COLON_SPEAKER_RE.match(txt)
            if m_spk:
                spk = m_spk.group(1).strip().upper()
                dlg = m_spk.group(2).strip().strip('"“”')
            else:
                spk = "PROTAGONIST"
                dlg = txt.strip('"“”')
            if spk not in speakers_seen:
                speakers_seen.append(spk)
            extracted_dialogues.append(dlg)

            ch_id = "CH01"
            for ch in chapters:
                if ch["start_s"] <= c.start_s <= max(ch["end_s"], c.start_s + 0.1):
                    ch_id = ch["chapter_id"]
                    break

            # Gộp cue liền kề cùng người nói nếu tổng thời lượng <= 8.5s và <= 24 từ
            if (
                parsed_turns
                and parsed_turns[-1]["speaker_key"] == spk
                and parsed_turns[-1]["chapter_id"] == ch_id
                and (c.end_s - parsed_turns[-1]["source_start_s"]) <= 8.5
                and len((parsed_turns[-1]["dialogue"] + " " + dlg).split()) <= 24
            ):
                parsed_turns[-1]["dialogue"] = f"{parsed_turns[-1]['dialogue']} {dlg}".strip()
                parsed_turns[-1]["source_end_s"] = round(c.end_s, 2)
            else:
                parsed_turns.append({
                    "speaker_key": spk,
                    "chapter_id": ch_id,
                    "dialogue": dlg,
                    "source_start_s": round(c.start_s, 2),
                    "source_end_s": round(c.end_s, 2),
                })

        if not speakers_seen:
            speakers_seen = ["PROTAGONIST"]

        full_blob = " ".join(t["dialogue"] for t in parsed_turns)
        characters = [
            cls._infer_char_profile(spk, idx, context_text=full_blob)
            for idx, spk in enumerate(speakers_seen)
        ]
        spk_to_cid = {spk: characters[idx]["id"] for idx, spk in enumerate(speakers_seen)}
        all_cids = [c["id"] for c in characters]

        loc = cls._infer_location_profile("INT. PRIMARY DRAMATIC SETTING - NIGHT", full_blob)
        beats: List[Dict[str, Any]] = []
        for idx, t in enumerate(parsed_turns, start=1):
            pcid = spk_to_cid[t["speaker_key"]]
            present = [pcid] + [c for c in all_cids if c != pcid]
            beats.append({
                "beat_id": f"B{idx:03d}",
                "chapter_id": t["chapter_id"],
                "location": loc["id"],
                "speaker": t["speaker_key"].title(),
                "characters_present": present,
                "action_summary": f"{t['speaker_key'].title()} speaks directly in the scene.",
                "dialogue": t["dialogue"],
                "narration": None,
                "source_start_s": t["source_start_s"],
                "source_end_s": t["source_end_s"],
            })

        return {
            "project_title": srt_path.stem.replace("_", " ").title(),
            "source_srt_path": str(srt_path.resolve()),
            "characters": characters,
            "locations": [loc],
            "props_ledger": [],
            "beats": beats,
        }, extracted_dialogues

    @classmethod
    def _call_gemini_llm(cls, raw_text: str, preset_cfg: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        api_key = os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY")
        if not api_key:
            return None
        try:
            from google import genai
            from google.genai import types

            client = genai.Client(api_key=api_key)
            sys_prompt = (
                "You are an expert AI Film Showrunner & DOP. Convert the user's screenplay or story into a single JSON object "
                "with keys: project_title, characters, locations, props_ledger, beats. "
                "Rules: (1) Omit ZERO events or spoken lines; keep spoken English dialogue verbatim in beat.dialogue. "
                "(2) Separate narration into beat.narration (with beat.dialogue = null). "
                "(3) Each character needs id (CHAR_*), name, detailed anatomical/wardrobe look_verbatim (>=25 words), "
                "voice_profile, unique anchor_image (<slug>.png), and axis_gaze. "
                "(4) Each location needs id (LOC_*), name, detailed look_verbatim, and set_facts list. "
                "(5) Group beats by chapter_id (CH01, CH02...) and location. "
                "(6) Read each scene as a sequence. In beat.staging propose coverage only when it reveals "
                "a visual fact or a change in what the listener understands. Include kind, purpose, source_field "
                "(dialogue, narration, or action_summary), and a verbatim source_excerpt. Use omit when coverage "
                "would repeat what viewers already know. For reaction, specify the present listener as character_id. "
                "For state_insert, specify prop_id and record its established visible state in state_tracking at this beat ID. "
                "A mention, promise or warning about a prop is not an enacted gesture. "
                "For source_action, use an existing silent action beat, copy its complete action verbatim, and specify "
                "character_id, prop_id, before_state and after_state supported by that action or the same scene's ledger. "
                "Never invent, replay, or move a physical action to another beat."
            )
            resp = client.models.generate_content(
                model="gemini-2.5-flash",
                contents=f"Visual style preset: {preset_cfg['visual_style']}\n\nSOURCE SCRIPT:\n{raw_text}",
                config=types.GenerateContentConfig(
                    system_instruction=sys_prompt,
                    response_mime_type="application/json",
                    temperature=0.2,
                ),
            )
            if resp and resp.text:
                return json.loads(resp.text)
        except Exception:
            return None
        return None

    @classmethod
    def sanitize_and_stage(
        cls,
        raw_data: Dict[str, Any],
        preset_name: str = "drama_35mm",
    ) -> Tuple[Dict[str, Any], Dict[str, Any]]:
        """
        Chuẩn hóa cứng `story_bible` & áp Ngữ pháp Dàn dựng DOP lên `beats`:
        - Cấm trùng `anchor_image` giữa các nhân vật.
        - Khóa `axis_gaze` cố định cho từng nhân vật xuyên suốt cảnh (0 lỗi AXIS_JUMP_180 / SCENE_AXIS_VIOLATION).
        - Tự động mở đầu mỗi chương/bối cảnh mới bằng `Wide Establishing Shot` / `Wide Establishing Two-Shot`.
        - Luân phiên `Over-the-shoulder Medium Shot`, `Medium Shot`, `Medium Close-up`, giới hạn `Close-up` liên tiếp <= 2.
        """
        preset = DIRECTOR_PRESETS.get(preset_name, DIRECTOR_PRESETS["drama_35mm"])
        chars_in = list(raw_data.get("characters") or [])
        if not chars_in:
            chars_in = [cls._infer_char_profile("Protagonist", 0)]

        used_anchors: Set[str] = set()
        clean_chars: List[Dict[str, Any]] = []
        char_by_id: Dict[str, Dict[str, Any]] = {}

        for idx, ch in enumerate(chars_in):
            name = (ch.get("name") or f"Character {idx + 1}").strip()
            cid = ch.get("id") or cls._slug(name, "CHAR")
            fallback = cls._infer_char_profile(name, idx)

            look = (ch.get("look_verbatim") or "").strip()
            if len(look) < 25:
                look = fallback["look_verbatim"]

            raw_anchor = Path(ch.get("anchor_image") or fallback["anchor_image"]).name
            stem = Path(raw_anchor).stem.lower()
            candidate_anchor = f"{stem}.png"
            if candidate_anchor in used_anchors or stem in ("same", "default", "anchor"):
                unique_stem = re.sub(r"[^a-z0-9]+", "_", cid.lower()).strip("_")
                candidate_anchor = f"{unique_stem}.png"
                suffix = 2
                while candidate_anchor in used_anchors:
                    candidate_anchor = f"{unique_stem}_{suffix}.png"
                    suffix += 1
            used_anchors.add(candidate_anchor)

            gaze = ch.get("axis_gaze")
            if gaze not in ("looking screen-right", "looking screen-left"):
                gaze = "looking screen-right" if idx % 2 == 0 else "looking screen-left"

            c_obj = {
                "id": cid,
                "name": name,
                "look_verbatim": look,
                "voice_profile": ch.get("voice_profile") or fallback["voice_profile"],
                "anchor_image": candidate_anchor,
                "axis_gaze": gaze,
            }
            clean_chars.append(c_obj)
            char_by_id[cid] = c_obj

        locs_in = list(raw_data.get("locations") or [])
        if not locs_in:
            locs_in = [cls._infer_location_profile("INT. MAIN SETTING - NIGHT")]
        clean_locs: List[Dict[str, Any]] = []
        loc_ids: Set[str] = set()
        for loc in locs_in:
            lname = (loc.get("name") or "Primary Location").strip()
            lid = loc.get("id") or cls._slug(lname, "LOC")
            look = (loc.get("look_verbatim") or "").strip()
            if len(look) < 15:
                look = cls._infer_location_profile(lname)["look_verbatim"]
            facts = list(loc.get("set_facts") or ["Consistent room layout across all camera angles"])
            clean_locs.append({
                "id": lid,
                "name": lname,
                "look_verbatim": look,
                "time_of_day_lock": loc.get("time_of_day_lock", "night"),
                "set_facts": facts,
            })
            loc_ids.add(lid)

        default_lid = clean_locs[0]["id"]
        default_cid = clean_chars[0]["id"]

        # Dàn dựng DOP lên từng beat (Pyramid Shot-Scale + 30° Rule + Lens Psychology + Motivated Camera)
        beats_in = list(raw_data.get("beats") or [])
        staged_beats: List[Dict[str, Any]] = []
        prev_ch = None
        prev_loc = None
        prev_primary = None
        prev_framing = None
        prev_angle = None
        scene_shot_counter = 0
        consec_cu = 0
        dialogue_cycle_multi = [
            "Over-the-shoulder Medium Shot",
            "Medium Shot",
            "Medium Two-Shot",
            "Medium Close-up",
            "Over-the-shoulder Medium Shot",
            "Three-Quarter Medium Shot",
        ]
        dialogue_cycle_single = [
            "Medium Shot",
            "Three-Quarter Medium Shot",
            "Medium Close-up",
            "Medium Wide Shot",
        ]

        for idx, b in enumerate(beats_in, start=1):
            ch_id = b.get("chapter_id") or "CH01"
            lid = b.get("location") if b.get("location") in loc_ids else default_lid
            present = [c for c in (b.get("characters_present") or []) if c in char_by_id]
            spk = b.get("speaker")

            # Xác định primary character khớp logic ScreenplayCompiler._match_character
            matched_primary = None
            if spk:
                s_low = spk.strip().lower()
                for cid, cinfo in char_by_id.items():
                    if s_low in cinfo["name"].lower() or s_low in cid.lower():
                        matched_primary = cid
                        break
            if not matched_primary:
                matched_primary = present[0] if present else default_cid
            if matched_primary not in present:
                present = [matched_primary] + present

            is_new_chapter_or_loc = (ch_id != prev_ch) or (lid != prev_loc)
            scene_shot_counter = 1 if is_new_chapter_or_loc else (scene_shot_counter + 1)
            dlg = (b.get("dialogue") or "").strip() or None
            nar = (b.get("narration") or "").strip() or None

            # Áp dụng DOP Staging Grammar (Pyramid Shot Budget + Re-establishing mỗi 6 nhịp)
            if is_new_chapter_or_loc:
                framing = "Wide Establishing Two-Shot" if len(present) >= 2 else "Wide Establishing Shot"
                consec_cu = 0
            elif scene_shot_counter % 6 == 0 and not (dlg and (len(dlg) >= 55 or dlg.endswith("!"))):
                framing = "Wide Two-Shot" if len(present) >= 2 else "Medium Wide Shot"
                consec_cu = 0
            else:
                requested = (b.get("framing") or "").strip()
                is_climax_line = bool(dlg and (len(dlg) >= 60 or dlg.endswith("!")))
                if is_climax_line and consec_cu < 2:
                    framing = "Close-up"
                elif requested and ("close" not in requested.lower() or consec_cu < 2):
                    framing = requested
                else:
                    framing = (
                        dialogue_cycle_multi[(scene_shot_counter - 2) % len(dialogue_cycle_multi)]
                        if len(present) >= 2
                        else dialogue_cycle_single[(scene_shot_counter - 2) % len(dialogue_cycle_single)]
                    )

                if "close" in framing.lower() and "medium" not in framing.lower():
                    consec_cu += 1
                    if consec_cu > 2:
                        framing = "Medium Shot"
                        consec_cu = 0
                elif "close" in framing.lower():
                    consec_cu += 1
                    if consec_cu > 2:
                        framing = "Over-the-shoulder Medium Shot" if len(present) >= 2 else "Medium Shot"
                        consec_cu = 0
                else:
                    consec_cu = 0

            # Quy tắc 30°: Không để cùng 1 nhân vật lặp lại y hệt cỡ cảnh + góc máy ở 2 shot đơn liên tiếp
            cam_angle = (b.get("camera_angle") or "").strip() or None
            if (
                not is_new_chapter_or_loc
                and matched_primary == prev_primary
                and framing == prev_framing
                and "two" not in framing.lower()
                and "wide" not in framing.lower()
                and "over-the-shoulder" not in framing.lower()
            ):
                if "close" in framing.lower():
                    framing = "Three-Quarter Medium Shot"
                    consec_cu = 0
                else:
                    cam_angle = cam_angle or "subtle three-quarter 30-degree angle"

            if not cam_angle and "close-up" in framing.lower() and "medium" not in framing.lower() and dlg and dlg.endswith("!"):
                cam_angle = "subtle low-angle"

            # Chuyển động camera có động cơ (Motivated Camera Motion)
            cam_motion = (b.get("camera_motion") or "").strip() or None
            if not cam_motion and not dlg:
                if is_new_chapter_or_loc or "wide" in framing.lower():
                    cam_motion = "slow lateral slider drift"
                else:
                    cam_motion = "slow dolly-in"

            fg_elem = (b.get("foreground_element") or "").strip() or None
            if not fg_elem and "over-the-shoulder" in framing.lower() and len(present) >= 2:
                fg_elem = "soft-focus foreground shoulder of the listening character framing the axis"

            locked_gaze = char_by_id[matched_primary]["axis_gaze"]
            staged_beat: Dict[str, Any] = {
                "beat_id": b.get("beat_id") or f"B{idx:03d}",
                "shot_id": b.get("shot_id") or f"SHOT_{idx:03d}_{ch_id}",
                "order": idx,
                "chapter_id": ch_id,
                "location": lid,
                "speaker": spk,
                "characters_present": present,
                "framing": framing,
                "gaze": locked_gaze,
                "action_summary": b.get("action_summary") or "Character maintains natural composed presence.",
                "dialogue": dlg,
                "narration": nar,
            }
            if cam_angle:
                staged_beat["camera_angle"] = cam_angle
            if cam_motion:
                staged_beat["camera_motion"] = cam_motion
            if fg_elem:
                staged_beat["foreground_element"] = fg_elem
            for opt_k in (
                "source_start_s", "source_end_s", "source_reference",
                "lens_mm", "lighting_mood", "is_flashback", "color_mood",
                "transition_in", "wardrobe_override", "post_camera_motion", "subtext",
                "shot_role", "target_trim_duration_s", "cutaway_type", "prop_source_beat_id", "scene_id", "staging",
            ):
                if b.get(opt_k) is not None:
                    staged_beat[opt_k] = b[opt_k]

            staged_beats.append(staged_beat)
            prev_ch = ch_id
            prev_loc = lid
            prev_primary = matched_primary
            prev_framing = framing
            prev_angle = cam_angle

        story_bible: Dict[str, Any] = {
            "project_title": raw_data.get("project_title") or "AI Film Project",
            "preset": preset_name,
            "world_rules": {
                "visual_style": raw_data.get("world_rules", {}).get("visual_style") or preset["visual_style"],
                "aspect_ratio": "16:9",
            },
            "characters": clean_chars,
            "locations": clean_locs,
            "props_ledger": list(raw_data.get("props_ledger") or []),
        }
        if raw_data.get("source_srt_path"):
            story_bible["source_srt_path"] = raw_data["source_srt_path"]
        if raw_data.get("must_show"):
            story_bible["must_show"] = raw_data["must_show"]

        beats_doc: Dict[str, Any] = {
            "project_title": story_bible["project_title"],
            "preset": preset_name,
            "total_beats": len(staged_beats),
            "beats": staged_beats,
        }
        return story_bible, beats_doc

    @staticmethod
    def inject_cinematic_cutaways(
        bible: Dict[str, Any],
        beats: List[Dict[str, Any]],
        max_extra_ratio: float = 0.20,
    ) -> List[Dict[str, Any]]:
        staged, _ = plan_staging(
            bible, beats, include_optional=True, max_extra_ratio=max_extra_ratio,
            materialize_source_action=False,
        )
        return staged

    @staticmethod
    def verify_dialogue_coverage(source_dialogues: List[str], beats: List[Dict[str, Any]]) -> Dict[str, Any]:
        norm = lambda s: re.sub(r"[^\w\s]", "", (s or "").lower()).split()
        beat_corpus = " ".join(
            " ".join(norm(b.get("dialogue") or "")) for b in beats
        )
        missing: List[str] = []
        for src in source_dialogues:
            toks = norm(src)
            if not toks:
                continue
            probe = " ".join(toks[: min(6, len(toks))])
            if probe not in beat_corpus:
                missing.append(src)
        return {
            "total_source_dialogues": len(source_dialogues),
            "missing_dialogues": missing,
            "passed": len(missing) == 0,
        }

    @classmethod
    def ingest_file(
        cls,
        input_path: Path,
        project_dir: Path,
        preset: str = "drama_35mm",
        chapters_path: Optional[Path] = None,
        use_llm: bool = True,
        llm_callable: Optional[Callable[[str], Dict[str, Any]]] = None,
        cinematic_cutaways: bool = False,
    ) -> Dict[str, Any]:
        """
        Đọc file kịch bản / truyện / SRT, sinh `story_bible.json` + `beats.json` vào `project_dir`.
        """
        input_path = Path(input_path)
        if not input_path.exists():
            raise FileNotFoundError(f"Không tìm thấy file kịch bản đầu vào: {input_path}")

        project_dir = Path(project_dir)
        project_dir.mkdir(parents=True, exist_ok=True)
        preset_cfg = DIRECTOR_PRESETS.get(preset, DIRECTOR_PRESETS["drama_35mm"])

        suffix = input_path.suffix.lower()
        source_dialogues: List[str] = []
        raw_struct: Optional[Dict[str, Any]] = None

        if suffix == ".srt":
            raw_struct, source_dialogues = cls._parse_srt_input(input_path, chapters_path=chapters_path)
        elif suffix == ".json":
            loaded = json.loads(input_path.read_text(encoding="utf-8-sig"))
            raw_struct = loaded if isinstance(loaded, dict) else {"beats": loaded}
        else:
            raw_text = input_path.read_text(encoding="utf-8-sig")
            local_struct, source_dialogues = cls._parse_text_or_screenplay(
                raw_text, default_title=input_path.stem.replace("_", " ").title()
            )
            if use_llm:
                if llm_callable is not None:
                    raw_struct = llm_callable(raw_text)
                else:
                    raw_struct = cls._call_gemini_llm(raw_text, preset_cfg)
            if not raw_struct or not raw_struct.get("beats"):
                raw_struct = local_struct
            elif raw_struct is not local_struct:
                source_text = " ".join(raw_text.split())
                enacted_actions = {
                    " ".join(beat["action_summary"].split())
                    for beat in local_struct.get("beats", [])
                    if not beat.get("dialogue") and not beat.get("narration") and beat.get("action_summary")
                }
                props_by_id = {
                    prop["id"]: prop for prop in raw_struct.get("props_ledger") or []
                    if isinstance(prop, dict) and prop.get("id")
                }
                for beat in raw_struct["beats"]:
                    direction = beat.get("staging")
                    if not isinstance(direction, dict):
                        continue
                    excerpt = " ".join(str(direction.get("source_excerpt") or "").split())
                    kind = direction.get("kind")
                    if kind == "source_action" and excerpt not in enacted_actions:
                        raw_struct = local_struct
                        break
                    if not excerpt or excerpt not in source_text:
                        beat.pop("staging")
                    elif kind == "state_insert":
                        states = props_by_id.get(str(direction.get("prop_id") or ""), {}).get("state_tracking") or {}
                        state = " ".join(str(states.get(beat.get("beat_id")) or "").split()) if isinstance(states, dict) else ""
                        if (
                            direction.get("source_field") != "action_summary" or excerpt not in enacted_actions
                            or not state or state not in excerpt
                        ):
                            beat.pop("staging")

        story_bible, beats_doc = cls.sanitize_and_stage(raw_struct, preset_name=preset)
        if cinematic_cutaways:
            beats_doc["beats"] = cls.inject_cinematic_cutaways(story_bible, beats_doc["beats"])
            beats_doc["total_beats"] = len(beats_doc["beats"])
        coverage = cls.verify_dialogue_coverage(source_dialogues, beats_doc["beats"])

        bible_out = project_dir / "story_bible.json"
        beats_out = project_dir / "beats.json"
        bible_out.write_text(json.dumps(story_bible, indent=2, ensure_ascii=False), encoding="utf-8")
        beats_out.write_text(json.dumps(beats_doc, indent=2, ensure_ascii=False), encoding="utf-8")

        return {
            "project_dir": str(project_dir),
            "story_bible_path": str(bible_out),
            "beats_path": str(beats_out),
            "preset": preset,
            "audio_mode": preset_cfg["audio_mode"],
            "total_characters": len(story_bible["characters"]),
            "total_locations": len(story_bible["locations"]),
            "total_beats": beats_doc["total_beats"],
            "coverage": coverage,
        }
