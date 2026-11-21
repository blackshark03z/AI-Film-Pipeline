import asyncio
import os
import time
import urllib.request
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional
from playwright.async_api import async_playwright, BrowserContext, Page

try:
    from .account_manager import AccountManager
    from .config import DEFAULT_MUSE_URL
    from .headless_muse_client import (
        BlockedException, HaltedException, HeadlessMuseClient, pre_submit_gate, raise_if_halted,
    )
except ImportError:
    from core.account_manager import AccountManager
    from core.config import DEFAULT_MUSE_URL
    from core.headless_muse_client import (
        BlockedException, HaltedException, HeadlessMuseClient, pre_submit_gate, raise_if_halted,
    )

WEBUI_BATCH_ID = "WEBUI"

class MuseWorkerException(Exception):
    pass

class QuotaExceededException(MuseWorkerException):
    pass

class GenerationFailedException(MuseWorkerException):
    pass

class MuseBrowserWorker:
    """Điều khiển tự động hóa Playwright cho một tài khoản cụ thể trong pool."""
    def __init__(self, account_id: str, account_manager: AccountManager):
        self.account_id = account_id
        self.account_manager = account_manager
        self.account_data = self.account_manager.get_account(account_id)
        if not self.account_data:
            raise ValueError(f"Account {account_id} not found")
        
        self.profile_dir = self.account_manager.get_profile_dir(account_id)
        self.proxy_cfg = self.account_manager.parse_proxy(self.account_data.get("proxy"))
        self.context: Optional[BrowserContext] = None
        self.page: Optional[Page] = None
        self._pw = None
        # True from the Generate click on: a failure after it may have reached Muse (never retried blindly).
        self.submitted = False

    async def start(self, headless: bool = True):
        """Khởi động Playwright persistent context."""
        if self.context:
            return
        
        self._pw = await async_playwright().start()
        launch_args = {
            "user_data_dir": str(self.profile_dir),
            "headless": headless,
            "args": [
                "--no-first-run",
                "--no-default-browser-check",
                "--disable-blink-features=AutomationControlled"
            ]
        }
        if self.proxy_cfg:
            launch_args["proxy"] = self.proxy_cfg

        self.context = await self._pw.chromium.launch_persistent_context(**launch_args)
        self.page = self.context.pages[0] if self.context.pages else await self.context.new_page()

    async def close(self):
        """Đóng context và giải phóng tài nguyên."""
        if self.context:
            try:
                await self.context.close()
            except Exception:
                pass
            self.context = None
            self.page = None
        if self._pw:
            try:
                await self._pw.stop()
            except Exception:
                pass
            self._pw = None

    async def generate_shot(
        self,
        prompt: str,
        reference_images: List[str],
        output_clip_path: Path,
        dialogue: Optional[str] = None,
        progress_callback: Optional[Callable[[int, str], None]] = None,
        timeout_seconds: int = 300,
        simulate: bool = False
    ) -> Dict[str, Any]:
        """Thực hiện một chu trình tạo video hoàn chỉnh: Nạp ref -> Prompt -> Bấm render -> Tải MP4."""
        output_clip_path = Path(output_clip_path)
        output_clip_path.parent.mkdir(parents=True, exist_ok=True)

        if progress_callback:
            progress_callback(5, "Đang chuẩn bị môi trường trình duyệt...")

        # Chế độ giả lập phục vụ kiểm thử hệ thống
        if simulate or os.environ.get("MUSE_SIMULATE") == "1":
            return await self._simulate_generation(output_clip_path, progress_callback)

        self.submitted = False
        raise_if_halted(self.account_id)  # Muse sending halted machine-wide: do not even open the browser
        await self.start(headless=True)
        assert self.page is not None

        try:
            if progress_callback:
                progress_callback(10, "Đang truy cập Muse...")

            await self.page.goto(DEFAULT_MUSE_URL, timeout=45000, wait_until="domcontentloaded")
            await asyncio.sleep(2)
            await HeadlessMuseClient._check_page_errors(self.page, self.account_id, WEBUI_BATCH_ID)

            # 1. Kiểm tra trạng thái đăng nhập
            cookies = await self.context.cookies()
            if not cookies:
                raise GenerationFailedException("Tài khoản chưa đăng nhập vào Muse. Vui lòng mở trình duyệt đăng nhập trước.")

            if progress_callback:
                progress_callback(20, "Đang tải ảnh tham chiếu...")

            # 2. Nạp ảnh tham chiếu (tối đa 9 ảnh)
            valid_refs = [str(Path(r).resolve()) for r in reference_images if Path(r).exists()]
            if valid_refs:
                file_inputs = self.page.locator('input[type="file"]')
                if await file_inputs.count() > 0:
                    try:
                        # Gán file vào input
                        await file_inputs.first.set_input_files(valid_refs[:9])
                        await asyncio.sleep(2)
                    except Exception as e:
                        print(f"[!] Warning khi upload refs: {e}")

            # 3. Điền prompt
            full_prompt = prompt.strip()
            if dialogue:
                full_prompt += f' The character says: "{dialogue.strip()}"'
            if "aspect ratio" not in full_prompt.lower():
                full_prompt += " in exactly 16:9 aspect ratio"

            if progress_callback:
                progress_callback(35, "Đang nhập prompt và thiết lập thông số...")

            prompt_box = self.page.locator('textarea, [contenteditable="true"], #prompt-textarea, input[placeholder*="prompt" i]').first
            if await prompt_box.count() > 0:
                await prompt_box.click()
                await prompt_box.fill(full_prompt)
            else:
                # Thử gửi phím hoặc evaluate
                await self.page.keyboard.type(full_prompt)

            await asyncio.sleep(1)

            # 4. Kiểm tra Quota trước khi bấm nút
            page_text = (await self.page.content()).lower()
            if any(w in page_text for w in ["limit reached", "out of credit", "hết lượt", "no credits remaining"]):
                raise QuotaExceededException("Tài khoản đã hết hạn mức (Quota Exceeded)")

            # 5. Bấm nút Generate
            if progress_callback:
                progress_callback(50, "Đang kích hoạt tiến trình render...")

            generate_btn = self.page.locator('button:has-text("Generate"), button:has-text("Tạo"), button:has-text("Create"), button[type="submit"]').first
            has_btn = await generate_btn.count() > 0
            # The one pre-submit gate (same as the headless client): page challenge, machine-wide halt.
            await pre_submit_gate(self.page, self.account_id, None, WEBUI_BATCH_ID)
            self.submitted = True
            if has_btn:
                await generate_btn.click()
            else:
                await self.page.keyboard.press("Enter")

            # 6. Polling theo dõi video render hoàn tất
            start_time = time.time()
            video_url = None
            last_pct = 50

            while time.time() - start_time < timeout_seconds:
                elapsed = int(time.time() - start_time)
                # Tăng dần phần trăm hiển thị giao diện từ 50% đến 95%
                calc_pct = min(95, 50 + int((elapsed / 90.0) * 45))
                if calc_pct > last_pct:
                    last_pct = calc_pct
                    if progress_callback:
                        progress_callback(last_pct, f"Đang render video trên Muse ({elapsed}s)...")

                # Kiểm tra lỗi phát sinh trong lúc render
                await HeadlessMuseClient._check_page_errors(self.page, self.account_id, WEBUI_BATCH_ID)
                current_text = (await self.page.content()).lower()
                if "quota exceeded" in current_text or "out of credits" in current_text:
                    raise QuotaExceededException("Tài khoản bị ngắt do hết hạn mức quota trong lúc render")
                if "service restarted" in current_text or "error generating" in current_text:
                    raise GenerationFailedException("Lỗi hệ thống từ Muse (Service Error/Restarted)")

                # Tìm thẻ video hoặc link tải
                video_elements = self.page.locator('video[src], a[download][href*=".mp4"], video source[src]')
                if await video_elements.count() > 0:
                    for i in range(await video_elements.count()):
                        elem = video_elements.nth(i)
                        src = await elem.get_attribute("src") or await elem.get_attribute("href")
                        if src and (".mp4" in src or "blob:" in src or "http" in src):
                            video_url = src
                            break
                    if video_url:
                        break

                await asyncio.sleep(4)

            if not video_url:
                raise GenerationFailedException("Timeout: Không phát hiện video hoàn tất sau thời gian chờ")

            # 7. Tải video về thư mục đích
            if progress_callback:
                progress_callback(96, "Đang tải file video về máy...")

            if video_url.startswith("http"):
                urllib.request.urlretrieve(video_url, str(output_clip_path))
            else:
                # Nếu là blob, dùng page evaluate để kéo buffer về
                js_download = """async (url) => {
                    const r = await fetch(url);
                    const b = await r.blob();
                    const buf = new Uint8Array(await b.arrayBuffer());
                    let s = '';
                    for (let i = 0; i < buf.length; i += 0x8000) {
                        s += String.fromCharCode.apply(null, buf.subarray(i, i + 0x8000));
                    }
                    return btoa(s);
                }"""
                b64 = await self.page.evaluate(js_download, video_url)
                import base64
                output_clip_path.write_bytes(base64.b64decode(b64))

            if progress_callback:
                progress_callback(100, "Hoàn tất render cảnh!")

            # Cập nhật thống kê tài khoản
            self._record_render()

            return {
                "success": True,
                "output_path": str(output_clip_path),
                "account_id": self.account_id,
                "duration_seconds": time.time() - start_time
            }

        except QuotaExceededException as qe:
            self.account_manager.update_account(self.account_id, status="COOLDOWN", error_message=str(qe))
            raise
        except BlockedException as be:
            # Already published machine-wide by the detector; take the account out, never retry.
            self.account_manager.update_account(self.account_id, status="ERROR", error_message=f"BLOCKED: {be}"[:300])
            raise
        except HaltedException:
            raise
        except Exception as e:
            err_msg = str(e)
            self.account_manager.update_account(self.account_id, error_message=err_msg)
            gf = GenerationFailedException(err_msg)
            gf.submitted = self.submitted
            raise gf
        finally:
            await self.close()

    def _record_render(self) -> None:
        """Count one finished render. The counter goes through the atomic `increment_account` (a read-then-write of
        `total_rendered` here would lose a concurrent increment); `last_used` is a plain overwrite."""
        self.account_manager.increment_account(self.account_id, "total_rendered", 1)
        self.account_manager.update_account(self.account_id, last_used=time.strftime("%Y-%m-%d %H:%M:%S"))

    async def _simulate_generation(self, output_clip_path: Path, progress_callback: Optional[Callable[[int, str], None]]) -> Dict[str, Any]:
        """Tạo clip mô phỏng nhanh trong 3 giây cho testing."""
        try:
            from .video_processor import VideoProcessor
        except ImportError:
            from core.video_processor import VideoProcessor
        for step in [20, 50, 80, 95]:
            await asyncio.sleep(0.5)
            if progress_callback:
                progress_callback(step, f"[MÔ PHỎNG] Đang xử lý render ({step}%)...")

        VideoProcessor.create_synthetic_test_clip(output_clip_path, duration_s=3.0, text=output_clip_path.stem)
        if progress_callback:
            progress_callback(100, "[MÔ PHỎNG] Đã render xong clip test!")

        self._record_render()
        return {
            "success": True,
            "output_path": str(output_clip_path),
            "account_id": self.account_id,
            "duration_seconds": 2.0,
            "simulated": True
        }
