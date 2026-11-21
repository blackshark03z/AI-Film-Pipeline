"""S2-lite: ``afp-film lane prepare|intake|status`` (synchronous, JSON out, stable exit codes)."""
from __future__ import annotations

import json

from film_pipeline import cli
from s2_lite_support import FILM_ID, make_world, sha


def run(capsys, *argv):
    code = cli.main(list(argv))
    out = capsys.readouterr().out
    return code, json.loads(out[out.index("{"):])


def _spec(w):
    return {"film_root": str(w.film), "muse_film": str(w.muse), "wave_id": "w7", "kind": "video", "account_id": "acc_1",
            "lease_key": "L-w7", "epoch": 1, "muse_tag": "muse-v1.0-r15",
            "slots": [{"slot_id": "shot_01", "child_key": "k7", "shot_id": "S7", "shot_version": 1, "take_index": 1,
                       "input_digest": sha(b"z"), "prompt_text": "p",
                       "inputs": [{"role": "first_frame", "path": str(w.tmp / "first_frame.png")}]}]}


def test_prepare_status_and_usage_errors(tmp_path, capsys):
    w = make_world(tmp_path, n=1)
    db = str(tmp_path / "jobs.sqlite3")
    spec = tmp_path / "spec.json"
    spec.write_text(json.dumps(_spec(w)), encoding="utf-8")
    code, out = run(capsys, "lane", "prepare", "--spec", str(spec), "--jobs-db", db)
    assert code == 0 and out["ok"] and out["created"] is True and len(out["job_dir"]) == 12
    code, again = run(capsys, "lane", "prepare", "--spec", str(spec), "--jobs-db", db)
    assert code == 0 and again["created"] is False and again["job_dir"] == out["job_dir"]
    code, st = run(capsys, "lane", "status", "--job", out["job_dir"], "--jobs-db", db)
    assert code == 0 and st["job"]["state"] == "ADMITTED" and [e["kind"] for e in st["events"]] == ["JOB_QUEUED", "JOB_ADMITTED"]
    assert run(capsys, "lane", "prepare", "--jobs-db", db)[0] == 2
    assert run(capsys, "lane", "intake", "--jobs-db", db)[0] == 2
    code, nf = run(capsys, "lane", "status", "--job", "zzz", "--jobs-db", db)
    assert code == 3 and nf["code"] == "NOT_FOUND"
    bad = tmp_path / "bad.json"
    bad.write_text("{", encoding="utf-8")
    assert run(capsys, "lane", "prepare", "--spec", str(bad), "--jobs-db", db)[0] == 2
    bad.write_text(json.dumps({**_spec(w), "lease_token": "x"}), encoding="utf-8")
    code, refused = run(capsys, "lane", "prepare", "--spec", str(bad), "--jobs-db", db)
    assert code == 3 and refused["code"] == "SECRET_IN_SPEC"


def test_intake_exit_codes_ok_then_attention(tmp_path, capsys):
    w = make_world(tmp_path, n=1)
    db, bdb = str(tmp_path / "jobs.sqlite3"), str(w.broker.db_path)
    w.clean_run()
    code, out = run(capsys, "lane", "intake", "--job", w.job["job_key"], "--jobs-db", db, "--broker-db", bdb)
    assert code == 0 and out["state"] == "REGISTERED"
    w2 = make_world(tmp_path / "second", n=1)
    code, out = run(capsys, "lane", "intake", "--job", w2.job["job_key"], "--jobs-db", str(tmp_path / "second" / "jobs.sqlite3"),
                    "--broker-db", str(w2.broker.db_path), "--no-broker-settle")   # no lane files: held
    assert code == 1 and out["state"] == "AMBIGUOUS" and out["attention"]
