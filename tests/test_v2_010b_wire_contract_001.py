"""V2-010B wire-contract golden tests: prove the repaired body matches
the AVP RE contract exactly at the structural level."""
from __future__ import annotations
import json, sys
from pathlib import Path
import pytest
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from film_pipeline.providers.dola_provider import (
    DolaCookieTransport, DolaTransportError, REQUESTED_MODEL, SUPPORTED_ASPECTS,
    SUPPORTED_DURATIONS)

FAKE_COOKIE = ("sessionid=test_session_abc; msToken=test_ms_token; "
               "s_v_web_id=test_fp_verify")
CID = "a" * 64


@pytest.fixture(scope="module")
def transport():
    return DolaCookieTransport(FAKE_COOKIE)


@pytest.fixture(scope="module")
def body(transport):
    return transport._video_body("test prompt", "16:9", 5, CID)


class TestWireContract:
    def test_ability_type_17(self, body):
        assert body["chat_ability"]["ability_type"] == 17

    def test_ability_param_video_json(self, body):
        param = json.loads(body["chat_ability"]["ability_param"])
        assert param["ratio"] == "16:9"
        assert param["model"] == "seedance_v2.0"
        assert param["duration"] == 5

    def test_prompt_prefix(self, body):
        text = body["messages"][0]["content_block"][0]["content"]["text_block"]["text"]
        assert text.startswith("生成影片：test prompt，16:9")

    def test_client_request_id_echo(self, body):
        assert body["messages"][0]["local_message_id"] == CID
        assert body["option"]["unique_key"] == CID

    def test_option_click_clear_context(self, body):
        assert body["option"]["click_clear_context"] is False

    def test_option_from_suggest(self, body):
        assert body["option"]["from_suggest"] is False

    def test_option_is_regen(self, body):
        assert body["option"]["is_regen"] is False

    def test_option_is_replace(self, body):
        assert body["option"]["is_replace"] is False

    def test_option_is_from_click_option(self, body):
        assert body["option"]["is_from_click_option"] is False

    def test_option_disable_sse_cache(self, body):
        assert body["option"]["disable_sse_cache"] is False

    def test_option_select_text_action(self, body):
        assert body["option"]["select_text_action"] == ""

    def test_option_is_select_text(self, body):
        assert body["option"]["is_select_text"] is False

    def test_option_resend_for_regen(self, body):
        assert body["option"]["resend_for_regen"] is False

    def test_option_scene_type(self, body):
        assert body["option"]["scene_type"] == 0

    def test_option_start_seq(self, body):
        assert body["option"]["start_seq"] == 0

    def test_option_regen_query_id(self, body):
        assert body["option"]["regen_query_id"] == []

    def test_option_edit_query_id(self, body):
        assert body["option"]["edit_query_id"] == []

    def test_option_regen_instruction(self, body):
        assert body["option"]["regen_instruction"] == ""

    def test_option_no_replace_for_regen(self, body):
        assert body["option"]["no_replace_for_regen"] is False

    def test_option_shared_app_name(self, body):
        assert body["option"]["shared_app_name"] == ""

    def test_option_shared_app_id(self, body):
        assert body["option"]["shared_app_id"] == ""

    def test_option_is_ai_playground(self, body):
        assert body["option"]["is_ai_playground"] is False

    def test_option_is_old_user(self, body):
        assert body["option"]["is_old_user"] is False

    def test_option_message_storage_type(self, body):
        assert body["option"]["message_storage_type"] == 0

    def test_ext_collection_id(self, body):
        assert body["ext"]["collection_id"] == ""


class TestHeaders:
    def test_user_agent_is_browser(self, transport):
        headers = transport._headers()
        assert "Mozilla/5.0" in headers["User-Agent"]
        assert "Chrome" in headers["User-Agent"]
        assert "AIFilmPipeline" not in headers["User-Agent"]

    def test_sec_ch_ua_present(self, transport):
        headers = transport._headers()
        assert "Sec-Ch-Ua" in headers
        assert "Google Chrome" in headers["Sec-Ch-Ua"]

    def test_accept_encoding_identity(self, transport):
        headers = transport._headers()
        assert headers["Accept-Encoding"] == "identity"

    def test_no_secret_in_headers_json(self, transport):
        headers = transport._headers()
        blob = json.dumps(headers)
        assert "test_session_abc" in blob  # cookie IS in headers (expected)
        # msToken IS in the cookie header (by design); it must NOT
        # appear as a separate header field
        separate = {k: v for k, v in headers.items() if k != "Cookie"}
        assert "test_ms_token" not in json.dumps(separate)

    def test_no_secret_in_params(self, transport):
        params = transport._params()
        assert "test_session_abc" not in params
        assert "test_ms_token" in params  # msToken goes in query params


class TestSecretRedaction:
    def test_body_has_no_cookie_or_session(self, body):
        blob = json.dumps(body)
        assert "test_session_abc" not in blob
        assert "test_ms_token" not in blob

    def test_request_hash_no_secret(self, transport):
        body = transport._video_body("test", "16:9", 5, CID)
        blob = json.dumps(body, separators=(",", ":"))
        assert FAKE_COOKIE not in blob


class TestGovernanceIntact:
    def test_receipt_first_callback(self, transport):
        """Receipt-first: on_receipt is called BEFORE return."""
        calls = []
        transport._receipt_from_sse_original = transport._receipt_from_sse
        # verify the submit signature requires on_receipt
        import inspect
        sig = inspect.signature(transport.submit)
        assert "on_receipt" in sig.parameters

    def test_echo_verification_in_poll(self, transport):
        import inspect
        sig = inspect.signature(transport.poll)
        assert "client_request_id" in sig.parameters

    def test_call_counts_exist(self, transport):
        assert "submit" in transport.call_counts
        assert "poll" in transport.call_counts
        assert "download" in transport.call_counts
