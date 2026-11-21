import asyncio
from pathlib import Path
from playwright.async_api import async_playwright

async def test_video_generation():
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
    
    # 1. Nếu có nút "Log in" 1-click
    login_btn = page.locator('button:has-text("Log in")').first
    if await login_btn.count() > 0:
        print("[*] Click nút Log in 1-click...")
        await login_btn.click()
        await asyncio.sleep(5)
        
    print("[*] URL hiện tại:", page.url)
    print("[*] Title hiện tại:", await page.title())
    
    # 2. Tìm ô chat
    chat_box = page.locator('textarea, [contenteditable="true"], input[placeholder*="Message" i]').first
    if await chat_box.count() > 0:
        print("[+] Đã vào giao diện chat! Đang gửi prompt tạo video...")
        prompt_text = "Generate a short video: A professional African American female airline captain standing in cockpit doorway looking confident."
        await chat_box.click()
        await chat_box.fill(prompt_text)
        await asyncio.sleep(1)
        await page.keyboard.press("Enter")
        print("[*] Đã gửi prompt! Đang theo dõi phản hồi của Muse trong 30s...")
        
        for sec in range(1, 31):
            await asyncio.sleep(1)
            # Kiểm tra xem có video hoặc tiến trình render không
            vids = await page.locator("video").all()
            if len(vids) > 0:
                print(f"[!] Tìm thấy {len(vids)} video ở giây thứ {sec}!")
                for v in vids:
                    src = await v.get_attribute("src")
                    print("    Video src:", src)
                    
        # Chụp ảnh sau 30s
        await page.screenshot(path=r"C:\Users\ADMIN\.gemini\antigravity\brain\920939ed-0307-4640-94c5-5d3f05f88f81\video_gen_snap.png")
        print("[+] Đã lưu ảnh kết quả tại video_gen_snap.png")
        
        # Đọc text trong chat
        chat_text = await page.locator("body").inner_text()
        print("[+] Text trong chat (200 ký tự cuối):", chat_text[-300:])
        
    else:
        print("[-] Không tìm thấy ô chat!")
        await page.screenshot(path=r"C:\Users\ADMIN\.gemini\antigravity\brain\920939ed-0307-4640-94c5-5d3f05f88f81\no_chat_snap.png")
        
    await context.close()
    await pw.stop()

if __name__ == "__main__":
    asyncio.run(test_video_generation())
