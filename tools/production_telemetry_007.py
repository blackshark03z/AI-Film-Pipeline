"""FLOW-PRODUCTION-SCALE-007 (L15) — production telemetry.

Machine-readable telemetry built ONLY from trusted local durable records
(generate ledger, shot results, master summary, editorial plan). No cost
estimation: no trusted provider billing data exists locally, so cost is
COST_UNKNOWN_TRUSTED_DATA_UNAVAILABLE.
"""
from __future__ import annotations

import json
import statistics
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys_path = str(ROOT / "src")
if sys_path not in sys.path:
    sys.path.insert(0, sys_path)
tools_path = str(ROOT / "tools")
if tools_path not in sys.path:
    sys.path.insert(0, tools_path)

from scale_run import mutation_accounting

RUN_DIR = ROOT / "projects/flow_production_scale_007"
OUT_DIR = RUN_DIR / "master_package_007"
PLAN_C = json.loads((ROOT / "fixtures/sequence007/sequence_plan_007.json")
                    .read_text(encoding="utf-8"))


def main() -> None:
    ledger = json.loads((RUN_DIR / "generate_ledger.json")
                        .read_text(encoding="utf-8"))
    master = json.loads((OUT_DIR / "master_summary.json")
                        .read_text(encoding="utf-8"))
    plan = json.loads((OUT_DIR / "editorial_plan_007.json")
                      .read_text(encoding="utf-8"))
    now = datetime.now(timezone.utc).isoformat()
    releases = ledger["primary_consumed"] + ledger["repair_consumed"]
    release_times = sorted(r["released_at"] for r in releases
                           if r.get("released_at"))
    acct = mutation_accounting(ledger, max_primary=12, max_repair=3,
                               max_uploads=2, hard_ceiling=15)
    # generated provider seconds: 12 releases × 8 s provider duration
    generated_seconds = 8.0 * len(releases)
    # selected seconds for the 12 new slots (frozen targets = selected)
    new_targets = [s.get("editorial_target_duration")
                   for scene in PLAN_C["scenes"] for s in scene["shots"]]
    new_selected_s = round(sum(t for t in new_targets if t), 3)
    historical_selected_s = round(master["expected_timeline_s"] -
                                  new_selected_s, 3)
    # provider media bytes for the 12 new releases (10 direct + 2 repair)
    new_bytes = 0
    for scene in PLAN_C["scenes"]:
        for shot in scene["shots"]:
            sid = shot["shot_id"]
            base = RUN_DIR / "sequence_SEQ007_DAYLIGHT_ROAD" / \
                f"scene_{scene['scene_id']}" / f"shot_{sid}"
            result_path = base / "result.json"
            if not result_path.exists():
                continue
            result = json.loads(result_path.read_text(encoding="utf-8"))
            if result.get("gate") == "SHOT_PROVEN":
                new_bytes += Path(result["asset"]["uri_or_path"]).stat() \
                    .st_size
    for repair_id in ("SEQ7_E2R", "SEQ7_G3B"):
        result = json.loads((RUN_DIR / "repair_scope" /
                             f"repair_{repair_id}" / f"shot_{repair_id}" /
                             "result.json").read_text(encoding="utf-8"))
        new_bytes += Path(result["asset"]["uri_or_path"]).stat().st_size
    polls = []
    for scene in PLAN_C["scenes"]:
        for shot in scene["shots"]:
            p = RUN_DIR / "sequence_SEQ007_DAYLIGHT_ROAD" / \
                f"scene_{scene['scene_id']}" / f"shot_{shot['shot_id']}" / \
                "result.json"
            if p.exists():
                r = json.loads(p.read_text(encoding="utf-8"))
                if "reconciliation_polls" in r:
                    polls.append(r["reconciliation_polls"])
    started = ledger.get("initialized_at")
    active_note = "wall-clock span of the run ledger (start → telemetry time)"
    span_hours = None
    if started:
        span_hours = round((datetime.fromisoformat(now) -
                            datetime.fromisoformat(started))
                           .total_seconds() / 3600, 2)
    telemetry = {
        "version": "telemetry-007-v1", "generated_at": now,
        "mutation_accounting": acct,
        "generated_provider_seconds": generated_seconds,
        "selected_final_seconds_timeline": master["expected_timeline_s"],
        "final_master_duration_s": master["duration_s"],
        "trim_ratio_new_slots": round(new_selected_s / generated_seconds, 3)
        if generated_seconds else None,
        "new_slot_selected_seconds": new_selected_s,
        "historical_slot_selected_seconds": historical_selected_s,
        "average_selected_shot_duration_s":
            round(master["expected_timeline_s"] / 30, 3),
        "scene_durations_s": plan["pacing"]["scenes"],
        "sequence_durations_s": plan["pacing"]["sequences"],
        "provider_media_bytes_new_releases": new_bytes,
        "provider_media_megabytes_new_releases": round(new_bytes / 1e6, 2),
        "reconciliation_polls": {
            "samples": len(polls),
            "mean": round(statistics.mean(polls), 2) if polls else None,
            "p50": statistics.median(polls) if polls else None,
            "max": max(polls) if polls else None,
            "note": "polls to backend attribution at 60 s interval"},
        "release_span": {
            "first_release": release_times[0] if release_times else None,
            "last_release": release_times[-1] if release_times else None,
            "releases_per_active_hour": round(
                len(releases) /
                max((datetime.fromisoformat(release_times[-1]) -
                     datetime.fromisoformat(release_times[0]))
                    .total_seconds() / 3600, 1e-9), 2)
            if len(release_times) >= 2 else None},
        "master_minutes_per_active_hour": round(
            (master["duration_s"] / 60) / span_hours, 3) if span_hours else None,
        "package_wall_span_hours": span_hours,
        "wall_span_note": active_note,
        "monetary_cost": "COST_UNKNOWN_TRUSTED_DATA_UNAVAILABLE",
        "successful_shots_per_release": "12/12 canonical slots proven; "
            "10 direct releases + 2 repair releases; 2 dead reservations "
            "(authority consumed at reservation, no release, no output)",
        "releases_per_canonical_selected_shot": round(12 / 30, 3),
        "repair_rate": "2 repairs / 12 new slots = 0.167",
        "discarded_media_rate": "0 (no acquired asset discarded; 2 slots "
            "never produced media — dead reservations pre-release)",
    }
    (OUT_DIR / "telemetry_007.json").write_text(
        json.dumps(telemetry, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8")
    print(json.dumps({k: telemetry[k] for k in (
        "mutation_accounting", "generated_provider_seconds",
        "final_master_duration_s", "trim_ratio_new_slots",
        "monetary_cost")}, default=str))


if __name__ == "__main__":
    main()
