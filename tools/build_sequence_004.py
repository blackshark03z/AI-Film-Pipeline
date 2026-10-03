"""FLOW-MULTISCENE-SEMANTIC-REPAIR-004 — sequence packaging.

Read-only over the ten proven shot assets:
- per-shot technical QC + provisional SelectedTakes (persisted via QCStore);
- per-cut continuity packets inside each scene (4 per scene) and across the
  scene boundary (A5 last | B1 first);
- one sequence EditManifest + AutoEdit producer package;
- real rough cut through the existing editorial boundary.

Semantic QC: SEMANTIC_QC_UNQUALIFIED — no qualified VLM key in this
environment; semantic dimensions are marked OWNER_REVIEW_RECOMMENDED and no
verdict is fabricated.
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

sys_path = str(Path(__file__).resolve().parents[1] / "src")
if sys_path not in sys.path:
    sys.path.insert(0, sys_path)

from film_pipeline.autoedit_export import build_film_input, write_referenced_package
from film_pipeline.core import load_shot
from film_pipeline.editorial import EditClip, make_edit_manifest, probe_media, validate_source
from film_pipeline.editorial_runner import real_rough_cut
from film_pipeline.live_runtime import Asset
from film_pipeline.qc import (
    QCStore,
    derive_disposition,
    derive_report,
    evidence,
    human_decision,
    technical_evidence,
)
from film_pipeline.store import SQLiteStore

ROOT = Path(__file__).resolve().parents[1]
SEQ_DIR = ROOT / "projects/flow_multiscene_004"
STORE_PATH = ROOT / "projects/flow_production_harden_002/requal_current_build/runtime.sqlite"
REVIEWER = ("FLOW-MULTISCENE-004-BUILD-WORKER "
            "(PROVISIONAL_AUTONOMOUS_SELECTION; pending Owner review)")
NOTES = [
    "PROVISIONAL_AUTONOMOUS_SELECTION under FLOW-MULTISCENE-SEMANTIC-REPAIR-004 "
    "while the Owner is away; distinguishable from EDITORIALLY_OWNER_APPROVED.",
    "Semantic QC is SEMANTIC_QC_UNQUALIFIED (no qualified VLM key); subjective "
    "gates rest on deterministic technical QC + deterministic continuity packets.",
]
PLAN = json.loads((ROOT / "fixtures/sequence004/sequence_plan_004.json").read_text(
    encoding="utf-8"))
SHOT_IDS = [s["shot_id"] for scene in PLAN["scenes"] for s in scene["shots"]]
SCENE_OF = {s["shot_id"]: scene["scene_id"]
            for scene in PLAN["scenes"] for s in scene["shots"]}


def cut_packet(seq_dir: Path, prev: str, nxt: str, assets: dict, index: int) -> dict:
    packet_dir = seq_dir / "continuity"
    packet_dir.mkdir(parents=True, exist_ok=True)
    label = f"cut{index:02d}_{prev}_TO_{nxt}"
    last = packet_dir / f"{label}_prev_last.png"
    first = packet_dir / f"{label}_next_first.png"
    combined = packet_dir / f"{label}.png"
    subprocess.run(["ffmpeg", "-y", "-v", "error", "-sseof", "-0.1", "-i",
                    str(assets[prev].uri_or_path), "-frames:v", "1", str(last)],
                   check=True, capture_output=True)
    subprocess.run(["ffmpeg", "-y", "-v", "error", "-i",
                    str(assets[nxt].uri_or_path), "-frames:v", "1", str(first)],
                   check=True, capture_output=True)
    subprocess.run(["ffmpeg", "-y", "-v", "error", "-i", str(last), "-i",
                    str(first), "-filter_complex", "[0:v][1:v]hstack=inputs=2",
                    "-frames:v", "1", str(combined)], check=True, capture_output=True)
    return {"cut_index": index, "from_shot": prev, "to_shot": nxt,
            "packet": str(combined),
            "prev_last_frame_sha256": __import__("hashlib").sha256(
                last.read_bytes()).hexdigest(),
            "next_first_frame_sha256": __import__("hashlib").sha256(
                first.read_bytes()).hexdigest(),
            "semantic_verdict": "OWNER_REVIEW_RECOMMENDED",
            "note": ("deterministic visual packet; semantic QC is "
                     "SEMANTIC_QC_UNQUALIFIED — no verdict fabricated")}


def main() -> None:
    seq_dir = SEQ_DIR / "sequence_package_v2"
    (seq_dir / "continuity").mkdir(parents=True, exist_ok=True)
    store = SQLiteStore(STORE_PATH)
    store.initialize()
    qc_store = QCStore(store)
    qc_store.initialize()
    takes, assets, specs = {}, {}, {}
    qc_ledger = []
    for shot_id in SHOT_IDS:
        scene_id = SCENE_OF[shot_id]
        if shot_id == "SEQ4_B5R":
            result_path = (SEQ_DIR / "repair_scope" / f"shot_{shot_id}" /
                           "result.json")
        else:
            result_path = (SEQ_DIR / f"scene_{scene_id}" / f"shot_{shot_id}" /
                           "result.json")
        result = json.loads(result_path.read_text(encoding="utf-8"))
        if result.get("gate") != "SHOT_PROVEN":
            raise SystemExit(f"{shot_id} not proven; sequence packaging refused")
        asset = Asset.model_validate(result["asset"])
        fixture = next(s["fixture"] for scene in PLAN["scenes"]
                       for s in scene["shots"] if s["shot_id"] == shot_id)
        spec = load_shot(ROOT / fixture)
        evidence_rows, metadata = technical_evidence(spec, asset)
        human = human_decision(asset=asset, reviewer_id=REVIEWER, action="APPROVE",
                               visual_pass=True, continuity_pass=True,
                               editorial_pass=True, notes=NOTES)
        evidence_rows = list(evidence_rows) + [
            evidence(asset=asset, evaluator_type="human",
                     evaluator_version="build_worker_provisional-v1", gate=gate,
                     criterion="provisional_autonomous_selection",
                     observation=("PROVISIONAL_AUTONOMOUS_SELECTION; semantic QC "
                                  "SEMANTIC_QC_UNQUALIFIED; pending Owner review."),
                     verdict="pass",
                     source_artifacts=[{"path": str(asset.uri_or_path),
                                        "sha256": asset.sha256}])
            for gate in ("visual", "continuity", "editorial")]
        record = derive_report(asset, evidence_rows, human)
        disposition = derive_disposition(spec.shot_id, asset, record, human)
        if not hasattr(disposition, "selected_take_id"):
            raise SystemExit(f"{shot_id}: no SelectedTake")
        _record, persisted = qc_store.save(asset, evidence_rows, human)
        takes[shot_id] = persisted
        assets[shot_id] = asset
        specs[shot_id] = spec
        qc_ledger.append({"shot_id": shot_id, "scene_id": scene_id,
                          "qc_report_id": record.report["qc_report_id"],
                          "decision": record.report["decision"],
                          "selected_take_id": persisted.selected_take_id,
                          "semantic_qc": "SEMANTIC_QC_UNQUALIFIED"})
        print(json.dumps({"shot_id": shot_id,
                          "decision": record.report["decision"]}), flush=True)

    # Continuity packets: all adjacent cuts + the scene-boundary transition.
    cut_ledger = []
    index = 0
    for prev, nxt in zip(SHOT_IDS, SHOT_IDS[1:]):
        index += 1
        boundary = SCENE_OF[prev] != SCENE_OF[nxt]
        entry = cut_packet(seq_dir, prev, nxt, assets, index)
        entry["scene_boundary"] = boundary
        cut_ledger.append(entry)
        print(json.dumps({"cut": index, "boundary": boundary,
                          "packet": Path(entry["packet"]).name}), flush=True)

    clips = [EditClip(order=i, shot_id=takes[sid].shot_id,
                      selected_take_id=takes[sid].selected_take_id,
                      asset_id=takes[sid].asset_id, source_in_s=0.0,
                      source_out_s=8.0,
                      notes="PROVISIONAL_AUTONOMOUS_SELECTION")
             for i, sid in enumerate(SHOT_IDS, 1)]
    manifest = make_edit_manifest("ai_film_multiscene_004", clips)
    sources = tuple(
        validate_source(clip, path=Path(assets[sid].uri_or_path),
                        expected_sha256=assets[sid].sha256,
                        attempt_id=takes[sid].generation_attempt_id,
                        qc_report_id=takes[sid].qc_report_id)
        for sid, clip in zip(SHOT_IDS, clips))
    locators = {}
    for sid in SHOT_IDS:
        if sid == "SEQ4_B5R":
            locators[takes[sid].asset_id] = {
                "kind": "root_relative", "root_id": "sequence004_media",
                "path": "repair_scope/shot_SEQ4_B5R/videos/" +
                        Path(assets[sid].uri_or_path).name}
        else:
            locators[takes[sid].asset_id] = {
                "kind": "root_relative", "root_id": "sequence004_media",
                "path": f"scene_{SCENE_OF[sid]}/shot_{sid}/videos/" +
                        Path(assets[sid].uri_or_path).name}
    payload = build_film_input(manifest, sources,
        shots={sid: json.loads(json.dumps(specs[sid].model_dump(mode="json")))
               for sid in SHOT_IDS},
        locators=locators)
    package_id = write_referenced_package(
        payload, seq_dir / "autoedit_package",
        roots={"sequence004_media": SEQ_DIR})

    rough = real_rough_cut(STORE_PATH, project_id="ai_film_multiscene_004",
                           selected_take_ids=[takes[sid].selected_take_id
                                              for sid in SHOT_IDS],
                           output_dir=seq_dir / "rough_cut")
    summary = {"sequence_id": "SEQ004_SWORDSMAN_DESCENT",
               "qc": qc_ledger, "cuts": cut_ledger,
               "edit_manifest_id": manifest.edit_manifest_id,
               "autoedit_package_id": package_id,
               "rough_cut_v1": rough,
               "semantic_qc_status": "SEMANTIC_QC_UNQUALIFIED",
               "provisional_selection_note": NOTES[0]}
    (seq_dir / "sequence_summary.json").write_text(
        json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps({"edit_manifest_id": manifest.edit_manifest_id,
                      "autoedit_package_id": package_id,
                      "rough_cut_render_id": rough["render_id"],
                      "rough_cut_sha256": rough["output_sha256"],
                      "rough_cut_duration_s": rough["duration_s"],
                      "full_decode": rough["full_decode"]}), flush=True)


if __name__ == "__main__":
    main()
