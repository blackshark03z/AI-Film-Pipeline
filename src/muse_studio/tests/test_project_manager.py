import os
import shutil
import tempfile
from pathlib import Path
import pytest
from core.project_manager import ProjectManager

@pytest.fixture
def temp_project_mgr():
    temp_dir = Path(tempfile.mkdtemp())
    mgr = ProjectManager(projects_dir=temp_dir)
    yield mgr
    shutil.rmtree(temp_dir, ignore_errors=True)

def test_project_crud(temp_project_mgr):
    proj = temp_project_mgr.create_project("Marcus Action", mode="batch_parallel")
    assert proj["name"] == "Marcus Action"
    assert proj["mode"] == "batch_parallel"
    assert proj["status"] == "IDLE"

    pid = proj["id"]
    p_data = temp_project_mgr.get_project(pid)
    assert p_data["id"] == pid

    updated = temp_project_mgr.update_project(pid, mode="chained_continuity")
    assert updated["mode"] == "chained_continuity"

def test_shots_management(temp_project_mgr):
    proj = temp_project_mgr.create_project("Test Shots")
    pid = proj["id"]

    shot1 = temp_project_mgr.add_shot(pid, prompt="Wide shot of diner", reference_images=["ref1.png", "ref2.png"], dialogue="Hello!")
    assert shot1["order"] == 1
    assert shot1["dialogue"] == "Hello!"
    assert len(shot1["reference_images"]) == 2

    shot2 = temp_project_mgr.add_shot(pid, prompt="Close up of police officer")
    assert shot2["order"] == 2

    p_data = temp_project_mgr.get_project(pid)
    assert p_data["total_shots"] == 2

    # Update shot
    temp_project_mgr.update_shot(pid, shot1["id"], status="COMPLETED")
    p_data = temp_project_mgr.get_project(pid)
    assert p_data["completed_shots"] == 1

    # Delete shot
    temp_project_mgr.delete_shot(pid, shot1["id"])
    p_data = temp_project_mgr.get_project(pid)
    assert p_data["total_shots"] == 1

def test_csv_import(temp_project_mgr):
    proj = temp_project_mgr.create_project("CSV Project")
    pid = proj["id"]

    csv_file = temp_project_mgr.get_project_dir(pid) / "test.csv"
    csv_content = """shot_id,prompt,dialogue,refs\nsh01,A detective sits in car,Watch out,ref_car.png;ref_city.png\nsh02,He looks out the window,,ref_car.png\n"""
    csv_file.write_text(csv_content, encoding="utf-8")

    count = temp_project_mgr.import_shots_from_csv(pid, csv_file)
    assert count == 2

    p_data = temp_project_mgr.get_project(pid)
    assert len(p_data["shots"]) == 2
    assert p_data["shots"][0]["dialogue"] == "Watch out"
    assert len(p_data["shots"][0]["reference_images"]) == 2
