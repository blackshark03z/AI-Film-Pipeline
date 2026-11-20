from __future__ import annotations

import json
import shutil
from pathlib import Path

import pytest

cv2 = pytest.importorskip("cv2")
np = pytest.importorskip("numpy")

from film_pipeline.production import dailies_triage as DT  # noqa: E402
from film_pipeline.production import edge_intrusion as EI  # noqa: E402
from film_pipeline.production import takes as T  # noqa: E402
from film_pipeline.production.package import load_package  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
FILM03 = ROOT / "films" / "film03_front_desk"
W, H, FPS, DUR = 640, 360, 24, 4.0
ENTER_S = 1.0


def _texture(width: int, height: int, seed: int = 7) -> np.ndarray:
    rng = np.random.default_rng(seed)
    small = rng.integers(40, 215, size=(height // 8, width // 8, 3), dtype=np.uint8)
    big = cv2.resize(small, (width, height), interpolation=cv2.INTER_CUBIC)
    return cv2.GaussianBlur(big, (7, 7), 0)


def _write_clip(path: Path, *, pan_px_per_frame: float = 0.0, intruder: str | None = None, seed: int = 7) -> Path:
    canvas = _texture(W + 200, H, seed)
    writer = cv2.VideoWriter(str(path), cv2.VideoWriter_fourcc(*"mp4v"), FPS, (W, H))
    assert writer.isOpened()
    n = int(DUR * FPS)
    for i in range(n):
        t = i / FPS
        x0 = int(round(min(200, i * pan_px_per_frame)))
        frame = canvas[:, x0:x0 + W].copy()
        # a "subject" in the centre that sways a little (talking head stand-in)
        cx = W // 2 + int(6 * np.sin(2 * np.pi * t))
        cv2.ellipse(frame, (cx, H // 2 + 20), (70, 110), 0, 0, 360, (90, 120, 170), -1)
        if intruder and t >= ENTER_S:
            depth = int(min(1.0, (t - ENTER_S) / 0.4) * 0.14 * W)  # slides in to 14% of the width
            centre_x = W + 90 - depth if intruder == "right" else -90 + depth
            cv2.ellipse(frame, (centre_x, H // 2 - 10), (90, 130), 0, 0, 360, (35, 45, 60), -1)
        writer.write(frame)
    writer.release()
    return path


def test_static_scene_with_intruder_from_right_is_flagged(tmp_path):
    clip = _write_clip(tmp_path / "intrude.mp4", intruder="right")
    res = EI.detect_clip(clip, visible_count=1)
    assert res["verdict"] == "SUSPECT"
    assert res["sides"] == ["right"]
    assert res["detector"] == "edge_intrusion" and res["detector_version"] == EI.DETECTOR_VERSION
    assert res["clip_sha256"] == EI.sha256_file(clip)
    assert res["analysis_fps"] >= 6.0
    t0, t1 = res["time_ranges"][0]
    assert ENTER_S - 0.2 <= t0 <= ENTER_S + 0.8
    assert t1 >= DUR - 0.3


def test_panning_scene_with_intruder_from_left_is_flagged(tmp_path):
    clip = _write_clip(tmp_path / "pan_intrude.mp4", pan_px_per_frame=1.5, intruder="left")
    res = EI.detect_clip(clip, visible_count=1)
    assert res["verdict"] == "SUSPECT"
    assert res["sides"] == ["left"]


def test_clean_static_and_clean_pan_are_not_flagged(tmp_path):
    for name, pan in (("static.mp4", 0.0), ("pan.mp4", 1.5)):
        res = EI.detect_clip(_write_clip(tmp_path / name, pan_px_per_frame=pan), visible_count=1)
        assert res["verdict"] == "CLEAR", (name, res["side_levels"], res["time_ranges"])
        assert res["sides"] == [] and res["time_ranges"] == []


def test_missing_face_model_degrades_to_edge_band(tmp_path):
    clip = _write_clip(tmp_path / "intrude.mp4", intruder="right")
    params = EI.with_params(use_faces=True)
    res = EI.detect_clip(clip, visible_count=1, params=params, face_model_path=tmp_path / "missing.onnx")
    assert res["face_status"] == "missing_model"
    assert res["verdict"] == "SUSPECT" and res["sides"] == ["right"]


def test_signal_shape_is_exact(tmp_path):
    clip = _write_clip(tmp_path / "intrude.mp4", intruder="right")
    res = EI.detect_clip(clip, visible_count=1)
    sig = EI.make_signal(res, "SC01_g01_t1", "WARN")
    assert set(sig) == {"code", "detector", "detector_version", "take_id", "clip_sha256", "sides",
                        "time_ranges", "score", "severity"}
    assert sig["code"] == "EDGE_INTRUSION_SUSPECT" and sig["detector"] == "edge_intrusion"
    assert isinstance(sig["score"], float) and all(len(r) == 2 for r in sig["time_ranges"])
    json.dumps(sig)
    with pytest.raises(ValueError):
        EI.make_signal(res, "x", "FAIL")


def test_triage_of_single_visible_take_includes_signal(tmp_path):
    if not (shutil.which("ffmpeg") and shutil.which("ffprobe")):
        pytest.skip("ffmpeg/ffprobe not on PATH")
    root = tmp_path / "film"
    root.mkdir()
    for name in ("film.json", "script.fountain", "01_story.json", "02_direction.json", "03_preprod.json", "04_shots.json"):
        shutil.copyfile(FILM03 / name, root / name)
    pkg = load_package(root)
    gid = next(g.generation_id for g in pkg.typed["shots"].generations if len(g.visible) == 1)
    multi = next(g.generation_id for g in pkg.typed["shots"].generations if len(g.visible) > 1)
    takes_dir = root / "media" / "takes"
    takes_dir.mkdir(parents=True)
    clip = _write_clip(takes_dir / f"{gid}_t1.mp4", intruder="right")
    T.register_take(root, pkg.header.film_id, gid, clip, prompt_text="p", route="r", model="m", credits=0.0)
    clip2 = _write_clip(takes_dir / f"{multi}_t1.mp4", intruder="right", seed=11)
    T.register_take(root, pkg.header.film_id, multi, clip2, prompt_text="p2", route="r", model="m", credits=0.0)

    report = DT.triage_take(load_package(root), f"{gid}_t1")
    sigs = [s for s in report["signals"] if s["code"] == "EDGE_INTRUSION_SUSPECT"]
    assert len(sigs) == 1
    sig = sigs[0]
    assert sig["take_id"] == f"{gid}_t1" and sig["sides"] == ["right"]
    assert sig["clip_sha256"] == report["output_sha256"]
    assert sig["severity"] == DT.EDGE_INTRUSION_SEVERITY
    assert report["metrics"]["edge_intrusion"]["verdict"] == "SUSPECT"
    if sig["severity"] == "WARN":
        assert sig in report["warnings"]
    assert report["auto_pass_forbidden"] is True
    assert not any((root / "takes" / "reviews").glob("*.json"))

    multi_report = DT.triage_take(load_package(root), f"{multi}_t1")
    assert not any(s["code"] == "EDGE_INTRUSION_SUSPECT" for s in multi_report["signals"])
