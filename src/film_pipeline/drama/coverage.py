"""Drama P0 #10 + #11 — dialogue coverage inside a 15-second scene unit.

``DirectorCompiler`` stages one walking subject and emits one 5-second
shot per generation. A drama scene is instead ONE generation of ~15 s
holding several shots with explicit time marks:

    master (geography) -> over-the-shoulder / single on whoever speaks
    -> reaction on the listener (the silence the scene needs)

Durations follow the speech each shot carries (syllables / rate), are
normalised to the scene length in 0.1 s steps and must respect the
minimum shot length and maximum shot count. Values marked ``(*)`` are
assumptions to re-measure on the first test scene.
"""
from __future__ import annotations

from typing import Literal

from pydantic import Field

from ..core import ContractModel
from .axis import AxisBook, ShotAxisRecord, axis_record, check_axis
from .script import ScriptScene

Coverage = Literal["MASTER", "TWO_SHOT", "OTS", "SINGLE", "REACTION"]
ShotSize = Literal["WIDE", "MEDIUM", "MEDIUM_CLOSE", "CLOSE"]

_SIZE: dict[str, ShotSize] = {"MASTER": "WIDE", "TWO_SHOT": "MEDIUM",
                              "OTS": "MEDIUM_CLOSE", "SINGLE": "CLOSE",
                              "REACTION": "MEDIUM_CLOSE"}
# beats that earn a clean single instead of an over-the-shoulder
_SINGLE_BEATS = {"REVEAL", "DECISION", "REACTION", "PRESSURE"}


class SceneTiming(ContractModel):
    duration_s: float = 15.0
    max_shots: int = 4              # (*)
    min_shot_s: float = 2.0
    syllables_per_second: float = 4.0   # (*)
    establish_s: float = 1.5        # extra hold on the master
    reaction_s: float = 3.0         # silence held on the listener


class SpokenLine(ContractModel):
    character: str
    text: str
    syllables: int
    parenthetical: str = ""
    line_no: int | None = None


class CoverageShot(ContractModel):
    shot_id: str
    coverage: Coverage
    shot_size: ShotSize
    subject: str = ""          # who the shot is on ("" for master)
    foreground: str = ""       # OTS: whose shoulder frames the subject
    start_s: float = 0.0
    end_s: float = 0.0
    lines: list[SpokenLine] = Field(default_factory=list)
    action: str = ""
    axis: ShotAxisRecord

    @property
    def duration_s(self) -> float:
        return round(self.end_s - self.start_s, 3)

    def describe(self, book: AxisBook) -> str:
        if self.coverage == "MASTER":
            placed = ", ".join(f"{c} {s.lower()}"
                               for c, s in book.sides.items())
            kind = "wide two-shot" if len(book.sides) <= 2 else "wide shot"
            return f"{kind}, {placed}"
        if self.coverage == "TWO_SHOT":
            return "medium two-shot, profiles facing each other"
        if self.coverage == "OTS":
            return f"over {self.foreground}'s shoulder onto {self.subject}"
        if self.coverage == "SINGLE":
            return (f"close-up of {self.subject} looking "
                    f"{book.eyeline_toward_partner(self.subject)}")
        return (f"silent close-up of {self.subject} looking "
                f"{book.eyeline_toward_partner(self.subject)}")


class SceneUnit(ContractModel):
    scene_id: str
    duration_s: float
    shots: list[CoverageShot]
    axis_book: AxisBook

    def timing_problems(self, timing: SceneTiming | None = None
                        ) -> list[str]:
        timing = timing or SceneTiming()
        problems: list[str] = []
        if not self.shots:
            return ["scene has no shots"]
        if len(self.shots) > timing.max_shots:
            problems.append(f"{len(self.shots)} shots > max "
                            f"{timing.max_shots}")
        cursor = 0.0
        for shot in self.shots:
            if abs(shot.start_s - cursor) > 1e-6:
                problems.append(f"{shot.shot_id}: starts at {shot.start_s}"
                                f", expected {cursor:g} (gap/overlap)")
            if shot.duration_s < timing.min_shot_s - 1e-6:
                problems.append(f"{shot.shot_id}: {shot.duration_s:g}s < "
                                f"min {timing.min_shot_s:g}s")
            cursor = shot.end_s
        if abs(cursor - self.duration_s) > 1e-6:
            problems.append(f"shot marks end at {cursor:g}s, scene is "
                            f"{self.duration_s:g}s")
        return problems

    def axis_problems(self) -> list[str]:
        return check_axis(self.axis_book, [s.axis for s in self.shots])


class _Segment:
    def __init__(self, coverage: str, subject: str = "",
                 lines: list[SpokenLine] | None = None,
                 action: str = "", beat: str = "") -> None:
        self.coverage = coverage
        self.subject = subject
        self.lines = lines or []
        self.action = action
        self.beat = beat

    def weight(self, timing: SceneTiming) -> float:
        speech = sum(l.syllables for l in self.lines) / \
            timing.syllables_per_second
        if self.coverage == "MASTER":
            speech += timing.establish_s
        if self.coverage == "REACTION":
            speech = max(speech, timing.reaction_s)
        # a short breath after each line so cuts never clip a word
        return max(timing.min_shot_s, speech + 0.4 * len(self.lines))


class CoveragePlanner:
    """Script scene + axis book -> SceneUnit with time-marked shots."""

    def __init__(self, timing: SceneTiming | None = None) -> None:
        self.timing = timing or SceneTiming()

    def plan(self, scene: ScriptScene, book: AxisBook) -> SceneUnit:
        segments = self._segments(scene, book)
        segments = self._fit_count(segments)
        marks = self._marks([s.weight(self.timing) for s in segments])
        shots = []
        for index, (segment, (start, end)) in enumerate(
                zip(segments, marks)):
            shot_id = f"{scene.scene_id}_S{index + 1}"
            visible = self._visible(segment, book)
            foreground = (book.partner(segment.subject) or ""
                          if segment.coverage == "OTS" else "")
            shots.append(CoverageShot(
                shot_id=shot_id, coverage=segment.coverage,  # type: ignore[arg-type]
                shot_size=_SIZE[segment.coverage], subject=segment.subject,
                foreground=foreground, start_s=start, end_s=end,
                lines=segment.lines, action=segment.action,
                axis=axis_record(book, shot_id, visible)))
        return SceneUnit(scene_id=scene.scene_id,
                         duration_s=self.timing.duration_s, shots=shots,
                         axis_book=book)

    # -- shot selection ---------------------------------------------------------

    def _segments(self, scene: ScriptScene, book: AxisBook
                  ) -> list[_Segment]:
        lines: list[tuple[SpokenLine, str]] = []
        opening_action: list[str] = []
        for element in scene.elements:
            if element.kind == "dialogue":
                lines.append((SpokenLine(
                    character=element.character, text=element.text,
                    syllables=element.syllables,
                    parenthetical=element.parenthetical,
                    line_no=element.line_no), element.beat))
            elif element.kind == "action" and not lines:
                opening_action.append(element.text)
        master = _Segment("MASTER", action=" ".join(opening_action))
        if not lines:
            return [master]
        segments = [master]
        # the master also carries the first line: geography + who speaks
        master.lines.append(lines[0][0])
        previous_speaker = lines[0][0].character
        for line, beat in lines[1:]:
            same_speaker = line.character == previous_speaker
            # a key beat from the same speaker earns a punch-in single;
            # _fit_count folds it back if the shot budget is exceeded
            punch_in = beat in _SINGLE_BEATS and \
                segments[-1].coverage != "SINGLE"
            if segments[-1].coverage != "MASTER" and same_speaker and \
                    not punch_in:
                segments[-1].lines.append(line)
                continue
            coverage = "SINGLE" if beat in _SINGLE_BEATS or \
                book.partner(line.character) is None else "OTS"
            segments.append(_Segment(coverage, subject=line.character,
                                     lines=[line], beat=beat))
            previous_speaker = line.character
        listener = book.partner(lines[-1][0].character)
        if listener:
            segments.append(_Segment("REACTION", subject=listener))
        return segments

    def _fit_count(self, segments: list[_Segment]) -> list[_Segment]:
        """Too many shots: merge the lightest adjacent pair of middle
        (dialogue) shots into a two-shot. Master and reaction stay."""
        while len(segments) > self.timing.max_shots:
            middle = range(1, len(segments) - 2) \
                if segments[-1].coverage == "REACTION" \
                else range(1, len(segments) - 1)
            if not middle:
                # only master + reaction would remain mergeable: fold the
                # reaction away rather than exceed the shot budget
                segments.pop()
                continue
            best = min(middle, key=lambda i: segments[i].weight(self.timing)
                       + segments[i + 1].weight(self.timing))
            a, b = segments[best], segments[best + 1]
            same = a.subject == b.subject
            merged = _Segment(a.coverage if same else "TWO_SHOT",
                              subject=a.subject if same else "",
                              lines=a.lines + b.lines, beat=a.beat or b.beat)
            segments[best:best + 2] = [merged]
        return segments

    def _marks(self, weights: list[float]) -> list[tuple[float, float]]:
        """Normalise weights to the scene length in 0.1 s steps; every shot
        keeps >= min_shot_s; rounding residue goes to the longest shot."""
        total_ticks = round(self.timing.duration_s * 10)
        min_ticks = round(self.timing.min_shot_s * 10)
        if min_ticks * len(weights) > total_ticks:
            raise ValueError(f"{len(weights)} shots cannot each hold "
                             f"{self.timing.min_shot_s}s in "
                             f"{self.timing.duration_s}s")
        scale = total_ticks / sum(weights)
        ticks = [max(min_ticks, round(w * scale)) for w in weights]
        while sum(ticks) != total_ticks:
            if sum(ticks) > total_ticks:
                candidates = [i for i, t in enumerate(ticks) if t > min_ticks]
                i = max(candidates, key=lambda k: ticks[k])
                ticks[i] -= 1
            else:
                i = max(range(len(ticks)), key=lambda k: weights[k])
                ticks[i] += 1
        marks, cursor = [], 0
        for t in ticks:
            marks.append((cursor / 10, (cursor + t) / 10))
            cursor += t
        return marks

    @staticmethod
    def _visible(segment: _Segment, book: AxisBook) -> list[str]:
        if segment.coverage in ("MASTER", "TWO_SHOT"):
            return list(book.axis_pair)
        if segment.coverage == "OTS":
            partner = book.partner(segment.subject)
            return [segment.subject] + ([partner] if partner else [])
        return [segment.subject]
