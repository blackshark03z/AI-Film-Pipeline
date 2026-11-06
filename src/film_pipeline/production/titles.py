"""Titles, credits, subtitles and reframing (categories 126 reframing, 128 titles & credits, 129 subtitles, 130 final composite).

* **Credits** - ``credits_lines(pkg, lang)`` builds the end card from the package: the title, the characters (the cast of
  ``03_preprod.json``), the AI disclosure line (generators from the disclosure record when given, else the generic notice), the
  attributions owed by the cleared sound assets (``sound_rights.attributions``) and the fiction line. ``fit_lines`` shrinks
  lines to the frame and blocks (``CREDITS_OVERFLOW``) when they cannot fit. The fixed words exist in English and Vietnamese.
* **Subtitles** - the text of every dialogue line comes from the script (the lines a shot declares). Timing, per TAKE event
  of the EDL, is: an explicit entry of ``titles/cues.json`` (``{"cues": [{"event_id", "line_no", "start_s", "end_s"}]}``,
  seconds into the used part of the event) or, otherwise, the speech windows ``silencedetect`` finds in the used part of the
  take, matched to the lines (1:1; extra windows merged over the smallest gap; too few windows shared out by word count).
  Anything that is not a clean 1:1 match is a WARN ``DIALOGUE_UNALIGNED`` so a human checks the timing. The picture burns in
  the source language; sidecar SRTs (title, cards, identity tags, dialogue, credits) are written for the source language and,
  from ``direction.translations``, Vietnamese - a missing translation blocks that sidecar (``TRANSLATION_MISSING``).
* **Reframe** - ``titles/reframe.json`` (``{"events": {event_id: {x, y, w, h, stabilize}}}``) crops a box of the frame and scales
  it back up (a punch-in / recomposition); ``stabilize`` adds ffmpeg ``deshake``. The box must keep the frame's aspect
  (``w == h``, fractions of the frame), a box narrower than half the frame warns (``REFRAME_SOFT``: upscaled over 2x), a
  reframed event with identity tags warns (``REFRAME_TAG``: the face moves under the tag). The render applies it
  (``edit.render_cut(reframes=...)``); the takes are untouched. 9:16 deliverables are out of scope here.
"""
from __future__ import annotations

import json
import re
import subprocess
from pathlib import Path
from typing import Any

from pydantic import Field

from film_pipeline.core import ContractModel
from film_pipeline.production.edit import (EditSection, Reframe, edit_problems, resolve_clip, resolved_cards, source_length,
                                           timeline)

MAX_CPS = 20.0          # characters per second a viewer can read
MIN_CUE_S = 0.7
MIN_SPEECH_S = 0.2
MAX_CARD_HEIGHT, MAX_CARD_WIDTH, MIN_FONT = 620, 1160, 16

LABELS: dict[str, dict[str, str]] = {
    "en": {"characters": "Characters", "ai_generic": "Video, images and voices generated with AI.",
           "ai_with": "Generated with AI", "sound": "Music and sound", "fiction": "A work of fiction. All characters are fictional.",
           "synthetic": "Synthetic characters: faces and voices are AI-generated."},
    "vi": {"characters": "Nhân vật", "ai_generic": "Video, hình ảnh và giọng nói do AI tạo ra.",
           "ai_with": "Tạo bằng AI", "sound": "Âm nhạc và âm thanh", "fiction": "Tác phẩm hư cấu. Mọi nhân vật đều là hư cấu.",
           "synthetic": "Nhân vật tổng hợp: gương mặt và giọng nói do AI tạo ra."},
}


class ReframePlan(ContractModel):
    events: dict[str, Reframe] = Field(default_factory=dict)


class CueTiming(ContractModel):
    event_id: str
    line_no: int
    start_s: float = Field(ge=0)
    end_s: float = Field(gt=0)


class CueFile(ContractModel):
    cues: list[CueTiming] = Field(default_factory=list)


def titles_dir(root: Path) -> Path:
    return Path(root) / "titles"


def _load(model: Any, path: Path) -> Any:
    return model.model_validate_json(path.read_text(encoding="utf-8")) if path.is_file() else model()


def load_reframes(root: Path) -> ReframePlan:
    return _load(ReframePlan, titles_dir(root) / "reframe.json")


def load_cue_file(root: Path) -> CueFile:
    return _load(CueFile, titles_dir(root) / "cues.json")


# ------------------------------------------------------------------ credits

def _text_width(text: str, size: int) -> float:
    from PIL import Image, ImageDraw, ImageFont
    from film_pipeline.drama.post import BOLD, FONT
    font = ImageFont.truetype(BOLD if size > 40 else FONT, size)
    return ImageDraw.Draw(Image.new("RGB", (1, 1))).textlength(text, font=font)


def fit_lines(lines: list[tuple[str, int]]) -> tuple[list[tuple[str, int]], list[dict[str, str]]]:
    """Shrink each line to the card width, then all but the first to the card height; BLOCK when the minimum does not fit."""
    out, problems = [], []
    for i, (text, size) in enumerate(lines):
        while size > MIN_FONT and _text_width(text, size) > MAX_CARD_WIDTH:
            size -= 1
        if _text_width(text, size) > MAX_CARD_WIDTH:
            problems.append({"code": "CREDITS_OVERFLOW", "severity": "BLOCK", "detail": f"line {i + 1} is wider than the card: {text[:40]!r}"})
        out.append((text, size))
    height = lambda ls: sum(s for _, s in ls) + 20 * (len(ls) - 1)  # noqa: E731 - the layout of drama.post.title_card
    while height(out) > MAX_CARD_HEIGHT and any(s > MIN_FONT for _, s in out[1:]):
        out = [out[0]] + [(t, max(MIN_FONT, s - 1)) for t, s in out[1:]]
    if height(out) > MAX_CARD_HEIGHT:
        problems.append({"code": "CREDITS_OVERFLOW", "severity": "BLOCK",
                         "detail": f"{len(out)} lines need {height(out)} px, the card has {MAX_CARD_HEIGHT}"})
    return out, problems


def cast_names(pkg: Any) -> list[str]:
    pre = pkg.typed.get("preprod")
    return list(pre.characters) if pre is not None else []


def credits_lines(pkg: Any, lang: str = "en", *, generators: str = "") -> tuple[list[tuple[str, int]], list[dict[str, str]]]:
    """(lines, problems) of the end card in ``lang`` ('en' / 'vi')."""
    from film_pipeline.production.sound_rights import attributions
    words = LABELS[lang]
    lines: list[tuple[str, int]] = [(pkg.header.title, 64)]
    names = cast_names(pkg)
    if names:
        lines.append((f"{words['characters']}: {' · '.join(names)}", 30))
        lines.append((words["synthetic"], 24))
    lines.append((f"{words['ai_with']}: {generators}" if generators else words["ai_generic"], 26))
    owed = attributions(pkg)
    if owed:
        lines.append((words["sound"], 24))
        lines += [(a, 22) for a in owed]
    lines.append((words["fiction"], 28))
    return fit_lines(lines)


# ------------------------------------------------------------------ dialogue timing

def speech_windows(clip: Path, start_s: float, length_s: float, *, noise_db: float = -40.0,
                   min_silence_s: float = 0.25) -> list[tuple[float, float]]:
    """Windows (seconds into the used part) where the clip's sound is above ``noise_db``."""
    done = subprocess.run(["ffmpeg", "-nostats", "-v", "info", "-ss", f"{start_s:.6f}", "-t", f"{length_s:.6f}", "-i", str(clip),
                           "-vn", "-af", f"silencedetect=noise={noise_db}dB:d={min_silence_s}", "-f", "null", "-"],
                          capture_output=True, text=True, check=True)
    silences: list[list[float]] = []
    for line in done.stderr.splitlines():
        if (m := re.search(r"silence_start:\s*(-?[\d.]+)", line)):
            silences.append([max(0.0, float(m.group(1))), length_s])
        elif (m := re.search(r"silence_end:\s*(-?[\d.]+)", line)) and silences:
            silences[-1][1] = min(length_s, float(m.group(1)))
    windows, cursor = [], 0.0
    for a, b in silences:
        if a - cursor >= MIN_SPEECH_S:
            windows.append((round(cursor, 3), round(a, 3)))
        cursor = max(cursor, b)
    if length_s - cursor >= MIN_SPEECH_S:
        windows.append((round(cursor, 3), round(length_s, 3)))
    return windows


def allocate(windows: list[tuple[float, float]], words: list[int]) -> list[tuple[float, float]]:
    """One (start, end) per line: windows 1:1, extra windows merged over the smallest gap, too few shared out by words."""
    m, wins = len(words), [tuple(w) for w in windows]
    if m == 0 or not wins:
        return []
    while len(wins) > m:
        gap, at = min((wins[i + 1][0] - wins[i][1], i) for i in range(len(wins) - 1))
        wins[at:at + 2] = [(wins[at][0], wins[at + 1][1])]
    if len(wins) == m:
        return [(a, b) for a, b in wins]
    total, speech = float(sum(words)), sum(b - a for a, b in wins)

    def at(speech_t: float, closing: bool) -> float:
        used = 0.0
        for a, b in wins:
            span = b - a
            if speech_t < used + span - 1e-9 or (closing and speech_t <= used + span + 1e-9):
                return a + max(0.0, speech_t - used)
            used += span
        return wins[-1][1]

    out, done = [], 0.0
    for w in words:
        lo, hi = done / total * speech, (done + w) / total * speech
        out.append((round(at(lo, False), 3), round(at(hi, True), 3)))
        done += w
    return out


def _shot_lines(pkg: Any, gid: str) -> list[Any]:
    shots = pkg.typed.get("shots")
    if shots is None or pkg.script is None:
        return []
    decl = next((g for g in shots.generations if g.generation_id == gid), None)
    if decl is None:
        return []
    by_no = {(s.scene_id, e.line_no): e for s in pkg.script.scenes for e in s.elements if e.kind == "dialogue"}
    return [by_no[(decl.scene_id, n)] for n in decl.dialogue if (decl.scene_id, n) in by_no]


def dialogue_cues(pkg: Any, section: EditSection, durations: dict[str, float], *,
                  clips_dir: Path | None = None) -> dict[str, Any]:
    """{cues: [SubtitleCue keyed by event_id], rows, problems} for the TAKE events of the EDL."""
    from film_pipeline.drama.post import SubtitleCue
    from film_pipeline.production.takes import load_log
    root = Path(pkg.root)
    entries = {t.take_id: t for t in load_log(root, pkg.header.film_id).takes}
    given = {(c.event_id, c.line_no): c for c in load_cue_file(root).cues}
    cues, rows, problems = [], [], []
    for event in section.events:
        if event.kind != "TAKE":
            continue
        lines = _shot_lines(pkg, event.generation_id)
        if not lines:
            continue
        length = source_length(event, durations.get(event.take_id))
        spans: dict[int, tuple[float, float, str]] = {l.line_no: (given[(event.event_id, l.line_no)].start_s,
                                                                   given[(event.event_id, l.line_no)].end_s, "override")
                                                      for l in lines if (event.event_id, l.line_no) in given}
        rest = [l for l in lines if l.line_no not in spans]
        if rest:
            windows = []
            clip = resolve_clip(root, entries[event.take_id].output_file, clips_dir) if event.take_id in entries else None
            if clip is not None and clip.is_file():
                windows = speech_windows(clip, event.src_in_s, length)
            placed = allocate(windows, [len(l.text.split()) or 1 for l in rest])
            source = "windows"
            if not placed:
                source = "even"
                step = length / len(rest)
                placed = [(round(i * step, 3), round((i + 1) * step, 3)) for i in range(len(rest))]
                problems.append({"code": "DIALOGUE_NO_SPEECH", "severity": "WARN", "event_id": event.event_id,
                                 "detail": f"no speech found in {event.event_id}: {len(rest)} line(s) spread evenly"})
            elif len(windows) != len(rest):
                problems.append({"code": "DIALOGUE_UNALIGNED", "severity": "WARN", "event_id": event.event_id,
                                 "detail": f"{event.event_id}: {len(windows)} speech window(s) for {len(rest)} line(s); check the timing"})
            for line, (a, b) in zip(rest, placed):
                spans[line.line_no] = (a, b, source)
        for line in lines:
            a, b, source = spans[line.line_no]
            a, b = max(0.0, a), min(length, b)
            if b - a <= 1e-6:
                problems.append({"code": "CUE_OUTSIDE_EVENT", "severity": "BLOCK", "event_id": event.event_id,
                                 "detail": f"line {line.line_no} lies outside the used {length:.2f} s of {event.event_id}"})
                continue
            if b - a < MIN_CUE_S:
                problems.append({"code": "CUE_TOO_SHORT", "severity": "WARN", "event_id": event.event_id,
                                 "detail": f"line {line.line_no} shows for {b - a:.2f} s (< {MIN_CUE_S})"})
            if len(line.text) / (b - a) > MAX_CPS:
                problems.append({"code": "CUE_TOO_FAST", "severity": "WARN", "event_id": event.event_id,
                                 "detail": f"line {line.line_no}: {len(line.text) / (b - a):.0f} characters/s (> {MAX_CPS:g})"})
            cues.append(SubtitleCue(generation_id=event.event_id, start_s=a, end_s=b, text=line.text, speaker_window=(0.0, length)))
            rows.append({"event_id": event.event_id, "line_no": line.line_no, "character": line.character, "text": line.text,
                         "start_s": round(a, 3), "end_s": round(b, 3), "source": source})
    return {"cues": cues, "rows": rows, "problems": problems}


# ------------------------------------------------------------------ sidecars

def translator(pkg: Any, lang: str):
    """(callable text -> text|None, error) for ``lang``: the source language is the identity, 'vi' reads the translations."""
    source = pkg.header.language
    if lang == source:
        return (lambda text: text), ""
    direction = pkg.typed.get("direction")
    if lang == "vi" and source == "en" and direction is not None:
        table = direction.translations
        return (lambda text: table.get(text)), ""
    return None, f"no translation path {source} -> {lang}"


def sidecar_events(pkg: Any, section: EditSection, plan: dict[str, Any], rows: list[dict[str, Any]], lang: str,
                   credits: list[tuple[str, int]]) -> tuple[list[tuple[float, float, str]], list[str]]:
    """(timed texts on the final clock, texts missing in ``lang``)."""
    tr, error = translator(pkg, lang)
    if tr is None:
        return [], [error]
    missing: list[str] = []

    def t(text: str) -> str:
        done = tr(text)
        if done is None:
            missing.append(text)
            return text
        return done

    title, _ = resolved_cards(pkg, section)
    start = {e["event_id"]: e["start_s"] for e in plan["events"]}
    def t_title(text: str) -> str:   # the title is a name: an upper-case translation key counts, none is no error
        return tr(text) or tr(text.upper()) or text

    events = [(0.0, section.title_s, "\n".join(t_title(x) for x, _ in title))]
    for event, placed in zip(section.events, plan["events"]):
        if event.kind == "CARD":
            events.append((placed["start_s"], placed["end_s"], "\n".join(t(l) for l in event.card_lines)))
    for row in rows:
        events.append((start[row["event_id"]] + row["start_s"], start[row["event_id"]] + row["end_s"], t(row["text"])))
    for tag in section.tags:
        text = tag.label + (f"\n{t(tag.relation)}" if tag.relation else "")
        events.append((start[tag.event_id] + tag.start_s, start[tag.event_id] + tag.end_s, text))
    events.append((plan["body_end_s"], plan["total_s"], "\n".join(x for x, _ in credits[1:])))
    return events, sorted(set(missing))


# ------------------------------------------------------------------ reframe

def reframe_problems(section: EditSection, reframes: ReframePlan) -> list[dict[str, str]]:
    kinds = {e.event_id: e.kind for e in section.events}
    tagged = {t.event_id for t in section.tags}
    out = []

    def add(code: str, severity: str, event_id: str, detail: str) -> None:
        out.append({"code": code, "severity": severity, "event_id": event_id, "detail": detail})

    for event_id, box in reframes.events.items():
        if kinds.get(event_id) != "TAKE":
            add("REFRAME_EVENT_UNKNOWN", "BLOCK", event_id, "not a TAKE event of the EDL")
            continue
        if abs(box.w - box.h) > 0.005:
            add("REFRAME_ASPECT", "BLOCK", event_id, f"w {box.w} != h {box.h}: the crop would distort the frame")
        if box.w < 0.5:
            add("REFRAME_SOFT", "WARN", event_id, f"a {box.w:.0%} crop is scaled up {1 / box.w:.1f}x; expect softness")
        if event_id in tagged and (box.x, box.y, box.w, box.h) != (0.0, 0.0, 1.0, 1.0):
            add("REFRAME_TAG", "WARN", event_id, "the event has identity tags; the face moves under them")
    return out


# ------------------------------------------------------------------ the whole step

def prepare(pkg: Any, *, clips_dir: Path | None = None, langs: tuple[str, ...] = ("en", "vi"),
            generators: str = "") -> dict[str, Any]:
    """Credits, dialogue cues, sidecar texts and reframe checks for the EDL. Nothing is written."""
    section = pkg.typed.get("edit")
    if section is None or not section.events:
        raise ValueError("titles need a valid 05_edit.json with events")
    root = Path(pkg.root)
    edit_issues, durations = edit_problems(pkg, section, clips_dir=clips_dir)
    problems = [p for p in edit_issues if p["severity"] == "BLOCK"]
    if problems:
        raise ValueError("; ".join(f"{p['code']} {p['event_id']}: {p['detail']}" for p in problems))
    lengths = {e.event_id: source_length(e, durations.get(e.take_id)) for e in section.events}
    plan = timeline(section, durations, lengths)
    dialogue = dialogue_cues(pkg, section, durations, clips_dir=clips_dir)
    reframes = load_reframes(root)
    problems = list(dialogue["problems"]) + reframe_problems(section, reframes)
    credits, sidecars = {}, {}
    for lang in langs:
        if lang not in LABELS:
            problems.append({"code": "LANGUAGE_UNSUPPORTED", "severity": "BLOCK", "detail": f"no credits wording for {lang!r}"})
            continue
        lines, issues = credits_lines(pkg, lang, generators=generators)
        credits[lang] = lines
        problems += [{**i, "lang": lang} for i in issues]
        events, missing = sidecar_events(pkg, section, plan, dialogue["rows"], lang, lines)
        if missing:
            problems.append({"code": "TRANSLATION_MISSING", "severity": "BLOCK", "lang": lang,
                             "detail": f"{len(missing)} text(s) without a {lang} translation: " + "; ".join(m[:50] for m in missing[:5])})
        else:
            sidecars[lang] = events
    return {"film_id": pkg.header.film_id, "plan": plan, "credits": credits, "rows": dialogue["rows"],
            "cues": dialogue["cues"], "sidecars": sidecars, "reframes": dict(reframes.events), "problems": problems,
            "ok": not any(p["severity"] == "BLOCK" for p in problems)}


def write_outputs(pkg: Any, prepared: dict[str, Any], out_dir: Path | None = None) -> dict[str, Any]:
    """Write ``titles/credits.json``, the sidecar SRTs and ``titles/titles.json``; returns the public report."""
    from film_pipeline.drama.post import merge_cues, write_srt
    out = Path(out_dir) if out_dir else titles_dir(pkg.root)
    out.mkdir(parents=True, exist_ok=True)
    srts = {lang: str(write_srt(merge_cues(events), out / f"{pkg.header.film_id}.{lang}.srt"))
            for lang, events in prepared["sidecars"].items()}
    (out / "credits.json").write_text(json.dumps({lang: [{"text": t, "size": s} for t, s in lines]
                                                  for lang, lines in prepared["credits"].items()},
                                                 ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    report = {"film_id": prepared["film_id"], "ok": prepared["ok"], "sidecars": srts, "credits": "titles/credits.json",
              "cues": prepared["rows"], "reframed": sorted(prepared["reframes"]), "problems": prepared["problems"],
              "summary": {"cues": len(prepared["rows"]), "languages": sorted(srts), "reframed": len(prepared["reframes"]),
                          "blocks": sum(p["severity"] == "BLOCK" for p in prepared["problems"]),
                          "warnings": sum(p["severity"] == "WARN" for p in prepared["problems"])}}
    (out / "titles.json").write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return report
