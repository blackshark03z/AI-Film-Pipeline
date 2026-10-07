"""V2-019 Phase E — DolaAccountPoolRouter.

Multi-account routing for the Owner-authorized Dola pool.

Rules (work package + standing governance):
  - Account state NEVER carries secret material. profile_binding is a path
    reference; session cookies stay in DPAPI stores / persistent profiles.
  - Selection is deterministic: session READY -> entitlement -> known
    credit -> no active attempt -> not cooling down -> LRU.
  - Rotation is legal ONLY while dispatch_state = NOT_RELEASED. After
    NETWORK_RELEASE_OBSERVED the (attempt, account, profile, conversation,
    request identity) binding is IMMUTABLE.
  - Resource policy: CURRENT_ACCOUNT_INSUFFICIENT / POOL_ENTRY_UNAVAILABLE
    / KNOWN_POOL_INSUFFICIENT. OWNER_RESOURCE_EXHAUSTED is never set by
    this module — only the Owner can declare resources exhausted.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Literal

from pydantic import Field

from ...core import ContractModel

SessionState = Literal[
    "UNKNOWN", "LOGIN_REQUIRED", "SESSION_VALID", "SESSION_EXPIRED",
    "NO_CREDIT", "READY", "QUARANTINED",
]

PoolResourceState = Literal[
    "NONE", "CURRENT_ACCOUNT_INSUFFICIENT", "POOL_ENTRY_UNAVAILABLE",
    "KNOWN_POOL_INSUFFICIENT",
]

_OWNER_RESOURCE_EXHAUSTED = "OWNER_RESOURCE_EXHAUSTED"  # never produced here


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class DolaAccountState(ContractModel):
    account_alias: str
    profile_binding: str
    session_state: SessionState = "UNKNOWN"
    subscription_state: Literal["SUBSCRIBER", "NON_SUBSCRIBER", "UNKNOWN"] = \
        "UNKNOWN"
    model_entitlements: dict[str, bool] = Field(default_factory=dict)
    known_credit_state: int | None = None
    credit_observed_at: str | None = None
    last_success_at: str | None = None
    last_failure_at: str | None = None
    last_failure_code: str | None = None
    cooldown_until: str | None = None
    active_attempt_id: str | None = None
    last_used_at: str | None = None
    health_notes: list[str] = Field(default_factory=list)

    def tracked_view(self) -> dict:
        """Tracked-evidence view (no secrets exist here by construction,
        but keep the projection explicit for evidence writers)."""
        return self.model_dump(mode="json", exclude={"health_notes"})


class ReleaseBinding(ContractModel):
    attempt_id: str
    account_alias: str
    profile_binding: str
    conversation_id: str | None = None
    request_identity: str | None = None
    bound_at_utc: str


class SelectionDecision(ContractModel):
    selected_alias: str | None
    reason: str
    considered: list[str] = Field(default_factory=list)
    resource_state: PoolResourceState = "NONE"


class DolaAccountPoolRouter:
    def __init__(self, *, required_credit: int = 1) -> None:
        self._accounts: dict[str, DolaAccountState] = {}
        self._bindings: dict[str, ReleaseBinding] = {}
        self._required_credit = required_credit

    # -- pool management -----------------------------------------------------

    def register(self, state: DolaAccountState) -> None:
        if state.account_alias in self._accounts:
            raise ValueError("duplicate account alias: "
                             + state.account_alias)
        self._accounts[state.account_alias] = state

    def ensure_registered(self, alias: str, *,
                          profile_binding: str | None = None) -> DolaAccountState:
        """Idempotent registration used when durable state references an
        account that this router instance has not yet probed."""
        existing = self._accounts.get(alias)
        if existing is not None:
            return existing
        state = DolaAccountState(
            account_alias=alias,
            profile_binding=profile_binding or f"pool/{alias}")
        self._accounts[alias] = state
        return state

    def account(self, alias: str) -> DolaAccountState:
        return self._accounts[alias]

    def accounts(self) -> list[DolaAccountState]:
        return list(self._accounts.values())

    # -- pre-dispatch routing ------------------------------------------------

    def select(self, *, model_id: str | None = None,
               now: datetime | None = None) -> SelectionDecision:
        now = now or utcnow()
        considered: list[str] = []
        eligible: list[DolaAccountState] = []
        for state in self._accounts.values():
            considered.append(state.account_alias)
            # credit-unobservable SESSION_VALID stays eligible: an unknown
            # quota is not an insufficient quota
            if state.session_state not in ("READY", "SESSION_VALID"):
                continue
            if model_id is not None:
                entitled = state.model_entitlements.get(model_id)
                if entitled is False:
                    continue
            if state.known_credit_state is not None and \
                    state.known_credit_state < self._required_credit:
                continue
            if state.active_attempt_id is not None:
                continue
            if state.cooldown_until:
                try:
                    until = datetime.fromisoformat(state.cooldown_until)
                except ValueError:
                    until = None
                if until is not None and until > now:
                    continue
            eligible.append(state)
        if not eligible:
            return SelectionDecision(
                selected_alias=None, reason="no eligible account",
                considered=considered,
                resource_state=self._resource_state())
        eligible.sort(key=lambda s: (
            -(s.known_credit_state if s.known_credit_state is not None
              else -1),
            s.last_used_at or "", s.account_alias))
        chosen = eligible[0]
        return SelectionDecision(
            selected_alias=chosen.account_alias,
            reason="READY + entitled + credit + idle + LRU",
            considered=considered, resource_state="NONE")

    def _resource_state(self) -> PoolResourceState:
        if not self._accounts:
            return "POOL_ENTRY_UNAVAILABLE"
        states = [s.session_state for s in self._accounts.values()]
        unusable = ("LOGIN_REQUIRED", "SESSION_EXPIRED", "QUARANTINED",
                    "UNKNOWN")
        if all(s == "NO_CREDIT" for s in states):
            return "KNOWN_POOL_INSUFFICIENT"
        if any(s == "NO_CREDIT" for s in states) and \
                all(s == "NO_CREDIT" or s in unusable for s in states):
            # the credit-bearing entries are known-insufficient and the
            # rest cannot be used at all
            return "KNOWN_POOL_INSUFFICIENT"
        if all(s in unusable for s in states):
            return "POOL_ENTRY_UNAVAILABLE"
        return "CURRENT_ACCOUNT_INSUFFICIENT"

    # -- observation ingestion ------------------------------------------------

    def record_session(self, alias: str, session_state: SessionState, *,
                       credit_remaining: int | None = None,
                       subscription_state: Literal[
                           "SUBSCRIBER", "NON_SUBSCRIBER", "UNKNOWN"]
                       | None = None,
                       model_entitlements: dict[str, bool] | None = None,
                       note: str | None = None) -> None:
        state = self._accounts[alias]
        state.session_state = session_state
        if credit_remaining is not None:
            state.known_credit_state = credit_remaining
            state.credit_observed_at = utcnow().isoformat()
            if session_state == "SESSION_VALID" and \
                    credit_remaining >= self._required_credit:
                state.session_state = "READY"
            elif session_state == "SESSION_VALID" and credit_remaining < \
                    self._required_credit:
                state.session_state = "NO_CREDIT"
        if subscription_state is not None:
            state.subscription_state = subscription_state
        if model_entitlements:
            state.model_entitlements.update(model_entitlements)
        if note:
            state.health_notes.append(note)
        state.last_used_at = utcnow().isoformat()

    def record_failure(self, alias: str, code: str, *,
                       cooldown_seconds: int = 0) -> None:
        state = self._accounts[alias]
        state.last_failure_at = utcnow().isoformat()
        state.last_failure_code = code
        if cooldown_seconds > 0:
            from datetime import timedelta

            state.cooldown_until = (utcnow() + timedelta(
                seconds=cooldown_seconds)).isoformat()
        state.last_used_at = utcnow().isoformat()

    def record_success(self, alias: str) -> None:
        state = self._accounts[alias]
        state.last_success_at = utcnow().isoformat()
        state.cooldown_until = None
        state.last_used_at = utcnow().isoformat()

    # -- release binding (post-release immutability) ---------------------------

    def bind_release(self, *, attempt_id: str, account_alias: str,
                     conversation_id: str | None = None,
                     request_identity: str | None = None,
                     bound_at_utc: str | None = None) -> ReleaseBinding:
        if attempt_id in self._bindings:
            existing = self._bindings[attempt_id]
            if existing.account_alias != account_alias:
                raise ValueError("attempt already bound to another account")
            return existing
        state = self._accounts[account_alias]
        binding = ReleaseBinding(
            attempt_id=attempt_id, account_alias=account_alias,
            profile_binding=state.profile_binding,
            conversation_id=conversation_id,
            request_identity=request_identity,
            bound_at_utc=bound_at_utc or utcnow().isoformat())
        self._bindings[attempt_id] = binding
        state.active_attempt_id = attempt_id
        return binding

    def binding(self, attempt_id: str) -> ReleaseBinding | None:
        return self._bindings.get(attempt_id)

    def rotate_allowed(self, attempt_id: str) -> bool:
        """Rotation after release is NEVER allowed (one-way latch)."""
        return attempt_id not in self._bindings

    def complete_attempt(self, attempt_id: str, *, success: bool) -> None:
        binding = self._bindings.get(attempt_id)
        if binding is None:
            raise ValueError("unknown attempt: " + attempt_id)
        state = self._accounts[binding.account_alias]
        state.active_attempt_id = None
        if success:
            self.record_success(binding.account_alias)
        else:
            self.record_failure(binding.account_alias, "ATTEMPT_FAILED")

    # -- resource policy -------------------------------------------------------

    def resource_state_for(self, alias: str) -> PoolResourceState:
        state = self._accounts.get(alias)
        if state is None:
            return "POOL_ENTRY_UNAVAILABLE"
        if state.session_state == "NO_CREDIT":
            other_ready = [
                s for s in self._accounts.values()
                if s.account_alias != alias and s.session_state == "READY"]
            if other_ready:
                return "CURRENT_ACCOUNT_INSUFFICIENT"
            return self._resource_state()
        return "NONE"

    @staticmethod
    def forbidden_state() -> str:
        """Documentation-by-code: this value is NEVER set by the router."""
        return _OWNER_RESOURCE_EXHAUSTED
