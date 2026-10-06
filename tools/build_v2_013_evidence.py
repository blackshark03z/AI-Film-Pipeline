"""V2-013 — Clean Master Route Decision evidence builder (read-only slice)."""
import json
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PKG = ROOT / "projects/quality_v2_013_clean_master_route"


def utcnow():
    return datetime.now(timezone.utc).isoformat()


def write(name, payload):
    (PKG / name).write_text(json.dumps(payload, indent=1,
                                       ensure_ascii=False), encoding="utf-8")
    print("wrote", name)


write("V2_013_DOLA_ENTITLEMENT.json", {
    "version": "v2-013-dola-entitlement-v1",
    "checkpoint": "V2013_P1_DOLA_PLAN_ENTITLEMENT",
    "recorded_at": utcnow(),
    "method": "read-only authenticated UI inspection (ACCOUNT_D, Khởi Đặng219; "
              "corroborated across every 011W/013 session on ACCOUNT_A and "
              "ACCOUNT_D); no purchase, no URL manipulation",
    "surfaces_inspected": [
        "chat home + composer (all chips: 動画を作成/画像を作成/文章作成/宿題/翻訳 — no plan/upgrade chip)",
        "sidebar (new chat, scheduled tasks, AI生成, Drive, skills, recents — no plan entry)",
        "account chip (Khởi Đặng219 ›) — opens no visible account surface",
        "settings gear (⚙) — opens no textual plan/subscription panel",
        "conversation credit statements (daily-allowance mechanics only)",
        "011W full scans: no plan/subscription/upgrade/billing element anywhere in the SPA",
    ],
    "credit_mechanics": "daily video-credit allowance announced in-chat after "
                        "generations (本日の残りはN動画クレジット); no tier/plan "
                        "structure exposed",
    "DOLA_PLAN_NO_WATERMARK": "NO",
    "entitlement_condition": None,
    "evidence": "no plan/subscription/upgrade/billing/watermark-entitlement "
                "surface exists in the authenticated consumer UI; the only "
                "site-level download element is the Windows desktop installer",
    "required_action": "NONE AVAILABLE via the plan route — the consumer web "
                       "product has no entitlement layer to enable",
    "do_not": "purchase/upgrade automatically; manipulate URLs (both honored "
              "— nothing was purchased and no URL was touched)",
})

write("V2_013_ELYUM_ROUTE.json", {
    "version": "v2-013-elyum-route-v1",
    "checkpoint": "V2013_P2_ELYUM_ROUTE",
    "recorded_at": utcnow(),
    "method": "read-only inspection of project truth (V2-009 Seedance audit, "
             "V2-010A route state, SoT 06_PROVIDER_CAPABILITIES.md) and the "
             "existing Story Auto implementation (story_auto/providers/"
             "elyum_seedance/{service,client}.py); NO generation",
    "fields": {
        "ELYUM_ADAPTER_EXISTS": "SPLIT — Story Auto: YES (752-line gated "
            "production service + 426-line MCP client, live-proven); "
            "AI-Film: NO adapter built (recorded in V2-009 §Unresolved and "
            "V2-010A ELYUM_STATE=AVAILABLE_ALTERNATIVE_NOT_AUTHORIZED)",
        "ELYUM_AUTH_STATE": "PROVEN AVAILABLE — Bearer key file present at "
            "D:/API KEY/elyum_api_key.txt (Owner-managed; value never read "
            "into evidence); env ELYUM_API_KEY supported; MCP endpoint "
            "https://elyum.ai/mcp",
        "ELYUM_SEEDANCE_MODEL_AVAILABLE": "YES — seedance-2-fast-i2v "
            "(Seedance 2.0 family) is the live-proven default; modes "
            "t2v/i2v/ugc/clone; 16:9; resolution default 480p; provider "
            "duration default 4s (the film's 5s class is a parameter, "
            "resolvable in an adapter)",
        "ELYUM_OUTPUT_WATERMARK_POLICY": "UNKNOWN/UNVERIFIED — zero "
            "watermark handling anywhere in the adapter code; the Dola AI "
            "watermark is a consumer-web delivery artifact (lr=cici_ai "
            "delivery channel) and is NOT expected on a direct API/MCP "
            "delivery, but this has NOT been established by any AI-Film "
            "evidence",
        "ELYUM_COST_MODEL": "credit-based — X2 KEEP live proof consumed 20 "
            "credits; production service enforces DEFAULT_MAX_CREDITS=44 "
            "per run; per-generation credit price varies by model/resolution "
            "(not fixed in project truth)",
        "ELYUM_JOB_IDENTITY_SUPPORT": "PROVEN — durable jobId/genId custody; "
            "idempotent clientRef (≤120 chars); request_identity_sha256 "
            "manifest binding (dispatch_state RECONCILE_BY_CLIENT_REF)",
        "ELYUM_DOWNLOAD_AUTHORITY": "PROVEN — repeated live proofs with "
            "durable download (R1 g_e2fa8c99…, X2 KEEP g_d59e88f0… 20 "
            "credits, X3 preview g_a18de93d… sha 8c9163…, UAT g_f62ed089… "
            "preview sha a8c72a65…)",
    },
    "classification": "ELYUM_CLEAN_ROUTE = READY_TO_QUALIFY",
    "rationale": "transport, identity, cost and download are live-proven in "
                 "Story Auto and the key is available — the shortest path to "
                 "an AI-Film-qualified clean Seedance claim per the V2-009 "
                 "route selection. It is NOT ALREADY_QUALIFIED (no AI-Film "
                 "adapter; output watermark policy unverified) and NOT NOT_READY "
                 "(nothing is missing except bounded work)",
    "expected_qualification_work": [
        "1. port the Story Auto MCP client behind the Film Core VideoProvider "
        "interface (the SoT-mandated adapter boundary)",
        "2. ONE bounded qualification canary (Owner-authorized mutation) that "
        "renders an existing frozen shot and ESTABLISHES "
        "ELYUM_OUTPUT_WATERMARK_POLICY by frame evidence (watermark present/absent)",
        "3. custody wiring: jobId/genId + clientRef + asset sha + editorial "
        "range mapping (the identity machinery already exists)",
        "4. if outputs are clean: content-equivalence QC vs the Dola asset of "
        "the same ShotSpec, then the controlled rebind decision",
    ],
})

write("V2_013_OFFICIAL_API_ROUTE.json", {
    "version": "v2-013-official-api-route-v1",
    "checkpoint": "V2013_P3_OFFICIAL_API_ROUTE",
    "recorded_at": utcnow(),
    "method": "architecture readiness inspection only (SoT "
              "06_PROVIDER_CAPABILITIES.md adapter interface; core.py "
              "provider_id/fallback_provider_ids fields; the provider-neutral "
              "boundary proven in FLOW-WORKER-SEMANTIC-BACKEND-014); NO "
              "implementation",
    "findings": {
        "adapter_interface_mandated": "the SoT defines the required "
            "VideoProvider adapter interface and the replaceable-adapter "
            "transport rule ('Film Core never stores cookies'; 'Implement "
            "independent adapters so one transport can fail without "
            "affecting canonical state')",
        "transport_isolation_proven": "the same ShotSpec → generation → "
            "take → editorial → QC pipeline has already assembled flow_veo "
            "assets AND seedance assets into conformed master cuts "
            "(007→010 masters; the 011D/012 V2 sequence) — no domain layer "
            "encodes transport semantics",
        "domain_layers_uncoupled": "ShotSpec, World State, Continuity, "
            "Editorial, Asset Registry, QC are provider-agnostic by "
            "construction (provider_id is data, not logic)",
        "official_api_blocked_on": "external availability — an official "
            "BytePlus/Seedance API entitlement for the Owner does not exist "
            "in project truth; nothing in AI-Film blocks adopting one",
    },
    "OFFICIAL_API_MIGRATION_COST": "MEDIUM",
    "rationale": "a new HTTP adapter behind the existing VideoProvider "
                 "interface + custody wiring + one qualification canary — "
                 "strictly simpler than the proven browser-automation "
                 "transport; not LOW because every provider needs its own "
                 "qualification, identity mapping and QC evidence",
})

write("V2_013_CLEAN_MASTER_DECISION.json", {
    "version": "v2-013-clean-master-decision-v1",
    "checkpoint": "V2013_P4_DECISION",
    "decided_at": utcnow(),
    "decision": "A. KEEP_CURRENT_WATERMARKED_PROOF_ONLY + qualify a clean "
                "route before final master",
    "internal_proof_vs_final_master": {
        "INTERNAL_PROOF": "the locked 326-frame watermarked sequence (proof "
                          "63eac46c…, SEQ_CONTEXT_LOCK GRANTED) remains the "
                          "valid authority for ALL editorial, continuity, QC "
                          "and review work — watermarks do not diminish its "
                          "proof value",
        "FINAL_DISTRIBUTION_MASTER": "NOT_YET_AUTHORIZED — a clean master "
                                     "requires a qualified clean route first; "
                                     "no such route is qualified today",
    },
    "route_evaluation": {
        "ROUTE_B_dola_plan": "REJECTED — DOLA_PLAN_NO_WATERMARK = NO (no "
                             "entitlement surface exists to enable)",
        "ROUTE_elyum": "PREFERRED CANDIDATE — READY_TO_QUALIFY (proven "
                       "transport/identity/download; output watermark policy "
                       "is the single unverified variable, resolvable by ONE "
                       "bounded canary in a future Owner-authorized slice)",
        "ROUTE_official_api": "VALID FALLBACK — MEDIUM cost, architecture "
                              "ready, blocked only on external entitlement "
                              "availability",
    },
    "rejected_alternatives": {
        "B_CURRENT_DOLA_PLAN_CAN_EXPORT_CLEAN": "false premise — no export "
                                                "entitlement exists",
        "C_ELYUM_CLEAN_ROUTE_IS_READY": "overstated — the route is ready to "
                                        "QUALIFY, not yet qualified; the "
                                        "watermark behavior of its outputs "
                                        "is unverified",
        "D_WAIT_FOR_OFFICIAL_API": "weaker than A — it idles a proven "
                                   "READY_TO_QUALIFY route while adding no "
                                   "new information",
    },
    "next_slice_shape": "V2-014 proposal: Elyum adapter port + ONE bounded "
                        "qualification canary (mutation authority 1, no "
                        "retry) whose explicit deliverable is the output "
                        "watermark verdict; only then a rebind/mastering "
                        "slice",
    "film_assets_untouched": True,
    "video_generation_mutations": 0,
})

write("V2_013_AUDIO_FINISHING_PLAN.json", {
    "version": "v2-013-audio-finishing-plan-v1",
    "checkpoint": "V2013_AUDIO_PLAN",
    "recorded_at": utcnow(),
    "status": "PLAN ONLY — no final master rendered in this slice",
    "inputs": {
        "proof_sha256": "63eac46c7a5568ba4a3c1f0ffe54d911f7d96d35d3369bab59c70fe31c1b30ef",
        "measured_steps": {"F1R_to_F2_db": 0.8, "F2_to_F3R_db": 8.0},
        "AUDIO_CONTEXT": "FINISHING_REPAIR_REQUIRED",
    },
    "plan": [
        {"step": 1, "action": "ambience bed inventory per unit (F1R/F2/F3R_012 "
                              "stem or mixdown analysis: spectrum, loudness, "
                              "wind character)",
         "output": "per-unit ambience map"},
        {"step": 2, "action": "J2 (F2→F3R, frame 249) level-match: ~8 dB "
                              "level ride or a 12-frame ambience crossfade "
                              "with a matched wind bed; J1 (frame 115) needs "
                              "only a 0.8 dB trim",
         "output": "continuous ambience across both cuts"},
        {"step": 3, "action": "wind-character continuity pass (the storm bed "
                              "must not change character at cuts — same "
                              "spectral family, speed and gust rhythm)",
         "output": "single storm ambience continuity"},
        {"step": 4, "action": "loudness normalization to the distribution "
                              "target (e.g., -14 LUFS streaming / -23 LUFS "
                              "broadcast — Owner picks) with true-peak cap",
         "output": "delivery-grade loudness"},
        {"step": 5, "action": "render the finishing master in the SAME slice "
                              "as (or after) the clean-video route "
                              "qualification, so watermark status and audio "
                              "land together in ONE final mastering pass",
         "output": "final master candidate for Owner review"},
    ],
    "rules": [
        "audio is never a cause of video regeneration",
        "original source audio preserved until the finishing render",
        "watermark untouched by any audio work",
    ],
})

write("V2_013_CANDIDATE_SEAL.json", {
    "version": "v2-013-candidate-seal-v1",
    "sealed_at": utcnow(),
    "checkpoint": "V2013_SEAL",
    "status": "COMPLETED_CANDIDATE",
    "decision": "A. KEEP_CURRENT_WATERMARKED_PROOF_ONLY + qualify clean route "
                "before final master",
    "canonical": {
        "SEQ7_F1_F2_F3": "FILM_USABLE (unchanged)",
        "SEQ_CONTEXT_LOCK": "GRANTED (unchanged)",
        "locked_proof_sha256": "63eac46c7a5568ba4a3c1f0ffe54d911f7d96d35d3369bab59c70fe31c1b30ef",
        "watermark": "PRESENT (untouched)",
        "internal_proof": "YES",
        "clean_final_master": "NOT_YET_AUTHORIZED",
        "DOLA_PLAN_NO_WATERMARK": "NO",
        "ELYUM_CLEAN_ROUTE": "READY_TO_QUALIFY",
        "OFFICIAL_API_MIGRATION_COST": "MEDIUM",
    },
    "checks": {
        "head_verified": True,
        "no_generation": True,
        "no_asset_replacement": True,
        "no_watermark_removal": True,
        "011w_not_reopened": True,
        "three_routes_evaluated": True,
        "audio_plan_only_no_render": True,
        "film_assets_untouched": True,
        "video_generation_mutations": 0,
    },
    "next_handoff": "STOP — return to Tech Lead. Proposed next: V2-014 (Elyum "
                    "adapter port + ONE bounded watermark-verdict canary), "
                    "then the rebind/mastering decision. No regeneration or "
                    "final mastering begins without a new package",
})

print("V2-013 evidence complete")
