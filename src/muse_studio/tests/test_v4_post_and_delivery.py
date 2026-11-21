import json
import math
import re
import subprocess
import sys
import wave
from pathlib import Path
from unittest.mock import patch

import numpy as np
import pytest
from PIL import Image, ImageDraw
from scipy import signal

from muse_studio.core.cinema_audio_engine import CinemaAudioEngine, VoiceTimbreMatcher
from muse_studio.core.delivery_packager import DeliveryPackager
from muse_studio.core.film_qc_engine import FilmQCEngine
from muse_studio.core.master_assembler import MasterAssembler


def _write_stereo_wav(path: Path, left: np.ndarray, right: np.ndarray = None, sr: int = 48000) -> Path:
    if right is None:
        right = left
    stereo = np.clip(np.stack([left, right], axis=1), -0.98, 0.98)
    pcm = (stereo * 32767.0).astype(np.int16)
    path.parent.mkdir(parents=True, exist_ok=True)
    with wave.open(str(path), "wb") as wf:
        wf.setnchannels(2)
        wf.setsampwidth(2)
        wf.setframerate(sr)
        wf.writeframes(pcm.tobytes())
    return path


def _read_wav_float(path: Path):
    with wave.open(str(path), "rb") as wf:
        ch = wf.getnchannels()
        sr = wf.getframerate()
        n = wf.getnframes()
        raw = np.frombuffer(wf.readframes(n), dtype=np.int16).astype(np.float32) / 32768.0
    return raw.reshape(-1, ch), sr


def _synth_harmonic_voice_wav(path: Path, duration_s: float = 2.2, bright_boost: bool = False, sr: int = 48000) -> Path:
    n = int(duration_s * sr)
    t = np.arange(n, dtype=np.float32) / sr
    # Speech-like syllable envelope so active-frame detector sees realistic voiced segments
    syllable_env = np.clip(0.55 + 0.45 * np.sin(2 * np.pi * 3.2 * t), 0.0, 1.0)
    sig = np.zeros(n, dtype=np.float32)
    f0 = 165.0
    for k in range(1, 28):
        fk = f0 * k
        if fk >= 7400.0:
            break
        if bright_boost:
            amp = (0.04 / math.sqrt(k)) * (3.8 if 2200.0 <= fk <= 4800.0 else 0.35)
        else:
            amp = (0.18 / math.sqrt(k)) * (2.4 if 160.0 <= fk <= 750.0 else 0.25)
        sig += amp * np.sin(2 * np.pi * fk * t + 0.13 * k)
    sig = sig * syllable_env
    peak = float(np.max(np.abs(sig))) or 1.0
    sig = (sig / peak) * 0.45
    return _write_stereo_wav(path, sig, sig, sr=sr)


def _make_colored_clip(
    path: Path,
    duration_s: float = 3.3,
    rgb=(110, 110, 110),
    face_xy=(960, 320),
    bright_voice: bool = False,
) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    frame_png = path.with_suffix(".frame.png")
    img = Image.new("RGB", (1280, 720), rgb)
    d = ImageDraw.Draw(img)
    fx, fy = face_xy
    # Draw stylized head/shoulders + background geometry so clip is non-flat
    d.rectangle([80, 80, 1200, 660], outline=(180, 185, 195), width=3)
    d.ellipse([fx - 70, fy - 90, fx + 70, fy + 90], fill=(196, 148, 116))
    d.rectangle([fx - 120, fy + 90, fx + 120, 680], fill=(35, 50, 75))
    img.save(frame_png)

    wav_path = path.with_suffix(".voice.wav")
    _synth_harmonic_voice_wav(wav_path, duration_s=duration_s, bright_boost=bright_voice)

    subprocess.run(
        [
            "ffmpeg", "-y",
            "-loop", "1", "-t", f"{duration_s:.2f}", "-i", str(frame_png),
            "-i", str(wav_path),
            "-vf", "fps=24,noise=c0s=4:c0f=t,format=yuv420p",
            "-c:v", "libx264", "-preset", "ultrafast", "-pix_fmt", "yuv420p",
            "-c:a", "aac", "-b:a", "192k", "-ar", "48000", "-ac", "2",
            "-shortest", str(path),
        ],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        check=True,
    )
    frame_png.unlink(missing_ok=True)
    wav_path.unlink(missing_ok=True)
    return path


def test_dialogue_cleanup_af_chain_and_ffmpeg_execution(tmp_path: Path):
    af = CinemaAudioEngine.build_dialogue_cleanup_af(clip_dur=2.4)
    for token in (
        "aformat=sample_rates=48000:channel_layouts=stereo",
        "highpass=f=80",
        "afftdn=nf=-24",
        "equalizer=f=3000:t=q:w=1.2:g=1.8",
        "acompressor=threshold=-18dB:ratio=2.5:attack=15:release=180",
        "afade=t=in",
        "afade=t=out",
    ):
        assert token in af

    src_wav = _synth_harmonic_voice_wav(tmp_path / "noisy_speech.wav", duration_s=2.4)
    out_wav = tmp_path / "cleaned_speech.wav"
    subprocess.run(
        ["ffmpeg", "-y", "-i", str(src_wav), "-af", af, str(out_wav)],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        check=True,
    )
    samples, sr = _read_wav_float(out_wav)
    assert sr == 48000
    assert samples.shape[1] == 2
    assert float(np.max(np.abs(samples))) > 0.05


def test_voice_timbre_matcher_profile_fir_and_external_sts(tmp_path: Path):
    warm_wav = _synth_harmonic_voice_wav(tmp_path / "warm.wav", duration_s=2.2, bright_boost=False)
    harsh_wav = _synth_harmonic_voice_wav(tmp_path / "harsh.wav", duration_s=2.2, bright_boost=True)
    silent_wav = _write_stereo_wav(tmp_path / "silent.wav", np.zeros(48000, dtype=np.float32))

    assert VoiceTimbreMatcher.extract_voice_profile(silent_wav) is None

    warm_prof = VoiceTimbreMatcher.extract_voice_profile(warm_wav)
    harsh_prof = VoiceTimbreMatcher.extract_voice_profile(harsh_wav)
    assert warm_prof is not None and harsh_prof is not None
    assert warm_prof.shape == (16,)
    assert harsh_prof.shape == (16,)
    dist_before = float(np.linalg.norm(harsh_prof - warm_prof))
    assert dist_before > 3.0

    matched_wav = tmp_path / "matched.wav"
    res_path = VoiceTimbreMatcher.apply_voice_timbre_match(
        harsh_wav, warm_prof, matched_wav, strength=0.65
    )
    assert res_path == matched_wav and matched_wav.exists()
    samples, sr = _read_wav_float(matched_wav)
    assert sr == 48000 and samples.shape[1] == 2

    matched_prof = VoiceTimbreMatcher.extract_voice_profile(matched_wav)
    assert matched_prof is not None
    dist_after = float(np.linalg.norm(matched_prof - warm_prof))
    assert dist_after < dist_before

    # Optional external STS command template support
    sts_out = tmp_path / "sts_matched.wav"
    py_exe = str(Path(sys.executable)).replace("\\", "/")
    sts_cmd = f'"{py_exe}" -c "import shutil, sys; shutil.copyfile(sys.argv[1], sys.argv[2])" "{{input}}" "{{output}}"'
    VoiceTimbreMatcher.apply_voice_timbre_match(
        warm_wav, warm_prof, sts_out, voice_converter_cmd=sts_cmd
    )
    assert sts_out.exists() and sts_out.stat().st_size > 1000


def test_location_ambience_archetypes_crossfade_and_asset_override(tmp_path: Path):
    amb_wav = tmp_path / "ambience.wav"
    CinemaAudioEngine.build_scene_ambience_track(
        segments=[(0.0, 2.0, "LOC_COCKPIT"), (2.0, 2.0, "LOC_CONCOURSE_TERMINAL")],
        output_path=amb_wav,
        crossfade_s=0.5,
    )
    samples, sr = _read_wav_float(amb_wav)
    assert sr == 48000 and samples.shape[1] == 2
    assert abs(len(samples) / sr - 4.0) < 0.1

    # Compare spectral centroid of cockpit (0.3..1.4s) vs terminal concourse (2.6..3.7s)
    f1, p1 = signal.welch(samples[int(0.3 * sr) : int(1.4 * sr), 0], fs=sr, nperseg=2048)
    f2, p2 = signal.welch(samples[int(2.6 * sr) : int(3.7 * sr), 0], fs=sr, nperseg=2048)
    c1 = float(np.sum(f1 * p1) / (np.sum(p1) + 1e-12))
    c2 = float(np.sum(f2 * p2) / (np.sum(p2) + 1e-12))
    assert abs(c1 - c2) > 40.0

    # Smooth crossfade region around t=2.0s has continuous energy (no dropout)
    mid_rms = float(np.sqrt(np.mean(samples[int(1.85 * sr) : int(2.15 * sr), 0] ** 2)))
    assert mid_rms > 1e-4

    # Custom WAV asset loading from assets/audio/ambience/<loc_id>.wav
    assets_audio = tmp_path / "assets" / "audio"
    t = np.arange(sr * 2, dtype=np.float32) / sr
    _write_stereo_wav(assets_audio / "ambience" / "LOC_COURTROOM.wav", 0.2 * np.sin(2 * np.pi * 520.0 * t))
    custom_amb = tmp_path / "custom_amb.wav"
    CinemaAudioEngine.build_scene_ambience_track(
        segments=[(0.0, 2.0, "LOC_COURTROOM")],
        output_path=custom_amb,
        assets_audio_dir=assets_audio,
    )
    cs, _ = _read_wav_float(custom_amb)
    fc, pc = signal.welch(cs[:, 0], fs=sr, nperseg=4096)
    peak_hz = float(fc[int(np.argmax(pc))])
    assert 490.0 <= peak_hz <= 550.0


def test_12_class_foley_detection_and_track_synthesis(tmp_path: Path):
    prompt_all_12 = (
        "Officer walks toward gate door, rustles clipboard paper, sits on chair, "
        "judge strikes gavel, taps smartphone, types on console keyboard, sets coffee cup, "
        "turns jacket coat, slides metal pin on counter, intercom beep sounds, snatches badge."
    )
    events = CinemaAudioEngine.detect_foley_events(prompt_all_12, start_s=0.0, duration_s=6.0)
    detected_classes = {kind for _, kind in events}
    expected_12 = {
        "footsteps", "door_latch", "paper_rustle", "chair_shift",
        "gavel_strike", "phone_tap", "keyboard_type", "cup_set",
        "cloth_movement", "metal_clink", "intercom_beep", "badge_snatch",
    }
    assert expected_12.issubset(detected_classes)

    foley_wav = tmp_path / "foley_12.wav"
    CinemaAudioEngine.build_foley_track(6.5, events, foley_wav)
    samples, sr = _read_wav_float(foley_wav)
    assert sr == 48000 and samples.shape[1] == 2
    assert float(np.max(np.abs(samples))) > 0.05


def test_dynamic_score_track_moods_and_crossfade_to_silence(tmp_path: Path):
    score_wav = tmp_path / "score.wav"
    CinemaAudioEngine.build_dynamic_score_track(
        segments=[
            (0.0, 2.2, "tension"),
            (2.2, 2.2, "escalation"),
            (4.4, 2.2, "warm_flashback"),
            (6.6, 1.8, "silence"),
        ],
        output_path=score_wav,
        crossfade_s=1.0,
    )
    samples, sr = _read_wav_float(score_wav)
    assert sr == 48000 and samples.shape[1] == 2
    rms_tension = float(np.sqrt(np.mean(samples[int(0.5 * sr) : int(1.5 * sr), 0] ** 2)))
    rms_flashback = float(np.sqrt(np.mean(samples[int(4.9 * sr) : int(5.9 * sr), 0] ** 2)))
    rms_silence = float(np.sqrt(np.mean(samples[int(7.4 * sr) : int(8.2 * sr), 0] ** 2)))
    assert rms_tension > 0.01
    assert rms_flashback > 0.01
    assert rms_silence < 1e-4


def test_slate_renderer_netflix_srt_chapters_capcut_and_delivery_kit(tmp_path: Path):
    # 1. Opening Title & End Credits Slates
    open_mp4 = DeliveryPackager.render_slate_clip(
        tmp_path / "opening.mp4",
        kind="opening",
        title="Flight 1128",
        subtitle="Based on True Aviation Events",
    )
    cred_mp4 = DeliveryPackager.render_slate_clip(
        tmp_path / "credits.mp4",
        kind="credits",
        title="Flight 1128",
        characters=[
            {"id": "C1", "name": "Brianna Johnson", "role": "Airline Captain"},
            {"id": "C2", "name": "Katherine Moore", "role": "Federal Judge"},
        ],
    )
    for mp4, exp_dur in ((open_mp4, 2.5), (cred_mp4, 3.0)):
        probe = json.loads(subprocess.check_output([
            "ffprobe", "-v", "error", "-show_streams", "-show_format", "-of", "json", str(mp4)
        ], text=True))
        vs = next(s for s in probe["streams"] if s["codec_type"] == "video")
        aus = next(s for s in probe["streams"] if s["codec_type"] == "audio")
        assert int(vs["width"]) == 1920 and int(vs["height"]) == 1080
        assert vs["pix_fmt"] == "yuv420p"
        assert vs["r_frame_rate"] == "24/1"
        assert aus["sample_rate"] == "48000" and int(aus["channels"]) == 2
        assert abs(float(probe["format"]["duration"]) - exp_dur) < 0.25

    # 2. Word-Accurate Netflix SRT + i18n template
    words = [
        {"word": "Captain", "start": 0.90, "end": 1.15},
        {"word": "Brianna", "start": 1.15, "end": 1.45},
        {"word": "Johnson,", "start": 1.45, "end": 1.80},
        {"word": "please", "start": 1.85, "end": 2.05},
        {"word": "step", "start": 2.05, "end": 2.25},
        {"word": "away", "start": 2.25, "end": 2.50},
        {"word": "from", "start": 2.50, "end": 2.65},
        {"word": "the", "start": 2.65, "end": 2.75},
        {"word": "cockpit", "start": 2.75, "end": 3.05},
        {"word": "bulkhead", "start": 3.05, "end": 3.35},
        {"word": "immediately.", "start": 3.35, "end": 3.70},
    ]
    srt_entries, i18n_cues = DeliveryPackager.build_srt_entries(
        timeline_shots=[
            {
                "shot_id": "SH01",
                "speaker": "Officer Craig",
                "text": "Captain Brianna Johnson, please step away from the cockpit bulkhead immediately.",
                "timeline_start_s": 2.50,
                "seg_dur_s": 3.50,
                "trim_in_s": 0.60,
                "words": words,
            },
            {
                "shot_id": "SH02",
                "speaker": "Brianna",
                "text": "Check my FAA certificate.",
                "timeline_start_s": 6.00,
                "seg_dur_s": 2.50,
                "trim_in_s": 0.0,
                "words": [],
            },
        ]
    )
    assert len(srt_entries) >= 3  # SH01 split into >= 2 blocks + SH02 fallback block
    # Exact first speech start: 2.50 + (0.90 - 0.60) = 2.80s -> 00:00:02,800
    assert "00:00:02,800 -->" in srt_entries[0]
    # Exact speech end of SH01: 2.50 + (3.70 - 0.60) = 5.60s -> 00:00:05,600
    sh01_cues = [c for c in i18n_cues if c["shot_id"] == "SH01"]
    assert abs(sh01_cues[-1]["end_s"] - 5.60) < 0.02
    for block in srt_entries:
        text_lines = block.strip().splitlines()[2:]
        assert 1 <= len(text_lines) <= 2
        assert all(len(ln) <= 42 for ln in text_lines)

    i18n_path = DeliveryPackager.export_i18n_template(
        i18n_cues, tmp_path / "master.i18n_template.json", project_title="Flight 1128"
    )
    i18n_data = json.loads(i18n_path.read_text(encoding="utf-8"))
    assert len(i18n_data["cues"]) == len(srt_entries)

    # 3. Chapters FFMETADATA1 + YouTube .chapters.txt
    sample_mp4 = _make_colored_clip(tmp_path / "base_master.mp4", duration_s=3.2, face_xy=(1020, 280))
    ch_txt = DeliveryPackager.embed_chapters_and_export_txt(
        target_mp4=sample_mp4,
        chapters=[
            {"start_s": 0.0, "end_s": 1.6, "title": "CH01: Jetbridge"},
            {"start_s": 1.6, "end_s": 3.2, "title": "CH02: Cockpit"},
        ],
        project_title="Flight 1128",
    )
    assert ch_txt.exists()
    assert "00:00 - CH01: Jetbridge" in ch_txt.read_text(encoding="utf-8")
    ch_probe = json.loads(subprocess.check_output([
        "ffprobe", "-v", "error", "-show_chapters", "-of", "json", str(sample_mp4)
    ], text=True))
    assert len(ch_probe["chapters"]) == 2

    # 4. CapCut Desktop Draft Project
    dlg_stem = _synth_harmonic_voice_wav(tmp_path / "dlg.wav", duration_s=3.2)
    me_stem = _synth_harmonic_voice_wav(tmp_path / "me.wav", duration_s=3.2)
    draft_dir = DeliveryPackager.export_capcut_draft_project(
        output_mp4=sample_mp4,
        clip_segments=[{"path": sample_mp4, "start_s": 0.0, "duration_s": 3.2}],
        dialogue_stem_path=dlg_stem,
        me_stem_path=me_stem,
        subtitle_cues=i18n_cues[:1],
    )
    dc = json.loads((draft_dir / "draft_content.json").read_text(encoding="utf-8"))
    dm = json.loads((draft_dir / "draft_meta_info.json").read_text(encoding="utf-8"))
    assert dc["canvas_config"]["width"] == 1920 and dc["canvas_config"]["height"] == 1080
    v_tracks = [t for t in dc["tracks"] if t["type"] == "video"]
    a_tracks = [t for t in dc["tracks"] if t["type"] == "audio"]
    t_tracks = [t for t in dc["tracks"] if t["type"] == "text"]
    assert len(v_tracks) == 1 and v_tracks[0]["segments"][0]["target_timerange"]["duration"] == 3_200_000
    assert len(a_tracks) >= 2
    assert len(t_tracks) == 1
    assert dm["draft_name"]

    # 5. Delivery Promo Kit (Trailer + 9:16 Smart-Cropped Vertical Shorts + 1080p Poster)
    kit = DeliveryPackager.build_delivery_kit(
        output_mp4=sample_mp4,
        normalized_clips=[sample_mp4],
        shots=[{"shot_id": "SH01", "is_climax_closeup": True}],
        project_title="Flight 1128",
        qc_reports={"SH01": {"metrics": {"face_boxes": [[920, 180, 200, 220]]}}},
    )
    trailer_p = Path(kit["trailer_mp4"])
    shorts_p = Path(kit["shorts_mp4"])
    poster_p = Path(kit["poster_png"])
    assert trailer_p.exists() and shorts_p.exists() and poster_p.exists()

    sh_probe = json.loads(subprocess.check_output([
        "ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries", "stream=width,height", "-of", "json", str(shorts_p)
    ], text=True))
    assert int(sh_probe["streams"][0]["width"]) == 1080
    assert int(sh_probe["streams"][0]["height"]) == 1920
    with Image.open(poster_p) as pim:
        assert pim.size == (1920, 1080)


def test_master_assembler_v4_di_color_stems_titles_face_tag_and_no_win_filter_paths(tmp_path: Path):
    c1 = _make_colored_clip(tmp_path / "sh1.mp4", duration_s=3.4, rgb=(115, 115, 115), face_xy=(980, 280), bright_voice=False)
    c2 = _make_colored_clip(tmp_path / "sh2.mp4", duration_s=3.4, rgb=(85, 110, 165), face_xy=(420, 280), bright_voice=True)
    c3 = _make_colored_clip(tmp_path / "sh3.mp4", duration_s=2.4, rgb=(125, 115, 105), face_xy=(640, 280), bright_voice=False)

    bible = {
        "project_title": "Captain Brianna",
        "subtitle": "Cinema v4 Test",
        "characters": [
            {"id": "CHAR_BRIANNA", "name": "Brianna Johnson", "role": "Airline Captain", "axis_gaze": "looking screen-right"},
            {"id": "CHAR_JUDGE", "name": "Katherine Moore", "role": "Federal Judge", "axis_gaze": "looking screen-left"},
        ],
        "locations": [
            {"id": "LOC_COCKPIT", "name": "Flight Deck"},
            {"id": "LOC_COURTROOM", "name": "Federal Courtroom"},
        ],
    }
    manifest = {
        "project_title": "Captain Brianna",
        "shots": [
            {
                "shot_id": "SH01", "chapter_id": "CH01", "location": "LOC_COCKPIT",
                "primary_character_id": "CHAR_BRIANNA", "gaze": "looking screen-right",
                "speaker": "Brianna", "dialogue": "Pre-flight checklist complete.",
                "action_summary": "Brianna flips clipboard paper on console.",
                "is_climax_closeup": False, "audio_mode": "NATIVE_DIALOGUE",
            },
            {
                "shot_id": "SH02", "chapter_id": "CH01", "location": "LOC_COCKPIT",
                "primary_character_id": "CHAR_BRIANNA", "gaze": "looking screen-right",
                "speaker": "Brianna", "dialogue": "I earned these four stripes.",
                "action_summary": "Brianna turns jacket and holds badge.",
                "is_flashback": True, "transition_in": "fade_in",
                "is_climax_closeup": True, "audio_mode": "NATIVE_DIALOGUE",
            },
            {
                "shot_id": "SH03", "chapter_id": "CH02", "location": "LOC_COURTROOM",
                "primary_character_id": "CHAR_JUDGE", "gaze": "looking screen-left",
                "speaker": "Judge Moore", "dialogue": "The court enters judgment.",
                "action_summary": "Judge strikes gavel on bench.",
                "is_climax_closeup": False, "audio_mode": "NATIVE_DIALOGUE",
            },
        ],
    }
    qc_reports = {
        "SH01": {
            "metrics": {
                # Two faces on the right half -> tag must be placed on left (x=180) despite screen-right gaze!
                "face_boxes": [[880, 150, 180, 200], [1080, 160, 160, 190]],
                "trim_window": {"trim_in_s": 0.0, "trim_out_s": 3.4},
                "dialogue_qc": {
                    "words": [
                        {"word": "Pre-flight", "start": 0.30, "end": 0.90},
                        {"word": "checklist", "start": 0.95, "end": 1.60},
                        {"word": "complete.", "start": 1.65, "end": 2.40},
                    ]
                },
            }
        }
    }

    recorded_ffmpeg_cmds = []
    real_run = subprocess.run

    def _spy_run(cmd, *args, **kwargs):
        if isinstance(cmd, (list, tuple)) and cmd and "ffmpeg" in str(cmd[0]).lower():
            recorded_ffmpeg_cmds.append([str(x) for x in cmd])
        return real_run(cmd, *args, **kwargs)

    out_mp4 = tmp_path / "master" / "film_v4.mp4"
    with patch("subprocess.run", side_effect=_spy_run):
        rep = MasterAssembler.assemble_project(
            shots_manifest=manifest,
            clip_paths_by_shot={"SH01": c1, "SH02": c2, "SH03": c3},
            output_mp4=out_mp4,
            story_bible=bible,
            qc_reports=qc_reports,
            capcut_draft=True,
            color_mood="cold_thriller",
            enable_film_grain=True,
            enable_voice_timbre_lock=True,
            enable_j_l_cuts=True,
            with_titles=True,
            export_stems=True,
            build_promo_kit=True,
        )

    assert rep["success"] is True
    assert out_mp4.exists()
    assert Path(rep["sidecar_srt"]).exists()
    assert Path(rep["capcut_manifest"]).exists()
    assert Path(rep["capcut_draft_dir"]).exists()
    assert Path(rep["me_stem"]).exists() and Path(rep["me_stem"]).stat().st_size > 2000
    assert Path(rep["dialogue_stem"]).exists() and Path(rep["dialogue_stem"]).stat().st_size > 2000
    assert Path(rep["chapters_txt"]).exists()
    assert Path(rep["i18n_template"]).exists()
    assert Path(rep["promo_kit"]["poster_png"]).exists()

    # Duration must include Opening Title (2.5s) + 3 shots (9.2s) + End Credits (3.0s) ~= 14.7s
    assert rep["duration_s"] >= 13.8

    # Verify Face-Aware Tag Placement chose x=180 on SH01 (not 1220) AND no Windows drive paths in -vf / -filter_complex
    saw_left_tag_overlay = False
    saw_colorbalance_and_grain = False
    win_drive_re = re.compile(r"[A-Za-z]:[\\/]")
    for cmd in recorded_ffmpeg_cmds:
        for i, arg in enumerate(cmd[:-1]):
            if arg in ("-vf", "-af", "-filter_complex"):
                fval = cmd[i + 1]
                assert not win_drive_re.search(fval), f"Windows path leaked into {arg}: {fval}"
                if "overlay=180:210" in fval:
                    saw_left_tag_overlay = True
                if "colorbalance=" in fval and "noise=c0s=3:c0f=t+u" in fval:
                    saw_colorbalance_and_grain = True

    assert saw_left_tag_overlay is True
    assert saw_colorbalance_and_grain is True

    # Full stream decode check
    ok_dec, dec_msg = FilmQCEngine.verify_full_decode(out_mp4)
    assert ok_dec is True, dec_msg
