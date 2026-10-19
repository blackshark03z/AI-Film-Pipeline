"""Probe and verify account eligibility sequentially.

Worker execution script for F1:
- Maps alias to correct profile directory
- Checks session validity (composer + nickname)
- Checks passive credit statements
- If lacking fresh credit statement, sends ONE text inquiry query (ACCOUNT_STATE_QUERY)
- Extracts verified remaining video credits
"""
from __future__ import annotations

import asyncio
import json
import re
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
sys.path.insert(0, str(ROOT / "src"))

from dola_010c_session import DolaSessionManager
from dola_010e_session_router import CREDIT_STATEMENTS_JS
from v2_020_runner import LOGIN_CHECK_JS, CONSENT_DISMISS_JS

PROFILE_MAP = {
    "ACCOUNT_E": Path(r"D:\AI FILM MAKER\AI-Film-Pipeline\projects\quality_v2_021_narrative_compiler\pool_profiles\ACCOUNT_E"),
    "ACCOUNT_F": Path(r"D:\AI FILM MAKER\AI-Film-Pipeline\projects\quality_v2_021_narrative_compiler\pool_profiles\ACCOUNT_F"),
    "ACCOUNT_A": Path(r"D:\AI FILM MAKER\AI-Film-Pipeline\projects\quality_v2_010e_final_f2b\runtime\account_profiles\ACCOUNT_A"),
}

NICKNAME_MAP = {
    "ACCOUNT_E": "Khởi Đặng868",
    "ACCOUNT_F": "shh ddhdh",
    "ACCOUNT_A": None,
}

INQUIRY = ("本日の動画生成クレジットの残り枚数を正確に教えてください。"
           "生成はしないでください。")


async def probe_account(alias: str, allow_query: bool = True) -> dict:
    profile_dir = PROFILE_MAP.get(alias)
    if not profile_dir or not profile_dir.exists():
        return {"alias": alias, "status": "PROFILE_NOT_FOUND", "profile_dir": str(profile_dir)}

    expected_nick = NICKNAME_MAP.get(alias)
    mgr = DolaSessionManager(profile_dir=profile_dir)
    result = {
        "alias": alias,
        "profile_dir": str(profile_dir),
        "expected_nickname": expected_nick,
        "probed_at": datetime.now(timezone.utc).isoformat(),
        "session_state": "UNKNOWN",
        "passive_statements": [],
        "query_sent": False,
        "query_reply": None,
        "verified_free_credit": None,
    }

    try:
        page = await mgr.launch_browser(headless=False)
        await page.goto("https://www.dola.com/chat", timeout=60000, wait_until="domcontentloaded")
        
        try:
            await page.evaluate(CONSENT_DISMISS_JS)
        except Exception:
            pass

        # Wait for composer / login state
        waited = 0
        state = {}
        body_text = ""
        while waited < 30:
            state = await page.evaluate(LOGIN_CHECK_JS)
            try:
                body_text = await page.evaluate("() => (document.body && document.body.innerText) || ''")
            except Exception:
                body_text = ""
            
            if state.get("composer") and not state.get("logged_out"):
                break
            if expected_nick and expected_nick in body_text and state.get("composer"):
                break
            await page.wait_for_timeout(2000)
            waited += 2

        logged_in = (state.get("composer") and not state.get("logged_out")) or (
            expected_nick and expected_nick in body_text and state.get("composer")
        )

        if not logged_in:
            result["session_state"] = "LOGIN_REQUIRED"
            result["body_head"] = body_text[:200]
            return result

        result["session_state"] = "SESSION_VALID"
        result["nickname_present"] = (expected_nick in body_text) if expected_nick else True

        # Check passive statements
        statements = []
        for _ in range(3):
            try:
                statements = await page.evaluate(CREDIT_STATEMENTS_JS, {"conversationIds": []})
                if statements:
                    break
            except Exception:
                await page.wait_for_timeout(2000)

        result["passive_statements"] = statements
        print(f"[{alias}] Passive statements found: {len(statements)}")

        # Check if latest statement is from today (after 2026-10-19 00:00:00 UTC -> timestamp 1792368000)
        today_cutoff = 1792368000
        latest_today_statement = None
        for s in reversed(statements):
            create_time = int(s.get("create_time") or 0)
            if create_time >= today_cutoff:
                latest_today_statement = s
                break

        if latest_today_statement is not None:
            rem = latest_today_statement.get("remaining")
            print(f"[{alias}] Found today's statement: remaining={rem}, text={latest_today_statement.get('source_text')}")
            if rem is not None and rem >= 1:
                result["verified_free_credit"] = rem
                result["credit_evidence_source"] = "PASSIVE_STATEMENT_TODAY"
                result["latest_statement"] = latest_today_statement
                return result

        # If lacking fresh credit or remaining is 0/unknown, try query if authorized
        if allow_query:
            print(f"[{alias}] Sending text inquiry query...")
            box = await page.query_selector("textarea") or await page.query_selector('[contenteditable="true"]')
            if not box:
                result["status"] = "NO_COMPOSER_FOR_QUERY"
                return result

            await box.click()
            await page.keyboard.type(INQUIRY, delay=20)
            await page.wait_for_timeout(500)
            await page.keyboard.press("Enter")
            result["query_sent"] = True
            result["query_sent_at"] = datetime.now(timezone.utc).isoformat()

            # Poll for reply
            deadline = asyncio.get_event_loop().time() + 90
            reply_text = ""
            while asyncio.get_event_loop().time() < deadline:
                await page.wait_for_timeout(5000)
                try:
                    # Check statements
                    fresh_statements = await page.evaluate(CREDIT_STATEMENTS_JS, {"conversationIds": []})
                    if fresh_statements:
                        newest = fresh_statements[-1]
                        c_time = int(newest.get("create_time") or 0)
                        if c_time >= int(time.time()) - 180:
                            result["latest_statement"] = newest
                            result["verified_free_credit"] = newest.get("remaining")
                            result["credit_evidence_source"] = "QUERY_MUTATION_STATEMENT"
                            print(f"[{alias}] Query statement observed: remaining={newest.get('remaining')}")
                            break
                except Exception as e:
                    pass

                # Also read the latest message text from the current page
                try:
                    last_msg = await page.evaluate("""() => {
                        const msgs = document.querySelectorAll('[class*=message], [class*=Message], [data-message-id]');
                        if (msgs.length) {
                            return msgs[msgs.length - 1].innerText;
                        }
                        return '';
                    }""")
                    if last_msg and last_msg != INQUIRY:
                        reply_text = last_msg
                        # Check patterns on reply text
                        p = re.search(r"残りは?\s*(\d+)\s*(?:動画)?クレジット|残り[はも]?[^。]{0,6}?(\d+)|(\d+)\s*(?:動画クレジット|video credits?)", reply_text)
                        if p:
                            num = int(p.group(1) or p.group(2) or p.group(3))
                            result["verified_free_credit"] = num
                            result["credit_evidence_source"] = "QUERY_MUTATION_REPLY_TEXT"
                            result["query_reply"] = reply_text[:300]
                            print(f"[{alias}] Text match from reply: remaining={num}")
                            break
                except Exception:
                    pass

            result["query_reply"] = reply_text[:500]

        return result
    except Exception as error:
        result["status"] = "ERROR"
        result["error"] = f"{type(error).__name__}: {error}"[:300]
        return result
    finally:
        try:
            await mgr.close()
        except Exception:
            pass


async def main():
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    target = sys.argv[1] if len(sys.argv) > 1 else "ACCOUNT_E"
    allow_query = "--no-query" not in sys.argv
    res = await probe_account(target, allow_query=allow_query)
    out_dir = ROOT / "isolated_s08_run"
    out_dir.mkdir(parents=True, exist_ok=True)
    out_file = out_dir / f"probe_{target}.json"
    out_file.write_text(json.dumps(res, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps(res, indent=2, ensure_ascii=True))


if __name__ == "__main__":
    asyncio.run(main())

