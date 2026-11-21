import asyncio
import re
import time
import urllib.request
import json
from pathlib import Path
from playwright.async_api import async_playwright

async def do_login():
    pw = await async_playwright().start()
    profile_dir = Path(r"D:\Muse\muse_studio\data\profiles\acc_d5b0c7e2")
    context = await pw.chromium.launch_persistent_context(
        user_data_dir=str(profile_dir),
        headless=True,
        args=["--no-first-run", "--no-default-browser-check"]
    )
    page = context.pages[0] if context.pages else await context.new_page()
    
    print("[*] Truy cập https://muse.ai...")
    await page.goto("https://muse.ai", timeout=45000, wait_until="networkidle")
    
    print("[*] Điền email magjh64ylv@merepost.com...")
    inp = page.locator("input").first
    await inp.fill("magjh64ylv@merepost.com")
    await asyncio.sleep(1)
    
    btn_cont = page.locator("button").filter(has_text="Continue").first
    await btn_cont.click()
    print("[*] Đã bấm Continue, chờ giao diện nhập code...")
    await asyncio.sleep(4)
    
    # Polling tempmail API
    print("[*] Đang chờ mã OTP từ tempmail.plus...")
    otp_code = None
    start_t = time.time()
    
    # Ghi nhận mail_id ban đầu để tìm mail mới
    init_mail_id = None
    try:
        req = urllib.request.Request(
            "https://tempmail.plus/api/mails?email=magjh64ylv@merepost.com&limit=1",
            headers={"User-Agent": "Mozilla/5.0"}
        )
        with urllib.request.urlopen(req) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            if data.get("mail_list"):
                init_mail_id = data["mail_list"][0].get("mail_id")
    except Exception:
        pass

    while time.time() - start_t < 45:
        try:
            req = urllib.request.Request(
                "https://tempmail.plus/api/mails?email=magjh64ylv@merepost.com&limit=5",
                headers={"User-Agent": "Mozilla/5.0"}
            )
            with urllib.request.urlopen(req) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                mails = data.get("mail_list", [])
                for m_item in mails:
                    subj = m_item.get("subject", "")
                    m = re.search(r"(\d{6})", subj)
                    if m:
                        otp_code = m.group(1)
                        print(f"[+] Bắt được mã OTP: {otp_code} (Subject: {subj})")
                        break
                if otp_code:
                    break
        except Exception:
            pass
        await asyncio.sleep(2)
        
    if not otp_code:
        print("[-] Không lấy được mã OTP!")
        await context.close()
        await pw.stop()
        return
        
    # Điền OTP
    code_input = page.locator('input[type="text"]').first
    await code_input.fill(otp_code)
    await asyncio.sleep(1)
    
    btn_next = page.locator("button").filter(has_text="Next").first
    if await btn_next.count() > 0:
        await btn_next.click()
    else:
        await page.keyboard.press("Enter")
        
    print("[*] Đã gửi mã OTP, đợi chuyển hướng vào Muse...")
    await asyncio.sleep(10)
    
    print("[+] URL sau khi đăng nhập:", page.url)
    print("[+] Tiêu đề:", await page.title())
    
    ss_path = Path(r"D:\Muse\muse_studio\data\profiles\acc_d5b0c7e2\login_success.png")
    await page.screenshot(path=str(ss_path))
    print("[+] Đã lưu screenshot tại:", ss_path)
    
    await context.close()
    await pw.stop()

if __name__ == "__main__":
    asyncio.run(do_login())
