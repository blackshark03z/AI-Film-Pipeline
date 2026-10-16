"""V2-021 shared run plumbing — the two mappings every 021 tool needs.

Single source of truth for:

1. alias -> profile root   (which directory holds a slot's enrolled
   browser state). The runner CLI, the reconcile tool and the recover
   tool each re-implemented this mapping; that three-way duplication is
   the drift class behind the V2-021 E/F wrong-profile-root defect — a
   dispatch silently opened an empty profile and the provider answered
   USER_LOGIN_REQUIRED.

2. the discovery needle convention: the MOTION section of a frozen
   ProviderPromptPlan is unique per shot function (two shots may share a
   subject line; conversation discovery must not cross-match), and the
   needle is its first 80 characters.

No import-time reads of ignored `projects/` state: every helper takes its
inputs explicitly.
"""
from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PKG = ROOT / "projects/quality_v2_021_narrative_compiler"
PKG_PROFILES = PKG / "pool_profiles"
ENROLLED_SLOTS = ("ACCOUNT_E", "ACCOUNT_F")


def enrolled_profile_root(alias: str, legacy_root: Path) -> Path:
    """Alias -> the profile root that holds its enrolled browser state.

    The V2-021 enrolled slots (ACCOUNT_E/ACCOUNT_F) live in THIS
    package's pool_profiles; the rest of the pool lives in the legacy
    010E runtime root. Every browser touch for an alias — probe OR
    dispatch — must address the same root.
    """
    return PKG_PROFILES if alias in ENROLLED_SLOTS else Path(legacy_root)


def needle_for(comp: dict, shot_id: str) -> str:
    """Discovery needle for a frozen shot: first 80 chars of MOTION."""
    return comp["prompt_plans"][shot_id]["sections"]["motion"][:80]
