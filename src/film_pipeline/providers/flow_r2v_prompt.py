"""Pure provider adaptation; canonical Film PromptPlan is never rewritten."""
from __future__ import annotations

import re
from dataclasses import dataclass

from ..core import PromptPlan, sha256

VERSION = 'flow-r2v-compact-v1'
MODEL = 'abra_r2v_8s'
MAX_PROMPT_CHARS = 1800
MAX_PROMPT_WORDS = 240
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


def compile_flow_r2v_prompt(plan: PromptPlan, provider_job_id: str) -> FlowR2VPrompt:
    """Derive cinematic prose from creative blocks, preserving their source."""
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
        purpose = blocks['SHOT / DRAMATIC PURPOSE']['dramatic_purpose']
        performance = blocks['ACTION / PERFORMANCE']['performance'] or {}
        camera = blocks['CAMERA / LENS / MOVEMENT']['camera']
        blocking = blocks['BLOCKING / START-END STATE']['blocking']
        environment = blocks['ENVIRONMENT / WORLD LOCK']['environment'] or {}
        continuity = blocks['CONTINUITY CONSTRAINTS']['continuity']
        negatives = blocks['NEGATIVE / FORBIDDEN BEHAVIOR']
        lighting = blocks['LIGHTING / STYLE']['lighting'] or {}
        audio = blocks['AUDIO / DIALOGUE']['audio'] or {}
    except (KeyError, TypeError):
        raise ValueError('FLOW_R2V_CREATIVE_BLOCKS_INVALID') from None
    if duration != 8:
        raise ValueError('FLOW_R2V_DURATION_UNSUPPORTED')

    def prose(value):
        if not isinstance(value, str):
            raise ValueError('FLOW_R2V_CREATIVE_TEXT_INVALID')
        clean = ' '.join(value.replace('_', ' ').split()).rstrip('.; ')
        if '[FILM-' in clean:
            raise ValueError('FLOW_R2V_CREATIVE_MARKER_COLLISION')
        return clean

    framings = {'ECU': 'extreme close-up', 'CU': 'close-up', 'MCU': 'medium close-up',
        'MS': 'medium shot', 'MLS': 'medium long shot', 'WS': 'wide shot', 'EWS': 'extreme wide shot',
        'OTS': 'over-the-shoulder shot', 'TWO_SHOT': 'two-shot', 'INSERT': 'insert', 'CUTAWAY': 'cutaway'}
    sentences = [f"8-second cinematic {framings[camera['framing']]}, 16:9, "
        f"{prose(camera['height'])}, {prose(camera['lens_intent'])} lens, {prose(camera['movement']['type'])} camera",
        prose(purpose), 'Use the exact image reference', prose(blocking['start']),
        '; '.join(dict.fromkeys(prose(v) for v in blocking['action_beats']
                               + performance.get('observable_beats', [])
                               + blocking.get('prop_interactions', []))), prose(blocking['end'])]
    if environment:
        sentences.append('; '.join(prose(environment[k]) for k in ('time_of_day', 'weather', 'atmosphere')
                                   if environment.get(k)))
    if camera['movement'].get('purpose'):
        sentences.append(prose(camera['movement']['purpose']))
    locks = list(dict.fromkeys(continuity.get('critical_invariants', [])
        + blocks['CONTINUITY CONSTRAINTS'].get('must_preserve', [])))
    if locks:
        sentences.append('Preserve ' + '; '.join(prose(v) for v in locks))
    if continuity.get('screen_direction') or continuity.get('eyeline'):
        sentences.append('; '.join(prose(v) for v in
            (continuity.get('screen_direction'), continuity.get('eyeline')) if v))
    if lighting:
        sentences.append('; '.join(prose(v) for v in lighting.values() if v))
    if audio:
        sentences.append('; '.join(prose(audio[k]) for k in ('dialogue', 'room_tone', 'sfx_intent') if audio.get(k)))
    forbidden = list(dict.fromkeys(negatives.get('performance_forbidden', []) + negatives.get('must_avoid', [])))
    if forbidden:
        sentences.append('Avoid ' + '; '.join(prose(v) for v in forbidden))
    text = '. '.join(v for v in sentences if v) + '.\n' + marker
    if len(text) > MAX_PROMPT_CHARS or len(text.split()) > MAX_PROMPT_WORDS:
        raise ValueError('FLOW_R2V_COMPACT_PROMPT_LIMIT; explicit creative reduction required')
    return FlowR2VPrompt(text, marker, sha256(plan))
