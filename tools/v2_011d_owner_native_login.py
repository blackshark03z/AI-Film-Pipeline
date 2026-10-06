"""V2-011D RESUME — Owner manual login INSIDE the ACCOUNT_D automation profile.

The captured-cookie route is dead (ByteDance passport cookies are
fingerprint-bound; replaying the real-Chrome session in patchright chromium
invalidates it — the 010B lesson). The durable route is a NATIVE session in
the exact automation profile the runner uses.

This launches the ACCOUNT_D profile HEADED at dola.com and polls up to 25
minutes for the Owner to complete the Google login IN THAT WINDOW. When the
Dola session is native-valid it re-captures the (fingerprint-consistent)
cookies into the DPAPI blob and exits 0. The browser is closed on exit.
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

from dola_010c_session import dpapi_protect
from dola_010e_session_router import ACCOUNT_PROFILES

PKG = ROOT / "projects/quality_v2_011d_world_matched_context"
STORE = PKG / "runtime" / "runtime_secret_store"
ALIAS = "ACCOUNT_D"
LOGIN_CHECK_JS = """() => {
    const t = (document.body && document.body.innerText) || '';
    return {
        logged_out: /(^|\\n)\\s*ログイン\\s*(\\n|$)/.test(t)
            || /\\bLog\\s?in\\b|\\bSign\\s?in\\b/.test(t)
            || /Đăng nhập|Đăng ký/i.test(t),
        composer: !!(document.querySelector('textarea')
            || document.querySelector('[contenteditable="true"]')),
    };
}"""


def utcnow():
    return datetime.now(timezone.utc).isoformat()


def emit(payload):
    print(json.dumps(payload, ensure_ascii=False, default=str), flush=True)


async def main() -> int:
    from patchright.async_api import async_playwright
    pw = await async_playwright().start()
    profile = ACCOUNT_PROFILES / ALIAS
    ctx = await pw.chromium.launch_persistent_context(
        str(profile), headless=False,
        args=["--disable-blink-features=AutomationControlled",
              "--no-first-run", "--no-default-browser-check",
              "--window-size=1400,900"],
        locale="ja-JP", timezone_id="Asia/Tokyo")
    page = ctx.pages[0] if ctx.pages else await ctx.new_page()
    try:
        await page.goto("https://www.dola.com/", timeout=60000,
                        wait_until="domcontentloaded")
    except Exception:
        pass
    emit({"event": "LOGIN_WINDOW_OPEN — waiting for Owner to complete "
                   "Google login in THIS window (up to 25 min)"})

    deadline = asyncio.get_event_loop().time() + 1500
    authed = False
    while asyncio.get_event_loop().time() < deadline:
        try:
            state = await page.evaluate(LOGIN_CHECK_JS)
        except Exception:
            await page.wait_for_timeout(3000)
            continue
        if state.get("composer") and not state.get("logged_out"):
            authed = True
            break
        await page.wait_for_timeout(4000)
    if not authed:
        emit({"status": "OWNER_LOGIN_NOT_COMPLETED"})
        await ctx.close()
        await pw.stop()
        return 1
    emit({"event": "dola_session_authenticated_native", "at": utcnow()})
    await page.wait_for_timeout(3000)

    cookies = await ctx.cookies("https://www.dola.com")
    dola_cookies = [c for c in cookies if ".dola.com" in (c.get("domain") or "")]
    STORE.mkdir(parents=True, exist_ok=True)
    blob = STORE / f"dola_session_{ALIAS}.dpapi"
    blob.write_text(dpapi_protect(json.dumps(
        {"registered_at": utcnow(),
         "source": "owner_manual_login_native_profile",
         "cookies": dola_cookies}).encode("utf-8")), encoding="ascii")
    emit({"event": "dpapi_refreshed", "n_cookies": len(dola_cookies),
          "native_fingerprint": True})

    log_path = PKG / "V2_011D_RESUME_OBSERVATION_LOG.json"
    log = json.loads(log_path.read_text(encoding="utf-8"))
    log["observations"].append({
        "kind": "SESSION_REMEDIATION", "at": utcnow(), "account": ALIAS,
        "detail": "captured-cookie route invalidated by passport "
                  "fingerprint binding (010B lesson confirmed); Owner "
                  "completed the Google login NATIVELY inside the ACCOUNT_D "
                  "automation profile; DPAPI blob refreshed from the "
                  "fingerprint-consistent session"})
    log_path.write_text(json.dumps(log, indent=1, ensure_ascii=False),
                        encoding="utf-8")
    emit({"checkpoint": "V2011D_ACCOUNT_D_NATIVE_SESSION",
          "n_cookies": len(dola_cookies)})
    await ctx.close()
    await pw.stop()
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
