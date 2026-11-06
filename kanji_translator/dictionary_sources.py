"""Streaming public dictionary builder. Source restrictions remain first-class data."""
from __future__ import annotations
import gzip,hashlib,json,os,sqlite3,tempfile
import xml.etree.ElementTree as ET
from pathlib import Path
from .reading_candidates import roman_forms

VERSION='public-dictionary-v1'
SCHEMA='''
CREATE TABLE dictionary_releases(source TEXT PRIMARY KEY,sha256 TEXT NOT NULL,manifest_json TEXT NOT NULL);
CREATE TABLE dictionary_spellings(source TEXT,entry_id TEXT,ordinal INTEGER,literal TEXT NOT NULL,tags_json TEXT NOT NULL,PRIMARY KEY(source,entry_id,ordinal));
CREATE TABLE dictionary_readings(source TEXT,entry_id TEXT,ordinal INTEGER,kana TEXT NOT NULL,no_kanji INTEGER NOT NULL,restrictions_json TEXT NOT NULL,payload_json TEXT NOT NULL,PRIMARY KEY(source,entry_id,ordinal));
CREATE TABLE dictionary_senses(source TEXT,entry_id TEXT,ordinal INTEGER,role TEXT NOT NULL,spellings_json TEXT NOT NULL,readings_json TEXT NOT NULL,pos_json TEXT NOT NULL,payload_json TEXT NOT NULL,PRIMARY KEY(source,entry_id,ordinal));
CREATE TABLE dictionary_aliases(alias TEXT,source TEXT,entry_id TEXT,kana TEXT,rule TEXT,PRIMARY KEY(alias,source,entry_id,kana,rule));
CREATE TABLE dictionary_characters(literal TEXT PRIMARY KEY,payload_json TEXT NOT NULL);
CREATE TABLE japanese_variant_relations(literal TEXT,target TEXT,relation TEXT,source TEXT,evidence TEXT,PRIMARY KEY(literal,target,relation,source));
CREATE TABLE glyph_sequences(sequence TEXT,collection TEXT,glyph TEXT,source TEXT,PRIMARY KEY(sequence,collection,glyph));
'''
INDEXES='''
CREATE INDEX spelling_lookup ON dictionary_spellings(literal);
CREATE INDEX reading_lookup ON dictionary_readings(kana);
CREATE INDEX variant_lookup ON japanese_variant_relations(literal);
CREATE INDEX variant_target ON japanese_variant_relations(target);
'''

def encoded(value):return json.dumps(value,ensure_ascii=False,separators=(',',':'))
def sha256(path):
    with Path(path).open('rb') as stream:return hashlib.file_digest(stream,'sha256').hexdigest()
def payload(element):
    return {'tag':element.tag,'attributes':dict(element.attrib),'text':element.text or '', 'children':[payload(e) for e in element]}
def values(element,tag):return [e.text or '' for e in element.findall(tag)]
def records(path,tag,root_tag):
    # ElementTree does not fetch external entities; its amplification limit stays enabled.
    with gzip.open(path,'rb') as stream:
        context=ET.iterparse(stream,events=('start','end'));_,root=next(context)
        if root.tag!=root_tag:raise ValueError('Unexpected dictionary root: '+root.tag)
        for event,node in context:
            if event=='end' and node.tag==tag:
                yield node
                node.clear();root.clear()
def entries(db,path,source):
    count=0
    for entry in records(path,'entry','JMdict' if source=='jmdict' else 'JMnedict'):
        eid=entry.findtext('ent_seq')
        if not eid:raise ValueError('Dictionary entry missing ent_seq')
        for i,k in enumerate(entry.findall('k_ele')):
            literal=k.findtext('keb')
            if not literal:raise ValueError('Dictionary spelling missing keb')
            db.execute('INSERT INTO dictionary_spellings VALUES(?,?,?,?,?)',(source,eid,i,literal,encoded(payload(k))))
        for i,r in enumerate(entry.findall('r_ele')):
            kana=r.findtext('reb')
            if not kana:raise ValueError('Dictionary reading missing reb')
            db.execute('INSERT INTO dictionary_readings VALUES(?,?,?,?,?,?,?)',(source,eid,i,kana,int(r.find('re_nokanji') is not None),encoded(values(r,'re_restr')),encoded(payload(r))))
            db.executemany('INSERT OR IGNORE INTO dictionary_aliases VALUES(?,?,?,?,?)',[(alias.casefold(),source,eid,kana,rule) for rule,alias in roman_forms(kana).items()])
        prior_pos=[]
        for i,s in enumerate(entry.findall('sense' if source=='jmdict' else 'trans')):
            prior_pos=values(s,'pos') or prior_pos
            db.execute('INSERT INTO dictionary_senses VALUES(?,?,?,?,?,?,?,?)',(source,eid,i,'word_sense' if source=='jmdict' else 'name_translation',encoded(values(s,'stagk')),encoded(values(s,'stagr')),encoded(prior_pos),encoded(payload(s))))
        count+=1
    if not count:raise ValueError('Empty dictionary: '+source)
    return count

def characters(db,path):
    codes={};edges=[];count=0
    for node in records(path,'character','kanjidic2'):
        literal=node.findtext('literal')
        if not literal:raise ValueError('Character missing literal')
        db.execute('INSERT INTO dictionary_characters VALUES(?,?)',(literal,encoded(payload(node))))
        for cp in node.findall('codepoint/cp_value'):codes[(cp.get('cp_type'),cp.text)]=literal
        for edge in node.findall('misc/variant'):edges.append((literal,edge.get('var_type'),edge.text))
        count+=1
    for literal,kind,code in edges:
        target=codes.get((kind,code))
        if kind=='ucs':
            try:target=chr(int(code,16))
            except (ValueError,TypeError):continue
        if target and target!=literal:
            db.execute('INSERT OR IGNORE INTO japanese_variant_relations VALUES(?,?,?,?,?)',(literal,target,'dictionary_variant','kanjidic2',encoded({'type':kind,'value':code})))
    if not count:raise ValueError('Empty character dictionary')
    return count

def build(inputs,output,manifests):
    """Atomic replacement. An interrupted/invalid build leaves the old DB intact."""
    from .data_paths import external
    output=external(output);output.parent.mkdir(parents=True,exist_ok=True)
    hashes={name:sha256(path) for name,path in inputs.items()}
    expected={name:(hashes[name],encoded({**manifests[name],'builder':VERSION})) for name in inputs}
    if output.is_file():
        try:
            with sqlite3.connect(output.as_uri()+'?mode=ro',uri=True) as db:
                previous={n:(h,m) for n,h,m in db.execute('select * from dictionary_releases')}
                if previous==expected:return {'state':'unchanged','sources':hashes}
        except sqlite3.DatabaseError:pass
    handle,temp=tempfile.mkstemp(prefix='dictionary-',suffix='.sqlite3',dir=output.parent);os.close(handle);temp=Path(temp)
    counts={}
    try:
        with sqlite3.connect(temp) as db:
            db.executescript(SCHEMA)
            for name in ('jmdict','jmnedict'):counts[name]=entries(db,inputs[name],name)
            counts['kanjidic2']=characters(db,inputs['kanjidic2'])
            db.executemany('INSERT INTO dictionary_releases VALUES(?,?,?)',[(n,h,m) for n,(h,m) in expected.items()])
            db.executescript(INDEXES)
            if db.execute('PRAGMA integrity_check').fetchone()[0]!='ok':raise ValueError('Dictionary integrity check failed')
        os.replace(temp,output)
    finally:temp.unlink(missing_ok=True)
    return {'state':'built','counts':counts,'sources':hashes}
