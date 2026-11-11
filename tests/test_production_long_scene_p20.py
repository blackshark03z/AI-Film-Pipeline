from pathlib import Path

from film_pipeline.drama.feasibility import check_script, FeasibilityLimits
from film_pipeline.drama.script import parse_fountain
from film_pipeline.production.package import load_package
from film_pipeline.production.plan import plan_package
from test_production_generate import film


def test_long_scene_budget_is_local_and_default_short_scene_guard_remains():
    script = parse_fountain("INT. ROOM - DAY\n\nRUTH\n" + "hello " * 40 + "\n")
    assert any(i.rule == "DIALOGUE_TOO_LONG" for i in check_script(script).issues)
    sid = script.scenes[0].scene_id
    result = check_script(script, scene_limits={sid: FeasibilityLimits(scene_duration_s=60, max_dialogue_syllables=140)})
    assert not any(i.rule in {"DIALOGUE_TOO_LONG", "NO_ROOM_FOR_REACTION"} for i in result.issues)
    assert any(i.rule == "DIALOGUE_TOO_LONG" for i in check_script(script).issues)


def test_production_plan_allocates_long_scene_from_its_generation_durations(tmp_path):
    pkg = film(tmp_path, approve=False)
    shots = pkg.typed["shots"]
    first_scene = shots.generations[0].scene_id
    scene_generations = [g for g in shots.generations if g.scene_id == first_scene]
    assert len(scene_generations) >= 2
    # Change two existing dialogue lines without shifting their script line numbers.
    source = (pkg.root / "script.fountain").read_text(encoding="utf-8")
    lines = source.splitlines()
    for g in scene_generations[:2]:
        for line_no in g.dialogue:
            # The parser's dialogue line_no identifies the speaker cue; speech is on the following line.
            lines[line_no] = "hello " * 20
    (pkg.root / "script.fountain").write_text("\n".join(lines) + "\n", encoding="utf-8")
    import json
    path = pkg.root / "04_shots.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    for g in data["generations"]:
        if g["scene_id"] == first_scene:
            g["duration_s"] = 15
    path.write_text(json.dumps(data), encoding="utf-8")
    pkg = load_package(pkg.root)
    assert any(i.scene_id == first_scene and i.rule == "DIALOGUE_TOO_LONG" for i in check_script(pkg.script).issues)
    result = plan_package(pkg, pkg.root / "media/plan", storyboard=False)
    assert not any(i["scene_id"] == first_scene and i["rule"] in {"DIALOGUE_TOO_LONG", "NO_ROOM_FOR_REACTION"}
                   for i in result.record["feasibility"])
