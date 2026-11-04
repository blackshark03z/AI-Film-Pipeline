"""Generic reference-conditioned Flow R2V runtime orchestration.

One ordinary Film shot, one reusable path from frozen Film lineage to a
QC-eligible generated Asset:

ShotSpec
→ PromptPlan (existing deterministic compiler, reference hashes bound)
→ RoutingDecision / GenerationAttempt (existing routing)
→ ProviderJob with the exact Flow submission prompt frozen before authority
→ verified reference attestation gate (FlowR2VBoundary, mandatory)
→ one durable mutation reservation (one dispatch budget, one journal)
→ one guarded native-UI request (browser is transport only)
→ unique backend output attribution against the frozen pre-dispatch baseline
→ exact media acquisition through LiveRuntimeExecutor
→ fresh lineage readback and QC exact-lineage eligibility.

This module composes proven pieces; it introduces no second dispatch journal,
ProviderJob model, attestation system, acquisition store or Film Core, and it
has no Slice-0011 semantic dependency. Slice orchestration stays historical
authority. Creative semantic qualification remains a per-shot concern: the
compact prompt adapter below enforces the qualified wire envelope mechanically
and fails closed rather than truncating or dropping creative content.
"""
from __future__ import annotations

import asyncio
import re
import sqlite3
from dataclasses import dataclass
from pathlib import Path

from .core import PromptPlan, ProviderCapabilities, ShotSpec, sha256
from .execution import DryRunProvider, route as route_plan
from .flow_r2v_boundary import FlowR2VBoundary, MutationIntent
from .live_runtime import Asset, LiveRuntimeExecutor, make_provider_job
from .providers import flow_rpc_contract as contract
from .providers.flow_canonical_ui import OneGenerateGuard
from .providers.flow_media import MediaResource, bind_media_bytes, parse_media_resource
from .providers.flow_reference_rpc import FlowReferenceRpcDrift, FlowReferenceRpcSession
from .providers.flow_reference_upload import OwnerAmbiguityGate
from .providers.flow_r2v_prompt import FlowR2VPrompt, film_marker
from .store import SQLiteStore

# The runtime's own compact-prompt adapter version. Distinct from the
# historical Shot-A-qualified semantic reducer; both freeze the same durable
# correlation keys.
COMPACT_VERSION = 'flow-r2v-runtime-compact-v1'

# Qualified Flow R2V wire envelope for the creative body. The trailing
# execution marker is excluded from both bounds, matching the qualified
# historical envelope. Anything larger fails closed for explicit creative
# reduction; nothing is ever silently truncated.
MAX_PROMPT_CHARS = 500
MAX_PROMPT_WORDS = 75

_MARK = '[FILM-'


def _clean_creative(value) -> str:
    """Whitespace-normalized creative text; marker collisions fail closed."""
    if not isinstance(value, str):
        raise OwnerAmbiguityGate('FLOW_R2V_CREATIVE_TEXT_INVALID')
    clean = ' '.join(value.split())
    if _MARK in clean:
        raise OwnerAmbiguityGate('FLOW_R2V_CREATIVE_MARKER_COLLISION')
    return clean


def _scan_creative(value) -> None:
    if isinstance(value, str):
        if _MARK in value:
            raise OwnerAmbiguityGate('FLOW_R2V_CREATIVE_MARKER_COLLISION')
    elif isinstance(value, dict):
        for child in value.values():
            _scan_creative(child)
    elif isinstance(value, list):
        for child in value:
            _scan_creative(child)


def compact_r2v_prompt(plan: PromptPlan, provider_job_id: str, *, model: str) -> FlowR2VPrompt:
    """Deterministic mechanical reduction of a canonical PromptPlan to the
    qualified Flow R2V wire envelope: fixed-order compact prose plus exactly
    one execution marker. Fail-closed on unqualified provider, missing or
    multiple image references, wrong duration, marker collisions and
    over-length creative bodies."""
    marker = film_marker(provider_job_id)
    if plan.provider_id != 'flow_veo':
        raise OwnerAmbiguityGate('FLOW_R2V_PROVIDER_UNQUALIFIED')
    image_input = plan.mapped_controls.get('image_input')
    if (not isinstance(image_input, list) or len(image_input) != 1
            or not isinstance(image_input[0], dict)
            or set(image_input[0]) != {'asset_id', 'sha256'}
            or not re.fullmatch('[a-f0-9]{64}', image_input[0].get('sha256', ''))):
        raise OwnerAmbiguityGate('FLOW_R2V_EXACT_IMAGE_INPUT_REQUIRED')
    _scan_creative(plan.canonical_blocks)
    blocks = plan.canonical_blocks
    try:
        shot_block = blocks['SHOT / DRAMATIC PURPOSE']
        camera = blocks['CAMERA / LENS / MOVEMENT']['camera']
        characters = blocks['SUBJECT / CHARACTER LOCK'].get('characters') or []
        action = blocks['ACTION / PERFORMANCE']
        environment = blocks['ENVIRONMENT / WORLD LOCK'].get('environment') or {}
        blocking = blocks['BLOCKING / START-END STATE']['blocking']
        continuity = blocks['CONTINUITY CONSTRAINTS']
        audio = blocks['AUDIO / DIALOGUE'].get('audio') or {}
        negatives = blocks['NEGATIVE / FORBIDDEN BEHAVIOR']
    except (KeyError, TypeError):
        raise OwnerAmbiguityGate('FLOW_R2V_CREATIVE_BLOCKS_INVALID') from None
    if shot_block.get('duration_target_s') != 8:
        raise OwnerAmbiguityGate('FLOW_R2V_DURATION_UNSUPPORTED')

    parts = [f"{shot_block['shot_type']} shot: {_clean_creative(shot_block['dramatic_purpose'])}"]
    movement = camera.get('movement') or {}
    move = movement.get('type', 'locked')
    if movement.get('purpose'):
        move += f" ({_clean_creative(movement['purpose'])})"
    parts.append(f"{camera.get('framing')} from {camera.get('height')}, "
                 f"{camera.get('lens_intent')} lens, {move} camera")
    for character in characters:
        if not isinstance(character, dict):
            raise OwnerAmbiguityGate('FLOW_R2V_CREATIVE_BLOCKS_INVALID')
        described = ', '.join(_clean_creative(character[key]) for key in
                              ('character_id', 'role_in_shot', 'behavior_state')
                              if character.get(key))
        parts.append('Subject: ' + described)
    performance = action.get('performance') or {}
    beats = [_clean_creative(beat) for beat in
             (action.get('action_beats') or []) + (performance.get('observable_beats') or [])]
    if beats:
        parts.append('Action: ' + '; '.join(beats))
    setting = [_clean_creative(environment[key]) for key in
               ('time_of_day', 'weather', 'atmosphere') if environment.get(key)]
    if setting:
        parts.append('Setting: ' + ', '.join(setting))
    parts.append(f"Start: {_clean_creative(blocking['start'])}; "
                 f"End: {_clean_creative(blocking['end'])}")
    preserve = [_clean_creative(value) for value in continuity.get('must_preserve') or []]
    if preserve:
        parts.append('Preserve: ' + '; '.join(preserve))
    avoid = list(dict.fromkeys(
        [_clean_creative(value) for value in (negatives.get('must_avoid') or [])
         + (negatives.get('performance_forbidden') or [])]))
    if avoid:
        parts.append('Avoid: ' + '; '.join(avoid))
    if audio.get('dialogue'):
        parts.append('Dialogue: ' + _clean_creative(audio['dialogue']))
    body = '. '.join(parts) + '.'
    if len(body) > MAX_PROMPT_CHARS or len(body.split()) > MAX_PROMPT_WORDS:
        raise OwnerAmbiguityGate(
            'FLOW_R2V_COMPACT_PROMPT_LIMIT; explicit creative reduction required')
    # The marker joins the body as one single-line prompt. The qualified
    # native-UI envelope is proven with exactly this serialization: the
    # ProseMirror editor readback and the browser wire prompt reproduce a
    # single line byte-for-byte (the canonical A reproof released its request
    # through this form); a multi-line frozen prompt cannot pass the qualified
    # editor readback gate.
    return FlowR2VPrompt(body + ' ' + marker, marker, sha256(plan),
                         version=COMPACT_VERSION, model=model)


def qualified_catalog_snapshot(records, *, project_id: str,
        fingerprint: str = contract.QUALIFIED_BASELINE_FINGERPRINT) -> dict:
    """Validate, normalize and identity-hash one catalog observation.

    This is the pure composition applied to whatever the runtime captured
    through the qualified provider-read boundary: existing Flow catalog row
    validation → qualified fingerprint and project gate → normalized exact
    IDs → deterministic immutable snapshot identity hash. It is not an
    authority entry point: ordinary callers reach it only through
    ``freeze``'s runtime-owned capture, never with their own record lists.
    """
    if (fingerprint not in contract.QUALIFIED_CATALOG_FINGERPRINTS
            or fingerprint != contract.catalog_fingerprint(records)):
        raise OwnerAmbiguityGate('FLOW_R2V_CATALOG_BASELINE_DRIFT')
    try:
        validated = contract._validate_catalog_rows(records, project_id)
    except contract.ContractError as error:
        raise OwnerAmbiguityGate('FLOW_R2V_CATALOG_RECORDS_UNQUALIFIED') from error
    basis = {'catalog_fingerprint': fingerprint,
             'catalog_ids': sorted({row[0].lower() for row in validated}),
             'project_id': project_id}
    return {**basis, 'snapshot_sha256': sha256(basis)}


@dataclass(frozen=True)
class QualifiedFlowCatalogCapability:
    """Authority for the runtime's ONE authoritative pre-dispatch catalog read.

    Minted for a fresh, exact-type ``FlowReferenceRpcSession`` — before any
    catalog read exists. Two distinct states are never conflated:

    - SESSION AUTHORITY is qualified at mint time and requires zero reads:
      the wrapped object must be exactly ``FlowReferenceRpcSession`` (no
      subclass, wrapper or duck-typed look-alike) with a valid project UUID.
      A fresh session's ``catalog_fingerprint`` is ``None`` — that is the
      correct production state for minting.
    - OBSERVATION QUALIFICATION happens inside ``capture``: the single
      concrete catalog read must itself establish the qualified baseline
      fingerprint (via the existing ``validate_catalog_baseline`` inside the
      session's ``catalog()``), the project scope must remain exactly the
      minted one, and the exact records returned by that one read are the
      only source of the frozen snapshot.

    ``capture`` binds to the concrete class implementation, so neither
    subclass overrides nor instance-attribute shadowing can replace catalog
    semantics.
    """

    session: FlowReferenceRpcSession

    def __post_init__(self):
        # Session-AUTHORITY qualification only; no catalog read happens here.
        if type(self.session) is not FlowReferenceRpcSession:
            raise OwnerAmbiguityGate('FLOW_R2V_CATALOG_SOURCE_UNQUALIFIED')
        project_id = getattr(self.session, 'project_id', '')
        if not contract.UUID_RE.fullmatch(project_id or ''):
            raise OwnerAmbiguityGate('FLOW_R2V_CATALOG_SOURCE_UNQUALIFIED')
        # Snap the minted project scope; capture verifies it never drifts.
        object.__setattr__(self, '_minted_project', project_id)

    @property
    def project_id(self) -> str:
        return self.session.project_id

    def capture(self) -> tuple[list, str]:
        """The ONE authoritative pre-dispatch observation.

        Invokes the concrete catalog implementation exactly once, then
        qualifies the OBSERVATION: the fingerprint established by this very
        read must equal the qualified baseline, and the project scope must
        still be the minted one. Returns the immutable observation pair
        ``(records, fingerprint)``.
        """
        records = FlowReferenceRpcSession.catalog(self.session)
        fingerprint = getattr(self.session, 'catalog_fingerprint', None)
        if (fingerprint not in contract.QUALIFIED_CATALOG_FINGERPRINTS
                or fingerprint != contract.catalog_fingerprint(records)):
            raise OwnerAmbiguityGate('FLOW_R2V_CATALOG_BASELINE_DRIFT')
        if self.session.project_id != self._minted_project:
            raise OwnerAmbiguityGate('FLOW_R2V_CATALOG_SOURCE_PROJECT_MISMATCH')
        return records, fingerprint


def qualify_flow_catalog_source(session) -> QualifiedFlowCatalogCapability:
    """The authorized factory for catalog-read capabilities.

    Accepts a concrete qualified Flow session (existing FlowReferenceRpcSession
    whose catalog_fingerprint was established by validate_catalog_baseline).
    There is no other way to obtain a capability: duck-typed look-alikes,
    wrappers and unqualified sessions fail closed here.
    """
    return QualifiedFlowCatalogCapability(session)


@dataclass(frozen=True)
class RenderState:
    """One read-only render-lifecycle observation for one owned output.

    ``payload``/``resource`` are transport data for the completed case (they
    enable exact acquisition without a second as29s read) and are never
    persisted as identity; durable truth lives in the dispatch journal.
    """

    state: str
    output_id: str
    resource: MediaResource | None
    payload: object


# Journal diagnostics are bounded structural tokens, never raw transport text.
_DIAGNOSTIC_RE = re.compile(r'[A-Za-z0-9_:.-]{1,300}')


# --- as29s payload recognition (deterministic, schema-specific) -------------

# Only provider shapes with direct durable evidence are recognized. Anything
# else is UNKNOWN: never pending, never failure — it cannot advance any
# render state, streak, or window, and must not be inferred as terminal.
AS29S_PAYLOAD_KNOWN_PENDING = 'KNOWN_PENDING'
AS29S_PAYLOAD_COMPLETED = 'COMPLETED'
AS29S_PAYLOAD_UNKNOWN = 'UNKNOWN'


def classify_as29s_payload(payload, *, media_id: str, project_id: str) -> str:
    """Recognize one as29s payload against the evidenced provider shapes.

    Recognized shapes (exhaustive):

    - ``None`` — the JSON-null pending form: the historically observed
      pending signature and still evidenced on the current build;
    - the qualified completed media-resource shape for the exact media
      id/project (the flow_media contract is the schema check).

    Every other payload — arbitrary objects, malformed structures,
    superficially similar lists with drifted slots, unknown fields or types —
    is ``UNKNOWN``. An unknown payload must be surfaced as
    ``RENDER_UNOBSERVABLE`` (durable observation failure), never treated as
    pending eventual-consistency evidence and never inferred as a terminal
    failure. A future provider pending shape may only enter the recognized
    set with its own captured, constrained structural evidence.
    """
    if payload is None:
        return AS29S_PAYLOAD_KNOWN_PENDING
    try:
        parse_media_resource(payload, media_id=media_id, project_id=project_id,
                             kind='video')
    except contract.ContractError:
        return AS29S_PAYLOAD_UNKNOWN
    return AS29S_PAYLOAD_COMPLETED


@dataclass(frozen=True)
class FrozenR2VShot:
    """The frozen provider intent for one ordinary shot.

    ``job`` is the stored handle; every consuming method re-reads durable
    state and never trusts mutable fields of this dataclass alone.
    """

    shot: ShotSpec
    plan: PromptPlan
    attempt: object
    job: object
    intent: MutationIntent
    reference_asset: object


class FlowR2VShotRuntime:
    """Composition point for one reference-conditioned Flow R2V shot."""

    def __init__(self, store: SQLiteStore, *, project_id: str, account_id: str,
                 model: str = contract.MODEL_VEO_3_1_LITE):
        if model not in contract.QUALIFIED_VEO_3_1_MODELS:
            raise OwnerAmbiguityGate('MUTATION_INTENT_MODEL_UNQUALIFIED')
        self.store = store
        self.project_id = project_id
        self.account_id = account_id
        self.model = model
        self.boundary = FlowR2VBoundary(store, project_id=project_id,
                                        account_id=account_id)
        # Deterministic provider-project binding identity, derived only from
        # the provider project id; identical to the historical derivation.
        self.project_binding_id = sha256(project_id)

    def _require_reference_binding(self, job, intent: MutationIntent) -> dict:
        """The frozen reference binding must match the intent reference exactly."""
        binding = job.correlation_evidence.get('reference_binding')
        if not isinstance(binding, dict) or binding.get('media_id') != intent.reference_media_id:
            raise OwnerAmbiguityGate('FLOW_R2V_REFERENCE_BINDING_MISMATCH')
        if not isinstance(binding.get('asset_id'), str) or not binding.get('asset_id'):
            raise OwnerAmbiguityGate('FLOW_R2V_REFERENCE_BINDING_MISMATCH')
        return binding

    def _require_baseline_snapshot(self, job) -> list[str]:
        """The frozen pre-dispatch baseline is mandatory at every authority point.

        No silent empty-baseline fallback exists: a job whose snapshot lacks
        the qualified fingerprint, the runtime's project, a list of UUIDs or
        the deterministic snapshot identity hash can never reserve or
        attribute through this runtime. Content changes cannot preserve the
        snapshot identity, so tampered snapshots fail closed.
        """
        snapshot = job.pre_dispatch_snapshot
        if snapshot.get('catalog_fingerprint') not in contract.QUALIFIED_CATALOG_FINGERPRINTS:
            raise OwnerAmbiguityGate('FLOW_R2V_CATALOG_BASELINE_DRIFT')
        if snapshot.get('project_id') != self.project_id:
            raise OwnerAmbiguityGate('FLOW_R2V_BASELINE_PROJECT_MISMATCH')
        ids = snapshot.get('catalog_ids')
        if not isinstance(ids, list) or any(not isinstance(value, str) for value in ids):
            raise OwnerAmbiguityGate('FLOW_R2V_BASELINE_SNAPSHOT_INVALID')
        try:
            for value in ids:
                contract._uuid(value, 'OUTPUT_BASELINE_INVALID')
        except contract.ContractError as error:
            raise OwnerAmbiguityGate('FLOW_R2V_BASELINE_SNAPSHOT_INVALID') from error
        basis = {'catalog_fingerprint': snapshot['catalog_fingerprint'],
                 'catalog_ids': ids, 'project_id': snapshot['project_id']}
        if snapshot.get('snapshot_sha256') != sha256(basis):
            raise OwnerAmbiguityGate('FLOW_R2V_BASELINE_SNAPSHOT_IDENTITY_DRIFT')
        return ids

    # --- Freeze -------------------------------------------------------------

    def _existing_job_for_shot(self, shot_id: str, spec_version: int | None = None):
        """A restart resumes the same job; it cannot create another attempt."""
        with sqlite3.connect(self.store.path) as connection:
            query = "SELECT id FROM generation_attempts WHERE json_extract(payload,'$.shot_id')=?"
            args = [shot_id]
            if spec_version is not None:
                query += " AND json_extract(payload,'$.shot_spec_version')=?"
                args.append(spec_version)
            attempts = [row[0] for row in connection.execute(query, args).fetchall()]
            if not attempts:
                return None
            if len(attempts) != 1:
                raise OwnerAmbiguityGate('FLOW_R2V_SHOT_ATTEMPT_AMBIGUOUS')
            jobs = [row[0] for row in connection.execute(
                'SELECT id FROM provider_jobs WHERE generation_attempt_id=?',
                (attempts[0],)).fetchall()]
        if len(jobs) != 1:
            raise OwnerAmbiguityGate('FLOW_R2V_SHOT_JOB_AMBIGUOUS')
        return self.store.read_provider_job(jobs[0])

    def repair_parent(self, shot: ShotSpec, repair_decision_id: str) -> ShotSpec:
        """A changed version needs an exact, resolved, Owner-rejected predecessor.

        This only qualifies a new intent. The caller still needs its current
        Owner budget; no failed or uncertain request becomes retryable.
        """
        from .qc import QCStore
        try:
            parent, route, job, _, repair = QCStore(self.store).repair_source(repair_decision_id)
        except (ValueError, KeyError) as error:
            raise OwnerAmbiguityGate('FLOW_REPAIR_PREDECESSOR_UNQUALIFIED') from error
        if (repair['shot_id'] != shot.shot_id or job.project_binding_id != self.project_binding_id
                or job.provider_id != 'flow_veo' or route.provider_id != 'flow_veo'
                or job.status != 'SUCCEEDED' or job.dispatch_count != 1
                or shot.spec_version != parent.spec_version + 1 or shot.spec_version > 3
                or shot.shot_id != parent.shot_id or sha256(shot) == sha256(parent)):
            raise OwnerAmbiguityGate('FLOW_REPAIR_PREDECESSOR_UNQUALIFIED')
        return parent

    def freeze(self, shot: ShotSpec, capabilities: ProviderCapabilities, *,
               reference_asset, reference_media_id: str, reference_filename: str = '',
               catalog_source, started_at: str | None = None,
               prompt_compiler=compact_r2v_prompt,
               compiler_kwargs: dict | None = None,
               repair_decision_id: str | None = None) -> FrozenR2VShot:
        """Compile, route and freeze one ordinary R2V shot into a ProviderJob
        whose exact submission prompt is durable before any authority exists.
        A restart with identical inputs returns the same frozen job.

        The pre-dispatch baseline is runtime-captured through the qualified
        provider-read boundary: ``catalog_source`` must be a
        ``QualifiedFlowCatalogCapability`` minted by
        ``qualify_flow_catalog_source`` for a fresh, exact-type Flow session —
        no prior catalog read is required or allowed to matter. The runtime
        itself asks that capability exactly once for the authoritative
        pre-dispatch observation (the single read that also establishes the
        qualified baseline fingerprint) and derives the snapshot from that
        observation alone. Callers choose WHICH qualified session is used;
        they cannot manufacture an object that merely looks like a catalog
        source, and a restart reuses the frozen snapshot without re-capture.
        The whole Film path plus ProviderJob freeze commits atomically."""
        contract._uuid(reference_media_id, 'REFERENCE_ID_INVALID')
        if not isinstance(catalog_source, QualifiedFlowCatalogCapability):
            raise OwnerAmbiguityGate('FLOW_R2V_CATALOG_SOURCE_UNQUALIFIED')
        if catalog_source.project_id != self.project_id:
            raise OwnerAmbiguityGate('FLOW_R2V_CATALOG_SOURCE_PROJECT_MISMATCH')
        # Fresh immutable reference readback; the plan binds these exact bytes.
        stored_reference = self.store.read_reference_asset(reference_asset.asset_id)
        reference_binding = {'asset_id': stored_reference.asset_id,
                             'reference_sha256': stored_reference.sha256,
                             'media_id': reference_media_id}
        if reference_filename:
            reference_binding['provider_filename'] = reference_filename

        plan = compile_plan(shot, capabilities, stored_reference)
        decision = route_plan(shot, [plan], [capabilities],
                              {capabilities.provider_id: True},
                              required_controls={'image_input'})
        dry = DryRunProvider()
        request = dry.build_request(plan, decision)
        attempt = dry.create_attempt(shot, plan, decision, request,
                                     started_at=started_at)

        if repair_decision_id:
            parent = self.repair_parent(shot, repair_decision_id)
            if sha256(shot.blocking) == sha256(parent.blocking) and shot.references == parent.references:
                raise OwnerAmbiguityGate('FLOW_REPAIR_CHANGED_INPUT_REQUIRED')
        prior = self._existing_job_for_shot(shot.shot_id, shot.spec_version)
        if prior is not None:
            if prior.correlation_evidence.get('repair_decision_id') != repair_decision_id:
                raise OwnerAmbiguityGate('FLOW_REPAIR_RESTART_DECISION_CHANGED')
            return self._resume_frozen(prior, shot, plan, decision, reference_binding)
        if not repair_decision_id:
            with sqlite3.connect(self.store.path) as connection:
                if connection.execute("SELECT id FROM generation_attempts WHERE json_extract(payload,'$.shot_id')=?",
                                      (shot.shot_id,)).fetchone():
                    raise OwnerAmbiguityGate('FLOW_R2V_RESTART_REPAIR_DECISION_REQUIRED')
        # The ONE authoritative pre-dispatch catalog observation, captured by
        # the runtime through the qualified capability: exactly one concrete
        # read that itself establishes the qualified baseline; a restart
        # never reaches this line again.
        records, fingerprint = catalog_source.capture()
        snapshot = qualified_catalog_snapshot(records, project_id=self.project_id,
                                              fingerprint=fingerprint)
        preview = make_provider_job(attempt, project_binding_id=self.project_binding_id,
                                    pre_dispatch_snapshot=snapshot)
        compiled = prompt_compiler(plan, preview.provider_job_id, model=self.model,
                                   **(compiler_kwargs or {}))
        prompt = compiled.text
        job = preview.model_copy(update={'correlation_evidence': {
            'prompt': prompt, 'prompt_plan_hash': sha256(plan),
            'submission_prompt_hash': sha256(prompt),
            'correlation_marker': compiled.marker,
            'provider_prompt_compiler': compiled.version,
            'reference_binding': reference_binding}})
        if repair_decision_id:
            job = job.model_copy(update={'correlation_evidence': {
                **job.correlation_evidence, 'repair_decision_id': repair_decision_id}})
        self.store.save_frozen_path_and_job(shot, plan, decision, attempt, job)
        if job.provider_job_id != preview.provider_job_id:
            raise ValueError('provider job identity changed during freeze')
        return self._frozen(job, stored_reference)

    def _resume_frozen(self, prior, shot, plan, decision, reference_binding,
                       prompt_compiler=compact_r2v_prompt,
                       compiler_kwargs: dict | None = None):
        """Restart path: identical inputs must resume the identical frozen job.

        The frozen pre-dispatch snapshot IS the historical truth: it is
        verified here and never re-captured from a fresh observation."""
        self._require_baseline_snapshot(prior)
        old_shot, old_plan, old_route, _ = self.store.read_path(
            prior.generation_attempt_id)
        if (old_shot, old_plan, old_route) != (shot, plan, decision):
            raise OwnerAmbiguityGate('FLOW_R2V_RESTART_PATH_DIFFERS')
        if (prior.project_binding_id != self.project_binding_id
                or prior.correlation_evidence.get('reference_binding') != reference_binding):
            raise OwnerAmbiguityGate('FLOW_R2V_RESTART_INTENT_DIFFERS')
        if prior.correlation_evidence.get('prompt') != prompt_compiler(
                old_plan, prior.provider_job_id, model=self.model,
                **(compiler_kwargs or {})).text:
            raise OwnerAmbiguityGate('FLOW_R2V_RESTART_PROMPT_DIFFERS')
        return self._frozen(prior, self.store.read_reference_asset(
            reference_binding['asset_id']))

    def _frozen(self, job, stored_reference) -> FrozenR2VShot:
        job = self.store.read_provider_job(job.provider_job_id)
        binding = job.correlation_evidence.get('reference_binding')
        intent = MutationIntent(project_id=self.project_id, account_id=self.account_id,
                                reference_media_id=binding.get('media_id')
                                if isinstance(binding, dict) else None, model=self.model)
        self._require_reference_binding(job, intent)
        shot, plan, route, attempt = self.store.read_path(job.generation_attempt_id)
        return FrozenR2VShot(shot=shot, plan=plan, attempt=attempt, job=job,
                             intent=intent, reference_asset=stored_reference)

    # --- One mutation opportunity -------------------------------------------

    def reserve(self, frozen: FrozenR2VShot, *, attestation: dict, evidence_dir) -> object:
        """Verify the attested reference, then consume the one mutation budget.

        The frozen pre-dispatch baseline is re-validated before the budget is
        spent: a job without a qualified snapshot can never reserve.
        """
        job = self.store.read_provider_job(frozen.job.provider_job_id)
        binding = self._require_reference_binding(job, frozen.intent)
        self._require_baseline_snapshot(job)
        reference = self.store.read_reference_asset(binding['asset_id'])
        return self.boundary.reserve_mutation(job.provider_job_id, intent=frozen.intent,
                                              asset=reference, attestation=attestation,
                                              evidence_dir=evidence_dir)

    # --- One guarded native request ------------------------------------------

    def arm_native_guard(self, frozen: FrozenR2VShot) -> OneGenerateGuard:
        """Arm the one-request guard against the durably frozen prompt."""
        guard = self.boundary.request_guard(self.store.read_provider_job(
            frozen.job.provider_job_id), frozen.intent)
        guard.armed = True
        return guard

    def observe_native_request(self, frozen: FrozenR2VShot, method: str, url: str,
                               body: str) -> dict:
        """Qualify one browser-created request against the frozen intent."""
        job = self.store.read_provider_job(frozen.job.provider_job_id)
        return self.boundary.observe_native_request(
            method, url, body, intent=frozen.intent,
            prompt=job.correlation_evidence['prompt'])

    def _request_fact(self, job_id: str) -> dict:
        requests = [fact for fact in self.store.read_dispatch_facts(job_id)
                    if fact['kind'] == 'GENERATE_REQUEST_OBSERVED']
        if len(requests) != 1:
            raise OwnerAmbiguityGate('FLOW_R2V_REQUEST_NOT_OBSERVED')
        return requests[0]

    def observe_provider_response(self, frozen: FrozenR2VShot, *, status: int) -> None:
        """Record the one HTTP response against the one observed request."""
        job_id = frozen.job.provider_job_id
        request = self._request_fact(job_id)
        self.store.record_dispatch_fact(job_id, 'PROVIDER_RESPONSE_OBSERVED',
            {'request_hash': request['data']['request_hash'], 'status': status})

    def observe_provider_acceptance(self, frozen: FrozenR2VShot, *,
                                    provider_reference: str) -> None:
        """Record observed acceptance bound to the same observed request.

        Acceptance is transport evidence only; it never establishes output
        identity, which stays backend-owned attribution below.
        """
        job_id = frozen.job.provider_job_id
        request = self._request_fact(job_id)
        self.store.record_dispatch_fact(job_id, 'PROVIDER_ACCEPTANCE_OBSERVED',
            {'request_hash': request['data']['request_hash'],
             'provider_reference': provider_reference,
             'contract': request['data']['contract']})

    # --- Backend-owned output identity ----------------------------------------

    def attribute_backend_output(self, frozen: FrozenR2VShot, records) -> str | None:
        """Own the one fresh backend output or return None (effect UNKNOWN).

        Uses only the frozen pre-dispatch baseline and the stored frozen
        reference filename; a missing output never re-authorizes a Generate.
        """
        job_id = frozen.job.provider_job_id
        job = self.store.read_provider_job(job_id)
        binding = self._require_reference_binding(job, frozen.intent)
        baseline = self._require_baseline_snapshot(job)
        row = self.boundary.attribute_output(records, intent=frozen.intent,
            provider_job_id=job_id, baseline_ids=list(baseline),
            reference_filename=binding.get('provider_filename', ''))
        if row is None:
            return None
        output_id = row[0]
        self.store.record_dispatch_fact(job_id, 'REMOTE_IDENTITY_OBSERVED',
            {'output_id': output_id,
             'method': 'flow_r2v_runtime_backend_attribution'})
        self.boundary.bind_owned_output(job_id, output_id)
        return output_id

    # --- Exact acquisition ------------------------------------------------------

    def acquire(self, frozen: FrozenR2VShot, *, transport, destination_dir,
                media_payload) -> Asset:
        """Reconcile from the exact binding, then acquire exact provider media.

        The qualified flow_media contract is runtime-owned here: the provider
        media payload is parsed against the durably owned output id and
        project, and bound to the actual staged bytes before any receipt or
        Asset can exist. Caller-created evidence cannot enter this path.
        """
        job_id = frozen.job.provider_job_id
        executor = LiveRuntimeExecutor(self.store, transport)
        reconciled = asyncio.run(executor.reconcile(job_id))
        if reconciled.status != 'SUCCEEDED':
            raise OwnerAmbiguityGate('FLOW_R2V_OUTPUT_NOT_SUCCEEDED')
        bindings = self.store.read_output_bindings(job_id)
        if len(bindings) != 1:
            raise OwnerAmbiguityGate('FLOW_R2V_OUTPUT_NOT_UNIQUE')
        output_id = bindings[0]['output_id']
        try:
            resource = parse_media_resource(media_payload, media_id=output_id,
                                            project_id=self.project_id, kind='video')
        except contract.ContractError as error:
            raise OwnerAmbiguityGate('FLOW_R2V_MEDIA_PAYLOAD_UNQUALIFIED') from error
        verified = _VerifiedAcquisition(transport, resource)
        # The download executor runs the runtime-owned wrapper: the qualified
        # flow_media contract binds the parsed resource to the staged bytes
        # before any receipt or Asset can exist.
        downloader = LiveRuntimeExecutor(self.store, verified)
        assets = asyncio.run(downloader.download_assets(job_id, Path(destination_dir)))
        if len(assets) != 1 or assets[0].provider_asset_id != output_id:
            raise OwnerAmbiguityGate('FLOW_R2V_ACQUIRED_ASSET_MISMATCH')
        if verified.media is None:
            # Idempotent restart path: the completed receipt already covered
            # this output, so the wrapper never fetched. The runtime still
            # binds the parsed resource to the persisted bytes itself.
            persisted = Path(assets[0].uri_or_path).read_bytes()
            verified.media = bind_media_bytes(resource, data=persisted,
                response_url=resource.url, status=200,
                headers={'content-type': resource.mime_type,
                         'content-length': str(resource.byte_size)})
        if verified.media.evidence['sha256'] != assets[0].sha256:
            raise OwnerAmbiguityGate('FLOW_R2V_ACQUIRED_BYTES_DRIFT')
        return assets[0]

    # --- Render lifecycle observation (read-only, post-ownership) -------------

    # Bounded render-terminal policy: one qualified catalog disappearance may
    # be eventual consistency, a provider transition, or read lag. A terminal
    # drop is established only when the disappearance persists across this
    # many consecutive qualified read-only reconciliation observations (policy
    # option 2), or when explicit provider terminal-failure evidence exists
    # (option 1 — none is observable on the current qualified surfaces, so no
    # code path fabricates one). Between the first disappearance and
    # terminality the state is RENDER_STATE_UNRESOLVED: may_submit stays false
    # and repair-regeneration authority does not exist.
    RENDER_DROP_PERSISTENCE_THRESHOLD = 3
    # Terminality additionally requires the disappearance to persist for at
    # least this many seconds — measured durably from the journal timestamp of
    # the FIRST disappearance of the current streak to the current qualified
    # observation. Renders historically complete within ~30–120 s and provider
    # eventual-consistency windows are expected to be far shorter, so a
    # disappearance that is both repeatedly observed and at least this old is
    # durable absence, not a rapid polling burst. Production default; tests
    # pass explicit observation times instead of sleeping.
    RENDER_DROP_MIN_ELAPSED_SECONDS = 900

    def observe_render_state(self, frozen: FrozenR2VShot, *, session,
                             observed_at: str | None = None) -> RenderState:
        """One read-only render-state reconciliation for the owned output.

        Reachable only after durable output ownership (exactly one bound
        output). The read transport must be an exact fresh
        ``FlowReferenceRpcSession`` for the runtime's project; catalog/media
        reads bind to the concrete class implementations so wrappers and
        shadowing cannot replace the qualified read semantics.

        The as29s payload is recognized by ``classify_as29s_payload`` — only
        the evidenced null pending form and the qualified completed media
        shape are recognized; anything else is UNKNOWN →

        Classification per qualified observation:

        - recognized completed media shape → ``RENDER_COMPLETED`` (and a
          previously recorded drop never downgrades it — resolved media is
          stronger evidence than a policy-derived absence);
        - recognized null pending form with the owned row still present in a
          qualified fresh catalog read → ``RENDER_PENDING`` — pending
          evidence, never failure, never retry authority;
        - recognized null pending form with the owned row absent →
          ``RENDER_STATE_UNRESOLVED`` (a single disappearance may be eventual
          consistency or read lag) — until the disappearance persists across
          ``RENDER_DROP_PERSISTENCE_THRESHOLD`` consecutive qualified
          observations AND at least ``RENDER_DROP_MIN_ELAPSED_SECONDS``
          measured durably from the journal timestamp of the streak's first
          disappearance; only then is the terminal ``ADMITTED_RENDER_DROPPED``
          recorded, routed to an Owner RepairDecision, never to redispatch;
        - an UNKNOWN payload or any unqualified read (RPC drift, catalog
          baseline drift) → ``RENDER_UNOBSERVABLE`` plus a durable
          ``OBSERVATION_FAILURE``; it advances neither the streak counter nor
          the persistence window, and the previous state stands.

        ``observed_at`` pins the observation time (ISO-8601 UTC); production
        callers leave it unset (wall clock). Re-observation is idempotent for
        fixed-basis states; disappearance observations accumulate by design —
        each qualified read is one more persistence datapoint.
        """
        job_id = frozen.job.provider_job_id
        job = self.store.read_provider_job(job_id)
        bindings = self.store.read_output_bindings(job_id)
        if len(bindings) != 1:
            raise OwnerAmbiguityGate('FLOW_R2V_OUTPUT_NOT_UNIQUE')
        output_id = bindings[0]['output_id']
        if type(session) is not FlowReferenceRpcSession:
            raise OwnerAmbiguityGate('FLOW_R2V_RENDER_SOURCE_UNQUALIFIED')
        if session.project_id != self.project_id:
            raise OwnerAmbiguityGate('FLOW_R2V_RENDER_SOURCE_PROJECT_MISMATCH')
        if observed_at is not None:
            # Validate before anything can be journaled with a bad timestamp.
            self._observation_time(observed_at)

        def unobservable(diagnostic: str) -> RenderState:
            if not _DIAGNOSTIC_RE.fullmatch(diagnostic):
                diagnostic = 'RENDER_READ_UNAVAILABLE'
            self.store.record_dispatch_fact(job_id, 'OBSERVATION_FAILURE',
                                            {'diagnostic': diagnostic},
                                            at=observed_at)
            return RenderState(state='RENDER_UNOBSERVABLE', output_id=output_id,
                               resource=None, payload=None)

        try:
            payload = FlowReferenceRpcSession.media_payload(session, output_id)
        except FlowReferenceRpcDrift as error:
            return unobservable(str(error))
        classification = classify_as29s_payload(payload, media_id=output_id,
                                                project_id=self.project_id)
        if classification == AS29S_PAYLOAD_UNKNOWN:
            return unobservable('FLOW_R2V_MEDIA_PAYLOAD_UNQUALIFIED')
        if classification == AS29S_PAYLOAD_COMPLETED:
            resource = parse_media_resource(payload, media_id=output_id,
                                            project_id=self.project_id, kind='video')
            self.store.record_dispatch_fact(job_id, 'RENDER_COMPLETED_OBSERVED',
                {'output_id': output_id, 'basis': 'as29s_media_resolved'},
                at=observed_at)
            return RenderState(state='RENDER_COMPLETED', output_id=output_id,
                               resource=resource, payload=payload)
        # Recognized pending form: the qualified fresh catalog read decides
        # between still-pending, unresolved, and (only after the bounded
        # persistence policy) admitted-then-dropped.
        try:
            records = FlowReferenceRpcSession.catalog(session)
            fingerprint = getattr(session, 'catalog_fingerprint', None)
            if (fingerprint not in contract.QUALIFIED_CATALOG_FINGERPRINTS
                    or fingerprint != contract.catalog_fingerprint(records)):
                raise FlowReferenceRpcDrift('FLOW_R2V_CATALOG_BASELINE_DRIFT')
            if session.project_id != self.project_id:
                raise FlowReferenceRpcDrift('FLOW_R2V_RENDER_SOURCE_PROJECT_MISMATCH')
        except FlowReferenceRpcDrift as error:
            return unobservable(str(error))
        row_present = any(row[0].lower() == output_id.lower() for row in records)
        if row_present:
            self.store.record_dispatch_fact(job_id, 'RENDER_PENDING_OBSERVED',
                {'output_id': output_id, 'basis': 'as29s_null_media_row_present'},
                at=observed_at)
            return RenderState(state='RENDER_PENDING', output_id=output_id,
                               resource=None, payload=None)
        facts = self.store.read_dispatch_facts(job_id)
        if any(f['kind'] == 'ADMITTED_RENDER_DROPPED'
               and f['data'].get('output_id') == output_id for f in facts):
            # Terminality is already durably established; further misses add
            # no datapoints and never un-drop the output.
            return RenderState(state='ADMITTED_RENDER_DROPPED', output_id=output_id,
                               resource=None, payload=None)
        if any(f['kind'] == 'RENDER_COMPLETED_OBSERVED'
               and f['data'].get('output_id') == output_id for f in facts):
            # Resolved media was observed for this exact output: completion is
            # never downgraded into a drop by a later catalog disappearance.
            return RenderState(state='RENDER_COMPLETED', output_id=output_id,
                               resource=None, payload=None)
        streak_count, streak_first_at = self._trailing_disappearance_streak(
            job_id, output_id)
        candidate_count = streak_count + 1
        now = self._observation_time(observed_at)
        window_start = streak_first_at or now
        elapsed_s = (now - window_start).total_seconds()
        if (candidate_count >= self.RENDER_DROP_PERSISTENCE_THRESHOLD
                and elapsed_s >= self.RENDER_DROP_MIN_ELAPSED_SECONDS):
            self.store.record_dispatch_fact(job_id, 'ADMITTED_RENDER_DROPPED',
                {'output_id': output_id,
                 'basis': 'persistent_disappearance_across_bounded_policy'},
                at=observed_at)
            return RenderState(state='ADMITTED_RENDER_DROPPED', output_id=output_id,
                               resource=None, payload=None)
        self.store.record_dispatch_fact(job_id, 'RENDER_STATE_UNRESOLVED',
            {'output_id': output_id,
             'basis': f'as29s_null_media_row_absent_attempt_{candidate_count}'},
            at=observed_at)
        return RenderState(state='RENDER_STATE_UNRESOLVED', output_id=output_id,
                           resource=None, payload=None)

    @staticmethod
    def _observation_time(observed_at: str | None):
        from datetime import datetime

        if observed_at is None:
            from .live_runtime import utc_now

            observed_at = utc_now()
        try:
            parsed = datetime.fromisoformat(observed_at)
        except (TypeError, ValueError) as error:
            raise OwnerAmbiguityGate('RENDER_OBSERVATION_TIME_INVALID') from error
        if parsed.tzinfo is None:
            raise OwnerAmbiguityGate('RENDER_OBSERVATION_TIME_INVALID')
        return parsed

    def _trailing_disappearance_streak(self, job_id: str, output_id: str):
        """Trailing run of qualified disappearance observations.

        Returns ``(count, first_observation_datetime_or_None)`` for the
        consecutive ``RENDER_STATE_UNRESOLVED`` facts after the last state
        change (any pending/completed/drop observation breaks the streak, so
        a row return resets persistence and a later disappearance starts a
        new interval). Unqualified observations (``OBSERVATION_FAILURE``) and
        unrelated facts neither advance the streak nor break it; their
        timestamps are never used for the persistence window. Journal
        integrity and timestamp validity raise fail-closed.
        """
        count = 0
        first_at = None
        for fact in reversed(self.store.read_dispatch_facts(job_id)):
            kind = fact['kind']
            if kind == 'RENDER_STATE_UNRESOLVED':
                if fact['data'].get('output_id') == output_id:
                    count += 1
                    first_at = fact['at']
                continue
            if kind in {'RENDER_PENDING_OBSERVED', 'RENDER_COMPLETED_OBSERVED',
                        'ADMITTED_RENDER_DROPPED'}:
                break
        return count, (self._observation_time(first_at) if first_at else None)

    # --- Restart classification -------------------------------------------------

    def recovery(self, frozen: FrozenR2VShot):
        """Durable restart classification for one frozen job.

        Delegates to the existing recovery policy with correctly derived
        binding/acquisition state. ``may_submit`` can never be true once the
        dispatch budget is consumed; callers never re-implement this.
        """
        executor = LiveRuntimeExecutor(self.store, None)  # transport never consulted
        return executor.recovery_decision(frozen.job.provider_job_id)

    # --- QC handoff eligibility ---------------------------------------------------

    def qc_eligibility(self, frozen: FrozenR2VShot, asset: Asset) -> dict:
        """Fresh-process readback: exact lineage plus hard technical gates."""
        from .qc import technical_evidence
        from .qc_runner import exact_lineage
        _, shot, exact_asset = exact_lineage(self.store.path,
            frozen.attempt.generation_attempt_id, frozen.job.provider_job_id,
            asset.asset_id)
        evidence_rows, metadata = technical_evidence(shot, exact_asset)
        return {'exact_lineage': True,
                'technical_pass': all(row.verdict == 'pass' for row in evidence_rows),
                'metadata': metadata}


class _VerifiedAcquisition:
    """Transport wrapper that enforces the qualified flow_media contract on
    the exact staged bytes before any receipt or Asset can exist.

    The wrapper is runtime-owned: caller-created evidence never enters the
    acquisition path, and the parsed provider resource is bound to the actual
    downloaded bytes with ``bind_media_bytes`` before persistence can happen.
    """

    def __init__(self, transport, resource):
        self._transport = transport
        self._resource = resource
        self.media = None

    async def fetch(self, job, output_id, destination):
        result = await self._transport.fetch(job, output_id, destination)
        data = Path(result).read_bytes()
        self.media = bind_media_bytes(self._resource, data=data,
            response_url=self._resource.url, status=200,
            headers={'content-type': self._resource.mime_type,
                     'content-length': str(self._resource.byte_size)})
        return result


def compile_plan(shot: ShotSpec, capabilities: ProviderCapabilities,
                 reference) -> PromptPlan:
    from .compiler import compile_prompt
    return compile_prompt(shot, capabilities,
                          reference_hashes={reference.asset_id: reference.sha256})
