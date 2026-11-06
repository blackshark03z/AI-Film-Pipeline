import json
import subprocess
import sys
from pathlib import Path

import pytest

from film_pipeline.production.package import load_package
from film_pipeline.production.planning import (CREDITS_PER_GENERATION, KPI_HISTORY, RETAKE_FACTORS, budget, legal,
                                               planning_issues, planning_report, risks, schedule)

ROOT = Path(__file__).resolve().parents[1]
FILM03 = ROOT / "films" / "film03_front_desk"
FILES = ("film.json", "script.fountain", "01_story.json", "02_direction.json", "03_preprod.json", "04_shots.json")


def clone(tmp_path, film=None, pre=None, shots=None):
    for name in FILES:
        (tmp_path / name).write_text((FILM03 / name).read_text(encoding="utf-8"), encoding="utf-8")
    for name, mutate in (("film.json", film), ("03_preprod.json", pre), ("04_shots.json", shots)):
        if mutate:
            data = json.loads((tmp_path / name).read_text(encoding="utf-8"))
            mutate(data)
            (tmp_path / name).write_text(json.dumps(data), encoding="utf-8")
    pkg = load_package(tmp_path)
    assert pkg.issues == [], pkg.issues
    return pkg


def sub(tmp_path, name):
    (tmp_path / name).mkdir()
    return tmp_path / name


def gen(shots, gid):
    return next(g for g in shots["generations"] if g["generation_id"] == gid)


def test_retake_factors_follow_the_three_kpi_ledgers():
    assert RETAKE_FACTORS["film01_first_day"] == pytest.approx(168 / (10 * 12))
    assert RETAKE_FACTORS["film03_front_desk"] == pytest.approx(1.0)  # 16 generations, 192 production credits
    assert set(KPI_HISTORY) == {"film01_first_day", "film02_spare_key", "film03_front_desk"} and CREDITS_PER_GENERATION == 12


def test_film03_budget_matches_the_arithmetic():
    b = budget(load_package(FILM03))
    mean = sum(RETAKE_FACTORS.values()) / 3
    assert b["generations"] == 16 and b["base_credits"] == 192.0
    assert b["expected_credits"] == pytest.approx(192 * mean, abs=0.1) and b["high_credits"] == pytest.approx(268.8)
    assert b["cap_credits"] == pytest.approx(b["expected_credits"] * 1.5, abs=0.1)
    assert [f["check"] for f in b["findings"]] == ["BUDGET_NOT_SET"] and b["owner_estimate"] is None


def test_owner_estimate_below_expected_warns_and_enough_is_quiet(tmp_path):
    def low(film):
        film["budget"]["credits_estimate"] = 150

    b = budget(clone(tmp_path, film=low))
    assert [f["check"] for f in b["findings"]] == ["BUDGET_BELOW_EXPECTED"] and b["owner_cap"] == 225.0

    def enough(film):
        film["budget"]["credits_estimate"] = 240
    assert budget(clone(sub(tmp_path, "ok"), film=enough))["findings"] == []


def test_schedule_chains_waves_and_stills_before_videos():
    s = schedule(load_package(FILM03))
    assert s["parallel_chains"] == 2 and s["critical_path"] == 12  # lobby chain of 12, briefing chain of 4
    assert [len(c["generations"]) for c in s["chains"]] == [12, 4]
    assert s["waves"][0] == ["SC01_g1", "SC07_g1"] and s["waves"][-1] == ["SC06_g2"]
    names = [step["step"] for step in s["steps"]]
    assert names.index("character stills") < names.index("location plates") < next(
        i for i, n in enumerate(names) if n.startswith("videos"))
    assert next(st for st in s["steps"] if st["step"].startswith("start stills"))["items"] == ["start_SC01_g1",
                                                                                             "start_SC07_g1"]


def test_film03_has_no_high_risk_but_reports_medium_ones():
    found = risks(load_package(FILM03))
    assert not [r for r in found if r["level"] == "HIGH"]
    assert {"PROP_ACTION", "CROWD"} <= {r["kind"] for r in found}
    deep = {r["generation_id"] for r in found if r["kind"] == "HANDOFF_DEPTH"}
    assert deep == {"SC02_g2", "SC03_g1", "SC03_g2", "SC04_g1", "SC04_g2", "SC05_g1", "SC05_g2", "SC06_g1", "SC06_g2",
                    "SC08_g2"}  # 4th and later generation of the 12-long lobby chain, last of the briefing chain


def test_contact_is_a_high_risk_that_needs_a_fallback_plan(tmp_path):
    def hug(shots):
        gen(shots, "SC06_g2")["choreography"]["phases"][1]["description"] = "KESSLER grabs NORA's arm"
    pkg = clone(tmp_path, shots=hug)
    contact = [r for r in risks(pkg) if r["kind"] == "CONTACT"]
    assert len(contact) == 1 and contact[0]["generation_id"] == "SC06_g2" and contact[0]["level"] == "HIGH"
    assert any(i.startswith("RISK_NO_FALLBACK SC06_g2") for i in planning_issues(pkg))

    def with_fallback(shots):
        hug(shots)

    def plan(pre):
        pre["risk_fallbacks"] = {"SC06_g2": "cut to an insert of the desk; the grab happens off-screen"}
    ok = clone(sub(tmp_path, "fb"), pre=plan, shots=with_fallback)
    assert planning_issues(ok) == [] and [r["fallback"] for r in risks(ok) if r["kind"] == "CONTACT"][0].startswith("cut")


def test_handover_between_characters_is_high(tmp_path):
    def pass_it(pre):
        pre["states"]["SC03_g2"]["props"]["the letter:"] = "in KESSLER's hand"
        pre["states"]["SC03_end"]["props"]["the letter:"] = "in NORA's hand"
    found = risks(clone(tmp_path, pre=pass_it))
    assert any(r["kind"] == "HANDOVER" and "KESSLER" in r["detail"] and "NORA" in r["detail"] for r in found)


def test_crowd_and_deep_chain_levels():
    found = risks(load_package(FILM03))
    assert all(r["level"] == "MEDIUM" for r in found if r["kind"] == "CROWD")
    assert all(r["level"] == "LOW" for r in found if r["kind"] == "HANDOFF_DEPTH")
    import re
    assert max(int(re.match(r"\d+", r["detail"]).group()) for r in found if r["kind"] == "HANDOFF_DEPTH") == 12


def test_film03_legal_ledger_is_pending_owner_decisions_not_a_pass():
    ledger = legal(load_package(FILM03))
    assert ledger["status"] == "pending" and len(ledger["entries"]) == 8
    assert "character NORA: pending" in ledger["owner_decisions"] and "location lobby_morning: pending" in \
        ledger["owner_decisions"]
    assert not any("music" in d for d in ledger["owner_decisions"])  # "no music" is original, not a decision


def test_started_ledger_must_cover_every_character_and_location(tmp_path):
    def drop(pre):
        pre["rights"] = [r for r in pre["rights"] if r["subject"] not in ("ORTIZ", "briefing_morning")]
    issues = planning_issues(clone(tmp_path, pre=drop))
    assert "RIGHTS_MISSING character ORTIZ: no entry in 03_preprod.rights" in issues
    assert "RIGHTS_MISSING location briefing_morning: no entry in 03_preprod.rights" in issues

    def none(pre):
        pre["rights"] = []
    pkg = clone(sub(tmp_path, "n"), pre=none)
    assert planning_issues(pkg) == [] and legal(pkg)["status"] == "not_declared"


def test_cleared_everything_is_clear(tmp_path):
    def clear(pre):
        for r in pre["rights"]:
            r["status"] = "cleared"
    ledger = legal(clone(tmp_path, pre=clear))
    assert ledger["status"] == "clear" and ledger["owner_decisions"] == []


def test_rights_schema_rejects_unknown_status(tmp_path):
    for name in FILES:
        (tmp_path / name).write_text((FILM03 / name).read_text(encoding="utf-8"), encoding="utf-8")
    pre = json.loads((tmp_path / "03_preprod.json").read_text(encoding="utf-8"))
    pre["rights"][0]["status"] = "probably fine"
    (tmp_path / "03_preprod.json").write_text(json.dumps(pre), encoding="utf-8")
    assert any("03_preprod.json" in i for i in load_package(tmp_path).issues)


def test_report_and_validate_show_budget_and_risks():
    report = planning_report(load_package(FILM03))
    assert report["ok"] and report["risk_summary"]["HIGH"] == 0 and report["budget"]["generations"] == 16
    tool = ROOT / "tools" / "film.py"
    val = subprocess.run([sys.executable, str(tool), "validate", "--film", str(FILM03)], capture_output=True,
                         text=True, encoding="utf-8")
    planning = json.loads(val.stdout)["planning"]
    assert planning["budget"]["expected_credits"] == report["budget"]["expected_credits"]
    assert planning["legal"] == "pending" and planning["issues"] == [] and planning["risk_summary"]["MEDIUM"] >= 1


def test_validate_blocks_on_a_planning_error_and_cli_planning(tmp_path):
    def hug(shots):
        gen(shots, "SC06_g2")["choreography"]["phases"][1]["description"] = "KESSLER grabs NORA's arm"
    clone(tmp_path, shots=hug)
    tool = ROOT / "tools" / "film.py"
    bad = subprocess.run([sys.executable, str(tool), "planning", "--film", str(tmp_path)], capture_output=True,
                         text=True, encoding="utf-8")
    body = json.loads(bad.stdout)
    assert bad.returncode == 1 and not body["ok"] and body["issues"][0].startswith("RISK_NO_FALLBACK")
    val = subprocess.run([sys.executable, str(tool), "validate", "--film", str(tmp_path)], capture_output=True,
                         text=True, encoding="utf-8")
    assert json.loads(val.stdout)["blocked"] and json.loads(val.stdout)["planning"]["issues"]
    ok = subprocess.run([sys.executable, str(tool), "planning", "--film", str(FILM03)], capture_output=True,
                        text=True, encoding="utf-8")
    assert ok.returncode == 0
