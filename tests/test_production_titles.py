import json
import re
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

from film_pipeline.production import sound_rights as S
from film_pipeline.production import takes as T
from film_pipeline.production import titles as TI
from film_pipeline.production.edit import EditEvent, EditSection, Reframe, TagEvent, Transition, reframe_filter, render_cut
from film_pipeline.production.package import load_package

ROOT = Path(__file__).resolve().parents[1]
FILM03 = ROOT / "films" / "film03_front_desk"
TOOL = ROOT / "tools" / "film.py"
FILES = ("film.json", "script.fountain", "01_story.json", "02_direction.json", "03_preprod.json", "04_shots.json")
needs_ffmpeg = pytest.mark.skipif(not (shutil.which("ffmpeg") and shutil.which("ffprobe")), reason="ffmpeg not installed")
LINE1 = "Complaints window opens at nine."          # SC01_g1, KESSLER


def clip(path: Path, speech=(2.0, 4.0), seconds=5.0, split=False, seed="") -> Path:
    """Blue frame (left half red when ``split``) and a 300 Hz tone for ``speech``, silence elsewhere."""
    video = f"color=c=blue:size=320x180:rate=24:duration={seconds}"
    if split:
        video += ",drawbox=x=0:y=0:w=160:h=180:color=red:t=fill"
    audio = ("anullsrc=r=48000:cl=mono" if speech is None else
             f"sine=frequency=300:sample_rate=48000:duration={speech[1] - speech[0]}")
    af = ["-af", f"adelay={int(speech[0] * 1000)},apad=whole_dur={seconds}"] if speech else []
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "lavfi", "-i", video, "-f", "lavfi", "-i", audio, *af, "-t", str(seconds),
                    "-metadata", f"comment={seed or path.stem}", "-c:v", "libx264", "-pix_fmt", "yuv420p", "-c:a", "aac", str(path)], check=True)
    return path


def make_film(tmp_path: Path, takes: dict[str, dict]):
    root = tmp_path / "film"
    root.mkdir()
    for name in FILES:
        shutil.copyfile(FILM03 / name, root / name)
    clips = tmp_path / "clips"
    clips.mkdir()
    for gid, kw in takes.items():
        T.register_take(root, "film03_front_desk", gid, clip(clips / f"{gid}.mp4", **kw), prompt_text=f"prompt {gid}",
                        route="r", model="m", credits=12.0)
    return root, clips


def write_edl(root: Path, section: EditSection) -> None:
    (root / "05_edit.json").write_text(section.model_dump_json(indent=2), encoding="utf-8")


def ev(event_id, gid, **kw):
    return EditEvent(event_id=event_id, take_id=f"{gid}_t1", **kw)


def srt_blocks(path: Path):
    out = []
    for block in path.read_text(encoding="utf-8").strip().split("\n\n"):
        _, times, *text = block.split("\n")
        a, b = (sum(float(x) * k for x, k in zip(re.split(r"[:,]", t.replace(",", ".", 1)) if False else
                                                  t.replace(",", ":").split(":"), (3600, 60, 1, 0.001))) for t in times.split(" --> "))
        out.append((a, b, "\n".join(text)))
    return out


def codes(report, severity=None):
    return sorted(p["code"] for p in report["problems"] if severity in (None, p["severity"]))


# ------------------------------------------------------------------ credits

def test_credits_come_from_the_package():
    lines, problems = TI.credits_lines(load_package(FILM03), "en")
    texts = [t for t, _ in lines]
    assert not problems and texts[0] == "The Front Desk"
    assert "Characters: NORA · KESSLER · ORTIZ" in texts
    assert "Video, images and voices generated with AI." in texts and texts[-1].startswith("A work of fiction")
    assert not any("Music and sound" in t for t in texts)
    vi = [t for t, _ in TI.credits_lines(load_package(FILM03), "vi", generators="Google Flow Omni 1.1 Flash")[0]]
    assert "Nhân vật: NORA · KESSLER · ORTIZ" in vi and "Tạo bằng AI: Google Flow Omni 1.1 Flash" in vi


def test_rights_credits_are_on_the_card(tmp_path):
    root, _ = make_film(tmp_path, {})
    (root / "audio" / "music").mkdir(parents=True)
    (root / "audio" / "music" / "theme.wav").write_bytes(b"x")
    from film_pipeline.production import mix as M
    (root / "audio" / "mix_plan.json").write_text(M.MixPlan(music=[M.MusicCue(
        cue_id="M1", asset="music/theme.wav", start_s=1.0, end_s=5.0, why="w")]).model_dump_json(), encoding="utf-8")
    pkg = load_package(root)
    S.record_asset(pkg, "audio/music/theme.wav", "music", "CC-BY-4.0", source_url="https://example.org/t", status="cleared",
                   attribution="Theme by A. Composer, CC BY 4.0", usage=[S.UsageRange(start_s=0.0, end_s=20.0)])
    texts = [t for t, _ in TI.credits_lines(pkg, "en")[0]]
    assert "Music and sound" in texts and "Theme by A. Composer, CC BY 4.0" in texts
    assert texts.index("Music and sound") < texts.index("Theme by A. Composer, CC BY 4.0") < len(texts) - 1


def test_long_lines_shrink_and_too_many_lines_block():
    lines, problems = TI.fit_lines([("T", 64), ("x" * 90, 30)])
    assert not problems and lines[1][1] < 30 and TI._text_width(*lines[1]) <= TI.MAX_CARD_WIDTH
    lines, problems = TI.fit_lines([("T", 64)] + [(f"credit line {i}", 30) for i in range(40)])
    assert [p["code"] for p in problems] == ["CREDITS_OVERFLOW"] and problems[0]["severity"] == "BLOCK"
    lines, problems = TI.fit_lines([("T", 64)] + [(f"credit line {i}", 30) for i in range(12)])
    assert not problems and all(s >= TI.MIN_FONT for _, s in lines) and lines[0][1] == 64


# ------------------------------------------------------------------ timing

def test_windows_are_matched_to_lines():
    assert TI.allocate([(1.0, 2.0), (3.0, 4.0)], [3, 3]) == [(1.0, 2.0), (3.0, 4.0)]
    assert TI.allocate([(1.0, 2.0), (2.2, 3.0), (6.0, 7.0)], [3, 3]) == [(1.0, 3.0), (6.0, 7.0)]      # smallest gap merged
    shared = TI.allocate([(1.0, 5.0)], [1, 3])
    assert shared == [(1.0, 2.0), (2.0, 5.0)]
    split = TI.allocate([(0.0, 1.0), (3.0, 4.0)], [1, 1, 2])                                          # 4 words over 2 s of speech
    assert split[0] == (0.0, 0.5) and split[1] == (0.5, 1.0) or split[1][0] >= 0.5
    assert split[2][1] == 4.0 and TI.allocate([], [2]) == [] and TI.allocate([(0.0, 1.0)], []) == []


@needs_ffmpeg
def test_speech_windows_find_the_tone(tmp_path):
    path = clip(tmp_path / "s.mp4", speech=(2.0, 3.5))
    (a, b), = TI.speech_windows(path, 0.0, 5.0)
    assert abs(a - 2.0) < 0.15 and abs(b - 3.5) < 0.15
    assert TI.speech_windows(clip(tmp_path / "q.mp4", speech=None), 0.0, 5.0) == []
    (a, b), = TI.speech_windows(path, 1.0, 3.0)                      # the used part starts 1 s into the clip
    assert abs(a - 1.0) < 0.15 and abs(b - 2.5) < 0.15


@needs_ffmpeg
def test_cues_follow_the_speech_of_the_used_part(tmp_path):
    root, clips = make_film(tmp_path, {"SC01_g1": {}, "SC01_g2": {"speech": None}})
    write_edl(root, EditSection(events=[ev("a", "SC01_g1", src_in_s=1.0), ev("b", "SC01_g2")]))
    pkg = load_package(root)
    prepared = TI.prepare(pkg, clips_dir=clips)
    first, second = prepared["rows"]
    assert first["text"] == LINE1 and first["source"] == "windows" and abs(first["start_s"] - 1.0) < 0.15
    assert abs(first["end_s"] - 3.0) < 0.15 and prepared["cues"][0].generation_id == "a"
    assert second["source"] == "even" and (second["start_s"], second["end_s"]) == (0.0, 5.0)
    assert codes(prepared) == ["DIALOGUE_NO_SPEECH"] and prepared["ok"]


@needs_ffmpeg
def test_an_explicit_timing_wins_and_a_bad_one_blocks(tmp_path):
    root, clips = make_film(tmp_path, {"SC01_g1": {}})
    write_edl(root, EditSection(events=[ev("a", "SC01_g1")]))
    (root / "titles").mkdir()
    (root / "titles" / "cues.json").write_text(json.dumps({"cues": [{"event_id": "a", "line_no": 14, "start_s": 0.5, "end_s": 2.0}]}))
    row, = TI.prepare(load_package(root), clips_dir=clips)["rows"]
    assert (row["start_s"], row["end_s"], row["source"]) == (0.5, 2.0, "override")
    (root / "titles" / "cues.json").write_text(json.dumps({"cues": [{"event_id": "a", "line_no": 14, "start_s": 9.0, "end_s": 10.0}]}))
    assert codes(TI.prepare(load_package(root), clips_dir=clips), "BLOCK") == ["CUE_OUTSIDE_EVENT"]


@needs_ffmpeg
def test_unreadable_cues_warn(tmp_path):
    root, clips = make_film(tmp_path, {"SC01_g1": {}})
    write_edl(root, EditSection(events=[ev("a", "SC01_g1")]))
    (root / "titles").mkdir()
    (root / "titles" / "cues.json").write_text(json.dumps({"cues": [{"event_id": "a", "line_no": 14, "start_s": 1.0, "end_s": 1.3}]}))
    assert codes(TI.prepare(load_package(root), clips_dir=clips)) == ["CUE_TOO_FAST", "CUE_TOO_SHORT"]


# ------------------------------------------------------------------ sidecars

@needs_ffmpeg
def test_sidecars_in_both_languages(tmp_path):
    root, clips = make_film(tmp_path, {"SC01_g1": {}, "SC01_g2": {"speech": (1.0, 2.5)}})
    tag = TagEvent(event_id="a", character="KESSLER", label="Sgt. Kessler", start_s=0.2, end_s=1.5, anchor_x=0.5, anchor_y=0.12)
    write_edl(root, EditSection(events=[ev("a", "SC01_g1"), EditEvent(event_id="c", kind="CARD", card_lines=["The new captain arrives early"],
                                                                      card_duration_s=2.0), ev("b", "SC01_g2")], tags=[tag]))
    pkg = load_package(root)
    report = TI.write_outputs(pkg, TI.prepare(pkg, clips_dir=clips, generators="Google Flow Omni 1.1 Flash"))
    assert report["ok"] and sorted(report["sidecars"]) == ["en", "vi"] and report["summary"]["cues"] == 2
    en, vi = (srt_blocks(Path(report["sidecars"][l])) for l in ("en", "vi"))
    translations = pkg.typed["direction"].translations
    assert [t for _, _, t in en if t == LINE1] and [t for _, _, t in vi if t == translations[LINE1]]
    assert en[0][:2] == (0.0, 3.0) and en[0][2] == "The Front Desk" and vi[0][2] == translations["THE FRONT DESK"]
    dialogue = next(a for a, _, t in en if t == LINE1)
    assert abs(dialogue - (3.0 + 2.0)) < 0.2                              # the title card, then 2 s into event a
    card = next((a, b) for a, b, t in en if t == "The new captain arrives early")
    assert card == (8.0, 10.0)                                            # after the 5 s event a
    assert any(t.startswith("Sgt. Kessler") for _, _, t in en)
    assert any("Generated with AI: Google Flow Omni 1.1 Flash" in t for _, _, t in en)
    assert any("Tạo bằng AI: Google Flow Omni 1.1 Flash" in t for _, _, t in vi)
    assert (root / "titles" / "credits.json").is_file() and (root / "titles" / "titles.json").is_file()


@needs_ffmpeg
def test_a_missing_translation_blocks_that_language_only(tmp_path):
    root, clips = make_film(tmp_path, {"SC01_g1": {}})
    write_edl(root, EditSection(events=[ev("a", "SC01_g1"),
                                        EditEvent(event_id="c", kind="CARD", card_lines=["Nobody translated this"], card_duration_s=2.0)]))
    pkg = load_package(root)
    report = TI.write_outputs(pkg, TI.prepare(pkg, clips_dir=clips))
    assert not report["ok"] and codes(report, "BLOCK") == ["TRANSLATION_MISSING"] and list(report["sidecars"]) == ["en"]
    assert not (root / "titles" / "film03_front_desk.vi.srt").exists()
    only_en = TI.prepare(pkg, clips_dir=clips, langs=("en",))
    assert only_en["ok"]
    assert codes(TI.prepare(pkg, clips_dir=clips, langs=("de",)), "BLOCK") == ["LANGUAGE_UNSUPPORTED"]


# ------------------------------------------------------------------ reframe

def test_reframe_filter_and_rules():
    assert reframe_filter(None) == "" and reframe_filter(Reframe()) == "" and reframe_filter(Reframe(stabilize=True)) == "deshake"
    assert reframe_filter(Reframe(x=0.25, y=0.25, w=0.5, h=0.5)).startswith("crop=trunc(iw*0.500000/2)*2:trunc(ih*0.500000/2)*2:")
    with pytest.raises(ValueError, match="leaves the frame"):
        Reframe(x=0.6, w=0.5, h=0.5)
    section = EditSection(events=[ev("a", "SC01_g1"), EditEvent(event_id="c", kind="CARD", card_lines=["x"], card_duration_s=1.0)],
                          tags=[TagEvent(event_id="a", character="N", label="N", start_s=0.0, end_s=1.0, anchor_x=0.5, anchor_y=0.1)])
    plan = TI.ReframePlan(events={"a": Reframe(w=0.4, h=0.4), "c": Reframe(w=0.8, h=0.8), "zz": Reframe(w=0.9, h=0.8),
                                  })
    found = {(p["event_id"], p["code"], p["severity"]) for p in TI.reframe_problems(section, plan)}
    assert found == {("a", "REFRAME_SOFT", "WARN"), ("a", "REFRAME_TAG", "WARN"), ("c", "REFRAME_EVENT_UNKNOWN", "BLOCK"),
                     ("zz", "REFRAME_EVENT_UNKNOWN", "BLOCK")}
    wide = TI.ReframePlan(events={"a": Reframe(w=0.9, h=0.6)})
    assert "REFRAME_ASPECT" in [p["code"] for p in TI.reframe_problems(section, wide)]


def rgb_of(video: Path, at_s: float, x: int, y: int) -> tuple[int, int, int]:
    raw = subprocess.run(["ffmpeg", "-v", "error", "-ss", f"{at_s:.3f}", "-i", str(video), "-frames:v", "1", "-vf",
                          f"crop=40:40:{x}:{y},scale=1:1", "-f", "rawvideo", "-pix_fmt", "rgb24", "-"],
                         capture_output=True, check=True).stdout
    return raw[0], raw[1], raw[2]


@needs_ffmpeg
def test_a_reframe_changes_the_picture_on_both_render_paths(tmp_path):
    root, clips = make_film(tmp_path, {"SC01_g1": {"split": True}, "SC01_g2": {"split": True}})
    pkg = load_package(root)
    box = {"a": Reframe(x=0.0, y=0.0, w=0.5, h=0.5)}                       # the red top-left quarter
    for name, edge in (("hard", None), ("fine", Transition(type="DIP_TO_BLACK", duration_s=0.5))):
        section = EditSection(events=[ev("a", "SC01_g1"), ev("b", "SC01_g2", **({"transition": edge} if edge else {}))])
        plain, framed = tmp_path / f"{name}_p.mp4", tmp_path / f"{name}_f.mp4"
        render_cut(pkg, section, plain, clips_dir=clips)
        assert render_cut(pkg, section, framed, clips_dir=clips, reframes=box)["path"] == name
        r, g, b = rgb_of(plain, 3.0 + 1.0, 900, 340)                       # right half of the first event
        assert b > 200 and r < 60, name
        r, g, b = rgb_of(framed, 3.0 + 1.0, 900, 340)
        assert r > 200 and b < 60, name
        r, g, b = rgb_of(framed, 3.0 + 5.0 - (0.25 if edge else 0.0) + 1.5, 900, 340)   # event b is not reframed
        assert b > 200 and r < 60, name


@needs_ffmpeg
def test_stabilize_renders_and_keeps_the_length(tmp_path):
    root, clips = make_film(tmp_path, {"SC01_g1": {}})
    pkg = load_package(root)
    section = EditSection(events=[ev("a", "SC01_g1")])
    plain, still = tmp_path / "p.mp4", tmp_path / "s.mp4"
    a = render_cut(pkg, section, plain, clips_dir=clips)["total_s"]
    b = render_cut(pkg, section, still, clips_dir=clips, reframes={"a": Reframe(stabilize=True)})["total_s"]
    assert abs(a - b) < 0.1


@needs_ffmpeg
def test_cards_can_be_replaced(tmp_path):
    root, clips = make_film(tmp_path, {"SC01_g1": {}})
    section = EditSection(events=[ev("a", "SC01_g1")])
    out = tmp_path / "c.mp4"
    done = render_cut(load_package(root), section, out, clips_dir=clips, title_lines=[("MY TITLE", 80)],
                      end_lines=[("MY TITLE", 64), ("Characters: A", 30)])
    assert done["total_s"] == pytest.approx(3.0 + 5.0 + 4.0, abs=0.2)
    assert max(rgb_of(out, 1.0, 540, 320)) > 20                            # title text on the black card


# ------------------------------------------------------------------ CLI

@needs_ffmpeg
def test_cli_titles_writes_everything_and_renders(tmp_path):
    root, clips = make_film(tmp_path, {"SC01_g1": {}, "SC01_g2": {"speech": (1.0, 2.5)}})
    write_edl(root, EditSection(events=[ev("a", "SC01_g1"), ev("b", "SC01_g2")]))
    (root / "titles").mkdir()
    (root / "titles" / "reframe.json").write_text(json.dumps({"events": {"a": {"x": 0.1, "y": 0.1, "w": 0.8, "h": 0.8}}}))

    def run(*args):
        return subprocess.run([sys.executable, str(TOOL), "titles", "--film", str(root), "--clips", str(clips), *args],
                              capture_output=True, text=True, encoding="utf-8", cwd=ROOT)

    done = run("--generators", "Google Flow Omni 1.1 Flash", "--render", "--out", str(tmp_path / "t.mp4"))
    body = json.loads(done.stdout)
    assert done.returncode == 0 and body["ok"] and body["reframed"] == ["a"] and (tmp_path / "t.mp4").is_file()
    assert body["render"]["path"] == "hard" and body["summary"]["languages"] == ["en", "vi"]
    post = json.loads((root / "06_post.json").read_text(encoding="utf-8"))
    assert post["titles"]["ok"] and post["titles"]["locked_against"] == "" and post["titles"]["summary"]["cues"] == 2
    credits = json.loads((root / "titles" / "credits.json").read_text(encoding="utf-8"))
    assert credits["en"][0]["text"] == "The Front Desk" and any("Google Flow Omni" in l["text"] for l in credits["en"])
    (root / "titles" / "reframe.json").write_text(json.dumps({"events": {"nope": {"w": 0.5, "h": 0.5}}}))
    bad = run("--render", "--out", str(tmp_path / "u.mp4"))
    assert bad.returncode == 1 and not (tmp_path / "u.mp4").exists() and "REFRAME_EVENT_UNKNOWN" in bad.stdout
