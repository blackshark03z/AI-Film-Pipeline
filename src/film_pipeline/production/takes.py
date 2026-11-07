"""Take log and dailies review (categories 57-90 at take level, 131-146 evidence).

``<film>/takes/index.json`` is the append-only register of every rendered take of a drama package:

    take_id (`<generation_id>_t<N>`), generation_id, prompt_sha256 (the exact text sent), start_frame_sha256, route,
    model, credits, output_file + output_sha256, status, registered_at

Status follows the review, never the other way round: GENERATED (nobody looked) -> ACCEPTED / REJECTED / INCOMPLETE once a
filled review is ingested (`qc_model.TakeQc.verdict`). A take is identified by its bytes: registering the same output hash
twice returns the existing entry, and a review is accepted only if it names the hash the log holds.

``dailies_template`` is what the reviewer fills in: the sixteen-group QC record (all UNASSESSED), plus the questions the
shot itself raises (each choreography phase and its seconds, once-actions, performance cues and their forbidden misread,
spoken lines, the expected start and end state, the planned camera size). ``auto_evidence`` runs `drama.autoqc` when the
optional models are installed and turns its findings into WARN checks - never a PASS; without the models it says so and
returns nothing.
"""
from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Literal

from pydantic import Field, model_validator

from film_pipeline.core import ContractModel
from film_pipeline.production.qc_model import GroupCheck, TakeQc, auto_check, blank_take

TakeStatus = Literal["GENERATED", "INCOMPLETE", "ACCEPTED", "REJECTED"]
_STATUS_OF = {"ACCEPTED": "ACCEPTED", "REJECTED": "REJECTED", "INCOMPLETE": "INCOMPLETE"}
# planned camera size -> the face-height band autoqc measures (INSERT has no face to measure)
_SCALE_OF = {"EXTREME_WIDE": "WS", "WIDE": "WS", "MEDIUM": "MS", "MEDIUM_CLOSE": "MCU", "CLOSE": "CU"}


class TakeEntry(ContractModel):
    take_id: str = Field(min_length=1)
    generation_id: str = Field(min_length=1)
    prompt_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    start_frame_sha256: str = Field(default="", pattern=r"^([0-9a-f]{64})?$")  # "" = no start frame used
    route: str = Field(min_length=1)  # e.g. "start_frame+Khung hinh", "ingredients"
    model: str = Field(min_length=1)
    credits: float = Field(ge=0)
    output_file: str = Field(min_length=1)
    output_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    status: TakeStatus = "GENERATED"
    shot_version: int = Field(default=1, ge=1)  # ShotDecl.version the take was rendered from
    cause: str = ""  # failure cause from the review of a REJECTED take (qc_model.Cause)
    registered_at: str = ""
    review_file: str = ""  # relative to the takes directory once a template or review exists


class TakeLog(ContractModel):
    film_id: str
    takes: list[TakeEntry] = Field(default_factory=list)

    @model_validator(mode="after")
    def _unique(self) -> "TakeLog":
        ids = [t.take_id for t in self.takes]
        if len(ids) != len(set(ids)):
            raise ValueError("duplicate take_id in the take log")
        return self

    def for_generation(self, gid: str) -> list[TakeEntry]:
        return [t for t in self.takes if t.generation_id == gid]

    def get(self, take_id: str) -> TakeEntry:
        for t in self.takes:
            if t.take_id == take_id:
                return t
        raise KeyError(f"no take {take_id!r} in the take log")


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def takes_dir(film_root: Path) -> Path:
    return Path(film_root) / "takes"


def load_log(film_root: Path, film_id: str) -> TakeLog:
    path = takes_dir(film_root) / "index.json"
    if not path.is_file():
        return TakeLog(film_id=film_id)
    return TakeLog.model_validate_json(path.read_text(encoding="utf-8"))


def save_log(film_root: Path, log: TakeLog) -> Path:
    path = takes_dir(film_root) / "index.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(log.model_dump(mode="json"), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return path


def register_take(film_root: Path, film_id: str, generation_id: str, clip: Path, *, prompt_text: str, route: str,
                  model: str, credits: float, start_frame: Path | None = None, known_generations: set[str] | None = None,
                  shot_version: int = 1) -> tuple[TakeEntry, bool]:
    """Add a rendered clip to the log. Returns (entry, created); the same bytes registered twice is not a new take."""
    if known_generations is not None and generation_id not in known_generations:
        raise ValueError(f"unknown generation {generation_id!r}")
    clip = Path(clip)
    if not clip.is_file() or clip.stat().st_size == 0:
        raise ValueError(f"take output {clip} is missing or empty")
    if not prompt_text.strip():
        raise ValueError("the prompt text that was sent is required (its hash is the take's provenance)")
    if start_frame is not None and not Path(start_frame).is_file():
        raise ValueError(f"start frame {start_frame} not found")
    log = load_log(film_root, film_id)
    digest = sha256_file(clip)
    for existing in log.takes:
        if existing.output_sha256 == digest:
            if existing.generation_id != generation_id:
                raise ValueError(f"these bytes are already take {existing.take_id} of {existing.generation_id}")
            return existing, False
    entry = TakeEntry(
        take_id=f"{generation_id}_t{len(log.for_generation(generation_id)) + 1}", generation_id=generation_id,
        prompt_sha256=sha256_text(prompt_text), start_frame_sha256=sha256_file(start_frame) if start_frame else "",
        route=route, model=model, credits=credits, output_file=clip.name, output_sha256=digest,
        shot_version=shot_version, registered_at=datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"))
    log.takes.append(entry)
    save_log(film_root, log)
    return entry, True


def _questions(decl: Any, pre: Any, script_lines: dict[int, str]) -> list[dict[str, str]]:
    q: list[dict[str, str]] = []
    choreo = decl.choreography
    for p in choreo.phases:
        q.append({"group": "action", "question": f"{p.start_s:g}-{p.end_s:g}s {p.kind}: does this happen on screen - "
                                                 f"{p.description}?"})
    for action in choreo.once_actions:
        q.append({"group": "action", "question": f"Happens exactly once (not repeated or looped): {action}"})
    for cue in choreo.performance:
        miss = f" Must NOT read as: {cue.prohibited_misread}." if cue.prohibited_misread else ""
        q.append({"group": "character", "question": f"{cue.character}: does the face/body read as "
                                                    f"{cue.emotion_intent} ({cue.intensity})?{miss}"})
    for n in decl.dialogue:
        q.append({"group": "sync", "question": f"Line {n} is audible, spoken by the right character, lips match: "
                                               f"{script_lines.get(n, '(see script.fountain)')}"})
    if decl.camera is not None:
        q.append({"group": "camera", "question": f"Planned size {decl.camera.size}, {decl.camera.angle}, "
                                                 f"{decl.camera.movement}: does the take match?"})
    start, end = pre.states.get(decl.start_state), pre.states.get(decl.end_state)
    if start is not None:
        q.append({"group": "spatial", "question": f"First frame matches state {decl.start_state}: "
                                                  f"{start.describe() or start.as_dict()}"})
    if end is not None:
        q.append({"group": "spatial", "question": f"Last frame matches state {decl.end_state}: "
                                                  f"{end.describe() or end.as_dict()}"})
    q.append({"group": "visual", "question": "Identity, wardrobe, set and light stable; no morphing, extra limbs, "
                                             "text artefacts or flicker."})
    q.append({"group": "motion", "question": "Motion is physically plausible and smooth (full clip, not stills)."})
    return q


def dailies_template(pkg: Any, entry: TakeEntry, script_lines: dict[int, str] | None = None) -> dict[str, Any]:
    """The review sheet for one take: shot context + the QC record to fill in."""
    shots, pre = pkg.typed.get("shots"), pkg.typed.get("preprod")
    if shots is None or pre is None:
        raise ValueError("dailies need a valid 03_preprod.json and 04_shots.json")
    decl = next((g for g in shots.generations if g.generation_id == entry.generation_id), None)
    if decl is None:
        raise ValueError(f"take {entry.take_id} names {entry.generation_id}, which is not in 04_shots.json")
    qc = blank_take(entry.take_id, entry.generation_id).model_dump(mode="json")
    qc["output_sha256"] = entry.output_sha256  # the review is bound to these bytes
    return {"take": entry.model_dump(mode="json"),
            "shot": {"coverage": decl.coverage, "visible": list(decl.visible), "start_state": decl.start_state,
                     "end_state": decl.end_state,
                     "phases": [{"kind": p.kind, "start_s": p.start_s, "end_s": p.end_s, "description": p.description}
                                for p in decl.choreography.phases]},
            "questions": _questions(decl, pre, script_lines or {}),
            "instructions": "Fill checks[] (result, severity on FAIL, level, evidence, reviewer human:<id>), then "
                            "`film.py review --film DIR --ingest FILE`. Leave a group UNASSESSED if you did not look.",
            "qc": qc}


def auto_evidence(pkg: Any, entry: TakeEntry, clip: Path, previous_clip: Path | None = None) -> tuple[list[GroupCheck], str]:
    """WARN-only checks from `drama.autoqc` for one take, and a note on what was skipped (never raises for missing models)."""
    try:
        from film_pipeline.drama import autoqc
        if not autoqc.models_available():
            return [], "autoqc skipped: ONNX models not installed (tools/drama_fetch_qc_models.py)"
        shots = pkg.typed["shots"]
        decl = next(g for g in shots.generations if g.generation_id == entry.generation_id)
        planned = _SCALE_OF.get(decl.camera.size) if decl.camera is not None else None
        report = autoqc.run_autoqc(Path(clip), planned_scale=planned, previous_clip=previous_clip)
    except ImportError as exc:  # cv2 / numpy are an optional extra
        return [], f"autoqc skipped: {exc.name or 'optional dependency'} not installed"
    except Exception as exc:  # a broken clip must not stop the dailies; the reviewer sees the note
        return [], f"autoqc skipped: {type(exc).__name__}: {exc}"
    by_check = {"SHOT_SCALE_MISMATCH": "camera", "SET_DRIFT": "spatial"}
    checks = []
    for issue in report.issues:
        group = by_check.get(issue.check, "character" if "IDENTITY" in issue.check else "visual")
        checks.append(auto_check(group, "autoqc", ok=False, evidence=f"{entry.output_file}: {issue.check}",
                                 level="SAMPLED", note=issue.detail))
    return checks, f"autoqc ran: {len(checks)} warning(s)"


def script_dialogue(pkg: Any) -> dict[int, str]:
    """Script line number -> "CHARACTER: text" for every dialogue element."""
    if pkg.script is None:
        return {}
    return {e.line_no: f"{e.character}: {e.text}" for s in pkg.script.scenes for e in s.elements
            if e.kind == "dialogue"}


def new_takes(film_root: Path, log: TakeLog) -> list[TakeEntry]:
    """Takes without a review sheet yet."""
    return [t for t in log.takes if not (t.review_file and (takes_dir(film_root) / t.review_file).is_file())]


def write_dailies(pkg: Any, film_root: Path, script_lines: dict[int, str] | None = None,
                  clips_dir: Path | None = None) -> list[dict[str, str]]:
    """A template per take that has none (existing sheets - possibly filled in - are never overwritten)."""
    log = load_log(film_root, pkg.header.film_id)
    lines = script_lines if script_lines is not None else script_dialogue(pkg)
    out = []
    for entry in new_takes(film_root, log):
        sheet = dailies_template(pkg, entry, lines)
        warns, note = [], "autoqc not requested (no --clips directory)"
        if clips_dir is not None:
            clip = Path(clips_dir) / entry.output_file
            if clip.is_file() and sha256_file(clip) == entry.output_sha256:
                warns, note = auto_evidence(pkg, entry, clip)
            else:
                note = f"autoqc skipped: {entry.output_file} not found in {clips_dir} or its bytes changed"
        sheet["auto_evidence"] = {"note": note, "warnings": [c.model_dump(mode="json") for c in warns]}
        rel = f"dailies/{entry.take_id}.review.json"
        path = takes_dir(film_root) / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(sheet, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        entry.review_file = rel
        out.append({"take_id": entry.take_id, "template": str(path), "autoqc": note})
    if out:
        save_log(film_root, log)
    return out


def ingest_review(film_root: Path, film_id: str, filled: dict[str, Any]) -> dict[str, Any]:
    """Validate a filled sheet (or a bare TakeQc), bind it to the logged bytes, store it and set the take's status."""
    qc_raw = dict(filled.get("qc", filled))
    claimed = qc_raw.pop("output_sha256", None)
    take = TakeQc.model_validate(qc_raw)  # raises on any invalid check (auto PASS on content, missing proof, ...)
    from film_pipeline.production.rehearsal import refuse_bot
    refuse_bot(film_root, *(c.reviewer for c in take.checks), *(c.waiver.by for c in take.checks if c.waiver))
    log = load_log(film_root, film_id)
    entry = log.get(take.take_id)
    if take.generation_id != entry.generation_id:
        raise ValueError(f"review names generation {take.generation_id}, the log has {entry.generation_id}")
    if claimed != entry.output_sha256:
        raise ValueError(f"review is not bound to this take's bytes (expected output_sha256 {entry.output_sha256[:12]}…)")
    verdict = take.verdict()
    entry.status = _STATUS_OF[verdict.status]  # type: ignore[assignment]
    entry.cause = take.cause or ""
    rel = f"reviews/{take.take_id}.qc.json"
    path = takes_dir(film_root) / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    stored = take.model_dump(mode="json")
    stored["output_sha256"] = entry.output_sha256
    path.write_text(json.dumps(stored, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    if not entry.review_file:
        entry.review_file = rel
    save_log(film_root, log)
    return {"take_id": take.take_id, "status": entry.status, "reasons": verdict.reasons, "review": str(path)}
