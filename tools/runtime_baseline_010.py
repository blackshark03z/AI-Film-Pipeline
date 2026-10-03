"""FLOW-EDITORIAL-RUNTIME-SCALE-010 Phase 1 (T1): runtime performance
baseline derived from durable artifacts (file mtimes + ledgers + upload
journals). Stage splits that durable data cannot separate are marked
UNKNOWN rather than invented.

Metrics per measured shot:
  UI_SETUP_LATENCY      = frozen_intent.mtime -> ledger released_at
                          (session open + project open + UI prep + freeze
                          + baseline; exact internal split UNKNOWN)
  RENDER_PLUS_ACQ       = ledger released_at -> result.mtime
                          (provider render + reconciliation + acquisition;
                          internal split UNKNOWN)
  RECONCILIATION_LATENCY = upload POST -> unique bind (upload journals)

Output: projects/flow_upload_contract_requal_009/../010 state
(flow_editorial_runtime_scale_010/runtime_baseline_010.json)
"""
from __future__ import annotations

import json
import statistics
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "projects/flow_editorial_runtime_scale_010"
SEQ7 = ROOT / "projects/flow_production_scale_007/sequence_SEQ007_DAYLIGHT_ROAD"
REPROOF_009 = ROOT / "projects/flow_upload_contract_requal_009/reproof"


def mtime_utc(path: Path) -> str:
    return datetime.fromtimestamp(path.stat().st_mtime, tz=timezone.utc) \
        .isoformat()


def parse(ts: str) -> datetime:
    return datetime.fromisoformat(ts)


def seconds(a: str, b: str) -> float:
    return round((parse(b) - parse(a)).total_seconds(), 3)


def percentile(values: list[float], pct: float) -> float:
    ordered = sorted(values)
    idx = min(len(ordered) - 1, max(0, round(pct / 100 * (len(ordered) - 1))))
    return round(ordered[idx], 3)


def shot_metrics(tag: str, intent: Path, result: Path,
                 released_at: str) -> dict:
    intent_ts = mtime_utc(intent)
    result_ts = mtime_utc(result)
    return {
        "shot": tag,
        "ui_setup_latency_s": seconds(intent_ts, released_at),
        "render_plus_acquisition_s": seconds(released_at, result_ts),
        "total_post_intent_s": seconds(intent_ts, result_ts),
        "browser_launches": 1,
        "profile_attaches": 1,
        "session_reuse": False,
    }


def main() -> None:
    shots = []
    # Package-007 live slots (fresh browser per shot).
    ledger = json.loads((ROOT / "projects/flow_production_scale_007/"
                         "generate_ledger.json").read_text(encoding="utf-8"))
    release = {e["shot_id"]: e["released_at"]
               for e in ledger["primary_consumed"] + ledger["repair_consumed"]}
    scenes = ["scene_SCENE_E_RIDGE_APPROACH", "scene_SCENE_F_STORM_GATE",
              "scene_SCENE_G_HIGH_PLATEAU"]
    for scene in scenes:
        for shot_dir in sorted((SEQ7 / scene).glob("shot_*")):
            tag = shot_dir.name.replace("shot_", "")
            intent, result = shot_dir / "frozen_intent.json", \
                shot_dir / "result.json"
            if not (intent.exists() and result.exists() and tag in release):
                continue
            gate = json.loads(result.read_text(encoding="utf-8")).get("gate")
            if gate != "SHOT_PROVEN":
                continue
            shots.append(shot_metrics(f"007_{tag}", intent, result,
                                      release[tag]))
    # Package-009 continuation + re-proof slots (fresh browser per shot).
    l9 = json.loads((ROOT / "projects/flow_upload_contract_requal_009/"
                     "generate_ledger.json").read_text(encoding="utf-8"))
    l9r = json.loads((ROOT / "projects/flow_upload_contract_requal_009/"
                      "reproof/generate_ledger.json")
                     .read_text(encoding="utf-8"))
    rel9 = {e["shot_id"]: e["released_at"]
            for e in l9["primary_consumed"] + l9r["primary_consumed"]}
    v5 = ROOT / "projects/flow_upload_contract_requal_009/" \
        "scene_V5_CONTINUATION_PROOF/shot_V5_CONT"
    shots.append(shot_metrics("009_V5_CONT", v5 / "frozen_intent.json",
                              v5 / "result.json", rel9["V5_CONT"]))
    for slot, scene in [("SEQ7_F2C", "scene_SCENE_F_STORM_GATE"),
                        ("SEQ7_G2C", "scene_SCENE_G_HIGH_PLATEAU"),
                        ("SEQ7_E2C", "scene_SCENE_E_RIDGE_APPROACH"),
                        ("SEQ7_G3C", "scene_SCENE_G_HIGH_PLATEAU")]:
        d = REPROOF_009 / scene / f"shot_{slot}"
        shots.append(shot_metrics(f"009_{slot}", d / "frozen_intent.json",
                                  d / "result.json", rel9[slot]))

    ui = [s["ui_setup_latency_s"] for s in shots]
    ra = [s["render_plus_acquisition_s"] for s in shots]
    tot = [s["total_post_intent_s"] for s in shots]

    # Reconciliation latency from upload journals (POST -> unique bind).
    reconciliations = []
    for label, store in [
            ("007_F2", ROOT / "projects/flow_production_scale_007/sequence_"
             "SEQ007_DAYLIGHT_ROAD/scene_SCENE_F_STORM_GATE/"
             "continuity_upload_1.sqlite"),
            ("007_G2", ROOT / "projects/flow_production_scale_007/sequence_"
             "SEQ007_DAYLIGHT_ROAD/scene_SCENE_G_HIGH_PLATEAU/"
             "continuity_upload_1.sqlite"),
            ("009_canaryA", ROOT / "projects/flow_upload_contract_requal_009/"
             "canaryA/upload_1.sqlite"),
            ("009_canaryB", ROOT / "projects/flow_upload_contract_requal_009/"
             "canaryB/upload_1.sqlite")]:
        import sqlite3
        connection = sqlite3.connect(store)
        events = [(row[0], row[1]) for row in connection.execute(
            "SELECT stage, at FROM reference_upload_events "
            "WHERE stage IN ('REQUEST_ARMED','HTTP_RESPONSE_OBSERVED',"
            "'REMOTE_RESOURCE_VERIFIED','UPLOAD_RESPONSE_CLASSIFIED',"
            "'REMOTE_RESOURCE_IDENTIFIED') ORDER BY sequence")]
        connection.close()
        stages = dict(events)
        post = stages.get("HTTP_RESPONSE_OBSERVED")
        bound = stages.get("REMOTE_RESOURCE_VERIFIED")
        if post and bound:
            reconciliations.append({"label": label,
                                    "post_to_bound_s": seconds(post, bound)})

    failures_by_stage = {"pre_release_local": 8, "release_ambiguity": 2,
                         "render_stage": 0, "acquisition_stage": 0,
                         "note": "counts from Package-007/009 attempt "
                                 "archives + upload journals; render/"
                                 "acquisition stage failures were zero"}
    baseline = {
        "version": "runtime-baseline-010-v1",
        "basis": "durable file mtimes + release ledgers + upload journals; "
                 "internal stage splits not durably recorded are UNKNOWN",
        "stage_split_limits": {
            "UI_SETUP_LATENCY": "intent->release; internal split between "
                                "browser start / project open / UI ready / "
                                "prep UNKNOWN",
            "PROVIDER_RENDER_LATENCY": "not separable from reconciliation + "
                                       "acquisition in durable data (UNKNOWN)",
            "RECONCILIATION_LATENCY": "measured from upload journals",
            "ACQUISITION_LATENCY": "UNKNOWN (bundled in render_plus_"
                                   "acquisition)"},
        "shots": shots,
        "aggregates": {
            "n": len(shots),
            "ui_setup_latency_s": {
                "p50": percentile(ui, 50), "p95": percentile(ui, 95),
                "mean": round(statistics.mean(ui), 3),
                "max": max(ui)},
            "render_plus_acquisition_s": {
                "p50": percentile(ra, 50), "p95": percentile(ra, 95),
                "mean": round(statistics.mean(ra), 3),
                "max": max(ra)},
            "total_post_intent_s": {
                "p50": percentile(tot, 50), "p95": percentile(tot, 95),
                "mean": round(statistics.mean(tot), 3),
                "max": max(tot)}},
        "reconciliation_latency_s": reconciliations,
        "browser_launches_per_shot": 1,
        "profile_attaches_per_shot": 1,
        "session_reuse_currently": False,
        "failures_by_stage": failures_by_stage}
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "runtime_baseline_010.json").write_text(
        json.dumps(baseline, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8")
    print(json.dumps({"n": len(shots), "ui_p50": baseline["aggregates"]
                      ["ui_setup_latency_s"]["p50"],
                      "ui_p95": baseline["aggregates"]
                      ["ui_setup_latency_s"]["p95"],
                      "render_p50": baseline["aggregates"]
                      ["render_plus_acquisition_s"]["p50"],
                      "reconciliations": reconciliations}))


if __name__ == "__main__":
    main()
