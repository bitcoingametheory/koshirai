"""Bilingual fact export excludes passages and validates exact source labels."""
import copy
import json
import pytest
from kanji_translator.glossary_bridge import build_aligned_terms


@pytest.fixture
def alignment():
    return {'literal': '無地肌', 'unicode_codepoints': ['U+7121', 'U+5730', 'U+808C'],
            'reading_printed': 'Muji-hada', 'english_summary': 'apparently grainless fine grain',
            'raw_ocr_changed': False, 'review_status': 'AI_source_image_reviewed_provisional_not_expert',
            'private_passage': 'THIS MUST NOT BE EXPORTED',
            'japanese': {'pdf_page': 12, 'printed_page': 10, 'label_line_id': 3,
                         'raw_label': '◎無地肌', 'source_sha256': 'a'*64, 'image_sha256': 'b'*64},
            'english': {'edition': 1997, 'label_printed_page': 20, 'definition_printed_page': 19,
                        'definition_payload_sha256': 'c'*64, 'definition_image_sha256': 'd'*64,
                        'label_image_sha256': 'e'*64, 'retained_paragraph': 'PRIVATE SOURCE PASSAGE'}}


def export(tmp_path, row):
    path = tmp_path/'alignments.jsonl'
    path.write_text(json.dumps(row, ensure_ascii=False)+'\n')
    return build_aligned_terms(path)


def test_only_bounded_facts_leave_the_private_alignment(tmp_path, alignment):
    saved = copy.deepcopy(alignment)
    row, = export(tmp_path, alignment)
    assert alignment == saved
    assert row['literal'] == '無地肌'
    assert row['citations'][0]['literal_span'] == [1, 4]
    assert row['citations'][1]['printed_page'] == 19
    assert row['citations'][1]['label_printed_page'] == 20
    assert 'PRIVATE' not in json.dumps(row) and 'MUST NOT' not in json.dumps(row)


@pytest.mark.parametrize('key,value', [('raw_ocr_changed', True), ('review_status', 'unreviewed'),
                                      ('english_summary', 'This is an entire definition that must remain private.'),
                                      ('unicode_codepoints', ['U+7121'])])
def test_unreviewed_or_nonlexical_alignments_are_rejected(tmp_path, alignment, key, value):
    alignment[key] = value
    with pytest.raises(ValueError):
        export(tmp_path, alignment)


def test_complete_label_and_page_hash_are_required(tmp_path, alignment):
    alignment['japanese']['raw_label'] = '小無地肌'
    with pytest.raises(ValueError, match='complete literal'):
        export(tmp_path, alignment)
    alignment['japanese']['raw_label'] = '無地肌'
    alignment['english']['label_image_sha256'] = 'not-a-hash'
    with pytest.raises(ValueError, match='sha256'):
        export(tmp_path, alignment)
