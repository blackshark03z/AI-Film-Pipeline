"""Stage-skill hint hook for Claude Code and Google Antigravity.

Tells the agent which film skills to load for the Muse stage in play.

Claude Code (.claude/settings.json, snake_case payload):
  * UserPromptSubmit  - matches stage keywords (English + Vietnamese) in the prompt.
  * PreToolUse (Bash) - matches `muse_studio.cli <stage>` / `pool_runner <stage>` commands.
  Output: hookSpecificOutput.additionalContext.

Antigravity (.agents/hooks.json, camelCase payload with `hookEventName`):
  * SessionStart + PreInvocation - match `lastUserInput` plus the muse_studio commands found in the
    tail of `transcriptPath`. Each stage is hinted once per conversation (state file in the OS temp
    folder), because PreInvocation fires before every model call. State files older than 7 days are
    pruned on each run, keeping at most the newest 200.
  Output: {"injectSteps": [{"systemMessage": {"systemMessage": ...}}]} or {}.
  (Antigravity's PreToolUse output has no context field and requires a permission decision, so the
  command hint is taken from the transcript instead.)

It only adds context; it never blocks and always exits 0.
"""

from __future__ import annotations

import json
import os
import re
import sys
import tempfile
import time
import unicodedata
from pathlib import Path

PRE = "pre-production"
POST = "post-production review"

# stage id -> (label, phase, skills in load order)
STAGES = {
    "1-2": ("stage 1-2 SRT/beats/story bible/treatment", PRE,
            ["muse-director", "film-treatment", "film-craft"]),
    "3a": ("stage 3a compile + staging/generability", PRE, ["muse-director", "film-craft"]),
    "2.5": ("stage 2.5 anchors/plates/keyframes", PRE,
            ["muse-director", "film-craft", "film-creative-review"]),
    "3b": ("stage 3b final compile + preflight", PRE, ["muse-director", "film-craft"]),
    "3.5": ("stage 3.5 animatic", PRE, ["muse-director", "film-craft", "film-creative-review"]),
    "sound": ("dialogue/voice/sound plan", PRE, ["film-sound-design"]),
    "4": ("stage 4 generation", "production", ["muse-director", "film-craft", "film-lessons"]),
    "5": ("stage 5 FilmQC + take review", POST,
          ["muse-director", "film-creative-review", "film-lessons"]),
    "6-7": ("stage 6-7 assemble/mix/master", POST,
            ["muse-director", "film-creative-review", "film-lessons", "film-sound-design"]),
    "8": ("stage 8 delivery", POST, ["muse-director", "film-creative-review", "film-lessons"]),
    "defect": ("defect/retry/lesson", POST, ["film-lessons"]),
}

CLI_STAGE = {
    "normalize-srt": "1-2", "srt-audit": "1-2", "compile": "3a", "keyframes": "2.5",
    "preflight": "3b", "animatic": "3.5", "videos": "4", "qc-audit": "5",
    "assemble": "6-7", "deliver": "8",
}

# Prompt keywords, matched on lower-cased text with Vietnamese diacritics stripped.
PROMPT_PATTERNS = {
    "1-2": r"\bsrt\b|\bbeats?\b|story.?bible|treatment|\bkich ban\b|\bscript\b|y do dao dien|"
           r"bang mau|color script|colou?r script|mo.?tip|\bmotif|duong cam xuc|tong phim",
    "3a": r"\bcompile\b|\bstaging\b|generab|phan canh|shot list|\bbien dich\b",
    "2.5": r"keyframe|\banchors?\b|turnaround|\bplates?\b|contact sheet|khung hinh|tao anh",
    "3b": r"preflight",
    "3.5": r"animatic|storyboard",
    "sound": r"\bthoai\b|dialogue|\bvoice|\bgiong\b|long tieng|lip.?sync|khau hinh|am thanh|\bsound|"
             r"\bmix\b|\blufs\b|nhac nen|tieng dong|foley|ambience",
    "4": r"pool_runner videos|\bgeneration\b|\bgenerate\b|\brender\b|chay live|luot live|"
         r"\bchay\b.*\b(01|02|shot|canh)\b",
    "5": r"qc.?audit|\bfilmqc\b|\btakes?\b|duyet take|chon take|\bqc\b",
    "6-7": r"\bassembl|\brap\b|ban rap|ban dung|\bmaster\b|rough cut|\bcut\b|dung canh",
    "8": r"\bdeliver|giao hang|trailer|poster|shorts",
    "defect": r"\bloi\b|\bdefect|\bbug\b|retry|tao lai|lam lai|bai hoc|rut kinh nghiem|lesson|"
              r"post.?mortem|\bslop\b|\bhong\b",
}


def _fold(text: str) -> str:
    text = text.replace("đ", "d").replace("Đ", "D")
    text = unicodedata.normalize("NFKD", text)
    return "".join(c for c in text if not unicodedata.combining(c)).lower()


def stages_for_command(command: str) -> list[str]:
    hits = []
    for match in re.finditer(r"muse_studio\.(?:cli|pool_runner)\s+([a-z-]+)", command):
        stage = CLI_STAGE.get(match.group(1))
        if stage and stage not in hits:
            hits.append(stage)
    return hits


def stages_for_prompt(prompt: str) -> list[str]:
    folded = _fold(prompt)
    return [stage for stage, pattern in PROMPT_PATTERNS.items() if re.search(pattern, folded)]


def build_context(stages: list[str], source: str) -> str:
    skills: list[str] = []
    labels = []
    for stage in stages:
        label, phase, names = STAGES[stage]
        labels.append(f"{label} ({phase})")
        skills.extend(n for n in names if n not in skills)
    return (
        f"Muse stage skills ({source}): detected {'; '.join(labels)}. "
        f"Before acting on this stage, invoke these skills with the Skill tool unless already loaded "
        f"in this session: {', '.join(skills)}. Their rules apply on top of CLAUDE.md "
        f"(Owner review points unchanged; Muse spend needs no approval, other providers still do)."
    )


SKILL_PATHS = {
    "muse-director": Path(__file__).resolve().parents[1] / "skills" / "muse-director" / "SKILL.md",
}
FILM_SKILLS_DIR = Path.home() / ".claude" / "skills"
TRANSCRIPT_TAIL_BYTES = 65536


def _skill_path(name: str) -> str:
    return str(SKILL_PATHS.get(name, FILM_SKILLS_DIR / name / "SKILL.md"))


def build_agy_context(stages: list[str], source: str) -> str:
    skills: list[str] = []
    labels = []
    for stage in stages:
        label, phase, names = STAGES[stage]
        labels.append(f"{label} ({phase})")
        skills.extend(n for n in names if n not in skills)
    paths = "; ".join(f"{n} = {_skill_path(n)}" for n in skills)
    return (
        f"Muse stage skills ({source}): detected {'; '.join(labels)}. "
        f"Before acting on this stage, activate these skills unless already loaded in this "
        f"conversation: {', '.join(skills)}. If one is missing from your skill list, read its file "
        f"directly: {paths}. Their rules apply on top of AGENTS.md (lane rules and self-review "
        f"points unchanged)."
    )


def _commands_in(obj, out: list[str]) -> None:
    if isinstance(obj, dict):
        args = obj.get("args")
        if obj.get("name") == "run_command" and isinstance(args, dict):
            out.append(str(args.get("CommandLine") or args.get("commandLine") or ""))
        for value in obj.values():
            _commands_in(value, out)
    elif isinstance(obj, list):
        for value in obj:
            _commands_in(value, out)


def recent_commands(transcript_path: str) -> list[str]:
    """run_command lines in the last TRANSCRIPT_TAIL_BYTES of an Antigravity transcript."""
    if not transcript_path or not os.path.isfile(transcript_path):
        return []
    with open(transcript_path, "rb") as handle:
        handle.seek(0, os.SEEK_END)
        handle.seek(max(0, handle.tell() - TRANSCRIPT_TAIL_BYTES))
        tail = handle.read().decode("utf-8", "replace")
    commands: list[str] = []
    for line in tail.splitlines():
        if "muse_studio" not in line:
            continue
        try:
            _commands_in(json.loads(line), commands)
        except ValueError:
            continue
    return commands


def _state_file(conversation_id: str) -> Path:
    safe = re.sub(r"[^A-Za-z0-9_.-]", "_", conversation_id)[:80] or "unknown"
    return Path(tempfile.gettempdir()) / "muse_stage_skills" / f"{safe}.json"


STATE_MAX_AGE_S = 7 * 24 * 3600
STATE_MAX_FILES = 200


def _prune_state(keep: Path, now: float | None = None) -> None:
    """Drop state files older than 7 days and keep the newest 200; never raises."""
    try:
        now = time.time() if now is None else now
        files = []
        for path in keep.parent.glob("*.json"):
            if path == keep:
                continue
            try:
                files.append((path.stat().st_mtime, path))
            except OSError:
                continue
        files.sort(reverse=True)
        for index, (mtime, path) in enumerate(files):
            if now - mtime > STATE_MAX_AGE_S or index >= STATE_MAX_FILES - 1:
                try:
                    path.unlink()
                except OSError:
                    pass
    except Exception:
        pass


def _run_antigravity(payload: dict) -> int:
    event = str(payload.get("hookEventName", ""))
    if event not in ("PreInvocation", "SessionStart"):
        return 0  # other events expect other output shapes; stay silent
    stages = stages_for_prompt(str(payload.get("lastUserInput") or ""))
    sources = ["prompt"] if stages else []
    cmd_stages: list[str] = []
    for command in recent_commands(str(payload.get("transcriptPath") or "")):
        cmd_stages.extend(s for s in stages_for_command(command) if s not in cmd_stages)
    if cmd_stages:
        sources.append("command")
        stages.extend(s for s in cmd_stages if s not in stages)
    state = _state_file(str(payload.get("conversationId") or ""))
    try:
        seen = set(json.loads(state.read_text(encoding="utf-8")))
    except (OSError, ValueError, TypeError):
        seen = set()
    new = [s for s in stages if s not in seen]
    out: dict = {}
    if new:
        text = build_agy_context(new, " + ".join(sources))
        out = {"injectSteps": [{"systemMessage": {"systemMessage": text}}]}
        try:
            state.parent.mkdir(parents=True, exist_ok=True)
            state.write_text(json.dumps(sorted(seen | set(new))), encoding="utf-8")
        except OSError:
            pass
    _prune_state(state)
    sys.stdout.write(json.dumps(out, ensure_ascii=True))
    return 0


def main() -> int:
    try:
        return _run()
    except Exception:  # a context hint must never break a prompt or a tool call
        return 0


def _run() -> int:
    try:
        payload = json.loads(sys.stdin.buffer.read().decode("utf-8", "replace") or "{}")
    except ValueError:
        return 0
    if not isinstance(payload, dict):
        return 0
    if "hookEventName" in payload:
        return _run_antigravity(payload)
    event = payload.get("hook_event_name", "")
    if event == "PreToolUse":
        tool_input = payload.get("tool_input")
        command = tool_input.get("command", "") if isinstance(tool_input, dict) else ""
        stages = stages_for_command(str(command))
        source = "command"
    else:
        event = "UserPromptSubmit"
        stages = stages_for_prompt(str(payload.get("prompt", "")))
        source = "prompt"
    if not stages:
        return 0
    out = {"hookSpecificOutput": {"hookEventName": event, "additionalContext": build_context(stages, source)}}
    sys.stdout.write(json.dumps(out, ensure_ascii=True))
    return 0


if __name__ == "__main__":
    sys.exit(main())
