"""Reproducible shot QC with separate evidence, report, and human authority."""

from __future__ import annotations

import json
import sqlite3
import subprocess
import time
from pathlib import Path
from typing import Literal

from pydantic import Field, model_validator

from .core import ContractModel, canonical_json, sha256, validate_contract
from .live_runtime import Asset, file_sha256, inspect_video
from .store import SQLiteStore

POLICY_VERSION = "qc-v1.0"
DURATION_TOLERANCE_S = 0.5
GATES = ("technical", "visual", "continuity", "editorial")
HUMAN_GATES = ("visual", "continuity", "editorial")
REQUIRED_TECHNICAL_CRITERIA = frozenset({"file_nonempty", "asset_sha256", "valid_video_stream",
                                         "stored_metadata", "duration_target", "full_video_decode"})


class QCEvidence(ContractModel):
    evidence_id: str
    asset_id: str
    generation_attempt_id: str
    evaluator_type: Literal["ffprobe", "ffmpeg", "temporal_heuristic", "vlm", "human"]
    evaluator_version: str
    gate: Literal["technical", "visual", "continuity", "editorial"]
    criterion: str
    observation: str
    verdict: Literal["pass", "fail", "uncertain"]
    failure_code: str | None = None
    confidence: float | None = Field(default=None, ge=0, le=1)
    time_range_s: tuple[float, float] | None = None
    source_artifacts: list[dict[str, str]] = Field(default_factory=list)

    @model_validator(mode="after")
    def check_identity(self):
        basis = self.model_dump(mode="json", exclude={"evidence_id"})
        if self.evidence_id != "qce_" + sha256(basis):
            raise ValueError("evidence identity mismatch")
        if self.verdict == "fail" and not self.failure_code:
            raise ValueError("failed evidence needs a failure code")
        return self


def evidence(*, asset: Asset, evaluator_type: str, evaluator_version: str,
             gate: str, criterion: str, observation: str, verdict: str,
             failure_code: str | None = None, confidence: float | None = None,
             time_range_s: tuple[float, float] | None = None,
             source_artifacts: list[dict[str, str]] | None = None) -> QCEvidence:
    data = dict(asset_id=asset.asset_id, generation_attempt_id=asset.source_attempt_id,
                evaluator_type=evaluator_type, evaluator_version=evaluator_version,
                gate=gate, criterion=criterion, observation=observation,
                verdict=verdict, failure_code=failure_code, confidence=confidence,
                time_range_s=time_range_s, source_artifacts=source_artifacts or [])
    return QCEvidence(evidence_id="qce_" + sha256(data), **data)


class HumanDecision(ContractModel):
    decision_id: str
    asset_id: str
    generation_attempt_id: str
    reviewer_id: str
    action: Literal["APPROVE", "REJECT", "NEEDS_REVIEW"]
    visual_pass: bool | None = None
    continuity_pass: bool | None = None
    editorial_pass: bool | None = None
    failure_codes: list[str] = Field(default_factory=list)
    failure_observations: dict[str, str] = Field(default_factory=dict)
    notes: list[str] = Field(default_factory=list)
    vlm_assisted: bool = False

    @model_validator(mode="after")
    def check_authority(self):
        basis = self.model_dump(mode="json", exclude={"decision_id"})
        if self.decision_id != "human_" + sha256(basis):
            raise ValueError("human decision identity mismatch")
        if not self.reviewer_id.strip():
            raise ValueError("reviewer identity required")
        gates = (self.visual_pass, self.continuity_pass, self.editorial_pass)
        if self.action == "APPROVE" and (gates != (True, True, True) or self.failure_codes):
            raise ValueError("approval requires all subjective gates passed")
        if self.action == "REJECT" and (False not in gates or not self.failure_codes):
            raise ValueError("rejection requires a failed gate and failure codes")
        if self.action == "NEEDS_REVIEW" and (False in gates or self.failure_codes):
            raise ValueError("needs review cannot assert a confirmed failure")
        if set(self.failure_observations) != set(self.failure_codes) or any(
                not observation.strip() for observation in self.failure_observations.values()):
            raise ValueError("each failure code requires a concrete human observation")
        return self


def human_decision(*, asset: Asset, reviewer_id: str, action: str,
                   visual_pass: bool | None = None, continuity_pass: bool | None = None,
                   editorial_pass: bool | None = None, failure_codes: list[str] | None = None,
                   failure_observations: dict[str, str] | None = None,
                   notes: list[str] | None = None, vlm_assisted: bool = False) -> HumanDecision:
    data = dict(asset_id=asset.asset_id, generation_attempt_id=asset.source_attempt_id,
                reviewer_id=reviewer_id, action=action, visual_pass=visual_pass,
                continuity_pass=continuity_pass, editorial_pass=editorial_pass,
                failure_codes=sorted(set(failure_codes or [])),
                failure_observations=failure_observations or {}, notes=notes or [],
                vlm_assisted=vlm_assisted)
    return HumanDecision(decision_id="human_" + sha256(data), **data)


class QCReportRecord(ContractModel):
    asset_id: str
    evidence_ids: list[str]
    human_decision_id: str | None
    report: dict


class SelectedTake(ContractModel):
    selected_take_id: str
    shot_id: str
    generation_attempt_id: str
    asset_id: str
    qc_report_id: str
    selection_authority: Literal["human", "human_with_vlm_assist"]
    reviewer_id: str
    notes: list[str] = Field(default_factory=list)


def derive_report(asset: Asset, evidence_rows: list[QCEvidence],
                  human: HumanDecision | None = None) -> QCReportRecord:
    if not evidence_rows or any(e.asset_id != asset.asset_id or
                                e.generation_attempt_id != asset.source_attempt_id for e in evidence_rows):
        raise ValueError("QC evidence must belong to exact Asset")
    if human and (human.asset_id != asset.asset_id or
                  human.generation_attempt_id != asset.source_attempt_id):
        raise ValueError("human decision belongs to another Asset")
    technical = [e for e in evidence_rows if e.gate == "technical"]
    if not technical:
        raise ValueError("technical evidence missing")
    # Only deterministic technical evidence has automatic gate authority.
    if any(e.evaluator_type not in {"ffprobe", "ffmpeg"} for e in technical):
        raise ValueError("technical gate contains non-deterministic evidence")
    observed_technical = {e.criterion for e in technical}
    technical_issues = sorted({e.failure_code or "TECHNICAL_UNRESOLVED" for e in technical
                               if e.verdict != "pass"} |
                              {"TECHNICAL_CHECK_MISSING:" + criterion for criterion in
                               REQUIRED_TECHNICAL_CRITERIA - observed_technical})
    gates: dict[str, dict] = {"technical": {"pass": not technical_issues,
                                             "issues": technical_issues}}
    human_values = {"visual": human.visual_pass if human else None,
                    "continuity": human.continuity_pass if human else None,
                    "editorial": human.editorial_pass if human else None}
    for gate in HUMAN_GATES:
        if not any(e.gate == gate for e in evidence_rows):
            raise ValueError(f"{gate} evidence missing")
        value = human_values[gate]
        if value is True:
            gates[gate] = {"pass": True, "issues": []}
        elif value is False:
            codes = sorted(c for c in (human.failure_codes if human else [])
                           if c.startswith({"visual": ("VISUAL_", "WORLD_", "IDENTITY_", "CAMERA_", "PERFORMANCE_"),
                                            "continuity": ("CONTINUITY_", "IDENTITY_"),
                                            "editorial": ("EDITORIAL_",)}[gate]))
            if not codes:
                raise ValueError(f"human failed {gate} without matching failure code")
            gates[gate] = {"pass": False, "issues": codes}
        else:
            gates[gate] = {"pass": False, "issues": [gate.upper() + "_HUMAN_REVIEW_REQUIRED"]}
    if human:
        supported = set().union(*(set(gates[gate]["issues"]) for gate in HUMAN_GATES
                                  if human_values[gate] is False))
        if set(human.failure_codes) != supported:
            raise ValueError("human failure codes do not match failed gates")
    if technical_issues or any(human_values[g] is False for g in HUMAN_GATES):
        decision = "fail"
    elif human and human.action == "APPROVE" and all(gates[g]["pass"] for g in GATES):
        decision = "pass"
    else:
        decision = "needs_human_review"
    ids = sorted({e.evidence_id for e in evidence_rows})
    if len(ids) != len(evidence_rows):
        raise ValueError("duplicate QC evidence")
    failure_codes = sorted(set(technical_issues + (human.failure_codes if human else [])))
    basis = {"policy": POLICY_VERSION, "asset_id": asset.asset_id,
             "evidence_ids": ids, "human_decision_id": human.decision_id if human else None}
    report = {"qc_report_id": "qcr_" + sha256(basis),
              "generation_attempt_id": asset.source_attempt_id, "decision": decision,
              **gates, "failure_codes": failure_codes,
              "notes": ["Subjective gates require human authority; advisory evidence alone cannot select a take."]}
    validate_contract("qc_report", report)
    return QCReportRecord(asset_id=asset.asset_id, evidence_ids=ids,
                          human_decision_id=human.decision_id if human else None, report=report)


def derive_disposition(shot_id: str, asset: Asset, record: QCReportRecord,
                       human: HumanDecision | None) -> SelectedTake | dict | None:
    report = record.report
    if report["decision"] == "needs_human_review":
        return None
    if report["decision"] == "pass":
        if not human or human.action != "APPROVE":
            raise ValueError("SelectedTake requires human approval")
        basis = {"shot_id": shot_id, "asset_id": asset.asset_id,
                 "qc_report_id": report["qc_report_id"], "human_decision_id": human.decision_id}
        return SelectedTake(selected_take_id="take_" + sha256(basis), shot_id=shot_id,
                            generation_attempt_id=asset.source_attempt_id,
                            asset_id=asset.asset_id, qc_report_id=report["qc_report_id"],
                            selection_authority="human_with_vlm_assist" if human.vlm_assisted else "human",
                            reviewer_id=human.reviewer_id, notes=human.notes)
    codes = report["failure_codes"]
    if not codes:
        raise ValueError("failed report requires failure codes")
    repair_hints = {
        "CONTINUITY_GEOGRAPHY_DRIFT": ("prompt_recompile",
            "Strengthen the frozen stable-alley-geography constraint across opening and end frames."),
        "CAMERA_MOVEMENT_UNEXPECTED": ("prompt_recompile",
            "Recompile with an explicit locked camera and unchanged start/end framing."),
        "WORLD_WEATHER_MISMATCH": ("prompt_recompile",
            "Recompile for visibly falling rain and wet reflective pavement throughout."),
        "WORLD_TIME_OF_DAY_MISMATCH": ("prompt_recompile",
            "Recompile for night lighting throughout the establishing shot."),
        "IDENTITY_PEOPLE_PRESENT": ("prompt_recompile",
            "Recompile with the critical no-people invariant across the entire shot."),
        "EDITORIAL_UNUSABLE": ("editorial_workaround",
            "Hold this take out of the cut and review existing exact-lineage alternatives."),
    }
    if any(c.startswith("TECHNICAL_") for c in codes):
        strategy = "human_review"
        changes = ["Quarantine the invalid Asset and inspect its exact acquisition receipt and bytes."]
    elif len(codes) == 1 and codes[0] in repair_hints:
        strategy, change = repair_hints[codes[0]]
        changes = [change]
    else:
        strategy = "human_review"
        changes = ["Keep this Asset unselected and classify each confirmed finding against the frozen ShotSpec before proposing a new execution."]
    basis = {"shot_id": shot_id, "from_attempt_id": asset.source_attempt_id,
             "report_id": report["qc_report_id"], "codes": codes}
    repair = {"repair_decision_id": "repair_" + sha256(basis), "shot_id": shot_id,
              "from_attempt_id": asset.source_attempt_id, "failure_codes": codes,
              "strategy": strategy, "changes": changes,
              "next_action": "Owner reviews evidence and authorizes any repair in a later slice.",
              "budget_note": "No Generate authorized in SLICE-0007.",
              "requires_human_approval": True}
    validate_contract("repair_decision", repair)
    return repair


class QCStore:
    """Append-only QC records in the proven runtime DB, with exact Asset links."""

    def __init__(self, runtime: SQLiteStore):
        self.runtime = runtime

    def initialize(self) -> None:
        self.runtime.initialize()
        c = self.runtime._connect()
        try:
            c.executescript("""
                CREATE TABLE IF NOT EXISTS qc_evidence (
                    id TEXT PRIMARY KEY, asset_id TEXT NOT NULL REFERENCES assets(id),
                    attempt_id TEXT NOT NULL REFERENCES generation_attempts(id), payload TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS human_qc_decisions (
                    id TEXT PRIMARY KEY, asset_id TEXT NOT NULL REFERENCES assets(id), payload TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS qc_reports (
                    id TEXT PRIMARY KEY, asset_id TEXT NOT NULL REFERENCES assets(id),
                    human_decision_id TEXT REFERENCES human_qc_decisions(id), payload TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS selected_takes (
                    id TEXT PRIMARY KEY, asset_id TEXT NOT NULL REFERENCES assets(id),
                    report_id TEXT NOT NULL REFERENCES qc_reports(id), payload TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS repair_decisions (
                    id TEXT PRIMARY KEY, report_id TEXT NOT NULL REFERENCES qc_reports(id), payload TEXT NOT NULL);
            """)
        finally:
            c.close()

    @staticmethod
    def _insert(c: sqlite3.Connection, table: str, key: str, payload: str,
                columns: tuple[str, ...], values: tuple[str, ...]) -> None:
        names = ("id", *columns, "payload")
        c.execute(f"INSERT OR IGNORE INTO {table} ({','.join(names)}) VALUES ({','.join('?' for _ in names)})",
                  (key, *values, payload))
        row = c.execute(f"SELECT {','.join(columns)},payload FROM {table} WHERE id=?", (key,)).fetchone()
        if row != (*values, payload):
            raise ValueError(f"immutable {table} identity collision")

    def _exact_asset(self, asset: Asset) -> tuple:
        lineage = self.runtime.read_runtime_lineage(asset.source_attempt_id, asset.provider_job_id)
        if asset not in lineage[5] or lineage[4].status != "SUCCEEDED":
            raise ValueError("QC Asset is not proven in runtime lineage")
        binding = next((b for b in self.runtime.read_output_bindings(asset.provider_job_id)
                        if b["output_id"] == asset.provider_asset_id), None)
        receipt = self.runtime.read_acquisition_record(asset.provider_job_id,
                                                       asset.provider_asset_id, completed=True)
        if not binding or not receipt or asset.rights_metadata != {
                "identity_binding": binding, "acquisition_receipt": receipt}:
            raise ValueError("QC Asset binding or acquisition receipt mismatch")
        return lineage

    @staticmethod
    def _validate_review_artifacts(e: QCEvidence) -> None:
        if e.gate == "technical" or e.evaluator_type == "temporal_heuristic":
            return
        for reference in e.source_artifacts:
            path = Path(reference.get("path", ""))
            if not path.is_file() or file_sha256(path) != reference.get("sha256"):
                raise ValueError("QC review artifact changed or missing")

    def save(self, asset: Asset, evidence_rows: list[QCEvidence],
             human: HumanDecision | None = None) -> tuple[QCReportRecord, SelectedTake | dict | None]:
        shot, _, _, _, _, _ = self._exact_asset(asset)
        record = derive_report(asset, evidence_rows, human)
        disposition = derive_disposition(shot.shot_id, asset, record, human)
        for e in evidence_rows:
            self._validate_review_artifacts(e)
        if isinstance(disposition, SelectedTake):
            path = Path(asset.uri_or_path)
            if not path.is_file() or file_sha256(path) != asset.sha256:
                raise ValueError("SelectedTake requires current exact Asset bytes")
        self.initialize()
        c = self.runtime._connect()
        try:
            with c:
                for e in evidence_rows:
                    self._insert(c, "qc_evidence", e.evidence_id, canonical_json(e.payload()),
                                 ("asset_id", "attempt_id"), (e.asset_id, e.generation_attempt_id))
                if human:
                    self._insert(c, "human_qc_decisions", human.decision_id, canonical_json(human.payload()),
                                 ("asset_id",), (human.asset_id,))
                self._insert(c, "qc_reports", record.report["qc_report_id"], canonical_json(record.payload()),
                             ("asset_id", "human_decision_id"),
                             (asset.asset_id, human.decision_id if human else None))
                if isinstance(disposition, SelectedTake):
                    self._insert(c, "selected_takes", disposition.selected_take_id,
                                 canonical_json(disposition.payload()), ("asset_id", "report_id"),
                                 (asset.asset_id, record.report["qc_report_id"]))
                elif isinstance(disposition, dict):
                    self._insert(c, "repair_decisions", disposition["repair_decision_id"],
                                 canonical_json(disposition), ("report_id",),
                                 (record.report["qc_report_id"],))
        finally:
            c.close()
        return record, disposition

    def read(self, asset: Asset, report_id: str) -> tuple[QCReportRecord, SelectedTake | dict | None]:
        shot, _, _, _, _, _ = self._exact_asset(asset)
        c = self.runtime._connect()
        try:
            row = c.execute("SELECT asset_id,human_decision_id,payload FROM qc_reports WHERE id=?",
                            (report_id,)).fetchone()
            if not row or row[0] != asset.asset_id:
                raise KeyError(report_id)
            record = QCReportRecord.model_validate(json.loads(row[2]))
            if record.asset_id != asset.asset_id or record.report["qc_report_id"] != report_id:
                raise ValueError("QC report identity mismatch")
            evidence_rows = []
            for key in record.evidence_ids:
                erow = c.execute("SELECT asset_id,attempt_id,payload FROM qc_evidence WHERE id=?", (key,)).fetchone()
                if not erow or erow[:2] != (asset.asset_id, asset.source_attempt_id):
                    raise ValueError("QC evidence lineage mismatch")
                e = QCEvidence.model_validate(json.loads(erow[2]))
                if e.evidence_id != key:
                    raise ValueError("QC evidence identity mismatch")
                self._validate_review_artifacts(e)
                evidence_rows.append(e)
            human = None
            if row[1]:
                hrow = c.execute("SELECT asset_id,payload FROM human_qc_decisions WHERE id=?", (row[1],)).fetchone()
                if not hrow or hrow[0] != asset.asset_id:
                    raise ValueError("human QC lineage mismatch")
                human = HumanDecision.model_validate(json.loads(hrow[1]))
                if human.decision_id != row[1]:
                    raise ValueError("human decision identity mismatch")
            if derive_report(asset, evidence_rows, human) != record:
                raise ValueError("QC report derivation mismatch")
            disposition = derive_disposition(shot.shot_id, asset, record, human)
            if isinstance(disposition, SelectedTake):
                path = Path(asset.uri_or_path)
                if not path.is_file() or file_sha256(path) != asset.sha256:
                    raise ValueError("SelectedTake Asset bytes changed")
                drow = c.execute("SELECT asset_id,report_id,payload FROM selected_takes WHERE id=?",
                                 (disposition.selected_take_id,)).fetchone()
                if not drow or drow[:2] != (asset.asset_id, report_id) or \
                        SelectedTake.model_validate(json.loads(drow[2])) != disposition:
                    raise ValueError("SelectedTake readback mismatch")
            elif isinstance(disposition, dict):
                drow = c.execute("SELECT report_id,payload FROM repair_decisions WHERE id=?",
                                 (disposition["repair_decision_id"],)).fetchone()
                if not drow or drow != (report_id, canonical_json(disposition)):
                    raise ValueError("RepairDecision readback mismatch")
            return record, disposition
        finally:
            c.close()


def technical_evidence(shot, asset: Asset) -> tuple[list[QCEvidence], dict]:
    """Return hard technical facts. Never dispatch or contact a provider."""
    path = Path(asset.uri_or_path)
    rows: list[QCEvidence] = []
    def add(criterion, good, observation, code):
        rows.append(evidence(asset=asset, evaluator_type="ffprobe", evaluator_version=POLICY_VERSION,
                             gate="technical", criterion=criterion, observation=observation,
                             verdict="pass" if good else "fail",
                             failure_code=None if good else code,
                             source_artifacts=[{"path": str(path), "sha256": asset.sha256}]))
    exists = path.is_file() and path.stat().st_size > 0
    add("file_nonempty", exists, "file exists and is non-empty" if exists else "missing or empty file",
        "TECHNICAL_FILE_MISSING")
    if not exists:
        return rows, {}
    digest = file_sha256(path)
    add("asset_sha256", digest == asset.sha256, "actual sha256=" + digest,
        "TECHNICAL_HASH_MISMATCH")
    try:
        metadata = inspect_video(path)
    except (ValueError, RuntimeError) as exc:
        add("valid_video_stream", False, type(exc).__name__ + ": " + str(exc),
            "TECHNICAL_INVALID_VIDEO")
        return rows, {}
    add("valid_video_stream", True, "ffprobe found a valid video stream",
        "TECHNICAL_INVALID_VIDEO")
    add("stored_metadata", all(metadata[k] == getattr(asset, k) for k in ("duration_s", "width", "height")),
        "ffprobe metadata=" + canonical_json(metadata), "TECHNICAL_METADATA_MISMATCH")
    delta = abs(metadata["duration_s"] - shot.duration_target_s)
    add("duration_target", delta <= DURATION_TOLERANCE_S,
        f"target={shot.duration_target_s}s actual={metadata['duration_s']}s tolerance={DURATION_TOLERANCE_S}s",
        "TECHNICAL_DURATION_MISMATCH")
    try:
        completed = subprocess.run(["ffmpeg", "-v", "error", "-xerror", "-i", str(path),
                                    "-map", "0:v:0", "-f", "null", "-"],
                                   capture_output=True, text=True, timeout=120)
        good = completed.returncode == 0
    except (OSError, subprocess.TimeoutExpired):
        good = False
    add("full_video_decode", good, "all video frames decoded" if good else "video decode failed",
        "TECHNICAL_DECODE_FAILED")
    return rows, metadata
