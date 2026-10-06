"""AI-FILM-QUALITY-V2-010C — Layer 0 custody: receipt, ledger, secret baseline.

Creates the isolated 010C execution scope:
- custody receipt (HEAD, branch, immutable prior-evidence hashes, tree state)
- NEW MutationAuthority ledger (OPEN) scoped QUALITY-V2-010C-DOLA-FULLSTACK
  (010B latch is NOT reused, NOT reopened, remains terminal evidence)
- secret-scan baseline over tracked repository files
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
PKG.mkdir(parents=True, exist_ok=True)
sys.path.insert(0, str(ROOT / "tools"))
sys.path.insert(0, str(ROOT / "src"))

EXPECTED_HEAD = "51fc0eb2afb63117fe9832cea367cf01b4cdf3bf"
SCOPE = "QUALITY-V2-010C-DOLA-FULLSTACK"

PRIOR_EVIDENCE = [
    "projects/quality_v2_010a_dola_re_authority/route_history_truth_v2_010a.json",
    "projects/quality_v2_010a_dola_re_authority/dola_re_contract_v1.json",
    "projects/quality_v2_010a_dola_re_authority/dola_transport_diff_v2_010a.json",
    "projects/quality_v2_010a_dola_re_authority/dg1_cause_analysis_v2_010a.json",
    "projects/quality_v2_010b_dola_re_live/mutation_authority.json",
    "projects/quality_v2_010b_dola_re_live/qualification_result.json",
    "docs/operating/AI_FILM_QUALITY_V2_010A_DOLA_RE_AUTHORITY_RECONSTRUCTION_EVIDENCE.md",
    "src/film_pipeline/providers/dola_provider.py",
    "tools/qualify_v2_010b_dola.py",
]

SECRET_MARKERS = [
    b"sessionid=", b"msToken=", b"data:application/json", b"AIza",
    b"sk-", b"BEGIN OPENSSH", b"BEGIN RSA PRIVATE", b"BEGIN PRIVATE KEY",
    b"password=", b"bearer ", b"__Secure-1PSID=",
]

UNTRACKED_ALLOWLIST = {
    ".zcodeignore",
    "FLOW_CURRENT_R2V_CONTRACT_20261001.md",
    "FLOW_R2V_CURRENT_CONTRACT_CANARY_20261001.md",
    "FLOW_R2V_INDEPENDENT_STORYAUTO_RECONSTRUCTION.md",
    "FLOW_R2V_OPEN_INVESTIGATION_20261001.md",
    "STORY_AUTO_R2V_LIVE_CONTROL_20261001.md",
    "OWNER_REVIEW/",
    "chrome_profile/",
    "fixtures/requal002/",
    "scratch/",
    "tools/build_v2_002_owner_surface.py",
    "uv.lock",
}


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
                          "reason": f"HEAD {head} != expected {EXPECTED_HEAD}"}))
        return 1
    if branch != "quality-v2/010c-dola-fullstack-re":
        print(json.dumps({"status": "STOPPED_PRE_DISPATCH",
                          "reason": f"branch {branch} is not the 010C branch"}))
        return 1

    prior = {rel: sha256_file(ROOT / rel) for rel in PRIOR_EVIDENCE}

    status_out = git("status", "--porcelain")
    untracked = sorted(line[3:] for line in status_out.splitlines()
                       if line.startswith("??"))
    # 010C work products (tools/tests) are committed at seal time; until then
    # they are expected untracked files, not tree contamination.
    own_work = ("tools/custody_v2_010c.py",)
    unexpected = [u for u in untracked
                  if u not in UNTRACKED_ALLOWLIST and u not in own_work]

    # secret-scan baseline over TRACKED files only (untracked runtime dirs are
    # out of repo scope by construction; gitignore projects/* covers runtime)
    tracked_files = git("ls-files").splitlines()
    hits = []
    for rel in tracked_files:
        path = ROOT / rel
        if not path.is_file() or path.suffix in (".mp4", ".png", ".jpg", ".sqlite"):
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
        "head": head, "branch": branch, "baseline_tests": 1285,
        "prior_evidence_files": len(prior), "proxy_story_auto": "DEAD"}))

    receipt = {
        "version": "v2-010c-custody-v1",
        "checkpoint": "V2010C_P0_CUSTODY",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "head": head,
        "branch": branch,
        "baseline": {"tests_passed": 1285,
                     "suite": "pytest full regression 2026-10-06"},
        "prior_evidence_sha256": prior,
        "prior_latches": {
            "v2_010b": {"scope": "QUALITY-V2-010B-DOLA-RE-LIVE",
                        "authority": "LATCHED_CLOSED",
                        "disposition": "PRESERVED_IMMUTABLE_NOT_REUSED_NOT_REOPENED"},
            "d_g1": {"disposition": "PERMANENTLY_QUARANTINED (FLOW-FORENSIC-TO-DOLA-001)"}},
        "mutation_budget": {
            "scope": SCOPE, "authority": auth.authority,
            "hard_max": 4,
            "items": {"m1_browser_oracle": 1, "m2_native_qualification": "optional",
                      "f2a": "conditional", "f2b": "conditional"}},
        "worktree": {"untracked_allowlisted": sorted(untracked),
                     "unexpected_untracked": unexpected},
        "environment": {
            "story_auto_proxy_127.0.0.1:7890": "DEAD (timed out) — browser runs DIRECT; "
                                               "recorded as an environment delta vs canary-4",
            "patchright": "1.63.0 chromium-1243", "cv2": "ABSENT (PIL fallback for solver)",
            "ffprobe": "9.0.1"},
        "secret_scan_baseline": {"tracked_files_scanned": len(tracked_files),
                                 "hits": hits},
    }
    (PKG / "V2_010C_CUSTODY.json").write_text(
        json.dumps(receipt, indent=1, ensure_ascii=False), encoding="utf-8")
    print(json.dumps({"checkpoint": "V2010C_P0_CUSTODY_OK",
                      "branch": branch, "tests_baseline": 1285,
                      "unexpected_untracked": unexpected,
                      "secret_hits": hits,
                      "authority": auth.authority}))
    return 0 if not unexpected else 1


if __name__ == "__main__":
    raise SystemExit(main())
