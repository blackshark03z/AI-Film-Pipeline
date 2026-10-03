"""Bounded characterization re-run of the API-errored qualification controls."""
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from film_pipeline.gemini_semantic import GeminiSemanticQCEvaluator
from film_pipeline.semantic_qc import SemanticQCRequest

ROOT = Path(__file__).resolve().parents[1]
corpus = json.loads((ROOT / "projects/flow_semantic_qualify_006/corpus/qualification_corpus.json")
                    .read_text(encoding="utf-8"))
results = json.loads((ROOT / "projects/flow_semantic_qualify_006/qualification_results.json")
                     .read_text(encoding="utf-8"))
corpus_controls = {c["control_id"]: c for c in corpus["controls"]}
evaluator = GeminiSemanticQCEvaluator(key_file=Path(corpus["key_path"]),
                                      model=corpus["model"])
errored = [c for c in results["controls"] if "error" in c]
final = []
for control in errored:
    corpus_control = corpus_controls[control["control_id"]]
    request = SemanticQCRequest(
        request_id="qual_char_" + control["control_id"],
        dimensions=[control["dimension"]],
        frames=corpus_control["frames"],
        requirements={control["dimension"]:
                      corpus_control["requirement"]},
        provenance={"control_id": control["control_id"]})
    entry = {"control_id": control["control_id"]}
    try:
        observations = evaluator.evaluate(request)
        entry["verdict"] = observations[0].verdict
        entry["confidence"] = observations[0].confidence
        entry["observations"] = observations[0].observations
    except Exception as exc:  # noqa: BLE001
        entry["error"] = str(exc)
    final.append(entry)
    print(json.dumps(entry, ensure_ascii=False)[:200], flush=True)
    time.sleep(20)
out = {"characterization": "bounded single re-run of API-errored controls "
                          "after backoff",
       "controls": final}
(ROOT / "projects/flow_semantic_qualify_006/api_error_characterization.json")\
    .write_text(json.dumps(out, indent=2, ensure_ascii=False), encoding="utf-8")
print("characterization written", flush=True)
