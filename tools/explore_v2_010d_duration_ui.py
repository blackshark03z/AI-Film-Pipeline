"""V2-010D: READ-ONLY video-mode UI exploration — find the duration control.

No dispatch: navigation + click 動画を作成 + DOM snapshot only. The run
asserts ZERO /chat/completion POSTs during the whole session.
"""
from __future__ import annotations

import asyncio
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
sys.path.insert(0, str(ROOT / "src"))

from dola_010c_browser_adapter import DolaBrowserAdapter, SEEDANCE_CONVERSATION_ID
from dola_010c_session import PKG


def utcnow() -> str:
    return datetime.now(timezone.utc).isoformat()


async def main() -> int:
    run_id = "dur_" + datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S")
    adapter = DolaBrowserAdapter(run_id=run_id)
    await adapter.open()
    result: dict = {"run_id": run_id, "started_at": utcnow()}
    try:
        await adapter.goto_conversation(SEEDANCE_CONVERSATION_ID)
        before_posts = [e for e in adapter.capture.recent
                        if e.get("kind") == "REQ" and
                        "/chat/completion" in (e.get("url") or "")]

        # click video mode and snapshot the composer area
        mode = await adapter.enable_video_mode()
        await adapter.page.wait_for_timeout(2000)

        snapshot = await adapter.page.evaluate(
            """() => {
                const els = [...document.querySelectorAll(
                    'button, [role=button], [role=radio], [role=option], ' +
                    'span, div, li, [class*=chip], [class*=duration]')];
                const rows = [];
                for (const el of els) {
                    const t = (el.innerText || '').trim();
                    if (!t || t.length > 30) continue;
                    const r = el.getBoundingClientRect();
                    if (r.width === 0 || r.height === 0) continue;
                    if (r.top < window.innerHeight - 260) continue; // composer area only
                    rows.push({
                        text: t.slice(0, 30),
                        tag: el.tagName.toLowerCase(),
                        cls: String(el.className || '').slice(0, 90),
                        aria: el.getAttribute && el.getAttribute('aria-label'),
                        selected: el.className && String(el.className)
                            .match(/selected|active|checked/) !== null,
                        rect: [Math.round(r.left), Math.round(r.top),
                               Math.round(r.width), Math.round(r.height)],
                    });
                }
                return rows;
            }""")
        await adapter.page.screenshot(path=str(
            PKG.parent / "quality_v2_010d_f2b_completion" / "duration_ui.png"))

        after_posts = [e for e in adapter.capture.recent
                       if e.get("kind") == "REQ" and
                       "/chat/completion" in (e.get("url") or "")]
        result.update({
            "video_mode_text": mode,
            "composer_elements": snapshot,
            "completion_posts_during_exploration": len(after_posts) -
                                                  len(before_posts),
        })
    finally:
        summary = await adapter.close(sanitize_to=None)
    result["completed_at"] = utcnow()
    result["no_dispatch_assert"] = result.get(
        "completion_posts_during_exploration") == 0
    out = PKG / "V2_010D_DURATION_UI_EXPLORATION.json"
    out.write_text(json.dumps(result, indent=1, ensure_ascii=False),
                   encoding="utf-8")
    texts = [e.get("text") for e in result.get("composer_elements", [])]
    print(json.dumps({"mode": mode,
                      "no_dispatch": result["no_dispatch_assert"],
                      "elements": len(texts)}, ensure_ascii=False))
    for t in texts:
        print(" ", t)
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
