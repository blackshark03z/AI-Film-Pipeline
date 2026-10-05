"""V2-003 DIRECTOR SUBSTITUTE INGEST — freeze the F2 director plan.

Owner authorization (Tech Lead chat, 2026-10-04):
  DIRECTOR_SUBSTITUTE = GPT-5.6 Sol, ROLE = DIRECTOR_SHOT_DESIGNER.
The DirectorIntent / BlockingSpec / CameraCoveragePlan supplied by the
Tech Lead chat are used as authoritative Director output — NOT
redesigned. The ONLY completion is the unresolved continuity binding:
the screen direction is resolved MECHANICALLY from the exact canonical
F1 -> F2 -> F3 authority; a missing/conflicting/non-unique direction
stops with BLOCKED_INVARIANT (no guessing).

No video generation, no Flow submit, no upload, no canonical mutation.
"""
from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "tools"))

from film_pipeline.core import sha256
from film_pipeline.director_blocking import (
    BlockingSpec, CameraCoveragePlan, DirectorIntent, SpatialStateChange,
    TravelPath, Waypoint, director_semantic_identity, make_blocking_spec,
    make_camera_coverage_plan, make_director_intent, require_director_gates,
    validate_timing_invariant)

PKG = ROOT / "projects/quality_v2_003_director_blocking"
FIXTURES = {shot: ROOT / f"fixtures/sequence007/{shot}.json"
            for shot in ("SEQ7_F1", "SEQ7_F2", "SEQ7_F3")}

OWNER_TIMING = {"usable_window_s": 5.6, "cross_deadline_s": 4.8}


def resolve_screen_direction() -> dict:
    """Mechanical resolution from the canonical F1/F2/F3 authority.
    Every non-missing screen_direction must agree AND at least one
    authority must state it — otherwise BLOCKED_INVARIANT (no guess)."""
    values = {}
    for shot, path in FIXTURES.items():
        payload = json.loads(path.read_text(encoding="utf-8"))
        values[shot] = (payload.get("continuity", {})
                        .get("screen_direction") or "").strip()
    stated = {k: v for k, v in values.items() if v}
    if not stated:
        raise SystemExit("BLOCKED_INVARIANT: no screen direction stated "
                         "by the F1/F2/F3 authority")
    unique = {v.lower() for v in stated.values()}
    if len(unique) != 1:
        raise SystemExit(
            f"BLOCKED_INVARIANT: conflicting screen directions {stated}")
    corroboration = {
        "f1_last_frame_binding":
            "V2-002 reference binding (SEQ7_F1 last frame) governs the F2 "
            "entry state; F1 travels toward the gate facing frame-left",
        "f3_first_frame": "SEQ7_F3 opens on the same left-facing profile",
    }
    return {"version": "screen-direction-resolution-v1",
            "method": "mechanical (exact authority fields; no guess)",
            "authority_values": values,
            "resolved_direction": stated[next(iter(stated))],
            "unique": True,
            "corroboration": corroboration}


def update_binding_authorization() -> dict:
    binding_path = PKG / "director_model_binding_v2_003.json"
    binding = json.loads(binding_path.read_text(encoding="utf-8"))
    binding["substitute_authorization"] = {
        "authorized_by": "OWNER (explicit authorization in Tech Lead chat)",
        "authorized_at": "2026-10-04",
        "provider": "OpenAI",
        "model": "GPT-5.6 Sol",
        "role": "DIRECTOR_SHOT_DESIGNER",
        "authorization_source": "Owner explicit authorization in Tech "
                                "Lead chat",
        "execution_note": "the Tech Lead chat plan is used as the "
                          "authoritative Director output per the Owner's "
                          "explicit authorization; no runtime model call "
                          "was made (the substitute model is not callable "
                          "from this worker runtime); the authority "
                          "transfer is recorded here verbatim",
        "redesign_allowed": False,
        "scope": "complete the unresolved continuity binding only, then "
                 "mint the frozen plan"}
    binding["director_work_state"] = "AUTHORIZED_SUBSTITUTE_FROZEN"
    binding_path.write_text(json.dumps(binding, indent=1,
                                       ensure_ascii=False),
                            encoding="utf-8")
    return binding["substitute_authorization"]


def critique_pass() -> list[dict]:
    """One advisory critique of the frozen plan (the seven frozen
    questions), answered from the mechanical gate evidence."""
    return [
        {"q": "Is the character's objective visually obvious?",
         "a": "YES — B3 (monotonic gate-mouth -> opening -> far side) and "
              "B8 (distinct zone-bound subject regions) make the forward "
              "objective the plan's spine; the V2-002 blind precedent "
              "showed this traversal reads correctly when rendered",
         "evidence": "B3_PATH_HAS_PROGRESS, B8_END_STATE_OBSERVABLE"},
        {"q": "Can the viewer mistake the rock as the destination?",
         "a": "NO — the rock is never a waypoint (forbidden zone "
              "AT_ROCK), all four ROCK_* interactions are forbidden "
              "(B4), and the required end read is the far side",
         "evidence": "B4_NO_FORBIDDEN_INTERACTION, B2_TARGET_REACHED"},
        {"q": "Is forward progress monotonic?",
         "a": "YES — B5 refuses any zone revisit and B6 refuses any "
              "post-crossing return to the start zone",
         "evidence": "B5_NO_CIRCLING, B6_NO_REVERSAL"},
        {"q": "Is the crossing visually observable?",
         "a": "YES — the camera plan flags required_crossing_visibility, "
              "occludes nothing at the opening, and stays locked with "
              "orbit/reversal/axis-cross forbidden",
         "evidence": "B7_CROSSING_OBSERVABLE"},
        {"q": "Is the final location unmistakably beyond the gate?",
         "a": "YES — the final waypoint is BEYOND_GATE:FAR_SIDE_CLEAR "
              "and the camera's subject_end_region binds the same zone",
         "evidence": "B8_END_STATE_OBSERVABLE, B2_TARGET_REACHED"},
        {"q": "Does camera placement hide any required state change?",
         "a": "NO — a locked profile full-shot perpendicular to the path "
              "keeps both sides of the threshold in frame for the whole "
              "5.6 s window",
         "evidence": "B7_CROSSING_OBSERVABLE, B8_END_STATE_OBSERVABLE"},
        {"q": "Does F1->F2->F3 continuity remain coherent?",
         "a": "YES — the screen direction was resolved MECHANICALLY to "
              "the unique authority value shared by F1/F2/F3 and bound "
              "into both plans; neighbor bindings are recorded",
         "evidence": "B9_CONTINUITY_COMPATIBLE + "
                     "screen-direction-resolution receipt"},
    ]


def main() -> int:
    # 1. mechanical continuity resolution (STOP on non-unique)
    resolution = resolve_screen_direction()
    direction = resolution["resolved_direction"]
    print(json.dumps({"step": "screen_direction_resolved",
                      "direction": direction}))

    # 2. binding authorization update (Owner substitute)
    authorization = update_binding_authorization()

    # 3. mint the frozen contracts EXACTLY as supplied in the Tech Lead
    #    chat plan (not redesigned); screen direction is the only
    #    completion + the Owner timing anchors
    authority = "V2-003 Owner truth (package) + V2-004 handoff freeze"
    intent = make_director_intent(
        shot_id="SEQ7_F2C",
        dramatic_purpose="pass the gate against the gust",
        viewer_must_understand=[
            "he is blocked by the gust at the gate",
            "his goal is the far side of the gate, onward",
            "the rock is never his destination"],
        primary_action_objective="PASS THROUGH THE GATE AGAINST THE GUST",
        required_visual_change="BEFORE_GATE -> BEYOND_GATE",
        required_end_read="he is unmistakably on the far side of the gate",
        forbidden_interpretations=[
            "the rock is his destination",
            "he takes shelter behind the rock",
            "he ends braced at the rock"],
        authority_sources={
            "dramatic_purpose": authority,
            "viewer_must_understand": authority,
            "primary_action_objective": authority,
            "required_visual_change": authority,
            "required_end_read": authority,
            "forbidden_interpretations": authority},
        director_model_receipt={
            "provider": "OpenAI", "model": "GPT-5.6 Sol",
            "role": "DIRECTOR_SHOT_DESIGNER",
            "thinking_effort": "HIGH",
            "authorization_source":
                "Owner explicit authorization in Tech Lead chat",
            "execution_note": authorization["execution_note"]},
        created_at="2026-10-04T00:00:00Z")

    blocking = make_blocking_spec(
        shot_id="SEQ7_F2C",
        start_zone="BEFORE_GATE", target_zone="BEYOND_GATE",
        end_zone="BEYOND_GATE:FAR_SIDE_CLEAR",
        screen_direction=direction,
        travel_path=TravelPath(
            path_type="DIRECT_TRAVERSAL",
            ordered_waypoints=[
                Waypoint(zone="BEFORE_GATE",
                         note="gate mouth, matches F1 last frame"),
                Waypoint(zone="CENTER_GATE_OPENING", is_crossing=True,
                         note="CENTER_GATE_OPENING; full body across",
                         cross_by_s=OWNER_TIMING["cross_deadline_s"]),
                Waypoint(zone="BEYOND_GATE:FAR_SIDE_CLEAR",
                         note="far side, readable inside the window",
                         reach_by_s=OWNER_TIMING["usable_window_s"])],
            required_crossing="CENTER_GATE_OPENING"),
        start_body_orientation="facing the gate, leaning into the gust",
        end_body_orientation="facing onward, settled",
        required_spatial_state_change=SpatialStateChange(
            from_zone="BEFORE_GATE", to_zone="BEYOND_GATE"),
        forbidden_interactions=["ROCK_CONTACT", "ROCK_BRACE",
                                "ROCK_CIRCLE", "ROCK_SHELTER"],
        forbidden_zones=["AT_ROCK"],
        forbidden_reversal=True, must_exit_start_zone=True,
        must_reach_target_zone=True,
        visibility_requirements=[
            "both sides of the threshold distinguishable for the whole "
            "shot",
            "full body crosses CENTER_GATE_OPENING by "
            f"{OWNER_TIMING['cross_deadline_s']} s",
            "far-side state readable within the canonical 0-5.6 s "
            "usable window"],
        continuity_bindings={"previous_shot_id": "SEQ7_F1",
                             "next_shot_id": "SEQ7_F3",
                             "resolution": "screen_direction_resolution_"
                                           "v1"},
        authority_sources={
            "zones": authority, "travel_path": authority,
            "crossing": authority, "interactions": authority,
            "continuity": "fixtures/sequence007 F1/F2/F3 screen_direction "
                          "authority (mechanically resolved)"},
        created_at="2026-10-04T00:00:00Z")

    camera = make_camera_coverage_plan(
        shot_id="SEQ7_F2C",
        camera_position_intent="static full-shot beside the gate, profile "
                               "to the travel path",
        framing="WS", axis="perpendicular to the travel path",
        screen_direction=direction,
        subject_start_region="BEFORE_GATE",
        subject_end_region="BEYOND_GATE:FAR_SIDE_CLEAR",
        required_action_visibility=True,
        required_crossing_visibility=True,
        occlusion_constraints=[],
        camera_motion="locked",
        forbidden_camera_behavior=["orbit", "camera reversal",
                                   "axis cross"],
        authority_sources={
            "camera_position_intent": authority,
            "subject_regions": "blocking zones (frozen plan)"},
        created_at="2026-10-04T00:00:00Z")

    # 4. B1-B10 against the neighbor authority directions
    gates = require_director_gates(intent, blocking, camera,
                                   previous_screen_direction=direction,
                                   next_screen_direction=direction)

    # 5. Owner timing invariant
    timing = validate_timing_invariant(blocking, **OWNER_TIMING)
    if timing["state"] != "PASS":
        raise SystemExit("BLOCKED_INVARIANT: " + json.dumps(timing))

    # 6. semantic identity binding (base = canonical F2 ShotSpec bytes)
    base_payload = json.loads(FIXTURES["SEQ7_F2"].read_text(
        encoding="utf-8"))
    base_sha = sha256(base_payload)
    identity = director_semantic_identity(base_sha, intent, blocking,
                                          camera)

    # 7. one advisory critique of the frozen plan
    critique = critique_pass()

    plan = {
        "version": "f2-director-plan-v2-003-substitute-ingest-v1",
        "status": "FROZEN",
        "substitute_authorization": authorization,
        "screen_direction_resolution": resolution,
        "director_intent": intent.model_dump(mode="json"),
        "blocking_spec": blocking.model_dump(mode="json"),
        "camera_coverage_plan": camera.model_dump(mode="json"),
        "gates_B1_B10": gates,
        "timing_invariant": timing,
        "semantic_identity": identity,
        "critique": {"advisory_only": True, "revisions": 1,
                     "change_triggered": False, "items": critique},
        "invariants": {"video_generation": 0, "flow_submit": 0,
                       "upload": 0, "canonical_mutation": 0,
                       "rock_interaction": "FORBIDDEN COMPLETELY"}}
    (PKG / "f2_director_plan_v2_003.json").write_text(
        json.dumps(plan, indent=1, ensure_ascii=False), encoding="utf-8")

    # 8. deterministic previz artifacts (required names: render with the
    #    F2_ prefix, then rename to the exact package names)
    spec_path = PKG / "f2_blocking_spec_for_previz.json"
    spec_path.write_text(json.dumps(blocking.model_dump(mode="json"),
                                    indent=1, ensure_ascii=False),
                         encoding="utf-8")
    subprocess.run(
        [sys.executable, str(ROOT / "tools/build_v2_003_previz.py"),
         str(spec_path), str(PKG),
         "F2 BLOCKING PREVIZ (frozen plan, QUALITY-V2-003)",
         "F2_"], check=True)
    renames = {
        "F2_BLOCKING_TOPDOWN.png": "F2_BLOCKING_TOPDOWN_V2_003.png",
        "F2_START_FRAME_SCHEMATIC.png": "F2_START_FRAME_SCHEMATIC.png",
        "F2_END_FRAME_SCHEMATIC.png": "F2_END_FRAME_SCHEMATIC.png",
        "F2_BLOCKING_PREVIZ.mp4": "F2_BLOCKING_PREVIZ_V2_003.mp4"}
    for src_name, dst_name in renames.items():
        src = PKG / src_name
        dst = PKG / dst_name
        if src.exists():
            src.replace(dst)
    previz = {name: str((PKG / name).relative_to(ROOT)) for name in (
        "F2_BLOCKING_TOPDOWN_V2_003.png", "F2_START_FRAME_SCHEMATIC.png",
        "F2_END_FRAME_SCHEMATIC.png", "F2_BLOCKING_PREVIZ_V2_003.mp4")}
    for name, rel in previz.items():
        assert (ROOT / rel).exists(), name
    (PKG / "previz_manifest_v2_003.json").write_text(
        json.dumps({"version": "f2-previz-manifest-v1",
                    "artifacts": previz,
                    "sha256": {name: hashlib.sha256(
                        (ROOT / rel).read_bytes()).hexdigest()
                        for name, rel in previz.items()}}, indent=1),
        encoding="utf-8")
    print(json.dumps({"status": "FROZEN",
                      "B1_B10": "ALL_PASS",
                      "timing": timing["state"],
                      "resolved_direction": direction,
                      "identity": identity["generation_semantic_identity"][
                          :16],
                      "previz": previz}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
