"""One typed lexical adapter for native text and recognized literal spans.

No sentence translation or automatic identity decision. Source spellings and
pronunciations are independent. Dictionary alternatives retain restrictions.
"""
from __future__ import annotations
import csv, hashlib, importlib.metadata, json, os, re, sqlite3, unicodedata
from pathlib import Path
from .request_contracts import canonical,digest
from .reading_candidates import roman_forms
from .data_paths import data_dir
MASTER=Path(os.environ.get('KANJI_LEXICON',data_dir()/'lexicon.sqlite3'))
VERSION='lexical-reader-v5-bounded-literal'
PROFILES=Path(os.environ.get('KANJI_PROFILES',data_dir()/'profiles.json'))
JP=re.compile('[\u3040-\u30ff\u3400-\u9fff\uf900-\ufaff\U00020000-\U0003347f]')
def children(node,tag):return [c for c in node['children'] if c['tag']==tag]
def texts(node,tag):return [c['text'] for c in children(node,tag)]
def identity(path=MASTER,profile='modern'):
 from .research_corpus import revision
 corpus_revision=revision()
 path=Path(path)
 if not path.is_file():return {'version':VERSION,'state':'unavailable','path':str(path),'profile':profile}
 with sqlite3.connect(path.resolve().as_uri()+'?mode=ro',uri=True) as db:
  try:releases=db.execute('select source,sha256,manifest_json from dictionary_releases order by source').fetchall()
  except sqlite3.OperationalError:return {'version':VERSION,'state':'unavailable','reason':'dictionary_tables_missing','profile':profile}
 return {'version':VERSION,'corpus_revision':corpus_revision,'releases':[list(r) for r in releases],'profile':profile,'profiles_sha256':digest(PROFILES.read_bytes()) if PROFILES.exists() else None,'rules':'exact-first-kanjidic-japanese-ivd-v1','romaji':'hepburn-expanded-macron-lossy-v1'}
def morphology(text,profile):
 if profile=='modern':
  try:
   import unidic_lite
   p={'state':'available','dictionary':unidic_lite.DICDIR,'version':importlib.metadata.version('unidic-lite')}
  except ImportError:return {'state':'runtime_unavailable','profile':profile,'tokens':[]}
 else:
  profiles=json.loads(PROFILES.read_text()) if PROFILES.exists() else {}
  p=profiles.get(profile)
 if not p or p.get('state')!='available':return {'state':'unsupported_profile','profile':profile,'tokens':[]}
 try:
  import MeCab
  tagger=MeCab.Tagger('-r /dev/null -d "'+p['dictionary']+'"')
  n=tagger.parseToNode(text);tokens=[];position=0
  while n:
   if n.surface:
    start=text.find(n.surface,position)
    if start<0:raise ValueError('Morphological span failed literal roundtrip')
    features=next(csv.reader([n.feature]));get=lambda i:features[i] if i<len(features) and features[i]!='*' else None
    lemma=get(7);pron=get(9)
    tokens.append({'start':start,'end':start+len(n.surface),'literal':n.surface,'lemma':lemma,'lemma_reading':get(6),'pronunciation':pron,'orthographic_base':get(10),'pos':features[:4],'inflection_type':get(4),'inflection_form':get(5),'features':features,'unknown':n.stat==1,'negative':bool(lemma in ('無い','ない','ぬ','ず','不','未') or (get(0)=='助動詞' and get(4) and any(x in get(4) for x in ('ナイ','ヌ','ズ'))))})
    position=start+len(n.surface)
   n=n.next
  return {'state':'available','profile':profile,'dictionary_version':p['version'],'tokens':tokens,'engine':'MeCab','engine_version':importlib.metadata.version('mecab-python3')}
 except ImportError:return {'state':'runtime_unavailable','profile':profile,'tokens':[]}

def variants(db,text):
 result=[(text,[])];seen={text}
 # No normalization rewrites literal; every retrieval derivative cites its edge.
 for i,c in enumerate(text):
  edges=db.execute('select literal,target,relation,source,evidence from japanese_variant_relations where literal=? or target=?',(c,c)).fetchall()
  for old,path in list(result):
   for a,b,relation,source,evidence in edges:
    target=b if a==c else a;new=old[:i]+target+old[i+1:]
    if new not in seen and len(result)<64:seen.add(new);result.append((new,path+[{'start':i,'original':c,'target':target,'relation':relation,'source':source,'evidence':json.loads(evidence) if evidence.startswith('{') else evidence}]))
 # IVS fallback is explicit and only for registered sequences.
 for seq,coll,glyph in db.execute('select sequence,collection,glyph from glyph_sequences where sequence in ('+','.join('?' for _ in range(max(1,len(text)-1)))+')',tuple(text[i:i+2] for i in range(len(text)-1)) or ('',)):
  new=text.replace(seq,seq[0]);
  if new not in seen:result.append((new,[{'relation':'registered_IVS_base_candidate','sequence':seq,'collection':coll,'glyph':glyph}]))
 return result

class LexicalReader:
 def __init__(self,path=MASTER):
  self.db=sqlite3.connect(Path(path).resolve().as_uri()+'?mode=ro',uri=True)
 def close(self):self.db.close()
 def exact(self,text,method='exact',path=None,limit=128):
  db=self.db
  ids=db.execute('select source,entry_id from dictionary_spellings where literal=? union select source,entry_id from dictionary_readings where kana=?',(text,text)).fetchall()
  roman=bool(re.fullmatch("[A-Za-zāīūēōĀĪŪĒŌ'’-]+",text))
  if roman:ids=db.execute('select distinct source,entry_id from dictionary_aliases where alias=?',(text.casefold(),)).fetchall()
  rows=[]
  for source,eid in ids[:limit]:
   ks=[x[0] for x in db.execute('select literal from dictionary_spellings where source=? and entry_id=? order by ordinal',(source,eid))]
   senses=db.execute('select ordinal,role,spellings_json,readings_json,pos_json,payload_json from dictionary_senses where source=? and entry_id=? order by ordinal',(source,eid)).fetchall()
   for kana,no_kanji,restr,payload in db.execute('select kana,no_kanji,restrictions_json,payload_json from dictionary_readings where source=? and entry_id=? order by ordinal',(source,eid)):
    restrictions=json.loads(restr);forms=[] if no_kanji else restrictions or ks
    if roman and not db.execute('select 1 from dictionary_aliases where alias=? and source=? and entry_id=? and kana=?',(text.casefold(),source,eid,kana)).fetchone():continue
    if not roman and text!=kana and text not in forms:continue
    for spelling in (forms if text==kana or roman else [text]) or [None]:
     applicable=[]
     for ordinal,role,sk,sr,pos,p in senses:
      if (json.loads(sk) and spelling not in json.loads(sk)) or (json.loads(sr) and kana not in json.loads(sr)):continue
      node=json.loads(p);glosses=children(node,'gloss' if source=='jmdict' else 'trans_det')
      applicable.append({'ordinal':ordinal,'role':role,'english':[g['text'] for g in glosses if g['attributes'].get('{http://www.w3.org/XML/1998/namespace}lang','eng')=='eng'],'glosses':glosses,'pos':json.loads(pos),'name_types':texts(node,'name_type'),'tags':node,'restrictions':{'spellings':json.loads(sk),'readings':json.loads(sr)}})
     if applicable:rows.append({'source':source,'entry_id':eid,'spelling':spelling,'kana':kana,'romaji':roman_forms(kana),'romaji_basis':'dictionary kana spelling; historical pronunciation is not inferred','historical_kana_spelling':bool(re.search('[ゐゑヰヱ]',kana)),'reading_payload':json.loads(payload),'reading_restrictions':restrictions,'match':method if not roman else 'romaji_alias','variant_path':path or [],'senses':applicable,'identity_accepted':False})
  return {'candidates':rows,'entry_count':len(ids),'truncated':len(ids)>limit}
 def lookup(self,text):
  row=self.exact(text)
  rows=list(row['candidates']);truncated=row['truncated']
  for alias,path in variants(self.db,text)[1:]:
   r=self.exact(alias,'attested_variant',path);rows.extend(r['candidates']);truncated|=r['truncated']
  return {'candidates':rows,'entry_count':len({(r['source'],r['entry_id']) for r in rows}),'truncated':truncated}
 def domain(self,text):
  from .sword_library import lookup
  public=lookup(text)
  private=self._private_domain(text)
  if private.get("state")!="unavailable":
   for kind in ("assertions","concepts","smith_name_candidates"):
    public[kind].extend(private.get(kind,[]))
  return public
 def _private_domain(self,text):
  from .text_normalization import normalized
  rows=[]
  required={'witnesses','domain_assertions','domain_entries','domain_spellings','sword_concepts','sword_concept_aliases','sword_concept_evidence'}
  available={r[0] for r in self.db.execute("select name from sqlite_master where type='table'")}
  if not required <= available:return {'state':'unavailable','assertions':[],'concepts':[],'smith_name_candidates':[],'truncated':False,'independent_chains':None,'chain_policy':'optional private domain tables absent'}
  sql='''select w.id,w.raw_text,w.source,w.record_id,w.kind,w.english,w.context_json,w.evidence_json,a.role,a.printed_romaji,a.english,a.chain_id,a.review_state from witnesses w join domain_assertions a on a.witness_id=w.id where w.search_form=? order by w.id limit 129'''
  fetched=self.db.execute(sql,(normalized(text),)).fetchall()
  for wid,literal,source,record,kind,original,context,evidence,role,roman,english,chain,review in fetched[:128]:
   rows.append({'witness_id':wid,'literal':literal,'source':source,'record_id':record,'kind':kind,'original_english_field':original,'role':role,'printed_romaji':roman,'english':english,'context':json.loads(context),'evidence':json.loads(evidence),'chain_id':chain,'review_state':review,'identity_accepted':False})
  for source,eid,original,roman,english,role,payload,provenance in self.db.execute('select e.* from domain_entries e join domain_spellings s on e.source=s.source and e.entry_id=s.entry_id where s.literal=? order by e.source,e.entry_id',(text,)):
   rows.append({'source':source,'entry_id':eid,'literal':original,'printed_romaji':roman,'english':english,'role':role,'payload':json.loads(payload),'evidence':json.loads(provenance),'review_state':'retained_source_extraction','identity_accepted':False})
  from .text_normalization import query_normalized
  concepts=[]
  for cid,payload in self.db.execute('select distinct c.concept_id,c.payload_json from sword_concepts c join sword_concept_aliases a using(concept_id) where a.query_key=? order by c.concept_id',(query_normalized(text),)):
   concepts.append({'concept_id':cid,'source_concept':json.loads(payload),'aliases':[json.loads(r[0]) for r in self.db.execute('select payload_json from sword_concept_aliases where concept_id=? order by alias_id',(cid,))],'source_senses':[json.loads(r[0]) for r in self.db.execute('select payload_json from sword_concept_evidence where concept_id=? order by entry_id',(cid,))],'resolution':'existing source concept; review status belongs to each sense link; subtype IDs remain distinct'})
  names=[]
  for wid,literal,record,roman,context,evidence in self.db.execute("select id,raw_text,record_id,english,context_json,evidence_json from witnesses where family='club' and search_form=? order by id",(normalized(text),)):
   names.append({'witness_id':wid,'literal':literal,'source':'club','source_record_id':record,'printed_romaji':roman,'context':json.loads(context),'evidence':json.loads(evidence),'identity_accepted':False,'role':'smith_name_candidate'})
  return {'assertions':rows,'concepts':concepts,'smith_name_candidates':names,'truncated':len(fetched)>128,'independent_chains':None,'chain_policy':'unknown independence is not corroboration'}

def read(text,config=None):
 config=config or {};path=Path(config.get('path',MASTER));profile=config.get('profile','modern');ident=identity(path,profile)
 if ident.get('state')=='unavailable':return {'state':'unavailable','identity':ident,'literal_text':text,'spans':[]}
 morph=morphology(text,profile);tokens=morph['tokens'];reader=LexicalReader(path)
 try:
  spans={(0,len(text)):'whole'} if text else {}
  for i,t in enumerate(tokens):
   for end in tokens[i:i+8]:spans.setdefault((t['start'],end['end']),'compound_candidate')
  # Exact bounded substrings make whole names independent of morphology runtime
  # and token boundaries. SQL filters candidates in batches before sense lookup.
  potential={}
  for start in range(len(text)):
   if not JP.match(text[start]):continue
   for end in range(start+2,min(len(text),start+32)+1):
    literal=text[start:end]
    if re.search(r'[\s。、，,！？!?\[\]【】]',literal):break
    potential.setdefault(literal,[]).append((start,end))
  keys=list(potential)
  for offset in range(0,len(keys),500):
   batch=keys[offset:offset+500]
   sql='select distinct literal from dictionary_spellings where literal in ('+','.join('?' for _ in batch)+')'
   for literal, in reader.db.execute(sql,batch):
    for key in potential[literal]:spans.setdefault(key,'exact_bounded_literal')
  out=[];covered=set()
  for (start,end),kind in sorted(spans.items()):
   literal=text[start:end];result=reader.lookup(literal)
   lemma=None
   token=next((t for t in tokens if t['start']==start and t['end']==end),None)
   if not result['candidates'] and token:
    for base in dict.fromkeys([token['orthographic_base'],token['lemma']]):
     if base and base!=literal:
      r=reader.lookup(base)
      if r['candidates']:result=r;lemma=base;break
   domain=reader.domain(literal) if config.get('include_sword',True) else {'assertions':[],'concepts':[],'smith_name_candidates':[]}
   excluded=set(config.get('exclude_source_families',[]))
   if excluded:
    for key in ('assertions','smith_name_candidates'):
     domain[key]=[row for row in domain.get(key,[]) if row.get('source','').split(':')[0] not in excluded]
   if result['candidates'] or domain['assertions'] or domain['concepts'] or domain['smith_name_candidates'] or domain.get('local_mappings'):
    for assertion in domain['assertions']:
     if assertion.get('printed_romaji'):
      fold=lambda s:re.sub('[^a-z]', '', unicodedata.normalize('NFD',s.casefold()))
      printed=fold(assertion['printed_romaji']);agrees=[c for c in result['candidates'] if any(fold(a)==printed for a in c['romaji'].values())]
      assertion['romaji_comparison']={'state':'unresolved' if not result['candidates'] else 'candidate_agreement' if agrees else 'conflict','matching_candidates':[{'source':c['source'],'entry_id':c['entry_id'],'kana':c['kana']} for c in agrees],'basis':'bounded derived aliases; printed source remains independent; no identity decision'}
    covered.update(range(start,end));span={'start':start,'end':end,'literal':literal,'lookup_lemma':lemma,'span_role':kind,**result,'domain':domain,'ambiguous':len(result['candidates'])>1,'resolution':'candidates_only'}
    from .meaning_selection import select
    span['selection']=select(span);out.append(span)
  characters=[]
  for c in dict.fromkeys(text):
   row=reader.db.execute('select payload_json from dictionary_characters where literal=?',(c,)).fetchone()
   if row:characters.append({'literal':c,'role':'character_gloss','source':'kanjidic2','payload':json.loads(row[0])})
  predicates=[]
  for i,t in enumerate(tokens):
   if t['pos'][0] not in ('動詞','形容詞','形状詞'):continue
   tail=[]
   for aux in tokens[i+1:]:
    if aux['pos'][0] not in ('助動詞',):break
    tail.append(aux)
   if tail:
    end=tail[-1]['end'];predicates.append({'start':t['start'],'end':end,'literal':text[t['start']:end],'lemma':t['lemma'],'polarity':'negative' if any(x['negative'] for x in tail) else 'unmarked','past_auxiliary':any(x['lemma']=='た' and x['pos'][0]=='助動詞' for x in tail),'evidence':'MeCab/UniDic token features; scope is the bounded auxiliary chain','tokens':[t,*tail]})
  return {'state':'available','version':VERSION,'identity':ident,'literal_text':text,'nfc_derivative':unicodedata.normalize('NFC',text),'morphology':morph,'spans':out,'characters':characters,'unknown_offsets':[i for i,c in enumerate(text) if JP.match(c) and i not in covered],'predicates':predicates,'negative_tokens':[t for t in tokens if t['negative']],'translation':None,'qualification':'engineering_lexical_candidates_only'}
 finally:reader.close()


def candidates(request):
 """Exact dictionary/domain witnesses only. Never infer missing characters."""
 from .text_normalization import normalized
 from .source_evidence import witness_chain
 from .context_constraints import compare
 text=request['pattern'];path=Path(request.get('lexicon_path',MASTER))
 library={'state':'available' if path.is_file() else 'unavailable','path':str(path)}
 unknown=bool(re.search(r'[?*□〓�\[\]]',text))
 rows=[];seen=set();excluded=request.get('exclude_chain_ids',[]);book=request.get('source_work_id')
 explicit='witnesses' in request or request.get('use_master_lexicon') is False
 if explicit:library={'state':'explicit_witnesses'}
 dictionary={'candidates':[]};domain={}
 if not unknown:
  witnesses=request.get('witnesses',[]) if explicit else []
  if not explicit and path.is_file():
   reader=LexicalReader(path)
   try:
    dictionary=reader.lookup(text);domain=reader.domain(text)
    has_witnesses=reader.db.execute("select 1 from sqlite_master where type='table' and name='witnesses'").fetchone()
    for raw,source,record,kind,english,context,evidence in (reader.db.execute('select raw_text,source,record_id,kind,english,context_json,evidence_json from witnesses where search_form=? order by id',(normalized(text),)) if has_witnesses else []):
     ev=json.loads(evidence);ev.update(lexicon_owner=str(path),lexicon_locator=record)
     witnesses.append({'raw_text':raw,'source':source,'source_record_id':record,'kind':kind,'english':english,'context':json.loads(context),'evidence':ev})
   finally:reader.close()
  for w in witnesses:
   if normalized(w.get('raw_text') or '')!=normalized(text):continue
   chain=witness_chain(w);ev=w.get('evidence') or {}
   if chain in excluded or (book and ev.get('source_work_id')==book):continue
   key=(w['raw_text'],chain)
   if key in seen:continue
   seen.add(key);support,conflicts=compare(request.get('context',{}),w.get('context',{}))
   rows.append({'candidate':w['raw_text'],'source':w.get('source','unknown'),'source_record_id':str(w.get('source_record_id','unknown')),'kind':w.get('kind','reference_term'),'english':w.get('english'),'context':w.get('context',{}),'evidence':ev,'supporting_fields':support,'contradictory_fields':conflicts,'identity_accepted':False})
 return {'library':library,'candidates':rows,'dictionary':dictionary,'domain':domain,'state':'abstain' if unknown or not (rows or dictionary['candidates'] or any(domain.get(k) for k in ('assertions','concepts','smith_name_candidates'))) else 'exact_evidence','proposed_reading':None,'reason':'literal_unknown_preserved' if unknown else 'exact_lookup_only','probability_correct':None,'identity_accepted':False}
