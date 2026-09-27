"""Story Auto passive identity baseline and exact official VIDEO acquisition.

Raw UI response bodies and thumbnail URLs remain memory-only. No RPC replay.
"""
import asyncio
import hashlib
import json
import secrets
from pathlib import Path
from urllib.parse import urlsplit

from .flow_live import FlowLiveTransport
from .flow_response import FlowResponseModelDecoder
from .flow_veo import PROMPT_SELECTOR, project_surface_readback
from .flow_dispatch_network import generate_request_metadata
from ..core import sha256


class FlowNetworkTransport(FlowLiveTransport):
    async def _click_pinned_generate(self, element):
        # The guarded element must be the clicked element. Detachment fails closed.
        await element.click(timeout=10000)

    def set_evidence_sink(self, sink, job):
        self._sink, self._job = sink, job

    def _record(self, kind, data=None):
        if not hasattr(self, '_sink'):
            raise ValueError('DURABLE_EVIDENCE_SINK_REQUIRED')
        self._sink.record(kind, data)

    async def _prompt_value(self, editor):
        if await editor.evaluate('e=>e.tagName') == 'TEXTAREA':
            return await editor.input_value()
        return await editor.inner_text()

    async def _fill_prompt(self, editor, prompt):
        if await editor.evaluate('e=>e.tagName') == 'TEXTAREA':
            await editor.fill(prompt)
            return
        await editor.fill('')
        # Native soft breaks preserve internal blank lines in contenteditable.
        for index, line in enumerate(prompt.split('\n')):
            if index:
                await editor.press('Shift+Enter')
            if line:
                await self.page.keyboard.insert_text(line)

    async def _wait_prompt_reset(self, editor):
        for _ in range(40):
            if not (await self._prompt_value(editor)).strip():
                if hasattr(self, '_sink'):
                    self._record('PROMPT_ACCEPTANCE_TRANSITION')
                return True
            await self.page.wait_for_timeout(250)
        return False

    def _observe_page(self):
        self.decoder = FlowResponseModelDecoder(self.project_id)
        self._tasks = set()
        self._observer_failed = False
        self._armed = False
        self._requests = {}
        def request_observed(request):
            if not self._armed or not hasattr(self, '_job'):
                return
            try:
                metadata = generate_request_metadata(request.method, request.url, request.post_data,
                    self.project_id, self._job.correlation_evidence['prompt'])
                if metadata is None:
                    return
                if self._requests:
                    self._record('AMBIGUOUS_EVIDENCE', {'diagnostic': 'MULTIPLE_GENERATE_REQUESTS'})
                    self._observer_failed = True
                    return
                self._record('GENERATE_REQUEST_OBSERVED', metadata)
                self._requests[request] = metadata['request_hash']
            except Exception:
                self._observer_failed = True
        self.page.on('request', request_observed)
        def response_received(response):
            task = asyncio.create_task(self._observe(response))
            self._tasks.add(task)
            task.add_done_callback(self._tasks.discard)
        self.page.on('response', response_received)

    async def _observe(self, response):
        if response.request.resource_type not in {'xhr', 'fetch'} or urlsplit(response.url).hostname != 'flow.google.com':
            return
        try:
            request_hash = self._requests.get(response.request)
            if request_hash:
                self._record('PROVIDER_RESPONSE_OBSERVED', {'request_hash': request_hash,
                    'status': response.status})
                # No currently qualified acceptance parser. HTTP200 is not acceptance.
            body = await asyncio.wait_for(response.text(), timeout=10)
            self.decoder.observe_body(body)
        except Exception:
            # Incomplete evidence cannot silently qualify an output.
            self._observer_failed = True

    async def _drain(self):
        if self._tasks:
            await asyncio.wait_for(asyncio.gather(*list(self._tasks)), timeout=12)
        if self._observer_failed:
            raise ValueError('PASSIVE_RESPONSE_EVIDENCE_INCOMPLETE')

    async def snapshot(self):
        if await project_surface_readback(self.page, self.project_id) != 'PROJECT_READBACK_READY':
            raise ValueError('BOUND_PROJECT_NOT_READY')
        await self.page.wait_for_timeout(1000)
        await self._drain()
        baseline = sorted(i.identity for i in self.decoder.identities())
        await self.page.wait_for_timeout(1000)
        await self._drain()
        current = sorted(i.identity for i in self.decoder.identities())
        if baseline != current or not self.decoder.observed_response_count:
            raise ValueError('NETWORK_BASELINE_NOT_STABLE')
        # This single canary uses the newly created, otherwise empty project.
        if current:
            raise ValueError('DEDICATED_CANARY_PROJECT_NOT_EMPTY')
        if await self.page.locator('[role="progressbar"], mat-progress-bar, mat-spinner, .generating').count():
            raise ValueError('CONCURRENT_GENERATION')
        rendered = await self._rendered()
        if any(identity is None for identity in rendered):
            raise ValueError('RENDERED_VIDEO_IDENTITY_UNRESOLVED')
        editor = self.page.locator(PROMPT_SELECTOR)
        button = self.page.locator('button.generate-icon-button')
        if await editor.count() != 1 or await button.count() != 1 or not await button.is_visible():
            raise ValueError('UNAMBIGUOUS_SUBMIT_SURFACE_REQUIRED')
        return {'asset_ids': current, 'method': 'passive_response_tuple_baseline',
                'response_count': self.decoder.observed_response_count}

    async def _rendered(self):
        tiles = self.page.locator('flow-video-tile')
        urls = []
        for index in range(await tiles.count()):
            image = tiles.nth(index).locator('img.thumbnail')
            urls.append(await image.get_attribute('src') if await image.count() == 1 else '')
        return self.decoder.resolve_urls(urls)

    async def submit(self, job, prompt):
        if self._submit_invoked or job is None or job.dispatch_count != 1 or job.submission_state != 'SUBMISSION_RESERVED':
            raise ValueError('DURABLE_FIRST_DISPATCH_RESERVATION_REQUIRED')
        if sha256(self.project_id) != job.project_binding_id:
            raise ValueError('FROZEN_PROJECT_BINDING_MISMATCH')
        self._submit_invoked = True
        editor = self.page.locator(PROMPT_SELECTOR)
        button = self.page.locator('button.generate-icon-button')
        if await editor.count() != 1 or await button.count() != 1:
            raise ValueError('UNAMBIGUOUS_SUBMIT_SURFACE_REQUIRED')
        if not await editor.is_visible() or not await editor.is_editable() or not await button.is_visible():
            raise ValueError('SUBMIT_SURFACE_NOT_READY')
        await self._fill_prompt(editor, prompt)
        actual = await self._prompt_value(editor)
        if actual != prompt:
            raise ValueError('EXACT_SUBMISSION_PROMPT_UNVERIFIED')
        self._record('PROMPT_VERIFIED', {'prompt_sha256': sha256(prompt)})
        # Flow keeps Generate disabled until the editor contains a prompt.
        # Wait only after exact readback; an unenabled control never gets a click.
        for _ in range(20):
            if await button.is_enabled():
                break
            await self.page.wait_for_timeout(250)
        else:
            raise ValueError('GENERATE_BUTTON_NOT_ENABLED_AFTER_VERIFIED_PROMPT')
        if await editor.count() != 1 or await self._prompt_value(editor) != prompt:
            raise ValueError('EXACT_SUBMISSION_PROMPT_DRIFT_BEFORE_CLICK')
        guarded_button = await button.element_handle()
        if guarded_button is None:
            raise ValueError('GENERATE_BUTTON_DETACHED_BEFORE_GUARD')
        # Patchright expose_binding misses already-created isolated contexts.
        # A native CDP binding delivers the event directly to the durable sink.
        cdp = await self.page.context.new_cdp_session(self.page)
        receipt = asyncio.get_running_loop().create_future()
        binding = '__filmTrusted_' + secrets.token_hex(12)
        def trusted_click(event):
            if event.get('name') != binding or receipt.done():
                return
            try:
                payload = json.loads(event.get('payload', 'null'))
                trusted = payload == {'trusted': True, 'exact': True}
                if trusted:
                    self._record('TRUSTED_CLICK_OBSERVED')
                receipt.set_result(trusted)
            except Exception as exc:
                receipt.set_exception(exc)
        cdp.on('Runtime.bindingCalled', trusted_click)
        try:
            await cdp.send('Runtime.enable')
            await cdp.send('Runtime.addBinding', {'name': binding})
            await guarded_button.evaluate("""(e,args)=>{
              e.addEventListener('click',ev=>{
                const matches=document.querySelectorAll(args.selector);
                const editor=matches.length===1?matches[0]:null;
                const actual=editor?(editor.tagName==='TEXTAREA'?editor.value:editor.innerText):null;
                const exact=actual===args.prompt;
                if(!exact){ev.preventDefault();ev.stopImmediatePropagation()}
                window[args.binding](JSON.stringify({trusted:ev.isTrusted,exact}));
              },{capture:true,once:true})}
              """, {'binding': binding, 'selector': PROMPT_SELECTOR, 'prompt': prompt})
            self._record('CLICK_ARMED')
            self._armed = True
            await self._click_pinned_generate(guarded_button)
            trusted = await asyncio.wait_for(receipt, timeout=10)
            if not trusted:
                raise ValueError('TRUSTED_EXACT_GENERATE_CLICK_UNVERIFIED')
            reset = await self._wait_prompt_reset(editor)
        finally:
            if not receipt.done():
                receipt.cancel()
            await cdp.detach()
        return {'external_job_id': None, 'correlation_evidence': {
            'official_generate_click_completed': True,
            'trusted_generate_click': trusted, 'prompt_acceptance_transition': reset,
            'correlation_method': 'passive_response_tuple_baseline_exact_delta'}}

    async def poll(self, job):
        await self._drain()
        if hasattr(self, '_sink'):
            facts = self._sink.facts()
            kinds = {f['kind'] for f in facts}
            if 'AMBIGUOUS_EVIDENCE' in kinds:
                return {'status': 'INCONCLUSIVE', 'output_ids': []}
            bound = self._sink.bindings()
            if bound:
                return {'status': 'SUCCEEDED', 'output_ids': [b['output_id'] for b in bound]}
            durable_causal = {'PROMPT_VERIFIED', 'CLICK_ARMED', 'TRUSTED_CLICK_OBSERVED', 'PROMPT_ACCEPTANCE_TRANSITION'} <= kinds
        else:
            durable_causal = False
        if not all(job.correlation_evidence.get(k) for k in
                   ('official_generate_click_completed', 'trusted_generate_click', 'prompt_acceptance_transition')) and not durable_causal:
            return {'status': 'INCONCLUSIVE', 'output_ids': []}
        baseline = set(job.pre_dispatch_snapshot['asset_ids'])
        new = {i for i in self.decoder.identities() if i.identity not in baseline}
        if len(new) > 1:
            return {'status': 'INCONCLUSIVE', 'output_ids': []}
        if not new:
            return {'status': 'RUNNING', 'output_ids': []}
        target = next(iter(new))
        rendered = await self._rendered()
        matches = [i for i in rendered if i == target]
        if len(matches) > 1:
            return {'status': 'INCONCLUSIVE', 'output_ids': []}
        if len(matches) != 1:
            return {'status': 'RUNNING', 'output_ids': []}
        if hasattr(self, '_sink'):
            self._record('REMOTE_IDENTITY_OBSERVED', {'output_id': target.identity, 'method': 'passive_response_exact_tuple_tile'})
        return {'status': 'SUCCEEDED', 'output_ids': [target.identity],
                'correlation_evidence': {'observed_identity': target.identity,
                  'identity_binding_hash': hashlib.sha256((job.provider_job_id + target.identity).encode()).hexdigest()}}

    async def _overlay(self, action):
        marker = secrets.token_hex(12)
        # Reused Story Auto unique visible overlay control semantics.
        script = """([marker,action])=>{const visible=e=>{const r=e.getBoundingClientRect(),s=getComputedStyle(e);
          return r.width>0&&r.height>0&&s.visibility!=='hidden'&&s.display!=='none'&&!e.disabled};
          const overlays=Array.from(document.querySelectorAll('.cdk-overlay-pane,[role=menu]')).filter(visible);
          const controls=Array.from(new Set(overlays.flatMap(root=>Array.from(root.querySelectorAll('[role=menuitem],button')))))
          .filter(visible).filter(e=>action==='DOWNLOAD'?Array.from(e.querySelectorAll('i,mat-icon'))
          .some(i=>(i.textContent||'').trim()==='download'):e.matches('[role=menuitem]')&&/(^|\\s)720p($|\\s)/i.test(e.innerText||e.textContent||''));
          if(controls.length===1)controls[0].setAttribute('data-film-download-control',marker);return controls.length}"""
        for _ in range(20):
            count = await self.page.evaluate(script, [marker, action])
            if count == 1:
                return self.page.locator(f'[data-film-download-control="{marker}"]')
            if count > 1:
                raise ValueError('OFFICIAL_DOWNLOAD_CONTROL_AMBIGUOUS')
            await self.page.wait_for_timeout(250)
        raise ValueError('OFFICIAL_DOWNLOAD_CONTROL_MISSING')

    async def fetch(self, job, output_id, destination):
        destination = Path(destination)
        if destination.exists():
            raise ValueError('IMMUTABLE_OUTPUT_ALREADY_EXISTS')
        result = await self.poll(job)
        if result['status'] != 'SUCCEEDED' or output_id not in result['output_ids']:
            raise ValueError('OUTPUT_NOT_CORRELATED')
        rendered = await self._rendered()
        indices = [i for i, identity in enumerate(rendered) if identity and identity.identity == output_id]
        if len(indices) != 1:
            raise ValueError('EXACT_VIDEO_TILE_AMBIGUOUS')
        tile = self.page.locator('flow-video-tile').nth(indices[0])
        await tile.hover()
        marker = secrets.token_hex(12)
        count = await tile.evaluate("""(root,marker)=>{const buttons=Array.from(root.querySelectorAll('button'))
          .filter(e=>{const r=e.getBoundingClientRect();return r.width>0&&r.height>0&&!e.disabled})
          .filter(e=>Array.from(e.querySelectorAll('i,mat-icon')).some(i=>['more_vert','more_horiz'].includes((i.textContent||'').trim())));
          if(buttons.length===1)buttons[0].setAttribute('data-film-download-control',marker);return buttons.length}""", marker)
        if count != 1:
            raise ValueError('EXACT_TILE_MENU_AMBIGUOUS')
        await tile.locator(f'[data-film-download-control="{marker}"]').click()
        await (await self._overlay('DOWNLOAD')).click()
        resolution = await self._overlay('720P')
        async with self.page.expect_download(timeout=45000) as info:
            await resolution.click()
        download = await info.value
        destination.parent.mkdir(parents=True, exist_ok=True)
        await download.save_as(destination)
        return destination

    async def close(self):
        if hasattr(self, '_tasks'):
            for task in list(self._tasks):
                task.cancel()
            await asyncio.gather(*list(self._tasks), return_exceptions=True)
        await super().close()
