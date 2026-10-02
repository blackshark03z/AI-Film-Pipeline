"""Offline render-lifecycle proofs for the productized Flow R2V route.

Covers the SoT-required separation between admission, render pending/completed
and admitted-render-dropped, the TECH-LEAD PROVE HARDENING DELTA semantics:

- as29s payload recognition is deterministic and schema-specific: only the
  evidenced null pending form and the qualified completed media shape are
  recognized; every other payload is UNKNOWN → RENDER_UNOBSERVABLE (durable
  observation failure) — never pending, never terminal;
- terminal ADMITTED_RENDER_DROPPED requires BOTH the consecutive-observation
  threshold AND a minimum elapsed persistence window measured durably from
  the journal timestamp of the streak's first disappearance;
- row return resets the streak/window; completion evidence is never
  downgraded into a drop;
- restart cannot shorten the window; rapid polling can never manufacture
  terminality; every consumed-authority state keeps may_submit false.

No sleeps: observation times are pinned explicitly. Every provider behavior
is a frozen/synthetic local double. No live provider access, mutation,
upload, or read exists in this module.
"""
from datetime import datetime, timedelta, timezone

import pytest

from film_pipeline.dispatch_evidence import recovery_decision
from film_pipeline.flow_r2v_runtime import (
    AS29S_PAYLOAD_COMPLETED,
    AS29S_PAYLOAD_KNOWN_PENDING,
    AS29S_PAYLOAD_UNKNOWN,
    classify_as29s_payload,
)
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

T0 = "2026-10-02T12:00:00+00:00"


def at(seconds):
    return (datetime.fromisoformat(T0) + timedelta(seconds=seconds))\
        .isoformat().replace("+00:00", "+00:00")


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
            if f['kind'] in {'RENDER_PENDING_OBSERVED', 'RENDER_STATE_UNRESOLVED',
                             'RENDER_COMPLETED_OBSERVED', 'ADMITTED_RENDER_DROPPED'}]


def decision(env):
    return env.runtime.recovery(env.frozen)


def row_for(env, output_id):
    return [[output_id, env.runtime.project_id, 'IMAGE', 'CAE', None, None, None]]


def observe(env, monkeypatch, *, media, rows, at_time=None, threshold=None):
    """One observe_render_state call with controlled media/catalog/time."""
    env.session._offline_rows = rows
    patch_media_read(monkeypatch, media)
    kwargs = {'session': env.session}
    if at_time is not None:
        kwargs['observed_at'] = at_time
    if threshold is not None:
        env.runtime.RENDER_DROP_MIN_ELAPSED_SECONDS = threshold
    return env.runtime.observe_render_state(env.frozen, **kwargs)


def completed_payload(output_id):
    payload, _data = video_row(output_id)
    return payload


# ===========================================================================
# FIX 1 — deterministic as29s payload recognition
# ===========================================================================

def test_recognizer_only_accepts_evidenced_shapes():
    assert classify_as29s_payload(None, media_id=OUTPUT_ID,
                                  project_id=env_project()) == AS29S_PAYLOAD_KNOWN_PENDING
    assert classify_as29s_payload(completed_payload(OUTPUT_ID), media_id=OUTPUT_ID,
                                  project_id=env_project()) == AS29S_PAYLOAD_COMPLETED
    for unknown in ({'junk': True}, 'garbage-string', 42, [OUTPUT_ID] * 3,
                    completed_payload(OUTPUT_ID) + ['extra-slot']):
        assert classify_as29s_payload(unknown, media_id=OUTPUT_ID,
                                      project_id=env_project()) == AS29S_PAYLOAD_UNKNOWN


def env_project():
    return '11111111-2222-3333-4444-555555555555'


def test_known_null_pending_payload_classifies_pending(runtime_env, monkeypatch):
    env = runtime_env
    output_id = owned_job(env)
    state = observe(env, monkeypatch, media=None, rows=row_for(env, output_id),
                    at_time=T0)
    assert state.state == 'RENDER_PENDING'
    assert [f['kind'] for f in render_facts(env)] == ['RENDER_PENDING_OBSERVED']
    recovered = decision(env)
    assert (recovered.classification, recovered.action) == ('RENDER_PENDING', 'RECONCILE_ONLY')
    assert recovered.may_submit is False


def test_arbitrary_non_null_object_is_unobservable_not_pending(runtime_env, monkeypatch):
    env = runtime_env
    output_id = owned_job(env)
    for payload in ({'status': 'rendering'}, [output_id], 'pending-garbage', 42):
        state = observe(env, monkeypatch, media=payload, rows=row_for(env, output_id),
                        at_time=T0)
        assert state.state == 'RENDER_UNOBSERVABLE'
    assert render_facts(env) == []
    failures = [f['data']['diagnostic'] for f in
                env.store.read_dispatch_facts(env.frozen.job.provider_job_id)
                if f['kind'] == 'OBSERVATION_FAILURE']
    # Identical observation failures dedupe in the immutable journal.
    assert failures == ['FLOW_R2V_MEDIA_PAYLOAD_UNQUALIFIED']


def test_superficially_similar_but_invalid_shape_is_unobservable(runtime_env, monkeypatch):
    """The live-observed class of pending-looking payloads (right length,
    right id slots, drifted inner structure) is UNKNOWN, never pending."""
    env = runtime_env
    output_id = owned_job(env)
    payload, _data = video_row(output_id)
    payload[3] = 'RENDERING'  # status slot drift; identity slots intact
    state = observe(env, monkeypatch, media=payload, rows=row_for(env, output_id),
                    at_time=T0)
    assert state.state == 'RENDER_UNOBSERVABLE'
    payload2, _data2 = video_row(output_id)
    payload2[7][0][8] = 'https://flow-content.google/video/other-id'
    state = observe(env, monkeypatch, media=payload2, rows=row_for(env, output_id),
                    at_time=T0)
    assert state.state == 'RENDER_UNOBSERVABLE'
    assert render_facts(env) == []


def test_restart_after_unknown_payload_still_blocks_submission(runtime_env, monkeypatch):
    from film_pipeline.flow_r2v_runtime import FlowR2VShotRuntime
    env = runtime_env
    owned_job(env)
    observe(env, monkeypatch, media={'unknown': 1}, rows=[], at_time=T0)
    restarted = FlowR2VShotRuntime(env.store, project_id=env.runtime.project_id,
                                   account_id=env.runtime.account_id)
    recovered = restarted.recovery(env.frozen)
    assert (recovered.classification, recovered.action) == (
        'OUTPUT_BOUND_UNOBSERVED', 'RECONCILE_RENDER_STATE')
    assert recovered.may_submit is False
    with pytest.raises(OwnerAmbiguityGate, match='ALREADY_CONSUMED'):
        reserve(env)


def test_unknown_payload_cannot_append_completed_or_dropped(runtime_env, monkeypatch):
    env = runtime_env
    output_id = owned_job(env)
    # A burst of unknown payloads combined with catalog absence must neither
    # complete nor drop the output.
    for seconds in (0, 60, 120, 600, 100000):
        observe(env, monkeypatch, media={'unknown': seconds}, rows=[],
                at_time=at(seconds))
    kinds = [f['kind'] for f in render_facts(env)]
    assert 'RENDER_COMPLETED_OBSERVED' not in kinds
    assert 'ADMITTED_RENDER_DROPPED' not in kinds
    recovered = decision(env)
    assert (recovered.classification, recovered.action) == (
        'OUTPUT_BOUND_UNOBSERVED', 'RECONCILE_RENDER_STATE')


# ===========================================================================
# FIX 2 — temporal persistence policy for terminal render drop
# ===========================================================================

def test_disappearances_one_and_two_stay_unresolved(runtime_env, monkeypatch):
    env = runtime_env
    output_id = owned_job(env)
    first = observe(env, monkeypatch, media=None, rows=[], at_time=T0)
    second = observe(env, monkeypatch, media=None, rows=[], at_time=at(60))
    assert (first.state, second.state) == ('RENDER_STATE_UNRESOLVED',
                                           'RENDER_STATE_UNRESOLVED')
    kinds = [f['kind'] for f in render_facts(env)]
    assert kinds == ['RENDER_STATE_UNRESOLVED', 'RENDER_STATE_UNRESOLVED']
    assert decision(env).may_submit is False


def test_threshold_inside_minimum_window_is_still_unresolved(runtime_env, monkeypatch):
    env = runtime_env
    output_id = owned_job(env)
    states = [observe(env, monkeypatch, media=None, rows=[], at_time=at(s))
              for s in (0, 60, 120)]
    assert all(s.state == 'RENDER_STATE_UNRESOLVED' for s in states)
    assert decision(env).may_submit is False
    kinds = [f['kind'] for f in render_facts(env)]
    assert kinds == ['RENDER_STATE_UNRESOLVED'] * 3


def test_threshold_plus_minimum_elapsed_window_terminal_drop(runtime_env, monkeypatch):
    env = runtime_env
    output_id = owned_job(env)
    for seconds in (0, 60):
        observe(env, monkeypatch, media=None, rows=[], at_time=at(seconds))
    final = observe(env, monkeypatch, media=None, rows=[], at_time=at(900))
    # Candidate count 3 AND elapsed 900 s >= the configured window.
    assert final.state == 'ADMITTED_RENDER_DROPPED'
    recovered = decision(env)
    assert (recovered.classification, recovered.action) == (
        'ADMITTED_RENDER_DROPPED', 'REPAIR_DECISION_REQUIRED')
    assert recovered.may_submit is False
    with pytest.raises(OwnerAmbiguityGate, match='ALREADY_CONSUMED'):
        reserve(env)


def test_production_minimum_window_is_conservative(runtime_env):
    assert runtime_env.runtime.RENDER_DROP_PERSISTENCE_THRESHOLD == 3
    assert runtime_env.runtime.RENDER_DROP_MIN_ELAPSED_SECONDS == 900


def test_restart_preserves_durable_timing(runtime_env, monkeypatch):
    from film_pipeline.flow_r2v_runtime import FlowR2VShotRuntime
    env = runtime_env
    output_id = owned_job(env)
    observe(env, monkeypatch, media=None, rows=[], at_time=T0)
    observe(env, monkeypatch, media=None, rows=[], at_time=at(60))
    restarted = FlowR2VShotRuntime(env.store, project_id=env.runtime.project_id,
                                   account_id=env.runtime.account_id)
    state = observe(env, monkeypatch, media=None, rows=[], at_time=at(120))
    assert state.state == 'RENDER_STATE_UNRESOLVED'
    # A post-restart process cannot shorten the window: the streak's durable
    # first-disappearance timestamp governs.
    final = observe(env, monkeypatch, media=None, rows=[], at_time=at(900))
    assert final.state == 'ADMITTED_RENDER_DROPPED'
    assert restarted.recovery(env.frozen).may_submit is False


def test_row_return_resets_streak_and_window(runtime_env, monkeypatch):
    env = runtime_env
    output_id = owned_job(env)
    observe(env, monkeypatch, media=None, rows=[], at_time=T0)
    observe(env, monkeypatch, media=None, rows=[], at_time=at(60))
    returned = observe(env, monkeypatch, media=None,
                       rows=row_for(env, output_id), at_time=at(120))
    assert returned.state == 'RENDER_PENDING'
    again = observe(env, monkeypatch, media=None, rows=[], at_time=at(180))
    # A new persistence interval: the fresh streak starts at 180 s.
    assert again.state == 'RENDER_STATE_UNRESOLVED'
    kinds = [f['kind'] for f in render_facts(env)]
    assert kinds == ['RENDER_STATE_UNRESOLVED', 'RENDER_STATE_UNRESOLVED',
                     'RENDER_PENDING_OBSERVED', 'RENDER_STATE_UNRESOLVED']


def test_disappearance_after_row_return_starts_new_interval(runtime_env, monkeypatch):
    env = runtime_env
    output_id = owned_job(env)
    observe(env, monkeypatch, media=None, rows=[], at_time=T0)
    observe(env, monkeypatch, media=None, rows=row_for(env, output_id), at_time=at(30))
    # Even a huge gap after a row return cannot satisfy the new interval's
    # window without new disappearance observations.
    late = observe(env, monkeypatch, media=None, rows=[], at_time=at(100000))
    assert late.state == 'RENDER_STATE_UNRESOLVED'
    kinds = [f['kind'] for f in render_facts(env)]
    assert kinds == ['RENDER_STATE_UNRESOLVED', 'RENDER_PENDING_OBSERVED',
                     'RENDER_STATE_UNRESOLVED']


def test_unqualified_read_neither_advances_nor_breaks_streak(runtime_env, monkeypatch):
    env = runtime_env
    output_id = owned_job(env)
    observe(env, monkeypatch, media=None, rows=[], at_time=T0)
    drifted = observe(env, monkeypatch, media={'drift': 1}, rows=[],
                      at_time=at(400))
    assert drifted.state == 'RENDER_UNOBSERVABLE'
    resolved = observe(env, monkeypatch, media=None, rows=[], at_time=at(450))
    assert resolved.state == 'RENDER_STATE_UNRESOLVED'
    kinds = [f['kind'] for f in render_facts(env)]
    # The unqualified read added no disappearance datapoint and no window time;
    # the streak's durable first disappearance (T0) still governs.
    assert kinds == ['RENDER_STATE_UNRESOLVED', 'RENDER_STATE_UNRESOLVED']
    final = observe(env, monkeypatch, media=None, rows=[], at_time=at(900))
    assert final.state == 'ADMITTED_RENDER_DROPPED'


def test_unknown_schema_does_not_advance_drop_counter_or_window(runtime_env, monkeypatch):
    env = runtime_env
    output_id = owned_job(env)
    observe(env, monkeypatch, media=None, rows=[], at_time=T0)
    observe(env, monkeypatch, media=None, rows=[], at_time=at(60))
    unknown = observe(env, monkeypatch, media={'schema': 'drifted'}, rows=[],
                      at_time=at(120))
    assert unknown.state == 'RENDER_UNOBSERVABLE'
    # The unknown observation added no disappearance datapoint and no window
    # time: the streak is still 2 and its first disappearance is still T0.
    final = observe(env, monkeypatch, media=None, rows=[], at_time=at(900))
    # Count 2 (+1 = 3) meets the threshold; window measured T0 → 900 s.
    assert final.state == 'ADMITTED_RENDER_DROPPED'
    unresolved = [f for f in render_facts(env)
                  if f['kind'] == 'RENDER_STATE_UNRESOLVED']
    assert len(unresolved) == 2
    assert [f['at'] for f in unresolved] == [T0, at(60)]


def test_completion_before_threshold_prevents_drop(runtime_env, monkeypatch):
    env = runtime_env
    output_id = owned_job(env)
    observe(env, monkeypatch, media=None, rows=[], at_time=T0)
    observe(env, monkeypatch, media=None, rows=[], at_time=at(60))
    done = observe(env, monkeypatch, media=completed_payload(output_id),
                   rows=row_for(env, output_id), at_time=at(120))
    assert done.state == 'RENDER_COMPLETED'
    gone = observe(env, monkeypatch, media=None, rows=[], at_time=at(100000))
    # Completion evidence is never downgraded by a later disappearance.
    assert gone.state == 'RENDER_COMPLETED'
    recovered = decision(env)
    assert (recovered.classification, recovered.action) == ('RENDER_COMPLETED',
                                                            'ACQUIRE_ONLY')
    assert recovered.may_submit is False


def test_completion_after_unresolved_disappearance_remains_completion(
        runtime_env, monkeypatch):
    env = runtime_env
    output_id = owned_job(env)
    observe(env, monkeypatch, media=None, rows=[], at_time=T0)
    observe(env, monkeypatch, media=None, rows=[], at_time=at(60))
    dropped = observe(env, monkeypatch, media=None, rows=[], at_time=at(900))
    # Third disappearance at the 900 s boundary satisfies threshold + window.
    assert dropped.state == 'ADMITTED_RENDER_DROPPED'
    resolved = observe(env, monkeypatch, media=completed_payload(output_id),
                       rows=row_for(env, output_id), at_time=at(1100))
    assert resolved.state == 'RENDER_COMPLETED'
    recovered = decision(env)
    # Resolved media outranks the policy-derived drop.
    assert (recovered.classification, recovered.action) == ('RENDER_COMPLETED',
                                                            'ACQUIRE_ONLY')


def test_rapid_poll_burst_can_never_produce_terminal_drop(runtime_env, monkeypatch):
    env = runtime_env
    output_id = owned_job(env)
    for seconds in range(0, 30, 3):
        state = observe(env, monkeypatch, media=None, rows=[], at_time=at(seconds))
        assert state.state == 'RENDER_STATE_UNRESOLVED'
    kinds = [f['kind'] for f in render_facts(env)]
    assert 'ADMITTED_RENDER_DROPPED' not in kinds
    assert decision(env).may_submit is False


def test_journal_timestamp_tamper_remains_rejected(runtime_env, monkeypatch):
    import sqlite3

    env = runtime_env
    owned_job(env)
    observe(env, monkeypatch, media=None, rows=[], at_time=T0)
    connection = sqlite3.connect(env.store.path)
    with pytest.raises(sqlite3.IntegrityError):
        connection.execute(
            "UPDATE dispatch_journal SET at='1999-01-01T00:00:00+00:00' "
            "WHERE kind='RENDER_STATE_UNRESOLVED'")
    with pytest.raises(sqlite3.IntegrityError):
        connection.execute(
            "DELETE FROM dispatch_journal WHERE kind='RENDER_STATE_UNRESOLVED'")


def test_malformed_observation_time_fails_closed(runtime_env, monkeypatch):
    env = runtime_env
    output_id = owned_job(env)
    with pytest.raises(OwnerAmbiguityGate, match='OBSERVATION_TIME_INVALID'):
        observe(env, monkeypatch, media=None, rows=[], at_time='not-a-timestamp')
    with pytest.raises(OwnerAmbiguityGate, match='OBSERVATION_TIME_INVALID'):
        observe(env, monkeypatch, media=None, rows=[],
                at_time='2026-10-02T12:00:00')


# ===========================================================================
# Prior invariants (kept green under the new semantics)
# ===========================================================================

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
    assert [f['kind'] for f in render_facts(env)] == ['RENDER_COMPLETED_OBSERVED']
    recovered = decision(env)
    assert (recovered.classification, recovered.action) == ('RENDER_COMPLETED', 'ACQUIRE_ONLY')
    assert recovered.may_submit is False


def test_render_pending_is_not_failure_and_not_retry_authority(runtime_env, monkeypatch):
    env = runtime_env
    output_id = owned_job(env)
    observe(env, monkeypatch, media=None, rows=row_for(env, output_id), at_time=T0)
    recovered = decision(env)
    assert (recovered.classification, recovered.action) == ('RENDER_PENDING', 'RECONCILE_ONLY')
    assert recovered.may_submit is False
    with pytest.raises(OwnerAmbiguityGate, match='ALREADY_CONSUMED'):
        reserve(env)


def test_unqualified_media_payload_is_unobservable(runtime_env, monkeypatch):
    env = runtime_env
    output_id = owned_job(env)
    observe(env, monkeypatch, media=[output_id, env.runtime.project_id, 'junk'],
            rows=[], at_time=T0)
    failures = [f['data']['diagnostic'] for f in
                env.store.read_dispatch_facts(env.frozen.job.provider_job_id)
                if f['kind'] == 'OBSERVATION_FAILURE']
    assert failures == ['FLOW_R2V_MEDIA_PAYLOAD_UNQUALIFIED']
    assert render_facts(env) == []
    recovered = decision(env)
    assert (recovered.classification, recovered.action) == (
        'OUTPUT_BOUND_UNOBSERVED', 'RECONCILE_RENDER_STATE')


def test_rpc_drift_is_unobservable_not_dropped(runtime_env, monkeypatch):
    env = runtime_env
    owned_job(env)
    patch_media_read(monkeypatch, FlowReferenceRpcDrift('FLOW_REFERENCE_RPC_READ_UNAVAILABLE'))
    state = env.runtime.observe_render_state(env.frozen, session=env.session)
    assert state.state == 'RENDER_UNOBSERVABLE'
    assert render_facts(env) == []
    failures = [f['data']['diagnostic'] for f in
                env.store.read_dispatch_facts(env.frozen.job.provider_job_id)
                if f['kind'] == 'OBSERVATION_FAILURE']
    assert failures == ['FLOW_REFERENCE_RPC_READ_UNAVAILABLE']


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


def test_render_observation_requires_unique_bound_output(runtime_env, monkeypatch):
    env = runtime_env
    patch_media_read(monkeypatch, None)
    reserve(env)
    release_request(env)
    with pytest.raises(OwnerAmbiguityGate, match='OUTPUT_NOT_UNIQUE'):
        env.runtime.observe_render_state(env.frozen, session=env.session)
    assert render_facts(env) == []


def test_reobservation_idempotent_and_transition_appends(runtime_env, monkeypatch):
    env = runtime_env
    output_id = owned_job(env)
    observe(env, monkeypatch, media=None, rows=row_for(env, output_id), at_time=T0)
    second = observe(env, monkeypatch, media=None, rows=row_for(env, output_id),
                     at_time=at(5))
    assert second.state == 'RENDER_PENDING'
    assert [f['kind'] for f in render_facts(env)] == ['RENDER_PENDING_OBSERVED']
    third = observe(env, monkeypatch, media=completed_payload(output_id),
                    rows=row_for(env, output_id), at_time=at(10))
    assert third.state == 'RENDER_COMPLETED'
    assert [f['kind'] for f in render_facts(env)] == ['RENDER_PENDING_OBSERVED',
                                                      'RENDER_COMPLETED_OBSERVED']
    assert decision(env).classification == 'RENDER_COMPLETED'


def test_catalog_drift_is_unobservable(runtime_env, monkeypatch):
    env = runtime_env
    owned_job(env)
    patch_media_read(monkeypatch, None)

    def drifting_catalog(self, *, contract_version=contract.CONTRACT_VERSION):
        self.catalog_fingerprint = 'unqualified-drift'

    monkeypatch.setattr(FlowReferenceRpcSession, 'catalog', drifting_catalog)
    state = env.runtime.observe_render_state(env.frozen, session=env.session,
                                             observed_at=T0)
    assert state.state == 'RENDER_UNOBSERVABLE'
    failures = [f['data']['diagnostic'] for f in
                env.store.read_dispatch_facts(env.frozen.job.provider_job_id)
                if f['kind'] == 'OBSERVATION_FAILURE']
    assert failures == ['FLOW_R2V_CATALOG_BASELINE_DRIFT']
    assert render_facts(env) == []


def test_production_seam_never_references_direct_mutation_path():
    import inspect

    from film_pipeline import flow_r2v_boundary, flow_r2v_runtime
    for module in (flow_r2v_boundary, flow_r2v_runtime):
        source = inspect.getsource(module)
        assert 'submit_once' not in source, module.__name__
        assert 'MZZa6b' not in source, module.__name__
        assert 'RPC_VIDEO' not in source, module.__name__
        assert 'build_video' not in source, module.__name__


def test_restart_during_render_pending_stays_reconcile_only(runtime_env, monkeypatch):
    from film_pipeline.flow_r2v_runtime import FlowR2VShotRuntime
    env = runtime_env
    owned_job(env)
    observe(env, monkeypatch, media=None, rows=row_for(env, output_id := OUTPUT_ID),
            at_time=T0)
    restarted = FlowR2VShotRuntime(env.store, project_id=env.runtime.project_id,
                                   account_id=env.runtime.account_id)
    recovered = restarted.recovery(env.frozen)
    assert (recovered.classification, recovered.action) == ('RENDER_PENDING', 'RECONCILE_ONLY')
    assert recovered.may_submit is False
    with pytest.raises(OwnerAmbiguityGate, match='ALREADY_CONSUMED'):
        restarted.reserve(env.frozen, attestation=env.attestation,
                          evidence_dir=env.attestation_dir)


def test_restart_after_drop_routes_to_repair(runtime_env, monkeypatch):
    from film_pipeline.flow_r2v_runtime import FlowR2VShotRuntime
    env = runtime_env
    owned_job(env)
    for seconds in (0, 60, 900):
        observe(env, monkeypatch, media=None, rows=[], at_time=at(seconds))
    restarted = FlowR2VShotRuntime(env.store, project_id=env.runtime.project_id,
                                   account_id=env.runtime.account_id)
    recovered = restarted.recovery(env.frozen)
    assert (recovered.classification, recovered.action) == (
        'ADMITTED_RENDER_DROPPED', 'REPAIR_DECISION_REQUIRED')
    assert recovered.may_submit is False
    with pytest.raises(OwnerAmbiguityGate, match='ALREADY_CONSUMED'):
        reserve(env)


def test_restart_after_render_completed_keeps_acquire_only(runtime_env, monkeypatch):
    from film_pipeline.flow_r2v_runtime import FlowR2VShotRuntime
    env = runtime_env
    output_id = owned_job(env)
    observe(env, monkeypatch, media=completed_payload(output_id),
            rows=row_for(env, output_id), at_time=T0)
    restarted = FlowR2VShotRuntime(env.store, project_id=env.runtime.project_id,
                                   account_id=env.runtime.account_id)
    recovered = restarted.recovery(env.frozen)
    assert (recovered.classification, recovered.action) == ('RENDER_COMPLETED', 'ACQUIRE_ONLY')
    assert recovered.may_submit is False
    with pytest.raises(OwnerAmbiguityGate, match='ALREADY_CONSUMED'):
        reserve(env)


def test_render_fact_tamper_breaks_journal_integrity(runtime_env, monkeypatch):
    import sqlite3

    env = runtime_env
    owned_job(env)
    observe(env, monkeypatch, media=None, rows=row_for(env, OUTPUT_ID), at_time=T0)
    job_id = env.frozen.job.provider_job_id
    connection = sqlite3.connect(env.store.path)
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
    kinds = [f['kind'] for f in env.store.read_dispatch_facts(job_id)]
    assert 'RENDER_PENDING_OBSERVED' in kinds
