"""Sound asset rights and the music cue sheet (categories 115-116 music, 110-111 effects, rights ledger).

Every sound file the mix would use must have a cleared record in ``<film>/audio/assets.json``:

* *used* = the music cues of ``audio/mix_plan.json`` and the ``audio/sfx/<slug>.*`` files that match a declared ``sfx`` of a
  shot that is in the cut (all shots when there is no EDL); generated beds need no record.
* a record names the asset (path under the film), its ``kind``, ``source_url`` (CC0 / CC-BY / royalty-free), ``license``,
  ``sha256`` (must equal the file on disk), ``status`` (only a human sets ``cleared``; the CLI records ``pending``), an
  ``attribution`` text where the license needs one, and ``usage`` ranges (music: the cue's start/end must lie inside one).
* ``sound_rights_issues`` returns BLOCK strings; ``planning_issues`` includes them, so ``film.py validate`` blocks delivery
  while any used asset is unrecorded, changed, uncleared, unlicensed or used outside its recorded range.

``cue_sheet`` reads the emotional curve of ``02_direction.json`` (per scene, mean over characters, 0-5) and says where music
could start, hold and stop and why; it is advice for the Owner/director, and it lists the cues the plan really has with their
reasons. Nothing is downloaded: assets are put in place by a human, with the source recorded here.
"""
from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any, Literal

from pydantic import Field

from film_pipeline.core import ContractModel
from film_pipeline.production.mix import audio_dir, load_plan, sha256_file, slug

LICENSES = ("CC0-1.0", "CC-BY-4.0", "CC-BY-3.0", "ROYALTY_FREE", "ORIGINAL", "GENERATED_OFFLINE", "OWNER_LICENSED")
NEEDS_SOURCE_URL = ("CC0-1.0", "CC-BY-4.0", "CC-BY-3.0", "ROYALTY_FREE")
NEEDS_ATTRIBUTION = ("CC-BY-4.0", "CC-BY-3.0")
HIGH, RISE = 3.0, 1.0   # a scene whose mean end intensity is >= HIGH, or that rises by >= RISE, calls for music


class UsageRange(ContractModel):
    start_s: float = Field(default=0.0, ge=0)
    end_s: float | None = None     # None: to the end of the film
    note: str = ""


class AssetRecord(ContractModel):
    asset: str                     # path under the film root, forward slashes
    kind: Literal["music", "sfx"]
    license: str
    status: Literal["cleared", "pending", "restricted", "unknown"] = "pending"
    source_url: str = ""
    sha256: str = ""
    attribution: str = ""
    note: str = ""
    usage: list[UsageRange] = Field(default_factory=list)


class AssetLedger(ContractModel):
    assets: list[AssetRecord] = Field(default_factory=list)


def ledger_path(root: Path) -> Path:
    return audio_dir(root) / "assets.json"


def load_ledger(root: Path) -> AssetLedger:
    path = ledger_path(root)
    return AssetLedger.model_validate_json(path.read_text(encoding="utf-8")) if path.is_file() else AssetLedger()


def save_ledger(root: Path, ledger: AssetLedger) -> Path:
    path = ledger_path(root)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(ledger.model_dump_json(indent=2) + "\n", encoding="utf-8")
    return path


def record_asset(pkg: Any, asset: str, kind: str, license: str, *, source_url: str = "", status: str = "pending",
                 attribution: str = "", note: str = "", usage: list[UsageRange] | None = None) -> AssetRecord:
    """Add or replace the record of ``asset`` (hash taken from the file). Raises ValueError for a missing file."""
    root = Path(pkg.root)
    path = root / asset
    if not path.is_file():
        raise ValueError(f"{asset} not found under {root}")
    rec = AssetRecord(asset=asset.replace("\\", "/"), kind=kind, license=license, status=status, source_url=source_url,
                      sha256=sha256_file(path), attribution=attribution, note=note, usage=usage or [])
    ledger = load_ledger(root)
    save_ledger(root, AssetLedger(assets=[a for a in ledger.assets if a.asset != rec.asset] + [rec]))
    return rec


def used_assets(pkg: Any) -> list[dict[str, Any]]:
    """Assets the plan would put in the mix: {asset, kind, uses: [{...}]}, music first."""
    root = Path(pkg.root)
    plan = load_plan(root)
    found: dict[str, dict[str, Any]] = {}
    for cue in plan.music:
        rel = ("audio/" + cue.asset).replace("\\", "/")
        found.setdefault(rel, {"asset": rel, "kind": "music", "uses": []})["uses"].append(
            {"cue_id": cue.cue_id, "start_s": cue.start_s, "end_s": cue.end_s})
    shots, edit = pkg.typed.get("shots"), pkg.typed.get("edit")
    if shots is not None:
        in_cut = {e.generation_id for e in edit.events if e.kind == "TAKE"} if edit is not None and edit.events else None
        for g in shots.generations:
            if in_cut is not None and g.generation_id not in in_cut:
                continue
            for text in g.sfx:
                for ext in (".wav", ".flac", ".mp3"):
                    path = audio_dir(root) / "sfx" / f"{slug(text)}{ext}"
                    if path.is_file():
                        rel = path.relative_to(root).as_posix()
                        found.setdefault(rel, {"asset": rel, "kind": "sfx", "uses": []})["uses"].append(
                            {"generation_id": g.generation_id, "text": text})
                        break
    return sorted(found.values(), key=lambda a: (a["kind"] != "music", a["asset"]))


def _covered(use: dict[str, Any], rec: AssetRecord) -> bool:
    start, end = use["start_s"], use["end_s"]
    for r in rec.usage:
        if start >= r.start_s - 1e-6 and (r.end_s is None or (end is not None and end <= r.end_s + 1e-6)):
            return True
    return False


def check_assets(pkg: Any) -> dict[str, Any]:
    """{used, issues: [{code, asset, detail}]} - every issue is a BLOCK."""
    root = Path(pkg.root)
    ledger = {a.asset: a for a in load_ledger(root).assets}
    used, issues = used_assets(pkg), []

    def add(code: str, asset: str, detail: str) -> None:
        issues.append({"code": code, "asset": asset, "detail": detail})

    for item in used:
        name = item["asset"]
        rec = ledger.get(name)
        path = root / name
        if not path.is_file():
            add("ASSET_MISSING", name, "the plan uses a file that does not exist")
            continue
        if rec is None:
            add("ASSET_UNRECORDED", name, "no record in audio/assets.json (film.py sounds --record ...)")
            continue
        if rec.sha256 != sha256_file(path):
            add("ASSET_HASH_CHANGED", name, "the file no longer matches the recorded sha256; record it again")
        if rec.license not in LICENSES:
            add("LICENSE_UNKNOWN", name, f"license {rec.license!r} is not one of {', '.join(LICENSES)}")
        if rec.status != "cleared":
            add("LICENSE_NOT_CLEARED", name, f"status {rec.status}: a human must clear it")
        if rec.license in NEEDS_SOURCE_URL and not re.match(r"^https?://\S+$", rec.source_url):
            add("SOURCE_MISSING", name, f"{rec.license} needs the source_url it came from")
        if rec.license in NEEDS_ATTRIBUTION and not rec.attribution.strip():
            add("ATTRIBUTION_MISSING", name, f"{rec.license} requires an attribution text")
        if rec.kind != item["kind"]:
            add("KIND_MISMATCH", name, f"recorded as {rec.kind}, used as {item['kind']}")
        if item["kind"] == "music":
            for use in item["uses"]:
                if not _covered(use, rec):
                    add("USAGE_NOT_COVERED", name, f"cue {use['cue_id']} {use['start_s']}-{use['end_s']} s lies outside "
                                                   f"the recorded usage ranges")
    return {"used": used, "issues": issues}


def sound_rights_issues(pkg: Any) -> list[str]:
    return [f"SOUND_RIGHTS {i['code']} {i['asset']}: {i['detail']}" for i in check_assets(pkg)["issues"]]


def attributions(pkg: Any) -> list[str]:
    """Credit lines owed by the used, recorded assets (for the credits card in P5-04)."""
    ledger = {a.asset: a for a in load_ledger(Path(pkg.root)).assets}
    return sorted({ledger[u["asset"]].attribution.strip() for u in used_assets(pkg)
                   if u["asset"] in ledger and ledger[u["asset"]].attribution.strip()})


def cue_sheet(pkg: Any) -> dict[str, Any]:
    """Advice per scene from the emotional curve, and the cues the plan has (with their scene and reason)."""
    direction, story = pkg.typed.get("direction"), pkg.typed.get("story")
    plan = load_plan(Path(pkg.root))
    if direction is None:
        raise ValueError("a cue sheet needs a valid 02_direction.json")
    order = list(story.scenes) if story is not None else list(direction.scenes)
    scenes = [sid for sid in order if sid in direction.scenes]
    advice, running, previous_end = [], False, None
    for sid in scenes:
        d = direction.scenes[sid]
        starts = [c.start for c in d.curve.values()]
        ends = [c.end for c in d.curve.values()]
        level_start, level_end = sum(starts) / len(starts), sum(ends) / len(ends)
        rising = previous_end is not None and level_end - previous_end >= RISE
        hold = any(e.device == "hold" for e in d.emphasis)
        if not running and (level_end >= HIGH or (rising and level_end >= 2)):
            action, why, running = "IN", f"intensity {level_start:g} -> {level_end:g}: the scene reaches the high register", True
        elif running and level_end <= 1:
            action, why, running = "OUT", f"intensity falls to {level_end:g}: let the room be quiet", False
        elif running and hold:
            action, why = "DUCK", "a held emphasis moment: pull the music under it or stop it"
        elif running:
            action, why = "HOLD", f"intensity {level_start:g} -> {level_end:g}: keep the bed"
        else:
            action, why = "NONE", f"intensity {level_start:g} -> {level_end:g}: nothing for music to say"
        advice.append({"scene_id": sid, "intensity_start": round(level_start, 2), "intensity_end": round(level_end, 2),
                       "action": action, "why": why})
        previous_end = level_end
    known = set(direction.scenes)
    planned, warnings = [], []
    for cue in plan.music:
        row = {**cue.model_dump(mode="json")}
        planned.append(row)
        if not cue.why.strip():
            warnings.append({"code": "CUE_NO_REASON", "cue_id": cue.cue_id, "detail": "a cue says why it starts and stops"})
        if cue.scene_id and cue.scene_id not in known:
            warnings.append({"code": "CUE_SCENE_UNKNOWN", "cue_id": cue.cue_id, "detail": f"{cue.scene_id} is not a scene"})
        elif cue.scene_id:
            said = next((a["action"] for a in advice if a["scene_id"] == cue.scene_id), "NONE")
            if said == "NONE":
                warnings.append({"code": "CUE_AGAINST_CURVE", "cue_id": cue.cue_id,
                                 "detail": f"{cue.scene_id}: the emotional curve calls for no music here"})
    return {"advice": advice, "planned": planned, "warnings": warnings,
            "music_planned": bool(plan.music), "music_suggested": any(a["action"] == "IN" for a in advice)}
