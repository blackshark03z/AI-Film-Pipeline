import asyncio
import os
import shutil
import tempfile
from pathlib import Path
import pytest

from core.account_manager import AccountManager
from core.project_manager import ProjectManager
from core.queue_dispatcher import QueueDispatcher

@pytest.fixture
def temp_environment():
    temp_dir = Path(tempfile.mkdtemp())
    acc_mgr = AccountManager(
        storage_file=temp_dir / "accounts.json",
        profiles_dir=temp_dir / "profiles"
    )
    proj_mgr = ProjectManager(projects_dir=temp_dir / "projects")
    yield acc_mgr, proj_mgr, temp_dir
    shutil.rmtree(temp_dir, ignore_errors=True)

def test_queue_parallel_execution(temp_environment):
    async def _test():
        acc_mgr, proj_mgr, _ = temp_environment

        # Thêm 2 tài khoản test
        a1 = acc_mgr.add_account("Test_Acc_1")
        a2 = acc_mgr.add_account("Test_Acc_2")
        acc_mgr.update_account(a1["id"], status="READY")
        acc_mgr.update_account(a2["id"], status="READY")

        # Tạo dự án với 2 cảnh
        proj = proj_mgr.create_project("Parallel Test", mode="batch_parallel")
        pid = proj["id"]
        proj_mgr.add_shot(pid, prompt="Shot A prompt")
        proj_mgr.add_shot(pid, prompt="Shot B prompt")

        events = []
        async def _on_event(evt_type, data):
            events.append((evt_type, data))

        dispatcher = QueueDispatcher(acc_mgr, proj_mgr, broadcast_callback=_on_event)
        
        # Bắt đầu chạy render ở chế độ giả lập (simulate=True)
        res = await dispatcher.start(pid, concurrency=2, simulate=True)
        assert res["success"] is True
        assert dispatcher.is_running is True

        # Chờ hàng đợi hoàn thành (mỗi shot simulate mất ~2s)
        for _ in range(15):
            await asyncio.sleep(1)
            p_data = proj_mgr.get_project(pid)
            if p_data["status"] == "COMPLETED":
                break

        p_final = proj_mgr.get_project(pid)
        assert p_final["status"] == "COMPLETED"
        assert p_final["completed_shots"] == 2
        for s in p_final["shots"]:
            assert s["status"] == "COMPLETED"
            assert s["output_clip"] is not None
            assert Path(s["output_clip"]).exists()

    asyncio.run(_test())

def test_queue_stop(temp_environment):
    async def _test():
        acc_mgr, proj_mgr, _ = temp_environment
        a1 = acc_mgr.add_account("Acc_Pause")
        acc_mgr.update_account(a1["id"], status="READY")

        proj = proj_mgr.create_project("Pause Test")
        pid = proj["id"]
        proj_mgr.add_shot(pid, prompt="Shot to pause")

        dispatcher = QueueDispatcher(acc_mgr, proj_mgr)
        await dispatcher.start(pid, concurrency=1, simulate=True)
        assert dispatcher.is_running is True

        # Dừng ngay
        await dispatcher.stop()
        assert dispatcher.is_running is False
        p_data = proj_mgr.get_project(pid)
        assert p_data["status"] == "PAUSED"

    asyncio.run(_test())
