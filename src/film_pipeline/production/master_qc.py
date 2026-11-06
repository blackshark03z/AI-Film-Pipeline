"""Master technical QC (categories 139-144 technical/temporal/audio/sync/colour/delivery QC of the rendered cut).

``check_master(video, ...)`` looks at a rendered, mixed master and writes a CUT-level QC record (``qc/master_qc.json``) with one
``GroupCheck`` per machine group - technical, audio, sync, color, delivery - using ``auto:master_qc`` as reviewer (a machine
may PASS or FAIL those groups; it never judges story, acting or motion).

* **technical** - streams present; resolution, fps, codec and pixel format against the film header; duration against the
  planned clock (``<cut>.cut.json``); black frames, frozen frames and the share of duplicated frames, measured on a 32x18 gray
  reduction of every frame. The title card, the end card and CARD events are static and dark by design and are exempt; a dip
  to black the EDL asks for is exempt too.
* **audio** - codec; integrated loudness and true peak against the target (-14 LUFS +-1.5 LU, <= -1 dBTP); clipping (runs of
  full-scale samples); silent gaps longer than 3 s in the body.
* **sync** - audio and video lengths agree; every dialogue cue of ``titles/titles.json`` is checked against the activity of
  ``audio/stems/dialogue.wav`` (the offset that best aligns the cue with speech; more than 0.3 s off blocks). Without cues or a
  dialogue stem the group stays UNASSESSED - it is never an implicit pass.
* **color** - the share of body frames that are crushed or blown out; the worst deviation left by ``film.py grade``.
* **delivery** - the file is not empty and the moov atom comes first (``+faststart``).

A BLOCK finding makes its group FAIL (P1; a missing stream or an unreadable file is P0), a WARN finding makes it WARN, a clean
group PASSes. The record also keeps the measured numbers. Technical evidence only: it says nothing about whether the film is good.
"""
from __future__ import annotations

import array
import json
import re
import statistics
import subprocess
from pathlib import Path
from typing import Any

from pydantic import Field

from film_pipeline.core import ContractModel
from film_pipeline.production.qc_model import GroupCheck

GROUPS = ("technical", "audio", "sync", "color", "delivery")
REVIEWER = "auto:master_qc"
EVIDENCE = "qc/master_qc.json"
AN_W, AN_H = 32, 18


class MasterSpec(ContractModel):
    width: int = 1280
    height: int = 720
    fps: float = 24.0
    vcodec: str = "h264"
    acodec: str = "aac"
    pix_fmt: str = "yuv420p"
    target_lufs: float = -14.0
    lufs_tol: float = 1.5
    true_peak_max: float = -1.0
    duration_tol_s: float = 0.25
    av_tol_s: float = 0.15
    black_luma: float = 12.0          # mean luma of the reduction (0-255) at or below which a frame is black
    max_black_s: float = 0.5
    warn_black_s: float = 0.2
    freeze_diff: float = 0.08         # mean absolute difference to the previous frame at or below which it is frozen
    freeze_warn_s: float = 2.0
    freeze_fail_s: float = 4.0
    dup_ratio_warn: float = 0.05
    silence_noise_db: float = -50.0
    silence_warn_s: float = 3.0
    clip_level: int = 32700
    clip_run: int = 3
    sync_max_offset_s: float = 0.3
    active_db: float = -45.0
    exposure_low: float = 20.0
    exposure_high: float = 235.0
    exposure_share_warn: float = 0.05


class Finding(ContractModel):
    group: str
    code: str
    severity: str                      # BLOCK | WARN | P0
    detail: str
    at_s: float | None = None


class MasterQc(ContractModel):
    film_id: str
    video: str
    sha256: str
    spec: MasterSpec
    metrics: dict[str, Any] = Field(default_factory=dict)
    findings: list[Finding] = Field(default_factory=list)
    checks: list[GroupCheck] = Field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not any(c.result == "FAIL" for c in self.checks)


def spec_for(pkg: Any | None) -> MasterSpec:
    if pkg is None:
        return MasterSpec()
    w, _, h = pkg.header.resolution.partition("x")
    return MasterSpec(width=int(w), height=int(h), fps=float(pkg.header.fps))


def probe(video: Path) -> dict[str, Any]:
    done = subprocess.run(["ffprobe", "-v", "error", "-show_streams", "-show_format", "-of", "json", str(video)],
                          capture_output=True, text=True, check=True)
    return json.loads(done.stdout)


def _rate(text: str) -> float:
    a, _, b = text.partition("/")
    return float(a) / float(b or 1) if float(b or 1) else 0.0


def frame_series(video: Path) -> dict[str, Any]:
    """Per-frame mean luma and mean absolute difference to the previous frame, on a 32x18 gray reduction."""
    raw = subprocess.run(["ffmpeg", "-v", "error", "-i", str(video), "-an", "-vf", f"scale={AN_W}:{AN_H}:flags=area,format=gray",
                          "-fps_mode", "passthrough", "-f", "rawvideo", "-"], capture_output=True, check=True).stdout
    size = AN_W * AN_H
    luma, diff, previous = [], [], None
    for i in range(0, len(raw) - size + 1, size):
        frame = raw[i:i + size]
        luma.append(sum(frame) / size)
        diff.append(0.0 if previous is None else sum(abs(a - b) for a, b in zip(frame, previous)) / size)
        previous = frame
    return {"luma": luma, "diff": diff}


def _runs(flags: list[bool]) -> list[tuple[int, int]]:
    out, start = [], None
    for i, f in enumerate(flags + [False]):
        if f and start is None:
            start = i
        elif not f and start is not None:
            out.append((start, i))
            start = None
    return out


def _outside(t0: float, t1: float, exempt: list[tuple[float, float]]) -> list[tuple[float, float]]:
    """Parts of [t0, t1] not covered by the exempt windows."""
    pieces = [(t0, t1)]
    for a, b in exempt:
        nxt = []
        for x, y in pieces:
            if b <= x or a >= y:
                nxt.append((x, y))
                continue
            if a > x:
                nxt.append((x, a))
            if b < y:
                nxt.append((b, y))
        pieces = nxt
    return [(x, y) for x, y in pieces if y - x > 1e-6]


def expected_windows(pkg: Any | None, cut_report: dict[str, Any] | None) -> dict[str, list[tuple[float, float]]]:
    """{'static': title, end card, CARD events; 'dark': dips to black the EDL asks for}."""
    static: list[tuple[float, float]] = []
    dark: list[tuple[float, float]] = []
    if not cut_report:
        return {"static": static, "dark": dark}
    plan = cut_report["planned"]
    static += [(0.0, plan["title_s"]), (plan["body_end_s"], plan["total_s"])]
    section = pkg.typed.get("edit") if pkg is not None else None
    for i, placed in enumerate(plan["events"]):
        if placed["kind"] == "CARD":
            static.append((placed["start_s"], placed["end_s"]))
        if section is not None and i < len(section.events) and section.events[i].transition.type == "DIP_TO_BLACK":
            d = section.events[i].transition.duration_s
            dark.append((placed["start_s"] - 0.05, placed["start_s"] + d + 0.05))
    return {"static": static, "dark": dark}


def video_checks(series: dict[str, Any], fps: float, spec: MasterSpec, windows: dict[str, list[tuple[float, float]]],
                 total_s: float) -> tuple[list[Finding], dict[str, Any]]:
    luma, diff = series["luma"], series["diff"]
    n = len(luma)
    exempt = windows["static"] + windows["dark"]

    def free(i0: int, i1: int) -> list[tuple[float, float]]:
        return _outside(i0 / fps, i1 / fps, exempt)

    findings: list[Finding] = []
    for i0, i1 in _runs([v <= spec.black_luma for v in luma]):
        for a, b in free(i0, i1):
            if b - a >= spec.max_black_s:
                findings.append(Finding(group="technical", code="BLACK_FRAMES", severity="BLOCK", at_s=round(a, 3),
                                        detail=f"black for {b - a:.2f} s at {a:.2f} s (> {spec.max_black_s} s)"))
            elif b - a >= spec.warn_black_s:
                findings.append(Finding(group="technical", code="BLACK_FRAMES", severity="WARN", at_s=round(a, 3),
                                        detail=f"black for {b - a:.2f} s at {a:.2f} s"))
    for i0, i1 in _runs([d <= spec.freeze_diff for d in diff]):
        for a, b in free(max(i0 - 1, 0), i1):
            if b - a >= spec.freeze_fail_s:
                findings.append(Finding(group="technical", code="FREEZE", severity="BLOCK", at_s=round(a, 3),
                                        detail=f"picture frozen for {b - a:.2f} s at {a:.2f} s (> {spec.freeze_fail_s} s)"))
            elif b - a >= spec.freeze_warn_s:
                findings.append(Finding(group="technical", code="FREEZE", severity="WARN", at_s=round(a, 3),
                                        detail=f"picture frozen for {b - a:.2f} s at {a:.2f} s"))
    live = [i for i in range(1, n) if not any(a <= i / fps < b for a, b in exempt)]
    dups = sum(1 for i in live if diff[i] <= spec.freeze_diff)
    ratio = dups / len(live) if live else 0.0
    if ratio > spec.dup_ratio_warn:
        findings.append(Finding(group="technical", code="DUPLICATED_FRAMES", severity="WARN",
                                detail=f"{ratio:.1%} of the body frames repeat the previous one (> {spec.dup_ratio_warn:.0%})"))
    body = [luma[i] for i in live]
    off = sum(1 for v in body if v < spec.exposure_low or v > spec.exposure_high)
    share = off / len(body) if body else 0.0
    if share > spec.exposure_share_warn:
        findings.append(Finding(group="color", code="EXPOSURE_RANGE", severity="WARN",
                                detail=f"{share:.1%} of the body frames are crushed (<{spec.exposure_low:g}) or blown out "
                                       f"(>{spec.exposure_high:g}) on mean luma"))
    metrics = {"frames": n, "duplicate_ratio": round(ratio, 4), "exposure_off_share": round(share, 4),
               "body_luma_mean": round(statistics.fmean(body), 2) if body else None}
    return findings, metrics


def clipping(video: Path, spec: MasterSpec) -> list[float]:
    """Seconds at which a run of full-scale samples starts."""
    raw = subprocess.run(["ffmpeg", "-v", "error", "-i", str(video), "-vn", "-ac", "1", "-ar", "48000", "-f", "s16le", "-"],
                         capture_output=True, check=True).stdout
    samples = array.array("h")
    samples.frombytes(raw[: len(raw) // 2 * 2])
    hits, chunk = [], 480
    for base in range(0, len(samples), chunk):
        part = samples[base:base + chunk]
        if not part or (max(part) < spec.clip_level and min(part) > -spec.clip_level):
            continue
        run = 0
        for k, v in enumerate(part):
            run = run + 1 if abs(v) >= spec.clip_level else 0
            if run == spec.clip_run:
                hits.append(round((base + k) / 48000.0, 3))
                break
    return hits


def silent_gaps(video: Path, spec: MasterSpec) -> list[tuple[float, float]]:
    done = subprocess.run(["ffmpeg", "-nostats", "-v", "info", "-i", str(video), "-vn", "-af",
                           f"silencedetect=noise={spec.silence_noise_db}dB:d={spec.silence_warn_s}", "-f", "null", "-"],
                          capture_output=True, text=True, check=True)
    gaps: list[list[float]] = []
    for line in done.stderr.splitlines():
        if (m := re.search(r"silence_start:\s*(-?[\d.]+)", line)):
            gaps.append([max(0.0, float(m.group(1))), float("inf")])
        elif (m := re.search(r"silence_end:\s*(-?[\d.]+)", line)) and gaps:
            gaps[-1][1] = float(m.group(1))
    return [(a, b) for a, b in gaps]


def audio_checks(video: Path, spec: MasterSpec, windows: dict[str, list[tuple[float, float]]], total_s: float,
                 audio_codec: str) -> tuple[list[Finding], dict[str, Any]]:
    from film_pipeline.drama.post import measure_ebur128
    findings: list[Finding] = []
    if audio_codec != spec.acodec:
        findings.append(Finding(group="audio", code="ACODEC", severity="BLOCK", detail=f"audio codec {audio_codec}, wanted {spec.acodec}"))
    loud = measure_ebur128(video)
    lufs, peak = loud["integrated_lufs"], loud["peak_dbfs"]
    if abs(lufs - spec.target_lufs) > spec.lufs_tol:
        findings.append(Finding(group="audio", code="LOUDNESS", severity="BLOCK",
                                detail=f"integrated {lufs} LUFS, target {spec.target_lufs} +-{spec.lufs_tol}"))
    if peak > spec.true_peak_max:
        findings.append(Finding(group="audio", code="TRUE_PEAK", severity="BLOCK",
                                detail=f"peak {peak} dBFS above {spec.true_peak_max}"))
    clips = clipping(video, spec)
    if clips:
        findings.append(Finding(group="audio", code="CLIPPING", severity="BLOCK", at_s=clips[0],
                                detail=f"{len(clips)} clipped passage(s), first at {clips[0]} s"))
    exempt = windows["static"]
    for a, b in silent_gaps(video, spec):
        for x, y in _outside(a, min(b, total_s), exempt):
            if y - x >= spec.silence_warn_s:
                findings.append(Finding(group="audio", code="SILENCE_GAP", severity="WARN", at_s=round(x, 3),
                                        detail=f"no sound for {y - x:.1f} s at {x:.1f} s"))
    return findings, {"integrated_lufs": lufs, "peak_dbfs": peak, "clipped_passages": len(clips)}


def dialogue_activity(stem: Path, spec: MasterSpec, hop_s: float = 0.05) -> list[bool]:
    from film_pipeline.production.mix import _frames_db
    return [db > spec.active_db for db in _frames_db(stem, hop_s)]


def cue_offset(active: list[bool], start_s: float, end_s: float, spec: MasterSpec, hop_s: float = 0.05) -> dict[str, float]:
    """Coverage of the cue by speech, and the shift (|s| <= 1 s) that covers it best (closest to 0 on a tie)."""
    def coverage(shift: float) -> float:
        a, b = int(round((start_s + shift) / hop_s)), int(round((end_s + shift) / hop_s))
        a, b = max(a, 0), min(b, len(active))
        return sum(active[a:b]) / max(b - a, 1) if b > a else 0.0
    shifts = [k * hop_s for k in range(-20, 21)]
    best = max(shifts, key=lambda s: (round(coverage(s), 3), -abs(s)))
    return {"coverage": round(coverage(0.0), 3), "best_shift_s": round(best, 3), "best_coverage": round(coverage(best), 3)}


def sync_checks(root: Path, spec: MasterSpec, video_s: float, audio_s: float) -> tuple[list[Finding], dict[str, Any], bool]:
    """(findings, metrics, assessed): ``assessed`` is False when there are no cues or no dialogue stem."""
    findings: list[Finding] = []
    if abs(video_s - audio_s) > spec.av_tol_s:
        findings.append(Finding(group="sync", code="AV_DURATION", severity="BLOCK",
                                detail=f"video {video_s:.2f} s and audio {audio_s:.2f} s differ by more than {spec.av_tol_s} s"))
    stem, report = root / "audio" / "stems" / "dialogue.wav", root / "titles" / "titles.json"
    if not (stem.is_file() and report.is_file()):
        return findings, {"cues_checked": 0}, False
    cues = [c for c in json.loads(report.read_text(encoding="utf-8")).get("cues", []) if "abs_start_s" in c]
    if not cues:
        return findings, {"cues_checked": 0}, False
    active = dialogue_activity(stem, spec)
    offsets = []
    for c in cues:
        r = cue_offset(active, c["abs_start_s"], c["abs_end_s"], spec)
        if r["coverage"] >= 0.5:
            offsets.append(0.0)
        elif r["best_coverage"] >= 0.5:
            offsets.append(r["best_shift_s"])
            if abs(r["best_shift_s"]) > spec.sync_max_offset_s:
                findings.append(Finding(group="sync", code="SYNC_OFFSET", severity="BLOCK", at_s=c["abs_start_s"],
                                        detail=f"cue at {c['abs_start_s']:.2f} s sits {r['best_shift_s']:+.2f} s from the speech"))
        else:
            findings.append(Finding(group="sync", code="CUE_NO_SPEECH", severity="WARN", at_s=c["abs_start_s"],
                                    detail=f"no clear speech under the cue at {c['abs_start_s']:.2f} s"))
    return findings, {"cues_checked": len(cues), "median_offset_s": statistics.median(offsets) if offsets else None}, True


def faststart(video: Path) -> bool | None:
    """True when the moov atom precedes mdat, None when the container is not an MP4."""
    with video.open("rb") as f:
        while True:
            head = f.read(8)
            if len(head) < 8:
                return None
            size, kind = int.from_bytes(head[:4], "big"), head[4:8]
            if kind == b"moov":
                return True
            if kind == b"mdat":
                return False
            if size == 1:
                size = int.from_bytes(f.read(8), "big")
                f.seek(size - 16, 1)
            elif size < 8:
                return None
            else:
                f.seek(size - 8, 1)


def check_master(video: Path, *, pkg: Any | None = None, spec: MasterSpec | None = None,
                 cut_report: Path | None = None) -> MasterQc:
    from film_pipeline.production.mix import sha256_file
    video = Path(video)
    spec = spec or spec_for(pkg)
    film_id = pkg.header.film_id if pkg is not None else ""
    findings: list[Finding] = []
    metrics: dict[str, Any] = {}
    digest = sha256_file(video) if video.is_file() else ""
    try:
        info = probe(video)
    except (subprocess.CalledProcessError, OSError, ValueError):
        info = {"streams": [], "format": {}}
    v = next((s for s in info["streams"] if s["codec_type"] == "video"), None)
    a = next((s for s in info["streams"] if s["codec_type"] == "audio"), None)
    for kind, stream in (("video", v), ("audio", a)):
        if stream is None:
            findings.append(Finding(group="technical", code="STREAM_MISSING", severity="P0", detail=f"no {kind} stream in {video.name}"))
    assessed = {g: False for g in GROUPS}
    if v is not None:
        assessed["technical"] = assessed["color"] = True
        fps = _rate(v.get("avg_frame_rate", "0/1")) or spec.fps
        if (v["width"], v["height"]) != (spec.width, spec.height):
            findings.append(Finding(group="technical", code="RESOLUTION", severity="BLOCK",
                                    detail=f"{v['width']}x{v['height']}, wanted {spec.width}x{spec.height}"))
        if abs(fps - spec.fps) > 0.01:
            findings.append(Finding(group="technical", code="FPS", severity="BLOCK", detail=f"{fps:.3f} fps, wanted {spec.fps:g}"))
        if v["codec_name"] != spec.vcodec or v.get("pix_fmt") != spec.pix_fmt:
            findings.append(Finding(group="technical", code="VCODEC", severity="BLOCK",
                                    detail=f"{v['codec_name']}/{v.get('pix_fmt')}, wanted {spec.vcodec}/{spec.pix_fmt}"))
        report_path = Path(cut_report) if cut_report else video.with_suffix(".cut.json")
        cut = json.loads(report_path.read_text(encoding="utf-8")) if report_path.is_file() else None
        total = float(info["format"].get("duration") or v.get("duration") or 0.0)
        metrics.update({"duration_s": round(total, 3), "fps": round(fps, 3), "size": f"{v['width']}x{v['height']}"})
        if cut is not None:
            planned = float(cut["planned"]["total_s"])
            metrics["planned_s"] = planned
            if abs(total - planned) > spec.duration_tol_s:
                findings.append(Finding(group="technical", code="DURATION_MISMATCH", severity="BLOCK",
                                        detail=f"{total:.2f} s rendered, {planned:.2f} s planned (> {spec.duration_tol_s} s)"))
        windows = expected_windows(pkg, cut and {"planned": cut["planned"]})
        vf, vm = video_checks(frame_series(video), fps, spec, windows, total)
        findings += vf
        metrics.update(vm)
        if pkg is not None:
            color = Path(pkg.root) / "color" / "color.json"
            if color.is_file():
                summary = json.loads(color.read_text(encoding="utf-8")).get("summary", {})
                metrics["colour_worst_after"] = summary.get("worst_after")
                if summary.get("worst_after", 0) > 6.0:
                    findings.append(Finding(group="color", code="COLOR_MATCH", severity="WARN",
                                            detail=f"film.py grade left a shot {summary['worst_after']} levels from its reference"))
        if a is not None:
            assessed["audio"] = True
            af, am = audio_checks(video, spec, windows, total, a["codec_name"])
            findings += af
            metrics.update(am)
            audio_s = float(a.get("duration") or total)
            sf, sm, assessed["sync"] = sync_checks(Path(pkg.root), spec, float(v.get("duration") or total), audio_s) \
                if pkg is not None else ([], {"cues_checked": 0}, False)
            if pkg is None and abs(float(v.get("duration") or total) - audio_s) > spec.av_tol_s:
                sf = [Finding(group="sync", code="AV_DURATION", severity="BLOCK", detail="video and audio lengths differ")]
            findings += sf
            metrics.update(sm)
    if video.is_file():
        assessed["delivery"] = True
        if video.stat().st_size == 0:
            findings.append(Finding(group="delivery", code="EMPTY_FILE", severity="P0", detail="the file is empty"))
        elif faststart(video) is False:
            findings.append(Finding(group="delivery", code="FASTSTART", severity="WARN",
                                    detail="moov atom after mdat: not streamable (re-mux with -movflags +faststart)"))
    checks = []
    for group in GROUPS:
        mine = [f for f in findings if f.group == group]
        if not assessed[group] and not mine:
            checks.append(GroupCheck(group=group, note="not assessable: " + {  # type: ignore[arg-type]
                "sync": "no dialogue stem or no timed dialogue cues", "audio": "no audio stream"}.get(group, "no media")))
            continue
        worst = "P0" if any(f.severity == "P0" for f in mine) else "FAIL" if any(f.severity == "BLOCK" for f in mine) \
            else "WARN" if mine else "PASS"
        note = "; ".join(f"{f.code}: {f.detail}" for f in mine[:6])
        if worst in ("P0", "FAIL"):
            checks.append(GroupCheck(group=group, result="FAIL", severity="P0" if worst == "P0" else "P1", level="CUT",  # type: ignore[arg-type]
                                     evidence=EVIDENCE, reviewer=REVIEWER, note=note))
        elif worst == "WARN":
            checks.append(GroupCheck(group=group, result="WARN", level="CUT", evidence=EVIDENCE, reviewer=REVIEWER, note=note))  # type: ignore[arg-type]
        else:
            checks.append(GroupCheck(group=group, result="PASS", level="CUT", evidence=EVIDENCE, reviewer=REVIEWER))  # type: ignore[arg-type]
    return MasterQc(film_id=film_id, video=str(video), sha256=digest, spec=spec, metrics=metrics, findings=findings,
                    checks=checks)


def write_record(pkg: Any, record: MasterQc) -> Path:
    path = Path(pkg.root) / "qc" / "master_qc.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(record.model_dump_json(indent=2) + "\n", encoding="utf-8")
    return path
