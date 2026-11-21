import asyncio
from pathlib import Path
from playwright.async_api import async_playwright

async def inspect_chat():
    pw = await async_playwright().start()
    profile_dir = Path(r"D:\Muse\muse_studio\data\profiles\acc_d5b0c7e2")
    context = await pw.chromium.launch_persistent_context(
        user_data_dir=str(profile_dir),
        headless=True
    )
    page = context.pages[0] if context.pages else await context.new_page()
    await page.goto("https://muse.ai", timeout=30000, wait_until="networkidle")
    print("Title:", await page.title())
    print("URL:", page.url)
    
    # Check textareas or inputs
    boxes = await page.locator('textarea, [contenteditable="true"], input').all()
    print("Input/Textarea elements count:", len(boxes))
    for i, b in enumerate(boxes):
        tag = await b.evaluate("el => el.tagName")
        ph = await b.get_attribute("placeholder")
        cls = await b.get_attribute("class")
        print(f"  Box {i}: tag={tag}, placeholder={ph}")
        
    # Check buttons
    btns = await page.locator("button").all()
    print("Buttons count:", len(btns))
    for b in btns[:15]:
        t = (await b.inner_text()).strip().replace("\n", " ")
        title = await b.get_attribute("title") or await b.get_attribute("aria-label")
        print(f'  Btn: text="{t}", title/aria="{title}"')
        
    # Check file inputs
    file_inputs = await page.locator('input[type="file"]').all()
    print("File inputs count:", len(file_inputs))
    for f in file_inputs:
        acc = await f.get_attribute("accept")
        print("  File input accept:", acc)
        
    await context.close()
    await pw.stop()

if __name__ == "__main__":
    asyncio.run(inspect_chat())
