"""One self-contained HTML page the Owner can decide from: gates and why, storyboard, budget, risks and fallbacks, rights
still pending, takes waiting for a human review. No external assets (frames are inlined, downscaled JPEG), no scripts.

It reports; it never approves, accepts or changes the package. A rehearsal package is stamped REHEARSAL — synthetic.
"""
from __future__ import annotations

import base64
import html
import io
import json
from pathlib import Path
from typing import Any

from film_pipeline.production import takes as T
from film_pipeline.production.planning import planning_report
from film_pipeline.production.rehearsal import STAMP, is_rehearsal
from film_pipeline.production.report import status_report

FRAME_WIDTH = 360
CSS = """body{font:15px/1.45 system-ui,sans-serif;margin:24px auto;max-width:980px;padding:0 16px;color:#1b1b1f;background:#fff}
h1{font-size:24px;margin:0 0 4px}h2{font-size:17px;margin:28px 0 8px;border-bottom:1px solid #ddd;padding-bottom:4px}
table{border-collapse:collapse;width:100%}td,th{border:1px solid #ddd;padding:5px 8px;text-align:left;vertical-align:top}
th{background:#f3f3f5}.PASS{color:#0a6b2d}.BLOCK,.NOT_RUN{color:#a40e26}.OWNER_PENDING{color:#8a5a00}
.stamp{background:#a40e26;color:#fff;padding:4px 10px;display:inline-block;font-weight:600}
.next{background:#eef4ff;border-left:4px solid #2f5fd0;padding:8px 12px;margin:12px 0}
.grid{display:flex;flex-wrap:wrap;gap:10px}.grid figure{margin:0;width:FRAMEpx}.grid img{width:100%;display:block}
figcaption{font-size:12px;color:#555}small{color:#555}
@media (prefers-color-scheme:dark){body{background:#17171a;color:#e8e8ec}th{background:#26262b}td,th{border-color:#3a3a40}
.next{background:#1c2438}.PASS{color:#6fd48f}.BLOCK,.NOT_RUN{color:#ff8a9a}.OWNER_PENDING{color:#f0c060}}""".replace("FRAME", str(FRAME_WIDTH))


def _e(value: Any) -> str:
    return html.escape(str(value))


def _frame(path: Path) -> str:
    """A data: URI of a downscaled JPEG of the image, or '' when it cannot be read."""
    try:
        from PIL import Image
        with Image.open(path) as im:
            im = im.convert("RGB")
            im.thumbnail((FRAME_WIDTH * 2, FRAME_WIDTH * 2))
            buf = io.BytesIO()
            im.save(buf, "JPEG", quality=70)
    except Exception:  # noqa: BLE001 - a frame we cannot read is shown as missing, not fatal
        return ""
    return "data:image/jpeg;base64," + base64.b64encode(buf.getvalue()).decode("ascii")


def _table(head: list[str], rows: list[list[Any]]) -> str:
    if not rows:
        return "<p><small>none</small></p>"
    cells = "".join(f"<tr>{''.join(f'<td>{c}</td>' for c in row)}</tr>" for row in rows)
    return f"<table><tr>{''.join(f'<th>{_e(h)}</th>' for h in head)}</tr>{cells}</table>"


def _awaiting(pkg: Any) -> list[list[Any]]:
    root = Path(pkg.root)
    rows = []
    for t in T.load_log(root, pkg.header.film_id).takes:
        if t.status not in ("GENERATED", "INCOMPLETE"):
            continue
        sheet = (T.takes_dir(root) / t.review_file) if t.review_file else None
        shown = _e(sheet) if sheet and sheet.is_file() else "<small>no sheet yet: film.py review --film F</small>"
        rows.append([_e(t.take_id), _e(t.generation_id), _e(t.status), _e(t.output_file), shown])
    return rows


def build(pkg: Any, out: Path | None = None) -> dict[str, Any]:
    """Write the page (default `media/review/index.html`) and return where and what it holds."""
    root = Path(pkg.root)
    out = Path(out) if out else root / "media" / "review" / "index.html"
    status = status_report(pkg)
    plan = planning_report(pkg) if pkg.typed.get("shots") is not None and pkg.typed.get("preprod") is not None else None
    parts = [f"<h1>{_e(pkg.header.title)}</h1><small>{_e(pkg.header.film_id)} · profile {_e(pkg.header.profile)}</small>"]
    if is_rehearsal(root):
        parts.append(f'<p><span class="stamp">{_e(STAMP)}</span></p>')
    parts.append(f'<div class="next"><b>Next action:</b> {_e(status["next_action"])}<br>'
                 f'<small>Runbook: {_e(status["runbook"])}</small></div>')
    parts.append("<h2>Gates</h2>" + _table(["Gate", "Name", "Status", "Why"], [
        [_e(g), _e(v["name"]), f'<span class="{_e(v["status"])}">{_e(v["status"])}</span>', _e("; ".join(v["first"]))]
        for g, v in status["gates"].items()]))
    frames = []
    for png in sorted((root / "media" / "plan" / "storyboard").glob("*.png")):
        uri = _frame(png)
        img = f'<img src="{uri}" alt="{_e(png.stem)}">' if uri else "<small>unreadable</small>"
        frames.append(f"<figure>{img}<figcaption>{_e(png.stem)}</figcaption></figure>")
    animatic = root / "media" / "animatic.mp4"
    parts.append("<h2>Storyboard</h2>" + (f'<div class="grid">{"".join(frames)}</div>' if frames else "<p><small>no storyboard frames: film.py plan</small></p>")
                 + f"<p><small>Animatic: {_e(animatic) if animatic.is_file() else 'not built (film.py animatic)'}</small></p>")
    cr = status["credits"]
    budget = plan["budget"] if plan else {}
    parts.append("<h2>Budget</h2>" + _table(["Generations", "Expected credits", "High", "Cap (expected x factor)", "Owner estimate", "Spent"], [[
        _e(budget.get("generations", "")), _e(budget.get("expected_credits", "")), _e(budget.get("high_credits", "")),
        _e(budget.get("cap_credits", "")), _e(cr.get("estimate")), _e(cr.get("spent"))]])
        + "".join(f'<p class="{_e(f["severity"])}">{_e(f["check"])}: {_e(f["detail"])}</p>' for f in budget.get("findings", [])))
    parts.append("<h2>Risks and fallbacks</h2>" + _table(["Shot", "Kind", "Level", "Detail", "Fallback"], [
        [_e(r["generation_id"]), _e(r["kind"]), _e(r["level"]), _e(r["detail"]), _e(r["fallback"] or "— none —")]
        for r in (plan["risks"] if plan else [])]))
    parts.append("<h2>Rights waiting for the Owner</h2>" + _table(["Decision"], [[_e(d)] for d in status["rights"]["pending"] + status["rights"]["sound"]]))
    parts.append("<h2>Takes awaiting review</h2>" + _table(["Take", "Shot", "Status", "File", "QC sheet"], _awaiting(pkg)))
    parts.append(f"<p><small>Generated by film.py reviewpack. Technical report only: it approves nothing "
                 f"(OWNER_GO_LIVE is read from the backlog by generate, never from here).</small></p>")
    page = (f'<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">'
            f"<title>Review pack — {_e(pkg.header.title)}</title><style>{CSS}</style></head><body>{''.join(parts)}</body></html>")
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(page, encoding="utf-8")
    return {"page": str(out), "bytes": len(page.encode("utf-8")), "frames": len(frames), "next_action": status["next_action"],
            "runbook": status["runbook"]}
