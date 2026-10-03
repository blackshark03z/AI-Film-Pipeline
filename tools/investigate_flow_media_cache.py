"""One explicit no-cache read per existing image; no query rewriting or retries."""
import json

from investigate_flow_media_binding import (OUTPUT, PROFILE, PROJECT, REFERENCE,
    CONTROL, ReadOnlySession, contract, digest, redacted, safe_url)


def main():
    path = OUTPUT / 'cache_control_evidence.json'
    if path.exists():
        raise RuntimeError('CACHE_PROBE_EXISTS_NO_AUTOMATIC_RERUN')
    report = {'request_headers': {'Cache-Control': 'no-cache, max-age=0', 'Pragma': 'no-cache'},
        'project': PROJECT, 'generate_actions': 0, 'reference_uploads': 0,
        'retries': 0, 'observations': []}
    def save():
        path.write_text(json.dumps(report, indent=2) + '\n', encoding='utf-8')
    save()
    try:
        with ReadOnlySession(profile_path=PROFILE, project_id=PROJECT, native_ui=True) as s:
            for media_id in (REFERENCE, CONTROL):
                payload = s.rpc(contract.RPC_MEDIA, contract.build_media(media_id))
                item = {'requested_id': media_id, 'response_structure': redacted(payload)}
                report['observations'].append(item)
                if (len(payload) != 7 or payload[0] != media_id or payload[1] != PROJECT
                        or payload[5][10] != payload[6][1][3]):
                    raise RuntimeError('CACHE_CONTROL_IDENTITY_CONFLICT')
                url = payload[5][10]
                if safe_url(url)['path'] != f'/image/{media_id}':
                    raise RuntimeError('CACHE_CONTROL_RESOURCE_CONFLICT')
                item['resource'] = safe_url(url)
                response = s.page.context.request.get(url, headers=report['request_headers'],
                    timeout=60000, max_redirects=0, max_retries=0)
                try:
                    item['status'] = response.status
                    item['response_resource'] = safe_url(response.url)
                    item['headers'] = {k: response.headers[k] for k in (
                        'content-type', 'content-length', 'cache-control', 'age', 'date',
                        'etag', 'last-modified') if k in response.headers}
                    if response.status != 200:
                        raise RuntimeError('CACHE_CONTROL_FAILED_NO_RETRY')
                    data = response.body()
                    item['bytes_sha256'], item['byte_size'] = digest(data), len(data)
                finally:
                    response.dispose()
                save()
                print(json.dumps(item), flush=True)
            report['rpc_counts'] = s.rpc_call_counts
            report['completed'] = True
    except Exception as exc:
        report['completed'] = False
        report['error_type'] = type(exc).__name__
        save()
        return 1
    save()
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
