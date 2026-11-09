"""Routing (section 3 item 8) and the route preflight (item 3): does the routed model cover this shot?

``film.json`` ``route`` is the film's default (provider + model + tier, default Flow Omni 1.2 Flash TEST); a shot's
``route`` overrides it. ``route_issues`` checks a ``GenerationRequest`` against the routed entry before any spend:
BLOCK when the model cannot do it (duration, tier, aspect, frame roles, reference count, prompt length, a dialogue shot
on a model with ``native_audio`` false), WARN when nobody knows yet (dialogue on ``native_audio`` unknown).
"""
from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import Field

from ..core import ContractModel
from .capability import DEFAULT_MODEL, DEFAULT_PROVIDER, ModelCapability, get_capability
from .request import GenerationRequest, Tier


class RouteSpec(ContractModel):
    provider: str = Field(default=DEFAULT_PROVIDER, min_length=1)
    model: str = Field(default=DEFAULT_MODEL, min_length=1)
    tier: Tier = "TEST"

    def capability(self) -> ModelCapability:
        return get_capability(self.provider, self.model)


ROUTES_FILE = Path(__file__).resolve().parent / "routes.json"


class RouteDefaults(ContractModel):
    """``providers/routes.json``: the production default (Flow), the experiment default (Owner 2026-11-09: MiniMax H3
    480p through Vilao omh3) and per-day caps per money unit."""

    production: RouteSpec
    experiment: RouteSpec
    daily_caps: dict[str, float] = Field(default_factory=dict)
    source: str = ""


@lru_cache(maxsize=1)
def route_defaults() -> RouteDefaults:
    return RouteDefaults.model_validate(json.loads(ROUTES_FILE.read_text(encoding="utf-8")))


def resolve_route(header: object, decl: object | None = None) -> RouteSpec:
    """The shot's own route if it has one, else the film's explicit ``route``, else the experiment default for a film
    marked ``experiment``, else the production default (Flow: every existing film)."""
    own = getattr(decl, "route", None) if decl is not None else None
    if own is not None:
        return own
    fields_set = getattr(header, "model_fields_set", set())
    if "route" in fields_set and getattr(header, "route", None) is not None:
        return header.route  # type: ignore[attr-defined]
    defaults = route_defaults()
    return defaults.experiment if getattr(header, "experiment", False) else defaults.production


class RouteIssue(ContractModel):
    code: str
    severity: Literal["BLOCK", "WARN"]
    detail: str


def route_issues(request: GenerationRequest, cap: ModelCapability) -> list[RouteIssue]:
    out: list[RouteIssue] = []
    name = f"{cap.provider}/{cap.model}"

    def block(code: str, detail: str) -> None:
        out.append(RouteIssue(code=code, severity="BLOCK", detail=f"{name}: {detail}"))

    lo, hi = cap.duration_s
    if not lo <= request.duration_s <= hi:
        block("ROUTE_DURATION", f"{request.duration_s} s is outside {lo}-{hi} s")
    if request.tier not in cap.tiers:
        block("ROUTE_TIER", f"tier {request.tier} is not offered (tiers: {sorted(cap.tiers)})")
    if cap.aspects and request.aspect not in cap.aspects:
        block("ROUTE_ASPECT", f"aspect {request.aspect} is not offered ({', '.join(cap.aspects)})")
    for role in request.frame_roles:
        if role not in cap.frame_roles:
            block("ROUTE_FRAME_ROLE", f"no {role} input")
    if len(request.references) > cap.max_refs:
        block("ROUTE_TOO_MANY_REFS", f"{len(request.references)} reference(s), at most {cap.max_refs}")
    if request.references and request.frame_roles and not cap.mix_frames_and_refs:
        block("ROUTE_FRAMES_AND_REFS", "frame roles and reference images cannot be mixed in one request")
    if cap.prompt_limit_chars is not None and len(request.prompt) > cap.prompt_limit_chars:
        block("ROUTE_PROMPT_TOO_LONG", f"{len(request.prompt)} characters, limit {cap.prompt_limit_chars}")
    if request.audio_mode == "NATIVE_DIALOGUE":
        if cap.native_audio == "false":
            block("ROUTE_NO_NATIVE_AUDIO", "dialogue shot on a silent model (route it elsewhere or add a TTS + "
                                           "lip-sync stage)")
        elif cap.native_audio == "unknown":
            out.append(RouteIssue(code="ROUTE_NATIVE_AUDIO_UNKNOWN", severity="WARN",
                                  detail=f"{name}: dialogue shot; whether this model speaks the line is unverified"))
    return out
