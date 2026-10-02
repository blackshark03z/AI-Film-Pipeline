"""Additive canonical reference attestations; existing upload history is read-only.

Adoption path: media that already exists in the qualified provider project
(uploaded outside this system, e.g. by the Owner) can be adopted as a
canonical Film reference through an attested readback — a purely READ-ONLY
provider access. Adoption never uploads, re-uploads or replaces anything; it
registers the exact bytes the provider already serves under an exact media
identity in the exact project scope, then runs the same attestation chain as
an uploaded reference.
"""
from __future__ import annotations

import hashlib
import os
import re
import io
from contextlib import closing
from datetime import datetime, timezone
from pathlib import Path

from ..core import canonical_json, sha256
from .flow_media import BoundMedia, VERSION
from .flow_reference_transport import image_comparison
from .flow_reference_upload import OwnerAmbiguityGate, ReferenceUploadStore

ADOPTION_BASIS = 'readback_adoption_of_existing_project_media'


class AdoptedReferenceStore:
    """Immutable receipts for project media adopted via attested readback."""

    def __init__(self, db_path: Path):
        self.db_path = Path(db_path)

    def _connect(self):
        import sqlite3

        connection = sqlite3.connect(self.db_path)
        connection.execute('PRAGMA synchronous=FULL')
        return connection

    def initialize(self) -> None:
        connection = self._connect()
        try:
            connection.execute("""
                CREATE TABLE IF NOT EXISTS reference_adoptions (
                    id TEXT PRIMARY KEY,
                    provider_id TEXT NOT NULL,
                    project_id TEXT NOT NULL,
                    account_id TEXT NOT NULL,
                    asset_id TEXT NOT NULL,
                    reference_sha256 TEXT NOT NULL,
                    media_id TEXT NOT NULL,
                    provider_media_sha256 TEXT NOT NULL,
                    basis TEXT NOT NULL,
                    adopted_at TEXT NOT NULL,
                    payload TEXT NOT NULL,
                    UNIQUE(provider_id,project_id,media_id)
                )""")
            for action in ('UPDATE', 'DELETE'):
                connection.execute(f'CREATE TRIGGER IF NOT EXISTS reference_adoptions_no_{action.lower()} '
                    f'BEFORE {action} ON reference_adoptions BEGIN '
                    "SELECT RAISE(ABORT,'immutable reference adoption'); END")
            connection.execute("""CREATE TABLE IF NOT EXISTS reference_adoption_events (
                    reservation_id TEXT NOT NULL, sequence INTEGER NOT NULL, stage TEXT NOT NULL,
                    payload TEXT NOT NULL, at TEXT NOT NULL, previous TEXT NOT NULL, digest TEXT NOT NULL,
                    PRIMARY KEY(reservation_id,sequence))""")
            for action in ('UPDATE', 'DELETE'):
                connection.execute(f'CREATE TRIGGER IF NOT EXISTS ref_adoption_events_no_{action.lower()} '
                    f'BEFORE {action} ON reference_adoption_events BEGIN '
                    "SELECT RAISE(ABORT,'immutable reference adoption event'); END")
            connection.commit()
        finally:
            connection.close()

    def record(self, *, provider_id: str, project_id: str, account_id: str,
               asset_id: str, reference_sha256: str, media_id: str,
               provider_media_sha256: str) -> dict:
        self.initialize()
        basis = {'provider_id': provider_id, 'project_id': project_id.lower(),
                 'account_id': account_id, 'asset_id': asset_id,
                 'reference_sha256': reference_sha256, 'media_id': media_id.lower()}
        receipt = {'id': 'refadopt_' + sha256(basis), 'provider_id': provider_id,
            'project_id': project_id.lower(), 'account_id': account_id,
            'asset_id': asset_id, 'reference_sha256': reference_sha256,
            'media_id': media_id, 'provider_media_sha256': provider_media_sha256,
            'basis': ADOPTION_BASIS,
            'adopted_at': datetime.now(timezone.utc).isoformat()}
        connection = self._connect()
        try:
            with connection:
                connection.execute('INSERT OR IGNORE INTO reference_adoptions '
                    '(id,provider_id,project_id,account_id,asset_id,reference_sha256,'
                    'media_id,provider_media_sha256,basis,adopted_at,payload) '
                    'VALUES (?,?,?,?,?,?,?,?,?,?,?)',
                    (receipt['id'], receipt['provider_id'], receipt['project_id'],
                     receipt['account_id'], receipt['asset_id'], receipt['reference_sha256'],
                     receipt['media_id'], receipt['provider_media_sha256'],
                     receipt['basis'], receipt['adopted_at'], canonical_json(receipt)))
                row = connection.execute('SELECT payload FROM reference_adoptions WHERE id=?',
                    (receipt['id'],)).fetchone()
                stored = json_loads(row[0])
                if row[0] != canonical_json(receipt):
                    # Idempotent re-adoption of the identical fact is accepted;
                    # anything else is a collision.
                    if {**stored, 'adopted_at': None} != {**receipt, 'adopted_at': None}:
                        raise OwnerAmbiguityGate('REFERENCE_ADOPTION_COLLISION')
                    receipt = stored
                else:
                    self._append_event(connection, receipt['id'], 'ADOPT_READBACK_OBSERVED',
                                       receipt)
        finally:
            connection.close()
        return receipt

    def _append_event(self, connection, reservation_id, stage, payload):
        previous = connection.execute('SELECT sequence,digest FROM reference_adoption_events '
            'WHERE reservation_id=? ORDER BY sequence DESC LIMIT 1',
            (reservation_id,)).fetchone()
        seq, prior = (previous[0] + 1, previous[1]) if previous else (1, '0' * 64)
        at = datetime.now(timezone.utc).isoformat()
        digest = sha256({'id': reservation_id, 'sequence': seq, 'stage': stage,
                         'payload': payload, 'at': at, 'previous': prior})
        connection.execute('INSERT INTO reference_adoption_events VALUES (?,?,?,?,?,?,?)',
            (reservation_id, seq, stage, canonical_json(payload), at, prior, digest))

    def read_adopted(self, provider_id: str, project_id: str, account_id: str,
                     asset, media_id: str) -> dict:
        """Re-derive the adoption receipt; any drift or tampering fails closed."""
        from ..live_runtime import file_sha256

        path = Path(asset.uri_or_path)
        if not path.is_file() or file_sha256(path) != asset.sha256:
            raise OwnerAmbiguityGate('CANONICAL_REFERENCE_BYTES_CHANGED')
        self.initialize()
        connection = self._connect()
        try:
            rows = connection.execute('SELECT id,payload FROM reference_adoptions '
                'WHERE provider_id=? AND project_id=? AND account_id=? AND asset_id=? '
                'AND media_id=?', (provider_id, project_id.lower(), account_id,
                                   asset.asset_id, media_id)).fetchall()
            if len(rows) != 1:
                raise OwnerAmbiguityGate('REFERENCE_ADOPTION_NOT_UNIQUE')
            receipt = json_loads(rows[0][1])
            if (rows[0][0] != receipt.get('id') or receipt.get('basis') != ADOPTION_BASIS
                    or receipt.get('reference_sha256') != asset.sha256
                    or receipt.get('provider_media_sha256') is None
                    or not re.fullmatch(r'[0-9a-f]{64}', receipt['provider_media_sha256'])
                    or canonical_json(receipt) != rows[0][1]):
                raise OwnerAmbiguityGate('REFERENCE_ADOPTION_RECEIPT_INVALID')
            events = connection.execute('SELECT stage,payload FROM reference_adoption_events '
                'WHERE reservation_id=? ORDER BY sequence', (receipt['id'],)).fetchall()
        finally:
            connection.close()
        if [(stage, payload) for stage, payload in events] != \
                [('ADOPT_READBACK_OBSERVED', canonical_json(receipt))]:
            raise OwnerAmbiguityGate('REFERENCE_ADOPTION_EVENT_MISMATCH')
        return receipt


def json_loads(text):
    import json

    return json.loads(text)


def adopt_existing_reference(store, session, *, account_id: str, media_id: str,
                             reference_dir) -> tuple:
    """Adopt one existing project media as a canonical Film reference.

    Read-only provider access: one attested readback of the exact media id in
    the exact project scope. No upload, no re-upload, no substitution of any
    external resource. The canonical Film asset is registered from the exact
    adopted bytes, and the same immutable attestation chain as uploaded
    references is then satisfied (local bytes == readback bytes == provider
    resource for that exact identity).
    """
    from ..live_runtime import Asset
    from .flow_rpc_contract import UUID_RE

    if not UUID_RE.fullmatch(media_id or ''):
        raise OwnerAmbiguityGate('REFERENCE_MEDIA_ID_INVALID')
    store.initialize()
    media = session.bound_media(media_id, 'image')
    directory = Path(reference_dir)
    directory.mkdir(parents=True, exist_ok=True)
    local_path = directory / (media.evidence['sha256'] + '.png')
    if local_path.exists():
        if local_path.read_bytes() != media.data:
            raise OwnerAmbiguityGate('REFERENCE_ADOPTION_BYTES_CONFLICT')
    else:
        with local_path.open('xb') as stream:
            stream.write(media.data)
            stream.flush()
            os.fsync(stream.fileno())
    asset = Asset(asset_id='asset_' + sha256({'origin': 'reference',
                      'provider': 'flow_veo', 'project': session.project_id,
                      'media_id': media_id, 'sha256': media.evidence['sha256']}),
        origin='reference', asset_type='image', uri_or_path=str(local_path),
        sha256=media.evidence['sha256'], mime_type=media.evidence['mime_type'],
        width=media.evidence['width'], height=media.evidence['height'],
        file_size=len(media.data),
        rights_metadata={'source_kind': 'provider_readback_adoption',
                         'adopted_provider_media_id': media_id,
                         'adoption_basis': ADOPTION_BASIS})
    store.save_reference_asset(asset)
    receipt = AdoptedReferenceStore(store.path).record(
        provider_id='flow_veo', project_id=session.project_id, account_id=account_id,
        asset_id=asset.asset_id, reference_sha256=asset.sha256, media_id=media_id,
        provider_media_sha256=media.evidence['sha256'])
    attestation = reference_attestation(asset, receipt, media,
        project_id=session.project_id, media_id=media_id)
    evidence_dir = directory / 'attestation'
    evidence_dir.mkdir(parents=True, exist_ok=True)
    resource_path = evidence_dir / (media.evidence['sha256'] + '.jpg')
    if resource_path.exists():
        if resource_path.read_bytes() != media.data:
            raise OwnerAmbiguityGate('REFERENCE_EVIDENCE_BYTES_CONFLICT')
    else:
        with resource_path.open('xb') as stream:
            stream.write(media.data)
            stream.flush()
            os.fsync(stream.fileno())
    write_immutable(evidence_dir / (attestation['attestation_id'] + '.json'), attestation)
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
    return asset, attestation


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
    if attestation.get('upload_receipt_id', '').startswith('refadopt_'):
        receipt = AdoptedReferenceStore(store.path).read_adopted(
            'flow_veo', project_id, attestation['account_id'], asset, media_id)
    else:
        receipt = ReferenceUploadStore(store.path).read_verified('flow_veo', project_id,
            attestation['account_id'], asset)
    data = (Path(evidence_dir) / (attestation['readback']['sha256'] + '.jpg')).read_bytes()
    recomputed = reference_attestation(asset, receipt, BoundMedia(data, attestation['readback']),
        project_id=project_id, media_id=media_id)
    if persisted != attestation or row != (canonical_json(attestation),) or recomputed != attestation:
        raise OwnerAmbiguityGate('CANONICAL_REFERENCE_ATTESTATION_INVALID')
    return attestation
