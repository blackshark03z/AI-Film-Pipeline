"""READ-ONLY post-gate verification of the canary tool save state.

OWNER_AMBIGUITY_GATE is active: this script performs ZERO provider mutation.
Navigation + reading + screenshots only. It resolves the recorded ambiguity
(what external effect the single Xong/save click produced) without changing
anything.
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
    print(json.dumps(entry, ensure_ascii=False)[:1200], flush=True)
    (OUT / "verification_report.json").write_text(
        json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")


def everything(page):
    raw = page.evaluate("""() => {
        const out = [];
        for (const el of document.querySelectorAll('a,button,[role=link],[role=button],h1,h2,h3,h4,input,textarea,[role=textbox],[role=dialog],select,option,[class*=title],[class*=card]')) {
            const text = (el.innerText || '').trim().replace(/\\s+/g, ' ');
            const aria = el.getAttribute('aria-label') || '';
            const href = el.getAttribute('href') || '';
            if (text || aria || href)
                out.push({tag: el.tagName, text: text.slice(0, 100),
                          aria: aria.slice(0, 100), href});
        }
        return out;
    }""")
    seen, out = set(), []
    for item in scrub(raw):
        key = json.dumps(item, sort_keys=True)
        if key not in seen:
            seen.add(key)
            out.append(item)
    return out[:150]


with sync_playwright() as p:
    ctx = p.chromium.launch_persistent_context(
        str(PROFILE_PATH), channel="chrome", headless=False,
        args=["--no-first-run", "--no-default-browser-check",
              "--disable-blink-features=AutomationControlled"],
        ignore_default_args=["--enable-automation"], viewport=None)
    page = ctx.pages[0] if ctx.pages else ctx.new_page()
    try:
        # 1: direct read-only view of the tool identity assigned by the builder.
        page.goto(f"https://flow.google.com/project/{PROJECT_ID}/tool/{TOOL_ID}",
                  timeout=60000)
        page.wait_for_timeout(9000)
        step("tool_view", url=page.url)
        page.screenshot(path=str(OUT / "20_tool_view.png"))
        step("tool_view_inventory", items=everything(page))

        # 2: My tools tab, full card extraction (read-only).
        page.goto(f"https://flow.google.com/project/{PROJECT_ID}/tools",
                  timeout=60000)
        page.wait_for_timeout(7000)
        mine = page.locator("button", has_text=re.compile("Công cụ của tôi", re.I))
        if mine.count():
            mine.first.click(timeout=10000)
            page.wait_for_timeout(7000)
        step("my_tools_url", url=page.url)
        page.screenshot(path=str(OUT / "21_my_tools.png"))
        step("my_tools_inventory", items=everything(page))

        report["finished_at"] = datetime.now(timezone.utc).isoformat()
        (OUT / "verification_report.json").write_text(
            json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
        step("done")
    finally:
        try:
            ctx.close()
        except Exception:
            pass
