"""Director/Shot-Designer authority layer (Package QUALITY-V2-003).

Freezes the authority ordering

    NarrativeBeat -> ActionIntent -> DirectorIntent -> BlockingSpec
    -> PerformanceSpec -> CameraCoveragePlan -> ShotSpec
    -> Prompt Compiler -> Provider

and the structured contracts the ordering needs: DirectorIntent v1,
BlockingSpec v1 (spatial action plan), CameraCoveragePlan v1, the ten
deterministic director gates (B1-B10), the director-layer semantic
identity extension, and the prompt-compiler authority boundary.

The Director model (gpt-6-sol, HIGH) designs plans THROUGH these
contracts; the contracts themselves are provider-neutral and never call
providers. Historical V1 semantic identities are untouched: the
director layer is a forward-compatible extension keyed by the V1 base
shot-spec identity.
"""
from __future__ import annotations

from typing import Literal

from pydantic import Field, model_validator

from .core import ContractModel, canonical_json, sha256, validate_contract

GOVERNANCE_VERSION = "director-blocking-governance-v2-003-v1"

AUTHORITY_LAYERING = (
    "NarrativeBeat", "ActionIntent", "DirectorIntent", "BlockingSpec",
    "PerformanceSpec", "CameraCoveragePlan", "ShotSpec", "PromptCompiler",
    "Provider")
AUTHORITY_LAYER_MEANINGS = {
    "NarrativeBeat": "WHAT happens",
    "ActionIntent": "WHY the character acts / desired outcome",
    "DirectorIntent": "HOW the audience should understand the beat",
    "BlockingSpec": "WHERE the character moves",
    "PerformanceSpec": "HOW the body performs it",
    "CameraCoveragePlan": "HOW the action is made visible",
    "ShotSpec": "the assembled shot contract",
    "PromptCompiler": "deterministic translation only",
    "Provider": "never authority"}

INTENT_SCHEMA_VERSION = "director-intent-v1"
BLOCKING_SCHEMA_VERSION = "blocking-spec-v1"
CAMERA_SCHEMA_VERSION = "camera-coverage-plan-v1"

INTENT_AUTHORITY_KEYS = (
    "dramatic_purpose", "viewer_must_understand",
    "primary_action_objective", "required_visual_change",
    "required_end_read", "forbidden_interpretations")
BLOCKING_AUTHORITY_KEYS = (
    "zones", "travel_path", "crossing", "interactions", "continuity")
CAMERA_AUTHORITY_KEYS = ("camera_position_intent", "subject_regions")

PATH_TYPES = ("DIRECT_TRAVERSAL", "STAGED_TRAVERSAL", "STATIC_HELD",
              "AUTHORIZED_LOOP")
# Zones may be hierarchical ("BEYOND_GATE:FAR_SIDE"); zone_matches
# compares the top component: BEYOND_GATE:FAR_SIDE is still BEYOND_GATE.


def zone_matches(a: str, b: str) -> bool:
    """Equality on the top component: BEYOND_GATE matches
    BEYOND_GATE:FAR_SIDE (the far side IS beyond the gate)."""
    top_a = a.split(":")[0].strip().upper()
    top_b = b.split(":")[0].strip().upper()
    return top_a == top_b


class DirectorIntent(ContractModel):
    """HOW the audience should understand the beat. Every semantic field
    binds a concrete authority source — no prose-only authority."""
    schema_version: Literal["director-intent-v1"] = INTENT_SCHEMA_VERSION
    director_intent_id: str = Field(pattern=r"^DI-[a-f0-9]{16}$")
    shot_id: str = Field(min_length=1)
    dramatic_purpose: str = Field(min_length=1)
    viewer_must_understand: list[str] = Field(min_length=1)
    primary_action_objective: str = Field(min_length=1)
    required_visual_change: str = Field(min_length=1)
    required_end_read: str = Field(min_length=1)
    forbidden_interpretations: list[str] = Field(min_length=1)
    authority_sources: dict[str, str]
    director_model_receipt: dict = Field(min_length=1)
    created_at: str = Field(min_length=1)

    @model_validator(mode="after")
    def validate_intent(self):
        missing = [k for k in INTENT_AUTHORITY_KEYS
                   if not self.authority_sources.get(k, "").strip()]
        if missing:
            raise ValueError(
                f"DirectorIntent semantic fields lack authority sources: "
                f"{missing} (no prose-only authority)")
        validate_contract("director_intent", self.model_dump(mode="json"))
        basis = self.model_dump(mode="json", exclude={"director_intent_id"})
        expected = "DI-" + sha256(basis)[:16]
        if self.director_intent_id != expected:
            raise ValueError(
                f"DirectorIntent identity mismatch: expected {expected}")
        return self


def _mint(model_cls, id_field: str, prefix: str, data: dict):
    """Normalize the payload (construct without validators), derive the
    id from the exact normalized content, then validate fully with the
    real id."""
    data = dict(data)
    data[id_field] = prefix + "0" * 16
    normalized = model_cls.model_construct(**data).model_dump(mode="json")
    real = prefix + sha256({k: v for k, v in normalized.items()
                            if k != id_field})[:16]
    normalized[id_field] = real
    return model_cls.model_validate(normalized)


def make_director_intent(**data) -> DirectorIntent:
    """Mint a DirectorIntent; the id derives from the exact content."""
    return _mint(DirectorIntent, "director_intent_id", "DI-", data)


def make_blocking_spec(**data) -> BlockingSpec:
    return _mint(BlockingSpec, "blocking_spec_id", "BS-", data)


def make_camera_coverage_plan(**data) -> CameraCoveragePlan:
    return _mint(CameraCoveragePlan, "camera_plan_id", "CC-", data)


class Waypoint(ContractModel):
    zone: str = Field(min_length=1)
    note: str = ""
    is_crossing: bool = False


class TravelPath(ContractModel):
    path_type: Literal["DIRECT_TRAVERSAL", "STAGED_TRAVERSAL",
                       "STATIC_HELD", "AUTHORIZED_LOOP"]
    ordered_waypoints: list[Waypoint] = Field(min_length=1)
    required_crossing: str = Field(min_length=1)


class SpatialStateChange(ContractModel):
    from_zone: str = Field(min_length=1)
    to_zone: str = Field(min_length=1)


class BlockingSpec(ContractModel):
    """WHERE the character moves — the structured spatial authority.
    Provider-neutral by construction (no provider fields exist)."""
    schema_version: Literal["blocking-spec-v1"] = BLOCKING_SCHEMA_VERSION
    blocking_spec_id: str = Field(pattern=r"^BS-[a-f0-9]{16}$")
    shot_id: str = Field(min_length=1)
    start_zone: str = Field(min_length=1)
    target_zone: str = Field(min_length=1)
    end_zone: str = Field(min_length=1)
    screen_direction: str = Field(min_length=1)
    travel_path: TravelPath
    start_body_orientation: str = Field(min_length=1)
    end_body_orientation: str = Field(min_length=1)
    required_spatial_state_change: SpatialStateChange
    allowed_interactions: list[str] = Field(default_factory=list)
    forbidden_interactions: list[str] = Field(default_factory=list)
    forbidden_zones: list[str] = Field(default_factory=list)
    forbidden_reversal: bool = False
    must_exit_start_zone: bool
    must_reach_target_zone: bool
    visibility_requirements: list[str] = Field(min_length=1)
    continuity_bindings: dict
    authority_sources: dict[str, str]
    created_at: str = Field(min_length=1)

    @model_validator(mode="after")
    def validate_blocking(self):
        missing = [k for k in BLOCKING_AUTHORITY_KEYS
                   if not self.authority_sources.get(k, "").strip()]
        if missing:
            raise ValueError(
                f"BlockingSpec fields lack authority sources: {missing}")
        validate_contract("blocking_spec", self.model_dump(mode="json"))
        basis = self.model_dump(mode="json", exclude={"blocking_spec_id"})
        expected = "BS-" + sha256(basis)[:16]
        if self.blocking_spec_id != expected:
            raise ValueError(
                f"BlockingSpec identity mismatch: expected {expected}")
        return self


class CameraCoveragePlan(ContractModel):
    """HOW the action is made visible. A valid BlockingSpec with an
    invalid camera plan is NOT sufficient: the camera must make the
    required state change observable."""
    schema_version: Literal["camera-coverage-plan-v1"] = \
        CAMERA_SCHEMA_VERSION
    camera_plan_id: str = Field(pattern=r"^CC-[a-f0-9]{16}$")
    shot_id: str = Field(min_length=1)
    camera_position_intent: str = Field(min_length=1)
    framing: str = Field(min_length=1)
    axis: str = Field(min_length=1)
    screen_direction: str = Field(min_length=1)
    subject_start_region: str = Field(min_length=1)
    subject_end_region: str = Field(min_length=1)
    required_action_visibility: bool
    required_crossing_visibility: bool
    occlusion_constraints: list[str] = Field(default_factory=list)
    camera_motion: str = Field(min_length=1)
    forbidden_camera_behavior: list[str] = Field(default_factory=list)
    authority_sources: dict[str, str]
    created_at: str = Field(min_length=1)

    @model_validator(mode="after")
    def validate_camera(self):
        missing = [k for k in CAMERA_AUTHORITY_KEYS
                   if not self.authority_sources.get(k, "").strip()]
        if missing:
            raise ValueError(
                f"CameraCoveragePlan fields lack authority sources: "
                f"{missing}")
        validate_contract("camera_coverage_plan",
                          self.model_dump(mode="json"))
        basis = self.model_dump(mode="json", exclude={"camera_plan_id"})
        expected = "CC-" + sha256(basis)[:16]
        if self.camera_plan_id != expected:
            raise ValueError(
                f"CameraCoveragePlan identity mismatch: expected {expected}")
        return self


def _waypoint_zones(blocking: BlockingSpec) -> list[str]:
    return [w.zone for w in blocking.travel_path.ordered_waypoints]


def _crossing_index(blocking: BlockingSpec) -> int:
    return next((i for i, w in
                 enumerate(blocking.travel_path.ordered_waypoints)
                 if w.is_crossing), -1)


def validate_director_gates(intent: DirectorIntent, blocking: BlockingSpec,
                            camera: CameraCoveragePlan, *,
                            previous_screen_direction: str | None = None,
                            next_screen_direction: str | None = None) -> dict:
    """The ten deterministic director gates. Returns a structured
    checklist; `require_director_gates` turns failures into
    BLOCKED_INVARIANT."""
    results: dict[str, dict] = {}

    def record(gate: str, ok: bool, detail: str):
        results[gate] = {"state": "PASS" if ok else "FAIL", "detail": detail}

    zones = _waypoint_zones(blocking)
    traversal_required = blocking.must_exit_start_zone or \
        blocking.must_reach_target_zone

    # B1 START_END_DISTINCT
    record("B1_START_END_DISTINCT",
           (not traversal_required) or
           not zone_matches(blocking.start_zone, blocking.end_zone),
           f"start={blocking.start_zone} end={blocking.end_zone} "
           f"(traversal_required={traversal_required})")

    # B2 TARGET_REACHED
    ok_b2 = zone_matches(blocking.required_spatial_state_change.to_zone,
                         blocking.target_zone)
    if blocking.must_reach_target_zone:
        ok_b2 = ok_b2 and zone_matches(blocking.end_zone,
                                       blocking.target_zone)
    record("B2_TARGET_REACHED", ok_b2,
           f"state change to={blocking.required_spatial_state_change.to_zone}"
           f" target={blocking.target_zone} end={blocking.end_zone}")

    # B3 PATH_HAS_PROGRESS
    ok_b3 = bool(zones) and zone_matches(zones[0], blocking.start_zone) \
        and zone_matches(zones[-1], blocking.target_zone) \
        and zones.count(blocking.start_zone) == 1 \
        and not any(z in blocking.forbidden_zones for z in zones)
    record("B3_PATH_HAS_PROGRESS", ok_b3,
           f"waypoints={zones} start appears "
           f"{zones.count(blocking.start_zone)}x")

    # B4 NO_FORBIDDEN_INTERACTION
    overlap = sorted(set(blocking.allowed_interactions) &
                     set(blocking.forbidden_interactions))
    notes_blob = " ".join(w.note.lower() for w in
                          blocking.travel_path.ordered_waypoints)
    invented = [i for i in blocking.forbidden_interactions
                if (i.lower() in notes_blob) or
                (i.lower().replace("_", " ") in notes_blob)]
    record("B4_NO_FORBIDDEN_INTERACTION", not overlap and not invented,
           f"allowed/forbidden overlap={overlap} "
           f"path-note violations={invented}")

    # B5 NO_CIRCLING (a return to any previously-visited zone family)
    loop_authorized = bool(blocking.authority_sources.get(
        "path_loop_authorization", "").strip())
    repeats = sorted({z for i, z in enumerate(zones)
                      if any(zone_matches(z, earlier)
                             for earlier in zones[:i])})
    ok_b5 = loop_authorized or not repeats or (
        blocking.travel_path.path_type == "AUTHORIZED_LOOP" and
        loop_authorized)
    record("B5_NO_CIRCLING", ok_b5,
           f"repeated zones={repeats} "
           f"loop_authorized={loop_authorized}")

    # B6 NO_REVERSAL
    crossing_count = sum(1 for w in blocking.travel_path.ordered_waypoints
                         if w.is_crossing)
    crossing_idx = _crossing_index(blocking)
    exactly_once = bool(blocking.travel_path.required_crossing) and \
        crossing_count == 1
    post_crossing_zones = zones[crossing_idx + 1:] if crossing_idx >= 0 \
        else []
    backtracking = [z for z in post_crossing_zones
                    if zone_matches(z, blocking.start_zone)]
    ok_b6 = (not blocking.forbidden_reversal) or (
        exactly_once and crossing_idx >= 0 and not backtracking)
    record("B6_NO_REVERSAL", ok_b6,
           f"crossing marked {crossing_count}x, post-crossing "
           f"start-zone returns={backtracking}")

    # B7 CROSSING_OBSERVABLE
    crossing = blocking.travel_path.required_crossing.lower()
    occluded = [o for o in camera.occlusion_constraints
                if crossing and crossing in o.lower()]
    motion_words = camera.camera_motion.lower().replace("-", " ").split()
    motion_violations = [
        f for f in camera.forbidden_camera_behavior
        if all(w in motion_words
               for w in f.lower().replace("-", " ").split())]
    record("B7_CROSSING_OBSERVABLE",
           camera.required_crossing_visibility and not occluded
           and not motion_violations,
           f"crossing_visibility={camera.required_crossing_visibility} "
           f"occluded_by={occluded} motion_violations={motion_violations}")

    # B8 END_STATE_OBSERVABLE
    regions_distinct = not zone_matches(camera.subject_start_region,
                                        camera.subject_end_region)
    start_bound = zone_matches(camera.subject_start_region,
                               blocking.start_zone) or \
        zone_matches(blocking.start_zone, camera.subject_start_region)
    end_bound = zone_matches(camera.subject_end_region,
                             blocking.end_zone) or \
        zone_matches(blocking.end_zone, camera.subject_end_region)
    record("B8_END_STATE_OBSERVABLE",
           regions_distinct and start_bound and end_bound and
           camera.required_action_visibility,
           f"start_region={camera.subject_start_region} "
           f"end_region={camera.subject_end_region} "
           f"distinct={regions_distinct} bound=({start_bound},"
           f"{end_bound}) action_visibility="
           f"{camera.required_action_visibility}")

    # B9 CONTINUITY_COMPATIBLE
    binds_neighbors = bool(blocking.continuity_bindings.get(
        "previous_shot_id")) and bool(blocking.continuity_bindings.get(
            "next_shot_id"))
    flip_authorized = bool(blocking.continuity_bindings.get(
        "screen_direction_flip_authorized"))
    prev_ok = previous_screen_direction is None or flip_authorized or \
        previous_screen_direction.strip().lower() == \
        blocking.screen_direction.strip().lower()
    next_ok = next_screen_direction is None or flip_authorized or \
        next_screen_direction.strip().lower() == \
        blocking.screen_direction.strip().lower()
    record("B9_CONTINUITY_COMPATIBLE",
           binds_neighbors and prev_ok and next_ok,
           f"binds_neighbors={binds_neighbors} prev={prev_ok} "
           f"next={next_ok}")

    # B10 AUTHORITY_COMPLETE
    intent_missing = [k for k in INTENT_AUTHORITY_KEYS
                      if not intent.authority_sources.get(k, "").strip()]
    blocking_missing = [k for k in BLOCKING_AUTHORITY_KEYS
                        if not blocking.authority_sources.get(k, "").strip()]
    camera_missing = [k for k in CAMERA_AUTHORITY_KEYS
                      if not camera.authority_sources.get(k, "").strip()]
    same_shot = (intent.shot_id == blocking.shot_id == camera.shot_id)
    record("B10_AUTHORITY_COMPLETE",
           not intent_missing and not blocking_missing and
           not camera_missing and same_shot,
           f"missing intent={intent_missing} blocking={blocking_missing} "
           f"camera={camera_missing} same_shot={same_shot}")

    blocked = sorted(g for g, r in results.items() if r["state"] == "FAIL")
    return {"gates": results, "all_pass": not blocked,
            "blocked_by": blocked}


def require_director_gates(intent: DirectorIntent, blocking: BlockingSpec,
                           camera: CameraCoveragePlan, **kwargs) -> dict:
    result = validate_director_gates(intent, blocking, camera, **kwargs)
    if not result["all_pass"]:
        raise ValueError(
            "BLOCKED_INVARIANT: director gates failed: "
            f"{result['blocked_by']}")
    return result


# ---------------------------------------------------------------------------
# Director-layer semantic identity (forward-compatible extension; V1
# identities are never rewritten)
# ---------------------------------------------------------------------------

def director_semantic_identity(base_shot_spec_sha256: str,
                               intent: DirectorIntent,
                               blocking: BlockingSpec,
                               camera: CameraCoveragePlan) -> dict:
    if not (intent.shot_id == blocking.shot_id == camera.shot_id):
        raise ValueError("director identity requires one shot across all "
                         "three layers")
    layer = {"director_intent": intent.director_intent_id,
             "blocking_spec": blocking.blocking_spec_id,
             "camera_coverage_plan": camera.camera_plan_id}
    return {
        "version": "generation-semantic-identity-v2",
        "base_shot_spec_sha256": base_shot_spec_sha256,
        "director_layer": layer,
        "director_layer_sha256": sha256(layer),
        "generation_semantic_identity": sha256(
            {"base": base_shot_spec_sha256, "director_layer": layer}),
        "v1_identity_untouched": True}


# ---------------------------------------------------------------------------
# Prompt compiler authority boundary (P12)
# ---------------------------------------------------------------------------

REQUIRED_COMPILE_AUTHORITIES = ("action_intent", "director_intent",
                                "blocking_spec", "performance_spec",
                                "camera_coverage_plan")


def assert_compile_authorities_present(**authorities) -> None:
    missing = [name for name in REQUIRED_COMPILE_AUTHORITIES
               if not authorities.get(name)]
    if missing:
        raise ValueError(
            f"REFUSE_COMPILE: required authority missing {missing}; no "
            f"fallback prose inference")


def assert_compiler_respected_authority(prompt_text: str,
                                        blocking: BlockingSpec) -> None:
    """The compiled wire text must not introduce forbidden interactions
    (all component words of a forbidden interaction present) and must
    carry the required end spatial read. Deterministic scans."""
    text = prompt_text.lower()
    for interaction in blocking.forbidden_interactions:
        parts = [p.lower() for p in interaction.split("_") if p.strip()]
        if parts and all(p in text for p in parts):
            raise ValueError(
                f"REFUSE_COMPILE: compiled prompt introduces forbidden "
                f"interaction {interaction}")
    if blocking.must_reach_target_zone:
        slug = "".join(ch for ch in text.lower() if ch.isalnum())
        end_slugs = [
            "".join(ch for ch in token.lower() if ch.isalnum())
            for token in (blocking.end_zone,
                          blocking.required_spatial_state_change.to_zone)]
        if not any(s and s in slug for s in end_slugs):
            raise ValueError(
                "REFUSE_COMPILE: compiled prompt lacks the required end "
                f"spatial read ({blocking.end_zone})")
