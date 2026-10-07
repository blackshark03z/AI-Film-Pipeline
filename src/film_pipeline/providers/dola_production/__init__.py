"""V2-019 — Dola production layer.

Productionized Dola route truth (capability registry, generation-time
observability, clean-asset variant resolution, account pool routing,
dormant draft->final domain types, cost/quality planning).

Read-only by construction: nothing here dispatches a generation. Wire
truth consolidated in
projects/quality_v2_019_dola_productionization/V2_019_PHASEA_*.json.
"""
from .capability import (
    DolaCapabilityRegistry,
    DolaModelCatalog,
    DolaModelEntry,
    GateClass,
    merge_registry,
    parse_composer_template,
    parse_skill_pack,
)
from .draft import (
    DOLA_DRAFT_FINAL_SUPPORTED,
    DraftAttempt,
    DraftSelection,
    FinalizationAttempt,
)
from .hardening import (
    clear_stale_profile_locks,
    extract_poll_messages,
    safe_close,
    stale_profile_locks,
)
from .fixture_v2_020 import FIXTURE, FixtureSpec, ShotSpec
from .orchestrator import (
    DolaProductionOrchestrator,
    OrchestratorInterrupt,
    ProductionRunState,
    QC_POLICY,
    ShotPlan,
    ShotRecord,
)
from .observability import (
    CreationObserved,
    CreditStatementObserved,
    DraftIdentityObserved,
    FinalizationObserved,
    GenerationReceipt,
    GenerationReleased,
    ProviderEvent,
    VariantObserved,
    deep_json_strings,
    normalize_poll_payload,
    redact_url,
)
from .pool import (
    DolaAccountPoolRouter,
    DolaAccountState,
    PoolResourceState,
    SessionState,
)
from .routing import (
    DolaPlanRouter,
    GenerationPlan,
    PlanMode,
)
from .variants import (
    DolaAssetVariantResolver,
    VariantAuthority,
    VideoVariant,
    VariantSelection,
)

__all__ = [
    "DolaCapabilityRegistry",
    "DolaProductionOrchestrator",
    "OrchestratorInterrupt",
    "ProductionRunState",
    "QC_POLICY",
    "ShotPlan",
    "ShotRecord",
    "FIXTURE",
    "FixtureSpec",
    "ShotSpec",
    "DolaModelCatalog",
    "DolaModelEntry",
    "GateClass",
    "merge_registry",
    "parse_composer_template",
    "parse_skill_pack",
    "DOLA_DRAFT_FINAL_SUPPORTED",
    "DraftAttempt",
    "DraftSelection",
    "FinalizationAttempt",
    "CreationObserved",
    "CreditStatementObserved",
    "DraftIdentityObserved",
    "FinalizationObserved",
    "GenerationReceipt",
    "GenerationReleased",
    "ProviderEvent",
    "VariantObserved",
    "deep_json_strings",
    "normalize_poll_payload",
    "redact_url",
    "clear_stale_profile_locks",
    "extract_poll_messages",
    "safe_close",
    "stale_profile_locks",
    "DolaAccountPoolRouter",
    "DolaAccountState",
    "PoolResourceState",
    "SessionState",
    "DolaPlanRouter",
    "GenerationPlan",
    "PlanMode",
    "DolaAssetVariantResolver",
    "VariantAuthority",
    "VideoVariant",
    "VariantSelection",
]
