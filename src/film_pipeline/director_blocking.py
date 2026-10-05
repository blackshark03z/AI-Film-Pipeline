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
    # Owner timing invariant (V2-003 substitute ingest): the crossing
    # deadline and the end-read deadline inside the canonical usable
    # window. Optional fields; required by validate_timing_invariant
    # for traversal plans.
    cross_by_s: float | None = Field(default=None, ge=0)
    reach_by_s: float | None = Field(default=None, ge=0)


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

    # B5 NO_CIRCLING (a zone family re-entered AFTER a different family
    # was visited; deepening within the same family is progress, and a
    # plan that never crosses cannot circle)
    loop_authorized = bool(blocking.authority_sources.get(
        "path_loop_authorization", "").strip())
    tops = [z.split(":")[0] for z in zones]
    seen: list[str] = []
    reentered: list[str] = []
    for top in tops:
        if top in seen and seen and seen[-1] != top:
            reentered.append(top)
        if not seen or seen[-1] != top:
            seen.append(top)
    ok_b5 = loop_authorized or not reentered or (
        blocking.travel_path.path_type == "AUTHORIZED_LOOP" and
        loop_authorized)
    record("B5_NO_CIRCLING", ok_b5,
           f"re-entered families={reentered} "
           f"loop_authorized={loop_authorized}")

    # B6 NO_REVERSAL (a plan with no marked crossing cannot reverse
    # after one; otherwise the crossing must be marked exactly once
    # with no post-crossing return to the start zone)
    crossing_count = sum(1 for w in blocking.travel_path.ordered_waypoints
                         if w.is_crossing)
    crossing_idx = _crossing_index(blocking)
    exactly_once = bool(blocking.travel_path.required_crossing) and \
        crossing_count == 1
    post_crossing_zones = zones[crossing_idx + 1:] if crossing_idx >= 0 \
        else []
    backtracking = [z for z in post_crossing_zones
                    if zone_matches(z, blocking.start_zone)]
    ok_b6 = (not blocking.forbidden_reversal) or crossing_count == 0 or (
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


def validate_timing_invariant(blocking: BlockingSpec, *,
                              usable_window_s: float = 5.6,
                              cross_deadline_s: float = 4.8) -> dict:
    """Owner timing invariant (V2-003 substitute ingest): the full body
    must clearly cross the gate threshold by <= cross_deadline_s and the
    far-side state must already be readable inside the canonical usable
    window. Deterministic; traversal plans must carry the anchors."""
    waypoints = blocking.travel_path.ordered_waypoints
    crossing = [w for w in waypoints if w.is_crossing]
    final = waypoints[-1] if waypoints else None
    checks = {}
    checks["crossing_anchored"] = bool(crossing) and \
        crossing[0].cross_by_s is not None
    checks["cross_within_deadline"] = checks["crossing_anchored"] and \
        crossing[0].cross_by_s <= cross_deadline_s
    checks["end_read_anchored"] = final is not None and \
        final.reach_by_s is not None
    checks["end_read_within_window"] = checks["end_read_anchored"] and \
        final.reach_by_s <= usable_window_s
    checks["deadline_inside_window"] = cross_deadline_s < usable_window_s
    ok = all(checks.values())
    return {"invariant": "F2_TIMING_INVARIANT_V2_003",
            "usable_window_s": usable_window_s,
            "cross_deadline_s": cross_deadline_s,
            "cross_by_s": crossing[0].cross_by_s if crossing else None,
            "reach_by_s": final.reach_by_s if final else None,
            "checks": checks,
            "state": "PASS" if ok else "FAIL"}


# ---------------------------------------------------------------------------
# Decomposition gates (V2-005): a two-shot editorial solution for F2.
# Each gate is deterministic over the frozen plan pair + editorial plan.
# ---------------------------------------------------------------------------

DECOMPOSITION_GATES = (
    "D1_STORY_MEANING_PRESERVED", "D2_EACH_SHOT_ONE_DOMINANT_ACTION",
    "D3_F2A_END_F2B_START_COMPATIBLE", "D4_FAR_SIDE_STATE_OBSERVABLE",
    "D5_ROCK_NOT_DESTINATION", "D6_NO_REVERSAL_REQUIRED",
    "D7_EDITORIAL_ELLIPSIS_LEGIBLE", "D8_F1_F2A_F2B_F3_CONTINUITY",
    "D9_DURATION_BOUNDED", "D10_CANONICAL_UNCHANGED")

FROZEN_EDITORIAL_STATES = {
    "F2A_END_STATE": "AT_THRESHOLD_COMMITTED_FORWARD",
    "F2B_START_STATE": "CROSSING_OR_JUST_BEYOND_THRESHOLD",
    "F2B_END_STATE": "FAR_SIDE_CLEAR"}


def _meaning_keywords(text: str, needle: str) -> bool:
    words = [w for w in needle.lower().replace(",", " ").split()
             if len(w) > 3]
    blob = " ".join(text.lower().split())
    return all(w in blob for w in words)


def validate_decomposition_gates(*, story_meaning: dict,
                                 f2a: dict, f2b: dict,
                                 editorial_states: dict,
                                 timing: dict,
                                 canonical: dict) -> dict:
    """The ten V2-005 decomposition gates.

    f2a/f2b: {"intent": DirectorIntent, "blocking": BlockingSpec,
              "camera": CameraCoveragePlan, "trim_s": float}
    story_meaning: frozen {"trigger", "goal", "outcome", "not_goal"}.
    timing: {"f2a_trim_s", "f2b_trim_s", "allocation_s", "max_total_s"}.
    canonical: {"canonical_manifest_id", "preview_manifest_id",
                "no_change_proof": bool}.
    """
    results: dict[str, dict] = {}

    def record(gate: str, ok: bool, detail: str):
        results[gate] = {"state": "PASS" if ok else "FAIL",
                         "detail": detail}

    def blob(shot: dict) -> str:
        i = shot["intent"]
        return " ".join([i.dramatic_purpose, i.required_end_read,
                         i.primary_action_objective,
                         *i.viewer_must_understand])

    # D1 STORY_MEANING_PRESERVED: each frozen element is carried via its
    # semantic anchors (Owner text preserved verbatim alongside).
    anchors = story_meaning.get("anchors", {})
    def carries(needle: str, texts: list[str], anchor_list=None) -> bool:
        if anchor_list:
            blob_all = " ".join(texts).lower()
            return any(a.lower() in blob_all for a in anchor_list)
        return any(_meaning_keywords(t, needle) for t in texts)
    pair_blob = [blob(f2a), blob(f2b)]
    goal_ok = carries(story_meaning["goal"], pair_blob,
                      anchors.get("goal"))
    trigger_ok = carries(story_meaning["trigger"], pair_blob,
                         anchors.get("trigger"))
    outcome_ok = carries(story_meaning["outcome"], [blob(f2b)],
                         anchors.get("outcome"))
    not_goal_ok = True
    for ng in story_meaning["not_goal"]:
        ng_anchors = anchors.get("not_goal", {}).get(ng)
        if ng_anchors:
            ok = any(any(a.lower() in " ".join(
                i.forbidden_interpretations).lower()
                for a in ng_anchors)
                for i in (f2a["intent"], f2b["intent"]))
        else:
            ok = any(_meaning_keywords(
                " ".join(i.forbidden_interpretations), ng)
                for i in (f2a["intent"], f2b["intent"]))
        not_goal_ok = not_goal_ok and ok
    record("D1_STORY_MEANING_PRESERVED",
           goal_ok and trigger_ok and outcome_ok and not_goal_ok,
           f"goal={goal_ok} trigger={trigger_ok} outcome={outcome_ok} "
           f"not_goal={not_goal_ok}")

    # D2 EACH_SHOT_ONE_DOMINANT_ACTION
    def one_action(shot: dict, opens_with_crossing: bool) -> bool:
        bl: BlockingSpec = shot["blocking"]
        wps = bl.travel_path.ordered_waypoints
        crossings = [i for i, w in enumerate(wps) if w.is_crossing]
        single_objective = bool(shot["intent"].primary_action_objective)
        if opens_with_crossing:
            # F2B: exactly one crossing waypoint and it OPENS the shot;
            # the shot ends in the BEYOND family
            return single_objective and len(crossings) == 1 and \
                bool(wps) and crossings[0] == 0 and \
                zone_matches(wps[-1].zone, "BEYOND_GATE")
        # F2A: at most one crossing waypoint and it must be the LAST
        # waypoint (arrival at the threshold); nothing reaches BEYOND
        return single_objective and len(crossings) <= 1 and \
            (not crossings or crossings[0] == len(wps) - 1) and \
            not any(zone_matches(w.zone, "BEYOND_GATE") for w in wps)

    ok_a = one_action(f2a, opens_with_crossing=False)
    ok_b = one_action(f2b, opens_with_crossing=True)
    record("D2_EACH_SHOT_ONE_DOMINANT_ACTION", ok_a and ok_b,
           f"f2a_single={ok_a} f2b_single={ok_b}")

    # D3 F2A_END_F2B_START_COMPATIBLE (threshold family match)
    ok_d3 = zone_matches(f2a["blocking"].end_zone,
                         f2b["blocking"].start_zone)
    record("D3_F2A_END_F2B_START_COMPATIBLE", ok_d3,
           f"f2a_end={f2a['blocking'].end_zone} "
           f"f2b_start={f2b['blocking'].start_zone}")

    # D4 FAR_SIDE_STATE_OBSERVABLE (F2B end binds BEYOND + camera)
    b = f2b["blocking"]
    c = f2b["camera"]
    ok_d4 = zone_matches(b.end_zone, "BEYOND_GATE") and \
        zone_matches(c.subject_end_region, b.end_zone) and \
        bool(b.visibility_requirements)
    record("D4_FAR_SIDE_STATE_OBSERVABLE", ok_d4,
           f"f2b_end={b.end_zone} camera_end={c.subject_end_region}")

    # D5 ROCK_NOT_DESTINATION
    forbidden = {"ROCK_CONTACT", "ROCK_BRACE", "ROCK_CIRCLE",
                 "ROCK_SHELTER"}
    def rock_clean(shot: dict) -> bool:
        bl = shot["blocking"]
        return forbidden <= set(bl.forbidden_interactions) and \
            not (set(bl.allowed_interactions) & forbidden) and \
            "AT_ROCK" in bl.forbidden_zones and not any(
                zone_matches(w.zone, "AT_ROCK")
                for w in bl.travel_path.ordered_waypoints)
    ok_d5 = rock_clean(f2a) and rock_clean(f2b)
    record("D5_ROCK_NOT_DESTINATION", ok_d5,
           f"f2a={rock_clean(f2a)} f2b={rock_clean(f2b)}")

    # D6 NO_REVERSAL_REQUIRED (both plans forbid reversal; B6 held)
    ok_d6 = f2a["blocking"].forbidden_reversal and \
        f2b["blocking"].forbidden_reversal and \
        f2a["gates_b6"] and f2b["gates_b6"]
    record("D6_NO_REVERSAL_REQUIRED", ok_d6,
           f"f2a_b6={f2a['gates_b6']} f2b_b6={f2b['gates_b6']}")

    # D7 EDITORIAL_ELLIPSIS_LEGIBLE
    ok_d7 = editorial_states == FROZEN_EDITORIAL_STATES and ok_d3
    record("D7_EDITORIAL_ELLIPSIS_LEGIBLE", ok_d7,
           f"states={editorial_states} threshold_match={ok_d3}")

    # D8 F1_F2A_F2B_F3_CONTINUITY
    direction = f2a["blocking"].screen_direction
    ok_d8 = f2b["blocking"].screen_direction == direction and \
        f2a["blocking"].continuity_bindings.get("previous_shot_id") == \
        "SEQ7_F1" and \
        f2a["blocking"].continuity_bindings.get("next_shot_id") == \
        "SEQ7_F2A_F2B_CUT" and \
        f2b["blocking"].continuity_bindings.get("previous_shot_id") == \
        "SEQ7_F2A_F2B_CUT" and \
        f2b["blocking"].continuity_bindings.get("next_shot_id") == \
        "SEQ7_F3"
    record("D8_F1_F2A_F2B_F3_CONTINUITY", ok_d8,
           f"direction={direction} chain bound")

    # D9 DURATION_BOUNDED
    total = timing["f2a_trim_s"] + timing["f2b_trim_s"]
    ok_d9 = 0 < timing["f2a_trim_s"] and 0 < timing["f2b_trim_s"] and \
        total <= timing["max_total_s"]
    record("D9_DURATION_BOUNDED", ok_d9,
           f"total={total}s allocation={timing['allocation_s']}s "
           f"max={timing['max_total_s']}s")

    # D10 CANONICAL_UNCHANGED
    ok_d10 = canonical["preview_manifest_id"] != \
        canonical["canonical_manifest_id"] and \
        canonical["no_change_proof"] is True
    record("D10_CANONICAL_UNCHANGED", ok_d10,
           "preview manifest is a separate payload; canonical untouched")

    blocked = sorted(g for g, r in results.items() if r["state"] == "FAIL")
    return {"gates": results, "all_pass": not blocked,
            "blocked_by": blocked}


def require_decomposition_gates(**kwargs) -> dict:
    result = validate_decomposition_gates(**kwargs)
    if not result["all_pass"]:
        raise ValueError(
            "BLOCKED_INVARIANT: decomposition gates failed: "
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
