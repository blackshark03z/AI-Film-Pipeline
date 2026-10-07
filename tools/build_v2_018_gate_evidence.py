"""V2-018 — resource gate evidence + seal (credential missing, fail-closed)."""
import json
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PKG = ROOT / "projects/quality_v2_018_byteplus_live"
PKG.mkdir(parents=True, exist_ok=True)


def utcnow():
    return datetime.now(timezone.utc).isoformat()


def write(name, payload):
    (PKG / name).write_text(json.dumps(payload, indent=1,
                                       ensure_ascii=False), encoding="utf-8")
    print("wrote", name)


write("V2_018_RESOURCE_GATE.json", {
    "version": "v2-018-resource-gate-v1",
    "checkpoint": "V2018_P1_RESOURCE_GATE",
    "recorded_at": utcnow(),
    "status": "STOPPED_OWNER_CREDENTIAL_REQUIRED",
    "head_verified": "9f69eab536b167ac3f190e9f6fb6ffb4a6a96e15",
    "worktree_clean": True,
    "v2_017_source_authority": "UNCHANGED (transport reconstruction + source "
                               "snapshots intact; model "
                               "dreamina-seedance-2-5-260628; endpoint family "
                               "ark.ap-southeast.bytepluses.com/api/v3)",
    "credential_sources_checked": [
        {"source": "env BYTEPLUS_MODELARK_API_KEY", "result": "unset"},
        {"source": "env BYTEPLUS_API_KEY", "result": "unset"},
        {"source": "env ARK_API_KEY", "result": "unset"},
        {"source": "D:/API KEY/ directory (12 Owner key files listed)",
         "result": "NO byteplus/ark/modelark key file present",
         "files_seen": ["coverr", "deepseek", "elevenlabs", "elyum",
                        "gemini", "justworker", "notion", "open_ai",
                        "pixaby", "typecast", "wanglin08ma_client_desktop",
                        "youtubeapi"]},
        {"source": "Story Auto provider pool provider_keys("
                   "'byteplus_modelark') — DPAPI store %LOCALAPPDATA%/"
                   "Story Auto/credentials.v1.json + legacy fallback",
         "result": "CREDENTIAL_MISSING (pool exists, no key enrolled)"},
    ],
    "conclusion": "NO BytePlus ModelArk credential exists in any "
                  "Owner-managed local source. Per package Phase 1: "
                  "STOPPED_OWNER_CREDENTIAL_REQUIRED — no provider mutation "
                  "created; nothing spent",
    "never_concluded_resource_exhaustion": True,
    "mutation_ledger": {"DRAFT": "0/1 UNSPENT",
                        "FINALIZATION": "0/1 UNSPENT",
                        "total": "0/2"},
    "frozen_experiment_ready": {
        "model": "dreamina-seedance-2-5-260628",
        "endpoint": "https://ark.ap-southeast.bytepluses.com/api/v3",
        "prompt_class": "wide cinematic windswept mountain pass, cool "
                        "overcast, tall grass and mist in wind, slow lateral "
                        "tracking, dark rock, no text/logos/architecture, "
                        "no people",
        "draft": {"resolution": "480p", "draft": True, "duration": 4,
                  "ratio": "16:9", "generate_audio": False,
                  "seed": 20260218, "watermark": False},
        "finalization": {"resolution": "1080p", "watermark": False,
                         "content_type": "draft_task",
                         "reference": "the draft task id from this slice"},
    },
    "owner_request": "provision a BytePlus ModelArk API key (enroll in the "
                     "Story Auto byteplus_modelark pool or place a key file "
                     "under D:/API KEY/), plus enough credits for one 480p "
                     "draft + one 1080p finalization — then re-run this "
                     "slice; the frozen canary and governance machinery are "
                     "ready",
})

# ---- mutation ledger ------------------------------------------------------------
write("V2_018_MUTATION_LEDGER.json", {
    "version": "v2-018-mutation-ledger-v1",
    "checkpoint": "V2018_LEDGER",
    "recorded_at": utcnow(),
    "authority": {"DRAFT_MUTATION": "0/1",
                  "FINALIZATION_MUTATION": "0/1",
                  "total_provider_paid_mutations": "0/2"},
    "no_retry": True,
    "events": [
        {"at": utcnow(), "kind": "RESOURCE_GATE_FAILED_CLOSED",
         "detail": "no BytePlus credential in any Owner-managed local "
                   "source; STOPPED_OWNER_CREDENTIAL_REQUIRED"}],
})

# ---- secret audit ------------------------------------------------------------------
write("V2_018_SECRET_AUDIT.json", {
    "version": "v2-018-secret-audit-v1", "built_at": utcnow(),
    "scope": "no credential values were read into evidence at any point; "
             "the gate checked presence only (length/unset state)",
    "verdict": "CLEAN"})

write("V2_018_CANDIDATE_SEAL.json", {
    "version": "v2-018-candidate-seal-v1", "sealed_at": utcnow(),
    "checkpoint": "V2018_SEAL",
    "status": "STOPPED_OWNER_CREDENTIAL_REQUIRED",
    "completed_candidate": False,
    "engineering_status": "frozen canary + governance + adapter design ready "
                          "(V2-017 source authority intact)",
    "canonical": {
        "SEQ7_F1_F2_F3": "CLEAN_DISTRIBUTION_MASTER_READY (untouched)",
        "FINAL_MASTER_LOCK": "GRANTED (unchanged)",
        "ELYUM_CANARY": "0/1 UNSPENT (frozen)",
        "BYTEPLUS_DRAFT": "0/1 UNSPENT",
        "BYTEPLUS_FINALIZATION": "0/1 UNSPENT",
        "video_generation_mutations": 0},
    "next_handoff": "STOP — return to Owner: provision a BytePlus ModelArk "
                    "API key + credits, then re-run V2-018; the frozen "
                    "canary (480p draft → 1080p same-take final, "
                    "watermark=false) dispatches as-is under the existing "
                    "governance",
})

print("V2-018 evidence complete")
