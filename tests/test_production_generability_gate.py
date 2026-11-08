"""P16-06 generability v2 at the generate entry point: send caps, review wait, RED refusal, Owner exceptions (dry run only)."""
import json
from datetime import date
from pathlib import Path

from film_pipeline.production import generate as G
from film_pipeline.production import takes as T
from film_pipeline.production.package import load_package
from film_pipeline.production.plan import plan_package

ROOT = Path(__file__).resolve().parents[1]
FILM03 = ROOT / "films" / "film03_front_desk"
FILES = ("film.json", "script.fountain", "01_story.json", "02_direction.json", "03_preprod.json", "04_shots.json")
GATE = {"ACCEPTED_TAKE_REUSE", "GENERABILITY_RED", "EXCEPTION_MISMATCH", "EXCEPTION_EXPIRED", "EXCEPTION_SPENT",
        "SEND_CAP", "AWAITING_REVIEW"}
GID = "SC01_g1"
GREEN_TEXT, AMBER_TEXT = "NORA nods", "NORA walks toward the desk"
UNKNOWN_TEXT, RED_TEXT = "NORA juggles three oranges", "NORA pushes the shutter up"
TODAY = date(2026, 11, 8)


def edit_shot(root, text=None, **extra):
    path = root / "04_shots.json"
    body = json.loads(path.read_text(encoding="utf-8"))
    decl = next(g for g in body["generations"] if g["generation_id"] == GID)
    if text is not None:
        decl["choreography"]["phases"][2]["description"] = text  # phase 1 keeps "KESSLER speaks" (the dialogue)
        decl["choreography"]["phases"][0]["description"] = "NORA stands at the glass doors"
    decl.update(extra)
    path.write_text(json.dumps(body), encoding="utf-8")


def film(tmp_path, text, **extra):
    """A tmp film03 with generability switched on and shot SC01_g1 rewritten; extra['generability_exception'] with
    prompt_sha256 'AUTO' is filled in from the prompt this very shot compiles to."""
    root = tmp_path / "film"
    root.mkdir(parents=True)
    for name in FILES:
        (root / name).write_text((FILM03 / name).read_text(encoding="utf-8"), encoding="utf-8")
    pre = json.loads((root / "03_preprod.json").read_text(encoding="utf-8"))
    pre["preflight"]["generability"] = True
    (root / "03_preprod.json").write_text(json.dumps(pre), encoding="utf-8")
    header = json.loads((root / "film.json").read_text(encoding="utf-8"))
    header["budget"]["credits_estimate"] = 100
    (root / "film.json").write_text(json.dumps(header), encoding="utf-8")
    exc = extra.pop("generability_exception", None)
    edit_shot(root, text, **extra)
    if exc is not None:
        if exc.get("prompt_sha256") == "AUTO":
            probe = load_package(root)
            plan_package(probe, root / "media" / "plan", approve_storyboard="owner")
            exc = {**exc, "prompt_sha256": G.build_payload(probe, GID, stills_dir=still(tmp_path))["prompt_sha256"]}
        edit_shot(root, generability_exception=exc)
    return reload(root)


def reload(root):
    pkg = load_package(root)
    plan_package(pkg, root / "media" / "plan", approve_storyboard="owner")
    return pkg


def exception(**kw):
    return {"authorized_by": "owner", "owner_words": "ok, one try", "shot_version": 1, "prompt_sha256": "AUTO",
            "max_attempts": 1, "max_credits": 20, "expires": "2026-12-01", "reason": "test", **kw}


def still(tmp_path):
    folder = tmp_path / "stills"
    folder.mkdir(parents=True, exist_ok=True)
    (folder / f"start_{GID}.png").write_bytes(b"png-bytes")
    return folder


def dry(pkg, tmp_path):
    done = G.generate(pkg, GID, dry_run=True, stills_dir=still(tmp_path), start_token="tok:abc", today=TODAY,
                      backlog=tmp_path / "none.md")
    return done, [b["code"] for b in done["payload"]["blockers"]]


def sent(pkg, n, version=1, result="PASSED", credits=8.0, gid=GID):
    """A receipt of a real send (what generate() writes before and after the runner)."""
    path = T.takes_dir(pkg.root) / "intents" / f"{gid}_t{n}.intent.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"film_id": pkg.header.film_id, "generation_id": gid, "take_id": f"{gid}_t{n}",
                                "shot_version": version, "sent": True, "result": result, "expected_credits": credits}),
                    encoding="utf-8")


def take(pkg, n, status, version=1):
    log = T.load_log(pkg.root, pkg.header.film_id)
    log.takes.append(T.TakeEntry(take_id=f"{GID}_t{n}", generation_id=GID, prompt_sha256="a" * 64, route="r", model="m",
                                 credits=8.0, output_file=f"{GID}_t{n}.mp4", output_sha256="b" * 64, status=status,
                                 shot_version=version))
    T.save_log(pkg.root, log)


def set_status(pkg, n, status):
    log = T.load_log(pkg.root, pkg.header.film_id)
    log.get(f"{GID}_t{n}").status = status
    T.save_log(pkg.root, log)


def test_green_shot_sends_once_then_hits_the_cap(tmp_path):
    pkg = film(tmp_path, GREEN_TEXT)
    done, found = dry(pkg, tmp_path)
    assert not set(found) & GATE and done["ready_to_send"]
    assert done["payload"]["attempts"] == {"this_version": 0, "all_versions": 0, "cap": 1, "level": "GREEN"}
    sent(pkg, 1)
    _, found = dry(pkg, tmp_path)
    assert found == ["SEND_CAP"]


def test_red_without_exception_is_refused(tmp_path):
    done, found = dry(film(tmp_path, RED_TEXT), tmp_path)
    assert "GENERABILITY_RED" in found and not done["ready_to_send"]
    assert done["payload"]["attempts"]["level"] == "RED" and done["payload"]["attempts"]["cap"] == 0
    assert not any(b["live_only"] for b in done["payload"]["blockers"] if b["code"] == "GENERABILITY_RED")


def test_legacy_waiver_does_not_unblock_a_red_send(tmp_path):
    done, found = dry(film(tmp_path, RED_TEXT, generability_waiver="restaged"), tmp_path)
    assert "GENERABILITY_RED" in found and not done["ready_to_send"]


def test_red_with_accepted_take_reuse_refuses_any_send(tmp_path):
    done, found = dry(film(tmp_path, RED_TEXT, accepted_take_reuse="SC01_g1_t3"), tmp_path)
    assert found == ["ACCEPTED_TAKE_REUSE"] and not done["ready_to_send"]
    _, green = dry(film(tmp_path / "g", GREEN_TEXT, accepted_take_reuse="SC01_g1_t3"), tmp_path / "g")
    assert "ACCEPTED_TAKE_REUSE" in green  # any level


def test_valid_exception_allows_the_send(tmp_path):
    pkg = film(tmp_path, RED_TEXT, generability_exception=exception())
    done, found = dry(pkg, tmp_path)
    assert not set(found) & GATE and "PACKAGE_PROBLEM" not in found and done["ready_to_send"]
    assert done["payload"]["attempts"]["level"] == "RED"


def test_expired_exception_is_refused(tmp_path):
    _, found = dry(film(tmp_path, RED_TEXT, generability_exception=exception(expires="2026-11-07")), tmp_path)
    assert found == ["EXCEPTION_EXPIRED"]
    _, today_ok = dry(film(tmp_path / "b", RED_TEXT, generability_exception=exception(expires="2026-11-08")), tmp_path / "b")
    assert today_ok == []  # valid through its last day


def test_version_mismatched_exception_is_refused(tmp_path):
    _, found = dry(film(tmp_path, RED_TEXT, generability_exception=exception(shot_version=2)), tmp_path)
    assert found == ["PACKAGE_PROBLEM", "EXCEPTION_MISMATCH"]  # gate3 also BLOCKs: no exception for this version
    bad_hash = film(tmp_path / "b", RED_TEXT, generability_exception=exception(prompt_sha256="c" * 64))
    _, found = dry(bad_hash, tmp_path / "b")
    assert found == ["EXCEPTION_MISMATCH"]


def test_spent_exception_is_refused(tmp_path):
    pkg = film(tmp_path, RED_TEXT, generability_exception=exception(max_attempts=1))
    sent(pkg, 1)
    _, found = dry(pkg, tmp_path)
    assert found == ["EXCEPTION_SPENT"]
    credits = film(tmp_path / "b", RED_TEXT, generability_exception=exception(max_attempts=3, max_credits=10))
    sent(credits, 1)  # 8 spent + 8 more > 10
    _, found = dry(credits, tmp_path / "b")
    assert found == ["EXCEPTION_SPENT"]
    pre_submit = film(tmp_path / "c", RED_TEXT, generability_exception=exception(max_attempts=1))
    sent(pre_submit, 1, result="START_NOT_FOUND")  # nothing was submitted: not an attempt
    assert dry(pre_submit, tmp_path / "c")[1] == []


def test_unknown_allows_one_send_then_the_cap(tmp_path):
    pkg = film(tmp_path, UNKNOWN_TEXT)
    done, found = dry(pkg, tmp_path)
    assert not set(found) & GATE and done["payload"]["attempts"]["level"] == "UNKNOWN"
    sent(pkg, 1)
    assert dry(pkg, tmp_path)[1] == ["SEND_CAP"]


def test_amber_second_send_waits_for_review(tmp_path):
    pkg = film(tmp_path, AMBER_TEXT)
    done, found = dry(pkg, tmp_path)
    assert not set(found) & GATE and done["payload"]["attempts"]["cap"] == 2
    sent(pkg, 1)
    take(pkg, 1, "GENERATED")
    assert dry(pkg, tmp_path)[1] == ["AWAITING_REVIEW"]
    set_status(pkg, 1, "REJECTED")
    done, found = dry(pkg, tmp_path)
    assert not set(found) & GATE and done["payload"]["attempts"]["this_version"] == 1
    sent(pkg, 2)
    take(pkg, 2, "REJECTED")
    assert dry(pkg, tmp_path)[1] == ["SEND_CAP"]


def test_version_bump_keeps_the_history_but_resets_the_cap(tmp_path):
    root = tmp_path / "film"
    pkg = film(tmp_path, GREEN_TEXT)
    sent(pkg, 1)
    assert dry(pkg, tmp_path)[1] == ["SEND_CAP"]
    edit_shot(root, version=2)
    bumped = reload(root)
    done, found = dry(bumped, tmp_path)
    assert not set(found) & GATE
    assert done["payload"]["attempts"] == {"this_version": 0, "all_versions": 1, "cap": 1, "level": "GREEN"}
    sent(bumped, 2, version=2)
    done, found = dry(bumped, tmp_path)
    assert found == ["SEND_CAP"]
    assert done["payload"]["attempts"]["this_version"] == 1 and done["payload"]["attempts"]["all_versions"] == 2


def test_film_without_the_opt_in_has_no_generability_blockers(tmp_path):
    pkg = film(tmp_path, RED_TEXT)
    pre = json.loads((pkg.root / "03_preprod.json").read_text(encoding="utf-8"))
    pre["preflight"]["generability"] = False
    (pkg.root / "03_preprod.json").write_text(json.dumps(pre), encoding="utf-8")
    done, found = dry(reload(pkg.root), tmp_path)
    assert not set(found) & GATE and "attempts" not in done["payload"]
