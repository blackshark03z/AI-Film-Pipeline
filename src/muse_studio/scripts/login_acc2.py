import asyncio
import re
import time
import urllib.request
import json
from pathlib import Path
from playwright.async_api import async_playwright

async def login_acc2():
    pw = await async_playwright().start()
    profile_dir = Path(r"D:\Muse\muse_studio\data\profiles\acc_63746e8e")
    context = await pw.chromium.launch_persistent_context(
        user_data_dir=str(profile_dir),
        headless=True,
        args=["--no-first-run", "--no-default-browser-check"]
    )
    page = context.pages[0] if context.pages else await context.new_page()
    
    print("[*] Truy cập https://muse.ai...")
    await page.goto("https://muse.ai", timeout=45000, wait_until="domcontentloaded")
    await asyncio.sleep(3)
    
    title = await page.title()
    if "chat" in title.lower():
        print("[+] Đã đăng nhập sẵn!")
        await context.close()
        await pw.stop()
        return
        
    print("[*] Điền email ywddiv6cxm@merepost.com...")
    inp = page.locator("input").first
    await inp.fill("ywddiv6cxm@merepost.com")
    await asyncio.sleep(1)
    
    btn_cont = page.locator("button").filter(has_text="Continue").first
    await btn_cont.click()
    print("[*] Đã bấm Continue, chờ giao diện nhập code...")
    await asyncio.sleep(4)
    
    print("[*] Đang chờ mã OTP từ tempmail.plus...")
    otp_code = None
    start_t = time.time()
    while time.time() - start_t < 45:
        try:
            req = urllib.request.Request(
                "https://tempmail.plus/api/mails?email=ywddiv6cxm@merepost.com&limit=5",
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
    
    ss_path = Path(r"D:\Muse\muse_studio\data\profiles\acc_63746e8e\login_success.png")
    await page.screenshot(path=str(ss_path))
    print("[+] Đã lưu screenshot tại:", ss_path)
    
    await context.close()
    await pw.stop()

if __name__ == "__main__":
    asyncio.run(login_acc2())
