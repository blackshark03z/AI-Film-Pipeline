"""Generability rating: can the video model (Omni 1.2 Flash) do this beat? GREEN / AMBER / RED per shot.

film04 lost ~14 h because beats the model cannot do passed every gate (docs/production/FILM04_SHOT_QUALITY_REVIEW.md
sections 2 and 4); 5 of 6 rejected takes failed on a rolling shutter: an articulated prop at a partial position, a pinned
prop that moved while a body moved near it, a body lowering its face into the fixed gap.

The rules are data (``RULES``): a regex over the lowercased phase description. Levels GREEN / AMBER / RED / UNKNOWN,
aggregated RED > UNKNOWN > AMBER > GREEN. GREEN needs a positive match: every ACTION phase must hit a ``SUPPORTED``
family (or a rule); an ACTION that matches nothing makes the shot UNKNOWN (finding UNMATCHED_ACTION).

A RED shot blocks the plan unless the shot reuses an Owner-accepted take (``accepted_take_reuse``) or carries a
``generability_exception`` for its current version (both WARN here; the exception's prompt hash, expiry and budget are
checked at generate time). The legacy free-text ``generability_waiver`` demotes nothing. HOLD phases say what does not
move, so only the constraint rules (``HOLD_RULES``: a held state, e.g. a mechanism at a partial position) scan them.
"""
from __future__ import annotations

import re
from typing import Literal

from ..core import ContractModel
from .motion_library import MOTION_LIBRARY
from .preflight import PreflightIssue

Level = Literal["GREEN", "AMBER", "RED", "UNKNOWN"]

# (rule id, level, regex over the lowercased description, reason)
RULES: tuple[tuple[str, str, str, str], ...] = (
    ("PARTIAL_MECHANISM", "RED",
     r"\b(?:pushes|pulls|raises|lowers|drags|rolls|slides|push|pull|raise|lower)\b[^.;,]{0,30}"
     r"\b(?:shutter|window|drawer|lid|blind)s?\b"
     r"|\b(?:half|partly|partially|halfway|part-way)\b[- ]?\w*\b[^.;,]{0,20}\b(?:shutter|window|drawer|lid|blind)s?\b"
     r"|\b(?:shutter|window|drawer|lid|blind)s?\b[^.;,]{0,25}\b(?:half|partly|partially|halfway|part-way)\b",
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

# rules that describe a held state, so they also scan HOLD phases (everything else describes a motion)
HOLD_RULES = frozenset({"PARTIAL_MECHANISM", "READABLE_TEXT"})

# actions the model does reliably at a stable setup: an ACTION phase hitting one of these (and no AMBER/RED rule) is GREEN
SUPPORTED: tuple[tuple[str, str], ...] = (
    ("SPEAK", r"\b(?:speaks?|speaking|says?|saying|asks?|asking|replies|answers?|whispers?|murmurs?|tells?|talks?|talking)\b"),
    ("LOOK", r"\b(?:glances?|glancing|looks?|looking|gazes?|stares?|watches)\b"
             r"|\bturns? (?:her |his |their |the )?(?:head|face|gaze|eyes)\b"),
    ("STILL", r"\bholds? (?:a |the |her |his )?(?:look|gaze|stare|still|stillness|pose|beat)\b"
              r"|\b(?:stands|stays|remains|waits|pauses|freezes)\b(?! up)"),
    ("NOD", r"\bnods?\b|\bshakes? (?:her|his) head\b"),
    ("BREATHE", r"\b(?:breathes?|sighs?|exhales?|inhales?)\b"),
    ("FACE", r"\b(?:blinks?|smiles?|frowns?|swallows?)\b"),
    ("GESTURE", r"\b(?:gestures?|shrugs?|(?:crosses|folds) (?:her|his|their) arms)\b"),
)
_SUPPORTED = tuple(re.compile(rx) for _, rx in SUPPORTED)
_SUPPORTED_MOTIONS = frozenset({"turn_head", "glance"})

# a phase is a body action (not speech or looks) when one of these appears; used by TWO_PEOPLE_ACTION
_ACTION_VERBS = re.compile(
    r"\b(?:walks?|hurries|steps?|crosses|opens?|pushes|pulls|lifts|takes|sets|puts|places|hands|lays|reaches|grabs|picks"
    r"|turns (?:to|away)|stands up|sits|rises|embraces|touches|enters|runs|moves)\b")
_POSTURE = re.compile(r"\b(?:sits|stands|rises?) (?:down|up)\b|\b(?:sit|stand) (?:down|up)\b|\b(?:stoops?|bends|crouch\w*|kneels?)\b")
_BODY_TRAVEL = {"sit_down", "stand_up", "walk_across_room"}
_COMPILED = tuple((rid, lvl, re.compile(rx), why) for rid, lvl, rx, why in RULES)

# send cap per shot version (generate.py SEND_CAP); RED sends nothing without an Owner exception
DRAFTS = {"GREEN": 1, "AMBER": 2, "UNKNOWN": 1, "RED": 0}


class Finding(ContractModel):
    rule: str
    level: Literal["AMBER", "RED", "UNKNOWN"]
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
    for phase in decl.choreography.phases:
        text = phase.description.lower()
        if phase.kind == "HOLD":
            for rid, lvl, rx, why in _COMPILED:
                if rid in HOLD_RULES and rx.search(text):
                    add(rid, lvl, phase, why)
            continue
        before = len(findings)
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
        if phase.kind == "ACTION" and len(findings) == before and phase.motion not in _SUPPORTED_MOTIONS \
                and not any(rx.search(text) for rx in _SUPPORTED):
            add("UNMATCHED_ACTION", "UNKNOWN", phase, f"no rule and no supported family matches: {phase.description!r}")
    levels = {f.level for f in findings}
    level: Level = ("RED" if "RED" in levels else "UNKNOWN" if "UNKNOWN" in levels
                    else "AMBER" if "AMBER" in levels else "GREEN")
    waiver = (getattr(decl, "generability_waiver", "") or "").strip()
    return GenerabilityRating(generation_id=decl.generation_id, level=level, findings=findings,
                              drafts=DRAFTS[level], waiver=waiver)


def generability_issues(decl) -> tuple[GenerabilityRating, list[PreflightIssue]]:
    """gate3 issues: RED BLOCKs unless the shot reuses an accepted take or has an exception for its version (then WARN);
    AMBER and UNKNOWN WARN; GREEN says nothing. A legacy waiver only adds a WARN."""
    rating = rate_shot(decl)
    issues: list[PreflightIssue] = []
    if rating.waiver:
        issues.append(PreflightIssue(check="GENERABILITY_WAIVER_LEGACY", severity="WARN",
                                     detail=f"{rating.waiver!r} demotes nothing; migrate to accepted_take_reuse or "
                                            "generability_exception"))
    if rating.level == "GREEN":
        return rating, issues
    rules = ", ".join(f"{f.rule} ({f.phase})" for f in rating.findings if f.level == rating.level)
    exc = getattr(decl, "generability_exception", None)
    reuse = (getattr(decl, "accepted_take_reuse", "") or "").strip()
    if rating.level == "RED":
        if reuse:
            issues.append(PreflightIssue(check="GENERABILITY_RED_REUSE", severity="WARN",
                                         detail=f"{rules}; reuses the accepted take {reuse}, no new send"))
        elif exc is not None and exc.shot_version == decl.version:
            issues.append(PreflightIssue(check="GENERABILITY_RED_EXCEPTION", severity="WARN",
                                         detail=f"{rules}; Owner exception for v{exc.shot_version}, {exc.max_attempts} "
                                                f"send(s) / {exc.max_credits:g} credits until {exc.expires}"))
        else:
            issues.append(PreflightIssue(
                check="GENERABILITY_RED", severity="BLOCK",
                detail=f"{rules}; restage (cut around it, prop-only insert, off screen + sound, prop out of frame), "
                       "reuse an accepted take (accepted_take_reuse) or get an Owner generability_exception"))
    elif rating.level == "UNKNOWN":
        issues.append(PreflightIssue(check="GENERABILITY_UNKNOWN", severity="WARN",
                                     detail=f"{rules}; unrated beat, offline work only, {rating.drafts} send per version"))
    else:
        issues.append(PreflightIssue(check="GENERABILITY_AMBER", severity="WARN",
                                     detail=f"{rules}; plan {rating.drafts} drafts"))
    return rating, issues
