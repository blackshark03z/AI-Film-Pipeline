"""Structural continuity checks stay separate from observed visual acceptance."""

import asyncio
import subprocess
from pathlib import Path

import pytest

from film_pipeline.compiler import compile_prompt
from film_pipeline.autoedit_export import export_film_package
from film_pipeline.core import CharacterRef, ProviderCapabilities, load_shot
from film_pipeline.editorial_runner import real_rough_cut
from film_pipeline.execution import DryRunProvider, route
from film_pipeline.live_runtime import LiveRuntimeExecutor
from film_pipeline.qc import QCStore, evidence, human_decision
from film_pipeline.sequence import validate_shot_sequence
from film_pipeline.slice0010 import (require_approved_second_take,
                                     require_paired_continuity_evidence,
                                     verify_predecessor)
from film_pipeline.store import SQLiteStore


FIXTURES = Path(__file__).resolve().parents[1] / "fixtures"


def pair():
    return (load_shot(FIXTURES / "flow_canary.json"),
            load_shot(FIXTURES / "flow_canary_shot2.json"))


def changed(shot, **changes):
    return shot.model_copy(update=changes, deep=True)


def test_real_planned_pair_has_exact_predecessor_and_scene():
    validate_shot_sequence(pair())


@pytest.mark.parametrize("bad_previous", [None, "OTHER_SHOT", "FLOW_CANARY_002"])
def test_wrong_missing_and_self_predecessor_rejected(bad_previous):
    first, second = pair()
    second.continuity.previous_shot_id = bad_previous
    with pytest.raises(ValueError):
        validate_shot_sequence((first, second))


def test_duplicate_and_circular_ids_rejected():
    first, second = pair()
    second.shot_id = first.shot_id
    second.continuity.previous_shot_id = first.shot_id
    with pytest.raises(ValueError):
        validate_shot_sequence((first, second))
    first, second = pair()
    first.continuity.previous_shot_id = second.shot_id
    with pytest.raises(ValueError, match="missing predecessor provenance"):
        validate_shot_sequence((first, second))


def test_cross_scene_and_explicit_environment_conflicts_rejected():
    first, second = pair()
    second.scene_id = "OTHER_SCENE"
    with pytest.raises(ValueError, match="cross-scene"):
        validate_shot_sequence((first, second))
    first, second = pair()
    second.environment.weather = "clear"
    with pytest.raises(ValueError, match="weather"):
        validate_shot_sequence((first, second))


def test_overlapping_structured_state_must_match():
    first, second = pair()
    first.continuity.end_state["RAIN_STATUS"] = {"present": True}
    second.continuity.start_state["RAIN_STATUS"] = {"present": False}
    with pytest.raises(ValueError, match="RAIN_STATUS"):
        validate_shot_sequence((first, second))
    second.continuity.start_state["RAIN_STATUS"] = {"present": True}
    validate_shot_sequence((first, second))


def test_shared_character_identity_and_look_state_are_structural():
    first, second = pair()
    shared = CharacterRef(character_id="LINH", identity_version="ID_V1",
                          look_state_id="LOOK_01")
    first.characters = [shared]
    second.characters = [shared.model_copy(deep=True)]
    validate_shot_sequence((first, second))
    second.characters[0].look_state_id = "LOOK_02"
    with pytest.raises(ValueError, match="look_state_id"):
        validate_shot_sequence((first, second))
    second.characters[0].look_state_id = "LOOK_01"
    second.characters[0].identity_version = "ID_V2"
    with pytest.raises(ValueError, match="identity_version"):
        validate_shot_sequence((first, second))


def test_invalid_spec_version_is_rejected():
    first, second = pair()
    second.spec_version = 0
    with pytest.raises(ValueError):
        validate_shot_sequence((first, second))


def test_missing_persisted_predecessor_is_rejected(tmp_path):
    runtime = tmp_path / "empty.sqlite"
    SQLiteStore(runtime).initialize()
    with pytest.raises(KeyError):
        verify_predecessor(runtime)


def test_owner_finalization_requires_exact_predecessor_pair_evidence():
    from test_qc_kernel import sample_asset

    prior = sample_asset()
    candidate = prior.model_copy(update={"asset_id": "asset_second",
                                         "source_attempt_id": "attempt_second"})
    source = {"path": prior.uri_or_path, "sha256": prior.sha256}
    paired = evidence(asset=candidate, evaluator_type="ffmpeg", evaluator_version="fixture",
        gate="continuity", criterion="paired_scene_continuity",
        observation="paired comparison pending", verdict="uncertain",
        source_artifacts=[source, {"path": "first.jpg", "sha256": "1" * 64},
                          {"path": "second.jpg", "sha256": "2" * 64},
                          {"path": "pair.jpg", "sha256": "3" * 64}])
    with pytest.raises(ValueError, match="paired Shot 1"):
        require_paired_continuity_evidence([], prior)
    wrong = paired.model_copy(update={"source_artifacts": [
        {"path": "wrong.mp4", "sha256": "0" * 64}, *paired.source_artifacts[1:]]})
    with pytest.raises(ValueError, match="paired Shot 1"):
        require_paired_continuity_evidence([wrong], prior)
    require_paired_continuity_evidence([paired], prior)


def test_dispatch_budget_allows_next_shot_but_never_second_attempt_for_same_shot(tmp_path):
    from test_live_runtime import FakeTransport, make_executor

    executor, store, _, first_job = make_executor(tmp_path, FakeTransport())
    assert store.reserve_dispatch(first_job.provider_job_id).dispatch_count == 1
    profile = ProviderCapabilities(profile_version="fixture", provider_id="flow_veo",
                                   transport_type="browser_cookie")
    shot = pair()[1]
    plan = compile_prompt(shot, profile)
    decision = route(shot, [plan], [profile], {profile.provider_id: True})
    dry = DryRunProvider()
    request = dry.build_request(plan, decision)
    attempt = dry.create_attempt(shot, plan, decision, request,
                                 started_at="2026-09-30T00:00:00+00:00")
    second_job = LiveRuntimeExecutor(store, FakeTransport()).freeze_path(
        shot, plan, decision, attempt, project_binding_id="second-project",
        pre_dispatch_snapshot={"asset_ids": []})
    assert store.reserve_dispatch(second_job.provider_job_id).dispatch_count == 1
    another = dry.create_attempt(shot, plan, decision, request,
                                 started_at="2026-09-30T00:00:01+00:00")
    duplicate_job = executor.freeze_path(shot, plan, decision, another,
        project_binding_id="third-project", pre_dispatch_snapshot={"asset_ids": []})
    with pytest.raises(RuntimeError, match="single dispatch budget"):
        store.reserve_dispatch(duplicate_job.provider_job_id)
    assert store.read_provider_job(duplicate_job.provider_job_id).dispatch_count == 0


def test_two_approved_shots_render_and_export_two_portable_media(tmp_path):
    from test_live_runtime import FakeTransport, make_executor
    from test_qc_kernel import evidence_set

    class RedTransport(FakeTransport):
        async def fetch(self, job, output_id, destination):
            result = subprocess.run(["ffmpeg", "-hide_banner", "-loglevel", "error",
                "-y", "-f", "lavfi", "-i", "color=c=red:s=16x16:d=0.1",
                "-an", str(destination)], capture_output=True, text=True, check=False)
            assert result.returncode == 0, result.stderr
            return destination

    first_executor, runtime, _, first_job = make_executor(tmp_path, FakeTransport(),
                                                          project_binding_id="project-one")
    asyncio.run(first_executor.submit_once(first_job.provider_job_id))
    asyncio.run(first_executor.reconcile(first_job.provider_job_id))
    first_asset = asyncio.run(first_executor.download_assets(
        first_job.provider_job_id, tmp_path / "first"))[0]
    _, first_take = QCStore(runtime).save(first_asset, evidence_set(first_asset),
        human_decision(asset=first_asset, reviewer_id="test_owner", action="APPROVE",
                       visual_pass=True, continuity_pass=True, editorial_pass=True))

    profile = ProviderCapabilities(profile_version="fixture", provider_id="provider_full",
                                   transport_type="other")
    second_shot = pair()[1]
    plan = compile_prompt(second_shot, profile)
    decision = route(second_shot, [plan], [profile], {profile.provider_id: True})
    dry = DryRunProvider()
    request = dry.build_request(plan, decision)
    attempt = dry.create_attempt(second_shot, plan, decision, request,
                                 started_at="2026-09-30T00:00:00+00:00")
    second_executor = LiveRuntimeExecutor(runtime, RedTransport())
    second_job = second_executor.freeze_path(second_shot, plan, decision, attempt,
        project_binding_id="project-two", pre_dispatch_snapshot={"asset_ids": []})
    asyncio.run(second_executor.submit_once(second_job.provider_job_id))
    asyncio.run(second_executor.reconcile(second_job.provider_job_id))
    second_asset = asyncio.run(second_executor.download_assets(
        second_job.provider_job_id, tmp_path / "second"))[0]
    _, second_take = QCStore(runtime).save(second_asset, evidence_set(second_asset),
        human_decision(asset=second_asset, reviewer_id="test_owner", action="APPROVE",
                       visual_pass=True, continuity_pass=True, editorial_pass=True))

    first_shot, _, _, _, _, _ = runtime.read_runtime_lineage(
        first_asset.source_attempt_id, first_asset.provider_job_id)
    with pytest.raises(ValueError, match="Owner approval lineage missing"):
        require_approved_second_take(runtime, second_take.selected_take_id,
                                     first_shot, first_asset)

    ordered = [first_take.selected_take_id, second_take.selected_take_id]
    render = real_rough_cut(runtime.path, project_id="fixture_scene",
        selected_take_ids=ordered, output_dir=tmp_path / "rough")
    assert render["clip_count"] == 2 and render["selected_take_ids"] == ordered
    assert render["full_decode"] and abs(render["duration_s"] -
        (first_asset.duration_s + second_asset.duration_s)) < 0.1
    samples = []
    for at in (first_asset.duration_s / 2,
               first_asset.duration_s + second_asset.duration_s / 2):
        frame = subprocess.run(["ffmpeg", "-hide_banner", "-loglevel", "error",
            "-ss", str(at), "-i", render["output_path"], "-frames:v", "1",
            "-vf", "scale=1:1", "-f", "rawvideo", "-pix_fmt", "rgb24", "-"],
            capture_output=True, check=False)
        assert frame.returncode == 0 and len(frame.stdout) == 3
        samples.append(frame.stdout)
    assert max(samples[0]) < 20 and samples[1][0] > 100
    package = export_film_package(runtime.path, manifest_id=render["manifest_id"],
        media_root=tmp_path, destination=tmp_path / "package")
    assert package["media_count"] == 2 and package["package_id"]
    assert export_film_package(runtime.path, manifest_id=render["manifest_id"],
        media_root=tmp_path, destination=tmp_path / "package")["package_id"] == package["package_id"]
