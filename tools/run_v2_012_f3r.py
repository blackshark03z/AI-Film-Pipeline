"""V2-012 — F3R_012 dispatch runner (EXACTLY ONE mutation, no retry).

Adapted from the 011D runner. Fail-closed pre-render gates: F1R custody SHA,
locked-F2 SHA, repaired spec frozen, secret audit CLEAN, session valid,
journal fresh, network capture active. ACCOUNT_D native session.

Needle for conversation discovery: 'stands safely beside' — unique to the
repaired prompt (the refused 011D conversation says 'the same swordsman').
"""
from __future__ import annotations

import asyncio
import hashlib
import json
import subprocess
import sys
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
sys.path.insert(0, str(ROOT / "src"))

from dola_010c_capture import NetworkCapture
from dola_010c_session import DolaSessionManager
from dola_010d_adapter_delta import DolaBrowserAdapter010D
from dola_010e_adapter_delta import DolaBrowserAdapter010E
from dola_010e_dispatch_journal import (ASSET_DOWNLOADED, CREATION_BOUND,
                                        DISPATCH_ARMED_EV, MUTATION_RESERVED,
                                        NETWORK_RELEASE_OBSERVED,
                                        SSE_RECEIPT_CAPTURED,
                                        TERMINAL_PROVIDER_FAILURE,
                                        TERMINAL_SUCCESS, DispatchJournal)
from dola_010e_session_router import ACCOUNT_PROFILES
from film_pipeline.core import GenerationAttempt
from film_pipeline.execution import sha256
from mutation_authority import MutationAuthority

SCOPE = "QUALITY-V2-012-F3R-POLICY-REPAIR"
PKG = ROOT / "projects/quality_v2_012_f3r_policy_repair"
P11D = ROOT / "projects/quality_v2_011d_world_matched_context"
SHOT = "F3R_012"
F1R_SHA = "b879f21586392fa7463021f60853b1aa99fecb286890dad1b3f192c6dd805171"
F2_SHA = "ada66463983636e505b181d5b81b10c6a7f4da8cdd1a80aff55880dd8fd820de"

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

RECENT_CONVS_JS = """async () => {
  const params = new URLSearchParams({
    version_code: "20800", language: "ja", device_platform: "web",
    doubao_device_platform: "web", aid: "495671", real_aid: "495671",
    pkg_type: "release_version", pc_version: "3.39.1",
    doubao_pc_version: "3.39.1", region: "VN", sys_region: "VN",
    samantha_web: "1", web_platform: "browser",
    "use-olympus-account": "1", web_tab_id: crypto.randomUUID(),
  });
  const resp = await fetch("/im/chain/recent_conv?" + params.toString(), {
    method: "POST",
    headers: {"Content-Type": "application/json; encoding=utf-8",
              "agw-js-conv": "str",
              "Accept": "application/json, text/plain, */*"},
    credentials: "include",
    body: JSON.stringify({cmd: 3200, uplink_body: {
      pull_recent_conv_chain_uplink_body: {limit: 10,
        message_count_per_conv: 2, api_version: 1, conv_version: 0,
        direction: 3, option: {not_need_message: false,
          need_complete_conversation: true, need_coco_conversation: true,
          need_coco_bot: true, need_pc_pin_chain: true,
          pc_pin_query_type: 0}}},
      sequence_id: crypto.randomUUID(), channel: 2, version: "1"})});
  const data = await resp.json();
  const cells = ((data.downlink_body || {})
    .pull_recent_conv_chain_downlink_body || {}).cells || [];
  return cells.map(c => (c.conversation || {}).conversation_id || c.id)
              .filter(id => /^\\d{10,}$/.test(String(id)));
}"""

PULL_JS = """async ({conversationId}) => {
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
        conversation_id: conversationId,
        anchor_index: Number.MAX_SAFE_INTEGER, conversation_type: 3,
        direction: 1, limit: 10, ext: {}, filter: {index_list: []},
        evaluate_ab_params: "", evaluate_common_params: ""}},
      sequence_id: crypto.randomUUID(), channel: 2, version: "1"})});
  const data = await resp.json();
  const messages = ((data.downlink_body || {})
    .pull_singe_chain_downlink_body || {}).messages || [];
  const rows = [];
  for (const m of messages) {
    let blocks = m.content;
    if (typeof blocks === "string") {
      try { blocks = JSON.parse(blocks); } catch (e) { blocks = []; }
    }
    let text = "";
    const creations = [];
    for (const b of (Array.isArray(blocks) ? blocks : [])) {
      if (b.block_type === 2074) {
        for (const c of (((b.content || {}).creation_block || {})
            .creations || [])) {
          creations.push({id: c.id ? String(c.id) : null, type: c.type,
            v_status: (c.video || {}).status ?? null,
            download_url: (c.video || {}).download_url || null});
        }
      } else if (b.block_type === 10000) {
        text += (((b.content || {}).text_block || {}).text || "");
      }
    }
    rows.push({message_id: String(m.message_id),
               create_time: m.create_time, text: text.slice(0, 300),
               creations});
  }
  return rows;
}"""


def utcnow() -> str:
    return datetime.now(timezone.utc).isoformat()


def emit(payload: dict) -> None:
    print(json.dumps(payload, ensure_ascii=False, default=str), flush=True)


def write_pkg(name: str, payload: dict) -> None:
    (PKG / name).write_text(json.dumps(payload, indent=1,
                                       ensure_ascii=False), encoding="utf-8")


def gate_fail(status: str, reason: str) -> int:
    emit({"status": status, "reason": reason})
    return 1


def build_attempt(prompt: str) -> GenerationAttempt:
    identity = {
        "shot_spec_hash": sha256({"shot_id": SHOT,
                                  "plan": "SEQ7_WORLD_LOCK_FROM_F2 + "
                                          "V2-012 policy-compliant repair"}),
        "prompt_plan_hash": sha256({"prompt_sha256": hashlib.sha256(
            prompt.encode()).hexdigest()}),
        "routing_decision_id": "route_v2_012_f3r",
        "provider_id": "seedance_dola_browser",
        "request_id": "f3r_012",
        "started_at": utcnow(),
    }
    return GenerationAttempt(
        generation_attempt_id="attempt_" + sha256(identity),
        shot_id=SHOT, shot_spec_version=1,
        shot_spec_hash=identity["shot_spec_hash"],
        prompt_plan_hash=identity["prompt_plan_hash"],
        routing_decision_id=identity["routing_decision_id"],
        provider_id="seedance_dola_browser", status="created",
        started_at=identity["started_at"])


async def run(opaque: str) -> int:
    spec_path = PKG / "V2_012_F3R_REPAIRED_SPEC.json"
    if not spec_path.exists():
        return gate_fail("STOPPED_GOVERNANCE_GAP", "repaired spec missing")
    spec = json.loads(spec_path.read_text(encoding="utf-8"))
    spec_prompt = spec["prompt"]
    prompt_sha = hashlib.sha256(spec_prompt.encode()).hexdigest()
    budget_kind = spec["budget_kind"]

    # ---- fail-closed pre-render gates -----------------------------------
    f1r = P11D / "assets" / "f1r.mp4"
    if hashlib.sha256(f1r.read_bytes()).hexdigest() != F1R_SHA:
        return gate_fail("STOPPED_CUSTODY_MISMATCH", "F1R custody")
    f2 = P11D / "inputs_F2_proof.mp4"
    if hashlib.sha256(f2.read_bytes()).hexdigest() != F2_SHA:
        return gate_fail("STOPPED_CUSTODY_MISMATCH", "locked F2 custody")
    audit = PKG / "V2_012_SECRET_AUDIT.json"
    if not audit.exists() or json.loads(
            audit.read_text(encoding="utf-8")).get("verdict") != "CLEAN":
        return gate_fail("STOPPED_PRERENDER_GATE", "secret audit not CLEAN")

    journal_path = PKG / "dispatch_journal_f3r_012.jsonl"
    if journal_path.exists():
        journal_path.unlink()
    slot_scope = PKG / "slot_f3r_012"
    auth = MutationAuthority(slot_scope, SCOPE + '/F3R_012')
    if auth.authority != 'OPEN':
        emit({'status': 'STOPPED_GOVERNANCE_GAP',
              'authority': auth.authority, 'slot': SHOT})
        return 1
    attempt = build_attempt(spec_prompt)
    journal = DispatchJournal(journal_path, attempt.generation_attempt_id)
    journal.append(MUTATION_RESERVED, {
        "budget_kind": budget_kind, "account_opaque_id": opaque,
        "prompt_sha256": prompt_sha})
    auth._event("MUTATION_RESERVED", budget_kind=budget_kind, detail=SHOT)
    reservation = {"version": "v2-012-reservation-v1", "shot": SHOT,
                   "attempt_id": attempt.generation_attempt_id,
                   "account_opaque_id": opaque,
                   "prompt_sha256": prompt_sha, "created_at": utcnow()}
    write_pkg("mutation_reservation_f3r_012.json", reservation)
    write_pkg("generation_attempt_f3r_012.json", {
        "attempt": json.loads(attempt.model_dump_json()),
        "reservation": reservation})
    emit({"event": "reserved", "shot": SHOT, "account": opaque})

    manager = DolaSessionManager(profile_dir=ACCOUNT_PROFILES / opaque)
    await manager.launch_browser()
    page = manager._page
    screenshots = PKG / "screenshots_f3r_012"
    screenshots.mkdir(parents=True, exist_ok=True)

    def fail(status: str, reason: str, *, latch: bool = False) -> int:
        if latch:
            auth.latch(status, reason[:250])
            journal.append("AMBIGUITY_LATCHED", {"status": status})
        else:
            journal.append(TERMINAL_PROVIDER_FAILURE,
                           {"status": status, "reason": reason[:250]})
        write_pkg("V2_012_F3R_EVIDENCE.json", {
            "version": "v2-012-evidence-v1", "shot": SHOT,
            "status": status, "reason": reason,
            "journal_events": journal.events})
        emit({"status": status, "reason": reason})
        return 1

    try:
        await page.goto("https://www.dola.com/chat", timeout=60000,
                        wait_until="domcontentloaded")
        state = await page.evaluate(LOGIN_CHECK_JS)
        stable = 0
        waited = 0
        while waited < 900 and not (state.get("composer")
                                    and not state.get("logged_out")):
            await asyncio.sleep(5)
            waited += 5
            state = await page.evaluate(LOGIN_CHECK_JS)
            stable = stable + 1 if (state.get("composer")
                                    and not state.get("logged_out")) else 0
            if stable >= 3:
                break
        if not (state.get("composer") and not state.get("logged_out")):
            return fail("USER_LOGIN_REQUIRED",
                        f"{opaque} session not authenticated")
        emit({"event": "session_authenticated", "account": opaque})

        convs = await page.evaluate(RECENT_CONVS_JS)
        baseline_creations: set[str] = set()
        for conv in convs[:6]:
            try:
                rows = await page.evaluate(PULL_JS,
                                           {"conversationId": conv})
                for row in rows:
                    for c in row.get("creations", []):
                        if c.get("id"):
                            baseline_creations.add(c["id"])
            except Exception:
                continue
        emit({"event": "baseline", "conversations": len(convs),
              "known_creations": len(baseline_creations)})

        adapter = DolaBrowserAdapter010E(run_id="f3r_012_" +
                                         datetime.now(timezone.utc)
                                         .strftime("%Y%m%dT%H%M%S"))
        adapter.manager = manager
        adapter.page = page
        adapter.capture = NetworkCapture(manager._context, page,
                                         adapter.run_id)
        await adapter.capture.start()

        await adapter.ensure_video_mode()
        await adapter.select_duration(5)
        gate = await adapter.verify_duration_pre_dispatch(5)
        await page.screenshot(path=str(screenshots / "01_5s_armed.png"))
        emit({"event": "duration_gated", "chip": gate["chip"]})

        fingerprint = hashlib.sha256(json.dumps(
            {"prompt_sha256": prompt_sha, "duration_class": 5},
            sort_keys=True).encode()).hexdigest()
        journal.append(DISPATCH_ARMED_EV, {
            "attempt_id": attempt.generation_attempt_id,
            "account_opaque_id": opaque, "duration_class": 5,
            "request_fingerprint": fingerprint,
            "capture_run_id": adapter.run_id,
            "spec": "V2_012_F3R_REPAIRED_SPEC.json",
            "world_lock": "SEQ7_WORLD_LOCK_FROM_F2 (011D package)"})

        adapter.attach_journal(
            journal, expected_needle=spec_prompt, index_boundary=0,
            known_creation_ids=baseline_creations,
            on_receipt_captured=lambda receipt: auth.consume(budget_kind))

        dispatch = await adapter.submit(spec_prompt, conversation_id="HOME")
        release = dispatch["release"]
        if not await adapter.wait_journal_state("RELEASE_OBSERVED", 30):
            return fail("OWNER_AMBIGUITY_GATE", "release not observed",
                        latch=True)
        journal.append(NETWORK_RELEASE_OBSERVED, {
            "account_binding": {
                "generation_attempt_id": attempt.generation_attempt_id,
                "account_opaque_id": opaque,
                "request_fingerprint": fingerprint},
            "binding_rule": "IMMUTABLE after this event"})
        refined = await adapter.verify_release_body(release["request_id"])
        emit({"event": "release_refined", **{k: refined.get(k)
                                             for k in ("duration",
                                                       "needle_present")}})
        if refined.get("duration") not in (5, None):
            return fail("OWNER_AMBIGUITY_GATE",
                        f"released duration={refined.get('duration')} ≠ 5",
                        latch=True)
        if not await adapter.wait_journal_state("RECEIPT_CAPTURED", 120):
            return fail("OWNER_AMBIGUITY_GATE",
                        "receipt not captured within 120s "
                        "(release confirmed)", latch=True)
        attempt.provider_job_id = "new_conversation"
        attempt.status = "running"
        write_pkg("generation_attempt_f3r_012.json", {
            "attempt": json.loads(attempt.model_dump_json()),
            "reservation": reservation,
            "release_request": {k: v for k, v in release.items()
                                if k != "body_structure"}})
        emit({"event": "receipt_captured"})

        # ---- discover the NEW conversation (repaired-prompt needle) -------
        new_conv = None
        done_records = []
        deadline = asyncio.get_event_loop().time() + 1500
        attempt_n = 0
        while asyncio.get_event_loop().time() < deadline:
            attempt_n += 1
            try:
                convs = await page.evaluate(RECENT_CONVS_JS)
            except Exception:
                await page.wait_for_timeout(5000)
                continue
            for conv in convs[:6]:
                try:
                    rows = await page.evaluate(PULL_JS,
                                               {"conversationId": conv})
                except Exception:
                    continue
                needle = "stands safely beside"
                has_prompt = any(needle in (r.get("text") or "")
                                 for r in rows)
                if not has_prompt:
                    continue
                new_conv = conv
                done = [c for r in rows for c in r.get("creations", [])
                        if c.get("type") == 2 and c.get("download_url")
                        and c.get("id") not in baseline_creations]
                if done:
                    done_records = done
                newest = [r.get("text", "")[:120] for r in rows[:3]]
                if attempt_n % 6 == 1:
                    emit({"step": "conv_state", "attempt": attempt_n,
                          "conv": conv,
                          "creations": [{k: c.get(k) for k in
                                         ("id", "type", "v_status")}
                                        for r in rows
                                        for c in r.get("creations", [])],
                          "texts": newest})
                refusal = any("生成できません" in (r.get("text") or "")
                              for r in rows[:4])
                if refusal and not any(r.get("creations")
                                       for r in rows[:4]):
                    return fail("STOPPED_REPEATED_PROVIDER_POLICY_REFUSAL",
                                f"provider refusal: {newest}")
            if done_records:
                break
            await page.wait_for_timeout(10000)
        if not done_records:
            return fail("STOPPED_PROVIDER_CORRELATION_GAP",
                        "no completed video for the new conversation "
                        "within 1500s")
        urls = {r["download_url"] for r in done_records}
        if len(urls) != 1:
            return fail("STOPPED_PROVIDER_CORRELATION_GAP",
                        f"{len(urls)} distinct urls")
        video_url = urls.pop()
        creation_ids = sorted({r["id"] for r in done_records})
        journal.append(CREATION_BOUND, {"creation_ids": creation_ids,
                                        "conversation_id": new_conv})
        emit({"event": "creation_bound", "creation_ids": creation_ids,
              "conversation_id": new_conv})

        dest = PKG / "assets" / "f3r_012.mp4"
        dest.parent.mkdir(exist_ok=True)
        candidate = dest.with_suffix(".mp4.candidate")
        try:
            with urllib.request.urlopen(
                    urllib.request.Request(video_url), timeout=300) as resp, \
                    candidate.open("wb") as out:
                total = 0
                while True:
                    part = resp.read(256 * 1024)
                    if not part:
                        break
                    total += len(part)
                    out.write(part)
        except Exception as error:
            candidate.unlink(missing_ok=True)
            return fail("STOPPED_PROVIDER_CORRELATION_GAP",
                        f"download failed: {type(error).__name__}")
        asset_sha = hashlib.sha256(candidate.read_bytes()).hexdigest()
        candidate.replace(dest)
        journal.append(ASSET_DOWNLOADED, {"sha256": asset_sha,
                                          "size": total})
        journal.append(TERMINAL_SUCCESS, {"sha256": asset_sha})
        attempt.status = "succeeded"
        attempt.completed_at = utcnow()
        attempt.output_asset_ids = [f"asset_sha256:{asset_sha[:16]}"]

        probe = subprocess.run(
            ["ffprobe", "-v", "error", "-show_entries",
             "format=duration:stream=width,height,codec_name,r_frame_rate,nb_frames",
             "-of", "json", str(dest)], capture_output=True, text=True)
        meta = json.loads(probe.stdout or "{}")
        stream = next((s for s in meta.get("streams", [])
                       if "width" in s), {})
        frames_dir = PKG / "frames_f3r_012"
        frames_dir.mkdir(exist_ok=True)
        subprocess.run(["ffmpeg", "-y", "-v", "error", "-i", str(dest),
                        "-fps_mode", "passthrough", "-start_number", "0",
                        str(frames_dir / "F3R12_%04d.png")],
                       capture_output=True)
        n_frames = len(list(frames_dir.glob("F3R12_*.png")))
        write_pkg("V2_012_F3R_EVIDENCE.json", {
            "version": "v2-012-evidence-v1", "shot": SHOT,
            "status": "ACQUIRED_AWAITING_CREATIVE_QC",
            "attempt": json.loads(attempt.model_dump_json()),
            "journal_events": journal.events,
            "conversation_id": new_conv,
            "creation_ids": creation_ids,
            "asset": {"path": str(dest), "sha256": asset_sha,
                      "size": total, "host": video_url.split("/")[2],
                      "duration_s": meta.get("format", {}).get("duration"),
                      "width": stream.get("width"),
                      "height": stream.get("height"),
                      "codec": stream.get("codec_name"),
                      "fps": stream.get("r_frame_rate"),
                      "nb_frames": stream.get("nb_frames")},
            "frames_dir": str(frames_dir),
            "frames_extracted": n_frames})
        emit({"checkpoint": "V2012_F3R_012_ACQUIRED",
              "sha256": asset_sha[:16],
              "duration": meta.get("format", {}).get("duration"),
              "frames": n_frames})
        return 0
    except Exception as error:
        state_before = journal.state
        if journal.has("NETWORK_RELEASE_OBSERVED") or \
                state_before in ("RELEASE_OBSERVED", "RECEIPT_CAPTURED",
                                 "PROVIDER_JOB_BOUND"):
            return fail("OWNER_AMBIGUITY_GATE",
                        f"failure after release: {type(error).__name__}: "
                        f"{error}", latch=True)
        return fail("STOPPED_PRE_DISPATCH",
                    f"failure: {type(error).__name__}: {error}")
    finally:
        write_pkg("V2_012_MUTATION_LEDGER.json", {
            "version": "v2-012-mutation-ledger-v1", "shot": SHOT,
            "exported_at": utcnow(),
            "authority": json.loads((slot_scope / "mutation_authority.json")
                                    .read_text(encoding="utf-8")),
            "journal": journal.events})
        await manager.close()


if __name__ == "__main__":
    opaque = sys.argv[1] if len(sys.argv) > 1 else "ACCOUNT_D"
    raise SystemExit(asyncio.run(run(opaque)))
