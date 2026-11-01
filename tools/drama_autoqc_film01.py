"""Run WP4 auto-QC over film01 (calibration + negative controls).

Writes docs/drama/film01_takes/qc/autoqc_film01.json and prints a table.
Needs extra `qc` and the models from tools/drama_fetch_qc_models.py.
Usage: PYTHONPATH=src python tools/drama_autoqc_film01.py
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

from film_pipeline.drama import autoqc as q

ROOT = Path(__file__).resolve().parents[1]
TAKES = ROOT / "docs/drama/film01_takes/noref"
PROMPTS = ROOT / "docs/drama/film01_prompts/noref"
OUT = ROOT / "docs/drama/film01_takes/qc/autoqc_film01.json"
SIDE_OF = {"NORA": "left", "DOYLE": "right"}
ANCHOR_CLIP, ANCHOR_TIMES = "SC01_g1", (1.0, 2.5, 4.0)
ACCEPTED = [f"SC0{s}_g{g}" for s in range(1, 6) for g in (1, 2)]
SHOT_RE = re.compile(r"Shot (\d+) \(([\d.]+)-([\d.]+)s\):\s*(.*?)"
                     r"(?=Shot \d+ \(|English dialogue|Sound:|$)", re.S)
INSET_S = 0.3        # stay clear of the hard cuts


def planned_scale(text: str) -> str:
    t = text.lower()
    if "close-up" in t:
        return "CU"
    if "shoulder" in t:
        return "MCU"                   # over-the-shoulder on one face
    if "medium" in t:
        return "MS"
    return "MS"                        # wide two-shot: faces 0.1-0.2 of H


def plan_shots(prompt_name: str) -> list[dict]:
    text = (PROMPTS / f"{prompt_name}.txt").read_text(encoding="utf-8")
    return [{"shot": int(m[1]), "start": float(m[2]), "end": float(m[3]),
             "text": m[4].strip()[:60], "planned": planned_scale(m[4])}
            for m in SHOT_RE.finditer(text)]


def scale_for(clip: str, prompt_name: str, n_per_shot: int = 4) -> list[dict]:
    rows = []
    for shot in plan_shots(prompt_name):
        window = (shot["start"] + INSET_S, shot["end"] - INSET_S)
        rep = q.shot_scale_report(TAKES / f"{clip}.mp4", shot["planned"],
                                  n_per_shot, window=window)
        rows.append({**shot, "majority": rep.majority,
                     "per_frame": rep.per_frame,
                     "band_distance": rep.band_distance,
                     "warn": bool(rep.issues)})
    return rows


def ident(clip: str, anchors) -> dict:
    rep = q.identity_report(TAKES / f"{clip}.mp4", anchors, side_of=SIDE_OF)
    return {"characters": {c.character: c.model_dump(exclude={"character"})
                           for c in rep.characters},
            "warn": [i.detail for i in rep.issues]}


def main() -> int:
    if not q.models_available():
        print("models missing: run tools/drama_fetch_qc_models.py")
        return 1
    anchors = [q.anchor_from_clip(c, TAKES / f"{ANCHOR_CLIP}.mp4", t, s)
               for t in ANCHOR_TIMES for c, s in SIDE_OF.items()]
    result: dict = {
        "anchors": {"clip": f"{ANCHOR_CLIP}.mp4", "at_s": list(ANCHOR_TIMES),
                    "side_of": SIDE_OF},
        "thresholds": {
            "identity_mean_min": q.IDENTITY_MEAN_MIN,
            "identity_min_min": q.IDENTITY_MIN_MIN,
            "scale_bands_height_ratio": dict(q.SCALE_BANDS),
            "scale_tolerance_bands": 1,
            "set_min_inliers": q.SET_MIN_INLIERS},
    }

    # negative controls: all accepted clips
    neg = {}
    for clip in ACCEPTED:
        neg[clip] = {"identity": ident(clip, anchors),
                     "scale": scale_for(clip, clip)}
    result["negative_controls"] = neg
    result["false_warns"] = {
        "identity": [c for c, v in neg.items() if v["identity"]["warn"]],
        "shot_scale": [c for c, v in neg.items()
                       if any(s["warn"] for s in v["scale"])]}
    # anchor clip scores itself: exclude it from the honest count
    result["false_warns"]["note"] = (
        f"{ANCHOR_CLIP} supplies the anchors (self-match)")

    def nora_range(key: str):
        vals = [v["identity"]["characters"]["NORA"][key]
                for c, v in neg.items() if c != ANCHOR_CLIP
                and v["identity"]["characters"]["NORA"][key] is not None]
        return [round(min(vals), 3), round(max(vals), 3)]

    defects = {}
    for name in ("SC03_g1_rejected_hair", "SC03_g1_rejected_curly"):
        r = ident(name, anchors)
        nora = r["characters"]["NORA"]
        defects[name] = {
            "check": "IDENTITY_DRIFT (NORA, face embedding)", **r,
            "score": nora["mean_similarity"],
            "accepted_nora_mean_range": nora_range("mean_similarity"),
            "caught": bool(r["warn"]),
            "head_region": {
                "score": nora["mean_head_similarity"],
                "accepted_nora_range": nora_range("mean_head_similarity"),
                "separates": nora["mean_head_similarity"] <
                nora_range("mean_head_similarity")[0]}}
    wd = "SC03_g2_rejected_wrong_doyle"
    r = ident(wd, anchors)
    defects[wd + ":identity"] = {
        "check": "IDENTITY_DRIFT (DOYLE)", **r,
        "score": r["characters"]["DOYLE"]["mean_similarity"],
        "accepted_doyle_mean_range": [round(min(
            v["identity"]["characters"]["DOYLE"]["mean_similarity"]
            for c, v in neg.items() if c != ANCHOR_CLIP), 3), round(max(
            v["identity"]["characters"]["DOYLE"]["mean_similarity"]
            for c, v in neg.items() if c != ANCHOR_CLIP), 3)],
        "caught": bool(r["warn"])}
    for clip in (wd, "SC03_g2"):
        rows = scale_for(clip, "SC03_g2")
        defects[f"{clip}:scale_planned_CU"] = {
            "check": "SHOT_SCALE_MISMATCH", "shots": rows,
            "caught": any(s["warn"] for s in rows),
            "caught_if_tolerance_0": any(
                s["band_distance"] != 0 for s in rows)}
    handoffs = {}
    for s in range(1, 6):
        rep = q.handoff_set_report(TAKES / f"SC0{s}_g1.mp4",
                                   TAKES / f"SC0{s}_g2.mp4")
        handoffs[f"SC0{s}_g1->g2"] = {**rep.similarity.model_dump(),
                                      "warn": bool(rep.issues)}
    defects["SC03_handoff_set"] = {
        "check": "SET_DRIFT", "handoffs": handoffs,
        "caught": handoffs["SC03_g1->g2"]["warn"],
        "stands_out": False if any(
            k != "SC03_g1->g2" and
            v["inliers"] >= handoffs["SC03_g1->g2"]["inliers"]
            for k, v in handoffs.items()) else True}
    result["known_defects"] = defects
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(result, indent=2), encoding="utf-8")

    print(f"{'clip':30} {'NORA m/min':>11} {'DOYLE m/min':>12}  scale")
    for clip, v in neg.items():
        ch = v["identity"]["characters"]
        f = lambda c: (f"{ch[c]['mean_similarity']:.2f}/"
                       f"{ch[c]['min_similarity']:.2f}"
                       if ch[c]["mean_similarity"] is not None else "-")
        sc = ",".join(f"{s['planned']}>{s['majority']}" +
                      ("!" if s["warn"] else "") for s in v["scale"])
        print(f"{clip:30} {f('NORA'):>11} {f('DOYLE'):>12}  {sc}"
              f"{'  WARN' if v['identity']['warn'] else ''}")
    print("\nknown defects")
    for k, v in defects.items():
        print(f"{k:45} score={v.get('score')} caught={v['caught']}")
    print("false WARNs:", result["false_warns"])
    return 0


if __name__ == "__main__":
    sys.exit(main())
