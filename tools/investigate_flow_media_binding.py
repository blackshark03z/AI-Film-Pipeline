"""Bounded read-only forensic probe; no mutation or automatic retry path.

Uses the already-bound qualification profile, one fixed project, existing IDs,
and ordinary browser authentication. Raw responses and signed URLs are never
written. Repeated *successful* reads are explicit differential controls.
"""
from __future__ import annotations

import hashlib
import io
import json
import re
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

from PIL import Image

from film_pipeline.providers import flow_rpc_contract as contract
from film_pipeline.providers.flow_reference_rpc import FlowReferenceRpcSession
from film_pipeline.providers.flow_reference_transport import image_comparison

ROOT = Path(__file__).resolve().parents[1]
PROJECT = 'f6b40e79-d6f8-4354-80ae-c863260e96f5'
REFERENCE = '347f9951-5bbc-4910-b6fd-3a17c74e29d2'
CONTROL = '53b5a413-7bb5-4f97-9be4-2461794a7d80'
SHOT_A = 'a47636b8-f7fb-4d99-8100-4cb5d989da8d'
PROFILE = Path('D:/Video/AutoVideoPipeline/scratch/google_flow_slice0011_manual')
SOURCE = ROOT / 'projects/character_continuity/slice0011/reference/31ca872d7b608dee61db0f0bdc753e4acaf659c428706ff7da88dfee98c3e531.png'
OUTPUT = ROOT / 'projects/character_continuity/reference_binding_20261001'
UUID = re.compile(r'(?i)[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}')


def digest(value):
    return hashlib.sha256(value if isinstance(value, bytes) else value.encode()).hexdigest()


def safe_url(value):
    parsed = urlsplit(value)
    exact = re.fullmatch(r'/(image|video)/(' + UUID.pattern.removeprefix('(?i)') + r')', parsed.path, re.I)
    return {'scheme': parsed.scheme, 'host': parsed.hostname,
        'path': parsed.path if parsed.hostname == 'flow-content.google' and exact else '<redacted>',
        'path_sha256': digest(parsed.path), 'path_media_ids': UUID.findall(parsed.path),
        'query_keys': sorted(parse_qs(parsed.query)), 'query_values': '<redacted>',
        'fragment_present': bool(parsed.fragment)}


def redacted(value):
    if isinstance(value, list):
        return [redacted(item) for item in value]
    if isinstance(value, dict):
        return {'<key-sha256:' + digest(key) + '>': redacted(item) for key, item in value.items()}
    if isinstance(value, str):
        if value.startswith(('http://', 'https://')):
            return {'url': safe_url(value)}
        if UUID.fullmatch(value):
            return value
        return {'string_length': len(value), 'string_sha256': digest(value),
            'contained_media_ids': UUID.findall(value)}
    return value


def strings(value, path='$'):
    if isinstance(value, str):
        yield path, value
    elif isinstance(value, list):
        for index, item in enumerate(value):
            yield from strings(item, f'{path}[{index}]')
    elif isinstance(value, dict):
        for key, item in value.items():
            yield from strings(item, path + '[key-sha256:' + digest(key) + ']')


def save(report):
    (OUTPUT / 'evidence.json').write_text(json.dumps(report, indent=2) + '\n', encoding='utf-8')


class ReadOnlySession(FlowReferenceRpcSession):
    def _rpc_body(self, rpc_id, body, **kwargs):
        if rpc_id not in {contract.RPC_CATALOG, contract.RPC_MEDIA}:
            raise RuntimeError('READ_ONLY_RPC_REQUIRED')
        return super()._rpc_body(rpc_id, body, **kwargs)

    def captcha(self, action):
        raise RuntimeError('NO_GENERATION_ACTION_ALLOWED')

    def upload_reference(self, *args, **kwargs):
        raise RuntimeError('NO_UPLOAD_ALLOWED')

    def submit_once(self, *args, **kwargs):
        raise RuntimeError('NO_GENERATE_ALLOWED')


def main():
    OUTPUT.mkdir(parents=True, exist_ok=True)
    if (OUTPUT / 'evidence.json').exists():
        raise RuntimeError('FORENSIC_RUN_EXISTS_NO_AUTOMATIC_RERUN')
    source = SOURCE.read_bytes()
    report = {'project_id': PROJECT, 'source_sha256': digest(source),
        'probe_policy': 'Two explicit successful reads per ID in one session; fail stops; no retries',
        'generate_actions': 0, 'reference_uploads': 0, 'retries': 0,
        'profile_path_sha256': digest(str(PROFILE)), 'observations': [],
        'source_files': {p: digest((ROOT / p).read_bytes()) for p in (
            'src/film_pipeline/providers/flow_reference_rpc.py',
            'src/film_pipeline/providers/flow_rpc_contract.py',
            'src/film_pipeline/providers/flow_reference_transport.py',
            'tools/investigate_flow_media_binding.py')}}
    save(report)
    try:
        with ReadOnlySession(profile_path=PROFILE, project_id=PROJECT, native_ui=True) as session:
            records = session.catalog(contract_version=contract.CONTRACT_VERSION_2026_10_01)
            report['catalog_before'] = redacted(records)
            report['catalog_ids_before'] = [row[0] for row in records]
            for target in (REFERENCE, CONTROL, SHOT_A):
                if sum(row[0] == target for row in records) != 1:
                    raise RuntimeError('EXACT_EXISTING_CONTROL_REQUIRED')
            save(report)
            for round_no in (1, 2):
                for media_id, kind in ((REFERENCE, 'image'), (CONTROL, 'image'), (SHOT_A, 'video')):
                    body = contract.build_media(media_id)
                    item = {'round': round_no, 'requested_id': media_id, 'kind': kind,
                        'request_envelope': json.loads(body), 'request_sha256': digest(body)}
                    report['observations'].append(item)
                    text = session._rpc_body(contract.RPC_MEDIA, body,
                        on_http_response=lambda status, length: item.update(
                            rpc_status=status, rpc_response_bytes=length))
                    payload = contract.parse_rpc(text, contract.RPC_MEDIA)
                    item['rpc_response_sha256'] = digest(text)
                    item['response_structure'] = redacted(payload)
                    leaves = list(strings(payload))
                    item['response_ids'] = [{'slot': path, 'ids': UUID.findall(value),
                        'exact_id_string': bool(UUID.fullmatch(value))}
                        for path, value in leaves if UUID.search(value)]
                    urls = [(path, value) for path, value in leaves if value.startswith('https://')]
                    item['url_candidates'] = [{'slot': path, **safe_url(value)} for path, value in urls]
                    candidates = {value for _, value in urls if urlsplit(value).hostname == 'flow-content.google'
                        and urlsplit(value).path.startswith(f'/{kind}/')}
                    item['legacy_candidate_count'] = len(candidates)
                    save(report)
                    if len(candidates) != 1:
                        raise RuntimeError('RESOURCE_CANDIDATES_NOT_UNIQUE')
                    target_url = next(iter(candidates))
                    item['requested_resource'] = safe_url(target_url)
                    response = session.page.context.request.get(target_url,
                        timeout=60000, max_redirects=0, max_retries=0)
                    try:
                        item['resource_status'] = response.status
                        item['response_resource'] = safe_url(response.url)
                        item['headers'] = {k: response.headers[k] for k in (
                            'content-type', 'content-length', 'content-encoding', 'cache-control',
                            'age', 'date', 'etag', 'last-modified', 'vary') if k in response.headers}
                        if 'location' in response.headers:
                            item['redirect_location'] = safe_url(response.headers['location'])
                        if response.status != 200:
                            raise RuntimeError('RESOURCE_READ_UNQUALIFIED_NO_RETRY')
                        data = response.body()
                        item['bytes_sha256'], item['byte_size'] = digest(data), len(data)
                        suffix = '.png' if kind == 'image' else '.mp4'
                        path = OUTPUT / f'{media_id}_r{round_no}_{digest(data)}{suffix}'
                        with path.open('xb') as stream:
                            stream.write(data)
                        item['local_artifact'] = str(path)
                        if kind == 'image':
                            with Image.open(io.BytesIO(data)) as image:
                                image.load()
                                item['image_metadata'] = {'format': image.format,
                                    'mode': image.mode, 'width': image.width, 'height': image.height}
                            item['comparison'] = image_comparison(source, data)
                    finally:
                        response.dispose()
                    save(report)
                    print(json.dumps({k: item[k] for k in ('round', 'requested_id',
                        'legacy_candidate_count', 'requested_resource', 'bytes_sha256', 'byte_size')}) , flush=True)
            after = session.catalog(contract_version=contract.CONTRACT_VERSION_2026_10_01)
            report['catalog_after'] = redacted(after)
            report['catalog_ids_after'] = [row[0] for row in after]
            report['catalog_id_set_unchanged'] = sorted(report['catalog_ids_before']) == sorted(report['catalog_ids_after'])
            report['rpc_counts'] = session.rpc_call_counts
            report['completed'] = True
            save(report)
    except Exception as exc:
        report['error_type'] = type(exc).__name__
        report['completed'] = False
        save(report)
        print(json.dumps({'stopped': True, 'error_type': type(exc).__name__}), flush=True)
        return 1
    print(json.dumps({'completed': True, 'evidence': str(OUTPUT / 'evidence.json'),
        'rpc_counts': report['rpc_counts']}), flush=True)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
