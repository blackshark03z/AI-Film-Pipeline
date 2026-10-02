"""FLOW-FORENSIC-TO-DOLA-001 C2 — read-only differential between the two
known Flow projects. No mutation of any kind; every read is qualified.

A = a94d36d0-5f95-420d-97b4-dc7cf0c87453  (historical manual-UI success 8d88d601)
B = f6b40e79-d6f8-4354-80ae-c863260e96f5  (UI canary success a47636b8; all
    other releases null/no-delta)

Captured per project (sanitized only):
- session metadata (via contract.sanitize_session);
- frontend build label `bl` and locale;
- catalog ids + record-count, plus the known successful output records'
  lineage slots (display-prompt marker presence, model slot, reference slot);
- high-demand/outage banner detection from the page text (boolean + phrase
  class only);
- native UI settings summary tokens (no gating).
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from film_pipeline.core import canonical_json
from film_pipeline.providers import flow_rpc_contract as contract
from film_pipeline.providers.flow_reference_rpc import (
    FlowReferenceRpcDrift,
    FlowReferenceRpcSession,
    OwnerAuthRequired,
)

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "projects/flow_forensic_dola_20261002/c2_differential"

PROJECT_A = "a94d36d0-5f95-420d-97b4-dc7cf0c87453"
PROJECT_B = "f6b40e79-d6f8-4354-80ae-c863260e96f5"
SUCCESS_B_OUTPUT = "a47636b8-f7fb-4d99-8100-4cb5d989da8d"
SUCCESS_A_OUTPUT = "8d88d601-8c8d-493b-aabf-26a18d6030c5"
REFERENCE_B_SUCCESS = "347f9951-5bbc-4910-b6fd-3a17c74e29d2"
REFERENCE_B_FAILING = "53b5a413-7bb5-4f97-9be4-2461794a7d80"
PROFILE = Path("D:/Video/AutoVideoPipeline/scratch/google_flow_slice0011_manual")

BANNER_PHRASES = {
    "high_demand_en": "high demand",
    "high_demand_vi": "gi nhu cầu cao",
    "affecting_video_en": "affecting video generation",
    "refunds_en": "will be refunded",
    "unusual_activity": "unusual activity",
}


def project_read(session: FlowReferenceRpcSession, project_id: str,
                 success_output: str) -> dict:
    report = {"project_id": project_id}
    meta = session.metadata()
    report["session"] = contract.sanitize_session(meta, project_id)
    report["bl"] = meta.get("bl", "")
    # Banner detection from the rendered page text (phrase classes only).
    body_text = session.page.locator("body").inner_text(timeout=10000).lower()
    banners = [name for name, phrase in BANNER_PHRASES.items() if phrase in body_text]
    report["banner_phrase_classes"] = banners
    # Catalog (current parser; also probe the default parser like the runtime does).
    try:
        session.catalog()
        report["catalog_default_parser_ok"] = True
    except FlowReferenceRpcDrift:
        report["catalog_default_parser_ok"] = False
    records = session.catalog(contract_version=contract.CONTRACT_VERSION_2026_10_01)
    report["catalog_count"] = len(records)
    report["catalog_ids"] = sorted(row[0].lower() for row in records)
    # Successful-output record lineage (sanitized slots only).
    matches = [row for row in records if row[0].lower() == success_output]
    if len(matches) == 1:
        row = matches[0]
        lineage = {}
        try:
            display = row[5][1]
            lineage["display_prompt_slot_present"] = isinstance(display, str)
            lineage["display_prompt_sha256"] = hashlib.sha256(display.encode()).hexdigest()
            lineage["row_length"] = len(row)
            lineage["status"] = row[3]
            model_slot = row[5][6][1][0][0]
            lineage["model_slot"] = model_slot
            refs = row[5][6][1][1]
            lineage["reference_slot"] = [[item[0], item[2]] if isinstance(item, list) and len(item) >= 3 else item for item in refs] if isinstance(refs, list) else None
        except (IndexError, TypeError, KeyError):
            lineage["shape"] = "UNPARSED"
        report["success_output_record"] = lineage
    else:
        report["success_output_record"] = None
    # Settings summary (no gating; transport representation only).
    try:
        summary = session.page.locator("button.settings-trigger-button")
        if summary.count() == 1:
            report["ui_settings_tokens"] = summary.inner_text().split()
        else:
            report["ui_settings_tokens"] = None
    except Exception:
        report["ui_settings_tokens"] = None
    report["rpc_calls"] = dict(session.rpc_call_counts)
    return report


def run() -> dict:
    OUT.mkdir(parents=True, exist_ok=True)
    target = OUT / "differential.json"
    if target.exists():
        raise SystemExit("differential evidence already recorded")
    result = {"stage": "C2_READ_ONLY_DIFFERENTIAL", "projects": {}}
    for project_id, success_output in ((PROJECT_B, SUCCESS_B_OUTPUT), (PROJECT_A, SUCCESS_A_OUTPUT)):
        session = FlowReferenceRpcSession(profile_path=PROFILE, project_id=project_id,
                                          native_ui=True)
        try:
            with session:
                session.page.context.route("**/batchexecute?*", _blocker())
                result["projects"][project_id] = project_read(session, project_id, success_output)
        except OwnerAuthRequired:
            result["projects"][project_id] = {"project_id": project_id,
                                              "gate": "OWNER_GATE_AUTH_REQUIRED"}
        except Exception as exc:
            result["projects"][project_id] = {"project_id": project_id,
                                              "stop_type": type(exc).__name__}
    result["differential"] = {
        "same_frontend_host": (result["projects"][PROJECT_B].get("session", {}).get("host")
                               == result["projects"][PROJECT_A].get("session", {}).get("host")),
        "bl_builds": {pid: result["projects"][pid].get("bl") for pid in (PROJECT_A, PROJECT_B)},
        "banners": {pid: result["projects"][pid].get("banner_phrase_classes")
                    for pid in (PROJECT_A, PROJECT_B)},
        "catalog_counts": {pid: result["projects"][pid].get("catalog_count")
                           for pid in (PROJECT_A, PROJECT_B)},
        "success_reference_present_in_B": REFERENCE_B_SUCCESS in (result["projects"][PROJECT_B].get("catalog_ids") or []),
        "failing_reference_present_in_B": REFERENCE_B_FAILING in (result["projects"][PROJECT_B].get("catalog_ids") or []),
    }
    target.write_text(canonical_json(result), encoding="utf-8")
    print(json.dumps(result["differential"], indent=1))
    return result


def _blocker():
    """Abort any generation/upload RPC; nothing here may mutate."""
    def route(route):
        request = route.request
        body = request.post_data or ""
        if any(token in request.url or token in body for token in ("MZZa6b", "maseQ")):
            route.abort()
            raise RuntimeError("READ_ONLY_DIFFERENTIAL_MUTATION_BLOCKED")
        route.continue_()
    return route


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    args = parser.parse_args()
    run()
