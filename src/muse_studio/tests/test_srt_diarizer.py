import pytest
from pathlib import Path
from muse_studio.core.srt_diarizer import (
    SRTCue,
    CharacterProfile,
    SRTDiarizer,
    parse_srt,
    parse_timestamp_to_seconds,
)

SAMPLE_SRT = """1
00:00:01,000 --> 00:00:03,500
BRIANNA: I am Captain Brianna Vance.

2
00:00:03,600 --> 00:00:06,000
ATTENDANT: You don't look like a pilot to me.

3
00:00:06,200 --> 00:00:08,500
ATTENDANT: Show me your authorization badge right now.

4
00:00:08,700 --> 00:00:11,000
BRIANNA: My credentials are fully verified.
"""

def test_parse_timestamp():
    assert parse_timestamp_to_seconds("00:01:23,500") == 83.5
    assert parse_timestamp_to_seconds("00:00:02.100") == 2.1
    assert parse_timestamp_to_seconds("02:10") == 130.0

def test_parse_srt():
    cues = parse_srt(SAMPLE_SRT)
    assert len(cues) == 4
    assert cues[0].index == 1
    assert cues[0].start_s == 1.0
    assert cues[0].end_s == 3.5
    assert "Captain Brianna" in cues[0].text

def test_diarize_and_stage_180_rule():
    cues = parse_srt(SAMPLE_SRT)
    chars = {
        "BRIANNA": CharacterProfile(
            name="BRIANNA",
            visual_desc="Captain Brianna in pilot uniform",
            default_gaze="looking screen-right",
            default_framing="medium close-up, screen-left",
            default_tone="in a calm measured voice"
        ),
        "ATTENDANT": CharacterProfile(
            name="ATTENDANT",
            visual_desc="Flight attendant in red uniform",
            default_gaze="looking screen-left",
            default_framing="medium close-up, screen-right",
            default_tone="with sharp authority"
        )
    }

    diarizer = SRTDiarizer(characters=chars, scene_context="aircraft forward galley")
    turns = diarizer.diarize_and_stage(cues, primary_speakers=("BRIANNA", "ATTENDANT"))

    # Turn 1: Brianna
    # Turn 2: Attendant (gộp cue 2 và 3 vì cùng speaker và duration < 8s)
    # Turn 3: Brianna
    assert len(turns) == 3

    assert turns[0].speaker == "BRIANNA"
    assert turns[0].gaze_direction == "looking screen-right"
    assert "Captain Brianna Vance" in turns[0].dialogue_text

    assert turns[1].speaker == "ATTENDANT"
    assert turns[1].gaze_direction == "looking screen-left"
    assert "Show me your authorization badge" in turns[1].dialogue_text
    assert len(turns[1].cues) == 2

    assert turns[2].speaker == "BRIANNA"
    assert turns[2].gaze_direction == "looking screen-right"

def test_compile_muse_prompt_format():
    char = CharacterProfile(
        name="Alma",
        visual_desc="older Alma in burgundy cardigan",
        default_gaze="looking screen-right",
        default_framing="close-up of the woman in burgundy looking screen-right",
        default_tone="in a low measured voice"
    )
    diarizer = SRTDiarizer(characters={"Alma": char}, scene_context="community legal help office")
    cues = [SRTCue(index=1, start_s=0.0, end_s=5.0, text="Grant Foundation. This is Alma.")]
    turns = diarizer.diarize_and_stage(cues, primary_speakers=("Alma", "Caller"))
    
    prompt = turns[0].muse_prompt
    assert "16:9" in prompt
    assert "Clear view of lips" in prompt
    assert "Grant Foundation. This is Alma." in prompt
    assert "Nobody looks into the lens" in prompt
    assert "Hands remain below frame" in prompt
