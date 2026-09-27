import asyncio
from types import SimpleNamespace

import pytest

from film_pipeline.providers.flow_network import FlowNetworkTransport
from film_pipeline.providers.flow_response import FlowObservedIdentity
from film_pipeline.providers.flow_veo import FlowConfig


def identities():
    return [FlowObservedIdentity(f'{n:08x}-bbbb-cccc-dddd-eeeeeeeeeeee',
            '11111111-2222-3333-4444-555555555555', '99999999-8888-7777-6666-555555555555')
            for n in range(3)]


@pytest.mark.parametrize('delta,rendered,causal,state', [
    (0, 0, True, 'RUNNING'), (1, 1, True, 'SUCCEEDED'),
    (1, 0, True, 'RUNNING'), (1, 2, True, 'INCONCLUSIVE'),
    (2, 1, True, 'INCONCLUSIVE'), (1, 1, False, 'INCONCLUSIVE'),
])
def test_network_delta_requires_causal_activation_and_unique_tile(delta, rendered, causal, state):
    old, new, another = identities()
    transport = FlowNetworkTransport(FlowConfig())
    transport.decoder = SimpleNamespace(identities=lambda: {old, *[new, another][:delta]})
    async def drain(): pass
    async def tiles(): return [new] * rendered
    transport._drain = drain
    transport._rendered = tiles
    job = SimpleNamespace(provider_job_id='unit-job', pre_dispatch_snapshot={'asset_ids': [old.identity]},
        correlation_evidence={'official_generate_click_completed': True,
         'trusted_generate_click': causal, 'prompt_acceptance_transition': True})
    result = asyncio.run(transport.poll(job))
    assert result['status'] == state
    assert result['output_ids'] == ([new.identity] if state == 'SUCCEEDED' else [])


def test_incomplete_observer_cannot_supply_baseline():
    transport = FlowNetworkTransport(FlowConfig())
    transport._tasks = set()
    transport._observer_failed = True
    with pytest.raises(ValueError, match='EVIDENCE_INCOMPLETE'):
        asyncio.run(transport._drain())


def test_network_submit_rejects_repeat_before_any_browser_action():
    transport = FlowNetworkTransport(FlowConfig())
    transport._submit_invoked = True
    with pytest.raises(ValueError, match='RESERVATION_REQUIRED'):
        asyncio.run(transport.submit(SimpleNamespace(dispatch_count=1, submission_state='SUBMISSION_RESERVED'), 'prompt'))


def test_textarea_acceptance_requires_value_reset_not_empty_innertext():
    transport = FlowNetworkTransport(FlowConfig())
    waits = []
    async def wait(ms): waits.append(ms)
    transport.page = SimpleNamespace(wait_for_timeout=wait)
    class Editor:
        async def evaluate(self, expression): return 'TEXTAREA'
        async def inner_text(self): return ''  # DOM text does not reflect filled value.
        async def input_value(self): return 'filled prompt' if len(waits) < 2 else ''
    assert asyncio.run(transport._wait_prompt_reset(Editor()))
    assert len(waits) == 2


@pytest.mark.parametrize('sets,count,rendered,diagnostic', [
    ([set(), set()], 0, [], 'NETWORK_BASELINE_NOT_STABLE'),
    ([set(), {identities()[0]}], 1, [], 'NETWORK_BASELINE_NOT_STABLE'),
    ([{identities()[0]}, {identities()[0]}], 1, [], 'DEDICATED_CANARY_PROJECT_NOT_EMPTY'),
    ([set(), set()], 1, [None], 'RENDERED_VIDEO_IDENTITY_UNRESOLVED'),
])
def test_baseline_gate_refusals(monkeypatch, sets, count, rendered, diagnostic):
    from film_pipeline.providers import flow_network
    async def ready(*args): return 'PROJECT_READBACK_READY'
    monkeypatch.setattr(flow_network, 'project_surface_readback', ready)
    transport = FlowNetworkTransport(FlowConfig())
    transport.project_id = 'unit'
    async def wait(ms): pass
    class Locator:
        async def count(self): return 0
    transport.page = SimpleNamespace(wait_for_timeout=wait, locator=lambda selector: Locator())
    sequence = iter(sets)
    transport.decoder = SimpleNamespace(identities=lambda: next(sequence), observed_response_count=count)
    async def drain(): pass
    async def tiles(): return rendered
    transport._drain = drain
    transport._rendered = tiles
    with pytest.raises(ValueError, match=diagnostic):
        asyncio.run(transport.snapshot())
