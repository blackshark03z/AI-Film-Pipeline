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
matches). P17-07: NOT_IN_GALLERY at least SETTLE_S after the send ended adds ``provider_no_clip: true``; generate
then counts that send as FLOW_FAILED (credits spent, send cap not used). Never reads cookies, never closes the browser, persists no signed URL or token.
"""
from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import flow_bind as fb  # noqa: E402
import flow_send as fs  # noqa: E402
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))
from film_pipeline.production.runtime import atomic_json  # noqa: E402


def _sha(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def known_ids(manifests: Path | None, out_dir: Path, skip: frozenset[str] = frozenset()) -> set[str]:
    """Media id tails of registered take manifests plus the media ids of earlier BOUND reconcile results.

    P17-04: results of the receipts in `skip` (the ones being reconciled now) are left out, so a re-run with
    --download can bind the same clip again instead of hiding it from itself."""
    known: set[str] = set()
    if manifests and Path(manifests).is_dir():
        for m in sorted(Path(manifests).glob("*.take.json")):
            if m.name.removesuffix(".take.json") in skip:
                continue
            tail = json.loads(m.read_text(encoding="utf-8")).get("media_id_tail")
            if tail:
                known.add(tail)
    if out_dir.is_dir():
        for r in sorted(out_dir.glob("*.reconcile.json")):
            body = json.loads(r.read_text(encoding="utf-8"))
            if body.get("receipt_id") in skip:
                continue
            if body.get("result") == "BOUND" and body.get("media_id"):
                known.add(body["media_id"])
    return known


SETTLE_S = 600   # P17-07: a clip not in the gallery 10 min after its send ended is not coming
MIN_SCAN = 6     # ... and only when at least this many newest detail pages were read


def settled(manifest: Path, now: datetime | None = None) -> bool:
    """True when the send's take manifest says it finished SETTLE_S or more ago (film05: Flow jobs that vanished)."""
    try:
        record = json.loads(manifest.read_text(encoding="utf-8"))
        if record.get("result") == fs.ACCOUNT_WARNING:
            return False   # gallery absence cannot clear a stop for an account warning
        sent = record.get("submission_phase") in {"SUBMITTING", "SUBMITTED"}   # PREPARING never pressed Enter
        stamp = record.get("finished") or (record.get("submitted_at") or record.get("submitting_at") if sent else None)
        finished = datetime.fromisoformat(stamp)
    except (OSError, ValueError, KeyError, TypeError):
        return False
    now = now or datetime.now(finished.tzinfo)   # the manifest writes local naive time; an offset is honoured too
    if (now.tzinfo is None) != (finished.tzinfo is None):
        return False
    return (now - finished).total_seconds() >= SETTLE_S


def load_receipt(receipts: Path, rid: str, prompts: Path) -> tuple[dict, str | None, str | None]:
    """(receipt, prompt, problem): the prompt only when its hash is the one the receipt recorded."""
    receipt = json.loads((receipts / f"{rid}.intent.json").read_text(encoding="utf-8"))
    snapshot = receipts / f"{rid}.prompt.txt"
    path = snapshot if snapshot.is_file() else prompts / f"{receipt['generation_id']}.txt"
    if not path.is_file():
        return receipt, None, f"prompt file {path.name} not found"
    prompt = path.read_text(encoding="utf-8").strip()
    if _sha(prompt) != receipt.get("prompt_sha256"):
        return receipt, None, "PROMPT_CHANGED: the plan prompt is not the one that was sent"
    return receipt, prompt, None


def bind_receipt(prompt: str, details: list[dict], known: set[str], context: dict) -> dict:
    if context.get("prompt_sha256") and context["prompt_sha256"] != _sha(prompt):
        return {"result": "NATIVE_PROMPT_MISMATCH"}
    excluded = known | set(context.get("before_ids", []))
    own = context.get("own_tile_at_submit", {}).get("media_id")
    if own:
        excluded |= {mid for d in details if (mid := fb.media_id_from_url(d.get("url", ""))) and not fb.is_known(mid, {own})}
    return fb.reconcile(prompt, details, excluded)


async def scan_gallery(page, n: int) -> list[dict]:
    home = page.url
    details: list[dict] = []
    for i in range(n):
        d = await fs.read_nth_detail(page, i, home)
        if d is None:
            break
        details.append(d)
    return details


def exhaustion_confirmed(first: list[dict], second: list[dict]) -> bool:
    """A short scan counts as the whole gallery only if a fresh rescan returns the same ordered media ids."""
    a = [fb.media_id_from_url(d.get("url", "")).lower() for d in first]
    b = [fb.media_id_from_url(d.get("url", "")).lower() for d in second]
    return bool(a) and all(a) and a == b


async def confirm_exhausted(page, first: list[dict], requested: int, home: str) -> bool:
    """Short first scan (it ran out of videos before `requested`): reload the project, let the grid render, rescan.
    A transient short read (grid still lazy-loading) must never authorise a provider-failure verdict and a resend."""
    if len(first) >= requested:
        return False
    await page.goto(home, timeout=45000)
    await page.wait_for_timeout(6000)
    return exhaustion_confirmed(first, await scan_gallery(page, requested))


def complete_negative_scan(details: list[dict], home: str, exhausted: bool = False) -> bool:
    """Full scan: MIN_SCAN newest pages read, or the gallery ran out of videos first (a young project holds fewer)."""
    prefix = home.split('/edit/')[0].split('?')[0].rstrip('/') + '/edit/'
    ids = [fb.media_id_from_url(d.get("url", "")) for d in details]
    return ((len(ids) >= MIN_SCAN or (exhausted and ids)) and all(ids) and len({m.lower() for m in ids}) == len(ids)
            and all(d.get("url", "").startswith(prefix) and d.get("text", "").strip() for d in details))


JS_MARKED_CENTRE = r"""() => { const c = document.querySelector('[data-vp-n]');
    if (!c) return null; c.scrollIntoView({block: 'center'});
    const r = c.getBoundingClientRect(); return [r.x + r.width / 2, r.y + r.height / 2] }"""

JS_CAPTURE_AND_OPEN = r"""() => {
    const c = document.querySelector('[data-vp-n]');
    const tile = c && c.querySelector('flow-video-tile');
    const video = c && c.querySelector('video');
    const src = video && (video.currentSrc || video.src);
    if (!tile || !src) return null;
    tile.click();
    return src;
}"""


async def download_nth(page, ctx, n: int, out: Path, *, media_id: str, prompt: str) -> str | None:
    """Bind the captured player URL to the identity opened by that same tile activation."""
    home = page.url
    await page.evaluate(fs.JS_TOP)
    await page.wait_for_timeout(500)
    if not await page.evaluate(fs.JS_MARK_NTH, n):
        return "TILE_NOT_FOUND"
    xy = await page.evaluate(JS_MARKED_CENTRE)
    if not xy:
        return "TILE_NOT_FOUND"
    await page.mouse.move(*xy)
    await page.wait_for_timeout(2500)
    src = await page.evaluate(JS_CAPTURE_AND_OPEN)
    if not src:
        return "NO_VIDEO_UNDER_TILE"
    try:
        await page.wait_for_timeout(3500)
        prefix = home.split('/edit/')[0].split('?')[0].rstrip('/') + '/edit/'
        if (fb.media_id_from_url(page.url) != media_id or not page.url.startswith(prefix)
                or not fb.prompt_on_page(prompt, await page.evaluate("document.body.innerText"))):
            return "DOWNLOAD_IDENTITY_MISMATCH"
        resp = await ctx.request.get(src, timeout=300000)
        ctype = resp.headers.get("content-type", "")
        data = await resp.body()
    except Exception as exc:
        return f"DOWNLOAD_FAILED {type(exc).__name__}"  # signed URLs never enter the receipt/error text
    finally:
        await page.goto(home, timeout=45000)
        await page.wait_for_timeout(1000)
    if resp.status != 200 or not ctype.startswith("video/") or not data:
        return f"DOWNLOAD_FAILED {resp.status} {ctype}"
    out.parent.mkdir(parents=True, exist_ok=True)
    if out.exists():
        return None if hashlib.sha256(out.read_bytes()).digest() == hashlib.sha256(data).digest() else "OUTPUT_CONFLICT"
    temporary = out.with_suffix(".download.tmp")
    temporary.write_bytes(data)
    temporary.replace(out)
    return None


async def run(args) -> dict[str, dict]:
    from patchright.async_api import async_playwright
    receipts, out_dir = Path(args.receipts), Path(args.out_dir)
    film = Path(args.takes_index).parent.parent
    manifests = Path(args.manifests) if args.manifests else film / "media" / "takes"
    prompts = Path(args.prompts) if args.prompts else film / "media" / "plan" / "prompts"
    out_dir.mkdir(parents=True, exist_ok=True)
    known = known_ids(manifests, out_dir, frozenset(args.ids))
    results: dict[str, dict] = {}
    todo: dict[str, tuple[str, dict]] = {}
    projects: set[str] = set()
    pinned = fs.flow_project()
    for rid in args.ids:
        receipt, prompt, problem = load_receipt(receipts, rid, prompts)
        wrong_target = fs._runtime().flow_target_problem(receipt)   # another profile / project: never scan it here
        if wrong_target:
            results[rid] = {"result": "WRONG_PROFILE", "why": wrong_target}
        elif problem:
            results[rid] = {"result": "NO_PROMPT", "why": problem}
        else:
            native = manifests / f"{rid}.take.json"
            context = json.loads(native.read_text(encoding="utf-8")) if native.is_file() else {}
            targets = {p for p in (pinned, receipt.get("project"), context.get("project")) if p}
            if len(targets) > 1:
                results[rid] = {"result": "WRONG_PROJECT"}
                continue
            projects.update(targets)
            todo[rid] = (prompt, context)
    if len(projects) > 1:
        raise ValueError("Flow reconciliation needs one project per call")
    if todo:
        pw = await async_playwright().start()
        try:
            browser = await pw.chromium.connect_over_cdp(fs.cdp_endpoint(), timeout=30000)
            ctx = browser.contexts[0]
            page = fs.select_flow_page(ctx.pages, next(iter(projects), pinned))
            if page is None:   # no tab of the pinned project on this profile: nothing is scanned
                for rid in todo:
                    results[rid] = {"result": "NO_FLOW_TAB"}
            else:
                home = page.url
                project = fs.flow_project_id(home)
                await page.set_viewport_size({"width": 1280, "height": 720})
                await page.keyboard.press("Escape")
                details = await scan_gallery(page, args.scan)   # once, shared by every receipt
                exhausted = await confirm_exhausted(page, details, args.scan, home)
                for rid, (prompt, context) in todo.items():
                    native = manifests / f"{rid}.take.json"
                    if fs.flow_project_id(page.url) != project:
                        results[rid] = {"result": "WRONG_PROJECT"}
                        continue
                    res = bind_receipt(prompt, details, known, context)
                    res["scanned"] = len(details)
                    res.update(prompt_sha256=_sha(prompt), project=context.get("project"),
                               scan_verified=complete_negative_scan(details, page.url, exhausted=exhausted))
                    if native.is_file():
                        res["native_sha256"] = hashlib.sha256(native.read_bytes()).hexdigest()
                    if res["result"] == "BOUND":
                        known.add(res["media_id"])   # a clip binds to one receipt only
                        if args.download:
                            failed = await download_nth(page, ctx, res["index"], out_dir / f"{rid}.mp4",
                                                        media_id=res["media_id"], prompt=prompt)
                            res["download"] = failed or "SAVED"
                            if not failed:
                                res["sha256"] = hashlib.sha256((out_dir / f"{rid}.mp4").read_bytes()).hexdigest()
                                res["prompt_sha256"] = _sha(prompt)
                    results[rid] = res
        finally:
            await pw.stop()   # disconnect only; browser and tab stay open
    for rid, res in results.items():
        # Codex review: only a full scan proves the clip is gone (a short or failed scan could hide it)
        if (res["result"] == "NOT_IN_GALLERY" and res.get("scan_verified") and res.get("project")
                and settled(manifests / f"{rid}.take.json")):
            res["provider_no_clip"] = True
        atomic_json(out_dir / f"{rid}.reconcile.json", {"receipt_id": rid, **res})
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
