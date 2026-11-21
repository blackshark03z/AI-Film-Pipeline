import asyncio
import os
import shutil
import time
from pathlib import Path
from typing import Any, Callable, Coroutine, Dict, List, Optional

try:
    from . import send_halt
    from .account_manager import AccountManager
    from .browser_worker import MuseBrowserWorker, QuotaExceededException, GenerationFailedException
    from .headless_muse_client import BlockedException, HaltedException
    from .project_manager import ProjectManager
    from .video_processor import VideoProcessor
    from .film_qc_engine import FilmQCEngine
    from .lane_leases import LeaseRegistry
except ImportError:
    from core import send_halt
    from core.account_manager import AccountManager
    from core.browser_worker import MuseBrowserWorker, QuotaExceededException, GenerationFailedException
    from core.headless_muse_client import BlockedException, HaltedException
    from core.project_manager import ProjectManager
    from core.video_processor import VideoProcessor
    from core.film_qc_engine import FilmQCEngine
    from core.lane_leases import LeaseRegistry

class ClipPreservationError(GenerationFailedException):
    """A rejected clip could not be moved to quarantine. The shot is stopped, never requeued: the next attempt would
    write to the same `clips/<sid>.mp4` and overwrite the take that must be kept."""


class QueueDispatcher:
    """Bộ điều phối render song song đa tài khoản kèm cơ chế Failover và trích frame cho Chained Continuity."""
    def __init__(
        self,
        account_manager: AccountManager,
        project_manager: ProjectManager,
        broadcast_callback: Optional[Callable[[str, Any], Coroutine[Any, Any, None]]] = None
    ):
        self.account_manager = account_manager
        self.project_manager = project_manager
        self.broadcast_callback = broadcast_callback
        
        self.is_running = False
        self.active_project_id: Optional[str] = None
        self.concurrency_limit = 3
        self.simulate_mode = False
        
        self._dispatcher_task: Optional[asyncio.Task] = None
        self._active_workers: Dict[str, asyncio.Task] = {}  # shot_id -> asyncio.Task
        self._shot_retry_count: Dict[str, int] = {}         # shot_id -> count

    async def broadcast(self, event_type: str, data: Any):
        if self.broadcast_callback:
            try:
                await self.broadcast_callback(event_type, data)
            except Exception as e:
                print(f"[!] Lỗi khi broadcast websocket: {e}")

    async def start(self, project_id: str, concurrency: int = 3, simulate: bool = False) -> Dict[str, Any]:
        """Bắt đầu tiến trình render dự án."""
        if self.is_running:
            return {"success": False, "message": "Hàng đợi đang chạy dự án khác"}

        proj = self.project_manager.get_project(project_id)
        if not proj:
            return {"success": False, "message": "Dự án không tồn tại"}

        if not simulate:
            stop = send_halt.send_stop()
            if stop is not None:
                return {"success": False, "status": "HALTED", "halted": stop,
                        "message": f"Muse sending is halted machine-wide; {send_halt.CLEAR_HALT_HINT}"}

        # Đặt lại các shot bị kẹt RUNNING về PENDING
        for s in proj.get("shots", []):
            if s.get("status") == "RUNNING":
                self.project_manager.update_shot(project_id, s["id"], status="PENDING", progress=0, assigned_account=None)

        self.is_running = True
        self.active_project_id = project_id
        self.concurrency_limit = max(1, concurrency)
        self.simulate_mode = simulate
        self._shot_retry_count.clear()

        self.project_manager.update_project(project_id, status="RUNNING")
        self._dispatcher_task = asyncio.create_task(self._dispatcher_loop())

        await self.broadcast("project_started", {"project_id": project_id, "mode": proj.get("mode")})
        return {"success": True, "message": "Đã kích hoạt hàng đợi render song song"}

    async def stop(self) -> Dict[str, Any]:
        """Tạm dừng hàng đợi render."""
        if not self.is_running:
            return {"success": False, "message": "Hàng đợi không ở trạng thái chạy"}

        self.is_running = False
        if self._dispatcher_task:
            self._dispatcher_task.cancel()
            self._dispatcher_task = None

        # Hủy các worker đang chạy
        for sid, task in list(self._active_workers.items()):
            task.cancel()
            if self.active_project_id:
                self.project_manager.update_shot(self.active_project_id, sid, status="PENDING", progress=0, assigned_account=None)

        self._active_workers.clear()

        # Đưa các tài khoản BUSY về READY
        for acc in self.account_manager.list_accounts():
            if acc.get("status") == "BUSY":
                self.account_manager.update_account(acc["id"], status="READY")

        if self.active_project_id:
            self.project_manager.update_project(self.active_project_id, status="PAUSED")
            await self.broadcast("project_paused", {"project_id": self.active_project_id})
            self.active_project_id = None

        return {"success": True, "message": "Đã tạm dừng render"}

    def _halted(self) -> Optional[Dict[str, Any]]:
        """The machine-wide Muse stop (a real run only)."""
        return None if self.simulate_mode else send_halt.send_stop()

    async def _halt_dispatch(self, project_id: Optional[str], info: Optional[Dict[str, Any]]) -> None:
        """Stop dispatching for good on a block / halt: no requeue, no retry; restart only after --clear-halt."""
        self.is_running = False
        if project_id:
            self.project_manager.update_project(project_id, status="HALTED")
            await self.broadcast("project_halted", {"project_id": project_id, "halted": info,
                                                    "message": send_halt.halted_line(info)})

    async def _dispatcher_loop(self):
        """Vòng lặp điều phối chính."""
        try:
            while self.is_running and self.active_project_id:
                stop = self._halted()
                if stop is not None:
                    await self._halt_dispatch(self.active_project_id, stop)
                    break
                proj = self.project_manager.get_project(self.active_project_id)
                if not proj:
                    break

                shots = proj.get("shots", [])
                mode = proj.get("mode", "batch_parallel")

                pending_shots = [s for s in shots if s.get("status") == "PENDING"]
                running_shots = [s for s in shots if s.get("status") == "RUNNING"]

                # Kiểm tra nếu toàn bộ shot đã hoàn tất
                if not pending_shots and not running_shots:
                    self.project_manager.update_project(self.active_project_id, status="COMPLETED")
                    await self.broadcast("project_completed", {"project_id": self.active_project_id})
                    self.is_running = False
                    self.active_project_id = None
                    break

                # Lấy danh sách tài khoản sẵn sàng trong pool
                leased = LeaseRegistry().live_leases()  # accounts held by a production lane are off-limits
                ready_accounts = [
                    a for a in self.account_manager.list_accounts()
                    if a.get("status") in ["READY", "UNCHECKED"] and a["id"] not in leased
                ]

                # Xử lý theo từng chế độ
                if mode == "batch_parallel":
                    # Chế độ song song: Cứ có acc rảnh và shot chờ thì bốc việc
                    available_slots = self.concurrency_limit - len(self._active_workers)
                    while available_slots > 0 and pending_shots and ready_accounts:
                        target_shot = pending_shots.pop(0)
                        target_account = ready_accounts.pop(0)
                        available_slots -= 1

                        self._launch_worker_task(target_shot, target_account, proj)

                elif mode == "chained_continuity":
                    # Chế độ chuỗi nối tiếp: Shot N cần frame cuối của Shot N-1
                    # Kiểm tra xem có shot nào đang chạy không
                    if not self._active_workers and pending_shots and ready_accounts:
                        target_shot = pending_shots[0]
                        order = target_shot.get("order", 1)

                        # Nếu là shot đầu tiên hoặc shot trước đã COMPLETED
                        prev_shot = next((s for s in shots if s.get("order") == order - 1), None)
                        if prev_shot is None or prev_shot.get("status") == "COMPLETED":
                            pending_shots.pop(0)
                            target_account = ready_accounts.pop(0)
                            self._launch_worker_task(target_shot, target_account, proj, prev_shot=prev_shot)

                await asyncio.sleep(1.5)

        except asyncio.CancelledError:
            pass
        except Exception as e:
            print(f"[!] Lỗi nghiêm trọng trong Dispatcher loop: {e}")
            self.is_running = False

    def _launch_worker_task(self, shot: Dict[str, Any], account: Dict[str, Any], project: Dict[str, Any], prev_shot: Optional[Dict[str, Any]] = None):
        sid = shot["id"]
        acc_id = account["id"]
        project_id = project["id"]
        if self._halted() is not None:
            return  # the dispatcher loop stops on its next pass

        # TIỀN KIỂM PREFLIGHT: Kiểm tra prompt & assets trước khi tốn tài nguyên
        if not self.simulate_mode:
            is_valid, preflight_errors = FilmQCEngine.validate_shot_preflight(shot, prev_shot)
            if not is_valid:
                err_msg = "; ".join(preflight_errors)
                print(f"[PREFLIGHT_FAIL] Cảnh {sid} không đạt tiền kiểm QA: {err_msg}")
                self.project_manager.update_shot(project_id, sid, status="FAILED", progress=0, error=f"Lỗi tiền kiểm QA: {err_msg}")
                return

        # Đánh dấu trạng thái
        self.project_manager.update_shot(project_id, sid, status="RUNNING", assigned_account=account.get("name", acc_id), progress=5)
        self.account_manager.update_account(acc_id, status="BUSY")

        # Nạp start frame từ shot trước nếu ở chế độ Chained
        refs = list(shot.get("reference_images", []))
        if prev_shot and prev_shot.get("last_frame_path"):
            last_frame = prev_shot["last_frame_path"]
            if Path(last_frame).exists():
                # Chèn làm ảnh đầu tiên (Start frame)
                refs.insert(0, str(last_frame))

        # Đường dẫn output video
        p_dir = self.project_manager.get_project_dir(project_id)
        output_clip = p_dir / "clips" / f"{sid}.mp4"

        task = asyncio.create_task(
            self._execute_shot(
                project_id,
                sid,
                acc_id,
                shot.get("prompt", ""),
                refs,
                output_clip,
                shot.get("dialogue"),
                shot_spec=shot,
            )
        )
        self._active_workers[sid] = task


    @staticmethod
    def _quarantine_rejected_clip(clip: Path) -> Optional[Path]:
        """Move a QC-rejected clip to `<dir>/qc_rejected/<stem>_<ts>.mp4` (a fresh name per take, nothing is
        overwritten). Returns the new path, or None when the move failed (the clip is then left untouched)."""
        clip = Path(clip)
        if not clip.exists():
            return None
        try:
            qdir = clip.parent / "qc_rejected"
            qdir.mkdir(parents=True, exist_ok=True)
            dest = qdir / f"{clip.stem}_{time.strftime('%Y%m%d_%H%M%S')}{clip.suffix}"
            n = 1
            while dest.exists():
                dest = qdir / f"{clip.stem}_{time.strftime('%Y%m%d_%H%M%S')}_{n}{clip.suffix}"
                n += 1
            shutil.move(str(clip), str(dest))
            return dest
        except Exception:
            return None

    async def _execute_shot(
        self,
        project_id: str,
        shot_id: str,
        account_id: str,
        prompt: str,
        reference_images: List[str],
        output_clip_path: Path,
        dialogue: Optional[str] = None,
        shot_spec: Optional[Dict[str, Any]] = None,
    ):
        """Thực thi một cảnh và bắt lỗi failover."""
        worker = MuseBrowserWorker(account_id, self.account_manager)

        def _on_progress(pct: int, msg: str):
            self.project_manager.update_shot(project_id, shot_id, progress=pct)
            asyncio.create_task(
                self.broadcast("shot_progress", {
                    "project_id": project_id,
                    "shot_id": shot_id,
                    "progress": pct,
                    "message": msg,
                    "account_id": account_id
                })
            )

        try:
            res = await worker.generate_shot(
                prompt=prompt,
                reference_images=reference_images,
                output_clip_path=output_clip_path,
                dialogue=dialogue,
                progress_callback=_on_progress,
                simulate=self.simulate_mode
            )

            # HẬU KIỂM QC: Đánh giá chất lượng clip sinh ra với đầy đủ shot_spec (Gate 1-5)
            if output_clip_path.exists() and not self.simulate_mode:
                _on_progress(98, "Đang tiến hành hậu kiểm QA/QC chất lượng video...")
                eval_spec = dict(shot_spec or {})
                eval_spec.setdefault("id", shot_id)
                eval_spec.setdefault("prompt", prompt)
                if dialogue and not eval_spec.get("dialogue"):
                    eval_spec["dialogue"] = dialogue
                qc_result = FilmQCEngine.evaluate_generated_clip(output_clip_path, eval_spec, min_duration_s=3.0)
                if qc_result["verdict"] == "REJECT":
                    # Loại bỏ shot lỗi và đẩy lại hàng đợi
                    err_reasons = "; ".join(qc_result.get("defects", []))
                    print(f"[QC_REJECT] Cảnh {shot_id} bị từ chối hậu kiểm: {err_reasons}")
                    # Never delete a received clip: move it into a per-take quarantine and record the rejection.
                    quarantined = self._quarantine_rejected_clip(output_clip_path)
                    if quarantined is None:
                        # The take could not be preserved and a retry would overwrite it: stop this shot.
                        raise ClipPreservationError(
                            f"CLIP_PRESERVATION_FAILED: the QC-rejected clip {output_clip_path.name} could not be "
                            f"moved to quarantine and was kept in place; the shot is not retried ({err_reasons})")
                    try:
                        self.project_manager.update_shot(
                            project_id, shot_id, qc_status="REJECTED", qc_rejected_clip=str(quarantined))
                    except Exception:
                        pass
                    raise GenerationFailedException(f"Hậu kiểm QC thất bại: {err_reasons}")

            # Nếu tạo thành công và đạt chuẩn QC, trích xuất frame cuối nếu cần
            last_frame_file = None
            if output_clip_path.exists():
                last_frame_path = output_clip_path.parent / f"{shot_id}_last_frame.png"
                if VideoProcessor.extract_last_frame(output_clip_path, last_frame_path):
                    last_frame_file = str(last_frame_path)

            self.project_manager.update_shot(
                project_id,
                shot_id,
                status="COMPLETED",
                progress=100,
                output_clip=str(output_clip_path),
                last_frame_path=last_frame_file,
                error=None
            )
            self.account_manager.update_account(account_id, status="READY", error_message=None)

            await self.broadcast("shot_completed", {
                "project_id": project_id,
                "shot_id": shot_id,
                "output_clip": str(output_clip_path)
            })

        except QuotaExceededException as qe:
            # Xử lý Failover khi tài khoản hết hạn mức
            print(f"[FAILOVER] Tài khoản {account_id} hết quota. Đưa shot {shot_id} lại hàng đợi!")
            self.account_manager.update_account(account_id, status="COOLDOWN", error_message=str(qe))
            self._handle_retry(project_id, shot_id, str(qe))

        except BlockedException as be:
            # CAPTCHA / verification: already published machine-wide by the detector. Never requeued or retried.
            sent = bool(getattr(worker, "submitted", False))
            print(f"[HALTED] Muse block on {account_id} (shot {shot_id}): all Muse sending stopped")
            self.project_manager.update_shot(
                project_id, shot_id, status="FAILED", progress=0, assigned_account=None,
                error=("SUBMITTED_UNCONFIRMED + " if sent else "") + f"BLOCKED: {be}"[:300],
            )
            await self._halt_dispatch(project_id, send_halt.send_stop() or {"account_id": account_id})

        except HaltedException as he:
            # Halted elsewhere before the submit: never sent. Left PENDING for after --clear-halt; not retried now.
            self.account_manager.update_account(account_id, status="READY")
            self.project_manager.update_shot(project_id, shot_id, status="PENDING", progress=0, assigned_account=None,
                                             error=f"HALTED (not sent): {he}"[:300])
            await self._halt_dispatch(project_id, send_halt.send_stop())

        except ClipPreservationError as pe:
            # Stopped for good (no requeue): the kept take stays untouched until an operator handles it.
            print(f"[PRESERVATION] shot {shot_id}: {pe}")
            self.account_manager.update_account(account_id, status="READY", error_message=str(pe)[:300])
            self.project_manager.update_shot(project_id, shot_id, status="FAILED", progress=0,
                                             assigned_account=None, error=str(pe)[:300])

        except Exception as e:
            if getattr(e, "submitted", False):
                # Failed after the Generate click: it may be rendering on Muse. Never resent blindly.
                self.account_manager.update_account(account_id, status="READY", error_message=str(e)[:300])
                self.project_manager.update_shot(project_id, shot_id, status="FAILED", progress=0,
                                                 assigned_account=None,
                                                 error=f"SUBMITTED_UNCONFIRMED: {e}"[:300])
                return
            # Lỗi khác (mạng, timeout, etc.)
            err_msg = str(e)
            print(f"[ERROR] Lỗi render shot {shot_id} trên acc {account_id}: {err_msg}")
            self.account_manager.update_account(account_id, status="READY", error_message=err_msg)
            self._handle_retry(project_id, shot_id, err_msg)

        finally:
            self._active_workers.pop(shot_id, None)

    def _handle_retry(self, project_id: str, shot_id: str, error_msg: str):
        retries = self._shot_retry_count.get(shot_id, 0) + 1
        self._shot_retry_count[shot_id] = retries

        if retries <= 3:
            # Cho phép thử lại bằng cách đưa về PENDING để account khác bốc
            self.project_manager.update_shot(
                project_id,
                shot_id,
                status="PENDING",
                progress=0,
                assigned_account=None,
                error=f"Thử lại ({retries}/3) sau lỗi: {error_msg}"
            )
        else:
            # Vượt quá 3 lần thì đánh dấu FAILED
            self.project_manager.update_shot(
                project_id,
                shot_id,
                status="FAILED",
                progress=0,
                error=f"Thất bại sau 3 lần thử lại: {error_msg}"
            )
