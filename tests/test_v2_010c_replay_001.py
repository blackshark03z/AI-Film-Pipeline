"""AI-FILM-QUALITY-V2-010C — replay/contract tests (L9).

Golden fixtures recorded from live 010C sessions replay through the Python
contract oracle (tools/dola_010c_contract.py). Fail-closed secret scan over
all committed fixtures.
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TOOLS = ROOT / "tools"
for path in (TOOLS, ROOT / "src"):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

from dola_010c_contract import (  # noqa: E402
    correlate_new_videos, deterministic_video, parse_poll_replies,
    parse_sse_ack, receipt_first_ordering, redact_signed_url, sanitize_value)

FIXTURES = ROOT / "tests/fixtures/v2_010c"
SECRET_MARKERS = re.compile(
    r"sessionid=(?!REDACTED)[A-Za-z0-9]|msToken=(?!REDACTED)[A-Za-z0-9]|"
    r"a_bogus=(?!REDACTED)[A-Za-z0-9]", re.I)


def _load(name: str) -> dict:
    return json.loads((FIXTURES / name).read_text(encoding="utf-8"))


def test_01_sse_ack_receipt_is_current_and_parseable():
    fixture = _load("sse_ack_stream_m1.json")
    stream = fixture["stream_text"]
    assert "SSE_ACK" in stream
    receipt = parse_sse_ack(stream)
    assert receipt is not None
    assert receipt["conversation_id"] == "38417972940811793"
    assert receipt["question_id"] == "1541253913616145"
    assert receipt["message_index"] == 7
    assert receipt["local_message_id"]


def test_02_poll_downlink_parses_creations_with_history_immunity():
    fixture = _load("poll_downlink_observation.json")
    payload = fixture["payload"]
    assert payload and payload.get("downlink_body")
    replies = parse_poll_replies(payload)
    assert replies, "expected creation records from the live observation"
    m1_ids = {"40033753389997329", "40033753389997585",
              "40033753389997841", "40033753389998097"}
    m1_records = [r for r in replies if r.get("creation_id") in m1_ids]
    assert len(m1_records) == 4, "M1's four image creations must be present"
    assert all(r.get("type") == 1 for r in m1_records)
    fresh = correlate_new_videos(
        replies, known_creation_ids=m1_ids,
        known_message_ids={"1546406012981009"})
    assert all(r.get("creation_id") not in m1_ids for r in fresh)


def test_03_baseline_diff_correlation_is_history_immune():
    history = [
        {"message_id": "100", "creation_id": "900", "type": 2,
         "video_download_url": "https://old.example/v.mp4"},
        {"message_id": "200", "creation_id": "901", "type": 1,
         "video_download_url": None},
    ]
    new_record = {"message_id": "300", "creation_id": "902", "type": 2,
                  "video_download_url": "https://new.example/v.mp4"}
    records = correlate_new_videos(
        history + [new_record], known_creation_ids={"900", "901"},
        known_message_ids={"100", "200"})
    assert records == [new_record]
    assert deterministic_video(records) == "https://new.example/v.mp4"


def test_04_determinism_fail_closed_on_multiple_urls():
    records = [
        {"message_id": "1", "creation_id": "a", "type": 2,
         "video_download_url": "https://a/x.mp4"},
        {"message_id": "2", "creation_id": "b", "type": 2,
         "video_download_url": "https://b/y.mp4"},
    ]
    assert deterministic_video(records) is None


def test_05_receipt_first_ordering():
    assert receipt_first_ordering(True, True, True)
    assert not receipt_first_ordering(True, False, True)
    assert not receipt_first_ordering(False, True, True)


def test_06_secret_redaction_of_attestation_params():
    url = ("https://www.dola.com/chat/completion?a=1&msToken=SECRETVALUE"
           "&a_bogus=SIGVALUE&fp=FPVALUE")
    redacted = redact_signed_url(url)
    assert "SECRETVALUE" not in redacted and "SIGVALUE" not in redacted
    assert "FPVALUE" not in redacted
    assert "msToken=REDACTED" in redacted


def test_07_sanitizer_redacts_secret_keys_but_keeps_structure():
    payload = {"headers": {"Cookie": "sessionid=abc"},
               "creation": {"id": "123", "video": {"download_url":
                             "https://v/x.mp4?x-signature=SIG"}}}
    cleaned = sanitize_value("", payload)
    assert cleaned["headers"]["Cookie"] == "REDACTED"
    assert cleaned["creation"]["id"] == "123"
    assert "SIG" not in cleaned["creation"]["video"]["download_url"]


def test_08_committed_fixtures_pass_secret_scan():
    for path in FIXTURES.glob("*.json"):
        text = path.read_text(encoding="utf-8")
        assert not SECRET_MARKERS.search(text), f"secret in {path.name}"


def test_09_release_request_fixture_carries_current_query_contract():
    fixture = _load("release_request_m2.json")
    params = fixture.get("query_params") or {}
    for required in ("a_bogus", "device_id", "web_id", "tea_uuid",
                     "region", "sys_region", "msToken"):
        assert required in params, f"missing {required} in release query"
    assert params.get("region") == "VN" and params.get("sys_region") == "VN"
    body = fixture.get("body_structure") or {}
    assert "client_meta" in body and "messages" in body
    client_meta = body["client_meta"]
    assert client_meta.get("conversation_id") == "38417972940811793"
    assert client_meta.get("last_message_index") is not None
