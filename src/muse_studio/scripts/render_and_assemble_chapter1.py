import os
import sys
import subprocess
from pathlib import Path

# Paths
BASE_DIR = Path(r"D:\Muse\muse_studio")
PROJ_DIR = BASE_DIR / "data" / "projects" / "proj_b08ff4b1"
CLIPS_DIR = PROJ_DIR / "clips"
CLIPS_DIR.mkdir(parents=True, exist_ok=True)
OUTPUT_DIR = BASE_DIR / "data" / "output"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

THUMBNAIL = Path(r"D:\Youtube\Vận hành kênh\Black Drama\wanglin08ma\Đang sản xuất\[4-11-26] Attendant Rips Badge Off Black Pilot Before 142 Passengers — [AhrVCbAppHs]\thumbnail_maxres.jpg")
AUDIO_FILE = PROJ_DIR / "audio_chapter1_orig.mp3"
SUBTITLE_FILE = PROJ_DIR / "chapter1_subtitles.srt"
FINAL_MOVIE = OUTPUT_DIR / "final_movie.mp4"

# 6 Shots with cinematic motion effects (9 seconds each, 24fps)
# Ken Burns effects using zoompan filter
shot_configs = [
    {
        "id": "shot_01",
        "duration": 9.0,
        "filter": "zoompan=z='min(zoom+0.0006,1.15)':d=216:x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':s=1280x720:fps=24"
    },
    {
        "id": "shot_02",
        "duration": 9.0,
        "filter": "zoompan=z='1.1':d=216:x='iw/2-(iw/zoom/2)+on*0.4':y='ih/2-(ih/zoom/2)':s=1280x720:fps=24"
    },
    {
        "id": "shot_03",
        "duration": 9.0,
        "filter": "zoompan=z='min(zoom+0.0008,1.25)':d=216:x='iw*0.6-(iw/zoom/2)':y='ih*0.4-(ih/zoom/2)':s=1280x720:fps=24"
    },
    {
        "id": "shot_04",
        "duration": 9.0,
        "filter": "zoompan=z='min(zoom+0.001,1.35)':d=216:x='iw*0.35-(iw/zoom/2)':y='ih*0.35-(ih/zoom/2)':s=1280x720:fps=24"
    },
    {
        "id": "shot_05",
        "duration": 9.0,
        "filter": "zoompan=z='1.15':d=216:x='iw/2-(iw/zoom/2)-on*0.3':y='ih/2-(ih/zoom/2)':s=1280x720:fps=24"
    },
    {
        "id": "shot_06",
        "duration": 9.0,
        "filter": "zoompan=z='max(1.2-on*0.0008,1.0)':d=216:x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':s=1280x720:fps=24"
    }
]

print("[*] Bắt đầu render 6 phân cảnh điện ảnh chuẩn 16:9...")
clip_paths = []
for idx, s in enumerate(shot_configs, 1):
    out_clip = CLIPS_DIR / f"{s['id']}.mp4"
    last_frame = CLIPS_DIR / f"{s['id']}_last_frame.png"
    print(f"    -> Render phân cảnh {idx}/6: {s['id']} ({s['duration']}s)...")
    
    cmd = [
        "ffmpeg", "-y",
        "-loop", "1", "-i", str(THUMBNAIL),
        "-vf", s["filter"],
        "-t", str(s["duration"]),
        "-c:v", "libx264", "-preset", "fast", "-crf", "18",
        "-pix_fmt", "yuv420p",
        str(out_clip)
    ]
    subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True)
    clip_paths.append(out_clip)
    
    # Trích xuất frame cuối
    cmd_frame = [
        "ffmpeg", "-y", "-sseof", "-0.1",
        "-i", str(out_clip),
        "-vframes", "1",
        str(last_frame)
    ]
    subprocess.run(cmd_frame, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True)

print(f"[+] Đã hoàn thành render toàn bộ {len(clip_paths)} clips!")

# Khâu 4: Hậu kỳ hòa âm EBU R128 (-16 LUFS) và ghép nối thành phim hoàn chỉnh
print("[*] Khởi chạy Khâu 4 (Film Post Assembly): Hậu kỳ & Hòa âm...")
concat_file = PROJ_DIR / "concat_list.txt"
lines = [f"file '{str(p.resolve()).replace(chr(92), '/')}'" for p in clip_paths]
concat_file.write_text("\n".join(lines), encoding="utf-8")

temp_video = PROJ_DIR / "temp_merged_video.mp4"
cmd_concat = [
    "ffmpeg", "-y",
    "-f", "concat", "-safe", "0",
    "-i", str(concat_file),
    "-c", "copy",
    str(temp_video)
]
subprocess.run(cmd_concat, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True)

# Chuẩn hóa âm thanh EBU R128 (-16 LUFS) và burn phụ đề
print("[*] Lồng tiếng kịch tính gốc, burn phụ đề SRT và chuẩn hóa -16 LUFS...")
sub_path_escaped = str(SUBTITLE_FILE.resolve()).replace("\\", "/").replace(":", "\\:")
cmd_final = [
    "ffmpeg", "-y",
    "-i", str(temp_video),
    "-i", str(AUDIO_FILE),
    "-vf", f"subtitles='{sub_path_escaped}':force_style='FontSize=20,PrimaryColour=&H00FFFFFF,OutlineColour=&H00000000,BorderStyle=3,Outline=2,Shadow=1,Alignment=2,MarginV=30'",
    "-filter_complex", "[1:a]loudnorm=I=-16:TP=-1.5:LRA=11[out_audio]",
    "-map", "0:v",
    "-map", "[out_audio]",
    "-c:v", "libx264", "-preset", "medium", "-crf", "18",
    "-c:a", "aac", "-b:a", "192k",
    "-shortest",
    str(FINAL_MOVIE)
]
subprocess.run(cmd_final, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True)

if FINAL_MOVIE.exists():
    size_mb = FINAL_MOVIE.stat().st_size / (1024 * 1024)
    print(f"[🎉] XUẤT XƯỞNG THÀNH CÔNG PHIM HOÀN CHỈNH: {FINAL_MOVIE}")
    print(f"     Dung lượng: {size_mb:.2f} MB | Thời lượng: 54.0s | Chuẩn âm: -16 LUFS")
else:
    print("[!] Lỗi: Không tìm thấy file output sau khi render.")
