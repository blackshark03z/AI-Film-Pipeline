"""Canonical EditManifestV1 intent and exact approved-source resolution."""

from __future__ import annotations

import json
import math
import subprocess
from dataclasses import dataclass
from fractions import Fraction
from pathlib import Path

from pydantic import Field, model_validator

from .core import ContractModel, sha256, validate_contract
from .live_runtime import Asset, file_sha256
from .qc import QCStore, SelectedTake
from .store import SQLiteStore

MANIFEST_VERSION = "editmanifest-v1"
TARGET_DURATION_TOLERANCE_S = 0.05


class EditClip(ContractModel):
    order: int = Field(ge=1)
    shot_id: str = Field(min_length=1)
    selected_take_id: str = Field(min_length=1)
    asset_id: str = Field(min_length=1)
    source_in_s: float = Field(default=0, ge=0)
    source_out_s: float | None = None
    target_duration_s: float | None = None
    notes: str | None = None

    @model_validator(mode="after")
    def validate_times(self):
        for value in (self.source_in_s, self.source_out_s, self.target_duration_s):
            if value is not None and not math.isfinite(value):
                raise ValueError("non-finite editorial time")
        if self.source_out_s is not None and self.source_out_s <= self.source_in_s:
            raise ValueError("source_out_s must be greater than source_in_s")
        if self.target_duration_s is not None and self.target_duration_s <= 0:
            raise ValueError("target_duration_s must be positive")
        return self


class EditManifest(ContractModel):
    edit_manifest_id: str
    project_id: str = Field(min_length=1)
    clips: list[EditClip] = Field(min_length=1)

    @model_validator(mode="after")
    def validate_identity_order(self):
        if [clip.order for clip in self.clips] != list(range(1, len(self.clips) + 1)):
            raise ValueError("clip order must be supplied as contiguous 1..N")
        basis = {"version": MANIFEST_VERSION, "project_id": self.project_id,
                 "clips": [clip.model_dump(mode="json") for clip in self.clips]}
        if self.edit_manifest_id != "edit_" + sha256(basis):
            raise ValueError("EditManifest identity mismatch")
        validate_contract("edit_manifest", self.model_dump(mode="json"))
        return self


def make_edit_manifest(project_id: str, clips: list[EditClip]) -> EditManifest:
    if not project_id or not clips:
        raise ValueError("nonempty project and clips required")
    basis = {"version": MANIFEST_VERSION, "project_id": project_id,
             "clips": [clip.model_dump(mode="json") for clip in clips]}
    return EditManifest(edit_manifest_id="edit_" + sha256(basis), project_id=project_id,
                        clips=clips)


@dataclass(frozen=True)
class MediaProbe:
    duration_s: float
    width: int
    height: int
    fps_num: int
    fps_den: int
    video_codec: str
    audio_codec: str | None
    audio_duration_s: float | None

    @property
    def fps(self) -> float:
        return self.fps_num / self.fps_den


def probe_media(path: Path) -> MediaProbe:
    if not path.is_file() or path.stat().st_size <= 0:
        raise ValueError("source media missing or empty")
    try:
        result = subprocess.run(
            ["ffprobe", "-v", "error", "-show_entries",
             "format=duration:stream=codec_type,codec_name,width,height,avg_frame_rate,duration",
             "-of", "json", str(path)], capture_output=True, text=True,
            timeout=30, check=False)
        if result.returncode:
            raise ValueError("ffprobe rejected media")
        data = json.loads(result.stdout)
        duration = float(data["format"]["duration"])
        video = next(s for s in data["streams"] if s["codec_type"] == "video")
        audio = next((s for s in data["streams"] if s["codec_type"] == "audio"), None)
        fps = Fraction(video["avg_frame_rate"])
        width, height = int(video["width"]), int(video["height"])
        audio_duration = float(audio["duration"]) if audio and audio.get("duration") else None
    except (OSError, subprocess.TimeoutExpired, KeyError, StopIteration, TypeError,
            ValueError, ZeroDivisionError, json.JSONDecodeError) as exc:
        raise ValueError("invalid media metadata") from exc
    if not math.isfinite(duration) or duration <= 0 or width <= 0 or height <= 0 or fps <= 0:
        raise ValueError("invalid media dimensions, frame rate or duration")
    return MediaProbe(duration, width, height, fps.numerator, fps.denominator,
                      video["codec_name"], audio["codec_name"] if audio else None,
                      audio_duration)


@dataclass(frozen=True)
class ResolvedClip:
    clip: EditClip
    path: Path
    asset_sha256: str
    attempt_id: str
    qc_report_id: str
    media: MediaProbe
    source_in_s: float
    source_out_s: float

    @property
    def duration_s(self) -> float:
        return self.source_out_s - self.source_in_s


def validate_source(clip: EditClip, *, path: Path, expected_sha256: str,
                    attempt_id: str, qc_report_id: str) -> ResolvedClip:
    if not path.is_file():
        raise ValueError("source media missing")
    if file_sha256(path) != expected_sha256:
        raise ValueError("source Asset SHA-256 mismatch")
    media = probe_media(path)
    in_s = float(clip.source_in_s)
    out_s = media.duration_s if clip.source_out_s is None else float(clip.source_out_s)
    if in_s >= media.duration_s or out_s > media.duration_s + 1e-6:
        raise ValueError("source trim exceeds actual media bounds")
    if out_s <= in_s:
        raise ValueError("empty source trim")
    trimmed = out_s - in_s
    if (clip.target_duration_s is not None and
            abs(clip.target_duration_s - trimmed) > TARGET_DURATION_TOLERANCE_S):
        raise ValueError("target duration requests implicit retiming")
    if media.audio_codec and media.audio_duration_s is not None and \
            out_s > media.audio_duration_s + TARGET_DURATION_TOLERANCE_S:
        raise ValueError("source audio does not cover trim")
    return ResolvedClip(clip, path, expected_sha256, attempt_id, qc_report_id,
                        media, in_s, out_s)


class EditorialStore:
    """Append-only manifest/render records in the established runtime SQLite DB."""

    def __init__(self, runtime: SQLiteStore):
        self.runtime = runtime

    def initialize(self) -> None:
        self.runtime.initialize()
        connection = self.runtime._connect()
        try:
            connection.executescript("""
                CREATE TABLE IF NOT EXISTS edit_manifests (
                    id TEXT PRIMARY KEY, project_id TEXT NOT NULL, payload TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS edit_manifest_clips (
                    manifest_id TEXT NOT NULL REFERENCES edit_manifests(id),
                    clip_order INTEGER NOT NULL,
                    selected_take_id TEXT NOT NULL REFERENCES selected_takes(id),
                    asset_id TEXT NOT NULL REFERENCES assets(id),
                    payload TEXT NOT NULL,
                    PRIMARY KEY (manifest_id, clip_order));
                CREATE TABLE IF NOT EXISTS rough_cut_renders (
                    id TEXT PRIMARY KEY, manifest_id TEXT NOT NULL REFERENCES edit_manifests(id),
                    payload TEXT NOT NULL);
            """)
        finally:
            connection.close()

    def _resolve_persisted_clip(self, clip: EditClip) -> ResolvedClip:
        connection = self.runtime._connect()
        try:
            row = connection.execute("SELECT asset_id, report_id, payload FROM selected_takes WHERE id=?",
                                     (clip.selected_take_id,)).fetchone()
            if row is None:
                raise ValueError("selected take missing or unapproved")
            if row[0] != clip.asset_id:
                raise ValueError("clip Asset differs from SelectedTake")
            asset_row = connection.execute("SELECT payload FROM assets WHERE id=?", (clip.asset_id,)).fetchone()
            if asset_row is None:
                raise ValueError("selected Asset missing")
        finally:
            connection.close()
        take = SelectedTake.model_validate(json.loads(row[2]))
        asset = Asset.model_validate(json.loads(asset_row[0]))
        report, readback_take = QCStore(self.runtime).read(asset, row[1])
        if (readback_take != take or report.report["decision"] != "pass"
                or take.selected_take_id != clip.selected_take_id
                or take.shot_id != clip.shot_id or take.asset_id != clip.asset_id
                or take.generation_attempt_id != asset.source_attempt_id):
            raise ValueError("clip does not resolve to an approved exact Asset")
        shot, _, _, _, _, assets = self.runtime.read_runtime_lineage(asset.source_attempt_id,
                                                                     asset.provider_job_id)
        if shot.shot_id != clip.shot_id or asset not in assets:
            raise ValueError("clip ShotSpec or Asset lineage mismatch")
        return validate_source(clip, path=Path(asset.uri_or_path), expected_sha256=asset.sha256,
                               attempt_id=asset.source_attempt_id,
                               qc_report_id=take.qc_report_id)

    def resolve_manifest(self, manifest: EditManifest) -> tuple[ResolvedClip, ...]:
        return tuple(self._resolve_persisted_clip(clip) for clip in manifest.clips)

    def save_manifest(self, manifest: EditManifest) -> tuple[ResolvedClip, ...]:
        sources = self.resolve_manifest(manifest)
        self.initialize()
        connection = self.runtime._connect()
        try:
            with connection:
                payload = json.dumps(manifest.model_dump(mode="json"), sort_keys=True,
                                     separators=(",", ":"), ensure_ascii=False)
                connection.execute("INSERT OR IGNORE INTO edit_manifests VALUES (?,?,?)",
                                   (manifest.edit_manifest_id, manifest.project_id, payload))
                stored = connection.execute("SELECT project_id,payload FROM edit_manifests WHERE id=?",
                                            (manifest.edit_manifest_id,)).fetchone()
                if stored != (manifest.project_id, payload):
                    raise ValueError("immutable EditManifest collision")
                for clip in manifest.clips:
                    clip_payload = json.dumps(clip.model_dump(mode="json"), sort_keys=True,
                                              separators=(",", ":"), ensure_ascii=False)
                    connection.execute("INSERT OR IGNORE INTO edit_manifest_clips VALUES (?,?,?,?,?)",
                                       (manifest.edit_manifest_id, clip.order, clip.selected_take_id,
                                        clip.asset_id, clip_payload))
                    old = connection.execute("SELECT selected_take_id,asset_id,payload FROM edit_manifest_clips "
                                             "WHERE manifest_id=? AND clip_order=?",
                                             (manifest.edit_manifest_id, clip.order)).fetchone()
                    if old != (clip.selected_take_id, clip.asset_id, clip_payload):
                        raise ValueError("immutable EditManifest clip collision")
        finally:
            connection.close()
        return sources

    def read_manifest(self, manifest_id: str) -> tuple[EditManifest, tuple[ResolvedClip, ...]]:
        connection = self.runtime._connect()
        try:
            row = connection.execute("SELECT project_id,payload FROM edit_manifests WHERE id=?",
                                     (manifest_id,)).fetchone()
            if row is None:
                raise KeyError(manifest_id)
            clip_rows = connection.execute("SELECT clip_order,selected_take_id,asset_id,payload "
                                           "FROM edit_manifest_clips WHERE manifest_id=? ORDER BY clip_order",
                                           (manifest_id,)).fetchall()
        finally:
            connection.close()
        manifest = EditManifest.model_validate(json.loads(row[1]))
        if manifest.edit_manifest_id != manifest_id or manifest.project_id != row[0] or \
                len(clip_rows) != len(manifest.clips):
            raise ValueError("EditManifest readback mismatch")
        for clip, stored in zip(manifest.clips, clip_rows):
            if stored[:3] != (clip.order, clip.selected_take_id, clip.asset_id) or \
                    json.loads(stored[3]) != clip.model_dump(mode="json"):
                raise ValueError("EditManifest clip readback mismatch")
        return manifest, self.resolve_manifest(manifest)
