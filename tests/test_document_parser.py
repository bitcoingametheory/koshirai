"""Synthetic regressions only; these fixtures are never persisted as human gold."""
import io,json,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
from PIL import Image,ImageDraw
from kanji_translator import parse
from kanji_translator.request_contracts import canonical,digest
from kanji_translator.reading_candidates import readings,romaji

class Pipeline(unittest.TestCase):
 def test_literal_ivs_and_retired_option_migration(self):
  text='English: 國\U000e0100光 123 original prose.'
  row=parse({'text':text})['enrichment']['regions'][0]
  self.assertEqual(row['literal_text'],text);self.assertIn('\U000e0100',row['search_form'])
  for key,value in [('vision_limit',1),('translation_config',{'enabled':True}),('enhancement_config',{'profile':'sword-lattice-v1'})]:
   with self.assertRaisesRegex(ValueError,'retired'):parse({'text':text,key:value})
 def test_readings_optional_and_unknown(self):
  a=parse({'text':'國光'});self.assertIsNone(a['enrichment']['regions'][0]['readings'])
  self.assertTrue(readings('國光',{})['abstained']);self.assertEqual(romaji('シンヨウ'),"shin'you");self.assertEqual(romaji('がっこう'),'gakkou');self.assertEqual(romaji('キャー'),'kyaa');self.assertIsNone(romaji('國'))
  value=readings('國光',{'entries':[{'start':0,'end':2,'literal':'國光','kana':'くにみつ','evidence':{'origin':'synthetic_candidate'}}]})
  self.assertEqual(value['alternatives'][0]['romaji'],'kunimitsu');self.assertEqual(value['review_state'],'proposed')
  with self.assertRaises(ValueError):readings('國光',{'entries':[{'start':0,'end':2,'literal':'国光'}]})
 def test_mixed_pdf_coverage_native_and_raster(self):
  import pymupdf
  with tempfile.TemporaryDirectory() as tmp:
   im=Image.new('RGB',(300,100),'white');ImageDraw.Draw(im).text((20,20),'SCAN WORDS',fill='black',font_size=28);buf=io.BytesIO();im.save(buf,format='PNG')
   doc=pymupdf.open();page=doc.new_page(width=400,height=400);page.insert_text((20,30),'Native English');page.insert_image(pymupdf.Rect(20,100,320,200),stream=buf.getvalue());p=Path(tmp)/'mixed.pdf';p.write_bytes(doc.tobytes());doc.close()
   result=parse({'kind':'pdf','path':str(p),'sha256':digest(p.read_bytes()),'cache_dir':tmp,'local_ocr':False,'use_master_lexicon':False})
   self.assertEqual(result['regions'][0]['origin'],'native_pdf');self.assertGreater(result['unresolved_regions'],0)
   self.assertTrue(result['native_payload']['coordinate_transform']['native_masks']);self.assertGreater(result['native_payload']['regions_detected'],0)
