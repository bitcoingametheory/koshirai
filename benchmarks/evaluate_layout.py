"""Score frozen source-image panel/link targets without supplying labels to inference."""
import argparse
import hashlib
import json
from pathlib import Path
import sys
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from kanji_translator.document_layout import infer_figure_links,mark_duplicate_lines


def intersection(a,b):
    return max(0,min(a[2],b[2])-max(a[0],b[0]))*max(0,min(a[3],b[3])-max(a[1],b[1]))


def area(a):return max(0,a[2]-a[0])*max(0,a[3]-a[1])


def iou(a,b):return intersection(a,b)/max(1,area(a)+area(b)-intersection(a,b))


def native(box,dimensions):
    return [v*dimensions[i%2]/1000 for i,v in enumerate(box)] if box else None


def evaluate(predictions,references):
    refs={p['page_id']:p for p in references['pages']}
    if len({p['page_id'] for p in predictions})!=len(predictions):raise ValueError('Duplicate prediction page')
    rows=[]
    for prediction in predictions:
        page=refs[prediction['page_id']];ref=page['layout_reference']
        if prediction['source_sha256']!=page['source_sha256']:raise ValueError('Layout source hash mismatch')
        graph=prediction['supporting']['document_groups']
        regions=[n['source_fields'] for n in graph['nodes'] if n.get('source_fields',{}).get('region_id')]
        blocks=[n['source_fields'] for n in graph['nodes'] if n.get('status')=='native_detector_proposal']
        # No reference text, geometry or category reaches the inference function.
        dimensions=ref['source_dimensions']
        mark_duplicate_lines(regions)
        proposed=infer_figure_links(regions,{'blocks':blocks},dimensions)
        figures={f['id']:f for f in proposed['figures']};text={r['region_id']:r for r in regions}
        target=native(ref['figure'],dimensions)
        detection=max((iou(target,f['geometry']) for f in blocks if f['type']=='figure'),default=0.) if target else None
        relation=ref['relation'];expected=native(ref['text'],dimensions)
        scoped=[]
        if target and expected:
            for link in proposed['links']:
                if link['state']!='layout_inferred' or link['relation']!=relation:continue
                figure=figures[link['figure_id']]['geometry']
                if iou(target,figure)<.45:continue
                box=text[link['text_region_id']]['geometry']
                matches=intersection(box,expected)/max(1,min(area(box),area(expected)))>=.5
                scoped.append({**link,'text_geometry':box,'figure_geometry':figure,
                               'literal':text[link['text_region_id']]['text'],'correct':matches})
        correct=min(1,sum(p['correct'] for p in scoped));false=sum(not p['correct'] for p in scoped)
        rows.append({'page_id':page['page_id'],'source_sha256':page['source_sha256'],
                     'reference':ref,'target_figure_iou':detection,'figure_detected':detection>=.5 if detection is not None else None,
                     'link_scored':bool(expected),'correct_links':correct,'false_links':false,
                     'missed_links':int(bool(expected) and not correct),'scoped_predictions':scoped,
                     'redundant_correct_panel_links':max(0,sum(p['correct'] for p in scoped)-1),
                     'all_proposals':proposed,
                     'unscored_other_relation_proposals':sum(l['relation']!=relation for l in proposed['links']),
                     'image_free_right_page':relation=='no_figure',
                     'right_page_figure_proposals':sum(f['geometry'][0]>dimensions[0]/2 for f in proposed['figures'])})
    tp=sum(r['correct_links'] for r in rows);fp=sum(r['false_links'] for r in rows);fn=sum(r['missed_links'] for r in rows)
    return {'schema':'source-panel-link-evaluation-v1','pages':rows,
            'summary':{'frames':len(rows),'figure_targets':sum(r['reference']['figure'] is not None for r in rows),
                       'detected_figure_targets':sum(r['figure_detected'] is True for r in rows),
                       'resolvable_link_targets':sum(r['link_scored'] for r in rows),
                       'correct_links':tp,'false_links':fp,'missed_links':fn,
                       'link_precision':tp/(tp+fp) if tp+fp else None,'link_recall':tp/(tp+fn) if tp+fn else None,
                       'image_free_right_pages':sum(r['image_free_right_page'] for r in rows),
                       'correct_image_free_right_pages':sum(r['image_free_right_page'] and not r['right_page_figure_proposals'] for r in rows)},
            'reference_sha256':hashlib.sha256(json.dumps(references,sort_keys=True,ensure_ascii=False).encode()).hexdigest(),
            'limitations':['One source-selected panel per frame; no full-frame segmentation precision is inferred.',
                          'Forty resolvable entry/caption targets; unresolved continuations are unscored, not negative truth.',
                          'AI source-image annotations are provisional, not expert gold.',
                          'Development/regression evidence; exposed frames do not become a new blind test.']}


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--predictions',type=Path,required=True);p.add_argument('--references',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args()
    rows=[json.loads(line) for line in a.predictions.read_text().splitlines()]
    report=evaluate(rows,json.loads(a.references.read_text()))
    a.output.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n');print(json.dumps(report['summary']))
if __name__=='__main__':main()
