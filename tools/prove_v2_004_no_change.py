"""AI-FILM-QUALITY-V2-004 — Phase 11 (canonical no-change proof)."""
from __future__ import annotations

import hashlib
import json
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PKG = ROOT / "projects/quality_v2_004_f2_blocking"
MASTER = (ROOT / "projects/flow_editorial_runtime_scale_010/"
          "master_package_010/master_editorial_010_v1.mp4")
BASELINE_F2 = (ROOT / "projects/flow_upload_contract_requal_009/reproof/"
               "scene_SCENE_F_STORM_GATE/shot_SEQ7_F2C/videos/"
               "c1a69047933565230870ad22.mp4")
F2_CANONICAL_SHA = ("e84ba56ccd0f556e3eebe8ccf83def5"
                    "67118a59b87a463c8c39898254890a767")


def file_sha(path: Path) -> str:
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def main() -> int:
    dirty = [ln for ln in subprocess.run(
        ["git", "status", "--porcelain"], cwd=ROOT, capture_output=True,
        text=True).stdout.splitlines() if not ln.startswith("??")]
    proof = {
        "version": "v2-004-canonical-no-change-proof-v1",
        "checkpoint": "V2004_P11_CANONICAL_UNCHANGED",
        "canonical_master_sha256_expected":
            "976876a1a24a0fe50ea5cff9ea24694f1196ec0faf25edec3a5f1afda17865"
            "95",
        "canonical_master_sha256_actual": file_sha(MASTER),
        "canonical_master_unchanged": file_sha(MASTER) ==
            "976876a1a24a0fe50ea5cff9ea24694f1196ec0faf25edec3a5f1afda17865"
            "95",
        "canonical_f2_take_sha256_actual": file_sha(BASELINE_F2),
        "canonical_f2_take_unchanged":
            file_sha(BASELINE_F2) == F2_CANONICAL_SHA,
        "edit_manifest_unchanged": json.loads(
            (ROOT / "projects/flow_editorial_runtime_scale_010/"
             "master_package_010/master_summary.json").read_text(
                encoding="utf-8"))["edit_manifest_id"] ==
            "edit_c82343ee78951fadcd7a4bf9e94fb6107ec2ba18a4feca6590654b05"
            "9c7969d3",
        "v1_tracked_files_modified": dirty,
        "v1_tracked_files_clean": not dirty,
        "promotion_ledger": "EMPTY (no promotion transaction proposed or "
                            "executed)",
        "canonical_mutation": 0}
    (PKG / "canonical_no_change_v2_004.json").write_text(
        json.dumps(proof, indent=1, ensure_ascii=False), encoding="utf-8")
    ok = (proof["canonical_master_unchanged"] and
          proof["canonical_f2_take_unchanged"] and
          proof["edit_manifest_unchanged"] and
          proof["v1_tracked_files_clean"])
    print(json.dumps({"checkpoint": "V2004_P11_CANONICAL_UNCHANGED",
                      "result": "UNCHANGED" if ok else "MUTATED"}))
    if not ok:
        raise SystemExit(1)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
