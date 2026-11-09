"""Advisory word-level dialogue check: did the generated actors say the scripted line? (Vosk STT, never blocks)."""
from __future__ import annotations

import difflib
import json
import os
import re
import subprocess
from pathlib import Path
from typing import Callable

PASS_RECALL = 0.8
ENGINE = "vosk-small-en-us-0.15"
ROOT = Path(__file__).resolve().parents[3]
HELPER = ROOT / "tools" / "stt_vosk.py"
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


def transcribe(wav: Path, spans: list[list[float]]) -> list[str] | None:
    model = _model_dir()
    if not model.is_dir():
        return None
    try:
        import vosk  # type: ignore
    except ImportError:
        vosk = None
    try:
        if vosk is not None:
            vosk.SetLogLevel(-1)
            m = vosk.Model(str(model))
            out = []
            for a, b in spans:
                pcm = subprocess.run(["ffmpeg", "-v", "error", "-ss", str(a), "-t", str(max(b - a, 0.1)), "-i", str(wav),
                                      "-ac", "1", "-ar", "16000", "-f", "s16le", "-"],
                                     capture_output=True, check=True).stdout
                rec = vosk.KaldiRecognizer(m, 16000)
                rec.AcceptWaveform(pcm)
                out.append(json.loads(rec.FinalResult()).get("text", ""))
            return out
        py = os.environ.get("AFP_STT_PYTHON")
        if not py:
            return None
        res = subprocess.run([py, str(HELPER), str(model), str(wav), json.dumps(spans)],
                             capture_output=True, text=True, check=True)
        out = json.loads(res.stdout)
        return out if isinstance(out, list) and len(out) == len(spans) else None
    except (OSError, subprocess.CalledProcessError, ValueError):
        return None


def _stem(root: Path) -> Path | None:
    mix = root / "audio" / "mix.json"
    if not mix.is_file():
        return None
    raw = (json.loads(mix.read_text(encoding="utf-8")).get("stems") or {}).get("dialogue")
    if not raw:
        return None
    p = Path(str(raw).replace("\\", "/"))
    if not p.is_absolute() and not p.exists():
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


def check(pkg, *, transcriber: Callable | None = None, pad_s: float = 0.4) -> dict:
    root = Path(pkg.root)
    cues: list[dict] = []
    titles = root / "titles" / "titles.json"
    if titles.is_file():
        cues = json.loads(titles.read_text(encoding="utf-8")).get("cues") or []
    wav = _stem(root)
    rows: list[dict] = []
    problems: list[dict] = []
    engine = None
    heard_all = None
    if pkg.header.language != "en":
        why = f"language {pkg.header.language!r} unsupported"
    elif wav is None:
        why = "no dialogue stem"
    elif not cues:
        why = "no cues"
    else:
        spans = [[max(0.0, c["abs_start_s"] - pad_s), c["abs_end_s"] + pad_s] for c in cues]
        heard_all = (transcriber or transcribe)(wav, spans)
        why = "no STT backend available"
    if heard_all is None:
        problems.append({"code": "STT_UNAVAILABLE", "severity": "WARN", "detail": why})
    else:
        engine = ENGINE
        for c, heard in zip(cues, heard_all):
            s, source = score_line(c["text"], heard), "stem"
            if s["recall"] < PASS_RECALL and "start_s" in c:
                # second opinion on the raw take: film04 SC06_g2 heard "last show" on the mixed-down stem and
                # "last shift" on the take itself
                found = _take_source(pkg, c.get("event_id"))
                # a wider window: the raw take carries only this line, and the small model reads a clipped last
                # word differently (SC06_g2 "shift" at +-1.0 s, "show" at +-0.4 s)
                wide = max(pad_s, TAKE_PAD_S)
                again = (transcriber or transcribe)(found[0], [[max(0.0, found[1] + c["start_s"] - wide),
                                                                found[1] + c["end_s"] + wide]]) if found else None
                if again:
                    s2 = score_line(c["text"], again[0])
                    if s2["recall"] > s["recall"]:
                        s, heard, source = s2, again[0], "take"
            verdict = "PASS" if s["recall"] >= PASS_RECALL else "WARN"
            rows.append({"event_id": c.get("event_id"), "line_no": c.get("line_no"), "character": c.get("character"),
                         "expected": c["text"], "heard": heard, "source": source, "recall": s["recall"],
                         "missing": s["missing"], "verdict": verdict})
            if verdict == "WARN":
                problems.append({"code": "DIALOGUE_STT_MISMATCH", "severity": "WARN",
                                 "detail": f"{c.get('event_id')} line {c.get('line_no')}: heard {heard!r} for "
                                           f"{c['text']!r} (missing: {' '.join(s['missing'])})"})
    npass = sum(r["verdict"] == "PASS" for r in rows)
    report = {"film_id": pkg.header.film_id, "ok": True, "engine": engine, "rows": rows, "problems": problems,
              "summary": {"lines": len(rows), "pass": npass, "warn": len(rows) - npass,
                          "mean_recall": round(sum(r["recall"] for r in rows) / len(rows), 3) if rows else 0.0}}
    out = root / "qc" / "dialogue_stt.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    return report
