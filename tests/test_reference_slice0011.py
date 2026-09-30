"""Reference assets and exact image-input planning without provider effects."""

import base64
import hashlib
import sqlite3
from pathlib import Path

import pytest
import json
from unittest.mock import Mock

from film_pipeline.compiler import compile_prompt
from film_pipeline.core import ProviderCapabilities, References, load_shot
from film_pipeline.execution import route
from film_pipeline.live_runtime import Asset
from film_pipeline.providers.flow_reference_upload import OwnerAmbiguityGate, ReferenceUploadStore
from film_pipeline.providers import flow_rpc_contract as rpc_contract
from film_pipeline.providers.flow_reference_transport import FlowReferenceTransport
from film_pipeline.slice0011 import (REFERENCE_ASSET_ID, REFERENCE_SHA256,
                                     compile_character_paths, freeze_reference,
                                     validate_character_pair, upload_reference_once,
                                     freeze_shot_job, submit_and_acquire_shot,
                                     reconcile_and_acquire_shot, PROJECT_ID, ACCOUNT_ID)
from film_pipeline.store import SQLiteStore


TINY_PNG = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAusB9xY3f7sAAAAASUVORK5CYII="
)


def reference(tmp_path: Path) -> Asset:
    path = tmp_path / "reference.png"
    path.write_bytes(TINY_PNG)
    return Asset(asset_id="asset_synthetic_reference", asset_type="image",
                 origin="reference", uri_or_path=str(path.resolve()),
                 sha256=hashlib.sha256(TINY_PNG).hexdigest(), mime_type="image/png",
                 width=1, height=1, file_size=len(TINY_PNG),
                 rights_metadata={"source_kind": "test_generated_png"})


def test_reference_asset_has_no_fake_generation_lineage(tmp_path):
    store = SQLiteStore(tmp_path / "runtime.sqlite")
    store.initialize()
    item = reference(tmp_path)
    store.save_reference_asset(item)
    assert store.read_reference_asset(item.asset_id) == item
    with sqlite3.connect(store.path) as connection:
        row = connection.execute("SELECT generation_attempt_id,provider_job_id "
                                 "FROM assets WHERE id=?", (item.asset_id,)).fetchone()
    assert row == (None, None)
    store.save_reference_asset(item)


def test_legacy_asset_table_migrates_only_on_reference_save(tmp_path):
    store = SQLiteStore(tmp_path / "legacy.sqlite")
    store.initialize()
    with sqlite3.connect(store.path) as connection:
        connection.execute("DROP TABLE assets")
        connection.execute("CREATE TABLE assets (id TEXT PRIMARY KEY, "
            "generation_attempt_id TEXT NOT NULL, provider_job_id TEXT NOT NULL, "
            "payload TEXT NOT NULL)")
    store.save_reference_asset(reference(tmp_path))
    assert store.read_reference_asset("asset_synthetic_reference").origin == "reference"
    with sqlite3.connect(store.path) as connection:
        columns = {row[1]: row[3] for row in connection.execute("PRAGMA table_info(assets)")}
    assert columns["generation_attempt_id"] == columns["provider_job_id"] == 0


def test_missing_or_changed_reference_bytes_rejected(tmp_path):
    store = SQLiteStore(tmp_path / "runtime.sqlite")
    store.initialize()
    item = reference(tmp_path)
    store.save_reference_asset(item)
    Path(item.uri_or_path).write_bytes(TINY_PNG + b"tamper")
    with pytest.raises(ValueError, match="bytes or provenance mismatch"):
        store.read_reference_asset(item.asset_id)
    Path(item.uri_or_path).unlink()
    with pytest.raises(ValueError, match="local file missing"):
        store.read_reference_asset(item.asset_id)


def test_generated_asset_still_requires_real_lineage():
    with pytest.raises(ValueError, match="generated Asset requires"):
        Asset(asset_id="bad", uri_or_path="video.mp4", sha256="0" * 64,
              file_size=1)


def test_one_image_input_binds_asset_and_hash_and_t2v_route_fails(tmp_path):
    item = reference(tmp_path)
    shot = load_shot(Path(__file__).resolve().parents[1] / "fixtures/flow_canary_shot2.json")
    shot.references = References(character_asset_ids=[item.asset_id])
    capable = ProviderCapabilities(profile_version="flow-reference-fixture-v1",
        provider_id="flow_veo", transport_type="browser_cookie", supports_image_input=True)
    plan = compile_prompt(shot, capable, reference_hashes={item.asset_id: item.sha256})
    assert plan.mapped_controls["image_input"] == [
        {"asset_id": item.asset_id, "sha256": item.sha256}]
    assert "image_input" not in plan.degraded_controls
    assert "image_input" in route(shot, [plan], [capable], {"flow_veo": True},
                                  required_controls={"image_input"}).required_capabilities
    changed = compile_prompt(shot, capable, reference_hashes={item.asset_id: "0" * 64})
    assert changed.prompt_plan_id != plan.prompt_plan_id
    with pytest.raises(ValueError, match="reference hash binding"):
        compile_prompt(shot, capable, reference_hashes={"wrong_asset": item.sha256})
    t2v = capable.model_copy(update={"supports_image_input": False})
    fallback = compile_prompt(shot, t2v, reference_hashes={item.asset_id: item.sha256})
    assert "image_input" in fallback.unsupported_controls
    with pytest.raises(ValueError, match="required mapped controls"):
        route(shot, [fallback], [t2v], {"flow_veo": True},
              required_controls={"image_input"})


def test_shared_upload_reservation_is_one_shot_and_reusable_after_receipt(tmp_path):
    runtime = SQLiteStore(tmp_path / "runtime.sqlite")
    runtime.initialize()
    item = reference(tmp_path)
    runtime.save_reference_asset(item)
    uploads = ReferenceUploadStore(runtime.path)
    project_id = "f6b40e79-d6f8-4354-80ae-c863260e96f5"
    account = "fixture-account"
    assert uploads.read_verified("flow_veo", project_id, account, item) is None
    reservation = uploads.reserve_once("flow_veo", project_id, account, item)
    with pytest.raises(OwnerAmbiguityGate, match="reserved without"):
        uploads.read_verified("flow_veo", project_id, account, item)
    with pytest.raises(OwnerAmbiguityGate, match="already reserved"):
        uploads.reserve_once("flow_veo", project_id, account, item)
    uploads.record_identified(reservation['id'], "9f2ef342-65e7-4af0-ad3e-a65b921f0e16",
                              method='fixture_response', evidence_hash='2' * 64)
    receipt = uploads.complete(reservation, "9f2ef342-65e7-4af0-ad3e-a65b921f0e16",
                               "1" * 64)
    assert receipt["upload_attempts"] == 1
    assert uploads.read_verified("flow_veo", project_id, account, item) == receipt
    with pytest.raises(OwnerAmbiguityGate, match="already reserved"):
        uploads.reserve_once("flow_veo", project_id, account, item)


def test_real_synthetic_fixture_frozen_as_one_reference_and_both_plans_bind_it(tmp_path):
    db = tmp_path / "runtime.sqlite"
    asset = freeze_reference(db, tmp_path / "reference")
    assert (asset.asset_id, asset.sha256) == (REFERENCE_ASSET_ID, REFERENCE_SHA256)
    same = freeze_reference(db, tmp_path / "reference")
    assert same == asset
    ref, profile, paths = compile_character_paths(db)
    assert ref == asset and profile.supports_image_input
    assert [shot.shot_id for shot, _, _ in paths] == [
        "CHAR_CONTINUITY_A", "CHAR_CONTINUITY_B"]
    for shot, plan, decision in paths:
        assert shot.references.character_asset_ids == [asset.asset_id]
        assert plan.mapped_controls["image_input"] == [
            {"asset_id": asset.asset_id, "sha256": asset.sha256}]
        assert "image_input" in decision.required_capabilities


def test_character_pair_rejects_changed_identity_look_and_reference(monkeypatch):
    first, second = validate_character_pair()
    from film_pipeline import slice0011

    def changed_pair(field, value):
        changed = second.model_copy(deep=True)
        setattr(changed.characters[0], field, value)
        monkeypatch.setattr(slice0011, "load_shot", lambda path: first if path ==
                            slice0011.SHOT_A_PATH else changed)
        with pytest.raises(ValueError):
            validate_character_pair()

    changed_pair("identity_version", "ID_V2")
    changed_pair("look_state_id", "LOOK_V2")
    wrong = second.model_copy(deep=True)
    wrong.references.character_asset_ids = ["wrong_asset"]
    monkeypatch.setattr(slice0011, "load_shot", lambda path: first if path ==
                        slice0011.SHOT_A_PATH else wrong)
    with pytest.raises(ValueError, match="exact character/reference"):
        validate_character_pair()


class FakeSession:
    project_id = PROJECT_ID
    catalog_fingerprint = rpc_contract.QUALIFIED_BASELINE_FINGERPRINT

    def __init__(self):
        self.records = []
        self.uploads = 0
        self.submits = 0
        self.remote_images = {}

    def catalog(self):
        return self.records

    def upload_reference(self, source_bytes, request_id, *, before_post,
                         on_http_response, on_identified):
        before_post('2' * 64)
        self.uploads += 1
        media_id = "9f2ef342-65e7-4af0-ad3e-a65b921f0e16"
        self.remote_images[media_id] = source_bytes
        on_http_response(200, 100)
        on_identified(media_id)
        return media_id

    def media(self, media_id, kind):
        return self.remote_images.get(media_id)

    def submit_once(self, prompt, reference_id, request_id, *, before_post):
        self.submits += 1
        before_post("2" * 64)
        raise TimeoutError("HTTP outcome unknown")


def _prepared_pair(tmp_path):
    db = tmp_path / "runtime.sqlite"
    reference = freeze_reference(db, tmp_path / "reference")
    session = FakeSession()
    receipt = FlowReferenceTransport(ReferenceUploadStore(db), session,
        account_id=ACCOUNT_ID, evidence_dir=tmp_path / 'evidence', interval_s=0).ensure_verified(reference)
    paths = compile_character_paths(db)[2]
    return db, session, receipt, paths


def test_ambiguous_upload_stops_and_restart_cannot_upload_again(tmp_path):
    db = tmp_path / "runtime.sqlite"
    reference = freeze_reference(db, tmp_path / "reference")
    session = FakeSession()
    def lost_response(*args, **kwargs):
        kwargs['before_post']('2' * 64)
        raise TimeoutError('unknown')
    session.upload_reference = Mock(side_effect=lost_response)
    with pytest.raises(OwnerAmbiguityGate, match="upload armed"):
        FlowReferenceTransport(ReferenceUploadStore(db), session, account_id=ACCOUNT_ID,
            evidence_dir=tmp_path / 'evidence', interval_s=0).ensure_verified(reference)
    with pytest.raises(OwnerAmbiguityGate, match="forensic"):
        upload_reference_once(db, FakeSession(), reference)
    assert session.upload_reference.call_count == 1


def test_catalog_drift_prevents_upload_reservation(tmp_path):
    db = tmp_path / "runtime.sqlite"
    reference = freeze_reference(db, tmp_path / "reference")
    session = FakeSession()
    session.catalog = Mock(side_effect=ValueError("catalog drift"))
    with pytest.raises(ValueError, match="catalog drift"):
        FlowReferenceTransport(ReferenceUploadStore(db), session, account_id=ACCOUNT_ID,
            evidence_dir=tmp_path / 'evidence', interval_s=0).ensure_verified(reference)
    assert session.uploads == 0
    assert ReferenceUploadStore(db).read_verified(
        "flow_veo", PROJECT_ID, ACCOUNT_ID, reference) is None


def test_slice_upload_authority_cannot_switch_project_or_account(tmp_path):
    db = tmp_path / "runtime.sqlite"
    reference = freeze_reference(db, tmp_path / "reference")
    session = FakeSession()
    with pytest.raises(ValueError, match="authority"):
        upload_reference_once(db, session, reference, account_id="other")
    with pytest.raises(ValueError, match="only the frozen"):
        upload_reference_once(db, session, reference.model_copy(update={
            "asset_id": "wrong_reference"}))
    assert session.uploads == 0
    with pytest.raises(OwnerAmbiguityGate, match='no production upload'):
        upload_reference_once(db, session, reference)
    receipt = FlowReferenceTransport(ReferenceUploadStore(db), session, account_id=ACCOUNT_ID,
        evidence_dir=tmp_path / 'evidence', interval_s=0).ensure_verified(reference)
    with pytest.raises(OwnerAmbiguityGate, match="already reserved"):
        ReferenceUploadStore(db).reserve_once("flow_veo",
            "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee", "other", reference)
    assert receipt["upload_attempts"] == session.uploads == 1


def test_one_verified_upload_reused_and_two_shots_freeze_same_binding(tmp_path, monkeypatch):
    db, session, receipt, paths = _prepared_pair(tmp_path)
    reference = SQLiteStore(db).read_reference_asset(REFERENCE_ASSET_ID)
    assert upload_reference_once(db, session, reference) == receipt
    assert session.uploads == 1
    with pytest.raises(ValueError, match="Shot A must be acquired"):
        freeze_shot_job(db, session, paths[1], receipt)
    from film_pipeline import slice0011
    monkeypatch.setattr(slice0011, "_require_acquired_shot_a", lambda store: None)
    jobs = [freeze_shot_job(db, session, path, receipt) for path in paths]
    assert jobs[0].provider_job_id != jobs[1].provider_job_id
    assert [job.correlation_evidence["reference_binding"]["media_id"] for job in jobs] == [
        receipt["media_id"], receipt["media_id"]]
    assert freeze_shot_job(db, session, paths[0], receipt) == jobs[0]
    with pytest.raises(ValueError, match="FROZEN_PROVIDER_INTENT_CHANGED"):
        SQLiteStore(db).save_provider_job(jobs[0].model_copy(update={
            "correlation_evidence": {**jobs[0].correlation_evidence,
                "reference_binding": {**jobs[0].correlation_evidence["reference_binding"],
                    "media_id": "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee"}}}))


def test_ambiguous_submit_is_one_shot_and_restart_never_redispatches(tmp_path):
    db, session, receipt, paths = _prepared_pair(tmp_path)
    job = freeze_shot_job(db, session, paths[0], receipt)
    with pytest.raises(OwnerAmbiguityGate, match="shot reserved"):
        submit_and_acquire_shot(db, session, job, tmp_path / "video", poll_seconds=0)
    assert session.submits == 1
    fresh = SQLiteStore(db).read_provider_job(job.provider_job_id)
    assert fresh.dispatch_count == 1
    with pytest.raises(OwnerAmbiguityGate, match="no redispatch"):
        submit_and_acquire_shot(db, session, fresh, tmp_path / "video", poll_seconds=0)
    assert session.submits == 1


def _catalog_record(prompt, reference_id, output_id):
    raw = json.loads((Path(__file__).parent / "fixtures/flow_rpc_catalog_redacted.json").read_text())["record"]
    replacements = {"OUTPUT": output_id, "PROJECT": PROJECT_ID,
                    "REFERENCE": reference_id, "MODEL": "abra_r2v_8s", "PROMPT": prompt}
    def fill(node):
        return [fill(item) for item in node] if isinstance(node, list) else replacements.get(node, node) if isinstance(node, str) else node
    row = fill(raw)
    row[3] = "CAE"
    return row


def test_exact_output_attribution_rejects_collision_and_reference_tamper():
    prompt = "exact prompt with unique job marker"
    reference_id = "9f2ef342-65e7-4af0-ad3e-a65b921f0e16"
    first = _catalog_record(prompt, reference_id, "99999999-8888-7777-6666-555555555555")
    assert rpc_contract.match_output([first], PROJECT_ID, prompt, reference_id) == first
    with pytest.raises(rpc_contract.ContractError, match="OUTPUT_AMBIGUOUS"):
        rpc_contract.match_output([first, _catalog_record(prompt, reference_id,
            "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee")], PROJECT_ID, prompt, reference_id)
    with pytest.raises(rpc_contract.ContractError, match="OUTPUT_REFERENCE_MISMATCH"):
        rpc_contract.match_output([first], PROJECT_ID, prompt,
                                  "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee")


def test_restart_reconciles_exact_output_without_new_submit(tmp_path, monkeypatch):
    from film_pipeline import slice0011
    db, session, receipt, paths = _prepared_pair(tmp_path)
    job = freeze_shot_job(db, session, paths[0], receipt)
    store = SQLiteStore(db)
    store.reserve_dispatch(job.provider_job_id)
    request_hash = job.correlation_evidence["rpc_request_hash"]
    request = {"request_hash": request_hash, "body_sha256": "2" * 64,
               "contract": slice0011.RPC_CONTRACT}
    store.record_dispatch_fact(job.provider_job_id, "RPC_REQUEST_ARMED", request)
    store.record_dispatch_fact(job.provider_job_id, "GENERATE_REQUEST_OBSERVED", request)
    output_id = "99999999-8888-7777-6666-555555555555"
    session.records = [_catalog_record(job.correlation_evidence["prompt"],
                                      receipt["media_id"], output_id)]
    expected = object()
    monkeypatch.setattr(slice0011, "_acquire_bound", lambda *args: expected)
    assert reconcile_and_acquire_shot(db, session, job, tmp_path / "video") is expected
    fresh = store.read_provider_job(job.provider_job_id)
    assert fresh.dispatch_count == 1 and fresh.external_job_id == output_id
    assert len(store.read_output_bindings(job.provider_job_id)) == 1
    assert reconcile_and_acquire_shot(db, session, fresh, tmp_path / "video") is expected
    assert session.submits == 0


def test_restart_without_network_request_fact_returns_owner_gate(tmp_path):
    db, session, receipt, paths = _prepared_pair(tmp_path)
    job = freeze_shot_job(db, session, paths[0], receipt)
    SQLiteStore(db).reserve_dispatch(job.provider_job_id)
    session.records = [_catalog_record(job.correlation_evidence["prompt"],
        receipt["media_id"], "99999999-8888-7777-6666-555555555555")]
    with pytest.raises(OwnerAmbiguityGate, match="cannot be reconciled"):
        reconcile_and_acquire_shot(db, session, job, tmp_path / "video")
    assert session.submits == 0


def test_restart_conflicting_external_identity_stops_before_binding(tmp_path):
    from film_pipeline import slice0011
    db, session, receipt, paths = _prepared_pair(tmp_path)
    job = freeze_shot_job(db, session, paths[0], receipt)
    store = SQLiteStore(db)
    reserved = store.reserve_dispatch(job.provider_job_id)
    request = {"request_hash": job.correlation_evidence["rpc_request_hash"],
               "body_sha256": "2" * 64, "contract": slice0011.RPC_CONTRACT}
    store.record_dispatch_fact(job.provider_job_id, "RPC_REQUEST_ARMED", request)
    store.record_dispatch_fact(job.provider_job_id, "GENERATE_REQUEST_OBSERVED", request)
    conflicting = reserved.model_copy(update={
        "external_job_id": "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee"})
    store.save_provider_job(conflicting)
    session.records = [_catalog_record(job.correlation_evidence["prompt"],
        receipt["media_id"], "99999999-8888-7777-6666-555555555555")]
    with pytest.raises(OwnerAmbiguityGate, match="identity changed"):
        reconcile_and_acquire_shot(db, session, conflicting, tmp_path / "video")
    assert store.read_output_bindings(job.provider_job_id) == []
