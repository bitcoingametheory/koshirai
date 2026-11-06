import unittest
from kanji_translator import parse,candidates
from kanji_translator.text_normalization import forms,forms_with_offsets,normalized
from kanji_translator.context_constraints import compare
class Core(unittest.TestCase):
 def test_unicode_literal_and_offsets(self):
  text="𠮷国葛\U000e0100e\u0301";value=forms(text);search,offsets=forms_with_offsets(text)
  self.assertEqual(value['raw_text'],text);self.assertEqual(search,normalized(text));self.assertEqual(len(search),len(offsets));self.assertEqual(offsets[-1],4)
 def test_native_bypasses_ocr_and_region_failure_is_local(self):
  def forbidden(*args):raise AssertionError('native OCR')
  result=parse({'kind':'regions','regions':[{'region_id':'ok','text':'𠮷備國'},{'region_id':'bad','text':'□'}]},ocr_adapter=forbidden)
  self.assertEqual([r['state'] for r in result['regions']],['literal','unresolved']);self.assertEqual(result['unresolved_regions'],1);self.assertIsNone(result['probability_correct'])
 def test_constraints(self):
  for field in ('generation','province','school_phase','role','era'):
   self.assertEqual(compare({field:'a'},{field:'b'}),([],[field]));self.assertEqual(compare({field:'a'},{}),([],[]))
  self.assertEqual(compare({'date_start':1400,'date_end':1450},{'date_start':1500,'date_end':1600}),([],['date_interval']))
  self.assertEqual(compare({'date_start':1400,'date_end':1550},{'date_start':1500,'date_end':1600}),(['date_interval'],[]))
 def test_candidate_ties_chains_and_self_book(self):
  witnesses=[{'raw_text':name,'source':'test','source_record_id':str(i),'evidence':{'original_chain_id':str(i),'source_work_id':'book'},'context':{'era':'永正','role':'smith','generation':'1'}} for i,name in enumerate(('國光','國吉'))]
  request={'pattern':'國?','witnesses':witnesses,'context':{'era':'永正','role':'smith','generation':'1'}}
  a=candidates(request);self.assertEqual(a['state'],'abstain');self.assertFalse(a['identity_accepted'])
  self.assertEqual(candidates({**request,'witnesses':witnesses+witnesses})['candidates'],a['candidates'])
  self.assertFalse(candidates({**request,'source_work_id':'book'})['candidates'])
  self.assertEqual(candidates({**request,'context':{'era':'慶長'}})['state'],'abstain')
 def test_unknown_native_preserves_original(self):
  r=parse({'text':'國□','witnesses':[{'raw_text':'國光','source':'retained','evidence':{'original_chain_id':'one'}}]})['regions'][0]
  self.assertEqual(r['raw_text'],'國□');self.assertEqual(r['reading_text'],'國□');self.assertTrue(r['mechanical']);self.assertFalse(r['identity_accepted'])
