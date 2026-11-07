import json
import shutil
from pathlib import Path

import pytest

from film_pipeline.production import deliver as DL
from film_pipeline.production.edit import EditEvent, EditSection, TextLine
from film_pipeline.production.package import load_package
from test_production_versions import film, needs_ffmpeg, register, run

GEN = "Google Flow Omni 1.1 Flash"
EVENTS = [EditEvent(event_id="a", take_id="SC02_g1_t1"), EditEvent(event_id="b", take_id="SC03_g1_t1"),
          EditEvent(event_id="d", take_id="SC04_g2_t1")]
LABELLED = [TextLine(text="The Front Desk", size=64), TextLine(text="Generated with AI", size=26)]


def pipeline(tmp_path: Path, *, label=True, versions=True, mastercheck=True, ai_label=None):
    """film03's skeleton, three synthetic takes, then titles -> mix -> mastercheck -> versions, all through the CLI.
    `ai_label` sets film.json disclosure.ai_label before the render (default: the header's own default)."""
    root, clips = film(tmp_path), tmp_path / "clips"
    if ai_label:
        header = json.loads((root / "film.json").read_text(encoding="utf-8"))
        (root / "film.json").write_text(json.dumps({**header, "disclosure": {"ai_label": ai_label}}), encoding="utf-8")
    register(root, clips, ["SC02_g1", "SC03_g1", "SC04_g2"])
    (root / "05_edit.json").write_text(EditSection(events=EVENTS, title=LABELLED if label else []).model_dump_json(), encoding="utf-8")
    cut = root / "media" / "cut" / "titled_cut.mp4"
    assert run("titles", "--film", str(root), "--clips", str(clips), "--langs", "en,vi", "--render", "--out", str(cut)).returncode == 0
    assert run("mix", "--film", str(root), "--cut", str(cut), "--out", str(root / "media" / "cut" / "mixed.mp4")).returncode == 0
    report = str(cut.with_suffix(".cut.json"))
    if mastercheck:
        assert run("mastercheck", "--film", str(root), "--cut-report", report).returncode == 0
    if versions:
        assert run("versions", "--film", str(root), "--cut-report", report, "--generators", GEN).returncode == 0
    return root, report


def deliver(root: Path, report: str, *extra):
    done = run("deliver", "--film", str(root), "--cut-report", report, "--generators", GEN, *extra)
    return done, json.loads(done.stdout)


def codes(body, severity=None):
    return {f["code"] for f in body["findings"] if severity in (None, f["severity"])}


def test_generators_and_the_label_come_from_what_exists():
    records = DL.split_generators("Google Flow Omni 1.1 Flash; Other Tool")
    assert [(g.provider, g.model) for g in records] == [("Google", "Flow Omni 1.1 Flash"), ("Other", "Tool")]
    assert DL.split_generators("Solo")[0].model == "unspecified"
    assert DL.split_generators("  ") == []
    assert DL.visible_label(EditSection(events=EVENTS, title=LABELLED)).text == "Generated with AI"
    empty = DL.visible_label(EditSection(events=EVENTS))
    assert empty.text == "" and empty.duration_s == 0
    late = DL.visible_label(EditSection(events=EVENTS, title=[TextLine(text="Made with AI")], title_s=3.0))
    assert late.start_s == 0 and late.duration_s == 3.0


@needs_ffmpeg
def test_deliver_archives_restores_and_catches_tampering(tmp_path):
    root, report = pipeline(tmp_path)
    done, body = deliver(root, report)
    assert done.returncode == 0 and body["ok"], body
    assert not body["release_ready"] and {"PICTURE_NOT_LOCKED", "RIGHTS_PENDING"} <= codes(body, "WARN")
    arch = root / "delivery"
    manifest = DL.ArchiveManifest.model_validate_json((arch / "MANIFEST.json").read_text(encoding="utf-8"))
    paths = {f.path for f in manifest.files}
    assert {"masters/film03_front_desk_16x9.mp4", "masters/film03_front_desk_9x16.mp4", "disclosure_16x9.json", "disclosure_9x16.json",
            "metadata.json", "qc/master_qc.json", "rights/rights.json", "package/film.json", "package/01_story.json",
            "package/takes/index.json", "package/titles/titles.json"} <= paths
    assert any(p.startswith("sidecars/") and p.endswith(".en.srt") for p in paths) and any(p.startswith("thumbs/") for p in paths)
    assert all(f.sha256 and f.size > 0 for f in manifest.files) and "MANIFEST.json" not in paths
    deps = manifest.external_dependencies          # the test keeps its clips outside media/takes: honestly "not present"
    assert [d.path for d in deps] == ["media/takes/SC02_g1.mp4", "media/takes/SC03_g1.mp4", "media/takes/SC04_g2.mp4"]
    assert not any(d.present_at_delivery for d in deps) and all(len(d.sha256) == 64 for d in deps)
    shutil.copytree(tmp_path / "clips", root / "media" / "takes")
    assert all(d.present_at_delivery for d in DL.dependencies(load_package(root)))
    rights = json.loads((arch / "rights" / "rights.json").read_text(encoding="utf-8"))
    assert rights["preprod"] and "sound_assets" in rights
    post = json.loads((root / "07_delivery.json").read_text(encoding="utf-8"))
    assert post["delivery"]["files"] == len(manifest.files) and post["delivery"]["release_ready"] is False

    from film_pipeline.drama import disclosure as D
    marked = arch / "masters" / "film03_front_desk_16x9.mp4"
    assert D.check_release(marked, arch / "disclosure_16x9.json") == []
    assert D.read_metadata(marked)["ai_generated"] == "true"
    assert D.load_disclosure(arch / "disclosure_16x9.json").visible_label.text == "Generated with AI"

    restored = tmp_path / "elsewhere" / "delivery"
    shutil.copytree(arch, restored)
    shutil.rmtree(root)                                    # the working tree is gone
    ok = run("status", "--package", str(restored))
    got = json.loads(ok.stdout)
    assert ok.returncode == 0 and got["ok"], got
    assert got["missing_files"] == [] and got["hash_mismatch"] == [] and got["unlisted_files"] == []
    assert got["package"]["loaded"] and got["package"]["film_id"] == "film03_front_desk"
    assert len(got["missing_dependencies"]) == 3 and "re-rendering needs" in got["note"]

    (restored / "metadata.json").write_text("{}", encoding="utf-8")
    (restored / "thumbs").joinpath(next(p.name for p in (restored / "thumbs").iterdir())).unlink()
    (restored / "extra.txt").write_text("x", encoding="utf-8")
    bad = run("status", "--package", str(restored))
    got = json.loads(bad.stdout)
    assert bad.returncode == 1 and got["hash_mismatch"] == ["metadata.json"] and len(got["missing_files"]) == 1
    assert got["unlisted_files"] == ["extra.txt"]


@needs_ffmpeg
def test_a_tampered_master_fails_the_restore_check(tmp_path):
    root, report = pipeline(tmp_path)
    assert deliver(root, report)[0].returncode == 0
    master = root / "delivery" / "masters" / "film03_front_desk_16x9.mp4"
    with master.open("ab") as f:
        f.write(b"\0")
    got = json.loads(run("status", "--package", str(root / "delivery")).stdout)
    assert not got["ok"] and got["hash_mismatch"] == ["masters/film03_front_desk_16x9.mp4"]
    assert any(p["code"] == "COMPLIANCE" for p in got["problems"])


def test_status_without_an_archive_or_a_manifest(tmp_path):
    assert run("status").returncode == 2
    empty = tmp_path / "empty"
    empty.mkdir()
    done = run("status", "--package", str(empty))
    assert done.returncode == 1 and "MANIFEST.json not found" in json.loads(done.stdout)["error"]


@needs_ffmpeg
def test_without_the_ai_label_or_generators_nothing_is_delivered(tmp_path):
    root, report = pipeline(tmp_path, label=False)
    done, body = deliver(root, report)
    assert done.returncode == 1 and not body["ok"] and "AI_LABEL_MISSING" in codes(body, "BLOCK")
    assert not (root / "delivery").exists() and not (root / "delivery.staging").exists()
    bare = run("deliver", "--film", str(root), "--cut-report", report)
    assert "GENERATORS_MISSING" in {f["code"] for f in json.loads(bare.stdout)["findings"]}


@needs_ffmpeg
def test_missing_stale_or_failing_inputs_block(tmp_path):
    root, report = pipeline(tmp_path, versions=False, mastercheck=False)
    body = deliver(root, report)[1]
    assert {"QC_MISSING", "VERSIONS_MISSING"} <= codes(body, "BLOCK")
    assert run("mastercheck", "--film", str(root), "--cut-report", report).returncode == 0
    assert run("versions", "--film", str(root), "--cut-report", report, "--generators", GEN).returncode == 0
    master = root / "media" / "cut" / "mixed.mp4"
    with master.open("ab") as f:
        f.write(b"\0")                                      # the QC no longer describes these bytes
    assert "QC_STALE" in codes(deliver(root, report)[1], "BLOCK")
    qc = root / "qc" / "master_qc.json"
    record = json.loads(qc.read_text(encoding="utf-8"))
    record["sha256"] = DL.sha256_file(master)
    record["findings"] = [{"group": "technical", "code": "X", "severity": "P0", "detail": "forced"}]
    record["checks"] = [{**c, "result": "FAIL", "severity": "P0"} if c["group"] == "technical" else c for c in record["checks"]]
    qc.write_text(json.dumps(record), encoding="utf-8")
    assert not (root / "delivery").exists()


@needs_ffmpeg
def test_a_second_delivery_keeps_the_first(tmp_path):
    root, report = pipeline(tmp_path)
    first = deliver(root, report)[1]
    again = deliver(root, report)[1]
    assert first["superseded"] is None and again["superseded"].startswith("delivery.superseded-")
    assert (root / again["superseded"] / "MANIFEST.json").is_file() and (root / "delivery" / "MANIFEST.json").is_file()


@needs_ffmpeg
def test_c2pa_asked_for_but_failing_blocks(tmp_path):
    root, report = pipeline(tmp_path)
    junk = tmp_path / "junk.pem"
    junk.write_text("not a certificate", encoding="utf-8")
    done, body = deliver(root, report, "--c2pa-cert", str(junk), "--c2pa-key", str(junk))
    assert done.returncode == 1 and "C2PA_FAILED" in codes(body, "BLOCK") and not (root / "delivery").exists()
    half = run("deliver", "--film", str(root), "--c2pa-cert", str(junk))
    assert half.returncode == 2
