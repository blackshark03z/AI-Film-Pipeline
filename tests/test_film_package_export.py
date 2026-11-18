"""film_package v1 exporter: mapping, derived-bed exclusion, optional files, hashes and schema validity.

The film folder is synthetic (tiny JSON stage files + 64x36 lavfi media), built once and copied per test.
"""
from __future__ import annotations

import copy
import hashlib
import json
import shutil
import subprocess
from pathlib import Path

import pytest

from film_pipeline.film_package_export import ExportError, build_package, export, validate_package
from film_pipeline.film_package_export.__main__ import main
from film_pipeline.film_package_export.validate import semantic_errors

pytestmark = pytest.mark.skipif(not (shutil.which("ffmpeg") and shutil.which("ffprobe")), reason="ffmpeg/ffprobe needed")

FPS = 24
# frames: title [0,24) | SC01_g1 [24,72) | SC01_card [72,96) | SC02_g1 [96,120) | end card [120,144)
BODY = [("SC01_g1", "TAKE", "SC01_g1_t1", 1.0, 3.0), ("SC01_card", "CARD", "", 3.0, 4.0), ("SC02_g1", "TAKE", "SC02_g1_t1", 4.0, 5.0)]
SFX_NAMES = ("door",)


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _put(root: Path, rel: str, data) -> Path:
    path = root / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=1), encoding="utf-8") if not isinstance(data, bytes) else path.write_bytes(data)
    return path


def _wav(path: Path, hz: int, seconds: float = 6.0) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "lavfi", "-i", f"sine=f={hz}:d={seconds}:r=8000", "-ac", "1",
                    "-c:a", "pcm_s16le", str(path)], check=True)


@pytest.fixture(scope="session")
def template(tmp_path_factory) -> Path:
    root = tmp_path_factory.mktemp("tpl") / "film99_test"
    root.mkdir()
    pic = root / "media/cut/rough_cut.mp4"
    pic.parent.mkdir(parents=True)
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "lavfi", "-i", "color=c=gray:s=64x36:r=24:d=6", "-f", "lavfi", "-i",
                    "sine=f=300:d=6:r=48000", "-c:v", "libx264", "-pix_fmt", "yuv420p", "-c:a", "aac", "-shortest", str(pic)],
                   check=True)
    for name, hz in (("dialogue", 200), ("ambience", 300), ("sfx", 400), ("music", 500), ("bed", 600), ("bed_ducked", 700), ("mix", 800)):
        _wav(root / f"audio/stems/{name}.wav", hz)
    for name in SFX_NAMES:
        _wav(root / f"audio/sfx/{name}.wav", 900, 0.5)
    _put(root, "film.json", {"film_id": "film99_test", "title": "Test", "language": "en", "fps": 24})
    events = [{"event_id": e, "kind": k, "take_id": t} for e, k, t, _, _ in BODY]
    _put(root, "05_edit.json", {"events": events, "title": [{"text": "TEST", "size": 96}]})
    planned = [{"event_id": e, "kind": k, "take_id": t, "start_s": a, "end_s": b, "duration_s": b - a, "transition": "CUT"}
               for e, k, t, a, b in BODY]
    _put(root, "media/cut/rough_cut.cut.json", {"film_id": "film99_test", "output_sha256": _sha(pic), "total_s": 6.0,
                                                  "planned": {"events": planned, "title_s": 1.0, "body_end_s": 5.0, "end_s": 1.0, "total_s": 6.0}})
    _put(root, "lock/picture.lock.json", {"film_id": "film99_test", "edl_sha256": "a" * 64, "events": [{"event_id": e} for e, *_ in BODY],
                                           "sources": {"SC01_g1_t1": "b" * 64, "SC02_g1_t1": "c" * 64}})
    _put(root, "04_shots.json", {"generations": [{"generation_id": "SC01_g1", "scene_id": "SC01"}, {"generation_id": "SC02_g1", "scene_id": "SC02"}]})
    _put(root, "01_story.json", {"scenes": {"SC01": {"purpose": "Open.", "conflict": "A.", "outcome": "B."}, "SC02": {"purpose": "Close."}}})
    _put(root, "03_preprod.json", {"scenes": {"SC01": {"location": "office", "occupancy": {"initial": ["MARA"]}},
                                              "SC02": {"location": "platform", "occupancy": {"initial": []}}},
                                   "locations": {"office": {"look": {"time_of_day": "NIGHT"}, "room_tone": "hum"},
                                                 "platform": {"look": {"time_of_day": "DAWN"}, "room_tone": "wind"}}})
    _put(root, "titles/titles.json", {"cues": [{"event_id": "SC01_g1", "line_no": 1, "character": "THEO", "text": "Hello.",
                                                 "start_s": 0.5, "end_s": 1.5, "source": "override"},
                                                {"event_id": "SC02_g1", "line_no": 2, "character": "MARA", "text": "Bye.",
                                                 "start_s": 0.0, "end_s": 0.5, "source": "windows"}]})
    _put(root, "titles/cues.json", {"cues": [{"event_id": "SC01_g1", "line_no": 1, "start_s": 0.5, "end_s": 1.5}]})
    _put(root, "audio/mix.json", {"plan": {"music": []}, "ambience": [{"scene_id": "SC01", "location": "office", "room_tone": "rain"}],
                                  "sfx": [{"event_id": "SC01_g1", "asset": "audio/sfx/door.wav"}]})
    _put(root, "audio/assets.json", {"assets": [{"asset": "audio/sfx/door.wav", "kind": "sfx", "sha256": _sha(root / "audio/sfx/door.wav")}]})
    _put(root, "delivery/rights/rights.json", {"preprod": []})
    _put(root, "qc/master_qc.json", {"ok": True})
    _put(root, "07_delivery.json", {})
    return root


@pytest.fixture()
def film(template, tmp_path) -> Path:
    dst = tmp_path / "film99_test"
    shutil.copytree(template, dst)
    return dst


def test_mapping_and_schema(film):
    pkg, warns = build_package(film)
    validate_package(pkg)  # schema + semantic rules + re-hash + durations
    assert pkg["source"] == {"root": str(film.resolve()), "producer": "afp"}  # no git repo around tmp_path
    assert pkg["clock"] == {"fps_num": 24, "fps_den": 1, "duration_frames": 144, "audio_sample_rate": 8000}
    assert [(e["event_id"], e["kind"], e["in_frame"], e["out_frame"]) for e in pkg["timeline"]] == [
        ("TITLE_CARD", "CARD", 0, 24), ("SC01_g1", "TAKE", 24, 72), ("SC01_card", "CARD", 72, 96),
        ("SC02_g1", "TAKE", 96, 120), ("END_CARD", "CARD", 120, 144)]
    take = pkg["timeline"][1]
    assert take["take_id"] == "SC01_g1_t1" and take["source_sha256"] == "b" * 64 and take["source_in_frame"] == 0
    assert take["scene_id"] == "SC01" and pkg["timeline"][2]["scene_id"] == "SC01"  # card falls back to the id prefix
    cue = pkg["dialogue"][0]
    assert (cue["event_id"], cue["speaker"], cue["in_frame"], cue["out_frame"], cue["timing_source"]) == ("SC01_g1", "THEO", 36, 60, "manual")
    assert pkg["dialogue"][1]["timing_source"] == "script_estimate" and pkg["dialogue"][1]["in_frame"] == 96
    sc = {s["scene_id"]: s for s in pkg["scenes"]}
    assert sc["SC01"]["room_tone"] == "rain" and sc["SC01"]["time_of_day"] == "night" and sc["SC01"]["characters"] == ["MARA", "THEO"]
    assert sc["SC02"]["room_tone"] == "wind" and sc["SC02"]["location"] == "platform"
    assert pkg["audio"]["level"] == "L2"
    assert pkg["audio"]["production_track"] == {"file_id": "stem_dialogue", "provenance": "native_composite"}
    assert [(x["id"], x["role"], x["provenance"]) for x in pkg["audio"]["layers"]] == [
        ("ambience", "ambience", "afp_synthesized"), ("sfx", "sfx", "catalog_asset")]  # no music: plan.music is empty
    assert pkg["assets"] == [{"id": "asset_door", "file_id": "asset_door", "role": "sfx", "rights_ref": "rights"}]
    assert set(pkg["references"]) == {"edl", "cut_report", "mix_report", "qc", "delivery", "rights"}
    assert pkg["lock"] == {"file_id": "lock", "render_binding": "unverified", "edl_sha256": "a" * 64}
    assert pkg["picture"]["baked"] == {"grade": "afp_default_grade", "cards": True, "subtitles": False,
                                       "tags": "AI-generated label over the body + opening card"}


def test_files_are_relative_hashed_and_sized(film):
    pkg, _ = build_package(film)
    for f in pkg["files"]:
        path = film / f["path"]
        assert not Path(f["path"]).is_absolute() and ".." not in f["path"]
        assert f["sha256"] == _sha(path) and f["bytes"] == path.stat().st_size
    assert len({f["id"] for f in pkg["files"]}) == len(pkg["files"])


def test_derived_beds_never_listed(film):
    pkg, _ = build_package(film)
    listed = {f["path"] for f in pkg["files"]}
    assert not {"audio/stems/bed.wav", "audio/stems/bed_ducked.wav", "audio/stems/mix.wav", "audio/stems/music.wav"} & listed
    bad = copy.deepcopy(pkg)
    bad["files"].append({"id": "bed", "path": "audio/stems/bed_ducked.wav", "sha256": "d" * 64})
    bad["audio"]["layers"].append({"id": "bed", "file_id": "bed", "role": "ambience", "provenance": "x"})
    assert any("derived bed/mix" in e for e in semantic_errors(bad))


def test_music_layer_only_when_cues_exist(film):
    mix = json.loads((film / "audio/mix.json").read_text())
    mix["plan"]["music"] = [{"cue": "theme"}]
    _put(film, "audio/mix.json", mix)
    pkg, _ = build_package(film)
    assert [x["id"] for x in pkg["audio"]["layers"]] == ["ambience", "sfx", "music"]
    validate_package(pkg)


def test_missing_titles_degrades_to_l0_with_warning(film):
    shutil.rmtree(film / "titles")
    pkg, warns = build_package(film)
    validate_package(pkg)
    assert "dialogue" not in pkg and pkg["audio"]["level"] == "L0" and pkg["timeline"]
    assert any("titles" in w for w in warns) and any("independent layer" in w for w in warns)
    assert len(pkg["audio"]["layers"]) == 2  # kept, but the level stays honest


def test_missing_mix_lock_rights_and_assets(film):
    for rel in ("audio/mix.json", "lock/picture.lock.json", "delivery/rights/rights.json", "audio/assets.json"):
        (film / rel).unlink()
    pkg, warns = build_package(film)
    validate_package(pkg)
    assert "layers" not in pkg["audio"] and pkg["audio"]["level"] == "L1"
    assert "lock" not in pkg and "assets" not in pkg and "rights" not in pkg["references"]
    assert "source_sha256" not in pkg["timeline"][1] and any("mix.json" in w for w in warns)


def test_missing_required_files(film):
    (film / "audio/stems/dialogue.wav").unlink()
    with pytest.raises(ExportError, match="dialogue.wav"):
        build_package(film)


def test_picture_changed_after_render_is_refused(film):
    with (film / "media/cut/rough_cut.mp4").open("ab") as handle:
        handle.write(b"x")
    with pytest.raises(ExportError, match="differs from"):
        build_package(film)


def test_stale_cut_report_is_refused(film):
    edit = json.loads((film / "05_edit.json").read_text())
    edit["events"].pop()
    _put(film, "05_edit.json", edit)
    with pytest.raises(ExportError, match="different events"):
        build_package(film)


def test_gap_is_declared_black(film):
    cut = json.loads((film / "media/cut/rough_cut.cut.json").read_text())
    cut["planned"]["events"][2]["start_s"] = 4.5  # SC02_g1 starts half a second late
    _put(film, "media/cut/rough_cut.cut.json", cut)
    pkg, warns = build_package(film)
    black = [e for e in pkg["timeline"] if e["kind"] == "BLACK"]
    assert [(e["in_frame"], e["out_frame"]) for e in black] == [(96, 108)] and any("BLACK" in w for w in warns)


def test_semantic_rules_reject_bad_packages(film):
    good, _ = build_package(film)
    assert semantic_errors(good) == []

    def broken(mutate):
        bad = copy.deepcopy(good)
        mutate(bad)
        return semantic_errors(bad)

    assert any("overlaps" in e for e in broken(lambda p: p["timeline"][2].update(in_frame=60)))
    assert any("not declared as BLACK" in e for e in broken(lambda p: p["timeline"].pop(2)))
    assert any("half-open" in e for e in broken(lambda p: p["timeline"][-1].update(out_frame=999)))
    assert any("not in files[]" in e for e in broken(lambda p: p["audio"]["production_track"].update(file_id="nope")))
    assert any("not in files[]" in e for e in broken(lambda p: p["references"].update(qc="nope")))
    assert any("relative" in e for e in broken(lambda p: p["files"][0].update(path="../x.mp4")))
    assert any("relative" in e for e in broken(lambda p: p["files"][0].update(path="C:/x.mp4")))
    assert any("leaves its event" in e for e in broken(lambda p: p["dialogue"][0].update(in_frame=10)))
    assert any("level L2" in e for e in broken(lambda p: p["audio"].pop("layers")))
    assert any("duplicate file ids" in e for e in broken(lambda p: p["files"].append(dict(p["files"][0]))))


def test_schema_violation_and_tampered_hash_fail(film):
    pkg, _ = build_package(film)
    bad = copy.deepcopy(pkg)
    bad["audio"]["level"] = "L9"
    with pytest.raises(ExportError, match="schema"):
        validate_package(bad)
    bad = copy.deepcopy(pkg)
    bad["files"][0]["sha256"] = "0" * 64
    with pytest.raises(ExportError, match="sha256"):
        validate_package(bad)


def test_export_and_cli(film, tmp_path, capsys):
    out = tmp_path / "out" / "pkg.json"
    assert main([str(film), "--out", str(out)]) == 0
    assert json.loads(out.read_text(encoding="utf-8"))["film_id"] == "film99_test"
    assert "level L2, 5 events, 2 cues, 2 layers, 144 frames" in capsys.readouterr().out
    with pytest.raises(ExportError, match="outside the film folder"):
        export(film, film / "pkg.json")
    assert main([str(film), "--out", str(film / "pkg.json")]) == 2 and not (film / "pkg.json").exists()
    assert main([str(film), "--out", str(out), "--picture", "nope"]) == 2
    (film / "film.json").unlink()
    assert main([str(film), "--out", str(tmp_path / "x.json")]) == 2
