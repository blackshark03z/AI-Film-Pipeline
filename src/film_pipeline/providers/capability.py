"""Capability registry: what each provider+model can do and what it costs, as data (``registry/*.json``).

One entry per (provider, model). The registry - not an ``if`` in the ledger - says which normalized results are charged
(``charged_on``) and how a provider's raw outcome (Flow result string, HTTP status, API error code) maps onto the five
normalized results. Fields nobody has measured yet are listed in the entry's ``unverified`` and stay that way until a
live probe (phase B) settles them.

Normalized results (section 3 item 4):

    NOT_SUBMITTED    nothing reached the provider: zero cost
    REJECTED_POLICY  moderation refused the job
    PROVIDER_FAILED  the provider took the job and failed it
    AMBIGUOUS        submitted, outcome unknown (Flow binding/timeouts)
    PASSED           output received
"""
from __future__ import annotations

import json
import math
from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import Field, model_validator

from ..core import ContractModel, ProviderCapabilities

REGISTRY_DIR = Path(__file__).resolve().parent / "registry"

NormalizedResult = Literal["NOT_SUBMITTED", "REJECTED_POLICY", "PROVIDER_FAILED", "AMBIGUOUS", "PASSED"]
NORMALIZED: tuple[str, ...] = ("NOT_SUBMITTED", "REJECTED_POLICY", "PROVIDER_FAILED", "AMBIGUOUS", "PASSED")
CostUnit = Literal["credits", "USD", "VND"]
FrameRole = Literal["first_frame", "last_frame"]
NativeAudio = Literal["true", "false", "unknown"]

DEFAULT_PROVIDER = "flow"
DEFAULT_MODEL = "omni-1.2-flash"


class PriceSpec(ContractModel):
    """``tiered_per_second``: ``rate`` per started second up to ``threshold_s``, ``rate_above`` per second after it
    (Flow Omni 1.2 Flash). ``per_second``: ``rates[native resolution]`` per started second. ``per_request``:
    ``rates[native resolution]`` (or ``amount``) per request, whatever the length."""

    kind: Literal["tiered_per_second", "per_second", "per_request"]
    unit: CostUnit
    rate: float | None = Field(default=None, ge=0)
    threshold_s: int | None = Field(default=None, ge=0)
    rate_above: float | None = Field(default=None, ge=0)
    rates: dict[str, float] = Field(default_factory=dict)
    amount: float | None = Field(default=None, ge=0)

    @model_validator(mode="after")
    def _complete(self) -> "PriceSpec":
        if self.kind == "tiered_per_second" and None in (self.rate, self.threshold_s, self.rate_above):
            raise ValueError("tiered_per_second needs rate, threshold_s and rate_above")
        if self.kind == "per_second" and not self.rates:
            raise ValueError("per_second needs rates per native resolution")
        if self.kind == "per_request" and self.amount is None and not self.rates:
            raise ValueError("per_request needs amount or rates")
        return self


class ErrorMap(ContractModel):
    """Raw outcome -> normalized result. ``exact`` is tried first, then ``prefix`` (longest first); anything else is
    ``default``. Keys are provider strings: Flow result strings, ``http_<status>``, API error codes, task statuses."""

    exact: dict[str, NormalizedResult] = Field(default_factory=dict)
    prefix: dict[str, NormalizedResult] = Field(default_factory=dict)
    default: NormalizedResult = "AMBIGUOUS"


class ModelCapability(ContractModel):
    provider: str = Field(min_length=1)
    model: str = Field(min_length=1)          # registry id, e.g. "omni-1.2-flash", "h3-480p"
    display_name: str = Field(min_length=1)   # what take logs and receipts show ("Omni 1.2 Flash 360p")
    aliases: list[str] = Field(default_factory=list)  # free-text model names older records carry
    adapter: Literal["flow_ui", "openai_videos", "minimax"]
    transport: Literal["official_api", "browser_cookie", "gateway", "manual", "other"]
    api_model: str = ""                       # the model id the provider's API expects
    base_url: str = ""
    auth_env: str = ""                        # env var holding the key; the key itself is never stored
    duration_s: tuple[int, int]               # inclusive range
    tiers: dict[str, str]                     # TEST/FINAL -> native resolution; a missing tier is not offered
    aspects: list[str] = Field(default_factory=list)  # [] = not restricted
    frame_roles: list[FrameRole] = Field(default_factory=list)
    max_refs: int = Field(default=0, ge=0)
    mix_frames_and_refs: bool = True          # MiniMax: image-to-video roles and reference roles cannot be mixed
    native_audio: NativeAudio = "unknown"
    prompt_limit_chars: int | None = Field(default=None, gt=0)
    price: PriceSpec
    error_map: ErrorMap = Field(default_factory=ErrorMap)
    charged_on: list[NormalizedResult]
    request_fields: dict[str, str] = Field(default_factory=dict)  # neutral field -> provider body field
    size_by_aspect: dict[str, dict[str, str]] = Field(default_factory=dict)  # native resolution -> aspect -> size
    unverified: list[str] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def _consistent(self) -> "ModelCapability":
        lo, hi = self.duration_s
        if not 0 < lo <= hi:
            raise ValueError(f"{self.key}: bad duration range {self.duration_s}")
        if set(self.tiers) - {"TEST", "FINAL"}:
            raise ValueError(f"{self.key}: tiers must be TEST/FINAL")
        if "last_frame" in self.frame_roles and "first_frame" not in self.frame_roles:
            raise ValueError(f"{self.key}: last_frame needs first_frame")
        if self.price.kind != "tiered_per_second" and self.price.rates:
            missing = set(self.tiers.values()) - set(self.price.rates)
            if missing:
                raise ValueError(f"{self.key}: no price for native resolution(s) {sorted(missing)}")
        return self

    @property
    def key(self) -> tuple[str, str]:
        return (self.provider, self.model)

    # ---- money ---------------------------------------------------------------------------------------------------
    def price_of(self, seconds: float, tier: str = "TEST") -> float:
        """Cost of one request of ``seconds`` at ``tier``, in ``price.unit``. Seconds are rounded up."""
        p, s = self.price, max(0, math.ceil(seconds))
        if p.kind == "tiered_per_second":
            assert p.rate is not None and p.threshold_s is not None and p.rate_above is not None
            return float(p.rate * s if s <= p.threshold_s else p.rate * p.threshold_s + p.rate_above * (s - p.threshold_s))
        native = self.tiers.get(tier)
        if p.kind == "per_second":
            if native not in p.rates:
                raise ValueError(f"{self.key}: tier {tier} is not offered")
            return round(p.rates[native] * s, 6)
        if p.rates:
            if native not in p.rates:
                raise ValueError(f"{self.key}: tier {tier} is not offered")
            return float(p.rates[native])
        return float(p.amount or 0.0)

    # ---- results -------------------------------------------------------------------------------------------------
    def normalize(self, raw: object) -> NormalizedResult:
        """Map a raw outcome onto the five normalized results (an already normalized one maps to itself)."""
        text = str(raw if raw is not None else "None")
        if text in self.error_map.exact:
            return self.error_map.exact[text]
        for prefix in sorted(self.error_map.prefix, key=len, reverse=True):
            if text.startswith(prefix):
                return self.error_map.prefix[prefix]
        if text in NORMALIZED:
            return text  # type: ignore[return-value]
        return self.error_map.default

    def charged(self, result: str) -> bool:
        return result in self.charged_on

    def provider_capabilities(self) -> ProviderCapabilities:
        """The core router's view of this entry."""
        return ProviderCapabilities(
            profile_version=f"registry:{self.provider}/{self.model}", provider_id=self.provider,
            transport_type=self.transport, supports_image_input=bool(self.frame_roles or self.max_refs),
            supports_start_frame="first_frame" in self.frame_roles, supports_end_frame="last_frame" in self.frame_roles,
            supports_multi_reference=self.max_refs > 1, supports_native_audio=self.native_audio == "true",
            supports_duration_control=self.duration_s[0] != self.duration_s[1], supports_aspect_ratio=bool(self.aspects),
            supports_resolution_control=len(set(self.tiers.values())) > 1,
            supports_cancel=False, supports_stable_external_job_id=self.adapter != "flow_ui",
            notes=[f"UNVERIFIED {u}" for u in self.unverified] + self.notes)


class RegistryFile(ContractModel):
    entries: list[ModelCapability]


@lru_cache(maxsize=4)
def load_registry(folder: str | None = None) -> dict[tuple[str, str], ModelCapability]:
    out: dict[tuple[str, str], ModelCapability] = {}
    for path in sorted(Path(folder or REGISTRY_DIR).glob("*.json")):
        for entry in RegistryFile.model_validate_json(path.read_text(encoding="utf-8")).entries:
            if entry.key in out:
                raise ValueError(f"duplicate registry entry {entry.key} ({path.name})")
            out[entry.key] = entry
    return out


def get_capability(provider: str | None = None, model: str | None = None) -> ModelCapability:
    """The entry for (provider, model). ``model`` may be a registry id, the display name or an alias. Missing provider
    = Flow (every record before provider adapters is a Flow record)."""
    provider = provider or DEFAULT_PROVIDER
    reg = load_registry()
    if model is None:
        model = DEFAULT_MODEL if provider == DEFAULT_PROVIDER else ""
    if (provider, model) in reg:
        return reg[(provider, model)]
    for entry in reg.values():
        if entry.provider == provider and (model == entry.display_name or model in entry.aliases):
            return entry
    raise KeyError(f"no registry entry for provider {provider!r} model {model!r}")


def charging_entry(provider: str | None, model: str | None) -> ModelCapability:
    """The entry whose ``charged_on``/``error_map`` rules a stored record: an exact match, else the provider's default
    (a Flow receipt from before the registry may name an older Flow model; Flow's charging rules did not change)."""
    try:
        return get_capability(provider, model)
    except KeyError:
        provider = provider or DEFAULT_PROVIDER
        if provider == DEFAULT_PROVIDER:
            return get_capability(DEFAULT_PROVIDER, DEFAULT_MODEL)
        raise
