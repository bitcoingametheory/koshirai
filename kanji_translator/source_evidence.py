"""Read-only reviewed evidence reuse. Explicit human reviews remain separate from model proposals."""
import json
from pathlib import Path
from .request_contracts import digest,require_hash,canonical
PROVENANCE_KEYS=('source_sha256','crop_sha256','locator','style','geometry','orientation')
def retained_json(spec):
    raw=Path(spec['path']).read_bytes()
    if digest(raw)!=require_hash(spec['sha256']):raise ValueError('Retained payload hash mismatch')
    return json.loads(raw)
def reviewed_reuse(spec,identity):
    record=retained_json(spec)
    review=record.get('source_review') or {}
    matched=all(key in identity and key in record and record[key]==identity[key] for key in PROVENANCE_KEYS)
    # Model consensus/cost and a top-level verified flag cannot authorize reuse.
    valid=(matched and review.get('method')=='source_pixels' and review.get('reviewer_kind')=='human'
           and bool(review.get('reviewer_id')) and bool(review.get('review_record_id'))
           and review.get('source_sha256')==identity.get('source_sha256')
           and review.get('crop_sha256')==identity.get('crop_sha256')
           and review.get('locator')==identity.get('locator') and review.get('decision')=='source_verified'
           and isinstance(record.get('literal_text'),str))
    return {'state':'source_verified' if valid else 'proposal','record':record,'reusable':bool(valid),
            'reason':'exact_source_review' if valid else 'missing_or_mismatched_source_review'}
def witness_chain(row):
    evidence=row.get('evidence') or {}
    return evidence.get('original_chain_id') or evidence.get('source_sha256') or evidence.get('raw_sha256') or canonical({'source':row.get('source'),'record':row.get('source_record_id')}).decode()
def export_reviewed(request):
    records=[];seen={};source_splits={};excluded=[]
    for spec in request.get('records',[]):
        identity=spec.get('identity') or {};result=reviewed_reuse(spec,identity);record=result['record']
        if not result['reusable']:
            excluded.append({'sha256':spec['sha256'],'reason':result['reason']});continue
        group=record.get('split_group')
        if not group:raise ValueError('Reviewed export requires source/work/edition split_group')
        split=record.get('split')
        if split not in ('train','validation','test'):raise ValueError('Explicit immutable split required')
        if group in seen and seen[group]!=split:raise ValueError('Source/work/edition split leakage')
        seen[group]=split
        source=record['source_sha256']
        if source in source_splits and source_splits[source]!=split:raise ValueError('Original source split leakage')
        source_splits[source]=split
        if record.get('label_origin') in ('model','self_label','consensus'):raise ValueError('Model label cannot enter training export')
        if record.get('label_origin')!='source_review':raise ValueError('Explicit source_review label origin required')
        if spec.get('crop'):
            crop=Path(spec['crop']).read_bytes()
            if digest(crop)!=record['crop_sha256']:raise ValueError('Training crop mismatch')

        records.append({k:record.get(k) for k in (*PROVENANCE_KEYS,'literal_text','original_text','corrections','source_review','split_group','split','negative')})
    unique={digest(canonical(r)):r for r in records}
    return {'schema':'source-reviewed-export-v2','records':[unique[k] for k in sorted(unique)],'excluded':excluded,'training_run':False}
