"""Versions, thumbnails and the metadata draft (categories 148 encoding, 149 versioning, 151/152 packaging and metadata, 153
platform compliance). Nothing here publishes anything: it writes files under ``versions/`` for the Owner to review.

* **9:16 version** - cut from the 16:9 master, segment by segment on the master's own clock (``cut_report["planned"]``): a TAKE
  event is cropped to a 9:16 window of the frame centred on where the face is - the identity-tag anchor of the event when it has
  tags, else the centre of its ``titles/reframe.json`` box, else the middle of the frame (``PORTRAIT_FOCUS_UNKNOWN``: nobody
  has said where the subject is, a human checks it). Two tagged faces further apart than the window warn
  (``PORTRAIT_SPREAD``). Title, end card and CARD events cannot be cropped without losing words: they are fitted to the width
  on black. The sound is copied untouched. Burned-in cues sit across the whole 16:9 frame, so a crop loses part of them
  (``PORTRAIT_BURNED_TEXT``): pass a clean ``portrait_source`` with the same clock, or ship the sidecar SRTs with it.
* **Thumbnails** - candidate frames from the director's emphasis moments (reveal moments first, then hold / push / reaction /
  insert), taken from the master at a moment with no tag or cue burned over it when one exists in the event, rejected when
  nearly black or blown out.
* **Metadata draft** - title (source language and Vietnamese when the package translates it), description from the logline,
  tags, AI disclosure text and flags, credits, runtime and the hashes of every version. ``status`` is always
  ``DRAFT_NOT_PUBLISHED``; the platform's own AI-content label is the Owner's to set at upload.
"""
from __future__ import annotations

import hashlib
import json
import statistics
import subprocess
from pathlib import Path
from typing import Any

PORTRAIT_H = 1280
PORTRAIT_W = 720
DEVICE_RANK = {"hold": 0, "push": 1, "reaction": 2, "insert": 3}
THUMB_MIN_LUMA, THUMB_MAX_LUMA, THUMB_MIN_CONTRAST = 28.0, 225.0, 14.0
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
                           "-of", "json", str(video)], capture_output=True, text=True, check=True)
    s = json.loads(done.stdout)["streams"][0]
    a, _, b = s["r_frame_rate"].partition("/")
    return int(s["width"]), int(s["height"]), float(a) / float(b or 1)


# ------------------------------------------------------------------ 9:16

def focus_for(event_id: str, section: Any, reframes: dict[str, Any], crop_frac: float) -> tuple[float, str, list[dict[str, Any]]]:
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
    box = reframes.get(event_id)
    if box is not None:
        return box.x + box.w / 2, "reframe", []
    return 0.5, "center", [_problem("PORTRAIT_FOCUS_UNKNOWN", "WARN",
                                    f"{event_id}: no tag or reframe says where the subject is; the crop is centred, check it")]


def portrait_segments(plan: dict[str, Any], section: Any, reframes: dict[str, Any], width: int, height: int, fps: float,
                      ) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Partition the master's clock into segments, each cropped around its focus or fitted. Frames, so the video keeps its length."""
    crop_w = int(height * 9 / 16) // 2 * 2
    crop_frac = crop_w / width
    problems: list[dict[str, Any]] = []
    cuts: list[tuple[float, float, str, str]] = [(0.0, plan["title_s"], "fit", "title")]
    events = plan["events"]
    for i, placed in enumerate(events):
        start = placed["start_s"] if i else plan["title_s"]
        end = events[i + 1]["start_s"] if i + 1 < len(events) else plan["body_end_s"]
        cuts.append((start, end, "fit" if placed["kind"] == "CARD" else "crop", placed["event_id"]))
    cuts.append((plan["body_end_s"], plan["total_s"], "fit", "end"))
    segments: list[dict[str, Any]] = []
    for start, end, mode, event_id in cuts:
        f0, f1 = round(start * fps), round(end * fps)
        if f1 <= f0:
            continue
        seg = {"event_id": event_id, "mode": mode, "start_frame": f0, "end_frame": f1,
               "start_s": round(f0 / fps, 3), "end_s": round(f1 / fps, 3)}
        if mode == "crop":
            cx, source, found = focus_for(event_id, section, reframes, crop_frac)
            problems += found
            left = min(max(int(round(cx * width - crop_w / 2)), 0), width - crop_w) // 2 * 2
            seg.update(focus=round(cx, 3), focus_source=source, crop_x=left, crop_w=crop_w)
        segments.append(seg)
    return segments, problems


def portrait_graph(segments: list[dict[str, Any]], height: int) -> str:
    parts, labels = [], []
    for k, s in enumerate(segments):
        trim = f"[0:v]trim=start_frame={s['start_frame']}:end_frame={s['end_frame']},setpts=PTS-STARTPTS"
        if s["mode"] == "crop":
            shape = f"crop={s['crop_w']}:{height}:{s['crop_x']}:0,scale={PORTRAIT_W}:{PORTRAIT_H}:flags=lanczos"
        else:
            shape = f"scale={PORTRAIT_W}:-2:flags=lanczos,pad={PORTRAIT_W}:{PORTRAIT_H}:0:(oh-ih)/2:black"
        parts.append(f"{trim},{shape},setsar=1[s{k}]")
        labels.append(f"[s{k}]")
    return ";".join(parts) + ";" + "".join(labels) + f"concat=n={len(segments)}:v=1:a=0[v]"


def render_portrait(source: Path, segments: list[dict[str, Any]], out: Path, height: int, fps: float) -> Path:
    out.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", str(source), "-filter_complex", portrait_graph(segments, height),
                    "-map", "[v]", "-map", "0:a?", "-c:v", "libx264", "-preset", "medium", "-crf", "18", "-pix_fmt", "yuv420p",
                    "-r", f"{fps:g}", "-c:a", "copy", "-movflags", "+faststart", str(out)], check=True)
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


def grab_frame(video: Path, at_s: float, out: Path, width: int = 1280) -> Path:
    out.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-ss", f"{at_s:.3f}", "-i", str(video), "-frames:v", "1",
                    "-vf", f"scale={width}:-2:flags=lanczos", "-q:v", "2", str(out)], check=True)
    return out


def frame_stats(image: Path) -> tuple[float, float]:
    """(mean luma, luma spread) on a 32x18 reduction."""
    raw = subprocess.run(["ffmpeg", "-v", "error", "-i", str(image), "-vf", "scale=32:18:flags=area,format=gray", "-f", "rawvideo",
                          "-"], capture_output=True, check=True).stdout
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
                if luma < THUMB_MIN_LUMA or luma > THUMB_MAX_LUMA or spread < THUMB_MIN_CONTRAST:
                    path.unlink(missing_ok=True)
                    continue
                burned = not clean(at_s)
                chosen.append({"file": str(path.relative_to(Path(pkg.root))).replace("\\", "/"), "at_s": round(at_s, 3),
                               "event_id": placed["event_id"], "scene": m["scene"], "moment": m["moment"], "device": m["device"],
                               "fact_id": m["fact_id"], "luma": round(luma, 1), "contrast": round(spread, 1),
                               "burned_text": burned, "sha256": sha256_file(path)})
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
          generators: Any = "") -> dict[str, Any]:
    """Write ``versions/`` (9:16 mp4, thumbnails, metadata.json, versions.json) and return the report."""
    from film_pipeline.production import titles as ti
    section = pkg.typed.get("edit")
    if section is None:
        raise ValueError("versions needs a valid 05_edit.json")
    plan = json.loads(Path(cut_report).read_text(encoding="utf-8"))["planned"]
    out = Path(out_dir) if out_dir else versions_dir(pkg.root)
    out.mkdir(parents=True, exist_ok=True)
    width, height, fps = probe_size(master)
    problems: list[dict[str, Any]] = []
    reframes = ti.load_reframes(pkg.root).events
    titles_path = ti.titles_dir(pkg.root) / "titles.json"
    titles_report = json.loads(titles_path.read_text(encoding="utf-8")) if titles_path.is_file() else None
    source = Path(portrait_source) if portrait_source else master
    segments, found = portrait_segments(plan, section, reframes, width, height, fps)
    problems += found
    if titles_report and titles_report.get("cues") and portrait_source is None:
        problems.append(_problem("PORTRAIT_BURNED_TEXT", "WARN",
                                 "the master carries burned-in dialogue cues across the 16:9 frame; the 9:16 crop loses part of them "
                                 "(use --portrait-source with a clean cut or ship the sidecar SRTs)"))
    portrait = render_portrait(source, segments, out / f"{pkg.header.film_id}_9x16.mp4", height, fps)
    thumbs, found = thumbnails(pkg, master, plan, section, out / "thumbs", titles_report)
    problems += found
    p_w, p_h, p_fps = probe_size(portrait)
    versions = [{"name": "master_16x9", "file": str(Path(master)), "width": width, "height": height, "fps": fps,
                 "sha256": sha256_file(master)},
                {"name": "portrait_9x16", "file": str(portrait.relative_to(Path(pkg.root))).replace("\\", "/"), "width": p_w,
                 "height": p_h, "fps": p_fps, "sha256": sha256_file(portrait), "upscale": round(PORTRAIT_H / height, 2),
                 "segments": segments}]
    if (p_w, p_h) != (PORTRAIT_W, PORTRAIT_H):
        problems.append(_problem("PORTRAIT_SIZE", "BLOCK", f"portrait render is {p_w}x{p_h}, expected {PORTRAIT_W}x{PORTRAIT_H}"))
    draft, found = metadata_draft(pkg, plan, [{k: v for k, v in x.items() if k != "segments"} for x in versions], generators=generators)
    problems += found
    draft["thumbnails"] = [t["file"] for t in thumbs]
    (out / "metadata.json").write_text(json.dumps(draft, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    report = {"film_id": pkg.header.film_id, "ok": not any(p["severity"] == "BLOCK" for p in problems),
              "versions": versions, "thumbnails": thumbs, "metadata": "versions/metadata.json", "problems": problems,
              "summary": {"portrait_segments": len(segments), "thumbnails": len(thumbs),
                          "blocks": sum(p["severity"] == "BLOCK" for p in problems),
                          "warnings": sum(p["severity"] == "WARN" for p in problems)}}
    (out / "versions.json").write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return report
