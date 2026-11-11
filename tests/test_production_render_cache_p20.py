from film_pipeline.production.render_cache import cached, key_for, save


def test_render_cache_rejects_corrupt_bytes_and_reuses_verified_content(tmp_path):
    source = tmp_path / "source.bin"
    source.write_bytes(b"source")
    cache = tmp_path / "cache"
    key = key_for(sources=[source], settings={"trim": [0, 1]})
    assert cached(cache, key, ".bin") is None
    saved = save(cache, key, source, ".bin")
    assert cached(cache, key, ".bin") == saved
    saved.write_bytes(b"tampered")
    assert cached(cache, key, ".bin") is None


def test_cache_identity_depends_on_bytes_not_disposable_temp_paths(tmp_path):
    left, right = tmp_path / "temp_a.bin", tmp_path / "temp_b.bin"
    left.write_bytes(b"same source")
    right.write_bytes(left.read_bytes())
    assert key_for(sources=[left], settings={"trim": [0, 1]}) == key_for(sources=[right], settings={"trim": [0, 1]})
