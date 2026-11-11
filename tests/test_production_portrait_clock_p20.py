import array
import shutil
import subprocess

import pytest
from PIL import Image, ImageDraw

from film_pipeline.production.versions import render_portrait

pytestmark = pytest.mark.skipif(not shutil.which("ffmpeg"), reason="ffmpeg not installed")


def pixel(path, at, crop=None):
    filters = (crop + "," if crop else "") + "scale=1:1"
    p = subprocess.run(["ffmpeg", "-v", "error", "-ss", str(at), "-i", str(path),
                        "-frames:v", "1", "-vf", filters, "-pix_fmt", "rgb24", "-f", "rawvideo", "-"],
                       capture_output=True, check=True)
    return tuple(p.stdout[:3])


def test_long_portrait_keeps_absolute_picture_audio_clock_and_png_label(tmp_path):
    source = tmp_path / "blue220_then_red880.mp4"
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "lavfi", "-i", "color=blue:s=320x180:r=24:d=2",
                    "-f", "lavfi", "-i", "color=red:s=320x180:r=24:d=2",
                    "-f", "lavfi", "-i", "sine=frequency=220:sample_rate=48000:duration=2",
                    "-f", "lavfi", "-i", "sine=frequency=880:sample_rate=48000:duration=2",
                    "-filter_complex", "[0:v][2:a][1:v][3:a]concat=n=2:v=1:a=1[v][a]",
                    "-map", "[v]", "-map", "[a]", "-c:v", "libx264", "-preset", "ultrafast",
                    "-pix_fmt", "yuv420p", "-c:a", "aac", str(source)], check=True)
    segments = [{"event_id": f"e{i}", "mode": "fit", "start_frame": i * 4, "end_frame": (i + 1) * 4,
                 "start_s": i / 6, "end_s": (i + 1) / 6} for i in range(24)]
    label = tmp_path / "label.png"
    image = Image.new("RGBA", (720, 1280), (0, 0, 0, 0))
    ImageDraw.Draw(image).rectangle((0, 0, 40, 40), fill=(0, 255, 0, 255))
    image.save(label)
    for marked in (False, True):
        out = tmp_path / ("marked.mp4" if marked else "plain.mp4")
        render_portrait(source, segments, out, 180, 24,
                        label=(label, 0, 4) if marked else None, cache_dir=tmp_path / "cache")
        early, late = pixel(out, 0.5), pixel(out, 3)
        assert early[2] > early[0] + 30
        assert late[0] > late[2] + 30, "later chunks repeated source time zero"
        pcm = subprocess.run(["ffmpeg", "-v", "error", "-ss", "3", "-t", "0.25", "-i", str(out),
                              "-ac", "1", "-ar", "8000", "-f", "s16le", "-"], capture_output=True, check=True).stdout
        samples = array.array("h", pcm)
        crossings = sum(a <= 0 < b for a, b in zip(samples, samples[1:]))
        assert 750 < crossings / (len(samples) / 8000) < 1000, "cached audio came from the wrong interval"
        if marked:
            r, g, b = pixel(out, 3, "crop=32:32:0:0")
            assert g > r + 70 and g > b + 70, "label overlay did not use its PNG input"
