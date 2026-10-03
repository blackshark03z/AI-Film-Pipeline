"""S3 — run Gemini semantic QC qualification against the frozen corpus.

Produces the qualification matrix, repeatability subset, and the frozen
acceptance verdict A-L. Also writes the per-control observations ledger.
"""
from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from film_pipeline.gemini_semantic import GeminiSemanticQCEvaluator
from film_pipeline.semantic_qc import SemanticQCRequest, validate_semantic_batch

ROOT = Path(__file__).resolve().parents[1]
CORPUS = ROOT / "projects/flow_semantic_qualify_006/corpus/qualification_corpus.json"
OUT = ROOT / "projects/flow_semantic_qualify_006/qualification_results.json"
REPEAT_CONTROLS = {"identity_positive", "identity_negative", "world_negative",
                   "shot_continuity_positive", "ambiguous"}


def main() -> None:
    corpus = json.loads(CORPUS.read_text(encoding="utf-8"))
    evaluator = GeminiSemanticQCEvaluator(
        key_file=Path(corpus["key_path"]), model=corpus["model"])
    results = []
    for control in corpus["controls"]:
        cid = control["control_id"]
        request = SemanticQCRequest(
            request_id="qual_" + cid, dimensions=[control["dimension"]],
            frames=control["frames"],
            requirements={control["dimension"]: control["requirement"]},
            provenance={"control_id": cid,
                        "expected_class": control["expected_class"]})
        entry = {"control_id": cid, "dimension": control["dimension"],
                 "expected_class": control["expected_class"]}
        try:
            observations = evaluator.evaluate(request)
            entry["verdict"] = observations[0].verdict
            entry["confidence"] = observations[0].confidence
            entry["observations"] = observations[0].observations
            entry["fingerprint"] = observations[0].prompt_fingerprint
        except ValueError as exc:
            entry["rejected"] = str(exc)
        except RuntimeError as exc:
            entry["error"] = str(exc)
        results.append(entry)
        print(json.dumps(entry, ensure_ascii=False)[:220], flush=True)

    # Repeatability subset.
    repeats = []
    by_id = {c["control_id"]: c for c in corpus["controls"]}
    for cid in sorted(REPEAT_CONTROLS):
        control = by_id[cid]
        request = SemanticQCRequest(
            request_id="qual_repeat_" + cid, dimensions=[control["dimension"]],
            frames=control["frames"],
            requirements={control["dimension"]: control["requirement"]},
            provenance={"control_id": cid})
        verdicts = []
        for _ in range(2):
            try:
                observations = evaluator.evaluate(request)
                verdicts.append(observations[0].verdict)
            except Exception as exc:  # noqa: BLE001
                verdicts.append("ERROR:" + type(exc).__name__)
        repeats.append({"control_id": cid, "verdicts": verdicts,
                        "stable": len(set(verdicts)) == 1})
        print(json.dumps({"repeat": cid, "verdicts": verdicts}), flush=True)

    out = {"model": corpus["model"],
           "credential_source": corpus["key_source"],
           "ran_at": datetime.now(timezone.utc).isoformat(),
           "controls": results, "repeatability": repeats}
    OUT.write_text(json.dumps(out, indent=2, ensure_ascii=False), encoding="utf-8")
    print("wrote", OUT)


if __name__ == "__main__":
    from datetime import datetime, timezone  # noqa: F401
    main()
