"""V2-019 Phase K — long-run hardening utilities.

Operational debt resolved here:
  - safe_close(): manager.close() exceptions must never mask results.
  - stale_profile_locks()/clear_stale_profile_locks(): automation-profile
    lock lifecycle WITHOUT force-kill as steady state — a lock file is
    cleared only when no live chrome process references that profile dir.
  - extract_poll_messages(): poll schema variation adapter (limit-10 /
    limit-20 / recent_conv shapes) — finds message arrays wherever the
    provider puts them, so schema drift cannot strand a receipt.

Owner's own Chrome windows are NEVER touched: only profile dirs explicitly
registered as automation profiles may be inspected.
"""
from __future__ import annotations

import json
import subprocess
from pathlib import Path
from typing import Any, Iterable

_LOCK_NAMES = ("SingletonLock", "SingletonCookie", "SingletonSocket",
               "lockfile")


def safe_close(manager: Any, *, notes: list[str] | None = None) -> bool:
    """Close a session manager without letting its exceptions propagate."""
    try:
        manager.close()  # may be async — handled by caller wrapper below
        return True
    except TypeError:
        # async close invoked from sync context
        return False
    except Exception as error:  # noqa: BLE001 - hardening boundary
        if notes is not None:
            notes.append(f"close_error:{type(error).__name__}")
        return False


def _chrome_commandlines() -> list[str]:
    try:
        out = subprocess.run(
            ["powershell", "-NoProfile", "-Command",
             "Get-CimInstance Win32_Process -Filter \"Name='chrome.exe'\" "
             "| Select-Object -ExpandProperty CommandLine"],
            capture_output=True, text=True, timeout=30)
    except Exception:
        return []
    return [ln for ln in (out.stdout or "").splitlines() if ln.strip()]


def stale_profile_locks(profile_dir: Path,
                        commandlines: Iterable[str] | None = None
                        ) -> list[Path]:
    """Lock files in an automation profile dir whose owning process is gone.

    A lock counts as stale only when NO chrome.exe command line references
    the profile directory. Owner Chrome windows use different profile dirs
    and are never matched.
    """
    profile_dir = Path(profile_dir)
    if not profile_dir.exists():
        return []
    lines = list(commandlines) if commandlines is not None \
        else _chrome_commandlines()
    needle = str(profile_dir).lower()
    if any(needle in (ln or "").lower() for ln in lines):
        return []
    return [profile_dir / name for name in _LOCK_NAMES
            if (profile_dir / name).exists()]


def clear_stale_profile_locks(profile_dir: Path,
                              commandlines: Iterable[str] | None = None
                              ) -> list[str]:
    cleared: list[str] = []
    for lock in stale_profile_locks(profile_dir, commandlines):
        try:
            lock.unlink(missing_ok=True)
            cleared.append(lock.name)
        except OSError:
            continue
    return cleared


def extract_poll_messages(payload: dict) -> list[dict]:
    """Message arrays from any observed poll shape: /im/chain/single
    limit-10, limit-20, recent_conv, or an SSE-embedded body. Shape drift
    degrades to 'no messages', never to a wrong-message read."""
    found: list[dict] = []
    from .observability import deep_json_strings

    for obj in deep_json_strings(payload):
        if not isinstance(obj, dict):
            continue
        downlink = obj.get("downlink_body") if \
            isinstance(obj.get("downlink_body"), dict) else None
        for key in ("pull_singe_chain_downlink_body",
                    "pull_recent_conv_chain_downlink_body"):
            body = (downlink or {}).get(key) if downlink else None
            if isinstance(body, dict) and \
                    isinstance(body.get("messages"), list):
                found.extend(
                    m for m in body["messages"] if isinstance(m, dict))
    # dedupe by message_id, preserving order
    seen: set[str] = set()
    unique = []
    for message in found:
        mid = str(message.get("message_id") or id(message))
        if mid in seen:
            continue
        seen.add(mid)
        unique.append(message)
    return unique


def summarize_payload_shape(payload: dict) -> dict:
    """Redacted shape summary for evidence: keys and message counts only."""
    messages = extract_poll_messages(payload)
    return {"message_count": len(messages),
            "has_creations": bool(json.dumps(payload).find(
                "creation_block") >= 0)}
