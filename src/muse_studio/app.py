import asyncio
import json
import os
import re
import shutil
import zipfile
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional


def _safe_filename(raw_name: Optional[str], fallback: str = "upload.bin") -> str:
    clean = Path(raw_name or fallback).name
    clean = re.sub(r'[<>:"/\\|?*\x00-\x1f]+', "_", clean).strip(" ._")
    return clean or fallback


def _safe_export_stem(raw_name: Optional[str], fallback: str) -> str:
    clean = re.sub(r'[<>:"/\\|?*\x00-\x1f]+', "_", (raw_name or "")).strip(" ._")
    return clean or fallback

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, UploadFile, File, Form, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

try:
    from .core.config import (
        BASE_DIR, DATA_DIR, PROJECTS_DIR, OUTPUT_DIR, DEFAULT_HOST, DEFAULT_PORT
    )
    from .core.account_manager import AccountManager, AccountStoreUnreadable
    from .core.lane_leases import LeaseRegistry, public_lease_view
    from .core.project_manager import ProjectManager
    from .core.video_processor import VideoProcessor
    from .core.queue_dispatcher import QueueDispatcher
    from .core.master_assembler import MasterAssembler
except ImportError:
    from core.config import (
        BASE_DIR, DATA_DIR, PROJECTS_DIR, OUTPUT_DIR, DEFAULT_HOST, DEFAULT_PORT
    )
    from core.account_manager import AccountManager, AccountStoreUnreadable
    from core.lane_leases import LeaseRegistry, public_lease_view
    from core.project_manager import ProjectManager
    from core.video_processor import VideoProcessor
    from core.queue_dispatcher import QueueDispatcher
    from core.master_assembler import MasterAssembler

app = FastAPI(title="Muse Video Studio", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Khởi tạo các manager cốt lõi
account_mgr = AccountManager()
project_mgr = ProjectManager()

# WebSocket Connection Hub
class WebSocketHub:
    def __init__(self):
        self.active_connections: List[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)

    def disconnect(self, websocket: WebSocket):
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)

    async def broadcast(self, event_type: str, data: Any):
        payload = json.dumps({"type": event_type, "data": data, "timestamp": datetime.now().isoformat()})
        for conn in list(self.active_connections):
            try:
                await conn.send_text(payload)
            except Exception:
                self.disconnect(conn)

ws_hub = WebSocketHub()

# Khởi tạo Queue Dispatcher
dispatcher = QueueDispatcher(
    account_manager=account_mgr,
    project_manager=project_mgr,
    broadcast_callback=ws_hub.broadcast
)

# Mount thư mục tĩnh
STATIC_DIR = BASE_DIR / "static"
STATIC_DIR.mkdir(parents=True, exist_ok=True)
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")
app.mount("/media", StaticFiles(directory=str(PROJECTS_DIR)), name="media")
app.mount("/output", StaticFiles(directory=str(OUTPUT_DIR)), name="output")

@app.get("/", response_class=HTMLResponse)
async def serve_index():
    index_file = STATIC_DIR / "index.html"
    if index_file.exists():
        return HTMLResponse(content=index_file.read_text(encoding="utf-8"))
    return HTMLResponse("<h1>Muse Video Studio Backend Running. (Missing index.html)</h1>")

def _init_state_payload() -> Dict[str, Any]:
    """First websocket message. An unreadable accounts.json is shown as an error (empty list + `accounts_error`);
    it is read-only here and nothing is ever saved."""
    data: Dict[str, Any] = {
        "accounts": [],
        "is_rendering": dispatcher.is_running,
        "active_project_id": dispatcher.active_project_id,
    }
    try:
        data["accounts"] = account_mgr.list_accounts()
    except AccountStoreUnreadable as exc:
        data["accounts_error"] = f"accounts.json is unreadable: {exc}"
    return {"type": "init_state", "data": data}


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await ws_hub.connect(websocket)
    try:
        # Gửi ngay trạng thái ban đầu
        await websocket.send_text(json.dumps(_init_state_payload()))
        while True:
            msg = await websocket.receive_text()
            # Xử lý lệnh ping / pong nếu có
            if msg == "ping":
                await websocket.send_text("pong")
    except WebSocketDisconnect:
        ws_hub.disconnect(websocket)
    except Exception:
        ws_hub.disconnect(websocket)

# ----------------- ACCOUNTS API -----------------
class CreateAccountPayload(BaseModel):
    name: str
    proxy: Optional[str] = None
    email: Optional[str] = None
    invite_code: Optional[str] = None
    raw_cookie: Optional[str] = None
    auto_verify: bool = False

class UpdateAccountPayload(BaseModel):
    name: Optional[str] = None
    proxy: Optional[str] = None
    status: Optional[str] = None

@app.get("/api/accounts")
async def get_accounts():
    try:
        accounts = account_mgr.list_accounts()
    except AccountStoreUnreadable as exc:
        # Read-only error for the UI: nothing is saved and the accounts file is left exactly as it is.
        raise HTTPException(status_code=503, detail=f"accounts.json is unreadable: {exc}")
    try:
        live = LeaseRegistry().live_leases()
    except Exception:
        live = {}
    for acc in accounts:
        # Read-only: which production lane holds this account (see `python -m muse_studio.lane status`).
        view = public_lease_view(live.get(acc["id"]))
        acc["lease"] = (
            {k: view[k] for k in ("lane_id", "project_dir", "expires_at")} if view else None
        )
    return accounts

@app.post("/api/accounts")
async def add_account(payload: CreateAccountPayload):
    acc = account_mgr.add_account(
        name=payload.name,
        proxy=payload.proxy,
        email=payload.email,
        invite_code=payload.invite_code,
        raw_cookie=payload.raw_cookie,
    )
    await ws_hub.broadcast("accounts_updated", account_mgr.list_accounts())
    if payload.auto_verify or payload.raw_cookie or payload.email or payload.invite_code:
        asyncio.create_task(_run_parallel_verification([acc["id"]]))
    return acc

@app.put("/api/accounts/{account_id}")
async def update_account(account_id: str, payload: UpdateAccountPayload):
    acc = account_mgr.update_account(account_id, **payload.model_dump(exclude_unset=True))
    if not acc:
        raise HTTPException(status_code=404, detail="Không tìm thấy tài khoản")
    await ws_hub.broadcast("accounts_updated", account_mgr.list_accounts())
    return acc

@app.delete("/api/accounts/{account_id}")
async def delete_account(account_id: str):
    ok = account_mgr.delete_account(account_id)
    if not ok:
        raise HTTPException(status_code=404, detail="Không tìm thấy tài khoản")
    await ws_hub.broadcast("accounts_updated", account_mgr.list_accounts())
    return {"success": True}

@app.post("/api/accounts/{account_id}/open_login")
async def open_login_browser(account_id: str):
    try:
        account_mgr.launch_login_browser_process(account_id)
        return {"success": True, "message": "Đã mở cửa sổ trình duyệt để đăng nhập"}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@app.post("/api/accounts/{account_id}/check")
async def check_account_session(account_id: str):
    # Dùng hàm auto_login_and_verify (cookie -> tempmail fallback)
    loop = asyncio.get_running_loop()
    res = await loop.run_in_executor(None, account_mgr.auto_login_and_verify, account_id)
    await ws_hub.broadcast("accounts_updated", account_mgr.list_accounts())
    return res

class BulkImportPayload(BaseModel):
    raw_text: str
    auto_verify: bool = True

async def _run_parallel_verification(account_ids: List[str], max_concurrent: int = 3):
    pending = [aid for aid in account_ids if not account_mgr._get_verify_lock(aid).locked()]
    if not pending:
        return
    for aid in pending:
        account_mgr.update_account(aid, status="CHECKING", error_message=None)
    await ws_hub.broadcast("accounts_updated", account_mgr.list_accounts())

    sem = asyncio.Semaphore(max_concurrent)

    async def _verify_one(aid):
        async with sem:
            loop = asyncio.get_running_loop()
            res = await loop.run_in_executor(None, account_mgr.auto_login_and_verify, aid)
            await ws_hub.broadcast("account_verified", {"account_id": aid, "result": res})
            await ws_hub.broadcast("accounts_updated", account_mgr.list_accounts())

    tasks = [_verify_one(aid) for aid in pending]
    await asyncio.gather(*tasks, return_exceptions=True)

@app.post("/api/accounts/bulk_import")
async def bulk_import_accounts(payload: BulkImportPayload):
    res = account_mgr.bulk_import_accounts(payload.raw_text)
    await ws_hub.broadcast("accounts_updated", account_mgr.list_accounts())

    if payload.auto_verify and res.get("accounts"):
        account_ids = [a["id"] for a in res["accounts"]]
        asyncio.create_task(_run_parallel_verification(account_ids))

    return res

@app.post("/api/accounts/bulk_check")
async def bulk_check_accounts():
    accounts = account_mgr.list_accounts()
    account_ids = [a["id"] for a in accounts]
    asyncio.create_task(_run_parallel_verification(account_ids))
    return {
        "success": True,
        "count": len(account_ids),
        "message": f"Đang kiểm tra xác thực & hạn mức {len(account_ids)} tài khoản..."
    }

class RedeemInviteCodePayload(BaseModel):
    code: str
    account_ids: Optional[List[str]] = None

async def _run_parallel_redeem(account_ids: List[str], code: str, max_concurrent: int = 3):
    pending = [aid for aid in account_ids if not account_mgr._get_verify_lock(aid).locked()]
    if not pending:
        return
    prev_statuses = {
        aid: (account_mgr.get_account(aid) or {}).get("status", "UNCHECKED")
        for aid in pending
    }
    for aid in pending:
        account_mgr.update_account(aid, status="CHECKING", error_message=None)
    await ws_hub.broadcast("accounts_updated", account_mgr.list_accounts())

    sem = asyncio.Semaphore(max_concurrent)

    async def _redeem_one(aid):
        async with sem:
            loop = asyncio.get_running_loop()
            res = await loop.run_in_executor(None, account_mgr.redeem_invite_code, aid, code)
            curr = account_mgr.get_account(aid) or {}
            if curr.get("status") == "CHECKING":
                fallback_status = res.get("status")
                if not fallback_status or fallback_status == "CHECKING":
                    fallback_status = prev_statuses.get(aid, "UNCHECKED")
                account_mgr.update_account(
                    aid,
                    status=fallback_status,
                    error_message=res.get("message") if fallback_status != "READY" else None,
                )
            await ws_hub.broadcast("account_verified", {"account_id": aid, "result": res})
            await ws_hub.broadcast("accounts_updated", account_mgr.list_accounts())

    tasks = [_redeem_one(aid) for aid in pending]
    await asyncio.gather(*tasks, return_exceptions=True)

@app.post("/api/accounts/redeem")
async def redeem_accounts_invite_code(payload: RedeemInviteCodePayload):
    clean_code = (payload.code or "").strip().upper()
    if not clean_code:
        raise HTTPException(status_code=400, detail="Mã mời không được để trống")
    accounts = account_mgr.list_accounts()
    valid_ids = {a["id"] for a in accounts}
    target_ids = [aid for aid in (payload.account_ids or [a["id"] for a in accounts]) if aid in valid_ids]
    asyncio.create_task(_run_parallel_redeem(target_ids, clean_code))
    return {
        "success": True,
        "count": len(target_ids),
        "code": clean_code,
        "message": f"Đang nhập mã mời {clean_code} cho {len(target_ids)} tài khoản..."
    }

# ----------------- PROJECTS API -----------------
class CreateProjectPayload(BaseModel):
    name: str
    mode: str = "batch_parallel"

class UpdateProjectPayload(BaseModel):
    name: Optional[str] = None
    mode: Optional[str] = None

class AddShotPayload(BaseModel):
    prompt: str
    dialogue: Optional[str] = None
    reference_images: Optional[List[str]] = None
    shot_id: Optional[str] = None

class UpdateShotPayload(BaseModel):
    prompt: Optional[str] = None
    dialogue: Optional[str] = None
    reference_images: Optional[List[str]] = None
    status: Optional[str] = None

@app.get("/api/projects")
async def get_projects():
    return project_mgr.list_projects()

@app.post("/api/projects")
async def create_project(payload: CreateProjectPayload):
    proj = project_mgr.create_project(name=payload.name, mode=payload.mode)
    await ws_hub.broadcast("projects_updated", project_mgr.list_projects())
    return proj

@app.get("/api/projects/{project_id}")
async def get_project(project_id: str):
    proj = project_mgr.get_project(project_id)
    if not proj:
        raise HTTPException(status_code=404, detail="Không tìm thấy dự án")
    return proj

@app.put("/api/projects/{project_id}")
async def update_project(project_id: str, payload: UpdateProjectPayload):
    proj = project_mgr.update_project(project_id, **payload.model_dump(exclude_unset=True))
    if not proj:
        raise HTTPException(status_code=404, detail="Không tìm thấy dự án")
    await ws_hub.broadcast("projects_updated", project_mgr.list_projects())
    return proj

@app.delete("/api/projects/{project_id}")
async def delete_project(project_id: str):
    ok = project_mgr.delete_project(project_id)
    if not ok:
        raise HTTPException(status_code=404, detail="Không tìm thấy dự án")
    await ws_hub.broadcast("projects_updated", project_mgr.list_projects())
    return {"success": True}

@app.post("/api/projects/{project_id}/shots")
async def add_shot(project_id: str, payload: AddShotPayload):
    shot = project_mgr.add_shot(
        project_id,
        prompt=payload.prompt,
        reference_images=payload.reference_images,
        dialogue=payload.dialogue,
        shot_id=payload.shot_id
    )
    if not shot:
        raise HTTPException(status_code=404, detail="Không tìm thấy dự án")
    await ws_hub.broadcast("project_detail_updated", project_mgr.get_project(project_id))
    return shot

@app.put("/api/projects/{project_id}/shots/{shot_id}")
async def update_shot(project_id: str, shot_id: str, payload: UpdateShotPayload):
    shot = project_mgr.update_shot(project_id, shot_id, **payload.model_dump(exclude_unset=True))
    if not shot:
        raise HTTPException(status_code=404, detail="Không tìm thấy cảnh")
    await ws_hub.broadcast("project_detail_updated", project_mgr.get_project(project_id))
    return shot

@app.delete("/api/projects/{project_id}/shots/{shot_id}")
async def delete_shot(project_id: str, shot_id: str):
    ok = project_mgr.delete_shot(project_id, shot_id)
    if not ok:
        raise HTTPException(status_code=404, detail="Không tìm thấy cảnh")
    await ws_hub.broadcast("project_detail_updated", project_mgr.get_project(project_id))
    return {"success": True}

@app.post("/api/projects/{project_id}/upload_ref")
async def upload_ref_image(project_id: str, file: UploadFile = File(...)):
    p_dir = project_mgr.get_project_dir(project_id)
    refs_dir = p_dir / "refs"
    refs_dir.mkdir(parents=True, exist_ok=True)
    safe_name = _safe_filename(file.filename, fallback="ref.png")

    file_path = refs_dir / safe_name
    content = await file.read()
    file_path.write_bytes(content)

    # Trả về đường dẫn truy cập tĩnh
    return {
        "success": True,
        "filename": safe_name,
        "absolute_path": str(file_path.resolve()),
        "url": f"/media/{project_id}/refs/{safe_name}"
    }

@app.post("/api/projects/{project_id}/import_csv")
async def import_csv(project_id: str, file: UploadFile = File(...)):
    p_dir = project_mgr.get_project_dir(project_id)
    safe_csv = _safe_filename(file.filename, fallback="shots.csv")
    temp_csv = p_dir / f"temp_{safe_csv}"
    temp_csv.write_bytes(await file.read())
    
    count = project_mgr.import_shots_from_csv(project_id, temp_csv)
    if temp_csv.exists():
        temp_csv.unlink()
        
    await ws_hub.broadcast("project_detail_updated", project_mgr.get_project(project_id))
    return {"success": True, "imported_count": count}

# ----------------- RENDER CONTROLLER API -----------------
class StartRenderPayload(BaseModel):
    project_id: str
    concurrency: int = 3
    simulate: bool = False

@app.post("/api/render/start")
async def start_render(payload: StartRenderPayload):
    res = await dispatcher.start(
        project_id=payload.project_id,
        concurrency=payload.concurrency,
        simulate=payload.simulate
    )
    if not res.get("success"):
        raise HTTPException(status_code=400, detail=res.get("message"))
    return res

@app.post("/api/render/stop")
async def stop_render():
    res = await dispatcher.stop()
    return res

@app.get("/api/render/status")
async def render_status():
    return {
        "is_running": dispatcher.is_running,
        "active_project_id": dispatcher.active_project_id,
        "active_workers_count": len(dispatcher._active_workers),
        "concurrency_limit": dispatcher.concurrency_limit,
        "simulate_mode": dispatcher.simulate_mode
    }

# ----------------- EXPORT & MERGE API -----------------
@app.post("/api/projects/{project_id}/merge")
async def merge_videos(project_id: str):
    proj = project_mgr.get_project(project_id)
    if not proj:
        raise HTTPException(status_code=404, detail="Không tìm thấy dự án")

    shots = sorted(proj.get("shots", []), key=lambda s: s.get("order", 0))
    clips = []
    for s in shots:
        if s.get("status") == "COMPLETED" and s.get("output_clip"):
            p = Path(s["output_clip"])
            if p.exists():
                clips.append(p)

    if not clips:
        raise HTTPException(status_code=400, detail="Chưa có clip nào render hoàn tất để ghép nối")

    safe_stem = _safe_export_stem(proj.get("name"), project_id)
    output_merged = OUTPUT_DIR / f"{safe_stem}_final.mp4"
    p_dir = project_mgr.get_project_dir(project_id)
    manifest_p = p_dir / "shots_manifest.json"
    if manifest_p.exists():
        manifest = json.loads(manifest_p.read_text(encoding="utf-8"))
        sb_p = p_dir / "story_bible.json"
        bible = json.loads(sb_p.read_text(encoding="utf-8")) if sb_p.exists() else None
        clip_map = {
            s["id"]: Path(s["output_clip"])
            for s in shots
            if s.get("status") == "COMPLETED" and s.get("output_clip") and Path(s["output_clip"]).exists()
        }
        asm_res = MasterAssembler.assemble_project(
            shots_manifest=manifest,
            clip_paths_by_shot=clip_map,
            output_mp4=output_merged,
            story_bible=bible,
        )
        return {
            "success": True,
            "output_url": f"/output/{output_merged.name}",
            "clips_count": asm_res.get("shots_assembled"),
            "total_duration": asm_res.get("duration_s"),
            "ebur128": asm_res.get("ebur128"),
        }

    res = VideoProcessor.merge_project_videos(clips, output_merged, reencode=True)
    if not res.get("success"):
        raise HTTPException(status_code=500, detail=res.get("error"))

    return {
        "success": True,
        "output_url": f"/output/{output_merged.name}",
        "clips_count": res.get("clips_count"),
        "total_duration": res.get("total_duration")
    }

@app.get("/api/projects/{project_id}/download_zip")
async def download_project_zip(project_id: str):
    proj = project_mgr.get_project(project_id)
    if not proj:
        raise HTTPException(status_code=404, detail="Không tìm thấy dự án")

    p_dir = project_mgr.get_project_dir(project_id)
    safe_stem = _safe_export_stem(proj.get("name"), project_id)
    zip_path = OUTPUT_DIR / f"{safe_stem}_clips.zip"
    
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
        # Ghi file project.json
        p_json = p_dir / "project.json"
        if p_json.exists():
            zf.write(p_json, arcname="project.json")
        # Ghi các clip mp4
        clips_dir = p_dir / "clips"
        if clips_dir.exists():
            for f in clips_dir.iterdir():
                if f.is_file():
                    zf.write(f, arcname=f"clips/{f.name}")

    return FileResponse(path=str(zip_path), filename=zip_path.name, media_type="application/zip")

if __name__ == "__main__":
    import uvicorn
    print(f"[*] Starting Muse Video Studio at http://{DEFAULT_HOST}:{DEFAULT_PORT}")
    uvicorn.run("app:app", host=DEFAULT_HOST, port=DEFAULT_PORT, reload=False)
