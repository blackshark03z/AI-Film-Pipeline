"""READ-ONLY discovery round 3: Tools gallery card inventory + My tools/Templates tabs.

Same frozen constraints: no Create/Save/Generate/Remix/Run clicks, no
cookie/token capture; local untracked evidence only; emails scrubbed.
"""
import json
import re
from datetime import datetime, timezone
from pathlib import Path

from playwright.sync_api import sync_playwright

PROFILE_PATH = Path(r"D:\AI FILM MAKER\Flow-Claude-Clean-Profile")
OUT = Path(__file__).resolve().parents[1] / "scratch" / "flow_tools_discovery"
OUT.mkdir(parents=True, exist_ok=True)
TOOLS_URL_PREFIX = "https://flow.google.com/project"
PROJECT_ID = "93a579b4-834e-435b-8304-5f6682937935"  # qualified project (already in committed evidence)

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
    print(json.dumps(entry, ensure_ascii=False)[:900], flush=True)
    (OUT / "discovery_report3.json").write_text(
        json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")


def card_inventory(page):
    """Card titles live in aria-labels of interactive/named elements."""
    raw = page.evaluate("""() => {
        const out = [];
        for (const el of document.querySelectorAll('[aria-label]')) {
            const label = el.getAttribute('aria-label') || '';
            if (label && label.length > 1 && label.length < 120) {
                const rect = el.getBoundingClientRect();
                out.push({tag: el.tagName, label: label.replace(/\\s+/g, ' ').trim(),
                          visible: rect.width > 40 && rect.height > 40});
            }
        }
        return out;
    }""")
    return scrub([r for r in raw if r["visible"]])


with sync_playwright() as p:
    ctx = p.chromium.launch_persistent_context(
        str(PROFILE_PATH), channel="chrome", headless=False,
        args=["--no-first-run", "--no-default-browser-check",
              "--disable-blink-features=AutomationControlled"],
        ignore_default_args=["--enable-automation"], viewport=None)
    page = ctx.pages[0] if ctx.pages else ctx.new_page()
    try:
        page.goto(f"{TOOLS_URL_PREFIX}/{PROJECT_ID}/tools?tab=COMMUNITY", timeout=60000)
        page.wait_for_timeout(8000)
        if "accounts.google" in page.url:
            step("auth_gate", gate="OWNER_AUTH_GATE_LOGIN_LOST")
            raise SystemExit(2)
        step("community_tab", url=page.url)
        page.screenshot(path=str(OUT / "05_community_full.png"), full_page=True)
        step("community_cards", items=card_inventory(page))

        mine = page.get_by_role("button", name=re.compile("Công cụ của tôi", re.I))
        if mine.count():
            mine.first.click(timeout=10000)
            page.wait_for_timeout(6000)
            step("my_tools_tab", url=page.url)
            page.screenshot(path=str(OUT / "06_my_tools.png"))
            step("my_tools_cards", items=card_inventory(page))
            body_text = " ".join(page.locator("body").inner_text().split())[:600]
            step("my_tools_text", text=body_text)

        templates = page.get_by_role("button", name=re.compile("Mẫu", re.I))
        if templates.count():
            templates.first.click(timeout=10000)
            page.wait_for_timeout(6000)
            step("templates_tab", url=page.url)
            page.screenshot(path=str(OUT / "07_templates.png"))
            step("templates_cards", items=card_inventory(page))

        report["finished_at"] = datetime.now(timezone.utc).isoformat()
        report["phase3"] = "READ_ONLY_ROUND3_COMPLETE"
        (OUT / "discovery_report3.json").write_text(
            json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
        step("done")
    finally:
        try:
            ctx.close()
        except Exception:
            pass
