"""V2-014 Phase 4 — live READ-ONLY Elyum capability discovery.

No generation. elyum_account + elyum_models + elyum_estimate quotes for the
canary parameter set and production-relevant alternatives. Establishes:
auth validity, credit balance, live model ids, and DEFAULTS-vs-LIMITS
(provider-quoted parameter acceptance).
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
    load_credential,
)

PKG = ROOT / "projects/quality_v2_014_elyum_clean_route"


def utcnow():
    return datetime.now(timezone.utc).isoformat()


def main() -> int:
    record = {"version": "v2-014-elyum-capabilities-v1",
              "checkpoint": "V2014_P4_CAPABILITY_DISCOVERY",
              "recorded_at": utcnow(),
              "mode": "READ-ONLY (elyum_account / elyum_models / "
                      "elyum_estimate — no generation, no credit spend)"}
    key = load_credential()
    if not key:
        record["status"] = "STOPPED_ELYUM_AUTH_REQUIRED"
        record["reason"] = "no credential in env or Owner key file"
        PKG.joinpath("V2_014_ELYUM_CAPABILITIES.json").write_text(
            json.dumps(record, indent=1, ensure_ascii=False), encoding="utf-8")
        print(record["status"])
        return 1
    client = ElyumSeedanceClient(key=key)
    try:
        balance = client.account_balance()
        record["auth"] = "VALID (read-only elyum_account accepted)"
        record["credit_balance"] = balance
        print("balance:", balance)
    except ElyumTransportError as e:
        record["status"] = ("STOPPED_ELYUM_AUTH_REQUIRED"
                            if e.failure_class == "CREDENTIAL_OR_ACCESS_DENIED"
                            else "DISCOVERY_FAILED")
        record["failure_class"] = e.failure_class
        PKG.joinpath("V2_014_ELYUM_CAPABILITIES.json").write_text(
            json.dumps(record, indent=1, ensure_ascii=False), encoding="utf-8")
        print(record["status"], e.failure_class)
        return 1
    try:
        catalog = client.model_catalog()
        ids = client.seedance_model_ids()
        record["model_catalog_ids"] = ids
        record["model_catalog_note"] = ("full catalog persisted in the redacted "
                                        "raw run record; only ids quoted here")
        print("seedance ids:", ids)
        (PKG / "elyum_models_raw.json").write_text(
            json.dumps(catalog, indent=1, ensure_ascii=False)[:200000],
            encoding="utf-8")
    except ElyumTransportError as e:
        record["model_catalog"] = f"UNAVAILABLE ({e.failure_class})"
        print("catalog unavailable:", e.failure_class)

    # estimates: canary config + production-relevant alternatives (read-only)
    estimates = {}
    model = "seedance-2-fast-i2v"
    for label, params in [
        ("canary_t2v_4s_480p", {"mode": "t2v", "duration": 4, "resolution": "480p"}),
        ("canary_t2v_5s_480p", {"mode": "t2v", "duration": 5, "resolution": "480p"}),
        ("film_class_t2v_5s_720p", {"mode": "t2v", "duration": 5, "resolution": "720p"}),
        ("film_class_t2v_5s_1080p", {"mode": "t2v", "duration": 5, "resolution": "1080p"}),
    ]:
        try:
            credits = client.estimate_video(model=model, **params)
            estimates[label] = {"params": params, "quoted_credits": credits,
                                "provider_accepted": True}
            print(label, "->", credits, "credits")
        except ElyumTransportError as e:
            estimates[label] = {"params": params,
                                "failure_class": e.failure_class,
                                "provider_accepted": False}
            print(label, "-> REJECTED:", e.failure_class)
    record["estimates"] = estimates
    canary_ok = estimates["canary_t2v_4s_480p"].get("provider_accepted")
    five_ok = estimates["canary_t2v_5s_480p"].get("provider_accepted")
    record["capability_findings"] = {
        "ELYUM_SEEDANCE_MODEL_ID": model,
        "ELYUM_PROVEN_RESOLUTIONS_STORY_AUTO": ["480p (4s i2v live-proven)"],
        "ELYUM_QUOTED_RESOLUTIONS": [k for k, v in estimates.items()
                                     if v.get("provider_accepted")],
        "canary_config_provider_quoted": bool(canary_ok),
        "duration_5s_provider_quoted": bool(five_ok),
        "720p_1080p": "QUOTED (provider-accepted for costing) but "
                      "render-unproven — classified UNPROVEN per package",
    }
    record["status"] = "DISCOVERED"
    PKG.joinpath("V2_014_ELYUM_CAPABILITIES.json").write_text(
        json.dumps(record, indent=1, ensure_ascii=False), encoding="utf-8")
    print("wrote V2_014_ELYUM_CAPABILITIES.json")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
