"""Validate a film_package against the vendored JSON schema plus the semantic rules of film_package.md."""
from __future__ import annotations

import json
from fractions import Fraction
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator

from .media import ExportError, probe, sha256_file

SCHEMA_PATH = Path(__file__).resolve().parents[3] / "docs" / "integration" / "film_package.v1.schema.json"
DERIVED_STEMS = {"bed", "bed_ducked", "mix", "mixed", "master"}


def _ranges(rows: list[dict[str, Any]], key: str, duration: int, errors: list[str]) -> None:
    for r in rows:
        if not 0 <= r["in_frame"] < r["out_frame"] <= duration:
            errors.append(f"{key} {r.get(key + '_id', r.get('event_id', r.get('cue_id')))}: range "
                          f"[{r['in_frame']},{r['out_frame']}) is not half-open within [0,{duration}]")


def semantic_errors(pkg: dict[str, Any]) -> list[str]:
    """Rules that JSON Schema cannot express (file ids, ranges, layers, level)."""
    errors: list[str] = []
    ids = [f["id"] for f in pkg["files"]]
    if len(ids) != len(set(ids)):
        errors.append("duplicate file ids")
    paths = {f["id"]: f["path"] for f in pkg["files"]}
    for fid, rel in paths.items():
        parts = Path(rel.replace("\\", "/")).parts
        if Path(rel).is_absolute() or rel.startswith(("/", "\\")) or ".." in parts or (len(rel) > 1 and rel[1] == ":"):
            errors.append(f"file {fid}: path {rel!r} must be relative and stay inside source.root")
    refs: list[tuple[str, str]] = [("picture", pkg["picture"]["file_id"]),
                                   ("audio.production_track", pkg["audio"]["production_track"]["file_id"])]
    if "lock" in pkg:
        refs.append(("lock", pkg["lock"]["file_id"]))
    refs += [(f"layer {x['id']}", x["file_id"]) for x in pkg["audio"].get("layers", [])]
    for a in pkg.get("assets", []):
        refs.append((f"asset {a['id']}", a["file_id"]))
        if "rights_ref" in a:
            refs.append((f"asset {a['id']} rights_ref", a["rights_ref"]))
    refs += [(f"references.{k}", v) for k, v in pkg.get("references", {}).items()]
    errors += [f"{where}: file id {fid!r} is not in files[]" for where, fid in refs if fid not in paths]

    duration = pkg["clock"]["duration_frames"]
    timeline = pkg.get("timeline", [])
    _ranges(timeline, "event", duration, errors)
    cursor = 0
    for ev in sorted(timeline, key=lambda r: r["in_frame"]):
        if ev["in_frame"] < cursor:
            errors.append(f"event {ev['event_id']} overlaps the previous event")
        elif ev["in_frame"] > cursor:
            errors.append(f"timeline gap [{cursor},{ev['in_frame']}) before {ev['event_id']} is not declared as BLACK")
        cursor = max(cursor, ev["out_frame"])
    if timeline and cursor < duration:
        errors.append(f"timeline ends at {cursor}, picture is {duration} frames (gap not declared as BLACK)")
    if len({e["event_id"] for e in timeline}) != len(timeline):
        errors.append("duplicate event ids in timeline")
    by_event = {e["event_id"]: e for e in timeline}
    scene_ids = {s["scene_id"] for s in pkg.get("scenes", [])}
    for ev in timeline:
        if scene_ids and ev.get("scene_id") and ev["scene_id"] not in scene_ids:
            errors.append(f"event {ev['event_id']}: scene {ev['scene_id']} is not in scenes[]")
    _ranges(pkg.get("dialogue", []), "cue", duration, errors)
    for cue in pkg.get("dialogue", []):
        ev = by_event.get(cue.get("event_id", ""))
        if cue.get("event_id") and not ev:
            errors.append(f"cue {cue['cue_id']}: event {cue['event_id']} is not on the timeline")
        elif ev and not (ev["in_frame"] <= cue["in_frame"] and cue["out_frame"] <= ev["out_frame"]):
            errors.append(f"cue {cue['cue_id']} leaves its event {ev['event_id']}")

    layers = pkg["audio"].get("layers", [])
    if len({x["id"] for x in layers}) != len(layers):
        errors.append("duplicate layer ids")
    track_path = paths.get(pkg["audio"]["production_track"]["file_id"])
    for layer in layers:
        path = paths.get(layer["file_id"], "")
        if Path(path).stem.lower() in DERIVED_STEMS or Path(path).name.lower().startswith("bed"):
            errors.append(f"layer {layer['id']}: {path} is a derived bed/mix and must never be a layer")
        if path == track_path:
            errors.append(f"layer {layer['id']} is the production track")
    level = pkg["audio"]["level"]
    has_l1 = bool(timeline) and bool(pkg.get("dialogue"))
    if level in ("L1", "L2") and not has_l1:
        errors.append(f"level {level} needs a timeline and dialogue cues")
    if level == "L2" and not layers:
        errors.append("level L2 needs at least one audio layer")
    return errors


def media_errors(pkg: dict[str, Any]) -> list[str]:
    """Re-hash every file and compare picture/audio durations with the clock (what the engine does on ingest)."""
    errors: list[str] = []
    root = Path(pkg["source"]["root"])
    for f in pkg["files"]:
        path = root / f["path"]
        if not path.is_file():
            errors.append(f"file {f['id']}: {f['path']} not found")
        elif sha256_file(path) != f["sha256"] or ("bytes" in f and path.stat().st_size != f["bytes"]):
            errors.append(f"file {f['id']}: sha256/size differs from the file on disk")
    if errors:
        return errors
    paths = {f["id"]: root / f["path"] for f in pkg["files"]}
    clock = pkg["clock"]
    fps = Fraction(clock["fps_num"], clock["fps_den"])
    video = probe(paths[pkg["picture"]["file_id"]])["video"] or {}
    frames = video.get("nb_frames") or round(video.get("duration_s", 0) * float(fps))
    if abs(frames - clock["duration_frames"]) > 1:
        errors.append(f"picture decodes to {frames} frames, clock says {clock['duration_frames']}")
    audio_ids = [pkg["audio"]["production_track"]["file_id"]] + [x["file_id"] for x in pkg["audio"].get("layers", [])]
    for fid in audio_ids:
        seconds = (probe(paths[fid])["audio"] or {}).get("duration_s", 0)
        if seconds * float(fps) > clock["duration_frames"] + 1:
            errors.append(f"audio {fid} is longer than the picture by more than 1 frame")
    return errors


def validate_package(pkg: dict[str, Any], *, schema_path: Path | None = None, check_media: bool = True) -> None:
    """Raise ExportError listing every problem; return None when the package is valid."""
    schema = json.loads((schema_path or SCHEMA_PATH).read_text(encoding="utf-8"))
    errors = [f"schema: {'/'.join(map(str, e.absolute_path)) or '<root>'}: {e.message}"
              for e in sorted(Draft202012Validator(schema).iter_errors(pkg), key=lambda e: list(map(str, e.absolute_path)))]
    if not errors:
        errors = semantic_errors(pkg)
    if not errors and check_media:
        errors = media_errors(pkg)
    if errors:
        raise ExportError("film_package is invalid:\n  - " + "\n  - ".join(errors))
