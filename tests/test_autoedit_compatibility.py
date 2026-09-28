import copy
import hashlib
import json
import subprocess
import sys
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator, ValidationError

from film_pipeline.autoedit_export import (export_film_package, package_identity,
    validate_envelope, validate_producer_package, verify_media, write_referenced_package)
from film_pipeline.editorial import EditClip, EditorialStore, make_edit_manifest

ROOT = Path(__file__).resolve().parents[1]
FIXTURES = ROOT / "fixtures/integration/autoedit_v0"
SCHEMA = ROOT / "docs/integration/edit_job_input_v0.schema.json"
GOLDEN = FIXTURES / "one_selected_take_with_timeline_hint"
VALID = ["one_media_no_timeline.json", "multi_media.json", "with_transcript.json",
         "with_frozen_constraint.json", "with_optional_film_metadata.json",
         "one_selected_take_with_timeline_hint/edit_job.json"]


def load(name):
    return json.loads((FIXTURES / name).read_text(encoding="utf-8"))


@pytest.mark.parametrize("name", VALID)
def test_valid_generic_and_film_producer_fixtures(name):
    payload = load(name)
    Draft202012Validator(json.loads(SCHEMA.read_text())).validate(payload)
    validate_envelope(payload)
    if name != "one_selected_take_with_timeline_hint/edit_job.json":
        verify_media(payload, package_root=FIXTURES, roots={})


def test_schema_and_every_valid_fixture_work_without_film_imports_or_db():
    # A separate process uses only JSON + jsonschema, with Film imports forbidden.
    program = """
import json, sys
from pathlib import Path
from jsonschema import Draft202012Validator
class NoFilmImports:
    def find_spec(self, fullname, path=None, target=None):
        if fullname == 'film_pipeline' or fullname.startswith('film_pipeline.'):
            raise AssertionError('Film dependency is forbidden')
sys.meta_path.insert(0, NoFilmImports())
validator = Draft202012Validator(json.loads(Path(sys.argv[1]).read_text()))
for filename in sys.argv[2:]:
    validator.validate(json.loads(Path(filename).read_text()))
assert not any(name.startswith('film_pipeline') for name in sys.modules)
print('independent_schema_fixtures_pass')
"""
    result = subprocess.run([sys.executable, "-I", "-c", program, str(SCHEMA),
                             *[str(FIXTURES / name) for name in VALID]],
                            capture_output=True, text=True, check=False)
    assert result.returncode == 0, result.stderr
    assert "independent_schema_fixtures_pass" in result.stdout


@pytest.mark.parametrize("name", ["malformed_missing_media.json", "malformed_bad_version.json"])
def test_malformed_structural_fixtures_rejected(name):
    with pytest.raises(ValidationError):
        validate_envelope(load(name))


def test_hash_mismatch_requires_actual_byte_verification():
    payload = load("malformed_hash_mismatch.json")
    validate_envelope(payload)  # Well-formed hash is not matching-byte evidence.
    with pytest.raises(ValueError, match="SHA-256 mismatch"):
        verify_media(payload, package_root=FIXTURES, roots={})
    referenced = load("one_selected_take_with_timeline_hint/edit_job.json")
    with pytest.raises(ValueError, match="root binding unavailable"):
        verify_media(referenced, package_root=GOLDEN, roots={})


def test_golden_provenance_hash_and_optional_film_removal():
    payload = load("one_selected_take_with_timeline_hint/edit_job.json")
    media = payload["media"][0]
    assert media["sha256"] == "c5014f1438dd8b4e1fbcd85df85fc5216bf91985b2164d0afbe5c3a0695abacf"
    film = payload["optional_provenance"]["film"]
    link = film["by_media_id"][media["media_id"]][0]
    assert link["selected_take_id"] == "take_a4f85e57ca88fe9629eb0c377ca6751711116c2f61425d9595d75ba09898647b"
    assert link["asset_id"] == "asset_c45abad93f33adbf43a6da62f3a04091b1cb712314ef209e6d84bea31a653c01"
    assert link["shot_id"] == "FLOW_CANARY_001" and link["qc_decision"] == "pass"
    assert film["edit_manifest_id"] == "edit_52750848b473f76fd6e14f4007fa30b73a25082017e2d0fa191efcb44526ecc5"
    assert payload["optional_timeline_hint"]["authority"] == "suggestion"
    assert payload["frozen_constraints"] == []
    minimal = {key: payload[key] for key in ("contract_version", "job_id", "media")}
    Draft202012Validator(json.loads(SCHEMA.read_text())).validate(minimal)
    validate_envelope(minimal)
    checks = json.loads((GOLDEN / "checksums.json").read_text())
    assert checks["package_id"] == package_identity(payload)
    assert checks["edit_job_sha256"] == hashlib.sha256((GOLDEN / "edit_job.json").read_bytes()).hexdigest()


def test_unknown_optional_content_is_preserved_but_structural_fields_rejected():
    payload = load("one_media_no_timeline.json")
    payload["extensions"] = {"future:observations": {"unknown_field": [1, 2, 3]}}
    payload["optional_semantic_metadata"] = {"new_producer": {"arbitrary_metadata": True}}
    validate_envelope(payload)
    assert package_identity(payload) == package_identity(copy.deepcopy(payload))
    changed = copy.deepcopy(payload)
    changed["extensions"]["future:observations"]["unknown_field"].append(4)
    assert package_identity(changed) != package_identity(payload)
    payload["unknown_top_level"] = {}
    with pytest.raises(ValidationError):
        validate_envelope(payload)


@pytest.mark.parametrize("path", ["../video.mp4", "a/../video.mp4", "/absolute.mp4",
                                  "C:/absolute.mp4", "a\\video.mp4", "a/./video.mp4"])
def test_portable_locator_schema_rejects_machine_paths_and_traversal(path):
    payload = load("one_media_no_timeline.json")
    payload["media"][0]["locator"]["path"] = path
    with pytest.raises(ValidationError):
        Draft202012Validator(json.loads(SCHEMA.read_text())).validate(payload)


def test_constraints_are_explicit_and_identity_references_unambiguous():
    payload = load("with_frozen_constraint.json")
    assert len(payload["frozen_constraints"]) == 1
    payload["frozen_constraints"][0]["media_ids"] = ["unknown_media"]
    with pytest.raises(ValueError, match="unknown media"):
        validate_envelope(payload)
    payload = load("one_media_no_timeline.json")
    payload["media"].append(copy.deepcopy(payload["media"][0]))
    with pytest.raises(ValueError, match="duplicate media"):
        validate_envelope(payload)
    payload = load("one_selected_take_with_timeline_hint/edit_job.json")
    payload["optional_timeline_hint"]["authority"] = "frozen"
    with pytest.raises(ValidationError):
        validate_envelope(payload)


def test_film_export_same_state_across_two_machine_roots_is_identical(tmp_path):
    from test_editorial_slice import approved_runtime

    exported = []
    for name in ("machine_a", "machine_b"):
        machine_root = tmp_path / name
        machine_root.mkdir()
        runtime, asset, take = approved_runtime(machine_root)
        manifest = make_edit_manifest("fixture_project", [EditClip(order=1, shot_id=take.shot_id,
            selected_take_id=take.selected_take_id, asset_id=asset.asset_id)])
        EditorialStore(runtime).save_manifest(manifest)
        before = hashlib.sha256(runtime.path.read_bytes()).hexdigest()
        destination = tmp_path / (name + "_export")
        result = export_film_package(runtime.path, manifest_id=manifest.edit_manifest_id,
            media_root=machine_root, destination=destination)
        assert hashlib.sha256(runtime.path.read_bytes()).hexdigest() == before
        payload = validate_producer_package(destination, roots={"film_workspace": machine_root})
        assert payload["media"][0]["sha256"] == asset.sha256
        assert str(machine_root) not in json.dumps(payload)
        repeated = export_film_package(runtime.path, manifest_id=manifest.edit_manifest_id,
            media_root=machine_root, destination=destination)
        assert repeated == result
        exported.append((result, (destination / "edit_job.json").read_bytes(),
                         (destination / "checksums.json").read_bytes()))
    assert exported[0] == exported[1]


def test_package_tamper_and_overwrite_are_rejected(tmp_path):
    payload = load("one_media_no_timeline.json")
    payload["media"][0].update(storage="referenced", locator={"kind": "root_relative",
        "root_id": "fixture_media", "path": "media/color.ppm"})
    destination = tmp_path / "package"
    roots = {"fixture_media": FIXTURES}
    original_id = write_referenced_package(payload, destination, roots=roots)
    assert original_id == package_identity(validate_producer_package(destination, roots=roots))
    changed = copy.deepcopy(payload)
    changed["user_intent"] = {"request": "different input"}
    with pytest.raises(ValueError, match="refusing overwrite"):
        write_referenced_package(changed, destination, roots=roots)
    (destination / "edit_job.json").write_text(json.dumps(changed), encoding="utf-8")
    with pytest.raises(ValueError, match="checksum or identity"):
        validate_producer_package(destination, roots=roots)


@pytest.mark.parametrize("filename", ["edit_job.json", "checksums.json"])
def test_duplicate_json_keys_cannot_hide_frozen_authority_or_checksum(tmp_path, filename):
    payload = load("one_media_no_timeline.json")
    payload["frozen_constraints"] = []
    payload["media"][0].update(storage="referenced", locator={"kind": "root_relative",
        "root_id": "fixture_media", "path": "media/color.ppm"})
    roots = {"fixture_media": FIXTURES}
    write_referenced_package(payload, tmp_path / "package", roots=roots)
    directory = tmp_path / "package"
    if filename == "edit_job.json":
        text = (directory / filename).read_text(encoding="utf-8")
        text = text.replace('"frozen_constraints":[]',
            '"frozen_constraints":[{"constraint_id":"owner_lock","requirement":"Do not reorder."}],'
            '"frozen_constraints":[]')
        contents = text.encode("utf-8")
        (directory / filename).write_bytes(contents)
        checks = json.loads((directory / "checksums.json").read_bytes())
        # Match the raw bytes and last-wins semantic hash, so checksum alone cannot save us.
        checks["edit_job_sha256"] = hashlib.sha256(contents).hexdigest()
        (directory / "checksums.json").write_text(json.dumps(checks), encoding="utf-8")
    else:
        text = (directory / filename).read_text(encoding="utf-8")
        digest = payload["media"][0]["sha256"]
        text = text.replace('"generic_image":"' + digest + '"',
            '"generic_image":"' + digest + '","generic_image":"' + digest + '"')
        (directory / filename).write_text(text, encoding="utf-8")
    with pytest.raises(ValueError, match="duplicate JSON key"):
        validate_producer_package(directory, roots=roots)
