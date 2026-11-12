"""The disk rule depends on the operation: long renders keep 10 GiB (Owner, 2026-11-12), a single send needs the 4 GiB reserve + a download."""
from types import SimpleNamespace

import pytest

from film_pipeline.production import preflight as P


def _free(monkeypatch, gib):
    monkeypatch.setattr(P.shutil, "disk_usage", lambda p: SimpleNamespace(free=int(gib * 2**30)))
    monkeypatch.setattr(P.subprocess, "run", lambda *a, **k: SimpleNamespace(returncode=0, stdout="tool version"))


def _space_issues(result):
    return [i for i in result["issues"] if "free" in i]


def test_send_is_allowed_at_13_gib(tmp_path, monkeypatch):
    _free(monkeypatch, 13.0)
    result = P.check(tmp_path, operation="send")
    assert _space_issues(result) == []
    assert result["required_free_gib"] == pytest.approx(P.SEND_RESERVE_GIB + P.SEND_TAKE_BOUND_GIB)


def test_render_is_refused_below_10_gib(tmp_path, monkeypatch):
    _free(monkeypatch, 8.0)
    for kwargs in ({}, {"operation": "render"}):
        result = P.check(tmp_path, **kwargs)
        issues = _space_issues(result)
        assert len(issues) == 2 and all("render" in i and "10GiB" in i for i in issues)
        assert result["required_free_gib"] == 10.0


def test_render_is_allowed_at_13_gib(tmp_path, monkeypatch):
    _free(monkeypatch, 13.0)
    assert _space_issues(P.check(tmp_path, operation="render")) == []


def test_send_is_refused_below_the_reserve_and_names_operation_and_gib(tmp_path, monkeypatch):
    _free(monkeypatch, 3.0)
    issues = _space_issues(P.check(tmp_path, operation="send"))
    assert len(issues) == 2
    need = f"{P.SEND_RESERVE_GIB + P.SEND_TAKE_BOUND_GIB:g}GiB"
    assert all("send" in i and need in i for i in issues)


def test_send_bound_grows_with_expected_bytes(tmp_path, monkeypatch):
    _free(monkeypatch, 5.0)
    assert _space_issues(P.check(tmp_path, operation="send")) == []
    assert len(_space_issues(P.check(tmp_path, operation="send", expected_bytes=2 * 2**30))) == 2


def test_unknown_operation_is_rejected(tmp_path):
    with pytest.raises(ValueError):
        P.check(tmp_path, operation="whatever")
