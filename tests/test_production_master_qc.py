import json
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

from film_pipeline.production import master_qc as Q
from film_pipeline.production.package import load_package

ROOT = Path(__file__).resolve().parents[1]
FILM03 = ROOT / "films" / "film03_front_desk"
TOOL = ROOT / "tools" / "film.py"
needs_ffmpeg = pytest.mark.skipif(not (shutil.which("ffmpeg") and shutil.which("ffprobe")), reason="ffmpeg not installed")
PICTURE = "testsrc2=size=1280x720:rate=24"
TONE = "sine=frequency=1000:sample_rate=48000"


def master(path: Path, *, seconds=10.0, picture=PICTURE, vf="", audio_vol=2.47, af="", size=None, rate=None, faststart=True,
           audio=True, codec_args=(), pix_fmt="yuv420p") -> Path:
    """A synthetic master: moving test picture and a 1 kHz tone (the sine is 0.125 full scale: volume 2.47 is about -14 LUFS)."""
    src = picture if size is None else f"testsrc2=size={size}:rate={rate or 24}"
    cmd = ["ffmpeg", "-v", "error", "-y", "-f", "lavfi", "-i", f"{src}:duration={seconds}"]
    if audio:
        cmd += ["-f", "lavfi", "-i", f"{TONE}:duration={seconds}"]
    if vf:
        cmd += ["-vf", vf]
    if audio:
        cmd += ["-af", f"volume={audio_vol}" + (f",{af}" if af else "")]
    else:
        cmd += ["-an"]
    cmd += ["-r", str(rate or 24), "-c:v", "libx264", "-pix_fmt", pix_fmt, *codec_args]
    if audio:
        cmd += ["-c:a", "aac", "-ar", "48000"]
    if faststart:
        cmd += ["-movflags", "+faststart"]
    subprocess.run(cmd + [str(path)], check=True)
    return path


def findings(record, severity=None):
    return sorted({(f.code, f.severity) for f in record.findings if severity in (None, f.severity)})


def results(record):
    return {c.group: c.result for c in record.checks}


@needs_ffmpeg
def test_a_clean_master_passes_where_it_can(tmp_path):
    record = Q.check_master(master(tmp_path / "ok.mp4"))
    assert record.ok and findings(record) == []
    assert results(record) == {"technical": "PASS", "audio": "PASS", "sync": "UNASSESSED", "color": "PASS", "delivery": "PASS"}
    assert abs(record.metrics["integrated_lufs"] + 14) < 1.5 and record.metrics["size"] == "1280x720"
    assert all(c.level == "CUT" and c.reviewer == "auto:master_qc" for c in record.checks if c.result != "UNASSESSED")


@needs_ffmpeg
def test_wrong_format_blocks(tmp_path):
    record = Q.check_master(master(tmp_path / "small.mp4", size="640x360", rate=25))
    assert {("RESOLUTION", "BLOCK"), ("FPS", "BLOCK")} <= set(findings(record)) and not record.ok
    assert results(record)["technical"] == "FAIL"
    wide = Q.check_master(master(tmp_path / "444.mp4", pix_fmt="yuv444p"))
    assert ("VCODEC", "BLOCK") in findings(wide)


@needs_ffmpeg
def test_black_frames_block_and_short_ones_warn(tmp_path):
    for seconds, severity in ((1.5, "BLOCK"), (0.3, "WARN")):
        vf = f"drawbox=x=0:y=0:w=iw:h=ih:color=black:t=fill:enable='between(t,4,{4 + seconds})'"
        record = Q.check_master(master(tmp_path / f"black{seconds}.mp4", vf=vf))
        code = next(f for f in record.findings if f.code == "BLACK_FRAMES")
        assert code.severity == severity and abs(code.at_s - 4.0) < 0.2


@needs_ffmpeg
def test_a_frozen_picture_is_found_by_length(tmp_path):
    for hold, severity in ((5.0, "BLOCK"), (2.5, "WARN")):
        vf = f"freezeframes=first=1:last={int(24 * 8)}:replace={int((8 - hold) * 24) + 1}" if False else \
            f"trim=duration={8 - hold},tpad=stop_mode=clone:stop_duration={hold}"
        record = Q.check_master(master(tmp_path / f"freeze{hold}.mp4", seconds=8.0, vf=vf))
        freeze = next(f for f in record.findings if f.code == "FREEZE")
        assert freeze.severity == severity and abs(freeze.at_s - (8 - hold)) < 0.3


@needs_ffmpeg
def test_duplicated_frames_warn(tmp_path):
    record = Q.check_master(master(tmp_path / "dup.mp4", seconds=6.0, vf="fps=12,fps=24"))
    assert ("DUPLICATED_FRAMES", "WARN") in findings(record) and record.metrics["duplicate_ratio"] > 0.4
    assert ("DUPLICATED_FRAMES", "WARN") not in findings(Q.check_master(master(tmp_path / "live.mp4", seconds=6.0)))


@needs_ffmpeg
def test_exposure_extremes_warn(tmp_path):
    for name, vf in (("dark", "eq=brightness=-0.5"), ("bright", "eq=brightness=0.5")):   # mean luma 16.7 / 236.5
        record = Q.check_master(master(tmp_path / f"{name}.mp4", seconds=6.0, vf=vf))
        assert ("EXPOSURE_RANGE", "WARN") in findings(record) and results(record)["color"] == "WARN" and record.ok, name


@needs_ffmpeg
def test_audio_levels_and_clipping_block(tmp_path):
    loud = Q.check_master(master(tmp_path / "loud.mp4", audio_vol=20.0))
    assert {"LOUDNESS", "TRUE_PEAK", "CLIPPING"} <= {c for c, _ in findings(loud)} and results(loud)["audio"] == "FAIL"
    quiet = Q.check_master(master(tmp_path / "quiet.mp4", audio_vol=0.05))
    assert [c for c, s in findings(quiet) if s == "BLOCK"] == ["LOUDNESS"]


@needs_ffmpeg
def test_a_long_silence_in_the_body_warns(tmp_path):
    record = Q.check_master(master(tmp_path / "gap.mp4", seconds=12.0, af="volume=enable='between(t,3,8)':volume=0"))
    gap = next(f for f in record.findings if f.code == "SILENCE_GAP")
    assert gap.severity == "WARN" and abs(gap.at_s - 3.0) < 0.3 and results(record)["audio"] == "WARN"


@needs_ffmpeg
def test_missing_streams_and_files(tmp_path):
    silent = Q.check_master(master(tmp_path / "mute.mp4", audio=False))
    assert ("STREAM_MISSING", "P0") in findings(silent) and results(silent)["audio"] == "UNASSESSED"
    assert next(c for c in silent.checks if c.group == "technical").severity == "P0"
    empty = tmp_path / "empty.mp4"
    empty.write_bytes(b"")
    gone = Q.check_master(empty)
    assert not gone.ok and ("EMPTY_FILE", "P0") in findings(gone)


@needs_ffmpeg
def test_a_slow_start_container_warns(tmp_path):
    record = Q.check_master(master(tmp_path / "slow.mp4", faststart=False))
    assert findings(record) == [("FASTSTART", "WARN")] and results(record)["delivery"] == "WARN" and record.ok
    assert Q.faststart(tmp_path / "slow.mp4") is False


@needs_ffmpeg
def test_the_audio_and_video_must_agree_in_length(tmp_path):
    path = tmp_path / "drift.mp4"
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "lavfi", "-i", f"{PICTURE}:duration=10", "-f", "lavfi", "-i",
                    f"{TONE}:duration=7", "-af", "volume=2.47", "-c:v", "libx264", "-pix_fmt", "yuv420p", "-c:a", "aac",
                    str(path)], check=True)
    record = Q.check_master(path, pkg=load_package(FILM03))
    assert ("AV_DURATION", "BLOCK") in findings(record) and results(record)["sync"] == "FAIL"


# ------------------------------------------------------------------ sync against the dialogue stem

def speech_stem(path: Path, start=2.0, seconds=2.0, total=10.0) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "lavfi", "-i", f"{TONE}:duration={seconds}", "-af",
                    f"volume=0.3,adelay={int(start * 1000)},apad=whole_dur={total}", "-ac", "2", "-ar", "48000",
                    str(path)], check=True)
    return path


def film_with(tmp_path: Path, cues: list[tuple[float, float]]):
    root = tmp_path / "film"
    root.mkdir(parents=True)
    for name in ("film.json", "script.fountain", "01_story.json", "02_direction.json", "03_preprod.json", "04_shots.json"):
        shutil.copyfile(FILM03 / name, root / name)
    speech_stem(root / "audio" / "stems" / "dialogue.wav")
    (root / "titles").mkdir()
    (root / "titles" / "titles.json").write_text(json.dumps({"cues": [
        {"abs_start_s": a, "abs_end_s": b, "text": "x"} for a, b in cues]}), encoding="utf-8")
    return load_package(root)


@needs_ffmpeg
def test_cues_are_checked_against_the_speech(tmp_path):
    video = master(tmp_path / "m.mp4")
    pkg = film_with(tmp_path, [(2.0, 4.0)])
    ok = Q.check_master(video, pkg=pkg)
    assert results(ok)["sync"] == "PASS" and ok.metrics["cues_checked"] == 1 and ok.metrics["median_offset_s"] == 0.0


@needs_ffmpeg
def test_a_late_cue_and_a_cue_without_speech(tmp_path):
    video = master(tmp_path / "m.mp4")
    late = Q.check_master(video, pkg=film_with(tmp_path / "a", [(3.5, 5.5)]))
    off = next(f for f in late.findings if f.code == "SYNC_OFFSET")
    assert off.severity == "BLOCK" and results(late)["sync"] == "FAIL"
    nothing = Q.check_master(video, pkg=film_with(tmp_path / "b", [(7.0, 8.5)]))
    assert findings(nothing) == [("CUE_NO_SPEECH", "WARN")] and results(nothing)["sync"] == "WARN"


def test_cue_offset_finds_the_best_shift():
    spec = Q.MasterSpec()
    active = [False] * 40 + [True] * 40 + [False] * 40          # speech 2.0 - 4.0 s at a 0.05 s hop
    assert Q.cue_offset(active, 2.0, 4.0, spec)["best_shift_s"] == 0.0
    assert Q.cue_offset(active, 2.3, 4.3, spec)["best_shift_s"] == -0.3
    assert Q.cue_offset(active, 0.2, 0.9, spec)["best_coverage"] == 0.0


def test_exempt_windows_are_cut_out():
    assert Q._outside(0.0, 10.0, [(0.0, 3.0), (8.0, 12.0)]) == [(3.0, 8.0)]
    assert Q._outside(2.0, 4.0, [(0.0, 10.0)]) == []
    assert Q._runs([False, True, True, False, True]) == [(1, 3), (4, 5)]


# ------------------------------------------------------------------ the real pipeline output

@needs_ffmpeg
def test_cli_on_a_cut_rendered_titled_and_mixed_by_the_pipeline(tmp_path):
    root = tmp_path / "film"
    root.mkdir()
    for name in ("film.json", "script.fountain", "01_story.json", "02_direction.json", "03_preprod.json", "04_shots.json"):
        shutil.copyfile(FILM03 / name, root / name)
    from film_pipeline.production import takes as T
    from film_pipeline.production.edit import EditEvent, EditSection
    clips = tmp_path / "clips"
    clips.mkdir()
    for i, gid in enumerate(("SC01_g1", "SC01_g2")):
        path = clips / f"{gid}.mp4"
        subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "lavfi", "-i", f"testsrc2=size=1280x720:rate=24:duration=6",
                        "-f", "lavfi", "-i", f"sine=frequency={500 + 200 * i}:sample_rate=48000:duration=1.8", "-af",
                        "volume=0.3,adelay=2000,apad=whole_dur=6", "-c:v", "libx264", "-pix_fmt", "yuv420p", "-c:a", "aac",
                        str(path)], check=True)
        T.register_take(root, "film03_front_desk", gid, path, prompt_text=f"p {gid}", route="r", model="m", credits=1.0)
    (root / "05_edit.json").write_text(EditSection(events=[
        EditEvent(event_id="a", take_id="SC01_g1_t1"), EditEvent(event_id="b", take_id="SC01_g2_t1")]).model_dump_json(),
        encoding="utf-8")

    def run(*args):
        return subprocess.run([sys.executable, str(TOOL), *args], capture_output=True, text=True, encoding="utf-8", cwd=ROOT)

    cut = root / "media" / "cut" / "titled_cut.mp4"
    assert run("titles", "--film", str(root), "--clips", str(clips), "--langs", "en", "--render", "--out", str(cut)).returncode == 0
    assert run("mix", "--film", str(root), "--cut", str(cut), "--out", str(root / "media" / "cut" / "mixed.mp4")).returncode == 0
    done = run("mastercheck", "--film", str(root), "--cut-report", str(cut.with_suffix(".cut.json")))
    body = json.loads(done.stdout)
    assert done.returncode == 0 and body["ok"], body
    assert body["checks"]["technical"] == "PASS" and body["checks"]["audio"] == "PASS" and body["checks"]["delivery"] in ("PASS", "WARN")
    assert body["checks"]["sync"] in ("PASS", "WARN")
    assert (root / "qc" / "master_qc.json").is_file()
    post = json.loads((root / "06_post.json").read_text(encoding="utf-8"))
    assert post["master_qc"]["ok"] and post["master_qc"]["sha256"]
    record = Q.MasterQc.model_validate_json((root / "qc" / "master_qc.json").read_text(encoding="utf-8"))
    assert record.ok and abs(record.metrics["duration_s"] - record.metrics["planned_s"]) < 0.25
    missing = run("mastercheck", "--film", str(root), "--video", str(tmp_path / "none.mp4"))
    assert missing.returncode == 2
