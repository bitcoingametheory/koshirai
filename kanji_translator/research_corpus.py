"""Private, immutable scan observations and explicit human mapping reviews."""
import json,sqlite3,hashlib
from pathlib import Path
from .request_contracts import canonical,digest
from .data_paths import data_dir,external
from .text_normalization import query_normalized

def database(path=None):
    path=external(path or data_dir()/'corpus.sqlite3');path.parent.mkdir(parents=True,exist_ok=True)
    db=sqlite3.connect(path)
    db.executescript('''CREATE TABLE IF NOT EXISTS observations(id TEXT PRIMARY KEY,payload TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS reviews(id TEXT PRIMARY KEY,observation_id TEXT NOT NULL,payload TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS mappings(review_id TEXT,form TEXT,PRIMARY KEY(review_id,form));''')
    return db

def ingest(request):
    """Idempotently retain scan regions, original OCR and source-bound locations."""
    folder=Path(request['source_dir']).expanduser().resolve();results=Path(request['results']).expanduser().resolve()
    added=existing=0
    with database(request.get('database')) as db,results.open(encoding='utf-8') as stream:
        for line in stream:
            row=json.loads(line);source=(folder/row['file']).resolve()
            if not source.is_relative_to(folder) or not source.is_file():raise ValueError('Source file must be inside the supplied folder')
            sha=hashlib.sha256(source.read_bytes()).hexdigest()
            if sha!=row['source_sha256']:raise ValueError('Source hash differs from scan receipt')
            for region in row['result']['enrichment']['regions']:
                observation={'source_sha256':sha,'source_path':str(source),'locator':{'file':row['file'],'page':row['page'],'region_id':region['region_id']},'original_text':region.get('original_text',region['literal_text']),'region':region,'state':'unreviewed'}
                if observation['original_text'] != region['literal_text'] or region.get('enhancement'):
                    observation['enhanced_text']=region['literal_text'];observation['enhancement']=region.get('enhancement')
                # The identity also contains the observation, so a new OCR result never
                # overwrites the previous payload or its accepted corrections.
                key=digest(canonical({k:v for k,v in observation.items() if k!='source_path'}))
                cursor=db.execute('INSERT OR IGNORE INTO observations VALUES(?,?)',(key,canonical(observation).decode()))
                added+=cursor.rowcount;existing+=1-cursor.rowcount
    return {'added':added,'existing':existing,'automatic_promotion':False,'sharing_performed':False}

def review(request):
    """A human explicitly reviews pixels and each proposed mapping; never infer it."""
    if request.get('attestation')!='source_pixels_and_mapping_review_completed':raise ValueError('Explicit completed source and mapping review required')
    if not isinstance(request.get('reviewer_id'),str) or not request['reviewer_id'].strip():raise ValueError('Reviewer ID required')
    decision=request.get('decision')
    if decision not in ('accept','reject'):raise ValueError('Explicit accept or reject decision required')
    with database(request.get('database')) as db:
        row=db.execute('SELECT payload FROM observations WHERE id=?',(request['observation_id'],)).fetchone()
        if not row:raise ValueError('Unknown observation')
        observation=json.loads(row[0]);source=Path(observation['source_path'])
        if hashlib.sha256(source.read_bytes()).hexdigest()!=observation['source_sha256']:raise ValueError('Original source changed')
        literal=request.get('literal');reading=request.get('reading');english=request.get('english')
        if decision=='accept':
            from .build_sword_library import literal as japanese,roman
            if japanese(literal)!=literal:raise ValueError('A bounded Japanese literal without unknown glyphs is required')
            if reading is not None and (not roman(reading) or len(reading)>80):raise ValueError('Unsupported or ambiguous reading; retain as an unreviewed observation')
            if english is not None and (not isinstance(english,str) or not english.strip() or len(english)>160):raise ValueError('Explicit bounded English mapping required')
            if not reading and not english:raise ValueError('Supply an explicitly reviewed reading or English mapping')
        payload={'observation_id':request['observation_id'],'source_sha256':observation['source_sha256'],'locator':observation['locator'],'original_text':observation['original_text'],'literal':literal,'reading':reading,'english':english,'decision':decision,'reviewer_id':request['reviewer_id'],'attestation':request['attestation'],'note':request.get('note'),'supersedes':request.get('supersedes')}
        if payload['supersedes']:
            previous=db.execute('SELECT observation_id FROM reviews WHERE id=?',(payload['supersedes'],)).fetchone()
            if not previous or previous[0]!=request['observation_id']:raise ValueError('Superseded review must belong to the same observation')
        key=digest(canonical(payload));db.execute('INSERT OR IGNORE INTO reviews VALUES(?,?,?)',(key,request['observation_id'],canonical(payload).decode()))
        if decision=='accept':
            for form in (literal,reading,english):
                if form:db.execute('INSERT OR IGNORE INTO mappings VALUES(?,?)',(key,query_normalized(form)))
    return {'review_id':key,'state':'reviewed_'+decision,'sharing_performed':False}

def lookup(text,path=None):
    path=external(path or data_dir()/'corpus.sqlite3')
    if not path.exists():return []
    with sqlite3.connect(path.as_uri()+'?mode=ro',uri=True) as db:
        rows=db.execute('SELECT r.id,r.observation_id,r.payload FROM mappings m JOIN reviews r ON r.id=m.review_id WHERE m.form=?',(query_normalized(text),)).fetchall()
        all_reviews=[json.loads(p) for p, in db.execute('SELECT payload FROM reviews')]
    superseded={p['supersedes'] for p in all_reviews if p.get('supersedes')};out=[]
    for key,oid,raw in rows:
        if key in superseded:continue
        row=json.loads(raw)
        # Competing accepted interpretations stay visible; a reviewer must explicitly
        # supersede a previous review rather than silently replacing it.
        out.append({**row,'review_id':key,'identity_accepted':False,'resolution':'human_reviewed_local_mapping'})
    conflict=len({(r['literal'],r['reading'],r['english']) for r in out})>1
    for row in out:row['conflict']=conflict
    return out

def inspect(request):
    with database(request.get('database')) as db:
        rows=db.execute('SELECT id,payload FROM observations ORDER BY id LIMIT ?',(min(100,max(1,int(request.get('limit',20)))),)).fetchall()
        return {'observations':[{'id':k,**json.loads(p)} for k,p in rows],'total':db.execute('SELECT count(*) FROM observations').fetchone()[0],'reviews':db.execute('SELECT count(*) FROM reviews').fetchone()[0]}


def revision():
    path=data_dir()/'corpus.sqlite3'
    if not path.is_file():return None
    with sqlite3.connect(path.as_uri()+'?mode=ro',uri=True) as db:
        return digest(canonical([k for k, in db.execute('SELECT id FROM reviews ORDER BY id')]))
