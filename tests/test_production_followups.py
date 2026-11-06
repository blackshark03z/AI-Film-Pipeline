"""P1-00: explicit dialogue per generation, handoff verification from real evidence, limit on emitted text."""
import hashlib
import json
import shutil
from pathlib import Path

import pytest

from film_pipeline.drama.qc import HandoffQC
from film_pipeline.production.evidence import Attestations, HandoffReceipt, end_state_verified, passed_take_sha
from film_pipeline.production.package import load_package
from film_pipeline.production.plan import plan_package

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "films" / "film03_front_desk"
TAKES = ROOT / "docs" / "drama" / "film03" / "takes"


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def make_take(dir_: Path, gid: str, payload: bytes = b"video-bytes", **over):
    (dir_ / f"{gid}.mp4").write_bytes(payload)
    record = {"result": "PASSED", "file": f"{gid}.mp4", "sha256": hashlib.sha256(payload).hexdigest(), **over}
    (dir_ / f"{gid}.take.json").write_text(json.dumps(record), encoding="utf-8")
    return record["sha256"]


def passing_qc(prev, nxt):
    qc = HandoffQC.from_end_state(prev, nxt, load_package(SRC).typed["preprod"].states["SC01_g1"])
    for c in qc.checks:
        c.status = "PASS"
    qc.reviewer = "QA"
    return qc


# -- handoff evidence ------------------------------------------------------------------------------------------

def test_bare_or_empty_mp4_never_verifies(tmp_path):
    (tmp_path / "A.mp4").write_bytes(b"")
    assert not end_state_verified(tmp_path, "A", "B")
    (tmp_path / "A.mp4").write_bytes(b"x")  # exists, no take.json
    assert not end_state_verified(tmp_path, "A", "B")
    make_take(tmp_path, "A", b"")  # take.json present but zero bytes
    assert passed_take_sha(tmp_path, "A") is None


def test_hash_mismatch_or_failed_take_does_not_verify(tmp_path):
    make_take(tmp_path, "A")
    (tmp_path / "A.mp4").write_bytes(b"replaced")  # file swapped after the record
    assert passed_take_sha(tmp_path, "A") is None
    make_take(tmp_path, "B", result="FAILED")
    assert passed_take_sha(tmp_path, "B") is None


def test_passed_take_alone_is_not_a_review(tmp_path):
    make_take(tmp_path, "A")
    assert passed_take_sha(tmp_path, "A") and not end_state_verified(tmp_path, "A", "B")


def test_reviewed_receipt_bound_to_hash_verifies(tmp_path):
    digest = make_take(tmp_path, "A")
    receipt = HandoffReceipt(take_sha256=digest, qc=passing_qc("A", "B"))
    (tmp_path / "B.handoff_qc.json").write_text(receipt.model_dump_json(), encoding="utf-8")
    assert end_state_verified(tmp_path, "A", "B")
    # receipt for a different pair, an unreviewed QC, or another hash is not accepted
    assert not end_state_verified(tmp_path, "A", "C")
    bad = receipt.model_copy(update={"take_sha256": "0" * 64})
    (tmp_path / "B.handoff_qc.json").write_text(bad.model_dump_json(), encoding="utf-8")
    assert not end_state_verified(tmp_path, "A", "B")
    unreviewed = HandoffReceipt(take_sha256=digest, qc=HandoffQC.from_end_state(
        "A", "B", load_package(SRC).typed["preprod"].states["SC01_g1"]))
    (tmp_path / "B.handoff_qc.json").write_text(unreviewed.model_dump_json(), encoding="utf-8")
    assert not end_state_verified(tmp_path, "A", "B")


def test_attestation_pins_hash(tmp_path):
    digest = make_take(tmp_path, "A")
    att = Attestations(basis="legacy eye check, pinned by hash", attested_by="Tech Lead", takes={"A": digest})
    assert end_state_verified(tmp_path, "A", "B", att)
    (tmp_path / "A.mp4").write_bytes(b"other")
    assert not end_state_verified(tmp_path, "A", "B", att)


def test_film03_attestations_match_kept_takes():
    att = Attestations.model_validate_json((SRC / "handoff_attestations.json").read_text(encoding="utf-8"))
    assert len(att.takes) == 16
    for gid, digest in att.takes.items():
        assert sha(TAKES / f"{gid}.mp4") == digest


# -- explicit dialogue -----------------------------------------------------------------------------------------

@pytest.fixture()
def pkg_dir(tmp_path):
    dest = tmp_path / "p"
    shutil.copytree(SRC, dest)
    return dest


def edit(path, fn):
    data = json.loads(path.read_text(encoding="utf-8"))
    fn(data)
    path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")


def run_plan(pkg_dir, tmp_path):
    return plan_package(load_package(pkg_dir), tmp_path / "out", takes_dir=TAKES, storyboard=False)


def test_silent_shot_does_not_shift_dialogue(pkg_dir, tmp_path):
    # making SC01_g1 silent leaves line 14 unassigned: reported, and SC01_g2 keeps its own line (no shifting)
    edit(pkg_dir / "04_shots.json", lambda d: d["generations"][0].update(dialogue=[]))
    problems = run_plan(pkg_dir, tmp_path).problems
    assert any(p.startswith("DIALOGUE_UNASSIGNED SC01: line 14") for p in problems)
    line14 = next(e.text for sc in load_package(pkg_dir).script.scenes if sc.scene_id == "SC01"
                  for e in sc.elements if e.kind == "dialogue" and e.line_no == 14)
    assert line14 not in (tmp_path / "out" / "prompts" / "SC01_g1.txt").read_text(encoding="utf-8")
    assert line14 in (ROOT / "docs/drama/film03/prompts/SC01_g1.txt").read_text(encoding="utf-8")


def test_duplicate_and_unknown_dialogue_lines(pkg_dir, tmp_path):
    edit(pkg_dir / "04_shots.json", lambda d: (d["generations"][0].update(dialogue=[14, 19]),
                                               d["generations"][1].update(dialogue=[19, 999])))
    problems = run_plan(pkg_dir, tmp_path).problems
    assert any("DIALOGUE_DUPLICATE SC01_g2: line 19" in p for p in problems)
    assert any("DIALOGUE_UNKNOWN SC01_g2: line 999" in p for p in problems)


def test_dialogue_field_is_required(pkg_dir):
    edit(pkg_dir / "04_shots.json", lambda d: d["generations"][0].pop("dialogue"))
    assert any("dialogue" in i for i in load_package(pkg_dir).issues)


def test_film03_dialogue_matches_legacy_rule():
    pkg = load_package(SRC)
    scenes = {s.scene_id: [e.line_no for e in s.elements if e.kind == "dialogue"] for s in pkg.script.scenes}
    seen = {}
    for g in pkg.typed["shots"].generations:
        k = seen[g.scene_id] = seen.get(g.scene_id, 0) + 1
        assert g.dialogue == scenes[g.scene_id][k - 1:k]


# -- limit on emitted text -------------------------------------------------------------------------------------

def test_overlong_requires_a_documented_exception(pkg_dir, tmp_path):
    # film03 has four overlong prompts, each with a documented reason: no PROMPT_TOO_LONG problem
    assert not [p for p in run_plan(pkg_dir, tmp_path).problems if p.startswith("PROMPT_TOO_LONG")]
    edit(pkg_dir / "03_preprod.json", lambda d: d["accepted_overlong"].pop("SC02_g2"))
    problems = run_plan(pkg_dir, tmp_path).problems
    assert any(p.startswith("PROMPT_TOO_LONG SC02_g2: 222 words > 215") for p in problems)


def test_exceptions_are_exactly_the_overlong_prompts():
    pre = load_package(SRC).typed["preprod"]
    record = json.loads((ROOT / "docs/drama/film03/gate3_film03.json").read_text(encoding="utf-8"))
    over = {g for g, v in record["generations"].items() if v["words"] > pre.preflight.max_prompt_words}
    assert over == set(pre.accepted_overlong)
    assert all("Owner review pending" in why for why in pre.accepted_overlong.values())
