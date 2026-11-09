"""Standalone Vosk helper: transcribe spans of a wav. argv: <model_dir> <wav> <json_spans>; prints a JSON list of texts."""
import json
import subprocess
import sys


def main() -> int:
    model_dir, wav, spans = sys.argv[1], sys.argv[2], json.loads(sys.argv[3])
    import vosk

    vosk.SetLogLevel(-1)
    model = vosk.Model(model_dir)
    out = []
    for a, b in spans:
        pcm = subprocess.run(
            ["ffmpeg", "-v", "error", "-ss", str(a), "-t", str(max(b - a, 0.1)), "-i", wav,
             "-ac", "1", "-ar", "16000", "-f", "s16le", "-"],
            capture_output=True, check=True).stdout
        rec = vosk.KaldiRecognizer(model, 16000)
        rec.AcceptWaveform(pcm)
        out.append(json.loads(rec.FinalResult()).get("text", ""))
    print(json.dumps(out))
    return 0


if __name__ == "__main__":
    sys.exit(main())
