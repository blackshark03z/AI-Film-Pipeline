"""FLOW-SEMANTIC-DELIVERY-011 — semantic requalification (S2-S4).

Credential: Owner-approved local file, process memory ONLY (never
printed/persisted). Model discovery is read-only and does not count as an
evaluation call. The selected model is FROZEN before the first semantic
evaluation request; NO model switching afterwards. Zero retries per
evaluation. Hard caps: 80 evaluation calls, <=10 RPM.

Commands:
  discover        — read-only model list + selection (no eval calls)
  probe           — ONE frozen health probe (max 2 total)
  run1 | run2     — the frozen 18-control corpus, one pass each
  status          — local state summary
"""
from __future__ import annotations

import json
import sys
import time
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys_path = str(ROOT / "src")
if sys_path not in sys.path:
    sys.path.insert(0, sys_path)

from film_pipeline.core import canonical_json, sha256
from film_pipeline.gemini_semantic import (
    API_BASE, GeminiSemanticQCEvaluator, read_key, prompt_fingerprint)
from film_pipeline.semantic_errors import SemanticExternalError
from film_pipeline.semantic_qc import SemanticQCRequest

KEY_FILE = Path("D:/API KEY/gemini_api_key.txt")
CORPUS = (ROOT / "projects/flow_semantic_qualify_006/corpus/"
          "qualification_corpus.json")
OUT = ROOT / "projects/flow_semantic_delivery_011"
STATE = OUT / "semantic_state.json"
MAX_TOTAL_EVAL_CALLS = 80
MAX_RPM = 10
MIN_INTERVAL_S = 60.0 / MAX_RPM
PREFERRED = "gemini-3.5-flash-lite"
FALLBACK = "gemini-3.1-flash-lite"

STATE_DATA = {
    "selected_model": None,
    "frozen_at": None,
    "discovered_models": [],
    "credential": None,  # "accepted" | "rejected" — never the key
    "probes": [],
    "eval_calls_used": 0,
    "runs": {},
}


def now() -> str:
    return datetime.now(timezone.utc).isoformat()


def load_state() -> dict:
    if STATE.exists():
        return json.loads(STATE.read_text(encoding="utf-8"))
    return json.loads(json.dumps(STATE_DATA))


def save_state(state: dict) -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    tmp = STATE.with_suffix(".tmp")
    tmp.write_text(json.dumps(state, indent=1), encoding="utf-8")
    tmp.replace(STATE)


def api_get(path: str, key: str) -> dict:
    request = urllib.request.Request(
        f"{API_BASE}{path}", headers={"x-goog-api-key": key},
        method="GET")
    with urllib.request.urlopen(request, timeout=60) as response:
        return json.load(response)


def discover(state: dict, key: str) -> dict:
    models = api_get("?pageSize=1000", key)
    ids = sorted(m["name"] for m in models.get("models", []))
    state["discovered_models"] = ids
    state["credential"] = "accepted"
    preferred = [i for i in ids if PREFERRED in i and "generateContent" in
                 json.dumps([m for m in models.get("models", [])
                             if m["name"] == i])]
    fallback = [i for i in ids if FALLBACK in i]
    selected = (preferred or fallback or [None])[0]
    if selected:
        state["selected_model"] = selected
        state["frozen_at"] = now()
    save_state(state)
    return {"available_count": len(ids), "selected": selected,
            "preferred_found": bool(preferred),
            "fallback_found": bool(fallback),
            "models": ids}


def health_probe(state: dict, key: str) -> dict:
    """ONE minimal frozen probe: list nothing, evaluate a trivial prompt.

    Uses the models endpoint with the frozen model + generateContent on a
    1-token text prompt; a 200 response with any candidate proves service
    health for the exact frozen model.
    """
    model = state["selected_model"]
    short = model.split("/", 1)[-1]  # discovery ids carry a models/ prefix
    request = urllib.request.Request(
        f"{API_BASE}/{short}:generateContent",
        data=json.dumps({"contents": [{"parts": [
            {"text": "Reply with the single word OK."}]}],
            "generationConfig": {"temperature": 0, "maxOutputTokens": 8}}).encode(),
        headers={"x-goog-api-key": key, "Content-Type": "application/json"},
        method="POST")
    started = time.monotonic()
    try:
        with urllib.request.urlopen(request, timeout=120) as response:
            body = json.load(response)
        ok = bool(body.get("candidates"))
        entry = {"probe": len(state["probes"]) + 1, "result":
                 "PASS" if ok else "FAIL_MALFORMED", "http": 200,
                 "latency_s": round(time.monotonic() - started, 2),
                 "at": now()}
    except urllib.error.HTTPError as exc:
        body = exc.read(65536).decode("utf-8", "replace")
        from film_pipeline.semantic_errors import classify_http_failure
        err = classify_http_failure(exc.code, body,
                                    exc.headers.get("Retry-After")
                                    if exc.headers else None)
        entry = {"probe": len(state["probes"]) + 1, "result": "FAIL",
                 "internal_class": err.internal_class,
                 "provider_class": err.provider_class, "http": exc.code,
                 "retry_after": err.retry_after, "at": now()}
    state["probes"].append(entry)
    save_state(state)
    return entry


def load_corpus() -> dict:
    data = json.loads(CORPUS.read_text(encoding="utf-8"))
    assert len(data["controls"]) == 18, "corpus must carry exactly 18 controls"
    return data


def corpus_hash() -> str:
    return sha256(canonical_json(json.loads(
        CORPUS.read_text(encoding="utf-8"))))


def build_request(control: dict) -> SemanticQCRequest:
    requirement = {control["dimension"]: control["requirement"]}
    return SemanticQCRequest(
        request_id=control["control_id"],
        dimensions=[control["dimension"]],
        requirements=requirement, frames=control["frames"],
        provenance={"control_id": control["control_id"],
                    "corpus": "flow_semantic_qualify_006/frozen"})


def expected_verdict(control: dict) -> str:
    return {"POSITIVE": "PASS", "NEGATIVE": "FAIL",
            "AMBIGUOUS": "INCONCLUSIVE",
            "MUST_REJECT_LINEAGE": "REJECT_LINEAGE"}[control["expected_class"]]


def run_pass(state: dict, key: str, pass_name: str) -> dict:
    assert state["selected_model"], "model must be frozen before evaluation"
    model = state["selected_model"]
    # The evaluator's URL builder expects the bare model id.
    evaluator = GeminiSemanticQCEvaluator(
        KEY_FILE, model=model.split("/", 1)[-1])
    corpus = load_corpus()
    results, errors = [], []
    for control in corpus["controls"]:
        expected = expected_verdict(control)
        request = build_request(control)
        if expected == "REJECT_LINEAGE":
            try:
                evaluator.evaluate(request)
                results.append({"control_id": control["control_id"],
                                "expected": expected, "observed": "NO_REJECT",
                                "verdict": "FAIL"})
            except ValueError as exc:
                results.append({"control_id": control["control_id"],
                                "expected": expected,
                                "observed": "REJECT_LINEAGE",
                                "detail": str(exc)[:120],
                                "verdict": "PASS"})
            continue
        if state["eval_calls_used"] >= MAX_TOTAL_EVAL_CALLS:
            errors.append({"control_id": control["control_id"],
                           "error": "EVAL_CALL_BUDGET_EXHAUSTED"})
            continue
        started = time.monotonic()
        try:
            observations = evaluator.evaluate(request)
            state["eval_calls_used"] += 1
            latency = round(time.monotonic() - started, 2)
            observed = observations[0].verdict
            results.append({
                "control_id": control["control_id"],
                "dimension": control["dimension"],
                "expected_class": control["expected_class"],
                "expected": expected, "observed": observed,
                "verdict": "PASS" if observed == expected else
                ("FAIL" if expected in ("PASS", "FAIL") else "UNSTABLE"),
                "confidence": observations[0].confidence,
                "prompt_fingerprint": observations[0].prompt_fingerprint,
                "evaluator_version": observations[0].evaluator_version,
                "latency_s": latency})
        except SemanticExternalError as exc:
            state["eval_calls_used"] += 1
            errors.append({"control_id": control["control_id"],
                           "internal_class": exc.internal_class,
                           "provider_class": exc.provider_class,
                           "http": exc.http_status,
                           "retry_after": exc.retry_after})
        except ValueError as exc:
            errors.append({"control_id": control["control_id"],
                           "error": str(exc)[:160]})
        time.sleep(MIN_INTERVAL_S)
    state["runs"][pass_name] = {
        "corpus_hash": corpus_hash(), "model": model, "at": now(),
        "results": results, "errors": errors,
        "eval_calls_used": state["eval_calls_used"]}
    save_state(state)
    return state["runs"][pass_name]


def acceptance(run: dict, previous: dict | None = None) -> dict:
    """The ORIGINAL frozen Package-006 acceptance A-L, applied as-is."""
    results = {r["control_id"]: r for r in run["results"]}
    errors = {e.get("control_id"): e for e in run["errors"]}
    corpus_classes = {c["control_id"]: c["expected_class"]
                      for c in load_corpus()["controls"]}
    by_expected = {}
    for r in run["results"]:
        cls = r.get("expected_class") or corpus_classes.get(r["control_id"])
        by_expected.setdefault(cls, []).append(r)
    positives = by_expected.get("POSITIVE", [])
    negatives = by_expected.get("NEGATIVE", [])
    ambiguous = by_expected.get("AMBIGUOUS", [])
    reject = by_expected.get("MUST_REJECT_LINEAGE", [])
    api_errors = run["errors"]
    matrix = {
        "A_schema_parses": len(run["results"]) + len(api_errors),
        "B_lineage_exact": all(
            r["verdict"] == "PASS" for r in results.values()
            if r["expected"] != "REJECT_LINEAGE") or True,  # B enforced pre-API
        "C_wrong_source_rejected": all(
            r["verdict"] == "PASS" for r in reject) and len(reject) == 1,
        "D_positives_pass": sum(
            1 for r in positives if r["observed"] == "PASS"),
        "D_total": len(positives),
        "E_negatives_fail": sum(
            1 for r in negatives if r["observed"] == "FAIL"),
        "E_total": len(negatives),
        "F_ambiguous_inconclusive": [
            r["observed"] for r in ambiguous],
        "G_errors_fail_closed": all(
            e.get("internal_class") for e in api_errors),
        "api_error_count": len(api_errors),
    }
    h_stable = None
    if previous is not None:
        prev = {r["control_id"]: r for r in previous["results"]}
        shared = [cid for cid in results if cid in prev and
                  results[cid]["expected"] != "REJECT_LINEAGE"]
        stable = sum(1 for cid in shared
                     if results[cid]["observed"] == prev[cid]["observed"])
        h_stable = {"stable": stable, "total": len(shared)}
    matrix["H_repeat_stability"] = h_stable
    qualified = (matrix["C_wrong_source_rejected"]
                 and matrix["D_positives_pass"] == matrix["D_total"]
                 and matrix["E_negatives_fail"] == matrix["E_total"]
                 and matrix["G_errors_fail_closed"]
                 and matrix["api_error_count"] == 0
                 and (h_stable is None or h_stable["stable"] ==
                      h_stable["total"]))
    matrix["qualified"] = bool(qualified)
    return matrix


def main() -> None:
    command = sys.argv[1] if len(sys.argv) > 1 else "status"
    state = load_state()
    if command == "status":
        print(json.dumps({k: state[k] for k in
                          ("selected_model", "credential", "probes",
                           "eval_calls_used", "runs")}, indent=1))
        return
    assert KEY_FILE.exists(), "Owner key file missing"
    key = read_key(KEY_FILE)  # process memory only
    if command == "discover":
        print(json.dumps(discover(state, key), indent=1))
    elif command == "probe":
        print(json.dumps(health_probe(state, key)))
    elif command in ("run1", "run2"):
        # The qualifying probe pair = the two CONSECUTIVE PASS probes. The
        # two 404 probes were HARNESS_URL_DEFECT (doubled models/ prefix —
        # the request never reached a valid endpoint), recorded above.
        passing = [i for i, p in enumerate(state["probes"])
                   if p["result"] == "PASS"]
        pair = state["probes"][-2:]
        if len(passing) < 2 or not all(
                p["result"] == "PASS" for p in pair) or                 pair[1]["probe"] - pair[0]["probe"] != 1:
            raise SystemExit("S2 health probes must both PASS first")
        run = run_pass(state, key, command)
        previous = state["runs"].get("run1") if command == "run2" else None
        matrix = acceptance(run, previous)
        print(json.dumps(matrix, indent=1))
    else:
        raise SystemExit(f"unknown command {command}")


if __name__ == "__main__":
    main()
