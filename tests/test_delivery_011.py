"""Package-011 S11 — DeliveryPackage contract offline proofs."""
import hashlib
from pathlib import Path

import pytest

from film_pipeline.delivery import (
    DeliveryEntry, DeliveryManifest, finalize, undeclared_files, verify)


def entry(tmp_path, name="a.mp4", role="master", data=b"payload"):
    path = tmp_path / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)
    media = "application/json" if name.endswith(".json") else "video/mp4"
    return DeliveryEntry(role=role, path=name,
                         sha256=hashlib.sha256(data).hexdigest(),
                         bytes=len(data), media_type=media,
                         source_lineage="canonical master")


def make_manifest(tmp_path):
    return DeliveryManifest(
        film_id="swordsman_film", entries=[entry(tmp_path)])


def test_finalize_mints_identity_and_verifies(tmp_path):
    unfrozen = make_manifest(tmp_path)
    assert unfrozen.delivery_id is None
    frozen = finalize(unfrozen, tmp_path)
    assert frozen.delivery_id.startswith("delivery_")
    assert verify(frozen, tmp_path)["result"] == "PASS"


def test_finalize_refuses_missing_file(tmp_path):
    manifest = make_manifest(tmp_path)
    (tmp_path / "a.mp4").unlink()
    with pytest.raises(ValueError, match="missing"):
        finalize(manifest, tmp_path)


def test_finalize_refuses_checksum_mismatch(tmp_path):
    manifest = make_manifest(tmp_path)
    (tmp_path / "a.mp4").write_bytes(b"tampered")
    with pytest.raises(ValueError, match="checksum mismatch"):
        finalize(manifest, tmp_path)


def test_finalized_manifest_is_immutable(tmp_path):
    frozen = finalize(make_manifest(tmp_path), tmp_path)
    tampered = frozen.model_copy(update={
        "entries": [entry(tmp_path, data=b"other")]})
    with pytest.raises(ValueError, match="modified after finalize"):
        verify(tampered, tmp_path)


def test_verify_detects_later_tamper(tmp_path):
    frozen = finalize(make_manifest(tmp_path), tmp_path)
    (tmp_path / "a.mp4").write_bytes(b"later tamper")
    result = verify(frozen, tmp_path)
    assert result["result"] == "FAIL" and result["bad_checksum"]


def test_undeclared_files_detected(tmp_path):
    frozen = finalize(make_manifest(tmp_path), tmp_path)
    (tmp_path / "extra.txt").write_text("undeclared")
    assert undeclared_files(frozen, tmp_path, tmp_path) == ["extra.txt"]


def test_absolute_and_dotdot_paths_refused():
    with pytest.raises(ValueError, match="relative"):
        DeliveryEntry(role="master", path="C:/abs/a.mp4", sha256="0" * 64,
                      bytes=1, media_type="video/mp4",
                      source_lineage="x")
    with pytest.raises(ValueError, match="relative"):
        DeliveryEntry(role="master", path="../escape.mp4", sha256="0" * 64,
                      bytes=1, media_type="video/mp4", source_lineage="x")


def test_unknown_role_refused():
    with pytest.raises(ValueError, match="unknown delivery role"):
        DeliveryEntry(role="marketing_thumbnail", path="a.mp4",
                      sha256="0" * 64, bytes=1, media_type="video/mp4",
                      source_lineage="x")


def test_duplicate_paths_refused(tmp_path):
    e1 = entry(tmp_path, name="a.mp4", data=b"1")
    with pytest.raises(ValueError, match="duplicate delivery paths"):
        DeliveryManifest(film_id="f",
                         entries=[e1, e1], delivery_id=None) and None
        DeliveryManifest(film_id="f", entries=[e1, e1],
                         delivery_id="delivery_" + "0" * 64)


def test_multi_receipt_semantic_roles_allowed(tmp_path):
    e1 = entry(tmp_path, name="a.mp4", data=b"1")
    e2 = entry(tmp_path, name="r1.json", role="semantic_qc", data=b"2")
    e3 = entry(tmp_path, name="r2.json", role="semantic_qc", data=b"3")
    m = DeliveryManifest(film_id="f", entries=[e1, e2, e3],
                         delivery_id=None)
    assert len(m.entries) == 3


def test_media_type_extension_binding(tmp_path):
    with pytest.raises(ValueError, match="media type disagrees"):
        entry(tmp_path, name="b.png", role="poster").model_copy(
            update={"media_type": "video/mp4"})
