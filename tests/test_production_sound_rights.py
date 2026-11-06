import json
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

from film_pipeline.production import mix as M
from film_pipeline.production import sound_rights as S
from film_pipeline.production.package import load_package
from film_pipeline.production.planning import planning_issues

ROOT = Path(__file__).resolve().parents[1]
FILM03 = ROOT / "films" / "film03_front_desk"
TOOL = ROOT / "tools" / "film.py"
FILES = ("film.json", "script.fountain", "01_story.json", "02_direction.json", "03_preprod.json", "04_shots.json")


@pytest.fixture()
def film(tmp_path):
    root = tmp_path / "film"
    root.mkdir()
    for name in FILES:
        shutil.copyfile(FILM03 / name, root / name)
    (root / "audio" / "music").mkdir(parents=True)
    (root / "audio" / "sfx").mkdir(parents=True)
    (root / "audio" / "music" / "theme.wav").write_bytes(b"music-bytes")
    (root / "audio" / "sfx" / "paper_unfolding.wav").write_bytes(b"sfx-bytes")
    plan = M.MixPlan(music=[M.MusicCue(cue_id="M1", asset="music/theme.wav", start_s=3.0, end_s=12.0,
                                       why="the room waits", scene_id="SC02")])
    (root / "audio" / "mix_plan.json").write_text(plan.model_dump_json(indent=2), encoding="utf-8")
    return load_package(root)


def good_record(pkg, **kw):
    args = dict(source_url="https://example.org/theme", status="cleared", attribution="Theme by A. Composer, CC BY 4.0",
                usage=[S.UsageRange(start_s=0.0, end_s=20.0)])
    args.update(kw)
    return S.record_asset(pkg, "audio/music/theme.wav", "music", "CC-BY-4.0", **args)


def codes(pkg):
    return sorted(i["code"] for i in S.check_assets(pkg)["issues"])


def test_film03_has_no_sound_assets_and_no_issues():
    pkg = load_package(FILM03)
    assert S.used_assets(pkg) == [] and S.sound_rights_issues(pkg) == []


def test_used_assets_follow_the_plan_and_the_declared_sfx(film):
    used = S.used_assets(film)
    assert [(u["asset"], u["kind"]) for u in used] == [("audio/music/theme.wav", "music"), ("audio/sfx/paper_unfolding.wav", "sfx")]
    assert used[0]["uses"] == [{"cue_id": "M1", "start_s": 3.0, "end_s": 12.0}]
    assert used[1]["uses"] == [{"generation_id": "SC02_g1", "text": "paper unfolding"}]
    (Path(film.root) / "audio" / "sfx" / "unrelated.wav").write_bytes(b"x")   # no shot declares it
    assert len(S.used_assets(film)) == 2


def test_unrecorded_assets_block_validate(film):
    assert codes(film) == ["ASSET_UNRECORDED", "ASSET_UNRECORDED"]
    assert all(i.startswith("SOUND_RIGHTS ASSET_UNRECORDED") for i in planning_issues(film) if "SOUND_RIGHTS" in i)
    assert len([i for i in planning_issues(film) if "SOUND_RIGHTS" in i]) == 2


def test_a_cleared_record_passes_and_a_changed_file_does_not(film):
    good_record(film)
    S.record_asset(film, "audio/sfx/paper_unfolding.wav", "sfx", "GENERATED_OFFLINE", status="cleared", note="synth in house")
    assert codes(film) == [] and S.attributions(film) == ["Theme by A. Composer, CC BY 4.0"]
    (Path(film.root) / "audio" / "music" / "theme.wav").write_bytes(b"swapped")
    assert codes(film) == ["ASSET_HASH_CHANGED"]
    (Path(film.root) / "audio" / "music" / "theme.wav").unlink()
    assert codes(film) == ["ASSET_MISSING"]


@pytest.mark.parametrize("kw,code", [
    ({"status": "pending"}, "LICENSE_NOT_CLEARED"),
    ({"status": "restricted"}, "LICENSE_NOT_CLEARED"),
    ({"source_url": ""}, "SOURCE_MISSING"),
    ({"source_url": "not a url"}, "SOURCE_MISSING"),
    ({"attribution": " "}, "ATTRIBUTION_MISSING"),
    ({"usage": []}, "USAGE_NOT_COVERED"),
    ({"usage": [S.UsageRange(start_s=0.0, end_s=8.0)]}, "USAGE_NOT_COVERED"),
])
def test_each_missing_piece_of_a_license_blocks(film, kw, code):
    S.record_asset(film, "audio/sfx/paper_unfolding.wav", "sfx", "CC0-1.0", source_url="https://example.org/s", status="cleared")
    good_record(film, **kw)
    assert codes(film) == [code]


def test_unknown_license_and_wrong_kind_block(film):
    S.record_asset(film, "audio/sfx/paper_unfolding.wav", "music", "CC0-1.0", source_url="https://example.org/s", status="cleared")
    S.record_asset(film, "audio/music/theme.wav", "music", "SOME-EULA", status="cleared",
                   usage=[S.UsageRange(start_s=0.0)])
    assert codes(film) == ["KIND_MISMATCH", "LICENSE_UNKNOWN"]


def test_open_ended_usage_covers_any_cue_end(film):
    S.record_asset(film, "audio/sfx/paper_unfolding.wav", "sfx", "ORIGINAL", status="cleared")
    S.record_asset(film, "audio/music/theme.wav", "music", "ORIGINAL", status="cleared", usage=[S.UsageRange(start_s=0.0)])
    assert codes(film) == []


def test_record_needs_the_file(film):
    with pytest.raises(ValueError, match="not found"):
        S.record_asset(film, "audio/music/nowhere.wav", "music", "CC0-1.0")


def test_cue_sheet_reads_the_emotional_curve():
    sheet = S.cue_sheet(load_package(FILM03))
    by_scene = {a["scene_id"]: a for a in sheet["advice"]}
    assert list(by_scene) == ["SC01", "SC02", "SC03", "SC04", "SC05", "SC06", "SC07", "SC08"]
    assert sheet["music_planned"] is False and sheet["planned"] == []
    assert all(a["why"] for a in sheet["advice"]) and {a["action"] for a in sheet["advice"]} <= {"IN", "HOLD", "OUT", "DUCK", "NONE"}
    # the state machine never says HOLD/OUT/DUCK before an IN
    seen = False
    for a in sheet["advice"]:
        seen = seen or a["action"] == "IN"
        assert seen or a["action"] == "NONE"


def test_cue_sheet_checks_the_planned_cues(film):
    sheet = S.cue_sheet(film)
    assert sheet["planned"][0]["why"] == "the room waits" and sheet["music_planned"]
    plan = M.MixPlan(music=[M.MusicCue(cue_id="A", asset="music/theme.wav", start_s=0.0),
                            M.MusicCue(cue_id="B", asset="music/theme.wav", start_s=1.0, why="x", scene_id="SC99")])
    (Path(film.root) / "audio" / "mix_plan.json").write_text(plan.model_dump_json(), encoding="utf-8")
    warnings = {(w["code"], w["cue_id"]) for w in S.cue_sheet(film)["warnings"]}
    assert warnings == {("CUE_NO_REASON", "A"), ("CUE_SCENE_UNKNOWN", "B")}


def test_cli_record_then_check(film):
    def run(*args):
        return subprocess.run([sys.executable, str(TOOL), "sounds", "--film", str(film.root), *args], capture_output=True,
                              text=True, encoding="utf-8", cwd=ROOT)

    first = run()
    assert first.returncode == 1 and len(json.loads(first.stdout)["issues"]) == 2
    no_license = run("--record", "audio/music/theme.wav")
    assert no_license.returncode == 1 and "--kind and --license" in json.loads(no_license.stdout)["error"]
    rec = run("--record", "audio/music/theme.wav", "--kind", "music", "--license", "CC0-1.0", "--source-url", "https://example.org/t",
              "--usage", "0:20")
    body = json.loads(rec.stdout)["recorded"]
    assert rec.returncode == 0 and body["status"] == "pending" and body["usage"][0]["end_s"] == 20.0   # never auto-cleared
    still = json.loads(run().stdout)
    assert {i["code"] for i in still["issues"] if i["asset"].endswith("theme.wav")} == {"LICENSE_NOT_CLEARED"}
    run("--record", "audio/music/theme.wav", "--kind", "music", "--license", "CC0-1.0", "--source-url", "https://example.org/t",
        "--usage", "0:20", "--status", "cleared")
    run("--record", "audio/sfx/paper_unfolding.wav", "--kind", "sfx", "--license", "GENERATED_OFFLINE", "--status", "cleared")
    done = run()
    assert done.returncode == 0 and json.loads(done.stdout)["ok"] and json.loads(done.stdout)["cue_sheet"]["music_planned"]
