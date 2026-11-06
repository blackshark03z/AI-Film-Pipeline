"""`plan` stage: Production Package -> video prompts, start-frame still prompts, schematic storyboard, gate3 record.

Generalises what `tools/drama_film03.py` did with module-level constants; here everything comes from the package
(`02_direction`, `03_preprod`, `04_shots`, `script.fountain`). Output layout under `out/`:
prompts/<gid>.txt, stills/char_<NAME>.txt, stills/plate_<look_id>.txt, stills/start_<gid>.txt,
storyboard/ (frames + gate), gate3.json.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from film_pipeline.drama import (CharacterBrief, ContinuityState, GenerationHandoff, StoryboardGate, check_temporal,
                                 compile_scene_prompt, preflight_scene, render_schematic_frame)
from film_pipeline.drama.axis import axis_record
from film_pipeline.drama.comprehension import check_comprehension, lint_script
from film_pipeline.drama.coverage import _SIZE, CoverageShot, SceneUnit, SpokenLine
from film_pipeline.drama.feasibility import check_script
from film_pipeline.production.package import FilmPackage, PackageError
from film_pipeline.production.sections import DirectionSection, PreprodSection, ShotDecl, ShotsSection

_LANGUAGE = {"en": "English", "vi": "Vietnamese"}
START_PREFIX = "Starts on the given frame; same room, people and places. "


class _Plan:
    def __init__(self, pkg: FilmPackage, takes_dir: Path | None, reference_root: Path | None) -> None:
        missing = [k for k in ("direction", "preprod", "shots") if k not in pkg.typed]
        if missing or pkg.script is None:
            raise PackageError(f"plan needs typed sections {missing or ''} and script.fountain")
        self.pkg = pkg
        self.pre: PreprodSection = pkg.typed["preprod"]
        self.shots: ShotsSection = pkg.typed["shots"]
        self.direction: DirectionSection = pkg.typed["direction"]
        self.script = pkg.script
        self.scenes = {s.scene_id: s for s in pkg.script.scenes}
        self.gen_s = float(pkg.header.generation_s)
        self.by_id = {g.generation_id: g for g in self.shots.generations}
        self.takes_dir = takes_dir
        self.reference_root = reference_root or pkg.root / "refs"
        self.language = _LANGUAGE.get(pkg.header.language, pkg.header.language)
        self.video_looks = {n: c.look.model_copy(update={"text": c.video_text})
                            for n, c in self.pre.characters.items()}
        # index of each generation inside its scene (1-based): generation k speaks the k-th line
        seen: dict[str, int] = {}
        self.gen_index: dict[str, int] = {}
        for g in self.shots.generations:
            seen[g.scene_id] = seen.get(g.scene_id, 0) + 1
            self.gen_index[g.generation_id] = seen[g.scene_id]

    # -- helpers ---------------------------------------------------------------------------------------------
    def state(self, name: str) -> ContinuityState:
        return self.pre.states[name]

    @staticmethod
    def cut(full: ContinuityState, visible: list[str]) -> ContinuityState:
        see = set(visible)
        return full.model_copy(update={
            "positions": {c: p for c, p in full.positions.items() if c in see},
            "looks": {c: v for c, v in full.looks.items() if c in see}})

    @staticmethod
    def action_text(decl: ShotDecl) -> str:
        return " ".join(p.description for p in decl.choreography.phases if p.kind == "ACTION")

    def lines_for(self, decl: ShotDecl) -> list[SpokenLine]:
        spoken = [SpokenLine(character=e.character, text=e.text, syllables=e.syllables, line_no=e.line_no)
                  for e in self.scenes[decl.scene_id].elements if e.kind == "dialogue"]
        k = self.gen_index[decl.generation_id]
        return spoken[k - 1:k]

    def unit_for(self, decl: ShotDecl) -> SceneUnit:
        sid, k = decl.scene_id, self.gen_index[decl.generation_id]
        book = self.pre.scenes[sid].axis
        shot_id = f"{sid}_S{k}"
        shot = CoverageShot(
            shot_id=shot_id, coverage=decl.coverage, shot_size=_SIZE[decl.coverage], subject=decl.subject,
            foreground=decl.foreground, start_s=0.0, end_s=self.gen_s, lines=self.lines_for(decl),
            action=self.action_text(decl), axis=axis_record(book, shot_id, decl.visible))
        return SceneUnit(scene_id=sid, duration_s=self.gen_s, shots=[shot], axis_book=book)

    def handoff_for(self, decl: ShotDecl) -> GenerationHandoff | None:
        if decl.previous_generation_id is None:
            return None
        prev = self.by_id[decl.previous_generation_id]
        verified = bool(self.takes_dir and (self.takes_dir / f"{prev.generation_id}.mp4").is_file())
        return GenerationHandoff(
            previous_generation_id=prev.generation_id, previous_action=self.action_text(prev),
            previous_start=self.state(prev.start_state),
            previous_end=self.cut(self.state(prev.end_state), decl.visible),
            end_state_verified=verified)

    def build(self, decl: ShotDecl, gate: StoryboardGate):
        scene = self.pre.scenes[decl.scene_id]
        location = self.pre.locations[scene.location]
        unit = self.unit_for(decl)
        start = self.cut(self.state(decl.start_state), decl.visible)
        cast = [CharacterBrief(name=c, look=self.video_looks[c], voice=self.pre.characters[c].voice)
                for c in start.positions]
        plan = compile_scene_prompt(
            unit, characters=cast, setting=scene.extras, room_tone=location.room_tone, sfx=decl.sfx or None,
            dialogue_language=self.language, start_state=start, location=location.look,
            choreography=decl.choreography)
        report = preflight_scene(
            scene=self.scenes[decl.scene_id], unit=unit, prompt=plan, reference_sets=[],
            reference_root=self.reference_root, storyboard=gate, known_characters=self.script.characters,
            limits=self.pre.preflight, reference_mode="TEXT_ONLY", looks=list(self.video_looks.values()),
            generation_index=self.gen_index[decl.generation_id], handoff=self.handoff_for(decl),
            start_state=start, location=location.look, occupancy=scene.occupancy,
            choreography=decl.choreography)
        return unit, plan, report

    def still_prompt(self, decl: ShotDecl, unit: SceneUnit) -> str:
        """Start-frame image: the shot's first instant, character stills attached."""
        scene = self.pre.scenes[decl.scene_id]
        shot = unit.shots[0]
        start = self.state(decl.start_state)
        shown = [c for c in start.positions if c in shot.axis.visible or shot.coverage == "MASTER"]
        people = "; ".join(f"{c} ({self.pre.characters[c].look.text}) {start.positions[c]}" for c in shown)
        # a prop placed on someone out of frame would summon a stranger
        hidden = [c for c in self.pre.characters if c not in shown]
        props = "; ".join(f"{k.rstrip(':')} {v}" for k, v in start.props.items()
                          if not any(c in v for c in hidden))
        props = f" {props}." if props else ""
        extras = f" {scene.extras.capitalize()}." if scene.extras and shot.coverage == "MASTER" else ""
        alone = "" if len(shown) > 1 else f" Only {shown[0]} in frame."
        location = self.pre.locations[scene.location].look
        return (f"Photoreal film still, 16:9, {self.pre.still_templates.framing[shot.coverage]}: "
                f"{shot.describe(unit.axis_book)}. {location.text}. {people}.{props}{extras}{alone} "
                "Faces and clothes exactly as in the attached character images. Natural, restrained "
                "expressions. No text, no logos.")

    def temporal(self) -> list[Any]:
        order = list(self.pre.scenes)
        first = {g.scene_id: g for g in reversed(self.shots.generations)}  # earliest generation per scene
        last = {g.scene_id: g for g in self.shots.generations}  # latest generation per scene
        return check_temporal(
            [self.pre.scenes[s].story_time for s in order],
            {s: self.state(last[s].end_state) for s in order if s in last},
            {s: self.state(first[s].start_state) for s in order if s in first})


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8", newline="\n")


def plan_package(pkg: FilmPackage, out: str | Path, *, takes_dir: str | Path | None = None,
                 reference_root: str | Path | None = None, storyboard: bool = True,
                 reviewer: str = "Tech Lead (Owner-delegated)") -> dict[str, Any]:
    """Write all plan artefacts under `out`; returns the gate3 record."""
    p = _Plan(pkg, Path(takes_dir) if takes_dir else None, Path(reference_root) if reference_root else None)
    out = Path(out)
    out.mkdir(parents=True, exist_ok=True)
    feas = check_script(p.script, limits=p.pre.feasibility)
    temporal = p.temporal()

    gate = StoryboardGate(out / "storyboard")
    if storyboard:
        for decl in p.shots.generations:
            unit = p.unit_for(decl)
            shot = unit.shots[0]
            rel = f"{decl.generation_id}.png"
            render_schematic_frame(unit, shot, out / "storyboard" / rel, width=640)
            gate.register(unit.scene_id, shot.shot_id, rel)
            gate.review(shot.shot_id, status="APPROVED", reviewer=reviewer)
        gate.save()

    for name, spec in p.pre.characters.items():
        _write(out / "stills" / f"char_{name}.txt",
               p.pre.still_templates.character.format(text=spec.look.text) + "\n")
    for look_id, loc in p.pre.locations.items():
        _write(out / "stills" / f"plate_{look_id}.txt",
               p.pre.still_templates.plate.format(text=loc.look.text) + "\n")

    record: dict[str, Any] = {"feasibility": [i.model_dump() for i in feas.issues],
                              "temporal": [i.model_dump() for i in temporal], "generations": {}}
    for decl in p.shots.generations:
        gid = decl.generation_id
        unit, plan, report = p.build(decl, gate)
        text = START_PREFIX + plan.compiled_text
        _write(out / "prompts" / f"{gid}.txt", text + "\n")
        still = p.still_prompt(decl, unit)
        _write(out / "stills" / f"start_{gid}.txt", still + "\n")
        record["generations"][gid] = {
            "words": len(text.split()), "verdict": report.verdict, "still_words": len(still.split()),
            "issues": [i.model_dump() for i in report.issues]}
    comp = p.direction.comprehension
    order = [g.generation_id for g in p.shots.generations]
    in_frame = {g.generation_id: list(g.visible) for g in p.shots.generations}
    record["comprehension"] = [i.model_dump() for i in (
        lint_script(p.script, comp.intros, comp.facts)
        + check_comprehension(order, in_frame, comp.intros, comp.facts, comp.tags, comp.cards))]
    record["looks"] = {k: v.look.model_dump() for k, v in p.pre.characters.items()}
    record["locations"] = [v.look.model_dump() for v in p.pre.locations.values()]
    record["states"] = {k: v.model_dump() for k, v in p.pre.states.items()}
    _write(out / "gate3.json", json.dumps(record, ensure_ascii=False, indent=2))
    return record
