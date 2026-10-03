"""Package-010 T7 — audio-lane contract offline proofs."""
import hashlib
import io
from pathlib import Path

import pytest

from film_pipeline.audio_lane import (
    AudioAsset, AudioClip, AudioLane, lane_inputs_and_filter,
    validate_lane_assets)


def wav_bytes(seconds=1.0, rate=48000, channels=2):
    import struct, wave
    buf = io.BytesIO()
    with wave.open(buf, "wb") as w:
        w.setnchannels(channels)
        w.setsampwidth(2)
        w.setframerate(rate)
        frames = int(rate * seconds)
        for i in range(frames):
            value = int(8000 * ((i % 100) / 100))
            w.writeframes(struct.pack("<" + "h" * channels,
                              *([value] * channels)))
    return buf.getvalue()


def make_asset(tmp_path, seconds=10.0, rate=48000, channels=2, name="a"):
    """tmp_path must be a real directory; tests pass pytest tmp_path."""
    data = wav_bytes(seconds, rate, channels)
    path = tmp_path / f"{name}.wav"
    path.write_bytes(data)
    return AudioAsset(
        asset_id=f"asset_{hashlib.sha256(name.encode()).hexdigest()[:64]}",
        uri_or_path=str(path), sha256=hashlib.sha256(data).hexdigest(),
        duration_s=seconds, sample_rate=rate, channels=channels,
        mime_type="audio/x-wav", provenance="test_fixture")


def lane_of(clip_kwargs):
    return AudioLane(lane_id="lane_master", role="master",
                     clips=[AudioClip(**kw) for kw in clip_kwargs])


def test_full_clip_and_trimmed_clip_validate(tmp_path):
    asset = make_asset(tmp_path, name="full")
    lane = lane_of([dict(asset_id=asset.asset_id, source_in_s=0,
                         source_out_s=10.0, timeline_start_s=0)])
    assert validate_lane_assets(lane, {asset.asset_id: asset}, 16.0)["validated"]
    trimmed = lane_of([dict(asset_id=asset.asset_id, source_in_s=2.0,
                            source_out_s=7.5, timeline_start_s=3.0)])
    assert validate_lane_assets(trimmed, {asset.asset_id: asset}, 16.0)
    assert trimmed.clips[0].duration_s == 5.5


def test_missing_asset_refused(tmp_path):
    asset = make_asset(tmp_path)
    lane = lane_of([dict(asset_id="asset_" + "0" * 64, source_in_s=0,
                         source_out_s=1, timeline_start_s=0)])
    with pytest.raises(ValueError, match="missing audio asset"):
        validate_lane_assets(lane, {asset.asset_id: asset}, 16.0)


def test_trim_out_of_bounds_refused(tmp_path):
    asset = make_asset(tmp_path, seconds=5.0)
    lane = lane_of([dict(asset_id=asset.asset_id, source_in_s=0,
                         source_out_s=6.0, timeline_start_s=0)])
    with pytest.raises(ValueError, match="exceeds asset duration"):
        validate_lane_assets(lane, {asset.asset_id: asset}, 16.0)


def test_placement_beyond_timeline_refused(tmp_path):
    asset = make_asset(tmp_path)
    lane = lane_of([dict(asset_id=asset.asset_id, source_in_s=0,
                         source_out_s=5.0, timeline_start_s=14.0)])
    with pytest.raises(ValueError, match="exceeds timeline"):
        validate_lane_assets(lane, {asset.asset_id: asset}, 16.0)


def test_same_lane_overlap_refused(tmp_path):
    asset = make_asset(tmp_path)
    clips = [
        dict(asset_id=asset.asset_id, source_in_s=0, source_out_s=4.0,
             timeline_start_s=0),
        dict(asset_id=asset.asset_id, source_in_s=0, source_out_s=2.0,
             timeline_start_s=2.0)]
    with pytest.raises(ValueError, match="overlapping"):
        lane_of(clips)


def test_zero_and_negative_trim_refused(tmp_path):
    with pytest.raises(ValueError):
        AudioClip(asset_id="asset_x", source_in_s=3.0, source_out_s=3.0,
                  timeline_start_s=0)


def test_gain_and_filtergraph_deterministic(tmp_path):
    asset = make_asset(tmp_path)
    lane = lane_of([
        dict(asset_id=asset.asset_id, source_in_s=1.0, source_out_s=4.0,
             timeline_start_s=2.0, gain_db=-3.0),
        dict(asset_id=asset.asset_id, source_in_s=0, source_out_s=2.5,
             timeline_start_s=8.0)])
    inputs, filter_frag, has_audio = lane_inputs_and_filter(
        lane, {asset.asset_id: asset})
    assert has_audio and len(inputs) == 4  # two clips x (-i, path)
    assert "volume=-3.0dB" in filter_frag
    assert "adelay=2000|2000" in filter_frag
    assert "amix=inputs=2" in filter_frag
    again = lane_inputs_and_filter(lane, {asset.asset_id: asset})
    assert again[1] == filter_frag


def test_empty_lane_has_no_audio(tmp_path):
    lane = AudioLane(lane_id="lane_master", role="master", clips=[])
    inputs, frag, has_audio = lane_inputs_and_filter(lane, {})
    assert not inputs and not frag and not has_audio


def test_wrong_sample_rate_refused(tmp_path):
    asset = make_asset(tmp_path, rate=44100)
    lane = lane_of([dict(asset_id=asset.asset_id, source_in_s=0,
                         source_out_s=1, timeline_start_s=0)])
    with pytest.raises(ValueError, match="sample rate"):
        validate_lane_assets(lane, {asset.asset_id: asset}, 16.0)


def test_mono_and_stereo_both_accepted(tmp_path):
    mono = make_asset(tmp_path, channels=1, name="mono")
    stereo = make_asset(tmp_path, channels=2, name="stereo")
    lane = lane_of([
        dict(asset_id=mono.asset_id, source_in_s=0, source_out_s=1,
             timeline_start_s=0),
        dict(asset_id=stereo.asset_id, source_in_s=0, source_out_s=1,
             timeline_start_s=2)])
    assert validate_lane_assets(lane, {mono.asset_id: mono,
                                       stereo.asset_id: stereo}, 16.0)


def test_lane_roundtrip_serialization(tmp_path):
    asset = make_asset(tmp_path)
    lane = lane_of([dict(asset_id=asset.asset_id, source_in_s=0.5,
                         source_out_s=2.5, timeline_start_s=1.0,
                         gain_db=-1.5)])
    restored = AudioLane.model_validate(lane.model_dump(mode="json"))
    assert restored == lane
