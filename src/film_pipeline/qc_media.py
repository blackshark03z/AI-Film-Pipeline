"""Local QC review media and advisory Gemini vision observations."""

from __future__ import annotations

import base64
import json
import os
import re
import subprocess
import tempfile
import time
import urllib.error
import urllib.request
from pathlib import Path

from .core import canonical_json
from .live_runtime import Asset, file_sha256
from .qc import POLICY_VERSION, QCEvidence, evidence

SAMPLE_FRACTIONS = (0.025, 0.25, 0.5, 0.75, 0.975)
VISUAL_CRITERIA = (
    ("establishing_wide_framing", "Is the shot a wide establishing view?"),
    ("night_rain_alley", "Is the setting a rainy urban alley at night?"),
    ("empty_no_people", "Are people absent throughout the shot?"),
)
CONTINUITY_CRITERIA = (
    ("stable_alley_geography", "Is alley geography stable throughout?"),
    ("locked_start_end_composition", "Is the camera effectively locked and start/end composition stable?"),
)
EDITORIAL_CRITERIA = (
    ("establishing_usefulness", "Does this shot serve the specified quiet establishing purpose and cut usefully?"),
)
DEFAULT_CRITERIA = {"visual": VISUAL_CRITERIA, "continuity": CONTINUITY_CRITERIA,
                    "editorial": EDITORIAL_CRITERIA}


def _run(args: list[str], timeout: int = 90) -> subprocess.CompletedProcess[str]:
    return subprocess.run(args, capture_output=True, text=True, timeout=timeout, check=False)


def _promote_content_addressed(staging: Path, output_dir: Path, stem: str) -> dict:
    digest = file_sha256(staging)
    final = output_dir / f"{stem}_{digest}.jpg"
    try:
        os.link(staging, final)  # Never overwrite an artifact referenced by immutable evidence.
    except FileExistsError:
        if file_sha256(final) != digest:
            raise ValueError("QC content-addressed artifact collision") from None
    finally:
        staging.unlink(missing_ok=True)
    return {"path": str(final), "sha256": digest}


def make_review_media(asset: Asset, output_dir: Path, *, criteria=None) -> tuple[list[QCEvidence], dict]:
    """Extract exact-position frames and bounded temporal signals; never judge story truth."""
    output_dir = output_dir.resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    source = Path(asset.uri_or_path)
    if not source.is_file() or file_sha256(source) != asset.sha256:
        raise ValueError("review media source is not the exact persisted Asset bytes")
    if not asset.duration_s:
        raise ValueError("Asset duration missing")
    frames: list[dict] = []
    for index, fraction in enumerate(SAMPLE_FRACTIONS):
        at_s = round(asset.duration_s * fraction, 3)
        handle, name = tempfile.mkstemp(prefix="qc_frame_", suffix=".jpg", dir=output_dir)
        os.close(handle)
        path = Path(name)
        result = _run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-ss", str(at_s),
                       "-i", str(source), "-frames:v", "1", "-vf", "scale=320:180",
                       "-q:v", "3", str(path)])
        if result.returncode or not path.is_file() or path.stat().st_size == 0:
            path.unlink(missing_ok=True)
            raise ValueError(f"QC frame extraction failed at {at_s}s")
        frames.append({"time_s": at_s, **_promote_content_addressed(
            path, output_dir, f"frame_{index}_{at_s:.3f}s")})
    handle, name = tempfile.mkstemp(prefix="qc_contact_", suffix=".jpg", dir=output_dir)
    os.close(handle)
    contact = Path(name)
    args = ["ffmpeg", "-hide_banner", "-loglevel", "error", "-y"]
    for item in frames:
        args += ["-i", item["path"]]
    args += ["-filter_complex", "xstack=inputs=5:layout=0_0|320_0|640_0|960_0|1280_0",
             "-frames:v", "1", "-q:v", "3", str(contact)]
    result = _run(args)
    if result.returncode or not contact.is_file() or contact.stat().st_size == 0:
        contact.unlink(missing_ok=True)
        raise ValueError("QC contact sheet creation failed")
    contact_ref = _promote_content_addressed(contact, output_dir, "contact_sheet")
    frame_refs = [{"path": f["path"], "sha256": f["sha256"]} for f in frames]
    rows: list[QCEvidence] = []
    for gate, gate_criteria in (criteria or DEFAULT_CRITERIA).items():
        for criterion, question in gate_criteria:
            rows.append(evidence(asset=asset, evaluator_type="ffmpeg", evaluator_version=POLICY_VERSION,
                                 gate=gate, criterion=criterion,
                                 observation="Human review required: " + question,
                                 verdict="uncertain", source_artifacts=[contact_ref, *frame_refs]))
    signals = {}
    filters = {
        "black_intervals": ("blackdetect=d=0.2:pix_th=0.10", r"black_start:(\d+(?:\.\d+)?)\s+black_end:(\d+(?:\.\d+)?)"),
        "freeze_intervals": ("freezedetect=n=-60dB:d=0.5", r"freeze_start:\s*(\d+(?:\.\d+)?)|freeze_end:\s*(\d+(?:\.\d+)?)"),
    }
    for criterion, (filter_spec, pattern) in filters.items():
        result = _run(["ffmpeg", "-hide_banner", "-nostats", "-i", str(source),
                       "-vf", filter_spec, "-an", "-f", "null", "-"], timeout=120)
        if result.returncode:
            observation = "signal extraction unavailable"
            count = None
        else:
            count = len(re.findall(pattern, result.stderr))
            observation = f"{criterion} detector event_count={count}; advisory only"
        signals[criterion] = count
        rows.append(evidence(asset=asset, evaluator_type="temporal_heuristic",
                             evaluator_version="ffmpeg-" + POLICY_VERSION, gate="visual",
                             criterion=criterion, observation=observation, verdict="uncertain",
                             source_artifacts=[{"path": str(source), "sha256": asset.sha256}]))
    return rows, {"frames": frames, "contact_sheet": contact_ref, "signals": signals}


def make_pair_sheet(first: dict, second: dict, output_dir: Path) -> dict:
    """Place verified per-shot contact sheets side by side for human comparison."""
    left, right = first["contact_sheet"], second["contact_sheet"]
    for item in (left, right):
        if item is None or file_sha256(Path(item["path"])) != item["sha256"]:
            raise ValueError("pair contact source mismatch")
    output_dir = output_dir.resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    handle, name = tempfile.mkstemp(prefix="qc_pair_", suffix=".jpg", dir=output_dir)
    os.close(handle)
    staging = Path(name)
    result = _run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-y",
                   "-i", left["path"], "-i", right["path"],
                   "-filter_complex", "hstack=inputs=2", "-frames:v", "1",
                   "-q:v", "3", str(staging)])
    if result.returncode or not staging.is_file() or staging.stat().st_size == 0:
        staging.unlink(missing_ok=True)
        raise ValueError("pair contact sheet creation failed")
    return _promote_content_addressed(staging, output_dir, "shot1_vs_shot2")


def list_gemini_models(key_file: Path) -> list[str]:
    """Read the existing local key without printing or persisting it."""
    keys = [line.strip() for line in key_file.read_text(encoding="utf-8-sig").splitlines()
            if line.strip() and not line.lstrip().startswith("#")]
    if not keys:
        raise ValueError("configured Gemini key file is empty")
    request = urllib.request.Request("https://generativelanguage.googleapis.com/v1beta/models?pageSize=1000",
                                     headers={"x-goog-api-key": keys[0]}, method="GET")
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            payload = json.load(response)
    except (urllib.error.URLError, ValueError) as exc:
        raise RuntimeError("GEMINI_MODEL_DISCOVERY_UNAVAILABLE") from None
    return sorted(model["name"].removeprefix("models/") for model in payload.get("models", [])
                  if "generateContent" in model.get("supportedGenerationMethods", []))


def gemini_advisory(asset: Asset, frames: list[dict], *, key_file: Path,
                    model: str, criteria=None) -> tuple[list[QCEvidence], dict]:
    """One bounded sampled-frame advisory call; no model result controls selection."""
    available = list_gemini_models(key_file)
    if model not in available:
        raise ValueError("configured model unavailable for generateContent")
    keys = [line.strip() for line in key_file.read_text(encoding="utf-8-sig").splitlines()
            if line.strip() and not line.lstrip().startswith("#")]
    criterion_groups = criteria or DEFAULT_CRITERIA
    questions = {criterion: question for group in criterion_groups.values()
                 for criterion, question in group}
    prompt = ("You are an advisory shot QC observer. The five images are chronological samples of one "
              "8-second video, each labeled by time. Respond with JSON only: an object with a 'findings' "
              "array. Include exactly one entry per criterion: criterion, verdict (pass/fail/uncertain), "
              "confidence (0..1), observation (short concrete visible fact), time_ranges (array of [start,end] "
              "seconds). Never infer absence of a person throughout the video from sampled frames; use "
              "uncertain when temporal evidence is insufficient. Criteria: " + canonical_json(questions))
    parts = [{"text": prompt}]
    for frame in frames:
        parts.append({"text": f"Frame at {frame['time_s']} seconds"})
        parts.append({"inline_data": {"mime_type": "image/jpeg",
                                       "data": base64.b64encode(Path(frame["path"]).read_bytes()).decode("ascii")}})
    body = {"contents": [{"parts": parts}],
            "generationConfig": {"responseMimeType": "application/json", "temperature": 0}}
    request = urllib.request.Request(
        f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent",
        data=json.dumps(body).encode("utf-8"),
        headers={"x-goog-api-key": keys[0], "Content-Type": "application/json"}, method="POST")
    started = time.perf_counter()
    try:
        with urllib.request.urlopen(request, timeout=90) as response:
            result = json.load(response)
    except (urllib.error.URLError, ValueError):
        raise RuntimeError("GEMINI_ADVISORY_UNAVAILABLE") from None
    latency = round(time.perf_counter() - started, 3)
    try:
        raw = result["candidates"][0]["content"]["parts"][0]["text"]
        findings = json.loads(raw)["findings"]
        by_criterion = {entry["criterion"]: entry for entry in findings}
        if len(findings) != len(questions) or set(by_criterion) != set(questions):
            raise ValueError("VLM criteria mismatch")
        rows = []
        for gate, group in criterion_groups.items():
            for criterion, _ in group:
                item = by_criterion[criterion]
                verdict = item["verdict"]
                if verdict not in {"pass", "fail", "uncertain"}:
                    raise ValueError("bad VLM verdict")
                observation = str(item["observation"])[:500]
                confidence = float(item["confidence"])
                if not 0 <= confidence <= 1:
                    raise ValueError("bad VLM confidence")
                ranges = item.get("time_ranges", [])
                if not isinstance(ranges, list) or any(
                        not isinstance(span, list) or len(span) != 2 or
                        not all(isinstance(point, (int, float)) for point in span) or
                        not 0 <= span[0] <= span[1] <= asset.duration_s
                        for span in ranges):
                    raise ValueError("bad VLM time range")
                # A model failure is an advisory candidate, not a policy failure code.
                rows.append(evidence(asset=asset, evaluator_type="vlm", evaluator_version=model,
                                     gate=gate, criterion=criterion, observation=observation,
                                     verdict=verdict, confidence=confidence,
                                     time_range_s=tuple(ranges[0]) if ranges else None,
                                     source_artifacts=[{"path": f["path"], "sha256": f["sha256"]}
                                                       for f in frames]))
    except (KeyError, IndexError, TypeError, ValueError, json.JSONDecodeError):
        raise RuntimeError("GEMINI_ADVISORY_MALFORMED") from None
    usage = result.get("usageMetadata", {})
    safe_usage = {k: usage[k] for k in ("promptTokenCount", "candidatesTokenCount", "totalTokenCount")
                  if isinstance(usage.get(k), int)}
    return rows, {"used": True, "model": model, "input_strategy": "five timestamped sampled frames",
                  "latency_s": latency, "usage": safe_usage, "cost": "unknown"}
