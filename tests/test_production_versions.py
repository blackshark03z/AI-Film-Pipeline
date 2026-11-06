import json
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

from film_pipeline.production import versions as V
from film_pipeline.production.edit import EditEvent, EditSection, Reframe, TagEvent
from film_pipeline.production.package import load_package

ROOT = Path(__file__).resolve().parents[1]
FILM03 = ROOT / "films" / "film03_front_desk"
TOOL = ROOT / "tools" / "film.py"
needs_ffmpeg = pytest.mark.skipif(not (shutil.which("ffmpeg") and shutil.which("ffprobe")), reason="ffmpeg not installed")

PLAN = {"title_s": 3.0, "body_end_s": 12.0, "end_s": 4.0, "total_s": 16.0,
        "events": [{"event_id": "a", "kind": "TAKE", "take_id": "SC02_g1_t1", "start_s": 3.0, "end_s": 6.0, "duration_s": 3.0},
                   {"event_id": "b", "kind": "TAKE", "take_id": "SC03_g1_t1", "start_s": 6.0, "end_s": 9.0, "duration_s": 3.0},
                   {"event_id": "c", "kind": "CARD", "take_id": "", "start_s": 9.0, "end_s": 10.0, "duration_s": 1.0},
                   {"event_id": "d", "kind": "TAKE", "take_id": "SC04_g2_t1", "start_s": 10.0, "end_s": 12.0, "duration_s": 2.0}]}


def section(tags=()):
    return EditSection(events=[EditEvent(event_id="a", take_id="SC02_g1_t1"), EditEvent(event_id="b", take_id="SC03_g1_t1"),
                               EditEvent(event_id="c", kind="CARD", card_lines=["x"], card_duration_s=1.0),
                               EditEvent(event_id="d", take_id="SC04_g2_t1")], tags=list(tags))


def tag(event_id, x, start=0.2, end=1.0, who="Nora"):
    return TagEvent(event_id=event_id, character=who, label=who, start_s=start, end_s=end, anchor_x=x, anchor_y=0.4)


def test_segments_follow_the_tag_the_reframe_and_the_centre():
    sec = section([tag("a", 0.8)])
    segs, problems = V.portrait_segments(PLAN, sec, {"d": Reframe(x=0.1, y=0.1, w=0.5, h=0.5)}, 1280, 720, 24.0)
    by = {s["event_id"]: s for s in segs}
    assert by["a"]["focus_source"] == "tag" and by["a"]["crop_x"] == (round(0.8 * 1280 - 202) // 2 * 2)
    assert by["b"]["focus_source"] == "center" and by["b"]["crop_x"] == (1280 - 404) // 2 // 2 * 2
    assert by["d"]["focus_source"] == "reframe" and by["d"]["focus"] == 0.35
    assert {s["mode"] for s in segs if s["event_id"] in ("title", "c", "end")} == {"fit"}
    assert [p["code"] for p in problems] == ["PORTRAIT_FOCUS_UNKNOWN"]
    assert problems[0]["detail"].startswith("b:")


def test_the_window_stays_inside_the_frame():
    segs, _ = V.portrait_segments(PLAN, section([tag("a", 0.99), tag("b", 0.0)]), {}, 1280, 720, 24.0)
    by = {s["event_id"]: s for s in segs}
    assert by["a"]["crop_x"] == 1280 - 404 and by["b"]["crop_x"] == 0


def test_segments_partition_the_clock_in_frames():
    segs, _ = V.portrait_segments(PLAN, section(), {}, 1280, 720, 24.0)
    assert segs[0]["start_frame"] == 0 and segs[-1]["end_frame"] == 16 * 24
    assert all(a["end_frame"] == b["start_frame"] for a, b in zip(segs, segs[1:]))


def test_faces_further_apart_than_the_window_warn():
    _, problems = V.portrait_segments(PLAN, section([tag("a", 0.15), tag("a", 0.85, who="Ray")]), {}, 1280, 720, 24.0)
    assert "PORTRAIT_SPREAD" in [p["code"] for p in problems]
    _, near = V.portrait_segments(PLAN, section([tag("a", 0.45), tag("a", 0.55, who="Ray")]), {}, 1280, 720, 24.0)
    assert "PORTRAIT_SPREAD" not in [p["code"] for p in near]


def test_the_graph_crops_takes_and_fits_cards():
    segs, _ = V.portrait_segments(PLAN, section(), {}, 1280, 720, 24.0)
    graph = V.portrait_graph(segs, 720)
    assert graph.count("crop=404:720") == 3 and graph.count("pad=720:1280") == 3
    assert graph.endswith(f"concat=n={len(segs)}:v=1:a=0[v]")


def test_text_windows_cover_tags_and_cues():
    sec = section([tag("b", 0.5, start=0.5, end=1.5)])
    found = V.text_windows(sec, PLAN, {"cues": [{"abs_start_s": 4.0, "abs_end_s": 5.0}, {"start_s": 1}]})
    assert (6.5, 7.5) in found and (4.0, 5.0) in found and len(found) == 2


def make_clip(path: Path, seconds=6, color=None):
    """A clip whose bytes differ per file (the take log refuses the same bytes under two generations)."""
    src = f"testsrc2=size=1280x720:rate=24:duration={seconds}" if color is None else f"color=c={color}:size=1280x720:rate=24:duration={seconds}"
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "lavfi", "-i", src, "-f", "lavfi", "-i",
                    f"sine=frequency=500:sample_rate=48000:duration={seconds}", "-af", "volume=0.3", "-c:v", "libx264", "-pix_fmt",
                    "yuv420p", "-c:a", "aac", "-metadata", f"comment={path.stem}", str(path)], check=True)
    return path


@needs_ffmpeg
def test_frame_stats_tell_black_from_picture(tmp_path):
    black = tmp_path / "b.jpg"
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "lavfi", "-i", "color=c=black:size=320x180:d=1", "-frames:v", "1", str(black)], check=True)
    pic = tmp_path / "p.jpg"
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "lavfi", "-i", "testsrc2=size=320x180:d=1", "-frames:v", "1", str(pic)], check=True)
    assert V.frame_stats(black)[0] < V.THUMB_MIN_LUMA
    luma, spread = V.frame_stats(pic)
    assert V.THUMB_MIN_LUMA < luma < V.THUMB_MAX_LUMA and spread > V.THUMB_MIN_CONTRAST


def film(tmp_path: Path):
    root = tmp_path / "film"
    root.mkdir()
    for name in ("film.json", "script.fountain", "01_story.json", "02_direction.json", "03_preprod.json", "04_shots.json"):
        shutil.copyfile(FILM03 / name, root / name)
    return root


def register(root: Path, clips: Path, gids, black=()):
    from film_pipeline.production import takes as T
    clips.mkdir(exist_ok=True)
    for gid in gids:
        path = make_clip(clips / f"{gid}.mp4", color="black" if gid in black else None)
        T.register_take(root, "film03_front_desk", gid, path, prompt_text=f"p {gid}", route="r", model="m", credits=1.0)


def run(*args):
    return subprocess.run([sys.executable, str(TOOL), *args], capture_output=True, text=True, encoding="utf-8", cwd=ROOT)


def cut_and_mix(root: Path, clips: Path, events, tags=()):
    (root / "05_edit.json").write_text(EditSection(events=events, tags=list(tags)).model_dump_json(), encoding="utf-8")
    cut = root / "media" / "cut" / "titled_cut.mp4"
    assert run("titles", "--film", str(root), "--clips", str(clips), "--langs", "en,vi", "--render", "--out", str(cut)).returncode == 0
    assert run("mix", "--film", str(root), "--cut", str(cut), "--out", str(root / "media" / "cut" / "mixed.mp4")).returncode == 0
    return cut


@needs_ffmpeg
def test_cli_builds_the_portrait_version_the_thumbnails_and_the_draft(tmp_path):
    root, clips = film(tmp_path), tmp_path / "clips"
    register(root, clips, ["SC02_g1", "SC03_g1", "SC04_g2"])
    cut = cut_and_mix(root, clips, [EditEvent(event_id="a", take_id="SC02_g1_t1"), EditEvent(event_id="b", take_id="SC03_g1_t1"),
                                     EditEvent(event_id="d", take_id="SC04_g2_t1")])
    done = run("versions", "--film", str(root), "--cut-report", str(cut.with_suffix(".cut.json")), "--generators", "Google Flow Omni 1.1 Flash")
    body = json.loads(done.stdout)
    assert done.returncode == 0 and body["ok"], body
    portrait = next(v for v in body["versions"] if v["name"] == "portrait_9x16")
    assert (portrait["width"], portrait["height"]) == (720, 1280) and portrait["fps"] == 24.0
    master = root / "media" / "cut" / "mixed.mp4"
    probe = lambda p, e: float(subprocess.run(["ffprobe", "-v", "error", "-show_entries", f"format={e}", "-of", "csv=p=0", str(p)],
                                              capture_output=True, text=True).stdout)
    assert abs(probe(root / portrait["file"], "duration") - probe(master, "duration")) < 0.15
    audio = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "a", "-show_entries", "stream=codec_name", "-of", "csv=p=0",
                            str(root / portrait["file"])], capture_output=True, text=True).stdout.strip()
    assert audio == "aac"
    assert [t["device"] for t in body["thumbnails"]][0] == "hold"          # the reveal moment first
    assert all((root / t["file"]).is_file() and t["sha256"] for t in body["thumbnails"]) and len(body["thumbnails"]) == 3
    assert "PORTRAIT_BURNED_TEXT" in {p["code"] for p in body["problems"]}   # the titled master burns its cues
    meta = json.loads((root / "versions" / "metadata.json").read_text(encoding="utf-8"))
    assert meta["status"] == "DRAFT_NOT_PUBLISHED" and meta["title"]["source"] == "The Front Desk"
    assert meta["title"]["vi"] and meta["title"]["vi"] != "The Front Desk"
    assert "Google Flow Omni 1.1 Flash" in meta["ai_disclosure"]["text"]["en"] and meta["ai_disclosure"]["synthetic_persons"]
    assert meta["description"].startswith("On her first morning") and meta["runtime_s"] > 10
    assert {v["name"] for v in meta["versions"]} == {"master_16x9", "portrait_9x16"} and all(v["sha256"] for v in meta["versions"])
    post = json.loads((root / "06_post.json").read_text(encoding="utf-8"))
    assert post["versions"]["ok"] and post["versions"]["summary"]["thumbnails"] == 3
    assert not (root / "versions" / "thumbs" / "thumb_04.jpg").exists()


@needs_ffmpeg
def test_a_dark_moment_gives_no_thumbnail_and_a_missing_generator_warns(tmp_path):
    root, clips = film(tmp_path), tmp_path / "clips"
    register(root, clips, ["SC02_g1", "SC03_g1", "SC04_g2"], black=("SC02_g1",))
    cut = cut_and_mix(root, clips, [EditEvent(event_id="a", take_id="SC02_g1_t1"), EditEvent(event_id="b", take_id="SC03_g1_t1"),
                                     EditEvent(event_id="d", take_id="SC04_g2_t1")])
    body = json.loads(run("versions", "--film", str(root), "--cut-report", str(cut.with_suffix(".cut.json"))).stdout)
    codes = {p["code"] for p in body["problems"]}
    assert "THUMB_REJECTED" in codes and "META_NO_GENERATORS" in codes
    assert [t["event_id"] for t in body["thumbnails"]] == ["d", "b"]       # push before reaction; the black hold has none
    meta = json.loads((root / "versions" / "metadata.json").read_text(encoding="utf-8"))
    assert meta["ai_disclosure"]["generators"] == "" and "AI" in meta["ai_disclosure"]["text"]["en"]


@needs_ffmpeg
def test_a_tag_moves_the_crop_and_a_clean_source_drops_the_burned_text_warning(tmp_path):
    root, clips = film(tmp_path), tmp_path / "clips"
    register(root, clips, ["SC02_g1", "SC03_g1", "SC04_g2"])
    pre = load_package(root).typed["preprod"]
    who = next(iter(pre.characters))
    cut = cut_and_mix(root, clips, [EditEvent(event_id="a", take_id="SC02_g1_t1"), EditEvent(event_id="b", take_id="SC03_g1_t1"),
                                     EditEvent(event_id="d", take_id="SC04_g2_t1")], tags=[tag("a", 0.8, who=who)])
    clean = tmp_path / "clean.mp4"
    shutil.copyfile(root / "media" / "cut" / "mixed.mp4", clean)
    body = json.loads(run("versions", "--film", str(root), "--cut-report", str(cut.with_suffix(".cut.json")),
                          "--portrait-source", str(clean)).stdout)
    assert "PORTRAIT_BURNED_TEXT" not in {p["code"] for p in body["problems"]}
    seg = next(s for s in next(v for v in body["versions"] if v["name"] == "portrait_9x16")["segments"] if s["event_id"] == "a")
    assert seg["focus_source"] == "tag" and seg["crop_x"] > 700
    missing = run("versions", "--film", str(root), "--video", str(tmp_path / "none.mp4"))
    assert missing.returncode == 2
