"""Topological handoff-wave DAG scheduler over `04_shots.json` and `takes/index.json`."""
from __future__ import annotations

from pathlib import Path
from typing import Any

from film_pipeline.production.takes import load_log


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
        accepted_ids = {
            t.generation_id
            for t in log.takes
            if t.status == "ACCEPTED" and t.shot_version == getattr(by_id.get(t.generation_id), "version", None)
        }

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
        ready = [item["generation_id"] for item in waves_map.get(0, [])]
        crit_depth = (max(waves_map) + 1) if waves_map else 0
        return {
            "film_id": self.pkg.header.film_id,
            "total_generations": len(shots.generations),
            "accepted_count": len(accepted_ids),
            "remaining_count": len(remaining),
            "waves": waves,
            "ready_frontier": ready,
            "blocked_chains": blocked,
            "critical_path_depth": crit_depth,
        }

    def ready_generations(self) -> list[str]:
        return list(self.plan_waves()["ready_frontier"])
