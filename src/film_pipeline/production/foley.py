"""Offline procedural Foley & SFX synthesis (`assets/sfx_catalog.json` + `GENERATED_OFFLINE` sound rights).

Closes 168-matrix category 110 (Foley) and 111 (Sound effects) locally using deterministic FFmpeg `lavfi`
synthesis and registers cleared `GENERATED_OFFLINE` hashes in ``audio/assets.json`` via ``sound_rights``.
"""
from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace
from typing import Any

from film_pipeline.production.ffjoin import media_timeout, run_ffmpeg
from film_pipeline.production.mix import audio_dir, sha256_file, slug
from film_pipeline.production import sound_rights as sr_mod

DEFAULT_CATALOG = Path(__file__).resolve().parents[3] / "assets" / "sfx_catalog.json"


def load_catalog(catalog_path: Path | None = None) -> dict[str, Any]:
    """Load the deterministic SFX/Foley recipe catalog."""
    if catalog_path is not None:
        path = Path(catalog_path)
        if not path.is_file():
            raise FileNotFoundError(f"SFX catalog not found: {path}")
        raw = path.read_text(encoding="utf-8")
        src_desc = str(path)
    elif DEFAULT_CATALOG.is_file():
        raw = DEFAULT_CATALOG.read_text(encoding="utf-8")
        src_desc = str(DEFAULT_CATALOG)
    else:
        from importlib import resources

        pkg_res = resources.files("film_pipeline.production.data").joinpath("sfx_catalog.json")
        raw = pkg_res.read_text(encoding="utf-8")
        src_desc = "package://film_pipeline/production/data/sfx_catalog.json"
    data = json.loads(raw)
    if not isinstance(data, dict) or not isinstance(data.get("entries"), list):
        raise ValueError(f"Invalid SFX catalog format: {src_desc}")
    return data


def catalog_entries(catalog_path: Path | None = None) -> dict[str, dict[str, Any]]:
    """Return mapping ``entry_id -> entry`` from the SFX catalog."""
    data = load_catalog(catalog_path)
    out: dict[str, dict[str, Any]] = {}
    for item in data["entries"]:
        eid = str(item.get("id", "")).strip()
        if eid:
            out[eid] = item
    return out


def _resolve_entry(entry_id: str, entries: dict[str, dict[str, Any]]) -> dict[str, Any]:
    if entry_id in entries:
        return entries[entry_id]
    wanted = slug(entry_id)
    for eid, item in entries.items():
        if slug(eid) == wanted:
            return item
    raise ValueError(f"Unknown SFX catalog entry {entry_id!r}; available: {', '.join(sorted(entries))}")


def synthesize_sfx(entry_id: str, out_wav: Path, *, catalog_path: Path | None = None) -> dict[str, Any]:
    """Deterministically render one catalog SFX/Foley cue to a PCM WAV file via FFmpeg ``lavfi``."""
    catalog = load_catalog(catalog_path)
    entries = {str(e["id"]): e for e in catalog["entries"] if e.get("id")}
    entry = _resolve_entry(entry_id, entries)
    duration_s = float(entry["duration_s"])
    sample_rate = int(catalog.get("sample_rate", 48000))
    channels = int(catalog.get("channels", 1))
    lavfi_in = str(entry["lavfi_input"])
    af = str(entry.get("filtergraph") or entry.get("af") or "").strip()

    out_wav = Path(out_wav)
    out_wav.parent.mkdir(parents=True, exist_ok=True)
    cmd: list[str] = [
        "ffmpeg", "-v", "error", "-y",
        "-f", "lavfi", "-i", lavfi_in,
        *(["-af", af] if af else []),
        "-t", f"{duration_s:.3f}",
        "-ar", str(sample_rate), "-ac", str(channels),
        "-c:a", "pcm_s16le", str(out_wav),
    ]
    run_ffmpeg(cmd, timeout_s=media_timeout(duration_s, floor=60.0))
    if not out_wav.is_file() or out_wav.stat().st_size <= 44:
        raise ValueError(f"Synthesized SFX output missing or empty: {out_wav}")
    return {
        "id": entry["id"],
        "slug": slug(entry["id"]),
        "category": str(entry.get("category", "sfx")),
        "license": str(catalog.get("license", "GENERATED_OFFLINE")),
        "duration_s": duration_s,
        "path": str(out_wav),
        "sha256": sha256_file(out_wav),
    }


def _film_requested_sfx_slugs(pkg: Any) -> list[str]:
    shots = pkg.typed.get("shots")
    edit = pkg.typed.get("edit")
    if shots is None:
        return []
    in_cut = {e.generation_id for e in edit.events if e.kind == "TAKE"} if edit is not None and edit.events else None
    seen: list[str] = []
    for g in shots.generations:
        if in_cut is not None and g.generation_id not in in_cut:
            continue
        for text in g.sfx:
            s = slug(text)
            if s and s not in seen:
                seen.append(s)
    return seen


def materialize_film_foley(
    pkg: Any,
    entry_ids: list[str] | None = None,
    *,
    all_catalog: bool = False,
    register_rights: bool = True,
    catalog_path: Path | None = None,
) -> dict[str, Any]:
    """Synthesize requested or shot-declared Foley/SFX WAVs into ``<film>/audio/sfx/`` and clear rights."""
    root = Path(pkg.root) if hasattr(pkg, "root") else Path(pkg)
    pkg_obj = pkg if hasattr(pkg, "root") else SimpleNamespace(root=root, typed={})
    catalog = load_catalog(catalog_path)
    entries = {str(e["id"]): e for e in catalog["entries"] if e.get("id")}
    by_slug = {slug(eid): eid for eid in entries}
    license_name = str(catalog.get("license", "GENERATED_OFFLINE"))

    skipped: list[str] = []
    if entry_ids is not None:
        wanted_ids = list(entry_ids)
    elif all_catalog:
        wanted_ids = list(entries)
    else:
        wanted_ids = []
        for s in _film_requested_sfx_slugs(pkg_obj):
            if s in by_slug:
                wanted_ids.append(by_slug[s])
            else:
                skipped.append(s)

    synthesized: list[dict[str, Any]] = []
    for raw_id in wanted_ids:
        entry = _resolve_entry(raw_id, entries)
        target_slug = slug(entry["id"])
        out_wav = audio_dir(root) / "sfx" / f"{target_slug}.wav"
        info = synthesize_sfx(entry["id"], out_wav, catalog_path=catalog_path)
        rel = out_wav.relative_to(root).as_posix()
        record_info = None
        if register_rights:
            rec = sr_mod.record_asset(
                pkg_obj,
                rel,
                "sfx",
                license_name,
                status="cleared",
                note=f"procedural {info['category']} catalog:{entry['id']}",
            )
            record_info = rec.model_dump(mode="json")
        synthesized.append({**info, "rel_path": rel, "rights_record": record_info})

    return {
        "film_id": getattr(getattr(pkg_obj, "header", None), "film_id", root.name),
        "license": license_name,
        "synthesized": synthesized,
        "unmatched_slugs": skipped,
    }


def unsourced_catalog_matches(pkg: Any, *, catalog_path: Path | None = None) -> list[str]:
    """Return matched catalog entry IDs requested by shots in cut that lack a sourced audio file."""
    root = Path(pkg.root) if hasattr(pkg, "root") else Path(pkg)
    pkg_obj = pkg if hasattr(pkg, "root") else SimpleNamespace(root=root, typed={})
    requested = _film_requested_sfx_slugs(pkg_obj)
    if not requested:
        return []
    catalog = load_catalog(catalog_path)
    entries = {str(e["id"]): e for e in catalog["entries"] if e.get("id")}
    by_slug = {slug(eid): eid for eid in entries}

    sourced_slugs: set[str] = set()
    sfx_dir = audio_dir(root) / "sfx"
    if sfx_dir.is_dir():
        for ext in ("*.wav", "*.flac", "*.mp3"):
            for p in sfx_dir.glob(ext):
                if p.is_file():
                    sourced_slugs.add(slug(p.stem))
    assets_file = audio_dir(root) / "assets.json"
    if assets_file.is_file():
        try:
            assets_doc = json.loads(assets_file.read_text(encoding="utf-8"))
            for item in assets_doc.get("assets", []):
                if item.get("kind") == "sfx" and item.get("path"):
                    asset_p = root / str(item["path"])
                    if asset_p.is_file():
                        sourced_slugs.add(slug(asset_p.stem))
        except Exception:
            pass

    missing_ids: list[str] = []
    for s in requested:
        if s in by_slug and s not in sourced_slugs:
            eid = by_slug[s]
            if eid not in missing_ids:
                missing_ids.append(eid)
    return missing_ids
