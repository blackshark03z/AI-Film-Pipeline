"""Compiler defaults must not erase authored behavior, framing, line length or opening state."""

from pathlib import Path

from PIL import Image

from muse_studio.core.keyframe_composer import KeyframeComposer
from muse_studio.core.screenplay_compiler import ScreenplayCompiler

B14_LINE = "Pamela, this is Captain Brianna Johnson. She is not just the pilot assigned to Flight 1128."
PAMELA = ("Pamela's mouth opens and her lips move without sound. Her fingers lose their grip and the "
          "clipboard slips from her hand onto the carpet.")


def _bible():
    return {
        "characters": [
            {"id": "T", "name": "Todd", "look_verbatim": "Todd wears a pale blue uniform shirt.", "anchor_image": "t.png"},
            {"id": "P", "name": "Pamela", "look_verbatim": "Pamela wears a navy suit.", "anchor_image": "p.png"},
        ],
        "locations": [{"id": "GATE", "look_verbatim": "An airport gate lounge."}],
    }


def _beats(*lines):
    return [
        {
            "beat_id": f"B{i}", "shot_id": f"S{i}", "chapter_id": "CH01", "location": "GATE",
            "dialogue": line, "speaker": "Todd", "characters_present": ["T", "P"],
        }
        for i, line in enumerate(lines, 1)
    ]


def _reaction_beats(**extra):
    beats = _beats(B14_LINE, "Line two.", "Line three.", "Line four.", "Line five.")
    beats[0]["staging"] = {
        "kind": "reaction", "purpose": "Show Pamela's response to the accusation.",
        "source_field": "dialogue", "source_excerpt": "Flight 1128.", "character_id": "P", **extra,
    }
    return beats


def _reaction(compiled):
    return next(shot for shot in compiled["shots"] if shot.get("cutaway_type") == "reaction")


def test_authored_reaction_keeps_behavior_hands_and_silent_mouth():
    beats = _reaction_beats(visible_behavior=PAMELA, framing="Medium Shot")
    shot = _reaction(ScreenplayCompiler.compile_shots(_bible(), beats, cinematic_cutaways=True))
    prompt = shot["compiled_prompt"]
    assert PAMELA in prompt
    assert "restrained reaction" not in prompt
    assert ScreenplayCompiler.HAND_GUARD in prompt
    assert "Keep hands out of frame" not in prompt
    assert "No words and no speech sound" in prompt
    assert "no lip movement" not in prompt
    assert shot["framing"] == "Medium Shot"
    assert shot["target_trim_duration_s"] == 5.0
    assert shot["audio_mode"] == "SILENT_ACTION"


def test_default_reaction_names_listener_and_keeps_hands_out():
    shot = _reaction(ScreenplayCompiler.compile_shots(_bible(), _reaction_beats(), cinematic_cutaways=True))
    assert "Pamela silently takes in the line" in shot["compiled_prompt"]
    assert "Keep hands out of frame for this reaction." in shot["compiled_prompt"]
    assert "Lips remain completely closed" in shot["compiled_prompt"]
    assert shot["framing"] == "Medium Close-up" and shot["lens_mm"] == 85


def test_blank_visible_behavior_is_rejected():
    compiled = ScreenplayCompiler.compile_shots(_bible(), _reaction_beats(visible_behavior="  "),
                                                cinematic_cutaways=True)
    assert [row["outcome"] for row in compiled["staging_review"]] == ["invalid"]
    assert not any(shot.get("cutaway_type") for shot in compiled["shots"])


def test_dialogue_window_follows_line_length():
    timing = ScreenplayCompiler.estimate_dialogue_timing(B14_LINE)
    assert timing["spoken_words"] == 17  # "1128" is read as two words
    assert timing["status"] == "FITS"
    shot = ScreenplayCompiler.compile_shots(_bible(), _beats(B14_LINE))["shots"][0]
    end = shot["dialogue_timing"]["speech_window_s"][1]
    assert 7.0 < end < 8.5
    assert f"[0.5-{end:g}s]" in shot["compiled_prompt"]
    assert f"[{end:g}-10s]" in shot["compiled_prompt"]
    assert "No further words from anyone" in shot["compiled_prompt"]


def test_overlong_line_is_flagged_before_render():
    long_line = " ".join(["Every word in this sentence keeps going."] * 7)
    compiled = ScreenplayCompiler.compile_shots(_bible(), _beats(long_line))
    shot = compiled["shots"][0]
    assert shot["dialogue_timing"]["status"] == "OVER_CAPACITY"
    assert shot["dialogue_timing"]["speech_window_s"] == [0.5, 9.0]
    assert any(w.startswith("DIALOGUE_OVER_CAPACITY (S1)") for w in compiled["coverage_warnings"])


def test_opening_state_reaches_keyframe_and_splits_keys(tmp_path: Path):
    beats = _beats("We wait here.", "We wait here.")
    for beat in beats:
        beat.update(characters_present=["T"], framing="Medium Shot")
    beats[0]["opening_state"] = "Feet, hips, chest and face turned toward Pamela at screen right."
    compiled = ScreenplayCompiler.compile_shots(_bible(), beats)
    first, second = compiled["shots"]
    assert first["keyframe_key"] != second["keyframe_key"]
    anchors = tmp_path / "assets" / "anchors"
    anchors.mkdir(parents=True)
    Image.new("RGB", (640, 360), (90, 90, 90)).save(anchors / "t.png")
    planned = KeyframeComposer.plan_missing_scene_keyframes(_bible(), compiled, tmp_path)
    prompts = {item.kf_id: item.prompt for item in planned}
    assert "Opening state: Feet, hips, chest and face turned toward Pamela at screen right." in prompts[first["keyframe_key"]]
    assert "mouth closed" not in prompts[first["keyframe_key"]]
    assert "eyes open, mouth closed" in prompts[second["keyframe_key"]]


def test_number_punctuation_does_not_change_timing():
    plain = ScreenplayCompiler.estimate_dialogue_timing("Board Flight 1128 now.")
    comma = ScreenplayCompiler.estimate_dialogue_timing("Board Flight 1,128 now.")
    assert plain["spoken_words"] == comma["spoken_words"] == 5  # 1128 -> two words
    assert plain["est_speech_s"] == comma["est_speech_s"]
    decimal = ScreenplayCompiler.estimate_dialogue_timing("Wait 1.5 hours")
    assert decimal["est_speech_s"] == round(decimal["spoken_words"] / ScreenplayCompiler.SPEECH_WORDS_PER_S, 2)


def test_listener_name_containing_hand_keeps_hands_out():
    bible = _bible()
    bible["characters"][1]["name"] = "Chandler"
    shot = _reaction(ScreenplayCompiler.compile_shots(bible, _reaction_beats(), cinematic_cutaways=True))
    assert "Chandler silently takes in the line" in shot["compiled_prompt"]
    assert "Keep hands out of frame for this reaction." in shot["compiled_prompt"]
    assert ScreenplayCompiler.HAND_GUARD not in shot["compiled_prompt"]


def test_silent_opening_state_overrides_closed_lips():
    beat = {
        "beat_id": "B1", "shot_id": "S1", "chapter_id": "CH01", "location": "GATE",
        "characters_present": ["P"], "framing": "Medium Shot",
        "action_summary": "Pamela stares at the departures board.",
        "opening_state": "Eyes closed, mouth open in silent shock.",
    }
    prompt = ScreenplayCompiler.compile_shots(_bible(), [beat])["shots"][0]["compiled_prompt"]
    assert "[0-0.5s] Hold the exact opening state of image 1: Eyes closed, mouth open in silent shock." in prompt
    assert "lips completely closed" not in prompt.lower()
    assert "no lip movement" not in prompt


def test_unicode_dialogue_words_are_counted():
    short = ScreenplayCompiler.estimate_dialogue_timing("Ừ, ở đó.")
    assert short["spoken_words"] == 3
    assert short["speech_window_s"][1] > short["speech_window_s"][0]
    assert ScreenplayCompiler.estimate_dialogue_timing("Tôi")["spoken_words"] == 1
    assert ScreenplayCompiler.estimate_dialogue_timing("Don't go, B14.")["spoken_words"] == 3


def _silent_beat(action, **extra):
    return {
        "beat_id": "B1", "shot_id": "S1", "chapter_id": "CH01", "location": "GATE",
        "characters_present": ["P"], "framing": "Medium Shot", "action_summary": action, **extra,
    }


def test_compound_phone_words_keep_hand_guard():
    for action in ("Pamela raises her smartphone to her ear.", "Pamela lifts her cellphone."):
        prompt = ScreenplayCompiler.compile_shots(_bible(), [_silent_beat(action)])["shots"][0]["compiled_prompt"]
        assert ScreenplayCompiler.HAND_GUARD in prompt, action


def test_hand_in_opening_state_keeps_hand_guard():
    beat = _silent_beat("Pamela looks at the departures board.",
                        opening_state="Right hand holding the clipboard at chest height.")
    prompt = ScreenplayCompiler.compile_shots(_bible(), [beat])["shots"][0]["compiled_prompt"]
    assert ScreenplayCompiler.HAND_GUARD in prompt
    assert "out of frame or relaxed" not in prompt


def test_mouths_verb_is_not_forbidden():
    prompt = ScreenplayCompiler.compile_shots(_bible(), [_silent_beat('Pamela silently mouths "What?"')])
    text = prompt["shots"][0]["compiled_prompt"]
    assert "no lip movement" not in text
    assert "any mouth movement stays silent" in text


def test_two_shot_keyframe_keeps_opening_state(tmp_path: Path):
    beats = _beats("We wait here.")
    beats[0].update(framing="Two-Shot", dialogue="", action_summary="Todd and Pamela face each other.",
                    opening_state="Todd has eyes closed and mouth open in silent shock.")
    compiled = ScreenplayCompiler.compile_shots(_bible(), beats)
    shot = compiled["shots"][0]
    assert shot.get("is_multi_person")
    anchors = tmp_path / "assets" / "anchors"
    anchors.mkdir(parents=True)
    for name in ("t.png", "p.png"):
        Image.new("RGB", (640, 360), (90, 90, 90)).save(anchors / name)
    planned = KeyframeComposer.plan_missing_scene_keyframes(_bible(), compiled, tmp_path)
    prompt = {item.kf_id: item.prompt for item in planned}[shot["keyframe_key"]]
    assert "Opening state: Todd has eyes closed and mouth open in silent shock." in prompt


def test_curly_apostrophe_and_nfd_count_like_plain_text():
    est = ScreenplayCompiler.estimate_dialogue_timing
    assert est("Don\u2019t go, B14.")["spoken_words"] == est("Don't go, B14.")["spoken_words"] == 3
    assert est("To\u0302i")["spoken_words"] == est("T\u00f4i")["spoken_words"] == 1


def test_hidden_hands_opening_does_not_demand_visible_hands():
    beat = _silent_beat("Pamela looks at the departures board.",
                        opening_state="Arms folded, hands hidden under her sleeves.")
    prompt = ScreenplayCompiler.compile_shots(_bible(), [beat])["shots"][0]["compiled_prompt"]
    assert ScreenplayCompiler.HAND_GUARD not in prompt
    assert "Hands stay hidden exactly as in the opening state." in prompt


def test_appearance_words_keep_closed_lips():
    for opening in ("She has a sharp jawline and wears red lipstick.", "A bottle of mouthwash sits beside her."):
        beat = _silent_beat("Pamela looks at the departures board.", opening_state=opening)
        prompt = ScreenplayCompiler.compile_shots(_bible(), [beat])["shots"][0]["compiled_prompt"]
        assert "no lip movement" in prompt, opening
    jaw = _silent_beat("Pamela's jaw drops.")
    assert "no lip movement" not in ScreenplayCompiler.compile_shots(_bible(), [jaw])["shots"][0]["compiled_prompt"]


def test_two_shot_opening_state_uses_new_cache_key():
    beats = _beats("We wait here.", "We wait here.")
    beats[0].update(framing="Two-Shot", opening_state="Todd turns toward Pamela.")
    beats[1].update(framing="Medium Shot", characters_present=["T"], opening_state="Todd turns toward Pamela.")
    two, single = ScreenplayCompiler.compile_shots(_bible(), beats)["shots"]
    assert "__os2_" in two["keyframe_key"] and "__os_" not in two["keyframe_key"]
    assert "__os_" in single["keyframe_key"]
