"""Topological handoff-wave DAG scheduler over `04_shots.json` and `takes/index.json`."""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
import json
from pathlib import Path
from typing import Any

from film_pipeline.production.ffjoin import render_workers
from film_pipeline.production.package import load_package
from film_pipeline.production.recovery import pending_receipts
from film_pipeline.production.runtime import atomic_json
from film_pipeline.production.takes import load_log, sha256_file


def hash_files_parallel(paths: list[Path], *, jobs: int | None = None) -> dict[Path, str]:
    """Compute SHA-256 digests for distinct existing files using bounded worker threads."""
    unique = [p for p in dict.fromkeys(paths) if p.is_file()]
    if not unique:
        return {}
    workers = render_workers(jobs)
    if len(unique) > 1 and workers > 1:
        with ThreadPoolExecutor(max_workers=workers) as pool:
            digests = list(pool.map(sha256_file, unique))
    else:
        digests = [sha256_file(p) for p in unique]
    return dict(zip(unique, digests))


class WaveDAGScheduler:
    """Computes parallel dispatch waves without splitting worktrees."""

    def __init__(
        self,
        pkg: Any,
        *,
        optimistic_lookahead: int = 0,
        verified_hashes: dict[Path, str] | None = None,
    ) -> None:
        self.pkg = pkg
        self.optimistic_lookahead = max(0, int(optimistic_lookahead))
        self.verified_hashes = verified_hashes

    def _clip_digest(self, clip: Path, cache: dict[Path, str]) -> str:
        if clip not in cache:
            cache[clip] = sha256_file(clip)
        return cache[clip]

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

        def _resolve_clip_path(output_file: str) -> Path:
            cand = root / "media" / "takes" / Path(output_file).name
            return cand if cand.is_file() else (root / "media" / "takes" / output_file)

        if self.verified_hashes is not None:
            hash_cache = dict(self.verified_hashes)
        else:
            to_hash = [
                _resolve_clip_path(t.output_file)
                for t in log.takes
                if t.output_sha256 and t.status in ("ACCEPTED", "GENERATED")
                and t.shot_version == getattr(by_id.get(t.generation_id), "version", None)
            ]
            hash_cache = hash_files_parallel(to_hash)

        accepted_ids: set[str] = set()
        unverified_accepted: list[str] = []
        for t in log.takes:
            if t.status != "ACCEPTED" or t.shot_version != getattr(by_id.get(t.generation_id), "version", None):
                continue
            review_missing = bool(t.review_file) and not (
                (root / "takes" / t.review_file).is_file() or (root / t.review_file).is_file()
            )
            clip = _resolve_clip_path(t.output_file)
            clip_present = clip.is_file()
            clip_corrupt = clip_present and bool(t.output_sha256) and self._clip_digest(clip, hash_cache) != t.output_sha256
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
            if getattr(decl, "independent_still", False):
                wave_of[gid] = 0
                return 0
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

        speculative_frontier: list[str] = []
        if self.optimistic_lookahead > 0:
            blocked_ids = {b["generation_id"] for b in blocked}
            ready_set = set(ready)
            speculative_base: set[str] = set()
            for t in log.takes:
                if t.status != "GENERATED" or t.shot_version != getattr(by_id.get(t.generation_id), "version", None):
                    continue
                clip = _resolve_clip_path(t.output_file)
                if not clip.is_file():
                    continue
                if t.output_sha256 and self._clip_digest(clip, hash_cache) != t.output_sha256:
                    continue
                triage_candidates = (
                    root / "media" / "triage" / f"{t.take_id}.json",
                    root / "takes" / "triage" / f"{t.take_id}.json",
                )
                flagged = False
                for triage_file in triage_candidates:
                    if not triage_file.is_file():
                        continue
                    try:
                        triage_doc = json.loads(triage_file.read_text(encoding="utf-8"))
                        if triage_doc.get("warnings") or triage_doc.get("flags"):
                            flagged = True
                            break
                    except (OSError, ValueError):
                        flagged = True
                        break
                if flagged:
                    continue
                speculative_base.add(t.generation_id)

            frontier_done = set(accepted_ids) | speculative_base
            seen_spec: set[str] = set()
            for _ in range(self.optimistic_lookahead):
                hop_added: list[str] = []
                for g in remaining:
                    gid = g.generation_id
                    if gid in ready_set or gid in seen_spec or gid in pending_set or gid in blocked_ids:
                        continue
                    prev = g.previous_generation_id
                    if prev and prev in frontier_done and gid not in speculative_base:
                        hop_added.append(gid)
                        seen_spec.add(gid)
                speculative_frontier.extend(hop_added)
                frontier_done.update(hop_added)
                if not hop_added:
                    break

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
            "speculative_frontier": speculative_frontier,
            "blocked_chains": blocked,
            "critical_path_depth": crit_depth,
        }

    def ready_generations(self) -> list[str]:
        return list(self.plan_waves()["ready_frontier"])


def suggest_setup_anchors(
    pkg: Any,
    *,
    max_chain_depth: int = 4,
    apply: bool = False,
) -> dict[str, Any]:
    """Identify safe mid-chain generations to anchor to independent start stills to flatten deep sequential DAGs."""
    shots = pkg.typed.get("shots")
    pre = pkg.typed.get("preprod")
    if shots is None:
        raise ValueError("suggest_setup_anchors requires a valid 04_shots.json")

    limit = max(2, int(max_chain_depth))
    before = WaveDAGScheduler(pkg).plan_waves()
    by_id = {g.generation_id: g for g in shots.generations}
    states = pre.states if pre is not None else {}
    stills = pre.stills if pre is not None else {}

    chain_depth: dict[str, int] = {}
    chosen: list[dict[str, Any]] = []
    chosen_ids: set[str] = set()

    for decl in shots.generations:
        gid = decl.generation_id
        prev_id = decl.previous_generation_id
        if not prev_id or getattr(decl, "independent_still", False) or prev_id not in by_id:
            chain_depth[gid] = 1
            continue
        prev_decl = by_id[prev_id]
        depth_here = chain_depth.get(prev_id, 1) + 1
        if depth_here <= limit:
            chain_depth[gid] = depth_here
            continue

        prev_end = states.get(prev_decl.end_state)
        cur_start = states.get(decl.start_state)
        steady_props = bool(prev_end and cur_start and prev_end.props == cur_start.props)
        has_approved_still = bool(stills.get(gid) and stills[gid].approved_by)
        if has_approved_still:
            reason = "approved_start_still_available"
        elif decl.coverage == "SINGLE" and steady_props:
            reason = "single_coverage_steady_props"
        elif steady_props:
            reason = "steady_props_chain_break"
        else:
            reason = "chain_depth_cap"

        chosen_ids.add(gid)
        chain_depth[gid] = 1
        chosen.append({
            "generation_id": gid,
            "scene_id": decl.scene_id,
            "previous_generation_id": prev_id,
            "coverage": decl.coverage,
            "reason": reason,
        })

    if apply and chosen_ids:
        shots_path = Path(pkg.root) / "04_shots.json"
        raw = json.loads(shots_path.read_text(encoding="utf-8"))
        for g in raw.get("generations", []):
            if g.get("generation_id") in chosen_ids:
                g["independent_still"] = True
        atomic_json(shots_path, raw)
        pkg_after = load_package(pkg.root)
    else:
        sim_gens = [
            g.model_copy(update={"independent_still": True}) if g.generation_id in chosen_ids else g
            for g in shots.generations
        ]
        sim_shots = shots.model_copy(update={"generations": sim_gens})
        pkg_after = pkg.model_copy(update={"typed": {**pkg.typed, "shots": sim_shots}})

    after = WaveDAGScheduler(pkg_after).plan_waves()
    return {
        "film_id": pkg.header.film_id,
        "max_chain_depth": limit,
        "applied": apply,
        "anchor_count": len(chosen),
        "anchors": chosen,
        "wave0_before": len(before["ready_frontier"]),
        "wave0_after": len(after["ready_frontier"]),
        "critical_path_before": before["critical_path_depth"],
        "critical_path_after": after["critical_path_depth"],
    }
