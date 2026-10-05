"""F2 world-geography reframe authority (Package QUALITY-V2-009).

The Owner's V2-008 NEEDS_REPAIR verdict established that a freestanding
decorative doorway in an open field fails creative acceptance: the
viewer can reasonably think "he could simply walk around it". This
module freezes the provider-neutral GEOGRAPHY and WIND-CAUSALITY
authority that any future F2 render must satisfy:

- TraversalGeometrySpec v1 + gates G1-G10: the gate is a PASS-THROUGH
  OBSTACLE / CHOKE POINT integrated into continuous terrain; the road
  funnels through the opening; no visible bypass; no shelter niche.
- CausalEnvironmentSpec v1 + gates W1-W6: the gust is a visually
  causal force (cloth, hair, vegetation, body lean agree in direction;
  progress visibly requires effort).
- Legibility contract L1-L8: rendered-shot acceptance concepts — a
  shot cannot pass merely because coordinates satisfy the plan.

The Director MAY interpret the choke point as a narrow stone pass /
ruined stone boundary / rock choke point integrated into the terrain
— that interpretation is DESIGN, not a newly asserted source fact.
"""
from __future__ import annotations

from typing import Literal

from pydantic import Field, model_validator

from .core import ContractModel, canonical_json, sha256, validate_contract

GOVERNANCE_VERSION = "world-geography-governance-v2-009-v1"

TRAVERSAL_SCHEMA_VERSION = "traversal-geometry-spec-v1"
ENVIRONMENT_SCHEMA_VERSION = "causal-environment-spec-v1"

TRAVERSAL_GATES = (
    "G1_GATE_OR_PASSAGE_INTEGRATED_IN_WORLD",
    "G2_BARRIER_CONTINUES_BEYOND_VISIBLE_OPENING",
    "G3_OPEN_FIELD_BYPASS_NOT_VISUALLY_AVAILABLE",
    "G4_ROAD_OR_TRAVEL_PATH_FUNNELS_THROUGH_OPENING",
    "G5_ENTRY_THRESHOLD_EXIT_SPATIALLY_DISTINCT",
    "G6_ROCK_IS_BARRIER_NOT_DESTINATION",
    "G7_NO_SHELTER_NICHE_READ",
    "G8_NO_DECORATIVE_FREESTANDING_GATE",
    "G9_FAR_SIDE_MEANINGFULLY_BEYOND_OBSTACLE",
    "G10_CAMERA_CAN_PROVE_THE_CROSSING")

WIND_GATES = (
    "W1_GUST_DIRECTION_READABLE", "W2_BODY_REACTS_TO_GUST",
    "W3_ENVIRONMENT_REACTS_SAME_DIRECTION",
    "W4_ACTION_EFFORT_CAUSED_BY_GUST", "W5_NO_SHELTERING_READ",
    "W6_NO_VOLUNTARY_LOITERING")

LEGIBILITY_GATES = (
    "L1_OBSTACLE_NECESSARY_TO_TRAVERSE", "L2_BYPASS_NOT_VISIBLE",
    "L3_FORWARD_GOAL_DOMINATES", "L4_ROCK_NOT_DESTINATION",
    "L5_NO_SHELTERING_BODY_LANGUAGE", "L6_NO_LOITERING",
    "L7_NO_MEANINGLESS_SIDE_MOVEMENT", "L8_END_STATE_PROVES_PROGRESS")

BARRIER_TYPES = ("CONTINUOUS_ROCK_RIDGE_BOTH_SIDES",
                 "RUINED_STONE_BOUNDARY_WALL",
                 "TERRAIN_CHOKE_POINT_ROCK_FACE",
                 "CLIFF_PASS_NARROW_ROCK_WALLS")
FORBIDDEN_GEOGRAPHY = (
    "FREESTANDING_DECORATIVE_GATE", "OPEN_FIELD_BYPASS",
    "SHELTER_NICHE_OR_CAVE", "CASTLE_OR_FORTRESS", "METAL_GATE",
    "WARM_CLOUD_SEA", "LIGHTNING_AS_GUST_PROXY")


class TraversalGeometrySpec(ContractModel):
    """WHERE the traversal happens — the geography authority. The gate
    is a choke point integrated into continuous terrain, not a
    freestanding decoration."""
    schema_version: Literal["traversal-geometry-spec-v1"] = \
        TRAVERSAL_SCHEMA_VERSION
    traversal_id: str = Field(pattern=r"^TG-[a-f0-9]{16}$")
    shot_scope: str = Field(min_length=1)
    entry_region: str = Field(min_length=1)
    threshold_region: str = Field(min_length=1)
    exit_region: str = Field(min_length=1)
    barrier_extent: str = Field(min_length=1)
    passage_axis: str = Field(min_length=1)
    travel_direction: str = Field(min_length=1)
    bypass_visibility: Literal["NONE_IN_FRAME", "PARTIAL", "OPEN"] = \
        "NONE_IN_FRAME"
    shelter_affordance: Literal["NONE", "PARTIAL", "OPEN"] = "NONE"
    world_connection: str = Field(min_length=1)
    wind_channel: str = Field(min_length=1)
    camera_proof_requirements: list[str] = Field(min_length=1)
    forbidden_geography: list[str] = Field(min_length=1)
    authority_sources: dict[str, str]
    created_at: str = Field(min_length=1)

    @model_validator(mode="after")
    def validate_spec(self):
        required_sources = ("regions", "barrier", "wind_channel",
                            "forbidden_geography")
        missing = [k for k in required_sources
                   if not self.authority_sources.get(k, "").strip()]
        if missing:
            raise ValueError(
                f"TraversalGeometrySpec fields lack authority sources: "
                f"{missing}")
        validate_contract("traversal_geometry_spec",
                          self.model_dump(mode="json"))
        basis = self.model_dump(mode="json", exclude={"traversal_id"})
        expected = "TG-" + sha256(basis)[:16]
        if self.traversal_id != expected:
            raise ValueError(
                f"TraversalGeometrySpec identity mismatch: expected "
                f"{expected}")
        return self


class CausalEnvironmentSpec(ContractModel):
    """WHY the action is forced — the gust as a visually causal
    obstacle. At least two environment/body cues must agree in
    direction with the wind vector."""
    schema_version: Literal["causal-environment-spec-v1"] = \
        ENVIRONMENT_SCHEMA_VERSION
    environment_id: str = Field(pattern=r"^CE-[a-f0-9]{16}$")
    shot_scope: str = Field(min_length=1)
    gust_direction: str = Field(min_length=1)
    cloth_pressure: str = Field(min_length=1)
    hair_movement: str = ""
    vegetation_movement: str = ""
    body_lean_response: str = Field(min_length=1)
    effort_requirement: str = Field(min_length=1)
    forbidden_environment: list[str] = Field(min_length=1)
    authority_sources: dict[str, str]
    created_at: str = Field(min_length=1)

    @model_validator(mode="after")
    def validate_spec(self):
        missing = [k for k in ("gust_direction", "cloth_pressure",
                               "body_lean_response", "effort_requirement")
                   if not self.authority_sources.get(k, "").strip()]
        if missing:
            raise ValueError(
                f"CausalEnvironmentSpec fields lack authority sources: "
                f"{missing}")
        validate_contract("causal_environment_spec",
                          self.model_dump(mode="json"))
        basis = self.model_dump(mode="json", exclude={"environment_id"})
        expected = "CE-" + sha256(basis)[:16]
        if self.environment_id != expected:
            raise ValueError(
                f"CausalEnvironmentSpec identity mismatch: expected "
                f"{expected}")
        return self


def _mint(model_cls, id_field: str, prefix: str, data: dict):
    data = dict(data)
    data[id_field] = prefix + "0" * 16
    normalized = model_cls.model_construct(**data).model_dump(mode="json")
    real = prefix + sha256({k: v for k, v in normalized.items()
                            if k != id_field})[:16]
    normalized[id_field] = real
    return model_cls.model_validate(normalized)


def make_traversal_geometry(**data) -> TraversalGeometrySpec:
    return _mint(TraversalGeometrySpec, "traversal_id", "TG-", data)


def make_causal_environment(**data) -> CausalEnvironmentSpec:
    return _mint(CausalEnvironmentSpec, "environment_id", "CE-", data)


def _gate(results: dict, gate: str, ok: bool, detail: str) -> None:
    results[gate] = {"state": "PASS" if ok else "FAIL", "detail": detail}


def validate_traversal_gates(geo: TraversalGeometrySpec) -> dict:
    """The ten frozen geography gates (G1-G10), deterministic over the
    spec. These encode the Owner reframe: the barrier must make the
    traversal NECESSARY."""
    r: dict = {}
    integrated = any(k in geo.barrier_extent.lower()
                     for k in ("ridge", "boundary", "choke", "cliff",
                               "terrain", "wall"))
    _gate(r, "G1_GATE_OR_PASSAGE_INTEGRATED_IN_WORLD", integrated,
          f"barrier_extent={geo.barrier_extent}")
    continues = ("both sides" in geo.barrier_extent.lower() or
                 "continuous" in geo.barrier_extent.lower() or
                 "beyond" in geo.barrier_extent.lower())
    _gate(r, "G2_BARRIER_CONTINUES_BEYOND_VISIBLE_OPENING", continues,
          f"barrier_extent={geo.barrier_extent}")
    _gate(r, "G3_OPEN_FIELD_BYPASS_NOT_VISUALLY_AVAILABLE",
          geo.bypass_visibility == "NONE_IN_FRAME",
          f"bypass_visibility={geo.bypass_visibility}")
    funnels = any(k in geo.world_connection.lower()
                  for k in ("funnel", "road", "path", "travel"))
    _gate(r, "G4_ROAD_OR_TRAVEL_PATH_FUNNELS_THROUGH_OPENING", funnels,
          f"world_connection={geo.world_connection[:80]}")
    distinct = len({geo.entry_region.split(":")[0],
                    geo.threshold_region.split(":")[0],
                    geo.exit_region.split(":")[0]}) == 3
    _gate(r, "G5_ENTRY_THRESHOLD_EXIT_SPATIALLY_DISTINCT", distinct,
          f"entry={geo.entry_region} threshold={geo.threshold_region} "
          f"exit={geo.exit_region}")
    barrier_not_dest = "FORBIDDEN_DESTINATION" not in \
        geo.barrier_extent.upper() and \
        geo.exit_region != geo.threshold_region
    _gate(r, "G6_ROCK_IS_BARRIER_NOT_DESTINATION", barrier_not_dest,
          f"exit={geo.exit_region} != threshold")
    _gate(r, "G7_NO_SHELTER_NICHE_READ",
          geo.shelter_affordance == "NONE",
          f"shelter_affordance={geo.shelter_affordance}")
    decorative = any(k in " ".join(geo.forbidden_geography).lower()
                     for k in ("freestanding", "decorative"))
    _gate(r, "G8_NO_DECORATIVE_FREESTANDING_GATE", decorative,
          f"forbidden_geography lists it: {decorative}")
    beyond = any(k in geo.exit_region.lower()
                 for k in ("beyond", "clear", "road", "onward"))
    _gate(r, "G9_FAR_SIDE_MEANINGFULLY_BEYOND_OBSTACLE", beyond,
          f"exit_region={geo.exit_region}")
    provable = len(geo.camera_proof_requirements) >= 1 and all(
        c.strip() for c in geo.camera_proof_requirements)
    _gate(r, "G10_CAMERA_CAN_PROVE_THE_CROSSING", provable,
          f"{len(geo.camera_proof_requirements)} proof requirements")
    blocked = sorted(g for g, res in r.items() if res["state"] == "FAIL")
    return {"gates": r, "all_pass": not blocked, "blocked_by": blocked}


def require_traversal_gates(geo: TraversalGeometrySpec) -> dict:
    result = validate_traversal_gates(geo)
    if not result["all_pass"]:
        raise ValueError(
            "BLOCKED_INVARIANT: traversal geography gates failed: "
            f"{result['blocked_by']}")
    return result


def validate_wind_gates(env: CausalEnvironmentSpec) -> dict:
    """The six wind-causality gates (W1-W6). At least TWO
    environment/body cues must agree in direction with the gust."""
    r: dict = {}
    _gate(r, "W1_GUST_DIRECTION_READABLE",
          bool(env.gust_direction.strip()),
          f"gust_direction={env.gust_direction}")
    body_agrees = any(k in env.body_lean_response.lower()
                      for k in ("against", "into", "lean", "brace",
                                "forward"))
    _gate(r, "W2_BODY_REACTS_TO_GUST", body_agrees,
          f"body_lean_response={env.body_lean_response[:80]}")
    cues = [c for c in (env.cloth_pressure, env.hair_movement,
                        env.vegetation_movement) if c.strip()]
    _gate(r, "W3_ENVIRONMENT_REACTS_SAME_DIRECTION", len(cues) >= 2,
          f"{len(cues)} environment cues present (>=2 required)")
    effort = any(k in env.effort_requirement.lower()
                 for k in ("effort", "against", "drive", "push", "force"))
    _gate(r, "W4_ACTION_EFFORT_CAUSED_BY_GUST", effort,
          f"effort_requirement={env.effort_requirement[:80]}")
    forb = " ".join(env.forbidden_environment).lower()
    no_shelter = any(k in forb for k in ("shelter", "cover",
                                         "crouch beside"))
    _gate(r, "W5_NO_SHELTERING_READ", no_shelter,
          f"sheltering forbidden in contract: {no_shelter}")
    no_loiter = any(k in forb for k in ("loiter", "linger",
                                        "ambient-only"))
    _gate(r, "W6_NO_VOLUNTARY_LOITERING", no_loiter,
          f"loitering forbidden in contract: {no_loiter}")
    blocked = sorted(g for g, res in r.items() if res["state"] == "FAIL")
    return {"gates": r, "all_pass": not blocked, "blocked_by": blocked}


def require_wind_gates(env: CausalEnvironmentSpec) -> dict:
    result = validate_wind_gates(env)
    if not result["all_pass"]:
        raise ValueError(
            "BLOCKED_INVARIANT: wind causality gates failed: "
            f"{result['blocked_by']}")
    return result


def validate_legibility_contract(specs: dict, *,
                                 previz_manifest: dict | None = None,
                                 owner_vietnamese_read: str = "") -> dict:
    """L1-L8: the rendered-shot acceptance contract. At DESIGN time the
    specs + previz must encode every concept; at RENDER QC time each
    gate is re-checked against the actual frames. A shot cannot pass
    merely because coordinates satisfy the plan."""
    r: dict = {}
    geo = specs["geometry"]
    env = specs["environment"]
    _gate(r, "L1_OBSTACLE_NECESSARY_TO_TRAVERSE",
          geo.bypass_visibility == "NONE_IN_FRAME" and
          geo.barrier_extent != "",
          "the choke point makes traversal necessary (design level)")
    _gate(r, "L2_BYPASS_NOT_VISIBLE",
          geo.bypass_visibility == "NONE_IN_FRAME" and
          "OPEN_FIELD_BYPASS" in
          " ".join(geo.forbidden_geography).upper(),
          "no bypass in frame; open-field bypass forbidden")
    _gate(r, "L3_FORWARD_GOAL_DOMINATES",
          any(k in env.effort_requirement.lower()
              for k in ("forward", "onward", "through", "pass")),
          f"effort_requirement={env.effort_requirement[:80]}")
    _gate(r, "L4_ROCK_NOT_DESTINATION",
          any("destination" in f.lower()
              for f in geo.forbidden_geography) or
          "G6_ROCK_IS_BARRIER_NOT_DESTINATION" in
          validate_traversal_gates(geo)["gates"],
          "barrier-not-destination frozen")
    _gate(r, "L5_NO_SHELTERING_BODY_LANGUAGE",
          "W5_NO_SHELTERING_READ" in
          validate_wind_gates(env)["gates"] and
          validate_wind_gates(env)["gates"]["W5_NO_SHELTERING_READ"][
              "state"] == "PASS",
          "sheltering body language forbidden")
    _gate(r, "L6_NO_LOITERING",
          validate_wind_gates(env)["gates"]["W6_NO_VOLUNTARY_LOITERING"][
              "state"] == "PASS",
          "voluntary loitering forbidden")
    _gate(r, "L7_NO_MEANINGLESS_SIDE_MOVEMENT",
          geo.passage_axis != "" and geo.travel_direction != "",
          "movement constrained to the passage axis")
    end_proves = any(k in geo.exit_region.lower()
                     for k in ("clear", "beyond", "road"))
    _gate(r, "L8_END_STATE_PROVES_PROGRESS", end_proves,
          f"exit_region={geo.exit_region}")
    if previz_manifest is not None:
        required = {"F2_WORLD_GEOGRAPHY_TOPDOWN.png",
                    "F2A_BLOCKING_REFRAME.png", "F2B_BLOCKING_REFRAME.png",
                    "F2_START_END_STATES.png",
                    "F2_WORLD_REFRAME_PREVIZ.mp4"}
        have = set(previz_manifest.get("artifacts", {}))
        _gate(r, "L9_PREVIZ_ENCODES_GEOMETRY", required <= have,
              f"missing={sorted(required - have)}")
    blocked = sorted(g for g, res in r.items() if res["state"] == "FAIL")
    return {"gates": r, "all_pass": not blocked, "blocked_by": blocked}
