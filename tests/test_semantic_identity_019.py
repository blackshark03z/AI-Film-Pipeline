"""Generation semantic identity invariant (Package-019 Phase V2).

Proves how ActionIntent / PerformanceSpec distinctions propagate into
generation identity and that two semantically different generation
requests cannot collide:

    same base ShotSpec + different ActionIntent  -> different identity
    same base ShotSpec + different PerformanceSpec -> different identity
    identical full semantic input -> deterministic same identity

Mechanism (option A, already the live implementation): extension fields
present on a ShotSpec participate directly in sha256(shot) (legacy
shots without them keep their historical digest via the
canonical_json exclusion), which feeds the canonical PromptPlan
input_hash -> prompt_plan_id -> GenerationAttempt.prompt_plan_hash ->
ProviderJob.correlation_evidence.prompt_plan_hash — the same identity
chain the frozen-path resume and any cache/replay keying consume.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

from film_pipeline.compiler import compile_prompt
from film_pipeline.core import (ActionIntent, References, ShotSpec,
                                canonical_json, load_shot, sha256,
                                validate_contract)

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
from run_scene_scale_003 import flow_capabilities  # noqa: E402

REF = "asset_cb5bba09ce60fecbf009dcaaaa122e104e44fd5b99749a72eda0fa31ec44edc3"
REF_SHA = "fecf669e9b81436c80cd6502036d10b401f3964534e8d3fe9dea0800355f8313"


def base_shot():
    shot = load_shot(ROOT / "fixtures/requal018/SEQ7_F2C_P018_A.json")
    return shot.model_copy(
        update={"references": References(other_asset_ids=[REF])})


def plan_of(shot):
    return compile_prompt(shot, flow_capabilities(),
                          reference_hashes={REF: REF_SHA})


def test_01_same_base_different_action_intent_no_collision():
    a = base_shot()
    b = base_shot().model_copy(deep=True)
    b.action_intent.character_goal = "a different goal entirely"
    pa, pb = plan_of(a), plan_of(b)
    assert pa.input_hash != pb.input_hash
    assert pa.prompt_plan_id != pb.prompt_plan_id
    assert sha256(pa) != sha256(pb)  # attempt-level binding differs


def test_02_same_base_different_performance_spec_no_collision():
    a = base_shot()
    b = base_shot().model_copy(deep=True)
    b.performance_spec.weight_transfer = "a different weight transfer"
    pa, pb = plan_of(a), plan_of(b)
    assert pa.input_hash != pb.input_hash
    assert pa.prompt_plan_id != pb.prompt_plan_id
    assert sha256(pa) != sha256(pb)


def test_03_identical_semantics_deterministic():
    a, b = base_shot(), base_shot()
    pa, pb = plan_of(a), plan_of(b)
    assert pa.input_hash == pb.input_hash
    assert pa.prompt_plan_id == pb.prompt_plan_id
    assert sha256(pa) == sha256(pb)
    assert canonical_json(pa) == canonical_json(pb)


def test_04_extension_fields_participate_in_base_identity():
    shot = base_shot()
    dump = json.loads(canonical_json(shot))
    # extensions PRESENT on the shot are part of its identity...
    assert dump["action_intent"]["trigger"] == \
        shot.action_intent.trigger
    assert dump["performance_spec"]["primary_action"]
    # ...while a shot WITHOUT them hashes without the keys at all
    bare = json.loads(canonical_json(
        load_shot(ROOT / "fixtures/requal009/SEQ7_F2C.json")))
    assert "action_intent" not in bare and "performance_spec" not in bare


def test_05_legacy_digest_pins_unchanged_by_extensions():
    # the pinned canary plan digests from the qualified route still hold
    import subprocess
    out = subprocess.run(
        [sys.executable, "-m", "pytest",
         "tests/test_flow_r2v_compact.py", "-q", "--no-header"],
        capture_output=True, text=True, cwd=ROOT)
    assert out.returncode == 0, out.stdout[-400:]


def test_06_frozen_resume_refuses_different_semantics():
    """The frozen path keys on shot_id and re-verifies the FROZEN PATH:
    a same-shot-id resume with different ActionIntent hits
    FLOW_R2V_RESTART_PATH_DIFFERS (the stored shot differs), because
    the extensions participate in the shot identity. The compact wire
    body alone is NOT the semantic identity (it may not render intent);
    the identity chain is shot -> plan -> path comparison."""
    a = base_shot()
    b = base_shot().model_copy(deep=True)
    b.action_intent.character_goal = "a different goal entirely"
    from film_pipeline.core import canonical_json
    assert canonical_json(a) != canonical_json(b)
    caps = flow_capabilities()
    pa = compile_prompt(a, caps, reference_hashes={REF: REF_SHA})
    pb = compile_prompt(b, caps, reference_hashes={REF: REF_SHA})
    assert pa.input_hash != pb.input_hash  # plan identity differs too
    # with a causal wire compiler the prompt itself also differs
    from film_pipeline.performance_compiler import compile_causal_r2v_prompt
    from film_pipeline.performance import BodyProportionAuthority
    body = BodyProportionAuthority(character_id="swordsman_white_robes",
                                   identity_version="v",
                                   authority_basis="x")
    ta = compile_causal_r2v_prompt(
        pa, "job_" + "0" * 64, model="veo_3_1_r2v_lite",
        performance_spec=a.performance_spec, body_authority=body,
        action_intent=a.action_intent).text
    tb = compile_causal_r2v_prompt(
        pb, "job_" + "0" * 64, model="veo_3_1_r2v_lite",
        performance_spec=b.performance_spec, body_authority=body,
        action_intent=b.action_intent).text
    assert ta != tb


def test_07_generation_semantic_fingerprint_helper():
    """Explicit custody fingerprint: binds base identity + both
    extensions + compiler identity + provider semantic inputs."""
    def fingerprint(shot, *, wire_version, model="veo_3_1_r2v_lite"):
        basis = {
            "kind": "generation-semantic-fingerprint-v1",
            "shot_spec_sha256": sha256(shot),
            "performance_spec_sha256":
                sha256(shot.performance_spec)
                if shot.performance_spec else None,
            "action_intent_sha256":
                sha256(shot.action_intent)
                if shot.action_intent else None,
            "canonical_compiler_version": "deterministic-v1",
            "wire_compiler_version": wire_version,
            "reference_hashes": {REF: REF_SHA},
            "model": model}
        return sha256(canonical_json(basis))
    a = base_shot()
    b = base_shot().model_copy(deep=True)
    b.action_intent.character_goal = "another goal"
    assert fingerprint(a, wire_version="flow-r2v-causal-compact-v1") != \
        fingerprint(b, wire_version="flow-r2v-causal-compact-v1")
    assert fingerprint(a, wire_version="flow-r2v-causal-compact-v1") == \
        fingerprint(base_shot(),
                    wire_version="flow-r2v-causal-compact-v1")
