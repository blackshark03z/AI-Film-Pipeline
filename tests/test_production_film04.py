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


def run(*args):
    return subprocess.run([*FILM, *args], capture_output=True, text=True, encoding="utf-8", cwd=ROOT,
                          env={**__import__("os").environ, "PYTHONPATH": str(ROOT / "src"), "PYTHONIOENCODING": "utf-8"})


@pytest.fixture(scope="module")
def pkg():
    return load_package(PKG)


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
    assert res["4"].status == "BLOCK" and "no take of shot version 1" in res["4"].issues[0]  # nothing generated
    assert res["5"].status == res["6"].status == "BLOCK"  # nothing shot, nothing cut: never a pass


def test_plan_has_only_the_pending_storyboard_left(plan):
    done, g3, out = plan
    assert done.returncode == 1  # exit 1 while the storyboard is not approved
    checks = {(i["check"], i["severity"]) for v in g3["generations"].values() for i in v["issues"]}
    assert checks == {("STORYBOARD", "BLOCK")}, checks  # an Owner/reviewer decision, never self-approved
    assert len(g3["generations"]) == 12
    assert "PROMPT_TOO_LONG" not in done.stdout  # the 215-word limit holds with no accepted_overlong
    for gid in g3["generations"]:
        words = len((out / "prompts" / f"{gid}.txt").read_text(encoding="utf-8").split())
        assert words <= MAX_WORDS, (gid, words)


def test_no_overlong_exemption_and_every_high_risk_has_a_fallback(pkg):
    pre = pkg.typed["preprod"]
    assert pre.accepted_overlong == {}
    done = run("validate", "--film", str(PKG))
    planning = json.loads(done.stdout)["planning"]
    assert planning["issues"] == []
    assert planning["budget"]["generations"] == 12 and planning["budget"]["owner_estimate"] is None
    assert planning["legal"] == "pending"  # originality is the Owner's to confirm


def test_script_stays_inside_the_moderation_rules():
    text = (PKG / "script.fountain").read_text(encoding="utf-8").lower()
    banned = r"\b(police|cop|cops|officer|arrest\w*|gun|weapon|knife|blood|kill\w*|race|racial|black|white man|asian)\b"
    assert not re.search(banned, text)


def test_authoring_added_no_film04_specific_code():
    hits = [p for root in ("src", "tools") for p in (ROOT / root).rglob("*.py")
            if "film04" in p.name or "last_ticket" in p.read_text(encoding="utf-8", errors="ignore")]
    assert hits == []
