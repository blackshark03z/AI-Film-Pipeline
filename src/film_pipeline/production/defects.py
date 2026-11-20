"""Registry of reviewed defect codes: the custody link between a detector signal, a human review and a repair.

Chain of custody (each step is bound to the clip hash, so it cannot be replayed on other footage)::

    detector signal  --(a reviewer looks at the clip)-->  reviewed defect on a take review  -->  repair action

* A detector signal (``EDGE_INTRUSION_SUSPECT`` ...) is only a suspicion. It never triggers a repair by itself.
* A reviewed defect (``qc_model.ReviewedDefect``) names a code from this registry, the clip hash and the time ranges the
  reviewer judged. It may cite the ``source_signal`` that prompted it, but only a code whose ``confirms_signals`` lists that
  signal code can be confirmed from it.
* The registry fixes the broad cause (``qc_model.Cause``), the repair action and whether a plain automatic retry is allowed.
  Only a provider artefact may simply be rendered again; every other defect needs a changed start frame, prompt or staging.
* An unknown code, or a code whose action the router does not know, STOPs (``causal_repair.STOP_UNKNOWN_DEFECT``).

Seeded from the rejections actually written in film07_first_shift and film08_chain_of_custody take reviews and from the
repair actions already in ``causal_repair``. Codes:

    OFFFRAME_INTRUSION       off-frame listener's head / hair / shoulder enters the frame edge (restage, de-personify)
    IDENTITY_DRIFT           a character's face / look changes or a second copy of a character appears
    WRONG_SPEAKER_LIPSYNC    the wrong person speaks, mouth does not match the line, or an unscripted line is heard
    DIALOGUE_TRUNCATED       a scripted line is cut at the start / end or does not fit the clip
    GAZE_EYELINE_DRIFT       eyes look into the lens or away from the scripted eyeline, screen direction wrong
    PROP_CONTINUITY_BREAK    wrong hand / prop state / background side of the room against the plan
    CAMERA_INSTABILITY       unplanned push-in, drift or shake of the camera
    PROVIDER_ARTEFACT        transient provider glitch (corrupt frames, stall); the only code a plain retry may fix
"""
from __future__ import annotations

from dataclasses import dataclass

# Actions the repair router understands (the old cause-based table plus the registry's). Anything else STOPs.
KNOWN_ACTIONS = frozenset({
    "rewrite_prompt_plain_single_action", "split_into_shorter_beat",
    "regenerate_start_still", "restage_clean_character_still",
    "retry_transient_once", "cover_with_insert_or_reaction",
    "simplify_choreography_phase", "restage_blocking_or_insert",
    "enable_de_personify_off_frame", "upgrade_single_to_ots",
    "restage_start_still", "reframe_safe_edge", "pin_end_frame_prop_state", "trim_or_pace_line",
    "HALT_HUMAN_DECISION",
})


@dataclass(frozen=True)
class DefectSpec:
    code: str
    cause: str  # one of qc_model.Cause (checked by the registry test; no import here to keep qc_model importing this module)
    description: str
    repair_action: str  # a member of KNOWN_ACTIONS
    auto_retry_allowed: bool
    confirms_signals: tuple[str, ...] = ()  # detector signal codes a reviewer may confirm into this defect


_SPECS = (
    DefectSpec("OFFFRAME_INTRUSION", "STAGING",
               "off-frame listener's head, hair or shoulder enters the frame edge although the shot must hold them out",
               "enable_de_personify_off_frame", False, ("EDGE_INTRUSION_SUSPECT",)),
    DefectSpec("IDENTITY_DRIFT", "START_FRAME",
               "a character's face or look drifts from the cast still, or a second copy of a character appears",
               "restage_clean_character_still", False),
    DefectSpec("WRONG_SPEAKER_LIPSYNC", "PROMPT",
               "the wrong person speaks, the mouth does not follow the line, or an unscripted line is heard",
               "rewrite_prompt_plain_single_action", False),
    DefectSpec("DIALOGUE_TRUNCATED", "PROMPT",
               "a scripted line is cut at its start or end, or does not fit the clip length",
               "trim_or_pace_line", False),
    DefectSpec("GAZE_EYELINE_DRIFT", "START_FRAME",
               "eyes look into the lens or off the scripted eyeline, or the screen direction is wrong",
               "restage_start_still", False),
    DefectSpec("PROP_CONTINUITY_BREAK", "START_FRAME",
               "the hand, prop state or background side of the room contradicts the plan or the previous shot",
               "pin_end_frame_prop_state", False),
    DefectSpec("CAMERA_INSTABILITY", "PROMPT",
               "unplanned push-in, drift or shake of the camera",
               "reframe_safe_edge", False),
    DefectSpec("PROVIDER_ARTEFACT", "PROVIDER_LIMIT",
               "transient provider glitch (corrupt frames, stall) not caused by the prompt or the start frame",
               "retry_transient_once", True),
)

DEFECTS: dict[str, DefectSpec] = {s.code: s for s in _SPECS}


def get_defect(code: str) -> DefectSpec | None:
    return DEFECTS.get(str(code or "").strip())


def signal_may_confirm(defect_code: str, signal_code: str) -> bool:
    spec = DEFECTS.get(defect_code)
    return spec is not None and signal_code in spec.confirms_signals
