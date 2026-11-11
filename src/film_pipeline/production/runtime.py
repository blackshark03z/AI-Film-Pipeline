"""Small shared boundaries for durable package writes and exclusive production operations."""
from __future__ import annotations

import hashlib
import asyncio
import json
import os
import tempfile
import threading
from contextlib import contextmanager, ExitStack
from concurrent.futures import ThreadPoolExecutor
from functools import wraps
from pathlib import Path

_local = threading.local()


def run_async(factory, *, timeout=None):
    """Keep native UI control in the lock-owning process, including async API callers."""
    async def invoke():
        return await factory() if timeout is None else await asyncio.wait_for(factory(), timeout)
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        return asyncio.run(invoke())
    with ThreadPoolExecutor(max_workers=1) as pool:
        return pool.submit(lambda: asyncio.run(invoke())).result()


class WriterBusy(ValueError):
    pass


def atomic_text(path: Path, value: str) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, name = tempfile.mkstemp(prefix=path.name + ".", suffix=".tmp", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as handle:
            handle.write(value)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(name, path)
    finally:
        Path(name).unlink(missing_ok=True)


def atomic_json(path: Path, value) -> None:
    atomic_text(path, json.dumps(value, ensure_ascii=False, indent=2) + "\n")


@contextmanager
def _exclusive(key: str):
    held = getattr(_local, "held", None)
    if held is None:
        held = _local.held = set()
    if key in held:
        yield
        return
    # Independent of TEMP/TMP: separate invocations must resolve the same lock directory.
    base = Path(os.environ.get("LOCALAPPDATA", str(Path.home() / ".cache"))) / "AI-Film-Pipeline" / "locks"
    base.mkdir(parents=True, exist_ok=True)
    path = base / (hashlib.sha256(key.encode()).hexdigest() + ".lock")
    with path.open("a+b") as handle:
        if path.stat().st_size == 0:
            handle.write(b"0")
            handle.flush()
        handle.seek(0)
        try:
            if os.name == "nt":
                import msvcrt
                msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
            else:
                import fcntl
                fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError as exc:
            raise WriterBusy("FILM_BUSY: another production operation owns this film or Flow session") from exc
        held.add(key)
        try:
            yield
        finally:
            held.remove(key)
            handle.seek(0)
            if os.name == "nt":
                msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                fcntl.flock(handle.fileno(), fcntl.LOCK_UN)


@contextmanager
def writer(root: Path, *, flow: bool = False):
    with ExitStack() as stack:
        if flow:
            # flow_send currently has one CDP composer endpoint; protect that shared surface too.
            stack.enter_context(_exclusive("flow-ui-composer"))
        stack.enter_context(_exclusive("film:" + os.path.normcase(str(Path(root).resolve()))))
        yield


def film_writer(*, flow: bool = False):
    def decorate(fn):
        @wraps(fn)
        def call(pkg_or_root, *args, **kwargs):
            with writer(Path(getattr(pkg_or_root, "root", pkg_or_root)), flow=flow):
                return fn(pkg_or_root, *args, **kwargs)
        return call
    return decorate
