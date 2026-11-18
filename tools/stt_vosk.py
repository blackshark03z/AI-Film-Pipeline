"""Standalone Vosk helper: transcribe spans of a wav in 1 FFmpeg decode pass + parallel KaldiRecognizer Reset()."""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
import json
import os
import subprocess
import sys


def _decode_window(wav: str, start_s: float, duration_s: float) -> bytes:
    return subprocess.run(
        [
            "ffmpeg", "-v", "error",
            "-ss", f"{start_s:.6f}",
            "-t", f"{max(duration_s, 0.1):.6f}",
            "-i", wav,
            "-ac", "1", "-ar", "16000", "-f", "s16le", "-",
        ],
        capture_output=True,
        check=True,
        timeout=300,
    ).stdout


def main() -> int:
    raw_spans = sys.stdin.read() if sys.argv[3] == "-" else sys.argv[3]
    model_dir, wav, spans = sys.argv[1], sys.argv[2], json.loads(raw_spans)
    if not spans:
        print("[]")
        return 0
    import vosk

    vosk.SetLogLevel(-1)
    model = vosk.Model(model_dir)
    min_a = max(0.0, min(float(a) for a, _ in spans))
    max_b = max(max(float(b), float(a) + 0.1) for a, b in spans)
    pcm_all = _decode_window(wav, min_a, max_b - min_a)

    def _run_batch(batch: list[tuple[int, list[float]]]) -> list[tuple[int, str]]:
        rec = vosk.KaldiRecognizer(model, 16000)
        res: list[tuple[int, str]] = []
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
    return 0


if __name__ == "__main__":
    sys.exit(main())
