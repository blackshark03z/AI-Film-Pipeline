"""Defect custody: detector signal -> reviewed defect (bound to clip hash / time range) -> repair; unknown codes STOP."""
import json
from pathlib import Path
from typing import get_args

import pytest
from pydantic import ValidationError

from film_pipeline.agentic import CausalRepairRouter
from film_pipeline.agentic.causal_repair import _CAUSAL_ACTIONS, STOP_UNKNOWN_DEFECT
from film_pipeline.production import defects as D
from film_pipeline.production import takes as T
from film_pipeline.production.gates import evaluate_gate
from film_pipeline.production.package import load_package
from film_pipeline.production.qc_model import Cause, ReviewedDefect, TakeQc

from test_production_gate_checks import clone, register_all, sheet_pass

ROOT = Path(__file__).resolve().parents[1]


def _rejected_sheet(pkg, entry, defects=None, *, version=1):
    sheet = sheet_pass(T.dailies_template(pkg, entry))
    for c in sheet["qc"]["checks"]:
        if version >= 2:
            c["observed"] = {"frames_viewed": 1, "frames_total": None, "full_playback": True, "audio_listened": True}
    next(c for c in sheet["qc"]["checks"] if c["group"] == "spatial").update(result="FAIL", severity="P1",
                                                                          note="listener head at right edge")
    sheet["qc"]["evidence_version"] = version
    if defects is not None:
        sheet["qc"]["defects"] = defects
    return sheet


def _defect(entry, code="OFFFRAME_INTRUSION", **kw):
    return {"code": code, "clip_sha256": entry.output_sha256, "time_ranges": [[1.2, 5.0]], "note": "edge", **kw}


def _signal(code="EDGE_INTRUSION_SUSPECT"):
    return {"detector": "edge_intrusion", "detector_version": "1.0", "code": code}


def _film(tmp_path, v2=False):
    tmp_path.mkdir(parents=True, exist_ok=True)
    root = clone(tmp_path)
    if v2:
        raw = json.loads((root / "film.json").read_text(encoding="utf-8"))
        raw["qc_evidence_version"] = 2
        (root / "film.json").write_text(json.dumps(raw, indent=2), encoding="utf-8")
    pkg = load_package(root)
    return root, pkg, register_all(root, pkg, upto=1)[0]


# ------------------------------------------------------------------ registry


def test_registry_integrity():
    assert set(D.DEFECTS) == {"OFFFRAME_INTRUSION", "IDENTITY_DRIFT", "WRONG_SPEAKER_LIPSYNC", "DIALOGUE_TRUNCATED",
                              "GAZE_EYELINE_DRIFT", "PROP_CONTINUITY_BREAK", "CAMERA_INSTABILITY", "PROVIDER_ARTEFACT"}
    for code, spec in D.DEFECTS.items():
        assert spec.code == code and spec.description
        assert spec.cause in get_args(Cause)
        assert spec.repair_action in D.KNOWN_ACTIONS
        assert code in D.__doc__  # every code is listed in the module docstring
    assert {c for c, s in D.DEFECTS.items() if s.auto_retry_allowed} == {"PROVIDER_ARTEFACT"}
    assert not D.DEFECTS["OFFFRAME_INTRUSION"].auto_retry_allowed
    assert D.signal_may_confirm("OFFFRAME_INTRUSION", "EDGE_INTRUSION_SUSPECT")
    assert not D.signal_may_confirm("IDENTITY_DRIFT", "EDGE_INTRUSION_SUSPECT")
    assert not D.signal_may_confirm("NOPE", "EDGE_INTRUSION_SUSPECT")
    assert {a for opts in _CAUSAL_ACTIONS.values() for a in opts} <= D.KNOWN_ACTIONS  # the legacy table is all understood


# ------------------------------------------------------------------ ingest


def test_review_with_a_valid_defect_ingests_and_stores_it(tmp_path):
    root, pkg, entry = _film(tmp_path)
    sheet = _rejected_sheet(pkg, entry, [_defect(entry, source_signal=_signal())])
    out = T.ingest_review(root, pkg.header.film_id, sheet)
    assert out["status"] == "REJECTED"
    stored = json.loads(Path(out["review"]).read_text(encoding="utf-8"))
    assert stored["defects"][0]["code"] == "OFFFRAME_INTRUSION"
    assert stored["defects"][0]["source_signal"]["detector_version"] == "1.0"
    assert T.load_log(root, pkg.header.film_id).get(entry.take_id).cause == "STAGING"  # broad cause from the registry


def test_defect_bound_to_another_clip_is_refused(tmp_path):
    root, pkg, entry = _film(tmp_path)
    bad = _defect(entry, clip_sha256="0" * 64)
    with pytest.raises(ValueError, match="bound to clip 000000000000"):
        T.ingest_review(root, pkg.header.film_id, _rejected_sheet(pkg, entry, [bad]))


def test_unknown_code_bad_range_and_disallowed_signal_are_refused(tmp_path):
    root, pkg, entry = _film(tmp_path)
    with pytest.raises(ValueError, match="unknown defect code"):
        T.ingest_review(root, pkg.header.film_id, _rejected_sheet(pkg, entry, [_defect(entry, code="MADE_UP")]))
    with pytest.raises(ValueError, match="time range"):
        T.ingest_review(root, pkg.header.film_id, _rejected_sheet(pkg, entry, [_defect(entry, time_ranges=[[3, 3]])]))
    with pytest.raises(ValueError, match="cannot be confirmed from detector signal"):
        T.ingest_review(root, pkg.header.film_id,
                        _rejected_sheet(pkg, entry, [_defect(entry, code="IDENTITY_DRIFT", source_signal=_signal())]))
    assert T.load_log(root, pkg.header.film_id).get(entry.take_id).status == "GENERATED"  # nothing was stored


def test_v2_reject_needs_a_defect_but_v1_does_not(tmp_path):
    root, pkg, entry = _film(tmp_path, v2=True)
    with pytest.raises(ValueError, match="must carry at least one reviewed defect"):
        T.ingest_review(root, pkg.header.film_id, _rejected_sheet(pkg, entry, version=2))
    assert T.ingest_review(root, pkg.header.film_id,
                           _rejected_sheet(pkg, entry, [_defect(entry)], version=2))["status"] == "REJECTED"
    root1, pkg1, entry1 = _film(tmp_path / "v1")
    assert T.ingest_review(root1, pkg1.header.film_id, _rejected_sheet(pkg1, entry1))["status"] == "REJECTED"  # unchanged


def test_old_review_json_without_defects_loads_and_a_v2_pass_needs_none():
    raw = {"take_id": "t1", "generation_id": "g1", "checks": [{"group": "visual"}]}
    assert TakeQc.model_validate(raw).defects == []
    with pytest.raises(ValidationError):
        ReviewedDefect.model_validate({"code": "OFFFRAME_INTRUSION", "clip_sha256": "x" * 64, "time_ranges": [[0, 1]]})


# ------------------------------------------------------------------ router


def test_router_maps_offframe_intrusion_to_restage_without_auto_retry():
    r = CausalRepairRouter().route("g1", "OFFFRAME_INTRUSION", failed_attempts=1)
    assert r["action"] == "enable_de_personify_off_frame"
    assert r["auto_retry_allowed"] is False and r["halted"] is False
    again = CausalRepairRouter().route("g1", "OFFFRAME_INTRUSION", failed_attempts=2)
    assert again["action"] == "ESCALATE_TO_TECH_LEAD" and again["auto_retry_allowed"] is False


def test_unknown_code_stops_with_no_retry_even_over_budget():
    router = CausalRepairRouter()
    for attempts in (1, 5):
        r = router.route("g1", "SOMETHING_NEW", failed_attempts=attempts)
        assert r["action"] == STOP_UNKNOWN_DEFECT == "STOP_UNKNOWN_DEFECT"
        assert r["auto_retry_allowed"] is False and r["halted"] is True and "SOMETHING_NEW" in r["reason"]
    assert router.route_defects("g1", ["OFFFRAME_INTRUSION", "MADE_UP"])["action"] == STOP_UNKNOWN_DEFECT
    assert router.route_defects("g1", [])["action"] == STOP_UNKNOWN_DEFECT  # a signal alone is not a reviewed defect
    assert router.route_defects("g1", ["UNKNOWN"])["action"] == STOP_UNKNOWN_DEFECT


def test_provider_artefact_may_retry_and_mixed_defects_take_the_strictest_row():
    router = CausalRepairRouter()
    r = router.route("g1", "PROVIDER_ARTEFACT")
    assert r["action"] == "retry_transient_once" and r["auto_retry_allowed"] is True
    mixed = router.route_defects("g1", ["PROVIDER_ARTEFACT", "IDENTITY_DRIFT"])
    assert mixed["auto_retry_allowed"] is False and mixed["action"] == "restage_clean_character_still"
    assert mixed["defect_codes"] == ["PROVIDER_ARTEFACT", "IDENTITY_DRIFT"]


def test_legacy_cause_path_is_unchanged():
    router = CausalRepairRouter()
    assert router.route("g1", "PROMPT")["action"] == "rewrite_prompt_plain_single_action"
    assert router.route("g1", "")["action"] == "CLASSIFY"
    assert router.route("g1", "PROVIDER_CONTENT_REFUSAL")["halted"] is True


def test_diagnose_routes_from_the_reviewed_defect_and_stops_on_a_removed_code(tmp_path):
    root, pkg, entry = _film(tmp_path)
    out = T.ingest_review(root, pkg.header.film_id, _rejected_sheet(pkg, entry, [_defect(entry)]))
    diag = CausalRepairRouter().diagnose_take_log(load_package(root))
    assert [d["action"] for d in diag] == ["enable_de_personify_off_frame"] and diag[0]["auto_retry_allowed"] is False
    assert diag[0]["defect_codes"] == ["OFFFRAME_INTRUSION"]
    review = Path(out["review"])
    raw = json.loads(review.read_text(encoding="utf-8"))
    raw["defects"][0]["code"] = "RETIRED_CODE"
    review.write_text(json.dumps(raw), encoding="utf-8")
    diag = CausalRepairRouter().diagnose_take_log(load_package(root))
    assert diag[0]["action"] == STOP_UNKNOWN_DEFECT and diag[0]["auto_retry_allowed"] is False


def test_diagnose_ignores_detector_signals_without_a_reviewed_defect(tmp_path):
    root, pkg, entry = _film(tmp_path)
    T.ingest_review(root, pkg.header.film_id, _rejected_sheet(pkg, entry))  # v1 reject, no cause -> classify, not repair
    diag = CausalRepairRouter().diagnose_take_log(load_package(root))
    assert diag[0]["action"] == "CLASSIFY" and diag[0]["auto_retry_allowed"] is False


# ------------------------------------------------------------------ real films stay valid


def test_real_film06_07_08_reviews_still_load_and_gate4_is_unchanged():
    reviews = [p for f in ("film06_six_am", "film07_first_shift", "film08_chain_of_custody")
               for p in (ROOT / "films" / f / "takes" / "reviews").glob("*.qc.json")]
    assert reviews
    for p in reviews:
        raw = json.loads(p.read_text(encoding="utf-8"))
        raw.pop("output_sha256", None)
        assert TakeQc.model_validate(raw).defects == []
    for f in ("film06_six_am", "film07_first_shift", "film08_chain_of_custody"):
        assert evaluate_gate(load_package(ROOT / "films" / f), "4").status == "PASS", f
