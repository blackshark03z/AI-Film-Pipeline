"""Shard parallelism step 3: `film.py takes --merge-from <ref>` unions a shard branch's take results."""
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

from film_pipeline.production import shard_merge as SM

ROOT = Path(__file__).resolve().parents[1]
FILM03 = ROOT / "films" / "film03_front_desk"
TOOL = ROOT / "tools" / "film.py"
FILES = ("film.json", "script.fountain", "01_story.json", "02_direction.json", "03_preprod.json", "04_shots.json")
REL = "films/filmx"
GIT_ENV = dict(os.environ, GIT_AUTHOR_NAME="t", GIT_AUTHOR_EMAIL="t@example.invalid", GIT_COMMITTER_NAME="t",
               GIT_COMMITTER_EMAIL="t@example.invalid")


def git(repo, *args):
    done = subprocess.run(["git", "-c", "commit.gpgsign=false", "-c", "core.autocrlf=false", *args], cwd=repo,
                          capture_output=True, text=True, env=GIT_ENV, check=True)
    return done.stdout.strip()


def entry(take_id, **over):
    gid, n = take_id.rsplit("_t", 1)
    base = {"take_id": take_id, "generation_id": gid, "prompt_sha256": "a" * 64, "start_frame_sha256": "",
            "route": "start_frame+Khung hinh", "model": "Omni 1.2 Flash 360p", "credits": 6.0,
            "output_file": f"{take_id}.mp4", "output_sha256": "b" * 64, "status": "GENERATED", "shot_version": 1,
            "cause": "", "registered_at": "2026-11-12T10:00:00+00:00"}
    base.update(over)
    return base


def line(take_id, at, **over):
    return json.dumps({"at": at, "take_id": take_id, "result": "PASSED", **over})


def write_state(root, takes, log_lines, film_id="filmx"):
    d = Path(root) / "takes"
    d.mkdir(parents=True, exist_ok=True)
    (d / "index.json").write_text(json.dumps({"film_id": film_id, "takes": takes}, indent=2) + "\n", encoding="utf-8")
    (d / "send_log.jsonl").write_text("".join(x + "\n" for x in log_lines), encoding="utf-8")


def commit(repo, msg="c"):
    git(repo, "add", "-A")
    git(repo, "commit", "-q", "-m", msg)


@pytest.fixture()
def repo(tmp_path):
    r = tmp_path / "repo"
    (r / REL).mkdir(parents=True)
    git(r, "init", "-q", "-b", "main")
    (r / REL / "04_shots.json").write_text('{"generations": [1]}\n', encoding="utf-8")
    write_state(r / REL, [entry("SC01_g01_t1", status="ACCEPTED")], [line("SC01_g01_t1", "2026-11-12T09:00:00+00:00")])
    commit(r, "base")
    return r


def branch(repo, name, takes, lines, shots=None):
    git(repo, "checkout", "-q", "-b", name, "main")
    write_state(repo / REL, [entry("SC01_g01_t1", status="ACCEPTED"), *takes],
                [line("SC01_g01_t1", "2026-11-12T09:00:00+00:00"), *lines])
    if shots is not None:
        (repo / REL / "04_shots.json").write_text(shots, encoding="utf-8")
    commit(repo, name)
    git(repo, "checkout", "-q", "main")


def read_index(repo):
    return json.loads((repo / REL / "takes/index.json").read_text(encoding="utf-8"))["takes"]


def read_log(repo):
    return (repo / REL / "takes/send_log.jsonl").read_text(encoding="utf-8").splitlines()


def test_takes_of_two_shards_are_unioned_and_the_send_log_is_ordered_by_time(repo):
    branch(repo, "s1", [entry("SC05_g01_t1")], [line("SC05_g01_t1", "2026-11-12T12:00:00+00:00")])
    branch(repo, "s2", [entry("SC09_g01_t1")], [line("SC09_g01_t1", "2026-11-12T11:00:00+00:00")])
    SM.merge_shard_takes(repo / REL, "s1")
    report = SM.merge_shard_takes(repo / REL, "s2")
    assert [t["take_id"] for t in read_index(repo)] == ["SC01_g01_t1", "SC05_g01_t1", "SC09_g01_t1"]
    assert [json.loads(x)["take_id"] for x in read_log(repo)] == ["SC01_g01_t1", "SC09_g01_t1", "SC05_g01_t1"]
    assert report["takes_added"] == ["SC09_g01_t1"] and report["send_log_lines_added"] == 1 and not report["conflicts"]


def test_merging_twice_is_idempotent(repo):
    branch(repo, "s1", [entry("SC05_g01_t1")], [line("SC05_g01_t1", "2026-11-12T12:00:00+00:00")])
    SM.merge_shard_takes(repo / REL, "s1")
    before = (read_index(repo), read_log(repo))
    report = SM.merge_shard_takes(repo / REL, "s1")
    assert (read_index(repo), read_log(repo)) == before and report["takes_added"] == [] and report["send_log_lines_added"] == 0


def test_same_take_id_with_different_content_is_a_hard_error_and_writes_nothing(repo):
    branch(repo, "s1", [entry("SC05_g01_t1", status="ACCEPTED")], [line("SC05_g01_t1", "2026-11-12T12:00:00+00:00")])
    write_state(repo / REL, [entry("SC01_g01_t1", status="ACCEPTED"), entry("SC05_g01_t1", status="REJECTED")],
                [line("SC01_g01_t1", "2026-11-12T09:00:00+00:00")])
    before = ((repo / REL / "takes/index.json").read_bytes(), (repo / REL / "takes/send_log.jsonl").read_bytes())
    with pytest.raises(SM.ShardMergeError, match="SC05_g01_t1"):
        SM.merge_shard_takes(repo / REL, "s1")
    assert ((repo / REL / "takes/index.json").read_bytes(), (repo / REL / "takes/send_log.jsonl").read_bytes()) == before


def test_send_log_lines_are_deduplicated_exactly_and_kept_in_order(repo):
    same = line("SC05_g01_t1", "2026-11-12T12:00:00+00:00")
    branch(repo, "s1", [entry("SC05_g01_t1")], [same, line("SC05_g01_t2", "2026-11-12T12:30:00+00:00")])
    write_state(repo / REL, [entry("SC01_g01_t1", status="ACCEPTED"), entry("SC05_g01_t1")],
                [line("SC01_g01_t1", "2026-11-12T09:00:00+00:00"), same])
    report = SM.merge_shard_takes(repo / REL, "s1")
    assert read_log(repo).count(same) == 1 and report["send_log_lines_added"] == 1
    assert [json.loads(x)["at"] for x in read_log(repo)] == sorted(json.loads(x)["at"] for x in read_log(repo))


def test_a_ref_without_takes_is_a_no_op(repo):
    git(repo, "checkout", "-q", "-b", "empty", "main")
    git(repo, "rm", "-q", "-r", f"{REL}/takes")
    commit(repo, "no takes")
    git(repo, "checkout", "-q", "main")
    report = SM.merge_shard_takes(repo / REL, "empty")
    assert report["takes_added"] == [] and [t["take_id"] for t in read_index(repo)] == ["SC01_g01_t1"]


def test_a_shard_of_another_film_is_refused(repo):
    git(repo, "checkout", "-q", "-b", "other", "main")
    write_state(repo / REL, [entry("SC01_g01_t1", status="ACCEPTED")], [], film_id="film_other")
    commit(repo, "other")
    git(repo, "checkout", "-q", "main")
    with pytest.raises(SM.ShardMergeError, match="film"):
        SM.merge_shard_takes(repo / REL, "other")


def test_a_conflicted_worktree_falls_back_to_head_for_our_side(repo):
    branch(repo, "s1", [entry("SC05_g01_t1")], [line("SC05_g01_t1", "2026-11-12T12:00:00+00:00")])
    (repo / REL / "takes/index.json").write_text("<<<<<<< HEAD\n{}\n=======\n{}\n>>>>>>> s1\n", encoding="utf-8")
    (repo / REL / "takes/send_log.jsonl").write_text("<<<<<<< HEAD\n=======\n>>>>>>> s1\n", encoding="utf-8")
    report = SM.merge_shard_takes(repo / REL, "s1")
    assert report["ours_source"] == "HEAD"
    assert [t["take_id"] for t in read_index(repo)] == ["SC01_g01_t1", "SC05_g01_t1"]
    assert all("<<<<" not in x for x in read_log(repo))


@pytest.mark.parametrize("ours, theirs, expected", [
    (None, None, "same"),
    (None, '{"generations": [1, 2]}\n', "theirs_changed"),
    ('{"generations": [1, 3]}\n', None, "ours_changed"),
    ('{"generations": [1, 3]}\n', '{"generations": [1, 2]}\n', "CONFLICT"),
    ('{"generations": [1, 2]}\n', '{"generations": [1, 2]}\n', "same"),
])
def test_shots_changes_are_reported_never_resolved(repo, ours, theirs, expected):
    branch(repo, "s1", [entry("SC05_g01_t1")], [], shots=theirs)
    if ours is not None:
        (repo / REL / "04_shots.json").write_text(ours, encoding="utf-8")
        commit(repo, "ours edit")
    before = (repo / REL / "04_shots.json").read_bytes()
    report = SM.merge_shard_takes(repo / REL, "s1")
    assert report["shots"] == expected and (repo / REL / "04_shots.json").read_bytes() == before
    assert report["conflicts"] == (["04_shots.json"] if expected == "CONFLICT" else [])


def test_cli_merge_from_reports_a_shots_conflict_with_a_nonzero_exit(tmp_path):
    r = tmp_path / "repo"
    film = r / "films" / "filmx"
    film.mkdir(parents=True)
    for name in FILES:
        shutil.copyfile(FILM03 / name, film / name)
    film_id = json.loads((film / "film.json").read_text(encoding="utf-8"))["film_id"]
    git(r, "init", "-q", "-b", "main")
    write_state(film, [], [], film_id=film_id)
    commit(r, "base")
    git(r, "checkout", "-q", "-b", "s1")
    write_state(film, [entry("SC05_g01_t1")], [line("SC05_g01_t1", "2026-11-12T12:00:00+00:00")], film_id=film_id)
    (film / "04_shots.json").write_text((film / "04_shots.json").read_text(encoding="utf-8") + "\n", encoding="utf-8")
    commit(r, "shard")
    git(r, "checkout", "-q", "main")
    (film / "04_shots.json").write_text((film / "04_shots.json").read_text(encoding="utf-8") + "\n\n", encoding="utf-8")
    commit(r, "ours")
    env = dict(os.environ, PYTHONPATH=str(ROOT / "src"), LOCALAPPDATA=str(tmp_path / "la"))
    done = subprocess.run([sys.executable, str(TOOL), "takes", "--film", str(film), "--merge-from", "s1"],
                          capture_output=True, text=True, env=env, timeout=60)
    out = json.loads(done.stdout)
    assert done.returncode == 1 and out["conflicts"] == ["04_shots.json"] and out["takes_added"] == ["SC05_g01_t1"]
