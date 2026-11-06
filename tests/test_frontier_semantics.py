"""Closed model choices, Japanese offsets, exact replay and no implicit calls."""
import copy,json
from unittest.mock import patch
import pytest
from kanji_translator.frontier_semantics import prepare,validate,request_body,response_answer,run
from kanji_translator.semantic_groups import interpret
from kanji_translator.request_contracts import canonical,digest


def specimen():
    text='板目肌に柾目肌が交じる。'
    item=prepare(text,interpret(text,context={'role':'text_line'}),{'source_sha256':'a'*64})
    ids=[next(k for k,v in item['candidates'].items() if v['literal']==term and v['english']) for term in ('板目肌','柾目肌')]
    answer={'selected_ids':ids,'claims':[{'relation':'mixed_with','argument_ids':ids,
        'cue':{'start':7,'end':11,'literal':'が交じる'},'polarity':'positive','modality':'asserted',
        'english_proposal':'Wood grain is mixed with straight grain.'}],'unresolved':[]}
    return item,answer


def test_native_packet_does_not_send_selector_predictions_or_references():
    item,answer=specimen();result=validate(item,answer)
    assert result['state']=='model_proposal' and not result['identity_accepted']
    assert 'score' not in canonical(item).decode() and 'reference_claims' not in item
    body=request_body(item,'gpt-6-astra')
    assert body['store'] is False and body['text']['format']['strict'] is True
    assert body['reasoning']['effort']=='medium' and body['max_output_tokens']==4096


@pytest.mark.parametrize('fault',['unknown_id','changed_text','wrong_cue','overlap','identity','cross_sentence','wrong_arguments'])
def test_invalid_model_evidence_rejected(fault):
    item,answer=specimen()
    if fault=='unknown_id':answer['selected_ids'].append('invented')
    elif fault=='changed_text':item['text']='原文を改変'
    elif fault=='wrong_cue':answer['claims'][0]['cue']['literal']='が混じる'
    elif fault=='overlap':
        other=next(k for k,v in item['candidates'].items() if v['literal']=='板目肌' and k not in answer['selected_ids'])
        answer['selected_ids'].append(other)
    elif fault=='identity':answer['claims'][0]['identity_accepted']=True
    elif fault=='cross_sentence':answer['claims'][0]['cue']={'start':7,'end':12,'literal':'が交じる。'}
    elif fault=='wrong_arguments':answer['claims'][0]['relation']='child_of'
    with pytest.raises(ValueError):validate(item,answer)


def test_exact_offline_replay_and_corruption_detection(tmp_path):
    item,answer=specimen();body=request_body(item,'gpt-6.1-sol')
    response={'status':'completed','model':'gpt-6.1-sol','output':[{'type':'message','content':[{'type':'output_text','text':json.dumps(answer)}]}]}
    path=tmp_path/'receipt.json';receipt={'request_sha256':digest(canonical(body)),'response':response,'response_sha256':digest(canonical(response))}
    path.write_text(json.dumps(receipt))
    with patch('urllib.request.build_opener',side_effect=AssertionError('network forbidden')):
        assert run(item,'gpt-6.1-sol',path,replay=True)['claims']
        with pytest.raises(ValueError):run(item,'gpt-6-astra',path,replay=True)
        receipt['response']['output']=[];path.write_text(json.dumps(receipt))
        with pytest.raises(ValueError):run(item,'gpt-6.1-sol',path,replay=True)


def test_incomplete_provider_reply_is_not_retried_or_scored():
    with pytest.raises(ValueError):response_answer({'status':'incomplete','output':[]})


def test_absent_credential_makes_no_request(tmp_path,monkeypatch):
    monkeypatch.delenv('KOSHIRAI_TEST_API_KEY',raising=False)
    item,_=specimen()
    with patch('urllib.request.build_opener',side_effect=AssertionError('network forbidden')):
        with pytest.raises(RuntimeError):run(item,'gpt-6-astra',tmp_path/'missing.json',key_env='KOSHIRAI_TEST_API_KEY')
    assert not (tmp_path/'missing.json').exists()
