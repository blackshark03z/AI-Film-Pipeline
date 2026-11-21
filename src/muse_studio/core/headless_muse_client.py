"""
Headless Muse AI Client
Điều khiển trình duyệt Playwright hoàn toàn headless (`headless=True`, `accept_downloads=True`)
trên từng profile tài khoản để:
1. Gửi lô tối đa 4 Keyframe (`create_keyframe_handoff`) -> nhận `{batch_id}_kf_result.zip`
2. Gửi lô tối đa 6 Video Shot (`create_batch_handoff`) -> nhận `{batch_id}_result.zip`
3. Phát hiện sớm hết Quota (`QuotaExceededException`), chặn CAPTCHA/Payment (`BlockedException`),
   và chống click nhầm nút Download của batch cũ hoặc prompt người dùng.
"""

import asyncio
import json
import os
import time
import zipfile
from pathlib import Path
from typing import Any, Callable, Dict, Iterable, List, Optional, Tuple
from playwright.async_api import async_playwright, BrowserContext, Page

try:
    from . import send_halt
    from .account_manager import BLOCK_TEXT_MARKERS, CHALLENGE_PROBE_JS, AccountManager, challenge_reason
    from .batch_packager import BatchPackager, KeyframeItem, ShotItem, compute_sha256
    from .config import DEFAULT_MUSE_URL
except ImportError:
    from core import send_halt
    from core.account_manager import BLOCK_TEXT_MARKERS, CHALLENGE_PROBE_JS, AccountManager, challenge_reason
    from core.batch_packager import BatchPackager, KeyframeItem, ShotItem, compute_sha256
    from core.config import DEFAULT_MUSE_URL


def _mark_submitted(exc: BaseException) -> None:
    """Tag a failure raised after the batch was sent, so the pool never resends it in the same run."""
    try:
        setattr(exc, "submitted", True)
    except Exception:
        pass


class HeadlessMuseException(Exception):
    pass


class QuotaExceededException(HeadlessMuseException):
    pass


class SessionInvalidException(HeadlessMuseException):
    pass


class GenerationFailedException(HeadlessMuseException):
    pass


class BlockedException(HeadlessMuseException):
    """CAPTCHA, verification or unusual-activity page: ALL Muse sending stops (never a failover to another account).

    Carries the `submitted` flag like the other failures, so a block after the submit keystroke is reconciled."""


class LeaseLostException(HeadlessMuseException):
    """The account's lane lease was lost before the submit keystroke: the batch was never sent."""


class HaltedException(LeaseLostException):
    """Muse sending is halted machine-wide (a block seen anywhere, or a stop signal present): never sent."""


def trip_block(reason: str, account_id: Optional[str] = None, batch_id: Optional[str] = None) -> "BlockedException":
    """A block was just seen: stop ALL Muse sending synchronously (Enter disabled in memory, halt published under the
    halt-file lock) BEFORE any awaited cleanup, then hand back the exception to raise."""
    exc = BlockedException(reason)
    exc.account_id, exc.batch_id = account_id, batch_id
    send_halt.publish_halt(send_halt.halt_info(exc, account_id, batch_id))
    return exc


def raise_if_halted(account_id: Optional[str] = None) -> None:
    stop = send_halt.send_stop()
    if stop is not None:
        exc = HaltedException(
            f"Muse sending halted ({stop.get('signal')}: {stop.get('reason')}); not sent on {account_id}"
        )
        exc.stop = dict(stop)  # the engine adopts this record as the run's halt (never a silent NOT_SENT loss)
        raise exc


async def pre_submit_gate(page: Any, account_id: str, lease_guard: Optional[Callable[[], bool]] = None,
                          batch_id: Optional[str] = None) -> None:
    """The ONE gate right before every real submit keystroke / Generate click (headless client and web UI worker).

    1. Probe the page for a visible challenge or notice (a challenge that appeared during the upload is caught here,
       and published as a machine-wide halt before raising). A page that cannot be probed is not submitted.
    2. Synchronously from here to the keystroke: the in-memory stop and the machine-wide stop signals (read under the
       halt-file lock), then the lease. Any of them refuses: the batch was never sent.
    """
    try:
        probe = await page.evaluate(CHALLENGE_PROBE_JS)
    except Exception as exc:
        raise SessionInvalidException(f"Page probe failed before submit on {account_id}: {exc}") from exc
    reason = challenge_reason(probe)
    if reason:
        raise trip_block(reason, account_id, batch_id)
    raise_if_halted(account_id)
    if lease_guard is not None and not lease_guard():
        raise LeaseLostException(f"Lease of {account_id} lost before submit: batch not sent")


class HeadlessMuseClient:
    """Client Playwright Headless điều phối tương tác batch với Muse VM."""

    _profile_locks: Dict[str, asyncio.Lock] = {}

    QUOTA_MARKERS = (
        "out of usage",
        "quota exceeded",
        "out of credits",
        "out of credit",
        "limit reached",
        "no credits remaining",
        "insufficient credits",
        "daily limit",
        "hết lượt",
    )
    CAPTCHA_MARKERS = (
        "verify you are human",
        "hcaptcha",
        "recaptcha",
        "cf-turnstile",
    )

    BLOCK_MARKERS = BLOCK_TEXT_MARKERS

    def __init__(self, account_manager: AccountManager, muse_url: str = DEFAULT_MUSE_URL):
        self.account_manager = account_manager
        self.muse_url = muse_url
        self._keep_warm: bool = False
        self._warm_sessions: Dict[str, Tuple[Any, BrowserContext, Page]] = {}

    def enable_warm_pool(self, enabled: bool = True) -> None:
        """Bật/tắt chế độ giữ ấm phiên trình duyệt theo account_id giữa các batch liên tiếp."""
        self._keep_warm = bool(enabled)

    @property
    def warm_account_ids(self) -> set[str]:
        return {aid for aid, (_, _, page) in self._warm_sessions.items() if not page.is_closed()}

    @staticmethod
    def compute_adaptive_timeout(batch_size: int, is_video: bool = True) -> int:
        """Tính timeout thích ứng theo kích thước batch thay vì chờ cứng 240s/480s."""
        n = max(1, int(batch_size))
        if is_video:
            return max(180, min(600, 120 + n * 65))
        return max(120, min(320, 90 + n * 35))

    async def _evict_warm_session(self, account_id: str) -> None:
        """Đóng và loại bỏ phiên trình duyệt giữ ấm của một tài khoản."""
        sess = self._warm_sessions.pop(account_id, None)
        if not sess:
            return
        pw, context, _page = sess
        if context is not None:
            try:
                await context.close()
            except Exception:
                pass
        if pw is not None:
            try:
                await pw.stop()
            except Exception:
                pass

    async def close_all_sessions(self, keep_account_ids: Iterable[str] = ()) -> None:
        """Đóng các phiên Playwright nằm ngoài danh sách tài khoản tiếp tục chạy."""
        for aid in set(self._warm_sessions).difference(keep_account_ids):
            await self._evict_warm_session(aid)

    @classmethod
    def _get_lock(cls, account_id: str) -> asyncio.Lock:
        lock = cls._profile_locks.get(account_id)
        if lock is None:
            lock = asyncio.Lock()
            cls._profile_locks[account_id] = lock
        return lock

    async def _ensure_logged_in(self, account_id: str) -> Dict[str, Any]:
        acc = self.account_manager.get_account(account_id)
        if not acc:
            raise SessionInvalidException(f"Không tìm thấy tài khoản {account_id}")
        if acc.get("status") != "READY":
            await self._evict_warm_session(account_id)
            res = await asyncio.to_thread(self.account_manager.auto_login_and_verify, account_id, self.muse_url)
            if res.get("status") == "BLOCKED":
                raise trip_block(f"BLOCKED: CAPTCHA / verification page at login of {account_id}", account_id)
            if res.get("status") != "READY":
                raise SessionInvalidException(f"Tài khoản {account_id} chưa sẵn sàng: {res.get('message')}")
            acc = self.account_manager.get_account(account_id)
        return acc

    @staticmethod
    async def _is_chat_ready(page: Page) -> bool:
        try:
            body_txt = (await page.locator("body").inner_text(timeout=3000) or "").lower()
            if any(k in body_txt for k in ("what's your name", "choose your", "confirm your birthday", "enter the 6-digit")):
                return False
            box = page.locator('textarea[placeholder*="Message" i], textarea').first
            file_in = page.locator('input[type="file"]').first
            return (await box.count() > 0 and await box.is_visible()) and (await file_in.count() > 0)
        except Exception:
            return False

    @classmethod
    async def _check_page_errors(cls, page: Page, account_id: Optional[str] = None,
                                 batch_id: Optional[str] = None) -> None:
        # Only a visible challenge or a system notice blocks (never chat text, script or resource URLs). A block is
        # published machine-wide right here, before the caller's cleanup awaits anything.
        try:
            probe = await page.evaluate(CHALLENGE_PROBE_JS)
        except Exception:
            probe = None
        reason = challenge_reason(probe)
        if reason:
            raise trip_block(reason, account_id, batch_id)
        try:
            body = (await page.locator("body").inner_text(timeout=2000) or "").lower()
        except Exception:
            return
        if any(m in body for m in cls.QUOTA_MARKERS):
            raise QuotaExceededException("Tài khoản Muse đã hết quota / credits.")

    @staticmethod
    async def _start_fresh_chat(page: Page, muse_url: str) -> None:
        """Mở cuộc trò chuyện mới để lịch sử DOM không lẫn thẻ tải ZIP cũ."""
        try:
            new_chat = page.locator(
                'a:has-text("New chat"), button:has-text("New chat"), [aria-label*="New side chat" i], [aria-label*="New chat" i]'
            ).first
            if await new_chat.count() > 0 and await new_chat.is_visible():
                await new_chat.click()
                await asyncio.sleep(2)
                return
        except Exception:
            pass
        await page.goto(muse_url, timeout=45000, wait_until="domcontentloaded")
        await asyncio.sleep(3)

    @staticmethod
    async def _find_attachment_card(page: Page, expected_zip_name: str):
        """Find the returned attachment card: a `[role="button"]` element (Muse's `span.group/card`) whose text holds the
        expected zip name. Never the user's own message or plain text."""
        btn_cards = page.locator(f'[role="button"]:has-text("{expected_zip_name}")')
        cnt = await btn_cards.count()
        for i in reversed(range(cnt)):
            el = btn_cards.nth(i)
            try:
                txt = (await el.inner_text(timeout=1500) or "").strip()
                if expected_zip_name in txt and "AFP MUSE" not in txt and "The external system owns" not in txt and len(txt) <= 260:
                    return el
            except Exception:
                continue

        # No loose fallback (R15, L38): a plain span/div/a/button that merely contains the name can be the user's own
        # message or the relay text, and matching it sent a Download-less "card" 5 s after Enter. Only a real attachment
        # element (`[role="button"]`) counts; otherwise keep waiting.
        return None

    def _mark_account_exhausted(self, account_id: str, qe: BaseException) -> None:
        acc_cur = self.account_manager.get_account(account_id) or {}
        u_info = dict(acc_cur.get("usage_info") or {})
        plan_name = u_info.get("plan") or "Free plan"
        reset_txt = u_info.get("reset_text") or ""
        u_info.update({
            "plan": plan_name,
            "weekly_used_pct": 100.0,
            "weekly_remaining_pct": 0.0,
            "bonus_used_pct": 100.0 if u_info.get("bonus_used_pct") is not None or u_info.get("bonus_tokens_left") is not None else None,
            "bonus_remaining_pct": 0.0 if u_info.get("bonus_remaining_pct") is not None or u_info.get("bonus_tokens_left") is not None else None,
            "bonus_tokens_left": 0 if u_info.get("bonus_tokens_left") is not None else None,
            "is_exhausted": True,
            "summary": f"{plan_name}: Còn 0% (đã dùng 100%)" + (f" • {reset_txt}" if reset_txt else ""),
        })
        self.account_manager.update_account(
            account_id,
            status="COOLDOWN",
            error_message=str(qe),
            usage_info=u_info,
        )

    async def _dispatch_zip_and_wait_result(
        self,
        account_id: str,
        handoff_zip: Path,
        relay_message: str,
        expected_result_zip: Path,
        timeout_seconds: int = 480,
        lease_guard: Optional[Callable[[], bool]] = None,
    ) -> Path:
        """Thực thi gửi ZIP handoff qua Playwright Headless (tái sử dụng warm session nếu bật), chờ kết quả và tải về đúng file.

        `lease_guard()` is checked right before the submit keystroke (after login and upload): when it returns False
        the batch is aborted unsent with `LeaseLostException`.
        """
        raise_if_halted(account_id)  # never even log in while Muse sending is halted
        lock = self._get_lock(account_id)
        async with lock:
            raise_if_halted(account_id)
            acc = await self._ensure_logged_in(account_id)
            profile_dir = self.account_manager.get_profile_dir(account_id)
            proxy_cfg = self.account_manager.parse_proxy(acc.get("proxy"))
            expected_result_zip = Path(expected_result_zip)
            expected_result_zip.parent.mkdir(parents=True, exist_ok=True)
            expected_zip_name = expected_result_zip.name

            pw: Any = None
            context: Optional[BrowserContext] = None
            page: Optional[Page] = None
            keep_alive_on_exit = False
            submitted = False
            try:
                launch_args: Dict[str, Any] = {
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

                reused = False
                if self._keep_warm and account_id in self._warm_sessions:
                    pw, context, page = self._warm_sessions[account_id]
                    try:
                        if page is not None and not page.is_closed():
                            await self._start_fresh_chat(page, self.muse_url)
                            await self._check_page_errors(page, account_id)
                            reused = await self._is_chat_ready(page)
                    except (QuotaExceededException, BlockedException):
                        raise
                    except Exception:
                        reused = False

                    if not reused:
                        await self._evict_warm_session(account_id)
                        pw, context, page = None, None, None

                if not reused:
                    pw = await async_playwright().start()
                    context = await pw.chromium.launch_persistent_context(**launch_args)
                    if acc.get("raw_cookie"):
                        parsed = self.account_manager.parse_cookie_string(acc["raw_cookie"])
                        if parsed:
                            try:
                                await context.add_cookies(parsed)
                            except Exception:
                                pass
                    page = context.pages[0] if context.pages else await context.new_page()

                    await page.goto(self.muse_url, timeout=45000, wait_until="domcontentloaded")
                    await asyncio.sleep(2.0)
                    await self._check_page_errors(page, account_id)

                    if not await self._is_chat_ready(page):
                        await context.close()
                        context = None
                        res = await asyncio.to_thread(self.account_manager.auto_login_and_verify, account_id, self.muse_url)
                        if res.get("status") == "COOLDOWN":
                            raise QuotaExceededException(res.get("message", "Out of usage"))
                        if res.get("status") == "BLOCKED":
                            raise trip_block(f"BLOCKED: CAPTCHA / verification page at login of {account_id}",
                                             account_id)
                        if res.get("status") != "READY":
                            raise SessionInvalidException(f"Không thể đăng nhập lại {account_id}: {res.get('message')}")
                        acc = self.account_manager.get_account(account_id) or acc
                        context = await pw.chromium.launch_persistent_context(**launch_args)
                        if acc.get("raw_cookie"):
                            parsed = self.account_manager.parse_cookie_string(acc["raw_cookie"])
                            if parsed:
                                try:
                                    await context.add_cookies(parsed)
                                except Exception:
                                    pass
                        page = context.pages[0] if context.pages else await context.new_page()
                        await page.goto(self.muse_url, timeout=45000, wait_until="domcontentloaded")
                        await asyncio.sleep(2.0)

                    await self._start_fresh_chat(page, self.muse_url)
                    await self._check_page_errors(page, account_id)

                    if not await self._is_chat_ready(page):
                        raise SessionInvalidException(f"Không thấy ô chat/upload trên tài khoản {account_id}")

                assert page is not None
                # 1. Đính kèm file handoff ZIP
                file_input = page.locator('input[type="file"]').first
                await file_input.set_input_files(str(handoff_zip.resolve()))
                await asyncio.sleep(2.0)

                # 2. Nhập relay message & gửi
                box = page.locator('textarea[placeholder*="Message" i], textarea').first
                await box.click()
                await box.fill(relay_message)
                await asyncio.sleep(0.8)
                # The one pre-Enter gate: page challenge, machine-wide halt, lease. Nothing awaits between its
                # synchronous checks and the keystroke.
                await pre_submit_gate(page, account_id, lease_guard)
                # From here on the batch may be rendering on Muse (and spending credits): any later failure is
                # tagged `submitted` so the pool reconciles instead of resending.
                submitted = True
                await page.keyboard.press("Enter")

                # 3. Chờ thẻ result.zip xuất hiện
                start_t = time.time()
                found_card = None
                while time.time() - start_t < timeout_seconds:
                    await self._check_page_errors(page, account_id)
                    card = await self._find_attachment_card(page, expected_zip_name)
                    if card is not None:
                        found_card = card
                        break
                    await asyncio.sleep(2.5)

                if found_card is None:
                    raise GenerationFailedException(
                        f"Timeout {timeout_seconds}s không thấy {expected_zip_name} trên tài khoản {account_id}"
                    )

                # 4. Cuộn & bấm thẻ để mở nút Download, sau đó tải về chính xác
                await page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
                await asyncio.sleep(0.8)
                await found_card.scroll_into_view_if_needed()
                await page.evaluate("window.scrollBy(0, -150)")
                await asyncio.sleep(0.8)

                try:
                    await found_card.click(force=True, timeout=5000)
                except Exception:
                    await found_card.dispatch_event("click")
                await asyncio.sleep(1.5)

                dl_btn = page.get_by_role("button", name="Download", exact=True)
                if await dl_btn.count() == 0:
                    dl_btn = page.locator('button:has-text("Download"), a:has-text("Download")')
                if await dl_btn.count() == 0:
                    dl_btn = page.locator('[aria-label*="download" i], [title*="download" i]')

                if await dl_btn.count() == 0:
                    raise GenerationFailedException(f"Tìm thấy thẻ {expected_zip_name} nhưng không thấy nút Download")

                async with page.expect_download(timeout=90000) as download_info:
                    await dl_btn.first.click(force=True)
                download = await download_info.value
                await download.save_as(str(expected_result_zip))

                if not expected_result_zip.exists() or not zipfile.is_zipfile(expected_result_zip):
                    raise GenerationFailedException(f"File tải về {expected_result_zip} bị rỗng hoặc không phải ZIP hợp lệ")

                try:
                    # Best-effort: the result is already on disk, a bookkeeping error must not discard it.
                    self.account_manager.update_account(
                        account_id,
                        status="READY",
                        error_message=None,
                        last_used=time.strftime("%Y-%m-%d %H:%M:%S")
                    )
                except Exception:
                    pass
                if self._keep_warm and context is not None and page is not None and not page.is_closed():
                    self._warm_sessions[account_id] = (pw, context, page)
                    keep_alive_on_exit = True
                return expected_result_zip

            except QuotaExceededException as qe:
                if submitted:
                    _mark_submitted(qe)
                # Bookkeeping is best-effort: a failure here must never replace the original exception (and its
                # `submitted` flag), or the pool would resend a batch that already reached Muse.
                try:
                    self._mark_account_exhausted(account_id, qe)
                except Exception:
                    pass
                raise
            except SessionInvalidException as se:
                if submitted:
                    _mark_submitted(se)
                try:
                    self.account_manager.update_account(account_id, status="ERROR", error_message=str(se))
                except Exception:
                    pass
                raise
            except BaseException as exc:
                if submitted:
                    _mark_submitted(exc)
                raise
            finally:
                if not keep_alive_on_exit:
                    self._warm_sessions.pop(account_id, None)
                    if context is not None:
                        try:
                            await context.close()
                        except Exception:
                            pass
                    if pw is not None:
                        try:
                            await pw.stop()
                        except Exception:
                            pass

    async def generate_keyframes_batch(
        self,
        account_id: str,
        keyframes: List[KeyframeItem],
        batch_id: str,
        output_dir: Path,
        timeout_seconds: Optional[int] = None,
        simulate: bool = False,
        lease_guard: Optional[Callable[[], bool]] = None,
    ) -> Dict[str, Any]:
        """Sinh tối đa 4 keyframe 16:9 trên Muse VM, tải và giải nén đối soát."""
        eff_timeout = (
            int(timeout_seconds)
            if timeout_seconds is not None
            else self.compute_adaptive_timeout(len(keyframes), is_video=False)
        )
        output_dir = Path(output_dir)
        handoff_zip, relay_msg = BatchPackager.create_keyframe_handoff(batch_id, keyframes, output_dir)
        result_zip = output_dir / f"{batch_id}_kf_result.zip"
        extract_dir = output_dir / "keyframes"

        dry = simulate or os.environ.get("MUSE_SIMULATE") == "1"
        if dry:
            self._simulate_keyframe_zip(keyframes, result_zip)
        else:
            await self._dispatch_zip_and_wait_result(
                account_id=account_id,
                handoff_zip=handoff_zip,
                relay_message=relay_msg,
                expected_result_zip=result_zip,
                timeout_seconds=eff_timeout,
                lease_guard=lease_guard,
            )

        try:
            unpacked = BatchPackager.unpack_keyframe_result(
                result_zip,
                extract_dir,
                expected_kf_ids=[k.kf_id for k in keyframes],
                handoff_manifest_path=output_dir / f"{batch_id}_kf_manifest.json",
            )
        except BaseException as exc:
            # The batch already reached Muse: a local post-processing failure must never cause a resend.
            if not dry:
                _mark_submitted(exc)
            raise
        unpacked["batch_id"] = batch_id
        unpacked["handoff_zip"] = str(handoff_zip)
        return unpacked

    async def generate_videos_batch(
        self,
        account_id: str,
        shots: List[ShotItem],
        batch_id: str,
        output_dir: Path,
        timeout_seconds: Optional[int] = None,
        simulate: bool = False,
        lease_guard: Optional[Callable[[], bool]] = None,
    ) -> Dict[str, Any]:
        """Sinh tối đa 6 video shot trên Muse VM, tải và đối soát chặt chẽ với manifest."""
        eff_timeout = (
            int(timeout_seconds)
            if timeout_seconds is not None
            else self.compute_adaptive_timeout(len(shots), is_video=True)
        )
        output_dir = Path(output_dir)
        handoff_zip, relay_msg = BatchPackager.create_batch_handoff(batch_id, shots, output_dir)
        result_zip = output_dir / f"{batch_id}_result.zip"
        extract_dir = output_dir / "verified_clips"

        dry = simulate or os.environ.get("MUSE_SIMULATE") == "1"
        if dry:
            self._simulate_video_zip(shots, batch_id, result_zip)
        else:
            await self._dispatch_zip_and_wait_result(
                account_id=account_id,
                handoff_zip=handoff_zip,
                relay_message=relay_msg,
                expected_result_zip=result_zip,
                timeout_seconds=eff_timeout,
                lease_guard=lease_guard,
            )

        try:
            unpacked = BatchPackager.unpack_batch_result(
                result_zip,
                extract_dir,
                handoff_manifest_path=output_dir / f"{batch_id}_manifest.json",
                strict_min_bytes=1024 if dry else None,
            )
        except BaseException as exc:
            # The batch already reached Muse: a local post-processing failure must never cause a resend.
            if not dry:
                _mark_submitted(exc)
            raise
        verified_count = len(unpacked.get("verified_shots", {}))
        if verified_count > 0 and not dry:
            # Dry runs never write accounts.json. A failed usage-counter write never discards verified clips.
            try:
                # Atomic increment under the accounts lock (a read-then-update here lost concurrent increments).
                self.account_manager.increment_account(account_id, "total_rendered", verified_count)
            except Exception:
                pass
        unpacked["batch_id"] = batch_id
        unpacked["handoff_zip"] = str(handoff_zip)
        return unpacked

    @staticmethod
    def _simulate_keyframe_zip(keyframes: List[KeyframeItem], result_zip: Path) -> None:
        from PIL import Image, ImageDraw
        import io as _io
        import numpy as _np
        receipt_items = []
        with zipfile.ZipFile(result_zip, "w", zipfile.ZIP_DEFLATED) as zf:
            for kf in keyframes:
                # Tạo ảnh textured 1280x720 > 20KB thực tế
                rng = _np.random.default_rng(int(compute_sha256(kf.kf_id.encode())[:16], 16))
                noise = rng.integers(25, 65, size=(720, 1280, 3), dtype=_np.uint8)
                img = Image.fromarray(noise, mode="RGB")
                d = ImageDraw.Draw(img)
                d.rectangle([120, 140, 520, 620], fill=(90, 120, 155))
                d.rectangle([760, 140, 1160, 620], fill=(130, 95, 110))
                buf = _io.BytesIO()
                img.save(buf, format="PNG")
                raw = buf.getvalue()
                zf.writestr(f"{kf.kf_id}.png", raw)
                receipt_items.append({"kf_id": kf.kf_id, "output_file": f"{kf.kf_id}.png", "sha256": compute_sha256(raw)})
            zf.writestr("kf_receipt.json", json.dumps({"keyframes": receipt_items}, indent=2))

    @staticmethod
    def _simulate_video_zip(shots: List[ShotItem], batch_id: str, result_zip: Path) -> None:
        try:
            from .video_processor import VideoProcessor
        except ImportError:
            from core.video_processor import VideoProcessor
        import tempfile
        with tempfile.TemporaryDirectory() as td:
            tdp = Path(td)
            receipt_shots = []
            with zipfile.ZipFile(result_zip, "w", zipfile.ZIP_DEFLATED) as zf:
                for idx, sh in enumerate(shots, start=1):
                    slot_id = f"shot_{idx:02d}"
                    mp4_p = tdp / f"{slot_id}.mp4"
                    VideoProcessor.create_synthetic_test_clip(mp4_p, duration_s=min(4.0, sh.duration_s), text=sh.shot_id)
                    raw = mp4_p.read_bytes()
                    zf.writestr(f"{slot_id}.mp4", raw)
                    receipt_shots.append({
                        "slot_id": slot_id,
                        "shot_id": sh.shot_id,
                        "output_file": f"{slot_id}.mp4",
                        "bytes": len(raw),
                        "sha256": compute_sha256(raw),
                        "status": "ok",
                    })
                zf.writestr("batch_receipt.json", json.dumps({"batch_id": batch_id, "shots": receipt_shots, "failed_shots": []}, indent=2))
