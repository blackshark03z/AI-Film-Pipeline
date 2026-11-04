"""Offline regressions for the uploaded-image response observed on 2026-11-04."""
import copy
import json
from pathlib import Path

import pytest
from test_flow_r2v_runtime import runtime_env, _offline_flow_catalog

from film_pipeline.providers import flow_rpc_contract as c
from film_pipeline.providers.flow_media import bind_media_bytes, parse_media_resource
from film_pipeline.providers.flow_upload_classifier import (
    QUALIFIED_COMPLETED, TRUE_AMBIGUOUS, classify_upload_response,
)
from test_canonical_reference_binding import bound, PROJECT, REMOTE, OTHER


def uploaded_image():
    row, _, headers, media = bound()
    row[2], row[3], row[5][9] = OTHER, None, 1
    return row, headers, media


def test_uploaded_image_still_requires_exact_resource_and_bytes():
    row, headers, media = uploaded_image()
    assert c._validate_catalog_rows([row], PROJECT) == [row]
    resource = parse_media_resource(row, media_id=REMOTE, project_id=PROJECT, kind='image')
    assert bind_media_bytes(resource, data=media.data, response_url=resource.url,
                           status=200, headers=headers).evidence == media.evidence
    wrong = copy.deepcopy(row)
    wrong[6][1][3] = wrong[5][10] = f'https://flow-content.google/image/{OTHER}'
    with pytest.raises(c.ContractError):
        parse_media_resource(wrong, media_id=REMOTE, project_id=PROJECT, kind='image')
    with pytest.raises(c.ContractError):
        c._validate_catalog_rows([row + [[]]], PROJECT)  # Null-status video remains forbidden.
    row[5][9] = 0
    with pytest.raises(c.ContractError):
        c._validate_catalog_rows([row], PROJECT)


def test_library_header_is_not_a_second_media_identity_but_conflicts_still_stop():
    row, _, _ = uploaded_image()
    header = [OTHER, None, None, ['reference.png', [1, 0], None, None, REMOTE], PROJECT]
    request_id = '5db2a14f-f50a-508d-8232-9fd1041469be'
    result = classify_upload_response(200, [row, header], project_id=PROJECT, request_id=request_id)
    assert result.classification == QUALIFIED_COMPLETED
    broken = copy.deepcopy(header)
    broken[4] = OTHER
    result = classify_upload_response(200, [row, broken], project_id=PROJECT, request_id=request_id)
    assert result.classification == TRUE_AMBIGUOUS
    broken = copy.deepcopy(header)
    broken[3][4] = OTHER
    assert classify_upload_response(200, [row, broken], project_id=PROJECT,
                                    request_id=request_id).classification == TRUE_AMBIGUOUS


def test_fresh_runtime_budget_uses_persisted_job_schema(tmp_path):
    from film_pipeline.e2e_flow import remaining_budget
    from film_pipeline.store import SQLiteStore
    store = SQLiteStore(tmp_path / 'runtime.sqlite')
    store.initialize()
    assert remaining_budget(store, PROJECT) == 14


def test_observed_nullable_video_requires_full_lineage_and_exact_media_resource():
    from film_pipeline.flow_r2v_runtime import qualified_catalog_snapshot
    data = json.loads((Path(__file__).parent / 'fixtures/flow_null_media_20261104.json').read_text())
    row, media = data['row'], data['media']
    project, reference = row[1], row[5][6][1][1][0][2]
    job = 'job_b41f4039354983528a821f3b4b7948803488f93e4fbed4104de8b06ae5f95718'
    def match(value, baseline=None):
        return c.match_r2v_output_v2026_10_01([value], project, reference, '', job,
            baseline_ids=baseline or [reference], model=c.MODEL_VEO_3_1_LITE)
    assert match(row) == row
    assert qualified_catalog_snapshot([row], project_id=project,
        fingerprint=c.NULL_MEDIA_CATALOG_FINGERPRINT)['catalog_fingerprint'] == c.NULL_MEDIA_CATALOG_FINGERPRINT
    with pytest.raises(Exception):
        qualified_catalog_snapshot([row], project_id=project)
    resource = parse_media_resource(media, media_id=row[0], project_id=project, kind='video')
    assert resource.byte_size == 1724190
    with pytest.raises(c.ContractError):
        parse_media_resource(row, media_id=row[0], project_id=project, kind='video')  # Catalog thumbnail is not video.
    with pytest.raises(c.ContractError):
        match(row, [row[0]])
    for defect in ('status', 'size', 'reference', 'model', 'self_link', 'prompt'):
        bad = copy.deepcopy(row)
        if defect == 'status': bad[3] = 'PENDING'
        if defect == 'size': bad[5][13] = True
        if defect == 'reference': bad[5][6][1][1][0][2] = OTHER
        if defect == 'model': bad[7][0][12] = 'unknown'
        if defect == 'self_link': bad[7][2] = [OTHER]
        if defect == 'prompt': bad[5][1] = 'unrelated'
        with pytest.raises(c.ContractError):
            match(bad)


def test_restart_adoption_keeps_existing_asset_path_with_short_attestation_directory(tmp_path):
    from types import SimpleNamespace
    from test_reference_adoption import adopt, ACCOUNT
    from film_pipeline.providers.flow_reference_binding import adopt_existing_reference, verify_attestation
    store, (asset, _) = adopt(tmp_path)
    _, _, _, media = bound()
    session = SimpleNamespace(project_id=PROJECT, bound_media=lambda mid, kind: media)
    asset2, attestation = adopt_existing_reference(store, session, account_id=ACCOUNT,
        media_id=REMOTE, reference_dir=tmp_path / 'different', attestation_dir=tmp_path / 'short')
    assert asset2 == asset
    assert verify_attestation(store, asset2, attestation, media_id=REMOTE, project_id=PROJECT,
                              evidence_dir=tmp_path / 'short') == attestation


def test_same_shot_id_cannot_substitute_different_creative_intent():
    from film_pipeline.e2e import _require_planned_shot
    from film_pipeline.e2e_flow import shot_spec
    planned = {'shot_id': 'SHOT_01', 'visual_intent': 'Present badge', 'video_prompt': 'Raise one badge'}
    spec = shot_spec(planned, 'asset_reference')
    _require_planned_shot(spec, planned)
    with pytest.raises(ValueError, match='locked creative plan'):
        _require_planned_shot(spec, {**planned, 'video_prompt': 'Drop badge'})


def test_repair_is_changed_version_of_resolved_owner_rejection_not_a_replay(tmp_path, runtime_env, monkeypatch):
    from test_flow_r2v_runtime import (reserve, release_request, own_output, mp4_fixture,
        media_payload, FixtureAcquisitionTransport, flow_capabilities)
    from film_pipeline.qc import QCStore, technical_evidence, evidence, human_decision
    env = runtime_env
    reserve(env)
    release_request(env)
    output_id, row = own_output(env)
    data = mp4_fixture(tmp_path / 'repair_fixture.mp4')
    asset = env.runtime.acquire(env.frozen, transport=FixtureAcquisitionTransport(data),
        destination_dir=tmp_path / 'acquired', media_payload=media_payload(env, output_id, data))
    rows, _ = technical_evidence(env.shot, asset)
    for gate in ('visual', 'continuity', 'editorial'):
        rows.append(evidence(asset=asset, evaluator_type='temporal_heuristic', evaluator_version='fixture',
            gate=gate, criterion='unassessed', observation='Offline fixture only', verdict='uncertain'))
    human = human_decision(asset=asset, reviewer_id='fixture_owner', source='owner_explicit_review',
        action='REJECT', visual_pass=False, failure_codes=['PERFORMANCE_ACTION_UNCLEAR'],
        failure_observations={'PERFORMANCE_ACTION_UNCLEAR': 'Offline fixture action is unclear'})
    _, repair = QCStore(env.store).save(asset, rows, human)
    changed = env.shot.model_copy(update={'spec_version': 2,
        'blocking': env.shot.blocking.model_copy(update={'action_beats': ['One clear step then hold']})})
    original_lineage = env.store.read_runtime_lineage
    with monkeypatch.context() as patch:
        def foreign_route(*args):
            lineage = list(original_lineage(*args))
            lineage[2] = lineage[2].model_copy(update={'provider_id': 'other_provider'})
            return tuple(lineage)
        patch.setattr(env.store, 'read_runtime_lineage', foreign_route)
        with pytest.raises(Exception, match='PREDECESSOR_UNQUALIFIED'):
            env.runtime.repair_parent(changed, repair['repair_decision_id'])
    kwargs = dict(reference_asset=env.asset, reference_media_id=REMOTE,
        reference_filename='reference.png', catalog_source=env.catalog_source)
    with pytest.raises(Exception, match='REPAIR_DECISION_REQUIRED'):
        env.runtime.freeze(changed, flow_capabilities(), **kwargs)
    env.session._offline_rows.append(row)
    frozen = env.runtime.freeze(changed, flow_capabilities(),
        repair_decision_id=repair['repair_decision_id'], **kwargs)
    assert frozen.job.provider_job_id != env.frozen.job.provider_job_id
    assert frozen.job.dispatch_count == 0
    assert env.store.read_provider_job(env.frozen.job.provider_job_id).dispatch_count == 1
    resumed = env.runtime.freeze(changed, flow_capabilities(),
        repair_decision_id=repair['repair_decision_id'], **kwargs)
    assert resumed.job.provider_job_id == frozen.job.provider_job_id
    assert env.runtime.reserve(frozen, attestation=env.attestation,
        evidence_dir=env.attestation_dir).dispatch_count == 1
    with pytest.raises(Exception, match='CONSUMED|consumed'):
        env.runtime.reserve(frozen, attestation=env.attestation, evidence_dir=env.attestation_dir)
    # Resuming the original version also retains the original job after repair.
    assert env.runtime.freeze(env.shot, flow_capabilities(), **kwargs).job.provider_job_id == env.frozen.job.provider_job_id
    with pytest.raises(Exception, match='PREDECESSOR_UNQUALIFIED'):
        env.runtime.freeze(changed.model_copy(update={'spec_version': 3}), flow_capabilities(),
            repair_decision_id=repair['repair_decision_id'], **kwargs)
