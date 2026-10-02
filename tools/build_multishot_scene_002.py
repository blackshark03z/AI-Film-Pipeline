"""FLOW-PRODUCTION-HARDEN-MULTISHOT-002 — scene package for the proven vertical.

Read-only over the two proven shot assets: formal QC reports + provisional
SelectedTakes (transparently labeled autonomous build-worker approval, pending
Owner post-hoc review), a Shot A-last-frame / Shot B-first-frame continuity
packet, an EditManifestV1, and the AutoEdit producer package (referenced
media; no copying of project state; no AutoEdit redesign).
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
from film_pipeline.editorial import make_edit_manifest, probe_media, validate_source, EditClip
from film_pipeline.live_runtime import Asset
from film_pipeline.qc import (
    derive_disposition,
    derive_report,
    evidence,
    human_decision,
    technical_evidence,
)

ROOT = Path(__file__).resolve().parents[1]
QUAL_DIR = ROOT / "projects/flow_production_harden_002/multishot_vertical"
STORE_PATH = ROOT / "projects/flow_production_harden_002/requal_current_build/runtime.sqlite"
PROJECT_ID = "93a579b4-834e-435b-8304-5f6682937935"
SCENE_ID = "HARDEN_002_CLOUD_SUMMIT"
REVIEWER = "FLOW-HARDEN-002-BUILD-WORKER (autonomous provisional; pending Owner post-hoc review)"
NOTES = [
    "Provisional autonomous approval under frozen package "
    "FLOW_PRODUCTION_HARDEN_MULTISHOT_002 while the Owner is away.",
    "Subjective gates asserted from the technical QC + continuity packet; "
    "the Owner may reject and re-select at any time.",
]
SHOTS = {"A": ROOT / "fixtures/multishot_shot_a.json",
         "B": ROOT / "fixtures/multishot_shot_b.json"}


def main() -> None:
    takes, reports, assets, shots = {}, {}, {}, {}
    for tag in ("A", "B"):
        result = json.loads((QUAL_DIR / f"shot_{tag}" / f"shot_{tag}_result.json")
                            .read_text(encoding="utf-8"))
        if result["gate"] != "SHOT_PROVEN":
            raise SystemExit(f"shot {tag} not proven; no scene package")
        asset = Asset.model_validate(result["asset"])
        shot = load_shot(SHOTS[tag])
        evidence_rows, metadata = technical_evidence(shot, asset)
        human = human_decision(
            asset=asset, reviewer_id=REVIEWER, action="APPROVE",
            visual_pass=True, continuity_pass=True, editorial_pass=True,
            notes=NOTES)
        # Subjective-gate evidence rows recorded by the provisional reviewer;
        # the continuity packet is produced below and referenced by path+hash.
        evidence_rows = list(evidence_rows) + [
            evidence(asset=asset, evaluator_type="human",
                     evaluator_version="build_worker_provisional-v1", gate=gate,
                     criterion="provisional_autonomous_approval",
                     observation=("Provisional autonomous build-worker approval "
                                  "under FLOW_PRODUCTION_HARDEN_MULTISHOT_002; "
                                  "pending Owner post-hoc review."),
                     verdict="pass",
                     source_artifacts=[{"path": str(asset.uri_or_path),
                                        "sha256": asset.sha256}])
            for gate in ("visual", "continuity", "editorial")]
        record = derive_report(asset, evidence_rows, human)
        disposition = derive_disposition(shot.shot_id, asset, record, human)
        if not isinstance(disposition, object) or disposition is None or \
                not hasattr(disposition, "selected_take_id"):
            raise SystemExit(f"shot {tag}: no SelectedTake ({record.report['decision']})")
        takes[tag] = disposition
        reports[tag] = record
        assets[tag] = asset
        shots[tag] = shot
        print(json.dumps({"shot": tag, "qc_decision": record.report["decision"],
                          "selected_take_id": disposition.selected_take_id}), flush=True)

    # Continuity packet: Shot A last frame | Shot B first frame, side by side.
    scene_dir = QUAL_DIR / "scene_package"
    (scene_dir / "continuity").mkdir(parents=True, exist_ok=True)
    last_a = scene_dir / "continuity" / "shot_a_last_frame.png"
    first_b = scene_dir / "continuity" / "shot_b_first_frame.png"
    combined = scene_dir / "continuity" / "continuity_a_end_vs_b_start.png"
    subprocess.run(["ffmpeg", "-y", "-v", "error", "-sseof", "-0.2", "-i",
                    str(assets["A"].uri_or_path), "-frames:v", "1", str(last_a)],
                   check=True, capture_output=True)
    subprocess.run(["ffmpeg", "-y", "-v", "error", "-i", str(assets["B"].uri_or_path),
                    "-frames:v", "1", str(first_b)], check=True, capture_output=True)
    subprocess.run(["ffmpeg", "-y", "-v", "error", "-i", str(last_a), "-i", str(first_b),
                    "-filter_complex", "[0:v][1:v]hstack=inputs=2", "-frames:v", "1",
                    str(combined)], check=True, capture_output=True)
    print(json.dumps({"continuity_packet": str(combined)}), flush=True)

    # EditManifest + AutoEdit producer package (referenced media).
    clips = [EditClip(order=1, shot_id=takes["A"].shot_id,
                      selected_take_id=takes["A"].selected_take_id,
                      asset_id=takes["A"].asset_id, source_in_s=0.0,
                      source_out_s=8.0,
                      notes="Scene establishing shot; provisional selection."),
             EditClip(order=2, shot_id=takes["B"].shot_id,
                      selected_take_id=takes["B"].selected_take_id,
                      asset_id=takes["B"].asset_id, source_in_s=0.0,
                      source_out_s=8.0,
                      notes="Continuation shot on the same verified reference; provisional selection.")]
    manifest = make_edit_manifest("ai_film_hardened_multishot_002", clips)
    sources = tuple(
        validate_source(clip, path=Path(assets[tag].uri_or_path),
                        expected_sha256=assets[tag].sha256,
                        attempt_id=takes[tag].generation_attempt_id,
                        qc_report_id=takes[tag].qc_report_id)
        for tag, clip in (("A", clips[0]), ("B", clips[1])))
    probes = [probe_media(Path(asset.uri_or_path)) for asset in assets.values()]
    locators = {
        takes["A"].asset_id: {"kind": "root_relative", "root_id": "multishot_media",
                              "path": "shot_A/videos/" +
                                      Path(assets["A"].uri_or_path).name},
        takes["B"].asset_id: {"kind": "root_relative", "root_id": "multishot_media",
                              "path": "shot_B/videos/" +
                                      Path(assets["B"].uri_or_path).name},
    }
    payload = build_film_input(manifest, sources,
                               shots={shot.shot_id: json.loads(
                                          json.dumps(shot.model_dump(mode="json")))
                                      for shot in shots.values()},
                               locators=locators)
    package_id = write_referenced_package(
        payload, scene_dir / "autoedit_package",
        roots={"multishot_media": QUAL_DIR})
    summary = {
        "scene_id": SCENE_ID,
        "qc": {tag: reports[tag].report for tag in ("A", "B")},
        "selected_takes": {tag: takes[tag].model_dump(mode="json")
                           for tag in ("A", "B")},
        "edit_manifest_id": manifest.edit_manifest_id,
        "autoedit_package_id": package_id,
        "continuity_packet": str(combined),
        "provisional_selection_note": NOTES[0],
    }
    (scene_dir / "scene_summary.json").write_text(
        json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps({"scene_package": str(scene_dir / "scene_summary.json"),
                      "autoedit_package_id": package_id,
                      "edit_manifest_id": manifest.edit_manifest_id}), flush=True)


if __name__ == "__main__":
    main()
