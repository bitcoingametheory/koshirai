"""Bounded real image/PDF/TIFF traversal with the existing OCR interface."""
import json,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
from PIL import Image,ImageDraw
from kanji_translator.scan_folder import scan

class Folder(unittest.TestCase):
 def test_page_order_frames_and_outputs(self):
  import pymupdf
  with tempfile.TemporaryDirectory() as tmp:
   root=Path(tmp);source=root/'input';source.mkdir()
   image=Image.new('RGB',(320,100),'white');ImageDraw.Draw(image).text((20,20),'SWORD',fill='black',font_size=30)
   image.save(source/'page10.png');image.save(source/'page2.tiff',save_all=True,append_images=[image])
   doc=pymupdf.open();doc.new_page().insert_text((50,50),'SWORD');doc.save(source/'page3.pdf');doc.close()
   config={'image_config':{'page_ocr':False},'local_ocr':False,'cache_dir':str(root/'cache'),'lexical_config':{'enabled':False},'use_master_lexicon':False}
   # Use the production parser/layout and one deterministic OCR interface.
   from kanji_translator import parse
   config['adapter_version']='synthetic'
   with patch('kanji_translator.parse',side_effect=lambda req:parse(req,ocr_adapter=lambda *a:'SWORD')):
    summary=scan(source,root/'out',config=config)
   self.assertEqual(summary['errors'],0);self.assertEqual(summary['pages'],4)
   rows=[json.loads(line) for line in (root/'out/results.jsonl').read_text().splitlines()]
   self.assertEqual([(r['file'],r['page']) for r in rows],[('page2.tiff',1),('page2.tiff',2),('page3.pdf',1),('page10.png',1)])
   self.assertTrue(all(r['result']['regions'] for r in rows))
   self.assertTrue((root/'out/unresolved.jsonl').is_file())
   self.assertIn('SWORD',(root/'out/text.txt').read_text())
   self.assertIn('page3.pdf page 1',(root/'out/raw_ndl.txt').read_text())
   bounded=scan(source,root/'limited',config=config,max_pages=1)
   self.assertEqual(bounded['pages'],1);self.assertTrue(bounded['stopped_at_limit'])



def test_folder_keeps_unlocated_ocr_as_unresolved_evidence(tmp_path):
    source=tmp_path/'input';source.mkdir();Image.new('RGB',(10,10),'white').save(source/'page.png')
    evidence={'text':'原文保持','original_geometry':[[20,1],[25,1],[25,8],[20,8]],'geometry':None,'state':'unresolved'}
    result={'regions':[],'raw_ndl_transcript':'國光','enhanced_transcript':'國光',
            'enrichment':{'regions':[]},'native_payload':{'unlocated_ocr_regions':[evidence]}}
    with patch('kanji_translator.parse',return_value=result):summary=scan(source,tmp_path/'out')
    assert summary['errors']==0 and summary['pages']==1
    assert summary['unlocated_ocr_regions']==summary['unresolved_regions']==1
    rows=[json.loads(line) for line in (tmp_path/'out/unresolved.jsonl').read_text().splitlines()]
    assert rows[0]['state']=='requires_review' and rows[0]['region']==evidence
    assert json.loads((tmp_path/'out/results.jsonl').read_text())['result']['native_payload']['unlocated_ocr_regions']==[evidence]
