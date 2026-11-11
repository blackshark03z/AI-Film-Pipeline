import json
import os
from pathlib import Path

import pytest

from film_pipeline.production import deliver as D
from film_pipeline.production.package import load_package
from film_pipeline.production.runtime import atomic_json
from test_production_deliver import pipeline, deliver, needs_ffmpeg


def test_current_archive_resolves_legacy_and_rejects_escaping_pointer(tmp_path):
    assert D.current_archive(tmp_path) == tmp_path / "delivery"
    atomic_json(tmp_path / "07_delivery.json", {"delivery": {"manifest": "media/deliveries/v1/MANIFEST.json"}})
    assert D.current_archive(tmp_path) == tmp_path / "media/deliveries/v1"
    atomic_json(tmp_path / "07_delivery.json", {"delivery": {"manifest": "../outside/MANIFEST.json"}})
    with pytest.raises(ValueError, match="manifest"):
        D.current_archive(tmp_path)


@needs_ffmpeg
def test_delivery_versions_are_immutable_and_unchanged_call_reuses_pointer(tmp_path, monkeypatch):
    root, cut_report = pipeline(tmp_path)
    first = deliver(root, cut_report)[1]
    archive = root / first["archive"]
    assert archive.is_relative_to(root / "media/deliveries")
    assert D.verify_archive(archive)["ok"]
    old_manifest = (archive / "MANIFEST.json").read_bytes()
    pointer = (root / "07_delivery.json").read_bytes()
    again = deliver(root, cut_report)[1]
    assert again["reused"] and again["archive"] == first["archive"]
    assert (root / "07_delivery.json").read_bytes() == pointer
    pre = root / "03_preprod.json"
    data = json.loads(pre.read_text(encoding="utf-8"))
    data["rights"][0]["note"] = "amended evidence in test fixture"
    atomic_json(pre, data)
    rename = Path.rename
    def guard(path, target):
        if path == archive:
            raise PermissionError("old master is open")
        return rename(path, target)
    monkeypatch.setattr(Path, "rename", guard)
    from film_pipeline.production import deliver as dl
    body = dl.deliver(load_package(root), root / "media/cut/mixed.mp4", cut_report,
                      generators="Google Flow Omni 1.1 Flash")
    assert body["ok"] and body["archive"] != first["archive"]
    assert body["superseded"] == first["archive"]
    assert (archive / "MANIFEST.json").read_bytes() == old_manifest
    assert D.current_archive(root) == root / body["archive"]
    assert D.verify_archive(root / body["archive"])["ok"]
    # A complete orphan version must be recoverable if the final pointer write fails.
    pointer = (root / "07_delivery.json").read_bytes()
    versions = set((root / "media/deliveries").iterdir())
    data["rights"][0]["note"] = "second amendment after delivery"
    atomic_json(pre, data)
    from film_pipeline.production import mix as M
    stamp = M.stamp_post_item
    def fail_pointer(*args, **kwargs):
        raise OSError("power lost before pointer promotion")
    monkeypatch.setattr(M, "stamp_post_item", fail_pointer)
    with pytest.raises(OSError, match="pointer promotion"):
        dl.deliver(load_package(root), root / "media/cut/mixed.mp4", cut_report,
                   generators="Google Flow Omni 1.1 Flash")
    assert (root / "07_delivery.json").read_bytes() == pointer
    orphan = set((root / "media/deliveries").iterdir()) - versions
    assert len(orphan) == 1 and D.verify_archive(orphan.pop())["ok"]
    monkeypatch.setattr(M, "stamp_post_item", stamp)
    dirs = set((root / "media/deliveries").iterdir())
    # Hold the previous master without FILE_SHARE_DELETE on the actual Windows filesystem.
    handle = None
    if os.name == "nt":
        import ctypes
        from ctypes import wintypes
        kernel = ctypes.WinDLL("kernel32", use_last_error=True)
        kernel.CreateFileW.restype = wintypes.HANDLE
        kernel.CreateFileW.argtypes = [wintypes.LPCWSTR, wintypes.DWORD, wintypes.DWORD,
                                      wintypes.LPVOID, wintypes.DWORD, wintypes.DWORD, wintypes.HANDLE]
        handle = kernel.CreateFileW(str(next((root / body["archive"]).rglob("*.mp4"))),
                                    0x80000000, 1, None, 3, 0, None)
        assert handle != ctypes.c_void_p(-1).value
        kernel.CloseHandle.argtypes = [wintypes.HANDLE]
    try:
        recovered = dl.deliver(load_package(root), root / "media/cut/mixed.mp4", cut_report,
                               generators="Google Flow Omni 1.1 Flash")
        assert recovered["ok"] and recovered["reused"]
        assert set((root / "media/deliveries").iterdir()) == dirs
        assert D.verify_archive(root / body["archive"])["ok"]
        assert D.current_archive(root) == root / recovered["archive"]
    finally:
        if handle is not None:
            kernel.CloseHandle(handle)
