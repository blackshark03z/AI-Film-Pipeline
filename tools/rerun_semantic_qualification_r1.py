"""R1 — requalification of the FROZEN semantic corpus with bounded retries.

Same frozen corpus and frozen expected labels as Package-006 (never
re-derived). Delta vs the first run: transient SEMANTIC_API_UNAVAILABLE
errors get up to 2 bounded retries with 30 s backoff (characterizing
whether they are rate-limit transients); malformed/lineage failures are
single-attempt fail-closed. Verdict re-evaluated against the SAME frozen
acceptance criteria — thresholds not lowered.
"""
from __future__ import annotations

import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from film_pipeline.gemini_semantic import GeminiSemanticQCEvaluator
from film_pipeline.semantic_qc import SemanticQCRequest, validate_semantic_batch

ROOT = Path(__file__).resolve().parents[1]
CORPUS = ROOT / "projects/flow_semantic_qualify_006/corpus/qualification_corpus.json"
OUT = ROOT / "projects/flow_semantic_qualify_006/requalification_results.json"
MAX_ATTEMPTS = 3          # 1 + 2 bounded retries
BACKOFF_S = 30
REPEAT_CONTROLS = {"identity_positive", "identity_negative", "world_negative",
                   "shot_continuity_positive", "ambiguous", "framing_positive",
                   "lighting_negative"}


def now() -> str:
    return datetime.now(timezone.utc).isoformat()


def evaluate_with_retry(evaluator, request):
    last = None
    for attempt in range(1, MAX_ATTEMPTS + 1):
        try:
            return evaluator.evaluate(request), attempt
        except RuntimeError as exc:
            message = str(exc)
            last = exc
            # Only transient API failures are retried; malformed/lineage
            # failures are single-attempt fail-closed.
            if message != "SEMANTIC_API_UNAVAILABLE":
                raise
            if attempt < MAX_ATTEMPTS:
                print(json.dumps({"retry": attempt, "backoff_s": BACKOFF_S}),
                      flush=True)
                time.sleep(BACKOFF_S)
    raise last


def main() -> None:
    corpus = json.loads(CORPUS.read_text(encoding="utf-8"))
    evaluator = GeminiSemanticQCEvaluator(
        key_file=Path(corpus["key_path"]), model=corpus["model"])
    results = []
    for control in corpus["controls"]:
        cid = control["control_id"]
        request = SemanticQCRequest(
            request_id="r1_" + cid, dimensions=[control["dimension"]],
            frames=control["frames"],
            requirements={control["dimension"]: control["requirement"]},
            provenance={"control_id": cid})
        entry = {"control_id": cid, "dimension": control["dimension"],
                 "expected_class": control["expected_class"]}
        try:
            observations, attempts = evaluate_with_retry(evaluator, request)
            validate_semantic_batch(request, observations)
            entry["verdict"] = observations[0].verdict
            entry["confidence"] = observations[0].confidence
            entry["observations"] = observations[0].observations
            entry["fingerprint"] = observations[0].prompt_fingerprint
            entry["attempts"] = attempts
        except ValueError as exc:
            entry["rejected"] = str(exc)
        except RuntimeError as exc:
            entry["error"] = str(exc)
        results.append(entry)
        print(json.dumps(entry, ensure_ascii=False)[:220], flush=True)
        time.sleep(10)

    repeats = []
    by_id = {c["control_id"]: c for c in corpus["controls"]}
    for cid in sorted(REPEAT_CONTROLS):
        corpus_control = by_id[cid]
        request = SemanticQCRequest(
            request_id="r1_repeat_" + cid, dimensions=[control_dimension(corpus_control)],
            frames=corpus_control["frames"],
            requirements={control_dimension(corpus_control):
                          corpus_control["requirement"]},
            provenance={"control_id": cid})
        verdicts = []
        for _ in range(3):
            try:
                observations, _a = evaluate_with_retry(evaluator, request)
                verdicts.append(observations[0].verdict)
            except Exception as exc:  # noqa: BLE001
                verdicts.append("ERROR:" + type(exc).__name__)
            time.sleep(10)
        repeats.append({"control_id": cid, "verdicts": verdicts,
                        "stable": len(set(verdicts)) == 1})
        print(json.dumps({"repeat": cid, "verdicts": verdicts}), flush=True)

    out = {"model": corpus["model"],
           "credential_source": corpus["key_source"],
           "ran_at": now(), "controls": results, "repeatability": repeats,
           "note": ("bounded 2-retry/30s-backoff for transient API errors; "
                    "frozen labels unchanged from Package-006 corpus")}
    OUT.write_text(json.dumps(out, indent=2, ensure_ascii=False), encoding="utf-8")
    print("wrote", OUT, flush=True)


def control_dimension(control: dict) -> str:
    return control["dimension"]


if __name__ == "__main__":
    main()
