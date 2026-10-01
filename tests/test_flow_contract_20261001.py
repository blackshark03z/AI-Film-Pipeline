"""Deterministic verification of the 2026-10-01 Flow R2V contract delta.

Validates the 10 fail-closed properties required before live canary authorization:
1. historical contract remains unchanged;
2. current Veo3.1 builder reproduces the captured structural request;
3. inline reference entity is exact;
4. model is veo_3_1_r2v_fast_landscape;
5. current catalog parser accepts captured current records;
6. old catalog envelope and current envelope are version-separated;
7. exact current output matcher accepts one valid candidate;
8. collisions/multiple candidates fail closed;
9. null/ErrorInfo never establish acceptance;
10. canonical Film PromptPlan remains unchanged.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from film_pipeline.compiler import compile_prompt
from film_pipeline.core import load_shot, sha256
from film_pipeline.providers import flow_rpc_contract as contract
from film_pipeline.providers.flow_r2v_prompt import (
    MODEL as HISTORICAL_MODEL,
    FlowR2VPrompt,
    compile_flow_r2v_prompt,
    film_marker,
)

FIXTURES_DIR = Path(__file__).resolve().parents[1] / "fixtures"
SHOT_A_PATH = FIXTURES_DIR / "character_continuity_shot_a.json"

TEST_PROJECT_ID = "f6b40e79-d6f8-4354-80ae-c863260e96f5"
TEST_REF_ID = "53b5a413-7bb5-4f97-9be4-2461794a7d80"
TEST_REF_FILENAME = "story-auto-reference.png"
TEST_CAPTCHA = "test_captcha_enterprise_token_val_1234567890"
TEST_REQUEST_ID = "4095c9a0-9759-4d3a-b892-9a0352cb2da7"
TEST_JOB_ID = "job_0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef"


# Sample catalog payload with scene boards in payload[4] (observed live on Flow UI)
def make_catalog_wire(records, project_id=TEST_PROJECT_ID, scenes=None):
    aux_records = [
        [
            "item_aux_id_" + r[0][:8],
            None,
            None,
            ["title", [1790745437, 74868000], None, None, r[0], None, [1790745444, 633911000]],
            project_id,
        ]
        for r in records
    ]
    voices = [
        [
            f"voice_{i}",
            3,
            f"Voice {i}",
            [
                f"voice_{i}",
                None,
                None,
                None,
                None,
                None,
                None,
                None,
                None,
                None,
                [[f"Voice {i}", "Desc", True, f"https://example.com/v{i}.wav"]],
            ],
        ]
        for i in range(30)
    ]
    quotas = [
        None,
        None,
        [[None, 3, 2, None, "narwhal_display"], [None, 2, 1, None, "abra"]],
        None,
        1,
    ]
    payload = [
        None,
        aux_records,
        records,
        voices,
        scenes,  # None in old contract, list of scenes in current contract
        None,
        None,
        quotas,
    ]
    frame = [["wrb.fr", contract.RPC_CATALOG, json.dumps(payload), None, None, None, "generic"]]
    return ")]}'\n" + json.dumps(frame)


def make_veo31_video_record(
    output_id,
    project_id,
    reference_id,
    reference_filename,
    prompt_with_marker,
    model=contract.MODEL_VEO_3_1_FAST_LANDSCAPE,
    status="CAE",
):
    display_prompt = f"{reference_filename} {prompt_with_marker}"
    ast_slot = [
        None,
        None,
        [
            [
                [None, [[reference_id, reference_filename]]],
                [f" {prompt_with_marker}"],
            ]
        ],
    ]
    lineage_5_6 = [
        None,
        [[model, 3, [5], None, 2, 1], [[None, 4, reference_id]]],
        [ast_slot],
        None,
        1,
    ]
    xml_prompt = (
        f"<root><context><image id=\"image_0\" /></context>"
        f"<instruction><prompt>{prompt_with_marker}</prompt></instruction></root>"
    )
    lineage_7 = [
        [None, 335559, None, None, None, None, None, xml_prompt, "http://thumb", None, None, None, model, "", None, False, 2],
        [None, None, [8]],
        [output_id],
    ]
    return [
        output_id,
        project_id,
        "dummy_client_row_id",
        status,
        None,
        [
            [1790802068, 359783000],
            display_prompt,
            None,
            None,
            None,
            "http://thumb",
            lineage_5_6,
            None,
            [3],
            1,
            "http://thumb2",
            None,
            None,
            9984868,
        ],
        None,
        lineage_7,
    ]


def test_01_historical_contract_remains_unchanged():
    """Historical contract version, fingerprint, builder and matcher remain intact."""
    assert contract.CONTRACT_VERSION == "flow-batchexecute/2026-09-20.1"
    assert contract.CONTRACT_VERSION_HISTORICAL == "flow-batchexecute/2026-09-20.1"
    assert contract.QUALIFIED_BASELINE_FINGERPRINT == (
        "78ca7a1c3048b2c86802981696ca7e196752a661a027d3f11b8b5edece84e049"
    )

    # Historical build_video still produces abra_r2v_8s with flat [[[prompt]]]
    envelope = contract.build_video(
        TEST_PROJECT_ID,
        "historical prompt",
        TEST_REF_ID,
        TEST_CAPTCHA,
        TEST_REQUEST_ID,
    )
    outer = json.loads(envelope)
    assert outer[0][0][0] == contract.RPC_VIDEO
    payload = json.loads(outer[0][0][1])
    request = payload[0][0]
    assert request[0] == [None, None, [[["historical prompt"]]]]
    assert request[1] == [[None, TEST_REF_ID]]
    assert request[2] == "abra_r2v_8s"
    assert request[3] == 2


def test_02_current_veo31_builder_reproduces_captured_structural_request():
    """Current builder produces the exact captured MZZa6b request envelope and slots."""
    prompt = "A calm cinematic view at sunrise"
    envelope = contract.build_video_v2026_10_01(
        TEST_PROJECT_ID,
        prompt,
        TEST_REF_ID,
        TEST_REF_FILENAME,
        TEST_CAPTCHA,
        TEST_REQUEST_ID,
        model=contract.MODEL_VEO_3_1_FAST_LANDSCAPE,
    )
    outer = json.loads(envelope)
    assert len(outer) == 1 and len(outer[0]) == 1
    call = outer[0][0]
    assert call[0] == contract.RPC_VIDEO
    assert call[3] == "generic"

    payload = json.loads(call[1])
    assert len(payload) == 3
    # Top-level context
    ctx = payload[1]
    assert ctx[1] == contract.SURFACE_ID
    assert ctx[5] == TEST_PROJECT_ID
    assert ctx[10] == [TEST_CAPTCHA, 1]

    # Top-level request correlation
    assert payload[2][1] == 2

    # Request array
    assert len(payload[0]) == 1
    req = payload[0][0]
    assert len(req) == 6
    assert req[1] == [[None, TEST_REF_ID]]
    assert req[2] == "veo_3_1_r2v_fast_landscape"
    assert req[3] == 2  # 16:9 ratio
    assert req[4] is None
    assert len(req[5]) == 6


def test_03_inline_reference_entity_is_exact():
    """Prompt AST contains exact inline reference entity [[UUID, filename]] and text."""
    prompt = "Action in daytime living room"
    envelope = contract.build_video_v2026_10_01(
        TEST_PROJECT_ID,
        prompt,
        TEST_REF_ID,
        TEST_REF_FILENAME,
        TEST_CAPTCHA,
        TEST_REQUEST_ID,
    )
    outer = json.loads(envelope)
    payload = json.loads(outer[0][0][1])
    prompt_ast = payload[0][0][0]

    assert prompt_ast[0] is None
    assert prompt_ast[1] is None
    assert len(prompt_ast[2]) == 1
    branch = prompt_ast[2][0]
    assert len(branch) == 2

    ref_entity = branch[0]
    assert ref_entity[0] is None
    assert ref_entity[1] == [[TEST_REF_ID, TEST_REF_FILENAME]]

    prompt_node = branch[1]
    assert prompt_node == [f" {prompt}"]


def test_04_model_is_veo_3_1_r2v_fast_landscape():
    """Default model is veo_3_1_r2v_fast_landscape; unapproved models fail closed."""
    envelope = contract.build_video_v2026_10_01(
        TEST_PROJECT_ID,
        "prompt",
        TEST_REF_ID,
        TEST_REF_FILENAME,
        TEST_CAPTCHA,
        TEST_REQUEST_ID,
    )
    payload = json.loads(json.loads(envelope)[0][0][1])
    assert payload[0][0][2] == "veo_3_1_r2v_fast_landscape"

    # Historical abra_r2v_8s is rejected by current builder
    with pytest.raises(contract.ContractError) as exc_info:
        contract.build_video_v2026_10_01(
            TEST_PROJECT_ID,
            "prompt",
            TEST_REF_ID,
            TEST_REF_FILENAME,
            TEST_CAPTCHA,
            TEST_REQUEST_ID,
            model="abra_r2v_8s",
        )
    assert exc_info.value.code == "MODEL_INVALID"


def test_05_current_catalog_parser_accepts_captured_current_records():
    """catalog_records_v2026_10_01 accepts payload with multi-scene board lists."""
    marker = film_marker(TEST_JOB_ID)
    prompt = f"Calm action {marker}"
    output_id = "8d88d601-8c8d-493b-aabf-26a18d6030c5"
    record = make_veo31_video_record(
        output_id, TEST_PROJECT_ID, TEST_REF_ID, TEST_REF_FILENAME, prompt
    )
    scenes = [
        [
            "5c436758-2544-4086-b0d4-f04c89f4cd3f",
            "Untitled Scene",
            None,
            [1790796359, 934136000],
            [1790796360, 52119000],
            2,
            None,
            [],
        ]
    ]
    wire_text = make_catalog_wire([record], scenes=scenes)
    parsed = contract.catalog_records_v2026_10_01(wire_text, TEST_PROJECT_ID)
    assert len(parsed) == 1
    assert parsed[0][0] == output_id
    assert parsed[0][3] == "CAE"


def test_06_old_catalog_envelope_and_current_envelope_are_version_separated():
    """Historical catalog parser rejects new scene-bearing envelope; current parser accepts."""
    assert contract.CONTRACT_VERSION_HISTORICAL != contract.CONTRACT_VERSION_2026_10_01
    output_id = "8d88d601-8c8d-493b-aabf-26a18d6030c5"
    record = make_veo31_video_record(
        output_id, TEST_PROJECT_ID, TEST_REF_ID, TEST_REF_FILENAME, "prompt"
    )
    scenes = [["scene_uuid_1", "Scene Title", None, [1, 2], [3, 4], 2, None, []]]
    new_wire_text = make_catalog_wire([record], scenes=scenes)

    # Historical parser fails on CATALOG_ENVELOPE_DRIFT due to payload[4] not being None
    with pytest.raises(contract.ContractError) as exc:
        contract.catalog_records(new_wire_text, TEST_PROJECT_ID)
    assert exc.value.code == "CATALOG_ENVELOPE_DRIFT"

    # Current parser accepts
    accepted = contract.catalog_records_v2026_10_01(new_wire_text, TEST_PROJECT_ID)
    assert len(accepted) == 1

    # Old empty/None scenes envelope is accepted by both
    old_wire_text = make_catalog_wire([record], scenes=None)
    assert len(contract.catalog_records(old_wire_text, TEST_PROJECT_ID)) == 1
    assert len(contract.catalog_records_v2026_10_01(old_wire_text, TEST_PROJECT_ID)) == 1


def test_07_exact_current_output_matcher_accepts_one_valid_candidate():
    """match_r2v_output_v2026_10_01 verifies full lineage and marker ownership."""
    marker = film_marker(TEST_JOB_ID)
    prompt = f"8-second locked MCU {marker}"
    output_id = "8d88d601-8c8d-493b-aabf-26a18d6030c5"
    record = make_veo31_video_record(
        output_id,
        TEST_PROJECT_ID,
        TEST_REF_ID,
        TEST_REF_FILENAME,
        prompt,
        model=contract.MODEL_VEO_3_1_FAST_LANDSCAPE,
    )

    baseline_ids = [
        "11111111-1111-1111-1111-111111111111",
        "22222222-2222-2222-2222-222222222222",
    ]
    matched = contract.match_r2v_output_v2026_10_01(
        [record],
        TEST_PROJECT_ID,
        TEST_REF_ID,
        TEST_REF_FILENAME,
        TEST_JOB_ID,
        baseline_ids=baseline_ids,
        model=contract.MODEL_VEO_3_1_FAST_LANDSCAPE,
    )
    assert matched is not None
    assert matched[0] == output_id
    assert matched[3] == "CAE"


def test_08_collisions_multiple_candidates_fail_closed():
    """Any collision or lineage conflict fails closed with specific ContractError."""
    marker = film_marker(TEST_JOB_ID)
    prompt = f"Prompt with marker {marker}"
    output_1 = "8d88d601-8c8d-493b-aabf-26a18d6030c5"
    output_2 = "9e99e702-9d9e-4bac-a1b2-3c4d5e6f7a8b"

    rec1 = make_veo31_video_record(
        output_1, TEST_PROJECT_ID, TEST_REF_ID, TEST_REF_FILENAME, prompt
    )
    rec2 = make_veo31_video_record(
        output_2, TEST_PROJECT_ID, TEST_REF_ID, TEST_REF_FILENAME, prompt
    )

    # 1. Multiple rows with same marker -> OUTPUT_MARKER_COLLISION
    with pytest.raises(contract.ContractError) as exc:
        contract.match_r2v_output_v2026_10_01(
            [rec1, rec2],
            TEST_PROJECT_ID,
            TEST_REF_ID,
            TEST_REF_FILENAME,
            TEST_JOB_ID,
            baseline_ids=[],
        )
    assert exc.value.code == "OUTPUT_MARKER_COLLISION"

    # 2. Pre-existing output ID in baseline -> OUTPUT_PREEXISTING_IDENTITY
    with pytest.raises(contract.ContractError) as exc:
        contract.match_r2v_output_v2026_10_01(
            [rec1],
            TEST_PROJECT_ID,
            TEST_REF_ID,
            TEST_REF_FILENAME,
            TEST_JOB_ID,
            baseline_ids=[output_1],
        )
    assert exc.value.code == "OUTPUT_PREEXISTING_IDENTITY"

    # 3. Output ID identical to reference ID -> OUTPUT_REFERENCE_NOT_DISTINCT
    rec_same_id = make_veo31_video_record(
        TEST_REF_ID, TEST_PROJECT_ID, TEST_REF_ID, TEST_REF_FILENAME, prompt
    )
    with pytest.raises(contract.ContractError) as exc:
        contract.match_r2v_output_v2026_10_01(
            [rec_same_id],
            TEST_PROJECT_ID,
            TEST_REF_ID,
            TEST_REF_FILENAME,
            TEST_JOB_ID,
            baseline_ids=[],
        )
    assert exc.value.code == "OUTPUT_REFERENCE_NOT_DISTINCT"

    # 4. Model mismatch in lineage -> OUTPUT_MODEL_MISMATCH
    rec_wrong_model = make_veo31_video_record(
        output_1,
        TEST_PROJECT_ID,
        TEST_REF_ID,
        TEST_REF_FILENAME,
        prompt,
        model=contract.MODEL_VEO_3_1_LITE,
    )
    with pytest.raises(contract.ContractError) as exc:
        contract.match_r2v_output_v2026_10_01(
            [rec_wrong_model],
            TEST_PROJECT_ID,
            TEST_REF_ID,
            TEST_REF_FILENAME,
            TEST_JOB_ID,
            baseline_ids=[],
            model=contract.MODEL_VEO_3_1_FAST_LANDSCAPE,
        )
    assert exc.value.code == "OUTPUT_MODEL_MISMATCH"

    # 5. Status not CAE -> OUTPUT_STATUS_UNQUALIFIED
    rec_pending = make_veo31_video_record(
        output_1, TEST_PROJECT_ID, TEST_REF_ID, TEST_REF_FILENAME, prompt, status="PENDING"
    )
    with pytest.raises(contract.ContractError) as exc:
        contract.match_r2v_output_v2026_10_01(
            [rec_pending],
            TEST_PROJECT_ID,
            TEST_REF_ID,
            TEST_REF_FILENAME,
            TEST_JOB_ID,
            baseline_ids=[],
        )
    assert exc.value.code == "OUTPUT_STATUS_UNQUALIFIED"


def test_09_null_and_errorinfo_never_establish_acceptance():
    """Null response and ErrorInfo frames are never inferred as success or acceptance."""
    # Null payload response (observed when abra_r2v_8s is submitted)
    null_frame = ')]}\'\n[["wrb.fr", "MZZa6b", null, null, null, null, "generic"]]'
    parsed = contract.parse_rpc(null_frame, contract.RPC_VIDEO)
    assert parsed is None

    diag = contract.submission_diagnostics(null_frame)
    assert diag["parsed"] is True
    assert diag["advisory_only"] is True
    assert diag["type_counts"]["null"] == 1
    assert diag["type_counts"]["str"] == 0

    # ErrorInfo frame (observed on anti-automation detection)
    error_frame = (
        ')]}\'\n[["wrb.fr", "MZZa6b", null, null, null, '
        '[7, null, [["type.googleapis.com/google.rpc.ErrorInfo", ["PUBLIC_ERROR_UNUSUAL_ACTIVITY"]]]]]]'
    )
    diag_err = contract.submission_diagnostics(error_frame)
    assert diag_err["advisory_only"] is True
    # parse_rpc on error_frame returns None (since payload is null) or non-success
    parsed_err = contract.parse_rpc(error_frame, contract.RPC_VIDEO)
    assert parsed_err is None


def test_10_canonical_film_prompt_plan_remains_unchanged():
    """Canonical Film PromptPlan and ShotSpec are never modified during compilation."""
    from film_pipeline.core import canonical_json
    from film_pipeline.slice0011 import (
        REFERENCE_ASSET_ID,
        REFERENCE_SHA256,
        reference_capabilities,
    )

    shot = load_shot(SHOT_A_PATH)
    shot_before = canonical_json(shot)
    caps = reference_capabilities()
    plan = compile_prompt(
        shot, caps, reference_hashes={REFERENCE_ASSET_ID: REFERENCE_SHA256}
    )

    hash_before = sha256(plan)
    plan_json_before = canonical_json(plan)

    # Provider adaptation for current Veo 3.1
    compiled = compile_flow_r2v_prompt(
        plan, TEST_JOB_ID, model=contract.MODEL_VEO_3_1_FAST_LANDSCAPE
    )

    hash_after = sha256(plan)
    plan_json_after = canonical_json(plan)
    shot_after = canonical_json(shot)

    assert hash_before == hash_after
    assert plan_json_before == plan_json_after
    assert shot_before == shot_after
    assert hash_before == "cbc6cabae3fe2132c6ba6c3b49d78e9994ff3b670549f1980eff82e0cc9da324"
    assert compiled.model == contract.MODEL_VEO_3_1_FAST_LANDSCAPE
    assert compiled.canonical_plan_hash == hash_before
