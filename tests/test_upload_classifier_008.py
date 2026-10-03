"""Package-008 U2/U4: upload response classifier — offline proof, fail-closed."""
import hashlib
import io
import json
from pathlib import Path
from unittest.mock import Mock

import pytest
from PIL import Image, ImageDraw

from film_pipeline.providers import flow_rpc_contract as contract
from film_pipeline.providers.flow_reference_rpc import FlowReferenceRpcSession
from film_pipeline.providers.flow_reference_upload import OwnerAmbiguityGate
from film_pipeline.providers.flow_upload_classifier import (
    HISTORICAL_PENDING_RESPONSE_CLASS,
    QUALIFIED_COMPLETED,
    QUALIFIED_PENDING,
    TRUE_AMBIGUOUS,
    UNOBSERVABLE,
    classify_parse_failure,
    classify_unobservable,
    classify_upload_response,
    skeleton_fingerprint,
    QualifiedUploadPending,
    UploadResponseAmbiguous,
    UploadResponseClassified,
)

PROJECT = '11111111-2222-3333-4444-555555555555'
REQUEST = 'aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee'
MEDIA = 'dddddddd-eeee-ffff-0000-111111111111'


def test_direct_identity_envelope_is_qualified_completed():
    result = classify_upload_response(200, [[MEDIA, None]], project_id=PROJECT,
                                      request_id=REQUEST)
    assert result.classification == QUALIFIED_COMPLETED
    assert not isinstance(result, UploadResponseAmbiguous)


LIVE_PENDING_SKELETON = {'list': [
    {'list': ['uuid', 'uuid', 'uuid', 'str', 'null',
              {'list': [{'list': ['int', 'int']}, 'null', 'null', 'null',
                        'null', 'null',
                        {'list': ['null', 'null', 'null', 'null', 'int']},
                        'null', 'null', 'int', 'null', 'null', 'null', 'int']},
              {'list': ['null', {'list': ['null', 'null', 'null', 'null',
                                          'int', 'null', 'str']},
                         {'list': ['int', 'int']}]}]},
    {'list': ['uuid', 'null', 'null',
              {'list': ['str', {'list': ['int', 'int']}, 'null', 'null',
                        'uuid']},
              'uuid']}]}
FROZEN_FINGERPRINT = 'ae90da3e8da5f4330d774bce43dc8c6e995f948d3f904149cf5857152373b9a1'


_UUID_COUNTER = {'n': 0}


def build_payload(skeleton):
    import uuid as uuid_module
    if skeleton == 'uuid':
        _UUID_COUNTER['n'] += 1
        return str(uuid_module.UUID(int=_UUID_COUNTER['n']))
    if skeleton == 'str':
        return 'story-auto-reference.png'
    if skeleton == 'int':
        return 1
    if skeleton == 'float':
        return 0.5
    if skeleton == 'bool':
        return True
    if skeleton == 'null':
        return None
    if isinstance(skeleton, dict) and 'list' in skeleton:
        return [build_payload(item) for item in skeleton['list']]
    if isinstance(skeleton, dict) and 'dict' in skeleton:
        return {key: build_payload(value)
                for key, value in skeleton['dict'].items()}
    raise ValueError('bad skeleton')


def test_live_frozen_class_is_qualified_pending():
    from film_pipeline.providers.flow_upload_classifier import (
        LIVE_PENDING_SKELETON_FINGERPRINT)
    assert LIVE_PENDING_SKELETON_FINGERPRINT == FROZEN_FINGERPRINT
    payload = build_payload(LIVE_PENDING_SKELETON)
    result = classify_upload_response(200, payload, project_id=PROJECT,
                                      request_id=REQUEST)
    assert result.classification == QUALIFIED_PENDING
    assert result.reason == 'maseQ-200-live-skeleton'
    assert result.fingerprint == FROZEN_FINGERPRINT
    assert isinstance(result, QualifiedUploadPending)
    assert not isinstance(result, OwnerAmbiguityGate)


def test_live_class_value_variation_keeps_same_fingerprint():
    import uuid as uuid_module
    payload = build_payload(LIVE_PENDING_SKELETON)
    payload[0][3] = 'a-completely-different-filename.png'
    payload[0][0] = str(uuid_module.UUID(int=99))
    result = classify_upload_response(200, payload, project_id=PROJECT,
                                      request_id=REQUEST)
    assert result.classification == QUALIFIED_PENDING
    assert result.fingerprint == FROZEN_FINGERPRINT


def test_live_class_structural_drift_fails_closed():
    payload = build_payload(LIVE_PENDING_SKELETON)
    payload[0].append('extra-field')
    result = classify_upload_response(200, payload, project_id=PROJECT,
                                      request_id=REQUEST)
    assert result.classification == TRUE_AMBIGUOUS
    assert isinstance(result, OwnerAmbiguityGate)


def test_live_class_requires_status_200():
    payload = build_payload(LIVE_PENDING_SKELETON)
    result = classify_upload_response(500, payload, project_id=PROJECT,
                                      request_id=REQUEST)
    assert result.classification == TRUE_AMBIGUOUS


def test_identity_free_structured_record_is_no_longer_pending():
    """U4 correction: the guessed 'no UUID anywhere' envelope mis-predicted
    the live class (Canary 1 fail-closed); it is no longer a pending class."""
    payload = [[None, None, 'x' * 500], [None]]
    result = classify_upload_response(200, payload, project_id=PROJECT,
                                      request_id=REQUEST)
    assert result.classification == TRUE_AMBIGUOUS
    assert isinstance(result, OwnerAmbiguityGate)


@pytest.mark.parametrize('status,payload', [
    (200, None),
    (200, {}),
    (200, 'text'),
    (200, []),
    (200, ['bare-string', 'second']),
    (200, [MEDIA]),
    (200, [PROJECT]),
    (200, [['x'], [MEDIA]]),
    (200, [[None, ['nested', MEDIA]]]),
    (500, [[None, None]]),
    (429, [[None, None]]),
    (None, [[None, None]]),
])
def test_every_non_pending_shape_fails_closed_ambiguous(status, payload):
    result = classify_upload_response(status, payload, project_id=PROJECT,
                                      request_id=REQUEST)
    assert result.classification == TRUE_AMBIGUOUS
    assert isinstance(result, UploadResponseAmbiguous)
    assert isinstance(result, OwnerAmbiguityGate)


def test_parse_failure_is_true_ambiguous_and_never_pending():
    result = classify_parse_failure()
    assert result.classification == TRUE_AMBIGUOUS
    assert isinstance(result, OwnerAmbiguityGate)
    assert 'pending' not in result.classification.lower()


def test_unobservable_is_distinct_but_still_gate():
    result = classify_unobservable()
    assert result.classification == UNOBSERVABLE
    assert isinstance(result, OwnerAmbiguityGate)


def test_correlation_metadata_siblings_do_not_conflict():
    client = contract._new_uuid(REQUEST, 'upload-client')
    session_id = contract._new_uuid(REQUEST, 'upload-session')
    result = classify_upload_response(200, [[MEDIA, client], [session_id]],
                                      project_id=PROJECT, request_id=REQUEST)
    assert result.classification == QUALIFIED_COMPLETED


def test_skeleton_is_value_free_and_deterministic():
    first = classify_upload_response(200, [[None, 'https://secret.example/x',
                                            'p@ssw0rd', 12345, 4.5, True]],
                                     project_id=PROJECT, request_id=REQUEST)
    second = classify_upload_response(200, [[None, 'https://other.example/y',
                                             'different', 99999, 0.5, False]],
                                      project_id=PROJECT, request_id=REQUEST)
    assert first.skeleton == second.skeleton
    assert first.fingerprint == second.fingerprint
    encoded = repr(first.skeleton)
    for leak in ('secret.example', 'p@ssw0rd', '12345', '4.5'):
        assert leak not in encoded


def test_uuid_strings_are_marked_but_not_valued_in_skeleton():
    result = classify_upload_response(200, [[None, MEDIA]],
                                      project_id=PROJECT, request_id=REQUEST)
    assert MEDIA not in repr(result.skeleton)
    assert 'uuid' in repr(result.skeleton)


def test_classification_requires_all_inputs_fresh_each_call():
    a = classify_upload_response(200, [[None, None]], project_id=PROJECT,
                                 request_id=REQUEST)
    b = classify_upload_response(200, [[None, None]], project_id=PROJECT,
                                 request_id=REQUEST)
    assert a.fingerprint == b.fingerprint
    c = classify_upload_response(200, [[None, None, None]], project_id=PROJECT,
                                 request_id=REQUEST)
    assert c.fingerprint != a.fingerprint


def test_real_session_transport_failure_after_dispatch_classifies_unobservable(tmp_path):
    session = FlowReferenceRpcSession(cookie_path=Path('unused'), project_id=PROJECT)
    session.captcha = Mock(return_value='test_captcha')
    session.metadata = Mock(return_value={'source': '/project/' + PROJECT,
        'bl': 'x', 'sid': 'x', 'hl': 'en', 'at': 'x'})
    session.page = Mock()
    session.page.context.request.post.side_effect = TimeoutError('wire dead')
    with pytest.raises(OwnerAmbiguityGate, match='UNOBSERVABLE'):
        session.upload_reference(b'png-bytes', REQUEST,
            before_post=lambda digest: None,
            on_http_response=lambda status, length: None,
            on_identified=lambda identity: pytest.fail('never identified'))


def _batchexecute(payload_json: str) -> str:
    import json
    line = json.dumps([["wrb.fr", "maseQ", payload_json, None, "generic"]])
    return ")]}'\n\n" + str(len(line)) + '\n' + line + '\n'


def test_real_session_pending_response_shape_reaches_transport(tmp_path):
    """End-to-end through the real _rpc_body path: HTTP 200 + the live
    frozen pending skeleton → QualifiedUploadPending."""
    session = FlowReferenceRpcSession(cookie_path=Path('unused'), project_id=PROJECT)
    session.captcha = Mock(return_value='test_captcha')
    session.metadata = Mock(return_value={'source': '/project/' + PROJECT,
        'bl': 'x', 'sid': 'x', 'hl': 'en', 'at': 'x'})
    response = Mock(status=200)
    response.text.return_value = _batchexecute(json.dumps(
        build_payload(LIVE_PENDING_SKELETON)))
    session.page = Mock()
    session.page.context.request.post.return_value = response
    observed = []
    with pytest.raises(QualifiedUploadPending) as pending:
        session.upload_reference(b'png-bytes', REQUEST,
            before_post=lambda digest: observed.append(digest),
            on_http_response=lambda status, length: observed.append((status, length)),
            on_identified=lambda identity: pytest.fail('never identified'))
    assert pending.value.classification == QUALIFIED_PENDING
    assert pending.value.fingerprint == FROZEN_FINGERPRINT
    assert observed[1] == (200, len(response.text.return_value.encode('utf-8')))


def test_real_session_http_200_unknown_body_fails_closed(tmp_path):
    session = FlowReferenceRpcSession(cookie_path=Path('unused'), project_id=PROJECT)
    session.captcha = Mock(return_value='test_captcha')
    session.metadata = Mock(return_value={'source': '/project/' + PROJECT,
        'bl': 'x', 'sid': 'x', 'hl': 'en', 'at': 'x'})
    response = Mock(status=200)
    response.text.return_value = _batchexecute('{"unexpected": "shape"}')
    session.page = Mock()
    session.page.context.request.post.return_value = response
    with pytest.raises(OwnerAmbiguityGate, match='TRUE_AMBIGUOUS'):
        session.upload_reference(b'png-bytes', REQUEST,
            before_post=lambda digest: None,
            on_http_response=lambda status, length: None,
            on_identified=lambda identity: pytest.fail('never identified'))
