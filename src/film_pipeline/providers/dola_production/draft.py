"""V2-019 Phase I — provider-neutral draft->final domain types (DORMANT).

Dola has NO true draft->final lineage (V2-019 Phase B/F: NOT_OBSERVED).
These types stay dormant here for providers that support the semantics
(e.g. the BytePlus draft_task contract). Finalization MUST reference an
existing DraftAttempt — a same-prompt regeneration is NOT a finalization.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Literal

from pydantic import Field

from ...core import ContractModel

# Registry-driven: flipped only after a provider delivers a draft identity
# AND a finalization operation referencing it (Phase F rule).
DOLA_DRAFT_FINAL_SUPPORTED = False

DraftStatus = Literal["PENDING", "RUNNING", "READY", "FAILED", "EXPIRED"]


def _utcnow() -> str:
    return datetime.now(timezone.utc).isoformat()


class DraftAttempt(ContractModel):
    draft_attempt_id: str
    provider_id: str
    provider_draft_id: str | None = None
    account_alias: str | None = None
    request_spec_sha256: str | None = None
    status: DraftStatus = "PENDING"
    created_at_utc: str = Field(default_factory=_utcnow)
    draft_asset: dict[str, Any] = Field(default_factory=dict)
    qc_report: dict[str, Any] = Field(default_factory=dict)


class DraftSelection(ContractModel):
    selection_id: str
    draft_attempt_id: str
    selected_at_utc: str = Field(default_factory=_utcnow)
    reason: str = ""


class FinalizationAttempt(ContractModel):
    finalization_attempt_id: str
    provider_id: str
    draft_attempt_id: str  # REQUIRED lineage: the exact draft being finalized
    provider_draft_id: str | None = None
    account_alias: str | None = None
    status: DraftStatus = "PENDING"
    created_at_utc: str = Field(default_factory=_utcnow)
    final_asset: dict[str, Any] = Field(default_factory=dict)

    def validate_lineage(self, drafts: dict[str, DraftAttempt]) -> None:
        if self.draft_attempt_id not in drafts:
            raise ValueError(
                "FinalizationAttempt references unknown DraftAttempt: "
                + self.draft_attempt_id)
        draft = drafts[self.draft_attempt_id]
        if draft.provider_id != self.provider_id:
            raise ValueError("cross-provider finalization is not a "
                             "same-take finalization")
