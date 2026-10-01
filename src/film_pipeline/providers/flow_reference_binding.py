"""Additive canonical reference attestations; existing upload history is read-only."""
from __future__ import annotations

import hashlib
import os
import re
import io
from contextlib import closing
from pathlib import Path

from ..core import canonical_json, sha256
from .flow_media import BoundMedia, VERSION
from .flow_reference_transport import image_comparison
from .flow_reference_upload import OwnerAmbiguityGate, ReferenceUploadStore


def reference_attestation(asset, receipt, media: BoundMedia, *, project_id, media_id):
    source = Path(asset.uri_or_path).read_bytes()
    if (asset.origin != 'reference' or asset.asset_type != 'image'
            or hashlib.sha256(source).hexdigest() != asset.sha256):
        raise OwnerAmbiguityGate('CANONICAL_REFERENCE_BYTES_CHANGED')
    if (receipt is None or receipt['asset_id'] != asset.asset_id
            or receipt['reference_sha256'] != asset.sha256
            or receipt['project_id'] != project_id or receipt['media_id'] != media_id):
        raise OwnerAmbiguityGate('CANONICAL_REFERENCE_RECEIPT_MISMATCH')
    if not isinstance(media, BoundMedia):
        raise OwnerAmbiguityGate('INDEPENDENTLY_BOUND_READBACK_REQUIRED')
    e = media.evidence
    expected = {'version': VERSION, 'media_id': media_id, 'project_id': project_id,
        'kind': 'image', 'response_id': media_id, 'response_project_id': project_id,
        'resource_host': 'flow-content.google', 'resource_path': f'/image/{media_id}',
        'response_status': 200, 'redirects': 0,
        'sha256': hashlib.sha256(media.data).hexdigest(), 'byte_size': len(media.data)}
    if (any(e.get(key) != value for key, value in expected.items())
            or set(e) != set(expected) | {'mime_type', 'width', 'height'}
            or receipt['provider_media_sha256'] != expected['sha256']):
        raise OwnerAmbiguityGate('REFERENCE_READBACK_BINDING_MISMATCH')
    comparison = image_comparison(source, media.data)
    from PIL import Image
    with Image.open(io.BytesIO(media.data)) as decoded:
        decoded.load()
        if decoded.size != (e['width'], e['height']) or Image.MIME.get(decoded.format) != e['mime_type']:
            raise OwnerAmbiguityGate('REFERENCE_DECODE_METADATA_MISMATCH')
    if not comparison['strong_match']:
        raise OwnerAmbiguityGate('CANONICAL_REFERENCE_CONTENT_MISMATCH')
    basis = {'version': 'flow-canonical-reference-v1', 'asset_id': asset.asset_id,
        'source_sha256': asset.sha256, 'provider_id': 'flow_veo',
        'account_id': receipt['account_id'], 'project_id': project_id, 'media_id': media_id,
        'upload_receipt_id': receipt['id'], 'upload_receipt_sha256': sha256(receipt),
        'readback': e, 'comparison': comparison}
    return {'attestation_id': 'refbind_' + sha256(basis), **basis}


def write_immutable(path, data):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    encoded = canonical_json(data).encode('utf-8')
    if path.exists():
        if path.read_bytes() != encoded:
            raise OwnerAmbiguityGate('IMMUTABLE_REFERENCE_EVIDENCE_CONFLICT')
        return
    with path.open('xb') as stream:
        stream.write(encoded)
        stream.flush()
        os.fsync(stream.fileno())


def attest_existing_reference(store, asset, session, *, account_id, media_id, evidence_dir):
    """Read-only provider proof. No upload/recovery/alternate-ID path exists."""
    receipt = ReferenceUploadStore(store.path).read_verified(
        'flow_veo', session.project_id, account_id, asset)
    if not receipt or receipt['media_id'] != media_id:
        raise OwnerAmbiguityGate('REQUIRED_PROVIDER_REFERENCE_MISMATCH')
    media = session.bound_media(media_id, 'image')
    attestation = reference_attestation(asset, receipt, media,
        project_id=session.project_id, media_id=media_id)
    directory = Path(evidence_dir)
    directory.mkdir(parents=True, exist_ok=True)
    resource_path = directory / (media.evidence['sha256'] + '.jpg')
    if resource_path.exists():
        if resource_path.read_bytes() != media.data:
            raise OwnerAmbiguityGate('REFERENCE_EVIDENCE_BYTES_CONFLICT')
    else:
        with resource_path.open('xb') as stream:
            stream.write(media.data)
            stream.flush()
            os.fsync(stream.fileno())
    write_immutable(directory / (attestation['attestation_id'] + '.json'), attestation)
    connection = store._connect()
    try:
        with connection:
            connection.execute('CREATE TABLE IF NOT EXISTS flow_reference_attestations '
                '(id TEXT PRIMARY KEY, payload TEXT NOT NULL)')
            for action in ('UPDATE', 'DELETE'):
                connection.execute(f'CREATE TRIGGER IF NOT EXISTS reference_attestation_no_{action.lower()} '
                    f'BEFORE {action} ON flow_reference_attestations BEGIN '
                    "SELECT RAISE(ABORT,'immutable canonical reference attestation'); END")
            connection.execute('INSERT OR IGNORE INTO flow_reference_attestations VALUES (?,?)',
                (attestation['attestation_id'], canonical_json(attestation)))
            row = connection.execute('SELECT payload FROM flow_reference_attestations WHERE id=?',
                (attestation['attestation_id'],)).fetchone()
            if row != (canonical_json(attestation),):
                raise OwnerAmbiguityGate('REFERENCE_ATTESTATION_COLLISION')
    finally:
        connection.close()
    return attestation


def verify_attestation(store, asset, attestation, *, media_id, project_id, evidence_dir):
    """Recompute from retained exact bytes and existing receipt at each boundary."""
    import json
    key = attestation['attestation_id']
    if (not re.fullmatch(r'refbind_[a-f0-9]{64}', key)
            or not re.fullmatch(r'[a-f0-9]{64}', attestation['readback']['sha256'])):
        raise OwnerAmbiguityGate('INVALID_REFERENCE_EVIDENCE_LOCATOR')
    persisted = json.loads((Path(evidence_dir) / (key + '.json')).read_text(encoding='utf-8'))
    with closing(store._connect()) as connection:
        row = connection.execute('SELECT payload FROM flow_reference_attestations WHERE id=?', (key,)).fetchone()
    receipt = ReferenceUploadStore(store.path).read_verified('flow_veo', project_id,
        attestation['account_id'], asset)
    data = (Path(evidence_dir) / (attestation['readback']['sha256'] + '.jpg')).read_bytes()
    recomputed = reference_attestation(asset, receipt, BoundMedia(data, attestation['readback']),
        project_id=project_id, media_id=media_id)
    if persisted != attestation or row != (canonical_json(attestation),) or recomputed != attestation:
        raise OwnerAmbiguityGate('CANONICAL_REFERENCE_ATTESTATION_INVALID')
    return attestation
