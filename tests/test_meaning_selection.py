from kanji_translator.meaning_selection import english_quality, select


def test_source_fragments_cannot_become_english_meanings():
    for value in ('Occasionally found on Mishina-', 'cm', 'includingKomaiYoshitomo',
                  'His son Egawa Kamemichi', 'B bachigai-mono'):
        assert not english_quality(value)['eligible']
    assert english_quality('Hollyhock')['eligible']
    assert not english_quality('Hollyhock')['verified']
    result = select({'domain': {'assertions': [{'english': 'Hollyhock', 'source': 'supporting_reference'}]}})
    assert result['english'] is None and result['state'] == 'abstained'


def test_names_and_competing_senses_are_not_forced_into_translations():
    name = {'source': 'jmnedict', 'entry_id': '1', 'kana': 'くにみつ',
            'senses': [{'role': 'trans', 'english': ['Kunimitsu'], 'name_types': ['person']} ]}
    assert select({'candidates': [name]})['english'] is None
    word = {'source': 'jmdict', 'entry_id': '2', 'kana': 'かたな', 'romaji': {'hepburn': 'katana'},
            'senses': [{'ordinal': 1, 'english': ['sword', 'single-edged sword']}]}
    result = select({'candidates': [word]})
    assert result['english'] == 'sword' and result['reading'] == 'katana'
    assert result['state'] == 'dictionary_proposal' and not result['verified']
    word['senses'].append({'ordinal': 2, 'english': ['knife']})
    assert select({'candidates': [word]})['english'] is None


def test_domain_evidence_can_choose_a_dictionary_supported_sense():
    word = {'source': 'jmdict', 'entry_id': '2', 'kana': 'は',
            'senses': [{'ordinal': 1, 'english': ['edge']},
                       {'ordinal': 2, 'english': ['leaf']}]}
    result = select({'candidates': [word], 'domain': {'assertions': [
        {'english': 'edge', 'source': 'supporting_reference', 'literal': '刃'}]}})
    assert result['english'] == 'edge' and result['domain_sense_agreement']
    assert result['state'] == 'dictionary_proposal' and not result['verified']
