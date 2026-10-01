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
from .providers.flow_media import BoundMedia
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
    return FlowR2VPrompt(body + '\n' + marker, marker, sha256(plan),
                         version=COMPACT_VERSION, model=model)


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


def _require_reference_binding(job, intent: MutationIntent) -> dict:
    """The frozen reference binding must match the intent reference exactly."""
    binding = job.correlation_evidence.get('reference_binding')
    if not isinstance(binding, dict) or binding.get('media_id') != intent.reference_media_id:
        raise OwnerAmbiguityGate('FLOW_R2V_REFERENCE_BINDING_MISMATCH')
    if not isinstance(binding.get('asset_id'), str) or not binding.get('asset_id'):
        raise OwnerAmbiguityGate('FLOW_R2V_REFERENCE_BINDING_MISMATCH')
    return binding


class FlowR2VShotRuntime:
    """Composition point for one reference-conditioned Flow R2V shot."""

    def __init__(self, store: SQLiteStore, *, project_id: str, account_id: str,
                 model: str = contract.MODEL_VEO_3_1_LITE):
        self.store = store
        self.project_id = project_id
        self.account_id = account_id
        self.model = model
        self.boundary = FlowR2VBoundary(store, project_id=project_id,
                                        account_id=account_id)
        # Deterministic provider-project binding identity, derived only from
        # the provider project id; identical to the historical derivation.
        self.project_binding_id = sha256(project_id)

    # --- Freeze -------------------------------------------------------------

    def _existing_job_for_shot(self, shot_id: str):
        """A restart resumes the same job; it cannot create another attempt."""
        with sqlite3.connect(self.store.path) as connection:
            attempts = [row[0] for row in connection.execute(
                "SELECT id FROM generation_attempts WHERE json_extract(payload,'$.shot_id')=?",
                (shot_id,)).fetchall()]
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

    def freeze(self, shot: ShotSpec, capabilities: ProviderCapabilities, *,
               reference_asset, reference_media_id: str, reference_filename: str = '',
               baseline_catalog_ids: list[str] | tuple = (),
               baseline_fingerprint: str = contract.QUALIFIED_BASELINE_FINGERPRINT,
               started_at: str | None = None) -> FrozenR2VShot:
        """Compile, route and freeze one ordinary R2V shot into a ProviderJob
        whose exact submission prompt is durable before any authority exists.
        A restart with identical inputs returns the same frozen job."""
        contract._uuid(reference_media_id, 'REFERENCE_ID_INVALID')
        if baseline_fingerprint != contract.QUALIFIED_BASELINE_FINGERPRINT:
            raise OwnerAmbiguityGate('FLOW_R2V_CATALOG_BASELINE_DRIFT')
        baseline = sorted({value.lower() for value in baseline_catalog_ids})
        for value in baseline:
            contract._uuid(value, 'OUTPUT_BASELINE_INVALID')
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

        prior = self._existing_job_for_shot(shot.shot_id)
        if prior is not None:
            return self._resume_frozen(prior, shot, plan, decision, reference_binding)
        snapshot = {'catalog_ids': baseline, 'catalog_fingerprint': baseline_fingerprint,
                    'project_id': self.project_id}
        preview = make_provider_job(attempt, project_binding_id=self.project_binding_id,
                                    pre_dispatch_snapshot=snapshot)
        compiled = compact_r2v_prompt(plan, preview.provider_job_id, model=self.model)
        prompt = compiled.text
        job = preview.model_copy(update={'correlation_evidence': {
            'prompt': prompt, 'prompt_plan_hash': sha256(plan),
            'submission_prompt_hash': sha256(prompt),
            'correlation_marker': compiled.marker,
            'provider_prompt_compiler': compiled.version,
            'reference_binding': reference_binding}})
        self.store.save_path(shot, plan, decision, attempt)
        self.store.save_provider_job(job)
        if job.provider_job_id != preview.provider_job_id:
            raise ValueError('provider job identity changed during freeze')
        return self._frozen(job, stored_reference)

    def _resume_frozen(self, prior, shot, plan, decision, reference_binding):
        """Restart path: identical inputs must resume the identical frozen job."""
        old_shot, old_plan, old_route, _ = self.store.read_path(
            prior.generation_attempt_id)
        if (old_shot, old_plan, old_route) != (shot, plan, decision):
            raise OwnerAmbiguityGate('FLOW_R2V_RESTART_PATH_DIFFERS')
        if (prior.project_binding_id != self.project_binding_id
                or prior.correlation_evidence.get('reference_binding') != reference_binding):
            raise OwnerAmbiguityGate('FLOW_R2V_RESTART_INTENT_DIFFERS')
        if prior.correlation_evidence.get('prompt') != compact_r2v_prompt(
                old_plan, prior.provider_job_id, model=self.model).text:
            raise OwnerAmbiguityGate('FLOW_R2V_RESTART_PROMPT_DIFFERS')
        return self._frozen(prior, self.store.read_reference_asset(
            reference_binding['asset_id']))

    def _frozen(self, job, stored_reference) -> FrozenR2VShot:
        job = self.store.read_provider_job(job.provider_job_id)
        binding = job.correlation_evidence.get('reference_binding')
        intent = MutationIntent(project_id=self.project_id, account_id=self.account_id,
                                reference_media_id=binding.get('media_id')
                                if isinstance(binding, dict) else None, model=self.model)
        _require_reference_binding(job, intent)
        shot, plan, route, attempt = self.store.read_path(job.generation_attempt_id)
        return FrozenR2VShot(shot=shot, plan=plan, attempt=attempt, job=job,
                             intent=intent, reference_asset=stored_reference)

    # --- One mutation opportunity -------------------------------------------

    def reserve(self, frozen: FrozenR2VShot, *, attestation: dict, evidence_dir) -> object:
        """Verify the attested reference, then consume the one mutation budget."""
        job = self.store.read_provider_job(frozen.job.provider_job_id)
        binding = _require_reference_binding(job, frozen.intent)
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
        binding = _require_reference_binding(job, frozen.intent)
        baseline = list(job.pre_dispatch_snapshot.get('catalog_ids') or [])
        row = self.boundary.attribute_output(records, intent=frozen.intent,
            provider_job_id=job_id, baseline_ids=baseline,
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
                media: BoundMedia) -> Asset:
        """Reconcile from the exact binding, then acquire exact bytes.

        The boundary's media binding is a precondition: the owned output,
        project and kind must match, and the persisted Asset bytes must equal
        the bound bytes. Acquisition itself reuses the existing receipt,
        staging and atomic-promotion machinery untouched.
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
        if (not isinstance(media, BoundMedia)
                or media.evidence['media_id'] != output_id
                or media.evidence['project_id'] != self.project_id
                or media.evidence['kind'] != 'video'):
            raise OwnerAmbiguityGate('FLOW_R2V_MEDIA_EVIDENCE_MISMATCH')
        assets = asyncio.run(executor.download_assets(job_id, Path(destination_dir)))
        if len(assets) != 1 or assets[0].provider_asset_id != output_id:
            raise OwnerAmbiguityGate('FLOW_R2V_ACQUIRED_ASSET_MISMATCH')
        if assets[0].sha256 != media.evidence['sha256']:
            raise OwnerAmbiguityGate('FLOW_R2V_ACQUIRED_BYTES_DRIFT')
        return assets[0]

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


def compile_plan(shot: ShotSpec, capabilities: ProviderCapabilities,
                 reference) -> PromptPlan:
    from .compiler import compile_prompt
    return compile_prompt(shot, capabilities,
                          reference_hashes={reference.asset_id: reference.sha256})
