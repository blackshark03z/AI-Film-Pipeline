"""Pure rules that bind a new Flow video tile to the prompt that was sent (P12-01).

Why: Omni Flash answers on tiny acknowledgement responses, so the network never
holds the prompt (P3-05 attempts 1-3). Thumbnail tokens are also unstable: a
lazy tile shows no ``src`` until it scrolls in, so an OLD clip can look "new".

Verified live on film04 (read-only): a video tile has no media id in the DOM,
but its detail page (``/edit/<media id>``) shows the media id in the URL and the
full prompt text. Binding therefore uses:

  1. the multiset of tile titles (``aria-label``) before and after the send;
     exactly one title must be new (a count, never a position);
  2. the candidate's detail page must contain the whole sent prompt;
  3. its media id must not be a known one.

Anything else is UNBOUND or AMBIGUOUS. No network data is needed.
"""
from __future__ import annotations

import re
from collections import Counter

_UUID = re.compile(r"/edit/([0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12})", re.I)


def norm(text: str) -> str:
    """Collapse all whitespace so line wrapping never decides a match."""
    return " ".join((text or "").split())


def media_id_from_url(url: str) -> str | None:
    m = _UUID.search(url or "")
    return m.group(1).lower() if m else None


def new_titles(before: list[str], after: list[str]) -> list[str]:
    """Titles present more often after the send than before (multiset diff)."""
    diff = Counter(after) - Counter(before)
    return sorted(diff.elements())


def prompt_on_page(prompt: str, page_text: str) -> bool:
    """The page holds the WHOLE sent prompt; a truncated copy is not a match."""
    p = norm(prompt)
    return bool(p) and p in norm(page_text)


def decide(before: list[str], after: list[str], details: dict[str, dict],
           prompt: str, known_media_ids: set[str] | None = None) -> dict:
    """Return {"result": "BOUND"|"UNBOUND"|"AMBIGUOUS", "title", "media_id", "why"}.

    ``details`` maps a title to ``{"url": ..., "text": ...}`` read from that
    tile's detail page; only titles from ``new_titles`` need an entry.
    """
    known = {k.lower() for k in (known_media_ids or set())}
    new = new_titles(before, after)
    if len(after) != len(before) + len(new) or len(Counter(before) - Counter(after)):
        return {"result": "AMBIGUOUS", "why": "tiles disappeared or were replaced"}
    if not new:
        return {"result": "UNBOUND", "why": "no new tile"}
    if len(new) > 1:
        return {"result": "AMBIGUOUS", "why": f"{len(new)} new tiles"}
    title = new[0]
    d = details.get(title)
    if not d:
        return {"result": "UNBOUND", "title": title, "why": "no detail page read"}
    mid = media_id_from_url(d.get("url", ""))
    if not mid:
        return {"result": "UNBOUND", "title": title, "why": "no media id in detail URL"}
    if mid in known:
        return {"result": "AMBIGUOUS", "title": title, "media_id": mid,
                "why": "media id was already known"}
    if not prompt_on_page(prompt, d.get("text", "")):
        return {"result": "UNBOUND", "title": title, "media_id": mid,
                "why": "detail page does not hold the whole sent prompt"}
    return {"result": "BOUND", "title": title, "media_id": mid,
            "binding": "DETAIL_PROMPT_MATCH", "why": "one new tile, prompt equal"}
