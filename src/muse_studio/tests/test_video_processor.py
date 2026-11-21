import os
import shutil
import tempfile
from pathlib import Path
import pytest
from core.video_processor import VideoProcessor

@pytest.fixture
def temp_video_dir():
    temp_dir = Path(tempfile.mkdtemp())
    yield temp_dir
    shutil.rmtree(temp_dir, ignore_errors=True)

def test_synthetic_video_and_info(temp_video_dir):
    clip1 = temp_video_dir / "clip1.mp4"
    ok = VideoProcessor.create_synthetic_test_clip(clip1, duration_s=2.0, text="Shot 1")
    assert ok is True
    assert clip1.exists()

    info = VideoProcessor.get_video_info(clip1)
    assert info["valid"] is True
    assert info["width"] == 1280
    assert info["height"] == 720
    assert info["duration"] > 1.5

def test_extract_last_frame(temp_video_dir):
    clip = temp_video_dir / "clip_test.mp4"
    VideoProcessor.create_synthetic_test_clip(clip, duration_s=2.0, text="End Frame")
    
    last_frame = temp_video_dir / "last_frame.png"
    ok = VideoProcessor.extract_last_frame(clip, last_frame)
    assert ok is True
    assert last_frame.exists()
    assert last_frame.stat().st_size > 0

def test_merge_videos(temp_video_dir):
    c1 = temp_video_dir / "c1.mp4"
    c2 = temp_video_dir / "c2.mp4"
    VideoProcessor.create_synthetic_test_clip(c1, duration_s=1.5, text="Part 1")
    VideoProcessor.create_synthetic_test_clip(c2, duration_s=1.5, text="Part 2")

    merged = temp_video_dir / "merged.mp4"
    res = VideoProcessor.merge_project_videos([c1, c2], merged, reencode=True)
    assert res["success"] is True
    assert merged.exists()
    assert res["clips_count"] == 2
    assert res["total_duration"] > 2.5
