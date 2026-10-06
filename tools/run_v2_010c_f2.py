"""AI-FILM-QUALITY-V2-010C — F2A/F2B through the qualified browser transport.

Runs ONE authorized Seedance video generation per shot (budget kinds
f2a_dola / f2b_dola; the last two slots of the HARD MAX 4), using prompts
built from the FROZEN V2-009 world-reframe plan (traversal geometry +
causal environment + forbidden geography, verbatim authority).

QC is separated per package contract:
    TRANSPORT_QC  — receipt/IDs/correlation proven (network authority)
    TECHNICAL_QC  — ffprobe + full decode + duration/aspect sanity
    CREATIVE_QC   — worker advisory from frame strips; Owner read is
                    authoritative (same limitation as V2-008)
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

from dola_010c_browser_adapter import (DolaBrowserAdapter,
                                       SEEDANCE_CONVERSATION_ID)
from film_pipeline.core import GenerationAttempt
from film_pipeline.execution import sha256
from mutation_authority import MutationAuthority

SCOPE = "QUALITY-V2-010C-DOLA-FULLSTACK"
PKG = ROOT / "projects/quality_v2_010c_dola_fullstack"
PLAN = json.loads((ROOT / "projects/quality_v2_009_world_geography_reframe/"
                   "world_reframe_plan_v2_009.json").read_text(encoding="utf-8"))
WORLD_REF = (ROOT / "projects/quality_v2_008_world_anchored_live/"
             "world_reference_frame.png")

CHARACTER = ("a swordsman in flowing white robes with a topknot and ribbon")
WORLD = ("a continuous rock ridge closing a narrow stone pass — the only "
         "walkable gap — with the mountain road funneling into the opening "
         "and continuing beyond it, grass on both sides bending in the wind")

F2A_PROMPT = (
    "Generate a 5-second cinematic video, 16:9, locked camera. "
    + CHARACTER + " walks along a mountain road that visibly funnels toward "
    + WORLD + " A hard gust channels through the pass against him: his robes "
    "press flat against his body on the windward side and stream violently "
    "leeward, his hair and headband stream tangent to the wind, and he leans "
    "INTO the gust, center of gravity dropping, forcing every forward step "
    "against the wind with visible muscular effort. He commits into the "
    "choke point and the shot ends just inside the pass opening, committed "
    "forward, rock boundary on both lateral sides in the same frames, "
    "crossing not yet completed. The road is visible entering the pass. "
    "No sword drawn, no sheltering or bracing on the rock, no loitering, "
    "no freestanding decorative gate in an open field, no metal gate, "
    "no lightning.")

F2B_PROMPT = (
    "Generate a 5-second cinematic video, 16:9, locked camera. "
    + CHARACTER + " forces through the last meters of " + WORLD + " The hard "
    "gust funnels through the pass against the travel direction, streaming "
    "his robes and headband leeward as he pushes through the opening with "
    "visible effort. He emerges beyond the pass onto the open road that "
    "continues onward and keeps walking forward without ever turning back: "
    "the rock boundary is BEHIND him, visible on both lateral sides of the "
    "opening in the same frames, and the road ahead continues onward — the "
    "traversal mattered. No turning back toward the opening, no interacting "
    "with the rock, no loitering or sheltering, no freestanding decorative "
    "gate, no metal gate, no lightning.")

SHOTS = {
    "f2a": {"shot_id": "SEQ7_F2A", "budget_kind": "f2a_dola",
            "prompt": F2A_PROMPT, "reference": None,
            "plan_key": "f2a_enter_choke_point"},
    "f2b": {"shot_id": "SEQ7_F2B", "budget_kind": "f2b_dola",
            "prompt": F2B_PROMPT, "reference": WORLD_REF,
            "plan_key": "f2b_exit_choke_point"},
}


def utcnow() -> str:
    return datetime.now(timezone.utc).isoformat()


def emit(payload: dict) -> None:
    print(json.dumps(payload, ensure_ascii=False, default=str), flush=True)


def write_pkg(name: str, payload: dict) -> Path:
    path = PKG / name
    path.write_text(json.dumps(payload, indent=1, ensure_ascii=False),
                    encoding="utf-8")
    return path


def build_attempt(shot_id: str, prompt: str) -> GenerationAttempt:
    identity = {
        "shot_spec_hash": sha256({"shot_id": shot_id,
                                  "plan": "world_reframe_plan_v2_009"}),
        "prompt_plan_hash": sha256({"prompt_sha256":
                                    hashlib.sha256(
                                        prompt.encode()).hexdigest()}),
        "routing_decision_id": "route_v2_010c_browser_network",
        "provider_id": "seedance_dola_browser",
        "request_id": shot_id.lower(),
        "started_at": utcnow(),
    }
    return GenerationAttempt(
        generation_attempt_id="attempt_" + sha256(identity),
        shot_id=shot_id, shot_spec_version=1,
        shot_spec_hash=identity["shot_spec_hash"],
        prompt_plan_hash=identity["prompt_plan_hash"],
        routing_decision_id=identity["routing_decision_id"],
        provider_id="seedance_dola_browser", status="created",
        started_at=identity["started_at"])


async def run_shot(key: str) -> int:
    spec = SHOTS[key]
    run_id = f"{key}_" + datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S")
    prompt_sha = hashlib.sha256(spec["prompt"].encode()).hexdigest()

    auth = MutationAuthority(PKG, SCOPE)
    if auth.authority != "OPEN":
        emit({"status": "STOPPED_GOVERNANCE_GAP", "authority": auth.authority})
        return 1
    attempt = build_attempt(spec["shot_id"], spec["prompt"])
    reservation = {
        "version": "v2-010c-mutation-reservation-v1",
        "budget_kind": spec["budget_kind"], "run_id": run_id,
        "attempt_id": attempt.generation_attempt_id,
        "intent": {"shot_id": spec["shot_id"], "prompt_sha256": prompt_sha,
                   "conversation_id": SEEDANCE_CONVERSATION_ID,
                   "plan_authority": "world_reframe_plan_v2_009 (FROZEN)",
                   "reference_frame_sha256":
                       hashlib.sha256(spec["reference"].read_bytes())
                       .hexdigest()[:16] if spec["reference"] else None},
        "request_fingerprint_placeholder": hashlib.sha256(
            json.dumps({"prompt_sha256": prompt_sha}, sort_keys=True)
            .encode()).hexdigest(),
        "created_at": utcnow()}
    write_pkg(f"mutation_reservation_{key}.json", reservation)
    auth._event("MUTATION_RESERVED", budget_kind=spec["budget_kind"],
                detail=run_id)

    adapter = DolaBrowserAdapter(run_id=run_id)
    await adapter.open()
    evidence: dict = {}
    try:
        await adapter.goto_conversation(SEEDANCE_CONVERSATION_ID)
        video_mode = await adapter.enable_video_mode()
        # Reference-attach is deliberately NOT exercised: the composer file
        # input surface is unreversed in 010C and a blind attach could hit
        # the wrong input (e.g. profile photo). F2B's world authority is
        # carried by the frozen plan text; CREATIVE_QC judges the result.
        reference_state = False
        poll = await adapter.poll_replies(SEEDANCE_CONVERSATION_ID)
        baseline_creations = {r.get("creation_id")
                              for r in poll.get("replies", [])}
        baseline_messages = {r.get("message_id")
                             for r in poll.get("replies", [])}

        dispatch = await adapter.submit(
            spec["prompt"], conversation_id=SEEDANCE_CONVERSATION_ID)
        release = dispatch["release"]
        receipt_doc = {
            "version": "v2-010c-f2-receipt-v1", "shot_id": spec["shot_id"],
            "run_id": run_id, "conversation_id": SEEDANCE_CONVERSATION_ID,
            "user_action_at": dispatch["user_action_at"],
            "receipt_at": dispatch["receipt_at"],
            "release_request_id": release["request_id"],
            "body_sha256": release["body_sha256"],
            "video_mode_text": video_mode,
            "reference_attached": reference_state,
            "prompt_sha256": prompt_sha}
        write_pkg(f"{key}_receipt.json", receipt_doc)
        write_pkg(f"generation_attempt_{key}.json", {
            "attempt": json.loads(attempt.model_dump_json()),
            "reservation": reservation,
            "release_request": {k: v for k, v in release.items()
                                if k != "body_structure"},
            "release_body_structure": release["body_structure"]})
        auth.consume(spec["budget_kind"])
        attempt.provider_job_id = SEEDANCE_CONVERSATION_ID
        attempt.status = "running"
        emit({"event": "receipt_first_persisted", "shot": spec["shot_id"],
              "video_mode": video_mode, "reference": reference_state})

        done = await adapter.wait_for_new_video(
            SEEDANCE_CONVERSATION_ID,
            known_creation_ids=baseline_creations,
            known_message_ids=baseline_messages,
            on_progress=lambda fresh, done_n: emit(
                {"event": "poll_progress", "shot": spec["shot_id"],
                 "new_records": fresh, "done_videos": done_n}))
        if not done:
            raise RuntimeError("CORRELATION_GAP: no new completed video")
        urls = {r["video_download_url"] for r in done}
        if len(urls) != 1:
            raise RuntimeError(f"CORRELATION_GAP: {len(urls)} distinct urls")
        video_url = urls.pop()
        assets = PKG / "assets"
        dest = assets / f"{run_id}.mp4"
        meta = await adapter.download(video_url, dest)
        asset_sha = hashlib.sha256(dest.read_bytes()).hexdigest()
        attempt.status = "succeeded"
        attempt.completed_at = utcnow()
        attempt.output_asset_ids = [f"asset_sha256:{asset_sha[:16]}"]

        # ---- separated QC -------------------------------------------------
        transport_qc = {
            "receipt": "PROVEN", "stable_ids": "PROVEN",
            "creation_ids": sorted({r["creation_id"] for r in done}),
            "message_ids": sorted({r["message_id"] for r in done}),
            "correlation": "creation-id equality (baseline-diffed, "
                           "network authority)",
            "verdict": "PASS"}
        duration = float(meta.get("duration_s") or 0)
        # provider duration classes: 5s or 10s (observed; 動画を作成 default
        # is 10s even when the prompt says 5) — either is trim-compatible
        # with the 2.8s editorial slots (V2-008 trimmed 8s sources)
        duration_class_ok = min(abs(duration - 5.0), abs(duration - 10.0)) <= 1.5
        technical_qc = {
            "ffprobe": meta,
            "duration_s": duration,
            "duration_class": "5s" if abs(duration - 5.0) <=
                              abs(duration - 10.0) else "10s",
            "duration_class_ok": duration_class_ok,
            "aspect_16_9": bool(meta.get("width") and meta.get("height")
                                and abs(meta["width"] / meta["height"]
                                        - 16 / 9) < 0.05),
            "full_decode": meta.get("full_decode"),
            "verdict": "PASS" if (meta.get("full_decode")
                                  and duration_class_ok) else "FAIL"}
        creative_qc = {
            "method": "WORKER_ADVISORY — frame-strip extraction deferred to "
                      "the owner review packet; Owner visual read is "
                      "authoritative (V2-008 limitation stands)",
            "prompt_authority": "world_reframe_plan_v2_009 (FROZEN): "
                                + spec["plan_key"],
            "verdict": "DEFERRED_TO_OWNER"}

        evidence = {
            "version": "v2-010c-f2-evidence-v1",
            "checkpoint": f"V2010C_P7_{key.upper()}",
            "shot_id": spec["shot_id"], "run_id": run_id,
            "attempt": json.loads(attempt.model_dump_json()),
            "reservation": reservation,
            "receipt": receipt_doc,
            "video_records": done,
            "asset": {"path_class": "projects/.../assets/" + dest.name,
                      "sha256": asset_sha, **meta},
            "qc": {"TRANSPORT_QC": transport_qc, "TECHNICAL_QC": technical_qc,
                   "CREATIVE_QC": creative_qc},
            "adapter_events": adapter.events,
        }
        status = "PROVEN" if technical_qc["verdict"] == "PASS" else "PARTIAL"
        evidence["status"] = status
        write_pkg(f"V2_010C_{key.upper()}_EVIDENCE.json", evidence)
        emit({"checkpoint": f"V2010C_{key.upper()}_COMPLETE",
              "status": status, "asset_sha256": asset_sha[:16],
              "meta": meta})
        return 0
    except RuntimeError as error:
        evidence = {
            "version": "v2-010c-f2-evidence-v1",
            "checkpoint": f"V2010C_P7_{key.upper()}",
            "shot_id": spec["shot_id"], "run_id": run_id,
            "status": "STOPPED_PROVIDER_CORRELATION_GAP",
            "reason": str(error),
            "reservation": reservation,
            "adapter_events": adapter.events}
        write_pkg(f"V2_010C_{key.upper()}_EVIDENCE.json", evidence)
        # release happened (submit correlates before raising only for
        # dispatch gaps); if the receipt was persisted the budget was
        # consumed — correlation gaps NEVER latch (receipt was proven)
        emit({"status": evidence["status"], "reason": str(error)})
        return 1
    finally:
        await adapter.close(
            sanitize_to=PKG / f"V2_010C_{key.upper()}_CAPTURE_SANITIZED.json")


async def main() -> int:
    which = sys.argv[1] if len(sys.argv) > 1 else "f2a"
    if which not in SHOTS:
        emit({"status": "STOPPED_GOVERNANCE_GAP", "reason": "unknown shot"})
        return 1
    return await run_shot(which)


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
