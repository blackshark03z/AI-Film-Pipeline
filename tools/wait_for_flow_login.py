import argparse
import asyncio
import json
import os
import sys
import time
from pathlib import Path
from typing import Any, Dict, List

if sys.stdout and hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if sys.stderr and hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

try:
    from patchright.async_api import async_playwright
except ImportError:
    from playwright.async_api import async_playwright


def is_login_success(url: str, cookies: List[Dict[str, Any]]) -> bool:
    if not url:
        return False
    url_lower = url.lower()
    if "accounts.google.com" in url_lower:
        return False
    if "/about" in url_lower:
        return False
    if "accountchooser" in url_lower:
        return False
    if "/signin" in url_lower:
        return False
    if "/login" in url_lower:
        return False
    if "flow.google.com" not in url_lower:
        return False

    now = time.time()
    essential = {"SID", "HSID", "__Secure-1PSID", "__Secure-3PSID"}
    found_tokens = {}
    for c in cookies:
        name = c.get("name", "")
        if name in essential:
            exp = c.get("expires", 0)
            is_valid = (exp <= 0 or exp > now)
            found_tokens[name] = is_valid

    if "SID" not in found_tokens or not found_tokens["SID"]:
        return False

    return True


def export_cookies_atomically(cookies: List[Dict[str, Any]], output_path: Path) -> bool:
    try:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        tmp_out = output_path.with_suffix(f".tmp.{os.getpid()}_{int(time.time() * 1000)}")
        with open(tmp_out, "w", encoding="utf-8") as cf:
            json.dump(cookies, cf, indent=2)
        os.replace(tmp_out, output_path)
        print(f"[XÁC NHẬN] Đã tự động xuất {len(cookies)} cookies vào:\n  -> {output_path}", flush=True)
        return True
    except Exception as ce:
        print(f"[CẢNH BÁO] Không thể xuất cookie vào {output_path}: {ce}", flush=True)
        return False


async def main():
    parser = argparse.ArgumentParser(description="Google Flow Login & Cookie Exporter")
    parser.add_argument("--profile-dir", default=r"D:\AI FILM MAKER\Flow-Claude-Clean-Profile", help="Chrome user data dir")
    parser.add_argument("--timeout-sec", type=int, default=900, help="Timeout in seconds")
    args = parser.parse_args()

    profile_dir = Path(args.profile_dir)
    profile_dir.mkdir(parents=True, exist_ok=True)

    output_targets = [
        Path(r"D:\AI FILM MAKER\AI-Film-Pipeline-Claude-Forensics\api_keys\google_flow_cookie.json"),
        Path(r"D:\AI FILM MAKER\AI-Film-Pipeline\api_keys\google_flow_cookie.json"),
        Path(r"D:\AI FILM MAKER\Flow-Claude-Forensics-Evidence\google_flow_cookie.json"),
    ]

    print("=" * 65, flush=True)
    print("  AI-FILM-PIPELINE: GOOGLE FLOW LOGIN & TỰ ĐỘNG LƯU COOKIE", flush=True)
    print(f"  Profile: {profile_dir}", flush=True)
    print("=" * 65, flush=True)
    print(">> Đang mở Google Chrome...", flush=True)

    async with async_playwright() as p:
        context = await p.chromium.launch_persistent_context(
            str(profile_dir),
            channel="chrome",
            headless=False,
            args=[
                "--no-first-run",
                "--no-default-browser-check",
                "--disable-blink-features=AutomationControlled",
                "--start-maximized",
            ],
            ignore_default_args=["--enable-automation"],
            viewport=None,
        )
        page = context.pages[0] if context.pages else await context.new_page()

        login_url = "https://accounts.google.com/AccountChooser?continue=https%3A%2F%2Fflow.google.com%2F"
        print(f">> Điều hướng tới trang đăng nhập Google Flow...", flush=True)
        try:
            await page.goto(login_url, timeout=35000, wait_until="domcontentloaded")
        except Exception as e:
            print(f">> Ghi chú điều hướng: {e}", flush=True)

        print("\n" + "=" * 65, flush=True)
        print(">> CỬA SỔ CHROME ĐÃ MỞ TRÊN MÀN HÌNH!", flush=True)
        print(">> Bạn hãy đăng nhập tài khoản Google trên trình duyệt.", flush=True)
        print(">> Sau khi vào Google Flow, hệ thống sẽ TỰ ĐỘNG lưu cookie.", flush=True)
        print("=" * 65 + "\n", flush=True)

        poll_interval = 3
        max_loops = max(1, args.timeout_sec // poll_interval)

        for _ in range(max_loops):
            await asyncio.sleep(poll_interval)
            if page.is_closed():
                print("[THÔNG BÁO] Cửa sổ trình duyệt đã được đóng.", flush=True)
                await context.close()
                return

            try:
                url = page.url
                cookies = await context.cookies()
            except Exception:
                break

            now = time.time()
            has_sid = any(c.get("name") == "SID" and (c.get("expires", 0) <= 0 or c.get("expires", 0) > now) for c in cookies)

            if has_sid and "flow.google.com" in url.lower():
                if "/about" in url.lower():
                    try:
                        await page.goto("https://flow.google.com/", timeout=15000, wait_until="domcontentloaded")
                        await asyncio.sleep(2)
                        url = page.url
                        cookies = await context.cookies()
                    except Exception:
                        pass

            if is_login_success(url, cookies):
                print("\n" + "=" * 65, flush=True)
                print(f"[XÁC NHẬN] ĐĂNG NHẬP THÀNH CÔNG! URL: {url}", flush=True)
                print(">> Đang tự động lưu cookie...", flush=True)
                saved_any = False
                for target in output_targets:
                    if export_cookies_atomically(cookies, target):
                        saved_any = True
                print("=" * 65, flush=True)
                if saved_any:
                    print("[HOÀN TẤT] Cookie đã được lưu thành công!", flush=True)
                await asyncio.sleep(2)
                await context.close()
                return

        print("[CẢNH BÁO] Quá thời gian chờ đăng nhập (timeout).", flush=True)
        await context.close()


if __name__ == "__main__":
    asyncio.run(main())
