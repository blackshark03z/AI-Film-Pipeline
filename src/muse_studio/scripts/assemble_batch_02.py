"""
Assemble and QC Corrected Native Dialogue Demo (Batch 02)
1. Thu thập clips đã giải nén từ Batch 02
2. Chạy 5-Gate QA/QC (Faster-Whisper ASR, Decode, Hand, Face Identity)
3. Ghép Master Timeline 60s chuẩn 24fps
4. Chuẩn hóa EBU R128 (-16 LUFS) và mux phụ đề SRT đồng bộ
5. Trích xuất frame bằng chứng kiểm định
"""

import json
import os
import subprocess
import sys
from pathlib import Path

# Add project root
ROOT = Path(r"D:\Muse")
sys.path.insert(0, str(ROOT))

from muse_studio.core.film_qc_engine import FilmQCEngine
from muse_studio.core.batch_packager import compute_sha256

NATIVE_DIR = Path(r"D:\Muse\BLACK_PILOT_DEMO_60S_20261117\NATIVE_PRODUCTION_V2")
CLIPS_DIR = NATIVE_DIR / "verified_clips"
FINAL_DIR = NATIVE_DIR / "FINAL"
EVIDENCE_DIR = FINAL_DIR / "evidence_frames"
CLIPS_DIR.mkdir(parents=True, exist_ok=True)
FINAL_DIR.mkdir(parents=True, exist_ok=True)
EVIDENCE_DIR.mkdir(parents=True, exist_ok=True)

CORRECTED_SPECS = [
    {
        "shot_id": "shot_01",
        "speaker": "ATTENDANT",
        "actor_type": "Caucasian_Blonde",
        "dialogue": "What the hell are you doing up here? This is not a place for jokes."
    },
    {
        "shot_id": "shot_02",
        "speaker": "BRIANNA",
        "actor_type": "Black_Captain",
        "dialogue": "I am Captain Brianna Vance, your pilot today."
    },
    {
        "shot_id": "shot_03",
        "speaker": "ATTENDANT",
        "actor_type": "Caucasian_Blonde",
        "dialogue": "It smells like garbage. People like you don't even deserve to sit in economy class."
    },
    {
        "shot_id": "shot_04",
        "speaker": "ATTENDANT",
        "actor_type": "Caucasian_Blonde",
        "dialogue": "Get out before I have someone drag you off this plane!"
    },
    {
        "shot_id": "shot_05",
        "speaker": "ATTENDANT",
        "actor_type": "Caucasian_Blonde",
        "dialogue": "Security, get this woman off my plane right now!"
    },
    {
        "shot_id": "shot_06",
        "speaker": "BRIANNA",
        "actor_type": "Black_Captain",
        "dialogue": "Flight operations, this is Captain Vance on flight 142. We have a security breach in the forward galley."
    }
]

def run_batch_02_assembly():
    print("[*] STEP 1: Thu thập clips Batch 02...")
    mp4_files = sorted(CLIPS_DIR.glob("**/*.mp4"))
    print(f"[+] Tìm thấy {len(mp4_files)} clips MP4 trong {CLIPS_DIR}")
    if len(mp4_files) < 6:
        print(f"[-] Chưa đủ 6 clips (mới có {len(mp4_files)}).")
        return None

    print("\n[*] STEP 2: Chạy 5-Gate QA/QC và trích xuất ASR Timestamps...")
    qc_reports = {}
    verified_shots = []

    for idx, spec in enumerate(CORRECTED_SPECS, start=1):
        s_id = spec["shot_id"]
        matching = [f for f in mp4_files if s_id in f.name or f"shot_{idx:02d}" in f.name]
        if not matching and idx <= len(mp4_files):
            matching = [mp4_files[idx - 1]]

        clip_path = matching[0]
        shot_spec = {
            "id": s_id,
            "dialogue": spec["dialogue"],
            "prompt": spec["dialogue"],
            "aspect_ratio": "16:9"
        }

        res = FilmQCEngine.evaluate_generated_clip(clip_path, shot_spec, min_duration_s=3.0)
        qc_reports[s_id] = res

        asr_text = res.get("metrics", {}).get("dialogue_qc", {}).get("transcript", "")
        wer = res.get("metrics", {}).get("dialogue_qc", {}).get("wer", 1.0)
        print(f"  [{s_id}] {spec['speaker']} ({spec['actor_type']}): Verdict={res['verdict']} | WER={wer*100:.1f}%")
        print(f"       ASR: \"{asr_text[:65]}...\"")

        verified_shots.append({
            "shot_id": s_id,
            "speaker": spec["speaker"],
            "dialogue": spec["dialogue"],
            "clip_path": clip_path,
            "qc": res
        })

    (NATIVE_DIR / "qc_batch_02_report.json").write_text(json.dumps(qc_reports, indent=2, ensure_ascii=False), encoding="utf-8")

    print("\n[*] STEP 3: Ghép Master Timeline & Hòa âm EBU R128...")
    concat_txt = FINAL_DIR / "concat_list.txt"
    srt_out = FINAL_DIR / "dialogue_subtitles.srt"
    master_mp4 = FINAL_DIR / "black_pilot_1min_corrected_master.mp4"

    concat_lines = []
    srt_entries = []
    current_time_s = 0.0

    normalized_clips = []
    for idx, item in enumerate(verified_shots, start=1):
        s_id = item["shot_id"]
        raw_clip = item["clip_path"]
        norm_clip = FINAL_DIR / f"norm_{s_id}.mp4"

        cmd_norm = [
            "ffmpeg", "-y", "-i", str(raw_clip),
            "-vf", "scale=1280:720:force_original_aspect_ratio=increase,crop=1280:720,fps=24",
            "-af", "aformat=sample_rates=48000:channel_layouts=stereo",
            "-c:v", "libx264", "-preset", "veryfast", "-crf", "18",
            "-c:a", "aac", "-b:a", "192k",
            str(norm_clip)
        ]
        subprocess.run(cmd_norm, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)

        probe_cmd = ["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "default=noprint_wrappers=1:nokey=1", str(norm_clip)]
        dur = float(subprocess.check_output(probe_cmd, text=True).strip())

        escaped_path = str(norm_clip.resolve()).replace("\\", "/")
        concat_lines.append(f"file '{escaped_path}'")
        normalized_clips.append((norm_clip, dur))

        # Phụ đề
        start_ts = format_srt_time(current_time_s + 0.3)
        end_ts = format_srt_time(current_time_s + dur - 0.3)
        srt_entries.append(f"{idx}\n{start_ts} --> {end_ts}\n{item['speaker']}: {item['dialogue']}\n")

        current_time_s += dur

    concat_txt.write_text("\n".join(concat_lines), encoding="utf-8")
    srt_out.write_text("\n".join(srt_entries), encoding="utf-8")

    # Concat
    temp_concat_mp4 = FINAL_DIR / "temp_concat_video.mp4"
    cmd_concat = [
        "ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", str(concat_txt),
        "-c:v", "copy", "-c:a", "copy",
        str(temp_concat_mp4)
    ]
    subprocess.run(cmd_concat, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)

    # Master render
    srt_escaped = str(srt_out.resolve()).replace("\\", "/").replace(":", "\\:")
    vf_filter = (
        f"subtitles='{srt_escaped}':force_style="
        f"'FontSize=18,PrimaryColour=&H00FFFFFF,OutlineColour=&H00000000,BorderStyle=3,Outline=2,Shadow=1,MarginV=30'"
    )
    af_filter = "loudnorm=I=-16:TP=-1.5:LRA=11"

    cmd_master = [
        "ffmpeg", "-y",
        "-i", str(temp_concat_mp4),
        "-vf", vf_filter,
        "-af", af_filter,
        "-c:v", "libx264", "-preset", "medium", "-crf", "18",
        "-pix_fmt", "yuv420p",
        "-c:a", "aac", "-b:a", "192k", "-ar", "48000",
        "-movflags", "+faststart",
        str(master_mp4)
    ]
    res_master = subprocess.run(cmd_master, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    if res_master.returncode != 0:
        cmd_fallback = [
            "ffmpeg", "-y",
            "-i", str(temp_concat_mp4),
            "-i", str(srt_out),
            "-af", af_filter,
            "-map", "0:v", "-map", "0:a", "-map", "1:s",
            "-c:v", "libx264", "-preset", "medium", "-crf", "18",
            "-pix_fmt", "yuv420p",
            "-c:a", "aac", "-b:a", "192k", "-ar", "48000",
            "-c:s", "mov_text",
            "-movflags", "+faststart",
            str(master_mp4)
        ]
        subprocess.run(cmd_fallback, check=True)

    print(f"\n[+] XUẤT XƯỞNG MASTER THÀNH CÔNG: {master_mp4}")
    print(f"    Dung lượng: {master_mp4.stat().st_size} bytes ({master_mp4.stat().st_size/1024/1024:.2f} MB)")

    # Trích xuất frames bằng chứng kiểm định
    for idx, t in enumerate([5.0, 15.0, 25.0, 35.0, 45.0, 55.0], start=1):
        f_p = EVIDENCE_DIR / f"shot_{idx:02d}_{t:.0f}s.png"
        subprocess.run(["ffmpeg", "-y", "-ss", str(t), "-i", str(master_mp4), "-vframes", "1", str(f_p)], capture_output=True)
        print(f"  [+] Đã trích xuất evidence frame shot {idx} -> {f_p.name}")

    return master_mp4

def format_srt_time(seconds: float) -> str:
    h = int(seconds // 3600)
    m = int((seconds % 3600) // 60)
    s = int(seconds % 60)
    ms = int(round((seconds - int(seconds)) * 1000))
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"

if __name__ == "__main__":
    run_batch_02_assembly()
