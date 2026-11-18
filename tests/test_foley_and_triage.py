from __future__ import annotations

import json
import shutil
import subprocess
import sys
from pathlib import Path

from film_pipeline.production import dailies_triage as DT
from film_pipeline.production import edit as E
from film_pipeline.production import foley as F
from film_pipeline.production import sound_rights as SR
from film_pipeline.production import takes as T
from film_pipeline.production.edit import AudioCut, EditEvent, EditSection, Transition
from film_pipeline.production.package import load_package

ROOT = Path(__file__).resolve().parents[1]
FILM03 = ROOT / "films" / "film03_front_desk"
TOOL = ROOT / "tools" / "film.py"


def _copy_film03(tmp_path: Path) -> Path:
    root = tmp_path / "film"
    root.mkdir(parents=True)
    for name in ("film.json", "script.fountain", "01_story.json", "02_direction.json", "03_preprod.json", "04_shots.json"):
        shutil.copyfile(FILM03 / name, root / name)
    return root


def test_sfx_catalog_and_offline_foley_clears_sound_rights(tmp_path):
    if not shutil.which("ffmpeg"):
        return
    cat = F.load_catalog()
    ids = {e["id"] for e in cat["entries"]}
    assert {
        "paper_rustle", "envelope_open", "stamp_press", "ledger_close",
        "chair_creak", "footsteps_hallway", "door_latch", "keys_set_down",
        "cup_set_down", "pen_write",
    } <= ids

    root = _copy_film03(tmp_path)
    shots = json.loads((root / "04_shots.json").read_text(encoding="utf-8"))
    shots["generations"][0]["sfx"] = ["paper rustle", "stamp_press"]
    (root / "04_shots.json").write_text(json.dumps(shots, indent=2), encoding="utf-8")

    pkg = load_package(root)
    res = F.materialize_film_foley(pkg)
    assert [s["id"] for s in res["synthesized"]] == ["paper_rustle", "stamp_press"]
    assert all((root / s["rel_path"]).is_file() for s in res["synthesized"])

    checked = SR.check_assets(load_package(root))
    assert checked["issues"] == []
    assert len(checked["used"]) == 2
    ledger = SR.load_ledger(root)
    assert all(a.license == "GENERATED_OFFLINE" and a.status == "cleared" for a in ledger.assets)

    cli = subprocess.run([sys.executable, str(TOOL), "foley", "--film", str(root), "--list"], capture_output=True, text=True, cwd=ROOT)
    assert cli.returncode == 0
    assert json.loads(cli.stdout)["license"] == "GENERATED_OFFLINE"


def test_transition_alignment_issues_warns_on_scene_boundary_mismatch(tmp_path):
    root = _copy_film03(tmp_path)
    pkg = load_package(root)
    shots = pkg.typed["shots"].generations
    # Pick two shots from different scenes
    a_shot = shots[0]
    b_shot = next(g for g in shots if g.scene_id != a_shot.scene_id)

    direction = json.loads((root / "02_direction.json").read_text(encoding="utf-8"))
    direction["scenes"][b_shot.scene_id]["transition_in"] = {"kind": "DISSOLVE", "reason": "passage of time"}
    (root / "02_direction.json").write_text(json.dumps(direction, indent=2), encoding="utf-8")

    pkg = load_package(root)
    mismatch_sec = EditSection(events=[
        EditEvent(event_id="e1", take_id=f"{a_shot.generation_id}_t1"),
        EditEvent(event_id="e2", take_id=f"{b_shot.generation_id}_t1", transition=Transition(type="CUT", duration_s=0.0)),
    ])
    issues = E.transition_alignment_issues(pkg, mismatch_sec)
    assert len(issues) == 1
    assert issues[0]["code"] == "DIRECTION_TRANSITION_MISMATCH"
    assert issues[0]["severity"] == "WARN"
    assert issues[0]["between"] == ["e1", "e2"]

    cont = E.cut_continuity(pkg, mismatch_sec, {})
    assert any(i["code"] == "DIRECTION_TRANSITION_MISMATCH" for i in cont["issues"])

    matched_sec = EditSection(events=[
        EditEvent(event_id="e1", take_id=f"{a_shot.generation_id}_t1"),
        EditEvent(event_id="e2", take_id=f"{b_shot.generation_id}_t1", transition=Transition(type="DISSOLVE", duration_s=0.5)),
    ])
    assert E.transition_alignment_issues(pkg, matched_sec) == []

    # J_CUT check via AudioCut
    direction["scenes"][b_shot.scene_id]["transition_in"] = {"kind": "J_CUT", "reason": "lead audio"}
    (root / "02_direction.json").write_text(json.dumps(direction, indent=2), encoding="utf-8")
    pkg = load_package(root)
    assert E.transition_alignment_issues(pkg, EditSection(events=[
        EditEvent(event_id="e1", take_id=f"{a_shot.generation_id}_t1"),
        EditEvent(event_id="e2", take_id=f"{b_shot.generation_id}_t1", audio=AudioCut(j_cut_s=0.4)),
    ])) == []


def test_triage_take_returns_advisory_warnings_and_writes_no_reviews(tmp_path):
    if not (shutil.which("ffmpeg") and shutil.which("ffprobe")):
        return
    root = _copy_film03(tmp_path)
    pkg = load_package(root)
    gid = next(g.generation_id for g in pkg.typed["shots"].generations if g.dialogue)
    takes_dir = root / "media" / "takes"
    takes_dir.mkdir(parents=True, exist_ok=True)
    clip = takes_dir / f"{gid}_t1.mp4"
    # Solid black silent clip -> flat corner (CORNER_MARK_LOW_SIGNAL) & silent dialogue (SPEECH_ACTIVITY_LOW)
    subprocess.run([
        "ffmpeg", "-v", "error", "-y",
        "-f", "lavfi", "-i", "color=c=black:size=320x180:rate=24:duration=2",
        "-f", "lavfi", "-i", "anullsrc=r=48000:cl=mono:duration=2",
        "-c:v", "libx264", "-pix_fmt", "yuv420p", "-c:a", "aac", str(clip),
    ], check=True)
    T.register_take(root, pkg.header.film_id, gid, clip, prompt_text="p", route="r", model="m", credits=0.0)
    report = DT.triage_take(load_package(root), f"{gid}_t1")
    assert report["advisory_only"] is True
    assert report["auto_pass_forbidden"] is True
    codes = {w["code"] for w in report["warnings"]}
    assert "CORNER_MARK_LOW_SIGNAL" in codes
    assert "SPEECH_ACTIVITY_LOW" in codes
    assert not any((root / "takes" / "reviews").glob("*.json"))

    cli = subprocess.run([sys.executable, str(TOOL), "triage", "--film", str(root), "--take-id", f"{gid}_t1"],
                         capture_output=True, text=True, cwd=ROOT)
    assert cli.returncode == 0
    assert json.loads(cli.stdout)["advisory_only"] is True
