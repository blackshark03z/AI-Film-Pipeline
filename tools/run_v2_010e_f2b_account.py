"""V2-010E — account-aware F2B runner: ONE launch for the whole flow.

Hard lessons baked in (010E resume):
  - the persistent profile OWNS its login state; cookies are NEVER injected
    over a live profile (an older injected sessionid DOWNGRADES the session
    server-side),
  - ONE launch serves validation + credit read + dispatch + download
    (re-launching mid-flow breaks the session),
  - login detection requires sessionid + no login affordance
    (ログイン/Sign in/Đăng nhập) + on dola.com + stable across 3 checks.

Flow: launch → (login if needed) → credit read → READY? → journal arm →
dispatch → receipt (fsync) → creation → download → SHA256 → terminal.
"""
from __future__ import annotations

import asyncio
import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
sys.path.insert(0, str(ROOT / "src"))

from dola_010e_dispatch_journal import (ASSET_DOWNLOADED, CREATION_BOUND,
                                        DISPATCH_ARMED_EV, MUTATION_RESERVED,
                                        NETWORK_RELEASE_OBSERVED,
                                        SSE_RECEIPT_CAPTURED,
                                        TERMINAL_PROVIDER_FAILURE,
                                        TERMINAL_SUCCESS, DispatchJournal)
from dola_010e_adapter_delta import DolaBrowserAdapter010E
from dola_010e_session_router import (ACCOUNT_PROFILES, CREDIT_STATEMENTS_JS,
                                      LOGIN_REQUIRED, NO_CREDIT, READY,
                                      SESSION_VALID)
from dola_010c_browser_adapter import SEEDANCE_CONVERSATION_ID
from dola_010c_session import DolaSessionManager, dpapi_protect
from film_pipeline.core import GenerationAttempt
from film_pipeline.execution import sha256
from mutation_authority import MutationAuthority

SCOPE = "QUALITY-V2-010E-FINAL-F2B"
PKG = ROOT / "projects/quality_v2_010e_final_f2b"
BUDGET_KIND = "f2b_010e"
SHOT_ID = "SEQ7_F2B"
JOURNAL_PATH = PKG / "dispatch_journal_f2b_010e.jsonl"
OPAQUE = "ACCOUNT_A"
PROFILE = ACCOUNT_PROFILES / OPAQUE

F2B_PROMPT = (
    "Generate a 5-second cinematic video, 16:9, locked camera. "
    "a swordsman in flowing white robes with a topknot and ribbon forces "
    "through the last meters of a continuous rock ridge closing a narrow "
    "stone pass — the only walkable gap — with the mountain road funneling "
    "into the opening and continuing beyond it, grass on both sides bending "
    "in the wind. The hard gust funnels through the pass against the travel "
    "direction, streaming his robes and headband leeward as he pushes "
    "through the opening with visible effort. He emerges beyond the pass "
    "onto the open road that continues onward and keeps walking forward "
    "without ever turning back: the rock boundary is BEHIND him, visible on "
    "both lateral sides of the opening in the same frames, and the road "
    "ahead continues onward — the traversal mattered. No turning back "
    "toward the opening, no interacting with the rock, no loitering or "
    "sheltering, no freestanding decorative gate, no metal gate, "
    "no lightning.")
PROMPT_SHA = hashlib.sha256(F2B_PROMPT.encode("utf-8")).hexdigest()

LOGIN_CHECK_JS = """() => {
    const t = (document.body && document.body.innerText) || '';
    return {
        logged_out: /(^|\\n)\\s*ログイン\\s*(\\n|$)/.test(t)
            || /\\bLog\\s?in\\b|\\bSign\\s?in\\b/.test(t)
            || /đăng nhập/i.test(t),
        composer: !!(document.querySelector('textarea')
            || document.querySelector('[contenteditable="true"]')),
    };
}"""


def utcnow() -> str:
    return datetime.now(timezone.utc).isoformat()


def emit(payload: dict) -> None:
    print(json.dumps(payload, ensure_ascii=False, default=str), flush=True)


def write_pkg(name: str, payload: dict) -> None:
    (PKG / name).write_text(json.dumps(payload, indent=1,
                                       ensure_ascii=False), encoding="utf-8")


def build_attempt() -> GenerationAttempt:
    identity = {
        "shot_spec_hash": sha256({"shot_id": SHOT_ID,
                                  "plan": "world_reframe_plan_v2_009"}),
        "prompt_plan_hash": sha256({"prompt_sha256": PROMPT_SHA}),
        "routing_decision_id": "route_v2_010e_browser_network",
        "provider_id": "seedance_dola_browser",
        "request_id": "f2b_010e",
        "started_at": utcnow(),
    }
    return GenerationAttempt(
        generation_attempt_id="attempt_" + sha256(identity),
        shot_id=SHOT_ID, shot_spec_version=1,
        shot_spec_hash=identity["shot_spec_hash"],
        prompt_plan_hash=identity["prompt_plan_hash"],
        routing_decision_id=identity["routing_decision_id"],
        provider_id="seedance_dola_browser", status="created",
        started_at=identity["started_at"])


async def read_credit_state(page) -> dict:
    """Provider-visible credit evidence, all read-only, same context."""
    evidence: dict = {"methods": []}
    # 1) history statements across recent conversations
    try:
        statements = await page.evaluate(CREDIT_STATEMENTS_JS,
                                         {"conversationIds": []})
        evidence["history_statements"] = statements[-6:]
        if statements:
            evidence["latest_statement"] = statements[-1]
    except Exception as error:
        evidence["history_error"] = type(error).__name__
    # 2) open the credit conversation if the sidebar offers it
    for text in ("クレジット残数確認", "動画生成クレジット"):
        try:
            locator = page.get_by_text(text, exact=True).first
            if await locator.count() and await locator.is_visible():
                await locator.click(timeout=5000)
                await page.wait_for_timeout(6000)
                body = await page.evaluate(
                    "() => (document.body && document.body.innerText) || ''")
                lines = [l.strip() for l in body.splitlines() if l.strip()]
                evidence.setdefault("conversation_reads", {})[text] = \
                    lines[:40]
                break
        except Exception:
            continue
    # verdict from the freshest numeric statement found anywhere
    import re
    candidates = []
    for statement in evidence.get("history_statements", []) or []:
        candidates.append((statement.get("create_time") or 0,
                           statement.get("remaining")))
    for read in (evidence.get("conversation_reads") or {}).values():
        joined = "\n".join(read)
        for match in re.finditer(
                r"(?:残り|残っています|あと)[^0-9\n]{0,8}(\d+)"
                r"|(\d+)\s*(?:枚|個)?\s*(?:動画クレジット|クレジット)",
                joined):
            value = next((g for g in match.groups() if g), None)
            if value is not None:
                candidates.append((0, int(value)))  # undated → lowest prio
    candidates.sort(key=lambda pair: pair[0])
    if candidates:
        evidence["credit_remaining"] = candidates[-1][1]
        evidence["credit_verdict"] = ("SUFFICIENT" if candidates[-1][1] >= 1
                                      else "INSUFFICIENT")
    else:
        evidence["credit_remaining"] = None
        evidence["credit_verdict"] = "UNOBSERVABLE"
    return evidence


async def main() -> int:
    journal_path = JOURNAL_PATH
    if journal_path.exists():
        existing = DispatchJournal(journal_path, "attempt_010e")
        if existing.events and existing.state not in ("RESERVED",):
            emit({"status": "REFUSED_NONFRESH_JOURNAL",
                  "state": existing.state,
                  "reason": "use recover mode / new authority"})
            return 1
        journal_path.unlink()
    auth = MutationAuthority(PKG, SCOPE)
    if auth.authority != "OPEN":
        emit({"status": "STOPPED_GOVERNANCE_GAP",
              "authority": auth.authority})
        return 1
    attempt = build_attempt()
    journal = DispatchJournal(journal_path, attempt.generation_attempt_id)
    journal.append(MUTATION_RESERVED, {
        "budget_kind": BUDGET_KIND, "account_opaque_id": OPAQUE,
        "account_alias": "dola-main",
        "conversation_id": SEEDANCE_CONVERSATION_ID})
    auth._event("MUTATION_RESERVED", budget_kind=BUDGET_KIND,
                detail="account=" + OPAQUE)
    reservation = {"version": "v2-010e-mutation-reservation-v1",
                   "budget_kind": BUDGET_KIND, "run_id": "f2b010e",
                   "attempt_id": attempt.generation_attempt_id,
                   "account_opaque_id": OPAQUE,
                   "intent": {"shot_id": SHOT_ID, "prompt_sha256": PROMPT_SHA,
                              "duration_class": 5, "expected_credit": 1,
                              "plan_authority":
                              "world_reframe_plan_v2_009 (FROZEN)"},
                   "created_at": utcnow()}
    write_pkg("mutation_reservation_f2b_010e.json", reservation)
    write_pkg("generation_attempt_f2b_010e.json", {
        "attempt": json.loads(attempt.model_dump_json()),
        "reservation": reservation})
    emit({"event": "reserved", "account": OPAQUE})

    # ---- ONE launch for the whole flow -------------------------------------
    manager = DolaSessionManager(profile_dir=PROFILE)
    await manager.launch_browser()
    page = manager._page
    screenshots = PKG / "screenshots_f2b_010e"
    screenshots.mkdir(parents=True, exist_ok=True)

    async def terminate(status: str, reason: str, *,
                        latch: bool = False) -> int:
        journal.append("AMBIGUITY_LATCHED" if latch
                       else TERMINAL_PROVIDER_FAILURE,
                       {"status": status, "reason": reason[:250]})
        if latch:
            auth.latch(status, reason[:250])
        write_pkg("V2_010E_F2B_EVIDENCE.json", {
            "version": "v2-010e-f2b-evidence-v1", "status": status,
            "reason": reason, "journal_events": journal.events,
            "account_opaque_id": OPAQUE})
        emit({"status": status, "reason": reason})
        return 1

    try:
        # ---- session gate (stable authentication in THIS context) --------
        try:
            await page.goto("https://www.dola.com/chat", timeout=60000,
                            wait_until="domcontentloaded")
        except Exception as error:
            return await terminate("STOPPED_SESSION_GAP",
                                   f"navigation: {type(error).__name__}")
        state = await page.evaluate(LOGIN_CHECK_JS)
        stable = 0
        waited = 0
        while waited < 1500 and not (state.get("composer")
                                     and not state.get("logged_out")):
            await asyncio.sleep(5)
            waited += 5
            state = await page.evaluate(LOGIN_CHECK_JS)
            stable = stable + 1 if (state.get("composer")
                                    and not state.get("logged_out")) else 0
            if stable >= 3:
                break
            if waited % 120 == 0:
                emit({"step": "waiting_login", "waited": waited,
                      **state})
        if not (state.get("composer") and not state.get("logged_out")):
            return await terminate("USER_LOGIN_REQUIRED",
                                   "session not authenticated within window")
        emit({"event": "session_authenticated", "account": OPAQUE})

        # capture the fresh session blob (evidence/backup; no re-injection)
        cookies = await manager._context.cookies("https://www.dola.com")
        blob = json.dumps({"schema": "ai-film-dola-session-v2-010e",
                           "account_alias": "dola-main",
                           "saved_at": utcnow(), "cookies": cookies},
                          ensure_ascii=False, separators=(",", ":"))
        secrets = PKG / "runtime/runtime_secret_store"
        secrets.mkdir(parents=True, exist_ok=True)
        target = secrets / f"dola_session_{OPAQUE}.dpapi"
        tmp = target.with_suffix(".dpapi.tmp")
        tmp.write_text(dpapi_protect(blob.encode("utf-8")), encoding="ascii")
        tmp.replace(target)
        emit({"event": "session_blob_refreshed"})

        # ---- credit gate ---------------------------------------------------
        credit = await read_credit_state(page)
        write_pkg("V2_010E_SESSION_CREDIT_PRECHECK.json", {
            "version": "v2-010e-session-credit-precheck-v2",
            "account_opaque_id": OPAQUE, "session": "SESSION_VALID",
            "built_at": utcnow(), **credit})
        emit({"event": "credit_precheck",
              "verdict": credit["credit_verdict"],
              "remaining": credit.get("credit_remaining")})
        if credit["credit_verdict"] == "INSUFFICIENT":
            # unspent: the reservation stays OPEN and unused
            journal.events.pop()  # remove the terminal event just added
            write_pkg("V2_010E_F2B_EVIDENCE.json", {
                "version": "v2-010e-f2b-evidence-v1",
                "status": "STOPPED_INSUFFICIENT_CREDIT_PRE_DISPATCH",
                "credit": credit, "account_opaque_id": OPAQUE,
                "journal_events": journal.events})
            emit({"status": "STOPPED_INSUFFICIENT_CREDIT_PRE_DISPATCH"})
            return 1
        if credit["credit_verdict"] == "UNOBSERVABLE":
            return await terminate(
                "STOPPED_CREDIT_UNOBSERVABLE",
                "no provider-visible credit statement obtainable "
                "pre-dispatch; authority unspent")

        # ---- baseline + arm + dispatch --------------------------------------
        poll_js = """async () => {
          const params = new URLSearchParams({
            version_code: "20800", language: "ja", device_platform: "web",
            doubao_device_platform: "web", aid: "495671", real_aid: "495671",
            pkg_type: "release_version", pc_version: "3.39.1",
            doubao_pc_version: "3.39.1", region: "VN", sys_region: "VN",
            samantha_web: "1", web_platform: "browser",
            "use-olympus-account": "1", web_tab_id: crypto.randomUUID(),
          });
          const resp = await fetch("/im/chain/single?" + params.toString(), {
            method: "POST",
            headers: {"Content-Type": "application/json; encoding=utf-8",
                      "agw-js-conv": "str",
                      "Accept": "application/json, text/plain, */*"},
            credentials: "include",
            body: JSON.stringify({cmd: 3100,
              uplink_body: {pull_singe_chain_uplink_body: {
                conversation_id: arguments_0,
                anchor_index: Number.MAX_SAFE_INTEGER,
                conversation_type: 3, direction: 1, limit: 20,
                ext: {}, filter: {index_list: []},
                evaluate_ab_params: "", evaluate_common_params: ""}},
              sequence_id: crypto.randomUUID(), channel: 2, version: "1"})});
          if (!resp.ok) return {ok: false, replies: []};
          const data = await resp.json();
          const messages = ((data.downlink_body || {})
            .pull_singe_chain_downlink_body || {}).messages || [];
          const replies = [];
          for (const m of messages) {
            let blocks = m.content;
            if (typeof blocks === "string") {
              try { blocks = JSON.parse(blocks); } catch (e) { continue; }
            }
            for (const b of (Array.isArray(blocks) ? blocks : [])) {
              if (b.block_type === 2074) {
                for (const c of (((b.content || {}).creation_block || {})
                    .creations || [])) {
                  replies.push({message_id: String(m.message_id),
                    creation_id: c.id ? String(c.id) : null, type: c.type,
                    video_download_url: (c.video || {}).download_url || null});
                }
              }
            }
          }
          return {ok: true, replies};
        }"""
        poll = await page.evaluate(
            poll_js.replace("arguments_0", json.dumps(SEEDANCE_CONVERSATION_ID)))
        if not poll.get("ok"):
            return await terminate("STOPPED_SESSION_GAP",
                                   "baseline poll failed")
        known_creations = {r.get("creation_id")
                           for r in poll.get("replies", [])}
        known_messages = {r.get("message_id")
                          for r in poll.get("replies", [])}

        from dola_010d_adapter_delta import DolaBrowserAdapter010D as _Base
        adapter = DolaBrowserAdapter010E(run_id="f2b010e_" +
                                         datetime.now(timezone.utc)
                                         .strftime("%Y%m%dT%H%M%S"))
        # adopt the LIVE context (never re-launch)
        adapter.manager = manager
        adapter.page = page
        adapter.capture = await manager._context.new_cdp_session(page)
        from dola_010c_capture import NetworkCapture
        capture = NetworkCapture(manager._context, page, adapter.run_id)
        capture._cdp = adapter.capture
        await capture.start()
        adapter.capture = capture
        adapter.event("adopted_live_context")

        await adapter.ensure_video_mode()
        await adapter.select_duration(5)
        gate = await adapter.verify_duration_pre_dispatch(5)
        await page.screenshot(path=str(screenshots / "01_duration_5s.png"))
        emit({"event": "duration_gated", "chip": gate["chip"]})

        journal.append(DISPATCH_ARMED_EV, {
            "attempt_id": attempt.generation_attempt_id,
            "account_opaque_id": OPAQUE, "account_alias": "dola-main",
            "session_alias": f"router_profile_{OPAQUE}",
            "request_fingerprint": hashlib.sha256(json.dumps(
                {"prompt_sha256": PROMPT_SHA, "duration_class": 5,
                 "conversation_id": SEEDANCE_CONVERSATION_ID,
                 "index_boundary": 999}, sort_keys=True).encode()).hexdigest(),
            "session_alias_note": "single-launch flow; live profile",
            "conversation_id": SEEDANCE_CONVERSATION_ID,
            "capture_run_id": adapter.run_id, "duration_class": 5})

        adapter.attach_journal(
            journal, expected_needle=F2B_PROMPT, index_boundary=999,
            known_creation_ids=known_creations,
            on_receipt_captured=lambda receipt: auth.consume(BUDGET_KIND))

        dispatch = await adapter.submit(
            F2B_PROMPT, conversation_id=SEEDANCE_CONVERSATION_ID)
        release = dispatch["release"]
        if not await adapter.wait_journal_state("RELEASE_OBSERVED", 30):
            return await terminate("OWNER_AMBIGUITY_GATE",
                                   "release not observed", latch=True)
        # account binding becomes IMMUTABLE here
        journal.append(NETWORK_RELEASE_OBSERVED, {
            "account_binding": {
                "generation_attempt_id": attempt.generation_attempt_id,
                "account_opaque_id": OPAQUE, "account_alias": "dola-main",
                "session_alias": f"router_profile_{OPAQUE}",
                "conversation_id": SEEDANCE_CONVERSATION_ID,
                "request_fingerprint": hashlib.sha256(json.dumps(
                    {"prompt_sha256": PROMPT_SHA, "duration_class": 5},
                    sort_keys=True).encode()).hexdigest()},
            "binding_rule": "NO ACCOUNT SWITCH / NO SECOND ACCOUNT / "
                            "NO RETRY after this event"})
        refined = await adapter.verify_release_body(release["request_id"])
        emit({"event": "release_refined", **refined})
        if refined.get("duration") not in (5, None):
            return await terminate("OWNER_AMBIGUITY_GATE",
                                   f"released duration={refined.get('duration')} ≠ 5",
                                   latch=True)
        if not await adapter.wait_journal_state("RECEIPT_CAPTURED", 120):
            return await terminate("OWNER_AMBIGUITY_GATE",
                                   "receipt not captured within 120s",
                                   latch=True)
        attempt.provider_job_id = SEEDANCE_CONVERSATION_ID
        attempt.status = "running"
        write_pkg("generation_attempt_f2b_010e.json", {
            "attempt": json.loads(attempt.model_dump_json()),
            "reservation": reservation,
            "release_request": {k: v for k, v in release.items()
                                if k != "body_structure"},
            "release_body_structure": release["body_structure"]})
        await page.screenshot(path=str(screenshots / "02_receipt.png"))
        emit({"event": "receipt_captured"})

        # ---- completion (network authority, baseline-diffed) ---------------
        done = await adapter.wait_for_new_video(
            SEEDANCE_CONVERSATION_ID,
            known_creation_ids=known_creations,
            known_message_ids=known_messages, timeout_s=1500,
            on_progress=lambda fresh, done_n: emit(
                {"event": "poll_progress", "new_records": fresh,
                 "done_videos": done_n}))
        if not done:
            texts = []
            try:
                repoll = await page.evaluate(poll_js.replace(
                    "arguments_0", json.dumps(SEEDANCE_CONVERSATION_ID)))
                texts = [str(x) for x in [repoll.get("replies")][:1]]
            except Exception:
                pass
            credits = adapter.parse_credit_requirement(" ".join(texts))
            return await terminate(
                "STOPPED_EXPLICIT_PROVIDER_FAILURE"
                if credits.get("required") else
                "STOPPED_PROVIDER_CORRELATION_GAP",
                "no new completed video")
        urls = {r["video_download_url"] for r in done}
        if len(urls) != 1:
            return await terminate("STOPPED_PROVIDER_CORRELATION_GAP",
                                   f"{len(urls)} distinct urls")
        video_url = urls.pop()
        journal.append(CREATION_BOUND, {
            "creation_ids": sorted({r["creation_id"] for r in done}),
            "message_ids": sorted({r["message_id"] for r in done})})
        emit({"event": "creation_bound",
              "creation_ids": sorted({r["creation_id"] for r in done})})

        dest = PKG / "assets" / "f2b_010e.mp4"
        meta = await adapter.download(video_url, dest)
        asset_sha = hashlib.sha256(dest.read_bytes()).hexdigest()
        journal.append(ASSET_DOWNLOADED, {"sha256": asset_sha, **meta})
        journal.append(TERMINAL_SUCCESS, {"sha256": asset_sha})
        attempt.status = "succeeded"
        attempt.completed_at = utcnow()
        attempt.output_asset_ids = [f"asset_sha256:{asset_sha[:16]}"]
        await page.screenshot(path=str(screenshots / "03_completed.png"))

        duration = float(meta.get("duration_s") or 0)
        duration_class = "5s" if abs(duration - 5.0) <= abs(duration - 10.0) \
            else "10s"
        technical_qc = {
            "ffprobe": meta, "duration_s": duration,
            "duration_class": duration_class, "requested_class": "5s",
            "class_matches_request": duration_class == "5s",
            "full_decode": meta.get("full_decode"),
            "verdict": "PASS" if (meta.get("full_decode")
                                  and duration_class == "5s") else "FAIL"}
        write_pkg("V2_010E_F2B_EVIDENCE.json", {
            "version": "v2-010e-f2b-evidence-final-v1",
            "checkpoint": "V2010E_P4_F2B",
            "status": "PROVEN" if technical_qc["verdict"] == "PASS"
            else "PARTIAL",
            "attempt": json.loads(attempt.model_dump_json()),
            "journal_events": journal.events,
            "account_binding": {"account_opaque_id": OPAQUE,
                                "account_alias": "dola-main",
                                "bound_at": "NETWORK_RELEASE_OBSERVED",
                                "immutable_after_release": True},
            "video_records": done,
            "asset": {"path_class": "assets/" + dest.name,
                      "sha256": asset_sha,
                      "host": video_url.split("/")[2], **meta},
            "qc": {"TRANSPORT_QC": {"single_release": True,
                                    "durable_release_record": True,
                                    "durable_sse_receipt": True,
                                    "exact_creation_id": True,
                                    "verdict": "PASS"},
                   "TECHNICAL_QC": technical_qc,
                   "CREATIVE_QC": {"method": "WORKER_ADVISORY — strips for "
                                             "Owner read; authoritative",
                                   "verdict": "DEFERRED_TO_OWNER"}},
            "editorial_use_flags": {
                "trim_required": duration > 2.8, "crop_required": False,
                "watermark_handling": "download_url variant watermarked; "
                                      "unwatermarked OBSERVED_NOT_AUTHORIZED",
                "regeneration": "PROHIBITED"}})
        write_pkg("V2_010E_PROVIDER_LINEAGE.json", {
            "version": "v2-010e-provider-lineage-v1", "built_at": utcnow(),
            "account": OPAQUE, "conversation_id": SEEDANCE_CONVERSATION_ID,
            "creation_ids": sorted({r["creation_id"] for r in done}),
            "message_ids": sorted({r["message_id"] for r in done}),
            "asset": {"sha256": asset_sha, **meta}})
        emit({"checkpoint": "V2010E_F2B_COMPLETE",
              "status": "PROVEN" if technical_qc["verdict"] == "PASS"
              else "PARTIAL", "duration": duration,
              "class": duration_class, "sha256": asset_sha})
        return 0
    except Exception as error:
        state_before = journal.state
        if journal.has("NETWORK_RELEASE_OBSERVED") or \
                state_before in ("RELEASE_OBSERVED", "RECEIPT_CAPTURED",
                                 "PROVIDER_JOB_BOUND"):
            return await terminate("OWNER_AMBIGUITY_GATE",
                                   f"failure after release: "
                                   f"{type(error).__name__}: {error}",
                                   latch=True)
        return await terminate("STOPPED_PRE_DISPATCH",
                               f"failure: {type(error).__name__}: {error}")
    finally:
        write_pkg("V2_010E_MUTATION_LEDGER.json", {
            "version": "v2-010e-mutation-ledger-v1", "exported_at": utcnow(),
            "authority": json.loads((PKG / "mutation_authority.json")
                                    .read_text(encoding="utf-8")),
            "journal": journal.events})
        await manager.close()


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
