"""Offline render-lifecycle lifecycle proofs for the productized Flow R2V route.

Covers the SoT-required separation between admission, render pending/completed
and admitted-render-dropped:

- an as29s miss while the owned row is still present is RENDER_PENDING —
  pending evidence, never failure and never retry authority;
- a null as29s payload with the owned row absent from a qualified fresh
  catalog read is ADMITTED_RENDER_DROPPED — routed to an Owner repair
  decision, never to redispatch;
- any unqualified read is RENDER_UNOBSERVABLE and never invents a drop;
- restart cannot redispatch consumed authority in any render state.

Every provider behavior is a frozen/synthetic local double. No live provider
access, mutation, upload, or read exists in this module.
"""
import pytest

from film_pipeline.dispatch_evidence import recovery_decision
from film_pipeline.providers import flow_rpc_contract as contract
from film_pipeline.providers.flow_reference_rpc import (
    FlowReferenceRpcDrift,
    FlowReferenceRpcSession,
)
from film_pipeline.providers.flow_reference_upload import OwnerAmbiguityGate
from test_flow_r2v_boundary import OUTPUT_ID, video_row
from test_flow_r2v_runtime import (
    _offline_flow_catalog,
    own_output,
    release_request,
    reserve,
    runtime_env,
)


def patch_media_read(monkeypatch, behavior):
    """Patch the concrete as29s payload read; behavior is None/list/exception."""
    calls = []

    def media_payload(self, media_id):
        calls.append(media_id)
        if isinstance(behavior, Exception):
            raise behavior
        return behavior(media_id) if callable(behavior) else behavior

    monkeypatch.setattr(FlowReferenceRpcSession, 'media_payload', media_payload)
    return calls


def owned_job(env):
    """Drive the frozen job through reservation, release and owned output."""
    reserve(env)
    release_request(env)
    output_id, _row = own_output(env)
    assert output_id == OUTPUT_ID
    return output_id


def render_facts(env):
    return [f for f in env.store.read_dispatch_facts(env.frozen.job.provider_job_id)
            if f['kind'] in {'RENDER_PENDING_OBSERVED', 'RENDER_COMPLETED_OBSERVED',
                             'ADMITTED_RENDER_DROPPED'}]


def decision(env):
    job_id = env.frozen.job.provider_job_id
    return env.runtime.recovery(env.frozen)


# 1: media resolved → RENDER_COMPLETED with acquisition as the only action.
def test_render_completed_observed(runtime_env, monkeypatch):
    env = runtime_env
    output_id = owned_job(env)
    payload, _data = video_row(output_id)
    calls = patch_media_read(monkeypatch, payload)
    state = env.runtime.observe_render_state(env.frozen, session=env.session)
    assert state.state == 'RENDER_COMPLETED'
    assert state.output_id == output_id
    assert state.resource is not None and state.resource.media_id == output_id
    assert calls == [output_id]
    kinds = [f['kind'] for f in render_facts(env)]
    assert kinds == ['RENDER_COMPLETED_OBSERVED']
    recovered = decision(env)
    assert (recovered.classification, recovered.action) == ('RENDER_COMPLETED', 'ACQUIRE_ONLY')
    assert recovered.may_submit is False


# 2: as29s miss with the owned row present is RENDER_PENDING, never failure.
def test_render_pending_is_not_failure_and_not_retry_authority(runtime_env, monkeypatch):
    env = runtime_env
    output_id = owned_job(env)
    env.session._offline_rows = [[output_id, env.runtime.project_id, 'IMAGE',
                                  'CAE', None, None, None]]
    patch_media_read(monkeypatch, None)
    state = env.runtime.observe_render_state(env.frozen, session=env.session)
    assert state.state == 'RENDER_PENDING'
    recovered = decision(env)
    assert (recovered.classification, recovered.action) == ('RENDER_PENDING', 'RECONCILE_ONLY')
    assert recovered.may_submit is False
    # A restart of a consumed authority can never re-enter the mutation path.
    with pytest.raises(OwnerAmbiguityGate, match='ALREADY_CONSUMED'):
        reserve(env)
    fresh = env.runtime.recovery(env.frozen)
    assert fresh.action == 'RECONCILE_ONLY' and fresh.may_submit is False


# 3: null media with the owned row absent from the qualified read is a drop
#    routed to an Owner repair decision, never to redispatch.
def test_admitted_render_dropped_routes_to_repair(runtime_env, monkeypatch):
    env = runtime_env
    output_id = owned_job(env)
    env.session._offline_rows = []
    patch_media_read(monkeypatch, None)
    state = env.runtime.observe_render_state(env.frozen, session=env.session)
    assert state.state == 'ADMITTED_RENDER_DROPPED'
    recovered = decision(env)
    assert (recovered.classification, recovered.action) == (
        'ADMITTED_RENDER_DROPPED', 'REPAIR_DECISION_REQUIRED')
    assert recovered.may_submit is False
    with pytest.raises(OwnerAmbiguityGate, match='ALREADY_CONSUMED'):
        reserve(env)


# 4: a non-null as29s payload that fails the qualified media contract is
#    RENDER_UNOBSERVABLE — contract drift, never a drop and never completion.
def test_unqualified_media_payload_is_unobservable(runtime_env, monkeypatch):
    env = runtime_env
    output_id = owned_job(env)
    env.session._offline_rows = []
    patch_media_read(monkeypatch, [output_id, env.runtime.project_id, 'junk'])
    state = env.runtime.observe_render_state(env.frozen, session=env.session)
    assert state.state == 'RENDER_UNOBSERVABLE'
    failures = [f for f in env.store.read_dispatch_facts(env.frozen.job.provider_job_id)
                if f['kind'] == 'OBSERVATION_FAILURE']
    assert [f['data']['diagnostic'] for f in failures] == ['FLOW_R2V_MEDIA_PAYLOAD_UNQUALIFIED']
    assert render_facts(env) == []
    recovered = decision(env)
    assert (recovered.classification, recovered.action) == ('OUTPUT_BOUND', 'ACQUIRE_ONLY')


# 5: RPC drift is RENDER_UNOBSERVABLE and never invents a drop.
def test_rpc_drift_is_unobservable_not_dropped(runtime_env, monkeypatch):
    env = runtime_env
    output_id = owned_job(env)
    env.session._offline_rows = []  # would classify drop if the read were trusted
    patch_media_read(monkeypatch, FlowReferenceRpcDrift('FLOW_REFERENCE_RPC_READ_UNAVAILABLE'))
    state = env.runtime.observe_render_state(env.frozen, session=env.session)
    assert state.state == 'RENDER_UNOBSERVABLE'
    assert render_facts(env) == []
    failures = [f['data']['diagnostic'] for f in
                env.store.read_dispatch_facts(env.frozen.job.provider_job_id)
                if f['kind'] == 'OBSERVATION_FAILURE']
    assert failures == ['FLOW_REFERENCE_RPC_READ_UNAVAILABLE']


# 6: the render read source must be an exact qualified session for the project.
def test_unqualified_render_source_fails_closed(runtime_env, monkeypatch):
    import pathlib

    env = runtime_env
    owned_job(env)
    patch_media_read(monkeypatch, None)
    offline_profile = pathlib.Path('offline-unused')

    class LookAlike:
        project_id = env.runtime.project_id

    with pytest.raises(OwnerAmbiguityGate, match='RENDER_SOURCE_UNQUALIFIED'):
        env.runtime.observe_render_state(env.frozen, session=LookAlike())
    subclass = FlowReferenceRpcSession(profile_path=offline_profile,
                                       project_id=env.runtime.project_id)
    subclass.__class__ = type('QualifiedSub', (FlowReferenceRpcSession,), {})
    with pytest.raises(OwnerAmbiguityGate, match='RENDER_SOURCE_UNQUALIFIED'):
        env.runtime.observe_render_state(env.frozen, session=subclass)
    other_project = FlowReferenceRpcSession(
        profile_path=offline_profile, project_id='22222222-2222-3333-4444-555555555555')
    with pytest.raises(OwnerAmbiguityGate, match='RENDER_SOURCE_PROJECT_MISMATCH'):
        env.runtime.observe_render_state(env.frozen, session=other_project)


# 7: render observation requires exactly one durably owned output.
def test_render_observation_requires_unique_bound_output(runtime_env, monkeypatch):
    env = runtime_env
    patch_media_read(monkeypatch, None)
    reserve(env)
    release_request(env)
    with pytest.raises(OwnerAmbiguityGate, match='OUTPUT_NOT_UNIQUE'):
        env.runtime.observe_render_state(env.frozen, session=env.session)
    assert render_facts(env) == []


# 8: identical re-observation dedupes; a pending → completed transition appends
#    and upgrades the recovery classification.
def test_reobservation_idempotent_and_transition_appends(runtime_env, monkeypatch):
    env = runtime_env
    output_id = owned_job(env)
    env.session._offline_rows = [[output_id, env.runtime.project_id, 'IMAGE',
                                  'CAE', None, None, None]]
    patch_media_read(monkeypatch, None)
    first = env.runtime.observe_render_state(env.frozen, session=env.session)
    second = env.runtime.observe_render_state(env.frozen, session=env.session)
    assert (first.state, second.state) == ('RENDER_PENDING', 'RENDER_PENDING')
    assert [f['kind'] for f in render_facts(env)] == ['RENDER_PENDING_OBSERVED']
    payload, _data = video_row(output_id)
    monkeypatch.setattr(FlowReferenceRpcSession, 'media_payload',
                        lambda self, media_id: payload)
    third = env.runtime.observe_render_state(env.frozen, session=env.session)
    assert third.state == 'RENDER_COMPLETED'
    assert [f['kind'] for f in render_facts(env)] == ['RENDER_PENDING_OBSERVED',
                                                      'RENDER_COMPLETED_OBSERVED']
    assert decision(env).classification == 'RENDER_COMPLETED'


# 9: a durable drop stays terminal in recovery even if a later observation
#    claims completion — a flapping catalog is drift, not redispatch authority.
def test_drop_is_terminal_in_recovery(runtime_env, monkeypatch):
    env = runtime_env
    output_id = owned_job(env)
    env.session._offline_rows = []
    patch_media_read(monkeypatch, None)
    assert env.runtime.observe_render_state(env.frozen, session=env.session).state == \
        'ADMITTED_RENDER_DROPPED'
    payload, _data = video_row(output_id)
    monkeypatch.setattr(FlowReferenceRpcSession, 'media_payload',
                        lambda self, media_id: payload)
    assert env.runtime.observe_render_state(env.frozen, session=env.session).state == \
        'RENDER_COMPLETED'
    recovered = decision(env)
    assert (recovered.classification, recovered.action) == (
        'ADMITTED_RENDER_DROPPED', 'REPAIR_DECISION_REQUIRED')
    assert recovered.may_submit is False


# 10: catalog baseline drift while media is unresolved is UNOBSERVABLE.
def test_catalog_drift_is_unobservable(runtime_env, monkeypatch):
    env = runtime_env
    owned_job(env)
    patch_media_read(monkeypatch, None)

    def drifting_catalog(self, *, contract_version=contract.CONTRACT_VERSION):
        self.catalog_fingerprint = 'unqualified-drift'

    monkeypatch.setattr(FlowReferenceRpcSession, 'catalog', drifting_catalog)
    state = env.runtime.observe_render_state(env.frozen, session=env.session)
    assert state.state == 'RENDER_UNOBSERVABLE'
    failures = [f['data']['diagnostic'] for f in
                env.store.read_dispatch_facts(env.frozen.job.provider_job_id)
                if f['kind'] == 'OBSERVATION_FAILURE']
    assert failures == ['FLOW_R2V_CATALOG_BASELINE_DRIFT']
    assert render_facts(env) == []


# 11: structural guard — the productized seam references no direct/private
#     mutation path. The only Generate-mutation authority is the native-UI
#     browser request; direct MZZa6b construction stays outside the seam.
def test_production_seam_never_references_direct_mutation_path():
    import inspect

    from film_pipeline import flow_r2v_boundary, flow_r2v_runtime
    for module in (flow_r2v_boundary, flow_r2v_runtime):
        source = inspect.getsource(module)
        assert 'submit_once' not in source, module.__name__
        assert 'MZZa6b' not in source, module.__name__
        assert 'RPC_VIDEO' not in source, module.__name__
        assert 'build_video' not in source, module.__name__


# 12: fresh-process restart while RENDER_PENDING keeps reconcile-only and
#     never re-arms the consumed dispatch budget.
def test_restart_during_render_pending_stays_reconcile_only(runtime_env, monkeypatch):
    import sqlite3

    from film_pipeline.flow_r2v_runtime import FlowR2VShotRuntime
    env = runtime_env
    owned_job(env)
    env.session._offline_rows = [[OUTPUT_ID, env.runtime.project_id, 'IMAGE',
                                  'CAE', None, None, None]]
    patch_media_read(monkeypatch, None)
    assert env.runtime.observe_render_state(env.frozen, session=env.session).state == \
        'RENDER_PENDING'
    # Simulate a fresh process: a brand-new runtime over the same durable store.
    restarted = FlowR2VShotRuntime(env.store, project_id=env.runtime.project_id,
                                   account_id=env.runtime.account_id)
    decision = restarted.recovery(env.frozen)
    assert (decision.classification, decision.action) == ('RENDER_PENDING', 'RECONCILE_ONLY')
    assert decision.may_submit is False
    with pytest.raises(OwnerAmbiguityGate, match='ALREADY_CONSUMED'):
        restarted.reserve(env.frozen, attestation=env.attestation,
                          evidence_dir=env.attestation_dir)


# 13: fresh-process restart after a durable drop routes to a repair decision
#     and can never re-enter the mutation path.
def test_restart_after_drop_routes_to_repair(runtime_env, monkeypatch):
    from film_pipeline.flow_r2v_runtime import FlowR2VShotRuntime
    env = runtime_env
    owned_job(env)
    env.session._offline_rows = []
    patch_media_read(monkeypatch, None)
    assert env.runtime.observe_render_state(env.frozen, session=env.session).state == \
        'ADMITTED_RENDER_DROPPED'
    restarted = FlowR2VShotRuntime(env.store, project_id=env.runtime.project_id,
                                   account_id=env.runtime.account_id)
    decision = restarted.recovery(env.frozen)
    assert (decision.classification, decision.action) == (
        'ADMITTED_RENDER_DROPPED', 'REPAIR_DECISION_REQUIRED')
    assert decision.may_submit is False
    with pytest.raises(OwnerAmbiguityGate, match='ALREADY_CONSUMED'):
        reserve(env)


# 14: the dispatch journal is tamper-proof at the database level — a render
#     fact cannot be modified or deleted in place.
def test_render_fact_tamper_breaks_journal_integrity(runtime_env, monkeypatch):
    import sqlite3

    env = runtime_env
    owned_job(env)
    env.session._offline_rows = [[OUTPUT_ID, env.runtime.project_id, 'IMAGE',
                                  'CAE', None, None, None]]
    patch_media_read(monkeypatch, None)
    env.runtime.observe_render_state(env.frozen, session=env.session)
    job_id = env.frozen.job.provider_job_id
    with sqlite3.connect(env.store.path) as connection:
        row = connection.execute(
            "SELECT payload FROM dispatch_journal WHERE job_id=? AND kind=?",
            (job_id, 'RENDER_PENDING_OBSERVED')).fetchone()
        assert row is not None
        tampered = row[0].replace('as29s_null_media_row_present', 'tampered_basis')
        with pytest.raises(sqlite3.IntegrityError):
            connection.execute(
                "UPDATE dispatch_journal SET payload=? WHERE job_id=? AND kind=?",
                (tampered, job_id, 'RENDER_PENDING_OBSERVED'))
        with pytest.raises(sqlite3.IntegrityError):
            connection.execute(
                "DELETE FROM dispatch_journal WHERE job_id=? AND kind=?",
                (job_id, 'RENDER_PENDING_OBSERVED'))
    # The untouched journal still reads back exactly.
    kinds = [f['kind'] for f in env.store.read_dispatch_facts(job_id)]
    assert 'RENDER_PENDING_OBSERVED' in kinds
