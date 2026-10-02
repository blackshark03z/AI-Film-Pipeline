"""Launch clean visible headful Chrome for Owner login to Google Flow.

Does not record traffic, cookies, credentials, or tokens.
Keeps browser window open until Owner completes login and signals READY.
"""
from pathlib import Path
import sys
import time
from playwright.sync_api import sync_playwright

PROFILE_PATH = Path(r"D:\AI FILM MAKER\Flow-Claude-Clean-Profile")
PROFILE_PATH.mkdir(parents=True, exist_ok=True)

print(f"Launching clean headful Chrome with profile: {PROFILE_PATH}...", flush=True)

with sync_playwright() as p:
    ctx = p.chromium.launch_persistent_context(
        str(PROFILE_PATH),
        channel="chrome",
        headless=False,
        args=[
            "--no-first-run",
            "--no-default-browser-check",
            "--disable-blink-features=AutomationControlled",
        ],
        ignore_default_args=["--enable-automation"],
        viewport=None,
    )
    page = ctx.pages[0] if ctx.pages else ctx.new_page()
    print("Navigating to https://flow.google.com/...", flush=True)
    page.goto("https://flow.google.com/")
    print("CHROME_READY_FOR_OWNER_LOGIN", flush=True)
    
    try:
        while True:
            time.sleep(1)
            if not ctx.pages:
                break
    except KeyboardInterrupt:
        pass
    except Exception as exc:
        print(f"Browser loop ended: {exc}", flush=True)
    finally:
        try:
            ctx.close()
        except Exception:
            pass
