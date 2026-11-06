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
nothing, J/L cuts without source handles). ``render_cut`` renders through `drama.post.assemble` (title card, graded
clips, end card, AI label, tags). An EDL of hard cuts goes straight through it, byte-for-byte the legacy path. An EDL with
a dissolve, a dip to black or a J/L cut first builds the body in one FFmpeg graph (xfade for the picture, per-event audio
slices placed on the clock with their J/L handles, overlapping slices cross-faded) and hands that body to the same
assembly. ``rhythm_report`` sets the used shot lengths against the direction's pacing and flags holds longer than
planned; ``cut_continuity`` checks every cut between two takes (end/start state, axis side, eyeline, jump cut).
Loudness, subtitles and credits belong to P5.
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


def timeline(section: EditSection, durations: dict[str, float],
             lengths: dict[str, float] | None = None) -> dict[str, Any]:
    """Place the events on the final clock. ``durations`` maps take_id -> clip seconds (cards need none); ``lengths``
    (event_id -> used seconds) overrides what the declaration implies, e.g. with probed card clips. All times are
    seconds from the start of the film, title card included."""
    placed: list[dict[str, Any]] = []
    cursor = section.title_s
    for index, event in enumerate(section.events):
        length = (lengths or {}).get(event.event_id)
        if length is None:
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


def probe_audio_duration(path: Path) -> float:
    """Seconds of the first audio stream; 0.0 when the clip has no sound (an L-cut then has no handle)."""
    out = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "a:0", "-show_entries", "stream=duration",
                          "-of", "csv=p=0", str(path)], capture_output=True, text=True, check=True)
    text = (out.stdout.strip().splitlines() or [""])[0].strip()
    return float(text) if text and text != "N/A" else 0.0


def resolve_clip(root: Path, output_file: str, clips_dir: Path | None = None) -> Path:
    return Path(clips_dir) / output_file if clips_dir else Path(root) / "media" / "takes" / output_file


def resolved_cards(pkg: Any, section: EditSection) -> tuple[list[tuple[str, int]], list[tuple[str, int]]]:
    """The title and end card lines as rendered (an empty list in the EDL falls back to the film title)."""
    title = [(l.text, l.size) for l in section.title] or [(pkg.header.title, 96)]
    end = [(l.text, l.size) for l in section.end] or [(pkg.header.title, 64), ("All characters are fictional.", 30)]
    return title, end


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def edit_problems(pkg: Any, section: EditSection, *, clips_dir: Path | None = None, require_accepted: bool = False,
                  probe: Callable[[Path], float] | None = None,
                  audio_probe: Callable[[Path], float] | None = None) -> tuple[list[dict[str, str]], dict[str, float]]:
    """(problems, durations). Each problem: {code, severity BLOCK|WARN, event_id, detail}. ``durations`` has every take
    that could be probed. ``require_accepted`` (a fine cut / picture lock) turns an unreviewed take from WARN to BLOCK."""
    from film_pipeline.production.takes import load_log
    audio_probe = audio_probe or (probe_audio_duration if probe is None else probe)
    probe = probe or probe_duration
    root = Path(pkg.root)
    log = load_log(root, pkg.header.film_id)
    entries = {t.take_id: t for t in log.takes}
    shots = pkg.typed.get("shots")
    versions = {g.generation_id: g.version for g in shots.generations} if shots is not None else {}
    problems: list[dict[str, str]] = []
    durations: dict[str, float] = {}
    clips_by_take: dict[str, Path] = {}

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
        clips_by_take[event.take_id] = clip
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
    for index, event in enumerate(section.events):
        j, l = event.audio.j_cut_s, event.audio.l_cut_s
        if not (j or l):
            continue
        if index == 0:
            add("AUDIO_CUT_ON_FIRST", "BLOCK", event.event_id, "the first event has no previous sound to split with")
            continue
        prev = section.events[index - 1]
        if j and (event.kind != "TAKE" or event.src_in_s + FRAME_S / 2 < j):
            add("JCUT_NO_HANDLE", "BLOCK", event.event_id,
                f"J-cut of {j}s needs {j}s of source before src_in_s ({event.src_in_s}s) of a take")
        if j and prev.event_id in lengths and j >= lengths[prev.event_id]:
            add("JCUT_TOO_LONG", "BLOCK", event.event_id, f"J-cut of {j}s is longer than {prev.event_id}")
        if l:
            clip_s = None
            if prev.kind == "TAKE" and prev.take_id in clips_by_take:   # the sound handle, not the picture length
                try:
                    clip_s = audio_probe(clips_by_take[prev.take_id])
                except (subprocess.CalledProcessError, OSError, ValueError):
                    clip_s = None
            if prev.kind != "TAKE" or clip_s is None or prev.src_out_s is None or prev.src_out_s + l > clip_s + FRAME_S:
                add("LCUT_NO_HANDLE", "BLOCK", event.event_id,
                    f"L-cut of {l}s needs {l}s of {prev.event_id} sound after its src_out_s (set src_out_s earlier)")
            if event.event_id in lengths and l >= lengths[event.event_id]:
                add("LCUT_TOO_LONG", "BLOCK", event.event_id, f"L-cut of {l}s is longer than {event.event_id}")

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

def gain_filter(gains: tuple[float, float, float] | None) -> str:
    """ffmpeg filter that scales the R, G, B channels (the colour match of a shot); empty when there is none."""
    return "" if gains is None else f"colorchannelmixer=rr={gains[0]:.5f}:gg={gains[1]:.5f}:bb={gains[2]:.5f}"


class Reframe(ContractModel):
    """A crop box inside the frame (fractions of its width/height) that is scaled back up, plus optional stabilising.
    Kept outside ``05_edit.json`` (``titles/reframe.json``) so the EDL bytes and the picture lock do not move."""

    x: float = Field(default=0.0, ge=0.0, le=1.0)
    y: float = Field(default=0.0, ge=0.0, le=1.0)
    w: float = Field(default=1.0, gt=0.0, le=1.0)
    h: float = Field(default=1.0, gt=0.0, le=1.0)
    stabilize: bool = False

    @model_validator(mode="after")
    def _inside(self) -> "Reframe":
        if self.x + self.w > 1.0 + 1e-6 or self.y + self.h > 1.0 + 1e-6:
            raise ValueError("the crop box leaves the frame")
        return self


def reframe_filter(r: Reframe | None) -> str:
    """ffmpeg filters for a reframe (deshake first, then the crop with even sides); empty for none/identity."""
    if r is None:
        return ""
    parts = ["deshake"] if r.stabilize else []
    if (r.x, r.y, r.w, r.h) != (0.0, 0.0, 1.0, 1.0):
        parts.append(f"crop=trunc(iw*{r.w:.6f}/2)*2:trunc(ih*{r.h:.6f}/2)*2:iw*{r.x:.6f}:ih*{r.y:.6f}")
    return ",".join(parts)


def _trim(src: Path, dst: Path, start: float, end: float | None,
          gains: tuple[float, float, float] | None = None, reframe: Reframe | None = None) -> Path:
    cmd = ["ffmpeg", "-v", "error", "-y", "-ss", f"{start:.6f}", "-i", str(src)]
    if end is not None:
        cmd += ["-t", f"{end - start:.6f}"]
    vf = ",".join(f for f in (reframe_filter(reframe), gain_filter(gains)) if f)
    if vf:
        cmd += ["-vf", vf]
    cmd += ["-r", str(FPS), "-c:v", "libx264", "-pix_fmt", "yuv420p", "-c:a", "aac", "-ar", "48000", str(dst)]
    subprocess.run(cmd, check=True)
    return dst


def _is_fine(section: EditSection) -> bool:
    return any(e.transition.type not in _HARD or e.audio.j_cut_s or e.audio.l_cut_s for e in section.events)


def fine_graph(section: EditSection, starts: list[float], lengths: list[float], in_points: list[float],
               body_s: float, grade: str, w: int, h: int,
               gains: list[tuple[float, float, float] | None] | None = None,
               reframes: list[Reframe | None] | None = None) -> list[str]:
    """FFmpeg filter graph of the body: inputs 0..n-1 are the event sources, input n is a silent bed of ``body_s``.
    ``starts`` are body-relative picture starts (a dissolve already overlaps), ``lengths`` the used picture seconds,
    ``in_points`` the source second each event's picture starts at. Outputs: [vout] and [aout]."""
    events, n = section.events, len(section.events)
    fl: list[str] = []
    for i in range(n):
        a, b = in_points[i], in_points[i] + lengths[i]
        match = gain_filter(gains[i]) if gains else ""
        frame = reframe_filter(reframes[i]) if reframes else ""
        fl.append(f"[{i}:v]fps={FPS},settb=1/{FPS},{frame + ',' if frame else ''}scale={w}:{h},setsar=1,"
                  f"{match + ',' if match else ''}{grade},format=yuv420p,"
                  f"trim=start={a:.6f}:end={b:.6f},setpts=PTS-STARTPTS[v{i}]")
    acc = "v0"
    for i in range(1, n):
        t = events[i].transition
        label = "vout" if i == n - 1 else f"x{i}"
        if t.type in _HARD:
            # concat leaves a 1/1000000 time base; xfade wants both inputs on the same one
            fl.append(f"[{acc}][v{i}]concat=n=2:v=1:a=0,fps={FPS},settb=1/{FPS}[{label}]")
        else:
            kind = "fade" if t.type == "DISSOLVE" else "fadeblack"
            fl.append(f"[{acc}][v{i}]xfade=transition={kind}:duration={t.duration_s:.6f}:offset={starts[i]:.6f},"
                      f"fps={FPS},settb=1/{FPS}[{label}]")
        acc = label
    if n == 1:
        fl.append("[v0]null[vout]")
    labels = []
    for i in range(n):
        j = events[i].audio.j_cut_s
        l_next = events[i + 1].audio.l_cut_s if i + 1 < n else 0.0
        d_in = events[i].transition.duration_s if i else 0.0
        d_out = events[i + 1].transition.duration_s if i + 1 < n else 0.0
        a0, a1 = in_points[i] - j, in_points[i] + lengths[i] + l_next
        place = starts[i] - j                      # body second the sound starts at; before 0 means it is cut off
        if place < 0:
            a0 -= place                           # drop the part that would play before the film starts
        span = a1 - a0
        fade_in = d_in if d_in else (min(j, 0.3) if j else 0.05)
        fade_out = d_out if d_out else (min(l_next, 0.3) if l_next else 0.08)
        ms = max(0, round(place * 1000))
        fl.append(f"[{i}:a]aresample=48000,aformat=channel_layouts=stereo,atrim=start={a0:.6f}:end={a1:.6f},"
                  f"asetpts=PTS-STARTPTS,afade=t=in:d={fade_in:.3f},afade=t=out:st={max(0.0, span - fade_out):.3f}:"
                  f"d={fade_out:.3f},adelay={ms}|{ms}[a{i}]")
        labels.append(f"[a{i}]")
    fl.append(f"[{n}:a]{''.join(labels)}amix=inputs={n + 1}:normalize=0:duration=first,atrim=0:{body_s:.6f}[aout]")
    return fl


def render_cut(pkg: Any, section: EditSection, out: Path, *, clips_dir: Path | None = None,
               require_accepted: bool = False, cues: list | None = None,
               corrections: dict[str, tuple[float, float, float]] | None = None, look: str | None = None,
               reframes: dict[str, Reframe] | None = None, title_lines: list[tuple[str, int]] | None = None,
               end_lines: list[tuple[str, int]] | None = None) -> dict[str, Any]:
    """Render the EDL to ``out`` and return the report. Raises ValueError listing BLOCK problems. Cues, if given, are
    SubtitleCue keyed by event_id with times in seconds of the used part of that event. ``corrections`` maps a take id
    to the per-channel gains of its colour match (production/color.py); ``look`` replaces the global grade; ``reframes``
    maps an event id to its crop box (production/titles.py); ``title_lines`` / ``end_lines`` replace the cards."""
    from film_pipeline.drama.post import (GRADE as DEFAULT_GRADE, H, W, Overlay, assemble, context_card_clip,
                                          identity_tag_png, probe_video_duration)
    from film_pipeline.production.takes import load_log
    GRADE = look or DEFAULT_GRADE
    corrections = corrections or {}
    gains = [corrections.get(e.take_id) if e.kind == "TAKE" else None for e in section.events]
    boxes = [(reframes or {}).get(e.event_id) if e.kind == "TAKE" else None for e in section.events]
    problems, durations = edit_problems(pkg, section, clips_dir=clips_dir, require_accepted=require_accepted)
    blocks = [p for p in problems if p["severity"] == "BLOCK"]
    if blocks:
        raise ValueError("; ".join(f"{p['code']} {p['event_id']}: {p['detail']}" for p in blocks))
    root = Path(pkg.root)
    entries = {t.take_id: t for t in load_log(root, pkg.header.film_id).takes}
    title, end = resolved_cards(pkg, section)
    title, end = title_lines or title, end_lines or end
    fine = _is_fine(section)
    out = Path(out)
    out.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory() as tmp:
        work = Path(tmp)
        sources: list[Path] = []
        lengths: dict[str, float] = {}
        for event in section.events:
            if event.kind == "CARD":
                src = context_card_clip(work / f"{event.event_id}.mp4", list(event.card_lines),
                                        float(event.card_duration_s))
                lengths[event.event_id] = probe_video_duration(src)
            else:
                src = resolve_clip(root, entries[event.take_id].output_file, clips_dir)
                lengths[event.event_id] = source_length(event, durations[event.take_id])
            sources.append(src)
        plan = timeline(section, durations, lengths)
        sub_cues = list(cues or [])

        def tag_png(index: int, t: TagEvent) -> str:
            return str(identity_tag_png(work / f"tag_{index:02}.png", t.label, t.relation, t.anchor_x, t.anchor_y))

        if fine:
            starts = [e["start_s"] - section.title_s for e in plan["events"]]
            body_s = plan["body_end_s"] - section.title_s
            body = work / "body.mp4"
            graph = fine_graph(section, starts, [lengths[e.event_id] for e in section.events],
                               [e.src_in_s for e in section.events], body_s, GRADE, W, H, gains, boxes)
            cmd = ["ffmpeg", "-v", "error", "-y"]
            for src in sources:
                cmd += ["-i", str(src)]
            cmd += ["-f", "lavfi", "-t", f"{body_s:.6f}", "-i", "anullsrc=r=48000:cl=stereo",
                    "-filter_complex", ";".join(graph), "-map", "[vout]", "-map", "[aout]", "-t", f"{body_s:.6f}",
                    "-r", str(FPS), "-c:v", "libx264", "-crf", "14", "-preset", "fast", "-pix_fmt", "yuv420p",
                    "-c:a", "aac", "-b:a", "256k", str(body)]
            subprocess.run(cmd, check=True)
            at = {e.event_id: starts[i] for i, e in enumerate(section.events)}
            overlays = [Overlay(generation_id="body", start_s=at[t.event_id] + t.start_s,
                                end_s=at[t.event_id] + t.end_s, png=tag_png(i, t))
                        for i, t in enumerate(section.tags, 1)]
            sub_cues = [c.model_copy(update={"generation_id": "body", "start_s": at[c.generation_id] + c.start_s,
                                             "end_s": at[c.generation_id] + c.end_s}) for c in sub_cues]
            assemble([body], out, cues=sub_cues, title_lines=title, end_lines=end, title_s=section.title_s,
                     end_s=section.end_s, overlays=overlays, grade="null")
        else:
            clips: list[Path] = []
            for event, src, gain, box in zip(section.events, sources, gains, boxes):
                if event.kind == "CARD":
                    clips.append(src)
                    continue
                dst = work / f"{event.event_id}.mp4"
                if event.src_in_s == 0 and event.src_out_s is None and gain is None and not reframe_filter(box):
                    shutil.copyfile(src, dst)
                else:
                    _trim(src, dst, event.src_in_s, event.src_out_s, gain, box)
                clips.append(dst)
            overlays = [Overlay(generation_id=t.event_id, start_s=t.start_s, end_s=t.end_s, png=tag_png(i, t))
                        for i, t in enumerate(section.tags, 1)]
            assemble(clips, out, cues=sub_cues, title_lines=title, end_lines=end, title_s=section.title_s,
                     end_s=section.end_s, overlays=overlays, grade=GRADE)
            lengths = {e.event_id: probe_video_duration(c) for e, c in zip(section.events, clips)}
            plan = timeline(section, durations, lengths)
    total = probe_video_duration(out)
    report = {"film_id": pkg.header.film_id, "output": str(out), "output_sha256": _sha256(out),
              "path": "fine" if fine else "hard", "total_s": round(total, 6), "planned": plan,
              "rendered_events": [{"event_id": e["event_id"], "start_s": e["start_s"], "duration_s": e["duration_s"]}
                                  for e in plan["events"]],
              "problems": problems}
    report_path = out.with_suffix(".cut.json")
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    report["report"] = str(report_path)
    return report


# ------------------------------------------------------------------ rhythm and continuity across cuts

PACE_TOLERANCE = 0.30  # a scene's average used shot length may differ from the target by this fraction
UNPLANNED_HOLD_FACTOR = 1.5  # a shot longer than this x target, with no declared hold, is an unplanned hold


def used_lengths(section: EditSection, durations: dict[str, float]) -> dict[str, float]:
    """event_id -> used picture seconds for the events whose length is known."""
    out: dict[str, float] = {}
    for event in section.events:
        try:
            out[event.event_id] = source_length(event, durations.get(event.take_id))
        except ValueError:
            pass
    return out


def rhythm_report(pkg: Any, section: EditSection, durations: dict[str, float]) -> dict[str, Any]:
    """Used shot lengths per scene against `02_direction` pacing; advisory (WARN only). A scene whose average shot is
    30% off its target is flagged; a declared hold buys its seconds over the target for that shot, so a held shot longer
    than target + hold is over plan, and a shot over 1.5 x target with no hold is an unplanned hold."""
    direction, shots = pkg.typed.get("direction"), pkg.typed.get("shots")
    if direction is None or shots is None:
        return {"scenes": [], "issues": [], "skipped": "needs valid 02_direction.json and 04_shots.json"}
    scene_of = {g.generation_id: g.scene_id for g in shots.generations}
    lengths = used_lengths(section, durations)
    takes = [e for e in section.events if e.kind == "TAKE" and e.event_id in lengths]
    issues: list[dict[str, str]] = []
    rows: list[dict[str, Any]] = []

    def add(code: str, scene: str, detail: str) -> None:
        issues.append({"code": code, "severity": "WARN", "scene_id": scene, "detail": detail})

    for scene_id, sd in direction.scenes.items():
        inside = [e for e in takes if scene_of.get(e.generation_id) == scene_id]
        if not inside:
            continue
        target = sd.pacing.target_avg_shot_s
        secs = [lengths[e.event_id] for e in inside]
        avg = sum(secs) / len(secs)
        rows.append({"scene_id": scene_id, "shots": len(inside), "total_s": round(sum(secs), 3),
                     "avg_s": round(avg, 3), "target_avg_shot_s": target, "ratio": round(avg / target, 3)})
        if avg > target * (1 + PACE_TOLERANCE):
            add("SCENE_PACE_SLOW", scene_id, f"average shot {avg:.1f}s vs target {target:g}s")
        elif avg < target * (1 - PACE_TOLERANCE):
            add("SCENE_PACE_FAST", scene_id, f"average shot {avg:.1f}s vs target {target:g}s")
        holds = {h.generation_id: h for h in sd.pacing.holds}
        for gid, hold in holds.items():
            events = [e for e in inside if e.generation_id == gid]
            if not events:
                add("HOLD_NOT_IN_CUT", scene_id, f"planned hold on {gid} ({hold.seconds:g}s) has no event in the cut")
            for e in events:
                if lengths[e.event_id] > target + hold.seconds + FRAME_S:  # a hold buys time over the average shot
                    add("HOLD_OVER_PLAN", scene_id,
                        f"{e.event_id} runs {lengths[e.event_id]:.1f}s; target {target:g}s + planned hold "
                        f"{hold.seconds:g}s allows {target + hold.seconds:g}s ({hold.why})")
        for e in inside:
            if e.generation_id not in holds and lengths[e.event_id] > target * UNPLANNED_HOLD_FACTOR:
                add("LONG_SHOT_UNPLANNED", scene_id,
                    f"{e.event_id} runs {lengths[e.event_id]:.1f}s (> {UNPLANNED_HOLD_FACTOR:g} x target {target:g}s) "
                    "with no declared hold")
    return {"scenes": rows, "issues": issues}


def cut_continuity(pkg: Any, section: EditSection, durations: dict[str, float]) -> dict[str, Any]:
    """Checks at every cut between two takes (a card between them is a deliberate break and is skipped):

    * end/start state, through `continuity._handoff`; only a take chained to the previous one (`previous_generation_id`)
      has to match exactly, and only when the cut keeps the ends of both clips - at a trimmed point the state is unknown;
    * axis side: a REVERSE camera against an ESTABLISHED one in the same scene crosses the line, which flips the
      eyelines (`AxisBook.eyeline_toward_partner`);
    * jump cut: same scene, same size/angle on the same subject.
    A BLOCK finding means a chained handoff that cannot work; everything else is for the human at CUT review."""
    from film_pipeline.production import continuity as C
    pre, shots = pkg.typed.get("preprod"), pkg.typed.get("shots")
    if pre is None or shots is None:
        return {"cuts": 0, "issues": [], "skipped": "needs valid 03_preprod.json and 04_shots.json"}
    by_id = {g.generation_id: g for g in shots.generations}
    issues: list[dict[str, Any]] = []
    checked = 0

    def add(code: str, severity: str, a: EditEvent, b: EditEvent, detail: str) -> None:
        issues.append({"code": code, "severity": severity, "between": [a.event_id, b.event_id], "detail": detail})

    for a, b in zip(section.events, section.events[1:]):
        if a.kind != "TAKE" or b.kind != "TAKE" or a.generation_id not in by_id or b.generation_id not in by_id:
            continue
        ga, gb = by_id[a.generation_id], by_id[b.generation_id]
        checked += 1
        same_scene = ga.scene_id == gb.scene_id
        clip_a = durations.get(a.take_id)
        tail_kept = a.src_out_s is None or (clip_a is not None and a.src_out_s >= clip_a - FRAME_S)
        head_kept = b.src_in_s <= FRAME_S
        chained = gb.previous_generation_id == ga.generation_id
        if chained and not (tail_kept and head_kept):
            add("TRIMMED_HANDOFF", "WARN", a, b,
                f"{gb.generation_id} continues {ga.generation_id} but the cut is not at the clip ends: the shared "
                "state cannot be proven, check it at CUT level")
        elif tail_kept and head_kept and ga.end_state in pre.states and gb.start_state in pre.states:
            found: list[Any] = []
            C._handoff(gb.generation_id, ga.generation_id, same_scene and chained, pre.states[ga.end_state],
                       pre.states[gb.start_state], found)
            for f in found:
                add(f.check, f.severity, a, b, f.detail)
        if not same_scene:
            continue
        ca, cb = ga.camera, gb.camera
        if ca is not None and cb is not None and ca.side != cb.side:
            book = pre.scenes[ga.scene_id].axis if ga.scene_id in pre.scenes else None
            eyes = ""
            if book is not None and len(book.axis_pair) >= 2:
                shared = [c for c in book.axis_pair if c in ga.visible and c in gb.visible]
                eyes = "; eyelines flip for " + ", ".join(
                    f"{c} ({book.eyeline_toward_partner(c)} -> {'screen-left' if book.eyeline_toward_partner(c) == 'screen-right' else 'screen-right'})"
                    for c in shared) if shared else ""
            add("AXIS_SIDE_CHANGE", "WARN", a, b,
                f"camera goes {ca.side} -> {cb.side} inside {ga.scene_id}: the cut crosses the line of action{eyes}")
        if ca is not None and cb is not None and not chained and ca.size == cb.size and ca.angle == cb.angle \
                and ga.subject and ga.subject == gb.subject and ca.side == cb.side:
            add("JUMP_CUT_RISK", "WARN", a, b,
                f"same scene, same {ca.size} {ca.angle} on {ga.subject}: reads as a jump cut unless the action bridges it")
    return {"cuts": checked, "issues": issues}
