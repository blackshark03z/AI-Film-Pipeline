"""P0-04: films/film03_front_desk loads cleanly and matches the declarations in tools/drama_film03*.py."""
import importlib
import sys
from pathlib import Path

import pytest

from film_pipeline.production.gates import evaluate_gates
from film_pipeline.production.package import load_package

ROOT = Path(__file__).resolve().parents[1]
PKG = ROOT / "films" / "film03_front_desk"


@pytest.fixture(scope="module")
def pkg():
    return load_package(PKG)


@pytest.fixture(scope="module")
def legacy():
    old = Path.cwd()
    import os
    os.chdir(ROOT)  # the legacy tool reads docs/ relative to the repo root
    sys.path[:0] = [str(ROOT / "tools"), str(ROOT / "src")]
    try:
        yield importlib.import_module("drama_film03"), importlib.import_module("drama_film03_story")
    finally:
        os.chdir(old)
        del sys.path[:2]


def test_loads_with_zero_schema_errors(pkg):
    assert pkg.issues == []
    assert set(pkg.typed) == {"story", "direction", "preprod", "shots", "edit"}  # edit: added by the P7-02 re-run
    assert pkg.script is not None and len(pkg.script.scenes) == 8
    assert pkg.header.profile == "drama" and pkg.header.generation_s == 8


def test_gates_report_only_unvalidated_and_missing_stages(pkg):
    res = {r.gate: r for r in evaluate_gates(pkg)}
    assert res["2"].status == "PASS"  # 02_direction.json checked against story + shots
    assert res["3"].status == res["4"].status == "NOT_RUN"  # present, no validator yet
    assert res["1"].status == "PASS" and res["1"].issues == []  # real checks: 01_story.json + script scenes


def test_shots_match_legacy(pkg, legacy):
    f, st = legacy
    gens = pkg.typed["shots"].generations
    assert [g.generation_id for g in gens] == st.TAKES_ORDER
    for g in gens:
        cov, subject, fg, visible = f.SHOTS[g.generation_id]
        assert (g.coverage, g.subject, g.foreground, g.visible) == (cov, subject, fg, list(visible))
        assert g.choreography == f.CHOREO[g.generation_id]
        assert g.sfx == f.SFX.get(g.generation_id, [])
        assert g.end_state == f.END[g.generation_id]
        assert g.start_state in f.STATE and g.end_state in f.STATE
    firsts = [g.generation_id for g in gens if g.previous_generation_id is None]
    assert firsts == ["SC01_g1", "SC07_g1"]
    for g in gens:
        if g.previous_generation_id:
            assert g.previous_generation_id == st.TAKES_ORDER[st.TAKES_ORDER.index(g.generation_id) - 1]


def test_preprod_matches_legacy(pkg, legacy):
    f, _ = legacy
    pre = pkg.typed["preprod"]
    assert pre.states == f.STATE
    assert pre.feasibility == f.FEAS and pre.preflight == f.LIMITS
    for name, spec in pre.characters.items():
        assert spec.look == f.LOOKS[name]
        assert spec.video_text == f.VIDEO_LOOKS[name].text and spec.voice == f.VOICE[name]
    for sid, scene in pre.scenes.items():
        loc = f.LOCATION[sid]
        assert pre.locations[scene.location].look == loc
        assert pre.locations[scene.location].room_tone == f.ROOM_TONE[sid]
        assert scene.axis == f.BOOK[sid] and scene.occupancy == f.OCCUPANCY[sid]
        assert scene.story_time == f.STORY[int(sid[-1]) - 1]
        assert scene.extras == f.EXTRAS.get(sid, "")
    t = pre.still_templates
    assert (t.framing, t.character, t.plate) == (f.FRAMING, f.CHAR_STILL, f.PLATE)


def test_direction_matches_legacy(pkg, legacy):
    _, st = legacy
    d = pkg.typed["direction"]
    c = d.comprehension
    assert (c.intros, c.facts, c.tags, c.cards) == (st.INTROS, st.FACTS, st.TAGS, st.CARDS)
    assert d.translations == st.VI


def test_script_identical_to_source(pkg):
    src = (ROOT / "docs" / "drama" / "film03_front_desk.fountain").read_text(encoding="utf-8")
    assert (PKG / "script.fountain").read_text(encoding="utf-8") == src


def test_broken_reference_is_reported(tmp_path, pkg):
    import json
    import shutil
    shutil.copytree(PKG, tmp_path / "p")
    path = tmp_path / "p" / "03_preprod.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    data["scenes"]["SC01"]["location"] = "nowhere"
    path.write_text(json.dumps(data), encoding="utf-8")
    broken = load_package(tmp_path / "p")
    assert any("unknown location" in i for i in broken.issues) and "preprod" not in broken.typed
    assert {r.gate: r for r in evaluate_gates(broken)}["3"].status == "BLOCK"
