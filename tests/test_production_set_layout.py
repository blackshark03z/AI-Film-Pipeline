import json
from pathlib import Path

import pytest

from film_pipeline.production import takes as T
from film_pipeline.production.package import load_package
from film_pipeline.production.plan import plan_package
from film_pipeline.production.set_layout import SetLayout, layout_issues

ROOT = Path(__file__).resolve().parents[1] / "films"
FILM04 = ROOT / "film04_last_ticket"
FILM03 = ROOT / "film03_front_desk"
FILES = ("film.json", "script.fountain", "01_story.json", "02_direction.json", "03_preprod.json", "04_shots.json",
         "05_edit.json", "06_post.json", "07_delivery.json", "ledger.json")
OFFICE = "ticket_office_night"


def layout_data():
    return {
        "zones": [{"id": "booth", "label": "clerk booth (staff side)", "box": [0.0, 0.0, 1.0, 0.4]},
                  {"id": "hall", "label": "public hall", "box": [0.0, 0.5, 1.0, 1.0]}],
        "objects": [
            {"id": "window", "label": "ticket window", "zone": "booth",
             "placement": "set in the wall between the booth and the hall", "at": [0.5, 0.45]},
            {"id": "shutter", "label": "roll-down shutter", "zone": "booth",
             "placement": "mounted above the ticket window, rolls down over its glass",
             "operation": "pulled down by the handle on its bottom edge", "at": [0.5, 0.35]},
            {"id": "clock", "label": "wall clock", "zone": "booth", "placement": "on the back wall of the booth",
             "at": [0.9, 0.05]}],
        "cameras": [
            {"id": "A", "zone": "hall", "view": "From the public hall, facing the ticket window",
             "sees": ["window", "shutter"], "at": [0.5, 0.9], "look_at": "window"},
            {"id": "B", "zone": "booth", "view": "From inside the booth, facing the clock",
             "sees": ["clock"], "at": [0.2, 0.1], "look_at": "clock"}]}


def add_layout(pre):
    pre["locations"][OFFICE]["layout"] = layout_data()


def add_positions(shots):
    for g in shots["generations"]:
        if g["scene_id"] != "SC06":
            g["camera_position"] = "A"
        g["readout"] = [{"fact": "the office is closing", "evidence": [g["visible"][0]], "min_size": "WIDE"}]
    shots["generations"][0]["readout"] = [
        {"fact": "the shutter comes down", "evidence": ["shutter", "MARA"], "min_size": "MEDIUM_CLOSE"}]


def clone(tmp_path, pre=add_layout, shots=add_positions, root=FILM04):
    for name in FILES:
        if (root / name).is_file():
            (tmp_path / name).write_text((root / name).read_text(encoding="utf-8"), encoding="utf-8")
    for name, mutate in (("03_preprod.json", pre), ("04_shots.json", shots)):
        data = json.loads((tmp_path / name).read_text(encoding="utf-8"))
        # start from a film04 without its own layout / readouts, so every test states what it adds
        if name == "03_preprod.json":
            data.pop("stills", None)
            for loc in data["locations"].values():
                loc.pop("layout", None)
        else:
            for g in data["generations"]:
                g.pop("camera_position", None)
                g.pop("readout", None)
        if mutate:
            mutate(data)
        (tmp_path / name).write_text(json.dumps(data), encoding="utf-8")
    return load_package(tmp_path)


def issues(pkg):
    assert pkg.issues == [], pkg.issues
    return layout_issues(pkg.typed["preprod"], pkg.typed["shots"])


def checks(found):
    return [i.check for i in found]


def first(shots):
    return shots["generations"][0]


# ---- model validation ---------------------------------------------------------------------------------------

def broken(mutate):
    data = layout_data()
    mutate(data)
    with pytest.raises(ValueError):
        SetLayout.model_validate(data)


def test_valid_layout_loads():
    assert SetLayout.model_validate(layout_data()).drawable()


def test_duplicate_id_is_rejected():
    broken(lambda d: d["objects"][0].update(id="booth"))


def test_unknown_zone_is_rejected():
    broken(lambda d: d["objects"][0].update(zone="nowhere"))
    broken(lambda d: d["cameras"][0].update(zone="nowhere"))


def test_unknown_sees_or_look_at_is_rejected():
    broken(lambda d: d["cameras"][0].update(sees=["ghost"]))
    broken(lambda d: d["cameras"][0].update(look_at="ghost"))


def test_coordinates_out_of_range_are_rejected():
    broken(lambda d: d["objects"][0].update(at=[1.5, 0.5]))
    broken(lambda d: d["zones"][0].update(box=[0.0, 0.0, 1.2, 0.4]))
    broken(lambda d: d["zones"][0].update(box=[0.6, 0.0, 0.4, 0.4]))


def test_empty_zones_or_cameras_are_rejected():
    broken(lambda d: d.update(zones=[], objects=[], cameras=[]))
    broken(lambda d: d.update(cameras=[]))


def test_invalid_layout_surfaces_as_package_issue(tmp_path):
    def bad(pre):
        add_layout(pre)
        pre["locations"][OFFICE]["layout"]["cameras"][0]["sees"] = ["ghost"]
    assert clone(tmp_path, pre=bad, shots=None).issues


def test_view_text_order_and_operation():
    layout = SetLayout.model_validate(layout_data())
    assert layout.view_text("A") == (
        "From the public hall, facing the ticket window. "
        "The ticket window is set in the wall between the booth and the hall. "
        "The roll-down shutter is mounted above the ticket window, rolls down over its glass. "
        "The roll-down shutter is pulled down by the handle on its bottom edge.")
    assert layout.view_text("B").endswith("The wall clock is on the back wall of the booth.")
    assert "shutter" not in layout.view_text("B")


def test_unseen_text_names_objects_out_of_frame():
    # film04 plate B: the location text names the clock, camera B does not see it, the model drew a second one
    layout = SetLayout.model_validate(layout_data())
    assert layout.unseen_text("A") == "Out of frame, not shown: the wall clock."
    assert layout.unseen_text("B") == "Out of frame, not shown: the ticket window, the roll-down shutter."
    assert layout.unseen_text("nope") == ""


def test_operated_from_tells_which_side_the_hand_stays_on():
    # film04 SC01_g1 still: the clerk's hand reached through the glass to a hall-side shutter handle
    data = layout_data()
    next(o for o in data["objects"] if o["id"] == "shutter")["operated_from"] = "booth"
    layout = SetLayout.model_validate(data)
    assert layout.view_text("A").endswith(
        "It is worked only from the clerk booth (staff side), the far side from the camera: "
        "the hand on it stays on that side and never reaches through to the camera's side.")
    data["cameras"][1]["sees"] = ["clock", "shutter"]
    assert "It is worked from the clerk booth (staff side), the camera's side." in \
        SetLayout.model_validate(data).view_text("B")
    next(o for o in data["objects"] if o["id"] == "shutter")["operated_from"] = "roof"
    with pytest.raises(ValueError, match="operated from unknown zone"):
        SetLayout.model_validate(data)


# ---- rules --------------------------------------------------------------------------------------------------

def test_clean_layout_has_no_issues(tmp_path):
    assert issues(clone(tmp_path)) == []


def test_camera_position_without_layout(tmp_path):
    def shots(s):
        add_positions(s)
        s["generations"][-1]["camera_position"] = "A"  # SC06 is on the platform, which has no layout
    found = issues(clone(tmp_path, shots=shots))
    assert checks(found) == ["LAYOUT_CAMERA"] and found[0].detail.startswith("SC06_g2:")


def test_unknown_camera_position(tmp_path):
    def shots(s):
        add_positions(s)
        first(s)["camera_position"] = "Z"
    found = issues(clone(tmp_path, shots=shots))
    assert checks(found)[0] == "LAYOUT_CAMERA" and "SC01_g1" in found[0].detail  # shutter evidence then has no view


def test_layout_without_camera_position(tmp_path):
    def shots(s):
        add_positions(s)
        first(s).pop("camera_position")
    found = issues(clone(tmp_path, shots=shots))
    assert checks(found)[0] == "LAYOUT_CAMERA" and "A, B" in found[0].detail


def test_readout_missing_once_any_declared(tmp_path):
    def shots(s):
        add_positions(s)
        first(s)["readout"] = []
    found = issues(clone(tmp_path, shots=shots))
    assert checks(found) == ["READOUT_MISSING"] and found[0].detail.startswith("SC01_g1:")


def test_no_readout_anywhere_is_not_forced(tmp_path):
    def shots(s):
        add_positions(s)
        for g in s["generations"]:
            g["readout"] = []
    assert issues(clone(tmp_path, shots=shots)) == []


def test_readout_evidence_object_out_of_view(tmp_path):
    def shots(s):
        add_positions(s)
        first(s)["readout"][0]["evidence"] = ["clock"]  # exists in the set but camera A does not see it
    found = issues(clone(tmp_path, shots=shots))
    assert checks(found) == ["READOUT_EVIDENCE"] and "outside" in found[0].detail and "'clock'" in found[0].detail


def test_readout_evidence_unknown(tmp_path):
    def shots(s):
        add_positions(s)
        first(s)["readout"][0]["evidence"] = ["unicorn"]
    found = issues(clone(tmp_path, shots=shots))
    assert checks(found) == ["READOUT_EVIDENCE"] and "'unicorn'" in found[0].detail and "outside" not in found[0].detail


def test_readout_size_too_wide(tmp_path):
    def shots(s):
        add_positions(s)
        first(s)["readout"][0]["min_size"] = "CLOSE"  # the shot is MEDIUM_CLOSE
    found = issues(clone(tmp_path, shots=shots))
    assert checks(found) == ["READOUT_SIZE"]
    assert "needs CLOSE or closer, the shot is MEDIUM_CLOSE" in found[0].detail


def test_film03_has_no_layout_issues():
    pkg = load_package(FILM03)
    assert pkg.issues == []
    assert layout_issues(pkg.typed["preprod"], pkg.typed["shots"]) == []


# ---- plan ---------------------------------------------------------------------------------------------------

def test_plan_writes_camera_plate_and_still_prompt(tmp_path):
    (tmp_path / "film").mkdir()
    pkg = clone(tmp_path / "film")
    out = tmp_path / "out"
    result = plan_package(pkg, out, storyboard=False)
    view = SetLayout.model_validate(layout_data()).view_text("A")
    plate = (out / "stills" / f"plate_{OFFICE}_A.txt").read_text(encoding="utf-8")
    assert view in plate
    assert "Out of frame, not shown: the wall clock. " in plate and ".." not in plate
    assert (out / "stills" / f"plate_{OFFICE}.txt").is_file()
    assert (out / "stills" / f"plate_{OFFICE}_B.txt").is_file()
    assert view in (out / "stills" / "start_SC01_g1.txt").read_text(encoding="utf-8")
    assert "layout" not in result.record
    assert not (out / "layout").exists()


def test_plan_records_layout_findings(tmp_path):
    def shots(s):
        add_positions(s)
        first(s).pop("camera_position")
    (tmp_path / "film").mkdir()
    pkg = clone(tmp_path / "film", shots=shots)
    result = plan_package(pkg, tmp_path / "out", storyboard=False)
    assert result.record["layout"][0]["check"] == "LAYOUT_CAMERA"
    assert any(p.startswith("LAYOUT LAYOUT_CAMERA") for p in result.problems)


def test_plan_renders_floor_plan_with_storyboard(tmp_path):
    pytest.importorskip("PIL")
    (tmp_path / "film").mkdir()
    pkg = clone(tmp_path / "film")
    out = tmp_path / "out"
    plan_package(pkg, out, storyboard=True)
    png = out / "layout" / f"{OFFICE}.png"
    assert png.is_file() and png.stat().st_size > 0
    again = tmp_path / "out2"
    plan_package(pkg, again, storyboard=True)
    assert (again / "layout" / f"{OFFICE}.png").read_bytes() == png.read_bytes()


def test_film_without_layout_writes_no_layout_artifacts(tmp_path):
    (tmp_path / "film").mkdir()
    pkg = clone(tmp_path / "film", pre=lambda p: None, shots=None)
    out = tmp_path / "out"
    result = plan_package(pkg, out, storyboard=False)
    assert "layout" not in result.record
    assert sorted(p.name for p in (out / "stills").glob("plate_*")) == [
        "plate_platform_night.txt", f"plate_{OFFICE}.txt"]


# ---- dailies ------------------------------------------------------------------------------------------------

def test_dailies_questions_include_readout(tmp_path):
    (tmp_path / "film").mkdir()
    pkg = clone(tmp_path / "film")
    entry = T.TakeEntry(take_id="SC01_g1_t1", generation_id="SC01_g1", prompt_sha256="0" * 64, route="test",
                        model="test", credits=0, output_file="x.mp4", output_sha256="1" * 64)
    questions = T.dailies_template(pkg, entry)["questions"]
    assert questions[0] == {"group": "narrative",
                            "question": "Viewer reads: the shutter comes down - carried by: roll-down shutter, MARA"}
    assert questions[1]["group"] != "narrative"
