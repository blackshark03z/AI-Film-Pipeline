r"""
High-Throughput Dynamic Worker Pool Engine (`N tài khoản × 6 video shots` / `N tài khoản × 4 keyframes`).
Thiết kế chuyên biệt để Gemini Agent gọi tuần tự từng khâu trong dự án `d:\Muse`:
  - Tôn trọng tuyệt đối trần luồng được cấp `--max-accounts N` (tối đa `N × 6` video hoặc `N × 4` ảnh song song).
  - Hàng đợi động `asyncio.Queue` (tài khoản nào xong lô 6 shots trước lập tức bốc lô kế tiếp, không chờ đợt chậm).
  - Hot-swap tự động sang tài khoản dự phòng rảnh (`standby`) ngay khi 1 tài khoản hết quota giữa chừng.
  - Tuyệt đối không chạm vào các tài khoản đang mở ở session Playwright/Chrome khác (`BusyAccountDetector` + `SessionLock`).
"""

import asyncio
import hashlib
import inspect
import io
import json
import math
import os
import re
import secrets
import shutil
import time
import zipfile
from collections import deque
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any, Callable, Deque, Dict, Iterable, List, Optional, Set, Tuple, Union

try:
    from .account_manager import AccountManager
    from .autoprod_orchestrator import (
        BusyAccountDetector, SessionLock, _load_render_checkpoint, _render_fingerprint, _write_json_atomic,
    )
    from .batch_packager import BatchPackager, IntegrityUnpersistedError, KeyframeItem, ShotItem, compute_sha256
    from .film_qc_engine import FilmQCEngine
    from .headless_muse_client import (
        BlockedException,
        GenerationFailedException,
        HeadlessMuseClient,
        HaltedException,
        LeaseLostException,
        QuotaExceededException,
        SessionInvalidException,
    )
    from .keyframe_composer import KeyframeComposer
    from .lane_leases import LaneContext, LeaseRegistry, heartbeat_interval_s
    from .prompt_repair_agent import PromptRepairAgent
    from . import send_halt
    from .send_halt import CLEAR_HALT_HINT, HALT_FILE, halt_info, record_block  # noqa: F401 (re-export)
    from .staging import require_current_staging
except ImportError:
    from core.account_manager import AccountManager
    from core.autoprod_orchestrator import (
        BusyAccountDetector, SessionLock, _load_render_checkpoint, _render_fingerprint, _write_json_atomic,
    )
    from core.batch_packager import BatchPackager, IntegrityUnpersistedError, KeyframeItem, ShotItem, compute_sha256
    from core.film_qc_engine import FilmQCEngine
    from core.headless_muse_client import (
        BlockedException,
        GenerationFailedException,
        HeadlessMuseClient,
        HaltedException,
        LeaseLostException,
        QuotaExceededException,
        SessionInvalidException,
    )
    from core.keyframe_composer import KeyframeComposer
    from core.lane_leases import LaneContext, LeaseRegistry, heartbeat_interval_s
    from core.prompt_repair_agent import PromptRepairAgent
    from core import send_halt
    from core.send_halt import CLEAR_HALT_HINT, HALT_FILE, halt_info, record_block  # noqa: F401 (re-export)
    from core.staging import require_current_staging


VIDEO_BATCH_SIZE = 6
KEYFRAME_BATCH_SIZE = 4


SIM_ACCOUNT_PREFIX = "sim_acc_"

# Send ledger, kept across invocations (see `_run_videos_async`): every batch is recorded `PENDING_SEND` before it is
# dispatched, then `RESOLVED` (result received / never sent) or `UNCONFIRMED` (reached Muse, no result). Entries stay
# as history. Statuses in UNCONFIRMED_BLOCKING block a resend of their shot.
UNCONFIRMED_FILE = "unconfirmed_submissions.json"
DEFAULT_UNCONFIRMED_TTL_MIN = 120.0
UNCONFIRMED_BLOCKING = ("PENDING_SEND", "UNCONFIRMED", "EXPIRED_NEEDS_RECONCILE", "RESULT_CORRUPT")
# Per-batch sidecar with the render fingerprint of every shot at send time (read by `cli qc-audit`).
BATCH_FINGERPRINTS_FILE = "render_fingerprints.json"
# Run halt (`muse_halt.json`, see `send_halt`): shared by every send entry point; only `--clear-halt` removes it.
# Keyframe send ledger, kept across invocations, same model as UNCONFIRMED_FILE (one entry per image): `PENDING_SEND`
# before the batch is dispatched, then `RESOLVED` or `UNCONFIRMED`. `--clear-halt` never releases an entry.
KF_LEDGER_FILE = "unconfirmed_keyframes.json"
INTEGRITY_UNPERSISTED_STATUS = "INTEGRITY_UNPERSISTED"


def load_unconfirmed_keyframes(project_dir: Path) -> List[Dict[str, Any]]:
    """Keyframe send ledger entries (history included). A corrupt ledger fails closed (raises, nothing is sent)."""
    path = Path(project_dir) / KF_LEDGER_FILE
    if not path.exists():
        return []
    data = json.loads(path.read_text(encoding="utf-8"))
    return [
        {**e, "status": e.get("status") or "UNCONFIRMED"}
        for e in data.get("entries") or []
        if isinstance(e, dict) and e.get("kf_id")
    ]


KF_RESULT_IMAGE_EXTS = (".png", ".jpg", ".jpeg")


def kf_result_image(out_dir: Path, batch_id: str, kf_id: str,
                    not_before: Optional[float] = None) -> Optional[Dict[str, Any]]:
    """Evidence that `kf_id` of this submission came back: an image in `<out_dir>/<batch_id>_kf_result.zip` (named by
    kf id or its manifest slot) of at least the planner's size floor that decodes as PNG/JPEG, in a result zip no
    older than the submission (`not_before`, epoch). None = not verified (never released on a bare file)."""
    out_dir = Path(out_dir)
    zp = out_dir / f"{batch_id}_kf_result.zip"
    try:
        if not zp.is_file():
            return None
        if not_before is not None and zp.stat().st_mtime + 1.0 < float(not_before):
            return None  # a result of an earlier send of the same batch id
        names = {kf_id}
        mp = out_dir / f"{batch_id}_kf_manifest.json"
        if mp.is_file():
            try:
                for e in json.loads(mp.read_text(encoding="utf-8")).get("keyframes") or []:
                    if str(e.get("kf_id")) == kf_id and e.get("slot_id"):
                        names.add(str(e["slot_id"]))
            except (ValueError, OSError, AttributeError):
                pass
        from PIL import Image

        # The exclusion list of this keyframe batch (same dir `unpack_keyframe_result` records into): an unreadable
        # list means the whole batch is untrusted, a listed name is never evidence.
        list_ok, excluded = BatchPackager.read_integrity_failed(out_dir)
        if not list_ok:
            return None
        with zipfile.ZipFile(zp, "r") as zf:
            receipt_sha: Dict[str, str] = {}
            for info in zf.infolist():
                if info.filename.lower().endswith(".json") and "receipt" in Path(info.filename).name.lower():
                    try:
                        receipt_sha.update(BatchPackager.parse_keyframe_receipt(json.loads(zf.read(info))))
                    except (ValueError, OSError):
                        continue
            for info in zf.infolist():
                stem, ext = os.path.splitext(Path(info.filename).name)
                if ext.lower() not in KF_RESULT_IMAGE_EXTS or not (stem in names or kf_id in stem):
                    continue
                if Path(info.filename).name in excluded:
                    continue
                if info.file_size < BatchPackager.MIN_IMAGE_BYTES:
                    continue
                raw = zf.read(info)
                if len(raw) < BatchPackager.MIN_IMAGE_BYTES:
                    continue
                try:
                    with Image.open(io.BytesIO(raw)) as im:
                        if im.format not in ("PNG", "JPEG"):
                            continue
                        im.verify()
                    with Image.open(io.BytesIO(raw)) as im:
                        im.load()
                except Exception:
                    continue
                digest = hashlib.sha256(raw).hexdigest()
                want = receipt_sha.get(stem) or receipt_sha.get(kf_id)
                if want and want != digest:
                    continue  # the receipt says this image is not the one the VM verified: not evidence
                return {"result_zip": str(zp), "member": info.filename, "bytes": len(raw),
                        "sha256": digest}
    except (zipfile.BadZipFile, OSError):
        return None
    return None


def adopt_legacy_kf_batches(batch_roots: Iterable[Path], ledger: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Keyframe batches handed off before the ledger existed (a `<bid>_kf_manifest.json` with no ledger entry) and
    without a verified result are adopted as UNCONFIRMED (`legacy`): withheld until reconciled or released by hand.
    An unreadable manifest fails closed (raises: its images cannot be told apart from unsent ones)."""
    known = {(e.get("batch_id"), e.get("kf_id")) for e in ledger}
    adopted: List[Dict[str, Any]] = []
    for root in batch_roots:
        root = Path(root)
        if not root.is_dir():
            continue
        for bdir in sorted(p for p in root.iterdir() if p.is_dir()):
            bid = bdir.name
            mp = bdir / f"{bid}_kf_manifest.json"
            if not mp.is_file():
                continue
            try:
                kf_ids = [str(e["kf_id"]) for e in json.loads(mp.read_text(encoding="utf-8")).get("keyframes") or []
                          if isinstance(e, dict) and e.get("kf_id")]
            except (ValueError, OSError, AttributeError) as exc:
                raise RuntimeError(f"Unreadable keyframe batch manifest {mp}: {exc}. Fix or move it before sending.")
            stamp = mp.stat().st_mtime
            for kf in kf_ids:
                if (bid, kf) in known or kf_result_image(bdir, bid, kf):
                    continue
                e = {"kf_id": kf, "batch_id": bid, "account_id": None, "status": "UNCONFIRMED", "legacy": True,
                     "out_dir": str(bdir), "submitted_epoch": stamp,
                     "submitted_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(stamp)),
                     "error": "LEGACY_BATCH_WITHOUT_VERIFIED_RESULT"}
                ledger.append(e)
                known.add((bid, kf))
                adopted.append(dict(e))
    return adopted


def _fresh_batch_dir(bid: str, out_dir: Path) -> Tuple[str, Path]:
    """Never write into an output dir that already holds files of another run (or an earlier attempt): such a dir gets
    a new short suffix on the batch id (and so on the zip names) until it is free."""
    out_dir = Path(out_dir)
    while out_dir.exists() and any(out_dir.iterdir()):
        bid = f"{bid}_{secrets.token_hex(2)}"
        out_dir = out_dir.parent / bid
    return bid, out_dir


def _was_submitted(exc: BaseException) -> bool:
    """True when the client reports the batch reached Muse (message sent) before the failure."""
    return bool(getattr(exc, "submitted", False))


def _accepts_kw(fn: Any, name: str) -> bool:
    try:
        params = inspect.signature(fn).parameters
    except (TypeError, ValueError):
        return False
    return name in params or any(p.kind is inspect.Parameter.VAR_KEYWORD for p in params.values())


def resolve_unconfirmed_ttl_min(override: Optional[float] = None) -> float:
    """TTL (minutes) after which an unreconciled send is flagged `EXPIRED_NEEDS_RECONCILE` (it still blocks a resend):
    arg > env `MUSE_UNCONFIRMED_TTL_MIN` > default."""
    if override is not None:
        return float(override)
    raw = os.environ.get("MUSE_UNCONFIRMED_TTL_MIN")
    try:
        return float(raw) if raw else DEFAULT_UNCONFIRMED_TTL_MIN
    except ValueError:
        return DEFAULT_UNCONFIRMED_TTL_MIN


def load_unconfirmed_submissions(project_dir: Path) -> List[Dict[str, Any]]:
    """Read the project's send ledger (all entries, history included; an entry without `status` is `UNCONFIRMED`).
    A corrupt ledger fails closed (raises, nothing is sent)."""
    path = Path(project_dir) / UNCONFIRMED_FILE
    if not path.exists():
        return []
    data = json.loads(path.read_text(encoding="utf-8"))
    out = []
    for e in data.get("entries") or []:
        if isinstance(e, dict) and e.get("shot_id"):
            out.append({**e, "status": e.get("status") or "UNCONFIRMED"})
    return out


def _zip_is_valid_result(zp: Path) -> bool:
    """The result zip opens, every member passes its CRC check, and it holds at least one clip."""
    try:
        with zipfile.ZipFile(zp, "r") as zf:
            if zf.testzip() is not None:
                return False
            return any(n.lower().endswith(".mp4") for n in zf.namelist())
    except (OSError, zipfile.BadZipFile, EOFError, ValueError):
        return False


def _batch_result_state(batch_dir: Path) -> str:
    """`ARRIVED` once the batch was unpacked (clips on disk) or its result zip verifies; `CORRUPT` when only an empty
    or broken result zip exists (an interrupted download proves nothing); `NONE` otherwise."""
    if not batch_dir.is_dir():
        return "NONE"
    if any(batch_dir.glob("verified_clips/*.mp4")) or any(batch_dir.glob("integrity_failed/*.mp4")):
        return "ARRIVED"
    zips = list(batch_dir.glob("*_result.zip"))
    if not zips:
        return "NONE"
    return "ARRIVED" if any(_zip_is_valid_result(z) for z in zips) else "CORRUPT"


def _batch_result_arrived(batch_dir: Path) -> bool:
    return _batch_result_state(batch_dir) == "ARRIVED"


def legacy_inflight_batches(project_dir: Path, shot_ids: Iterable[str]) -> List[Dict[str, Any]]:
    """Batch dirs written before the send ledger existed that have no result: their generation may still be running on
    Muse, so their shots are treated as unconfirmed until checked (never silently resent)."""
    root = Path(project_dir) / "BATCHES_V2"
    wanted = set(shot_ids)
    out: List[Dict[str, Any]] = []
    if not root.is_dir():
        return out
    for bdir in sorted(p for p in root.iterdir() if p.is_dir()):
        if _batch_result_arrived(bdir):
            continue
        side: Dict[str, Any] = {}
        try:
            side = json.loads((bdir / BATCH_FINGERPRINTS_FILE).read_text(encoding="utf-8")) or {}
        except (OSError, ValueError):
            side = {}
        if side.get("simulate"):
            continue
        fps = dict(side.get("shots") or {})
        sids = list(fps)
        if not sids:
            try:
                bm = json.loads((bdir / f"{bdir.name}_manifest.json").read_text(encoding="utf-8")) or {}
                sids = [e.get("shot_id") for e in bm.get("shots") or [] if isinstance(e, dict)]
            except (OSError, ValueError):
                sids = []
        stamp = bdir.stat().st_mtime
        for sid in sids:
            if sid in wanted:
                out.append({
                    "shot_id": sid,
                    "batch_id": bdir.name,
                    "take": side.get("take") or 1,
                    "status": "UNCONFIRMED",
                    "submitted_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(stamp)),
                    "submitted_epoch": stamp,
                    "fingerprint": fps.get(sid),
                    "error": "LEGACY_BATCH_WITHOUT_RESULT: batch dir from before the send ledger has no result",
                })
    return out


@asynccontextmanager
async def _warm_pool(client):
    try:
        if hasattr(client, "enable_warm_pool"):
            client.enable_warm_pool(True)
        yield
    finally:
        if hasattr(client, "close_all_sessions"):
            await client.close_all_sessions()


async def _run_workers(workers):
    tasks = [asyncio.create_task(worker) for worker in workers]
    try:
        await asyncio.gather(*tasks)
    finally:
        for task in tasks:
            if not task.done():
                task.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)


class ParallelPoolEngine:
    """Bộ điều phối hàng đợi động đa tài khoản đạt công suất cực đại `N × 6` shots."""

    def __init__(
        self,
        account_manager: Optional[AccountManager] = None,
        client_factory: Optional[Callable[[AccountManager], Any]] = None,
        qc_evaluator: Optional[Callable[..., Dict[str, Any]]] = None,
        sync_ui: bool = True,
        lane: Optional[LaneContext] = None,
        lease_registry: Optional[LeaseRegistry] = None,
    ):
        self.account_manager = account_manager or AccountManager()
        self.client_factory = client_factory or HeadlessMuseClient
        self.qc_evaluator = qc_evaluator or FilmQCEngine.evaluate_generated_clip
        self.sync_ui = sync_ui
        # With a lane: only that lane's leased accounts are eligible. Without: skip every live-leased account.
        self.lane = lane
        self.lease_registry = lane.registry if lane is not None else (lease_registry or LeaseRegistry())
        self.lease_conflicts: Set[str] = set()
        self._kf_batch_errors: List[Dict[str, Any]] = []
        self._kf_skipped_phases: List[str] = []
        # Set when an integrity-failed clip could be neither listed nor quarantined: the run STOPS (contract v8 s10 #11).
        self._integrity_stop: List[Dict[str, Any]] = []
        # Run-wide stop after a CAPTCHA / verification page: no worker dispatches another batch once it is set.
        self._halt: Optional[Dict[str, Any]] = None
        self._halt_ctx: Optional[Tuple[Path, bool]] = None
        self._halt_seen: Optional[Dict[str, Any]] = None
        self._halt_cleared: Optional[Dict[str, Any]] = None
        # Keyframe send ledger of the current keyframes run (None = no ledger, e.g. a direct chunk call).
        self._kf_ledger: Optional[List[Dict[str, Any]]] = None
        self._kf_ledger_path: Optional[Path] = None
        self._kf_withheld: List[str] = []
        # Synthetic accounts a --simulate run stands in for a lane's real accounts (never in any registry).
        self._sim_dispatch_ids: Set[str] = set()

    def _account_allowed(self, account_id: str) -> bool:
        """Dispatch-time lease check: the lane still owns it, or (no lane) no live lane holds it."""
        if account_id in self._sim_dispatch_ids:
            return True
        if self.lane is not None:
            return self.lane.owns(account_id)
        if self.lease_registry.holder_of(account_id) is not None:
            self.lease_conflicts.add(account_id)
            return False
        return True

    @property
    def _halt(self) -> Optional[Dict[str, Any]]:
        """The run's halt. A real run also adopts the machine-wide stop (a block seen by another engine, project or
        process, a pending halt marker, the AFP halt): every worker loop and except branch then stops dispatching."""
        if self._halt_local is None:
            ctx = getattr(self, "_halt_ctx", None)
            if ctx is not None and not ctx[1]:
                stop = send_halt.send_stop()
                if stop is not None:
                    self._halt_local = dict(stop)
        return self._halt_local

    @_halt.setter
    def _halt(self, value: Optional[Dict[str, Any]]) -> None:
        self._halt_local = value

    def _send_allowed(self, account_id: str) -> bool:
        """Checked by the client right before the submit keystroke: the lease still holds, no block halted the run and
        no integrity stop is pending (another worker must never press Enter after an unpersisted clip)."""
        return self._halt is None and not self._integrity_stop and self._account_allowed(account_id)

    def _kf_blocked_ids(self) -> Set[str]:
        return {e["kf_id"] for e in self._kf_ledger or [] if e.get("status") in UNCONFIRMED_BLOCKING}

    def _kf_ledger_mark(self, bid: str, chunk: List[KeyframeItem], account_id: Optional[str], status: str,
                        **extra: Any) -> None:
        if self._kf_ledger is None:
            return
        stamp = time.time()
        for k in chunk:
            e = next((x for x in self._kf_ledger if x.get("batch_id") == bid and x.get("kf_id") == k.kf_id), None)
            if e is None:
                e = {"kf_id": k.kf_id, "batch_id": bid, "account_id": account_id,
                     "submitted_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(stamp)),
                     "submitted_epoch": stamp}
                self._kf_ledger.append(e)
            elif status == "PENDING_SEND":
                # A new send of a reused batch id: bind the entry to this submission (time, account), not the last.
                for stale in ("legacy", "reason", "error", "resolved_at", "released_at", "result"):
                    e.pop(stale, None)
                e.update({"account_id": account_id, "submitted_epoch": stamp,
                          "submitted_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(stamp))})
            e["status"] = status
            if status == "RESOLVED":
                e["resolved_at"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(stamp))
            e.update(extra)
        if self._kf_ledger_path is not None:
            _write_json_atomic(self._kf_ledger_path, {"entries": self._kf_ledger})

    def _halt_gate(self, project_dir: Path, simulate: bool, clear_halt: bool) -> Optional[Dict[str, Any]]:
        """Refusal report while any machine-wide stop signal (or this project's halt copy) exists (None = proceed)."""
        self._halt_ctx = (Path(project_dir), bool(simulate))
        data = send_halt.load_halt(project_dir)
        if data is None:
            return None
        if simulate:
            self._halt_seen = data  # a dry run never sends: reported, not enforced (and never cleared)
            return None
        if clear_halt:
            # Lifts the Muse halt only (global file + project copy). Unreconciled sends (both ledgers) stay blocked
            # until explicitly released; AFP halt and halt_pending markers are the Owner's to clear.
            send_halt.clear_halt(project_dir)
            self._halt_cleared = data
            data = send_halt.load_halt(project_dir)
            if data is None:
                return None
        return {
            "status": "HALTED",
            "halted": data,
            "halt_path": str(send_halt.halt_path()),
            "message": f"Sending refused: Muse sending is halted machine-wide; {CLEAR_HALT_HINT}.",
        }

    def _on_blocked(self, exc: BaseException, account_id: Optional[str], batch_id: Optional[str]) -> None:
        """Stop ALL sending for this run, persist the halt and take the account out (no failover)."""
        # Synchronous on purpose: the halt is set before the caller awaits anything (a worker mid-upload then fails
        # its submit guard instead of sending).
        project_dir, simulate = self._halt_ctx or (None, True)
        info = halt_info(exc, account_id, batch_id)
        if self._halt is None:
            self._halt = info
        record_block(project_dir, info, self.account_manager, simulate)

    def _adopt_halt_refusal(self, exc: BaseException, account_id: Optional[str], batch_id: Optional[str]) -> None:
        """A pre-Enter gate refused because Muse sending is halted (`HaltedException`): that IS the run's halt, never a
        plain NOT_SENT failure to requeue. Adopts the stop record the gate saw (OWNER_PAUSE, a block elsewhere, ...)."""
        if self._halt is not None or not isinstance(exc, HaltedException):
            return
        stop = getattr(exc, "stop", None) or send_halt.send_stop()
        info = dict(stop) if stop else {"reason": "HALTED", "detail": str(exc)[:200]}
        info.setdefault("account_id", account_id)
        info.setdefault("batch_id", batch_id)
        self._halt = info

    def _note_not_dispatched(self, chunks: Iterable[Tuple[str, List[KeyframeItem], Path]], reason: str,
                             account_id: Optional[str] = None, error: Optional[str] = None) -> None:
        """Chunks that were never sent (no account left, run halted, failover exhausted): reported, never dropped."""
        for bid, chunk, _out in chunks:
            self._kf_batch_errors.append(
                {"batch_id": bid, "account_id": account_id, "submitted": False, "not_dispatched": True,
                 "reason": reason, "error": error or f"not sent: {reason}", "kf_ids": [k.kf_id for k in chunk]}
            )
            m = re.match(r"KF_[A-Z]+", bid)
            phase = m.group(0) if m else bid
            if phase not in self._kf_skipped_phases:
                self._kf_skipped_phases.append(phase)

    def _lease_report(self) -> Optional[Dict[str, Any]]:
        if self.lane is not None:
            return self.lane.report()
        if self.lease_conflicts:
            return {"lane_id": None, "leased_by_other_lane_mid_run": sorted(self.lease_conflicts)}
        return None

    def _with_lease_report(self, report: Dict[str, Any]) -> Dict[str, Any]:
        lane_rep = self._lease_report()
        if lane_rep is not None:
            report["lane"] = lane_rep
        return report

    @asynccontextmanager
    async def _lane_heartbeat(self):
        """Renew the lane's leases at start, every `MUSE_LANE_HEARTBEAT_S` (default 300 s) and at the end."""
        if self.lane is None:
            yield
            return
        self.lane.renew()

        async def _beat() -> None:
            while True:
                await asyncio.sleep(heartbeat_interval_s())
                try:
                    self.lane.renew()
                except Exception:
                    pass

        task = asyncio.create_task(_beat())
        try:
            yield
        finally:
            task.cancel()
            await asyncio.gather(task, return_exceptions=True)
            try:
                self.lane.renew()
            except Exception:
                pass

    def _pick_standby(self, standby_q: Deque[str], simulate: bool) -> Optional[str]:
        while standby_q:
            cand = standby_q.popleft()
            if not self._account_allowed(cand):
                continue
            if simulate or not BusyAccountDetector.is_profile_locked(self.account_manager.profiles_dir / cand):
                return cand
        return None

    def inspect_capacity(
        self,
        max_accounts: Optional[int] = None,
        only_accounts: Optional[Set[str]] = None,
        exclude_accounts: Optional[Set[str]] = None,
        auto_verify_unchecked: bool = False,
        simulate: bool = False,
        owned_profile_ids: Optional[Set[str]] = None,
    ) -> Dict[str, Any]:
        excl = set(exclude_accounts or set())
        only = set(only_accounts or set())
        lane_id = self.lane.lane_id if self.lane is not None else None
        leases = self.lease_registry.live_leases()
        if self.lane is not None:
            lane_held = self.lane.held_ids()
            only = (only & lane_held) if only else set(lane_held)

        if auto_verify_unchecked and not simulate:
            for acc in self.account_manager.list_accounts():
                aid = acc["id"]
                if aid in excl or ((only or self.lane is not None) and aid not in only):
                    continue
                holder = (leases.get(aid) or {}).get("lane_id")
                if holder and holder != lane_id:
                    continue
                if (acc.get("status") or "").upper() in ("READY", "COOLDOWN", "BUSY"):
                    continue
                if BusyAccountDetector.is_profile_locked(self.account_manager.profiles_dir / aid):
                    continue
                res = self.account_manager.auto_login_and_verify(aid)
                if isinstance(res, dict) and res.get("status") == "BLOCKED":
                    # CAPTCHA / verification at login: stop, never try the next account.
                    self._on_blocked(BlockedException(str(res.get("message") or "BLOCKED at login")), aid, None)
                    break

        if simulate:
            # Offline dry run: never select a real account (accounts.json is neither read for selection nor written).
            skipped: Dict[str, str] = {}
            if self.lane is not None:
                uncontended = sorted(aid for aid in only if aid.startswith(SIM_ACCOUNT_PREFIX) and aid not in excl)
                n_sim = len(only) if (only and not uncontended) else 0  # real lane in a dry run: same width
            else:
                uncontended = []
                n_sim = max(1, int(max_accounts or 2))
            i = 0
            while len(uncontended) < n_sim and i < 999:
                i += 1
                sim_id = f"{SIM_ACCOUNT_PREFIX}{i:02d}"
                holder = (leases.get(sim_id) or {}).get("lane_id")
                if sim_id in excl or (holder and holder != lane_id):
                    continue
                uncontended.append(sim_id)
                if self.lane is not None:
                    # Dry run of a lane holding real accounts: the stand-ins are authorised for this run only.
                    self._sim_dispatch_ids.add(sim_id)
        else:
            uncontended, skipped = BusyAccountDetector.select_uncontended_ready_accounts(
                self.account_manager,
                exclude_ids=excl,
                owned_profile_ids=owned_profile_ids,
                lane_id=lane_id,
                leases=leases,
            )
            if only or self.lane is not None:
                uncontended = [aid for aid in uncontended if aid in only]

        if max_accounts is not None and max_accounts > 0:
            active_ids = uncontended[:max_accounts]
            standby_ids = uncontended[max_accounts:]
        else:
            active_ids = list(uncontended)
            standby_ids = []

        n_active = len(active_ids)
        return {
            "granted_accounts": n_active,
            "requested_max_accounts": max_accounts,
            "parallel_video_shots_per_wave": n_active * VIDEO_BATCH_SIZE,
            "parallel_keyframe_images_per_wave": n_active * KEYFRAME_BATCH_SIZE,
            "active_account_ids": active_ids,
            "standby_account_ids": standby_ids,
            "skipped_busy_accounts": skipped,
            "lane_id": lane_id,
        }

    @staticmethod
    def _compute_balanced_batch_size(total_items: int, n_accounts: int, max_batch: int) -> int:
        """
        Giữ nguyên cỡ lô chuẩn (`6` video / `4` ảnh) khi hàng đợi dồi dào (`total >= N * max_batch`),
        nhưng tự chia đều tải khi số lượng còn ít (ví dụ vòng retry còn 8 shots trên 4 tài khoản -> `[2,2,2,2]`
        thay vì `[6,2,0,0]`) để toàn bộ tài khoản rảnh cùng gánh song song, giảm tới 3x thời gian chờ đuôi.
        """
        if total_items <= 0:
            return max_batch
        n_acc = max(1, int(n_accounts))
        if total_items >= n_acc * max_batch:
            return max_batch
        return max(1, min(max_batch, math.ceil(total_items / n_acc)))

    async def _run_kf_chunks_parallel(
        self,
        chunks: List[Tuple[str, List[KeyframeItem], Path]],
        active_ids: List[str],
        standby_ids: List[str],
        client: Any,
        simulate: bool,
    ) -> List[Dict[str, Any]]:
        if not chunks:
            return []
        if self._halt is not None:
            self._note_not_dispatched(chunks, "run halted")
            return []
        if not active_ids:
            self._note_not_dispatched(chunks, "no account left")
            return []
        blocked = self._kf_blocked_ids()
        if blocked:
            # An earlier send of these images is not reconciled: never resend them (explicit release only).
            kept = []
            for bid, chunk, out_dir in chunks:
                self._kf_withheld.extend(k.kf_id for k in chunk if k.kf_id in blocked)
                rest = [k for k in chunk if k.kf_id not in blocked]
                if rest:
                    kept.append((bid, rest, out_dir))
            chunks = kept
            if not chunks:
                return []

        work_q: asyncio.Queue = asyncio.Queue()
        for bid, chunk, out_dir in chunks:
            work_q.put_nowait((bid, chunk, out_dir, 0))

        standby_q: Deque[str] = deque(standby_ids)
        results: List[Dict[str, Any]] = []
        replacements: Dict[str, Optional[str]] = {}

        async def _kf_worker(initial_acc_id: str) -> None:
            cur_acc: Optional[str] = initial_acc_id
            while cur_acc is not None:
                if self._halt is not None:
                    break  # a block anywhere stops every worker (in-flight batches finish)
                if not self._account_allowed(cur_acc):
                    # Lease lost/expired (or taken by a lane): stop dispatching on this account.
                    cur_acc = self._pick_standby(standby_q, simulate)
                    replacements[initial_acc_id] = cur_acc
                    continue
                try:
                    bid, chunk, out_dir, attempt = work_q.get_nowait()
                except asyncio.QueueEmpty:
                    break
                if attempt == 0:
                    bid, out_dir = _fresh_batch_dir(bid, out_dir)

                if not simulate:
                    self._kf_ledger_mark(bid, chunk, cur_acc, "PENDING_SEND", out_dir=str(out_dir))
                kw: Dict[str, Any] = {}
                if _accepts_kw(client.generate_keyframes_batch, "lease_guard"):
                    kw["lease_guard"] = lambda acc=cur_acc: self._send_allowed(acc)
                try:
                    res = await client.generate_keyframes_batch(
                        account_id=cur_acc,
                        keyframes=chunk,
                        batch_id=bid,
                        output_dir=out_dir,
                        timeout_seconds=HeadlessMuseClient.compute_adaptive_timeout(len(chunk), is_video=False),
                        simulate=simulate,
                        **kw,
                    )
                    if not simulate:
                        self._kf_ledger_mark(bid, chunk, cur_acc, "RESOLVED", reason="RESULT_RECEIVED")
                    results.append(res)
                except BlockedException as exc:
                    # Never re-queued, never handed to a standby account. The halt is set before any await.
                    self._on_blocked(exc, cur_acc, bid)
                    if not simulate:
                        if _was_submitted(exc):
                            self._kf_ledger_mark(bid, chunk, cur_acc, "UNCONFIRMED", error=str(exc)[:300])
                        else:
                            self._kf_ledger_mark(bid, chunk, cur_acc, "RESOLVED", reason="NOT_SENT")
                    self._kf_batch_errors.append(
                        {"batch_id": bid, "account_id": cur_acc, "submitted": _was_submitted(exc), "blocked": True,
                         "error": str(exc), "kf_ids": [k.kf_id for k in chunk]}
                    )
                    replacements[initial_acc_id] = None
                    if cur_acc in getattr(client, "warm_account_ids", ()):
                        await client._evict_warm_session(cur_acc)
                    break
                except (
                    QuotaExceededException, SessionInvalidException, GenerationFailedException, LeaseLostException,
                ) as exc:
                    # A gate refusal because sending is halted is the run's halt (OWNER_PAUSE, a block elsewhere).
                    self._adopt_halt_refusal(exc, cur_acc, bid)
                    if not simulate:
                        if _was_submitted(exc):
                            self._kf_ledger_mark(bid, chunk, cur_acc, "UNCONFIRMED", error=str(exc)[:300])
                        else:
                            self._kf_ledger_mark(bid, chunk, cur_acc, "RESOLVED", reason="NOT_SENT")
                    if self._halt is not None and not _was_submitted(exc):
                        # Another account was blocked meanwhile (e.g. the submit guard refused): stop, not sent.
                        self._kf_batch_errors.append(
                            {"batch_id": bid, "account_id": cur_acc, "submitted": False, "halted": True,
                             "error": str(exc), "kf_ids": [k.kf_id for k in chunk]}
                        )
                        break
                    if cur_acc in getattr(client, "warm_account_ids", ()):
                        await client._evict_warm_session(cur_acc)
                    if _was_submitted(exc):
                        # Already sent to Muse: never resend in this run (it may still render and spend credits).
                        self._kf_batch_errors.append(
                            {"batch_id": bid, "account_id": cur_acc, "submitted": True, "error": str(exc),
                             "kf_ids": [k.kf_id for k in chunk]}
                        )
                    elif attempt < 2:
                        work_q.put_nowait((f"{bid}_FO{attempt + 1}", chunk, out_dir, attempt + 1))
                    else:
                        # Third failure before Enter: no requeue left. Reported, never dropped.
                        self._note_not_dispatched(
                            [(bid, chunk, out_dir)], "failover exhausted", account_id=cur_acc, error=str(exc))
                    next_acc = self._pick_standby(standby_q, simulate)
                    cur_acc = next_acc
                    replacements[initial_acc_id] = next_acc

        worker_count = min(len(active_ids), len(chunks))
        await _run_workers(_kf_worker(aid) for aid in active_ids[:worker_count])
        # Anything still queued was never sent (every worker stopped: halt, no account left): reported, never dropped.
        leftover: List[Tuple[str, List[KeyframeItem], Path]] = []
        while not work_q.empty():
            bid, chunk, out_dir, _attempt = work_q.get_nowait()
            leftover.append((bid, chunk, out_dir))
        if leftover:
            self._note_not_dispatched(leftover, "run halted" if self._halt is not None else "no account left")
        active_ids[:] = [
            replacement
            for aid in active_ids
            if (replacement := replacements.get(aid, aid)) is not None
        ]
        standby_ids[:] = standby_q
        return results

    async def _run_keyframes_async(
        self,
        project_dir: Path,
        max_accounts: Optional[int] = None,
        only_accounts: Optional[Set[str]] = None,
        exclude_accounts: Optional[Set[str]] = None,
        simulate: bool = False,
        include_setups: bool = False,
        session_tag: str = "pool_keyframes",
        include_turnarounds: bool = False,
        clear_halt: bool = False,
        release_unconfirmed: Union[bool, Iterable[str], None] = False,
    ) -> Dict[str, Any]:
        project_dir = Path(project_dir).resolve()
        self._kf_batch_errors: List[Dict[str, Any]] = []
        self._kf_skipped_phases = []
        # Batch ids are unique per run (L38): Muse matches a result card by its zip NAME, and a name an earlier run used
        # may already sit in the chat history. The token also keeps this run out of another run's output dir.
        kf_run_token = secrets.token_hex(3)
        self._kf_ledger, self._kf_ledger_path, self._kf_withheld = None, None, []
        with SessionLock(project_dir, session_tag=session_tag):
            refused = self._halt_gate(project_dir, simulate, clear_halt)
            if refused is not None:
                return refused
            cap = self.inspect_capacity(
                max_accounts=max_accounts,
                only_accounts=only_accounts,
                exclude_accounts=exclude_accounts,
                auto_verify_unchecked=True,
                simulate=simulate,
            )
            active_ids = list(cap["active_account_ids"])
            standby_ids = list(cap["standby_account_ids"])
            if not active_ids or self._halt is not None:
                return {
                    "status": "HALTED" if self._halt is not None else "BLOCKED_NO_ACCOUNTS",
                    "capacity": cap,
                    "anchors_generated": [],
                    "turnarounds_generated": [],
                    "keyframes_generated": [],
                    "rejected": [],
                    "contact_sheets": [],
                }

            dirs = KeyframeComposer.ensure_asset_dirs(project_dir)
            # Images sent by an earlier invocation and never reconciled (crash mid-send, failure or block after the
            # submit keystroke) are withheld. Released only when the image arrived, or by an explicit
            # `release_unconfirmed` (all, or a list of kf ids); `--clear-halt` never releases them.
            if release_unconfirmed is True:
                kf_release_all, kf_release_ids = True, set()
            elif release_unconfirmed:
                kf_release_all, kf_release_ids = False, {str(x) for x in release_unconfirmed}
            else:
                kf_release_all, kf_release_ids = False, set()
            kf_ledger = load_unconfirmed_keyframes(project_dir)
            batch_roots = [d / "_batches" for d in dirs.values()]
            kf_legacy_adopted = adopt_legacy_kf_batches(batch_roots, kf_ledger)
            kf_released: List[Dict[str, Any]] = []
            for entry in kf_ledger:
                if entry.get("status") not in UNCONFIRMED_BLOCKING:
                    continue
                why, evidence = None, None
                if kf_release_all or entry["kf_id"] in kf_release_ids:
                    why = "MANUAL"
                else:
                    # Released only on a verified image of THIS submission (never on a bare `<kf_id>.png`).
                    bid = str(entry.get("batch_id") or "")
                    cands = [Path(entry["out_dir"])] if entry.get("out_dir") else [r / bid for r in batch_roots]
                    for od in cands:
                        evidence = kf_result_image(od, bid, entry["kf_id"], entry.get("submitted_epoch"))
                        if evidence:
                            why = "RESULT_RECEIVED"
                            break
                if why:
                    entry.update({"status": "RELEASED", "reason": why,
                                  "released_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())})
                    if evidence:
                        entry["result"] = evidence
                    kf_released.append(dict(entry))
            if not simulate:
                self._kf_ledger, self._kf_ledger_path = kf_ledger, project_dir / KF_LEDGER_FILE
                if kf_released or kf_legacy_adopted:
                    _write_json_atomic(self._kf_ledger_path, {"entries": kf_ledger})
            else:
                self._kf_ledger = [dict(e) for e in kf_ledger]  # a dry run honours the ledger, never writes it
            bible_path = project_dir / "story_bible.json"
            bible = json.loads(bible_path.read_text(encoding="utf-8"))
            manifest_path = project_dir / "shots_manifest.json"
            manifest = (
                json.loads(manifest_path.read_text(encoding="utf-8"))
                if manifest_path.exists()
                else {"shots": []}
            )
            require_current_staging(manifest)
            client = self.client_factory(self.account_manager)

            async with _warm_pool(client):
                report: Dict[str, Any] = {
                    "status": "COMPLETED",
                    "capacity": cap,
                    "setups_generated": [],
                    "anchors_generated": [],
                    "turnarounds_generated": [],
                    "keyframes_generated": [],
                    "rejected": [],
                    "contact_sheets": [],
                }
                planned_items: List[KeyframeItem] = []  # every image this run was asked to produce
                all_results: List[Dict[str, Any]] = []

                # 0. Sinh song song Master Location Plates nếu bật include_setups hoặc generate_location_plates
                if include_setups or bool(bible.get("generate_location_plates")):
                    missing_plates = KeyframeComposer.plan_missing_location_plates(bible, dirs["setups"])
                    planned_items.extend(missing_plates)
                    if missing_plates:
                        plate_bs = self._compute_balanced_batch_size(len(missing_plates), len(active_ids), KEYFRAME_BATCH_SIZE)
                        plate_chunks = [
                            (
                                f"KF_SETUP_{(i // plate_bs) + 1:02d}_{kf_run_token}",
                                missing_plates[i : i + plate_bs],
                                dirs["setups"] / "_batches" / f"KF_SETUP_{(i // plate_bs) + 1:02d}_{kf_run_token}",
                            )
                            for i in range(0, len(missing_plates), plate_bs)
                        ]
                        plate_results = await self._run_kf_chunks_parallel(
                            plate_chunks, active_ids, standby_ids, client, simulate
                        )
                        all_results.extend(plate_results)
                        for res in plate_results:
                            for kf_id, kinfo in res.get("keyframes", {}).items():
                                src_p = Path(kinfo["path"])
                                ok, errs, _ = KeyframeComposer.verify_keyframe_image(src_p)
                                if ok:
                                    dest_p = dirs["setups"] / f"{kf_id}.png"
                                    dest_p.write_bytes(src_p.read_bytes())
                                    report["setups_generated"].append(str(dest_p))
                                else:
                                    report["rejected"].append({"id": kf_id, "errors": errs})
                    all_setups = sorted(dirs["setups"].glob("*.png"))
                    if all_setups:
                        cs_s = KeyframeComposer.build_contact_sheet(
                            all_setups, dirs["setups"] / "setups_contact_sheet.jpg"
                        )
                        if cs_s:
                            report["contact_sheets"].append(str(cs_s))

                # 1. Sinh song song Character Anchors (N tài khoản x 4 ảnh đồng thời)
                missing_anchors = KeyframeComposer.plan_missing_character_anchors(bible, dirs["anchors"])
                planned_items.extend(missing_anchors)
                if missing_anchors:
                    anc_bs = self._compute_balanced_batch_size(len(missing_anchors), len(active_ids), KEYFRAME_BATCH_SIZE)
                    anchor_chunks = [
                        (
                            f"KF_ANCHOR_{(i // anc_bs) + 1:02d}_{kf_run_token}",
                            missing_anchors[i : i + anc_bs],
                            dirs["anchors"] / "_batches" / f"KF_ANCHOR_{(i // anc_bs) + 1:02d}_{kf_run_token}",
                        )
                        for i in range(0, len(missing_anchors), anc_bs)
                    ]
                    anchor_results = await self._run_kf_chunks_parallel(
                        anchor_chunks, active_ids, standby_ids, client, simulate
                    )
                    all_results.extend(anchor_results)
                    for res in anchor_results:
                        for kf_id, kinfo in res.get("keyframes", {}).items():
                            src_p = Path(kinfo["path"])
                            ok, errs, _ = KeyframeComposer.verify_keyframe_image(src_p)
                            if ok:
                                dest_p = dirs["anchors"] / f"{kf_id}.png"
                                dest_p.write_bytes(src_p.read_bytes())
                                report["anchors_generated"].append(str(dest_p))
                            else:
                                report["rejected"].append({"id": kf_id, "errors": errs})

                if include_turnarounds:
                    turnarounds = KeyframeComposer.plan_missing_character_turnarounds(bible, dirs["anchors"])
                    batch_size = self._compute_balanced_batch_size(
                        len(turnarounds), len(active_ids), KEYFRAME_BATCH_SIZE
                    )
                    chunks = []
                    for offset in range(0, len(turnarounds), batch_size):
                        batch_id = f"KF_TURN_{offset // batch_size + 1:02d}_{kf_run_token}"
                        chunks.append((
                            batch_id,
                            turnarounds[offset : offset + batch_size],
                            dirs["anchors"] / "_batches" / batch_id,
                        ))
                    results = await self._run_kf_chunks_parallel(chunks, active_ids, standby_ids, client, simulate)
                    KeyframeComposer.save_character_turnarounds(
                        bible_path, bible, dirs["anchors"], turnarounds, results, report
                    )

                # 2. Sinh song song Scene Keyframes (N tài khoản x 4 ảnh đồng thời)
                missing_kfs = KeyframeComposer.plan_missing_scene_keyframes(bible, manifest, project_dir)
                planned_items.extend(missing_kfs)
                kf_index_path = dirs["keyframes"] / "keyframes_index.json"
                kf_index: Dict[str, str] = (
                    json.loads(kf_index_path.read_text(encoding="utf-8")) if kf_index_path.exists() else {}
                )
                if missing_kfs:
                    sc_bs = self._compute_balanced_batch_size(len(missing_kfs), len(active_ids), KEYFRAME_BATCH_SIZE)
                    scene_chunks = [
                        (
                            f"KF_SCENE_{(i // sc_bs) + 1:02d}_{kf_run_token}",
                            missing_kfs[i : i + sc_bs],
                            dirs["keyframes"] / "_batches" / f"KF_SCENE_{(i // sc_bs) + 1:02d}_{kf_run_token}",
                        )
                        for i in range(0, len(missing_kfs), sc_bs)
                    ]
                    scene_results = await self._run_kf_chunks_parallel(
                        scene_chunks, active_ids, standby_ids, client, simulate
                    )
                    all_results.extend(scene_results)
                    for res in scene_results:
                        for kf_id, kinfo in res.get("keyframes", {}).items():
                            src_p = Path(kinfo["path"])
                            ok, errs, _ = KeyframeComposer.verify_keyframe_image(src_p)
                            if ok:
                                dest_p = dirs["keyframes"] / f"{kf_id}.png"
                                dest_p.write_bytes(src_p.read_bytes())
                                kf_index[kf_id] = str(dest_p)
                                report["keyframes_generated"].append(str(dest_p))
                            else:
                                report["rejected"].append({"id": kf_id, "errors": errs})
                    _write_json_atomic(kf_index_path, kf_index)

                # 3. Xuất Contact Sheet duyệt thị giác cho Gemini Agent
                all_anchors = sorted(dirs["anchors"].glob("*.png"))
                all_kfs = sorted(dirs["keyframes"].glob("*.png"))
                if all_anchors:
                    cs_a = KeyframeComposer.build_contact_sheet(
                        all_anchors, dirs["anchors"] / "anchors_contact_sheet.jpg"
                    )
                    if cs_a:
                        report["contact_sheets"].append(str(cs_a))
                if all_kfs:
                    cs_k = KeyframeComposer.build_contact_sheet(
                        all_kfs, dirs["keyframes"] / "keyframes_contact_sheet.jpg"
                    )
                    if cs_k:
                        report["contact_sheets"].append(str(cs_k))

                # Every planned image must be produced and verified; anything else is not COMPLETED.
                produced = {
                    Path(x).stem
                    for key in ("setups_generated", "anchors_generated", "keyframes_generated")
                    for x in report[key]
                }
                rejected_ids = {r.get("id") for r in report["rejected"]}
                report["unconfirmed_keyframes"] = [
                    dict(e) for e in self._kf_ledger or [] if e.get("status") in UNCONFIRMED_BLOCKING
                ]
                report["withheld_keyframes"] = sorted(set(self._kf_withheld))
                if kf_released:
                    report["unconfirmed_released"] = kf_released
                if kf_legacy_adopted:
                    report["kf_legacy_adopted"] = [e["kf_id"] for e in kf_legacy_adopted]
                report["missing_keyframes"] = sorted(
                    {k.kf_id for k in planned_items} - produced - rejected_ids
                )
                report["batch_errors"] = list(self._kf_batch_errors) + [
                    {"batch_id": r.get("batch_id"), "errors": r.get("errors"),
                     "missing_keyframes": r.get("missing_keyframes")}
                    for r in all_results
                    if r.get("verified") is False or r.get("errors") or r.get("missing_keyframes")
                ]
                if self._kf_skipped_phases:
                    report["skipped_phases"] = list(self._kf_skipped_phases)
                    report["skipped_phases_note"] = (
                        "later phases did nothing because no account was left to send (or the run halted): "
                        + ", ".join(self._kf_skipped_phases)
                    )
                if report["missing_keyframes"]:
                    report["status"] = "INCOMPLETE"
                elif report["rejected"]:
                    report["status"] = "PARTIAL_REJECTED"
                elif self._kf_batch_errors or self._kf_skipped_phases or any(
                    r.get("verified") is False for r in all_results
                ):
                    report["status"] = "INCOMPLETE"
                return report

    async def _run_videos_async(
        self,
        project_dir: Path,
        max_accounts: Optional[int] = None,
        only_accounts: Optional[Set[str]] = None,
        exclude_accounts: Optional[Set[str]] = None,
        max_rounds: int = 3,
        auto_repair: bool = True,
        simulate: bool = False,
        session_tag: str = "pool_videos",
        takes: int = 1,
        release_unconfirmed: Union[bool, Iterable[str], None] = False,
        unconfirmed_ttl_min: Optional[float] = None,
        clear_halt: bool = False,
    ) -> Dict[str, Any]:
        project_dir = Path(project_dir).resolve()
        with SessionLock(project_dir, session_tag=session_tag):
            manifest_path = project_dir / "shots_manifest.json"
            if not manifest_path.exists():
                raise FileNotFoundError(f"Chưa có shots_manifest.json tại {project_dir}")

            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            require_current_staging(manifest)
            shots_by_id: Dict[str, Dict[str, Any]] = {s["shot_id"]: s for s in manifest.get("shots", [])}
            total_shots = len(manifest.get("shots", []))

            canonical_dir = project_dir / "verified_clips"
            canonical_dir.mkdir(parents=True, exist_ok=True)
            strips_dir = project_dir / "qc_strips"
            strips_dir.mkdir(parents=True, exist_ok=True)
            audit_path = project_dir / "qc_audit_report.json"

            passed_clips, per_shot_qc, render_fingerprints = _load_render_checkpoint(
                audit_path, shots_by_id, simulate
            )
            refused = self._halt_gate(project_dir, simulate, clear_halt)
            if refused is not None:
                return {
                    **refused,
                    "total_shots": total_shots,
                    "passed_count": len(passed_clips),
                    "remaining_shot_ids": [
                        s["shot_id"] for s in manifest.get("shots", []) if s["shot_id"] not in passed_clips
                    ],
                }

            # Sends of earlier invocations that are not reconciled (crash mid-send, failure after the submit keystroke,
            # or an old-code batch dir without result) block a resend. They are released only when the shot passed,
            # the design changed, the shot was removed, the result arrived, or by an explicit `release_unconfirmed`
            # (all, or a list of shot ids) after checking Muse. Past the TTL an entry becomes
            # `EXPIRED_NEEDS_RECONCILE`: reported, still blocking. Entries are kept as history. A dry run never writes.
            ledger_path = project_dir / UNCONFIRMED_FILE
            ttl_min = resolve_unconfirmed_ttl_min(unconfirmed_ttl_min)
            ledger_existed = ledger_path.exists()
            if release_unconfirmed is True:
                release_all, release_ids = True, set()
            elif release_unconfirmed:
                release_all, release_ids = False, {str(x) for x in release_unconfirmed}
            else:
                release_all, release_ids = False, set()
            now_s = time.time()
            ledger_entries: List[Dict[str, Any]] = load_unconfirmed_submissions(project_dir)
            if not ledger_existed:
                ledger_entries.extend(legacy_inflight_batches(project_dir, shots_by_id))
            unconfirmed_released: List[Dict[str, Any]] = []
            for entry in ledger_entries:
                if entry.get("status") not in UNCONFIRMED_BLOCKING:
                    continue
                e_sid = entry.get("shot_id")
                e_shot = shots_by_id.get(e_sid)
                age_min = round((now_s - float(entry.get("submitted_epoch") or 0.0)) / 60.0, 1)
                why = None
                if release_all or e_sid in release_ids:
                    why = "MANUAL"
                elif e_shot is None:
                    why = "SHOT_REMOVED"
                elif e_sid in passed_clips:
                    why = "RECONCILED_PASSED"
                elif entry.get("fingerprint") and entry["fingerprint"] != _render_fingerprint(e_shot, False):
                    why = "STALE_DESIGN"
                result_state = (
                    _batch_result_state(project_dir / "BATCHES_V2" / entry["batch_id"])
                    if entry.get("batch_id") else "NONE"
                )
                if not why and result_state == "ARRIVED":
                    why = "RESULT_RECEIVED"
                if why and why != "MANUAL" and entry.get("integrity_failure"):
                    # Flagged by an INTEGRITY_UNPERSISTED stop: only an explicit manual release frees it.
                    why = None
                if why:
                    entry.update({
                        "status": "RELEASED", "reason": why, "age_min": age_min,
                        "released_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(now_s)),
                    })
                    unconfirmed_released.append(dict(entry))
                elif result_state == "CORRUPT":
                    # A broken result proves nothing about the earlier generation: still blocking until reconciled.
                    entry.update({"status": "RESULT_CORRUPT", "age_min": age_min})
                elif age_min > ttl_min:
                    entry.update({"status": "EXPIRED_NEEDS_RECONCILE", "age_min": age_min})
            unconfirmed_entries = [e for e in ledger_entries if e.get("status") in UNCONFIRMED_BLOCKING]
            if not simulate and ledger_entries:
                # Persist releases / expiries / adopted legacy batches now, even if nothing is sent below.
                _write_json_atomic(ledger_path, {"ttl_min": ttl_min, "entries": ledger_entries})
            blocked_ids = {e["shot_id"] for e in unconfirmed_entries}

            remaining_ids = [
                s["shot_id"] for s in manifest.get("shots", [])
                if s["shot_id"] not in passed_clips and s["shot_id"] not in blocked_ids
            ]
            client = self.client_factory(self.account_manager)
            async with _warm_pool(client):
                # Unique per invocation (date, time, random): a batch dir is never reused by another run.
                run_tag = f"{time.strftime('%y%m%d%H%M%S')}{secrets.token_hex(3)}"
                repair_logs: List[Dict[str, Any]] = []
                last_cap: Dict[str, Any] = {}
                # Sends per shot in this run. A shot whose batch reached Muse but whose result was not reconciled
                # (failure after submission) is never resent in this run: it is reported for collection/review.
                sends_by_shot: Dict[str, int] = {}
                # Planned independent takes per shot per round: the manifest `takes` field wins over `--takes`.
                takes_by_shot: Dict[str, int] = {}

                def _takes_for(sid: str) -> int:
                    raw = shots_by_id.get(sid, {}).get("takes")
                    # Only a real integer >= 1 overrides the flag (bool, 0, negative, float, str fall back to it).
                    if isinstance(raw, int) and not isinstance(raw, bool) and raw >= 1:
                        return raw
                    try:
                        return max(1, int(takes or 1))
                    except (TypeError, ValueError):
                        return 1

                def _take_score(qc_res: Dict[str, Any]) -> float:
                    return float(((qc_res or {}).get("metrics") or {}).get("quality_score") or 0.0)

                batch_errors_all: List[str] = []
                submitted_unconfirmed: Set[str] = set(blocked_ids)
                fail_reason: Dict[str, str] = {sid: "SUBMITTED_UNCONFIRMED" for sid in blocked_ids}
                # Every QC'd take per shot (source clip, fingerprint, strip), stored as `per_shot_qc[sid].candidates`.
                cand_log: Dict[str, List[Dict[str, Any]]] = {
                    sid: list((rec or {}).get("candidates") or []) for sid, rec in per_shot_qc.items()
                }

                def _count_send(chunk_items) -> None:
                    for c in chunk_items:
                        sends_by_shot[c.shot_id] = sends_by_shot.get(c.shot_id, 0) + 1

                ledger_by_key: Dict[Tuple[str, str], Dict[str, Any]] = {}

                def _ledger_mark(bid: str, chunk_items, take_idx: int, fps: Dict[str, str], status: str,
                                 **extra: Any) -> None:
                    stamp = time.time()
                    for c in chunk_items:
                        e = ledger_by_key.get((bid, c.shot_id))
                        if e is None:
                            e = {
                                "shot_id": c.shot_id,
                                "batch_id": bid,
                                "take": take_idx + 1,
                                "submitted_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(stamp)),
                                "submitted_epoch": stamp,
                                "fingerprint": fps.get(c.shot_id),
                            }
                            ledger_by_key[(bid, c.shot_id)] = e
                            ledger_entries.append(e)
                        e["status"] = status
                        if status == "RESOLVED":
                            e["resolved_at"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(stamp))
                        e.update(extra)

                def _write_ledger() -> None:
                    if not simulate and (ledger_existed or ledger_entries):
                        _write_json_atomic(ledger_path, {"ttl_min": ttl_min, "entries": ledger_entries})

                def _record_unconfirmed(bid: str, chunk_items, take_idx: int, fps: Dict[str, str], exc) -> None:
                    _count_send(chunk_items)
                    for c in chunk_items:
                        submitted_unconfirmed.add(c.shot_id)
                        fail_reason[c.shot_id] = "SUBMITTED_UNCONFIRMED"
                    _ledger_mark(bid, chunk_items, take_idx, fps, "UNCONFIRMED", error=str(exc)[:300])

                def _open_unconfirmed() -> List[Dict[str, Any]]:
                    return [
                        e for e in ledger_entries
                        if e.get("status") in UNCONFIRMED_BLOCKING and e["shot_id"] not in passed_clips
                    ]

                def _flush_checkpoint() -> None:
                    for c_sid, c_list in cand_log.items():
                        if c_sid in per_shot_qc:
                            per_shot_qc[c_sid]["candidates"] = c_list
                    _write_ledger()
                    pending_now = [s["shot_id"] for s in manifest.get("shots", []) if s["shot_id"] not in passed_clips]
                    _write_json_atomic(
                        audit_path,
                        {
                            "total_shots": total_shots,
                            "passed_count": len(passed_clips),
                            "failed_or_missing_count": len(pending_now),
                            "passed_clips": passed_clips,
                            "render_fingerprints": render_fingerprints,
                            "per_shot_qc": per_shot_qc,
                            "failed_or_missing": [
                                {
                                    "shot_id": x,
                                    "reason": "QC_REJECT" if x in per_shot_qc else "PENDING_OR_MISSING",
                                    "defects": (per_shot_qc.get(x) or {}).get("defects", []),
                                }
                                for x in pending_now
                            ],
                        },
                    )

                round_num = 1
                remaining_ids = list(remaining_ids)
                while remaining_ids and round_num <= max_rounds:
                    last_cap = self.inspect_capacity(
                        max_accounts=max_accounts,
                        only_accounts=only_accounts,
                        exclude_accounts=exclude_accounts,
                        auto_verify_unchecked=(round_num == 1),
                        simulate=simulate,
                        owned_profile_ids=getattr(client, "warm_account_ids", None),
                    )
                    if self._halt is not None:
                        break  # blocked at login: nothing is dispatched
                    active_ids = last_cap["active_account_ids"]
                    warm_accounts = getattr(client, "warm_account_ids", set())
                    if warm_accounts.difference(active_ids):
                        await client.close_all_sessions(keep_account_ids=active_ids)
                    standby_q: Deque[str] = deque(last_cap["standby_account_ids"])
                    if not active_ids:
                        _flush_checkpoint()
                        return {
                            "status": "BLOCKED_NO_ACCOUNTS",
                            "total_shots": total_shots,
                            "passed_count": len(passed_clips),
                            "remaining_shot_ids": remaining_ids,
                            "sends_by_shot": dict(sorted(sends_by_shot.items())),
                            "takes_by_shot": dict(sorted(takes_by_shot.items())),
                            "submitted_unconfirmed_shot_ids": sorted(submitted_unconfirmed - set(passed_clips)),
                            "unconfirmed_submissions": _open_unconfirmed(),
                            "unconfirmed_expired": [
                                e for e in _open_unconfirmed() if e.get("status") == "EXPIRED_NEEDS_RECONCILE"
                            ],
                            "unconfirmed_released": unconfirmed_released,
                            "unconfirmed_ttl_min": ttl_min,
                            "batch_errors": batch_errors_all,
                            "capacity": last_cap,
                            "repair_logs": repair_logs,
                        }

                    # Đóng gói hàng đợi động (N x 6 khi hàng đợi lớn, hoặc tự cân bằng tải khi số shot ít ở vòng retry)
                    def _shot_item(sid: str) -> ShotItem:
                        return ShotItem(
                            shot_id=sid,
                            prompt=shots_by_id[sid]["compiled_prompt"],
                            first_frame_path=Path(shots_by_id[sid]["first_frame_path"]),
                            duration_s=float(shots_by_id[sid].get("duration_s", 10.0)),
                            dialogue=shots_by_id[sid].get("dialogue") or "",
                            speaker=shots_by_id[sid].get("speaker") or "",
                            audio_mode=shots_by_id[sid].get("audio_mode") or "NATIVE_DIALOGUE",
                            extra_refs=[
                                Path(r)
                                for r in (shots_by_id[sid].get("extra_refs") or [])
                                if r and Path(r).exists()
                            ],
                        )

                    # Take k of every shot forms one layer; a batch never holds the same shot twice (results are
                    # keyed by shot_id), and layers run concurrently on different accounts.
                    for sid in remaining_ids:
                        takes_by_shot[sid] = _takes_for(sid)
                    max_take = max((takes_by_shot[sid] for sid in remaining_ids), default=1)
                    layers = [
                        [_shot_item(sid) for sid in remaining_ids if takes_by_shot[sid] > k] for k in range(max_take)
                    ]
                    total_items = sum(len(layer) for layer in layers)
                    vid_bs = self._compute_balanced_batch_size(total_items, len(active_ids), VIDEO_BATCH_SIZE)
                    work_q: asyncio.Queue = asyncio.Queue()
                    num_batches = 0
                    for take_idx, layer in enumerate(layers):
                        for i in range(0, len(layer), vid_bs):
                            chunk = layer[i : i + vid_bs]
                            num_batches += 1
                            take_tag = f"_T{take_idx + 1}" if max_take > 1 else ""
                            bid = f"POOL_{run_tag}_R{round_num:02d}_B{num_batches:02d}{take_tag}"
                            work_q.put_nowait((bid, chunk, 0, take_idx))

                    round_defects: Dict[str, List[str]] = {}
                    failed_in_round: Set[str] = set()
                    batch_errors = batch_errors_all

                    async def _video_worker(initial_acc_id: str) -> None:
                        cur_acc: Optional[str] = initial_acc_id
                        while cur_acc is not None:
                            if self._halt is not None or self._integrity_stop:
                                break  # a block anywhere stops every worker (in-flight batches finish)
                            if not self._account_allowed(cur_acc):
                                # Lease lost/expired (or taken by a lane): stop dispatching on this account.
                                cur_acc = self._pick_standby(standby_q, simulate)
                                continue
                            try:
                                bid, chunk, fo_attempt, take_idx = work_q.get_nowait()
                            except asyncio.QueueEmpty:
                                break

                            # A batch dir is created exclusively: an existing batch (its clips, its fingerprint
                            # sidecar) is never reused or overwritten.
                            prefix = f"POOL_{run_tag}"
                            while True:
                                out_dir = project_dir / "BATCHES_V2" / bid
                                try:
                                    out_dir.mkdir(parents=True, exist_ok=False)
                                    break
                                except FileExistsError:
                                    tail = bid[len(prefix):] if bid.startswith(prefix) else f"_{bid}"
                                    bid = f"{prefix}{secrets.token_hex(2)}{tail}"
                            # Design fingerprint of every shot at send time: qc-audit only accepts takes whose
                            # fingerprint matches the current design.
                            fps = {c.shot_id: _render_fingerprint(shots_by_id[c.shot_id], simulate) for c in chunk}
                            _write_json_atomic(
                                out_dir / BATCH_FINGERPRINTS_FILE,
                                {"batch_id": bid, "take": take_idx + 1, "simulate": simulate, "shots": fps},
                            )
                            if not simulate:
                                # Durable record before the send: a crash from here on leaves PENDING_SEND, which
                                # blocks a resend on resume until reconciled.
                                _ledger_mark(bid, chunk, take_idx, fps, "PENDING_SEND")
                                _write_ledger()
                            kw: Dict[str, Any] = {}
                            if _accepts_kw(client.generate_videos_batch, "lease_guard"):
                                # Checked by the client right before the submit keystroke.
                                kw["lease_guard"] = lambda acc=cur_acc: self._send_allowed(acc)
                            try:
                                wres = await client.generate_videos_batch(
                                    account_id=cur_acc,
                                    shots=chunk,
                                    batch_id=bid,
                                    output_dir=out_dir,
                                    timeout_seconds=HeadlessMuseClient.compute_adaptive_timeout(len(chunk), is_video=True),
                                    simulate=simulate,
                                    **kw,
                                )
                            except BlockedException as exc:
                                # CAPTCHA / verification page: never re-queued, never handed to a standby account.
                                if _was_submitted(exc):
                                    _record_unconfirmed(bid, chunk, take_idx, fps, exc)
                                    batch_errors.append(f"{bid} ({cur_acc}) submitted, then blocked: {exc}")
                                else:
                                    _ledger_mark(bid, chunk, take_idx, fps, "RESOLVED", reason="NOT_SENT")
                                    failed_in_round.update(c.shot_id for c in chunk)
                                    for c in chunk:
                                        fail_reason[c.shot_id] = "HALTED_BLOCKED"
                                    batch_errors.append(f"{bid} ({cur_acc}) blocked before send: {exc}")
                                self._on_blocked(exc, cur_acc, bid)
                                _flush_checkpoint()
                                break
                            except (QuotaExceededException, SessionInvalidException, LeaseLostException) as exc:
                                self._adopt_halt_refusal(exc, cur_acc, bid)
                                if self._halt is not None and not _was_submitted(exc):
                                    # Another account was blocked meanwhile (the submit guard refused): not sent.
                                    _ledger_mark(bid, chunk, take_idx, fps, "RESOLVED", reason="NOT_SENT")
                                    failed_in_round.update(c.shot_id for c in chunk)
                                    for c in chunk:
                                        fail_reason[c.shot_id] = "HALTED_BLOCKED"
                                    batch_errors.append(f"{bid} ({cur_acc}) not sent, run halted: {exc}")
                                    _flush_checkpoint()
                                    break
                                if _was_submitted(exc):
                                    # Batch reached Muse: reconcile later, never resend it (persisted in the ledger).
                                    _record_unconfirmed(bid, chunk, take_idx, fps, exc)
                                    batch_errors.append(f"{bid} ({cur_acc}) submitted, no result: {exc}")
                                    _flush_checkpoint()
                                elif fo_attempt < 2:
                                    _ledger_mark(bid, chunk, take_idx, fps, "RESOLVED", reason="NOT_SENT")
                                    # Not sent: hand the batch to a standby / healthy account right away.
                                    work_q.put_nowait((f"{bid}_FO{fo_attempt + 1}", chunk, fo_attempt + 1, take_idx))
                                else:
                                    _ledger_mark(bid, chunk, take_idx, fps, "RESOLVED", reason="NOT_SENT")
                                    failed_in_round.update(c.shot_id for c in chunk)
                                    for c in chunk:
                                        fail_reason[c.shot_id] = "NOT_DISPATCHED"
                                    batch_errors.append(
                                        f"{bid} ({cur_acc}) not sent, failover exhausted: {exc}")
                                    _write_ledger()
                                cur_acc = self._pick_standby(standby_q, simulate)
                                continue
                            except IntegrityUnpersistedError as exc:
                                # A received clip failed its SHA-256 and could be neither listed nor quarantined:
                                # the batch is UNCONFIRMED (never RESULT) and the whole run STOPS.
                                _record_unconfirmed(bid, chunk, take_idx, fps, exc)
                                # Flag the entries: the next run sees the un-quarantined MP4 as ARRIVED, which must
                                # never auto-release a ledger entry that failed integrity (only a MANUAL release can).
                                _ledger_mark(bid, chunk, take_idx, fps, "UNCONFIRMED", error=str(exc)[:300],
                                             integrity_failure=INTEGRITY_UNPERSISTED_STATUS)
                                self._integrity_stop.append(
                                    {"batch_id": bid, "account_id": cur_acc, "clips": list(exc.clips),
                                     "error": str(exc)[:300]})
                                batch_errors.append(f"{bid} ({cur_acc}) {INTEGRITY_UNPERSISTED_STATUS}: {exc}")
                                _flush_checkpoint()
                                break
                            except Exception as exc:
                                batch_errors.append(f"{bid} ({cur_acc}): {exc}")
                                failed_in_round.update(c.shot_id for c in chunk)
                                if self._halt is not None and not _was_submitted(exc):
                                    _ledger_mark(bid, chunk, take_idx, fps, "RESOLVED", reason="NOT_SENT")
                                    for c in chunk:
                                        fail_reason[c.shot_id] = "HALTED_BLOCKED"
                                    _flush_checkpoint()
                                    break
                                if _was_submitted(exc):
                                    _record_unconfirmed(bid, chunk, take_idx, fps, exc)
                                else:
                                    _ledger_mark(bid, chunk, take_idx, fps, "RESOLVED", reason="NOT_SENT")
                                    for c in chunk:
                                        fail_reason[c.shot_id] = "BATCH_ERROR"
                                _flush_checkpoint()
                                continue

                            _count_send(chunk)

                            vmap = wres.get("verified_shots", {})
                            integrity_failed = set(wres.get("integrity_failed_shots") or [])
                            for item in chunk:
                                sid = item.shot_id
                                vinfo = vmap.get(sid)
                                if not vinfo:
                                    failed_in_round.add(sid)
                                    fail_reason[sid] = (
                                        "INTEGRITY_FAILED" if sid in integrity_failed else "NO_RESULT_IN_BATCH"
                                    )
                                    continue

                                cpath = Path(vinfo["path"])
                                dest = canonical_dir / f"{sid}.mp4"
                                if simulate:
                                    if sid not in passed_clips:
                                        shutil.copyfile(cpath, dest)
                                        passed_clips[sid] = str(dest)
                                        render_fingerprints[sid] = fps[sid]
                                    failed_in_round.discard(sid)
                                    round_defects.pop(sid, None)
                                    continue

                                # Every take writes its own strip (named by batch, never rewritten), and only the take
                                # that becomes the shot's QC record is copied to the canonical name.
                                canonical_strip = strips_dir / f"{sid}_strip.jpg"
                                strip_path = strips_dir / f"{sid}_{bid}_strip.jpg"

                                def _promote_strip() -> None:
                                    if strip_path.exists():
                                        shutil.copyfile(strip_path, canonical_strip)
                                    elif canonical_strip.exists():
                                        canonical_strip.unlink()  # never leave another take's strip in place

                                qc_res = self.qc_evaluator(
                                    cpath,
                                    shots_by_id[sid],
                                    min_duration_s=2.5 if item.duration_s <= 5.5 else 3.0,
                                    strip_output_path=strip_path,
                                )
                                qc_res = {**qc_res, "take": take_idx + 1, "clip_path": str(cpath), "batch_id": bid}
                                cand_log.setdefault(sid, []).append({
                                    "take": take_idx + 1,
                                    "batch_id": bid,
                                    "clip_path": str(cpath),
                                    "verdict": qc_res.get("verdict"),
                                    "quality_score": _take_score(qc_res),
                                    "defects": list(qc_res.get("defects") or []),
                                    "metrics": dict(qc_res.get("metrics") or {}),
                                    "fingerprint": fps[sid],
                                    "strip_path": str(strip_path) if strip_path.exists() else None,
                                    "sha256": vinfo.get("sha256") or compute_sha256(cpath),
                                })
                                if qc_res.get("verdict") == "PASS":
                                    prev = per_shot_qc.get(sid) or {}
                                    already = sid in passed_clips and prev.get("verdict") == "PASS"
                                    # Several takes may pass: keep the highest quality_score as the canonical clip.
                                    if not already or _take_score(qc_res) > _take_score(prev):
                                        shutil.copyfile(cpath, dest)
                                        _promote_strip()
                                        passed_clips[sid] = str(dest)
                                        per_shot_qc[sid] = qc_res
                                        render_fingerprints[sid] = fps[sid]
                                    failed_in_round.discard(sid)
                                    round_defects.pop(sid, None)
                                    fail_reason.pop(sid, None)
                                elif sid not in passed_clips:
                                    # A rejected take never overwrites a passing take's QC record or strip.
                                    _promote_strip()
                                    per_shot_qc[sid] = qc_res
                                    defs = list(qc_res.get("defects") or ["QC_REJECT"])
                                    round_defects[sid] = defs
                                    failed_in_round.add(sid)
                                    fail_reason[sid] = "QC_REJECT"

                            if not simulate:
                                _ledger_mark(bid, chunk, take_idx, fps, "RESOLVED", reason="RESULT_RECEIVED")
                            _flush_checkpoint()

                    worker_count = min(len(active_ids), num_batches)
                    await _run_workers(_video_worker(aid) for aid in active_ids[:worker_count])

                    # Rút nốt các lô còn sót nếu toàn bộ worker cạn quota giữa vòng
                    while not work_q.empty():
                        rem_bid, rem_chunk, _, _ = work_q.get_nowait()
                        batch_errors.append(
                            f"{rem_bid} not sent: "
                            f"{'run halted' if self._halt else 'no account left'} "
                            f"(shots {', '.join(c.shot_id for c in rem_chunk)})"
                        )
                        failed_in_round.update(c.shot_id for c in rem_chunk)
                        for c in rem_chunk:
                            fail_reason.setdefault(c.shot_id, "HALTED_BLOCKED" if self._halt else "NOT_DISPATCHED")

                    _flush_checkpoint()
                    if self._halt is not None or self._integrity_stop:
                        break  # no further round, no repair
                    remaining_ids = [
                        s["shot_id"] for s in manifest.get("shots", []) if s["shot_id"] not in passed_clips
                    ]
                    # Retry rounds never resend a shot whose earlier send is still unreconciled.
                    retry_ids = [sid for sid in remaining_ids if sid not in submitted_unconfirmed]

                    if auto_repair and round_defects and remaining_ids and round_num < max_rounds:
                        rep_info = PromptRepairAgent.repair_manifest_shots(manifest, round_defects)
                        _write_json_atomic(manifest_path, manifest)
                        shots_by_id = {s["shot_id"]: s for s in manifest.get("shots", [])}
                        repair_logs.append({"round": round_num, **rep_info})

                    round_num += 1
                    if not retry_ids:
                        break
                    remaining_ids = retry_ids

                if self.sync_ui:
                    try:
                        from ..cli import sync_project_to_web_ui
                        sync_project_to_web_ui(project_dir)
                    except Exception:
                        pass

                remaining_ids = [
                    s["shot_id"] for s in manifest.get("shots", []) if s["shot_id"] not in passed_clips
                ]
                status = "COMPLETED" if not remaining_ids else "INCOMPLETE"
                return {
                    "status": status,
                    "total_shots": total_shots,
                    "passed_count": len(passed_clips),
                    "remaining_shot_ids": remaining_ids,
                    "failed_shots": [
                        {
                            "shot_id": sid,
                            "reason": fail_reason.get(sid, "PENDING_OR_MISSING"),
                            "defects": (per_shot_qc.get(sid) or {}).get("defects", []),
                        }
                        for sid in remaining_ids
                    ],
                    "sends_by_shot": dict(sorted(sends_by_shot.items())),
                    "takes_by_shot": dict(sorted(takes_by_shot.items())),
                    "submitted_unconfirmed_shot_ids": sorted(submitted_unconfirmed - set(passed_clips)),
                    "unconfirmed_submissions": _open_unconfirmed(),
                    "unconfirmed_expired": [
                        e for e in _open_unconfirmed() if e.get("status") == "EXPIRED_NEEDS_RECONCILE"
                    ],
                    "unconfirmed_released": unconfirmed_released,
                    "unconfirmed_ttl_min": ttl_min,
                    "batch_errors": batch_errors_all,
                    "qc_audit_report": str(audit_path),
                    "qc_strips_dir": str(strips_dir),
                    "capacity": last_cap,
                    "repair_logs": repair_logs,
                }

    async def _run_with_lane(self, coro_fn, **kwargs) -> Dict[str, Any]:
        self.lease_conflicts = set()
        self._halt = self._halt_ctx = self._halt_seen = self._halt_cleared = None
        self._integrity_stop = []
        async with self._lane_heartbeat():
            res = await coro_fn(**kwargs)
        if self._integrity_stop:
            res["integrity_unpersisted"] = list(self._integrity_stop)
            if self._halt is None:
                res["status"] = INTEGRITY_UNPERSISTED_STATUS
        if self._halt is not None:
            res["status"] = "HALTED"
            res["halted"] = dict(self._halt)
        if self._halt_seen is not None:
            res["halt_file"] = self._halt_seen
        if self._halt_cleared is not None:
            res["halt_cleared"] = self._halt_cleared
        return self._with_lease_report(res)

    def run_keyframes(self, **kwargs) -> Dict[str, Any]:
        return asyncio.run(self._run_with_lane(self._run_keyframes_async, **kwargs))

    def run_videos(self, **kwargs) -> Dict[str, Any]:
        return asyncio.run(self._run_with_lane(self._run_videos_async, **kwargs))
