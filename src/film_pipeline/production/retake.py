"""Retake and pickup policy: what to do after a take is REJECTED (categories 83, 135 and the retake loop).

A rejected take carries a cause (`qc_model.Cause`, set by the human reviewer): PROMPT, START_FRAME, PROVIDER_LIMIT or
STAGING. Per generation, looking only at the takes of its *current* shot version, `retake_plan` answers:

* ``DONE``             a take of this version is ACCEPTED
* ``AWAITING_REVIEW``  the newest take is still GENERATED / INCOMPLETE - nothing to decide yet
* ``CLASSIFY``         the newest rejected take has no cause; the reviewer must name one first
* ``RETRY``            the first failure for that cause: the cheap fix for that cause, then render again
* ``CHANGE_APPROACH``  the same cause failed twice: a retry is the same bet, so the shot itself must change
                       (split, re-stage, insert / reaction coverage, different start frame)
* ``ESCALATE``         three rejections in one version, or the third version also failing: Owner decision (accept with
                       a waiver, drop or rewrite the shot) - the policy never spends credits past that on its own

Credits already spent and the cost of one more render are reported with every decision. A chained generation lists the
generations downstream of it, whose start frame comes from this take's end frame and must be re-verified after a change.

`start_version` / `apply_pickup` feed a decision back into `04_shots.json`: the current declaration moves to
``history`` verbatim and the shot is replaced in place by version N+1 (same generation_id, so states, take ids and
risk fallbacks keep working) with ``repair_of`` / ``repair_reason`` filled in. The caller supplies the edits - the policy
suggests, a director decides what the new staging is. Only a shot with a rejected take in its current version can be
re-versioned.
"""
from __future__ import annotations

import copy
import json
from pathlib import Path
from typing import Any, Literal

from pydantic import Field

from film_pipeline.core import ContractModel
from film_pipeline.production.planning import CREDITS_PER_GENERATION
from film_pipeline.production.sections import ShotsSection
from film_pipeline.production.takes import TakeLog, load_log

Action = Literal["DONE", "AWAITING_REVIEW", "CLASSIFY", "RETRY", "CHANGE_APPROACH", "ESCALATE"]
OPEN_ACTIONS = ("CLASSIFY", "RETRY", "CHANGE_APPROACH", "ESCALATE")

FIRST_FIX = {
    "PROMPT": "Rewrite the prompt for what failed (say it in plain words, one action per sentence), then render again.",
    "START_FRAME": "Regenerate the start still (check pose, face, set against the planned start state), then render again.",
    "PROVIDER_LIMIT": "Render once more unchanged - provider failures can be transient - and note if it repeats.",
    "STAGING": "Simplify the choreography phase that failed (fewer movers, one action at a time), then render again.",
}
CHANGE_OPTIONS = {
    "PROMPT": ["split the shot into two shorter generations, one beat each",
               "cut the failing beat and cover it with a reaction or insert"],
    "START_FRAME": ["use a different start frame (other pose, angle or crop)",
                    "start from a clean character still instead of the chained end frame"],
    "PROVIDER_LIMIT": ["avoid the behaviour on screen: cover it with an insert, reaction or off-screen action",
                       "isolate the limited element in its own short generation"],
    "STAGING": ["re-stage the blocking (different positions or business)",
                "replace the full action with insert / reaction coverage"],
}
_PROTECTED = {"generation_id", "version", "repair_of", "repair_reason"}


class RetakePolicy(ContractModel):
    same_cause_limit: int = Field(default=2, ge=2)  # this many rejections for one cause => change approach
    rejected_per_version_limit: int = Field(default=3, ge=2)  # this many in one version => escalate to the Owner
    max_versions: int = Field(default=3, ge=2)  # a failing shot at this version => escalate
    credits_per_render: float = CREDITS_PER_GENERATION


def _downstream(shots: ShotsSection, gid: str) -> list[str]:
    found: list[str] = []
    frontier = [gid]
    while frontier:
        nxt = [g.generation_id for g in shots.generations if g.previous_generation_id in frontier]
        found += nxt
        frontier = nxt
    return found


def retake_plan(log: TakeLog, shots: ShotsSection, policy: RetakePolicy | None = None) -> list[dict[str, Any]]:
    policy = policy or RetakePolicy()
    plan: list[dict[str, Any]] = []
    for decl in shots.generations:
        gid = decl.generation_id
        every = log.for_generation(gid)
        if not every:
            continue  # never rendered: nothing to decide
        current = [t for t in every if t.shot_version == decl.version]
        rejected = [t for t in current if t.status == "REJECTED"]
        spent = sum(t.credits for t in every)
        row: dict[str, Any] = {"generation_id": gid, "shot_version": decl.version, "takes": [t.take_id for t in every],
                               "rejected_in_version": len(rejected), "credits_spent": spent, "cause": "",
                               "next_render_credits": policy.credits_per_render, "options": [], "downstream": []}
        if any(t.status == "ACCEPTED" for t in current):
            row.update(action="DONE", reason="a take of this version is accepted")
        elif current and current[-1].status in ("GENERATED", "INCOMPLETE"):
            row.update(action="AWAITING_REVIEW", reason=f"{current[-1].take_id} is {current[-1].status}")
        elif not rejected:
            row.update(action="AWAITING_REVIEW", reason="no take of this version yet")
        else:
            last = rejected[-1]
            row["cause"] = last.cause
            if not last.cause:
                row.update(action="CLASSIFY", reason=f"{last.take_id} was rejected without a cause "
                                                     "(PROMPT / START_FRAME / PROVIDER_LIMIT / STAGING)")
            elif len(rejected) >= policy.rejected_per_version_limit or (
                    decl.version >= policy.max_versions and len(rejected) >= policy.same_cause_limit):
                row.update(action="ESCALATE", options=["accept the best take with a written waiver",
                                                       "rewrite or drop the shot in the script", "spend more credits"],
                           reason=f"{len(rejected)} rejected takes in version {decl.version} "
                                  f"({spent:g} credits spent in total) - the Owner decides")
            elif sum(1 for t in rejected if t.cause == last.cause) >= policy.same_cause_limit:
                row.update(action="CHANGE_APPROACH", options=CHANGE_OPTIONS[last.cause],
                           reason=f"{last.cause} failed {sum(1 for t in rejected if t.cause == last.cause)} times - "
                                  "retrying repeats the same bet")
            else:
                row.update(action="RETRY", options=[FIRST_FIX[last.cause]],
                           reason=f"first {last.cause} failure of version {decl.version}")
            row["downstream"] = _downstream(shots, gid)
        plan.append(row)
    return plan


def pickup_list(plan: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [r for r in plan if r["action"] in OPEN_ACTIONS]


def retake_report(log: TakeLog, shots: ShotsSection, policy: RetakePolicy | None = None) -> dict[str, Any]:
    plan = retake_plan(log, shots, policy)
    pickups = pickup_list(plan)
    return {"ok": not pickups, "plan": plan, "pickups": pickups,
            "credits_spent": sum(t.credits for t in log.takes),
            "counts": {a: sum(1 for r in plan if r["action"] == a)
                       for a in ("DONE", "AWAITING_REVIEW", "CLASSIFY", "RETRY", "CHANGE_APPROACH", "ESCALATE")}}


def start_version(shots_raw: dict[str, Any], log: TakeLog, generation_id: str, reason: str,
                  edits: dict[str, Any]) -> dict[str, Any]:
    """New `04_shots.json` content with `generation_id` replaced by its next version (the old one moves to history)."""
    if not reason.strip():
        raise ValueError("a pickup needs a written reason")
    bad = sorted(set(edits) & _PROTECTED)
    if bad:
        raise ValueError(f"edits may not set {bad} (the policy owns the version fields)")
    if not edits:
        raise ValueError("a new version must change something - give the edits")
    raw = copy.deepcopy(shots_raw)
    index = next((i for i, g in enumerate(raw["generations"]) if g["generation_id"] == generation_id), None)
    if index is None:
        raise ValueError(f"unknown generation {generation_id!r}")
    old = raw["generations"][index]
    version = int(old.get("version", 1))
    if not any(t.status == "REJECTED" and t.shot_version == version for t in log.for_generation(generation_id)):
        raise ValueError(f"{generation_id} v{version} has no rejected take - nothing to repair")
    new = {**old, **edits, "version": version + 1, "repair_of": f"{generation_id}@v{version}",
           "repair_reason": reason.strip()}
    if isinstance(edits.get("choreography"), dict):
        new["choreography"] = {**edits["choreography"], "generation_id": generation_id}
    raw.setdefault("history", []).append(old)
    raw["generations"][index] = new
    ShotsSection.model_validate(raw)  # the result must still be a valid shots section
    return raw


def apply_pickup(film_root: Path, film_id: str, generation_id: str, reason: str, edits: dict[str, Any]) -> dict[str, Any]:
    path = Path(film_root) / "04_shots.json"
    raw = json.loads(path.read_text(encoding="utf-8"))
    updated = start_version(raw, load_log(film_root, film_id), generation_id, reason, edits)
    path.write_text(json.dumps(updated, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    new = next(g for g in updated["generations"] if g["generation_id"] == generation_id)
    return {"generation_id": generation_id, "version": new["version"], "repair_of": new["repair_of"],
            "file": str(path)}
