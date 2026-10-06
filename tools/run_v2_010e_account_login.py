"""V2-010E — optional account bootstrap: manual login for ACCOUNT_A.

Opens the account's dedicated headed profile at the Dola login surface,
waits (light, non-navigating poll) for the Owner to log in manually — the
worker NEVER reads keyboard input, never asks for passwords/cookies — then
captures the browser session into a per-account DPAPI blob, validates, reads
provider-visible credit state, and classifies. Stops the onboarding as soon
as one account is READY.
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

from dola_010e_session_router import (ACCOUNT_PROFILES, LOGIN_REQUIRED,
                                      NO_CREDIT, READY, SESSION_VALID,
                                      DolaSessionRouter, opaque_alias)
from dola_010c_session import dpapi_protect

PKG = ROOT / "projects/quality_v2_010e_final_f2b"
SECRETS = PKG / "runtime" / "runtime_secret_store"
WAIT_SECONDS = int(sys.argv[1]) if len(sys.argv) > 1 else 1200


def utcnow() -> str:
    return datetime.now(timezone.utc).isoformat()


def emit(payload: dict) -> None:
    print(json.dumps(payload, ensure_ascii=False, default=str), flush=True)


async def main() -> int:
    router = DolaSessionRouter()
    accounts = router.enumerate_known_accounts()
    opaque = opaque_alias(0)
    alias, source = accounts[0]
    result = {"version": "v2-010e-account-bootstrap-v1",
              "account_opaque_id": opaque, "account_alias": alias,
              "started_at": utcnow()}

    from patchright.async_api import async_playwright
    pw_cm = async_playwright()
    playwright = await pw_cm.start()
    profile_dir = ACCOUNT_PROFILES / opaque
    profile_dir.mkdir(parents=True, exist_ok=True)
    context = await playwright.chromium.launch_persistent_context(
        str(profile_dir), headless=False,
        args=["--disable-blink-features=AutomationControlled",
              "--no-first-run", "--no-default-browser-check"],
        locale="ja-JP", timezone_id="Asia/Tokyo")
    page = context.pages[0] if context.pages else context.new_page()
    try:
        # seed whatever the store has (may be stale; the Owner's manual
        # login will refresh it in-profile)
        cookie = router.load_cookie(alias, source) or ""
        if cookie:
            cookies = []
            for pair in cookie.split(";"):
                pair = pair.strip()
                if "=" in pair:
                    name, _, value = pair.partition("=")
                    cookies.append({"name": name.strip(), "value": value.strip(),
                                    "domain": ".dola.com", "path": "/",
                                    "secure": True, "httpOnly": False,
                                    "sameSite": "Lax"})
            await context.add_cookies(cookies)
        try:
            await page.goto("https://www.dola.com/chat", timeout=60000,
                            wait_until="domcontentloaded")
        except Exception as error:
            result["navigation"] = type(error).__name__
        emit({"status": "USER_LOGIN_REQUIRED",
              "account": opaque,
              "note": "headed window open — Owner logs in manually; the "
                      "worker polls without reloading"})
        waited = 0
        sessionid_seen = False
        authenticated = False
        stable_authenticated = 0
        while waited < WAIT_SECONDS:
            await asyncio.sleep(5)
            waited += 5
            try:
                names = {c["name"] for c in
                         await context.cookies("https://www.dola.com")}
                sessionid_seen = "sessionid" in names
                # anonymous sessionid is NOT login: the logged-out/OAuth UI
                # shows a login affordance (Japanese, English OR VIETNAMESE
                # — the Owner's OAuth flow renders Đăng nhập), and the page
                # must be ON dola.com (not accounts.google.com mid-flow)
                logged_out = await page.evaluate(
                    """() => {
                        const t = (document.body && document.body.innerText)
                            || "";
                        return /(^|\\n)\\s*ログイン\\s*(\\n|$)/.test(t)
                            || /\\bLog\\s?in\\b|\\bSign\\s?in\\b/.test(t)
                            || /đăng nhập/i.test(t);
                    }""")
                url_ok = "dola.com" in (page.url or "")
            except Exception:
                sessionid_seen, logged_out, url_ok = False, True, False
            authenticated = sessionid_seen and not logged_out and url_ok
            # require STABILITY: an OAuth redirect or transient navigation
            # must not be mistaken for a completed login
            stable_authenticated = stable_authenticated + 1 if authenticated \
                else 0
            if stable_authenticated >= 3:
                break
            if waited % 120 == 0:
                emit({"step": "still_waiting", "waited": waited,
                      "sessionid": sessionid_seen, "logged_out": logged_out,
                      "url_ok": url_ok,
                      "url_tail": (page.url or "")[-40:]})
        if not authenticated:
            result.update({"status": "LOGIN_TIMEOUT",
                           "waited_seconds": waited,
                           "note": "sessionid present but anonymous (logged-"
                                   "out UI) or no sessionid"})
            (PKG / "V2_010E_ACCOUNT_BOOTSTRAP.json").write_text(
                json.dumps(result, indent=1, ensure_ascii=False),
                encoding="utf-8")
            emit({"status": "LOGIN_TIMEOUT"})
            return 1
        # capture the fresh session (browser-side) into per-account DPAPI
        cookies = await context.cookies("https://www.dola.com")
        ls_ss = await page.evaluate(
            """() => ({localStorage:
                Object.fromEntries(Object.entries(localStorage))})""")
        blob = json.dumps({"schema": "ai-film-dola-session-v2-010e",
                           "account_alias": alias,
                           "saved_at": utcnow(),
                           "cookies": cookies,
                           "web_storage": ls_ss},
                          ensure_ascii=False, separators=(",", ":"))
        SECRETS.mkdir(parents=True, exist_ok=True)
        target = SECRETS / f"dola_session_{opaque}.dpapi"
        tmp = target.with_suffix(".dpapi.tmp")
        tmp.write_text(dpapi_protect(blob.encode("utf-8")), encoding="ascii")
        tmp.replace(target)
        emit({"step": "session_captured",
              "blob_sha256_12": hashlib.sha256(
                  blob.encode()).hexdigest()[:12]})

        # validate + credit check (same probe as the router)
        probe = await router.probe_account(opaque, alias, source)
        # the probe re-injects the STORE cookie (stale) — instead validate
        # the LIVE profile directly
        probe.session_state = SESSION_VALID
        probe.health_state = "FRESH_LOGIN_CAPTURED"
        for _ in range(12):
            try:
                has_composer = await page.evaluate(
                    """() => !!(document.querySelector('textarea')
                            || document.querySelector('[contenteditable="true"]'))""")
            except Exception:
                has_composer = False
            if has_composer:
                break
            await page.wait_for_timeout(1000)
        if not has_composer:
            probe.session_state = LOGIN_REQUIRED
        else:
            statements = []
            # credit read via the router's JS on the live page
            from dola_010e_session_router import CREDIT_STATEMENTS_JS
            for _ in range(5):
                try:
                    statements = await page.evaluate(
                        CREDIT_STATEMENTS_JS, {"conversationIds": []})
                    break
                except Exception:
                    await page.wait_for_timeout(2000)
            if statements:
                latest = statements[-1]
                probe.credit_remaining = latest.get("remaining")
                probe.credit_observed_at = utcnow()
                probe.credit_source_text = latest.get("source_text", "")
        router.classify(probe, required_credit=1)
        result.update({"status": probe.session_state,
                       "credit_remaining": probe.credit_remaining,
                       "credit_source": probe.credit_source_text,
                       "completed_at": utcnow(),
                       "dpapi_ref": "runtime_secret_store/"
                                    f"dola_session_{opaque}.dpapi"})
        (PKG / "V2_010E_ACCOUNT_BOOTSTRAP.json").write_text(
            json.dumps(result, indent=1, ensure_ascii=False),
            encoding="utf-8")
        # update the selection if READY
        if probe.session_state == READY:
            (PKG / "V2_010E_ACCOUNT_SELECTION.json").write_text(
                json.dumps({"version": "v2-010e-account-selection-v1",
                            "selected_at": utcnow(),
                            "selected_opaque_id": opaque,
                            "selected_account_alias": alias,
                            "selected_profile_alias": probe.profile_alias,
                            "encrypted_session_ref": probe.encrypted_session_ref,
                            "selection_reason": "only READY account after "
                                                "bootstrap manual login "
                                                "(ACCOUNT_B has 0 credit)",
                            "credit_remaining": probe.credit_remaining,
                            "credit_observed_at": probe.credit_observed_at,
                            "session_state": probe.session_state,
                            "binding_rule": "account becomes IMMUTABLY "
                                            "bound at "
                                            "NETWORK_RELEASE_OBSERVED"},
                           indent=1, ensure_ascii=False),
                encoding="utf-8")
        emit({"checkpoint": "V2010E_BOOTSTRAP_DONE",
              "state": probe.session_state,
              "credit": probe.credit_remaining})
        return 0 if probe.session_state == READY else 1
    finally:
        try:
            await context.close()
        except Exception:
            pass
        await playwright.stop()


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
