"""V2-010E RESUME — run account discovery + selection, write pool evidence."""
from __future__ import annotations

import asyncio
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
sys.path.insert(0, str(ROOT / "src"))

from dola_010e_session_router import (PKG, DolaSessionRouter, opaque_alias)

QUALIFIED_ALIAS = "dola-profile-20260923"  # 010C/010D qualified behavior


def utcnow() -> str:
    return datetime.now(timezone.utc).isoformat()


async def main() -> int:
    router = DolaSessionRouter()
    accounts = router.enumerate_known_accounts()
    print(json.dumps({"step": "discovered",
                      "accounts": [a for a, _ in accounts]}), flush=True)

    pool = []
    for index, (alias, source) in enumerate(accounts):
        opaque = opaque_alias(index)
        session = await router.probe_account(opaque, alias, source)
        router.classify(session, required_credit=1)
        pool.append(session)
        print(json.dumps({"step": "probed", "opaque": opaque,
                          "alias": alias,
                          "state": session.session_state,
                          "credit": session.credit_remaining,
                          "health": session.health_state,
                          "credit_source": session.credit_source_text}),
              flush=True)

    selection = router.select(pool, qualified_alias=QUALIFIED_ALIAS)
    chosen = selection.get("selected")
    result = {
        "version": "v2-010e-dola-account-pool-v1",
        "checkpoint": "V2010E_P3B_ACCOUNT_POOL",
        "built_at": utcnow(),
        "policy": "Owner-authorized accounts only (Story Auto DPAPI store); "
                  "no fake accounts, no enforcement circumvention; switching "
                  "legal only while dispatch_state=NOT_RELEASED",
        "required_credit": 1,
        "pool": [s.tracked_view() for s in pool],
        "selection": {
            "selected_opaque_id": chosen.opaque_id if chosen else None,
            "selected_account_alias": chosen.account_alias if chosen else None,
            "selection_reason": selection.get("selection_reason"),
            "credit_observation": {
                "remaining": chosen.credit_remaining,
                "observed_at": chosen.credit_observed_at,
                "source_text": chosen.credit_source_text} if chosen else None,
            "session_health": chosen.health_state if chosen else None},
    }
    (PKG / "V2_010E_DOLA_ACCOUNT_POOL.json").write_text(
        json.dumps(result, indent=1, ensure_ascii=False), encoding="utf-8")
    if chosen:
        (PKG / "V2_010E_ACCOUNT_SELECTION.json").write_text(
            json.dumps({"version": "v2-010e-account-selection-v1",
                        "selected_at": utcnow(),
                        "selected_opaque_id": chosen.opaque_id,
                        "selected_account_alias": chosen.account_alias,
                        "selected_profile_alias": chosen.profile_alias,
                        "encrypted_session_ref": chosen.encrypted_session_ref,
                        "selection_reason": selection["selection_reason"],
                        "credit_remaining": chosen.credit_remaining,
                        "credit_observed_at": chosen.credit_observed_at,
                        "session_state": chosen.session_state,
                        "binding_rule": "account becomes IMMUTABLY bound at "
                                        "NETWORK_RELEASE_OBSERVED; no "
                                        "switch/retry after release"},
                       indent=1, ensure_ascii=False), encoding="utf-8")
    print(json.dumps({"checkpoint": "V2010E_POOL_BUILT",
                      "ready": [s.opaque_id for s in pool
                                if s.session_state == "READY"],
                      "selected": (chosen.opaque_id if chosen else None),
                      "selected_credit": (chosen.credit_remaining
                                          if chosen else None)}))
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
