"""Prepare, run and compare the same bounded Japanese corpus on Astra and Sol."""
import argparse
import json
import math
import os
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from kanji_translator.frontier_semantics import MODELS,prepare,request_body,run
from kanji_translator.request_contracts import canonical,digest

# Price observation, 2026-11-06. Explicit conservative reservation, not a bill.
# https://developers.openai.com/api/docs/models/compare?model=gpt-6-astra&model=gpt-6.1-sol
RATES={'gpt-6-astra':(10.,50.),'gpt-6.1-sol':(2.,10.)}


def reservation(item,model,tokens):
    body=request_body(item,model,tokens)
    # UTF-8 bytes plus framing allowance overestimates bounded text token input.
    return ((len(canonical(body))+4096)*RATES[model][0]+tokens*RATES[model][1])/1_000_000


def metrics(expected,actual):
    from collections import Counter
    a,b=Counter(expected),Counter(actual);correct=sum((a&b).values())
    fp=sum((b-a).values());fn=sum((a-b).values())
    return {'correct':correct,'rejected':fp,'missed':fn,
            'precision':correct/(correct+fp) if correct+fp else None,
            'recall':correct/(correct+fn) if correct+fn else None}


def group_key(r):return r['start'],r['end'],r['literal'],r['category']
def claim_key(r,args):
    return r['relation'],tuple((a['start'],a['end'],a['literal']) for a in args),r['polarity'],r['modality']


def score(cases,receipts,prepared,tokens):
    results={}
    for model in MODELS:
        groups_expected=[];groups_actual=[];claims_expected=[];claims_actual=[];english=[];failures=[]
        for case in cases:
            ident=case['id'];item=prepared[ident];file=receipts/model/(digest(ident.encode())+'.json')
            try:prediction=run(item,model,file,replay=True,max_output_tokens=tokens)
            except (ValueError,RuntimeError,KeyError) as error:
                failures.append({'id':ident,'reason':type(error).__name__});prediction={'selected':[],'claims':[]}
            groups_expected.extend((ident,*group_key(r)) for r in case['reference_mentions'])
            groups_actual.extend((ident,*group_key(r)) for r in prediction['selected'])
            claims_expected.extend((ident,*claim_key(r,r['arguments'])) for r in case['reference_claims'])
            choices={r['candidate_id']:r for r in prediction['selected']}
            claims_actual.extend((ident,*claim_key(r,[choices[k] for k in r['argument_ids']])) for r in prediction['claims'])
            english.extend({'id':ident,'input_sha256':item['input_sha256'],'claim':r,'state':'requires_independent_review'} for r in prediction['claims'])
        results[model]={'grouping':metrics(groups_expected,groups_actual),'relations':metrics(claims_expected,claims_actual),
                        'failed_cases':failures,'english_accuracy':None,'english_review_queue':english}
    return {'schema':'paired-native-frontier-evaluation-v1','reference_sha256':digest(canonical(cases)),
            'input_sha256':{k:v['input_sha256'] for k,v in prepared.items()},'models':results,
            'limitations':['Same frozen text and source candidates for both models.',
                           'Closed candidate scope cannot recover absent spellings.',
                           'Failed or unavailable calls remain misses, never successful samples.',
                           'Structural validation is not factual or English accuracy.']}


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action',choices=('prepare','run','score'))
    parser.add_argument('--cases',type=Path,required=True)
    parser.add_argument('--prepared',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--max-output-tokens',type=int,default=4096)
    parser.add_argument('--max-calls',type=int,default=24)
    parser.add_argument('--max-cost-usd',type=float,default=5.)
    parser.add_argument('--key-env',default='OPENAI_API_KEY')
    args=parser.parse_args();cases=json.loads(args.cases.read_text())
    if not cases or len({c['id'] for c in cases})!=len(cases):raise ValueError('Cases need unique nonempty IDs')
    if args.action=='prepare':
        from kanji_translator.document_parser import parse
        items={}
        for case in cases:
            result=parse({'text':case['text'],'context':{'role':'text_line'}})
            # Explicit experimental context: plain native text uses conservative
            # body boundaries, independent of inferred image layout roles.
            from kanji_translator.semantic_groups import interpret
            semantic=interpret(case['text'],result['enrichment']['regions'][0]['lexical'],{'role':'text_line'})
            items[case['id']]=prepare(case['text'],semantic,case['source'])
        envelope={'cases_sha256':digest(canonical(cases)),'items':items}
        args.prepared.parent.mkdir(parents=True,exist_ok=True)
        if args.prepared.exists():raise ValueError('Prepared corpus exists')
        args.prepared.write_text(json.dumps(envelope,ensure_ascii=False,indent=2)+'\n')
        total=sum(reservation(item,m,args.max_output_tokens) for item in items.values() for m in MODELS)
        args.output.write_text(json.dumps({'cases':len(items),'calls':len(items)*2,'maximum_reserved_usd':total,
            'output_tokens_per_call':args.max_output_tokens,'models':list(MODELS),'live_calls':0},indent=2)+'\n')
        print(json.dumps({'cases':len(items),'calls':len(items)*2,'maximum_reserved_usd':total}));return
    envelope=json.loads(args.prepared.read_text());items=envelope['items']
    if envelope['cases_sha256']!=digest(canonical(cases)) or set(items)!={c['id'] for c in cases}:
        raise ValueError('Reference corpus changed after preparation')
    if args.action=='run':
        if not math.isfinite(args.max_cost_usd) or args.max_cost_usd<=0 or args.max_calls<=0:
            raise ValueError('Positive finite cost and call bounds required')
        planned=[(ident,item,m) for ident,item in items.items() for m in MODELS]
        total=sum(reservation(item,m,args.max_output_tokens) for _,item,m in planned)
        if len(planned)>args.max_calls or total>args.max_cost_usd:
            raise ValueError('Prepared comparison exceeds the call or reserved cost limit')
        if not os.getenv(args.key_env):raise RuntimeError('API credential is not configured in '+args.key_env)
        for ident,item,model in planned:
            path=args.output/model/(digest(ident.encode())+'.json')
            if path.exists():
                print(json.dumps({'id':ident,'model':model,'state':'existing_receipt_not_retried'}),flush=True);continue
            try:
                run(item,model,path,key_env=args.key_env,max_output_tokens=args.max_output_tokens)
                state='validated_proposal'
            except RuntimeError:state='failed'
            print(json.dumps({'id':ident,'model':model,'state':state}),flush=True)
        return
    report=score(cases,args.output,items,args.max_output_tokens)
    (args.output/'comparison.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps({m:{k:v for k,v in r.items() if k!='english_review_queue'} for m,r in report['models'].items()}))


if __name__=='__main__':main()
