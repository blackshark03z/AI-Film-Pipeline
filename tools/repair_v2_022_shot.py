"""V2-022 operator repair — safe re-dispatch preparation for a refused or
unrecoverable shot.

    python tools/repair_v2_022_shot.py <shot_id> [--run-dir DIR]
        [--reason TEXT]

A shot whose journal holds a latched release is NEVER re-dispatched
blindly: this tool makes the repair an explicit, recorded operator act:

  1. refuses if the shot is QC_ACCEPT (accepted work is never repaired);
  2. archives the latched dispatch journal as .prior-N.jsonl (evidence
     preserved, never deleted);
  3. archives the consumed slot authority dir as .prior-N (a fresh
     authority is issued on the next dispatch);
  4. resets the record to PENDING with a repair-history entry naming the
     reason (the original refusal/receipt-miss evidence stays in the
     archived journal and recovery scans).

The release accounting is untouched: a repair costs one NEW release when
dispatched (or is recovered read-only if it completes provider-side).
"""
from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_RUN_DIR = ROOT / "projects/quality_v2_022_longform_120s"


def _next_prior(path: Path) -> Path:
    n = 1
    while True:
        candidate = path.with_name(path.name + f".prior-{n}")
        if not candidate.exists():
            return candidate
        n += 1


def repair(run_dir: Path, shot_id: str, reason: str) -> dict:
    state_path = run_dir / "v2_022_run_state.json"
    state = json.loads(state_path.read_text(encoding="utf-8"))
    record = state["shots"][shot_id]
    if record.get("status") == "QC_ACCEPT" or \
            record.get("qc_verdict") == "ACCEPT":
        raise SystemExit(f"refusing to repair {shot_id}: QC_ACCEPT")

    archived = {}
    journal = run_dir / f"dispatch_journal_{shot_id}.jsonl"
    if journal.exists():
        dst = _next_prior(journal)
        journal.rename(dst)
        archived["journal"] = str(dst)
    slot = run_dir / "slots" / shot_id
    if slot.is_dir():
        dst = _next_prior(slot)
        slot.rename(dst)
        archived["slot"] = str(dst)

    history = record.setdefault("repairs", [])
    history.append({
        "at": datetime.now(timezone.utc).isoformat(),
        "reason": reason,
        "archived": archived,
        "previous_status": record.get("status"),
        "previous_error": record.get("error"),
    })
    record["status"] = "PENDING"
    record.pop("error", None)
    record.pop("recovery_verdict", None)
    record["repair_needed"] = False
    state_path.write_text(json.dumps(state, indent=1, ensure_ascii=False),
                          encoding="utf-8")
    return {"shot": shot_id, "status": "PENDING",
            "archived": archived, "repairs": len(history)}


def main() -> int:
    args = sys.argv[1:]
    if not args:
        print(__doc__)
        return 2
    shot_id = args[0]
    run_dir = DEFAULT_RUN_DIR
    reason = "operator repair"
    if "--run-dir" in args:
        run_dir = Path(args[args.index("--run-dir") + 1])
    if "--reason" in args:
        reason = args[args.index("--reason") + 1]
    print(json.dumps(repair(run_dir, shot_id, reason), indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
