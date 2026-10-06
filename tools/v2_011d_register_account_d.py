"""V2-011D RESUME — register the Owner-authorized fresh Dola session.

1. capture ONLY dola.com cookies from the login Chrome (CDP 9334);
2. persist the DPAPI blob under the existing encrypted mechanism
   (runtime_secret_store/dola_session_ACCOUNT_D.dpapi);
3. seed the runner profile ACCOUNT_PROFILES/ACCOUNT_D (patchright persistent
   context, inject once, validate, close);
4. record the Owner's structural-dispatch authorization in the credit gate.

No Google cookies are captured, copied or persisted. Raw cookie values are
written ONLY into the DPAPI blob (encrypted at rest) and the local profile —
never into tracked evidence.
"""
from __future__ import annotations

import asyncio
import json
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
CDP = "http://127.0.0.1:9334"
ALIAS = "ACCOUNT_D"
LOGIN_CHECK_JS = """() => {
    const t = (document.body && document.body.innerText) || '';
    return {
        logged_out: /(^|\\n)\\s*ログイン\\s*(\\n|$)/.test(t)
            || /\\bLog\\s?in\\b|\\bSign\\s?in\\b/.test(t),
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

    # ---- 1. capture dola.com cookies from the login Chrome ----------------
    pw = await async_playwright().start()
    browser = await pw.chromium.connect_over_cdp(CDP)
    ctx = browser.contexts[0]
    cookies = await ctx.cookies("https://www.dola.com")
    dola_cookies = [c for c in cookies if c.get("name") and
                    ".dola.com" in (c.get("domain") or "")]
    if not any(c["name"] == "sessionid" for c in dola_cookies):
        emit({"status": "NO_DOLA_SESSION_COOKIE"})
        await pw.stop()
        return 1
    emit({"event": "captured", "n_cookies": len(dola_cookies),
          "names": sorted(c["name"] for c in dola_cookies)})

    # ---- 2. DPAPI blob ----------------------------------------------------
    STORE.mkdir(parents=True, exist_ok=True)
    blob = STORE / f"dola_session_{ALIAS}.dpapi"
    blob.write_text(dpapi_protect(json.dumps(
        {"registered_at": utcnow(), "source": "owner_manual_login_chrome",
         "cookies": dola_cookies}).encode("utf-8")), encoding="ascii")
    emit({"event": "dpapi_registered", "blob": str(blob)})

    # ---- 3. seed the runner profile ---------------------------------------
    profile = ACCOUNT_PROFILES / ALIAS
    profile.mkdir(parents=True, exist_ok=True)
    pctx = await pw.chromium.launch_persistent_context(
        str(profile), headless=True,
        args=["--disable-blink-features=AutomationControlled",
              "--no-first-run", "--no-default-browser-check"],
        locale="ja-JP", timezone_id="Asia/Tokyo")
    page = pctx.pages[0] if pctx.pages else await pctx.new_page()
    await pctx.add_cookies([
        {"name": c["name"], "value": c["value"], "domain": ".dola.com",
         "path": c.get("path", "/"), "secure": True, "httpOnly": False,
         "sameSite": "Lax"} for c in dola_cookies])
    await page.goto("https://www.dola.com/chat", timeout=60000,
                    wait_until="domcontentloaded")
    state = None
    for _ in range(20):
        try:
            state = await page.evaluate(LOGIN_CHECK_JS)
            if state.get("composer") and not state.get("logged_out"):
                break
        except Exception:
            pass
        await page.wait_for_timeout(1000)
    seeded = bool(state and state.get("composer")
                  and not state.get("logged_out"))
    emit({"event": "profile_seeded", "profile": str(profile),
          "session_valid": seeded})
    await pctx.close()

    # ---- 4. credit gate record (Owner structural authorization) -----------
    gate = {
        "version": "v2-011d-f3r-credit-gate-final-v2",
        "recorded_at": utcnow(),
        "account_opaque_id": ALIAS,
        "dola_identity_display": "Khởi Đặng219 (Owner's manual Google login)",
        "gate_rule": "fresh provider-visible credit >= 1",
        "provider_visible_observation": "IMPOSSIBLE_PRE_FIRST_GENERATION "
            "(no statements exist; the chat bot refuses credit questions — "
            "the 010E inquiry was refused identically; no UI credit surface)",
        "verdict": "SUFFICIENT",
        "verdict_basis": "OWNER_STRUCTURAL_DISPATCH_AUTHORIZATION — the "
            "Owner explicitly accepted the stated risk and authorized the "
            "F3R dispatch as the FIRST-EVER generation of this Owner-created "
            "fresh account (daily grant unused; standard grant 4/day per "
            "ACCOUNT_A evidence). If the provider refuses at submit, nothing "
            "is charged; if accepted, it consumes 1 credit of the fresh "
            "grant. Recorded as an Owner decision, NOT as a provider-visible "
            "credit observation.",
        "account_state_query_mutations_spent": 1,
        "video_generation_mutations_touched": 0,
    }
    (PKG / "V2_011D_F3R_CREDIT_GATE.json").write_text(
        json.dumps(gate, indent=1, ensure_ascii=False), encoding="utf-8")
    log_path = PKG / "V2_011D_RESUME_OBSERVATION_LOG.json"
    log = json.loads(log_path.read_text(encoding="utf-8"))
    log["observations"].append({
        "kind": "OWNER_STRUCTURAL_DISPATCH_AUTHORIZATION", "at": utcnow(),
        "account": ALIAS, "risk_accepted": True,
        "detail": "Owner authorized F3R dispatch on the fresh account "
                  "without provider-visible credit observation"})
    log_path.write_text(json.dumps(log, indent=1, ensure_ascii=False),
                        encoding="utf-8")
    await pw.stop()
    emit({"checkpoint": "V2011D_ACCOUNT_D_REGISTERED",
          "session_valid": seeded, "gate": "SUFFICIENT (owner structural)"})
    return 0 if seeded else 1


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
