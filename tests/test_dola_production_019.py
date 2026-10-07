"""V2-019 — Dola production layer tests.

Covers: capability registry (real provider bodies), deep embedded-JSON
parsing (anti-011W rule), clean-variant resolution, account pool routing +
post-release immutability + resource policy, dormant draft lineage, plan
router, URL redaction. No network, no secrets, no mutations.
"""
from __future__ import annotations

import base64
import json
from pathlib import Path

import pytest

from film_pipeline.providers.dola_production import (
    DOLA_DRAFT_FINAL_SUPPORTED,
    DolaAccountPoolRouter,
    DolaAccountState,
    DolaAssetVariantResolver,
    DolaCapabilityRegistry,
    DolaPlanRouter,
    FinalizationAttempt,
    DraftAttempt,
    merge_registry,
    normalize_poll_payload,
    parse_composer_template,
    parse_skill_pack,
    redact_url,
)

ROOT = Path(__file__).resolve().parents[1]
PKG = ROOT / "projects/quality_v2_019_dola_productionization"


# ---------------------------------------------------------------- fixtures

@pytest.fixture(scope="module")
def skill_pack():
    return json.loads(
        (PKG / "V2_019_PHASEA_SKILL_PACK_1.json").read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def action_bar():
    return json.loads((PKG / "V2_019_PHASEA_ACTION_BAR_CONF_FULL.json")
                      .read_text(encoding="utf-8"))


def _video_model_json(lr: str, host: str = "v16-dola.dola.com",
                      definition: str = "1080p", bitrate: int = 888152,
                      list_key: str = "video_1") -> str:
    url = (f"https://{host}/video/tos/mya/abc/"
           f"?a=489823&lr={lr}&br=1734&mime_type=video_mp4")
    return json.dumps({
        "status": 10, "message": "success", "enable_ssl": True,
        "auto_definition": "360p", "enable_adaptive": False,
        "video_id": "v0abc123", "video_duration": 5.089,
        "media_type": "video",
        "video_list": {
            list_key: {
                "definition": definition, "quality": "normal",
                "vtype": "mp4", "vwidth": 1280, "vheight": 720,
                "bitrate": bitrate,
                "main_url": base64.b64encode(url.encode()).decode(),
                "file_hash": "deadbeef",
            },
        },
    })


def _poll_payload(*, lr: str = "unwatermarked") -> dict:
    """Poll-shaped payload with the real nesting: messages[0].content is a
    JSON STRING holding creation_block; video.video_model is a JSON STRING
    holding video_list (the exact V2-011W shallow-scan trap)."""
    content = json.dumps([{
        "block_type": 2074,
        "content": {"creation_block": {"creations": [{
            "id": "1542350901495057", "type": 2,
            "video": {"status": 10, "download_url":
                      f"https://v.dola.com/x?lr={lr}&sig=SECRET",
                      "video_model": _video_model_json(lr)},
        }]}},
    }])
    return {"downlink_body": {"pull_singe_chain_downlink_body": {
        "messages": [{"message_id": "m1", "content": content,
                      "create_time": 1}],
    }}}


# ------------------------------------------------------------- capability

def test_registry_from_real_skill_pack(skill_pack):
    catalog = parse_skill_pack(skill_pack)
    ids = {m.model_id for m in catalog.models}
    assert {"seedance_v2.0", "ic_mini"} <= ids
    cap = catalog.capabilities["seedance_v2.0"]
    assert cap.supported_durations == ["5", "10"]
    assert cap.supported_resolutions == ["720p"]
    assert cap.support_video_ref is False


def test_registry_from_real_action_bar(action_bar):
    catalog = parse_composer_template(action_bar)
    ids = {m.model_id for m in catalog.models}
    assert {"seedance_v2.5", "seedance_v2.0", "ic_mini"} <= ids
    gates = {m.model_id: m.gate for m in catalog.models}
    assert gates["seedance_v2.5"] == "SUBSCRIPTION_GATED"
    assert gates["seedance_v2.0"] in ("FREE", "UNKNOWN")
    assert catalog.duration_options == ["5", "10"]
    assert catalog.ratio_options == ["1:1", "3:4", "4:3", "9:16",
                                     "16:9", "21:9"]
    assert catalog.resolution_control_delivered is False


def test_merged_registry_fail_closed_gates(skill_pack, action_bar):
    registry = merge_registry(skill_pack, action_bar)
    assert isinstance(registry, DolaCapabilityRegistry)
    ok, reason = registry.supports_request(model_id="seedance_v2.0",
                                           duration="5")
    assert ok and reason == "OK"
    ok, reason = registry.supports_request(model_id="seedance_v2.5")
    assert not ok and reason == "SUBSCRIPTION_GATED"
    ok, reason = registry.supports_request(model_id="seedance_v2.0",
                                           resolution="1080p")
    assert not ok and reason == "RESOLUTION_NOT_DECLARED"
    ok, reason = registry.supports_request(model_id="ghost_model")
    assert not ok and reason == "MODEL_NOT_IN_DELIVERED_REGISTRY"
    # Phase F rule
    assert registry.true_draft_final_supported is False
    assert DOLA_DRAFT_FINAL_SUPPORTED is False


# ----------------------------------------------------------- observability

def test_deep_json_strings_peels_json_string_fields():
    payload = _poll_payload()
    texts = json.dumps(payload)
    # the video_model JSON string exists only inside a JSON string field
    assert "video_list" in texts
    peeled = list(normalize_poll_payload(payload))
    kinds = [e.kind for e in peeled]
    assert "CreationObserved" in kinds
    assert "VariantObserved" in kinds


def test_normalize_poll_payload_variants_redacted():
    events = normalize_poll_payload(_poll_payload(lr="unwatermarked"))
    variants = [e for e in events if e.kind == "VariantObserved"]
    assert variants, "deep surface missed — 011W regression"
    data = variants[0].data
    assert data["variant_lr"] == "unwatermarked"
    redacted = data["main_url"]
    assert isinstance(redacted, dict) and redacted["redacted"]
    assert "sig=SECRET" not in json.dumps(data)
    assert data["width"] == 1280 and data["height"] == 720


def test_normalize_poll_payload_credit_statement():
    content = json.dumps([{"block_type": 10000,
                           "content": {"text_block": {
                               "text": "本日の残り 3 枚の動画クレジット…"}}}])
    payload = {"downlink_body": {"pull_singe_chain_downlink_body": {
        "messages": [{"message_id": "m2", "content": content}]}}}
    events = normalize_poll_payload(payload)
    credits = [e for e in events if e.kind == "CreditStatementObserved"]
    assert credits and credits[0].data["remaining"] == 3


def test_redact_url_keeps_names_not_values():
    red = redact_url("https://v16-dola.dola.com/a/b?lr=unwatermarked"
                     "&sig=SECRETVALUE&rc=ZGczaTc6")
    assert red["host"] == "v16-dola.dola.com"
    assert set(red["query_param_names"]) == {"lr", "sig", "rc"}
    assert "SECRETVALUE" not in json.dumps(red)
    assert "ZGczaTc6" not in json.dumps(red)


# ---------------------------------------------------------------- variants

def _creation(lr: str) -> dict:
    return {"id": "c1", "video": {
        "status": 10, "video_model": _video_model_json(lr)}}


def test_resolver_prefers_provider_issued_unwatermarked():
    resolver = DolaAssetVariantResolver()
    selection = resolver.select(_creation("unwatermarked"))
    assert selection.authority == "PROVIDER_ISSUED_UNWATERMARKED"
    assert selection.variant.variant_lr == "unwatermarked"


def test_resolver_falls_back_to_watermarked():
    resolver = DolaAssetVariantResolver()
    selection = resolver.select(_creation("cici_ai"))
    assert selection.authority == "PROVIDER_ISSUED_WATERMARKED"


def test_resolver_fail_closed_without_renditions():
    resolver = DolaAssetVariantResolver()
    selection = resolver.select({"id": "c2", "video": {"status": 5}})
    assert selection.authority == "NOT_FOUND"


def test_resolver_rejects_disallowed_host():
    video_model = _video_model_json("unwatermarked", host="evil.example.com")
    resolver = DolaAssetVariantResolver()
    selection = resolver.select({"id": "c3",
                                 "video": {"video_model": video_model}})
    assert selection.authority == "NOT_FOUND"


def test_resolver_ambiguous_distinct_clean_renditions_fail_closed():
    video_model = json.dumps({
        "video_list": {
            "video_1": {"definition": "1080p", "bitrate": 888152,
                        "main_url": base64.b64encode(
                            "https://v16-dola.dola.com/a?lr=unwatermarked"
                            .encode()).decode()},
            "video_2": {"definition": "720p", "bitrate": 400000,
                        "main_url": base64.b64encode(
                            "https://v19-dola.dola.com/b?lr=unwatermarked"
                            .encode()).decode()},
        }})
    resolver = DolaAssetVariantResolver()
    selection = resolver.select({"id": "c4",
                                 "video": {"video_model": video_model}})
    assert selection.authority == "NOT_FOUND"
    assert "ambiguous" in selection.reason


# -------------------------------------------------------------------- pool

def _account(alias: str, credit: int | None = 5,
             session: str = "READY") -> DolaAccountState:
    return DolaAccountState(
        account_alias=alias, profile_binding=f"profiles/{alias}",
        session_state=session, known_credit_state=credit)


def test_pool_select_prefers_credit_then_lru():
    router = DolaAccountPoolRouter()
    router.register(_account("ACCOUNT_A", credit=3, session="SESSION_VALID"))
    router.register(_account("ACCOUNT_B", credit=9, session="SESSION_VALID"))
    router.register(_account("ACCOUNT_C", credit=0, session="NO_CREDIT"))
    router.account("ACCOUNT_A").last_used_at = "2026-10-07T00:00:00+00:00"
    decision = router.select()
    assert decision.selected_alias == "ACCOUNT_B"


def test_pool_select_skips_busy_cooldown_and_gated_model():
    router = DolaAccountPoolRouter()
    router.register(_account("ACCOUNT_A", credit=9))
    router.account("ACCOUNT_A").active_attempt_id = "att1"
    router.register(_account("ACCOUNT_B", credit=9))
    router.account("ACCOUNT_B").cooldown_until = "2999-01-01T00:00:00+00:00"
    router.register(_account("ACCOUNT_C", credit=9))
    router.account("ACCOUNT_C").model_entitlements = {"seedance_v2.5": False}
    decision = router.select(model_id="seedance_v2.5")
    assert decision.selected_alias is None
    assert decision.resource_state == "CURRENT_ACCOUNT_INSUFFICIENT"


def test_pool_post_release_binding_immutable():
    router = DolaAccountPoolRouter()
    router.register(_account("ACCOUNT_A"))
    router.register(_account("ACCOUNT_B"))
    router.bind_release(attempt_id="att9", account_alias="ACCOUNT_A",
                        conversation_id="38417944671772433",
                        request_identity="16852.1008")
    assert router.rotate_allowed("att9") is False
    binding = router.binding("att9")
    assert binding.account_alias == "ACCOUNT_A"
    with pytest.raises(ValueError):
        router.bind_release(attempt_id="att9", account_alias="ACCOUNT_B")
    # duplicate bind to the SAME account is idempotent
    again = router.bind_release(attempt_id="att9", account_alias="ACCOUNT_A")
    assert again.conversation_id == "38417944671772433"


def test_pool_resource_states_never_owner_exhausted():
    router = DolaAccountPoolRouter()
    for alias in ("ACCOUNT_A", "ACCOUNT_B"):
        router.register(_account(alias, credit=0, session="NO_CREDIT"))
    decision = router.select()
    assert decision.selected_alias is None
    assert decision.resource_state == "KNOWN_POOL_INSUFFICIENT"
    router.register(_account("ACCOUNT_C", credit=0, session="LOGIN_REQUIRED"))
    assert router.resource_state_for("ACCOUNT_A") == \
        "KNOWN_POOL_INSUFFICIENT"
    # the forbidden state is never produced by any router path
    states = {decision.resource_state,
              router.resource_state_for("ACCOUNT_A")}
    assert "OWNER_RESOURCE_EXHAUSTED" not in states
    assert router.forbidden_state() == "OWNER_RESOURCE_EXHAUSTED"


def test_pool_state_carries_no_secret_material():
    state = _account("ACCOUNT_A")
    blob = json.dumps(state.tracked_view())
    for marker in ("sessionid", "cookie", "Bearer", "token"):
        assert marker not in blob.lower() or marker == "token" and \
            "token" not in blob.lower()


def test_pool_complete_attempt_records_health():
    router = DolaAccountPoolRouter()
    router.register(_account("ACCOUNT_A"))
    router.bind_release(attempt_id="att5", account_alias="ACCOUNT_A")
    router.complete_attempt("att5", success=False)
    state = router.account("ACCOUNT_A")
    assert state.active_attempt_id is None
    assert state.last_failure_code == "ATTEMPT_FAILED"
    assert state.last_failure_at is not None


# ------------------------------------------------------------------- draft

def test_draft_finalization_lineage_enforced():
    drafts = {"d1": DraftAttempt(draft_attempt_id="d1",
                                 provider_id="byteplus_seedance")}
    fin = FinalizationAttempt(finalization_attempt_id="f1",
                              provider_id="byteplus_seedance",
                              draft_attempt_id="d1")
    fin.validate_lineage(drafts)  # OK
    fin_bad = FinalizationAttempt(finalization_attempt_id="f2",
                                  provider_id="byteplus_seedance",
                                  draft_attempt_id="missing")
    with pytest.raises(ValueError):
        fin_bad.validate_lineage(drafts)
    fin_cross = FinalizationAttempt(finalization_attempt_id="f3",
                                    provider_id="dola_seedance",
                                    draft_attempt_id="d1")
    with pytest.raises(ValueError):
        fin_cross.validate_lineage(drafts)


# ----------------------------------------------------------------- routing

def test_plan_router_normal_final_multiplier(skill_pack, action_bar):
    router = DolaPlanRouter(merge_registry(skill_pack, action_bar))
    plan = router.plan(model_id="seedance_v2.0", duration="5")
    assert plan.plan_mode == "NORMAL_FINAL"
    assert plan.expected_generations == 1
    assert plan.expected_total_credits == 1


def test_plan_router_refuses_draft_then_final_on_dola(skill_pack,
                                                      action_bar):
    router = DolaPlanRouter(merge_registry(skill_pack, action_bar))
    with pytest.raises(ValueError, match="draft->final"):
        router.plan(model_id="seedance_v2.0", mode="DRAFT_THEN_FINAL")


def test_plan_router_refuses_gated_model(skill_pack, action_bar):
    router = DolaPlanRouter(merge_registry(skill_pack, action_bar))
    with pytest.raises(ValueError, match="SUBSCRIPTION_GATED"):
        router.plan(model_id="seedance_v2.5")


def test_plan_router_low_cost_exploration_picks_free(skill_pack,
                                                     action_bar):
    router = DolaPlanRouter(merge_registry(skill_pack, action_bar))
    plan = router.plan(model_id="seedance_v2.0", mode="LOW_COST_EXPLORATION")
    assert plan.model_id in ("ic_mini", "seedance_v2.0")
    assert plan.expected_total_credits == 1
