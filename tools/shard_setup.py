"""Create one film07 shard: a git worktree `<parent>/AFP-shard-<n>` on a new branch `film07/shard-<n>`.

    uv run --frozen python tools/shard_setup.py --n 1            # from the AFP-stable checkout; repo = this checkout

What it does, in order (stops at the first failure and leaves nothing half-registered when a precondition fails):
1. refuses when the directory or the branch already exists;
2. `git worktree add -b film07/shard-<n> <dir> HEAD` -- the *committed* tip; uncommitted edits are not carried;
3. copies an untracked `uv.lock` and `<film>/media` (git-ignored: stills, plan prompts, take manifests the reconciler uses to skip known clips);
4. `uv sync --frozen` in the worktree (its own .venv);
5. `tools/film.py status --film <film>` in the worktree must exit 0.

A shard process then sets AFP_FLOW_CDP (its profile's CDP endpoint) and AFP_FLOW_PROJECT (its Flow project id) --
see src/film_pipeline/production/runtime.py. Prints one JSON summary; the status output goes to <dir>/shard_setup.log.
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

DEFAULT_REPO = Path(__file__).resolve().parents[1]
DEFAULT_FILM = "films/film07_first_shift"
SYNC = ["uv", "sync", "--frozen"]
CHECK = ["uv", "run", "--frozen", "python", "tools/film.py", "status", "--film"]


class ShardSetupError(RuntimeError):
    pass


def _git(repo: Path, *args: str) -> str:
    done = subprocess.run(["git", *args], cwd=repo, capture_output=True, text=True)
    if done.returncode != 0:
        raise ShardSetupError(f"git {' '.join(args[:2])} failed: {done.stderr.strip()[:300]}")
    return done.stdout.strip()


def setup_shard(repo: Path, n, *, parent: Path | None = None, film: str = DEFAULT_FILM,
                sync_cmd: list[str] | None = None, check_cmd: list[str] | None = None, resume: bool = False) -> dict:
    if not isinstance(n, int) or isinstance(n, bool) or not 1 <= n <= 99:
        raise ShardSetupError(f"shard number must be an integer 1..99, got {n!r}")
    repo = Path(repo).resolve()
    work = Path(parent or repo.parent).resolve() / f"AFP-shard-{n}"
    branch = f"film07/shard-{n}"
    if resume:   # finish a setup whose sync/check failed: only for this shard's own worktree, nothing is recreated
        if not (work.is_dir() and subprocess.run(["git", "rev-parse", "--abbrev-ref", "HEAD"], cwd=work, capture_output=True,
                                                 text=True).stdout.strip() == branch):
            raise ShardSetupError(f"{work} is not a worktree on branch {branch}")
        base = _git(work, "rev-parse", "HEAD")
        report = {"worktree": str(work), "branch": branch, "base": base, "film": film, "resumed": True}
    else:
        if work.exists():
            raise ShardSetupError(f"{work} already exists")
        if subprocess.run(["git", "rev-parse", "--verify", "-q", f"refs/heads/{branch}"], cwd=repo,
                          capture_output=True).returncode == 0:
            raise ShardSetupError(f"branch {branch} already exists")
        base = _git(repo, "rev-parse", "HEAD")
        _git(repo, "worktree", "add", "-b", branch, str(work), base)
        report = {"worktree": str(work), "branch": branch, "base": base, "film": film}
    media = repo / film / "media"
    if media.is_dir():
        shutil.copytree(media, work / film / "media", ignore=shutil.ignore_patterns("*.tmp"), dirs_exist_ok=True)
        report["media_copied"] = True
    lock = repo / "uv.lock"
    if lock.is_file() and not (work / "uv.lock").exists():   # uv.lock is kept out of git here; --frozen needs it
        shutil.copyfile(lock, work / "uv.lock")
        report["uv_lock_copied"] = True
    env = {k: v for k, v in os.environ.items() if k != "VIRTUAL_ENV"}   # the parent venv must not hijack uv
    env["PYTHONPATH"] = "src"
    log = work / "shard_setup.log"
    sync = subprocess.run(sync_cmd or SYNC, cwd=work, capture_output=True, text=True, env=env)
    if sync.returncode != 0:
        log.write_text(sync.stdout + sync.stderr, encoding="utf-8")
        raise ShardSetupError(f"uv sync failed in {work} (exit {sync.returncode}); see {log}: {(sync.stderr or sync.stdout)[-300:]}")
    check = subprocess.run(check_cmd or CHECK + [film], cwd=work, capture_output=True, text=True, env=env)
    log.write_text(check.stdout + check.stderr, encoding="utf-8")
    if check.returncode != 0:
        raise ShardSetupError(f"status check failed in {work} (exit {check.returncode}); see {log}: "
                              f"{(check.stderr or check.stdout)[-300:]}")
    report["status_check"] = "ok"
    return report


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--n", type=int, required=True, help="shard number (AFP-shard-<n>, branch film07/shard-<n>)")
    ap.add_argument("--repo", type=Path, default=DEFAULT_REPO)
    ap.add_argument("--parent", type=Path, help="directory that receives AFP-shard-<n> (default: the repo's parent)")
    ap.add_argument("--film", default=DEFAULT_FILM, help="film folder relative to the repo")
    ap.add_argument("--resume", action="store_true", help="reuse an existing AFP-shard-<n> worktree on its branch (after a failed sync)")
    args = ap.parse_args(argv)
    try:
        report = setup_shard(args.repo, args.n, parent=args.parent, film=args.film, resume=args.resume)
    except ShardSetupError as exc:
        print(json.dumps({"ok": False, "error": str(exc)}, ensure_ascii=False))
        return 1
    print(json.dumps({"ok": True, **report}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
