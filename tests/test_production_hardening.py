"""Review findings (Codex gpt-6.1-sol, 2026-11-06) turned into regression tests."""
import json
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

from film_pipeline.production.package import PackageError, load_package
from film_pipeline.production.plan import plan_package

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "films" / "film03_front_desk"
TAKES = ROOT / "docs" / "drama" / "film03" / "takes"
FILM = ROOT / "tools" / "film.py"


@pytest.fixture()
def pkg_dir(tmp_path):
    dest = tmp_path / "p"
    shutil.copytree(SRC, dest)
    return dest


def edit(path: Path, fn):
    data = json.loads(path.read_text(encoding="utf-8"))
    fn(data)
    path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")


def issues(pkg_dir):
    return load_package(pkg_dir).issues


def test_bad_references_are_load_issues_not_crashes(pkg_dir):
    edit(pkg_dir / "04_shots.json", lambda d: d["generations"][0].update(start_state="nope", scene_id="SC99"))
    found = issues(pkg_dir)
    assert any("unknown start_state" in i for i in found) and any("unknown scene_id" in i for i in found)


def test_unknown_character_and_coverage_rejected(pkg_dir):
    edit(pkg_dir / "04_shots.json", lambda d: d["generations"][1].update(visible=["GHOST"]))
    assert any("unknown character 'GHOST'" in i for i in issues(pkg_dir))
    edit(pkg_dir / "04_shots.json", lambda d: d["generations"][1].update(visible=["NORA"], coverage="CLOSEUP"))
    assert any("coverage" in i for i in issues(pkg_dir))


def test_self_and_forward_predecessor_rejected(pkg_dir):
    edit(pkg_dir / "04_shots.json", lambda d: d["generations"][1].update(previous_generation_id="SC01_g2"))
    assert any("earlier generation" in i for i in issues(pkg_dir))
    edit(pkg_dir / "04_shots.json", lambda d: d["generations"][1].update(previous_generation_id="SC08_g2"))
    assert any("earlier generation" in i for i in issues(pkg_dir))


def test_path_like_ids_rejected(pkg_dir):
    def evil(d):
        d["generations"][0]["generation_id"] = "../../victim"
        d["generations"][0]["choreography"]["generation_id"] = "../../victim"
    edit(pkg_dir / "04_shots.json", evil)
    assert issues(pkg_dir) and "victim" in "".join(issues(pkg_dir))
    with pytest.raises(PackageError):
        plan_package(load_package(pkg_dir), pkg_dir / "out")  # typed shots section failed to load


def test_unsupported_aspect_is_refused(pkg_dir):
    edit(pkg_dir / "film.json", lambda d: d.update(aspect="9:16"))
    with pytest.raises(PackageError, match="aspect"):
        plan_package(load_package(pkg_dir), pkg_dir / "out")


def test_storyboard_is_pending_unless_reviewer_named(pkg_dir, tmp_path):
    pytest.importorskip("PIL")
    pending = plan_package(load_package(pkg_dir), tmp_path / "a", takes_dir=TAKES)
    assert not pending.ok and any("preflight BLOCKED" in p for p in pending.problems)
    approved = plan_package(load_package(pkg_dir), tmp_path / "b", takes_dir=TAKES, approve_storyboard="QA")
    assert approved.ok, approved.problems


def test_plan_exit_code_reflects_non_generation_blocks(pkg_dir, tmp_path):
    pytest.importorskip("PIL")
    # story order going backwards on a linear cut is a TEMPORAL_ORDER BLOCK outside any single generation
    edit(pkg_dir / "03_preprod.json", lambda d: d["scenes"]["SC02"]["story_time"].update(story_order=0.5))
    result = plan_package(load_package(pkg_dir), tmp_path / "o", takes_dir=TAKES, approve_storyboard="QA")
    assert not result.ok and any("TEMPORAL" in p for p in result.problems)
    cli = subprocess.run([sys.executable, str(FILM), "plan", "--film", str(pkg_dir), "--out", str(tmp_path / "o2"),
                          "--takes", str(TAKES), "--approve-storyboard", "QA"],
                         capture_output=True, text=True, encoding="utf-8")
    assert cli.returncode == 1 and "TEMPORAL" in cli.stdout


def test_unassigned_dialogue_is_a_problem(pkg_dir, tmp_path):
    text = (pkg_dir / "script.fountain").read_text(encoding="utf-8")
    marker = "Roll call is at eight, Sergeant."
    assert marker in text
    (pkg_dir / "script.fountain").write_text(text.replace(marker, marker + "\n\nKESSLER\nOne more line.", 1),
                                             encoding="utf-8")
    result = plan_package(load_package(pkg_dir), tmp_path / "o", takes_dir=TAKES, storyboard=False)
    assert any("DIALOGUE_UNASSIGNED" in p for p in result.problems)


def test_validate_fails_on_package_issues_outside_gate_files(pkg_dir):
    (pkg_dir / "ledger.json").write_text("{broken", encoding="utf-8")
    out = subprocess.run([sys.executable, str(FILM), "validate", "--film", str(pkg_dir)],
                         capture_output=True, text=True, encoding="utf-8")
    report = json.loads(out.stdout)
    assert out.returncode == 1 and any("ledger.json" in i for i in report["package_issues"])
