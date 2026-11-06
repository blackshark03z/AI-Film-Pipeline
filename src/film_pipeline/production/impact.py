"""Change impact (G13): what must be redone when one versioned design changes.

`affected_by(pkg, design_id)` returns the shots that depend on the design (owners in frame, the location,
props named in continuity states — the same rule that makes a stale `id@version` pin a package issue), the stills
to redo, the takes to re-render (direct shots plus every later generation that hands off from one of them), and the
items of the still-untyped edit / post / delivery stages that point at those generations.
"""
from __future__ import annotations

from typing import Any

from film_pipeline.core import ContractModel
from film_pipeline.production.sections import DesignKind, shot_design_ids

_ID_KEYS = ("generation_id", "shot_id")
_CHARACTER_KINDS = ("look", "costume", "hair_makeup")


class Impact(ContractModel):
    design: str
    kind: DesignKind
    version: int
    shots: list[str]  # direct dependents, production order
    stills: list[str]  # still names under stills/ (char_*, plate_*, start_*) to redo
    takes: list[str]  # generations to re-render: shots + handoff cascade, production order
    edit_items: list[str]  # "edit:<path>" nodes of 05_edit.json that reference an affected generation
    post_items: list[str]  # "post:<path>" / "delivery:<path>" likewise


def _hits(node: Any, ids: set[str], path: str, out: list[str]) -> None:
    if isinstance(node, dict):
        if any(isinstance(node.get(k), str) and node[k] in ids for k in _ID_KEYS):
            out.append(path)
        for key, value in node.items():
            _hits(value, ids, f"{path}.{key}" if path else str(key), out)
    elif isinstance(node, list):
        for index, value in enumerate(node):
            _hits(value, ids, f"{path}[{index}]", out)


def _stage_hits(pkg, stage: str, ids: set[str]) -> list[str]:
    found: list[str] = []
    _hits(pkg.stages.get(stage) or {}, ids, "", found)
    return [f"{stage}:{p or '.'}" for p in found]


def affected_by(pkg, design_id: str) -> Impact:
    pre, shots = pkg.typed.get("preprod"), pkg.typed.get("shots")
    if pre is None or shots is None:
        raise ValueError("impact needs a valid 03_preprod.json and 04_shots.json")
    design = pre.designs.get(design_id)
    if design is None:
        raise ValueError(f"unknown design {design_id!r}; known: {sorted(pre.designs)}")
    order = [g.generation_id for g in shots.generations]
    direct = [g.generation_id for g in shots.generations if design_id in shot_design_ids(pre, g)]

    cascade = set(direct)
    for g in shots.generations:  # predecessors always come earlier, so one forward pass closes the chain
        if g.previous_generation_id in cascade:
            cascade.add(g.generation_id)
    takes = [gid for gid in order if gid in cascade]

    stills = [f"start_{gid}" for gid in direct]
    if design.kind in _CHARACTER_KINDS:
        stills.insert(0, f"char_{design.owner}")
    elif design.kind == "location":
        stills.insert(0, f"plate_{design.owner}")
    return Impact(design=design_id, kind=design.kind, version=design.version, shots=direct, stills=stills,
                  takes=takes, edit_items=_stage_hits(pkg, "edit", cascade),
                  post_items=_stage_hits(pkg, "post", cascade) + _stage_hits(pkg, "delivery", cascade))
