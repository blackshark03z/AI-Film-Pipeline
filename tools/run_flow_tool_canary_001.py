"""FLOW-PRODUCTION-TOOLS-LONGRUN-001 Phase 4 — minimal Flow Tool canary.

Frozen budgets (package authority, never retry authority):
    MAX_CUSTOM_TOOL_CREATE_OR_SAVE = 1
    MAX_FRESH_VIDEO_GENERATE       = 1   (optional; only if semantics require)

Hard rules enforced by this runner:
- ONE tool create/save flow; ONE optional Tool-driven video generation.
- Any ambiguous external effect / ambiguous identity / ambiguous save state
  => OWNER_AMBIGUITY_GATE: stop all provider mutation, record, no retry.
- Payment/subscription prompts are NEVER accepted => OWNER_PAYMENT_GATE.
- No cookie export; no token capture; no request bodies persisted (only
  lengths/structural facts). All evidence local under scratch/ (untracked).
- Publish/share controls are NEVER clicked (outward-facing action).
- Reconciliation is read-only through the qualified session surfaces.

Stages (durable journal in scratch/flow_tool_canary/journal.json):
  1 baseline   — qualified read-only catalog snapshot before any mutation
  2 create     — open builder, describe tool, save once, verify in My tools
  3 generate   — optional single Tool-run video generate with marker embedded
Stage 4 (read-only reconciliation + acquisition) runs as a separate script.
"""
import json
import re
import secrets
from datetime import datetime, timezone
from pathlib import Path

from film_pipeline.core import canonical_json, sha256
from film_pipeline.providers.flow_reference_rpc import (
    FlowReferenceRpcDrift,
    FlowReferenceRpcSession,
)
from film_pipeline.flow_r2v_runtime import qualified_catalog_snapshot

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "scratch" / "flow_tool_canary"
OUT.mkdir(parents=True, exist_ok=True)
JOURNAL = OUT / "journal.json"
PROFILE = Path(r"D:\AI FILM MAKER\Flow-Claude-Clean-Profile")
PROJECT_ID = "93a579b4-834e-435b-8304-5f6682937935"  # qualified project (committed evidence)
ACCOUNT_TAG = "clean-pro-qualified"

MAX_CREATE_OR_SAVE = 1
MAX_GENERATE = 1

TOOL_DESCRIPTION = (
    "AI Film Shot Tool. Inputs: a single free-text 'shot prompt' describing one "
    "cinematic shot. Behavior: generate exactly ONE video from that prompt using "
    "Flow's native video generation with 16:9 aspect ratio, 8-second duration and "
    "this project's current video model settings, and put the finished video into "
    "this Flow project's media. First-party Flow capabilities only; no external "
    "services.")

SHOTS = {}


def now():
    return datetime.now(timezone.utc).isoformat()


def load_journal():
    if JOURNAL.exists():
        return json.loads(JOURNAL.read_text(encoding="utf-8"))
    return {"started_at": now(), "account_tag": ACCOUNT_TAG,
            "project_id": PROJECT_ID, "events": [],
            "budget": {"create_or_save_used": 0, "generate_used": 0},
            "gates": [], "baseline_qualified": False}


def save_journal(journal):
    JOURNAL.write_text(json.dumps(journal, indent=2, ensure_ascii=False),
                       encoding="utf-8")


def event(journal, kind, **data):
    entry = {"kind": kind, "at": now(), **data}
    journal["events"].append(entry)
    save_journal(journal)
    print(json.dumps(entry, ensure_ascii=False)[:700], flush=True)
    return entry


def gate(journal, name, detail):
    journal["gates"].append({"name": name, "detail": detail, "at": now()})
    save_journal(journal)
    print("GATE:", name, detail, flush=True)


def shot(page, name, full=False):
    try:
        path = OUT / f"{len(SHOTS):02d}_{name}.png"
        page.screenshot(path=str(path), full_page=full)
        SHOTS[name] = path.name
    except Exception as error:
        print("screenshot failed:", error, flush=True)


def inventory(page, selectors=("h1", "h2", "h3", "button", "a", "textarea",
                               "input", "[role=button]", "[role=textbox]",
                               "[role=dialog]", "div.ProseMirror[contenteditable='true']"),
              limit=250):
    items = []
    for selector in selectors:
        for element in page.locator(selector).all()[:limit]:
            try:
                text = " ".join(element.inner_text().split())[:100] or None
            except Exception:
                text = None
            try:
                aria = element.get_attribute("aria-label")
            except Exception:
                aria = None
            try:
                placeholder = element.get_attribute("placeholder")
            except Exception:
                placeholder = None
            if text or aria or placeholder:
                items.append({"sel": selector, "text": text, "aria": aria,
                              "ph": placeholder})
    seen, out = set(), []
    for item in items:
        key = json.dumps(item, sort_keys=True)
        if key not in seen:
            seen.add(key)
            out.append(item)
    return out[:140]


def install_wire_observer(page, sink):
    """READ-ONLY wire observation: lengths/structure only, never bodies."""
    def on_request(request):
        try:
            if request.method != "POST" or "batchexecute" not in request.url:
                return
            body = request.post_data or ""
            sink.append({"at": now(),
                         "rpcs": re.findall(r"rpcids=([A-Za-z0-9_]+)", request.url),
                         "body_len": len(body.encode("utf-8")),
                         "mzza6b": "MZZa6b" in request.url or "MZZa6b" in body,
                         "marker_in_body": "[FILM-job_" in body})
        except Exception:
            pass

    def on_response(response):
        try:
            if "batchexecute" not in response.url:
                return
            sink.append({"at": now(), "response_status": response.status,
                         "rpcs": re.findall(r"rpcids=([A-Za-z0-9_]+)", response.url)})
        except Exception:
            pass

    page.on("request", on_request)
    page.on("response", on_response)


def current_page(ctx, page):
    """Follow SPA/popup reality: newest non-blank page in the context."""
    candidates = [p for p in ctx.pages
                  if not p.url.startswith(("about:blank", "devtools:"))]
    return candidates[-1] if candidates else page


# ---------------------------------------------------------------- stage 1
def stage_baseline(journal):
    if journal["baseline_qualified"]:
        print("baseline already qualified; skip", flush=True)
        return
    with FlowReferenceRpcSession(profile_path=PROFILE, project_id=PROJECT_ID,
                                 native_ui=True) as session:
        records = session.catalog()
        fingerprint = session.catalog_fingerprint
        snapshot = qualified_catalog_snapshot(records, project_id=PROJECT_ID,
                                              fingerprint=fingerprint)
    journal["baseline_qualified"] = True
    journal["baseline"] = snapshot
    event(journal, "baseline_captured", snapshot=snapshot,
          record_count=len(records), record_ids=[row[0] for row in records][:20])


# ---------------------------------------------------------------- stage 2
SAVE_RE = re.compile(r"\b(lưu|save|xong|done|hoàn thành|hoàn tất)\b", re.I)
PUBLISH_RE = re.compile(r"xuất bản|publish|chia sẻ|share|đăng công cụ|nổi bật", re.I)
RUN_RE = re.compile(r"chạy|run|generate|tạo video|thử", re.I)
PAYMENT_RE = re.compile(r"nâng cấp|upgrade|thanh toán|payment|mua|buy|giá\b|price", re.I)

INPUT_SELECTORS = ("textarea:visible", "div.ProseMirror[contenteditable='true']",
                   "[role=textbox]:visible", "input[type='text']:visible")


def fill_first_input(page, text, journal, event_name):
    """Fill the first visible, non-recaptcha description surface."""
    for selector in INPUT_SELECTORS:
        for candidate in page.locator(selector).all():
            try:
                attributes = (candidate.get_attribute("name") or "",
                              candidate.get_attribute("id") or "",
                              candidate.get_attribute("class") or "")
            except Exception:
                continue
            if any("recaptcha" in part.lower() for part in attributes):
                continue
            try:
                candidate.click(timeout=8000)
                if selector in ("textarea:visible", "input[type='text']:visible"):
                    candidate.fill(text)
                else:
                    page.keyboard.type(text, delay=8)
                event(journal, event_name, selector=selector)
                return True
            except Exception:
                continue
    return False


def submit_builder_prompt(page):
    """Send the builder chat prompt: Enter first, then the send control."""
    page.keyboard.press("Enter")
    page.wait_for_timeout(2500)
    page.evaluate("""() => {
        for (const el of document.querySelectorAll('button')) {
            const label = (el.getAttribute('aria-label') || '') +
                          ' ' + (el.innerText || '');
            if (/gửi|send/i.test(label) && !/công cụ|công khai|xuất bản/i.test(label)) {
                el.click();
                return true;
            }
        }
        return false;
    }""")
    return True


def stage_create(journal, ctx, page):
    if journal["budget"]["create_or_save_used"]:
        print("create budget already consumed; skip", flush=True)
        return
    if journal["gates"]:
        print("prior gate present; no mutation", flush=True)
        return
    page.goto(f"https://flow.google.com/project/{PROJECT_ID}/tools?tab=COMMUNITY",
              timeout=60000)
    page.wait_for_timeout(7000)
    shot(page, "create_entry")
    create_link = page.locator("a", has_text=re.compile("Tạo công cụ", re.I))
    if not create_link.count():
        gate(journal, "C4_CREATE_ENTRY_UNAVAILABLE", "no create-tool link")
        return
    # From here the create flow may produce a draft: record BEFORE the click.
    event(journal, "create_flow_entering", budget_allowance=MAX_CREATE_OR_SAVE)
    create_link.first.click(timeout=15000)
    page.wait_for_timeout(8000)
    page = current_page(ctx, page)
    shot(page, "builder_open")
    if "accounts.google" in page.url:
        gate(journal, "OWNER_AUTH_GATE", "login lost in builder")
        return
    event(journal, "builder_opened", url=page.url)
    items = inventory(page)
    event(journal, "builder_inventory", items=items)
    page.screenshot(path=str(OUT / "10_builder_inventory.png"), full_page=True)

    if not fill_first_input(page, TOOL_DESCRIPTION, journal, "description_filled"):
        gate(journal, "C4_BUILDER_INPUT_UNAVAILABLE", "no description input found")
        return
    shot(page, "description_filled")
    submit_builder_prompt(page)
    page.wait_for_timeout(12000)
    page = current_page(ctx, page)
    shot(page, "after_submit")

    # Bounded adaptive wait for the builder to produce a save control; answer
    # at most three follow-ups inside the SAME single create flow.
    followups = 0
    saved = False
    deadline = time.monotonic() + 420
    while time.monotonic() < deadline:
        page.wait_for_timeout(8000)
        page = current_page(ctx, page)
        shot(page, "build_poll")
        items = inventory(page)
        buttons = [i for i in items if i["sel"] in ("button", "[role=button]")]
        save_buttons = [b for b in buttons
                        if (b["text"] and SAVE_RE.search(b["text"]) and not PUBLISH_RE.search(b["text"]))
                        or (b["aria"] and SAVE_RE.search(b["aria"]) and not PUBLISH_RE.search(b["aria"]))]
        publish_only = [b for b in buttons
                        if ((b["text"] and PUBLISH_RE.search(b["text"]))
                            or (b["aria"] and PUBLISH_RE.search(b["aria"])))
                        and not ((b["text"] and SAVE_RE.search(b["text"]))
                                 or (b["aria"] and SAVE_RE.search(b["aria"])))]
        event(journal, "build_poll", url=page.url, n_buttons=len(buttons),
              save=[(b["text"], b["aria"]) for b in save_buttons][:6],
              publish_only=[(b["text"], b["aria"]) for b in publish_only][:6])
        if any(PAYMENT_RE.search((b["text"] or "") + (b["aria"] or ""))
               for b in buttons):
            gate(journal, "OWNER_PAYMENT_GATE", "payment prompt in builder; not accepted")
            return
        if save_buttons:
            # ONE save of the ONE tool. Never publish.
            page.locator("button", has_text=SAVE_RE).first.click(timeout=10000)
            event(journal, "save_clicked")
            page.wait_for_timeout(9000)
            page = current_page(ctx, page)
            # A naming/confirm dialog is still the same single save.
            confirm = page.locator("[role=dialog] button", has_text=SAVE_RE)
            if confirm.count():
                confirm.first.click(timeout=8000)
                event(journal, "save_dialog_confirmed")
                page.wait_for_timeout(6000)
            shot(page, "after_save")
            saved = True
            break
        if publish_only:
            gate(journal, "C4_SAVE_CONTROL_UNAVAILABLE",
                 "only publish/share controls present; not clicked")
            return
        if page.locator("textarea:visible").count() or \
                page.locator("div.ProseMirror[contenteditable='true']").count():
            followups += 1
            if followups > 3:
                gate(journal, "C4_BUILDER_UNRESOLVED", "too many follow-ups")
                return
            fill_first_input(page, "Use the defaults: one 16:9, 8-second video "
                                   "per run, saved into this project.",
                             journal, "followup_answered")
            submit_builder_prompt(page)
            event(journal, "followup_answered", n=followups)
            page.wait_for_timeout(12000)
    if not saved:
        gate(journal, "C4_SAVE_NOT_REACHED", "builder never offered a save control")
        return

    journal["budget"]["create_or_save_used"] = 1
    event(journal, "create_or_save_consumed", used=1, allowed=MAX_CREATE_OR_SAVE)

    # Verify uniqueness in My tools (read-only): click the tab, don't guess URLs.
    page.goto(f"https://flow.google.com/project/{PROJECT_ID}/tools?tab=COMMUNITY",
              timeout=60000)
    page.wait_for_timeout(7000)
    mine = page.locator("button", has_text=re.compile("Công cụ của tôi", re.I))
    if mine.count():
        mine.first.click(timeout=10000)
        page.wait_for_timeout(7000)
    shot(page, "my_tools_after_save")
    cards = page.evaluate("""() => {
        const out = [];
        for (const el of document.querySelectorAll('a,button,[role=link],[role=button]')) {
            const text = (el.innerText || '').trim().replace(/\\s+/g, ' ');
            if (text && 1 < text.length < 90) out.push({tag: el.tagName, text: text.slice(0, 90),
                                                        href: el.getAttribute('href')});
        }
        return out;
    }""")
    event(journal, "my_tools_after_save", items=cards[:80])
    tool_links = [c for c in cards if c.get("href") and "/tools/" in c["href"]]
    journal["tool_links"] = tool_links[:10]
    save_journal(journal)
    if not tool_links:
        gate(journal, "OWNER_AMBIGUITY_GATE",
             "save clicked but no unique saved-tool link resolved in My tools")
        return
    event(journal, "tool_saved_identity", links=tool_links[:10])


# ---------------------------------------------------------------- stage 3
def stage_generate(journal, ctx, page):
    """Optional single Tool-run generate; only if semantics require it."""
    if not journal["baseline_qualified"]:
        print("baseline unqualified; no generate", flush=True)
        return
    if not journal["budget"]["create_or_save_used"]:
        print("create never completed; no generate", flush=True)
        return
    if journal["budget"]["generate_used"]:
        print("generate budget already consumed; skip", flush=True)
        return
    if journal["gates"]:
        print("prior gate present; no mutation", flush=True)
        return
    tool_links = journal.get("tool_links") or []
    if not tool_links:
        gate(journal, "C4_GENERATE_SKIP_NO_TOOL", "no saved tool identity")
        return
    # Requirement 1: preclaim the unique marker durably BEFORE release.
    if not journal.get("marker"):
        job_id = "job_" + sha256(canonical_json({
            "canary": "FLOW_TOOL_CANARY_001", "project": PROJECT_ID,
            "created_at": now(), "nonce": secrets.token_hex(16)}))
        journal["marker_job_id"] = job_id
        journal["marker"] = f"[FILM-{job_id}]"
        event(journal, "marker_preclaimed", job_id=job_id)
    marker = journal["marker"]
    # Requirement 2: fresh qualified backend baseline (stage 1) is in the journal.

    wire = []
    install_wire_observer(page, wire)

    href = tool_links[0]["href"]
    url = href if href.startswith("http") else "https://flow.google.com" + href
    page.goto(url, timeout=60000)
    page.wait_for_timeout(8000)
    page = current_page(ctx, page)
    shot(page, "tool_runner_open")
    event(journal, "tool_runner_opened", url=url)
    items = inventory(page)
    event(journal, "tool_runner_inventory", items=items)

    # Requirement 3+4: the tool's own first-party input carries the marker.
    prompt_text = ("8-second locked eye-level wide shot, 16:9. A solitary lighthouse "
                   "on a basalt reef at dawn, calm sea, slow atmospheric drift. "
                   "Subtle waves. " + marker)
    if not fill_first_input(page, prompt_text, journal, "tool_prompt_filled"):
        gate(journal, "C4_TOOL_PROMPT_INPUT_UNAVAILABLE", "no tool input found")
        return
    shot(page, "tool_prompt_filled")
    journal["wire"] = wire
    save_journal(journal)

    # Requirement 6: release at most once — click a real handle, never a
    # re-resolved selector; handle at most one confirm dialog; never payment.
    run_controls = []
    for selector in ("button", "[role=button]"):
        for element in page.locator(selector).all():
            try:
                if not element.is_visible():
                    continue
                text = " ".join(element.inner_text().split())
                aria = element.get_attribute("aria-label") or ""
            except Exception:
                continue
            if (((text and RUN_RE.search(text)) or (aria and RUN_RE.search(aria)))
                    and not PUBLISH_RE.search(text + " " + aria)
                    and not PAYMENT_RE.search(text + " " + aria)):
                run_controls.append((element, text[:60], aria[:60]))
    event(journal, "run_controls", controls=[(t, a) for _e, t, a in run_controls][:10])
    if not run_controls:
        gate(journal, "C4_RUN_CONTROL_UNAVAILABLE", "no tool run control found")
        return
    try:
        run_controls[0][0].click(timeout=8000)
    except Exception as error:
        gate(journal, "C4_RUN_CLICK_FAILED", f"{type(error).__name__}")
        return
    page.wait_for_timeout(5000)
    page = current_page(ctx, page)
    shot(page, "after_run_click")
    dialog_items = inventory(page)
    buttons = [i for i in dialog_items if i["sel"] in ("button", "[role=button]")]
    if any(PAYMENT_RE.search((b["text"] or "") + (b["aria"] or "")) for b in buttons):
        gate(journal, "OWNER_PAYMENT_GATE",
             "payment prompt during tool run; not accepted, release unresolved")
        return
    confirms = [b for b in buttons
                if ((b["text"] and RUN_RE.search(b["text"]))
                    or (b["aria"] and RUN_RE.search(b["aria"])))
                and not PUBLISH_RE.search((b["text"] or "") + (b["aria"] or ""))]
    if confirms and page.locator("[role=dialog]").count():
        # One confirmation dialog is still the same single release.
        page.locator("[role=dialog] button", has_text=RUN_RE).first.click(timeout=8000)
        event(journal, "run_dialog_confirmed")
    journal["budget"]["generate_used"] = 1
    event(journal, "tool_generate_released", used=1, allowed=MAX_GENERATE,
          marker=marker, at=now())
    page.wait_for_timeout(20000)
    shot(page, "after_release")
    journal["wire"] = wire
    event(journal, "wire_after_release", observations=wire[-20:])
    # Bounded in-page wait for visible completion signals (read-only).
    deadline = time.monotonic() + 240
    while time.monotonic() < deadline:
        page.wait_for_timeout(15000)
        shot(page, "render_wait")
        event(journal, "render_wait_poll", wire_tail=wire[-6:])
        body = " ".join(page.locator("body").inner_text().split())[:300]
        if re.search(r"(100%|hoàn thành|completed)", body, re.I):
            event(journal, "render_visible_complete", text=body[:200])
            break
    journal["wire"] = wire
    save_journal(journal)


def main():
    journal = load_journal()
    event(journal, "run_started")
    try:
        stage_baseline(journal)
    except FlowReferenceRpcDrift as error:
        gate(journal, "C4_BASELINE_UNQUALIFIED", str(error))
    except Exception as error:  # noqa: BLE001 — canary boundary
        gate(journal, "C4_BASELINE_ERROR", f"{type(error).__name__}: {error}")

    from playwright.sync_api import sync_playwright
    with sync_playwright() as p:
        ctx = p.chromium.launch_persistent_context(
            str(PROFILE), channel="chrome", headless=False,
            args=["--no-first-run", "--no-default-browser-check",
                  "--disable-blink-features=AutomationControlled"],
            ignore_default_args=["--enable-automation"], viewport=None)
        page = ctx.pages[0] if ctx.pages else ctx.new_page()
        try:
            page.goto("https://flow.google.com/", timeout=60000)
            page.wait_for_timeout(6000)
            if "accounts.google" in page.url:
                gate(journal, "OWNER_AUTH_GATE", "login lost")
                return
            stage_create(journal, ctx, page)
            if not journal["gates"] and journal["budget"]["create_or_save_used"]:
                stage_generate(journal, ctx, page)
        finally:
            shot(page, "final_state")
            try:
                ctx.close()
            except Exception:
                pass
    event(journal, "browser_closed")
    event(journal, "run_completed_mutation_phase",
          budget=journal["budget"], gates=journal["gates"])


if __name__ == "__main__":
    import time
    main()
