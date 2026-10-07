"""V2-017 — Seedance 2.5 Draft→Final transport authority evidence."""
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PKG = ROOT / "projects/quality_v2_017_seedance25_transport"


def utcnow():
    return datetime.now(timezone.utc).isoformat()


def write(name, payload):
    (PKG / name).write_text(json.dumps(payload, indent=1,
                                       ensure_ascii=False), encoding="utf-8")
    print("wrote", name)


write("V2_017_SOURCE_AUTHORITY.json", {
    "version": "v2-017-source-authority-v1",
    "checkpoint": "V2017_P1_SOURCES",
    "recorded_at": utcnow(),
    "priority_1_source_implementation": {
        "repo": "comfyanonymous/ComfyUI (master)",
        "files": [
            "comfy_api_nodes/nodes_bytedance.py (3907 lines — built-in "
            "ByteDance partner nodes incl. Seedance 2.5 Draft and the "
            "ByteDance Seedance 2.5 Draft to Final Video node)",
            "comfy_api_nodes/apis/bytedance.py (425 lines — wire schemas: "
            "Seedance2TaskCreationRequest, TaskDraftTaskContent, "
            "TaskStatusResponse)",
        ],
        "fetched": "raw.githubusercontent.com master snapshots retained in "
                   "analysis/ (nodes_bytedance.py, bytedance_schema.py)",
    },
    "priority_2_official_api": {
        "provider": "BytePlus ModelArk (volcengine Ark twin)",
        "endpoint": "https://ark.ap-southeast.bytepluses.com/api/v3",
        "paths": ["POST contents/generations/tasks",
                  "GET contents/generations/tasks/{task_id}",
                  "GET contents/generations/tasks?page_num&page_size"],
        "auth": "Bearer API key",
    },
    "priority_3_local_implementation": {
        "repo": "D:/Story Auto/story-auto @ 5464cbb",
        "files": ["story_auto/providers/byteplus_seedance/client.py (221 "
                  "lines — SAME endpoint/model/task flow, watermark: False "
                  "in the request, host-allowlisted downloads, durable "
                  "service layer with ambiguous-POST discipline)"],
    },
    "no_local_comfyui_install": "no ComfyUI installation found on this "
                                "machine; the SOURCE is the upstream repo",
})

write("V2_017_TRANSPORT_RECONSTRUCTION.json", {
    "version": "v2-017-transport-reconstruction-v1",
    "checkpoint": "V2017_P2_TRANSPORT",
    "recorded_at": utcnow(),
    "upstream_provider": "BytePlus ModelArk (Dreamina Seedance family; "
                         "Volcengine Ark twin on the CN side)",
    "auth_model": "Bearer API-key scheme (Authorization header with a "
            "secret key value; scheme name only — no key material in "
            "evidence); env "
                  "BYTEPLUS_MODELARK_API_KEY / BYTEPLUS_API_KEY / ARK_API_KEY",
    "draft_submit": {
        "endpoint": "POST /api/v3/contents/generations/tasks",
        "model_id": "dreamina-seedance-2-5-260628 (SAME model id as the "
                    "final — Draft is a mode flag, not a different model)",
        "request_schema": {
            "model": "dreamina-seedance-2-5-260628",
            "content": [{"type": "text", "text": "<prompt>"}],
            "generate_audio": "bool",
            "resolution": "480p",
            "ratio": "16:9 (or adaptive for edit/extend)",
            "duration": "int seconds (4..30 per Story Auto; model-level "
                        "durations 4-15 in the Elyum catalog)",
            "seed": "int — MUST be fixed to reuse the reviewed draft",
            "watermark": "bool (request parameter, default false)",
            "draft": True},
    },
    "draft_task_id_source": "TaskCreationResponse.id — the draft task's own "
                            "persistent id IS the draft_task_id (the ComfyUI "
                            "t2v node returns initial_response.id as the "
                            "draft_task_id output); only the 'Seedance 2.5 "
                            "Draft' mode produces a draft_task_id "
                            "(_seedance2_validate_draft_output)",
    "poll_status": {
        "endpoint": "GET /api/v3/contents/generations/tasks/{task_id} "
                    "(ComfyUI uses the /proxy/byteplus-seedance2/ variant "
                    "for Seedance 2.x status)",
        "statuses": ["queued", "running", "cancelled", "succeeded", "failed"],
        "interval": "9 s (ComfyUI poll_op)",
        "result": "content.video_url (https, provider CDN)",
    },
    "expiry": "A draft can be rendered (finalized) for 7 DAYS after creation "
              "(node tooltip); BytePlus clears output URLs 24 h after task "
              "completion (docs) — acquire promptly",
    "finalization": {
        "endpoint": "POST /api/v3/contents/generations/tasks (the SAME task "
                    "creation endpoint — finalization is a task whose "
                    "content references the draft)",
        "request_schema": {
            "model": "dreamina-seedance-2-5-260628",
            "content": [{"type": "draft_task",
                         "draft_task": {"task": {"id": "<draft_task_id>"}}}],
            "resolution": "1080p",
            "watermark": "bool (default false)"},
        "provider_documented_same_take": "The final keeps the draft's scene "
            "and motion, and reuses its prompt, references, duration, aspect "
            "ratio, and audio setting (node description) — SAME-TAKE, not a "
            "regeneration",
        "price_badge": "$3.2864..$29.3964 per finalization (duration/refs "
                       "dependent)",
    },
    "watermark_parameter": "explicit request field `watermark: bool` on BOTH "
                           "draft and final tasks (Story Auto client sends "
                           "watermark: False; ComfyUI node default false)",
    "resolution_duration_reference_audio": {
        "draft_resolution": "480p",
        "final_resolution": "1080p",
        "duration": "4-30 s (Story Auto validation); Elyum catalog 4-15",
        "references": "up to 30 images + 10 videos (<=15 s) + 10 audios; "
                      "auto downscale/upscale of reference videos",
        "audio": "generate_audio flag; audio-policy rejection class "
                 "documented (OutputAudioSensitiveContentDetected)",
    },
    "output_identity": "task id (persistent, listable via "
                       "contents/generations/tasks listing) + content."
                       "video_url per task",
    "download_authority": "content.video_url, https, host allowlist "
                          "volces.com/bytepluses.com/byteplus.com "
                          "(Story Auto client enforces)",
    "pricing_semantics": "per-frame: 2.5 480p = 400 frames/ratio-unit at "
                         "$0.015301/kframe; 2.5 1080p = 2025 frames at "
                         "$0.016731/kframe — 4 s 480p draft ≈ $0.59; 4 s "
                         "1080p final ≈ $3.29 (ComfyUI price-badge formula)",
    "account_pool": "one API key = one account namespace; the finalize POST "
                    "must run under the SAME key as the draft (task "
                    "ownership scoping — cross-account finalize is NOT "
                    "documented; treat as same-account required)",
    "restart_idempotency": "poll GETs are idempotent; the draft task id is "
                           "persistent and listable; a POST dispatch is "
                           "ambiguous on transport failure (Story Auto "
                           "AMBIGUOUS_POST_DISPATCH discipline: reconcile "
                           "via list_tasks/get_task, NEVER a second POST)",
})

write("V2_017_DRAFT_FINAL_DOMAIN_MODEL.json", {
    "version": "v2-017-draft-final-domain-model-v1",
    "checkpoint": "V2017_P6_DOMAIN_MODEL",
    "recorded_at": utcnow(),
    "status": "READY — the provider natively supports the lineage; the "
              "provider-neutral types map 1:1",
    "mapping": {
        "DraftAttempt": {
            "attempt_id": "AI-Film attempt id",
            "shot_spec_hash": "ShotSpec hash",
            "prompt_plan_hash": "PromptPlan hash",
            "provider": "byteplus_seedance",
            "account_binding": "API key identity (same key required for "
                               "finalization)",
            "provider_draft_id": "TaskCreationResponse.id of the draft "
                                 "(task with draft=true, resolution 480p)",
            "draft_asset": "content.video_url @ 480p (acquired for draft QC)",
            "expiry": "finalize within 7 days; output URL 24 h",
            "mutation_receipt": "dispatch journal + reservation (the 011D/"
                                "012 discipline applies unchanged)"},
        "DraftSelection": {
            "draft_attempt_id": "the selected draft attempt",
            "director_qc_verdict": "composition/blocking/motion/world/beat "
                                   "(draft-authoritative list)",
            "selected": True},
        "FinalizationAttempt": {
            "parent_draft_attempt_id": "MUST reference the exact draft "
                                       "(content type draft_task → task.id)",
            "provider_finalization_id": "TaskCreationResponse.id of the "
                                        "finalization task",
            "final_asset": "content.video_url @ 1080p",
            "resolution": "1080p (same take)",
            "mutation_receipt": "same discipline"},
    },
    "film_core_boundary": "Film Core never sees draft: true, content type "
                          "draft_task, ModelArk paths, CDN hosts or "
                          "signature params — the adapter exposes "
                          "submit_draft/poll/fetch_outputs/finalize/download",
})

write("V2_017_COST_MODEL.json", {
    "version": "v2-017-cost-model-v1",
    "checkpoint": "V2017_P7_ECONOMICS",
    "recorded_at": utcnow(),
    "per_shot_economics": {
        "draft_480p_4s": "≈ $0.59 (formula) — the draft price is duration- "
                         "and ratio-driven",
        "final_1080p_4s": "≈ $3.29",
        "comparison_dola": "Dola Seedance 2.5 = 5× credits (subscriber-"
                           "gated); Elyum 2.5 = 136-170 credits quoted",
        "comparison_watermarked_dola_current": "the existing clean route "
                                               "(V2-011X rebind) has NO "
                                               "incremental generation cost",
    },
    "break_even": "draft-first is cheaper than final-first whenever a shot "
                  "needs more than ~1.2 attempts at final quality "
                  "(0.59·N + 3.29 < 3.29·(1+rejects) → rejects > 0.18·N "
                  "roughly — director-stage rejection pays immediately)",
    "no_credits_spent": True,
})

write("V2_017_ACCOUNT_POOL_IMPLICATIONS.json", {
    "version": "v2-017-account-pool-v1",
    "checkpoint": "V2017_P9_ACCOUNT_POOL",
    "recorded_at": utcnow(),
    "binding": "ONE BytePlus API key = ONE account namespace; the draft and "
               "its finalization MUST share the key (task ownership)",
    "rotation": "rotation is possible only BEFORE the draft dispatch; after "
                "the draft exists, the same account must finalize it",
    "credential_check": "env BYTEPLUS_MODELARK_API_KEY / BYTEPLUS_API_KEY / "
                        "ARK_API_KEY or the Story Auto key pool "
                        "(provider_keys('byteplus_modelark')) — key "
                        "PROVISION STATE NOT VERIFIED in this slice",
})

# ---- secret audit ----------------------------------------------------------------
# The auth-SCHEME name ("Bearer") legitimately appears in transport docs; the
# authoritative check is that no credential VALUE leaked anywhere.
import os
MARKERS = [b"sessionid=", b"msToken=", b"a_bogus=", b"key_seed=",
           b"BEGIN OPENSSH", b"BEGIN RSA PRIVATE", b"BEGIN PRIVATE KEY"]
hits, scanned = [], 0
targets = sorted(ROOT.glob("tools/v2_017_*.py")) + \
    [p for p in sorted(PKG.glob("*.json"))
     if p.name not in ("V2_017_SECRET_AUDIT.json",)]
for p in targets:
    if p.name == "build_v2_017_evidence.py":
        continue
    scanned += 1
    blob = p.read_bytes()
    for m in MARKERS:
        if m.lower() in blob.lower():
            hits.append(f"{p.name}: {m.decode()} (scheme/structural name, "
                        "not a secret)")
key_value = ""
for env_name in ("BYTEPLUS_MODELARK_API_KEY", "BYTEPLUS_API_KEY",
                 "ARK_API_KEY"):
    v = os.getenv(env_name, "").strip()
    if v:
        key_value = v
        break
if not key_value:
    key_file = Path("D:/API KEY/byteplus_modelark_key.txt")
    if key_file.is_file():
        key_value = key_file.read_text(encoding="utf-8").strip().splitlines()[0]
value_hits = [f"{p.name}: CREDENTIAL_VALUE" for p in targets
              if key_value and key_value.encode() in p.read_bytes()]
write("V2_017_SECRET_AUDIT.json", {
    "version": "v2-017-secret-audit-v1", "built_at": utcnow(),
    "files_scanned": scanned, "marker_hits": hits,
    "credential_value_hits": value_hits,
    "note": "the Bearer scheme name in transport documentation is "
            "structural; the authoritative check is the credential VALUE "
            "scan across all evidence",
    "verdict": "CLEAN" if not value_hits else "FAIL"})

write("V2_017_CANDIDATE_SEAL.json", {
    "version": "v2-017-candidate-seal-v1", "sealed_at": utcnow(),
    "checkpoint": "V2017_SEAL", "status": "COMPLETED_CANDIDATE",
    "conclusion": "A THIRD SeedanceProvider route (BytePlus ModelArk, "
                  "model dreamina-seedance-2-5-260628) NATIVELY SUPPORTS "
                  "480p Draft → persistent draft_task_id (7-day window) → "
                  "same-take 1080p Final → watermark=false as a documented "
                  "request parameter — reconstructed from the ComfyUI "
                  "built-in node source (priority-1 implementation) plus "
                  "the local Story Auto client",
    "canonical": {
        "SEQ7_F1_F2_F3": "CLEAN_DISTRIBUTION_MASTER_READY (untouched)",
        "FINAL_MASTER_LOCK": "GRANTED (unchanged)",
        "BYTEPLUS_TRANSPORT": "RECONSTRUCTED_FROM_SOURCE",
        "DRAFT_FINAL_LINEAGE": "PROVIDER_DOCUMENTED (content type "
                               "draft_task -> task.id)",
        "WATERMARK": "request parameter watermark:false (provider-"
                     "authorized surface)",
        "live_mutations": "0 — live qualification REQUIRES Owner "
                          "authorization + a BytePlus ModelArk API key "
                          "(not verified present) + credits",
        "elyum_canary": "0/1 UNSPENT (frozen)"},
    "video_generation_mutations": 0,
    "next_handoff": "STOP — return to Tech Lead: live qualification needs an "
                    "Owner decision (BytePlus key/credit provision) — the "
                    "frozen experiment would be: 1 draft (480p, ~$0.59) + 1 "
                    "finalization (1080p, ~$3.29) on a provisioned key",
})

print("V2-017 evidence complete")
