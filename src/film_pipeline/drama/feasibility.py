"""Drama P0 #3 — script feasibility check (feeds Gate 1, fail-closed).

Blocks what the free Seedance route is known to render badly before any
generation is spent: physical contact/fights, three or more speakers,
crowded frames, readable on-screen text and dialogue that cannot fit the
15-second scene with room for reactions.

Values marked ``(*)`` in ``FeasibilityLimits`` are assumptions from the
2026-10-31 gap analysis; re-measure them on the first test scene.
"""
from __future__ import annotations

import re
from typing import Literal

from pydantic import Field

from ..core import ContractModel
from .script import Script, ScriptScene, normalize

Severity = Literal["BLOCK", "WARN"]


class FeasibilityLimits(ContractModel):
    max_speakers: int = 2
    max_in_frame: int = 3
    max_dialogue_syllables: int = 35        # (*) per 15 s scene
    scene_duration_s: float = 15.0
    min_silence_s: float = 3.0
    syllables_per_second: float = 4.0       # (*) calm Vietnamese delivery


class FeasibilityIssue(ContractModel):
    scene_id: str
    rule: str
    severity: Severity
    detail: str
    line_no: int | None = None


class FeasibilityReport(ContractModel):
    issues: list[FeasibilityIssue] = Field(default_factory=list)
    scene_metrics: dict[str, dict] = Field(default_factory=dict)

    @property
    def verdict(self) -> Literal["PASS", "BLOCKED"]:
        return "BLOCKED" if any(i.severity == "BLOCK"
                                for i in self.issues) else "PASS"


def _rx(*patterns: str) -> re.Pattern:
    # word-bounded alternatives; \w is Unicode-aware for Vietnamese
    return re.compile("|".join(rf"(?<!\w)(?:{p})(?!\w)" for p in patterns),
                      re.IGNORECASE)


# (rule, severity, pattern) — matched against action lines and
# parentheticals, never against dialogue (characters may TALK about a
# fight without one being shown)
_ACTION_RULES: tuple[tuple[str, Severity, re.Pattern], ...] = (
    ("CONTACT_OR_FIGHT", "BLOCK", _rx(
        r"đánh(?! rơi| răng| giá| thức| dấu| máy| chữ| son)", r"đấm",
        r"đá vào", r"đạp", r"tát", r"xô ngã", r"xô đẩy", r"va vào",
        r"va chạm", r"vật lộn", r"giằng co", r"bóp cổ", r"đâm", r"chém",
        r"túm cổ", r"ẩu đả",
        r"punch\w*", r"fight\w*", r"kick\w*", r"slap\w*", r"collid\w*",
        r"wrestl\w*", r"shov\w*", r"stab\w*", r"grab\w* (?:him|her)")),
    ("COMPLEX_EMBRACE", "BLOCK", _rx(
        r"ôm chầm", r"ôm chặt", r"ôm lấy nhau", r"ôm nhau",
        r"(?<!đính )hôn(?! nhân| lễ| thê| phu)",
        r"kiss\w*", r"embrac\w*", r"hug\w*")),
    ("FAST_SMALL_HANDOFF", "BLOCK", _rx(
        r"giật lấy", r"chộp lấy", r"dúi vào tay", r"ném cho", r"tung cho",
        r"snatch\w*", r"toss\w*")),
    ("HANDOFF_REVIEW", "WARN", _rx(
        r"đưa cho", r"trao cho", r"hand\w* (?:over|it|the)")),
    ("READABLE_TEXT", "BLOCK", _rx(
        r"tin nhắn", r"dòng chữ", r"chữ viết", r"biển hiệu", r"tấm biển",
        r"bảng tên", r"màn hình điện thoại", r"đọc thư", r"đọc tin",
        r"tờ báo", r"tiêu đề", r"text message", r"sign reads",
        r"caption", r"headline", r"subtitle", r"logo")),
)


def _speech_seconds(syllables: int, limits: FeasibilityLimits) -> float:
    return syllables / limits.syllables_per_second


def check_scene(scene: ScriptScene, *, known_characters: list[str],
                limits: FeasibilityLimits | None = None
                ) -> tuple[list[FeasibilityIssue], dict]:
    limits = limits or FeasibilityLimits()
    issues: list[FeasibilityIssue] = []
    sid = scene.scene_id

    def add(rule: str, severity: Severity, detail: str,
            line_no: int | None = None) -> None:
        issues.append(FeasibilityIssue(scene_id=sid, rule=rule,
                                       severity=severity, detail=detail,
                                       line_no=line_no))

    speakers = scene.speakers
    if len(speakers) > limits.max_speakers:
        add("TOO_MANY_SPEAKERS", "BLOCK",
            f"{len(speakers)} speakers ({', '.join(speakers)}); "
            f"max {limits.max_speakers}")
    present = scene.characters_present(known_characters)
    if len(present) > limits.max_in_frame:
        add("TOO_MANY_IN_FRAME", "BLOCK",
            f"{len(present)} characters in frame ({', '.join(present)}); "
            f"max {limits.max_in_frame}")
    for element in scene.elements:
        texts = []
        if element.kind == "action":
            texts.append(element.text)
        if element.parenthetical:
            texts.append(element.parenthetical)
        for text in texts:
            low = normalize(text).lower()
            for rule, severity, pattern in _ACTION_RULES:
                match = pattern.search(low)
                if match:
                    add(rule, severity, f"'{match.group(0)}' in: {text}",
                        element.line_no)
    syllables = scene.dialogue_syllables
    speech_s = _speech_seconds(syllables, limits)
    silence_s = limits.scene_duration_s - speech_s
    if syllables > limits.max_dialogue_syllables:
        add("DIALOGUE_TOO_LONG", "BLOCK",
            f"{syllables} syllables > {limits.max_dialogue_syllables} "
            f"per {limits.scene_duration_s:g}s scene")
    if silence_s < limits.min_silence_s:
        add("NO_ROOM_FOR_REACTION", "BLOCK",
            f"~{speech_s:.1f}s of speech leaves {silence_s:.1f}s; need "
            f">= {limits.min_silence_s:g}s reaction/silence")
    if not scene.elements:
        add("EMPTY_SCENE", "BLOCK", "scene has no action or dialogue")
    metrics = {"speakers": speakers, "in_frame": present,
               "dialogue_syllables": syllables,
               "estimated_speech_s": round(speech_s, 2),
               "estimated_silence_s": round(silence_s, 2)}
    return issues, metrics


def check_script(script: Script, *,
                 limits: FeasibilityLimits | None = None,
                 extra_characters: list[str] | None = None
                 ) -> FeasibilityReport:
    """``extra_characters``: non-speaking cast who may appear in action."""
    known = list(dict.fromkeys(script.characters + (extra_characters or [])))
    report = FeasibilityReport()
    if not script.scenes:
        report.issues.append(FeasibilityIssue(
            scene_id="-", rule="NO_SCENES", severity="BLOCK",
            detail="no scene headings found (INT./EXT./NỘI./NGOẠI.)"))
    for scene in script.scenes:
        issues, metrics = check_scene(scene, known_characters=known,
                                      limits=limits)
        report.issues.extend(issues)
        report.scene_metrics[scene.scene_id] = metrics
    return report
