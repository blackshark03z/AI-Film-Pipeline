"""V2-019 Phase K — hardening utility tests."""
from __future__ import annotations

import json
from pathlib import Path

from film_pipeline.providers.dola_production import (
    clear_stale_profile_locks,
    extract_poll_messages,
    safe_close,
    stale_profile_locks,
)


class _ExplodingClose:
    def close(self):
        raise RuntimeError("patchright target closed")


class _QuietClose:
    def __init__(self):
        self.closed = False

    def close(self):
        self.closed = True


def test_safe_close_swallows_manager_exceptions():
    notes: list[str] = []
    assert safe_close(_ExplodingClose(), notes=notes) is False
    assert notes == ["close_error:RuntimeError"]
    quiet = _QuietClose()
    assert safe_close(quiet) is True
    assert quiet.closed is True


def test_stale_profile_lock_requires_no_matching_process(tmp_path):
    profile = tmp_path / "ACCOUNT_T"
    profile.mkdir()
    (profile / "SingletonLock").write_text("stale", encoding="utf-8")
    # a chrome process still references this profile -> NOT stale
    lines = [f'chrome.exe --user-data-dir="{profile}"']
    assert stale_profile_locks(profile, commandlines=lines) == []
    assert clear_stale_profile_locks(profile, commandlines=lines) == []
    assert (profile / "SingletonLock").exists()
    # no process references it -> stale, cleared
    cleared = clear_stale_profile_locks(profile, commandlines=[])
    assert cleared == ["SingletonLock"]
    assert not (profile / "SingletonLock").exists()


def test_stale_profile_lock_missing_dir_is_empty(tmp_path):
    assert stale_profile_locks(tmp_path / "nope", commandlines=[]) == []


def test_extract_poll_messages_both_limit_shapes():
    inner = {"messages": [{"message_id": "m1"}, {"message_id": "m2"}]}
    limit10 = {"downlink_body": {"pull_singe_chain_downlink_body": inner}}
    assert [m["message_id"] for m in extract_poll_messages(limit10)] == \
        ["m1", "m2"]
    # content-as-JSON-string shape (SSE-embedded)
    wrapped = {"data": json.dumps(limit10)}
    assert len(extract_poll_messages(wrapped)) == 2
    # shape drift degrades to empty, never wrong
    assert extract_poll_messages({"unexpected": 1}) == []
    # dedupe
    dup = {"a": json.dumps(limit10), "b": json.dumps(limit10)}
    assert len(extract_poll_messages(dup)) == 2


def test_extract_poll_messages_recent_conv_shape():
    payload = {"downlink_body": {"pull_recent_conv_chain_downlink_body": {
        "cells": [{"conversation": {"conversation_id": "123"}}, "junk"]}}}
    # recent_conv has no `messages` key -> zero messages, no crash
    assert extract_poll_messages(payload) == []
