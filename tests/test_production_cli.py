import json
import subprocess
import sys
from pathlib import Path

from film_pipeline.production.gates import evaluate_gates, register_validator
from film_pipeline.production import gates as gates_mod
from film_pipeline.production.package import load_package

FILM = Path(__file__).resolve().parents[1] / "tools" / "film.py"


def run(*args):
    return subprocess.run([sys.executable, str(FILM), *args], capture_output=True, text=True, encoding="utf-8")


def test_new_then_validate_blocks_cleanly(tmp_path):
    out = run("new", "t1", "--profile", "drama", "--root", str(tmp_path))
    assert out.returncode == 0, out.stderr
    assert (tmp_path / "t1" / "script.fountain").exists() and (tmp_path / "t1" / "media").is_dir()
    val = run("validate", "--film", str(tmp_path / "t1"))
    assert val.returncode == 1, val.stderr
    report = json.loads(val.stdout)
    assert report["blocked"] is True
    assert "story empty" in report["gates"]["1"]["issues"]
    assert "script.fountain has no scenes" in report["gates"]["1"]["issues"]
    assert report["gates"]["2"]["status"] == "BLOCK"
    assert "Traceback" not in val.stderr


def test_new_refuses_overwrite_and_narration_has_no_script(tmp_path):
    assert run("new", "n1", "--profile", "narration", "--root", str(tmp_path)).returncode == 0
    assert not (tmp_path / "n1" / "script.fountain").exists()
    again = run("new", "n1", "--profile", "narration", "--root", str(tmp_path))
    assert again.returncode == 2 and "refusing to overwrite" in again.stdout


def test_status_and_missing_film(tmp_path):
    run("new", "t2", "--profile", "narration", "--root", str(tmp_path))
    st = run("status", "--film", str(tmp_path / "t2"))
    data = json.loads(st.stdout)
    assert st.returncode == 0 and data["stages_empty"] and data["gates"]["1"] == "BLOCK"
    bad = run("status", "--film", str(tmp_path / "nope"))
    assert bad.returncode == 2 and "film.json not found" in bad.stdout


def test_present_stage_without_validator_is_not_pass(tmp_path):
    run("new", "t3", "--profile", "narration", "--root", str(tmp_path))
    (tmp_path / "t3" / "01_story.json").write_text('{"concept": "c"}')
    res = {r.gate: r for r in evaluate_gates(load_package(tmp_path / "t3"))}
    assert res["1"].status == "NOT_RUN"


def test_registered_validator_decides(tmp_path):
    run("new", "t4", "--profile", "narration", "--root", str(tmp_path))
    (tmp_path / "t4" / "01_story.json").write_text('{"concept": "c"}')
    try:
        register_validator("1", lambda pkg: [])
        assert evaluate_gates(load_package(tmp_path / "t4"))[0].status == "PASS"
        register_validator("1", lambda pkg: ["logline missing"])
        first = evaluate_gates(load_package(tmp_path / "t4"))[0]
        assert first.status == "BLOCK" and first.issues == ["logline missing"]
    finally:
        gates_mod._VALIDATORS.clear()


def test_plan_command_on_film03(tmp_path):
    film = Path(__file__).resolve().parents[1] / "films" / "film03_front_desk"
    takes = film.parents[1] / "docs" / "drama" / "film03" / "takes"
    # without reviewed takes the handoffs are unverified, so preflight blocks (by design)
    blocked = run("plan", "--film", str(film), "--out", str(tmp_path / "ob"))
    assert blocked.returncode == 1 and '"BLOCKED"' in blocked.stdout
    out = run("plan", "--film", str(film), "--out", str(tmp_path / "o"), "--takes", str(takes))
    assert out.returncode == 0, out.stdout + out.stderr
    report = json.loads(out.stdout)
    assert len(report["generations"]) == 16 and all(v["verdict"] == "PASS" for v in report["generations"].values())
    assert (tmp_path / "o" / "prompts" / "SC01_g1.txt").is_file()
    # a package without the typed sections cannot be planned
    run("new", "n9", "--profile", "drama", "--root", str(tmp_path))
    bad = run("plan", "--film", str(tmp_path / "n9"), "--out", str(tmp_path / "o2"))
    assert bad.returncode == 2 and "plan needs" in bad.stdout
