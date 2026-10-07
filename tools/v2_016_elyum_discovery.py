"""V2-016 Phase 4 — Elyum read-only capability discovery (NO generation).

Enumerates the MCP tool catalog (tools/list), extracts tool schemas, and
quotes read-only estimates for the Seedance 2.5 family. No make_video call.
"""
from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from film_pipeline.providers.elyum_provider import (
    ElyumSeedanceClient,
    ElyumTransportError,
    McpToolSession,
    load_credential,
)

PKG = ROOT / "projects/quality_v2_016_seedance25_capability"


def utcnow():
    return datetime.now(timezone.utc).isoformat()


def main() -> int:
    PKG.mkdir(parents=True, exist_ok=True)
    record = {"version": "v2-016-elyum-discovery-v1",
              "checkpoint": "V2016_P4_ELYUM_READONLY",
              "recorded_at": utcnow(),
              "mode": "READ-ONLY (tools/list + elyum_account + elyum_models + "
                      "elyum_estimate — no generation)"}
    key = load_credential()
    if not key:
        record["status"] = "STOPPED_ELYUM_AUTH_REQUIRED"
        (PKG / "V2_016_ELYUM_DRAFT_CAPABILITY.json").write_text(
            json.dumps(record, indent=1), encoding="utf-8")
        return 1
    session = McpToolSession("https://elyum.ai/mcp", key)
    client = ElyumSeedanceClient(key=key, session=session)

    # ---- tools/list: the FULL tool catalog (Story Auto only used a subset) --
    try:
        raw = session._request("tools/list", {})
        tools = raw.get("tools", [])
        catalog = []
        for t in tools:
            catalog.append({
                "name": t.get("name"),
                "description": (t.get("description") or "")[:300],
            })
        record["tool_catalog"] = catalog
        record["n_tools"] = len(tools)
        print("tools:", [t["name"] for t in catalog])
        (PKG / "elyum_tools_list.json").write_text(
            json.dumps(raw, indent=1, ensure_ascii=False)[:200000],
            encoding="utf-8")
    except ElyumTransportError as e:
        record["tools_list_error"] = e.failure_class
        print("tools/list failed:", e.failure_class)

    try:
        record["credit_balance"] = client.account_balance()
        print("balance:", record["credit_balance"])
    except ElyumTransportError as e:
        record["credit_balance"] = f"UNAVAILABLE ({e.failure_class})"

    # ---- estimates for the Seedance 2.5 family (read-only) ------------------
    estimates = {}
    for model in ("seedance-2.5-t2v", "seedance-2.5-i2v",
                  "seedance-2.5-reference"):
        for label, params in (
                ("4s_480p", {"duration": 4, "resolution": "480p"}),
                ("5s_720p", {"duration": 5, "resolution": "720p"}),
                ("5s_1080p", {"duration": 5, "resolution": "1080p"})):
            mode = "i2v" if "i2v" in model or "reference" in model else "t2v"
            try:
                credits = client.estimate_video(model=model, mode=mode,
                                                **params)
                estimates[f"{model}|{mode}|{label}"] = credits
                print(f"{model} {mode} {label}: {credits} credits")
            except ElyumTransportError as e:
                estimates[f"{model}|{mode}|{label}"] = \
                    f"REJECTED:{e.failure_class}"
                print(f"{model} {mode} {label}: REJECTED {e.failure_class}")
    record["seedance_25_estimates"] = estimates

    # reference model supports video input — record the schema fact
    catalog_meta = json.loads(
        (ROOT / "projects/quality_v2_014_elyum_clean_route/"
         "elyum_models_raw.json").read_text(encoding="utf-8"))
    fam = {}
    for mid in ("seedance-2.5-t2v", "seedance-2.5-i2v",
                "seedance-2.5-reference", "seedance-2.5"):
        m = catalog_meta.get("models", {}).get(mid)
        if m:
            fam[mid] = m
    record["seedance_25_family"] = fam
    (PKG / "V2_016_ELYUM_DRAFT_CAPABILITY.json").write_text(
        json.dumps(record, indent=1, ensure_ascii=False)[:300000],
        encoding="utf-8")
    print("wrote V2_016_ELYUM_DRAFT_CAPABILITY.json")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
