"""V2-019 Phase A — live read-only probe of the authenticated Dola runtime.

Per account (one browser at a time, automation profile only):
  1. launch persistent profile, navigate to /chat (passive CDP capture ON),
  2. classify session state (logged-in vs login UI),
  3. let the page fire its own config endpoints (skill/pack, action_bar_v3,
     user/subscription) and record them passively,
  4. dump the composer chip texts + a localStorage key census (values
     truncated; no secrets persisted),
  5. stop capture (DPAPI-encrypt raw), extract config bodies to memory and
     write sanitized tracked evidence.

NO message is sent. NO composer submission. UI interaction limited to
reading text. 0 mutations.
"""
from __future__ import annotations

import asyncio
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
sys.path.insert(0, str(ROOT / "src"))

from dola_010c_capture import NetworkCapture
from dola_010c_session import DolaSessionManager, dpapi_unprotect

RUNTIME = ROOT / "projects/quality_v2_010e_final_f2b/runtime"
ACCOUNT_PROFILES = RUNTIME / "account_profiles"
PKG = ROOT / "projects/quality_v2_019_dola_productionization"
CAPTURE_DIR = PKG / "runtime/capture"
CAPTURE_DIR.mkdir(parents=True, exist_ok=True)

TARGETS = sys.argv[1:] or ["ACCOUNT_D", "ACCOUNT_A"]

LOGGED_OUT_MARKERS = ("ログイン", "Log in", "Sign in", "登录")


def utcnow() -> str:
    return datetime.now(timezone.utc).isoformat()


def emit(payload: dict) -> None:
    print(json.dumps(payload, ensure_ascii=False, default=str), flush=True)


async def probe_account(alias: str) -> dict:
    result: dict = {"account_alias": alias, "started_at": utcnow()}
    manager = DolaSessionManager(
        profile_dir=ACCOUNT_PROFILES / alias)
    capture = None
    raw_path = None
    try:
        page = await manager.launch_browser()
        capture = NetworkCapture(manager._context, page,
                                 f"v2_019_phaseA_{alias}")
        await capture.start()
        await page.goto("https://www.dola.com/chat", timeout=60000,
                        wait_until="domcontentloaded")
        # settle: page fires its own config endpoints here
        for _ in range(15):
            await page.wait_for_timeout(1000)
            body = await page.evaluate(
                "() => (document.body && document.body.innerText) || ''")
            if any(m in body for m in LOGGED_OUT_MARKERS[:2]):
                break
            if await page.evaluate(
                    """() => !!(document.querySelector('textarea')
                            || document.querySelector('[contenteditable="true"]'))"""):
                break

        body_text = await page.evaluate(
            "() => (document.body && document.body.innerText) || ''")
        logged_out = any(m in body_text for m in LOGGED_OUT_MARKERS)
        has_composer = await page.evaluate(
            """() => !!(document.querySelector('textarea')
                    || document.querySelector('[contenteditable="true"]'))""")
        result["session_state"] = (
            "LOGIN_REQUIRED" if logged_out and not has_composer
            else "SESSION_VALID" if has_composer else "UNRESOLVED")
        result["logged_out_marker"] = logged_out
        result["has_composer"] = has_composer

        if result["session_state"] == "SESSION_VALID":
            # composer chip census (visible control values only)
            chips = await page.evaluate(
                """() => {
                  const out = [];
                  for (const el of document.querySelectorAll(
                      '[class*="chip"],[class*="Chip"],button,'
                      + '[role="button"]')) {
                    const t = (el.innerText || '').trim();
                    if (t && t.length <= 24) out.push(t);
                  }
                  return Array.from(new Set(out)).slice(0, 80);
                }""")
            result["composer_visible_texts"] = chips
            # localStorage key census (values truncated to 80 chars)
            ls = await page.evaluate(
                """() => {
                  const out = {};
                  for (let i = 0; i < localStorage.length; i++) {
                    const k = localStorage.key(i);
                    const v = (localStorage.getItem(k) || '');
                    out[k] = v.length > 80 ? v.slice(0, 80) + '…'
                                           : v;
                  }
                  return out;
                }""")
            result["localStorage_census"] = {
                k: v for k, v in ls.items()
                if not re.search(r"token|cookie|secret|session", k, re.I)}
            # wait a little longer for late config endpoints
            await page.wait_for_timeout(8000)
    except Exception as error:
        result["error"] = f"{type(error).__name__}: {error}"[:300]
    finally:
        if capture is not None:
            try:
                summary = await capture.stop(encrypt=True)
                result["capture"] = summary
                raw_path = capture.raw_path
            except Exception as error:
                result["capture_error"] = str(error)[:200]
        try:
            await manager.close()
        except Exception:
            pass
    result["completed_at"] = utcnow()
    return result, raw_path


def extract_config_evidence(raw_path: Path | None, alias: str) -> dict:
    """Decrypt raw (memory only), pull config bodies, write sanitized."""
    if raw_path is None:
        return {}
    enc = raw_path.with_name(raw_path.name + ".dpapi")
    blob_src = enc if enc.exists() else raw_path
    if not blob_src.exists():
        return {}
    try:
        data = dpapi_unprotect(blob_src.read_text(encoding="ascii"))
    except Exception as error:
        return {"decrypt_error": str(error)[:200]}
    lines = data.decode("utf-8", errors="replace").splitlines()
    configs = []
    endpoints_seen = []
    for line in lines:
        if "skill/pack" not in line and "action_bar_v3" not in line \
                and "subscription" not in line and "user/" not in line:
            continue
        try:
            ev = json.loads(line)
        except Exception:
            continue
        url = ev.get("url") or ""
        if ev.get("kind") == "RESP":
            endpoints_seen.append({"url_head": url.split("?")[0],
                                   "status": ev.get("status")})
        if ev.get("kind") != "BODY":
            continue
        body = ev.get("body") or ""
        if not body or "Seedance" not in body and "skill/pack" not in url \
                and "subscription" not in url:
            continue
        try:
            obj = json.loads(body)
        except Exception:
            continue
        configs.append({"url_head": url.split("?")[0], "body": obj})
    # keep only the informative ones (video_generation / selector templates)
    keep = []
    for c in configs:
        s = json.dumps(c["body"], ensure_ascii=False)
        if "video_generation" in s or "Seedance" in s or \
                "video-model" in s:
            keep.append(c)
    out = {"version": "v2-019-phaseA-live-configs-v1",
           "account_alias": alias, "endpoints_seen": endpoints_seen[:40],
           "config_bodies": keep}
    dst = PKG / f"V2_019_PHASEA_LIVE_CONFIGS_{alias}.json"
    dst.write_text(json.dumps(out, indent=1, ensure_ascii=False),
                   encoding="utf-8")
    return {"saved": str(dst), "n_configs": len(keep),
            "endpoints": len(endpoints_seen)}


async def main() -> int:
    report = {"version": "v2-019-phaseA-live-probe-v1", "accounts": {}}
    for alias in TARGETS:
        result, raw_path = await probe_account(alias)
        report["accounts"][alias] = result
        extraction = extract_config_evidence(raw_path, alias)
        report["accounts"][alias]["config_extraction"] = extraction
        emit({"account": alias, "session": result.get("session_state"),
              "extraction": extraction})
        if result.get("session_state") == "SESSION_VALID":
            break  # one valid probe is enough for Phase A truth
    dst = PKG / "V2_019_PHASEA_LIVE_PROBE.json"
    dst.write_text(json.dumps(report, indent=1, ensure_ascii=False),
                   encoding="utf-8")
    emit({"saved": str(dst)})
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
