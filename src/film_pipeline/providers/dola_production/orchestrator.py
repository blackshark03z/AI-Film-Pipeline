"""V2-020 — Dola end-to-end production orchestrator (state machine).

Pure-logic core: durable state, restartable/idempotent stages, capability
planning, frozen QC policy, targeted-repair budget, deterministic editorial
ranges, provenance manifest. The live runner injects browser transport;
tests run fully offline.

Durability rules:
  - every transition is saved atomically (tmp file + os.replace) with an
    append-only transition journal next to the state file;
  - stages are no-ops when their output is already recorded (idempotent);
  - a released generation is never re-POSTed: the receipt/creation binding
    is recovered from durable state on restart;
  - crash-point hooks (OrchestratorInterrupt) enable restart proofs without
    wasting provider mutations.
"""
from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from typing import Any, Literal

from pydantic import Field

from ...core import ContractModel
from .capability import DolaCapabilityRegistry
from .fixture_v2_020 import FixtureSpec
from .pool import DolaAccountPoolRouter, SelectionDecision

RunStatus = Literal[
    "RUNNING", "WAITING_PROVIDER", "RECONCILING", "QC", "REPAIRING",
    "ASSEMBLING", "FINISHING", "COMPLETED", "STOPPED_EXTERNAL_GATE",
]
ShotStatus = Literal[
    "PENDING", "PLANNED", "RESERVED", "RELEASED", "RECEIPT_BOUND",
    "CREATION_BOUND", "ACQUIRED", "QC_ACCEPT", "QC_REPAIR_REQUIRED",
    "QC_REJECT", "REPAIRED", "EDITORIAL_LOCKED",
]


def utcnow() -> str:
    return datetime.now(timezone.utc).isoformat()


class OrchestratorInterrupt(Exception):
    """Controlled crash-point exception (restart proofs). Never raised by
    provider behavior."""


class ShotPlan(ContractModel):
    shot_id: str
    model_id: str
    duration_class: int
    expected_credits: int
    eligible: bool
    reason: str


class ShotRecord(ContractModel):
    shot_id: str
    status: ShotStatus = "PENDING"
    role: str = ""
    plan: ShotPlan | None = None
    account_alias: str | None = None
    attempt_id: str | None = None
    request_fingerprint: str | None = None
    conversation_id: str | None = None
    receipt: dict[str, Any] = Field(default_factory=dict)
    creation_ids: list[str] = Field(default_factory=list)
    asset_path: str | None = None
    watermarked_sha256: str | None = None
    clean_sha256: str | None = None
    variant_authority: str | None = None
    qc_technical: dict[str, Any] = Field(default_factory=dict)
    qc_visual: dict[str, Any] = Field(default_factory=dict)
    qc_continuity: dict[str, Any] = Field(default_factory=dict)
    qc_verdict: str | None = None      # ACCEPT / REPAIR_REQUIRED / REJECT
    qc_notes: list[str] = Field(default_factory=list)
    editorial_range: list[int] | None = None  # [start_frame, end_frame)


class ProductionRunState(ContractModel):
    run_id: str
    fixture_id: str
    status: RunStatus = "RUNNING"
    status_detail: str = ""
    fixture: dict[str, Any] = Field(default_factory=dict)
    shots: list[ShotRecord] = Field(default_factory=list)
    repair_used: bool = False
    repair_shot_id: str | None = None
    editorial: dict[str, Any] = Field(default_factory=dict)
    finishing: dict[str, Any] = Field(default_factory=dict)
    master: dict[str, Any] = Field(default_factory=dict)
    pool_log: list[dict[str, Any]] = Field(default_factory=list)
    manifest: dict[str, Any] = Field(default_factory=dict)
    updated_at_utc: str = Field(default_factory=utcnow)


# ---- frozen QC policy (Phase 7) -------------------------------------------
QC_POLICY = {
    "duration_s": (4.2, 6.8),
    "min_height": 700,
    "min_fps": 20.0,
    "max_black_frame_ratio": 0.05,
    "max_freeze_frame_ratio": 0.30,
    "max_mean_luma": 150.0,
    "min_mean_luma": 25.0,
    "max_mean_saturation": 0.45,
    "min_motion_mad": 0.05,
    "max_palette_distance_adjacent": 60.0,
    "required_variant_authorities": [
        "PROVIDER_ISSUED_UNWATERMARKED",
        "PROVIDER_ISSUED_WATERMARKED",
    ],
}


class DolaProductionOrchestrator:
    """Owns ProductionRun durable state; the live runner drives stages."""

    def __init__(self, state_path, fixture: FixtureSpec, *,
                 registry: DolaCapabilityRegistry | None = None,
                 pool: DolaAccountPoolRouter | None = None,
                 mutation_budget: int = 4,
                 crash_point: str | None = None) -> None:
        self.state_path = state_path
        self.fixture = fixture
        self.registry = registry
        self.pool = pool or DolaAccountPoolRouter()
        self.mutation_budget = mutation_budget
        self.mutations_used = 0
        self._crash_point = crash_point
        self.state: ProductionRunState | None = None

    # -- durability -----------------------------------------------------------

    def _crash(self, point: str) -> None:
        if self._crash_point == point:
            self.save()
            raise OrchestratorInterrupt(point)

    def load_or_init(self, run_id: str) -> ProductionRunState:
        if self.state_path.exists():
            self.state = ProductionRunState.model_validate_json(
                self.state_path.read_text(encoding="utf-8"))
            # RESERVED-but-never-released is NOT a spent mutation
            self.mutations_used = sum(
                1 for s in self.state.shots
                if s.attempt_id and s.status in (
                    "RELEASED", "RECEIPT_BOUND", "CREATION_BOUND",
                    "ACQUIRED", "QC_ACCEPT", "QC_REPAIR_REQUIRED",
                    "QC_REJECT", "REPAIRED", "EDITORIAL_LOCKED"))
            # rebuild pool bindings from durable state (restart recovery:
            # a released generation is NEVER re-POSTed)
            for record in self.state.shots:
                if record.attempt_id and record.account_alias:
                    self.pool.ensure_registered(record.account_alias)
                    self.pool.bind_release(
                        attempt_id=record.attempt_id,
                        account_alias=record.account_alias,
                        conversation_id=record.conversation_id,
                        request_identity=record.request_fingerprint)
            return self.state
        self.state = ProductionRunState(
            run_id=run_id, fixture_id=self.fixture.fixture_id,
            fixture=json.loads(self.fixture.model_dump_json()),
            shots=[ShotRecord(shot_id=s.shot_id, role=s.role)
                   for s in self.fixture.shots])
        self.save()
        return self.state

    def save(self) -> None:
        assert self.state is not None
        self.state.updated_at_utc = utcnow()
        tmp = self.state_path.with_suffix(".state.tmp")
        tmp.write_text(self.state.model_dump_json(), encoding="utf-8")
        os.replace(tmp, self.state_path)
        with self.state_path.with_suffix(".transitions.jsonl") \
                .open("a", encoding="utf-8") as handle:
            handle.write(json.dumps({
                "utc": self.state.updated_at_utc,
                "status": self.state.status,
                "shots": {s.shot_id: s.status for s in self.state.shots},
            }) + "\n")

    def shot(self, shot_id: str) -> ShotRecord:
        for record in self.state.shots:
            if record.shot_id == shot_id:
                return record
        raise KeyError(shot_id)

    def set_status(self, status: RunStatus, detail: str = "") -> None:
        self.state.status = status
        self.state.status_detail = detail
        self.save()

    # -- Phase 2: capability-aware planning -----------------------------------

    def plan_shot(self, shot_id: str, *, preferred_model: str =
                  "seedance_v2.0") -> ShotPlan:
        record = self.shot(shot_id)
        if record.plan is not None:
            return record.plan
        spec = next(s for s in self.fixture.shots if s.shot_id == shot_id)
        eligible, reason = self.registry.supports_request(
            model_id=preferred_model,
            duration=str(spec.duration_class))
        model = self.registry.model(preferred_model)
        plan = ShotPlan(
            shot_id=shot_id, model_id=preferred_model,
            duration_class=spec.duration_class,
            expected_credits=model.credit_multiplier or 1 if model else 1,
            eligible=eligible, reason=reason)
        record.plan = plan
        record.status = "PLANNED"
        self.save()
        return plan

    # -- Phase 3: account pool --------------------------------------------------

    def select_account(self, model_id: str) -> SelectionDecision:
        decision = self.pool.select(model_id=model_id)
        self.state.pool_log.append({
            "utc": utcnow(), "decision": decision.model_dump(mode="json")})
        self.save()
        return decision

    def record_release(self, shot_id: str, *, account_alias: str,
                       attempt_id: str, conversation_id: str,
                       request_fingerprint: str) -> None:
        record = self.shot(shot_id)
        record.account_alias = account_alias
        record.attempt_id = attempt_id
        record.conversation_id = conversation_id
        record.request_fingerprint = request_fingerprint
        record.status = "RELEASED"
        self.mutations_used += 1
        self.pool.ensure_registered(account_alias)
        self.pool.bind_release(
            attempt_id=attempt_id, account_alias=account_alias,
            conversation_id=conversation_id,
            request_identity=request_fingerprint)
        self.set_status("WAITING_PROVIDER",
                        f"{shot_id} released on {account_alias}")
        self._crash("after_receipt")

    def record_creation(self, shot_id: str, creation_ids: list[str]) -> None:
        record = self.shot(shot_id)
        record.creation_ids = creation_ids
        record.status = "CREATION_BOUND"
        self.save()
        self._crash("after_creation")

    def record_asset(self, shot_id: str, *, path: str,
                     clean_sha256: str | None,
                     watermarked_sha256: str | None,
                     variant_authority: str) -> None:
        record = self.shot(shot_id)
        record.asset_path = path
        record.clean_sha256 = clean_sha256
        record.watermarked_sha256 = watermarked_sha256
        record.variant_authority = variant_authority
        record.status = "ACQUIRED"
        self.save()
        self._crash("after_acquisition")

    # -- Phase 7: frozen QC ------------------------------------------------------

    def qc_verdict(self, shot_id: str, *, technical: dict,
                   visual: dict | None = None,
                   continuity: dict | None = None) -> str:
        """Frozen-threshold verdict. Deterministic metrics only; the live
        runner attaches agent-review results via `visual`/`continuity`."""
        record = self.shot(shot_id)
        record.qc_technical = technical
        record.qc_visual = visual or {}
        record.qc_continuity = continuity or {}
        failures: list[str] = []
        duration = technical.get("duration_s")
        if not technical.get("decode_ok"):
            failures.append("DECODE_FAILED")
        if duration is None or not (
                QC_POLICY["duration_s"][0] <= duration <=
                QC_POLICY["duration_s"][1]):
            failures.append("DURATION_OUT_OF_RANGE")
        if (technical.get("height") or 0) < QC_POLICY["min_height"]:
            failures.append("RESOLUTION_BELOW_DECLARED")
        if (technical.get("fps") or 0) < QC_POLICY["min_fps"]:
            failures.append("FPS_LOW")
        if (technical.get("black_frame_ratio") or 0) > \
                QC_POLICY["max_black_frame_ratio"]:
            failures.append("BLACK_FRAMES")
        if (technical.get("freeze_frame_ratio") or 0) > \
                QC_POLICY["max_freeze_frame_ratio"]:
            failures.append("FROZEN_FRAMES")
        metrics = {**technical, **(visual or {})}
        if (metrics.get("mean_luma") or 0) > QC_POLICY["max_mean_luma"] or \
                (metrics.get("mean_luma") or 255) < QC_POLICY["min_mean_luma"]:
            failures.append("LUMA_OUT_OF_WORLD_BAND")
        if (metrics.get("mean_saturation") or 0) > \
                QC_POLICY["max_mean_saturation"]:
            failures.append("PALETTE_TOO_SATURATED")
        if (metrics.get("motion_mad") or 0) < QC_POLICY["min_motion_mad"]:
            failures.append("NO_MOTION")
        if visual:
            failures.extend(visual.get("hard_failures") or [])
        if continuity:
            if (continuity.get("palette_distance") or 0) > \
                    QC_POLICY["max_palette_distance_adjacent"]:
                failures.append("CONTINUITY_PALETTE_BREAK")
            failures.extend(continuity.get("hard_failures") or [])
        record.qc_notes = failures
        hard = visual and visual.get("verdict") == "REJECT" or \
            continuity and continuity.get("verdict") == "REJECT"
        if hard or "DECODE_FAILED" in failures or \
                "RESOLUTION_BELOW_DECLARED" in failures or \
                "BLACK_FRAMES" in failures or "FROZEN_FRAMES" in failures:
            record.qc_verdict = "REJECT"
        elif failures:
            record.qc_verdict = "REPAIR_REQUIRED"
        else:
            record.qc_verdict = "ACCEPT"
        record.status = {
            "ACCEPT": "QC_ACCEPT", "REPAIR_REQUIRED": "QC_REPAIR_REQUIRED",
            "REJECT": "QC_REJECT"}[record.qc_verdict]
        self.set_status("QC", f"{shot_id} verdict {record.qc_verdict}")
        return record.qc_verdict

    # -- Phase 8: targeted repair budget -----------------------------------------

    def request_repair(self, shot_id: str) -> bool:
        """ONE repair slot for exactly one failing shot."""
        record = self.shot(shot_id)
        if record.qc_verdict != "REPAIR_REQUIRED":
            return False
        if self.state.repair_used or \
                self.mutations_used >= self.mutation_budget:
            return False
        self.state.repair_used = True
        self.state.repair_shot_id = shot_id
        record.status = "REPAIRED"  # reserve consumed on next release
        self.set_status("REPAIRING", shot_id)
        return True

    def repair_eligible(self) -> str | None:
        if self.state.repair_used:
            return None
        failing = [s.shot_id for s in self.state.shots
                   if s.qc_verdict == "REPAIR_REQUIRED"]
        if len(failing) == 1 and \
                self.mutations_used < self.mutation_budget:
            return failing[0]
        return None

    # -- Phase 9: editorial --------------------------------------------------------

    def editorial_ranges(self, *, fps: float = 24.0,
                         trims: dict[str, int] | None = None) -> dict:
        """Deterministic ranges: whole assets minus optional bounded tail
        trims (frames) per shot. Trim-first policy: no regeneration for a
        cut problem."""
        trims = trims or {}
        ranges = {}
        for record in self.state.shots:
            frames = int(round((record.qc_technical.get("duration_s")
                                or 5.0) * fps))
            trim = int(trims.get(record.shot_id, 0))
            ranges[record.shot_id] = [0, max(frames - trim, 1)]
            record.editorial_range = ranges[record.shot_id]
        self.state.editorial = {
            "ranges": ranges, "fps": fps,
            "assembled_at_utc": utcnow(),
            "trim_policy": "bounded tail trims only; regeneration "
                           "never for a cut problem"}
        self.set_status("ASSEMBLING", "ranges locked")
        return self.state.editorial

    def record_editorial_proof(self, *, path: str, sha256: str,
                               frame_count: int, junctions: dict) -> None:
        self.state.editorial.update({
            "sequence_proof_path": path, "sequence_proof_sha256": sha256,
            "frame_count": frame_count, "junctions": junctions})

    def record_finishing(self, *, loudness_lufs: float | None,
                         true_peak_dbtp: float | None, av_sync: str,
                         path: str, sha256: str) -> None:
        self.state.finishing = {
            "loudness_lufs": loudness_lufs,
            "true_peak_dbtp": true_peak_dbtp,
            "av_sync": av_sync, "finish_master_path": path,
            "finish_master_sha256": sha256}
        self.set_status("FINISHING", "finish master recorded")

    def record_master(self, *, path: str, sha256: str,
                      watermark_status: str) -> None:
        self.state.master = {"distribution_master_path": path,
                             "distribution_master_sha256": sha256,
                             "watermark_status": watermark_status}

    # -- Phase 14: manifest -----------------------------------------------------------

    def manifest(self, *, run_dir: str) -> dict:
        state = self.state
        doc = {
            "version": "v2-020-manifest-v1",
            "run_id": state.run_id,
            "fixture_id": state.fixture_id,
            "generated_at_utc": utcnow(),
            "chain": [],
            "repair": {"used": state.repair_used,
                       "shot_id": state.repair_shot_id},
            "status": state.status,
        }
        for record in state.shots:
            spec = next(s for s in self.fixture.shots
                        if s.shot_id == record.shot_id)
            doc["chain"].append({
                "shot_id": record.shot_id,
                "role": spec.role,
                "prompt_sha256": __import__("hashlib").sha256(
                    spec.prompt.encode()).hexdigest(),
                "attempt_id": record.attempt_id,
                "account_alias": record.account_alias,
                "conversation_id": record.conversation_id,
                "creation_ids": record.creation_ids,
                "asset_path": record.asset_path,
                "clean_sha256": record.clean_sha256,
                "watermarked_sha256": record.watermarked_sha256,
                "variant_authority": record.variant_authority,
                "qc_verdict": record.qc_verdict,
                "editorial_range": record.editorial_range,
                "status": record.status,
            })
        doc["editorial"] = {k: v for k, v in state.editorial.items()}
        doc["finishing"] = state.finishing
        doc["distribution_master"] = state.master
        doc["run_dir"] = run_dir
        state.manifest = doc
        self.save()
        return doc
