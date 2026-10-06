"""V2-011D RESUME — corrected bounded credit observation (governance fix).

Ledger separation (Owner correction):
  VIDEO_GENERATION_MUTATIONS  — F1R=1 consumed, F3R=0/1 (separate ledger)
  ACCOUNT_STATE_QUERY_MUTATIONS — any inquiry that SENDS a provider message;
    never called read-only; minimum necessary; NO polling-by-mutation.

Per observation boundary (15:04Z, 17:04Z UTC — candidate reset boundaries,
NOT authority):
  1. router probe on ACCOUNT_A = TRUE read-only (navigates + reads EXISTING
     statements via API; sends no message) — preferred order 2/3;
  2. only if no statement authoritative for the current quota epoch exists
     -> at most ONE inquiry message (ACCOUNT_STATE_QUERY_MUTATION);
  3. dispatch only on fresh provider-visible evidence.

Exit: 0 = SUFFICIENT observed, 1 = bounded window exhausted insufficient.
"""
from __future__ import annotations

import asyncio
import json
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
sys.path.insert(0, str(ROOT / "src"))

PKG = ROOT / "projects/quality_v2_011d_world_matched_context"
LOG = PKG / "V2_011D_RESUME_OBSERVATION_LOG.json"
BOUNDARIES = [("boundary_1_jst_midnight", 15, 4),
              ("boundary_2_ict_midnight", 17, 4)]
OPAQUE = "ACCOUNT_A"


def utcnow():
    return datetime.now(timezone.utc).isoformat()


def log_append(entry):
    data = json.loads(LOG.read_text(encoding="utf-8")) if LOG.exists() else {
        "version": "v2-011d-resume-observation-log-v1",
        "ledger_rule": "VIDEO_GENERATION_MUTATIONS (F1R=1, F3R=0/1) tracked "
                       "separately from ACCOUNT_STATE_QUERY_MUTATIONS",
        "account_state_query_mutations_sent": 0,
        "observations": []}
    data["observations"].append(entry)
    if entry.get("kind") == "ACCOUNT_STATE_QUERY_MUTATION" and entry.get("sent"):
        data["account_state_query_mutations_sent"] += 1
    LOG.write_text(json.dumps(data, indent=1, ensure_ascii=False),
                   encoding="utf-8")


async def probe() -> dict:
    from dola_010e_session_router import DolaSessionRouter
    router = DolaSessionRouter()
    s = await router.probe_account(OPAQUE, OPAQUE, "dpapi_blob_010e")
    router.classify(s, required_credit=1)
    view = s.tracked_view()
    return view


def sleep_until(hh, mm):
    target = time.strftime("%Y-%m-%d", time.gmtime())
    target_ts = time.mktime(time.strptime(
        f"{target} {hh:02d}:{mm:02d}:00", "%Y-%m-%d %H:%M:%S")) - \
        time.timezone  # convert local-struct to UTC epoch
    now = time.time()
    if now < target_ts:
        wait = target_ts - now
        print(f"sleeping {int(wait)}s until {hh:02d}:{mm:02d}Z", flush=True)
        time.sleep(wait)


def main() -> int:
    for name, hh, mm in BOUNDARIES:
        sleep_until(hh, mm)
        print(f"[{utcnow()}] {name}: read-only probe {OPAQUE}", flush=True)
        view = asyncio.run(probe())
        log_append({"kind": "READ_ONLY_PROBE", "boundary": name,
                    "at": utcnow(), "account": OPAQUE,
                    "session_state": view["session_state"],
                    "credit_remaining": view["credit_remaining"],
                    "credit_source_text": view["credit_source_text"],
                    "observed_at": view["credit_observed_at"],
                    "ledger_class": "READ_ONLY (no provider message created)"})
        print(json.dumps({k: view.get(k) for k in
                          ("session_state", "credit_remaining",
                           "credit_source_text")}, ensure_ascii=False),
              flush=True)
        if view["session_state"] == "READY" and \
                (view["credit_remaining"] or 0) >= 1:
            (PKG / "V2_011D_F3R_CREDIT_GATE.json").write_text(
                json.dumps({"version": "v2-011d-f3r-credit-gate-v1",
                            "account_opaque_id": OPAQUE,
                            "verdict": "SUFFICIENT",
                            "basis": "fresh provider-visible statement "
                                     "(read-only probe)",
                            "credit_remaining": view["credit_remaining"],
                            "observed_at": utcnow()}, indent=1),
                encoding="utf-8")
            print("SUFFICIENT (probe) — ready for F3R dispatch", flush=True)
            return 0
        # statements stale for the new epoch -> ONE state query message
        print(f"[{utcnow()}] {name}: one ACCOUNT_STATE_QUERY_MUTATION "
              f"(inquiry)", flush=True)
        r = subprocess.run(
            [str(ROOT / ".venv/Scripts/python.exe"),
             str(ROOT / "tools/v2_011d_resume_credit_inquiry.py"), OPAQUE],
            capture_output=True, text=True)
        sent = "inquiry_sent" in (r.stdout or "")
        log_append({"kind": "ACCOUNT_STATE_QUERY_MUTATION", "boundary": name,
                    "at": utcnow(), "account": OPAQUE, "sent": sent,
                    "stdout_tail": (r.stdout or "")[-400:],
                    "ledger_class": "ACCOUNT_STATE_QUERY_MUTATION "
                                    "(provider message; never read-only)"})
        gate = {}
        if (PKG / "V2_011D_F3R_CREDIT_GATE.json").exists():
            gate = json.loads((PKG / "V2_011D_F3R_CREDIT_GATE.json")
                              .read_text(encoding="utf-8"))
        verdict = gate.get("verdict")
        print(f"gate verdict: {verdict} "
              f"credit={gate.get('credit_remaining')}", flush=True)
        if verdict == "SUFFICIENT":
            return 0
    print("bounded observation window exhausted without sufficient credit",
          flush=True)
    log_append({"kind": "WINDOW_EXHAUSTED", "at": utcnow(),
                "consequence": "STOPPED_INSUFFICIENT_CREDIT_PRE_DISPATCH "
                               "unless credit appears before dispatch"})
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
