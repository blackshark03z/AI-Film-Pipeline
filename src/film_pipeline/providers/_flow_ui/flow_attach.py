"""Attach uploaded ingredients to the Flow composer by file-name prefix, in order.
Usage: flow_attach.py name1 name2 ...   (picker is opened via the composer "+")"""
import asyncio, sys

async def main(names):
    from patchright.async_api import async_playwright
    pw = await async_playwright().start()
    try:
        b = await pw.chromium.connect_over_cdp("http://127.0.0.1:9333")
        page = [p for p in b.contexts[0].pages if "flow.google" in p.url][0]
        for n in names:
            add = page.get_by_text("Thêm vào câu lệnh", exact=True)
            if not await add.count():
                await page.mouse.click(359, 662)
                await page.wait_for_timeout(1500)
            await page.locator(f"text={n} >> visible=true").first.click()
            await page.wait_for_timeout(800)
            await page.get_by_text("Thêm vào câu lệnh", exact=True).click()
            await page.wait_for_timeout(1500)
            print("attached", n)
    finally:
        await pw.stop()

asyncio.run(main(sys.argv[1:]))
