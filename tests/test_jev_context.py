"""Closed-set Jev selection, uncertainty, secret isolation and offline replay."""
import json
import pytest
from kanji_translator import parse
from kanji_translator import jev_context as jev


def test_invalid_distribution_or_invented_identifier_is_rejected():
    fit={'type':'noul','noul':.9}
    for answer in [
        {'type':'choice','choice':'invented','probabilities':{'candidate_0':1.,'unknown':0.}},
        {'type':'choice','choice':'candidate_0','probabilities':{'candidate_0':float('nan'),'unknown':0.}},
        {'type':'choice','choice':'candidate_0','probabilities':{'candidate_0':.9,'unknown':.9}},
        {'type':'choice','choice':'unknown','probabilities':{'candidate_0':.9,'unknown':.1}},
    ]:
        with pytest.raises(RuntimeError):jev.validate(answer,fit,['candidate_0','unknown'])


def test_role_choice_does_not_claim_a_pronunciation_is_resolved():
    options=[{'category':'sword_school','reading':'first','english':None,'score':6.,'support':[{'source':'fixture'}]},
             {'category':'sword_school','reading':'second','english':None,'score':6.,'support':[{'source':'fixture'}]}]
    d={'choice':'unknown','model_probability':.6,'margin':.1,'suitable':.9,
       'role_decision':{'choice':'sword_school','model_probability':.95,'margin':.9}}
    result,state=jev.rerank(options,options,d)
    assert result[0]['reading']==options[0]['reading'] and state['state']=='context_selected'
    assert result[1]==options[1]
    assert not state['sense_selected']
    d['suitable']=.3
    assert jev.rerank(options,options,d)[1]['state']=='requires_review'


def test_cache_replays_without_key_and_never_contains_credentials(monkeypatch,tmp_path):
    secret='unit-test-private-token'
    monkeypatch.setenv('TYPESAFE_API_KEY',secret)
    identity={'model':'jev-latest','release_date':'test-release'}
    monkeypatch.setattr(jev,'model_identity',lambda *args:identity)
    calls=[]
    def transport(route,key,payload=None):
        assert route=='systemone' and key==secret
        calls.append(payload);answers={}
        for name,q in payload['questions'].items():
            if q['type']=='noul':answers[name]={'type':'noul','noul':.95}
            else:
                choice=next(k for k in q['criteria'] if k!='unknown')
                answers[name]={'type':'choice','choice':choice,'probabilities':{k:1. if k==choice else 0. for k in q['criteria']}}
        return {'model':'jev-latest','answers':answers,'usage':{'input_tokens':100,'output_tokens':20}}
    monkeypatch.setattr(jev,'request',transport)
    items=[{'left':'','target':'一文字','right':'派','options':{'candidate_0':{'category':'sword_school'}}}]
    config={'jev_cache_dir':str(tmp_path),'jev_revision':'test-release'}
    first=jev.decide(items,config)
    monkeypatch.delenv('TYPESAFE_API_KEY')
    replay=jev.decide(items,{**config,'jev_replay_only':True})
    assert len(calls)==1 and replay[0]['cache_hit']
    assert first[0]['choice']==replay[0]['choice']
    assert all(secret not in p.read_text() for p in tmp_path.iterdir())
    assert not any('api_key' in str(payload).lower() for payload in calls)
    items[0]['right']='different context'
    with pytest.raises(RuntimeError,match='missing a required cached decision'):
        jev.decide(items,{**config,'jev_replay_only':True})


def test_requesting_jev_without_a_key_fails_without_fallback(monkeypatch,tmp_path):
    monkeypatch.delenv('TYPESAFE_API_KEY',raising=False);jev.model_identity.cache_clear()
    with pytest.raises(RuntimeError,match='requires an API key'):
        parse({'text':'一文字','lexical_config':{'enabled':False},
               'semantic_config':{'profile':'jev','jev_cache_dir':str(tmp_path)}})


def test_default_pipeline_does_not_call_jev(monkeypatch):
    def forbidden(*args,**kwargs):raise AssertionError('Unexpected external inference')
    monkeypatch.setattr(jev,'request',forbidden)
    assert parse({'text':'雲次','lexical_config':{'enabled':False}})['raw_ndl_transcript']=='雲次'


def test_raw_ocr_and_proposals_survive_a_supported_jev_choice(monkeypatch,tmp_path):
    def decisions(items,config):
        result=[]
        for item in items:
            key=next((k for k,v in item['options'].items() if v['category']=='sword_school'),None)
            role='sword_school' if key else 'unknown'
            result.append({'choice':key or 'unknown','model_probability':.99,'margin':.98,'suitable':.99,
                           'role_decision':{'choice':role,'model_probability':.99,'margin':.98},
                           'model':'fixture','release_date':'fixture','calibrated':False})
        return result
    monkeypatch.setattr(jev,'decide',decisions)
    result=parse({'text':'一文字','lexical_config':{'enabled':False},'semantic_config':{'profile':'jev','jev_cache_dir':str(tmp_path)}})
    assert result['raw_ndl_transcript']=='一文字'
    row=next(m for m in result['semantic_mentions'] if m['literal']=='一文字')
    assert row['selection']['category']=='sword_school' and row['selection']['support']
    assert not row['identity_accepted'] and row['alternatives']
