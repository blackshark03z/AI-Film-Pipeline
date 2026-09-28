"""Thin Film producer export and producer-side package checks, not AutoEdit ingest."""

from __future__ import annotations

import argparse
import json
import os
import tempfile
from functools import lru_cache
from pathlib import Path, PurePosixPath

from jsonschema import Draft202012Validator

from .core import canonical_json, sha256
from .editorial import EditManifest, EditorialStore, ResolvedClip
from .live_runtime import Asset, file_sha256
from .store import SQLiteStore

CONTRACT_VERSION = "0.1.0"
SCHEMA_PATH = Path(__file__).resolve().parents[2] / "docs/integration/edit_job_input_v0.schema.json"


@lru_cache(maxsize=1)
def _validator() -> Draft202012Validator:
    schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
    Draft202012Validator.check_schema(schema)
    return Draft202012Validator(schema)


def validate_envelope(payload: dict) -> None:
    """Check exported structural data; optional Film objects are never required."""
    _validator().validate(payload)
    canonical_json(payload)  # Reject NaN/infinite values even inside opaque enrichment.
    ids = [media["media_id"] for media in payload["media"]]
    if len(ids) != len(set(ids)):
        raise ValueError("duplicate media identity")
    for media in payload["media"]:
        path = media["locator"]["path"]
        if ("\\" in path or ":" in path or path.startswith("/") or
                any(part in {"", ".", ".."} for part in path.split("/"))):
            raise ValueError("media locator must be portable and relative")
    constraints = payload.get("optional_constraints", []) + payload.get("frozen_constraints", [])
    constraint_ids = [item["constraint_id"] for item in constraints]
    if len(constraint_ids) != len(set(constraint_ids)):
        raise ValueError("duplicate constraint identity")
    if any(set(item.get("media_ids", [])) - set(ids) for item in constraints):
        raise ValueError("constraint references unknown media")


def package_identity(payload: dict) -> str:
    validate_envelope(payload)
    return "editpkg_" + sha256(payload)


def verify_media(payload: dict, *, package_root: Path, roots: dict[str, Path]) -> None:
    """Producer evidence check; no codec ingest or editorial execution is performed."""
    validate_envelope(payload)
    for media in payload["media"]:
        locator = media["locator"]
        if locator["kind"] == "package_relative":
            base = package_root.resolve()
        else:
            if locator["root_id"] not in roots:
                raise ValueError("media root binding unavailable")
            base = roots[locator["root_id"]].resolve()
        source = base.joinpath(*PurePosixPath(locator["path"]).parts).resolve()
        if not source.is_relative_to(base):
            raise ValueError("media locator escapes bound root")
        if not source.is_file() or source.stat().st_size == 0:
            raise ValueError("referenced media missing or empty")
        if "sha256" in media and file_sha256(source) != media["sha256"]:
            raise ValueError("media SHA-256 mismatch")


def _json_bytes(payload: dict) -> bytes:
    return (canonical_json(payload) + "\n").encode("utf-8")


def _checksums(payload: dict, contents: bytes) -> dict:
    import hashlib

    return {"package_id": package_identity(payload),
            "edit_job_sha256": hashlib.sha256(contents).hexdigest(),
            "media_sha256": {media["media_id"]: media["sha256"]
                             for media in payload["media"] if "sha256" in media}}


def _load_package_json(contents: bytes) -> dict:
    def unique_object(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                raise ValueError("duplicate JSON key in producer package")
            result[key] = value
        return result

    def reject_constant(_):
        raise ValueError("non-finite JSON number in producer package")

    return json.loads(contents, object_pairs_hook=unique_object, parse_constant=reject_constant)


def validate_producer_package(directory: Path, *, roots: dict[str, Path]) -> dict:
    contents = (directory / "edit_job.json").read_bytes()
    payload = _load_package_json(contents)
    validate_envelope(payload)
    recorded = _load_package_json((directory / "checksums.json").read_bytes())
    if recorded != _checksums(payload, contents):
        raise ValueError("package checksum or identity mismatch")
    verify_media(payload, package_root=directory, roots=roots)
    return payload


def write_referenced_package(payload: dict, destination: Path, *, roots: dict[str, Path]) -> str:
    """No-overwrite filesystem export. This Film adapter references existing media."""
    if any(media["storage"] != "referenced" for media in payload["media"]):
        raise ValueError("Film package writer only exports referenced media")
    verify_media(payload, package_root=destination, roots=roots)
    contents = _json_bytes(payload)
    if destination.exists():
        previous = validate_producer_package(destination, roots=roots)
        if previous != payload:
            raise ValueError("existing package differs; refusing overwrite")
        return package_identity(previous)
    destination.parent.mkdir(parents=True, exist_ok=True)
    staging = Path(tempfile.mkdtemp(prefix=".editjob-", dir=destination.parent))
    try:
        (staging / "edit_job.json").write_bytes(contents)
        (staging / "checksums.json").write_bytes(_json_bytes(_checksums(payload, contents)))
        validate_producer_package(staging, roots=roots)
        os.rename(staging, destination)
    finally:
        if staging.exists():
            # Only the two files created above are removed; never recursive cleanup.
            for name in ("edit_job.json", "checksums.json"):
                (staging / name).unlink(missing_ok=True)
            staging.rmdir()
    validate_producer_package(destination, roots=roots)
    return package_identity(payload)


def build_film_input(manifest: EditManifest, sources: tuple[ResolvedClip, ...],
                     shots: dict[str, dict], locators: dict[str, dict]) -> dict:
    """Pure mapping of already verified Film state; runtime paths are not read/exported."""
    media, provenance, semantics = {}, {}, {}
    for source in sources:
        clip = source.clip
        media_id = "media_" + source.asset_sha256
        entry = {"media_id": media_id, "media_type": "video", "storage": "referenced",
                 "locator": locators[clip.asset_id], "duration_s": source.media.duration_s,
                 "sha256": source.asset_sha256}
        if media_id in media and media[media_id] != entry:
            raise ValueError("same media bytes have conflicting locators")
        media[media_id] = entry
        provenance.setdefault(media_id, []).append({"asset_id": clip.asset_id,
            "selected_take_id": clip.selected_take_id, "qc_report_id": source.qc_report_id,
            "qc_decision": "pass", "generation_attempt_id": source.attempt_id,
            "shot_id": clip.shot_id})
        shot = shots[clip.shot_id]
        semantics.setdefault(media_id, []).append({key: shot[key] for key in
            ("shot_id", "scene_id", "dramatic_purpose", "camera", "continuity") if key in shot})
    payload = {"contract_version": CONTRACT_VERSION, "media": list(media.values()),
        "user_intent": {"request": "Use the Film assembly as a suggested editorial starting point."},
        "optional_timeline_hint": {"authority": "suggestion", "source_format": "EditManifestV1",
                                   "data": manifest.model_dump(mode="json")},
        "optional_provenance": {"film": {"producer": "AI-Film-Pipeline",
            "project_id": manifest.project_id, "edit_manifest_id": manifest.edit_manifest_id,
            "by_media_id": provenance}},
        "optional_semantic_metadata": {"film": {"by_media_id": semantics}},
        "frozen_constraints": []}
    payload["job_id"] = "editjob_" + sha256(payload)
    validate_envelope(payload)
    return payload


def export_film_package(db_path: Path, *, manifest_id: str, media_root: Path,
                        destination: Path, root_id: str = "film_workspace") -> dict:
    store = EditorialStore(SQLiteStore(db_path))
    manifest, sources = store.read_manifest(manifest_id)
    shots, locators = {}, {}
    base = media_root.resolve()
    for source in sources:
        path = source.path.resolve()
        if not path.is_relative_to(base):
            raise ValueError("Film source outside explicit media root")
        locators[source.clip.asset_id] = {"kind": "root_relative", "root_id": root_id,
                                        "path": path.relative_to(base).as_posix()}
        connection = store.runtime._connect()
        try:
            row = connection.execute("SELECT payload FROM assets WHERE id=?",
                                     (source.clip.asset_id,)).fetchone()
        finally:
            connection.close()
        asset = Asset.model_validate(json.loads(row[0]))
        shot, _, _, _, _, _ = store.runtime.read_runtime_lineage(source.attempt_id,
                                                                 asset.provider_job_id)
        shots[shot.shot_id] = shot.model_dump(mode="json")
    payload = build_film_input(manifest, sources, shots, locators)
    identity = write_referenced_package(payload, destination, roots={root_id: base})
    return {"job_id": payload["job_id"], "package_id": identity,
            "manifest_id": manifest.edit_manifest_id, "media_count": len(payload["media"]),
            "media_storage": "referenced", "fresh_package_readback": True}


def main() -> None:
    parser = argparse.ArgumentParser(description="Export a verified Film manifest for AutoEdit research")
    parser.add_argument("--db", required=True, type=Path)
    parser.add_argument("--manifest-id", required=True)
    parser.add_argument("--media-root", required=True, type=Path)
    parser.add_argument("--destination", required=True, type=Path)
    args = parser.parse_args()
    print(json.dumps(export_film_package(args.db, manifest_id=args.manifest_id,
        media_root=args.media_root, destination=args.destination), indent=2))


if __name__ == "__main__":
    main()
