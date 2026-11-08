"""P16-05: continuity across screenplay scene numbers inside one encounter (production/continuity.py)."""
import copy
import json
from pathlib import Path

from film_pipeline.production.continuity import continuity_issues
from film_pipeline.production.package import load_package

ROOT = Path(__file__).resolve().parents[1]
FILM04 = ROOT / "films" / "film04_last_ticket"
FILES = ("film.json", "script.fountain", "01_story.json", "02_direction.json", "03_preprod.json", "04_shots.json")
LOC = "ticket_office_night"
MARKS = [{"id": "booth_stand", "at": [0.60, 0.30], "zone": "booth"},
         {"id": "booth_stool", "at": [0.62, 0.30], "zone": "booth"},
         {"id": "hall_window", "at": [0.62, 0.52], "zone": "hall"}]
STAND = {"mark": "booth_stand", "posture": "standing"}
SIT = {"mark": "booth_stool", "posture": "seated"}


def _load(path):
    return json.loads(path.read_text(encoding="utf-8"))


def _save(path, data):
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def make(tmp_path, *, contract=True, encounter=True, end=STAND, start=SIT, ellipsis=""):
    root = tmp_path / "film"
    root.mkdir(parents=True)
    for name in FILES:
        (root / name).write_text((FILM04 / name).read_text(encoding="utf-8"), encoding="utf-8")
    pre = _load(root / "03_preprod.json")
    pre["preflight"]["interaction_contract"] = contract
    pre["locations"][LOC]["layout"]["marks"] = copy.deepcopy(MARKS)
    pre["states"]["SC01_end"]["blocking"] = {"MARA": copy.deepcopy(end)}
    pre["states"]["SC02_g1"]["blocking"] = {"MARA": copy.deepcopy(start)}
    if encounter:
        for sc in ("SC01", "SC02"):
            pre["scenes"][sc]["encounter_id"] = "E1"
    _save(root / "03_preprod.json", pre)
    shots = _load(root / "04_shots.json")
    next(g for g in shots["generations"] if g["generation_id"] == "SC02_g1")["handoff_ellipsis"] = ellipsis
    _save(root / "04_shots.json", shots)
    return load_package(root)


def found(pkg, prefix="SPATIAL_HANDOFF_BLOCKING"):
    return [i for i in continuity_issues(pkg.typed["preprod"], pkg.typed["shots"], include_temporal=False)
            if i.check.startswith(prefix)]


def test_blocking_jump_across_scene_numbers_blocks(tmp_path):
    pkg = make(tmp_path)
    (issue,) = found(pkg)
    assert issue.check == "SPATIAL_HANDOFF_BLOCKING" and issue.severity == "BLOCK"
    assert issue.detail.startswith("SC02_g1:") and "MARA" in issue.detail
    assert "booth_stand, standing" in issue.detail and "booth_stool, seated" in issue.detail


def test_declared_ellipsis_warns(tmp_path):
    pkg = make(tmp_path, ellipsis="she sits down while THEO pleads")
    (issue,) = found(pkg)
    assert issue.check == "SPATIAL_HANDOFF_BLOCKING_ELLIPSIS" and issue.severity == "WARN"
    assert not [i for i in found(pkg, "SPATIAL") if i.severity == "BLOCK"]


def test_same_blocking_is_clean(tmp_path):
    assert found(make(tmp_path, start=STAND), "SPATIAL_HANDOFF") == []


def test_no_encounter_is_not_continuous(tmp_path):
    pkg = make(tmp_path, encounter=False)
    assert found(pkg, "SPATIAL_HANDOFF") == []


def test_contract_off_matches_shipped(tmp_path):
    pkg = make(tmp_path, contract=False)
    shipped = load_package(FILM04)
    mine = [i.model_dump() for i in continuity_issues(pkg.typed["preprod"], pkg.typed["shots"])]
    base = [i.model_dump() for i in continuity_issues(shipped.typed["preprod"], shipped.typed["shots"])]
    assert mine == base
    assert not [i for i in mine if i["check"].startswith("SPATIAL_HANDOFF")]
