"""Small shared boundaries for durable package writes and exclusive production operations."""
from __future__ import annotations

import hashlib
import asyncio
import json
import os
import tempfile
import threading
import time
from urllib.parse import urlsplit
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


# One Flow profile = one CDP endpoint. A shard process sets AFP_FLOW_CDP (and AFP_FLOW_PROJECT) for the profile it drives.
DEFAULT_FLOW_CDP = "http://127.0.0.1:9333"
FLOW_CDP_ENV = "AFP_FLOW_CDP"
FLOW_PROJECT_ENV = "AFP_FLOW_PROJECT"


def normalize_cdp(endpoint: str | None) -> str:
    """Canonical ``http://127.0.0.1:<port>`` form: localhost, trailing slash and a missing scheme are the same endpoint."""
    text = (endpoint or "").strip() or DEFAULT_FLOW_CDP
    parts = urlsplit(text if "://" in text else "http://" + text)
    host = (parts.hostname or "127.0.0.1").lower()
    host = "127.0.0.1" if host == "localhost" else host
    port = parts.port or (443 if parts.scheme == "https" else 80)
    return f"{parts.scheme or 'http'}://{host}:{port}"


def flow_cdp(override: str | None = None) -> str:
    """The CDP endpoint this process drives (override > AFP_FLOW_CDP > the legacy 127.0.0.1:9333)."""
    return normalize_cdp(override or os.environ.get(FLOW_CDP_ENV))


def flow_project() -> str:
    """The Flow project id this process is pinned to ('' = whatever Flow tab the endpoint shows, as before)."""
    return os.environ.get(FLOW_PROJECT_ENV, "").strip()


def flow_target_problem(receipt: dict) -> str | None:
    """Why this process may not scan for / reconcile the send `receipt` (None = it may). A receipt without ``cdp`` was
    sent before shards existed, through the default endpoint. A pinned project must match the receipt's project."""
    sent = normalize_cdp(receipt.get("cdp"))
    if sent != flow_cdp():
        return f"FLOW_TARGET_MISMATCH: the send used endpoint {sent}, this process drives {flow_cdp()}"
    pinned, was = flow_project(), str(receipt.get("project") or "")
    if pinned and was and pinned != was:
        return f"FLOW_TARGET_MISMATCH: the send used project {was}, this process is pinned to {pinned}"
    return None


def flow_lock_key(cdp: str | None = None) -> str:
    endpoint = flow_cdp(cdp)
    # the default endpoint keeps the pre-shard key, so old and new processes still exclude each other on it
    return "flow-ui-composer" if endpoint == normalize_cdp(DEFAULT_FLOW_CDP) else "flow-ui-composer:" + endpoint


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
def scratch_tempdir(*, prefix: str = "afp-work-", root: Path | None = None):
    """Temporary directory placed on the spacious scratch volume selected by preflight."""
    from film_pipeline.production.preflight import scratch_dir

    base = scratch_dir(root)
    base.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix=prefix, dir=str(base)) as tmp:
        yield Path(tmp)


@contextmanager
def _exclusive(key: str, *, timeout_s: float = 0.0):
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
        deadline = time.monotonic() + max(0.0, float(timeout_s))
        while True:
            handle.seek(0)
            try:
                if os.name == "nt":
                    import msvcrt
                    msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
                else:
                    import fcntl
                    fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
                break
            except OSError as exc:
                if time.monotonic() >= deadline:
                    raise WriterBusy("FILM_BUSY: another production operation owns this film or Flow session") from exc
                time.sleep(0.05)
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
def composer_lock(cdp: str | None = None):
    """Exclusive lock for a single Flow composer CDP endpoint across sends/reconciles."""
    with _exclusive(flow_lock_key(cdp)):
        yield


@contextmanager
def film_lock(root: Path, *, timeout_s: float = 0.0):
    """Short metadata/index lock for a film package directory."""
    with _exclusive("film:" + os.path.normcase(str(Path(root).resolve())), timeout_s=timeout_s):
        yield


@contextmanager
def writer(root: Path, *, flow: bool = False, cdp: str | None = None):
    with ExitStack() as stack:
        if flow:
            # One in-flight send per composer: the lock is keyed by the CDP endpoint (= the Flow profile) in use.
            stack.enter_context(composer_lock(cdp))
        stack.enter_context(film_lock(root))
        yield


def film_writer(*, flow: bool = False):
    def decorate(fn):
        @wraps(fn)
        def call(pkg_or_root, *args, **kwargs):
            with writer(Path(getattr(pkg_or_root, "root", pkg_or_root)), flow=flow):
                return fn(pkg_or_root, *args, **kwargs)
        return call
    return decorate
