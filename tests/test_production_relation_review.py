"""P16-04 relation review questions: ids, required answers in the verdict, template, supplemental sheet."""
import copy
import json
from pathlib import Path

import pytest

from film_pipeline.production import takes as T
from film_pipeline.production.package import load_package
from film_pipeline.production.qc_model import MIN_LEVEL
from film_pipeline.production.relation_review import relation_questions, speakers_of

from test_production_interaction import legacy_film04

ROOT = Path(__file__).resolve().parents[1]
FILM04 = ROOT / "films" / "film04_last_ticket"
FILES = ("film.json", "script.fountain", "01_story.json", "02_direction.json", "03_preprod.json", "04_shots.json")
LOC = "ticket_office_night"
MARKS = [{"id": "booth_stool", "at": [0.62, 0.30], "zone": "booth"},
         {"id": "hall_window", "at": [0.62, 0.52], "zone": "hall"}]
POSES = {"MARA": {"mark": "booth_stool", "posture": "seated"}, "THEO": {"mark": "hall_window", "posture": "standing"}}
OTS = {"coverage": "OTS", "foreground": "THEO", "subject": "MARA", "visible": ["MARA", "THEO"], "version": 4,
       "addressees": {"22": ["THEO"]}, "gaze_target": "THEO",
       "listener_anchors": {"THEO": {"mode": "OTS_FOREGROUND"}}}
IDS = ["REL_ADDRESS:22", "REL_LISTENER:THEO", "REL_GAZE", "REL_BARRIER"]


def _load(path):
    return json.loads(path.read_text(encoding="utf-8"))


def _save(path, data):
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def make(tmp_path, *, contract=True):
    root = tmp_path / "film"
    root.mkdir(parents=True)
    for name in FILES:
        (root / name).write_text((FILM04 / name).read_text(encoding="utf-8"), encoding="utf-8")
    pre = _load(root / "03_preprod.json")
    shots = _load(root / "04_shots.json")
    legacy_film04(pre, shots)  # the shipped film04 is the P16-07a pilot: start from the plain v3 package
    if contract:
        pre["preflight"]["interaction_contract"] = True
        pre["locations"][LOC]["layout"]["marks"] = copy.deepcopy(MARKS)
        for sid in ("SC01_g2", "SC01_end", "SC02_g1", "SC02_g2", "SC02_end"):
            pre["states"][sid]["blocking"] = copy.deepcopy(POSES)
    _save(root / "03_preprod.json", pre)
    g = next(x for x in shots["generations"] if x["generation_id"] == "SC02_g1")
    if contract:
        g.update(copy.deepcopy(OTS))
    _save(root / "04_shots.json", shots)
    return load_package(root)


def take(pkg, tmp_path):
    clip = tmp_path / "SC02_g1.mp4"
    clip.write_bytes(b"clip-bytes")
    entry, _ = T.register_take(pkg.root, pkg.header.film_id, "SC02_g1", clip, prompt_text="p", route="ingredients",
                               model="veo-omni-flash", credits=1, known_generations={"SC02_g1"})
    return entry


def decl_of(pkg):
    return next(g for g in pkg.typed["shots"].generations if g.generation_id == "SC02_g1")


def human_pass(sheet, answers=None, fail_group=None):
    for c in sheet["qc"]["checks"]:
        c.update(result="PASS", level=MIN_LEVEL[c["group"]], evidence="x.png", reviewer="human:owner")
        if fail_group == c["group"]:
            c.update(result="FAIL", severity="P1")
    for qid, text in (answers or {}).items():
        group = "narrative" if qid.startswith("REL_ADDRESS") else "spatial"
        next(c for c in sheet["qc"]["checks"] if c["group"] == group).setdefault("answers", {})[qid] = text
    return sheet


def test_question_ids_for_ots(tmp_path):
    pkg = make(tmp_path)
    qs = relation_questions(pkg.typed["preprod"], decl_of(pkg), speakers_of(decl_of(pkg), T.script_dialogue(pkg)))
    assert [q["id"] for q in qs] == IDS
    by = {q["id"]: q for q in qs}
    assert by["REL_ADDRESS:22"]["group"] == "narrative" and "THEO" in by["REL_ADDRESS:22"]["question"]
    assert "near frame-" in by["REL_LISTENER:THEO"]["question"]
    assert "(" in by["REL_BARRIER"]["question"] and "MARA and THEO" in by["REL_BARRIER"]["question"]


def test_required_answers_gate_acceptance(tmp_path):
    pkg = make(tmp_path)
    entry = take(pkg, tmp_path)
    sheet = T.dailies_template(pkg, entry, T.script_dialogue(pkg))
    assert sheet["qc"]["required_answers"] == IDS
    answers = {i: "yes, seen at 2s" for i in IDS}
    partial = {k: v for k, v in answers.items() if k != "REL_LISTENER:THEO"}
    res = T.ingest_review(pkg.root, pkg.header.film_id, human_pass(copy.deepcopy(sheet), partial))
    assert res["status"] == "INCOMPLETE"
    res = T.ingest_review(pkg.root, pkg.header.film_id, human_pass(copy.deepcopy(sheet), answers))
    assert res["status"] == "ACCEPTED"
    res = T.ingest_review(pkg.root, pkg.header.film_id, human_pass(copy.deepcopy(sheet), partial, fail_group="spatial"))
    assert res["status"] == "REJECTED"


def test_blank_answer_and_auto_reviewer_do_not_count(tmp_path):
    pkg = make(tmp_path)
    entry = take(pkg, tmp_path)
    sheet = T.dailies_template(pkg, entry, T.script_dialogue(pkg))
    answers = {i: "ok" for i in IDS}
    answers["REL_GAZE"] = "   "
    assert T.ingest_review(pkg.root, pkg.header.film_id, human_pass(copy.deepcopy(sheet), answers))["status"] == "INCOMPLETE"


def test_contract_off_template_unchanged(tmp_path):
    pkg = make(tmp_path, contract=False)
    entry = take(pkg, tmp_path)
    sheet = T.dailies_template(pkg, entry, T.script_dialogue(pkg))
    assert sheet["qc"]["required_answers"] == []
    assert not any("id" in q for q in sheet["questions"]) and "REL_" not in sheet["instructions"]
    with pytest.raises(ValueError, match="no relation questions"):
        T.supplemental_template(pkg, entry)
    res = T.ingest_review(pkg.root, pkg.header.film_id, human_pass(sheet))
    assert res["status"] == "ACCEPTED"


def test_supplemental_flow(tmp_path):
    pkg = make(tmp_path)
    root, fid = pkg.root, pkg.header.film_id
    entry = take(pkg, tmp_path)
    T.write_dailies(pkg, root)
    sheet_file = T.takes_dir(root) / "dailies" / f"{entry.take_id}.review.json"
    sheet_before = sheet_file.read_bytes()
    main = _load(sheet_file)
    main["qc"]["required_answers"] = []  # a sheet written before the contract carried none
    assert T.ingest_review(root, fid, human_pass(main))["status"] == "ACCEPTED"
    review = T.takes_dir(root) / "reviews" / f"{entry.take_id}.qc.json"
    before = review.read_bytes()
    path = T.supplemental_template(pkg, T.load_log(root, fid).get(entry.take_id))
    assert path.name == "SC02_g1_t1.relations.review.json"
    with pytest.raises(ValueError, match="never overwritten"):
        T.supplemental_template(pkg, entry)
    supp = _load(path)
    assert supp["supplemental"] == "relations" and [q["id"] for q in supp["questions"]] == IDS
    partial = {i: "yes" for i in IDS[:-1]}
    res = T.ingest_review(root, fid, human_pass(copy.deepcopy(supp), partial))
    assert res["status"] == "INCOMPLETE" and any("REL_BARRIER" in r for r in res["reasons"])
    assert T.load_log(root, fid).get(entry.take_id).status == "INCOMPLETE"
    res = T.ingest_review(root, fid, human_pass(copy.deepcopy(supp), {i: "yes" for i in IDS}))
    assert res["status"] == "ACCEPTED"
    assert T.load_log(root, fid).get(entry.take_id).status == "ACCEPTED"
    res = T.ingest_review(root, fid, human_pass(copy.deepcopy(supp), {i: "no" for i in IDS}, "spatial"))
    assert res["status"] == "REJECTED"
    assert review.read_bytes() == before and sheet_file.read_bytes() == sheet_before  # existing sheets untouched
    empty = copy.deepcopy(supp)
    empty["qc"]["required_answers"] = []
    with pytest.raises(ValueError, match="required_answers"):
        T.ingest_review(root, fid, human_pass(empty))


def test_cli_ingest_refuses_sheet_that_drops_package_questions(tmp_path):
    pkg = make(tmp_path)
    root, fid = pkg.root, pkg.header.film_id
    entry = take(pkg, tmp_path)
    sheet = T.dailies_template(pkg, entry, T.script_dialogue(pkg))
    answers = {i: "yes" for i in IDS if i != "REL_GAZE"}
    edited = human_pass(copy.deepcopy(sheet), answers)
    edited["qc"]["required_answers"] = [i for i in IDS if i != "REL_GAZE"]
    with pytest.raises(ValueError, match="drops required relation questions"):
        T.ingest_review(root, fid, edited, pkg=pkg)
    legacy = human_pass(copy.deepcopy(sheet))
    legacy["qc"]["required_answers"] = []  # pre-contract sheet: needs the supplemental review first
    with pytest.raises(ValueError, match="drops required relation questions"):
        T.ingest_review(root, fid, legacy, pkg=pkg)
    full = human_pass(copy.deepcopy(sheet), {i: "yes" for i in IDS})
    assert T.ingest_review(root, fid, full, pkg=pkg)["status"] == "ACCEPTED"
