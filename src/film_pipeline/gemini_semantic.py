"""Gemini-backed semantic QC evaluator implementing the frozen interface.

Advisory evidence ONLY: no mutation authority, no budget, no ownership.
The credential is read at runtime from the Owner-approved local file and is
never printed, logged, persisted, or passed via argv.
"""
from __future__ import annotations

import base64
import json
import urllib.request
from pathlib import Path

from .core import canonical_json, sha256
from .semantic_qc import (
    SemanticQCEvaluator,
    SemanticQCRequest,
    SemanticQCObservation,
    validate_semantic_batch,
)

API_BASE = "https://generativelanguage.googleapis.com/v1beta/models"
DIMENSION_QUESTIONS = {
    "character_identity": "Do the frames show the same character identity as the requirement describes?",
    "wardrobe_props": "Do wardrobe and props match the requirement exactly?",
    "environment_world": "Does the environment/world match the requirement?",
    "action_completion": "Does the visible action match the required action?",
    "framing_camera": "Does framing/camera match the requirement (shot size, lens feel, camera height/lock)?",
    "lighting_time": "Does lighting/time-of-day match the requirement?",
    "shot_continuity": "Do the two frames form a continuous same-scene transition (identity, world, light, geography)?",
    "scene_transition": "Do the two frames form the required scene transition (exit then new-space entry, etc.)?",
}


def read_key(key_file: Path) -> str:
    """Read the Owner-approved key at runtime. Never print or persist."""
    text = Path(key_file).read_text(encoding="utf-8-sig")
    keys = [line.strip() for line in text.splitlines()
            if line.strip() and not line.lstrip().startswith("#")]
    if not keys:
        raise ValueError("GEMINI_KEY_FILE_EMPTY")
    return keys[0]


def prompt_fingerprint(request: SemanticQCRequest, model: str) -> str:
    return sha256(canonical_json({
        "dimensions": request.dimensions,
        "requirements": request.requirements,
        "frame_hashes": [f.get("sha256") for f in request.frames],
        "model": model,
        "prompt_version": "gemini-semantic-v1",
    }))


class GeminiSemanticQCEvaluator(SemanticQCEvaluator):
    """One bounded API call per request; strict JSON; fail-closed errors.

    Source lineage is enforced before any API call: every frame's on-disk
    bytes must hash to the pinned sha256, else the request is rejected
    (MUST_REJECT_LINEAGE semantics).
    """

    evaluator_type = "gemini"
    prompt_version = "gemini-semantic-v1"

    def __init__(self, key_file: Path, model: str):
        self.key_file = Path(key_file)
        self.model = model

    def evaluate(self, request: SemanticQCRequest) -> list[SemanticQCObservation]:
        self.verify_source_lineage(request)
        fingerprint = prompt_fingerprint(request, self.model)
        prompt = self._prompt(request)
        parts = [{"text": prompt}]
        for frame in request.frames:
            data = Path(frame["path"]).read_bytes()
            parts.append({"text": f"Frame: {frame.get('label', 'image')}"})
            parts.append({"inline_data": {"mime_type": "image/png",
                                          "data": base64.b64encode(data).decode("ascii")}})
        body = {"contents": [{"parts": parts}],
                "generationConfig": {"responseMimeType": "application/json",
                                     "temperature": 0}}
        key = read_key(self.key_file)
        request_obj = urllib.request.Request(
            f"{API_BASE}/{self.model}:generateContent",
            data=json.dumps(body).encode("utf-8"),
            headers={"x-goog-api-key": key, "Content-Type": "application/json"},
            method="POST")
        try:
            with urllib.request.urlopen(request_obj, timeout=120) as response:
                result = json.load(response)
        except urllib.error.HTTPError as exc:
            body_text = ""
            try:
                body_text = exc.read(65536).decode("utf-8", "replace")
            except Exception:
                body_text = ""
            retry_after = exc.headers.get("Retry-After") if \
                exc.headers else None
            from .semantic_errors import classify_http_failure
            raise classify_http_failure(exc.code, body_text,
                                        retry_after) from None
        except urllib.error.URLError as exc:
            from .semantic_errors import classify_transport_exception
            raise classify_transport_exception(exc) from None
        observations = self._parse(result, request, fingerprint)
        validate_semantic_batch(request, observations)
        return observations

    def verify_source_lineage(self, request: SemanticQCRequest) -> None:
        import hashlib

        for frame in request.frames:
            path = Path(frame["path"])
            if not path.is_file():
                raise ValueError("SEMANTIC_SOURCE_MISSING")
            digest = hashlib.sha256(path.read_bytes()).hexdigest()
            if digest != frame.get("sha256"):
                raise ValueError("SEMANTIC_SOURCE_LINEAGE_MISMATCH")

    def _prompt(self, request: SemanticQCRequest) -> str:
        lines = []
        for dimension in request.dimensions:
            lines.append(f"{dimension}: {request.requirements[dimension]}")
        requirement_text = "\n".join(lines)
        n = len(request.frames)
        frame_note = ("The images are chronological frames of one shot."
                      if n > 1 else
                      "The image is one frame of one shot.")
        if n == 2 and any(d in request.dimensions for d in
                          ("shot_continuity", "scene_transition")):
            frame_note = ("The two images are the boundary frames of an "
                          "adjacent cut: FIRST frame of the later shot's "
                          "predecessor context and LAST frame — judge only "
                          "the continuity/transition dimensions requested.")
        return (
            "You are an advisory film-continuity QC observer. "
            + frame_note + " "
            "Answer strictly in JSON only: an object with one key 'observations', "
            "an array with EXACTLY one entry per requested dimension. Each entry: "
            "{'dimension': <dimension>, 'verdict': 'PASS'|'FAIL'|'INCONCLUSIVE', "
            "'confidence': <0..1>, 'observations': [<short concrete visible facts>]}. "
            "Judge ONLY what is visible. Use INCONCLUSIVE when the frames cannot "
            "decide. Never invent off-screen facts. Requested dimensions and "
            "frozen requirements:\n" + requirement_text)

    def _parse(self, result, request: SemanticQCRequest,
               fingerprint: str) -> list[SemanticQCObservation]:
        try:
            raw = result["candidates"][0]["content"]["parts"][0]["text"]
            payload = json.loads(raw)
            entries = payload["observations"]
            by_dimension = {e["dimension"]: e for e in entries}
        except (KeyError, IndexError, TypeError, ValueError, json.JSONDecodeError):
            raise RuntimeError("SEMANTIC_RESPONSE_MALFORMED") from None
        observations = []
        for dimension in request.dimensions:
            entry = by_dimension.get(dimension)
            if not isinstance(entry, dict):
                raise RuntimeError("SEMANTIC_DIMENSION_MISSING")
            verdict = entry.get("verdict")
            if verdict not in ("PASS", "FAIL", "INCONCLUSIVE"):
                raise RuntimeError("SEMANTIC_VERDICT_UNQUALIFIED")
            try:
                observations.append(SemanticQCObservation(
                    request_id=request.request_id, dimension=dimension,
                    verdict=verdict,
                    confidence=float(entry.get("confidence", 0.0)),
                    observations=[str(o)[:400] for o in entry.get("observations", [])],
                    evidence_refs=list(request.frames),
                    evaluator_type=self.evaluator_type,
                    evaluator_version=self.model,
                    prompt_fingerprint=fingerprint))
            except (TypeError, ValueError):
                raise RuntimeError("SEMANTIC_RESPONSE_MALFORMED") from None
        return observations
