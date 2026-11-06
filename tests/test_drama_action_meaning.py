from film_pipeline.drama.action_meaning import ActionMeaning, sentences
from film_pipeline.drama.choreography import GenerationChoreography

CUES = [{'index': 5, 'start_s': 10.0, 'end_s': 12.0, 'text': 'Brennan shoved Irene.'},
        {'index': 6, 'start_s': 12.0, 'end_s': 14.0, 'text': 'She staggered back.'}]
SPLIT = [{'index': 1, 'start_s': 0.0, 'end_s': 2.0, 'text': 'Brennan shoved'},
         {'index': 2, 'start_s': 2.0, 'end_s': 4.0, 'text': 'Irene hard.'}]
WINDOW = (8.0, 16.0)


def choreo(once=('shoves once',), kinds=('SETUP', 'ACTION', 'REACTION')):
    spans = {'SETUP': (0, 2), 'ACTION': (2, 3), 'REACTION': (3, 8)}
    if kinds == ('SETUP', 'ACTION', 'HOLD'):
        spans['HOLD'] = (3, 8)
    return GenerationChoreography.model_validate({'generation_id': 'S1',
        'phases': [{'kind': k, 'start_s': spans[k][0], 'end_s': spans[k][1], 'description': k.lower()}
                   for k in kinds],
        'once_actions': list(once)})


def meaning(**over):
    data = {'source_cues': [5, 6], 'initiator': 'Brennan', 'action': 'shoved',
            'receiver': 'Irene', 'consequence': 'staggered back'}
    return ActionMeaning.model_validate({**data, **over})


def details(m, cues=CUES, choreography=None, window=WINDOW):
    return [i.detail for i in m.problems('S1', cues, window, choreography)]


def test_sentences_join_split_cues_and_keep_ids():
    found = sentences(SPLIT + CUES)
    assert found[0]['cue_ids'] == [1, 2]
    assert found[0]['text'] == 'Brennan shoved Irene hard.'
    assert [s['cue_ids'] for s in found[1:]] == [[5], [6]]


def test_correct_declaration_has_no_problems():
    assert details(meaning(), choreography=choreo()) == []


def test_unknown_cue_blocks():
    assert any('not in the SRT' in d for d in details(meaning(source_cues=[5, 99]), choreography=choreo()))


def test_partial_sentence_blocks():
    m = meaning(source_cues=[1], initiator='Brennan', action='shoved', receiver='', consequence='')
    assert any('declare the whole sentence' in d
               for d in details(m, cues=SPLIT, choreography=choreo(), window=(0.0, 8.0)))


def test_word_not_in_source_blocks():
    assert any("action 'pushed' is not in the source" in d
               for d in details(meaning(action='pushed'), choreography=choreo()))


def test_missing_choreography_blocks():
    assert any('choreography' in d for d in details(meaning()))


def test_consequence_needs_reaction_after_action():
    found = details(meaning(), choreography=choreo(kinds=('SETUP', 'ACTION', 'HOLD')))
    assert any('REACTION/CONSEQUENCE' in d for d in found)


def test_empty_once_actions_blocks():
    assert any('once_actions' in d for d in details(meaning(), choreography=choreo(once=())))


def test_escalations_flag_only_words_absent_from_source():
    m = meaning()
    assert m.escalations(CUES, 'Irene arches into a backbend') == ['backbend', 'arch']
    assert m.escalations(CUES, 'Brennan shoved Irene, who staggered back') == []


def test_qc_questions_mention_initiator_action_consequence():
    text = ' '.join(meaning().qc_questions())
    assert 'Brennan' in text and 'shoved' in text and 'staggered back' in text
