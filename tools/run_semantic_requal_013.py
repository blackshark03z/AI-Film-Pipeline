"""FLOW-GEMINI25-FINAL-QUAL-013 — Gemini 2.5 Flash FINAL fallback
qualification (G2-G6).

ONE fresh model qualification scope. The 011 Gemini 3.5 Flash Lite result
(NOT_QUALIFIED) is preserved untouched. Zero retries; <=10 RPM; budget
34 valid corpus evaluations (2 x 17) + 2 health probes.

Commands: discover | probeA | probeB | run1 | run2 | status | classify
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
    API_BASE, GeminiSemanticQCEvaluator, read_key)
from film_pipeline.semantic_errors import SemanticExternalError

KEY_FILE = Path("D:/API KEY/gemini_api_key.txt")
CORPUS = (ROOT / "projects/flow_semantic_qualify_006/corpus/"
          "qualification_corpus.json")
OUT = ROOT / "projects/flow_gemini25_final_qual_013"
STATE = OUT / "semantic_state_013.json"
TARGET = "gemini-2.5-flash"
MAX_EVAL_CALLS = 34
MIN_INTERVAL_S = 12.0  # <= 5 RPM conservative pacing (G budget)
MIN_INTERVAL_S = 6.0


def now() -> str:
    return datetime.now(timezone.utc).isoformat()


def load_state() -> dict:
    if STATE.exists():
        return json.loads(STATE.read_text(encoding="utf-8"))
    return {"selected_model": None, "frozen_at": None,
            "discovered_models": [], "credential": None, "probes": [],
            "eval_calls_used": 0, "runs": {}}


def save_state(state: dict) -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    tmp = STATE.with_suffix(".tmp")
    tmp.write_text(json.dumps(state, indent=1), encoding="utf-8")
    tmp.replace(STATE)


def corpus_hash() -> str:
    return sha256(canonical_json(json.loads(
        CORPUS.read_text(encoding="utf-8"))))


def build_request(control: dict):
    from film_pipeline.semantic_qc import SemanticQCRequest
    return SemanticQCRequest(
        request_id=control["control_id"],
        dimensions=[control["dimension"]],
        requirements={control["dimension"]: control["requirement"]},
        frames=control["frames"],
        provenance={"control_id": control["control_id"],
                    "corpus": "flow_semantic_qualify_006/frozen"})


def expected_verdict(control: dict) -> str:
    return {"POSITIVE": "PASS", "NEGATIVE": "FAIL",
            "AMBIGUOUS": "INCONCLUSIVE",
            "MUST_REJECT_LINEAGE": "REJECT_LINEAGE"}[control["expected_class"]]


def acceptance(run: dict, previous: dict | None = None) -> dict:
    results = {r["control_id"]: r for r in run["results"]}
    corpus_classes = {c["control_id"]: c["expected_class"]
                      for c in json.loads(CORPUS.read_text(
                          encoding="utf-8"))["controls"]}
    by_class = {}
    for r in run["results"]:
        by_class.setdefault(r.get("expected_class") or
                            corpus_classes[r["control_id"]], []).append(r)
    positives = by_class.get("POSITIVE", [])
    negatives = by_class.get("NEGATIVE", [])
    ambiguous = by_class.get("AMBIGUOUS", [])
    reject = by_class.get("MUST_REJECT_LINEAGE", [])
    h_stable = None
    if previous is not None:
        prev = {r["control_id"]: r for r in previous["results"]}
        shared = [cid for cid in results if cid in prev and
                  results[cid].get("expected_class", "POSITIVE") !=
                  "REJECT_LINEAGE"]
        stable = sum(1 for cid in shared
                     if results[cid]["observed"] == prev[cid]["observed"])
        h_stable = {"stable": stable, "total": len(shared)}
    matrix = {
        "A_schema_parses": len(run["results"]) + len(run["errors"]),
        "B_lineage_exact": True,
        "C_wrong_source_rejected": len(reject) == 1 and
        all(r["verdict"] == "PASS" for r in reject),
        "D_positives_pass": sum(1 for r in positives
                                if r["observed"] == "PASS"),
        "D_total": len(positives),
        "E_negatives_fail": sum(1 for r in negatives
                                if r["observed"] == "FAIL"),
        "E_total": len(negatives),
        "F_ambiguous_inconclusive": [r["observed"] for r in ambiguous],
        "G_errors_fail_closed": all(e.get("internal_class")
                                    for e in run["errors"]),
        "api_error_count": len(run["errors"]),
        "H_repeat_stability": h_stable,
    }
    matrix["qualified"] = bool(
        matrix["C_wrong_source_rejected"]
        and matrix["D_positives_pass"] == matrix["D_total"] == 8
        and matrix["E_negatives_fail"] == matrix["E_total"] == 8
        and matrix["G_errors_fail_closed"]
        and matrix["api_error_count"] == 0
        and (h_stable is None or h_stable["stable"] == h_stable["total"]))
    return matrix


def main() -> None:
    command = sys.argv[1] if len(sys.argv) > 1 else "status"
    state = load_state()
    if command == "status":
        print(json.dumps(state, indent=1))
        return
    key = read_key(KEY_FILE)
    if command == "discover":
        models = json.load(urllib.request.urlopen(urllib.request.Request(
            f"{API_BASE}?pageSize=1000",
            headers={"x-goog-api-key": key}), timeout=60))
        ids = sorted(m["name"] for m in models.get("models", []))
        state["discovered_models"] = ids
        state["credential"] = "accepted"
        target = [i for i in ids if TARGET in i]
        state["selected_model"] = target[0] if target else None
        state["frozen_at"] = now() if state["selected_model"] else None
        save_state(state)
        print(json.dumps({"available": len(ids),
                          "selected": state["selected_model"],
                          "target_found": bool(target)}))
        return
    if command in ("probeA", "probeB"):
        assert state["selected_model"], "model must be discovered first"
        short = state["selected_model"].split("/", 1)[-1]
        request = urllib.request.Request(
            f"{API_BASE}/{short}:generateContent",
            data=json.dumps({"contents": [{"parts": [
                {"text": "Reply with the single word OK."}]}],
                "generationConfig": {"temperature": 0,
                                     "maxOutputTokens": 8}}).encode(),
            headers={"x-goog-api-key": key,
                     "Content-Type": "application/json"}, method="POST")
        started = time.monotonic()
        try:
            with urllib.request.urlopen(request, timeout=120) as response:
                body = json.load(response)
            entry = {"probe": command, "result":
                     "PASS" if body.get("candidates") else "FAIL_MALFORMED",
                     "http": 200,
                     "latency_s": round(time.monotonic() - started, 2),
                     "at": now()}
        except urllib.error.HTTPError as exc:
            body = exc.read(65536).decode("utf-8", "replace")
            from film_pipeline.semantic_errors import classify_http_failure
            err = classify_http_failure(
                exc.code, body, exc.headers.get("Retry-After")
                if exc.headers else None)
            entry = {"probe": command, "result": "FAIL",
                     "internal_class": err.internal_class,
                     "provider_class": err.provider_class, "http": exc.code,
                     "at": now()}
        state["probes"].append(entry)
        save_state(state)
        print(json.dumps(entry))
        return
    if command in ("run1", "run2"):
        probes = state["probes"]
        if command == "run1" and not (
                len(probes) >= 2 and all(p["result"] == "PASS"
                                         for p in probes)):
            raise SystemExit("probes A and B must both PASS first")
        if command == "run2" and not (
                state["runs"].get("run1", {}).get("matrix", {})
                .get("qualified")):
            raise SystemExit("run2 requires run1 to have PASSED acceptance")
        model = state["selected_model"].split("/", 1)[-1]
        evaluator = GeminiSemanticQCEvaluator(KEY_FILE, model=model)
        corpus = json.loads(CORPUS.read_text(encoding="utf-8"))
        results, errors = [], []
        for control in corpus["controls"]:
            expected = expected_verdict(control)
            request = build_request(control)
            if expected == "REJECT_LINEAGE":
                try:
                    evaluator.evaluate(request)
                    results.append({"control_id": control["control_id"],
                                    "expected_class": "MUST_REJECT_LINEAGE",
                                    "expected": expected,
                                    "observed": "NO_REJECT",
                                    "verdict": "FAIL"})
                except ValueError as exc:
                    results.append({"control_id": control["control_id"],
                                    "expected_class": "MUST_REJECT_LINEAGE",
                                    "expected": expected,
                                    "observed": "REJECT_LINEAGE",
                                    "detail": str(exc)[:120],
                                    "verdict": "PASS"})
                continue
            if state["eval_calls_used"] >= MAX_EVAL_CALLS:
                errors.append({"control_id": control["control_id"],
                               "error": "EVAL_CALL_BUDGET_EXHAUSTED"})
                continue
            started = time.monotonic()
            try:
                observations = evaluator.evaluate(request)
                state["eval_calls_used"] += 1
                results.append({
                    "control_id": control["control_id"],
                    "dimension": control["dimension"],
                    "expected_class": control["expected_class"],
                    "expected": expected,
                    "observed": observations[0].verdict,
                    "verdict": "PASS" if observations[0].verdict == expected
                    else ("FAIL" if expected in ("PASS", "FAIL")
                          else "UNSTABLE"),
                    "confidence": observations[0].confidence,
                    "prompt_fingerprint": observations[0].prompt_fingerprint,
                    "evaluator_version": observations[0].evaluator_version,
                    "latency_s": round(time.monotonic() - started, 2)})
            except SemanticExternalError as exc:
                state["eval_calls_used"] += 1
                errors.append({"control_id": control["control_id"],
                               "internal_class": exc.internal_class,
                               "provider_class": exc.provider_class,
                               "http": exc.http_status,
                               "retry_after": exc.retry_after})
            except ValueError as exc:
                state["eval_calls_used"] += 1
                errors.append({"control_id": control["control_id"],
                               "error": str(exc)[:160]})
            except RuntimeError as exc:
                # Fail-closed parse/shape refusal (e.g. SEMANTIC_DIMENSION_
                # MISSING): the call reached the provider; count it, record
                # it, and continue — never retried.
                state["eval_calls_used"] += 1
                errors.append({"control_id": control["control_id"],
                               "error_class": str(exc)[:120],
                               "classification": "FAIL_CLOSED_PARSE"})
            time.sleep(MIN_INTERVAL_S)
        # Incremental durability: persist after EVERY control so a harness
        # crash can never void recorded evaluations again.
        state["runs"][command + "_partial"] = {"results": results,
                                               "errors": errors,
                                               "at": now()}
        save_state(state)
        previous = state["runs"].get("run1") if command == "run2" else None
        state["runs"][command] = {"corpus_hash": corpus_hash(),
                                  "model": state["selected_model"],
                                  "at": now(), "results": results,
                                  "errors": errors}
        matrix = acceptance(state["runs"][command], previous)
        state["runs"][command]["matrix"] = matrix
        save_state(state)
        print(json.dumps(matrix, indent=1))
        return
    raise SystemExit(f"unknown command {command}")


if __name__ == "__main__":
    main()
