import json
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

from film_pipeline.production import lock as L
from film_pipeline.production import takes as T
from film_pipeline.production.edit import EditEvent, EditSection, Transition
from film_pipeline.production.gates import evaluate_gate
from film_pipeline.production.package import load_package

ROOT = Path(__file__).resolve().parents[1]
FILM03 = ROOT / "films" / "film03_front_desk"
TOOL = ROOT / "tools" / "film.py"
FILES = ("film.json", "script.fountain", "01_story.json", "02_direction.json", "03_preprod.json", "04_shots.json")
needs_ffmpeg = pytest.mark.skipif(not (shutil.which("ffmpeg") and shutil.which("ffprobe")), reason="ffmpeg not installed")


def make_clip(path: Path, seconds: float, freq: int) -> Path:
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "lavfi", "-i", f"testsrc2=size=320x180:rate=24:duration={seconds}",
                    "-f", "lavfi", "-i", f"sine=frequency={freq}:duration={seconds}:sample_rate=48000",
                    "-c:v", "libx264", "-pix_fmt", "yuv420p", "-c:a", "aac", "-shortest", str(path)], check=True)
    return path


def ev(event_id, gid, **kw):
    return EditEvent(event_id=event_id, take_id=f"{gid}_t1", **kw)


@pytest.fixture()
def film(tmp_path):
    """film03 package with three accepted synthetic takes and a three-event cut a, b, c."""
    root = tmp_path / "film"
    root.mkdir()
    for name in FILES:
        shutil.copyfile(FILM03 / name, root / name)
    clips = tmp_path / "clips"
    clips.mkdir()
    for index, gid in enumerate(("SC01_g1", "SC01_g2", "SC02_g1")):
        T.register_take(root, "film03_front_desk", gid, make_clip(clips / f"{gid}.mp4", 3.0, 300 + 100 * index),
                        prompt_text=f"prompt {gid}", route="r", model="m", credits=12.0)
    log = T.load_log(root, "film03_front_desk")
    T.save_log(root, log.model_copy(update={"takes": [t.model_copy(update={"status": "ACCEPTED"}) for t in log.takes]}))
    write_edl(root, EditSection(events=[ev("a", "SC01_g1"), ev("b", "SC01_g2"), ev("c", "SC02_g1")]))
    return root, clips


def write_edl(root: Path, section: EditSection) -> None:
    (root / "05_edit.json").write_text(section.model_dump_json(indent=2), encoding="utf-8")


def write_post(root: Path, items: dict) -> None:
    (root / "06_post.json").write_text(json.dumps(items), encoding="utf-8")


def reload(root):
    return load_package(root)


@needs_ffmpeg
def test_lock_needs_a_name_accepted_takes_and_an_edl(film, tmp_path):
    root, clips = film
    with pytest.raises(ValueError, match="locked_by"):
        L.lock_picture(reload(root), " ", clips_dir=clips)
    log = T.load_log(root, "film03_front_desk")
    T.save_log(root, log.model_copy(update={"takes": [log.takes[0].model_copy(update={"status": "GENERATED"}), *log.takes[1:]]}))
    with pytest.raises(ValueError, match="TAKE_NOT_ACCEPTED a"):
        L.lock_picture(reload(root), "Owner", clips_dir=clips)
    (root / "05_edit.json").unlink()
    with pytest.raises(ValueError, match="no valid 05_edit.json"):
        L.lock_picture(reload(root), "Owner", clips_dir=clips)


@needs_ffmpeg
def test_lock_records_the_cut_and_keeps_every_lock(film):
    root, clips = film
    record = L.lock_picture(reload(root), "Owner", "picture approved", clips_dir=clips)
    assert record["locked_by"] == "Owner" and [e["event_id"] for e in record["events"]] == ["a", "b", "c"]
    assert (root / "lock" / "picture.lock.json").is_file()
    assert (root / "lock" / "history" / f"{record['edl_sha256']}.json").is_file()
    status = L.lock_status(reload(root))
    assert status["locked"] and status["fresh"] and status["changed_events"] == []


@needs_ffmpeg
def test_gate_5_follows_the_lock(film):
    root, clips = film
    gate = lambda: evaluate_gate(reload(root), "5")  # noqa: E731
    assert gate().status == "BLOCK" and "not locked" in gate().issues[0]
    L.lock_picture(reload(root), "Owner", clips_dir=clips)
    assert gate().status == "PASS"
    write_edl(root, EditSection(events=[ev("a", "SC01_g1"), ev("b", "SC01_g2", src_out_s=2.0), ev("c", "SC02_g1")]))
    result = gate()
    assert result.status == "BLOCK" and "b, c" in result.issues[0] and "relock" in result.issues[0]


@needs_ffmpeg
def test_changing_one_src_out_flags_subtitles_mix_and_master_qc_dirty(film):
    root, clips = film
    lock = L.lock_picture(reload(root), "Owner", clips_dir=clips)
    stamp = lock["edl_sha256"]
    write_post(root, {"subtitles": {"locked_against": stamp}, "mix": {"locked_against": stamp},
                      "master_qc": {"locked_against": stamp},
                      "opening_grade": {"locked_against": stamp, "events": ["a"]},
                      "ending_grade": {"locked_against": stamp, "events": ["c"]},
                      "scratch": "not an item"})
    assert L.dirty_items(reload(root))["dirty"] == []
    write_edl(root, EditSection(events=[ev("a", "SC01_g1"), ev("b", "SC01_g2", src_out_s=2.0), ev("c", "SC02_g1")]))
    report = L.dirty_items(reload(root))
    assert {d["item"] for d in report["dirty"]} == {"subtitles", "mix", "master_qc", "ending_grade"}
    assert [c["item"] for c in report["clean"]] == ["opening_grade"]   # before the change: untouched
    assert all(d["reason"].startswith("CUT_CHANGED: b, c") for d in report["dirty"] if d["item"] != "ending_grade")
    assert next(d for d in report["dirty"] if d["item"] == "ending_grade")["events"] == ["c"]  # shifted by the change


@needs_ffmpeg
def test_unstamped_and_unknown_stamps_are_dirty(film):
    root, clips = film
    L.lock_picture(reload(root), "Owner", clips_dir=clips)
    write_post(root, {"a": {}, "b": {"locked_against": "f" * 64}})
    delivery = {"master": {"locked_against": ""}}
    (root / "07_delivery.json").write_text(json.dumps(delivery), encoding="utf-8")
    reasons = {(d["stage"], d["item"]): d["reason"].split(":")[0] for d in L.dirty_items(reload(root))["dirty"]}
    assert reasons == {("post", "a"): "UNSTAMPED", ("post", "b"): "UNKNOWN_LOCK", ("delivery", "master"): "UNSTAMPED"}


@needs_ffmpeg
def test_relock_records_what_it_supersedes_and_old_stamps_stay_comparable(film):
    root, clips = film
    first = L.lock_picture(reload(root), "Owner", clips_dir=clips)
    write_edl(root, EditSection(events=[ev("a", "SC01_g1"), ev("b", "SC01_g2"), ev("c", "SC02_g1", src_out_s=2.5)]))
    second = L.lock_picture(reload(root), "Owner", "trimmed the last shot", clips_dir=clips)
    assert second["supersedes"] == first["edl_sha256"] and second["changed_events"] == ["c"]
    assert (root / "lock" / "history" / f"{first['edl_sha256']}.json").is_file()
    write_post(root, {"mix": {"locked_against": first["edl_sha256"]}, "titles": {"locked_against": second["edl_sha256"]},
                      "intro": {"locked_against": first["edl_sha256"], "events": ["a"]}})
    report = L.dirty_items(reload(root))
    assert [d["item"] for d in report["dirty"]] == ["mix"] and {c["item"] for c in report["clean"]} == {"titles", "intro"}
    assert L.lock_status(reload(root))["fresh"]


@needs_ffmpeg
def test_a_take_whose_bytes_or_review_changed_after_the_lock_breaks_it(film):
    root, clips = film
    L.lock_picture(reload(root), "Owner", clips_dir=clips)
    log = T.load_log(root, "film03_front_desk")
    T.save_log(root, log.model_copy(update={"takes": [log.takes[0], log.takes[1].model_copy(update={"status": "REJECTED"}),
                                                      log.takes[2]]}))
    status = L.lock_status(reload(root))
    assert not status["fresh"] and status["changed_events"] == ["b", "c"]
    T.save_log(root, log.model_copy(update={"takes": [log.takes[0], log.takes[1],
                                                      log.takes[2].model_copy(update={"output_sha256": "e" * 64})]}))
    status = L.lock_status(reload(root))
    assert not status["fresh"] and status["changed_events"] == ["c"]


@needs_ffmpeg
def test_frame_or_structure_changes_affect_the_right_events(film):
    root, clips = film
    L.lock_picture(reload(root), "Owner", clips_dir=clips)
    events = [ev("a", "SC01_g1"), ev("b", "SC01_g2"), ev("c", "SC02_g1")]
    write_edl(root, EditSection(events=events, title_s=5.0))
    assert L.lock_status(reload(root))["changed_events"] == ["a", "b", "c"]          # everything moves on the clock
    write_edl(root, EditSection(events=events[:2]))
    assert L.lock_status(reload(root))["changed_events"] == ["c"]                    # removed at the end
    write_edl(root, EditSection(events=[events[0], ev("d", "SC02_g1", transition=Transition(type="DISSOLVE", duration_s=0.5)),
                                        *events[1:]]))
    assert L.lock_status(reload(root))["changed_events"] == ["d", "b", "c"]          # inserted in the middle


@needs_ffmpeg
def test_cli_lock_status_and_lock(film):
    root, clips = film

    def run(*args):
        return subprocess.run([sys.executable, str(TOOL), "lock", "--film", str(root), *args], capture_output=True,
                              text=True, cwd=ROOT)

    first = run()
    assert first.returncode == 1 and json.loads(first.stdout)["status"]["locked"] is False
    refused = run("--lock", "--clips", str(clips))
    assert refused.returncode == 1 and "locked_by" in json.loads(refused.stdout)["error"]
    done = run("--lock", "--by", "Owner", "--clips", str(clips))
    assert done.returncode == 0 and json.loads(done.stdout)["locked"]["locked_by"] == "Owner"
    again = run()
    assert again.returncode == 0 and json.loads(again.stdout)["status"]["fresh"]
