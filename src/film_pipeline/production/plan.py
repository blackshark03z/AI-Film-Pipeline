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

from film_pipeline.drama import (CharacterBrief, ContinuityState, GenerationHandoff, StoryboardGate,
                                 compile_scene_prompt, preflight_scene, render_schematic_frame)
from film_pipeline.drama.axis import axis_record
from film_pipeline.drama.preflight import PreflightIssue
from film_pipeline.drama.prompt import apply_handles
from film_pipeline.drama.comprehension import check_comprehension, lint_script
from film_pipeline.drama.coverage import _SIZE, CoverageShot, SceneUnit, SpokenLine
from film_pipeline.drama.feasibility import check_script
from film_pipeline.production.camera import camera_issues
from film_pipeline.production.continuity import continuity_issues, temporal_issues
from film_pipeline.production.evidence import end_state_verified, load_attestations
from film_pipeline.production.package import FilmPackage, PackageError
from film_pipeline.production.sections import DirectionSection, PreprodSection, ShotDecl, ShotsSection, shot_seconds
from film_pipeline.production.set_layout import layout_issues, render_floor_plan

_LANGUAGE = {"en": "English", "vi": "Vietnamese"}
SUPPORTED_ASPECT = "16:9"  # prompt compiler and schematic renderer are landscape-only
START_PREFIX = "Starts on the given frame; same room, people and places. "
START_FRAME_PREFIX = "The given image is the first frame. "  # prompt_style "start_frame" (P13-04)
END_FRAME_PREFIX = "The given images are the first and last frames. "  # start_frame style + ShotDecl.end_frame (P13-05)
# the emitted prompt = start prefix + the compiler's sections in this order (drama.prompt.SECTION_ORDER)
BUDGET_SECTIONS = ("prefix", "characters", "setting", "continuity", "shots", "performance", "dialogue", "sound", "prohibitions")
# plain names for the report: characters = cast and locked looks, continuity = start-state list, shots = shot + timing/action
BUDGET_LABELS = {"prefix": "start prefix", "characters": "cast/looks", "setting": "setting", "continuity": "start state",
                 "shots": "shot timing/action", "performance": "performance", "dialogue": "dialogue", "sound": "sound",
                 "prohibitions": "fixed tail"}

# words that leave the stopping point of a mid-travel motion to the model
VAGUE_POSITION_WORDS = ("halfway", "half way", "half-closed", "middle", "upper half", "lower half", "partway",
                        "part way", "a third")


def word_budget(sections: dict[str, str], prefix: str = START_PREFIX) -> dict[str, int]:
    """Words of the emitted prompt per section (zeros left out); they add up to the prompt's word count."""
    counts = {"prefix": len(prefix.split()), **{k: len(v.split()) for k, v in sections.items()}}
    return {k: counts[k] for k in BUDGET_SECTIONS if counts.get(k)}


def top_sections(sections: dict[str, int], n: int = 3) -> str:
    ranked = sorted(sections.items(), key=lambda kv: (-kv[1], BUDGET_SECTIONS.index(kv[0])))[:n]
    return ", ".join(f"{BUDGET_LABELS[k]} {v}" for k, v in ranked)


class _Plan:
    def __init__(self, pkg: FilmPackage, takes_dir: Path | None, reference_root: Path | None,
                 attestations: Path | None = None, verified_handoffs: frozenset[str] = frozenset()) -> None:
        missing = [k for k in ("direction", "preprod", "shots") if k not in pkg.typed]
        if missing or pkg.script is None:
            raise PackageError(f"plan needs typed sections {missing or ''} and script.fountain")
        if pkg.header.aspect != SUPPORTED_ASPECT:
            raise PackageError(f"plan supports aspect {SUPPORTED_ASPECT} only, film.json has {pkg.header.aspect!r}")
        self.pkg = pkg
        self.pre: PreprodSection = pkg.typed["preprod"]
        self.shots: ShotsSection = pkg.typed["shots"]
        self.direction: DirectionSection = pkg.typed["direction"]
        self.script = pkg.script
        self.scenes = {s.scene_id: s for s in pkg.script.scenes}
        absent = sorted({g.scene_id for g in self.shots.generations} - set(self.scenes))
        if absent:
            raise PackageError(f"04_shots.json references scenes missing from script.fountain: {absent}")
        self.gen_s = float(pkg.header.generation_s)
        self.by_id = {g.generation_id: g for g in self.shots.generations}
        self.budget: dict[str, dict[str, int]] = {}  # generation_id -> words per section of the emitted prompt
        self.takes_dir = takes_dir
        self.verified_handoffs = verified_handoffs  # generations whose accepted take verifies their end state
        self.attestations = load_attestations(attestations if attestations is not None
                                              else pkg.root / "handoff_attestations.json")
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
        """Dialogue named by `decl.dialogue` (script line numbers), in the order listed."""
        by_no = {e.line_no: e for e in self.scenes[decl.scene_id].elements if e.kind == "dialogue"}
        return [SpokenLine(character=by_no[n].character, text=by_no[n].text, syllables=by_no[n].syllables,
                           line_no=n) for n in decl.dialogue if n in by_no]

    def unit_for(self, decl: ShotDecl) -> SceneUnit:
        sid, k = decl.scene_id, self.gen_index[decl.generation_id]
        book = self.pre.scenes[sid].axis
        shot_id = f"{sid}_S{k}"
        seconds = shot_seconds(decl, self.pkg.header)
        shot = CoverageShot(
            shot_id=shot_id, coverage=decl.coverage, shot_size=_SIZE[decl.coverage], subject=decl.subject,
            foreground=decl.foreground, start_s=0.0, end_s=seconds, lines=self.lines_for(decl),
            action=self.action_text(decl), axis=axis_record(book, shot_id, decl.visible))
        return SceneUnit(scene_id=sid, duration_s=seconds, shots=[shot], axis_book=book)

    def handoff_for(self, decl: ShotDecl) -> GenerationHandoff | None:
        if decl.previous_generation_id is None:
            return None
        prev = self.by_id[decl.previous_generation_id]
        verified = (prev.generation_id in self.verified_handoffs
                    or end_state_verified(self.takes_dir, prev.generation_id, decl.generation_id, self.attestations))
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
        cast = [CharacterBrief(name=c, look=self.video_looks[c], voice=self.pre.characters[c].voice,
                               handle=self.pre.characters[c].handle) for c in start.positions]
        plan = compile_scene_prompt(
            unit, characters=cast, setting=scene.extras, room_tone=location.room_tone, sfx=decl.sfx or None,
            dialogue_language=self.language, start_state=start,
            end_state=(self.cut(self.state(decl.end_state), decl.visible)
                       if self.pre.preflight.end_state_in_prompt else None), location=location.look,
            choreography=decl.choreography, style=self.pre.preflight.prompt_style,
            handles={n: c.handle for n, c in self.pre.characters.items() if c.handle})
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
        loc_spec = self.pre.locations[scene.location]
        location = loc_spec.look
        view = (f" {loc_spec.layout.view_text(decl.camera_position)}"
                if decl.camera_position and loc_spec.layout is not None else "")
        # film04 SC01_g1: the still showed MARA seated while the shot says she stands, hand on the cord
        setup = next((p.description for p in decl.choreography.phases if p.kind == "SETUP"), "")
        pose = f" First instant: {setup}." if setup and self.pre.still_templates.pose else ""
        return (f"Photoreal film still, 16:9, {self.pre.still_templates.framing[shot.coverage]}: "
                f"{shot.describe(unit.axis_book)}. {location.text}.{view} {people}.{props}{extras}{alone}{pose} "
                "Faces and clothes exactly as in the attached character images. Natural, restrained "
                "expressions. No text, no logos.")

    def end_clauses(self, decl: ShotDecl) -> list[str]:
        """What the end state changes from the start state (people in frame only)."""
        start = self.cut(self.state(decl.start_state), decl.visible)
        end = self.cut(self.state(decl.end_state), decl.visible)
        return end.change_clauses(start)

    def end_still_prompt(self, decl: ShotDecl) -> str:
        """End-frame image: an edit of the start image (Google's editing guidance: short, ends with 'keep the rest').
        Character names become their handles, as in the start-frame prompt."""
        handles = {n: c.handle for n, c in self.pre.characters.items() if c.handle}
        change = apply_handles("Change only this: " + "; ".join(self.end_clauses(decl)), handles)
        # the end frame is the last phase's pose too: an edit naming only the prop kept her hands where the start had
        # them (film04 SC01_g1 v4: hands up at the raised shutter, shutter at the middle)
        phases = decl.choreography.phases if decl.choreography else []
        last = decl.end_pose.strip() or (phases[-1].description.strip() if phases else "")
        pose = (" " + apply_handles(f"Pose at the end of the shot: {last.rstrip('.')}.", handles)) if last else ""
        return ("Edit the given image, the first frame of this shot. "
                f"{change}.{pose} Keep everything else the same: framing, people, faces, clothes, light.")

    def motion_target_issues(self, decl: ShotDecl) -> list[PreflightIssue]:
        """Mid-travel stops must name a real set object (STOP_TARGET) and no text may describe the stop vaguely
        (TARGET_CONFLICT); the model otherwise picks its own stopping point (film04 SC01_g1 t9/t10)."""
        stops = [p for p in decl.choreography.phases if p.kind == "ACTION" and p.stops_at]
        if not stops:
            return []
        out: list[PreflightIssue] = []

        def add(check: str, detail: str) -> None:
            out.append(PreflightIssue(check=check, severity="BLOCK", detail=detail))

        layout = self.pre.locations[self.pre.scenes[decl.scene_id].location].layout
        objects = {o.id: o for o in layout.objects} if layout is not None else {}
        for phase in stops:
            obj = objects.get(phase.stops_at)
            if obj is None:
                add("STOP_TARGET", f"stops_at {phase.stops_at!r} is not an object of the location layout")
            elif obj.label.lower() not in phase.description.lower():
                add("STOP_TARGET", f"the phase description must name the stop object {obj.label!r}")
        texts = {"ACTION phase": " ".join(p.description for p in stops), "end_pose": decl.end_pose,
                 "end state change": " ".join(self.end_clauses(decl))}
        for where, text in texts.items():
            vague = [w for w in VAGUE_POSITION_WORDS if w in text.lower()]
            if vague:
                add("TARGET_CONFLICT", f"{where} places the stop vaguely ({', '.join(vague)}); name the set object instead")
        if decl.end_frame:
            labels = [objects[p.stops_at].label for p in stops if p.stops_at in objects]
            if labels and not any(label.lower() in decl.end_pose.lower() for label in labels):
                add("TARGET_CONFLICT", f"end_pose must mention the stop object ({', '.join(labels)})")
        return out

    def dialogue_problems(self) -> list[str]:
        """Each scripted dialogue line is spoken by exactly one generation of its scene; references must exist."""
        out: list[str] = []
        used: dict[tuple[str, int], str] = {}
        for g in self.shots.generations:
            scripted = {e.line_no for e in self.scenes[g.scene_id].elements if e.kind == "dialogue"}
            for n in g.dialogue:
                if n not in scripted:
                    out.append(f"DIALOGUE_UNKNOWN {g.generation_id}: line {n} is not a dialogue line of {g.scene_id}")
                elif (g.scene_id, n) in used:
                    out.append(f"DIALOGUE_DUPLICATE {g.generation_id}: line {n} already spoken in {used[(g.scene_id, n)]}")
                else:
                    used[(g.scene_id, n)] = g.generation_id
        for sid, scene in self.scenes.items():
            for e in scene.elements:
                if e.kind == "dialogue" and (sid, e.line_no) not in used:
                    out.append(f"DIALOGUE_UNASSIGNED {sid}: line {e.line_no} ({e.character}) is spoken in no generation")
        return out

    def overlong_problems(self, record: dict[str, Any]) -> list[str]:
        """Limit applies to the text actually written (start prefix included); exceptions must carry a reason."""
        limit = self.pre.preflight.max_prompt_words
        return [f"PROMPT_TOO_LONG {gid}: {v['words']} words > {limit} (emitted text; biggest: "
                f"{top_sections(self.budget.get(gid, {}))}); add a reason to "
                "03_preprod.json accepted_overlong or shorten the shot"
                for gid, v in record["generations"].items()
                if v["words"] > limit and gid not in self.pre.accepted_overlong]

    def temporal(self) -> list[Any]:
        return temporal_issues(self.pre, self.shots)

    def camera(self) -> list[Any]:
        return camera_issues(self.pre, self.shots)

    def layout(self) -> list[Any]:
        return layout_issues(self.pre, self.shots)

    def continuity(self) -> list[Any]:
        return continuity_issues(self.pre, self.shots, include_temporal=False)


def _write(path: Path, text: str, root: Path) -> None:
    if not path.resolve().is_relative_to(root.resolve()):
        raise PackageError(f"refusing to write outside the output directory: {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8", newline="\n")


class PlanResult:
    """`record` = the gate3 json; `problems` = every BLOCK found (empty = the plan is clean)."""

    def __init__(self, record: dict[str, Any], problems: list[str]) -> None:
        self.record, self.problems = record, problems

    @property
    def ok(self) -> bool:
        return not self.problems


def plan_package(pkg: FilmPackage, out: str | Path, *, takes_dir: str | Path | None = None,
                 reference_root: str | Path | None = None, storyboard: bool = True,
                 approve_storyboard: str | None = None, attestations: str | Path | None = None,
                 verified_handoffs: frozenset[str] = frozenset()) -> PlanResult:
    """Write all plan artefacts under `out`.

    Storyboard frames are rendered and registered PENDING. They count as reviewed only when the caller passes
    `approve_storyboard=<reviewer name>` — the plan never invents an approval.
    """
    p = _Plan(pkg, Path(takes_dir) if takes_dir else None, Path(reference_root) if reference_root else None,
              Path(attestations) if attestations else None, verified_handoffs)
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
            if approve_storyboard:
                from film_pipeline.production.rehearsal import refuse_bot
                refuse_bot(Path(pkg.root), approve_storyboard)
                gate.review(shot.shot_id, status="APPROVED", reviewer=approve_storyboard)
        gate.save()

    for name, spec in p.pre.characters.items():
        _write(out / "stills" / f"char_{name}.txt",
               p.pre.still_templates.character.format(text=spec.look.text) + "\n", out)
    for look_id, loc in p.pre.locations.items():
        _write(out / "stills" / f"plate_{look_id}.txt",
               p.pre.still_templates.plate.format(text=loc.look.text) + "\n", out)
        if loc.layout is not None:
            for cam in loc.layout.cameras:
                _write(out / "stills" / f"plate_{look_id}_{cam.id}.txt",
                       p.pre.still_templates.plate.format(
                           text=" ".join(t for t in (f"{loc.look.text}.", loc.layout.view_text(cam.id),
                                                     loc.layout.unseen_text(cam.id)) if t).rstrip(".")) + "\n", out)
            if storyboard and loc.layout.drawable():
                render_floor_plan(loc.layout, loc.look.location, out / "layout" / f"{look_id}.png")

    record: dict[str, Any] = {"feasibility": [i.model_dump() for i in feas.issues],
                              "temporal": [i.model_dump() for i in temporal], "generations": {}}
    continuity = p.continuity()
    if continuity:  # only recorded when there is something to say, so a clean film keeps its golden gate3.json
        record["continuity"] = [i.model_dump() for i in continuity]
    camera = p.camera()
    if camera:  # likewise: a film with no camera findings keeps its golden gate3.json
        record["camera"] = [i.model_dump() for i in camera]
    layout = p.layout()
    if layout:  # likewise: only recorded when there are findings
        record["layout"] = [i.model_dump() for i in layout]
    for decl in p.shots.generations:
        gid = decl.generation_id
        unit, plan, report = p.build(decl, gate)
        prefix = START_FRAME_PREFIX if p.pre.preflight.prompt_style == "start_frame" else START_PREFIX
        if decl.end_frame and p.pre.preflight.prompt_style == "start_frame":
            prefix = END_FRAME_PREFIX
        text = prefix + plan.compiled_text
        p.budget[gid] = word_budget(plan.sections, prefix)
        _write(out / "prompts" / f"{gid}.txt", text + "\n", out)
        still = p.still_prompt(decl, unit)
        _write(out / "stills" / f"start_{gid}.txt", still + "\n", out)
        issues = list(report.issues)
        issues += p.motion_target_issues(decl)
        end_words: int | None = None
        if decl.end_frame:
            if p.end_clauses(decl):
                end_still = p.end_still_prompt(decl)
                _write(out / "stills" / f"end_{gid}.txt", end_still + "\n", out)
                end_words = len(end_still.split())
            else:
                issues.append(PreflightIssue(check="END_FRAME", severity="BLOCK",
                                             detail="end_frame set but the end state changes nothing"))
        record["generations"][gid] = {
            "words": len(text.split()), "verdict": "BLOCKED" if any(i.severity == "BLOCK" for i in issues) else "PASS",
            "still_words": len(still.split()), "issues": [i.model_dump() for i in issues]}
        if end_words is not None:  # only for end_frame shots, so other films keep their golden gate3.json
            record["generations"][gid]["end_still_words"] = end_words
    comp = p.direction.comprehension
    order = [g.generation_id for g in p.shots.generations]
    in_frame = {g.generation_id: list(g.visible) for g in p.shots.generations}
    record["comprehension"] = [i.model_dump() for i in (
        lint_script(p.script, comp.intros, comp.facts)
        + check_comprehension(order, in_frame, comp.intros, comp.facts, comp.tags, comp.cards))]
    record["looks"] = {k: v.look.model_dump() for k, v in p.pre.characters.items()}
    record["locations"] = [v.look.model_dump() for v in p.pre.locations.values()]
    record["states"] = {k: v.model_dump() for k, v in p.pre.states.items()}
    _write(out / "gate3.json", json.dumps(record, ensure_ascii=False, indent=2), out)
    problems = [f"{k.upper()} {i['check']}: {i['detail']}" for k in ("feasibility", "temporal", "continuity", "camera", "layout", "comprehension")
                for i in record.get(k, []) if i["severity"] == "BLOCK"]
    problems += [f"{g} preflight {v['verdict']}" for g, v in record["generations"].items() if v["verdict"] != "PASS"]
    problems += p.dialogue_problems() + p.overlong_problems(record)
    if not p.shots.generations:
        problems.append("no generations in 04_shots.json")
    from film_pipeline.production.gate_checks import PLAN_META, plan_inputs_sha
    # sidecar (not part of gate3.json, which is pinned byte-for-byte by the film03 golden test): gate 3 reads it to
    # tell a plan that still matches its stage files from a stale one
    limit = p.pre.preflight.max_prompt_words
    budget = {gid: {"words": record["generations"][gid]["words"], "limit": limit, "sections": p.budget[gid]}
              for gid in record["generations"]}
    _write(out / PLAN_META, json.dumps({"planned_from": plan_inputs_sha(pkg.root), "problems": problems,
                                        "word_budget": budget}, ensure_ascii=False, indent=2), out)
    return PlanResult(record, problems)
