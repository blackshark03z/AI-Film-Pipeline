"""V2-011W Phase 2+3 v2 — card-scoped UI entitlement + download correlation.

v1 lesson: page-wide label scanning matches the site's desktop-installer
button. This version scopes the control enumeration AND the download click to
the creation card that contains the <video> element.
"""
from __future__ import annotations

import asyncio
import hashlib
import json
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
sys.path.insert(0, str(ROOT / "src"))

from dola_010c_capture import NetworkCapture
from dola_010e_session_router import ACCOUNT_PROFILES

PKG = ROOT / "projects/quality_v2_011w_unwatermarked_authority"
P11D = ROOT / "projects/quality_v2_011d_world_matched_context"

CREATIONS = [
    {"label": "F3R_012", "account": "ACCOUNT_D",
     "conversation_id": "38417944671772433",
     "creation_id": "1542350901495057",
     "watermarked_asset": P11D / "assets" / "f3r_012.mp4",
     "click_download": True},
    {"label": "F1R", "account": "ACCOUNT_A",
     "conversation_id": "38417962862699025",
     "creation_id": "1546471384527889",
     "click_download": False},
    {"label": "F2A-R", "account": "ACCOUNT_A",
     "conversation_id": "38417852262252561",
     "creation_id": "1543341075843857",
     "click_download": False},
    {"label": "F2B-R", "account": "ACCOUNT_A",
     "conversation_id": "38418085966239761",
     "creation_id": "1546449850446097",
     "click_download": False},
]

CARD_CONTROLS_JS = """() => {
  const vids = Array.from(document.querySelectorAll('video'));
  if (!vids.length) return {card_found: false, controls: []};
  const vid = vids[vids.length - 1];
  let card = vid.closest('[class*=creation],[class*=video],[class*=card],[class*=message]') || vid.parentElement;
  for (let i = 0; i < 5 && card; i++) {
    if (card.querySelectorAll('button,[role=button]').length >= 1) break;
    card = card.parentElement;
  }
  if (!card) return {card_found: false, controls: []};
  const els = Array.from(card.querySelectorAll(
    'button,[role=button],a,[aria-label],[title]'));
  const seen = new Set();
  const controls = [];
  for (const el of els) {
    const lab = ((el.getAttribute('aria-label') || '') + ' ' +
                 (el.getAttribute('title') || '') + ' ' +
                 (el.innerText || '')).trim().replace(/\\s+/g, ' ').slice(0, 60);
    if (!lab || seen.has(lab)) continue;
    seen.add(lab);
    controls.push(lab);
  }
  return {card_found: true, controls};
}"""


def utcnow():
    return datetime.now(timezone.utc).isoformat()


def emit(payload):
    print(json.dumps(payload, ensure_ascii=False, default=str), flush=True)


def classify(labels):
    text = " | ".join(labels).lower()
    if re.search(r"no[- ]?watermark|without watermark|original|无水印|透かしなし", text):
        return "UI_EXPLICIT_NO_WATERMARK"
    if re.search(r"download|保存|ダウンロード", text):
        return "UI_GENERIC_DOWNLOAD"
    if not labels:
        return "NO_UI_VARIANT_CONTROL"
    return "AMBIGUOUS"


def redact_url(u: str) -> dict:
    from urllib.parse import urlparse, parse_qsl
    parsed = urlparse(u)
    params = [{"name": k,
               "value": v if k.lower() == "lr" else "<redacted>"}
              for k, v in parse_qsl(parsed.query, keep_blank_values=True)]
    return {"host": parsed.netloc, "path_head": parsed.path[:90],
            "params": params}


def lr_of(u: str):
    from urllib.parse import urlparse, parse_qsl
    for k, v in parse_qsl(urlparse(u).query):
        if k.lower() == "lr":
            return v
    return None


def corner_luma(path: Path, tag: str) -> dict:
    probe = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration",
         "-of", "csv=p=0", str(path)], capture_output=True, text=True)
    dur = float(probe.stdout.strip() or 0)
    t = max(0.0, dur * 0.5)
    tmp = path.with_name(f"{path.stem}_wmcheck_{tag}.png")
    subprocess.run(["ffmpeg", "-y", "-v", "error", "-ss", f"{t:.3f}",
                    "-i", str(path), "-frames:v", "1", str(tmp)],
                   capture_output=True)
    from PIL import Image
    im = Image.open(tmp).convert("L")
    w, h = im.size
    crop = im.crop((int(w * 0.70), int(h * 0.86), w, h))
    mean = sum(crop.getdata()) / (crop.width * crop.height)
    return {"frame_t": round(t, 3), "corner_mean_luma": round(mean, 2),
            "probe_png": str(tmp)}


async def main() -> int:
    from patchright.async_api import async_playwright
    pw = await async_playwright().start()
    ui_records = []
    correlation = None
    for account in ("ACCOUNT_D", "ACCOUNT_A"):
        targets = [c for c in CREATIONS if c["account"] == account]
        ctx = await pw.chromium.launch_persistent_context(
            str(ACCOUNT_PROFILES / account), headless=False,
            args=["--disable-blink-features=AutomationControlled",
                  "--no-first-run", "--no-default-browser-check"],
            locale="ja-JP", timezone_id="Asia/Tokyo",
            accept_downloads=True)
        page = ctx.pages[0] if ctx.pages else await ctx.new_page()
        try:
            await page.goto("https://www.dola.com/chat", timeout=60000,
                            wait_until="domcontentloaded")
            for _ in range(20):
                if await page.evaluate(
                        """() => !!(document.querySelector('textarea')
                                || document.querySelector('[contenteditable="true"]'))"""):
                    break
                await page.wait_for_timeout(1000)
            for c in targets:
                await page.goto(
                    f"https://www.dola.com/chat/{c['conversation_id']}",
                    timeout=60000, wait_until="domcontentloaded")
                await page.wait_for_timeout(6000)
                for _ in range(6):
                    await page.keyboard.press("End")
                    await page.wait_for_timeout(700)
                # hover the video to reveal its control overlay
                try:
                    await page.locator("video").last.hover(timeout=5000)
                    await page.wait_for_timeout(1200)
                except Exception:
                    pass
                card = await page.evaluate(CARD_CONTROLS_JS)
                labels = card.get("controls", [])
                shot = PKG / "owner_review_011w" / f"ui_{c['label']}_card.png"
                shot.parent.mkdir(parents=True, exist_ok=True)
                await page.screenshot(path=str(shot))
                classification = classify(labels)
                ui_records.append({
                    "label": c["label"],
                    "conversation_id": c["conversation_id"],
                    "creation_id": c["creation_id"],
                    "card_found": card.get("card_found", False),
                    "card_control_labels": labels,
                    "classification": classification,
                    "screenshot": str(shot)})
                emit({"event": "ui_inspected", "label": c["label"],
                      "card_found": card.get("card_found"),
                      "classification": classification,
                      "labels": labels[:10]})

                if c["click_download"] and classification in (
                        "UI_GENERIC_DOWNLOAD", "UI_EXPLICIT_NO_WATERMARK",
                        "AMBIGUOUS"):
                    capture = NetworkCapture(ctx, page, "v011w_dl2_" +
                                             datetime.now(timezone.utc)
                                             .strftime("%Y%m%dT%H%M%S"))
                    await capture.start()
                    dl_dir = PKG / "downloads"
                    dl_dir.mkdir(exist_ok=True)
                    pending = []

                    def _on_download(d):
                        pending.append(d)

                    page.on("download", _on_download)
                    clicked = await page.evaluate(
                        """() => {
                          const vids = Array.from(document.querySelectorAll('video'));
                          if (!vids.length) return 'no_video';
                          const vid = vids[vids.length - 1];
                          let card = vid.closest('[class*=creation],[class*=video],[class*=card],[class*=message]') || vid.parentElement;
                          for (let i = 0; i < 5 && card; i++) {
                            if (card.querySelectorAll('button,[role=button]').length >= 1) break;
                            card = card.parentElement;
                          }
                          if (!card) return 'no_card';
                          const els = Array.from(card.querySelectorAll(
                            'button,[role=button],a,[aria-label],[title]'));
                          const dl = els.find(el => {
                            const lab = ((el.getAttribute('aria-label')||'')
                              + ' ' + (el.getAttribute('title')||'') + ' '
                              + (el.innerText||'')).toLowerCase();
                            return /download|ダウンロード|保存/.test(lab);
                          });
                          if (!dl) return 'no_download_control';
                          dl.scrollIntoView({block: 'center'});
                          dl.click();
                          return 'clicked';
                        }""")
                    emit({"event": "download_clicked", "result": clicked})
                    await page.wait_for_timeout(12000)
                    page.remove_listener("download", _on_download)
                    saved = []
                    for d in pending:
                        try:
                            target = dl_dir / d.suggested_filename
                            await d.save_as(str(target))
                            saved.append({"url": d.url,
                                          "suggested_filename":
                                              d.suggested_filename,
                                          "saved_to": str(target)})
                        except Exception as e:
                            saved.append({"url": d.url,
                                          "save_error":
                                              type(e).__name__})
                    cap_result = await capture.stop()
                    correlation = {
                        "creation_id": c["creation_id"],
                        "label": c["label"],
                        "click_result": clicked,
                        "n_download_events": len(pending),
                        "provider_issued_download_urls": [
                            {**redact_url(d["url"]),
                             "lr": lr_of(d["url"]),
                             "suggested_filename": d["suggested_filename"]}
                            for d in saved],
                    }
                    files = [Path(s["saved_to"]) for s in saved
                             if s.get("saved_to") and Path(s["saved_to"]).exists()]
                    if files:
                        f = files[0]
                        fsha = hashlib.sha256(f.read_bytes()).hexdigest()
                        correlation["downloaded_asset"] = {
                            "path": str(f), "sha256": fsha,
                            "size": f.stat().st_size,
                            "watermark_probe": corner_luma(f, "candidate"),
                            "watermarked_reference_probe": corner_luma(
                                Path(c["watermarked_asset"]), "reference"),
                            "url_lr": lr_of(saved[0]["url"])}
                    emit({"event": "correlation_done",
                          "n_downloads": len(pending),
                          "saved": len(files),
                          "lr": [lr_of(s["url"]) for s in saved]})
        finally:
            await ctx.close()
    doc = {
        "version": "v2-011w-ui-entitlement-v2",
        "checkpoint": "V2011W_P2_P3_UI_ENTITLEMENT",
        "built_at": utcnow(),
        "mode": "READ-ONLY card-scoped UI inspection on all four creations; "
                "ONE provider-download click (F3R_012 card) with network "
                "capture — a normal asset download of an existing creation",
        "v1_note": "v1 matched the site-wide desktop-installer button; v2 "
                   "scopes to the creation card containing the <video>",
        "creations": ui_records,
        "network_correlation": correlation,
    }
    PKG.mkdir(parents=True, exist_ok=True)
    (PKG / "V2_011W_UI_ENTITLEMENT.json").write_text(
        json.dumps(doc, indent=1, ensure_ascii=False), encoding="utf-8")
    print("wrote V2_011W_UI_ENTITLEMENT.json")
    await pw.stop()
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
