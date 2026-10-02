"""Offline proofs for the read-only reference adoption path.

Adoption registers an existing provider project media as a canonical Film
reference via an attested readback — no upload, no re-upload, no substitution.
Every provider behavior is a frozen synthetic local double.
"""
import hashlib
from types import SimpleNamespace

import pytest

from film_pipeline.providers.flow_reference_binding import (
    AdoptedReferenceStore,
    adopt_existing_reference,
    verify_attestation,
)
from film_pipeline.providers.flow_reference_upload import OwnerAmbiguityGate
from film_pipeline.store import SQLiteStore
from test_canonical_reference_binding import bound, png
from test_reference_reconcilable_transport import ACCOUNT, OTHER, PROJECT, REMOTE


def adopt(tmp_path, *, media_id=REMOTE):
    store = SQLiteStore(tmp_path / 'runtime.sqlite')
    _row, _resource, _headers, media = bound(identity=media_id)
    session = SimpleNamespace(project_id=PROJECT,
                              bound_media=lambda mid, kind: media)
    return store, adopt_existing_reference(
        store, session, account_id=ACCOUNT, media_id=media_id,
        reference_dir=tmp_path / 'reference')


def test_adopt_registers_canonical_asset_and_attestation(tmp_path):
    store, (asset, attestation) = adopt(tmp_path)
    assert asset.origin == 'reference' and asset.asset_type == 'image'
    assert asset.sha256 == hashlib.sha256(png()).hexdigest()
    stored = store.read_reference_asset(asset.asset_id)
    assert (stored.sha256, stored.mime_type) == (asset.sha256, 'image/png')
    assert attestation['upload_receipt_id'].startswith('refadopt_')
    evidence_dir = tmp_path / 'reference' / 'attestation'
    verified = verify_attestation(store, stored, attestation, media_id=REMOTE,
                                  project_id=PROJECT, evidence_dir=evidence_dir)
    assert verified == attestation


def test_adoption_is_idempotent_for_identical_readback(tmp_path):
    store, (asset, attestation) = adopt(tmp_path)
    _row, _resource, _headers, media = bound()
    session = SimpleNamespace(project_id=PROJECT,
                              bound_media=lambda mid, kind: media)
    asset2, attestation2 = adopt_existing_reference(
        store, session, account_id=ACCOUNT, media_id=REMOTE,
        reference_dir=tmp_path / 'reference')
    assert (asset2.asset_id, attestation2) == (asset.asset_id, attestation)


def test_verify_rejects_wrong_media_identity(tmp_path):
    store, (asset, attestation) = adopt(tmp_path)
    stored = store.read_reference_asset(asset.asset_id)
    with pytest.raises(OwnerAmbiguityGate, match='ADOPTION'):
        verify_attestation(store, stored, attestation, media_id=OTHER,
                           project_id=PROJECT,
                           evidence_dir=tmp_path / 'reference' / 'attestation')


def test_verify_rejects_changed_local_bytes(tmp_path):
    store, (asset, attestation) = adopt(tmp_path)
    stored = store.read_reference_asset(asset.asset_id)
    stored = stored.model_copy(update={'sha256': 'a' * 64})
    with pytest.raises(OwnerAmbiguityGate, match='BYTES_CHANGED'):
        verify_attestation(store, stored, attestation, media_id=REMOTE,
                           project_id=PROJECT,
                           evidence_dir=tmp_path / 'reference' / 'attestation')


def test_adoption_receipt_is_immutable_and_journal_agreed(tmp_path):
    import sqlite3

    store, (asset, _attestation) = adopt(tmp_path)
    connection = sqlite3.connect(store.path)
    with pytest.raises(sqlite3.IntegrityError):
        connection.execute("UPDATE reference_adoptions SET media_id='" + OTHER + "'")
    with pytest.raises(sqlite3.IntegrityError):
        connection.execute('DELETE FROM reference_adoptions')
    # The adoption event journal is equally tamper-proof at the DB level.
    with pytest.raises(sqlite3.IntegrityError):
        connection.execute("UPDATE reference_adoption_events SET payload='{\"x\":1}'")
    with pytest.raises(sqlite3.IntegrityError):
        connection.execute('DELETE FROM reference_adoption_events')
    receipt = AdoptedReferenceStore(store.path).read_adopted(
        'flow_veo', PROJECT, ACCOUNT, store.read_reference_asset(asset.asset_id), REMOTE)
    assert receipt['basis'] == 'readback_adoption_of_existing_project_media'
