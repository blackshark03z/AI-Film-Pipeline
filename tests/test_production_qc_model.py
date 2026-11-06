import json
import subprocess
import sys
from pathlib import Path

import pytest
from pydantic import ValidationError

from film_pipeline.production.qc_model import (CONTENT_GROUPS, GROUP_NUMBERS, MACHINE_GROUPS, MIN_LEVEL, TAKE_GROUPS,
                                               GroupCheck, TakeQc, Waiver, auto_check, blank_take, verdict_report)

TOOL = Path(__file__).resolve().parents[1] / "tools" / "film.py"
HUMAN, EVID = "human:owner", "reviews/SC01_g1/contact.png"


def human_pass(group, level=None):
    return GroupCheck(group=group, result="PASS", level=level or MIN_LEVEL[group], evidence=EVID, reviewer=HUMAN)


def all_passed(take_id="t1"):
    return TakeQc(take_id=take_id, generation_id="SC01_g1", checks=[human_pass(g) for g in TAKE_GROUPS])


def test_sixteen_groups_numbered_131_to_146():
    assert len(GROUP_NUMBERS) == 16 and min(GROUP_NUMBERS.values()) == 131 and max(GROUP_NUMBERS.values()) == 146
    assert GROUP_NUMBERS["narrative"] == 131 and GROUP_NUMBERS["motion"] == 136 and GROUP_NUMBERS["visual"] == 138
    assert CONTENT_GROUPS | MACHINE_GROUPS == set(GROUP_NUMBERS) and not CONTENT_GROUPS & MACHINE_GROUPS


def test_blank_take_is_incomplete_never_accepted():
    v = blank_take("t1", "SC01_g1").verdict()
    assert v.status == "INCOMPLETE" and v.open_groups == list(TAKE_GROUPS)


def test_all_groups_passed_by_a_human_at_the_right_level_is_accepted():
    assert all_passed().verdict().status == "ACCEPTED"


def test_a_p0_fail_rejects_and_cannot_be_waived():
    fail = GroupCheck(group="motion", result="FAIL", severity="P0", level="FULL_MOTION", evidence=EVID, reviewer=HUMAN)
    take = TakeQc(take_id="t", generation_id="g", checks=[fail] + [human_pass(g) for g in TAKE_GROUPS if g != "motion"])
    assert take.verdict().status == "REJECTED" and take.verdict().p0 == ["motion(136)"]
    with pytest.raises(ValidationError, match="only a P1 FAIL can be waived"):
        GroupCheck(group="motion", result="FAIL", severity="P0", level="FULL_MOTION", evidence=EVID, reviewer=HUMAN,
                   waiver=Waiver(reason="looks fine to me", by=HUMAN))


def test_p1_fail_rejects_until_waived_by_a_human_with_a_reason():
    def take(waiver):
        fail = GroupCheck(group="visual", result="FAIL", severity="P1", level="SAMPLED", evidence=EVID,
                          reviewer=HUMAN, waiver=waiver)
        return TakeQc(take_id="t", generation_id="g", checks=[fail] + [human_pass(g) for g in TAKE_GROUPS
                                                                        if g != "visual"])
    assert take(None).verdict().status == "REJECTED" and take(None).verdict().p1_unwaived == ["visual(138)"]
    waived = take(Waiver(reason="grain is a stylistic choice", by="human:owner")).verdict()
    assert waived.status == "ACCEPTED" and waived.p1_waived == ["visual(138)"] and not waived.p1_unwaived
    with pytest.raises(ValidationError):
        Waiver(reason="ok", by="auto:tool")  # an automatic tool cannot waive
    with pytest.raises(ValidationError):
        Waiver(reason="", by=HUMAN)


def test_p2_fail_is_noted_and_does_not_block():
    p2 = GroupCheck(group="camera", result="FAIL", severity="P2", level="SAMPLED", evidence=EVID, reviewer=HUMAN)
    take = TakeQc(take_id="t", generation_id="g", checks=[p2] + [human_pass(g) for g in TAKE_GROUPS if g != "camera"])
    assert take.verdict().status == "ACCEPTED" and take.verdict().p2 == ["camera(137)"]


def test_auto_tool_cannot_pass_or_fail_a_content_group():
    for result, sev in (("PASS", None), ("FAIL", "P1")):
        with pytest.raises(ValidationError, match="auto tool may only WARN"):
            GroupCheck(group="action", result=result, severity=sev, level="FULL_MOTION", evidence=EVID,
                       reviewer="auto:vision")


def test_auto_check_downgrades_content_groups_and_keeps_machine_ones():
    ok = auto_check("narrative", "vision", ok=True, evidence=EVID, level="SAMPLED")
    assert ok.result == "UNASSESSED" and not ok.reviewer  # "no concern" is not a narrative verdict
    warn = auto_check("action", "vision", ok=False, evidence=EVID, level="SAMPLED")
    assert warn.result == "WARN" and warn.severity is None and warn.reviewer == "auto:vision"
    assert auto_check("audio", "ffmpeg", ok=True, evidence="a.log", level="FULL_MOTION").result == "PASS"
    bad = auto_check("technical", "ffprobe", ok=False, evidence="p.json", level="FULL_MOTION", severity="P0")
    assert bad.result == "FAIL" and bad.severity == "P0"


def test_auto_warn_keeps_the_take_incomplete_until_a_human_looks():
    take = all_passed()
    take.checks[[c.group for c in take.checks].index("action")] = auto_check(
        "action", "vision", ok=False, evidence=EVID, level="SAMPLED")
    v = take.verdict()
    assert v.status == "INCOMPLETE" and v.open_groups == ["action"]


def test_a_still_cannot_prove_motion_and_a_pass_needs_the_minimum_level():
    with pytest.raises(ValidationError, match="needs level FULL_MOTION"):
        human_pass("motion", level="STILL")
    with pytest.raises(ValidationError, match="needs level FULL_MOTION"):
        human_pass("action", level="SAMPLED")
    with pytest.raises(ValidationError, match="needs level CUT"):
        human_pass("sequence", level="FULL_MOTION")
    assert human_pass("motion", level="CUT").result == "PASS"  # higher is fine


def test_records_without_proof_are_rejected_by_the_schema():
    with pytest.raises(ValidationError, match="needs evidence, reviewer and level"):
        GroupCheck(group="visual", result="PASS")
    with pytest.raises(ValidationError, match="FAIL needs a severity"):
        GroupCheck(group="visual", result="FAIL", level="SAMPLED", evidence=EVID, reviewer=HUMAN)
    with pytest.raises(ValidationError, match="PASS has no severity"):
        GroupCheck(group="visual", result="PASS", severity="P2", level="SAMPLED", evidence=EVID, reviewer=HUMAN)
    with pytest.raises(ValidationError, match="UNASSESSED carries no severity"):
        GroupCheck(group="visual", severity="P1")
    with pytest.raises(ValidationError):
        GroupCheck(group="visual", result="PASS", level="SAMPLED", evidence=EVID, reviewer="somebody")
    with pytest.raises(ValidationError):
        GroupCheck(group="visual", result="PASS", level="SAMPLED", evidence=EVID, reviewer="xhuman:owner")
    with pytest.raises(ValidationError):
        GroupCheck(group="not_a_group")


def test_one_check_per_group_per_take():
    with pytest.raises(ValidationError, match="more than one check"):
        TakeQc(take_id="t", generation_id="g", checks=[human_pass("visual"), human_pass("visual")])


def test_a_missing_group_counts_as_open():
    take = TakeQc(take_id="t", generation_id="g", checks=[human_pass(g) for g in TAKE_GROUPS if g != "sync"])
    assert take.verdict().status == "INCOMPLETE" and take.verdict().open_groups == ["sync"]


def test_report_lists_every_group_with_its_number():
    report = verdict_report(all_passed())
    assert report["status"] == "ACCEPTED" and report["groups"]["136:motion"]["reviewer"] == HUMAN


def test_cli_qc_verdicts_and_exit_codes(tmp_path):
    def run(payload):
        rec = tmp_path / "rec.json"
        rec.write_text(json.dumps(payload), encoding="utf-8")
        done = subprocess.run([sys.executable, str(TOOL), "qc", "--record", str(rec)], capture_output=True, text=True,
                              encoding="utf-8")
        return done.returncode, json.loads(done.stdout)

    accepted = all_passed().model_dump(mode="json")
    code, body = run(accepted)
    assert code == 0 and body["ok"] and body["takes"][0]["status"] == "ACCEPTED"
    code, body = run(blank_take("t2", "SC01_g2").model_dump(mode="json"))
    assert code == 0 and not body["ok"] and body["takes"][0]["status"] == "INCOMPLETE"
    rejected = all_passed("t3").model_dump(mode="json")
    rejected["checks"][0].update(result="FAIL", severity="P0")
    code, body = run([rejected])
    assert code == 1 and body["takes"][0]["status"] == "REJECTED"
    cheat = all_passed("t4").model_dump(mode="json")
    cheat["checks"][0].update(reviewer="auto:vision")  # an auto tool claiming a narrative PASS
    code, body = run(cheat)
    assert code == 2 and not body["ok"] and any("auto tool may only WARN" in m for m in body["error"])
