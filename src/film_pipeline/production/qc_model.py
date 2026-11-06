"""Take QC record (categories 131-146): sixteen QC groups per take, severity P0/P1/P2, review level, evidence, reviewer.

One `TakeQc` per rendered take holds one `GroupCheck` per QC group:

* ``result``   PASS / FAIL / WARN / UNASSESSED (a group nobody looked at stays UNASSESSED - never an implicit pass)
* ``severity`` P0 (the take is unusable) / P1 (must be fixed or knowingly waived) / P2 (noted); required on FAIL
* ``level``    what was actually looked at: STILL < SAMPLED (frames) < FULL_MOTION (the whole clip) < CUT (in sequence)
* ``evidence`` path of the sheet / frame / log the verdict rests on; ``reviewer`` `human:<id>` or `auto:<tool>`

Who may say what (enforced when a record is built, so a hand-edited JSON cannot cheat):

* Content groups (narrative, coverage, character, spatial, action, motion, camera, visual, temporal, sequence,
  compliance) cannot be passed or failed by an `auto:` tool - it may only WARN or leave the group UNASSESSED. Only a
  `human:` review can PASS them, and only at the minimum level the group needs (a still cannot prove motion).
* Machine groups (audio, sync, color, technical, delivery) may be PASSed or FAILed by an auto tool.
* A P1 FAIL can be waived by a human with a written reason; a P0 FAIL can never be waived.

Verdict (`TakeQc.verdict`): REJECTED when any P0 FAIL or an unwaived P1 FAIL; otherwise INCOMPLETE while any required
group is UNASSESSED, WARN, or missing; otherwise ACCEPTED. The take-level required groups are `TAKE_GROUPS`; coverage,
sequence, color, compliance and delivery are judged on the cut / master, not on a single take. ACCEPTED means the
declared checks hold, not that the Owner accepts the footage.
"""
from __future__ import annotations

from typing import Any, Literal

from pydantic import Field, model_validator

from film_pipeline.core import ContractModel

Group = Literal["narrative", "coverage", "character", "spatial", "action", "motion", "camera", "visual", "temporal",
                "sequence", "audio", "sync", "color", "technical", "compliance", "delivery"]
Result = Literal["PASS", "FAIL", "WARN", "UNASSESSED"]
Severity = Literal["P0", "P1", "P2"]
Level = Literal["STILL", "SAMPLED", "FULL_MOTION", "CUT"]
Status = Literal["ACCEPTED", "REJECTED", "INCOMPLETE"]

GROUP_NUMBERS: dict[str, int] = {g: 131 + i for i, g in enumerate((
    "narrative", "coverage", "character", "spatial", "action", "motion", "camera", "visual", "temporal", "sequence",
    "audio", "sync", "color", "technical", "compliance", "delivery"))}
MACHINE_GROUPS = frozenset({"audio", "sync", "color", "technical", "delivery"})
CONTENT_GROUPS = frozenset(GROUP_NUMBERS) - MACHINE_GROUPS
TAKE_GROUPS = ("narrative", "character", "spatial", "action", "motion", "camera", "visual", "temporal", "audio", "sync",
               "technical")
_LEVEL_ORDER = {"STILL": 0, "SAMPLED": 1, "FULL_MOTION": 2, "CUT": 3}
MIN_LEVEL: dict[str, str] = {
    "narrative": "SAMPLED", "coverage": "CUT", "character": "SAMPLED", "spatial": "SAMPLED", "action": "FULL_MOTION",
    "motion": "FULL_MOTION", "camera": "SAMPLED", "visual": "SAMPLED", "temporal": "FULL_MOTION", "sequence": "CUT",
    "audio": "FULL_MOTION", "sync": "FULL_MOTION", "color": "SAMPLED", "technical": "FULL_MOTION", "compliance": "STILL",
    "delivery": "STILL"}
_REVIEWER = r"^(?:$|(?:human|auto):[A-Za-z0-9_.\-]+)$"


class Waiver(ContractModel):
    reason: str = Field(min_length=3)
    by: str = Field(pattern=r"^human:[A-Za-z0-9_.\-]+$")


class GroupCheck(ContractModel):
    group: Group
    result: Result = "UNASSESSED"
    severity: Severity | None = None
    level: Level | None = None
    evidence: str = ""
    reviewer: str = Field(default="", pattern=_REVIEWER)
    note: str = ""
    waiver: Waiver | None = None

    @property
    def number(self) -> int:
        return GROUP_NUMBERS[self.group]

    @property
    def by_human(self) -> bool:
        return self.reviewer.startswith("human:")

    @model_validator(mode="after")
    def _rules(self) -> "GroupCheck":
        g = f"QC group {self.group} ({self.number})"
        if self.result == "UNASSESSED":
            if self.severity or self.waiver:
                raise ValueError(f"{g}: UNASSESSED carries no severity or waiver")
            return self
        if not (self.evidence.strip() and self.reviewer and self.level):
            raise ValueError(f"{g}: {self.result} needs evidence, reviewer and level")
        if self.result == "FAIL" and self.severity is None:
            raise ValueError(f"{g}: FAIL needs a severity (P0/P1/P2)")
        if self.result == "PASS" and self.severity is not None:
            raise ValueError(f"{g}: PASS has no severity")
        if self.waiver is not None and not (self.result == "FAIL" and self.severity == "P1"):
            raise ValueError(f"{g}: only a P1 FAIL can be waived (P0 never)")
        if self.group in CONTENT_GROUPS and not self.by_human and self.result in ("PASS", "FAIL"):
            raise ValueError(f"{g}: an auto tool may only WARN or leave a content group UNASSESSED, not {self.result}")
        if self.result == "PASS" and _LEVEL_ORDER[self.level] < _LEVEL_ORDER[MIN_LEVEL[self.group]]:
            raise ValueError(f"{g}: a PASS needs level {MIN_LEVEL[self.group]} or higher, got {self.level}")
        return self

    @property
    def waived(self) -> bool:
        return self.waiver is not None


class Verdict(ContractModel):
    status: Status
    p0: list[str] = Field(default_factory=list)
    p1_unwaived: list[str] = Field(default_factory=list)
    p1_waived: list[str] = Field(default_factory=list)
    p2: list[str] = Field(default_factory=list)
    open_groups: list[str] = Field(default_factory=list)  # required groups still UNASSESSED / WARN / missing
    reasons: list[str] = Field(default_factory=list)


class TakeQc(ContractModel):
    take_id: str = Field(min_length=1)
    generation_id: str = Field(min_length=1)
    checks: list[GroupCheck] = Field(default_factory=list)

    @model_validator(mode="after")
    def _one_check_per_group(self) -> "TakeQc":
        seen = [c.group for c in self.checks]
        dup = sorted({g for g in seen if seen.count(g) > 1})
        if dup:
            raise ValueError(f"take {self.take_id}: more than one check for {dup}")
        return self

    def check(self, group: str) -> GroupCheck:
        return next((c for c in self.checks if c.group == group), GroupCheck(group=group))  # type: ignore[arg-type]

    def verdict(self) -> Verdict:
        p0, p1u, p1w, p2 = [], [], [], []
        for c in self.checks:
            if c.result != "FAIL":
                continue
            label = f"{c.group}({c.number})"
            if c.severity == "P0":
                p0.append(label)
            elif c.severity == "P1":
                (p1w if c.waived else p1u).append(label)
            else:
                p2.append(label)
        open_groups = [g for g in TAKE_GROUPS if self.check(g).result in ("UNASSESSED", "WARN")]
        reasons = [f"P0 FAIL: {', '.join(p0)}"] if p0 else []
        reasons += [f"P1 FAIL not waived: {', '.join(p1u)}"] if p1u else []
        if p0 or p1u:
            status: Status = "REJECTED"
        elif open_groups:
            status = "INCOMPLETE"
            reasons.append(f"not yet judged: {', '.join(open_groups)}")
        else:
            status = "ACCEPTED"
        return Verdict(status=status, p0=p0, p1_unwaived=p1u, p1_waived=p1w, p2=p2, open_groups=open_groups,
                       reasons=reasons)


def auto_check(group: str, tool: str, *, ok: bool, evidence: str, level: Level, note: str = "",
               severity: Severity = "P1") -> GroupCheck:
    """The only way an automatic tool should write a check: content groups are downgraded to WARN / UNASSESSED."""
    reviewer = f"auto:{tool}"
    if group in CONTENT_GROUPS:
        if ok:  # "no concern found" is not a verdict on story, acting or motion
            return GroupCheck(group=group, result="UNASSESSED", note=note or f"{tool}: no concern found")  # type: ignore[arg-type]
        return GroupCheck(group=group, result="WARN", evidence=evidence, reviewer=reviewer, level=level, note=note,  # type: ignore[arg-type]
                          severity=None)
    return GroupCheck(group=group, result="PASS" if ok else "FAIL", evidence=evidence, reviewer=reviewer,  # type: ignore[arg-type]
                      level=level, note=note, severity=None if ok else severity)


def blank_take(take_id: str, generation_id: str) -> TakeQc:
    """A review template: every take-level group UNASSESSED, waiting for a reviewer."""
    return TakeQc(take_id=take_id, generation_id=generation_id,
                  checks=[GroupCheck(group=g) for g in TAKE_GROUPS])  # type: ignore[arg-type]


def verdict_report(take: TakeQc) -> dict[str, Any]:
    v = take.verdict()
    return {"take_id": take.take_id, "generation_id": take.generation_id, **v.model_dump(mode="json"),
            "groups": {f"{c.number}:{c.group}": {"result": c.result, "severity": c.severity, "level": c.level,
                                                  "reviewer": c.reviewer, "waived": c.waived}
                       for c in take.checks}}
