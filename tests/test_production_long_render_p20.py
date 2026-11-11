import shutil
import subprocess

import pytest

from film_pipeline.drama.post import probe_video_duration
from film_pipeline.production.edit import AudioCut, EditEvent, EditSection, TagEvent, Transition, render_cut
from film_pipeline.production.versions import render_portrait


needs_ffmpeg = pytest.mark.skipif(not (shutil.which("ffmpeg") and shutil.which("ffprobe")),
                                   reason="ffmpeg not installed")


@needs_ffmpeg
def test_portrait_render_chunks_more_than_twelve_segments_and_reuses_cache(tmp_path):
    source = tmp_path / "source.mp4"
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "lavfi", "-i",
                    "color=c=blue:s=320x180:r=24:d=1.083333", "-f", "lavfi", "-i",
                    "sine=frequency=440:sample_rate=48000:duration=1.083333", "-c:v", "libx264",
                    "-pix_fmt", "yuv420p", "-c:a", "aac", "-shortest", str(source)], check=True)
    segments = [{"event_id": f"e{i}", "mode": "fit", "start_frame": i * 2, "end_frame": (i + 1) * 2,
                "start_s": round(i * 2 / 24, 3), "end_s": round((i + 1) * 2 / 24, 3)} for i in range(13)]
    cache = tmp_path / "cache"
    out = tmp_path / "portrait.mp4"
    assert render_portrait(source, segments, out, 160, 24, cache_dir=cache) == out
    assert probe_video_duration(out) == pytest.approx(26 / 24, abs=0.12)
    out.unlink()
    render_portrait(source, segments, out, 160, 24, cache_dir=cache)
    assert probe_video_duration(out) == pytest.approx(26 / 24, abs=0.12)


@needs_ffmpeg
def test_landscape_hard_cut_render_chunks_more_than_twelve_events(tmp_path):
    from test_production_edit import LEGACY, film03_package

    pkg = film03_package(tmp_path)
    take_id = "SC01_g1_t1"
    events = [EditEvent(event_id=f"e{i}", take_id=take_id, src_out_s=0.2) for i in range(13)]
    out = tmp_path / "long-cut.mp4"
    report = render_cut(pkg, EditSection(events=events), out, clips_dir=LEGACY / "takes")
    assert len(report["rendered_events"]) == 13
    assert probe_video_duration(out) == pytest.approx(3.0 + 13 * 0.2 + 4.0, abs=0.3)


@needs_ffmpeg
def test_fine_render_keeps_dissolves_and_j_l_audio_across_chunk_boundary(tmp_path):
    from test_production_edit import LEGACY, film03_package

    pkg = film03_package(tmp_path)
    events = [EditEvent(event_id=f"e{i}", take_id="SC01_g1_t1", src_in_s=0.1, src_out_s=0.3,
                        transition=(Transition() if i == 0 else Transition(type="DISSOLVE", duration_s=0.05)),
                        audio=(AudioCut() if i == 0 else AudioCut(j_cut_s=0.02, l_cut_s=0.02)))
              for i in range(13)]
    out = tmp_path / "fine-cut.mp4"
    section = EditSection(events=events, tags=[TagEvent(event_id="e8", character="SAM", label="SAM",
                           start_s=.05, end_s=.15, anchor_x=.1, anchor_y=.2)])
    report = render_cut(pkg, section, out, clips_dir=LEGACY / "takes")
    assert report["path"] == "fine"
    assert probe_video_duration(out) == pytest.approx(3.0 + 13 * 0.2 - 12 * 0.05 + 4.0, abs=0.3)
    cache = out.parent / ".render_cache"
    before = {p.name: p.stat().st_mtime_ns for p in cache.iterdir()}
    render_cut(pkg, section, out, clips_dir=LEGACY / "takes")
    assert {p.name: p.stat().st_mtime_ns for p in cache.iterdir()} == before
