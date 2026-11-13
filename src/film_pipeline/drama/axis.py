"""Drama P0 #9 — 180-degree axis book.

``DirectorCompiler`` only labels ``camera_side_of_axis``; nothing enforced
it. The axis book fixes, per scene, which character holds screen-left and
which screen-right. Every shot must keep those sides, and eyelines must
mirror: the screen-left character looks screen-right and vice versa. A
shot that crosses the line is legal only when declared with a reason.
"""
from __future__ import annotations

from typing import Literal

from pydantic import Field, model_validator

from ..core import ContractModel

ScreenSide = Literal["LEFT", "RIGHT"]
Eyeline = Literal["screen-left", "screen-right", "camera", "down", "none"]


class AxisBook(ContractModel):
    scene_id: str
    # the two characters the line of action runs between, A then B
    axis_pair: list[str] = Field(min_length=1, max_length=2)
    sides: dict[str, ScreenSide]

    @model_validator(mode="after")
    def _pair_on_opposite_sides(self):
        missing = [c for c in self.axis_pair if c not in self.sides]
        if missing:
            raise ValueError(f"axis characters without a side: {missing}")
        if len(self.axis_pair) == 2 and \
                self.sides[self.axis_pair[0]] == self.sides[self.axis_pair[1]]:
            raise ValueError("axis pair must hold opposite screen sides")
        return self

    @classmethod
    def for_pair(cls, scene_id: str, a: str, b: str | None = None,
                 *, a_side: ScreenSide = "LEFT") -> "AxisBook":
        sides: dict[str, ScreenSide] = {a: a_side}
        if b:
            sides[b] = "RIGHT" if a_side == "LEFT" else "LEFT"
        return cls(scene_id=scene_id, axis_pair=[a] + ([b] if b else []),
                   sides=sides)

    def partner(self, character: str) -> str | None:
        if len(self.axis_pair) < 2 or character not in self.axis_pair:
            return None
        return self.axis_pair[1] if character == self.axis_pair[0] \
            else self.axis_pair[0]

    def eyeline_toward_partner(self, character: str) -> Eyeline:
        side = self.sides.get(character)
        if side is None:
            return "none"
        return "screen-right" if side == "LEFT" else "screen-left"


class ShotAxisRecord(ContractModel):
    shot_id: str
    visible: dict[str, ScreenSide] = Field(default_factory=dict)
    # where each visible character looks; toward the partner is the norm
    eyelines: dict[str, Eyeline] = Field(default_factory=dict)
    crosses_axis: bool = False
    cross_justification: str = ""
    # characters looking at someone other than their axis partner (a third
    # person anchored off frame); their lateral eyeline is not checked
    # against the partner
    off_partner: list[str] = Field(default_factory=list)


def axis_record(book: AxisBook, shot_id: str, visible: list[str], *,
                looking_at_partner: bool = True,
                eyelines: dict[str, Eyeline] | None = None,
                gaze_target: str = "") -> ShotAxisRecord:
    """Build the record a compliant shot should have.

    ``eyelines`` overrides the partner-derived eyeline per character: with
    three people only two hold the axis, and the third (film08 HOLLIS,
    centre) looks toward whoever the shot addresses, not a fixed partner.
    """
    looks = {c: (book.eyeline_toward_partner(c)
                 if looking_at_partner and book.partner(c) else "none")
             for c in visible}
    overrides = {c: e for c, e in (eyelines or {}).items() if c in looks}
    looks.update(overrides)
    off_partner = [c for c in overrides if gaze_target and book.partner(c)
                   and gaze_target != book.partner(c)]
    return ShotAxisRecord(
        shot_id=shot_id,
        visible={c: book.sides[c] for c in visible if c in book.sides},
        eyelines=looks, off_partner=off_partner)


def check_axis(book: AxisBook, shots: list[ShotAxisRecord]) -> list[str]:
    """Violations; empty == the scene respects the line."""
    problems: list[str] = []
    for shot in shots:
        if shot.crosses_axis:
            if not shot.cross_justification.strip():
                problems.append(f"{shot.shot_id}: crosses the axis without "
                                "a declared justification")
            continue
        for character, side in shot.visible.items():
            expected = book.sides.get(character)
            if expected is None:
                problems.append(f"{shot.shot_id}: {character} has no side "
                                "in the axis book")
            elif side != expected:
                problems.append(f"{shot.shot_id}: {character} on {side}, "
                                f"axis book says {expected}")
        for character, eyeline in shot.eyelines.items():
            if eyeline == "camera":
                problems.append(f"{shot.shot_id}: {character} looks into "
                                "the lens (breaks the fourth wall)")
            elif eyeline in ("screen-left", "screen-right") and \
                    book.partner(character) and \
                    character not in shot.off_partner and \
                    eyeline != book.eyeline_toward_partner(character):
                problems.append(
                    f"{shot.shot_id}: {character} looks {eyeline}, must "
                    f"look {book.eyeline_toward_partner(character)} toward "
                    f"{book.partner(character)}")
    return problems
