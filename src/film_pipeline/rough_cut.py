"""Bounded local FFmpeg rough-cut renderer; EditManifest stays canonical."""

from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path

from pydantic import Field, model_validator

from .core import ContractModel, canonical_json, sha256
from .editorial import EditManifest, EditorialStore, ResolvedClip, probe_media
from .live_runtime import file_sha256

RENDER_POLICY_VERSION = "rough-cut-v1"


class RoughCutRender(ContractModel):
    render_id: str
    manifest_id: str
    output_path: str
    output_sha256: str
    duration_s: float = Field(gt=0)
    width: int = Field(gt=0)
    height: int = Field(gt=0)
    fps_num: int = Field(gt=0)
    fps_den: int = Field(gt=0)
    video_codec: str
    audio_codec: str | None
    audio_policy: str
    render_method: str
    render_command_fingerprint: str
    ffmpeg_version: str
    source_asset_ids: list[str]
    selected_take_ids: list[str]
    source_hashes: list[str]
    full_decode: bool

    @model_validator(mode="after")
    def validate_identity(self):
        basis = self.model_dump(mode="json", exclude={"render_id", "output_path"})
        if self.render_id != "rough_" + sha256(basis):
            raise ValueError("rough-cut render identity mismatch")
        if not self.full_decode:
            raise ValueError("rough cut needs complete decode proof")
        return self


def ffmpeg_version() -> str:
    result = subprocess.run(["ffmpeg", "-version"], capture_output=True, text=True,
                            check=False, timeout=15)
    if result.returncode or not result.stdout:
        raise RuntimeError("FFmpeg unavailable")
    return result.stdout.splitlines()[0]


def validate_resolved(manifest: EditManifest, sources: tuple[ResolvedClip, ...]) -> None:
    if len(sources) != len(manifest.clips):
        raise ValueError("resolved source count differs from manifest")
    for clip, source in zip(manifest.clips, sources):
        if source.clip != clip or not source.attempt_id or not source.qc_report_id:
            raise ValueError("resolved source identity differs from manifest")
        if not source.path.is_file() or file_sha256(source.path) != source.asset_sha256:
            raise ValueError("resolved source bytes changed")
        if probe_media(source.path) != source.media:
            raise ValueError("resolved source media changed")
    has_audio = [source.media.audio_codec is not None for source in sources]
    if any(has_audio) and not all(has_audio):
        raise ValueError("mixed audio presence is unsupported in V1 rough cut")


def render_method(manifest: EditManifest, sources: tuple[ResolvedClip, ...]) -> str:
    validate_resolved(manifest, sources)
    source = sources[0]
    whole = abs(source.source_in_s) <= 1e-9 and \
        abs(source.source_out_s - source.media.duration_s) <= 1e-6
    return "single_full_clip_remux" if len(sources) == 1 and whole else "normalized_filtergraph"


def _filtergraph(sources: tuple[ResolvedClip, ...]) -> tuple[str, bool]:
    width, height = sources[0].media.width, sources[0].media.height
    fps = f"{sources[0].media.fps_num}/{sources[0].media.fps_den}"
    audio = all(source.media.audio_codec is not None for source in sources)
    parts = []
    concat_inputs = []
    for index, source in enumerate(sources):
        start, end = source.source_in_s, source.source_out_s
        parts.append(
            f"[{index}:v:0]trim=start={start:.6f}:end={end:.6f},setpts=PTS-STARTPTS,"
            f"scale={width}:{height}:force_original_aspect_ratio=decrease,"
            f"pad={width}:{height}:(ow-iw)/2:(oh-ih)/2,"
            f"fps={fps},format=yuv420p[v{index}]")
        concat_inputs.append(f"[v{index}]")
        if audio:
            parts.append(
                f"[{index}:a:0]atrim=start={start:.6f}:end={end:.6f},"
                f"asetpts=PTS-STARTPTS,aresample=48000,"
                f"aformat=sample_rates=48000:channel_layouts=stereo[a{index}]")
            concat_inputs.append(f"[a{index}]")
    parts.append("".join(concat_inputs) +
                 f"concat=n={len(sources)}:v=1:a={1 if audio else 0}[v]" +
                 ("[a]" if audio else ""))
    return ";".join(parts), audio


def _command(sources: tuple[ResolvedClip, ...], staging: Path, method: str) -> list[str]:
    args = ["ffmpeg", "-hide_banner", "-loglevel", "error", "-nostdin", "-y"]
    for source in sources:
        args += ["-i", str(source.path)]
    audio = all(source.media.audio_codec is not None for source in sources)
    if method == "single_full_clip_remux":
        args += ["-map", "0:v:0"]
        if audio:
            args += ["-map", "0:a:0"]
        args += ["-c", "copy"]
    else:
        graph, audio = _filtergraph(sources)
        args += ["-filter_complex", graph, "-map", "[v]"]
        if audio:
            args += ["-map", "[a]"]
        args += ["-c:v", "libx264", "-preset", "veryfast", "-crf", "20", "-pix_fmt", "yuv420p"]
        if audio:
            args += ["-c:a", "aac", "-b:a", "192k", "-ar", "48000", "-ac", "2"]
    if not audio:
        args += ["-an"]
    args += ["-movflags", "+faststart", "-f", "mp4", str(staging)]
    return args


def _full_decode(path: Path) -> bool:
    try:
        result = subprocess.run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-xerror",
                                 "-i", str(path), "-map", "0", "-f", "null", "-"],
                                capture_output=True, text=True, timeout=180, check=False)
    except (OSError, subprocess.TimeoutExpired):
        return False
    return result.returncode == 0


def _render_record(manifest: EditManifest, sources: tuple[ResolvedClip, ...],
                   output: Path, method: str, command_fingerprint: str,
                   version: str) -> RoughCutRender:
    media = probe_media(output)
    _validate_output_media(media, sources)
    if not _full_decode(output):
        raise ValueError("rough-cut full decode failed")
    data = dict(manifest_id=manifest.edit_manifest_id, output_path=str(output.resolve()),
                output_sha256=file_sha256(output), duration_s=media.duration_s,
                width=media.width, height=media.height, fps_num=media.fps_num,
                fps_den=media.fps_den, video_codec=media.video_codec,
                audio_codec=media.audio_codec,
                audio_policy="preserve_all_source_audio" if media.audio_codec else
                "video_only_no_source_audio",
                render_method=method, render_command_fingerprint=command_fingerprint,
                ffmpeg_version=version,
                source_asset_ids=[s.clip.asset_id for s in sources],
                selected_take_ids=[s.clip.selected_take_id for s in sources],
                source_hashes=[s.asset_sha256 for s in sources], full_decode=True)
    render_id = "rough_" + sha256({k: v for k, v in data.items() if k != "output_path"})
    return RoughCutRender(render_id=render_id, **data)


def _validate_output_media(media, sources: tuple[ResolvedClip, ...]) -> None:
    expected_duration = sum(source.duration_s for source in sources)
    tolerance = max(0.1, len(sources) / sources[0].media.fps + 0.03)
    if abs(media.duration_s - expected_duration) > tolerance:
        raise ValueError("rough-cut duration differs from manifest")
    if (media.width, media.height) != (sources[0].media.width, sources[0].media.height):
        raise ValueError("rough-cut resolution differs from plan")
    if (media.fps_num, media.fps_den) != (sources[0].media.fps_num,
                                          sources[0].media.fps_den):
        raise ValueError("rough-cut frame rate differs from plan")
    if media.video_codec != "h264":
        raise ValueError("rough-cut video codec is not H.264")
    audio = all(source.media.audio_codec is not None for source in sources)
    if audio != (media.audio_codec is not None):
        raise ValueError("rough-cut audio policy mismatch")
    if audio and media.audio_codec != "aac":
        raise ValueError("rough-cut audio codec is not AAC")


def _verify_record_output(record: RoughCutRender, sources: tuple[ResolvedClip, ...]) -> None:
    output = Path(record.output_path)
    if not output.is_file() or file_sha256(output) != record.output_sha256:
        raise ValueError("rough-cut output missing or changed")
    media = probe_media(output)
    _validate_output_media(media, sources)
    if ((media.duration_s, media.width, media.height, media.fps_num, media.fps_den,
         media.video_codec, media.audio_codec) !=
            (record.duration_s, record.width, record.height, record.fps_num,
             record.fps_den, record.video_codec, record.audio_codec)):
        raise ValueError("rough-cut metadata mismatch")
    expected_audio_policy = ("preserve_all_source_audio" if media.audio_codec else
                             "video_only_no_source_audio")
    if record.audio_policy != expected_audio_policy or not _full_decode(output):
        raise ValueError("rough-cut audio policy or full decode mismatch")


def _plan_fingerprint(manifest: EditManifest, sources: tuple[ResolvedClip, ...],
                      method: str, version: str) -> str:
    plan = {"policy": RENDER_POLICY_VERSION, "manifest_id": manifest.edit_manifest_id,
            "method": method, "ffmpeg_version": version,
            "source_hashes": [s.asset_sha256 for s in sources],
            "source_intervals": [[s.source_in_s, s.source_out_s] for s in sources],
            "profile": [sources[0].media.width, sources[0].media.height,
                        sources[0].media.fps_num, sources[0].media.fps_den],
            "audio": all(s.media.audio_codec is not None for s in sources)}
    return sha256(plan)


def render_sources(manifest: EditManifest, sources: tuple[ResolvedClip, ...],
                   output: Path) -> RoughCutRender:
    """Render local sources; caller supplies approved-source resolver and stores record."""
    method = render_method(manifest, sources)
    output = output.resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    if output.exists():
        raise ValueError("rough-cut output exists without a readback receipt")
    staging = output.with_name(output.stem + ".partial.mp4")
    if staging.exists():
        raise ValueError("unresolved rough-cut staging file")
    version = ffmpeg_version()
    fingerprint = _plan_fingerprint(manifest, sources, method, version)
    command = _command(sources, staging, method)
    try:
        result = subprocess.run(command, capture_output=True, text=True, timeout=240,
                                check=False)
        if result.returncode or not staging.is_file() or staging.stat().st_size <= 0:
            raise ValueError("FFmpeg rough-cut render failed")
        record = _render_record(manifest, sources, staging, method, fingerprint, version)
        # A no-overwrite promotion makes the local artifact stable once validated.
        os.link(staging, output)
    finally:
        staging.unlink(missing_ok=True)
    return record.model_copy(update={"output_path": str(output)})


def persist_render(store: EditorialStore, render: RoughCutRender) -> None:
    manifest, sources = store.read_manifest(render.manifest_id)
    if ([s.clip.asset_id for s in sources] != render.source_asset_ids or
            [s.clip.selected_take_id for s in sources] != render.selected_take_ids or
            [s.asset_sha256 for s in sources] != render.source_hashes):
        raise ValueError("rough-cut sources differ from manifest")
    if (render.render_method != render_method(manifest, sources) or
            render.render_command_fingerprint != _plan_fingerprint(
                manifest, sources, render.render_method, render.ffmpeg_version)):
        raise ValueError("rough-cut plan differs from manifest")
    _verify_record_output(render, sources)
    store.initialize()
    connection = store.runtime._connect()
    try:
        with connection:
            payload = canonical_json(render.payload())
            connection.execute("INSERT OR IGNORE INTO rough_cut_renders VALUES (?,?,?)",
                               (render.render_id, render.manifest_id, payload))
            row = connection.execute("SELECT manifest_id,payload FROM rough_cut_renders WHERE id=?",
                                     (render.render_id,)).fetchone()
            if row != (render.manifest_id, payload):
                raise ValueError("immutable rough-cut render collision")
            count = connection.execute("SELECT COUNT(*) FROM rough_cut_renders WHERE manifest_id=?",
                                       (render.manifest_id,)).fetchone()[0]
            if count != 1:
                raise ValueError("multiple rough-cut records for one manifest")
    finally:
        connection.close()


def read_render(store: EditorialStore, render_id: str) -> tuple[RoughCutRender, EditManifest,
                                                                 tuple[ResolvedClip, ...]]:
    connection = store.runtime._connect()
    try:
        row = connection.execute("SELECT manifest_id,payload FROM rough_cut_renders WHERE id=?",
                                 (render_id,)).fetchone()
    finally:
        connection.close()
    if row is None:
        raise KeyError(render_id)
    record = RoughCutRender.model_validate(json.loads(row[1]))
    manifest, sources = store.read_manifest(record.manifest_id)
    if (record.render_id != render_id or row[0] != manifest.edit_manifest_id or
            record.source_asset_ids != [s.clip.asset_id for s in sources] or
            record.selected_take_ids != [s.clip.selected_take_id for s in sources] or
            record.source_hashes != [s.asset_sha256 for s in sources] or
            record.render_method != render_method(manifest, sources) or
            record.render_command_fingerprint != _plan_fingerprint(
                manifest, sources, record.render_method, record.ffmpeg_version)):
        raise ValueError("rough-cut provenance mismatch")
    _verify_record_output(record, sources)
    return record, manifest, sources
