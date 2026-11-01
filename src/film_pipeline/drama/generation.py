"""Split a scene into provider generations with sequential render gating.

A 16 s drama scene is rendered as independent 8 s generations (the provider
cap). ``split_unit`` cuts the planned ``SceneUnit`` into one unit per
generation with shot marks rebased to the window; ``GenerationPlan`` chains
the declared start/end continuity states and decides, from reviewed
``qc.HandoffQC`` objects only, whether generation N+1 may be dispatched.
Nothing here talks to a provider.
"""
from __future__ import annotations

from pydantic import Field

from ..core import ContractModel
from .continuity import ContinuityState, GenerationHandoff
from .coverage import SceneUnit
from .qc import HandoffQC

_EPS = 1e-6


def split_unit(unit: SceneUnit, generation_s: float = 8.0
               ) -> list[SceneUnit]:
    """One unit per ``generation_s`` window; shots belong to the window
    holding their start, times rebased to it."""
    count = round(unit.duration_s / generation_s)
    if count < 1 or abs(count * generation_s - unit.duration_s) > _EPS:
        raise ValueError(f"{unit.scene_id}: duration {unit.duration_s:g}s "
                         f"is not a multiple of {generation_s:g}s")
    for shot in unit.shots:
        window = int(shot.start_s // generation_s + _EPS)
        edge = (window + 1) * generation_s
        if shot.end_s > edge + _EPS:
            raise ValueError(
                f"{unit.scene_id}/{shot.shot_id}: {shot.start_s:g}-"
                f"{shot.end_s:g}s straddles the {edge:g}s generation "
                "boundary")
    units = []
    for i in range(count):
        lo, hi = i * generation_s, (i + 1) * generation_s
        shots = [s.model_copy(update={"start_s": round(s.start_s - lo, 3),
                                      "end_s": round(s.end_s - lo, 3)})
                 for s in unit.shots if lo - _EPS <= s.start_s < hi - _EPS]
        units.append(unit.model_copy(update={"shots": shots,
                                             "duration_s": generation_s}))
    return units


class GenerationSpec(ContractModel):
    generation_id: str          # e.g. "SC03_g1"
    index: int                  # 1-based
    unit: SceneUnit
    action: str
    start_state: ContinuityState
    end_state: ContinuityState


class GenerationPlan(ContractModel):
    scene_id: str
    generations: list[GenerationSpec] = Field(default_factory=list)

    def problems(self) -> list[str]:
        out: list[str] = []
        ids = [g.generation_id for g in self.generations]
        for dup in sorted({i for i in ids if ids.count(i) > 1}):
            out.append(f"duplicate generation_id {dup}")
        expected = list(range(1, len(self.generations) + 1))
        got = [g.index for g in self.generations]
        if got != expected:
            out.append(f"indices {got} are not {expected}")
        for prev, cur in zip(self.generations, self.generations[1:]):
            a, b = prev.end_state.as_dict(), cur.start_state.as_dict()
            for key in a:
                if a[key] != b[key]:
                    out.append(f"{cur.generation_id}: start_state.{key} != "
                               f"{prev.generation_id} end_state.{key}")
        return out

    def _spec(self, index: int) -> GenerationSpec:
        return next(g for g in self.generations if g.index == index)

    def handoff_for(self, index: int, qc: HandoffQC | None
                    ) -> GenerationHandoff | None:
        if index <= 1:
            return None
        prev = self._spec(index - 1)
        if qc is None:
            return GenerationHandoff(
                previous_generation_id=prev.generation_id,
                previous_action=prev.action, previous_start=prev.start_state,
                previous_end=prev.end_state, end_state_verified=False)
        return qc.to_handoff(previous_action=prev.action,
                             previous_start=prev.start_state,
                             previous_end=prev.end_state)

    def dispatchable(self, index: int,
                     qc_by_previous_id: dict[str, HandoffQC]) -> bool:
        if index <= 1:
            return True
        qc = qc_by_previous_id.get(self._spec(index - 1).generation_id)
        return qc is not None and qc.verified
