from __future__ import annotations

import io
import json
import math
import shutil
import struct
import subprocess
import sys
import wave
from pathlib import Path
from types import SimpleNamespace

import pytest
from PIL import Image

from film_pipeline import cli as cli_mod
from film_pipeline.agentic import PreSendCritic, WaveDAGScheduler
from film_pipeline.drama import post as drama_post
from film_pipeline.production import (
    color as color_mod,
    dailies_triage as dt_mod,
    deliver as dl_mod,
    dialogue_stt as stt_mod,
    mix as mix_mod,
    planning as planning_mod,
    preflight as preflight_mod,
    report as report_mod,
    review_ui as rui_mod,
    stills as stills_mod,
    takes as T,
)
from film_pipeline.production.edit import EditEvent, EditSection, TextLine, render_cut
from film_pipeline.production.package import load_package, wants_portrait
from film_pipeline.production.plan import plan_package

ROOT = Path(__file__).resolve().parents[1]
FILM03 = ROOT / "films" / "film03_front_desk"
FFMPEG = shutil.which("ffmpeg")
needs_ffmpeg = pytest.mark.skipif(not FFMPEG, reason="ffmpeg not available")


def _copy_film03(tmp_path: Path, count: int | None = 4) -> Path:
    root = tmp_path / "film"
    root.mkdir(parents=True, exist_ok=True)
    for name in ("film.json", "script.fountain", "01_story.json", "02_direction.json", "03_preprod.json", "04_shots.json"):
        shutil.copyfile(FILM03 / name, root / name)
    if count is not None:
        shots = json.loads((root / "04_shots.json").read_text(encoding="utf-8"))
        shots["generations"] = shots["generations"][:count]
        for g in shots["generations"]:
            g["previous_generation_id"] = None
        (root / "04_shots.json").write_text(json.dumps(shots, indent=2), encoding="utf-8")
    return root


def _make_clip(out: Path, *, duration_s: float = 2.0, vf: str = "", color: str = "0x304050",
               audio_vol: float = 0.25, size: str = "320x180", testsrc: bool = False) -> Path:
    out.parent.mkdir(parents=True, exist_ok=True)
    vsrc = f"testsrc2=size={size}:rate=24:duration={duration_s:.3f}" if testsrc else f"color=c={color}:s={size}:r=24:d={duration_s:.3f}"
    cmd = [
        "ffmpeg", "-v", "error", "-y",
        "-f", "lavfi", "-i", vsrc,
        "-f", "lavfi", "-i", f"sine=f=440:r=48000:d={duration_s:.3f}",
    ]
    if vf:
        cmd += ["-vf", vf]
    cmd += [
        "-af", f"volume={audio_vol}",
        "-c:v", "libx264", "-preset", "ultrafast", "-pix_fmt", "yuv420p",
        "-c:a", "aac", "-ac", "2", "-ar", "48000", "-shortest", str(out),
    ]
    subprocess.run(cmd, check=True, timeout=120)
    return out


# ---------------------------------------------------------------------------
# 1. review_ui --triage + WaveDAGScheduler warnings/cache fix + new optical/audio triage
# ---------------------------------------------------------------------------

@needs_ffmpeg
def test_triage_warnings_surface_in_review_ui_and_block_speculative_lookahead(tmp_path):
    root = _copy_film03(tmp_path, 2)
    shots = json.loads((root / "04_shots.json").read_text(encoding="utf-8"))
    g0, g1 = shots["generations"][0]["generation_id"], shots["generations"][1]["generation_id"]
    shots["generations"][1]["previous_generation_id"] = g0
    (root / "04_shots.json").write_text(json.dumps(shots, indent=2), encoding="utf-8")

    # Static dark picture with clipped audio + bright bottom-right corner mark -> FROZEN_TAKE_RISK + AUDIO_CLIPPING_RISK + CORNER_MARK_PRESENT
    bad_clip = _make_clip(
        root / "media" / "takes" / f"{g0}_t1.mp4",
        duration_s=3.0,
        color="0x181818",
        vf="drawbox=x=iw-16:y=ih-12:w=16:h=12:color=white:t=fill",
        audio_vol=25.0,
    )
    entry, _ = T.register_take(root, "film03_front_desk", g0, bad_clip, prompt_text="p", route="flow", model="m", credits=6.0)

    ui = rui_mod.build_review_ui(load_package(root), run_triage=True)
    assert ui["flagged_pending_count"] == 1
    html_body = Path(ui["html"]).read_text(encoding="utf-8")
    assert '"triage_status": "FLAGGED"' in html_body or '"triage_status":"FLAGGED"' in html_body
    assert "FROZEN_TAKE_RISK" in html_body
    assert "AUDIO_CLIPPING_RISK" in html_body
    assert (root / "media" / "triage" / f"{entry.take_id}.json").is_file()
    assert not (root / "takes" / "triage").exists()

    # Speculative lookahead must NOT advance past a flagged GENERATED take
    waves = WaveDAGScheduler(load_package(root), optimistic_lookahead=1).plan_waves()
    assert g1 not in waves["speculative_frontier"]


@needs_ffmpeg
def test_triage_detects_luma_flicker_spike_and_reuses_cache_and_batches(tmp_path, monkeypatch):
    root = _copy_film03(tmp_path, 2)
    pkg = load_package(root)
    g0, g1 = [g.generation_id for g in pkg.typed["shots"].generations]

    # Mid-clip white flash at t=0.9..1.1s on moving picture -> LUMA_FLICKER_SPIKE
    flash_clip = _make_clip(
        root / "media" / "takes" / f"{g0}_t1.mp4",
        duration_s=2.2,
        testsrc=True,
        vf="drawbox=x=0:y=0:w=iw:h=ih:color=white:t=fill:enable='between(t,0.9,1.15)'",
    )
    clean_clip = _make_clip(root / "media" / "takes" / f"{g1}_t1.mp4", duration_s=2.0, testsrc=True)
    e0, _ = T.register_take(root, pkg.header.film_id, g0, flash_clip, prompt_text="p0", route="flow", model="m", credits=6.0)
    e1, _ = T.register_take(root, pkg.header.film_id, g1, clean_clip, prompt_text="p1", route="flow", model="m", credits=6.0)

    batch = dt_mod.triage_batch(load_package(root), [e0.take_id, e1.take_id], jobs=2)
    codes_0 = {w["code"] for w in batch[e0.take_id]["warnings"]}
    assert "LUMA_FLICKER_SPIKE" in codes_0

    # Cache hit does not invoke _gray_frames again
    monkeypatch.setattr(dt_mod, "_gray_frames", lambda *_a, **_k: pytest.fail("expected triage cache hit"))
    cached_tri = dt_mod.triage_take(load_package(root), e0.take_id)
    assert cached_tri["output_sha256"] == e0.output_sha256
    assert "LUMA_FLICKER_SPIKE" in {w["code"] for w in cached_tri["warnings"]}


# ---------------------------------------------------------------------------
# 2. Scratch volume auto-overflow & preflight doctor
# ---------------------------------------------------------------------------

def test_scratch_dir_overflows_when_default_temp_is_low_and_blocks_when_all_low(tmp_path, monkeypatch):
    low_tmp = tmp_path / "low_temp"
    spacious_scratch = tmp_path / "spacious_scratch"
    film_dir = tmp_path / "film_vol"
    low_tmp.mkdir()
    spacious_scratch.mkdir()
    film_dir.mkdir()

    def fake_usage(p):
        ps = str(p)
        if "spacious_scratch" in ps or "film_vol" in ps:
            return SimpleNamespace(free=50 * 2**30)
        return SimpleNamespace(free=3 * 2**30)

    monkeypatch.setattr(preflight_mod.tempfile, "gettempdir", lambda: str(low_tmp))
    monkeypatch.setattr(preflight_mod.shutil, "disk_usage", fake_usage)
    monkeypatch.setenv("AFP_SCRATCH_DIR", str(spacious_scratch))
    monkeypatch.setattr(preflight_mod.subprocess, "run", lambda *a, **k: SimpleNamespace(returncode=0, stdout="ffmpeg 7"))

    res = preflight_mod.check(film_dir, operation="render")
    assert res["ok"] is True
    assert res["volumes"]["scratch"]["path"] == str(spacious_scratch)

    # All drives low -> still blocks cleanly
    monkeypatch.delenv("AFP_SCRATCH_DIR", raising=False)
    monkeypatch.setattr(preflight_mod.shutil, "disk_usage", lambda _p: SimpleNamespace(free=2 * 2**30))
    bad = preflight_mod.check(film_dir, operation="render")
    assert bad["ok"] is False
    assert any("scratch has" in msg for msg in bad["issues"])


# ---------------------------------------------------------------------------
# 3. planning_issues skips RISK_NO_FALLBACK once current-version take is ACCEPTED
# ---------------------------------------------------------------------------

def test_planning_issues_skips_no_fallback_on_accepted_shot_only(tmp_path):
    root = _copy_film03(tmp_path, 1)
    shots = json.loads((root / "04_shots.json").read_text(encoding="utf-8"))
    pre = json.loads((root / "03_preprod.json").read_text(encoding="utf-8"))
    g = shots["generations"][0]
    gid = g["generation_id"]
    # Trigger CONTACT HIGH risk with no entry in preprod.risk_fallbacks
    g["choreography"]["phases"][0]["description"] = "NORA and KESSLER shake hands across the desk"
    pre.get("risk_fallbacks", {}).pop(gid, None)
    (root / "04_shots.json").write_text(json.dumps(shots, indent=2), encoding="utf-8")
    (root / "03_preprod.json").write_text(json.dumps(pre, indent=2), encoding="utf-8")

    before = planning_mod.planning_report(load_package(root))
    assert any("RISK_NO_FALLBACK" in i and gid in i for i in before["issues"])

    # Register & mark ACCEPTED without review_file -> still blocked; with review_file -> RISK_NO_FALLBACK resolved
    clip = root / "media" / "takes" / f"{gid}_t1.mp4"
    clip.parent.mkdir(parents=True, exist_ok=True)
    clip.write_bytes(b"verified-accepted-clip")
    entry, _ = T.register_take(root, "film03_front_desk", gid, clip, prompt_text="p", route="flow", model="m", credits=6.0)
    log = T.load_log(root, "film03_front_desk")
    log.get(entry.take_id).status = "ACCEPTED"
    T.save_log(root, log)
    mid = planning_mod.planning_report(load_package(root))
    assert any("RISK_NO_FALLBACK" in i and gid in i for i in mid["issues"])

    rev_rel = f"takes/reviews/{entry.take_id}.json"
    (root / rev_rel).parent.mkdir(parents=True, exist_ok=True)
    (root / rev_rel).write_text("{}", encoding="utf-8")
    log = T.load_log(root, "film03_front_desk")
    log.get(entry.take_id).review_file = rev_rel
    T.save_log(root, log)

    after = planning_mod.planning_report(load_package(root))
    assert not any("RISK_NO_FALLBACK" in i and gid in i for i in after["issues"])
    assert after["risk_summary"] == before["risk_summary"]


# ---------------------------------------------------------------------------
# 4. report.next_action prioritizes Owner acceptance & finished Gate 4 over stale unused sends
# ---------------------------------------------------------------------------

def test_report_next_action_handles_accepted_and_finished_films_with_unused_receipts():
    all_pass = {str(k): {"name": f"G{k}", "status": "PASS", "first": []} for k in range(1, 7)}
    stale_sends = [{"take_id": "SC12_g23_t2"}]
    prod_complete = {"not_rendered": [], "open_retakes": [], "awaiting_review": [], "takes": 300}
    assert report_mod.next_action({"gates": all_pass, "production": prod_complete, "pending_sends": stale_sends}) == (
        "Nothing open on the pipeline side: delivery accepted by the Owner"
    )

    gate6_pending = {**all_pass, "6": {"name": "Release", "status": "OWNER_PENDING", "first": ["awaiting owner"]}}
    assert "Owner decision needed at Gate 6" in report_mod.next_action(
        {"gates": gate6_pending, "production": prod_complete, "pending_sends": stale_sends}
    )

    still_generating = {**all_pass, "4": {"name": "Production", "status": "BLOCK", "first": ["missing"]},
                        "5": {"name": "Post", "status": "NOT_RUN", "first": []},
                        "6": {"name": "Release", "status": "NOT_RUN", "first": []}}
    prod_incomplete = {"not_rendered": ["SC01_g2"], "open_retakes": [], "awaiting_review": [], "takes": 1}
    assert "Reconcile existing send SC12_g23_t2" in report_mod.next_action(
        {"gates": still_generating, "production": prod_incomplete, "pending_sends": stale_sends}
    )


# ---------------------------------------------------------------------------
# 5. Dual-aspect legacy custody vs 16:9 default + status --all optional path
# ---------------------------------------------------------------------------

def test_wants_portrait_preserves_legacy_archive_and_defaults_new_packages_to_16x9(tmp_path, monkeypatch):
    root = _copy_film03(tmp_path, 1)
    assert wants_portrait(load_package(root)) is False

    # Simulate an existing delivered dual-aspect archive (like film06/film07/film08) without editing film.json
    arch = root / "media" / "deliveries" / "legacy"
    arch.mkdir(parents=True)
    (arch / "MANIFEST.json").write_text(
        json.dumps({"masters": {"master_16x9": "masters/a.mp4", "portrait_9x16": "masters/b.mp4"}}),
        encoding="utf-8",
    )
    (root / "07_delivery.json").write_text(
        json.dumps({"delivery": {"manifest": "media/deliveries/legacy/MANIFEST.json"}}),
        encoding="utf-8",
    )
    assert wants_portrait(load_package(root)) is True
    assert wants_portrait(root) is True

    # status --all works without positional argument
    films_parent = tmp_path / "films_collection"
    films_parent.mkdir()
    shutil.copytree(root, films_parent / "film03_front_desk")
    monkeypatch.setattr(cli_mod, "DEFAULT_FILMS_DIR", films_parent)
    buf = io.StringIO()
    monkeypatch.setattr(sys, "stdout", buf)
    assert cli_mod.main(["status", "--all"]) == 0
    parsed = json.loads(buf.getvalue())
    assert len(parsed["films"]) == 1


# ---------------------------------------------------------------------------
# 6. flow_send pure-Pillow fallback without cv2 & byte-identical packaged copy
# ---------------------------------------------------------------------------

def test_flow_send_pillow_fallback_without_cv2_and_synced_copies(monkeypatch):
    repo_fs = ROOT / "tools" / "drama_flow_ui" / "flow_send.py"
    pkg_fs = ROOT / "src" / "film_pipeline" / "providers" / "_flow_ui" / "flow_send.py"
    assert repo_fs.read_bytes() == pkg_fs.read_bytes()

    sys.path.insert(0, str(repo_fs.parent))
    import flow_send as fs

    monkeypatch.setitem(sys.modules, "cv2", None)
    b1 = io.BytesIO()
    b2 = io.BytesIO()
    b3 = io.BytesIO()
    im1 = Image.new("RGB", (160, 90), (40, 40, 40))
    for x in range(30, 130):
        for y in range(20, 70):
            im1.putpixel((x, y), (210, 210, 210))
    im1.save(b1, format="PNG", compress_level=1)
    im1.save(b2, format="PNG", compress_level=9)
    im_diff = Image.new("RGB", (160, 90), (200, 30, 30))
    im_diff.save(b3, format="PNG")

    raw1, raw2, raw3 = b1.getvalue(), b2.getvalue() + b"\x00", b3.getvalue()
    assert fs.same_image(raw1, raw2) is True
    assert fs.same_image(raw1, raw3) is False

    sigs_a = fs.tile_signatures(b1.getvalue(), [(10, 10, 120, 70)], 1.0)
    sigs_b = fs.tile_signatures(b3.getvalue(), [(10, 10, 120, 70)], 1.0)
    assert len(sigs_a) == 1 and len(sigs_b) == 1
    assert fs.new_tiles(sigs_a, sigs_a) == 0
    assert fs.new_tiles(sigs_a, sigs_b) == 1


# ---------------------------------------------------------------------------
# 7. subtitle_png balanced multi-line wrapping without horizontal edge clipping
# ---------------------------------------------------------------------------

def test_subtitle_png_wraps_long_cues_inside_frame_and_keeps_short_cues_single_line(tmp_path):
    short_png = drama_post.subtitle_png(tmp_path / "short.png", "One ticket to Halden.")
    long_text = (
        "Chain of custody requires every evidence bag seal number to be read aloud "
        "on camera before the locker door closes for the night."
    )
    long_png = drama_post.subtitle_png(tmp_path / "long.png", long_text)

    with Image.open(short_png) as s_im, Image.open(long_png) as l_im:
        s_box = s_im.split()[3].getbbox()
        l_box = l_im.split()[3].getbbox()
        assert s_box is not None and l_box is not None
        assert l_box[0] >= 12 and l_box[2] <= drama_post.W - 12
        # Multi-line wrapped subtitle box is taller than single-line box
        assert (l_box[3] - l_box[1]) > (s_box[3] - s_box[1]) + 20


# ---------------------------------------------------------------------------
# 8. PreSendCritic stage-direction leak, end-still check, and pace overflow
# ---------------------------------------------------------------------------

def test_pre_send_critic_catches_stage_direction_end_still_and_pace_overflow(tmp_path):
    root = _copy_film03(tmp_path, 1)
    # Inject parenthetical + long dialogue into script line 14 and enable end_frame on SC01_g1
    script_path = root / "script.fountain"
    fountain = script_path.read_text(encoding="utf-8")
    fountain = fountain.replace(
        "Complaints window opens at nine.",
        "(sighs quietly) Complaints window opens at nine sharp and every single duplicate yellow intake slip must be stamped twice before you step up to the glass.",
    )
    script_path.write_text(fountain, encoding="utf-8")
    shots = json.loads((root / "04_shots.json").read_text(encoding="utf-8"))
    shots["generations"][0]["end_frame"] = True
    shots["generations"][0]["duration_s"] = 4
    (root / "04_shots.json").write_text(json.dumps(shots, indent=2), encoding="utf-8")

    pkg = load_package(root)
    plan_package(pkg, root / "media" / "plan", storyboard=False)
    rep = PreSendCritic().inspect(load_package(root), plan_dir=root / "media" / "plan")
    codes = {f["code"] for f in rep["findings"]}
    assert "END_STILL_NOT_READY" in codes
    assert "STAGE_DIRECTION_IN_DIALOGUE" in codes
    assert "DIALOGUE_PACE_OVERFLOW" in codes


# ---------------------------------------------------------------------------
# 9. Single-pass dialogue_stt PCM decoding & slicing
# ---------------------------------------------------------------------------

def test_dialogue_stt_single_pass_16k_wav_decoding_spawns_zero_ffmpeg(tmp_path, monkeypatch):
    wav_path = tmp_path / "mono16k.wav"
    sr = 16000
    # 3 seconds: first 1.5s tone amplitude 4000, last 1.5s silence
    samples = [int(4000 * math.sin(2 * math.pi * 440 * i / sr)) if i < int(1.5 * sr) else 0 for i in range(3 * sr)]
    with wave.open(str(wav_path), "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(sr)
        wf.writeframes(struct.pack(f"<{len(samples)}h", *samples))

    monkeypatch.setattr(stt_mod.subprocess, "run", lambda *a, **k: pytest.fail("16kHz mono WAV must not spawn ffmpeg"))
    pcm = stt_mod.decode_mono_16k_pcm(wav_path, start_s=0.0, duration_s=3.0)
    first_slice = stt_mod.slice_pcm_16k(pcm, 0.0, 0.2, 1.0)
    silent_slice = stt_mod.slice_pcm_16k(pcm, 0.0, 2.0, 2.8)
    assert any(b != 0 for b in first_slice)
    assert all(b == 0 for b in silent_slice)


# ---------------------------------------------------------------------------
# 10. ColorPlan(group_by_camera=True) & MixPlan(dialogue_cleanup=True)
# ---------------------------------------------------------------------------

@needs_ffmpeg
def test_color_group_by_camera_prevents_reverse_wall_distortion_and_mix_cleanup_runs(tmp_path):
    root = _copy_film03(tmp_path, 4)
    shots = json.loads((root / "04_shots.json").read_text(encoding="utf-8"))
    gids = []
    # Two bright cool window shots (ESTABLISHED / NORA) and two dark warm shelf shots (REVERSE / KESSLER) in SC01
    specs = [
        ("ESTABLISHED", "NORA", "0xB8C8D8"),
        ("ESTABLISHED", "NORA", "0xB2C2D2"),
        ("REVERSE", "KESSLER", "0x483828"),
        ("REVERSE", "KESSLER", "0x4E3E2E"),
    ]
    clips_dir = tmp_path / "clips"
    for g, (side, subj, hex_col) in zip(shots["generations"], specs):
        g["scene_id"] = "SC01"
        g["coverage"] = "SINGLE"
        g["subject"] = subj
        g["foreground"] = ""
        g["visible"] = [subj]
        g["choreography"]["performance"] = []
        g["camera"]["size"] = "MEDIUM_CLOSE"
        g["camera"]["lens_intent"] = "SHALLOW_ISOLATE"
        g["camera"]["side"] = side
        if side == "REVERSE":
            g["camera"]["crossing_note"] = "reverse angle onto dark wall"
        gids.append(g["generation_id"])
    (root / "04_shots.json").write_text(json.dumps(shots, indent=2), encoding="utf-8")
    pkg_check = load_package(root)
    assert "shots" in pkg_check.typed, pkg_check.issues

    for gid, (_, _, hex_col) in zip(gids, specs):
        c = _make_clip(clips_dir / f"{gid}.mp4", duration_s=1.5, color=hex_col)
        T.register_take(root, "film03_front_desk", gid, c, prompt_text=f"p {gid}", route="flow", model="m", credits=6.0)

    flat_rep = color_mod.match(load_package(root), clips_dir=clips_dir, plan=color_mod.ColorPlan(group_by_camera=False), jobs=2)
    cam_rep = color_mod.match(load_package(root), clips_dir=clips_dir, plan=color_mod.ColorPlan(group_by_camera=True), jobs=2)

    assert flat_rep["summary"]["worst_after"] > 20.0
    assert any(p["code"] == "OUT_OF_RANGE" for p in flat_rep["problems"])
    assert cam_rep["summary"]["worst_after"] <= 6.0
    assert cam_rep["problems"] == []

    # Verify MixPlan(dialogue_cleanup=True) produces loudness-compliant master
    edl = EditSection(
        events=[EditEvent(event_id=f"e{i+1}", take_id=f"{gid}_t1") for i, gid in enumerate(gids[:2])],
        title=[TextLine(text="Test", size=48), TextLine(text="Generated with AI", size=24)],
        title_s=1.0,
        end=[TextLine(text="End", size=40)],
        end_s=0.5,
    )
    (root / "05_edit.json").write_text(edl.model_dump_json(), encoding="utf-8")
    cut_mp4 = root / "media" / "cut" / "rough_cut.mp4"
    render_cut(load_package(root), edl, cut_mp4, clips_dir=clips_dir)
    mixed_mp4 = root / "media" / "cut" / "mixed.mp4"
    mrep = mix_mod.mix_cut(
        load_package(root), edl, cut_mp4, mixed_mp4,
        plan=mix_mod.MixPlan(dialogue_cleanup=True),
    )
    assert mrep["ok"] is True
    assert abs(mrep["loudness"]["after"]["integrated_lufs"] - (-14.0)) <= 1.0
