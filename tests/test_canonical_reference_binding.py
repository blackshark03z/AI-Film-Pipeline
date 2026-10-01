import copy
import hashlib
import json
from types import SimpleNamespace
import sqlite3
from urllib.parse import urlencode, parse_qs
from unittest.mock import Mock

import pytest

from film_pipeline.providers.flow_media import parse_media_resource, bind_media_bytes, BoundMedia
from film_pipeline.providers.flow_reference_binding import reference_attestation
from film_pipeline.providers.flow_reference_upload import OwnerAmbiguityGate
from film_pipeline.providers.flow_canonical_ui import validate_native_request, OneGenerateGuard, verify_chip
from film_pipeline.providers import flow_rpc_contract as c
from test_reference_reconcilable_transport import png, PROJECT, REMOTE, OTHER
from test_flow_contract_20261001 import make_veo31_video_record, TEST_JOB_ID
from film_pipeline.providers.flow_r2v_prompt import film_marker


def bound(data=None, identity=REMOTE):
    data = data or png()
    url = f'https://flow-content.google/image/{identity}?signature=test'
    meta = [None] * 14
    meta[10], meta[13] = url, len(data)
    image = [None] * 7
    image[3], image[6] = url, 'image/png'
    row = [identity, PROJECT, None, 'CAE', None, meta, [None, image, [128, 72]]]
    resource = parse_media_resource(row, media_id=identity, project_id=PROJECT, kind='image')
    headers = {'content-type': 'image/png', 'content-length': str(len(data))}
    media = bind_media_bytes(resource, data=data, response_url=url, status=200, headers=headers)
    return row, resource, headers, media


def test_exact_requested_id_resource_bytes_binding():
    _, _, _, media = bound()
    assert media.evidence['media_id'] == REMOTE
    assert media.evidence['sha256'] == hashlib.sha256(png()).hexdigest()


@pytest.mark.parametrize('defect', ['echo', 'project', 'url', 'secondary', 'size', 'mime', 'dimensions', 'conflict'])
def test_binding_rejects_wrong_resource_or_metadata(defect):
    row, _, _, _ = bound()
    if defect == 'echo': row[0] = OTHER
    elif defect == 'project': row[1] = OTHER
    elif defect == 'url': row[5][10] = row[6][1][3] = f'https://flow-content.google/image/{OTHER}'
    elif defect == 'secondary': row[6][1][3] += 'different'
    elif defect == 'size': row[5][13] = 0
    elif defect == 'mime': row[6][1][6] = 'text/html'
    elif defect == 'dimensions': row[6][2] = [True, 72]
    elif defect == 'conflict': row[4] = f'https://flow-content.google/image/{OTHER}'
    with pytest.raises(c.ContractError):
        parse_media_resource(row, media_id=REMOTE, project_id=PROJECT, kind='image')


@pytest.mark.parametrize('defect', ['redirect', 'url', 'mime', 'size', 'bytes', 'encoding'])
def test_returned_bytes_must_match_exact_download_contract(defect):
    _, resource, headers, media = bound()
    options = dict(data=media.data, response_url=resource.url, status=200, headers=headers)
    if defect == 'redirect': options['status'] = 302
    elif defect == 'url': options['response_url'] += 'changed'
    elif defect == 'mime': headers['content-type'] = 'text/html'
    elif defect == 'size': headers['content-length'] = '1'
    elif defect == 'bytes': options['data'] = b'x' * len(media.data)
    else: headers['content-encoding'] = 'gzip'
    with pytest.raises(c.ContractError): bind_media_bytes(resource, **options)


def test_canonical_success_and_geometric_conflation_rejected(tmp_path):
    data = png()
    source = tmp_path / 'canonical.png'
    source.write_bytes(data)
    asset = SimpleNamespace(uri_or_path=str(source), origin='reference', asset_type='image',
        sha256=hashlib.sha256(data).hexdigest(), asset_id='asset_test')
    _, _, _, media = bound(data)
    receipt = {'id': 'receipt', 'asset_id': asset.asset_id, 'reference_sha256': asset.sha256,
        'project_id': PROJECT, 'media_id': REMOTE, 'provider_media_sha256': media.evidence['sha256'], 'account_id': 'test'}
    proof = reference_attestation(asset, receipt, media, project_id=PROJECT, media_id=REMOTE)
    assert proof['comparison']['strong_match']
    # Even internally consistent ID/receipt/bytes cannot qualify wrong content.
    _, _, _, geometric = bound(png((220, 10, 10), pattern=False), identity=OTHER)
    wrong = {**receipt, 'media_id': OTHER, 'provider_media_sha256': geometric.evidence['sha256']}
    with pytest.raises(OwnerAmbiguityGate, match='CONTENT_MISMATCH'):
        reference_attestation(asset, wrong, geometric, project_id=PROJECT, media_id=OTHER)
    with pytest.raises(OwnerAmbiguityGate):
        reference_attestation(asset, receipt, geometric, project_id=PROJECT, media_id=REMOTE)


def request(reference=REMOTE, model='veo_3_1_r2v_lite'):
    body = c.build_video_v2026_10_01(PROJECT, 'exact prompt', reference, 'same.png',
        'test_token_not_real', OTHER, model=model)
    envelope = json.loads(body)
    payload = json.loads(envelope[0][0][1])
    payload[0][0][0] = [None, None, [[['exact prompt']]]]
    envelope[0][0][1] = json.dumps(payload)
    body = json.dumps(envelope)
    return urlencode({'f.req': body})


def test_wrong_reference_blocks_browser_request_and_duplicate_cannot_dispatch():
    store = Mock()
    job = SimpleNamespace(provider_job_id=TEST_JOB_ID, correlation_evidence={'prompt': 'exact prompt'})
    store.read_provider_job.return_value.dispatch_count = 1
    def route(body):
        r = Mock()
        r.request.method = 'POST'
        r.request.url = 'https://flow.google.com/_/AiSandboxAngularFrontend/data/batchexecute?rpcids=MZZa6b'
        r.request.post_data = body
        return r
    guard = OneGenerateGuard(store, job, PROJECT, REMOTE)
    guard.armed = True
    bad = route(request(OTHER))
    guard.route(bad)
    bad.abort.assert_called_once(); bad.continue_.assert_not_called()
    assert guard.sent == 0
    guard = OneGenerateGuard(store, job, PROJECT, REMOTE); guard.armed = True
    first, duplicate = route(request()), route(request())
    guard.route(first); guard.route(duplicate)
    first.continue_.assert_called_once(); duplicate.abort.assert_called_once()
    assert guard.sent == 1 and guard.seen == 2


def test_prompt_elsewhere_does_not_authorize_wrong_creative_ast():
    envelope = json.loads(parse_qs(request())['f.req'][0])
    payload = json.loads(envelope[0][0][1])
    payload[0][0][0] = [None, None, [[['WRONG CREATIVE PROMPT']]]]
    payload[1].append('exact prompt')
    envelope[0][0][1] = json.dumps(payload)
    with pytest.raises(OwnerAmbiguityGate):
        validate_native_request('POST',
            'https://flow.google.com/_/AiSandboxAngularFrontend/data/batchexecute?rpcids=MZZa6b',
            urlencode({'f.req': json.dumps(envelope)}), project_id=PROJECT,
            reference_id=REMOTE, prompt='exact prompt')


@pytest.mark.parametrize('reference', [OTHER, '347f9951-5bbc-4910-b6fd-3a17c74e29d2'])
def test_backend_reference_must_equal_canonical(reference):
    marker = film_marker(TEST_JOB_ID)
    row = make_veo31_video_record(OTHER, PROJECT, reference, 'same.png', marker, model='veo_3_1_r2v_lite')
    with pytest.raises(c.ContractError):
        c.match_r2v_output_v2026_10_01([row], PROJECT, REMOTE, 'same.png', TEST_JOB_ID, baseline_ids=[], model='veo_3_1_r2v_lite')


def test_native_text_ast_requires_exact_single_reference_and_marker():
    marker = film_marker(TEST_JOB_ID)
    row = make_veo31_video_record(OTHER, PROJECT, REMOTE, 'same.png', marker, model='veo_3_1_r2v_lite')
    row[5][6][2][0][2][0] = [[marker]]
    def match(value):
        return c.match_r2v_output_v2026_10_01([value], PROJECT, REMOTE, 'same.png', TEST_JOB_ID, baseline_ids=[], model='veo_3_1_r2v_lite')
    assert match(row) == row
    bad = copy.deepcopy(row); bad[5][6][1][1].append([None, 4, OTHER])
    with pytest.raises(c.ContractError): match(bad)
    bad = copy.deepcopy(row); bad[5][6][2] = None
    with pytest.raises(c.ContractError): match(bad)
    bad = copy.deepcopy(row); bad[5][1] += marker
    with pytest.raises(c.ContractError): match(bad)


def test_ui_chip_wrong_id_blocks_mutation():
    page = Mock()
    page.locator.return_value.count.return_value = 1
    page.locator.return_value.get_attribute.return_value = f'https://flow-content.google/image/{OTHER}?signature=test'
    with pytest.raises(OwnerAmbiguityGate): verify_chip(page, REMOTE)


@pytest.mark.parametrize('defect', ['none', 'bytes', 'json', 'db', 'id', 'receipt'])
def test_persisted_attestation_recomputes_all_evidence(tmp_path, monkeypatch, defect):
    from test_reference_reconcilable_transport import setup, ACCOUNT
    from film_pipeline.store import SQLiteStore
    from film_pipeline.providers.flow_reference_binding import attest_existing_reference, verify_attestation
    from film_pipeline.providers.flow_reference_upload import ReferenceUploadStore
    asset, upload_store, session, transport, key = setup(tmp_path)
    receipt = transport.ensure_verified(asset)  # Offline transport double only.
    runtime = SQLiteStore(upload_store.db_path)
    session.bound_media = lambda identity, kind: bound()[3]
    directory = tmp_path / 'attestation'
    proof = attest_existing_reference(runtime, asset, session, account_id=ACCOUNT,
        media_id=REMOTE, evidence_dir=directory)
    assert session.uploads == 1  # Attestation never calls upload.
    if defect == 'bytes': (directory / (proof['readback']['sha256'] + '.jpg')).write_bytes(b'corrupt')
    elif defect == 'json': (directory / (proof['attestation_id'] + '.json')).write_text('{}')
    elif defect == 'db':
        with sqlite3.connect(runtime.path) as db:
            with pytest.raises(sqlite3.IntegrityError):
                db.execute("UPDATE flow_reference_attestations SET payload='{}'")
            db.execute('DROP TRIGGER reference_attestation_no_update')
            db.execute("UPDATE flow_reference_attestations SET payload='{}'")
    elif defect == 'id': proof['attestation_id'] = '../outside'
    elif defect == 'receipt':
        monkeypatch.setattr(ReferenceUploadStore, 'read_verified', lambda *args: {**receipt, 'media_id': OTHER})
    if defect == 'none':
        assert verify_attestation(runtime, asset, proof, media_id=REMOTE, project_id=PROJECT, evidence_dir=directory) == proof
    else:
        with pytest.raises(OwnerAmbiguityGate):
            verify_attestation(runtime, asset, proof, media_id=REMOTE, project_id=PROJECT, evidence_dir=directory)
