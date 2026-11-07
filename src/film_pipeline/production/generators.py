"""Generators named in the AI credit and the disclosure (P10-03).

Two input forms reach ``titles``, ``versions`` and ``deliver``:

* a string, ``"Google Flow Omni 1.1 Flash; Other Tool"`` - kept for compatibility; every part becomes one entry with no role;
* a JSON file (``--generators-file``), a list of ``{"role", "name", "model", "settings"}`` - the role says what the tool made
  (``video+audio``, ``image``, ``voice`` or ``music``), so one tool is never credited for another's work.

Both end up as ``GeneratorRecord`` lists (provider = name); ``generators_line`` is the text the credits card and the metadata
draft print.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from film_pipeline.drama.disclosure import GeneratorRecord

ROLES = ("video+audio", "image", "voice", "music")


def split_generators(text: str) -> list[GeneratorRecord]:
    """'Google Flow Omni 1.1 Flash; Other Tool 2' -> role-less records (the first word is the provider)."""
    out = []
    for part in (p.strip() for p in text.split(";")):
        if part:
            provider, _, model = part.partition(" ")
            out.append(GeneratorRecord(provider=provider, model=model or "unspecified", role=""))
    return out


def records_from_data(data: Any) -> list[GeneratorRecord]:
    if not isinstance(data, list) or not data:
        raise ValueError("generators file: expected a non-empty JSON list of {role, name, model, settings}")
    out = []
    for n, item in enumerate(data, 1):
        if not isinstance(item, dict):
            raise ValueError(f"generators file: entry {n} is not an object")
        unknown = sorted(set(item) - {"role", "name", "model", "settings"})
        if unknown:
            raise ValueError(f"generators file: entry {n} has unknown keys {unknown}")
        name, model, role = (str(item.get(k, "")).strip() for k in ("name", "model", "role"))
        if not name:
            raise ValueError(f"generators file: entry {n} needs a name")
        if role not in ROLES:
            raise ValueError(f"generators file: entry {n} ({name}) role must be one of {', '.join(ROLES)} (got {role!r})")
        out.append(GeneratorRecord(provider=name, model=model or "unspecified", role=role,
                                   settings=str(item.get("settings", "")).strip()))
    return out


def load_generators_file(path: Path) -> list[GeneratorRecord]:
    try:
        data = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise ValueError(f"generators file {path}: {exc}") from exc
    return records_from_data(data)


def as_records(value: str | list[GeneratorRecord] | None) -> list[GeneratorRecord]:
    if not value:
        return []
    return split_generators(value) if isinstance(value, str) else list(value)


def generators_line(value: str | list[GeneratorRecord] | None) -> str:
    """'Google Flow Omni 1.1 Flash (video+audio); Google Nano Banana 2.1 (image)'; role-less entries print bare."""
    parts = []
    for g in as_records(value):
        name = g.provider if g.model == "unspecified" else f"{g.provider} {g.model}"
        parts.append(f"{name} ({g.role})" if g.role else name)
    return "; ".join(parts)
