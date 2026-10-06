"""AI-FILM-QUALITY-V2-002 — Phase 12: the blind Owner surface.

Built BEFORE any per-candidate open review: neutral labels only
(BASELINE / CANDIDATE 1 / CANDIDATE 2), candidate order fixed by a
deterministic hash draw, the label->candidate mapping held ONLY in the
separate answer key. The blind packet and the reel carry no intent and
no mapping (leak-checked).
"""
from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from film_pipeline.core import sha256

PKG = ROOT / "projects/quality_v2_002_f2_causality_experiment"
REEL = PKG / "OWNER_F2_CAUSALITY_V2_002_REEL.mp4"
FONT = "C\\:/Windows/Fonts/arial.ttf"

BASELINE_VIDEO = ROOT / ("projects/flow_upload_contract_requal_009/"
                         "reproof/scene_SCENE_F_STORM_GATE/shot_SEQ7_F2C/"
                         "videos/c1a69047933565230870ad22.mp4")
TRIM = (0.0, 5.6)

INTENT_CARD_TEXT = ("AUTHORITATIVE INTENT: The swordsman must cross the "
                    "stone gate against a powerful gust and emerge on the "
                    "far side; the rock is not his destination.")

BLIND_QUESTIONS = [
    "Q1: What is happening to the character?",
    "Q2: What is he trying to accomplish?",
    "Q3: What is preventing him?",
    "Q4: What changes by the end of the shot?",
    "Q5: Does he appear to pass through the gate, stop at the rock, "
    "or do something else?"]


def file_sha(path: Path) -> str:
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def main() -> int:
    freeze = json.loads((PKG / "experiment_freeze_v2_002.json").read_text(
        encoding="utf-8"))
    candidates = {c["candidate_id"]: c for c in freeze["candidates"]}
    videos = {}
    for cid in candidates:
        result = json.loads(
            (PKG / f"scene_SCENE_F_STORM_GATE/shot_{candidates[cid]['shot_id']}"
             f"/result.json").read_text(encoding="utf-8"))
        videos[cid] = Path(result["asset"]["uri_or_path"])

    # deterministic blind draw: CANDIDATE 1 / CANDIDATE 2 order
    draw = sorted(candidates, key=lambda cid: sha256(
        {"blind_order": "V2-002", "candidate_id": cid}))
    mapping = {"CANDIDATE 1": draw[0], "CANDIDATE 2": draw[1]}

    inputs, filters = [], []
    seg_rows = []
    t = 0.0
    segments = [("BASELINE", BASELINE_VIDEO)] + [
        (label, videos[cid]) for label, cid in mapping.items()]
    for stream, (label, video) in enumerate(segments):
        inputs += ["-i", str(video)]
        start, end = TRIM
        filters.append(
            f"[{stream}:v]trim=start={start:.3f}:end={end:.3f},"
            f"setpts=PTS-STARTPTS,fps=24,scale=1280:720,setsar=1,"
            f"drawtext=fontfile='{FONT}':text='{label}':"
            f"fontcolor=white:fontsize=40:box=1:boxcolor=black@0.55:"
            f"boxborderw=12:x=24:y=24[v{stream}]")
        dur = round(end - start, 3)
        seg_rows.append({"reel_start_s": round(t, 3),
                         "reel_end_s": round(t + dur, 3),
                         "section": "BLIND", "label": label,
                         "asset_sha256": file_sha(video)})
        t += dur
    # intent card AFTER the blind section (PIL: safe text rendering)
    card_dir = PKG / "intent_cards"
    card_dir.mkdir(parents=True, exist_ok=True)
    card_png = card_dir / "AUTHORITATIVE_INTENT.png"
    from PIL import Image, ImageDraw, ImageFont
    img = Image.new("RGB", (1280, 720), "black")
    draw = ImageDraw.Draw(img)
    font = ImageFont.truetype("C:/Windows/Fonts/arial.ttf", 34)
    words = INTENT_CARD_TEXT.split()
    lines, line = [], ""
    for word in words:
        trial = (line + " " + word).strip()
        if draw.textlength(trial, font=font) > 1100:
            lines.append(line)
            line = word
        else:
            line = trial
    lines.append(line)
    y = 300 - (len(lines) - 1) * 22
    for text_line in lines:
        draw.text((90, y), text_line, font=font, fill="white")
        y += 46
    img.save(card_png)
    inputs += ["-loop", "1", "-t", "6.0", "-i", str(card_png)]
    filters.append(
        f"[{len(segments)}:v]fps=24,scale=1280:720,setsar=1,"
        f"trim=duration=6.0,setpts=PTS-STARTPTS[v{len(segments)}]")
    seg_rows.append({"reel_start_s": round(t, 3),
                     "reel_end_s": round(t + 6.0, 3),
                     "section": "INTENT", "label": "AUTHORITATIVE INTENT",
                     "asset_sha256": None})
    t += 6.0
    concat = "".join(f"[v{i}]" for i in range(len(segments) + 1))
    filters.append(f"{concat}concat=n={len(segments) + 1}:v=1:a=0[vout]")
    subprocess.run(
        ["ffmpeg", "-y", "-v", "error"] + inputs +
        ["-filter_complex", ";".join(filters), "-map", "[vout]", "-an",
         "-c:v", "libx264", "-preset", "veryfast", "-crf", "18",
         "-pix_fmt", "yuv420p", "-r", "24", str(REEL)], check=True)

    manifest = {
        "version": "owner-f2-compare-manifest-v2-002-v1",
        "checkpoint": "V2002_P12_OWNER_SURFACE_READY",
        "reel": {"path": REEL.name, "sha256": file_sha(REEL),
                 "duration_s": t, "trim_window_s": list(TRIM),
                 "note": "the reel is judged on the canonical 5.6s "
                         "editorial window for every segment"},
        "blind_section_order": ["BASELINE"] + list(mapping),
        "questions": BLIND_QUESTIONS,
        "leak_check": {"mapping_in_reel": False,
                       "mapping_in_manifest_blind_section": False,
                       "answer_key_separate_file": True,
                       "intent_revealed_before_blind_section": False},
        "segments": seg_rows,
        # mapping lives here but the BLIND surfaces (reel, packet) never
        # reference this file; the reviewer answers before opening it
        "answer_key_file": "answer_key_v2_002.json",
    }
    (PKG / "owner_f2_compare_manifest_v2_002.json").write_text(
        json.dumps(manifest, indent=1, ensure_ascii=False),
        encoding="utf-8")

    answer_key = {
        "version": "answer-key-v2-002-v1",
        "leak_discipline": "open ONLY after the blind answers are "
                           "recorded in owner_f2_blind_review_v2_002.json",
        "mapping": mapping,
        "candidates": {cid: {
            "asset_sha256": file_sha(videos[cid]),
            "provider_job_id": json.loads(
                (PKG / f"scene_SCENE_F_STORM_GATE/shot_"
                 f"{candidates[cid]['shot_id']}/result.json")
                .read_text(encoding="utf-8"))["provider_job_id"],
            "design": candidates[cid]["purpose"]} for cid in candidates},
        "baseline": {"asset_sha256": file_sha(BASELINE_VIDEO),
                     "note": "canonical SEQ7_F2C SelectedTake "
                             "(take_91e4997b…)"}}
    (PKG / "answer_key_v2_002.json").write_text(
        json.dumps(answer_key, indent=1, ensure_ascii=False),
        encoding="utf-8")

    blind_packet = {
        "version": "owner-f2-blind-review-v2-002-v1",
        "reel_sha256": file_sha(REEL),
        "instructions": "watch the blind section (BASELINE, CANDIDATE 1, "
                        "CANDIDATE 2) and answer the five questions per "
                        "segment BEFORE opening the answer key; the "
                        "intent card plays after the blind section",
        "questions": BLIND_QUESTIONS,
        "answers": {label: {q: None for q in BLIND_QUESTIONS}
                    for label in ["BASELINE", "CANDIDATE 1", "CANDIDATE 2"]},
        "answered_blind": False,
    }
    (PKG / "owner_f2_blind_review_v2_002.json").write_text(
        json.dumps(blind_packet, indent=1, ensure_ascii=False),
        encoding="utf-8")
    print(json.dumps({"checkpoint": "V2002_P12_OWNER_SURFACE_READY",
                      "reel_sha256": file_sha(REEL)[:16],
                      "blind_order_key_digest": sha256(mapping)[:16]}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
