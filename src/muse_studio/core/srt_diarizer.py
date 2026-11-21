"""
SRT Diarizer & Cinematic Dialogue Staging Engine
Tự động đọc hiểu file phụ đề SRT, phân vai nhân vật (Speaker Attribution),
gộp các cue thành lượt thoại hoàn chỉnh (Dialogue Turns: 3-8s)
và dàn dựng cặp góc máy đối ứng (Shot-Reverse-Shot) bảo toàn trục 180°.
"""

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Tuple


@dataclass
class SRTCue:
    index: int
    start_s: float
    end_s: float
    text: str

    @property
    def duration_s(self) -> float:
        return max(0.0, self.end_s - self.start_s)


@dataclass
class CharacterProfile:
    name: str
    visual_desc: str
    default_gaze: str = "looking screen-right"
    default_framing: str = "close-up, screen-left"
    default_tone: str = "in a low measured voice"
    hand_instruction: str = "Hands remain below frame."


@dataclass
class DialogueTurn:
    turn_id: str
    speaker: str
    character_profile: CharacterProfile
    cues: List[SRTCue]
    start_s: float
    end_s: float
    dialogue_text: str
    gaze_direction: str
    framing: str
    tone_direction: str
    scene_context: str
    first_frame_ref: Optional[str] = None
    muse_prompt: str = ""

    @property
    def duration_s(self) -> float:
        return max(0.0, self.end_s - self.start_s)


def parse_timestamp_to_seconds(ts_str: str) -> float:
    """Chuyển đổi 00:01:23,456 hoặc 00:01:23.456 sang float giây."""
    ts_str = ts_str.strip().replace(",", ".")
    parts = ts_str.split(":")
    if len(parts) == 3:
        h, m, s = parts
        return float(h) * 3600.0 + float(m) * 60.0 + float(s)
    elif len(parts) == 2:
        m, s = parts
        return float(m) * 60.0 + float(s)
    return float(ts_str)


def parse_srt(content_or_path: str | Path) -> List[SRTCue]:
    """Phân tích nội dung hoặc file SRT thành danh sách SRTCue."""
    if isinstance(content_or_path, Path) or (isinstance(content_or_path, str) and "\n" not in content_or_path and Path(content_or_path).exists()):
        text = Path(content_or_path).read_text(encoding="utf-8-sig")
    else:
        text = str(content_or_path)

    # Chuẩn hóa xuống dòng
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    blocks = re.split(r"\n\s*\n", text.strip())

    cues: List[SRTCue] = []
    pattern = re.compile(
        r"^(\d+)\s*\n"
        r"(\d{2}:\d{2}:\d{2}[,\.]\d{3})\s*-->\s*(\d{2}:\d{2}:\d{2}[,\.]\d{3})\s*\n"
        r"([\s\S]+)$"
    )

    for block in blocks:
        block = block.strip()
        if not block:
            continue
        m = pattern.match(block)
        if m:
            idx = int(m.group(1))
            start_s = parse_timestamp_to_seconds(m.group(2))
            end_s = parse_timestamp_to_seconds(m.group(3))
            raw_text = m.group(4).strip()
            # Xóa các thẻ HTML subtitle như <i>, <font>
            clean_text = re.sub(r"<[^>]+>", "", raw_text)
            clean_text = " ".join(clean_text.split())
            if clean_text:
                cues.append(SRTCue(index=idx, start_s=start_s, end_s=end_s, text=clean_text))

    return cues


class SRTDiarizer:
    """
    Bộ phân vai tự động và dàn dựng góc máy 180 độ cho kịch bản có thoại Native.
    """

    def __init__(
        self,
        characters: Optional[Dict[str, CharacterProfile]] = None,
        scene_context: str = "quiet airplane galley",
        ambient_sound: str = "airplane cabin ventilation hum"
    ):
        self.characters = characters or {}
        self.scene_context = scene_context
        self.ambient_sound = ambient_sound

    def diarize_and_stage(
        self,
        cues: List[SRTCue],
        primary_speakers: Optional[Tuple[str, str]] = None,
        max_turn_duration_s: float = 8.0,
        shot_duration_s: float = 10.0
    ) -> List[DialogueTurn]:
        """
        Gộp các cue thành các lượt thoại (Dialogue Turns) và dàn dựng trục 180°.
        """
        if not cues:
            return []

        # Tự động gán 2 nhân vật chính nếu chưa chỉ định
        if not primary_speakers:
            keys = list(self.characters.keys())
            if len(keys) >= 2:
                primary_speakers = (keys[0], keys[1])
            elif len(keys) == 1:
                primary_speakers = (keys[0], "Offscreen Speaker")
            else:
                primary_speakers = ("Speaker_A", "Speaker_B")

        spk_a, spk_b = primary_speakers

        # Thiết lập profile mặc định nếu thiếu
        if spk_a not in self.characters:
            self.characters[spk_a] = CharacterProfile(
                name=spk_a,
                visual_desc=f"{spk_a}",
                default_gaze="looking screen-right",
                default_framing="medium close-up, screen-left",
                default_tone="in a low measured voice"
            )
        if spk_b not in self.characters:
            self.characters[spk_b] = CharacterProfile(
                name=spk_b,
                visual_desc=f"{spk_b}",
                default_gaze="looking screen-left",
                default_framing="medium close-up, screen-right",
                default_tone="in a sharp tone"
            )

        # 1. Phân loại từng cue cho speaker
        attributed_cues: List[Tuple[str, SRTCue, str]] = []
        current_speaker = spk_a

        for cue in cues:
            text = cue.text
            extracted_speaker = None
            clean_dialogue = text

            # Kiểm tra tiền tố dạng "BRIANNA: ..." hoặc "[Attendant] ..."
            prefix_match = re.match(r"^([A-Za-z0-9_\s]+)[:\-]\s*(.+)$", text)
            if prefix_match:
                prefix = prefix_match.group(1).strip().upper()
                clean_dialogue = prefix_match.group(2).strip()
                for name in self.characters:
                    if name.upper() in prefix:
                        extracted_speaker = name
                        break

            if extracted_speaker:
                current_speaker = extracted_speaker
            elif text.endswith("?"):
                # Dấu hỏi có thể kết thúc lượt thoại, chuẩn bị chuyển người nói tiếp theo
                pass

            attributed_cues.append((current_speaker, cue, clean_dialogue))

            # Nếu là câu hỏi hoặc dấu chấm kết thúc rõ rệt, lượt tiếp theo luân phiên
            if text.endswith("?") and current_speaker == spk_a:
                current_speaker = spk_b
            elif text.endswith("?") and current_speaker == spk_b:
                current_speaker = spk_a

        # 2. Gộp các cue cùng speaker thành Turn (tối đa max_turn_duration_s)
        turns: List[DialogueTurn] = []
        turn_idx = 1

        curr_turn_speaker: Optional[str] = None
        curr_turn_cues: List[SRTCue] = []
        curr_turn_texts: List[str] = []

        def flush_turn():
            nonlocal turn_idx, curr_turn_speaker, curr_turn_cues, curr_turn_texts
            if not curr_turn_cues or not curr_turn_speaker:
                return

            prof = self.characters.get(curr_turn_speaker) or self.characters[spk_a]
            start_s = curr_turn_cues[0].start_s
            end_s = curr_turn_cues[-1].end_s
            merged_text = " ".join(curr_turn_texts).strip()

            # Bảo toàn trục 180 độ
            if curr_turn_speaker == spk_a:
                gaze = prof.default_gaze or "looking screen-right"
                framing = prof.default_framing or "close-up of the character looking screen-right"
            else:
                gaze = prof.default_gaze or "looking screen-left"
                framing = prof.default_framing or "close-up of the character looking screen-left"

            turn = DialogueTurn(
                turn_id=f"T{turn_idx:02d}_{curr_turn_speaker}",
                speaker=curr_turn_speaker,
                character_profile=prof,
                cues=list(curr_turn_cues),
                start_s=start_s,
                end_s=end_s,
                dialogue_text=merged_text,
                gaze_direction=gaze,
                framing=framing,
                tone_direction=prof.default_tone,
                scene_context=self.scene_context
            )
            turn.muse_prompt = self.compile_muse_prompt(turn, shot_duration_s=shot_duration_s)
            turns.append(turn)
            turn_idx += 1

            curr_turn_cues = []
            curr_turn_texts = []
            curr_turn_speaker = None

        for speaker, cue, clean_text in attributed_cues:
            if curr_turn_speaker is None:
                curr_turn_speaker = speaker
                curr_turn_cues.append(cue)
                curr_turn_texts.append(clean_text)
            elif curr_turn_speaker == speaker:
                prospective_dur = cue.end_s - curr_turn_cues[0].start_s
                if prospective_dur <= max_turn_duration_s:
                    curr_turn_cues.append(cue)
                    curr_turn_texts.append(clean_text)
                else:
                    flush_turn()
                    curr_turn_speaker = speaker
                    curr_turn_cues.append(cue)
                    curr_turn_texts.append(clean_text)
            else:
                flush_turn()
                curr_turn_speaker = speaker
                curr_turn_cues.append(cue)
                curr_turn_texts.append(clean_text)

        flush_turn()
        return turns

    def compile_muse_prompt(self, turn: DialogueTurn, shot_duration_s: float = 10.0) -> str:
        """
        Biên dịch prompt Native Dialogue chuẩn xác theo mẫu chứng minh của Codex.
        """
        char_desc = turn.character_profile.visual_desc
        tone = turn.tone_direction
        dialogue = turn.dialogue_text
        gaze = turn.gaze_direction
        framing = turn.framing
        scene = turn.scene_context
        ambient = self.ambient_sound
        hands = turn.character_profile.hand_instruction

        prompt = (
            f"The given image is the first frame. A single unbroken {int(shot_duration_s)}s shot, no scene cuts, 16:9: "
            f"{framing}. "
            f"[0-0.5s] Close single of {turn.speaker} in the established {scene}, eyes attentive, {gaze}. "
            f"Clear view of lips. "
            f"[0.5-9s] The speaker says the exact words once with a short, natural breath between sentences. "
            f"{hands} "
            f"[9-{int(shot_duration_s)}s] Mouth closes and gaze settles. Quiet room tone. "
            f"No added gesture, lettering, or speech. "
            f"{char_desc}, {tone}, says in English: {dialogue} "
            f"Sound design: quiet {ambient}, no music. "
            f"Only this character in frame, same cast and wardrobe as the reference. "
            f"No new lettering. No on-screen text, subtitles or logos. Nobody looks into the lens."
        )
        return prompt
