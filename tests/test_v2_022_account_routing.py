"""V2-022 P0: mocked account routing; NEVER contacts a provider."""
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))


def _setup(monkeypatch, balances, overrides=None):
    import run_v2_022_production as runner

    def probe(alias):
        session, credit = balances.get(alias, ("SESSION_INVALID", None))
        return {"session_state": session, "known_credit_state": credit}

    monkeypatch.setattr(runner, "_probe", probe)
    monkeypatch.setattr(runner, "_stale_overrides", lambda: overrides or {})
    monkeypatch.setattr(runner, "emit", lambda *_: None)
    return runner


def test_positive_credit_beats_zero_credit_without_plan(monkeypatch, tmp_path):
    runner = _setup(monkeypatch, {
        "ACCOUNT_A": ("SESSION_VALID", 3),
        "ACCOUNT_F": ("SESSION_VALID", 2),
        "ACCOUNT_E": ("SESSION_VALID", 0),
        "ACCOUNT_B": ("SESSION_VALID", 0),
    })
    assert runner._pick_account(tmp_path, {"shots": {}}, "S18") == "ACCOUNT_A"


def test_planned_zero_credit_cannot_override_positive_fallback(monkeypatch, tmp_path):
    runner = _setup(monkeypatch, {
        "ACCOUNT_E": ("SESSION_VALID", 0),
        "ACCOUNT_F": ("SESSION_VALID", 2),
    })
    state = {"shots": {}, "account_plan": {"S08": "ACCOUNT_E"}}
    assert runner._pick_account(tmp_path, state, "S08") == "ACCOUNT_F"


def test_planned_positive_credit_is_preferred_within_safe_tier(monkeypatch, tmp_path):
    runner = _setup(monkeypatch, {
        "ACCOUNT_E": ("SESSION_VALID", 1),
        "ACCOUNT_F": ("SESSION_VALID", 3),
    })
    state = {"shots": {}, "account_plan": {"S08": "ACCOUNT_E"}}
    assert runner._pick_account(tmp_path, state, "S08") == "ACCOUNT_E"


def test_hard_blocked_plan_cannot_dispatch(monkeypatch, tmp_path):
    runner = _setup(monkeypatch, {
        "ACCOUNT_D": ("SESSION_VALID", 3),
        "ACCOUNT_F": ("SESSION_VALID", 2),
    }, {"ACCOUNT_D": {"hard_blocked_today": True}})
    state = {"shots": {}, "account_plan": {"S09": "ACCOUNT_D"}}
    assert runner._pick_account(tmp_path, state, "S09") == "ACCOUNT_F"


def test_evidenced_credit_override_cannot_dispatch_zero(monkeypatch, tmp_path):
    runner = _setup(monkeypatch, {
        "ACCOUNT_E": ("SESSION_VALID", 3),
        "ACCOUNT_F": ("SESSION_VALID", 1),
    }, {"ACCOUNT_E": {"effective_credit": 0}})
    assert runner._pick_account(tmp_path, {"shots": {}}, "S18") == "ACCOUNT_F"


def test_all_exhausted_returns_none_and_does_not_post(monkeypatch, tmp_path):
    runner = _setup(monkeypatch, {
        "ACCOUNT_E": ("SESSION_VALID", 0),
        "ACCOUNT_F": ("SESSION_VALID", 0),
    })
    assert runner._pick_account(tmp_path, {"shots": {}}, "S18") is None


def test_account_reusable_after_quota_refresh_even_with_prior_accept(monkeypatch, tmp_path):
    runner = _setup(monkeypatch, {
        "ACCOUNT_A": ("SESSION_VALID", 2),
        "ACCOUNT_E": ("SESSION_VALID", 0),
    })
    state = {"shots": {
        "S03": {"status": "QC_ACCEPT", "account": "ACCOUNT_A"},
        "S07": {"status": "QC_ACCEPT", "account": "ACCOUNT_A"},
    }}
    assert runner._pick_account(tmp_path, state, "S18") == "ACCOUNT_A"


def test_unknown_credit_only_after_observed_positive(monkeypatch, tmp_path):
    runner = _setup(monkeypatch, {
        "ACCOUNT_E": ("SESSION_VALID", None),
        "ACCOUNT_A": ("SESSION_VALID", 1),
    })
    assert runner._pick_account(tmp_path, {"shots": {}}, "S18") == "ACCOUNT_A"
    runner = _setup(monkeypatch, {
        "ACCOUNT_E": ("SESSION_VALID", None),
        "ACCOUNT_A": ("SESSION_VALID", 0),
    })
    assert runner._pick_account(tmp_path, {"shots": {}}, "S18") == "ACCOUNT_E"
