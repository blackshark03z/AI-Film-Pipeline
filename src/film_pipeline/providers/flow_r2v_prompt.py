"""Pure provider adaptation; canonical Film PromptPlan is never rewritten."""
from __future__ import annotations

import re
from dataclasses import dataclass

from ..core import PromptPlan, sha256

VERSION = 'flow-r2v-compact-v1'
MODEL = 'abra_r2v_8s'
MAX_PROMPT_CHARS = 500  # Creative body only; the final marker is not counted.
MAX_PROMPT_WORDS = 75
JOB_RE = re.compile(r'job_[a-f0-9]{64}')
MARKER_RE = re.compile(r'\[FILM-job_[a-f0-9]{64}\]')


def film_marker(provider_job_id: str) -> str:
    if not isinstance(provider_job_id, str) or not JOB_RE.fullmatch(provider_job_id):
        raise ValueError('FLOW_R2V_JOB_ID_INVALID')
    return f'[FILM-{provider_job_id}]'


@dataclass(frozen=True)
class FlowR2VPrompt:
    text: str
    marker: str
    canonical_plan_hash: str
    version: str = VERSION
    model: str = MODEL


def compile_flow_r2v_prompt(plan: PromptPlan, provider_job_id: str, *, model: str = MODEL) -> FlowR2VPrompt:
    """Semantic reduction for the qualified illustrated-character R2V envelope.

    Canonical purpose/state/negatives remain in Film. The wire body prioritizes
    camera, exact reference, visible anchors, primary action, room and continuity.
    Known synonymous beats collapse to one meaning; unknown essential meanings
    fail for explicit reduction rather than being sliced or silently omitted.
    """
    marker = film_marker(provider_job_id)
    blocks = plan.canonical_blocks
    image_input = plan.mapped_controls.get('image_input')
    if (plan.provider_id != 'flow_veo' or not isinstance(image_input, list) or len(image_input) != 1
            or not isinstance(image_input[0], dict)
            or set(image_input[0]) != {'asset_id', 'sha256'}
            or not re.fullmatch('[a-f0-9]{64}', image_input[0].get('sha256', ''))):
        raise ValueError('FLOW_R2V_EXACT_IMAGE_INPUT_REQUIRED')
    try:
        duration = blocks['SHOT / DRAMATIC PURPOSE']['duration_target_s']
        performance = blocks['ACTION / PERFORMANCE']['performance'] or {}
        camera = blocks['CAMERA / LENS / MOVEMENT']['camera']
        blocking = blocks['BLOCKING / START-END STATE']['blocking']
        environment = blocks['ENVIRONMENT / WORLD LOCK']['environment'] or {}
        continuity = blocks['CONTINUITY CONSTRAINTS']['continuity']
        characters = blocks['SUBJECT / CHARACTER LOCK']['characters']
    except (KeyError, TypeError):
        raise ValueError('FLOW_R2V_CREATIVE_BLOCKS_INVALID') from None
    if duration != 8:
        raise ValueError('FLOW_R2V_DURATION_UNSUPPORTED')

    def prose(value):
        if not isinstance(value, str):
            raise ValueError('FLOW_R2V_CREATIVE_TEXT_INVALID')
        clean = ' '.join(value.split()).rstrip('.; ')
        if '[FILM-' in clean:
            raise ValueError('FLOW_R2V_CREATIVE_MARKER_COLLISION')
        if any(c in clean for c in '{}[]\n') or re.search(r'\b(?:asset_|CHAR_|ID_V|LOOK_V|REMOTE_|REQUEST_|schema_)', clean):
            raise ValueError('FLOW_R2V_CREATIVE_TEXT_UNQUALIFIED')
        return clean

    # A marker supplied anywhere in creative data cannot become a second marker.
    def creative_strings(value):
        if isinstance(value, str):
            yield value
        elif isinstance(value, dict):
            for child in value.values():
                yield from creative_strings(child)
        elif isinstance(value, list):
            for child in value:
                yield from creative_strings(child)

    if any('[FILM-' in value for value in creative_strings(blocks)):
        raise ValueError('FLOW_R2V_CREATIVE_MARKER_COLLISION')

    framings = {'ECU': 'extreme close-up', 'CU': 'close-up', 'MCU': 'medium close-up',
        'MS': 'medium shot', 'MLS': 'medium long shot', 'WS': 'wide shot', 'EWS': 'extreme wide shot',
        'OTS': 'over-the-shoulder shot', 'TWO_SHOT': 'two-shot', 'INSERT': 'insert', 'CUTAWAY': 'cutaway'}
    if (camera['movement'] != {'type': 'locked'} or camera['height'] != 'eye_level'
            or camera.get('lens_intent') != 'portrait'
            or camera['framing'] not in framings
            or continuity.get('screen_direction') != 'slightly_frame_right'):
        raise ValueError('FLOW_R2V_CAMERA_CONTINUITY_REDUCTION_UNQUALIFIED')
    if (len(characters) != 1 or characters[0].get('role_in_shot') != 'single subject'
            or characters[0].get('behavior_state') not in {'calm neutral', 'quiet attention'}):
        raise ValueError('FLOW_R2V_SUBJECT_REDUCTION_UNQUALIFIED')
    # These locks reduce to the single-subject, stable-face/outfit, locked-camera,
    # stable-room and subtle-performance prose. Novel essential restrictions
    # require a qualified semantic mapping; dropping them would be silent loss.
    covered_preserves = {'reference face and look', 'illustrated room layout'}
    covered_restrictions = {'identity change', 'wardrobe change', 'large head turn',
        'extra person', 'identity swap', 'new accessories', 'camera movement', 'scene change'}
    negatives = blocks['NEGATIVE / FORBIDDEN BEHAVIOR']
    if (any(v not in covered_preserves for v in blocks['CONTINUITY CONSTRAINTS'].get('must_preserve', []))
            or any(v not in covered_restrictions for v in
                negatives.get('performance_forbidden', []) + negatives.get('must_avoid', []))):
        raise ValueError('FLOW_R2V_RESTRICTION_REDUCTION_UNQUALIFIED')
    starts = {'one illustrated adult woman faces slightly frame-right in the room',
        'the same illustrated adult woman appears in a closer portrait, still slightly frame-right'}
    ends = {'the same woman holds the same pose and look',
        'she holds the closer pose with the same face, hair, glasses and wardrobe'}
    if prose(blocking['start']) not in starts or prose(blocking['end']) not in ends:
        raise ValueError('FLOW_R2V_POSE_REDUCTION_UNQUALIFIED')
    if (blocks['LIGHTING / STYLE'].get('lighting')
            or blocks['AUDIO / DIALOGUE'].get('audio')):
        raise ValueError('FLOW_R2V_ADDITIONAL_INTENT_REDUCTION_UNQUALIFIED')

    invariants = list(dict.fromkeys(prose(v) for v in continuity.get('critical_invariants', [])))
    if not any('illustrated adult woman' in v for v in invariants):
        raise ValueError('FLOW_R2V_SUBJECT_REDUCTION_UNQUALIFIED')
    anchor_phrases = {
        'teal bob hair': 'teal bob hair',
        'crimson round glasses': 'crimson round glasses',
        'mustard jacket over blue shirt': 'a mustard jacket over a blue shirt',
        'silver triangle earrings': 'silver triangle earrings',
        'small beauty mark below her right eye': 'a beauty mark below her right eye',
    }
    redundant_locks = {
        'same illustrated adult woman as the exact image reference',
        'same illustrated adult woman as Shot A and the exact image reference',
        'one person only', 'no wardrobe or identity mutation',
    }
    if any(v not in anchor_phrases and v not in redundant_locks for v in invariants):
        raise ValueError('FLOW_R2V_IDENTITY_REDUCTION_UNQUALIFIED')
    anchors = [phrase for key, phrase in anchor_phrases.items() if key in invariants]
    if not all(v in invariants for v in ('teal bob hair', 'crimson round glasses', 'mustard jacket over blue shirt')):
        raise ValueError('FLOW_R2V_MINIMAL_IDENTITY_ANCHORS_REQUIRED')
    identity = ', '.join(anchors[:-1]) + ' and ' + anchors[-1]

    # Semantic aliases, not substring truncation: repeated breathing, blinking,
    # expression and gaze instructions each contribute only one concept.
    beat_aliases = {
        'subtle natural breathing': 'breathes gently', 'gentle breathing': 'breathes gently',
        'natural breathing': 'breathes gently',
        'one small blink while keeping a calm neutral expression': 'blinks once',
        'one small natural blink': 'blinks once',
        'her gaze shifts modestly toward the left window': 'shifts her gaze toward the left window',
        'small gaze shift toward window': 'shifts her gaze toward the left window',
        'she keeps a restrained natural expression': None,  # Represented by calm continuity below.
        'one restrained smile': 'smiles faintly',
        'touch the cup gently': 'touches the cup gently',
    }
    actions = []
    for value in blocking['action_beats'] + performance.get('observable_beats', []) + blocking.get('prop_interactions', []):
        beat = prose(value)
        if beat not in beat_aliases:
            if len(beat) > MAX_PROMPT_CHARS:
                raise ValueError('FLOW_R2V_COMPACT_PROMPT_LIMIT; explicit creative reduction required')
            raise ValueError('FLOW_R2V_ACTION_REDUCTION_UNQUALIFIED')
        reduced = beat_aliases[beat]
        if reduced is not None and reduced not in actions:
            actions.append(reduced)
    if not actions:
        raise ValueError('FLOW_R2V_PRIMARY_ACTION_REQUIRED')
    expected_eyeline = ('near_camera_right_to_window_left' if any('left window' in a for a in actions)
                        else 'near_camera_right')
    if continuity.get('eyeline') != expected_eyeline:
        raise ValueError('FLOW_R2V_EYELINE_REDUCTION_UNQUALIFIED')
    action = ', '.join(actions[:-1]) + ' and ' + actions[-1] if len(actions) > 1 else actions[0]
    if (environment.get('time_of_day') != 'day' or environment.get('weather')
            or environment.get('atmosphere') != 'simple illustrated living room with window left and sofa and plant right'):
        raise ValueError('FLOW_R2V_ENVIRONMENT_REDUCTION_UNQUALIFIED')

    body = (f"8-second locked eye-level {framings[camera['framing']]}, 16:9. "
        f"Use the exact image reference: one illustrated adult woman with {identity}; "
        f"facing slightly right, she {action} in a daytime living room, window left, sofa and plant right. "
        'Keep her face and outfit stable; movements subtle and calm.')
    if len(body) > MAX_PROMPT_CHARS or len(body.split()) > MAX_PROMPT_WORDS:
        raise ValueError('FLOW_R2V_COMPACT_PROMPT_LIMIT; explicit creative reduction required')
    return FlowR2VPrompt(body + '\n' + marker, marker, sha256(plan), model=model)
