"""Portable derived sword facts. Source prose and private records are absent."""
import gzip,hashlib,json,re,sqlite3
from functools import lru_cache
from importlib.resources import files
from .text_normalization import query_normalized

@lru_cache(maxsize=1)
def bundle():
    root=files('kanji_translator').joinpath('resources')
    manifest=json.loads(root.joinpath('sword_library_manifest.json').read_text(encoding='utf-8'))
    raw=root.joinpath('sword_library.json.gz').read_bytes()
    if hashlib.sha256(raw).hexdigest()!=manifest['sha256']:raise ValueError('Sword bundle hash mismatch')
    decoded=gzip.decompress(raw)
    if hashlib.sha256(decoded).hexdigest()!=manifest['decoded_sha256']:raise ValueError('Sword decoded hash mismatch')
    data=json.loads(decoded)
    if data['schema']!=manifest['schema'] or any(len(data[k])!=n for k,n in manifest['counts'].items()):raise ValueError('Sword bundle completeness mismatch')
    return data,manifest

@lru_cache(maxsize=1)
def index():
    data,_=bundle();lookup={};concepts={r['concept_id']:r for r in data['concepts']}
    def add(form,kind,row):
        if form:lookup.setdefault(query_normalized(form),{}).setdefault(kind,[]).append(row)
    for row in data['aliases']:add(row['form'],'concepts',concepts[row['concept_id']])
    for row in data['concepts']:
        for key in ('label_ja','label_en'):add(row[key],'concepts',row)
    terms={(r['source'],r['entry_id']):r for r in data['terms']}
    for row in data['terms']:
        add(row['literal'],'assertions',row);add(row['printed_romaji'],'assertions',row);add(row.get('english'),'assertions',row)
    for row in data['spellings']:add(row['literal'],'assertions',terms[row['source'],row['entry_id']])
    for row in data['forms']:
        add(row['literal'],'assertions',row);add(row['printed_romaji'],'assertions',row);add(row.get('english'),'assertions',row)
    for row in data['variants']:
        add(row['literal'],'character_relations',row);add(row['target'],'character_relations',row)
    for row in data['glyphs']:add(row['sequence'],'glyph_sequences',row)
    for row in data['characters']:
        add(chr(int(row['codepoint'].removeprefix('U+'),16)),'unicode_properties',row)
    for row in data['character_forms']:
        for cp in re.findall(r'U\+([0-9A-Fa-f]{4,6})',row['ucs'] or ''):
            add(chr(int(cp,16)),'character_forms',row)
    for row in data['names']:
        add(row['literal'],'smith_name_candidates',row);add(row['printed_romaji'],'smith_name_candidates',row)
    return lookup

def lookup(text):
    data,manifest=bundle();matches=index().get(query_normalized(text),{})
    result={'state':'available','bundle_sha256':manifest['sha256'],'truncated':False,'independent_chains':None,'chain_policy':'Unknown independence is not corroboration; normalized source facts remain candidates.'}
    for kind in ('assertions','concepts','smith_name_candidates','character_relations','glyph_sequences','unicode_properties','character_forms'):
        seen=set();rows=[]
        for row in matches.get(kind,[]):
            key=json.dumps(row,sort_keys=True)
            if key in seen:continue
            seen.add(key)
            if kind=='concepts':
                cid=row['concept_id']
                row={'concept_id':cid,'source_concept':row,'aliases':[a for a in data['aliases'] if a['concept_id']==cid],'source_senses':[a for a in data['concept_links'] if a['concept_id']==cid],'resolution':'Retained review states; source prose omitted.'}
            from .meaning_selection import english_quality
            rows.append({**row,'identity_accepted':False,**({'english_quality':english_quality(row['english'])} if row.get('english') else {})})
        result[kind]=rows
    from .research_corpus import lookup as local_lookup
    from .semantic_roles import role_records
    result['semantic_role_assertions']=[{**r,'identity_accepted':False} for r in role_records(text)]
    result['local_mappings']=local_lookup(text)
    return result

def install(path):
    """Import only allowlisted bundled records into the external application DB."""
    data,manifest=bundle()
    with sqlite3.connect(path) as db:
        db.execute('CREATE TABLE IF NOT EXISTS sword_bundle (kind TEXT,ordinal INTEGER,payload TEXT,PRIMARY KEY(kind,ordinal))')
        db.execute('CREATE TABLE IF NOT EXISTS sword_release (sha256 TEXT PRIMARY KEY,manifest TEXT)')
        if db.execute('SELECT 1 FROM sword_release WHERE sha256=?',(manifest['sha256'],)).fetchone():return manifest
        db.execute('DELETE FROM sword_bundle');db.execute('DELETE FROM sword_release')
        for kind,rows in data.items():
            if isinstance(rows,list):db.executemany('INSERT INTO sword_bundle VALUES(?,?,?)',[(kind,i,json.dumps(row,ensure_ascii=False)) for i,row in enumerate(rows)])
        db.execute('INSERT INTO sword_release VALUES(?,?)',(manifest['sha256'],json.dumps(manifest)))
    return manifest
