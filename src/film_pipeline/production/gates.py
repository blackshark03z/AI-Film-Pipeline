"""Gate evaluation for a Production Package.

Skeleton level (P0-03): a gate BLOCKs while its stage file is missing or empty. A gate whose stage has
content stays NOT_RUN until a typed validator exists for that stage — a gate is never PASS unchecked.
Later phases register real validators with `register_validator`.
"""
from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from typing import Any

from film_pipeline.core import ContractModel
from film_pipeline.production.package import GATE_NAMES, SCRIPT_FILE, STAGE_FILES, FilmPackage, GateState
from film_pipeline.production.runtime import atomic_json
from film_pipeline.production.direction import direction_issues
from film_pipeline.production.narration import narration_direction_issues, narration_pending, narration_story_issues
from film_pipeline.production.story import story_issues, story_pending

# gate id -> stage keys that must have content before the gate can be evaluated
GATE_STAGES: dict[str, tuple[str, ...]] = {
    "1": ("story",),
    "2": ("direction",),
    "3": ("preprod",),
    "4": ("shots",),
    "5": ("edit",),
    "6": ("post", "delivery"),
}

Validator = Callable[[FilmPackage], list[str]]
_VALIDATORS: dict[str, Validator] = {}  # overrides (tests, experiments); built-ins below are not cleared with them


def _by_profile(drama: Validator, narration: Validator) -> Validator:
    return lambda pkg: narration(pkg) if pkg.header.profile == "narration" else drama(pkg)


_BUILTIN: dict[str, Validator] = {
    "1": _by_profile(story_issues, narration_story_issues),
    "2": _by_profile(direction_issues, narration_direction_issues),
}
# gate id -> reasons the Owner must decide even though the validator found no defect (-> OWNER_PENDING, never PASS)
_PENDING: dict[str, Validator] = {"1": _by_profile(story_pending, narration_pending)}


def _picture_lock(pkg: FilmPackage) -> list[str]:
    from film_pipeline.production.lock import picture_lock_issues
    return picture_lock_issues(pkg)


def _checks(name: str) -> Validator:
    def run(pkg: FilmPackage) -> list[str]:
        from film_pipeline.production import gate_checks
        return getattr(gate_checks, name)(pkg)
    return run


# gates 3, 4 and 6 read evidence on disk (plan record, take log + reviews, delivery archive); drama profile only
_DRAMA_ONLY: dict[str, tuple[Validator, Validator]] = {
    "3": (_checks("plan_issues"), _checks("plan_pending")),
    "4": (_checks("take_issues"), _checks("take_pending")),
    "6": (_checks("master_issues"), _checks("master_pending")),
}


def _builtin(pkg: FilmPackage, gate_id: str) -> Validator | None:
    """Built-in validator for a gate; gate 5 (picture lock) exists for the drama profile only."""
    if gate_id == "5":
        return _picture_lock if pkg.header.profile == "drama" else None
    if gate_id in _DRAMA_ONLY:
        return _DRAMA_ONLY[gate_id][0] if pkg.header.profile == "drama" else None
    return _BUILTIN.get(gate_id)


def _pending(pkg: FilmPackage, gate_id: str) -> Validator | None:
    if gate_id in _DRAMA_ONLY:
        return _DRAMA_ONLY[gate_id][1] if pkg.header.profile == "drama" else None
    return _PENDING.get(gate_id)


def register_validator(gate_id: str, fn: Validator) -> None:
    """A registered validator returns issue strings; no issues -> PASS (it must really check)."""
    _VALIDATORS[gate_id] = fn


class GateResult(ContractModel):
    gate: str
    name: str
    status: GateState
    issues: list[str]


def _gate_stages(pkg: FilmPackage, gate_id: str) -> tuple[str, ...]:
    # a narration film's director-level plan is its shot list (the E2E plan), not a 02_direction.json
    if pkg.header.profile == "narration" and gate_id == "2":
        return ("shots",)
    return GATE_STAGES[gate_id]


def _stage_issues(pkg: FilmPackage, gate_id: str) -> list[str]:
    out: list[str] = []
    for key in _gate_stages(pkg, gate_id):
        if key in pkg.missing_stages:
            out.append(f"{key} missing")
        elif not pkg.stages.get(key):
            out.append(f"{key} empty")
    return out


def evaluate_gate(pkg: FilmPackage, gate_id: str) -> GateResult:
    issues = _stage_issues(pkg, gate_id)
    prefixes = tuple(STAGE_FILES[k] for k in _gate_stages(pkg, gate_id))
    if gate_id == "1":
        prefixes += (SCRIPT_FILE,)
        if pkg.header.profile == "drama" and pkg.script is not None and not pkg.script.scenes:
            issues.append(f"{SCRIPT_FILE} has no scenes")
    issues += [i for i in pkg.issues if i.startswith(prefixes)]
    status: GateState
    if issues:
        status = "BLOCK"
    elif gate_id in _VALIDATORS or _builtin(pkg, gate_id) is not None:
        issues = (_VALIDATORS.get(gate_id) or _builtin(pkg, gate_id))(pkg)
        status = "BLOCK" if issues else "PASS"
        pending = _pending(pkg, gate_id)
        if status == "PASS" and pending is not None and gate_id not in _VALIDATORS:
            issues = pending(pkg)
            status = "OWNER_PENDING" if issues else "PASS"
    else:
        status = "NOT_RUN"
        issues = ["no validator registered; stage present but unchecked"]
    return GateResult(gate=gate_id, name=GATE_NAMES[gate_id], status=status, issues=issues)


def evaluate_gates(pkg: FilmPackage) -> list[GateResult]:
    return [evaluate_gate(pkg, g) for g in GATE_NAMES]


def summary(results: list[GateResult]) -> dict[str, Any]:
    return {
        "gates": {r.gate: {"name": r.name, "status": r.status, "issues": r.issues} for r in results},
        "blocked": any(r.status == "BLOCK" for r in results),
    }


def _archive_locked_for_sync(root: Path) -> bool:
    import json
    from film_pipeline.production import deliver as dl_mod
    dpath = root / "07_delivery.json"
    if dpath.is_file():
        try:
            data = json.loads(dpath.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            data = {}
        delivery = data.get("delivery") if isinstance(data, dict) else None
        if isinstance(delivery, dict) and delivery.get("owner_acceptance"):
            return True
    try:
        arch = dl_mod.current_archive(root)
    except (OSError, ValueError):
        return False
    return (arch / dl_mod.MANIFEST).is_file() and bool(dl_mod.verify_archive(arch).get("ok"))


def sync_header_gates(
    pkg: FilmPackage,
    results: list[GateResult] | None = None,
    *,
    force: bool = False,
    gate6_override: GateState | None = None,
) -> dict[str, str]:
    """Synchronize ``film.json['gates']`` from evaluated gates.

    Preserves existing verified delivery archives unless ``force=True``.
    """
    import json
    root = Path(pkg.root)
    if not force and _archive_locked_for_sync(root):
        return {k: str(v) for k, v in pkg.header.gates.items()}
    evaluated = results if results is not None else evaluate_gates(pkg)
    desired: dict[str, str] = {r.gate: r.status for r in evaluated}
    if gate6_override is not None:
        desired["6"] = gate6_override
    film_path = root / "film.json"
    raw = json.loads(film_path.read_text(encoding="utf-8"))
    if raw.get("gates") != desired:
        raw["gates"] = desired
        atomic_json(film_path, raw)
    return desired
