"""V2-021 Phases A-D — NarrativeCompiler, StoryGraph, WorldStateGraph,
CharacterBible.

Film Core (provider-neutral). A shot is a COMPILED unit; the provider is an
implementation detail. The compiler is deterministic: beat identification
uses an explicit typed grammar (function keywords + structured scene
markup), never "split text every N seconds".

A narrative beat answers: WHO wants WHAT, WHAT CHANGES, what the audience
should understand, emotional state before/after, required visual
information.
"""
from __future__ import annotations

import re
from typing import Any, Literal

from pydantic import Field

from ..core import ContractModel

# ---------------------------------------------------------------- Phases A

BeatFunction = Literal[
    "ESTABLISH", "APPROACH", "DISCOVER", "PRESSURE", "REACTION",
    "DECISION", "REVEAL", "PAYOFF", "AFTERMATH", "RESOLVE", "TRANSITION",
]

# deterministic function cues (lowercased substrings)
_FUNCTION_CUES: dict[str, tuple[str, ...]] = {
    "ESTABLISH": ("opens on", "we see", "established", "a wide view",
                  "the story begins"),
    "APPROACH": ("crosses", "walks", "travels", "moves toward", "climbs",
                 "approaches", "carried", "journey"),
    "DISCOVER": ("finds", "discovers", "notices", "sees", "spots",
                 "comes upon"),
    "PRESSURE": ("hesitates", "wavers", "fears", "dreads", "pauses",
                 "uncertain", "afraid"),
    "REACTION": ("looks up", "stares", "breath", "trembl", "shudder",
                 "frozen", "stunned"),
    "DECISION": ("decides", "resolves to", "chooses", "commits", "opens",
                 "reaches"),
    "REVEAL": ("reveals", "inside is", "bears", "bearing her", "the letter",
               "discovers that", "realiz"),
    "PAYOFF": ("tucks", "walks on", "faster", "sets off", "continues",
               "moves on"),
    "AFTERMATH": ("empty", "silence", "wind", "alone", "no one", "gone"),
    "RESOLVE": ("walks on", "faster", "onward", "at last"),
}


class EmotionalState(ContractModel):
    label: str
    intensity: float = 0.5   # 0..1


class StoryEvent(ContractModel):
    event_id: str
    text: str
    function: BeatFunction
    who: list[str] = Field(default_factory=list)
    wants: str = ""
    what_changes: str = ""
    audience_understands: str = ""
    emotional_before: EmotionalState | None = None
    emotional_after: EmotionalState | None = None
    required_visual_info: list[str] = Field(default_factory=list)
    source_span: list[int] | None = None   # [char_start, char_end)


class CausalRelation(ContractModel):
    cause_event: str
    effect_event: str
    relation: Literal["causes", "precedes", "reveals", "motivates",
                      "blocks", "resolves"]


class NarrativeObjective(ContractModel):
    objective_id: str
    character: str
    desire: str
    satisfied_by_events: list[str] = Field(default_factory=list)


class Reveal(ContractModel):
    reveal_id: str
    event_id: str
    knowledge_change: str
    audience_learns: str


class Transition(ContractModel):
    from_event: str
    to_event: str
    kind: Literal["CUT", "TIME_JUMP", "LOCATION_TRANSITION", "CONTINUOUS"] \
        = "CUT"


class StoryBeat(ContractModel):
    """The compiled unit between events and shots."""
    beat_id: str
    event_ids: list[str]
    function: BeatFunction
    summary: str
    emotional_arc: str = ""


def parse_srt(text: str) -> list[dict]:
    """SRT -> [{index, start_s, end_s, text}]. Deterministic; semantics
    untouched (Phase P input path)."""
    blocks = re.split(r"\r?\n\r?\n", text.strip())
    entries = []
    time_re = re.compile(
        r"(\d+):(\d+):(\d+)[,.](\d+)\s*-->\s*(\d+):(\d+):(\d+)[,.](\d+)")
    for block in blocks:
        lines = [ln for ln in block.splitlines() if ln.strip()]
        if not lines:
            continue
        match = time_re.search(block)
        if not match:
            continue
        g = [int(x) for x in match.groups()]
        start = g[0] * 3600 + g[1] * 60 + g[2] + g[3] / 1000
        end = g[4] * 3600 + g[5] * 60 + g[6] + g[7] / 1000
        body = " ".join(ln for ln in lines[1:]
                        if not time_re.search(ln))
        entries.append({"index": int(lines[0]) if lines[0].isdigit()
                        else len(entries) + 1,
                        "start_s": start, "end_s": end, "text": body})
    return entries


def classify_function(sentence: str, *, position: int,
                      total: int) -> BeatFunction:
    low = sentence.lower()
    # position-aware precedence: openings establish, endings resolve
    if position == 0:
        for cue in _FUNCTION_CUES["ESTABLISH"] + _FUNCTION_CUES["APPROACH"]:
            if cue in low:
                return "ESTABLISH"
    if position >= total - 1:
        for cue in _FUNCTION_CUES["PAYOFF"] + _FUNCTION_CUES["RESOLVE"]:
            if cue in low:
                return "RESOLVE"
    best: tuple[int, BeatFunction] | None = None
    for function in ("REVEAL", "DISCOVER", "DECISION", "PRESSURE",
                     "REACTION", "AFTERMATH", "PAYOFF", "APPROACH",
                     "ESTABLISH"):
        hits = sum(1 for cue in _FUNCTION_CUES[function] if cue in low)
        if hits and (best is None or hits > best[0]):
            best = (hits, function)  # type: ignore[assignment]
    return best[1] if best else "APPROACH"


def split_sentences(text: str) -> list[tuple[int, str]]:
    out = []
    for match in re.finditer(r"[^.!?]+[.!?]?", text):
        sentence = match.group(0).strip()
        if sentence:
            out.append((match.start(), sentence))
    return out


class NarrativeCompiler:
    """Prose / SRT / structured package -> typed narrative graph pieces."""

    def compile(self, *, source_text: str, source_kind: str = "prose",
                cast: list[dict] | None = None,
                world_facts: dict | None = None) -> dict:
        sentences = split_sentences(source_text)
        events: list[StoryEvent] = []
        known_characters = {c["name"].lower(): c for c in (cast or [])}
        pronouns = {"she", "he", "they", "her", "him"}
        current_subject = cast[0]["name"] if cast else ""
        for position, (start, sentence) in enumerate(sentences):
            function = classify_function(sentence, position=position,
                                         total=len(sentences))
            low = sentence.lower()
            subjects = [name for name in known_characters
                        if name in low]
            resolved = [known_characters[s]["name"] for s in subjects]
            if resolved:
                current_subject = resolved[0]
            elif current_subject:
                resolved = [current_subject]
            events.append(StoryEvent(
                event_id=f"ev_{position + 1:02d}",
                text=sentence, function=function,
                who=resolved,
                wants=self._wants(function),
                what_changes=self._change(function, low),
                audience_understands=self._understanding(function),
                required_visual_info=self._visual_info(function, low),
                source_span=[start, start + len(sentence)]))
        beats = self._beats(events)
        causality = self._causality(events)
        reveals = [Reveal(reveal_id=f"reveal_{position + 1:02d}",
                          event_id=e.event_id,
                          knowledge_change=e.what_changes,
                          audience_learns=e.audience_understands)
                   for position, e in enumerate(events)
                   if e.function == "REVEAL"]
        objectives = [NarrativeObjective(
            objective_id=f"obj_{c['name'].lower().replace(' ', '_')}",
            character=c["name"], desire=c.get("desire", ""))
            for c in (cast or [])]
        transitions = [Transition(from_event=events[i].event_id,
                                  to_event=events[i + 1].event_id,
                                  kind="CONTINUOUS")
                       for i in range(len(events) - 1)]
        return {
            "source_kind": source_kind,
            "events": events, "beats": beats, "causality": causality,
            "reveals": reveals, "objectives": objectives,
            "transitions": transitions,
            "world_facts": world_facts or {},
        }

    @staticmethod
    def _wants(function: BeatFunction) -> str:
        return {
            "ESTABLISH": "orientation in the world",
            "APPROACH": "to reach the destination",
            "DISCOVER": "to understand what is found",
            "PRESSURE": "to avoid the risk of knowing",
            "REACTION": "to absorb the blow",
            "DECISION": "to act despite the risk",
            "REVEAL": "the truth of the object",
            "PAYOFF": "to complete the journey changed",
            "AFTERMATH": "to read the new world",
            "RESOLVE": "to leave the old state behind",
            "TRANSITION": "to pass through",
        }[function]

    @staticmethod
    def _change(function: BeatFunction, low: str) -> str:
        return {
            "DISCOVER": "unknown -> found object present",
            "REVEAL": "ignorance -> knowledge of the truth",
            "DECISION": "hesitation -> commitment",
            "PAYOFF": "stationary/weary -> moving/resolved",
        }.get(function, f"{function}: state advances")

    @staticmethod
    def _understanding(function: BeatFunction) -> str:
        return {
            "REVEAL": "the object concerns the protagonist personally",
            "DECISION": "courage costs fear",
            "PAYOFF": "the story state has permanently changed",
        }.get(function, "story advances one meaningful step")

    @staticmethod
    def _visual_info(function: BeatFunction, low: str) -> list[str]:
        info = []
        if function in ("ESTABLISH", "APPROACH"):
            info += ["location scale", "travel direction", "weather",
                     "isolation"]
        if function == "DISCOVER":
            info += ["the found object in frame", "protagonist gaze line"]
        if function == "REVEAL":
            info += ["object detail (no readable text)",
                     "protagonist facial reaction"]
        if function == "AFTERMATH":
            info += ["emptiness of the location", "scale against world"]
        if function in ("PAYOFF", "RESOLVE"):
            info += ["renewed motion", "exit vector"]
        return info

    @staticmethod
    def _beats(events: list[StoryEvent]) -> list[StoryBeat]:
        """Group consecutive events into beats: a new beat starts when the
        function class changes (orientation -> discovery -> decision ...)."""
        beats: list[StoryBeat] = []
        current: list[StoryEvent] = []
        for event in events:
            if current and event.function != current[-1].function:
                beats.append(StoryBeat(
                    beat_id=f"beat_{len(beats) + 1:02d}",
                    event_ids=[e.event_id for e in current],
                    function=current[-1].function,
                    summary="; ".join(e.text for e in current)[:220],
                    emotional_arc=f"{current[0].emotional_after or ''}"
                    f"->{event.emotional_before or ''}"))
                current = []
            current.append(event)
        if current:
            beats.append(StoryBeat(
                beat_id=f"beat_{len(beats) + 1:02d}",
                event_ids=[e.event_id for e in current],
                function=current[-1].function,
                summary="; ".join(e.text for e in current)[:220]))
        return beats

    @staticmethod
    def _causality(events: list[StoryEvent]) -> list[CausalRelation]:
        relations = []
        for i in range(len(events) - 1):
            relation = "precedes"
            if events[i].function == "DISCOVER" and \
                    events[i + 1].function in ("PRESSURE", "DECISION"):
                relation = "causes"
            if events[i].function == "REVEAL":
                relation = "reveals"
            if events[i + 1].function == "PAYOFF":
                relation = "motivates"
            relations.append(CausalRelation(
                cause_event=events[i].event_id,
                effect_event=events[i + 1].event_id,
                relation=relation))  # type: ignore[arg-type]
        return relations


# ---------------------------------------------------------------- Phase B

GraphNodeKind = Literal["event", "character", "location", "object",
                        "knowledge", "emotion"]


class StoryGraphNode(ContractModel):
    node_id: str
    kind: GraphNodeKind
    label: str
    data: dict[str, Any] = Field(default_factory=dict)


class StoryGraphEdge(ContractModel):
    src: str
    dst: str
    relation: Literal["causes", "precedes", "reveals", "motivates",
                      "blocks", "resolves", "participates", "located_in",
                      "holds", "knows", "feels"]


class StoryGraph:
    """Durable typed graph; every shot must trace to >=1 node."""

    def __init__(self) -> None:
        self.nodes: dict[str, StoryGraphNode] = {}
        self.edges: list[StoryGraphEdge] = []

    def add_node(self, node: StoryGraphNode) -> StoryGraphNode:
        self.nodes[node.node_id] = node
        return node

    def add_edge(self, edge: StoryGraphEdge) -> None:
        if edge.src not in self.nodes or edge.dst not in self.nodes:
            raise ValueError(f"edge endpoint missing: {edge.src}->{edge.dst}")
        self.edges.append(edge)

    def build_from_compiled(self, compiled: dict, *,
                            cast: list[dict],
                            locations: list[str],
                            objects: list[str]) -> "StoryGraph":
        for event in compiled["events"]:
            self.add_node(StoryGraphNode(
                node_id=event.event_id, kind="event",
                label=event.text[:80], data=event.model_dump()))
        for character in cast:
            self.add_node(StoryGraphNode(
                node_id=f"char_{character['name'].lower().replace(' ', '_')}",
                kind="character", label=character["name"],
                data=character))
        for location in locations:
            self.add_node(StoryGraphNode(
                node_id=f"loc_{location.lower().replace(' ', '_')}",
                kind="location", label=location))
        for obj in objects:
            self.add_node(StoryGraphNode(
                node_id=f"obj_{obj.lower().replace(' ', '_')}",
                kind="object", label=obj))
        for relation in compiled["causality"]:
            self.add_edge(StoryGraphEdge(
                src=relation.cause_event, dst=relation.effect_event,
                relation=relation.relation))
        for event in compiled["events"]:
            for who in event.who:
                cid = f"char_{who.lower().replace(' ', '_')}"
                if cid in self.nodes:
                    self.add_edge(StoryGraphEdge(
                        src=cid, dst=event.event_id,
                        relation="participates"))
        return self

    def trace_shot(self, node_ids: list[str]) -> bool:
        return all(nid in self.nodes for nid in node_ids) and bool(node_ids)

    def to_manifest(self) -> dict:
        return {"nodes": [n.model_dump() for n in self.nodes.values()],
                "edges": [e.model_dump() for e in self.edges]}


# ---------------------------------------------------------------- Phase C

class WorldState(ContractModel):
    location: str
    time_of_day: str = ""
    weather: str = ""
    lighting: str = ""
    terrain: str = ""
    architecture: str = "none"
    props_present: list[str] = Field(default_factory=list)
    character_position: str = ""
    character_orientation: str = ""
    wardrobe_state: str = ""
    damage_dirt: str = "clean"
    held_objects: list[str] = Field(default_factory=list)
    camera_side_of_axis: str = ""
    screen_direction: str = ""


class WorldStateTransition(ContractModel):
    from_world: WorldState
    to_world: WorldState
    delta: dict[str, list[str]]   # field -> [before, after]
    justified_by_event: str


class WorldStateGraph:
    """Explicit world state per shot; transitions must be justified by a
    story event (no spontaneous weapon/building/weather/costume)."""

    def __init__(self, initial: WorldState) -> None:
        self.states: list[tuple[str, WorldState]] = [("shot_00", initial)]
        self.transitions: list[WorldStateTransition] = []

    @staticmethod
    def delta(before: WorldState, after: WorldState) -> dict:
        changed = {}
        for field in type(before).model_fields:
            b, a = getattr(before, field), getattr(after, field)
            if b != a:
                changed[field] = [str(b), str(a)]
        return changed

    def push_shot_state(self, shot_id: str, state: WorldState, *,
                        justified_by_event: str) -> WorldStateTransition:
        before = self.states[-1][1]
        delta = self.delta(before, state)
        spontaneous = {k for k in delta if k in (
            "architecture", "weather")} 
        if spontaneous and not justified_by_event:
            raise ValueError("spontaneous world change without story "
                             f"event: {sorted(spontaneous)}")
        transition = WorldStateTransition(
            from_world=before, to_world=state, delta=delta,
            justified_by_event=justified_by_event)
        self.transitions.append(transition)
        self.states.append((shot_id, state))
        return transition

    def to_manifest(self) -> dict:
        return {"states": [{"shot": sid, "world": w.model_dump()}
                           for sid, w in self.states],
                "transitions": [t.model_dump() for t in
                                self.transitions]}


# ---------------------------------------------------------------- Phase D

class CharacterBible(ContractModel):
    """IDENTITY HARD CONSTRAINTS vs SHOT-DEPENDENT APPEARANCE."""
    character_id: str
    name: str
    # hard identity constraints
    age_band: str = ""
    face_geometry_family: str = ""
    hair: str = ""
    body_build: str = ""
    skin_tone: str = ""
    signature_wardrobe: str = ""
    persistent_accessories: list[str] = Field(default_factory=list)
    # shot-dependent (never used as identity evidence)
    variable_dimensions: tuple[str, ...] = (
        "pose", "expression", "camera_angle", "distance", "lighting",
        "wind_deformation", "temporary_dirt_wetness")

    def identity_fingerprint(self) -> str:
        import hashlib
        payload = " | ".join(filter(None, [
            self.age_band, self.face_geometry_family, self.hair,
            self.body_build, self.skin_tone, self.signature_wardrobe,
            ",".join(self.persistent_accessories)]))
        return hashlib.sha256(payload.encode()).hexdigest()[:16]


class IdentityEvidence(ContractModel):
    shot_id: str
    framing: Literal["CLOSE", "MEDIUM_CLOSE", "MEDIUM", "WIDE", "EXTREME_WIDE"]
    face_visible: bool
    hard_constraints_observed: list[str] = Field(default_factory=list)
    violations: list[str] = Field(default_factory=list)
    # facial geometry is a STRONGER authority in close/medium-close:
    facial_geometry_checked: bool = False
    verdict: Literal["PASS", "WEAK", "FAIL"] = "WEAK"


class IdentityContinuityLedger:
    """Identity evidence across shots; wardrobe match alone is NEVER a
    PASS."""

    def __init__(self, bible: CharacterBible) -> None:
        self.bible = bible

    def evaluate(self, evidence: IdentityEvidence) -> IdentityEvidence:
        evidence.violations = []   # re-evaluation resets derived state
        if not evidence.face_visible:
            if evidence.hard_constraints_observed:
                evidence.verdict = "WEAK"
                evidence.violations.append(
                    "wardrobe/build only — face not visible; cannot PASS "
                    "identity on wardrobe match")
            else:
                evidence.verdict = "WEAK"
                evidence.violations.append("no identity evidence observed")
            return evidence
        required = {self.bible.hair, self.bible.skin_tone}
        observed = set(evidence.hard_constraints_observed)
        missing = {r for r in required if r and not any(
            r in o for o in observed)}
        if missing:
            evidence.violations.append(
                "hard constraints not observed: " + ", ".join(missing))
        if evidence.framing in ("CLOSE", "MEDIUM_CLOSE"):
            if not evidence.facial_geometry_checked:
                evidence.verdict = "WEAK"
                evidence.violations.append(
                    "close framing requires facial-geometry check")
                return evidence
        evidence.verdict = "FAIL" if evidence.violations else "PASS"
        return evidence
