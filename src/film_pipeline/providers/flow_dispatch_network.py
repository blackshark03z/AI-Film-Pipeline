"""Passive recognition of one inspected experimental Generate RPC shape.

This recognizes browser observation only, not acceptance or idempotency.
Unknown current Flow/text-video shapes stay unqualified. No request is built.
"""
import hashlib
import json
from urllib.parse import parse_qs, urlsplit


CONTRACT = 'batchexecute-MZZa6b-observed-unqualified-v1'


def generate_request_metadata(method, url, body, project_id, prompt):
    parsed = urlsplit(url)
    if (method != 'POST' or parsed.scheme != 'https' or parsed.hostname != 'flow.google.com'
            or parsed.path != '/_/AiSandboxAngularFrontend/data/batchexecute'
            or not isinstance(body, str) or len(body.encode()) > 4 * 1024 * 1024):
        return None
    try:
        fields = parse_qs(body, max_num_fields=20)
        encoded = fields.get('f.req', [])
        if len(encoded) != 1:
            return None
        envelope = json.loads(encoded[0])
        calls = envelope[0]
        if not isinstance(calls, list) or len(calls) != 1:
            return None
        call = calls[0]
        if len(call) != 4 or call[0] != 'MZZa6b':
            return None
        payload = json.loads(call[1])
        # Exact values must appear in the same one-call payload; substring,
        # URL query, another RPC and generic POST activity cannot qualify.
        stack, strings, visited = [payload], set(), 0
        while stack:
            value = stack.pop()
            visited += 1
            if visited > 80_000:
                return None
            if isinstance(value, list): stack.extend(value)
            elif isinstance(value, dict): stack.extend(value.values())
            elif isinstance(value, str): strings.add(value)
        if project_id not in strings or prompt not in strings:
            return None
    except (ValueError, TypeError, IndexError, KeyError):
        return None
    body_hash = hashlib.sha256(body.encode()).hexdigest()
    fingerprint = hashlib.sha256((method + '\n' + parsed.hostname + '\n' + parsed.path + '\n' + body_hash).encode()).hexdigest()
    return {'request_hash': fingerprint, 'body_sha256': body_hash, 'contract': CONTRACT}
