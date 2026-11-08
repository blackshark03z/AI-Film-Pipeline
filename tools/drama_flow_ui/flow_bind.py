"""Pure rules that bind a new Flow video tile to the prompt that was sent (P12-01).

Why: Omni Flash answers on tiny acknowledgement responses, so the network never
holds the prompt (P3-05 attempts 1-3). Thumbnail tokens are also unstable (a
lazy tile shows no ``src`` until it scrolls in, so an OLD clip can look new) and
tile titles repeat for equal prompts (attempt 5: three clips, two titles).

What is stable, verified live on film04: a video's detail page
(``/edit/<media id>``) shows the media id in the URL and the full prompt text.

Rule (front-insertion proof, not a position guess): Flow lists the newest video
first. A send is bound only when
  1. the gallery holds exactly ONE more video than before;
  2. the video that was in front before the send is now second (same media id);
  3. the new front video has another media id;
  4. its detail page holds the WHOLE sent prompt.
Any other outcome is UNBOUND or AMBIGUOUS. No network data is needed.
"""
from __future__ import annotations

import re

_UUID = re.compile(r"/edit/([0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12})", re.I)


def norm(text: str) -> str:
    """Collapse all whitespace so line wrapping never decides a match."""
    return " ".join((text or "").split())


def media_id_from_url(url: str) -> str | None:
    m = _UUID.search(url or "")
    return m.group(1).lower() if m else None


def prompt_on_page(prompt: str, page_text: str) -> bool:
    """The page holds the WHOLE sent prompt; a truncated copy is not a match."""
    p = norm(prompt)
    return bool(p) and p in norm(page_text)


def decide_front(n_before: int, n_after: int, front_id_before: str | None,
                 front: dict | None, second: dict | None, prompt: str) -> dict:
    """Return {"result": "BOUND"|"UNBOUND"|"AMBIGUOUS", "why", "media_id"?}.

    ``front`` / ``second`` are ``{"url", "text"}`` read from the detail pages of
    the first and second video after the send (``second`` only when there was a
    video before). ``front_id_before`` is the media id of the old front video.
    """
    if n_after == n_before:
        return {"result": "UNBOUND", "why": "no new video"}
    if n_after != n_before + 1:
        return {"result": "AMBIGUOUS", "why": f"{n_after - n_before} new videos"}
    mid = media_id_from_url((front or {}).get("url", ""))
    if not mid:
        return {"result": "UNBOUND", "why": "no media id for the front video"}
    if n_before:
        if not front_id_before:
            return {"result": "AMBIGUOUS", "why": "front video before the send was not identified"}
        if mid == front_id_before:
            return {"result": "AMBIGUOUS", "media_id": mid,
                    "why": "front video is the one that was there before"}
        if media_id_from_url((second or {}).get("url", "")) != front_id_before:
            return {"result": "AMBIGUOUS", "media_id": mid,
                    "why": "old front video is not second: the new one is not in front"}
    if not prompt_on_page(prompt, (front or {}).get("text", "")):
        return {"result": "UNBOUND", "media_id": mid,
                "why": "detail page does not hold the whole sent prompt"}
    return {"result": "BOUND", "media_id": mid, "binding": "DETAIL_PROMPT_MATCH",
            "why": "one more video, old front now second, prompt equal"}


def id_matches_tail(media_id: str, tail: str) -> bool:
    """A take manifest keeps only the last 8 characters of a media id (``media_id_tail``): match by suffix."""
    return bool(media_id) and bool(tail) and media_id.lower().endswith(tail.lower())


def is_known(media_id: str, known: set[str]) -> bool:
    """``known`` holds full media ids or 8-char tails; a media id is known when it equals one or ends with one."""
    return any(media_id.lower() == k.lower() or id_matches_tail(media_id, k) for k in known)


def reconcile(prompt: str, details: list[dict], known_media_ids: set[str]) -> dict:
    """Bind a send that ended UNBOUND/AMBIGUOUS from the gallery detail pages (newest first).

    A candidate is a clip whose media id is not already registered and whose detail page holds the WHOLE prompt.
    Returns BOUND (exactly one candidate: ``media_id``, ``index``), AMBIGUOUS (``media_ids``) or NOT_IN_GALLERY
    (``why``); ``already_registered`` lists the media ids that matched the prompt but were known."""
    candidates: list[tuple[int, str]] = []
    registered: list[str] = []
    for i, d in enumerate(details):
        mid = media_id_from_url((d or {}).get("url", ""))
        if not mid or not prompt_on_page(prompt, (d or {}).get("text", "")):
            continue
        if is_known(mid, known_media_ids):
            if mid not in registered:
                registered.append(mid)
        elif mid not in [c[1] for c in candidates]:
            candidates.append((i, mid))
    out: dict = {"already_registered": registered}
    if len(candidates) == 1:
        out.update(result="BOUND", media_id=candidates[0][1], index=candidates[0][0])
    elif candidates:
        out.update(result="AMBIGUOUS", media_ids=[c[1] for c in candidates])
    else:
        out.update(result="NOT_IN_GALLERY",
                   why=f"no unregistered clip among {len(details)} scanned holds the whole prompt")
    return out
