"""Frozen same-OCR 10/50-page execution and exhaustive grouped-mention scoring.

References are separate source-only annotations; an absent/incomplete reference
is unscored, never an empty page. Re-run --score-only after reference freeze.
"""
import argparse
from collections import Counter,defaultdict
import hashlib
import json
from pathlib import Path
import random
import sys
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from kanji_translator.request_contracts import canonical,digest
from kanji_translator.semantic_groups import interpret,compatible


def general(text,lexical,context):
    rows=[]
    for span in lexical.get('spans',[]):
        if len(span['literal'])<2:continue
        # Fixed general interpretation means dictionary order, with no sword prior.
        from kanji_translator.semantic_groups import candidates
        options=[c for c in candidates(text,span['start'],span['end'],[span])
                 if c['source'] in ('jmdict','jmnedict','kanjidic2')]
        if not options:continue
        rows.append({'start':span['start'],'end':span['end'],'literal':span['literal'],
                     'selection':{**options[0],'score':1.},'alternatives':options[1:],
                     'identity_accepted':False,'links':context})
    return compatible(rows)


def page_predictions(result):
    methods={'general':[],'exact':[],'contextual':result['semantic_mentions']}
    blocked={rid for block in result.get('semantic_blocks',[]) for rid in block['block']['region_ids']}
    units=[(row['literal_text'],row['lexical'],row['context'],row['region_id'],row['identity'].get('geometry'),None)
           for row in result['enrichment']['regions'] if row['region_id'] not in blocked
           and not row['context'].get('semantic_exclusion')]
    for block in result.get('semantic_blocks',[]):
        context=block['semantic']['candidates'][0]['links'] if block['semantic']['candidates'] else {}
        units.append((block['literal_text'],block['lexical'],context,block['block']['region_ids'][0],None,block['literal_alignment']))
    for text,lexical,context,rid,box,alignment in units:
        for method,mentions in [('general',general(text,lexical,context)),('exact',interpret(text,lexical,context,{'profile':'exact'})['mentions'])]:
            for mention in mentions:
                boxes=[s['geometry'] for s in (alignment or []) if s.get('geometry') and s['block_start']<mention['end'] and s['block_end']>mention['start']]
                geometry=[min(b[0] for b in boxes),min(b[1] for b in boxes),max(b[2] for b in boxes),max(b[3] for b in boxes)] if boxes else box
                methods[method].append({**mention,'region_id':rid,'geometry':geometry,
                    'geometry_scope':'union of aligned whole native OCR lines' if alignment else 'whole native OCR line; no invented character boxes'})
    return methods


def overlap(a,b):
    if not a or not b:return 0.
    area=max(0,min(a[2],b[2])-max(a[0],b[0]))*max(0,min(a[3],b[3])-max(a[1],b[1]))
    smaller=min((a[2]-a[0])*(a[3]-a[1]),(b[2]-b[0])*(b[3]-b[1]))
    return area/max(1,smaller)


GEOMETRY_POLICIES = ('area_overlap_min_half', 'native_line_projection_v1')


def same_location(reference, prediction, policy):
    if policy not in GEOMETRY_POLICIES:
        raise ValueError('Unknown geometry policy')
    a, b = reference.get('box'), prediction.get('geometry')
    if not a:
        return (reference.get('region_id') == prediction.get('region_id') and
                reference.get('start') == prediction.get('start') and
                reference.get('end') == prediction.get('end'))
    if overlap(a, b) >= .5:
        return True
    # A narrow whole-line box and a wider short annotation can cover the same
    # printed term but fail area/min-area. Both axes must independently overlap.
    # Never apply this to multi-line unions or pretend to locate characters.
    if (policy != 'native_line_projection_v1' or not b or
        prediction.get('geometry_scope') != 'whole native OCR line; no invented character boxes'):
        return False
    return all(min(a[i+2], b[i+2])-max(a[i], b[i]) >=
               .85 * min(a[i+2]-a[i], b[i+2]-b[i]) > 0 for i in (0, 1))


def counts(reference,predictions,geometry_policy='area_overlap_min_half'):
    used=set();correct=[];false=[]
    for prediction in predictions:
        eligible=[(i,r) for i,r in enumerate(reference) if i not in used and r['literal']==prediction['literal'] and
                  same_location(r,prediction,geometry_policy)]
        if not eligible:false.append(prediction);continue
        i,ref=max(eligible,key=lambda pair:overlap(pair[1].get('box'),prediction.get('geometry')))
        used.add(i);correct.append((ref,prediction))
    missed=[r for i,r in enumerate(reference) if i not in used]
    def metric(field):
        comparable=[(r,p) for r,p in correct if r.get(field) is not None]
        n=sum(p['selection'].get(field)==r[field] or p['selection'].get(field) in r.get(field+'_alternatives',[]) for r,p in comparable)
        return {'correct':n,'scored':len(comparable),'unknown_reference':len(correct)-len(comparable)}
    tp=len(correct);fp=len(false);fn=len(missed)
    component_pairs=[(r,p) for r,p in correct if r.get('components') is not None]
    component_total=sum(len(r['components']) for r,p in component_pairs)
    component_correct=sum(sum(a.get('quantity')==b.get('quantity') and a.get('unit')==b.get('unit') for a,b in zip(r['components'],p['selection'].get('components',[]))) for r,p in component_pairs)
    return {'measurement_components':{'correct':component_correct,'reference_components':component_total,'scored_expressions':len(component_pairs)},'reference_mentions':len(reference),'predicted_mentions':len(predictions),'correct_complete_groups':tp,
            'false_positives':fp,'missed_mentions':fn,'precision':tp/(tp+fp) if tp+fp else None,
            'recall':tp/(tp+fn) if tp+fn else None,'f1':2*tp/(2*tp+fp+fn) if 2*tp+fp+fn else None,
            'category':metric('category'),'reading':metric('reading'),'english_sense':metric('english'),
            'false_specific_person_assignments':sum(bool(p.get('identity_accepted') or p['selection'].get('identity_accepted')) for p in false),
            'errors':{'false_positives':false,'misses':missed,'category':[{'reference':r,'prediction':p} for r,p in correct if r.get('category') and r['category']!=p['selection']['category']]}}


def scored_scope(page,reference):
    """Do not turn explicitly unreadable reference areas into false positives.

    Geometry is line-level. Keep a prediction that matches a readable reference
    even if its line also crosses an uncertainty box; otherwise record exclusion.
    """
    mentions=[r for r in reference['mentions'] if r.get('state','readable') not in ('unreadable','disputed')]
    uncertain=[r for r in reference['mentions'] if r.get('state') in ('unreadable','disputed')]
    methods={};excluded={}
    for method,values in page['methods'].items():
        kept=[];ignored=[]
        for prediction in values:
            if reference.get('scored_boxes') and not any(overlap(box,prediction.get('geometry'))>=.5 for box in reference['scored_boxes']):
                continue
            ambiguous=any(overlap(r.get('box'),prediction.get('geometry'))>=.5 for r in uncertain)
            readable=any(r['literal']==prediction['literal'] and overlap(r.get('box'),prediction.get('geometry'))>=.5 for r in mentions)
            (ignored if ambiguous and not readable else kept).append(prediction)
        methods[method]=kept;excluded[method]=ignored
    return mentions,methods,excluded


def score(predictions,references,geometry_policy='area_overlap_min_half'):
    if geometry_policy not in GEOMETRY_POLICIES:raise ValueError('Unknown geometry policy')
    by_id={r['page_id']:r for r in references.get('pages',[])};pages=[]
    for row in predictions:
        ref=by_id.get(row['page_id'])
        entry={'page_id':row['page_id'],'execution_state':row['state'],'accuracy_state':'unscored',
               'prediction_counts':{m:len(v) for m,v in row.get('methods',{}).items()}}
        if ref:
            entry.update(reference_scope=ref.get('scope','whole_frame'),scored_boxes=ref.get('scored_boxes'),
                         whole_frame_exhaustive=ref.get('whole_frame_exhaustive',ref.get('exhaustive',False)))
        if row['state']=='complete' and ref and ref.get('exhaustive') is True:
            mentions,methods,excluded=scored_scope(row,ref)
            categories={r['category'] for r in mentions}|{p['selection']['category'] for values in methods.values() for p in values}
            entry.update(accuracy_state='scored_provisional' if ref.get('label_origin','').startswith('AI') else 'scored',
                         label_origin=ref.get('label_origin'),excluded_uncertain_mentions=len(ref['mentions'])-len(mentions),
                         excluded_uncertain_predictions={m:len(v) for m,v in excluded.items()},
                         excluded_outside_scope_predictions={m:len(row['methods'][m])-len(v)-len(excluded[m]) for m,v in methods.items()},
                         uncertainty_exclusions=excluded,
                         methods={m:counts(mentions,v,geometry_policy) for m,v in methods.items()},
                         by_category={cat:{m:counts([r for r in mentions if r['category']==cat],[p for p in v if p['selection']['category']==cat],geometry_policy) for m,v in methods.items()} for cat in sorted(categories)})
        pages.append(entry)
    scored=[p for p in pages if 'methods' in p];summary={}
    for method in ('general','exact','contextual'):
        total={key:sum(p['methods'][method][key] for p in scored) for key in ('reference_mentions','predicted_mentions','correct_complete_groups','false_positives','missed_mentions')}
        tp=total['correct_complete_groups'];fp=total['false_positives'];fn=total['missed_mentions']
        total.update(precision=tp/(tp+fp) if tp+fp else None,recall=tp/(tp+fn) if tp+fn else None,f1=2*tp/(2*tp+fp+fn) if 2*tp+fp+fn else None,false_positives_per_page=fp/len(scored) if scored else None)
        summary[method]=total
    interval=None
    if scored:
        differences=[p['methods']['contextual']['correct_complete_groups']-p['methods']['exact']['correct_complete_groups'] for p in scored]
        rng=random.Random(20261106);means=sorted(sum(rng.choice(differences) for _ in differences)/len(differences) for _ in range(2000))
        interval={'measure':'paired difference in correct groups per page, contextual minus exact','mean':sum(differences)/len(differences),'percentile95':[means[49],means[1949]],'seed':20261106,'draws':2000,'label_uncertainty':'not captured by page bootstrap'}
    matched_coverage=[]
    for page in predictions:
        ref=by_id.get(page['page_id'])
        if page['state']!='complete' or not ref or not ref.get('exhaustive'):continue
        reference,methods,_=scored_scope(page,ref)
        k=min(len(v) for v in methods.values())
        matched_coverage.append({'page_id':page['page_id'],'predictions_per_method':k,'methods':{method:counts(reference,sorted(values,key=lambda r:-r['selection'].get('score',0))[:k],geometry_policy) for method,values in methods.items()}})
    unseen={'state':'not_applicable','reason':'No trained semantic model; library exposure is documented separately.'}
    if any(p.get('model',{}).get('context_encoder') for row in predictions for p in row.get('methods',{}).get('contextual',[])):
        unseen={'state':'not_audited','reason':'Neural-model pretraining exposure is unknown. These 50 pages are development/regression evidence; consult each model report for supervision.'}
    return {'geometry_policy':geometry_policy,'matched_coverage_pages':matched_coverage,'unseen_names':unseen,'schema':'semantic-page-evaluation-v1','pages':pages,'summary':summary,'scored_pages':len(scored),'unscored_pages':len(pages)-len(scored),'paired_interval':interval,
            'matched_coverage':'Per-page top K where K is the minimum selected count across methods; ranking uses already frozen scores. Zero K is explicitly visible and proves no semantic superiority.',
            'reference_sha256':digest(canonical(references)),'limitations':['Source-only AI is provisional; zero human expertise is inferred.','Grouping uses exact literal plus source geometry; line boxes do not validate character-level position.','Category-specific counts confound missed grouping and wrong category; conditional category accuracy is separate.','Reading order, headings, figure links and OCR CER require separate independent reference labels; unlabelled means unscored.']}


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--manifest',type=Path,required=True);p.add_argument('--output',type=Path,required=True);p.add_argument('--config',type=Path);p.add_argument('--references',type=Path);p.add_argument('--score-only',action='store_true')
    p.add_argument('--geometry-policy',choices=GEOMETRY_POLICIES,default=GEOMETRY_POLICIES[0])
    a=p.parse_args();a.output.mkdir(parents=True,exist_ok=True);manifest=json.loads(a.manifest.read_text());target=a.output/'predictions.jsonl'
    if not a.score_only:
        from kanji_translator import parse
        config=json.loads(a.config.read_text()) if a.config else {};completed={}
        if target.exists():completed={r['page_id']:r for r in map(json.loads,target.read_text().splitlines())}
        with target.open('a') as stream:
            for page in manifest['pages']:
                if page['page_id'] in completed:continue
                image=Path(page['image_path']);sha=digest(image.read_bytes())
                if sha!=page['source_sha256']:raise ValueError('Manifest source hash mismatch')
                row={'page_id':page['page_id'],'source_sha256':sha}
                try:
                    result=parse({**config,'kind':'image','path':str(image),'sha256':sha})
                    row.update(state='complete',methods=page_predictions(result),supporting={'regions':len(result['regions']),'unresolved_regions':result['unresolved_regions'],'native_OCR_sha256':digest(result['raw_ndl_transcript'].encode()),'runtime_metrics':result['metrics'],'document_groups':result['document_groups']})
                except (ValueError,RuntimeError,OSError,ImportError) as error:row.update(state='failed',error=str(error))
                stream.write(json.dumps(row,ensure_ascii=False)+'\n');stream.flush()
                print(json.dumps({'page_id':page['page_id'],'state':row['state']}),flush=True)
    rows=[json.loads(line) for line in target.read_text().splitlines()]
    refs=json.loads(a.references.read_text()) if a.references else {'pages':[]}
    report=score(rows,refs,a.geometry_policy);report['manifest_sha256']=digest(a.manifest.read_bytes())
    (a.output/'evaluation.json').write_bytes(canonical(report)+b'\n')
    print(json.dumps({'pages':len(rows),'scored_pages':report['scored_pages'],'unscored_pages':report['unscored_pages']}))
if __name__=='__main__':main()
