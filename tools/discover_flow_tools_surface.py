"""READ-ONLY discovery of the Flow Tools / custom mini-app surface.

FROZEN-CONSTRAINTS-001 (LONGRUN-001 Phase 3):
- No provider mutation of any kind: no Create, Save, Generate, Remix, Run or
  upload is clicked. Only navigation/reading/screenshotting.
- No cookie export, no token capture, no network traffic recording.
- Screenshots and DOM inventories stay in scratch/ (untracked local evidence);
  only sanitized structural findings reach committed documentation.

Output: scratch/flow_tools_discovery/discovery_report.json + screenshots.
"""
import json
import re
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

from playwright.sync_api import sync_playwright

PROFILE_PATH = Path(r"D:\AI FILM MAKER\Flow-Claude-Clean-Profile")
OUT = Path(__file__).resolve().parents[1] / "scratch" / "flow_tools_discovery"
OUT.mkdir(parents=True, exist_ok=True)

report = {"started_at": datetime.now(timezone.utc).isoformat(), "steps": []}


def step(name, **data):
    entry = {"name": name, "at": datetime.now(timezone.utc).isoformat(), **data}
    report["steps"].append(entry)
    print(json.dumps(entry)[:400], flush=True)
    (OUT / "discovery_report.json").write_text(
        json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")


def visible_inventory(page, selectors, limit=400):
    """Read-only structural inventory: text + aria attributes of elements."""
    items = []
    for selector in selectors:
        for element in page.locator(selector).all()[:limit]:
            try:
                text = " ".join(element.inner_text().split())[:120]
            except Exception:
                text = None
            try:
                aria = element.get_attribute("aria-label")
            except Exception:
                aria = None
            if text or aria:
                items.append({"selector": selector, "text": text, "aria": aria})
    return items


with sync_playwright() as p:
    ctx = p.chromium.launch_persistent_context(
        str(PROFILE_PATH),
        channel="chrome",
        headless=False,
        args=["--no-first-run", "--no-default-browser-check",
              "--disable-blink-features=AutomationControlled"],
        ignore_default_args=["--enable-automation"],
        viewport=None,
    )
    page = ctx.pages[0] if ctx.pages else ctx.new_page()
    try:
        step("launch", profile=str(PROFILE_PATH))
        page.goto("https://flow.google.com/", timeout=60000)
        page.wait_for_timeout(6000)
        step("navigated", url=page.url)

        if "accounts.google" in page.url or "ServiceLogin" in page.url:
            step("auth_gate", gate="OWNER_AUTH_GATE_LOGIN_LOST", url=page.url)
            sys.exit(2)

        # Frontend build fingerprint (script path), read-only.
        builds = page.evaluate(
            "() => Array.from(document.scripts).map(s => s.src)"
            ".filter(src => /boq_labs|ai-sandbox/.test(src)).slice(0, 8)")
        step("frontend_scripts", scripts=[re.sub(r'/v\d+/.*$', '/<path>', s) for s in builds])

        # Settings summary tokens (re-qualification scope check), read-only.
        try:
            summary = page.locator("button.settings-trigger-button")
            tokens = summary.first.inner_text() if summary.count() else None
        except Exception:
            tokens = None
        step("settings_tokens_readonly", tokens=tokens)

        # Left navigation / top-level affordances.
        nav = visible_inventory(page, [
            "nav a", "nav button", "aside a", "aside button",
            "a[href*='tool']", "button[data-test-id]",
        ])
        step("nav_inventory", items=nav[:80])
        page.screenshot(path=str(OUT / "01_board.png"))

        # Look for any Tools entry point anywhere in the DOM (read-only).
        candidates = page.evaluate("""() => {
            const wanted = /tool|build|create a tool|my tools|mini.?app/i;
            const out = [];
            for (const el of document.querySelectorAll('a,button,[role=link],[role=tab],[role=button]')) {
                const text = (el.innerText || el.getAttribute('aria-label') || '').trim();
                if (text && wanted.test(text) && text.length < 80) {
                    out.push({tag: el.tagName, text: text.slice(0, 80),
                              href: el.getAttribute('href')});
                }
            }
            return out.slice(0, 40);
        }""")
        step("tool_entry_candidates", items=candidates)

        tool_link = next((c for c in candidates
                          if re.search(r'\btools?\b', c["text"], re.I) and c.get("href")),
                         None)
        tool_button = next((c for c in candidates
                            if re.fullmatch(r'tools?', c["text"] or "", re.I)), None)
        if tool_link:
            page.goto(tool_link["href"] if tool_link["href"].startswith("http")
                      else "https://flow.google.com" + tool_link["href"], timeout=60000)
        elif tool_button or candidates:
            target = page.locator("a,button,[role=link],[role=tab]", has_text=re.compile(
                r'^\s*Tools?\s*$', re.I)).first
            if target.count():
                target.click(timeout=10000)
            else:
                step("tools_entry_not_found")
        else:
            step("tools_entry_not_found")
        page.wait_for_timeout(6000)
        step("tools_page", url=page.url)
        page.screenshot(path=str(OUT / "02_tools_page.png"))

        # Inventory the Tools page: sections, cards, create affordances.
        sections = visible_inventory(page, [
            "h1", "h2", "h3", "h4", "button", "a", "[role=button]", "[role=tab]",
        ])
        step("tools_page_inventory", items=sections[:150])

        cards = page.evaluate("""() => {
            const out = [];
            for (const el of document.querySelectorAll('a,button,[role=link],[role=button]')) {
                const text = (el.innerText || '').trim().replace(/\\s+/g, ' ');
                if (text && text.length > 2 && text.length < 90)
                    out.push({tag: el.tagName, text});
            }
            return out.slice(0, 120);
        }""")
        step("tools_cards_text", items=cards)

        create_candidates = [c for c in cards
                             if re.search(r'create|new tool|build|remix|duplicate',
                                          c["text"], re.I)]
        step("create_affordances_text_only", items=create_candidates,
             note="NOT clicked in Phase 3 (read-only)")

        report["finished_at"] = datetime.now(timezone.utc).isoformat()
        report["phase3"] = "READ_ONLY_COMPLETE"
        (OUT / "discovery_report.json").write_text(
            json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
        step("done")
    finally:
        try:
            ctx.close()
        except Exception:
            pass
