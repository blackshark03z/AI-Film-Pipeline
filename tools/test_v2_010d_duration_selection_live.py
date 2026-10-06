"""V2-010D: read-only duration-selection mechanics test (no dispatch).

Clicks the duration chip, selects 5s, verifies the chip state, screenshots.
Asserts ZERO /chat/completion POSTs. This validates the adapter delta before
the governed F2B run.
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

from dola_010d_adapter_delta import DolaBrowserAdapter010D
from dola_010c_browser_adapter import SEEDANCE_CONVERSATION_ID

PKG = ROOT / "projects/quality_v2_010d_f2b_completion"


def utcnow() -> str:
    return datetime.now(timezone.utc).isoformat()


async def main() -> int:
    run_id = "dursel_" + datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S")
    adapter = DolaBrowserAdapter010D(run_id=run_id)
    await adapter.open()
    result: dict = {"run_id": run_id, "started_at": utcnow()}
    try:
        await adapter.goto_conversation(SEEDANCE_CONVERSATION_ID)
        mode = await adapter.enable_video_mode()
        before_posts = [e for e in adapter.capture.recent
                        if e.get("kind") == "REQ" and
                        "/chat/completion" in (e.get("url") or "")]
        chip_before = await adapter.read_duration_chip()
        selection = await adapter.select_duration(5)
        await adapter.page.wait_for_timeout(800)
        chip_after = await adapter.read_duration_chip()
        await adapter.page.screenshot(path=str(
            PKG / "duration_selected_5s.png"))
        after_posts = [e for e in adapter.capture.recent
                       if e.get("kind") == "REQ" and
                       "/chat/completion" in (e.get("url") or "")]
        result.update({
            "video_mode_text": mode,
            "chip_before": chip_before,
            "selection": selection,
            "chip_after": chip_after,
            "duration_proof_ok": chip_after == "5s",
            "completion_posts_during_exploration":
                len(after_posts) - len(before_posts),
        })
    except RuntimeError as error:
        result["error"] = str(error)
    finally:
        await adapter.close(sanitize_to=None)
    result["completed_at"] = utcnow()
    result["no_dispatch_assert"] = result.get(
        "completion_posts_during_exploration", 1) == 0
    (PKG / "V2_010D_DURATION_SELECTION_TEST.json").write_text(
        json.dumps(result, indent=1, ensure_ascii=False), encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
