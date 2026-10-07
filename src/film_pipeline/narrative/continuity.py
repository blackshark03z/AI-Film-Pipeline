"""V2-021 Phases L-N — continuity QC engine, repair planner, editorial
intelligence.

Numeric thresholds are ADVISORY; verdicts come from deterministic visual
evidence classes (contact sheets, junction frames, full-res keyframes)
combined with typed continuity contracts. Guards against the V2-020
false-failure class (medium darker than wide because rock fills frame)
and false-pass class (similar average color, wrong geography).
"""
from __future__ import annotations

from typing import Literal

from pydantic import Field

from ..core import ContractModel

FailureClass = Literal[
    "PROMPT_REPAIRABLE", "EDITORIAL_REPAIRABLE", "FINISHING_REPAIRABLE",
    "PROVIDER_CAPABILITY_GAP", "STORY_DESIGN_GAP",
]


class ContinuityDimension(ContractModel):
    dimension: str
    verdict: Literal["PASS", "FAIL", "NOT_ASSESSED"] = "NOT_ASSESSED"
    evidence: str = ""
    advisory_metrics: dict = Field(default_factory=dict)


class ShotQCReport(ContractModel):
    shot_id: str
    technical: dict = Field(default_factory=dict)
    shot_local: list[ContinuityDimension] = Field(default_factory=list)
    cut_compatibility: list[ContinuityDimension] = Field(default_factory=list)
    verdict: Literal["ACCEPT", "REPAIR_REQUIRED", "REJECT"] = "ACCEPT"
    failure_class: FailureClass | None = None


class ContinuityEngine:
    """Phase L+M — shot-local validity + incoming cut compatibility.

    Contract dimensions are judged from EVIDENCE RECORDS (produced by the
    runner: contact sheets + keyframes reviewed by the pipeline QC
    operator). Threshold metrics (luma/saturation/MAD) are attached as
    ADVISORY context and can never alone flip a verdict.
    """

    DIMENSIONS = ("IDENTITY", "WORLD", "GEOGRAPHY", "LIGHTING", "WEATHER",
                  "WARDROBE", "PROP_STATE", "SCREEN_DIRECTION", "EYELINE",
                  "MOTION", "BODY_ORIENTATION", "ACTION_STATE",
                  "NARRATIVE_STATE")

    def evaluate_shot(self, *, shot_id: str, technical: dict,
                      evidence: dict) -> ShotQCReport:
        """evidence: {dimension: {"verdict": PASS/FAIL, "evidence": str}}
        for shot-local; plus optional {"cut": {dimension: ...}}."""
        report = ShotQCReport(shot_id=shot_id, technical=technical)
        failures = []
        for dimension in self.DIMENSIONS:
            record = (evidence.get("shot_local") or {}).get(dimension)
            entry = ContinuityDimension(
                dimension=dimension,
                verdict=(record or {}).get("verdict", "NOT_ASSESSED"),
                evidence=(record or {}).get("evidence", ""),
                advisory_metrics=(record or {}).get("metrics", {}))
            report.shot_local.append(entry)
            if entry.verdict == "FAIL":
                failures.append((dimension, "shot_local"))
        for dimension, record in (evidence.get("cut") or {}).items():
            entry = ContinuityDimension(
                dimension=dimension,
                verdict=record.get("verdict", "NOT_ASSESSED"),
                evidence=record.get("evidence", ""),
                advisory_metrics=record.get("metrics", {}))
            report.cut_compatibility.append(entry)
            if entry.verdict == "FAIL":
                failures.append((dimension, "cut"))
        hard_technical = (not technical.get("decode_ok"))
        if hard_technical or any(d == "IDENTITY" for d, _ in failures):
            report.verdict = "REJECT"
            report.failure_class = "PROVIDER_CAPABILITY_GAP" \
                if hard_technical else "PROMPT_REPAIRABLE"
        elif failures:
            report.verdict = "REPAIR_REQUIRED"
            report.failure_class = self._classify(failures)
        else:
            report.verdict = "ACCEPT"
        return report

    @staticmethod
    def _classify(failures) -> FailureClass:
        dimensions = {d for d, _ in failures}
        if dimensions & {"SCREEN_DIRECTION", "EYELINE",
                         "BODY_ORIENTATION", "MOTION"}:
            return "PROMPT_REPAIRABLE"
        if dimensions & {"PROP_STATE", "ACTION_STATE", "NARRATIVE_STATE"}:
            return "STORY_DESIGN_GAP"
        return "PROMPT_REPAIRABLE"


class RepairPlanner:
    """Phase N — MINIMAL truth delta: change ONLY failing dimensions,
    keep accepted truths verbatim."""

    def plan(self, report: ShotQCReport, truth: dict) -> dict:
        failing = [d.dimension for d in report.shot_local
                   if d.verdict == "FAIL"]
        failing += [d.dimension for d in report.cut_compatibility
                    if d.verdict == "FAIL"]
        delta = {k.lower(): v for k, v in truth.items()
                 if k.lower() in {f.lower() for f in failing}}
        return {
            "shot_id": report.shot_id,
            "failure_class": report.failure_class,
            "accepted_truths_kept": [k for k in truth
                                     if k.lower() not in
                                     {f.lower() for f in failing}],
            "changed_dimensions": delta,
            "prompt_edit_policy": "ONLY failing sections are rewritten; "
                                  "all other sections byte-identical",
        }


class EditorialIntelligence:
    """Phase O — editorial trim BEFORE generation repair; exact frame
    authority retained."""

    def propose_trim(self, *, qc_report: ShotQCReport,
                     junction_metrics: dict,
                     fps: float = 24.0) -> dict:
        """If the failure is at a cut (motion phase/entrance), propose a
        bounded tail trim instead of regeneration."""
        if qc_report.verdict != "REPAIR_REQUIRED":
            return {"trim_frames": 0, "regenerate": False}
        cut_fail = any(d.verdict == "FAIL" for d in
                       qc_report.cut_compatibility)
        motion_ok = not any(d.dimension == "MOTION" and d.verdict == "FAIL"
                            for d in qc_report.shot_local)
        if cut_fail and motion_ok:
            frames = int(junction_metrics.get("tail_trim_frames", 6))
            return {"trim_frames": min(frames, 12), "regenerate": False,
                    "rationale": "cut-phase defect; shot-local truth is "
                                 "intact — trim before regeneration"}
        return {"trim_frames": 0, "regenerate": True}
