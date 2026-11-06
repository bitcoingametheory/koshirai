"""Compare complete sword groups only after verifying identical pages and OCR."""
import argparse
import gzip
import hashlib
import json
from pathlib import Path
if __package__:
    from .evaluate_semantics import score, GEOMETRY_POLICIES
else:
    from evaluate_semantics import score, GEOMETRY_POLICIES

DOMAIN = ('technical_sword_term', 'swordsmith_artisan', 'sword_school',
          'sword_tradition', 'measurement_dimension')


def load(path):
    raw = Path(path).read_bytes()
    text = gzip.decompress(raw) if str(path).endswith('.gz') else raw
    return [json.loads(line) for line in text.splitlines()], hashlib.sha256(raw).hexdigest()


def domain_summary(report):
    result = {}
    for method in ('general', 'exact', 'contextual'):
        counts = {key: 0 for key in ('reference_mentions', 'correct_complete_groups',
                                     'false_positives', 'missed_mentions', 'false_specific_person_assignments')}
        english = {'correct': 0, 'scored': 0}
        errors = []
        for page in report['pages']:
            for category in DOMAIN:
                row = page.get('by_category', {}).get(category, {}).get(method)
                if not row:
                    continue
                for key in counts:
                    counts[key] += row[key]
                for key in english:
                    english[key] += row['english_sense'][key]
                for error in row['errors']['false_positives']:
                    errors.append({'page_id': page['page_id'], 'literal': error['literal'],
                                   'category': category, 'geometry': error.get('geometry')})
        tp, fp, fn = (counts[k] for k in ('correct_complete_groups', 'false_positives', 'missed_mentions'))
        result[method] = {**counts, 'precision': tp/(tp+fp) if tp+fp else None,
                          'recall': tp/(tp+fn) if tp+fn else None,
                          'english_reference': english, 'rejections': errors}
    return result


def compare(before, after, references, geometry_policy='area_overlap_min_half'):
    indexes = [{r['page_id']: r for r in rows} for rows in (before, after)]
    if any(len(idx) != len(rows) for idx, rows in zip(indexes, (before, after))) or not before or indexes[0].keys() != indexes[1].keys():
        raise ValueError('Comparison requires unique identical page cohorts')
    for key in indexes[0]:
        a, b = (idx[key] for idx in indexes)
        if a['state'] != 'complete' or b['state'] != 'complete':
            raise ValueError('Comparison includes an incomplete page')
        if a['source_sha256'] != b['source_sha256'] or a['supporting']['native_OCR_sha256'] != b['supporting']['native_OCR_sha256']:
            raise ValueError('Comparison source images or native OCR differ')
    scored = [score(rows, references, geometry_policy) for rows in (before, after)]
    if any(r['scored_pages'] != len(before) for r in scored):
        raise ValueError('Comparison requires declared exhaustive reference regions for every page')
    return {'schema': 'paired-boundary-regression-v1', 'pages': len(before), 'geometry_policy': geometry_policy,
            'source_and_ocr_identical': True, 'reference_sha256': scored[0]['reference_sha256'],
            'domain_categories': list(DOMAIN),
            'baseline': domain_summary(scored[0]), 'candidate': domain_summary(scored[1]),
            'limitations': ['Exposed development/regression pages; provisional AI references.',
                           'Exact complete literal, category and geometry are scored separately from translation.',
                           'No English accuracy is inferred when English reference count is zero.']}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('baseline', 'candidate', 'references', 'output'):
        parser.add_argument('--'+name, type=Path, required=True)
    parser.add_argument('--geometry-policy',choices=GEOMETRY_POLICIES,default=GEOMETRY_POLICIES[0])
    args = parser.parse_args()
    before, bh = load(args.baseline)
    after, ah = load(args.candidate)
    report = compare(before, after, json.loads(args.references.read_text()), args.geometry_policy)
    report['prediction_sha256'] = {'baseline': bh, 'candidate': ah}
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2)+'\n')
    print(json.dumps({k: {field: value for field, value in report[k]['contextual'].items() if field != 'rejections'} for k in ('baseline', 'candidate')}))
