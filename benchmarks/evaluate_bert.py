"""Compare source priority and BERT on the same frozen, recovered source targets."""
import argparse
from collections import Counter
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from kanji_translator.bert_context import classify, rerank
from kanji_translator.dictionary_lookup import read
from kanji_translator.request_contracts import canonical, digest
from kanji_translator.semantic_groups import candidates, evidence_rank, MEASUREMENT


def evaluate(dataset, config):
    rows = [r for r in dataset['rows'] if r['kind']=='source']
    decisions = classify(rows, config)
    output = []
    for row, decision in zip(rows, decisions):
        text = row['left']+row['target']+row['right']
        a, b = len(row['left']), len(row['left'])+len(row['target'])
        lexical = read(row['target'], config.get('lexical_config', {}))
        spans = [{**s,'start':s['start']+a,'end':s['end']+a} for s in lexical.get('spans', [])]
        options = candidates(text, a, b, spans)
        ranked, _ = evidence_rank(text, a, b, options, 'unknown')
        original = ranked[0]['category'] if ranked and ranked[0]['score'] >= 1 else None
        revised, state = rerank(ranked, decision)
        chosen = revised[0]['category'] if state['state']=='context_selected' else None
        if MEASUREMENT.fullmatch(row['target']):
            chosen='measurement_dimension'
            state={**state,'reason':'explicit_printed_quantity_and_units'}
        output.append({'id':row['id'],'page_id':row['page_id'],'split':row['split'],
                       'target':row['target'],'reference':row['label'],
                       'baseline':original,'bert':chosen,'raw_bert':decision['category'],
                       'state':state['reason'],'supported_categories':sorted({c['category'] for c in options}),
                       'model_probability':decision['model_probability']})
    def metric(subset, field):
        selected = [r for r in subset if r[field] is not None]
        correct = sum(r[field]==r['reference'] for r in selected)
        return {'targets':len(subset),'selected':len(selected),'correct':correct,
                'wrong':len(selected)-correct,'abstained':len(subset)-len(selected),
                'precision':correct/len(selected) if selected else None,
                'coverage':len(selected)/len(subset) if subset else None,
                'correct_target_fraction':correct/len(subset) if subset else None}
    return {'schema':'bert-candidate-comparison-v1','dataset_sha256':digest(canonical(dataset)),
            'splits':{split:{method:metric([r for r in output if r['split']==split],method) for method in ('baseline','bert')}
                      for split in ('train','validation','test')},
            'by_category':{label:{method:metric([r for r in output if r['reference']==label],method) for method in ('baseline','bert')}
                           for label in sorted({r['reference'] for r in output})},
            'decisions':output,
            'limitations':['Conditional on supplied recovered target and source location; not end-to-end span detection.',
                           'Same-source candidate comparison includes training/development pages; split results remain separate.',
                           'Reference labels are provisional AI annotations. No expert truth is inferred.',
                           'Earlier test observations informed development; test split is now regression evidence.']}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--dataset',type=Path,required=True)
    parser.add_argument('--config',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args()
    result=evaluate(json.loads(args.dataset.read_text()),json.loads(args.config.read_text()))
    args.output.write_bytes(canonical(result)+b'\n')
    print(json.dumps(result['splits']))
