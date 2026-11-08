"""P15-02: a start/end still pair is compared before the shot is sent; findings are WARN, never an approval."""
from types import SimpleNamespace

import numpy as np
import pytest
from PIL import Image

from film_pipeline.production.stills import PAIR_GLOBAL_MAX, pair_check

PINNED = SimpleNamespace(object="shutter", roi=(0.4, 0.0, 0.7, 0.5), direction="still")
MOVING = SimpleNamespace(object="shutter", roi=(0.4, 0.0, 0.7, 0.5), direction="down")


def _still(path, *, shutter=200, body=90, light=0):
    img = np.full((180, 320), 60 + light, np.uint8)
    img[0:80, 130:220] = shutter          # the shutter, inside the ROI
    img[100:170, 140:200] = body          # a person below it
    Image.fromarray(img).save(path)
    return path


def names(result):
    return [f["check"] for f in result["findings"]]


def test_same_image_is_only_noted(tmp_path):
    a = _still(tmp_path / "a.png")
    result = pair_check(a, a, PINNED)
    assert names(result) == ["SAME_IMAGE"] and result["global_diff"] == 0 and result["roi_diff"] == 0


def test_a_small_pose_change_passes(tmp_path):
    result = pair_check(_still(tmp_path / "a.png"), _still(tmp_path / "b.png", body=120), PINNED)
    assert names(result) == []


def test_a_pinned_prop_drawn_differently_is_flagged(tmp_path):
    result = pair_check(_still(tmp_path / "a.png"), _still(tmp_path / "b.png", shutter=90), PINNED)
    assert "PINNED_PROP_DIFFERS" in names(result)
    assert all(f["severity"] == "WARN" for f in result["findings"])


def test_a_prop_meant_to_move_is_not_flagged(tmp_path):
    # film04 SC01_g1: the shutter is lowered in the shot, so its ROI differs by design (27 on the real pair)
    result = pair_check(_still(tmp_path / "a.png"), _still(tmp_path / "b.png", shutter=90), MOVING)
    assert "PINNED_PROP_DIFFERS" not in names(result)


def test_a_light_change_is_a_large_delta(tmp_path):
    result = pair_check(_still(tmp_path / "a.png"), _still(tmp_path / "b.png", light=PAIR_GLOBAL_MAX + 25), None)
    assert names(result) == ["LARGE_DELTA"] and "roi_diff" not in result


@pytest.mark.parametrize("gid", ["SC01_g1", "SC01_g2"])
def test_film04_accepted_pairs_pass(gid):
    from pathlib import Path

    from film_pipeline.production.package import load_package
    from film_pipeline.production.stills import pair_check_for
    root = Path(__file__).resolve().parents[1] / "films" / "film04_last_ticket"
    if not (root / "media" / "stills" / f"end_{gid}.png").is_file():
        pytest.skip("film04 media is not in this checkout")
    result = pair_check_for(load_package(root), gid)
    assert result is not None and [f for f in result["findings"] if f["severity"] == "WARN"] == []
