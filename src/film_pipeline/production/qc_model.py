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

Evidence version 2 (``TakeQc.evidence_version``, set per film by ``film.json`` ``qc_evidence_version``; older records
stay version 1 and validate exactly as before): a judged check must say what was actually examined in ``observed``
(frames viewed, whether the clip was watched in full motion in real time, whether the audio was heard). FULL_MOTION / CUT
needs a full playback or every frame counted; SAMPLED needs at least one frame viewed; only a ``human:`` reviewer can have
watched in real time or listened, so an ``agent:`` reviewer counts frames and leaves audio / sync verdicts to ``auto:``
machine checks; a PASS on audio or sync by a human / agent needs ``audio_listened``; and a FULL_MOTION / CUT level whose
evidence or note admits "contact strip" / "sampled frames only" / "not listened" is a contradiction (it was SAMPLED).

Reviewed defects (``TakeQc.defects``, optional): what a REJECT actually found, as a code from ``production.defects`` plus
the clip hash and time ranges judged, optionally citing the detector signal that prompted the look (``source_signal``; the
registry says which signal codes may be confirmed into which defect). ``takes.ingest_review`` refuses a defect whose
``clip_sha256`` is not the reviewed take's bytes. A REJECTED review with evidence_version 2 must carry at least one; older
records and reviews without defects stay valid and load unchanged.
"""
from __future__ import annotations

import re
from typing import Any, Literal

from pydantic import Field, model_validator

from film_pipeline.core import ContractModel

Group = Literal["narrative", "coverage", "character", "spatial", "action", "motion", "camera", "visual", "temporal",
                "sequence", "audio", "sync", "color", "technical", "compliance", "delivery"]
Result = Literal["PASS", "FAIL", "WARN", "UNASSESSED"]
Severity = Literal["P0", "P1", "P2"]
Level = Literal["STILL", "SAMPLED", "FULL_MOTION", "CUT"]
Status = Literal["ACCEPTED", "REJECTED", "INCOMPLETE"]
Cause = Literal["PROMPT", "START_FRAME", "PROVIDER_LIMIT", "STAGING"]  # what to change before trying again

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
_ANSWER_GROUP = {"REL_ADDRESS": "narrative"}  # question-id prefix -> QC group (default spatial)
# agent:<name> = an AI reviewer the Owner delegated judgment to (film04, 2026-11-09: "Bạn tự duyệt still, board và
# take (ký là agent:tech-lead, ủy quyền của mình)"); it may judge content groups like a human, auto: tools still may not
_REVIEWER = r"^(?:$|(?:human|agent|auto):[A-Za-z0-9_.\-]+)$"


def answer_group(question_id: str) -> str:
    return _ANSWER_GROUP.get(question_id.split(":")[0], "spatial")


class Waiver(ContractModel):
    reason: str = Field(min_length=3)
    by: str = Field(pattern=r"^human:[A-Za-z0-9_.\-]+$")


_SAMPLED_ADMISSION = re.compile(r"not listened|sampled frames only|\b\d+-frame (?:contact )?strip|contact strip",
                                re.IGNORECASE)


class Observation(ContractModel):
    """What the reviewer actually examined (evidence version 2)."""

    frames_viewed: int = Field(ge=0)
    frames_total: int | None = Field(default=None, ge=1)
    full_playback: bool = False  # the whole clip watched in motion in real time
    audio_listened: bool = False  # the audio was actually heard, not only measured


class SourceSignal(ContractModel):
    """The detector signal a reviewer looked at before confirming a defect (the signal itself is only a suspicion)."""

    detector: str = Field(min_length=1)
    detector_version: str = Field(min_length=1)
    code: str = Field(min_length=1)


class ReviewedDefect(ContractModel):
    """A defect a reviewer confirmed on this clip: bound to the clip bytes and the time ranges that were judged."""

    code: str
    clip_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    time_ranges: list[tuple[float, float]] = Field(min_length=1)  # seconds [start, end] in this clip
    note: str = ""
    source_signal: SourceSignal | None = None

    @model_validator(mode="after")
    def _rules(self) -> "ReviewedDefect":
        from film_pipeline.production.defects import DEFECTS, signal_may_confirm
        if self.code not in DEFECTS:
            raise ValueError(f"unknown defect code {self.code!r}; reviewed codes: {', '.join(sorted(DEFECTS))}")
        for t0, t1 in self.time_ranges:
            if not (0 <= t0 < t1):
                raise ValueError(f"defect {self.code}: time range [{t0}, {t1}] must satisfy 0 <= start < end")
        if self.source_signal is not None and not signal_may_confirm(self.code, self.source_signal.code):
            raise ValueError(f"defect {self.code} cannot be confirmed from detector signal {self.source_signal.code!r} "
                             f"(allowed: {', '.join(DEFECTS[self.code].confirms_signals) or 'none'})")
        return self


class GroupCheck(ContractModel):
    group: Group
    result: Result = "UNASSESSED"
    severity: Severity | None = None
    level: Level | None = None
    evidence: str = ""
    reviewer: str = Field(default="", pattern=_REVIEWER)
    note: str = ""
    waiver: Waiver | None = None
    answers: dict[str, str] = Field(default_factory=dict)  # review question id -> the reviewer's short answer / evidence
    observed: Observation | None = None  # required on judged checks of an evidence_version >= 2 record

    @property
    def number(self) -> int:
        return GROUP_NUMBERS[self.group]

    @property
    def by_human(self) -> bool:
        """A judging reviewer: a human, or an agent the Owner delegated review to."""
        return self.reviewer.startswith(("human:", "agent:"))

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
    cause: Cause | None = None  # why a REJECTED take failed; retake.py decides the next move from it
    cause_note: str = ""
    required_answers: list[str] = Field(default_factory=list)  # question ids a human must answer before ACCEPTED
    evidence_version: int = 1  # >= 2: every judged check states what was examined (`observed`), see the module docstring
    defects: list[ReviewedDefect] = Field(default_factory=list)  # reviewed defects (production.defects); required on a v2 REJECT

    @model_validator(mode="after")
    def _defect_rules(self) -> "TakeQc":
        if self.evidence_version >= 2 and not self.defects and self.verdict().status == "REJECTED":
            raise ValueError(f"take {self.take_id}: a REJECTED review with evidence_version {self.evidence_version} must carry "
                             f"at least one reviewed defect (`defects`: code, clip_sha256, time_ranges)")
        return self

    @model_validator(mode="after")
    def _observed_rules(self) -> "TakeQc":
        if self.evidence_version < 2:
            return self
        for c in self.checks:
            if c.result == "UNASSESSED" or not c.by_human:
                continue
            g = f"take {self.take_id}: QC group {c.group} ({c.number})"
            ob = c.observed
            if ob is None:
                raise ValueError(f"{g}: evidence_version {self.evidence_version} requires `observed` "
                                 f"(frames viewed / full playback / audio listened) on every judged check")
            if c.level in ("FULL_MOTION", "CUT") and not (
                    ob.full_playback or (ob.frames_total is not None and ob.frames_viewed >= ob.frames_total)):
                raise ValueError(f"{g}: level {c.level} needs full_playback or every frame viewed "
                                 f"(frames_viewed {ob.frames_viewed} of frames_total {ob.frames_total}); otherwise use SAMPLED")
            if c.level == "SAMPLED" and ob.frames_viewed < 1:
                raise ValueError(f"{g}: level SAMPLED needs frames_viewed >= 1")
            if (ob.full_playback or ob.audio_listened) and not c.reviewer.startswith("human:"):
                raise ValueError(f"{g}: only a human: reviewer can claim full_playback or audio_listened "
                                 f"(reviewer {c.reviewer}); an agent counts frames and leaves audio / sync to auto: tools")
            if c.group in ("audio", "sync") and c.result == "PASS" and not ob.audio_listened:
                raise ValueError(f"{g}: a PASS by {c.reviewer} needs audio_listened (only a human can hear the clip); "
                                 f"an auto: tool may PASS it from machine evidence")
            if c.level in ("FULL_MOTION", "CUT") and _SAMPLED_ADMISSION.search(f"{c.evidence}\n{c.note}"):
                raise ValueError(f"{g}: level {c.level} contradicts the evidence/note, which says the take was only sampled "
                                 f"(contact strip / sampled frames only / not listened); the level must be SAMPLED")
        return self

    @model_validator(mode="after")
    def _one_check_per_group(self) -> "TakeQc":
        seen = [c.group for c in self.checks]
        dup = sorted({g for g in seen if seen.count(g) > 1})
        if dup:
            raise ValueError(f"take {self.take_id}: more than one check for {dup}")
        if self.cause is not None and self.verdict().status != "REJECTED":
            raise ValueError(f"take {self.take_id}: a failure cause only belongs on a rejected take")
        return self

    def check(self, group: str) -> GroupCheck:
        return next((c for c in self.checks if c.group == group), GroupCheck(group=group))  # type: ignore[arg-type]

    def _missing(self) -> list[tuple[str, str]]:
        """(question id, group) of every required answer without a non-blank answer in a human-reviewed group check."""
        out = []
        for qid in self.required_answers:
            group = answer_group(qid)
            c = self.check(group)
            if not (c.by_human and c.answers.get(qid, "").strip()):
                out.append((qid, group))
        return out

    def unanswered(self) -> list[str]:
        return list(dict.fromkeys(g for _, g in self._missing()))

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
        unanswered = self.unanswered()
        for g in unanswered:
            if g not in open_groups:
                open_groups.append(g)
        reasons = [f"P0 FAIL: {', '.join(p0)}"] if p0 else []
        reasons += [f"P1 FAIL not waived: {', '.join(p1u)}"] if p1u else []
        if p0 or p1u:
            status: Status = "REJECTED"
        elif open_groups:
            status = "INCOMPLETE"
            reasons.append(f"not yet judged: {', '.join(open_groups)}")
            if unanswered:
                reasons.append(f"required answers missing: {', '.join(i for i, _ in self._missing())}")
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
