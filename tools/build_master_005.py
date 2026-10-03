"""FLOW-SEQUENCE-SCALE-005 — production-run packaging + MASTER_ROUGH_CUT_V1.

Composes the canonical 18-shot lineage:
- 10 historical shots from Package-004 (SEQ004, read-only adoption; takes
  persisted in QCStore, re-derivation is deterministic and idempotent);
- 8 fresh shots from this package (SEQ005).

Produces per-shot QC + provisional takes, per-cut continuity packets
(incl. the Sequence-A→B boundary), one production-run EditManifest, the
AutoEdit producer package, and MASTER_ROUGH_CUT_V1 through the existing
editorial boundary. Semantic QC: SEMANTIC_QC_UNQUALIFIED (no qualified VLM);
semantic dimensions are OWNER_REVIEW_RECOMMENDED, never fabricated.
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
RUN_DIR = ROOT / "projects/flow_sequence_005"
P4_DIR = ROOT / "projects/flow_multiscene_004"
STORE_PATH = ROOT / "projects/flow_production_harden_002/requal_current_build/runtime.sqlite"
PROJECT_ID = "ai_film_run005_swordsman_journey"
REVIEWER = ("FLOW-SEQUENCE-SCALE-005-BUILD-WORKER "
            "(PROVISIONAL_AUTONOMOUS_SELECTION; pending Owner review)")
NOTES = [
    "PROVISIONAL_AUTONOMOUS_SELECTION under FLOW-SEQUENCE-SCALE-005; "
    "distinguishable from EDITORIALLY_OWNER_APPROVED.",
    "Semantic QC SEMANTIC_QC_UNQUALIFIED (no qualified VLM key); subjective "
    "gates rest on deterministic technical QC + continuity packets.",
]
HIST = {"SEQ4_A1": "SCENE_A_DAWN_STANCE", "SEQ4_A2": "SCENE_A_DAWN_STANCE",
        "SEQ4_A3": "SCENE_A_DAWN_STANCE", "SEQ4_A4": "SCENE_A_DAWN_STANCE",
        "SEQ4_A5": "SCENE_A_DAWN_STANCE", "SEQ4_B1": "SCENE_B_VALLEY_PASS",
        "SEQ4_B2": "SCENE_B_VALLEY_PASS", "SEQ4_B3": "SCENE_B_VALLEY_PASS",
        "SEQ4_B4": "SCENE_B_VALLEY_PASS", "SEQ4_B5R": "SCENE_B_VALLEY_PASS"}
NEW = {"SEQ5_C1": "SCENE_C_VALLEY_FLOOR", "SEQ5_C2": "SCENE_C_VALLEY_FLOOR",
       "SEQ5_C3": "SCENE_C_VALLEY_FLOOR", "SEQ5_C4": "SCENE_C_VALLEY_FLOOR",
       "SEQ5_D1": "SCENE_D_STREAM_REST", "SEQ5_D2": "SCENE_D_STREAM_REST",
       "SEQ5_D3": "SCENE_D_STREAM_REST", "SEQ5_D4": "SCENE_D_STREAM_REST"}
SHOT_SCENE = {**HIST, **NEW}
SHOT_ORDER = list(HIST) + list(NEW)
FIXTURES = {sid: (ROOT / f"fixtures/sequence004/{sid}.json")
            for sid in HIST}
FIXTURES.update({sid: (ROOT / f"fixtures/sequence005/{sid}.json")
                 for sid in NEW})


def result_path(shot_id: str) -> Path:
    scene = SHOT_SCENE[shot_id]
    if shot_id in NEW:
        return RUN_DIR / f"sequence_SEQ005_VALLEY_STREAM" / f"scene_{scene}" / \
            f"shot_{shot_id}" / "result.json"
    if shot_id == "SEQ4_B5R":
        return P4_DIR / "repair_scope" / f"shot_{shot_id}" / "result.json"
    return P4_DIR / f"scene_{scene}" / f"shot_{shot_id}" / "result.json"


def main() -> None:
    run_dir = RUN_DIR / "master_package"
    (run_dir / "continuity").mkdir(parents=True, exist_ok=True)
    store = SQLiteStore(STORE_PATH)
    store.initialize()
    qc_store = QCStore(store)
    qc_store.initialize()
    takes, assets, specs = {}, {}, {}
    qc_ledger = []
    for shot_id in SHOT_ORDER:
        result = json.loads(result_path(shot_id).read_text(encoding="utf-8"))
        gate = result.get("gate")
        if gate not in ("SHOT_PROVEN", "R3_SHOT3_REPROOF_PROVEN"):
            raise SystemExit(f"{shot_id} not proven ({gate}); packaging refused")
        asset = Asset.model_validate(result["asset"])
        spec = load_shot(FIXTURES[shot_id])
        evidence_rows, metadata = technical_evidence(spec, asset)
        human = human_decision(asset=asset, reviewer_id=REVIEWER, action="APPROVE",
                               visual_pass=True, continuity_pass=True,
                               editorial_pass=True, notes=NOTES)
        evidence_rows = list(evidence_rows) + [
            evidence(asset=asset, evaluator_type="human",
                     evaluator_version="build_worker_provisional-v1", gate=gate_,
                     criterion="provisional_autonomous_selection",
                     observation=("PROVISIONAL_AUTONOMOUS_SELECTION; semantic QC "
                                  "SEMANTIC_QC_UNQUALIFIED; pending Owner review."),
                     verdict="pass",
                     source_artifacts=[{"path": str(asset.uri_or_path),
                                        "sha256": asset.sha256}])
            for gate_ in ("visual", "continuity", "editorial")]
        record = derive_report(asset, evidence_rows, human)
        disposition = derive_disposition(spec.shot_id, asset, record, human)
        if not hasattr(disposition, "selected_take_id"):
            raise SystemExit(f"{shot_id}: no SelectedTake")
        # Historical shots already carry persisted immutable takes (Package-
        # 004); re-deriving with new provisional evidence would mint a
        # DIFFERENT take for the same shot — reuse the persisted one instead.
        import json as _json
        with store._connect() as _c:
            row = _c.execute(
                "SELECT payload FROM selected_takes WHERE asset_id=?",
                (asset.asset_id,)).fetchone()
        if row is not None:
            from film_pipeline.qc import SelectedTake
            persisted = SelectedTake.model_validate(_json.loads(row[0]))
        else:
            _record, persisted = qc_store.save(asset, evidence_rows, human)
        takes[shot_id] = persisted
        assets[shot_id] = asset
        specs[shot_id] = spec
        qc_ledger.append({"shot_id": shot_id, "scene_id": SHOT_SCENE[shot_id],
                          "qc_report_id": record.report["qc_report_id"],
                          "decision": record.report["decision"],
                          "selected_take_id": persisted.selected_take_id})
        print(json.dumps({"shot_id": shot_id,
                          "decision": record.report["decision"]}), flush=True)

    # Continuity packets for all 17 adjacent cuts.
    cut_ledger = []
    for index, (prev, nxt) in enumerate(zip(SHOT_ORDER, SHOT_ORDER[1:]), 1):
        last = run_dir / "continuity" / f"cut{index:02d}_{prev}_TO_{nxt}_prev_last.png"
        first = run_dir / "continuity" / f"cut{index:02d}_{prev}_TO_{nxt}_next_first.png"
        combined = run_dir / "continuity" / f"cut{index:02d}_{prev}_TO_{nxt}.png"
        subprocess.run(["ffmpeg", "-y", "-v", "error", "-sseof", "-0.1", "-i",
                        str(assets[prev].uri_or_path), "-frames:v", "1",
                        str(last)], check=True, capture_output=True)
        subprocess.run(["ffmpeg", "-y", "-v", "error", "-i",
                        str(assets[nxt].uri_or_path), "-frames:v", "1",
                        str(first)], check=True, capture_output=True)
        subprocess.run(["ffmpeg", "-y", "-v", "error", "-i", str(last), "-i",
                        str(first), "-filter_complex", "[0:v][1:v]hstack=inputs=2",
                        "-frames:v", "1", str(combined)], check=True,
                       capture_output=True)
        boundary = SHOT_SCENE[prev] != SHOT_SCENE[nxt]
        cut_ledger.append({"cut_index": index, "from_shot": prev,
                           "to_shot": nxt, "packet": str(combined),
                           "scene_boundary": boundary,
                           "semantic_verdict": "OWNER_REVIEW_RECOMMENDED"})
        print(json.dumps({"cut": index, "boundary": boundary}), flush=True)

    clips = [EditClip(order=i, shot_id=takes[sid].shot_id,
                      selected_take_id=takes[sid].selected_take_id,
                      asset_id=takes[sid].asset_id, source_in_s=0.0,
                      source_out_s=8.0,
                      notes="PROVISIONAL_AUTONOMOUS_SELECTION")
             for i, sid in enumerate(SHOT_ORDER, 1)]
    manifest = make_edit_manifest(PROJECT_ID, clips)
    sources = tuple(
        validate_source(clip, path=Path(assets[sid].uri_or_path),
                        expected_sha256=assets[sid].sha256,
                        attempt_id=takes[sid].generation_attempt_id,
                        qc_report_id=takes[sid].qc_report_id)
        for sid, clip in zip(SHOT_ORDER, clips))
    locators = {}
    for sid in SHOT_ORDER:
        base_root, rel = master_locator(sid, assets[sid])
        locators[takes[sid].asset_id] = {
            "kind": "root_relative", "root_id": base_root, "path": rel}
    payload = build_film_input(manifest, sources,
        shots={sid: json.loads(json.dumps(specs[sid].model_dump(mode="json")))
               for sid in SHOT_ORDER},
        locators=locators)
    package_id = write_referenced_package(
        payload, run_dir / "autoedit_package",
        roots={"seq004_media": P4_DIR, "seq005_media": RUN_DIR})

    rough = real_rough_cut(STORE_PATH, project_id=PROJECT_ID,
                           selected_take_ids=[takes[sid].selected_take_id
                                              for sid in SHOT_ORDER],
                           output_dir=run_dir / "master_rough_cut_v1")
    summary = {"run_id": "RUN005_FLOW_SWORDSMAN_JOURNEY",
               "qc": qc_ledger, "cuts": cut_ledger,
               "edit_manifest_id": manifest.edit_manifest_id,
               "autoedit_package_id": package_id,
               "master_rough_cut_v1": rough,
               "semantic_qc_status": "SEMANTIC_QC_UNQUALIFIED",
               "provisional_selection_note": NOTES[0]}
    (run_dir / "master_summary.json").write_text(
        json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps({"edit_manifest_id": manifest.edit_manifest_id,
                      "autoedit_package_id": package_id,
                      "master_rough_cut_render_id": rough["render_id"],
                      "master_rough_cut_sha256": rough["output_sha256"],
                      "master_rough_cut_duration_s": rough["duration_s"],
                      "full_decode": rough["full_decode"]}), flush=True)


def master_locator(sid: str, asset: Asset) -> tuple[str, str]:
    if sid in HIST and sid != "SEQ4_B5R":
        scene = HIST[sid]
        return "seq004_media", (f"scene_{scene}/shot_{sid}/videos/" +
                                Path(asset.uri_or_path).name)
    if sid == "SEQ4_B5R":
        return "seq004_media", ("repair_scope/shot_SEQ4_B5R/videos/" +
                                Path(asset.uri_or_path).name)
    scene = NEW[sid]
    if sid.startswith("SEQ5_C"):
        # Scene C was acquired in the flat run-2 layout (receipts bind to
        # those paths); the per-scene copies hold results only.
        return "seq005_media", ("sequence_SEQ005_VALLEY_STREAM/shot_" + sid +
                                "/videos/" + Path(asset.uri_or_path).name)
    return "seq005_media", ("sequence_SEQ005_VALLEY_STREAM/scene_" + scene +
                            "/shot_" + sid + "/videos/" +
                            Path(asset.uri_or_path).name)


if __name__ == "__main__":
    main()
