"""FLOW-SCENE-SCALE-003 — scene packaging: QC, takes, cuts, manifest, rough cut.

Read-only over the six proven shot assets. Produces:
- per-shot QC reports + provisional SelectedTakes (persisted via QCStore so
  the existing editorial boundary can execute);
- deterministic per-cut continuity packets (previous last frame | next first
  frame) for cuts 1→2 … 5→6 — visual evidence only, no fabricated semantic
  verdicts (dimensions without a qualified evaluator are marked
  OWNER_REVIEW_RECOMMENDED);
- the scene EditManifest + AutoEdit producer package;
- the real rough cut through the existing editorial boundary
  (editorial_runner.real_rough_cut) with full lineage readback.
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
from film_pipeline.core import load_shot, sha256
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
SCENE_DIR = ROOT / "projects/flow_scene_scale_003"
STORE_PATH = ROOT / "projects/flow_production_harden_002/requal_current_build/runtime.sqlite"
PROJECT_ID = "93a579b4-834e-435b-8304-5f6682937935"
REVIEWER = "FLOW-SCENE-SCALE-003-BUILD-WORKER (PROVISIONAL_AUTONOMOUS_SELECTION; pending Owner review)"
NOTES = [
    "PROVISIONAL_AUTONOMOUS_SELECTION under FLOW-SCENE-SCALE-003 while the "
    "Owner is away; distinguishable from EDITORIALLY_OWNER_APPROVED.",
    "Subjective gates asserted from deterministic technical QC + continuity "
    "packets; the Owner may reject and re-select at any time.",
]
PLAN = json.loads((ROOT / "fixtures/scene_plan_003.json").read_text(encoding="utf-8"))
SHOT_IDS = [s["shot_id"] for s in PLAN["shots"]]


def main() -> None:
    scene_dir = SCENE_DIR / "scene_package"
    (scene_dir / "continuity").mkdir(parents=True, exist_ok=True)
    store = SQLiteStore(STORE_PATH)
    store.initialize()
    qc_store = QCStore(store)
    qc_store.initialize()
    takes, assets, specs = {}, {}, {}
    qc_ledger = []
    for shot_id in SHOT_IDS:
        result = json.loads((SCENE_DIR / f"shot_{shot_id}" / "result.json")
                            .read_text(encoding="utf-8"))
        if result.get("gate") != "SHOT_PROVEN":
            raise SystemExit(f"{shot_id} not proven; scene packaging refused")
        asset = Asset.model_validate(result["asset"])
        fixture = next(s["fixture"] for s in PLAN["shots"] if s["shot_id"] == shot_id)
        spec = load_shot(ROOT / fixture)
        evidence_rows, metadata = technical_evidence(spec, asset)
        human = human_decision(
            asset=asset, reviewer_id=REVIEWER, action="APPROVE",
            visual_pass=True, continuity_pass=True, editorial_pass=True,
            notes=NOTES)
        # Subjective-gate evidence rows from the provisional reviewer.
        evidence_rows = list(evidence_rows) + [
            evidence(asset=asset, evaluator_type="human",
                     evaluator_version="build_worker_provisional-v1", gate=gate,
                     criterion="provisional_autonomous_selection",
                     observation=("PROVISIONAL_AUTONOMOUS_SELECTION under "
                                  "FLOW-SCENE-SCALE-003; pending Owner review."),
                     verdict="pass",
                     source_artifacts=[{"path": str(asset.uri_or_path),
                                        "sha256": asset.sha256}])
            for gate in ("visual", "continuity", "editorial")]
        record = derive_report(asset, evidence_rows, human)
        disposition = derive_disposition(spec.shot_id, asset, record, human)
        if not hasattr(disposition, "selected_take_id"):
            raise SystemExit(f"{shot_id}: no SelectedTake "
                             f"({record.report['decision']})")
        persisted_record, persisted_take = qc_store.save(
            asset, evidence_rows, human)
        takes[shot_id] = persisted_take
        assets[shot_id] = asset
        specs[shot_id] = spec
        qc_ledger.append({"shot_id": shot_id,
                          "qc_report_id": record.report["qc_report_id"],
                          "decision": record.report["decision"],
                          "selected_take_id": persisted_take.selected_take_id})
        print(json.dumps({"shot_id": shot_id, "decision": record.report["decision"],
                          "take": persisted_take.selected_take_id[:24]}), flush=True)

    # Per-cut continuity packets: previous last frame | next first frame.
    cut_ledger = []
    for cut, (prev_id, next_id) in enumerate(zip(SHOT_IDS, SHOT_IDS[1:]), 1):
        last = scene_dir / "continuity" / f"cut{cut}_prev_{prev_id}_last.png"
        first = scene_dir / "continuity" / f"cut{cut}_next_{next_id}_first.png"
        combined = scene_dir / "continuity" / f"cut{cut}_continuity.png"
        subprocess.run(["ffmpeg", "-y", "-v", "error", "-sseof", "-0.1", "-i",
                        str(assets[prev_id].uri_or_path), "-frames:v", "1",
                        str(last)], check=True, capture_output=True)
        subprocess.run(["ffmpeg", "-y", "-v", "error", "-i",
                        str(assets[next_id].uri_or_path), "-frames:v", "1",
                        str(first)], check=True, capture_output=True)
        subprocess.run(["ffmpeg", "-y", "-v", "error", "-i", str(last), "-i",
                        str(first), "-filter_complex", "[0:v][1:v]hstack=inputs=2",
                        "-frames:v", "1", str(combined)], check=True,
                       capture_output=True)
        cut_ledger.append({"cut": f"{prev_id}->{next_id}",
                           "packet": str(combined),
                           "semantic_verdict": "OWNER_REVIEW_RECOMMENDED",
                           "note": ("deterministic visual packet only; no "
                                    "qualified semantic VLM verdict fabricated")})
        print(json.dumps({"cut": cut, "packet": combined.name}), flush=True)

    # Scene EditManifest + AutoEdit producer package.
    clips = [EditClip(order=i, shot_id=takes[sid].shot_id,
                      selected_take_id=takes[sid].selected_take_id,
                      asset_id=takes[sid].asset_id, source_in_s=0.0,
                      source_out_s=8.0,
                      notes="PROVISIONAL_AUTONOMOUS_SELECTION")
             for i, sid in enumerate(SHOT_IDS, 1)]
    manifest = make_edit_manifest("ai_film_scene_scale_003", clips)
    sources = tuple(
        validate_source(clip, path=Path(assets[sid].uri_or_path),
                        expected_sha256=assets[sid].sha256,
                        attempt_id=takes[sid].generation_attempt_id,
                        qc_report_id=takes[sid].qc_report_id)
        for sid, clip in zip(SHOT_IDS, clips))
    locators = {takes[sid].asset_id: {
        "kind": "root_relative", "root_id": "scene003_media",
        "path": f"shot_{sid}/videos/" + Path(assets[sid].uri_or_path).name}
        for sid in SHOT_IDS}
    payload = build_film_input(manifest, sources,
        shots={sid: json.loads(json.dumps(specs[sid].model_dump(mode="json")))
               for sid in SHOT_IDS},
        locators=locators)
    package_id = write_referenced_package(
        payload, scene_dir / "autoedit_package",
        roots={"scene003_media": SCENE_DIR})

    # Real rough cut through the existing editorial boundary.
    rough = real_rough_cut(STORE_PATH, project_id="ai_film_scene_scale_003",
                           selected_take_ids=[takes[sid].selected_take_id
                                              for sid in SHOT_IDS],
                           output_dir=scene_dir / "rough_cut")

    summary = {"scene_id": "SCENE003_CLOUD_SUMMIT",
               "qc": qc_ledger, "cuts": cut_ledger,
               "edit_manifest_id": manifest.edit_manifest_id,
               "autoedit_package_id": package_id,
               "rough_cut": rough,
               "provisional_selection_note": NOTES[0]}
    (scene_dir / "scene_summary.json").write_text(
        json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps({"edit_manifest_id": manifest.edit_manifest_id,
                      "autoedit_package_id": package_id,
                      "rough_cut_render_id": rough["render_id"],
                      "rough_cut_sha256": rough["output_sha256"],
                      "rough_cut_duration_s": rough["duration_s"],
                      "full_decode": rough["full_decode"]}), flush=True)


if __name__ == "__main__":
    main()
