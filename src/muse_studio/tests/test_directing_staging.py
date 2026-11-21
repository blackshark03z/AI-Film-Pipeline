import json
import subprocess
from pathlib import Path

import pytest

from muse_studio.core.film_qc_engine import FilmQCEngine
from muse_studio.core.autoprod_orchestrator import _load_render_checkpoint, _render_fingerprint
from muse_studio.core.prompt_repair_agent import PromptRepairAgent
from muse_studio.core.screenplay_compiler import ScreenplayCompiler
from muse_studio.core.script_ingestor import ScriptIngestor
from muse_studio.core.staging import require_current_staging


def _bible():
    return {
        "characters": [
            {"id": "A", "name": "Asha", "look_verbatim": "Asha wears a loose orange jacket.", "anchor_image": "a.png"},
            {"id": "I", "name": "Ines", "look_verbatim": "Ines wears a green cardigan.", "anchor_image": "i.png"},
        ],
        "locations": [
            {"id": "OFFICE", "look_verbatim": "A small room with a walnut desk."},
            {"id": "HALL", "look_verbatim": "A long empty corridor."},
        ],
        "props_ledger": [{"id": "KEY", "name": "brass key", "state_tracking": {"CH01": "On the desk"}}],
    }


def _beats(*lines):
    return [
        {
            "beat_id": f"B{i}", "shot_id": f"S{i}", "chapter_id": "CH01", "location": "OFFICE",
            "dialogue": line, "speaker": "Asha" if i % 2 else "Ines",
            "characters_present": ["A", "I"],
        }
        for i, line in enumerate(lines, 1)
    ]


@pytest.mark.parametrize("line", [
    "The brass key stays on the desk.",
    "I will take the brass key tomorrow.",
    "Do not touch the brass key.",
    "The brass key was never here.",
    "I am ready to go.",
])
def test_dialogue_and_ledger_context_do_not_authorize_an_action(line):
    bible = _bible()
    beats = _beats("We should wait.", "Do you want me to stay?", line, "All right.", "See you then.")
    staged = ScreenplayCompiler.compile_shots(bible, beats, cinematic_cutaways=True)
    assert [shot["dialogue"] for shot in staged["shots"]] == [beat["dialogue"] for beat in beats]
    assert not staged["staging_review"]
    assert all(not shot.get("cutaway_type") for shot in staged["shots"])

    beats[2]["staging"] = {
        "kind": "source_action", "purpose": "Demonstrate possession", "prop_id": "KEY",
        "source_field": "dialogue", "source_excerpt": line, "character_id": "A",
    }
    checked = ScreenplayCompiler.compile_shots(bible, beats, cinematic_cutaways=True)
    assert len(checked["shots"]) == len(beats)
    assert checked["staging_review"][0]["outcome"] == "invalid"


def test_staging_respects_same_scene_states_and_skips_repeated_coverage():
    bible = _bible()
    beats = _beats(*["The brass key stays on the desk."] * 12)
    for index in (0, 1, 2, 3):
        beats[index]["staging"] = {
            "kind": "state_insert", "purpose": "Show the position before the decision.",
            "source_field": "dialogue", "source_excerpt": beats[index]["dialogue"], "prop_id": "KEY",
        }
    bible["props_ledger"][0]["state_tracking"].update(B1="On the desk", B2="On the desk", B3="On the desk")
    beats[2]["scene_id"] = "ARRIVAL"
    beats[3]["location"] = "HALL"
    manifest = ScreenplayCompiler.compile_shots(bible, beats, cinematic_cutaways=True)
    states = [shot for shot in manifest["shots"] if shot.get("staging")]
    assert [shot["staging"]["source_beat_id"] for shot in states] == ["B1", "B3"]
    assert [row["outcome"] for row in manifest["staging_review"]] == [
        "planned", "omitted", "planned", "invalid",
    ]


def test_source_visible_state_can_make_an_insert_redundant():
    bible = _bible()
    beats = _beats("Opening.", "The brass key stays on the desk.", "All right.", "I know.", "See you.")
    beats[0].update(dialogue=None, action_summary="The brass key is lying flat on the desk.", speaker=None)
    beats[1]["staging"] = {
        "kind": "state_insert", "purpose": "Show where the key remains.", "prop_id": "KEY",
        "source_field": "dialogue", "source_excerpt": beats[1]["dialogue"],
    }
    bible["props_ledger"][0]["state_tracking"].update(B1="lying flat on the desk", B2="lying flat on the desk")
    manifest = ScreenplayCompiler.compile_shots(bible, beats, cinematic_cutaways=True)
    assert len(manifest["shots"]) == len(beats)
    assert manifest["staging_review"][0]["outcome"] == "omitted"


def test_legacy_insert_is_removed_on_recompile_and_never_cached_as_new_state(tmp_path):
    bible = _bible()
    bible["props_ledger"][0]["state_tracking"]["B3"] = "On the desk"
    beats = _beats("Wait here.", "You have time.", "The brass key stays on the desk.", "All right.", "See you.")
    beats[2]["staging"] = {
        "kind": "state_insert", "purpose": "Show the agreed location of the key.",
        "prop_id": "KEY", "source_field": "dialogue", "source_excerpt": beats[2]["dialogue"],
    }
    legacy = {
        "shot_id": "S3__prop_insert", "beat_id": "B3__prop_insert", "prop_source_beat_id": "B3",
        "cutaway_type": "prop_insert", "action_summary":
            "A hand moves into frame and gently rests on the brass key, keeping it in place.",
    }
    with pytest.raises(ValueError, match="Recompile"):
        require_current_staging({"shots": [legacy]})
    beats.insert(3, legacy)
    (tmp_path / "story_bible.json").write_text(json.dumps(bible), encoding="utf-8")
    (tmp_path / "beats.json").write_text(json.dumps(beats), encoding="utf-8")
    (tmp_path / "a_beats.json").write_text(json.dumps(_beats("Unrelated archived input.")), encoding="utf-8")
    _, _, default = ScreenplayCompiler.compile_project_dir(tmp_path)
    assert len(default["shots"]) == 5
    assert default["staging_review"][0]["outcome"] == "omitted"
    _, _, directed = ScreenplayCompiler.compile_project_dir(tmp_path, cinematic_cutaways=True)
    (state,) = [shot for shot in directed["shots"] if shot.get("cutaway_type")]
    assert state["shot_id"] != legacy["shot_id"]
    assert "hands and faces out of frame" in state["compiled_prompt"]
    _, _, repeated = ScreenplayCompiler.compile_project_dir(tmp_path, cinematic_cutaways=True)
    assert repeated == directed

    bible["props_ledger"][0]["state_tracking"]["B3"] = "In the open drawer"
    updated = ScreenplayCompiler.compile_shots(bible, beats, cinematic_cutaways=True)
    (updated_state,) = [shot for shot in updated["shots"] if shot.get("cutaway_type")]
    assert updated_state["shot_id"] != state["shot_id"]
    assert updated_state["keyframe_key"] != state["keyframe_key"]


def test_source_action_cannot_borrow_opening_state_from_another_scene():
    bible = _bible()
    bible["props_ledger"][0]["state_tracking"].update(B1="On the desk", B2="In Asha's hand")
    beats = _beats("Wait here.", "I will pick it up.")
    action = "Asha picks up the brass key."
    beats[1].update(
        speaker=None, dialogue=None, action_summary=action, location="HALL",
        staging={
            "kind": "source_action", "purpose": "Show Asha taking the key.", "prop_id": "KEY",
            "source_field": "action_summary", "source_excerpt": action, "character_id": "A",
            "before_state": "On the desk", "after_state": "In Asha's hand",
        },
    )
    first = ScreenplayCompiler.compile_shots(bible, beats, cinematic_cutaways=True)
    assert first["staging_review"][0]["outcome"] == "invalid"
    assert first["shots"][1]["action_summary"] == action
    beats[1]["location"] = "OFFICE"
    second = ScreenplayCompiler.compile_shots(bible, beats, cinematic_cutaways=True)
    source = second["shots"][1]
    assert source["staging"]["kind"] == "source_action"
    assert source["primary_character_id"] == "A"
    assert source["staging"]["before_state"] == "On the desk"
    assert source["staging"]["after_state"] == "In Asha's hand"
    assert source["compiled_prompt"].count(action) == 1
    assert len(second["shots"]) == len(beats)
    defects = ["DEFECT_FINGER", "DEFECT_FROZEN_VIDEO", "DEFECT_AUDIO_CLIPPING", "DEFECT_CAMERA_DRIFT"]
    repair = PromptRepairAgent.repair_shot(source, defects)
    assert repair["staging"] == source["staging"] and repair["framing"] == source["framing"]
    assert repair["action_summary"] == action and action in repair["compiled_prompt"]
    assert "speaks facing" not in repair["compiled_prompt"]
    assert "facial micro-movements" not in repair["compiled_prompt"]


def test_model_proposal_cannot_turn_spoken_intention_into_a_source_action(tmp_path):
    source = tmp_path / "scene.txt"
    spoken = "I will take the brass key tomorrow."
    source.write_text(f"INT. OFFICE - NIGHT\n\nASHA: {spoken}\n", encoding="utf-8")
    invented_action = "Asha takes the brass key."
    invented = _beats(spoken)
    invented.append({
        "beat_id": "FAKE", "location": "OFFICE", "characters_present": ["A"],
        "action_summary": invented_action,
        "staging": {"kind": "source_action", "source_excerpt": invented_action},
    })
    report = ScriptIngestor.ingest_file(
        source, tmp_path / "project", cinematic_cutaways=True,
        llm_callable=lambda _: {**_bible(), "beats": invented},
    )
    beats = json.loads(Path(report["beats_path"]).read_text(encoding="utf-8"))["beats"]
    assert [beat["dialogue"] for beat in beats] == [spoken]
    assert all(invented_action != beat["action_summary"] for beat in beats)


def test_resume_reuses_only_matching_recorded_render_inputs(tmp_path):
    keyframe = tmp_path / "frame.png"
    keyframe.write_bytes(b"original keyframe")
    clip = tmp_path / "clip.mp4"
    clip.touch()
    shot = {"shot_id": "S1", "compiled_prompt": "The key remains on the desk.", "first_frame_path": str(keyframe)}
    fingerprint = _render_fingerprint(shot, False)
    audit = tmp_path / "qc_audit_report.json"
    audit.write_text(json.dumps({
        "passed_clips": {"S1": str(clip)}, "per_shot_qc": {"S1": {"verdict": "PASS"}},
        "render_fingerprints": {"S1": fingerprint},
    }), encoding="utf-8")
    assert _load_render_checkpoint(audit, {"S1": shot}, False)[0] == {"S1": str(clip)}
    assert _load_render_checkpoint(audit, {"S1": {**shot, "compiled_prompt": "New coverage."}}, False) == ({}, {}, {})
    assert _load_render_checkpoint(audit, {"S1": shot}, True) == ({}, {}, {})
    keyframe.write_bytes(b"new keyframe")
    assert _load_render_checkpoint(audit, {"S1": shot}, False) == ({}, {}, {})
    assert clip.exists()


def test_deliberate_state_hold_and_authored_action_have_different_qc_contracts(tmp_path):
    clip = Path(tmp_path) / "hold.mp4"
    subprocess.run([
        "ffmpeg", "-v", "error", "-f", "lavfi",
        "-i", "testsrc2=s=640x360:r=24,trim=end_frame=1,tpad=stop_mode=clone:stop_duration=3",
        "-t", "3", "-c:v", "libx264", "-g", "1", "-threads", "2", "-pix_fmt", "yuv420p", str(clip),
    ], check=True)
    base = {"target_trim_duration_s": 2.0, "audio_mode": "SILENT_ACTION"}
    state = FilmQCEngine.evaluate_generated_clip(clip, {**base, "staging": {"kind": "state_insert"}}, min_duration_s=2.5)
    action = FilmQCEngine.evaluate_generated_clip(clip, {**base, "staging": {"kind": "source_action"}}, min_duration_s=2.5)
    assert state["verdict"] == "PASS", state["defects"]
    assert any("DEFECT_FROZEN_VIDEO" in item for item in action["defects"])
    assert action["metrics"]["trim_window"]["trim_in_s"] == 0.0
    assert action["metrics"]["trim_window"]["trim_out_s"] == 3.0
