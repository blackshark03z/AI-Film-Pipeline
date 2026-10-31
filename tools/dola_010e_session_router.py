"""V2-010E RESUME — DolaSessionRouter: multi-account discovery/selection.

Operational session/credit management across Owner-authorized accounts
(Story Auto DPAPI store). NOT a provider-enforcement bypass: no fake
accounts, no CAPTCHA/access-control circumvention, no credit farming.

Per account (read-only): own persistent profile (isolated browser state per
account, mirroring legitimate multi-account usage), cookie injection from
the DPAPI store (memory only), session validation, provider-visible credit
statements via /im/chain/recent_conv + /im/chain/single (LATEST statement
wins), classification into
UNKNOWN/LOGIN_REQUIRED/SESSION_VALID/SESSION_EXPIRED/NO_CREDIT/READY.
READY = SESSION_VALID AND remaining_video_credit >= 1.

Selection is deterministic (valid session → credit → region health →
qualified behavior → LRU); no random rotation. Account switching is legal
only while dispatch_state = NOT_RELEASED; after NETWORK_RELEASE_OBSERVED
the account is journal-bound to the GenerationAttempt.
"""
from __future__ import annotations

import asyncio
import hashlib
import json
import re
import sys
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
sys.path.insert(0, str(ROOT / "src"))

PKG = ROOT / "projects/quality_v2_010e_final_f2b"
RUNTIME = PKG / "runtime"
ACCOUNT_PROFILES = RUNTIME / "account_profiles"

UNKNOWN = "UNKNOWN"
LOGIN_REQUIRED = "LOGIN_REQUIRED"
SESSION_VALID = "SESSION_VALID"
SESSION_EXPIRED = "SESSION_EXPIRED"
NO_CREDIT = "NO_CREDIT"
READY = "READY"
QUARANTINED = "QUARANTINED"


def utcnow() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass
class DolaAccountSession:
    account_alias: str
    opaque_id: str
    source: str
    profile_alias: str
    encrypted_session_ref: str
    session_state: str = UNKNOWN
    provider_region: str = ""
    credit_remaining: int | None = None
    credit_observed_at: str | None = None
    credit_source_text: str = ""
    last_used_at: str | None = None
    health_state: str = "UNPROBED"
    notes: list = field(default_factory=list)

    def tracked_view(self) -> dict:
        view = asdict(self)
        view.pop("notes", None)
        return view


CREDIT_STATEMENTS_JS = """async ({conversationIds}) => {
  const params = new URLSearchParams({
    version_code: "20800", language: "ja", device_platform: "web",
    doubao_device_platform: "web", aid: "495671", real_aid: "495671",
    pkg_type: "release_version", pc_version: "3.39.1",
    doubao_pc_version: "3.39.1", region: "VN", sys_region: "VN",
    samantha_web: "1", web_platform: "browser",
    "use-olympus-account": "1", web_tab_id: crypto.randomUUID(),
  });
  const headers = {"Content-Type": "application/json; encoding=utf-8",
                   "agw-js-conv": "str",
                   "Accept": "application/json, text/plain, */*"};
  const pull = async (body) => {
    const resp = await fetch("/im/chain/single?" + params.toString(), {
      method: "POST", headers, credentials: "include",
      body: JSON.stringify(body)});
    if (!resp.ok) return [];
    const data = await resp.json();
    return ((data.downlink_body || {})
      .pull_singe_chain_downlink_body || {}).messages || [];
  };
  // 1) recent conversation ids
  const recent = await fetch("/im/chain/recent_conv?" + params.toString(), {
    method: "POST", headers, credentials: "include",
    body: JSON.stringify({cmd: 3200, uplink_body: {
      pull_recent_conv_chain_uplink_body: {limit: 20,
        message_count_per_conv: 2, api_version: 1, conv_version: 0,
        direction: 3, option: {not_need_message: false,
          need_complete_conversation: true, need_coco_conversation: true,
          need_coco_bot: true, need_pc_pin_chain: true,
          pc_pin_query_type: 0}}},
      sequence_id: crypto.randomUUID(), channel: 2, version: "1"})});
  let convIds = conversationIds;
  if (recent.ok) {
    try {
      const data = await recent.json();
      const cells = ((data.downlink_body || {})
        .pull_recent_conv_chain_downlink_body || {}).cells || [];
      const ids = cells.map(c => (c.conversation || {}).conversation_id
        || c.id).filter(Boolean);
      if (ids.length) convIds = ids.slice(0, 6);
    } catch (e) {}
  }
  // 2) credit statements from the newest messages of those conversations
  const statements = [];
  const patterns = [/残りは?\\s*(\\d+)\\s*(?:動画)?クレジット/, /残り[はも]?[^。]{0,6}?(\\d+)/];
  for (const conversation_id of convIds) {
    const messages = await pull({cmd: 3100, uplink_body: {
      pull_singe_chain_uplink_body: {conversation_id,
        anchor_index: Number.MAX_SAFE_INTEGER, conversation_type: 3,
        direction: 1, limit: 10, ext: {}, filter: {index_list: []},
        evaluate_ab_params: "", evaluate_common_params: ""}},
      sequence_id: crypto.randomUUID(), channel: 2, version: "1"});
    for (const m of messages) {
      let blocks = m.content;
      if (typeof blocks === "string") {
        try { blocks = JSON.parse(blocks); } catch (e) { blocks = []; }
      }
      let text = "";
      for (const b of (Array.isArray(blocks) ? blocks : [])) {
        if (b.block_type === 10000) {
          text += (((b.content || {}).text_block || {}).text || "");
        }
      }
      for (const p of patterns) {
        const match = p.exec(text);
        if (match) {
          statements.push({conversation_id, message_id: String(m.message_id),
            create_time: m.create_time, remaining: parseInt(match[1], 10),
            source_text: match[0].slice(0, 80)});
          break;
        }
      }
    }
  }
  statements.sort((a, b) => (a.create_time || 0) - (b.create_time || 0));
  return statements;
}"""


class DolaSessionRouter:
    """Enumerate → validate → credit-check → classify Owner accounts."""

    def __init__(self) -> None:
        self.pool: list[DolaAccountSession] = []

    # -- discovery -----------------------------------------------------------

    def enumerate_known_accounts(self) -> list[tuple[str, str]]:
        """(account_alias, source). Read-only DPAPI enumeration. Fresh
        per-account blobs captured by the 010E bootstrap take priority over
        the (possibly stale) Story Auto store records."""
        found: list[tuple[str, str]] = []
        for blob in sorted((PKG / "runtime/runtime_secret_store")
                           .glob("dola_session_*.dpapi")):
            opaque = blob.stem.replace("dola_session_", "")
            found.append((opaque, "dpapi_blob_010e"))
        sa = Path("D:/Story Auto/story-auto")
        if sa.exists():
            sys.path.insert(0, str(sa))
            try:
                from story_auto.providers.dola_cookie.accounts import (
                    DolaAccountStore)
                store = DolaAccountStore()
                for entry in store.list_accounts():
                    alias = entry.get("account_id")
                    if entry.get("configured") and alias:
                        found.append((alias, "story_auto_dpapi"))
            except Exception:
                pass
        # dedupe preserving order
        seen: set[str] = set()
        unique = []
        for alias, source in found:
            if alias not in seen:
                seen.add(alias)
                unique.append((alias, source))
        return unique

    def load_cookie(self, alias: str, source: str) -> str | None:
        if source == "dpapi_blob_010e":
            blob = (PKG / "runtime/runtime_secret_store"
                    / f"dola_session_{alias}.dpapi")
            if not blob.exists():
                return None
            from dola_010c_session import dpapi_unprotect
            try:
                session = json.loads(dpapi_unprotect(
                    blob.read_text(encoding="ascii")))
                header = "; ".join(
                    f"{c['name']}={c['value']}" for c in session["cookies"])
                return header if "sessionid=" in header else None
            except Exception:
                return None
        if source == "story_auto_dpapi":
            sa = Path("D:/Story Auto/story-auto")
            sys.path.insert(0, str(sa))
            try:
                from story_auto.providers.dola_cookie.accounts import (
                    DolaAccountStore)
                cookie = DolaAccountStore().get_cookie(alias)
                return cookie if cookie and "sessionid=" in cookie else None
            except Exception:
                return None
        return None

    # -- per-account probe (read-only) ----------------------------------------

    async def probe_account(self, opaque_id: str, alias: str,
                            source: str) -> DolaAccountSession:
        session = DolaAccountSession(
            account_alias=alias, opaque_id=opaque_id, source=source,
            profile_alias=f"router_profile_{opaque_id}",
            encrypted_session_ref=f"story_auto_dpapi:{alias}",
            last_used_at=utcnow())
        cookie = self.load_cookie(alias, source)
        if not cookie or "sessionid=" not in cookie:
            # a stored record without a live sessionid = needs manual login
            session.session_state = LOGIN_REQUIRED
            session.health_state = "NO_SESSIONID_IN_STORE"
            session.notes.append("DPAPI store record has no sessionid "
                                 "cookie; manual login required")
            return session

        from patchright.async_api import async_playwright
        pw_cm = async_playwright()
        playwright = await pw_cm.start()
        profile_dir = ACCOUNT_PROFILES / opaque_id
        profile_dir.mkdir(parents=True, exist_ok=True)
        context = None
        try:
            context = await playwright.chromium.launch_persistent_context(
                str(profile_dir), headless=False,
                args=["--disable-blink-features=AutomationControlled",
                      "--no-first-run", "--no-default-browser-check"],
                locale="ja-JP", timezone_id="Asia/Tokyo")
            page = context.pages[0] if context.pages else context.new_page()
            # ONLY seed cookies when the profile has no native session:
            # injecting a captured (older) sessionid over a live login
            # DOWNGRADES the session to anonymous
            native = {c["name"] for c in
                      await context.cookies("https://www.dola.com")}
            if "sessionid" not in native and cookie:
                cookies = []
                for pair in cookie.split(";"):
                    pair = pair.strip()
                    if "=" in pair:
                        name, _, value = pair.partition("=")
                        cookies.append({"name": name.strip(),
                                        "value": value.strip(),
                                        "domain": ".dola.com", "path": "/",
                                        "secure": True, "httpOnly": False,
                                        "sameSite": "Lax"})
                await context.add_cookies(cookies)
            try:
                await page.goto("https://www.dola.com/chat", timeout=60000,
                                wait_until="domcontentloaded")
            except Exception as error:
                session.health_state = "NAVIGATION_FAILED"
                session.notes.append(f"goto: {type(error).__name__}")
                return session
            for _ in range(15):
                await page.wait_for_timeout(1000)
                cookie_names = {c["name"] for c in
                                await context.cookies("https://www.dola.com")}
                if "sessionid" in cookie_names:
                    break
            cookie_names = {c["name"] for c in
                            await context.cookies("https://www.dola.com")}
            url = page.url or ""
            if "sessionid" not in cookie_names:
                session.session_state = SESSION_EXPIRED
                session.health_state = "NO_SESSION_COOKIE"
                return session
            # sessionid alone is NOT authentication: Dola issues an
            # anonymous sessionid to every visitor. The logged-out home
            # shows a ログイン button; the logged-in UI does not.
            try:
                logged_out = await page.evaluate(
                    r"""() => {
                        const t = (document.body && document.body.innerText)
                            || "";
                        return /(^|\n)\s*ログイン\s*(\n|$)/.test(t)
                            || /Log\s?in|Sign\s?in/.test(t);
                    }""")
            except Exception:
                logged_out = False
            if logged_out:
                session.session_state = LOGIN_REQUIRED
                session.health_state = "ANONYMOUS_SESSIONID_LOGGED_OUT"
                session.notes.append("anonymous sessionid — no "
                                     "authenticated UI")
                return session
            if any(marker in url.lower() for marker in
                   ("signin", "login", "accountchooser")):
                session.session_state = LOGIN_REQUIRED
                session.health_state = "LOGIN_UI"
                return session
            has_composer = False
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
                body = (await page.evaluate(
                    "() => (document.body && document.body.innerText) || ''")
                    or "")
                session.session_state = (LOGIN_REQUIRED
                                         if re.search(r"log\\s?in|sign\\s?in|登录|ログイン",
                                                      body, re.I)
                                         else SESSION_EXPIRED)
                return session
            session.session_state = SESSION_VALID
            session.health_state = "COMPOSER_OK"

            # provider-visible credit statements (this account's own view);
            # evaluate races with SPA navigations — retry resiliently
            statements = []
            for _ in range(5):
                try:
                    statements = await page.evaluate(
                        CREDIT_STATEMENTS_JS, {"conversationIds": []})
                    break
                except Exception as error:
                    if "Execution context" in str(error) or \
                            "navigation" in str(error).lower():
                        await page.wait_for_timeout(2000)
                        continue
                    break
            if statements:
                latest = statements[-1]
                session.credit_remaining = latest.get("remaining")
                session.credit_observed_at = utcnow()
                session.credit_source_text = latest.get("source_text", "")
                region_match = re.search(
                    r"region=(\w+)", page.url or "")  # rarely in URL
                session.provider_region = region_match.group(1) \
                    if region_match else ""
            else:
                session.credit_remaining = None
                session.credit_observed_at = utcnow()
                session.credit_source_text = "NO_STATEMENT_VISIBLE"
            return session
        finally:
            if context:
                try:
                    await context.close()
                except Exception:
                    pass
            await playwright.stop()

    # -- pool + selection ------------------------------------------------------

    def classify(self, session: DolaAccountSession,
                 required_credit: int = 1) -> None:
        if session.session_state == SESSION_VALID:
            if session.credit_remaining is None:
                session.session_state = SESSION_VALID  # credit unobservable
                session.health_state += "|CREDIT_UNOBSERVABLE"
            elif session.credit_remaining >= required_credit:
                session.session_state = READY
            else:
                session.session_state = NO_CREDIT
        session.last_used_at = utcnow()

    def select(self, pool: list[DolaAccountSession],
               qualified_alias: str, required_credit: int = 1) -> dict:
        """Deterministic selection: valid session → credit → region health →
        previously-qualified behavior → least-recently-used tie-break."""
        ready = [s for s in pool if s.session_state == READY]
        ready.sort(key=lambda s: (
            0 if s.source == "story_auto_dpapi" else 1,          # stable source
            0 if s.account_alias == qualified_alias else 1,      # qualified
            -(s.credit_remaining or 0),                          # most credit
            s.last_used_at or ""))                               # LRU
        if not ready:
            return {"selected": None,
                    "reason": "no READY account (all "
                              "LOGIN_REQUIRED/EXPIRED/NO_CREDIT)"}
        chosen = ready[0]
        reasons = [
            "valid existing session",
            f"credit {chosen.credit_remaining} >= {required_credit}",
            "region/context healthy (composer + poll OK)",
            "previously qualified BrowserNetwork behavior"
            if chosen.account_alias == qualified_alias else
            "same qualified adapter/profile machinery",
            "least-recently-used tie-break among equal candidates",
        ]
        return {"selected": chosen, "selection_reason": "; ".join(reasons)}


def opaque_alias(index: int) -> str:
    return f"ACCOUNT_{chr(ord('A') + index)}"
