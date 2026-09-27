"""Read-only Flow preflight. No generation mechanics are imported or exposed."""
from __future__ import annotations

import json
import os
import re
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Awaitable, Callable
from urllib.parse import urlparse

from ..core import ProviderCapabilities
from .base import ProviderHealth


@dataclass(frozen=True, repr=False)
class FlowConfig:
    cookie_path: Path | None = None
    session_path: Path | None = None
    project_id: str | None = None

    @classmethod
    def from_environment(cls) -> "FlowConfig":
        return cls(
            Path(os.environ['FLOW_COOKIE_PATH']) if os.environ.get('FLOW_COOKIE_PATH') else None,
            Path(os.environ['FLOW_SESSION_PATH']) if os.environ.get('FLOW_SESSION_PATH') else None,
            os.environ.get('FLOW_PROJECT_ID'),
        )


async def browser_readback(cookies: list[dict], project_id: str) -> str:
    """Navigate only to the bound project. Do not click, submit or refresh auth."""
    from patchright.async_api import async_playwright
    async with async_playwright() as driver:
        browser = await driver.chromium.launch(headless=True)
        try:
            context = await browser.new_context()
            await context.add_cookies(cookies)
            page = await context.new_page()
            response = await page.goto(f'https://flow.google.com/project/{project_id}', timeout=30000)
            if response is None or response.status >= 400:
                return 'UNAVAILABLE'
            parsed = urlparse(page.url)
            if parsed.hostname == 'accounts.google.com' or parsed.path.startswith('/about'):
                return 'AUTH_REQUIRED'
            if parsed.hostname != 'flow.google.com' or parsed.path.rstrip('/') != f'/project/{project_id}':
                return 'INCONCLUSIVE'
            # A matching URL alone does not establish a usable project surface.
            prompt = page.locator('textarea')
            if await prompt.count() != 1 or not await prompt.is_visible() or not await prompt.is_enabled():
                return 'INCONCLUSIVE'
            return 'READY'
        finally:
            await browser.close()


class FlowVeoProvider:
    def __init__(self, config: FlowConfig, readback: Callable[[list[dict], str], Awaitable[str]] = browser_readback):
        self._config = config
        self._readback = readback

    def capabilities(self) -> ProviderCapabilities:
        return ProviderCapabilities(
            profile_version='flow-preflight-826e018-v1', provider_id='flow_veo', transport_type='browser_cookie',
            supports_text_to_video=True,
            notes=[
                'Text-to-video transport observed in AutoVideoPipeline@826e01866af1b28ed29b6fbb51cabb71f31ef561.',
                'All other capability flags are false: usable support is unverified in this adapter.',
                'Generation methods are disabled in SLICE-0003; capabilities do not authorize dispatch.',
            ],
        )

    def _health(self, state: str, code: str) -> ProviderHealth:
        return ProviderHealth(provider_id='flow_veo', state=state, diagnostic_code=code, evidence=[code])

    async def preflight(self) -> ProviderHealth:
        config = self._config
        if config.cookie_path is None or not config.cookie_path.is_file():
            return self._health('AUTH_REQUIRED', 'SESSION_MISSING')
        if config.session_path is None or not config.session_path.is_file():
            return self._health('MISCONFIGURED', 'PROJECT_BINDING_MISSING')
        try:
            session = json.loads(config.session_path.read_text(encoding='utf-8'))
            cookies = json.loads(config.cookie_path.read_text(encoding='utf-8'))
            if not isinstance(session, dict) or session.get('schema') != 'google-flow-session-v1':
                return self._health('MISCONFIGURED', 'SESSION_FORMAT_INVALID')
            project_id = session.get('project_id')
            if not isinstance(project_id, str) or not re.fullmatch(r'[A-Za-z0-9_-]+', project_id):
                return self._health('MISCONFIGURED', 'PROJECT_BINDING_INVALID')
            if config.project_id and config.project_id != project_id:
                return self._health('MISCONFIGURED', 'PROJECT_BINDING_MISMATCH')
            if session.get('project_url', f'https://flow.google.com/project/{project_id}') != f'https://flow.google.com/project/{project_id}':
                return self._health('MISCONFIGURED', 'PROJECT_URL_MISMATCH')
            if not isinstance(cookies, list) or not cookies:
                return self._health('AUTH_REQUIRED', 'COOKIE_SET_EMPTY')
            essential = {'SID', 'HSID', '__Secure-1PSID', '__Secure-1PSIDTS'}
            valid_sid = False
            clean = []
            for cookie in cookies:
                if not isinstance(cookie, dict) or not all(isinstance(cookie.get(k), str) for k in ('name', 'value', 'domain')):
                    return self._health('MISCONFIGURED', 'COOKIE_FORMAT_INVALID')
                if cookie['domain'].lstrip('.') not in {'google.com', 'flow.google.com', 'accounts.google.com'}:
                    continue
                expiry = cookie.get('expires', 0)
                if not isinstance(expiry, (int, float)):
                    return self._health('MISCONFIGURED', 'COOKIE_EXPIRY_INVALID')
                if cookie['name'] in essential and expiry > 0 and expiry < time.time():
                    return self._health('AUTH_REQUIRED', 'COOKIE_EXPIRED')
                if cookie['name'] == 'SID' and cookie['value']:
                    valid_sid = True
                item = {k: cookie[k] for k in ('name', 'value', 'domain')}
                item['path'] = cookie.get('path', '/')
                for key in ('expires', 'httpOnly', 'secure'):
                    if key in cookie:
                        item[key] = cookie[key]
                if cookie.get('sameSite') in {'Strict', 'Lax', 'None'}:
                    item['sameSite'] = cookie['sameSite']
                clean.append(item)
            if not valid_sid:
                return self._health('AUTH_REQUIRED', 'ESSENTIAL_COOKIE_MISSING')
        except (OSError, ValueError, TypeError):
            return self._health('MISCONFIGURED', 'LOCAL_STATE_INVALID')
        try:
            state = await self._readback(clean, project_id)
            if state not in {'READY', 'UNAVAILABLE', 'AUTH_REQUIRED', 'MISCONFIGURED', 'INCONCLUSIVE'}:
                state = 'INCONCLUSIVE'
            return self._health(state, 'PROJECT_READBACK_' + state)
        except ImportError:
            return self._health('UNAVAILABLE', 'BROWSER_RUNTIME_UNAVAILABLE')
        except Exception:
            # Never expose exception text: transport errors may embed URLs or tokens.
            return self._health('INCONCLUSIVE', 'READBACK_ERROR')

    async def submit(self, request):
        raise NotImplementedError('NOT_IMPLEMENTED_IN_SLICE_0003')

    async def poll(self, provider_job_id):
        raise NotImplementedError('NOT_IMPLEMENTED_IN_SLICE_0003')

    async def fetch_outputs(self, provider_job_id):
        raise NotImplementedError('NOT_IMPLEMENTED_IN_SLICE_0003')

    async def cancel(self, provider_job_id):
        raise NotImplementedError('NOT_IMPLEMENTED_IN_SLICE_0003')
