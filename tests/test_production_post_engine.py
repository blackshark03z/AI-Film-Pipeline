"""Opt-in delegation of the final mix to the external post engine (switch, command, failure handling, end to end)."""
import json
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

from film_pipeline.production import finish as F
from film_pipeline.production import mix as M
from film_pipeline.production import post_engine as PE
from film_pipeline.production import takes as T
from film_pipeline.production.edit import EditEvent, EditSection, render_cut
from film_pipeline.production.package import load_package

ROOT = Path(__file__).resolve().parents[1]
FILM03 = ROOT / "films" / "film03_front_desk"
FILES = ("film.json", "script.fountain", "01_story.json", "02_direction.json", "03_preprod.json", "04_shots.json")
GIDS = ("SC01_g1", "SC01_g2", "SC02_g1")
needs_ffmpeg = pytest.mark.skipif(not (shutil.which("ffmpeg") and shutil.which("ffprobe")), reason="ffmpeg not installed")

# A stand-in for `post-engine render <package> --out <dir>`: MODE (argv[1]) decides how it misbehaves.
FAKE_ENGINE = r'''
import json, shutil, sys
from pathlib import Path

mode, package, out = sys.argv[1], Path(sys.argv[2]), Path(sys.argv[4])
data = json.loads(package.read_text(encoding="utf-8"))
if mode == "crash":
    print("boom: engine exploded", file=sys.stderr)
    sys.exit(3)
folder = out / data["film_id"]
folder.mkdir(parents=True)
root = Path(data["source"]["root"])
picture = next(f for f in data["files"] if f["id"] == data["picture"]["file_id"])
if mode != "no_output":
    shutil.copyfile(root / picture["path"], folder / "final.mp4")
checks = {"lufs_within_tolerance": mode != "failed", "true_peak_ok": True, "duration_within_1_frame": True}
report = {"passed": mode != "failed", "package_sha256": "x", "dialogue_leveling": {"gain_db": 1.5},
          "measurements": {"integrated_lufs": -14.1, "true_peak_dbtp": -1.2, "duration_frames": 288, "checks": checks}}
if mode != "no_report":
    (folder / "render_report.json").write_text(json.dumps(report), encoding="utf-8")
'''


@pytest.fixture()
def fake_engine(tmp_path, monkeypatch):
    script = tmp_path / "fake_engine.py"
    script.write_text(FAKE_ENGINE, encoding="utf-8")
    state = {"mode": "ok", "calls": []}

    def command(engine_dir, package, out_dir):
        state["calls"].append((engine_dir, package, out_dir))
        return [sys.executable, str(script), state["mode"], str(package), "--out", str(out_dir)]

    monkeypatch.setattr(PE, "engine_command", command)
    return state


def test_switch_is_off_by_default_and_option_beats_env():
    assert PE.resolve_engine_dir(None, {}) is None
    assert PE.resolve_engine_dir(None, {PE.ENV_VAR: "  "}) is None
    assert PE.resolve_engine_dir(None, {PE.ENV_VAR: "D:/engine"}) == Path("D:/engine")
    assert PE.resolve_engine_dir("D:/cli", {PE.ENV_VAR: "D:/engine"}) == Path("D:/cli")


def test_switch_reads_the_process_environment(monkeypatch):
    monkeypatch.delenv(PE.ENV_VAR, raising=False)
    assert PE.resolve_engine_dir() is None
    monkeypatch.setenv(PE.ENV_VAR, "D:/engine")
    assert PE.resolve_engine_dir() == Path("D:/engine")


def test_engine_command_is_a_uv_subprocess_never_an_import():
    command = PE.engine_command(Path("D:/AutoEdit-v2"), Path("p/film_package.json"), Path("o"))
    assert command == ["uv", "run", "--project", str(Path("D:/AutoEdit-v2")), "post-engine", "render",
                       str(Path("p/film_package.json")), "--out", str(Path("o"))]


def test_mix_fingerprint_changes_only_when_the_engine_is_on(tmp_path, monkeypatch):
    monkeypatch.delenv(PE.ENV_VAR, raising=False)
    monkeypatch.setattr(PE, "engine_revision", lambda engine_dir: "rev1")
    plain = F._fingerprint(tmp_path, "mix")
    monkeypatch.setenv(PE.ENV_VAR, str(tmp_path / "engine"))
    assert F._fingerprint(tmp_path, "mix") != plain
    other = F._fingerprint(tmp_path, "titles")
    monkeypatch.delenv(PE.ENV_VAR)
    assert F._fingerprint(tmp_path, "titles") == other and F._fingerprint(tmp_path, "mix") == plain


def test_picture_name_accepts_only_the_exporter_layout(tmp_path):
    cuts = tmp_path / "media" / "cut"
    stems = tmp_path / "audio" / "stems"
    assert PE.picture_name(tmp_path, cuts / "titled_cut.mp4", stems) == "titled_cut"
    with pytest.raises(ValueError, match="engine mix needs the cut"):
        PE.picture_name(tmp_path, tmp_path / "elsewhere" / "titled_cut.mp4", stems)
    with pytest.raises(ValueError, match="engine mix needs the cut"):
        PE.picture_name(tmp_path, cuts / "other.mp4", stems)
    with pytest.raises(ValueError, match="needs the stems"):
        PE.picture_name(tmp_path, cuts / "titled_cut.mp4", tmp_path / "stems")


def test_mix_info_keeps_only_sourced_sfx():
    built = {"ambience": [{"scene_id": "SC01"}], "music": [{"cue_id": "m"}],
             "sfx": [{"asset": "audio/sfx/a.wav"}, {"asset": ""}]}
    assert PE.mix_info_from(built) == {"ambience": [{"scene_id": "SC01"}], "sfx": [{"asset": "audio/sfx/a.wav"}],
                                       "plan": {"music": [{"cue_id": "m"}]}}


def _package(tmp_path) -> Path:
    path = tmp_path / "pkg" / "film_package.json"
    path.parent.mkdir()
    path.write_text(json.dumps({"film_id": "f1", "source": {"root": str(tmp_path / "src")},
                                "files": [{"id": "picture", "path": "pic.mp4"}], "picture": {"file_id": "picture"}}),
                    encoding="utf-8")
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "pic.mp4").write_bytes(b"picture")
    return path


def test_run_engine_returns_the_final_and_its_report(tmp_path, fake_engine):
    final, report = PE.run_engine(tmp_path / "engine", _package(tmp_path), tmp_path / "out")
    assert final == tmp_path / "out" / "f1" / "final.mp4" and final.read_bytes() == b"picture"
    assert report["passed"] is True and report["measurements"]["integrated_lufs"] == -14.1


def test_run_engine_fails_on_nonzero_exit(tmp_path, fake_engine):
    fake_engine["mode"] = "crash"
    with pytest.raises(ValueError, match=r"post engine exit 3: boom: engine exploded"):
        PE.run_engine(tmp_path / "engine", _package(tmp_path), tmp_path / "out")


def test_run_engine_fails_when_the_report_says_not_passed(tmp_path, fake_engine):
    fake_engine["mode"] = "failed"
    with pytest.raises(ValueError, match=r"passed=false; failed checks: lufs_within_tolerance"):
        PE.run_engine(tmp_path / "engine", _package(tmp_path), tmp_path / "out")


@pytest.mark.parametrize("mode, message", [("no_output", "no final.mp4"), ("no_report", "no render_report.json")])
def test_run_engine_fails_on_missing_output(tmp_path, fake_engine, mode, message):
    fake_engine["mode"] = mode
    with pytest.raises(ValueError, match=message):
        PE.run_engine(tmp_path / "engine", _package(tmp_path), tmp_path / "out")


def test_run_engine_fails_when_the_engine_cannot_start(tmp_path, monkeypatch):
    monkeypatch.setattr(PE, "engine_command", lambda *a: [str(tmp_path / "does_not_exist.exe")])
    with pytest.raises(ValueError, match="could not run"):
        PE.run_engine(tmp_path / "engine", _package(tmp_path), tmp_path / "out")


def test_copy_atomic_replaces_the_target_and_leaves_no_temp(tmp_path):
    source, target = tmp_path / "a.bin", tmp_path / "m" / "mixed.mp4"
    target.parent.mkdir()
    target.write_bytes(b"old")
    source.write_bytes(b"new")
    PE.copy_atomic(source, target)
    assert target.read_bytes() == b"new" and [p.name for p in target.parent.iterdir()] == ["mixed.mp4"]


@pytest.fixture()
def titled(tmp_path):
    """film03 package with a 16 s rendered cut stored as media/cut/titled_cut.mp4 (what finish hands to mix)."""
    root = tmp_path / "film"
    root.mkdir()
    for name in FILES:
        shutil.copyfile(FILM03 / name, root / name)
    clips = tmp_path / "clips"
    clips.mkdir()
    for i, gid in enumerate(GIDS):
        clip = clips / f"{gid}.mp4"
        subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "lavfi", "-i", "color=c=gray:size=320x180:rate=24:duration=3",
                        "-f", "lavfi", "-i", f"sine=frequency={300 + 100 * i}:sample_rate=48000:duration=3",
                        "-af", "volume='if(lt(mod(t,2),1),0.5,0)':eval=frame", "-c:v", "libx264", "-pix_fmt", "yuv420p",
                        "-c:a", "aac", "-shortest", str(clip)], check=True)
        T.register_take(root, "film03_front_desk", gid, clip, prompt_text=f"prompt {gid}", route="r", model="m",
                        credits=12.0)
    section = EditSection(events=[EditEvent(event_id=e, take_id=f"{g}_t1") for e, g in zip("abc", GIDS)])
    (root / "05_edit.json").write_text(section.model_dump_json(indent=2), encoding="utf-8")
    pkg = load_package(root)
    cut = root / "media" / "cut" / "titled_cut.mp4"
    render_cut(pkg, section, cut, clips_dir=clips)
    return pkg, section, cut


@needs_ffmpeg
def test_engine_mix_writes_the_master_and_the_engine_section(titled, fake_engine, tmp_path):
    pkg, section, cut = titled
    root = Path(pkg.root)
    out = root / "media" / "cut" / "mixed.mp4"
    report = M.mix_cut(pkg, section, cut, out, stems_dir=root / "audio" / "stems", engine_dir=tmp_path / "engine")
    assert report["ok"] is True and out.read_bytes() == cut.read_bytes()
    assert report["output_sha256"] == M.sha256_file(out)
    saved = json.loads((root / "audio" / "mix.json").read_text(encoding="utf-8"))
    assert saved["output_sha256"] == M.sha256_file(out)
    engine = saved["engine"]
    assert engine["dir"] == str(tmp_path / "engine") and len(engine["package_sha256"]) == 64
    assert engine["report"] == {"passed": True, "dialogue_leveling": {"gain_db": 1.5},
                                "measurements": {"integrated_lufs": -14.1, "true_peak_dbtp": -1.2,
                                                 "duration_frames": 288,
                                                 "checks": {"lufs_within_tolerance": True, "true_peak_ok": True,
                                                            "duration_within_1_frame": True}}}
    for path in saved["stems"].values():
        assert Path(path).is_file()
    (engine_dir, package, out_dir), = fake_engine["calls"]
    assert root not in Path(package).parents and root not in Path(out_dir).parents
    assert not Path(package).exists()


@needs_ffmpeg
def test_engine_failure_leaves_no_master_and_no_report(titled, fake_engine, tmp_path):
    pkg, section, cut = titled
    root = Path(pkg.root)
    out = root / "media" / "cut" / "mixed.mp4"
    fake_engine["mode"] = "failed"
    with pytest.raises(ValueError, match="failed checks: lufs_within_tolerance"):
        M.mix_cut(pkg, section, cut, out, stems_dir=root / "audio" / "stems", engine_dir=tmp_path / "engine")
    assert not out.exists() and not (root / "audio" / "mix.json").exists()
    assert not list((root / "media" / "cut").glob("*.tmp"))


@needs_ffmpeg
def test_export_layers_come_from_the_fresh_stems_not_a_stale_mix_json(titled, fake_engine, tmp_path, monkeypatch):
    pkg, section, cut = titled
    root = Path(pkg.root)
    stale = root / "audio" / "mix.json"
    stale.parent.mkdir(parents=True, exist_ok=True)
    stale.write_text(json.dumps({"ambience": [], "sfx": []}), encoding="utf-8")
    seen = {}
    real = PE.run_engine

    def spy(engine_dir, package, out_dir):
        seen["package"] = json.loads(Path(package).read_text(encoding="utf-8"))
        return real(engine_dir, package, out_dir)

    monkeypatch.setattr(PE, "run_engine", spy)
    M.mix_cut(pkg, section, cut, root / "media" / "cut" / "mixed.mp4", stems_dir=root / "audio" / "stems",
              engine_dir=tmp_path / "engine")
    assert [layer["id"] for layer in seen["package"]["audio"]["layers"]] == ["ambience"]
    assert "mix_report" not in seen["package"]["references"]
    assert seen["package"]["picture"]["file_id"] == "picture"
