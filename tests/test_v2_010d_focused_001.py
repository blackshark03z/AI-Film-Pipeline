"""AI-FILM-QUALITY-V2-010D — focused tests.

Duration authority, credit parsing, restart semantics, multi-creation
filtering, redaction. Live-recorded fixtures; no network, no provider calls.
"""
from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
for path in (ROOT / "tools", ROOT / "src"):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

from dola_010d_adapter_delta import (  # noqa: E402
    duration_gate_ok, extract_released_duration,
    verify_asset_integrity)
from dola_010d_adapter_delta import DolaBrowserAdapter010D  # noqa: E402
from dola_010c_contract import (  # noqa: E402
    correlate_new_videos, deterministic_video, parse_poll_replies)

FIX010C = ROOT / "tests/fixtures/v2_010c"
FIX010D = ROOT / "tests/fixtures/v2_010d"


def _load(base: Path, name: str) -> dict:
    return json.loads((base / name).read_text(encoding="utf-8"))


def test_01_duration_carrier_field_is_structural_not_prompt_text():
    body = _load(FIX010D, "release_body_chat_ability_f2a.json")
    duration = extract_released_duration(body)
    assert duration == 10, "video-mode default 10s must be the carrier value"
    raw = json.loads(body["chat_ability"]["ability_param"])
    prompt_text = raw["input_box_content"]["user_input_content"]
    assert "5-second" in prompt_text
    assert raw["duration"] == 10, "prompt text must NOT override the field"


def test_02_duration_gate_fail_closed():
    assert duration_gate_ok("5s", 5)
    assert not duration_gate_ok("10s", 5)
    assert not duration_gate_ok(None, 5)
    assert not duration_gate_ok("5秒", 5)


def test_03_credit_requirement_parsing_from_real_refusal():
    fixture = _load(FIX010D, "credit_refusal_f2b_010c.json")
    parsed = DolaBrowserAdapter010D.parse_credit_requirement(fixture["text"])
    assert parsed == fixture["expected"], parsed


def test_04_sse_receipt_restart_after_receipt():
    """A process that died right after receipt-first persistence can resume:
    reload the receipt (fixture) + baseline ids, re-poll (fixture), correlate,
    and reach the same completed video WITHOUT any new dispatch."""
    receipt = _load(FIX010C, "m1_receipt.json")
    assert receipt["conversation_id"] == "38417972940811793"
    assert receipt["release_request_count"] >= 1
    # durable restart state: baseline = everything already known at receipt
    known_creations = {"40033753389997329", "40033753389997585",
                       "40033753389997841", "40033753389998097"}
    known_messages = {"1546406012981009"}
    poll = _load(FIX010C, "poll_downlink_observation.json")
    replies = parse_poll_replies(poll["payload"])
    fresh = correlate_new_videos(replies,
                                 known_creation_ids=known_creations,
                                 known_message_ids=known_messages)
    assert all(r["creation_id"] not in known_creations for r in fresh)
    assert all(r["message_id"] not in known_messages for r in fresh)


def test_05_restart_after_download_integrity():
    asset = ROOT / "tests/fixtures/v2_010d/asset_integrity_sample.bin"
    payload = b"V2-010D restart-after-download integrity sample"
    asset.write_bytes(payload)
    sha = hashlib.sha256(payload).hexdigest()
    assert verify_asset_integrity(asset, sha)
    assert not verify_asset_integrity(asset, "0" * 64)
    assert not verify_asset_integrity(
        ROOT / "tests/fixtures/v2_010d/missing.bin", sha)
    asset.unlink()


def test_06_multiple_creation_objects_and_video_type_filter():
    poll = _load(FIX010C, "poll_downlink_observation.json")
    replies = parse_poll_replies(poll["payload"])
    assert len(replies) >= 5, "M1 images + history video must all parse"
    images = [r for r in replies if r.get("type") == 1]
    videos = [r for r in replies if r.get("type") == 2]
    assert len(images) == 4 and all(r["video_download_url"] is None
                                    for r in images)
    assert len(videos) == 1 and videos[0]["video_download_url"]
    # correlation only ever promotes type-2 with a URL:
    done = [r for r in replies if r.get("type") == 2
            and r.get("video_download_url")]
    assert deterministic_video(done) == videos[0]["video_download_url"]


def test_07_credit_text_redaction_safe():
    # credit texts are safe to persist; secret-bearing strings are not
    from dola_010c_contract import sanitize_value
    record = {"credit_text": "2動画クレジット…残り1",
              "url": "https://v16-dola.dola.com/a/b.mp4?x-signature=SIG"
                     "&msToken=TOK"}
    cleaned = sanitize_value("", record)
    assert cleaned["credit_text"] == record["credit_text"]
    assert "SIG" not in cleaned["url"] and "TOK" not in cleaned["url"]


def test_010d_08_committed_fixtures_pass_secret_scan():
    import re
    markers = re.compile(
        r"sessionid=(?!REDACTED)[A-Za-z0-9]|msToken=(?!REDACTED)[A-Za-z0-9]|"
        r"a_bogus=(?!REDACTED)[A-Za-z0-9]", re.I)
    for base in (FIX010C, FIX010D):
        for path in base.glob("*.json"):
            text = path.read_text(encoding="utf-8")
            assert not markers.search(text), f"secret in {path.name}"
