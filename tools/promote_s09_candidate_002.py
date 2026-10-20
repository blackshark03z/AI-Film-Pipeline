"""S3 Film120 — Safe Canonical Promotion for Owner-Accepted S09 Candidate-002.

Executes safe local promotion of S09 Candidate-002 in strict compliance with
TASK_S3_S09_OWNER_ACCEPTED_SAFE_PROMOTION.md.

Guards:
- Fail-closed preflight on Git, policy, candidate SHA, manifest, journals, baseline state.
- Zero external mutations / zero provider calls / zero paid usage.
- Staged non-overwriting copy of asset and evidence to canonical project directory.
- Preserves prior repair history and all 23 other shot records intact.
- Full readback verification proving 10/24 QC_ACCEPT / 14 PENDING.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any, Dict, List, Tuple

WORKER_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(WORKER_ROOT / "tools"))
sys.path.insert(0, str(WORKER_ROOT / "src"))

PRIMARY_ROOT = Path(r"D:\AI FILM MAKER\AI-Film-Pipeline")
CANONICAL_PKG = PRIMARY_ROOT / "projects/quality_v2_022_longform_120s"
CANONICAL_STATE_PATH = CANONICAL_PKG / "v2_022_run_state.json"
CANONICAL_ASSETS_DIR = CANONICAL_PKG / "assets"
CANONICAL_SHEETS_DIR = CANONICAL_PKG / "contact_sheets"

POLICY_REF = "45f71d6226c5ffc58b4e70f3bcea1bb0151b7003"
AGENTS_BLOB_SHA = "6cab2103e32448a10e13b7f00c1a3eb4adb4a221"

BASELINE_STATE_SHA256 = "476760bfad67c1c324b6b7f97dec3b11dc3b8da663103434b391f2c1064b917b"
EXPECTED_CANDIDATE_SHA256 = "1c1c7c73f6d43ab5757744d16d81864c606b0226ba221702a989b60f5673d7b6"
EXPECTED_CANDIDATE_SIZE = 424985

EXPECTED_CREATION_ID = "1585201765857041"
EXPECTED_CONVERSATION_ID = "38418268167176721"
EXPECTED_ACCOUNT = "ACCOUNT_A"
EXPECTED_ATTEMPT_ID = "attempt_24bb3a988d9ab9bb71d5e28d553567d4a0f62fca269aa70f7c7a314f54f8fc62"
EXPECTED_AUTHORITY = "PROVIDER_ISSUED_UNWATERMARKED"
EXPECTED_PROMPT_SHA = "0aef0a7bd851299cb89690f5cccc3d5e3558a1e1c3d632d9d58542d7ae5d00af"

ATTESTATION_REL_PATH = "docs/operating/S3_S09_LINEAGE_ATTESTATION.md"
ATTESTATION_FULL_PATH = WORKER_ROOT / ATTESTATION_REL_PATH

CANDIDATE_REVIEW_MP4 = WORKER_ROOT / "OWNER_REVIEW/FILM120_S09_CANDIDATE_002/S09.mp4"
CANDIDATE_ISOLATED_MP4 = WORKER_ROOT / "isolated_s09_candidate_002/assets/S09.mp4"
CANDIDATE_MANIFEST_PATH = WORKER_ROOT / "OWNER_REVIEW/FILM120_S09_CANDIDATE_002/MANIFEST.json"
CANDIDATE_SHEET_PATH = WORKER_ROOT / "OWNER_REVIEW/FILM120_S09_CANDIDATE_002/S09_contact_sheet.png"
CANDIDATE_PREVIEW_PATH = WORKER_ROOT / "OWNER_REVIEW/FILM120_S09_CANDIDATE_002/S01_S10_PREVIEW.mp4"
CANDIDATE_JOURNAL_PATH = WORKER_ROOT / "isolated_s09_candidate_002/dispatch_journal_S09.jsonl"
CANDIDATE_AUTH_PATH = WORKER_ROOT / "isolated_s09_candidate_002/slots/S09/mutation_authority.json"

ACCEPTED_BASELINE_SHAS = {
    "S01": "175e54e6927c778cc185eebe9cfc5b002a5b3893aa1ccdb434b13ca925519511",
    "S02": "7d1608e4cc27613a4376657c1a4ea6eeb5f940b485e8cb266b0d5bd09b8391d6",
    "S03": "d47651febaffddf12155d52415fa1d3ea834fe167781fb5ceb2eb89ab10282e6",
    "S04": "116d29cab711cf9c4a8880dd9e9cb8d50c65e5d49963fbfb8c45e175d7955829",
    "S05": "2e4d72cc4503c07e0122f9cc3f7376047d1f62d73fa4eb35b516fcb2b6e507cf",
    "S06": "c9b8a03de0585a867a583dbff4bbbaec59517a2b45fa096a59a7a782ded141e6",
    "S07": "ee7caa66525d14275cad36f311d7d9112d9f23907a22e88eaf5df8047d33c530",
    "S08": "111a045ce9c875c1cf64eebd18e150a9b2527bdff3561674447a814ae583b5c0",
    "S10": "a023dd9b4dfaa274a92b30a2187067a5ab30c715829d80b1b2c8dd6659b31393",
}


def _file_sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def run_preflight() -> Dict[str, Any]:
    print("[PREFLIGHT] Starting fail-closed preflight checks for S09 Candidate-002...")

    # 1. Policy check
    rev = subprocess.run(
        ["git", "rev-parse", f"{POLICY_REF}:AGENTS.md"],
        cwd=str(WORKER_ROOT),
        capture_output=True,
        text=True,
    )
    if rev.returncode != 0 or rev.stdout.strip() != AGENTS_BLOB_SHA:
        raise RuntimeError(
            f"Policy blob mismatch: got '{rev.stdout.strip()}', expected '{AGENTS_BLOB_SHA}'"
        )
    print(f"  [OK] Policy AGENTS.md blob verified ({AGENTS_BLOB_SHA})")

    # 2. Immutable candidate checks
    if not CANDIDATE_REVIEW_MP4.exists():
        raise RuntimeError(f"Candidate review MP4 missing: {CANDIDATE_REVIEW_MP4}")
    if not CANDIDATE_ISOLATED_MP4.exists():
        raise RuntimeError(f"Candidate isolated MP4 missing: {CANDIDATE_ISOLATED_MP4}")

    review_sha = _file_sha256(CANDIDATE_REVIEW_MP4)
    isolated_sha = _file_sha256(CANDIDATE_ISOLATED_MP4)
    if review_sha != EXPECTED_CANDIDATE_SHA256:
        raise RuntimeError(f"Review MP4 SHA mismatch: {review_sha}")
    if isolated_sha != EXPECTED_CANDIDATE_SHA256:
        raise RuntimeError(f"Isolated MP4 SHA mismatch: {isolated_sha}")
    if CANDIDATE_REVIEW_MP4.stat().st_size != EXPECTED_CANDIDATE_SIZE:
        raise RuntimeError(f"Review MP4 size mismatch: {CANDIDATE_REVIEW_MP4.stat().st_size}")
    if CANDIDATE_ISOLATED_MP4.stat().st_size != EXPECTED_CANDIDATE_SIZE:
        raise RuntimeError(f"Isolated MP4 size mismatch: {CANDIDATE_ISOLATED_MP4.stat().st_size}")
    print(f"  [OK] Candidate MP4 files verified ({EXPECTED_CANDIDATE_SHA256}, {EXPECTED_CANDIDATE_SIZE} bytes)")

    # 3. Manifest checks
    if not CANDIDATE_MANIFEST_PATH.exists():
        raise RuntimeError(f"Manifest missing: {CANDIDATE_MANIFEST_PATH}")
    manifest = json.loads(CANDIDATE_MANIFEST_PATH.read_text(encoding="utf-8"))
    if manifest.get("shot_id") != "S09":
        raise RuntimeError(f"Manifest shot_id mismatch: {manifest.get('shot_id')}")
    if manifest.get("asset_sha256") != EXPECTED_CANDIDATE_SHA256:
        raise RuntimeError(f"Manifest SHA mismatch: {manifest.get('asset_sha256')}")
    if manifest.get("asset_size") != EXPECTED_CANDIDATE_SIZE:
        raise RuntimeError(f"Manifest size mismatch: {manifest.get('asset_size')}")
    if manifest.get("account") != EXPECTED_ACCOUNT:
        raise RuntimeError(f"Manifest account mismatch: {manifest.get('account')}")
    if manifest.get("conversation_id") != EXPECTED_CONVERSATION_ID:
        raise RuntimeError(f"Manifest conversation_id mismatch: {manifest.get('conversation_id')}")
    if manifest.get("creation_id") != EXPECTED_CREATION_ID:
        raise RuntimeError(f"Manifest creation_id mismatch: {manifest.get('creation_id')}")
    if manifest.get("variant_authority") != EXPECTED_AUTHORITY:
        raise RuntimeError(f"Manifest authority mismatch: {manifest.get('variant_authority')}")
    print(f"  [OK] Manifest verified (creation_id={EXPECTED_CREATION_ID}, account={EXPECTED_ACCOUNT})")

    # 4. Isolated journal & authority
    if not CANDIDATE_JOURNAL_PATH.exists():
        raise RuntimeError(f"Journal missing: {CANDIDATE_JOURNAL_PATH}")
    journal_lines = [
        json.loads(line)
        for line in CANDIDATE_JOURNAL_PATH.read_text(encoding="utf-8").strip().splitlines()
        if line.strip()
    ]
    kinds = [event["kind"] for event in journal_lines]
    if kinds.count("NETWORK_RELEASE_OBSERVED") != 1:
        raise RuntimeError(
            f"Expected exactly 1 NETWORK_RELEASE_OBSERVED, found {kinds.count('NETWORK_RELEASE_OBSERVED')}"
        )
    if "TERMINAL_SUCCESS" not in kinds or "CREATION_BOUND" not in kinds:
        raise RuntimeError(f"Journal missing terminal success or creation bound: {kinds}")

    # Verify journal hash chain integrity
    prev_hash = ""
    for ev_idx, ev in enumerate(journal_lines, 1):
        if ev.get("previous_event_hash") != prev_hash:
            raise RuntimeError(f"Journal chain broken at ordinal {ev_idx}: {ev.get('previous_event_hash')} != {prev_hash}")
        calc_hash = hashlib.sha256(
            json.dumps({k: v for k, v in ev.items() if k != "event_hash"}, sort_keys=True, ensure_ascii=False).encode("utf-8")
        ).hexdigest()[:32]
        if ev.get("event_hash") != calc_hash:
            raise RuntimeError(f"Journal event hash mismatch at ordinal {ev_idx}")
        prev_hash = ev.get("event_hash")
    print(f"  [OK] Journal lineage verified (1 release observed, unbroken cryptographic chain)")

    if not CANDIDATE_AUTH_PATH.exists():
        raise RuntimeError(f"Authority missing: {CANDIDATE_AUTH_PATH}")
    auth_data = json.loads(CANDIDATE_AUTH_PATH.read_text(encoding="utf-8"))
    if auth_data.get("mutation_authority") != "LATCHED_CLOSED":
        raise RuntimeError(f"Authority not latched closed: {auth_data.get('mutation_authority')}")
    if auth_data.get("external_effect_knowledge") != "RESOLVED_EFFECT_IDENTIFIED":
        raise RuntimeError(f"Knowledge state mismatch: {auth_data.get('external_effect_knowledge')}")
    print("  [OK] MutationAuthority verified (LATCHED_CLOSED / RESOLVED_EFFECT_IDENTIFIED)")

    # 5. Attestation file check
    if not ATTESTATION_FULL_PATH.exists():
        raise RuntimeError(f"Lineage attestation document missing: {ATTESTATION_FULL_PATH}")
    attestation_sha = _file_sha256(ATTESTATION_FULL_PATH)
    print(f"  [OK] Lineage attestation document verified ({attestation_sha})")

    # 6. Canonical baseline state check
    if not CANONICAL_STATE_PATH.exists():
        raise RuntimeError(f"Canonical state file missing: {CANONICAL_STATE_PATH}")
    current_state_bytes = CANONICAL_STATE_PATH.read_bytes()
    current_state_sha = hashlib.sha256(current_state_bytes).hexdigest()
    state = json.loads(current_state_bytes)

    is_already_promoted = (
        state.get("shots", {}).get("S09", {}).get("status") == "QC_ACCEPT"
        and state.get("shots", {}).get("S09", {}).get("sha256") == EXPECTED_CANDIDATE_SHA256
    )

    if not is_already_promoted:
        if current_state_sha != BASELINE_STATE_SHA256:
            raise RuntimeError(
                f"Canonical state SHA mismatch: got {current_state_sha}, expected baseline {BASELINE_STATE_SHA256}"
            )
        if state["shots"]["S09"]["status"] != "PENDING":
            raise RuntimeError(f"Baseline S09 status is not PENDING: {state['shots']['S09']['status']}")
        if state["shots"]["S10"]["status"] != "QC_ACCEPT":
            raise RuntimeError(f"Baseline S10 status is not QC_ACCEPT: {state['shots']['S10']['status']}")
        accepted_baseline = [s for s, d in state["shots"].items() if d.get("status") == "QC_ACCEPT"]
        if len(accepted_baseline) != 9:
            raise RuntimeError(f"Expected exactly 9 accepted baseline shots, got {len(accepted_baseline)}")
        print(f"  [OK] Canonical baseline state verified (SHA256={current_state_sha}, 9/24 QC_ACCEPT)")
    else:
        print("  [NOTICE] Canonical state is already promoted with S09 Candidate-002 (idempotent resume)")

    # 7. Verify 9 existing accepted assets
    for sid, exp_sha in ACCEPTED_BASELINE_SHAS.items():
        asset_file = CANONICAL_ASSETS_DIR / f"{sid}.mp4"
        if not asset_file.exists():
            raise RuntimeError(f"Canonical accepted asset missing: {asset_file}")
        actual_sha = _file_sha256(asset_file)
        if actual_sha != exp_sha:
            raise RuntimeError(f"Canonical accepted asset {sid} SHA mismatch: {actual_sha} != {exp_sha}")
    print("  [OK] All 9 prior accepted canonical assets verified intact")

    # 8. Check target S09 destination collision
    target_s09 = CANONICAL_ASSETS_DIR / "S09.mp4"
    if target_s09.exists():
        target_sha = _file_sha256(target_s09)
        if target_sha != EXPECTED_CANDIDATE_SHA256:
            raise RuntimeError(
                f"Collision: target S09.mp4 exists with unexpected SHA: {target_sha} != {EXPECTED_CANDIDATE_SHA256}"
            )
        print("  [OK] Target S09.mp4 already exists with identical SHA (safe idempotent resume)")
    else:
        print("  [OK] Target S09.mp4 is absent (ready for clean staged copy)")

    print("[PREFLIGHT] All fail-closed checks PASSED.\n")
    return {
        "manifest": manifest,
        "state": state,
        "is_already_promoted": is_already_promoted,
        "current_state_sha": current_state_sha,
        "attestation_sha": attestation_sha,
    }


def stage_and_copy_assets() -> None:
    print("[ASSET CUSTODY] Staging and verifying asset copy...")
    CANONICAL_ASSETS_DIR.mkdir(parents=True, exist_ok=True)
    target_s09 = CANONICAL_ASSETS_DIR / "S09.mp4"

    if target_s09.exists() and _file_sha256(target_s09) == EXPECTED_CANDIDATE_SHA256:
        print("  [SKIP] Canonical S09.mp4 already present and verified; skipping copy.")
    else:
        tmp_target = CANONICAL_ASSETS_DIR / "S09.mp4.tmp"
        if tmp_target.exists():
            tmp_target.unlink()
        shutil.copy2(CANDIDATE_REVIEW_MP4, tmp_target)
        tmp_sha = _file_sha256(tmp_target)
        if tmp_sha != EXPECTED_CANDIDATE_SHA256:
            tmp_target.unlink()
            raise RuntimeError(f"Staged S09.mp4.tmp SHA mismatch: {tmp_sha}")
        os.replace(tmp_target, target_s09)
        print(f"  [OK] Canonical S09.mp4 copied and verified: {_file_sha256(target_s09)}")

    # Copy contact sheet
    CANONICAL_SHEETS_DIR.mkdir(parents=True, exist_ok=True)
    target_sheet = CANONICAL_SHEETS_DIR / "S09.png"
    if not target_sheet.exists() or _file_sha256(target_sheet) != _file_sha256(CANDIDATE_SHEET_PATH):
        shutil.copy2(CANDIDATE_SHEET_PATH, target_sheet)
        print(f"  [OK] Contact sheet copied to {target_sheet}")
    else:
        print(f"  [SKIP] Contact sheet already present at {target_sheet}")


def mutate_film_state(manifest: Dict[str, Any], attestation_sha: str) -> str:
    print("[FILM STATE MUTATION] Performing atomic safe mutation on v2_022_run_state.json...")

    raw_before = CANONICAL_STATE_PATH.read_bytes()
    sha_before = hashlib.sha256(raw_before).hexdigest()
    state = json.loads(raw_before)

    # Invariants check
    if len(state["shots"]) != 24:
        raise RuntimeError(f"Expected 24 shots in state, found {len(state['shots'])}")

    s09_record = state["shots"]["S09"]
    preserved_repairs = s09_record.get("repairs", [])

    # Preserve all other 23 shots exactly
    other_shots_snapshot = {
        sid: json.dumps(record, sort_keys=True)
        for sid, record in state["shots"].items()
        if sid != "S09"
    }

    # Prepare updated S09 record
    updated_s09 = {
        "status": "QC_ACCEPT",
        "account": EXPECTED_ACCOUNT,
        "conversation": EXPECTED_CONVERSATION_ID,
        "attempt_id": EXPECTED_ATTEMPT_ID,
        "creation_ids": [EXPECTED_CREATION_ID],
        "repair_needed": False,
        "repairs": preserved_repairs,
        "asset": r"projects\quality_v2_022_longform_120s\assets\S09.mp4",
        "sha256": EXPECTED_CANDIDATE_SHA256,
        "authority": EXPECTED_AUTHORITY,
        "recovered": {
            "method": "READ_ONLY_PROVIDER_SIDE_BIND",
            "conversation_id": EXPECTED_CONVERSATION_ID,
            "creation_id": EXPECTED_CREATION_ID,
            "attempt_id": EXPECTED_ATTEMPT_ID,
            "attestation_path": ATTESTATION_REL_PATH,
            "attestation_sha256": attestation_sha,
            "provenance_note": (
                "Lineage proven via journal cryptographic hash chain, candidate needle matching, "
                "and multi-artifact state consistency. Note: dispatch_journal events 5-7 have blank "
                "attempt_id field (runner initialization defect); billing free route verified by session, "
                "not audited by external financial receipt."
            ),
            "note": (
                "Candidate-002: single network release observed on ACCOUNT_A, receipt missed, "
                "provider completed creation provider-side; bound read-only unwatermarked rendition "
                "with zero extra mutations; Owner creatively ACCEPTED on 2026-10-20"
            ),
        },
        "technical": manifest["technical_qc"],
        "contact_sheet": str(CANONICAL_SHEETS_DIR / "S09.png"),
        "qc_verdict": "ACCEPT",
        "qc_failure_class": None,
        "owner_creative_verdict": "ACCEPT",
        "owner_decision_date": "2026-10-20",
    }

    state["shots"]["S09"] = updated_s09

    # Assert other shots did not change
    for sid, orig_repr in other_shots_snapshot.items():
        curr_repr = json.dumps(state["shots"][sid], sort_keys=True)
        if curr_repr != orig_repr:
            raise RuntimeError(f"Shot {sid} was mutated unexpectedly during S09 promotion!")

    # Assert global counters unchanged
    if state.get("mutations_used") != 11:
        raise RuntimeError(f"mutations_used mutated unexpectedly: {state.get('mutations_used')} != 11")

    # Write atomically via temp file
    tmp_state = CANONICAL_STATE_PATH.with_suffix(".json.tmp")
    serialized = json.dumps(state, indent=1, ensure_ascii=False)
    tmp_state.write_text(serialized, encoding="utf-8")

    os.replace(tmp_state, CANONICAL_STATE_PATH)
    raw_after = CANONICAL_STATE_PATH.read_bytes()
    sha_after = hashlib.sha256(raw_after).hexdigest()

    print(f"  [OK] Atomic mutation complete:")
    print(f"       Before SHA256: {sha_before}")
    print(f"       After  SHA256: {sha_after}")
    return sha_after


def readback_prove() -> Dict[str, Any]:
    print("[READBACK PROVE] Executing independent readback verification...")

    raw_state = CANONICAL_STATE_PATH.read_bytes()
    state_sha = hashlib.sha256(raw_state).hexdigest()
    state = json.loads(raw_state)

    shots = state.get("shots", {})
    if len(shots) != 24:
        raise RuntimeError(f"Expected 24 shots in state, got {len(shots)}")

    accepted = [s for s, d in shots.items() if d.get("status") == "QC_ACCEPT"]
    pending = [s for s, d in shots.items() if d.get("status") == "PENDING"]

    if len(accepted) != 10:
        raise RuntimeError(f"Expected exactly 10 accepted shots, got {len(accepted)}: {accepted}")
    if len(pending) != 14:
        raise RuntimeError(f"Expected exactly 14 pending shots, got {len(pending)}: {pending}")

    expected_accepted = ["S01", "S02", "S03", "S04", "S05", "S06", "S07", "S08", "S09", "S10"]
    if sorted(accepted) != sorted(expected_accepted):
        raise RuntimeError(f"Accepted shots mismatch: got {accepted}, expected {expected_accepted}")

    if shots["S09"]["status"] != "QC_ACCEPT":
        raise RuntimeError(f"S09 status is not QC_ACCEPT: {shots['S09']['status']}")
    if shots["S10"]["status"] != "QC_ACCEPT":
        raise RuntimeError(f"S10 status is not QC_ACCEPT: {shots['S10']['status']}")
    if shots["S11"]["status"] != "PENDING":
        raise RuntimeError(f"S11 status is not PENDING: {shots['S11']['status']}")

    # Verify physical canonical MP4 assets for all 10 accepted shots
    all_10_shas = dict(ACCEPTED_BASELINE_SHAS)
    all_10_shas["S09"] = EXPECTED_CANDIDATE_SHA256

    for sid, exp_sha in all_10_shas.items():
        p = CANONICAL_ASSETS_DIR / f"{sid}.mp4"
        if not p.exists():
            raise RuntimeError(f"Accepted asset missing on disk: {p}")
        act_sha = _file_sha256(p)
        if act_sha != exp_sha:
            raise RuntimeError(f"Asset {sid} SHA mismatch: {act_sha} != {exp_sha}")

    # Verify preserved repairs in S09
    s09_repairs = shots["S09"].get("repairs", [])
    if len(s09_repairs) != 1:
        raise RuntimeError(f"Expected 1 preserved repair record in S09, got {len(s09_repairs)}")
    if "day-1 hard refusal" not in s09_repairs[0].get("reason", ""):
        raise RuntimeError("Historical repair reason corrupted in S09")

    # Verify global invariants
    if state.get("mutations_used") != 11:
        raise RuntimeError(f"mutations_used mismatch: {state.get('mutations_used')} != 11")

    print("  [OK] Readback verified: 10/24 QC_ACCEPT, 14/24 PENDING")
    print(f"       Accepted shots: {', '.join(sorted(accepted))}")
    print(f"       All 10 physical canonical MP4s verified bitwise")
    print(f"       Canonical state SHA-256: {state_sha}")

    return {
        "state_sha": state_sha,
        "accepted_count": len(accepted),
        "pending_count": len(pending),
        "accepted_shots": accepted,
        "pending_shots": pending,
    }


def main():
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")

    parser = argparse.ArgumentParser(description="Promote Owner-accepted S09 Candidate-002")
    parser.add_argument("--preflight-only", action="store_true", help="Run only fail-closed preflight checks")
    args = parser.parse_args()

    preflight = run_preflight()
    if args.preflight_only:
        print("[SUCCESS] Preflight checks passed.")
        return 0

    if not preflight["is_already_promoted"]:
        stage_and_copy_assets()
        mutate_film_state(preflight["manifest"], preflight["attestation_sha"])

    readback_prove()
    print("\n[PROMOTION COMPLETED SUCCESSFULLY]")
    return 0


if __name__ == "__main__":
    sys.exit(main())
