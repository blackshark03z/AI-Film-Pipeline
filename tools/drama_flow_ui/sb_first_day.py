"""Plan coverage + schematic storyboard for film01 "First Day".

Flow renders 8 s per generation, so each 16 s scene is two generations and
the cut nearest 8.0 s is snapped onto the generation boundary.
"""
import json
import sys
from pathlib import Path

from PIL import Image

sys.path.insert(0, "src")
from film_pipeline.drama import (AxisBook, CoveragePlanner,  # noqa: E402
                                 StoryboardGate, parse_fountain,
                                 render_schematic_frame)
from film_pipeline.drama.coverage import SceneTiming  # noqa: E402

GEN_S = 8.0
ROOT = Path("docs/drama/storyboard_film01")
timing = SceneTiming(duration_s=16.0, max_shots=4, min_shot_s=2.0,
                     syllables_per_second=2.5)   # (*) English words/s
script = parse_fountain(Path("docs/drama/film01_first_day.fountain")
                        .read_text(encoding="utf-8"))


def book_for(scene):
    if "REED" in scene.speakers:
        # REED comes in on DOYLE's side of the counter, facing NORA
        return AxisBook(scene_id=scene.scene_id, axis_pair=["NORA", "REED"],
                        sides={"NORA": "LEFT", "REED": "RIGHT",
                               "DOYLE": "RIGHT"})
    return AxisBook.for_pair(scene.scene_id, "NORA", "DOYLE")


def snap_to_generation(unit):
    cuts = [s.end_s for s in unit.shots[:-1]]
    if not cuts:
        return unit, None
    k = min(range(len(cuts)), key=lambda i: abs(cuts[i] - GEN_S))
    a, b = unit.shots[k], unit.shots[k + 1]
    if GEN_S - a.start_s >= timing.min_shot_s and \
            b.end_s - GEN_S >= timing.min_shot_s:
        shots = list(unit.shots)
        shots[k] = a.model_copy(update={"end_s": GEN_S})
        shots[k + 1] = b.model_copy(update={"start_s": GEN_S})
        unit = unit.model_copy(update={"shots": shots})
    return unit, k


def reveal_scene(unit):
    """SC05: the payoff is DOYLE's freeze, not REED's face. Generation 1 is
    the master with REED's line; generation 2 plays NORA vs DOYLE."""
    from film_pipeline.drama.axis import axis_record
    from film_pipeline.drama.coverage import _SIZE, CoverageShot
    book = AxisBook(scene_id=unit.scene_id, axis_pair=["NORA", "DOYLE"],
                    sides={"NORA": "LEFT", "DOYLE": "RIGHT", "REED": "RIGHT"})
    master, ots = unit.shots[0], unit.shots[1]
    sid = unit.scene_id

    def shot(n, cov, subject, start, end, visible, lines=(), action="",
             fg=""):
        return CoverageShot(shot_id=f"{sid}_S{n}", coverage=cov,
                            shot_size=_SIZE[cov], subject=subject,
                            foreground=fg, start_s=start, end_s=end,
                            lines=list(lines), action=action,
                            axis=axis_record(book, f"{sid}_S{n}", visible))
    shots = [
        shot(1, "MASTER", "", 0.0, 8.0, ["NORA", "REED", "DOYLE"],
             master.lines, master.action),
        shot(2, "REACTION", "DOYLE", 8.0, 10.5, ["DOYLE"],
             action="DOYLE freezes; the handcuffs sink in his hand"),
        shot(3, "OTS", "NORA", 10.5, 13.5, ["NORA", "DOYLE"], ots.lines,
             fg="DOYLE"),
        shot(4, "SINGLE", "DOYLE", 13.5, 16.0, ["DOYLE"],
             action="DOYLE unpins his badge and lays it on the counter"),
    ]
    return unit.model_copy(update={"shots": shots, "axis_book": book})


def plan_unit(scene):
    unit, _ = snap_to_generation(CoveragePlanner(timing).plan(scene, book_for(scene)))
    if "REED" in scene.speakers:
        unit = reveal_scene(unit)
    return unit


def main():
    ROOT.mkdir(parents=True, exist_ok=True)
    gate = StoryboardGate(ROOT)
    plan, frames = {}, []
    for scene in script.scenes:
        unit, k = snap_to_generation(CoveragePlanner(timing).plan(scene,
                                                                  book_for(scene)))
        if "REED" in scene.speakers:
            unit = reveal_scene(unit)
        problems = unit.timing_problems(timing) + unit.axis_problems()
        crosses = [s.shot_id for s in unit.shots
                   if s.start_s < GEN_S < s.end_s]
        plan[scene.scene_id] = {
            "shots": [{"shot_id": s.shot_id, "coverage": s.coverage,
                       "subject": s.subject, "start_s": s.start_s,
                       "end_s": s.end_s, "describe": s.describe(unit.axis_book),
                       "lines": [f"{l.character}: {l.text}" for l in s.lines],
                       "generation": 1 if s.end_s <= GEN_S else 2}
                      for s in unit.shots],
            "problems": problems, "shots_crossing_generation_boundary": crosses}
        for s in unit.shots:
            rel = f"{s.shot_id}.png"
            render_schematic_frame(unit, s, ROOT / rel, width=640)
            gate.register(unit.scene_id, s.shot_id, rel)
            frames.append(Image.open(ROOT / rel))
        print(scene.scene_id, [(s.shot_id, s.coverage, s.subject, s.start_s,
                                s.end_s) for s in unit.shots], problems, crosses)

    (ROOT / "shot_list.json").write_text(json.dumps(plan, ensure_ascii=False,
                                                    indent=2), encoding="utf-8")
    print(gate.save())
    w, h = frames[0].size
    cols = 4
    rows = -(-len(frames) // cols)
    sheet = Image.new("RGB", (w * cols, h * rows), "white")
    for i, f in enumerate(frames):
        sheet.paste(f, ((i % cols) * w, (i // cols) * h))
    sheet.save(ROOT / "contact_sheet.png")
    print(len(frames), "frames")


if __name__ == "__main__":
    main()
