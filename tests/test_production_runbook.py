"""P10-06: every command in RUNBOOK.md exists in the CLI; the review pack is self-contained and changes nothing."""
import re
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

from film_pipeline.production import report as R
from film_pipeline.production import reviewpack as RP
from film_pipeline.production.package import load_package

ROOT = Path(__file__).resolve().parents[1]
RUNBOOK = ROOT / "docs" / "production" / "RUNBOOK.md"
TOOL = ROOT / "tools" / "film.py"
FILM03 = ROOT / "films" / "film03_front_desk"


def runbook_commands():
    text = RUNBOOK.read_text(encoding="utf-8")
    blocks = re.findall(r"```bash\n(.*?)```", text, re.S)
    return [line.strip() for b in blocks for line in b.splitlines() if "tools/film.py" in line]


def help_of(action):
    done = subprocess.run([sys.executable, str(TOOL), action, "--help"], capture_output=True, text=True, encoding="utf-8",
                          env={**__import__("os").environ, "PYTHONPATH": str(ROOT / "src"), "PYTHONIOENCODING": "utf-8"},
                          check=False)
    assert done.returncode == 0, f"film.py {action} --help failed: {done.stderr[-200:]}"
    return done.stdout


def test_runbook_has_commands_for_every_step():
    cmds = runbook_commands()
    assert len(cmds) >= 25
    text = RUNBOOK.read_text(encoding="utf-8")
    for step in ("R1", "R2", "R3", "R4", "R5", "R6", "R7", "R8", "R9", "R10"):
        assert re.search(rf"^## {step} ", text, re.M), step


def test_every_runbook_action_and_flag_exists_in_the_cli():
    helps = {}
    for line in runbook_commands():
        action = re.search(r"film\.py (\w+)", line).group(1)
        helps.setdefault(action, help_of(action))
        for flag in re.findall(r"(?<!\S)(--[a-z0-9-]+)", line):
            assert flag in helps[action], f"{action}: runbook uses {flag}, the CLI has no such option"


def test_runbook_never_tells_anyone_to_flip_go_live():
    text = RUNBOOK.read_text(encoding="utf-8")
    assert "No agent flips it" in text and "OWNER_GO_LIVE: YES" in text


def test_runbook_steps_exist_for_every_next_action():
    steps = {s for _, s in R.RUNBOOK_STEPS}
    text = RUNBOOK.read_text(encoding="utf-8")
    assert all(re.search(rf"^## {s} ", text, re.M) for s in steps)
    assert R.runbook_step("Resolve Gate 3 (visual_spatial): the plan is stale") == "R3"
    assert R.runbook_step("Resolve Gate 2 (Direction): no vision") == "R2"
    assert R.runbook_step("Run film.py deliver") == "R10"
    assert R.runbook_step("something unknown") == ""


def test_status_names_the_runbook_step():
    r = R.status_report(load_package(FILM03))
    assert r["runbook"].startswith("docs/production/RUNBOOK.md")


def test_reviewpack_is_self_contained_and_reads_only(tmp_path):
    pkg_dir = tmp_path / "film"
    shutil.copytree(FILM03, pkg_dir, ignore=shutil.ignore_patterns("media", "delivery*"))
    frames = pkg_dir / "media" / "plan" / "storyboard"
    frames.mkdir(parents=True)
    from PIL import Image
    Image.new("RGB", (640, 360), (20, 80, 140)).save(frames / "SC01_g1.png")
    before = {p.relative_to(pkg_dir): p.read_bytes() for p in pkg_dir.rglob("*") if p.is_file() and "media" not in p.parts}
    result = RP.build(load_package(pkg_dir))
    page = Path(result["page"]).read_text(encoding="utf-8")
    assert result["frames"] == 1 and page.startswith("<!doctype html>")
    assert "data:image/jpeg;base64," in page
    assert not re.search(r"""(?:src|href)=["']https?://""", page) and "<script" not in page
    for needle in ("Gates", "Storyboard", "Budget", "Risks and fallbacks", "Rights waiting", "Takes awaiting review", "Next action"):
        assert needle in page
    after = {p.relative_to(pkg_dir): p.read_bytes() for p in pkg_dir.rglob("*") if p.is_file() and "media" not in p.parts}
    assert before == after
    assert "REHEARSAL" not in page


def test_reviewpack_stamps_a_rehearsal(tmp_path):
    import json
    pkg_dir = tmp_path / "film"
    shutil.copytree(FILM03, pkg_dir, ignore=shutil.ignore_patterns("media", "delivery*"))
    header = json.loads((pkg_dir / "film.json").read_text(encoding="utf-8"))
    header["rehearsal"] = True
    (pkg_dir / "film.json").write_text(json.dumps(header), encoding="utf-8")
    page = Path(RP.build(load_package(pkg_dir))["page"]).read_text(encoding="utf-8")
    assert "REHEARSAL — synthetic" in page
