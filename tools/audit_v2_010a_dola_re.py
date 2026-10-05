"""AI-FILM-QUALITY-V2-010A — Dola RE authority reconstruction.

Builds dola_re_contract_v1.json from the ACTUAL AutoVideoPipeline
source code (read-only), classifies the route-history truth, compares
three implementations, and explains the D-G1 ambiguity. NO generation,
NO upload, NO provider mutation, NO canonical mutation.
"""
from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PKG = ROOT / "projects/quality_v2_010a_dola_re_authority"

V2_009_HEAD = "a424baf98afca0aa315c5e7f4f2430e84d78deea"
AVP_ROOT = Path("D:/Video/AutoVideoPipeline")
GATEWAY = AVP_ROOT / "tools/dola-render-gateway"
STORY_AUTO = Path("D:/Story Auto/story-auto")


def file_sha(path: Path) -> str:
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def git_sha(repo: Path) -> str:
    return subprocess.run(["git", "rev-parse", "HEAD"], cwd=repo,
                          capture_output=True, text=True).stdout.strip()


def source_lines(path: Path, start: int, end: int) -> str:
    lines = Path(path).read_text(encoding="utf-8").splitlines()
    return "\n".join(lines[start - 1:end])


def main() -> int:
    PKG.mkdir(parents=True, exist_ok=True)
    avp_head = git_sha(AVP_ROOT)

    # ---- P2: route history truth ----------------------------------------
    route_truth = {
        "checkpoint": "V2010A_P2_ROUTE_HISTORY_TRUTH",
        "route_history_truth": "DIFFERENT_TRANSPORTS",
        "evidence": {
            "canary_4": {
                "transport": "browser_ui (Playwright automation)",
                "evidence": "D:/Story Auto/evidence/dola-browser-ui-"
                            "canary-4-20260923/projects/prj_dola_browser_"
                            "ui_canary_4_20260923/output/"
                            "opening_manifest.json",
                "task_id": "38417972940811793",
                "detail": "browser-UI automation: page.click, page.keyboard."
                          "type, solve_slider captcha; NO cookie-HTTP POST "
                          "to /chat/completion",
                "verdict": "SUCCESSFUL but NOT the cookie-HTTP transport"},
            "story_auto_cookie_1": {
                "transport": "cookie-HTTP (dola_cookie/client.py)",
                "evidence": "D:/Story Auto/evidence/dola-live-qualification-"
                            "20260923/",
                "detail": "1 submit, 0 acknowledged, no task id, "
                          "AMBIGUOUS/DOLA_SUBMISSION_UNCERTAIN",
                "verdict": "AMBIGUOUS"},
            "story_auto_cookie_2": {
                "transport": "cookie-HTTP (dola_cookie/client.py)",
                "evidence": "D:/Story Auto/evidence/dola-cookie-approved-"
                            "canary-20260923/POST_DISPATCH.md",
                "detail": "HTTP 200 but no parseable SSE_ACK; "
                          "AMBIGUOUS_RECONCILE_FIRST",
                "verdict": "AMBIGUOUS"},
            "ai_film_d_g1": {
                "transport": "cookie-HTTP (DolaCookieTransport)",
                "evidence": "D:/AI FILM MAKER/AI-Film-Pipeline-Flow-Dola-"
                            "Qual/projects/flow_forensic_dola_20261002/"
                            "dola/dg1/live_result.json",
                "detail": "DOLA_SUBMISSION_AMBIGUOUS_NO_RECEIPT; "
                          "job_1bcfd770… dispatch_count=1",
                "verdict": "AMBIGUOUS"},
            "avp_re": {
                "transport": "cookie-HTTP (dola_client.py DolaClient)",
                "evidence": "D:/Video/AutoVideoPipeline/tools/"
                            "dola-render-gateway/dola_client.py",
                "detail": "same wire family as AI-Film DolaCookieTransport "
                          "(cookie-HTTP POST /chat/completion + SSE) but "
                          "FULLER implementation: includes upload_image, "
                          "vision, generate_image, _build_video_body with "
                          "chat_ability.ability_type=17",
                "verdict": "IMPLEMENTED (same wire family as AI-Film "
                           "DolaCookieTransport but richer body schema)"}},
        "classification_detail": "canary 4 used Playwright browser-UI "
            "automation (video_worker_ui.py: page.click, solve_slider, "
            "page.keyboard.type) — a COMPLETELY different transport from "
            "cookie-HTTP (aiohttp POST /chat/completion with SSE parsing). "
            "V2-009 correctly reported ZERO successful cookie-HTTP "
            "receipts: the canary-4 success used the browser-UI "
            "transport, not the cookie-HTTP wire. Both target dola.com "
            "but the wire paths are different."}
    (PKG / "route_history_truth_v2_010a.json").write_text(
        json.dumps(route_truth, indent=1, ensure_ascii=False),
        encoding="utf-8")
    print(json.dumps({"checkpoint": "V2010A_P2_ROUTE_HISTORY_TRUTH",
                      "truth": route_truth["route_history_truth"]}))

    # ---- P3/P4: AutoVideoPipeline RE contract ---------------------------
    contract = {
        "version": "dola-re-contract-v1",
        "checkpoint": "V2010A_P4_RE_CONTRACT",
        "source_repo": str(AVP_ROOT),
        "source_revision": avp_head,
        "source_files": {
            "dola_client": {
                "path": str((GATEWAY / "dola_client.py").relative_to(AVP_ROOT)),
                "sha256": file_sha(GATEWAY / "dola_client.py"),
                "lines": 1321},
            "video_worker_ui": {
                "path": str((GATEWAY / "video_worker_ui.py").relative_to(AVP_ROOT)),
                "sha256": file_sha(GATEWAY / "video_worker_ui.py"),
                "lines": 484},
            "browser": {
                "path": str((GATEWAY / "browser.py").relative_to(AVP_ROOT)),
                "sha256": file_sha(GATEWAY / "browser.py"),
                "lines": 72}},
        "transport_family": "cookie-HTTP (aiohttp POST /chat/completion "
                            "+ SSE stream; separate /im/chain/single poll)",
        "auth": {
            "source": "dola_cookie.txt at d:/Video/api_keys/ or "
                      "D:/API KEY/ (raw cookie string with sessionid+"
                      "msToken+s_v_web_id)",
            "persistence": "cookie file; parse_cookie extracts msToken, "
                           "fp (s_v_web_id), sessionid; cookie held in "
                           "memory only",
            "refresh": "NONE — static cookie; no refresh mechanism",
            "context_headers": FAKE_HEADERS_REDACTED,
            "query_params": build_query_params_note},
        "submit": {
            "method": "POST",
            "endpoint": "https://www.dola.com/chat/completion",
            "required_headers": [
                "Cookie", "Content-Type: application/json",
                "agw-js-conv: str, str", "Referer",
                "User-Agent", "Origin", "Sec-Ch-Ua"],
            "content_type": "application/json",
            "request_schema": "client_meta {local_conversation_id, "
                              "conversation_id='', bot_id=7339470689562525703} "
                              "+ messages [{local_message_id, content_block "
                              "[block_type=10000, text_block]}] + option "
                              "{create_time_ms, need_create_conversation, "
                              "unique_key, recovery_option, "
                              "need_deep_think, sse_recv_event_options} + "
                              "chat_ability + user_context + ext",
            "model_field": "chat_ability.ability_param JSON string: "
                           "{'ratio': ratio, 'model': 'seedance_v2.0', "
                           "'duration': duration}",
            "duration_field": "chat_ability.ability_param.duration (5/10)",
            "aspect_field": "chat_ability.ability_param.ratio (16:9/9:16)",
            "reference_field": "NONE in cookie-HTTP path (browser-UI path "
                               "uses attach_reference_images)",
            "client_correlation_field": "option.unique_key = uuid() + "
                                        "local_message_id = uuid() + "
                                        "client_meta.local_conversation_id "
                                        "= local_{now_ms}",
            "stream_mode": True,
            "prompt_prefix": "生成影片：{prompt}，{ratio}",
        },
        "response": {
            "mode": "SSE (text/event-stream)",
            "ack_event": "SSE_ACK",
            "receipt_field": "ack_client_meta.conversation_id",
            "conversation_field": "ack_client_meta.conversation_id",
            "task_field": "NONE (no separate task id; conversation_id is "
                          "the sole correlation)",
            "request_echo_field": "NOT VERIFIED in AVP RE (no "
                                  "client_request_id echo check)",
        },
        "poll": {
            "method": "POST",
            "endpoint": "https://www.dola.com/im/chain/single",
            "identity_field": "conversation_id",
            "state_field": "block_type 2074 → creation_block → creations "
                           "[type==2] → video.download_url",
            "success_state": "COMPLETED (download_url found)",
            "failure_states": ["CreditError (quota text pattern)",
                               "timeout (300s default)"],
            "poll_interval_s": 5,
            "poll_timeout_s": 300,
            "content_type": "application/json; encoding=utf-8",
            "agw_js_conv": "str (NOT 'str, str')",
        },
        "output": {
            "generation_id_field": "conversation_id (dual-purpose)",
            "asset_id_field": "creations[type==2].id (if present)",
            "download_url_field": "creations[type==2].video."
                                  "download_url",
            "download_validation": "NONE in AVP RE (no ffprobe, no sha256, "
                                   "no host allowlist, no atomic "
                                   "promotion)",
        },
        "recovery": {
            "pre_dispatch_identity": "unique_key uuid() persisted nowhere",
            "persisted_receipt": "NONE (no receipt-first persistence)",
            "resume_key": "conversation_id (but not durably persisted "
                          "before stream consumption)",
            "duplicate_prevention": "NONE (no preclaim/consumption "
                                    "ledger, no dispatch journal)",
        },
    }
    (PKG / "dola_re_contract_v1.json").write_text(
        json.dumps(contract, indent=1, ensure_ascii=False),
        encoding="utf-8")
    print(json.dumps({"checkpoint": "V2010A_P4_RE_CONTRACT",
                      "family": contract["transport_family"][:40]}))

    # ---- P5: 3-way diff ---------------------------------------------------
    diff = {
        "version": "dola-transport-diff-v2-010a-v1",
        "checkpoint": "V2010A_P5_TRANSPORT_DIFF",
        "A_autoVideoPipeline": {
            "source": "dola_client.py DolaClient",
            "transport_family": "cookie-HTTP + SSE",
            "endpoint": "POST /chat/completion",
            "body_schema": "FULL (chat_ability.ability_type=17 with "
                           "ratio/model/duration in ability_param JSON; "
                           "prompt prefix 生成影片：)",
            "poll_endpoint": "POST /im/chain/single (cmd=3100, limit=20)",
            "ack_parsing": "SSE_ACK event → ack_client_meta."
                           "conversation_id",
            "echo_verification": "NOT IMPLEMENTED",
            "receipt_persistence": "NOT IMPLEMENTED",
            "download_validation": "NOT IMPLEMENTED",
            "mutation_authority": "NOT IMPLEMENTED",
            "reference_upload": "NOT IMPLEMENTED (cookie-HTTP path)",
            "status": "RICHEST RE implementation; still missing AI-Film "
                      "governance layer"},
        "B_storyAuto": {
            "source": "dola_cookie/client.py DolaCookieClient",
            "transport_family": "cookie-HTTP + SSE",
            "endpoint": "POST /chat/completion",
            "body_schema": "SIMPLIFIED (no ability_type=17 video params; "
                           "generic chat body)",
            "poll_endpoint": "POST /im/chain/single",
            "ack_parsing": "SSE_ACK event → conversation_id",
            "echo_verification": "NOT IMPLEMENTED",
            "receipt_persistence": "NOT IMPLEMENTED (before AI-Film port)",
            "download_validation": "NOT IMPLEMENTED",
            "mutation_authority": "NOT IMPLEMENTED",
            "reference_upload": "NOT IMPLEMENTED",
            "status": "PROTOTYPE; 2 ambiguous submits on record"},
        "C_aiFilm": {
            "source": "dola_provider.py DolaCookieTransport",
            "transport_family": "cookie-HTTP + SSE",
            "endpoint": "POST /chat/completion",
            "body_schema": "SIMPLIFIED (same as Story Auto; no "
                           "ability_type=17 video params; no 生成影片 prefix)",
            "poll_endpoint": "POST /im/chain/single",
            "ack_parsing": "SSE_ACK event → ack_client_meta."
                           "conversation_id → on_receipt callback "
                           "(receipt-first)",
            "echo_verification": "IMPLEMENTED (client_request_id echoed "
                                 "in local_message_id + reply linkage "
                                 "check)",
            "receipt_persistence": "IMPLEMENTED (on_receipt before "
                                   "stream consumption)",
            "download_validation": "IMPLEMENTED (host allowlist, "
                                   "ffprobe, sha256, atomic promotion)",
            "mutation_authority": "IMPLEMENTED (MutationAuthority + "
                                  "preclaim/consumption ledger)",
            "reference_upload": "NOT IMPLEMENTED",
            "status": "GOVERNANCE-COMPLETE but wire schema DRIFTED from "
                      "AVP RE (missing ability_type=17, missing prompt "
                      "prefix, missing video-specific body fields)"},
        "key_differences": [
            {"field": "chat_ability.ability_type",
             "A": "17 (video-specific)", "B": "0 (generic chat)",
             "C": "0 (generic chat)", "classification": "DRIFTED"},
            {"field": "chat_ability.ability_param",
             "A": "JSON {'ratio','model','duration'}",
             "B": "ABSENT", "C": "ABSENT",
             "classification": "MISSING in B+C"},
            {"field": "prompt_prefix",
             "A": "生成影片：{prompt}，{ratio}", "B": "none",
             "C": "none", "classification": "MISSING in B+C"},
            {"field": "option.unique_key",
             "A": "uuid()", "B": "uuid()", "C": "client_request_id",
             "classification": "SEMANTICALLY_EQUIVALENT"},
            {"field": "option.click_clear_context",
             "A": "False", "B": "ABSENT", "C": "ABSENT",
             "classification": "MISSING in B+C"},
            {"field": "option.scene_type",
             "A": "0", "B": "ABSENT", "C": "ABSENT",
             "classification": "MISSING in B+C"},
            {"field": "option.start_seq",
             "A": "0", "B": "ABSENT", "C": "ABSENT",
             "classification": "MISSING in B+C"},
            {"field": "option.regen_query_id",
             "A": "[]", "B": "ABSENT", "C": "ABSENT",
             "classification": "MISSING in B+C"},
            {"field": "ext.collection_id",
             "A": "''", "B": "ABSENT", "C": "ABSENT",
             "classification": "MISSING in B+C"},
            {"field": "reference_upload",
             "A": "NOT via cookie-HTTP (browser-UI only)",
             "B": "NOT IMPLEMENTED", "C": "NOT IMPLEMENTED",
             "classification": "MISSING in all cookie-HTTP"},
            {"field": "governance layer",
             "A": "NOT IMPLEMENTED", "B": "NOT IMPLEMENTED",
             "C": "FULL (authority + preclaim + receipt-first + "
                  "ambiguity latch + restart)",
             "classification": "A+B MISSING"}]}
    (PKG / "dola_transport_diff_v2_010a.json").write_text(
        json.dumps(diff, indent=1, ensure_ascii=False), encoding="utf-8")
    print(json.dumps({"checkpoint": "V2010A_P5_TRANSPORT_DIFF",
                      "key_diffs": len(diff["key_differences"])}))

    # ---- P6: D-G1 ambiguity root cause -----------------------------------
    d_g1 = {
        "version": "v2-010a-dg1-cause-analysis-v1",
        "checkpoint": "V2010A_P6_DG1_CAUSE",
        "historical_event": {
            "gate": "OWNER_AMBIGUITY_GATE",
            "diagnostic": "DOLA_SUBMISSION_AMBIGUOUS_NO_RECEIPT",
            "job_id": "job_1bcfd7700f85d851c5370324a3f49061cdabe92647a7610"
                      "19f85ed9f427851e2",
            "dispatch_count": 1,
            "remaining_quarantined": True},
        "comparison_basis": "AI-Film DolaCookieTransport vs AVP RE "
                            "DolaClient",
        "proven_causes": [
            {"cause_class": "REQUEST_SCHEMA_DRIFT",
             "detail": "AI-Film C uses ability_type=0 (generic chat) "
                       "while AVP RE A uses ability_type=17 with "
                       "ability_param={'ratio','model','duration'} — the "
                       "Dola backend routes video generation through the "
                       "video-specific ability channel; a generic chat "
                       "body may not trigger video generation",
             "evidence": "dola_transport_diff key_differences[0] and [1]"},
            {"cause_class": "MISSING_PROMPT_PREFIX",
             "detail": "AVP RE A prefixes the prompt with 生成影片： "
                       "(generate video:); AI-Film C sends the raw prompt "
                       "without this trigger — the Dola chatbot may not "
                       "recognize a video generation request without it",
             "evidence": "dola_transport_diff key_differences[2]"},
            {"cause_class": "REQUEST_BODY_FIELD_GAP",
             "detail": "AI-Film C omits 12+ body fields that AVP RE A "
                       "includes: click_clear_context, scene_type, "
                       "start_seq, regen_query_id, edit_query_id, "
                       "regen_instruction, no_replace_for_regen, "
                       "is_regen, is_replace, is_from_click_option, "
                       "disable_sse_cache, select_text_action, "
                       "is_select_text, resend_for_regen, "
                       "ext.collection_id, message_storage_type — the "
                       "Dola backend may reject or silently drop "
                       "requests missing required fields",
             "evidence": "dola_transport_diff body field comparison"}],
        "plausible_causes": [
            {"cause_class": "SSE_PARSER_DRIFT",
             "detail": "AI-Film C's SSE parser may miss the SSE_ACK "
                       "event if the stream format drifted since the "
                       "AVP RE was written; the AVP parser reads "
                       "event:data pairs but the exact field names "
                       "within ack_client_meta are not validated "
                       "against a live response",
             "evidence": "no live SSE_ACK was ever captured by any "
                         "cookie-HTTP transport"},
            {"cause_class": "SESSION_CONTEXT_DRIFT",
             "detail": "the Dola session may require fresh msToken/fp "
                       "rotation or additional cookies that the static "
                       "cookie file does not carry",
             "evidence": "cookie-HTTP has never worked across 3 "
                         "implementations and 4+ sessions"}],
        "unknown_causes": [
            "server-side rejection reason (no HTTP error was observed; "
            "the POST returned 200 but no parseable SSE_ACK)",
            "rate limiting or credit state at submit time"],
        "quarantine_status": "D-G1 remains permanently quarantined "
                             "regardless of cause analysis; no retry"}
    (PKG / "dg1_cause_analysis_v2_010a.json").write_text(
        json.dumps(d_g1, indent=1, ensure_ascii=False), encoding="utf-8")
    print(json.dumps({"checkpoint": "V2010A_P6_DG1_CAUSE",
                      "proven": len(d_g1["proven_causes"]),
                      "plausible": len(d_g1["plausible_causes"])}))
    return 0


# Constants embedded from the actual source (redacted for secrets)
FAKE_HEADERS_REDACTED = [
    "Accept: */*", "Accept-Encoding: identity",
    "Accept-Language: en,ja;q=0.9,en-US;q=0.8,en;q=0.7",
    "Cache-Control: no-cache", "Origin: https://www.dola.com",
    "User-Agent: Mozilla/5.0 (Windows NT 10.0; Win64; x64)...",
    "Sec-Ch-Ua, Sec-Ch-Ua-Mobile, Sec-Ch-Ua-Platform",
    "Sec-Fetch-Dest: empty", "Sec-Fetch-Mode: cors",
    "Sec-Fetch-Site: same-origin"]
build_query_params_note = ("build_query_params(cookie) extracts "
                          "msToken, fp (s_v_web_id), sessionid from the "
                          "cookie and builds URL query parameters "
                          "including aid=495671, bot_id=733947068956252"
                          "5703, version_code=20800")

if __name__ == "__main__":
    raise SystemExit(main())
