"""P10-02: the start-still stage - register, approve, go stale, and feed generate / animatic."""
import json
import os
import shutil
import struct
import subprocess
import sys
import zlib
from pathlib import Path

import pytest

from film_pipeline.production import gate_checks as GC
from film_pipeline.production import stills as S
from film_pipeline.production.animatic import build_animatic
from film_pipeline.production.generate import build_payload
from film_pipeline.production.package import load_package
from film_pipeline.production.plan import plan_package

ROOT = Path(__file__).resolve().parents[1]
FILM04 = ROOT / "films" / "film04_last_ticket"
FILES = ("film.json", "script.fountain", "01_story.json", "02_direction.json", "03_preprod.json", "04_shots.json",
         "05_edit.json", "06_post.json", "07_delivery.json", "ledger.json")


def png(tmp_path: Path, name: str, shade: int = 10) -> Path:
    """A real 8x8 PNG, made by hand so the test needs no imaging library."""
    def chunk(tag: bytes, data: bytes) -> bytes:
        return struct.pack(">I", len(data)) + tag + data + struct.pack(">I", zlib.crc32(tag + data) & 0xFFFFFFFF)
    rows = b"".join(b"\x00" + bytes([shade, shade, shade]) * 8 for _ in range(8))
    body = (b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", 8, 8, 8, 2, 0, 0, 0))
            + chunk(b"IDAT", zlib.compress(rows)) + chunk(b"IEND", b""))
    path = tmp_path / name
    path.write_bytes(body)
    return path


@pytest.fixture()
def root(tmp_path):
    target = tmp_path / "film04"
    target.mkdir()
    for name in FILES:
        shutil.copyfile(FILM04 / name, target / name)
    # film04 now carries the Owner's real start still for SC01_g1; these tests start from a package with none registered
    pre = json.loads((target / "03_preprod.json").read_text(encoding="utf-8"))
    pre.pop("stills", None)
    (target / "03_preprod.json").write_text(json.dumps(pre, ensure_ascii=False, indent=2), encoding="utf-8")
    return target


def pkg_of(root):
    return load_package(root)


def head_and_chained(root):
    shots = pkg_of(root).typed["shots"].generations
    return shots[0].generation_id, next((g.generation_id for g in shots if g.previous_generation_id), None)


def test_list_shows_a_still_prompt_per_generation_and_what_is_waiting(root):
    rows = S.list_stills(pkg_of(root))
    assert len(rows) == 12 and all(r["state"] == "MISSING" for r in rows)
    heads = {r["generation_id"] for r in rows if r["needs_still"]}
    assert heads == set(S.chain_heads(pkg_of(root))) and "SC01_g1" in heads
    assert all(len(r["prompt_sha256"]) == 64 for r in rows)


def test_still_prompt_states_the_pose_of_the_first_instant_and_names_only_who_is_in_frame(root):
    # film04 SC01_g1: the approved still showed MARA seated; the shot says she stands, hand on the cord,
    # and the prompt called for a "two-shot, THEO left" with MARA alone
    pkg = pkg_of(root)
    prompt = S.still_prompts(pkg)["SC01_g1"]
    assert "First instant: MARA stands behind the counter at the ticket window, her hand on the shutter cord, the wall clock beside her." in prompt
    assert "THEO" not in prompt and "two-shot" not in prompt and "Only MARA in frame" in prompt


def test_register_copies_the_image_records_it_and_never_approves(root, tmp_path):
    gid = head_and_chained(root)[0]
    image = png(tmp_path, "made.png")
    out = S.register_still(pkg_of(root), gid, image, source="ChatGPT GPM tab 2", credits=0, now="2026-11-07T08:00:00+00:00")
    assert out["approved"] is False and out["file"] == f"media/stills/start_{gid}.png"
    assert (root / out["file"]).read_bytes() == image.read_bytes()
    record = json.loads((root / "03_preprod.json").read_text(encoding="utf-8"))["stills"][gid]
    assert record["source"] == "ChatGPT GPM tab 2" and record["sha256"] == out["sha256"] and record["approved_by"] == ""
    pkg = pkg_of(root)
    assert pkg.issues == []  # the typed section accepts its own record
    assert S.state_of(pkg, gid)[0] == "UNAPPROVED" and S.approved_still_path(pkg, gid) is None


def test_register_refuses_bad_input_and_writes_nothing(root, tmp_path):
    gid = head_and_chained(root)[0]
    before = (root / "03_preprod.json").read_text(encoding="utf-8")
    not_image = tmp_path / "x.png"
    not_image.write_bytes(b"this is text")
    for args, message in (((  "NOPE", png(tmp_path, "a.png")), "unknown generation"), ((gid, not_image), "not a PNG or JPEG"),
                          ((gid, tmp_path / "missing.png"), "image not found")):
        with pytest.raises(ValueError, match=message):
            S.register_still(pkg_of(root), *args)
    with pytest.raises(ValueError, match="negative"):
        S.register_still(pkg_of(root), gid, png(tmp_path, "b.png"), credits=-1)
    assert (root / "03_preprod.json").read_text(encoding="utf-8") == before and not (root / "media").exists()


def test_register_decodes_the_image_a_signature_alone_is_not_a_picture(root, tmp_path):
    """P11-06: a PNG/JPEG signature followed by garbage, or a cut-off file, is refused and nothing is written."""
    gid = head_and_chained(root)[0]
    before = (root / "03_preprod.json").read_text(encoding="utf-8")
    good = png(tmp_path, "good.png").read_bytes()
    png_magic, jpeg_magic = good[:8], bytes([0xFF, 0xD8, 0xFF, 0xE0])
    fakes = {"garbage.png": png_magic + b"not really a picture " * 20,
             "cut.png": good[:len(good) // 2],
             "corrupt.png": good[:-20] + bytes(20),              # intact signature, damaged tail
             "fake.jpg": jpeg_magic + b"junk" * 50}
    for name, data in fakes.items():
        path = tmp_path / name
        path.write_bytes(data)
        with pytest.raises(ValueError, match="does not decode"):
            S.register_still(pkg_of(root), gid, path)
    assert (root / "03_preprod.json").read_text(encoding="utf-8") == before and not (root / "media").exists()


def test_register_accepts_a_real_jpeg_and_a_real_png(root, tmp_path):
    PIL = pytest.importorskip("PIL.Image")
    gid = head_and_chained(root)[0]
    jpg = tmp_path / "real.jpg"
    PIL.new("RGB", (64, 36), (200, 30, 30)).save(jpg)
    assert S.register_still(pkg_of(root), gid, jpg)["file"].endswith(".jpg")
    assert S.decode_check(png(tmp_path, "ok.png")) == (8, 8)


def test_approve_needs_a_name_a_registered_current_still(root, tmp_path):
    gid = head_and_chained(root)[0]
    with pytest.raises(ValueError, match="register one first"):
        S.approve_still(pkg_of(root), gid, "Owner")
    S.register_still(pkg_of(root), gid, png(tmp_path, "made.png"))
    with pytest.raises(ValueError, match="reviewer's name"):
        S.approve_still(pkg_of(root), gid, "  ")
    out = S.approve_still(pkg_of(root), gid, " Owner ", now="2026-11-07T09:00:00+00:00")
    assert out["approved_by"] == "Owner"
    pkg = pkg_of(root)
    assert S.state_of(pkg, gid)[0] == "APPROVED" and S.approved_still_path(pkg, gid) == root / f"media/stills/start_{gid}.png"


def test_approval_goes_stale_when_the_prompt_or_the_file_changes(root, tmp_path):
    gid = head_and_chained(root)[0]
    S.register_still(pkg_of(root), gid, png(tmp_path, "made.png"))
    S.approve_still(pkg_of(root), gid, "Owner")
    assert S.state_of(pkg_of(root), gid)[0] == "APPROVED"
    (root / f"media/stills/start_{gid}.png").write_bytes(b"tampered")  # the file no longer is what was approved
    state, reason = S.state_of(pkg_of(root), gid)
    assert state == "STALE_FILE" and "changed after" in reason
    with pytest.raises(ValueError, match="cannot approve"):
        S.approve_still(pkg_of(root), gid, "Owner")
    S.register_still(pkg_of(root), gid, png(tmp_path, "made.png"))  # same image again: approval comes back
    assert S.state_of(pkg_of(root), gid)[0] == "APPROVED"
    raw = json.loads((root / "03_preprod.json").read_text(encoding="utf-8"))
    raw["stills"][gid]["prompt_sha256"] = "0" * 64  # what a re-planned, different still prompt looks like
    (root / "03_preprod.json").write_text(json.dumps(raw), encoding="utf-8")
    state, reason = S.state_of(pkg_of(root), gid)
    assert state == "STALE_PROMPT" and "make and register a new still" in reason
    assert S.approved_still_path(pkg_of(root), gid) is None


def test_a_different_image_resets_approval_and_keeps_the_old_one(root, tmp_path):
    gid = head_and_chained(root)[0]
    first = png(tmp_path, "one.png", 10)
    S.register_still(pkg_of(root), gid, first)
    S.approve_still(pkg_of(root), gid, "Owner")
    S.register_still(pkg_of(root), gid, png(tmp_path, "two.png", 200))
    assert S.state_of(pkg_of(root), gid)[0] == "UNAPPROVED"
    kept = list((root / "media/stills/history").glob(f"start_{gid}.*.png"))
    assert len(kept) == 1 and kept[0].read_bytes() == first.read_bytes()


def test_registering_a_still_does_not_make_the_plan_stale(root, tmp_path):
    plan_package(pkg_of(root), GC.plan_dir(root), storyboard=False)
    assert not any("stale" in i for i in GC.plan_issues(pkg_of(root)))
    gid = head_and_chained(root)[0]
    S.register_still(pkg_of(root), gid, png(tmp_path, "made.png"))
    S.approve_still(pkg_of(root), gid, "Owner")
    assert not any("stale" in i for i in GC.plan_issues(pkg_of(root)))
    raw = json.loads((root / "03_preprod.json").read_text(encoding="utf-8"))
    raw["preflight"]["max_prompt_words"] = raw["preflight"]["max_prompt_words"] - 1  # a real planning change
    (root / "03_preprod.json").write_text(json.dumps(raw), encoding="utf-8")
    assert any("stale" in i for i in GC.plan_issues(pkg_of(root)))


def blockers(root, gid, **kw):
    return {b["code"] for b in build_payload(pkg_of(root), gid, **kw)["blockers"]}


def test_generate_uses_the_approved_still_by_default(root, tmp_path):
    gid = head_and_chained(root)[0]
    assert "START_FRAME_MISSING" in blockers(root, gid)
    S.register_still(pkg_of(root), gid, png(tmp_path, "made.png"))
    assert "START_FRAME_NOT_APPROVED" in blockers(root, gid) and "START_FRAME_MISSING" not in blockers(root, gid)
    S.approve_still(pkg_of(root), gid, "Owner")
    payload = build_payload(pkg_of(root), gid)
    codes = {b["code"] for b in payload["blockers"]}
    assert not codes & {"START_FRAME_MISSING", "START_FRAME_NOT_APPROVED"}
    assert payload["start_frame"]["exists"] and payload["start_frame"]["file"].endswith(f"start_{gid}.png")
    assert payload["start_frame"]["sha256"] == json.loads((root / "03_preprod.json").read_text(
        encoding="utf-8"))["stills"][gid]["sha256"]


def test_generate_stills_dir_override_and_stale_approval(root, tmp_path):
    gid = head_and_chained(root)[0]
    S.register_still(pkg_of(root), gid, png(tmp_path, "made.png"))
    S.approve_still(pkg_of(root), gid, "Owner")
    other = tmp_path / "other"
    other.mkdir()
    assert "START_FRAME_MISSING" in blockers(root, gid, stills_dir=other)  # the override is used as given
    shutil.copyfile(png(tmp_path, "z.png", 99), other / f"start_{gid}.png")
    assert "START_FRAME_MISSING" not in blockers(root, gid, stills_dir=other)
    (root / f"media/stills/start_{gid}.png").write_bytes(b"tampered")
    assert "START_FRAME_NOT_APPROVED" in blockers(root, gid)  # a stale approval is not an approval


def test_animatic_defaults_to_approved_stills_only(root, tmp_path):
    pytest.importorskip("PIL")
    gid = head_and_chained(root)[0]
    S.register_still(pkg_of(root), gid, png(tmp_path, "made.png"))
    plain = build_animatic(pkg_of(root), tmp_path / "a1")
    assert not any(r["frame_source"] == "still" for r in plain["generations"])  # registered, not approved
    S.approve_still(pkg_of(root), gid, "Owner")
    approved = build_animatic(pkg_of(root), tmp_path / "a2")
    sources = {r["generation_id"]: r["frame_source"] for r in approved["generations"]}
    assert sources[gid] == "still" and list(sources.values()).count("still") == 1


def test_cli_list_register_approve(root, tmp_path):
    gid = head_and_chained(root)[0]

    def film(*args):
        done = subprocess.run([sys.executable, str(ROOT / "tools" / "film.py"), "stills", "--film", str(root), *args],
                              capture_output=True, text=True, encoding="utf-8", cwd=ROOT,
                              env={**os.environ, "PYTHONPATH": str(ROOT / "src"), "PYTHONIOENCODING": "utf-8"})
        return done.returncode, json.loads(done.stdout)

    code, body = film()
    assert code == 1 and gid in body["waiting"]
    assert film("--register", gid)[0] == 2  # --image is required
    code, body = film("--register", gid, "--image", str(png(tmp_path, "made.png")), "--source", "test")
    assert code == 0 and body["registered"]["approved"] is False
    assert film("--approve", gid)[0] == 1  # no --by
    code, body = film("--approve", gid, "--by", "Owner")
    assert code == 0 and body["approved"]["approved_by"] == "Owner"
    code, body = film()
    assert gid not in body["waiting"]
