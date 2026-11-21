"""Codex r15d fixes: a drifted canonical clip is never blessed by qc-audit, and promote-take keeps batch provenance."""
import hashlib
import json
from pathlib import Path

import pytest

import muse_studio.cli as cli
from muse_studio.core.autoprod_orchestrator import _clip_currently_excluded
from muse_studio.core.batch_packager import BatchPackager
from muse_studio.core.film_qc_engine import FilmQCEngine
from muse_studio.tests.test_r15c_fixes import _canonical
from muse_studio.tests.test_review6_fixes import _audit, _fake_eval


@pytest.fixture(autouse=True)
def _temp_lease_registry(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("MUSE_LEASES_FILE", str(tmp_path / "lane_leases.json"))


def _sha(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def _drift(canonical: Path) -> str:
    """Replace the canonical copy with different content that would score best (tag `C`) and return its SHA."""
    canonical.write_bytes(b"C" + b"\x00" * (200 * 1024))  # over the 100 KB candidate floor
    return _sha(canonical)


# ---- A. qc-audit must not legitimise a canonical clip whose content changed since the last audit --------------------
def test_qc_audit_does_not_bless_a_drifted_canonical_copy(tmp_path: Path, monkeypatch, capsys):
    proj, sid, c1, canonical, rec = _canonical(tmp_path, monkeypatch, capsys)
    old_copy_sha = rec["copy_sha256"]
    drifted = _drift(canonical)
    drifted_bytes = canonical.read_bytes()
    monkeypatch.setattr(FilmQCEngine, "evaluate_generated_clip", _fake_eval({"A": 80.0, "B": 40.0, "C": 99.0}))
    assert cli.main(["qc-audit", str(proj)]) == 0
    capsys.readouterr()
    audit = _audit(proj)
    new = audit["per_shot_qc"][sid]
    assert new["copy_sha256"] != drifted, "qc-audit recorded the SHA of a canonical copy nobody verified"
    assert canonical.read_bytes()[:1] == b"A", "the drifted canonical won selection"
    assert new["copy_sha256"] == old_copy_sha == _sha(canonical) == _sha(c1)  # re-copied from the verified source
    assert new["clip_path"] == str(c1)
    assert not _clip_currently_excluded(str(canonical), new)
    kept = [p for p in proj.rglob("*.mp4") if p.read_bytes() == drifted_bytes]
    assert kept, "the drifted copy must be kept (quarantined), never deleted"


def test_qc_audit_drops_a_drifted_canonical_when_no_verified_source_is_left(tmp_path: Path, monkeypatch, capsys):
    proj, sid, c1, canonical, rec = _canonical(tmp_path, monkeypatch, capsys)
    drifted = _drift(canonical)
    for bdir in (proj / "BATCHES_V2").iterdir():  # every batch clip is gone: only the drifted canonical is left
        for clip in (bdir / "verified_clips").glob("*.mp4"):
            clip.unlink()
    monkeypatch.setattr(FilmQCEngine, "evaluate_generated_clip", _fake_eval({"A": 80.0, "B": 40.0, "C": 99.0}))
    assert cli.main(["qc-audit", str(proj)]) == 0
    capsys.readouterr()
    audit = _audit(proj)
    assert sid not in audit["passed_clips"], "a drifted canonical copy passed with no verified source"
    assert (audit.get("per_shot_qc") or {}).get(sid, {}).get("copy_sha256") != drifted
    entry = next(f for f in audit["failed_or_missing"] if f["shot_id"] == sid)
    assert entry["reason"] == "INTEGRITY_FAILED" and entry["cause"] == "CANONICAL_SHA_MISMATCH"


# ---- B. promote-take through the canonical fallback keeps the source batch as provenance --------------------------------
def _promote_via_canonical(tmp_path: Path, monkeypatch, capsys):
    proj, sid, c1, canonical, rec = _canonical(tmp_path, monkeypatch, capsys)
    assert cli.main(["qc-audit", str(proj)]) == 0  # the canonical copy of take 1 is now a recorded candidate too
    capsys.readouterr()
    c1.unlink()  # the immutable source is gone; the canonical still matches the audited SHA
    rc = cli.main(["promote-take", str(proj), sid, "1"])
    out = capsys.readouterr().out
    return proj, sid, c1, canonical, rc, out


def test_promote_take_fallback_keeps_the_source_batch_provenance(tmp_path: Path, monkeypatch, capsys):
    proj, sid, c1, canonical, rc, out = _promote_via_canonical(tmp_path, monkeypatch, capsys)
    assert rc == 0, out
    rec = _audit(proj)["per_shot_qc"][sid]
    assert rec["selected_by"] == "promote-take"
    assert Path(rec["source_clip_path"]) == c1, "provenance must name the original source batch clip"
    assert Path(rec["copy_source_path"]) == canonical
    assert not cli._clip_integrity_bad(canonical, rec)
    BatchPackager.record_integrity_failure(c1.parent.parent, c1.name)  # the source batch is excluded later
    assert cli._clip_integrity_bad(canonical, rec)
    assert _clip_currently_excluded(str(canonical), rec)
    assert BatchPackager.clip_currently_excluded(canonical, {"copy_sha256": rec["copy_sha256"],
                                                             "source_clip_path": str(c1), "clip_path": str(canonical)})
    assert canonical.exists()


def test_promote_take_refuses_when_no_batch_provenance_can_be_established(tmp_path: Path, monkeypatch, capsys):
    proj, sid, c1, canonical, rec = _canonical(tmp_path, monkeypatch, capsys)
    assert cli.main(["qc-audit", str(proj)]) == 0
    capsys.readouterr()
    audit_p = proj / "qc_audit_report.json"
    audit = json.loads(audit_p.read_text(encoding="utf-8"))
    for c in audit["per_shot_qc"][sid]["candidates"]:
        if c["take"] == 1:
            c["clip_path"] = str(canonical)  # the record no longer names any batch clip
            c["candidate_path"] = str(canonical)
            c["sha256"] = _sha(canonical)
    audit_p.write_text(json.dumps(audit), encoding="utf-8")
    c1.unlink()
    before = audit_p.read_text(encoding="utf-8")
    rc = cli.main(["promote-take", str(proj), sid, "1"])
    out = json.loads(capsys.readouterr().out)
    assert rc == 1 and out["error"] == "PROVENANCE_UNKNOWN", out
    assert audit_p.read_text(encoding="utf-8") == before, "a refused promotion must not touch the audit"
