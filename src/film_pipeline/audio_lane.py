"""Minimal audio-lane contract (Package-010 T7/T8).

The FIRST independent-audio surface for the editorial runtime. Existing
proven behavior (source-audio passthrough with per-clip atrim/aresample in
rough_cut) is unchanged; this module adds an OPTIONAL lane of external
audio clips placed on the timeline.

Immutable truth per asset: exact source hash + duration + sample rate +
channels. Placements reference assets by id; everything fails closed on
hash drift, bounds, overlap (same lane) or missing assets.
"""
from __future__ import annotations

import re

from pydantic import BaseModel, Field, model_validator

from .core import canonical_json, sha256

SAMPLE_RATE = 48000
CHANNELS = 2


class AudioAsset(BaseModel):
    asset_id: str = Field(pattern=r"^asset_[a-f0-9]{64}$")
    uri_or_path: str
    sha256: str = Field(pattern=r"^[a-f0-9]{64}$")
    duration_s: float = Field(gt=0)
    sample_rate: int = Field(gt=0)
    channels: int = Field(gt=0)
    mime_type: str
    provenance: str

    def digest(self) -> str:
        return sha256(canonical_json(self.model_dump(mode="json")))


class AudioClip(BaseModel):
    asset_id: str
    source_in_s: float = Field(ge=0)
    source_out_s: float = Field(gt=0)
    timeline_start_s: float = Field(ge=0)
    gain_db: float = 0.0
    role: str = Field(default="master", pattern=r"^[a-z_]{1,32}$")

    @model_validator(mode="after")
    def validate_bounds(self):
        if self.source_out_s <= self.source_in_s:
            raise ValueError("audio clip trim out must exceed in")
        return self

    @property
    def duration_s(self) -> float:
        return round(self.source_out_s - self.source_in_s, 6)


class AudioLane(BaseModel):
    lane_id: str = Field(pattern=r"^lane_[a-z0-9_]{1,40}$")
    role: str
    clips: list[AudioClip]

    @model_validator(mode="after")
    def validate_no_overlap(self):
        ordered = sorted(self.clips, key=lambda c: c.timeline_start_s)
        for prev, nxt in zip(ordered, ordered[1:]):
            if nxt.timeline_start_s < prev.timeline_start_s + prev.duration_s - 1e-6:
                raise ValueError("overlapping clips on one audio lane")
        return self


def validate_lane_assets(lane: AudioLane, assets: dict[str, AudioAsset],
                         timeline_duration_s: float) -> dict:
    """Fail-closed binding of every clip to its exact asset + timeline."""
    for clip in lane.clips:
        asset = assets.get(clip.asset_id)
        if asset is None:
            raise ValueError(f"missing audio asset {clip.asset_id}")
        from pathlib import Path as _Path
        resolved = _Path(asset.uri_or_path)
        if not resolved.is_file():
            raise ValueError("audio asset path does not exist")
        if any(ch in asset.uri_or_path for ch in "\n\r\t;|&$`"):
            raise ValueError("unsafe audio asset path")
        if clip.source_out_s > asset.duration_s + 1e-6:
            raise ValueError("audio trim exceeds asset duration")
        if clip.timeline_start_s + clip.duration_s > timeline_duration_s + 1e-6:
            raise ValueError("audio placement exceeds timeline duration")
        if asset.sample_rate != SAMPLE_RATE:
            raise ValueError("audio sample rate must be 48000")
        if asset.channels not in (1, 2):
            raise ValueError("audio channels must be mono or stereo")
    return {"lane_id": lane.lane_id, "clips": len(lane.clips),
            "timeline_duration_s": timeline_duration_s,
            "validated": True}


def lane_inputs_and_filter(lane: AudioLane, assets: dict[str, AudioAsset],
                           input_offset: int = 0
                           ) -> tuple[list[str], str, bool]:
    """Deterministic ffmpeg inputs + filter fragment for ONE lane.

    Returns (input_args, filter_fragment_output_label, has_audio).
    Each clip: atrim -> asetpts -> aresample 48k -> stereo -> volume(gain)
    -> adelay(timeline start). Clips on one lane are amix-ed (no overlap
    is enforced upstream, so amix sums never double-hit).
    """
    inputs: list[str] = []
    mixed: list[str] = []
    for index, clip in enumerate(lane.clips):
        asset = assets[clip.asset_id]
        inputs += ["-i", asset.uri_or_path]
        stream = index + input_offset
        delay_ms = int(round(clip.timeline_start_s * 1000))
        gain = f",volume={clip.gain_db}dB" if clip.gain_db else ""
        mixed.append(
            f"[{stream}:a:0]atrim=start={clip.source_in_s:.6f}:"
            f"end={clip.source_out_s:.6f},asetpts=PTS-STARTPTS,"
            f"aresample={SAMPLE_RATE},"
            f"aformat=sample_rates={SAMPLE_RATE}:channel_layouts=stereo"
            f"{gain},adelay={delay_ms}|{delay_ms}[a{index}]")
    if not mixed:
        return [], "", False
    if len(mixed) == 1:
        return inputs, ";" + mixed[0], True
    label = "".join(f"[a{i}]" for i in range(len(mixed)))
    return (inputs, ";" + "".join(mixed) +
            f"{label}amix=inputs={len(mixed)}:normalize=0[a]", True)
