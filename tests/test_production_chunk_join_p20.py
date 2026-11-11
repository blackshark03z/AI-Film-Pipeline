"""A body joined from chunks with different colour tags must still go through the title/body concat filter."""
import shutil
import subprocess

import pytest

from film_pipeline.production.ffjoin import FfmpegTimeout, join_video_chunks, run_ffmpeg

needs_ffmpeg = pytest.mark.skipif(not (shutil.which("ffmpeg") and shutil.which("ffprobe")),
                                   reason="ffmpeg not installed")
FF = ["ffmpeg", "-v", "error", "-y"]
PROBE_TIMEOUT_S = 40


def _chunk(path, *, seconds, colour, tagged):
    colour_args = ["-colorspace", "bt709", "-color_primaries", "bt709", "-color_trc", "bt709"] if tagged else []
    subprocess.run([*FF, "-f", "lavfi", "-i", f"testsrc=s=320x180:r=24:d={seconds}", "-f", "lavfi", "-i",
                    f"sine=frequency={colour}:sample_rate=48000:duration={seconds}", "-c:v", "libx264", "-preset", "fast",
                    "-pix_fmt", "yuv420p", *colour_args, "-c:a", "pcm_s16le", str(path)], check=True, timeout=60)


def _title_then_body(tmp_path, body):
    title = tmp_path / "title.png"
    subprocess.run([*FF, "-f", "lavfi", "-i", "color=c=red:s=320x180", "-frames:v", "1", str(title)], check=True, timeout=30)
    graph = ("[0:v]setsar=1,format=yuv420p[tv];[2:a]atrim=0:1,asetpts=PTS-STARTPTS[ta];"
             "[tv][ta][1:v][1:a]concat=n=2:v=1:a=1[v][a]")
    # the same shape as assemble(): a looped title still, the joined body and a silent title track
    return subprocess.run([*FF, "-loop", "1", "-t", "1", "-r", "24", "-i", str(title), "-i", str(body),
                           "-f", "lavfi", "-i", "anullsrc=r=48000:cl=stereo", "-filter_complex", graph,
                           "-map", "[v]", "-map", "[a]", "-f", "null", "-"],
                          check=True, timeout=PROBE_TIMEOUT_S, capture_output=True)


@needs_ffmpeg
def test_joined_chunks_with_different_colour_tags_do_not_hang_the_concat_filter(tmp_path):
    first, second = tmp_path / "body_0000.mkv", tmp_path / "body_0001.mkv"
    _chunk(first, seconds=2.375, colour=440, tagged=False)     # no overlay: libx264 writes no colour description
    _chunk(second, seconds=3, colour=660, tagged=True)         # overlay graph: tagged bt709
    listing = tmp_path / "list.txt"
    listing.write_text("".join(f"file '{p.as_posix()}'\n" for p in (first, second)), encoding="utf-8")
    body = join_video_chunks(listing, tmp_path / "body.mkv")
    _title_then_body(tmp_path, body)  # a stalled ffmpeg raises TimeoutExpired here instead of blocking the suite
    tags = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "v", "-show_entries",
                           "stream=color_primaries,color_space,color_transfer", "-of", "csv=p=0", str(body)],
                          capture_output=True, text=True, check=True, timeout=30).stdout.strip()
    assert tags == "bt709,bt709,bt709"


@needs_ffmpeg
def test_join_keeps_every_frame_and_does_not_reencode(tmp_path):
    chunks = []
    for i, tagged in enumerate((False, True, False)):
        chunk = tmp_path / f"c{i}.mkv"
        _chunk(chunk, seconds=1, colour=300 + i * 100, tagged=tagged)
        chunks.append(chunk)
    listing = tmp_path / "list.txt"
    listing.write_text("".join(f"file '{p.as_posix()}'\n" for p in chunks), encoding="utf-8")
    body = join_video_chunks(listing, tmp_path / "body.mkv")
    count = subprocess.run(["ffprobe", "-v", "error", "-count_frames", "-select_streams", "v", "-show_entries",
                            "stream=nb_read_frames,codec_name", "-of", "csv=p=0", str(body)],
                           capture_output=True, text=True, check=True, timeout=30).stdout.strip()
    assert count == "h264,72"


def test_run_ffmpeg_fails_loudly_on_a_stalled_process(tmp_path, monkeypatch):
    def stall(cmd, **kwargs):
        raise subprocess.TimeoutExpired(cmd, kwargs["timeout"])
    monkeypatch.setattr(subprocess, "run", stall)
    with pytest.raises(FfmpegTimeout):
        run_ffmpeg(["ffmpeg", "-i", "x"], timeout_s=1)
