"""Animatic (G-animatic): the film as timed storyboard frames, a reviewable mp4 before any credit is spent.

`build_animatic` takes a Production Package and writes under `out_dir` (default `films/<id>/media/`):

* ``animatic.mp4``          one frame per generation, held for the planned generation length (`film.json` generation_s),
                            dialogue burned in as captions, a small label with the generation id and its time range
* ``animatic.srt``          the same captions as subtitles, on the animatic timeline
* ``animatic_report.json``  the timing report (Gate 3 input): per generation start/end, frame source, dialogue windows,
                            reading speed, findings

Frames, best source first: an approved still (`<stills_dir>/<gid>.png|jpg` when a directory is given, else the approved
stills recorded in `03_preprod.json`, see stills.py), else the schematic storyboard frame
(`plan`'s `storyboard/<gid>.png`, or rendered here from the axis book), else a plain card. Audio is silence unless a
temp dialogue track `<audio_dir>/<gid>.wav|mp3|m4a` exists for a generation (any TTS, produced elsewhere - this module
never synthesises speech and never touches the network); it is padded or cut to the generation length so the timeline
holds. 0 credits, ffmpeg + PIL only.

Timing findings: ``DIALOGUE_TOO_FAST`` (more than `MAX_WORDS_PER_SECOND` in its window - the actor cannot say it in that
time), ``AUDIO_TOO_LONG`` (a temp track is longer than the generation), ``FRAME_PLACEHOLDER`` (no still and no storyboard
frame, so the animatic shows a card). Findings are WARN; the report's ``ok`` is false only when the build itself is wrong
(duration drift after encoding).
"""
from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path
from typing import Any

from film_pipeline.drama.post import probe_video_duration, write_srt
from film_pipeline.drama.storyboard import _font, render_schematic_frame
from film_pipeline.production.package import FilmPackage, PackageError

MAX_WORDS_PER_SECOND = 3.5  # spoken dialogue in a drama: ~2.5 w/s normal, 3.5 is already brisk
SIZE = (1280, 720)
FPS = 24
DRIFT_TOLERANCE_S = 0.25
_IMAGE_EXT = (".png", ".jpg", ".jpeg")
_AUDIO_EXT = (".wav", ".mp3", ".m4a")


def _find(directory: Path | None, gid: str, exts: tuple[str, ...]) -> Path | None:
    if directory is None:
        return None
    for ext in exts:
        candidate = directory / f"{gid}{ext}"
        if candidate.is_file():
            return candidate
    return None


def _media_duration(path: Path) -> float:
    """Container duration, so audio-only files work (`post.probe_video_duration` reads the video stream)."""
    done = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(path)],
                          capture_output=True, text=True, check=True)
    return float(done.stdout.strip())


def _clock(seconds: float) -> str:
    return f"{int(seconds // 60)}:{seconds % 60:04.1f}"


def _plan_segments(duration_s: float, setup_s: float, lines: list[Any]) -> list[tuple[float, float, Any | None]]:
    """Cut one generation into caption segments: lead-in without a caption, then dialogue lines evenly."""
    if not lines:
        return [(0.0, duration_s, None)]
    start = min(max(setup_s, 0.0), duration_s * 0.5)
    each = (duration_s - start) / len(lines)
    segments: list[tuple[float, float, Any | None]] = []
    if start > 0:
        segments.append((0.0, start, None))
    for i, line in enumerate(lines):
        segments.append((start + i * each, start + (i + 1) * each if i < len(lines) - 1 else duration_s, line))
    return segments


def _card(path: Path, label: str, note: str) -> None:
    from PIL import Image, ImageDraw
    image = Image.new("RGB", SIZE, (226, 224, 218))
    draw = ImageDraw.Draw(image)
    draw.text((SIZE[0] // 2, SIZE[1] // 2 - 20), label, fill=(40, 40, 40), font=_font(48), anchor="mm")
    draw.text((SIZE[0] // 2, SIZE[1] // 2 + 40), note, fill=(90, 90, 90), font=_font(26), anchor="mm")
    image.save(path)


def _compose(base: Path, out: Path, label: str, caption: str | None) -> None:
    """Fit the frame to 1280x720 and draw the id label (top left) and the caption (bottom)."""
    from PIL import Image, ImageDraw
    src = Image.open(base).convert("RGB")
    scale = min(SIZE[0] / src.width, SIZE[1] / src.height)
    src = src.resize((max(1, round(src.width * scale)), max(1, round(src.height * scale))))
    canvas = Image.new("RGB", SIZE, (0, 0, 0))
    canvas.paste(src, ((SIZE[0] - src.width) // 2, (SIZE[1] - src.height) // 2))
    draw = ImageDraw.Draw(canvas, "RGBA")
    tag_font = _font(22)
    right = SIZE[0] - 8 - draw.textlength(label, font=tag_font) - 8  # top right: the storyboard keeps its own header
    draw.rectangle((right, 0, SIZE[0], 34), fill=(0, 0, 0, 220))
    draw.text((right + 8, 17), label, fill=(255, 255, 255), font=tag_font, anchor="lm")
    if caption:
        font = _font(34)
        words, rows, row = caption.split(), [], ""
        for word in words:  # wrap to 90% of the width
            trial = f"{row} {word}".strip()
            if draw.textlength(trial, font=font) > SIZE[0] * 0.9 and row:
                rows.append(row)
                row = word
            else:
                row = trial
        rows.append(row)
        top = SIZE[1] - 30 - 44 * len(rows)
        draw.rectangle((0, top - 10, SIZE[0], SIZE[1] - 14), fill=(0, 0, 0, 245))  # opaque: covers the storyboard's own caption
        for i, text in enumerate(rows):
            draw.text((SIZE[0] // 2, top + 22 + 44 * i), text, fill=(255, 255, 255), font=font, anchor="mm")
    canvas.save(out)


def _run(ffmpeg: str, *args: str) -> None:
    done = subprocess.run([ffmpeg, "-v", "error", "-nostats", "-y", *args], capture_output=True, text=True,
                          encoding="utf-8", errors="replace")
    if done.returncode != 0:
        raise PackageError(f"ffmpeg failed: {done.stderr.strip()[:400]}")


def _concat_list(path: Path, entries: list[tuple[Path, float | None]]) -> None:
    lines: list[str] = []
    for file, duration in entries:
        lines.append(f"file '{file.resolve().as_posix()}'")
        if duration is not None:
            lines.append(f"duration {duration:.3f}")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")


def _schematic_frames(pkg: FilmPackage, directory: Path) -> dict[str, Path]:
    """Render the storyboard frames the way `plan` does, for a package that has not been planned into a folder."""
    from film_pipeline.production.plan import _Plan
    plan = _Plan(pkg, None, None)
    directory.mkdir(parents=True, exist_ok=True)
    frames: dict[str, Path] = {}
    for decl in plan.shots.generations:
        unit = plan.unit_for(decl)
        target = directory / f"{decl.generation_id}.png"
        render_schematic_frame(unit, unit.shots[0], target, width=640)
        frames[decl.generation_id] = target
    return frames


def build_animatic(pkg: FilmPackage, out_dir: Path | str | None = None, *, stills_dir: Path | str | None = None,
                   storyboard_dir: Path | str | None = None, audio_dir: Path | str | None = None,
                   ffmpeg: str = "ffmpeg") -> dict[str, Any]:
    shots = pkg.typed.get("shots")
    if shots is None or pkg.script is None:
        raise PackageError("animatic needs a valid 04_shots.json and script.fountain")
    if not shots.generations:
        raise PackageError("animatic needs at least one generation")
    out_dir = Path(out_dir) if out_dir else pkg.root / "media"
    work = out_dir / "animatic_work"
    work.mkdir(parents=True, exist_ok=True)
    stills, board = Path(stills_dir) if stills_dir else None, Path(storyboard_dir) if storyboard_dir else None
    audio = Path(audio_dir) if audio_dir else None
    gen_s = float(pkg.header.generation_s)
    approved: dict[str, Path] = {}
    if stills is None and "preprod" in pkg.typed:  # default: the stills the package recorded as approved (stills.py)
        from film_pipeline.production.stills import approved_stills
        approved = approved_stills(pkg)

    dialogue = {(s.scene_id, e.line_no): e for s in pkg.script.scenes for e in s.elements if e.kind == "dialogue"}
    generated: dict[str, Path] = {}
    if board is None:  # the fallback for any generation without an approved still
        generated = _schematic_frames(pkg, work / "storyboard")

    findings: list[dict[str, str]] = []
    gen_rows: list[dict[str, Any]] = []
    video_entries: list[tuple[Path, float | None]] = []
    audio_entries: list[tuple[Path, float | None]] = []
    cues: list[tuple[float, float, str]] = []
    clock = 0.0
    for decl in shots.generations:
        gid = decl.generation_id
        base, source = _find(stills, gid, _IMAGE_EXT) or approved.get(gid), "still"
        if base is None:
            base, source = _find(board, gid, _IMAGE_EXT) or generated.get(gid), "storyboard"
        if base is None:
            base, source = work / f"{gid}_card.png", "placeholder"
            _card(base, gid, decl.choreography.phases[0].description if decl.choreography.phases else decl.coverage)
            findings.append({"check": "FRAME_PLACEHOLDER", "detail": f"{gid}: no still and no storyboard frame"})
        setup = decl.choreography.phases[0].end_s if decl.choreography.phases and \
            decl.choreography.phases[0].kind == "SETUP" else 0.0
        lines = [dialogue[(decl.scene_id, n)] for n in decl.dialogue if (decl.scene_id, n) in dialogue]
        windows = []
        for index, (t0, t1, line) in enumerate(_plan_segments(gen_s, setup, lines)):
            caption = f"{line.character}: {line.text}" if line is not None else None
            frame = work / f"{gid}_{index}.png"
            _compose(base, frame, f"{gid}  {_clock(clock + t0)}-{_clock(clock + t1)}", caption)
            video_entries.append((frame, t1 - t0))
            if line is not None:
                words = len(line.text.split())
                wps = round(words / (t1 - t0), 2)
                windows.append({"line_no": line.line_no, "character": line.character, "start_s": round(clock + t0, 3),
                                "end_s": round(clock + t1, 3), "words": words, "words_per_second": wps})
                cues.append((clock + t0, clock + t1, caption))
                if wps > MAX_WORDS_PER_SECOND:
                    findings.append({"check": "DIALOGUE_TOO_FAST",
                                     "detail": f"{gid} line {line.line_no}: {words} words in {t1 - t0:.1f} s "
                                               f"({wps} w/s > {MAX_WORDS_PER_SECOND})"})
        track = _find(audio, gid, _AUDIO_EXT)
        segment = work / f"{gid}_audio.wav"
        if track is not None:
            length = _media_duration(track)
            if length > gen_s + 0.05:
                findings.append({"check": "AUDIO_TOO_LONG", "detail": f"{gid}: temp audio {length:.1f} s > {gen_s:.1f} s"})
            _run(ffmpeg, "-i", str(track), "-af", "apad", "-t", f"{gen_s}", "-ar", "48000", "-ac", "1", str(segment))
        else:
            _run(ffmpeg, "-f", "lavfi", "-i", "anullsrc=r=48000:cl=mono", "-t", f"{gen_s}", str(segment))
        audio_entries.append((segment, None))
        gen_rows.append({"generation_id": gid, "scene_id": decl.scene_id, "start_s": round(clock, 3),
                         "end_s": round(clock + gen_s, 3), "frame_source": source,
                         "audio": "temp" if track else "silence", "dialogue": windows})
        clock += gen_s

    video_entries.append((video_entries[-1][0], None))  # the concat demuxer ignores the last duration otherwise
    _concat_list(work / "video.txt", video_entries)
    _concat_list(work / "audio.txt", audio_entries)
    _run(ffmpeg, "-f", "concat", "-safe", "0", "-i", str(work / "audio.txt"), "-c", "copy", str(work / "audio.wav"))
    mp4 = out_dir / "animatic.mp4"
    _run(ffmpeg, "-f", "concat", "-safe", "0", "-i", str(work / "video.txt"), "-i", str(work / "audio.wav"),
         "-vf", f"fps={FPS},format=yuv420p", "-c:v", "libx264", "-preset", "veryfast", "-c:a", "aac", "-t", f"{clock}",
         str(mp4))
    write_srt(cues, out_dir / "animatic.srt")
    actual = probe_video_duration(mp4)
    shutil.rmtree(work, ignore_errors=True)
    report = {"film_id": pkg.header.film_id, "video": str(mp4), "subtitles": str(out_dir / "animatic.srt"),
              "planned_duration_s": round(clock, 3), "actual_duration_s": round(actual, 3),
              "generation_s": gen_s, "audio": "temp dialogue where provided, silence elsewhere",
              "ok": abs(actual - clock) <= DRIFT_TOLERANCE_S, "findings": findings, "generations": gen_rows}
    (out_dir / "animatic_report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n",
                                                  encoding="utf-8", newline="\n")
    return report
