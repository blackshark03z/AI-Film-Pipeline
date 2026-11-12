"""Shard parallelism step 4: tools/shard_setup.py builds one worktree + branch per shard (fake sync/check commands here)."""
import importlib.util
import os
import subprocess
import sys
from pathlib import Path

import pytest

TOOL = Path(__file__).resolve().parents[1] / "tools" / "shard_setup.py"
spec = importlib.util.spec_from_file_location("shard_setup", TOOL)
SS = importlib.util.module_from_spec(spec)
spec.loader.exec_module(SS)

GIT_ENV = dict(os.environ, GIT_AUTHOR_NAME="t", GIT_AUTHOR_EMAIL="t@example.invalid", GIT_COMMITTER_NAME="t",
               GIT_COMMITTER_EMAIL="t@example.invalid")
OK = [sys.executable, "-c", "import pathlib; pathlib.Path('sync.done').write_text('x')"]
PASS = [sys.executable, "-c", "print('status ok')"]
FAIL = [sys.executable, "-c", "import sys; print('boom'); sys.exit(3)"]


def git(repo, *args):
    return subprocess.run(["git", "-c", "commit.gpgsign=false", *args], cwd=repo, capture_output=True, text=True,
                          env=GIT_ENV, check=True).stdout.strip()


@pytest.fixture()
def repo(tmp_path):
    r = tmp_path / "AFP-stable"
    (r / "films" / "filmx").mkdir(parents=True)
    git(r, "init", "-q", "-b", "main")
    (r / "films" / "filmx" / "film.json").write_text("{}", encoding="utf-8")
    (r / ".gitignore").write_text("films/*/media/\n", encoding="utf-8")
    git(r, "add", "-A")
    git(r, "commit", "-q", "-m", "base")
    (r / "films" / "filmx" / "media" / "stills").mkdir(parents=True)
    (r / "films" / "filmx" / "media" / "stills" / "a.png").write_bytes(b"png")
    return r


def setup(repo, n=1, **kw):
    return SS.setup_shard(repo, n, parent=repo.parent, film="films/filmx", sync_cmd=OK, check_cmd=PASS, **kw)


def test_creates_worktree_branch_from_the_current_tip_and_copies_the_ignored_media(repo):
    tip = git(repo, "rev-parse", "HEAD")
    report = setup(repo, 3)
    work = repo.parent / "AFP-shard-3"
    assert report["worktree"] == str(work) and report["branch"] == "film07/shard-3" and report["base"] == tip
    assert git(work, "rev-parse", "HEAD") == tip and git(work, "branch", "--show-current") == "film07/shard-3"
    assert (work / "sync.done").is_file()                                   # sync ran inside the worktree
    assert (work / "films/filmx/media/stills/a.png").read_bytes() == b"png"  # media is git-ignored, so it is copied
    assert report["status_check"] == "ok"


def test_uncommitted_changes_are_not_carried(repo):
    (repo / "films/filmx/film.json").write_text('{"dirty": true}', encoding="utf-8")
    setup(repo, 1)
    assert (repo.parent / "AFP-shard-1/films/filmx/film.json").read_text(encoding="utf-8") == "{}"


def test_existing_directory_or_branch_is_refused_without_touching_anything(repo):
    setup(repo, 1)
    with pytest.raises(SS.ShardSetupError, match="exists"):
        setup(repo, 1)
    git(repo, "branch", "film07/shard-2")
    with pytest.raises(SS.ShardSetupError, match="branch"):
        setup(repo, 2)
    assert not (repo.parent / "AFP-shard-2").exists()


def test_a_failing_status_check_fails_the_setup_and_names_the_log(repo):
    with pytest.raises(SS.ShardSetupError, match="status check failed") as err:
        SS.setup_shard(repo, 4, parent=repo.parent, film="films/filmx", sync_cmd=OK, check_cmd=FAIL)
    assert "boom" in str(err.value)


def test_a_failing_sync_fails_the_setup(repo):
    with pytest.raises(SS.ShardSetupError, match="sync failed"):
        SS.setup_shard(repo, 5, parent=repo.parent, film="films/filmx", sync_cmd=FAIL, check_cmd=PASS)


def test_shard_number_must_be_a_small_positive_integer(repo):
    for bad in (0, -1, 100, "a"):
        with pytest.raises(SS.ShardSetupError, match="shard number"):
            setup(repo, bad)


def test_untracked_uv_lock_is_copied_so_that_sync_frozen_works(repo):
    (repo / "uv.lock").write_text("lock", encoding="utf-8")        # uv.lock is deliberately not committed
    report = setup(repo, 6)
    assert (repo.parent / "AFP-shard-6/uv.lock").read_text(encoding="utf-8") == "lock" and report["uv_lock_copied"]


def test_the_parent_virtualenv_is_not_leaked_into_the_shard_commands(repo, monkeypatch):
    monkeypatch.setenv("VIRTUAL_ENV", "C:/somewhere/else/.venv")
    show = [sys.executable, "-c", "import os, sys; sys.exit(7 if 'VIRTUAL_ENV' in os.environ else 0)"]
    SS.setup_shard(repo, 7, parent=repo.parent, film="films/filmx", sync_cmd=show, check_cmd=show)


def test_resume_finishes_a_worktree_whose_sync_failed_and_keeps_its_commits(repo):
    with pytest.raises(SS.ShardSetupError, match="sync failed"):
        SS.setup_shard(repo, 8, parent=repo.parent, film="films/filmx", sync_cmd=FAIL, check_cmd=PASS)
    work = repo.parent / "AFP-shard-8"
    with pytest.raises(SS.ShardSetupError, match="exists"):
        setup(repo, 8)                                                # without --resume nothing is reused
    report = setup(repo, 8, resume=True)
    assert report["resumed"] and report["status_check"] == "ok" and (work / "sync.done").is_file()


def test_resume_refuses_a_directory_that_is_not_that_shards_worktree(repo):
    (repo.parent / "AFP-shard-9").mkdir()
    with pytest.raises(SS.ShardSetupError, match="not a worktree"):
        setup(repo, 9, resume=True)

