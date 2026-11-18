"""Drama post: grade, cards, AI label, subtitles and loudness for a cut.

Ported from the film01 post script. ffmpeg + PIL only: ffmpeg drawtext and
libass are unusable on the production machine (no fontconfig), so cards,
the AI label and subtitles are PNG overlays switched by ``enable`` windows,
with an .srt sidecar written from the same cues.

``assemble`` builds picture and per-clip-faded audio; loudness is a separate
step (``normalize_loudness``: two-pass linear loudnorm, then a gain and a
limiter so the true peak stays under ~-0.5 dBFS). Cue timing is estimated;
text comes from the script. A cue is clamped into the shot that speaks it
(``speaker_window``) -- in film01 a cue once ran over the other actor's
close-up.
"""
from __future__ import annotations

import json
import math
import os
import re
import subprocess
import tempfile
from pathlib import Path

from pydantic import Field

from ..core import ContractModel
from ..production.ffjoin import media_timeout, run_ffmpeg

W, H, FPS = 1280, 720, 24
FONT = "C:/Windows/Fonts/arial.ttf"
BOLD = "C:/Windows/Fonts/arialbd.ttf"
GRADE = ("eq=contrast=1.04:saturation=0.92:gamma=0.98,"
         "colorbalance=bs=0.02:rh=0.01")
Fonts = tuple[str, str]            # (regular, bold)
DEFAULT_FONTS: Fonts = (FONT, BOLD)


class SubtitleCue(ContractModel):
    generation_id: str
    start_s: float                 # clip-relative
    end_s: float
    text: str
    speaker_window: tuple[float, float] | None = None   # speaking shot


class Overlay(ContractModel):
    """A full-frame RGBA PNG shown over one clip (clip-relative window),
    with a short alpha fade at both ends; identity tags use it."""
    generation_id: str
    start_s: float
    end_s: float
    png: str
    fade_s: float = 0.25
    fade_in_s: float | None = None
    fade_out_s: float | None = None


def clamp_cues(cues: list[SubtitleCue], notes: list[str] | None = None
               ) -> list[SubtitleCue]:
    """Clamp each cue into its speaker window; drop empty ones (a flag is
    appended to ``notes`` for every clamp or drop)."""
    out: list[SubtitleCue] = []
    for cue in cues:
        start, end = cue.start_s, cue.end_s
        if cue.speaker_window is not None:
            start = max(start, cue.speaker_window[0])
            end = min(end, cue.speaker_window[1])
        if not cue.text.strip() or end - start <= 1e-6:
            if notes is not None:
                notes.append(f"{cue.generation_id}: dropped cue "
                             f"{cue.text!r} ({cue.start_s:g}-{cue.end_s:g})")
            continue
        if notes is not None and (start, end) != (cue.start_s, cue.end_s):
            notes.append(f"{cue.generation_id}: clamped {cue.text!r} "
                         f"{cue.start_s:g}-{cue.end_s:g} -> "
                         f"{start:g}-{end:g}")
        out.append(cue.model_copy(update={"start_s": start, "end_s": end}))
    return out


def _ts(s: float) -> str:
    ms = int(round(s * 1000))
    h, ms = divmod(ms, 3600000)
    m, ms = divmod(ms, 60000)
    sec, ms = divmod(ms, 1000)
    return f"{h:02}:{m:02}:{sec:02},{ms:03}"


def write_srt(cues_abs: list[tuple[float, float, str]], path: Path) -> Path:
    """``cues_abs``: (start_s, end_s, text) on the final timeline."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(f"{i}\n{_ts(a)} --> {_ts(b)}\n{txt}\n"
                              for i, (a, b, txt) in enumerate(cues_abs, 1)),
                    encoding="utf-8")
    return path


def merge_cues(cues_abs: list[tuple[float, float, str]]
               ) -> list[tuple[float, float, str]]:
    """Split overlapping cues into non-overlapping ones, stacking the text
    of every cue active in a segment (earlier start on top). Some players
    drop or garble overlapping SRT cues; an identity tag over a line of
    dialogue is the common case."""
    cuts = sorted({t for a, b, _ in cues_abs for t in (a, b)})
    order = sorted(cues_abs, key=lambda c: c[0])
    out: list[tuple[float, float, str]] = []
    for a, b in zip(cuts, cuts[1:]):
        text = "\n".join(t for s, e, t in order if s < b and a < e)
        if not text:
            continue
        if out and out[-1][2] == text and abs(out[-1][1] - a) < 1e-6:
            out[-1] = (out[-1][0], b, text)
        else:
            out.append((a, b, text))
    return out


def probe_video_duration(path: Path, *, timeout_s: float = 120.0) -> float:
    out = subprocess.run(
        ["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries",
         "stream=duration", "-of", "csv=p=0", str(path)],
        capture_output=True, text=True, check=True, timeout=timeout_s)
    value = out.stdout.strip()
    if value and value != "N/A":
        return float(value)
    out = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration",
                          "-of", "csv=p=0", str(path)], capture_output=True, text=True, check=True, timeout=timeout_s)
    return float(out.stdout.strip())


def cue_offsets(clips: list[Path], lead_s: float) -> dict[str, float]:
    """Start of every clip (keyed by stem) on the final timeline, after a
    title card of ``lead_s``; uses video-stream durations."""
    offsets, t = {}, lead_s
    for clip in clips:
        offsets[clip.stem] = t
        t += probe_video_duration(clip)
    return offsets


def absolute_cues(cues: list[SubtitleCue], offsets: dict[str, float]
                  ) -> list[tuple[float, float, str]]:
    return [(offsets[c.generation_id] + c.start_s,
             offsets[c.generation_id] + c.end_s, c.text) for c in cues]


# ------------------------------------------------------------ PNG builders

def title_card(path: Path, lines: list[tuple[str, int]],
               fonts: Fonts = DEFAULT_FONTS) -> Path:
    """Centered black card; ``lines`` are (text, size), bold above 40 px.
    Used for both the title card and the end card."""
    from PIL import Image, ImageDraw, ImageFont
    img = Image.new("RGB", (W, H), "black")
    d = ImageDraw.Draw(img)
    y = H // 2 - sum(s for _, s in lines) // 2 - 10 * (len(lines) - 1)
    for text, size in lines:
        f = ImageFont.truetype(fonts[1] if size > 40 else fonts[0], size)
        w = d.textlength(text, font=f)
        d.text(((W - w) / 2, y), text, font=f, fill="white")
        y += size + 20
    path.parent.mkdir(parents=True, exist_ok=True)
    img.save(path)
    return path


end_card = title_card


def ai_label_png(path: Path, text: str = "AI-generated", *, size: int = 20,
                 fonts: Fonts = DEFAULT_FONTS) -> Path:
    """Bottom-left semi-transparent label."""
    from PIL import Image, ImageDraw, ImageFont
    img = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    d.text((24, H - 40), text, font=ImageFont.truetype(fonts[0], size),
           fill=(255, 255, 255, 190))
    path.parent.mkdir(parents=True, exist_ok=True)
    img.save(path)
    return path


def subtitle_png(path: Path, text: str, *, size: int = 34,
                 fonts: Fonts = DEFAULT_FONTS) -> Path:
    """Centered subtitle with a translucent box and a black stroke."""
    from PIL import Image, ImageDraw, ImageFont
    img = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    f = ImageFont.truetype(fonts[0], size)
    w = d.textlength(text, font=f)
    x, y = (W - w) / 2, H - 80
    d.rectangle((x - 12, y - 6, x + w + 12, y + size + 10),
                fill=(0, 0, 0, 140))
    d.text((x, y), text, font=f, fill=(255, 255, 255, 255),
           stroke_width=2, stroke_fill=(0, 0, 0, 255))
    path.parent.mkdir(parents=True, exist_ok=True)
    img.save(path)
    return path


TAG_MARGIN, TAG_LINE2 = 38, 38    # frame margin, relation line offset


def _tag_fonts(fonts: Fonts):
    from PIL import ImageFont
    return ImageFont.truetype(fonts[1], 30), ImageFont.truetype(fonts[0], 24)


def identity_tag_size(label: str, relation: str,
                      fonts: Fonts = DEFAULT_FONTS) -> tuple[float, float]:
    """(width, height) in px of the tag text block on the W x H frame."""
    from PIL import Image, ImageDraw
    d = ImageDraw.Draw(Image.new("RGBA", (1, 1)))
    fn, fr = _tag_fonts(fonts)
    return (max(d.textlength(label, font=fn), d.textlength(relation, font=fr)),
            TAG_LINE2 + 24 + 6)


def identity_tag_png(path: Path, label: str, relation: str, anchor_x: float,
                     anchor_y: float = 0.12, *,
                     fonts: Fonts = DEFAULT_FONTS) -> Path:
    """Name (bold) over relation, no box (Owner: no black plate); a black
    stroke keeps it legible on light walls. Centred on ``anchor_x`` beside
    the character's face (never over it) and kept inside the frame."""
    from PIL import Image, ImageDraw
    img = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    fn, fr = _tag_fonts(fonts)
    w, _ = identity_tag_size(label, relation, fonts)
    x = min(max(anchor_x * W - w / 2, TAG_MARGIN), W - TAG_MARGIN - w)
    y = anchor_y * H
    for text, f, dy in ((label, fn, 0), (relation, fr, TAG_LINE2)):
        d.text((x, y + dy), text, font=f, fill=(255, 255, 255, 255),
               stroke_width=2, stroke_fill=(0, 0, 0, 230))
    path.parent.mkdir(parents=True, exist_ok=True)
    img.save(path)
    return path


def context_card_clip(out: Path, lines: list[str], duration_s: float, *,
                      size: int = 40, fonts: Fonts = DEFAULT_FONTS,
                      timeout_s: float | None = None) -> Path:
    """White-on-black card as a clip (silent stereo, same format as the
    takes) to cut into the body: time jumps, facts the picture cannot
    carry. Length comes from ``comprehension.read_time``."""
    png = title_card(out.with_suffix(".png"), [(t, size) for t in lines],
                     fonts)
    run_ffmpeg(
        ["ffmpeg", "-v", "error", "-y", "-loop", "1", "-t", f"{duration_s}",
         "-r", str(FPS), "-i", str(png), "-f", "lavfi", "-t",
         f"{duration_s}", "-i", "anullsrc=r=48000:cl=stereo",
         "-c:v", "libx264", "-pix_fmt", "yuv420p", "-c:a", "aac",
         "-shortest", str(out)],
        timeout_s=timeout_s if timeout_s is not None else media_timeout(max(1.0, duration_s)),
    )
    png.unlink()
    return out


# ---------------------------------------------------------------- assemble

def assemble(clips: list[Path], out: Path, *, cues: list[SubtitleCue],
             title_lines: list[tuple[str, int]],
             end_lines: list[tuple[str, int]], title_s: float = 3.0,
             end_s: float = 4.0, grade: str = GRADE,
             label_text: str = "AI-generated",
             fonts: Fonts = DEFAULT_FONTS,
             overlays: list[Overlay] = (), _body_only: bool = False,
             _edge_fades: bool = True) -> Path:
    """title card + graded clips + end card, AI label over the body,
    subtitle overlays for ``cues`` and faded ``overlays`` (both
    clip-relative, matched to clips by stem). Audio is edge-faded per clip
    but not loudness-normalised."""
    lead_s = 0.0 if _body_only else title_s
    offs = cue_offsets(clips, lead_s)
    durs = [probe_video_duration(c) for c in clips]
    body_end = lead_s + sum(durs)
    abs_cues = absolute_cues(cues, offs)
    abs_ovs = [(offs[o.generation_id] + o.start_s,
                offs[o.generation_id] + o.end_s, o) for o in overlays]
    out.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory() as tmp:
        cards = Path(tmp)
        title = None if _body_only else title_card(cards / "title.png", title_lines, fonts)
        end = None if _body_only else title_card(cards / "end.png", end_lines, fonts)
        label = ai_label_png(cards / "ai_label.png", label_text, fonts=fonts)
        subs = [subtitle_png(cards / f"sub_{i:02}.png", txt, fonts=fonts)
                for i, (_, _, txt) in enumerate(abs_cues, 1)]

        n = len(clips)
        end_idx = n + 1
        if _body_only:
            inputs = [arg for c in clips for arg in ("-i", str(c))]
            ov0 = n
        else:
            inputs = ["-loop", "1", "-t", str(title_s), "-r", str(FPS), "-i", str(title)]
            for c in clips:
                inputs += ["-i", str(c)]
            inputs += ["-loop", "1", "-t", str(end_s), "-r", str(FPS), "-i", str(end)]
            for d in (title_s, end_s):
                inputs += ["-f", "lavfi", "-t", str(d), "-i", "anullsrc=r=48000:cl=stereo"]
            a_title, a_end, ov0 = end_idx + 1, end_idx + 2, end_idx + 3
        for png in [label, *subs, *(o.png for _, _, o in abs_ovs)]:
            inputs += ["-loop", "1", "-i", str(png)]

        fl = [] if _body_only else [f"[0:v]fps={FPS},format=yuv420p,"
              f"fade=t=out:st={title_s - 0.6}:d=0.6[v0]"]
        for i, d in enumerate(durs, 1):
            idx = i - 1 if _body_only else i
            fl.append(f"[{idx}:v]fps={FPS},scale={W}:{H},setsar=1,"
                      f"{grade},format=yuv420p[v{i}]")
            fade = f",afade=t=in:d=0.05,afade=t=out:st={d - 0.08:.3f}:d=0.08" if _edge_fades else ""
            fl.append(f"[{idx}:a]aresample=48000,aformat=channel_layouts=stereo,atrim=0:{d}{fade}[a{i}]")
        if _body_only:
            fl.append("".join(f"[v{k}][a{k}]" for k in range(1, n + 1)) + f"concat=n={n}:v=1:a=1[cv][aout]")
        else:
            fl.append(f"[{end_idx}:v]fps={FPS},format=yuv420p,fade=t=in:d=0.6[v{end_idx}]")
            fl.append(f"[{a_title}:a]anull[a0]")
            fl.append(f"[{a_end}:a]anull[a{end_idx}]")
            fl.append("".join(f"[v{k}][a{k}]" for k in range(end_idx + 1)) +
                      f"concat=n={end_idx + 1}:v=1:a=1[cv][aout]")
        fl.append(f"[cv][{ov0}:v]overlay=0:0:shortest=1:"
                  f"enable='between(t,{lead_s},{body_end:.3f})'[o0]")
        last = "o0"
        for k, (a, b, _) in enumerate(abs_cues, 1):
            fl.append(f"[{last}][{ov0 + k}:v]overlay=0:0:shortest=1:"
                      f"enable='between(t,{a:.3f},{b:.3f})'[o{k}]")
            last = f"o{k}"
        base = ov0 + len(abs_cues) + 1
        for j, (a, b, o) in enumerate(abs_ovs):
            fade_in = o.fade_s if o.fade_in_s is None else o.fade_in_s
            fade_out = o.fade_s if o.fade_out_s is None else o.fade_out_s
            filters = ["format=rgba"]
            if fade_in > 0:
                filters.append(f"fade=t=in:st={a:.3f}:d={fade_in}:alpha=1")
            if fade_out > 0:
                filters.append(f"fade=t=out:st={b - fade_out:.3f}:d={fade_out}:alpha=1")
            fl.append(f"[{base + j}:v]{','.join(filters)}[t{j}]")
            fl.append(f"[{last}][t{j}]overlay=0:0:shortest=1:"
                      f"enable='between(t,{a:.3f},{b:.3f})'[p{j}]")
            last = f"p{j}"
        graph_file = cards / "assemble.filter"
        graph_file.write_text(";".join(fl), encoding="utf-8")
        run_ffmpeg(["ffmpeg", "-v", "error", "-y", *inputs,
                    "-/filter_complex", str(graph_file),
                    "-map", f"[{last}]", "-map", "[aout]",
                    "-c:v", "libx264", "-crf", "18",
                    "-preset", "medium", "-pix_fmt", "yuv420p",
                    *( ["-c:a", "pcm_s16le"] if _body_only else ["-c:a", "aac", "-b:a", "192k"] ),
                    "-movflags", "+faststart", str(out)],
                   timeout_s=media_timeout(body_end + (0.0 if _body_only else end_s)))
    return out


# ---------------------------------------------------------------- loudness

def measure_ebur128(path: Path, *, timeout_s: float = 300.0) -> dict:
    """Integrated loudness and true peak of the first audio stream."""
    proc = subprocess.run(
        ["ffmpeg", "-nostats", "-i", str(path), "-vn", "-af",
         "ebur128=peak=true", "-f", "null", "-"],
        capture_output=True, text=True, check=True, timeout=timeout_s)
    summary = proc.stderr.rsplit("Summary:", 1)[-1]
    lufs = re.search(r"I:\s+(-?[\d.]+|-inf) LUFS", summary)
    peak = re.search(r"Peak:\s+(-?[\d.]+|-inf) dBFS", summary)
    return {"integrated_lufs": float(lufs.group(1)) if lufs else float("-inf"),
            "peak_dbfs": float(peak.group(1)) if peak else float("-inf")}


def _run(*args: str, timeout_s: float = 600.0) -> subprocess.CompletedProcess:
    return subprocess.run(["ffmpeg", "-v", "error", "-nostats", "-y", *args],
                          capture_output=True, text=True, check=True, timeout=timeout_s)


def normalize_loudness(path: Path, *, target_i: float = -14.0,
                       true_peak: float = -1.5, lra: float = 11.0,
                       max_gain_db: float = 3.0, timeout_s: float = 600.0) -> dict:
    """Rewrite ``path`` in place with normalised audio (video copied).

    1. loudnorm measure; 2. linear loudnorm; 3. a make-up gain (target
    minus what pass 2 measured, capped) and a closed-loop ``alimiter`` +
    AAC pass so downsampling/AAC overshoot cannot push true peaks above
    ``true_peak + 0.3`` dBTP. Returns {"integrated_lufs", "peak_dbfs"}.
    """
    probe = subprocess.run(
        ["ffmpeg", "-nostats", "-i", str(path), "-vn", "-af",
         f"loudnorm=I={target_i}:TP={true_peak}:LRA={lra}:print_format=json",
         "-f", "null", "-"], capture_output=True, text=True, check=True, timeout=timeout_s)
    m = json.loads(probe.stderr[probe.stderr.rindex("{"):
                                probe.stderr.rindex("}") + 1])
    if (
        not all(
            math.isfinite(float(m[k]))
            for k in ("input_i", "input_tp", "input_lra", "input_thresh", "target_offset")
        )
        or float(m["input_i"]) <= -69.9
    ):
        return measure_ebur128(path, timeout_s=min(timeout_s, 300.0))
    linear = (f"loudnorm=I={target_i}:TP={true_peak}:LRA={lra}"
              f":measured_I={m['input_i']}:measured_TP={m['input_tp']}"
              f":measured_LRA={m['input_lra']}"
              f":measured_thresh={m['input_thresh']}"
              f":offset={m['target_offset']}:linear=true")
    ceiling_db = true_peak + 0.3
    limit_db = min(-3.5, true_peak - 2.0)
    measured = {"integrated_lufs": target_i, "peak_dbfs": ceiling_db}
    with tempfile.TemporaryDirectory() as tmp:
        p2 = Path(tmp) / "pass2.wav"
        _run("-i", str(path), "-vn", "-af", f"{linear},aresample=48000",
             "-c:a", "pcm_f32le", str(p2), timeout_s=timeout_s)
        pass2_lufs = measure_ebur128(p2, timeout_s=min(timeout_s, 300.0))["integrated_lufs"]
        gain = (target_i - pass2_lufs) if math.isfinite(pass2_lufs) else 0.0
        gain = max(-max_gain_db, min(max_gain_db, gain))
        p3 = Path(tmp) / "pass3.wav"
        tmp_out = path.with_name(path.stem + ".norm" + path.suffix)
        for _ in range(3):
            limit_lin = max(0.0625, min(1.0, 10 ** (limit_db / 20.0)))
            _run("-i", str(p2), "-af",
                 f"aresample=192000,volume={gain:.2f}dB,"
                 f"alimiter=limit={limit_lin:.6f}:attack=1:release=60:level=false,"
                 "aresample=48000", "-c:a", "pcm_f32le", str(p3), timeout_s=timeout_s)
            _run("-i", str(path), "-i", str(p3), "-map", "0:v", "-map", "1:a",
                 "-c:v", "copy", "-c:a", "aac", "-b:a", "256k",
                 "-movflags", "+faststart", str(tmp_out), timeout_s=timeout_s)
            measured = measure_ebur128(tmp_out, timeout_s=min(timeout_s, 300.0))
            if measured["peak_dbfs"] <= ceiling_db:
                break
            limit_db -= (measured["peak_dbfs"] - ceiling_db) + 0.5
    os.replace(tmp_out, path)
    return measured


# ---------------------------------------------------------------- manifest

class PostManifest(ContractModel):
    film: str
    date: str
    source: str
    clips: list[str]
    final: str
    sha256: str
    duration_s: float
    title_s: float
    end_card_s: float
    grade: str
    audio: str
    subtitles: dict = Field(default_factory=dict)
    label: str = ""
    owner_review: str | dict = "PENDING"
    disclosure: dict | None = None   # paths + sha256s, see disclosure.py
