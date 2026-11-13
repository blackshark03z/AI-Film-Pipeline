"""Read-only structural check for the film08 screenplay draft; no provider or film-package imports."""
import json
import re
from collections import Counter
from pathlib import Path

CAST = {"NAOMI", "HOLLIS", "ELI", "CALVIN"}


def check():
    root = Path(__file__).resolve().parent
    draft = json.loads((root / "beats.json").read_text(encoding="utf-8"))
    script = (root / "script.fountain").read_text(encoding="utf-8")
    scenes = draft["scenes"]
    assert draft["film_id"] == "film08_chain_of_custody"
    assert len(scenes) == 12
    beats = [beat for scene in scenes for beat in scene["beats"]]
    assert len(beats) == 300
    ids = [beat["generation_id"] for beat in beats]
    assert len(set(ids)) == 300
    assert re.findall(r"\[\[(SC\d{2}_g\d{2}) ", script) == ids
    assert len(re.findall(r"^INT\. ", script, re.MULTILINE)) == 12
    dialogue = [beat for beat in beats if beat["kind"] == "dialogue"]
    assert len(dialogue) == 270
    counts = Counter(beat["kind"] for beat in beats)
    assert counts["action"] + counts["reaction"] == 30
    words = [len(beat["text_en"].split()) for beat in dialogue]
    assert all(9 <= count <= 11 for count in words), "dialogue must be 9-11 words"
    for index, scene in enumerate(scenes, 1):
        assert scene["scene_id"] == f"SC{index:02}"
        assert scene["title"] and scene["goal"] and scene["outcome"]
        assert [beat["generation_id"] for beat in scene["beats"]] == [f"SC{index:02}_g{n:02}" for n in range(1, 26)]
    for scene in scenes[:11]:
        assert all(beat["speaker"] != "CALVIN" for beat in scene["beats"]), "CALVIN appears only in SC12"
    for beat in beats:
        assert beat["speaker"] in CAST
        assert beat["native_s"] == 6 and beat["target_used_s"] == 5.5
        assert beat["stage_action"]
        assert beat["motion_class"] in {"simple", "static"}
        assert beat["kind"] in {"dialogue", "action", "reaction"}
        assert not re.search(r"\b(black|white|african|caucasian)\b", beat["stage_action"], re.I) or "red wax" in beat["stage_action"]
        if beat["kind"] == "dialogue":
            assert beat["text_en"] and beat["text_vi"], beat["generation_id"]
            assert beat["motion_class"] == "static"
            assert beat["addressee"] in CAST | {"RADIO"} and beat["addressee"] != beat["speaker"]
            assert beat["text_en"] in script
        else:
            assert not beat["text_en"] and not beat["text_vi"]
    body_s = sum(beat["target_used_s"] for beat in beats)
    pilot_s = draft["timing"]["opening_card_s"] + sum(beat["target_used_s"] for beat in beats[:50])
    assert body_s == 1650 and body_s + 3 + 4 == 1657
    assert pilot_s == 278 and beats[-1]["generation_id"] == "SC12_g25"
    result = {"structural_check": "PASS", "scenes": len(scenes), "generation_beats": len(beats),
              "kinds": dict(counts), "english_dialogue_words": sum(words),
              "english_words_per_dialogue_min": min(words), "english_words_per_dialogue_max": max(words),
              "lines_by_speaker": dict(Counter(beat["speaker"] for beat in dialogue)),
              "vietnamese_subtitle_words_whitespace": sum(len(beat["text_vi"].split()) for beat in dialogue),
              "intended_body_s": body_s, "intended_full_s": 1657, "pilot_excerpt_s": pilot_s,
              "media_timing": "UNVERIFIED"}
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    check()
