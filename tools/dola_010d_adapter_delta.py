"""AI-FILM-QUALITY-V2-010D — audited adapter delta (duration authority).

Extends the QUALIFIED 010C DolaBrowserAdapter WITHOUT modifying it (the base
file is untouched — git diff is the audit). Adds:

    select_duration(seconds)   — click the composer duration chip and choose
                                 the class from its dropdown
    read_duration_chip()       — the visible chip text ("5s"/"10s"), the
                                 pre-dispatch duration authority proof
    parse_credit_requirement() — parse the provider's credit texts
    verify_duration_pre_dispatch() — fail-closed gate

Duration authority mapping (from 010C evidence, one structural step):
    composer video mode (動画を作成) builds chat_ability.ability_param with
    duration = <UI class>; observed UI default 10s → body duration:10 (F2A
    release body, V2_010C generation_attempt_f2a.json). Therefore UI chip
    "5s" → ability_param.duration = 5. The body itself is only observable at
    release; the chip state is the pre-dispatch authority, recorded as
    screenshot + DOM text.
"""
from __future__ import annotations

import re

import json

from dola_010c_browser_adapter import DolaBrowserAdapter

CREDIT_PATTERNS = (
    re.compile(r"(\d+)\s*動画クレジット"),
    re.compile(r"(\d+)\s*video credits?", re.I),
    re.compile(r"(\d+)\s*動画クレジット[がが使用]"),
)
REMAINING_PATTERNS = (
    re.compile(r"残り\s*(\d+)"),
    re.compile(r"(\d+)\s*(?:video credits?|動画クレジット)\s*(?:left|残り)",
               re.I),
)


def extract_released_duration(body_structure: dict) -> int | None:
    """Pull the provider duration class out of a /chat/completion release
    body (chat_ability.ability_param JSON string)."""
    ability = (body_structure or {}).get("chat_ability")
    if not isinstance(ability, dict):
        return None
    raw = ability.get("ability_param")
    if isinstance(raw, str):
        try:
            raw = json.loads(raw)
        except json.JSONDecodeError:
            return None
    if not isinstance(raw, dict):
        return None
    duration = raw.get("duration")
    return duration if isinstance(duration, int) else None


def duration_gate_ok(chip_text: str | None, expected_seconds: int) -> bool:
    """Pre-dispatch fail-closed gate: the chip must read the exact class."""
    return chip_text == f"{expected_seconds}s"


def verify_asset_integrity(path, expected_sha256: str) -> bool:
    """Restart-after-download recovery: the durable asset must hash-match
    the recorded lineage (no re-download, no network)."""
    import hashlib
    from pathlib import Path as _Path
    path = _Path(path)
    if not path.is_file():
        return False
    return hashlib.sha256(path.read_bytes()).hexdigest() == expected_sha256


class DolaBrowserAdapter010D(DolaBrowserAdapter):
    """010D delta: explicit transport-controlled duration."""

    async def ensure_video_mode(self) -> dict:
        """Idempotent video-mode activation.

        The composer persists the 動画を作成 chip across sessions (persistent
        profile); blindly clicking the entry text TOGGLES an already-active
        mode OFF. Probe the duration chip first; click the entry only when
        the mode is truly off."""
        chip = await self.read_duration_chip(timeout_s=4)
        if chip:
            self.event("video_mode_already_active", chip=chip)
            return {"already_active": True, "chip": chip}
        for text in ("動画を作成", "Create video", "创建视频", "影片生成"):
            try:
                locator = self.page.get_by_text(text, exact=True).first
                if await locator.count() and await locator.is_visible():
                    await locator.click(timeout=5000)
                    self.event("video_mode_activated", text=text)
                    break
            except Exception:
                continue
        chip = await self.read_duration_chip(timeout_s=12)
        if not chip:
            raise RuntimeError(
                "DURATION_AUTHORITY_GAP: video mode did not expose a "
                "duration chip")
        return {"activated": True, "chip": chip}

    async def read_duration_chip(self, timeout_s: int = 12) -> str | None:
        """Visible duration chip text in the composer toolbar (e.g. '10s').
        Retries — the video-mode toolbar renders asynchronously."""
        import asyncio
        deadline = asyncio.get_event_loop().time() + timeout_s
        while asyncio.get_event_loop().time() < deadline:
            try:
                texts = await self.page.evaluate(
                    """() => [...document.querySelectorAll('button, span, div')]
                        .map(el => (el.innerText || '').trim())
                        .filter(t => /^\\d+\\s?s$/.test(t) && t.length <= 6)
                        .slice(0, 10)""")
            except Exception:
                texts = []
            if texts:
                return texts[0]
            await self.page.wait_for_timeout(1000)
        return None

    async def select_duration(self, seconds: int) -> dict:
        """Open the duration dropdown and select the class. Returns the
        observed before/after chip texts. Raises on failure (fail-closed)."""
        before = await self.read_duration_chip()
        opened = False
        if before is not None:
            # open the dropdown via the chip itself
            try:
                chip = self.page.get_by_text(before, exact=True).first
                if await chip.count() and await chip.is_visible():
                    await chip.click(timeout=5000)
                    await self.page.wait_for_timeout(1200)
                    opened = True
            except Exception:
                opened = False
        if not opened:
            raise RuntimeError(
                "DURATION_AUTHORITY_GAP: duration chip not found/clickable")
        # choose the target class from the dropdown
        target = f"{seconds}s"
        clicked = None
        for text in (target, f"{seconds}秒", f"{seconds} giây"):
            try:
                option = self.page.get_by_text(text, exact=True).first
                if await option.count() and await option.is_visible():
                    await option.click(timeout=5000)
                    clicked = text
                    break
            except Exception:
                continue
        if not clicked:
            raise RuntimeError(
                f"DURATION_AUTHORITY_GAP: option '{target}' not in dropdown")
        await self.page.wait_for_timeout(1200)
        after = await self.read_duration_chip()
        if after != target:
            raise RuntimeError(
                f"DURATION_AUTHORITY_GAP: chip reads {after!r} after "
                f"selecting {target!r}")
        self.event("duration_selected", before=before, after=after,
                   clicked=clicked)
        return {"before": before, "after": after, "clicked": clicked}

    async def verify_duration_pre_dispatch(self, seconds: int) -> dict:
        """Fail-closed gate: video mode active AND chip == f'{seconds}s'."""
        chip = await self.read_duration_chip()
        ok = chip == f"{seconds}s"
        self.event("duration_pre_dispatch_check", chip=chip,
                   expected=f"{seconds}s", ok=ok)
        if not ok:
            raise RuntimeError(
                f"DURATION_AUTHORITY_GAP: chip={chip!r}, expected "
                f"{seconds}s — no mutation may be spent")
        return {"chip": chip, "requested_class": f"{seconds}s", "ok": True}

    @staticmethod
    def parse_credit_requirement(text: str) -> dict:
        """Parse the provider's credit texts (required vs remaining)."""
        required = None
        for pattern in CREDIT_PATTERNS:
            match = pattern.search(text or "")
            if match:
                required = int(match.group(1))
                break
        remaining = None
        for pattern in REMAINING_PATTERNS:
            match = pattern.search(text or "")
            if match:
                remaining = int(match.group(1))
                break
        return {"required": required, "remaining": remaining}
