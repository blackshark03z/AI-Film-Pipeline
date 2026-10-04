"""Schema-aligned film state and deterministic identities for the first vertical path."""

from __future__ import annotations

import hashlib
import json
from functools import lru_cache
from pathlib import Path
from typing import Any, Literal

from jsonschema import Draft202012Validator
from pydantic import BaseModel, ConfigDict, Field, model_validator


class ContractModel(BaseModel):
    model_config = ConfigDict(extra="forbid")

    def payload(self) -> dict[str, Any]:
        return self.model_dump(mode="json", exclude_unset=True)


class CharacterRef(ContractModel):
    character_id: str
    identity_version: str
    look_state_id: str
    behavior_state: str | None = None
    role_in_shot: str | None = None


class Environment(ContractModel):
    location_id: str | None = None
    location_version: str | None = None
    time_of_day: str | None = None
    weather: str | None = None
    atmosphere: str | None = None


class Movement(ContractModel):
    type: Literal["locked", "pan", "tilt", "dolly_in", "dolly_out", "tracking", "orbit", "handheld", "crane", "rack_focus", "custom"]
    purpose: str | None = None
    timing: str | None = None

    @model_validator(mode="after")
    def require_purpose_for_motion(self) -> "Movement":
        if self.type != "locked" and not self.purpose:
            raise ValueError("non-locked camera movement requires a purpose")
        return self


class Camera(ContractModel):
    framing: Literal["ECU", "CU", "MCU", "MS", "MLS", "WS", "EWS", "OTS", "TWO_SHOT", "INSERT", "CUTAWAY"]
    height: Literal["eye_level", "low", "high", "overhead", "ground_level", "dutch"]
    lens_intent: Literal["ultrawide", "wide", "normal", "portrait", "telephoto", "macro", "custom"]
    focal_hint_mm: float | None = Field(default=None, gt=0)
    movement: Movement


class Blocking(ContractModel):
    start: str
    action_beats: list[str]
    end: str
    prop_interactions: list[str] = Field(default_factory=list)


class Performance(ContractModel):
    observable_beats: list[str] = Field(default_factory=list)
    forbidden: list[str] = Field(default_factory=list)


class Lighting(ContractModel):
    key_direction: str | None = None
    contrast: str | None = None
    notes: str | None = None


class Continuity(ContractModel):
    screen_direction: str | None
    eyeline: str | None
    start_state: dict[str, Any]
    end_state: dict[str, Any]
    previous_shot_id: str | None = None
    critical_invariants: list[str] = Field(default_factory=list)


class Audio(ContractModel):
    dialogue: str | None = None
    dialogue_character_id: str | None = None
    room_tone: str | None = None
    sfx_intent: str | None = None


class References(ContractModel):
    character_asset_ids: list[str] = Field(default_factory=list)
    location_asset_ids: list[str] = Field(default_factory=list)
    wardrobe_asset_ids: list[str] = Field(default_factory=list)
    other_asset_ids: list[str] = Field(default_factory=list)


class Constraints(ContractModel):
    must_preserve: list[str] = Field(default_factory=list)
    must_avoid: list[str] = Field(default_factory=list)


class Editorial(ContractModel):
    cut_purpose: str | None = None
    handles_s: float | None = Field(default=None, ge=0)
    pickup_priority: Literal["low", "normal", "high"] | None = None


class PerformanceBeat(ContractModel):
    label: str = Field(min_length=1, max_length=40)
    description: str = Field(min_length=1)
    approx_start_s: float | None = Field(default=None, ge=0, le=8)


class PerformanceSpec(ContractModel):
    """Structured performance direction (Package-017): HOW the body moves
    (biomechanics), distinct from WHAT the shot shows. Only primary_action
    is required; quiet shots need nothing more."""
    schema_version: Literal["performance-spec-v1"] = "performance-spec-v1"
    primary_action: str = Field(min_length=1)
    action_intent: str = ""
    anticipation: str = ""
    locomotion: str = ""
    weight_transfer: str = ""
    foot_plant: str = ""
    hip_torso_rotation: str = ""
    arm_countermotion: str = ""
    contact_event: str = ""
    reaction: str = ""
    recovery: str = ""
    secondary_motion: str = ""
    motion_energy: Literal["low", "moderate", "high"] | None = None
    motion_risk_class: Literal["LOW", "MEDIUM", "HIGH", "EXTREME"] | None = None
    beats: list[PerformanceBeat] = []

    def filled_biomechanics(self) -> dict[str, str]:
        """The non-empty biomechanics fields, in frozen order."""
        order = ("anticipation", "locomotion", "weight_transfer",
                 "foot_plant", "hip_torso_rotation", "arm_countermotion",
                 "contact_event", "reaction", "recovery",
                 "secondary_motion")
        return {k: getattr(self, k) for k in order if getattr(self, k)}

    def digest(self) -> str:
        return sha256(canonical_json(self.model_dump(mode="json")))


class ActionIntent(ContractModel):
    """Why this character acts NOW and what the action is meant to
    accomplish (Package-018). Distinct layers: NarrativeBeat = what story
    beat must occur; ActionIntent = why the character acts and to what
    end; PerformanceSpec = how the body performs it. Every field must be
    recoverable from authoritative upstream truth — never invented."""
    schema_version: Literal["action-intent-v1"] = "action-intent-v1"
    trigger: str = ""
    perception: str = ""
    character_goal: str = ""
    motivation: str = ""
    obstacle_or_pressure: str = ""
    chosen_action: str = ""
    intended_outcome: str = ""
    resulting_state: str = ""
    next_decision: str = ""
    visual_legibility_requirements: list[str] = []
    stakes: str = ""
    urgency: str = ""
    knowledge_state: str = ""

    def digest(self) -> str:
        return sha256(canonical_json(self.model_dump(mode="json")))


class ShotSpec(ContractModel):
    schema_version: Literal["1.0.0"]
    spec_version: int = Field(ge=1)
    shot_id: str = Field(min_length=1)
    scene_id: str = Field(min_length=1)
    dramatic_purpose: str = Field(min_length=3)
    duration_target_s: float = Field(gt=0)
    shot_type: Literal["establishing", "insert", "cutaway", "reaction", "dialogue", "performance", "action", "transition", "hero", "other"]
    characters: list[CharacterRef]
    environment: Environment | None = None
    camera: Camera
    blocking: Blocking
    performance: Performance | None = None
    lighting: Lighting | None = None
    continuity: Continuity
    audio: Audio | None = None
    references: References | None = None
    constraints: Constraints | None = None
    editorial: Editorial | None = None
    performance_spec: PerformanceSpec | None = None
    action_intent: ActionIntent | None = None


class ProviderCapabilities(ContractModel):
    profile_version: str
    provider_id: str
    transport_type: Literal["official_api", "browser_cookie", "gateway", "manual", "other"]
    supports_text_to_video: bool = True
    supports_image_input: bool = False
    supports_start_frame: bool = False
    supports_end_frame: bool = False
    supports_multi_reference: bool = False
    supports_seed: bool = False
    supports_native_audio: bool = False
    supports_duration_control: bool = False
    supports_aspect_ratio: bool = False
    supports_resolution_control: bool = False
    supports_negative_prompt: bool = False
    supports_batch: bool = False
    supports_cancel: bool = False
    supports_stable_external_job_id: bool = False
    notes: list[str] = Field(default_factory=list)


class PromptPlan(ContractModel):
    prompt_plan_id: str
    compiler_version: str
    input_hash: str
    shot_id: str
    shot_spec_version: int
    provider_id: str
    canonical_blocks: dict[str, Any]
    provider_prompt: str
    mapped_controls: dict[str, Any]
    unsupported_controls: list[str]
    degraded_controls: list[str]
    warnings: list[str]


class RoutingDecision(ContractModel):
    routing_decision_id: str
    shot_id: str
    provider_id: str
    reasons: list[str]
    required_capabilities: list[str]
    difficulty: dict[str, Any]
    fallback_provider_ids: list[str] = Field(default_factory=list)
    benchmark_policy_version: str | None = None


class GenerationAttempt(ContractModel):
    generation_attempt_id: str
    shot_id: str
    shot_spec_version: int = Field(ge=1)
    shot_spec_hash: str
    prompt_plan_hash: str
    routing_decision_id: str
    provider_id: str
    provider_job_id: str | None = None
    status: Literal["created", "submitted", "running", "succeeded", "failed", "cancelled"]
    started_at: str
    completed_at: str | None = None
    output_asset_ids: list[str] = Field(default_factory=list)
    error_code: str | None = None
    error_detail: str | None = None
    qc_report_id: str | None = None


def canonical_json(value: Any) -> str:
    if isinstance(value, ShotSpec):
        dump = value.model_dump(mode="json")
        # Legacy identity stability (Packages 017/018): shots without the
        # extension fields hash exactly as before those fields existed;
        # shots WITH one hash with it included (versioned semantics).
        for extension in ("performance_spec", "action_intent"):
            if dump.get(extension) is None:
                dump.pop(extension, None)
        value = dump
    elif isinstance(value, ContractModel):
        # Normalize schema defaults before hashing: omitted and explicit defaults
        # describe the same model, while payload() retains original field presence.
        value = value.model_dump(mode="json")
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False)


def sha256(value: Any) -> str:
    return hashlib.sha256(canonical_json(value).encode("utf-8")).hexdigest()


@lru_cache(maxsize=None)
def _validator(schema_name: str) -> Draft202012Validator:
    schema_path = Path(__file__).resolve().parents[2] / "schemas" / f"{schema_name}.schema.json"
    schema = json.loads(schema_path.read_text(encoding="utf-8"))
    Draft202012Validator.check_schema(schema)
    return Draft202012Validator(schema)


def validate_contract(schema_name: str, payload: dict[str, Any]) -> None:
    _validator(schema_name).validate(payload)


def load_shot(path: str | Path) -> ShotSpec:
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    validate_contract("shot_spec", payload)
    return ShotSpec.model_validate(payload)
