import asyncio
from pathlib import Path
from playwright.async_api import async_playwright

async def finish_onboarding(acc_id):
    pw = await async_playwright().start()
    profile_dir = Path(rf"D:\Muse\muse_studio\data\profiles\{acc_id}")
    context = await pw.chromium.launch_persistent_context(
        user_data_dir=str(profile_dir),
        headless=True,
        args=["--no-first-run", "--no-default-browser-check"]
    )
    page = context.pages[0] if context.pages else await context.new_page()
    await page.goto("https://muse.ai", timeout=45000, wait_until="domcontentloaded")
    await asyncio.sleep(4)
    
    # 1. Nếu có câu hỏi tên
    chat_box = page.locator('textarea, input[placeholder*="Message" i], [contenteditable="true"]').first
    body_text = await page.locator("body").inner_text()
    if "what's your name" in body_text.lower():
        if await chat_box.count() > 0:
            await chat_box.click()
            await chat_box.fill("Director")
            await asyncio.sleep(1)
            await page.keyboard.press("Enter")
            await asyncio.sleep(4)
            
    # 2. Nếu có nút chọn tên bot: Pax, Alder, Muse
    muse_btn = page.locator('button:has-text("Muse"), [role="button"]:has-text("Muse")').first
    if await muse_btn.count() > 0:
        await muse_btn.click()
        print(f"[+] [{acc_id}] Đã bấm chọn tên 'Muse'!")
        await asyncio.sleep(4)
        
    print(f"[+] [{acc_id}] Onboarding hoàn tất!")
    await context.close()
    await pw.stop()

async def main():
    print("[*] Hoàn tất onboarding tài khoản 1 (magjh64ylv)...")
    await finish_onboarding("acc_d5b0c7e2")
    print("[*] Hoàn tất onboarding tài khoản 2 (ywddiv6cxm)...")
    await finish_onboarding("acc_63746e8e")

if __name__ == "__main__":
    asyncio.run(main())
