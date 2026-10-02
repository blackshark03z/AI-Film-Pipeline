"""READ-ONLY dump of the saved tool's Code (Mã) view.

Only view toggles are clicked (Preview/Code tabs). No editing, no save,
no run. OWNER_AMBIGUITY_GATE remains active for all provider mutation.
"""
import json
import re
from datetime import datetime, timezone
from pathlib import Path

from playwright.sync_api import sync_playwright

PROFILE_PATH = Path(r"D:\AI FILM MAKER\Flow-Claude-Clean-Profile")
OUT = Path(__file__).resolve().parents[1] / "scratch" / "flow_tool_canary"
PROJECT_ID = "93a579b4-834e-435b-8304-5f6682937935"
TOOL_ID = "083a64f8-6f43-4a48-bd1b-3f1cc81e6b12"
report = {"started_at": datetime.now(timezone.utc).isoformat(), "steps": []}


def scrub(value):
    if isinstance(value, str):
        return re.sub(r"[\w.+-]+@[\w-]+\.[\w.]+", "<EMAIL>", value)
    if isinstance(value, list):
        return [scrub(v) for v in value]
    if isinstance(value, dict):
        return {k: scrub(v) for k, v in value.items()}
    return value


def step(name, **data):
    entry = scrub({"name": name, "at": datetime.now(timezone.utc).isoformat(), **data})
    report["steps"].append(entry)
    print(json.dumps(entry, ensure_ascii=False)[:300], flush=True)
    (OUT / "code_view_report.json").write_text(
        json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")


with sync_playwright() as p:
    ctx = p.chromium.launch_persistent_context(
        str(PROFILE_PATH), channel="chrome", headless=False,
        args=["--no-first-run", "--no-default-browser-check",
              "--disable-blink-features=AutomationControlled"],
        ignore_default_args=["--enable-automation"], viewport=None)
    page = ctx.pages[0] if ctx.pages else ctx.new_page()
    try:
        page.goto(f"https://flow.google.com/project/{PROJECT_ID}/tool/{TOOL_ID}?mode=EDIT",
                  timeout=60000)
        page.wait_for_timeout(9000)
        code_tab = page.locator("button", has_text=re.compile(r"^\s*Mã\s*$", re.I))
        if not code_tab.count():
            code_tab = page.locator("button.applet-content-tab", has_text=re.compile("Mã", re.I))
        step("code_tab_found", count=code_tab.count())
        code_tab.first.click(timeout=10000)
        page.wait_for_timeout(8000)
        step("code_view", url=page.url)
        page.screenshot(path=str(OUT / "24_tool_code.png"))
        text = page.evaluate("""() => {
            const areas = document.querySelectorAll('pre, code, .code, [class*=code], textarea');
            let best = '';
            for (const el of areas) {
                const t = el.innerText || '';
                if (t.length > best.length) best = t;
            }
            return best.slice(0, 20000);
        }""")
        (OUT / "tool_code_dump.txt").write_text(text, encoding="utf-8")
        step("code_dump", length=len(text), head=text[:600])
        page.screenshot(path=str(OUT / "25_tool_code_full.png"), full_page=True)
        step("done")
    finally:
        try:
            ctx.close()
        except Exception:
            pass
