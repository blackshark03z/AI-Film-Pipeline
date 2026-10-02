"""READ-ONLY discovery round 2: Tools page + qualified-board re-qualification check.

Same frozen constraints as round 1: no Create/Save/Generate/Remix/Run clicks,
no cookie/token capture; local untracked evidence only. Account emails are
scrubbed from captured structures.
"""
import json
import re
from datetime import datetime, timezone
from pathlib import Path

from playwright.sync_api import sync_playwright

PROFILE_PATH = Path(r"D:\AI FILM MAKER\Flow-Claude-Clean-Profile")
OUT = Path(__file__).resolve().parents[1] / "scratch" / "flow_tools_discovery"
OUT.mkdir(parents=True, exist_ok=True)
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
    print(json.dumps(entry, ensure_ascii=False)[:500], flush=True)
    (OUT / "discovery_report2.json").write_text(
        json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")


def inventory(page, selectors, limit=300):
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
                items.append({"sel": selector, "text": text, "aria": aria})
    return scrub(items)


with sync_playwright() as p:
    ctx = p.chromium.launch_persistent_context(
        str(PROFILE_PATH), channel="chrome", headless=False,
        args=["--no-first-run", "--no-default-browser-check",
              "--disable-blink-features=AutomationControlled"],
        ignore_default_args=["--enable-automation"], viewport=None)
    page = ctx.pages[0] if ctx.pages else ctx.new_page()
    try:
        page.goto("https://flow.google.com/", timeout=60000)
        page.wait_for_timeout(6000)
        if "accounts.google" in page.url:
            step("auth_gate", gate="OWNER_AUTH_GATE_LOGIN_LOST")
            raise SystemExit(2)
        step("home", url=page.url)

        # --- Read-only: open the Tools gallery -----------------------------
        explore = page.get_by_role("button", name=re.compile("Explore Tools", re.I))
        if not explore.count():
            explore = page.locator("button", has_text=re.compile("Explore Tools", re.I))
        explore.first.click(timeout=15000)
        page.wait_for_timeout(7000)
        step("tools_gallery", url=page.url)
        page.screenshot(path=str(OUT / "03_tools_gallery.png"))
        step("tools_gallery_inventory",
             items=inventory(page, ["h1", "h2", "h3", "h4", "button", "a", "[role=button]",
                                    "[role=tab]", "textarea", "input"]))
        cards = page.evaluate("""() => {
            const out = [];
            for (const el of document.querySelectorAll('a,button,[role=link],[role=button]')) {
                const text = (el.innerText || '').trim().replace(/\\s+/g, ' ');
                if (text && text.length > 1 && text.length < 100)
                    out.push({tag: el.tagName, text});
            }
            return out;
        }""")
        step("tools_gallery_items", items=scrub(cards)[:160])
        create = [c for c in cards if re.search(r'create|new tool|build|remix|duplicate|use',
                                                c["text"], re.I)]
        step("create_affordances_text_only", items=scrub(create), note="NOT clicked")

        # --- Read-only: back to a project board (re-qualification check) ----
        page.goto("https://flow.google.com/", timeout=60000)
        page.wait_for_timeout(5000)
        board = page.get_by_role("link", name=re.compile("Mở dự án", re.I)).first
        if not board.count():
            board = page.locator("a", has_text=re.compile("Mở dự án", re.I)).first
        board.click(timeout=15000)
        page.wait_for_timeout(8000)
        step("project_board", url=page.url)
        page.screenshot(path=str(OUT / "04_project_board.png"))
        try:
            summary = page.locator("button.settings-trigger-button")
            tokens = summary.first.inner_text() if summary.count() else None
        except Exception:
            tokens = None
        board_inventory = inventory(page, ["button", "[role=button]", "div.ProseMirror"])
        step("board_settings_readonly", settings_tokens=tokens)
        step("board_inventory", items=board_inventory[:80])
        present = {
            "settings_trigger": bool(page.locator("button.settings-trigger-button").count()),
            "generate_button": bool(page.locator("button.generate-icon-button").count()),
            "prosemirror_editor": bool(page.locator("div.ProseMirror[contenteditable='true']").count()),
            "chip_container": bool(page.locator("button.chip-container img.chip-image").count()),
            "add_menu_trigger": bool(page.locator("button.add-menu-trigger").count()),
        }
        step("qualified_ui_selectors_present", selectors=present)

        report["finished_at"] = datetime.now(timezone.utc).isoformat()
        report["phase3"] = "READ_ONLY_ROUND2_COMPLETE"
        (OUT / "discovery_report2.json").write_text(
            json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
        step("done")
    finally:
        try:
            ctx.close()
        except Exception:
            pass
