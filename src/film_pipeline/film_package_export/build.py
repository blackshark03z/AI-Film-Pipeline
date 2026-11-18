"""Build a film_package v1 manifest from an AFP film folder (read-only on the folder)."""
from __future__ import annotations

import json
import re
import subprocess
from fractions import Fraction
from pathlib import Path
from typing import Any

from .media import ExportError, probe, sha256_file
from .story import build_dialogue, build_scenes, build_timeline

# Pictures AFP renders under media/cut/. Only the default-graded rough cut has a provable baked state; for the others
# the grade is reported as "unknown" rather than guessed. (grade, subtitles baked)
PICTURES = {"rough_cut": ("afp_default_grade", False), "graded_cut": ("unknown", False),
            "titled_cut.clean": ("unknown", False), "titled_cut": ("unknown", True)}
# (mix.json key = role = stem name, provenance): a stem is a layer only when mix.json says it carries something
LAYER_STEMS = (("ambience", "ambience", "afp_synthesized"), ("sfx", "sfx", "catalog_asset"))
ROLES = {"music", "ambience", "sfx", "foley"}


class _Files:
    def __init__(self, root: Path) -> None:
        self.root, self.items, self.by_path = root, [], {}

    def add(self, rel: str, file_id: str) -> str:
        rel = rel.replace("\\", "/")
        if rel in self.by_path:
            return self.by_path[rel]
        path = (self.root / rel).resolve()
        if self.root not in path.parents or not path.is_file():
            raise ExportError(f"file not found inside the film folder: {rel}")
        if any(i["id"] == file_id for i in self.items):
            raise ExportError(f"duplicate file id {file_id}")
        self.items.append({"id": file_id, "path": rel, "sha256": sha256_file(path), "bytes": path.stat().st_size})
        self.by_path[rel] = file_id
        return file_id

    def sha(self, file_id: str) -> str:
        return next(i["sha256"] for i in self.items if i["id"] == file_id)

    def has(self, rel: str) -> bool:
        return (self.root / rel).is_file()


def _json(root: Path, rel: str, required: bool = False) -> Any:
    path = root / rel
    if not path.is_file():
        if required:
            raise ExportError(f"missing required file: {rel}")
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ExportError(f"{rel} is not valid JSON: {exc}") from exc


def _git(root: Path) -> dict[str, Any]:
    def run(*args: str) -> str | None:
        try:
            done = subprocess.run(["git", "-C", str(root), *args], capture_output=True, text=True, check=False)
        except OSError:
            return None
        return done.stdout if done.returncode == 0 else None
    rev, status = run("rev-parse", "HEAD"), run("status", "--porcelain")
    if rev is None or status is None:
        return {}
    return {"revision": rev.strip(), "dirty": bool(status.strip())}


def _slug(text: str) -> str:
    return re.sub(r"[^A-Za-z0-9_.:-]+", "_", text).strip("_")[:100]


def build_package(film_dir: str | Path, picture: str = "rough_cut",
                  mix_info: dict[str, Any] | None = None) -> tuple[dict[str, Any], list[str]]:
    """Return ``(package, warnings)``. Raises ExportError when the folder cannot honestly be exported.

    ``mix_info`` (``ambience``/``sfx`` rows and ``plan.music``, the shape of audio/mix.json) replaces audio/mix.json
    when the stems were just built and the file on disk is stale or not written yet; it is then not referenced."""
    root = Path(film_dir).resolve()
    if not root.is_dir():
        raise ExportError(f"film folder not found: {root}")
    if picture not in PICTURES:
        raise ExportError(f"unsupported picture {picture!r}; choose one of {sorted(PICTURES)}")
    warns: list[str] = []
    files = _Files(root)
    film = _json(root, "film.json", required=True)
    pic_rel, cut_rel = f"media/cut/{picture}.mp4", f"media/cut/{picture}.cut.json"
    pic_id = files.add(pic_rel, "picture")
    cut = _json(root, cut_rel, required=True)
    if cut.get("output_sha256") and cut["output_sha256"] != files.sha(pic_id):
        raise ExportError(f"{pic_rel} sha256 differs from {cut_rel} output_sha256 (picture changed after render)")
    video = probe(root / pic_rel)["video"]
    if not video or not video["fps"]:
        raise ExportError(f"{pic_rel} has no readable video stream")
    fps: Fraction = video["fps"]
    if film.get("fps") and Fraction(str(film["fps"])).limit_denominator(1001) != fps:
        raise ExportError(f"film.json fps {film['fps']} differs from the picture's {fps}")
    duration = video["nb_frames"] or round(video["duration_s"] * float(fps))
    if cut.get("total_s") and abs(float(cut["total_s"]) * float(fps) - duration) > 1:
        raise ExportError(f"cut report total_s {cut['total_s']} does not match the picture ({duration} frames)")

    edit = _json(root, "05_edit.json")
    lock = _json(root, "lock/picture.lock.json")
    shots = {g["generation_id"]: g["scene_id"] for g in (_json(root, "04_shots.json") or {}).get("generations", [])
             if g.get("generation_id") and g.get("scene_id")}
    timeline: list[dict[str, Any]] = []
    if edit:
        timeline = build_timeline(cut, edit, lock, fps, duration, shots, warns)
    else:
        warns.append("05_edit.json missing: no timeline")
    titles, cues = _json(root, "titles/titles.json"), _json(root, "titles/cues.json")
    if titles is None:
        warns.append("titles/titles.json missing: no dialogue cues")
    dialogue = build_dialogue(titles, cues, timeline, fps, cut, warns) if timeline else []
    if lock and edit and {e["event_id"] for e in lock.get("events", [])} != {e["event_id"] for e in edit["events"]}:
        warns.append("picture lock lists different events than 05_edit.json (lock is stale)")

    # --- audio: the dialogue stem is the whole cut audio (native composite); layers are independent stems only
    stem = "audio/stems/dialogue.wav"
    track_id = files.add(stem, "stem_dialogue")
    sample_rate = (probe(root / stem)["audio"] or {}).get("sample_rate")
    mix = mix_info if mix_info is not None else _json(root, "audio/mix.json")
    layers = []
    if mix is None:
        warns.append("audio/mix.json missing: no layers (cannot tell independent stems from derived beds)")
    else:
        wanted = [(k, k, p) for k, _, p in LAYER_STEMS if mix.get(k)]
        if (mix.get("plan") or {}).get("music"):
            wanted.append(("music", "music", "catalog_asset"))
        for role, name, prov in wanted:
            layers.append({"id": name, "file_id": files.add(f"audio/stems/{name}.wav", f"stem_{name}"),
                           "role": role, "provenance": prov})
    rights_id = files.add("delivery/rights/rights.json", "rights") if files.has("delivery/rights/rights.json") else None
    assets = []
    for entry in (_json(root, "audio/assets.json") or {}).get("assets", []):
        if entry.get("kind") not in ROLES:
            warns.append(f"asset {entry.get('asset')}: kind {entry.get('kind')!r} is not a contract role, skipped")
            continue
        fid = files.add(entry["asset"], "asset_" + _slug(Path(entry["asset"]).stem))
        if entry.get("sha256") and entry["sha256"] != files.sha(fid):
            raise ExportError(f"{entry['asset']} sha256 differs from audio/assets.json")
        row = {"id": fid, "file_id": fid, "role": entry["kind"]}
        if rights_id:
            row["rights_ref"] = rights_id
        assets.append(row)
    refs = {}
    for role, rel in (("edl", "05_edit.json"), ("cut_report", cut_rel), ("mix_report", "audio/mix.json"),
                      ("qc", "qc/master_qc.json"), ("delivery", "07_delivery.json")):
        if files.has(rel) and not (role == "mix_report" and mix_info is not None):
            refs[role] = files.add(rel, role)
    if rights_id:
        refs["rights"] = rights_id
    lock_id = files.add("lock/picture.lock.json", "lock") if lock else None

    level = "L2" if timeline and dialogue and layers else "L1" if timeline and dialogue else "L0"
    if level == "L0":
        warns.append("level L0: L1 needs both a timeline and dialogue cues")
    if layers and level != "L2":
        warns.append(f"{len(layers)} independent layer(s) kept but level is {level} (L2 needs L1 first)")
    event_scene = {r["event_id"]: r.get("scene_id") for r in timeline}
    speakers: dict[str, list[str]] = {}
    for cue in dialogue:
        if cue.get("speaker") and event_scene.get(cue["event_id"]):
            speakers.setdefault(event_scene[cue["event_id"]], []).append(cue["speaker"])
    scenes = build_scenes(timeline, _json(root, "01_story.json"), _json(root, "03_preprod.json"), mix, speakers)

    grade, subs = PICTURES[picture]
    if grade == "unknown":
        warns.append(f"{picture}: baked grade not verifiable, reported as unknown")
    planned = cut.get("planned") or {}
    cards = bool(planned.get("title_s") or planned.get("end_s")) or any(r["kind"] == "CARD" for r in timeline)
    always = (film.get("disclosure") or {}).get("ai_label", "always") == "always"
    pkg: dict[str, Any] = {"schema_version": "1.0", "film_id": film["film_id"], "title": film.get("title", film["film_id"]),
                           "language": film.get("language", "en"),
                           "source": {"root": str(root), "producer": "afp", **_git(root)}, "files": files.items}
    if lock_id:
        pkg["lock"] = {"file_id": lock_id, "render_binding": "unverified",
                       **({"edl_sha256": lock["edl_sha256"]} if lock.get("edl_sha256") else {})}
    pkg["clock"] = {"fps_num": fps.numerator, "fps_den": fps.denominator, "duration_frames": duration,
                    **({"audio_sample_rate": sample_rate} if sample_rate else {})}
    pkg["picture"] = {"file_id": pic_id, "width": video["width"], "height": video["height"],
                      "baked": {"grade": grade, "cards": cards, "subtitles": subs,
                                "tags": "AI-generated label over the body + opening card" if always else "opening card only"}}
    for key, val in (("timeline", timeline), ("scenes", scenes), ("dialogue", dialogue)):
        if val:
            pkg[key] = val
    pkg["audio"] = {"level": level, "production_track": {"file_id": track_id, "provenance": "native_composite"},
                    **({"layers": layers} if layers else {})}
    if assets:
        pkg["assets"] = assets
    pkg["references"] = refs
    return pkg, warns
