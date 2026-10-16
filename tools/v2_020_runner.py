"""V2-020 — production runner library (browser wiring for the orchestrator).

Every provider-facing behavior is ported from the live-proven 010E/012
machinery (receipt-first journal, needle discovery with baseline creations,
AMBIGUOUS_POST_DISPATCH discipline, host-allowlisted downloads). New in
V2-020: model verification on the release body, deep video_list variant
resolution on the bound creation, normalized provider events, orchestrator
durable state after EVERY transition.

One browser at a time. No retries. No latest-card correlation.
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
from dola_010e_dispatch_journal import (
    ASSET_DOWNLOADED, CREATION_BOUND, DISPATCH_ARMED_EV, MUTATION_RESERVED,
    NETWORK_RELEASE_OBSERVED, SSE_RECEIPT_CAPTURED, TERMINAL_SUCCESS,
    DispatchJournal)
from dola_010e_session_router import ACCOUNT_PROFILES
from film_pipeline.providers.dola_production import (
    DolaAssetVariantResolver, VariantAuthority)
from film_pipeline.providers.dola_production.observability import (
    decode_media_url, normalize_poll_payload)
from film_pipeline.providers.dola_production.variants import (
    _host_allowed, extract_renditions)

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

# raw creations incl. the video_model JSON STRING (deep surface)
PULL_RAW_JS = """async ({conversationId}) => {
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
    const contentRaw = (typeof m.content === "string")
      ? m.content : JSON.stringify(m.content || []);
    for (const b of (Array.isArray(blocks) ? blocks : [])) {
      if (b.block_type === 2074) {
        for (const c of (((b.content || {}).creation_block || {})
            .creations || [])) {
          creations.push({id: c.id ? String(c.id) : null, type: c.type,
            status: (c.video || {}).status ?? null,
            download_url: (c.video || {}).download_url || null,
            video_model_raw: (c.video || {}).video_model || null});
        }
      } else if (b.block_type === 10000) {
        text += (((b.content || {}).text_block || {}).text || "");
      }
    }
    rows.push({message_id: String(m.message_id),
               create_time: m.create_time, text: text.slice(0, 2000),
               content_raw: contentRaw, creations});
  }
  return rows;
}"""

# "クレジット" ALONE appears in normal ACK credit statements
# ("本日の残りは2動画クレジットです") — only insufficient-credit or
# generation-refused phrasings are refusals (V2-020 live lesson)
CONSENT_DISMISS_JS = """() => {
  const buttons = Array.from(document.querySelectorAll(
      'button, [role="button"], a'));
  const hit = buttons.find(b => /同意する|同意|'
      + 'Accept all|Accept|Agree|I agree/i.test((b.innerText || '').trim()));
  if (hit) { hit.click(); return true; }
  return false;
}"""

REFUSAL_MARKERS = ("生成できません", "无法生成", "不能生成",
                   "unable to generate", "cannot generate",
                   "クレジットが足りません", "クレジットが不足",
                   "残りは0", "クレジットが0")


def utcnow() -> str:
    return datetime.now(timezone.utc).isoformat()


def emit(payload: dict) -> None:
    print(json.dumps(payload, ensure_ascii=False, default=str), flush=True)


class RunnerEvents:
    """Observability sink (Phase 4): normalized events to jsonl."""

    def __init__(self, path: Path) -> None:
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def append(self, events) -> None:
        with self.path.open("a", encoding="utf-8") as handle:
            for event in events:
                handle.write(event.model_dump_json() + "\n")


def ffprobe_json(path: Path) -> dict:
    probe = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries",
         "format=duration:stream=index,codec_type,codec_name,width,height,"
         "r_frame_rate,nb_frames", "-of", "json", str(path)],
        capture_output=True, text=True)
    return json.loads(probe.stdout or "{}")


def decode_ok(path: Path) -> bool:
    return subprocess.run(
        ["ffmpeg", "-v", "error", "-xerror", "-i", str(path),
         "-map", "0:v:0", "-f", "null", "-"],
        capture_output=True).returncode == 0


def frame_metrics(frames_dir: Path) -> dict:
    """Deterministic pixel metrics (PIL-only): luma, saturation, black,
    freeze, motion."""
    from PIL import Image
    import statistics

    paths = sorted(frames_dir.glob("*.png"))
    lumas, sats = [], []
    for p in paths:
        with Image.open(p) as im:
            small = im.convert("RGB").resize((160, 90))
            gray = small.convert("L")
            pixels = list(gray.getdata())
            lumas.append(sum(pixels) / len(pixels))
            hsv = small.convert("HSV").split()[1]
            s_values = list(hsv.getdata())
            sats.append(sum(s_values) / len(s_values) / 255.0)
    mads = []
    for i in range(1, len(paths)):
        with Image.open(paths[i]) as a, Image.open(paths[i - 1]) as b:
            ga = list(a.convert("L").resize((160, 90)).getdata())
            gb = list(b.convert("L").resize((160, 90)).getdata())
            mads.append(sum(abs(x - y) for x, y in zip(ga, gb))
                        / len(ga))
    n = len(paths)
    return {
        "frames": n,
        "mean_luma": round(statistics.mean(lumas), 2) if lumas else None,
        "mean_saturation": round(statistics.mean(sats), 4) if sats else None,
        "black_frame_ratio": round(
            sum(1 for v in lumas if v < 16) / n, 4) if n else 1.0,
        "freeze_frame_ratio": round(
            sum(1 for v in mads if v < 0.02) / len(mads), 4)
        if mads else 1.0,
        "motion_mad": round(statistics.median(mads), 3) if mads else 0.0,
    }


def extract_frames(asset: Path, frames_dir: Path) -> int:
    frames_dir.mkdir(parents=True, exist_ok=True)
    subprocess.run(
        ["ffmpeg", "-y", "-v", "error", "-i", str(asset),
         "-fps_mode", "passthrough", "-start_number", "0",
         str(frames_dir / "f_%05d.png")],
        capture_output=True)
    return len(list(frames_dir.glob("f_*.png")))


def technical_qc(asset: Path, frames_dir: Path) -> dict:
    meta = ffprobe_json(asset)
    stream = next((s for s in meta.get("streams", [])
                   if s.get("codec_type") == "video"), {})
    num, _, den = (stream.get("r_frame_rate") or "0/1").partition("/")
    fps = float(num) / float(den or 1)
    metrics = frame_metrics(frames_dir)
    return {
        "decode_ok": decode_ok(asset),
        "duration_s": float(meta.get("format", {}).get("duration") or 0),
        "width": stream.get("width"), "height": stream.get("height"),
        "codec": stream.get("codec_name"), "fps": round(fps, 3),
        "nb_frames": stream.get("nb_frames"),
        "has_audio": any(s.get("codec_type") == "audio"
                         for s in meta.get("streams", [])),
        **metrics,
    }


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def download_allowlisted(url: str, dest: Path, timeout: int = 300) -> int:
    if not _host_allowed(url):
        raise RuntimeError("ASSET_HOST_NOT_ALLOWED")
    dest.parent.mkdir(parents=True, exist_ok=True)
    candidate = dest.with_suffix(dest.suffix + ".candidate")
    try:
        with urllib.request.urlopen(urllib.request.Request(url),
                                    timeout=timeout) as resp, \
                candidate.open("wb") as out:
            total = 0
            while True:
                part = resp.read(256 * 1024)
                if not part:
                    break
                total += len(part)
                out.write(part)
        candidate.replace(dest)
        return total
    except Exception:
        candidate.unlink(missing_ok=True)
        raise


async def probe_account_readonly(alias: str) -> dict:
    """One-at-a-time read-only account probe: session + credit statements."""
    manager = DolaSessionManager(profile_dir=ACCOUNT_PROFILES / alias)
    result = {"account_alias": alias, "probed_at": utcnow()}
    try:
        page = None
        for attempt in (1, 2):
            try:
                page = await manager.launch_browser()
                await page.goto("https://www.dola.com/chat",
                                timeout=60000,
                                wait_until="domcontentloaded")
                break
            except Exception as error:
                if attempt == 2:
                    raise
                await asyncio.sleep(4)
        try:
            await page.evaluate(CONSENT_DISMISS_JS)
        except Exception:
            pass
        for _ in range(15):
            state = await page.evaluate(LOGIN_CHECK_JS)
            if state.get("composer") and not state.get("logged_out"):
                break
            await page.wait_for_timeout(2000)
        state = await page.evaluate(LOGIN_CHECK_JS)
        try:
            body = await page.evaluate(
                "() => (document.body && document.body.innerText) || ''")
        except Exception:
            body = ""
        identity_map = {}
        ident_path = ROOT / ("projects/quality_v2_021_narrative_compiler/"
                             "slot_identities.json")
        if ident_path.exists():
            identity_map = json.loads(
                ident_path.read_text(encoding="utf-8"))
        expected_nick = (identity_map.get(alias) or {}).get("nickname")
        logged_in = (state.get("composer")
                     and not state.get("logged_out")) or (
            expected_nick and expected_nick in body and
            state.get("composer"))
        if not logged_in:
            result["session_state"] = "LOGIN_REQUIRED"
            return result
        result["session_state"] = "SESSION_VALID"
        from dola_010e_session_router import CREDIT_STATEMENTS_JS
        for _ in range(4):
            try:
                statements = await page.evaluate(
                    CREDIT_STATEMENTS_JS, {"conversationIds": []})
                break
            except Exception:
                await page.wait_for_timeout(2000)
        else:
            statements = []
        result["credit_statements"] = statements[-3:] if statements else []
        result["known_credit_state"] = (statements[-1]["remaining"]
                                        if statements else None)
        return result
    finally:
        try:
            await manager.close()
        except Exception:
            pass


async def dispatch_and_acquire(
        *, shot_spec, account_alias: str, run_dir: Path, shot_tag: str,
        on_release, on_creation, events_sink, expected_model: str =
        "seedance_v2.0", poll_seconds: int = 1500,
        expected_nickname: str | None = None) -> dict:
    """The proven live dispatch flow, V2-020-wired. EXACTLY ONE mutation.

    Returns {conversation_id, creation_ids, asset_path, asset_sha256,
    variant_authority, download_host, watermarked_fallback}.
    Raises RuntimeError with fail-closed statuses.
    """
    pkg = run_dir
    assets = pkg / "assets"
    assets.mkdir(parents=True, exist_ok=True)
    journal_path = pkg / f"dispatch_journal_{shot_tag}.jsonl"
    if journal_path.exists():
        prior = DispatchJournal(journal_path, "")
        if any(e["kind"] != MUTATION_RESERVED for e in prior.events):
            # engine-side latch guard: a journal past reservation holds
            # provider-side evidence (armed/released/bound). It must be
            # reconciled read-only — never overwritten by a re-dispatch.
            # The caller-side guard mirrors this; fail-closed here too so
            # a direct engine call can never destroy release lineage.
            raise RuntimeError(
                "OWNER_AMBIGUITY_GATE:prior dispatch journal holds events "
                "beyond MUTATION_RESERVED; read-only reconciliation "
                "required, re-dispatch refused")
        # reservation-only leftovers are archived, never deleted: the
        # destructive unlink lost interrupted-run attempt evidence in
        # V2-021 and forced manual recovery-lineage reconstruction
        ordinal = 1
        while True:
            archive = journal_path.with_name(
                f"{journal_path.stem}.prior-{ordinal}"
                f"{journal_path.suffix}")
            if not archive.exists():
                break
            ordinal += 1
        journal_path.rename(archive)

    prompt_sha = hashlib.sha256(shot_spec.prompt.encode()).hexdigest()
    identity = {"shot_id": shot_spec.shot_id, "prompt_sha256": prompt_sha,
                "duration_class": shot_spec.duration_class,
                "started_at": utcnow()}
    attempt_id = "attempt_" + hashlib.sha256(
        json.dumps(identity, sort_keys=True).encode()).hexdigest()

    journal = DispatchJournal(journal_path, attempt_id)
    journal.append(MUTATION_RESERVED, {
        "budget_kind": f"v2_020_{shot_tag}", "account": account_alias,
        "prompt_sha256": prompt_sha})

    manager = DolaSessionManager(profile_dir=ACCOUNT_PROFILES /
                                 account_alias)
    screenshots = pkg / "screenshots"
    screenshots.mkdir(parents=True, exist_ok=True)
    try:
        page = None
        for launch_attempt in (1, 2):
            try:
                page = await manager.launch_browser()
                await page.goto("https://www.dola.com/chat",
                                timeout=60000,
                                wait_until="domcontentloaded")
                try:
                    await page.evaluate(CONSENT_DISMISS_JS)
                except Exception:
                    pass
                state = await page.evaluate(LOGIN_CHECK_JS)
                break
            except Exception as error:
                if launch_attempt == 2 or "TargetClosed" not in                         type(error).__name__ and "Target closed" not in                         str(error):
                    raise
                emit({"event": "launch_retry", "shot": shot_tag,
                      "error": type(error).__name__})
                await asyncio.sleep(5)
        state = state if page is not None else {}
        waited = 0
        body_text = ""

        def login_ok() -> bool:
            if state.get("composer") and not state.get("logged_out"):
                return True
            # nickname authority: banners/promos embed login strings,
            # so the marker regex alone misfires on logged-in sessions
            return bool(expected_nickname) and expected_nickname in                 body_text and bool(state.get("composer"))

        while waited < 240 and not login_ok():
            await asyncio.sleep(5)
            waited += 5
            try:
                if not state.get("composer"):
                    await page.evaluate(CONSENT_DISMISS_JS)
            except Exception:
                pass
            state = await page.evaluate(LOGIN_CHECK_JS)
            try:
                body_text = await page.evaluate(
                    "() => (document.body && document.body.innerText) "
                    "|| ''")
            except Exception:
                pass
        if not login_ok():
            raise RuntimeError(
                f"USER_LOGIN_REQUIRED:{account_alias}"
                f"|composer={state.get('composer')}"
                f"|logged_out={state.get('logged_out')}"
                f"|nick={'expected_nickname' if False else ''}"
                f"{(expected_nickname or '')[:3]}..in_body="
                f"{bool(expected_nickname) and expected_nickname in body_text}"
                f"|body_head={body_text[:120]!r}")

        convs = await page.evaluate(RECENT_CONVS_JS)
        baseline: set[str] = set()
        for conv in convs[:6]:
            try:
                rows = await page.evaluate(PULL_RAW_JS,
                                           {"conversationId": conv})
                for row in rows:
                    for c in row.get("creations", []):
                        if c.get("id"):
                            baseline.add(c["id"])
            except Exception:
                continue
        emit({"event": "baseline", "shot": shot_tag,
              "known_creations": len(baseline)})

        adapter = DolaBrowserAdapter010E(
            run_id=f"v2_020_{shot_tag}_" + datetime.now(timezone.utc)
            .strftime("%Y%m%dT%H%M%S"))
        adapter.manager = manager
        adapter.page = page
        adapter.capture = NetworkCapture(manager._context, page,
                                         adapter.run_id)
        await adapter.capture.start()
        await adapter.ensure_video_mode()
        await adapter.select_duration(shot_spec.duration_class)
        gate = await adapter.verify_duration_pre_dispatch(
            shot_spec.duration_class)
        await page.screenshot(path=str(screenshots / f"{shot_tag}_01_armed.png"))

        fingerprint = hashlib.sha256(json.dumps(
            {"prompt_sha256": prompt_sha,
             "duration_class": shot_spec.duration_class},
            sort_keys=True).encode()).hexdigest()
        journal.append(DISPATCH_ARMED_EV, {
            "attempt_id": attempt_id, "account": account_alias,
            "request_fingerprint": fingerprint,
            "capture_run_id": adapter.run_id})

        adapter.attach_journal(
            journal, expected_needle=shot_spec.prompt, index_boundary=0,
            known_creation_ids=baseline)

        dispatch = await adapter.submit(shot_spec.prompt,
                                        conversation_id="HOME")
        release = dispatch["release"]
        if not await adapter.wait_journal_state("RELEASE_OBSERVED", 30):
            raise RuntimeError("OWNER_AMBIGUITY_GATE:release not observed")
        journal.append(NETWORK_RELEASE_OBSERVED, {
            "account_binding": {"attempt_id": attempt_id,
                                "account": account_alias,
                                "request_fingerprint": fingerprint},
            "binding_rule": "IMMUTABLE after this event"})
        refined = await adapter.verify_release_body(release["request_id"])
        emit({"event": "release_refined", "shot": shot_tag,
              "duration": refined.get("duration"),
              "needle": refined.get("needle_present")})
        if refined.get("duration") not in (shot_spec.duration_class, None):
            raise RuntimeError("OWNER_AMBIGUITY_GATE:released duration "
                               f"{refined.get('duration')}")
        if not refined.get("needle_present", False):
            raise RuntimeError("OWNER_AMBIGUITY_GATE:prompt needle missing "
                               "from release body")
        # MODEL verification (V2-020): released ability_param.model
        post_data = await adapter.capture.get_post_data(
            release["request_id"])
        released_model = None
        if post_data:
            try:
                body = json.loads(post_data)
                raw = (body.get("chat_ability") or {}).get("ability_param")
                if isinstance(raw, str):
                    raw = json.loads(raw)
                released_model = (raw or {}).get("model")
            except Exception:
                released_model = None
        if released_model is not None and released_model != expected_model:
            raise RuntimeError("OWNER_AMBIGUITY_GATE:released model "
                               f"{released_model} != {expected_model}")
        journal.append("MODEL_VERIFIED", {"released_model": released_model})

        if not await adapter.wait_journal_state("RECEIPT_CAPTURED", 120):
            # the release is already latched (NETWORK_RELEASE_OBSERVED +
            # MODEL_VERIFIED): the provider mutation is a fact even when
            # the SSE receipt never arrives. Fire the accounting callback
            # BEFORE failing so budget consumption matches the latched
            # release; receipt-miss under-counting was a live V2-021
            # defect that required manual retroactive correction.
            on_release({"attempt_id": attempt_id, "conversation_id": None,
                        "receipt": {}, "request_fingerprint": fingerprint,
                        "released_model": released_model})
            raise RuntimeError("OWNER_AMBIGUITY_GATE:receipt not captured")
        conversation_id = None
        for event in journal.events:
            if event.get("event") == "SSE_RECEIPT_CAPTURED" or \
                    event.get("kind") == "SSE_RECEIPT_CAPTURED":
                conversation_id = event.get("conversation_id")
        receipt = next((e for e in journal.events
                        if e.get("event") == SSE_RECEIPT_CAPTURED
                        or e.get("kind") == SSE_RECEIPT_CAPTURED), {})
        on_release({"attempt_id": attempt_id, "conversation_id":
                    receipt.get("conversation_id"),
                    "receipt": receipt, "request_fingerprint": fingerprint,
                    "released_model": released_model})

        # ---- discovery + deep variant resolution --------------------------
        resolver = DolaAssetVariantResolver()
        bound_creation = None
        bound_conv = None
        creation_ids: list[str] = []
        deadline = asyncio.get_event_loop().time() + poll_seconds
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
                    rows = await page.evaluate(PULL_RAW_JS,
                                               {"conversationId": conv})
                except Exception:
                    continue
                if not any(shot_spec.needle in (r.get("text") or "")
                           for r in rows):
                    continue
                bound_conv = conv
                done = [c for r in rows for c in r.get("creations", [])
                        if c.get("type") == 2 and c.get("download_url")
                        and c.get("id") not in baseline]
                refusal = any(m in (r.get("text") or "")
                              for r in rows[:4] for m in REFUSAL_MARKERS)
                if refusal and not any(r.get("creations")
                                       for r in rows[:4]):
                    raise RuntimeError("STOPPED_PROVIDER_POLICY_REFUSAL")
                if done:
                    # normalized events for the deep surface (Phase 4)
                    payload = {"downlink_body": {
                        "pull_singe_chain_downlink_body": {
                            "messages": [{"message_id": r["message_id"],
                                          "content": r.get("content_raw")}
                                         for r in rows]}}}
                    ids = sorted({str(c["id"]) for c in done})
                    urls = {c["download_url"] for c in done}
                    events_sink.append(normalize_poll_payload(
                        payload, observed_at_utc=utcnow()))
                    if len(urls) != 1:
                        raise RuntimeError(
                            "STOPPED_PROVIDER_CORRELATION_GAP:"
                            f"{len(urls)} distinct urls")
                    on_creation({"conversation_id": conv,
                                 "creation_ids": ids})
                    video_url = urls.pop()
                    # deep video_model resolution on the newest creation
                    newest = done[-1]
                    raw_model = newest.get("video_model_raw")
                    creation_obj = {"id": newest.get("id"), "video": {
                        "status": newest.get("status"),
                        "download_url": newest.get("download_url"),
                        "video_model": raw_model}}
                    selection = resolver.select(creation_obj)
                    authority = selection.authority
                    target_url = None
                    if selection.variant is not None:
                        renditions = extract_renditions(creation_obj)
                        for r in renditions:
                            if str(r.get("_list_key")) == \
                                    selection.variant.list_key:
                                url = decode_media_url(
                                    r.get(selection.variant.field))
                                if url and _host_allowed(url):
                                    target_url = url
                                break
                    if target_url is None and authority == \
                            "PROVIDER_ISSUED_UNWATERMARKED":
                        raise RuntimeError("CLEAN_VARIANT_RESOLUTION_GAP")
                    fallback = target_url is None
                    if target_url is None:
                        target_url = video_url  # provider watermarked
                        authority = "PROVIDER_ISSUED_WATERMARKED"
                    dest = assets / f"{shot_tag}.mp4"
                    total = download_allowlisted(target_url, dest)
                    record = {
                        "conversation_id": conv, "creation_ids": ids,
                        "asset_path": str(dest), "asset_sha256":
                            _sha256(dest), "size": total,
                        "variant_authority": authority,
                        "download_host": target_url.split("/")[2],
                        "watermarked_fallback": fallback,
                        "selection_reason": selection.reason,
                        "video_model_status": newest.get("status"),
                        "poll_attempts": attempt_n,
                    }
                    journal.append(CREATION_BOUND,
                                   {"creation_ids": ids,
                                    "conversation_id": conv})
                    journal.append(ASSET_DOWNLOADED, {
                        "sha256": record["asset_sha256"], "size": total})
                    journal.append(TERMINAL_SUCCESS, {
                        "sha256": record["asset_sha256"]})
                    return record
            await page.wait_for_timeout(10000)
        raise RuntimeError("STOPPED_PROVIDER_CORRELATION_GAP:no completed "
                           "video within window")
    finally:
        try:
            await manager.close()
        except Exception:
            pass
