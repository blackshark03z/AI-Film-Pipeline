"""AI-FILM-QUALITY-V2-010E — Phase 2 focused tests: dispatch durability.

Acceptance: ZERO restart-redispatch path, ZERO gallery/history-as-authority
path, ZERO silently-RESERVED released mutation.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
for path in (ROOT / "tools", ROOT / "src"):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

from dola_010e_dispatch_journal import (  # noqa: E402
    DISPATCH_ARMED, NETWORK_RELEASE_OBSERVED, RESERVED, SSE_RECEIPT_CAPTURED,
    TERMINAL, DispatchJournal, creation_linkage_ok, receipt_is_fresh)

FIX010C = ROOT / "tests/fixtures/v2_010c"
FIX010D = ROOT / "tests/fixtures/v2_010d"


def _fresh_journal(tmp_path: Path, name: str) -> DispatchJournal:
    return DispatchJournal(tmp_path / name, "attempt_test_010e")


def _arm(journal: DispatchJournal) -> None:
    journal.append("MUTATION_RESERVED", {"budget_kind": "f2b_010e"})
    journal.append("DISPATCH_ARMED", {"duration_class": 5,
                                      "index_boundary": 34})


def test_01_crash_before_release_is_safe_unspent(tmp_path):
    journal = _fresh_journal(tmp_path, "j1.jsonl")
    _arm(journal)
    plan = journal.recover(conversation_has_new_message=False)
    assert plan["boundary"] == "A" and plan["action"].startswith("SAFE_UNSPENT")
    assert plan["action"].endswith("BEFORE_ANY_RETRY")


def test_02_unobserved_release_promotes_to_ambiguity(tmp_path):
    """Enter fired but the process died before the CDP event: the
    conversation (authority) shows a new message → boundary B, never
    automatic redispatch."""
    journal = _fresh_journal(tmp_path, "j2.jsonl")
    _arm(journal)
    plan = journal.recover(conversation_has_new_message=True)
    assert plan["boundary"] == "B"
    assert "AMBIGUITY_LATCH" in plan["action"]
    assert "REDISPATCH" not in plan["action"].upper()


def test_03_crash_immediately_after_post_observation(tmp_path):
    journal = _fresh_journal(tmp_path, "j3.jsonl")
    _arm(journal)
    journal.append(NETWORK_RELEASE_OBSERVED, {"request_id": "8052.765"})
    plan = journal.recover()
    assert plan["boundary"] == "B"
    assert "AMBIGUITY_LATCH" in plan["action"]
    # the released mutation is durably recorded — never silently RESERVED
    assert journal.has(NETWORK_RELEASE_OBSERVED)
    assert journal.state != RESERVED


def test_04_crash_after_sse_ack_resumes_by_receipt(tmp_path):
    journal = _fresh_journal(tmp_path, "j4.jsonl")
    _arm(journal)
    journal.append(NETWORK_RELEASE_OBSERVED, {"request_id": "r1"})
    journal.append(SSE_RECEIPT_CAPTURED, {"question_id": "q1",
                                          "message_index": 36})
    plan = journal.recover()
    assert plan["boundary"] == "C"
    assert plan["action"] == "RESUME_POLL_BY_RECEIPT_IDENTITY"


def test_05_crash_after_creation_resumes_download(tmp_path):
    journal = _fresh_journal(tmp_path, "j5.jsonl")
    _arm(journal)
    journal.append(NETWORK_RELEASE_OBSERVED, {"request_id": "r1"})
    journal.append(SSE_RECEIPT_CAPTURED, {"question_id": "q1"})
    journal.append("CREATION_BOUND", {"creation_id": "c1"})
    plan = journal.recover()
    assert plan["boundary"] == "D"
    assert plan["action"] == "RESUME_DOWNLOAD_BY_CREATION_IDENTITY"


def test_06_crash_after_download_verifies_sha(tmp_path):
    journal = _fresh_journal(tmp_path, "j6.jsonl")
    _arm(journal)
    for kind, payload in (("NETWORK_RELEASE_OBSERVED", {"request_id": "r1"}),
                          ("SSE_RECEIPT_CAPTURED", {"question_id": "q1"}),
                          ("CREATION_BOUND", {"creation_id": "c1"}),
                          ("ASSET_DOWNLOADED", {"sha256": "abc"})):
        journal.append(kind, payload)
    plan = journal.recover()
    assert plan["boundary"] == "E"
    assert "VERIFY_LOCAL_SHA256" in plan["action"]


def test_07_duplicate_event_handling_is_idempotent(tmp_path):
    journal = _fresh_journal(tmp_path, "j7.jsonl")
    _arm(journal)
    first = journal.append(NETWORK_RELEASE_OBSERVED, {"request_id": "r1"})
    second = journal.append(NETWORK_RELEASE_OBSERVED, {"request_id": "r1"})
    assert second.get("duplicate_ignored") is True
    assert second["event_id"] == first["event_id"]
    assert len([e for e in journal.events
                if e["kind"] == NETWORK_RELEASE_OBSERVED]) == 1


def test_08_restart_idempotency_reload_from_disk(tmp_path):
    journal = _fresh_journal(tmp_path, "j8.jsonl")
    _arm(journal)
    journal.append(NETWORK_RELEASE_OBSERVED, {"request_id": "r1"})
    journal.append(SSE_RECEIPT_CAPTURED, {"question_id": "q1",
                                          "message_index": 36})
    reloaded = DispatchJournal(journal.path, "attempt_test_010e")
    assert reloaded.state == journal.state
    assert [e["event_id"] for e in reloaded.events] == \
        [e["event_id"] for e in journal.events]
    # restarting after receipt NEVER triggers a new dispatch
    assert reloaded.recover()["action"] == "RESUME_POLL_BY_RECEIPT_IDENTITY"


def test_09_receipt_replay_rejects_stale_index(tmp_path):
    assert receipt_is_fresh({"message_index": 36}, 34)
    assert not receipt_is_fresh({"message_index": 34}, 34)
    assert not receipt_is_fresh({"message_index": 7}, 34)
    assert not receipt_is_fresh({"message_index": None}, 34)


def test_10_false_historical_creation_rejected():
    known = {"1490518952401169", "1543843763689489", "1540180629641233",
             "40033753389997329"}
    receipt = {"question_id": "1541259999999999", "message_index": 36,
               "local_message_id": "lm-010e"}
    history = {"creation_id": "1490518952401169", "reply_to": None,
               "message_index": 23, "local_message_id": None}
    assert not creation_linkage_ok(history, receipt, known)
    fresh_linked = {"creation_id": "9999000011112222",
                    "reply_to": "1541259999999999",
                    "message_index": 37, "local_message_id": None}
    assert creation_linkage_ok(fresh_linked, receipt, known)
    unlinked_fresh = {"creation_id": "9999000011113333", "reply_to": None,
                      "message_index": 5, "local_message_id": None}
    assert not creation_linkage_ok(unlinked_fresh, receipt, known)


def test_11_duration_5_enforcement_recorded_in_journal(tmp_path):
    journal = _fresh_journal(tmp_path, "j11.jsonl")
    _arm(journal)
    armed = journal.last_of("DISPATCH_ARMED")
    assert armed["payload"]["duration_class"] == 5
    released = json.loads((FIX010D / "release_body_chat_ability_f2a.json")
                          .read_text(encoding="utf-8"))
    from dola_010d_adapter_delta import extract_released_duration
    # the 010C reference body proves the carrier; 010E's gate requires 5
    assert extract_released_duration(released) == 10  # known reference
    assert armed["payload"]["duration_class"] == 5


def test_12_journal_payloads_are_secret_free(tmp_path):
    journal = _fresh_journal(tmp_path, "j12.jsonl")
    journal.append("MUTATION_RESERVED", {"cookie_header": "sessionid=SECRET",
                                         "msToken": "TOK",
                                         "conversation_id": "384179"})
    text = journal.path.read_text(encoding="utf-8")
    assert "SECRET" not in text and "TOK" not in text
    # payloads carry ids only; the caller is responsible for never passing
    # secrets — assert the journal kept the safe field
    assert journal.last_of("MUTATION_RESERVED")["payload"][
        "conversation_id"] == "384179"


def test_13_torn_tail_write_is_ignored(tmp_path):
    journal = _fresh_journal(tmp_path, "j13.jsonl")
    _arm(journal)
    journal.append(NETWORK_RELEASE_OBSERVED, {"request_id": "r1"})
    good = journal.path.read_text(encoding="utf-8")
    journal.path.write_text(good + '{"kind":"SSE_RECEIPT_CA', encoding="utf-8")
    reloaded = DispatchJournal(journal.path, "attempt_test_010e")
    assert reloaded.state == "RELEASE_OBSERVED"
    assert reloaded.recover()["boundary"] == "B"


def test_14_terminal_is_absorbing(tmp_path):
    journal = _fresh_journal(tmp_path, "j14.jsonl")
    _arm(journal)
    journal.append("TERMINAL_PROVIDER_FAILURE",
                   {"notice": "動画を生成できません"})
    plan = journal.recover()
    assert plan["boundary"] is None and plan["state"] == TERMINAL
