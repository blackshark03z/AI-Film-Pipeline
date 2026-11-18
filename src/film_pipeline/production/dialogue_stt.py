"""Advisory word-level dialogue check: did the generated actors say the scripted line? (Vosk + offline faster-whisper, never blocks)."""
from __future__ import annotations

import difflib
import json
import os
import re
import subprocess
import wave
from pathlib import Path
from typing import Callable

from film_pipeline.production.runtime import atomic_json

PASS_RECALL = 0.8
ENGINE = "vosk-small-en-us-0.15"
ROOT = Path(__file__).resolve().parents[3]
HELPER = ROOT / "tools" / "stt_vosk.py"
_INLINE_VOSK_SCRIPT = """from concurrent.futures import ThreadPoolExecutor
import json, os, subprocess, sys, vosk
raw_spans = sys.stdin.read() if sys.argv[3] == "-" else sys.argv[3]
model_dir, wav, spans = sys.argv[1], sys.argv[2], json.loads(raw_spans)
if not spans:
    print("[]")
    raise SystemExit(0)
vosk.SetLogLevel(-1)
model = vosk.Model(model_dir)
min_a = max(0.0, min(float(a) for a, _ in spans))
max_b = max(max(float(b), float(a) + 0.1) for a, b in spans)
pcm_all = subprocess.run(
    ["ffmpeg", "-v", "error", "-ss", f"{min_a:.6f}", "-t", f"{max(max_b - min_a, 0.1):.6f}", "-i", wav,
     "-ac", "1", "-ar", "16000", "-f", "s16le", "-"],
    capture_output=True, check=True, timeout=300).stdout
def _run_batch(batch):
    rec = vosk.KaldiRecognizer(model, 16000)
    res = []
    for idx, (a, b) in batch:
        a_f, b_f = max(0.0, float(a)), float(b)
        s0 = max(0, int(round((a_f - min_a) * 16000))) * 2
        s1 = max(s0 + 3200, int(round((max(b_f, a_f + 0.1) - min_a) * 16000)) * 2)
        rec.AcceptWaveform(pcm_all[s0:s1])
        res.append((idx, json.loads(rec.FinalResult()).get("text", "")))
        rec.Reset()
    return res
indexed = list(enumerate(spans))
workers = min(len(indexed), max(1, min(6, (os.cpu_count() or 4) // 2)))
if workers <= 1:
    ordered = _run_batch(indexed)
else:
    batches = [indexed[i::workers] for i in range(workers)]
    with ThreadPoolExecutor(max_workers=workers) as pool:
        parts = list(pool.map(_run_batch, batches))
    ordered = sorted(item for part in parts for item in part)
print(json.dumps([txt for _, txt in ordered]))
"""
_INLINE_WHISPER_SCRIPT = """import io, json, subprocess, sys, wave
from faster_whisper import WhisperModel
raw_spans = sys.stdin.read() if sys.argv[3] == "-" else sys.argv[3]
model_dir, wav, spans = sys.argv[1], sys.argv[2], json.loads(raw_spans)
if not spans:
    print("[]")
    raise SystemExit(0)
min_a = max(0.0, min(float(a) for a, _ in spans))
max_b = max(max(float(b), float(a) + 0.1) for a, b in spans)
pcm_all = subprocess.run(
    ["ffmpeg", "-v", "error", "-ss", f"{min_a:.6f}", "-t", f"{max(max_b - min_a, 0.1):.6f}", "-i", wav,
     "-ac", "1", "-ar", "16000", "-f", "s16le", "-"],
    capture_output=True, check=True, timeout=300).stdout
model = WhisperModel(model_dir, device="cpu", compute_type="int8", local_files_only=True)
out = []
for a, b in spans:
    a_f, b_f = max(0.0, float(a)), float(b)
    s0 = max(0, int(round((a_f - min_a) * 16000))) * 2
    s1 = max(s0 + 3200, int(round((max(b_f, a_f + 0.1) - min_a) * 16000)) * 2)
    buf = io.BytesIO()
    with wave.open(buf, "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(16000)
        wf.writeframes(pcm_all[s0:s1])
    buf.seek(0)
    segs, _ = model.transcribe(buf, language="en", beam_size=2, vad_filter=False)
    out.append(" ".join(s.text.strip() for s in segs).strip())
print(json.dumps(out))
"""
_HOMOPHONES = [{"to", "too", "two"}, {"fare", "fair"}, {"for", "four"}, {"there", "their"}, {"here", "hear"},
               {"right", "write"}, {"no", "know"}, {"ate", "eight"}, {"one", "won"}]


def normalize(text: str) -> list[str]:
    text = text.lower().replace("'", "").replace("’", "").replace("-", " ")
    return [w for w in re.split(r"[^a-z0-9]+", text) if w]


def _same(a: str, b: str) -> bool:
    if a == b or any(a in g and b in g for g in _HOMOPHONES):
        return True
    return difflib.SequenceMatcher(None, a, b).ratio() >= 0.75


def score_line(expected: str, heard: str) -> dict:
    exp, pool = normalize(expected), normalize(heard)
    missing = []
    for w in exp:
        hit = next((i for i, h in enumerate(pool) if _same(w, h)), None)
        if hit is None:
            missing.append(w)
        else:
            pool.pop(hit)
    recall = (len(exp) - len(missing)) / len(exp) if exp else 1.0
    return {"recall": round(recall, 3), "missing": missing}


def _model_dir() -> Path:
    return Path(os.environ.get("AFP_VOSK_MODEL") or Path.home() / ".cache" / "vosk" / "vosk-model-small-en-us-0.15")


def _cached_whisper_model() -> tuple[str, Path] | None:
    explicit = os.environ.get("AFP_WHISPER_MODEL", "").strip()
    if explicit:
        p = Path(explicit)
        if (p / "model.bin").is_file():
            return p.name, p
    hub = Path.home() / ".cache" / "huggingface" / "hub"
    for name in ("small.en", "base.en", "base"):
        snaps = hub / f"models--Systran--faster-whisper-{name}" / "snapshots"
        if not snaps.is_dir():
            continue
        for cand in sorted(snaps.iterdir(), reverse=True):
            if (cand / "model.bin").is_file():
                return f"faster-whisper-{name}", cand
    return None


_PROBED_PYTHONS: dict[str, str | None] = {}


def _stt_python(module: str = "vosk") -> str | None:
    import shutil
    env_py = os.environ.get("AFP_STT_PYTHON", "").strip()
    if env_py:
        return env_py
    if module in _PROBED_PYTHONS:
        return _PROBED_PYTHONS[module]
    candidates = [shutil.which("python"), shutil.which("python3")]
    win_py = Path.home() / "AppData" / "Local" / "Programs" / "Python" / "Python311" / "python.exe"
    if win_py.is_file():
        candidates.append(str(win_py))
    seen: set[str] = set()
    for cand in candidates:
        if not cand:
            continue
        norm = str(Path(cand))
        if norm in seen:
            continue
        seen.add(norm)
        try:
            ok = subprocess.run([cand, "-c", f"import {module}"], capture_output=True, timeout=15).returncode == 0
            if ok:
                _PROBED_PYTHONS[module] = cand
                return cand
        except (OSError, subprocess.TimeoutExpired):
            continue
    _PROBED_PYTHONS[module] = None
    return None


def decode_mono_16k_pcm(media: Path, *, start_s: float = 0.0, duration_s: float | None = None,
                        timeout_s: float = 300.0) -> bytes:
    """Decode audio once to 16 kHz mono s16le PCM bytes (fast pure-Python path for 16 kHz mono WAV, else 1 FFmpeg pass)."""
    media = Path(media)
    if media.suffix.lower() == ".wav":
        try:
            with wave.open(str(media), "rb") as wf:
                if wf.getnchannels() == 1 and wf.getsampwidth() == 2 and wf.getframerate() == 16000 and wf.getcomptype() == "NONE":
                    f0 = max(0, int(round(start_s * 16000)))
                    wf.setpos(min(f0, wf.getnframes()))
                    n_frames = wf.getnframes() - f0 if duration_s is None else max(1600, int(round(duration_s * 16000)))
                    return wf.readframes(n_frames)
        except (wave.Error, OSError, EOFError):
            pass
    cmd = ["ffmpeg", "-v", "error"]
    if start_s > 0:
        cmd += ["-ss", f"{start_s:.6f}"]
    if duration_s is not None:
        cmd += ["-t", f"{max(duration_s, 0.1):.6f}"]
    cmd += ["-i", str(media), "-ac", "1", "-ar", "16000", "-f", "s16le", "-"]
    return subprocess.run(cmd, capture_output=True, check=True, timeout=timeout_s).stdout


def slice_pcm_16k(pcm: bytes, base_s: float, a: float, b: float) -> bytes:
    a_f = max(0.0, float(a))
    b_f = max(a_f + 0.1, float(b))
    s0 = max(0, int(round((a_f - base_s) * 16000))) * 2
    s1 = max(s0 + 3200, int(round((b_f - base_s) * 16000)) * 2)
    return pcm[s0:s1]


def transcribe(wav: Path, spans: list[list[float]]) -> list[str] | None:
    if not spans:
        return []
    model = _model_dir()
    if not model.is_dir():
        return None
    try:
        import vosk  # type: ignore
    except ImportError:
        vosk = None
    try:
        if vosk is not None:
            from concurrent.futures import ThreadPoolExecutor
            vosk.SetLogLevel(-1)
            m = vosk.Model(str(model))
            min_a = max(0.0, min(float(a) for a, _ in spans))
            max_b = max(max(float(b), float(a) + 0.1) for a, b in spans)
            pcm_all = decode_mono_16k_pcm(Path(wav), start_s=min_a, duration_s=max_b - min_a)

            def _batch_fn(batch: list[tuple[int, list[float]]]) -> list[tuple[int, str]]:
                rec = vosk.KaldiRecognizer(m, 16000)
                res: list[tuple[int, str]] = []
                for idx, (a, b) in batch:
                    rec.AcceptWaveform(slice_pcm_16k(pcm_all, min_a, a, b))
                    res.append((idx, json.loads(rec.FinalResult()).get("text", "")))
                    rec.Reset()
                return res

            indexed = list(enumerate(spans))
            workers = min(len(indexed), max(1, min(6, (os.cpu_count() or 4) // 2)))
            if workers <= 1:
                ordered = _batch_fn(indexed)
            else:
                batches = [indexed[i::workers] for i in range(workers)]
                with ThreadPoolExecutor(max_workers=workers) as pool:
                    parts = list(pool.map(_batch_fn, batches))
                ordered = sorted(item for part in parts for item in part)
            return [txt for _, txt in ordered]
        py = _stt_python("vosk")
        if not py:
            return None
        spans_json = json.dumps([[round(float(a), 3), round(float(b), 3)] for a, b in spans])
        cmd = [py, str(HELPER), str(model), str(wav), "-"] if HELPER.is_file() else [
            py, "-c", _INLINE_VOSK_SCRIPT, str(model), str(wav), "-"
        ]
        res = subprocess.run(cmd, input=spans_json, capture_output=True, text=True, check=True, timeout=300)
        out = json.loads(res.stdout)
        return out if isinstance(out, list) and len(out) == len(spans) else None
    except (OSError, subprocess.CalledProcessError, subprocess.TimeoutExpired, ValueError):
        return None


def transcribe_whisper(wav: Path, spans: list[list[float]]) -> tuple[str, list[str]] | None:
    """Offline cached faster-whisper transcription (local_files_only=True; zero network access)."""
    found = _cached_whisper_model()
    if found is None:
        return None
    engine_name, snap_dir = found
    if not spans:
        return engine_name, []
    try:
        import io
        from faster_whisper import WhisperModel  # type: ignore
    except ImportError:
        WhisperModel = None
    try:
        if WhisperModel is not None:
            min_a = max(0.0, min(float(a) for a, _ in spans))
            max_b = max(max(float(b), float(a) + 0.1) for a, b in spans)
            pcm_all = decode_mono_16k_pcm(Path(wav), start_s=min_a, duration_s=max_b - min_a)
            model = WhisperModel(str(snap_dir), device="cpu", compute_type="int8", local_files_only=True)
            out: list[str] = []
            for a, b in spans:
                buf = io.BytesIO()
                with wave.open(buf, "wb") as wf:
                    wf.setnchannels(1)
                    wf.setsampwidth(2)
                    wf.setframerate(16000)
                    wf.writeframes(slice_pcm_16k(pcm_all, min_a, a, b))
                buf.seek(0)
                segs, _ = model.transcribe(buf, language="en", beam_size=2, vad_filter=False)
                out.append(" ".join(s.text.strip() for s in segs).strip())
            return engine_name, out
        py = _stt_python("faster_whisper")
        if not py:
            return None
        spans_json = json.dumps([[round(float(a), 3), round(float(b), 3)] for a, b in spans])
        res = subprocess.run(
            [py, "-c", _INLINE_WHISPER_SCRIPT, str(snap_dir), str(wav), "-"],
            input=spans_json, capture_output=True, text=True, check=True, timeout=600,
        )
        out = json.loads(res.stdout)
        return (engine_name, out) if isinstance(out, list) and len(out) == len(spans) else None
    except (OSError, subprocess.CalledProcessError, subprocess.TimeoutExpired, ValueError):
        return None


def _stem(root: Path) -> Path | None:
    mix = root / "audio" / "mix.json"
    if not mix.is_file():
        return None
    raw = (json.loads(mix.read_text(encoding="utf-8")).get("stems") or {}).get("dialogue")
    if not raw:
        return None
    p = Path(str(raw).replace("\\", "/"))
    if not p.is_absolute():
        cand = root / p
        if cand.is_file():
            p = cand
        elif not p.is_file():
            p = ROOT / p
    return p if p.is_file() else None


TAKE_PAD_S = 1.0


def _take_source(pkg, event_id: str | None) -> tuple[Path, float] | None:
    """(the take's own clip, its in-point in the cut) for an EDL event: the raw take has no music or ambience under it."""
    section = pkg.typed.get("edit")
    event = next((e for e in getattr(section, "events", []) if e.event_id == event_id and e.kind == "TAKE"), None)
    if event is None:
        return None
    try:
        from film_pipeline.production import takes as T
        entry = T.load_log(Path(pkg.root), pkg.header.film_id).get(event.take_id)
    except (KeyError, ValueError, OSError):
        return None
    clip = Path(pkg.root) / "media" / "takes" / Path(entry.output_file).name
    return (clip, event.src_in_s) if clip.is_file() else None


def check(pkg, *, transcriber: Callable | None = None, pad_s: float = 0.4,
          engine_mode: str | None = None) -> dict:
    root = Path(pkg.root)
    mode = (engine_mode or os.environ.get("AFP_STT_ENGINE") or "auto").strip().lower()
    cues: list[dict] = []
    titles = root / "titles" / "titles.json"
    if titles.is_file():
        cues = json.loads(titles.read_text(encoding="utf-8")).get("cues") or []
    wav = _stem(root)
    rows: list[dict] = []
    problems: list[dict] = []
    engine: str | None = None
    heard_all: list[str] | None = None
    active_fn: Callable[[Path, list[list[float]]], list[str] | None] = transcriber or transcribe
    if pkg.header.language != "en":
        why = f"language {pkg.header.language!r} unsupported"
    elif wav is None:
        why = "no dialogue stem"
    elif not cues:
        why = "no cues"
    else:
        spans = [[max(0.0, c["abs_start_s"] - pad_s), c["abs_end_s"] + pad_s] for c in cues]
        why = "no STT backend available"
        if transcriber is not None:
            heard_all = transcriber(wav, spans)
            if heard_all is not None:
                engine = ENGINE
        elif mode == "faster-whisper":
            w_res = transcribe_whisper(wav, spans)
            if w_res is not None:
                engine, heard_all = w_res
                active_fn = lambda p, sp: (transcribe_whisper(p, sp) or (None, None))[1]  # noqa: E731
        else:
            heard_all = transcribe(wav, spans)
            if heard_all is not None:
                engine = ENGINE
            elif mode == "auto":
                w_res = transcribe_whisper(wav, spans)
                if w_res is not None:
                    engine, heard_all = w_res
                    active_fn = lambda p, sp: (transcribe_whisper(p, sp) or (None, None))[1]  # noqa: E731
    if heard_all is None:
        problems.append({"code": "STT_UNAVAILABLE", "severity": "WARN", "detail": why})
    else:
        whisper_candidates: list[tuple[int, list[float]]] = []
        for idx, (c, heard) in enumerate(zip(cues, heard_all)):
            s, source = score_line(c["text"], heard), "stem"
            if s["recall"] < PASS_RECALL and "start_s" in c:
                # second opinion on the raw take: film04 SC06_g2 heard "last show" on the mixed-down stem and
                # "last shift" on the take itself
                found = _take_source(pkg, c.get("event_id"))
                wide = max(pad_s, TAKE_PAD_S)
                again = active_fn(found[0], [[max(0.0, found[1] + c["start_s"] - wide),
                                              found[1] + c["end_s"] + wide]]) if found else None
                if again:
                    s2 = score_line(c["text"], again[0])
                    if s2["recall"] > s["recall"]:
                        s, heard, source = s2, again[0], "take"
            rows.append({"event_id": c.get("event_id"), "line_no": c.get("line_no"), "character": c.get("character"),
                         "expected": c["text"], "heard": heard, "source": source, "recall": s["recall"],
                         "missing": s["missing"], "verdict": "PASS" if s["recall"] >= PASS_RECALL else "WARN"})
            if s["recall"] < PASS_RECALL and transcriber is None and mode == "auto" and engine == ENGINE:
                whisper_candidates.append((idx, [max(0.0, c["abs_start_s"] - pad_s), c["abs_end_s"] + pad_s]))

        if whisper_candidates and len(whisper_candidates) <= 40 and wav is not None:
            w_res = transcribe_whisper(wav, [sp for _, sp in whisper_candidates])
            if w_res is not None:
                w_name, w_texts = w_res
                upgraded = False
                for (row_idx, _), w_txt in zip(whisper_candidates, w_texts):
                    sw = score_line(rows[row_idx]["expected"], w_txt)
                    if sw["recall"] > rows[row_idx]["recall"]:
                        rows[row_idx].update(
                            heard=w_txt,
                            source="whisper",
                            recall=sw["recall"],
                            missing=sw["missing"],
                            verdict="PASS" if sw["recall"] >= PASS_RECALL else "WARN",
                        )
                        upgraded = True
                if upgraded:
                    engine = f"{ENGINE}+{w_name}"

        for r in rows:
            if r["verdict"] == "WARN":
                problems.append({"code": "DIALOGUE_STT_MISMATCH", "severity": "WARN",
                                 "detail": f"{r['event_id']} line {r['line_no']}: heard {r['heard']!r} for "
                                           f"{r['expected']!r} (missing: {' '.join(r['missing'])})"})
    npass = sum(r["verdict"] == "PASS" for r in rows)
    report = {"film_id": pkg.header.film_id, "ok": True, "engine": engine, "rows": rows, "problems": problems,
              "summary": {"lines": len(rows), "pass": npass, "warn": len(rows) - npass,
                          "mean_recall": round(sum(r["recall"] for r in rows) / len(rows), 3) if rows else 0.0}}
    out = root / "qc" / "dialogue_stt.json"
    atomic_json(out, report)
    return report
