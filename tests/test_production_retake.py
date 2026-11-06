import json
import subprocess
import sys
from pathlib import Path

import pytest
from pydantic import ValidationError

from film_pipeline.production import takes as T
from film_pipeline.production.package import load_package
from film_pipeline.production.qc_model import MIN_LEVEL, TakeQc, blank_take
from film_pipeline.production.retake import (CHANGE_OPTIONS, RetakePolicy, pickup_list, retake_plan, retake_report,
                                             start_version)
from film_pipeline.production.sections import ShotsSection

ROOT = Path(__file__).resolve().parents[1]
FILM03 = ROOT / "films" / "film03_front_desk"
TOOL = ROOT / "tools" / "film.py"
FILES = ("film.json", "script.fountain", "01_story.json", "02_direction.json", "03_preprod.json", "04_shots.json")


def shots():
    return load_package(FILM03).typed["shots"]


def entry(gid, n, status, cause="", version=1, credits=12.0):
    h = f"{abs(hash((gid, n, version))):064x}"[:64]
    return T.TakeEntry(take_id=f"{gid}_t{n}", generation_id=gid, prompt_sha256="a" * 64, route="r", model="m",
                       credits=credits, output_file=f"{gid}_{n}.mp4", output_sha256=h.rjust(64, "0"), status=status,
                       cause=cause, shot_version=version)


def log_of(*entries):
    return T.TakeLog(film_id="film03_front_desk", takes=list(entries))


def row(plan, gid="SC01_g1"):
    return next(r for r in plan if r["generation_id"] == gid)


def test_unrendered_shots_are_not_in_the_plan():
    assert retake_plan(log_of(), shots()) == []


def test_accepted_and_awaiting_review_need_no_decision():
    plan = retake_plan(log_of(entry("SC01_g1", 1, "ACCEPTED"), entry("SC01_g2", 1, "GENERATED"),
                              entry("SC02_g1", 1, "INCOMPLETE")), shots())
    assert [r["action"] for r in plan] == ["DONE", "AWAITING_REVIEW", "AWAITING_REVIEW"]
    assert pickup_list(plan) == []


def test_a_rejection_without_a_cause_must_be_classified_first():
    r = row(retake_plan(log_of(entry("SC01_g1", 1, "REJECTED")), shots()))
    assert r["action"] == "CLASSIFY" and "without a cause" in r["reason"]


@pytest.mark.parametrize("cause", ["PROMPT", "START_FRAME", "PROVIDER_LIMIT", "STAGING"])
def test_first_failure_gets_the_cheap_fix_for_its_cause(cause):
    r = row(retake_plan(log_of(entry("SC01_g1", 1, "REJECTED", cause)), shots()))
    assert r["action"] == "RETRY" and r["cause"] == cause and len(r["options"]) == 1
    assert r["next_render_credits"] == 12 and r["credits_spent"] == 12


@pytest.mark.parametrize("cause", ["PROMPT", "START_FRAME", "PROVIDER_LIMIT", "STAGING"])
def test_same_cause_twice_changes_the_approach_instead_of_retrying(cause):
    r = row(retake_plan(log_of(entry("SC01_g1", 1, "REJECTED", cause), entry("SC01_g1", 2, "REJECTED", cause)), shots()))
    assert r["action"] == "CHANGE_APPROACH" and r["options"] == CHANGE_OPTIONS[cause] and r["credits_spent"] == 24


def test_two_different_causes_still_retry_but_three_rejections_escalate():
    two = row(retake_plan(log_of(entry("SC01_g1", 1, "REJECTED", "PROMPT"), entry("SC01_g1", 2, "REJECTED", "STAGING")),
                          shots()))
    assert two["action"] == "RETRY" and two["cause"] == "STAGING"
    three = row(retake_plan(log_of(*[entry("SC01_g1", n, "REJECTED", "PROMPT") for n in (1, 2, 3)]), shots()))
    assert three["action"] == "ESCALATE" and "Owner decides" in three["reason"] and "36 credits" in three["reason"]
    assert "accept the best take with a written waiver" in three["options"]


def test_the_newest_take_decides_when_it_is_still_unreviewed():
    plan = retake_plan(log_of(entry("SC01_g1", 1, "REJECTED", "PROMPT"), entry("SC01_g1", 2, "GENERATED")), shots())
    assert row(plan)["action"] == "AWAITING_REVIEW"


def test_chained_generations_report_what_is_downstream():
    r = row(retake_plan(log_of(entry("SC01_g1", 1, "REJECTED", "STAGING")), shots()))
    assert r["downstream"][0] == "SC01_g2" and len(r["downstream"]) == 11  # the 12-long lobby chain
    brief = row(retake_plan(log_of(entry("SC07_g1", 1, "REJECTED", "STAGING")), shots()), "SC07_g1")
    assert len(brief["downstream"]) == 3  # the 4-long briefing chain


def test_a_new_version_gets_a_fresh_count_and_the_third_version_escalates():
    s = shots()
    v2 = s.generations[0].model_copy(update={"version": 2})
    s2 = s.model_copy(update={"generations": [v2] + s.generations[1:]})
    fresh = row(retake_plan(log_of(entry("SC01_g1", 1, "REJECTED", "PROMPT"), entry("SC01_g1", 2, "REJECTED", "PROMPT"),
                                   entry("SC01_g1", 3, "GENERATED", version=2)), s2))
    assert fresh["action"] == "AWAITING_REVIEW" and fresh["shot_version"] == 2 and fresh["credits_spent"] == 36
    again = row(retake_plan(log_of(entry("SC01_g1", 1, "REJECTED", "PROMPT"), entry("SC01_g1", 2, "REJECTED", "PROMPT"),
                                   entry("SC01_g1", 3, "REJECTED", "STAGING", version=2)), s2))
    assert again["action"] == "RETRY" and again["rejected_in_version"] == 1
    v3 = s.generations[0].model_copy(update={"version": 3})
    s3 = s.model_copy(update={"generations": [v3] + s.generations[1:]})
    last = row(retake_plan(log_of(entry("SC01_g1", 1, "REJECTED", "PROMPT", version=3),
                                  entry("SC01_g1", 2, "REJECTED", "PROMPT", version=3)), s3))
    assert last["action"] == "ESCALATE"


def test_policy_limits_are_adjustable():
    log = log_of(entry("SC01_g1", 1, "REJECTED", "PROMPT"), entry("SC01_g1", 2, "REJECTED", "PROMPT"))
    assert row(retake_plan(log, shots(), RetakePolicy(same_cause_limit=3, rejected_per_version_limit=4)))["action"] == "RETRY"
    with pytest.raises(ValidationError):
        RetakePolicy(same_cause_limit=1)


def test_report_summarises_counts_and_credits():
    rep = retake_report(log_of(entry("SC01_g1", 1, "ACCEPTED"), entry("SC01_g2", 1, "REJECTED", "STAGING")), shots())
    assert not rep["ok"] and rep["counts"]["DONE"] == 1 and rep["counts"]["RETRY"] == 1
    assert rep["credits_spent"] == 24 and [p["generation_id"] for p in rep["pickups"]] == ["SC01_g2"]


# ---- cause on the QC record -------------------------------------------------------------------------------------

def test_cause_belongs_only_on_a_rejected_take():
    from film_pipeline.production.qc_model import GroupCheck
    fail = GroupCheck(group="motion", result="FAIL", severity="P0", level="FULL_MOTION", evidence="e.png",
                      reviewer="human:owner")
    ok = TakeQc(take_id="t", generation_id="g", checks=[fail], cause="STAGING", cause_note="actors teleport")
    assert ok.cause == "STAGING"
    with pytest.raises(ValidationError, match="only belongs on a rejected take"):
        TakeQc(take_id="t", generation_id="g", checks=[], cause="PROMPT")
    with pytest.raises(ValidationError):
        TakeQc(take_id="t", generation_id="g", checks=[fail], cause="BAD_LUCK")


def test_ingest_stores_the_cause_in_the_log(tmp_path):
    root = tmp_path / "film"
    root.mkdir()
    for name in FILES:
        (root / name).write_text((FILM03 / name).read_text(encoding="utf-8"), encoding="utf-8")
    pkg = load_package(root)
    mp4 = tmp_path / "a.mp4"
    mp4.write_bytes(b"x")
    taken, _ = T.register_take(root, pkg.header.film_id, "SC01_g1", mp4, prompt_text="p", route="r", model="m",
                               credits=12, shot_version=1)
    sheet = T.dailies_template(pkg, taken)
    for c in sheet["qc"]["checks"]:
        c.update(result="PASS", level=MIN_LEVEL[c["group"]], evidence="x.png", reviewer="human:owner")
    motion = next(c for c in sheet["qc"]["checks"] if c["group"] == "motion")
    motion.update(result="FAIL", severity="P0", level="FULL_MOTION")
    sheet["qc"]["cause"] = "PROVIDER_LIMIT"
    T.ingest_review(root, pkg.header.film_id, sheet)
    logged = T.load_log(root, pkg.header.film_id).get("SC01_g1_t1")
    assert logged.status == "REJECTED" and logged.cause == "PROVIDER_LIMIT" and logged.shot_version == 1


# ---- feeding a decision back into 04_shots ----------------------------------------------------------------------

def raw_shots():
    return json.loads((FILM03 / "04_shots.json").read_text(encoding="utf-8"))


def test_start_version_replaces_in_place_and_keeps_the_old_one_in_history():
    log = log_of(entry("SC01_g1", 1, "REJECTED", "STAGING"), entry("SC01_g1", 2, "REJECTED", "STAGING"))
    edits = {"sfx": ["door closes softly"], "coverage": "TWO_SHOT"}
    new = start_version(raw_shots(), log, "SC01_g1", "actors teleported twice", edits)
    cur = new["generations"][0]
    assert cur["generation_id"] == "SC01_g1" and cur["version"] == 2 and cur["repair_of"] == "SC01_g1@v1"
    assert cur["sfx"] == ["door closes softly"] and cur["coverage"] == "TWO_SHOT" and cur["repair_reason"] == "actors teleported twice"
    section = ShotsSection.model_validate(new)
    assert [g.generation_id for g in section.generations] == [g.generation_id for g in shots().generations]
    assert section.history[0].generation_id == "SC01_g1" and section.history[0].version == 1


def test_start_version_refuses_unsafe_requests():
    log = log_of(entry("SC01_g1", 1, "REJECTED", "STAGING"))
    with pytest.raises(ValueError, match="written reason"):
        start_version(raw_shots(), log, "SC01_g1", " ", {"sfx": ["x"]})
    with pytest.raises(ValueError, match="may not set"):
        start_version(raw_shots(), log, "SC01_g1", "r", {"version": 9})
    with pytest.raises(ValueError, match="change something"):
        start_version(raw_shots(), log, "SC01_g1", "r", {})
    with pytest.raises(ValueError, match="unknown generation"):
        start_version(raw_shots(), log, "SC99_g1", "r", {"sfx": ["x"]})
    with pytest.raises(ValueError, match="no rejected take"):
        start_version(raw_shots(), log_of(entry("SC01_g1", 1, "ACCEPTED")), "SC01_g1", "r", {"sfx": ["x"]})
    with pytest.raises(ValidationError):
        start_version(raw_shots(), log, "SC01_g1", "r", {"coverage": "NOT_A_COVERAGE"})  # result must still validate


def test_choreography_edit_keeps_its_generation_id():
    log = log_of(entry("SC01_g1", 1, "REJECTED", "STAGING"))
    choreo = raw_shots()["generations"][0]["choreography"]
    choreo["generation_id"] = "SOMETHING_ELSE"
    new = start_version(raw_shots(), log, "SC01_g1", "r", {"choreography": choreo})
    assert new["generations"][0]["choreography"]["generation_id"] == "SC01_g1"


def test_history_must_be_older_than_the_current_version():
    raw = raw_shots()
    raw["history"] = [dict(raw["generations"][0])]  # same version as the current one
    with pytest.raises(ValidationError, match="not older"):
        ShotsSection.model_validate(raw)


def test_a_shot_with_history_still_passes_the_package_checks(tmp_path):
    root = tmp_path / "film"
    root.mkdir()
    for name in FILES:
        (root / name).write_text((FILM03 / name).read_text(encoding="utf-8"), encoding="utf-8")
    log = log_of(entry("SC01_g1", 1, "REJECTED", "STAGING"))
    new = start_version(raw_shots(), log, "SC01_g1", "r", {"sfx": ["door closes softly"]})
    (root / "04_shots.json").write_text(json.dumps(new), encoding="utf-8")
    pkg = load_package(root)
    assert pkg.issues == [] and pkg.typed["shots"].generations[0].version == 2


def test_cli_retake_report_and_pickup(tmp_path):
    root = tmp_path / "film"
    root.mkdir()
    for name in FILES:
        (root / name).write_text((FILM03 / name).read_text(encoding="utf-8"), encoding="utf-8")
    (root / "takes").mkdir()
    log = log_of(entry("SC01_g1", 1, "REJECTED", "STAGING"), entry("SC01_g1", 2, "REJECTED", "STAGING"))
    (root / "takes" / "index.json").write_text(json.dumps(log.model_dump(mode="json")), encoding="utf-8")

    def run(*args):
        done = subprocess.run([sys.executable, str(TOOL), "retake", "--film", str(root), *args], capture_output=True,
                              text=True, encoding="utf-8")
        return done.returncode, json.loads(done.stdout)

    code, body = run()
    assert code == 1 and body["pickups"][0]["action"] == "CHANGE_APPROACH"
    edits = tmp_path / "edits.json"
    edits.write_text(json.dumps({"sfx": ["door closes softly"]}), encoding="utf-8")
    code, body = run("--pickup", "SC01_g1", "--reason", "re-staged", "--edits", str(edits))
    assert code == 0 and body["version"] == 2 and body["repair_of"] == "SC01_g1@v1"
    code, body = run()
    assert body["plan"][0]["shot_version"] == 2 and body["plan"][0]["action"] == "AWAITING_REVIEW"
    code, body = run("--pickup", "SC01_g1")
    assert code == 2 and "--reason" in body["error"]
