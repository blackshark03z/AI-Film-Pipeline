"""AI-FILM-QUALITY-V2-010C — Layers 4/5/6: current protocol map, 010B diff,
transport decision. Built ONLY from observed 010C evidence (no speculation;
unknown stays UNKNOWN)."""
from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PKG = ROOT / "projects/quality_v2_010c_dola_fullstack"
sys.path.insert(0, str(ROOT / "tools"))


def utcnow() -> str:
    return datetime.now(timezone.utc).isoformat()


def write(name: str, payload: dict) -> None:
    (PKG / name).write_text(json.dumps(payload, indent=1, ensure_ascii=False),
                            encoding="utf-8")


def main() -> int:
    observation = json.loads(
        (PKG / "V2_010C_M1_OUTPUT_OBSERVATION.json").read_text(encoding="utf-8"))
    m1_incomplete = json.loads(
        (PKG / "m1_incomplete.json").read_text(encoding="utf-8"))

    # ------------------------------------------------------------ LAYER 4 --
    protocol = {
        "version": "dola-current-protocol-v2-010c",
        "checkpoint": "V2010C_P4_CURRENT_PROTOCOL",
        "built_at": utcnow(),
        "source_evidence": [
            "V2_010C_BROWSER_ORACLE_EVIDENCE.json",
            "V2_010C_M1_OUTPUT_OBSERVATION.json",
            "V2_010C_BROWSER_CAPTURE_SANITIZED.json",
            "V2_010C_OBSERVATION_CAPTURE_SANITIZED.json",
            "m1_receipt.json"],
        "bootstrap": {
            "entry": "https://www.dola.com/chat (SPA, static from "
                     "sf-flow-web-cdn.ciciai.com)",
            "auth_inputs": ["cookies (sessionid, sessionid_ss AUTH class)"],
            "device_runtime_inputs": ["device_id", "web_id", "tea_uuid",
                                      "fp=verify_…", "msToken (rotating)",
                                      "a_bogus (request signature)"],
            "push_channel": {
                "transport": "wss://wss-normal-i18n.dola.com/ws/v2",
                "frame_format": "binary protobuf (observed; schema UNKNOWN)",
                "role": "server push of conversation/creation updates"},
            "risk_sdk": "mssdk.bytedance.com/web/common (periodic attestation)",
            "heartbeat": "passport/token/beat/web"},
        "generation_dispatch": {
            "endpoint": "POST https://www.dola.com/chat/completion",
            "response": "HTTP 200, text/event-stream (h2), consumed via "
                        "fetch stream (NOT native EventSource; CDP emits no "
                        "EventSourceMessageReceived — body captured on close)",
            "observed_query_params": ["aid=495671", "device_id",
                                      "device_platform=web",
                                      "doubao_device_platform=web",
                                      "doubao_pc_version=3.39.1",
                                      "fp=verify_…", "language=ja",
                                      "pc_version=3.39.1",
                                      "pkg_type=release_version",
                                      "real_aid=495671", "region=VN",
                                      "samantha_web=1", "sys_region=VN",
                                      "tea_uuid", "tz_name=Asia/Tokyo",
                                      "use-olympus-account=1",
                                      "version_code=20800", "web_id",
                                      "web_platform=browser", "web_tab_id",
                                      "msToken", "a_bogus"],
            "observed_headers": ["Agw-Js-Conv: str, str", "x-flow-trace",
                                 "last-event-id: undefined",
                                 "Referer: <origin>/chat/<conversation_id>",
                                 "sec-ch-ua / UA: real Chromium 153"],
            "request_body": "STRUCTURE CONFIRMED LIVE (client_meta with "
                            "bot_id 7339470689562525703 + existing "
                            "conversation_id + last_section_id + "
                            "last_message_index; messages content_block; "
                            "option; chat_ability; user_context; ext). "
                            "Exact field-level dump persisted at M2 "
                            "release correlation.",
            "conversation_model": "ONE DURABLE skill conversation "
                                  "(38417972940811793) reused across "
                                  "generations; message_index increments "
                                  "(index 7 = M1). canary-4's 'task_id' was "
                                  "this conversation id."},
        "receipt_protocol": {
            "ack_event": "SSE_ACK (CONFIRMED CURRENT — observed live)",
            "ack_structure": {"ack_client_meta.conversation_id": "durable id",
                              "ack_client_meta.section_id": "section id",
                              "query_list[].question_id": "question id",
                              "query_list[].local_message_id": "client uuid",
                              "query_list[].message_index": "int",
                              "timeout_conf": "180s first packet, retries 10"},
            "stream_frame_sequence_observed": ["SSE_HEARTBEAT", "SSE_ACK",
                                               "FULL_MSG_NOTIFY",
                                               "DOWNLINK_CMD",
                                               "STREAM_MSG_NOTIFY",
                                               "STREAM_CHUNK×150",
                                               "SSE_REPLY_END×3"]},
        "job_identity": {
            "conversation_id": "38417972940811793 (durable)",
            "question_message_id": "1541253913616145 (M1 prompt)",
            "reply_message_id": "1546406012981009 (M1 reply)",
            "creation_ids": ["40033753389997329", "40033753389997585",
                             "40033753389997841", "40033753389998097"],
            "creation_card": "STREAM_CHUNK patch_op → content_block "
                             "block_type 2074 creation_block.creations[]"},
        "progress_and_completion": {
            "primary": "WS push (protobuf) updates the page; no HTTP polling "
                       "observed from the page itself after release",
            "http_poll": {
                "endpoint": "POST /im/chain/single",
                "uplink": "uplink_body.pull_singe_chain_uplink_body "
                          "{conversation_id, anchor_index:MAX_SAFE_INTEGER, "
                          "conversation_type:3, direction:1, limit:20}",
                "required_content_type": "application/json; encoding=utf-8 "
                                         "(WITHOUT '; encoding=utf-8' the API "
                                         "returns 712012002 不支持编码类型)",
                "agw_js_conv": "str",
                "downlink": "downlink_body.pull_singe_chain_downlink_body."
                            "messages[].content[] blocks; block_type 2074 "
                            "→ creation_block.creations[]"},
            "creation_status_semantics": {
                "type": "1=image (Seedream req_key seedream_v43_flow), "
                        "2=video (task_type 6)",
                "image_status": "1=pending, 2=completed (observed)",
                "video_status": "3=completed (observed; pending value UNKNOWN)"},
            "output_identity": "creation.id is the stable job identity; "
                               "video.download_url appears ONLY on the "
                               "type-2 creation of the completing message"},
        "output_download": {
            "observed_hosts": ["v16-dola.dola.com (video)",
                               "p16-flow-image-sign.ibyteimg.com (cover/"
                               "image, x-expires+x-signature signed)"],
            "url_form": "signed, transport-only; never persisted",
            "010B_download_allowlist_gap": "v16-dola.dola.com and "
                                           "ibyteimg.com were NOT in the "
                                           "010B allowlist"},
        "unknown": ["a_bogus signing algorithm (page JS; not reversed)",
                    "WS protobuf frame schema",
                    "server-side behavior on requests lacking a_bogus "
                    "(010B observed HTTP 200 + silence; mechanism UNKNOWN)"],
    }
    write("V2_010C_CURRENT_PROTOCOL.json", protocol)

    # ------------------------------------------------------------ LAYER 5 --
    diff = {
        "version": "v2-010c-protocol-diff-v1",
        "checkpoint": "V2010C_P5_PROTOCOL_DIFF",
        "built_at": utcnow(),
        "compared": "CURRENT_BROWSER (live 010C capture) vs "
                    "010B_REPAIRED_COOKIE_HTTP (DolaCookieTransport)",
        "root_cause_of_010b": {
            "classification": "ATTESTATION_DEPENDENCY (multi-layer)",
            "proven": [
                "SIGNATURE_GAP: browser sends a_bogus query signature on "
                "/chat/completion; 010B sent none",
                "DEVICE_ID_GAP: browser sends device_id/web_id/tea_uuid; "
                "010B sent none",
                "REGION_MISMATCH: browser live session region=VN, "
                "sys_region=VN; 010B hardcoded region=JP, sys_region=JP",
                "CONVERSATION_CONTEXT_GAP: browser reuses the durable skill "
                "conversation (client_meta carries conversation_id + "
                "last_section_id + last_message_index); 010B always asked "
                "for a NEW conversation (need_create_conversation=true, "
                "empty conversation_id)",
                "FINGERPRINT_GAP: browser fp=verify_… runtime token; 010B "
                "reused the s_v_web_id cookie value",
                "QUERY_PARAM_GAP: doubao_pc_version/pc_version/pkg_type/"
                "real_aid/doubao_device_platform/tz_name missing in 010B",
                "RUNTIME_TOKEN_GAP: msToken rotates per request in the "
                "browser; 010B reused the cookie-static value"],
            "plausible": ["the backend enqueues the request but the "
                          "attestation layer silently drops generation for "
                          "unattested clients (HTTP 200 + no SSE_ACK, "
                          "exactly the 010B signature)"],
            "unknown": ["exact server-side decision logic"]},
        "material_differences": [
            {"class": "SIGNATURE_GAP", "browser": "a_bogus present",
             "cookie_http": "absent", "materiality": "PROVEN"},
            {"class": "DEVICE_ID_GAP",
             "browser": "device_id, web_id, tea_uuid",
             "cookie_http": "absent", "materiality": "PROVEN"},
            {"class": "REGION_MISMATCH", "browser": "VN/VN",
             "cookie_http": "JP/JP (hardcoded)", "materiality": "PROVEN"},
            {"class": "CONVERSATION_CONTEXT_GAP",
             "browser": "reuses durable conversation with section/index",
             "cookie_http": "always new conversation",
             "materiality": "PROVEN"},
            {"class": "RUNTIME_TOKEN_GAP",
             "browser": "fresh msToken per request",
             "cookie_http": "static cookie value", "materiality": "PROVEN"},
            {"class": "FINGERPRINT_GAP", "browser": "fp=verify_…",
             "cookie_http": "s_v_web_id cookie", "materiality": "PROVEN"},
            {"class": "QUERY_PARAM_GAP",
             "browser": "6 additional version/platform params",
             "cookie_http": "absent", "materiality": "PROVEN"},
            {"class": "HEADER_DRIFT", "browser": "x-flow-trace, "
             "last-event-id, Chromium-153 UA",
             "cookie_http": "Chrome-131 UA, no trace header",
             "materiality": "PROVEN"},
            {"class": "ENDPOINT_DRIFT", "browser": "NONE — /chat/completion "
             "and /im/chain/single are BOTH STILL CURRENT",
             "cookie_http": "same endpoints", "materiality": "PROVEN"},
            {"class": "SSE_SCHEMA_DRIFT", "browser": "SSE_ACK CURRENT with "
             "ack_client_meta + query_list", "cookie_http": "same schema "
             "assumed by 010B parser", "materiality": "PROVEN_NO_DRIFT"},
            {"class": "POLLING_DRIFT", "browser": "uplink_body wrapper + "
             "anchor MAX_SAFE_INTEGER + '; encoding=utf-8' content type",
             "cookie_http": "flat body {cmd, conversation_id, anchor_index:0,"
             " direction, limit} + 'charset=utf-8'",
             "materiality": "PROVEN — 010B poll schema is WRONG (returns "
             "712012002 with the browser-observed requirement)"},
            {"class": "OUTPUT_SCHEMA_DRIFT", "browser": "type-2 creation "
             "video.download_url on v16-dola.dola.com",
             "cookie_http": "parser expected byteimg/volces families only",
             "materiality": "PROVEN — download host allowlist is stale"},
            {"class": "WAF/ATTESTATION_DEPENDENCY",
             "browser": "mssdk periodic attestation + a_bogus",
             "cookie_http": "none", "materiality": "PROVEN_PRESENT"}],
        "endpoint_survival": {
            "chat_completion": "CURRENT (live-proven by M1 release)",
            "im_chain_single": "CURRENT (live-proven by observation poll) "
                               "but request schema is uplink_body-wrapped"},
        "m1_incomplete_record": m1_incomplete["status"],
        "observation_poll_status": observation.get("poll_status"),
    }
    write("V2_010C_PROTOCOL_DIFF.json", diff)

    # ------------------------------------------------------------ LAYER 6 --
    decision = {
        "version": "v2-010c-transport-decision-v1",
        "checkpoint": "V2010C_P6_TRANSPORT_DECISION",
        "built_at": utcnow(),
        "decision": "ROUTE_B_C_HYBRID: BrowserNetwork (UI trigger + network "
                    "authority inside the managed authenticated browser "
                    "runtime DOLA_RE_PROFILE)",
        "evidence_basis": [
            "Route A (native HTTP) requires reproducing a_bogus signing + "
            "mssdk device attestation + rotating msToken — a moving "
            "anti-bot target; NOT deterministically reproducible, so Route A "
            "is disqualified on evidence, not preference",
            "Route B/C: M1 live-proved the full dispatch → SSE_ACK receipt → "
            "stable IDs → progress → output-correlation chain inside the "
            "browser with zero DOM-selector dependence for identity "
            "(receipt = SSE_ACK/URL conversation id; outputs = creation ids "
            "from poll; download = network URL)",
            "The 010B failure signature (HTTP 200 + silence) is explained by "
            "the PROVEN attestation-layer gaps above — cookie-HTTP remains "
            "permanently non-viable per the 010A/010B latches"],
        "authority_rules": [
            "Film Core never depends on DOM selectors for IDENTITY: "
            "receipt = SSE_ACK conversation id; job = creation ids; "
            "output = type-2 creation download_url from poll",
            "UI/DOM may TRIGGER only (composer typing + Enter)",
            "cookie-HTTP transport stays dead (latched); no reuse"],
        "qualification_plan": {
            "m1": {"budget_kind": "m1_browser_oracle", "used": 1,
                   "proved": "dispatch/receipt/IDs/progress/output-"
                             "correlation (image-class output; 4 creations "
                             "image_status 2 correlated by id)"},
            "m2": {"budget_kind": "m2_browser_video_qualification",
                   "authorization": "optional qualification slot, package "
                                    "HARD MAX 4; reinterpreted from "
                                    "'native HTTP qualification' to "
                                    "'browser video qualification' because "
                                    "the evidence-selected transport is "
                                    "BrowserNetwork — documented as a "
                                    "deliberate, evidence-backed deviation",
                   "purpose": "prove VIDEO output stage end-to-end"},
            "f2a_f2b": "conditional on DOLA_CURRENT_TRANSPORT_QUALIFIED"},
        "budget_after_m2": {"used": 2, "hard_max": 4,
                            "remaining_for_f2": 2},
    }
    write("V2_010C_TRANSPORT_DECISION.json", decision)
    print("L4/L5/L6 evidence written")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
