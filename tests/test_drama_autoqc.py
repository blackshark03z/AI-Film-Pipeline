"""WP4 auto-QC: pure logic always; model-dependent tests need cv2 + models."""
from pathlib import Path

import pytest

from film_pipeline.drama import autoqc as q
from film_pipeline.drama.kpi import DefectRecord, FilmKPI


def box(cx: float, ratio: float, score: float = 0.9) -> q.FaceBox:
    return q.FaceBox(x=cx * 1000 - 50, y=100, w=100, h=ratio * 720,
                     score=score, center_x_norm=cx, height_ratio=ratio)


@pytest.mark.parametrize("ratio,expected", [
    (0.60, "ECU"), (0.40, "CU"), (0.25, "MCU"), (0.12, "MS"), (0.05, "WS"),
    (None, "NO_FACE")])
def test_shot_scale_banding(ratio, expected):
    assert q.shot_scale_from_ratio(ratio) == expected


def test_scale_distance_and_judge():
    assert q.scale_distance("CU", "MCU") == 1
    assert q.scale_distance("CU", "WS") == 3
    assert q.scale_distance("CU", "NO_FACE") is None
    assert q.judge_scale("CU", ["MCU", "MCU", "CU", "NO_FACE"]) == ("MCU", 1)
    assert q.judge_scale("WS", ["NO_FACE"] * 3) == ("NO_FACE", 0)
    assert q.judge_scale("CU", ["NO_FACE"] * 3)[1] is None


def test_cosine():
    assert q.cosine([1, 0], [1, 0]) == pytest.approx(1.0)
    assert q.cosine([1, 0], [0, 1]) == pytest.approx(0.0)
    assert q.cosine([1, 0], [-1, 0]) == pytest.approx(-1.0)
    assert q.cosine([0, 0], [1, 0]) == 0.0


def test_assign_faces_by_side():
    left, right = box(0.25, 0.15), box(0.7, 0.2)
    got = q.assign_faces_by_side([left, right],
                                 {"NORA": "left", "DOYLE": "right"})
    assert got["NORA"] is left and got["DOYLE"] is right


def test_assign_faces_single_face_is_left_to_caller():
    assert q.assign_faces_by_side([box(0.7, 0.2)],
                                  {"NORA": "left", "DOYLE": "right"}) == {}


def test_assign_faces_extra_face_picks_biggest_on_side():
    a, b, c = box(0.2, 0.15), box(0.6, 0.1), box(0.85, 0.2)
    got = q.assign_faces_by_side([a, b, c],
                                 {"NORA": "left", "DOYLE": "right"})
    assert got["NORA"] is a and got["DOYLE"] is c


def test_people_faces_drops_wall_portraits():
    kept = q.people_faces([box(0.3, 0.03), box(0.5, 0.15), box(0.8, 0.2)])
    assert [b.height_ratio for b in kept] == [0.15, 0.2]


def test_kpi_properties():
    kpi = FilmKPI(film_id="f", generations_planned=10, generations_sent=14,
                  generations_blocked=0, generations_first_pass_accepted=8,
                  credits_total=228, credits_investigation=60,
                  usable_seconds=80, rerenders=4,
                  defects=[DefectRecord(generation_id="g", category="SET",
                                        stage_missed="s", fixed_by="x")])
    assert kpi.first_pass_usable_rate == pytest.approx(0.8)
    assert kpi.credits_per_usable_second == pytest.approx(2.1)
    assert kpi.rerenders_per_100s == pytest.approx(5.0)
    assert kpi.defects_by_category() == {"SET": 1}


def test_kpi_zero_division_safe():
    kpi = FilmKPI(film_id="f", generations_planned=0, generations_sent=0,
                  generations_blocked=0, generations_first_pass_accepted=0,
                  credits_total=0, credits_investigation=0,
                  usable_seconds=0, rerenders=0)
    assert (kpi.first_pass_usable_rate, kpi.credits_per_usable_second,
            kpi.rerenders_per_100s) == (0.0, 0.0, 0.0)


def test_missing_model_error_names_fetch_tool(monkeypatch, tmp_path):
    monkeypatch.setenv("FILM_PIPELINE_MODELS", str(tmp_path))
    with pytest.raises(FileNotFoundError, match="drama_fetch_qc_models"):
        q._model_path(q.YUNET_FILE)


TAKES = Path(__file__).resolve().parents[1] / \
    "docs/drama/film01_takes/noref"


@pytest.fixture
def models():
    pytest.importorskip("cv2")
    if not q.models_available() or not (TAKES / "SC01_g1.mp4").exists():
        pytest.skip("QC models or film01 clips not available")


def test_film01_identity_and_wrong_doyle(models):
    side = {"NORA": "left", "DOYLE": "right"}
    anchors = [q.anchor_from_clip(c, TAKES / "SC01_g1.mp4", 2.5, s)
               for c, s in side.items()]
    ok = q.identity_report(TAKES / "SC03_g1.mp4", anchors, side_of=side)
    assert not ok.issues
    bad = q.identity_report(TAKES / "SC03_g2_rejected_wrong_doyle.mp4",
                            anchors, side_of=side)
    assert [i.check for i in bad.issues] == ["IDENTITY_DRIFT"]
    assert all(i.severity == "WARN" for i in bad.issues)


def test_film01_set_similarity_identical_frames(models):
    frame = q.first_frame(TAKES / "SC03_g1.mp4")
    sim = q.set_similarity(frame, frame)
    assert sim.inliers > 100 and sim.hsv_correlation > 0.9
