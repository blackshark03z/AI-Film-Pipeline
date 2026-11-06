"""Offline choreography handoff regressions; no claim of video understanding."""
import json
import subprocess
import sys
from pathlib import Path

import pytest

from film_pipeline.compiler import compile_prompt
from film_pipeline.core import sha256
from film_pipeline.e2e import prepare, resume, status
from film_pipeline.e2e_flow import shot_spec
from film_pipeline.flow_r2v_runtime import compact_r2v_prompt
from film_pipeline.live_runtime import file_sha256
from film_pipeline.providers import flow_rpc_contract as contract
from test_e2e import fixture_direction, media, source_srt
from test_flow_r2v_runtime import flow_capabilities


@pytest.fixture
def directed_project(tmp_path):
    audio, srt = tmp_path / 'audio.mp3', tmp_path / 'source.srt'
    media(audio)
    source_srt(srt)
    root = tmp_path / 'film'
    prepare(audio, srt, 18, 48, root)
    plan = json.loads((root / 'shots.json').read_text())
    for shot in plan['shots']:
        shot.update(visual_intent='Interaction', image_prompt='Same actors',
                    video_prompt='One gesture, then arms at sides')
        fixture_direction(shot)
    return root, plan


def save_plan(root, plan):
    (root / 'shots.json').write_text(json.dumps(plan))


def test_local_status_does_not_require_live_flow_dependencies(directed_project):
    root, plan = directed_project
    save_plan(root, plan)
    cli = Path(__file__).resolve().parents[1] / 'tools/film_e2e.py'
    script = '''import importlib.abc, runpy, sys
class OfflineOnly(importlib.abc.MetaPathFinder):
    def find_spec(self, fullname, path=None, target=None):
        if fullname.split('.')[0] in {'PIL', 'playwright', 'patchright'}:
            raise ModuleNotFoundError('optional live dependency blocked: ' + fullname)
sys.meta_path.insert(0, OfflineOnly())
cli, project = sys.argv[1:]
sys.argv = [cli, 'status', '--project', project]
runpy.run_path(cli, run_name='__main__')
'''
    result = subprocess.run([sys.executable, '-c', script, str(cli), str(root)],
                            capture_output=True, text=True, timeout=30)
    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout)['direction_issues'] == []


def test_missing_settled_state_refuses_lock_without_runtime_mutation(directed_project):
    root, plan = directed_project
    plan['shots'][0]['blocking']['end'] = ''
    save_plan(root, plan)
    database = root / 'runtime.sqlite'
    before = file_sha256(database)
    assert status(root)['direction_issues']
    with pytest.raises(ValueError, match='interaction direction incomplete'):
        resume(root, database, 'offline-project')
    assert json.loads((root / 'project.json').read_text())['locked_plan_sha256'] is None
    assert file_sha256(database) == before


def test_contact_still_held_cannot_hand_off_to_released_contact(directed_project):
    root, plan = directed_project
    plan['shots'][0]['continuity']['end_state']['hand_contact'] = True
    save_plan(root, plan)
    with pytest.raises(ValueError, match='continuity state hand_contact conflicts'):
        resume(root, root / 'runtime.sqlite', 'offline-project')


def test_release_and_receiver_recovery_reach_real_compact_prompt():
    planned = {'shot_id': 'INTERACTION', 'visual_intent': 'Shove and disengage',
        'video_prompt': 'Brennan shoves once, then withdraws his hand. Irene recoils.',
        'blocking': {'start': 'Both stand apart',
                     'end': 'Brennan arm at side; Irene steady at counter'},
        'continuity': {'screen_direction': 'Brennan right', 'eyeline': 'at each other',
            'start_state': {'hand_contact': False}, 'end_state': {'hand_contact': False}}}
    spec = shot_spec(planned, 'reference', plan_version=2)
    plan = compile_prompt(spec, flow_capabilities(), reference_hashes={'reference': 'a' * 64})
    wire = compact_r2v_prompt(plan, 'job_' + 'b' * 64, model=contract.MODEL_VEO_3_1_LITE)
    assert 'withdraws his hand' in wire.text
    assert 'Irene recoils' in wire.text
    assert 'End: Brennan arm at side; Irene steady at counter' in wire.text
    assert spec.continuity.end_state == {'hand_contact': False}
    changed = shot_spec({**planned, 'blocking': {**planned['blocking'], 'end': 'Hand stays on arm'}}, 'reference', plan_version=2)
    assert sha256(changed) != sha256(spec)


SHOVE_PHASES = {'phases': [
    {'kind': 'SETUP', 'start_s': 0, 'end_s': 2, 'description': 'tense standoff'},
    {'kind': 'ACTION', 'start_s': 2, 'end_s': 3, 'description': 'Brennan shoves once'},
    {'kind': 'REACTION', 'start_s': 3, 'end_s': 8, 'description': 'Irene staggers back'}],
    'once_actions': ['shoves once']}


def test_drama_choreography_blocks_lock_when_phases_do_not_cover_generation(directed_project):
    root, plan = directed_project
    plan['shots'][0]['choreography'] = {**SHOVE_PHASES, 'phases': SHOVE_PHASES['phases'][:2]}
    save_plan(root, plan)
    issues = status(root)['direction_issues']
    assert any('last phase ends at 3s, not 8s' in issue for issue in issues)
    with pytest.raises(ValueError, match='interaction direction incomplete'):
        resume(root, root / 'runtime.sqlite', 'offline-project')


def test_drama_choreography_timing_reaches_shot_spec():
    planned = {'shot_id': 'SHOVE', 'visual_intent': 'Shove and stagger',
        'video_prompt': 'Brennan shoves Irene; she staggers back.',
        'blocking': {'start': 'Facing each other', 'end': 'Apart, both standing'},
        'continuity': {'screen_direction': None, 'eyeline': None,
            'start_state': {'hand_contact': False}, 'end_state': {'hand_contact': False}},
        'choreography': SHOVE_PHASES}
    beats = shot_spec(planned, 'reference', plan_version=2).blocking.action_beats
    assert beats[0] == planned['video_prompt']
    assert '2-3s action: Brennan shoves once' in beats[1]
    assert 'Happens exactly once: shoves once' in beats[1]
    legacy = shot_spec(planned, 'reference', plan_version=1).blocking.action_beats
    assert legacy == [planned['video_prompt']]


def test_action_meaning_gates_lock_and_warns_on_escalation(directed_project):
    root, plan = directed_project
    shot = plan['shots'][0]
    shot['choreography'] = SHOVE_PHASES
    shot['action_meaning'] = {'source_cues': [1], 'initiator': 'She', 'action': 'walks'}
    save_plan(root, plan)
    issues = status(root)['direction_issues']
    assert any("action 'walks' is not in the source sentence" in issue for issue in issues)
    with pytest.raises(ValueError, match='interaction direction incomplete'):
        resume(root, root / 'runtime.sqlite', 'offline-project')
    shot['action_meaning']['action'] = 'enters'
    shot['video_prompt'] = 'She enters and slams the door'
    save_plan(root, plan)
    report = status(root)
    assert report['direction_issues'] == []
    assert any("'slam'" in w for w in report['action_warnings'][shot['shot_id']])
    assert report['plan_review_required'] is False


@pytest.mark.parametrize('metadata', ['absent', 'populated', 'partial'])
def test_legacy_locked_plan_reopens_without_identity_or_file_change(directed_project, metadata):
    root, plan = directed_project
    plan['version'] = 1
    for shot in plan['shots']:
        if metadata == 'absent':
            shot.pop('blocking')
            shot.pop('continuity')
        elif metadata == 'partial':
            shot['blocking'] = {'end': None}
            shot['continuity'] = None
    save_plan(root, plan)
    meta_path = root / 'project.json'
    meta = json.loads(meta_path.read_text())
    meta.update(version=1, locked_plan_sha256=file_sha256(root / 'shots.json'),
                flow_project_id='offline-project', status='PLAN_LOCKED_AWAITING_FLOW_MEDIA')
    meta_path.write_text(json.dumps(meta, ensure_ascii=False, sort_keys=True, indent=2) + '\n')
    before = {p: file_sha256(root / p) for p in ('shots.json', 'project.json', 'runtime.sqlite')}
    spec = shot_spec(plan['shots'][0], 'reference')
    state = resume(root, root / 'runtime.sqlite', 'offline-project')
    assert state['legacy_direction_unassessed'] is True and state['direction_issues'] == []
    assert spec.blocking.start == 'reference pose' and spec.blocking.end == 'hold'
    assert spec.continuity.start_state == spec.continuity.end_state == {}
    assert before == {p: file_sha256(root / p) for p in before}
