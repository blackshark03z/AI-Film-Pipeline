"""P16-03: one placement source compiled into the still prompt and the video prompt (contract route only)."""
import json

from film_pipeline.production.package import load_package
from film_pipeline.production.plan import plan_package

from test_production_interaction import FILM04, off_frame, make

OTS_SHOT = {"coverage": "OTS", "foreground": "THEO", "visible": ["MARA", "THEO"], "subject": "MARA",
            "gaze_target": "THEO", "listener_anchors": {"THEO": {"mode": "OTS_FOREGROUND"}}}
OTS_TEXT = "Over THEO's shoulder: the back of THEO's head and one shoulder fill the near frame-left, out of focus"


def plan(root, gid="SC02_g1"):
    res = plan_package(load_package(root), root / "media" / "plan", storyboard=False)
    out = root / "media" / "plan"
    video = (out / "prompts" / f"{gid}.txt").read_text(encoding="utf-8")
    still = (out / "stills" / f"start_{gid}.txt").read_text(encoding="utf-8")
    return video, still, res


def issues(res, gid="SC02_g1"):
    return {i["check"] for i in res.record["generations"][gid]["issues"]}


def test_ots_placement_in_both_prompts(tmp_path):
    video, still, _ = plan(make(tmp_path, shot=OTS_SHOT))
    assert "MARA speaks to THEO." in still and OTS_TEXT in still
    assert "Only MARA in frame" not in still
    # the video prompt maps names to handles: the young man's shoulder, the woman speaks to the young man
    assert "Over the young man's shoulder: the back of the young man's head" in video
    assert "The woman speaks to the young man." in video
    assert "the jar in the young man's hands" in video
    assert "jar" in still and "THEO's hands" in still


def test_off_frame_close_single_places_listener(tmp_path):
    video, still, res = plan(off_frame(tmp_path))
    assert "THEO stands just off frame-left beside the camera." in still
    assert "the young man stands just off frame-left beside the camera." in video.lower()
    assert "MARA's eyes go just past the lens to frame-left." in still
    assert "The woman's eyes go just past the lens to frame-left." in video
    assert "Only MARA in frame" not in still
    assert "the jar" not in video and "young man's hands" not in video
    assert "close-up of the woman" in video
    assert still.startswith("Photoreal film still, 16:9, close-up: close-up of MARA")
    assert "HIDDEN_PERSON_UNPLACED" not in issues(res)


def test_hidden_person_unplaced_blocks(tmp_path):
    # THEO is in the room, out of frame, named by the authored text and anchored nowhere
    root = make(tmp_path, shot={"gaze_target": "THEO"})
    shots = json.loads((root / "04_shots.json").read_text(encoding="utf-8"))
    g = next(x for x in shots["generations"] if x["generation_id"] == "SC02_g1")
    assert g["visible"] == ["MARA"]
    _, _, res = plan(root)
    assert "HIDDEN_PERSON_UNPLACED" in issues(res)


def test_contract_off_prompts_are_unchanged(tmp_path):
    root = make(tmp_path, contract=False, marks=False, addressees=False)
    video, still, _ = plan(root)
    shipped = FILM04 / "media" / "plan"
    assert video == (shipped / "prompts" / "SC02_g1.txt").read_text(encoding="utf-8")
    assert still == (shipped / "stills" / "start_SC02_g1.txt").read_text(encoding="utf-8")
