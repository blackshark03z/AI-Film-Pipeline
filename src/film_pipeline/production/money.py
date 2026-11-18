"""Money ledger with a unit per provider (docs/production/PROVIDER_INDEPENDENCE.md section 3 item 5).

Spent per unit (Flow ``credits``, ``USD``, ``VND``) = registered takes + intent receipts that were submitted but never
became a take and whose normalized result the route's registry entry charges (``charged_on``). A receipt is matched to
its take by the take's output file, and for API routes also by ``provider_job_id``. Records from before provider
adapters carry no provider or unit: they are Flow credits. The film's cap applies per unit (``Budget.cap_for``).
"""
from __future__ import annotations

import math
import uuid
from collections.abc import Iterable
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Literal

from pydantic import Field, field_validator, model_validator

from film_pipeline.core import ContractModel
from film_pipeline.production.runtime import atomic_json
from film_pipeline.production.takes import takes_dir
from film_pipeline.providers.capability import charging_entry


class LedgerAdjustment(ContractModel):
    adjustment_id: str = Field(min_length=1)
    unit: str = Field(default="credits", min_length=1)
    delta: float
    reason: str = Field(min_length=1)
    evidence: str = Field(min_length=1)
    by: str = Field(min_length=1)
    at: str = Field(min_length=1)

    @field_validator("delta")
    @classmethod
    def _finite_delta(cls, value: float) -> float:
        if not math.isfinite(float(value)):
            raise ValueError("adjustment delta must be finite")
        return float(value)


class BalanceCheckpoint(ContractModel):
    scene_id: str = Field(min_length=1)
    boundary: Literal["start", "end"]
    account: str = Field(min_length=1)
    observed_balance: float = Field(ge=0)
    ledger_spent: float
    at: str = Field(min_length=1)
    note: str = ""

    @field_validator("observed_balance", "ledger_spent")
    @classmethod
    def _finite_amounts(cls, value: float) -> float:
        if not math.isfinite(float(value)):
            raise ValueError("checkpoint amount must be finite")
        return float(value)


class AdjustmentLog(ContractModel):
    adjustments: list[LedgerAdjustment] = Field(default_factory=list)
    checkpoints: list[BalanceCheckpoint] = Field(default_factory=list)

    @model_validator(mode="after")
    def _unique_ids(self) -> "AdjustmentLog":
        ids = [a.adjustment_id for a in self.adjustments]
        if len(ids) != len(set(ids)):
            raise ValueError("duplicate adjustment_id in adjustments log")
        return self


def adjustments_path(root: Path) -> Path:
    return takes_dir(Path(root)) / "adjustments.json"


def load_adjustments(root: Path) -> AdjustmentLog:
    path = adjustments_path(Path(root))
    if not path.is_file():
        return AdjustmentLog()
    return AdjustmentLog.model_validate_json(path.read_text(encoding="utf-8"))


def save_adjustments(root: Path, log: AdjustmentLog) -> Path:
    path = adjustments_path(Path(root))
    atomic_json(path, log.model_dump(mode="json"))
    return path


def record_adjustment(
    root: Path,
    delta: float,
    reason: str,
    evidence: str,
    by: str,
    *,
    unit: str = "credits",
    adjustment_id: str | None = None,
) -> LedgerAdjustment:
    log = load_adjustments(root)
    norm_delta = float(delta)
    if not math.isfinite(norm_delta):
        raise ValueError("adjustment delta must be finite")
    norm_reason, norm_evidence, norm_by = reason.strip(), evidence.strip(), by.strip()
    if adjustment_id is not None:
        existing = next((a for a in log.adjustments if a.adjustment_id == adjustment_id), None)
        if existing is not None:
            if (existing.unit, existing.delta, existing.reason, existing.evidence, existing.by) == (
                unit, norm_delta, norm_reason, norm_evidence, norm_by
            ):
                return existing
            raise ValueError(f"conflicting adjustment_id {adjustment_id!r}")
    adj_id = adjustment_id or f"ADJ-{len(log.adjustments) + 1:03d}-{uuid.uuid4().hex[:6]}"
    entry = LedgerAdjustment(
        adjustment_id=adj_id,
        unit=unit,
        delta=norm_delta,
        reason=norm_reason,
        evidence=norm_evidence,
        by=norm_by,
        at=datetime.now(timezone.utc).isoformat(timespec="seconds"),
    )
    log.adjustments.append(entry)
    save_adjustments(root, log)
    return entry


def record_checkpoint(
    root: Path,
    scene_id: str,
    boundary: Literal["start", "end"],
    account: str,
    observed_balance: float,
    ledger_spent: float,
    *,
    note: str = "",
) -> BalanceCheckpoint:
    log = load_adjustments(root)
    cp = BalanceCheckpoint(
        scene_id=scene_id.strip(),
        boundary=boundary,
        account=account.strip(),
        observed_balance=float(observed_balance),
        ledger_spent=float(ledger_spent),
        at=datetime.now(timezone.utc).isoformat(timespec="seconds"),
        note=note.strip(),
    )
    log.checkpoints.append(cp)
    save_adjustments(root, log)
    return cp


def receipt_unit(receipt: dict[str, Any]) -> str:
    return str(receipt.get("cost_unit") or "credits")


def receipt_amount(receipt: dict[str, Any]) -> float:
    """What a receipt reserves in its own unit. Flow receipts keep the legacy ``expected_credits`` field."""
    if receipt_unit(receipt) == "credits":
        return float(receipt.get("expected_credits") or 0.0)
    return float(receipt.get("expected_cost") or 0.0)


def receipt_result(receipt: dict[str, Any]) -> str:
    """The normalized result of a receipt (its raw ``result`` read through its route's registry entry)."""
    entry = charging_entry(receipt.get("provider"), receipt.get("provider_model") or None)
    return entry.normalize(receipt.get("result"))


def receipt_charged(receipt: dict[str, Any]) -> bool:
    entry = charging_entry(receipt.get("provider"), receipt.get("provider_model") or None)
    return entry.charged(entry.normalize(receipt.get("result")))


def _registered(log: Any) -> tuple[set[str], set[tuple[str, str]]]:
    files = {Path(t.output_file).stem for t in log.takes}
    jobs = {(getattr(t, "provider", "flow"), t.provider_job_id) for t in log.takes if getattr(t, "provider_job_id", "")}
    return files, jobs


def _is_registered(tid: str, receipt: dict[str, Any], files: set[str], jobs: set[tuple[str, str]]) -> bool:
    job = str(receipt.get("provider_job_id") or "")
    return tid in files or bool(job and (str(receipt.get("provider") or "flow"), job) in jobs)


def unresolved_sends(log: Any, sent: dict[str, dict[str, Any]]) -> dict[str, dict[str, Any]]:
    """Unknown outcomes and unregistered successes must be reconciled before another send."""
    files, jobs = _registered(log)
    return {tid: r for tid, r in sent.items()
            if receipt_result(r) in {"AMBIGUOUS", "PASSED"} and not _is_registered(tid, r, files, jobs)}


def money_ledger(
    log: Any,
    sent: dict[str, dict[str, Any]],
    adjustments: Iterable[Any] = (),
) -> dict[str, dict[str, Any]]:
    """unit -> {logged, unresolved {receipt id: amount}, not_submitted [ids], not_charged [ids], adjustments, spent}.
    ``credits`` is always present (every film has a Flow credit line, possibly 0)."""
    out: dict[str, dict[str, Any]] = {}

    def line(unit: str) -> dict[str, Any]:
        return out.setdefault(
            unit,
            {"logged": 0.0, "unresolved": {}, "not_submitted": [], "not_charged": [], "adjustments": 0.0, "spent": 0.0},
        )

    line("credits")
    for t in log.takes:
        cost = t.cost if hasattr(t, "cost") else {"amount": t.credits, "unit": "credits"}
        line(cost["unit"])["logged"] += float(cost["amount"])
    files, jobs = _registered(log)
    for tid, r in sent.items():
        if _is_registered(tid, r, files, jobs):
            continue
        led = line(receipt_unit(r))
        result = receipt_result(r)
        if result == "NOT_SUBMITTED":
            led["not_submitted"].append(tid)
        elif receipt_charged(r):
            led["unresolved"][tid] = receipt_amount(r)
        else:
            led["not_charged"].append(tid)
    for adj in adjustments:
        unit = str(getattr(adj, "unit", None) or (adj.get("unit") if isinstance(adj, dict) else "credits") or "credits")
        delta = float(getattr(adj, "delta", adj["delta"] if isinstance(adj, dict) else 0.0))
        line(unit)["adjustments"] += delta
    for led in out.values():
        led["not_submitted"].sort()
        led["not_charged"].sort()
        led["adjustments"] = round(led["adjustments"], 4)
        led["spent"] = round(led["logged"] + sum(led["unresolved"].values()) + led["adjustments"], 4)
    return out


def credit_ledger(
    log: Any,
    sent: dict[str, dict[str, Any]],
    adjustments: Iterable[Any] = (),
) -> dict[str, Any]:
    """Flow credits used = registered takes + receipts that were submitted but never became a take + adjustments.
    Preserves legacy 4-key dict when no adjustments are supplied."""
    adj_list = list(adjustments)
    full = money_ledger(log, sent, adj_list)
    credits = full["credits"]
    pre_submit = sorted(tid for led in full.values() for tid in led["not_submitted"])
    out = {"logged": credits["logged"], "unresolved": credits["unresolved"], "pre_submit": pre_submit,
           "spent": credits["spent"]}
    if adj_list or credits["adjustments"]:
        out["adjustments"] = credits["adjustments"]
    return out
