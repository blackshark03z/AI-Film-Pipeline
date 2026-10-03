"""FLOW-PRODUCTION-SCALE-007 (L6-L10) — canonical 30-slot assembly.

Stages (one deterministic pass, all offline):
1. Canonical slot ledger: 18 historical adopted slots (SEQ004 10 + SEQ005 8)
   + 12 live SEQ007 slots (slot SEQ7_E2 ← repair take SEQ7_E2R, slot
   SEQ7_G3 ← repair take SEQ7_G3B under durable RepairDecisions).
2. QC + provisional takes: historical slots reuse their persisted immutable
   takes; the 12 live slots derive technical QC evidence + provisional
   human decision (PROVISIONAL_AUTONOMOUS_SELECTION) and persist takes.
3. Editorial ranges (L6): historical slots keep the full clip (no qualified
   trim); live slots place the FROZEN editorial_target_duration inside the
   technically usable window (black/freeze scans) — never tuned after
   seeing clips. Every worker range: PROVISIONAL_AUTONOMOUS_EDITORIAL_RANGE.
4. EditorialPlan (L9): transitions (deterministic rules) + scene/sequence
   pacing metrics + anomaly flags.
5. EditManifest with per-slot source ranges + AutoEdit producer package
   (existing boundary; no AutoEdit redesign).
6. MASTER_SCALE_V1 (L10): trim-aware render through render_sources, with
   persisted receipt, output SHA-256, duration, codecs, full-decode EOF.

No Gemini calls. Semantic dimensions: OWNER_REVIEW_RECOMMENDED.
"""
from __future__ import annotations

import json
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

sys_path = str(Path(__file__).resolve().parents[1] / "src")
if sys_path not in sys.path:
    sys.path.insert(0, sys_path)

from film_pipeline.autoedit_export import build_film_input, write_referenced_package
from film_pipeline.core import load_shot, sha256
from film_pipeline.editorial import (
    EditClip,
    EditorialStore,
    make_edit_manifest,
    probe_media,
    validate_source,
)
from film_pipeline.editorial_range import (
    ProbeBasis,
    make_editorial_range,
    revalidate,
    write_range,
)
from film_pipeline.live_runtime import Asset as AssetModel
from film_pipeline.rough_cut import persist_render, render_sources
from film_pipeline.qc import (
    QCStore,
    SelectedTake,
    derive_disposition,
    derive_report,
    evidence,
    human_decision,
    technical_evidence,
)
from film_pipeline.store import SQLiteStore

ROOT = Path(__file__).resolve().parents[1]
RUN_DIR = ROOT / "projects/flow_production_scale_007"
OUT_DIR = RUN_DIR / "master_package_007"
STORE_PATH = ROOT / "projects/flow_production_harden_002/requal_current_build/runtime.sqlite"
P4 = ROOT / "projects/flow_multiscene_004"
P5_SEQ = ROOT / "projects/flow_sequence_005/sequence_SEQ005_VALLEY_STREAM"
P7_SEQ = RUN_DIR / "sequence_SEQ007_DAYLIGHT_ROAD"
PROJECT_ID = "ai_film_run007_swordsman_scale"
REVIEWER = ("FLOW-PRODUCTION-SCALE-007-BUILD-WORKER "
            "(PROVISIONAL_AUTONOMOUS_SELECTION; pending Owner review)")
NOTES = [
    "PROVISIONAL_AUTONOMOUS_SELECTION under FLOW-PRODUCTION-SCALE-007; "
    "distinguishable from EDITORIALLY_OWNER_APPROVED.",
    "Semantic QC SEMANTIC_QC_UNQUALIFIED (no qualified VLM; no Gemini calls "
    "in this package); subjective gates rest on deterministic technical QC "
    "+ continuity packets.",
]

PLAN_C = json.loads((ROOT / "fixtures/sequence007/sequence_plan_007.json")
                    .read_text(encoding="utf-8"))
TARGETS = {s["shot_id"]: s.get("editorial_target_duration")
           for scene in PLAN_C["scenes"] for s in scene["shots"]}
SEQ7_SCENE_OF = {s["shot_id"]: sc["scene_id"] for sc in PLAN_C["scenes"]
                 for s in sc["shots"]}

SEQ4_SLOTS = ["SEQ4_A1", "SEQ4_A2", "SEQ4_A3", "SEQ4_A4", "SEQ4_A5",
              "SEQ4_B1", "SEQ4_B2", "SEQ4_B3", "SEQ4_B4", "SEQ4_B5R"]
SEQ5_SLOTS = ["SEQ5_C1", "SEQ5_C2", "SEQ5_C3", "SEQ5_C4",
              "SEQ5_D1", "SEQ5_D2", "SEQ5_D3", "SEQ5_D4"]
SEQ7_SLOTS = ["SEQ7_E1", "SEQ7_E2", "SEQ7_E3", "SEQ7_E4",
              "SEQ7_F1", "SEQ7_F2", "SEQ7_F3", "SEQ7_F4",
              "SEQ7_G1", "SEQ7_G2", "SEQ7_G3", "SEQ7_G4"]
SEQ7_REPAIR_FOR = {"SEQ7_E2": "SEQ7_E2R", "SEQ7_G3": "SEQ7_G3B"}
CANONICAL_ORDER = SEQ4_SLOTS + SEQ5_SLOTS + SEQ7_SLOTS
SEQ_OF = {**{s: "SEQ004_SWORDSMAN_DESCENT" for s in SEQ4_SLOTS},
          **{s: "SEQ005_VALLEY_STREAM" for s in SEQ5_SLOTS},
          **{s: "SEQ007_DAYLIGHT_ROAD" for s in SEQ7_SLOTS}}
SCENE_OF = {
    "SEQ4_A1": "SCENE_A_DAWN_STANCE", "SEQ4_A2": "SCENE_A_DAWN_STANCE",
    "SEQ4_A3": "SCENE_A_DAWN_STANCE", "SEQ4_A4": "SCENE_A_DAWN_STANCE",
    "SEQ4_A5": "SCENE_A_DAWN_STANCE", "SEQ4_B1": "SCENE_B_VALLEY_PASS",
    "SEQ4_B2": "SCENE_B_VALLEY_PASS", "SEQ4_B3": "SCENE_B_VALLEY_PASS",
    "SEQ4_B4": "SCENE_B_VALLEY_PASS", "SEQ4_B5R": "SCENE_B_VALLEY_PASS",
    "SEQ5_C1": "SCENE_C_VALLEY_FLOOR", "SEQ5_C2": "SCENE_C_VALLEY_FLOOR",
    "SEQ5_C3": "SCENE_C_VALLEY_FLOOR", "SEQ5_C4": "SCENE_C_VALLEY_FLOOR",
    "SEQ5_D1": "SCENE_D_STREAM_REST", "SEQ5_D2": "SCENE_D_STREAM_REST",
    "SEQ5_D3": "SCENE_D_STREAM_REST", "SEQ5_D4": "SCENE_D_STREAM_REST",
}


def result_path(slot: str) -> Path:
    if slot in SEQ4_SLOTS:
        if slot == "SEQ4_B5R":
            return P4 / "repair_scope" / f"shot_{slot}" / "result.json"
        scene = "SCENE_A_DAWN_STANCE" if slot.startswith("SEQ4_A") \
            else "SCENE_B_VALLEY_PASS"
        return P4 / f"scene_{scene}" / f"shot_{slot}" / "result.json"
    if slot in SEQ5_SLOTS:
        scene = "SCENE_C_VALLEY_FLOOR" if slot.startswith("SEQ5_C") \
            else "SCENE_D_STREAM_REST"
        return P5_SEQ / f"scene_{scene}" / f"shot_{slot}" / "result.json"
    if slot in SEQ7_REPAIR_FOR:
        repair_id = SEQ7_REPAIR_FOR[slot]
        return RUN_DIR / "repair_scope" / f"repair_{repair_id}" / \
            f"shot_{repair_id}" / "result.json"
    return P7_SEQ / f"scene_{SEQ7_SCENE_OF[slot]}" / f"shot_{slot}" / \
        "result.json"


def spec_path(slot: str) -> Path:
    canonical = SEQ7_REPAIR_FOR.get(slot, slot)
    if canonical.startswith("SEQ4_"):
        return ROOT / f"fixtures/sequence004/{canonical}.json"
    if canonical.startswith("SEQ5_"):
        return ROOT / f"fixtures/sequence005/{canonical}.json"
    return ROOT / f"fixtures/sequence007/{canonical}.json"


def scene_of(slot: str) -> str:
    return SCENE_OF.get(slot) or SEQ7_SCENE_OF[slot]


def anomaly_scan(path: Path) -> dict:
    black = subprocess.run(
        ["ffmpeg", "-v", "info", "-i", str(path), "-vf",
         "blackdetect=d=0.1:pix_th=0.10", "-an", "-f", "null", "-"],
        capture_output=True, text=True, timeout=120, check=False)
    black_ranges = re.findall(
        r"black_start:([\d.]+)\s+black_end:([\d.]+)", black.stderr)
    freeze = subprocess.run(
        ["ffmpeg", "-v", "info", "-i", str(path), "-vf",
         "freezedetect=n=0.003:d=0.5", "-an", "-f", "null", "-"],
        capture_output=True, text=True, timeout=120, check=False)
    freeze_ranges = re.findall(
        r"freeze_start:([\d.]+)\s+freeze_duration:([\d.]+)", freeze.stderr)
    return {"black_ranges_s": [[float(a), float(b)] for a, b in black_ranges],
            "freeze_ranges_s": [[float(a), float(a) + float(b)]
                                for a, b in freeze_ranges]}


def usable_window(duration: float, scan: dict) -> tuple[float, float]:
    start, end = 0.0, duration
    for b0, b1 in scan["black_ranges_s"] + scan["freeze_ranges_s"]:
        if b0 <= 0.05 and b1 > start:
            start = b1
        if b1 >= duration - 0.05 and b0 < end:
            end = b0
    return start, end


def main() -> None:
    (OUT_DIR / "ranges").mkdir(parents=True, exist_ok=True)
    (OUT_DIR / "continuity").mkdir(parents=True, exist_ok=True)
    now = datetime.now(timezone.utc).isoformat()
    store = SQLiteStore(STORE_PATH)
    store.initialize()
    qc_store = QCStore(store)
    qc_store.initialize()

    # ---- stage 1+2: canonical ledger, QC, provisional takes --------------
    slots, takes, assets, specs = [], {}, {}, {}
    for order, slot in enumerate(CANONICAL_ORDER, 1):
        result = json.loads(result_path(slot).read_text(encoding="utf-8"))
        if result.get("gate") not in ("SHOT_PROVEN",
                                      "R3_SHOT3_REPROOF_PROVEN"):
            raise SystemExit(f"{slot}: not proven")
        asset = json.loads(json.dumps(result["asset"]))
        asset_path = Path(asset["uri_or_path"])
        spec = load_shot(spec_path(slot))
        with store._connect() as conn:
            row = conn.execute(
                "SELECT payload FROM selected_takes WHERE asset_id=?",
                (asset["asset_id"],)).fetchone()
        if row is not None:
            persisted = SelectedTake.model_validate(json.loads(row[0]))
        else:
            asset_model = AssetModel.model_validate(asset)
            evidence_rows, _metadata = technical_evidence(spec, asset_model)
            human = human_decision(asset=asset_model, reviewer_id=REVIEWER,
                                   action="APPROVE", visual_pass=True,
                                   continuity_pass=True, editorial_pass=True,
                                   notes=NOTES)
            evidence_rows = list(evidence_rows) + [
                evidence(asset=asset_model, evaluator_type="human",
                         evaluator_version="build_worker_provisional-v1",
                         gate=gate_,
                         criterion="provisional_autonomous_selection",
                         observation=("PROVISIONAL_AUTONOMOUS_SELECTION; "
                                      "semantic QC SEMANTIC_QC_UNQUALIFIED; "
                                      "pending Owner review."),
                         verdict="pass",
                         source_artifacts=[{"path": str(asset_path),
                                            "sha256": asset["sha256"]}])
                for gate_ in ("visual", "continuity", "editorial")]
            record = derive_report(asset_model, evidence_rows, human)
            disposition = derive_disposition(spec.shot_id, asset_model,
                                             record, human)
            if not hasattr(disposition, "selected_take_id"):
                raise SystemExit(f"{slot}: no SelectedTake")
            _record, persisted = qc_store.save(asset_model, evidence_rows,
                                               human)
        takes[slot] = persisted
        assets[slot] = asset
        specs[slot] = spec
        slots.append({"order": order, "slot_id": slot,
                      "canonical_shot_id": slot,
                      "take_shot_id": persisted.shot_id,
                      "sequence": SEQ_OF[slot], "scene": scene_of(slot),
                      "provenance": (
                          "repair_successor" if slot in SEQ7_REPAIR_FOR
                          else "direct_live" if slot in SEQ7_SLOTS
                          else "historical_adopted"),
                      "selected_take_id": persisted.selected_take_id,
                      "asset_id": asset["asset_id"],
                      "asset_sha256": asset["sha256"],
                      "asset_path": str(asset_path),
                      "provider_media_id": result.get("output_identity")})
        print(json.dumps({"slot": slot, "take": persisted.selected_take_id}),
              flush=True)

    # ---- stage 3: editorial ranges (L6) ----------------------------------
    ranges = {}
    for slot in CANONICAL_ORDER:
        asset_path = Path(assets[slot]["uri_or_path"])
        media = probe_media(asset_path)
        duration = media.duration_s
        is_live = slot in SEQ7_SLOTS
        if is_live:
            scan = anomaly_scan(asset_path)
            win_start, _win_end = usable_window(duration, scan)
            target = TARGETS[slot]
            source_in = round(min(win_start, max(0.0, duration - target)), 3)
            source_out = round(min(source_in + target, duration), 3)
            basis = (f"frozen editorial_target_duration {target}s; usable "
                     f"window from {win_start:.3f}s")
        else:
            source_in, source_out = 0.0, round(duration, 3)
            basis = "historical full-clip selection (no qualified trim)"
        rng = make_editorial_range(
            selected_take_id=takes[slot].selected_take_id,
            shot_id=takes[slot].shot_id,
            asset_id=assets[slot]["asset_id"],
            asset_sha256=assets[slot]["sha256"],
            source_in_s=source_in, source_out_s=source_out,
            probe=ProbeBasis(duration_s=duration, fps_num=media.fps_num,
                             fps_den=media.fps_den),
            note=f"{basis}; PROVISIONAL_AUTONOMOUS_EDITORIAL_RANGE")
        revalidate(rng, asset_path)
        write_range(rng, OUT_DIR / "ranges" /
                    f"{CANONICAL_ORDER.index(slot) + 1:02d}_{slot}.json")
        ranges[slot] = rng
        print(json.dumps({"slot": slot,
                          "range": [source_in, source_out]}), flush=True)

    # ---- stage 4: EditorialPlan (L9) --------------------------------------
    transitions = []
    for cut_index, (prev, nxt) in enumerate(
            zip(CANONICAL_ORDER, CANONICAL_ORDER[1:]), 1):
        if SEQ_OF[prev] != SEQ_OF[nxt]:
            kind = "HARD_SCENE_BREAK"  # sequence boundary
        elif scene_of(prev) != scene_of(nxt):
            kind = "HARD_SCENE_BREAK"
        elif nxt in ("SEQ7_F2", "SEQ7_G2"):
            kind = "MATCH_CUT"  # frozen last-frame conditioned slots
        else:
            kind = "CUT"
        transitions.append({
            "cut_index": cut_index, "from_slot": prev, "to_slot": nxt,
            "kind": kind,
            "boundary": scene_of(prev) != scene_of(nxt) or
                        SEQ_OF[prev] != SEQ_OF[nxt],
            "semantic_verdict": "OWNER_REVIEW_RECOMMENDED"})
    plan_metrics = {"scenes": {}, "sequences": {}}
    for key, group_field in (("scenes", "scene"), ("sequences", "sequence")):
        groups = {}
        for slot in CANONICAL_ORDER:
            groups.setdefault(
                (SEQ_OF[slot], scene_of(slot)) if group_field == "scene"
                else (SEQ_OF[slot],), []).append(slot)
        for gkey, members in groups.items():
            durations = [ranges[s].selected_duration_s for s in members]
            plan_metrics[key]["/".join(gkey)] = {
                "shot_count": len(members),
                "duration_s": round(sum(durations), 3),
                "avg_shot_s": round(sum(durations) / len(durations), 3),
                "min_shot_s": round(min(durations), 3),
                "max_shot_s": round(max(durations), 3)}
    anomalies = []
    for slot in CANONICAL_ORDER:
        d = ranges[slot].selected_duration_s
        if d < 1.0:
            anomalies.append({"slot": slot, "kind": "near_zero_range", "d": d})
    for key, metrics in plan_metrics["scenes"].items():
        seq, scene = key.split("/")
        for slot in CANONICAL_ORDER:
            if SEQ_OF[slot] == seq and scene_of(slot) == scene:
                d = ranges[slot].selected_duration_s
                if d > 2 * metrics["avg_shot_s"]:
                    anomalies.append({"slot": slot,
                                      "kind": "duration_outlier", "d": d})
    editorial_plan = {
        "version": "editorial-plan-007-v1",
        "generated_at": now,
        "slot_order": CANONICAL_ORDER,
        "transitions": transitions,
        "transition_classes_present": sorted({t["kind"]
                                              for t in transitions}),
        "dissolve_candidates": 0,
        "pacing": plan_metrics,
        "anomalies": anomalies,
        "provisional_label": "PROVISIONAL_AUTONOMOUS_EDITORIAL_PLAN",
    }
    (OUT_DIR / "editorial_plan_007.json").write_text(
        json.dumps(editorial_plan, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8")

    # ---- continuity packets for all 29 cuts -------------------------------
    cut_ledger = []
    for t in transitions:
        i, prev, nxt = t["cut_index"], t["from_slot"], t["to_slot"]
        last = OUT_DIR / "continuity" / f"cut{i:02d}_{prev}_TO_{nxt}_prev_last.png"
        first = OUT_DIR / "continuity" / f"cut{i:02d}_{prev}_TO_{nxt}_next_first.png"
        combined = OUT_DIR / "continuity" / f"cut{i:02d}_{prev}_TO_{nxt}.png"
        subprocess.run(["ffmpeg", "-y", "-v", "error", "-sseof", "-0.1",
                        "-i", assets[prev]["uri_or_path"], "-frames:v", "1",
                        str(last)], check=True, capture_output=True)
        subprocess.run(["ffmpeg", "-y", "-v", "error", "-i",
                        assets[nxt]["uri_or_path"], "-frames:v", "1",
                        str(first)], check=True, capture_output=True)
        subprocess.run(["ffmpeg", "-y", "-v", "error", "-i", str(last),
                        "-i", str(first), "-filter_complex",
                        "[0:v][1:v]hstack=inputs=2", "-frames:v", "1",
                        str(combined)], check=True, capture_output=True)
        cut_ledger.append({**t, "packet": str(combined)})

    # ---- stage 5: EditManifest + producer package -------------------------
    clips = []
    for order, slot in enumerate(CANONICAL_ORDER, 1):
        rng = ranges[slot]
        clips.append(EditClip(
            order=order, shot_id=takes[slot].shot_id,
            selected_take_id=takes[slot].selected_take_id,
            asset_id=takes[slot].asset_id,
            source_in_s=rng.source_in_s, source_out_s=rng.source_out_s,
            target_duration_s=rng.selected_duration_s,
            notes=("PROVISIONAL_AUTONOMOUS_SELECTION; "
                   + ("repair successor for " + slot
                      if slot in SEQ7_REPAIR_FOR else "direct slot"))))
    manifest = make_edit_manifest(PROJECT_ID, clips)
    sources = tuple(
        validate_source(clip, path=Path(assets[slot]["uri_or_path"]),
                        expected_sha256=assets[slot]["sha256"],
                        attempt_id=takes[slot].generation_attempt_id,
                        qc_report_id=takes[slot].qc_report_id)
        for slot, clip in zip(CANONICAL_ORDER, clips))
    editorial = EditorialStore(store)
    editorial.initialize()
    editorial.save_manifest(manifest)
    locators = {}
    for slot in CANONICAL_ORDER:
        rel = Path(assets[slot]["uri_or_path"])
        for root_id, base in (("seq004_media", P4),
                              ("seq005_media", P5_SEQ.parent),
                              ("seq007_media", RUN_DIR)):
            try:
                locators[assets[slot]["asset_id"]] = {
                    "kind": "root_relative", "root_id": root_id,
                    "path": rel.relative_to(base).as_posix()}
                break
            except ValueError:
                continue
        if assets[slot]["asset_id"] not in locators:
            raise SystemExit(f"{slot}: no locator root for {rel}")
    payload = build_film_input(
        manifest, sources,
        shots={takes[s].shot_id:
               json.loads(json.dumps(specs[s].model_dump(mode="json")))
               for s in CANONICAL_ORDER},
        locators=locators)
    package_id = write_referenced_package(
        payload, OUT_DIR / "autoedit_package",
        roots={"seq004_media": P4, "seq005_media": P5_SEQ.parent,
               "seq007_media": RUN_DIR})

    # ---- stage 6: MASTER_SCALE_V1 (trim-aware render) ---------------------
    output = OUT_DIR / "master_scale_v1.mp4"
    record = render_sources(manifest, sources, output)
    persist_render(editorial, record)
    summary = {
        "version": "master-scale-v1",
        "generated_at": now,
        "edit_manifest_id": manifest.edit_manifest_id,
        "autoedit_package_id": package_id,
        "render_id": record.render_id,
        "output_path": record.output_path,
        "output_sha256": record.output_sha256,
        "duration_s": record.duration_s,
        "width": record.width, "height": record.height,
        "video_codec": record.video_codec, "audio_codec": record.audio_codec,
        "source_count": len(sources),
        "source_intervals": [[s.source_in_s, s.source_out_s]
                             for s in sources],
        "expected_timeline_s": round(sum(
            rng.selected_duration_s for rng in
            (ranges[s] for s in CANONICAL_ORDER)), 3),
        "full_decode": record.full_decode,
        "render_method": record.render_method,
        "slots": slots,
        "cuts": cut_ledger,
        "editorial_plan": "editorial_plan_007.json",
        "timing_ranges": "ranges/",
        "semantic_qc_status": "SEMANTIC_QC_UNQUALIFIED",
    }
    (OUT_DIR / "master_summary.json").write_text(
        json.dumps(summary, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8")
    print(json.dumps({"manifest": manifest.edit_manifest_id,
                      "package": package_id, "render": record.render_id,
                      "sha256": record.output_sha256,
                      "duration_s": record.duration_s,
                      "expected_s": summary["expected_timeline_s"],
                      "full_decode": record.full_decode}), flush=True)


if __name__ == "__main__":
    main()
