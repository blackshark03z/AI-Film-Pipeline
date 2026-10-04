"""Deterministic, provider-neutral prompt compilation."""

from __future__ import annotations

import re
from typing import Any

from .core import PromptPlan, ProviderCapabilities, ShotSpec, canonical_json, sha256, validate_contract

COMPILER_VERSION = "deterministic-v1"
BLOCK_ORDER = (
    "SHOT / DRAMATIC PURPOSE",
    "SUBJECT / CHARACTER LOCK",
    "ACTION / PERFORMANCE",
    "ENVIRONMENT / WORLD LOCK",
    "CAMERA / LENS / MOVEMENT",
    "BLOCKING / START-END STATE",
    "LIGHTING / STYLE",
    "AUDIO / DIALOGUE",
    "CONTINUITY CONSTRAINTS",
    "NEGATIVE / FORBIDDEN BEHAVIOR",
)


def _data(value: Any) -> Any:
    return value.model_dump(mode="json", exclude_none=True) if value is not None else None


def compile_prompt(
    shot: ShotSpec,
    capabilities: ProviderCapabilities,
    *,
    compiler_version: str = COMPILER_VERSION,
    template_version: str = "canonical-blocks-v1",
    reference_hashes: dict[str, str] | None = None,
) -> PromptPlan:
    """Compile the same creative/config inputs to the same schema-valid PromptPlan."""
    blocks = dict(zip(BLOCK_ORDER, (
        {"shot_type": shot.shot_type, "dramatic_purpose": shot.dramatic_purpose, "duration_target_s": shot.duration_target_s},
        {"characters": [_data(character) for character in shot.characters], "references": _data(shot.references)},
        # performance_spec is carried only when present so legacy plans
        # compile byte-identically (no canonical-block drift).
        ({"action_beats": shot.blocking.action_beats, "performance": _data(shot.performance)}
         if shot.performance_spec is None else
         {"action_beats": shot.blocking.action_beats, "performance": _data(shot.performance),
          "performance_spec": _data(shot.performance_spec)}),
        {"environment": _data(shot.environment)},
        {"camera": _data(shot.camera)},
        {"blocking": _data(shot.blocking), "start_state": shot.continuity.start_state, "end_state": shot.continuity.end_state},
        {"lighting": _data(shot.lighting)},
        {"audio": _data(shot.audio)},
        {"continuity": _data(shot.continuity), "must_preserve": shot.constraints.must_preserve if shot.constraints else []},
        {"performance_forbidden": shot.performance.forbidden if shot.performance else [], "must_avoid": shot.constraints.must_avoid if shot.constraints else []},
    )))
    references = _data(shot.references) or {}
    reference_ids = [asset for group in references.values() for asset in group]
    if reference_hashes is not None:
        if (len(reference_ids) != len(set(reference_ids))
                or set(reference_hashes) != set(reference_ids)
                or any(not isinstance(value, str) or not re.fullmatch(r"[0-9a-f]{64}", value)
                       for value in reference_hashes.values())):
            raise ValueError("reference hash binding must match every exact image Asset ID")
    input_basis = {
        # ShotSpec carries the referenced creative identity/look/location versions.
        # Only declared capability flags enter this derived-input hash. Profile
        # notes and transport metadata are never creative inputs.
        "shot_spec_hash": sha256(shot),
        "capabilities_hash": sha256({
            key: value for key, value in capabilities.model_dump(mode="json").items()
            if key in {"provider_id", "profile_version"} or key.startswith("supports_")
        }),
        "compiler_version": compiler_version,
        "template_version": template_version,
    }
    if reference_hashes is not None:
        input_basis["reference_hashes"] = reference_hashes
    input_hash = sha256(input_basis)
    mapped: dict[str, Any] = {"text_fallbacks": {}}
    unsupported: list[str] = []
    degraded: list[str] = []
    warnings: list[str] = []

    def control(name: str, requested: Any, supported: bool, fallback: str) -> None:
        if not requested:
            return
        if supported:
            mapped[name] = requested
        else:
            unsupported.append(name)
            degraded.append(f"{name} converted to textual intent: {fallback}")
            mapped["text_fallbacks"][name] = requested
            warnings.append(f"{capabilities.provider_id} does not support {name}; review textual fallback")

    control("duration_control", shot.duration_target_s, capabilities.supports_duration_control, "target duration")
    image_input = ([{"asset_id": asset_id, "sha256": reference_hashes[asset_id]}
                    for asset_id in reference_ids] if reference_hashes is not None
                   else reference_ids)
    control("image_input", image_input, capabilities.supports_image_input, "reference asset IDs")
    if len(reference_ids) > 1:
        control("multi_reference", reference_ids, capabilities.supports_multi_reference, "multiple reference asset IDs")
    audio_intent = _data(shot.audio)
    if audio_intent and any(value for value in audio_intent.values()):
        control("native_audio", audio_intent, capabilities.supports_native_audio, "audio and dialogue intent")
    negatives = (shot.constraints.must_avoid if shot.constraints else []) + (shot.performance.forbidden if shot.performance else [])
    control("negative_prompt", negatives, capabilities.supports_negative_prompt, "forbidden behavior")
    if not capabilities.supports_text_to_video:
        unsupported.append("text_to_video")
        warnings.append(f"{capabilities.provider_id} cannot execute text-to-video")

    # All creative blocks remain in the prompt even when a structured control is unavailable.
    provider_prompt = "\n\n".join(
        f"{name}\n{canonical_json(content)}" for name, content in blocks.items()
    )
    plan = PromptPlan(
        prompt_plan_id=f"plan_{input_hash}",
        compiler_version=compiler_version,
        input_hash=input_hash,
        shot_id=shot.shot_id,
        shot_spec_version=shot.spec_version,
        provider_id=capabilities.provider_id,
        canonical_blocks=blocks,
        provider_prompt=provider_prompt,
        mapped_controls=mapped,
        unsupported_controls=unsupported,
        degraded_controls=degraded,
        warnings=warnings,
    )
    validate_contract("prompt_plan", plan.payload())
    return plan
