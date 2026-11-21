"""S2-lite: job rows, frozen inputs and ``batch_request.json`` (contract section 5)."""
from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest

from film_pipeline.agentic import lane_jobs as LJ
from s2_lite_support import FILM_ID, make_world, sha


def _spec(w):
    ff = w.tmp / "first_frame.png"
    return {"film_root": str(w.film), "muse_film": str(w.muse), "wave_id": "w9", "kind": "video", "account_id": "acc_1",
            "lease_key": "L-w9", "epoch": 1, "muse_tag": "muse-v1.0-r15",
            "slots": [{"slot_id": "shot_01", "child_key": "k9", "shot_id": "S9", "shot_version": 1, "take_index": 1,
                       "input_digest": sha(b"x"), "prompt_text": "p", "inputs": [{"role": "first_frame", "path": str(ff)}]}]}


def test_job_dir_is_12_hex_of_the_job_key_and_the_request_is_exactly_the_contract(tmp_path):
    w = make_world(tmp_path)
    job = w.job
    assert job["job_key"] == f"{FILM_ID}:w1:video:acc_1"
    assert job["job_dir"] == LJ.job_dir_name(job["job_key"]) and len(job["job_dir"]) == 12
    assert w.job_dir == w.muse / "jobs" / job["job_dir"]
    assert list(w.request) == ["contract", "film_id", "wave_id", "batch_id", "kind", "account_id", "lease", "muse_tag",
                               "quality", "slots"]
    assert w.request["contract"] == "afp-muse-lane/1" and w.request["batch_id"] == job["job_dir"]
    assert w.request["lease"] == {"lease_key": "L-w1", "epoch": 1}
    assert list(w.slot(0)) == ["slot_id", "child_key", "shot_id", "shot_version", "take_index", "input_digest",
                               "request_id", "depends_on", "rebind_of"]
    assert w.slot(0)["rebind_of"] is None and w.slot(0)["depends_on"] == []
    # no capability anywhere in the request
    assert w.token not in (w.job_dir / "batch_request.json").read_text(encoding="utf-8")
    assert "token" not in (w.job_dir / "batch_request.json").read_text(encoding="utf-8").lower()
    assert job["state"] == "ADMITTED" and job["request_sha256"] == sha((w.job_dir / "batch_request.json").read_bytes())


def test_inputs_are_frozen_with_their_hashes_and_the_job_holds_the_frozen_digest(tmp_path):
    w = make_world(tmp_path)
    frozen = w.film / "takes" / "jobs" / w.job["job_dir"]
    doc = json.loads((frozen / "frozen.json").read_text(encoding="utf-8"))
    assert doc["frozen_digest"] == w.job["frozen_digest"] and len(w.job["frozen_digest"]) == 64
    slot = doc["slots"][0]
    assert slot["inputs"][0]["sha256"] == sha(b"png-bytes")
    assert (frozen / "shot_01" / slot["inputs"][0]["file"]).read_bytes() == b"png-bytes"
    assert (frozen / "shot_01" / "prompt.txt").read_text(encoding="utf-8") == "prompt 1"
    assert slot["prompt_sha256"] == sha(b"prompt 1")


def test_prepare_is_idempotent_and_a_changed_input_is_refused_while_the_job_is_live(tmp_path):
    w = make_world(tmp_path)
    spec = _spec(w)
    spec.update(wave_id="w1", lease_key="L-w1")   # the same job key as the world's job: other slots -> other digest
    again = LJ.prepare_job(spec, store=w.store)
    assert not again["ok"] and again["code"] == "JOB_DIGEST_CONFLICT"
    # the identical spec returns the existing job without rewriting anything
    same = LJ.prepare_job(_spec(w), store=w.store)
    first = LJ.prepare_job(_spec(w), store=w.store)
    assert same["ok"] and first["ok"] and first["created"] is False and first["job_dir"] == same["job_dir"]
    assert len(w.store.children(same["job_key"])) == 1


def test_the_job_dir_is_created_exclusively(tmp_path):
    w = make_world(tmp_path)
    spec = _spec(w)
    job_dir = w.muse / "jobs" / LJ.job_dir_name(LJ.make_job_key(FILM_ID, "w9", "video", "acc_1"))
    job_dir.mkdir(parents=True)
    (job_dir / "stray.txt").write_text("not ours", encoding="utf-8")
    out = LJ.prepare_job(spec, store=w.store)
    assert not out["ok"] and out["code"] == "JOB_DIR_EXISTS"
    assert (job_dir / "stray.txt").read_text(encoding="utf-8") == "not ours" and not (job_dir / "batch_request.json").exists()


@pytest.mark.parametrize("mutate, code", [
    (lambda s: s.update(lease_token="x"), "SECRET_IN_SPEC"),
    (lambda s: s["slots"][0].update(cookie="x"), "SECRET_IN_SPEC"),
    (lambda s: s.update(extra=1), "SPEC_INVALID"),
    (lambda s: s.update(kind="stills"), "KIND_NOT_SUPPORTED"),
    (lambda s: s["slots"][0].pop("prompt_text"), "SPEC_INVALID"),
    (lambda s: s["slots"][0].update(input_digest="nothex"), "SPEC_INVALID"),
    (lambda s: s["slots"][0]["inputs"][0].update(path="C:/nope/missing.png"), "INPUT_MISSING"),
    (lambda s: s["slots"].append(copy.deepcopy(s["slots"][0])), "SPEC_INVALID"),
    (lambda s: s["slots"].append({**s["slots"][0], "slot_id": "shot_02", "child_key": "k10", "take_index": 2}),
     "SPEC_INVALID"),   # two takes of one shot version never share a batch
])
def test_a_bad_spec_is_refused_and_nothing_is_written(tmp_path, mutate, code):
    w = make_world(tmp_path)
    spec = _spec(w)
    mutate(spec)
    out = LJ.prepare_job(spec, store=w.store)
    assert not out["ok"] and out["code"] == code
    assert not (w.muse / "jobs" / LJ.job_dir_name(LJ.make_job_key(FILM_ID, "w9", "video", "acc_1"))).exists()


def test_take_identity_rules_and_rebind(tmp_path):
    w = make_world(tmp_path, n=1)
    spec = _spec(w)
    spec["slots"][0].update(shot_id="S1", child_key="k9", slot_id="shot_01")
    # S1 v1 is held by the world's PENDING child: another wave may not take it
    busy = LJ.prepare_job(spec, store=w.store)
    assert not busy["ok"] and busy["code"] == "SHOT_VERSION_BUSY"
    # settle the first attempt NOT_SENT in the job DB (what intake does), then the identity needs a rebind
    with w.store.transaction() as conn:
        conn.execute("UPDATE children SET state = 'NOT_SENT' WHERE job_key = ?", (w.job["job_key"],))
    plain = LJ.prepare_job(spec, store=w.store)
    assert not plain["ok"] and plain["code"] == "TAKE_IDENTITY_EXISTS"
    wrong = copy.deepcopy(spec)
    wrong["slots"][0]["rebind_of"] = {"batch_id": "deadbeef0000", "request_id": w.slot(0)["request_id"]}
    assert LJ.prepare_job(wrong, store=w.store)["code"] == "REBIND_REFUSED"
    good = copy.deepcopy(spec)
    good["slots"][0]["rebind_of"] = {"batch_id": w.job["job_dir"], "request_id": w.slot(0)["request_id"]}
    out = LJ.prepare_job(good, store=w.store)
    assert out["ok"], out
    request = json.loads(Path(out["batch_request"]).read_text(encoding="utf-8"))
    assert request["slots"][0]["rebind_of"] == {"batch_id": w.job["job_dir"], "request_id": w.slot(0)["request_id"]}
    assert request["slots"][0]["request_id"] != w.slot(0)["request_id"]   # a fresh attempt id


def test_a_job_state_change_and_its_event_are_one_transaction(tmp_path):
    w = make_world(tmp_path)
    kinds = [e["kind"] for e in w.store.events(job_key=w.job["job_key"])]
    assert kinds == ["JOB_QUEUED", "JOB_ADMITTED"]
    # the events.jsonl projection is derived from the rows, id-keyed
    lines = [json.loads(x) for x in (w.film / "events.jsonl").read_text(encoding="utf-8").splitlines()]
    assert [x["kind"] for x in lines] == kinds and lines[0]["id"] < lines[1]["id"]
    assert LJ.project_events(w.store, w.film, FILM_ID) == 0   # nothing new, nothing duplicated
    # a failing transaction leaves neither the state change nor its event
    with pytest.raises(RuntimeError):
        with w.store.transaction() as conn:
            conn.execute("UPDATE jobs SET state = 'AMBIGUOUS' WHERE job_key = ?", (w.job["job_key"],))
            LJ.add_event(conn, film_id=FILM_ID, job_key=w.job["job_key"], kind="X")
            raise RuntimeError("boom")
    assert w.store.find_job(w.job["job_key"])["state"] == "ADMITTED"
    assert len(w.store.events(job_key=w.job["job_key"])) == 2
