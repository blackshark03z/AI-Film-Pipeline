"""S2-lite intake (contract sections 7 and 10) against fixture lane outputs: no Muse process, no network."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from film_pipeline.agentic import lane_intake as LI
from s2_lite_support import FILM_ID, make_world
from film_pipeline.production.takes import load_log


def list_takes(film):
    return load_log(film, FILM_ID).takes



def intake(w, **kw):
    kw.setdefault("broker_db", w.broker.db_path)
    return LI.intake_job(w.job["job_key"], store=w.store, **kw)


def states(w):
    return {c["slot_id"]: (c["state"], c["reason"]) for c in w.store.children(w.job["job_key"])}


def kinds(w, **flt):
    return [e["kind"] for e in w.store.events(job_key=w.job["job_key"])]


def alarm_codes(w):
    return [e["state"] for e in w.store.events(job_key=w.job["job_key"]) if e["kind"] == "ALARM"]


def take_files(w):
    d = w.film / "takes"
    return sorted(p.name for p in d.glob("*.mp4")) if d.is_dir() else []


def attempt_of(w, i):
    for entry in w.read_ledger()["entries"]:
        for a in entry["attempts"]:
            if a["slot_id"] == w.slot(i)["slot_id"]:
                return a
    raise AssertionError("no attempt")


# ---- happy path -----------------------------------------------------------------------------------------------------
def test_clean_run_registers_every_slot_and_settles_everything(tmp_path):
    w = make_world(tmp_path)
    w.clean_run()
    out = intake(w)
    assert out["ok"] and out["state"] == "REGISTERED" and not out["attention"], out
    assert states(w) == {"shot_01": ("REGISTERED", "RESULT_EXACT_EVIDENCE"),
                         "shot_02": ("REGISTERED", "RESULT_EXACT_EVIDENCE")}
    assert take_files(w) == ["S1_v1_t1.mp4", "S2_v1_t1.mp4"]
    assert (w.film / "takes" / "S1_v1_t1.mp4").read_bytes() == w.clips["shot_01"]
    takes = list_takes(w.film)
    assert {t.provider_job_id for t in takes} == {f"{w.job['job_dir']}:{w.slot(i)['slot_id']}:{w.slot(i)['request_id']}"
                                                   for i in (0, 1)}
    assert all(t.provider == "muse" for t in takes)
    for i in (0, 1):
        a = attempt_of(w, i)
        assert (a["status"], a["reason"]) == ("RESOLVED", "RESULT_RECEIVED")
        assert w.child_row(i)["final"] == 1 and w.child_row(i)["outcome"] != "NOT_SENT"
    row = w.store.find_job(w.job["job_key"])
    assert row["state"] == "REGISTERED" and row["broker_settled"] == 1 and row["qc_pending"] == 1
    ks = kinds(w)
    assert ks.count("CHILD_REGISTERED") == 2 and "JOB_REGISTERED" in ks and "BROKER_SETTLED" in ks
    # the lane's own files are untouched (copies only), staging is gone
    assert (w.job_dir / "lane_result.json").is_file() and (w.batch_dir() / "shot_01.mp4").is_file()
    assert not (w.film / ".staging" / w.job["job_dir"]).exists()
    # evidence copied into the film package
    assert (w.film / "takes" / "jobs" / w.job["job_dir"] / "intake" / "lane_result.json").is_file()


def test_reintake_is_idempotent(tmp_path):
    w = make_world(tmp_path)
    w.clean_run()
    intake(w)
    before = (len(w.store.events(job_key=w.job["job_key"])), take_files(w), len(list_takes(w.film)),
              w.read_ledger())
    again = intake(w)
    assert again["ok"] and again["state"] == "REGISTERED" and again["changed"] is False
    after = (len(w.store.events(job_key=w.job["job_key"])), take_files(w), len(list_takes(w.film)), w.read_ledger())
    assert before == after


def test_a_decided_job_is_never_redecided_even_if_the_lane_files_change_later(tmp_path):
    w = make_world(tmp_path)
    w.clean_run()
    intake(w)
    (w.batch_dir() / "shot_01.mp4").write_bytes(b"different now")
    again = intake(w)
    assert again["state"] == "REGISTERED" and states(w)["shot_01"][0] == "REGISTERED"
    assert (w.film / "takes" / "S1_v1_t1.mp4").read_bytes() == w.clips["shot_01"]


# ---- partial / missing / mismatch / duplicate ------------------------------------------------------------------------
def test_partial_zip_only_the_proven_slot_is_registered_the_other_is_held(tmp_path):
    w = make_world(tmp_path)
    assert w.check(0, 1)["go"]
    a0 = w.good_slot(0)
    w.write_ledger([a0, w.attempt(1)])
    w.write_lane_result([w.lane_child(0), w.lane_child(1)])   # lane claims both, only slot 1's clip + receipt exist
    out = intake(w)
    assert out["state"] == "AMBIGUOUS" and out["attention"]
    assert states(w)["shot_01"][0] == "REGISTERED"
    assert states(w)["shot_02"] == ("AMBIGUOUS", "RECEIPT_MISSING")
    assert take_files(w) == ["S1_v1_t1.mp4"]
    assert (attempt_of(w, 1)["status"]) == "UNCONFIRMED"   # status unchanged: held
    assert w.child_row(1)["final"] == 0                      # never settled
    assert w.child_row(0)["final"] == 1


def test_missing_slot_in_the_lane_result_is_ambiguous_never_not_sent(tmp_path):
    w = make_world(tmp_path)
    assert w.check(0, 1)["go"]
    a0 = w.good_slot(0)
    w.write_ledger([a0, w.attempt(1)])
    w.write_lane_result([w.lane_child(0)])
    intake(w)
    assert states(w)["shot_02"] == ("AMBIGUOUS", "NO_RESULT_IN_BATCH")
    assert w.child_row(1)["outcome"] != "NOT_SENT"


def test_no_lane_result_at_all_holds_every_child(tmp_path):
    w = make_world(tmp_path)
    assert w.check(0, 1)["go"]
    w.write_ledger([w.attempt(0), w.attempt(1)])
    out = intake(w)
    assert out["state"] == "AMBIGUOUS"
    assert {r for _, r in states(w).values()} == {"LANE_RESULT_MISSING"}
    assert take_files(w) == []


def test_sha_mismatch_quarantines_the_clip_and_registers_nothing(tmp_path):
    w = make_world(tmp_path, n=1)
    assert w.check(0)["go"]
    w.write_clip(0)
    w.write_receipt(0, digest="0" * 64)
    w.write_ledger([w.attempt(0)])
    w.write_lane_result([w.lane_child(0)])
    out = intake(w)
    assert out["state"] == "AMBIGUOUS"
    assert states(w)["shot_01"][1] == "INTEGRITY_FAILED"
    assert take_files(w) == [] and list_takes(w.film) == []
    q = w.film / "takes" / "quarantine" / w.job["job_dir"]
    assert [p.name for p in q.iterdir()] == ["shot_01.mp4"] and (q / "shot_01.mp4").read_bytes() == w.clips["shot_01"]
    assert (w.batch_dir() / "shot_01.mp4").is_file()          # the original is never deleted
    assert "INTEGRITY_FAILED" in alarm_codes(w)
    assert attempt_of(w, 0)["status"] == "UNCONFIRMED" and w.child_row(0)["final"] == 0


def test_clip_listed_in_integrity_failed_is_quarantined_not_registered(tmp_path):
    w = make_world(tmp_path, n=1)
    assert w.check(0)["go"]
    w.write_clip(0)
    w.write_receipt(0)
    (w.batch_dir() / "integrity_failed.json").write_text(json.dumps({"clips": ["shot_01.mp4"]}), encoding="utf-8")
    w.write_ledger([w.attempt(0)])
    w.write_lane_result([w.lane_child(0)])
    intake(w)
    assert states(w)["shot_01"][1] == "INTEGRITY_FAILED" and take_files(w) == []
    assert (w.film / "takes" / "quarantine" / w.job["job_dir"] / "shot_01.mp4").is_file()


@pytest.mark.parametrize("what, reason", [
    ("two_clips", "CLIP_DUPLICATE_SLOT"),
    ("two_receipts", "RECEIPT_DUPLICATE_SLOT"),
    ("two_lane_entries", "LANE_RESULT_DUPLICATE_SLOT"),
    ("two_ledger_attempts", "LEDGER_ATTEMPT_DUPLICATE"),
])
def test_duplicate_slot_is_ambiguous(tmp_path, what, reason):
    w = make_world(tmp_path, n=1)
    assert w.check(0)["go"]
    att = w.good_slot(0)
    lane = [w.lane_child(0)]
    attempts = [att]
    if what == "two_clips":
        w.write_clip(0, w.clips["shot_01"], sub="copy")
    elif what == "two_receipts":
        (w.batch_dir() / "dup").mkdir()
        w.write_receipt(0, name="dup/shot_01_receipt.json")   # a second receipt for the same slot, other directory
    elif what == "two_lane_entries":
        lane.append(w.lane_child(0))
    else:
        attempts.append(dict(att))
    # two attempts for one slot: the writer puts them in one entry
    w.write_ledger(attempts)
    w.write_lane_result(lane)
    out = intake(w)
    assert out["state"] == "AMBIGUOUS" and states(w)["shot_01"][1] == reason, states(w)
    assert take_files(w) == [] and w.child_row(0)["final"] == 0


@pytest.mark.parametrize("over, reason_prefix", [
    ({"request_id": "11111111-1111-1111-1111-111111111111"}, "RECEIPT_IDENTITY_MISMATCH:request_id"),
    ({"batch_id": "ffffffffffff"}, "RECEIPT_IDENTITY_MISMATCH:batch_id"),
    ({"slot_id": "shot_99"}, "RECEIPT_IDENTITY_MISMATCH:slot_id"),
    ({"status": "weird"}, "RECEIPT_STATUS_UNKNOWN"),
])
def test_receipt_with_wrong_identity_or_status_is_ambiguous(tmp_path, over, reason_prefix):
    w = make_world(tmp_path, n=1)
    assert w.check(0)["go"]
    w.write_clip(0)
    w.write_receipt(0, **over)
    w.write_ledger([w.attempt(0)])
    w.write_lane_result([w.lane_child(0)])
    intake(w)
    assert states(w)["shot_01"][1].startswith(reason_prefix) and take_files(w) == []


def test_receipt_without_sha_or_malformed_is_ambiguous(tmp_path):
    w = make_world(tmp_path, n=2)
    assert w.check(0, 1)["go"]
    for i in (0, 1):
        w.write_clip(i)
    w.write_receipt(0, drop=("sha256",))
    (w.batch_dir() / "shot_02_receipt.json").write_text("{not json", encoding="utf-8")
    w.write_ledger([w.attempt(0), w.attempt(1)])
    w.write_lane_result([w.lane_child(0), w.lane_child(1)])
    intake(w)
    assert states(w)["shot_01"][1] == "RECEIPT_SHA_MISSING" and states(w)["shot_02"][1] == "RECEIPT_MALFORMED"
    assert take_files(w) == []


def test_lane_and_ledger_identity_contradictions_are_ambiguous(tmp_path):
    w = make_world(tmp_path, n=2)
    assert w.check(0, 1)["go"]
    a0, a1 = w.good_slot(0), w.good_slot(1)
    a1["input_digest"] = "f" * 64
    w.write_ledger([a0, a1])
    w.write_lane_result([w.lane_child(0, request_id="22222222-2222-2222-2222-222222222222"), w.lane_child(1)])
    intake(w)
    assert states(w)["shot_01"][1] == "LANE_IDENTITY_MISMATCH"
    assert states(w)["shot_02"][1] == "LEDGER_IDENTITY_MISMATCH"
    assert take_files(w) == []


# ---- the film ledger -------------------------------------------------------------------------------------------------
def test_missing_ledger_entry_is_ambiguous_with_an_alarm(tmp_path):
    w = make_world(tmp_path, n=2)
    assert w.check(0, 1)["go"]
    a0, _ = w.good_slot(0), w.good_slot(1)
    w.write_ledger([a0])   # slot 2 has clip + receipt + lane claim but no ledger attempt
    w.write_lane_result([w.lane_child(0), w.lane_child(1)])
    out = intake(w)
    assert out["state"] == "AMBIGUOUS" and out["attention"]
    assert states(w)["shot_02"] == ("AMBIGUOUS", "LEDGER_ATTEMPT_MISSING")
    assert "LEDGER_ATTEMPT_MISSING" in alarm_codes(w)
    assert take_files(w) == ["S1_v1_t1.mp4"]
    # intake never creates an attempt
    assert [a["slot_id"] for e in w.read_ledger()["entries"] for a in e["attempts"]] == ["shot_01"]
    assert w.child_row(1)["final"] == 0


@pytest.mark.parametrize("ledger", ["absent", "garbage", "wrong_shape"])
def test_absent_or_unreadable_ledger_holds_everything_and_never_settles_not_sent(tmp_path, ledger):
    w = make_world(tmp_path, n=2)
    w.clean_run(1)   # slot 1 checked + received; slot 2 never entered (PREPARING)
    if ledger == "garbage":
        w.write_ledger(None, raw="{nope")
    elif ledger == "wrong_shape":
        w.write_ledger(None, raw=json.dumps({"entries": "x"}))
    else:
        (w.muse / "film_send_ledger.json").unlink()
    out = intake(w)
    assert out["state"] == "AMBIGUOUS"
    assert {r for _, r in states(w).values()} == {"FILM_LEDGER_UNREADABLE_OR_INVALID"}
    assert w.child_row(1)["final"] == 0 and w.child_row(1)["outcome"] != "NOT_SENT"   # no settle_not_sent without a ledger
    assert take_files(w) == []


def test_ledger_attempt_marked_fenced_or_ineligible_is_ambiguous(tmp_path):
    w = make_world(tmp_path, n=1)
    assert w.check(0)["go"]
    a = w.good_slot(0)
    a["result_eligible"] = False
    w.write_ledger([a])
    w.write_lane_result([w.lane_child(0)])
    intake(w)
    assert states(w)["shot_01"][1] == "LEDGER_ATTEMPT_FENCED_OR_INELIGIBLE"


# ---- NOT_SENT ---------------------------------------------------------------------------------------------------------
def test_not_sent_only_when_the_broker_committed_it(tmp_path):
    w = make_world(tmp_path, n=2)
    assert w.check(0)["go"]                       # slot 1 entered, slot 2 still PREPARING
    a0 = w.good_slot(0)
    w.write_ledger([a0])
    w.write_lane_result([w.lane_child(0)])        # the lane says nothing about slot 2
    out = intake(w)
    # slot 2: PREPARING, no attempt, no lane entry, no files, valid ledger read -> settle_not_sent commits -> NOT_SENT
    assert states(w)["shot_02"] == ("NOT_SENT", "SETTLE_NOT_SENT_COMMITTED")
    assert w.child_row(1)["final"] == 1 and w.child_row(1)["outcome"] == "NOT_SENT"
    assert out["state"] == "REGISTERED"


def test_not_sent_proven_by_a_broker_commit_before_intake(tmp_path):
    w = make_world(tmp_path, n=1)
    assert w.settle_not_sent(0)["ok"]
    w.write_ledger([w.attempt(0, "PENDING_SEND")])
    w.write_lane_result([w.lane_child(0, "NOT_SENT_PROVEN")])
    out = intake(w)
    assert out["state"] == "NOT_SENT" and states(w)["shot_01"] == ("NOT_SENT", "BROKER_COMMITTED_NOT_SENT")
    a = attempt_of(w, 0)
    assert (a["status"], a["reason"], a["fenced"]) == ("RESOLVED", "NOT_SENT", True)


def test_lane_claim_of_not_sent_is_not_proof(tmp_path):
    w = make_world(tmp_path, n=1)
    assert w.check(0)["go"]                       # the child entered: the broker did not commit NOT_SENT
    w.write_ledger([w.attempt(0)])
    w.write_lane_result([w.lane_child(0, "NOT_SENT_PROVEN")])
    out = intake(w)
    assert out["state"] == "AMBIGUOUS" and states(w)["shot_01"][1] == "LANE_CUSTODY_NOT_SENT_PROVEN"
    assert w.child_row(0)["outcome"] != "NOT_SENT"


def test_preparing_child_with_a_ledger_attempt_is_ambiguous_not_settled(tmp_path):
    w = make_world(tmp_path, n=1)                 # never passed the pre-Enter check, but the lane wrote an attempt
    w.write_ledger([w.attempt(0)])
    w.write_lane_result([])
    intake(w)
    assert states(w)["shot_01"][1] == "CHILD_PREPARING_WITH_EVIDENCE"
    assert w.child_row(0)["final"] == 0


def test_no_settle_not_sent_flag_keeps_the_child_held(tmp_path):
    w = make_world(tmp_path, n=1)
    w.write_ledger([])
    w.write_lane_result([])
    intake(w, settle_unsent=False)
    assert states(w)["shot_01"][1] == "NO_ATTEMPT_NOT_SETTLED" and w.child_row(0)["final"] == 0


def test_broker_not_readable_holds_every_child(tmp_path):
    w = make_world(tmp_path, n=1)
    w.clean_run()
    out = intake(w, broker_db=tmp_path / "nope.sqlite3")
    assert states(w)["shot_01"][1] == "BROKER_UNREADABLE" and out["state"] == "AMBIGUOUS" and take_files(w) == []


# ---- FAILED_TERMINAL, halt, request integrity -------------------------------------------------------------------------
def test_explicit_failure_receipt_with_lane_agreement_is_failed_terminal(tmp_path):
    w = make_world(tmp_path, n=1)
    assert w.check(0)["go"]
    w.write_receipt(0, digest="0" * 64, status="failed")   # no clip
    w.write_ledger([w.attempt(0)])
    w.write_lane_result([w.lane_child(0, "FAILED_TERMINAL")])
    out = intake(w)
    assert states(w)["shot_01"] == ("FAILED_TERMINAL", "RECEIPT_EXPLICIT_FAILURE") and out["state"] == "FAILED"
    a = attempt_of(w, 0)
    assert (a["status"], a["reason"]) == ("RESOLVED", "FAILED_TERMINAL") and take_files(w) == []


def test_failure_claim_without_a_failure_receipt_is_ambiguous(tmp_path):
    w = make_world(tmp_path, n=1)
    assert w.check(0)["go"]
    w.write_ledger([w.attempt(0)])
    w.write_lane_result([w.lane_child(0, "FAILED_TERMINAL")])
    intake(w)
    assert states(w)["shot_01"][1] == "RECEIPT_MISSING"


def test_lane_exit_code_4_sets_the_afp_halt_once(tmp_path):
    from film_pipeline.production import halt as H
    w = make_world(tmp_path, n=1)
    w.clean_run()
    out = intake(w, lane_exit_code=4)
    assert out["post"].get("halt_set") is True
    assert w.store.find_job(w.job["job_key"])["halt_set"] == 1
    assert H.is_halted() and "lane" in H.halt_reason()
    intake(w, lane_exit_code=4)
    assert kinds(w).count("HALT_SET") == 1


def test_modified_batch_request_holds_every_child(tmp_path):
    w = make_world(tmp_path, n=2)
    w.clean_run()
    p = w.job_dir / "batch_request.json"
    p.write_text(p.read_text(encoding="utf-8").replace("max", "fast"), encoding="utf-8")
    out = intake(w)
    assert out["state"] == "AMBIGUOUS"
    assert {r for _, r in states(w).values()} == {"REQUEST_MODIFIED_OR_MISSING"} and take_files(w) == []


def test_a_take_file_conflict_is_ambiguous_and_nothing_is_overwritten(tmp_path):
    w = make_world(tmp_path, n=1)
    w.clean_run()
    (w.film / "takes").mkdir(exist_ok=True)
    (w.film / "takes" / "S1_v1_t1.mp4").write_bytes(b"someone else's file")
    intake(w)
    assert states(w)["shot_01"][1] == "TAKE_FILE_CONFLICT"
    assert (w.film / "takes" / "S1_v1_t1.mp4").read_bytes() == b"someone else's file"


def test_unknown_files_in_the_batch_are_reported_not_trusted(tmp_path):
    w = make_world(tmp_path, n=1)
    w.clean_run()
    (w.batch_dir() / "shot_77.mp4").write_bytes(b"stranger")
    out = intake(w)
    assert out["state"] == "REGISTERED" and "UNKNOWN_EVIDENCE" in alarm_codes(w) and out["attention"]
    assert take_files(w) == ["S1_v1_t1.mp4"]


def test_intake_of_an_unknown_or_unprepared_job(tmp_path):
    w = make_world(tmp_path, n=1)
    assert LI.intake_job("nope", store=w.store, broker_db=w.broker.db_path)["code"] == "NOT_FOUND"


# ---- regressions from the Codex review (round 1) ------------------------------------------------------------------------
def test_broker_committed_not_sent_with_an_unreadable_ledger_is_held(tmp_path):
    w = make_world(tmp_path, n=1)
    assert w.settle_not_sent(0)["ok"]
    w.write_ledger(None, raw="{nope")
    w.write_lane_result([])
    out = intake(w)
    assert out["state"] == "AMBIGUOUS" and states(w)["shot_01"][1] == "FILM_LEDGER_UNREADABLE_OR_INVALID"
    assert "LEDGER_UNREADABLE_NOT_SENT" in alarm_codes(w)


def test_batch_receipt_that_says_failed_contradicts_an_ok_slot_receipt(tmp_path):
    w = make_world(tmp_path, n=1)
    w.clean_run()
    s = w.slot(0)
    (w.batch_dir() / "batch_receipt.json").write_text(json.dumps(
        {"batch_id": w.job["job_dir"], "shots": [{"slot_id": s["slot_id"], "request_id": s["request_id"],
                                                   "status": "failed"}]}), encoding="utf-8")
    intake(w)
    assert states(w)["shot_01"][1] == "BATCH_RECEIPT_CONTRADICTS_SLOT_RECEIPT" and take_files(w) == []


def test_lane_entry_without_the_exact_identity_is_not_a_result(tmp_path):
    w = make_world(tmp_path, n=1)
    assert w.check(0)["go"]
    a = w.good_slot(0)
    w.write_ledger([a])
    child = w.lane_child(0)
    child.pop("request_id")
    w.write_lane_result([child])
    intake(w)
    assert states(w)["shot_01"][1] == "LANE_IDENTITY_INCOMPLETE" and take_files(w) == []


def test_a_broker_child_that_failed_elsewhere_cannot_be_a_result(tmp_path):
    import sqlite3
    w = make_world(tmp_path, n=1)
    w.clean_run()
    with sqlite3.connect(w.broker.db_path) as conn:
        conn.execute("UPDATE lease_children SET outcome = 'PROVIDER_FAILED', final = 1 WHERE child_key = ?",
                     (w.slot(0)["child_key"],))
    intake(w, settle_broker=False)
    assert states(w)["shot_01"][1] == "BROKER_STATE_CONTRADICTS_LANE" and take_files(w) == []


def test_verified_clips_are_promoted_only_for_registered_shots(tmp_path):
    w = make_world(tmp_path, n=2)
    assert w.check(0, 1)["go"]
    a0 = w.good_slot(0)
    w.write_clip(1)                                  # slot 2: clip but no receipt -> held
    w.write_ledger([a0, w.attempt(1)])
    w.write_lane_result([w.lane_child(0), w.lane_child(1)])
    vc = w.job_dir / "verified_clips"
    vc.mkdir()
    (vc / "S1.mp4").write_bytes(b"v1")
    (vc / "S2.mp4").write_bytes(b"v2")
    intake(w)
    assert states(w)["shot_02"][0] == "AMBIGUOUS"
    assert sorted(p.name for p in (w.muse / "verified_clips").iterdir()) == ["S1.mp4"]
    assert (w.film / "takes" / "jobs" / w.job["job_dir"] / "intake" / "verified_clips" / "S2.mp4").is_file()


def test_a_structured_lane_status_never_reaches_the_event_payload(tmp_path):
    w = make_world(tmp_path, n=1)
    assert w.check(0)["go"]
    w.write_ledger([w.attempt(0)])
    w.write_lane_result([], status={"lease_token": "SYNTHETIC_CANARY"})
    intake(w)
    dump = json.dumps(w.store.events(job_key=w.job["job_key"]), default=str)
    assert "SYNTHETIC_CANARY" not in dump and "TOKEN_FIELD_IN_LANE_RESULT" in alarm_codes(w)
