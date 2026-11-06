import json
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

from film_pipeline.production import color as C
from film_pipeline.production import takes as T
from film_pipeline.production.edit import EditEvent, EditSection, Transition, render_cut
from film_pipeline.production.package import load_package

ROOT = Path(__file__).resolve().parents[1]
FILM03 = ROOT / "films" / "film03_front_desk"
TOOL = ROOT / "tools" / "film.py"
FILES = ("film.json", "script.fountain", "01_story.json", "02_direction.json", "03_preprod.json", "04_shots.json")
needs_ffmpeg = pytest.mark.skipif(not (shutil.which("ffmpeg") and shutil.which("ffprobe")), reason="ffmpeg not installed")
GRAY, WARM, RED = "0x808080", "0xA08060", "0xFF0000"


def solid(path: Path, colour: str, seconds: float, freq: int) -> Path:
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "lavfi", "-i", f"color=c={colour}:size=320x180:rate=24:duration={seconds}",
                    "-f", "lavfi", "-i", f"sine=frequency={freq}:sample_rate=48000:duration={seconds}", "-c:v", "libx264",
                    "-pix_fmt", "yuv420p", "-c:a", "aac", "-shortest", str(path)], check=True)
    return path


def make_film(tmp_path: Path, colours: dict[str, str], seconds: float = 3.0):
    root = tmp_path / "film"
    root.mkdir()
    for name in FILES:
        shutil.copyfile(FILM03 / name, root / name)
    clips = tmp_path / "clips"
    clips.mkdir()
    for i, (gid, colour) in enumerate(colours.items()):
        T.register_take(root, "film03_front_desk", gid, solid(clips / f"{gid}.mp4", colour, seconds, 300 + 100 * i),
                        prompt_text=f"prompt {gid}", route="r", model="m", credits=12.0)
    return root, clips


def write_edl(root: Path, section: EditSection) -> None:
    (root / "05_edit.json").write_text(section.model_dump_json(indent=2), encoding="utf-8")


def ev(event_id, gid, **kw):
    return EditEvent(event_id=event_id, take_id=f"{gid}_t1", **kw)


def rgb_at(video: Path, at_s: float) -> tuple[int, int, int]:
    raw = subprocess.run(["ffmpeg", "-v", "error", "-ss", f"{at_s:.3f}", "-i", str(video), "-frames:v", "1", "-vf",
                          "crop=40:40:140:70,scale=1:1", "-f", "rawvideo", "-pix_fmt", "rgb24", "-"],
                         capture_output=True, check=True).stdout
    return raw[0], raw[1], raw[2]


@needs_ffmpeg
def test_frame_stats_read_the_colour_of_a_clip(tmp_path):
    stats = C.frame_stats(solid(tmp_path / "w.mp4", WARM, 2.0, 440))
    assert abs(stats["r"] - 160) < 6 and abs(stats["g"] - 128) < 6 and abs(stats["b"] - 96) < 6
    assert stats["r"] > stats["luma"] > stats["b"]


@needs_ffmpeg
def test_a_scene_is_matched_to_the_median_and_the_numbers_improve(tmp_path):
    root, clips = make_film(tmp_path, {"SC01_g1": GRAY, "SC01_g2": WARM})
    report = C.match(load_package(root), clips_dir=clips)
    g1, g2 = report["shots"]
    assert report["ok"] and g1["reference"] == "median" and not report["problems"]
    assert g1["deviation_before"] > 10 and g2["deviation_before"] > 10
    assert g1["deviation_after"] <= 6 and g2["deviation_after"] <= 6 and g1["matched"] and g2["matched"]
    assert g2["wb_shift"] < 0 < g1["wb_shift"]          # the warm shot is redder than the reference, the gray one bluer
    assert g2["gains"][0] < 1.0 < g2["gains"][2]        # so it loses red and gains blue
    assert set(report["corrections"]) == {"SC01_g1_t1", "SC01_g2_t1"}
    assert report["summary"]["worst_after"] < report["summary"]["worst_before"]


@needs_ffmpeg
def test_a_named_reference_stays_untouched_and_a_skipped_shot_too(tmp_path):
    root, clips = make_film(tmp_path, {"SC01_g1": GRAY, "SC01_g2": WARM, "SC02_g1": GRAY, "SC02_g2": WARM})
    plan = C.ColorPlan(references={"SC01": "SC01_g1"}, skip=["SC02_g2"], max_gain=0.4)   # warm needs blue x1.33
    report = C.match(load_package(root), clips_dir=clips, plan=plan)
    rows = {r["generation_id"]: r for r in report["shots"]}
    assert rows["SC01_g1"]["reference"] == "SC01_g1" and "SC01_g1_t1" not in report["corrections"]   # gains of 1.0
    assert "SC01_g2_t1" in report["corrections"] and rows["SC01_g2"]["deviation_after"] <= 6
    assert rows["SC02_g2"]["gains"] is None and rows["SC02_g2"]["skipped"] == "plan" and "SC02_g2_t1" not in report["corrections"]


@needs_ffmpeg
def test_a_clamped_gain_warns_instead_of_flattening_a_deliberate_light_change(tmp_path):
    root, clips = make_film(tmp_path, {"SC01_g1": GRAY, "SC01_g2": RED})
    report = C.match(load_package(root), clips_dir=clips, plan=C.ColorPlan(references={"SC01": "SC01_g1"}))
    red = next(r for r in report["shots"] if r["generation_id"] == "SC01_g2")
    assert red["gains"] == [0.75, 1.25, 1.25] and not red["matched"]
    assert [(p["code"], p["severity"]) for p in report["problems"]] == [("OUT_OF_RANGE", "WARN")] and report["ok"]


@needs_ffmpeg
def test_a_single_shot_scene_and_missing_clips(tmp_path):
    root, clips = make_film(tmp_path, {"SC01_g1": GRAY})
    only = C.match(load_package(root), clips_dir=clips)
    assert only["shots"][0]["skipped"] == "single shot" and only["corrections"] == {}
    (clips / "SC01_g1.mp4").unlink()
    gone = C.match(load_package(root), clips_dir=clips)
    assert not gone["ok"] and gone["problems"][0]["code"] == "CLIP_MISSING"


@needs_ffmpeg
def test_takes_follow_the_edl(tmp_path):
    root, clips = make_film(tmp_path, {"SC01_g1": GRAY, "SC01_g2": WARM, "SC02_g1": GRAY})
    assert [t["take_id"] for t in C.used_takes(load_package(root))] == ["SC01_g1_t1", "SC01_g2_t1", "SC02_g1_t1"]
    write_edl(root, EditSection(events=[ev("a", "SC02_g1"), ev("b", "SC01_g1")]))
    assert [t["take_id"] for t in C.used_takes(load_package(root))] == ["SC02_g1_t1", "SC01_g1_t1"]


@needs_ffmpeg
def test_the_render_applies_the_gains_on_the_hard_and_the_fine_path(tmp_path):
    root, clips = make_film(tmp_path, {"SC01_g1": GRAY, "SC01_g2": WARM})
    pkg = load_package(root)
    report = C.match(pkg, clips_dir=clips)

    def spread(path, first_at, second_at):
        a, b = rgb_at(path, first_at), rgb_at(path, second_at)
        return max(abs(x - y) for x, y in zip(a, b))

    for name, edge in (("hard", None), ("fine", Transition(type="DIP_TO_BLACK", duration_s=0.5))):
        section = EditSection(events=[ev("a", "SC01_g1"), ev("b", "SC01_g2", **({"transition": edge} if edge else {}))])
        raw, matched = tmp_path / f"{name}_raw.mp4", tmp_path / f"{name}_matched.mp4"
        assert render_cut(pkg, section, raw, clips_dir=clips)["path"] == name
        assert render_cut(pkg, section, matched, clips_dir=clips, corrections=C.corrections_of(report))["path"] == name
        first, second = 3.0 + 1.0, 3.0 + 3.0 - (0.25 if edge else 0.0) + 1.5   # inside each shot, clear of the dip
        assert spread(raw, first, second) > 25, name
        assert spread(matched, first, second) < 10, name


@needs_ffmpeg
def test_the_look_can_be_replaced(tmp_path):
    root, clips = make_film(tmp_path, {"SC01_g1": GRAY})
    pkg = load_package(root)
    section = EditSection(events=[ev("a", "SC01_g1")])
    plain, dark = tmp_path / "plain.mp4", tmp_path / "dark.mp4"
    render_cut(pkg, section, plain, clips_dir=clips)
    render_cut(pkg, section, dark, clips_dir=clips, look="eq=brightness=-0.3")
    assert sum(rgb_at(dark, 4.0)) < sum(rgb_at(plain, 4.0)) - 60


@needs_ffmpeg
def test_cli_grade_and_cut_color(tmp_path):
    root, clips = make_film(tmp_path, {"SC01_g1": GRAY, "SC01_g2": WARM})
    write_edl(root, EditSection(events=[ev("a", "SC01_g1"), ev("b", "SC01_g2")]))

    def run(*args):
        return subprocess.run([sys.executable, str(TOOL), *args], capture_output=True, text=True, encoding="utf-8", cwd=ROOT)

    early = run("cut", "--film", str(root), "--render", "--color", "--clips", str(clips), "--out", str(tmp_path / "x.mp4"))
    assert early.returncode == 1 and "run film.py grade first" in json.loads(early.stdout)["error"]
    graded = run("grade", "--film", str(root), "--clips", str(clips), "--render", "--out", str(tmp_path / "g.mp4"))
    body = json.loads(graded.stdout)
    assert graded.returncode == 0 and body["ok"] and (tmp_path / "g.mp4").is_file() and body["render"]["path"] == "hard"
    assert (root / "color" / "color.json").is_file()
    post = json.loads((root / "06_post.json").read_text(encoding="utf-8"))
    assert post["color"]["ok"] and post["color"]["locked_against"] == "" and post["color"]["summary"]["corrected"] == 2
    again = run("cut", "--film", str(root), "--render", "--color", "--clips", str(clips), "--out", str(tmp_path / "c.mp4"))
    assert again.returncode == 0 and (tmp_path / "c.mp4").is_file()
