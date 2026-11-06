import json,sys,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
from kanji_translator.request_contracts import digest,canonical
from kanji_translator.source_evidence import export_reviewed
from kanji_translator.reviewed_readings import record_review
class Review(unittest.TestCase):
 def test_review_integrity_export_and_profile_gate(self):
  # Synthetic fixture only: no fabricated human labels are persisted.
  with tempfile.TemporaryDirectory() as temporary:
   root=Path(temporary);source=root/'source';source.write_bytes(b'original');crop=root/'crop';crop.write_bytes(b'crop')
   identity={'source_sha256':digest(b'original'),'crop_sha256':digest(b'crop'),'locator':'p1','style':'print','geometry':[0,0,1,1],'orientation':'horizontal'}
   record={**identity,'literal_text':'國','original_text':'□','corrections':[],'label_origin':'source_review','split_group':'synthetic-work','split':'test','source_review':{'method':'source_pixels','reviewer_kind':'human','reviewer_id':'synthetic','review_record_id':'synthetic',**{k:identity[k] for k in ('source_sha256','crop_sha256','locator')},'decision':'source_verified'}}
   request={'record':record,'source_path':str(source),'crop':str(crop),'output_dir':str(root),'attestation':'source_pixels_review_completed'}
   with self.assertRaisesRegex(ValueError,'canonical reviews'):record_review(request)
   source.write_bytes(b'changed')
   with self.assertRaisesRegex(ValueError,'original source'):record_review(request)
   label=root/'label.json';label.write_bytes(canonical(record));spec={'path':str(label),'sha256':digest(label.read_bytes()),'identity':identity,'crop':str(crop)}
   exported=export_reviewed({'records':[spec]});self.assertEqual(exported['records'][0]['literal_text'],'國');self.assertFalse(exported['training_run'])
