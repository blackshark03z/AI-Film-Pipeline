"""Bounded single-canary orchestration; no implicit retry or new DB per run."""
import asyncio
import hashlib
from pathlib import Path

from .compiler import compile_prompt
from .core import load_shot, sha256
from .execution import DryRunProvider, route
from .live_runtime import LiveRuntimeExecutor
from .providers.flow_network import FlowNetworkTransport as FlowLiveTransport
from .providers.flow_veo import FlowConfig, FlowVeoProvider
from .store import SQLiteStore


async def run_canary(config: FlowConfig, *, authorize_new_submit=False, runtime_path=None, poll_limit=60, poll_interval=5):
    # SLICE-0005 is deterministic remediation, with no fresh Generate authority.
    # Recovery is exposed through the executor and never through this submit gate.
    if not authorize_new_submit:
        return {'result': 'INCONCLUSIVE', 'diagnostic': 'FRESH_GENERATE_AUTHORIZATION_REQUIRED', 'dispatch_count': 0}
    prior_path = Path('projects/flow_canary/runtime.sqlite').resolve()
    if runtime_path is None or Path(runtime_path).resolve() == prior_path:
        raise ValueError('FRESH_AUTHORIZED_RUNTIME_PATH_REQUIRED')
    provider = FlowVeoProvider(config)
    health = await provider.preflight()
    if health.state != 'READY':
        return {'result': 'INCONCLUSIVE', 'preflight': health.payload(), 'dispatch_count': 0}
    transport = FlowLiveTransport(config)
    store = SQLiteStore(Path(runtime_path))
    store.initialize()
    executor = LiveRuntimeExecutor(store, transport)
    try:
        await transport.open()
        # Existing reserved intent is recovered first, never replaced or redispatched.
        connection = store._connect()
        try:
            rows = connection.execute('SELECT id FROM provider_jobs').fetchall()
        finally:
            connection.close()
        if len(rows) > 1:
            raise ValueError('MULTIPLE_CANARY_INTENTS')
        if rows:
            job = store.read_provider_job(rows[0][0])
            if job.dispatch_count == 0:
                raise ValueError('EXISTING_UNDISPATCHED_INTENT_REQUIRES_RECONCILIATION')
            if job.project_binding_id != sha256(transport.project_id):
                raise ValueError('RECOVERY_PROJECT_MISMATCH')
        else:
            shot = load_shot(Path(__file__).resolve().parents[2] / 'fixtures/flow_canary.json')
            caps = provider.capabilities()
            plan = compile_prompt(shot, caps)
            decision = route(shot, [plan], [caps], {caps.provider_id: True})
            dry = DryRunProvider()
            attempt = dry.create_attempt(shot, plan, decision, dry.build_request(plan, decision))
            snapshot = await transport.snapshot()
            if (await provider.preflight()).state != 'READY':
                return {'result': 'INCONCLUSIVE', 'diagnostic': 'PREDISPATCH_NOT_READY', 'dispatch_count': 0}
            job = executor.freeze_path(shot, plan, decision, attempt,
                project_binding_id=sha256(transport.project_id),
                pre_dispatch_snapshot=snapshot)
            # Freeze is durable before the only reservation/click path.
            try:
                job = await executor.submit_once(job.provider_job_id)
            except Exception:
                job = store.read_provider_job(job.provider_job_id)
        for _ in range(poll_limit):
            job = await executor.reconcile(job.provider_job_id)
            if job.status in {'SUCCEEDED', 'FAILED', 'INCONCLUSIVE'}:
                break
            await asyncio.sleep(poll_interval)
        if job.status != 'SUCCEEDED':
            return {'result': 'INCONCLUSIVE', 'dispatch_count': job.dispatch_count, 'terminal_state': job.status,
                    'provider_job_id': job.provider_job_id}
        assets = await executor.download_assets(job.provider_job_id, Path('projects/flow_canary/outputs'))
        recovered = SQLiteStore(store.path).read_runtime_lineage(job.generation_attempt_id, job.provider_job_id)
        if len(recovered[-1]) != len(assets):
            raise ValueError('ASSET_READBACK_MISMATCH')
        for asset in recovered[-1]:
            if hashlib.sha256(Path(asset.uri_or_path).read_bytes()).hexdigest() != asset.sha256:
                raise ValueError('ASSET_HASH_MISMATCH')
        return {'result': 'PROVEN', 'dispatch_count': job.dispatch_count, 'provider_job_id': job.provider_job_id,
                'asset_ids': [a.asset_id for a in assets], 'fresh_readback': True}
    finally:
        await transport.close()
