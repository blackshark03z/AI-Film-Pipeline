"""Generability rating (P15-01): film04 beats must rate as the 2026-11-08 shot quality review says."""
import json
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

from film_pipeline.drama.generability import generability_issues, rate_shot
from film_pipeline.production.sections import ShotDecl

ROOT = Path(__file__).resolve().parents[1]
FILM04 = ROOT / "films" / "film04_last_ticket"
TOOL = ROOT / "tools" / "film.py"
FILES = ("film.json", "script.fountain", "01_story.json", "02_direction.json", "03_preprod.json", "04_shots.json")


def shot(gid, phases, visible=("MARA",), tracked=None, waiver=""):
    ph = [{"kind": k, "start_s": float(i), "end_s": float(i + 1), "description": d, **({"motion": m} if m else {})}
          for i, (k, d, m) in enumerate(phases)]
    return ShotDecl.model_validate({
        "generation_id": gid, "scene_id": gid[:4], "coverage": "SINGLE", "visible": list(visible), "dialogue": [],
        "start_state": gid, "end_state": gid, "choreography": {"generation_id": gid, "phases": ph},
        "tracked": tracked, "generability_waiver": waiver})


def still(obj="shutter"):
    return {"object": obj, "roi": [0.1, 0.1, 0.5, 0.5], "axis": "y", "direction": "still"}


def rules(decl):
    return {f.rule for f in rate_shot(decl).findings}


CASES = [
    ("SC01_g1", [("SETUP", "MARA stands inside the booth, her fingers hooked under the bottom edge of the raised shutter", None),
                 ("ACTION", "she pulls the shutter down in one smooth pull until its bottom edge comes to rest on the brass catches",
                  "lower_roll_shutter_partial"),
                 ("HOLD", "her hands rest on the shutter's bottom edge; nothing moves", None)],
     ("MARA",), None, "RED", {"PARTIAL_MECHANISM"}),
    ("SC01_g2", [("ACTION", "THEO pushes the glass door open with one hand and steps in out of the rain", "open_door"),
                 ("ACTION", "he hurries across the hall and stops at the counter", "walk_across_room"),
                 ("ACTION", "he stoops until his face is level with the open gap under the shutter's bottom edge and speaks", None)],
     ("MARA", "THEO"), None, "RED", {"BODY_INTO_FIXED_GAP", "DOOR", "LOCOMOTION"}),
    ("SC02_g1", [("ACTION", "MARA, already seated on her stool with her face in the open gap, glances at the wall clock "
                  "and back at him over her glasses", "turn_head"),
                 ("ACTION", "she speaks to him through the gap", None), ("HOLD", "she holds a level look", None)],
     ("MARA",), still(), "GREEN", set()),
    ("SC02_g1", [("ACTION", "MARA, standing behind the counter with her hands at her sides, sits down on her stool, which "
                  "brings her face level with the open gap above the counter", "sit_down")],
     ("MARA",), still(), "RED", {"BODY_VS_PINNED_PROP", "BODY_INTO_FIXED_GAP"}),
    ("SC02_g2", [("SETUP", "THEO glances at the platform door behind him, then back at the window", None),
                 ("ACTION", "he speaks, the jar held against his chest", None)], ("THEO",), None, "GREEN", set()),
    ("SC03_g1", [("SETUP", "THEO stands at the window, the jar held to his chest", None),
                 ("ACTION", "he sets the jar on the counter and speaks, hands flat", None),
                 ("HOLD", "MARA stays still behind the counter", None)], ("MARA", "THEO"), None, "AMBER",
     {"PLACE_OBJECT", "TWO_PEOPLE_ACTION"}),
    ("SC03_g2", [("SETUP", "MARA looks down at the jar of coins", None), ("ACTION", "she looks up at the clock and speaks", None),
                 ("REACTION", "she looks back at THEO and weighs it", None)], ("MARA",), None, "GREEN", set()),
    ("SC04_g1", [("ACTION", "she takes off her glasses and lets them hang on their chain", None)], ("MARA",), None, "RED",
     {"HANDS_SMALL_OBJECTS"}),
    ("SC04_g2", [("ACTION", "she pushes the shutter up and speaks", None),
                 ("CONSEQUENCE", "THEO tips the jar; the coins pour into the tray", None)], ("MARA", "THEO"), None, "RED",
     {"PARTIAL_MECHANISM", "POURING"}),
    ("SC05_g1", [("SETUP", "MARA sorts the coins into small stacks with quick fingers", None),
                 ("ACTION", "she counts the coins aloud and speaks", None)], ("MARA",), None, "RED", {"HANDS_SMALL_OBJECTS"}),
    ("SC05_g2", [("SETUP", "MARA lifts the date stamp over the ticket", None),
                 ("ACTION", "she stamps the ticket and lays it on the counter", None)], ("MARA", "THEO"), None, "RED",
     {"HANDS_SMALL_OBJECTS"}),
    ("SC06_g1", [("ACTION", "MARA walks out of the office behind THEO, the suitcase at her side", None)],
     ("MARA", "THEO"), None, "AMBER", {"LOCOMOTION"}),
    ("SC06_g2", [("SETUP", "THEO and MARA stand side by side as the train doors slide open", None),
                 ("ACTION", "MARA speaks, eyes on the train", None)], ("MARA", "THEO"), None, "AMBER", {"DOOR"}),
]


@pytest.mark.parametrize("gid,phases,visible,tracked,level,expect", CASES, ids=[f"{c[0]}-{c[4]}-{i}" for i, c in enumerate(CASES)])
def test_film04_beats(gid, phases, visible, tracked, level, expect):
    decl = shot(gid, phases, visible, tracked)
    rating = rate_shot(decl)
    assert rating.level == level
    assert expect <= rules(decl)
    assert rating.drafts == {"GREEN": 1, "AMBER": 2, "RED": 3}[level]


def test_red_blocks_unless_waived():
    phases = [("ACTION", "she pushes the shutter up", None)]
    rating, issues = generability_issues(shot("SC04_g2", phases))
    assert rating.level == "RED" and [(i.check, i.severity) for i in issues] == [("GENERABILITY_RED", "BLOCK")]
    _, waived = generability_issues(shot("SC04_g2", phases, waiver="restaged as a prop-only insert"))
    assert [(i.check, i.severity) for i in waived] == [("GENERABILITY_RED_WAIVED", "WARN")]


def test_amber_warns_and_green_is_silent():
    _, amber = generability_issues(shot("SC06_g1", [("ACTION", "she walks out", None)]))
    assert [(i.check, i.severity) for i in amber] == [("GENERABILITY_AMBER", "WARN")]
    assert generability_issues(shot("SC02_g2", [("ACTION", "he speaks", None)]))[1] == []


@pytest.mark.parametrize("text", ["light spills across the floor", "she crosses her arms", "she stands behind the counter",
                                  "he glances at the door behind him"])
def test_no_false_hits(text):
    assert rate_shot(shot("SC01_g1", [("ACTION", text, None)])).level == "GREEN"


def test_cli_on_film04_copy(tmp_path):
    film = tmp_path / "film04"
    film.mkdir()
    for name in FILES:
        shutil.copy(FILM04 / name, film / name)
    proc = subprocess.run([sys.executable, str(TOOL), "generability", "--film", str(film)], capture_output=True,
                          text=True, encoding="utf-8", env={**__import__("os").environ, "PYTHONPATH": str(ROOT / "src")})
    assert proc.returncode == 0, proc.stderr
    out = json.loads(proc.stdout)
    assert out["SC01_g1"]["level"] == "RED" and out["SC01_g1"]["waiver"]
    assert out["SC02_g1"]["level"] == "GREEN" and out["SC02_g1"]["drafts"] == 1
    assert {"level", "findings", "drafts"} <= set(out["SC04_g2"])
