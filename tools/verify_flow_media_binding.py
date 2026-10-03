"""Offline custody/identity checks for the bounded reference investigation.

This verifies captured evidence, not a globally stable Google API contract.
No browser, provider request, runtime ledger, or mutation is used.
"""
from __future__ import annotations

import copy
import hashlib
import io
import json
from pathlib import Path

from PIL import Image
from film_pipeline.providers.flow_reference_transport import image_comparison

ROOT = Path(__file__).resolve().parents[1]
FOLDER = ROOT / 'projects/character_continuity/reference_binding_20261001'
PROJECT = 'f6b40e79-d6f8-4354-80ae-c863260e96f5'
TARGET = '347f9951-5bbc-4910-b6fd-3a17c74e29d2'
CONTROL = '53b5a413-7bb5-4f97-9be4-2461794a7d80'
A = 'a47636b8-f7fb-4d99-8100-4cb5d989da8d'


def digest(data):
    return hashlib.sha256(data if isinstance(data, bytes) else data.encode()).hexdigest()


def require(condition, code):
    if not condition:
        raise ValueError(code)


def verify_observation(o, catalog):
    media_id, kind = o['requested_id'], o['kind']
    p = o['response_structure']
    require(media_id in {TARGET, CONTROL, A}, 'UNEXPECTED_CONTROL')
    require(kind == ('video' if media_id == A else 'image'), 'MEDIA_KIND')
    require(o['request_envelope'] == [[['as29s', json.dumps([media_id],
        separators=(',', ':')), None, 'generic']]], 'REQUEST_IDENTITY')
    require(o['rpc_status'] == 200 and p[0] == media_id, 'RESPONSE_IDENTITY')
    require(p[1] == PROJECT, 'RESPONSE_PROJECT')
    require(p[3]['string_sha256'] == digest('CAE'), 'RESPONSE_STATUS')
    require(len(p) == (7 if kind == 'image' else 8), 'RESPONSE_KIND_SHAPE')
    rows = [row for row in catalog if row[0] == media_id]
    require(len(rows) == 1, 'CATALOG_IDENTITY')
    row = rows[0]
    require((row[1], row[2], row[3], row[5][13]) ==
            (PROJECT, p[2], p[3], p[5][13]), 'CATALOG_METADATA')
    expected_path = f'/{kind}/{media_id}'
    for resource in (o['requested_resource'], o['response_resource']):
        require(resource['scheme'] == 'https' and resource['host'] == 'flow-content.google'
                and resource['path'] == expected_path
                and resource['path_media_ids'] == [media_id]
                and not resource['fragment_present'], 'RESOURCE_IDENTITY')
    require(o['legacy_candidate_count'] == 1, 'RESOURCE_CARDINALITY')
    require(o['resource_status'] == 200 and 'redirect_location' not in o, 'REDIRECT')
    data = Path(o['local_artifact']).read_bytes()
    require(digest(data) == o['bytes_sha256'], 'LOCAL_BYTES_HASH')
    require(len(data) == o['byte_size'] == p[5][13] == int(o['headers']['content-length']), 'BYTE_SIZE')
    if kind == 'image':
        first, second = p[5][10]['url'], p[6][1][3]['url']
        require(first == second == o['requested_resource'], 'IMAGE_RESOURCE_SLOTS')
        require(o['headers']['content-type'] == 'image/jpeg'
                and p[6][1][6]['string_sha256'] == digest('image/jpeg'), 'IMAGE_MIME')
        with Image.open(io.BytesIO(data)) as image:
            image.load()
            require(image.format == 'JPEG' and list(image.size) == p[6][2] == row[6][2]
                    == [o['image_metadata']['width'], o['image_metadata']['height']], 'IMAGE_DIMENSIONS')
    else:
        require(p[7][0][8]['url'] == o['requested_resource'], 'VIDEO_RESOURCE_SLOT')
        require(p[5][10]['url']['path'] == f'/image/{media_id}', 'THUMBNAIL_SEPARATE')
        require(p[5][6][1][1] == [[None, 4, TARGET]], 'SHOT_A_REFERENCE_LINEAGE')
        require(o['headers']['content-type'] == 'video/mp4', 'VIDEO_MIME')


def main():
    r = json.loads((FOLDER / 'evidence.json').read_text(encoding='utf-8'))
    cache = json.loads((FOLDER / 'cache_control_evidence.json').read_text(encoding='utf-8'))
    require(r['completed'] and cache['completed'], 'INCOMPLETE_PROBE')
    for name, expected in r['source_files'].items():
        require(digest((ROOT / name).read_bytes()) == expected, 'EXERCISED_SOURCE_CHANGED')
    require(r['rpc_counts'] == {'Zzl0ze': 2, 'as29s': 6}
            and cache['rpc_counts'] == {'as29s': 2}, 'READ_BUDGET')
    require(r['catalog_id_set_unchanged'] and r['catalog_ids_before'] == r['catalog_ids_after'], 'CATALOG_DELTA')
    for o in r['observations']:
        verify_observation(o, r['catalog_before'])
        verify_observation(o, r['catalog_after'])
    source = ROOT / 'projects/character_continuity/slice0011/reference/31ca872d7b608dee61db0f0bdc753e4acaf659c428706ff7da88dfee98c3e531.png'
    geometric = ROOT / 'projects/character_continuity/reference_qualification_20260930/reference/dc766e136c039ce4ae25f78dc7555c161a6178e8c835cf3d37600b4d7d0e8b0e.png'
    for o in r['observations']:
        if o['kind'] == 'image':
            require(image_comparison(source.read_bytes(), Path(o['local_artifact']).read_bytes()) == o['comparison'], 'COMPARISON_REPLAY')
    grouped = {media_id: [o for o in r['observations'] if o['requested_id'] == media_id]
        for media_id in (TARGET, CONTROL, A)}
    for media_id, observations in grouped.items():
        require([o['round'] for o in observations] == [1, 2]
                and observations[0]['bytes_sha256'] == observations[1]['bytes_sha256'], 'REPEAT_STABILITY')
    for o in cache['observations']:
        known = grouped[o['requested_id']][0]
        require(o['status'] == 200 and o['response_structure'][0] == o['requested_id']
                and o['response_structure'][1] == PROJECT
                and o['bytes_sha256'] == known['bytes_sha256']
                and o['response_resource'] == o['resource'] == known['requested_resource'], 'CACHE_CONTROL_IDENTITY')
    target, control = grouped[TARGET][0], grouped[CONTROL][0]
    require(not target['comparison']['strong_match'] and control['comparison']['strong_match'], 'CONTENT_VERDICT')
    geometric_match = image_comparison(geometric.read_bytes(), Path(target['local_artifact']).read_bytes())
    require(geometric_match['strong_match'], 'GEOMETRIC_FIXTURE_CONTENT')
    historical = []
    for name, media_id, sha in (
        ('projects/character_continuity/reference_qualification_20260930/qualification.json', TARGET, geometric_match['source_sha256']),
        ('projects/character_continuity/slice0011/frozen_reference_recovery.json', CONTROL, r['source_sha256'])):
        p = ROOT / name
        record = json.loads(p.read_text(encoding='utf-8'))
        require(record['media_id'] == media_id and record['reference_sha256'] == sha
                and record['provider_media_sha256'] == grouped[media_id][0]['bytes_sha256'], 'HISTORICAL_RECEIPT')
        historical.append({'path': name, 'sha256': digest(p.read_bytes()),
            'media_id': media_id, 'source_sha256': sha,
            'provider_media_sha256': record['provider_media_sha256']})
    rejected = []
    changes = {
        'wrong_echoed_id': lambda o: o['response_structure'].__setitem__(0, CONTROL),
        'wrong_echoed_project': lambda o: o['response_structure'].__setitem__(1, CONTROL),
        'wrong_request_id': lambda o: o.__setitem__('request_envelope', [[['as29s', json.dumps([CONTROL]), None, 'generic']]]),
        'wrong_resource_path': lambda o: o['requested_resource'].__setitem__('path', f'/image/{CONTROL}'),
        'wrong_resource_host': lambda o: o['requested_resource'].__setitem__('host', 'example.invalid'),
        'multiple_candidates': lambda o: o.__setitem__('legacy_candidate_count', 2),
        'redirect_status': lambda o: o.__setitem__('resource_status', 302),
        'redirect_location': lambda o: o.__setitem__('redirect_location', {}),
        'wrong_bytes_hash': lambda o: o.__setitem__('bytes_sha256', '0' * 64),
        'wrong_byte_size': lambda o: o.__setitem__('byte_size', 123),
        'wrong_dimensions': lambda o: o['image_metadata'].__setitem__('width', 1),
        'wrong_mime': lambda o: o['headers'].__setitem__('content-type', 'image/png'),
        'wrong_response_kind': lambda o: o['response_structure'].append(None),
    }
    for label, change in changes.items():
        candidate = copy.deepcopy(target)
        change(candidate)
        try:
            verify_observation(candidate, r['catalog_before'])
        except (ValueError, KeyError, IndexError):
            rejected.append(label)
        else:
            raise ValueError('NEGATIVE_CONTROL_ACCEPTED:' + label)
    summary = {'state': 'B. REFERENCE_BINDING_PROVEN_CONTENT_MISMATCH',
        'proof_state': 'PROVEN', 'verified_observations': len(r['observations']),
        'cache_controls': len(cache['observations']), 'negative_controls_rejected': rejected,
        'geometric_fixture_comparison': geometric_match, 'historical_receipts': historical,
        'binding_scope': 'Current served provider resources; no origin-cache freshness or global immutability claim',
        'evidence_sha256': digest((FOLDER / 'evidence.json').read_bytes()),
        'cache_evidence_sha256': digest((FOLDER / 'cache_control_evidence.json').read_bytes()),
        'verifier_sha256': digest(Path(__file__).read_bytes()),
        'generate_actions': 0, 'reference_uploads': 0, 'retries': 0}
    (FOLDER / 'offline_verification.json').write_text(json.dumps(summary, indent=2) + '\n', encoding='utf-8')
    print(json.dumps(summary, indent=2))


if __name__ == '__main__':
    main()
