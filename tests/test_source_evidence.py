import copy,json,tempfile,unittest
from pathlib import Path
from kanji_translator import parse
from kanji_translator.request_contracts import canonical,digest
from kanji_translator.source_evidence import reviewed_reuse,export_reviewed
from kanji_translator.result_cache import DEPENDENCIES,cache_key,write_cache,read_cache
class Evidence(unittest.TestCase):
 # Synthetic review records test the contract only; they are never retained labels.
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.root=Path(self.tmp.name)
  self.identity={'source_sha256':'a'*64,'crop_sha256':'b'*64,'locator':'page:1:region:2','style':'woodblock','geometry':[0,0,10,10],'orientation':'vertical'}
  self.record={**self.identity,'literal_text':'國光','original_text':'國□','corrections':[{'before':'□','after':'光','review_record_id':'synthetic-review'}],'label_origin':'source_review','split_group':'synthetic-work-edition','split':'test','source_review':{'method':'source_pixels','reviewer_kind':'human','reviewer_id':'synthetic-reviewer','review_record_id':'synthetic-review',**{k:self.identity[k] for k in ('source_sha256','crop_sha256','locator')},'decision':'source_verified'}}
 def tearDown(self):self.tmp.cleanup()
 def spec(self,record=None):
  raw=canonical(record or self.record);p=self.root/(digest(raw)+'.json');p.write_bytes(raw);return {'path':str(p),'sha256':digest(raw),'identity':self.identity}
 def test_retained_review_binding_and_no_flag_promotion(self):
  spec=self.spec();self.assertTrue(reviewed_reuse(spec,self.identity)['reusable'])
  with self.assertRaises(ValueError):reviewed_reuse({**spec,'sha256':'0'*64},self.identity)
  original=Path(spec['path']).read_bytes();Path(spec['path']).write_bytes(original+b' ')
  with self.assertRaises(ValueError):reviewed_reuse(spec,self.identity)
  Path(spec['path']).write_bytes(original)
  for field in self.identity:
   identity={**self.identity,field:'changed'};self.assertFalse(reviewed_reuse(spec,identity)['reusable'])
  for review in ({},{**self.record['source_review'],'reviewer_kind':'model'},{**self.record['source_review'],'method':'consensus'}):
   record={**self.record,'verified':True,'source_review':review};self.assertFalse(reviewed_reuse(self.spec(record),self.identity)['reusable'])
 def test_review_replay_preserves_original(self):
  request={'kind':'regions','regions':[{'region_id':'x','text':'國□','identity':self.identity,'review':self.spec()}]}
  row=parse(request)['regions'][0];self.assertEqual(row['state'],'source_verified');self.assertEqual(row['raw_text'],'國□');self.assertEqual(row['reading_text'],'國光');self.assertEqual(row['review']['record']['corrections'],self.record['corrections'])
 def test_cache_all_dependencies_and_corruption(self):
  deps={k:None for k in DEPENDENCIES};deps.update(self.identity);key=cache_key(deps)
  for k in DEPENDENCIES:self.assertNotEqual(key,cache_key({**deps,k:'changed'}),k)
  write_cache(self.root,deps,{'text':'','state':'unavailable'});self.assertEqual(read_cache(self.root,deps)['state'],'unavailable')
  (self.root/(key+'.json')).write_text('{}')
  with self.assertRaises(ValueError):read_cache(self.root,deps)
 def test_ocr_replay_and_proposal_only(self):
  crop=b'synthetic-raster';p=self.root/'crop';p.write_bytes(crop);identity={**self.identity,'crop_sha256':digest(crop)};calls=[]
  request={'kind':'regions','regions':[{'region_id':'bad','text':'□','crop':str(p),'identity':identity}],'cache_dir':str(self.root/'cache'),'adapter_version':'synthetic-v1'}
  def adapter(*args):calls.append(1);return '國光'
  a=parse(request,ocr_adapter=adapter);b=parse(request,ocr_adapter=adapter);self.assertEqual({k:v for k,v in a.items() if k!='metrics'},{k:v for k,v in b.items() if k!='metrics'});self.assertEqual(b['metrics']['ocr_cache_hits'],1);self.assertEqual(b['metrics']['ocr_calls'],0);self.assertEqual(len(calls),1);self.assertEqual(a['regions'][0]['state'],'proposal');self.assertFalse(a['regions'][0]['identity_accepted'])
  request['adapter_version']='synthetic-v2';parse(request,ocr_adapter=adapter);self.assertEqual(len(calls),2)
 def test_export_rejects_ai_and_split_leakage(self):
  valid=self.spec();export=export_reviewed({'records':[valid,valid]});self.assertEqual(len(export['records']),1);self.assertFalse(export['training_run'])
  ai={**self.record,'label_origin':'model'}
  with self.assertRaises(ValueError):export_reviewed({'records':[self.spec(ai)]})
  unreviewed={**self.record,'verified':True,'source_review':{}}
  self.assertFalse(export_reviewed({'records':[self.spec(unreviewed)]})['records'])
  other={**self.record,'split':'train','split_group':'different-group'}
  with self.assertRaises(ValueError):export_reviewed({'records':[valid,self.spec(other)]})
