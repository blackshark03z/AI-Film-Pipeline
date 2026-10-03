"""Package-010 T13 — the operational ledger is observational only."""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LEDGER = (ROOT / "projects/flow_editorial_runtime_scale_010/"
          "operational_ledger_010.json")

VALID = {"PLANNED", "RUNNING", "BLOCKED", "COMPLETE", "OWNER_REVIEW",
         "EXTERNAL_GATE"}


def test_ledger_exists_and_is_marked_observational():
    data = json.loads(LEDGER.read_text(encoding="utf-8"))
    assert data["observational_only"] is True
    assert "grants NOTHING" in data["authority_note"]


def test_all_statuses_are_from_the_frozen_vocabulary():
    data = json.loads(LEDGER.read_text(encoding="utf-8"))
    for status in data["status_counts"]:
        assert status in VALID


def test_ledger_grants_no_authority():
    data = json.loads(LEDGER.read_text(encoding="utf-8"))
    blob = json.dumps(data)
    for forbidden in ("LATCHED", "SUSPENDED", "check_mutation_allowed",
                      "consume(", "budget_kind"):
        assert forbidden not in blob


def test_ledger_restart_rebuild_is_deterministic(tmp_path):
    # Rebuilding from the same durable inputs yields identical rows.
    import subprocess, sys
    first = LEDGER.read_text(encoding="utf-8")
    subprocess.run([sys.executable, str(ROOT / "tools/"
                     "build_operational_ledger_010.py")],
                   capture_output=True, check=True)
    assert LEDGER.read_text(encoding="utf-8") == first


def test_generator_tool_has_no_authority_calls():
    tool = (ROOT / "tools/build_operational_ledger_010.py").read_text(
        encoding="utf-8")
    for forbidden in ("MutationAuthority", "latch(", "consume(",
                      "check_mutation_allowed"):
        assert forbidden not in tool
