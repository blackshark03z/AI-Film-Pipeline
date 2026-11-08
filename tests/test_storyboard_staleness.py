"""P16-11: a storyboard approval holds only for the shot decl the board was drawn from."""
import json
from pathlib import Path

import pytest

from film_pipeline.drama import StoryboardGate, shot_fingerprint
from film_pipeline.production import generate as G
from film_pipeline.production.package import load_package
from film_pipeline.production.plan import plan_package
from test_production_generate import backlog, codes, film, still

pytest.importorskip("PIL")
GID, SHOT = "SC01_g1", "SC01_S1"


def board(pkg):
    return StoryboardGate(pkg.root / "media" / "plan" / "storyboard")


def bump(pkg, gid=GID, version=2):
    path = pkg.root / "04_shots.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    next(g for g in data["generations"] if g["generation_id"] == gid)["version"] = version
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    return load_package(pkg.root)


def dry(pkg, tmp_path):
    return G.generate(pkg, GID, dry_run=True, stills_dir=still(tmp_path), start_token="tok:abc",
                      backlog=backlog(tmp_path))


def test_frames_record_the_fingerprint_they_were_drawn_from(tmp_path):
    pkg = film(tmp_path, 100)
    frame = board(pkg).frame(SHOT)
    assert frame.status == "APPROVED" and frame.fingerprint.startswith(f"{GID}@v1:")


def test_a_changed_decl_makes_the_approval_stale_in_dry_run_and_live(tmp_path):
    pkg = bump(film(tmp_path, 100))
    done = dry(pkg, tmp_path)
    assert "STORYBOARD_STALE" in codes(done["payload"]) and not done["ready_to_send"]
    stale = next(b for b in done["payload"]["blockers"] if b["code"] == "STORYBOARD_STALE")
    assert not stale["live_only"] and f"{GID}@v1:" in stale["detail"] and f"{GID}@v2:" in stale["detail"]
    live = G.generate(pkg, GID, dry_run=False, stills_dir=still(tmp_path), start_token="tok:abc",
                      backlog=backlog(tmp_path, "OWNER_GO_LIVE: YES"), runner=lambda argv, out: pytest.fail("sent"))
    assert not live["sent"] and "STORYBOARD_STALE" in [r["code"] for r in live["refused"]]
    # generate neither re-renders nor approves: the board still holds the v1 approval
    frame = board(pkg).frame(SHOT)
    assert frame.status == "APPROVED" and frame.fingerprint.startswith(f"{GID}@v1:")


def test_replanning_a_changed_decl_resets_the_frame_to_pending(tmp_path):
    pkg = bump(film(tmp_path, 100))
    plan_package(pkg, pkg.root / "media" / "plan")
    frame = board(pkg).frame(SHOT)
    assert frame.status == "PENDING" and frame.fingerprint.startswith(f"{GID}@v2:")


def test_an_unchanged_decl_keeps_its_approval_after_a_replan(tmp_path):
    pkg = film(tmp_path, 100)
    before = board(pkg).frame(SHOT)
    plan_package(pkg, pkg.root / "media" / "plan")
    after = board(pkg).frame(SHOT)
    assert after.status == "APPROVED" and after.fingerprint == before.fingerprint
    assert after.reviewed_at == before.reviewed_at
    assert "STORYBOARD_STALE" not in codes(dry(pkg, tmp_path)["payload"])


def _make_legacy(pkg):
    gate = board(pkg)
    for frame in gate.board.frames:
        frame.fingerprint = ""
    gate.save()


def test_a_legacy_frame_keeps_the_hash_only_rule(tmp_path):
    pkg = film(tmp_path, 100)
    _make_legacy(pkg)
    pkg = bump(pkg)
    done = dry(pkg, tmp_path)
    assert "STORYBOARD_STALE" not in codes(done["payload"]) and done["ready_to_send"]


def test_a_legacy_frame_redrawn_identically_adopts_the_fingerprint(tmp_path):
    pkg = film(tmp_path, 100)
    _make_legacy(pkg)
    plan_package(pkg, pkg.root / "media" / "plan")
    frame = board(pkg).frame(SHOT)
    assert frame.status == "APPROVED" and frame.fingerprint.startswith(f"{GID}@v1:")


def test_the_fingerprint_follows_every_drawn_field():
    from film_pipeline.production.plan import _Plan
    pkg = load_package(Path(__file__).resolve().parents[1] / "films" / "film03_front_desk")
    p = _Plan(pkg, None, None)
    decl = p.shots.generations[0]
    unit = p.unit_for(decl)
    shot = unit.shots[0]
    base = shot_fingerprint(decl.generation_id, decl.version, unit, shot)
    assert shot_fingerprint(decl.generation_id, decl.version, unit, shot) == base
    assert shot_fingerprint(decl.generation_id, decl.version + 1, unit, shot) != base
    for change in ({"shot_size": "CLOSE"}, {"subject": "X"}, {"foreground": "Y"}, {"action": "runs"},
                   {"end_s": shot.end_s + 1}, {"lines": []} if shot.lines else {"coverage": "TWO_SHOT"}):
        changed = unit.model_copy(update={"shots": [shot.model_copy(update=change)]})
        assert shot_fingerprint(decl.generation_id, decl.version, changed, changed.shots[0]) != base, change
