"""Reconcile sends that ended UNBOUND / AMBIGUOUS: find their clip in the Flow gallery by prompt text (read-only).

Usage (repo root; LIVE, needs the Flow tab on CDP 127.0.0.1:9333 -- 0 credits, nothing is generated):
  python tools/drama_flow_ui/flow_reconcile.py --receipts films/F/takes/intents --takes-index films/F/takes/index.json
         --ids SC01_g1_t1 SC01_g1_t2 --out-dir DIR [--scan 30] [--download] [--manifests DIR] [--prompts DIR]

The first N video tiles are read ONCE (detail page: URL = media id, body = prompt) and shared by all receipts.
A receipt's prompt is its generation's plan prompt (``<prompts>/<generation_id>.txt``), used only when its sha256 equals
the receipt's ``prompt_sha256`` (a re-planned prompt is not the one that was sent). Known media ids (excluded as
candidates) come from take manifests (``media_id_tail``, 8 chars: matched by suffix) and from earlier BOUND results in
--out-dir. Writes ``<out-dir>/<receipt_id>.reconcile.json``; with --download a BOUND clip is saved as
``<receipt_id>.mp4`` so ``film.py takes --register`` registers it under the receipt's stem (which the credit ledger
matches). Never reads cookies, never closes the browser, persists no signed URL or token.
"""
from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import flow_bind as fb  # noqa: E402
import flow_send as fs  # noqa: E402


def _sha(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def known_ids(manifests: Path | None, out_dir: Path) -> set[str]:
    """Media id tails of registered take manifests plus the media ids of earlier BOUND reconcile results."""
    known: set[str] = set()
    if manifests and Path(manifests).is_dir():
        for m in sorted(Path(manifests).glob("*.take.json")):
            tail = json.loads(m.read_text(encoding="utf-8")).get("media_id_tail")
            if tail:
                known.add(tail)
    if out_dir.is_dir():
        for r in sorted(out_dir.glob("*.reconcile.json")):
            body = json.loads(r.read_text(encoding="utf-8"))
            if body.get("result") == "BOUND" and body.get("media_id"):
                known.add(body["media_id"])
    return known


def load_receipt(receipts: Path, rid: str, prompts: Path) -> tuple[dict, str | None, str | None]:
    """(receipt, prompt, problem): the prompt only when its hash is the one the receipt recorded."""
    receipt = json.loads((receipts / f"{rid}.intent.json").read_text(encoding="utf-8"))
    path = prompts / f"{receipt['generation_id']}.txt"
    if not path.is_file():
        return receipt, None, f"prompt file {path.name} not found"
    prompt = path.read_text(encoding="utf-8").strip()
    if _sha(prompt) != receipt.get("prompt_sha256"):
        return receipt, None, "PROMPT_CHANGED: the plan prompt is not the one that was sent"
    return receipt, prompt, None


async def scan_gallery(page, n: int) -> list[dict]:
    home = page.url
    details: list[dict] = []
    for i in range(n):
        d = await fs.read_nth_detail(page, i, home)
        if d is None:
            break
        details.append(d)
    return details


JS_MARKED_CENTRE = r"""() => { const c = document.querySelector('[data-vp-n]');
    if (!c) return null; c.scrollIntoView({block: 'center'});
    const r = c.getBoundingClientRect(); return [r.x + r.width / 2, r.y + r.height / 2] }"""


async def download_nth(page, ctx, n: int, out: Path) -> str | None:
    """Download the n-th video tile (gallery at scroll 0) like flow_send does; None = saved, else the failure."""
    await page.evaluate(fs.JS_TOP)
    await page.wait_for_timeout(500)
    if not await page.evaluate(fs.JS_MARK_NTH, n):
        return "TILE_NOT_FOUND"
    xy = await page.evaluate(JS_MARKED_CENTRE)
    if not xy:
        return "TILE_NOT_FOUND"
    await page.mouse.move(*xy)
    await page.wait_for_timeout(2500)
    src = await page.evaluate(fs.JS_VIDEO_AT, xy)
    if not src:
        return "NO_VIDEO_UNDER_TILE"
    resp = await ctx.request.get(src, timeout=300000)
    ctype = resp.headers.get("content-type", "")
    data = await resp.body()
    if resp.status != 200 or not ctype.startswith("video/"):
        return f"DOWNLOAD_FAILED {resp.status} {ctype}"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_bytes(data)
    return None


async def run(args) -> dict[str, dict]:
    from patchright.async_api import async_playwright
    receipts, out_dir = Path(args.receipts), Path(args.out_dir)
    film = Path(args.takes_index).parent.parent
    manifests = Path(args.manifests) if args.manifests else film / "media" / "takes"
    prompts = Path(args.prompts) if args.prompts else film / "media" / "plan" / "prompts"
    out_dir.mkdir(parents=True, exist_ok=True)
    known = known_ids(manifests, out_dir)
    results: dict[str, dict] = {}
    todo: dict[str, str] = {}
    for rid in args.ids:
        _receipt, prompt, problem = load_receipt(receipts, rid, prompts)
        if problem:
            results[rid] = {"result": "NO_PROMPT", "why": problem}
        else:
            todo[rid] = prompt
    if todo:
        pw = await async_playwright().start()
        try:
            browser = await pw.chromium.connect_over_cdp(fs.CDP, timeout=30000)
            ctx = browser.contexts[0]
            page = next(p for p in ctx.pages if "flow.google" in p.url)
            await page.set_viewport_size({"width": 1280, "height": 720})
            await page.keyboard.press("Escape")
            details = await scan_gallery(page, args.scan)   # once, shared by every receipt
            for rid, prompt in todo.items():
                res = fb.reconcile(prompt, details, known)
                res["scanned"] = len(details)
                if res["result"] == "BOUND":
                    known.add(res["media_id"])   # a clip binds to one receipt only
                    if args.download:
                        failed = await download_nth(page, ctx, res["index"], out_dir / f"{rid}.mp4")
                        res["download"] = failed or "SAVED"
                results[rid] = res
        finally:
            await pw.stop()   # disconnect only; browser and tab stay open
    for rid, res in results.items():
        (out_dir / f"{rid}.reconcile.json").write_text(json.dumps({"receipt_id": rid, **res}, indent=2),
                                                       encoding="utf-8")
    return results


def build_parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser()
    ap.add_argument("--receipts", required=True, help="intents directory (<id>.intent.json)")
    ap.add_argument("--takes-index", required=True, help="takes/index.json of the film")
    ap.add_argument("--ids", nargs="+", required=True, help="receipt ids, e.g. SC01_g1_t1")
    ap.add_argument("--scan", type=int, default=30, help="how many video tiles to read (newest first)")
    ap.add_argument("--out-dir", required=True)
    ap.add_argument("--download", action="store_true", help="save a BOUND clip as <out-dir>/<receipt_id>.mp4")
    ap.add_argument("--manifests", default="", help="dir of *.take.json (default <film>/media/takes)")
    ap.add_argument("--prompts", default="", help="dir of plan prompts (default <film>/media/plan/prompts)")
    return ap


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8")
    results = asyncio.run(run(build_parser().parse_args()))
    for rid, res in results.items():
        print(rid, res["result"], res.get("media_id", ""))


if __name__ == "__main__":
    main()
