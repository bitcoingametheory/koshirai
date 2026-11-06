"""Japanese entry, polarity, relationship and provenance regression controls."""
import pytest
from kanji_translator import parse
from kanji_translator.entry_structure import extract,retained_witnesses
from kanji_translator.semantic_groups import interpret


def claims(text):
    return interpret(text,context={'role':'text_line'})['interpretation']['claims']


@pytest.mark.parametrize('text,kind,polarity',[
    ('板目肌に柾目肌が交じる。','mixed_with','positive'),
    ('板目肌に柾目肌が交じらない。','mixed_with','negative'),
    ('刃文は直刃。','described_as','positive'),
    ('刃文は直刃ではない。','described_as','negative'),
    ('刃文は直刃に似る。','resembles','positive'),
    ('刃文は直刃に似ない。','resembles','negative'),
    ('小沸が見られない。','observed','negative'),
    ('小沸が見られる。','observed','positive'),
    ('小沸がない。','observed','negative'),
    ('板目肌より柾目肌が多い。','more_frequent_than','positive'),
    ('雲次は雲生の子。','child_of','positive'),
    ('雲次は雲生の弟子ではない。','student_of','negative'),
])
def test_literal_relations_and_polarity(text,kind,polarity):
    rows=claims(text);row=next(c for c in rows if c['relation']==kind)
    assert row['polarity']==polarity and row['english']
    for evidence in row['arguments']+[row['cue']]:
        assert text[evidence['start']:evidence['end']]==evidence['literal']
    assert not row['identity_accepted'] and all(e['support'] for e in row['evidence'])


@pytest.mark.parametrize('text',[
    '小沸がないこともない。','小沸がなくはない。','小沸が見られないわけではない。',
    '小沸がついていない。','小沸が見られるとは限らない。','小沸が見られたら。',
    '「小沸がない」と書く。','板目肌。柾目肌が交じる。',
    '板目肌に\n柾目肌が交じる。','小沸が見られるものではない。',
    '板目肌に柾目肌が交じることはない。','小沸が見られるとは言えない。',
])
def test_unsupported_scope_abstains(text):
    assert not claims(text)


def test_reported_and_possible_claims_are_not_plain_assertions():
    a=claims('小沸が見られないとされる。')[0]
    assert a['polarity']=='negative' and a['modality']=='reported'
    assert a['modality_evidence']['literal']=='とされ'
    assert claims('小沸が見られるかもしれない。')[0]['modality']=='possible'


def test_index_tab_supports_three_character_head_without_name_invention():
    text='◇一竿子初代〔元祿-攝津〕新刀上作'
    r=extract(text,index_names=['一竿子'])['entries'][0]
    assert r['name']['literal']=='一竿子'
    assert r['unresolved_head_suffix']['literal']=='初代'
    assert r['fields']['era']['literal']=='元祿' and r['fields']['province']['literal']=='攝津'
    assert not r['identity_accepted']
    assert extract(text)['entries'][0]['name'] is None


def test_wrong_ocr_head_not_replaced_by_index_and_alternate_is_separate():
    p={'text_raw':'【か】兼永\n◇並永雲州〔天正-出雲〕',
       'text_alt_raw':'【か】兼永\n◇兼永雲州〔天正-出雲〕',
       'engine':'primary','alt_engine':'alternate'}
    w=retained_witnesses(p)['passes']
    assert w[0]['entries'][0]['entry']['name'] is None
    assert w[1]['entries'][0]['entry']['name']['literal']=='兼永'
    assert all(v['geometry'] is None and not v['automatic_promotion'] for v in w)


def test_entries_override_false_smiths_in_explicit_era_and_province_fields():
    r=interpret('◇宗吉〔慶長-越前〕新刀上作',context={'role':'text_line','entry_index_names':['宗吉']})
    selected={m['literal']:m['selection']['category'] for m in r['mentions']}
    assert selected['宗吉']=='swordsmith_artisan'
    assert selected['慶長']=='era_date' and selected['越前']=='place_province'


def test_parse_exposes_source_bound_interpretations_without_cross_line_join():
    r=parse({'kind':'regions','regions':[{'region_id':'a','text':'板目肌に'},
             {'region_id':'b','text':'柾目肌が交じる。'}],'lexical_config':{'enabled':False}})
    assert not any(u['claims'] for u in r['japanese_interpretations'])
    r=parse({'text':'板目肌に柾目肌が交じる。','lexical_config':{'enabled':False}})
    assert r['raw_ndl_transcript']=='板目肌に柾目肌が交じる。'
    assert r['japanese_interpretations'][0]['source_sha256']
    assert r['japanese_interpretations'][0]['claims'][0]['english']


def test_bare_person_school_conflict_is_visible_without_false_person_choice():
    result=interpret('當麻とされる。',context={'role':'text_line'})
    assert not result['mentions']
    row=next(r for r in result['candidates'] if r['literal']=='當麻')
    assert 'person_or_collective_role_unresolved' in row['uncertainty']
    assert any(c['category']=='sword_school' for c in row['alternatives'])


def test_generation_and_family_cues_bound_attested_names_only():
    result=interpret('初代忠吉門、雲生の子は雲次。',context={'role':'text_line'})
    assert {'忠吉','雲生','雲次'} <= {r['literal'] for r in result['mentions']}
    assert all(not r['identity_accepted'] for r in result['mentions'])


def test_duplicate_native_mentions_preserve_witness_and_separate_repetitions():
    from kanji_translator.document_layout import unique_mentions
    def mention(id,region,box,start=0):
        return {'mention_id':id,'region_id':region,'geometry':box,'literal':'雲次','start':start,'end':start+2,
                'selection':{'category':'swordsmith_artisan'}}
    a=mention('a','heading',[10,10,20,40]);b=mention('b','combined',[10,10,20,100])
    c=mention('c','adjacent',[22,10,32,40]);d=mention('d','heading',[10,10,20,40],4)
    result=unique_mentions([a,b,c])
    assert [r['mention_id'] for r in result]==['a','c']
    assert a['duplicate_witnesses'][0]['mention_id']=='b' and b['duplicate_of']=='a'
    a=mention('a','heading',[10,10,20,40]);b=mention('b','combined',[10,10,20,100])
    assert len(unique_mentions([a,b,d]))==3


def test_dimension_gloss_is_not_misclassified_as_biography():
    from kanji_translator.meaning_selection import english_quality
    assert english_quality('blade under thirty centimetres')['eligible']
    assert not english_quality('under Kunihiro')['eligible']
