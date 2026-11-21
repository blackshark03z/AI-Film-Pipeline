import asyncio
from pathlib import Path
from playwright.async_api import async_playwright

async def test_interaction():
    pw = await async_playwright().start()
    profile_dir = Path(r"D:\Muse\muse_studio\data\profiles\acc_d5b0c7e2")
    context = await pw.chromium.launch_persistent_context(
        user_data_dir=str(profile_dir),
        headless=True,
        args=["--no-first-run", "--no-default-browser-check"]
    )
    page = context.pages[0] if context.pages else await context.new_page()
    await page.goto("https://muse.ai", timeout=45000, wait_until="domcontentloaded")
    await asyncio.sleep(4)
    
    print("[*] Tiêu đề trang:", await page.title())
    
    # Tìm ô chat
    chat_box = page.locator('textarea, input[placeholder*="Message" i], [contenteditable="true"]').first
    if await chat_box.count() > 0:
        print("[+] Tìm thấy ô chat! Đang nhập phản hồi onboarding...")
        await chat_box.click()
        await chat_box.fill("Director")
        await asyncio.sleep(1)
        await page.keyboard.press("Enter")
        print("[*] Đã gửi tên 'Director', chờ Muse phản hồi...")
        await asyncio.sleep(6)
        
        # Đọc tin nhắn mới nhất trong chat
        texts = await page.locator('div, p, span').filter(has_text="Director").all_inner_texts()
        print("[+] Các đoạn text gần nhất:", texts[:3])
        
        # Chụp ảnh sau onboarding
        ss_path = Path(r"D:\Muse\muse_studio\data\profiles\acc_d5b0c7e2\after_onboarding.png")
        await page.screenshot(path=str(ss_path))
        print("[+] Đã lưu screenshot tại:", ss_path)
    else:
        print("[-] Không tìm thấy ô chat")
        
    await context.close()
    await pw.stop()

if __name__ == "__main__":
    asyncio.run(test_interaction())
