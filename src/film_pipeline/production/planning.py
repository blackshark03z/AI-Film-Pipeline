"""Production planning (G-planning): budget, schedule, risk register and legal/rights ledger, derived from the package.

Nothing here spends or sends anything; it answers "what will this cost, in what order, what can go wrong, and may we
use it" before Generate:

* ``budget``    generations x credits per generation x retake factor. The factors come from the three finished
                films' KPI ledgers (`tools/drama_write_film0N_kpi.py`, production credits only, investigation excluded):
                film01 168 credits / 10 planned, film02 84 / 6, film03 192 / 16, at 12 credits per charged generation
                (blocked jobs are refunded). Expected = mean retake factor, high = worst observed, cap = the header's
                `budget.cap_factor` x expected. `film.json budget.credits_estimate` is the Owner's number: below the
                expected cost it is a WARN, above the cap-adjusted high estimate it is just slack.
* ``schedule``  chains of hand-off generations (`previous_generation_id`) must run in order, chains are independent.
                Waves list the generations that can be in flight together; start stills come before their video
                (a chained generation may start from the previous take's end frame instead).
* ``risks``     every generation scored for what the AI route does badly: person-to-person CONTACT and prop HANDOVER are
                HIGH and need a fallback coverage plan in `03_preprod.risk_fallbacks[<generation_id>]` (else BLOCK
                ``RISK_NO_FALLBACK``); object handling, multi-speaker dialogue, crowds and deep hand-off chains are
                MEDIUM/LOW and only reported.
* ``legal``     `03_preprod.rights` entries (character / location / music / source / likeness / brand). Once any entry
                exists every character and location needs one (BLOCK ``RIGHTS_MISSING``); entries that are not
                `original`/`cleared` are Owner decisions (``pending``), never a PASS. No entries at all = ``not_declared``.

`planning_issues` returns the BLOCK strings, `planning_report` the full view `validate` and `film.py planning` show.
"""
from __future__ import annotations

import re
from statistics import mean
from typing import Any, Literal

from pydantic import Field

from film_pipeline.core import ContractModel

CREDITS_PER_GENERATION = 12.0  # film03: "19 charged x 12"; images are 0 credits (old Omni 1.1 history basis)
# the budget and retake estimates below keep this 1.1 basis; a single send is priced by `flow_credits`


def flow_credits(seconds: float) -> float:
    """Omni 1.2 Flash 360p, measured in Flow on 2026-11-08: 1 credit per second up to 10 s, 2 per second above
    (11 s = 12, 12 = 14, 13 = 16, 14 = 18, 15 = 20). Seconds are rounded up to a whole second."""
    s = max(0, -int(-seconds // 1))
    return float(s if s <= 10 else 10 + 2 * (s - 10))

# film -> (planned generations, production credits = credits_total - credits_investigation)
KPI_HISTORY: dict[str, tuple[int, float]] = {"film01_first_day": (10, 168.0), "film02_spare_key": (6, 84.0),
                                             "film03_front_desk": (16, 192.0)}
RETAKE_FACTORS = {film: credits / (planned * CREDITS_PER_GENERATION) for film, (planned, credits) in KPI_HISTORY.items()}
RightsKind = Literal["character", "location", "music", "source", "likeness", "brand"]
RightsStatus = Literal["original", "cleared", "pending", "restricted", "unknown"]
_RESOLVED = ("original", "cleared")

_CONTACT = re.compile(
    r"\b(shakes? hands?|handshake|hugs?|embrace[sd]?|grabs?|pushe?s?|shoves?|slaps?|strikes?|punche?s?|kisse?s?|touche?s?|"
    r"pulls?|drags?|carrie?s?|fights?|struggles?|takes (?:her|his|their|the) (?:hand|arm)|hands (?:him|her|them|it))\b")


class RightsEntry(ContractModel):
    subject: str = Field(min_length=1)  # "NORA", "lobby_morning", "none (room tone generated)", "script.fountain"
    kind: RightsKind
    status: RightsStatus
    evidence: str = ""  # where the clearance / originality is recorded
    note: str = ""


def _stage_text(decl: Any) -> str:
    choreo = decl.choreography
    return " ".join([p.description.lower() for p in choreo.phases] + [a.lower() for a in choreo.once_actions])


def _chains(shots: Any) -> list[list[str]]:
    """Generation ids grouped into hand-off chains, each in production order."""
    chains: list[list[str]] = []
    where: dict[str, int] = {}
    for g in shots.generations:
        if g.previous_generation_id in where:
            index = where[g.previous_generation_id]
            chains[index].append(g.generation_id)
        else:
            index = len(chains)
            chains.append([g.generation_id])
        where[g.generation_id] = index
    return chains


def budget(pkg: Any) -> dict[str, Any]:
    shots = pkg.typed.get("shots")
    count = len(shots.generations) if shots is not None else 0
    base = count * CREDITS_PER_GENERATION
    expected, high = base * mean(RETAKE_FACTORS.values()), base * max(RETAKE_FACTORS.values())
    header = pkg.header.budget
    out = {"generations": count, "credits_per_generation": CREDITS_PER_GENERATION,
           "retake_factor": {"mean": round(mean(RETAKE_FACTORS.values()), 3), "max": round(max(RETAKE_FACTORS.values()), 3),
                             "by_film": {k: round(v, 3) for k, v in RETAKE_FACTORS.items()}},
           "base_credits": round(base, 1), "expected_credits": round(expected, 1), "high_credits": round(high, 1),
           "cap_credits": round(expected * header.cap_factor, 1), "owner_estimate": header.credits_estimate,
           "owner_cap": header.credits_cap, "findings": []}
    if header.credits_estimate is None:
        out["findings"].append({"check": "BUDGET_NOT_SET", "severity": "WARN",
                                "detail": f"film.json budget.credits_estimate is empty; expected {out['expected_credits']}"})
    elif header.credits_estimate < expected:
        out["findings"].append({"check": "BUDGET_BELOW_EXPECTED", "severity": "WARN",
                                "detail": f"estimate {header.credits_estimate} < expected {out['expected_credits']} "
                                          f"({count} generations x {CREDITS_PER_GENERATION:g} x retake)"})
    return out


def schedule(pkg: Any) -> dict[str, Any]:
    shots = pkg.typed.get("shots")
    pre = pkg.typed.get("preprod")
    if shots is None:
        return {"chains": [], "waves": [], "critical_path": 0, "steps": []}
    chains = _chains(shots)
    waves = [[c[i] for c in chains if len(c) > i] for i in range(max((len(c) for c in chains), default=0))]
    steps = []
    if pre is not None:
        steps.append({"step": "character stills", "items": [f"char_{c}" for c in pre.characters]})
        steps.append({"step": "location plates", "items": [f"plate_{k}" for k in pre.locations]})
    heads = [c[0] for c in chains]
    steps.append({"step": "start stills for chain heads (free)", "items": [f"start_{g}" for g in heads]})
    steps.append({"step": "videos, each chain strictly in order; chained start frames come from the previous take",
                  "items": [g for wave in waves for g in wave]})
    return {"chains": [{"chain": c[0], "generations": c} for c in chains], "waves": waves,
            "critical_path": len(waves), "parallel_chains": len(chains), "steps": steps}


def risks(pkg: Any) -> list[dict[str, Any]]:
    shots, pre = pkg.typed.get("shots"), pkg.typed.get("preprod")
    if shots is None:
        return []
    fallbacks = pre.risk_fallbacks if pre is not None else {}
    depth: dict[str, int] = {}
    out: list[dict[str, Any]] = []

    def add(gid: str, kind: str, level: str, detail: str) -> None:
        out.append({"generation_id": gid, "kind": kind, "level": level, "detail": detail,
                    "fallback": fallbacks.get(gid, "")})

    for g in shots.generations:
        gid = g.generation_id
        depth[gid] = depth.get(g.previous_generation_id or "", 0) + 1
        text = _stage_text(g)
        hit = _CONTACT.search(text)
        if hit:
            add(gid, "CONTACT", "HIGH", f"physical contact in frame ({hit.group(0)!r})")
        start, end = pre.states.get(g.start_state) if pre else None, pre.states.get(g.end_state) if pre else None
        if start is not None and end is not None:
            holders = set(pre.characters)
            for key in sorted(set(start.props) & set(end.props)):
                a = {c for c in holders if c in start.props[key]}
                b = {c for c in holders if c in end.props[key]}
                if a and b and a != b:
                    add(gid, "HANDOVER", "HIGH", f"{key.rstrip(':')} passes from {', '.join(sorted(a))} to "
                                                  f"{', '.join(sorted(b))}")
            changed = [k.rstrip(':') for k in start.props if k in end.props and start.props[k] != end.props[k]]
            if changed:
                add(gid, "PROP_ACTION", "MEDIUM", f"prop state changes: {', '.join(changed)}")
        if len(g.visible) >= 3:
            add(gid, "CROWD", "MEDIUM", f"{len(g.visible)} characters in frame (identity swaps)")
        if depth[gid] >= 4:
            add(gid, "HANDOFF_DEPTH", "LOW", f"{depth[gid]}th generation of a hand-off chain (drift)")
    return out


def legal(pkg: Any) -> dict[str, Any]:
    pre = pkg.typed.get("preprod")
    entries = list(pre.rights) if pre is not None else []
    unresolved = [e for e in entries if e.status not in _RESOLVED]
    status = "not_declared" if not entries else ("pending" if unresolved else "clear")
    return {"status": status, "entries": [e.model_dump() for e in entries],
            "owner_decisions": [f"{e.kind} {e.subject}: {e.status}" for e in unresolved]}


def planning_issues(pkg: Any) -> list[str]:
    """BLOCK strings: a HIGH risk with no fallback plan, a character or location missing from a started rights ledger."""
    pre = pkg.typed.get("preprod")
    out = [f"RISK_NO_FALLBACK {r['generation_id']}: {r['kind']} ({r['detail']}) needs 03_preprod.risk_fallbacks"
           for r in risks(pkg) if r["level"] == "HIGH" and not r["fallback"].strip()]
    if pre is not None and pre.rights:
        covered = {(e.kind, e.subject) for e in pre.rights}
        out += [f"RIGHTS_MISSING character {c}: no entry in 03_preprod.rights" for c in pre.characters
                if ("character", c) not in covered]
        out += [f"RIGHTS_MISSING location {k}: no entry in 03_preprod.rights" for k in pre.locations
                if ("location", k) not in covered]
    from film_pipeline.production.sound_rights import sound_rights_issues
    return out + sound_rights_issues(pkg)


def planning_report(pkg: Any) -> dict[str, Any]:
    issues = planning_issues(pkg)
    register = risks(pkg)
    return {"ok": not issues, "issues": issues, "budget": budget(pkg), "schedule": schedule(pkg), "risks": register,
            "risk_summary": {lvl: sum(1 for r in register if r["level"] == lvl) for lvl in ("HIGH", "MEDIUM", "LOW")},
            "legal": legal(pkg)}
