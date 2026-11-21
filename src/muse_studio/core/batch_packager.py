"""
Batch Packager & Result Unpacker for Meta Muse AI
Đóng gói lô tối đa 6 video shot (`batch_handoff.zip`) hoặc tối đa 4 keyframe (`kf_handoff.zip`),
kèm lệnh thực thi cho Muse VM (có bước kiểm định ffprobe/SHA-256 ngay trên VM),
và giải nén đối soát chặt chẽ `batch_result.zip` so với `manifest.json` để phát hiện shot thiếu/lỗi
và tự đóng gói lô retry.
"""

import hashlib
import io
import json
import os
import zipfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from PIL import Image, ImageOps

# First-frame (T0) sizes with controlled evidence (R47B landscape, R51 portrait):
# only these exact sizes kept the output at native resolution with high frame-0 PSNR.
T0_TARGET_SIZES: Dict[str, Tuple[int, int]] = {"16:9": (1280, 720), "9:16": (720, 1280)}
# Max relative aspect mismatch fixed by a centered crop. Larger mismatches would cut
# into faces/hands/props, so the keyframe must be recomposed instead.
T0_MAX_ASPECT_DEVIATION = 0.01
# 8-bit modes only: Pillow's convert("RGB") clamps 16-bit/float data instead of scaling it.
T0_ACCEPTED_MODES = {"RGB", "RGBA", "L", "LA", "P", "PA"}


def normalize_first_frame(image_path: Path, aspect_ratio: str) -> Tuple[bytes, Dict[str, Any]]:
    """Return the exact T0 bytes to send plus a record of source vs sent image.

    For aspects listed in T0_TARGET_SIZES the image is brought to the exact target size
    (tiny centered crop + Lanczos). An image already at the target size as RGB PNG is sent
    byte-for-byte. Other aspects pass through unchanged and are marked unverified.
    """
    image_path = Path(image_path)
    src_bytes = image_path.read_bytes()
    src_sha = compute_sha256(src_bytes)
    target = T0_TARGET_SIZES.get(aspect_ratio)
    src_orientation = 1
    try:
        with Image.open(io.BytesIO(src_bytes)) as probe:
            src_format = probe.format
            src_size = probe.size
            src_mode = probe.mode
            src_orientation = probe.getexif().get(0x0112, 1)
            probe.load()  # full decode: rejects truncated image data
    except Exception as exc:
        if target is None:
            src_format, src_size, src_mode = None, None, None
        else:
            raise ValueError(f"First frame is not a decodable image: {image_path}") from exc
    if target is not None and src_mode not in T0_ACCEPTED_MODES:
        raise ValueError(f"First frame {image_path.name} has unsupported mode {src_mode}; export 8-bit RGB.")

    record: Dict[str, Any] = {
        "source": {
            "file_name": image_path.name,
            "sha256": src_sha,
            "width": src_size[0] if src_size else None,
            "height": src_size[1] if src_size else None,
            "format": src_format,
        },
    }
    if target is None:
        record["sent"] = dict(record["source"])
        record["normalization"] = {"status": "UNVERIFIED_ASPECT_PASSTHROUGH", "aspect": aspect_ratio}
        return src_bytes, record

    tw, th = target
    if src_size == target and src_format == "PNG" and src_mode == "RGB" and src_orientation == 1:
        sent_bytes = src_bytes
        record["normalization"] = {"status": "ALREADY_NORMALIZED", "aspect": aspect_ratio}
    else:
        with Image.open(io.BytesIO(src_bytes)) as im:
            im = ImageOps.exif_transpose(im)
            if im.mode == "P" and "transparency" in im.info:
                im = im.convert("RGBA")
            if im.mode in ("RGBA", "LA", "PA"):
                alpha = im.getchannel("A")
                if alpha.getextrema()[0] < 255:
                    raise ValueError(
                        f"First frame {image_path.name} has transparent pixels; export an opaque image."
                    )
            if im.mode != "RGB":
                im = im.convert("RGB")
            w, h = im.size
            target_ratio = tw / th
            src_ratio = w / h
            deviation = abs(src_ratio - target_ratio) / target_ratio
            if deviation > T0_MAX_ASPECT_DEVIATION + 1e-9:
                raise ValueError(
                    f"First frame {image_path.name} is {w}x{h} (ratio {src_ratio:.4f}); "
                    f"{aspect_ratio} needs {target_ratio:.4f}. Recompose the keyframe instead of cropping."
                )
            if src_ratio > target_ratio:
                cw, ch = round(h * target_ratio), h
            else:
                cw, ch = w, round(w / target_ratio)
            left, top = (w - cw) // 2, (h - ch) // 2
            crop_box = (left, top, left + cw, top + ch)
            out = im.resize((tw, th), Image.Resampling.LANCZOS, box=crop_box)
            buf = io.BytesIO()
            out.save(buf, format="PNG")
            sent_bytes = buf.getvalue()
        record["normalization"] = {
            "status": "NORMALIZED",
            "aspect": aspect_ratio,
            "method": "center_crop_lanczos_png",
            "crop_box": list(crop_box),
            "aspect_deviation": round(deviation, 6),
            "upscaled": cw < tw or ch < th,
        }
    record["sent"] = {
        "sha256": compute_sha256(sent_bytes),
        "width": tw,
        "height": th,
        "format": "PNG",
    }
    return sent_bytes, record


def compute_sha256(data: bytes | Path) -> str:
    """Tính toán mã băm SHA-256."""
    h = hashlib.sha256()
    if isinstance(data, Path):
        with open(data, "rb") as f:
            while chunk := f.read(65536):
                h.update(chunk)
    else:
        h.update(data)
    return h.hexdigest()


@dataclass
class ShotItem:
    shot_id: str
    prompt: str
    first_frame_path: Path
    duration_s: float = 10.0
    aspect_ratio: str = "16:9"
    dialogue: str = ""
    speaker: str = ""
    request_id: Optional[str] = None
    audio_mode: str = "NATIVE_DIALOGUE"
    extra_refs: List[Path] = field(default_factory=list)


@dataclass
class KeyframeItem:
    kf_id: str
    prompt: str
    reference_images: List[Path] = field(default_factory=list)
    aspect_ratio: str = "16:9"
    output_format: str = "png"
    request_id: Optional[str] = None


# Per-batch durable list of clip files that failed the receipt SHA-256 check.
INTEGRITY_FAILED_FILE = "integrity_failed.json"
INTEGRITY_UNPERSISTED = "INTEGRITY_UNPERSISTED"


class IntegrityUnpersistedError(RuntimeError):
    """A SHA-mismatched clip could be neither listed in `integrity_failed.json` nor moved to quarantine: nothing marks it
    as untrusted any more, so the run must STOP (lane contract v8 section 10 #11: a received clip is never deleted).
    `results` is the unpack result (the clip is NOT in `verified_shots`); `clips` names the affected files."""

    status = INTEGRITY_UNPERSISTED

    def __init__(self, message: str, results: Optional[Dict[str, Any]] = None, clips: Optional[List[str]] = None):
        super().__init__(message)
        self.results = results or {}
        self.clips = list(clips or [])


class BatchPackager:
    """Quản lý đóng gói lô gửi Muse VM và đối soát kết quả chặt chẽ."""

    MAX_BATCH_SIZE = 6
    MAX_KEYFRAME_BATCH_SIZE = 4
    MIN_VIDEO_BYTES = 100 * 1024
    MIN_IMAGE_BYTES = 5 * 1024

    @staticmethod
    def create_batch_handoff(
        batch_id: str,
        shots: List[ShotItem],
        output_dir: Path
    ) -> Tuple[Path, str]:
        """
        Tạo gói `{batch_id}_handoff.zip` chứa tối đa 6 shot theo chuẩn Muse VM.
        Trả về `(path_to_zip, relay_message_text)`.
        """
        if len(shots) > BatchPackager.MAX_BATCH_SIZE:
            raise ValueError(f"Một batch chỉ nhận tối đa {BatchPackager.MAX_BATCH_SIZE} shot (nhận {len(shots)}).")
        if not shots:
            raise ValueError("Danh sách shot không được rỗng.")

        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)
        zip_path = output_dir / f"{batch_id}_handoff.zip"
        result_zip_name = f"{batch_id}_result.zip"

        manifest_entries = []
        zip_buffer = io.BytesIO()

        with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zf:
            for idx, shot in enumerate(shots, start=1):
                slot_id = f"shot_{idx:02d}"
                folder = f"shots/{slot_id}_{shot.shot_id}"

                # 1. Đọc và lưu 00.png
                first_frame = Path(shot.first_frame_path)
                if not first_frame.exists():
                    raise FileNotFoundError(f"Không tìm thấy ảnh frame đầu: {first_frame}")
                # T0 goes out at the exact verified size; hashes below refer to the sent bytes.
                img_bytes, t0_record = normalize_first_frame(first_frame, shot.aspect_ratio)
                img_sha256 = t0_record["sent"]["sha256"]
                zf.writestr(f"{folder}/assets/00.png", img_bytes)

                # Ảnh tham chiếu phụ nếu có
                extra_ref_entries = []
                for r_idx, r_path in enumerate(shot.extra_refs or [], start=1):
                    rp = Path(r_path)
                    if rp.exists():
                        r_bytes = rp.read_bytes()
                        arc_ref = f"{folder}/assets/ref_{r_idx:02d}{rp.suffix or '.png'}"
                        zf.writestr(arc_ref, r_bytes)
                        extra_ref_entries.append({
                            "path": f"assets/ref_{r_idx:02d}{rp.suffix or '.png'}",
                            "sha256": compute_sha256(r_bytes)
                        })

                # 2. Lưu prompt.txt
                prompt_bytes = shot.prompt.encode("utf-8")
                prompt_sha256 = compute_sha256(prompt_bytes)
                zf.writestr(f"{folder}/prompt.txt", prompt_bytes)

                # 3. Tạo request_id và request.json (gắn batch_id để mỗi lần retry có request_id mới)
                req_id = shot.request_id or compute_sha256(
                    f"{batch_id}:{shot.shot_id}:{prompt_sha256}:{img_sha256}".encode()
                )
                req_dict = {
                    "schema_version": 2,
                    "request_id": req_id,
                    "slot_id": slot_id,
                    "shot_id": shot.shot_id,
                    "generation_id": shot.shot_id,
                    "prompt": shot.prompt,
                    "prompt_sha256": prompt_sha256,
                    "duration_s": shot.duration_s,
                    "aspect": shot.aspect_ratio,
                    "tier": "STANDARD",
                    "first_frame": {
                        "path": "assets/00.png",
                        "sha256": img_sha256,
                        "width": t0_record["sent"]["width"],
                        "height": t0_record["sent"]["height"],
                        "source_sha256": t0_record["source"]["sha256"],
                        "normalization": t0_record["normalization"]["status"]
                    },
                    "last_frame": None,
                    "references": extra_ref_entries,
                    "audio_mode": shot.audio_mode,
                    "speaker": shot.speaker,
                    "dialogue": shot.dialogue,
                    "output": f"{slot_id}.mp4"
                }
                zf.writestr(f"{folder}/request.json", json.dumps(req_dict, indent=2, ensure_ascii=False).encode("utf-8"))

                manifest_entries.append({
                    "shot_index": idx,
                    "slot_id": slot_id,
                    "shot_id": shot.shot_id,
                    "request_id": req_id,
                    "folder": folder,
                    "expected_output": f"{slot_id}.mp4",
                    "duration_s": shot.duration_s,
                    "speaker": shot.speaker,
                    "dialogue": shot.dialogue,
                    "audio_mode": shot.audio_mode,
                    "image_sha256": img_sha256,
                    "source_image_sha256": t0_record["source"]["sha256"],
                    "t0": t0_record,
                    "prompt_sha256": prompt_sha256
                })

            # 4. Ghi manifest.json
            manifest_data = {
                "schema_version": 2,
                "batch_id": batch_id,
                "expected_result_zip": result_zip_name,
                "total_shots": len(shots),
                "shots": manifest_entries
            }
            zf.writestr("manifest.json", json.dumps(manifest_data, indent=2, ensure_ascii=False).encode("utf-8"))

            # 5. Ghi relay_batch.txt hướng dẫn đầy đủ quy trình VM
            relay_txt = (
                f"MUSE BATCH SHOT REQUEST {batch_id}\n"
                f"Total shots in batch: {len(shots)} (maximum 6 per batch).\n"
                f"Instructions for Muse VM Agent:\n"
                f"1. Unzip the attached {zip_path.name} into workspace/{batch_id}/\n"
                f"2. For each shot entry in manifest.json, call media.generate_video ONCE passing prompt.txt verbatim and assets/00.png as the first image input (plus any references listed in request.json). Treat this batch_id and each request_id as a fresh independent run even if the same shot_id appeared in an earlier batch.\n"
                f"3. Save each video cleanly as <slot_id>.mp4 (e.g. shot_01.mp4 .. shot_{len(shots):02d}.mp4) and write <slot_id>_receipt.json.\n"
                f"4. Before zipping, run ffprobe and SHA-256 on every generated MP4 on the VM to confirm non-zero video stream, duration, width, height, fps.\n"
                f"5. Write batch_receipt.json containing 'batch_id', 'shots' (for valid clips with shot_id, slot_id, request_id, output_file, bytes, sha256, duration_s, width, height, fps, snapshot_id, status='ok') and 'failed_shots' (for any shot that failed to generate).\n"
                f"6. Package all generated MP4 clips, *_receipt.json, and batch_receipt.json into {result_zip_name} and return it as a downloadable attachment.\n"
            )
            zf.writestr("relay_batch.txt", relay_txt.encode("utf-8"))

        zip_path.write_bytes(zip_buffer.getvalue())

        relay_message = (
            f"AFP MUSE BATCH REQUEST {batch_id}\n"
            f"Render all {len(shots)} shots with media.generate_video using the attached {zip_path.name}. "
            f"The external system owns the shots: pass prompts verbatim from prompt.txt, first_frame from assets/00.png, "
            f"name outputs shot_01.mp4 .. shot_{len(shots):02d}.mp4. "
            f"Do not plan, rewrite dialogue, generate extra images/videos, retry, schedule, or publish. "
            f"Use existing account entitlement only; stop at payment, upgrade, or quota warnings. "
            f"Run ffprobe + SHA-256 verification on the VM and record both 'shots' and any 'failed_shots' into batch_receipt.json. "
            f"After all {len(shots)} attempts finish, return exactly {result_zip_name} containing all MP4 files, per-shot receipts, and batch_receipt.json. "
            f"Stop after this batch."
        )

        (output_dir / f"{batch_id}_relay_message.txt").write_text(relay_message, encoding="utf-8")
        (output_dir / f"{batch_id}_manifest.json").write_text(
            json.dumps(manifest_data, indent=2, ensure_ascii=False), encoding="utf-8"
        )
        return zip_path, relay_message

    @staticmethod
    def create_keyframe_handoff(
        batch_id: str,
        keyframes: List[KeyframeItem],
        output_dir: Path
    ) -> Tuple[Path, str]:
        """
        Đóng gói tối đa 4 keyframe/batch để gửi Muse VM gọi `media.generate_image`.
        Trả về `(path_to_zip, relay_message_text)`.
        """
        if len(keyframes) > BatchPackager.MAX_KEYFRAME_BATCH_SIZE:
            raise ValueError(
                f"Một keyframe batch chỉ nhận tối đa {BatchPackager.MAX_KEYFRAME_BATCH_SIZE} ảnh (nhận {len(keyframes)})."
            )
        if not keyframes:
            raise ValueError("Danh sách keyframe không được rỗng.")

        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)
        zip_path = output_dir / f"{batch_id}_kf_handoff.zip"
        result_zip_name = f"{batch_id}_kf_result.zip"

        entries = []
        zip_buffer = io.BytesIO()
        with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zf:
            for idx, kf in enumerate(keyframes, start=1):
                slot_id = f"kf_{idx:02d}"
                folder = f"keyframes/{slot_id}_{kf.kf_id}"

                ref_entries = []
                for r_idx, r_path in enumerate(kf.reference_images or [], start=1):
                    rp = Path(r_path)
                    if not rp.exists():
                        raise FileNotFoundError(f"Không tìm thấy ảnh tham chiếu keyframe: {rp}")
                    rb = rp.read_bytes()
                    arc_ref = f"{folder}/refs/ref_{r_idx:02d}{rp.suffix or '.png'}"
                    zf.writestr(arc_ref, rb)
                    ref_entries.append({
                        "path": f"refs/ref_{r_idx:02d}{rp.suffix or '.png'}",
                        "sha256": compute_sha256(rb)
                    })

                prompt_bytes = kf.prompt.encode("utf-8")
                prompt_sha = compute_sha256(prompt_bytes)
                zf.writestr(f"{folder}/prompt.txt", prompt_bytes)

                req_id = kf.request_id or compute_sha256(f"{batch_id}:{kf.kf_id}:{prompt_sha}".encode())
                req_dict = {
                    "schema_version": 1,
                    "request_id": req_id,
                    "slot_id": slot_id,
                    "kf_id": kf.kf_id,
                    "prompt": kf.prompt,
                    "prompt_sha256": prompt_sha,
                    "aspect": kf.aspect_ratio,
                    "output_format": kf.output_format,
                    "references": ref_entries,
                    "output": f"{kf.kf_id}.{kf.output_format}"
                }
                zf.writestr(f"{folder}/request.json", json.dumps(req_dict, indent=2, ensure_ascii=False).encode("utf-8"))

                entries.append({
                    "kf_index": idx,
                    "slot_id": slot_id,
                    "kf_id": kf.kf_id,
                    "request_id": req_id,
                    "folder": folder,
                    "expected_output": f"{kf.kf_id}.{kf.output_format}",
                    "prompt_sha256": prompt_sha
                })

            manifest_data = {
                "schema_version": 1,
                "batch_id": batch_id,
                "expected_result_zip": result_zip_name,
                "total_keyframes": len(keyframes),
                "keyframes": entries
            }
            zf.writestr("kf_manifest.json", json.dumps(manifest_data, indent=2, ensure_ascii=False).encode("utf-8"))

        zip_path.write_bytes(zip_buffer.getvalue())

        relay_message = (
            f"AFP MUSE KEYFRAME BATCH {batch_id}\n"
            f"Generate all {len(keyframes)} 16:9 PNG keyframes with media.generate_image using the attached {zip_path.name}. "
            f"For each entry in kf_manifest.json, pass its reference images in order + prompt.txt verbatim. "
            f"Save each output strictly as <kf_id>.png (no text, no subtitles, no watermarks). "
            f"Verify image dimensions (16:9) and SHA-256 on the VM into kf_receipt.json, "
            f"package all PNG files and kf_receipt.json into {result_zip_name}, and return it as a downloadable attachment. "
            f"Use existing account entitlement only; stop at payment or quota warnings."
        )
        (output_dir / f"{batch_id}_kf_relay_message.txt").write_text(relay_message, encoding="utf-8")
        (output_dir / f"{batch_id}_kf_manifest.json").write_text(
            json.dumps(manifest_data, indent=2, ensure_ascii=False), encoding="utf-8"
        )
        return zip_path, relay_message

    @staticmethod
    def _safe_extract_zip(zf: zipfile.ZipFile, extract_dir: Path) -> None:
        """Giải nén ZIP an toàn, chặn tấn công ZipSlip (`../` thoát khỏi `extract_dir`)."""
        base_resolved = extract_dir.resolve()
        for member in zf.infolist():
            dest = (extract_dir / member.filename).resolve()
            if not dest.is_relative_to(base_resolved):
                raise ValueError(f"ZipSlip path traversal bị chặn: {member.filename}")
        zf.extractall(extract_dir)

    @staticmethod
    def _load_expected_from_manifest(handoff_manifest_path: Optional[Path]) -> List[Dict[str, Any]]:
        if not handoff_manifest_path:
            return []
        mp = Path(handoff_manifest_path)
        if not mp.exists():
            return []
        if mp.suffix.lower() == ".zip":
            with zipfile.ZipFile(mp, "r") as zf:
                if "manifest.json" in zf.namelist():
                    data = json.loads(zf.read("manifest.json").decode("utf-8"))
                    return data.get("shots", [])
            return []
        data = json.loads(mp.read_text(encoding="utf-8"))
        return data.get("shots", [])

    @staticmethod
    def read_integrity_failed(batch_dir: Path) -> Tuple[bool, set]:
        """The ONE reader of `<batch_dir>/integrity_failed.json`: returns `(ok, names)`. The file is read once and
        must match the schema `{"clips": [str, ...]}`. A missing file is `(True, set())`; any read error, invalid JSON,
        JSON `null`, a non-object or a malformed `clips` is `(False, set())`: the exclusion list is unknown, so the
        whole batch is untrusted (fail closed)."""
        path = Path(batch_dir) / INTEGRITY_FAILED_FILE
        if not path.exists():
            return True, set()
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return False, set()
        clips = data.get("clips") if isinstance(data, dict) else None
        if not isinstance(clips, list) or not all(isinstance(c, str) for c in clips):
            return False, set()
        return True, set(clips)

    @staticmethod
    def batch_dir_of_clip(clip: Path) -> Optional[Path]:
        """`<project>/BATCHES_V2|BATCHES/<bid>/verified_clips/<x>.mp4` -> the batch dir (else None)."""
        clip = Path(clip)
        if clip.parent.name == "verified_clips" and clip.parent.parent.parent.name in ("BATCHES_V2", "BATCHES"):
            return clip.parent.parent
        return None

    @staticmethod
    def clip_currently_excluded(clip: Path, qc_rec: Optional[Dict[str, Any]] = None) -> bool:
        """True when a clip must not be reused now. A batch clip is judged by its batch's CURRENT exclusion list
        (unreadable list = excluded) and quarantine marker. A canonical copy (`<project>/verified_clips/<sid>.mp4`,
        written by qc-audit / promote-take) is judged through its audit record `qc_rec`: the copy's SHA-256 must still
        equal the recorded `copy_sha256`, and the SOURCE batch clip (`clip_path`, and the provenance `source_clip_path`
        that promote-take keeps when it copied from another copy) must not be excluded."""
        clip = Path(clip)
        bdir = BatchPackager.batch_dir_of_clip(clip)
        if bdir is not None:
            list_ok, excluded = BatchPackager.read_integrity_failed(bdir)
            if not list_ok or clip.name in excluded:
                return True
            return (not clip.exists()) and (bdir / "integrity_failed" / clip.name).exists()
        if not isinstance(qc_rec, dict):
            return False
        want = qc_rec.get("copy_sha256")
        if want:
            try:
                if compute_sha256(clip) != want:
                    return True
            except OSError:
                return True
        for key in ("clip_path", "source_clip_path"):  # the source batch clip and the provenance recorded by promote-take
            src = qc_rec.get(key)
            if src and BatchPackager.batch_dir_of_clip(Path(src)) is not None:
                if BatchPackager.clip_currently_excluded(Path(src)):
                    return True
        return False

    @staticmethod
    def record_integrity_failure(batch_dir: Path, clip_name: str) -> None:
        """Add a clip file name to `<batch_dir>/integrity_failed.json` (clip discovery never admits listed clips)."""
        path = Path(batch_dir) / INTEGRITY_FAILED_FILE
        clips: List[str] = []
        if path.exists():
            ok, names = BatchPackager.read_integrity_failed(batch_dir)
            if not ok:
                # Never overwrite an unreadable list: it may hold earlier exclusions that would be lost.
                raise OSError(f"{path} exists but is unreadable or has an invalid schema; not overwritten")
            clips = sorted(names)
        if clip_name not in clips:
            clips.append(clip_name)
        # Plain write (no rename): it must still work when renames fail, which is exactly when it matters most.
        path.write_text(json.dumps({"clips": clips}, indent=2), encoding="utf-8")

    @staticmethod
    def keyframe_receipt_sha_by_file(extract_dir: Path) -> Dict[str, str]:
        """Image file stem (and kf id / slot id) -> SHA-256 recorded by the keyframe receipt (`kf_receipt.json`, shape
        `{"keyframes": [{"kf_id", "output_file", "sha256"}]}`) under an unpacked keyframe result dir."""
        out: Dict[str, str] = {}
        for jf in sorted(Path(extract_dir).glob("**/*receipt*.json")):
            try:
                data = json.loads(jf.read_text(encoding="utf-8"))
            except (OSError, ValueError):
                continue
            out.update(BatchPackager.parse_keyframe_receipt(data))
        return out

    @staticmethod
    def parse_keyframe_receipt(data: Any) -> Dict[str, str]:
        """Keys (output file stem, kf id, slot id) -> SHA-256 for one parsed keyframe receipt document."""
        out: Dict[str, str] = {}
        if not isinstance(data, dict):
            return out
        items = data.get("keyframes")
        if not isinstance(items, list):
            items = data.get("shots") if isinstance(data.get("shots"), list) else [data]
        for item in items:
            if not isinstance(item, dict) or not item.get("sha256"):
                continue
            sha = str(item["sha256"])
            if item.get("output_file"):
                out[Path(str(item["output_file"])).stem] = sha
            for key in ("kf_id", "slot_id"):
                if item.get(key):
                    out[str(item[key])] = sha
        return out

    @staticmethod
    def receipt_sha_by_file(extract_dir: Path) -> Dict[str, str]:
        """Clip file stem -> SHA-256 recorded by the batch receipt(s) under an unpacked result dir."""
        out: Dict[str, str] = {}
        for jf in sorted(Path(extract_dir).glob("**/*receipt*.json")):
            try:
                data = json.loads(jf.read_text(encoding="utf-8"))
            except (OSError, ValueError):
                continue
            if not isinstance(data, dict):
                continue
            items = data.get("shots") if isinstance(data.get("shots"), list) else [data]
            for item in items:
                if not isinstance(item, dict) or not item.get("sha256"):
                    continue
                stem = Path(item.get("output_file") or f"{item.get('shot_id', '')}.mp4").stem
                if stem:
                    out[stem] = item["sha256"]
        return out

    @staticmethod
    def unpack_batch_result(
        result_zip_path: Path,
        extract_dir: Path,
        handoff_manifest_path: Optional[Path] = None,
        expected_shot_ids: Optional[List[str]] = None,
        strict_min_bytes: Optional[int] = None
    ) -> Dict[str, Any]:
        """
        Giải nén kết quả `{batch_id}_result.zip`, đối chiếu chặt chẽ SHA-256, `batch_receipt.json`
        và toàn bộ danh sách shot kỳ vọng từ `manifest.json` để phát hiện shot thiếu/lỗi.
        """
        result_zip_path = Path(result_zip_path)
        if not result_zip_path.exists():
            raise FileNotFoundError(f"Không tìm thấy file kết quả: {result_zip_path}")

        extract_dir = Path(extract_dir)
        extract_dir.mkdir(parents=True, exist_ok=True)

        results: Dict[str, Any] = {
            "result_zip": str(result_zip_path),
            "clips": {},
            "verified_shots": {},
            "receipts": {},
            "missing_shots": [],
            "failed_shots": [],
            "integrity_failed_shots": [],
            "verified": True,
            "errors": []
        }

        try:
            with zipfile.ZipFile(result_zip_path, "r") as zf:
                BatchPackager._safe_extract_zip(zf, extract_dir)
        except Exception as e:
            results["verified"] = False
            results["errors"].append(f"ZIP bị hỏng hoặc không thể giải nén: {e}")
            return results

        # Current exclusion list (same rules as the keyframe unpacker): an unreadable list means the whole batch is
        # untrusted; a listed name is never verified (the file stays where it is, never deleted).
        list_ok, excluded = BatchPackager.read_integrity_failed(extract_dir.parent)
        if not list_ok:
            results["verified"] = False
            results["integrity_list_unreadable"] = True
            results["errors"].append(f"{INTEGRITY_FAILED_FILE} is unreadable or has an invalid schema: "
                                     f"the whole batch is untrusted")
            return results

        mp4_files = sorted(extract_dir.glob("**/*.mp4"))
        json_files = sorted(extract_dir.glob("**/*receipt*.json"))

        # Đọc clips
        excluded_keys: set = set()
        for mp4 in mp4_files:
            sha = compute_sha256(mp4)
            shot_key = mp4.stem
            results["clips"][shot_key] = {
                "path": str(mp4),
                "bytes": mp4.stat().st_size,
                "sha256": sha
            }
            if mp4.name in excluded:
                excluded_keys.add(shot_key)
                results["clips"][shot_key]["excluded"] = True
                results["errors"].append(f"Clip {mp4.name} is listed in {INTEGRITY_FAILED_FILE}: not verified")

        # Đọc receipts & phát hiện failed_shots / kiểm tra SHA-256
        receipt_sha_by_file: Dict[str, str] = {}
        for jf in json_files:
            try:
                data = json.loads(jf.read_text(encoding="utf-8"))
                if jf.name == "batch_receipt.json" or ("shots" in data and isinstance(data["shots"], list)):
                    results["receipts"][jf.stem] = data
                    for item in data.get("shots", []):
                        out_f = Path(item.get("output_file") or f"{item.get('shot_id', '')}.mp4").stem
                        if item.get("sha256"):
                            receipt_sha_by_file[out_f] = item["sha256"]
                        if item.get("status") not in (None, "ok", "OK", "COMPLETED"):
                            results["failed_shots"].append(item)
                    for fitem in data.get("failed_shots", []):
                        results["failed_shots"].append(fitem)
                else:
                    req_id = data.get("request_id") or jf.stem
                    results["receipts"][req_id] = data
                    out_f = Path(data.get("output_file") or f"{data.get('shot_id', '')}.mp4").stem
                    if data.get("sha256") and out_f:
                        receipt_sha_by_file[out_f] = data["sha256"]
            except Exception as e:
                results["errors"].append(f"Lỗi đọc receipt {jf.name}: {e}")

        # Kiểm tra SHA-256 đối chiếu clip vs receipt
        sha_mismatch: set = set()
        unpersisted: List[str] = []
        for clip_key, clip_info in results["clips"].items():
            expected_sha = receipt_sha_by_file.get(clip_key)
            if expected_sha and expected_sha != clip_info["sha256"]:
                sha_mismatch.add(clip_key)
                results["errors"].append(
                    f"SHA-256 không khớp cho {clip_key}: actual={clip_info['sha256'][:12]} != receipt={expected_sha[:12]}"
                )
                # Durable exclusion first (honoured by clip discovery even if the move below fails), then quarantine
                # next to the extract dir so no later clip discovery (qc-audit) can pick it up again.
                src = Path(clip_info["path"])
                persisted = True
                try:
                    BatchPackager.record_integrity_failure(extract_dir.parent, src.name)
                except OSError as e:
                    persisted = False
                    results["errors"].append(f"Không ghi được {INTEGRITY_FAILED_FILE}: {e}")
                qdir = extract_dir.parent / "integrity_failed"
                try:
                    qdir.mkdir(parents=True, exist_ok=True)
                    dst = qdir / src.name
                    os.replace(src, dst)
                    clip_info["path"] = str(dst)
                    clip_info["quarantined"] = True
                except OSError as e:
                    # Never delete a received clip (contract v8 section 10 #11): it stays where it is, listed in
                    # `integrity_failed.json`, and every reader of clip candidates honours that exclusion.
                    clip_info["quarantine_failed"] = True
                    results["errors"].append(f"Không cách ly được {clip_key} (file giữ nguyên, đã ghi vào "
                                             f"{INTEGRITY_FAILED_FILE}): {e}" if persisted else
                                             f"Không cách ly được {clip_key}: {e}")
                    if not persisted:
                        unpersisted.append(src.name)

        if unpersisted:
            # Neither the exclusion list nor the quarantine move worked: nothing marks these clips as untrusted.
            results["verified"] = False
            results["status"] = INTEGRITY_UNPERSISTED
            results["integrity_unpersisted"] = sorted(unpersisted)
            for k in sha_mismatch:
                results["clips"][k]["verified"] = False
            raise IntegrityUnpersistedError(
                f"Integrity-failed clip(s) {sorted(unpersisted)} could be neither listed nor quarantined; stopping",
                results=results, clips=unpersisted)

        # Kiểm tra danh sách shot kỳ vọng từ manifest / expected_shot_ids
        manifest_entries = BatchPackager._load_expected_from_manifest(handoff_manifest_path)
        min_bytes = strict_min_bytes if strict_min_bytes is not None else (
            BatchPackager.MIN_VIDEO_BYTES if (manifest_entries or expected_shot_ids) else 1
        )

        expected_items: List[Tuple[str, Optional[str]]] = []
        if manifest_entries:
            for m in manifest_entries:
                sid = m.get("shot_id") or m.get("slot_id")
                slot_id = m.get("slot_id")
                if sid:
                    expected_items.append((sid, slot_id))
        elif expected_shot_ids:
            for idx, sid in enumerate(expected_shot_ids, start=1):
                expected_items.append((sid, f"shot_{idx:02d}"))

        for sid, slot_id in expected_items:
            matched_key = None
            for candidate in [sid, slot_id]:
                if candidate and candidate in results["clips"]:
                    matched_key = candidate
                    break
            if not matched_key:
                # Thử khớp tiền tố
                for k in results["clips"]:
                    if sid in k or (slot_id and k == slot_id):
                        matched_key = k
                        break

            if not matched_key:
                results["missing_shots"].append(sid)
            else:
                clip_info = results["clips"][matched_key]
                if matched_key in sha_mismatch or matched_key in excluded_keys:
                    # Integrity failure: never verified (other valid clips of the batch are still kept).
                    results["integrity_failed_shots"].append(sid)
                elif clip_info["bytes"] < min_bytes:
                    results["errors"].append(
                        f"Clip {matched_key} quá nhỏ ({clip_info['bytes']} < {min_bytes} bytes)"
                    )
                else:
                    results["verified_shots"][sid] = clip_info

        if results["missing_shots"] or results["failed_shots"] or results["errors"]:
            results["verified"] = False

        return results

    @staticmethod
    def unpack_keyframe_result(
        result_zip_path: Path,
        extract_dir: Path,
        expected_kf_ids: Optional[List[str]] = None,
        handoff_manifest_path: Optional[Path] = None,
    ) -> Dict[str, Any]:
        """Giải nén `{batch_id}_kf_result.zip`, ánh xạ `slot_id -> kf_id` nếu VM đặt tên theo slot, và kiểm tra PNG trả về."""
        result_zip_path = Path(result_zip_path)
        if not result_zip_path.exists():
            raise FileNotFoundError(f"Không tìm thấy keyframe zip: {result_zip_path}")

        extract_dir = Path(extract_dir)
        extract_dir.mkdir(parents=True, exist_ok=True)
        out: Dict[str, Any] = {
            "result_zip": str(result_zip_path),
            "keyframes": {},
            "missing_keyframes": [],
            "errors": [],
            "verified": True
        }

        try:
            with zipfile.ZipFile(result_zip_path, "r") as zf:
                BatchPackager._safe_extract_zip(zf, extract_dir)
        except Exception as e:
            out["verified"] = False
            out["errors"].append(f"Keyframe ZIP bị hỏng hoặc không hợp lệ: {e}")
            return out

        slot_to_kfid: Dict[str, str] = {}
        if handoff_manifest_path and Path(handoff_manifest_path).exists():
            try:
                kfm = json.loads(Path(handoff_manifest_path).read_text(encoding="utf-8"))
                for entry in kfm.get("keyframes", []):
                    if entry.get("slot_id") and entry.get("kf_id"):
                        slot_to_kfid[str(entry["slot_id"])] = str(entry["kf_id"])
            except Exception:
                pass
        elif expected_kf_ids:
            for idx, kfid in enumerate(expected_kf_ids, start=1):
                slot_to_kfid[f"kf_{idx:02d}"] = kfid

        # Exclusion list + receipt SHA (same rules as video clips): an excluded name or a SHA mismatch is never
        # verified. The file is kept (never deleted) and the failure is recorded in `integrity_failed.json`.
        list_ok, excluded = BatchPackager.read_integrity_failed(extract_dir.parent)
        if not list_ok:
            out["verified"] = False
            out["integrity_list_unreadable"] = True
            out["errors"].append(f"{INTEGRITY_FAILED_FILE} is unreadable or has an invalid schema: "
                                 f"the whole keyframe batch is untrusted")
            return out
        receipt_sha = BatchPackager.keyframe_receipt_sha_by_file(extract_dir)
        out["integrity_failed_keyframes"] = []

        imgs = sorted(extract_dir.glob("**/*.png")) + sorted(extract_dir.glob("**/*.jpg")) + sorted(extract_dir.glob("**/*.webp"))
        for img in imgs:
            resolved_id = slot_to_kfid.get(img.stem, img.stem)
            if img.name in excluded:
                out["integrity_failed_keyframes"].append(resolved_id)
                out["errors"].append(f"Keyframe {img.name} is listed in {INTEGRITY_FAILED_FILE}: not verified")
                continue
            if img.stat().st_size < BatchPackager.MIN_IMAGE_BYTES:
                out["errors"].append(f"Keyframe {img.name} quá nhỏ ({img.stat().st_size} bytes)")
                continue
            sha = compute_sha256(img)
            expected_sha = receipt_sha.get(img.stem) or receipt_sha.get(resolved_id)
            if expected_sha and expected_sha != sha:
                out["integrity_failed_keyframes"].append(resolved_id)
                out["errors"].append(
                    f"SHA-256 mismatch for keyframe {img.name}: actual={sha[:12]} != receipt={expected_sha[:12]}")
                try:
                    BatchPackager.record_integrity_failure(extract_dir.parent, img.name)
                except OSError as e:
                    out["errors"].append(f"Could not record {INTEGRITY_FAILED_FILE}: {e}")
                continue
            out["keyframes"][resolved_id] = {
                "path": str(img),
                "bytes": img.stat().st_size,
                "sha256": sha
            }

        if expected_kf_ids:
            for kfid in expected_kf_ids:
                if kfid not in out["keyframes"]:
                    matched_sub = next((k for k in out["keyframes"] if kfid in k), None)
                    if matched_sub:
                        out["keyframes"][kfid] = out["keyframes"][matched_sub]
                    else:
                        out["missing_keyframes"].append(kfid)

        if out["missing_keyframes"] or out["errors"] or not out["keyframes"]:
            out["verified"] = False
        return out

    @staticmethod
    def build_retry_batches(
        retry_shots: List[ShotItem],
        batch_prefix: str,
        output_root: Path,
        max_batch_size: int = MAX_BATCH_SIZE
    ) -> List[Tuple[str, Path, str, List[ShotItem]]]:
        """Tự động chia các shot lỗi/thiếu thành các lô retry <= 6 shots."""
        output_root = Path(output_root)
        batches: List[Tuple[str, Path, str, List[ShotItem]]] = []
        chunk_size = max(1, min(max_batch_size, BatchPackager.MAX_BATCH_SIZE))
        for b_idx in range(0, len(retry_shots), chunk_size):
            chunk = retry_shots[b_idx:b_idx + chunk_size]
            batch_num = (b_idx // chunk_size) + 1
            batch_id = f"{batch_prefix}_RETRY_{batch_num:02d}"
            batch_dir = output_root / batch_id
            zip_path, relay_msg = BatchPackager.create_batch_handoff(batch_id, chunk, batch_dir)
            batches.append((batch_id, zip_path, relay_msg, chunk))
        return batches
