"""Take evidence for handoffs: a previous generation's end state counts as verified only with real evidence.

Verified means ALL of:
1. `<takes>/<gid>.take.json` says `result == "PASSED"` and names an mp4 whose bytes hash to its recorded sha256
   (an empty, missing or replaced file never verifies);
2. a review receipt binds that exact hash to the handoff — either
   - `<takes>/<next_gid>.handoff_qc.json`: a `HandoffReceipt` wrapping a fully PASSed `drama.qc.HandoffQC`
     (reviewer named, every check PASS) for previous -> next, or
   - an entry for that hash in the package's `handoff_attestations.json` (explicit, labelled legacy basis).
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

from pydantic import Field

from film_pipeline.core import ContractModel
from film_pipeline.drama.qc import HandoffQC


class HandoffReceipt(ContractModel):
    """File `<next_gid>.handoff_qc.json`: a human-reviewed HandoffQC bound to the previous take's hash."""

    take_sha256: str
    qc: HandoffQC


class Attestations(ContractModel):
    """File `handoff_attestations.json` in a package: takes accepted on a stated basis, pinned by hash."""

    basis: str = Field(min_length=10)
    attested_by: str = Field(min_length=3)
    takes: dict[str, str]  # generation_id -> sha256 of the mp4


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def passed_take_sha(takes_dir: Path, gid: str) -> str | None:
    """sha256 of the take's mp4 if take.json is PASSED and the bytes match; otherwise None."""
    record_path = takes_dir / f"{gid}.take.json"
    if not record_path.is_file():
        return None
    try:
        record = json.loads(record_path.read_text(encoding="utf-8"))
        # some records omit "file"; the clip is then <gid>.mp4. Only the file name is used (no path escapes)
        clip = takes_dir / Path(str(record.get("file") or f"{gid}.mp4")).name
        if record.get("result") != "PASSED" or not clip.is_file() or clip.stat().st_size == 0:
            return None
        actual = _sha256(clip)
    except (OSError, ValueError, KeyError):
        return None
    return actual if actual == record.get("sha256") else None


def load_attestations(path: Path | None) -> Attestations | None:
    if path is None or not path.is_file():
        return None
    return Attestations.model_validate_json(path.read_text(encoding="utf-8"))


def end_state_verified(takes_dir: Path | None, previous_id: str, next_id: str,
                       attestations: Attestations | None = None) -> bool:
    if takes_dir is None:
        return False
    sha = passed_take_sha(takes_dir, previous_id)
    if sha is None:
        return False
    receipt_path = takes_dir / f"{next_id}.handoff_qc.json"
    if receipt_path.is_file():
        try:
            receipt = HandoffReceipt.model_validate_json(receipt_path.read_text(encoding="utf-8"))
        except ValueError:
            receipt = None
        if (receipt and receipt.take_sha256 == sha and receipt.qc.previous_generation_id == previous_id
                and receipt.qc.next_generation_id == next_id and receipt.qc.verified):
            return True
    return bool(attestations and attestations.takes.get(previous_id) == sha)
