import asyncio

from film_pipeline import canary
from film_pipeline.providers.base import ProviderHealth
from film_pipeline.providers.flow_veo import FlowConfig


def test_nonready_preflight_never_constructs_live_transport(monkeypatch):
    class Provider:
        def __init__(self, config):
            pass
        async def preflight(self):
            return ProviderHealth(provider_id='flow_veo', state='AUTH_REQUIRED', diagnostic_code='UNIT_AUTH')
    def forbidden(config):
        raise AssertionError('no transport for failed preflight')
    monkeypatch.setattr(canary, 'FlowVeoProvider', Provider)
    monkeypatch.setattr(canary, 'FlowLiveTransport', forbidden)
    result = asyncio.run(canary.run_canary(FlowConfig()))
    assert result['dispatch_count'] == 0
    assert result['result'] == 'INCONCLUSIVE'
