"""V2-012 — final sequence proof assembly + technical QC.

F1R (0..114, proven) HARD CUT locked F2 (verbatim 134 fr) HARD CUT F3R_012
(IN..IN+77). concat FILTER; h264 yuv420p + AAC 192k @ 24fps.
"""
import hashlib
import json
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parents[1]
P11D = ROOT / "projects/quality_v2_011d_world_matched_context"
PKG = ROOT / "projects/quality_v2_012_f3r_policy_repair"
F1R = P11D / "assets" / "f1r.mp4"
F2 = P11D / "inputs_F2_proof.mp4"
F3R = PKG / "assets" / "f3r_012.mp4"
OUT = PKG / "outputs" / "F1R_F2_F3R_SEQUENCE_PROOF.mp4"
F2_EXPECT = "ada66463983636e505b181d5b81b10c6a7f4da8cdd1a80aff55880dd8fd820de"
F1R_EXPECT = "b879f21586392fa7463021f60853b1aa99fecb286890dad1b3f192c6dd805171"


def sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def utcnow():
    return datetime.now(timezone.utc).isoformat()


def main() -> int:
    f3r_in = int(sys.argv[1]) if len(sys.argv) > 1 else 0
    assert 0 <= f3r_in <= 12, "F3R IN outside the authorized window"
    assert sha256(F1R) == F1R_EXPECT, "F1R custody mismatch"
    assert sha256(F2) == F2_EXPECT, "F2 custody mismatch"

    f3r_out = f3r_in + 77
    OUT.parent.mkdir(exist_ok=True)
    subprocess.run([
        "ffmpeg", "-loglevel", "error", "-y",
        "-i", str(F1R), "-i", str(F2), "-i", str(F3R),
        "-filter_complex",
        f"[0:v]trim=start_frame=0:end_frame=115,setpts=PTS-STARTPTS,fps=24,format=yuv420p[v0];"
        f"[0:a]atrim=end=4.791667,asetpts=PTS-STARTPTS[a0];"
        f"[1:v]fps=24,format=yuv420p[v1];"
        f"[1:a]anull[a1];"
        f"[2:v]trim=start_frame={f3r_in}:end_frame={f3r_out},setpts=PTS-STARTPTS,fps=24,format=yuv420p[v2];"
        f"[2:a]atrim=start={f3r_in/24:.6f}:end={f3r_out/24:.6f},asetpts=PTS-STARTPTS[a2];"
        f"[v0][a0][v1][a1][v2][a2]concat=n=3:v=1:a=1[v][a]",
        "-map", "[v]", "-map", "[a]",
        "-c:v", "libx264", "-preset", "medium", "-crf", "18",
        "-c:a", "aac", "-b:a", "192k", "-movflags", "+faststart",
        str(OUT)], check=True)
    print("assembled", OUT)

    probe = subprocess.run(
        ["ffprobe", "-v", "error", "-select_streams", "v", "-show_entries",
         "stream=codec_name,width,height,r_frame_rate,nb_frames:format=duration",
         "-of", "json", str(OUT)], capture_output=True, text=True)
    st = json.loads(probe.stdout)["streams"][0]
    qc = {"nb_frames": st["nb_frames"], "fps": st["r_frame_rate"],
          "codec": st["codec_name"], "size": f'{st["width"]}x{st["height"]}',
          "duration": json.loads(probe.stdout)["format"]["duration"]}
    expected = 115 + 134 + 77
    qc["frame_count_exact"] = int(st["nb_frames"]) == expected
    qc["decode_pass"] = subprocess.run(
        ["ffmpeg", "-v", "error", "-xerror", "-i", str(OUT), "-f", "null",
         "-"], capture_output=True).returncode == 0
    blk = subprocess.run(["ffmpeg", "-i", str(OUT), "-vf",
                          "blackdetect=d=0.04:pix_th=0.10", "-an", "-f",
                          "null", "-"], capture_output=True, text=True)
    qc["no_black_frames"] = "blackdetect" not in blk.stderr
    frz = subprocess.run(["ffmpeg", "-i", str(OUT), "-vf",
                          "freezedetect=n=0.001:d=0.3", "-an", "-f", "null",
                          "-"], capture_output=True, text=True)
    qc["no_frozen_frames"] = "freeze_start" not in frz.stderr
    pts = subprocess.run(
        ["ffprobe", "-v", "error", "-select_streams", "v", "-show_entries",
         "frame=pts_time", "-of", "csv=p=0", str(OUT)],
        capture_output=True, text=True)
    ts = [float(x) for x in pts.stdout.replace(",", "").split() if x.strip()]
    qc["timestamp_discontinuities"] = len(
        [i for i in range(1, len(ts))
         if abs(ts[i] - ts[i - 1] - 1 / 24) > 1e-6])
    proof_sha = sha256(OUT)
    qc["sha256"] = proof_sha
    qc["expected_frames"] = expected
    qc["junction_frames"] = {"f1r_f2": 115, "f2_f3r": 249}

    j2 = 249 / 24
    audio = {}
    for name, ss in (("pre_J1", 3.8), ("post_J1", 4.8),
                     ("pre_J2", j2 - 1.0), ("post_J2", j2)):
        r = subprocess.run(
            ["ffmpeg", "-ss", f"{ss:.3f}", "-t", "1.0", "-i", str(OUT),
             "-af", "volumedetect", "-f", "null", "-"],
            capture_output=True, text=True)
        m = re.search(r"mean_volume:\s*(-?[\d.]+) dB", r.stderr)
        audio[name] = float(m.group(1)) if m else None
    qc["audio_mean_db"] = audio
    qc["audio_step_J1_db"] = round(abs(audio["post_J1"] - audio["pre_J1"]), 1)
    qc["audio_step_J2_db"] = round(abs(audio["post_J2"] - audio["pre_J2"]), 1)

    # contact sheet
    seq_dir = PKG / "frames" / "seqproof"
    seq_dir.mkdir(parents=True, exist_ok=True)
    total = int(st["nb_frames"])
    idxs = sorted(set([0, 10, 20, 40, 60, 80, 100, 113, 114, 115, 125, 145,
                       165, 185, 205, 225, 245, 248, 249, 260, 280, 300, 315,
                       total - 1]))
    idxs = [i for i in idxs if i < total]
    for n in idxs:
        subprocess.run(["ffmpeg", "-loglevel", "error", "-i", str(OUT),
                        "-vf", f"select=eq(n\\,{n})", "-vframes", "1", "-y",
                        str(seq_dir / f"n{n:03d}.png")], capture_output=True)
    TW, TH, LH, COLS = 320, 180, 26, 5
    files = sorted(seq_dir.glob("n*.png"))
    rows = [files[i:i + COLS] for i in range(0, len(files), COLS)]
    W = COLS * (TW + 4) + 4
    H = 40 + len(rows) * (TH + LH + 4) + 30
    img = Image.new("RGB", (W, H), (10, 10, 14))
    d = ImageDraw.Draw(img)
    d.text((8, 8), "V2-012 FULL SEQUENCE PROOF | F1R(0-114) HARD CUT LOCKED F2(115-248) HARD CUT F3R_012(249-325) | "
           f"{total} fr @24fps | sha {proof_sha[:16]}", fill=(255, 220, 120))
    y = 36
    for row in rows:
        for j, f in enumerate(row):
            im = Image.open(f).convert("RGB").resize((TW, TH), Image.LANCZOS)
            c = Image.new("RGB", (TW, TH + LH), (16, 16, 20))
            c.paste(im, (0, 0))
            dd = ImageDraw.Draw(c)
            n = int(f.stem[1:])
            seg = "F1R" if n < 115 else ("F2" if n < 249 else "F3R")
            dd.text((6, TH + 2), f"n={n} [{seg}]", fill=(240, 240, 240))
            dd.text((6, TH + 13), f"t={n/24:.2f}s", fill=(160, 200, 255))
            img.paste(c, (4 + j * (TW + 4), y))
        y += TH + LH + 4
    d.text((8, y + 4), "ARRIVE -> FORCE THROUGH -> COST HELD | watermarks preserved (Dola AI)",
           fill=(120, 255, 140))
    img.save(PKG / "owner_review_012" / "FULL_SEQUENCE_CONTACT_SHEET.png")

    (PKG / "V2_012_TECHNICAL_QC.json").write_text(
        json.dumps({"version": "v2-012-technical-qc-v1",
                    "recorded_at": utcnow(), "output": str(OUT),
                    "f3r_in_frame": f3r_in, "f3r_out_exclusive": f3r_out,
                    "qc": qc}, indent=1, ensure_ascii=False),
        encoding="utf-8")
    print(json.dumps(qc, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
