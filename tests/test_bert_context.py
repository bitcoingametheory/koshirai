"""BERT integration: supported roles, whole names, abstention and literal preservation."""
import os
import pytest

from kanji_translator import parse
from kanji_translator.bert_context import LABELS, rerank
from kanji_translator.semantic_groups import role_records


def decision(category, probability=.99, margin=.98):
    return {'category':category,'model_probability':probability,'margin':margin,
            'probabilities':{c: probability if c==category else (1-probability)/(len(LABELS)-1) for c in LABELS}}


def test_model_cannot_invent_an_unsupported_role_or_specific_identity():
    option={'category':'swordsmith_artisan','score':8.,'reading':'Example',
            'support':[{'source':'primary_reference'}],'identity_accepted':False}
    ranked,state=rerank([option],decision('sword_school'))
    assert state['state']=='requires_review'
    assert state['reason']=='unsupported_context_role'
    assert ranked==[option] and not ranked[0]['identity_accepted']


def test_uncertain_context_does_not_promote_a_library_candidate():
    option={'category':'sword_school','score':6.,'support':[{'source':'primary_reference'}]}
    _,state=rerank([option],decision('sword_school',.6,.1))
    assert state['state']=='requires_review'


def test_ichimonji_and_traditions_have_explicit_source_roles():
    for literal,category in [('一文字','sword_school'),('備前','sword_tradition'),('當麻','sword_school'),('一文字助真','swordsmith_artisan')]:
        records=role_records(literal)
        assert any(r['role']==category and r['citations'][0]['selected_payload_sha256'] for r in records)
    suffix=role_records('備前傳')[0]
    assert suffix['printed_romaji'] is None and suffix['english'] is None
    assert suffix['derivation']=='cited_role_stem_with_explicit_printed_organizational_suffix'
    assert not role_records('雲')
    from kanji_translator.sword_library import lookup
    assert any(r['role']=='sword_school' for r in lookup('一文字')['semantic_role_assertions'])


@pytest.fixture
def bert_config():
    if not os.environ.get('KOSHIRAI_BERT_DIR'):
        pytest.skip('Set KOSHIRAI_BERT_DIR to run the real pinned BERT integration')
    pytest.importorskip('torch')
    pytest.importorskip('transformers')
    return {'profile':'bert','bert_device':os.environ.get('KOSHIRAI_BERT_DEVICE','cpu')}


@pytest.mark.parametrize('text,literal,category',[
    ('◇信房一文字','一文字','sword_school'),
    ('一文字派に属する刀工。','一文字派','sword_school'),
    ('備前伝の作風。','備前伝','sword_tradition'),
    ('五箇伝の一つである大和伝。','大和伝','sword_tradition'),
    ('一文字助真が鍛えた刀。','一文字助真','swordsmith_artisan'),
    ('刀工兼元が打った刀。','兼元','swordsmith_artisan'),
    ('兼元派に学んだ鍛冶。','兼元派','sword_school'),
    ('刃長二尺二寸七分','二尺二寸七分','measurement_dimension'),
])
def test_real_bert_pipeline_preserves_text_and_selects_supported_complete_roles(bert_config,text,literal,category):
    result=parse({'text':text,'semantic_config':bert_config,'lexical_config':{'enabled':False}})
    assert result['raw_ndl_transcript']==text
    assert any(m['literal']==literal and m['selection']['category']==category for m in result['semantic_mentions'])
    assert all(m['selection']['support'] and not m['identity_accepted'] for m in result['semantic_mentions'])
    assert all(m['disambiguation']['calibrated'] is False for m in result['semantic_mentions'])
    if literal=='一文字助真':
        assert not any(m['literal']=='一文字' for m in result['semantic_mentions'])


def test_same_bizen_literal_can_be_a_place_instead_of_a_tradition(bert_config):
    lexical={'spans':[{'start':0,'end':2,'literal':'備前','candidates':[{
        'source':'jmdict','entry_id':'fixture-bizen','romaji':{'びぜん':'bizen'},
        'senses':[{'ordinal':0,'english':['former province in western Japan'],'name_types':[]}]}]}]}
    from kanji_translator.semantic_groups import interpret
    result=interpret('備前国に住む。',lexical,config=bert_config)
    row=next(m for m in result['mentions'] if m['literal']=='備前')
    assert row['selection']['category']=='place_province'
    assert any(a['category']=='sword_tradition' for a in row['alternatives'])


def test_low_context_remains_a_proposal_with_all_alternatives(bert_config):
    result=parse({'text':'當麻','semantic_config':bert_config,'lexical_config':{'enabled':False}})
    rows=result['enrichment']['regions'][0]['semantic']['candidates']
    assert rows and all(r['review_state']=='model_proposal' for r in rows)
    assert all(not r['identity_accepted'] for r in rows)


def test_requested_bert_never_silently_falls_back_when_encoder_is_missing(bert_config,tmp_path):
    with pytest.raises(RuntimeError,match='BERT is not installed'):
        parse({'text':'一文字','semantic_config':{**bert_config,'bert_path':str(tmp_path/'missing')},
               'lexical_config':{'enabled':False}})
