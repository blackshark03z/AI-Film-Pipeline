"""Scene-Level Incremental Conform (`<film>/media/scenes/<scene_id>.mkv` + `.scene.json`)."""
from __future__ import annotations

import hashlib
import json
import subprocess
import tempfile
from pathlib import Path
from typing import Any

from film_pipeline.production.ffjoin import media_timeout, run_ffmpeg
from film_pipeline.production.runtime import atomic_json
from film_pipeline.production.takes import load_log


def _sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


class SceneIncrementalConformer:
    """Computes per-scene readiness/cache hashes and optionally conforms completed scenes incrementally."""

    def scene_status(self, pkg: Any, *, scenes_dir: Path | None = None) -> dict[str, Any]:
        shots = pkg.typed.get("shots")
        story = pkg.typed.get("story")
        if shots is None:
            raise ValueError("SceneIncrementalConformer requires valid 04_shots.json")

        root = Path(pkg.root)
        sdir = Path(scenes_dir) if scenes_dir is not None else root / "media" / "scenes"
        log = load_log(root, pkg.header.film_id)

        by_scene: dict[str, list[Any]] = {}
        for g in shots.generations:
            by_scene.setdefault(g.scene_id, []).append(g)

        order = [sid for sid in getattr(story, "scenes", {}) if sid in by_scene]
        for sid in by_scene:
            if sid not in order:
                order.append(sid)

        shared_post = {}
        for rel in ("color/color_plan.json", "titles/reframe.json", "titles/cues.json"):
            p = root / rel
            shared_post[rel] = _sha256_bytes(p.read_bytes()) if p.is_file() else ""

        rows: list[dict[str, Any]] = []
        fresh_scenes: list[str] = []
        ready_scenes: list[str] = []
        incomplete_scenes: list[str] = []

        for sid in order:
            gens = by_scene[sid]
            accepted_items: list[dict[str, Any]] = []
            missing: list[str] = []
            for g in gens:
                acc = [t for t in log.for_generation(g.generation_id) if t.status == "ACCEPTED" and t.shot_version == g.version]
                if not acc:
                    missing.append(g.generation_id)
                else:
                    t = acc[-1]
                    accepted_items.append({
                        "generation_id": g.generation_id,
                        "shot_version": g.version,
                        "take_id": t.take_id,
                        "output_file": t.output_file,
                        "output_sha256": t.output_sha256,
                    })

            payload = {"scene_id": sid, "takes": accepted_items, "missing": missing, "shared": shared_post}
            input_sha = _sha256_bytes(json.dumps(payload, sort_keys=True).encode("utf-8"))
            mkv = sdir / f"{sid}.mkv"
            meta = sdir / f"{sid}.scene.json"

            cached_sha = ""
            if meta.is_file():
                try:
                    cached_sha = str(json.loads(meta.read_text(encoding="utf-8")).get("input_sha256") or "")
                except (OSError, ValueError):
                    cached_sha = ""

            if missing:
                state = "INCOMPLETE"
                incomplete_scenes.append(sid)
            elif mkv.is_file() and mkv.stat().st_size > 0 and cached_sha == input_sha:
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
                "input_sha256": input_sha,
                "artifact": str(mkv),
                "accepted_takes": accepted_items,
            })

        return {
            "film_id": pkg.header.film_id,
            "total_scenes": len(rows),
            "fresh_scenes": fresh_scenes,
            "ready_scenes": ready_scenes,
            "incomplete_scenes": incomplete_scenes,
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
    ) -> dict[str, Any]:
        root = Path(pkg.root)
        sdir = Path(out_dir) if out_dir is not None else root / "media" / "scenes"
        cdir = Path(clips_dir) if clips_dir is not None else root / "media" / "takes"
        status = self.scene_status(pkg, scenes_dir=sdir)
        wanted = set(scenes) if scenes is not None else None

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

            take_files = [cdir / item["output_file"] for item in row["accepted_takes"]]
            missing_files = [str(p) for p in take_files if not p.is_file()]
            if missing_files:
                raise FileNotFoundError(f"Scene {sid} missing clip files: {missing_files[0]}")

            sdir.mkdir(parents=True, exist_ok=True)
            out_mkv = sdir / f"{sid}.mkv"
            meta_json = sdir / f"{sid}.scene.json"
            with tempfile.TemporaryDirectory() as tmp:
                lst = Path(tmp) / f"{sid}_concat.txt"
                lst.write_text(
                    "".join(
                        f"file '{p.resolve().as_posix().replace(chr(39), chr(39) + chr(92) + chr(39) + chr(39))}'\n"
                        for p in take_files
                    ),
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
            atomic_json(
                meta_json,
                {
                    "film_id": pkg.header.film_id,
                    "scene_id": sid,
                    "input_sha256": row["input_sha256"],
                    "takes": row["accepted_takes"],
                    "output": str(out_mkv),
                },
            )
            rendered.append({"scene_id": sid, "output": str(out_mkv), "input_sha256": row["input_sha256"]})

        return {**status, "render": render, "planned": planned, "rendered": rendered}
