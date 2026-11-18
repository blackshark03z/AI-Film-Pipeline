from __future__ import annotations

import json
import shutil
import subprocess
import sys
from pathlib import Path

from film_pipeline.production import deliver as D
from film_pipeline.production.gates import evaluate_gates, sync_header_gates
from film_pipeline.production.package import load_package

ROOT = Path(__file__).resolve().parents[1]
FILM03 = ROOT / "films" / "film03_front_desk"
TOOL = ROOT / "tools" / "film.py"


def _copy_film(tmp_path: Path) -> Path:
    root = tmp_path / "film"
    root.mkdir(parents=True)
    for name in ("film.json", "script.fountain", "01_story.json", "02_direction.json", "03_preprod.json", "04_shots.json"):
        shutil.copyfile(FILM03 / name, root / name)
    return root


def test_sync_header_gates_updates_editable_film_and_cli_validate(tmp_path):
    root = _copy_film(tmp_path)
    pkg = load_package(root)
    assert all(v == "NOT_RUN" for v in pkg.header.gates.values())

    r = subprocess.run(
        [sys.executable, str(TOOL), "validate", "--film", str(root), "--sync-gates"],
        capture_output=True, text=True, cwd=ROOT,
    )
    data = json.loads(r.stdout)
    expected = {g: info["status"] for g, info in data["gates"].items()}
    assert data["synced_gates"] == expected
    reloaded = load_package(root)
    assert reloaded.header.gates == expected


def test_sync_header_gates_preserves_verified_or_accepted_archive(tmp_path):
    root = _copy_film(tmp_path)
    (root / "07_delivery.json").write_text(
        json.dumps({"delivery": {"manifest": "delivery/MANIFEST.json", "owner_acceptance": {"by": "owner"}}}),
        encoding="utf-8",
    )
    pkg = load_package(root)
    orig = dict(pkg.header.gates)
    res = sync_header_gates(pkg)
    assert res == orig
    assert json.loads((root / "film.json").read_text(encoding="utf-8"))["gates"] == orig


def test_deliver_syncs_film_json_gates_and_reuses_archive(tmp_path):
    from test_production_deliver import deliver, needs_ffmpeg, pipeline
    if not (shutil.which("ffmpeg") and shutil.which("ffprobe")):
        return
    root, cut_report = pipeline(tmp_path)
    first = deliver(root, cut_report)[1]
    assert first["ok"] is True and first["reused"] is False
    arch = root / Path(first["archive"])
    verified = D.verify_archive(arch)
    assert verified["ok"] is True

    root_gates = json.loads((root / "film.json").read_text(encoding="utf-8"))["gates"]
    arch_gates = json.loads((arch / "package" / "film.json").read_text(encoding="utf-8"))["gates"]
    evaluated = {r.gate: r.status for r in evaluate_gates(load_package(root))}
    assert root_gates == arch_gates
    assert root_gates["6"] == "OWNER_PENDING"
    assert all(root_gates[g] == evaluated[g] for g in ("1", "2", "3", "4", "5"))
    assert root_gates["5"] == evaluated["5"]

    second = deliver(root, cut_report)[1]
    assert second["reused"] is True
