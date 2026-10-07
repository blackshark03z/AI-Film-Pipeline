"""V2-021 — interactive account enrollment: open headed login windows.

Usage: python tools/v2_021_interactive_login.py <PKG> ALIAS [ALIAS...]

Opens one headed patchright window per alias (separate persistent
profile), each at the Dola login page. The OWNER logs in interactively
(Google OAuth / credentials / CAPTCHA are theirs alone — never automated).
Each window is polled for a completed login (composer present, no
ログイン/Sign-in markers, up to 25 min); on success the account identity
(profile/self) and provider-visible credit statements are recorded
read-only, and the window closes.
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

from dola_010c_session import DolaSessionManager
from dola_010e_session_router import CREDIT_STATEMENTS_JS

PKG = Path(sys.argv[1]) if len(sys.argv) > 1 else \
    ROOT / "projects/quality_v2_021_narrative_compiler"
ALIASES = sys.argv[2:] or ["ACCOUNT_E", "ACCOUNT_F"]
PROFILE_ROOT = PKG / "pool_profiles"
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

IDENTITY_JS = """async () => {
  const params = new URLSearchParams({
    version_code: "20800", language: "ja", device_platform: "web",
    doubao_device_platform: "web", aid: "495671", real_aid: "495671",
    pkg_type: "release_version", pc_version: "3.39.1",
    region: "VN", sys_region: "VN", samantha_web: "1",
    "use-olympus-account": "1", web_tab_id: crypto.randomUUID(),
  });
  const resp = await fetch("/alice/profile/self?" + params.toString(), {
    method: "GET", credentials: "include",
    headers: {"Accept": "application/json, text/plain, */*"}});
  if (!resp.ok) return null;
  const data = await resp.json();
  const brief = ((data.data || {}).profile_brief) || {};
  return {nickname: brief.nickname || "", entity_id: brief.entity_id || "",
          membership: ((brief.membership_info || {}).level) || ""};
}"""


def emit(payload: dict) -> None:
    print(json.dumps(payload, ensure_ascii=False, default=str), flush=True)


async def run_slot(alias: str) -> dict:
    profile = PROFILE_ROOT / alias
    profile.mkdir(parents=True, exist_ok=True)
    manager = DolaSessionManager(profile_dir=profile)
    result = {"alias": alias, "opened_at": datetime.now(
        timezone.utc).isoformat()}
    try:
        page = await manager.launch_browser()
        await page.goto("https://www.dola.com/chat", timeout=60000,
                        wait_until="domcontentloaded")
        emit({"event": "window_open", "alias": alias,
              "note": "waiting for OWNER interactive login"})
        logged = False
        for _ in range(25 * 60 // 10):
            await page.wait_for_timeout(10000)
            try:
                state = await page.evaluate(LOGIN_CHECK_JS)
            except Exception:
                continue
            if state.get("composer") and not state.get("logged_out"):
                logged = True
                break
            if int(asyncio.get_event_loop().time()) % 60 < 11:
                emit({"event": "still_waiting", "alias": alias,
                      "logged_out": state.get("logged_out")})
        if not logged:
            result["status"] = "LOGIN_NOT_COMPLETED"
            emit(result)
            return result
        await page.wait_for_timeout(3000)
        identity = None
        try:
            identity = await page.evaluate(IDENTITY_JS)
        except Exception:
            pass
        statements = []
        for _ in range(4):
            try:
                statements = await page.evaluate(CREDIT_STATEMENTS_JS,
                                                 {"conversationIds": []})
                break
            except Exception:
                await page.wait_for_timeout(2000)
        latest = statements[-1] if statements else None
        result.update({
            "status": "ENROLLED",
            "identity": identity,
            "known_credit_state": (latest or {}).get("remaining"),
            "latest_statement": latest,
            "statement_count": len(statements),
        })
        emit({"event": "login_detected", "alias": alias,
              "identity": identity,
              "credit": result["known_credit_state"]})
        return result
    except Exception as error:
        result["status"] = "ERROR"
        result["error"] = f"{type(error).__name__}: {error}"[:200]
        emit(result)
        return result
    finally:
        try:
            await manager.close()
        except Exception:
            pass


async def main() -> int:
    PROFILE_ROOT.mkdir(parents=True, exist_ok=True)
    # windows open SEQUENTIALLY per the one-browser-per-slot rule, but the
    # owner can log in at their own pace; we open all windows first so
    # they can work in parallel, then poll each
    managers = {}
    pages = {}
    for alias in ALIASES:
        profile = PROFILE_ROOT / alias
        profile.mkdir(parents=True, exist_ok=True)
        manager = DolaSessionManager(profile_dir=profile)
        page = await manager.launch_browser()
        await page.goto("https://www.dola.com/chat", timeout=60000,
                        wait_until="domcontentloaded")
        managers[alias] = manager
        pages[alias] = page
        emit({"event": "window_open", "alias": alias,
              "note": "OWNER logs in interactively"})
    results = {}
    pending = dict(pages)
    deadline = asyncio.get_event_loop().time() + 25 * 60
    while pending and asyncio.get_event_loop().time() < deadline:
        await page_wait(10)
        for alias in list(pending):
            try:
                state = await pending[alias].evaluate(LOGIN_CHECK_JS)
            except Exception:
                continue
            if state.get("composer") and not state.get("logged_out"):
                results[alias] = await finalize(alias, managers[alias],
                                                pending[alias])
                del pending[alias]
    for alias, page in pending.items():
        results[alias] = {"alias": alias,
                          "status": "LOGIN_NOT_COMPLETED"}
    for alias, manager in managers.items():
        if alias in pending:
            try:
                await manager.close()
            except Exception:
                pass
    PKG.mkdir(parents=True, exist_ok=True)
    (PKG / "V2_021_POOL_ENROLLMENT.json").write_text(
        json.dumps({"enrolled_at": datetime.now(timezone.utc).isoformat(),
                    "slots": results}, indent=1, ensure_ascii=False),
        encoding="utf-8")
    emit({"status": "ENROLLMENT_DONE",
          "slots": {a: r.get("status") for a, r in results.items()},
          "saved": str(PKG / "V2_021_POOL_ENROLLMENT.json")})
    return 0


async def page_wait(seconds: int) -> None:
    await asyncio.sleep(seconds)


async def finalize(alias: str, manager, page) -> dict:
    await page.wait_for_timeout(3000)
    identity = None
    try:
        identity = await page.evaluate(IDENTITY_JS)
    except Exception:
        pass
    statements = []
    for _ in range(4):
        try:
            statements = await page.evaluate(CREDIT_STATEMENTS_JS,
                                             {"conversationIds": []})
            break
        except Exception:
            await page.wait_for_timeout(2000)
    latest = statements[-1] if statements else None
    result = {"alias": alias, "status": "ENROLLED", "identity": identity,
              "known_credit_state": (latest or {}).get("remaining"),
              "latest_statement": latest,
              "statement_count": len(statements)}
    emit({"event": "login_detected", "alias": alias, "identity": identity,
          "credit": result["known_credit_state"]})
    try:
        await manager.close()
    except Exception:
        pass
    return result


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
