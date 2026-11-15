"""Still --tighten (crop away from the off-frame listener) and a reframe riding on an accepted take at review ingest."""
import json

import pytest
from PIL import Image

from film_pipeline.production import stills as S
from film_pipeline.production import takes as T
from film_pipeline.production.package import load_package
from test_production_gate_checks import register_all, sheet_pass
from test_production_interaction import make, off_frame

GID = "SC02_g1"
SIZE = (100, 60)


def picture(tmp_path, name="src.png"):
    img = Image.new("RGB", SIZE)
    img.putdata([(x * 2, y * 4, 7) for y in range(SIZE[1]) for x in range(SIZE[0])])
    path = tmp_path / name
    img.save(path)
    return path


def registered(root, tmp_path):
    S.register_still(load_package(root), GID, picture(tmp_path), source="seed")
    return load_package(root)


def record(root):
    return json.loads((root / "03_preprod.json").read_text(encoding="utf-8"))["stills"][GID]


@pytest.mark.parametrize("side,x", [("right", 0.0), ("left", 0.15)])
def test_tighten_box_per_side_keeps_size_and_is_unapproved(tmp_path, side, x):
    root = off_frame(tmp_path)
    pkg = registered(root, tmp_path)
    S.approve_still(pkg, GID, "agent:tech-lead")
    out = S.tighten_still(load_package(root), GID, side=side)
    assert out["box"] == {"x": x, "y": 0.075, "w": 0.85, "h": 0.85} and out["side"] == side
    rec = record(root)
    assert rec["approved_by"] == "" and rec["credits"] == 0
    assert rec["source"].startswith("tighten of media/stills/start_SC02_g1.png") and f"(listener {side})" in rec["source"]
    with Image.open(root / rec["file"]) as img:
        assert img.size == SIZE
    # the left crop starts at x=15 of 100: the top-left pixel carries the source column 15 (LANCZOS blurs, so compare roughly)
    with Image.open(root / rec["file"]) as img:
        assert abs(img.getpixel((0, 30))[0] - x * 100 * 2) < 12


def test_tighten_derives_side_from_off_frame_listener(tmp_path):
    root = off_frame(tmp_path)  # THEO stands off frame-left
    registered(root, tmp_path)
    out = S.tighten_still(load_package(root), GID, scale=0.9, y=2.0)
    assert out["side"] == "left" and out["box"]["x"] == pytest.approx(0.1) and out["box"]["y"] == pytest.approx(0.1)


def test_tighten_without_a_derivable_side_fails(tmp_path):
    root = make(tmp_path)
    registered(root, tmp_path)
    with pytest.raises(ValueError, match="--side"):
        S.tighten_still(load_package(root), GID)
    assert record(root)["source"] == "seed"


@pytest.mark.parametrize("scale", [0.79, 0.96])
def test_tighten_rejects_out_of_range_scale(tmp_path, scale):
    root = off_frame(tmp_path)
    registered(root, tmp_path)
    with pytest.raises(ValueError, match="between 0.80 and 0.95"):
        S.tighten_still(load_package(root), GID, side="left", scale=scale)


# ------------------------------------------------------------------ reframe at review ingest

def take_sheet(tmp_path, reframe=None, result="PASS"):
    from test_production_gate_checks import clone
    root = clone(tmp_path)
    pkg = load_package(root)
    entry = register_all(root, pkg, upto=1)[0]
    sheet = sheet_pass(T.dailies_template(pkg, entry))
    if result == "FAIL":
        sheet["qc"]["checks"][0].update(result="FAIL", severity="P0", note="leak")
    if reframe is not None:
        sheet["reframe"] = reframe
    return root, pkg, entry, sheet


def reframe_file(root):
    return root / "titles" / "reframe.json"


def test_accepted_take_with_reframe_creates_and_merges_reframe_json(tmp_path):
    box = {"x": 0.0, "y": 0.02, "w": 0.96, "h": 0.96}
    root, pkg, entry, sheet = take_sheet(tmp_path, box)
    out = T.ingest_review(root, pkg.header.film_id, sheet)
    assert out["status"] == "ACCEPTED"
    assert json.loads(reframe_file(root).read_text(encoding="utf-8")) == {"events": {entry.generation_id: box}}
    # merge keeps other events (and their extra fields)
    other = {"x": 0.1, "y": 0.1, "w": 0.9, "h": 0.9, "stabilize": True}
    reframe_file(root).write_text(json.dumps({"events": {"OTHER": other}}), encoding="utf-8")
    sheet["reframe"] = {"x": 0.04, "y": 0.0, "w": 0.96, "h": 0.96}
    T.ingest_review(root, pkg.header.film_id, sheet)
    events = json.loads(reframe_file(root).read_text(encoding="utf-8"))["events"]
    assert events["OTHER"] == other and events[entry.generation_id]["x"] == 0.04
    from film_pipeline.production.titles import load_reframes
    assert load_reframes(root).events[entry.generation_id].w == 0.96


@pytest.mark.parametrize("box", [{"x": 0, "y": 0, "w": 0.9, "h": 0.95}, {"x": 0, "y": 0, "w": 0.85, "h": 0.85},
                                 {"x": 0.2, "y": 0, "w": 0.9, "h": 0.9}, {"x": 0, "y": 0, "w": 0.9}])
def test_invalid_reframe_fails_and_writes_nothing(tmp_path, box):
    root, pkg, entry, sheet = take_sheet(tmp_path, box)
    with pytest.raises(ValueError):
        T.ingest_review(root, pkg.header.film_id, sheet)
    assert not reframe_file(root).exists()
    assert T.load_log(root, pkg.header.film_id).get(entry.take_id).status != "ACCEPTED"


def test_rejected_take_with_reframe_is_an_error(tmp_path):
    root, pkg, entry, sheet = take_sheet(tmp_path, {"x": 0, "y": 0, "w": 0.9, "h": 0.9}, result="FAIL")
    with pytest.raises(ValueError, match="ACCEPTED"):
        T.ingest_review(root, pkg.header.film_id, sheet)
    assert not reframe_file(root).exists()
