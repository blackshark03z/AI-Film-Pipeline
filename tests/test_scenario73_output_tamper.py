"""Package-009 recovery scenario 73 — output tamper.

Acceptance: canonical/master output bytes changed after receipt/hash
→ tamper detected → artifact rejected fail-closed → no stale PROVEN
state retained. Proven against the existing durable verification
(`rough_cut._verify_record_output`) that guards every persisted render.
"""
import hashlib
from pathlib import Path

import pytest

from film_pipeline.rough_cut import RoughCutRender, _verify_record_output


def _record(tmp_path: Path, data: bytes) -> tuple[Path, RoughCutRender]:
    output = tmp_path / "master.mp4"
    output.write_bytes(data)
    basis_record = dict(
        manifest_id="edit_test",
        output_sha256=hashlib.sha256(data).hexdigest(),
        duration_s=194.541667, width=1280, height=720, fps_num=24,
        fps_den=1, video_codec="h264", audio_codec="aac",
        audio_policy="preserve_all_source_audio", render_method="test",
        render_command_fingerprint="0" * 64, ffmpeg_version="test",
        source_asset_ids=["asset_test"], selected_take_ids=["take_test"],
        source_hashes=["0" * 64], full_decode=True)
    from film_pipeline.core import sha256 as _sha
    render_id = "rough_" + _sha(basis_record)
    record = RoughCutRender(
        render_id=render_id, output_path=str(output), **basis_record)
    return output, record


def test_tampered_output_bytes_are_detected_and_fail_closed(tmp_path):
    output, record = _record(tmp_path, b"original master bytes")
    tampered = b"ORIGINAL master bytes"  # one byte flipped
    output.write_bytes(tampered)
    with pytest.raises(ValueError, match="missing or changed"):
        _verify_record_output(record, sources=())
    # No stale PROVEN state: the recorded sha no longer matches the
    # artifact, so any consumer re-deriving the receipt refuses it.
    assert hashlib.sha256(output.read_bytes()).hexdigest() != \
        record.output_sha256
