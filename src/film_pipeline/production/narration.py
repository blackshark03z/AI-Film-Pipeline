"""Narration profile adapter: an E2E project (`e2e.py`: SRT + audio, 8-12 planned shots) as a Production Package.

The E2E project directory stays the source of truth for media, the shot plan, runtime and delivery. The package
holds a typed view of it so the same gates, `film.py validate/status` and playbook apply:

- `01_story.json` (`NarrationStory`): the source locks (hashes, audio interval) and the story *sentences* read from the
  SRT with `drama.action_meaning.sentences` (cue boundaries are packaging, not beats), plus the rights status.
- `04_shots.json` (`NarrationShots`): the planned shots with the sentences they carry and their `action_meaning`.

Gate 1 re-checks the locks against the live project; Gate 2 re-checks coverage and reuses `e2e._direction_issues`,
so `plan_review_required` in `e2e.status` and a BLOCK on Gate 2 can never disagree.
`e2e` is imported lazily: the models below must stay importable from `sections.py` without the runtime stack.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Annotated, Any, Literal

from pydantic import Field, StringConstraints

from film_pipeline.core import ContractModel
from film_pipeline.drama.action_meaning import ActionMeaning, sentences

Ident = Annotated[str, StringConstraints(pattern=r"^[A-Za-z0-9][A-Za-z0-9_-]*$")]
Text = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)]
RightsStatus = Literal["cleared", "pending", "restricted", "unknown"]


class SourceRef(ContractModel):
    project: str  # E2E project directory: relative to the package root, or absolute
    audio_sha256: str
    srt_sha256: str
    audio_start_s: float = Field(ge=0)
    audio_end_s: float = Field(gt=0)


class NarrationSentence(ContractModel):
    id: Ident
    cue_ids: list[int] = Field(min_length=1)
    start_s: float  # source-audio seconds
    end_s: float
    text: Text


class NarrationStory(ContractModel):
    """`01_story.json` for profile narration."""

    source: SourceRef
    sentences: list[NarrationSentence] = Field(min_length=1)
    rights_status: RightsStatus = "unknown"  # the SRT/audio belong to someone; the Owner clears or restricts them
    source_note: str = ""


class NarrationShot(ContractModel):
    shot_id: Ident
    timeline_in_s: float  # film seconds (0 = start of the chosen interval)
    timeline_out_s: float
    source_text: str = ""
    sentence_ids: list[Ident] = Field(default_factory=list)
    action_meaning: ActionMeaning | None = None


class NarrationShots(ContractModel):
    """`04_shots.json` for profile narration."""

    shots: list[NarrationShot] = Field(min_length=1)


NARRATION_SECTIONS: dict[str, type[ContractModel]] = {"story": NarrationStory, "shots": NarrationShots}


# --- import -------------------------------------------------------------------------------------------------

def _e2e():
    from film_pipeline import e2e
    return e2e


def _interval_sentences(cues: list[dict], start_s: float, end_s: float) -> list[dict]:
    selected = [c for c in cues if c["end_s"] > start_s and c["start_s"] < end_s]
    return [{**s, "id": f"S{n:02d}"} for n, s in enumerate(sentences(selected), 1)]


def _rel(target: Path, base: Path) -> str:
    try:
        return os.path.relpath(target, base).replace("\\", "/")
    except ValueError:  # different drive on Windows
        return str(target)


def _write_json(path: Path, data: dict[str, Any]) -> None:
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")


def build_package(project: Path, out: Path, *, film_id: str | None = None, title: str | None = None,
                  language: str = "en", refresh: bool = False) -> dict[str, Any]:
    """Write (or with `refresh`, rewrite the story and shots of) a narration package for an E2E project.

    Refuses a non-empty `out` unless `refresh`; a refresh keeps `film.json` and the story's rights decision."""
    from film_pipeline.production.package import FilmHeader, PackageError, save_header
    e2e = _e2e()
    project, out = project.resolve(), out.resolve()
    try:
        meta, plan = e2e._project(project)
    except ValueError as exc:
        raise PackageError(f"not a valid E2E project: {exc}") from exc
    kept: dict[str, Any] = {}
    if refresh:
        if not (out / "film.json").is_file():
            raise PackageError(f"{out}: nothing to refresh (film.json missing)")
        old = out / "01_story.json"
        if old.is_file():
            previous = json.loads(old.read_text(encoding="utf-8"))
            kept = {k: previous[k] for k in ("rights_status", "source_note") if k in previous}
    elif out.exists() and any(out.iterdir()):
        raise PackageError(f"{out} is not empty; refusing to overwrite")
    cues = e2e._cues(project, meta)
    start = float(meta["audio_start_s"])
    end = float(meta["audio_end_s"])
    story_sentences = _interval_sentences(cues, start, end)
    story = {
        "source": {"project": _rel(project, out), "audio_sha256": meta["audio_sha256"],
                   "srt_sha256": meta["srt_sha256"], "audio_start_s": start, "audio_end_s": end},
        "sentences": [{"id": s["id"], "cue_ids": s["cue_ids"], "start_s": s["start_s"], "end_s": s["end_s"],
                       "text": s["text"]} for s in story_sentences],
        **kept,
    }
    shots = []
    for shot in plan["shots"]:
        lo, hi = start + shot["timeline_in_s"], start + shot["timeline_out_s"]
        entry = {"shot_id": shot["shot_id"], "timeline_in_s": shot["timeline_in_s"],
                 "timeline_out_s": shot["timeline_out_s"], "source_text": shot.get("source_text", ""),
                 "sentence_ids": [s["id"] for s in story_sentences if s["end_s"] > lo and s["start_s"] < hi]}
        if shot.get("action_meaning"):
            entry["action_meaning"] = shot["action_meaning"]
        shots.append(entry)
    out.mkdir(parents=True, exist_ok=True)
    if not refresh:
        save_header(out, FilmHeader(film_id=film_id or meta["project_id"], title=title or meta["project_id"],
                                    profile="narration", language=language))
    _write_json(out / "01_story.json", story)
    _write_json(out / "04_shots.json", {"shots": shots})
    return {"package": str(out), "film_id": film_id or meta["project_id"], "sentences": len(story_sentences),
            "shots": len(shots), "refreshed": refresh}


# --- gates --------------------------------------------------------------------------------------------------

def _live_project(pkg) -> tuple[Path, dict, dict] | str:
    """(project root, meta, plan) of the package's source project, or the reason it cannot be read."""
    story: NarrationStory | None = pkg.typed.get("story")
    if story is None:
        return "story not loaded"
    root = Path(story.source.project)
    if not root.is_absolute():
        root = (pkg.root / root).resolve()
    try:
        meta, plan = _e2e()._project(root)
    except ValueError as exc:
        return f"source project: {exc}"
    return root, meta, plan


def narration_story_issues(pkg) -> list[str]:
    """Gate 1 for the narration profile: the source locks hold and the sentences are what the SRT says."""
    live = _live_project(pkg)
    if isinstance(live, str):
        return [live]
    root, meta, _ = live
    story: NarrationStory = pkg.typed["story"]
    out: list[str] = []
    src = story.source
    for label, mine, theirs in (("audio_sha256", src.audio_sha256, meta["audio_sha256"]),
                                ("srt_sha256", src.srt_sha256, meta["srt_sha256"]),
                                ("audio_start_s", src.audio_start_s, meta["audio_start_s"]),
                                ("audio_end_s", src.audio_end_s, meta["audio_end_s"])):
        if mine != theirs:
            out.append(f"source {label} differs from the project (re-import with refresh)")
    ids = [s.id for s in story.sentences]
    if len(set(ids)) != len(ids):
        out.append("duplicate sentence id")
    fresh = _interval_sentences(_e2e()._cues(root, meta), float(meta["audio_start_s"]), float(meta["audio_end_s"]))
    mine = [(s.cue_ids, s.text) for s in story.sentences]
    if mine != [(s["cue_ids"], s["text"]) for s in fresh]:
        out.append("sentences differ from the SRT (re-import with refresh)")
    return out


def narration_pending(pkg) -> list[str]:
    story = pkg.typed.get("story")
    if story is not None and story.rights_status != "cleared":
        return [f"source SRT/audio rights_status={story.rights_status} (Owner must clear rights)"]
    return []


def narration_direction_issues(pkg) -> list[str]:
    """Gate 2 for the narration profile: sentence coverage plus exactly the E2E plan-review rules."""
    live = _live_project(pkg)
    if isinstance(live, str):
        return [live]
    root, meta, plan = live
    story: NarrationStory = pkg.typed["story"]
    shots: NarrationShots | None = pkg.typed.get("shots")
    if shots is None:
        return ["shots not loaded"]
    e2e = _e2e()
    out: list[str] = []
    live_shots = {s["shot_id"]: s for s in plan["shots"]}
    mine = {s.shot_id: s for s in shots.shots}
    if list(mine) != list(live_shots):
        out.append("package shots differ from the project plan (re-import with refresh)")
    else:
        for sid, shot in mine.items():
            lv = live_shots[sid]
            if (shot.timeline_in_s, shot.timeline_out_s) != (lv["timeline_in_s"], lv["timeline_out_s"]):
                out.append(f"{sid}: timeline differs from the project plan (re-import with refresh)")
            declared = ActionMeaning.model_validate(lv["action_meaning"]) if lv.get("action_meaning") else None
            if shot.action_meaning != declared:
                out.append(f"{sid}: action_meaning differs from the project plan (re-import with refresh)")
    known = {s.id for s in story.sentences}
    carried: set[str] = set()
    for shot in shots.shots:
        out += [f"{shot.shot_id}: unknown sentence {sid!r}" for sid in shot.sentence_ids if sid not in known]
        carried.update(shot.sentence_ids)
    out += [f"sentence {sid} is carried by no shot" for sid in sorted(known - carried)]
    # the E2E plan-review rules, verbatim
    out += [f"{s['shot_id']}: needs visual_intent, image_prompt and video_prompt" for s in plan["shots"]
            if not all(isinstance(s.get(k), str) and s[k].strip() for k in ("visual_intent", "image_prompt",
                                                                            "video_prompt"))]
    out += e2e._direction_issues(plan, e2e._cues(root, meta), meta["audio_start_s"])
    return out


# --- status -------------------------------------------------------------------------------------------------

def status_report(pkg, db_path: Path | None = None, project_id: str | None = None) -> dict[str, Any]:
    """Package gates next to `e2e.status` of the source project (unchanged, under the key `e2e`)."""
    from film_pipeline.production.gates import evaluate_gates, summary
    live = _live_project(pkg)
    report: dict[str, Any] = {"package": summary(evaluate_gates(pkg)), "package_issues": pkg.issues}
    if isinstance(live, str):
        report["e2e"] = None
        report["error"] = live
    else:
        report["e2e"] = _e2e().status(live[0], db_path, project_id)
    return report
