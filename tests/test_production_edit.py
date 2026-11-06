import json
import shutil
import subprocess
import sys
from pathlib import Path

import pytest
from pydantic import ValidationError

from film_pipeline.production import edit as E
from film_pipeline.production import takes as T
from film_pipeline.production.edit import (AudioCut, EditEvent, EditSection, TagEvent, Transition, edit_problems,
                                           render_cut, timeline)
from film_pipeline.production.impact import _stage_hits
from film_pipeline.production.package import load_package

ROOT = Path(__file__).resolve().parents[1]
FILM03 = ROOT / "films" / "film03_front_desk"
LEGACY = ROOT / "docs" / "drama" / "film03"
TOOL = ROOT / "tools" / "film.py"
FILES = ("film.json", "script.fountain", "01_story.json", "02_direction.json", "03_preprod.json", "04_shots.json")
FFMPEG = shutil.which("ffmpeg") and shutil.which("ffprobe")
needs_ffmpeg = pytest.mark.skipif(not FFMPEG, reason="ffmpeg/ffprobe not installed")


def clip(path: Path, seconds: float, freq: int = 440) -> Path:
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "lavfi", "-i", f"testsrc2=size=640x360:rate=24:duration={seconds}",
                    "-f", "lavfi", "-i", f"sine=frequency={freq}:duration={seconds}:sample_rate=48000",
                    "-c:v", "libx264", "-pix_fmt", "yuv420p", "-c:a", "aac", "-shortest", str(path)], check=True)
    return path


def make_film(tmp_path: Path, clips: dict[str, float]) -> tuple[Path, Path]:
    """A copy of film03's package plus registered synthetic takes `<gid>_t1` of the given lengths."""
    root = tmp_path / "film"
    root.mkdir()
    for name in FILES:
        shutil.copyfile(FILM03 / name, root / name)
    clips_dir = tmp_path / "clips"
    clips_dir.mkdir()
    for index, (gid, seconds) in enumerate(clips.items()):
        path = clip(clips_dir / f"{gid}.mp4", seconds, 300 + 110 * index)  # distinct bytes per take
        T.register_take(root, "film03_front_desk", gid, path, prompt_text=f"prompt {gid}", route="r", model="m", credits=12.0)
    return root, clips_dir


def take(event_id, gid, **kw):
    return EditEvent(event_id=event_id, take_id=f"{gid}_t1", **kw)


def card(event_id="C1", seconds=2.0, **kw):
    return EditEvent(event_id=event_id, kind="CARD", card_lines=["Later"], card_duration_s=seconds, **kw)


def codes(problems, severity=None):
    return {p["code"] for p in problems if severity is None or p["severity"] == severity}


# --------------------------------------------------------------- model

def test_first_event_cannot_have_a_transition_into_it():
    with pytest.raises(ValidationError, match="first event"):
        EditSection(events=[take("a", "SC01_g1", transition=Transition(type="DISSOLVE", duration_s=0.5))])


def test_transition_duration_matches_its_type():
    with pytest.raises(ValidationError, match="instantaneous"):
        Transition(type="CUT", duration_s=0.5)
    with pytest.raises(ValidationError, match="duration_s > 0"):
        Transition(type="DISSOLVE")
    assert Transition(type="MATCH_CUT").duration_s == 0


def test_event_ids_unique_and_take_shape():
    with pytest.raises(ValidationError, match="duplicate event_id"):
        EditSection(events=[take("a", "SC01_g1"), take("a", "SC01_g2")])
    with pytest.raises(ValidationError, match="needs take_id"):
        EditEvent(event_id="a")
    with pytest.raises(ValidationError, match="does not match"):
        EditEvent(event_id="a", take_id="SC01_g1_t1", generation_id="SC02_g1")
    with pytest.raises(ValidationError, match="after src_in_s"):
        take("a", "SC01_g1", src_in_s=2.0, src_out_s=1.0)
    with pytest.raises(ValidationError, match="CARD"):
        EditEvent(event_id="c", kind="CARD", take_id="SC01_g1_t1", card_lines=["x"], card_duration_s=1.0)
    with pytest.raises(ValidationError, match="card_lines"):
        EditEvent(event_id="c", kind="CARD")


def test_generation_id_is_derived_from_the_take():
    assert take("a", "SC03_g2").generation_id == "SC03_g2"


# --------------------------------------------------------------- timeline

def test_timeline_places_events_after_the_title_and_adds_the_end_card():
    sec = EditSection(events=[take("a", "SC01_g1"), card("c", 2.0), take("b", "SC01_g2", src_in_s=1.0, src_out_s=4.0)])
    tl = timeline(sec, {"SC01_g1_t1": 8.0, "SC01_g2_t1": 8.0})
    assert [(e["start_s"], e["end_s"]) for e in tl["events"]] == [(3.0, 11.0), (11.0, 13.0), (13.0, 16.0)]
    assert tl["body_end_s"] == 16.0 and tl["total_s"] == 20.0


def test_a_dissolve_overlaps_the_neighbours_but_audio_cuts_do_not_move_the_picture():
    plain = EditSection(events=[take("a", "SC01_g1"), take("b", "SC01_g2")])
    dissolved = EditSection(events=[take("a", "SC01_g1"),
                                    take("b", "SC01_g2", transition=Transition(type="DISSOLVE", duration_s=0.5))])
    jl = EditSection(events=[take("a", "SC01_g1"), take("b", "SC01_g2", audio=AudioCut(j_cut_s=0.4, l_cut_s=0.6))])
    dur = {"SC01_g1_t1": 8.0, "SC01_g2_t1": 8.0}
    assert timeline(plain, dur)["total_s"] == 23.0
    assert timeline(dissolved, dur)["total_s"] == 22.5
    assert timeline(dissolved, dur)["events"][1]["start_s"] == 10.5
    assert timeline(jl, dur) == timeline(plain, dur) | {"events": [
        {**e, "transition": "CUT"} for e in timeline(plain, dur)["events"]]}


# --------------------------------------------------------------- validation against the take log

@needs_ffmpeg
def test_a_clean_edl_has_no_blocking_problems(tmp_path):
    root, clips = make_film(tmp_path, {"SC01_g1": 2.0, "SC01_g2": 3.0})
    sec = EditSection(events=[take("a", "SC01_g1"), card(), take("b", "SC01_g2", src_in_s=0.5, src_out_s=2.5)],
                      tags=[TagEvent(event_id="b", character="NORA", label="NORA BELL", start_s=0.2, end_s=1.5,
                                     anchor_x=0.5, anchor_y=0.2)])
    problems, durations = edit_problems(load_package(root), sec, clips_dir=clips)
    assert codes(problems, "BLOCK") == set()
    assert codes(problems) == {"TAKE_NOT_ACCEPTED", "SHOT_NOT_IN_CUT"}
    assert set(durations) == {"SC01_g1_t1", "SC01_g2_t1"} and abs(durations["SC01_g2_t1"] - 3.0) < 0.1


@needs_ffmpeg
def test_unreviewed_takes_only_warn_until_acceptance_is_required(tmp_path):
    root, clips = make_film(tmp_path, {"SC01_g1": 2.0})
    sec = EditSection(events=[take("a", "SC01_g1")])
    pkg = load_package(root)
    assert "TAKE_NOT_ACCEPTED" in codes(edit_problems(pkg, sec, clips_dir=clips)[0], "WARN")
    assert "TAKE_NOT_ACCEPTED" in codes(edit_problems(pkg, sec, clips_dir=clips, require_accepted=True)[0], "BLOCK")


@needs_ffmpeg
def test_unknown_changed_missing_and_rejected_takes_block(tmp_path):
    root, clips = make_film(tmp_path, {"SC01_g1": 2.0, "SC01_g2": 2.0, "SC02_g1": 2.0})
    log = T.load_log(root, "film03_front_desk")
    log.takes[1] = log.takes[1].model_copy(update={"status": "REJECTED"})
    T.save_log(root, log)
    (clips / "SC02_g1.mp4").write_bytes((clips / "SC02_g1.mp4").read_bytes() + b"\0")
    (clips / "SC01_g1.mp4").unlink()
    sec = EditSection(events=[take("a", "SC01_g1"), take("b", "SC01_g2"), take("c", "SC02_g1"), take("d", "SC03_g1")])
    problems, _ = edit_problems(load_package(root), sec, clips_dir=clips)
    by_event = {p["event_id"]: p["code"] for p in problems if p["severity"] == "BLOCK"}
    assert by_event == {"a": "CLIP_MISSING", "b": "TAKE_REJECTED", "c": "CLIP_CHANGED", "d": "TAKE_UNKNOWN"}


@needs_ffmpeg
def test_a_take_of_a_superseded_shot_version_blocks(tmp_path):
    root, clips = make_film(tmp_path, {"SC01_g1": 2.0})
    log = T.load_log(root, "film03_front_desk")
    log.takes[0] = log.takes[0].model_copy(update={"shot_version": 0 + 2})  # rendered from v2; the shot is v1
    T.save_log(root, log)
    problems, _ = edit_problems(load_package(root), EditSection(events=[take("a", "SC01_g1")]), clips_dir=clips)
    assert "TAKE_SUPERSEDED" in codes(problems, "BLOCK")


@needs_ffmpeg
def test_trims_transitions_and_tags_must_fit_the_footage(tmp_path):
    root, clips = make_film(tmp_path, {"SC01_g1": 2.0, "SC01_g2": 2.0})
    sec = EditSection(
        events=[take("a", "SC01_g1", src_out_s=5.0),
                take("b", "SC01_g2", transition=Transition(type="DISSOLVE", duration_s=3.0), src_in_s=0.0, src_out_s=1.0),
                card("c")],
        tags=[TagEvent(event_id="c", character="X", label="X", start_s=0, end_s=1, anchor_x=.5, anchor_y=.5),
              TagEvent(event_id="b", character="Y", label="Y", start_s=0.5, end_s=2.0, anchor_x=.5, anchor_y=.5),
              TagEvent(event_id="zz", character="Z", label="Z", start_s=0, end_s=1, anchor_x=.5, anchor_y=.5)])
    problems, _ = edit_problems(load_package(root), sec, clips_dir=clips)
    blocks = {(p["code"], p["event_id"]) for p in problems if p["severity"] == "BLOCK"}
    assert blocks == {("TRIM_OUTSIDE_SOURCE", "a"), ("TAG_TARGET", "c"), ("TAG_TARGET", "zz"),
                      ("TAG_OUTSIDE_EVENT", "b"), ("TRANSITION_TOO_LONG", "b")}


@needs_ffmpeg
def test_audio_cut_on_the_first_event_and_reused_takes(tmp_path):
    root, clips = make_film(tmp_path, {"SC01_g1": 2.0})
    sec = EditSection(events=[take("a", "SC01_g1", audio=AudioCut(j_cut_s=0.3)), take("b", "SC01_g1")])
    problems, _ = edit_problems(load_package(root), sec, clips_dir=clips)
    assert {"AUDIO_CUT_ON_FIRST", "TAKE_REUSED"} <= codes(problems)


# --------------------------------------------------------------- render

@needs_ffmpeg
def test_render_matches_the_planned_timeline_within_a_frame_per_event(tmp_path):
    root, clips = make_film(tmp_path, {"SC01_g1": 2.0, "SC01_g2": 3.0})
    sec = EditSection(events=[take("a", "SC01_g1"), card("c", 1.5), take("b", "SC01_g2", src_in_s=0.5, src_out_s=2.5)],
                      tags=[TagEvent(event_id="b", character="NORA", label="NORA BELL", relation="the captain",
                                     start_s=0.2, end_s=1.5, anchor_x=0.5, anchor_y=0.2)])
    out = tmp_path / "out" / "cut.mp4"
    report = render_cut(load_package(root), sec, out, clips_dir=clips)
    planned = report["planned"]
    assert out.is_file() and Path(report["report"]).is_file()
    assert abs(report["total_s"] - planned["total_s"]) <= E.FRAME_S * len(sec.events)
    for got, want in zip(report["rendered_events"], planned["events"]):
        assert abs(got["start_s"] - want["start_s"]) <= E.FRAME_S * 2, got["event_id"]
    # the trim is real: the second take contributes 2 s, not its 3 s
    assert abs(report["rendered_events"][2]["duration_s"] - 2.0) <= E.FRAME_S * 2
    assert json.loads(Path(report["report"]).read_text(encoding="utf-8"))["output_sha256"] == report["output_sha256"]


@needs_ffmpeg
def test_render_refuses_blocked_edls_and_transitions_that_belong_to_p4_02(tmp_path):
    root, clips = make_film(tmp_path, {"SC01_g1": 2.0, "SC01_g2": 2.0})
    pkg = load_package(root)
    with pytest.raises(ValueError, match="TAKE_UNKNOWN"):
        render_cut(pkg, EditSection(events=[take("a", "SC09_g1")]), tmp_path / "x.mp4", clips_dir=clips)
    dissolve = EditSection(events=[take("a", "SC01_g1"),
                                   take("b", "SC01_g2", transition=Transition(type="DISSOLVE", duration_s=0.5))])
    with pytest.raises(NotImplementedError, match="P4-02"):
        render_cut(pkg, dissolve, tmp_path / "y.mp4", clips_dir=clips)
    assert not (tmp_path / "x.mp4").exists() and not (tmp_path / "y.mp4").exists()


# --------------------------------------------------------------- package, impact, CLI

def test_edit_stage_is_a_typed_section_and_impact_finds_events_by_generation(tmp_path):
    root = tmp_path / "film"
    root.mkdir()
    for name in FILES:
        shutil.copyfile(FILM03 / name, root / name)
    sec = EditSection(events=[take("a", "SC01_g1"), take("b", "SC01_g2")])
    (root / "05_edit.json").write_text(sec.model_dump_json(indent=2), encoding="utf-8")
    pkg = load_package(root)
    assert isinstance(pkg.typed["edit"], EditSection) and pkg.issues == []
    assert _stage_hits(pkg, "edit", {"SC01_g2"}) == ["edit:events[1]"]
    (root / "05_edit.json").write_text(json.dumps({"events": [{"event_id": "a"}]}), encoding="utf-8")
    assert any("05_edit.json" in i for i in load_package(root).issues)


@needs_ffmpeg
def test_cli_cut_checks_and_prints_the_timeline(tmp_path):
    root, clips = make_film(tmp_path, {"SC01_g1": 2.0})
    (root / "05_edit.json").write_text(EditSection(events=[take("a", "SC01_g1")]).model_dump_json(), encoding="utf-8")
    run = subprocess.run([sys.executable, str(TOOL), "cut", "--film", str(root), "--clips", str(clips)],
                         capture_output=True, text=True, cwd=ROOT)
    assert run.returncode == 0, run.stderr
    data = json.loads(run.stdout)
    assert data["ok"] and data["timeline"]["events"][0]["start_s"] == 3.0
    run = subprocess.run([sys.executable, str(TOOL), "cut", "--film", str(root), "--clips", str(clips), "--accepted-only"],
                         capture_output=True, text=True, cwd=ROOT)
    assert run.returncode == 1 and json.loads(run.stdout)["timeline"] is None


# --------------------------------------------------------------- golden: film03

def film03_edl() -> EditSection:
    """The event list that rebuilds the film03 final: same clip order, the two context cards, no trims."""
    post = json.loads((LEGACY / "post" / "film03_post.json").read_text(encoding="utf-8"))
    cards = {c["card_id"]: c for c in post["comprehension"]["cards"]}
    events = [card(c, cards[c]["duration_s"]).model_copy(update={"card_lines": cards[c]["lines"]}) if c in cards
              else take(c, c) for c in post["clips"]]
    return EditSection(events=events, title=[E.TextLine(text="THE FRONT DESK", size=96)],
                       end=[E.TextLine(text="THE FRONT DESK", size=64),
                            E.TextLine(text="A short drama. All characters are fictional.", size=30)])


def film03_package(tmp_path: Path):
    root = tmp_path / "film03"
    root.mkdir()
    for name in FILES:
        shutil.copyfile(FILM03 / name, root / name)
    for path in sorted((LEGACY / "takes").glob("*.mp4")):
        T.register_take(root, "film03_front_desk", path.stem, path,
                        prompt_text=(LEGACY / "prompts" / f"{path.stem}.txt").read_text(encoding="utf-8").strip(),
                        route="start_frame+Khung hinh", model="Omni Flash 360p", credits=12.0)
    return load_package(root)


@needs_ffmpeg
def test_film03_events_reproduce_the_legacy_timeline_within_a_frame_per_event(tmp_path):
    from film_pipeline.drama.post import context_card_clip, cue_offsets
    pkg = film03_package(tmp_path)
    sec = film03_edl()
    problems, durations = edit_problems(pkg, sec, clips_dir=LEGACY / "takes")
    assert codes(problems, "BLOCK") == set()
    tl = timeline(sec, durations)
    post = json.loads((LEGACY / "post" / "film03_post.json").read_text(encoding="utf-8"))
    clips = []
    for event in sec.events:  # the clip list the legacy post tool fed to cue_offsets
        clips.append(context_card_clip(tmp_path / f"{event.event_id}.mp4", event.card_lines, event.card_duration_s)
                     if event.kind == "CARD" else LEGACY / "takes" / f"{event.generation_id}.mp4")
    legacy = cue_offsets(clips, post["title_s"])
    assert len(tl["events"]) == len(post["clips"]) == 18
    for placed, clip_path in zip(tl["events"], clips):
        assert abs(placed["start_s"] - legacy[clip_path.stem]) <= E.FRAME_S, placed["event_id"]
    assert abs(tl["total_s"] - post["duration_s"]) <= E.FRAME_S * len(sec.events)


@needs_ffmpeg
def test_film03_rendered_cut_has_the_legacy_final_duration(tmp_path):
    pkg = film03_package(tmp_path)
    report = render_cut(pkg, film03_edl(), tmp_path / "cut.mp4", clips_dir=LEGACY / "takes")
    post = json.loads((LEGACY / "post" / "film03_post.json").read_text(encoding="utf-8"))
    assert abs(report["total_s"] - post["duration_s"]) <= E.FRAME_S * 18
    assert [e["event_id"] for e in report["rendered_events"]] == post["clips"]
