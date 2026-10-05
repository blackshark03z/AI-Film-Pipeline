"""AI-FILM-QUALITY-V2-008 — Phase 14: the Owner review surface."""
from __future__ import annotations

import hashlib
import json
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys_p = str(ROOT / "src")
if sys_p not in sys.path:
    sys.path.insert(0, sys_p)

PKG = ROOT / "projects/quality_v2_008_world_anchored_live"
REVIEW_DIR = ROOT / "OWNER_REVIEW/V2_008"
REEL = PKG / "OWNER_F2_WORLD_ANCHORED_V2_008_REEL.mp4"
FONT = "C:/Windows/Fonts/arial.ttf"
BASELINE_F2 = (ROOT / "projects/flow_upload_contract_requal_009/reproof/"
               "scene_SCENE_F_STORM_GATE/shot_SEQ7_F2C/videos/"
               "c1a69047933565230870ad22.mp4")

QUESTIONS = [
    "1. F2A co vao hanh dong du nhanh khong?",
    "2. F2A co con rut kiem hoac lam dong tac thua khong?",
    "3. F2B co ro rang dang o phia ben kia cong khong?",
    "4. Hai shot co cung mot the gioi / cung cong da khong?",
    "5. Cu cat co tu nhien khien ban hieu 'anh ta da vuot qua cong' khong?",
    "6. Nhan vat con luan quan quanh da khong?",
    "7. Pair moi co du chat luong dung trong phim khong?"]


def file_sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def question_card(out):
    from PIL import Image, ImageDraw, ImageFont
    img = Image.new("RGB", (1280, 720), "black")
    d = ImageDraw.Draw(img)
    d.text((640, 46), "CAU HOI CHO OWNER (V2-008 - F2 WORLD-ANCHORED)",
           font=ImageFont.truetype(FONT, 28), fill="white", anchor="mm")
    y = 118
    for q in QUESTIONS:
        d.text((70, y), q, font=ImageFont.truetype(FONT, 24),
               fill="white")
        y += 78
    d.text((640, 696), "Worker verdicts advisory; Owner read "
           "authoritative.", font=ImageFont.truetype(FONT, 18),
           fill="#adb5bd", anchor="mm")
    out.parent.mkdir(parents=True, exist_ok=True)
    img.save(out)


def main() -> int:
    gov = json.loads((PKG / "candidates_governance_v2_008.json")
                     .read_text(encoding="utf-8"))
    vids = {c["candidate_id"]: Path(c["custody"]["video"])
            for c in gov["candidates"]}
    pair = PKG / "NEW_F2_PAIR.mp4"
    inputs, filters = [], []
    seg_rows, t = [], 0.0
    segments = [("BASELINE F2", BASELINE_F2), ("NEW F2A", vids[
                    "F2A-V2-008"]), ("NEW F2B", vids["F2B-V2-008"])]
    for stream, (label, video) in enumerate(segments):
        inputs += ["-i", str(video)]
        filters.append(
            f"[{stream}:v]trim=start=0:end=2.8,setpts=PTS-STARTPTS,"
            f"fps=24,scale=1280:720,setsar=1,drawtext=fontfile="
            f"'C\\:/Windows/Fonts/arial.ttf':text='{label}':"
            f"fontcolor=white:fontsize=40:box=1:boxcolor=black@0.55:"
            f"boxborderw=12:x=24:y=24[v{stream}]")
        seg_rows.append({"reel_start_s": round(t, 3),
                         "reel_end_s": round(t + 2.8, 3), "label": label,
                         "asset_sha256": file_sha(video)})
        t += 2.8
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
              "F2A_REVISED.mp4": vids["F2A-V2-008"],
              "F2B_WORLD_ANCHORED.mp4": vids["F2B-V2-008"],
              "NEW_F2_PAIR.mp4": pair, "COMPARE_REEL.mp4": REEL}
    copied = {}
    for name, src in copies.items():
        dst = REVIEW_DIR / name
        shutil.copyfile(src, dst)
        assert file_sha(src) == file_sha(dst), name
        copied[name] = {"path": str(dst), "sha256": file_sha(dst)}

    manifest = {"version": "owner-f2-world-anchored-review-manifest-v1",
                "checkpoint": "V2008_P14_OWNER_SURFACE_READY",
                "reel": {"path": str(REEL.relative_to(ROOT)),
                         "sha256": file_sha(REEL),
                         "order": ["BASELINE F2 (2.8s)",
                                   "NEW F2A (2.8s)", "NEW F2B (2.8s)",
                                   "OWNER QUESTIONS"]},
                "segments": seg_rows, "questions": QUESTIONS,
                "review_copies": copied,
                "pair_state": gov["atomic_pair"]["pair_state"]}
    (PKG / "owner_review_manifest_v2_008.json").write_text(
        json.dumps(manifest, indent=1, ensure_ascii=False),
        encoding="utf-8")

    items = []
    for entry in gov["candidates"]:
        review = entry["review"]
        items.append({
            "candidate_id": entry["candidate_id"],
            "select_by_asset_sha256": entry["custody"]["asset_sha256"],
            "state": entry["governed"]["owner_decision_state"],
            "tradeoff_summary": review["findings"] and {
                f["dimension"]: f["verdict"] for f in review["findings"]},
            "spatial_qc": {k: v["verdict"] for k, v in
                           entry["spatial_qc"].items()},
            "camera_qc": entry["camera_qc"]})
    template = {
        "version": "owner-f2-world-anchored-decision-template-v2-008-v1",
        "checkpoint": "V2008_P14_DECISION_SURFACE",
        "atomic_pair_contract": "the pair is ONE editorial solution; no "
                                "half-selection",
        "decision_options": ["SELECT_F2A_F2B_PAIR", "REJECT_ALL",
                             "KEEP_CANONICAL", "NEEDS_REPAIR", "DEFER"],
        "decision": None, "selected_pair": None, "note": "",
        "pair_state": gov["atomic_pair"]["pair_state"],
        "worker_verdicts_are_advisory": True,
        "candidates": items, "review_copies": copied,
        "canonical_predecessor": gov["source_canonical_take"],
        "no_promotion_in_this_package": True}
    (PKG / "owner_f2_pair_decision_v2_008.template.json").write_text(
        json.dumps(template, indent=1, ensure_ascii=False),
        encoding="utf-8")
    print(json.dumps({"checkpoint": "V2008_P14_OWNER_SURFACE_READY",
                      "reel_sha256": file_sha(REEL)[:16],
                      "copies": {k: v["sha256"][:12]
                                 for k, v in copied.items()}}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
