"""V2-014 Phase 0 — Elyum source authority record."""
import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PKG = ROOT / "projects/quality_v2_014_elyum_clean_route"
SA = Path("D:/Story Auto/story-auto")


def utcnow():
    return datetime.now(timezone.utc).isoformat()


def main():
    PKG.mkdir(parents=True, exist_ok=True)
    (PKG / "outputs").mkdir(exist_ok=True)
    (PKG / "owner_review_014").mkdir(exist_ok=True)
    commit = subprocess.run(["git", "rev-parse", "--short", "HEAD"], cwd=SA,
                            capture_output=True, text=True).stdout.strip()
    write = PKG / "V2_014_ELYUM_SOURCE_AUTHORITY.json"
    doc = {
        "version": "v2-014-elyum-source-authority-v1",
        "checkpoint": "V2014_P0_SOURCE_AUTHORITY",
        "recorded_at": utcnow(),
        "source": {
            "repo": "D:/Story Auto/story-auto",
            "commit": commit,
            "paths": [
                "story_auto/providers/elyum_seedance/client.py (426 lines)",
                "story_auto/providers/elyum_seedance/service.py (752 lines)",
                "story_auto/providers/elyum_seedance/__init__.py",
                "story_auto/providers/elyum_seedance/research.py (267 lines)",
                "story_auto/providers/elyum_seedance/opening.py (383 lines)",
            ],
            "live_proof_lineage": "R1 g_e2fa8c99… · X2 KEEP g_d59e88f0… (20 "
                                  "credits) · X3 preview g_a18de93d… sha "
                                  "8c9163… · UAT g_f62ed089… preview sha "
                                  "a8c72a65… (V2-009 Seedance audit)",
        },
        "provider_contract_recorded_in_client_docstring": [
            "elyum_upload — imports local/public reference media; documented free",
            "elyum_estimate — quotes held Credits WITHOUT generation",
            "elyum_make_video — creates ONE job, idempotent clientRef",
            "elyum_wait / elyum_job_status — observe the same durable jobId",
            "elyum_keep — the only action documented to spend Credits (unlocks the original)",
            "elyum_kill — releases a hold, consumes kill allowance",
            "No browser/session automation exists in this boundary",
        ],
        "key_shapes": {
            "endpoint": "https://elyum.ai/mcp (MCP streamable HTTP, protocol 2025-06-18, Bearer auth)",
            "make_video_args": "clientRef(<=120), mode, model, prompt, "
                               "duration(2..30), aspectRatio, resolution, "
                               "audio, imageUrl/imageUrls(<=6)",
            "resolution_set": ["480p", "720p", "1080p"],
            "video_modes": ["ugc", "i2v", "t2v", "clone", "captions", "edit", "extend"],
            "result_keys": "jobid/job_id, genid/gen_id, status/state, "
                           "unlockcredits, url/download/file/video fields",
            "lifecycle": "make_video holds -> keep(genId) spends credits and "
                         "unlocks the downloadable original; kill releases",
        },
        "reuse_classification": {
            "REUSE_VERBATIM": [
                "McpToolSession (JSON-RPC + SSE decode, session id, initialize handshake, Bearer headers, failure classes CREDENTIAL_OR_ACCESS_DENIED/RATE_LIMITED/CAPABILITY_OR_REQUEST_INVALID/PROVIDER_TRANSIENT)",
                "ElyumSeedanceClient tool semantics: account_balance, model_catalog, seedance_model_ids, estimate_video, make_video (validation + idempotent replay class), wait, job_status, gen_id, execution_state, preview_urls, unlock_credits, downloadable_urls, keep, kill",
                "_find_first / _collect_urls resilient extraction",
                "ElyumSeedanceError failure-class taxonomy",
            ],
            "ADAPT_TO_VIDEOPROVIDER": [
                "credential loader (Story Auto DPAPI pool -> AI-Film loader: env ELYUM_API_KEY then the Owner key file D:/API KEY/elyum_api_key.txt; value never logged/persisted)",
                "clientRef builder (hash-of-identity, prefix aifilm-v2-014-)",
                "submit/poll/fetch_outputs mapping onto the AI-Film "
                "VideoProvider Protocol (capabilities/preflight/submit/poll/"
                "fetch_outputs)",
                "download to local asset + sha256 binding",
            ],
            "STORY_AUTO_SPECIFIC_DO_NOT_PORT": [
                "service.py production gating (Full Video provider capability "
                "contract, project RuntimeLayout, artifact manifest layout)",
                "opening.py (Story Auto opening-builder flows)",
                "research.py (Goal-54 research helper)",
                "Story Auto project/asset validation (story_auto.core paths)",
            ],
        },
        "do_not_assume": "absence of watermark code in the adapter does NOT "
                         "imply clean output — the watermark verdict comes "
                         "only from the rendered canary asset (Phase 8)",
    }
    write.write_text(json.dumps(doc, indent=1, ensure_ascii=False),
                     encoding="utf-8")
    print("wrote", write)


if __name__ == "__main__":
    main()
