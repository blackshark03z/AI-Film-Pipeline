"""AI-FILM-QUALITY-V2-004 — Phase 9 (Owner review reel + review copies)
and Phase 10 (decision template).

Reel order: BASELINE -> CANDIDATE A -> CANDIDATE B with simple neutral
labels (NOT blind: the Owner is explicitly reviewing the spatial
repair), then the Owner question card (Vietnamese, verbatim from the
package). The four review files are COPIES into OWNER_REVIEW/V2_004/
with SHA verification; sources are never modified. No promotion.
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
from film_pipeline.quality_repair_v2 import QualityReviewReceipt

PKG = ROOT / "projects/quality_v2_004_f2_blocking"
REVIEW_DIR = ROOT / "OWNER_REVIEW/V2_004"
REEL = PKG / "OWNER_F2_BLOCKING_V2_004_REEL.mp4"
FONT = "C:/Windows/Fonts/arial.ttf"
TRIM = (0.0, 5.6)

BASELINE_VIDEO = (ROOT / "projects/flow_upload_contract_requal_009/"
                  "reproof/scene_SCENE_F_STORM_GATE/shot_SEQ7_F2C/videos/"
                  "c1a69047933565230870ad22.mp4")

QUESTIONS = [
    "1. Nhan vat bat dau o phia nao cua cong?",
    "2. Anh ta dang co di toi dau?",
    "3. Anh ta co di XUYEN QUA cong hay chi quanh quan canh da?",
    "4. Co luc nao tang da trong giong muc tieu cua anh ta khong?",
    "5. Cuoi shot, anh ta co ro rang o phia ben kia cong khong?",
    "6. A hay B doc muc tieu hanh dong ro hon?",
    "7. Co candidate nao thuc su dat chat luong co the dung khong?"]


def file_sha(path: Path) -> str:
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def question_card(out: Path) -> None:
    img = Image.new("RGB", (1280, 720), "black")
    d = ImageDraw.Draw(img)
    font = ImageFont.truetype(FONT, 26)
    title = ImageFont.truetype(FONT, 30)
    d.text((640, 50), "CAU HOI CHO OWNER (V2-004 - F2 BLOCKING)",
           font=title, fill="white", anchor="mm")
    y = 130
    for q in QUESTIONS:
        d.text((80, y), q, font=font, fill="white")
        y += 74
    d.text((640, 700), "Owner visual read is authoritative.",
           font=ImageFont.truetype(FONT, 20), fill="#adb5bd", anchor="mm")
    out.parent.mkdir(parents=True, exist_ok=True)
    img.save(out)


def main() -> int:
    cands = {}
    for cid, shot in (("F2C-V2-004-A", "SEQ7_F2C_V2_004_A"),
                      ("F2C-V2-004-B", "SEQ7_F2C_V2_004_B")):
        result = json.loads(
            (PKG / f"scene_SCENE_F_STORM_GATE/shot_{shot}/result.json")
            .read_text(encoding="utf-8"))
        cands[cid] = Path(result["asset"]["uri_or_path"])

    inputs, filters = [], []
    seg_rows = []
    t = 0.0
    segments = [("BASELINE", BASELINE_VIDEO),
                ("CANDIDATE A", cands["F2C-V2-004-A"]),
                ("CANDIDATE B", cands["F2C-V2-004-B"])]
    for stream, (label, video) in enumerate(segments):
        inputs += ["-i", str(video)]
        start, end = TRIM
        filters.append(
            f"[{stream}:v]trim=start={start:.3f}:end={end:.3f},"
            f"setpts=PTS-STARTPTS,fps=24,scale=1280:720,setsar=1,"
            f"drawtext=fontfile='C\\:/Windows/Fonts/arial.ttf':"
            f"text='{label}':fontcolor=white:fontsize=40:box=1:"
            f"boxcolor=black@0.55:boxborderw=12:x=24:y=24[v{stream}]")
        dur = round(end - start, 3)
        seg_rows.append({"reel_start_s": round(t, 3),
                         "reel_end_s": round(t + dur, 3),
                         "label": label,
                         "asset_sha256": file_sha(video)})
        t += dur
    card = PKG / "owner_questions_card.png"
    question_card(card)
    inputs += ["-loop", "1", "-t", "12.0", "-i", str(card)]
    filters.append(
        f"[{len(segments)}:v]fps=24,scale=1280:720,setsar=1,"
        f"trim=duration=12.0,setpts=PTS-STARTPTS[v{len(segments)}]")
    seg_rows.append({"reel_start_s": round(t, 3),
                     "reel_end_s": round(t + 12.0, 3),
                     "label": "OWNER QUESTIONS", "asset_sha256": None})
    concat = "".join(f"[v{i}]" for i in range(len(segments) + 1))
    filters.append(
        f"{concat}concat=n={len(segments) + 1}:v=1:a=0[vout]")
    subprocess.run(
        ["ffmpeg", "-y", "-v", "error"] + inputs +
        ["-filter_complex", ";".join(filters), "-map", "[vout]", "-an",
         "-c:v", "libx264", "-preset", "veryfast", "-crf", "18",
         "-pix_fmt", "yuv420p", "-r", "24", str(REEL)], check=True)

    # review copies (never modifying sources)
    REVIEW_DIR.mkdir(parents=True, exist_ok=True)
    copies = {
        "BASELINE.mp4": BASELINE_VIDEO,
        "CANDIDATE_A.mp4": cands["F2C-V2-004-A"],
        "CANDIDATE_B.mp4": cands["F2C-V2-004-B"],
        "COMPARE_REEL.mp4": REEL}
    copied = {}
    for name, src in copies.items():
        dst = REVIEW_DIR / name
        shutil.copyfile(src, dst)
        sha_src, sha_dst = file_sha(src), file_sha(dst)
        assert sha_src == sha_dst, name
        copied[name] = {"path": str(dst), "sha256": sha_dst}

    manifest = {
        "version": "owner-f2-blocking-review-manifest-v2-004-v1",
        "checkpoint": "V2004_P9_OWNER_SURFACE_READY",
        "reel": {"path": str(REEL.relative_to(ROOT)),
                 "sha256": file_sha(REEL),
                 "order": ["BASELINE", "CANDIDATE A", "CANDIDATE B",
                           "OWNER QUESTIONS"],
                 "trim_window_s": list(TRIM),
                 "blind": False,
                 "blind_note": "mapping is explicit because the Owner is "
                               "reviewing the spatial repair directly"},
        "segments": seg_rows,
        "review_copies": copied,
        "questions": QUESTIONS}
    (PKG / "owner_review_manifest_v2_004.json").write_text(
        json.dumps(manifest, indent=1, ensure_ascii=False),
        encoding="utf-8")

    # Phase 10: decision template (future authority only; no promotion)
    gov = json.loads((PKG / "candidates_governance_v2_004.json").read_text(
        encoding="utf-8"))
    items = []
    for entry in gov["candidates"]:
        item = {"candidate_id": entry["candidate_id"],
                "select_by_asset_sha256":
                    entry["custody"]["asset_sha256"],
                "state": entry.get("governed", {}).get(
                    "owner_decision_state", entry["state"])}
        if "review_refusal" in entry:
            item["review_refusal"] = entry["review_refusal"]
        else:
            review = QualityReviewReceipt.model_validate(entry["review"])
            item["tradeoff_summary"] = review.tradeoff_summary()
        item["spatial_qc"] = entry.get("spatial_qc")
        item["camera_qc"] = entry.get("camera_qc")
        items.append(item)
    template = {
        "version": "owner-f2-blocking-decision-template-v2-004-v1",
        "checkpoint": "V2004_P10_DECISION_SURFACE",
        "instructions": [
            "choose EXACTLY ONE option; a selection binds the exact "
            "candidate asset sha256",
            "worker S-QC verdicts are advisory; the Owner visual read "
            "is authoritative (do NOT repeat the V2-002 mistake in "
            "either direction)",
            "NO promotion runs in this package: a selection is FUTURE "
            "authority only; promotion requires a dedicated "
            "promotion-adapter package",
            "KEEP_CANONICAL / REJECT_ALL / DEFER / NEEDS_REPAIR leave "
            "the canonical film untouched; QD-001 stays ACTIVE unless "
            "an Owner-selected promotion completes in a later package"],
        "decision_options": ["SELECT_A", "SELECT_B", "REJECT_ALL",
                             "KEEP_CANONICAL", "NEEDS_REPAIR", "DEFER"],
        "decision": None, "selected_asset_sha256": None, "note": "",
        "review_copies": copied, "candidates": items,
        "canonical_predecessor": gov["source_canonical_take"],
        "no_promotion_in_this_package": True}
    (PKG / "owner_f2_blocking_decision_v2_004.template.json").write_text(
        json.dumps(template, indent=1, ensure_ascii=False),
        encoding="utf-8")
    print(json.dumps({"checkpoint": "V2004_P9_OWNER_SURFACE_READY",
                      "reel_sha256": file_sha(REEL)[:16],
                      "copies": {k: v["sha256"][:12]
                                 for k, v in copied.items()}}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
