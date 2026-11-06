"""Gate evaluation for a Production Package.

Skeleton level (P0-03): a gate BLOCKs while its stage file is missing or empty. A gate whose stage has
content stays NOT_RUN until a typed validator exists for that stage — a gate is never PASS unchecked.
Later phases register real validators with `register_validator`.
"""
from __future__ import annotations

from collections.abc import Callable
from typing import Any

from film_pipeline.core import ContractModel
from film_pipeline.production.package import GATE_NAMES, SCRIPT_FILE, STAGE_FILES, FilmPackage, GateState
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
_BUILTIN: dict[str, Validator] = {"1": story_issues}
# gate id -> reasons the Owner must decide even though the validator found no defect (-> OWNER_PENDING, never PASS)
_PENDING: dict[str, Validator] = {"1": story_pending}


def register_validator(gate_id: str, fn: Validator) -> None:
    """A registered validator returns issue strings; no issues -> PASS (it must really check)."""
    _VALIDATORS[gate_id] = fn


class GateResult(ContractModel):
    gate: str
    name: str
    status: GateState
    issues: list[str]


def _stage_issues(pkg: FilmPackage, gate_id: str) -> list[str]:
    out: list[str] = []
    for key in GATE_STAGES[gate_id]:
        if key in pkg.missing_stages:
            out.append(f"{key} missing")
        elif not pkg.stages.get(key):
            out.append(f"{key} empty")
    return out


def evaluate_gate(pkg: FilmPackage, gate_id: str) -> GateResult:
    issues = _stage_issues(pkg, gate_id)
    prefixes = tuple(STAGE_FILES[k] for k in GATE_STAGES[gate_id])
    if gate_id == "1":
        prefixes += (SCRIPT_FILE,)
        if pkg.header.profile == "drama" and pkg.script is not None and not pkg.script.scenes:
            issues.append(f"{SCRIPT_FILE} has no scenes")
    issues += [i for i in pkg.issues if i.startswith(prefixes)]
    status: GateState
    if issues:
        status = "BLOCK"
    elif gate_id in _VALIDATORS or gate_id in _BUILTIN:
        issues = (_VALIDATORS.get(gate_id) or _BUILTIN[gate_id])(pkg)
        status = "BLOCK" if issues else "PASS"
        if status == "PASS" and gate_id in _PENDING and gate_id not in _VALIDATORS:
            issues = _PENDING[gate_id](pkg)
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
