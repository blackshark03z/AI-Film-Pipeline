import io
import json
import zipfile
import pytest
from pathlib import Path
from PIL import Image, ImageDraw
from muse_studio.core.batch_packager import BatchPackager, ShotItem, compute_sha256


def _png(path, size, mode="RGB"):
    img = Image.new(mode, size, (60, 80, 100) if mode == "RGB" else (60, 80, 100, 255))
    d = ImageDraw.Draw(img)
    w, h = size
    d.rectangle([w // 4, h // 4, w // 2, 3 * h // 4], fill=(200, 150, 120) if mode == "RGB" else (200, 150, 120, 255))
    img.save(path, format="PNG")
    return path


def _sent(zip_path, folder):
    with zipfile.ZipFile(zip_path) as zf:
        data = zf.read(f"{folder}/assets/00.png")
        request = json.loads(zf.read(f"{folder}/request.json"))
        manifest = json.loads(zf.read("manifest.json"))
    return data, request, manifest["shots"][0]


def test_t0_landscape_is_normalized_and_both_hashes_recorded(tmp_path):
    src = _png(tmp_path / "kf.png", (1672, 941))
    shot = ShotItem(shot_id="01A", prompt="p", first_frame_path=src)
    zp, _ = BatchPackager.create_batch_handoff("T0N", [shot], tmp_path / "out")
    data, request, row = _sent(zp, "shots/shot_01_01A")
    with Image.open(io.BytesIO(data)) as im:
        assert im.size == (1280, 720) and im.format == "PNG" and im.mode == "RGB"
    sent_sha = compute_sha256(data)
    assert row["image_sha256"] == request["first_frame"]["sha256"] == sent_sha
    assert row["source_image_sha256"] == request["first_frame"]["source_sha256"] == compute_sha256(src)
    assert sent_sha != compute_sha256(src)
    assert row["t0"]["normalization"]["status"] == "NORMALIZED"
    assert row["t0"]["normalization"]["upscaled"] is False
    assert (request["first_frame"]["width"], request["first_frame"]["height"]) == (1280, 720)
    # request_id is derived from the bytes actually sent
    assert row["request_id"] == compute_sha256(f"T0N:01A:{compute_sha256(b'p')}:{sent_sha}".encode())


def test_t0_already_normalized_png_is_sent_byte_for_byte(tmp_path):
    src = _png(tmp_path / "kf.png", (1280, 720))
    zp, _ = BatchPackager.create_batch_handoff("T0P", [ShotItem("S", "p", src)], tmp_path / "out")
    data, _, row = _sent(zp, "shots/shot_01_S")
    assert data == src.read_bytes()
    assert row["t0"]["normalization"]["status"] == "ALREADY_NORMALIZED"


def test_t0_rgba_at_target_size_is_converted(tmp_path):
    src = _png(tmp_path / "kf.png", (1280, 720), mode="RGBA")
    zp, _ = BatchPackager.create_batch_handoff("T0A", [ShotItem("S", "p", src)], tmp_path / "out")
    data, _, row = _sent(zp, "shots/shot_01_S")
    with Image.open(io.BytesIO(data)) as im:
        assert im.mode == "RGB" and im.size == (1280, 720)
    assert row["t0"]["normalization"]["status"] == "NORMALIZED"


def test_t0_portrait_and_small_source_upscaled(tmp_path):
    src = _png(tmp_path / "kf.png", (450, 800))
    shot = ShotItem("V", "p", src, aspect_ratio="9:16")
    zp, _ = BatchPackager.create_batch_handoff("T0V", [shot], tmp_path / "out")
    data, _, row = _sent(zp, "shots/shot_01_V")
    with Image.open(io.BytesIO(data)) as im:
        assert im.size == (720, 1280)
    assert row["t0"]["normalization"]["upscaled"] is True


def test_t0_large_aspect_mismatch_is_rejected(tmp_path):
    src = _png(tmp_path / "kf.png", (1600, 1200))
    with pytest.raises(ValueError, match="Recompose"):
        BatchPackager.create_batch_handoff("T0X", [ShotItem("S", "p", src)], tmp_path / "out")


def test_t0_undecodable_image_is_rejected(tmp_path):
    src = tmp_path / "bad.png"
    src.write_bytes(b"\x89PNG\r\n\x1a\n" + b"\x00" * 200)
    with pytest.raises(ValueError, match="not a decodable image"):
        BatchPackager.create_batch_handoff("T0B", [ShotItem("S", "p", src)], tmp_path / "out")


def test_t0_exact_one_percent_mismatch_is_accepted(tmp_path):
    src = _png(tmp_path / "kf.png", (1616, 900))
    zp, _ = BatchPackager.create_batch_handoff("T0E", [ShotItem("S", "p", src)], tmp_path / "out")
    data, _, _ = _sent(zp, "shots/shot_01_S")
    with Image.open(io.BytesIO(data)) as im:
        assert im.size == (1280, 720)


def test_t0_transparent_pixels_are_rejected(tmp_path):
    src = tmp_path / "kf.png"
    Image.new("RGBA", (1280, 720), (255, 0, 0, 0)).save(src, format="PNG")
    with pytest.raises(ValueError, match="transparent"):
        BatchPackager.create_batch_handoff("T0T", [ShotItem("S", "p", src)], tmp_path / "out")


def test_t0_16bit_image_is_rejected(tmp_path):
    src = tmp_path / "kf.png"
    Image.new("I;16", (1280, 720), 32768).save(src, format="PNG")
    with pytest.raises(ValueError, match="unsupported mode"):
        BatchPackager.create_batch_handoff("T0I", [ShotItem("S", "p", src)], tmp_path / "out")


def test_t0_exif_rotated_png_is_not_passed_through(tmp_path):
    src = tmp_path / "kf.png"
    exif = Image.Exif()
    exif[0x0112] = 6
    Image.new("RGB", (1280, 720), (60, 80, 100)).save(src, format="PNG", exif=exif)
    with pytest.raises(ValueError, match="Recompose"):
        BatchPackager.create_batch_handoff("T0R", [ShotItem("S", "p", src)], tmp_path / "out")


def test_t0_truncated_png_is_rejected(tmp_path):
    full = _png(tmp_path / "full.png", (1280, 720)).read_bytes()
    src = tmp_path / "kf.png"
    src.write_bytes(full[: len(full) - 40])
    with pytest.raises(ValueError, match="not a decodable image"):
        BatchPackager.create_batch_handoff("T0C", [ShotItem("S", "p", src)], tmp_path / "out")


def test_t0_unverified_aspect_passes_through(tmp_path):
    src = _png(tmp_path / "kf.png", (1000, 1000))
    zp, _ = BatchPackager.create_batch_handoff("T0S", [ShotItem("S", "p", src, aspect_ratio="1:1")], tmp_path / "out")
    data, _, row = _sent(zp, "shots/shot_01_S")
    assert data == src.read_bytes()
    assert row["t0"]["normalization"]["status"] == "UNVERIFIED_ASPECT_PASSTHROUGH"

def test_create_and_unpack_batch(tmp_path):
    # Tạo 2 dummy image file
    img1 = tmp_path / "img1.png"
    img2 = tmp_path / "img2.png"
    Image.new("RGB", (1280, 720), (10, 20, 30)).save(img1, format="PNG")
    Image.new("RGB", (1280, 720), (30, 20, 10)).save(img2, format="PNG")

    shots = [
        ShotItem(
            shot_id="shot_01",
            prompt="Prompt for shot 1 with 16:9 locked-off static tripod",
            first_frame_path=img1,
            speaker="BRIANNA",
            dialogue="Welcome aboard."
        ),
        ShotItem(
            shot_id="shot_02",
            prompt="Prompt for shot 2 with 16:9 locked-off static tripod",
            first_frame_path=img2,
            speaker="ATTENDANT",
            dialogue="Show me your pass."
        )
    ]

    zip_path, relay_msg = BatchPackager.create_batch_handoff(
        batch_id="TEST_BATCH_01",
        shots=shots,
        output_dir=tmp_path / "out"
    )

    assert zip_path.exists()
    assert "AFP MUSE BATCH REQUEST TEST_BATCH_01" in relay_msg

    # Kiểm tra cấu trúc trong zip
    with zipfile.ZipFile(zip_path, "r") as zf:
        namelist = zf.namelist()
        assert "manifest.json" in namelist
        assert "relay_batch.txt" in namelist
        assert "shots/shot_01_shot_01/assets/00.png" in namelist
        assert "shots/shot_01_shot_01/prompt.txt" in namelist
        assert "shots/shot_01_shot_01/request.json" in namelist

        manifest = json.loads(zf.read("manifest.json").decode("utf-8"))
        assert manifest["total_shots"] == 2
        assert manifest["batch_id"] == "TEST_BATCH_01"

    # Test unpack dummy result
    res_zip = tmp_path / "dummy_result.zip"
    with zipfile.ZipFile(res_zip, "w") as zf:
        zf.writestr("shot_01.mp4", b"dummy mp4 data 1")
        receipt_data = {"request_id": "req_01", "shot_id": "shot_01", "status": "ok"}
        zf.writestr("shot_01_receipt.json", json.dumps(receipt_data))

    unpacked = BatchPackager.unpack_batch_result(res_zip, tmp_path / "extracted")
    assert "shot_01" in unpacked["clips"]
    assert unpacked["clips"]["shot_01"]["bytes"] == len(b"dummy mp4 data 1")
    assert "req_01" in unpacked["receipts"]

def test_batch_size_limit(tmp_path):
    img = tmp_path / "dummy.png"
    img.write_bytes(b"dummy")
    shots = [
        ShotItem(shot_id=f"s_{i}", prompt="p", first_frame_path=img)
        for i in range(7)
    ]
    with pytest.raises(ValueError, match="tối đa 6 shot"):
        BatchPackager.create_batch_handoff("OVERFLOW", shots, tmp_path)


def test_retry_batches_rotate_request_id(tmp_path):
    img = tmp_path / "img.png"
    _png(img, (1280, 720))
    shots = [ShotItem(shot_id="SHOT_136_CH11", prompt="Sample static shot", first_frame_path=img)]

    z1, _ = BatchPackager.create_batch_handoff("BATCH_R01", shots, tmp_path / "r1")
    z2, _ = BatchPackager.create_batch_handoff("BATCH_R02", shots, tmp_path / "r2")

    with zipfile.ZipFile(z1, "r") as zf1, zipfile.ZipFile(z2, "r") as zf2:
        m1 = json.loads(zf1.read("manifest.json").decode("utf-8"))
        m2 = json.loads(zf2.read("manifest.json").decode("utf-8"))
        assert m1["shots"][0]["request_id"] != m2["shots"][0]["request_id"]
        assert "fresh independent run" in zf2.read("relay_batch.txt").decode("utf-8")
