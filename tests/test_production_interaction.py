"""P16-02 interaction contract: addressees, listener anchors, marks/blocking, gaze (production/interaction.py)."""
import copy
import json
from pathlib import Path

import pytest

from film_pipeline.production.interaction import ListenerAnchor
from film_pipeline.production.package import load_package
from film_pipeline.production.plan import plan_package
from film_pipeline.production.set_layout import SetLayout

ROOT = Path(__file__).resolve().parents[1]
FILM04 = ROOT / "films" / "film04_last_ticket"
FILES = ("film.json", "script.fountain", "01_story.json", "02_direction.json", "03_preprod.json", "04_shots.json")
LOC = "ticket_office_night"
MARKS = [{"id": "booth_stool", "at": [0.62, 0.30], "zone": "booth"},
         {"id": "hall_window", "at": [0.62, 0.52], "zone": "hall"}]
POSES = {"MARA": {"mark": "booth_stool", "posture": "seated"}, "THEO": {"mark": "hall_window", "posture": "standing"}}
ISSUE_PREFIXES = ("ADDRESSEE_", "LISTENER_ANCHOR_", "ANCHOR_CONTRADICTION", "OFF_FRAME_", "MARK_UNRESOLVED", "GAZE_")


def _load(path):
    return json.loads(path.read_text(encoding="utf-8"))


def _save(path, data):
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def make(tmp_path, *, contract=True, marks=True, addressees=True, shot=None):
    """tmp copy of film04; `shot` patches SC02_g1 (dict update)."""
    root = tmp_path / "film"
    root.mkdir(parents=True)
    for name in FILES:
        (root / name).write_text((FILM04 / name).read_text(encoding="utf-8"), encoding="utf-8")
    pre = _load(root / "03_preprod.json")
    if contract:
        pre["preflight"]["interaction_contract"] = True
    if marks:
        pre["locations"][LOC]["layout"]["marks"] = copy.deepcopy(MARKS)
        for sid in ("SC01_g2", "SC01_end", "SC02_g1", "SC02_g2", "SC02_end"):
            pre["states"][sid]["blocking"] = copy.deepcopy(POSES if sid != "SC01_end" else POSES)
        pre["states"]["SC01_g2"]["blocking"] = {"MARA": POSES["MARA"], "THEO": POSES["THEO"]}
        for sc in ("SC01", "SC02"):
            pre["scenes"][sc]["encounter_id"] = "E1"
    _save(root / "03_preprod.json", pre)
    shots = _load(root / "04_shots.json")
    g = next(x for x in shots["generations"] if x["generation_id"] == "SC02_g1")
    if addressees:
        g["addressees"] = {"22": ["THEO"]}
    g.update(shot or {})
    _save(root / "04_shots.json", shots)
    return root


def checks(root, gid="SC02_g1"):
    pkg = load_package(root)
    res = plan_package(pkg, root / "media" / "plan", storyboard=False)
    gen = json.loads((root / "media" / "plan" / "gate3.json").read_text(encoding="utf-8"))["generations"][gid]
    return {i["check"]: i["severity"] for i in gen["issues"] if i["check"].startswith(ISSUE_PREFIXES)}, res


OFF = {"mode": "OFF_FRAME", "side": "LEFT", "placement": "THEO stands just off frame-left beside the camera",
       "established_by": "SC01_g2"}
CLOSE = {"size": "CLOSE", "angle": "EYE_LEVEL", "height": "CHEST", "movement": "STATIC", "lens_intent": "NORMAL",
         "composition": "close single on MARA"}


def off_frame(tmp_path, anchor=None, camera=None, visible=None):
    cam = {**_camera(), **(camera or CLOSE)}
    return make(tmp_path, shot={"camera": cam, "visible": visible or ["MARA"], "gaze_target": "THEO",
                                "listener_anchors": {"THEO": {**OFF, **(anchor or {})}}})


def _camera():
    shots = _load(FILM04 / "04_shots.json")
    return next(x for x in shots["generations"] if x["generation_id"] == "SC02_g1")["camera"]


def test_contract_off_is_back_compatible(tmp_path):
    found, _ = checks(make(tmp_path, contract=False, marks=False, addressees=False))
    assert found == {}


def test_contract_on_shipped_shot_blocks(tmp_path):
    found, res = checks(make(tmp_path, marks=False, addressees=False))
    assert found["ADDRESSEE_MISSING"] == "BLOCK" and found["MARK_UNRESOLVED"] == "BLOCK"
    assert not res.ok


def test_false_off_frame_claims_block(tmp_path):
    cases = [
        ({"established_by": None}, None, None, "OFF_FRAME_NOT_ESTABLISHED"),
        ({}, {"size": "MEDIUM_CLOSE"}, None, "OFF_FRAME_TOO_WIDE"),
        ({}, None, ["MARA", "THEO"], "ANCHOR_CONTRADICTION"),
        ({"side": "RIGHT"}, None, None, "OFF_FRAME_WRONG_SIDE"),
    ]
    for n, (anchor, camera, visible, want) in enumerate(cases):
        found, _ = checks(off_frame(tmp_path / str(n), anchor, camera, visible))
        assert found.get(want) == "BLOCK", (want, found)


def test_unresolved_mark_blocks(tmp_path):
    root = make(tmp_path)
    pre = _load(root / "03_preprod.json")
    pre["states"]["SC02_g1"]["blocking"]["THEO"]["mark"] = "nowhere"
    _save(root / "03_preprod.json", pre)
    found, _ = checks(root)
    assert found["MARK_UNRESOLVED"] == "BLOCK"


def test_ots_passes(tmp_path):
    root = make(tmp_path, shot={"coverage": "OTS", "foreground": "THEO", "visible": ["MARA", "THEO"],
                                "subject": "MARA", "gaze_target": "THEO",
                                "listener_anchors": {"THEO": {"mode": "OTS_FOREGROUND"}}})
    found, _ = checks(root)
    assert found == {}


def test_legal_off_frame_close_single_passes(tmp_path):
    found, _ = checks(off_frame(tmp_path))
    assert found == {}


def test_single_needs_gaze_target_and_lens_warns(tmp_path):
    found, _ = checks(make(tmp_path, shot={"listener_anchors": {"THEO": OFF}, "camera": {**_camera(), **CLOSE}}))
    assert found["GAZE_TARGET_MISSING"] == "BLOCK"
    found, _ = checks(make(tmp_path / "b", shot={"gaze_target": "LENS"}))
    assert found["GAZE_INTO_LENS"] == "WARN"
    found, _ = checks(make(tmp_path / "c", shot={"gaze_target": "ghost"}))
    assert found["GAZE_TARGET_UNRESOLVED"] == "BLOCK"


def test_addressee_absent_or_speaker(tmp_path):
    found, _ = checks(make(tmp_path, shot={"addressees": {"22": ["MARA"]}}))
    assert found["ADDRESSEE_ABSENT"] == "BLOCK"
    found, _ = checks(make(tmp_path / "b", shot={"addressees": {"22": ["SELF"]}}))
    assert "ADDRESSEE_ABSENT" not in found and "ADDRESSEE_MISSING" not in found


def test_empty_blocking_stays_out_of_dumps(tmp_path):
    pre = _load(FILM04 / "03_preprod.json")
    assert "blocking" not in load_package(make(tmp_path, contract=False, marks=False)).typed["preprod"].states[
        "SC02_g1"].model_dump()
    assert "marks" not in pre["locations"][LOC]["layout"]


def _layout():
    return copy.deepcopy(_load(FILM04 / "03_preprod.json")["locations"][LOC]["layout"])


def test_layout_marks_validate():
    lay = _layout()
    lay["marks"] = copy.deepcopy(MARKS)
    assert len(SetLayout.model_validate(lay).marks) == 2
    dup = copy.deepcopy(lay)
    dup["marks"][0]["id"] = "counter"
    with pytest.raises(ValueError, match="duplicate ids"):
        SetLayout.model_validate(dup)
    bad_zone = copy.deepcopy(lay)
    bad_zone["marks"][0]["zone"] = "attic"
    with pytest.raises(ValueError, match="unknown zone"):
        SetLayout.model_validate(bad_zone)
    off = copy.deepcopy(lay)
    off["marks"][0]["at"] = [1.5, 0.2]
    with pytest.raises(ValueError):
        SetLayout.model_validate(off)


def test_off_frame_anchor_needs_side_and_placement():
    with pytest.raises(ValueError, match="side and a placement"):
        ListenerAnchor(mode="OFF_FRAME")
    with pytest.raises(ValueError, match="side and a placement"):
        ListenerAnchor(mode="OFF_FRAME", side="LEFT")
    assert ListenerAnchor(mode="VISIBLE").side is None
