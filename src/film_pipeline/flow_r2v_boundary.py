"""Reusable Flow reference-to-video (R2V) provider boundary.

One parameterized lifecycle for any reference-conditioned Flow shot:

verified Film reference
→ immutable provider-reference attestation (mandatory, fail-closed)
→ durable single-dispatch ProviderJob reservation
→ provider-native UI input preparation (UI is transport only)
→ exactly one authorized mutation opportunity
→ external effect UNKNOWN until backend proof
→ reconciliation-only recovery (a consumed dispatch is never re-authorized)
→ unique backend output attribution
→ exact media acquisition
→ downstream QC handoff.

This module composes the proven pieces — ``flow_reference_binding``
attestation, ``store.reserve_dispatch`` once-only semantics, native-UI
request qualification in ``flow_canonical_ui``, backend catalog ownership in
``flow_rpc_contract`` and exact ID/resource/bytes binding in ``flow_media`` —
so an ordinary shot needs no slice-specific orchestration component.

Provider volatility stays outside: no hypothesis about why direct RPC writes
fail while native-UI writes succeed is encoded here. Locale labels, RPC
quirks and UI selectors stay in the UI profile and never enter Film Core.
Slice Owner authority (grants, historical custody) remains in Slice-0011
orchestration; this module carries only generic behavior.
"""
from __future__ import annotations

from dataclasses import dataclass

from .providers import flow_rpc_contract as contract
from .providers.flow_canonical_ui import (
    DEFAULT_NATIVE_UI,
    NativeUiProfile,
    OneGenerateGuard,
    validate_native_request,
)
from .providers.flow_media import (
    BoundMedia,
    MediaResource,
    bind_media_bytes,
    parse_media_resource,
)
from .providers.flow_reference_binding import verify_attestation
from .providers.flow_reference_upload import OwnerAmbiguityGate

MUTATION_AVAILABLE = 'MUTATION_AVAILABLE'
RECONCILE_ONLY = 'RECONCILE_ONLY'

# The qualified offline envelope. Anything outside it fails closed rather
# than drifting into an unqualified mutation.
QUALIFIED_DURATION_S = 8
QUALIFIED_RESOLUTION = '720p'
QUALIFIED_ASPECT_RATIO = '16:9'


@dataclass(frozen=True)
class MutationIntent:
    """Fail-closed per-shot mutation parameters. No slice identity required.

    The output count is fixed at one by construction: exactly one mutation
    opportunity exists for one ProviderJob.
    """

    project_id: str
    account_id: str
    reference_media_id: str
    model: str = contract.MODEL_VEO_3_1_LITE
    duration_s: int = QUALIFIED_DURATION_S
    resolution: str = QUALIFIED_RESOLUTION
    aspect_ratio: str = QUALIFIED_ASPECT_RATIO
    output_count: int = 1
    contract_version: str = contract.CONTRACT_VERSION_2026_10_01
    ui_profile: NativeUiProfile = DEFAULT_NATIVE_UI

    def __post_init__(self):
        contract._uuid(self.project_id, 'PROJECT_ID_INVALID')
        contract._uuid(self.reference_media_id, 'REFERENCE_ID_INVALID')
        if not isinstance(self.account_id, str) or not self.account_id or ':' in self.account_id:
            raise OwnerAmbiguityGate('MUTATION_INTENT_ACCOUNT_UNQUALIFIED')
        if self.model not in contract.QUALIFIED_VEO_3_1_MODELS:
            raise OwnerAmbiguityGate('MUTATION_INTENT_MODEL_UNQUALIFIED')
        if (self.duration_s != QUALIFIED_DURATION_S or self.resolution != QUALIFIED_RESOLUTION
                or self.aspect_ratio != QUALIFIED_ASPECT_RATIO or self.output_count != 1):
            raise OwnerAmbiguityGate('MUTATION_INTENT_SETTINGS_UNQUALIFIED')
        if self.contract_version != contract.CONTRACT_VERSION_2026_10_01:
            raise OwnerAmbiguityGate('MUTATION_INTENT_CONTRACT_UNQUALIFIED')
        if not isinstance(self.ui_profile, NativeUiProfile):
            raise OwnerAmbiguityGate('MUTATION_INTENT_UI_PROFILE_UNQUALIFIED')


@dataclass(frozen=True)
class MutationState:
    """Post-effect mutation availability. Consumption is irreversible."""

    state: str
    dispatch_count: int


def mutation_state(job) -> MutationState:
    if job.dispatch_count == 0:
        return MutationState(MUTATION_AVAILABLE, 0)
    return MutationState(RECONCILE_ONLY, 1)


class FlowR2VBoundary:
    """Composition point for the proven Flow R2V semantics on one project."""

    def __init__(self, store, *, project_id: str, account_id: str):
        contract._uuid(project_id, 'PROJECT_ID_INVALID')
        self.store = store
        self.project_id = project_id
        self.account_id = account_id

    def intent(self, *, reference_media_id: str, **overrides) -> MutationIntent:
        return MutationIntent(project_id=self.project_id, account_id=self.account_id,
            reference_media_id=reference_media_id, **overrides)

    # --- Reference attestation (mandatory gate, before anything else) -----

    def verify_reference(self, asset, attestation, *, media_id: str, evidence_dir) -> dict:
        """Independent attestation proof; tamper or wrong scope fails closed.

        A malformed or missing attestation is a gate, never a crash: no
        mutation preparation can run without valid reference evidence.
        """
        contract._uuid(media_id, 'REFERENCE_ID_INVALID')
        try:
            return verify_attestation(self.store, asset, attestation, media_id=media_id,
                project_id=self.project_id, evidence_dir=evidence_dir)
        except OwnerAmbiguityGate:
            raise
        except (FileNotFoundError, KeyError, TypeError, ValueError) as error:
            raise OwnerAmbiguityGate('REFERENCE_ATTESTATION_MALFORMED') from error

    # --- Durable single dispatch ------------------------------------------

    def reserve_mutation(self, job_id, *, asset, attestation, media_id: str, evidence_dir) -> object:
        """Verify the attested reference, then consume the one mutation budget.

        A job whose dispatch is already consumed can never re-enter here:
        recovery is reconciliation only and a missing output never re-authorizes
        a Generate.
        """
        self.verify_reference(asset, attestation, media_id=media_id, evidence_dir=evidence_dir)
        job = self.store.read_provider_job(job_id)
        if mutation_state(job).state == RECONCILE_ONLY:
            raise OwnerAmbiguityGate('MUTATION_ALREADY_CONSUMED_RECONCILE_ONLY')
        return self.store.reserve_dispatch(job_id)

    def reconciliation_only(self, job_id) -> object:
        """Read-only post-effect state; never re-arms a consumed dispatch."""
        job = self.store.read_provider_job(job_id)
        if mutation_state(job).state == RECONCILE_ONLY:
            return job
        raise OwnerAmbiguityGate('MUTATION_NOT_YET_CONSUMED')

    # --- Provider-native UI: transport only --------------------------------

    def request_guard(self, job, intent: MutationIntent) -> OneGenerateGuard:
        return OneGenerateGuard(self.store, job, intent.project_id,
            intent.reference_media_id, profile=intent.ui_profile)

    def observe_native_request(self, method, url, body, *, intent: MutationIntent, prompt: str) -> dict:
        """Qualify one browser-created request against the frozen intent.

        An observed request and any HTTP success remain transport facts; they
        never establish provider acceptance or output identity.
        """
        return validate_native_request(method, url, body, project_id=intent.project_id,
            reference_id=intent.reference_media_id, prompt=prompt,
            profile=intent.ui_profile)

    # --- Backend-owned output identity -------------------------------------

    def attribute_output(self, records, *, intent: MutationIntent, prompt: str,
                         provider_job_id: str, baseline_ids: list[str],
                         reference_filename: str):
        """Own the one fresh backend output or return None (effect UNKNOWN).

        Attribution uses only backend catalog evidence — pre-dispatch baseline,
        new provider identity, exact marker/reference/model lineage. Preexisting
        outputs, wrong references, malformed records, marker collisions and
        multiple candidates fail closed. None of the observed click, request,
        HTTP, DOM or gallery state can substitute.
        """
        if intent.contract_version != contract.CONTRACT_VERSION_2026_10_01:
            raise OwnerAmbiguityGate('OUTPUT_ATTRIBUTION_CONTRACT_UNQUALIFIED')
        return contract.match_r2v_output_v2026_10_01(
            records, intent.project_id, intent.reference_media_id, reference_filename,
            provider_job_id, baseline_ids=baseline_ids, model=intent.model)

    def bind_owned_output(self, job_id: str, output_id: str) -> dict:
        return self.store.bind_output(job_id, output_id)

    # --- Exact acquisition --------------------------------------------------

    def acquire_bound_media(self, payload, *, intent: MutationIntent, media_id: str,
                            data: bytes, response_url: str, status: int, headers: dict,
                            kind: str = 'video') -> BoundMedia:
        """Bind media identity, project, stable resource path and exact bytes.

        Signed URLs are transport only and are never persisted in evidence.
        """
        if media_id == intent.reference_media_id and kind == 'video':
            raise OwnerAmbiguityGate('OUTPUT_REFERENCE_NOT_DISTINCT')
        resource = parse_media_resource(payload, media_id=media_id,
            project_id=intent.project_id, kind=kind)
        return bind_media_bytes(resource, data=data, response_url=response_url,
            status=status, headers=headers)

    def normalize_bound_media(self, payloads, *, intent: MutationIntent, media_id: str,
                              kind: str = 'video') -> MediaResource:
        """Identical duplicate representations of one resource normalize to one.

        The same media identity served with different resources, sizes or
        shapes stays ambiguous and fails closed.
        """
        resources = [parse_media_resource(payload, media_id=media_id,
            project_id=intent.project_id, kind=kind) for payload in payloads]
        representations = {(r.url, r.byte_size, r.mime_type) for r in resources}
        if len(representations) != 1:
            raise OwnerAmbiguityGate('BOUND_MEDIA_RESOURCE_AMBIGUOUS')
        return resources[0]
