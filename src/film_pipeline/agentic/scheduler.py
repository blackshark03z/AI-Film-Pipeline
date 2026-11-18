"""Topological handoff-wave DAG scheduler over `04_shots.json` and `takes/index.json`."""
from __future__ import annotations

from pathlib import Path
from typing import Any

from film_pipeline.production.recovery import pending_receipts
from film_pipeline.production.takes import load_log, sha256_file


class WaveDAGScheduler:
    """Computes parallel dispatch waves without splitting worktrees."""

    def __init__(self, pkg: Any) -> None:
        self.pkg = pkg

    def plan_waves(self) -> dict[str, Any]:
        shots = self.pkg.typed.get("shots")
        if shots is None:
            raise ValueError("WaveDAGScheduler requires a valid 04_shots.json")

        root = Path(self.pkg.root)
        log = load_log(root, self.pkg.header.film_id)
        by_id = {g.generation_id: g for g in shots.generations}
        pending = pending_receipts(self.pkg)
        pending_gids = sorted({str(r.get("generation_id") or "") for r in pending if r.get("generation_id")})
        pending_set = set(pending_gids)

        accepted_ids: set[str] = set()
        unverified_accepted: list[str] = []
        for t in log.takes:
            if t.status != "ACCEPTED" or t.shot_version != getattr(by_id.get(t.generation_id), "version", None):
                continue
            review_missing = bool(t.review_file) and not (
                (root / "takes" / t.review_file).is_file() or (root / t.review_file).is_file()
            )
            clip = root / "media" / "takes" / Path(t.output_file).name
            if not clip.is_file():
                clip = root / "media" / "takes" / t.output_file
            clip_present = clip.is_file()
            clip_corrupt = clip_present and bool(t.output_sha256) and sha256_file(clip) != t.output_sha256
            if review_missing or clip_corrupt:
                unverified_accepted.append(t.generation_id)
                continue
            if not clip_present or not t.review_file:
                unverified_accepted.append(t.generation_id)
            accepted_ids.add(t.generation_id)

        remaining = [g for g in shots.generations if g.generation_id not in accepted_ids]
        wave_of: dict[str, int] = {}
        blocked: list[dict[str, str]] = []

        def depth(gid: str, visiting: set[str] | None = None) -> int | None:
            if gid in accepted_ids:
                return -1
            if gid in wave_of:
                return wave_of[gid]
            decl = by_id.get(gid)
            if decl is None:
                return None
            prev = decl.previous_generation_id
            if not prev:
                wave_of[gid] = 0
                return 0
            if prev in accepted_ids:
                wave_of[gid] = 0
                return 0
            if prev not in by_id:
                blocked.append({"generation_id": gid, "reason": f"unknown previous_generation_id {prev!r}"})
                return None
            seen = set(visiting or set())
            if gid in seen:
                blocked.append({"generation_id": gid, "reason": f"cycle detected involving {gid}"})
                return None
            seen.add(gid)
            prev_depth = depth(prev, seen)
            if prev_depth is None:
                blocked.append({"generation_id": gid, "reason": f"upstream {prev} is blocked"})
                return None
            wave_of[gid] = prev_depth + 1
            return wave_of[gid]

        waves_map: dict[int, list[dict[str, Any]]] = {}
        for g in remaining:
            d = depth(g.generation_id)
            if d is None:
                continue
            waves_map.setdefault(d, []).append({
                "generation_id": g.generation_id,
                "scene_id": g.scene_id,
                "coverage": g.coverage,
                "previous_generation_id": g.previous_generation_id,
                "version": g.version,
            })

        waves = {str(k): waves_map[k] for k in sorted(waves_map)}
        ready = [item["generation_id"] for item in waves_map.get(0, []) if item["generation_id"] not in pending_set]
        crit_depth = (max(waves_map) + 1) if waves_map else 0
        unverified_unique = sorted(set(unverified_accepted))
        basis = "verified_media" if accepted_ids and not unverified_unique else "dependency_and_index"
        return {
            "film_id": self.pkg.header.film_id,
            "readiness_basis": basis,
            "total_generations": len(shots.generations),
            "accepted_count": len(accepted_ids),
            "unverified_accepted": unverified_unique,
            "pending_sends": pending_gids,
            "remaining_count": len(remaining),
            "waves": waves,
            "ready_frontier": ready,
            "blocked_chains": blocked,
            "critical_path_depth": crit_depth,
        }

    def ready_generations(self) -> list[str]:
        return list(self.plan_waves()["ready_frontier"])
