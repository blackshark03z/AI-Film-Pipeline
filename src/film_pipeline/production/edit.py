"""Edit stage (categories 93 synchronization, 95 assembly cut, 96 rough cut, 104 fine cut): `05_edit.json`, the EDL.

An EDL is an ordered list of events. A TAKE event names a take of the take log and the part of it that is used
(`src_in_s` .. `src_out_s`, default the whole clip); a CARD event is a context card cut into the body. Every event
carries the transition *into* it (the first one must be a CUT) and the J/L audio split at that edit. Identity tags are
overlays on a TAKE event, timed relative to the used part of that event.

``timeline`` places the events on the final clock. Lengths come from the sources (probed, or passed in); a dissolve
overlaps the two events by its duration, so the body is shorter by the sum of the overlaps. J/L cuts move sound only,
never the picture clock.

``edit_problems`` checks an EDL against the package and the take log (unknown/superseded/rejected takes, a take whose
bytes no longer match the log, trims outside the source, transitions longer than the events around them, tags on
nothing). ``render_cut`` renders hard cuts through `drama.post.assemble` (title card, graded clips, end card, AI label,
tags); a dissolve or a J/L cut is declared in the EDL but rendered by P4-02, so asking for one here is an error rather
than a silent hard cut. Loudness, subtitles and credits belong to P5.
"""
from __future__ import annotations

import hashlib
import json
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Any, Callable, Literal

from pydantic import Field, model_validator

from film_pipeline.core import ContractModel

FPS = 24
FRAME_S = 1.0 / FPS
TransitionType = Literal["CUT", "MATCH_CUT", "DISSOLVE", "DIP_TO_BLACK"]
_HARD = ("CUT", "MATCH_CUT")  # no overlap, no extra frames


class Transition(ContractModel):
    type: TransitionType = "CUT"
    duration_s: float = Field(default=0.0, ge=0)

    @model_validator(mode="after")
    def _duration_matches_type(self) -> "Transition":
        if self.type in _HARD and self.duration_s != 0:
            raise ValueError(f"{self.type} is instantaneous: duration_s must be 0")
        if self.type not in _HARD and self.duration_s <= 0:
            raise ValueError(f"{self.type} needs duration_s > 0")
        return self


class AudioCut(ContractModel):
    """Seconds the sound of this event starts before (J) / the previous event's sound runs on after (L) the picture cut."""

    j_cut_s: float = Field(default=0.0, ge=0)
    l_cut_s: float = Field(default=0.0, ge=0)


class EditEvent(ContractModel):
    event_id: str = Field(pattern=r"^[A-Za-z0-9][A-Za-z0-9_-]*$")
    kind: Literal["TAKE", "CARD"] = "TAKE"
    take_id: str = ""  # TAKE: `<generation_id>_t<N>`
    generation_id: str = ""  # TAKE: derived from take_id; also what impact analysis matches on
    src_in_s: float = Field(default=0.0, ge=0)
    src_out_s: float | None = Field(default=None, gt=0)  # None = to the end of the clip
    card_lines: list[str] = Field(default_factory=list)  # CARD
    card_duration_s: float | None = Field(default=None, gt=0)  # CARD
    transition: Transition = Field(default_factory=Transition)
    audio: AudioCut = Field(default_factory=AudioCut)
    note: str = ""

    @model_validator(mode="after")
    def _shape(self) -> "EditEvent":
        if self.kind == "TAKE":
            if not self.take_id:
                raise ValueError(f"{self.event_id}: a TAKE event needs take_id")
            gid = self.take_id.rsplit("_t", 1)[0]
            if self.generation_id and self.generation_id != gid:
                raise ValueError(f"{self.event_id}: generation_id {self.generation_id!r} does not match take {self.take_id!r}")
            self.generation_id = gid
            if self.src_out_s is not None and self.src_out_s <= self.src_in_s:
                raise ValueError(f"{self.event_id}: src_out_s must be after src_in_s")
        else:
            if self.take_id or self.src_in_s or self.src_out_s is not None:
                raise ValueError(f"{self.event_id}: a CARD event has no take or source range")
            if not self.card_lines or not self.card_duration_s:
                raise ValueError(f"{self.event_id}: a CARD event needs card_lines and card_duration_s")
        return self


class TagEvent(ContractModel):
    """Identity tag over a TAKE event; times are seconds into the used part of that event."""

    event_id: str
    character: str = Field(min_length=1)
    label: str = Field(min_length=1)
    relation: str = ""
    start_s: float = Field(ge=0)
    end_s: float = Field(gt=0)
    anchor_x: float = Field(ge=0.0, le=1.0)
    anchor_y: float = Field(ge=0.0, le=1.0)

    @model_validator(mode="after")
    def _order(self) -> "TagEvent":
        if self.end_s <= self.start_s:
            raise ValueError(f"tag {self.character}@{self.event_id}: end_s must be after start_s")
        return self


class TextLine(ContractModel):
    text: str = Field(min_length=1)
    size: int = Field(default=64, ge=8)


class EditSection(ContractModel):
    """`05_edit.json`."""

    events: list[EditEvent]
    tags: list[TagEvent] = Field(default_factory=list)
    title: list[TextLine] = Field(default_factory=list)  # empty: the film title
    end: list[TextLine] = Field(default_factory=list)  # empty: the film title + the fiction line
    title_s: float = Field(default=3.0, gt=0)
    end_s: float = Field(default=4.0, gt=0)

    @model_validator(mode="after")
    def _structure(self) -> "EditSection":
        ids = [e.event_id for e in self.events]
        if len(set(ids)) != len(ids):
            raise ValueError("duplicate event_id")
        if self.events and self.events[0].transition.type != "CUT":
            raise ValueError(f"{self.events[0].event_id}: the first event cannot have a transition into it")
        return self


# ------------------------------------------------------------------ timeline

def source_length(event: EditEvent, source_s: float | None) -> float:
    """Seconds of picture the event contributes (before overlaps)."""
    if event.kind == "CARD":
        return float(event.card_duration_s)
    if source_s is None:
        raise ValueError(f"{event.event_id}: source duration unknown")
    return float((event.src_out_s if event.src_out_s is not None else source_s) - event.src_in_s)


def timeline(section: EditSection, durations: dict[str, float]) -> dict[str, Any]:
    """Place the events on the final clock. ``durations`` maps take_id -> clip seconds (cards need none). All times are
    seconds from the start of the film, title card included."""
    placed: list[dict[str, Any]] = []
    cursor = section.title_s
    for index, event in enumerate(section.events):
        length = source_length(event, durations.get(event.take_id))
        overlap = event.transition.duration_s if index else 0.0
        start = cursor - overlap
        placed.append({"event_id": event.event_id, "kind": event.kind, "take_id": event.take_id,
                       "start_s": round(start, 6), "end_s": round(start + length, 6), "duration_s": round(length, 6),
                       "transition": event.transition.type})
        cursor = start + length
    body_end = cursor
    return {"events": placed, "title_s": section.title_s, "body_end_s": round(body_end, 6),
            "end_s": section.end_s, "total_s": round(body_end + section.end_s, 6)}


def frames(seconds: float) -> int:
    return round(seconds * FPS)


# ------------------------------------------------------------------ validation

def probe_duration(path: Path) -> float:
    from film_pipeline.drama.post import probe_video_duration
    return probe_video_duration(path)


def resolve_clip(root: Path, output_file: str, clips_dir: Path | None = None) -> Path:
    return Path(clips_dir) / output_file if clips_dir else Path(root) / "media" / "takes" / output_file


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def edit_problems(pkg: Any, section: EditSection, *, clips_dir: Path | None = None, require_accepted: bool = False,
                  probe: Callable[[Path], float] | None = None) -> tuple[list[dict[str, str]], dict[str, float]]:
    """(problems, durations). Each problem: {code, severity BLOCK|WARN, event_id, detail}. ``durations`` has every take
    that could be probed. ``require_accepted`` (a fine cut / picture lock) turns an unreviewed take from WARN to BLOCK."""
    from film_pipeline.production.takes import load_log
    probe = probe or probe_duration
    root = Path(pkg.root)
    log = load_log(root, pkg.header.film_id)
    entries = {t.take_id: t for t in log.takes}
    shots = pkg.typed.get("shots")
    versions = {g.generation_id: g.version for g in shots.generations} if shots is not None else {}
    problems: list[dict[str, str]] = []
    durations: dict[str, float] = {}

    def add(code: str, severity: str, event_id: str, detail: str) -> None:
        problems.append({"code": code, "severity": severity, "event_id": event_id, "detail": detail})

    by_event = {e.event_id: e for e in section.events}
    for event in section.events:
        if event.kind != "TAKE":
            continue
        entry = entries.get(event.take_id)
        if entry is None:
            add("TAKE_UNKNOWN", "BLOCK", event.event_id, f"{event.take_id} is not in the take log")
            continue
        if versions and event.generation_id not in versions:
            add("GENERATION_UNKNOWN", "BLOCK", event.event_id, f"{event.generation_id} is not in 04_shots.json")
        elif versions and entry.shot_version != versions[event.generation_id]:
            add("TAKE_SUPERSEDED", "BLOCK", event.event_id,
                f"{event.take_id} was rendered from shot v{entry.shot_version}, the shot is now v{versions[event.generation_id]}")
        if entry.status == "REJECTED":
            add("TAKE_REJECTED", "BLOCK", event.event_id, f"{event.take_id} was rejected in review")
        elif entry.status != "ACCEPTED":
            add("TAKE_NOT_ACCEPTED", "BLOCK" if require_accepted else "WARN", event.event_id,
                f"{event.take_id} is {entry.status}: no human accepted it")
        clip = resolve_clip(root, entry.output_file, clips_dir)
        if not clip.is_file():
            add("CLIP_MISSING", "BLOCK", event.event_id, f"{clip} not found")
            continue
        if _sha256(clip) != entry.output_sha256:
            add("CLIP_CHANGED", "BLOCK", event.event_id, f"{clip.name} no longer matches the hash in the take log")
            continue
        try:
            length = probe(clip)
        except (subprocess.CalledProcessError, OSError, ValueError) as exc:
            add("CLIP_UNREADABLE", "BLOCK", event.event_id, f"{clip.name}: {exc}")
            continue
        durations[event.take_id] = length
        if event.src_out_s is not None and event.src_out_s > length + FRAME_S / 2:
            add("TRIM_OUTSIDE_SOURCE", "BLOCK", event.event_id, f"src_out_s {event.src_out_s} > clip length {length:.3f}")
        if event.src_in_s >= length:
            add("TRIM_OUTSIDE_SOURCE", "BLOCK", event.event_id, f"src_in_s {event.src_in_s} >= clip length {length:.3f}")

    # transitions must fit inside both neighbours (and may not overlap an earlier transition on the same event)
    lengths: dict[str, float] = {}
    for event in section.events:
        try:
            lengths[event.event_id] = source_length(event, durations.get(event.take_id))
        except ValueError:
            pass  # the take is already reported
    for index, event in enumerate(section.events[1:], 1):
        d = event.transition.duration_s
        if d <= 0:
            continue
        prev = section.events[index - 1]
        if event.event_id in lengths and prev.event_id in lengths:
            if d >= min(lengths[event.event_id], lengths[prev.event_id]):
                add("TRANSITION_TOO_LONG", "BLOCK", event.event_id,
                    f"{event.transition.type} of {d}s does not fit between {prev.event_id} and {event.event_id}")
            nxt = section.events[index + 1] if index + 1 < len(section.events) else None
            if nxt is not None and nxt.transition.duration_s > 0 and \
                    d + nxt.transition.duration_s >= lengths[event.event_id]:
                add("TRANSITION_OVERLAP", "BLOCK", event.event_id,
                    f"the transitions into and out of {event.event_id} overlap each other")
    for event in section.events:
        if event.audio.j_cut_s or event.audio.l_cut_s:
            if event is section.events[0]:
                add("AUDIO_CUT_ON_FIRST", "BLOCK", event.event_id, "the first event has no previous sound to split with")

    for tag in section.tags:
        target = by_event.get(tag.event_id)
        if target is None or target.kind != "TAKE":
            add("TAG_TARGET", "BLOCK", tag.event_id, f"tag {tag.character} is on {tag.event_id!r}, which is not a TAKE event")
        elif tag.event_id in lengths and tag.end_s > lengths[tag.event_id] + FRAME_S / 2:
            add("TAG_OUTSIDE_EVENT", "BLOCK", tag.event_id,
                f"tag {tag.character} ends at {tag.end_s}s, the event is {lengths[tag.event_id]:.3f}s long")

    if shots is not None:
        used = {e.generation_id for e in section.events if e.kind == "TAKE"}
        for g in shots.generations:
            if g.generation_id not in used:
                add("SHOT_NOT_IN_CUT", "WARN", g.generation_id, f"{g.generation_id} has no event in the cut")
    taken = [e.take_id for e in section.events if e.kind == "TAKE"]
    for take_id in sorted({t for t in taken if taken.count(t) > 1}):
        add("TAKE_REUSED", "WARN", take_id, f"{take_id} appears in more than one event")
    return problems, durations


# ------------------------------------------------------------------ render

def _trim(src: Path, dst: Path, start: float, end: float | None) -> Path:
    cmd = ["ffmpeg", "-v", "error", "-y", "-ss", f"{start:.6f}", "-i", str(src)]
    if end is not None:
        cmd += ["-t", f"{end - start:.6f}"]
    cmd += ["-r", str(FPS), "-c:v", "libx264", "-pix_fmt", "yuv420p", "-c:a", "aac", "-ar", "48000", str(dst)]
    subprocess.run(cmd, check=True)
    return dst


def render_cut(pkg: Any, section: EditSection, out: Path, *, clips_dir: Path | None = None,
               require_accepted: bool = False, cues: list | None = None) -> dict[str, Any]:
    """Render the EDL (hard cuts only) to ``out`` and return the report. Raises ValueError listing BLOCK problems, or
    NotImplementedError for a transition/J-L cut that P4-02 renders. Cues, if given, are SubtitleCue keyed by event_id."""
    from film_pipeline.drama.post import (Overlay, assemble, context_card_clip, identity_tag_png,
                                          probe_video_duration)
    from film_pipeline.production.takes import load_log
    problems, durations = edit_problems(pkg, section, clips_dir=clips_dir, require_accepted=require_accepted)
    blocks = [p for p in problems if p["severity"] == "BLOCK"]
    if blocks:
        raise ValueError("; ".join(f"{p['code']} {p['event_id']}: {p['detail']}" for p in blocks))
    later = [e.event_id for e in section.events
             if e.transition.type not in _HARD or e.audio.j_cut_s or e.audio.l_cut_s]
    if later:
        raise NotImplementedError(f"dissolves and J/L cuts are rendered by P4-02 (events {later})")
    root = Path(pkg.root)
    log = load_log(root, pkg.header.film_id)
    entries = {t.take_id: t for t in log.takes}
    title = [(l.text, l.size) for l in section.title] or [(pkg.header.title, 96)]
    end = [(l.text, l.size) for l in section.end] or [(pkg.header.title, 64),
                                                      ("All characters are fictional.", 30)]
    out = Path(out)
    with tempfile.TemporaryDirectory() as tmp:
        work = Path(tmp)
        clips: list[Path] = []
        for event in section.events:
            dst = work / f"{event.event_id}.mp4"
            if event.kind == "CARD":
                context_card_clip(dst, list(event.card_lines), float(event.card_duration_s))
            else:
                src = resolve_clip(root, entries[event.take_id].output_file, clips_dir)
                if event.src_in_s == 0 and event.src_out_s is None:
                    shutil.copyfile(src, dst)
                else:
                    _trim(src, dst, event.src_in_s, event.src_out_s)
            clips.append(dst)
        overlays = [Overlay(generation_id=t.event_id, start_s=t.start_s, end_s=t.end_s,
                            png=str(identity_tag_png(work / f"tag_{i:02}.png", t.label, t.relation, t.anchor_x,
                                                     t.anchor_y)))
                    for i, t in enumerate(section.tags, 1)]
        assemble(clips, out, cues=cues or [], title_lines=title, end_lines=end, title_s=section.title_s,
                 end_s=section.end_s, overlays=overlays)
        actual = {e.event_id: probe_video_duration(c) for e, c in zip(section.events, clips)}
    cursor = section.title_s
    placed = []
    for event in section.events:
        placed.append({"event_id": event.event_id, "start_s": round(cursor, 6), "duration_s": round(actual[event.event_id], 6)})
        cursor += actual[event.event_id]
    total = probe_video_duration(out)
    report = {"film_id": pkg.header.film_id, "output": str(out), "output_sha256": _sha256(out),
              "total_s": round(total, 6), "planned": timeline(section, durations), "rendered_events": placed,
              "problems": problems}
    report_path = out.with_suffix(".cut.json")
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    report["report"] = str(report_path)
    return report
