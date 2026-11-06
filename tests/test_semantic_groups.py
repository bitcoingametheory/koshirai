"""Behavior of literal whole-name grouping, quantities and independent scoring."""
import gzip,json
from pathlib import Path
from kanji_translator import parse
from kanji_translator.semantic_groups import interpret,matched_spans


def test_whole_unji_name_and_no_single_cloud_expansion():
    result=parse({'text':'雲次。雲。','lexical_config':{'enabled':False}})
    names=[m for m in result['semantic_mentions'] if m['selection']['category']=='swordsmith_artisan']
    assert any(m['literal']=='雲次' and m['selection']['reading']=='Unji' for m in names)
    assert not any(m['literal']=='雲' for m in names)
    assert result['raw_ndl_transcript']=='雲次。雲。'
    assert all(m['selection']['support'] and not m['identity_accepted'] for m in names)


def test_quantity_units_count_as_one_group_with_components():
    result=parse({'text':'刃長二尺二寸七分','lexical_config':{'enabled':False}})
    measures=[m for m in result['semantic_mentions'] if m['selection']['category']=='measurement_dimension']
    assert len(measures)==1 and measures[0]['literal']=='二尺二寸七分'
    assert [r['unit'] for r in measures[0]['selection']['components']]==['尺','寸','分']
    assert measures[0]['selection']['dimension']=='刃長'


def test_literal_matching_never_crosses_unrelated_line_boundary():
    assert (0,2) in matched_spans('雲次')
    assert not matched_spans('雲\n次')
    result=parse({'kind':'regions','regions':[{'region_id':'a','text':'雲'},{'region_id':'b','text':'次'}],'lexical_config':{'enabled':False}})
    assert not any(m['literal']=='雲次' for m in result['semantic_mentions'])


def test_unannotated_pages_are_unscored_and_false_positives_are_visible():
    import importlib.util
    spec=importlib.util.spec_from_file_location('evaluator',Path('benchmarks/evaluate_semantics.py'))
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    prediction={'literal':'雲次','start':0,'end':2,'region_id':'r','geometry':[0,0,10,20],
                'selection':{'category':'swordsmith_artisan','reading':'Unji','identity_accepted':False}}
    rows=[{'page_id':'p','state':'complete','methods':{m:[prediction] for m in ('general','exact','contextual')}}]
    assert module.score(rows,{'pages':[]})['scored_pages']==0
    refs={'pages':[{'page_id':'p','exhaustive':True,'label_origin':'AI_source_only_provisional','mentions':[]}]}
    report=module.score(rows,refs)
    assert report['summary']['contextual']['false_positives']==1
    assert report['pages'][0]['methods']['contextual']['precision']==0


def test_source_attested_school_is_separate_from_a_smith():
    result=parse({'text':'長船派','lexical_config':{'enabled':False}})
    assert any(m['literal']=='長船派' and m['selection']['category']=='sword_school'
               and m['selection']['support'] for m in result['semantic_mentions'])


def test_attested_era_and_printed_year_form_one_date_without_invented_reading():
    lexical={'spans':[{'start':0,'end':2,'literal':'慶長','candidates':[{
        'source':'jmdict','entry_id':'fixture-era','romaji':{'けいちょう':'keichou'},
        'senses':[{'ordinal':1,'english':['Keichō era (1596.10.27-1615.7.13)'],'name_types':[]}]}]}]}
    result=interpret('慶長十八年',lexical)
    assert len(result['mentions'])==1
    mention=result['mentions'][0]
    assert mention['literal']=='慶長十八年' and mention['selection']['category']=='era_date'
    assert mention['selection']['reading'] is None
    assert mention['selection']['support'][0]['printed_date']=='十八年'


def test_attested_name_accepts_japanese_particle_boundary():
    result=interpret('初め雲次と云ふ',context={'role':'text_line'})
    assert any(r['literal']=='雲次' for r in result['mentions'])
    assert any(r['literal']=='雲次' for r in result['candidates'])
    result=interpret('「雲次」',context={'role':'text_line'})
    assert any(r['literal']=='雲次' for r in result['mentions'])


def test_cited_primary_reference_glossary_overrides_general_hat_meaning():
    result=interpret('帽子',context={'role':'heading'})
    row=next(r for r in result['mentions'] if r['literal']=='帽子')
    assert row['selection']['english']=='tip temper pattern'
    support=row['selection']['support'][0]
    assert support['citations'][0]['source']=='primary_reference'
    assert support['citations'][0]['source_sha256']
    assert support['citations'][0]['selected_payload_sha256']
    assert support['bridge'] and support['bridge'][0]['source'].startswith('supporting_reference')


def test_cited_technical_terms_in_japanese_prose_keep_full_compounds():
    text='地鉄小杢目肌に柾目肌が交じる。板目肌詰んで見える。'
    result=interpret(text,context={'role':'text_line'})
    selected={r['literal']:r for r in result['mentions']}
    assert {'地鉄','小杢目肌','柾目肌','板目肌'} <= selected.keys()
    assert '杢目肌' not in selected and '肌' not in selected
    for literal in ('小杢目肌','柾目肌','板目肌'):
        row=selected[literal]
        assert row['selection']['english'] and row['selection']['support'][0]['citations']
        assert row['boundary']['eligible'] and text[row['start']:row['end']]==literal
    assert result['changes_characters'] is False


def test_unmapped_size_compound_and_bare_kanji_extension_stay_candidates():
    for text in ('小板目肌に見える。','大板目肌に見える。','板目肌性','新刀期'):
        result=interpret(text,context={'role':'body'})
        assert not any(r['literal'] in ('板目肌','新刀') for r in result['mentions'])
        assert any(r['literal'] in ('板目肌','新刀') for r in result['candidates'])
    result=interpret('小板目肌',context={'role':'heading'})
    assert not any(r['literal']=='板目肌' for r in result['mentions'])


def test_bilingual_citations_keep_distinct_edition_locations_and_review_state():
    row=next(r for r in interpret('縮緬肌')['mentions'] if r['literal']=='縮緬肌')
    evidence=row['selection']['support'][0]
    assert evidence['review_state']=='AI_source_image_reviewed_provisional_not_expert'
    jp,en=evidence['citations']
    assert jp['pdf_page']==322 and jp['printed_page']==320
    assert en['printed_page']==84 and en['label_printed_page']==85
    assert row['identity_accepted'] is False
