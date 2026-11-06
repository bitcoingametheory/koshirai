"""Completeness, source-prose exclusion and normal public sword lookup."""
import json,sqlite3,tempfile,unittest
from pathlib import Path
from kanji_translator.sword_library import bundle,lookup,install
from kanji_translator.dictionary_lookup import LexicalReader

class Sword(unittest.TestCase):
 def test_private_source_map_preserves_lookup_text_and_normalizes_linked_ids(self):
  from kanji_translator.build_sword_library import remap_source_text
  mapping={'private_work':'primary_reference'}
  record={'source':'private_work','entry_id':'private_work:12','literal':'雲次','printed_romaji':'Unji'}
  value=json.loads(remap_source_text(json.dumps(record,ensure_ascii=False),mapping))
  self.assertEqual(value,{'source':'primary_reference','entry_id':'primary_reference:12','literal':'雲次','printed_romaji':'Unji'})
  self.assertEqual(remap_source_text(12,mapping),12)
  with self.assertRaises(ValueError):remap_source_text('text',{'private_work':''})
 def test_rebuild_applies_private_map_before_exporting_linked_records(self):
  import gzip
  from kanji_translator.build_sword_library import build
  with tempfile.TemporaryDirectory() as tmp:
   root=Path(tmp);master=root/'master.sqlite3'
   with sqlite3.connect(master) as db:
    for statement in (
     'CREATE TABLE sword_concepts(concept_id,payload_json)',
     'CREATE TABLE sword_concept_aliases(alias_id,payload_json)',
     'CREATE TABLE sword_concept_evidence(entry_id,concept_id,payload_json)',
     'CREATE TABLE domain_entries(source,entry_id,literal,printed_romaji,english,role)',
     'CREATE TABLE domain_spellings(literal,source,entry_id)',
     'CREATE TABLE witnesses(id,search_form,source,kind,english,has_unknown,evidence_json)',
     'CREATE TABLE domain_assertions(witness_id,printed_romaji,review_state,english)',
     'CREATE TABLE japanese_variant_relations(literal,target,relation,source)',
     'CREATE TABLE glyph_sequences(sequence,collection,glyph,source)',
     'CREATE TABLE unicode_properties(source,codepoint,property,value)',
     'CREATE TABLE mj_characters(mj_id,payload_json)',
    ):db.execute(statement)
    db.execute('INSERT INTO domain_entries VALUES(?,?,?,?,?,?)',('private_work','private_work:1','雲次','Unji',None,'smith_name_candidate'))
    db.execute('INSERT INTO domain_spellings VALUES(?,?,?)',('雲次','private_work','private_work:1'))
    db.execute('INSERT INTO witnesses VALUES(?,?,?,?,?,?,?)',(1,'雲次','private_work','smith_source_record','Unji',0,json.dumps({'locator':'private_work:page:1'})))
   manifest=build(master,root/'output',source_map={'private_work':'primary_reference'})
   raw=gzip.decompress((root/'output/sword_library.json.gz').read_bytes());data=json.loads(raw)
   self.assertNotIn(b'private_work',raw)
   self.assertEqual(manifest['term_sources'],{'primary_reference':1})
   self.assertEqual(data['terms'][0]['literal'],'雲次')
   self.assertEqual(data['spellings'][0]['entry_id'],'primary_reference:1')
   self.assertEqual(data['names'][0]['citations'][0]['locator'],'primary_reference:page:1')
 def test_complete_safe_linked_bundle(self):
  data,manifest=bundle()
  self.assertEqual(manifest['counts'],{k:len(v) for k,v in data.items() if isinstance(v,list)})
  self.assertEqual(len(data['terms'])-manifest['glossary_bridges']['records'],3263)
  self.assertEqual(sum(r['occurrences'] for r in data['forms']+data['names']),401979)
  self.assertEqual(sum(c['input'] for c in manifest['coverage']),401990)
  for cohort in manifest['coverage']:
   self.assertEqual(cohort['input'],sum(n for k,n in cohort.items() if k.startswith('rejected_') or k=='exported'))
  self.assertEqual({r['source'] for r in data['names']},{'club','nwatch','primary_reference-register'})
  self.assertEqual(len({r['candidate_id'] for r in data['names']}),len(data['names']))
  self.assertTrue(all(r['identity_accepted'] is False for r in data['names']+data['variants']))
  concepts={r['concept_id'] for r in data['concepts']}
  terms={(r['source'],r['entry_id']) for r in data['terms']}
  self.assertTrue(all(a['concept_id'] in concepts for a in data['aliases']+data['concept_links']))
  self.assertTrue(all((s['source'],s['entry_id']) in terms for s in data['spellings']))
  self.assertTrue(all(set(t['concept_ids'])<=concepts for t in data['terms']))
  self.assertTrue(any(t['concept_ids'] for t in data['terms']))
  for kind,rows in data.items():
   if not isinstance(rows,list):continue
   for row in rows:
    optional=set(manifest.get('optional_record_fields',{}).get(kind,[]))
    self.assertLessEqual(set(row),set(manifest['record_fields'][kind]))
    self.assertLessEqual(set(manifest['record_fields'][kind])-optional,set(row))
  self.assertTrue(all('definition' not in r for r in data['concepts']))
  encoded=json.dumps(data,ensure_ascii=False)
  for field in ('definition_raw','entry_text_raw','payload_json','provenance_json','source_pdf','original_evidence'):
   self.assertTrue(field not in encoded,field)
  for source,count in manifest['term_sources'].items():self.assertEqual(sum(t['source']==source for t in data['terms']),count)
 def test_representative_lookup_and_external_import(self):
  self.assertTrue(lookup('虻の目')['assertions'])
  self.assertTrue(lookup('bo-hi')['concepts'])
  self.assertTrue(lookup('國光')['smith_name_candidates'])
  self.assertFalse(lookup('国□')['smith_name_candidates'])
  with tempfile.TemporaryDirectory() as tmp:
   p=Path(tmp)/'lookup.sqlite3';first=install(p);self.assertEqual(first,install(p))
   with sqlite3.connect(p) as db:self.assertEqual(db.execute('select count(*) from sword_bundle').fetchone()[0],sum(first['counts'].values()))
   reader=LexicalReader(p)
   try:self.assertTrue(reader.domain('虻の目')['assertions'])
   finally:reader.close()

 def test_character_facts_and_reading_filters(self):
  from kanji_translator.build_sword_library import roman,literal
  self.assertIsNone(roman('the term aikuchi-koshirae'))
  self.assertEqual(roman('Kōzuke no Suke'),'Kōzuke no Suke')
  self.assertEqual(roman("Bitchū no Kami Masamitsu"),"Bitchū no Kami Masamitsu")
  self.assertEqual(roman("Shin'ichi"),"Shin'ichi")
  self.assertIsNone(roman('chapterdiscussion duringKoto noKami Masamitsu'))
  self.assertIsNone(roman('some laterauthorsused thename Masamitsu'))
  self.assertIsNone(literal('国□'))
  self.assertTrue(lookup('国')['unicode_properties'])
  self.assertTrue(lookup('国')['character_relations'])
  self.assertTrue(lookup('国')['character_forms'])

 def test_source_descriptions_are_not_public_lookup_labels(self):
  from kanji_translator.build_sword_library import roman,literal
  data,manifest=bundle()
  self.assertGreater(manifest['concept_dispositions']['aliases_omitted_non_lookup_text'],0)
  for row in data['concepts']:
   self.assertTrue(row['label_en'] is None or roman(row['label_en']))
  for row in data['aliases']:
   self.assertTrue(literal(row['form']) or roman(row['form']))
  for row in data['terms']+data['names']+data['forms']:
   self.assertTrue(row['printed_romaji'] is None or roman(row['printed_romaji']))

 def test_english_facts_and_all_mapping_field_dispositions(self):
  data,manifest=bundle()
  self.assertTrue(any(row.get('english') for row in data['terms']))
  self.assertTrue(any(row.get('english') for row in data['forms']))
  fields=manifest['mapping_fields']
  for cohort in manifest['coverage']:
   prefix='witnesses:'+cohort['source']+':'+cohort['kind']+':'
   for name in ('kanji','romaji','english'):
    self.assertEqual(sum(fields[prefix+name].values()),cohort['input'])
  from kanji_translator.build_sword_library import english_gloss
  self.assertEqual(english_gloss('Hollyhock.'),'Hollyhock')
  self.assertIsNone(english_gloss('The very tip of the bōshi temper line.'))
  self.assertTrue(lookup('Hollyhock')['assertions'])
