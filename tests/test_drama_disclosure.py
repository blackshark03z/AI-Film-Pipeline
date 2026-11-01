import json
import subprocess
from pathlib import Path

import pytest

from film_pipeline.drama.disclosure import (
    IPTC_TRAINED_ALGORITHMIC_MEDIA, Disclosure, GeneratorRecord,
    VisibleLabel, check_release, default_dev_cert_dir, embed_metadata,
    read_c2pa, read_metadata, record_sha256, sha256_file, sign_c2pa,
    write_disclosure)
from film_pipeline.drama.post import PostManifest



def _disc(**kw) -> Disclosure:
    base = dict(
        film_id="t", title="Test", created="2026-11-01",
        generators=[GeneratorRecord(provider="P", model="M",
                                    role="video+audio")],
        visible_label=VisibleLabel(text="AI-generated", start_s=0.0,
                                   duration_s=3.0))
    base.update(kw)
    return Disclosure(**base)


def test_problems_ok_and_defaults():
    d = _disc()
    assert d.problems() == []
    assert d.digital_source_type == IPTC_TRAINED_ALGORITHMIC_MEDIA


@pytest.mark.parametrize("label,watermark,expect", [
    (dict(start_s=3.0, duration_s=5.0), False, "must start within"),
    (dict(start_s=0.0, duration_s=1.0), False, "must start within"),
    (dict(start_s=3.0, duration_s=5.0), True, None),
    (dict(text=" ", start_s=0.0, duration_s=3.0), False, "text is empty"),
])
def test_problems_label(label, watermark, expect):
    vl = dict(text="AI-generated", start_s=0.0, duration_s=3.0)
    vl.update(label)
    d = _disc(visible_label=VisibleLabel(watermark_always_on=watermark, **vl))
    probs = d.problems()
    if expect is None:
        assert probs == []
    else:
        assert any(expect in p for p in probs)


def test_problems_generator_and_flag():
    assert any("generator" in p for p in _disc(generators=[]).problems())
    assert any("ai_generated" in p for p in _disc(ai_generated=False).problems())


def test_write_disclosure_sha(tmp_path):
    v = tmp_path / "v.bin"
    v.write_bytes(b"abc")
    out = tmp_path / "d.json"
    done = write_disclosure(_disc(), v, out)
    data = json.loads(out.read_text(encoding="utf-8"))
    assert data["content_sha256"] == done.content_sha256 == sha256_file(v)
    assert list(data) == sorted(data)
    # the record hash ignores content_sha256
    assert record_sha256(done) == record_sha256(_disc())


@pytest.fixture
def clip(tmp_path):
    p = tmp_path / "clip.mp4"
    try:
        subprocess.run(
            ["ffmpeg", "-v", "error", "-y", "-f", "lavfi", "-i",
             "testsrc=size=320x240:rate=24:duration=1", "-f", "lavfi", "-i",
             "sine=frequency=440:duration=1", "-c:v", "libx264", "-pix_fmt",
             "yuv420p", "-c:a", "aac", "-shortest", str(p)], check=True)
    except (FileNotFoundError, subprocess.CalledProcessError):
        pytest.skip("ffmpeg unavailable")
    return p


def _streams(path):
    out = subprocess.run(
        ["ffprobe", "-v", "error", "-show_streams", "-of", "json", str(path)],
        capture_output=True, text=True, check=True)
    return [(s["codec_name"], round(float(s["duration"]), 2))
            for s in json.loads(out.stdout)["streams"]]


def test_embed_metadata_copy_and_release(tmp_path, clip):
    d = _disc()
    marked = embed_metadata(clip, tmp_path / "marked.mp4", d)
    assert _streams(clip) == _streams(marked)
    tags = read_metadata(marked)
    for k in ("comment", "description", "ai_generated", "digital_source_type",
              "disclosure_sha256", "generator"):
        assert k in tags
    assert tags["ai_generated"] == "true"
    assert tags["digital_source_type"] == IPTC_TRAINED_ALGORITHMIC_MEDIA
    js = tmp_path / "disclosure.json"
    write_disclosure(d, marked, js)
    assert check_release(marked) == []
    assert check_release(marked, js) == []


def test_check_release_negative(tmp_path, clip):
    d = _disc()
    # no disclosure json
    assert any("missing" in p for p in check_release(clip))
    # json present but file has no ai_generated metadata
    js = tmp_path / "disclosure.json"
    write_disclosure(d, clip, js)
    assert any("ai_generated" in p for p in check_release(clip))
    # sha mismatch
    marked = embed_metadata(clip, tmp_path / "marked.mp4", d)
    write_disclosure(d, clip, js)
    assert any("content_sha256" in p for p in check_release(marked, js))


def test_check_release_manifest(tmp_path, clip):
    d = _disc()
    marked = embed_metadata(clip, tmp_path / "marked.mp4", d)
    write_disclosure(d, marked, tmp_path / "disclosure.json")
    m = PostManifest(film="t", date="2026-11-01", source="s", clips=[],
                     final="marked.mp4", sha256="x", duration_s=1.0,
                     title_s=0, end_card_s=0, grade="", audio="",
                     disclosure={"json": "disclosure.json",
                                 "marked": "marked.mp4"})
    assert check_release(m, base=tmp_path) == []
    bare = m.model_copy(update={"disclosure": None})
    assert check_release(bare, base=tmp_path)


def test_c2pa_sign_and_read(tmp_path, clip):
    pytest.importorskip("c2pa")
    certs = default_dev_cert_dir()
    cert, key = certs / "signer_cert.pem", certs / "signer_key.pem"
    if not (cert.is_file() and key.is_file()):
        pytest.skip("dev C2PA cert absent (tools/drama_make_c2pa_dev_cert.py)")
    d = _disc()
    out = tmp_path / "signed.mp4"
    summary = sign_c2pa(clip, out, d, cert, key)
    assert summary["digital_source_types"] == [IPTC_TRAINED_ALGORITHMIC_MEDIA]
    assert [a["action"] for a in summary["actions"]][:2] == [
        "c2pa.created", "c2pa.edited"]
    assert read_c2pa(out) is not None
    assert read_c2pa(clip) is None
    assert _streams(clip) == _streams(out)
