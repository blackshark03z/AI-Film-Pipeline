from __future__ import annotations

import json
import shutil
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace

from film_pipeline.production import money as M
from film_pipeline.production import report as R
from film_pipeline.production import takes as T
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


def test_ledger_adjustments_and_scene_checkpoints(tmp_path):
    root = _copy_film03(tmp_path)
    assert not M.adjustments_path(root).exists()
    empty = M.load_adjustments(root)
    assert empty.adjustments == [] and empty.checkpoints == []
    assert not M.adjustments_path(root).exists()  # load never creates files on disk

    # Legacy behavior stays intact without adjustments
    log = SimpleNamespace(takes=[SimpleNamespace(cost={"amount": 12.0, "unit": "credits"}, credits=12.0, output_file="a.mp4")])
    assert M.credit_ledger(log, {}) == {"logged": 12.0, "unresolved": {}, "pre_submit": [], "spent": 12.0}

    # Uncharged send (-6) + stray job (+12) + USD adjustment
    M.record_adjustment(root, -6.0, "FLOW_FAILED_NO_CLIP SC03_g22_t1", "takes/intents/SC03_g22_t1.intent.json", "agent:tech-lead")
    M.record_adjustment(root, 12.0, "stray job INC-001", "balance delta on account 02", "agent:tech-lead")
    M.record_adjustment(root, 1.5, "manual topup reconcile", "invoice #1", "human:owner", unit="USD")
    M.record_checkpoint(root, "SC01", "end", "571", 774.0, 18.0, note="clean scene close")

    loaded = M.load_adjustments(root)
    assert len(loaded.adjustments) == 3
    assert len(loaded.checkpoints) == 1
    assert loaded.checkpoints[0].observed_balance == 774.0

    full = M.money_ledger(log, {}, loaded.adjustments)
    assert full["credits"]["adjustments"] == 6.0
    assert full["credits"]["spent"] == 18.0
    assert full["USD"]["adjustments"] == 1.5
    assert full["USD"]["spent"] == 1.5

    cred = M.credit_ledger(log, {}, loaded.adjustments)
    assert cred["adjustments"] == 6.0
    assert cred["spent"] == 18.0

    # Report reflects adjustments on credits_spent
    clip = root / "media" / "takes" / "SC01_g1_t1.mp4"
    clip.parent.mkdir(parents=True, exist_ok=True)
    clip.write_bytes(b"clip")
    T.register_take(root, "film03_front_desk", "SC01_g1", clip, prompt_text="p", route="r", model="m", credits=12.0)
    rep = R.status_report(load_package(root))
    assert rep["production"]["credits_spent"] == 18.0


def test_cli_ledger_adjust_roundtrip(tmp_path):
    root = _copy_film03(tmp_path)
    r = subprocess.run(
        [sys.executable, str(TOOL), "ledger-adjust", "--film", str(root),
         "--add-adjustment", "--delta", "-6", "--reason", "FLOW_FAILED_NO_CLIP",
         "--evidence", "intent.json", "--by", "agent:tech-lead",
         "--checkpoint-scene", "SC01", "--boundary", "start", "--account", "02", "--observed-balance", "100"],
        capture_output=True, text=True, check=True, cwd=ROOT,
    )
    payload = json.loads(r.stdout)
    assert payload["money"]["credits"]["adjustments"] == -6.0
    assert payload["money"]["credits"]["spent"] == -6.0
    assert len(payload["adjustments"]) == 1
    assert len(payload["checkpoints"]) == 1
