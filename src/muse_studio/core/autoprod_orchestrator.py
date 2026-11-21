"""
Zero-Talk End-to-End Autoprod Orchestrator & Multi-Session Conflict Guards.
Điều phối khép kín từ 1 file kịch bản thô (.txt/.md/.fountain/.srt) -> Final Master 1080p MP4 + SRT:
  - `SessionLock`: Khóa mức dự án `.autoprod.lock` kèm kiểm tra PID sống thực tế trên OS & tự hồi phục khóa mồ côi.
  - `BusyAccountDetector`: Phát hiện không xâm lấn các profile trình duyệt đang bị khóa bởi phiên Playwright/Chrome khác
    (`lockfile` OS handle / `SingletonLock` / `status == BUSY`) để tránh xung đột tài khoản khi chạy song song nhiều session.
  - `AutoprodOrchestrator`: State Machine lưu checkpoint nguyên tử (`autoprod_state.json`), tích hợp
    `ScriptIngestor` + `ScreenplayCompiler` + `KeyframeComposer` + `FilmQCEngine` + `PromptRepairAgent` + `MasterAssembler`.
"""

import asyncio
import ctypes
import inspect
import json
import os
import re
import shutil
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Set, Tuple

try:
    from .account_manager import AccountManager
    from .batch_packager import BatchPackager, ShotItem, compute_sha256
    from .film_qc_engine import FilmQCEngine
    from .headless_muse_client import BlockedException, HeadlessMuseClient
    from .lane_leases import LeaseRegistry
    from . import send_halt
    from .keyframe_composer import KeyframeComposer
    from .master_assembler import MasterAssembler
    from .prompt_repair_agent import PromptRepairAgent
    from .screenplay_compiler import ScreenplayCompiler
    from .script_ingestor import DIRECTOR_PRESETS, ScriptIngestor
except ImportError:
    from core.account_manager import AccountManager
    from core.batch_packager import BatchPackager, ShotItem, compute_sha256
    from core.film_qc_engine import FilmQCEngine
    from core.headless_muse_client import BlockedException, HeadlessMuseClient
    from core.lane_leases import LeaseRegistry
    from core import send_halt
    from core.keyframe_composer import KeyframeComposer
    from core.master_assembler import MasterAssembler
    from core.prompt_repair_agent import PromptRepairAgent
    from core.screenplay_compiler import ScreenplayCompiler
    from core.script_ingestor import DIRECTOR_PRESETS, ScriptIngestor


class SessionConflictError(RuntimeError):
    """Ném ra khi thư mục dự án đang được một tiến trình `autoprod` sống khác nắm giữ."""


def _write_json_atomic(path: Path, payload: Dict[str, Any]) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = path.with_name(f".{path.name}.tmp.{os.getpid()}")
    tmp_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    os.replace(tmp_path, path)


def _accepts_kw(fn: Any, name: str) -> bool:
    try:
        params = inspect.signature(fn).parameters
    except (TypeError, ValueError):
        return False
    return name in params or any(p.kind is inspect.Parameter.VAR_KEYWORD for p in params.values())


def _pool_ledger():
    """The pool engine's video send ledger API (lazy: the engine module imports this one)."""
    try:
        from . import parallel_pool_engine as ppe
    except ImportError:
        import core.parallel_pool_engine as ppe
    return ppe


def _render_fingerprint(shot: Dict[str, Any], simulate: bool) -> str:
    def file_hash(raw):
        return compute_sha256(Path(raw)) if raw and Path(raw).is_file() else None

    payload = {
        name: shot.get(name) for name in ("compiled_prompt", "duration_s", "audio_mode", "dialogue", "speaker")
    }
    payload.update(
        first_frame=file_hash(shot.get("first_frame_path")),
        extra_refs=[digest for raw in shot.get("extra_refs") or [] if (digest := file_hash(raw))],
        simulate=simulate,
    )
    return compute_sha256(json.dumps(payload, sort_keys=True, ensure_ascii=False).encode("utf-8"))


def _clip_currently_excluded(raw: Any, qc_rec: Any = None) -> bool:
    """True when a clip is on its batch's CURRENT integrity exclusion list (or the list is unreadable): a stale
    qc_audit_report must never revive a clip whose receipt SHA failed. A canonical copy is judged through its audit
    record `qc_rec` (source batch clip + recorded copy SHA); see `BatchPackager.clip_currently_excluded`."""
    return BatchPackager.clip_currently_excluded(Path(raw), qc_rec)


def _load_render_checkpoint(audit_path: Path, shots: Dict[str, Any], simulate: bool):
    if not audit_path.exists():
        return {}, {}, {}

    previous = json.loads(audit_path.read_text(encoding="utf-8"))
    fingerprints = previous.get("render_fingerprints") or {}
    # Every manifest shot has a computable fingerprint, so a verified clip is reusable only when its recorded
    # fingerprint matches the current shot. A missing fingerprint (e.g. dropped by an older qc-audit) is stale.
    stale = {
        sid for sid in set(fingerprints) | set(previous.get("passed_clips") or {})
        if sid in shots and fingerprints.get(sid) != _render_fingerprint(shots[sid], simulate)
    }
    qc_recs = previous.get("per_shot_qc") or {}
    passed = {
        sid: path for sid, path in (previous.get("passed_clips") or {}).items()
        if sid in shots and sid not in stale and Path(path).is_file()
        and not _clip_currently_excluded(path, qc_recs.get(sid))
    }
    diagnostics = {
        sid: qc for sid, qc in (previous.get("per_shot_qc") or {}).items()
        if sid in shots and sid not in stale
    }
    return passed, diagnostics, {sid: fingerprints[sid] for sid in passed if sid in fingerprints}


class SessionLock:
    """Khóa độc quyền trên từng `project_dir` chống 2 session ghi đè nhau, tự thu dọn nếu PID cũ đã chết."""

    LOCK_FILENAME = ".autoprod.lock"

    def __init__(self, project_dir: Path, session_tag: str = "autoprod"):
        self.project_dir = Path(project_dir)
        self.lock_path = self.project_dir / self.LOCK_FILENAME
        self.session_tag = session_tag
        self._acquired = False
        self._fd: Optional[int] = None

    @staticmethod
    def is_pid_alive(pid: int) -> bool:
        if not isinstance(pid, int) or pid <= 0:
            return False
        if pid == os.getpid():
            return True
        if os.name == "nt":
            kernel32 = ctypes.windll.kernel32
            PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
            STILL_ACTIVE = 259
            ERROR_ACCESS_DENIED = 5
            handle = kernel32.OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION, False, pid)
            if not handle:
                return ctypes.GetLastError() == ERROR_ACCESS_DENIED
            try:
                exit_code = ctypes.c_ulong(0)
                if kernel32.GetExitCodeProcess(handle, ctypes.byref(exit_code)):
                    return int(exit_code.value) == STILL_ACTIVE
                return False
            finally:
                kernel32.CloseHandle(handle)
        else:
            try:
                os.kill(pid, 0)
                return True
            except PermissionError:
                return True
            except OSError:
                return False

    # The OS lock covers one byte far past the JSON owner record, so a refused session can still read who holds it.
    _LOCK_OFFSET = 1 << 30

    def _os_lock(self, fd: int) -> bool:
        try:
            if os.name == "nt":
                import msvcrt

                os.lseek(fd, self._LOCK_OFFSET, os.SEEK_SET)
                msvcrt.locking(fd, msvcrt.LK_NBLCK, 1)
            else:
                import fcntl

                fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
            return True
        except OSError:
            return False

    def _os_unlock(self, fd: int) -> None:
        try:
            if os.name == "nt":
                import msvcrt

                os.lseek(fd, self._LOCK_OFFSET, os.SEEK_SET)
                msvcrt.locking(fd, msvcrt.LK_UNLCK, 1)
            else:
                import fcntl

                fcntl.flock(fd, fcntl.LOCK_UN)
        except OSError:
            pass

    def _read_owner(self) -> Dict[str, Any]:
        try:
            data = json.loads(self.lock_path.read_text(encoding="utf-8") or "{}")
            return data if isinstance(data, dict) else {}
        except Exception:
            return {}

    def _conflict(self, owner: Dict[str, Any]) -> SessionConflictError:
        owner_pid = owner.get("pid") or "?"
        owner_tag = owner.get("session_tag") or "unknown"
        return SessionConflictError(
            f"Dự án '{self.project_dir}' đang được nắm giữ bởi phiên '{owner_tag}' (PID {owner_pid})."
        )

    def acquire(self) -> None:
        """Exclusive inter-process lock (msvcrt / fcntl) held for the whole session; never check-then-write."""
        self.project_dir.mkdir(parents=True, exist_ok=True)
        for _ in range(20):
            fd = os.open(str(self.lock_path), os.O_RDWR | os.O_CREAT, 0o644)
            if not self._os_lock(fd):
                os.close(fd)
                raise self._conflict(self._read_owner())
            try:
                same_file = os.path.samestat(os.fstat(fd), os.stat(self.lock_path))
            except OSError:
                same_file = False
            if not same_file:
                # The previous owner removed the file while we were opening it: lock the new one instead.
                self._os_unlock(fd)
                os.close(fd)
                continue
            owner = self._read_owner()
            owner_pid = int(owner.get("pid") or -1) if str(owner.get("pid") or "").lstrip("-").isdigit() else -1
            if not owner.get("os_lock") and owner_pid > 0 and owner_pid != os.getpid() and self.is_pid_alive(owner_pid):
                # A live session of the older file-only lock (no OS lock) still owns the project.
                self._os_unlock(fd)
                os.close(fd)
                raise self._conflict(owner)
            meta = {
                "pid": os.getpid(),
                "session_tag": self.session_tag,
                "started_at": datetime.now().isoformat(),
                "os_lock": True,
            }
            try:
                os.lseek(fd, 0, os.SEEK_SET)
                os.ftruncate(fd, 0)
                os.write(fd, json.dumps(meta, ensure_ascii=False).encode("utf-8"))
                os.fsync(fd)
            except BaseException:
                # Never leak the OS lock when the owner record cannot be written.
                self._os_unlock(fd)
                os.close(fd)
                raise
            self._fd = fd
            self._acquired = True
            return
        raise self._conflict(self._read_owner())

    def release(self) -> None:
        if not self._acquired:
            return
        fd = getattr(self, "_fd", None)
        self._fd = None
        self._acquired = False
        if fd is None:
            return
        if os.name != "nt":
            # POSIX: unlink while still holding the lock, so a waiter that opened the old file re-opens the new one.
            try:
                self.lock_path.unlink()
            except OSError:
                pass
        self._os_unlock(fd)
        os.close(fd)
        if os.name == "nt":
            # Windows refuses to delete a file another session has open; that session then holds the same file.
            try:
                self.lock_path.unlink()
            except OSError:
                pass

    def __enter__(self) -> "SessionLock":
        self.acquire()
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        self.release()


class BusyAccountDetector:
    """Phát hiện không xâm lấn (read-only) các tài khoản đang bận ở session Playwright / Chrome khác."""

    @staticmethod
    def is_profile_locked(profile_dir: Path) -> bool:
        profile_dir = Path(profile_dir)
        if not profile_dir.exists():
            return False

        # POSIX Chromium SingletonLock
        singleton = profile_dir / "SingletonLock"
        if singleton.exists() or singleton.is_symlink():
            return True

        # Windows Chromium `lockfile` (chỉ kiểm tra read-only với dwShareMode=0, tuyệt đối không ghi/xóa)
        lockfile = profile_dir / "lockfile"
        if lockfile.exists():
            if os.name == "nt":
                kernel32 = ctypes.windll.kernel32
                GENERIC_READ = 0x80000000
                OPEN_EXISTING = 3
                INVALID_HANDLE_VALUE = ctypes.c_void_p(-1).value
                handle = kernel32.CreateFileW(
                    str(lockfile),
                    GENERIC_READ,
                    0,  # Không cho phép chia sẻ -> báo lỗi ngay nếu tiến trình khác đang giữ file
                    None,
                    OPEN_EXISTING,
                    0,
                    None,
                )
                if handle == INVALID_HANDLE_VALUE or handle in (-1, 0):
                    return True
                kernel32.CloseHandle(handle)
                return False

        return False

    @classmethod
    def select_uncontended_ready_accounts(
        cls,
        account_manager: AccountManager,
        exclude_ids: Optional[Set[str]] = None,
        owned_profile_ids: Optional[Set[str]] = None,
        lane_id: Optional[str] = None,
        leases: Optional[Dict[str, Dict[str, Any]]] = None,
    ) -> Tuple[List[str], Dict[str, str]]:
        """
        Trả về `(available_ready_ids, skipped_reasons_by_id)`:
        - Bỏ qua tài khoản có `status == 'BUSY'`
        - Bỏ qua tài khoản nằm trong `exclude_ids`
        - Bỏ qua tài khoản đang được lane khác giữ lease còn hạn (`LEASED_BY_<lane_id>`); `lane_id` = lane của caller
        - Bỏ qua tài khoản có thư mục `profiles/<id>` đang bị khóa OS bởi trình duyệt đang chạy
        - Sắp xếp theo hạn mức còn lại cao nhất trước.
        `leases`: live leases `{account_id: record}`; None = read the default registry (`MUSE_LEASES_FILE`).
        """
        excl = set(exclude_ids or set())
        owned = owned_profile_ids or set()
        if leases is None:
            leases = LeaseRegistry().live_leases()
        ready_candidates: List[Dict[str, Any]] = []
        skipped: Dict[str, str] = {}

        for acc in account_manager.list_accounts():
            aid = acc["id"]
            if aid in excl:
                skipped[aid] = "EXCLUDED_BY_CALLER"
                continue
            holder = (leases.get(aid) or {}).get("lane_id")
            if holder and holder != lane_id:
                skipped[aid] = f"LEASED_BY_{holder}"
                continue
            st = (acc.get("status") or "").upper()
            if st == "BUSY":
                skipped[aid] = "ACCOUNT_STATUS_BUSY"
                continue
            prof_dir = account_manager.profiles_dir / aid
            if aid not in owned and cls.is_profile_locked(prof_dir):
                skipped[aid] = "BROWSER_PROFILE_OS_LOCKED"
                continue
            if st == "READY":
                ready_candidates.append(acc)

        ready_candidates.sort(key=AccountManager.get_effective_quota_pct, reverse=True)
        return [a["id"] for a in ready_candidates], skipped


class AutoprodOrchestrator:
    """Bộ điều phối khép kín Một Chạm (Script -> Bible/Beats -> Keyframes -> Pool + Self-Heal -> 1080p Master)."""

    def __init__(
        self,
        account_manager: Optional[AccountManager] = None,
        client_factory: Optional[Callable[[AccountManager], Any]] = None,
        qc_evaluator: Optional[Callable[..., Dict[str, Any]]] = None,
        sync_ui: bool = True,
    ):
        self.account_manager = account_manager or AccountManager()
        self.client_factory = client_factory or HeadlessMuseClient
        self.qc_evaluator = qc_evaluator or FilmQCEngine.evaluate_generated_clip
        self.sync_ui = sync_ui

    @staticmethod
    def _ledger_blocked_shots(project_dir: Path) -> Set[str]:
        ppe = _pool_ledger()
        return {e["shot_id"] for e in ppe.load_unconfirmed_submissions(project_dir)
                if e.get("status") in ppe.UNCONFIRMED_BLOCKING}

    @staticmethod
    def _ledger_record_unconfirmed(project_dir: Path, bid: str, account_id: str, chunk: List[ShotItem],
                                   exc: BaseException) -> None:
        ppe = _pool_ledger()
        entries = ppe.load_unconfirmed_submissions(project_dir)
        stamp = time.time()
        for c in chunk:
            entries.append({
                "shot_id": c.shot_id, "batch_id": bid, "account_id": account_id, "status": "UNCONFIRMED",
                "submitted_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(stamp)), "submitted_epoch": stamp,
                "source": "autoprod", "error": str(exc)[:300],
            })
        _write_json_atomic(Path(project_dir) / ppe.UNCONFIRMED_FILE,
                           {"ttl_min": ppe.resolve_unconfirmed_ttl_min(), "entries": entries})

    def _halt_state(self, project_dir: Path, state: Dict[str, Any], exc: BaseException, account_id: Optional[str],
                    batch_id: Optional[str], simulate: bool) -> Dict[str, Any]:
        """A CAPTCHA / verification page: persist the shared halt, take the account out, stop the whole run."""
        info = send_halt.halt_info(exc, account_id, batch_id)
        send_halt.record_block(project_dir, info, self.account_manager, simulate)
        state["status"] = "HALTED"
        state["halted"] = info
        self._save_state(project_dir, state)
        return state

    def _save_state(self, project_dir: Path, state: Dict[str, Any]) -> None:
        state["updated_at"] = datetime.now().isoformat()
        _write_json_atomic(project_dir / "autoprod_state.json", state)

    def _prepare_accounts(self, simulate: bool, exclude_ids: Set[str]) -> Tuple[List[str], Dict[str, str]]:
        if simulate:
            # Offline dry run: never select (or later write to) a real account.
            return ["sim_acc_01", "sim_acc_02"], {}

        # Chỉ auto_login các tài khoản chưa kiểm tra VÀ không bị phiên khác khóa profile / lane khác giữ lease
        leased = LeaseRegistry().live_leases()
        for acc in self.account_manager.list_accounts():
            aid = acc["id"]
            if aid in exclude_ids or aid in leased:
                continue
            if (acc.get("status") or "").upper() in ("READY", "COOLDOWN", "BUSY"):
                continue
            if BusyAccountDetector.is_profile_locked(self.account_manager.profiles_dir / aid):
                continue
            res = self.account_manager.auto_login_and_verify(aid)
            if isinstance(res, dict) and res.get("status") == "BLOCKED":
                exc = BlockedException(res.get("message") or "BLOCKED: challenge during login")
                exc.account_id, exc.batch_id = aid, "LOGIN"
                raise exc

        return BusyAccountDetector.select_uncontended_ready_accounts(
            self.account_manager, exclude_ids=exclude_ids
        )

    async def _run_async(
        self,
        input_path: Path,
        project_dir: Path,
        preset: str = "drama_35mm",
        audio_mode: Optional[str] = None,
        max_rounds: int = 3,
        simulate: bool = False,
        use_llm: bool = True,
        stop_after_casting: bool = False,
        exclude_accounts: Optional[Set[str]] = None,
        bgm_path: Optional[Path] = None,
        room_tone_path: Optional[Path] = None,
        session_tag: str = "autoprod",
        cinematic_cutaways: bool = False,
        clear_halt: bool = False,
    ) -> Dict[str, Any]:
        input_path = Path(input_path).resolve()
        project_dir = Path(project_dir).resolve()
        excl = set(exclude_accounts or set())
        preset_cfg = DIRECTOR_PRESETS.get(preset, DIRECTOR_PRESETS["drama_35mm"])
        resolved_audio_mode = audio_mode or preset_cfg["audio_mode"]

        with SessionLock(project_dir, session_tag=session_tag):
            state_path = project_dir / "autoprod_state.json"
            state: Dict[str, Any] = (
                json.loads(state_path.read_text(encoding="utf-8"))
                if state_path.exists()
                else {"created_at": datetime.now().isoformat(), "history": []}
            )
            state.update({
                "input_path": str(input_path),
                "project_dir": str(project_dir),
                "preset": preset,
                "audio_mode": resolved_audio_mode,
                "status": "RUNNING",
            })
            state.pop("halted", None)
            state.pop("message", None)
            self._save_state(project_dir, state)

            # Trạm 1: Đọc hiểu Kịch bản / Truyện / SRT -> story_bible.json + beats.json (bỏ qua nếu resume đã có đủ)
            bible_path = project_dir / "story_bible.json"
            beats_path = project_dir / "beats.json"
            if not (bible_path.exists() and beats_path.exists()):
                ingest_res = ScriptIngestor.ingest_file(
                    input_path=input_path,
                    project_dir=project_dir,
                    preset=preset,
                    use_llm=use_llm,
                    cinematic_cutaways=cinematic_cutaways,
                )
                state["stage"] = "STAGE_1_INGESTED"
                state["ingest_summary"] = ingest_res
                self._save_state(project_dir, state)

            # Trạm 2: Biên dịch sơ bộ để lập danh sách Keyframe cần sinh
            ScreenplayCompiler.compile_project_dir(
                project_dir=project_dir,
                audio_mode=resolved_audio_mode,
                strict_bible=True,
                cinematic_cutaways=cinematic_cutaways,
            )
            state["stage"] = "STAGE_2_INITIAL_COMPILE"
            self._save_state(project_dir, state)

            if not simulate:
                # One production send path: real keyframe and video sends go through the pool engine (keyframe and
                # video ledgers written before every send, machine-wide halt, leases). Autoprod never sends itself.
                state["status"] = "REFUSED_USE_POOL_RUNNER"
                state["message"] = (
                    "autoprod only sends with --simulate. Stages 1-2 are done; continue with "
                    f"`python -m muse_studio.pool_runner keyframes {project_dir}` (Owner approves the contact sheets), "
                    f"then `python -m muse_studio.pool_runner videos {project_dir}`."
                )
                self._save_state(project_dir, state)
                return state

            # Trạm 2.5: Sinh & Kiểm định Keyframes 00.png bằng các tài khoản rảnh (không xung đột session khác)
            try:
                ready_accs, skipped_accs = self._prepare_accounts(simulate=simulate, exclude_ids=excl)
            except BlockedException as exc:
                return self._halt_state(project_dir, state, exc, getattr(exc, "account_id", None),
                                        getattr(exc, "batch_id", None), simulate)
            state["skipped_busy_accounts"] = skipped_accs
            if not ready_accs:
                state["status"] = "BLOCKED_NO_ACCOUNTS"
                state["stage"] = "STAGE_2_5_KEYFRAMES"
                self._save_state(project_dir, state)
                return state

            client = self.client_factory(self.account_manager)
            try:
                kf_report = await KeyframeComposer.generate_and_verify_keyframes(
                    project_dir=project_dir,
                    account_ids=ready_accs,
                    client=client,
                    simulate=simulate,
                )
            except BlockedException as exc:
                state["stage"] = "STAGE_2_5_KEYFRAMES"
                return self._halt_state(project_dir, state, exc, getattr(exc, "account_id", None),
                                        getattr(exc, "batch_id", None), simulate)
            state["stage"] = "STAGE_2_5_KEYFRAMES_READY"
            state["keyframe_report"] = kf_report
            self._save_state(project_dir, state)

            if stop_after_casting:
                state["status"] = "PAUSED_FOR_CASTING_REVIEW"
                self._save_state(project_dir, state)
                return state

            # Trạm 3: Biên dịch chính thức (gắn keyframes_index.json) + Tiền kiểm Preflight 0 lỗi HARD
            manifest_path, _, manifest = ScreenplayCompiler.compile_project_dir(
                project_dir=project_dir,
                audio_mode=resolved_audio_mode,
                strict_bible=True,
                cinematic_cutaways=cinematic_cutaways,
            )
            bible = json.loads(bible_path.read_text(encoding="utf-8"))
            bible_errs = ScreenplayCompiler.validate_story_bible(
                bible, anchors_dir=project_dir / "assets" / "anchors", strict_files=True
            )
            ok_pre, pre_findings = FilmQCEngine.validate_manifest_preflight(manifest)
            if bible_errs or not ok_pre:
                state["status"] = "BLOCKED_PREFLIGHT"
                state["stage"] = "STAGE_3_PREFLIGHT"
                state["preflight_errors"] = bible_errs + [str(f) for f in pre_findings]
                self._save_state(project_dir, state)
                return state

            state["stage"] = "STAGE_3_PREFLIGHT_PASSED"
            self._save_state(project_dir, state)

            # Trạm 4 & 5: Render Pool Đa luồng + 5-Gate QC + Closed-Loop Prompt Self-Healing
            canonical_dir = project_dir / "verified_clips"
            canonical_dir.mkdir(parents=True, exist_ok=True)
            strips_dir = project_dir / "qc_strips"
            strips_dir.mkdir(parents=True, exist_ok=True)
            audit_path = project_dir / "qc_audit_report.json"

            shots_by_id: Dict[str, Dict[str, Any]] = {s["shot_id"]: s for s in manifest["shots"]}
            passed_clips, per_shot_qc, render_fingerprints = _load_render_checkpoint(
                audit_path, shots_by_id, simulate
            )

            # Sends that reached Muse without a result (this or an earlier run, any entry point) are never resent
            # here: they stay in the shared send ledger until reconciled / released (`pool_runner videos
            # --release-unconfirmed`).
            submitted_unconfirmed: Set[str] = set() if simulate else self._ledger_blocked_shots(project_dir)
            submitted_unconfirmed -= set(passed_clips)
            remaining_ids = [
                s["shot_id"] for s in manifest["shots"]
                if s["shot_id"] not in passed_clips and s["shot_id"] not in submitted_unconfirmed
            ]
            run_tag = time.strftime("%H%M%S")
            repair_logs: List[Dict[str, Any]] = []
            halt_box: Dict[str, Any] = {}

            async def _send(acc_id: str, bid: str, chunk: List[ShotItem], out_dir: Path) -> Dict[str, Any]:
                kw: Dict[str, Any] = {}
                if _accepts_kw(client.generate_videos_batch, "lease_guard"):
                    kw["lease_guard"] = lambda: not halt_box  # refused right before submit once any send is blocked
                try:
                    return await client.generate_videos_batch(
                        account_id=acc_id, shots=chunk, batch_id=bid, output_dir=out_dir, simulate=simulate, **kw
                    )
                except BlockedException as exc:
                    if not halt_box:
                        halt_box.update(exc=exc, account_id=acc_id, batch_id=bid)
                    raise

            round_num = 1
            while remaining_ids and round_num <= max_rounds:
                try:
                    ready_accs, skipped_accs = self._prepare_accounts(simulate=simulate, exclude_ids=excl)
                except BlockedException as exc:
                    halt_box.update(exc=exc, account_id=getattr(exc, "account_id", None), batch_id="LOGIN")
                    break
                state["skipped_busy_accounts"] = skipped_accs
                if not ready_accs:
                    state["status"] = "BLOCKED_NO_ACCOUNTS"
                    self._save_state(project_dir, state)
                    break

                shot_items = [
                    ShotItem(
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
                    for sid in remaining_ids
                ]

                batch_specs = [
                    (f"AUTOPROD_{run_tag}_R{round_num:02d}_B{(i // 6) + 1:02d}", shot_items[i : i + 6])
                    for i in range(0, len(shot_items), 6)
                ]

                next_round_ids: List[str] = []
                round_defects: Dict[str, List[str]] = {}
                w_idx = 0

                while w_idx < len(batch_specs) and not halt_box:
                    if not simulate:
                        ready_accs, skipped_accs = BusyAccountDetector.select_uncontended_ready_accounts(
                            self.account_manager, exclude_ids=excl
                        )
                        if not ready_accs:
                            for _, rem_chunk in batch_specs[w_idx:]:
                                next_round_ids.extend([c.shot_id for c in rem_chunk])
                            break

                    wave = batch_specs[w_idx : w_idx + len(ready_accs)]
                    w_idx += len(wave)
                    tasks = []
                    for idx_w, (bid, chunk) in enumerate(wave):
                        acc_id = ready_accs[(idx_w + round_num - 1) % len(ready_accs)]
                        out_dir = project_dir / "BATCHES_V2" / bid
                        tasks.append(_send(acc_id, bid, chunk, out_dir))

                    wave_results = await asyncio.gather(*tasks, return_exceptions=True)
                    for (bid, chunk), wres, acc_w in zip(
                        wave, wave_results, [ready_accs[(i + round_num - 1) % len(ready_accs)] for i in range(len(wave))]
                    ):
                        if isinstance(wres, Exception):
                            if getattr(wres, "submitted", False):
                                # Reached Muse: never resent (it may still render and spend credits).
                                submitted_unconfirmed.update(c.shot_id for c in chunk)
                                if not simulate:
                                    self._ledger_record_unconfirmed(project_dir, bid, acc_w, chunk, wres)
                            elif not halt_box:
                                next_round_ids.extend([c.shot_id for c in chunk])
                            continue

                        vmap = wres.get("verified_shots", {})
                        for item in chunk:
                            sid = item.shot_id
                            vinfo = vmap.get(sid)
                            if not vinfo:
                                next_round_ids.append(sid)
                                continue

                            cpath = Path(vinfo["path"])
                            if simulate:
                                dest = canonical_dir / f"{sid}.mp4"
                                shutil.copyfile(cpath, dest)
                                passed_clips[sid] = str(dest)
                                render_fingerprints[sid] = _render_fingerprint(shots_by_id[sid], simulate)
                                continue

                            qc_res = self.qc_evaluator(
                                cpath,
                                shots_by_id[sid],
                                min_duration_s=2.5 if item.duration_s <= 5.5 else 3.0,
                                strip_output_path=strips_dir / f"{sid}_strip.jpg",
                            )
                            per_shot_qc[sid] = qc_res
                            if qc_res.get("verdict") == "PASS":
                                dest = canonical_dir / f"{sid}.mp4"
                                shutil.copyfile(cpath, dest)
                                passed_clips[sid] = str(dest)
                                render_fingerprints[sid] = _render_fingerprint(shots_by_id[sid], simulate)
                            else:
                                defs = list(qc_res.get("defects") or ["QC_REJECT"])
                                round_defects[sid] = defs
                                next_round_ids.append(sid)

                    # Lưu checkpoint nguyên tử ngay sau mỗi đợt
                    pending_now = [s["shot_id"] for s in manifest["shots"] if s["shot_id"] not in passed_clips]
                    _write_json_atomic(
                        audit_path,
                        {
                            "total_shots": len(manifest["shots"]),
                            "passed_count": len(passed_clips),
                            "failed_or_missing_count": len(pending_now),
                            "passed_clips": passed_clips,
                            "render_fingerprints": render_fingerprints,
                            "per_shot_qc": per_shot_qc,
                            "failed_or_missing": [{"shot_id": x, "reason": "PENDING_RETRY"} for x in pending_now],
                        },
                    )

                if halt_box:
                    break  # no further wave or round, no repair
                # Closed-Loop Self-Heal: Tự chữa prompt cho các shot trượt QC trước khi bước sang vòng kế tiếp
                if round_defects and round_num < max_rounds:
                    rep_summary = PromptRepairAgent.repair_manifest_shots(manifest, round_defects)
                    _write_json_atomic(manifest_path, manifest)
                    shots_by_id = {s["shot_id"]: s for s in manifest["shots"]}
                    repair_logs.append({"round": round_num, **rep_summary})

                remaining_ids = [sid for sid in next_round_ids if sid not in submitted_unconfirmed]
                round_num += 1

            state["repair_logs"] = repair_logs
            state["submitted_unconfirmed_shot_ids"] = sorted(submitted_unconfirmed)
            if halt_box:
                state["stage"] = "STAGE_4_HALTED"
                state["remaining_shot_ids"] = [
                    s["shot_id"] for s in manifest["shots"] if s["shot_id"] not in passed_clips
                ]
                return self._halt_state(project_dir, state, halt_box["exc"], halt_box.get("account_id"),
                                        halt_box.get("batch_id"), simulate)
            remaining_ids = remaining_ids + sorted(submitted_unconfirmed - set(remaining_ids))
            if remaining_ids:
                if state.get("status") != "BLOCKED_NO_ACCOUNTS":
                    state["status"] = "BLOCKED_INCOMPLETE_SHOTS"
                state["stage"] = "STAGE_5_QC_INCOMPLETE"
                state["remaining_shot_ids"] = remaining_ids
                self._save_state(project_dir, state)
                return state

            # Trạm 6 & 7: Hậu kỳ 1080p @ 24fps, Hòa âm 4 tầng & EBU R128 2-Pass
            clip_paths_by_shot = {sid: Path(p) for sid, p in passed_clips.items()}
            master_mp4 = project_dir / "MASTER_OUTPUT" / "final_master_1080p.mp4"
            asm_res = MasterAssembler.assemble_project(
                shots_manifest=manifest,
                clip_paths_by_shot=clip_paths_by_shot,
                output_mp4=master_mp4,
                story_bible=bible,
                qc_reports=per_shot_qc,
                bgm_path=bgm_path,
                room_tone_path=room_tone_path,
                capcut_draft=False,
            )

            if self.sync_ui:
                try:
                    from ..cli import sync_project_to_web_ui
                    sync_project_to_web_ui(project_dir)
                except Exception:
                    pass

            state["stage"] = "STAGE_7_MASTER_DELIVERED"
            state["status"] = "COMPLETED"
            state["master_output"] = asm_res
            self._save_state(project_dir, state)
            return state

    def run(self, **kwargs) -> Dict[str, Any]:
        return asyncio.run(self._run_async(**kwargs))
