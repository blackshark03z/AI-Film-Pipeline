"""AI-FILM-QUALITY-V2-010E — Layer 0 custody: fresh scope, F2B_010E = ONE."""
from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PKG = ROOT / "projects/quality_v2_010e_final_f2b"
PKG.mkdir(parents=True, exist_ok=True)
sys.path.insert(0, str(ROOT / "tools"))
sys.path.insert(0, str(ROOT / "src"))

EXPECTED_HEAD = "cb54e871e31070074129ad8e285b3dac5daee04c"
SCOPE = "QUALITY-V2-010E-FINAL-F2B"

PRIOR_EVIDENCE = [
    "projects/quality_v2_010d_f2b_completion/V2_010D_CUSTODY.json",
    "projects/quality_v2_010d_f2b_completion/V2_010D_DURATION_AUTHORITY.json",
    "projects/quality_v2_010d_f2b_completion/V2_010D_F2B_EVIDENCE.json",
    "projects/quality_v2_010d_f2b_completion/V2_010D_PROVIDER_LINEAGE.json",
    "projects/quality_v2_010d_f2b_completion/V2_010D_CANDIDATE_SEAL.json",
    "projects/quality_v2_010d_f2b_completion/mutation_authority.json",
    "docs/operating/AI_FILM_QUALITY_V2_010D_F2B_COMPLETION_EVIDENCE.md",
    "docs/operating/AI_FILM_QUALITY_V2_010C_DOLA_FULLSTACK_EVIDENCE.md",
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
    if branch != "quality-v2/010e-final-f2b":
        print(json.dumps({"status": "STOPPED_PRE_DISPATCH",
                          "reason": f"branch {branch} wrong"}))
        return 1
    prior = {rel: sha256_file(ROOT / rel) for rel in PRIOR_EVIDENCE}

    from mutation_authority import MutationAuthority
    auth = MutationAuthority(PKG, SCOPE)
    auth.check_mutation_allowed("f2b_010e")
    auth._event("CUSTODY_ESTABLISHED", detail=json.dumps({
        "head": head, "branch": branch,
        "authority": "F2B_010E = ONE (fresh; 010C/010D authorities stay "
                     "spent; 010D latch stays CLOSED)",
        "preserved": ["DOLA_BROWSER_NETWORK=QUALIFIED",
                      "DURATION_AUTHORITY_5S=PROVEN", "M2=PROVEN",
                      "F2A=PROVEN",
                      "F2B_010C=EXPLICIT_CREDIT_REFUSAL",
                      "F2B_010D=EXPLICIT_PROVIDER_RENDER_FAILURE",
                      "010D_AUTHORITY=SPENT", "010D_LATCH=CLOSED"]}))
    receipt = {
        "version": "v2-010e-custody-v1",
        "checkpoint": "V2010E_P0_CUSTODY",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "head": head, "branch": branch,
        "prior_evidence_sha256": prior,
        "mutation_budget": {"scope": SCOPE, "authority": auth.authority,
                            "items": {"f2b_010e": 1}, "hard_max": 1},
        "preserved_truths": {
            "dola_browser_network": "QUALIFIED",
            "duration_authority_5s": "PROVEN",
            "m2": "PROVEN", "f2a": "PROVEN",
            "f2b_010c": "EXPLICIT_CREDIT_REFUSAL",
            "f2b_010d": "EXPLICIT_PROVIDER_RENDER_FAILURE",
            "010d_authority": "SPENT", "010d_latch": "CLOSED",
            "unwatermarked_variant": "OBSERVED_NOT_AUTHORIZED"},
        "no_retry_of_prior_authority": True,
    }
    (PKG / "V2_010E_CUSTODY.json").write_text(
        json.dumps(receipt, indent=1, ensure_ascii=False), encoding="utf-8")
    print(json.dumps({"checkpoint": "V2010E_P0_CUSTODY_OK",
                      "branch": branch, "authority": auth.authority}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
