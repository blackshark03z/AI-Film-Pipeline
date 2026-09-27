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


def project_url_state(url: str, project_id: str) -> str:
    parsed = urlparse(url)
    if parsed.hostname == 'accounts.google.com' or (parsed.hostname == 'flow.google.com' and parsed.path.startswith('/about')):
        return 'AUTH_REQUIRED'
    if parsed.scheme != 'https' or parsed.hostname != 'flow.google.com' or parsed.username or parsed.password:
        return 'PROJECT_URL_MISMATCH'
    match = re.fullmatch(r'/(?:u/[0-9]+/)?project/([A-Za-z0-9_-]+)/?', parsed.path)
    return 'MATCH' if match and match.group(1) == project_id else 'PROJECT_URL_MISMATCH'


# Verified live Flow editor; CAPTCHA/search/title controls are excluded.
PROMPT_SELECTOR = 'div.ProseMirror[contenteditable="true"], textarea[placeholder*="prompt" i], textarea[placeholder*="describe" i]'


async def project_surface_readback(page, project_id: str, *, checks: int = 40, interval_ms: int = 250) -> str:
    saw_candidate = False
    for index in range(checks):
        identity = project_url_state(page.url, project_id)
        if identity != 'MATCH':
            return identity
        controls = page.locator(PROMPT_SELECTOR)
        usable = 0
        for i in range(await controls.count()):
            control = controls.nth(i)
            saw_candidate = True
            if await control.is_visible() and await control.is_enabled() and await control.is_editable():
                usable += 1
        if usable == 1:
            # Identity and usability are independently required at readback.
            return 'PROJECT_READBACK_READY' if project_url_state(page.url, project_id) == 'MATCH' else 'PROJECT_URL_MISMATCH'
        if index + 1 < checks:
            await page.wait_for_timeout(interval_ms)
    return 'PROJECT_SURFACE_TIMEOUT' if saw_candidate else 'PROJECT_PROMPT_SURFACE_MISSING'


async def browser_readback(cookies: list[dict], project_id: str) -> str:
    """Read-only navigation and bounded project/editor verification."""
    from patchright.async_api import async_playwright
    async with async_playwright() as driver:
        browser = await driver.chromium.launch(headless=True)
        try:
            context = await browser.new_context()
            await context.add_cookies(cookies)
            page = await context.new_page()
            response = await page.goto(f'https://flow.google.com/project/{project_id}', timeout=30000)
            if project_url_state(page.url, project_id) == 'AUTH_REQUIRED':
                return 'AUTH_REQUIRED'
            if response is None or response.status >= 400:
                return 'UNAVAILABLE'
            return await project_surface_readback(page, project_id)
        finally:
            await browser.close()


class FlowVeoProvider:
    def __init__(self, config: FlowConfig, readback: Callable[[list[dict], str], Awaitable[str]] = browser_readback, *, live_executor=None):
        self._config = config
        self._readback = readback
        self._live_executor = live_executor

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
            if state == 'PROJECT_READBACK_READY':
                return self._health('READY', state)
            if state in {'PROJECT_URL_MISMATCH', 'PROJECT_SURFACE_TIMEOUT', 'PROJECT_PROMPT_SURFACE_MISSING'}:
                return self._health('INCONCLUSIVE', state)
            if state not in {'READY', 'UNAVAILABLE', 'AUTH_REQUIRED', 'MISCONFIGURED', 'INCONCLUSIVE'}:
                state = 'INCONCLUSIVE'
            return self._health(state, 'PROJECT_READBACK_' + state)
        except ImportError:
            return self._health('UNAVAILABLE', 'BROWSER_RUNTIME_UNAVAILABLE')
        except Exception:
            # Never expose exception text: transport errors may embed URLs or tokens.
            return self._health('INCONCLUSIVE', 'READBACK_ERROR')

    async def submit(self, request):
        if self._live_executor is not None:
            return await self._live_executor.submit_once(request)
        raise NotImplementedError('NOT_IMPLEMENTED_IN_SLICE_0003')

    async def poll(self, provider_job_id):
        if self._live_executor is not None:
            return await self._live_executor.reconcile(provider_job_id)
        raise NotImplementedError('NOT_IMPLEMENTED_IN_SLICE_0003')

    async def fetch_outputs(self, provider_job_id):
        if self._live_executor is not None:
            return await self._live_executor.download_assets(provider_job_id, Path('projects/flow_canary/outputs'))
        raise NotImplementedError('NOT_IMPLEMENTED_IN_SLICE_0003')

    async def cancel(self, provider_job_id):
        raise NotImplementedError('NOT_IMPLEMENTED_IN_SLICE_0003')
