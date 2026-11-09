"""Money ledger with a unit per provider (docs/production/PROVIDER_INDEPENDENCE.md section 3 item 5).

Spent per unit (Flow ``credits``, ``USD``, ``VND``) = registered takes + intent receipts that were submitted but never
became a take and whose normalized result the route's registry entry charges (``charged_on``). A receipt is matched to
its take by the take's output file, and for API routes also by ``provider_job_id``. Records from before provider
adapters carry no provider or unit: they are Flow credits. The film's cap applies per unit (``Budget.cap_for``).
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

from film_pipeline.providers.capability import charging_entry


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


def money_ledger(log: Any, sent: dict[str, dict[str, Any]]) -> dict[str, dict[str, Any]]:
    """unit -> {logged, unresolved {receipt id: amount}, not_submitted [ids], not_charged [ids], spent}.
    ``credits`` is always present (every film has a Flow credit line, possibly 0)."""
    out: dict[str, dict[str, Any]] = {}

    def line(unit: str) -> dict[str, Any]:
        return out.setdefault(unit, {"logged": 0.0, "unresolved": {}, "not_submitted": [], "not_charged": [],
                                     "spent": 0.0})

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
    for led in out.values():
        led["not_submitted"].sort()
        led["not_charged"].sort()
        led["spent"] = led["logged"] + sum(led["unresolved"].values())
    return out


def credit_ledger(log: Any, sent: dict[str, dict[str, Any]]) -> dict[str, Any]:
    """Flow credits used = registered takes + receipts that were submitted but never became a take (UNBOUND, AMBIGUOUS,
    TIMEOUT, PENDING ...: the clip may exist in Flow and was probably charged).
    A receipt is matched to its take by the take's output file (a take's id can differ from its receipt's id: the
    receipt numbers every send, the take log numbers registered takes). Pre-submit failures cost nothing.
    The legacy view of ``money_ledger``'s ``credits`` line: pre-submit receipts of every unit are listed."""
    full = money_ledger(log, sent)
    credits = full["credits"]
    pre_submit = sorted(tid for led in full.values() for tid in led["not_submitted"])
    return {"logged": credits["logged"], "unresolved": credits["unresolved"], "pre_submit": pre_submit,
            "spent": credits["spent"]}
