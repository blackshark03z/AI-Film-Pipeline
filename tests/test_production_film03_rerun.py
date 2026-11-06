"""P7-02: film03 re-run through the package. The shipped takes live in docs/drama/film03/takes (committed), so the
import is checked on a scratch copy of the package skeleton; the committed package files are checked against it."""
import json
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

from film_pipeline.production import takes as T
from film_pipeline.production.edit import EditSection
from film_pipeline.production.package import load_package

ROOT = Path(__file__).resolve().parents[1]
FILM03 = ROOT / "films" / "film03_front_desk"
LEGACY = ROOT / "docs" / "drama" / "film03"
TOOL = ROOT / "tools" / "film03_to_package.py"
FILES = ("film.json", "script.fountain", "01_story.json", "02_direction.json", "03_preprod.json", "04_shots.json")
needs_ffmpeg = pytest.mark.skipif(not (shutil.which("ffmpeg") and shutil.which("ffprobe")), reason="ffmpeg not installed")
needs_package = pytest.mark.skipif(not (FILM03 / "05_edit.json").is_file(), reason="film03 package not re-run here")


@pytest.fixture(scope="module")
def imported(tmp_path_factory):
    root = tmp_path_factory.mktemp("film03") / "film03_front_desk"
    root.mkdir()
    for f in FILES:
        shutil.copyfile(FILM03 / f, root / f)
    done = subprocess.run([sys.executable, str(TOOL), "--film", str(root)], capture_output=True, text=True, encoding="utf-8",
                          cwd=ROOT, env={**__import__("os").environ, "PYTHONPATH": str(ROOT / "src"), "PYTHONIOENCODING": "utf-8"})
    assert done.returncode == 0, done.stderr[-800:]
    return root


@needs_ffmpeg
def test_all_sixteen_shipped_takes_are_registered_bound_to_their_bytes(imported):
    log = T.load_log(imported, "film03_front_desk")
    assert [t.take_id for t in log.takes] == [f"SC0{s}_g{g}_t1" for s in range(1, 9) for g in (1, 2)]
    for t in log.takes:
        legacy = json.loads((LEGACY / "takes" / f"{t.generation_id}.take.json").read_text(encoding="utf-8"))
        assert t.output_sha256 == legacy["sha256"] and T.sha256_file(imported / "media" / "takes" / t.output_file) == t.output_sha256
        assert t.credits == 0 and t.start_frame_sha256


@needs_ffmpeg
def test_only_the_technical_group_is_judged_by_the_importer_nobody_accepts_a_take(imported):
    log = T.load_log(imported, "film03_front_desk")
    assert {t.status for t in log.takes} == {"INCOMPLETE"}
    for t in log.takes:
        qc = json.loads((imported / "takes" / "reviews" / f"{t.take_id}.qc.json").read_text(encoding="utf-8"))
        judged = {c["group"]: c for c in qc["checks"] if c["result"] != "UNASSESSED"}
        assert set(judged) == {"technical"} and judged["technical"]["reviewer"] == "auto:ffprobe"


@needs_ffmpeg
def test_the_edl_reproduces_the_shipped_structure(imported):
    section = EditSection.model_validate_json((imported / "05_edit.json").read_text(encoding="utf-8"))
    shipped = json.loads((LEGACY / "post" / "film03_post.json").read_text(encoding="utf-8"))
    assert [e.event_id for e in section.events] == shipped["clips"]
    assert [e.kind for e in section.events if e.event_id.endswith("_card")] == ["CARD", "CARD"]
    assert section.title_s == shipped["title_s"] and section.end_s == shipped["end_card_s"]
    assert [(t.character, t.event_id) for t in section.tags] == [("NORA", "SC01_g2"), ("KESSLER", "SC02_g1"), ("ORTIZ", "SC03_g1")]
    assert any(l.text == "Generated with AI" for l in section.title)      # deliver's AI-label gate


@needs_ffmpeg
def test_every_shipped_cue_resolves_to_exactly_one_script_line(imported):
    cues = json.loads((imported / "titles" / "cues.json").read_text(encoding="utf-8"))["cues"]
    assert len(cues) == 16 and len({(c["event_id"], c["line_no"]) for c in cues}) == 16
    pkg = load_package(imported)
    from film_pipeline.production.titles import _shot_lines
    for c in cues:
        assert c["line_no"] in {l.line_no for l in _shot_lines(pkg, c["event_id"])}


@needs_ffmpeg
def test_running_the_importer_twice_changes_nothing(imported):
    before = {p.name: p.read_bytes() for p in (imported / "takes").glob("index.json")}
    before["edit"] = (imported / "05_edit.json").read_bytes()
    done = subprocess.run([sys.executable, str(TOOL), "--film", str(imported)], capture_output=True, text=True, encoding="utf-8", cwd=ROOT,
                          env={**__import__("os").environ, "PYTHONPATH": str(ROOT / "src"), "PYTHONIOENCODING": "utf-8"})
    assert done.returncode == 0 and "kept" in done.stdout and "new" not in done.stdout
    assert (imported / "takes" / "index.json").read_bytes() == before["index.json"] and (imported / "05_edit.json").read_bytes() == before["edit"]


@needs_package
def test_the_committed_package_matches_what_the_importer_writes(imported):
    assert (FILM03 / "05_edit.json").read_text(encoding="utf-8") == (imported / "05_edit.json").read_text(encoding="utf-8")
    assert (FILM03 / "titles" / "cues.json").read_text(encoding="utf-8") == (imported / "titles" / "cues.json").read_text(encoding="utf-8")
    committed = {t["take_id"]: t["output_sha256"] for t in json.loads((FILM03 / "takes" / "index.json").read_text(encoding="utf-8"))["takes"]}
    fresh = {t["take_id"]: t["output_sha256"] for t in json.loads((imported / "takes" / "index.json").read_text(encoding="utf-8"))["takes"]}
    assert committed == fresh


@needs_package
def test_the_delivery_record_names_a_manifest_and_is_not_release_ready():
    rec = json.loads((FILM03 / "07_delivery.json").read_text(encoding="utf-8"))["delivery"]
    assert len(rec["manifest_sha256"]) == 64 and rec["release_ready"] is False and rec["files"] > 0
    qc = json.loads((FILM03 / "qc" / "master_qc.json").read_text(encoding="utf-8"))
    assert qc["metrics"]["duration_s"] == pytest.approx(139.125, abs=0.01)
