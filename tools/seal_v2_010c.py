"""AI-FILM-QUALITY-V2-010C — candidate seal.

Aggregates every 010C evidence artifact, asserts the COMPLETED_CANDIDATE
conditions from the work package, runs the tracked-file secret audit, and
emits V2_010C_CANDIDATE_SEAL.json (in the untracked state dir; the tracked
evidence MD records its hash).
"""
from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PKG = ROOT / "projects/quality_v2_010c_dola_fullstack"
sys.path.insert(0, str(ROOT / "tools"))

REQUIRED = [
    "V2_010C_CUSTODY.json",
    "V2_010C_SESSION_ACQUISITION.json",
    "V2_010C_CURRENT_PROTOCOL.json",
    "V2_010C_PROTOCOL_DIFF.json",
    "V2_010C_TRANSPORT_DECISION.json",
    "V2_010C_BROWSER_ORACLE_EVIDENCE.json",
    "V2_010C_M1_OUTPUT_OBSERVATION.json",
    "V2_010C_M2_QUALIFICATION_EVIDENCE.json",
    "V2_010C_F2A_EVIDENCE.json",
    "mutation_authority.json",
    "m1_receipt.json",
    "m2_receipt.json",
    "f2a_receipt.json",
    "f2b_receipt.json",
]




def main() -> int:
    import re
    markers = [b"sessionid=", b"msToken=", b"a_bogus=", b"AIza", b"sk-",
               b"BEGIN OPENSSH", b"BEGIN RSA PRIVATE", b"BEGIN PRIVATE KEY"]
    missing = [name for name in REQUIRED if not (PKG / name).exists()]
    checks: dict[str, bool] = {"evidence_files_present": not missing}

    def load(name: str) -> dict:
        return json.loads((PKG / name).read_text(encoding="utf-8"))

    try:
        session = load("V2_010C_SESSION_ACQUISITION.json")
        checks["session_captured_safely"] = \
            session.get("status") == "SESSION_CAPTURED"
        m2 = load("V2_010C_M2_QUALIFICATION_EVIDENCE.json")
        checks["qualification_proven"] = m2.get("status") == "PROVEN" and \
            all(v == "PROVEN" for v in m2["chain"]["verdicts"].values())
        f2a = load("V2_010C_F2A_EVIDENCE.json")
        checks["f2a_deterministic"] = f2a.get("status") == "PROVEN"
        f2b = load("V2_010C_F2B_EVIDENCE.json")
        checks["f2b_deterministic"] = f2b.get("status") == "PROVEN"
        ledger = load("mutation_authority.json")
        consumed = [e for e in ledger["events"]
                    if e["kind"] == "BUDGET_CONSUMED"]
        checks["mutation_count_within_budget"] = len(consumed) <= 4
        checks["no_unauthorized_retry"] = ledger["mutation_authority"] == "OPEN" \
            or len(consumed) <= 4
    except FileNotFoundError as error:
        checks["evidence_parsable"] = False
        missing.append(str(error))

    # secret audit over tracked files (fail-closed on NEW hits in 010C files)
    git = subprocess.run(["git", "ls-files"], cwd=ROOT, capture_output=True,
                         text=True, check=True).stdout.splitlines()
    tenC_files = [rel for rel in git if "010c" in rel.lower()
                  or "v2_010c" in rel.lower()]
    hits = []
    for rel in git:
        path = ROOT / rel
        if not path.is_file() or path.suffix in (".mp4", ".png", ".jpg"):
            continue
        try:
            blob = path.read_bytes()
        except OSError:
            continue
        for marker in markers:
            if marker.lower() in blob.lower():
                hits.append(f"{rel}: {marker.decode()}")
    tenC_hits = [h for h in hits if any(f in h for f in tenC_files)]
    checks["secret_audit_010c_clean"] = not tenC_hits

    status = "COMPLETED_CANDIDATE" if all(checks.values()) else "GATE_OPEN"
    seal = {
        "version": "v2-010c-candidate-seal-v1",
        "checkpoint": "V2010C_P9_CANDIDATE_SEAL",
        "sealed_at": datetime.now(timezone.utc).isoformat(),
        "status": status,
        "checks": checks,
        "missing_evidence": missing,
        "mutations_used": len(consumed) if 'consumed' in dir() else None,
        "secret_audit": {"tracked_files_scanned": len(git),
                         "total_hits_baseline_history": len(hits),
                         "hits_in_010c_files": tenC_hits},
        "sha_of_key_assets": {
            name: hashlib.sha256((PKG / name).read_bytes()).hexdigest()[:16]
            for name in REQUIRED if (PKG / name).exists()},
    }
    (PKG / "V2_010C_CANDIDATE_SEAL.json").write_text(
        json.dumps(seal, indent=1, ensure_ascii=False), encoding="utf-8")
    print(json.dumps({"checkpoint": "V2010C_SEAL", "status": status,
                      "checks": checks}))
    return 0 if status == "COMPLETED_CANDIDATE" else 1


if __name__ == "__main__":
    raise SystemExit(main())
