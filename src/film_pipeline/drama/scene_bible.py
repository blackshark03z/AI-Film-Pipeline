"""Scene bible: locked locations, who is in the room, story time (WP2).

Each rule exists for a film01 / Muse defect:

* ``LocationLook`` - film01 SC03_g2 background drifted (the EXIT sign was
  lost, a glass partition appeared). The set text is copied verbatim into
  every prompt and its invariants are what QC checks.
* ``check_environment`` - Muse "rain inside the room": weather in an
  interior needs a causal qualifier (window, glass, outside); a scene's
  time of day must agree with its location's.
* ``SceneOccupancy`` - a character may only be named or in frame while
  present in the scene (ENTER / EXIT events by generation).
* ``check_temporal`` - Muse R1 treated a cold-open teaser as continuous.
  A linear cut cannot go back in time, a non-linear cut must be readable
  by the audience, and going back in time may reset props and positions
  but never the face/look. Source conflicts are the Owner's call.

Issues use the same shape as ``preflight.PreflightIssue`` (defined here
because preflight imports this module).
"""
from __future__ import annotations

import re
from typing import Literal

from pydantic import Field

from ..core import ContractModel
from .continuity import ContinuityState
from .script import ScriptScene


class RuleIssue(ContractModel):
    check: str
    severity: Literal["BLOCK", "WARN"]
    detail: str


TemporalIssue = RuleIssue


class LocationLook(ContractModel):
    look_id: str
    location: str
    text: str                        # locked set description, verbatim
    invariants: list[str] = Field(default_factory=list)
    interior: bool = True
    time_of_day: str = ""            # "" = unspecified
    weather_outside: str = ""
    environment_rules: list[str] = Field(default_factory=list)
    approved: bool = False

    def problems(self) -> list[str]:
        found: list[str] = []
        if not self.text.strip():
            found.append(f"{self.location}: location {self.look_id} has no "
                         "text")
        if not self.invariants:
            found.append(f"{self.location}: location {self.look_id} lists "
                         "no invariants for QC")
        if not self.approved:
            found.append(f"{self.location}: location {self.look_id} not "
                         "approved")
        if self.interior and self.weather_outside and \
                not self.environment_rules:
            found.append(f"{self.location}: interior with outside weather "
                         f"{self.weather_outside!r} but no environment "
                         "rules")
        return found


class OccupancyEvent(ContractModel):
    generation_index: int
    character: str
    kind: Literal["ENTER", "EXIT"]


class SceneOccupancy(ContractModel):
    scene_id: str
    initial: list[str] = Field(default_factory=list)
    events: list[OccupancyEvent] = Field(default_factory=list)

    def _ordered(self) -> list[OccupancyEvent]:
        return sorted(self.events, key=lambda e: e.generation_index)

    def present_at(self, generation_index: int) -> set[str]:
        """Events at index k apply from generation k on."""
        here = set(self.initial)
        for event in self._ordered():
            if event.generation_index > generation_index:
                break
            if event.kind == "ENTER":
                here.add(event.character)
            else:
                here.discard(event.character)
        return here

    def problems(self) -> list[str]:
        found: list[str] = []
        here = set(self.initial)
        for event in self._ordered():
            who, gen = event.character, event.generation_index
            if event.kind == "ENTER":
                if who in here:
                    found.append(f"{who}: ENTER at generation {gen} but "
                                 "already present")
                here.add(who)
            else:
                if who not in here:
                    found.append(f"{who}: EXIT at generation {gen} but not "
                                 "present")
                here.discard(who)
        return found


TransitionIn = Literal["LINEAR", "FLASHBACK", "FLASHFORWARD", "ELLIPSIS",
                       "PARALLEL", "REPLAY"]


class StoryTime(ContractModel):
    scene_id: str
    story_order: float               # chronological position
    transition_in: TransitionIn = "LINEAR"
    marker: str = ""                 # how the audience reads the change
    source_conflict: str = ""


def check_temporal(scenes: list[StoryTime],
                   end_states: dict[str, ContinuityState],
                   start_states: dict[str, ContinuityState]
                   ) -> list[RuleIssue]:
    """``scenes`` in screen order; states keyed by scene_id."""
    issues: list[RuleIssue] = []

    def add(check: str, severity: str, detail: str) -> None:
        issues.append(RuleIssue(check=check, severity=severity,  # type: ignore[arg-type]
                                detail=detail))

    for index, (prev, cur) in enumerate(zip(scenes, scenes[1:])):
        sid = f"{prev.scene_id}->{cur.scene_id}"
        if cur.transition_in == "LINEAR":
            if cur.story_order <= prev.story_order:
                add("TEMPORAL_ORDER", "BLOCK",
                    f"{sid}: linear cut goes from story_order "
                    f"{prev.story_order:g} to {cur.story_order:g}; mark it "
                    "as a flashback/replay or reorder")
        elif not cur.marker.strip():
            add("TEMPORAL_READABILITY", "BLOCK",
                f"{sid}: {cur.transition_in} has no marker the audience "
                "can read")
        start = start_states.get(cur.scene_id)
        end = end_states.get(prev.scene_id)
        if cur.transition_in == "LINEAR":
            # a linear cut continues the latest earlier story moment: after
            # a flashback that is the scene before it, not the flashback
            earlier = [s for s in scenes[:index + 1]
                       if s.story_order < cur.story_order]
            if earlier:
                anchor = max(earlier, key=lambda s: s.story_order)
                end = end_states.get(anchor.scene_id)
                sid = f"{anchor.scene_id}->{cur.scene_id}"
        if end is None or start is None:
            continue
        if cur.transition_in == "LINEAR":
            for key in ("positions", "props"):
                a, b = getattr(end, key), getattr(start, key)
                for item in sorted(set(a) | set(b)):
                    if a.get(item) != b.get(item):
                        add("STATE", "BLOCK",
                            f"{sid}: {key}[{item}] ends {a.get(item)!r} but "
                            f"starts {b.get(item)!r}")
        for who in sorted(set(end.looks) & set(start.looks)):
            if end.looks[who] != start.looks[who]:
                add("IDENTITY", "BLOCK",
                    f"{sid}: {who} look changes {end.looks[who]!r} -> "
                    f"{start.looks[who]!r}; time may reset props, never the "
                    "look")
    for scene in scenes:
        if scene.source_conflict.strip():
            add("SOURCE_CONFLICT", "WARN",
                f"{scene.scene_id}: {scene.source_conflict} (Owner decides)")
    return issues


_WEATHER = re.compile(
    r"(?<!\w)(?:rain|raining|rainy|snow|storm|wind|puddle|mưa|tuyết|bão|gió)"
    r"(?!\w)", re.IGNORECASE)
_QUALIFIER = re.compile(
    r"(?<!\w)(?:window|glass|outside|through|ngoài|cửa sổ|kính)(?!\w)",
    re.IGNORECASE)

_DAY = {"DAY", "NGÀY", "MORNING", "SÁNG", "AFTERNOON", "CHIỀU"}
_NIGHT = {"NIGHT", "ĐÊM", "EVENING", "TỐI"}
# headings that inherit the time of the previous scene (nothing to compare)
_INHERIT = ("CONTINUOUS", "LATER", "SAME", "LIÊN TỤC", "TIẾP THEO")


_GROUPS = (("DAWN", {"DAWN", "BÌNH MINH"}), ("DUSK", {"DUSK", "HOÀNG HÔN"}),
           ("DAY", _DAY), ("NIGHT", _NIGHT))


def _tod_group(value: str) -> str:
    """Group a heading time; extra words count too ("THAT MORNING
    (FLASHBACK)" is DAY)."""
    v = value.strip().upper()
    for group, names in _GROUPS:
        if v in names:
            return group
    for group, names in _GROUPS:
        if any(re.search(rf"(?<!\w){re.escape(n)}(?!\w)", v) for n in names):
            return group
    return v


def check_environment(scene: ScriptScene, location: LocationLook,
                      texts: list[str]) -> list[RuleIssue]:
    issues: list[RuleIssue] = []
    if scene.setting == "INT" or location.interior:
        for text in texts:
            match = _WEATHER.search(text)
            if match and not _QUALIFIER.search(text):
                issues.append(RuleIssue(
                    check="ENVIRONMENT_CAUSALITY", severity="BLOCK",
                    detail=(f"'{match.group(0)}' in an interior without a "
                            f"window/outside qualifier: {text[:80]}")))
    inherits = any(k in scene.time_of_day.upper() for k in _INHERIT)
    if scene.time_of_day and location.time_of_day and not inherits and \
            _tod_group(scene.time_of_day) != _tod_group(location.time_of_day):
        issues.append(RuleIssue(
            check="TIME_OF_DAY", severity="BLOCK",
            detail=(f"scene is {scene.time_of_day!r} but location "
                    f"{location.look_id} is {location.time_of_day!r}")))
    return issues
