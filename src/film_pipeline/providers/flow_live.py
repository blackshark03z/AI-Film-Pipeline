"""Bounded canary transport. Correlation is required; gallery order is unused."""
import json
from pathlib import Path
from urllib.parse import urlparse

from .flow_veo import FlowConfig


class FlowLiveTransport:
    def __init__(self, config: FlowConfig):
        self.config = config
        self.page = None
        self._urls = {}
        self._submit_invoked = False

    async def open(self):
        from patchright.async_api import async_playwright
        self.driver = await async_playwright().start()
        self.browser = await self.driver.chromium.launch(headless=True)
        self.context = await self.browser.new_context()
        raw = json.loads(self.config.cookie_path.read_text(encoding='utf-8'))
        cookies = []
        for cookie in raw:
            item = {k: cookie[k] for k in ('name', 'value', 'domain')}
            item['path'] = cookie.get('path', '/')
            for key in ('expires', 'secure', 'httpOnly'):
                if key in cookie:
                    item[key] = cookie[key]
            if cookie.get('sameSite') in ('Strict', 'Lax', 'None'):
                item['sameSite'] = cookie['sameSite']
            cookies.append(item)
        await self.context.add_cookies(cookies)
        session = json.loads(self.config.session_path.read_text(encoding='utf-8'))
        self.project_id = session['project_id']
        self.page = await self.context.new_page()
        await self.page.goto(f'https://flow.google.com/project/{self.project_id}', timeout=30000)
        if urlparse(self.page.url).path.rstrip('/') != f'/project/{self.project_id}':
            raise ValueError('BOUND_PROJECT_NOT_READY')

    async def close(self):
        if hasattr(self, 'browser'):
            await self.browser.close()
        if hasattr(self, 'driver'):
            await self.driver.stop()

    async def snapshot(self):
        if await self.page.locator('[role="progressbar"], mat-progress-bar, mat-spinner, .generating').count():
            raise ValueError('CONCURRENT_GENERATION')
        # Only explicit stable asset identities are usable. Unknown DOM fails closed.
        cards = await self.page.locator('[data-asset-id]').evaluate_all('''els => els.map(e => ({
            asset_id:e.getAttribute('data-asset-id'),
            prompt:e.getAttribute('data-prompt'),
            url:e.querySelector('video')?.currentSrc || null
        }))''')
        media_count = await self.page.locator('video').count()
        if not cards:
            raise ValueError('STABLE_CORRELATION_SURFACE_UNVERIFIED')
        if media_count and len(cards) < media_count:
            raise ValueError('STABLE_ASSET_IDENTITIES_UNAVAILABLE')
        if len({c['asset_id'] for c in cards}) != len(cards):
            raise ValueError('AMBIGUOUS_ASSET_IDENTITY')
        for card in cards:
            if card['url']:
                self._urls[card['asset_id']] = card['url']
        return {'asset_ids': sorted(c['asset_id'] for c in cards), 'cards': [
            {'asset_id': c['asset_id'], 'prompt': c['prompt']} for c in cards
        ]}

    async def submit(self, job, prompt):
        # Called only after the durable executor has reserved the sole dispatch.
        if self._submit_invoked or job is None or job.dispatch_count != 1 or job.submission_state != 'SUBMISSION_RESERVED':
            raise ValueError('DURABLE_FIRST_DISPATCH_RESERVATION_REQUIRED')
        self._submit_invoked = True
        editor = self.page.locator('textarea, div.ProseMirror, [contenteditable="true"]')
        button = self.page.locator('button.generate-icon-button, button:has-text("arrow_forward")')
        if await editor.count() != 1 or await button.count() != 1:
            raise ValueError('UNAMBIGUOUS_SUBMIT_SURFACE_REQUIRED')
        if not await editor.is_visible() or not await button.is_enabled():
            raise ValueError('SUBMIT_SURFACE_NOT_READY')
        await editor.fill(prompt)
        await button.click(timeout=10000)
        return {'external_job_id': None}

    async def poll(self, job):
        current = await self.snapshot()
        prior = set(job.pre_dispatch_snapshot['asset_ids'])
        new = [c for c in current['cards'] if c['asset_id'] not in prior]
        exact = [c['asset_id'] for c in new if c['prompt'] == job.correlation_evidence['prompt']]
        marker = job.correlation_evidence.get('correlation_marker')
        if not marker or marker not in job.correlation_evidence['prompt']:
            return {'status': 'INCONCLUSIVE', 'output_ids': []}
        if new and len(exact) != len(new):
            return {'status': 'INCONCLUSIVE', 'output_ids': []}
        if exact and all(identity in self._urls for identity in exact):
            return {'status': 'SUCCEEDED', 'output_ids': sorted(exact)}
        return {'status': 'RUNNING', 'output_ids': []}

    async def fetch(self, job, output_id, destination):
        # URLs are ephemeral memory-only transport data; never stored in evidence.
        result = await self.poll(job)
        if result['status'] != 'SUCCEEDED' or output_id not in result['output_ids']:
            raise ValueError('OUTPUT_NOT_CORRELATED')
        response = await self.context.request.get(self._urls[output_id], timeout=60000)
        if not response.ok:
            raise ValueError('DOWNLOAD_UNAVAILABLE')
        destination = Path(destination)
        destination.parent.mkdir(parents=True, exist_ok=True)
        if destination.exists():
            raise ValueError('IMMUTABLE_OUTPUT_ALREADY_EXISTS')
        destination.write_bytes(await response.body())
        return destination
