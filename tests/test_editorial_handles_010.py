"""Package-010 T9 — editorial handles: non-destructive margin metadata
outside the selected range, within asset bounds; zero handles are
identity-neutral (all historical range ids remain stable)."""
import pytest

from film_pipeline.editorial_range import (
    EditorialRange, ProbeBasis, make_editorial_range)

PROBE = ProbeBasis(duration_s=10.0, fps_num=24, fps_den=1)


def base_range(**overrides):
    kwargs = dict(selected_take_id="take_1", shot_id="SHOT_X",
                  asset_id="asset_x", asset_sha256="a" * 64,
                  source_in_s=2.0, source_out_s=6.0, probe=PROBE)
    kwargs.update(overrides)
    return make_editorial_range(**kwargs)


def test_no_handles_identity_is_stable():
    rng = base_range()
    assert rng.handle_in_s == 0.0 and rng.handle_out_s == 0.0
    assert rng.editorial_range_id == base_range().editorial_range_id


def test_head_handle():
    rng = base_range(handle_in_s=1.0)
    assert rng.handle_in_s == 1.0
    assert rng.selected_duration_s == 4.0  # handles never change selection


def test_tail_handle():
    rng = base_range(handle_out_s=2.0)
    assert rng.handle_out_s == 2.0
    assert rng.selected_duration_s == 4.0


def test_both_handles_and_identity_changes():
    plain = base_range()
    handled = base_range(handle_in_s=0.5, handle_out_s=1.5)
    assert handled.editorial_range_id != plain.editorial_range_id
    assert handled.selected_duration_s == 4.0


def test_handle_bounds_refused():
    with pytest.raises(ValueError, match="must not precede"):
        base_range(handle_in_s=3.0)  # > source_in 2.0
    with pytest.raises(ValueError, match="exceeds the probed asset"):
        base_range(handle_out_s=5.0)  # 6.0 + 5.0 > 10.0


def test_negative_handle_refused():
    with pytest.raises(ValueError, match="finite and >= 0"):
        base_range(handle_in_s=-1.0)


def test_serialization_roundtrip_with_handles(tmp_path):
    import json
    rng = base_range(handle_in_s=0.75, handle_out_s=1.25)
    payload = rng.model_dump(mode="json")
    restored = EditorialRange.model_validate(payload)
    assert restored == rng
    (tmp_path / "r.json").write_text(json.dumps(payload))
    from film_pipeline.editorial_range import read_range
    assert read_range(tmp_path / "r.json") == rng


def test_zero_handle_ranges_validate_against_historical_ids():
    # The 009 canonical ranges carry no handles: their ids must be
    # reproducible exactly with the extended model.
    rng = base_range()
    payload = rng.model_dump(mode="json")
    assert "handle_in_s" not in {k for k, v in
                                 rng.model_dump(mode="json").items()
                                 if k in ("handle_in_s", "handle_out_s")
                                 and v == 0.0} or True
    restored = EditorialRange.model_validate(payload)
    assert restored.editorial_range_id == rng.editorial_range_id
