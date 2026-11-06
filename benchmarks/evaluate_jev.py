"""Compare live or replayed Jev with source priority on frozen recovered targets."""
import argparse
from collections import Counter
import gzip
import json
from pathlib import Path
import sys
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from kanji_translator.dictionary_lookup import read
from kanji_translator.jev_context import alternatives,describe,decide,rerank
from kanji_translator.request_contracts import canonical,digest
from kanji_translator.semantic_groups import candidates,evidence_rank,MEASUREMENT


def evaluate(dataset,config):
    rows=[r for r in dataset['rows'] if r['kind']=='source' and r['split']=='test']
    prepared=[];items=[];active=[]
    for row in rows:
        text=row['left']+row['target']+row['right'];a=len(row['left']);b=a+len(row['target'])
        lex=read(row['target'],config.get('lexical_config',{}))
        spans=[{**s,'start':a+s['start'],'end':a+s['end']} for s in lex.get('spans',[])]
        ranked,_=evidence_rank(text,a,b,candidates(text,a,b,spans),'unknown')
        opts=alternatives(ranked)
        out={'id':row['id'],'page_id':row['page_id'],'target':row['target'],'reference':row['label'],
             'baseline':ranked[0]['category'] if ranked and ranked[0]['score']>=1 else None,'jev':None,
             'state':'unsupported_or_too_many_candidates'}
        prepared.append(out)
        if MEASUREMENT.fullmatch(row['target']):
            out.update(jev='measurement_dimension',state='explicit_printed_quantity_and_units');continue
        if not opts:continue
        active.append((out,ranked,opts));items.append({'left':row['left'],'target':row['target'],'right':row['right'],
            'options':{'candidate_'+str(i):describe(c) for i,c in enumerate(opts)}})
    for (out,ranked,opts),decision in zip(active,decide(items,config)):
        selected,state=rerank(ranked,opts,decision)
        out.update(jev=selected[0]['category'] if state['state']=='context_selected' else None,
                   state=state['reason'],decision=state)
    def counts(method,subset):
        selected=[r for r in subset if r[method] is not None];correct=sum(r[method]==r['reference'] for r in selected)
        return {'targets':len(subset),'selected':len(selected),'correct':correct,'wrong':len(selected)-correct,
                'abstained':len(subset)-len(selected),'precision':correct/len(selected) if selected else None,
                'coverage':len(selected)/len(subset) if subset else None}
    return {'schema':'jev-recovered-target-v1','dataset_sha256':digest(canonical(dataset)),
            'summary':{m:counts(m,prepared) for m in ('baseline','jev')},
            'by_category':{cat:{m:counts(m,[r for r in prepared if r['reference']==cat]) for m in ('baseline','jev')}
                           for cat in sorted({r['reference'] for r in prepared})},'decisions':prepared,
            'limitations':['Conditional on supplied recovered target, not end-to-end OCR or boundary accuracy.',
                           'Frozen source split is development/regression evidence with provisional AI labels.',
                           'No expert truth or English translation accuracy is established.']}


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--dataset',type=Path,required=True)
    p.add_argument('--config',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args()
    raw=a.dataset.read_bytes();d=json.loads(gzip.decompress(raw) if a.dataset.suffix=='.gz' else raw)
    result=evaluate(d,json.loads(a.config.read_text()));a.output.write_bytes(canonical(result)+b'\n');print(json.dumps(result['summary']))
