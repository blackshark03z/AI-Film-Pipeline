import csv
import json
import os
import re
import shutil
import uuid
import threading
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field

try:
    from .config import PROJECTS_DIR
except ImportError:
    from core.config import PROJECTS_DIR

class ShotModel(BaseModel):
    id: str = Field(default_factory=lambda: f"shot_{uuid.uuid4().hex[:6]}")
    order: int = 1
    prompt: str
    dialogue: Optional[str] = None
    reference_images: List[str] = Field(default_factory=list)
    status: str = "PENDING"  # PENDING, RUNNING, COMPLETED, FAILED, SKIPPED
    assigned_account: Optional[str] = None
    progress: int = 0
    output_clip: Optional[str] = None
    last_frame_path: Optional[str] = None
    error: Optional[str] = None
    updated_at: Optional[str] = None

class ProjectModel(BaseModel):
    id: str = Field(default_factory=lambda: f"proj_{uuid.uuid4().hex[:8]}")
    name: str
    mode: str = "batch_parallel"  # "batch_parallel" or "chained_continuity"
    status: str = "IDLE"  # IDLE, RUNNING, PAUSED, COMPLETED
    created_at: str = Field(default_factory=lambda: datetime.now().isoformat())
    updated_at: str = Field(default_factory=lambda: datetime.now().isoformat())
    shots: List[ShotModel] = Field(default_factory=list)

class ProjectManager:
    def __init__(self, projects_dir: Path = PROJECTS_DIR):
        self.projects_dir = projects_dir
        self.projects_dir.mkdir(parents=True, exist_ok=True)
        self.lock = threading.RLock()

    def get_project_dir(self, project_id: str) -> Path:
        p_dir = self.projects_dir / project_id
        p_dir.mkdir(parents=True, exist_ok=True)
        (p_dir / "refs").mkdir(parents=True, exist_ok=True)
        (p_dir / "clips").mkdir(parents=True, exist_ok=True)
        return p_dir

    def _get_project_file(self, project_id: str) -> Path:
        return self.get_project_dir(project_id) / "project.json"

    @staticmethod
    def _write_project_atomic(p_file: Path, data: Dict[str, Any]) -> None:
        p_file.parent.mkdir(parents=True, exist_ok=True)
        tmp_f = p_file.with_name(f".{p_file.name}.tmp.{os.getpid()}.{threading.get_ident()}")
        tmp_f.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
        os.replace(tmp_f, p_file)

    def list_projects(self) -> List[Dict[str, Any]]:
        with self.lock:
            projects = []
            for item in self.projects_dir.iterdir():
                if item.is_dir():
                    p_file = item / "project.json"
                    if p_file.exists():
                        try:
                            data = json.loads(p_file.read_text(encoding="utf-8"))
                            # Tính toán tiến độ tóm tắt
                            shots = data.get("shots", [])
                            data["total_shots"] = len(shots)
                            data["completed_shots"] = sum(1 for s in shots if s.get("status") == "COMPLETED")
                            projects.append(data)
                        except Exception:
                            pass
            projects.sort(key=lambda x: x.get("updated_at", ""), reverse=True)
            return projects

    def get_project(self, project_id: str) -> Optional[Dict[str, Any]]:
        with self.lock:
            p_file = self._get_project_file(project_id)
            if not p_file.exists():
                return None
            try:
                data = json.loads(p_file.read_text(encoding="utf-8"))
                shots = data.get("shots", [])
                data["total_shots"] = len(shots)
                data["completed_shots"] = sum(1 for s in shots if s.get("status") == "COMPLETED")
                return data
            except Exception:
                return None

    def create_project(self, name: str, mode: str = "batch_parallel") -> Dict[str, Any]:
        with self.lock:
            new_proj = ProjectModel(name=name.strip(), mode=mode)
            p_dir = self.get_project_dir(new_proj.id)
            p_file = p_dir / "project.json"
            data = new_proj.model_dump()
            self._write_project_atomic(p_file, data)
            data["total_shots"] = 0
            data["completed_shots"] = 0
            return data

    def update_project(self, project_id: str, **kwargs) -> Optional[Dict[str, Any]]:
        with self.lock:
            data = self.get_project(project_id)
            if not data:
                return None
            for k, v in kwargs.items():
                if v is not None:
                    data[k] = v
            data["updated_at"] = datetime.now().isoformat()
            p_file = self._get_project_file(project_id)
            self._write_project_atomic(p_file, data)
            return data

    def delete_project(self, project_id: str) -> bool:
        with self.lock:
            p_dir = self.projects_dir / project_id
            if p_dir.exists():
                try:
                    shutil.rmtree(p_dir, ignore_errors=True)
                    return True
                except Exception:
                    return False
            return False

    def add_shot(self, project_id: str, prompt: str, reference_images: Optional[List[str]] = None,
                 dialogue: Optional[str] = None, shot_id: Optional[str] = None) -> Optional[Dict[str, Any]]:
        with self.lock:
            data = self.get_project(project_id)
            if not data:
                return None

            shots = data.get("shots", [])
            order = len(shots) + 1
            sid = shot_id if shot_id else f"shot_{order:02d}"
            
            # Đảm bảo không trùng ID
            existing_ids = {s["id"] for s in shots}
            while sid in existing_ids:
                sid = f"{sid}_{uuid.uuid4().hex[:3]}"

            shot = ShotModel(
                id=sid,
                order=order,
                prompt=prompt.strip(),
                dialogue=dialogue.strip() if dialogue else None,
                reference_images=reference_images or [],
                updated_at=datetime.now().isoformat()
            )
            shots.append(shot.model_dump())
            data["shots"] = shots
            data["updated_at"] = datetime.now().isoformat()
            self._write_project_atomic(self._get_project_file(project_id), data)
            return shot.model_dump()

    def update_shot(self, project_id: str, shot_id: str, **kwargs) -> Optional[Dict[str, Any]]:
        with self.lock:
            data = self.get_project(project_id)
            if not data:
                return None

            target = None
            for s in data.get("shots", []):
                if s["id"] == shot_id:
                    for k, v in kwargs.items():
                        if v is not None:
                            s[k] = v
                    s["updated_at"] = datetime.now().isoformat()
                    target = s
                    break

            if target:
                data["updated_at"] = datetime.now().isoformat()
                self._write_project_atomic(self._get_project_file(project_id), data)
            return target

    def delete_shot(self, project_id: str, shot_id: str) -> bool:
        with self.lock:
            data = self.get_project(project_id)
            if not data:
                return False

            shots = [s for s in data.get("shots", []) if s["id"] != shot_id]
            if len(shots) == len(data.get("shots", [])):
                return False

            # Đánh số lại order
            for idx, s in enumerate(shots, start=1):
                s["order"] = idx

            data["shots"] = shots
            data["updated_at"] = datetime.now().isoformat()
            self._write_project_atomic(self._get_project_file(project_id), data)
            return True

    def import_shots_from_csv(self, project_id: str, csv_path: Path) -> int:
        """Nhập danh sách shot từ file CSV."""
        csv_path = Path(csv_path)
        if not csv_path.exists():
            return 0

        imported = 0
        with open(csv_path, mode="r", encoding="utf-8-sig") as f:
            reader = csv.DictReader(f)
            for row in reader:
                # Tìm cột prompt
                prompt = row.get("prompt") or row.get("cau_lenh") or row.get("Prompt") or row.get("text")
                if not prompt:
                    continue

                sid = row.get("shot_id") or row.get("id") or row.get("stt") or row.get("Shot")
                dialogue = row.get("dialogue") or row.get("thoai") or row.get("voice")
                refs_raw = row.get("reference_images") or row.get("refs") or row.get("anh_tham_chieu") or row.get("images")
                
                refs = []
                if refs_raw:
                    # Tách bằng dấu phẩy hoặc chấm phẩy
                    refs = [r.strip() for r in re.split(r"[,;|\n]", refs_raw) if r.strip()]

                self.add_shot(project_id, prompt=prompt, reference_images=refs, dialogue=dialogue, shot_id=sid)
                imported += 1
        return imported

    def import_shots_from_json(self, project_id: str, json_data_or_path: Any) -> int:
        """Nhập danh sách shot từ JSON object hoặc path."""
        data = None
        if isinstance(json_data_or_path, (str, Path)):
            p = Path(json_data_or_path)
            if p.exists():
                data = json.loads(p.read_text(encoding="utf-8"))
        elif isinstance(json_data_or_path, (dict, list)):
            data = json_data_or_path

        if not data:
            return 0

        raw_shots = data if isinstance(data, list) else data.get("shots") or data.get("prompts") or []
        imported = 0
        for s in raw_shots:
            if isinstance(s, str):
                self.add_shot(project_id, prompt=s)
                imported += 1
            elif isinstance(s, dict):
                prompt = s.get("prompt") or s.get("compiled_prompt") or s.get("text")
                if not prompt:
                    continue
                sid = s.get("shot_id") or s.get("id")
                dialogue = s.get("dialogue")
                refs = s.get("reference_images") or s.get("ingredients") or s.get("images") or []
                if isinstance(refs, str):
                    refs = [refs]
                self.add_shot(project_id, prompt=prompt, reference_images=refs, dialogue=dialogue, shot_id=sid)
                imported += 1
        return imported
