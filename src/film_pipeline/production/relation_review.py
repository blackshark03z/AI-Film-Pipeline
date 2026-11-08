"""P16-04 relation review questions: who speaks to whom, where each listener is, gaze, and which side of a barrier.

Only meaningful when `preflight.interaction_contract` is on (the caller checks). Each question has a stable id; a take
that carries them in `TakeQc.required_answers` cannot be ACCEPTED until a human has written an answer for every id in
the group check (`GroupCheck.answers`). See `qc_model.TakeQc.verdict`.
"""
from __future__ import annotations

from typing import Any


def speakers_of(decl: Any, script_lines: dict[int, str]) -> dict[int, str]:
    """Script line number -> speaking character, for the shot's lines (from "CHARACTER: text" dailies lines)."""
    return {n: script_lines.get(n, "").split(":")[0].strip() for n in decl.dialogue}


def _zone_of(layout: Any, mark_id: str) -> str | None:
    mark = next((m for m in getattr(layout, "marks", []) if m.id == mark_id), None)
    return mark.zone if mark is not None else None


def _zone_label(layout: Any, zone_id: str) -> str:
    zone = next((z for z in layout.zones if z.id == zone_id), None)
    return zone.label if zone is not None else zone_id


def relation_questions(pre: Any, decl: Any, speakers: dict[int, str]) -> list[dict[str, str]]:
    scene = pre.scenes.get(decl.scene_id)
    subject = decl.subject or (decl.visible[0] if decl.visible else "")
    out: list[dict[str, str]] = []

    def add(qid: str, group: str, question: str) -> None:
        out.append({"id": qid, "group": group, "question": question})

    for n in decl.dialogue:
        names = decl.addressees.get(n) or []
        who = speakers.get(n) or "the speaker"
        if names == ["SELF"]:
            add(f"REL_ADDRESS:{n}", "narrative", f"Line {n}: does {who} speak to no one in the room?")
        elif names:
            to = " and ".join(x for x in names if x != "SELF")
            add(f"REL_ADDRESS:{n}", "narrative",
                f"Line {n}: does {who} clearly speak to {to} (eyes and body toward them)?")
    for name, a in sorted(decl.listener_anchors.items()):
        side = ((scene.axis.sides.get(name) if scene is not None else None) or "LEFT").lower()
        if a.mode == "VISIBLE":
            q = f"Is {name} in frame for the whole clip?"
        elif a.mode == "OTS_FOREGROUND":
            q = (f"Is {name}'s shoulder and back of head in the near frame-{side} for the whole clip, "
                 f"recognisably {name}?")
        else:
            eyes = "toward the camera's side" if a.side == "BEHIND_CAMERA" else f"just past the lens to frame-{(a.side or 'LEFT').lower()}"
            q = (f"Is the place where {name} stands kept out of frame (never shown empty), and do {subject}'s eyes "
                 f"go {eyes}?")
        add(f"REL_LISTENER:{name}", "spatial", q)
    if decl.gaze_target:
        add("REL_GAZE", "spatial", f"Does {subject} look at {decl.gaze_target} and never into the lens?"
            if decl.gaze_target != "LENS" else f"Does {subject} avoid looking into the lens?")
    loc = pre.locations.get(scene.location) if scene is not None else None
    layout = getattr(loc, "layout", None)
    state = pre.states.get(decl.start_state)
    if layout is not None and state is not None:
        zones = {who: _zone_of(layout, pose.mark) for who, pose in sorted(state.blocking.items())}
        zones = {who: z for who, z in zones.items() if z}
        names = list(zones)
        for i, a in enumerate(names):
            for b in names[i + 1:]:
                if zones[a] != zones[b]:
                    add("REL_BARRIER", "spatial",
                        f"Do {a} and {b} stay on their own sides ({_zone_label(layout, zones[a])} / "
                        f"{_zone_label(layout, zones[b])}) the whole clip?")
                    return out
    return out
