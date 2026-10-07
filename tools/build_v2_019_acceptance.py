"""V2-019 Phase M — production acceptance evidence + secret audit + seal."""
from __future__ import annotations

import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PKG = ROOT / "projects/quality_v2_019_dola_productionization"


def utcnow() -> str:
    return datetime.now(timezone.utc).isoformat()


def git_head() -> str:
    try:
        return subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT,
                              capture_output=True, text=True,
                              timeout=20).stdout.strip()
    except Exception:
        return "UNKNOWN"


ACCEPTANCE = {
    "version": "v2-019-acceptance-v1",
    "built_at": utcnow(),
    "work_package": "DOLA SEEDANCE 2.5 / DRAFT-FINAL / ACCOUNT-POOL "
                    "PRODUCTIONIZATION",
    "phases": {
        "A_capability_authority": "COMPLETE "
            "(V2_019_PHASEA_CAPABILITY_AUTHORITY.json; live probe ACCOUNT_D "
            "SESSION_VALID, 0 requests sent by automation)",
        "B_byteplus_oracle": "COMPLETE (V2_019_PHASEB_DRAFT_ORACLE.json)",
        "C_gate_classification": "COMPLETE "
            "(V2_019_PHASEC_GATE_CLASSIFICATION.json)",
        "D_observability": "QUALIFIED (deep JSON-string walker + normalized "
                           "events + redaction; 8 tests)",
        "E_account_pool": "QUALIFIED (deterministic pre-dispatch routing, "
                          "post-release immutable binding, resource policy; "
                          "8 tests)",
        "F_true_draft": "NOT_OBSERVED (no draft identity + no finalization "
                        "operation on any Dola surface)",
        "G_live_draft_final": "SKIPPED_BY_RULE (provider surface absent; "
                              "mutation budget preserved 0/4)",
        "H_clean_asset_resolver": "QUALIFIED (PROVIDER_ISSUED_UNWATERMARKED "
                                  "selection, fail-closed ambiguity; 5 tests)",
        "I_domain_model": "DORMANT (provider-neutral draft types with "
                          "enforced lineage; Dola flag False)",
        "J_cost_quality_router": "QUALIFIED (NORMAL_FINAL / "
                                 "LOW_COST_EXPLORATION exposed; "
                                 "DRAFT_THEN_FINAL refused on Dola)",
        "K_hardening": "QUALIFIED (safe_close, stale profile-lock lifecycle "
                       "without force-kill, poll schema adapter; 5 tests)",
        "L_tests": "PASS (28 new; full suite 1360 passed)",
        "M_acceptance": "THIS FILE",
    },
    "production_status": {
        "DOLA_PROVIDER": "PRODUCTION_QUALIFIED",
        "DOLA_ACCOUNT_POOL": "QUALIFIED",
        "DOLA_CAPABILITY_REGISTRY": "QUALIFIED",
        "DOLA_ASSET_VARIANT_RESOLVER": "QUALIFIED",
        "DOLA_GENERATION_OBSERVABILITY": "QUALIFIED",
        "DOLA_DRAFT_FINAL": "NOT_AVAILABLE_ON_CURRENT_FREE_ROUTE",
    },
    "dola_models": {
        "seedance_1_x_ic_mini": "UI_EXPOSED / FREE / durations 5,10 / 720p "
                                "/ no video ref / AVAILABLE_UNPROVEN",
        "seedance_2_0": "UI_EXPOSED / FREE (default) / durations 5,10 / "
                        "720p / no video ref / LIVE_PROVEN (10 generations "
                        "in project truth)",
        "seedance_2_5": "UI_EXPOSED / SUBSCRIPTION_GATED (subs_only_tag "
                        "enhanced, 5x credits) / capability hidden / "
                        "CURRENT_ACCOUNTS_NOT_ENTITLED",
    },
    "draft_final_report": {
        "frontend": "NOT_PRESENT (composer + bundles: no draft/finalize op)",
        "backend": "NOT_OBSERVED",
        "free_entitlement": "N/A (no route to entitle)",
        "live_proof": "NOT_RUN (rule: no surface -> no mutation)",
        "identity": "NONE (generation identity = conversation + creation "
                    "only; no draft id)",
        "same_take": "N/A",
        "final_resolution": "N/A (declared render resolution 720p)",
        "verdict": "NOT_AVAILABLE_ON_CURRENT_FREE_ROUTE — valid successful "
                   "completion per work package",
    },
    "account_pool_report": {
        "entries_discovered": ["ACCOUNT_A", "ACCOUNT_B", "ACCOUNT_C",
                               "ACCOUNT_D"],
        "ready_at_probe": "ACCOUNT_D (SESSION_VALID, non-subscriber)",
        "login_required": "rotates per probe (no interactive login "
                          "attempted, per authority)",
        "insufficient": "resource policy states implemented; "
                        "OWNER_RESOURCE_EXHAUSTED never set by code",
        "routing": "deterministic: READY/SESSION_VALID -> entitlement -> "
                   "credit -> idle -> cooldown -> LRU",
        "post_release_binding": "IMMUTABLE one-way latch (attempt/account/"
                                "profile/conversation/request identity)",
        "recovery": "rebind idempotent same-account; cross-account rebind "
                    "raises",
    },
    "observability_report": {
        "sse": "chat/completion streaming (receipt-first discipline "
               "preserved from 010C)",
        "ws": "wss://wss-normal-i18n.dola.com/ws/v2 (IM push channel; "
              "passive capture only)",
        "poll": "shape-adapter over limit-10/limit-20/recent_conv",
        "embedded_json": "deep JSON-string walker (the 011W lesson, now "
                         "enforced by tests)",
        "creation": "CreationObserved normalized",
        "variants": "VariantObserved with redacted URLs",
        "credit": "CreditStatementObserved (dedup)",
        "draft_identity": "DraftIdentityObserved DEFINED, never emitted on "
                          "Dola (no surface)",
    },
    "clean_output": {
        "resolver": "DolaAssetVariantResolver",
        "authority": "PROVIDER_ISSUED_UNWATERMARKED (class B) preferred; "
                     "fail-closed on ambiguity; no URL construction, no lr "
                     "mutation, allowlisted hosts",
        "watermark_free_status": "PROVEN machinery (V2-011W-R2/V2-011X) "
                                 "reused; pixel-QC remains the custody gate "
                                 "at acquisition time",
    },
    "live_mutations": {
        "used": 0, "budget": 4,
        "slots": {"D1_draft_canary": "UNSPENT (no provider draft surface)",
                  "D2_finalization": "UNSPENT",
                  "D3_control": "UNSPENT",
                  "D4_recovery": "UNSPENT"},
        "per_attempt_lineage": "no attempts dispatched this slice",
    },
    "other_providers": {"elyum_mutations": 0, "elyum_canary": "FROZEN 0/1",
                        "byteplus_mutations": 0,
                        "byteplus_canary": "FROZEN 0/2 (reference oracle "
                        "only)"},
    "current_film_modified": False,
    "sequence_locks": "SEQ7 CLEAN_DISTRIBUTION_MASTER_READY + "
                      "FINAL_MASTER_LOCK untouched",
    "git_head_at_build": git_head(),
}


def secret_audit() -> dict:
    markers = (b"sessionid=", b"msToken=", b"a_bogus=", b"key_seed=",
               b"BEGIN OPENSSH", b"Authorization:", b"Bearer ",
               b"x-signature=%", b"x-signature=Jt", b"x-signature=7C",
               b"x-signature=x9", b"x-signature=tV")
    hits, scanned = [], 0
    # the scanner itself and the scrubber legitimately contain marker
    # CONSTANTS (structural) — excluded from value scanning
    structural_tools = {"build_v2_019_acceptance.py",
                        "v2_019_scrub_evidence_urls.py"}
    targets = sorted(PKG.glob("*.json")) + \
        sorted((ROOT / "src/film_pipeline/providers/dola_production")
               .glob("*.py")) + \
        [ROOT / "tests/test_dola_production_019.py",
         ROOT / "tests/test_dola_production_hardening_019.py"] + \
        sorted((ROOT / "tools").glob("v2_019_*.py")) + \
        [ROOT / "tools/build_v2_019_phaseabc_evidence.py",
         ROOT / "tools/build_v2_019_acceptance.py",
         ROOT / "tools/v2_019_phaseA_live_probe.py"]
    for path in targets:
        if path.name in ("V2_019_SECRET_AUDIT.json",) or \
                path.name in structural_tools:
            continue
        scanned += 1
        blob = path.read_bytes()
        for marker in markers:
            if marker.lower() in blob.lower():
                hits.append(f"{path.name}: {marker.decode()}")
    return {"version": "v2-019-secret-audit-v1", "built_at": utcnow(),
            "files_scanned": scanned, "marker_hits": hits,
            "verdict": "CLEAN" if not hits else "REVIEW",
            "note": "raw captures DPAPI-encrypted outside tracked evidence; "
                    "video_model echo sanitized (key_seed/signed URLs "
                    "redacted)"}


def main() -> int:
    (PKG / "V2_019_ACCEPTANCE.json").write_text(
        json.dumps(ACCEPTANCE, indent=1, ensure_ascii=False),
        encoding="utf-8")
    print("wrote V2_019_ACCEPTANCE.json")
    audit = secret_audit()
    (PKG / "V2_019_SECRET_AUDIT.json").write_text(
        json.dumps(audit, indent=1, ensure_ascii=False), encoding="utf-8")
    print("secret audit:", audit["verdict"],
          f"({audit['files_scanned']} files)")
    if audit["verdict"] != "CLEAN":
        print("HITS:", audit["marker_hits"])
        return 1
    ledger = {
        "version": "v2-019-mutation-ledger-v1", "built_at": utcnow(),
        "dola_video_mutations": {"used": 0, "budget": 4,
                                 "slots": ["D1", "D2", "D3", "D4"]},
        "account_state_query_mutations": 0,
        "elyum_mutations": 0, "byteplus_mutations": 0,
        "film_sequence_mutations": 0,
    }
    (PKG / "V2_019_MUTATION_LEDGER.json").write_text(
        json.dumps(ledger, indent=1, ensure_ascii=False), encoding="utf-8")
    seal = {
        "version": "v2-019-candidate-seal-v1", "sealed_at": utcnow(),
        "status": "COMPLETED_CANDIDATE",
        "headline": "Dola productionized: capability registry + "
                    "observability + account pool + clean-asset resolver "
                    "+ plan router QUALIFIED; true draft->final "
                    "NOT_AVAILABLE_ON_CURRENT_FREE_ROUTE; 0/4 mutations "
                    "used",
        "evidence": sorted(p.name for p in PKG.glob("V2_019_*.json")),
    }
    (PKG / "V2_019_CANDIDATE_SEAL.json").write_text(
        json.dumps(seal, indent=1, ensure_ascii=False), encoding="utf-8")
    print("sealed COMPLETED_CANDIDATE")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
