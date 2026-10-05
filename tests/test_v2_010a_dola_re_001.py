"""AI-FILM-QUALITY-V2-010A tests: route-history truth, RE contract,
3-way diff, D-G1 cause analysis, and package invariants."""
from __future__ import annotations
import json
from pathlib import Path
import pytest
ROOT = Path(__file__).resolve().parents[1]
PKG = ROOT / "projects/quality_v2_010a_dola_re_authority"
def pkg_json(n): return json.loads((PKG / n).read_text(encoding="utf-8"))

def test_01_route_history_truth():
    d = pkg_json("route_history_truth_v2_010a.json")
    assert d["route_history_truth"] == "DIFFERENT_TRANSPORTS"
    assert d["evidence"]["canary_4"]["transport"] == "browser_ui (Playwright automation)"
    assert d["evidence"]["canary_4"]["task_id"] == "38417972940811793"
    assert "NOT the cookie-HTTP" in d["evidence"]["canary_4"]["verdict"]
    for k in ("story_auto_cookie_1", "story_auto_cookie_2", "ai_film_d_g1"):
        assert d["evidence"][k]["verdict"] == "AMBIGUOUS"

def test_02_re_contract_exists_and_complete():
    c = pkg_json("dola_re_contract_v1.json")
    assert c["version"] == "dola-re-contract-v1"
    assert c["source_repo"].startswith("D:")
    assert c["source_revision"]
    assert c["transport_family"].startswith("cookie-HTTP")
    for section in ("auth", "submit", "response", "poll", "output", "recovery"):
        assert section in c, section
    assert c["submit"]["endpoint"].startswith("https://www.dola.com")
    assert "seedance_v2.0" in c["submit"]["model_field"]
    assert "ability_type" in c["submit"]["model_field"] or "ability" in c["submit"]["model_field"]
    assert c["response"]["ack_event"] == "SSE_ACK"
    assert c["response"]["conversation_field"] == "ack_client_meta.conversation_id"
    assert "UNKNOWN" in json.dumps(c["poll"]["failure_states"]) or "CreditError" in json.dumps(c["poll"]["failure_states"])

def test_03_transport_diff_classifications():
    d = pkg_json("dola_transport_diff_v2_010a.json")
    diffs = d["key_differences"]
    by_field = {x["field"]: x for x in diffs}
    assert by_field["chat_ability.ability_type"]["classification"] == "DRIFTED"
    assert by_field["chat_ability.ability_param"]["classification"] == "MISSING in B+C"
    assert by_field["governance layer"]["C"].startswith("FULL")
    for x in diffs:
        assert any(k in x["classification"] for k in ("IDENTICAL", "SEMANTICALLY_EQUIVALENT", "DRIFTED", "MISSING", "UNKNOWN"))

def test_04_dg1_cause_analysis():
    d = pkg_json("dg1_cause_analysis_v2_010a.json")
    assert d["historical_event"]["gate"] == "OWNER_AMBIGUITY_GATE"
    assert d["historical_event"]["job_id"].startswith("job_1bcfd770")
    assert d["historical_event"]["remaining_quarantined"] is True
    proven = {c["cause_class"] for c in d["proven_causes"]}
    assert "REQUEST_SCHEMA_DRIFT" in proven
    assert "MISSING_PROMPT_PREFIX" in proven
    assert "REQUEST_BODY_FIELD_GAP" in proven
    plausible = {c["cause_class"] for c in d["plausible_causes"]}
    assert "SSE_PARSER_DRIFT" in plausible
    assert "SESSION_CONTEXT_DRIFT" in plausible

def test_05_invariants():
    import subprocess
    dirty = [l for l in subprocess.run(
        ["git", "status", "--porcelain"], cwd=ROOT, capture_output=True,
        text=True).stdout.splitlines() if not l.startswith("??")]
    # cust file is expected dirty; everything else clean
    assert all("010a" in l or "custody" in l or d is None for l in dirty)
    assert not (PKG / "generate_ledger.json").exists()
    assert not list(PKG.glob("**/*.mp4"))
