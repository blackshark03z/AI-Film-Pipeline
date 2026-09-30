"""One upload-only live canary and authorized read-only frozen-reference recovery."""
from __future__ import annotations

import hashlib
import io
import json
import sqlite3
from pathlib import Path

from PIL import Image, ImageDraw

from .core import canonical_json, sha256
from .live_runtime import Asset, file_sha256
from .providers.flow_reference_rpc import FlowReferenceRpcSession
from .providers.flow_reference_transport import FlowReferenceTransport
from .providers.flow_reference_upload import ReferenceUploadStore, OwnerAmbiguityGate, _key
from .slice0011 import ROOT, PROJECT_ID, ACCOUNT_ID, freeze_reference, REFERENCE_ASSET_ID
from .store import SQLiteStore

QUALIFICATION_ROOT = ROOT / 'projects/character_continuity/reference_qualification_20260930'
SLICE_ROOT = ROOT / 'projects/character_continuity/slice0011'
FROZEN_RESERVATION = 'refup_1521a9ea3a8582852abbe2b97bf8de4df2ddba6cb689df67c04e06b26021e3ce'


def _write_exact(path: Path, value: dict):
    data = canonical_json(value).encode('utf-8')
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        if path.read_bytes() != data:
            raise OwnerAmbiguityGate('immutable reference qualification artifact changed')
        return
    with path.open('xb') as stream:
        stream.write(data)
        stream.flush()
        import os
        os.fsync(stream.fileno())


def canary_reference() -> tuple[Path, Asset]:
    """Distinct synthetic PNG for transport research, no additional image provider."""
    image = Image.new('RGB', (1280, 720), (28, 42, 59))
    draw = ImageDraw.Draw(image)
    draw.rectangle((45, 40, 615, 330), fill=(207, 67, 84))
    draw.ellipse((690, 55, 1190, 490), fill=(42, 177, 151))
    draw.polygon([(135, 650), (425, 375), (610, 655)], fill=(227, 185, 51))
    for index in range(24):
        x, y = 700 + index * 19, 565 + (index % 3) * 24
        draw.rectangle((x, y, x + 11, y + 36), fill=(90 + index * 5, 90, 190))
    draw.text((50, 350), 'FILM REFERENCE TRANSPORT CANARY 20260930 V1', fill=(240, 240, 240))
    stream = io.BytesIO()
    image.save(stream, 'PNG')
    data = stream.getvalue()
    digest = hashlib.sha256(data).hexdigest()
    path = QUALIFICATION_ROOT / 'reference' / f'{digest}.png'
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists() and path.read_bytes() != data:
        raise OwnerAmbiguityGate('canary source changed')
    if not path.exists():
        path.write_bytes(data)
    asset = Asset(asset_id='asset_' + sha256({'origin': 'reference', 'sha256': digest}),
        asset_type='image', origin='reference', uri_or_path=str(path.resolve()),
        sha256=digest, mime_type='image/png', width=1280, height=720, file_size=len(data),
        rights_metadata={'source_kind': 'deterministic_synthetic_fixture',
            'provenance': 'Film reference upload-only canary v1; geometric drawing; no person'})
    database = QUALIFICATION_ROOT / 'runtime.sqlite'
    store = SQLiteStore(database)
    store.initialize()
    store.save_reference_asset(asset)
    return database, asset


class _NoNetworkSession:
    project_id = PROJECT_ID

    def __getattr__(self, _):
        raise AssertionError('verified reference reuse must not access network')


def run_live_canary(cookie_path: Path) -> dict:
    database, asset = canary_reference()
    store = ReferenceUploadStore(database)
    key = _key('flow_veo', PROJECT_ID, ACCOUNT_ID, asset)
    progress = store.read_progress(key)
    if progress and progress['effective_state'] in {
            'REQUEST_ARMED', 'FAILED_AMBIGUOUS', 'LEGACY_RESERVED_UNCERTAIN'}:
        raise OwnerAmbiguityGate('canary already armed without verified result; stop')
    if progress and progress['effective_state'] == 'REMOTE_RESOURCE_VERIFIED':
        if (QUALIFICATION_ROOT / 'qualification.json').exists():
            return read_live_qualification()
        return _finish_canary(database, asset, store, post_calls_this_run=0)
    with FlowReferenceRpcSession(cookie_path=cookie_path, project_id=PROJECT_ID) as session:
        transport = FlowReferenceTransport(store, session, account_id=ACCOUNT_ID,
            evidence_dir=QUALIFICATION_ROOT / 'evidence')
        receipt = transport.ensure_verified(asset)
        counts = dict(session.rpc_call_counts)
    return _finish_canary(database, asset, store,
                          post_calls_this_run=counts.get('maseQ', 0))


def _finish_canary(database, asset, store, *, post_calls_this_run):
    fresh = ReferenceUploadStore(database).read_verified('flow_veo', PROJECT_ID, ACCOUNT_ID, asset)
    reused = FlowReferenceTransport(ReferenceUploadStore(database), _NoNetworkSession(),
        account_id=ACCOUNT_ID, evidence_dir=QUALIFICATION_ROOT / 'evidence').ensure_verified(asset)
    if fresh is None or fresh != reused:
        raise OwnerAmbiguityGate('live canary durable/reuse identity mismatch')
    key = _key('flow_veo', PROJECT_ID, ACCOUNT_ID, asset)
    events = store.events(key)
    identified = next(e for e in events if e['stage'] == 'REMOTE_RESOURCE_IDENTIFIED')
    if identified['data']['method'] != 'upload_response':
        raise OwnerAmbiguityGate('canary requires observed upload response identity')
    result = {'result': 'LIVE_UPLOAD_CANARY_PASS', 'project_id': PROJECT_ID,
        'isolation': 'dedicated research database and distinct synthetic reference; existing project',
        'database': str(database.resolve()), 'asset_id': asset.asset_id,
        'reference_sha256': asset.sha256, 'reservation_id': key,
        'media_id': fresh['media_id'], 'provider_media_sha256': fresh['provider_media_sha256'],
        'request_armed_count': sum(e['stage'] == 'REQUEST_ARMED' for e in store.events(key)),
        'upload_attempts': fresh['upload_attempts'],
        'upload_post_invocations_this_run': post_calls_this_run,
        'upload_count_evidence': 'one durable upload arm and one HTTP response; no wire-delivery assertion',
        'restart_local_readback': True, 'second_ensure_network_calls': 0,
        'wire_dispatch_claimed': False, 'delivery_semantics': 'AT_MOST_ONCE_WITH_POSSIBLE_LOSS'}
    if result['request_armed_count'] != 1 or result['upload_attempts'] != 1:
        raise OwnerAmbiguityGate('canary authority count inconsistent')
    _write_exact(QUALIFICATION_ROOT / 'qualification.json', result)
    return read_live_qualification()


def read_live_qualification() -> dict:
    """Fresh local process checks actual live receipt/event/artifact consistency."""
    path = QUALIFICATION_ROOT / 'qualification.json'
    if not path.is_file():
        raise ValueError('live reference canary qualification required')
    result = json.loads(path.read_text(encoding='utf-8'))
    database, asset = canary_reference()
    if (result.get('result') != 'LIVE_UPLOAD_CANARY_PASS' or result.get('project_id') != PROJECT_ID
            or result.get('reference_sha256') != asset.sha256 or result.get('asset_id') != asset.asset_id
            or result.get('database') != str(database.resolve())
            or result.get('upload_attempts') != 1 or result.get('request_armed_count') != 1):
        raise OwnerAmbiguityGate('live qualification identity mismatch')
    store = ReferenceUploadStore(database)
    receipt = store.read_verified('flow_veo', PROJECT_ID, ACCOUNT_ID, asset)
    if receipt is None or any(receipt[k] != result[k] for k in ('media_id', 'provider_media_sha256')):
        raise OwnerAmbiguityGate('live qualification receipt mismatch')
    events = store.events(result['reservation_id'])
    stages = [event['stage'] for event in events]
    if (stages.count('REQUEST_ARMED') != 1
            or not stages.index('HTTP_RESPONSE_OBSERVED') < stages.index('REMOTE_RESOURCE_IDENTIFIED')
            < stages.index('REMOTE_RESOURCE_VERIFIED')
            or next(e for e in events if e['stage'] == 'HTTP_RESPONSE_OBSERVED')['data']['status'] != 200):
        raise OwnerAmbiguityGate('live qualification event order mismatch')
    verified = next(e['data'] for e in events if e['stage'] == 'REMOTE_RESOURCE_VERIFIED')
    evidence = json.loads((QUALIFICATION_ROOT / 'evidence' /
        f"{verified['verification_hash']}.json").read_text(encoding='utf-8'))
    if (sha256(evidence) != verified['verification_hash'] or evidence['media_id'] != receipt['media_id']
            or not evidence['comparison']['strong_match']
            or evidence['comparison']['source_sha256'] != asset.sha256
            or evidence['comparison']['provider_media_sha256'] != receipt['provider_media_sha256']):
        raise OwnerAmbiguityGate('live qualification content evidence mismatch')
    reused = FlowReferenceTransport(store, _NoNetworkSession(), account_id=ACCOUNT_ID,
        evidence_dir=QUALIFICATION_ROOT / 'evidence').ensure_verified(asset)
    if reused != receipt:
        raise OwnerAmbiguityGate('fresh process reference reuse mismatch')
    return result


def recover_frozen_reference(cookie_path: Path) -> dict:
    qualification = read_live_qualification()
    database = SLICE_ROOT / 'runtime.sqlite'
    asset = SQLiteStore(database).read_reference_asset(REFERENCE_ASSET_ID)
    store = ReferenceUploadStore(database)
    key = _key('flow_veo', PROJECT_ID, ACCOUNT_ID, asset)
    if key != FROZEN_RESERVATION:
        raise OwnerAmbiguityGate('frozen reservation identity mismatch')
    progress = store.read_progress(key)
    if progress is None or progress['upload_attempts'] != 1:
        raise OwnerAmbiguityGate('original one-upload reservation missing')
    snapshot_path = SLICE_ROOT / 'reference_evidence/frozen_reservation_before_recovery.json'
    if not snapshot_path.exists():
        with sqlite3.connect(database) as connection:
            original = json.loads(connection.execute(
                'SELECT payload FROM reference_uploads WHERE id=?', (key,)).fetchone()[0])
        _write_exact(snapshot_path, {'reservation': original, 'sha256': sha256(original)})
    with FlowReferenceRpcSession(cookie_path=cookie_path, project_id=PROJECT_ID) as session:
        transport = FlowReferenceTransport(store, session, account_id=ACCOUNT_ID,
            evidence_dir=SLICE_ROOT / 'reference_evidence')
        receipt = transport.reconcile_only(asset)
        if session.rpc_call_counts.get('maseQ', 0) != 0:
            raise OwnerAmbiguityGate('frozen recovery emitted unauthorized upload')
    result = {'result': 'FROZEN_REFERENCE_RECOVERED', 'reservation_id': key,
        'reference_sha256': asset.sha256, 'media_id': receipt['media_id'],
        'provider_media_sha256': receipt['provider_media_sha256'],
        'slice_reference_reuploads': 0, 'final_state': 'REMOTE_RESOURCE_VERIFIED',
        'qualification_reservation_id': qualification['reservation_id'],
        'attribution_scope': 'unique strongly matching resource in observed project catalog; original POST outcome not retrospectively proven'}
    _write_exact(SLICE_ROOT / 'frozen_reference_recovery.json', result)
    return result


def require_production_reference() -> dict:
    qualification = read_live_qualification()
    path = SLICE_ROOT / 'frozen_reference_recovery.json'
    if not path.is_file():
        raise ValueError('uniquely recovered frozen reference required before generation')
    result = json.loads(path.read_text(encoding='utf-8'))
    asset = SQLiteStore(SLICE_ROOT / 'runtime.sqlite').read_reference_asset(REFERENCE_ASSET_ID)
    receipt = ReferenceUploadStore(SLICE_ROOT / 'runtime.sqlite').read_verified(
        'flow_veo', PROJECT_ID, ACCOUNT_ID, asset)
    if (receipt is None or result.get('result') != 'FROZEN_REFERENCE_RECOVERED'
            or result.get('media_id') != receipt['media_id']
            or result.get('reference_sha256') != asset.sha256
            or result.get('slice_reference_reuploads') != 0
            or result.get('qualification_reservation_id') != qualification['reservation_id']):
        raise OwnerAmbiguityGate('production reference qualification mismatch')
    return result
