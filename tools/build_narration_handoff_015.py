"""FLOW-OWNER-REVIEW-CONTENT-GATES-015 (Phase 8): narration content
handoff package.

Deterministic handoff for whoever eventually produces narration. NO TTS
call, no invented script: current truth is that no authoritative
narration text exists for the canonical film
(NARRATION_TEXT_AUTHORITY_MISSING). The package binds exactly what an
authoritative input must satisfy so a real narration asset can be
adopted with zero new architecture work.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

D15 = ROOT / "projects/flow_owner_review_content_gates_015"
M10 = (ROOT / "projects/flow_editorial_runtime_scale_010/"
       "master_package_010")
MASTER_SHA = "976876a1a24a0fe50ea5cff9ea24694f1196ec0faf25edec3a5f1afda1786595"


def main() -> None:
    master = json.loads((M10 / "master_summary.json").read_text(
        encoding="utf-8"))
    timing = [{"order": s["order"], "slot_id": s["slot_id"],
               "scene": s["scene"], "sequence": s["sequence"]}
              for s in master["slots"]]
    handoff = {
        "version": "narration-handoff-015-v1",
        "status": "NARRATION_TEXT_AUTHORITY_MISSING",
        "status_note": ("no authoritative narration text/script exists "
                        "for the canonical swordsman film (Package-011 "
                        "S8/S10 scans; unchanged since). No script is "
                        "invented here. The narration gate stays "
                        "CONTENT_AUDIO_PRODUCTION_UNQUALIFIED until a "
                        "real authoritative source is bound."),
        "project_identity": {
            "project": "swordsman_film",
            "canonical_master_sha256": MASTER_SHA,
            "canonical_master_version": master["version"],
            "canonical_lineage": "Packages 004-010 (adopted SEQ004/005 + "
                                 "live SEQ007 + reproof successors)"},
        "narrative_authority": {
            "state": "MISSING",
            "rule": "the eventual producer MUST receive the authoritative "
                    "text from the Owner; NarrationSourceReceipt requires "
                    "text_authority_id + sha256 binding that source"},
        "required_output_audio_format": {
            "container_mime": ["audio/x-wav", "audio/mpeg", "audio/aac",
                               "audio/flac"],
            "sample_rate": 48000,
            "channels": "1 (mono) or 2 (stereo)",
            "max_duration_s": master["duration_s"],
            "placement_contract": "AudioAsset + AudioClip + AudioLane "
                                  "(src/film_pipeline/audio_lane.py); "
                                  "continuous narration may be placed as "
                                  "ONE clip; word-level timing is never "
                                  "invented"},
        "master_target_duration_s": master["duration_s"],
        "scene_shot_timing_references": timing,
        "delivery_naming_contract": {
            "audio": "narration/narration_master.<ext> (repo-relative "
                     "inside the delivery bundle)",
            "receipt": "manifests/narration_source_receipt.json",
            "rule": "the delivery manifest role narration_master binds "
                    "the exact audio sha256"},
        "required_provenance_receipt": {
            "schema": "NarrationSourceReceipt v1 "
                      "(src/film_pipeline/content_release.py)",
            "fields": ["project", "story_authority_id",
                       "story_authority_sha256", "text_authority_id",
                       "text_authority_sha256", "audio_locator",
                       "audio_sha256", "duration_s", "sample_rate",
                       "channels", "mime_type", "voice_provenance",
                       "production_provenance", "license_note",
                       "transcript_authority_id (optional)",
                       "timed_transcript_identity (optional)"]},
        "required_transcript_timing_expectations": {
            "rule": "either an authoritative timed transcript (SRT/VTT "
                    "with cue hashes bound to the narration text) or an "
                    "explicit continuous-narration declaration; guessed "
                    "or model-generated timings are forbidden",
            "caption_contract": "TimedCaptionSource v1 "
                                "(src/film_pipeline/content_release.py)"},
        "forbidden": "synthesizing narration or inventing a script just "
                     "to make the gate green",
    }
    out_dir = D15 / "narration_handoff_015"
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "narration_handoff_015.json").write_text(
        json.dumps(handoff, indent=2, ensure_ascii=False),
        encoding="utf-8")
    print(json.dumps({"out": str(out_dir / "narration_handoff_015.json"),
                      "status": handoff["status"],
                      "timing_refs": len(timing)}))


if __name__ == "__main__":
    main()
