import json
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

from film_pipeline.drama.post import probe_video_duration
from film_pipeline.production import animatic
from film_pipeline.production.animatic import MAX_WORDS_PER_SECOND, _plan_segments, build_animatic
from film_pipeline.production.package import PackageError, load_package

pytestmark = pytest.mark.skipif(shutil.which("ffmpeg") is None, reason="ffmpeg not installed")

FILM03 = Path(__file__).resolve().parents[1] / "films" / "film03_front_desk"
FILES = ("film.json", "script.fountain", "01_story.json", "02_direction.json", "03_preprod.json", "04_shots.json")


def tiny_package(tmp_path, keep=2, generation_s=None, name="film"):
    """film03 cut down to its first `keep` generations, optionally with a shorter generation length."""
    root = tmp_path / name
    root.mkdir()
    for file in FILES:
        (root / file).write_text((FILM03 / file).read_text(encoding="utf-8"), encoding="utf-8")
    shots = json.loads((root / "04_shots.json").read_text(encoding="utf-8"))
    shots["generations"] = shots["generations"][:keep]
    (root / "04_shots.json").write_text(json.dumps(shots), encoding="utf-8")
    if generation_s:
        film = json.loads((root / "film.json").read_text(encoding="utf-8"))
        film["generation_s"] = generation_s
        (root / "film.json").write_text(json.dumps(film), encoding="utf-8")
    return load_package(root)


def test_segments_lead_in_then_lines_evenly():
    assert _plan_segments(8.0, 2.0, []) == [(0.0, 8.0, None)]
    assert _plan_segments(8.0, 2.0, ["a", "b"]) == [(0.0, 2.0, None), (2.0, 5.0, "a"), (5.0, 8.0, "b")]
    assert _plan_segments(8.0, 0.0, ["a"]) == [(0.0, 8.0, "a")]
    assert _plan_segments(8.0, 20.0, ["a"])[0] == (0.0, 4.0, None)  # an absurd setup cannot eat the whole shot


def test_builds_mp4_srt_and_report_on_the_planned_timeline(tmp_path):
    pkg = tiny_package(tmp_path, keep=2, generation_s=4)
    out = tmp_path / "out"
    report = build_animatic(pkg, out)
    mp4 = out / "animatic.mp4"
    assert mp4.is_file() and report["ok"] and report["planned_duration_s"] == 8.0
    assert abs(probe_video_duration(mp4) - 8.0) <= 0.25
    assert [g["generation_id"] for g in report["generations"]] == ["SC01_g1", "SC01_g2"]
    assert [(g["start_s"], g["end_s"]) for g in report["generations"]] == [(0.0, 4.0), (4.0, 8.0)]
    assert {g["frame_source"] for g in report["generations"]} == {"storyboard"}
    assert {g["audio"] for g in report["generations"]} == {"silence"}
    srt = (out / "animatic.srt").read_text(encoding="utf-8")
    assert "KESSLER: Complaints window opens at nine." in srt and "NORA: I'm not here to complain." in srt
    assert json.loads((out / "animatic_report.json").read_text(encoding="utf-8"))["film_id"] == pkg.header.film_id
    assert not (out / "animatic_work").exists()  # scratch frames are cleaned up


def test_dialogue_windows_and_speed_findings(tmp_path):
    short = build_animatic(tiny_package(tmp_path, keep=2, generation_s=2), tmp_path / "out2")
    rows = [w for g in short["generations"] for w in g["dialogue"]]
    assert rows and all(w["end_s"] > w["start_s"] for w in rows)
    assert all(str(MAX_WORDS_PER_SECOND) in f["detail"] for f in short["findings"] if f["check"] == "DIALOGUE_TOO_FAST")
    assert short["ok"]  # speed findings are WARNs, the build itself is fine
    normal = build_animatic(tiny_package(tmp_path, keep=2, name="film8"), tmp_path / "out8")
    assert not [f for f in normal["findings"] if f["check"] == "DIALOGUE_TOO_FAST"]


def test_too_fast_dialogue_is_reported(tmp_path):
    # a 1 s generation holds a 5-word line in well under a second of window
    report = build_animatic(tiny_package(tmp_path, keep=2, generation_s=1), tmp_path / "out")
    assert any(f["check"] == "DIALOGUE_TOO_FAST" for f in report["findings"])


def test_approved_stills_beat_storyboard_frames(tmp_path):
    from PIL import Image
    pkg = tiny_package(tmp_path, keep=2, generation_s=2)
    stills = tmp_path / "stills"
    stills.mkdir()
    Image.new("RGB", (320, 180), (200, 30, 30)).save(stills / "SC01_g2.png")
    report = build_animatic(pkg, tmp_path / "out", stills_dir=stills)
    assert [g["frame_source"] for g in report["generations"]] == ["storyboard", "still"]


def test_temp_audio_is_padded_to_the_generation_and_long_audio_is_flagged(tmp_path):
    pkg = tiny_package(tmp_path, keep=2, generation_s=2)
    audio = tmp_path / "audio"
    audio.mkdir()
    for gid, seconds in (("SC01_g1", 1), ("SC01_g2", 3)):
        subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "lavfi", "-i", "sine=frequency=440", "-t", str(seconds),
                        str(audio / f"{gid}.wav")], check=True)
    out = tmp_path / "out"
    report = build_animatic(pkg, out, audio_dir=audio)
    assert [g["audio"] for g in report["generations"]] == ["temp", "temp"]
    assert any(f["check"] == "AUDIO_TOO_LONG" and "SC01_g2" in f["detail"] for f in report["findings"])
    assert abs(probe_video_duration(out / "animatic.mp4") - 4.0) <= 0.25  # the long track was cut, the timeline held


def test_placeholder_card_when_no_frame_source_exists(tmp_path, monkeypatch):
    pkg = tiny_package(tmp_path, keep=1, generation_s=2)
    monkeypatch.setattr(animatic, "_schematic_frames", lambda *a, **k: {})
    report = build_animatic(pkg, tmp_path / "out")
    assert report["generations"][0]["frame_source"] == "placeholder"
    assert any(f["check"] == "FRAME_PLACEHOLDER" for f in report["findings"])


def test_needs_shots_and_script(tmp_path):
    (tmp_path / "film.json").write_text((FILM03 / "film.json").read_text(encoding="utf-8"), encoding="utf-8")
    (tmp_path / "script.fountain").write_text("", encoding="utf-8")
    with pytest.raises(PackageError, match="needs a valid 04_shots.json"):
        build_animatic(load_package(tmp_path), tmp_path / "out")


def test_cli_animatic(tmp_path):
    root = tiny_package(tmp_path, keep=1, generation_s=2).root
    tool = Path(__file__).resolve().parents[1] / "tools" / "film.py"
    done = subprocess.run([sys.executable, str(tool), "animatic", "--film", str(root), "--out", str(tmp_path / "o")],
                          capture_output=True, text=True, encoding="utf-8")
    body = json.loads(done.stdout)
    assert done.returncode == 0 and body["ok"] and Path(body["video"]).is_file()
    default = subprocess.run([sys.executable, str(tool), "animatic", "--film", str(root)],
                             capture_output=True, text=True, encoding="utf-8")
    assert default.returncode == 0 and (root / "media" / "animatic.mp4").is_file()
