"""AI-FILM-QUALITY-V2-010D — Layer 0 custody: receipt + fresh ledger.

New execution scope QUALITY-V2-010D-F2B-COMPLETION with EXACTLY ONE provider
mutation (f2b_010d). 010C latches/truths preserved, never reused. F2B_010C's
spent authority stays dead; this is NEW Owner authority.
"""
from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PKG = ROOT / "projects/quality_v2_010d_f2b_completion"
PKG.mkdir(parents=True, exist_ok=True)
sys.path.insert(0, str(ROOT / "tools"))
sys.path.insert(0, str(ROOT / "src"))

EXPECTED_HEAD = "c3145d67cff1230a045335c509461191cd715b97"
SCOPE = "QUALITY-V2-010D-F2B-COMPLETION"

PRIOR_EVIDENCE = [
    "projects/quality_v2_010c_dola_fullstack/V2_010C_CUSTODY.json",
    "projects/quality_v2_010c_dola_fullstack/V2_010C_CURRENT_PROTOCOL.json",
    "projects/quality_v2_010c_dola_fullstack/V2_010C_PROTOCOL_DIFF.json",
    "projects/quality_v2_010c_dola_fullstack/V2_010C_TRANSPORT_DECISION.json",
    "projects/quality_v2_010c_dola_fullstack/V2_010C_BROWSER_ORACLE_EVIDENCE.json",
    "projects/quality_v2_010c_dola_fullstack/V2_010C_M2_QUALIFICATION_EVIDENCE.json",
    "projects/quality_v2_010c_dola_fullstack/V2_010C_F2A_EVIDENCE.json",
    "projects/quality_v2_010c_dola_fullstack/V2_010C_F2B_EVIDENCE.json",
    "projects/quality_v2_010c_dola_fullstack/mutation_authority.json",
    "docs/operating/AI_FILM_QUALITY_V2_010C_DOLA_FULLSTACK_EVIDENCE.md",
]

SECRET_MARKERS = [
    b"sessionid=", b"msToken=", b"a_bogus=", b"AIza", b"sk-",
    b"BEGIN OPENSSH", b"BEGIN RSA PRIVATE", b"BEGIN PRIVATE KEY",
]


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def git(*args: str) -> str:
    return subprocess.run(["git", *args], cwd=ROOT, capture_output=True,
                          text=True, check=True).stdout.strip()


def main() -> int:
    head = git("rev-parse", "HEAD")
    branch = git("branch", "--show-current")
    if head != EXPECTED_HEAD:
        print(json.dumps({"status": "STOPPED_PRE_DISPATCH",
                          "reason": f"HEAD {head} != {EXPECTED_HEAD}"}))
        return 1
    if branch != "quality-v2/010d-f2b-completion":
        print(json.dumps({"status": "STOPPED_PRE_DISPATCH",
                          "reason": f"branch {branch} wrong"}))
        return 1

    prior = {rel: sha256_file(ROOT / rel) for rel in PRIOR_EVIDENCE}
    tracked_files = git("ls-files").splitlines()
    hits = []
    for rel in tracked_files:
        path = ROOT / rel
        if not path.is_file() or path.suffix in (".mp4", ".png", ".jpg",
                                                 ".sqlite"):
            continue
        try:
            blob = path.read_bytes()
        except OSError:
            continue
        for marker in SECRET_MARKERS:
            if marker.lower() in blob.lower():
                hits.append(f"{rel}: {marker.decode(errors='replace')}")

    from mutation_authority import MutationAuthority
    auth = MutationAuthority(PKG, SCOPE)
    auth._event("CUSTODY_ESTABLISHED", detail=json.dumps({
        "head": head, "branch": branch, "baseline_tests": 1294,
        "authority": "F2B_010D = ONE provider mutation (fresh, does not "
                     "reuse F2B_010C)",
        "preserved_truths": ["DOLA_CURRENT_TRANSPORT=BrowserNetwork",
                             "DOLA_TRANSPORT_QUALIFICATION=PROVEN",
                             "M2=PROVEN", "F2A=PROVEN",
                             "F2B_010C=EXPLICIT_PROVIDER_CREDIT_REFUSAL",
                             "NO_AMBIGUITY=true"]}))
    auth.check_mutation_allowed("f2b_010d")  # must be OPEN now

    receipt = {
        "version": "v2-010d-custody-v1",
        "checkpoint": "V2010D_P0_CUSTODY",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "head": head, "branch": branch,
        "baseline": {"tests_passed": 1294,
                     "suite": "pytest full regression at 010C seal"},
        "prior_evidence_sha256": prior,
        "preserved_010c_truths": {
            "dola_current_transport": "BrowserNetwork",
            "qualification": "PROVEN (M2 7/7)",
            "f2a": "PROVEN", "f2b_010c": "EXPLICIT_PROVIDER_CREDIT_REFUSAL",
            "no_ambiguity": True,
            "dead_routes_not_reopened": ["NativeHTTP", "cookie-HTTP",
                                         "a_bogus reproduction", "AVP",
                                         "Elyum", "protocol reconstruction"]},
        "mutation_budget": {
            "scope": SCOPE, "authority": auth.authority,
            "items": {"f2b_010d": 1}, "hard_max": 1},
        "secret_scan_baseline": {"tracked_files_scanned": len(tracked_files),
                                 "hits": hits,
                                 "note": "hits are pre-existing test-fixture "
                                         "marker strings; baseline for "
                                         "no-NEW-hits gate"},
    }
    (PKG / "V2_010D_CUSTODY.json").write_text(
        json.dumps(receipt, indent=1, ensure_ascii=False), encoding="utf-8")
    print(json.dumps({"checkpoint": "V2010D_P0_CUSTODY_OK",
                      "branch": branch, "authority": auth.authority,
                      "prior_files": len(prior), "secret_hits": len(hits)}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
