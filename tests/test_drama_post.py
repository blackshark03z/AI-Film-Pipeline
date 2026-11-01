"""Drama post: cue clamping, SRT, assemble and loudness (needs ffmpeg)."""
from __future__ import annotations

import shutil
import subprocess

import pytest

from film_pipeline.drama import (
    SubtitleCue, assemble, clamp_cues, cue_offsets, normalize_loudness,
    write_srt,
)
from film_pipeline.drama.post import measure_ebur128, probe_video_duration

needs_ffmpeg = pytest.mark.skipif(
    not (shutil.which("ffmpeg") and shutil.which("ffprobe")),
    reason="ffmpeg not installed")


def test_clamp_cues_keeps_cue_inside_speaking_shot():
    notes: list[str] = []
    cues = [
        SubtitleCue(generation_id="SC05_g2", start_s=2.0, end_s=6.5,
                    text="Sergeant.", speaker_window=(2.5, 5.5)),
        SubtitleCue(generation_id="SC05_g2", start_s=5.6, end_s=6.0,
                    text="gone", speaker_window=(2.5, 5.5)),
        SubtitleCue(generation_id="SC01_g1", start_s=4.5, end_s=6.0,
                    text="free", speaker_window=None),
        SubtitleCue(generation_id="SC01_g1", start_s=1.0, end_s=2.0,
                    text="  ", speaker_window=None),
    ]
    out = clamp_cues(cues, notes)
    assert [(c.text, c.start_s, c.end_s) for c in out] == [
        ("Sergeant.", 2.5, 5.5), ("free", 4.5, 6.0)]
    assert len(notes) == 3 and "clamped" in notes[0]


def test_write_srt_format(tmp_path):
    path = write_srt([(3.6, 5.1, "Help you, ma'am?"),
                      (3661.25, 3662.0, "Second")], tmp_path / "a.srt")
    assert path.read_text(encoding="utf-8") == (
        "1\n00:00:03,600 --> 00:00:05,100\nHelp you, ma'am?\n\n"
        "2\n01:01:01,250 --> 01:01:02,000\nSecond\n")


def _clip(path, freq):
    subprocess.run(
        ["ffmpeg", "-v", "error", "-y", "-f", "lavfi", "-i",
         "color=c=blue:s=640x360:r=24:d=2", "-f", "lavfi", "-i",
         f"sine=f={freq}:r=48000:d=2", "-c:v", "libx264", "-pix_fmt",
         "yuv420p", "-c:a", "aac", "-shortest", str(path)], check=True)
    return path


@needs_ffmpeg
def test_assemble_and_normalize(tmp_path):
    clips = [_clip(tmp_path / "A_g1.mp4", 440),
             _clip(tmp_path / "A_g2.mp4", 660)]
    cues = clamp_cues([SubtitleCue(generation_id="A_g2", start_s=0.2,
                                   end_s=1.5, text="Hello there",
                                   speaker_window=(0.0, 2.0))])
    assert cue_offsets(clips, 3.0) == pytest.approx({"A_g1": 3.0,
                                                     "A_g2": 5.0}, abs=0.1)
    out = assemble(clips, tmp_path / "final.mp4", cues=cues,
                   title_lines=[("TEST", 96)],
                   end_lines=[("TEST", 64), ("fictional", 30)])
    assert probe_video_duration(out) == pytest.approx(11, abs=0.2)
    stats = normalize_loudness(out)
    assert abs(stats["integrated_lufs"] - (-14.0)) <= 1.0
    assert stats["peak_dbfs"] <= -0.3
    assert measure_ebur128(out) == stats
    assert probe_video_duration(out) == pytest.approx(11, abs=0.2)
