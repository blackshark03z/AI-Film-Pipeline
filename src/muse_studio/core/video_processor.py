import json
import os
import shutil
import subprocess
from pathlib import Path
from typing import Any, Dict, List, Optional

class VideoProcessor:
    @staticmethod
    def get_video_info(video_path: Path) -> Dict[str, Any]:
        """Trích xuất thông tin video bằng ffprobe."""
        video_path = Path(video_path)
        if not video_path.exists():
            return {"valid": False, "error": "File không tồn tại"}

        cmd = [
            "ffprobe",
            "-v", "error",
            "-select_streams", "v:0",
            "-show_entries", "stream=width,height,duration,r_frame_rate,codec_name:format=duration,size",
            "-of", "json",
            str(video_path)
        ]
        try:
            res = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, check=True)
            data = json.loads(res.stdout)
            streams = data.get("streams", [])
            fmt = data.get("format", {})
            if not streams:
                return {"valid": False, "error": "Không tìm thấy video stream"}

            stream = streams[0]
            width = int(stream.get("width", 0))
            height = int(stream.get("height", 0))
            dur_str = stream.get("duration") or fmt.get("duration", "0")
            duration = float(dur_str) if dur_str else 0.0
            size = int(fmt.get("size", 0))

            return {
                "valid": True,
                "width": width,
                "height": height,
                "duration": duration,
                "fps": stream.get("r_frame_rate", "24/1"),
                "codec": stream.get("codec_name", "unknown"),
                "size_bytes": size,
                "path": str(video_path)
            }
        except Exception as e:
            return {"valid": False, "error": str(e)}

    @staticmethod
    def extract_last_frame(video_path: Path, output_image_path: Path) -> bool:
        """Trích xuất khung hình cuối cùng của video ra file PNG làm ảnh tham chiếu start-frame."""
        video_path = Path(video_path)
        output_image_path = Path(output_image_path)
        output_image_path.parent.mkdir(parents=True, exist_ok=True)

        if not video_path.exists():
            return False

        # Dùng sseof -0.1 để tua nhanh đến 0.1s trước khi kết thúc video
        cmd = [
            "ffmpeg",
            "-y",
            "-sseof", "-0.1",
            "-i", str(video_path),
            "-update", "1",
            "-q:v", "2",
            str(output_image_path)
        ]
        try:
            res = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
            return output_image_path.exists() and output_image_path.stat().st_size > 0
        except Exception:
            return False

    @staticmethod
    def merge_project_videos(clips_list: List[Path], output_path: Path, reencode: bool = True) -> Dict[str, Any]:
        """Nối danh sách các video clips theo thứ tự thành một video hoàn chỉnh."""
        valid_clips = [Path(p) for p in clips_list if Path(p).exists() and Path(p).stat().st_size > 0]
        if not valid_clips:
            return {"success": False, "error": "Không có clip hợp lệ để ghép"}

        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        temp_concat_txt = output_path.parent / f"concat_{output_path.stem}.txt"

        try:
            # Tạo file danh sách concat
            lines = []
            for c in valid_clips:
                clean_path = str(c.resolve()).replace("\\", "/")
                lines.append(f"file '{clean_path}'")
            temp_concat_txt.write_text("\n".join(lines), encoding="utf-8")

            if reencode:
                cmd = [
                    "ffmpeg",
                    "-y",
                    "-f", "concat",
                    "-safe", "0",
                    "-i", str(temp_concat_txt),
                    "-c:v", "libx264",
                    "-pix_fmt", "yuv420p",
                    "-preset", "fast",
                    "-crf", "20",
                    "-c:a", "aac",
                    "-b:a", "192k",
                    str(output_path)
                ]
            else:
                cmd = [
                    "ffmpeg",
                    "-y",
                    "-f", "concat",
                    "-safe", "0",
                    "-i", str(temp_concat_txt),
                    "-c", "copy",
                    str(output_path)
                ]

            proc = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
            if output_path.exists() and output_path.stat().st_size > 0:
                info = VideoProcessor.get_video_info(output_path)
                return {
                    "success": True,
                    "output_path": str(output_path),
                    "clips_count": len(valid_clips),
                    "total_duration": info.get("duration", 0),
                    "size_bytes": output_path.stat().st_size
                }
            else:
                return {"success": False, "error": proc.stderr or "Lỗi khi chạy lệnh nối video FFmpeg"}
        except Exception as e:
            return {"success": False, "error": str(e)}
        finally:
            if temp_concat_txt.exists():
                try:
                    temp_concat_txt.unlink()
                except Exception:
                    pass

    @staticmethod
    def create_synthetic_test_clip(output_path: Path, duration_s: float = 3.0, text: str = "Test") -> bool:
        """Tạo clip test giả lập dùng cho kiểm thử tự động."""
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        cmd = [
            "ffmpeg",
            "-y",
            "-f", "lavfi",
            "-i", f"color=c=indigo:s=1280x720:d={duration_s}",
            "-f", "lavfi",
            "-i", "anullsrc=r=44100:cl=stereo",
            "-t", str(duration_s),
            "-vf", f"drawtext=text='{text}':fontsize=48:fontcolor=white:x=(w-text_w)/2:y=(h-text_h)/2",
            "-c:v", "libx264",
            "-c:a", "aac",
            "-shortest",
            str(output_path)
        ]
        try:
            # Nếu ffmpeg không hỗ trợ libfreetype thì fallback không dùng drawtext
            res = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            if not output_path.exists():
                fallback_cmd = [
                    "ffmpeg", "-y",
                    "-f", "lavfi", "-i", f"color=c=indigo:s=1280x720:d={duration_s}",
                    "-f", "lavfi", "-i", "anullsrc=r=44100:cl=stereo",
                    "-t", str(duration_s),
                    "-c:v", "libx264", "-c:a", "aac", "-shortest",
                    str(output_path)
                ]
                subprocess.run(fallback_cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True)
            return output_path.exists() and output_path.stat().st_size > 0
        except Exception:
            return False
