"""QC evidence version 2: a take review states what was actually examined (observed); version 1 records are unchanged."""
import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from film_pipeline import cli as cli_mod
from film_pipeline.production import review_ui as RUI
from film_pipeline.production import takes as T
from film_pipeline.production.gates import evaluate_gate
from film_pipeline.production.package import FilmHeader, load_package
from film_pipeline.production.qc_model import MIN_LEVEL, GroupCheck, Observation, TakeQc

from test_production_gate_checks import accepted_one, clone, register_all


def chk(group="visual", result="PASS", level="SAMPLED", reviewer="human:owner", evidence="reviews/x.png", observed=None,
        **kw):
    return {"group": group, "result": result, "level": level, "reviewer": reviewer, "evidence": evidence,
            "observed": observed, **kw}


def rec(*checks, version=2):
    return TakeQc.model_validate({"take_id": "t1", "generation_id": "g1", "evidence_version": version, "checks": list(checks)})


def obs(frames_viewed=1, frames_total=None, full_playback=False, audio_listened=False):
    return {"frames_viewed": frames_viewed, "frames_total": frames_total, "full_playback": full_playback,
            "audio_listened": audio_listened}


# --------------------------------------------------------------------------- a. observed required


def test_a_observed_is_required_on_a_judged_v2_check():
    with pytest.raises(ValidationError, match=r"visual.*requires `observed`"):
        rec(chk())
    assert rec(chk(observed=obs())).check("visual").observed == Observation(frames_viewed=1)


def test_a_unassessed_and_auto_checks_need_no_observed():
    rec({"group": "visual"})  # UNASSESSED
    rec(chk(group="technical", level="FULL_MOTION", reviewer="auto:ffprobe", evidence="probe.json"))


# --------------------------------------------------------------------------- b. level vs what was seen


def test_b_full_motion_needs_full_playback_or_every_frame():
    with pytest.raises(ValidationError, match=r"visual.*level FULL_MOTION needs full_playback or every frame"):
        rec(chk(level="FULL_MOTION", observed=obs(frames_viewed=3, frames_total=24)))
    with pytest.raises(ValidationError, match="level CUT needs full_playback"):
        rec(chk(level="CUT", observed=obs(frames_viewed=3)))
    rec(chk(level="FULL_MOTION", observed=obs(frames_viewed=0, full_playback=True)))
    rec(chk(level="FULL_MOTION", reviewer="agent:tech-lead", observed=obs(frames_viewed=24, frames_total=24)))


# --------------------------------------------------------------------------- c. SAMPLED needs a frame


def test_c_sampled_needs_at_least_one_frame():
    with pytest.raises(ValidationError, match=r"visual.*SAMPLED needs frames_viewed >= 1"):
        rec(chk(observed=obs(frames_viewed=0)))
    rec(chk(observed=obs(frames_viewed=1)))


# --------------------------------------------------------------------------- d. agents cannot watch in real time / listen


def test_d_agent_cannot_claim_playback_or_listening():
    with pytest.raises(ValidationError, match=r"visual.*only a human: reviewer"):
        rec(chk(reviewer="agent:tech-lead", level="FULL_MOTION", observed=obs(0, full_playback=True)))
    with pytest.raises(ValidationError, match=r"visual.*only a human: reviewer"):
        rec(chk(reviewer="agent:tech-lead", observed=obs(1, audio_listened=True)))
    rec(chk(observed=obs(0, full_playback=True), level="FULL_MOTION"))  # a human may


# --------------------------------------------------------------------------- e. audio / sync PASS needs listening


@pytest.mark.parametrize("group", ["audio", "sync"])
def test_e_audio_and_sync_pass_by_judgment_need_audio_listened(group):
    with pytest.raises(ValidationError, match=rf"{group}.*needs audio_listened"):
        rec(chk(group=group, level="FULL_MOTION", observed=obs(0, full_playback=True)))
    with pytest.raises(ValidationError, match=rf"{group}.*needs audio_listened"):
        rec(chk(group=group, level="FULL_MOTION", reviewer="agent:tech-lead", observed=obs(10, 10)))
    rec(chk(group=group, level="FULL_MOTION", observed=obs(0, full_playback=True, audio_listened=True)))
    rec(chk(group=group, level="FULL_MOTION", reviewer="auto:vosk", evidence="stt.json"))  # machine evidence may PASS
    rec(chk(group=group, result="WARN", level="SAMPLED", observed=obs(1)))  # only PASS is gated


# --------------------------------------------------------------------------- f. contradiction guard


@pytest.mark.parametrize("text", ["3-frame contact strip, audio not listened to", "Sampled Frames Only", "12-frame strip",
                                  "contact strip", "audio NOT LISTENED"])
@pytest.mark.parametrize("where", ["evidence", "note"])
def test_f_full_motion_contradicted_by_its_own_evidence(text, where):
    kw = {where: text}
    if where == "note":
        kw["evidence"] = "reviews/x.png"
    with pytest.raises(ValidationError, match=r"visual.*must be SAMPLED"):
        rec(chk(level="FULL_MOTION", observed=obs(0, full_playback=True), **kw))
    rec(chk(level="SAMPLED", observed=obs(3), **kw))  # honest: it was sampled


# --------------------------------------------------------------------------- v1 unchanged


def test_v1_record_with_the_old_claim_still_validates():
    v1 = rec(chk(level="FULL_MOTION", evidence="3-frame contact strip ... audio not listened to"), version=1)
    assert v1.evidence_version == 1 and v1.check("visual").observed is None
    legacy = TakeQc.model_validate({"take_id": "t", "generation_id": "g", "checks": [
        {"group": "visual", "result": "PASS", "level": "FULL_MOTION", "reviewer": "human:o", "evidence": "x"}]})
    assert legacy.evidence_version == 1
    GroupCheck(group="audio", result="PASS", level="FULL_MOTION", reviewer="human:o", evidence="e")  # no observed needed


# --------------------------------------------------------------------------- header, scaffold, ingest, gate 4


def test_header_default_is_1_and_bounded():
    h = FilmHeader(film_id="f", title="t", profile="drama")
    assert h.qc_evidence_version == 1
    with pytest.raises(ValidationError):
        FilmHeader(film_id="f", title="t", profile="drama", qc_evidence_version=3)


def test_scaffold_sets_evidence_version_2(tmp_path):
    target = cli_mod.scaffold("film_new", "drama", tmp_path, None)
    assert json.loads((target / "film.json").read_text(encoding="utf-8"))["qc_evidence_version"] == 2
    assert load_package(target).header.qc_evidence_version == 2


def _v2_film(tmp_path):
    root = clone(tmp_path)
    raw = json.loads((root / "film.json").read_text(encoding="utf-8"))
    raw["qc_evidence_version"] = 2
    (root / "film.json").write_text(json.dumps(raw, indent=2), encoding="utf-8")
    pkg = load_package(root)
    entry = register_all(root, pkg, upto=1)[0]
    return root, pkg, entry


def _v2_sheet(pkg, entry, **observed):
    sheet = T.dailies_template(pkg, entry)
    assert sheet["qc"]["evidence_version"] == 2  # the template carries the film's version
    for c in sheet["qc"]["checks"]:
        level = MIN_LEVEL[c["group"]]
        c.update(result="PASS", level=level, evidence="reviews/x.png", reviewer="human:owner",
                 observed=obs(1 if level == "SAMPLED" else 0, full_playback=True, audio_listened=True))
    return sheet


def test_ingest_refuses_a_v1_review_on_a_v2_film_and_accepts_a_v2_one(tmp_path):
    root, pkg, entry = _v2_film(tmp_path)
    old = _v2_sheet(pkg, entry)
    old["qc"]["evidence_version"] = 1
    for c in old["qc"]["checks"]:
        c.pop("observed")
    with pytest.raises(ValueError, match=r"evidence_version 1.*qc_evidence_version is 2"):
        T.ingest_review(root, pkg.header.film_id, old)
    with pytest.raises(ValueError, match=r"evidence_version 1.*qc_evidence_version is 2"):
        T.ingest_review(root, pkg.header.film_id, old, pkg=pkg)
    unobserved = _v2_sheet(pkg, entry)
    unobserved["qc"]["checks"][0].pop("observed")
    with pytest.raises(ValueError, match="requires `observed`"):
        T.ingest_review(root, pkg.header.film_id, unobserved)
    assert T.ingest_review(root, pkg.header.film_id, _v2_sheet(pkg, entry))["status"] == "ACCEPTED"
    assert evaluate_gate(load_package(root), "4").status in ("PASS", "OWNER_PENDING", "BLOCK")  # still evaluates


def test_gate4_flags_a_stored_v1_review_once_the_film_requires_v2(tmp_path):
    root, pkg, entry, _ = accepted_one(tmp_path)
    before = evaluate_gate(load_package(root), "4").issues  # a v1 film: no evidence-version issue
    assert not any("evidence_version" in i for i in before)
    raw = json.loads((root / "film.json").read_text(encoding="utf-8"))
    raw["qc_evidence_version"] = 2
    (root / "film.json").write_text(json.dumps(raw, indent=2), encoding="utf-8")
    res = evaluate_gate(load_package(root), "4")
    assert res.status == "BLOCK"
    assert any(i.startswith(entry.take_id) and "stored review has evidence_version 1" in i and "qc_evidence_version is 2" in i for i in res.issues)


# --------------------------------------------------------------------------- review_ui


def test_review_ui_no_longer_hardcodes_full_motion():
    html = RUI._TEMPLATE
    assert 'level: "FULL_MOTION", reviewer' not in html
    assert "level: seen.level" in html and "evidence_version: 2" in html
    assert 'level: "SAMPLED"' in html and "full_playback: true" in html and "full_playback: false" in html
    assert "audio_listened: coverage(w, w.heard) >= AUDIO_COVERAGE" in html
    assert 'data-vid="${item.take_id}"' in html
