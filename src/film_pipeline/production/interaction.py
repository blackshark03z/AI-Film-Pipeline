"""Interaction contract: who talks to whom, where everyone stands, and what the frame owes the listener.

Film04 SC02_g1: the clerk speaks to THEO, but the shot is a clean single from THEO's side and nothing in the data
said who she addressed or where he was, so the still showed an empty counter. Declared in the package (opt-in via
`03_preprod.preflight.interaction_contract`, default off so earlier films are untouched):

* `locations.<id>.layout.marks`         -> `ActorMark`      (named standing / seating spots in a zone)
* `states.<id>.blocking`                -> `ActorPose`      (character -> mark + posture, start and end of a shot)
* `scenes.<id>.encounter_id`            one encounter spans cuts (and scenes) where the same people stay together
* `generations[].addressees`            script line number -> listeners ("SELF" = talking to oneself / voiceover)
* `generations[].listener_anchors`      character -> `ListenerAnchor` (how the shot accounts for the listener)
* `generations[].gaze_target`           what the subject looks at (character, set object, mark, or "LENS")

`interaction_issues` rules (BLOCK unless stated): ADDRESSEE_MISSING, ADDRESSEE_ABSENT, LISTENER_ANCHOR_MISSING,
ANCHOR_CONTRADICTION, OFF_FRAME_TOO_WIDE, OFF_FRAME_NOT_ESTABLISHED, OFF_FRAME_WRONG_SIDE, MARK_UNRESOLVED,
GAZE_TARGET_MISSING, GAZE_TARGET_UNRESOLVED, GAZE_INTO_LENS (WARN).
`placement_sentences` (P16-03) compiles the same placement text into the still and the video prompt;
`hidden_person_issues` adds HIDDEN_PERSON_UNPLACED.
"""
from __future__ import annotations

import re
from typing import TYPE_CHECKING, Annotated, Any, Literal

from pydantic import Field, StringConstraints, model_validator

from film_pipeline.core import ContractModel

if TYPE_CHECKING:
    from film_pipeline.drama.preflight import PreflightIssue

Ident = Annotated[str, StringConstraints(pattern=r"^[A-Za-z0-9][A-Za-z0-9_-]*$")]


class ActorMark(ContractModel):
    id: Ident
    at: tuple[float, float]  # top-down floor plan, 0..1
    zone: Ident

    @model_validator(mode="after")
    def _unit(self) -> "ActorMark":
        if not all(0.0 <= v <= 1.0 for v in self.at):
            raise ValueError(f"mark {self.id}: position {self.at} must lie within 0..1")
        return self


class ActorPose(ContractModel):
    mark: Ident
    posture: str = Field(min_length=1)  # free word: standing / seated / bent ...
    facing: str = ""


class ListenerAnchor(ContractModel):
    mode: Literal["VISIBLE", "OTS_FOREGROUND", "OFF_FRAME"]
    side: Literal["LEFT", "RIGHT", "BEHIND_CAMERA"] | None = None
    placement: str = ""  # prompt phrase: "THEO stands just off frame-left beside the camera"
    established_by: Ident | None = None  # earlier generation that showed speaker and listener together

    @model_validator(mode="after")
    def _off_frame_needs_place(self) -> "ListenerAnchor":
        if self.mode == "OFF_FRAME" and (self.side is None or not self.placement.strip()):
            raise ValueError("an OFF_FRAME listener needs a side and a placement phrase")
        return self


def _size_index(decl: Any) -> int | None:
    from film_pipeline.production.camera import _SIZE_ORDER
    return _SIZE_ORDER.index(decl.camera.size) if decl.camera is not None else None


def interaction_issues(pre: Any, shots: Any, decl: Any, index: int, speakers: dict[int, str]) -> "list[PreflightIssue]":
    """Findings for one generation. `index` = its position among its scene's generations (occupancy index);
    `speakers` = script line number -> speaking character, for the shot's lines."""
    from film_pipeline.drama.preflight import PreflightIssue
    from film_pipeline.production.camera import _SIZE_ORDER

    out: list[PreflightIssue] = []

    def add(check: str, detail: str, severity: str = "BLOCK") -> None:
        out.append(PreflightIssue(check=check, severity=severity, detail=f"{decl.generation_id}: {detail}"))  # type: ignore[arg-type]

    scene = pre.scenes[decl.scene_id]
    present = scene.occupancy.present_at(index)
    loc = pre.locations.get(scene.location)
    layout = getattr(loc, "layout", None) if loc is not None else None
    visible = set(decl.visible)
    anchors = decl.listener_anchors

    # 1-2 addressees
    for n in decl.dialogue:
        if not decl.addressees.get(n):
            add("ADDRESSEE_MISSING", f"line {n} ({speakers.get(n, '?')}) has no addressee; name who it is said to, or SELF")
    for n, names in sorted(decl.addressees.items()):
        for name in names:
            if name == "SELF":
                continue
            if name == speakers.get(n):
                add("ADDRESSEE_ABSENT", f"line {n}: {name} is the speaker, not an addressee (use SELF)")
            elif name not in present:
                add("ADDRESSEE_ABSENT", f"line {n}: addressee {name} is not in the scene at this generation")

    # 3 every listener the shot depends on has an anchor
    listeners = {name for names in decl.addressees.values() for name in names if name != "SELF"}
    if decl.gaze_target in pre.characters:
        listeners.add(decl.gaze_target)
    for name in sorted(listeners - set(anchors)):
        add("LISTENER_ANCHOR_MISSING", f"{name} is addressed or looked at but has no listener anchor")

    # 4-6 anchors
    for name, a in sorted(anchors.items()):
        if a.mode == "VISIBLE" and name not in visible:
            add("ANCHOR_CONTRADICTION", f"{name} is anchored VISIBLE but is not in the shot's visible list")
        elif a.mode == "OTS_FOREGROUND" and (decl.coverage != "OTS" or decl.foreground != name or name not in visible
                                             or name == decl.subject):
            add("ANCHOR_CONTRADICTION", f"{name} is anchored OTS_FOREGROUND but the shot is not an OTS with {name} "
                                        "as visible foreground (and not the subject)")
        elif a.mode == "OFF_FRAME":
            if name in visible:
                add("ANCHOR_CONTRADICTION", f"{name} is anchored OFF_FRAME but is in the shot's visible list")
            si = _size_index(decl)
            if si is None:
                add("OFF_FRAME_TOO_WIDE", f"{name} is off frame but the shot size is unknown (no camera setup)")
            elif si < _SIZE_ORDER.index("CLOSE"):
                add("OFF_FRAME_TOO_WIDE", f"{name} is off frame but the shot is {decl.camera.size}; "
                                          "wider than CLOSE shows the empty place")
            axis_side = scene.axis.sides.get(name)
            if a.side in ("LEFT", "RIGHT") and axis_side is not None and a.side != axis_side:
                add("OFF_FRAME_WRONG_SIDE", f"{name} is off frame {a.side} but the axis book puts {name} {axis_side}")
            why = _not_established(pre, shots, decl, a, name, speakers)
            if why:
                add("OFF_FRAME_NOT_ESTABLISHED", f"{name}: {why}")

    # 7 blocking
    marks = {m.id for m in getattr(layout, "marks", [])} if layout is not None else set()
    for label, sid in (("start", decl.start_state), ("end", decl.end_state)):
        state = pre.states.get(sid)
        if state is None:
            continue
        for who in sorted(present - set(state.blocking)):
            add("MARK_UNRESOLVED", f"{who} is in the scene but {label} state {sid} has no blocking for them")
        for who, pose in sorted(state.blocking.items()):
            if pose.mark not in marks:
                add("MARK_UNRESOLVED", f"{label} state {sid}: {who} stands on mark {pose.mark!r}, "
                                       f"not a mark of location {scene.location}")

    # 8 gaze
    only_one = decl.coverage == "SINGLE" or (bool(decl.subject) and len(decl.visible) == 1)
    gaze = decl.gaze_target
    if not gaze:
        if only_one and len(present) >= 2:
            add("GAZE_TARGET_MISSING", f"a single with {len(present)} people present needs a gaze_target")
    elif gaze == "LENS":
        add("GAZE_INTO_LENS", "the subject looks into the lens", "WARN")
    elif gaze not in present and not (layout is not None and layout.object(gaze) is not None) and gaze not in marks:
        add("GAZE_TARGET_UNRESOLVED", f"gaze_target {gaze!r} is not a present character, set object or mark")
    return out


def _not_established(pre: Any, shots: Any, decl: Any, a: ListenerAnchor, name: str, speakers: dict[int, str]) -> str:
    """Why `a.established_by` does not establish an off-frame listener ("" = it does)."""
    if a.established_by is None:
        return "OFF_FRAME needs established_by: an earlier shot that showed the speaker and listener together"
    order = [g.generation_id for g in shots.generations]
    if a.established_by not in order or order.index(a.established_by) >= order.index(decl.generation_id):
        return f"established_by {a.established_by!r} is not an earlier generation"
    est = shots.generations[order.index(a.established_by)]
    here, there = pre.scenes[decl.scene_id], pre.scenes.get(est.scene_id)
    ea, eb = here.encounter_id, getattr(there, "encounter_id", None)
    same = (ea == eb) if (ea is not None and eb is not None) else est.scene_id == decl.scene_id
    if not same:
        return f"established_by {a.established_by!r} is not in the same encounter or scene"
    others = set(speakers.values()) or ({decl.subject} if decl.subject else set())
    missing = sorted(({name} | others) - set(est.visible))
    if missing:
        return f"established_by {a.established_by!r} does not show {', '.join(missing)} in frame"
    return ""


# -- prompt compilation (P16-03): one placement source for the still prompt and the video prompt ----------------------
SIZE_WORDS = {"EXTREME_WIDE": "extreme wide", "WIDE": "wide", "MEDIUM": "medium", "MEDIUM_CLOSE": "medium close-up",
              "CLOSE": "close-up", "INSERT": "insert close-up"}
_SIZE_RE = re.compile(r"\b(extreme wide|medium close-up|insert close-up|wide|medium|close-up)\b")


def framing_phrase(template: str, size: str) -> str:
    """The still template's framing phrase with its size word replaced by the camera's size (a phrase naming no size
    stays as authored)."""
    m = _SIZE_RE.search(template)
    if m is None or m.group(1) == SIZE_WORDS[size]:
        return template
    return template[:m.start()] + SIZE_WORDS[size] + template[m.end():]


def hidden_names(pre: Any, decl: Any, index: int) -> set[str]:
    """Characters in the scene at this generation who are not in the shot."""
    return set(pre.scenes[decl.scene_id].occupancy.present_at(index)) - set(decl.visible)


def placement_sentences(pre: Any, decl: Any, speakers: dict[int, str]) -> list[str]:
    """Who speaks to whom and where each listener is, in character NAMES (the video prompt maps them to handles)."""
    scene = pre.scenes[decl.scene_id]
    subject = decl.subject or (decl.visible[0] if decl.visible else "")
    out: list[str] = []

    def add(text: str) -> None:
        if text not in out:
            out.append(text)

    for n in decl.dialogue:
        names, who = decl.addressees.get(n) or [], speakers.get(n)
        if not names or not who:
            continue
        if names == ["SELF"]:
            add(f"{who} speaks aloud to no one in particular.")
        else:
            add(f"{who} speaks to {' and '.join(x for x in names if x != 'SELF')}.")
    for name, a in sorted(decl.listener_anchors.items()):
        if a.mode == "OTS_FOREGROUND":
            side = (scene.axis.sides.get(name) or "LEFT").lower()
            add(f"Over {name}'s shoulder: the back of {name}'s head and one shoulder fill the near frame-{side}, "
                f"out of focus; {subject} beyond faces {name}.")
        elif a.mode == "OFF_FRAME":
            text = a.placement.strip()
            add(text if text.endswith(".") else text + ".")
            if a.side == "BEHIND_CAMERA":
                add(f"{subject} looks toward the camera's side, never into the lens.")
            else:
                add(f"{subject}'s eyes go just past the lens to frame-{(a.side or 'LEFT').lower()}.")
    gaze = decl.gaze_target
    if gaze and gaze != "LENS" and gaze not in pre.characters:
        loc = pre.locations.get(scene.location)
        layout = getattr(loc, "layout", None) if loc is not None else None
        obj = layout.object(gaze) if layout is not None else None
        add(f"{subject} looks at the {obj.label if obj is not None else gaze.replace('_', ' ')}.")
    return out


def hidden_person_issues(pre: Any, decl: Any, index: int, texts: list[str]) -> "list[PreflightIssue]":
    """HIDDEN_PERSON_UNPLACED: a character in the scene but not in frame, named in a prompt, with no listener anchor."""
    from film_pipeline.drama.preflight import PreflightIssue

    out = []
    for name in sorted(hidden_names(pre, decl, index) - set(decl.listener_anchors)):
        handle = (pre.characters[name].handle or "") if name in pre.characters else ""
        pats = [re.compile(r"(?<!\w)" + re.escape(name) + r"(?!\w)")]
        if handle:
            pats.append(re.compile(r"(?<!\w)" + re.escape(handle) + r"(?!\w)", re.IGNORECASE))
        if any(p.search(t) for p in pats for t in texts):
            out.append(PreflightIssue(
                check="HIDDEN_PERSON_UNPLACED", severity="BLOCK",
                detail=f"{decl.generation_id}: {name} is in the scene but not in frame, a prompt names {name}, "
                       "and no listener anchor places them"))
    return out
