"""Editorial source-range truth (FLOW-PRODUCTION-SCALE-007, Q5 / L5).

The smallest generic editorial-range contract above SelectedTake:

    SelectedTake (immutable, approved Asset) + EditorialRange
    = which exact time interval of that exact asset the edit uses.

Invariants (frozen package):
- 0 <= source_in_s < source_out_s <= exact probed asset duration;
- selected_duration_s == source_out_s - source_in_s (no implicit retiming);
- the range binds take id, Asset id + SHA-256, ShotSpec id, and the exact
  media-probe basis the range was cut against (duration + frame rate);
- source media is never destructively trimmed — the range is a pure
  projection; revalidation always re-reads immutable bytes;
- deterministic identity: editorial_range_id is a SHA-256 over the full
  canonical payload, so equal ranges collide and any field drift mints a
  different identity;
- provenance is explicit: PROVISIONAL_AUTONOMOUS_EDITORIAL_RANGE is NOT
  Owner approval;
- no FFmpeg-specific semantics here: the probe basis is plain numbers
  (seconds + rational frame rate) carried from editorial.probe_media.
"""
from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Literal

from pydantic import Field, model_validator

from .core import ContractModel, sha256
from .editorial import probe_media
from .live_runtime import file_sha256

EDITORIAL_RANGE_VERSION = "editorial-range-v1"
DURATION_DRIFT_TOLERANCE_S = 1e-3
PROVISIONAL = "PROVISIONAL_AUTONOMOUS_EDITORIAL_RANGE"


class ProbeBasis(ContractModel):
    """The exact probe a range was cut against (immutable numbers)."""
    duration_s: float = Field(gt=0)
    fps_num: int = Field(gt=0)
    fps_den: int = Field(gt=0)

    @property
    def fps(self) -> float:
        return self.fps_num / self.fps_den


class EditorialRange(ContractModel):
    version: Literal["editorial-range-v1"]
    editorial_range_id: str
    selected_take_id: str = Field(min_length=1)
    shot_id: str = Field(min_length=1)
    asset_id: str = Field(min_length=1)
    asset_sha256: str = Field(min_length=1)
    source_in_s: float = Field(ge=0)
    source_out_s: float = Field(gt=0)
    selected_duration_s: float = Field(gt=0)
    probe_basis: ProbeBasis
    provenance: Literal["PROVISIONAL_AUTONOMOUS_EDITORIAL_RANGE"]
    note: str | None = None

    @model_validator(mode="after")
    def validate_range(self):
        for value in (self.source_in_s, self.source_out_s,
                      self.selected_duration_s):
            if not math.isfinite(value):
                raise ValueError("non-finite editorial time")
        if self.source_in_s < 0:
            raise ValueError("source_in_s must be >= 0")
        if self.source_out_s <= self.source_in_s:
            raise ValueError("source_out_s must be greater than source_in_s")
        if self.source_out_s > self.probe_basis.duration_s + \
                DURATION_DRIFT_TOLERANCE_S:
            raise ValueError("source_out_s exceeds the probed asset duration")
        if abs(self.selected_duration_s -
               (self.source_out_s - self.source_in_s)) > \
                DURATION_DRIFT_TOLERANCE_S:
            raise ValueError(
                "selected_duration_s must equal source_out_s - source_in_s")
        canonical = {k: v for k, v in self.model_dump(mode="json").items()
                     if k != "editorial_range_id"}
        if self.editorial_range_id != "er_" + sha256(canonical):
            raise ValueError("EditorialRange identity mismatch")
        return self


def make_editorial_range(*, selected_take_id: str, shot_id: str,
                         asset_id: str, asset_sha256: str,
                         source_in_s: float, source_out_s: float,
                         probe: ProbeBasis,
                         note: str | None = None) -> EditorialRange:
    """Mint the deterministic range (identity derived from full payload)."""
    payload = {"version": EDITORIAL_RANGE_VERSION,
               "selected_take_id": selected_take_id, "shot_id": shot_id,
               "asset_id": asset_id, "asset_sha256": asset_sha256,
               "source_in_s": float(source_in_s),
               "source_out_s": float(source_out_s),
               "selected_duration_s": round(
                   float(source_out_s) - float(source_in_s), 9),
               "probe_basis": probe.model_dump(mode="json"),
               "provenance": PROVISIONAL, "note": note}
    return EditorialRange(
        editorial_range_id="er_" + sha256(
            {k: v for k, v in payload.items()}),
        **payload)


def range_from_probe(path: Path, *, selected_take_id: str, shot_id: str,
                     asset_id: str, asset_sha256: str, source_in_s: float,
                     source_out_s: float,
                     note: str | None = None) -> EditorialRange:
    """Probe the immutable source once and cut the range against it."""
    media = probe_media(path)
    return make_editorial_range(
        selected_take_id=selected_take_id, shot_id=shot_id,
        asset_id=asset_id, asset_sha256=asset_sha256,
        source_in_s=source_in_s, source_out_s=source_out_s,
        probe=ProbeBasis(duration_s=media.duration_s, fps_num=media.fps_num,
                         fps_den=media.fps_den),
        note=note)


def revalidate(rng: EditorialRange, path: Path) -> dict:
    """Fail-closed revalidation against the immutable source bytes.

    Restarts and long gaps may sit between cutting a range and consuming it:
    the file must still be the same exact asset (SHA-256), its duration must
    not have drifted beyond a frame, and the range must still fit.
    """
    if not path.is_file():
        raise ValueError("source media missing")
    if file_sha256(path) != rng.asset_sha256:
        raise ValueError("source Asset SHA-256 mismatch")
    media = probe_media(path)
    if abs(media.duration_s - rng.probe_basis.duration_s) > \
            DURATION_DRIFT_TOLERANCE_S:
        raise ValueError(
            "asset duration drifted since the range was cut")
    if rng.source_out_s > media.duration_s + DURATION_DRIFT_TOLERANCE_S:
        raise ValueError("range no longer fits the asset duration")
    return {"asset_sha256": rng.asset_sha256, "duration_s": media.duration_s,
            "selected_duration_s": rng.selected_duration_s,
            "fps": media.fps}


def write_range(rng: EditorialRange, path: Path) -> None:
    """Durable one-way JSON write (write-once; content conflicts refuse)."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    encoded = json.dumps(rng.model_dump(mode="json"), indent=2,
                         sort_keys=True, ensure_ascii=False) + "\n"
    if path.exists():
        if path.read_text(encoding="utf-8") != encoded:
            raise ValueError(f"EVIDENCE_CONFLICT: {path.name}")
        return
    path.write_text(encoded, encoding="utf-8")


def read_range(path: Path) -> EditorialRange:
    """Reload after restart; identity re-derives inside the model."""
    return EditorialRange.model_validate(json.loads(
        Path(path).read_text(encoding="utf-8")))


def to_edit_clip_fields(rng: EditorialRange) -> dict:
    """Bridge into the existing EditManifest clip vocabulary (no retiming,
    no new assembly semantics — the AutoEdit boundary stays as-is)."""
    return {"source_in_s": rng.source_in_s,
            "source_out_s": rng.source_out_s,
            "target_duration_s": rng.selected_duration_s}
