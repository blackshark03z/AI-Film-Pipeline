"""Production-system journey using synthetic local media, never a film acceptance.

Provider I/O uses existing offline doubles; plan, lineage, QC, selection,
editorial, FFmpeg export and relocated delivery readback are real code paths.
"""
import json
import gc
import shutil
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace
from uuid import NAMESPACE_URL, uuid5

import pytest

from film_pipeline.e2e import finish, prepare, resume, status, verify_package
from film_pipeline.e2e_flow import shot_spec
from film_pipeline.flow_r2v_runtime import FlowR2VShotRuntime, qualify_flow_catalog_source
from film_pipeline.providers.flow_reference_binding import attest_existing_reference
from film_pipeline.qc import QCStore, evidence, technical_evidence
from film_pipeline.store import SQLiteStore
from film_pipeline.live_runtime import file_sha256
from test_canonical_reference_binding import bound
from test_e2e import media, source_srt, fixture_direction
from test_flow_r2v_runtime import (
    _offline_flow_catalog, offline_flow_session, flow_capabilities,
    reserve, release_request, own_output, mp4_fixture, media_payload,
    FixtureAcquisitionTransport,
)
from test_reference_reconcilable_transport import setup, ACCOUNT, PROJECT, REMOTE


def test_offline_prepare_resume_review_finish_and_relocated_package(tmp_path, _offline_flow_catalog):
    audio, srt = tmp_path / 'audio.mp3', tmp_path / 'source.srt'
    media(audio)
    source_srt(srt)
    root = tmp_path / 'offline-production-system'
    prepare(audio, srt, 18, 48, root)
    plan_path = root / 'shots.json'
    plan = json.loads(plan_path.read_text(encoding='utf-8'))
    for shot in plan['shots']:
        shot.update(visual_intent='Synthetic fixture: visible action',
                    image_prompt='Synthetic fixture reference',
                    video_prompt='One step forward, then hold')
        fixture_direction(shot)
    plan_path.write_text(json.dumps(plan), encoding='utf-8')
    reference, uploads, session, transport, _ = setup(root)
    receipt = root / 'offline-reference.json'
    receipt.write_text(json.dumps({'profile_email': 'nethaolabycss222@gmail.com', 'tab_index': 2,
        'images': [{'shot_ids': [s['shot_id'] for s in plan['shots']],
            'path': reference.uri_or_path, 'sha256': reference.sha256,
            'chat_url': 'https://chatgpt.com/c/offline-fixture-not-generated'}]}), encoding='utf-8')
    database = Path(uploads.db_path)
    state = resume(root, database, PROJECT, receipt)
    assert len(state['missing_selected_shots']) == 8
    with pytest.raises(ValueError, match='missing|approved|selected'):
        finish(root, database, PROJECT)
    # Simulated external I/O; all runtime custody and QC remain unchanged.
    transport.ensure_verified(reference)
    session.bound_media = lambda identity, kind: bound()[3]
    store = SQLiteStore(database)
    attestation_dir = root / 'attestation'
    attestation = attest_existing_reference(store, reference, session, account_id=ACCOUNT,
        media_id=REMOTE, evidence_dir=attestation_dir)
    runtime = FlowR2VShotRuntime(store, project_id=PROJECT, account_id=ACCOUNT)
    catalog = offline_flow_session(session.catalog())
    capability = qualify_flow_catalog_source(catalog)
    data = mp4_fixture(root / 'synthetic-source.mp4')
    jobs = []
    for planned in plan['shots']:
        spec = shot_spec(planned, reference.asset_id, plan_version=plan['version'])
        kwargs = dict(reference_asset=reference, reference_media_id=REMOTE,
                      reference_filename='reference.png', catalog_source=capability)
        frozen = runtime.freeze(spec, flow_capabilities(), **kwargs)
        env = SimpleNamespace(runtime=runtime, frozen=frozen, store=store,
                              attestation=attestation, attestation_dir=attestation_dir)
        reserve(env)
        release_request(env)
        output_id, row = own_output(env, str(uuid5(NAMESPACE_URL, planned['shot_id'])))
        asset = runtime.acquire(frozen, transport=FixtureAcquisitionTransport(data),
            destination_dir=root / 'assets', media_payload=media_payload(env, output_id, data))
        rows, _ = technical_evidence(spec, asset)
        rows.extend(evidence(asset=asset, evaluator_type='temporal_heuristic', evaluator_version='fixture',
            gate=gate, criterion='unassessed', observation='Offline fixture only', verdict='uncertain')
            for gate in ('visual', 'continuity', 'editorial'))
        report, _ = QCStore(store).save(asset, rows)
        assert report.report['decision'] == 'needs_human_review'
        catalog._offline_rows.append(row)
        # Reopen the exact completed request: no second reservation/submission.
        reopened = runtime.freeze(spec, flow_capabilities(), **kwargs)
        assert reopened.job.provider_job_id == frozen.job.provider_job_id
        assert store.read_provider_job(reopened.job.provider_job_id).dispatch_count == 1
        jobs.append(frozen.job.provider_job_id)
    before = file_sha256(database)
    pending = status(root)  # Infers the bound Flow project and local runtime.
    assert file_sha256(database) == before
    assert len(pending['missing_selected_shots']) == len(pending['review_template']['reviews']) == 8
    direction = pending['review_template']['reviews'][0]['direction_to_review']
    assert direction['end'] == 'Arms at sides'
    assert direction['end_state'] == {'hand_contact': False}
    assert direction['next_shot_id'] == 'SHOT_02'
    assert direction['qc_questions'] == []  # No action_meaning declared.
    review = pending['review_template']
    for entry in review['reviews']:
        entry.update(reviewer_id='offline_fixture_operator', visual_pass=True,
            continuity_pass=True, editorial_pass=True,
            notes=['Offline fixture decision only; not Owner film acceptance'])
    review_path = root / 'offline-review.json'
    review_path.write_text(json.dumps(review), encoding='utf-8')
    ready = resume(root, database, PROJECT, review_manifest=review_path)
    assert ready['status'] == 'READY_TO_FINISH'
    assert len(ready['selected_shots']) == 8
    result = finish(root, database, PROJECT)
    assert result['full_decode'] is True and len(result['shots']) == 8
    assert finish(root, database, PROJECT) == result
    assert all(store.read_provider_job(job).dispatch_count == 1 for job in jobs)
    relocated = tmp_path / 'cold-open'
    shutil.copytree(root / result['package_path'], relocated)
    assert verify_package(relocated)['result'] == 'PASS'
    # Hide the original project: CLI readback must need neither DB nor original paths.
    gc.collect()  # Close collected SQLite handles before moving a Windows directory.
    root.rename(tmp_path / 'original-project-unavailable')
    cli = Path(__file__).resolve().parents[1] / 'tools/film_e2e.py'
    check = subprocess.run([sys.executable, str(cli), 'status', '--package', str(relocated)],
                           capture_output=True, text=True, timeout=30)
    assert check.returncode == 0, check.stderr
    assert json.loads(check.stdout)['verified'] == 3
    subprocess.run(['ffmpeg', '-v', 'error', '-xerror', '-i', str(relocated / 'master.mp4'),
                    '-f', 'null', '-'], check=True, capture_output=True, timeout=60)
