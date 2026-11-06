"""Reference coverage must not hide false positives or invent readable truth."""
from benchmarks.evaluate_semantics import general, score
from benchmarks.compare_predictions import compare
import copy
import pytest
from benchmarks.evaluate_semantics import counts, same_location


def test_whole_line_cross_aspect_geometry_preserves_legacy_counts():
    ref={'literal':'古刀','box':[2966,2013,3036,2101]}
    pred={'literal':'古刀','geometry':[2987,2022,3023,2199],
          'geometry_scope':'whole native OCR line; no invented character boxes',
          'selection':{'category':'technical_sword_term'}}
    assert counts([ref],[pred])['false_positives']==1
    assert counts([ref],[pred],'native_line_projection_v1')['correct_complete_groups']==1
    # The same printed occurrence cannot satisfy duplicate detections.
    assert counts([ref],[pred,pred],'native_line_projection_v1')['false_positives']==1
    for bad in ({'geometry':[3037,2022,3073,2199]},
                {'geometry':[2987,2101,3023,2278]},
                {'geometry_scope':'union of aligned whole native OCR lines'},
                {'geometry_scope':None}):
        assert not same_location(ref,{**pred,**bad},'native_line_projection_v1')


def test_geometry_policy_cannot_change_literal_category_or_scored_scope():
    pred=page('新刀')
    pred['methods']['contextual'][0]['geometry_scope']='whole native OCR line; no invented character boxes'
    refs=reference([{'literal':'古刀','box':[0,0,20,20],'category':'technical_sword_term'}])
    report=score([pred],refs,'native_line_projection_v1')
    assert report['summary']['contextual']['correct_complete_groups']==0
    pred['methods']['contextual'][0]['literal']='古刀'
    report=score([pred],refs,'native_line_projection_v1')
    assert report['pages'][0]['by_category']['swordsmith_artisan']['contextual']['false_positives']==1
    refs['pages'][0]['scored_boxes']=[[100,0,120,100]]
    assert score([pred],refs,'native_line_projection_v1')['summary']['contextual']['predicted_mentions']==0


def test_general_baseline_uses_dictionary_sources_only(monkeypatch):
    from kanji_translator import semantic_groups
    def candidates(*args):
        return [{'authority':'general_dictionary','source':source,'category':'ordinary_language'}
                for source in ('primary_reference-register','nwatch','concept_inventory','jmdict','jmnedict')]
    monkeypatch.setattr(semantic_groups,'candidates',candidates)
    rows=general('雲次',{'spans':[{'literal':'雲次','start':0,'end':2}]},{})
    assert rows[0]['selection']['source']=='jmdict'
    assert [r['source'] for r in rows[0]['alternatives']]==['jmnedict']


def page(literal='雲次'):
    mention={'literal':literal,'geometry':[0,0,20,100],
             'selection':{'category':'swordsmith_artisan','score':1}}
    return {'page_id':'source-page','state':'complete',
            'methods':{method:[mention] for method in ('general','exact','contextual')}}


def reference(mentions):
    return {'pages':[{'page_id':'source-page','exhaustive':True,
                      'label_origin':'AI_source_only_provisional','mentions':mentions}]}


def test_prediction_only_category_keeps_its_false_positive():
    result=score([page()],reference([]))
    category=result['pages'][0]['by_category']['swordsmith_artisan']['contextual']
    assert category['reference_mentions']==0
    assert category['false_positives']==1
    assert result['summary']['contextual']['false_positives']==1


def test_unreadable_reference_area_is_not_negative_truth():
    result=score([page()],reference([{'literal':'','box':[0,0,20,100],
                                     'category':'unresolved','state':'unreadable'}]))
    assert result['summary']['contextual']['false_positives']==0
    assert result['summary']['contextual']['precision'] is None
    assert result['pages'][0]['excluded_uncertain_predictions']['contextual']==1
    assert result['pages'][0]['prediction_counts']['contextual']==1


def test_readable_mention_survives_uncertainty_on_same_line():
    result=score([page()],reference([
        {'literal':'','box':[0,0,20,100],'category':'unresolved','state':'unreadable'},
        {'literal':'雲次','box':[0,0,20,20],'category':'swordsmith_artisan'}]))
    assert result['summary']['contextual']['correct_complete_groups']==1
    assert result['pages'][0]['excluded_uncertain_predictions']['contextual']==0


def test_incomplete_reference_does_not_claim_an_empty_page():
    refs=reference([]);refs['pages'][0]['exhaustive']=False
    result=score([page()],refs)
    assert result['scored_pages']==0
    assert result['unscored_pages']==1
    assert result['summary']['contextual']['precision'] is None


def test_declared_region_excludes_predictions_outside_its_denominator():
    refs=reference([]);refs['pages'][0].update(scope='declared_region',whole_frame_exhaustive=False,scored_boxes=[[100,0,120,100]])
    result=score([page()],refs)
    assert result['summary']['contextual']['false_positives']==0
    assert result['pages'][0]['excluded_outside_scope_predictions']['contextual']==1
    assert result['pages'][0]['whole_frame_exhaustive'] is False


def test_paired_comparison_requires_identical_ocr_and_unique_pages():
    before=page()
    before.update(source_sha256='a'*64,supporting={'native_OCR_sha256':'b'*64})
    refs=reference([{'literal':'雲次','box':[0,0,20,100],'category':'swordsmith_artisan'}])
    report=compare([before],[copy.deepcopy(before)],refs)
    assert report['baseline']['contextual']['correct_complete_groups']==1
    after=copy.deepcopy(before)
    after['supporting']['native_OCR_sha256']='c'*64
    with pytest.raises(ValueError,match='native OCR differ'):
        compare([before],[after],refs)
    with pytest.raises(ValueError,match='unique identical'):
        compare([before,before],[before,before],refs)


def test_paired_comparison_counts_prediction_only_traditions():
    before=page('備前伝')
    before.update(source_sha256='a'*64,supporting={'native_OCR_sha256':'b'*64})
    for method in before['methods'].values():
        method[0]['selection']['category']='sword_tradition'
    report=compare([before],[copy.deepcopy(before)],reference([]))
    assert report['candidate']['contextual']['false_positives']==1
