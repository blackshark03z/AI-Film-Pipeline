"""V2-010E — acquire the completed F2B asset (one-shot, no browser)."""
from __future__ import annotations

import hashlib
import json
import subprocess
import sys
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PKG = ROOT / "projects/quality_v2_010e_final_f2b"

creation = json.loads(
    (PKG / "V2_010E_F2B_CREATION_OBJECT.json").read_text(encoding="utf-8"))
video = creation["video"]
url = video["download_url"]
dest = PKG / "assets" / "f2b_010e_reconciled.mp4"
dest.parent.mkdir(exist_ok=True)
candidate = dest.with_suffix(".mp4.candidate")

with urllib.request.urlopen(urllib.request.Request(url), timeout=300) as resp, \
        candidate.open("wb") as out:
    total = 0
    while True:
        part = resp.read(256 * 1024)
        if not part:
            break
        total += len(part)
        out.write(part)
sha = hashlib.sha256(candidate.read_bytes()).hexdigest()
candidate.replace(dest)

probe = subprocess.run(
    ["ffprobe", "-v", "error", "-show_entries",
     "format=duration:stream=width,height,codec_name,r_frame_rate",
     "-of", "json", str(dest)], capture_output=True, text=True)
meta = json.loads(probe.stdout or "{}")
stream = next((s for s in meta.get("streams", []) if "width" in s), {})
decode = subprocess.run(
    ["ffmpeg", "-v", "error", "-xerror", "-i", str(dest),
     "-map", "0:v:0", "-f", "null", "-"], capture_output=True).returncode == 0
record = {
    "creation_id": creation["id"], "creation_type": creation["type"],
    "video_status": video.get("status"), "vid": video.get("vid"),
    "provider_duration_field": video.get("duration"),
    "video_model": video.get("video_model"),
    "provider_filehash": video.get("download_filehash"),
    "asset": {"path": str(dest), "sha256": sha, "size": total,
              "host": url.split("/")[2],
              "duration_s": meta.get("format", {}).get("duration"),
              "width": stream.get("width"), "height": stream.get("height"),
              "codec": stream.get("codec_name"),
              "fps": stream.get("r_frame_rate"),
              "full_decode": decode},
}
(PKG / "V2_010E_F2B_ASSET_RECORD.json").write_text(
    json.dumps(record, indent=1, ensure_ascii=False), encoding="utf-8")
print(json.dumps(record, ensure_ascii=False, indent=1))
