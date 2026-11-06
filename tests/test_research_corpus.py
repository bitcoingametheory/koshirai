"""Actual scan receipts, immutable imports, explicit reviews and local lookup."""
import hashlib,json,os,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
from kanji_translator import research_corpus as corpus
from kanji_translator.sword_library import lookup
class Corpus(unittest.TestCase):
 def test_private_idempotent_review_conflict_and_source_hash(self):
  with tempfile.TemporaryDirectory() as tmp,patch.dict(os.environ,KANJI_DATA_DIR=tmp):
   root=Path(tmp);raw=root/'raw';raw.mkdir();image=raw/'1.png';image.write_bytes(b'fixture source');sha=hashlib.sha256(image.read_bytes()).hexdigest()
   results=root/'results.jsonl';results.write_text(json.dumps({'file':'1.png','page':1,'source_sha256':sha,'result':{'enrichment':{'regions':[{'region_id':'r1','literal_text':'國光','identity':{'source_sha256':sha}}]}}})+'\n')
   request={'source_dir':str(raw),'results':str(results)}
   self.assertEqual(corpus.ingest(request)['added'],1);self.assertEqual(corpus.ingest(request)['existing'],1)
   self.assertEqual(lookup('國光')['local_mappings'],[])
   obs=corpus.inspect({})['observations'][0]
   review={'observation_id':obs['id'],'literal':'國光','reading':'Kunimitsu','english':None,'decision':'accept','reviewer_id':'fixture-reviewer','attestation':'source_pixels_and_mapping_review_completed'}
   with self.assertRaises(ValueError):corpus.review({**review,'attestation':None})
   first=corpus.review(review);self.assertEqual(first,corpus.review(review));revision=corpus.revision()
   self.assertEqual(lookup('Kunimitsu')['local_mappings'][0]['original_text'],'國光')
   second=corpus.review({**review,'reading':'Kunihiro'})
   self.assertNotEqual(revision,corpus.revision())
   self.assertTrue(lookup('國光')['local_mappings'][0]['conflict'])
   corpus.review({**review,'reading':'Kunihiro','supersedes':first['review_id']})
   self.assertTrue(all(r['reading']=='Kunihiro' for r in lookup('國光')['local_mappings']))
   image.write_bytes(b'changed')
   with self.assertRaises(ValueError):corpus.ingest(request)
   with self.assertRaises(ValueError):corpus.review(review)
 def test_escape_and_unknown_are_not_accepted(self):
  with tempfile.TemporaryDirectory() as tmp,patch.dict(os.environ,KANJI_DATA_DIR=tmp):
   root=Path(tmp);raw=root/'raw';raw.mkdir();f=root/'source';f.write_bytes(b'raw');r=root/'result';r.write_text(json.dumps({'file':'../source','source_sha256':hashlib.sha256(b'raw').hexdigest()})+'\n')
   with self.assertRaises(ValueError):corpus.ingest({'source_dir':str(raw),'results':str(r)})

 def test_enhancement_does_not_replace_original_observation(self):
  with tempfile.TemporaryDirectory() as tmp,patch.dict(os.environ,KANJI_DATA_DIR=tmp):
   root=Path(tmp);raw=root/'raw';raw.mkdir();source=raw/'page.png';source.write_bytes(b'pixels')
   sha=hashlib.sha256(source.read_bytes()).hexdigest();receipt=root/'scan.jsonl'
   receipt.write_text(json.dumps({'file':'page.png','page':1,'source_sha256':sha,'result':{'enrichment':{'regions':[
    {'region_id':'r1','original_text':'wrong','literal_text':'國光','enhancement':{'state':'proposal'}}]}}})+'\n')
   req={'source_dir':str(raw),'results':str(receipt)}
   assert corpus.ingest(req)['added']==1
   assert corpus.ingest(req)['existing']==1
   row=corpus.inspect({})['observations'][0]
   assert row['original_text']=='wrong' and row['enhanced_text']=='國光'
