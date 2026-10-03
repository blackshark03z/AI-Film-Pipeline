"""Package-009 guardrail: ONE mutation authority domain.

The V12 adversarial finding — a tool instantiating the SAME scope_id
against a sub-directory state file — silently started fresh authority and
could have evaded a canary latch. These tests pin the single-domain
invariant on the 009 tools and on MutationAuthority itself.
"""
import re
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))

from film_pipeline.providers.flow_reference_upload import OwnerAmbiguityGate
from mutation_authority import MutationAuthority

ROOT = Path(__file__).resolve().parents[1]
TOOLS = ROOT / "tools"
PACKAGE_SCOPE = "FLOW-UPLOAD-CONTRACT-REQUAL-009"


@pytest.mark.parametrize("tool", [
    "run_requal_009.py", "run_continuation_009.py", "run_reproof_009.py"])
def test_all_009_tools_bind_the_shared_root_authority(tool):
    source = (TOOLS / tool).read_text(encoding="utf-8")
    calls = re.findall(r"MutationAuthority\(\s*([A-Z_0-9]+)\s*,", source)
    assert calls, f"{tool}: no authority instantiation found"
    for binding in calls:
        assert binding in ("RUN_DIR", "AUTHORITY_DIR"), \
            f"{tool}: authority bound to non-package-root dir {binding}"
    scope_ids = set(re.findall(r'"(FLOW-UPLOAD-CONTRACT-REQUAL-009)"',
                               source))
    assert scope_ids == {PACKAGE_SCOPE}, f"{tool}: unexpected scope ids"


def test_same_scope_id_from_two_dirs_is_a_single_logical_scope_only_when_paths_match(tmp_path):
    """The state file is path-scoped: two directories with the same
    scope_id are TWO state files. Tools must never rely on scope_id alone
    across different paths (the V12 finding)."""
    first = MutationAuthority(tmp_path / "a", "S")
    second = MutationAuthority(tmp_path / "b", "S")
    second.latch("TEST_GATE", "latched in the other directory")
    assert first.authority == "OPEN"
    # Therefore: every package tool must pass the SAME directory. Enforced
    # by the source-level guardrail above.


def test_latched_shared_state_refuses_every_later_entry(tmp_path):
    authority = MutationAuthority(tmp_path, "SCOPE")
    authority.latch("UPLOAD_RESPONSE_AMBIGUOUS", "canary ambiguity")
    for kind in ("qualification_upload_canaryB", "conditioned_generate",
                 "reproof_generate"):
        with pytest.raises(OwnerAmbiguityGate, match="MUTATION_LATCHED_CLOSED"):
            authority.check_mutation_allowed(kind)
    with pytest.raises(OwnerAmbiguityGate, match="latched"):
        authority.enter_upload_pending("refup_x", "0" * 64)
