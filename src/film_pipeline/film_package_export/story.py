"""Timeline, scenes and dialogue rows of a film_package, read from AFP stage files (plain JSON, no AFP imports)."""
from __future__ import annotations

import re
from fractions import Fraction
from typing import Any

from .media import ExportError, frames

# titles.json cue "source" -> contract timing_source. "override" = a human line in titles/cues.json; "windows" = speech
# windows (VAD) shared out by word count and "even" = an even split: both are script-based estimates, not STT alignment.
TIMING_SOURCE = {"override": "manual", "windows": "script_estimate", "even": "script_estimate"}


def scene_of(event_id: str, shots: dict[str, str]) -> str | None:
    if event_id in shots:
        return shots[event_id]
    found = re.match(r"^(SC\d+)(?:_|$)", event_id)
    return found.group(1) if found else None


def build_timeline(cut: dict[str, Any], edit: dict[str, Any], lock: dict[str, Any] | None, fps: Fraction,
                   duration_frames: int, shots: dict[str, str], warns: list[str]) -> list[dict[str, Any]]:
    """Events on the final picture clock (title card, body events, end card), half-open frames."""
    planned = cut.get("planned") or {}
    body = planned.get("events") or []
    edl = {e["event_id"]: e for e in edit.get("events", [])}
    if [p["event_id"] for p in body] != [e["event_id"] for e in edit.get("events", [])]:
        raise ExportError("05_edit.json and the cut report list different events (stale cut report?)")
    sources = (lock or {}).get("sources") or {}
    half = 0.5 / float(fps)
    rows: list[dict[str, Any]] = []
    title_s = float(planned.get("title_s") or 0)
    if title_s > 0:
        rows.append({"event_id": "TITLE_CARD", "kind": "CARD", "in_frame": 0, "out_frame": frames(title_s, fps)})
    for i, p in enumerate(body):
        nxt = body[i + 1] if i + 1 < len(body) else None
        out = frames(nxt["start_s"], fps) if nxt and abs(p["end_s"] - nxt["start_s"]) < half else frames(p["end_s"], fps)
        row: dict[str, Any] = {"event_id": p["event_id"], "kind": p["kind"] if p["kind"] in ("TAKE", "CARD") else "OTHER"}
        scene = scene_of(p["event_id"], shots)
        if scene:
            row["scene_id"] = scene
        if row["kind"] == "TAKE" and p.get("take_id"):
            row["take_id"] = p["take_id"]
            if p["take_id"] in sources:
                row["source_sha256"] = sources[p["take_id"]]
            else:
                warns.append(f"{p['event_id']}: take {p['take_id']} has no source hash in the picture lock")
            row["source_in_frame"] = frames(float(edl[p["event_id"]].get("src_in_s") or 0), fps)
        row.update(in_frame=frames(p["start_s"], fps), out_frame=out)
        rows.append(row)
    end_s = float(planned.get("end_s") or 0)
    if end_s > 0 and body:
        rows.append({"event_id": "END_CARD", "kind": "CARD", "in_frame": rows[-1]["out_frame"], "out_frame": duration_frames})
    # gaps must be declared as BLACK events (the contract forbids silent gaps)
    filled, cursor = [], 0
    for row in rows:
        if row["in_frame"] > cursor:
            filled.append({"event_id": f"GAP_{cursor}", "kind": "BLACK", "in_frame": cursor, "out_frame": row["in_frame"]})
            warns.append(f"gap [{cursor},{row['in_frame']}) before {row['event_id']} declared as BLACK")
        filled.append(row)
        cursor = row["out_frame"]
    if rows and cursor < duration_frames:
        filled.append({"event_id": f"GAP_{cursor}", "kind": "BLACK", "in_frame": cursor, "out_frame": duration_frames})
        warns.append(f"tail [{cursor},{duration_frames}) declared as BLACK")
    return filled


def build_scenes(timeline: list[dict[str, Any]], story: dict | None, preprod: dict | None, mix: dict | None,
                 speakers: dict[str, list[str]]) -> list[dict[str, Any]]:
    order = list(dict.fromkeys(r["scene_id"] for r in timeline if r.get("scene_id")))
    ambience = {a["scene_id"]: a for a in (mix or {}).get("ambience", []) if "scene_id" in a}
    out = []
    for sid in order:
        scene: dict[str, Any] = {"scene_id": sid}
        beat = ((story or {}).get("scenes") or {}).get(sid)
        if beat:
            parts = [beat.get("purpose"), f"Conflict: {beat['conflict']}" if beat.get("conflict") else None,
                     f"Outcome: {beat['outcome']}" if beat.get("outcome") else None]
            scene["intent"] = " ".join(p for p in parts if p)
        pre = ((preprod or {}).get("scenes") or {}).get(sid) or {}
        loc_id = pre.get("location") or ambience.get(sid, {}).get("location")
        if loc_id:
            scene["location"] = loc_id
            look = (((preprod or {}).get("locations") or {}).get(loc_id) or {}).get("look") or {}
            if look.get("time_of_day"):
                scene["time_of_day"] = str(look["time_of_day"]).lower()
        tone = ambience.get(sid, {}).get("room_tone") or (((preprod or {}).get("locations") or {}).get(
            loc_id or "", {}).get("room_tone"))
        if tone:
            scene["room_tone"] = tone
        chars = list(dict.fromkeys(list((pre.get("occupancy") or {}).get("initial") or []) + speakers.get(sid, [])))
        if chars:
            scene["characters"] = chars
        out.append(scene)
    return out


def build_dialogue(titles: dict | None, cues: dict | None, timeline: list[dict[str, Any]],
                   fps: Fraction, cut: dict[str, Any], warns: list[str]) -> list[dict[str, Any]]:
    """One row per titles.json cue; times are the used part of the event (titles) shifted to the picture clock."""
    if not titles:
        return []
    manual = {(c["event_id"], c["line_no"]): c for c in (cues or {}).get("cues", [])}
    starts = {p["event_id"]: float(p["start_s"]) for p in (cut.get("planned") or {}).get("events", [])}
    events = {r["event_id"]: r for r in timeline}
    rows, seen = [], set()
    for cue in titles.get("cues", []):
        eid, line = cue["event_id"], cue.get("line_no")
        if eid not in events or eid not in starts:
            raise ExportError(f"titles.json cue {eid}#{line} names an event that is not on the timeline")
        given = manual.get((eid, line))
        a, b = (given["start_s"], given["end_s"]) if given else (cue["start_s"], cue["end_s"])
        if given and (cue["start_s"], cue["end_s"]) != (given["start_s"], given["end_s"]):
            warns.append(f"{eid}#{line}: titles.json timing differs from cues.json; cues.json used")
        ev = events[eid]
        lo, hi = frames(starts[eid] + a, fps), frames(starts[eid] + b, fps)
        clo, chi = max(lo, ev["in_frame"]), min(hi, ev["out_frame"])
        if chi <= clo:
            raise ExportError(f"cue {eid}#{line} lies outside its event [{ev['in_frame']},{ev['out_frame']})")
        if (clo, chi) != (lo, hi):
            warns.append(f"cue {eid}#{line} clamped to its event")
        cue_id = f"{eid}.L{line}"
        if cue_id in seen:
            cue_id += f".{len(seen)}"
        seen.add(cue_id)
        src = "override" if given else cue.get("source")
        if src not in TIMING_SOURCE:
            warns.append(f"{eid}#{line}: unknown cue source {src!r}, recorded as script_estimate")
        row = {"cue_id": cue_id, "event_id": eid, "in_frame": clo, "out_frame": chi, "text": cue["text"],
               "timing_source": TIMING_SOURCE.get(src, "script_estimate")}
        if cue.get("character"):
            row["speaker"] = cue["character"]
        rows.append(row)
    return rows
