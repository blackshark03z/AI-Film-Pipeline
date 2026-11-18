"""Versions, thumbnails and the metadata draft (categories 148 encoding, 149 versioning, 151/152 packaging and metadata, 153
platform compliance). Nothing here publishes anything: it writes files under ``versions/`` for the Owner to review.

* **9:16 version** - cut from the 16:9 master, segment by segment on the master's own clock (``cut_report["planned"]``): a TAKE
  event is cropped to a 9:16 window of the frame centred on where the face is - the identity-tag anchor of the event when it has
  tags, else its ``titles/portrait_focus.json`` x (``{"events": {event_id: x 0..1}}``, set by a reviewer looking at the
  frame; it moves only the 9:16 window, never the 16:9 picture), else the centre of its ``titles/reframe.json`` box, else the middle of the frame (``PORTRAIT_FOCUS_UNKNOWN``: nobody
  has said where the subject is, a human checks it). Two tagged faces further apart than the window warn
  (``PORTRAIT_SPREAD``). Declared multi-person MASTER events are fitted to retain their shared composition.
  Title, end card and CARD events cannot be cropped without losing words: they are fitted to the width
  on black. The sound is copied untouched. Burned-in cues sit across the whole 16:9 frame, so a crop loses part of them
  (``PORTRAIT_BURNED_TEXT``). The fix: ``film.py titles --render --clean-copy`` also renders the cut with no cues and records
  it in ``titles/titles.json`` (``clean_render``, sha-bound); ``versions`` then crops that clean picture and burns the cues
  again, laid out for the 9:16 frame (``cues_relaid``). The sound always comes from the 16:9 master. An explicit
  ``portrait_source`` works the same way.
* **Thumbnails** - candidate frames from the director's emphasis moments (reveal moments first, then hold / push / reaction /
  insert), taken from the master at a moment with no tag or cue burned over it when one exists in the event, rejected when
  nearly black or blown out.
* **Metadata draft** - title (source language and Vietnamese when the package translates it), description from the logline,
  tags, AI disclosure text and flags, credits, runtime and the hashes of every version. ``status`` is always
  ``DRAFT_NOT_PUBLISHED``; the platform's own AI-content label is the Owner's to set at upload.
"""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
import hashlib
import json
import statistics
import subprocess
from pathlib import Path
from typing import Any

from film_pipeline.production.ffjoin import (
    ffconcat_path,
    join_video_chunks,
    media_timeout,
    render_workers,
    run_ffmpeg,
    use_hwaccel,
    video_encode_args,
)
from film_pipeline.production.package import wants_portrait
from film_pipeline.production.render_cache import cached as _cached_render, key_for as _render_key, save as _save_render
from film_pipeline.production.runtime import atomic_json, scratch_tempdir

PORTRAIT_H = 1280
PORTRAIT_W = 720
DEVICE_RANK = {"hold": 0, "push": 1, "reaction": 2, "insert": 3}
THUMB_MIN_LUMA, THUMB_MAX_LUMA, THUMB_MIN_CONTRAST = 28.0, 225.0, 14.0
# a low-key (night) frame with real contrast is lifted for the thumbnail instead of rejected; flat or black frames stay out
THUMB_LIFT_FLOOR, THUMB_LIFT = 15.0, "eq=gamma=1.45:brightness=0.02"
THUMB_OFFSETS = (0.5, 0.35, 0.65, 0.2, 0.8)
MAX_THUMBS = 6


def versions_dir(root: Path) -> Path:
    return Path(root) / "versions"


def _problem(code: str, severity: str, detail: str, at_s: float | None = None) -> dict[str, Any]:
    out: dict[str, Any] = {"code": code, "severity": severity, "detail": detail}
    if at_s is not None:
        out["at_s"] = round(at_s, 3)
    return out


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with Path(path).open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def probe_size(video: Path) -> tuple[int, int, float]:
    done = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries", "stream=width,height,r_frame_rate",
                           "-of", "json", str(video)], capture_output=True, text=True, check=True, timeout=60)
    s = json.loads(done.stdout)["streams"][0]
    a, _, b = s["r_frame_rate"].partition("/")
    return int(s["width"]), int(s["height"]), float(a) / float(b or 1)


# ------------------------------------------------------------------ 9:16

def load_portrait_focus(root: Path) -> dict[str, float]:
    """``titles/portrait_focus.json`` -> {event_id: x centre as a fraction of the frame width}; missing file -> {}."""
    path = Path(root) / "titles" / "portrait_focus.json"
    if not path.is_file():
        return {}
    events = json.loads(path.read_text(encoding="utf-8")).get("events", {})
    bad = {k: v for k, v in events.items() if not isinstance(v, (int, float)) or not 0.0 <= v <= 1.0}
    if bad:
        raise ValueError(f"portrait_focus.json: x must be a number in 0..1: {bad}")
    return {k: float(v) for k, v in events.items()}


def focus_for(event_id: str, section: Any, reframes: dict[str, Any], crop_frac: float,
              focus: dict[str, float] | None = None) -> tuple[float, str, list[dict[str, Any]]]:
    """(x centre as a fraction of the frame width, where it came from, problems)."""
    tags = [t for t in section.tags if t.event_id == event_id]
    if tags:
        xs = [t.anchor_x for t in tags]
        problems = []
        if max(xs) - min(xs) > crop_frac * 0.9:
            problems.append(_problem("PORTRAIT_SPREAD", "WARN",
                                     f"{event_id}: tagged faces span {max(xs) - min(xs):.2f} of the frame, the 9:16 window is "
                                     f"{crop_frac:.2f}: one of them is cut off"))
        return (max(xs) + min(xs)) / 2, "tag", problems
    if focus and event_id in focus:
        return focus[event_id], "portrait_focus", []
    box = reframes.get(event_id)
    if box is not None:
        return box.x + box.w / 2, "reframe", []
    return 0.5, "center", [_problem("PORTRAIT_FOCUS_UNKNOWN", "WARN",
                                    f"{event_id}: no tag or reframe says where the subject is; the crop is centred, check it")]


def portrait_segments(plan: dict[str, Any], section: Any, reframes: dict[str, Any], width: int, height: int, fps: float,
                      focus: dict[str, float] | None = None,
                      fit_events: set[str] | None = None) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Partition the master's clock into segments, each cropped around its focus or fitted. Frames, so the video keeps its length."""
    crop_w = int(height * 9 / 16) // 2 * 2
    crop_frac = crop_w / width
    fit_events = fit_events or set()
    problems: list[dict[str, Any]] = []
    cuts: list[tuple[float, float, str, str]] = [(0.0, plan["title_s"], "fit", "title")]
    events = plan["events"]
    for i, placed in enumerate(events):
        start = placed["start_s"] if i else plan["title_s"]
        end = events[i + 1]["start_s"] if i + 1 < len(events) else plan["body_end_s"]
        mode = "fit" if placed["kind"] == "CARD" or placed["event_id"] in fit_events else "crop"
        cuts.append((start, end, mode, placed["event_id"]))
    cuts.append((plan["body_end_s"], plan["total_s"], "fit", "end"))
    segments: list[dict[str, Any]] = []
    for start, end, mode, event_id in cuts:
        f0, f1 = round(start * fps), round(end * fps)
        if f1 <= f0:
            continue
        seg = {"event_id": event_id, "mode": mode, "start_frame": f0, "end_frame": f1,
               "start_s": round(f0 / fps, 3), "end_s": round(f1 / fps, 3)}
        if mode == "crop":
            cx, source, found = focus_for(event_id, section, reframes, crop_frac, focus)
            problems += found
            left = min(max(int(round(cx * width - crop_w / 2)), 0), width - crop_w) // 2 * 2
            seg.update(focus=round(cx, 3), focus_source=source, crop_x=left, crop_w=crop_w)
        segments.append(seg)
    return segments, problems


PORTRAIT_LABEL_X, PORTRAIT_LABEL_Y, PORTRAIT_LABEL_SIZE = 24, PORTRAIT_H - 260, 28  # above the bottom strip platforms cover


def portrait_label_png(path: Path, text: str, *, box: bool = True) -> Path:
    """The body AI label drawn for the 9:16 frame (the 16:9 one sits at x 24-130 and is cut off by the crop).

    It sits on a translucent dark box so it stays readable over bright footage; `box=False` draws the glyphs alone (the mask
    `deliver.label_evidence` looks for)."""
    from PIL import Image, ImageDraw, ImageFont
    from film_pipeline.drama.post import DEFAULT_FONTS
    img = Image.new("RGBA", (PORTRAIT_W, PORTRAIT_H), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    font = ImageFont.truetype(DEFAULT_FONTS[0], PORTRAIT_LABEL_SIZE)
    if box:
        x0, y0, x1, y1 = draw.textbbox((PORTRAIT_LABEL_X, PORTRAIT_LABEL_Y), text, font=font)
        draw.rectangle((x0 - 10, y0 - 6, x1 + 10, y1 + 6), fill=(0, 0, 0, 150))
    draw.text((PORTRAIT_LABEL_X, PORTRAIT_LABEL_Y), text, font=font, fill=(255, 255, 255, 235))
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    img.save(path)
    return Path(path)


def portrait_graph(segments: list[dict[str, Any]], height: int, label_window: tuple[float, float] | None = None,
                   overlays: list[tuple[int, float, float]] | None = None) -> str:
    """`label_window` (start_s, end_s) overlays input 1 (the label PNG) on the concatenated picture for that window;
    `overlays` adds more full-frame PNG inputs as (input index, start_s, end_s) (the 9:16 dialogue cues)."""
    parts, labels = [], []
    for k, s in enumerate(segments):
        trim = f"[0:v]trim=start_frame={s['start_frame']}:end_frame={s['end_frame']},setpts=PTS-STARTPTS"
        if s["mode"] == "crop":
            shape = f"crop={s['crop_w']}:{height}:{s['crop_x']}:0,scale={PORTRAIT_W}:{PORTRAIT_H}:flags=lanczos"
        else:
            shape = f"scale={PORTRAIT_W}:-2:flags=lanczos,pad={PORTRAIT_W}:{PORTRAIT_H}:0:(oh-ih)/2:black"
        parts.append(f"{trim},{shape},setsar=1[s{k}]")
        labels.append(f"[s{k}]")
    head = ";".join(parts) + ";" + "".join(labels) + f"concat=n={len(segments)}:v=1:a=0"
    layers = ([(1, *label_window)] if label_window is not None else []) + list(overlays or [])
    if not layers:
        return head + "[v]"
    chain, prev = head + "[o0]", "o0"
    for k, (idx, a, b) in enumerate(layers):
        nxt = "v" if k == len(layers) - 1 else f"o{k + 1}"
        chain += f";[{prev}][{idx}:v]overlay=0:0:shortest=1:enable='between(t,{a:.3f},{b:.3f})'[{nxt}]"
        prev = nxt
    return chain


PORTRAIT_CUE_SIZE, PORTRAIT_CUE_MAX_W, PORTRAIT_CUE_BOTTOM = 38, 640, PORTRAIT_H - 290  # above the AI label and platform UI


def portrait_cue_png(path: Path, text: str) -> Path:
    """A dialogue cue drawn for the 9:16 frame: wrapped to the portrait width, centred, on a translucent box."""
    from PIL import Image, ImageDraw, ImageFont
    from film_pipeline.drama.post import DEFAULT_FONTS
    img = Image.new("RGBA", (PORTRAIT_W, PORTRAIT_H), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    font = ImageFont.truetype(DEFAULT_FONTS[0], PORTRAIT_CUE_SIZE)
    lines: list[str] = []
    for para in text.splitlines() or [""]:
        line = ""
        for word in para.split():
            trial = f"{line} {word}".strip()
            if line and draw.textlength(trial, font=font) > PORTRAIT_CUE_MAX_W:
                lines.append(line)
                line = word
            else:
                line = trial
        lines.append(line)
    step = int(PORTRAIT_CUE_SIZE * 1.25)
    top = PORTRAIT_CUE_BOTTOM - step * len(lines)
    for k, line in enumerate(lines):
        w = draw.textlength(line, font=font)
        x, y = (PORTRAIT_W - w) / 2, top + k * step
        x0, y0, x1, y1 = draw.textbbox((x, y), line, font=font)
        draw.rectangle((x0 - 10, y0 - 6, x1 + 10, y1 + 6), fill=(0, 0, 0, 150))
        draw.text((x, y), line, font=font, fill=(255, 255, 255, 245))
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    img.save(path)
    return Path(path)


def picture_identity(parts: list[dict], start: int, end: int) -> list[dict]:
    identity, covered = [], start
    for p in parts:
        a, b = max(start, p["start_frame"]), min(end, p["end_frame"])
        if b <= a:
            continue
        if a != covered:
            raise ValueError("picture part coverage has a gap or overlap")
        identity.append({"key": p["key"], "in_frame": a - p["start_frame"], "out_frame": b - p["start_frame"]})
        covered = b
    if covered != end:
        raise ValueError("picture parts do not cover this portrait window")
    return identity


def verified_picture_parts(source: Path, plan: dict, fps: float) -> list[dict] | None:
    """Legacy or stale provenance falls back to hashing the entire source."""
    from film_pipeline.drama.post import probe_video_duration
    try:
        report = json.loads(source.with_suffix(".cut.json").read_text(encoding="utf-8"))
        parts = report.get("picture_parts")
        if not parts or report["output_sha256"] != sha256_file(source) or report["planned"] != plan:
            return None
        cursor = 0
        for part in parts:
            if (part["start_frame"] != cursor or not isinstance(part["end_frame"], int)
                    or part["end_frame"] <= cursor or len(part["key"]) != 64
                    or any(c not in "0123456789abcdef" for c in part["key"])):
                return None
            cursor = part["end_frame"]
        if cursor != round(plan["total_s"] * fps) or abs(cursor - round(probe_video_duration(source) * fps)) > 1:
            return None
        return parts
    except (OSError, ValueError, KeyError, TypeError, AttributeError):
        return None


def portrait_windows(segments: list[dict], fps: float, picture_parts: list[dict] | None = None) -> list[list[dict]]:
    max_frames = max(1, round(60 * fps))
    boundaries = [p["end_frame"] for p in picture_parts or []]
    pieces = []
    for segment in segments:
        start, end = segment["start_frame"], segment["end_frame"]
        while start < end:
            boundary = next((f for f in boundaries if f > start), end)
            stop = min(end, start + max_frames, boundary)
            pieces.append({**segment, "start_frame": start, "end_frame": stop,
                           "start_s": round(start / fps, 3), "end_s": round(stop / fps, 3)})
            start = stop
    windows = []
    for piece in pieces:
        previous = windows[-1] if windows else []
        boundary = previous and previous[-1]["end_frame"] in boundaries
        if (not previous or boundary or len(previous) == 12
                or piece["end_frame"] - previous[0]["start_frame"] > max_frames):
            windows.append([])
        windows[-1].append(piece)
    return windows


def render_portrait(source: Path, segments: list[dict[str, Any]], out: Path, height: int, fps: float,
                    label: tuple[Path, float, float] | None = None, cues: list[tuple[Path, float, float]] | None = None,
                    audio_from: Path | None = None, cache_dir: Path | None = None,
                    picture_parts: list[dict] | None = None, *,
                    jobs: int | None = None, hwaccel: bool | None = None) -> Path:
    """`label` = (PNG, start_s, end_s): the AI label burned over the body of the 9:16 picture; `cues` = more (PNG, start_s,
    end_s) layers; `audio_from` = the file whose sound is copied (default: the source)."""
    out.parent.mkdir(parents=True, exist_ok=True)
    cues = cues or []
    hw = use_hwaccel(hwaccel)
    vcodec_args, enc_name = video_encode_args("portrait", hwaccel=hwaccel)
    workers = render_workers(jobs, hwaccel=hw)
    windows = portrait_windows(segments, fps, picture_parts)
    if len(windows) > 1:
        cache_dir = Path(cache_dir) if cache_dir is not None else out.parent / ".render_cache"
        audio_source = Path(audio_from) if audio_from is not None else Path(source)
        with scratch_tempdir(prefix="afp_portrait_", root=out.parent) as work:
            win_keys: list[str] = []
            win_chunks: dict[str, Path] = {}
            uncached: dict[str, dict[str, Any]] = {}
            for chunk_no, part in enumerate(windows):
                first_frame, last_frame = part[0]["start_frame"], part[-1]["end_frame"]
                start_s, end_s = first_frame / fps, last_frame / fps
                local = [{**s, "start_frame": s["start_frame"] - first_frame,
                          "end_frame": s["end_frame"] - first_frame,
                          "start_s": round((s["start_frame"] - first_frame) / fps, 3),
                          "end_s": round((s["end_frame"] - first_frame) / fps, 3)} for s in part]
                active_label = label if label and label[1] < end_s and label[2] > start_s else None
                active_cues = [(p, a, b) for p, a, b in cues if a < end_s and b > start_s]
                files = [] if picture_parts else [Path(source)]
                if active_label:
                    files.append(Path(active_label[0]))
                files.extend(Path(p) for p, _, _ in active_cues)
                label_window = ((round(max(0., active_label[1] - start_s), 3), round(min(end_s - start_s, active_label[2] - start_s), 3))
                                if active_label else None)
                cue_windows = [(round(max(0., a - start_s), 3), round(min(end_s - start_s, b - start_s), 3)) for _, a, b in active_cues]
                settings: dict[str, Any] = {
                    "segments": local, "height": height, "fps": fps, "video_only_profile": 1,
                    "source_start_frame": None if picture_parts else first_frame,
                    "picture": picture_identity(picture_parts, first_frame, last_frame) if picture_parts else None,
                    "label": label_window, "cues": cue_windows,
                    "duration_frames": last_frame - first_frame,
                }
                if enc_name == "h264_nvenc":
                    settings["encoder"] = enc_name
                key = _render_key(sources=files, settings=settings)
                win_keys.append(key)
                if key in win_chunks or key in uncached:
                    continue
                hit = _cached_render(cache_dir, key, ".mkv")
                if hit is not None:
                    win_chunks[key] = hit
                    continue
                uncached[key] = {
                    "no": chunk_no, "key": key, "start_s": start_s,
                    "active_label": active_label, "active_cues": active_cues,
                    "local": local, "label_window": label_window, "cue_windows": cue_windows,
                    "chunk_dur": max(1.0, (last_frame - first_frame) / fps),
                }

            def _render_portrait_chunk(desc: dict[str, Any]) -> tuple[str, Path]:
                inputs = ["-ss", f"{desc['start_s']:.6f}", "-i", str(source)]
                if desc["active_label"]:
                    inputs += ["-loop", "1", "-i", str(desc["active_label"][0])]
                first_cue = 1 + int(bool(desc["active_label"]))
                for png, _, _ in desc["active_cues"]:
                    inputs += ["-loop", "1", "-i", str(png)]
                layer_list = [(first_cue + i, a, b) for i, (a, b) in enumerate(desc["cue_windows"])]
                graph = portrait_graph(desc["local"], height, desc["label_window"], layer_list)
                graph_file = work / f"portrait_{desc['no']:06d}.filter"
                graph_file.write_text(graph, encoding="utf-8")
                generated = work / f"portrait_{desc['no']:06d}.mkv"
                run_ffmpeg(["ffmpeg", "-v", "error", "-y", *inputs,
                            "-/filter_complex", str(graph_file), "-map", "[v]", "-an",
                            *vcodec_args, "-r", f"{fps:g}", str(generated)],
                           timeout_s=media_timeout(desc["chunk_dur"]))
                return desc["key"], generated

            if uncached:
                specs = list(uncached.values())
                if len(specs) > 1 and workers > 1:
                    with ThreadPoolExecutor(max_workers=workers) as pool:
                        rendered_pairs = list(pool.map(_render_portrait_chunk, specs))
                else:
                    rendered_pairs = [_render_portrait_chunk(s) for s in specs]
                for key, generated in rendered_pairs:
                    win_chunks[key] = _save_render(cache_dir, key, generated, ".mkv")
            chunks = [win_chunks[k] for k in win_keys]
            concat_list = work / "concat.txt"
            # Explicit exact durations: mkv timestamps are whole milliseconds, so without them every join took the
            # chunk's rounded-up length and a 30 min portrait ended a whole frame late.
            concat_list.write_text(
                "".join(f"file '{ffconcat_path(p)}'\nduration {(w[-1]['end_frame'] - w[0]['start_frame']) / fps:.9f}\n"
                        for p, w in zip(chunks, windows)), encoding="utf-8")
            joined = work / "joined.mkv"
            total_s = max(1.0, max((float(s.get("end_s", s.get("end", 10.0))) for s in segments), default=10.0))
            join_video_chunks(concat_list, joined, timeout_s=media_timeout(total_s))
            run_ffmpeg(["ffmpeg", "-v", "error", "-y", "-i", str(joined), "-i", str(audio_source),
                        "-map", "0:v:0", "-map", "1:a:0?", "-c", "copy", "-movflags", "+faststart", str(out)],
                       timeout_s=media_timeout(total_s))
        return out
    inputs = ["-i", str(source)] + (["-loop", "1", "-i", str(label[0])] if label else [])
    first = 2 if label else 1
    for png, _, _ in cues or []:
        inputs += ["-loop", "1", "-i", str(png)]
    overlays = [(first + k, a, b) for k, (_, a, b) in enumerate(cues or [])]
    audio = "0:a?"
    if audio_from is not None and Path(audio_from) != Path(source):
        inputs += ["-i", str(audio_from)]
        audio = f"{first + len(overlays)}:a?"
    graph_file = out.with_suffix(".filter")
    graph_file.write_text(portrait_graph(segments, height, (label[1], label[2]) if label else None, overlays), encoding="utf-8")
    total_s = max(1.0, max((float(s.get("end_s", s.get("end", 10.0))) for s in segments), default=10.0))
    run_ffmpeg(["ffmpeg", "-v", "error", "-y", *inputs, "-/filter_complex", str(graph_file),
                "-map", "[v]", "-map", audio, *vcodec_args,
                "-r", f"{fps:g}", "-c:a", "copy", "-movflags", "+faststart", str(out)],
               timeout_s=media_timeout(total_s))
    graph_file.unlink(missing_ok=True)
    return out


# ------------------------------------------------------------------ thumbnails

def text_windows(section: Any, plan: dict[str, Any], titles_report: dict[str, Any] | None) -> list[tuple[float, float]]:
    """Absolute windows of the master where a tag or a cue is burned over the picture."""
    start = {e["event_id"]: e["start_s"] for e in plan["events"]}
    out = [(start[t.event_id] + t.start_s, start[t.event_id] + t.end_s) for t in section.tags if t.event_id in start]
    for row in (titles_report or {}).get("cues", []):
        if "abs_start_s" in row:
            out.append((row["abs_start_s"], row["abs_end_s"]))
    return out


def emphasis_moments(pkg: Any) -> list[dict[str, Any]]:
    direction = pkg.typed.get("direction")
    if direction is None:
        return []
    out = []
    for sid, scene in direction.scenes.items():
        for e in scene.emphasis:
            if e.generation_id:
                out.append({"scene": sid, "moment": e.moment, "device": e.device, "generation_id": e.generation_id,
                            "fact_id": e.fact_id})
    out.sort(key=lambda m: (m["fact_id"] is None, DEVICE_RANK.get(m["device"], 9), m["scene"], m["generation_id"]))
    return out


def grab_frame(video: Path, at_s: float, out: Path, width: int = 1280, extra_vf: str = "") -> Path:
    out.parent.mkdir(parents=True, exist_ok=True)
    vf = f"scale={width}:-2:flags=lanczos" + (f",{extra_vf}" if extra_vf else "")
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-ss", f"{at_s:.3f}", "-i", str(video), "-frames:v", "1",
                    "-vf", vf, "-q:v", "2", str(out)], check=True, timeout=60)
    return out


def frame_stats(image: Path) -> tuple[float, float]:
    """(mean luma, luma spread) on a 32x18 reduction."""
    raw = subprocess.run(["ffmpeg", "-v", "error", "-i", str(image), "-vf", "scale=32:18:flags=area,format=gray", "-f", "rawvideo",
                          "-"], capture_output=True, check=True, timeout=60).stdout
    values = list(raw)
    return (statistics.fmean(values), statistics.pstdev(values)) if values else (0.0, 0.0)


def thumbnails(pkg: Any, source: Path, plan: dict[str, Any], section: Any, out_dir: Path,
               titles_report: dict[str, Any] | None = None) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    problems: list[dict[str, Any]] = []
    windows = text_windows(section, plan, titles_report)
    by_generation: dict[str, list[dict[str, Any]]] = {}
    for placed in plan["events"]:
        if placed["kind"] == "TAKE":
            by_generation.setdefault(placed["take_id"].rsplit("_t", 1)[0], []).append(placed)

    def clean(t: float) -> bool:
        return not any(a <= t <= b for a, b in windows)

    chosen: list[dict[str, Any]] = []
    used: set[str] = set()
    moments = emphasis_moments(pkg)
    if not moments:
        problems.append(_problem("THUMB_NO_EMPHASIS", "WARN", "the direction names no emphasis moment: no thumbnail candidate"))
    for m in moments:
        if len(chosen) >= MAX_THUMBS:
            break
        for placed in by_generation.get(m["generation_id"], []):
            if placed["event_id"] in used:
                continue
            tries = [(placed["start_s"] + f * placed["duration_s"], f) for f in THUMB_OFFSETS]
            tries.sort(key=lambda x: (not clean(x[0]), THUMB_OFFSETS.index(x[1])))
            for at_s, _ in tries:
                path = grab_frame(source, at_s, out_dir / f"thumb_{len(chosen) + 1:02d}.jpg")
                luma, spread = frame_stats(path)
                lifted = False
                if THUMB_LIFT_FLOOR <= luma < THUMB_MIN_LUMA and spread >= THUMB_MIN_CONTRAST:
                    path = grab_frame(source, at_s, path, extra_vf=THUMB_LIFT)
                    luma, spread = frame_stats(path)
                    lifted = True
                if luma < THUMB_MIN_LUMA or luma > THUMB_MAX_LUMA or spread < THUMB_MIN_CONTRAST:
                    path.unlink(missing_ok=True)
                    continue
                burned = not clean(at_s)
                chosen.append({"file": str(path.relative_to(Path(pkg.root))).replace("\\", "/"), "at_s": round(at_s, 3),
                               "event_id": placed["event_id"], "scene": m["scene"], "moment": m["moment"], "device": m["device"],
                               "fact_id": m["fact_id"], "luma": round(luma, 1), "contrast": round(spread, 1),
                               "burned_text": burned, "lifted": lifted, "sha256": sha256_file(path)})
                used.add(placed["event_id"])
                if burned:
                    problems.append(_problem("THUMB_BURNED_TEXT", "WARN",
                                             f"{placed['event_id']}: every candidate moment has a tag or cue over it", at_s))
                break
            else:
                problems.append(_problem("THUMB_REJECTED", "WARN",
                                         f"{placed['event_id']} ({m['moment']}): all candidate frames are too dark, too bright or flat",
                                         placed["start_s"]))
            if len(chosen) >= MAX_THUMBS:
                break
    if moments and not chosen:
        problems.append(_problem("THUMB_NONE", "WARN", "no emphasis moment gave a usable frame"))
    return chosen, problems


# ------------------------------------------------------------------ metadata

def metadata_draft(pkg: Any, plan: dict[str, Any], versions: list[dict[str, Any]], *, generators: Any = "") -> tuple[dict[str, Any], list[dict[str, Any]]]:
    from film_pipeline.production import titles as ti
    from film_pipeline.production import sound_rights as sr
    from film_pipeline.production.generators import as_records, generators_line
    records = [g.model_dump(mode="json") for g in as_records(generators)]
    generators = generators_line(generators)
    problems: list[dict[str, Any]] = []
    story = pkg.typed.get("story")
    source = pkg.header.language
    tr_vi, why = ti.translator(pkg, "vi") if source != "vi" else ((lambda t: t), "")
    title_vi = (tr_vi(pkg.header.title) or tr_vi(pkg.header.title.upper())) if tr_vi else None
    if tr_vi and not title_vi:
        problems.append(_problem("META_TITLE_UNTRANSLATED", "WARN", f"direction.translations has no entry for the title {pkg.header.title!r}"))
    elif why:
        problems.append(_problem("META_NO_TRANSLATION", "WARN", why))
    description = story.logline.text if story is not None else ""
    if not description:
        problems.append(_problem("META_NO_DESCRIPTION", "WARN", "no story logline to draft the description from"))
    tags = [t for t in (["AI film", "AI generated", "short film", story.genre if story else "", story.theme if story else ""]) if t]
    names = ti.cast_names(pkg)
    owed = sr.attributions(pkg)
    rights = sr.check_assets(pkg)["issues"]
    for issue in rights:
        problems.append(_problem("META_RIGHTS_OPEN", "WARN", f"{issue['code']} {issue['asset']}: {issue['detail']}"))
    if not generators:
        problems.append(_problem("META_NO_GENERATORS", "WARN", "no generator named for the AI disclosure (pass --generators or --generators-file)"))
    lang = "en" if source == "en" else "vi"
    words = ti.LABELS
    disclosure = {"ai_generated": True, "digital_source_type": "trainedAlgorithmicMedia", "synthetic_persons": bool(names),
                  "generators": generators, "generator_records": records,
                  "ai_label": pkg.header.disclosure.ai_label,
                  "text": {code: (f"{words[code]['ai_with']}: {generators}" if generators else words[code]["ai_generic"])
                           + (f" {words[code]['synthetic']}" if names else "") for code in ("en", "vi")}}
    draft = {"film_id": pkg.header.film_id, "status": "DRAFT_NOT_PUBLISHED", "source_language": source,
             "title": {"source": pkg.header.title, **({"vi": title_vi} if title_vi else {})},
             "description": description, "description_note": "drafted from the logline; the Owner writes the final copy",
             "tags": tags, "ai_disclosure": disclosure, "credits": {"characters": names, "sound_attributions": owed,
                                                                   "fiction_line": words[lang]["fiction"]},
             "runtime_s": plan["total_s"], "versions": versions,
             "platform_note": "set the platform's own AI / synthetic-content label at upload; nothing was published"}
    return draft, problems


def build(pkg: Any, master: Path, cut_report: Path, *, out_dir: Path | None = None, portrait_source: Path | None = None,
          generators: Any = "", include_portrait: bool | None = None,
          jobs: int | None = None, hwaccel: bool | None = None) -> dict[str, Any]:
    """Write ``versions/`` (thumbnails, metadata.json, versions.json, and opt-in 9:16 mp4) and return the report."""
    from film_pipeline.production import titles as ti
    section = pkg.typed.get("edit")
    if section is None:
        raise ValueError("versions needs a valid 05_edit.json")
    cut_report_path = Path(cut_report)
    cut_report_sha = sha256_file(cut_report_path)
    plan = json.loads(cut_report_path.read_text(encoding="utf-8"))["planned"]
    out = Path(out_dir) if out_dir else versions_dir(pkg.root)
    out.mkdir(parents=True, exist_ok=True)
    width, height, fps = probe_size(master)
    problems: list[dict[str, Any]] = []
    titles_path = ti.titles_dir(pkg.root) / "titles.json"
    titles_report = json.loads(titles_path.read_text(encoding="utf-8")) if titles_path.is_file() else None
    do_portrait = (wants_portrait(pkg) or portrait_source is not None) if include_portrait is None else bool(include_portrait)
    versions: list[dict[str, Any]] = [
        {"name": "master_16x9", "file": str(Path(master)), "width": width, "height": height, "fps": fps,
         "sha256": sha256_file(master)},
    ]
    segments: list[dict[str, Any]] = []
    if do_portrait:
        reframes = ti.resolve_reframes_for_section(pkg.root, section, ti.load_reframes(pkg.root).events)
        clean = Path(portrait_source) if portrait_source else None
        recorded = (titles_report or {}).get("clean_render") or {}
        if clean is None and recorded:
            candidate = Path(pkg.root) / recorded.get("output", "")
            if candidate.is_file() and sha256_file(candidate) == recorded.get("sha256"):
                clean = candidate
            else:
                problems.append(_problem("PORTRAIT_CLEAN_STALE", "WARN", f"titles.json names a clean render {recorded.get('output')} "
                                         "that is missing or changed since; cropping the master instead"))
        source = clean or master
        from film_pipeline.production.takes import load_log
        shots = pkg.typed.get("shots")
        masters = {g.generation_id for g in shots.generations if g.coverage == "MASTER" and len(g.visible) > 1} if shots else set()
        generations = {t.take_id: t.generation_id for t in load_log(pkg.root, pkg.header.film_id).takes}
        fit_events = {event["event_id"] for event in plan["events"] if generations.get(event.get("take_id")) in masters}
        segments, found = portrait_segments(plan, section, reframes, width, height, fps, load_portrait_focus(pkg.root), fit_events)
        problems += found
        if titles_report and titles_report.get("cues") and clean is None:
            problems.append(_problem("PORTRAIT_BURNED_TEXT", "WARN",
                                     "the master carries burned-in dialogue cues across the 16:9 frame; the 9:16 crop loses part of them "
                                     "(use --portrait-source with a clean cut or ship the sidecar SRTs)"))
        label_info: dict[str, Any] | None = None
        label = None
        if pkg.header.disclosure.ai_label == "always":  # same promise as the 16:9 body: the label stays on from the end of the title to the end card
            from film_pipeline.production.deliver import BODY_LABEL
            label_info = {"text": BODY_LABEL, "start_s": plan["title_s"], "end_s": plan["body_end_s"],
                          "x": PORTRAIT_LABEL_X, "y": PORTRAIT_LABEL_Y}
            label = (portrait_label_png(out / "portrait_label.png", BODY_LABEL), plan["title_s"], plan["body_end_s"])
        cue_layers: list[tuple[Path, float, float]] = []
        if clean is not None:  # the clean picture has no cues: burn them again, laid out for 9:16
            for k, row in enumerate(r for r in (titles_report or {}).get("cues", []) if "abs_start_s" in r):
                cue_layers.append((portrait_cue_png(out / "cues" / f"cue_{k:02d}.png", row["text"]),
                                   row["abs_start_s"], row["abs_end_s"]))
        portrait = render_portrait(source, segments, out / f"{pkg.header.film_id}_9x16.mp4", height, fps, label,
                                   cue_layers, audio_from=master,
                                   picture_parts=verified_picture_parts(source, plan, fps)
                                   if clean is not None and portrait_source is None else None,
                                   jobs=jobs, hwaccel=hwaccel)
        p_w, p_h, p_fps = probe_size(portrait)
        versions.append({"name": "portrait_9x16", "file": str(portrait.relative_to(Path(pkg.root))).replace("\\", "/"),
                         "width": p_w, "height": p_h, "fps": p_fps, "sha256": sha256_file(portrait),
                         "upscale": round(PORTRAIT_H / height, 2), "ai_label": label_info,
                         "source": "clean" if clean is not None else "master", "cues_relaid": len(cue_layers),
                         "segments": segments})
        if (p_w, p_h) != (PORTRAIT_W, PORTRAIT_H):
            problems.append(_problem("PORTRAIT_SIZE", "BLOCK", f"portrait render is {p_w}x{p_h}, expected {PORTRAIT_W}x{PORTRAIT_H}"))
    thumbs, found = thumbnails(pkg, master, plan, section, out / "thumbs", titles_report)
    problems += found
    draft, found = metadata_draft(pkg, plan, [{k: v for k, v in x.items() if k != "segments"} for x in versions], generators=generators)
    problems += found
    draft["thumbnails"] = [t["file"] for t in thumbs]
    atomic_json(out / "metadata.json", draft)
    report = {"film_id": pkg.header.film_id, "cut_report_sha256": cut_report_sha,
              "ok": not any(p["severity"] == "BLOCK" for p in problems),
              "versions": versions, "thumbnails": thumbs, "metadata": "versions/metadata.json", "problems": problems,
              "summary": {"portrait_enabled": do_portrait, "portrait_segments": len(segments),
                          "thumbnails": len(thumbs),
                          "blocks": sum(p["severity"] == "BLOCK" for p in problems),
                          "warnings": sum(p["severity"] == "WARN" for p in problems)}}
    atomic_json(out / "versions.json", report)
    return report
