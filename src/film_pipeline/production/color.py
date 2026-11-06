"""Colour matching (categories 123-125): shots of one scene should read as one light, then the film gets its look.

For every take used by the cut (the EDL's TAKE events; without an EDL the latest take of each shot) the mean R, G, B of
a handful of frames is measured. Per scene a *reference* is chosen - the shot named in ``color/color_plan.json``
(``references: {scene_id: generation_id}``) or, by default, the per-channel median of the scene's shots. Each shot gets
channel gains ``reference / measured`` (white balance and exposure in one), clamped to ``1 +- max_gain`` so a deliberate
lighting change is never flattened; ``skip`` lists shots left alone. The gains are applied in the render
(``edit.render_cut(corrections=...)``, a ``colorchannelmixer`` ahead of the global look ``drama.post.GRADE`` or the plan's
``look``), so the take files stay byte-identical. ``match`` reports, per shot, the deviation from the reference before and
after (measured on a corrected copy), the exposure change in stops and the white-balance shift, and warns
``OUT_OF_RANGE`` where the clamp left a shot far from its reference. A plan change or a new take changes the report; record
it as the post item ``color`` (``film.py grade``), stamped with the picture lock.
"""
from __future__ import annotations

import json
import math
import statistics
import subprocess
import tempfile
from pathlib import Path
from typing import Any

from pydantic import Field

from film_pipeline.core import ContractModel
from film_pipeline.production.edit import gain_filter, resolve_clip

SAMPLE_FRAMES = 12
LUMA = (0.2126, 0.7152, 0.0722)


class ColorPlan(ContractModel):
    references: dict[str, str] = Field(default_factory=dict)   # scene_id -> generation_id used as the reference
    skip: list[str] = Field(default_factory=list)              # generation ids left untouched (deliberate light change)
    max_gain: float = Field(default=0.25, ge=0.0, le=1.0)
    tolerance: float = Field(default=6.0, gt=0)                # 0-255 levels: "matched" when every channel is this close
    look: str = ""                                             # global grade filter; empty: drama.post.GRADE


def plan_path(root: Path) -> Path:
    return Path(root) / "color" / "color_plan.json"


def load_plan(root: Path) -> ColorPlan:
    path = plan_path(root)
    return ColorPlan.model_validate_json(path.read_text(encoding="utf-8")) if path.is_file() else ColorPlan()


def frame_stats(clip: Path, frames: int = SAMPLE_FRAMES) -> dict[str, float]:
    """Mean R, G, B (0-255) and luma over ``frames`` evenly spaced frames, measured on a 32x18 reduction."""
    raw = subprocess.run(
        ["ffmpeg", "-v", "error", "-i", str(clip), "-vf", "fps=3,scale=32:18:flags=area", "-frames:v", str(frames),
         "-f", "rawvideo", "-pix_fmt", "rgb24", "-"], capture_output=True, check=True).stdout
    pixels = len(raw) // 3
    if pixels == 0:
        raise ValueError(f"{clip}: no frames decoded")
    sums = [0, 0, 0]
    for i in range(0, pixels * 3, 3):
        sums[0] += raw[i]
        sums[1] += raw[i + 1]
        sums[2] += raw[i + 2]
    r, g, b = (s / pixels for s in sums)
    return {"r": round(r, 3), "g": round(g, 3), "b": round(b, 3), "luma": round(LUMA[0] * r + LUMA[1] * g + LUMA[2] * b, 3)}


def gains_for(measured: dict[str, float], reference: dict[str, float], max_gain: float) -> tuple[float, float, float]:
    lo, hi = 1.0 - max_gain, 1.0 + max_gain
    return tuple(round(min(hi, max(lo, reference[c] / max(measured[c], 1.0))), 5) for c in "rgb")  # type: ignore[return-value]


def deviation(measured: dict[str, float], reference: dict[str, float]) -> float:
    """Largest channel distance to the reference, in 0-255 levels."""
    return round(max(abs(measured[c] - reference[c]) for c in "rgb"), 3)


def exposure_ev(measured: dict[str, float], reference: dict[str, float]) -> float:
    return round(math.log2(max(reference["luma"], 1.0) / max(measured["luma"], 1.0)), 3)


def wb_shift(measured: dict[str, float], reference: dict[str, float]) -> float:
    """Change of the red/blue balance (log2 of the reference's r/b over the shot's r/b); + = the shot is too blue."""
    return round(math.log2((reference["r"] / max(reference["b"], 1.0)) / (measured["r"] / max(measured["b"], 1.0))), 3)


def used_takes(pkg: Any) -> list[dict[str, str]]:
    """{generation_id, scene_id, take_id, output_file} for the takes the cut uses (latest take per shot without an EDL)."""
    from film_pipeline.production.takes import load_log
    shots = pkg.typed.get("shots")
    if shots is None:
        raise ValueError("colour matching needs a valid 04_shots.json")
    scene = {g.generation_id: g.scene_id for g in shots.generations}
    log = load_log(Path(pkg.root), pkg.header.film_id)
    by_id = {t.take_id: t for t in log.takes}
    edit = pkg.typed.get("edit")
    chosen = []
    if edit is not None and edit.events:
        for e in edit.events:
            if e.kind == "TAKE" and e.take_id in by_id and by_id[e.take_id].generation_id in scene:
                chosen.append(by_id[e.take_id])
    else:
        latest: dict[str, Any] = {}
        for t in log.takes:
            if t.generation_id in scene:
                latest[t.generation_id] = t
        chosen = [latest[g.generation_id] for g in shots.generations if g.generation_id in latest]
    seen, out = set(), []
    for t in chosen:
        if t.take_id not in seen:
            seen.add(t.take_id)
            out.append({"generation_id": t.generation_id, "scene_id": scene[t.generation_id], "take_id": t.take_id,
                        "output_file": t.output_file})
    return out


def match(pkg: Any, *, clips_dir: Path | None = None, plan: ColorPlan | None = None,
          verify: bool = True) -> dict[str, Any]:
    """Measure, choose references, compute gains and (``verify``) re-measure corrected copies for the after-numbers."""
    root = Path(pkg.root)
    plan = plan or load_plan(root)
    takes = used_takes(pkg)
    problems: list[dict[str, str]] = []
    stats: dict[str, dict[str, float]] = {}
    for t in takes:
        clip = resolve_clip(root, t["output_file"], clips_dir)
        if not clip.is_file():
            problems.append({"code": "CLIP_MISSING", "severity": "BLOCK", "detail": f"{t['take_id']}: {clip} not found"})
            continue
        stats[t["take_id"]] = frame_stats(clip)
    scenes: dict[str, list[dict[str, str]]] = {}
    for t in takes:
        scenes.setdefault(t["scene_id"], []).append(t)
    rows, corrections = [], {}
    for scene_id, members in scenes.items():
        have = [m for m in members if m["take_id"] in stats]
        if not have:
            continue
        wanted = plan.references.get(scene_id)
        ref_take = next((m for m in have if m["generation_id"] == wanted), None)
        if wanted and ref_take is None:
            problems.append({"code": "REFERENCE_UNKNOWN", "severity": "WARN",
                             "detail": f"{scene_id}: reference shot {wanted} has no used take; median used"})
        if ref_take is not None:
            reference, source = dict(stats[ref_take["take_id"]]), ref_take["generation_id"]
        else:
            reference = {c: round(statistics.median(stats[m["take_id"]][c] for m in have), 3) for c in ("r", "g", "b")}
            reference["luma"] = round(sum(w * reference[c] for w, c in zip(LUMA, "rgb")), 3)
            source = "median"
        for m in have:
            measured = stats[m["take_id"]]
            skipped = m["generation_id"] in plan.skip or len(have) == 1
            gains = None if skipped else gains_for(measured, reference, plan.max_gain)
            rows.append({"generation_id": m["generation_id"], "scene_id": scene_id, "take_id": m["take_id"],
                         "reference": source, "measured": measured, "reference_stats": reference,
                         "deviation_before": deviation(measured, reference),
                         "exposure_ev": exposure_ev(measured, reference), "wb_shift": wb_shift(measured, reference),
                         "gains": list(gains) if gains else None,
                         "skipped": "single shot" if len(have) == 1 and m["generation_id"] not in plan.skip else
                                    ("plan" if skipped else "")})
            if gains is not None and any(abs(g - 1.0) > 1e-6 for g in gains):
                corrections[m["take_id"]] = gains
    if verify:
        with tempfile.TemporaryDirectory() as tmp:
            for row in rows:
                take = next(t for t in takes if t["take_id"] == row["take_id"])
                if row["gains"] is None:
                    row["after"], row["deviation_after"] = row["measured"], row["deviation_before"]
                    continue
                dst = Path(tmp) / f"{row['take_id']}.mp4"
                subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", str(resolve_clip(root, take["output_file"], clips_dir)),
                                "-vf", gain_filter(tuple(row["gains"])), "-an", "-c:v", "libx264", "-crf", "12",
                                "-pix_fmt", "yuv420p", str(dst)], check=True)
                row["after"] = frame_stats(dst)
                row["deviation_after"] = deviation(row["after"], row["reference_stats"])
    for row in rows:
        after = row.get("deviation_after", row["deviation_before"])
        row["matched"] = after <= plan.tolerance
        if not row["matched"] and not row["skipped"]:
            problems.append({"code": "OUT_OF_RANGE", "severity": "WARN",
                             "detail": f"{row['generation_id']}: still {after} levels from the {row['reference']} reference "
                                       f"after a gain clamped to +-{plan.max_gain}"})
    return {"film_id": pkg.header.film_id, "plan": plan.model_dump(mode="json"), "shots": rows,
            "corrections": {k: list(v) for k, v in corrections.items()}, "problems": problems,
            "ok": not any(p["severity"] == "BLOCK" for p in problems),
            "summary": {"shots": len(rows), "corrected": len(corrections),
                        "worst_before": max((r["deviation_before"] for r in rows), default=0.0),
                        "worst_after": max((r.get("deviation_after", r["deviation_before"]) for r in rows), default=0.0)}}


def corrections_of(report: dict[str, Any]) -> dict[str, tuple[float, float, float]]:
    return {k: tuple(v) for k, v in report["corrections"].items()}  # type: ignore[misc]


def write_report(pkg: Any, report: dict[str, Any]) -> Path:
    path = Path(pkg.root) / "color" / "color.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return path


def load_report(root: Path) -> dict[str, Any] | None:
    path = Path(root) / "color" / "color.json"
    return json.loads(path.read_text(encoding="utf-8")) if path.is_file() else None
