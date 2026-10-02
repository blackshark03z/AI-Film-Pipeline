"""READ-ONLY discovery round 4: My tools tab + Templates tab + community card titles.

Navigation-only tab clicks. No Create/Save/Generate/Remix/Run.
"""
import json
import re
from datetime import datetime, timezone
from pathlib import Path

from playwright.sync_api import sync_playwright

PROFILE_PATH = Path(r"D:\AI FILM MAKER\Flow-Claude-Clean-Profile")
OUT = Path(__file__).resolve().parents[1] / "scratch" / "flow_tools_discovery"
OUT.mkdir(parents=True, exist_ok=True)
PROJECT_ID = "93a579b4-834e-435b-8304-5f6682937935"

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
    print(json.dumps(entry, ensure_ascii=False)[:1400], flush=True)
    (OUT / "discovery_report4.json").write_text(
        json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")


def titles(page):
    raw = page.evaluate("""() => {
        const out = [];
        for (const el of document.querySelectorAll('a,button,[role=link],[role=button],h1,h2,h3,h4,[class*=title],[class*=card]')) {
            const text = (el.innerText || '').trim().replace(/\\s+/g, ' ');
            if (text && 1 < text.length < 90 && !/^(arrow_back|more_vert|close|help|search|filter_list|add|edit|delete|home)$/.test(text))
                out.push({tag: el.tagName, text: text.slice(0, 90)});
        }
        return out;
    }""")
    seen, out = set(), []
    for item in scrub(raw):
        if item["text"] not in seen:
            seen.add(item["text"])
            out.append(item)
    return out[:80]


with sync_playwright() as p:
    ctx = p.chromium.launch_persistent_context(
        str(PROFILE_PATH), channel="chrome", headless=False,
        args=["--no-first-run", "--no-default-browser-check",
              "--disable-blink-features=AutomationControlled"],
        ignore_default_args=["--enable-automation"], viewport=None)
    page = ctx.pages[0] if ctx.pages else ctx.new_page()
    try:
        page.goto(f"https://flow.google.com/project/{PROJECT_ID}/tools?tab=COMMUNITY",
                  timeout=60000)
        page.wait_for_timeout(8000)
        if "accounts.google" in page.url:
            step("auth_gate", gate="OWNER_AUTH_GATE_LOGIN_LOST")
            raise SystemExit(2)
        step("community_titles", items=titles(page))

        for tab_name, shot in (("Công cụ của tôi", "08_my_tools.png"),
                               ("Mẫu", "09_templates.png")):
            tab = page.locator("button", has_text=re.compile(tab_name, re.I))
            if tab.count():
                tab.first.click(timeout=10000)
                page.wait_for_timeout(7000)
                step(f"tab_{tab_name}", url=page.url)
                page.screenshot(path=str(OUT / shot))
                step(f"tab_{tab_name}_titles", items=titles(page))
                body = " ".join(page.locator("body").inner_text().split())[:700]
                step(f"tab_{tab_name}_bodytext", text=body)

        report["finished_at"] = datetime.now(timezone.utc).isoformat()
        report["phase3"] = "READ_ONLY_ROUND4_COMPLETE"
        (OUT / "discovery_report4.json").write_text(
            json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
        step("done")
    finally:
        try:
            ctx.close()
        except Exception:
            pass
