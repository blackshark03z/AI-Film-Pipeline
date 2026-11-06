"""Production Package: a film is a data directory (`films/<film_id>/`), not a per-film script.

`film.json` is the typed header. Stage files are optional sections; stages not yet designed stay
permissive `dict`s until the phase that owns them replaces them with typed models.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Literal

from pydantic import Field, ValidationError, field_validator

from film_pipeline.core import ContractModel
from film_pipeline.drama.script import Script, parse_fountain

Profile = Literal["drama", "narration"]
GateState = Literal["PASS", "BLOCK", "OWNER_PENDING", "NOT_RUN"]

GATE_NAMES = {
    "1": "story_audio_lock",
    "2": "directorial_coverage",
    "3": "visual_spatial",
    "4": "production_asset",
    "5": "editorial_picture_lock",
    "6": "final_master",
}

# stage key -> file name (order = production order)
STAGE_FILES: dict[str, str] = {
    "story": "01_story.json",
    "direction": "02_direction.json",
    "preprod": "03_preprod.json",
    "shots": "04_shots.json",
    "edit": "05_edit.json",
    "post": "06_post.json",
    "delivery": "07_delivery.json",
    "ledger": "ledger.json",
}
SCRIPT_FILE = "script.fountain"


class Budget(ContractModel):
    credits_estimate: float | None = Field(default=None, ge=0)
    cap_factor: float = Field(default=1.5, gt=0)

    @property
    def credits_cap(self) -> float | None:
        return None if self.credits_estimate is None else self.credits_estimate * self.cap_factor


class FilmHeader(ContractModel):
    """Contents of `film.json`."""

    film_id: str = Field(min_length=1)
    title: str = Field(min_length=1)
    profile: Profile
    language: str = "vi"
    aspect: str = "16:9"
    fps: int = Field(default=24, gt=0)
    resolution: str = "1280x720"
    generation_s: int = Field(default=8, gt=0)
    budget: Budget = Field(default_factory=Budget)
    gates: dict[str, GateState] = Field(default_factory=lambda: {k: "NOT_RUN" for k in GATE_NAMES})

    @field_validator("film_id")
    @classmethod
    def _slug(cls, v: str) -> str:
        if not v.replace("_", "").replace("-", "").isalnum():
            raise ValueError("film_id must be alphanumeric with - or _")
        return v

    @field_validator("gates")
    @classmethod
    def _gate_keys(cls, v: dict[str, GateState]) -> dict[str, GateState]:
        unknown = sorted(set(v) - set(GATE_NAMES))
        if unknown:
            raise ValueError(f"unknown gate ids {unknown}; valid: {sorted(GATE_NAMES)}")
        return {**{k: "NOT_RUN" for k in GATE_NAMES}, **v}


class PackageError(Exception):
    """Raised when a package cannot be loaded at all (no/invalid film.json)."""


class FilmPackage(ContractModel):
    root: Path
    header: FilmHeader
    stages: dict[str, dict[str, Any]] = Field(default_factory=dict)
    script: Script | None = None
    missing_stages: list[str] = Field(default_factory=list)
    issues: list[str] = Field(default_factory=list)

    def stage(self, key: str) -> dict[str, Any] | None:
        return self.stages.get(key)

    def payload(self) -> dict[str, Any]:
        return self.model_dump(mode="json")


def _read_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise PackageError(f"{path.name}: invalid JSON ({exc})") from exc


def load_package(path: str | Path) -> FilmPackage:
    """Load `films/<id>/`. Missing stages are reported, not raised; a bad `film.json` raises `PackageError`."""
    root = Path(path)
    header_path = root / "film.json"
    if not header_path.is_file():
        raise PackageError(f"film.json not found in {root}")
    raw = _read_json(header_path)
    if not isinstance(raw, dict):
        raise PackageError("film.json: expected a JSON object")
    try:
        header = FilmHeader.model_validate(raw)
    except ValidationError as exc:
        raise PackageError(f"film.json: {exc}") from exc

    stages: dict[str, dict[str, Any]] = {}
    missing: list[str] = []
    issues: list[str] = []
    for key, name in STAGE_FILES.items():
        file = root / name
        if not file.is_file():
            missing.append(key)
            continue
        try:
            data = _read_json(file)
        except PackageError as exc:
            issues.append(str(exc))
            continue
        if not isinstance(data, dict):
            issues.append(f"{name}: expected a JSON object")
            continue
        stages[key] = data

    script: Script | None = None
    script_path = root / SCRIPT_FILE
    if header.profile == "drama":
        if script_path.is_file():
            try:
                script = parse_fountain(script_path.read_text(encoding="utf-8"))
            except Exception as exc:  # parse errors surface as issues, not crashes
                issues.append(f"{SCRIPT_FILE}: {exc}")
        else:
            issues.append(f"{SCRIPT_FILE} missing (required for profile drama)")
    return FilmPackage(root=root, header=header, stages=stages, script=script,
                       missing_stages=missing, issues=issues)


def save_header(root: str | Path, header: FilmHeader) -> Path:
    path = Path(root) / "film.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(header.model_dump(mode="json"), ensure_ascii=False, indent=2) + "\n",
                    encoding="utf-8", newline="\n")
    return path
