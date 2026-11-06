import json
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

from film_pipeline.production import report as R
from film_pipeline.production import takes as T
from film_pipeline.production.package import load_package

ROOT = Path(__file__).resolve().parents[1]
FILM03 = ROOT / "films" / "film03_front_desk"
TOOL = ROOT / "tools" / "film.py"
FILES = ("film.json", "script.fountain", "01_story.json", "02_direction.json", "03_preprod.json", "04_shots.json")


def film(tmp_path: Path, name="film") -> Path:
    root = tmp_path / name
    root.mkdir(parents=True)
    for f in FILES:
        shutil.copyfile(FILM03 / f, root / f)
    return root


def run(*args):
    return subprocess.run([sys.executable, str(TOOL), *args], capture_output=True, text=True, encoding="utf-8", cwd=ROOT)


def take(root: Path, gid: str, credits=3.0, status="GENERATED", cause="", n=0):
    clip = root / "media" / "takes" / f"{gid}_{n}.mp4"
    clip.parent.mkdir(parents=True, exist_ok=True)
    clip.write_bytes(f"clip {gid} {n}".encode())
    entry, _ = T.register_take(root, "film03_front_desk", gid, clip, prompt_text=f"p {gid} {n}", route="r", model="m", credits=credits)
    log = T.load_log(root, "film03_front_desk")
    log.get(entry.take_id).status = status
    log.get(entry.take_id).cause = cause
    T.save_log(root, log)
    return entry.take_id


def report(root: Path):
    return R.status_report(load_package(root))


def test_a_film_with_no_takes_waits_for_the_go_live(tmp_path):
    r = report(film(tmp_path))
    assert r["errors"] == [] and r["film_id"] == "film03_front_desk"
    assert r["next_action"].startswith("Generate is paused") and "16 shots" in r["next_action"]
    assert r["production"]["generations"] == 16 and r["production"]["takes"] == 0 and r["production"]["retake_rate"] is None
    assert r["credits"]["spent"] == 0 and r["credits"]["planned_expected"] > 100 and r["credits"]["estimate"] is None
    assert set(r["gates"]) == {"1", "2", "3", "4", "5", "6"} and r["gates"]["1"]["status"] in ("PASS", "OWNER_PENDING")
    assert r["post"]["missing"] == ["titles", "mix", "master_qc", "versions"] and r["delivery"] == {"delivered": False}


def test_rights_blockers_use_the_planning_rule(tmp_path):
    r = report(film(tmp_path))
    pending = r["rights"]["pending"]
    assert "character NORA: pending" in pending and not any("original" in p for p in pending)
    assert r["rights"]["blockers"] == len(pending) and r["owner_decisions"] == pending


def test_takes_give_credits_usable_seconds_and_the_retake_rate(tmp_path):
    root = film(tmp_path)
    take(root, "SC01_g1", 3.0, "ACCEPTED")
    take(root, "SC01_g2", 3.0, "REJECTED", cause="PROMPT", n=0)
    take(root, "SC02_g1", 3.0, "REJECTED", cause="PROMPT", n=0)
    take(root, "SC02_g1", 3.0, "ACCEPTED", n=1)
    take(root, "SC03_g1", 3.0, "GENERATED")
    p = report(root)["production"]
    assert p["takes"] == 5 and p["by_status"] == {"ACCEPTED": 2, "REJECTED": 2, "GENERATED": 1} and p["retake_rate"] == 0.4
    assert p["accepted"] == 2 and p["rendered"] == 4 and p["first_pass"] == 1 and p["first_pass_rate"] == 0.25
    assert p["usable_s"] == 16 and p["credits_per_usable_s"] == round(15.0 / 16, 2) and p["credits_spent"] == 15.0
    assert [r["generation_id"] for r in p["open_retakes"]] == ["SC01_g2"] and p["open_retakes"][0]["action"] == "RETRY"
    assert p["awaiting_review"] == ["SC03_g1"] and len(p["not_rendered"]) == 12


def test_next_action_follows_retakes_then_reviews_then_the_rest(tmp_path):
    root = film(tmp_path)
    take(root, "SC01_g1", 3.0, "REJECTED", cause="PROMPT")
    assert report(root)["next_action"].startswith("Retake decision for SC01_g1: RETRY")
    take(root, "SC01_g1", 3.0, "ACCEPTED", n=1)
    take(root, "SC01_g2", 3.0, "GENERATED")
    assert report(root)["next_action"] == "Review takes of SC01_g2"


def test_credits_against_the_estimate_and_the_cap(tmp_path):
    root = film(tmp_path)
    header = json.loads((root / "film.json").read_text(encoding="utf-8"))
    header["budget"] = {"credits_estimate": 10, "cap_factor": 1.5}
    (root / "film.json").write_text(json.dumps(header), encoding="utf-8")
    for i, gid in enumerate(("SC01_g1", "SC01_g2", "SC02_g1", "SC02_g2")):
        take(root, gid, 3.0, "ACCEPTED", n=i)
    c = report(root)["credits"]
    assert c["spent"] == 12.0 and c["estimate"] == 10 and c["cap"] == 15.0
    assert c["pct_of_estimate"] == 120.0 and c["over_estimate"] and not c["over_cap"]
    take(root, "SC03_g1", 3.0, "ACCEPTED")
    assert not report(root)["credits"]["over_cap"]          # 15 is the cap, not over it
    take(root, "SC03_g2", 3.0, "ACCEPTED")
    assert report(root)["credits"]["over_cap"]


def test_a_broken_section_is_named_not_hidden(tmp_path):
    root = film(tmp_path)
    reviews = root / "takes" / "reviews"
    reviews.mkdir(parents=True)
    (reviews / "bad.qc.json").write_text("{not json", encoding="utf-8")
    r = report(root)
    assert any(e.startswith("qc:") for e in r["errors"]) and r["qc"] == {}
    assert r["gates"] and r["production"]["generations"] == 16 and r["next_action"]


BASE = {"gates": {"1": {"name": "n", "status": "PASS", "issues": 0, "first": []}}, "production": {"takes": 5},
        "edit": {"present": True}, "post": {"picture_lock": {"locked": True}, "dirty": [], "missing": []},
        "rights": {"pending": [], "sound": []}, "delivery": {"delivered": True, "release_ready": True}}


def merged(**over):
    out = {k: dict(v) if isinstance(v, dict) else v for k, v in BASE.items()}
    for k, v in over.items():
        out[k] = {**out[k], **v}
    return out


def test_next_action_for_each_later_state():
    gates = {"2": {"name": "Direction", "status": "BLOCK", "issues": 2, "first": ["no vision"]}}
    assert R.next_action(merged(gates=gates)) == "Resolve Gate 2 (Direction): no vision"
    owner = {"1": {"name": "Story", "status": "OWNER_PENDING", "issues": 1, "first": ["rights"]}}
    assert R.next_action(merged(gates=owner)).startswith("Owner decision needed at Gate 1")
    assert R.next_action(merged(edit={"present": False})) == "Write 05_edit.json from the accepted takes"
    assert R.next_action(merged(post={"picture_lock": {"locked": False}})).startswith("Lock the picture")
    assert R.next_action(merged(post={"dirty": ["post:mix"]})) == "Rebuild what the cut left behind: post:mix"
    assert "titles" in R.next_action(merged(post={"missing": ["titles", "mix"]}))
    assert R.next_action(merged(delivery={"delivered": False})) == "Run film.py deliver"
    late = R.next_action(merged(delivery={"release_ready": False}, rights={"pending": ["character NORA: pending"]}))
    assert "character NORA: pending" in late
    assert R.next_action(merged()).endswith("waiting for the Owner's acceptance")
    shots = merged(production={"not_rendered": ["SC09_g1"], "takes": 3})
    assert "Render 1 more shots" in R.next_action(shots)


def test_the_ledger_promotes_only_with_a_second_film(tmp_path):
    root = film(tmp_path)
    first = R.add_learning(root, "film03_front_desk", "Name the prop in every shot that shows it", "docs/drama/film03/README.md", area="shots")
    assert first.learning_id == "L001" and first.kind == "observation"
    with pytest.raises(ValueError, match="already in the ledger"):
        R.add_learning(root, "film03_front_desk", "name the prop in every shot that shows it", "x.md")
    again = R.add_evidence(root, "L001", "film03_front_desk", "takes/SC05_g1")
    assert again.kind == "observation" and len(again.evidence) == 2           # the same film again is not replication
    done = R.add_evidence(root, "L001", "film04_x", "films/film04_x/05_edit.json")
    assert done.kind == "replicated" and done.films == ["film03_front_desk", "film04_x"]
    with pytest.raises(ValueError, match="no learning L009"):
        R.add_evidence(root, "L009", "film04_x", "ref")
    assert R.ledger_view(root)["counts"] == {"observation": 0, "replicated": 1}


def test_the_scaffolded_empty_ledger_is_an_empty_ledger(tmp_path):
    root = film(tmp_path)
    (root / "ledger.json").write_text("{}", encoding="utf-8")
    assert R.ledger_view(root, "film03_front_desk")["counts"] == {"observation": 0, "replicated": 0}
    R.add_learning(root, "film03_front_desk", "A learning written over the placeholder", "docs/x.md")
    assert R.load_ledger(root).learnings[0].learning_id == "L001"
    (root / "ledger.json").write_text('{"cost": 3}', encoding="utf-8")        # anything else is not ours to overwrite
    with pytest.raises(ValueError):
        R.load_ledger(root)


def test_cli_status_ledger_and_all(tmp_path):
    root = film(tmp_path, "film03_front_desk")
    got = run("status", "--film", str(root))
    body = json.loads(got.stdout)
    assert got.returncode == 0 and body["next_action"].startswith("Generate is paused")
    assert body["gates"] == {k: v["status"] for k, v in body["report"]["gates"].items()} and "stages_present" in body
    noref = run("ledger", "--film", str(root), "--add", "Always name the prop in the shot")
    assert noref.returncode == 1 and "needs --ref" in json.loads(noref.stdout)["error"]
    added = json.loads(run("ledger", "--film", str(root), "--add", "Always name the prop in the shot", "--ref", "docs/x.md", "--area", "shots").stdout)
    assert added["counts"] == {"observation": 1, "replicated": 0} and added["learnings"][0]["id"] == "L001"
    bad = run("ledger", "--film", str(root), "--replicate", "L001", "--ref", "films/f4/x.json")
    assert bad.returncode == 1 and "needs --from-film" in json.loads(bad.stdout)["error"]
    rep = json.loads(run("ledger", "--film", str(root), "--replicate", "L001", "--from-film", "film04", "--ref", "films/film04/x.json").stdout)
    assert rep["counts"] == {"observation": 0, "replicated": 1}
    assert json.loads(run("status", "--film", str(root)).stdout)["report"]["learnings"] == {"observation": 0, "replicated": 1}

    films = tmp_path / "films"
    films.mkdir()
    shutil.copytree(root, films / "film03_front_desk")
    (films / "broken").mkdir()
    (films / "broken" / "film.json").write_text("[]", encoding="utf-8")
    (films / "notes").mkdir()
    table = json.loads(run("status", "--all", str(films)).stdout)["films"]
    assert [r["film"] for r in table] == ["broken", "film03_front_desk"]
    assert "error" in table[0] and table[1]["next_action"].startswith("Generate is paused") and table[1]["delivered"] is False
    assert run("status").returncode == 2
