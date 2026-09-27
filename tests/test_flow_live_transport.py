import asyncio
from types import SimpleNamespace

import pytest

from film_pipeline.providers.flow_live import FlowLiveTransport
from film_pipeline.providers.flow_veo import FlowConfig


def test_exact_prompt_correlation_never_uses_gallery_order():
    transport = FlowLiveTransport(FlowConfig())
    async def snapshot():
        return {'asset_ids': ['old', 'new'], 'cards': [
            {'asset_id': 'new', 'prompt': 'exact job_unique'}, {'asset_id': 'old', 'prompt': 'other'}]}
    transport.snapshot = snapshot
    transport._urls = {'new': 'memory-only'}
    job = SimpleNamespace(pre_dispatch_snapshot={'asset_ids': ['old']}, correlation_evidence={'prompt': 'exact job_unique', 'correlation_marker': 'job_unique'})
    assert asyncio.run(transport.poll(job)) == {'status': 'SUCCEEDED', 'output_ids': ['new']}


def test_unrelated_new_output_preserves_uncertainty():
    transport = FlowLiveTransport(FlowConfig())
    async def snapshot():
        return {'asset_ids': ['new'], 'cards': [{'asset_id': 'new', 'prompt': 'unrelated'}]}
    transport.snapshot = snapshot
    job = SimpleNamespace(pre_dispatch_snapshot={'asset_ids': []}, correlation_evidence={'prompt': 'exact'})
    assert asyncio.run(transport.poll(job))['status'] == 'INCONCLUSIVE'


def test_fetch_refuses_uncorrelated_asset(tmp_path):
    transport = FlowLiveTransport(FlowConfig())
    async def poll(job):
        return {'status': 'SUCCEEDED', 'output_ids': ['owned']}
    transport.poll = poll
    with pytest.raises(ValueError, match='NOT_CORRELATED'):
        asyncio.run(transport.fetch(None, 'wrong', tmp_path / 'wrong.mp4'))
    assert not (tmp_path / 'wrong.mp4').exists()


def test_snapshot_refuses_unverified_identity_surface():
    class EmptyLocator:
        async def count(self):
            return 0
        async def evaluate_all(self, expression):
            return []
    transport = FlowLiveTransport(FlowConfig())
    transport.page = SimpleNamespace(locator=lambda selector: EmptyLocator())
    with pytest.raises(ValueError, match='CORRELATION_SURFACE_UNVERIFIED'):
        asyncio.run(transport.snapshot())


def test_ambiguous_submit_selector_never_clicks():
    class Ambiguous:
        async def count(self):
            return 2
        async def click(self, **kwargs):
            raise AssertionError('no click authorized')
    transport = FlowLiveTransport(FlowConfig())
    transport.page = SimpleNamespace(locator=lambda selector: Ambiguous())
    with pytest.raises(ValueError, match='UNAMBIGUOUS_SUBMIT'):
        asyncio.run(transport.submit(SimpleNamespace(dispatch_count=1, submission_state='SUBMISSION_RESERVED'), 'prompt'))


def test_submitted_job_cannot_click_again():
    transport = FlowLiveTransport(FlowConfig())
    with pytest.raises(ValueError, match='RESERVATION_REQUIRED'):
        asyncio.run(transport.submit(SimpleNamespace(dispatch_count=1, submission_state='SUBMITTED'), 'prompt'))


def test_same_creative_prompt_from_unrelated_job_is_not_owned():
    transport = FlowLiveTransport(FlowConfig())
    async def snapshot():
        return {'asset_ids': ['unrelated'], 'cards': [{'asset_id': 'unrelated', 'prompt': 'same creative prompt'}]}
    transport.snapshot = snapshot
    job = SimpleNamespace(pre_dispatch_snapshot={'asset_ids': []}, correlation_evidence={
        'prompt': 'same creative prompt\nExecution correlation: unique_job', 'correlation_marker': 'unique_job'})
    assert asyncio.run(transport.poll(job))['status'] == 'INCONCLUSIVE'
