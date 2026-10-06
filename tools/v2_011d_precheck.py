"""V2-011D pre-render gates (read-only): secret audit + session/credit probe.

Fails closed: exits non-zero if the secret audit is not CLEAN or no account
is READY (SESSION_VALID + provider-visible credit >= required). The account
selection recorded here is the only legal rotation point — after
NETWORK_RELEASE_OBSERVED the account binding is immutable.
"""
from __future__ import annotations

import asyncio
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
sys.path.insert(0, str(ROOT / "src"))

PKG = ROOT / "projects/quality_v2_011d_world_matched_context"
SCOPE = "QUALITY-V2-011D-WORLD-MATCHED-CONTEXT"
REQUIRED_CREDIT = 1

MARKERS = [b"sessionid=", b"msToken=", b"a_bogus=", b"AIza", b"sk-",
           b"BEGIN OPENSSH", b"BEGIN RSA PRIVATE", b"BEGIN PRIVATE KEY"]


def utcnow() -> str:
    return datetime.now(timezone.utc).isoformat()


def write(name: str, payload: dict) -> None:
    (PKG / name).write_text(json.dumps(payload, indent=1, ensure_ascii=False),
                            encoding="utf-8")
    print("wrote", name)


def secret_audit() -> bool:
    git = subprocess.run(["git", "ls-files"], cwd=ROOT, capture_output=True,
                         text=True, check=True).stdout.splitlines()
    hits = []
    scanned = 0
    for rel in git:
        path = ROOT / rel
        if "011d" not in rel.lower() and "011c" not in rel.lower():
            continue
        if not path.is_file():
            continue
        scanned += 1
        try:
            blob = path.read_bytes()
        except OSError:
            continue
        for marker in MARKERS:
            if marker.lower() in blob.lower():
                hits.append(f"{rel}: {marker.decode(errors='replace')}")
    verdict = "CLEAN" if not hits else "FAIL"
    write("V2_011D_SECRET_AUDIT.json", {
        "version": "v2-011d-secret-audit-v1",
        "built_at": utcnow(), "scope": SCOPE,
        "tracked_files_scanned": scanned,
        "markers": [m.decode() for m in MARKERS],
        "hits": hits, "verdict": verdict,
        "note": "scan covers 011C + 011D tracked files (evidence/specs/tools); "
                "runtime cookies/DPAPI blobs are untracked by design",
    })
    return verdict == "CLEAN"


async def session_probe() -> dict:
    from dola_010e_session_router import DolaSessionRouter, opaque_alias
    router = DolaSessionRouter()
    pool = []
    for index, (alias, source) in enumerate(
            router.enumerate_known_accounts()):
        opaque = opaque_alias(index) if not alias.startswith("ACCOUNT_") else alias
        print(f"probing {opaque} ({alias}, {source}) ...", flush=True)
        session = await router.probe_account(opaque, alias, source)
        router.classify(session, required_credit=REQUIRED_CREDIT)
        pool.append(session)
        print(f"  -> {session.session_state} "
              f"credit={session.credit_remaining} "
              f"({session.health_state})", flush=True)
    from dola_010e_session_router import DolaAccountSession  # noqa: F401
    selection = router.select(pool, qualified_alias="ACCOUNT_A",
                              required_credit=REQUIRED_CREDIT)
    chosen = selection.get("selected")
    record = {
        "version": "v2-011d-session-precheck-v1",
        "checkpoint": "V2011D_PRE_RENDER_GATES",
        "probed_at": utcnow(),
        "scope": SCOPE,
        "required_credit": REQUIRED_CREDIT,
        "accounts": [s.tracked_view() for s in pool],
        "selection": {
            "selected_opaque_id": chosen.opaque_id if chosen else None,
            "selected_alias": chosen.account_alias if chosen else None,
            "credit_remaining": chosen.credit_remaining if chosen else None,
            "reason": selection.get("selection_reason"),
        },
        "rotation_rule": "rotation legal ONLY at this gate (before "
                         "dispatch); after NETWORK_RELEASE_OBSERVED the "
                         "account binding is immutable",
    }
    write("V2_011D_SESSION_PRECHECK.json", record)
    return record


def main() -> int:
    ok_audit = secret_audit()
    record = asyncio.run(session_probe())
    selected = record["selection"]["selected_opaque_id"]
    ready = [a for a in record["accounts"] if a["session_state"] == "READY"]
    credit_total = sum(a["credit_remaining"] or 0 for a in ready)
    print(f"\nAUDIT={'CLEAN' if ok_audit else 'FAIL'}  "
          f"READY_ACCOUNTS={len(ready)}  TOTAL_VISIBLE_CREDIT={credit_total}  "
          f"SELECTED={selected}")
    gates = {
        "secret_audit_clean": ok_audit,
        "at_least_one_ready_account": bool(selected),
    }
    (PKG / "V2_011D_PRERENDER_GATES.json").write_text(
        json.dumps({"version": "v2-011d-prerender-gates-v1",
                    "built_at": utcnow(), "gates": gates,
                    "all_pass": all(gates.values())}, indent=1),
        encoding="utf-8")
    if not all(gates.values()):
        print("PRE-RENDER GATES FAILED — fail closed")
        return 1
    print("PRE-RENDER GATES PASS (session/credit/world/spec gates "
          "re-asserted inside the runner)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
