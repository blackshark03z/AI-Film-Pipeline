"""W1: semantic boundary inventory — SEARCH before BUILD."""
from __future__ import annotations
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
inventory = {
  "version": "semantic-boundary-inventory-014-v1",
  "components": [
    {"component": "SemanticQCRequest", "location": "src/film_pipeline/semantic_qc.py", "classification": "REUSE_AS_IS"},
    {"component": "SemanticQCObservation", "location": "src/film_pipeline/semantic_qc.py", "classification": "REUSE_AS_IS"},
    {"component": "validate_semantic_batch", "location": "src/film_pipeline/semantic_qc.py", "classification": "REUSE_AS_IS"},
    {"component": "semantic error classes", "location": "src/film_pipeline/semantic_errors.py", "classification": "REUSE_AS_IS"},
    {"component": "GeminiSemanticQCEvaluator", "location": "src/film_pipeline/gemini_semantic.py", "classification": "HISTORICAL_PROVIDER_SPECIFIC (stays as an inactive API backend behind the new boundary)"},
    {"component": "normalize_model_id", "location": "src/film_pipeline/gemini_semantic.py", "classification": "HISTORICAL_PROVIDER_SPECIFIC"},
    {"component": "Package-006 frozen corpus", "location": "projects/flow_semantic_qualify_006/corpus/qualification_corpus.json", "classification": "REUSE_AS_IS"},
    {"component": "qualification runners 006/R1/011/012/013", "location": "tools/run_semantic_*.py", "classification": "HISTORICAL_PROVIDER_SPECIFIC"},
    {"component": "SemanticEvaluatorBackend + ProvenancedObservation + WorkerReviewPacket/Result + import_worker_result", "location": "src/film_pipeline/semantic_backends.py", "classification": "EXTEND (new provider-neutral boundary, this package)"},
    {"component": "Gemini cache/fingerprint code (prompt_fingerprint)", "location": "src/film_pipeline/gemini_semantic.py", "classification": "ADAPT (generic fingerprinting moves to the neutral boundary; Gemini keeps its adapter)"},
    {"component": "semantic dimensions/verdict schema", "location": "src/film_pipeline/semantic_qc.py SEMANTIC_DIMENSIONS", "classification": "REUSE_AS_IS"}
  ],
  "no_parallel_schema": True,
  "film_core_consumes": "SemanticQCRequest -> ProvenancedObservation (superset of SemanticQCObservation semantics)"
}
out = ROOT / "projects/flow_worker_semantic_backend_014/semantic_boundary_inventory_014.json"
out.parent.mkdir(parents=True, exist_ok=True)
out.write_text(json.dumps(inventory, indent=1), encoding="utf-8")
print(json.dumps({"components": len(inventory["components"]),
                  "no_parallel_schema": True}))
