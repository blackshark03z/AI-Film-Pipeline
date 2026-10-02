"""R1 — adversarial proofs for the durable mutation-authority latch.

Frozen invariant: an OWNER_AMBIGUITY_GATE permanently latches mutation
authority for the execution scope; read-only reconciliation may resolve
external-effect knowledge but can never re-open the latch; the latch is
durable across restarts; unused budgets cannot be consumed after latching;
a NEW Owner-authorized scope starts fresh. No provider access in this module.
"""
import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))

from film_pipeline.providers.flow_reference_upload import OwnerAmbiguityGate
from mutation_authority import (
    AUTHORITY_LATCHED_CLOSED,
    AUTHORITY_OPEN,
    KNOWLEDGE_RESOLVED_EFFECT_IDENTIFIED,
    KNOWLEDGE_RESOLVED_NO_EFFECT,
    KNOWLEDGE_UNKNOWN,
    MutationAuthority,
)


def test_upload_ambiguity_latches_closed(tmp_path):
    authority = MutationAuthority(tmp_path, "SCOPE_UPLOAD")
    authority.latch("UPLOAD_AMBIGUITY", "maseQ 200 response unparseable")
    assert authority.authority == AUTHORITY_LATCHED_CLOSED
    with pytest.raises(OwnerAmbiguityGate, match="MUTATION_LATCHED_CLOSED"):
        authority.check_mutation_allowed("continuity_upload")


def test_generate_ambiguity_latches_closed(tmp_path):
    authority = MutationAuthority(tmp_path, "SCOPE_GENERATE")
    authority.latch("GENERATE_AMBIGUITY", "released; external effect unresolved")
    with pytest.raises(OwnerAmbiguityGate, match="MUTATION_LATCHED_CLOSED"):
        authority.check_mutation_allowed("primary_generate")


def test_readonly_resolution_no_effect_keeps_latch(tmp_path):
    authority = MutationAuthority(tmp_path, "SCOPE_R1")
    authority.latch("GENERATE_AMBIGUITY", "released; effect unknown")
    authority.record_knowledge(KNOWLEDGE_RESOLVED_NO_EFFECT,
                               "catalog delta empty across bounded probes")
    assert authority.knowledge == KNOWLEDGE_RESOLVED_NO_EFFECT
    assert authority.authority == AUTHORITY_LATCHED_CLOSED
    with pytest.raises(OwnerAmbiguityGate):
        authority.check_mutation_allowed("primary_generate")


def test_readonly_resolution_identified_effect_keeps_latch(tmp_path):
    authority = MutationAuthority(tmp_path, "SCOPE_R2")
    authority.latch("UPLOAD_AMBIGUITY", "maseQ response unparseable")
    authority.record_knowledge(KNOWLEDGE_RESOLVED_EFFECT_IDENTIFIED,
                               "unique stable strong catalog match")
    assert authority.knowledge == KNOWLEDGE_RESOLVED_EFFECT_IDENTIFIED
    assert authority.authority == AUTHORITY_LATCHED_CLOSED
    with pytest.raises(OwnerAmbiguityGate):
        authority.check_mutation_allowed("continuity_upload")


def test_latch_survives_restart(tmp_path):
    MutationAuthority(tmp_path, "SCOPE_RESTART").latch("GENERATE_AMBIGUITY", "x")
    restarted = MutationAuthority(tmp_path, "SCOPE_RESTART")
    assert restarted.authority == AUTHORITY_LATCHED_CLOSED
    with pytest.raises(OwnerAmbiguityGate):
        restarted.check_mutation_allowed("primary_generate")


def test_unused_generate_budget_cannot_be_consumed_after_latch(tmp_path):
    authority = MutationAuthority(tmp_path, "SCOPE_B1")
    authority.latch("GENERATE_AMBIGUITY", "x")
    with pytest.raises(OwnerAmbiguityGate):
        authority.check_mutation_allowed("primary_generate")


def test_unused_upload_budget_cannot_be_consumed_after_latch(tmp_path):
    authority = MutationAuthority(tmp_path, "SCOPE_B2")
    authority.latch("UPLOAD_AMBIGUITY", "x")
    with pytest.raises(OwnerAmbiguityGate):
        authority.check_mutation_allowed("continuity_upload")


def test_successor_and_repair_paths_cannot_bypass_latch(tmp_path):
    """Successor and repair are mutation paths: the same choke point gates
    them; there is no bypass flag."""
    authority = MutationAuthority(tmp_path, "SCOPE_B3")
    authority.latch("GENERATE_AMBIGUITY", "x")
    for budget_kind in ("primary_generate", "repair_generate",
                        "successor_generate", "continuity_upload"):
        with pytest.raises(OwnerAmbiguityGate):
            authority.check_mutation_allowed(budget_kind)


def test_scene_resume_cannot_bypass_latch(tmp_path):
    """execute_scene through a latched scope: every shot entry is refused at
    the mutation choke point (the runner consults the authority before any
    reserve/release/upload)."""
    from scene_runner import execute_scene

    authority = MutationAuthority(tmp_path, "SCOPE_SCENE")
    authority.latch("UPLOAD_AMBIGUITY", "x")
    refused = []

    def run_shot(shot, state_dir, state):
        try:
            authority.check_mutation_allowed("primary_generate")
        except OwnerAmbiguityGate as exc:
            refused.append(shot["shot_id"])
            return {"shot_id": shot["shot_id"], "gate": f"MUTATION_LATCHED_CLOSED"}
        return {"shot_id": shot["shot_id"], "gate": "SHOT_PROVEN"}

    plan = {"scene_id": "S", "shots": [
        {"shot_id": f"S{i}", "fixture": "f",
         "continuity": {"kind": "reference", "media_id": "m"}} for i in range(1, 4)]}
    result = execute_scene(plan, tmp_path / "scene", run_shot)
    assert refused == ["S1", "S2", "S3"]
    assert result["scene_complete"] is False


def test_new_owner_authorized_scope_starts_fresh(tmp_path):
    latched = MutationAuthority(tmp_path / "old", "OLD_SCOPE")
    latched.latch("GENERATE_AMBIGUITY", "x")
    fresh = MutationAuthority(tmp_path / "new", "NEW_SCOPE")
    assert fresh.authority == AUTHORITY_OPEN
    fresh.check_mutation_allowed("primary_generate")  # allowed
    fresh.latch("GENERATE_AMBIGUITY", "fresh scope may also latch")
    assert fresh.authority == AUTHORITY_LATCHED_CLOSED
    assert latched.authority == AUTHORITY_LATCHED_CLOSED  # old scope untouched


def test_latch_is_one_way(tmp_path):
    authority = MutationAuthority(tmp_path, "SCOPE_ONEWAY")
    authority.latch("GENERATE_AMBIGUITY", "x")
    with pytest.raises(OwnerAmbiguityGate):
        authority.check_mutation_allowed("primary_generate")
    # No API mutates authority back to OPEN: the state file itself is terminal.
    state = json.loads((tmp_path / "mutation_authority.json").read_text(encoding="utf-8"))
    assert state["mutation_authority"] == AUTHORITY_LATCHED_CLOSED
    assert authority.authority == AUTHORITY_LATCHED_CLOSED


def test_readonly_operations_usable_after_latch(tmp_path):
    authority = MutationAuthority(tmp_path, "SCOPE_RO")
    authority.latch("UPLOAD_AMBIGUITY", "x")
    # Knowledge recording (read-only reconciliation outcome) remains usable.
    authority.record_knowledge(KNOWLEDGE_RESOLVED_EFFECT_IDENTIFIED, "probes")
    assert authority.knowledge == KNOWLEDGE_RESOLVED_EFFECT_IDENTIFIED
    # The gate is specific: only MUTATION paths are refused.
    with pytest.raises(OwnerAmbiguityGate, match="MUTATION_LATCHED_CLOSED"):
        authority.check_mutation_allowed("continuity_upload")
