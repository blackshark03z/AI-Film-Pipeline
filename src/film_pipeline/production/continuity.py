"""Continuity bible (G-continuity): six kinds of continuity checked over the per-generation start/end states.

Kinds and where they are checked:

* ``ACTION``    every change between a generation's start and end state needs a causing ACTION/CONSEQUENCE phase;
                a once-action must not be staged again in a later generation of the same scene.
* ``SPATIAL``   positions change only when a phase names the character moving.
* ``OBJECT``    a prop changes place / appears / disappears only when a phase names that prop
                (film03: the letter cannot go from the pocket to the bin without an action).
* ``TEMPORAL``  story-time order and readable markers (`drama.scene_bible.check_temporal`), plus one time of day
                per scene.
* ``VISUAL``    lighting, time of day, location and looks stay put inside a generation and across a hand-off.
* ``EMOTIONAL`` a performance does not leap two intensity levels between chained generations of one scene
                without a reaction/consequence beat.

Chained generations (`previous_generation_id`) continue from the last frame, so inside one scene the previous end
state must equal this start state exactly; across a scene cut a differing prop or look is only a WARN (the story-time
gap, owned by TEMPORAL, may explain it). The whole module takes the typed `preprod` and `shots` sections and never
reads a file, so it works the same for the package gates, `plan` and the CLI.
"""
from __future__ import annotations

import re
from typing import Any

from film_pipeline.drama.continuity import ContinuityState
from film_pipeline.drama.scene_bible import RuleIssue, check_temporal

KINDS = ("ACTION", "SPATIAL", "OBJECT", "TEMPORAL", "VISUAL", "EMOTIONAL")
_CAUSE_PHASES = ("ACTION", "CONSEQUENCE")
_RESPONSE_PHASES = ("REACTION", "CONSEQUENCE")
_INTENSITY = {"restrained": 0, "moderate": 1, "strong": 2}
_ARTICLES = {"the", "a", "an", "his", "her", "their", "its", "my", "your", "our", "at", "in", "on", "to", "of", "by",
             "with", "from", "into", "onto", "over", "under", "and", "is", "are", "it"}
_LIGHT_WORDS = ("light", "lamp", "switch", "blind", "curtain", "shade", "sun", "dawn", "dusk", "shutter", "flicker")
_SPEECH_STEMS = ("speak", "say", "reply", "answer", "ask", "whisper", "murmur")  # dialogue repeats legitimately
_WARDROBE_WORDS = ("coat", "jacket", "hat", "glove", "scarf", "tie", "uniform", "shirt", "dress", "change",
                   "remove", "put on", "take off", "takes off", "wear")


def _issue(out: list[RuleIssue], check: str, severity: str, detail: str) -> None:
    out.append(RuleIssue(check=check, severity=severity, detail=detail))  # type: ignore[arg-type]


def kind_of(check: str) -> str:
    """The continuity kind a check name belongs to ("OBJECT_NO_CAUSE" -> "OBJECT")."""
    return check.split("_", 1)[0]


def _words(text: str) -> list[str]:
    found = (w[:-2] if w.endswith("'s") else w for w in re.findall(r"[a-z0-9']+", text.lower()))
    return [w for w in found if w not in _ARTICLES and len(w) > 1]


def _prop_name(key: str) -> str:
    return key.rstrip(":").strip()


def _stage_texts(choreo: Any, kinds: tuple[str, ...] | None) -> list[str]:
    """Lower-cased phase descriptions (all phases, or only the given kinds) plus the declared once-actions."""
    if choreo is None:
        return []
    texts = [p.description.lower() for p in choreo.phases if kinds is None or p.kind in kinds]
    if kinds is not None and any(k in _CAUSE_PHASES for k in kinds):
        texts += [a.lower() for a in choreo.once_actions]
    return texts


def _names_prop(texts: list[str], prop: str, before: str | None, after: str | None, cast: set[str]) -> bool:
    """A phase names the prop by its name, or by a word that differs between where it was and where it ends up
    ("lifts the receiver to his ear" explains the desk phone going from "on the desk" to "receiver at his ear")."""
    changed = (set(_words(before or "")) ^ set(_words(after or ""))) - cast  # a holder's name is not the prop
    return any(w in t for t in texts for w in (*_words(prop), *sorted(changed)))


def _names_character(texts: list[str], who: str) -> bool:
    return any(who.lower() in t for t in texts)


def _generation_changes(gid: str, decl: Any, start: ContinuityState, end: ContinuityState, cast: set[str],
                        out: list[RuleIssue]) -> None:
    choreo = decl.choreography
    caused = _stage_texts(choreo, _CAUSE_PHASES)
    has_cause_phase = bool(choreo and any(p.kind in _CAUSE_PHASES for p in choreo.phases))

    for key in sorted(set(start.props) | set(end.props)):
        before, after = start.props.get(key), end.props.get(key)
        if before == after:
            continue
        if not _names_prop(caused, _prop_name(key), before, after, cast):
            move = f"{before!r} -> {after!r}" if before is not None and after is not None else (
                f"appears ({after!r})" if before is None else f"disappears (was {before!r})")
            _issue(out, "OBJECT_NO_CAUSE", "BLOCK",
                   f"{gid}: {_prop_name(key)} {move} with no ACTION/CONSEQUENCE phase naming it")

    for who in sorted(set(start.positions) & set(end.positions)):
        if start.positions[who] == end.positions[who] or _names_character(caused, who):
            continue
        if has_cause_phase:
            _issue(out, "SPATIAL_UNNAMED", "WARN",
                   f"{gid}: {who} moves ({start.positions[who]!r} -> {end.positions[who]!r}) but no ACTION phase "
                   f"names {who}")
        else:
            _issue(out, "SPATIAL_NO_ACTION", "BLOCK",
                   f"{gid}: {who} moves ({start.positions[who]!r} -> {end.positions[who]!r}) in a generation with "
                   "no ACTION/CONSEQUENCE phase")

    for who in sorted(set(start.looks) & set(end.looks)):
        if start.looks[who] != end.looks[who] and not (
                _names_character(caused, who) and any(w in t for t in caused for w in _WARDROBE_WORDS)):
            _issue(out, "VISUAL_LOOK_CHANGE", "BLOCK",
                   f"{gid}: {who} changes look {start.looks[who]!r} -> {end.looks[who]!r} with no wardrobe action")

    for field in ("time_of_day", "location"):
        a, b = getattr(start, field), getattr(end, field)
        if a and b and a != b:
            _issue(out, f"VISUAL_{field.upper()}_CHANGE", "BLOCK",
                   f"{gid}: {field} changes {a!r} -> {b!r} inside one generation (start a new scene)")
    if start.lighting and end.lighting and start.lighting != end.lighting and not any(
            w in t for t in caused for w in _LIGHT_WORDS):
        _issue(out, "VISUAL_LIGHTING_CHANGE", "BLOCK",
               f"{gid}: lighting changes {start.lighting!r} -> {end.lighting!r} with no motivating phase "
               "(lamp, switch, blind, sun ...)")


def _handoff(gid: str, prev_id: str, same_scene: bool, prev_end: ContinuityState, start: ContinuityState,
             out: list[RuleIssue]) -> None:
    severity = "BLOCK" if same_scene else "WARN"
    for key in sorted(set(prev_end.props) | set(start.props)):
        if prev_end.props.get(key) != start.props.get(key):
            _issue(out, "OBJECT_HANDOFF", severity,
                   f"{gid}: {_prop_name(key)} was {prev_end.props.get(key)!r} at the end of {prev_id} "
                   f"but starts {start.props.get(key)!r}")
    for who in sorted(set(prev_end.looks) & set(start.looks)):
        if prev_end.looks[who] != start.looks[who]:
            _issue(out, "VISUAL_HANDOFF_LOOK", severity,
                   f"{gid}: {who} look {prev_end.looks[who]!r} at the end of {prev_id} != {start.looks[who]!r}")
    if same_scene:  # a cut may reposition people; a continued take may not
        for who in sorted(set(prev_end.positions) & set(start.positions)):
            if prev_end.positions[who] != start.positions[who]:
                _issue(out, "SPATIAL_HANDOFF", "BLOCK",
                       f"{gid}: {who} ends {prev_id} {prev_end.positions[who]!r} but starts {start.positions[who]!r}")
        for field in ("lighting", "time_of_day", "location"):
            a, b = getattr(prev_end, field), getattr(start, field)
            if a and b and a != b:
                _issue(out, f"VISUAL_HANDOFF_{field.upper()}", "BLOCK",
                       f"{gid}: {field} {a!r} at the end of {prev_id} != {b!r}")


def _emotional(by_id: dict[str, Any], out: list[RuleIssue]) -> None:
    for gid, decl in by_id.items():
        prev = by_id.get(decl.previous_generation_id or "")
        if prev is None or prev.scene_id != decl.scene_id or prev.choreography is None or decl.choreography is None:
            continue
        responded = any(p.kind in _RESPONSE_PHASES for p in prev.choreography.phases)
        before = {c.character: _INTENSITY[c.intensity] for c in prev.choreography.performance}
        for cue in decl.choreography.performance:
            jump = _INTENSITY[cue.intensity] - before.get(cue.character, _INTENSITY[cue.intensity])
            if abs(jump) >= 2 and not responded:
                _issue(out, "EMOTIONAL_JUMP", "WARN",
                       f"{gid}: {cue.character} jumps {jump:+d} intensity levels to {cue.intensity} straight after "
                       f"{prev.generation_id} with no REACTION/CONSEQUENCE beat")


def temporal_issues(pre: Any, shots: Any) -> list[RuleIssue]:
    """Story-time order and markers, as `plan` has always reported them (states keyed by scene)."""
    order = list(pre.scenes)
    first = {g.scene_id: g for g in reversed(shots.generations)}  # earliest generation per scene
    last = {g.scene_id: g for g in shots.generations}  # latest generation per scene
    return check_temporal(
        [pre.scenes[s].story_time for s in order],
        {s: pre.states[last[s].end_state] for s in order if s in last},
        {s: pre.states[first[s].start_state] for s in order if s in first})


def continuity_issues(pre: Any, shots: Any, include_temporal: bool = True) -> list[RuleIssue]:
    """Every continuity finding (BLOCK and WARN) for the typed `preprod` + `shots` sections.

    `include_temporal=False` leaves out the story-time order check that `plan` already reports on its own."""
    out: list[RuleIssue] = []
    cast = {c.lower() for c in pre.characters}
    by_id = {g.generation_id: g for g in shots.generations}
    seen_actions: dict[tuple[str, str], str] = {}
    scene_time: dict[str, tuple[str, str]] = {}

    for gid, decl in by_id.items():
        start, end = pre.states.get(decl.start_state), pre.states.get(decl.end_state)
        if start is None or end is None:
            _issue(out, "ACTION_STATE_MISSING", "BLOCK",
                   f"{gid}: state {decl.start_state if start is None else decl.end_state!r} is not in 03_preprod.states")
            continue
        _generation_changes(gid, decl, start, end, cast, out)

        scene = pre.scenes.get(decl.scene_id)
        for label, state in (("start", start), ("end", end)):
            if state.location and scene and state.location != scene.location:
                _issue(out, "VISUAL_SCENE_LOCATION", "BLOCK",
                       f"{gid}: {label} state location {state.location!r} != scene {decl.scene_id} location "
                       f"{scene.location!r}")
            if state.time_of_day:
                known = scene_time.setdefault(decl.scene_id, (state.time_of_day, gid))
                if known[0] != state.time_of_day:
                    _issue(out, "TEMPORAL_SCENE_TIME", "BLOCK",
                           f"{gid}: time of day {state.time_of_day!r} but {known[1]} in the same scene says "
                           f"{known[0]!r}")

        prev = by_id.get(decl.previous_generation_id or "")
        if decl.previous_generation_id and prev is None:
            _issue(out, "ACTION_HANDOFF_MISSING", "BLOCK",
                   f"{gid}: previous_generation_id {decl.previous_generation_id!r} is not a generation")
        elif prev is not None and (prev_end := pre.states.get(prev.end_state)) is not None:
            _handoff(gid, prev.generation_id, prev.scene_id == decl.scene_id, prev_end, start, out)

        if decl.choreography is not None:
            for action in decl.choreography.once_actions:
                if any(w.startswith(_SPEECH_STEMS) for w in _words(action)):
                    continue
                key = (decl.scene_id, " ".join(_words(action)))
                if key in seen_actions and seen_actions[key] != gid:
                    _issue(out, "ACTION_REPEATED", "WARN",
                           f"{gid}: once-action {action!r} was already staged in {seen_actions[key]}")
                seen_actions.setdefault(key, gid)

    _emotional(by_id, out)
    if include_temporal:
        out += temporal_issues(pre, shots)
    return out


def continuity_report(pre: Any, shots: Any) -> dict[str, Any]:
    """CLI / status view: findings grouped by kind, `ok` = no BLOCK."""
    issues = continuity_issues(pre, shots)
    by_kind = {k: {"BLOCK": 0, "WARN": 0} for k in KINDS}
    for i in issues:
        by_kind.setdefault(kind_of(i.check), {"BLOCK": 0, "WARN": 0})[i.severity] += 1
    return {"ok": not any(i.severity == "BLOCK" for i in issues), "by_kind": by_kind,
            "issues": [i.model_dump() for i in issues],
            "generations": len(shots.generations), "states": len(pre.states)}


def blocking(issues: list[RuleIssue]) -> list[str]:
    return [f"CONTINUITY {i.check}: {i.detail}" for i in issues if i.severity == "BLOCK"]
