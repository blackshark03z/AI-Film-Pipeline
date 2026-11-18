"""Scene-Level Incremental Conform (`<film>/media/scenes/<scene_id>.mkv` + `.scene.json`)."""
from __future__ import annotations

import hashlib
import json
import subprocess
import tempfile
from pathlib import Path
from typing import Any

from film_pipeline.production.ffjoin import ffconcat_path, media_timeout, run_ffmpeg
from film_pipeline.production.runtime import atomic_json
from film_pipeline.production.takes import load_log, sha256_file


def _sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


class SceneIncrementalConformer:
    """Computes per-scene readiness/cache hashes and optionally conforms completed scenes incrementally."""

    def _scene_edit_events(self, section: Any, scene_gids: set[str], take_to_gid: dict[str, str]) -> list[Any]:
        if section is None or not getattr(section, "events", None):
            return []
        selected = []
        for ev in section.events:
            if getattr(ev, "kind", "TAKE") != "TAKE":
                continue
            tid = str(getattr(ev, "take_id", "") or "")
            gid = take_to_gid.get(tid)
            if gid in scene_gids or any(tid.startswith(f"{g}_t") for g in scene_gids):
                selected.append(ev)
        return selected

    def scene_status(
        self,
        pkg: Any,
        *,
        scenes_dir: Path | None = None,
        clips_dir: Path | None = None,
    ) -> dict[str, Any]:
        shots = pkg.typed.get("shots")
        story = pkg.typed.get("story")
        edit_section = pkg.typed.get("edit")
        if shots is None:
            raise ValueError("SceneIncrementalConformer requires valid 04_shots.json")

        root = Path(pkg.root)
        sdir = Path(scenes_dir) if scenes_dir is not None else root / "media" / "scenes"
        cdir = Path(clips_dir) if clips_dir is not None else root / "media" / "takes"
        log = load_log(root, pkg.header.film_id)
        take_to_gid = {t.take_id: t.generation_id for t in log.takes}

        by_scene: dict[str, list[Any]] = {}
        for g in shots.generations:
            by_scene.setdefault(g.scene_id, []).append(g)

        order = [sid for sid in getattr(story, "scenes", {}) if sid in by_scene]
        for sid in by_scene:
            if sid not in order:
                order.append(sid)

        shared_post = {}
        for rel in ("color/color_plan.json", "color/color.json", "titles/reframe.json", "titles/cues.json"):
            p = root / rel
            shared_post[rel] = _sha256_bytes(p.read_bytes()) if p.is_file() else ""

        rows: list[dict[str, Any]] = []
        fresh_scenes: list[str] = []
        ready_scenes: list[str] = []
        incomplete_scenes: list[str] = []
        invalid_scenes: list[str] = []

        for sid in order:
            gens = by_scene[sid]
            scene_gids = {g.generation_id for g in gens}
            accepted_items: list[dict[str, Any]] = []
            missing: list[str] = []
            corrupt_sources: list[str] = []
            for g in gens:
                acc = [t for t in log.for_generation(g.generation_id) if t.status == "ACCEPTED" and t.shot_version == g.version]
                if not acc:
                    missing.append(g.generation_id)
                else:
                    t = acc[-1]
                    clip_cand = cdir / Path(t.output_file).name
                    if not clip_cand.is_file():
                        clip_cand = cdir / t.output_file
                    source_ok = clip_cand.is_file() and (
                        not t.output_sha256 or sha256_file(clip_cand) == t.output_sha256
                    )
                    if not source_ok:
                        corrupt_sources.append(g.generation_id)
                    accepted_items.append({
                        "generation_id": g.generation_id,
                        "shot_version": g.version,
                        "take_id": t.take_id,
                        "output_file": t.output_file,
                        "output_sha256": t.output_sha256,
                        "source_verified": source_ok,
                    })

            scene_edl = self._scene_edit_events(edit_section, scene_gids, take_to_gid)
            edl_payload = [ev.model_dump(mode="json") for ev in scene_edl]
            payload = {
                "scene_id": sid,
                "takes": accepted_items,
                "missing": missing,
                "shared": shared_post,
                "edl": edl_payload,
            }
            input_sha = _sha256_bytes(json.dumps(payload, sort_keys=True).encode("utf-8"))
            mkv = sdir / f"{sid}.mkv"
            meta = sdir / f"{sid}.scene.json"

            cached_sha = ""
            cached_out_sha = ""
            if meta.is_file():
                try:
                    meta_doc = json.loads(meta.read_text(encoding="utf-8"))
                    cached_sha = str(meta_doc.get("input_sha256") or "")
                    cached_out_sha = str(meta_doc.get("output_sha256") or "")
                except (OSError, ValueError):
                    cached_sha = ""
                    cached_out_sha = ""

            mkv_sha = sha256_file(mkv) if (mkv.is_file() and mkv.stat().st_size > 0) else ""
            output_ok = bool(mkv_sha) and bool(cached_out_sha) and (mkv_sha == cached_out_sha)

            if missing:
                state = "INCOMPLETE"
                incomplete_scenes.append(sid)
            elif corrupt_sources:
                state = "SOURCE_INVALID"
                invalid_scenes.append(sid)
            elif output_ok and cached_sha == input_sha:
                state = "FRESH"
                fresh_scenes.append(sid)
            else:
                state = "READY_TO_CONFORM"
                ready_scenes.append(sid)

            rows.append({
                "scene_id": sid,
                "state": state,
                "generations": len(gens),
                "accepted": len(accepted_items),
                "missing": missing,
                "corrupt_sources": corrupt_sources,
                "edl_events": len(scene_edl),
                "input_sha256": input_sha,
                "output_sha256": mkv_sha,
                "artifact": str(mkv),
                "accepted_takes": accepted_items,
            })

        return {
            "film_id": pkg.header.film_id,
            "total_scenes": len(rows),
            "fresh_scenes": fresh_scenes,
            "ready_scenes": ready_scenes,
            "incomplete_scenes": incomplete_scenes,
            "invalid_scenes": invalid_scenes,
            "scenes": rows,
        }

    def conform_ready_scenes(
        self,
        pkg: Any,
        *,
        render: bool = False,
        scenes: list[str] | None = None,
        out_dir: Path | None = None,
        clips_dir: Path | None = None,
        jobs: int | None = None,
        hwaccel: bool | None = None,
    ) -> dict[str, Any]:
        root = Path(pkg.root)
        sdir = Path(out_dir) if out_dir is not None else root / "media" / "scenes"
        cdir = Path(clips_dir) if clips_dir is not None else root / "media" / "takes"
        status = self.scene_status(pkg, scenes_dir=sdir, clips_dir=cdir)
        wanted = set(scenes) if scenes is not None else None
        edit_section = pkg.typed.get("edit")
        log = load_log(root, pkg.header.film_id)
        take_to_gid = {t.take_id: t.generation_id for t in log.takes}

        planned: list[dict[str, Any]] = []
        rendered: list[dict[str, Any]] = []
        for row in status["scenes"]:
            sid = row["scene_id"]
            if wanted is not None and sid not in wanted:
                continue
            if row["state"] != "READY_TO_CONFORM":
                planned.append({"scene_id": sid, "action": f"SKIP_{row['state']}"})
                continue
            planned.append({"scene_id": sid, "action": "CONFORM" if render else "WOULD_CONFORM"})
            if not render:
                continue

            take_files = []
            for item in row["accepted_takes"]:
                cand = cdir / Path(item["output_file"]).name
                if not cand.is_file():
                    cand = cdir / item["output_file"]
                if not cand.is_file():
                    raise FileNotFoundError(f"Scene {sid} missing clip files: {cand}")
                if item.get("output_sha256") and sha256_file(cand) != item["output_sha256"]:
                    raise ValueError(f"Scene {sid} clip hash mismatch for {item['take_id']}")
                take_files.append(cand)

            sdir.mkdir(parents=True, exist_ok=True)
            out_mkv = sdir / f"{sid}.mkv"
            meta_json = sdir / f"{sid}.scene.json"

            scene_gids = {item["generation_id"] for item in row["accepted_takes"]}
            scene_edl = self._scene_edit_events(edit_section, scene_gids, take_to_gid)
            with tempfile.TemporaryDirectory() as tmp:
                tmp_dir = Path(tmp)
                if scene_edl and edit_section is not None:
                    from film_pipeline.production.edit import AudioCut, EditSection, Transition, render_cut

                    normalized_events = list(scene_edl)
                    first_ev = normalized_events[0]
                    if first_ev.transition.type != "CUT" or first_ev.audio.j_cut_s != 0 or first_ev.audio.l_cut_s != 0:
                        normalized_events[0] = first_ev.model_copy(
                            update={"transition": Transition(type="CUT"), "audio": AudioCut()}
                        )
                    scene_section = EditSection(
                        title=[],
                        title_s=1.0,
                        end=[],
                        end_s=1.0,
                        events=normalized_events,
                        tags=[],
                    )
                    scene_mp4 = tmp_dir / f"{sid}.mp4"
                    rep = render_cut(
                        pkg,
                        scene_section,
                        scene_mp4,
                        clips_dir=cdir,
                        require_accepted=True,
                        cache_dir=sdir / ".render_cache",
                        jobs=jobs,
                        hwaccel=hwaccel,
                    )
                    planned_cut = rep.get("planned") or {}
                    t0 = float(planned_cut.get("title_s", 1.0))
                    t1 = float(planned_cut.get("body_end_s", t0 + 1.0))
                    body_dur = max(0.05, t1 - t0)
                    run_ffmpeg(
                        [
                            "ffmpeg", "-v", "error", "-y",
                            "-ss", f"{t0:.6f}", "-t", f"{body_dur:.6f}", "-i", str(scene_mp4),
                            "-c:v", "libx264", "-pix_fmt", "yuv420p", "-r", str(pkg.header.fps),
                            "-c:a", "pcm_s16le", "-ar", "48000", "-ac", "2", str(out_mkv),
                        ],
                        timeout_s=media_timeout(max(6.0, body_dur), floor=120.0),
                    )
                else:
                    lst = tmp_dir / f"{sid}_concat.txt"
                    lst.write_text(
                        "".join(f"file '{ffconcat_path(p)}'\n" for p in take_files),
                        encoding="utf-8",
                    )
                    run_ffmpeg(
                        [
                            "ffmpeg", "-v", "error", "-y", "-f", "concat", "-safe", "0", "-i", str(lst),
                            "-c:v", "libx264", "-pix_fmt", "yuv420p", "-r", str(pkg.header.fps),
                            "-c:a", "pcm_s16le", "-ar", "48000", "-ac", "2", str(out_mkv),
                        ],
                        timeout_s=media_timeout(max(6.0, len(take_files) * 6.0), floor=120.0),
                    )
            out_sha = sha256_file(out_mkv)
            atomic_json(
                meta_json,
                {
                    "film_id": pkg.header.film_id,
                    "scene_id": sid,
                    "input_sha256": row["input_sha256"],
                    "output_sha256": out_sha,
                    "edl_events": len(scene_edl),
                    "takes": row["accepted_takes"],
                    "output": str(out_mkv),
                },
            )
            rendered.append({
                "scene_id": sid,
                "output": str(out_mkv),
                "input_sha256": row["input_sha256"],
                "output_sha256": out_sha,
                "edl_events": len(scene_edl),
            })

        return {**status, "render": render, "planned": planned, "rendered": rendered}
