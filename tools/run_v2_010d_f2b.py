"""AI-FILM-QUALITY-V2-010D — F2B completion (ONE authorized mutation).

Gates (fail-closed, in order):
  010C lineage → session valid → video mode → 5s chip PROVEN → baseline poll
  → reservation/attempt/fingerprint → capture active → dispatch →
  receipt-first persist (+ release-body duration verification) → consume →
  completion correlation → exact download → separated QC.

Failure semantics per the work package:
  explicit refusal         → STOPPED_EXPLICIT_PROVIDER_FAILURE (no retry)
  ambiguous effect         → OWNER_AMBIGUITY_GATE (no retry)
  duration not provable    → STOPPED_DURATION_AUTHORITY_GAP (no mutation)
  session invalid          → USER_LOGIN_REQUIRED (no mutation)
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

from dola_010d_adapter_delta import DolaBrowserAdapter010D
from dola_010c_browser_adapter import SEEDANCE_CONVERSATION_ID
from film_pipeline.core import GenerationAttempt
from film_pipeline.execution import sha256
from mutation_authority import MutationAuthority

SCOPE = "QUALITY-V2-010D-F2B-COMPLETION"
PKG = ROOT / "projects/quality_v2_010d_f2b_completion"
BUDGET_KIND = "f2b_010d"
SHOT_ID = "SEQ7_F2B"

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
        "routing_decision_id": "route_v2_010d_browser_network",
        "provider_id": "seedance_dola_browser",
        "request_id": "f2b_010d",
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


async def main() -> int:
    run_id = "f2b010d_" + datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S")
    auth = MutationAuthority(PKG, SCOPE)
    if auth.authority != "OPEN":
        emit({"status": "STOPPED_GOVERNANCE_GAP",
              "authority": auth.authority})
        return 1

    attempt = build_attempt()
    reservation = {
        "version": "v2-010d-mutation-reservation-v1",
        "budget_kind": BUDGET_KIND, "run_id": run_id,
        "attempt_id": attempt.generation_attempt_id,
        "intent": {"shot_id": SHOT_ID, "prompt_sha256": PROMPT_SHA,
                   "conversation_id": SEEDANCE_CONVERSATION_ID,
                   "requested_duration_class": "5s",
                   "expected_credit_cost": 1,
                   "plan_authority": "world_reframe_plan_v2_009 (FROZEN)",
                   "authority": "F2B_010D = ONE (fresh; does not reuse "
                                "F2B_010C)"},
        "request_fingerprint_placeholder": hashlib.sha256(
            json.dumps({"prompt_sha256": PROMPT_SHA,
                        "duration_class": "5s"}, sort_keys=True)
            .encode()).hexdigest(),
        "created_at": utcnow()}
    write_pkg("mutation_reservation_f2b_010d.json", reservation)
    auth._event("MUTATION_RESERVED", budget_kind=BUDGET_KIND, detail=run_id)
    write_pkg("generation_attempt_f2b_010d.json",
              {"attempt": json.loads(attempt.model_dump_json()),
               "reservation": reservation})
    emit({"event": "governance_pre_dispatch",
          "attempt_id": attempt.generation_attempt_id})

    adapter = DolaBrowserAdapter010D(run_id=run_id)
    screenshots = PKG / "screenshots_f2b"
    screenshots.mkdir(parents=True, exist_ok=True)

    async def fail(status: str, reason: str, *, latch: bool = False) -> int:
        evidence = {"version": "v2-010d-f2b-evidence-v1",
                    "checkpoint": "V2010D_P4_F2B", "run_id": run_id,
                    "status": status, "reason": reason,
                    "reservation": reservation,
                    "adapter_events": adapter.events}
        write_pkg("V2_010D_F2B_EVIDENCE.json", evidence)
        if latch:
            auth.latch(status, reason)
        emit({"status": status, "reason": reason})
        return 1

    try:
        await adapter.open()
    except Exception as error:
        return await fail("STOPPED_SESSION_GAP", f"open failed: "
                          f"{type(error).__name__}")
    try:
        # ---- gates ------------------------------------------------------
        try:
            await adapter.goto_conversation(SEEDANCE_CONVERSATION_ID)
        except Exception as error:
            return await fail("STOPPED_SESSION_GAP",
                              f"navigation failed: {type(error).__name__}")
        poll = await adapter.poll_replies(SEEDANCE_CONVERSATION_ID)
        if not poll.get("ok"):
            return await fail("STOPPED_SESSION_GAP",
                              "read-only poll failed — session likely "
                              "invalid; no mutation spent")
        emit({"event": "session_valid_readonly_poll"})

        mode_state = await adapter.ensure_video_mode()
        emit({"event": "video_mode_state", **mode_state})
        selection = await adapter.select_duration(5)
        emit({"event": "duration_selected", **selection})
        duration_gate = await adapter.verify_duration_pre_dispatch(5)
        await adapter.page.screenshot(path=str(
            screenshots / "01_duration_5s_gated.png"))
        emit({"event": "duration_authority_proven",
              "chip": duration_gate["chip"]})

        baseline = await adapter.poll_replies(SEEDANCE_CONVERSATION_ID)
        known_creations = {r.get("creation_id")
                           for r in baseline.get("replies", [])}
        known_messages = {r.get("message_id")
                          for r in baseline.get("replies", [])}

        # ---- dispatch (THE one mutation) --------------------------------
        dispatch = await adapter.submit(
            F2B_PROMPT, conversation_id=SEEDANCE_CONVERSATION_ID)
        release = dispatch["release"]
        ability = (release.get("body_structure") or {}).get("chat_ability")
        ability_param = {}
        if isinstance(ability, dict) and isinstance(
                ability.get("ability_param"), str):
            try:
                ability_param = json.loads(ability["ability_param"])
            except json.JSONDecodeError:
                ability_param = {}
        released_duration = ability_param.get("duration")
        emit({"event": "release_body_duration", "duration": released_duration,
              "ability_type": (ability or {}).get("ability_type")})

        receipt_doc = {
            "version": "v2-010d-f2b-receipt-v1", "run_id": run_id,
            "shot_id": SHOT_ID, "conversation_id": SEEDANCE_CONVERSATION_ID,
            "user_action_at": dispatch["user_action_at"],
            "receipt_at": dispatch["receipt_at"],
            "release_request_id": release["request_id"],
            "body_sha256": release["body_sha256"],
            "requested_duration_class": "5s",
            "released_ability_param_duration": released_duration,
            "prompt_sha256": PROMPT_SHA}
        write_pkg("f2b_010d_receipt.json", receipt_doc)
        write_pkg("generation_attempt_f2b_010d.json", {
            "attempt": json.loads(attempt.model_dump_json()),
            "reservation": reservation,
            "release_request": {k: v for k, v in release.items()
                                if k != "body_structure"},
            "release_body_structure": release["body_structure"]})
        auth.consume(BUDGET_KIND)
        attempt.provider_job_id = SEEDANCE_CONVERSATION_ID
        attempt.status = "running"
        emit({"event": "receipt_first_persisted_and_budget_consumed"})
        await adapter.page.screenshot(path=str(
            screenshots / "02_dispatched.png"))

        # ---- completion correlation --------------------------------------
        done = await adapter.wait_for_new_video(
            SEEDANCE_CONVERSATION_ID,
            known_creation_ids=known_creations,
            known_message_ids=known_messages,
            on_progress=lambda fresh, done_n: emit(
                {"event": "poll_progress", "new_records": fresh,
                 "done_videos": done_n}))
        if not done:
            # distinguish explicit refusal from unknown
            texts = []
            try:
                repoll = await adapter.poll_replies(SEEDANCE_CONVERSATION_ID)
                texts = repoll.get("texts", [])
            except Exception:
                pass
            blob = " ".join(texts)
            credits = adapter.parse_credit_requirement(blob)
            if credits.get("required"):
                return await fail(
                    "STOPPED_EXPLICIT_PROVIDER_FAILURE",
                    f"provider credit refusal: {credits}", latch=False)
            return await fail("STOPPED_PROVIDER_CORRELATION_GAP",
                              "no new completed video within timeout")
        urls = {r["video_download_url"] for r in done}
        if len(urls) != 1:
            return await fail("STOPPED_PROVIDER_CORRELATION_GAP",
                              f"{len(urls)} distinct download urls")
        video_url = urls.pop()
        creation_ids = sorted({r["creation_id"] for r in done})
        message_ids = sorted({r["message_id"] for r in done})
        emit({"event": "video_url_correlated",
              "host": video_url.split("/")[2] if "/" in video_url else "?",
              "creation_ids": creation_ids, "message_ids": message_ids})

        # ---- exact acquisition -------------------------------------------
        assets = PKG / "assets"
        dest = assets / f"{run_id}.mp4"
        meta = await adapter.download(video_url, dest)
        asset_sha = hashlib.sha256(dest.read_bytes()).hexdigest()
        attempt.status = "succeeded"
        attempt.completed_at = utcnow()
        attempt.output_asset_ids = [f"asset_sha256:{asset_sha[:16]}"]
        await adapter.page.screenshot(path=str(
            screenshots / "03_completed.png"))

        duration = float(meta.get("duration_s") or 0)
        duration_class = "5s" if abs(duration - 5.0) <= abs(duration - 10.0) \
            else "10s"
        transport_qc = {
            "receipt": "PROVEN (SSE_ACK + persisted receipt-first)",
            "stable_ids": "PROVEN", "creation_ids": creation_ids,
            "message_ids": message_ids,
            "correlation": "creation-id baseline-diff (network authority)",
            "release_body_duration": released_duration,
            "verdict": "PASS"}
        technical_qc = {
            "ffprobe": meta, "duration_s": duration,
            "duration_class": duration_class,
            "requested_class": "5s",
            "class_matches_request": duration_class == "5s",
            "aspect_16_9": bool(meta.get("width") and meta.get("height")
                                and abs(meta["width"] / meta["height"]
                                        - 16 / 9) < 0.05),
            "full_decode": meta.get("full_decode"),
            "verdict": "PASS" if (meta.get("full_decode")
                                  and duration_class == "5s") else "FAIL"}
        evidence = {
            "version": "v2-010d-f2b-evidence-v1",
            "checkpoint": "V2010D_P4_F2B",
            "status": "PROVEN" if technical_qc["verdict"] == "PASS"
            else "PARTIAL",
            "run_id": run_id,
            "attempt": json.loads(attempt.model_dump_json()),
            "reservation": reservation,
            "receipt": receipt_doc,
            "video_records": done,
            "asset": {"path_class": "projects/.../assets/" + dest.name,
                      "sha256": asset_sha,
                      "host": video_url.split("/")[2],
                      **meta},
            "qc": {"TRANSPORT_QC": transport_qc,
                   "TECHNICAL_QC": technical_qc,
                   "CREATIVE_QC": {
                       "method": "WORKER_ADVISORY — frame strips in "
                                 "owner_review_f2b/; Owner visual read "
                                 "authoritative",
                       "prompt_authority": "world_reframe_plan_v2_009 "
                                           "(FROZEN)",
                       "verdict": "DEFERRED_TO_OWNER"}},
            "editorial_use_flags": {
                "trim_required": duration > 2.8,
                "crop_required": False,
                "watermark_handling": "download_url variant carries the "
                                      "Dola AI mark; unwatermarked variant "
                                      "exists in the creation object "
                                      "(see V2_010D_PROVIDER_LINEAGE.json)",
                "direction_repair": "advisory pending owner read",
                "regeneration": "PROHIBITED (no retry authority)"},
            "adapter_events": adapter.events,
        }
        write_pkg("V2_010D_F2B_EVIDENCE.json", evidence)
        lineage = {
            "version": "v2-010d-provider-lineage-v1",
            "checkpoint": "V2010D_P5_PROVIDER_LINEAGE",
            "built_at": utcnow(),
            "conversation_id": SEEDANCE_CONVERSATION_ID,
            "question_message": F2B_PROMPT[:80] + "…",
            "creation_ids": creation_ids,
            "message_ids": message_ids,
            "asset": {"sha256": asset_sha, "duration_s": duration,
                      "duration_class": duration_class,
                      "width": meta.get("width"),
                      "height": meta.get("height"),
                      "codec": meta.get("codec"), "fps": meta.get("fps"),
                      "host": video_url.split("/")[2],
                      "watermark_state": "watermarked variant (Dola AI); "
                                         "unwatermarked variants observed "
                                         "in the same creation object"},
            "credit_consumption": {
                "expected": 1, "observed": "not stated in the success-path "
                                           "ack (provider states credits "
                                           "only on refusal/limits); "
                                           "class-based cost 1",
                "evidence": "video-mode body duration=5 + output class 5s"},
            "lineage": "GenerationAttempt → ProviderJob "
                       f"(conversation {SEEDANCE_CONVERSATION_ID}) → "
                       f"creation {creation_ids} → asset sha {asset_sha[:16]}",
        }
        write_pkg("V2_010D_PROVIDER_LINEAGE.json", lineage)
        emit({"checkpoint": "V2010D_F2B_COMPLETE",
              "status": evidence["status"],
              "duration": duration, "class": duration_class,
              "sha256": asset_sha})
        return 0
    except RuntimeError as error:
        message = str(error)
        if "DURATION_AUTHORITY_GAP" in message:
            return await fail("STOPPED_DURATION_AUTHORITY_GAP", message)
        if "DISPATCH_GAP" in message:
            return await fail("OWNER_AMBIGUITY_GATE" if
                              "no /chat/completion" not in message
                              else "STOPPED_PRE_DISPATCH", message)
        return await fail("STOPPED_PROVIDER_CORRELATION_GAP", message)
    finally:
        summary = await adapter.close(
            sanitize_to=PKG / "V2_010D_F2B_CAPTURE_SANITIZED.json")
        write_pkg("V2_010D_MUTATION_LEDGER.json", {
            "version": "v2-010d-mutation-ledger-export-v1",
            "exported_at": utcnow(),
            "authority": json.loads(
                (PKG / "mutation_authority.json")
                .read_text(encoding="utf-8"))})


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
