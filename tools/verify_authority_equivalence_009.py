"""Package-009 Phase-0C (Package-010 custody closure): deterministic proof
that each V8 re-proof release (F2C, G2C, E2C, G3C) was authorized by an
authority state the ROOT package authority would have granted identically
at the same instant — despite being recorded through the defective
sub-directory fragment file.

For each release, derived ONLY from durable timestamped artifacts:
  ROOT_AUTHORITY_WAS_OPEN + NO_PRIOR_LATCH + BUDGET_AVAILABLE +
  SAME_SCOPE_AND_INTENT ⇒ ROOT_WOULD_HAVE_AUTHORIZED_THE_RELEASE.

Output: projects/flow_upload_contract_requal_009/authority_equivalence_009.json
Exit code 1 if ANY release fails to prove equivalence.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RUN = ROOT / "projects/flow_upload_contract_requal_009"
SCOPE = "FLOW-UPLOAD-CONTRACT-REQUAL-009"
SUCCESSORS = {
    "SEQ7_F2C": "scene_SCENE_F_STORM_GATE",
    "SEQ7_G2C": "scene_SCENE_G_HIGH_PLATEAU",
    "SEQ7_E2C": "scene_SCENE_E_RIDGE_APPROACH",
    "SEQ7_G3C": "scene_SCENE_G_HIGH_PLATEAU",
}


def replay(events: list[dict], before_ts: str) -> dict:
    """Replay authority events with at < before_ts; return the state."""
    state, latch_count, prior = "OPEN", 0, []
    for event in sorted(events, key=lambda e: e["at"]):
        if event["at"] >= before_ts:
            continue
        prior.append(event)
        kind = event["kind"]
        if kind == "QUALIFIED_UPLOAD_PENDING_ENTERED":
            state = "SUSPENDED_QUALIFIED_UPLOAD_PENDING"
        elif kind in ("QUALIFIED_UPLOAD_BOUND",):
            state = "OPEN"
        elif kind.startswith("OWNER_AMBIGUITY_GATE"):
            state = "LATCHED_CLOSED"
            latch_count += 1
    return {"state": state, "latch_count": latch_count, "events": prior}


def main() -> None:
    releases = {}
    for ledger_path in (RUN / "generate_ledger.json",
                        RUN / "reproof/generate_ledger.json"):
        ledger = json.loads(ledger_path.read_text(encoding="utf-8"))
        for entry in ledger["primary_consumed"]:
            releases[entry["shot_id"]] = {**entry, "ledger": str(ledger_path)}
    root_auth = json.loads((RUN / "mutation_authority.json")
                           .read_text(encoding="utf-8"))
    assert root_auth["scope_id"] == SCOPE
    fragment = json.loads(
        (RUN / "reproof/mutation_authority_fragment_defect.json")
        .read_text(encoding="utf-8"))
    assert fragment["scope_id"] == SCOPE, "fragment must carry the SAME scope id"
    pkg_ledger = json.loads((RUN / "mutation_ledger.json")
                            .read_text(encoding="utf-8"))
    uploads_used = len(pkg_ledger["uploads_used"])
    conditioned = len(pkg_ledger["conditioned_generates"]) if \
        "conditioned_generates" in pkg_ledger else 1

    rows = []
    all_equivalent = True
    for slot in sorted(SUCCESSORS):
        release = releases[slot]
        ts = release["released_at"]
        job_id = release["provider_job_id"]
        root_before = replay(root_auth["events"], ts)
        fragment_before = replay(fragment["events"], ts)
        scene = SUCCESSORS[slot]
        result = json.loads(
            (RUN / "reproof" / scene / f"shot_{slot}" /
             "result.json").read_text(encoding="utf-8"))
        intent = json.loads(
            (RUN / "reproof" / scene / f"shot_{slot}" /
             "frozen_intent.json").read_text(encoding="utf-8"))
        reproof_before = sum(
            1 for e in root_auth["events"]
            if e["kind"] == "BUDGET_CONSUMED" and
            e.get("budget_kind") == "reproof_generate" and e["at"] < ts)
        budget_ok = (uploads_used <= 2 and conditioned <= 1 and
                     reproof_before < 4)
        checks = {
            "root_state_open": root_before["state"] == "OPEN",
            "no_prior_latch": root_before["latch_count"] == 0,
            "budget_available": budget_ok,
            "same_scope": root_auth["scope_id"] == fragment["scope_id"] == SCOPE,
            "same_intent": intent["provider_job_id"] == job_id ==
            result["provider_job_id"] and
            result.get("gate") == "SHOT_PROVEN",
        }
        equivalent = all(checks.values())
        all_equivalent &= equivalent
        rows.append({
            "slot": slot, "job_id": job_id, "timestamp": ts,
            "root_state": root_before["state"],
            "root_events_before": [
                {"kind": e["kind"], "at": e["at"]} for e in
                root_before["events"]],
            "root_latch_count_before": root_before["latch_count"],
            "fragment_state": fragment_before["state"],
            "fragment_events_before": [
                {"kind": e["kind"], "at": e["at"]} for e in
                fragment_before["events"]],
            "budget_before": {
                "uploads_used": uploads_used, "uploads_cap": 2,
                "conditioned_generates": conditioned, "conditioned_cap": 1,
                "reproof_generates_before": reproof_before,
                "reproof_cap": 4},
            "intent_digest": {
                "frozen_intent_job": intent["provider_job_id"],
                "result_job": result["provider_job_id"],
                "ledger_job": job_id,
                "gate": result.get("gate")},
            "checks": checks,
            "equivalent_authority": equivalent,
            "basis": ("ROOT_AUTHORITY_WAS_OPEN + NO_PRIOR_LATCH + "
                      "BUDGET_AVAILABLE + SAME_SCOPE_AND_INTENT => "
                      "ROOT_WOULD_HAVE_AUTHORIZED_THE_RELEASE"
                      if equivalent else "EQUIVALENCE_NOT_PROVEN")})

    verdict = {
        "version": "authority-equivalence-009-v1",
        "scope": SCOPE,
        "classification": ("AUTHORITY_STORE_FRAGMENTATION = "
                           "IMPLEMENTATION_DEFECT BUT "
                           "NO_ACTUAL_AUTHORITY_ESCALATION_OR_BYPASS"
                           if all_equivalent else
                           "EQUIVALENCE_NOT_PROVEN"),
        "all_equivalent": all_equivalent,
        "releases": rows}
    out = RUN / "authority_equivalence_009.json"
    out.write_text(json.dumps(verdict, indent=2, ensure_ascii=False) + "\n",
                   encoding="utf-8")
    print(json.dumps({"all_equivalent": all_equivalent,
                      "slots": [r["slot"] for r in rows],
                      "classification": verdict["classification"]}))
    if not all_equivalent:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
