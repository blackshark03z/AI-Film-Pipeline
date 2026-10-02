"""READ-ONLY inventory of the saved tool's Edit (config) view.

Zero mutation: navigation + reading + screenshots only. No typing, no control
clicks, no save. OWNER_AMBIGUITY_GATE remains active for all mutation.
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
    print(json.dumps(entry, ensure_ascii=False)[:1500], flush=True)
    (OUT / "edit_view_report.json").write_text(
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
        step("edit_view", url=page.url)
        page.screenshot(path=str(OUT / "22_tool_edit.png"))
        raw = page.evaluate("""() => {
            const out = [];
            for (const el of document.querySelectorAll(
                    'h1,h2,h3,h4,p,span,div,button,input,textarea,select,[role=textbox],[role=button]')) {
                const text = (el.innerText || '').trim().replace(/\\s+/g, ' ');
                const ph = el.getAttribute('placeholder') || '';
                const aria = el.getAttribute('aria-label') || '';
                if ((text || ph || aria) && text.length < 200)
                    out.push({tag: el.tagName, cls: (el.className || '').toString().slice(0, 40),
                              text: text.slice(0, 200), ph: ph.slice(0, 80), aria: aria.slice(0, 80)});
            }
            return out;
        }""")
        seen, items = set(), []
        for item in scrub(raw):
            key = json.dumps(item, sort_keys=True)
            if key not in seen:
                seen.add(key)
                items.append(item)
        # Only leaf-ish content: keep items whose text is not reproduced by a
        # longer sibling (rough dedup) — full dump is written to the report.
        step("edit_view_full_dump", items=items[:200])
        page.screenshot(path=str(OUT / "23_tool_edit_full.png"), full_page=True)
        step("done")
    finally:
        try:
            ctx.close()
        except Exception:
            pass
