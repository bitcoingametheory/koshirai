import io,json,sys,tempfile,unittest,subprocess,os
from pathlib import Path
from PIL import Image,ImageDraw
from kanji_translator import parse,candidates
from kanji_translator.request_contracts import digest
class Images(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.root=Path(self.tmp.name)
  im=Image.new('RGB',(500,140),'white');ImageDraw.Draw(im).text((30,50),'SWORD TEST',fill='black',font_size=36);self.raw=io.BytesIO();im.save(self.raw,format='PNG');self.raw=self.raw.getvalue();self.p=self.root/'page.png';self.p.write_bytes(self.raw)
 def tearDown(self):self.tmp.cleanup()
 def request(self):return {'kind':'image','path':str(self.p),'sha256':digest(self.raw),'image_config':{'page_ocr':False,'orientation':'horizontal'},'local_ocr':False,'cache_dir':str(self.root/'cache'),'use_master_lexicon':False}
 def test_blank_negative_and_scanned_pdf_native_bypass(self):
  import fitz
  blank=Image.new('RGB',(200,100),'white');buf=io.BytesIO();blank.save(buf,format='PNG');self.p.write_bytes(buf.getvalue());r=self.request();r['sha256']=digest(self.p.read_bytes());self.assertEqual(parse(r)['regions'],[])
  doc=fitz.open();page=doc.new_page(width=500,height=140);page.insert_image(page.rect,stream=self.raw);pdf=self.root/'scan.pdf';pdf.write_bytes(doc.tobytes());doc.close();r.update(kind='pdf',path=str(pdf),sha256=digest(pdf.read_bytes()));result=parse(r);self.assertEqual(result['native_payload']['route'],'rendered_pdf');self.assertTrue(result['regions'])
  doc=fitz.open();doc.new_page().insert_text((50,50),'native Unicode');pdf.write_bytes(doc.tobytes());doc.close();r['sha256']=digest(pdf.read_bytes());result=parse(r,ocr_adapter=lambda *a:self.fail('native OCR'));self.assertEqual(result['regions'][0]['origin'],'native_pdf')
 def test_exact_lookup_abstains_on_missing_characters(self):
  witnesses=[{'raw_text':'國光','source':'test','source_record_id':'1','context':{'province':'備前'},'evidence':{'original_chain_id':'a'}},{'raw_text':'國廣','source':'test','source_record_id':'2','context':{'province':'山城'},'evidence':{'original_chain_id':'b'}}]
  for context in ({'hints':{'province':'備前'}},{'province':'備前'}):
   result=candidates({'pattern':'國□','witnesses':witnesses,'context':context})
   self.assertEqual(result['state'],'abstain');self.assertIsNone(result['proposed_reading']);self.assertEqual(result['candidates'],[])
  exact=candidates({'pattern':'國光','witnesses':witnesses,'context':{'province':'山城'}})
  self.assertEqual(len(exact['candidates']),1)
  self.assertEqual(exact['candidates'][0]['candidate'],'國光')
  self.assertIsNone(exact['proposed_reading']);self.assertFalse(exact['identity_accepted'])

