"""
Cinema Audio Engine (v4 Post-Production):
- Dialogue Isolation & Cleanup Chain (`build_dialogue_cleanup_af`)
- Acoustic Voice Timbre Consistency Lock (`VoiceTimbreMatcher`)
- Location-Specific Ambience Track with 0.5s Cosine Crossfades (`build_scene_ambience_track`)
- 12-Class Acoustic Foley Detection & Multi-Transient Synthesis (`detect_foley_events`, `build_foley_track`)
- Chapter-Mood Evolving Musical Score with 1.0s Crossfades (`build_dynamic_score_track`)
- Sample-Accurate J/L-Cut Dialogue Stem Builder (`build_dialogue_stem_with_jl_cuts`)
"""

import math
import re
import shlex
import subprocess
import wave
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple, Union

import numpy as np
from scipy import signal


def _write_stereo_wav_48k(
    path: Path,
    samples_l: np.ndarray,
    samples_r: Optional[np.ndarray] = None,
    sr: int = 48000,
) -> Path:
    if samples_r is None:
        samples_r = samples_l
    stereo = np.stack([samples_l, samples_r], axis=1)
    peak = float(np.max(np.abs(stereo))) if stereo.size else 0.0
    if peak > 0.98:
        stereo = stereo * (0.98 / peak)
    stereo = np.clip(stereo, -0.98, 0.98)
    pcm = (stereo * 32767.0).astype(np.int16)
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with wave.open(str(path), "wb") as wf:
        wf.setnchannels(2)
        wf.setsampwidth(2)
        wf.setframerate(sr)
        wf.writeframes(pcm.tobytes())
    return path


def _load_audio_48k_stereo(media_path: Path, sr: int = 48000) -> np.ndarray:
    """Loads any WAV/media file as float32 shape (N, 2) at 48kHz."""
    media_path = Path(media_path)
    if media_path.suffix.lower() == ".wav":
        try:
            with wave.open(str(media_path), "rb") as wf:
                ch = wf.getnchannels()
                sw = wf.getsampwidth()
                fs = wf.getframerate()
                n = wf.getnframes()
                if sw == 2 and fs == sr and ch in (1, 2):
                    raw = np.frombuffer(wf.readframes(n), dtype=np.int16).astype(np.float32) / 32768.0
                    if ch == 1:
                        return np.stack([raw, raw], axis=1)
                    return raw.reshape(-1, 2)
        except Exception:
            pass

    cmd = [
        "ffmpeg", "-v", "error", "-i", str(media_path),
        "-vn", "-ac", "2", "-ar", str(sr), "-f", "s16le", "-",
    ]
    res = subprocess.run(cmd, capture_output=True, check=False)
    if res.returncode != 0 or not res.stdout:
        return np.zeros((sr, 2), dtype=np.float32)
    raw = np.frombuffer(res.stdout, dtype=np.int16).astype(np.float32) / 32768.0
    n_pairs = len(raw) // 2
    if n_pairs == 0:
        return np.zeros((sr, 2), dtype=np.float32)
    return raw[: n_pairs * 2].reshape(-1, 2)


def _loop_or_trim_stereo(buf: np.ndarray, target_len: int, fade_edge: int = 256) -> np.ndarray:
    """Loops or trims a (M, 2) stereo buffer cleanly to (target_len, 2)."""
    if target_len <= 0:
        return np.zeros((0, 2), dtype=np.float32)
    if len(buf) == 0:
        return np.zeros((target_len, 2), dtype=np.float32)
    if len(buf) >= target_len:
        return buf[:target_len].astype(np.float32, copy=True)

    reps = int(math.ceil(target_len / len(buf))) + 1
    tile = buf.astype(np.float32, copy=True)
    fe = min(fade_edge, len(tile) // 8)
    if fe > 4:
        ramp = np.linspace(0.0, 1.0, fe, dtype=np.float32)[:, None]
        tile[:fe] *= ramp
        tile[-fe:] *= ramp[::-1]
    tiled = np.tile(tile, (reps, 1))
    return tiled[:target_len]


class VoiceTimbreMatcher:
    """
    Acoustic Voice Timbre Consistency Lock:
    Locks per-character spectral formant/tilt across shots via 16-band Welch log-power
    envelope matching (`80Hz..7500Hz`) and 129-tap linear-phase FIR filtering.
    """

    BAND_EDGES = np.geomspace(80.0, 7500.0, 17)
    BAND_CENTERS = np.sqrt(BAND_EDGES[:-1] * BAND_EDGES[1:])

    @classmethod
    def extract_voice_profile(cls, media_path: Path) -> Optional[np.ndarray]:
        media_path = Path(media_path)
        if not media_path.exists():
            return None

        cmd = [
            "ffmpeg", "-v", "error", "-i", str(media_path),
            "-vn", "-ac", "1", "-ar", "16000", "-f", "s16le", "-",
        ]
        res = subprocess.run(cmd, capture_output=True, check=False)
        if res.returncode != 0 or not res.stdout:
            return None

        mono = np.frombuffer(res.stdout, dtype=np.int16).astype(np.float32) / 32768.0
        if len(mono) < 800:
            return None

        peak = float(np.max(np.abs(mono)))
        if peak < 1e-3:
            return None

        # Active speech frame selection (25ms frames @ 16kHz = 400 samples, hop = 200)
        win = 400
        hop = 200
        frames: List[np.ndarray] = []
        rms_vals: List[float] = []
        for idx in range(0, len(mono) - win + 1, hop):
            seg = mono[idx : idx + win]
            frames.append(seg)
            rms_vals.append(float(np.sqrt(np.mean(seg * seg))))

        if not frames:
            return None

        rms_arr = np.asarray(rms_vals, dtype=np.float32)
        max_rms = float(np.max(rms_arr))
        if max_rms < 1e-3:
            return None

        thresh = max(1e-3, max_rms * 0.18)
        active_chunks = [frames[i] for i in range(len(frames)) if rms_arr[i] >= thresh]
        active = np.concatenate(active_chunks) if active_chunks else mono
        if len(active) < 512:
            active = mono

        nperseg = min(2048, len(active))
        freqs, pxx = signal.welch(active, fs=16000.0, nperseg=nperseg)

        band_powers = np.zeros(16, dtype=np.float64)
        for b in range(16):
            f_lo = float(cls.BAND_EDGES[b])
            f_hi = float(cls.BAND_EDGES[b + 1])
            f_c = float(cls.BAND_CENTERS[b])
            mask = (freqs >= f_lo) & (freqs <= f_hi)
            if np.any(mask):
                band_powers[b] = float(np.mean(pxx[mask]))
            else:
                band_powers[b] = float(np.interp(f_c, freqs, pxx))

        env_db = 10.0 * np.log10(np.maximum(band_powers, 1e-12))
        if float(np.ptp(env_db)) < 1e-3:
            return None

        norm_env = (env_db - float(np.mean(env_db))).astype(np.float32)
        return norm_env

    @classmethod
    def apply_voice_timbre_match(
        cls,
        input_wav: Path,
        target_profile: np.ndarray,
        output_wav: Path,
        strength: float = 0.65,
        voice_converter_cmd: Optional[str] = None,
    ) -> Path:
        input_wav = Path(input_wav)
        output_wav = Path(output_wav)
        output_wav.parent.mkdir(parents=True, exist_ok=True)

        # Optional external STS voice converter hook
        if voice_converter_cmd:
            formatted = voice_converter_cmd.format(
                input=str(input_wav),
                output=str(output_wav),
                input_wav=str(input_wav),
                output_wav=str(output_wav),
            )
            raw_tokens = shlex.split(formatted, posix=False)
            clean_tokens = [
                tok[1:-1] if len(tok) >= 2 and tok[0] == tok[-1] and tok[0] in ('"', "'") else tok
                for tok in raw_tokens
            ]
            ext_res = subprocess.run(clean_tokens, capture_output=True, text=True, check=False)
            if ext_res.returncode == 0 and output_wav.exists() and output_wav.stat().st_size > 200:
                stereo_ext = _load_audio_48k_stereo(output_wav, sr=48000)
                return _write_stereo_wav_48k(output_wav, stereo_ext[:, 0], stereo_ext[:, 1], sr=48000)

        stereo = _load_audio_48k_stereo(input_wav, sr=48000)
        src_profile = cls.extract_voice_profile(input_wav)
        if src_profile is None or target_profile is None or len(target_profile) != 16:
            return _write_stereo_wav_48k(output_wav, stereo[:, 0], stereo[:, 1], sr=48000)

        delta_db = (
            np.asarray(target_profile, dtype=np.float64) - np.asarray(src_profile, dtype=np.float64)
        ) * float(strength)
        delta_db = np.clip(delta_db, -5.0, 5.0)
        band_gains = 10.0 ** (delta_db / 20.0)

        freqs_hz = np.concatenate([[0.0, 50.0], cls.BAND_CENTERS, [9500.0, 24000.0]])
        gains_lin = np.concatenate([[1.0, float(band_gains[0])], band_gains, [float(band_gains[-1]), 1.0]])

        fir_taps = signal.firwin2(129, freqs_hz, gains_lin, fs=48000.0).astype(np.float32)
        out_l = signal.fftconvolve(stereo[:, 0], fir_taps, mode="same").astype(np.float32)
        out_r = signal.fftconvolve(stereo[:, 1], fir_taps, mode="same").astype(np.float32)

        # Match overall RMS softly so spectral shaping does not jump loudness
        in_rms = float(np.sqrt(np.mean(stereo * stereo)))
        out_rms = float(np.sqrt(np.mean(0.5 * (out_l * out_l + out_r * out_r))))
        if in_rms > 1e-4 and out_rms > 1e-4:
            rms_scale = np.clip(in_rms / out_rms, 0.5, 1.8)
            out_l *= float(rms_scale)
            out_r *= float(rms_scale)

        return _write_stereo_wav_48k(output_wav, out_l, out_r, sr=48000)


class CinemaAudioEngine:
    """Cinema Post-Production Audio Engine: Dialogue Cleanup, Ambience, 12-Class Foley & Dynamic Score."""

    VoiceTimbreMatcher = VoiceTimbreMatcher

    FOLEY_RULES: List[Tuple[str, Tuple[str, ...]]] = [
        ("badge_snatch", ("snatch", "rip", "yank", "badge")),
        ("intercom_beep", ("intercom", "pa ")),
        ("metal_clink", ("pin", "ring", "coin", "toss", "drop", "slide", "clink", "counter")),
        ("footsteps", ("walk", "step", "pace", "enter")),
        ("door_latch", ("door", "gate")),
        ("paper_rustle", ("paper", "file", "document", "form", "clipboard")),
        ("chair_shift", ("sit", "stand", "seat", "chair")),
        ("gavel_strike", ("gavel", "sentence", "court")),
        ("phone_tap", ("phone", "smartphone")),
        ("keyboard_type", ("keyboard", "console", "type")),
        ("cup_set", ("cup", "glass", "coffee")),
        ("cloth_movement", ("jacket", "coat", "turn")),
    ]

    VALID_SCORE_MOODS = {
        "tension",
        "investigation",
        "escalation",
        "warm_flashback",
        "emotional_resolution",
        "silence",
    }

    @staticmethod
    def build_dialogue_cleanup_af(
        clip_dur: Optional[float] = None,
        fade_in_s: float = 0.04,
        fade_out_s: float = 0.06,
    ) -> str:
        """
        FFmpeg speech isolation & cleanup filter chain (pure parametric, zero file paths):
        48kHz stereo -> 80Hz highpass -> FFT denoise (-24dB) -> 3kHz presence EQ -> soft compressor + micro fades.
        """
        core = (
            "aformat=sample_rates=48000:channel_layouts=stereo,"
            "highpass=f=80,"
            "afftdn=nf=-24,"
            "equalizer=f=3000:t=q:w=1.2:g=1.8,"
            "equalizer=f=6800:t=q:w=2.0:g=-2.2,"
            "acompressor=threshold=-18dB:ratio=2.5:attack=15:release=180,"
            f"afade=t=in:st=0:d={fade_in_s:.3f}"
        )
        if clip_dur is not None and clip_dur > fade_out_s:
            st_out = max(0.05, float(clip_dur) - fade_out_s)
            return f"{core},afade=t=out:st={st_out:.3f}:d={fade_out_s:.3f}"
        return f"{core},areverse,afade=t=in:st=0:d={fade_out_s:.3f},areverse"

    @staticmethod
    def _find_audio_asset(assets_audio_dir: Optional[Path], subdir: str, name: str) -> Optional[Path]:
        if not assets_audio_dir:
            return None
        base = Path(assets_audio_dir)
        candidates = [
            base / subdir / f"{name}.wav",
            base / subdir / f"{name.lower()}.wav",
            base / f"{name}.wav",
            base / f"{name.lower()}.wav",
        ]
        for cand in candidates:
            if cand.exists() and cand.stat().st_size > 200:
                return cand
        return None

    @staticmethod
    def _classify_location_archetype(loc_id: str) -> str:
        s = (loc_id or "").lower()
        if any(k in s for k in ("cockpit", "flight_deck", "flightdeck")):
            return "cockpit"
        if any(k in s for k in ("jetbridge", "cabin", "galley", "aisle", "aircraft")):
            return "cabin"
        if any(k in s for k in ("concourse", "terminal", "lobby", "gate", "baggage")):
            return "concourse"
        if any(k in s for k in ("precinct", "office", "station", "conference", "boardroom", "hq")):
            return "precinct"
        if any(k in s for k in ("court", "hearing", "chamber")):
            return "courtroom"
        if any(k in s for k in ("ext", "exterior", "tarmac", "runway", "street", "outside", "curb")):
            return "exterior"
        if any(k in s for k in ("home", "house", "living", "kitchen", "bedroom", "apartment")):
            return "home"
        return "cabin"

    @classmethod
    def _synthesize_ambience_segment(cls, archetype: str, n_samples: int, sr: int = 48000, seed: int = 42) -> np.ndarray:
        """Synthesizes stereo (N, 2) acoustically distinct room-tone bed via Butterworth shaping."""
        n = max(1024, n_samples)
        rng = np.random.default_rng(seed)
        w_l = rng.normal(0.0, 1.0, n).astype(np.float32)
        w_r = rng.normal(0.0, 1.0, n).astype(np.float32)
        t = np.arange(n, dtype=np.float32) / sr

        if archetype == "cockpit":
            sos_lo = signal.butter(4, 150.0, btype="low", fs=sr, output="sos")
            sos_av = signal.butter(2, [340.0, 880.0], btype="band", fs=sr, output="sos")
            l = 0.72 * signal.sosfilt(sos_lo, w_l) + 0.22 * signal.sosfilt(sos_av, w_l) + 0.03 * np.sin(2 * np.pi * 400.0 * t)
            r = 0.72 * signal.sosfilt(sos_lo, w_r) + 0.22 * signal.sosfilt(sos_av, w_r) + 0.03 * np.sin(2 * np.pi * 400.0 * t + 0.4)
            target_amp = 0.13
        elif archetype == "cabin":
            sos_air = signal.butter(3, [110.0, 620.0], btype="band", fs=sr, output="sos")
            sos_sub = signal.butter(3, 120.0, btype="low", fs=sr, output="sos")
            l = 0.60 * signal.sosfilt(sos_air, w_l) + 0.40 * signal.sosfilt(sos_sub, w_l)
            r = 0.60 * signal.sosfilt(sos_air, w_r) + 0.40 * signal.sosfilt(sos_sub, w_r)
            target_amp = 0.12
        elif archetype == "concourse":
            sos_hall = signal.butter(2, [260.0, 2100.0], btype="band", fs=sr, output="sos")
            mod = 0.80 + 0.20 * np.sin(2 * np.pi * 0.23 * t)
            l = signal.sosfilt(sos_hall, w_l) * mod
            r = signal.sosfilt(sos_hall, w_r) * (0.80 + 0.20 * np.cos(2 * np.pi * 0.19 * t))
            target_amp = 0.11
        elif archetype == "precinct":
            sos_room = signal.butter(3, [95.0, 460.0], btype="band", fs=sr, output="sos")
            sos_vent = signal.butter(2, [900.0, 1750.0], btype="band", fs=sr, output="sos")
            hum = 0.025 * np.sin(2 * np.pi * 120.0 * t)
            l = 0.75 * signal.sosfilt(sos_room, w_l) + 0.18 * signal.sosfilt(sos_vent, w_l) + hum
            r = 0.75 * signal.sosfilt(sos_room, w_r) + 0.18 * signal.sosfilt(sos_vent, w_r) + hum
            target_amp = 0.09
        elif archetype == "courtroom":
            sos_wood = signal.butter(4, [65.0, 250.0], btype="band", fs=sr, output="sos")
            l = signal.sosfilt(sos_wood, w_l)
            r = signal.sosfilt(sos_wood, w_r)
            target_amp = 0.075
        elif archetype == "exterior":
            sos_wind = signal.butter(2, [160.0, 2800.0], btype="band", fs=sr, output="sos")
            swell = 0.65 + 0.35 * np.sin(2 * np.pi * 0.17 * t + 0.3)
            l = signal.sosfilt(sos_wind, w_l) * swell
            r = signal.sosfilt(sos_wind, w_r) * swell
            target_amp = 0.12
        else:  # home
            sos_home = signal.butter(3, [80.0, 340.0], btype="band", fs=sr, output="sos")
            l = signal.sosfilt(sos_home, w_l)
            r = signal.sosfilt(sos_home, w_r)
            target_amp = 0.08

        stereo = np.stack([l, r], axis=1).astype(np.float32)
        mx = float(np.max(np.abs(stereo))) or 1.0
        return (stereo[:n_samples] / mx) * target_amp

    @classmethod
    def build_scene_ambience_track(
        cls,
        segments: Sequence[Tuple[float, float, str]],
        output_path: Path,
        total_duration_s: Optional[float] = None,
        assets_audio_dir: Optional[Path] = None,
        crossfade_s: float = 0.5,
        sr: int = 48000,
    ) -> Path:
        """
        Builds continuous location-specific stereo ambience track with 0.5s cosine crossfades
        across location changes.
        """
        if not segments:
            dur = total_duration_s or 1.0
            bed = cls._synthesize_ambience_segment("cabin", max(sr, int(math.ceil(dur * sr))), sr=sr)
            return _write_stereo_wav_48k(output_path, bed[:, 0], bed[:, 1], sr=sr)

        # Merge contiguous segments with identical loc_id
        merged: List[Tuple[float, float, str]] = []
        for st_s, dur_s, loc_id in segments:
            st_f = max(0.0, float(st_s))
            en_f = st_f + max(0.1, float(dur_s))
            loc_str = str(loc_id or "LOC_CABIN")
            if merged and merged[-1][2] == loc_str and abs(st_f - merged[-1][1]) < 0.25:
                merged[-1] = (merged[-1][0], max(merged[-1][1], en_f), loc_str)
            else:
                merged.append((st_f, en_f, loc_str))

        end_total = max(merged[-1][1], float(total_duration_s or 0.0))
        merged[-1] = (merged[-1][0], end_total, merged[-1][2])
        if merged[0][0] > 0.0:
            merged[0] = (0.0, merged[0][1], merged[0][2])

        total_n = max(sr, int(round(end_total * sr)))
        master = np.zeros((total_n, 2), dtype=np.float32)
        half_cf_s = max(0.02, float(crossfade_s) * 0.5)

        for idx, (st_s, en_s, loc_str) in enumerate(merged):
            ext_st = st_s - (half_cf_s if idx > 0 else 0.0)
            ext_en = en_s + (half_cf_s if idx < len(merged) - 1 else 0.0)
            i0 = max(0, int(round(ext_st * sr)))
            i1 = min(total_n, int(round(ext_en * sr)))
            seg_len = i1 - i0
            if seg_len <= 0:
                continue

            custom_wav = cls._find_audio_asset(assets_audio_dir, "ambience", loc_str)
            if custom_wav is not None:
                raw_bed = _load_audio_48k_stereo(custom_wav, sr=sr)
                seg_buf = _loop_or_trim_stereo(raw_bed, seg_len)
            else:
                arch = cls._classify_location_archetype(loc_str)
                seg_buf = cls._synthesize_ambience_segment(arch, seg_len, sr=sr, seed=42 + idx * 7)

            env = np.ones(seg_len, dtype=np.float32)
            if idx > 0:
                cf_in = min(seg_len // 2, int(round(crossfade_s * sr)))
                if cf_in > 1:
                    u = np.linspace(0.0, 1.0, cf_in, dtype=np.float32)
                    env[:cf_in] = 0.5 * (1.0 - np.cos(np.pi * u))
            if idx < len(merged) - 1:
                cf_out = min(seg_len // 2, int(round(crossfade_s * sr)))
                if cf_out > 1:
                    u = np.linspace(0.0, 1.0, cf_out, dtype=np.float32)
                    env[-cf_out:] *= 0.5 * (1.0 + np.cos(np.pi * u))

            master[i0:i1] += seg_buf * env[:, None]

        return _write_stereo_wav_48k(output_path, master[:, 0], master[:, 1], sr=sr)

    @classmethod
    def detect_foley_events(
        cls,
        action_or_shots: Union[str, Sequence[Dict[str, Any]]],
        start_s: float = 0.0,
        duration_s: float = 3.0,
    ) -> List[Tuple[float, str]]:
        """
        Detects timestamps and 12 acoustic Foley classes from an action_summary string
        or a list of timeline shot dicts.
        """
        if not isinstance(action_or_shots, str):
            all_events: List[Tuple[float, str]] = []
            for item in action_or_shots:
                act = str(item.get("action_summary") or "")
                st = float(item.get("start_s", item.get("timeline_start_s", 0.0)))
                dur = float(item.get("duration_s", item.get("seg_dur_s", 3.0)))
                all_events.extend(cls.detect_foley_events(act, start_s=st, duration_s=dur))
            return all_events

        act_low = f" {(action_or_shots or '').lower()} "
        matched_kinds: List[str] = []
        for kind, keywords in cls.FOLEY_RULES:
            if kind == "intercom_beep":
                if "intercom" in act_low or re.search(r"\bpa\b", act_low):
                    matched_kinds.append(kind)
            elif any(kw in act_low for kw in keywords):
                matched_kinds.append(kind)

        if not matched_kinds:
            return []

        usable_span = max(0.3, float(duration_s) - 0.45)
        step = usable_span / (len(matched_kinds) + 1)
        events: List[Tuple[float, str]] = []
        for i, kind in enumerate(matched_kinds, start=1):
            t_ev = round(float(start_s) + min(float(duration_s) - 0.15, 0.20 + i * step), 3)
            events.append((t_ev, kind))
        return events

    @staticmethod
    def _synthesize_foley_one(kind: str, sr: int, rng: np.random.Generator) -> np.ndarray:
        """Synthesizes realistic multi-transient filtered burst (mono float32) for each of the 12 Foley classes."""
        if kind == "footsteps":
            ln = int(1.35 * sr)
            out = np.zeros(ln, dtype=np.float32)
            sos_thud = signal.butter(3, [95.0, 360.0], btype="band", fs=sr, output="sos")
            sos_scuff = signal.butter(2, [1100.0, 2900.0], btype="band", fs=sr, output="sos")
            for step_t in (0.0, 0.46, 0.92):
                i0 = int(step_t * sr)
                sl = min(int(0.22 * sr), ln - i0)
                tt = np.arange(sl, dtype=np.float32) / sr
                nz = rng.normal(0.0, 1.0, sl).astype(np.float32)
                hit = (
                    0.75 * signal.sosfilt(sos_thud, nz) * np.exp(-26.0 * tt)
                    + 0.25 * signal.sosfilt(sos_scuff, nz) * np.exp(-38.0 * tt)
                )
                out[i0 : i0 + sl] += hit.astype(np.float32)
            mx = float(np.max(np.abs(out))) or 1.0
            return (out / mx) * 0.22

        if kind == "door_latch":
            ln = int(0.42 * sr)
            tt = np.arange(ln, dtype=np.float32) / sr
            nz = rng.normal(0.0, 1.0, ln).astype(np.float32)
            sos_click = signal.butter(2, [1600.0, 4400.0], btype="band", fs=sr, output="sos")
            sos_body = signal.butter(3, [85.0, 240.0], btype="band", fs=sr, output="sos")
            click1 = signal.sosfilt(sos_click, nz) * np.exp(-55.0 * tt)
            shift = int(0.09 * sr)
            thud = np.zeros(ln, dtype=np.float32)
            thud[shift:] = (signal.sosfilt(sos_body, nz[:-shift]) * np.exp(-18.0 * tt[:-shift])).astype(np.float32)
            out = 0.55 * click1 + 0.70 * thud
            mx = float(np.max(np.abs(out))) or 1.0
            return (out.astype(np.float32) / mx) * 0.24

        if kind == "paper_rustle":
            ln = int(0.48 * sr)
            tt = np.arange(ln, dtype=np.float32) / sr
            nz = rng.normal(0.0, 1.0, ln).astype(np.float32)
            sos = signal.butter(2, [1800.0, 6800.0], btype="band", fs=sr, output="sos")
            flutter = np.abs(np.sin(2 * np.pi * 7.5 * tt)) * np.sin(np.pi * tt / 0.48)
            out = signal.sosfilt(sos, nz) * flutter
            mx = float(np.max(np.abs(out))) or 1.0
            return (out.astype(np.float32) / mx) * 0.16

        if kind == "chair_shift":
            ln = int(0.45 * sr)
            tt = np.arange(ln, dtype=np.float32) / sr
            nz = rng.normal(0.0, 1.0, ln).astype(np.float32)
            sos = signal.butter(3, [130.0, 620.0], btype="band", fs=sr, output="sos")
            creak = 0.35 * np.sin(2 * np.pi * (240.0 - 70.0 * tt) * tt) * np.exp(-8.0 * tt)
            out = signal.sosfilt(sos, nz) * np.exp(-9.0 * tt) + creak
            mx = float(np.max(np.abs(out))) or 1.0
            return (out.astype(np.float32) / mx) * 0.18

        if kind == "gavel_strike":
            ln = int(0.55 * sr)
            tt = np.arange(ln, dtype=np.float32) / sr
            nz = rng.normal(0.0, 1.0, ln).astype(np.float32)
            sos_wood = signal.butter(3, [220.0, 980.0], btype="band", fs=sr, output="sos")
            crack = (
                0.65 * np.sin(2 * np.pi * 390.0 * tt) * np.exp(-24.0 * tt)
                + 0.45 * np.sin(2 * np.pi * 1180.0 * tt) * np.exp(-42.0 * tt)
                + 0.55 * signal.sosfilt(sos_wood, nz) * np.exp(-16.0 * tt)
            )
            mx = float(np.max(np.abs(crack))) or 1.0
            return (crack.astype(np.float32) / mx) * 0.30

        if kind == "phone_tap":
            ln = int(0.14 * sr)
            tt = np.arange(ln, dtype=np.float32) / sr
            nz = rng.normal(0.0, 1.0, ln).astype(np.float32)
            sos = signal.butter(2, [1700.0, 5200.0], btype="band", fs=sr, output="sos")
            tap = signal.sosfilt(sos, nz) * np.exp(-85.0 * tt) + 0.35 * np.sin(2 * np.pi * 2400.0 * tt) * np.exp(-95.0 * tt)
            mx = float(np.max(np.abs(tap))) or 1.0
            return (tap.astype(np.float32) / mx) * 0.15

        if kind == "keyboard_type":
            ln = int(0.52 * sr)
            out = np.zeros(ln, dtype=np.float32)
            sos = signal.butter(2, [1600.0, 5600.0], btype="band", fs=sr, output="sos")
            for kt in (0.0, 0.09, 0.19, 0.27, 0.38):
                i0 = int(kt * sr)
                kl = min(int(0.06 * sr), ln - i0)
                tt = np.arange(kl, dtype=np.float32) / sr
                nz = rng.normal(0.0, 1.0, kl).astype(np.float32)
                out[i0 : i0 + kl] += (signal.sosfilt(sos, nz) * np.exp(-90.0 * tt)).astype(np.float32)
            mx = float(np.max(np.abs(out))) or 1.0
            return (out / mx) * 0.16

        if kind == "cup_set":
            ln = int(0.34 * sr)
            tt = np.arange(ln, dtype=np.float32) / sr
            ceramic = (
                0.55 * np.sin(2 * np.pi * 680.0 * tt) * np.exp(-26.0 * tt)
                + 0.40 * np.sin(2 * np.pi * 2180.0 * tt) * np.exp(-38.0 * tt)
                + 0.35 * np.sin(2 * np.pi * 155.0 * tt) * np.exp(-32.0 * tt)
            )
            mx = float(np.max(np.abs(ceramic))) or 1.0
            return (ceramic.astype(np.float32) / mx) * 0.19

        if kind == "cloth_movement":
            ln = int(0.36 * sr)
            tt = np.arange(ln, dtype=np.float32) / sr
            nz = rng.normal(0.0, 1.0, ln).astype(np.float32)
            sos = signal.butter(2, [700.0, 3600.0], btype="band", fs=sr, output="sos")
            env = np.sin(np.pi * tt / 0.36) ** 1.5
            swish = signal.sosfilt(sos, nz) * env
            mx = float(np.max(np.abs(swish))) or 1.0
            return (swish.astype(np.float32) / mx) * 0.15

        if kind == "metal_clink":
            ln = int(0.45 * sr)
            tt = np.arange(ln, dtype=np.float32) / sr
            burst = (
                0.50 * np.sin(2 * np.pi * 2450.0 * tt) * np.exp(-18.0 * tt)
                + 0.35 * np.sin(2 * np.pi * 3890.0 * tt) * np.exp(-24.0 * tt)
                + 0.20 * np.sin(2 * np.pi * 5620.0 * tt) * np.exp(-32.0 * tt)
            )
            mx = float(np.max(np.abs(burst))) or 1.0
            return (burst.astype(np.float32) / mx) * 0.22

        if kind == "intercom_beep":
            ln = int(0.48 * sr)
            out = np.zeros(ln, dtype=np.float32)
            half = ln // 2
            t1 = np.arange(half, dtype=np.float32) / sr
            t2 = np.arange(ln - half, dtype=np.float32) / sr
            out[:half] = np.sin(2 * np.pi * 1320.0 * t1) * np.exp(-6.5 * t1)
            out[half:] = np.sin(2 * np.pi * 1046.5 * t2) * np.exp(-6.5 * t2)
            mx = float(np.max(np.abs(out))) or 1.0
            return (out / mx) * 0.18

        # badge_snatch (and fallback)
        ln = int(0.30 * sr)
        tt = np.arange(ln, dtype=np.float32) / sr
        nz = rng.normal(0.0, 1.0, ln).astype(np.float32)
        sos = signal.butter(2, [950.0, 5400.0], btype="band", fs=sr, output="sos")
        snap = signal.sosfilt(sos, nz) * np.exp(-18.0 * tt)
        mx = float(np.max(np.abs(snap))) or 1.0
        return (snap.astype(np.float32) / mx) * 0.21

    @classmethod
    def build_foley_track(
        cls,
        duration_s: float,
        events: Sequence[Tuple[float, str]],
        output_path: Path,
        assets_audio_dir: Optional[Path] = None,
        sr: int = 48000,
    ) -> Path:
        n = max(sr, int(math.ceil(float(duration_s) * sr)))
        track = np.zeros((n, 2), dtype=np.float32)
        rng = np.random.default_rng(17)

        for t_sec, kind in events:
            idx0 = int(max(0.0, float(t_sec)) * sr)
            if idx0 >= n:
                continue
            custom_wav = cls._find_audio_asset(assets_audio_dir, "foley", kind)
            if custom_wav is not None:
                clip_st = _load_audio_48k_stereo(custom_wav, sr=sr)
            else:
                mono = cls._synthesize_foley_one(kind, sr=sr, rng=rng)
                pan = float(rng.uniform(0.88, 1.0))
                clip_st = np.stack([mono * pan, mono * (2.0 - pan)], axis=1).astype(np.float32)

            ln = min(len(clip_st), n - idx0)
            if ln > 0:
                track[idx0 : idx0 + ln] += clip_st[:ln]

        return _write_stereo_wav_48k(output_path, track[:, 0], track[:, 1], sr=sr)

    @classmethod
    def infer_segment_mood(cls, shot: Dict[str, Any], default_mood: str = "tension") -> str:
        explicit = str(shot.get("score_mood") or shot.get("bgm_mood") or shot.get("mood") or "").strip().lower()
        if explicit in cls.VALID_SCORE_MOODS:
            return explicit
        if shot.get("is_silence") or shot.get("silent_score"):
            return "silence"
        if shot.get("is_flashback"):
            return "warm_flashback"

        txt = " ".join(
            str(shot.get(k) or "") for k in ("action_summary", "dialogue", "narration", "chapter_id")
        ).lower()
        if any(w in txt for w in ("sentence", "verdict", "applaud", "justice", "touchdown", "resolv", "honor")):
            return "emotional_resolution"
        if any(w in txt for w in ("snatch", "arrest", "yank", "security", "confront", "escalat", "refuse")):
            return "escalation"
        if any(w in txt for w in ("investigat", "audit", "faa", "evidence", "review", "file", "inspect")):
            return "investigation"
        if shot.get("is_climax_closeup"):
            return "escalation"
        return default_mood if default_mood in cls.VALID_SCORE_MOODS else "tension"

    @staticmethod
    def _synthesize_score_segment(mood: str, n_samples: int, sr: int = 48000) -> np.ndarray:
        """Synthesizes evolving multi-chord harmonic progression + pulse per mood."""
        if mood == "silence" or n_samples <= 0:
            return np.zeros((max(0, n_samples), 2), dtype=np.float32)

        progressions: Dict[str, Tuple[List[Tuple[float, ...]], float, float]] = {
            # (4 chords in Hz, pulse_hz, target_amp)
            "tension": (
                [(73.42, 110.00, 146.83, 174.61), (58.27, 116.54, 146.83, 196.00),
                 (98.00, 146.83, 174.61, 220.00), (55.00, 110.00, 146.83, 164.81)],
                1.0,
                0.22,
            ),
            "investigation": (
                [(110.00, 164.81, 220.00, 246.94), (87.31, 130.81, 174.61, 220.00),
                 (73.42, 110.00, 174.61, 261.63), (82.41, 123.47, 164.81, 220.00)],
                1.5,
                0.20,
            ),
            "escalation": (
                [(65.41, 98.00, 130.81, 155.56), (103.83, 155.56, 207.65, 261.63),
                 (87.31, 130.81, 174.61, 207.65), (98.00, 146.83, 196.00, 246.94)],
                1.85,
                0.25,
            ),
            "warm_flashback": (
                [(87.31, 130.81, 174.61, 220.00), (82.41, 130.81, 196.00, 261.63),
                 (73.42, 110.00, 174.61, 220.00), (116.54, 174.61, 220.00, 293.66)],
                0.35,
                0.20,
            ),
            "emotional_resolution": (
                [(73.42, 110.00, 146.83, 185.00), (110.00, 164.81, 220.00, 293.66),
                 (123.47, 185.00, 220.00, 293.66), (98.00, 146.83, 196.00, 246.94)],
                0.55,
                0.22,
            ),
        }
        chords, pulse_hz, target_amp = progressions.get(mood, progressions["tension"])

        n = n_samples
        out_l = np.zeros(n, dtype=np.float32)
        out_r = np.zeros(n, dtype=np.float32)

        # Split segment across chords (approx 2.2s per chord, minimum 2 chords if >= 1.6s)
        chord_len = max(int(1.1 * sr), min(int(2.4 * sr), max(1, n // 2)))
        xf = min(int(0.35 * sr), chord_len // 3)
        pos = 0
        c_idx = 0
        while pos < n:
            i0 = max(0, pos - (xf if c_idx > 0 else 0))
            i1 = min(n, pos + chord_len)
            ln = i1 - i0
            if ln <= 0:
                break
            tt = np.arange(i0, i1, dtype=np.float32) / sr
            notes = chords[c_idx % len(chords)]

            seg_l = np.zeros(ln, dtype=np.float32)
            seg_r = np.zeros(ln, dtype=np.float32)
            weights = (0.44, 0.28, 0.18, 0.10)
            for n_idx, (w_note, f_hz) in enumerate(zip(weights, notes)):
                # Analog cello/synth-pad harmonic stack (sub-octave root + warm 2nd & 3rd harmonics + stereo chorus detune)
                sub_oct = 0.24 * np.sin(2 * np.pi * (f_hz * 0.5) * tt) if n_idx == 0 else 0.0
                seg_l += w_note * (
                    sub_oct
                    + np.sin(2 * np.pi * f_hz * tt)
                    + 0.26 * np.sin(2 * np.pi * (f_hz * 2.0) * tt + 0.3)
                    + 0.11 * np.sin(2 * np.pi * (f_hz * 3.0) * tt + 0.7)
                )
                seg_r += w_note * (
                    sub_oct
                    + np.sin(2 * np.pi * (f_hz * 1.0025) * tt + 0.2)
                    + 0.26 * np.sin(2 * np.pi * (f_hz * 1.9975) * tt + 0.6)
                    + 0.11 * np.sin(2 * np.pi * (f_hz * 3.003) * tt + 1.1)
                )

            pulse = 0.78 + 0.22 * (0.5 + 0.5 * np.sin(2 * np.pi * pulse_hz * tt))
            seg_l *= pulse
            seg_r *= pulse

            c_env = np.ones(ln, dtype=np.float32)
            if c_idx > 0 and xf > 1 and ln > xf:
                u = np.linspace(0.0, 1.0, xf, dtype=np.float32)
                c_env[:xf] = 0.5 * (1.0 - np.cos(np.pi * u))
            if i1 < n and xf > 1 and ln > xf:
                u = np.linspace(0.0, 1.0, xf, dtype=np.float32)
                c_env[-xf:] *= 0.5 * (1.0 + np.cos(np.pi * u))

            out_l[i0:i1] += seg_l * c_env
            out_r[i0:i1] += seg_r * c_env
            pos += chord_len - xf if xf > 1 else chord_len
            c_idx += 1

        # Warm Butterworth low-pass shaping (1650 Hz) for velvety cinema pad timbre
        if n >= 64:
            sos_warm = signal.butter(2, 1650.0, btype="low", fs=sr, output="sos")
            out_l = signal.sosfilt(sos_warm, out_l).astype(np.float32)
            out_r = signal.sosfilt(sos_warm, out_r).astype(np.float32)

        stereo = np.stack([out_l, out_r], axis=1)
        mx = float(np.max(np.abs(stereo))) or 1.0
        return (stereo / mx) * target_amp

    @classmethod
    def build_dynamic_score_track(
        cls,
        segments: Sequence[Tuple[float, float, str]],
        output_path: Path,
        total_duration_s: Optional[float] = None,
        assets_audio_dir: Optional[Path] = None,
        crossfade_s: float = 1.0,
        sr: int = 48000,
    ) -> Path:
        """
        Builds chapter-mood dynamic musical score track with 1.0s cosine crossfades.
        """
        if not segments:
            dur = total_duration_s or 1.0
            buf = cls._synthesize_score_segment("tension", max(sr, int(math.ceil(dur * sr))), sr=sr)
            return _write_stereo_wav_48k(output_path, buf[:, 0], buf[:, 1], sr=sr)

        merged: List[Tuple[float, float, str]] = []
        for st_s, dur_s, mood in segments:
            st_f = max(0.0, float(st_s))
            en_f = st_f + max(0.1, float(dur_s))
            m_str = str(mood or "tension").lower()
            if m_str not in cls.VALID_SCORE_MOODS:
                m_str = "tension"
            if merged and merged[-1][2] == m_str and abs(st_f - merged[-1][1]) < 0.25:
                merged[-1] = (merged[-1][0], max(merged[-1][1], en_f), m_str)
            else:
                merged.append((st_f, en_f, m_str))

        end_total = max(merged[-1][1], float(total_duration_s or 0.0))
        merged[-1] = (merged[-1][0], end_total, merged[-1][2])
        if merged[0][0] > 0.0:
            merged[0] = (0.0, merged[0][1], merged[0][2])

        total_n = max(sr, int(round(end_total * sr)))
        master = np.zeros((total_n, 2), dtype=np.float32)
        half_cf_s = max(0.05, float(crossfade_s) * 0.5)

        for idx, (st_s, en_s, m_str) in enumerate(merged):
            if m_str == "silence":
                continue
            # Do not bleed past silence start beyond half_cf_s so silence settles cleanly
            ext_st = st_s - (half_cf_s if idx > 0 else 0.0)
            ext_en = en_s + (half_cf_s if idx < len(merged) - 1 else 0.0)
            i0 = max(0, int(round(ext_st * sr)))
            i1 = min(total_n, int(round(ext_en * sr)))
            seg_len = i1 - i0
            if seg_len <= 0:
                continue

            custom_wav = cls._find_audio_asset(assets_audio_dir, "bgm", m_str)
            if custom_wav is not None:
                raw_bgm = _load_audio_48k_stereo(custom_wav, sr=sr)
                seg_buf = _loop_or_trim_stereo(raw_bgm, seg_len)
            else:
                seg_buf = cls._synthesize_score_segment(m_str, seg_len, sr=sr)

            env = np.ones(seg_len, dtype=np.float32)
            fade_in_len = min(seg_len // 2, int(round((crossfade_s if idx > 0 else 0.6) * sr)))
            if fade_in_len > 1:
                u = np.linspace(0.0, 1.0, fade_in_len, dtype=np.float32)
                env[:fade_in_len] = 0.5 * (1.0 - np.cos(np.pi * u))

            fade_out_len = min(seg_len // 2, int(round((crossfade_s if idx < len(merged) - 1 else 0.8) * sr)))
            if fade_out_len > 1:
                u = np.linspace(0.0, 1.0, fade_out_len, dtype=np.float32)
                env[-fade_out_len:] *= 0.5 * (1.0 + np.cos(np.pi * u))

            master[i0:i1] += seg_buf * env[:, None]

        return _write_stereo_wav_48k(output_path, master[:, 0], master[:, 1], sr=sr)

    @classmethod
    def build_dialogue_stem_with_jl_cuts(
        cls,
        dialogue_segments: Sequence[Dict[str, Any]],
        total_duration_s: float,
        output_wav: Path,
        enable_j_l_cuts: bool = True,
        sr: int = 48000,
    ) -> Path:
        """
        Assembles sample-accurate 48kHz stereo dialogue stem locked to video timestamps
        (zero cumulative drift), with J-cut pre-lap and L-cut tail cosine cross-blends.
        Each item in dialogue_segments:
          {"wav_path": Path, "start_s": float, "duration_s": float,
           "pre_lap_wav": Optional[Path], "post_lap_wav": Optional[Path]}
        """
        total_n = max(sr, int(round(float(total_duration_s) * sr)))
        stem = np.zeros((total_n, 2), dtype=np.float32)

        for seg in dialogue_segments:
            wav_p = seg.get("wav_path")
            if not wav_p or not Path(wav_p).exists():
                continue
            st_s = float(seg["start_s"])
            dur_s = float(seg["duration_s"])
            buf = _load_audio_48k_stereo(Path(wav_p), sr=sr)
            i0 = max(0, int(round(st_s * sr)))
            target_len = min(total_n - i0, int(round(dur_s * sr)), len(buf))
            if target_len <= 0:
                continue

            chunk = buf[:target_len].copy()
            # Smooth micro cosine edges so cuts never click; overlap J/L extensions when available
            edge_n = min(target_len // 4, int(round((0.08 if enable_j_l_cuts else 0.03) * sr)))
            if edge_n > 2:
                u = np.linspace(0.0, 1.0, edge_n, dtype=np.float32)[:, None]
                chunk[:edge_n] *= 0.5 * (1.0 - np.cos(np.pi * u))
                chunk[-edge_n:] *= 0.5 * (1.0 + np.cos(np.pi * u))

            stem[i0 : i0 + target_len] += chunk

            if enable_j_l_cuts:
                pre_p = seg.get("pre_lap_wav")
                if pre_p and Path(pre_p).exists():
                    pre_buf = _load_audio_48k_stereo(Path(pre_p), sr=sr)
                    pre_len = min(len(pre_buf), i0, int(0.26 * sr))
                    if pre_len > 16:
                        u = np.linspace(0.0, 1.0, pre_len, dtype=np.float32)[:, None]
                        stem[i0 - pre_len : i0] += pre_buf[-pre_len:] * (0.45 * (0.5 * (1.0 - np.cos(np.pi * u))))

                post_p = seg.get("post_lap_wav")
                if post_p and Path(post_p).exists():
                    post_buf = _load_audio_48k_stereo(Path(post_p), sr=sr)
                    end_i = i0 + target_len
                    post_len = min(len(post_buf), total_n - end_i, int(0.26 * sr))
                    if post_len > 16:
                        u = np.linspace(0.0, 1.0, post_len, dtype=np.float32)[:, None]
                        stem[end_i : end_i + post_len] += post_buf[:post_len] * (0.45 * (0.5 * (1.0 + np.cos(np.pi * u))))

        return _write_stereo_wav_48k(output_wav, stem[:, 0], stem[:, 1], sr=sr)
