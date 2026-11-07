"""Camera & lighting plan (cinematography): per-scene lighting, per-shot camera setup, and the rules between them.

Declared in the package:

* `03_preprod.scenes.<id>.lighting` -> `LightingPlan`  (key direction / quality / colour temperature, motivation, practicals)
* `04_shots.generations[].camera`   -> `CameraSetup`   (size, angle, height, movement, lens intent, composition note,
                                                         camera side against the axis book)

Rules (`camera_issues`):

* all-or-nothing: once any shot declares a camera (or any scene a lighting plan) every shot (scene) must, so a half-planned
  film cannot pass as a planned one; a film that declares neither is not forced (older packages keep working)
* ``CAMERA_AXIS_CROSS``  a REVERSE camera side crosses the line of action established by the scene's `AxisBook`;
                         it needs a `crossing_note` that motivates the move (movement across the line, a neutral shot)
* ``CAMERA_SIZE_RUN``    three identical sizes in a row inside one scene is a BLOCK, across scenes a WARN, unless every
                         repeat declares `declared_repeat` (e.g. a deliberate shot / reverse-shot rhythm)
* ``CAMERA_SIZE_COVERAGE`` the size must fit the coverage type (a MASTER is not a CLOSE); one step off is a WARN
* ``CAMERA_ACTION_LEGIBLE`` a WIDE shot with ONE person in frame whose ACTION/CONSEQUENCE/HOLD phases act on one of its own
                         props (``prop_*`` design refs), or any WIDE shot that reads a clock time, cannot be read by a viewer at that size (film04 SC01_g1: MARA a
                         tiny figure, shutter and clock unreadable): BLOCK unless `wide_reason` says why wide is right
* ``CAMERA_LENS_SIZE``   lens intent against size (tele compression on a wide, a wide-angle lens on a close) is a WARN
* ``LIGHT_JUMP``         the key light of a location changes between scenes of the same time of day: WARN

Which fields reach the video/still prompt: only the shot *size*, and it is derived from the coverage type by
`drama.coverage` (MASTER=WIDE, TWO_SHOT=MEDIUM, OTS=MEDIUM_CLOSE, SINGLE=CLOSE). Everything else here is planning and
review data - it is checked, reported (`film.py camera`) and recorded in `gate3.json`, but is *not* compiled into a prompt,
because the current route (Flow text-to-video, one start frame) has no controllable lens, rig or light. `PROMPT_FIELDS`
names the compiled fields and `prompt_hint` renders the optional text a route that supports it may append.
"""
from __future__ import annotations

import re
from typing import Any, Literal

from pydantic import Field, model_validator

from film_pipeline.core import ContractModel
from film_pipeline.drama.scene_bible import RuleIssue

PROMPT_FIELDS = ("size",)  # the only camera field that reaches a prompt today (via the coverage type)

Size = Literal["EXTREME_WIDE", "WIDE", "MEDIUM", "MEDIUM_CLOSE", "CLOSE", "INSERT"]
Angle = Literal["EYE_LEVEL", "HIGH", "LOW", "DUTCH", "OVERHEAD"]
Height = Literal["LOW", "WAIST", "CHEST", "EYE", "HIGH"]
Movement = Literal["STATIC", "PAN", "TILT", "PUSH_IN", "PULL_OUT", "TRACK", "HANDHELD", "CRANE"]
LensIntent = Literal["WIDE_ESTABLISH", "NORMAL", "TELE_COMPRESS", "SHALLOW_ISOLATE"]
CameraSide = Literal["ESTABLISHED", "REVERSE"]
KeyDirection = Literal["FRONT", "FRONT_LEFT", "FRONT_RIGHT", "SIDE_LEFT", "SIDE_RIGHT", "BACK", "TOP"]
PracticalKind = Literal["WINDOW", "LAMP", "OVERHEAD", "SCREEN", "FIRE", "STREET", "OTHER"]

_SIZE_ORDER = ["EXTREME_WIDE", "WIDE", "MEDIUM", "MEDIUM_CLOSE", "CLOSE", "INSERT"]
_COVERAGE_SIZE = {"MASTER": "WIDE", "TWO_SHOT": "MEDIUM", "OTS": "MEDIUM_CLOSE", "SINGLE": "CLOSE",
                  "REACTION": "MEDIUM_CLOSE"}
_WIDE_SIZES, _TIGHT_SIZES = {"EXTREME_WIDE", "WIDE"}, {"CLOSE", "INSERT"}
_CLOCK_TIME = re.compile(r"\b\d{1,2}:\d{2}\b")


class Practical(ContractModel):
    kind: PracticalKind
    note: str = Field(min_length=1)  # "tall window on the left", "desk lamp, warm"


class LightingPlan(ContractModel):
    key_direction: KeyDirection
    quality: Literal["HARD", "SOFT"]
    colour_temp_k: int = Field(ge=1500, le=10000)
    contrast: Literal["LOW", "MEDIUM", "HIGH"] = "MEDIUM"
    motivation: str = Field(min_length=1)  # where the key light comes from in the story world
    practicals: list[Practical] = Field(default_factory=list)


class CameraSetup(ContractModel):
    size: Size
    angle: Angle = "EYE_LEVEL"
    height: Height = "EYE"
    movement: Movement = "STATIC"
    lens_intent: LensIntent = "NORMAL"
    lens_mm: int | None = Field(default=None, ge=8, le=300)
    composition: str = ""  # "NORA frame-left, lower third; desk fills the right"
    side: CameraSide = "ESTABLISHED"
    crossing_note: str = ""
    declared_repeat: str = ""  # why the same size again is deliberate
    wide_reason: str = ""  # why a prop / clock beat is deliberately played wide

    @model_validator(mode="after")
    def _crossing_is_motivated(self) -> "CameraSetup":
        if self.side == "REVERSE" and not self.crossing_note.strip():
            raise ValueError("camera side REVERSE crosses the line of action and needs a crossing_note")
        return self

    def prompt_hint(self) -> str:
        """Optional prompt text for a route that can take it (not used by the Flow route)."""
        parts = [self.size.replace("_", " ").lower() + " shot"]
        if self.angle != "EYE_LEVEL":
            parts.append(self.angle.replace("_", " ").lower() + " angle")
        if self.movement != "STATIC":
            parts.append(self.movement.replace("_", " ").lower())
        return ", ".join(parts)


def _issue(out: list[RuleIssue], check: str, severity: str, detail: str) -> None:
    out.append(RuleIssue(check=check, severity=severity, detail=detail))  # type: ignore[arg-type]


def _rank(size: str) -> int:
    return _SIZE_ORDER.index(size)


def _completeness(pre: Any, shots: Any, out: list[RuleIssue]) -> None:
    declared = [g.generation_id for g in shots.generations if g.camera is not None]
    if declared:
        missing = [g.generation_id for g in shots.generations if g.camera is None]
        if missing:
            _issue(out, "CAMERA_MISSING", "BLOCK", f"camera plan is declared but {', '.join(missing)} have none")
    lit = [s for s, spec in pre.scenes.items() if spec.lighting is not None]
    if lit:
        dark = [s for s, spec in pre.scenes.items() if spec.lighting is None]
        if dark:
            _issue(out, "LIGHT_MISSING", "BLOCK", f"lighting is planned but scenes {', '.join(dark)} have no plan")


def _per_shot(pre: Any, shots: Any, out: list[RuleIssue]) -> None:
    for g in shots.generations:
        cam = g.camera
        if cam is None:
            continue
        gid = g.generation_id
        book = pre.scenes[g.scene_id].axis if g.scene_id in pre.scenes else None
        if cam.side == "REVERSE" and book is not None and len(book.axis_pair) < 2:
            _issue(out, "CAMERA_AXIS_CROSS", "WARN",
                   f"{gid}: scene {g.scene_id} has a single-character axis, so a reverse camera has no line to cross")
        elif cam.side == "REVERSE":
            _issue(out, "CAMERA_AXIS_CROSS", "WARN",
                   f"{gid}: camera crosses the {'/'.join(book.axis_pair) if book else ''} line ({cam.crossing_note}); "
                   "check the cut keeps screen direction")
        expect = _COVERAGE_SIZE.get(g.coverage)
        if expect is not None:
            gap = abs(_rank(cam.size) - _rank(expect))
            hard = (g.coverage == "MASTER" and cam.size in _TIGHT_SIZES) or (
                g.coverage == "SINGLE" and cam.size in _WIDE_SIZES)
            if hard:
                _issue(out, "CAMERA_SIZE_COVERAGE", "BLOCK", f"{gid}: {g.coverage} coverage declared as {cam.size}")
            elif gap > 1 and cam.size != "INSERT":
                _issue(out, "CAMERA_SIZE_COVERAGE", "WARN",
                       f"{gid}: {cam.size} is {gap} steps from the usual {expect} for {g.coverage}")
        if cam.size in _WIDE_SIZES and not cam.wide_reason.strip():
            beat = " ".join(p.description for p in g.choreography.phases
                            if p.kind in ("ACTION", "CONSEQUENCE", "HOLD")).lower()
            props = [r.split("@")[0][len("prop_"):].replace("_", " ") for r in g.design_refs if r.startswith("prop_")]
            # a lone figure acting on a prop is the unreadable case; a clock time is unreadable at any head count
            solo = len(g.visible) == 1
            hits = ([p for p in props if p and p in beat] if solo else []) + (
                ["a clock time"] if _CLOCK_TIME.search(beat) else [])
            if hits:
                _issue(out, "CAMERA_ACTION_LEGIBLE", "BLOCK",
                       f"{gid}: a {cam.size} shot plays a beat on {', '.join(hits)}; the viewer cannot read it at that size "
                       "- use MEDIUM or closer, or give camera.wide_reason")
        if (cam.lens_intent == "TELE_COMPRESS" and cam.size in _WIDE_SIZES) or (
                cam.lens_intent == "WIDE_ESTABLISH" and cam.size in _TIGHT_SIZES):
            _issue(out, "CAMERA_LENS_SIZE", "WARN", f"{gid}: lens intent {cam.lens_intent} on a {cam.size} shot")
        if cam.lens_mm is not None and cam.lens_intent == "WIDE_ESTABLISH" and cam.lens_mm > 35:
            _issue(out, "CAMERA_LENS_SIZE", "WARN", f"{gid}: {cam.lens_mm} mm is not a wide establishing lens")
        if cam.lens_mm is not None and cam.lens_intent == "TELE_COMPRESS" and cam.lens_mm < 70:
            _issue(out, "CAMERA_LENS_SIZE", "WARN", f"{gid}: {cam.lens_mm} mm is not a compressing lens")


def _size_runs(shots: Any, out: list[RuleIssue]) -> None:
    gens = [g for g in shots.generations if g.camera is not None]
    start = 0
    while start < len(gens):
        end = start
        while end + 1 < len(gens) and gens[end + 1].camera.size == gens[start].camera.size:
            end += 1
        run = gens[start:end + 1]
        if len(run) >= 3 and not all(g.camera.declared_repeat.strip() for g in run[1:]):
            same_scene = len({g.scene_id for g in run}) == 1
            _issue(out, "CAMERA_SIZE_RUN", "BLOCK" if same_scene else "WARN",
                   f"{len(run)} {run[0].camera.size} shots in a row ({run[0].generation_id}..{run[-1].generation_id}) "
                   "without declared_repeat on each repeat")
        start = end + 1


def _light_jump(pre: Any, out: list[RuleIssue]) -> None:
    seen: dict[tuple[str, str], tuple[str, Any]] = {}
    for sid, spec in pre.scenes.items():
        if spec.lighting is None:
            continue
        key = (spec.location, pre.locations[spec.location].look.time_of_day)  # same place, same time of day
        prev = seen.get(key)
        if prev is not None and prev[1].key_direction != spec.lighting.key_direction:
            _issue(out, "LIGHT_JUMP", "WARN",
                   f"{sid}: key light {spec.lighting.key_direction} but {prev[0]} lit the same location and time "
                   f"of day from {prev[1].key_direction}")
        seen.setdefault(key, (sid, spec.lighting))


def camera_issues(pre: Any, shots: Any) -> list[RuleIssue]:
    """Every camera / lighting finding (BLOCK and WARN) for the typed `preprod` + `shots` sections."""
    out: list[RuleIssue] = []
    _completeness(pre, shots, out)
    _per_shot(pre, shots, out)
    _size_runs(shots, out)
    _light_jump(pre, out)
    return out


def camera_report(pre: Any, shots: Any) -> dict[str, Any]:
    """CLI view: the plan as a table plus the findings."""
    issues = camera_issues(pre, shots)
    return {"ok": not any(i.severity == "BLOCK" for i in issues),
            "prompt_fields": list(PROMPT_FIELDS),
            "scenes": {s: spec.lighting.model_dump(mode="json") for s, spec in pre.scenes.items() if spec.lighting},
            "shots": {g.generation_id: g.camera.model_dump(mode="json") for g in shots.generations if g.camera},
            "issues": [i.model_dump() for i in issues]}


def blocking(issues: list[RuleIssue]) -> list[str]:
    return [f"CAMERA {i.check}: {i.detail}" for i in issues if i.severity == "BLOCK"]
