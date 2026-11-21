import asyncio
from pathlib import Path
from playwright.async_api import async_playwright

async def inspect_muse_elements():
    pw = await async_playwright().start()
    profile_dir = Path(r"D:\Muse\muse_studio\data\profiles\acc_d5b0c7e2")
    context = await pw.chromium.launch_persistent_context(
        user_data_dir=str(profile_dir),
        headless=True
    )
    page = context.pages[0] if context.pages else await context.new_page()
    await page.goto("https://muse.ai", timeout=45000, wait_until="domcontentloaded")
    await asyncio.sleep(4)
    
    # 1. Check all inputs
    inputs = await page.locator("input").all()
    print("Inputs count:", len(inputs))
    for i, inp in enumerate(inputs):
        typ = await inp.get_attribute("type")
        acc = await inp.get_attribute("accept")
        print(f"Input {i}: type={typ}, accept={acc}")
        
    # 2. Check textarea or contenteditable
    textareas = await page.locator('textarea, [contenteditable="true"]').all()
    print("Textareas count:", len(textareas))
    for i, ta in enumerate(textareas):
        ph = await ta.get_attribute("placeholder")
        tag = await ta.evaluate("el => el.tagName")
        print(f"Textarea {i}: tag={tag}, placeholder={ph}")
        
    # 3. Check plus button or upload button
    plus_btns = await page.locator('button:has-text("+"), [aria-label*="attach" i], [aria-label*="upload" i], [aria-label*="add" i]').all()
    print("Plus/Attach buttons count:", len(plus_btns))
    for b in plus_btns:
        aria = await b.get_attribute("aria-label")
        t = (await b.inner_text()).strip()
        print(f"Button: text={t}, aria={aria}")
        
    await context.close()
    await pw.stop()

if __name__ == "__main__":
    asyncio.run(inspect_muse_elements())
