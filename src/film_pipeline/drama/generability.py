"""Generability rating: can the video model (Omni 1.2 Flash) do this beat? GREEN / AMBER / RED per shot.

film04 lost ~14 h because beats the model cannot do passed every gate (docs/production/FILM04_SHOT_QUALITY_REVIEW.md
sections 2 and 4); 5 of 6 rejected takes failed on a rolling shutter: an articulated prop at a partial position, a pinned
prop that moved while a body moved near it, a body lowering its face into the fixed gap.

The rules are data (``RULES``): a regex over the lowercased phase description. A RED shot blocks the plan unless the
shot carries a ``generability_waiver`` (restage done, or the take was already accepted); then it is a WARN.
HOLD phases say what does not move, so they are not scanned.
"""
from __future__ import annotations

import re
from typing import Literal

from ..core import ContractModel
from .motion_library import MOTION_LIBRARY
from .preflight import PreflightIssue

Level = Literal["GREEN", "AMBER", "RED"]

# (rule id, level, regex over the lowercased description, reason)
RULES: tuple[tuple[str, str, str, str], ...] = (
    ("PARTIAL_MECHANISM", "RED",
     r"\b(?:pushes|pulls|raises|lowers|drags|rolls|slides|push|pull|raise|lower)\b[^.;,]{0,30}"
     r"\b(?:shutter|window|drawer|lid|blind)s?\b",
     "a mechanism that must stop at a partial position is not held (film04 SC01_g1 t2-t4, SC04_g2)"),
    ("BODY_INTO_FIXED_GAP", "RED",
     r"\b(?:stoops?|bends?|bent|crouch\w*|lowers?|sits?|sinks?|leans?)\b[^.;]{0,100}\b(?:face|head)\b"
     r"[^.;]{0,40}\b(?:gap|slot|hatch|opening)\b",
     "a body lowering its face into a fixed gap: the model moved the shutter, not the body (film04 SC01_g2, SC02_g1 v2)"),
    ("HANDS_SMALL_OBJECTS", "RED",
     r"\b(?:counts?|counting|sorts?|sorting|stacks?|squares?|shuffles?)\b[^.;]{0,25}\b(?:coins?|stacks?|tickets?|bills|notes)\b"
     r"|\bstamps (?:the|a|her|his)\b|\bdate stamp\b|\bstamping\b"
     r"|\b(?:takes? off|puts? on|removes?|slips? on|adjusts?|pushes? up)\b[^.;]{0,20}\b(?:glasses|spectacles)\b"
     r"|\b(?:turns?|inserts?|fumbles?|unlocks?)\b[^.;]{0,25}\bkeys?\b|\bkeys?\b[^.;]{0,25}\b(?:in|into) the lock\b"
     r"|\b(?:takes|tears|punches|folds)\b[^.;]{0,15}\btickets?\b"
     r"|\b(?:pen|pencil)\b[^.;]{0,20}\bwrit",
     "fingers handling small objects drift and merge (film04 SC04_g1, SC05_g1, SC05_g2)"),
    ("POURING", "RED",
     r"\b(?:pour|pours|poured|pouring|scatter|scatters|scattered|scattering)\b"
     r"|\b(?<!light )(?:spill|spills|spilled|spilling)\b"
     r"|\bdrips?\b(?! from| off)|\b(?:tips?|tilts?|empties)\b[^.;]{0,25}\b(?:into|onto)\b",
     "liquid and granular matter has no stable state (film04 SC04_g2)"),
    ("READABLE_TEXT", "RED",
     r"\b(?:reads?|writes?|writing)\b|\bsigns? (?:the|a|her|his)\b"
     r"|\b(?:label|sign|placard|notice)\b[^.;]{0,20}\b(?:reads|says|legible)\b",
     "text that must read is garbled by the model"),
    ("LOCOMOTION", "AMBER",
     r"\b(?:walks?|walking|hurries|hurry|steps?|stepping|strides?|runs?|enters)\b|\bcrosses (?!her|his|their)",
     "walking in or out drifts in look and path: plan 2 drafts"),
    ("PLACE_OBJECT", "AMBER",
     r"\b(?:sets?|puts?|places?|lays?)\b(?: down)? (?:the|a|an|her|his|it)\b|\bhands over\b|\bhands (?:him|her|them)\b"
     r"|\bpicks? up\b|\btakes (?:the|a|an|her|his|it)\b",
     "placing or taking an object: contact point and grip drift"),
    ("DOOR", "AMBER",
     r"\bdoors?\b[^.;]{0,25}\b(?:opens?|slides? open|slid open|swings?)\b|\b(?:opens?|pushes|pulls)\b[^.;]{0,20}\bdoors?\b",
     "a door that opens: the end position is not controlled"),
)

# a phase is a body action (not speech or looks) when one of these appears; used by TWO_PEOPLE_ACTION
_ACTION_VERBS = re.compile(
    r"\b(?:walks?|hurries|steps?|crosses|opens?|pushes|pulls|lifts|takes|sets|puts|places|hands|lays|reaches|grabs|picks"
    r"|turns (?:to|away)|stands up|sits|rises|embraces|touches|enters|runs|moves)\b")
_POSTURE = re.compile(r"\b(?:sits|stands|rises?) (?:down|up)\b|\b(?:sit|stand) (?:down|up)\b|\b(?:stoops?|bends|crouch\w*|kneels?)\b")
_BODY_TRAVEL = {"sit_down", "stand_up", "walk_across_room"}
_COMPILED = tuple((rid, lvl, re.compile(rx), why) for rid, lvl, rx, why in RULES)

DRAFTS = {"GREEN": 1, "AMBER": 2, "RED": 3}


class Finding(ContractModel):
    rule: str
    level: Literal["AMBER", "RED"]
    phase: str   # "a-b s"
    reason: str


class GenerabilityRating(ContractModel):
    generation_id: str
    level: Level
    findings: list[Finding]
    drafts: int
    waiver: str = ""


def rate_shot(decl) -> GenerabilityRating:
    """Rate one ShotDecl from its choreography phases, its tracked prop and who is visible."""
    findings: list[Finding] = []

    def add(rule: str, level: str, phase, reason: str) -> None:
        window = f"{phase.start_s:g}-{phase.end_s:g} s"
        if not any(f.rule == rule and f.phase == window for f in findings):
            findings.append(Finding(rule=rule, level=level, phase=window, reason=reason))  # type: ignore[arg-type]

    pinned = decl.tracked is not None and decl.tracked.direction == "still"
    phases = [p for p in decl.choreography.phases if p.kind != "HOLD"]
    for phase in phases:
        text = phase.description.lower()
        for rid, lvl, rx, why in _COMPILED:
            if rx.search(text):
                add(rid, lvl, phase, why)
        spec = MOTION_LIBRARY.get(phase.motion) if phase.motion else None
        if spec is not None and spec.stop == "mid_travel":
            add("PARTIAL_MECHANISM", "RED", phase, f"motion {phase.motion} stops mid-travel (film04 SC01_g1 t2-t4)")
        if phase.motion == "open_door":
            add("DOOR", "AMBER", phase, "a door that opens: the end position is not controlled")
        if phase.motion == "walk_across_room":
            add("LOCOMOTION", "AMBER", phase, "walking in or out drifts in look and path: plan 2 drafts")
        if phase.motion in ("pick_up_small_object", "put_down_small_object", "hand_over_object"):
            add("PLACE_OBJECT", "AMBER", phase, "placing or taking an object: contact point and grip drift")
        body_moves = phase.motion in _BODY_TRAVEL or bool(_POSTURE.search(text))
        if pinned and body_moves:
            add("BODY_VS_PINNED_PROP", "RED", phase,
                f"a body moves while {decl.tracked.object} must not (film04 SC02_g1 v2 t1/t2)")
        elif body_moves and (phase.motion in ("sit_down", "stand_up") or _POSTURE.search(text)):
            add("POSTURE_CHANGE", "AMBER", phase, "sitting down or standing up changes the whole pose: plan 2 drafts")
        if len(decl.visible) >= 2 and phase.kind in ("ACTION", "CONSEQUENCE") and \
                (_ACTION_VERBS.search(text) or phase.motion):
            add("TWO_PEOPLE_ACTION", "AMBER", phase, "two people in frame and a body action: plan 2 drafts")
    level: Level = ("RED" if any(f.level == "RED" for f in findings)
                    else "AMBER" if findings else "GREEN")
    waiver = (getattr(decl, "generability_waiver", "") or "").strip()
    return GenerabilityRating(generation_id=decl.generation_id, level=level, findings=findings,
                              drafts=DRAFTS[level], waiver=waiver)


def generability_issues(decl) -> tuple[GenerabilityRating, list[PreflightIssue]]:
    """gate3 issues: RED without a waiver BLOCKs, RED with one and AMBER WARN; GREEN says nothing."""
    rating = rate_shot(decl)
    if rating.level == "GREEN":
        return rating, []
    rules = ", ".join(f"{f.rule} ({f.phase})" for f in rating.findings if f.level == rating.level)
    if rating.level == "RED":
        if rating.waiver:
            issue = PreflightIssue(check="GENERABILITY_RED_WAIVED", severity="WARN",
                                   detail=f"{rules}; waiver: {rating.waiver}")
        else:
            issue = PreflightIssue(
                check="GENERABILITY_RED", severity="BLOCK",
                detail=f"{rules}; restage (cut around it, prop-only insert, off screen + sound, prop out of frame) "
                       "or set generability_waiver")
    else:
        issue = PreflightIssue(check="GENERABILITY_AMBER", severity="WARN",
                               detail=f"{rules}; plan {rating.drafts} drafts")
    return rating, [issue]
