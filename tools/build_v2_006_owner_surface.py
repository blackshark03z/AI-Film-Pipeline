"""AI-FILM-QUALITY-V2-006 — Phase 14: the Owner review surface.

OWNER_REVIEW/V2_006/: BASELINE_F2.mp4, F2A.mp4, F2B.mp4,
NEW_F2_PAIR.mp4, COMPARE_REEL.mp4 (BASELINE -> NEW PAIR -> question
card, Vietnamese verbatim). Sources never modified; copies SHA-
verified. No promotion.
"""
from __future__ import annotations

import hashlib
import json
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from PIL import Image, ImageDraw, ImageFont

PKG = ROOT / "projects/quality_v2_006_f2_decomposed_live"
REVIEW_DIR = ROOT / "OWNER_REVIEW/V2_006"
REEL = PKG / "OWNER_F2_DECOMPOSED_V2_006_REEL.mp4"
FONT = "C:/Windows/Fonts/arial.ttf"
TRIM = (0.0, 2.8)

BASELINE_F2 = (ROOT / "projects/flow_upload_contract_requal_009/reproof/"
               "scene_SCENE_F_STORM_GATE/shot_SEQ7_F2C/videos/"
               "c1a69047933565230870ad22.mp4")

QUESTIONS = [
    "1. Muc tieu hanh dong co ro khong?",
    "2. Cu cat co khien ban tu nhien hieu rang anh ta da vuot qua cong khong?",
    "3. Nhan vat con quanh quan canh tang da khong?",
    "4. Huong di chuyen co lien mach khong?",
    "5. F2B co ro rang o PHIA BEN KIA cong khong?",
    "6. Hai-shot version co tu nhien hon F2 cu khong?",
    "7. Pair nay co du tot de dung trong phim khong?"]


def file_sha(path: Path) -> str:
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def question_card(out: Path) -> None:
    img = Image.new("RGB", (1280, 720), "black")
    d = ImageDraw.Draw(img)
    title = ImageFont.truetype(FONT, 28)
    font = ImageFont.truetype(FONT, 24)
    d.text((640, 46), "CAU HOI CHO OWNER (V2-006 - F2 DECOMPOSED PAIR)",
           font=title, fill="white", anchor="mm")
    y = 118
    for q in QUESTIONS:
        d.text((70, y), q, font=font, fill="white")
        y += 78
    d.text((640, 696), "Worker verdicts are advisory; the Owner visual "
           "read is authoritative.", font=ImageFont.truetype(FONT, 18),
           fill="#adb5bd", anchor="mm")
    out.parent.mkdir(parents=True, exist_ok=True)
    img.save(out)


def main() -> int:
    gov = json.loads((PKG / "candidates_governance_v2_006.json").read_text(
        encoding="utf-8"))
    videos = {}
    for entry in gov["candidates"]:
        videos[entry["candidate_id"]] = Path(
            entry["custody"]["video"])
    pair = PKG / "NEW_F2_PAIR.mp4"

    inputs, filters = [], []
    seg_rows = []
    t = 0.0
    segments = [("BASELINE F2", BASELINE_F2, (0.0, 2.8)),
                ("NEW F2A", videos["F2A-V2-006"], TRIM),
                ("NEW F2B", videos["F2B-V2-006"], TRIM)]
    for stream, (label, video, (start, end)) in enumerate(segments):
        inputs += ["-i", str(video)]
        filters.append(
            f"[{stream}:v]trim=start={start:.3f}:end={end:.3f},"
            f"setpts=PTS-STARTPTS,fps=24,scale=1280:720,setsar=1,"
            f"drawtext=fontfile='C\\:/Windows/Fonts/arial.ttf':"
            f"text='{label}':fontcolor=white:fontsize=40:box=1:"
            f"boxcolor=black@0.55:boxborderw=12:x=24:y=24[v{stream}]")
        dur = round(end - start, 3)
        seg_rows.append({"reel_start_s": round(t, 3),
                         "reel_end_s": round(t + dur, 3), "label": label,
                         "asset_sha256": file_sha(video)})
        t += dur
    card = PKG / "owner_questions_card.png"
    question_card(card)
    inputs += ["-loop", "1", "-t", "14.0", "-i", str(card)]
    filters.append(
        f"[{len(segments)}:v]fps=24,scale=1280:720,setsar=1,"
        f"trim=duration=14.0,setpts=PTS-STARTPTS[v{len(segments)}]")
    seg_rows.append({"reel_start_s": round(t, 3),
                     "reel_end_s": round(t + 14.0, 3),
                     "label": "OWNER QUESTIONS", "asset_sha256": None})
    concat = "".join(f"[v{i}]" for i in range(len(segments) + 1))
    filters.append(f"{concat}concat=n={len(segments) + 1}:v=1:a=0[vout]")
    subprocess.run(
        ["ffmpeg", "-y", "-v", "error"] + inputs +
        ["-filter_complex", ";".join(filters), "-map", "[vout]", "-an",
         "-c:v", "libx264", "-preset", "veryfast", "-crf", "18",
         "-pix_fmt", "yuv420p", "-r", "24", str(REEL)], check=True)

    REVIEW_DIR.mkdir(parents=True, exist_ok=True)
    copies = {"BASELINE_F2.mp4": BASELINE_F2,
              "F2A.mp4": videos["F2A-V2-006"],
              "F2B.mp4": videos["F2B-V2-006"],
              "NEW_F2_PAIR.mp4": pair,
              "COMPARE_REEL.mp4": REEL}
    copied = {}
    for name, src in copies.items():
        dst = REVIEW_DIR / name
        shutil.copyfile(src, dst)
        assert file_sha(src) == file_sha(dst), name
        copied[name] = {"path": str(dst), "sha256": file_sha(dst)}

    manifest = {
        "version": "owner-f2-decomposed-review-manifest-v2-006-v1",
        "checkpoint": "V2006_P14_OWNER_SURFACE_READY",
        "reel": {"path": str(REEL.relative_to(ROOT)),
                 "sha256": file_sha(REEL),
                 "order": ["BASELINE F2 (2.8s)", "NEW F2A (2.8s)",
                           "NEW F2B (2.8s)", "OWNER QUESTIONS"],
                 "note": "the pair join NEW_F2_PAIR.mp4 = F2A 2.8s + "
                         "F2B 2.8s = 5.6s (the frozen editorial "
                         "solution)"},
        "segments": seg_rows, "questions": QUESTIONS,
        "review_copies": copied,
        "pair_state": gov["atomic_pair"]["pair_state"]}
    (PKG / "owner_review_manifest_v2_006.json").write_text(
        json.dumps(manifest, indent=1, ensure_ascii=False),
        encoding="utf-8")

    items = []
    for entry in gov["candidates"]:
        items.append({
            "candidate_id": entry["candidate_id"],
            "asset_sha256": entry["custody"]["asset_sha256"],
            "state": entry["state"],
            "review_refusal": entry["review_refusal"],
            "spatial_qc": entry["spatial_qc"],
            "camera_qc": entry["camera_qc"]})
    template = {
        "version": "owner-f2-decomposed-decision-template-v2-006-v1",
        "checkpoint": "V2006_P14_DECISION_SURFACE",
        "atomic_pair_contract": "the pair is ONE editorial solution; no "
                                "option selects one half",
        "decision_options": ["SELECT_F2A_F2B_PAIR", "REJECT_ALL",
                             "KEEP_CANONICAL", "NEEDS_REPAIR", "DEFER"],
        "decision": None, "selected_pair": None, "note": "",
        "pair_state": gov["atomic_pair"]["pair_state"],
        "worker_verdicts_are_advisory": True,
        "candidates": items,
        "review_copies": copied,
        "no_promotion_in_this_package": True}
    (PKG / "owner_f2_pair_decision_v2_006.template.json").write_text(
        json.dumps(template, indent=1, ensure_ascii=False),
        encoding="utf-8")
    print(json.dumps({"checkpoint": "V2006_P14_OWNER_SURFACE_READY",
                      "reel_sha256": file_sha(REEL)[:16],
                      "copies": {k: v["sha256"][:12]
                                 for k, v in copied.items()}}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
