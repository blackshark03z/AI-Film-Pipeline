import json
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

from film_pipeline.drama.post import measure_ebur128
from film_pipeline.production import lock as L
from film_pipeline.production import mix as M
from film_pipeline.production import takes as T
from film_pipeline.production.edit import EditEvent, EditSection, render_cut
from film_pipeline.production.package import load_package

ROOT = Path(__file__).resolve().parents[1]
FILM03 = ROOT / "films" / "film03_front_desk"
TOOL = ROOT / "tools" / "film.py"
FILES = ("film.json", "script.fountain", "01_story.json", "02_direction.json", "03_preprod.json", "04_shots.json")
needs_ffmpeg = pytest.mark.skipif(not (shutil.which("ffmpeg") and shutil.which("ffprobe")), reason="ffmpeg not installed")
GIDS = ("SC01_g1", "SC01_g2", "SC02_g1")   # SC02_g1 declares the sfx 'paper unfolding'


def speech_clip(path: Path, seconds: float, freq: int) -> Path:
    """Solid picture; sound is a tone that is on for 1 s and off for 1 s (something to duck under)."""
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "lavfi", "-i", f"color=c=gray:size=320x180:rate=24:duration={seconds}",
                    "-f", "lavfi", "-i", f"sine=frequency={freq}:sample_rate=48000:duration={seconds}",
                    "-af", "volume='if(lt(mod(t,2),1),0.5,0)':eval=frame", "-c:v", "libx264", "-pix_fmt", "yuv420p",
                    "-c:a", "aac", "-shortest", str(path)], check=True)
    return path


def tone_wav(path: Path, freq: int, seconds: float) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "lavfi", "-i", f"sine=frequency={freq}:sample_rate=48000:duration={seconds}",
                    "-ac", "2", str(path)], check=True)
    return path


@pytest.fixture()
def cut(tmp_path):
    """film03 package, three 3 s takes, rendered cut (title 3 s + 9 s + end 4 s = 16 s)."""
    root = tmp_path / "film"
    root.mkdir()
    for name in FILES:
        shutil.copyfile(FILM03 / name, root / name)
    clips = tmp_path / "clips"
    clips.mkdir()
    for i, gid in enumerate(GIDS):
        T.register_take(root, "film03_front_desk", gid, speech_clip(clips / f"{gid}.mp4", 3.0, 300 + 100 * i),
                        prompt_text=f"prompt {gid}", route="r", model="m", credits=12.0)
    section = EditSection(events=[EditEvent(event_id=e, take_id=f"{g}_t1") for e, g in zip("abc", GIDS)])
    (root / "05_edit.json").write_text(section.model_dump_json(indent=2), encoding="utf-8")
    pkg = load_package(root)
    out = tmp_path / "cut" / "rough.mp4"
    render_cut(pkg, section, out, clips_dir=clips)
    return pkg, section, out, tmp_path


def level(path: Path, t0: float, t1: float) -> float:
    return max(M._frames_db_range(path, t0, t1))


@needs_ffmpeg
def test_scene_spans_merge_consecutive_takes_of_one_scene(cut):
    pkg, section, out, _ = cut
    planned = json.loads(out.with_suffix(".cut.json").read_text(encoding="utf-8"))["planned"]
    spans = M.scene_spans(pkg, section, planned)
    assert [(s["scene_id"], s["start_s"], s["end_s"]) for s in spans] == [("SC01", 3.0, 9.0), ("SC02", 9.0, 12.0)]
    assert spans[0]["room_tone"] == "fluorescent hum, distant phones" and M.tone_for(spans[0]["room_tone"])[0] == "brown"
    assert M.tone_for("quiet room, chairs creaking") == ("brown", 400, 0) and M.tone_for("a courtyard") == M.DEFAULT_TONE


@needs_ffmpeg
def test_stems_are_cut_length_with_ambience_only_inside_scenes(cut):
    pkg, section, out, tmp = cut
    built = M.build_stems(pkg, section, out, tmp / "stems", M.MixPlan())
    total = built["total_s"]
    for name, path in built["stems"].items():
        got = float(subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", path],
                                   capture_output=True, text=True, check=True).stdout)
        assert abs(got - total) < 0.15, name
    assert level(Path(built["stems"]["ambience"]), 0.0, 2.5) < -80      # title card: silence
    assert level(Path(built["stems"]["ambience"]), 4.0, 8.0) > -70      # inside the scene: a bed
    assert level(Path(built["stems"]["ambience"]), 12.8, 15.5) < -80     # end card: silence
    amb = tmp / "amb_cut.wav"
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-ss", "3.6", "-t", "4.8", "-i", built["stems"]["ambience"], str(amb)], check=True)
    assert abs(measure_ebur128(amb)["integrated_lufs"] - (-40.0)) < 3.0
    assert level(Path(built["stems"]["music"]), 0.0, total) < -80       # no cues, no music
    assert [p["code"] for p in built["problems"]] == ["SFX_UNSOURCED"]


@needs_ffmpeg
def test_sfx_is_placed_only_when_an_asset_exists_and_music_comes_from_the_plan(cut):
    pkg, section, out, tmp = cut
    root = Path(pkg.root)
    tone_wav(root / "audio" / "sfx" / "paper_unfolding.wav", 1500, 0.6)
    tone_wav(root / "audio" / "music" / "theme.wav", 220, 12.0)
    plan = M.MixPlan(music=[M.MusicCue(cue_id="M1", asset="music/theme.wav", start_s=3.0, end_s=12.0, gain_db=-12.0,
                                       why="the room waits")])
    built = M.build_stems(pkg, section, out, tmp / "stems", plan)
    assert built["problems"] == [] and built["sfx"][0]["asset"] == "audio/sfx/paper_unfolding.wav"
    assert built["sfx"][0]["at_s"] == 9.0 and len(built["sfx"][0]["sha256"]) == 64
    sfx = Path(built["stems"]["sfx"])
    assert level(sfx, 9.1, 9.5) > -35 and level(sfx, 4.0, 8.0) < -80
    music = Path(built["stems"]["music"])
    assert level(music, 5.0, 8.0) > -40 and level(music, 0.0, 2.5) < -80 and level(music, 12.5, 15.5) < -80
    assert built["music"][0]["sha256"] and built["music"][0]["why"] == "the room waits"


@needs_ffmpeg
def test_a_missing_music_asset_blocks_the_mix(cut):
    pkg, section, out, tmp = cut
    plan = M.MixPlan(music=[M.MusicCue(cue_id="M1", asset="music/nowhere.wav", start_s=3.0)])
    with pytest.raises(ValueError, match="MUSIC_ASSET_MISSING"):
        M.mix_cut(pkg, section, out, tmp / "mixed.mp4", plan=plan)
    assert not (tmp / "mixed.mp4").exists()


def test_mixing_needs_the_cut_report(tmp_path):
    with pytest.raises(ValueError, match="render the cut first"):
        M.build_stems(type("P", (), {"root": tmp_path})(), None, tmp_path / "x.mp4", tmp_path / "stems")


@needs_ffmpeg
def test_full_mix_ducks_the_bed_under_dialogue_and_meets_the_loudness_target(cut):
    pkg, section, out, tmp = cut
    root = Path(pkg.root)
    tone_wav(root / "audio" / "music" / "theme.wav", 220, 12.0)
    plan = M.MixPlan(music=[M.MusicCue(cue_id="M1", asset="music/theme.wav", start_s=3.0, end_s=12.0, gain_db=-14.0)])
    report = M.mix_cut(pkg, section, out, tmp / "mixed.mp4", plan=plan)
    assert report["ok"] and Path(report["report"]).is_file()
    assert report["duck"]["depth_db"] >= 6.0 and report["duck"]["frames"] > 5, report["duck"]
    loud = report["loudness"]
    assert abs(loud["after"]["integrated_lufs"] + 14.0) <= 1.0 and loud["after"]["peak_dbfs"] <= -1.0 and loud["ok"]
    # the mixed file is measured from the file itself, not from the report
    again = measure_ebur128(tmp / "mixed.mp4")
    assert abs(again["integrated_lufs"] + 14.0) <= 1.0 and again["peak_dbfs"] <= -1.0
    # the picture is untouched (copied) and the length is the cut's
    probe = lambda p: float(subprocess.run(["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries",  # noqa: E731
                                            "stream=duration", "-of", "csv=p=0", str(p)], capture_output=True, text=True,
                                           check=True).stdout)
    assert abs(probe(tmp / "mixed.mp4") - probe(out)) < 0.1
    assert report["cut_sha256"] == M.sha256_file(out) and report["output_sha256"] == M.sha256_file(tmp / "mixed.mp4")


@needs_ffmpeg
def test_a_bed_alone_is_not_ducked_and_a_shallow_duck_warns(cut):
    pkg, section, out, tmp = cut
    root = Path(pkg.root)
    tone_wav(root / "audio" / "music" / "theme.wav", 220, 12.0)
    plan = M.MixPlan(duck_ratio=1.0, music=[M.MusicCue(cue_id="M1", asset="music/theme.wav", start_s=3.0, end_s=12.0)])
    report = M.mix_cut(pkg, section, out, tmp / "flat.mp4", plan=plan)
    assert "DUCK_TOO_SHALLOW" in {p["code"] for p in report["problems"]} and report["ok"]   # advisory only


@needs_ffmpeg
def test_stamp_marks_the_mix_unstamped_until_the_picture_is_locked(cut):
    pkg, section, out, tmp = cut
    report = M.mix_cut(pkg, section, out, tmp / "mixed.mp4")
    assert M.stamp_post_item(pkg, "mix", {"output_sha256": report["output_sha256"]}) == ""
    dirty = L.dirty_items(load_package(pkg.root))["dirty"]
    assert [(d["stage"], d["item"]) for d in dirty] == [("post", "mix")] and dirty[0]["reason"].startswith("UNSTAMPED")


@needs_ffmpeg
def test_cli_mix(cut):
    pkg, section, out, tmp = cut
    target = tmp / "cli_mixed.mp4"
    run = subprocess.run([sys.executable, str(TOOL), "mix", "--film", str(pkg.root), "--cut", str(out), "--out", str(target)],
                         capture_output=True, text=True, encoding="utf-8", cwd=ROOT)
    body = json.loads(run.stdout)
    assert run.returncode == 0 and body["ok"] and target.is_file()
    post = json.loads((Path(pkg.root) / "06_post.json").read_text(encoding="utf-8"))
    assert post["mix"]["output_sha256"] == body["output_sha256"] and post["mix"]["locked_against"] == ""
    missing = subprocess.run([sys.executable, str(TOOL), "mix", "--film", str(pkg.root), "--cut", str(tmp / "no.mp4")],
                             capture_output=True, text=True, encoding="utf-8", cwd=ROOT)
    assert missing.returncode == 1 and "render the cut first" in json.loads(missing.stdout)["error"]
