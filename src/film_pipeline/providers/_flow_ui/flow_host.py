"""Keep a headful Chrome on the Flow profile open with a local CDP port.
Never reads, prints or exports cookies."""
import time
from playwright.sync_api import sync_playwright
PROFILE = r"D:\AI FILM MAKER\Flow-Claude-Clean-Profile"
with sync_playwright() as p:
    ctx = p.chromium.launch_persistent_context(
        PROFILE, channel="chrome", headless=False,
        args=["--no-first-run", "--no-default-browser-check",
              "--disable-blink-features=AutomationControlled",
              "--remote-debugging-port=9333"],
        ignore_default_args=["--enable-automation"], viewport=None)
    page = ctx.pages[0] if ctx.pages else ctx.new_page()
    page.goto("https://flow.google.com/")
    print("FLOW_HOST_READY", flush=True)
    while ctx.pages:
        time.sleep(2)
