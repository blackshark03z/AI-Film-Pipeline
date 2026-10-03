"""FLOW-OWNER-REVIEW-SEMANTIC-RELEASE-012 (R8): consolidated Owner Review
Packet V2 — the four Package-009 successor slots + semantic qualification
findings + model comparison; plus R9/R10 narration/caption requirement
documents (specification only, no synthesis).
"""
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
D11 = ROOT / "projects/flow_semantic_delivery_011"
D12 = ROOT / "projects/flow_owner_review_release_012"
M10 = ROOT / "projects/flow_editorial_runtime_scale_010/master_package_010"

p11 = json.loads((D11 / "review/owner_review_packet_011.json")
                 .read_text(encoding="utf-8"))
semantic = json.loads((D11 / "qualification_011.json").read_text(
    encoding="utf-8"))
comparison = json.loads((D12 / "semantic_model_comparison_012.json")
                        .read_text(encoding="utf-8"))
narration = json.loads((D11 / "narration_discovery_011.json").read_text(
    encoding="utf-8"))

packet = {
    "version": "owner-review-packet-012-v1",
    "entries": p11["entries"],
    "semantic_context": {
        "verdict": "SEMANTIC_QC_NOT_QUALIFIED for both tested models",
        "gemini_3_5_flash_lite": {
            "model": semantic["model_frozen"],
            "verdict": "NOT_QUALIFIED",
            "mismatched_controls": [m["control_id"]
                                    for m in semantic["run1"]["mismatches"]]},
        "gemini_3_1_flash_lite": {
            "model": comparison["gemini_3_1_flash_lite"]["model"],
            "verdict": "NOT_QUALIFIED",
            "mismatched_controls": comparison["gemini_3_1_flash_lite"][
                "failed_control_ids"],
            "service_errors": comparison["gemini_3_1_flash_lite"][
                "api_error_details"]},
        "comparison": comparison["classification"],
        "owner_decision_requested": (
            "accept a NOT_QUALIFIED semantic gate for this production, "
            "authorize a higher-capability model attempt, or waive "
            "semantic QC for this film")},
    "narration_gate": narration["classification"],
    "caption_gate": "TIMED_CAPTION_AUTHORITY_UNAVAILABLE",
    "no_auto_approval": ("confidence scores and technical QC are advisory; "
                         "artistic quality approval is reserved to the "
                         "Owner")}
D12.mkdir(parents=True, exist_ok=True)
(D12 / "owner_review_packet_012.json").write_text(
    json.dumps(packet, indent=2, ensure_ascii=False), encoding="utf-8")

narration_req = {
    "version": "narration-production-requirement-012-v1",
    "status": "CONTENT_AUDIO_PRODUCTION_UNQUALIFIED",
    "requirement": "a future narration source MUST provide:",
    "must_provide": [
        "project/story binding to the canonical swordsman film lineage "
        "(Packages 004-010 asset hashes or the canonical master sha)",
        "source text authority (script/transcript document + its own hash)",
        "voice source provenance (who/what performed the narration; TTS "
        "engine + voice id + config hash if synthetic)",
        "audio file SHA-256, duration_s, sample_rate (48000), channels "
        "(1 or 2), mime type",
        "timed transcript expectations: either an authoritative timed "
        "transcript (SRT/VTT with cue hashes) or an explicit "
        "continuous-narration declaration (no fabricated word timings)",
        "licensing/provenance metadata if the voice or text is third-party"],
    "adoption_contract": "AudioAsset + AudioClip + AudioLane "
                         "(src/film_pipeline/audio_lane.py) with hash-bound "
                         "placement; continuous narration may be placed as "
                         "ONE clip; word-level timing will not be invented",
    "forbidden": "synthesizing narration just to make the gate green"}
(D12 / "narration_production_requirement_012.json").write_text(
    json.dumps(narration_req, indent=1), encoding="utf-8")

caption_req = {
    "version": "caption-production-requirement-012-v1",
    "status": "TIMED_CAPTION_AUTHORITY_UNAVAILABLE",
    "requirement": "a future caption source MUST provide:",
    "must_provide": [
        "authoritative timed transcript bound to the narration source hash "
        "or the canonical master sha",
        "cue ordering strictly increasing, end > start, no negative times",
        "no cue beyond the canonical master duration (194.541667 s)",
        "UTF-8 encoding",
        "source lineage (who authored the timing, from what transcript)"],
    "adoption_contract": "deterministic .srt and .vtt generated from the "
                         "authoritative timing only; validation before "
                         "adoption",
    "forbidden": "guessed or model-generated timings without authority"}
(D12 / "caption_production_requirement_012.json").write_text(
    json.dumps(caption_req, indent=1), encoding="utf-8")
print(json.dumps({"packet_entries": len(packet["entries"]),
                  "semantic_findings_included": True,
                  "requirement_docs": ["narration", "caption"]}))
