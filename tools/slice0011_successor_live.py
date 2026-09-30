"""Exactly the Owner-authorized A successor; no reference upload/B/retry command."""
from __future__ import annotations

import argparse
import json
import sqlite3
import subprocess
import tempfile
import os
import time
from pathlib import Path

from film_pipeline.core import canonical_json, sha256
from film_pipeline.live_runtime import file_sha256
from film_pipeline.providers.flow_reference_rpc import FlowReferenceRpcSession
from film_pipeline.providers.flow_reference_upload import ReferenceUploadStore, OwnerAmbiguityGate
from film_pipeline.reference_qualification import require_production_reference
from film_pipeline.slice0011 import ROOT, PROJECT_ID, ACCOUNT_ID, REFERENCE_ASSET_ID, submit_and_acquire_shot
from film_pipeline.slice0011_successor import (AUTHORITY_ID, OWNER_BRIEF_SHA256, BASE_REVISION,
    PARENT_ATTEMPT, PARENT_JOB, REFERENCE_MEDIA_ID, freeze_successor, historical_snapshot,
    read_successor)
from film_pipeline.store import SQLiteStore

SLICE_ROOT = ROOT / 'projects/character_continuity/slice0011'
DATABASE = SLICE_ROOT / 'runtime.sqlite'
OUTPUT = SLICE_ROOT / 'successor_a_compact_v1'


class SuccessorSession(FlowReferenceRpcSession):
    def _rpc_body(self, rpc_id, body, **options):
        if rpc_id not in {'Zzl0ze', 'as29s', 'MZZa6b'}:
            raise OwnerAmbiguityGate('successor forbids uploads and unrelated RPCs')
        if rpc_id == 'MZZa6b' and self.rpc_call_counts.get(rpc_id, 0):
            raise OwnerAmbiguityGate('successor MZZa6b already called; no retry')
        return super()._rpc_body(rpc_id, body, **options)


def write_exact(path, data):
    encoded = canonical_json(data)
    if path.exists():
        if path.read_text(encoding='utf-8') != encoded:
            raise OwnerAmbiguityGate('immutable successor evidence file differs')
        return
    with path.open('x', encoding='utf-8') as stream:
        stream.write(encoded)


def build_review(database, asset, output):
    """Pure local comparison/QC evidence. No selected take or human approval."""
    from film_pipeline.qc import QCStore, evidence, technical_evidence
    from film_pipeline.qc_media import make_review_media
    from film_pipeline.qc_runner import exact_lineage
    from PIL import Image, ImageDraw
    store, shot, asset = exact_lineage(database, asset.source_attempt_id, asset.provider_job_id, asset.asset_id)
    reference = store.read_reference_asset(REFERENCE_ASSET_ID)
    if file_sha256(Path(reference.uri_or_path)) != reference.sha256:
        raise OwnerAmbiguityGate('review reference bytes changed')
    technical, metadata = technical_evidence(shot, asset)
    if not metadata or any(row.verdict != 'pass' for row in technical):
        raise OwnerAmbiguityGate('successor technical QC failed')
    criteria = {
        'visual': (('reference_face_and_look', 'Same face, teal bob, crimson glasses, mustard/blue wardrobe, silver triangle earrings and beauty mark throughout?'),),
        'continuity': (('reference_identity_and_direction', 'Exact reference identity and frame-right direction stable throughout?'),),
        'editorial': (('calm_mcu_performance', 'Locked eye-level MCU, subtle breathing and one blink usable?'),)}
    rows, media = make_review_media(asset, output / 'frames', criteria=criteria)
    sheet = Image.new('RGB', (1600, 660), '#151a24')
    draw = ImageDraw.Draw(sheet)
    draw.text((12, 12), 'EXACT REFERENCE', fill='white')
    draw.text((812, 12), 'SHOT A SUCCESSOR - sampled middle frame', fill='white')
    descriptor, staging_name = tempfile.mkstemp(suffix='.png', dir=output)
    os.close(descriptor)
    staging = Path(staging_name)
    try:
        process = subprocess.run(['ffmpeg', '-v', 'error', '-y', '-ss', str(asset.duration_s / 2),
            '-i', asset.uri_or_path, '-frames:v', '1', str(staging)], capture_output=True, timeout=60)
        if process.returncode or not staging.stat().st_size:
            raise OwnerAmbiguityGate('full-resolution comparison frame unavailable')
        middle = output / ('middle_' + file_sha256(staging) + '.png')
        try:
            os.link(staging, middle)
        except FileExistsError:
            if file_sha256(middle) != file_sha256(staging):
                raise OwnerAmbiguityGate('middle-frame evidence collision')
    finally:
        staging.unlink(missing_ok=True)
    for x, source in ((0, reference.uri_or_path), (800, middle)):
        with Image.open(source) as image:
            sheet.paste(image.convert('RGB').resize((800, 450)), (x, 40))
    with Image.open(media['contact_sheet']['path']) as image:
        sheet.paste(image.convert('RGB'), (0, 480))
    pair = output / 'reference_vs_successor_a.png'
    sheet.save(pair)
    rows.append(evidence(asset=asset, evaluator_type='ffmpeg', evaluator_version='successor-reference-review-v1',
        gate='continuity', criterion='reference_vs_successor', verdict='uncertain',
        observation='Owner review required; sampled frames do not establish all-frame identity.',
        source_artifacts=[{'path': reference.uri_or_path, 'sha256': reference.sha256},
                          {'path': str(pair), 'sha256': file_sha256(pair)}]))
    record, disposition = QCStore(store).save(asset, technical + rows)
    if disposition is not None or record.report['decision'] != 'needs_human_review':
        raise OwnerAmbiguityGate('successor must remain unselected for Owner review')
    packet = {'gate': 'OWNER_CHARACTER_CONTINUITY_REVIEW_GATE', 'asset_id': asset.asset_id,
        'sha256': asset.sha256, 'video': asset.uri_or_path, 'reference': reference.uri_or_path,
        'comparison': str(pair), 'comparison_sha256': file_sha256(pair),
        'full_resolution_middle': {'path': str(middle), 'sha256': file_sha256(middle)},
        'sampled_media': media, 'technical': [row.model_dump(mode='json') for row in technical],
        'qc_report_id': record.report['qc_report_id'], 'selected_take_created': False}
    write_exact(output / 'character_review.json', packet)
    return packet


def run(cookie_path, owner_brief):
    if (OUTPUT / 'live_result.json').exists():
        raise OwnerAmbiguityGate('durable successor stop already recorded; no provider access or retry')
    if file_sha256(owner_brief) != OWNER_BRIEF_SHA256:
        raise OwnerAmbiguityGate('exact Owner successor authorization required')
    require_production_reference()
    store = SQLiteStore(DATABASE)
    prior = read_successor(store)
    if prior is not None and prior.dispatch_count != 0:
        raise OwnerAmbiguityGate('successor already consumed; no provider access or retry')
    OUTPUT.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(f'file:{DATABASE.as_posix()}?mode=ro', uri=True) as connection:
        before = historical_snapshot(connection)
    write_exact(OUTPUT / 'historical_before.json', before)
    reference = store.read_reference_asset(REFERENCE_ASSET_ID)
    receipt = ReferenceUploadStore(DATABASE).read_verified('flow_veo', PROJECT_ID, ACCOUNT_ID, reference)
    if receipt is None or receipt['media_id'] != REFERENCE_MEDIA_ID:
        raise OwnerAmbiguityGate('qualified exact reference receipt required')
    report = {'base_revision': BASE_REVISION,
        'implementation_revision': subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip(),
        'authority_id': AUTHORITY_ID, 'historical_attempt': PARENT_ATTEMPT, 'historical_job': PARENT_JOB,
        'historical_before_hash': sha256(before), 'reference_asset': reference.asset_id,
        'reference_sha256': reference.sha256, 'reference_media_id': REFERENCE_MEDIA_ID,
        'project_id': PROJECT_ID, 'model': 'abra_r2v_8s', 'duration_s': 8, 'aspect': '16:9',
        'shot_b_submits': 0, 'reference_uploads': 0, 'dola_seedance_calls': 0,
        'gate': 'OWNER_AMBIGUITY_GATE', 'asset': None, 'output_identity': None}
    session = SuccessorSession(cookie_path=cookie_path, project_id=PROJECT_ID)
    job = None
    try:
        with session:
            job = freeze_successor(DATABASE, session, receipt)
            body = job.correlation_evidence['prompt'].rsplit('\n', 1)[0]
            report.update(successor_attempt_id=job.generation_attempt_id, provider_job_id=job.provider_job_id,
                provider_prompt=job.correlation_evidence['prompt'], provider_prompt_body_characters=len(body),
                fresh_baseline=job.pre_dispatch_snapshot)
            write_exact(OUTPUT / 'frozen_intent.json', report)
            print(json.dumps({'stage': 'successor_frozen', 'attempt': job.generation_attempt_id,
                'job': job.provider_job_id, 'body_characters': len(body),
                'baseline_count': len(job.pre_dispatch_snapshot['catalog_ids'])}), flush=True)
            last = 0.0
            def progress(**values):
                nonlocal last
                if time.monotonic() - last >= 30:
                    print(json.dumps({'stage': 'waiting_exact_successor_output', **values}), flush=True)
                    last = time.monotonic()
            asset = submit_and_acquire_shot(DATABASE, session, job, OUTPUT / 'videos',
                successor_authority_id=AUTHORITY_ID, progress=progress)
            report['asset'] = asset.model_dump(mode='json')
            report['output_identity'] = asset.provider_asset_id
            packet = build_review(DATABASE, asset, OUTPUT)
            report['review_packet'] = str(OUTPUT / 'character_review.json')
            report['technical_qc'] = packet['technical']
            report['gate'] = 'OWNER_CHARACTER_CONTINUITY_REVIEW_GATE'
    except Exception as exc:
        report['stop_type'] = type(exc).__name__  # No authenticated exception bodies.
        if job is not None and store.read_provider_job(job.provider_job_id).dispatch_count:
            if not any(f['kind'] == 'AMBIGUOUS_EVIDENCE' for f in store.read_dispatch_facts(job.provider_job_id)):
                store.record_dispatch_fact(job.provider_job_id, 'AMBIGUOUS_EVIDENCE',
                    {'diagnostic': 'successor_requires_owner'})
    finally:
        report['rpc_calls'] = session.rpc_call_counts
        report['mzza6b_submits'] = session.rpc_call_counts.get('MZZa6b', 0)
        if job is not None:
            fresh = store.read_provider_job(job.provider_job_id)
            report['successor_dispatch_count'] = fresh.dispatch_count
            report['output_identity'] = fresh.external_job_id
            report['dispatch_facts'] = store.read_dispatch_facts(job.provider_job_id)
            report['response_diagnostics'] = [fact['data'] for fact in report['dispatch_facts'] if fact['kind'] == 'R2V_RESPONSE_DIAGNOSTICS']
        with sqlite3.connect(f'file:{DATABASE.as_posix()}?mode=ro', uri=True) as connection:
            after = historical_snapshot(connection)
        report['historical_after_hash'] = sha256(after)
        report['historical_unchanged'] = canonical_json(before) == canonical_json(after)
        if not report['historical_unchanged']:
            report['gate'] = 'OWNER_AMBIGUITY_GATE'
        write_exact(OUTPUT / 'historical_after.json', after)
        write_exact(OUTPUT / 'live_result.json', report)
        print(json.dumps({'gate': report['gate'], 'mzza6b_submits': report['mzza6b_submits'],
            'historical_unchanged': report['historical_unchanged'], 'report': str(OUTPUT / 'live_result.json')}), flush=True)
    return report


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--cookie', type=Path, required=True)
    parser.add_argument('--owner-brief', type=Path, required=True)
    args = parser.parse_args()
    try:
        run(args.cookie, args.owner_brief)
    except Exception as exc:
        print(json.dumps({'gate': 'OWNER_AMBIGUITY_GATE', 'stop_type': type(exc).__name__}), flush=True)
        raise SystemExit(1)
