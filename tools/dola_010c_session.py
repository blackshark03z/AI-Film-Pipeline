"""AI-FILM-QUALITY-V2-010C — Layer 7 Dola session manager (first-class).

States (fail-closed; stale cookies are never used merely because they exist):

    NO_SESSION → LOGIN_REQUIRED → SESSION_CAPTURED → SESSION_VALID
                                  → SESSION_EXPIRED / SESSION_UNCERTAIN

Secret handling:
- Plaintext secrets exist only in process memory / temp runtime while needed.
- Durable persistence: Windows DPAPI (current-user scope) at
  runtime_secret_store/dola_session.dpapi — OUTSIDE git-tracked evidence.
- Tracked metadata carries only names, counts, expiry classes, hashes.

The browser runs headed via patchright (anti-detection fork used by the
Owner's live-proven Story Auto browser-UI transport), persistent profile
DOLA_RE_PROFILE, isolated from every other browser profile on this machine.
No password/keyboard/credential interaction ever happens through this module.
"""
from __future__ import annotations

import base64
import ctypes
import ctypes.wintypes as wt
import hashlib
import json
import re
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PKG = ROOT / "projects/quality_v2_010c_dola_fullstack"
RUNTIME = PKG / "runtime"
SECRET_STORE = RUNTIME / "runtime_secret_store"
PROFILE = RUNTIME / "browser_profile"          # DOLA_RE_PROFILE (untracked)
RAW_DIR = RUNTIME / "capture"

ORIGIN = "https://www.dola.com"
SESSION_STORE_SCHEMA = "ai-film-dola-session-v2-010c"

NO_SESSION = "NO_SESSION"
LOGIN_REQUIRED = "LOGIN_REQUIRED"
SESSION_CAPTURED = "SESSION_CAPTURED"
SESSION_VALID = "SESSION_VALID"
SESSION_EXPIRED = "SESSION_EXPIRED"
SESSION_UNCERTAIN = "SESSION_UNCERTAIN"

# cookie name → class (structural classification; values never persisted here)
COOKIE_CLASSES = {
    "sessionid": "AUTH",
    "sessionid_ss": "AUTH",
    "msToken": "RUNTIME",
    "s_v_web_id": "DEVICE",
    "ttwid": "DEVICE",
    "tt_scid": "DEVICE",
    "xgplayer_user_id": "DEVICE",
    "csrf_session_id": "CSRF",
    "i18next": "SESSION",
    "store-region": "SESSION",
}
LOCALSTORAGE_CLASSES = (
    (re.compile(r"token|session|auth|login|user", re.I), "AUTH_OR_SESSION"),
)


# ---------------------------------------------------------------- DPAPI ----

class _DataBlob(ctypes.Structure):
    _fields_ = [("cbData", wt.DWORD), ("pbData", ctypes.POINTER(ctypes.c_char))]


def _blob(data: bytes):
    buf = ctypes.create_string_buffer(data, len(data))
    return _DataBlob(len(data), ctypes.cast(buf, ctypes.POINTER(ctypes.c_char))), buf


def dpapi_protect(data: bytes) -> str:
    """Encrypt bytes with Windows DPAPI, current-user scope → base64."""
    if sys.platform != "win32":
        raise OSError("Windows DPAPI unavailable")
    inp, _ = _blob(data)
    out = _DataBlob()
    if not ctypes.windll.crypt32.CryptProtectData(
            ctypes.byref(inp), None, None, None, None, 0, ctypes.byref(out)):
        raise OSError("DPAPI CryptProtectData failed")
    try:
        return base64.b64encode(
            ctypes.string_at(out.pbData, out.cbData)).decode("ascii")
    finally:
        ctypes.windll.kernel32.LocalFree(out.pbData)


def dpapi_unprotect(b64: str) -> bytes:
    if sys.platform != "win32":
        raise OSError("Windows DPAPI unavailable")
    raw = base64.b64decode(b64, validate=True)
    inp, _ = _blob(raw)
    out = _DataBlob()
    if not ctypes.windll.crypt32.CryptUnprotectData(
            ctypes.byref(inp), None, None, None, None, 0, ctypes.byref(out)):
        raise OSError("DPAPI CryptUnprotectData failed")
    try:
        return ctypes.string_at(out.pbData, out.cbData)
    finally:
        ctypes.windll.kernel32.LocalFree(out.pbData)


# ------------------------------------------------------- secret payloads ---

def save_session_encrypted(payload: dict) -> Path:
    """Persist the full session payload (cookie values, web storage) DPAPI-
    encrypted; only the encrypted blob lands on disk."""
    SECRET_STORE.mkdir(parents=True, exist_ok=True)
    target = SECRET_STORE / "dola_session.dpapi"
    blob = json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    tmp = target.with_suffix(".dpapi.tmp")
    tmp.write_text(dpapi_protect(blob), encoding="ascii")
    tmp.replace(target)
    return target


def load_session_encrypted() -> dict | None:
    target = SECRET_STORE / "dola_session.dpapi"
    if not target.exists():
        return None
    try:
        return json.loads(dpapi_unprotect(target.read_text(encoding="ascii")))
    except (OSError, ValueError, json.JSONDecodeError):
        return None


def delete_session_encrypted() -> None:
    (SECRET_STORE / "dola_session.dpapi").unlink(missing_ok=True)


# ------------------------------------------------------------ cookie IO ---

def parse_cookie_header(header: str) -> list[dict]:
    cookies = []
    for pair in header.split(";"):
        pair = pair.strip()
        if not pair or "=" not in pair:
            continue
        name, _, value = pair.partition("=")
        cookies.append({"name": name.strip(), "value": value.strip(),
                        "domain": ".dola.com", "path": "/",
                        "secure": True, "httpOnly": False, "sameSite": "Lax"})
    return cookies


def cookie_header_from_cookies(cookies: list[dict]) -> str:
    return "; ".join(f"{c['name']}={c['value']}" for c in cookies
                     if "dola" in (c.get("domain") or ""))


def cookie_expiry_class(cookie: dict) -> str:
    exp = cookie.get("expires", -1)
    if exp in (-1, 0):
        return "session"
    return "persistent"


# --------------------------------------------- Story Auto cookie source ---

def load_cookie_from_story_auto() -> tuple[str, str] | None:
    """Read-only load of the Owner's DPAPI-stored Dola cookie (memory only).

    Returns (cookie_header, source_alias) or None. Never writes their store,
    never logs values."""
    sa = Path("D:/Story Auto/story-auto")
    if sa.exists():
        sys.path.insert(0, str(sa))
        try:
            from story_auto.providers.dola_cookie.accounts import DolaAccountStore
            store = DolaAccountStore()
            for alias in ("dola-profile-20260923", "dola-main"):
                try:
                    cookie = store.get_cookie(alias)
                except Exception:
                    continue
                if cookie and "sessionid=" in cookie:
                    return cookie, f"story_auto_dpapi:{alias}"
        except ImportError:
            pass
    for p in (Path("D:/Video/api_keys/dola_cookie.txt"),
              Path("D:/API KEY/dola_cookie.txt")):
        if p.exists():
            content = p.read_text(encoding="utf-8").strip()
            lines = [l.strip() for l in content.splitlines()
                     if l.strip() and not l.startswith("#")]
            if lines and "sessionid=" in " ".join(lines):
                return " ".join(lines), f"raw_file:{p}"
    return None


# ------------------------------------------------------ session manager ---

class DolaSessionManager:
    """Owns the DOLA_RE_PROFILE browser runtime and its session state."""

    def __init__(self) -> None:
        self.state = NO_SESSION
        self._playwright = None
        self._context = None
        self._page = None
        self.session_meta: dict = {}
        self.cookie_source: str = ""

    # -- lifecycle ----------------------------------------------------------

    def acquire_cookie(self) -> bool:
        found = load_cookie_from_story_auto()
        if not found:
            self.state = NO_SESSION
            return False
        self._cookie_header, self.cookie_source = found
        self.state = LOGIN_REQUIRED  # cookie exists but is UNVALIDATED
        return True

    async def launch_browser(self, *, headless: bool = False):
        from patchright.async_api import async_playwright
        self._pw_cm = async_playwright()
        self._playwright = await self._pw_cm.start()
        PROFILE.mkdir(parents=True, exist_ok=True)
        self._context = await self._playwright.chromium.launch_persistent_context(
            str(PROFILE),
            headless=headless,
            args=["--disable-blink-features=AutomationControlled",
                  "--no-first-run", "--no-default-browser-check"],
            locale="ja-JP", timezone_id="Asia/Tokyo")
        self._page = self._context.pages[0] if self._context.pages \
            else self._context.new_page()
        return self._page

    async def inject_cookies(self) -> int:
        cookies = parse_cookie_header(self._cookie_header)
        await self._context.add_cookies(cookies)
        return len(cookies)

    async def close(self):
        if self._context:
            await self._context.close()
        if self._playwright:
            await self._playwright.stop()

    # -- validation (read-only: navigation + composer probe only) -----------

    async def light_check(self) -> dict:
        """Non-navigating auth-state probe (safe during manual login)."""
        try:
            cookies = await self._context.cookies(ORIGIN)
        except Exception:
            cookies = []
        names = sorted({c["name"] for c in cookies})
        try:
            url = self._page.url or ""
        except Exception:
            url = ""
        return {"sessionid": "sessionid" in names,
                "url_tail": url[-60:], "cookie_names": names}

    async def validate_session(self, *, renavigate: bool = True) -> str:
        page = self._page
        if renavigate:
            try:
                await page.goto(ORIGIN + "/chat", timeout=60000,
                                wait_until="domcontentloaded")
            except Exception as error:  # network/DNS/WAF — uncertain, not dead
                self.state = SESSION_UNCERTAIN
                self.session_meta["navigation_error"] = type(error).__name__
                return self.state
        for _ in range(20):
            await page.wait_for_timeout(1000)
            cookies = await self._context.cookies(ORIGIN)
            names = {c["name"] for c in cookies}
            if "sessionid" in names:
                break
        cookies = await self._context.cookies(ORIGIN)
        names = {c["name"] for c in cookies}
        url = page.url or ""
        if "sessionid" not in names:
            self.state = SESSION_EXPIRED
            return self.state
        if any(marker in url.lower() for marker in
               ("signin", "login", "accountchooser", "accounts.google")):
            self.state = LOGIN_REQUIRED
            return self.state
        try:
            has_composer = await page.evaluate(
                """() => !!(document.querySelector('textarea')
                        || document.querySelector('[contenteditable="true"]')
                        || document.querySelector('input[type="text"]'))""")
        except Exception:
            has_composer = False
        if not has_composer:
            # give the SPA a second chance before classifying
            for _ in range(15):
                await page.wait_for_timeout(1000)
                try:
                    has_composer = await page.evaluate(
                        """() => !!(document.querySelector('textarea')
                                || document.querySelector('[contenteditable="true"]')
                                || document.querySelector('input[type="text"]'))""")
                except Exception:
                    has_composer = False
                if has_composer:
                    break
        if has_composer:
            self.state = SESSION_VALID
            return self.state
        try:
            login_ui = await page.evaluate(
                """() => {
                    const t = (document.body && document.body.innerText) || "";
                    return /log\\s?in|sign\\s?in|đăng nhập|登录|ログイン/i.test(t);
                }""")
        except Exception:
            login_ui = False
        self.state = LOGIN_REQUIRED if login_ui else SESSION_UNCERTAIN
        return self.state

    # -- inventory capture ---------------------------------------------------

    async def capture_inventory(self) -> dict:
        page, context = self._page, self._context
        cookies = await context.cookies(ORIGIN)
        inv = await page.evaluate("""async () => {
            const ls = Object.fromEntries(Object.entries(localStorage));
            const ss = {};
            for (let i = 0; i < sessionStorage.length; i++) {
                const k = sessionStorage.key(i);
                ss[k] = sessionStorage.getItem(k);
            }
            let idb = [];
            try { idb = (await indexedDB.databases()).map(d => d.name); }
            catch (e) { idb = ["EVAL_ERROR"]; }
            let sw = [];
            try {
                const regs = await navigator.serviceWorker.getRegistrations();
                sw = regs.map(r => r.active ? r.active.scriptURL :
                             (r.installing || r.waiting || {}).scriptURL || "?");
            } catch (e) { sw = ["EVAL_ERROR"]; }
            const uad = navigator.userAgentData || null;
            return {
                localStorage: ls, sessionStorage: ss, indexedDB: idb,
                serviceWorkers: sw,
                ua: navigator.userAgent,
                languages: navigator.languages,
                timezone: Intl.DateTimeFormat().resolvedOptions().timeZone,
                userAgentData: uad ? {brands: uad.brands, mobile: uad.mobile,
                                      platform: uad.platform} : null,
                hardwareConcurrency: navigator.hardwareConcurrency,
                deviceMemory: navigator.deviceMemory || null,
                screen: {w: screen.width, h: screen.height, dpr: devicePixelRatio},
            };
        }""")

        def classify(name: str, table: dict) -> str:
            return table.get(name, "UNKNOWN")

        cookie_meta = []
        for c in sorted(cookies, key=lambda x: x["name"]):
            cookie_meta.append({
                "name": c["name"], "domain": c.get("domain"),
                "expiry_class": cookie_expiry_class(c),
                "class": classify(c["name"], COOKIE_CLASSES),
                "value_sha256_12": hashlib.sha256(
                    c["value"].encode("utf-8")).hexdigest()[:12],
                "value_len": len(c["value"])})

        def storage_meta(store: dict, kind: str) -> list[dict]:
            meta = []
            for key in sorted(store):
                value = str(store[key])
                cls = "UNKNOWN"
                for pattern, label in LOCALSTORAGE_CLASSES:
                    if pattern.search(key):
                        cls = label
                        break
                meta.append({"kind": kind, "key": key, "class": cls,
                             "value_sha256_12": hashlib.sha256(
                                 value.encode("utf-8")).hexdigest()[:12],
                             "value_len": len(value)})
            return meta

        self.session_meta = {
            "captured_at": datetime.now(timezone.utc).isoformat(),
            "profile_alias": "DOLA_RE_PROFILE",
            "cookie_source": self.cookie_source,
            "cookie_count": len(cookie_meta),
            "cookies": cookie_meta,
            "web_storage": storage_meta(inv.pop("localStorage"), "localStorage")
                           + storage_meta(inv.pop("sessionStorage"), "sessionStorage"),
            "indexed_db_names": inv.pop("indexedDB"),
            "service_workers": inv.pop("serviceWorkers"),
            "browser": inv,
        }
        self.state = SESSION_CAPTURED
        return self.session_meta

    # -- persistence ---------------------------------------------------------

    async def persist_session(self) -> Path:
        """Full session payload → DPAPI blob (values never hit disk plaintext)."""
        cookies = await self._context.cookies(ORIGIN)
        ls_ss = await self._page.evaluate(
            """() => ({
                localStorage: Object.fromEntries(Object.entries(localStorage)),
                sessionStorage: Object.fromEntries(Object.entries(sessionStorage)),
            })""")
        return save_session_encrypted({
            "schema": SESSION_STORE_SCHEMA,
            "saved_at": datetime.now(timezone.utc).isoformat(),
            "profile_alias": "DOLA_RE_PROFILE",
            "cookie_source": self.cookie_source,
            "cookies": cookies,
            "web_storage": ls_ss,
            "user_agent": self.session_meta.get("browser", {}).get("ua"),
        })

    def tracked_metadata(self) -> dict:
        meta = dict(self.session_meta)
        meta.pop("browser", None)
        return meta
