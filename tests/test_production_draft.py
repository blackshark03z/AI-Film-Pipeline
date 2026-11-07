"""P11-07: `film.py edit --init` and `generators --init` draft what the rehearsal had to write by hand (M1-M3)."""
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from film_pipeline.production import deliver as DL
from film_pipeline.production import draft as DR
from film_pipeline.production import takes as T
from film_pipeline.production.package import load_package
from test_production_gate_checks import ROOT, clone, register_all, sheet_pass

TOOL = ROOT / "tools" / "film.py"


def film(*args):
    done = subprocess.run([sys.executable, str(TOOL), *args], capture_output=True, text=True, encoding="utf-8", cwd=ROOT,
                          env={**os.environ, "PYTHONPATH": str(ROOT / "src"), "PYTHONIOENCODING": "utf-8"})
    return done.returncode, json.loads(done.stdout)


def accept(root, upto):
    pkg = load_package(root)
    for entry in register_all(root, pkg, upto=upto):
        T.ingest_review(root, pkg.header.film_id, sheet_pass(T.dailies_template(pkg, entry)))
    return load_package(root)


def test_edit_draft_takes_the_latest_accepted_take_per_generation_in_shot_order(tmp_path):
    root = clone(tmp_path)
    pkg = accept(root, 3)
    gids = [d.generation_id for d in pkg.typed["shots"].generations]
    draft = DR.edit_draft(pkg)
    assert [e["event_id"] for e in draft["events"]] == gids[:3]
    assert [e["take_id"] for e in draft["events"]] == [f"{g}_t1" for g in gids[:3]]
    assert draft["missing"] == gids[3:]  # no footage is invented for the rest
    assert [line["text"] for line in draft["title"]] == [pkg.header.title.upper(), "Generated with AI"]


def test_edit_draft_skips_rejected_and_older_shot_versions_and_picks_the_newest_accepted(tmp_path):
    root = clone(tmp_path)
    pkg = accept(root, 1)
    gid = pkg.typed["shots"].generations[0].generation_id
    clip = root / "media" / "takes" / "second.mp4"
    clip.write_bytes(b"second take")
    decl = pkg.typed["shots"].generations[0]
    entry, _ = T.register_take(root, pkg.header.film_id, gid, clip, prompt_text="sent", route="r", model="m", credits=1,
                               shot_version=decl.version)
    assert entry.take_id == f"{gid}_t2"
    T.ingest_review(root, pkg.header.film_id, sheet_pass(T.dailies_template(load_package(root), entry)))
    assert DR.edit_draft(load_package(root))["events"][0]["take_id"] == f"{gid}_t2"
    log = T.load_log(root, pkg.header.film_id)
    for take in log.takes:
        take.status = "REJECTED"
    T.save_log(root, log)
    with pytest.raises(ValueError, match="no ACCEPTED take"):
        DR.edit_draft(load_package(root))


def test_edit_draft_never_overwrites_a_real_edl_but_replaces_an_empty_one(tmp_path):
    root = clone(tmp_path)
    pkg = accept(root, 1)
    assert (root / "05_edit.json").read_text(encoding="utf-8").strip() in ("{}", "")  # film04 ships a blank EDL
    assert DR.edit_draft(pkg)["events"]
    (root / "05_edit.json").write_text(json.dumps({"events": [{"event_id": "a", "take_id": "X_g1_t1"}]}), encoding="utf-8")
    with pytest.raises(ValueError, match="already has events"):
        DR.edit_draft(load_package(root))
    (root / "05_edit.json").write_text("{not json", encoding="utf-8")  # unreadable is not blank
    with pytest.raises(ValueError, match="already has events"):
        DR.edit_draft(load_package(root))


def test_cli_edit_init_writes_a_valid_edl_whose_title_carries_the_ai_label(tmp_path):
    root = clone(tmp_path)
    accept(root, 2)
    code, body = film("edit", "--film", str(root), "--init")
    assert code == 0 and body["events"] == 2 and len(body["missing_takes"]) == 10
    written = json.loads((root / "05_edit.json").read_text(encoding="utf-8"))
    assert "missing" not in written  # the report is not part of the EDL (extra keys are forbidden)
    section = load_package(root).typed["edit"]
    assert len(section.events) == 2 and DL.visible_label(section).text == "Generated with AI"  # deliver would not BLOCK AI_LABEL_MISSING
    code, body = film("edit", "--film", str(root), "--init")
    assert code == 1 and "already has events" in body["error"]


def test_generators_draft_names_the_video_tool_from_the_takes_and_the_image_tool_from_the_stills(tmp_path):
    root = clone(tmp_path)
    accept(root, 1)
    records = DR.generators_draft(load_package(root))
    assert records == [{"role": "video+audio", "name": "r", "model": "m", "settings": "r"}]
    from film_pipeline.production.generators import records_from_data
    assert [g.role for g in records_from_data(records)] == ["video+audio"]  # the real parser accepts the draft


def test_generators_draft_adds_the_image_tool_of_registered_stills(tmp_path):
    from film_pipeline.production import stills as S
    root = clone(tmp_path)
    pkg = accept(root, 1)
    gid = pkg.typed["shots"].generations[0].generation_id
    PIL = pytest.importorskip("PIL.Image")
    image = tmp_path / "still.png"
    PIL.new("RGB", (64, 36), (10, 10, 10)).save(image)
    S.register_still(load_package(root), gid, image, source="Flow Nano Banana")
    records = DR.generators_draft(load_package(root))
    assert {"role": "image", "name": "Flow Nano Banana", "model": "Flow Nano Banana", "settings": ""} in records
    assert [r["role"] for r in records] == ["video+audio", "image"]


def test_generators_draft_refuses_when_nothing_names_a_tool_and_never_overwrites(tmp_path):
    root = clone(tmp_path)
    with pytest.raises(ValueError, match="no take and no registered still"):
        DR.generators_draft(load_package(root))
    accept(root, 1)
    code, body = film("generators", "--film", str(root), "--init")
    assert code == 0 and (root / "generators.json").is_file() and body["generators"][0]["role"] == "video+audio"
    code, body = film("generators", "--film", str(root), "--init")
    assert code == 1 and "already has entries" in body["error"]
