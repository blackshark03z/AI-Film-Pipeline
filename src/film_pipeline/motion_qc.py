"""Temporal motion QC boundary (Package-017 Phase 6).

The proven 3-frame semantic sampling stays; this EXTENDS review with
dense deterministic temporal evidence for motion-bearing shots:

- MotionReviewPacket: 8-12 fps deterministic frame extraction over the
  relevant action window (2-4 s), read-only against the source video
  (frames land in a packet directory; the media is never altered).
- Motion observations: 11 named motion dimensions, each PASS / FAIL /
  INCONCLUSIVE, recorded by a reviewer (worker or Owner) with identity
  + provenance. Observations are ADVISORY — the autonomous semantic
  backend is NOT_QUALIFIED, so no motion score can promote a candidate,
  release a take, or grant any provider authority.
"""
from __future__ import annotations

import hashlib
import subprocess
from pathlib import Path
from typing import Literal

from pydantic import Field, model_validator

from .core import ContractModel, canonical_json, sha256

MOTION_PACKET_VERSION = "motion-review-packet-v1"
MOTION_DIMENSIONS = (
    "GAIT_NATURALNESS", "WEIGHT_TRANSFER", "FOOT_SLIDING",
    "JOINT_CONTINUITY", "TORSO_HIP_COORDINATION", "ARM_COUNTERMOTION",
    "CONTACT_PHYSICS", "ACCELERATION_DECELERATION", "REACTION_TIMING",
    "RECOVERY_SETTLING", "PERFORMANCE_STIFFNESS",
)
MOTION_VERDICTS = ("PASS", "FAIL", "INCONCLUSIVE")
ADVISORY_LIMITATION = ("motion observations are advisory; no candidate "
                       "promotion or provider authority from any motion "
                       "score")


class MotionReviewPacket(ContractModel):
    """Sealed dense temporal evidence for one trim window of one asset."""
    schema_version: Literal["motion-review-packet-v1"] = \
        MOTION_PACKET_VERSION
    packet_id: str = Field(min_length=3)
    subject_label: str = Field(min_length=1)
    source_asset_sha256: str = Field(pattern=r"^[a-f0-9]{64}$")
    source_locator: str = Field(min_length=1)  # repo-relative
    trim_start_s: float = Field(ge=0)
    trim_end_s: float = Field(gt=0)
    sampling_fps: int = Field(ge=8, le=12)
    frame_dir: str = Field(min_length=1)  # repo-relative
    frame_files: list[str]
    frame_sha256s: list[str]
    dimensions: list[str]
    created_at: str

    @model_validator(mode="after")
    def validate_packet(self):
        if self.trim_end_s <= self.trim_start_s:
            raise ValueError("motion trim end must exceed start")
        if self.frame_files != self.frame_sha256s and \
                len(self.frame_files) != len(self.frame_sha256s):
            raise ValueError("frame hash count mismatch")
        if sorted(self.dimensions) != sorted(MOTION_DIMENSIONS):
            raise ValueError("motion packet must carry exactly the 11 "
                             "motion dimensions")
        return self

    def digest(self) -> str:
        return sha256(canonical_json(self.model_dump(mode="json")))


def build_motion_packet(*, packet_id: str, subject_label: str,
                        video_path: Path, out_base: Path,
                        trim_start_s: float, trim_end_s: float,
                        fps: int = 10, created_at: str) -> MotionReviewPacket:
    """Deterministic dense-frame extraction (read-only against source)."""
    video_path = Path(video_path)
    if not video_path.is_file():
        raise ValueError(f"motion packet source missing: {video_path}")
    if trim_end_s <= trim_start_s:
        raise ValueError("motion trim end must exceed start")
    source_sha = hashlib.sha256(video_path.read_bytes()).hexdigest()
    try:
        rel = video_path.resolve().relative_to(
            Path.cwd().resolve()).as_posix()
    except ValueError:
        rel = str(video_path)  # synthetic/test sources outside the repo
    frame_dir = Path(out_base) / packet_id
    frame_dir.mkdir(parents=True, exist_ok=True)
    pattern = frame_dir / "frame_%04d.png"
    out = subprocess.run(
        ["ffmpeg", "-y", "-v", "error",
         "-ss", f"{trim_start_s:.6f}", "-to", f"{trim_end_s:.6f}",
         "-i", str(video_path),
         "-vf", f"fps={fps}", "-frame_pts", "0", str(pattern)],
        capture_output=True, text=True)
    if out.returncode != 0:
        raise ValueError(f"frame extraction failed: {out.stderr[:300]}")
    frames = sorted(frame_dir.glob("frame_*.png"))
    if len(frames) < 8:
        raise ValueError("motion packet too sparse (<8 frames); widen the "
                         "trim window or raise the sampling rate")
    record = MotionReviewPacket(
        packet_id=packet_id, subject_label=subject_label,
        source_asset_sha256=source_sha, source_locator=rel,
        trim_start_s=trim_start_s, trim_end_s=trim_end_s,
        sampling_fps=fps,
        frame_dir=(frame_dir.resolve().relative_to(Path.cwd().resolve())
                   .as_posix()
                   if frame_dir.resolve().is_relative_to(
                       Path.cwd().resolve())
                   else str(frame_dir)),
        frame_files=[f.name for f in frames],
        frame_sha256s=[hashlib.sha256(f.read_bytes()).hexdigest()
                       for f in frames],
        dimensions=list(MOTION_DIMENSIONS), created_at=created_at)
    (frame_dir / "packet.json").write_text(
        json_dumps(record.model_dump(mode="json")), encoding="utf-8")
    return record


def json_dumps(payload) -> str:
    import json
    return json.dumps(payload, indent=1, ensure_ascii=False)


def record_motion_observations(packet: MotionReviewPacket, *,
                               observations: dict[str, tuple[str, str]],
                               reviewer_identity: str,
                               reviewed_at: str) -> dict:
    """Seal an advisory observation set against the exact packet digest.

    Fail-closed: every dimension observed exactly once; verdicts limited
    to PASS/FAIL/INCONCLUSIVE. The result carries the ADVISORY
    limitation on its face — it can never promote a candidate."""
    seen = {}
    for dim, (verdict, note) in observations.items():
        if dim not in MOTION_DIMENSIONS:
            raise ValueError(f"unknown motion dimension {dim}")
        if dim in seen:
            raise ValueError(f"duplicate motion dimension {dim}")
        if verdict not in MOTION_VERDICTS:
            raise ValueError(f"unqualified motion verdict {verdict}")
        seen[dim] = {"verdict": verdict, "note": str(note)[:300]}
    missing = [d for d in MOTION_DIMENSIONS if d not in seen]
    if missing:
        raise ValueError(f"missing motion dimensions: {missing}")
    record = {
        "version": "motion-observations-v1",
        "packet_id": packet.packet_id,
        "packet_digest": packet.digest(),
        "subject": packet.subject_label,
        "source_asset_sha256": packet.source_asset_sha256,
        "reviewer_identity": reviewer_identity,
        "reviewed_at": reviewed_at,
        "observations": seen,
        "authority": ADVISORY_LIMITATION,
    }
    return record
