import json
from pathlib import Path

import pytest

from film_pipeline.production.impact import affected_by
from film_pipeline.production.package import load_package

FILM03 = Path(__file__).resolve().parents[1] / "films" / "film03_front_desk"
FILES = ("film.json", "script.fountain", "01_story.json", "02_direction.json", "03_preprod.json", "04_shots.json")


def clone(tmp_path, pre=None, shots=None, extra=None):
    for name in FILES:
        (tmp_path / name).write_text((FILM03 / name).read_text(encoding="utf-8"), encoding="utf-8")
    for name, mutate in (("03_preprod.json", pre), ("04_shots.json", shots)):
        if mutate:
            data = json.loads((tmp_path / name).read_text(encoding="utf-8"))
            mutate(data)
            (tmp_path / name).write_text(json.dumps(data), encoding="utf-8")
    for name, data in (extra or {}).items():
        (tmp_path / name).write_text(json.dumps(data), encoding="utf-8")
    return load_package(tmp_path)


@pytest.fixture(scope="module")
def pkg():
    return load_package(FILM03)


def in_frame(pkg, who):
    return [g.generation_id for g in pkg.typed["shots"].generations
            if who in (*g.visible, g.subject, g.foreground)]


def test_film03_pins_are_current():
    assert load_package(FILM03).issues == []


def test_character_costume_impact_is_exactly_the_shots_with_that_character(pkg):
    nora = in_frame(pkg, "NORA")
    kessler = in_frame(pkg, "KESSLER")
    assert 0 < len(nora) < 16 and set(nora) != set(kessler)
    impact = affected_by(pkg, "NORA_costume")
    assert impact.shots == nora
    assert not set(impact.shots) & {g for g in in_frame(pkg, "ORTIZ") if "NORA" not in
                                    next(x for x in pkg.typed["shots"].generations if x.generation_id == g).visible}
    assert impact.stills[0] == "char_NORA" and impact.stills[1:] == [f"start_{g}" for g in nora]
    assert impact.kind == "costume" and impact.version == 1


def test_takes_include_the_handoff_cascade_but_shots_do_not(pkg):
    impact = affected_by(pkg, "NORA_hair")
    gens = {g.generation_id: g for g in pkg.typed["shots"].generations}
    extra = [g for g in impact.takes if g not in impact.shots]
    assert extra, "film03 has Nora-free shots that hand off from a Nora shot"
    for gid in extra:
        assert gens[gid].previous_generation_id in impact.takes
        assert "NORA" not in (*gens[gid].visible, gens[gid].subject, gens[gid].foreground)
    # film03's lobby is one continuous chain from SC01_g1, so a Nora design touches every take
    assert impact.takes == [g.generation_id for g in pkg.typed["shots"].generations]
    # a change confined to the second chain leaves the first one untouched
    briefing = affected_by(pkg, "loc_briefing_morning")
    untouched = set(gens) - set(briefing.takes)
    assert untouched == {f"SC0{n}_g{k}" for n in range(1, 7) for k in (1, 2)}
    assert all(gens[g].previous_generation_id not in briefing.takes for g in untouched)


def test_location_and_prop_impact(pkg):
    lobby = affected_by(pkg, "loc_lobby_morning")
    assert lobby.shots == [f"SC0{n}_g{k}" for n in range(1, 7) for k in (1, 2)]
    assert lobby.stills[0] == "plate_lobby_morning"
    briefing = affected_by(pkg, "loc_briefing_morning")
    assert briefing.shots == ["SC07_g1", "SC07_g2", "SC08_g1", "SC08_g2"]
    letter = affected_by(pkg, "prop_letter")
    assert letter.shots == lobby.shots and letter.stills == [f"start_{g}" for g in letter.shots]  # no char still


def test_unknown_design_and_missing_stage(pkg, tmp_path):
    with pytest.raises(ValueError, match="unknown design 'NOPE'"):
        affected_by(pkg, "NOPE")
    bare = load_package(_empty(tmp_path))
    with pytest.raises(ValueError, match="needs a valid 03_preprod.json"):
        affected_by(bare, "x")


def _empty(tmp_path):
    (tmp_path / "film.json").write_text((FILM03 / "film.json").read_text(encoding="utf-8"), encoding="utf-8")
    (tmp_path / "script.fountain").write_text("", encoding="utf-8")
    return tmp_path


def test_version_bump_makes_exactly_the_dependent_pins_stale(tmp_path):
    def bump(pre):
        pre["designs"]["NORA_costume"]["version"] = 2
    bumped = clone(tmp_path, pre=bump)
    stale = sorted(i.split(":")[1].strip() for i in bumped.issues if "pinned NORA_costume@1" in i)
    original = load_package(FILM03)
    assert stale == sorted(in_frame(original, "NORA"))
    assert len(bumped.issues) == len(stale)  # nothing else went stale
    assert all("current is NORA_costume@2" in i for i in bumped.issues)
    # the impact list names the same shots, so the report and the pins agree
    assert affected_by(bumped, "NORA_costume").shots == in_frame(bumped, "NORA")


def test_repinning_clears_the_issue(tmp_path):
    def bump(pre):
        pre["designs"]["NORA_costume"]["version"] = 2

    def repin(shots):
        for g in shots["generations"]:
            g["design_refs"] = [r.replace("NORA_costume@1", "NORA_costume@2") for r in g["design_refs"]]
    assert clone(tmp_path, pre=bump, shots=repin).issues == []


def test_missing_duplicate_and_unknown_pins(tmp_path):
    def unpin(shots):
        shots["generations"][0]["design_refs"] = []
    assert any("design NORA_look is not pinned (pin NORA_look@1)" in i for i in clone(tmp_path, shots=unpin).issues)

    def dup(shots):
        shots["generations"][0]["design_refs"].append("NORA_look@1")
    assert any("pinned twice" in i for i in clone(tmp_path, shots=dup).issues)

    def ghost(shots):
        shots["generations"][0]["design_refs"].append("GHOST@1")
    assert any("pins unknown design 'GHOST'" in i for i in clone(tmp_path, shots=ghost).issues)


def test_bad_pin_format_and_design_entry_rules(tmp_path):
    def bad_pin(shots):
        shots["generations"][0]["design_refs"].append("NORA_look@0")
    assert any("04_shots.json" in i for i in clone(tmp_path, shots=bad_pin).issues)

    def wrong_owner(pre):
        pre["designs"]["NORA_costume"]["owner"] = "lobby_morning"
    assert any("needs a character owner" in i for i in clone(tmp_path, pre=wrong_owner).issues)

    def no_prop(pre):
        pre["designs"]["prop_letter"]["prop"] = ""
    assert any("prop needs the prop name" in i for i in clone(tmp_path, pre=no_prop).issues)

    def version_zero(pre):
        pre["designs"]["NORA_look"]["version"] = 0
    assert any("03_preprod.json" in i for i in clone(tmp_path, pre=version_zero).issues)


def test_packages_without_designs_are_not_forced_to_pin(tmp_path):
    def strip(pre):
        pre.pop("designs")

    def unpin(shots):
        for g in shots["generations"]:
            g.pop("design_refs")
    assert clone(tmp_path, pre=strip, shots=unpin).issues == []


def test_edit_post_items_that_reference_affected_generations(tmp_path):
    edit = {"clips": [{"order": 1, "generation_id": "SC01_g1"}, {"order": 2, "generation_id": "SC05_g1"}]}
    post = {"subtitles": [{"shot_id": "SC02_g2", "text": "x"}], "cards": [{"card_id": "OPEN_card"}]}
    pkg = clone(tmp_path, extra={"05_edit.json": edit, "06_post.json": post})
    impact = affected_by(pkg, "NORA_costume")
    assert impact.edit_items == ["edit:clips[0]", "edit:clips[1]"]  # SC05_g1 is a handoff dependent of a Nora shot
    assert impact.post_items == ["post:subtitles[0]"]
    ortiz_only = affected_by(pkg, "prop_desk_phone")
    assert ortiz_only.post_items == ["post:subtitles[0]"]
    assert affected_by(pkg, "loc_briefing_morning").edit_items == []


def test_cli_impact():
    import subprocess
    import sys
    tool = Path(__file__).resolve().parents[1] / "tools" / "film.py"
    ok = subprocess.run([sys.executable, str(tool), "impact", "--film", str(FILM03), "--design", "loc_briefing_morning"],
                        capture_output=True, text=True, encoding="utf-8")
    assert ok.returncode == 0 and json.loads(ok.stdout)["shots"] == ["SC07_g1", "SC07_g2", "SC08_g1", "SC08_g2"]
    bad = subprocess.run([sys.executable, str(tool), "impact", "--film", str(FILM03), "--design", "nope"],
                         capture_output=True, text=True, encoding="utf-8")
    assert bad.returncode == 2 and "unknown design" in bad.stdout
