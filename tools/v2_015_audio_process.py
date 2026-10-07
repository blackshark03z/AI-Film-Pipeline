"""V2-015 — audio repair + loudness + masters.

Pass 1: per-segment gains (F2 -1.5 dB, F3R +7 dB) + 0.4 s equal-power
crossfades CENTERED on the two picture cuts (total duration preserved
exactly at 13.583333 s) -> repaired audio for measurement.
Pass 2: two-pass loudnorm (I=-14 LUFS, TP=-1.5 dBTP, linear=true).
Video stream is NEVER re-encoded: it is stream-copied into both masters.
"""
from __future__ import annotations

import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
P11X = ROOT / "projects/quality_v2_011x_clean_rebind"
PKG = ROOT / "projects/quality_v2_015_final_master"
SRC = P11X / "outputs/F1R_F2_F3R_SEQUENCE_PROOF_CLEAN.mp4"
AN = PKG / "analysis"

J1 = 4.791667  # frame 115 / 24
J2 = 10.375    # frame 249 / 24
XF = 0.4       # equal-power crossfade seconds (≈10 frames ≤ 12 allowed)


def run(cmd) -> str:
    r = subprocess.run(cmd, capture_output=True, text=True)
    return r.stdout + r.stderr


def main() -> int:
    AN.mkdir(parents=True, exist_ok=True)
    (PKG / "outputs").mkdir(exist_ok=True)
    (PKG / "owner_review_015").mkdir(exist_ok=True)
    wav = AN / "source_audio.wav"
    subprocess.run(["ffmpeg", "-loglevel", "error", "-y", "-i", str(SRC),
                    "-vn", "-acodec", "pcm_s16le", str(wav)], check=True)

    # ---- pass 1: repaired audio with per-segment gains + crossfades -------
    end = 326 / 24  # 13.583333
    seg1_end = J1 + XF / 2      # 4.991667
    seg2_start = J1 - XF / 2    # 4.591667
    seg2_end = J2 + XF / 2      # 10.575
    seg3_start = J2 - XF / 2    # 10.175
    g2 = 10 ** (-1.5 / 20)      # F2 trim
    g3 = 10 ** (7.0 / 20)       # F3R bed raise
    graph = (
        f"[0:a]atrim=start=0:end={seg1_end:.6f},asetpts=PTS-STARTPTS[s1];"
        f"[0:a]atrim=start={seg2_start:.6f}:end={seg2_end:.6f},"
        f"asetpts=PTS-STARTPTS,volume={g2:.6f}[s2];"
        f"[0:a]atrim=start={seg3_start:.6f}:end={end:.6f},"
        f"asetpts=PTS-STARTPTS,volume={g3:.6f}[s3];"
        f"[s1][s2]acrossfade=d={XF}:c1=tri:c2=tri[xf1];"
        f"[xf1][s3]acrossfade=d={XF}:c1=tri:c2=tri[rep]")
    subprocess.run(["ffmpeg", "-loglevel", "error", "-y", "-i", str(wav),
                    "-filter_complex", graph, "-map", "[rep]",
                    str(AN / "repaired_pre_loudnorm.wav")], check=True)

    # ---- pass 2a: measure repaired audio for loudnorm ----------------------
    m = run(["ffmpeg", "-loglevel", "info", "-i",
             str(AN / "repaired_pre_loudnorm.wav"), "-af",
             "loudnorm=I=-14:TP=-1.5:LRA=11:print_format=json", "-f", "null",
             "-"])
    mj = m[m.rfind("{"):m.rfind("}") + 1]
    meas = json.loads(mj)
    print("repaired measured:", {k: meas[k] for k in
                                  ("input_i", "input_tp", "input_lra")})

    # ---- pass 2b: linear loudnorm + resample 48k ---------------------------
    subprocess.run([
        "ffmpeg", "-loglevel", "error", "-y", "-i",
        str(AN / "repaired_pre_loudnorm.wav"), "-af",
        (f"loudnorm=I=-14:TP=-1.5:LRA=11:measured_I={meas['input_i']}:"
         f"measured_TP={meas['input_tp']}:measured_LRA={meas['input_lra']}:"
         f"measured_thresh={meas['input_thresh']}:offset={meas['target_offset']}:"
         f"linear=true:print_format=summary,"
         "aresample=48000"), "-ar", "48000",
        str(AN / "repaired_final.wav")], check=True)

    # ---- Phase 5: mezzanine master (.mov, video stream-copied, PCM audio) --
    mov = PKG / "outputs/SEQ7_F1_F2_F3_CLEAN_FINISH_MASTER.mov"
    subprocess.run([
        "ffmpeg", "-loglevel", "error", "-y", "-i", str(SRC), "-i",
        str(AN / "repaired_final.wav"),
        "-map", "0:v:0", "-map", "1:a:0", "-c:v", "copy",
        "-c:a", "pcm_s16le", "-ar", "48000", "-movflags", "+faststart",
        str(mov)], check=True)

    # ---- Phase 6: distribution master (mp4, video copied, AAC 192k) --------
    mp4 = PKG / "outputs/SEQ7_F1_F2_F3_CLEAN_DISTRIBUTION.mp4"
    subprocess.run([
        "ffmpeg", "-loglevel", "error", "-y", "-i", str(mov),
        "-map", "0:v:0", "-map", "0:a:0", "-c:v", "copy",
        "-c:a", "aac", "-b:a", "192k", "-ar", "48000", "-movflags",
        "+faststart", str(mp4)], check=True)
    print("masters written")
    return 0


if __name__ == "__main__":
    main()
