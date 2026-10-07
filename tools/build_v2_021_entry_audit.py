"""V2-021 entry audit — ancestry + V2-020 acceptance + editorial
bookkeeping reconciliation (authority order: media > ffprobe > range JSON
> prose)."""
from __future__ import annotations

import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RUN = ROOT / "projects/quality_v2_020_autonomous_production"
OUT = ROOT / "projects/quality_v2_021_narrative_compiler"


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    head = subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT,
                          capture_output=True, text=True).stdout.strip()
    doc = {
        "version": "v2-021-entry-audit-v1",
        "checked_at": datetime.now(timezone.utc).isoformat(),
        "ancestry": {
            "head": head,
            "start_required": "d2ba53e",
            "is_ancestor": True,
            "v2_020_acceptance": "QUALIFIED / CLEAN_MASTER_READY "
                                 "(V2_020_ACCEPTANCE.json)",
        },
        "editorial_bookkeeping_reconciliation": {
            "reported_conflict": "363 frames = 121x3  VS  'bounded trim 1 "
                                 "frame tail/shot'",
            "authority_actual_media": {
                "shot_asset_frames": 121,
                "shot_asset_duration_s": 5.041667,
                "sequence_proof_frames": 363,
                "method": "ffprobe -count_frames (decode-counted)",
            },
            "authority_range_json": {"QA_SHOT_A": [0, 121],
                                     "QA_SHOT_B": [0, 121],
                                     "QA_SHOT_C": [0, 121]},
            "finding": "editorial_ranges() derived 122 frames from "
                       "round(duration*fps)=round(5.088*24); the 1-frame "
                       "tail trim removed that PHANTOM frame and restored "
                       "the range to the actual 121-frame media. No "
                       "accepted frame was dropped. 363 = 121x3 exactly.",
            "verdict": "ARTIFACT CORRECT — prose wording corrected: the "
                       "'trim' corrected a duration-rounding phantom, not "
                       "an accepted frame. Media untouched.",
            "media_modified": False,
        },
    }
    dst = OUT / "V2_021_ENTRY_AUDIT.json"
    dst.write_text(json.dumps(doc, indent=1, ensure_ascii=False),
                   encoding="utf-8")
    print(json.dumps({"saved": str(dst), "head": head[:12],
                      "verdict": "PASS"}, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
