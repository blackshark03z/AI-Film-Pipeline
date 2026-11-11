from film_pipeline.production import versions as V
import json
import shutil
import subprocess

import pytest


def test_portrait_windows_stop_at_verified_picture_parts_and_keep_local_identity():
    segments = [{"event_id": f"e{i}", "mode": "fit", "start_frame": i * 120, "end_frame": (i + 1) * 120,
                 "start_s": i * 5., "end_s": (i + 1) * 5.} for i in range(30)]
    parts = [{"key": "a", "start_frame": 0, "end_frame": 1680},
             {"key": "b", "start_frame": 1680, "end_frame": 3600}]
    windows = V.portrait_windows(segments, 24, parts)
    assert all(len(w) <= 12 and w[-1]["end_frame"] - w[0]["start_frame"] <= 1440 for w in windows)
    assert all(not (w[0]["start_frame"] < 1680 < w[-1]["end_frame"]) for w in windows)
    # Same later scene, shifted one second by an earlier edit, has the same semantic input identity.
    assert V.picture_identity(parts, 1680, 3000) == V.picture_identity(
        [{"key": "a", "start_frame": 0, "end_frame": 1656},
         {"key": "b", "start_frame": 1656, "end_frame": 3576}], 1656, 2976)


def test_picture_parts_require_exact_source_hash_plan_and_ordered_coverage(tmp_path, monkeypatch):
    from film_pipeline.drama import post
    source = tmp_path / "clean.mp4"
    source.write_bytes(b"verified-source")
    plan = {"total_s": 4}
    parts = [{"key": "a" * 64, "start_frame": 0, "end_frame": 48},
             {"key": "b" * 64, "start_frame": 48, "end_frame": 96}]
    report = {"output_sha256": V.sha256_file(source), "planned": plan, "picture_parts": parts}
    path = source.with_suffix(".cut.json")
    monkeypatch.setattr(post, "probe_video_duration", lambda p: 4)
    def write():
        path.write_text(json.dumps(report), encoding="utf-8")
    write()
    assert V.verified_picture_parts(source, plan, 24) == parts
    assert V.verified_picture_parts(source, {"total_s": 5}, 24) is None
    parts[1]["start_frame"] = 49
    write()
    assert V.verified_picture_parts(source, plan, 24) is None
    parts[1]["start_frame"] = 47
    write()
    assert V.verified_picture_parts(source, plan, 24) is None
    parts[1]["start_frame"] = 48
    parts[1]["end_frame"] = 95
    write()
    assert V.verified_picture_parts(source, plan, 24) is None
    parts[1]["end_frame"] = 96
    report["output_sha256"] = "f" * 64
    write()
    assert V.verified_picture_parts(source, plan, 24) is None
    path.write_text('{"legacy":true}', encoding="utf-8")
    assert V.verified_picture_parts(source, plan, 24) is None


@pytest.mark.skipif(not shutil.which("ffmpeg"), reason="ffmpeg not installed")
def test_portrait_reuses_unchanged_picture_after_take_trim_and_audio_changes(tmp_path, monkeypatch):
    from PIL import Image
    from test_production_portrait_clock_p20 import pixel
    def source(name, first_s, second):
        path = tmp_path / name
        subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "lavfi", "-i", f"color=blue:s=320x180:r=24:d={first_s}",
                        "-f", "lavfi", "-i", f"color={second}:s=320x180:r=24:d={47/24}", "-f", "lavfi", "-i",
                        f"sine=frequency=220:sample_rate=48000:duration={first_s + 47/24}",
                        "-filter_complex", "[0:v][1:v]concat=n=2:v=1:a=0[v]", "-map", "[v]", "-map", "2:a",
                        "-c:v", "libx264", "-preset", "ultrafast", "-c:a", "aac", str(path)], check=True)
        return path
    original = source("original.mp4", 2, "red")
    changed = source("changed.mp4", 2, "yellow")
    trimmed = source("trimmed.mp4", 47/24, "yellow")
    segments = [{"event_id": f"e{i}", "mode": "fit", "start_frame": i * 4, "end_frame": (i + 1) * 4,
                 "start_s": i / 6, "end_s": (i + 1) / 6} for i in range(24)]
    segments[-1].update(end_frame=95, end_s=95/24)
    label = tmp_path / "label.png"
    Image.new("RGBA", (720, 1280), (0, 0, 0, 0)).save(label)
    parts = [{"key": "a" * 64, "start_frame": 0, "end_frame": 48},
             {"key": "b" * 64, "start_frame": 48, "end_frame": 95}]
    saves = []
    save = V._save_render
    def capture(cache, key, source, suffix):
        saves.append(key)
        return save(cache, key, source, suffix)
    monkeypatch.setattr(V, "_save_render", capture)
    out = tmp_path / "portrait.mp4"
    kwargs = {"height": 180, "fps": 24, "cache_dir": tmp_path / "cache", "picture_parts": parts,
              "label": (label, 0, 95/24)}
    V.render_portrait(original, segments, out, **kwargs)
    assert len(saves) == 2
    parts[1]["key"] = "c" * 64
    saves.clear()
    V.render_portrait(changed, segments, out, **kwargs)
    assert len(saves) == 1
    assert pixel(out, .5)[2] > pixel(out, .5)[0] + 30
    late = pixel(out, 3)
    assert late[0] > late[2] + 30 and late[1] > late[2] + 30
    audio = tmp_path / "new-audio.m4a"
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "lavfi", "-i",
                    f"sine=frequency=1030:sample_rate=48000:duration={95/24}", "-c:a", "aac", str(audio)], check=True)
    saves.clear()
    V.render_portrait(changed, segments, out, audio_from=audio, **kwargs)
    assert saves == []
    import array
    pcm = subprocess.run(["ffmpeg", "-v", "error", "-ss", "3", "-t", "0.25", "-i", str(out),
                          "-ac", "1", "-ar", "8000", "-f", "s16le", "-"], capture_output=True, check=True).stdout
    samples = array.array("h", pcm)
    crossings = sum(a <= 0 < b for a, b in zip(samples, samples[1:]))
    assert 950 < crossings / (len(samples) / 8000) < 1100
    later = [{**s, "start_frame": s["start_frame"] - 1, "end_frame": s["end_frame"] - 1,
              "start_s": s["start_s"] - 1/24, "end_s": s["end_s"] - 1/24} for s in segments[12:]]
    earlier = [dict(s) for s in segments[:12]]
    earlier[-1].update(end_frame=47, end_s=47/24)
    trimmed_segments = [*earlier, *later]
    parts[0]["end_frame"] = 47
    parts[1].update(start_frame=47, end_frame=94)
    kwargs["label"] = (label, 0, 94/24)
    saves.clear()
    V.render_portrait(trimmed, trimmed_segments, out, **kwargs)
    assert len(saves) == 1, "unchanged later scene must retain its portrait picture cache"
