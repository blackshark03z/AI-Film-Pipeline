"""AI-FILM-QUALITY-V2-010C — Layer 1 session acquisition runner.

Flow:
    acquire DPAPI cookie (Story Auto store, memory only)
      → launch headed DOLA_RE_PROFILE browser
      → inject cookies → navigate /chat → validate (read-only)
      → SESSION_VALID: capture inventory + persist encrypted + tracked metadata
      → LOGIN_REQUIRED/SESSION_EXPIRED: keep window open, poll for manual
        login (operator interrupt is authorized for exactly this), then resume.

Output: projects/quality_v2_010c_dola_fullstack/V2_010C_SESSION_ACQUISITION.json
(tracked metadata only — names/classes/hashes, never values).
"""
from __future__ import annotations

import asyncio
import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
sys.path.insert(0, str(ROOT / "src"))

from dola_010c_session import (LOGIN_REQUIRED, NO_SESSION, PKG, ROOT as _R,
                               SESSION_EXPIRED, SESSION_UNCERTAIN, SESSION_VALID,
                               DolaSessionManager)

WAIT_LOGIN_SECONDS = int(sys.argv[1]) if len(sys.argv) > 1 else 840


def emit(payload: dict) -> None:
    print(json.dumps(payload, ensure_ascii=False), flush=True)


async def main() -> int:
    manager = DolaSessionManager()
    acquisition = {
        "version": "v2-010c-session-acquisition-v1",
        "checkpoint": "V2010C_P1_SESSION_ACQUISITION",
        "started_at": datetime.now(timezone.utc).isoformat(),
        "profile_alias": "DOLA_RE_PROFILE",
    }
    if not manager.acquire_cookie():
        acquisition.update({"status": "USER_LOGIN_REQUIRED",
                            "state": NO_SESSION,
                            "reason": "no Dola cookie source available"})
        (PKG / "V2_010C_SESSION_ACQUISITION.json").write_text(
            json.dumps(acquisition, indent=1, ensure_ascii=False), encoding="utf-8")
        emit({"status": "USER_LOGIN_REQUIRED", "state": NO_SESSION})
        return 1

    emit({"step": "cookie_acquired", "source": manager.cookie_source,
          "cookie_header_len": len(manager._cookie_header)})
    await manager.launch_browser()
    injected = await manager.inject_cookies()
    emit({"step": "cookies_injected", "count": injected})

    state = await manager.validate_session()
    emit({"step": "first_validation", "state": state, "url_tail":
          (manager._page.url or "")[-60:]})

    waited = 0
    if state in (LOGIN_REQUIRED, SESSION_EXPIRED, SESSION_UNCERTAIN):
        acquisition.update({"status": "USER_LOGIN_REQUIRED",
                            "state": state,
                            "reason": "manual login window open in DOLA_RE_PROFILE",
                            "operator_note": "worker never reads credentials; "
                                             "polling for authenticated state"})
        (PKG / "V2_010C_SESSION_ACQUISITION.json").write_text(
            json.dumps(acquisition, indent=1, ensure_ascii=False), encoding="utf-8")
        emit({"status": "USER_LOGIN_REQUIRED", "waiting_seconds": WAIT_LOGIN_SECONDS})
        while waited < WAIT_LOGIN_SECONDS:
            # light, non-navigating check: the manual login window MUST NOT
            # be reloaded or it cannot be used
            await asyncio.sleep(3)
            waited += 3
            check = await manager.light_check()
            if check.get("sessionid"):
                state = await manager.validate_session(renavigate=True)
                emit({"step": "sessionid_seen_full_validation",
                      "state": state, "waited": waited})
                if state == SESSION_VALID:
                    break
            if waited % 120 == 0:
                emit({"step": "still_waiting", "waited": waited,
                      "url_tail": check.get("url_tail")})
        if state != SESSION_VALID:
            acquisition.update({"status": "USER_LOGIN_REQUIRED",
                                "state": state,
                                "final": True,
                                "waited_seconds": waited})
            (PKG / "V2_010C_SESSION_ACQUISITION.json").write_text(
                json.dumps(acquisition, indent=1, ensure_ascii=False), encoding="utf-8")
            emit({"status": "USER_LOGIN_REQUIRED", "final": True})
            await manager.close()
            return 1

    inventory = await manager.capture_inventory()
    blob_path = await manager.persist_session()
    blob = blob_path.read_text(encoding="ascii")
    emit({"step": "session_captured",
          "cookies": inventory["cookie_count"],
          "web_storage_keys": len(inventory["web_storage"]),
          "service_workers": len(inventory["service_workers"]),
          "blob_sha256_12": hashlib.sha256(blob.encode()).hexdigest()[:12]})

    tracked = manager.tracked_metadata()
    acquisition.update({
        "status": "SESSION_CAPTURED",
        "state": SESSION_VALID,
        "completed_at": datetime.now(timezone.utc).isoformat(),
        "session": tracked,
        "secret_store": {
            "path_class": "runtime_secret_store/dola_session.dpapi",
            "protection": "WINDOWS_DPAPI_CURRENT_USER",
            "tracked": False,
            "sha256_12": hashlib.sha256(blob.encode()).hexdigest()[:12]},
        "inventory_url_tail": (manager._page.url or "")[-60:],
    })
    (PKG / "V2_010C_SESSION_ACQUISITION.json").write_text(
        json.dumps(acquisition, indent=1, ensure_ascii=False), encoding="utf-8")
    emit({"checkpoint": "V2010C_P1_SESSION_CAPTURED",
          "cookie_count": inventory["cookie_count"],
          "auth_cookies": [c["name"] for c in tracked["cookies"]
                           if c["class"] == "AUTH"]})
    await manager.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
