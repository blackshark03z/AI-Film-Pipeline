"""V2-021 Phases E-H — DirectorCompiler, CameraContinuityState, ShotGraph,
minimum-shot-set optimization."""
from __future__ import annotations

from typing import Literal

from pydantic import Field

from ..core import ContractModel
from .narrative import StoryBeat, WorldState

ShotFunction = Literal[
    "ESTABLISH", "APPROACH", "DISCOVER", "PRESSURE", "REACTION", "DECISION",
    "REVEAL", "PAYOFF", "AFTERMATH", "RESOLVE", "ATMOSPHERE", "RHYTHM",
    "TRANSITION",
]
ShotSize = Literal["EXTREME_WIDE", "WIDE", "MEDIUM", "MEDIUM_CLOSE",
                   "CLOSE", "INSERT"]
CameraMovement = Literal["LOCKED", "PAN", "TILT", "TRACKING_LATERAL",
                         "PUSH_IN", "PULL_OUT", "HANDHELD"]
EdgeKind = Literal["CUT", "MATCH_CUT", "MOTION_CONTINUATION", "EYELINE",
                   "REVEAL", "TIME_JUMP", "LOCATION_TRANSITION"]


class CameraContinuityState(ContractModel):
    """Phase F — per-shot incoming/outgoing camera grammar state."""
    screen_direction: Literal["left-to-right", "right-to-left", "static",
                              "toward-camera", "away-camera"]
    camera_side_of_axis: Literal["north", "south", "neutral"] = "neutral"
    subject_scale: ShotSize = "MEDIUM"
    movement_vector: CameraMovement = "LOCKED"
    eyeline_target: str = ""        # "", "off_left", "off_right", "object"
    entrance_side: Literal["left", "right", "none", "center"] = "none"
    exit_side: Literal["left", "right", "none", "center"] = "none"
    lens_intent: str = ""           # e.g. "wide 24mm", "normal 50mm"


class DirectorShotIntent(ContractModel):
    """Phase E — one chosen shot before graph assembly."""
    shot_id: str
    function: ShotFunction
    beat_ids: list[str]
    story_purpose: str
    shot_size: ShotSize
    camera_angle: str
    camera_movement: CameraMovement
    blocking: str
    screen_direction: Literal["left-to-right", "right-to-left", "static",
                              "toward-camera", "away-camera"]
    light_direction: str
    motion_vector: str
    duration_target_s: float
    transition_intent: EdgeKind = "CUT"
    classified_extras: list[Literal["ATMOSPHERE", "RHYTHM",
                                    "TRANSITION"]] = Field(
        default_factory=list)
    story_node_ids: list[str] = Field(default_factory=list)


class ShotGraphNode(ContractModel):
    """Phase G — a compiled shot with explicit state contracts."""
    shot_id: str
    story_purpose: str
    story_node_ids: list[str]           # traceability (StoryGraph)
    function: ShotFunction
    incoming_state: dict = Field(default_factory=dict)
    outgoing_state: dict = Field(default_factory=dict)
    world_state: dict = Field(default_factory=dict)
    character_state: dict = Field(default_factory=dict)
    camera_intent: dict = Field(default_factory=dict)
    motion_intent: str = ""
    continuity_constraints: list[str] = Field(default_factory=list)
    duration_target_s: float = 5.0
    priority: Literal["P0", "P1", "P2"] = "P1"
    repairability: Literal["HIGH", "MEDIUM", "LOW"] = "HIGH"
    provider_requirements: dict = Field(default_factory=dict)


class ShotGraphEdge(ContractModel):
    src: str
    dst: str
    kind: EdgeKind
    rationale: str = ""


class ShotGraph:
    def __init__(self) -> None:
        self.nodes: list[ShotGraphNode] = []
        self.edges: list[ShotGraphEdge] = []

    def add_node(self, node: ShotGraphNode) -> None:
        self.nodes.append(node)

    def add_edge(self, edge: ShotGraphEdge) -> None:
        self.edges.append(edge)

    def to_manifest(self) -> dict:
        return {"nodes": [n.model_dump() for n in self.nodes],
                "edges": [e.model_dump() for e in self.edges]}


# beat-function -> cinematic defaults (the Director grammar table)
_GRAMMAR: dict[str, dict] = {
    "ESTABLISH": {"shot_size": "WIDE", "movement": "LOCKED",
                  "angle": "eye level", "duration": 5.0,
                  "transition": "CUT"},
    "APPROACH": {"shot_size": "WIDE", "movement": "LOCKED",
                 "angle": "eye level", "duration": 5.0,
                 "transition": "CUT"},
    "DISCOVER": {"shot_size": "MEDIUM", "movement": "PUSH_IN",
                 "angle": "eye level", "duration": 5.0,
                 "transition": "CUT"},
    "PRESSURE": {"shot_size": "MEDIUM_CLOSE", "movement": "LOCKED",
                 "angle": "slightly low", "duration": 5.0,
                 "transition": "CUT"},
    "REACTION": {"shot_size": "MEDIUM_CLOSE", "movement": "LOCKED",
                 "angle": "eye level", "duration": 5.0,
                 "transition": "CUT"},
    "DECISION": {"shot_size": "MEDIUM", "movement": "LOCKED",
                 "angle": "high-ish", "duration": 5.0,
                 "transition": "CUT"},
    "REVEAL": {"shot_size": "MEDIUM_CLOSE", "movement": "PUSH_IN",
               "angle": "eye level", "duration": 5.0,
               "transition": "MATCH_CUT"},
    "PAYOFF": {"shot_size": "WIDE", "movement": "LOCKED",
               "angle": "eye level", "duration": 5.0,
               "transition": "CUT"},
    "AFTERMATH": {"shot_size": "EXTREME_WIDE", "movement": "LOCKED",
                  "angle": "eye level", "duration": 5.0,
                  "transition": "CUT"},
    "RESOLVE": {"shot_size": "WIDE", "movement": "TRACKING_LATERAL",
                "angle": "eye level", "duration": 5.0,
                "transition": "CUT"},
    "ATMOSPHERE": {"shot_size": "EXTREME_WIDE", "movement": "LOCKED",
                   "angle": "eye level", "duration": 5.0,
                   "transition": "CUT"},
    "RHYTHM": {"shot_size": "MEDIUM", "movement": "LOCKED",
               "angle": "eye level", "duration": 5.0,
               "transition": "CUT"},
    "TRANSITION": {"shot_size": "WIDE", "movement": "LOCKED",
                   "angle": "eye level", "duration": 5.0,
                   "transition": "TIME_JUMP"},
}


class DirectorCompiler:
    """Phase E+H — beats -> cinematic treatment -> minimum ShotGraph.

    Rhythm rule: never more than two consecutive shots with the same
    (shot_size, movement) pair unless explicitly classified RHYTHM.
    Minimum set: merge consecutive beats that share one function into a
    single shot when the visual information requirement is unchanged.
    """

    def __init__(self, *, screen_direction: str = "left-to-right",
                 light_direction: str = "overcast diffuse",
                 mutation_cost: int = 1,
                 continuity_risk_weight: float = 0.6,
                 cost_weight: float = 0.4) -> None:
        self.screen_direction = screen_direction
        self.light_direction = light_direction
        self.mutation_cost = mutation_cost
        self.risk_weight = continuity_risk_weight
        self.cost_weight = cost_weight

    def design(self, beats: list[StoryBeat], *,
               world_state: WorldState,
               cast: list[dict]) -> tuple[ShotGraph, list[DirectorShotIntent]]:
        intents = self._treat(beats)
        intents = self._optimize(intents)
        graph = self._graph(intents, world_state=world_state, cast=cast)
        return graph, intents

    # -- Phase E: treatment --------------------------------------------------

    def _treat(self, beats: list[StoryBeat]) -> list[DirectorShotIntent]:
        intents = []
        previous_size = None
        for index, beat in enumerate(beats):
            grammar = _GRAMMAR[beat.function]
            size = grammar["shot_size"]
            movement = grammar["movement"]
            # rhythm rule: break identical consecutive pairs
            if (size, movement) == previous_size and \
                    len(beats) > 2:
                alt = {"WIDE": "MEDIUM", "MEDIUM": "MEDIUM_CLOSE",
                       "MEDIUM_CLOSE": "MEDIUM", "EXTREME_WIDE": "WIDE"}
                size = alt.get(size, "MEDIUM")  # type: ignore[assignment]
                if movement == "LOCKED" and size == "MEDIUM":
                    movement = "PUSH_IN"
            previous_size = (size, movement)
            intents.append(DirectorShotIntent(
                shot_id=f"S{index + 1:02d}",
                function=beat.function, beat_ids=[beat.beat_id],
                story_purpose=beat.summary[:160],
                shot_size=size,  # type: ignore[arg-type]
                camera_angle=grammar["angle"],
                camera_movement=movement,  # type: ignore[arg-type]
                blocking=self._blocking(beat.function),
                screen_direction=self.screen_direction,  # type: ignore[arg-type]
                light_direction=self.light_direction,
                motion_vector=self._motion_vector(beat.function),
                duration_target_s=grammar["duration"],
                transition_intent=grammar["transition"],  # type: ignore[arg-type]
                story_node_ids=list(beat.event_ids)))
        return intents

    @staticmethod
    def _blocking(function: str) -> str:
        return {
            "ESTABLISH": "subject enters left, traverses frame",
            "APPROACH": "subject walking through frame, steady pace",
            "DISCOVER": "subject stops, gaze drops to foreground object",
            "PRESSURE": "subject holds still, breath visible, hands tense",
            "REACTION": "subject still, gaze lifts slowly",
            "DECISION": "subject reaches/kneels, commits to the object",
            "REVEAL": "subject holds the object, face in profile",
            "PAYOFF": "subject secures object on body, resumes walking",
            "AFTERMATH": "subject small against the empty world",
            "RESOLVE": "subject exits frame, pace visibly quicker",
        }.get(function, "subject centered")

    @staticmethod
    def _motion_vector(function: str) -> str:
        return {
            "ESTABLISH": "travel left-to-right, slow",
            "APPROACH": "travel left-to-right, steady",
            "DISCOVER": "deceleration to stillness",
            "PAYOFF": "stillness -> acceleration",
            "RESOLVE": "accelerated exit left-to-right",
        }.get(function, "minimal")

    # -- Phase H: optimization -------------------------------------------------

    def _optimize(self, intents: list[DirectorShotIntent]) -> list[
            DirectorShotIntent]:
        """Minimum set: merge same-function consecutive beats; drop
        redundant coverage; score cost vs continuity risk."""
        merged: list[DirectorShotIntent] = []
        for intent in intents:
            if merged and merged[-1].function == intent.function and \
                    merged[-1].function in ("APPROACH", "REACTION",
                                            "AFTERMATH"):
                merged[-1].beat_ids.extend(intent.beat_ids)
                merged[-1].story_node_ids.extend(intent.story_node_ids)
                continue
            merged.append(intent)
        # risk scoring happens at graph assembly (repairability); story
        # order is preserved — the minimum set is the merged set
        return merged

    # -- Phase G: graph ----------------------------------------------------------

    def _graph(self, intents: list[DirectorShotIntent], *,
               world_state: WorldState,
               cast: list[dict]) -> ShotGraph:
        graph = ShotGraph()
        incoming: dict = {"screen_direction": self.screen_direction,
                          "world": world_state.model_dump(),
                          "characters": {c["name"]: "en route"
                                         for c in cast}}
        for index, intent in enumerate(intents):
            continuity = [
                "screen direction must remain "
                f"{self.screen_direction}",
                "wardrobe and props persist from previous shot",
                "world/lighting persist unless story changes it"]
            outgoing = dict(incoming)
            outgoing["last_function"] = intent.function
            node = ShotGraphNode(
                shot_id=intent.shot_id,
                story_purpose=intent.story_purpose,
                story_node_ids=intent.story_node_ids,
                function=intent.function,
                incoming_state=dict(incoming),
                outgoing_state=outgoing,
                world_state=world_state.model_dump(),
                character_state={c["name"]: self._character_state(
                    intent.function) for c in cast},
                camera_intent={
                    "shot_size": intent.shot_size,
                    "angle": intent.camera_angle,
                    "movement": intent.camera_movement,
                    "light_direction": intent.light_direction,
                    "duration_target_s": intent.duration_target_s},
                motion_intent=intent.motion_vector,
                continuity_constraints=continuity,
                duration_target_s=intent.duration_target_s,
                priority=("P0" if intent.function == "REVEAL"
                          else "P1" if intent.function in ("DISCOVER",
                                                           "PAYOFF")
                          else "P2"),  # type: ignore[arg-type]
                repairability="MEDIUM" if intent.shot_size in (
                    "CLOSE", "MEDIUM_CLOSE") else "HIGH",
                provider_requirements={
                    "duration_class": 5, "model": "free-route default",
                    "references": "TEXT_ANCHOR_ONLY"},
            )
            graph.add_node(node)
            if index > 0:
                graph.add_edge(ShotGraphEdge(
                    src=intents[index - 1].shot_id, dst=intent.shot_id,
                    kind=intent.transition_intent,
                    rationale=f"{intent.function} after "
                              f"{intents[index - 1].function}"))
            incoming = outgoing
        return graph

    @staticmethod
    def _character_state(function: str) -> str:
        return {
            "ESTABLISH": "weary, walking",
            "DISCOVER": "alert, cautious",
            "PRESSURE": "hesitant, tense",
            "DECISION": "committed",
            "REVEAL": "shaken, reading",
            "PAYOFF": "resolute, quicker",
            "RESOLVE": "resolute, exiting",
        }.get(function, "consistent")
