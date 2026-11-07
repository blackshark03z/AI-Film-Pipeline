"""P10-05: the rehearsal placeholder reviewer exists only inside a rehearsal package; a rehearsal is never releasable."""
import json
import shutil
import subprocess
from pathlib import Path

import pytest

from film_pipeline.production import deliver as D
from film_pipeline.production import generate as G
from film_pipeline.production import lock as L
from film_pipeline.production import rehearsal as R
from film_pipeline.production import stills as S
from film_pipeline.production import takes as T
from film_pipeline.production.package import load_package
from film_pipeline.production.plan import plan_package

ROOT = Path(__file__).resolve().parents[1]
FILM03 = ROOT / "films" / "film03_front_desk"
FILES = ("film.json", "script.fountain", "01_story.json", "02_direction.json", "03_preprod.json", "04_shots.json")
GID = "SC01_g1"


def make(tmp_path, rehearsal=False):
    root = tmp_path / ("rh" if rehearsal else "film")
    root.mkdir(parents=True)
    for name in FILES:
        (root / name).write_text((FILM03 / name).read_text(encoding="utf-8"), encoding="utf-8")
    header = json.loads((root / "film.json").read_text(encoding="utf-8"))
    if rehearsal:
        header["rehearsal"] = True
    (root / "film.json").write_text(json.dumps(header), encoding="utf-8")
    pkg = load_package(root)
    plan_package(pkg, root / "media" / "plan", approve_storyboard="owner")
    return load_package(root)


def png(tmp_path):
    from PIL import Image
    path = tmp_path / "frame.png"
    Image.new("RGB", (64, 36), (30, 60, 90)).save(path)
    return path


def registered(pkg, tmp_path, gid=GID):
    """Register a still and reload the package (the typed preprod section is read at load time)."""
    S.register_still(pkg, gid, png(tmp_path), source="test")
    return load_package(pkg.root)


def test_flag_defaults_to_false_and_reads_film_json(tmp_path):
    assert not R.is_rehearsal(tmp_path / "missing")
    assert not R.is_rehearsal(make(tmp_path).root)
    assert R.is_rehearsal(make(tmp_path, True).root)


def test_bot_name_is_refused_in_a_real_package(tmp_path):
    pkg = make(tmp_path)
    with pytest.raises(ValueError, match="REHEARSAL-BOT"):
        R.refuse_bot(pkg.root, "human:rehearsal-bot")
    R.refuse_bot(pkg.root, "human:Alice")  # a real name is fine


def test_bot_cannot_approve_a_still_or_lock_in_a_real_package(tmp_path):
    pkg = registered(make(tmp_path), tmp_path)
    with pytest.raises(ValueError, match="REHEARSAL-BOT"):
        S.approve_still(pkg, GID, R.BOT)
    with pytest.raises(ValueError, match="REHEARSAL-BOT"):
        L.lock_picture(pkg, R.BOT)
    with pytest.raises(ValueError, match="REHEARSAL-BOT"):
        plan_package(pkg, pkg.root / "out", approve_storyboard=R.BOT)
    assert S.approve_still(pkg, GID, "Alice")["approved_by"] == "Alice"


def test_bot_may_approve_a_still_in_a_rehearsal(tmp_path):
    pkg = registered(make(tmp_path, True), tmp_path)
    assert S.approve_still(pkg, GID, R.BOT)["approved_by"] == R.BOT


def test_bot_review_is_refused_in_a_real_package(tmp_path):
    pkg = make(tmp_path)
    clip = pkg.root / "media" / "takes" / "SC01_g1_t1.mp4"
    clip.parent.mkdir(parents=True)
    clip.write_bytes(b"clip")
    entry, _ = T.register_take(pkg.root, pkg.header.film_id, GID, clip, prompt_text="p", route="r", model="m", credits=0.0)
    sheet = R._review_sheet(pkg.root, pkg.header.film_id, entry.take_id, GID)
    with pytest.raises(ValueError, match="REHEARSAL-BOT"):
        T.ingest_review(pkg.root, pkg.header.film_id, sheet)
    shutil.copy(pkg.root / "film.json", tmp_path / "film.bak")
    header = json.loads((pkg.root / "film.json").read_text(encoding="utf-8"))
    header["rehearsal"] = True
    (pkg.root / "film.json").write_text(json.dumps(header), encoding="utf-8")
    assert T.ingest_review(pkg.root, pkg.header.film_id, sheet)["status"] == "ACCEPTED"


def test_rehearsal_cannot_be_accepted(tmp_path):
    pkg = make(tmp_path, True)
    with pytest.raises(ValueError, match="rehearsal"):
        D.accept_delivery(pkg, "Owner")
    with pytest.raises(ValueError, match="REHEARSAL-BOT"):
        D.accept_delivery(make(tmp_path), R.BOT)


def test_mock_runner_needs_a_rehearsal_to_skip_go_live(tmp_path):
    runner_calls = []

    def runner(argv, out):
        runner_calls.append(argv)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_bytes(b"fake")
        return {"result": "PASSED"}

    backlog = tmp_path / "backlog.md"
    backlog.write_text("OWNER_GO_LIVE: NO\n", encoding="utf-8")
    real = registered(make(tmp_path), tmp_path)
    S.approve_still(real, GID, "Alice")
    real = load_package(real.root)
    refused = G.generate(real, GID, dry_run=False, start_token="tok:x", backlog=backlog, runner=runner)
    assert not refused["sent"] and any(r["code"] == "OWNER_GO_LIVE_NO" for r in refused["refused"])
    assert runner_calls == []
    rh = registered(make(tmp_path, True), tmp_path)
    S.approve_still(rh, GID, R.BOT)
    rh = load_package(rh.root)
    sent = G.generate(rh, GID, dry_run=False, start_token="tok:x", backlog=backlog, runner=runner)
    assert sent["sent"] and sent["take"]["credits"] == 0.0 and len(runner_calls) == 1
    # without an explicit runner a rehearsal package still needs the Owner's go-live (the real sender is never reached)
    again = G.generate(rh, "SC01_g2", dry_run=False, start_token="tok:x", backlog=backlog)
    assert not again["sent"]


def test_rehearse_refuses_a_dirty_or_overlapping_directory(tmp_path):
    src = tmp_path / "src"
    src.mkdir()
    (src / "film.json").write_text("{}", encoding="utf-8")
    busy = tmp_path / "busy"
    busy.mkdir()
    (busy / "x").write_text("x", encoding="utf-8")
    with pytest.raises(ValueError, match="not empty"):
        R.rehearse(src, busy)
    with pytest.raises(ValueError, match="separate"):
        R.rehearse(src, src / "inside")


@pytest.mark.skipif(shutil.which("ffmpeg") is None, reason="needs ffmpeg")
def test_mock_runner_writes_a_clip_and_manifest(tmp_path):
    out = tmp_path / "take.mp4"
    manifest = R.mock_runner(["x", "p.txt", str(out), "--start-file", str(png(tmp_path))], out)
    assert manifest["result"] == "PASSED" and manifest["returncode"] == 0 and manifest["mock"]
    body = json.loads(out.with_suffix(".take.json").read_text(encoding="utf-8"))
    assert body["sha256"] == manifest["sha256"] and body["note"] == R.STAMP
    probe = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(out)],
                           capture_output=True, text=True, check=True)
    assert 7.9 < float(probe.stdout) < 8.2


def test_restore_check_is_not_run_without_a_delivery_archive(tmp_path):
    log = R._Log(tmp_path)
    assert R.restore_check(log, tmp_path) is False
    assert log.restore["ok"] is None and "no delivery archive" in log.restore["detail"] and log.steps == []


def test_restore_check_verifies_a_copy_of_the_archive_and_catches_a_damaged_one(tmp_path):
    """P11-08: the archive is copied elsewhere and checked there; the report carries the result."""
    from test_production_deliver import deliver, pipeline
    if not (shutil.which("ffmpeg") and shutil.which("ffprobe")):
        pytest.skip("ffmpeg not installed")
    root, report = pipeline(tmp_path)
    done, body = deliver(root, report)
    assert done.returncode == 0 and body["ok"], body
    log = R._Log(root)
    assert R.restore_check(log, root) is True
    assert log.restore["ok"] is True and log.restore["files"] > 5 and log.restore["film_id"]
    assert [s["step"] for s in log.steps] == ["restore"] and log.steps[0]["ok"]
    assert str(root) not in json.dumps(log.restore)               # the copy lived somewhere else
    master = next((root / "delivery" / "masters").glob("*_16x9.mp4"))
    with master.open("ab") as handle:
        handle.write(b"\0")                                        # the archive no longer matches its manifest
    log = R._Log(root)
    assert R.restore_check(log, root) is False
    assert log.restore["ok"] is False and log.restore["detail"] and not log.steps[0]["ok"]
