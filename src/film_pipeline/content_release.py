"""Content input contracts + final content release compiler (Package-015).

Covers four frozen boundaries:

- NarrationSourceReceipt: the ONLY way a real narration asset enters the
  pipeline (no synthesis, no fake scripts; fails closed on every drift).
- TimedCaptionSource: the ONLY way timed captions enter (SRT/VTT;
  timings are never invented; overlap cues are refused, never silently
  fixed).
- ContentReleaseInputBundle: optional inputs to the final content
  release, bound to the exact canonical master; grants ZERO provider
  generation authority.
- FinalContentReleaseCompiler: dry-run gate reporter — derives gate
  truth, never fakes missing content, and refuses to compile a release
  while any mandatory gate is blocked.
- SemanticQCWaiverDecision: the Owner waiver route (authorized by the
  Package-011 release contract: "a semantic model that passes the frozen
  corpus or an Owner waiver"). It may satisfy the semantic RELEASE gate;
  it never rewrites semantic truth to PASS and never flips
  SEMANTIC_AUTONOMOUS_READY.
"""
from __future__ import annotations

import hashlib
import json
import re
import subprocess
from pathlib import Path
from typing import Literal

from pydantic import Field, model_validator

from .core import ContractModel, canonical_json, sha256

NARRATION_RECEIPT_VERSION = "narration-source-receipt-v1"
CAPTION_SOURCE_VERSION = "timed-caption-source-v1"
BUNDLE_VERSION = "content-release-input-bundle-v1"
WAIVER_VERSION = "semantic-qc-waiver-decision-v1"
SUPPORTED_AUDIO_MIME = ("audio/wav", "audio/x-wav", "audio/mpeg",
                        "audio/aac", "audio/flac", "audio/ogg")
TIMESTAMP_RE = re.compile(
    r"^(?:(?P<h>\d{1,2}):)?(?P<m>\d{1,2}):(?P<s>\d{1,2})[,.]"
    r"(?P<ms>\d{1,3})$")


def _file_sha256(path: Path) -> str:
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def _probe_audio(path: Path) -> dict:
    """Local read-only probe: duration, sample rate, channels (ffprobe)."""
    out = subprocess.run(
        ["ffprobe", "-v", "error", "-select_streams", "a:0",
         "-show_entries", "stream=sample_rate,channels",
         "-show_entries", "format=duration", "-of", "json", str(path)],
        capture_output=True, text=True, check=True)
    info = json.loads(out.stdout)
    stream = info["streams"][0]
    return {"duration_s": float(info["format"]["duration"]),
            "sample_rate": int(stream["sample_rate"]),
            "channels": int(stream["channels"])}


class NarrationSourceReceipt(ContractModel):
    """Authoritative narration input — who made it, from what text,
    as exactly which bytes. No field is optional where authority is
    concerned."""
    schema_version: Literal["narration-source-receipt-v1"] = \
        NARRATION_RECEIPT_VERSION
    project: str = Field(min_length=1)
    story_authority_id: str = Field(min_length=1)
    story_authority_sha256: str = Field(pattern=r"^[a-f0-9]{64}$")
    text_authority_id: str = Field(min_length=1)
    text_authority_sha256: str = Field(pattern=r"^[a-f0-9]{64}$")
    audio_locator: str = Field(min_length=1)  # repo-relative; never abs
    audio_sha256: str = Field(pattern=r"^[a-f0-9]{64}$")
    duration_s: float = Field(gt=0)
    sample_rate: int = Field(gt=0)
    channels: int = Field(gt=0)
    mime_type: str
    voice_provenance: str = Field(min_length=1)  # performer/engine+config
    production_provenance: str = Field(min_length=1)  # who produced, when
    license_note: str = ""
    transcript_authority_id: str = ""
    timed_transcript_identity: str = ""

    @model_validator(mode="after")
    def validate_basic(self):
        if self.mime_type not in SUPPORTED_AUDIO_MIME:
            raise ValueError(f"unsupported audio mime {self.mime_type}")
        if Path(self.audio_locator).is_absolute() or ".." in \
                Path(self.audio_locator).parts:
            raise ValueError("audio locator must be repo-relative")
        return self

    def digest(self) -> str:
        return sha256(canonical_json(self.model_dump(mode="json")))


def verify_narration_receipt(receipt: NarrationSourceReceipt, *,
                             project: str,
                             story_authority: dict,
                             sample_rate: int = 48000,
                             channels: tuple[int, ...] = (1, 2),
                             expected_duration_s: float | None = None,
                             drift_tolerance_s: float = 0.05,
                             base_dir: Path | None = None) -> dict:
    """Fail-closed verification against the actual bytes on disk.

    Refuses: wrong project, wrong/unknown story authority, missing text
    authority, hash drift (receipt vs disk = source mutation), unsupported
    audio, probe mismatch (duration/sample rate/channels), and a duration
    that contradicts the declared master target when one is given.
    """
    if receipt.project != project:
        raise ValueError("narration receipt is bound to another project")
    if story_authority.get("story_authority_id") != \
            receipt.story_authority_id or \
            story_authority.get("story_authority_sha256") != \
            receipt.story_authority_sha256:
        raise ValueError("story authority unknown or drift")
    for field in ("text_authority_id", "text_authority_sha256"):
        if not getattr(receipt, field):
            raise ValueError(f"missing text authority: {field}")
    audio = (base_dir or Path.cwd()) / receipt.audio_locator
    if not audio.is_file():
        raise ValueError("narration audio file missing")
    if _file_sha256(audio) != receipt.audio_sha256:
        raise ValueError("narration audio hash drift (source mutation)")
    probe = _probe_audio(audio)
    if abs(probe["duration_s"] - receipt.duration_s) > drift_tolerance_s:
        raise ValueError("narration duration mismatch vs probed file")
    if probe["sample_rate"] != receipt.sample_rate:
        raise ValueError("narration sample rate mismatch vs probed file")
    if probe["channels"] != receipt.channels:
        raise ValueError("narration channel mismatch vs probed file")
    if receipt.sample_rate != sample_rate:
        raise ValueError(f"narration sample rate must be {sample_rate}")
    if receipt.channels not in channels:
        raise ValueError("narration channels must be mono or stereo")
    if expected_duration_s is not None and \
            receipt.duration_s > expected_duration_s + drift_tolerance_s:
        raise ValueError("narration longer than the master target duration")
    return {"verified": True, "probed": probe,
            "audio_sha256": receipt.audio_sha256}


class TimedCaptionSource(ContractModel):
    """Authoritative timed captions (SRT/VTT). Timings are validated,
    never synthesized or adjusted."""
    schema_version: Literal["timed-caption-source-v1"] = \
        CAPTION_SOURCE_VERSION
    project: str = Field(min_length=1)
    story_authority_id: str = Field(min_length=1)
    transcript_authority_id: str = Field(min_length=1)
    format: Literal["srt", "vtt"]
    caption_locator: str = Field(min_length=1)
    caption_sha256: str = Field(pattern=r"^[a-f0-9]{64}$")
    language: str = Field(min_length=2)
    lineage: dict
    cues: list[dict] = []

    @model_validator(mode="after")
    def validate_basic(self):
        if Path(self.caption_locator).is_absolute() or ".." in \
                Path(self.caption_locator).parts:
            raise ValueError("caption locator must be repo-relative")
        return self

    def digest(self) -> str:
        return sha256(canonical_json(self.model_dump(mode="json")))


def _parse_timestamp(text: str) -> float:
    match = TIMESTAMP_RE.match(text.strip())
    if not match:
        raise ValueError(f"malformed caption timestamp {text!r}")
    parts = match.groupdict()
    return ((int(parts["h"] or 0)) * 3600 + int(parts["m"]) * 60 +
            int(parts["s"]) + int(parts["ms"].ljust(3, "0")) / 1000.0)


def parse_captions(raw: bytes, fmt: str) -> list[dict]:
    """Strict SRT/VTT cue parsing. Refuses bad encoding, malformed
    timestamps, non-increasing ordering, negative times, end <= start,
    and overlapping cues (nothing is silently fixed)."""
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise ValueError(f"captions are not valid UTF-8: {exc}") from exc
    if fmt == "vtt":
        if not text.lstrip("\ufeff").startswith("WEBVTT"):
            raise ValueError("VTT source must start with WEBVTT")
    cues = []
    blocks = re.split(r"\n\s*\n", text.strip())
    previous_end = -1.0
    previous_start = -1.0
    for block in blocks:
        lines = [ln for ln in block.splitlines() if ln.strip()]
        if not lines:
            continue
        if fmt == "vtt" and lines[0].lstrip("\ufeff").startswith("WEBVTT"):
            continue
        timing_line = next((ln for ln in lines if "-->" in ln), None)
        if timing_line is None:
            raise ValueError("caption block without a timing line")
        start_raw, end_raw = [p.strip() for p in
                              timing_line.split("-->")] if \
            timing_line.count("-->") == 1 else (None, None)
        if start_raw is None:
            raise ValueError("malformed cue timing line")
        start, end = _parse_timestamp(start_raw), _parse_timestamp(end_raw)
        if start < 0 or end <= start:
            raise ValueError(f"invalid cue window {start}-{end}")
        if start < previous_start:
            raise ValueError("cue ordering is not increasing")
        if start < previous_end:
            raise ValueError(f"overlapping cues refused "
                             f"(cue starts {start} before previous end "
                             f"{previous_end}); fix at the source")
        payload = [ln for ln in lines if "-->" not in ln and
                   not ln.strip().isdigit() and
                   not ln.lstrip("\ufeff").startswith("WEBVTT")]
        cues.append({"start_s": round(start, 3), "end_s": round(end, 3),
                     "text": "\n".join(payload)})
        previous_start, previous_end = start, end
    if not cues:
        raise ValueError("caption source contains no cues")
    return cues


def verify_caption_source(source: TimedCaptionSource, *, project: str,
                          story_authority: dict,
                          master_duration_s: float,
                          base_dir: Path | None = None) -> dict:
    """Fail-closed caption verification: bytes, parse, master bounds."""
    if source.project != project:
        raise ValueError("caption source is bound to another project")
    if story_authority.get("story_authority_id") != \
            source.story_authority_id:
        raise ValueError("caption story binding unknown or drift")
    caption_path = (base_dir or Path.cwd()) / source.caption_locator
    if not caption_path.is_file():
        raise ValueError("caption file missing")
    if _file_sha256(caption_path) != source.caption_sha256:
        raise ValueError("caption hash drift (source mutation)")
    cues = parse_captions(caption_path.read_bytes(), source.format)
    for cue in cues:
        if cue["end_s"] > master_duration_s:
            raise ValueError(
                f"cue ends {cue['end_s']}s beyond the canonical master "
                f"duration {master_duration_s}s")
    source.cues = cues
    return {"verified": True, "cues": len(cues),
            "last_end_s": cues[-1]["end_s"]}


class SemanticQCWaiverDecision(ContractModel):
    """Owner waiver of the semantic release gate.

    Existing product truth (Package-011 release contract) authorizes the
    route. It satisfies the semantic RELEASE gate as OWNER_WAIVED; it
    NEVER rewrites semantic observations to PASS and never flips
    SEMANTIC_AUTONOMOUS_READY (stays false)."""
    schema_version: Literal["semantic-qc-waiver-decision-v1"] = \
        WAIVER_VERSION
    project: str = Field(min_length=1)
    master_sha256: str = Field(pattern=r"^[a-f0-9]{64}$")
    reason: str = Field(min_length=1)
    known_limitations: list[str] = Field(min_length=1)
    waived_at: str
    decision_source: Literal["OWNER"]
    semantic_autonomous_ready_after_waiver: Literal[False] = False
    semantic_qc_gate_effect: Literal["OWNER_WAIVED"] = "OWNER_WAIVED"

    def digest(self) -> str:
        return sha256(canonical_json(self.model_dump(mode="json")))


class ContentReleaseInputBundle(ContractModel):
    """Optional content inputs to the final content release.

    Binds to the exact canonical master identity + project + canonical
    lineage version. Grants ZERO provider generation authority: the
    release builder may consume it once mandatory gates are satisfied;
    nothing here can trigger Generate."""
    schema_version: Literal["content-release-input-bundle-v1"] = \
        BUNDLE_VERSION
    project: str = Field(min_length=1)
    master_sha256: str = Field(pattern=r"^[a-f0-9]{64}$")
    canonical_lineage_version: str = Field(min_length=1)
    narration_receipt_digest: str = ""
    caption_source_digest: str = ""
    owner_decisions_digest: str = ""
    semantic_waiver_digest: str = ""
    notes: str = ""

    @model_validator(mode="after")
    def validate_no_authority(self):
        blob = canonical_json(self.model_dump(mode="json")).lower()
        for forbidden in ("generate", "mutation_authority", "provider_job"):
            if f'"{forbidden}' in blob:
                raise ValueError(
                    f"content input bundle must not carry provider "
                    f"authority ({forbidden})")
        return self

    def digest(self) -> str:
        return sha256(canonical_json(self.model_dump(mode="json")))


class FinalContentReleaseCompiler:
    """Dry-run gate reporter / fail-closed release builder.

    Inputs: the current canonical technical master receipt, the current
    DeliveryManifest truth, and the ContentReleaseInputBundle. The gate
    report derives each gate's truth from those inputs — nothing about
    the remaining gates is hard-coded. Missing content is never faked:
    while any mandatory gate is blocked the result is
    FINAL_CONTENT_RELEASE_BLOCKED and compile_release refuses to run.
    """

    def __init__(self, *, project: str, master_receipt: dict,
                 manifest_truth: dict, bundle: ContentReleaseInputBundle,
                 owner_decision_state: dict | None = None,
                 narration_verification: dict | None = None,
                 caption_verification: dict | None = None,
                 semantic_autonomous_ready: bool = False,
                 semantic_waiver: SemanticQCWaiverDecision | None = None):
        self.project = project
        self.master_receipt = master_receipt
        self.manifest_truth = manifest_truth
        self.bundle = bundle
        self.owner_decision_state = owner_decision_state
        self.narration_verification = narration_verification
        self.caption_verification = caption_verification
        self.semantic_autonomous_ready = semantic_autonomous_ready
        self.semantic_waiver = semantic_waiver
        self._validate_bundle_binding()

    def _validate_bundle_binding(self) -> None:
        if self.bundle.project != self.project:
            raise ValueError("bundle bound to another project")
        if self.bundle.master_sha256 != \
                self.master_receipt["output_sha256"]:
            raise ValueError(
                "bundle binds a different master than the canonical "
                "technical master (release input refused)")

    def gate_report(self) -> dict:
        master_sha = self.master_receipt["output_sha256"]
        owner_state = self.owner_decision_state or {}
        owner_complete = bool(owner_state) and all(
            state == "ACCEPT" for state in owner_state.values())
        semantic_satisfied, semantic_truth = self._semantic_gate()
        gates = [
            self._gate("VISUAL_TECHNICAL_MASTER", True,
                       "PROVEN (master_package_010 conformance)",
                       not self.master_receipt.get("full_decode", False),
                       f"master {master_sha[:12]}…"),
            self._gate("UPLOAD_CONTRACT", True,
                       "PROVEN (009 single authority domain)",
                       False, "authority_equivalence_009.json"),
            self._gate("EDITORIAL", True,
                       "PROVEN (MASTER_EDITORIAL_010_V1)",
                       self.master_receipt.get("version") !=
                       "master-editorial-010-v1",
                       self.master_receipt.get("version", "")),
            self._gate("OWNER_TAKE_REVIEW", True,
                       "PENDING (no Owner decision file imported)"
                       if not owner_state else
                       f"state={sorted(owner_state.items())}",
                       not owner_complete,
                       "OwnerReviewDecisionSet" if owner_complete else
                       None),
            self._gate("SEMANTIC_RELEASE", True, semantic_truth,
                       not semantic_satisfied,
                       "SemanticQCWaiverDecision" if
                       self.semantic_waiver else None),
            self._gate("PRODUCTION_NARRATION", True,
                       "CONTENT_AUDIO_PRODUCTION_UNQUALIFIED (no "
                       "authoritative narration source)",
                       self.narration_verification is None,
                       "NarrationSourceReceipt" if
                       self.narration_verification else None),
            self._gate("TIMED_CAPTIONS", True,
                       "TIMED_CAPTION_AUTHORITY_UNAVAILABLE",
                       self.caption_verification is None,
                       "TimedCaptionSource" if
                       self.caption_verification else None),
        ]
        blocked = [g["name"] for g in gates if g["blocking"]]
        return {
            "version": "final-release-gate-report-v1",
            "mode": "DRY_RUN_GATE_REPORT",
            "project": self.project,
            "master_sha256": master_sha,
            "bundle_digest": self.bundle.digest(),
            "gates": gates,
            "blocked_gates": blocked,
            "release_state": "FINAL_CONTENT_RELEASE_BLOCKED" if blocked
            else "FINAL_CONTENT_RELEASE_READY",
            "provider_generation_authority": "NONE",
        }

    def _semantic_gate(self) -> tuple[bool, str]:
        if self.semantic_autonomous_ready:
            return True, "SEMANTIC_AUTONOMOUS_BACKEND_QUALIFIED"
        if self.semantic_waiver is not None:
            if self.semantic_waiver.master_sha256 != \
                    self.master_receipt["output_sha256"]:
                raise ValueError(
                    "semantic waiver binds a different master; refused")
            return True, "SEMANTIC_QC_GATE = OWNER_WAIVED (semantic " \
                         "truth unchanged: NOT_QUALIFIED backend; " \
                         "SEMANTIC_AUTONOMOUS_READY stays false)"
        return False, ("no qualified autonomous backend "
                       "(WORKER_SEMANTIC_BACKEND = NOT_QUALIFIED) and "
                       "no Owner waiver")

    @staticmethod
    def _gate(name: str, required: bool, current_truth: str,
              blocking: bool, satisfying_artifact) -> dict:
        return {"name": name, "required": required,
                "current_truth": current_truth, "blocking": blocking,
                "satisfying_artifact": satisfying_artifact}

    def compile_release(self) -> dict:
        """Fail closed: a release is only compilable with zero blocked
        gates. The dry-run gate report is the deliverable until then."""
        report = self.gate_report()
        if report["blocked_gates"]:
            raise ValueError(
                f"FINAL_CONTENT_RELEASE_BLOCKED — refusing to compile a "
                f"release with blocked gates: {report['blocked_gates']}")
        raise NotImplementedError(
            "release compilation requires real Owner/content inputs; "
            "the compiler is proven offline in gate-report mode only")
