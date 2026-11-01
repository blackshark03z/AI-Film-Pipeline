"""Audience comprehension: what the viewer must know, and what tells them.

film02: an older woman sat in the family kitchen and viewers read her as
the mother; "AUNT ROSA" and the mother's death lived only in action lines,
so "Your mother changed the locks" read as the mother talking about
herself. A fact the story depends on (who someone is, a death, a time
jump) must reach the screen -- by dialogue, picture, an identity tag or a
context card -- no later than the first generation that needs it.

Run on the plan before generation (a line of dialogue is the best carrier
and is free at script time) and again on the post plan, where identity
tags and context cards are the 0-credit fix. Reading time follows one rule
for every on-screen text: ``lead_s + chars / chars_per_s``, clamped.
"""
from __future__ import annotations

import re
from pathlib import Path
from typing import Literal

from pydantic import Field

from ..core import ContractModel
from .post import Overlay, SubtitleCue, identity_tag_png
from .scene_bible import RuleIssue
from .script import Script

CarrierKind = Literal["DIALOGUE", "VISUAL", "TAG", "CARD"]


class ReadingLimits(ContractModel):
    chars_per_s: float = 15.0        # comfortable for short on-screen text
    lead_s: float = 0.5              # time to find the text
    min_s: float = 2.0
    max_s: float = 3.0
    max_lines: int = 2
    max_line_chars: int = 42


def read_time(lines: list[str], limits: ReadingLimits = ReadingLimits()
              ) -> float:
    """Unclamped above: a result over ``max_s`` means the text is too long."""
    chars = sum(len(line.strip()) for line in lines)
    return round(max(limits.min_s, limits.lead_s + chars / limits.chars_per_s),
                 1)


class Carrier(ContractModel):
    kind: CarrierKind
    generation_id: str               # CARD: the generation it is cut before
    detail: str = ""                 # the line, the picture, the card text


class StoryFact(ContractModel):
    fact_id: str
    text: str                        # what the viewer must know
    needed_by: str                   # first generation that depends on it
    carriers: list[Carrier] = Field(default_factory=list)


class CharacterIntro(ContractModel):
    character: str
    label: str                       # on-screen name, e.g. "ROSA"
    relation: str                    # e.g. "their late mother's sister"
    needed_by: str = ""              # default: first generation in frame
    carriers: list[Carrier] = Field(default_factory=list)   # non-tag ones

    @property
    def lines(self) -> list[str]:
        return [self.label, self.relation]


class IdentityTag(ContractModel):
    character: str
    generation_id: str
    start_s: float                   # clip-relative
    end_s: float
    # tag centre / tag top as frame fractions, beside the face; None:
    # tag_layout.auto_place finds the face and fills them
    anchor_x: float | None = Field(default=None, ge=0.0, le=1.0)
    anchor_y: float | None = Field(default=None, ge=0.0, le=1.0)


class ContextCard(ContractModel):
    card_id: str
    before: str                      # generation the card is cut in front of
    lines: list[str]
    duration_s: float | None = None  # default: read_time(lines)

    def duration(self, limits: ReadingLimits = ReadingLimits()) -> float:
        return self.duration_s or min(limits.max_s, read_time(self.lines,
                                                              limits))


def _issue(check: str, detail: str, severity: str = "BLOCK") -> RuleIssue:
    return RuleIssue(check=check, severity=severity, detail=detail)


def check_comprehension(timeline: list[str],
                        in_frame: dict[str, list[str]],
                        intros: list[CharacterIntro],
                        facts: list[StoryFact] = (),
                        tags: list[IdentityTag] = (),
                        cards: list[ContextCard] = (),
                        cues: list[SubtitleCue] = (),
                        limits: ReadingLimits = ReadingLimits()
                        ) -> list[RuleIssue]:
    """``timeline``: generation ids in cut order; ``in_frame``: visible
    characters per generation. Every visible character needs an intro, and
    every intro and fact a carrier no later than its ``needed_by``."""
    pos = {g: float(i) for i, g in enumerate(timeline)}
    issues: list[RuleIssue] = []

    def where(c: Carrier) -> float | None:
        p = pos.get(c.generation_id)
        return None if p is None else p - 0.5 if c.kind == "CARD" else p

    def carried(what: str, needed: str, carriers: list[Carrier]) -> None:
        if needed not in pos:
            issues.append(_issue("UNKNOWN_GENERATION",
                                 f"{what}: needed_by {needed!r}"))
            return
        for c in carriers:
            if where(c) is None:
                issues.append(_issue("UNKNOWN_GENERATION",
                                     f"{what}: carrier {c.generation_id!r}"))
        if not any(where(c) is not None and where(c) <= pos[needed]
                   for c in carriers):
            issues.append(_issue(
                "FACT_UNCARRIED",
                f"{what}: nothing tells the viewer by {needed} (add a line, "
                "a picture, an identity tag or a context card)"))

    first_seen: dict[str, str] = {}
    for g in timeline:
        for who in in_frame.get(g, []):
            first_seen.setdefault(who, g)
    by_char = {i.character: i for i in intros}
    for who, g in first_seen.items():
        if who not in by_char:
            issues.append(_issue("IDENTITY_UNDECLARED",
                                 f"{who} is on screen from {g} with no "
                                 "CharacterIntro (who are they to the "
                                 "story?)"))
    for intro in intros:
        own = [Carrier(kind="TAG", generation_id=t.generation_id)
               for t in tags if t.character == intro.character]
        needed = intro.needed_by or first_seen.get(intro.character, "")
        if needed:
            carried(f"who is {intro.character}", needed,
                    intro.carriers + own)
    for fact in facts:
        carried(fact.fact_id, fact.needed_by, fact.carriers)

    for k, t in enumerate(tags):
        intro = by_char.get(t.character)
        if t.character not in in_frame.get(t.generation_id, []):
            issues.append(_issue("TAG_OFF_SCREEN",
                                 f"{t.character} tag on {t.generation_id}, "
                                 "where they are not in frame"))
        if intro and t.end_s - t.start_s + 1e-6 < read_time(intro.lines,
                                                            limits):
            issues.append(_issue(
                "TAG_TOO_SHORT",
                f"{t.character} tag {t.end_s - t.start_s:.1f} s < "
                f"{read_time(intro.lines, limits)} s to read"))
        for u in tags[k + 1:]:
            if (u.generation_id == t.generation_id and u.start_s < t.end_s
                    and t.start_s < u.end_s):
                issues.append(_issue("TAG_OVERLAP",
                                     f"{t.character} and {u.character} tags "
                                     f"overlap on {t.generation_id}"))
        for c in cues:
            if (c.generation_id == t.generation_id and c.start_s < t.end_s
                    and t.start_s < c.end_s):
                issues.append(_issue("TAG_OVER_DIALOGUE",
                                     f"{t.character} tag runs over "
                                     f"{c.text!r}", "WARN"))
    for card in cards:
        if card.before not in pos:
            issues.append(_issue("UNKNOWN_GENERATION",
                                 f"card {card.card_id}: before "
                                 f"{card.before!r}"))
        if len(card.lines) > limits.max_lines or any(
                len(line) > limits.max_line_chars for line in card.lines):
            issues.append(_issue("CARD_TOO_LONG",
                                 f"card {card.card_id}: at most "
                                 f"{limits.max_lines} lines of "
                                 f"{limits.max_line_chars} characters"))
        need = read_time(card.lines, limits)
        if need > limits.max_s:
            issues.append(_issue("CARD_TOO_LONG",
                                 f"card {card.card_id} needs {need} s to "
                                 f"read (max {limits.max_s} s)"))
        if not limits.min_s <= card.duration(limits) <= limits.max_s:
            issues.append(_issue("CARD_DURATION",
                                 f"card {card.card_id}: "
                                 f"{card.duration(limits)} s outside "
                                 f"{limits.min_s}-{limits.max_s} s"))
    return issues


def screen_text_cues(offsets: dict[str, float], cards: list[ContextCard],
                     tags: list[IdentityTag], intros: list[CharacterIntro],
                     tr: dict[str, str] | None = None,
                     limits: ReadingLimits = ReadingLimits()
                     ) -> list[tuple[float, float, str]]:
    """Cards and identity tags as sidecar cues on the final timeline
    (``offsets`` from ``post.cue_offsets``; card clips are keyed by
    card_id). ``tr`` translates every text; a missing entry raises, so no
    untranslated line reaches a translated sidecar."""
    def t(text: str) -> str:
        if tr is None:
            return text
        if text not in tr:
            raise KeyError(f"no translation for {text!r}")
        return tr[text]
    by_char = {i.character: i for i in intros}
    out = [(offsets[c.card_id], offsets[c.card_id] + c.duration(limits),
            "\n".join(t(line) for line in c.lines)) for c in cards]
    for tag in tags:
        intro = by_char[tag.character]
        out.append((offsets[tag.generation_id] + tag.start_s,
                    offsets[tag.generation_id] + tag.end_s,
                    f"{intro.label} – {t(intro.relation)}"))
    return out


def tag_overlays(tags: list[IdentityTag], intros: list[CharacterIntro],
                 out_dir: Path) -> list[Overlay]:
    """Render one PNG per tag for ``post.assemble(overlays=...)``."""
    by_char = {i.character: i for i in intros}
    out = []
    for k, t in enumerate(tags, 1):
        intro = by_char[t.character]
        if t.anchor_x is None or t.anchor_y is None:
            raise ValueError(f"{t.character} tag on {t.generation_id} has "
                             "no anchor (run tag_layout.auto_place)")
        png = identity_tag_png(out_dir / f"tag_{k:02}.png", intro.label,
                               intro.relation, t.anchor_x, t.anchor_y)
        out.append(Overlay(generation_id=t.generation_id, start_s=t.start_s,
                           end_s=t.end_s, png=str(png)))
    return out


# ------------------------------------------------------- script stage

# kinship words -> root; a root heard in dialogue names a person the viewer
# must be able to place (film02: "Mom" / "your mother", never on screen)
KIN = {w: root for root, words in {
    "mother": ["mother", "mom", "mum", "mama", "mommy"],
    "father": ["father", "dad", "daddy", "papa"],
    "brother": ["brother"], "sister": ["sister"],
    "aunt": ["aunt", "auntie"], "uncle": ["uncle"],
    "son": ["son"], "daughter": ["daughter"],
    "wife": ["wife"], "husband": ["husband"],
    "grandmother": ["grandmother", "grandma", "granny"],
    "grandfather": ["grandfather", "grandpa"],
    "cousin": ["cousin"], "niece": ["niece"], "nephew": ["nephew"],
}.items() for w in words}


def kin_roots(text: str) -> set[str]:
    return {KIN[w] for w in re.findall(r"[a-z]+", text.lower()) if w in KIN}


def lint_script(script: Script, intros: list[CharacterIntro],
                facts: list[StoryFact] = ()) -> list[RuleIssue]:
    """Script-stage check, before any generation: every speaker has an
    intro, and every family member named in dialogue is placed for the
    viewer by an intro relation or a declared fact. The hint quotes the
    action line that described the character, which the viewer never
    reads."""
    known = set().union(*(kin_roots(i.relation) for i in intros),
                        *(kin_roots(f.text) for f in facts))
    declared = {i.character for i in intros}
    issues: list[RuleIssue] = []
    seen: set[str] = set()
    for scene in script.scenes:
        actions = [e.text for e in scene.elements if e.kind == "action"]
        for e in scene.elements:
            if e.kind != "dialogue":
                continue
            who = e.character
            if who not in declared and who not in seen:
                seen.add(who)
                said = next((a for a in actions if who in a.upper()), "")
                hint = f' (action line: "{said[:80]}")' if said else ""
                issues.append(_issue(
                    "IDENTITY_UNDECLARED",
                    f"{who} speaks in {scene.scene_id} with no "
                    f"CharacterIntro{hint}"))
            for root in sorted(kin_roots(e.text) - known):
                issues.append(_issue(
                    "OFFSCREEN_PERSON",
                    f"{who} names a {root} in {scene.scene_id} "
                    f"({e.text!r}): declare who that is with a StoryFact "
                    "and a carrier"))
    return issues
