"""Explicit human review staging and exact source-bound reuse."""
from pathlib import Path
import sqlite3
from .data_paths import data_dir,external
REVIEW_ROOT=None
def review_root():return external(REVIEW_ROOT if REVIEW_ROOT is not None else data_dir()/"reviews")
from .request_contracts import canonical,digest,require_hash
from .source_evidence import reviewed_reuse,retained_json,PROVENANCE_KEYS

def record_review(request):
    if request.get('attestation')!='source_pixels_review_completed':raise ValueError('Explicit completed source-pixel review attestation required')
    record=dict(request['record']);identity={k:record.get(k) for k in PROVENANCE_KEYS}
    crop=Path(request['crop']).read_bytes()
    if digest(crop)!=require_hash(identity['crop_sha256']):raise ValueError('Reviewed crop mismatch')
    source=Path(request['source_path']).read_bytes()
    if digest(source)!=require_hash(identity['source_sha256']):raise ValueError('Reviewed original source mismatch')
    if not isinstance(record.get('original_text'),str) or not isinstance(record.get('corrections'),list):raise ValueError('Original transcript and explicit corrections required')
    if record.get('label_origin')!='source_review':raise ValueError('Human source_review label origin required')
    # Verify the supplied provenance with the same reuse gate before persisting.
    import tempfile
    with tempfile.TemporaryDirectory() as tmp:
        raw=canonical(record);p=Path(tmp)/'record.json';p.write_bytes(raw)
        if not reviewed_reuse({'path':str(p),'sha256':digest(raw)},identity)['reusable']:raise ValueError('Complete human review provenance required')
    root=external(request.get('output_dir',review_root()))
    staging=review_root()
    if not root.is_relative_to(staging):raise ValueError('Review staging belongs under canonical reviews directory')
    root.mkdir(parents=True,exist_ok=True)
    image=root/(digest(crop)+'.png');target=root/(digest(raw)+'.json')
    for path,data in ((image,crop),(target,raw)):
        if path.exists() and path.read_bytes()!=data:raise ValueError('Immutable staged review collision')
        if not path.exists():path.write_bytes(data)
    index=staging/'index.sqlite3'
    with sqlite3.connect(index) as db:
        db.execute('CREATE TABLE IF NOT EXISTS reviews(identity_sha TEXT PRIMARY KEY,path TEXT NOT NULL,sha256 TEXT NOT NULL)')
        db.execute('INSERT INTO reviews VALUES(?,?,?) ON CONFLICT(identity_sha) DO UPDATE SET path=excluded.path,sha256=excluded.sha256',(digest(canonical(identity)),str(target),digest(raw)))
    return {'path':str(target),'sha256':digest(raw),'identity':identity,'crop':str(image),'state':'source_verified','publication_performed':False}

def lookup_review(identity):
    """One indexed exact-identity lookup; payload/provenance revalidated by caller."""
    index=review_root()/'index.sqlite3'
    if not index.is_file() or any(k not in identity for k in PROVENANCE_KEYS):return None
    key=digest(canonical({k:identity[k] for k in PROVENANCE_KEYS}))
    with sqlite3.connect(index.as_uri()+'?mode=ro',uri=True) as db:
        row=db.execute('SELECT path,sha256 FROM reviews WHERE identity_sha=?',(key,)).fetchone()
    return {'path':row[0],'sha256':row[1]} if row else None
