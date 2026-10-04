"""Performance prompt compiler (Package-017 Phase 5).

Version flow-r2v-performance-compact-v1: the Flow R2V wire reduction for
shots that carry structured performance direction. EXTENDS the proven
compact reduction — same provider rails (fail-closed on unqualified
provider, missing/ambiguous image input, wrong duration, marker
collisions, over-length creative bodies), same single-line + marker
serialization — and adds exactly two bounded clauses:

- BODY direction from the BodyProportionAuthority (directional
  constraint only — never fake anthropometric precision);
- MOVEMENT clause from the PerformanceSpec's filled biomechanics +
  beat labels (compiled per shot — no prompt stuffing: empty fields
  render nothing, and the whole body must fit the 500-char / 75-word
  creative limit or compilation fails closed).

Film Core never sees Flow wording: this module sits beside the Flow
adapter and is selected per-shot by the 017 runner through the runtime's
optional prompt_compiler hook.
"""
from __future__ import annotations

from .core import ActionIntent, PromptPlan, sha256
from .performance import BodyProportionAuthority, PerformanceSpec
from .flow_r2v_runtime import (
    MAX_PROMPT_CHARS, MAX_PROMPT_WORDS, _clean_creative, _scan_creative,
    film_marker, FlowR2VPrompt)

VERSION = "flow-r2v-performance-compact-v1"
CAUSAL_VERSION = "flow-r2v-causal-compact-v1"

# Bounded movement clause: at most this many biomechanics phrases render,
# longest first is NOT used — frozen field order keeps output stable.
MAX_MOVEMENT_PHRASES = 5


def compile_performance_r2v_prompt(
        plan: PromptPlan, provider_job_id: str, *, model: str,
        performance_spec: PerformanceSpec,
        body_authority: BodyProportionAuthority) -> FlowR2VPrompt:
    from .flow_r2v_runtime import OwnerAmbiguityGate
    marker = film_marker(provider_job_id)
    if plan.provider_id != "flow_veo":
        raise OwnerAmbiguityGate("FLOW_R2V_PROVIDER_UNQUALIFIED")
    image_input = plan.mapped_controls.get("image_input")
    if (not isinstance(image_input, list) or len(image_input) != 1
            or not isinstance(image_input[0], dict)
            or set(image_input[0]) != {"asset_id", "sha256"}
            or not image_input[0].get("sha256", "").isalnum()):
        raise OwnerAmbiguityGate("FLOW_R2V_EXACT_IMAGE_INPUT_REQUIRED")
    _scan_creative(plan.canonical_blocks)
    blocks = plan.canonical_blocks
    try:
        shot_block = blocks["SHOT / DRAMATIC PURPOSE"]
        camera = blocks["CAMERA / LENS / MOVEMENT"]["camera"]
        characters = (blocks["SUBJECT / CHARACTER LOCK"].get("characters")
                      or [])
        action = blocks["ACTION / PERFORMANCE"]
        environment = (blocks["ENVIRONMENT / WORLD LOCK"].get("environment")
                       or {})
        blocking = blocks["BLOCKING / START-END STATE"]["blocking"]
        continuity = blocks["CONTINUITY CONSTRAINTS"]
        audio = blocks["AUDIO / DIALOGUE"].get("audio") or {}
        negatives = blocks["NEGATIVE / FORBIDDEN BEHAVIOR"]
    except (KeyError, TypeError):
        raise OwnerAmbiguityGate(
            "FLOW_R2V_CREATIVE_BLOCKS_INVALID") from None
    if shot_block.get("duration_target_s") != 8:
        raise OwnerAmbiguityGate("FLOW_R2V_DURATION_UNSUPPORTED")

    parts = [f"{shot_block['shot_type']} shot: "
             f"{_clean_creative(shot_block['dramatic_purpose'])}"]
    movement = camera.get("movement") or {}
    move = movement.get("type", "locked")
    if movement.get("purpose"):
        move += f" ({_clean_creative(movement['purpose'])})"
    parts.append(f"{camera.get('framing')} from {camera.get('height')}, "
                 f"{camera.get('lens_intent')} lens, {move} camera")
    for character in characters:
        if not isinstance(character, dict):
            raise OwnerAmbiguityGate("FLOW_R2V_CREATIVE_BLOCKS_INVALID")
        described = ", ".join(_clean_creative(character[key]) for key in
                              ("character_id", "role_in_shot",
                               "behavior_state") if character.get(key))
        # BODY direction: the Owner's directional constraint rides with
        # the subject clause — never a fabricated measurement.
        body = ", ".join(body_authority.directional_constraints())
        parts.append("Subject: " + (described + ", " + body if body
                                    else described))
    performance = action.get("performance") or {}
    beats = [_clean_creative(beat) for beat in
             (action.get("action_beats") or []) +
             (performance.get("observable_beats") or [])]
    if beats:
        parts.append("Action: " + "; ".join(beats))
    # MOVEMENT clause: only filled biomechanics VALUES (complete short
    # phrases), frozen field order, beat labels first, hard phrase cap
    # (no stuffing).
    movement = []
    if performance_spec.beats:
        movement.append("beats: " + ", ".join(
            beat.label for beat in performance_spec.beats))
    movement.extend(performance_spec.filled_biomechanics().values())
    if movement:
        parts.append("Movement: " + "; ".join(
            movement[:MAX_MOVEMENT_PHRASES]))
    setting = [_clean_creative(environment[key]) for key in
               ("time_of_day", "weather", "atmosphere")
               if environment.get(key)]
    if setting:
        parts.append("Setting: " + ", ".join(setting))
    parts.append(f"Start: {_clean_creative(blocking['start'])}; "
                 f"End: {_clean_creative(blocking['end'])}")
    preserve = [_clean_creative(value)
                for value in continuity.get("must_preserve") or []]
    if preserve:
        parts.append("Preserve: " + "; ".join(preserve))
    avoid = list(dict.fromkeys(
        [_clean_creative(value) for value in
         (negatives.get("must_avoid") or []) +
         (negatives.get("performance_forbidden") or [])]))
    if avoid:
        parts.append("Avoid: " + "; ".join(avoid))
    if audio.get("dialogue"):
        parts.append("Dialogue: " + _clean_creative(audio["dialogue"]))
    body = ". ".join(parts) + "."
    if len(body) > MAX_PROMPT_CHARS or \
            len(body.split()) > MAX_PROMPT_WORDS:
        raise OwnerAmbiguityGate(
            "FLOW_R2V_COMPACT_PROMPT_LIMIT; explicit creative reduction "
            "required")
    return FlowR2VPrompt(body + " " + marker, marker, sha256(plan),
                         version=VERSION, model=model)


def compile_causal_r2v_prompt(
        plan: PromptPlan, provider_job_id: str, *, model: str,
        performance_spec: PerformanceSpec,
        body_authority: BodyProportionAuthority,
        action_intent: ActionIntent) -> FlowR2VPrompt:
    """Causal wire reduction (Package-018, flow-r2v-causal-compact-v1).

    Same rails as the performance compiler; the rendering order becomes
    SCENE CONTEXT -> ACTION INTENT (trigger -> goal -> action) ->
    PERFORMANCE DIRECTION -> camera/visual -> outcome. Causal order is
    preserved; only non-empty authoritative fields render; the same
    500-char/75-word fail-closed envelope applies."""
    from .flow_r2v_runtime import OwnerAmbiguityGate
    marker = film_marker(provider_job_id)
    if plan.provider_id != "flow_veo":
        raise OwnerAmbiguityGate("FLOW_R2V_PROVIDER_UNQUALIFIED")
    image_input = plan.mapped_controls.get("image_input")
    if (not isinstance(image_input, list) or len(image_input) != 1
            or not isinstance(image_input[0], dict)
            or set(image_input[0]) != {"asset_id", "sha256"}
            or not image_input[0].get("sha256", "").isalnum()):
        raise OwnerAmbiguityGate("FLOW_R2V_EXACT_IMAGE_INPUT_REQUIRED")
    _scan_creative(plan.canonical_blocks)
    blocks = plan.canonical_blocks
    try:
        shot_block = blocks["SHOT / DRAMATIC PURPOSE"]
        camera = blocks["CAMERA / LENS / MOVEMENT"]["camera"]
        characters = (blocks["SUBJECT / CHARACTER LOCK"].get("characters")
                      or [])
        action = blocks["ACTION / PERFORMANCE"]
        environment = (blocks["ENVIRONMENT / WORLD LOCK"].get("environment")
                       or {})
        blocking = blocks["BLOCKING / START-END STATE"]["blocking"]
        continuity = blocks["CONTINUITY CONSTRAINTS"]
        audio = blocks["AUDIO / DIALOGUE"].get("audio") or {}
        negatives = blocks["NEGATIVE / FORBIDDEN BEHAVIOR"]
    except (KeyError, TypeError):
        raise OwnerAmbiguityGate(
            "FLOW_R2V_CREATIVE_BLOCKS_INVALID") from None
    if shot_block.get("duration_target_s") != 8:
        raise OwnerAmbiguityGate("FLOW_R2V_DURATION_UNSUPPORTED")

    parts = [f"{shot_block['shot_type']} shot: "
             f"{_clean_creative(shot_block['dramatic_purpose'])}"]
    movement = camera.get("movement") or {}
    move = movement.get("type", "locked")
    if movement.get("purpose"):
        move += f" ({_clean_creative(movement['purpose'])})"
    parts.append(f"{camera.get('framing')} from {camera.get('height')}, "
                 f"{camera.get('lens_intent')} lens, {move} camera")
    for character in characters:
        if not isinstance(character, dict):
            raise OwnerAmbiguityGate("FLOW_R2V_CREATIVE_BLOCKS_INVALID")
        described = ", ".join(_clean_creative(character[key]) for key in
                              ("character_id", "role_in_shot",
                               "behavior_state") if character.get(key))
        body = ", ".join(body_authority.directional_constraints())
        parts.append("Subject: " + (described + ", " + body if body
                                    else described))
    # causal chain in causal order — only authoritative, non-empty fields
    if action_intent.trigger:
        parts.append("Trigger: " + _clean_creative(action_intent.trigger))
    if action_intent.character_goal:
        parts.append("Goal: " +
                     _clean_creative(action_intent.character_goal))
    performance = action.get("performance") or {}
    beats = [_clean_creative(beat) for beat in
             (action.get("action_beats") or []) +
             (performance.get("observable_beats") or [])]
    if beats:
        parts.append("Action: " + "; ".join(beats))
    clause = []
    if performance_spec.beats:
        clause.append("beats: " + ", ".join(
            beat.label for beat in performance_spec.beats))
    clause.extend(performance_spec.filled_biomechanics().values())
    if clause:
        parts.append("Movement: " + "; ".join(
            clause[:MAX_MOVEMENT_PHRASES]))
    if action_intent.intended_outcome:
        parts.append("Outcome: " +
                     _clean_creative(action_intent.intended_outcome))
    setting = [_clean_creative(environment[key]) for key in
               ("time_of_day", "weather", "atmosphere")
               if environment.get(key)]
    if setting:
        parts.append("Setting: " + ", ".join(setting))
    parts.append(f"Start: {_clean_creative(blocking['start'])}; "
                 f"End: {_clean_creative(blocking['end'])}")
    preserve = [_clean_creative(value)
                for value in continuity.get("must_preserve") or []]
    if preserve:
        parts.append("Preserve: " + "; ".join(preserve))
    avoid = list(dict.fromkeys(
        [_clean_creative(value) for value in
         (negatives.get("must_avoid") or []) +
         (negatives.get("performance_forbidden") or [])]))
    if avoid:
        parts.append("Avoid: " + "; ".join(avoid))
    if audio.get("dialogue"):
        parts.append("Dialogue: " + _clean_creative(audio["dialogue"]))
    body = ". ".join(parts) + "."
    if len(body) > MAX_PROMPT_CHARS or \
            len(body.split()) > MAX_PROMPT_WORDS:
        raise OwnerAmbiguityGate(
            "FLOW_R2V_COMPACT_PROMPT_LIMIT; explicit creative reduction "
            "required")
    return FlowR2VPrompt(body + " " + marker, marker, sha256(plan),
                         version=CAUSAL_VERSION, model=model)
