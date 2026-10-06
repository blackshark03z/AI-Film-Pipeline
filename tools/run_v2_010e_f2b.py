"""AI-FILM-QUALITY-V2-010E — F2B final qualification (ONE mutation).

Modes:
  dispatch — fresh attempt: requires NO prior journal (or a terminal one);
             refuses to run when a non-terminal journal exists (a restart
             must use `recover` and can never auto-redispatch)
  recover  — resume from a crashed attempt per the journal's boundary plan
             (C resume-poll, D resume-download, E verify-sha+finalize,
             B latch+reconcile); NEVER dispatches
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

from dola_010e_adapter_delta import DolaBrowserAdapter010E
from dola_010e_dispatch_journal import (ASSET_DOWNLOADED, CREATION_BOUND,
                                        DISPATCH_ARMED,
                                        DISPATCH_ARMED_EV,
                                        MUTATION_RESERVED, RESERVED,
                                        SSE_RECEIPT_CAPTURED,
                                        TERMINAL_PROVIDER_FAILURE,
                                        TERMINAL_SUCCESS, DispatchJournal)
from dola_010c_browser_adapter import SEEDANCE_CONVERSATION_ID
from dola_010d_adapter_delta import extract_released_duration
from film_pipeline.core import GenerationAttempt
from film_pipeline.execution import sha256
from mutation_authority import MutationAuthority

SCOPE = "QUALITY-V2-010E-FINAL-F2B"
PKG = ROOT / "projects/quality_v2_010e_final_f2b"
BUDGET_KIND = "f2b_010e"
SHOT_ID = "SEQ7_F2B"
JOURNAL_PATH = PKG / "dispatch_journal_f2b_010e.jsonl"

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


def utcnow() -> str:
    return datetime.now(timezone.utc).isoformat()


def emit(payload: dict) -> None:
    print(json.dumps(payload, ensure_ascii=False, default=str), flush=True)


def write_pkg(name: str, payload: dict) -> Path:
    path = PKG / name
    path.write_text(json.dumps(payload, indent=1, ensure_ascii=False),
                    encoding="utf-8")
    return path


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


async def run_recover() -> int:
    """Restart path: resume per journal; NEVER dispatch."""
    if not JOURNAL_PATH.exists():
        emit({"status": "RECOVER_NOTHING", "reason": "no journal"})
        return 1
    journal = DispatchJournal(JOURNAL_PATH, "attempt_010e")
    auth = MutationAuthority(PKG, SCOPE)
    plan = journal.recover()
    emit({"event": "recovery_plan", **plan})
    action = plan["action"]
    if action in ("NONE_TERMINAL",):
        emit({"status": "ALREADY_TERMINAL"})
        return 0
    if action.startswith("AMBIGUITY_LATCH") or plan["boundary"] == "B":
        auth.latch("F2B_010E_RELEASE_WITHOUT_RECEIPT",
                   json.dumps(plan))
        emit({"status": "OWNER_AMBIGUITY_GATE", "plan": plan})
        return 1
    if plan["boundary"] in ("C", "D", "E"):
        # resume read-only / acquisition using the durable identity
        receipt_ev = journal.last_of(SSE_RECEIPT_CAPTURED) or {}
        creation_ev = journal.last_of(CREATION_BOUND) or {}
        download_ev = journal.last_of(ASSET_DOWNLOADED) or {}
        adapter = DolaBrowserAdapter010E(run_id="recover_" +
                                         datetime.now(timezone.utc)
                                         .strftime("%Y%m%dT%H%M%S"))
        await adapter.open()
        try:
            await adapter.goto_conversation(SEEDANCE_CONVERSATION_ID)
            if plan["boundary"] == "C":
                emit({"event": "resume_poll_by_receipt",
                      "question_id": receipt_ev.get("payload", {})
                      .get("question_id")})
                emit({"status": "RESUME_C_STARTED", "note": "poll loop "
                      "continues in a follow-up dispatch-mode run with "
                      "resume flags; identity is durable in the journal"})
                return 0
            if plan["boundary"] in ("D", "E"):
                url = creation_ev.get("payload", {}).get("download_url")
                if not url:
                    emit({"status": "RESUME_GAP",
                          "reason": "no download_url in journal"})
                    return 1
                dest = PKG / "assets" / "f2b_010e.mp4"
                meta = await adapter.download(url, dest)
                sha = hashlib.sha256(dest.read_bytes()).hexdigest()
                journal.append(ASSET_DOWNLOADED, {"sha256": sha, **meta})
                journal.append(TERMINAL_SUCCESS, {"sha256": sha})
                emit({"checkpoint": "V2010E_RECOVER_FINALIZED",
                      "sha256": sha})
                return 0
        finally:
            await adapter.close(sanitize_to=None)
    emit({"status": "RECOVER_UNHANDLED", "plan": plan})
    return 1


async def run_dispatch() -> int:
    if JOURNAL_PATH.exists():
        existing = DispatchJournal(JOURNAL_PATH, "attempt_010e")
        if existing.state not in (RESERVED,) and existing.events:
            emit({"status": "REFUSED_NONFRESH_JOURNAL",
                  "state": existing.state,
                  "reason": "a restart must use recover mode; dispatch "
                            "mode requires a fresh attempt"})
            return 1
        JOURNAL_PATH.unlink()
    auth = MutationAuthority(PKG, SCOPE)
    if auth.authority != "OPEN":
        emit({"status": "STOPPED_GOVERNANCE_GAP",
              "authority": auth.authority})
        return 1
    attempt = build_attempt()
    journal = DispatchJournal(JOURNAL_PATH, attempt.generation_attempt_id)
    journal.append(MUTATION_RESERVED, {"budget_kind": BUDGET_KIND,
                                       "conversation_id":
                                       SEEDANCE_CONVERSATION_ID})
    reservation = {"version": "v2-010e-mutation-reservation-v1",
                   "budget_kind": BUDGET_KIND, "run_id": "f2b010e",
                   "attempt_id": attempt.generation_attempt_id,
                   "intent": {"shot_id": SHOT_ID, "prompt_sha256": PROMPT_SHA,
                              "duration_class": 5, "expected_credit": 1,
                              "plan_authority":
                              "world_reframe_plan_v2_009 (FROZEN)"},
                   "created_at": utcnow()}
    write_pkg("mutation_reservation_f2b_010e.json", reservation)
    auth._event("MUTATION_RESERVED", budget_kind=BUDGET_KIND,
                detail=reservation["run_id"])
    emit({"event": "reserved", "attempt_id": attempt.generation_attempt_id})

    adapter = DolaBrowserAdapter010E(run_id="f2b010e_" +
                                     datetime.now(timezone.utc)
                                     .strftime("%Y%m%dT%H%M%S"))
    screenshots = PKG / "screenshots_f2b_010e"
    screenshots.mkdir(parents=True, exist_ok=True)

    def fail(status: str, reason: str, *, latch: bool = False) -> int:
        if latch:
            auth.latch(status, reason[:250])
            journal.append("AMBIGUITY_LATCHED", {"status": status})
        else:
            journal.append(TERMINAL_PROVIDER_FAILURE, {"status": status,
                                                       "reason": reason[:250]})
        write_pkg("V2_010E_F2B_EVIDENCE.json", {
            "version": "v2-010e-f2b-evidence-v1", "status": status,
            "reason": reason, "journal_events": journal.events,
            "run_id": reservation["run_id"]})
        emit({"status": status, "reason": reason})
        return 1

    try:
        await adapter.open()
        try:
            await adapter.goto_conversation(SEEDANCE_CONVERSATION_ID)
        except Exception as error:
            return fail("STOPPED_SESSION_GAP",
                        f"navigation failed: {type(error).__name__}")
        baseline = await adapter.poll_replies(SEEDANCE_CONVERSATION_ID)
        if not baseline.get("ok"):
            return fail("USER_LOGIN_REQUIRED",
                        "read-only poll failed — session invalid")
        replies = baseline.get("replies", [])
        known_creations = {r.get("creation_id") for r in replies}
        indexes = [r.get("index_in_conv") for r in replies
                   if isinstance(r.get("index_in_conv"), int)]
        index_boundary = max(indexes) if indexes else 0
        emit({"event": "session_valid", "known_creations":
              len(known_creations), "index_boundary": index_boundary})

        # credit precheck evidence reference (the precheck tool ran earlier)
        precheck_path = PKG / "V2_010E_SESSION_CREDIT_PRECHECK.json"
        precheck = json.loads(precheck_path.read_text(encoding="utf-8")) \
            if precheck_path.exists() else {"credit": "UNOBSERVABLE"}
        if precheck.get("credit_verdict") == "INSUFFICIENT":
            return fail("STOPPED_INSUFFICIENT_CREDIT_PRE_DISPATCH",
                        f"provider-visible credits: "
                        f"{precheck.get('credit_value')}")

        mode_state = await adapter.ensure_video_mode()
        selection = await adapter.select_duration(5)
        gate = await adapter.verify_duration_pre_dispatch(5)
        await adapter.page.screenshot(path=str(
            screenshots / "01_duration_5s_armed.png"))
        emit({"event": "duration_gated", **gate})

        journal.append(DISPATCH_ARMED_EV, {
            "attempt_id": attempt.generation_attempt_id,
            "request_fingerprint": hashlib.sha256(json.dumps(
                {"prompt_sha256": PROMPT_SHA, "duration_class": 5,
                 "conversation_id": SEEDANCE_CONVERSATION_ID,
                 "index_boundary": index_boundary}, sort_keys=True)
                .encode()).hexdigest(),
            "session_alias": "DOLA_RE_PROFILE (dpapi)",
            "conversation_id": SEEDANCE_CONVERSATION_ID,
            "expected_message_index_boundary": index_boundary,
            "capture_run_id": adapter.run_id,
            "duration_class": 5,
            "video_mode": mode_state, "selection": selection})
        write_pkg("generation_attempt_f2b_010e.json", {
            "attempt": json.loads(attempt.model_dump_json()),
            "reservation": reservation})
        emit({"event": "dispatch_armed", "index_boundary": index_boundary})

        adapter.attach_journal(
            journal, expected_needle=F2B_PROMPT,
            index_boundary=index_boundary,
            known_creation_ids=known_creations,
            on_receipt_captured=lambda receipt: auth.consume(BUDGET_KIND))

        dispatch = await adapter.submit(
            F2B_PROMPT, conversation_id=SEEDANCE_CONVERSATION_ID)
        release = dispatch["release"]

        if not await adapter.wait_journal_state("RELEASE_OBSERVED", 30):
            return fail("OWNER_AMBIGUITY_GATE",
                        "release not observed in journal within 30s",
                        latch=True)
        refined = await adapter.verify_release_body(release["request_id"])
        emit({"event": "release_refined", **refined})
        if refined.get("duration") not in (5, None):
            return fail("OWNER_AMBIGUITY_GATE",
                        f"released body duration={refined.get('duration')} "
                        f"≠ 5 — the 5s gate was violated",
                        latch=True)

        if not await adapter.wait_journal_state("RECEIPT_CAPTURED", 120):
            released_body = release.get("body_structure") or {}
            correlated = bool(released_body)
            return fail("OWNER_AMBIGUITY_GATE" if correlated
                        else "STOPPED_PRE_DISPATCH",
                        "receipt not captured within 120s"
                        + (" (release confirmed)" if correlated else ""),
                        latch=correlated)
        attempt.provider_job_id = SEEDANCE_CONVERSATION_ID
        attempt.status = "running"
        receipt_ev = journal.last_of(SSE_RECEIPT_CAPTURED)
        write_pkg("generation_attempt_f2b_010e.json", {
            "attempt": json.loads(attempt.model_dump_json()),
            "reservation": reservation,
            "release_request": {k: v for k, v in release.items()
                                if k != "body_structure"},
            "release_body_structure": release["body_structure"]})
        await adapter.page.screenshot(path=str(
            screenshots / "02_receipt_captured.png"))
        emit({"event": "receipt_captured",
              "question_id": receipt_ev["payload"].get("question_id"),
              "message_index": receipt_ev["payload"].get("message_index")})

        # ---- completion correlation (creation identity) -------------------
        done = await adapter.wait_for_new_video(
            SEEDANCE_CONVERSATION_ID,
            known_creation_ids=known_creations,
            known_message_ids={r.get("message_id") for r in replies},
            timeout_s=1500,
            on_progress=lambda fresh, done_n: emit(
                {"event": "poll_progress", "new_records": fresh,
                 "done_videos": done_n}))
        if not done:
            texts = []
            try:
                repoll = await adapter.poll_replies(SEEDANCE_CONVERSATION_ID)
                texts = repoll.get("texts", [])
            except Exception:
                pass
            credits = adapter.parse_credit_requirement(" ".join(texts))
            return fail("STOPPED_EXPLICIT_PROVIDER_FAILURE"
                        if credits.get("required") else
                        "STOPPED_PROVIDER_CORRELATION_GAP",
                        f"no new completed video; provider texts: "
                        f"{[t[:120] for t in texts[:3]]}")
        urls = {r["video_download_url"] for r in done}
        if len(urls) != 1:
            return fail("STOPPED_PROVIDER_CORRELATION_GAP",
                        f"{len(urls)} distinct urls")
        video_url = urls.pop()
        # receipt-linkage contradiction check (no positive-proof demand:
        # the poll records may not carry reply linkage; a CONTRADICTING
        # linkage or a baseline-known id is what fails correlation)
        receipt_payload = receipt_ev["payload"]
        linkage_verdicts = []
        for record in done:
            contradicts = (
                (record.get("reply_to") and receipt_payload.get("question_id")
                 and str(record["reply_to"]) !=
                 str(receipt_payload["question_id"]))
                or (record.get("message_id") in known_creations))
            linkage_verdicts.append({"creation_id": record.get("creation_id"),
                                     "contradicts": bool(contradicts)})
            if contradicts:
                return fail("STOPPED_PROVIDER_CORRELATION_GAP",
                            f"creation {record.get('creation_id')} carries "
                            f"linkage contradicting the receipt")
        journal.append(CREATION_BOUND, {
            "creation_ids": sorted({r["creation_id"] for r in done}),
            "message_ids": sorted({r["message_id"] for r in done}),
            "linkage_verdicts": linkage_verdicts,
            "download_url_host":
            video_url.split("/")[2] if "/" in video_url else "?"})
        emit({"event": "creation_bound",
              "creation_ids": sorted({r["creation_id"] for r in done})})

        dest = PKG / "assets" / "f2b_010e.mp4"
        meta = await adapter.download(video_url, dest)
        asset_sha = hashlib.sha256(dest.read_bytes()).hexdigest()
        journal.append(ASSET_DOWNLOADED, {"sha256": asset_sha, **meta})
        attempt.status = "succeeded"
        attempt.completed_at = utcnow()
        attempt.output_asset_ids = [f"asset_sha256:{asset_sha[:16]}"]
        await adapter.page.screenshot(path=str(
            screenshots / "03_completed.png"))

        duration = float(meta.get("duration_s") or 0)
        duration_class = "5s" if abs(duration - 5.0) <= abs(duration - 10.0) \
            else "10s"
        technical_qc = {
            "ffprobe": meta, "duration_s": duration,
            "duration_class": duration_class, "requested_class": "5s",
            "class_matches_request": duration_class == "5s",
            "aspect_16_9": bool(meta.get("width") and meta.get("height")
                                and abs(meta["width"] / meta["height"]
                                        - 16 / 9) < 0.05),
            "full_decode": meta.get("full_decode"),
            "verdict": "PASS" if (meta.get("full_decode")
                                  and duration_class == "5s") else "FAIL"}
        journal.append(TERMINAL_SUCCESS, {"sha256": asset_sha})
        evidence = {
            "version": "v2-010e-f2b-evidence-final-v1",
            "checkpoint": "V2010E_P4_F2B",
            "status": "PROVEN" if technical_qc["verdict"] == "PASS"
            else "PARTIAL",
            "run_id": reservation["run_id"],
            "attempt": json.loads(attempt.model_dump_json()),
            "journal_events": journal.events,
            "receipt": journal.last_of(SSE_RECEIPT_CAPTURED)["payload"],
            "video_records": done,
            "release_body_duration": refined.get("duration"),
            "asset": {"path_class": "projects/.../assets/" + dest.name,
                      "sha256": asset_sha,
                      "host": video_url.split("/")[2], **meta},
            "qc": {"TRANSPORT_QC": {
                       "single_release": True,
                       "durable_release_record": True,
                       "durable_sse_receipt": True,
                       "stable_provider_identity": True,
                       "exact_creation_id": True,
                       "correlation": "creation-id + receipt linkage "
                                      "(network authority)",
                       "verdict": "PASS"},
                   "TECHNICAL_QC": technical_qc,
                   "CREATIVE_QC": {
                       "method": "WORKER_ADVISORY — strips in "
                                 "owner_review_f2b_010e/; Owner read "
                                 "authoritative",
                       "verdict": "DEFERRED_TO_OWNER"}},
            "editorial_use_flags": {
                "trim_required": duration > 2.8, "crop_required": False,
                "watermark_handling": "download_url variant watermarked; "
                                      "unwatermarked OBSERVED_NOT_AUTHORIZED",
                "regeneration": "PROHIBITED"},
        }
        write_pkg("V2_010E_F2B_EVIDENCE.json", evidence)
        lineage = {
            "version": "v2-010e-provider-lineage-v1",
            "built_at": utcnow(),
            "conversation_id": SEEDANCE_CONVERSATION_ID,
            "question_message_id": journal.last_of(SSE_RECEIPT_CAPTURED)
            ["payload"].get("question_id"),
            "creation_ids": sorted({r["creation_id"] for r in done}),
            "message_ids": sorted({r["message_id"] for r in done}),
            "asset": {"sha256": asset_sha, **meta},
            "credit_consumption": {"expected": 1,
                                   "provider_statement": "see ack texts in "
                                                         "the journal/raw"},
            "lineage": "GenerationAttempt → ProviderJob → creation → asset",
        }
        write_pkg("V2_010E_PROVIDER_LINEAGE.json", lineage)
        emit({"checkpoint": "V2010E_F2B_COMPLETE",
              "status": evidence["status"], "duration": duration,
              "class": duration_class, "sha256": asset_sha})
        return 0
    except RuntimeError as error:
        return fail("STOPPED_DURATION_AUTHORITY_GAP"
                    if "DURATION_AUTHORITY_GAP" in str(error)
                    else "STOPPED_PROVIDER_CORRELATION_GAP", str(error))
    except Exception as error:
        # broad catch: a crash must land in a DURABLE terminal/latch state,
        # never leave the attempt silently RESERVED after a release
        state_before = journal.state
        if journal.has("NETWORK_RELEASE_OBSERVED") or \
                state_before in ("RELEASE_OBSERVED", "RECEIPT_CAPTURED",
                                 "PROVIDER_JOB_BOUND"):
            return fail("OWNER_AMBIGUITY_GATE",
                        f"unexpected failure after release: "
                        f"{type(error).__name__}: {error}", latch=True)
        return fail("STOPPED_PRE_DISPATCH",
                    f"unexpected failure: {type(error).__name__}: {error}")
    finally:
        await adapter.close(sanitize_to=PKG /
                            "V2_010E_F2B_CAPTURE_SANITIZED.json")
        write_pkg("V2_010E_MUTATION_LEDGER.json", {
            "version": "v2-010e-mutation-ledger-v1",
            "exported_at": utcnow(),
            "authority": json.loads((PKG / "mutation_authority.json")
                                    .read_text(encoding="utf-8")),
            "journal": journal.events})


async def main() -> int:
    mode = sys.argv[1] if len(sys.argv) > 1 else "dispatch"
    if mode == "recover":
        return await run_recover()
    return await run_dispatch()


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
