"""Build a factual release from an explicitly supplied read-only parsed master.

No source acquisition, source acceptance or raw context export occurs here.
"""
import argparse
from collections import Counter, defaultdict
import gzip
import hashlib
import json
from pathlib import Path
import re
import sqlite3
import os
import tempfile
import unicodedata


def literal(value):
    """Bounded Japanese lookup forms, never surrounding sentences or unknowns."""
    if not isinstance(value, str) or not value.strip(): return None
    value = unicodedata.normalize('NFC', value.strip())
    if len(value) > 32 or not any('\u3040' <= c <= '\u30ff' or '\u3400' <= c <= '\u9fff' or '\U00020000' <= c <= '\U000323af' for c in value): return None
    if not all(c.isspace() or c in '・々〆ヶヵー／/（）()「」『』' or '\u3040' <= c <= '\u30ff' or '\u3400' <= c <= '\u9fff' or '\uf900' <= c <= '\ufaff' or '\U00020000' <= c <= '\U000323af' or '\U000e0100' <= c <= '\U000e01ef' for c in value): return None
    return value


def roman(value):
    if not value: return None
    value = value.strip()
    # Extracted translation columns also contain sentences. Only bounded tokens
    # compatible with romanization are retained; their correctness stays unreviewed.
    if len(value) > 80 or len(value.split()) > 8 or not re.fullmatch(r"[A-Za-zÀ-ž\s'’\-・/()]+", value): return None
    prose = {'the','is','are','was','were','which','who','have','has','said','as','used','term','meant','decoration','this','that','with','from','also','and','of','in','to','for','on','it','a','an','by','or','can','sword','blade'}
    if set(value.lower().replace('-', ' ').split()) & prose: return None
    # A word-count/stopword filter alone admits OCR-joined English prose.
    # Require every token to have a Japanese romanization-shaped spelling.
    # This is a conservative export filter, not pronunciation verification;
    # rejected candidate readings remain in the private master.
    plain = ''.join(c for c in unicodedata.normalize('NFKD', value.casefold())
                    if not unicodedata.combining(c))
    tokens = re.findall(r'[a-z]+', plain)
    mora = r'(?:[aeiou]|[kgsztdnhbpmrywfvj][aeiou]|(?:ky|gy|sh|sy|jy|ch|ty|dy|ny|hy|by|py|my|ry|kw|gw|ts)[aeiou]|n|m(?=[bmp]))'
    for token in tokens:
        token = re.sub(r'([bcdfghjkmprstvwxyz])\1', r'\1', token)
        token = re.sub(r't(?=ch)', '', token)  # Bitchu / hatcho spelling of sokuon.
        if not re.fullmatch(mora + '+', token): return None
    if not tokens: return None
    return value


def english_gloss(value):
    """Only short lexical facts; definitions, sentences and source prose stay private."""
    if not isinstance(value,str) or not value.strip():return None
    value=value.strip().rstrip('.')
    if len(value)>48 or not 1<=len(value.split())<=5 or roman(value):return None
    if not re.fullmatch(r"[A-Za-z][A-Za-z '’()/-]*",value):return None
    if set(re.findall(r'[a-z]+',value.lower())) & {'the','a','an','see','e','g','i','is','are','was','were','it','its','this','that','which','who','used','means','lit','for','of','to','from','with','also','or','and','term','word','called','when','as','can','by'}:return None
    from .meaning_selection import english_quality
    return value if english_quality(value)['eligible'] else None


def source_citation(evidence):
    """Portable locators and hashes, with private paths excluded."""
    source = evidence.get('source') or {}
    result = {k: evidence[k] for k in ('locator', 'page_locator', 'pdf_pages', 'derived_sha256')
              if evidence.get(k) is not None}
    raw_hash = source.get('sha256') or evidence.get('raw_sha256')
    if raw_hash:
        result['source_sha256'] = raw_hash
    match = re.search(r'_label_([^./]+)', source.get('path', ''))
    if match:
        result['printed_page'] = match[1]
    # Locators are identifiers; reject accidental path/URL values.
    return {k: v for k, v in result.items()
            if not isinstance(v, str) or not any(marker in v for marker in ('/home/', '/media/', '://'))}


def remap_source_text(value, mapping):
    """Apply an externally supplied private-label map without publishing its keys."""
    if not isinstance(mapping,dict) or any(not isinstance(k,str) or not k or not isinstance(v,str) or not v for k,v in mapping.items()):
        raise ValueError('Source map must contain nonempty string pairs')
    if isinstance(value,str):
        for original,replacement in sorted(mapping.items(),key=lambda pair:-len(pair[0])):
            value=value.replace(original,replacement)
    return value


def build(master, output, primary_reference_pages=None, source_map=None, aligned_terms=None):
    db = sqlite3.connect(Path(master).resolve().as_uri() + '?mode=ro', uri=True)
    db.execute('PRAGMA query_only=ON')
    source_map=source_map or {}
    remap_source_text('',source_map)
    def select(query):
        for row in db.execute(query):
            yield tuple(remap_source_text(value,source_map) for value in row)
    data = {'schema': 'sword-derived-v2'}
    field_dispositions=defaultdict(Counter)
    def account_field(cohort,name,original,derived):
        field_dispositions[cohort+':'+name]['absent' if not original else 'exported' if derived else 'retained_private_unsupported_or_prose']+=1
        return derived
    def records(table, order):
        return [json.loads(p) for p, in select(f'SELECT payload_json FROM {table} ORDER BY {order}')]
    def choose(row, keys): return {k: row.get(k) for k in keys}
    concept_dispositions = Counter()
    data['concepts'] = []
    for r in records('sword_concepts','concept_id'):
        row = choose(r, ('concept_id','label_ja','label_en','category','parent_concept_ids_json','status'))
        # Source-derived descriptions can also occur in labels and aliases.
        # Preserve concept identities, but export only Japanese/romaji labels.
        row['label_ja'] = literal(r.get('label_ja'))
        row['label_en'] = roman(r.get('label_en'))
        for field in ('label_ja','label_en'):
            if r.get(field) and row[field] is None:
                concept_dispositions['omitted_' + field] += 1
        data['concepts'].append(row)
    data['aliases'] = []
    for r in records('sword_concept_aliases','alias_id'):
        form = literal(r['alias_normalized']) or roman(r['alias_normalized'])
        concept_dispositions['aliases_input'] += 1
        if not form:
            concept_dispositions['aliases_omitted_non_lookup_text'] += 1
            continue
        data['aliases'].append({**choose(r, ('alias_id','concept_id','language','source_id','status')), 'form':form})
        concept_dispositions['aliases_exported'] += 1
    data['concept_links'] = [{**choose(r, ('entry_id','concept_id','first_page','last_page','match_basis','status')), 'term':roman(r.get('headword_raw')), 'source':'supporting_reference-encyclopedia'} for r in records('sword_concept_evidence','entry_id,concept_id')]
    data['terms'] = []
    term_rejections = Counter()
    for s,i,l,r,english,role in select('SELECT source,entry_id,literal,printed_romaji,english,role FROM domain_entries ORDER BY source,entry_id'):
        cohort='entries:'+s
        l=account_field(cohort,'kanji',l,literal(l));r=account_field(cohort,'romaji',r,roman(r));english=account_field(cohort,'english',english,english_gloss(english))
        if not literal(l) and not roman(r): term_rejections['unusable_lookup_form'] += 1; continue
        data['terms'].append(dict(source=s,entry_id=i,literal=literal(l),printed_romaji=roman(r),role=role,english=english,review_state='retained_source_extraction',concept_ids=[]))
    term_keys = {(r['source'],r['entry_id']) for r in data['terms']}
    data['spellings'] = [dict(literal=literal(l),source=s,entry_id=i) for l,s,i in select('SELECT * FROM domain_spellings ORDER BY source,entry_id,literal') if literal(l) and (s,i) in term_keys]
    concept_keys = defaultdict(set)
    def key(v):return re.sub(r'\s+',' ',unicodedata.normalize('NFKC',v or '').casefold()).strip()
    for r in data['aliases']: concept_keys[key(r['form'])].add(r['concept_id'])
    for r in data['concept_links']:
        if r['term']: concept_keys[key(r['term'])].add(r['concept_id'])
    for r in data['terms']: r['concept_ids'] = sorted(concept_keys[key(r['literal'])] | (concept_keys[key(r['printed_romaji'])] if r['printed_romaji'] else set()))
    groups = {}; coverage = defaultdict(Counter); readings = Counter()
    query = '''SELECT w.id,w.search_form,w.source,w.kind,w.english,w.has_unknown,a.printed_romaji,COALESCE(a.review_state,json_extract(w.evidence_json,'$.verification'),'retained_source_unreviewed'),a.english,w.evidence_json
               FROM witnesses w LEFT JOIN domain_assertions a ON a.witness_id=w.id ORDER BY w.id'''
    for witness_id,form,source,kind,english,unknown,printed,review,assertion_english,evidence in select(query):
        field_cohort='witnesses:'+source+':'+kind
        account_field(field_cohort,'kanji',form,literal(form) if not unknown else None)
        account_field(field_cohort,'romaji',printed or english,roman(printed or english))
        gloss=account_field(field_cohort,'english',assertion_english or english,english_gloss(assertion_english or english))
        cohort = coverage[(source,kind)]; cohort['input'] += 1
        if unknown: cohort['rejected_unknown_glyph'] += 1; continue
        form = literal(form)
        if not form: cohort['rejected_unusable_lookup_form'] += 1; continue
        category = 'smith_name_candidate' if kind == 'smith_source_record' else 'untyped_source_form'
        reading = roman(printed or english)
        if printed or english: readings['retained' if reading else 'rejected_non_romanization_or_prose'] += 1
        else: readings['absent'] += 1
        cohort['exported'] += 1
        k = (source,kind,form,reading,gloss,category,str(witness_id) if category=='smith_name_candidate' else '')
        if k not in groups: groups[k] = dict(source=source,source_kind=kind,literal=form,printed_romaji=reading,english=gloss,category=category,review_state=review,resolution='unresolved_source_candidate',identity_accepted=False,occurrences=0,citations=[])
        groups[k]['occurrences'] += 1
        if not source.startswith('dealer'):
            citation = source_citation(json.loads(evidence))
            if citation and citation not in groups[k]['citations']:
                groups[k]['citations'].append(citation)
        if category=='smith_name_candidate': groups[k]['candidate_id'] = 'candidate-' + str(witness_id)
    rows = [groups[k] for k in sorted(groups,key=lambda k:tuple(v or '' for v in k))]
    data['names'] = [r for r in rows if r['category']=='smith_name_candidate']
    data['forms'] = [r for r in rows if r['category']!='smith_name_candidate']
    bridges = []
    if primary_reference_pages:
        from .glossary_bridge import build_bridges
        bridges = build_bridges(primary_reference_pages, data)
        data['terms'].extend(bridges)
    aligned = []
    if aligned_terms:
        from .glossary_bridge import build_aligned_terms
        aligned = build_aligned_terms(aligned_terms)
        bridges.extend(aligned)
        data['terms'].extend(aligned)
    # Unicode relationships describe characters/glyphs, never a shared smith identity.
    relevant = set(''.join(r.get('literal') or r.get('form') or '' for kind in ('terms','spellings','names','forms','aliases') for r in data[kind]))
    all_variants = [dict(literal=l,target=t,relation=r,source=s,identity_accepted=False) for l,t,r,s in select('SELECT literal,target,relation,source FROM japanese_variant_relations ORDER BY literal,target,relation,source') if literal(l) and literal(t)]
    while True:
        expanded = relevant | {c for r in all_variants if set(r['literal']+r['target']) & relevant for c in r['literal']+r['target']}
        if expanded == relevant: break
        relevant = expanded
    data['variants'] = [r for r in all_variants if set(r['literal']+r['target']) & relevant]
    data['glyphs'] = [dict(sequence=s,collection=c,glyph=g,source=source) for s,c,g,source in select('SELECT * FROM glyph_sequences ORDER BY 1,2,3,4') if s and s[0] in relevant]
    allowed_properties = {'kJapanese','kJapaneseOn','kJapaneseKun','kTotalStrokes','kRSUnicode'}
    data['characters'] = []; unicode_counts = Counter()
    for source,cp,prop,value in select('SELECT * FROM unicode_properties ORDER BY source,codepoint,property'):
        if prop not in allowed_properties: unicode_counts['excluded_non_japanese_reading_or_structure_property'] += 1; continue
        if chr(int(cp.removeprefix('U+'),16)) not in relevant: unicode_counts['excluded_outside_attested_character_closure'] += 1; continue
        # The selected upstream values are readings or numeric structural facts.
        if len(value)>512: unicode_counts['rejected_oversized_value'] += 1; continue
        data['characters'].append(dict(source=source,codepoint=cp,property=prop,value=value)); unicode_counts['exported'] += 1
    data['character_forms'] = [];mj_input=0
    for mj_id, payload in select('SELECT * FROM mj_characters ORDER BY mj_id'):
        mj_input += 1
        row = json.loads(payload)
        points = re.findall(r'U\+([0-9A-Fa-f]{4,6})',str(row.get('対応するUCS',''))+' '+str(row.get('実装したUCS','')))
        if not any(chr(int(cp,16)) in relevant for cp in points): continue
        reading = row.get('読み(参考)')
        if not isinstance(reading,str) or not re.fullmatch(r'[ぁ-ゖァ-ヺー・ /]+',reading): reading = None
        def ucs(field):
            value = row.get(field)
            return value if isinstance(value,str) and re.fullmatch(r'U\+[0-9A-Fa-f]{4,6}(?:[ ,;]+U\+[0-9A-Fa-f]{4,6})*',value) else None
        data['character_forms'].append(dict(mj_id=mj_id,ucs=ucs('対応するUCS'),implemented_ucs=ucs('実装したUCS'),reading=reading,source='mj',identity_accepted=False))
    data['bibliography'] = [dict(source=s,title=t) for s,t in [
        ('supporting_reference','Private Japanese–English sword reference B'),('supporting_reference-saved-books','Private Japanese–English sword reference B'),('primary_reference','Private Japanese–English sword reference A'),('primary_reference-register','Private Japanese–English sword reference A'),('club','Nihonto Club swordsmith index'),('nwatch','Nihonto Watch reference'),('unihan','Unicode Unihan'),('ivd','Unicode Ideographic Variation Database'),('mj','Moji Joho character information'),('kanjidic2','EDRDG KANJIDIC2')]]
    data['bibliography'] += [dict(source=s,title=s.removeprefix('dealer:').replace('_',' ')) for s in sorted({r['source'] for r in rows if r['source'].startswith('dealer:')})]
    counts = {k:len(v) for k,v in data.items() if isinstance(v,list)}
    raw = json.dumps(data,ensure_ascii=False,sort_keys=True,separators=(',',':')).encode()
    for marker in (b'drive.google.com',b'/media/',b'/home/',b'payload_json',b'provenance_json',b'definition_raw',b'entry_text_raw'): assert marker not in raw, marker
    packed = gzip.compress(raw,mtime=0)
    manifest = dict(data_licenses={'unihan':'Unicode-3.0','ivd':'Unicode-3.0','mj':'CC-BY-SA-2.1-JP','kanjidic2':'CC-BY-SA-4.0'},schema=data['schema'],sha256=hashlib.sha256(packed).hexdigest(),decoded_sha256=hashlib.sha256(raw).hexdigest(),counts=counts,record_fields={k:sorted(set().union(*(r.keys() for r in v))) for k,v in data.items() if isinstance(v,list)},optional_record_fields={},term_sources=dict(Counter(r['source'] for r in data['terms'])),coverage=[dict(source=s,kind=k,**dict(v)) for (s,k),v in sorted(coverage.items())],reading_dispositions=dict(readings),term_rejections=dict(term_rejections),unicode_dispositions=dict(unicode_counts),character_form_dispositions={'input':mj_input,'excluded_outside_attested_character_closure':mj_input-len(data['character_forms']),'exported':len(data['character_forms']),'omitted_reading':sum(r['reading'] is None for r in data['character_forms'])},character_scope={'attested_and_variant_closure_characters':len(relevant),'variant_input':len(all_variants),'variant_exported':len(data['variants']),'glyph_input':db.execute('SELECT count(*) FROM glyph_sequences').fetchone()[0],'glyph_exported':len(data['glyphs'])},policy='Every retained witness is accounted for. Bounded forms remain unresolved source candidates. Readings are extracted candidates, not verified pronunciation. Unicode relations do not establish person identity. Source prose and private evidence are omitted.',excluded_fields=['source prose','definitions','captions','raw context','original source records','private paths','private identifiers','contact information'])
    manifest['mapping_fields']={k:dict(v) for k,v in sorted(field_dispositions.items())}
    manifest['glossary_bridges'] = {'records': len(bridges),
                                  'policy': 'Cited editorial lexical summaries from explicit spelling/headword joins or image-reviewed bilingual labels. Edition-specific source chains and provisional review remain visible.'}
    manifest['bilingual_alignments'] = {'records': len(aligned),
                                      'review_state': 'AI_source_image_reviewed_provisional_not_expert',
                                      'policy': 'Exact printed Japanese forms linked to English labels and short editorial glosses by page-image review; edition-specific hashes and locators retained. One work supplies both editions.'}
    manifest['optional_record_fields'] = {'terms': ['citations', 'bridge', 'alignment', 'meaning_origin', 'independence']}
    manifest['english_policy']='Only bounded lexical gloss facts are public, never full definitions or source prose. Rejected fields remain in the private master. All mappings remain source candidates, not verified translations.'
    manifest['concept_dispositions'] = dict(concept_dispositions)
    manifest['reading_filter'] = 'Bounded Japanese romanization-shaped tokens only; conservative omissions are not pronunciation judgments. Concept descriptions and non-lookup aliases are omitted.'
    output=Path(output);output.mkdir(parents=True,exist_ok=True)
    def atomic(name, content):
        fd, temporary = tempfile.mkstemp(prefix='.library-', dir=output)
        try:
            with os.fdopen(fd, 'wb') as stream:
                stream.write(content);stream.flush();os.fsync(stream.fileno())
            os.replace(temporary, output/name)
        finally:
            if os.path.exists(temporary): os.unlink(temporary)
    atomic('sword_library.json.gz', packed)
    atomic('sword_library_manifest.json', (json.dumps(manifest,ensure_ascii=False,indent=2)+'\n').encode())
    db.close()
    return manifest


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--master',required=True,type=Path)
    p.add_argument('--output',required=True,type=Path)
    p.add_argument('--primary_reference-pages',type=Path)
    p.add_argument('--source-map',type=Path,help='External private JSON mapping original identifiers to public pseudonyms')
    p.add_argument('--aligned-terms',type=Path,help='External image-reviewed bilingual JSONL; only bounded facts are exported')
    a=p.parse_args();mapping=json.loads(a.source_map.read_text()) if a.source_map else None
    print(json.dumps(build(a.master,a.output,a.primary_reference_pages,mapping,a.aligned_terms),ensure_ascii=False))

if __name__=='__main__':main()
