"""Deterministic provider adaptation tests. All sessions are offline doubles."""
import copy
import json
from pathlib import Path
from unittest.mock import Mock

import pytest

from film_pipeline.compiler import compile_prompt
from film_pipeline.core import canonical_json, load_shot, sha256
from film_pipeline.dispatch_evidence import recovery_decision, validate_fact
from film_pipeline.providers import flow_rpc_contract as contract
from film_pipeline.providers.flow_r2v_prompt import compile_flow_r2v_prompt, film_marker, VERSION
from film_pipeline.providers.flow_reference_rpc import FlowReferenceRpcSession, FlowReferenceRpcDrift
from film_pipeline.providers.flow_reference_upload import OwnerAmbiguityGate, ReferenceUploadStore
from film_pipeline.slice0011 import (ROOT, SHOT_A_PATH, SHOT_B_PATH, REFERENCE_ASSET_ID, REFERENCE_SHA256,
    PROJECT_ID, ACCOUNT_ID, reference_capabilities, freeze_reference, compile_character_paths,
    freeze_shot_job, submit_and_acquire_shot)
from film_pipeline.store import SQLiteStore

JOB = 'job_' + 'a' * 64
OTHER_JOB = 'job_' + 'b' * 64
REFERENCE = '53b5a413-7bb5-4f97-9be4-2461794a7d80'
OUTPUT = '99999999-8888-7777-6666-555555555555'
OTHER_OUTPUT = 'aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee'


def plan_for(path):
    return compile_prompt(load_shot(path), reference_capabilities(), reference_hashes={REFERENCE_ASSET_ID: REFERENCE_SHA256})


@pytest.mark.parametrize('path', [SHOT_A_PATH, SHOT_B_PATH])
def test_compact_prompt_deterministic_and_canonical_plan_unchanged(path):
    plan = plan_for(path)
    before, digest = canonical_json(plan), sha256(plan)
    adapted = compile_flow_r2v_prompt(plan, JOB)
    assert adapted == compile_flow_r2v_prompt(plan, JOB)
    assert canonical_json(plan) == before and sha256(plan) == digest
    assert adapted.canonical_plan_hash == digest
    assert len(adapted.text) < 1800 and len(adapted.text.split()) <= 240
    assert len(adapted.text) < len(plan.provider_prompt) / 2
    assert adapted.text.count('[FILM-') == 1 and adapted.text.endswith(film_marker(JOB))
    assert 'Execution correlation:' not in adapted.text and 'SHOT / DRAMATIC PURPOSE' not in adapted.text
    assert '{' not in adapted.text and 'asset_' not in adapted.text
    assert 'teal bob hair' in adapted.text and 'silver triangle earrings' in adapted.text
    second = compile_flow_r2v_prompt(plan, OTHER_JOB)
    assert second.text.rsplit('\n', 1)[0] == adapted.text.rsplit('\n', 1)[0]
    assert second.marker != adapted.marker


def test_compiler_rejects_missing_reference_and_creative_marker_collision_or_oversize():
    plan = plan_for(SHOT_A_PATH)
    wrong = plan.model_copy(deep=True)
    wrong.mapped_controls['image_input'] = []
    with pytest.raises(ValueError, match='IMAGE_INPUT'):
        compile_flow_r2v_prompt(wrong, JOB)
    wrong = plan.model_copy(deep=True)
    wrong.canonical_blocks['BLOCKING / START-END STATE']['blocking']['start'] = film_marker(OTHER_JOB)
    with pytest.raises(ValueError, match='MARKER_COLLISION'):
        compile_flow_r2v_prompt(wrong, JOB)
    wrong.canonical_blocks['BLOCKING / START-END STATE']['blocking']['start'] = 'long creative intent ' * 300
    with pytest.raises(ValueError, match='COMPACT_PROMPT_LIMIT'):
        compile_flow_r2v_prompt(wrong, JOB)


def test_provider_prompt_carries_nonredundant_performance_and_prop_intent():
    plan = plan_for(SHOT_A_PATH)
    plan.canonical_blocks['ACTION / PERFORMANCE']['performance']['observable_beats'].append('one restrained smile')
    plan.canonical_blocks['BLOCKING / START-END STATE']['blocking']['prop_interactions'] = ['touch the cup gently']
    before = canonical_json(plan)
    text = compile_flow_r2v_prompt(plan, JOB).text
    assert 'one restrained smile' in text and 'touch the cup gently' in text
    assert 'establish her stable identity and look' in text
    assert canonical_json(plan) == before


def row(prompt=None, output=OUTPUT):
    raw = json.loads((Path(__file__).parent / 'fixtures/flow_rpc_catalog_redacted.json').read_text())['record']
    replacements = {'OUTPUT': output, 'PROJECT': PROJECT_ID, 'REFERENCE': REFERENCE,
                    'MODEL': 'abra_r2v_8s', 'PROMPT': prompt or 'Normalized cinematic text. ' + film_marker(JOB)}
    def fill(value):
        if isinstance(value, list):
            return [fill(v) for v in value]
        return replacements.get(value, value) if isinstance(value, str) else value
    result = fill(raw)
    result[3] = 'CAE'
    return result


def match(rows, baseline=None):
    return contract.match_r2v_output(rows, PROJECT_ID, REFERENCE, JOB, baseline_ids=baseline or [])


def test_marker_plus_qualified_ownership_allows_normalized_prose_and_optional_lineage():
    record = row()
    record[5][6][2][0][2][0][0][0] = 'Another normalization. ' + film_marker(JOB)
    assert match([record]) == record
    record[5][6][2] = None
    record[7] = None
    assert match([record]) == record
    assert match([row('Unrelated text ' + film_marker(OTHER_JOB))]) is None


@pytest.mark.parametrize('defect,code', [
    ('reference', 'OUTPUT_REFERENCE_MISMATCH'), ('model', 'OUTPUT_MODEL_MISMATCH'),
    ('project', 'CATALOG_RECORD_PROJECT_MISMATCH'), ('primary_marker', 'OUTPUT_MARKER_SLOT_MISMATCH'),
    ('lineage_marker', 'OUTPUT_MARKER_SLOT_MISMATCH'), ('lineage_model', 'OUTPUT_LINEAGE_SLOT_MISMATCH'),
    ('lineage_output', 'OUTPUT_LINEAGE_SLOT_MISMATCH'), ('malformed_lineage', 'OUTPUT_LINEAGE_SHAPE_DRIFT'),
    ('image_record', 'OUTPUT_VIDEO_SHAPE_UNQUALIFIED'), ('status', 'OUTPUT_STATUS_UNQUALIFIED'),
    ('repeated_marker', 'OUTPUT_MARKER_SLOT_MISMATCH'), ('other_marker', 'OUTPUT_MARKER_SLOT_MISMATCH'),
])
def test_exact_reference_model_project_and_marker_slots_required(defect, code):
    record = row()
    if defect == 'reference': record[5][6][1][1][0][2] = OTHER_OUTPUT
    elif defect == 'model': record[5][6][1][0][0] = 't2v-model'
    elif defect == 'project': record[1] = OTHER_OUTPUT
    elif defect == 'primary_marker': record[5][1] = 'unmarked prompt'
    elif defect == 'lineage_marker': record[7][0][7] = film_marker(OTHER_JOB)
    elif defect == 'lineage_model': record[7][0][12] = 't2v-model'
    elif defect == 'lineage_output': record[7][2] = [OTHER_OUTPUT]
    elif defect == 'malformed_lineage': record[7] = []
    elif defect == 'image_record': record = record[:7]
    elif defect == 'status': record[3] = 'UNQUALIFIED'
    elif defect == 'repeated_marker': record[5][1] += film_marker(JOB)
    elif defect == 'other_marker': record[5][1] += film_marker(OTHER_JOB)
    with pytest.raises(contract.ContractError, match=code):
        match([record])


def test_metadata_marker_is_not_sufficient_for_ownership():
    record = row('unmarked prose')
    record[2] = film_marker(JOB)
    with pytest.raises(contract.ContractError, match='MARKER_SLOT'):
        match([record])


def test_collision_multiple_candidates_and_preexisting_identity_fail_closed():
    with pytest.raises(contract.ContractError, match='MARKER_COLLISION'):
        match([row(), row(output=OTHER_OUTPUT)])
    unrelated = row(film_marker(OTHER_JOB), OTHER_OUTPUT)
    unrelated[2] = film_marker(JOB)  # Even an unqualified second collision blocks selection.
    with pytest.raises(contract.ContractError, match='MARKER_COLLISION'):
        match([row(), unrelated])
    with pytest.raises(contract.ContractError, match='IDENTITY_COLLISION'):
        match([row(), row()])
    with pytest.raises(contract.ContractError, match='PREEXISTING'):
        match([row()], [OUTPUT])
    with pytest.raises(contract.ContractError, match='BASELINE_INVALID'):
        match([row()], ['invalid'])


@pytest.mark.parametrize('reference_entries', [
    [[None, 4, REFERENCE], [None, 4, OTHER_OUTPUT]],
    [[None, 4, REFERENCE], [None, 4, REFERENCE]],
    [[None, 4, REFERENCE, 'unqualified']], [[None, 1, REFERENCE]], [],
])
def test_single_exact_structured_reference_required(reference_entries):
    record = row()
    record[5][6][1][1] = reference_entries
    record[7] = None
    with pytest.raises(contract.ContractError, match='REFERENCE_MISMATCH'):
        match([record])


def framed(payload):
    return ")]}'\n" + json.dumps([['wrb.fr', 'MZZa6b', json.dumps(payload)]])


def test_diagnostics_shape_excludes_all_string_key_and_numeric_values():
    secret = 'secret_cookie_authorization_signed_url_dummy'
    text = framed({'private-key-' + secret: [secret, 12456, True, None]})
    observed = contract.submission_diagnostics(text)
    changed = contract.submission_diagnostics(framed({'different-key': ['different-value', 98765, False, None]}))
    assert observed['parsed'] and observed['advisory_only']
    assert observed['response_shape_hash'] == changed['response_shape_hash']
    assert observed['type_counts'] == {'null': 1, 'bool': 1, 'int': 1, 'float': 0, 'str': 1, 'list': 1, 'dict': 1}
    assert observed['response_bytes_len'] == len(text.encode('utf-8'))
    assert secret not in canonical_json(observed) and 'private-key' not in canonical_json(observed)
    assert 'accepted' not in observed and 'admitted' not in observed
    assert contract.submission_diagnostics(framed(None))['parsed']


def test_unparsed_diagnostic_never_hashes_or_persists_raw_body():
    first = contract.submission_diagnostics('secret_A_not_json')
    second = contract.submission_diagnostics('secret_B_not_json')
    assert first['parsed'] is False and first['advisory_only']
    assert first['type_counts'] == dict.fromkeys(first['type_counts'], 0)
    assert first['response_shape_hash'] == second['response_shape_hash']
    assert 'secret' not in canonical_json(first)


def prepared(tmp_path):
    database = tmp_path / 'runtime.sqlite'
    asset = freeze_reference(database, tmp_path / 'reference')
    paths = compile_character_paths(database)[2]
    reference_store = ReferenceUploadStore(database)
    reserved = reference_store.reserve_once('flow_veo', PROJECT_ID, ACCOUNT_ID, asset)
    reference_store.record_identified(reserved['id'], REFERENCE, method='offline_fixture', evidence_hash='1' * 64)
    receipt = reference_store.complete(reserved, REFERENCE, '2' * 64)
    session = Mock(project_id=PROJECT_ID, catalog_fingerprint=contract.QUALIFIED_BASELINE_FINGERPRINT)
    session.catalog.return_value = []
    job = freeze_shot_job(database, session, paths[0], receipt)
    return database, paths[0][1], session, job


def test_freeze_uses_compact_wire_prompt_preserving_stored_plan_and_job_immutability(tmp_path):
    database, plan, session, job = prepared(tmp_path)
    store = SQLiteStore(database)
    persisted = store.read_path(job.generation_attempt_id)[1]
    assert canonical_json(persisted) == canonical_json(plan)
    assert job.correlation_evidence['prompt'] == compile_flow_r2v_prompt(plan, job.provider_job_id).text
    assert job.correlation_evidence['prompt_plan_hash'] == sha256(plan)
    assert job.correlation_evidence['provider_prompt_compiler'] == VERSION
    with pytest.raises(ValueError, match='FROZEN_PROVIDER_INTENT_CHANGED'):
        store.save_provider_job(job.model_copy(update={'correlation_evidence': {
            **job.correlation_evidence, 'provider_prompt_compiler': 'legacy'}}))


@pytest.mark.parametrize('text,status', [(framed(None), 200), ('not-json secret_dummy', 200), (framed([1, 'secret_dummy']), 403)])
def test_submission_diagnostic_persisted_before_parse_or_http_failure_is_not_admission(tmp_path, text, status):
    database, plan, _, job = prepared(tmp_path)
    store = SQLiteStore(database)
    store.reserve_dispatch(job.provider_job_id)
    request_hash = job.correlation_evidence['rpc_request_hash']
    store.record_dispatch_fact(job.provider_job_id, 'RPC_REQUEST_ARMED',
        {'body_sha256': '3' * 64, 'request_hash': request_hash, 'contract': 'offline'})
    session = FlowReferenceRpcSession(cookie_path=Path('unused'), project_id=PROJECT_ID)
    session.captcha = Mock(return_value='secret_captcha_dummy')
    session.metadata = Mock(return_value={'source': '/project/' + PROJECT_ID, 'bl': 'secret_dummy',
        'sid': 'secret_dummy', 'hl': 'en', 'at': 'secret_dummy'})
    response = Mock(status=status)
    response.text.return_value = text
    session.page = Mock()
    session.page.context.request.post.return_value = response
    callback = lambda d: store.record_dispatch_fact(job.provider_job_id, 'R2V_RESPONSE_DIAGNOSTICS',
                                                    {'request_hash': request_hash, **d})
    options = {'before_post': lambda _: None, 'on_diagnostics': callback}
    if status == 200 and text == framed(None):
        session.submit_once(job.correlation_evidence['prompt'], REFERENCE, PROJECT_ID, **options)
    else:
        with pytest.raises(FlowReferenceRpcDrift):
            session.submit_once(job.correlation_evidence['prompt'], REFERENCE, PROJECT_ID, **options)
    facts = store.read_dispatch_facts(job.provider_job_id)
    diagnostic = next(f for f in facts if f['kind'] == 'R2V_RESPONSE_DIAGNOSTICS')['data']
    assert diagnostic['parsed'] == (text != 'not-json secret_dummy')
    assert 'secret_dummy' not in canonical_json(facts)
    assert b'secret_dummy' not in database.read_bytes()
    assert not any(f['kind'] == 'PROVIDER_ACCEPTANCE_OBSERVED' for f in facts)
    assert recovery_decision(store.read_provider_job(job.provider_job_id), facts).may_submit is False
    assert session.rpc_call_counts['MZZa6b'] == 1
    session.page.context.request.post.assert_called_once()


def test_large_type_counts_do_not_grant_admission_or_weaken_attribution(tmp_path):
    database, _, _, job = prepared(tmp_path)
    store = SQLiteStore(database)
    reserved = store.reserve_dispatch(job.provider_job_id)
    request_hash = job.correlation_evidence['rpc_request_hash']
    store.record_dispatch_fact(job.provider_job_id, 'RPC_REQUEST_ARMED',
        {'body_sha256': '3' * 64, 'request_hash': request_hash, 'contract': 'offline'})
    diagnostics = contract.submission_diagnostics(framed(['many strings'] * 100))
    store.record_dispatch_fact(job.provider_job_id, 'R2V_RESPONSE_DIAGNOSTICS', {'request_hash': request_hash, **diagnostics})
    facts = store.read_dispatch_facts(job.provider_job_id)
    decision = recovery_decision(reserved, facts)
    assert decision.classification == 'INCONCLUSIVE' and decision.strength == 4 and not decision.may_submit
    assert store.read_output_bindings(job.provider_job_id) == []
    assert contract.match_r2v_output([], PROJECT_ID, REFERENCE, job.provider_job_id, baseline_ids=[]) is None
    with pytest.raises(ValueError, match='ADVISORY'):
        validate_fact('R2V_RESPONSE_DIAGNOSTICS', {'request_hash': request_hash, **diagnostics, 'advisory_only': False})
    with pytest.raises(ValueError, match='BINDING'):
        store.record_dispatch_fact(job.provider_job_id, 'R2V_RESPONSE_DIAGNOSTICS', {'request_hash': '4' * 64, **diagnostics})


def test_future_submit_journals_diagnostics_but_stops_without_owned_output(tmp_path):
    database, _, session, job = prepared(tmp_path)
    session.catalog.return_value = []
    def submit(prompt, reference, request_id, *, before_post, on_diagnostics):
        before_post('3' * 64)
        on_diagnostics(contract.submission_diagnostics(framed(['admission-looking text'] * 100)))
    session.submit_once.side_effect = submit
    with pytest.raises(OwnerAmbiguityGate, match='no redispatch'):
        submit_and_acquire_shot(database, session, job, tmp_path / 'video', poll_seconds=0)
    store = SQLiteStore(database)
    facts = store.read_dispatch_facts(job.provider_job_id)
    diagnostic = next(f for f in facts if f['kind'] == 'R2V_RESPONSE_DIAGNOSTICS')
    assert diagnostic['data']['type_counts']['str'] == 100
    assert any(f['kind'] == 'PROVIDER_RESPONSE_OBSERVED' for f in facts)
    assert not any(f['kind'] == 'PROVIDER_ACCEPTANCE_OBSERVED' for f in facts)
    assert store.read_output_bindings(job.provider_job_id) == []
    assert store.read_provider_job(job.provider_job_id).dispatch_count == 1
    session.submit_once.assert_called_once()
