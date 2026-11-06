"""Saved OCR preserves native source identity, lines and separate derivatives."""
import copy
import hashlib
import json
import pytest
from kanji_translator import parse


def request_for(tmp_path, snapshot):
    path = tmp_path/'snapshot.json'
    raw = json.dumps(snapshot, ensure_ascii=False).encode()
    path.write_bytes(raw)
    return {'kind': 'library_ocr', 'path': str(path), 'sha256': hashlib.sha256(raw).hexdigest(),
            'source_id': 7, 'page': 2, 'lexical_config': {'enabled': False}}


@pytest.fixture
def snapshot():
    return {'source': {'id': 7, 'sha256': 'a'*64, 'title': 'Synthetic fixture'},
            'pages': [{'source_id': 7, 'page': 2, 'printed_page': 1, 'engine': 'fixture-ocr-v1',
                       'text_raw': '小杢目肌が見える。\n雲\n次\n',
                       'text': 'Separate corrected text', 'text_ordered': 'Separate ordered text',
                       'lines': [{'t': text, 'b': [[x, 0], [x, 100], [x+10, 0], [x+10, 100]], 'v': True, 'c': .8}
                                 for x, text in [(40, '小杢目肌が見える。'), (20, '雲'), (0, '次')]]}]}


def test_import_preserves_raw_and_never_joins_unrelated_lines(tmp_path, snapshot):
    original = copy.deepcopy(snapshot)
    result = parse(request_for(tmp_path, snapshot))
    assert snapshot == original
    assert result['raw_ndl_transcript'] == snapshot['pages'][0]['text_raw']
    assert result['native_payload']['page'] == snapshot['pages'][0]
    assert result['metrics']['ocr_calls'] == 0
    assert result['semantic_blocks'] == []
    assert not any(m['literal'] == '雲次' for m in result['semantic_mentions'])
    mention = next(m for m in result['semantic_mentions'] if m['literal'] == '小杢目肌')
    assert mention['source_sha256'] == 'a'*64
    assert mention['geometry'] == [40, 0, 50, 100]
    assert mention['selection']['english'] == 'small burl-pattern grain'
    identity = result['regions'][0]['identity']
    assert identity['pdf_page'] == 2 and identity['printed_page'] == 1
    assert identity['engine'] == 'fixture-ocr-v1'
    assert identity['native_polygon'] == snapshot['pages'][0]['lines'][0]['b']


def test_import_rejects_mismatched_identity_and_duplicate_pages(tmp_path, snapshot):
    request = request_for(tmp_path, snapshot)
    for change in ({'source_id': 8}, {'page': 0}, {'page': True}, {'sha256': 'b'*64}):
        with pytest.raises(ValueError):
            parse({**request, **change})
    snapshot['pages'] *= 2
    with pytest.raises(ValueError, match='exactly one'):
        parse(request_for(tmp_path, snapshot))


@pytest.mark.parametrize('points', [[], [[0, 0]]*4, [[0, 0], [0, 10], [float('nan'), 0], [10, 10]]])
def test_import_rejects_invalid_geometry(tmp_path, snapshot, points):
    snapshot['pages'][0]['lines'][0]['b'] = points
    with pytest.raises(ValueError):
        parse(request_for(tmp_path, snapshot))
