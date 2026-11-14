"""P16-03: one placement source compiled into the still prompt and the video prompt (contract route only)."""
import json

from film_pipeline.production.package import load_package
from film_pipeline.production.plan import plan_package

from test_production_interaction import OFF as OFF_ANCHOR, off_frame, make

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
    # contract off: authored marks/blocking/addressees/anchors/gaze are inert, the prompts equal the plain v3 film04's
    # (the shipped media/plan is local state of the pilot now, so the baseline is rebuilt here, not read from it)
    video, still, _ = plan(make(tmp_path / "bare", contract=False, marks=False, addressees=False))
    video2, still2, _ = plan(make(tmp_path / "authored", contract=False, marks=True, addressees=True,
                                  shot={"gaze_target": "THEO", "listener_anchors": {"THEO": OFF_ANCHOR}}))
    assert video == video2 and still == still2


def test_clear_eyeline_scene_keeps_eyes_off_the_lens(tmp_path):
    # film08 SC02 rejects: NAOMI singles stared into the lens or pulled the off-frame listener in at the edge
    root = off_frame(tmp_path)
    pre = json.loads((root / "03_preprod.json").read_text(encoding="utf-8"))
    pre["preflight"]["clear_eyeline_scenes"] = ["SC02"]
    (root / "03_preprod.json").write_text(json.dumps(pre, indent=2), encoding="utf-8")
    video, still, _ = plan(root)
    assert "just past the lens" not in video and "just past the lens" not in still
    assert "MARA faces a quarter toward frame-left, eyes on THEO, well clear of the lens." in still
    assert "The frame-left edge shows only the room." in still
    assert "the woman faces a quarter toward frame-left, eyes on the young man, well clear of the lens." in video.lower()


def test_clear_eyeline_by_generation_id(tmp_path):
    # film08 SC02_g11: restage one shot after 3 rejects without changing the accepted shots' prompts in the scene
    root = off_frame(tmp_path)
    pre = json.loads((root / "03_preprod.json").read_text(encoding="utf-8"))
    pre["preflight"]["clear_eyeline_scenes"] = ["SC02_g1"]
    (root / "03_preprod.json").write_text(json.dumps(pre, indent=2), encoding="utf-8")
    video, still, _ = plan(root)
    assert "just past the lens" not in video
    assert "The frame-left edge shows only the room." in still
    pre["preflight"]["clear_eyeline_scenes"] = ["SC02_g9"]
    (root / "03_preprod.json").write_text(json.dumps(pre, indent=2), encoding="utf-8")
    video, _, _ = plan(root)
    assert "The woman's eyes go just past the lens to frame-left." in video


def test_listener_unplaced_drops_the_listeners_spot(tmp_path):
    # film08 SC02: 3 of 7 HOLLIS singles drew ELI at the frame-right edge; each prompt named ELI's spot by the door
    root = off_frame(tmp_path)
    pre = json.loads((root / "03_preprod.json").read_text(encoding="utf-8"))
    pre["preflight"]["safeguard_scenes"] = ["SC02"]
    pre["preflight"]["clear_eyeline_scenes"] = ["SC02"]
    (root / "03_preprod.json").write_text(json.dumps(pre, indent=2), encoding="utf-8")
    placed_video, placed_still, _ = plan(root)
    assert "beside the camera" in placed_video and "stays fully out of frame" in placed_video
    pre["preflight"]["listener_unplaced_scenes"] = ["SC02"]
    (root / "03_preprod.json").write_text(json.dumps(pre, indent=2), encoding="utf-8")
    video, still, res = plan(root)
    for text in (video, still):
        assert "beside the camera" not in text and "stays fully out of frame" not in text
        assert "just past the lens" not in text
    assert "MARA faces a quarter toward frame-left, eyes on THEO, well clear of the lens." in still
    assert "Only MARA is in frame; the frame-left edge shows only the room." in still
    assert "Only the woman is in frame; the frame-left edge shows only the room." in video
    assert len(video.split()) < len(placed_video.split())
    assert "HIDDEN_PERSON_UNPLACED" not in issues(res)


def test_listener_unplaced_needs_the_clear_eyeline(tmp_path):
    # the option only narrows clear-eyeline singles; alone it changes nothing (accepted hashes elsewhere stay put)
    root = off_frame(tmp_path)
    before = plan(root)[:2]
    pre = json.loads((root / "03_preprod.json").read_text(encoding="utf-8"))
    pre["preflight"]["listener_unplaced_scenes"] = ["SC02"]
    (root / "03_preprod.json").write_text(json.dumps(pre, indent=2), encoding="utf-8")
    assert plan(root)[:2] == before


def _clear_eyeline_pkg(tmp_path):
    root = off_frame(tmp_path)
    pre = json.loads((root / "03_preprod.json").read_text(encoding="utf-8"))
    pre["preflight"]["clear_eyeline_scenes"] = ["SC02"]
    (root / "03_preprod.json").write_text(json.dumps(pre, indent=2), encoding="utf-8")
    return load_package(root)


def test_still_checks_ask_eyeline_and_corner_marks(tmp_path):
    # film08 pilot: S07 v2 had eyes on the lens (lens stares in 3 takes); no review looked at the corner sparkle
    from film_pipeline.production.stills import still_checks_for
    from film_pipeline.production.takes import CORNER_MARK_QUESTION
    pkg = _clear_eyeline_pkg(tmp_path)
    checks = {c["id"]: c for c in still_checks_for(pkg, "SC02_g1")}
    assert set(checks) == {"STILL_EYELINE", "STILL_CORNER_MARK"}
    assert "off the lens; MARA's head turned a quarter toward frame-left" in checks["STILL_EYELINE"]["question"]
    assert checks["STILL_CORNER_MARK"]["question"] == CORNER_MARK_QUESTION
    assert still_checks_for(pkg, "end:SC02_g1") == still_checks_for(pkg, "SC02_g1")
    assert still_checks_for(pkg, "SC99_g1") == []


def test_take_review_asks_corners_and_clear_eyeline(tmp_path):
    from film_pipeline.production.relation_review import relation_questions
    from film_pipeline.production.takes import CORNER_MARK_QUESTION, _questions
    pkg = _clear_eyeline_pkg(tmp_path)
    pre = pkg.typed["preprod"]
    decl = next(g for g in pkg.typed["shots"].generations if g.generation_id == "SC02_g1")
    assert CORNER_MARK_QUESTION in [q["question"] for q in _questions(decl, pre, {})]
    listener = next(q for q in relation_questions(pre, decl, {}) if q["id"] == "REL_LISTENER:THEO")
    assert "eyes go to frame-left, well clear of the lens?" in listener["question"]
    pre.preflight.clear_eyeline_scenes = []
    listener = next(q for q in relation_questions(pre, decl, {}) if q["id"] == "REL_LISTENER:THEO")
    assert "just past the lens to frame-left" in listener["question"]


def test_listener_unplaced_object_gaze_says_only_subject(tmp_path):
    # film08 SC09_g24/SC10_g01: the subject looks at a prop; the listener's spot is left unsaid there too
    root = off_frame(tmp_path)
    shots = json.loads((root / "04_shots.json").read_text(encoding="utf-8"))
    next(g for g in shots["generations"] if g["generation_id"] == "SC02_g1")["gaze_target"] = "counter"
    (root / "04_shots.json").write_text(json.dumps(shots, indent=2), encoding="utf-8")
    pre = json.loads((root / "03_preprod.json").read_text(encoding="utf-8"))
    pre["preflight"].update(safeguard_scenes=["SC02"], clear_eyeline_scenes=["SC02"], listener_unplaced_scenes=["SC02"])
    (root / "03_preprod.json").write_text(json.dumps(pre, indent=2), encoding="utf-8")
    video, still, _ = plan(root)
    assert "MARA looks at the wooden counter. Only MARA is in frame." in still
    assert "Only the woman is in frame." in video
    for text in (video, still):
        assert "beside the camera" not in text and "stays fully out of frame" not in text
        assert "well clear of the lens" not in text and "edge shows only the room" not in text
