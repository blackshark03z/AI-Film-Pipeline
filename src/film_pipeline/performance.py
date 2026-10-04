"""Performance/motion control layer (Package-017).

EXTENDS existing truth; never parallels it:

- PerformanceSpec attaches to the existing ShotSpec as an OPTIONAL field
  (legacy shots parse unchanged; nothing is rewritten). It separates
  ACTION DESCRIPTION (what happens — the existing beats) from
  PERFORMANCE DIRECTION (how the body does it — biomechanics).
- BodyProportionAuthority extends the character identity authority with
  body fields ONLY where authority exists; exact proportion is UNKNOWN
  for this film (the reference is a chest-up portrait), so only the
  Owner's directional constraint is recorded as truth.
- classify_action_complexity is a deterministic ADVISORY rule: HIGH or
  EXTREME motion-risk shots may warrant SPLIT_SHOT, but nothing is
  rewritten automatically.
"""
from __future__ import annotations

from typing import Literal

from pydantic import Field, model_validator

from .core import (ContractModel, PerformanceBeat, PerformanceSpec,
                   canonical_json, sha256)

PERFORMANCE_SPEC_VERSION = "performance-spec-v1"
BODY_AUTHORITY_VERSION = "body-proportion-authority-v1"

# The canonical PerformanceSpec/PerformanceBeat models live in core
# (they are part of the ShotSpec contract surface); this module carries
# the BodyProportionAuthority and the advisory logic that operates on
# the specs.


class BodyProportionAuthority(ContractModel):
    """Body fields appended to the EXISTING character identity authority.

    Exact values are recorded only where authoritative references exist.
    `body_proportion_exact_authority = UNKNOWN` keeps subjective
    impressions out of truth; `avoid_short_compact_silhouette` is the
    Owner's directional constraint (a direction, not a measurement)."""
    schema_version: Literal["body-proportion-authority-v1"] = \
        BODY_AUTHORITY_VERSION
    character_id: str = Field(min_length=1)
    identity_version: str = Field(min_length=1)
    stature: str = "UNKNOWN"
    body_build: str = "UNKNOWN"
    body_proportion: str = "UNKNOWN"
    limb_proportion: str = "UNKNOWN"
    torso_leg_relationship: str = "UNKNOWN"
    shoulder_width: str = "UNKNOWN"
    waist_silhouette: str = "UNKNOWN"
    posture: str = ""
    gait_profile: str = ""
    body_proportion_exact_authority: Literal["UNKNOWN"] = "UNKNOWN"
    avoid_short_compact_silhouette: bool = False
    authority_basis: str = Field(min_length=1)

    @model_validator(mode="after")
    def validate_no_fake_precision(self):
        measured = {"stature", "body_build", "body_proportion",
                    "limb_proportion", "torso_leg_relationship",
                    "shoulder_width", "waist_silhouette"}
        exact = [f for f in measured
                 if getattr(self, f) not in ("UNKNOWN", "")]
        if exact and self.body_proportion_exact_authority != "EXACT":
            raise ValueError(
                f"measured body values {exact} recorded without exact "
                f"authority; keep UNKNOWN or prove a full-body reference")
        return self

    def directional_constraints(self) -> list[str]:
        return (["tall, long-legged, non-compact silhouette"]
                if self.avoid_short_compact_silhouette else [])

    def digest(self) -> str:
        return sha256(canonical_json(self.model_dump(mode="json")))


# Deterministic advisory action-complexity classification (Phase 4).
MAJOR_ACTION_FACETS = (
    "locomotion",        # run / step-driven travel
    "turn",              # significant body rotation
    "contact_event",     # strike / catch / object interaction
    "draw_or_weapon",    # drawing or manipulating a weapon
    "reaction",          # visible physical reaction to an event
    "camera_move",       # non-locked camera
)


def classify_action_complexity(spec: PerformanceSpec, *,
                               camera_locked: bool = True) -> dict:
    """Advisory complexity class from simultaneous major physical facets.

    ONE DOMINANT PHYSICAL ACTION per clip is the production principle.
    HIGH/EXTREME shots may warrant SPLIT_SHOT — a recommendation only;
    story/edit structure is never rewritten automatically."""
    facets = []
    if spec.locomotion:
        facets.append("locomotion")
    if spec.contact_event:
        facets.append("contact_event")
    if spec.reaction and spec.motion_energy in ("moderate", "high"):
        facets.append("reaction")
    if spec.hip_torso_rotation and spec.motion_energy == "high":
        facets.append("turn")
    if "weapon" in (spec.primary_action + " " + spec.action_intent
                    + " " + spec.contact_event).lower():
        facets.append("draw_or_weapon")
    if not camera_locked:
        facets.append("camera_move")
    if "weapon" in spec.primary_action.lower() and \
            "draw" in spec.primary_action.lower():
        facets.append("draw_or_weapon")
    facets = sorted(set(facets))
    count = len(facets)
    risk = ("LOW" if count <= 1 else "MEDIUM" if count == 2 else
            "HIGH" if count == 3 else "EXTREME")
    return {"motion_risk_class": risk,
            "facets": facets,
            "major_action_count": count,
            "recommendation": ("SPLIT_SHOT (advisory only — requires "
                               "explicit Tech Lead/Owner acceptance)"
                               if risk in ("HIGH", "EXTREME")
                               else "NONE"),
            "principle": "one dominant physical action per generated "
                         "clip whenever practical"}
