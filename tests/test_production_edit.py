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
def test_render_refuses_blocked_edls_before_writing_anything(tmp_path):
    root, clips = make_film(tmp_path, {"SC01_g1": 2.0, "SC01_g2": 2.0})
    pkg = load_package(root)
    with pytest.raises(ValueError, match="TAKE_UNKNOWN"):
        render_cut(pkg, EditSection(events=[take("a", "SC09_g1")]), tmp_path / "x.mp4", clips_dir=clips)
    assert not (tmp_path / "x.mp4").exists()


# --------------------------------------------------------------- fine cut: dissolve, J/L cut

def solid(path: Path, colour: str, seconds: float, freq: int) -> Path:
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "lavfi", "-i", f"color=c={colour}:s=640x360:r=24:d={seconds}",
                    "-f", "lavfi", "-i", f"sine=frequency={freq}:duration={seconds}:sample_rate=48000",
                    "-c:v", "libx264", "-pix_fmt", "yuv420p", "-c:a", "aac", "-shortest", str(path)], check=True)
    return path


def make_solid_film(tmp_path: Path, spec: dict[str, tuple[str, float, int]]) -> tuple[Path, Path]:
    root = tmp_path / "film"
    root.mkdir()
    for name in FILES:
        shutil.copyfile(FILM03 / name, root / name)
    clips_dir = tmp_path / "clips"
    clips_dir.mkdir()
    for gid, (colour, seconds, freq) in spec.items():
        T.register_take(root, "film03_front_desk", gid, solid(clips_dir / f"{gid}.mp4", colour, seconds, freq),
                        prompt_text=f"prompt {gid}", route="r", model="m", credits=12.0)
    return root, clips_dir


def frame_rgb(video: Path, at_s: float) -> tuple[int, int, int]:
    from PIL import Image
    png = video.with_suffix(f".{int(at_s * 1000)}.png")
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-ss", f"{at_s:.3f}", "-i", str(video), "-frames:v", "1",
                    "-vf", "crop=40:40:300:150", str(png)], check=True)
    return list(Image.open(png).convert("RGB").resize((1, 1)).getdata())[0]


def tone(video: Path, t0: float, t1: float, freq: int) -> float:
    """Amplitude of ``freq`` in [t0, t1] of the audio track (single-bin DFT)."""
    import numpy as np
    raw = subprocess.run(["ffmpeg", "-v", "error", "-ss", f"{t0:.3f}", "-t", f"{t1 - t0:.3f}", "-i", str(video), "-vn",
                          "-ac", "1", "-ar", "48000", "-f", "s16le", "-"], capture_output=True, check=True).stdout
    x = np.frombuffer(raw, dtype="<i2").astype(float) / 32768.0
    t = np.arange(len(x)) / 48000.0
    return float(abs((x * np.exp(-2j * np.pi * freq * t)).sum()) * 2 / len(x))


@needs_ffmpeg
def test_dissolve_overlaps_the_pictures_and_blends_the_middle(tmp_path):
    root, clips = make_solid_film(tmp_path, {"SC01_g1": ("red", 3.0, 440), "SC01_g2": ("blue", 3.0, 880)})
    sec = EditSection(events=[take("a", "SC01_g1"),
                              take("b", "SC01_g2", transition=Transition(type="DISSOLVE", duration_s=1.0))])
    out = tmp_path / "dissolve.mp4"
    report = render_cut(load_package(root), sec, out, clips_dir=clips)
    assert report["path"] == "fine" and report["planned"]["total_s"] == 3.0 + 5.0 + 4.0
    assert abs(report["total_s"] - 12.0) <= E.FRAME_S * 2
    r0, _, b0 = frame_rgb(out, 3.5)   # inside the first take only
    r1, _, b1 = frame_rgb(out, 5.5)   # mid-dissolve (overlap is 5.0-6.0 on the final clock)
    r2, _, b2 = frame_rgb(out, 7.5)   # second take only
    assert r0 > 120 > b0 and b2 > 120 > r2
    assert r1 > 40 and b1 > 40, (r1, b1)  # both pictures are present in the middle


@needs_ffmpeg
def test_j_cut_brings_the_next_sound_in_early_and_l_cut_keeps_the_last_one(tmp_path):
    root, clips = make_solid_film(tmp_path, {"SC01_g1": ("red", 4.0, 440), "SC01_g2": ("blue", 4.0, 880)})
    pkg = load_package(root)

    def rendered(name, **audio):
        sec = EditSection(events=[take("a", "SC01_g1", src_out_s=3.0),
                                  take("b", "SC01_g2", src_in_s=1.0, audio=AudioCut(**audio))])
        return render_cut(pkg, sec, tmp_path / name, clips_dir=clips)

    plain, jl = tmp_path / "plain.mp4", tmp_path / "jl.mp4"
    assert rendered("plain.mp4")["path"] == "hard"
    report = rendered("jl.mp4", j_cut_s=0.6, l_cut_s=0.6)
    assert report["path"] == "fine"
    cut = 3.0 + 3.0  # title + first event
    before = (cut - 0.45, cut - 0.15)   # picture still on event a
    after = (cut + 0.15, cut + 0.45)    # picture already on event b
    assert tone(plain, *before, 880) < 0.005 and tone(jl, *before, 880) > 0.03   # J: b's sound is already here
    assert tone(plain, *after, 440) < 0.005 and tone(jl, *after, 440) > 0.03    # L: a's sound is still here
    assert abs(report["total_s"] - report["planned"]["total_s"]) <= E.FRAME_S * 2  # sound never moves the picture


@needs_ffmpeg
def test_audio_cuts_need_source_handles(tmp_path):
    root, clips = make_film(tmp_path, {"SC01_g1": 3.0, "SC01_g2": 3.0})
    pkg = load_package(root)
    j_without_handle = EditSection(events=[take("a", "SC01_g1"), take("b", "SC01_g2", audio=AudioCut(j_cut_s=0.5))])
    l_without_handle = EditSection(events=[take("a", "SC01_g1"), take("b", "SC01_g2", audio=AudioCut(l_cut_s=0.5))])
    j_on_card = EditSection(events=[take("a", "SC01_g1"), card("c", audio=AudioCut(j_cut_s=0.5))])
    assert "JCUT_NO_HANDLE" in codes(edit_problems(pkg, j_without_handle, clips_dir=clips)[0], "BLOCK")
    assert "LCUT_NO_HANDLE" in codes(edit_problems(pkg, l_without_handle, clips_dir=clips)[0], "BLOCK")
    assert "JCUT_NO_HANDLE" in codes(edit_problems(pkg, j_on_card, clips_dir=clips)[0], "BLOCK")
    ok = EditSection(events=[take("a", "SC01_g1", src_out_s=2.0),
                             take("b", "SC01_g2", src_in_s=0.5, audio=AudioCut(j_cut_s=0.5, l_cut_s=0.5))])
    assert codes(edit_problems(pkg, ok, clips_dir=clips)[0], "BLOCK") == set()


# --------------------------------------------------------------- rhythm and continuity across cuts

def film03():
    return load_package(FILM03)


def test_rhythm_flags_slow_fast_unplanned_and_over_plan_holds():
    sec = EditSection(events=[take("a", "SC01_g1"), take("b", "SC01_g2"), take("c", "SC02_g2"), take("d", "SC03_g1"),
                              take("e", "SC03_g2")])
    durations = {"SC01_g1_t1": 13.0, "SC01_g2_t1": 11.0,   # SC01: avg 12 (slow), g1 unplanned long, g2 hold 2s -> max 10
                 "SC02_g2_t1": 3.0,                         # SC02: avg 3 (fast); its planned hold on SC02_g1 is not in the cut
                 "SC03_g1_t1": 9.5, "SC03_g2_t1": 8.0}      # SC03_g1 hold 2s allows 10s: fine
    report = E.rhythm_report(film03(), sec, durations)
    seen = {(i["code"], i["scene_id"]) for i in report["issues"]}
    assert seen == {("SCENE_PACE_SLOW", "SC01"), ("LONG_SHOT_UNPLANNED", "SC01"), ("HOLD_OVER_PLAN", "SC01"),
                    ("SCENE_PACE_FAST", "SC02"), ("HOLD_NOT_IN_CUT", "SC02")}
    assert all(i["severity"] == "WARN" for i in report["issues"])
    sc01 = next(r for r in report["scenes"] if r["scene_id"] == "SC01")
    assert sc01["avg_s"] == 12.0 and sc01["ratio"] == 1.5


def test_rhythm_on_the_planned_lengths_is_quiet():
    gens = ["SC01_g1", "SC01_g2", "SC02_g1", "SC02_g2"]
    sec = EditSection(events=[take(g, g) for g in gens])
    assert E.rhythm_report(film03(), sec, {f"{g}_t1": 8.0 for g in gens})["issues"] == []


def test_rhythm_without_a_direction_plan_says_so():
    pkg = film03()
    bare = type("P", (), {"typed": {k: v for k, v in pkg.typed.items() if k != "direction"}})()
    assert E.rhythm_report(bare, EditSection(events=[take("a", "SC01_g1")]), {})["skipped"]


def test_cut_continuity_accepts_a_chained_cut_at_the_clip_ends():
    sec = EditSection(events=[take("a", "SC01_g1"), take("b", "SC01_g2")])
    report = E.cut_continuity(film03(), sec, {"SC01_g1_t1": 8.0, "SC01_g2_t1": 8.0})
    assert report["cuts"] == 1 and report["issues"] == []


def test_cut_continuity_cannot_prove_the_state_at_a_trimmed_chained_cut():
    sec = EditSection(events=[take("a", "SC01_g1", src_out_s=5.0), take("b", "SC01_g2")])
    issues = E.cut_continuity(film03(), sec, {"SC01_g1_t1": 8.0, "SC01_g2_t1": 8.0})["issues"]
    assert [(i["code"], i["severity"]) for i in issues] == [("TRIMMED_HANDOFF", "WARN")]


def test_cut_continuity_reports_prop_changes_between_scenes_and_skips_cards():
    sec = EditSection(events=[take("a", "SC06_g2"), take("b", "SC07_g1")])
    issues = E.cut_continuity(film03(), sec, {"SC06_g2_t1": 8.0, "SC07_g1_t1": 8.0})["issues"]
    assert {i["code"] for i in issues} == {"OBJECT_HANDOFF"} and all(i["severity"] == "WARN" for i in issues)
    with_card = EditSection(events=[take("a", "SC06_g2"), card("c"), take("b", "SC07_g1")])
    assert E.cut_continuity(film03(), with_card, {"SC06_g2_t1": 8.0, "SC07_g1_t1": 8.0}) == {"cuts": 0, "issues": []}


def edited(pkg, **changes):
    """film03 with generations replaced: {gid: {field: value}} (camera fields via 'camera': {...})."""
    shots = pkg.typed["shots"]
    gens = []
    for g in shots.generations:
        upd = dict(changes.get(g.generation_id, {}))
        if "camera" in upd:
            upd["camera"] = g.camera.model_copy(update=upd["camera"])
        gens.append(g.model_copy(update=upd))
    return type("P", (), {"typed": {**pkg.typed, "shots": shots.model_copy(update={"generations": gens})}})()


def test_cut_continuity_flags_a_line_crossing_with_flipped_eyelines_and_jump_cuts():
    pkg = edited(film03(), SC02_g2={"camera": {"side": "REVERSE", "crossing_note": "over the desk"}})
    sec = EditSection(events=[take("a", "SC02_g1"), take("b", "SC02_g2")])
    got = {i["code"]: i for i in E.cut_continuity(pkg, sec, {"SC02_g1_t1": 8.0, "SC02_g2_t1": 8.0})["issues"]}
    assert "AXIS_SIDE_CHANGE" in got and "crosses the line" in got["AXIS_SIDE_CHANGE"]["detail"]

    jump = edited(film03(), SC02_g2={"subject": "KESSLER", "previous_generation_id": None,
                                     "camera": {"size": "MEDIUM_CLOSE"}})
    issues = E.cut_continuity(jump, sec, {"SC02_g1_t1": 8.0, "SC02_g2_t1": 8.0})["issues"]
    assert [i["code"] for i in issues] == ["JUMP_CUT_RISK"]


def test_a_broken_chained_handoff_inside_a_scene_blocks():
    pkg = film03()
    pre = pkg.typed["preprod"]
    base = edited(pkg, SC02_g2={"start_state": "BENT"})
    start = pre.states["SC02_g2"]
    bent = start.model_copy(update={"props": {**start.props, "the desk phone:": "on the floor"}})
    patched = type("P", (), {"typed": {**base.typed, "preprod": pre.model_copy(update={"states": {**pre.states, "BENT": bent}})}})()
    issues = E.cut_continuity(patched, EditSection(events=[take("a", "SC02_g1"), take("b", "SC02_g2")]),
                              {"SC02_g1_t1": 8.0, "SC02_g2_t1": 8.0})["issues"]
    assert [(i["code"], i["severity"]) for i in issues] == [("OBJECT_HANDOFF", "BLOCK")]


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
    assert "issues" in data["rhythm"] and data["continuity"]["cuts"] == 0
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
