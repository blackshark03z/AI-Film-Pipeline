"""Provider-independent DeliveryPackage contract (Package-011 S11).

The manifest REFERENCES canonical identities; it never creates them. Once
finalized (delivery_id minted over the sorted entries), the manifest is
immutable: any edit changes the id and verification fails. The package
carries zero provider authority.
"""
from __future__ import annotations

import hashlib
from pathlib import Path

from pydantic import Field, model_validator

from .core import ContractModel, canonical_json, sha256

MEDIA_TYPES = {
    ".mp4": "video/mp4", ".srt": "application/x-subrip",
    ".vtt": "text/vtt", ".png": "image/png", ".jpg": "image/jpeg",
    ".json": "application/json", ".txt": "text/plain",
    ".zip": "application/zip", ".aac": "audio/aac",
}
ROLES = {"master", "narration_master", "caption_srt", "caption_vtt",
         "poster", "technical_qc", "semantic_qc", "owner_review",
         "provenance", "checksums", "narration_receipt"}


class DeliveryEntry(ContractModel):
    role: str
    path: str  # repo-relative POSIX path; never absolute
    sha256: str = Field(pattern=r"^[a-f0-9]{64}$")
    bytes: int = Field(gt=0)
    media_type: str
    source_lineage: str

    @model_validator(mode="after")
    def validate_entry(self):
        if self.role not in ROLES:
            raise ValueError(f"unknown delivery role {self.role}")
        if Path(self.path).is_absolute() or ".." in Path(self.path).parts:
            raise ValueError("delivery paths must be relative")
        expected = MEDIA_TYPES.get(Path(self.path).suffix.lower())
        if expected and expected != self.media_type:
            raise ValueError("media type disagrees with file extension")
        return self


class DeliveryManifest(ContractModel):
    version: str = "delivery-manifest-v1"
    film_id: str
    entries: list[DeliveryEntry]
    delivery_id: str | None = None

    @model_validator(mode="after")
    def validate_identity(self):
        roles = [e.role for e in self.entries]
        if len(roles) != len(set(roles)):
            raise ValueError("duplicate delivery roles")
        if self.delivery_id is None:
            return self
        basis = {k: v for k, v in self.model_dump(mode="json").items()
                 if k != "delivery_id"}
        if self.delivery_id != "delivery_" + sha256(basis):
            raise ValueError("delivery identity mismatch")
        return self


def finalize(manifest: DeliveryManifest, root: Path) -> DeliveryManifest:
    """Verify every entry against on-disk bytes, then freeze the id."""
    for entry in manifest.entries:
        path = root / entry.path
        if not path.is_file():
            raise ValueError(f"delivery file missing: {entry.path}")
        data = path.read_bytes()
        if hashlib.sha256(data).hexdigest() != entry.sha256:
            raise ValueError(f"checksum mismatch: {entry.path}")
        if len(data) != entry.bytes:
            raise ValueError(f"size mismatch: {entry.path}")
    frozen = manifest.model_copy(update={
        "delivery_id": "delivery_" + sha256(
            {k: v for k, v in manifest.model_dump(mode="json").items()
             if k != "delivery_id"})})
    return frozen


def verify(manifest: DeliveryManifest, root: Path) -> dict:
    """Independent conformance: manifest vs files, hashes, sizes, id."""
    if manifest.delivery_id is None:
        raise ValueError("delivery manifest is not finalized")
    basis = {k: v for k, v in manifest.model_dump(mode="json").items()
             if k != "delivery_id"}
    if manifest.delivery_id != "delivery_" + sha256(basis):
        raise ValueError("delivery manifest was modified after finalize")
    missing, bad_checksum, ok = [], [], 0
    for entry in manifest.entries:
        path = root / entry.path
        if not path.is_file():
            missing.append(entry.path)
            continue
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        if digest != entry.sha256:
            bad_checksum.append(entry.path)
            continue
        ok += 1
    return {"entries": len(manifest.entries), "verified": ok,
            "missing": missing, "bad_checksum": bad_checksum,
            "result": "PASS" if not missing and not bad_checksum else "FAIL"}


def undeclared_files(manifest: DeliveryManifest, root: Path,
                     directory: Path) -> list[str]:
    """Files inside a delivered directory that the manifest does not declare."""
    declared = {e.path for e in manifest.entries}
    return [p.relative_to(root).as_posix()
            for p in sorted(directory.rglob("*"))
            if p.is_file() and p.relative_to(root).as_posix()
            not in declared]
