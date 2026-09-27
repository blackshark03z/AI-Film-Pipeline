import asyncio
import json

import pytest
from jsonschema import ValidationError

from film_pipeline.core import ShotSpec, validate_contract
from film_pipeline.providers.flow_veo import FlowConfig, FlowVeoProvider
from film_pipeline.providers.base import routing_availability


def configured(tmp_path, readback):
    cookie = tmp_path / 'test.cookie'
    session = tmp_path / 'test.session.json'
    cookie.write_text(json.dumps([{'name': 'SID', 'value': 'fake-unit-marker', 'domain': '.google.com', 'expires': -1}]))
    session.write_text(json.dumps({'schema': 'google-flow-session-v1', 'project_id': 'unit-project'}))
    return FlowVeoProvider(FlowConfig(cookie, session, 'unit-project'), readback)


@pytest.mark.parametrize('purpose', [None, '', 'missing'])
def test_schema_and_model_motion_alignment(purpose):
    from pathlib import Path
    raw = json.loads((Path(__file__).parents[1] / 'fixtures/dialogue_closeup.json').read_text())
    if purpose == 'missing':
        raw['camera']['movement'].pop('purpose')
    else:
        raw['camera']['movement']['purpose'] = purpose
    with pytest.raises(ValidationError):
        validate_contract('shot_spec', raw)
    with pytest.raises(ValueError):
        ShotSpec.model_validate(raw)
    raw['camera']['movement']['type'] = 'locked'
    validate_contract('shot_spec', raw)
    ShotSpec.model_validate(raw)


@pytest.mark.parametrize('state', ['READY', 'AUTH_REQUIRED', 'MISCONFIGURED', 'INCONCLUSIVE', 'UNAVAILABLE', 'unknown'])
def test_normalized_preflight(tmp_path, state):
    async def readback(cookies, project):
        assert project == 'unit-project'
        assert cookies[0]['sameSite'] if 'sameSite' in cookies[0] else True
        return state
    provider = configured(tmp_path, readback)
    result = asyncio.run(provider.preflight())
    assert result.state == (state if state != 'unknown' else 'INCONCLUSIVE')
    assert result.routable == (state == 'READY')
    assert routing_availability([result]) == {'flow_veo': state == 'READY'}
    assert 'fake-unit-marker' not in result.model_dump_json()
    assert 'unit-project' not in result.model_dump_json()


def test_missing_auth_and_bad_binding(tmp_path):
    async def forbidden(*args):
        raise AssertionError('must not reach network')
    missing = FlowVeoProvider(FlowConfig(), forbidden)
    assert asyncio.run(missing.preflight()).state == 'AUTH_REQUIRED'
    provider = configured(tmp_path, forbidden)
    provider._config.session_path.write_text('{}')
    assert asyncio.run(provider.preflight()).state == 'MISCONFIGURED'


def test_expiry_and_transport_error_are_fail_closed(tmp_path):
    async def broken(*args):
        raise RuntimeError('private-transport-marker')
    provider = configured(tmp_path, broken)
    result = asyncio.run(provider.preflight())
    assert result.state == 'INCONCLUSIVE'
    assert 'private-transport-marker' not in result.model_dump_json()
    provider._config.cookie_path.write_text(json.dumps([{'name': 'SID', 'value': 'fake', 'domain': '.google.com', 'expires': 1}]))
    assert asyncio.run(provider.preflight()).state == 'AUTH_REQUIRED'


def test_capabilities_and_generation_disabled(tmp_path):
    provider = FlowVeoProvider(FlowConfig())
    caps = provider.capabilities()
    validate_contract('provider_capabilities', caps.payload())
    assert caps.supports_text_to_video
    assert all(not value for key, value in caps.model_dump().items() if key.startswith('supports_') and key != 'supports_text_to_video')
    for name in ('submit', 'poll', 'fetch_outputs', 'cancel'):
        with pytest.raises(NotImplementedError, match='NOT_IMPLEMENTED_IN_SLICE_0003'):
            asyncio.run(getattr(provider, name)(None))


def test_unrelated_cookie_domain_cannot_reach_transport(tmp_path):
    async def forbidden(*args):
        raise AssertionError('unexpected transport call')
    provider = configured(tmp_path, forbidden)
    provider._config.cookie_path.write_text(json.dumps([{'name': 'SID', 'value': 'fake', 'domain': 'evil.example'}]))
    assert asyncio.run(provider.preflight()).state == 'AUTH_REQUIRED'


def test_environment_config_does_not_export_paths(monkeypatch):
    monkeypatch.delenv('FLOW_COOKIE_PATH', raising=False)
    monkeypatch.delenv('FLOW_SESSION_PATH', raising=False)
    monkeypatch.delenv('FLOW_PROJECT_ID', raising=False)
    assert FlowConfig.from_environment() == FlowConfig()
    assert 'cookie' not in repr(FlowConfig())
