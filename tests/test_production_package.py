import json

import pytest

from film_pipeline.production.package import (
    GATE_NAMES, STAGE_FILES, FilmHeader, PackageError, load_package, save_header,
)

FOUNTAIN = "INT. LOBBY - DAY\n\nAN\nXin chao.\n"


def _film(tmp_path, profile="drama", **extra):
    header = FilmHeader(film_id="t1", title="Test", profile=profile, **extra)
    save_header(tmp_path, header)
    return header


def test_round_trip_header(tmp_path):
    h = _film(tmp_path, budget={"credits_estimate": 100})
    pkg = load_package(tmp_path)
    assert pkg.header == h
    assert pkg.header.budget.credits_cap == 150
    assert pkg.header.generation_s == 8
    assert pkg.header.gates == {k: "NOT_RUN" for k in GATE_NAMES}


def test_missing_film_json_is_error(tmp_path):
    with pytest.raises(PackageError, match="film.json not found"):
        load_package(tmp_path)


def test_unknown_profile_rejected(tmp_path):
    (tmp_path / "film.json").write_text(json.dumps({"film_id": "x", "title": "T", "profile": "docu"}))
    with pytest.raises(PackageError, match="profile"):
        load_package(tmp_path)


def test_unknown_gate_rejected(tmp_path):
    (tmp_path / "film.json").write_text(json.dumps(
        {"film_id": "x", "title": "T", "profile": "narration", "gates": {"9": "PASS"}}))
    with pytest.raises(PackageError, match="unknown gate"):
        load_package(tmp_path)


def test_invalid_json_is_error(tmp_path):
    (tmp_path / "film.json").write_text("{nope")
    with pytest.raises(PackageError, match="invalid JSON"):
        load_package(tmp_path)


def test_missing_stages_reported_not_raised(tmp_path):
    _film(tmp_path, profile="narration")
    (tmp_path / "05_edit.json").write_text(json.dumps({"concept": "c"}))
    pkg = load_package(tmp_path)
    assert pkg.stage("edit") == {"concept": "c"}
    assert set(pkg.missing_stages) == set(STAGE_FILES) - {"edit"}
    assert pkg.issues == []


def test_drama_script_parsed_and_missing_reported(tmp_path):
    _film(tmp_path)
    assert any("script.fountain missing" in i for i in load_package(tmp_path).issues)
    (tmp_path / "script.fountain").write_text(FOUNTAIN, encoding="utf-8")
    pkg = load_package(tmp_path)
    assert pkg.issues == [] and pkg.script is not None and len(pkg.script.scenes) == 1


def test_bad_stage_file_becomes_issue(tmp_path):
    _film(tmp_path, profile="narration")
    (tmp_path / "02_direction.json").write_text("[1]")
    (tmp_path / "03_preprod.json").write_text("{bad")
    pkg = load_package(tmp_path)
    assert len(pkg.issues) == 2 and "direction" not in pkg.stages
