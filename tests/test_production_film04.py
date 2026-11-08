"""P8-01: films/film04_last_ticket - authored from scratch through the package, nothing generated.

Checks the decisions the package makes (gates, plan, budget), not the story's quality: that is an Owner call."""
import json
import re
import subprocess
import sys
from pathlib import Path

import pytest

from film_pipeline.production.gates import evaluate_gates
from film_pipeline.production.package import load_package

ROOT = Path(__file__).resolve().parents[1]
PKG = ROOT / "films" / "film04_last_ticket"
FILM = [sys.executable, str(ROOT / "tools" / "film.py")]
MAX_WORDS = 215
OPEN_OVERLONG = set()  # P13-04: the start-frame prompt style brought every prompt under the limit


def run(*args):
    return subprocess.run([*FILM, *args], capture_output=True, text=True, encoding="utf-8", cwd=ROOT,
                          env={**__import__("os").environ, "PYTHONPATH": str(ROOT / "src"), "PYTHONIOENCODING": "utf-8"})


FILES = ("film.json", "script.fountain", "01_story.json", "02_direction.json", "03_preprod.json", "04_shots.json",
         "05_edit.json", "06_post.json", "07_delivery.json", "ledger.json")


@pytest.fixture(scope="module")
def pkg(tmp_path_factory):
    # a copy of the stage files only: media/ (plan, stills, takes) is local, git-ignored state of whoever ran the film
    root = tmp_path_factory.mktemp("film04_pkg")
    for name in FILES:
        (root / name).write_bytes((PKG / name).read_bytes())
    return load_package(root)


@pytest.fixture(scope="module")
def plan(tmp_path_factory):
    out = tmp_path_factory.mktemp("film04_plan")
    done = run("plan", "--film", str(PKG), "--out", str(out))
    return done, json.loads((out / "gate3.json").read_text(encoding="utf-8")), out


def test_loads_clean_with_the_four_authored_stages(pkg):
    assert pkg.issues == []
    assert set(pkg.typed) == {"story", "direction", "preprod", "shots"}
    assert len(pkg.script.scenes) == 6 and len(pkg.typed["shots"].generations) == 12
    assert pkg.header.profile == "drama" and pkg.header.generation_s == 8


def test_gates_1_and_2_pass_and_the_rest_are_not_claimed(pkg):
    res = {r.gate: r for r in evaluate_gates(pkg)}
    assert res["1"].status == res["2"].status == "PASS"
    assert res["3"].status in ("BLOCK", "OWNER_PENDING")  # P10-01: the plan record decides; only the storyboard is the Owner's
    assert res["4"].status == "BLOCK" and "no take of shot version" in res["4"].issues[0]  # nothing generated
    assert res["5"].status == res["6"].status == "BLOCK"  # nothing shot, nothing cut: never a pass


def test_plan_has_only_the_pending_storyboard_left(plan):
    done, g3, out = plan
    assert done.returncode == 1  # exit 1 while the storyboard is not approved
    checks = {(i["check"], i["severity"]) for v in g3["generations"].values() for i in v["issues"]}
    # STORYBOARD: an Owner/reviewer decision, never self-approved; LOOK_NOT_PINNED (WARN): shots where someone
    # walks and no end frame shows where they arrive (SC01_g2 t1 lost THEO's jacket that way; v2 has an end frame)
    # P16-06 generability: SC04/SC05 are RED and not yet restaged (BLOCK until a restage or an Owner exception);
    # SC01_g1/g2 reuse their Owner-accepted takes (t5, t2) and send nothing new
    # P16-07a: the interaction contract is on and only the pilot (SC01..SC02) is authored for it; the contract
    # BLOCKs below are expected on SC03..SC06 until the rollout P16-07b
    contract = {("ADDRESSEE_MISSING", "BLOCK"), ("MARK_UNRESOLVED", "BLOCK"), ("HIDDEN_PERSON_UNPLACED", "BLOCK"),
                ("GAZE_TARGET_MISSING", "BLOCK")}
    assert checks == {("STORYBOARD", "BLOCK"), ("LOOK_NOT_PINNED", "WARN"), ("GENERABILITY_RED", "BLOCK"),
                      ("GENERABILITY_RED_REUSE", "WARN"), ("GENERABILITY_AMBER", "WARN")} | contract, checks
    per_gen = {g: {(i["check"], i["severity"]) for i in v["issues"]} for g, v in g3["generations"].items()}
    for gid in ("SC01_g1", "SC01_g2", "SC02_g1", "SC02_g2"):  # the pilot: only the storyboard blocks, generability warns
        assert not per_gen[gid] & contract, (gid, per_gen[gid])
        assert {c for c, sev in per_gen[gid] if sev == "BLOCK"} == {"STORYBOARD"}, (gid, per_gen[gid])
        assert all(c.startswith("GENERABILITY_") for c, sev in per_gen[gid] if sev == "WARN"), (gid, per_gen[gid])
    red = {g for g, v in g3["generations"].items() for i in v["issues"] if i["check"] == "GENERABILITY_RED"}
    assert red == {"SC04_g1", "SC04_g2", "SC05_g1", "SC05_g2"}
    warned = {g for g, v in g3["generations"].items() for i in v["issues"] if i["check"] == "LOOK_NOT_PINNED"}
    assert warned == {"SC06_g1"} and not any(g3["generations"][g]["verdict"] == "BLOCKED" and
                                            all(i["check"] == "LOOK_NOT_PINNED" for i in g3["generations"][g]["issues"])
                                            for g in warned)
    assert len(g3["generations"]) == 12
    for gid in g3["generations"]:  # the 215-word limit holds with no accepted_overlong everywhere else
        words = len((out / "prompts" / f"{gid}.txt").read_text(encoding="utf-8").split())
        assert gid in OPEN_OVERLONG or words <= MAX_WORDS, (gid, words)


def test_no_overlong_exemption_and_every_high_risk_has_a_fallback(pkg):
    pre = pkg.typed["preprod"]
    assert pre.accepted_overlong == {}
    done = run("validate", "--film", str(PKG))
    planning = json.loads(done.stdout)["planning"]
    assert planning["issues"] == []
    assert planning["budget"]["generations"] == 12 and planning["budget"]["owner_estimate"] == 171.2  # the Owner set it on 2026-11-07
    assert planning["legal"] == "pending"  # originality is the Owner's to confirm


def test_script_stays_inside_the_moderation_rules():
    text = (PKG / "script.fountain").read_text(encoding="utf-8").lower()
    banned = r"\b(police|cop|cops|officer|arrest\w*|gun|weapon|knife|blood|kill\w*|race|racial|black|white man|asian)\b"
    assert not re.search(banned, text)


def test_authoring_added_no_film04_specific_code():
    hits = [p for root in ("src", "tools") for p in (ROOT / root).rglob("*.py")
            if "film04" in p.name or "last_ticket" in p.read_text(encoding="utf-8", errors="ignore")]
    assert hits == []
