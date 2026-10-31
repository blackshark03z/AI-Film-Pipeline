"""Drama P0 #1 — Fountain screenplay intake (Vietnamese-first).

Accepts a dialogue screenplay in Fountain markup: scene headings, action,
character cues, parentheticals, dialogue and transitions. Vietnamese
headings (``NỘI.``/``NGOẠI.``) are accepted next to ``INT.``/``EXT.``.
Fountain notes ``[[key: value]]`` carry pipeline annotations such as
``[[beat: REVEAL]]`` (applies to the next element) or, at scene level,
``[[look: ...]]``.

The parser is deterministic and never invents content: every element keeps
its 1-based source line.
"""
from __future__ import annotations

import re
import unicodedata
from typing import Literal

from pydantic import Field

from ..core import ContractModel

ElementKind = Literal["action", "dialogue", "transition"]

_HEADING_RE = re.compile(
    r"^(?P<prefix>INT\./EXT\.|INT/EXT\.?|I/E\.?|INT\.|EXT\.|EST\.|"
    r"NỘI/NGOẠI\.?|NỘI\.|NGOẠI\.)\s*(?P<rest>.+)$", re.IGNORECASE)
_NOTE_RE = re.compile(r"\[\[(.*?)\]\]", re.DOTALL)
_BONEYARD_RE = re.compile(r"/\*.*?\*/", re.DOTALL)
_EXTENSION_RE = re.compile(r"\s*\(([^)]*)\)\s*$")
_TIME_SPLIT_RE = re.compile(r"\s+[-–—]\s+")
_WORD_RE = re.compile(r"[^\W_]+", re.UNICODE)


def normalize(text: str) -> str:
    """NFC so composed and decomposed Vietnamese diacritics compare equal."""
    return unicodedata.normalize("NFC", text)


def count_vi_syllables(text: str) -> int:
    """Vietnamese is written one syllable per space-separated word, so the
    syllable count is the number of letter/digit runs. Parentheticals are
    stage directions, not speech, and are excluded."""
    spoken = re.sub(r"\([^)]*\)", " ", normalize(text))
    return len(_WORD_RE.findall(spoken))


class ScriptElement(ContractModel):
    kind: ElementKind
    text: str
    line_no: int
    character: str = ""         # dialogue only: speaker (cue, no extension)
    extension: str = ""         # V.O. / O.S. / NGOÀI HÌNH ...
    parenthetical: str = ""
    beat: str = ""              # from a preceding [[beat: X]] note
    syllables: int = 0          # dialogue only


class ScriptScene(ContractModel):
    scene_id: str
    heading: str
    setting: Literal["INT", "EXT", "INT/EXT", "EST"]
    location: str
    time_of_day: str = ""
    line_no: int
    elements: list[ScriptElement] = Field(default_factory=list)
    notes: dict[str, str] = Field(default_factory=dict)

    @property
    def dialogue(self) -> list[ScriptElement]:
        return [e for e in self.elements if e.kind == "dialogue"]

    @property
    def speakers(self) -> list[str]:
        seen: list[str] = []
        for line in self.dialogue:
            if line.character not in seen:
                seen.append(line.character)
        return seen

    @property
    def dialogue_syllables(self) -> int:
        return sum(e.syllables for e in self.dialogue)

    def characters_present(self, known: list[str]) -> list[str]:
        """Speakers plus known characters named in action lines. Off-screen
        voices (V.O./O.S.) are heard, not seen, so they are excluded."""
        present = [e.character for e in self.dialogue
                   if not _is_offscreen(e.extension)]
        for element in self.elements:
            if element.kind != "action":
                continue
            low = element.text.lower()
            for name in known:
                if name not in present and re.search(
                        rf"(?<!\w){re.escape(name.lower())}(?!\w)", low):
                    present.append(name)
        return list(dict.fromkeys(present))


class Script(ContractModel):
    title_page: dict[str, str] = Field(default_factory=dict)
    scenes: list[ScriptScene] = Field(default_factory=list)

    @property
    def characters(self) -> list[str]:
        names: list[str] = []
        for scene in self.scenes:
            for name in scene.speakers:
                if name not in names:
                    names.append(name)
        return names


def _is_offscreen(extension: str) -> bool:
    ext = extension.upper().replace(" ", "")
    return ext in {"V.O.", "VO", "O.S.", "OS", "O.C.", "NGOÀIHÌNH",
                   "LỒNGTIẾNG"}


def _is_character_cue(line: str) -> bool:
    if line.startswith("@"):
        return True
    name = _EXTENSION_RE.sub("", line).strip()
    if not name or not any(ch.isalpha() for ch in name):
        return False
    return name == name.upper() and not name.endswith(":") \
        and not _HEADING_RE.match(name)


def _is_transition(line: str) -> bool:
    if line.startswith(">") and not line.endswith("<"):
        return True
    return line == line.upper() and line.endswith(":") and \
        any(ch.isalpha() for ch in line)


def _parse_notes(text: str) -> tuple[str, dict[str, str]]:
    notes: dict[str, str] = {}
    for match in _NOTE_RE.finditer(text):
        body = match.group(1).strip()
        if ":" in body:
            key, value = body.split(":", 1)
            notes[key.strip().lower()] = value.strip()
    return _NOTE_RE.sub("", text), notes


def _blank_before(lines: list[str], i: int) -> bool:
    """True when the previous line is blank, skipping note-only lines so a
    ``[[beat: X]]`` above a character cue does not hide the cue."""
    j = i - 1
    while j >= 0 and lines[j].strip() and \
            not _NOTE_RE.sub("", lines[j]).strip():
        j -= 1
    return j < 0 or not lines[j].strip()


def _heading(line: str, line_no: int, index: int) -> ScriptScene:
    forced = line.startswith(".") and not line.startswith("..")
    text = line[1:].strip() if forced else line.strip()
    match = _HEADING_RE.match(text)
    prefix = match.group("prefix").upper() if match else ""
    rest = match.group("rest") if match else text
    rest = re.sub(r"\s*#[^#]+#\s*$", "", rest)       # scene numbers
    setting = ("INT/EXT" if "/" in prefix else
               "EXT" if prefix.startswith(("EXT", "NGOẠI")) else
               "EST" if prefix.startswith("EST") else "INT")
    parts = _TIME_SPLIT_RE.split(rest, maxsplit=1)
    return ScriptScene(
        scene_id=f"SC{index:02d}", heading=text, setting=setting,
        location=parts[0].strip(),
        time_of_day=parts[1].strip() if len(parts) > 1 else "",
        line_no=line_no)


def parse_fountain(text: str) -> Script:
    """Fountain text -> typed Script. Lines before the first scene heading
    other than the title page are ignored (Fountain cold opens are not
    used in this pipeline)."""
    text = normalize(text).replace("\r\n", "\n").replace("\r", "\n")
    # keep line numbers stable when removing boneyard comments
    text = _BONEYARD_RE.sub(lambda m: "\n" * m.group(0).count("\n"), text)
    lines = text.split("\n")
    script = Script()
    i = 0
    # title page: "Key: value" block at the very top
    if lines and re.match(r"^[A-Za-zÀ-ỹ ]+:\s*\S", lines[0]) and \
            not _HEADING_RE.match(lines[0]):
        while i < len(lines) and lines[i].strip():
            if ":" in lines[i]:
                key, value = lines[i].split(":", 1)
                script.title_page[key.strip().lower()] = value.strip()
            i += 1
    scene: ScriptScene | None = None
    pending_beat = ""
    while i < len(lines):
        raw = lines[i]
        stripped = raw.strip()
        line_no = i + 1
        prev_blank = _blank_before(lines, i)
        if not stripped or stripped.startswith(("#", "=")):
            i += 1
            continue
        body, notes = _parse_notes(stripped)
        body = body.strip()
        is_heading = prev_blank and (
            (stripped.startswith(".") and not stripped.startswith(".."))
            or bool(_HEADING_RE.match(stripped)))
        if is_heading:
            scene = _heading(body, line_no, len(script.scenes) + 1)
            script.scenes.append(scene)
            pending_beat = ""
            i += 1
            continue
        if scene is None:
            i += 1
            continue
        if notes and not body:
            # standalone note: a beat tags the next element, anything else
            # is scene-level metadata
            if "beat" in notes:
                pending_beat = notes.pop("beat").upper()
            scene.notes.update(notes)
            i += 1
            continue
        next_nonblank = i + 1 < len(lines) and lines[i + 1].strip() != ""
        if prev_blank and next_nonblank and _is_character_cue(body):
            cue = body.lstrip("@").strip()
            extension = ""
            match = _EXTENSION_RE.search(cue)
            if match:
                extension = match.group(1).strip()
                cue = _EXTENSION_RE.sub("", cue).strip()
            cue = cue.rstrip("^").strip()   # dual-dialogue caret
            parenthetical: list[str] = []
            speech: list[str] = []
            i += 1
            while i < len(lines) and lines[i].strip():
                part, part_notes = _parse_notes(lines[i].strip())
                if "beat" in part_notes:
                    pending_beat = part_notes["beat"].upper()
                part = part.strip()
                if part.startswith("(") and part.endswith(")"):
                    parenthetical.append(part[1:-1].strip())
                elif part:
                    speech.append(part)
                i += 1
            spoken = " ".join(speech)
            scene.elements.append(ScriptElement(
                kind="dialogue", text=spoken, line_no=line_no,
                character=cue, extension=extension,
                parenthetical="; ".join(parenthetical),
                beat=pending_beat or notes.get("beat", "").upper(),
                syllables=count_vi_syllables(spoken)))
            pending_beat = ""
            continue
        if prev_blank and _is_transition(body) and not next_nonblank:
            scene.elements.append(ScriptElement(
                kind="transition", text=body.lstrip(">").strip(),
                line_no=line_no))
            i += 1
            continue
        # action: consecutive non-blank lines form one paragraph
        paragraph = [body.lstrip("!")]
        beat = pending_beat or notes.get("beat", "").upper()
        i += 1
        while i < len(lines) and lines[i].strip():
            part, part_notes = _parse_notes(lines[i].strip())
            beat = beat or part_notes.get("beat", "").upper()
            paragraph.append(part.strip())
            i += 1
        scene.elements.append(ScriptElement(
            kind="action", text=" ".join(p for p in paragraph if p),
            line_no=line_no, beat=beat))
        pending_beat = ""
    return script
