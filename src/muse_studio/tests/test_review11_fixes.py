"""Regression tests for review 11: a canonical clip is judged by its own SHA-256, never by its source's state."""
import hashlib
import json
from pathlib import Path

import pytest

import muse_studio.cli as cli
from muse_studio.core.batch_packager import BatchPackager
from muse_studio.tests.test_parallel_pool_nx6 import _seed_manifest_project
from muse_studio.tests.test_review6_fixes import BIG, _audit
from muse_studio.tests.test_review7_fixes import _two_take_audit


def _promote_then_break_source(proj: Path, monkeypatch, capsys, how: str):
    """Promote take 2, remove take 1, then make take 2's source fail integrity while the canonical stays intact."""
    sid, c1, c2 = _two_take_audit(proj, monkeypatch, capsys)
    assert cli.main(["promote-take", str(proj), sid, "2"]) == 0
    capsys.readouterr()
    c1.unlink()  # no other candidate is left: the canonical is the shot's last good clip
    good_sha = hashlib.sha256(c2.read_bytes()).hexdigest()
    if how == "receipt":
        (c2.parent / "batch_receipt.json").write_text(json.dumps({"shots": [
            {"shot_id": sid, "output_file": c2.name, "sha256": good_sha}]}), encoding="utf-8")
        c2.write_bytes(b"ROT" + b"\x00" * BIG)  # the source rots after the promote
    else:
        BatchPackager.record_integrity_failure(c2.parent.parent, c2.name)  # integrity mark on the source
    return sid, good_sha


@pytest.mark.parametrize("how", ["receipt", "mark"])
def test_intact_canonical_survives_corrupt_source(tmp_path: Path, monkeypatch, capsys, how):
    proj = _seed_manifest_project(tmp_path / "proj", num_shots=1)
    sid, good_sha = _promote_then_break_source(proj, monkeypatch, capsys, how)
    canonical = proj / "verified_clips" / f"{sid}.mp4"
    assert cli.main(["qc-audit", str(proj)]) == 0
    capsys.readouterr()
    audit = _audit(proj)
    assert canonical.exists(), "qc-audit deleted the intact canonical clip"
    assert hashlib.sha256(canonical.read_bytes()).hexdigest() == good_sha
    assert sid in audit["passed_clips"], audit["failed_or_missing"]
    rec = audit["per_shot_qc"][sid]
    assert rec["take"] == 2 and rec.get("selected_by") == "promote-take" and rec.get("sha256") == good_sha


@pytest.mark.parametrize("how", ["receipt", "mark"])
def test_corrupt_canonical_of_corrupt_source_is_quarantined(tmp_path: Path, monkeypatch, capsys, how):
    proj = _seed_manifest_project(tmp_path / "proj", num_shots=1)
    sid, _ = _promote_then_break_source(proj, monkeypatch, capsys, how)
    canonical = proj / "verified_clips" / f"{sid}.mp4"
    canonical.write_bytes(b"BZ" + b"\x00" * BIG)  # the canonical itself no longer matches the recorded SHA
    assert cli.main(["qc-audit", str(proj)]) == 0
    capsys.readouterr()
    audit = _audit(proj)
    assert sid not in audit["passed_clips"], "a corrupt canonical was silently kept"
    assert not canonical.exists()
    quarantined = list((proj / "verified_clips" / "integrity_failed").glob(f"{sid}*.mp4"))
    assert len(quarantined) == 1 and quarantined[0].read_bytes()[:2] == b"BZ", "the corrupt canonical was not quarantined"
    entry = next(e for e in audit["failed_or_missing"] if e["shot_id"] == sid)
    assert entry["reason"] == "INTEGRITY_FAILED" and entry.get("quarantined_to") == str(quarantined[0])
