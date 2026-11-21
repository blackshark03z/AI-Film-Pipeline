import json
import os
import re
import shutil
import time
import uuid
import threading
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Iterator, List, Optional
from pydantic import BaseModel, Field

try:
    from . import send_halt
    from .config import ACCOUNTS_FILE, PROFILES_DIR, DEFAULT_MUSE_URL
    from .tempmail_client import TempMailClient
except ImportError:
    from core import send_halt
    from core.config import ACCOUNTS_FILE, PROFILES_DIR, DEFAULT_MUSE_URL
    from core.tempmail_client import TempMailClient

# Verification / unusual-activity page text (lower case). Seeing one stops ALL sending: never fail over to another
# account. Kept conservative; CAPTCHA widgets are matched separately.
BLOCK_TEXT_MARKERS = (
    "unusual activity",
    "suspicious activity",
    "verify your identity",
    "verify it's you",
    "verify it’s you",
    "account suspended",
    "account has been suspended",
    "account locked",
    "account has been locked",
    "temporarily blocked",
    "hoạt động bất thường",
    "xác minh danh tính",
)


# Human-check text of a challenge page or dialog (lower case).
CHALLENGE_TEXT_MARKERS = (
    "verify you are human",
    "verify you're human",
    "are you a robot",
    "i'm not a robot",
    "complete the security check",
    "xác minh bạn là con người",
    "tôi không phải là người máy",
    "không phải là người máy",
    "không phải người máy",
)

# The normal email security-code step of the login flow says these; they are not a block while the code field is
# visible. Every other marker (unusual activity, locked, human check, ...) still blocks next to an OTP form.
OTP_INSTRUCTION_MARKERS = (
    "verify it's you",
    "verify it’s you",
    "verify your identity",
    "xác minh danh tính",
)

# Reads only what a user would see as a challenge:
# - visible CAPTCHA / Turnstile widgets and challenge forms (never script or resource URLs, not the invisible reCAPTCHA
#   badge); visibility includes every ancestor (display, opacity, visibility) and the viewport;
# - text of visible system UI regions (dialogs, alerts, modal notices) and of any visible overlay that covers the UI
#   (fixed / absolute, large, or on top of the composer), whatever its ARIA role and even with the composer mounted;
# - the whole body only on a page without a visible composer (a full-page interstitial).
# Chat messages and the composer are never read.
CHALLENGE_PROBE_JS = r"""
() => {
  const vw = window.innerWidth || 0, vh = window.innerHeight || 0;
  const vis = (el) => {
    if (!el || !el.isConnected) return false;
    const own = getComputedStyle(el);
    if (own.visibility === 'hidden' || own.visibility === 'collapse') return false;
    for (let a = el; a && a.nodeType === 1; a = a.parentElement) {
      const st = getComputedStyle(a);
      if (st.display === 'none' || parseFloat(st.opacity || '1') === 0) return false;
    }
    const r = el.getBoundingClientRect();
    if (r.width <= 2 || r.height <= 2) return false;
    return r.bottom > 0 && r.right > 0 && r.top < vh && r.left < vw;
  };
  const widgetSel = [
    'iframe[src*="hcaptcha.com"]', 'iframe[src*="recaptcha"]', 'iframe[src*="challenges.cloudflare.com"]',
    'iframe[title*="captcha" i]', 'iframe[title*="challenge" i]',
    '.h-captcha', '.g-recaptcha', '.cf-turnstile', '#challenge-form', '#challenge-stage', '#cf-challenge-running'
  ].join(',');
  let widget = false;
  for (const el of document.querySelectorAll(widgetSel)) {
    if (el.closest('.grecaptcha-badge')) continue;
    if ((el.getAttribute('src') || '').toLowerCase().includes('size=invisible')) continue;
    if (vis(el)) { widget = true; break; }
  }
  const composers = Array.from(document.querySelectorAll('textarea, [contenteditable="true"], [contenteditable=""]'))
    .filter(vis);
  const chatSel = '[data-message-author-role], [data-testid*="message" i], [class*="message" i], [role="log"], '
    + 'article, textarea, [contenteditable]';
  const holdsChat = '[data-message-author-role], [role="log"], textarea, [contenteditable="true"], [contenteditable=""]';
  const inChat = (el) => { const p = el.parentElement; return !!(p && p.closest(chatSel)); };
  const parts = [];
  const seen = new Set();
  const take = (el) => { if (el && !seen.has(el)) { seen.add(el); parts.push(el.innerText || ''); } };
  const sysSel = '[role="dialog"], [role="alertdialog"], [role="alert"], dialog[open], [aria-modal="true"]';
  for (const el of document.querySelectorAll(sysSel)) {
    if (vis(el) && !inChat(el)) take(el);
  }
  // Overlays covering the UI, regardless of role: fixed / absolute layers over >= 40% of the viewport that hold no
  // chat or composer (the app shell holds them and is skipped).
  const area = (r) => Math.max(0, Math.min(r.right, vw) - Math.max(r.left, 0))
    * Math.max(0, Math.min(r.bottom, vh) - Math.max(r.top, 0));
  if (document.body && vw && vh) {
    for (const el of document.body.getElementsByTagName('*')) {
      const pos = getComputedStyle(el).position;
      if (pos !== 'fixed' && pos !== 'absolute') continue;
      if (area(el.getBoundingClientRect()) < 0.4 * vw * vh) continue;
      if (!vis(el) || inChat(el) || el.querySelector(holdsChat)) continue;
      take(el);
    }
    // Anything painted on top of the composer: read the covering layer (its largest ancestor without the composer).
    for (const c of composers) {
      const r = c.getBoundingClientRect();
      const top = document.elementFromPoint(
        Math.min(vw - 1, Math.max(0, r.left + r.width / 2)), Math.min(vh - 1, Math.max(0, r.top + r.height / 2)));
      if (!top || top === c || c.contains(top) || top.contains(c)) continue;
      let layer = top;
      while (layer.parentElement && layer.parentElement !== document.body && !layer.parentElement.contains(c)) {
        layer = layer.parentElement;
      }
      if (!inChat(layer) && !layer.querySelector(holdsChat)) take(layer);
    }
  }
  if (!composers.length && document.body) parts.push(document.body.innerText || '');
  const otp = Array.from(document.querySelectorAll(
    'input[aria-label*="security code" i], input[autocomplete="one-time-code"], input[name*="otp" i]')).some(vis);
  return {widget: widget, text: parts.join('\n').slice(0, 20000), interstitial: !composers.length, otp: otp};
}
"""


def challenge_reason(probe: Any, ignore_text_on_otp: bool = False) -> Optional[str]:
    """"BLOCKED: ..." when the probe saw a visible challenge or a verification / unusual-activity notice.

    With `ignore_text_on_otp` (login) and the security-code field visible, only the normal OTP instructions are
    exempt; every other notice still blocks."""
    if not isinstance(probe, dict):
        return None
    if probe.get("widget"):
        return "BLOCKED: CAPTCHA / anti-bot challenge shown. Dừng mọi lệnh gửi, chờ người dùng xử lý."
    text = str(probe.get("text") or "").lower()
    if any(m in text for m in CHALLENGE_TEXT_MARKERS):
        return "BLOCKED: CAPTCHA / human check shown. Dừng mọi lệnh gửi, chờ người dùng xử lý."
    otp_exempt = OTP_INSTRUCTION_MARKERS if (ignore_text_on_otp and probe.get("otp")) else ()
    if any(m in text for m in BLOCK_TEXT_MARKERS if m not in otp_exempt):
        return "BLOCKED: verification / unusual-activity notice. Dừng mọi lệnh gửi, chờ người dùng xử lý."
    return None


class _LoginBlocked(Exception):
    """A challenge seen during a login step: the login result is BLOCKED (never an ordinary ERROR)."""


class AccountSchema(BaseModel):
    id: str = Field(default_factory=lambda: f"acc_{uuid.uuid4().hex[:8]}")
    name: str
    email: Optional[str] = None
    invite_code: Optional[str] = None
    password: Optional[str] = None
    raw_cookie: Optional[str] = None
    login_method: Optional[str] = None  # "cookie", "otp", "manual"
    proxy: Optional[str] = None
    status: str = "UNCHECKED"  # UNCHECKED, READY, BUSY, COOLDOWN, ERROR, LOGGED_OUT
    error_message: Optional[str] = None
    usage_info: Optional[Dict[str, Any]] = None
    total_rendered: int = 0
    created_at: str = Field(default_factory=lambda: datetime.now().isoformat())
    last_used: Optional[str] = None

class AccountStoreUnreadable(RuntimeError):
    """`accounts.json` is non-empty but unreadable or not a JSON list. It is NEVER treated as "no accounts": a writer
    that read `[]` here would overwrite every account. Readers may show the error; nothing is saved."""


class AccountStoreLockTimeout(RuntimeError):
    """The cross-process accounts lock could not be taken in time."""


DEFAULT_ACCOUNTS_LOCK_TIMEOUT_S = 30.0
_REPLACE_RETRIES = 8  # os.replace on Windows can hit a sharing violation while another process reads the file


class AccountManager:
    def __init__(self, storage_file: Path = ACCOUNTS_FILE, profiles_dir: Path = PROFILES_DIR):
        self.storage_file = storage_file
        self.profiles_dir = profiles_dir
        self.lock = threading.RLock()
        self._txn_depth = 0
        self._verify_locks: Dict[str, threading.Lock] = {}
        self._ensure_storage()

    def _get_verify_lock(self, account_id: str) -> threading.Lock:
        with self.lock:
            v_lock = self._verify_locks.get(account_id)
            if v_lock is None:
                v_lock = threading.Lock()
                self._verify_locks[account_id] = v_lock
            return v_lock

    @property
    def lock_path(self) -> Path:
        """`accounts.lock` next to the storage file (contract v8: one OS lock for every accounts.json writer)."""
        return Path(self.storage_file).with_suffix(".lock")

    @staticmethod
    def _lock_timeout_s() -> float:
        try:
            return float(os.environ.get("MUSE_ACCOUNTS_LOCK_TIMEOUT_S") or DEFAULT_ACCOUNTS_LOCK_TIMEOUT_S)
        except ValueError:
            return DEFAULT_ACCOUNTS_LOCK_TIMEOUT_S

    @contextmanager
    def _os_lock(self) -> Iterator[None]:
        """1-byte OS lock on `accounts.lock` (same primitive as `send_halt.halt_file_lock`: msvcrt / fcntl)."""
        path = self.lock_path
        path.parent.mkdir(parents=True, exist_ok=True)
        fd = os.open(str(path), os.O_RDWR | os.O_CREAT, 0o644)
        deadline = time.monotonic() + self._lock_timeout_s()
        locked = False
        try:
            while True:
                try:
                    if os.name == "nt":
                        import msvcrt

                        os.lseek(fd, 0, os.SEEK_SET)
                        msvcrt.locking(fd, msvcrt.LK_NBLCK, 1)
                    else:
                        import fcntl

                        fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
                    locked = True
                    break
                except OSError:
                    if time.monotonic() >= deadline:
                        raise AccountStoreLockTimeout(str(path))
                    time.sleep(0.02)
            yield
        finally:
            if locked:
                try:
                    if os.name == "nt":
                        import msvcrt

                        os.lseek(fd, 0, os.SEEK_SET)
                        msvcrt.locking(fd, msvcrt.LK_UNLCK, 1)
                    else:
                        import fcntl

                        fcntl.flock(fd, fcntl.LOCK_UN)
                except OSError:
                    pass
            os.close(fd)

    def _ensure_storage(self):
        # Create-exclusive under the OS lock: never replaces an existing (even unreadable) file.
        with self.lock:
            if not self.storage_file.exists():
                self.storage_file.parent.mkdir(parents=True, exist_ok=True)
                with self._os_lock():
                    if not self.storage_file.exists():
                        self.storage_file.write_text("[]", encoding="utf-8")

    def _read_all(self) -> List[Dict[str, Any]]:
        """Missing or empty file -> []. Non-empty but unreadable / not a JSON list -> AccountStoreUnreadable."""
        with self.lock:
            last: Optional[BaseException] = None
            for attempt in range(_REPLACE_RETRIES):
                try:
                    content = self.storage_file.read_text(encoding="utf-8")
                except FileNotFoundError:
                    return []
                except OSError as exc:  # e.g. a sharing violation while another process replaces the file
                    last = exc
                    time.sleep(0.02 * (attempt + 1))
                    continue
                if not content.strip():
                    return []
                try:
                    data = json.loads(content)
                except ValueError as exc:
                    raise AccountStoreUnreadable(f"{self.storage_file.name} is not valid JSON: {exc}") from exc
                if not isinstance(data, list) or not all(isinstance(a, dict) for a in data):
                    raise AccountStoreUnreadable(f"{self.storage_file.name} is not a JSON list of accounts")
                return data
            raise AccountStoreUnreadable(f"{self.storage_file.name} cannot be read: {last}")

    def _write_all_locked(self, accounts: List[Dict[str, Any]]) -> None:
        """Caller holds the OS lock. tmp + replace (short retry on a Windows sharing violation)."""
        self.storage_file.parent.mkdir(parents=True, exist_ok=True)
        tmp_f = self.storage_file.with_name(f".{self.storage_file.name}.tmp.{os.getpid()}.{threading.get_ident()}")
        tmp_f.write_text(json.dumps(accounts, indent=2, ensure_ascii=False), encoding="utf-8")
        try:
            for attempt in range(_REPLACE_RETRIES):
                try:
                    os.replace(tmp_f, self.storage_file)
                    return
                except PermissionError:
                    if attempt == _REPLACE_RETRIES - 1:
                        raise
                    time.sleep(0.02 * (attempt + 1))
        finally:
            if tmp_f.exists():
                try:
                    tmp_f.unlink()
                except OSError:
                    pass

    @contextmanager
    def _locked_update(self, allow_shrink: bool = False) -> Iterator[List[Dict[str, Any]]]:
        """The ONE way to change accounts.json: OS lock held across reload -> mutate -> replace, so a concurrent
        writer (another process, the UI, a cookie write-back, a relogin) can never lose this update or be lost by it.
        Yields the freshly read list; the caller mutates it in place. Written only when it changed. Fewer accounts than
        were read are refused unless `allow_shrink` (an explicit delete). Unreadable store -> AccountStoreUnreadable
        and nothing is saved."""
        with self.lock:
            if self._txn_depth:
                raise RuntimeError("nested _locked_update")
            with self._os_lock():
                self._txn_depth += 1
                try:
                    accounts = self._read_all()
                    n_read = len(accounts)
                    before = json.dumps(accounts, sort_keys=True, ensure_ascii=False)
                    yield accounts
                    if json.dumps(accounts, sort_keys=True, ensure_ascii=False) == before:
                        return
                    if len(accounts) < n_read and not allow_shrink:
                        raise RuntimeError(
                            f"refusing to write {len(accounts)} accounts after reading {n_read} (not a delete)")
                    self._write_all_locked(accounts)
                finally:
                    self._txn_depth -= 1

    def list_accounts(self) -> List[Dict[str, Any]]:
        return self._read_all()

    def get_account(self, account_id: str) -> Optional[Dict[str, Any]]:
        for acc in self._read_all():
            if acc["id"] == account_id:
                return acc
        return None

    def get_account_by_email(self, email: str) -> Optional[Dict[str, Any]]:
        if not email:
            return None
        clean_email = email.strip().lower()
        for acc in self._read_all():
            if (acc.get("email") or "").strip().lower() == clean_email:
                return acc
        return None

    def add_account(
        self,
        name: str,
        proxy: Optional[str] = None,
        email: Optional[str] = None,
        invite_code: Optional[str] = None,
        password: Optional[str] = None,
        raw_cookie: Optional[str] = None
    ) -> Dict[str, Any]:
        new_acc = AccountSchema(
            name=name.strip(),
            proxy=proxy.strip() if proxy else None,
            email=email.strip() if email else None,
            invite_code=invite_code.strip() if invite_code else None,
            password=password.strip() if password else None,
            raw_cookie=raw_cookie.strip() if raw_cookie else None
        )
        acc_dict = new_acc.model_dump()
        
        # Tạo thư mục profile riêng
        p_dir = self.get_profile_dir(new_acc.id)
        p_dir.mkdir(parents=True, exist_ok=True)
        
        with self._locked_update() as accounts:
            accounts.append(acc_dict)
        return acc_dict

    def update_account(self, account_id: str, **kwargs) -> Optional[Dict[str, Any]]:
        target = None
        with self._locked_update() as accounts:
            for acc in accounts:
                if acc["id"] == account_id:
                    for k, v in kwargs.items():
                        if v is not None or k in ["proxy", "error_message", "email", "invite_code", "password", "raw_cookie", "login_method", "usage_info"]:
                            acc[k] = v
                    target = acc
                    break
        return dict(target) if target else None

    def increment_account(self, account_id: str, field: str, n: int = 1) -> Optional[int]:
        """Atomic `acc[field] += n` inside `_locked_update` (reload -> add -> replace under the OS lock), so a
        concurrent increment or relogin can never be lost. Returns the new value, None if the account is missing."""
        new_value: Optional[int] = None
        with self._locked_update() as accounts:
            for acc in accounts:
                if acc["id"] == account_id:
                    try:
                        cur = int(acc.get(field) or 0)
                    except (TypeError, ValueError):
                        cur = 0
                    new_value = cur + int(n)
                    acc[field] = new_value
                    break
        return new_value

    def delete_account(self, account_id: str, remove_profile: bool = True) -> bool:
        with self._locked_update(allow_shrink=True) as accounts:
            kept = [a for a in accounts if a["id"] != account_id]
            if len(kept) == len(accounts):
                return False
            accounts[:] = kept  # explicit delete: the only writer allowed to shrink the list
        if remove_profile:
            p_dir = self.get_profile_dir(account_id)
            if p_dir.exists():
                try:
                    shutil.rmtree(p_dir, ignore_errors=True)
                except Exception:
                    pass
        return True

    def get_profile_dir(self, account_id: str) -> Path:
        p_dir = self.profiles_dir / account_id
        p_dir.mkdir(parents=True, exist_ok=True)
        return p_dir

    @staticmethod
    def parse_cookie_string(cookie_raw: Optional[str], default_domain: str = ".muse.ai") -> List[Dict[str, Any]]:
        """Phân tích chuỗi cookie (hỗ trợ cả JSON array lẫn định dạng key=val; key2=val2)."""
        if not cookie_raw or not cookie_raw.strip():
            return []

        raw = cookie_raw.strip()

        # 1. Thử parse dạng JSON array
        if (raw.startswith("[") and raw.endswith("]")) or (raw.startswith("{") and raw.endswith("}")):
            try:
                data = json.loads(raw)
                if isinstance(data, dict):
                    data = [data]
                valid_cookies = []
                for item in data:
                    if isinstance(item, dict) and "name" in item and "value" in item:
                        domain = item.get("domain") or default_domain
                        valid_cookies.append({
                            "name": str(item["name"]),
                            "value": str(item["value"]),
                            "domain": domain,
                            "path": item.get("path", "/"),
                            "sameSite": item.get("sameSite", "Lax"),
                            "secure": item.get("secure", True)
                        })
                if valid_cookies:
                    return valid_cookies
            except Exception:
                pass

        # 2. Parse dạng chuẩn: key=value; key2=value2
        cookies = []
        pairs = raw.split(";")
        for p in pairs:
            if not p or "=" not in p:
                continue
            k, v = p.split("=", 1)
            k_clean = k.strip()
            v_clean = v.strip().strip('"')
            if k_clean:
                cookies.append({
                    "name": k_clean,
                    "value": v_clean,
                    "domain": default_domain,
                    "path": "/",
                    "sameSite": "Lax",
                    "secure": True
                })

        return cookies

    def bulk_import_accounts(self, raw_text: str) -> Dict[str, Any]:
        """Nhập danh sách tài khoản theo định dạng: email|invite_code|password|cookie
        Nếu email đã tồn tại: Cập nhật thông tin và reset trạng thái UNCHECKED để xác thực lại.
        Nếu email mới: Tạo tài khoản mới.
        """
        lines = [line.strip() for line in raw_text.splitlines() if line.strip()]
        imported_count = 0
        updated_count = 0
        processed_accounts = []

        for line in lines:
            if line.startswith("#") or line.startswith("//"):
                continue

            parts = [p.strip() for p in line.split("|")]
            first_tok = parts[0] if len(parts) >= 1 else ""
            invite_code = parts[1] if len(parts) >= 2 else ""
            password = parts[2] if len(parts) >= 3 else ""
            raw_cookie = parts[3] if len(parts) >= 4 else ""
            proxy = parts[4] if len(parts) >= 5 else None

            is_email = bool(first_tok and "@" in first_tok)
            if not is_email and not raw_cookie:
                continue

            email = first_tok if is_email else None
            acc_name = email.split("@")[0] if email else (first_tok or f"Muse_Cookie_{imported_count + 1}")

            existing = (
                self.get_account_by_email(email)
                if email
                else next((a for a in self._read_all() if (a.get("name") or "") == acc_name), None)
            )
            if existing:
                aid = existing["id"]
                # Pass ONLY the fields this import line supplied: re-sending the (stale) values read above would
                # overwrite a cookie/password a concurrent relogin saved in between.
                supplied: Dict[str, Any] = {"status": "UNCHECKED", "error_message": None}
                if invite_code:
                    supplied["invite_code"] = invite_code
                if password:
                    supplied["password"] = password
                if raw_cookie:
                    supplied["raw_cookie"] = raw_cookie
                if proxy:
                    supplied["proxy"] = proxy
                self.update_account(aid, **supplied)
                updated_count += 1
                processed_accounts.append(self.get_account(aid))
            else:
                new_acc = self.add_account(
                    name=acc_name,
                    email=email,
                    invite_code=invite_code,
                    password=password,
                    raw_cookie=raw_cookie,
                    proxy=proxy
                )
                imported_count += 1
                processed_accounts.append(new_acc)

        return {
            "success": True,
            "imported_count": imported_count,
            "updated_count": updated_count,
            "total_processed": len(processed_accounts),
            "accounts": processed_accounts
        }

    @staticmethod
    def parse_proxy(proxy_str: Optional[str]) -> Optional[Dict[str, str]]:
        if not proxy_str or not proxy_str.strip():
            return None
        raw = proxy_str.strip()
        
        if "://" in raw:
            parts = raw.split("://", 1)
            scheme = parts[0]
            rest = parts[1]
            if "@" in rest:
                auth_part, host_part = rest.split("@", 1)
                user, password = auth_part.split(":", 1) if ":" in auth_part else (auth_part, "")
                return {
                    "server": f"{scheme}://{host_part}",
                    "username": user,
                    "password": password
                }
            else:
                return {"server": raw}
        
        tokens = raw.split(":")
        if len(tokens) == 4:
            host, port, user, pwd = tokens
            return {
                "server": f"http://{host}:{port}",
                "username": user,
                "password": pwd
            }
        elif len(tokens) == 2:
            host, port = tokens
            return {"server": f"http://{host}:{port}"}
            
        return {"server": f"http://{raw}"}

    def launch_login_browser_process(self, account_id: str, target_url: str = DEFAULT_MUSE_URL):
        """Mở trình duyệt trực quan để người dùng đăng nhập trong một thread riêng."""
        acc = self.get_account(account_id)
        if not acc:
            raise ValueError(f"Không tìm thấy tài khoản {account_id}")

        profile_dir = self.get_profile_dir(account_id)
        proxy_cfg = self.parse_proxy(acc.get("proxy"))

        def _browser_thread():
            from playwright.sync_api import sync_playwright
            with sync_playwright() as p:
                launch_args = {
                    "user_data_dir": str(profile_dir),
                    "headless": False,
                    "args": [
                        "--no-first-run",
                        "--no-default-browser-check",
                        "--disable-blink-features=AutomationControlled"
                    ]
                }
                if proxy_cfg:
                    launch_args["proxy"] = proxy_cfg

                context = p.chromium.launch_persistent_context(**launch_args)
                
                raw_cookie = acc.get("raw_cookie")
                if raw_cookie:
                    parsed = self.parse_cookie_string(raw_cookie)
                    if parsed:
                        try:
                            context.add_cookies(parsed)
                        except Exception:
                            pass

                page = context.pages[0] if context.pages else context.new_page()
                page.goto(target_url, wait_until="domcontentloaded")
                
                try:
                    page.wait_for_event("close", timeout=0)
                except Exception:
                    pass
                finally:
                    try:
                        context.close()
                    except Exception:
                        pass

        t = threading.Thread(target=_browser_thread, daemon=True)
        t.start()
        return True

    @staticmethod
    def _is_muse_chat_ready(page) -> bool:
        """Kiểm tra đã vào giao diện chat Muse kèm ô nhập lệnh và upload file chưa."""
        try:
            body_text = (page.locator("body").inner_text(timeout=3000) or "").lower()
            if any(k in body_text for k in ("what's your name", "choose your", "confirm your birthday", "enter the 6-digit")):
                return False
            box = page.locator('textarea[placeholder*="Message" i], textarea').first
            file_in = page.locator('input[type="file"]').first
            return (box.count() > 0 and box.is_visible()) and (file_in.count() > 0)
        except Exception:
            return False

    @staticmethod
    def _detect_captcha_or_block(page) -> Optional[str]:
        """Phát hiện CAPTCHA / Cloudflare / trang xác minh để dừng ngay, không bao giờ vượt rào.

        The message starts with "BLOCKED:"; callers return status BLOCKED, which halts all sending."""
        try:
            probe = page.evaluate(CHALLENGE_PROBE_JS)
        except Exception:
            return None
        return challenge_reason(probe, ignore_text_on_otp=True)

    @staticmethod
    def _complete_onboarding_sync(page) -> None:
        """Hoàn tất màn hình Birthday / đặt tên / chọn persona Muse nếu là tài khoản mới."""
        for _ in range(5):
            time.sleep(1.5)
            try:
                body_txt = (page.locator("body").inner_text(timeout=3000) or "").lower()
            except Exception:
                body_txt = ""

            # 1. Màn hình Birthday / First+Last name
            fn = page.locator('input[aria-label="First name"], input[placeholder*="First name" i]').first
            if fn.count() > 0 and fn.is_visible():
                fn.fill("David")
                ln = page.locator('input[aria-label="Last name"], input[placeholder*="Last name" i]').first
                if ln.count() > 0 and ln.is_visible():
                    ln.fill("Director")

                # Chọn Năm sinh qua nút dropdown Year (hoặc <select> fallback)
                year_btn = page.locator('button[aria-label="Year"]').first
                if year_btn.count() > 0 and year_btn.is_visible():
                    try:
                        year_btn.click()
                        time.sleep(0.8)
                        opt_1995 = page.locator(
                            'div[role="option"]:has-text("1995"), [role="menuitem"]:has-text("1995"), button:has-text("1995"), [data-value="1995"]'
                        ).first
                        if opt_1995.count() > 0:
                            opt_1995.click()
                            time.sleep(0.6)
                    except Exception:
                        pass

                # Nếu vẫn có Month/Day button và nút Confirm còn disabled, chọn option đầu nếu cần
                for lbl in ("Month", "Day"):
                    b_lbl = page.locator(f'button[aria-label="{lbl}"]').first
                    if b_lbl.count() > 0 and b_lbl.is_visible():
                        try:
                            cur_txt = (b_lbl.inner_text() or "").strip().lower()
                            if cur_txt in ("", "month", "day", "select"):
                                b_lbl.click()
                                time.sleep(0.5)
                                first_opt = page.locator('div[role="option"], [role="menuitem"]').first
                                if first_opt.count() > 0:
                                    first_opt.click()
                                    time.sleep(0.4)
                        except Exception:
                            pass

                for sel in page.locator("select").all():
                    try:
                        opts = sel.locator("option").all_inner_texts()
                        if any("1995" in o for o in opts):
                            sel.select_option("1995")
                            sel.dispatch_event("change")
                            break
                    except Exception:
                        pass

                cbtn = page.locator('button[data-pel-click="login_birthday_continue_click"], button:has-text("Confirm")').first
                if cbtn.count() > 0 and not cbtn.is_disabled():
                    cbtn.click()
                    time.sleep(4)
                    continue

            # 2. Hỏi tên người dùng trong chat onboarding
            if "what's your name" in body_txt:
                cbox = page.locator('textarea, input[placeholder*="Message" i], [contenteditable="true"]').first
                if cbox.count() > 0 and cbox.is_visible():
                    cbox.click()
                    cbox.fill("Director")
                    page.keyboard.press("Enter")
                    time.sleep(3)
                    continue

            # 3. Chọn persona Muse / bấm Continue / Get started
            muse_btn = page.locator('button:has-text("Muse"), [role="button"]:has-text("Muse")').first
            if muse_btn.count() > 0 and muse_btn.is_visible():
                muse_btn.click()
                time.sleep(2)

            next_btn = page.locator('button:has-text("Get started"), button:has-text("Continue"), button:has-text("Next")').first
            if next_btn.count() > 0 and next_btn.is_visible() and not next_btn.is_disabled():
                next_btn.click()
                time.sleep(2)
                continue

            if AccountManager._is_muse_chat_ready(page):
                break

    @staticmethod
    def get_effective_quota_pct(acc: Optional[Dict[str, Any]]) -> float:
        """Tính tổng % công suất khả dụng (weekly còn lại + bonus còn lại) để xếp lịch Pool."""
        u = (acc or {}).get("usage_info") or {}
        rem_w = u.get("weekly_remaining_pct")
        w_val = float(rem_w) if rem_w is not None else 50.0
        b_rem = u.get("bonus_remaining_pct")
        b_left = u.get("bonus_tokens_left")
        b_val = float(b_rem) if b_rem is not None else (100.0 if (b_left or 0) > 0 else 0.0)
        return w_val + b_val

    @staticmethod
    def parse_usage_from_settings_text(dialog_text: str) -> Optional[Dict[str, Any]]:
        """Phân tích thông tin hạn mức (Plan, % đã dùng, bonus tokens, thời điểm reset) từ Settings dialog của Muse."""
        if not dialog_text or "usage" not in dialog_text.lower():
            return None

        m_usage = re.search(r"\bUsage\b(.*)", dialog_text, re.DOTALL | re.IGNORECASE)
        if not m_usage:
            return None

        usage_tail = m_usage.group(1)
        m_stop = re.search(r"\b(?:Language|Appearance|Redeem invite code)\b", usage_tail, re.IGNORECASE)
        usage_block = usage_tail[: m_stop.start()] if m_stop else usage_tail[:500]

        parts = re.split(r"additional\s+tokens", usage_block, maxsplit=1, flags=re.IGNORECASE)
        main_part = parts[0]
        bonus_part = parts[1] if len(parts) > 1 else ""

        m_plan = re.search(r"([A-Za-z0-9 +\-]{1,25}\bplan\b)", main_part, re.IGNORECASE)
        if m_plan:
            plan = m_plan.group(1).strip()
        elif "free" in main_part.lower():
            plan = "Free plan"
        else:
            plan = "Muse Account"

        m_reset = re.search(
            r"((?:Weekly|Daily|Monthly)\s+limit\s+resets[^\n\r]*|Resets\s+(?:on|in)[^\n\r]*)",
            main_part,
            re.IGNORECASE,
        )
        reset_text = m_reset.group(1).strip() if m_reset else None

        m_used = re.search(r"(\d+(?:\.\d+)?)\s*%\s*used", main_part, re.IGNORECASE)
        weekly_used_pct: Optional[float] = None
        weekly_remaining_pct: Optional[float] = None
        if m_used:
            weekly_used_pct = max(0.0, min(100.0, float(m_used.group(1))))
            weekly_remaining_pct = round(max(0.0, 100.0 - weekly_used_pct), 1)

        bonus_used_pct: Optional[float] = None
        bonus_remaining_pct: Optional[float] = None
        bonus_tokens_detail: Optional[str] = None
        bonus_tokens_left: Optional[int] = None
        if bonus_part:
            m_b_used = re.search(r"(\d+(?:\.\d+)?)\s*%\s*used", bonus_part, re.IGNORECASE)
            if m_b_used:
                bonus_used_pct = max(0.0, min(100.0, float(m_b_used.group(1))))
                bonus_remaining_pct = round(max(0.0, 100.0 - bonus_used_pct), 1)
            m_b_det = re.search(r"\(([^()\n]*tokens?[^()\n]*)\)", bonus_part, re.IGNORECASE)
            if m_b_det:
                bonus_tokens_detail = m_b_det.group(1).strip()
            m_b_cnt = re.search(
                r"([\d,]+(?:\.\d+)?)\s*([KMB])?\s*tokens?(?:\s*(?:left|remaining))?",
                bonus_part,
                re.IGNORECASE,
            )
            if m_b_cnt:
                num_val = float(m_b_cnt.group(1).replace(",", ""))
                unit = (m_b_cnt.group(2) or "").upper()
                mult = {"K": 1_000, "M": 1_000_000, "B": 1_000_000_000}
                bonus_tokens_left = int(round(num_val * mult.get(unit, 1)))
            if not bonus_tokens_detail:
                for bline in bonus_part.splitlines():
                    bl = bline.strip()
                    if bl and re.search(r"token|used|never\s+expires|left", bl, re.IGNORECASE):
                        bonus_tokens_detail = bl
                        break
            if bonus_remaining_pct is None and bonus_tokens_left is not None and bonus_tokens_left > 0:
                bonus_remaining_pct = 100.0

        if weekly_used_pct is None and bonus_tokens_left is None and bonus_used_pct is None and reset_text is None:
            return None

        has_bonus = bool(
            (bonus_tokens_left is not None and bonus_tokens_left > 0)
            or (bonus_used_pct is not None and bonus_used_pct < 100.0)
            or (bonus_remaining_pct is not None and bonus_remaining_pct > 0.0)
        )
        is_exhausted = bool(
            weekly_used_pct is not None
            and weekly_used_pct >= 100.0
            and not has_bonus
        )

        rem_part = (
            f"Còn {weekly_remaining_pct:g}% (đã dùng {weekly_used_pct:g}%)"
            if weekly_used_pct is not None
            else "Chưa rõ %"
        )
        if has_bonus:
            b_desc = bonus_tokens_detail or (
                f"{bonus_tokens_left:,} tokens left"
                if bonus_tokens_left is not None
                else f"Bonus còn {bonus_remaining_pct:g}%"
            )
            bonus_str = f" • Bonus: {b_desc}"
        elif bonus_tokens_left is not None:
            bonus_str = f" • Bonus: {bonus_tokens_left} tokens"
        else:
            bonus_str = ""
        reset_str = f" • {reset_text}" if reset_text else ""
        summary = f"{plan}: {rem_part}{bonus_str}{reset_str}"

        return {
            "plan": plan,
            "weekly_used_pct": weekly_used_pct,
            "weekly_remaining_pct": weekly_remaining_pct,
            "reset_text": reset_text,
            "bonus_used_pct": bonus_used_pct,
            "bonus_remaining_pct": bonus_remaining_pct,
            "bonus_tokens_left": bonus_tokens_left,
            "bonus_tokens_detail": bonus_tokens_detail,
            "is_exhausted": is_exhausted,
            "summary": summary,
            "checked_at": datetime.now().isoformat(),
        }

    @staticmethod
    def _open_settings_dialog_sync(page) -> Any:
        """Mở modal Settings (Ctrl+,) với fallback icon Settings."""
        page.keyboard.press("Escape")
        time.sleep(0.3)
        page.keyboard.press("Control+,")
        time.sleep(1.8)
        dlg = page.locator('[role="dialog"]').first
        if dlg.count() == 0 or not dlg.is_visible():
            s_btn = page.locator('[aria-label="Settings"]').first
            if s_btn.count() > 0 and s_btn.is_visible():
                s_btn.click()
                time.sleep(0.8)
                m_item = page.locator('[role="menuitem"]:has-text("Settings")').first
                if m_item.count() > 0 and m_item.is_visible():
                    m_item.click()
                    time.sleep(1.5)
            dlg = page.locator('[role="dialog"]').first
        return dlg

    @staticmethod
    def _extract_usage_info_sync(page) -> Optional[Dict[str, Any]]:
        """Mở modal Settings (Ctrl+,) chỉ đọc inner_text vùng Usage và bấm Escape."""
        try:
            dlg = AccountManager._open_settings_dialog_sync(page)
            if dlg.count() > 0 and dlg.is_visible():
                txt = dlg.inner_text(timeout=2500)
                page.keyboard.press("Escape")
                time.sleep(0.3)
                parsed = AccountManager.parse_usage_from_settings_text(txt)
                if parsed is None:
                    print(f"[!] Usage text unparsed: {txt[:350]!r}")
                else:
                    parsed["raw_usage_snippet"] = txt[:600]
                return parsed
        except Exception:
            pass
        return None

    @staticmethod
    def _redeem_code_in_page_sync(page, invite_code: str) -> Dict[str, Any]:
        """Mở Settings -> Redeem invite code, nhập mã và Confirm hoàn toàn headless."""
        code = (invite_code or "").strip()
        if not code:
            return {"success": False, "redeemed": False, "message": "Mã invite rỗng."}
        try:
            dlg = AccountManager._open_settings_dialog_sync(page)
            if dlg.count() == 0 or not dlg.is_visible():
                return {"success": False, "redeemed": False, "message": "Không mở được Settings dialog."}

            redeem_trigger = page.get_by_text("Redeem invite code", exact=False).first
            if redeem_trigger.count() == 0 or not redeem_trigger.is_visible():
                page.keyboard.press("Escape")
                return {"success": False, "redeemed": False, "message": "Không thấy mục Redeem invite code trong Settings."}

            redeem_trigger.click()
            time.sleep(1.5)

            code_in = page.locator('input[aria-label="Invite code"], [role="dialog"] input[type="text"]').first
            if code_in.count() == 0:
                page.keyboard.press("Escape")
                return {"success": False, "redeemed": False, "message": "Không thấy ô nhập Invite code."}

            # Ô Invite code dùng kiểu 6 ô OTP (input.sr-only nằm dưới overlay visual) nên focus/force-fill + typefallback
            try:
                code_in.focus()
            except Exception:
                code_in.click(force=True)
            time.sleep(0.3)
            code_in.fill(code)
            time.sleep(0.8)

            confirm_btn = page.locator('[role="dialog"] button:has-text("Confirm")').first
            if confirm_btn.count() > 0 and confirm_btn.is_disabled():
                try:
                    code_in.locator("xpath=..").click(force=True)
                except Exception:
                    pass
                page.keyboard.type(code, delay=50)
                time.sleep(0.8)

            for _ in range(6):
                if confirm_btn.count() > 0 and confirm_btn.is_visible() and not confirm_btn.is_disabled():
                    break
                time.sleep(0.5)

            if confirm_btn.count() == 0 or confirm_btn.is_disabled():
                page.keyboard.press("Escape")
                time.sleep(0.3)
                page.keyboard.press("Escape")
                return {"success": False, "redeemed": False, "message": "Nút Confirm bị khóa sau khi nhập mã."}

            confirm_btn.click()
            time.sleep(3.5)

            post_txts = []
            try:
                post_txts = [d.inner_text(timeout=2000) for d in page.locator('[role="dialog"]').all()]
            except Exception:
                pass
            post_joined = " | ".join(post_txts).strip()
            low = post_joined.lower()

            for _ in range(2):
                page.keyboard.press("Escape")
                time.sleep(0.5)

            err_tokens = (
                "invalid", "expired", "already been redeemed", "already used",
                "not valid", "could not", "try again",
                "48-hour window", "window to redeem", "has passed",
            )
            if "redeem a code" in low and any(tok in low for tok in err_tokens):
                err_lines = [
                    ln.strip() for ln in post_joined.splitlines()
                    if ln.strip() and any(tok in ln.lower() for tok in err_tokens)
                ]
                err_msg = err_lines[0] if err_lines else post_joined[:250]
                return {"success": False, "redeemed": False, "dialog_response": post_joined, "message": err_msg}

            return {"success": True, "redeemed": True, "dialog_response": post_joined, "message": "Đã gửi & xác nhận mã thành công."}
        except Exception as e:
            try:
                page.keyboard.press("Escape")
            except Exception:
                pass
            return {"success": False, "redeemed": False, "message": f"Lỗi khi redeem code: {e}"}

    def redeem_invite_code(
        self,
        account_id: str,
        invite_code: str,
        target_url: str = DEFAULT_MUSE_URL,
    ) -> Dict[str, Any]:
        """Đăng nhập headless, nhập mã mời trong Settings -> Redeem invite code và đọc lại Usage/Bonus tokens."""
        v_lock = self._get_verify_lock(account_id)
        if not v_lock.acquire(blocking=False):
            return {"status": "CHECKING", "message": "Tài khoản đang bận kiểm tra..."}
        try:
            acc = self.get_account(account_id)
            if not acc:
                return {"status": "ERROR", "message": "Tài khoản không tồn tại"}

            profile_dir = self.get_profile_dir(account_id)
            proxy_cfg = self.parse_proxy(acc.get("proxy"))
            raw_cookie = acc.get("raw_cookie")
            code = (invite_code or "").strip()

            from playwright.sync_api import sync_playwright
            with sync_playwright() as p:
                launch_args = {
                    "user_data_dir": str(profile_dir),
                    "headless": True,
                    "accept_downloads": True,
                    "args": [
                        "--no-first-run",
                        "--no-default-browser-check",
                        "--disable-blink-features=AutomationControlled",
                    ],
                }
                if proxy_cfg:
                    launch_args["proxy"] = proxy_cfg

                context = p.chromium.launch_persistent_context(**launch_args)
                page = context.pages[0] if context.pages else context.new_page()
                page.goto(target_url, timeout=45000, wait_until="domcontentloaded")
                time.sleep(3)

                if not self._is_muse_chat_ready(page) and raw_cookie:
                    parsed_cookies = self.parse_cookie_string(raw_cookie)
                    if parsed_cookies:
                        context.add_cookies(parsed_cookies)
                        page.goto(target_url, timeout=45000, wait_until="domcontentloaded")
                        time.sleep(3)

                if not self._is_muse_chat_ready(page):
                    context.close()
                    return {"status": acc.get("status", "ERROR"), "message": "Phiên đăng nhập chưa sẵn sàng để redeem mã."}

                redeem_res = self._redeem_code_in_page_sync(page, code)
                usage_info = self._extract_usage_info_sync(page)
                try:
                    cookies_json = json.dumps(context.cookies(), ensure_ascii=False)
                except Exception:
                    cookies_json = raw_cookie
                context.close()

            if usage_info and not usage_info.get("is_exhausted"):
                self.update_account(
                    account_id,
                    status="READY",
                    invite_code=code,
                    raw_cookie=cookies_json,
                    error_message=None,
                    usage_info=usage_info,
                )
                return {
                    "status": "READY",
                    "redeem": redeem_res,
                    "usage_info": usage_info,
                    "message": usage_info.get("summary") or redeem_res.get("message"),
                }

            new_status = "COOLDOWN" if (usage_info and usage_info.get("is_exhausted")) else acc.get("status", "COOLDOWN")
            msg = redeem_res.get("message") or (usage_info or {}).get("summary") or "Không thể kích hoạt bonus tokens."
            self.update_account(
                account_id,
                status=new_status,
                invite_code=code,
                raw_cookie=cookies_json,
                error_message=None if new_status == "READY" else msg,
                usage_info=usage_info or acc.get("usage_info"),
            )
            return {"status": new_status, "redeem": redeem_res, "usage_info": usage_info, "message": msg}
        except Exception as e:
            return {"status": "ERROR", "message": f"Lỗi redeem code: {e}"}
        finally:
            v_lock.release()

    def auto_login_and_verify(self, account_id: str, target_url: str = DEFAULT_MUSE_URL) -> Dict[str, Any]:
        """Tự động đăng nhập và xác thực hoàn toàn headless (có khóa per-account tránh trùng profile):
        1. Kiểm tra session persistent profile sẵn có trên muse.ai (hoặc nút Log in 1-click).
        2. Fallback: Nạp raw_cookie nếu có và kiểm tra lại composer.
        3. Fallback: Đăng nhập Passwordless Email + OTP 6 số qua TempMailClient + hoàn tất Onboarding.
        """
        v_lock = self._get_verify_lock(account_id)
        if not v_lock.acquire(blocking=False):
            return {"status": "CHECKING", "message": "Đang kiểm tra tài khoản này..."}
        try:
            acc = self.get_account(account_id)
            if not acc:
                return {"status": "ERROR", "message": "Tài khoản không tồn tại"}
            self.update_account(account_id, status="CHECKING", error_message=None)
            return self._auto_login_and_verify_impl(account_id, target_url)
        finally:
            v_lock.release()

    def _auto_login_and_verify_impl(self, account_id: str, target_url: str = DEFAULT_MUSE_URL) -> Dict[str, Any]:
        acc = self.get_account(account_id)
        if not acc:
            return {"status": "ERROR", "message": "Tài khoản không tồn tại"}

        profile_dir = self.get_profile_dir(account_id)
        proxy_cfg = self.parse_proxy(acc.get("proxy"))
        raw_cookie = acc.get("raw_cookie")
        email = acc.get("email")
        invite_code = acc.get("invite_code")

        from playwright.sync_api import sync_playwright
        try:
            with sync_playwright() as p:
                launch_args = {
                    "user_data_dir": str(profile_dir),
                    "headless": True,
                    "accept_downloads": True,
                    "args": [
                        "--no-first-run",
                        "--no-default-browser-check",
                        "--disable-blink-features=AutomationControlled"
                    ]
                }
                if proxy_cfg:
                    launch_args["proxy"] = proxy_cfg

                context = p.chromium.launch_persistent_context(**launch_args)
                page = context.pages[0] if context.pages else context.new_page()

                def _check_block() -> None:
                    """After every login state change: a challenge makes the result BLOCKED, never ERROR/READY."""
                    msg = self._detect_captcha_or_block(page)
                    if msg:
                        # Stop-all first (Enter disabled in memory, halt published under the lock), then cleanup.
                        send_halt.publish_halt(send_halt.halt_info(Exception(msg), account_id, "LOGIN"))
                        try:
                            context.close()
                        except Exception:
                            pass
                        raise _LoginBlocked(msg)

                def _save_ready(method: str, msg: str) -> Dict[str, Any]:
                    _check_block()
                    try:
                        cookies_json = json.dumps(context.cookies(), ensure_ascii=False)
                    except Exception:
                        cookies_json = raw_cookie
                    try:
                        head_txt = (page.locator("body").inner_text(timeout=2000) or "")[:4000].lower()
                    except Exception:
                        head_txt = ""
                    usage_info = self._extract_usage_info_sync(page)
                    if invite_code and (
                        not usage_info
                        or (usage_info.get("bonus_tokens_left") is None and usage_info.get("bonus_used_pct") is None)
                    ):
                        r_res = self._redeem_code_in_page_sync(page, invite_code)
                        if r_res.get("redeemed"):
                            usage_info = self._extract_usage_info_sync(page) or usage_info
                    context.close()

                    banner_exhausted = any(
                        q in head_txt for q in ("out of usage", "out of credits", "quota exceeded", "limit reached")
                    )
                    has_active_usage = bool(usage_info and not usage_info.get("is_exhausted"))
                    if (banner_exhausted and not has_active_usage) or (usage_info and usage_info.get("is_exhausted")):
                        if usage_info is None:
                            usage_info = {
                                "plan": "Muse Account",
                                "weekly_used_pct": 100.0,
                                "weekly_remaining_pct": 0.0,
                                "reset_text": None,
                                "bonus_used_pct": None,
                                "bonus_tokens_left": 0,
                                "bonus_tokens_detail": None,
                                "is_exhausted": True,
                                "summary": "Đã dùng 100% hạn mức (Out of usage)",
                                "checked_at": datetime.now().isoformat(),
                            }
                        q_msg = f"Hết hạn mức sử dụng ({usage_info['summary']})"
                        self.update_account(
                            account_id,
                            status="COOLDOWN",
                            login_method=method,
                            raw_cookie=cookies_json,
                            error_message=q_msg,
                            usage_info=usage_info,
                        )
                        return {"status": "COOLDOWN", "method": method, "message": q_msg, "usage_info": usage_info}

                    full_msg = f"{msg} — {usage_info['summary']}" if usage_info else msg
                    self.update_account(
                        account_id,
                        status="READY",
                        login_method=method,
                        raw_cookie=cookies_json,
                        error_message=None,
                        usage_info=usage_info,
                    )
                    return {"status": "READY", "method": method, "message": full_msg, "usage_info": usage_info}

                # ----------------- BƯỚC 1: KIỂM TRA SESSION SẴN CÓ -----------------
                page.goto(target_url, timeout=45000, wait_until="domcontentloaded")
                time.sleep(3)

                _check_block()

                # Kiểm tra nếu tài khoản bị waitlist / giới hạn khu vực / bị ngắt kết nối
                try:
                    body_low = (page.locator("body").inner_text(timeout=2000) or "").lower()
                    if "join the waitlist" in body_low or "isn’t available in your country" in body_low or "isn't available in your country" in body_low:
                        context.close()
                        w_msg = "Tài khoản chưa được cấp quyền truy cập (Waitlist / Region unavailable)."
                        self.update_account(account_id, status="ERROR", error_message=w_msg)
                        return {"status": "ERROR", "message": w_msg}
                    if "muse is disconnected" in body_low or "we disconnected muse" in body_low:
                        context.close()
                        d_msg = "Tài khoản bị Muse ngắt kết nối (Muse is disconnected — cần người dùng xử lý/cấp tài khoản khác)."
                        self.update_account(account_id, status="ERROR", error_message=d_msg)
                        return {"status": "ERROR", "message": d_msg}
                except Exception:
                    pass

                # Thử các nút 1-click Log in (nút trong card "Log into Muse" thường nằm sau nút Log in ở header)
                log_btns = page.locator('button:has-text("Log in")')
                b_cnt = log_btns.count()
                for idx_b in reversed(range(b_cnt)):
                    btn_b = log_btns.nth(idx_b)
                    try:
                        if btn_b.is_visible() and not btn_b.is_disabled() and not self._is_muse_chat_ready(page):
                            btn_b.click()
                            time.sleep(4)
                            if self._is_muse_chat_ready(page):
                                break
                    except Exception:
                        pass

                self._complete_onboarding_sync(page)
                _check_block()
                try:
                    body_low2 = (page.locator("body").inner_text(timeout=2000) or "").lower()
                    if "muse is disconnected" in body_low2 or "we disconnected muse" in body_low2:
                        context.close()
                        d_msg = "Tài khoản bị Muse ngắt kết nối (Muse is disconnected — cần người dùng xử lý/cấp tài khoản khác)."
                        self.update_account(account_id, status="ERROR", error_message=d_msg)
                        return {"status": "ERROR", "message": d_msg}
                except Exception:
                    pass
                if self._is_muse_chat_ready(page):
                    return _save_ready("profile", "Đã xác thực bằng session profile sẵn có (Ready)")

                # ----------------- BƯỚC 2: NẠP COOKIE -----------------
                if raw_cookie:
                    parsed_cookies = self.parse_cookie_string(raw_cookie)
                    if parsed_cookies:
                        try:
                            context.add_cookies(parsed_cookies)
                            page.goto(target_url, timeout=45000, wait_until="domcontentloaded")
                            time.sleep(3)
                            for idx_b in reversed(range(page.locator('button:has-text("Log in")').count())):
                                btn_b = page.locator('button:has-text("Log in")').nth(idx_b)
                                if btn_b.is_visible() and not btn_b.is_disabled():
                                    btn_b.click()
                                    time.sleep(4)
                                    break
                            self._complete_onboarding_sync(page)
                            _check_block()
                            if self._is_muse_chat_ready(page):
                                return _save_ready("cookie", "Đăng nhập thành công qua Cookie (Ready)")
                        except _LoginBlocked:
                            raise
                        except Exception as ce:
                            print(f"[!] Warning cookie injection {account_id}: {ce}")

                # ----------------- BƯỚC 3: PASSWORDLESS EMAIL + TEMPMAIL OTP -----------------
                if email:
                    try:
                        # Nếu đang ở màn hình 1-click card ("Use another account"), bấm nút đó để hiện form email
                        use_other = page.locator('button:has-text("Use another account")').first
                        if use_other.count() > 0 and use_other.is_visible():
                            use_other.click()
                            time.sleep(2)

                        # Đảm bảo form nhập email xuất hiện
                        email_input = page.locator('input[type="email"], input[name="email"], input[placeholder*="email" i], input').first
                        if email_input.count() == 0 or not email_input.is_visible():
                            login_trigger = page.locator('button:has-text("Log in"), button:has-text("Sign in"), a:has-text("Log in"), button:has-text("Get started")').first
                            if login_trigger.count() > 0 and login_trigger.is_visible():
                                login_trigger.click()
                                time.sleep(3)
                            email_input = page.locator('input[type="email"], input[name="email"], input[placeholder*="email" i], input').first

                        if email_input.count() > 0 and email_input.is_visible():
                            # Chụp mail_id hiện tại TRƯỚC khi bấm Continue; KHÔNG truyền invite_code của Muse làm epin tempmail
                            tempmail_epin = acc.get("tempmail_epin")
                            seen_ids = TempMailClient.snapshot_seen_ids(email, epin=tempmail_epin)
                            email_input.fill(email)
                            time.sleep(0.8)

                            btn_cont = page.locator('button:has-text("Continue"), button[type="submit"]').first
                            if btn_cont.count() > 0 and btn_cont.is_visible():
                                btn_cont.click()
                            else:
                                page.keyboard.press("Enter")
                            time.sleep(4)

                            _check_block()

                            otp_input = page.locator(
                                'input[aria-label="6-digit security code"], input[name*="code" i], input[placeholder*="code" i], input[name*="otp" i], input[type="text"]'
                            ).first
                            if otp_input.count() > 0 and otp_input.is_visible():
                                print(f"[*] Đang chờ mã OTP từ tempmail.plus cho {email}...")
                                otp_code = TempMailClient.wait_for_otp_code(
                                    email,
                                    timeout_seconds=50,
                                    check_interval=3.0,
                                    epin=tempmail_epin,
                                    initial_seen_ids=seen_ids
                                )
                                if not otp_code:
                                    raise Exception("Không nhận được mã OTP từ tempmail.plus trong 50s")

                                otp_input.fill(otp_code)
                                # Muse tự chuyển trang sau khi nhập đủ 6 số OTP; chỉ bấm Next nếu nút Next còn hiển thị và enabled
                                time.sleep(4)
                                if otp_input.count() > 0 and otp_input.is_visible():
                                    btn_next = page.locator('button:has-text("Next"), button:has-text("Verify")').first
                                    if btn_next.count() > 0 and btn_next.is_visible() and not btn_next.is_disabled():
                                        btn_next.click()
                                        time.sleep(4)
                                    else:
                                        page.keyboard.press("Enter")
                                        time.sleep(4)
                                _check_block()

                            self._complete_onboarding_sync(page)
                            _check_block()
                            if self._is_muse_chat_ready(page):
                                return _save_ready("otp", "Đăng nhập thành công qua Email + TempMail OTP")

                    except _LoginBlocked:
                        raise
                    except Exception as fe:
                        print(f"[!] Fallback OTP login error ({account_id}): {fe}")

                _check_block()
                context.close()
                err_msg = "Không thể tự động đăng nhập headless (Cookie hết hạn hoặc OTP không thành công)"
                self.update_account(account_id, status="ERROR", error_message=err_msg)
                return {"status": "ERROR", "message": err_msg}

        except _LoginBlocked as blocked:
            self.update_account(account_id, status="ERROR", error_message=str(blocked))
            return {"status": "BLOCKED", "message": str(blocked)}
        except Exception as e:
            err = f"Lỗi xác thực tài khoản: {str(e)}"
            self.update_account(account_id, status="ERROR", error_message=err)
            return {"status": "ERROR", "message": err}
