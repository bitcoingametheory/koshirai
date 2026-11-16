import math
import pytest
from PIL import Image, ImageDraw
from kanji_translator import parse
from kanji_translator.request_contracts import digest
from kanji_translator.readers.ocr import ndlocr_lite as ndl


def test_default_ndl_preserves_literal_geometry_proposal_and_cache(tmp_path, monkeypatch):
    path = tmp_path / 'page.png'
    image = Image.new('RGB', (100, 100), 'white')
    ImageDraw.Draw(image).rectangle((20, 10, 39, 59), fill='black')
    image.save(path)
    pin = {'engine': 'fixture-NDL', 'model_sha256': 'a' * 64}
    monkeypatch.setattr(ndl, 'runtime', lambda config: ('unused', dict(pin)))
    calls = []
    def recognize(self, pixels, dimensions, config):
        calls.append(dimensions)
        return [{'box': [20, 10, 40, 60], 'text': '刄文'}]
    monkeypatch.setattr(ndl.NDLOCR, 'lines', recognize)
    request = {'kind': 'image', 'path': str(path), 'sha256': digest(path.read_bytes()),
               'cache_dir': str(tmp_path / 'cache'), 'use_master_lexicon': False,
               'lexical_config': {'enabled': False}}
    first = parse(request); second = parse(request)
    region = first['regions'][0]
    assert first['enrichment']['regions'][0]['literal_text'] == region['reading_text'] == '刄文'
    assert region['identity']['geometry'] == [20, 10, 40, 60]
    assert region['identity']['source_sha256'] == request['sha256']
    assert region['state'] == 'proposal' and not region['identity_accepted']
    assert region['ocr']['confidence'] is None
    assert first['metrics']['ocr_calls'] == second['metrics']['ocr_cache_hits'] == 1
    assert len(calls) == 1
    pin['model_sha256'] = 'b' * 64
    parse(request)
    assert len(calls) == 2


def test_ndl_validates_geometry_and_keeps_upstream_order():
    def line(text, x):
        return {'text': text, 'boundingBox': [[x, 1], [x, 8], [x + 2, 1], [x + 2, 8]]}
    raw = {'contents': [[line('國', 8), line('刄', 1)]]}
    assert [r['text'] for r in ndl.decode_lines(raw, [20, 20])] == ['國', '刄']
    raw['contents'][0][0]['boundingBox'][0][0] = math.nan
    with pytest.raises(ValueError, match='Invalid NDLOCR'):
        ndl.decode_lines(raw, [20, 20])


def test_missing_ndl_requires_explicit_fallback(tmp_path):
    with pytest.raises(RuntimeError, match='Run ./setup.sh --install-ocr'):
        ndl.runtime({'ndl_python': str(tmp_path / 'absent')})


def test_ndl_creates_output_directory_before_successful_subprocess(monkeypatch):
    import json
    from pathlib import Path
    monkeypatch.setattr(ndl, 'runtime', lambda config: ('fixture-python', {}))
    calls = []
    def run(argv, **kwargs):
        assert argv[:4] == ['fixture-python', '-B', '-m', 'ocr']
        output = Path(argv[argv.index('--output') + 1])
        assert output.is_dir()
        assert Path(argv[argv.index('--sourceimg') + 1]).read_bytes() == b'pixels'
        (output / 'page.json').write_text(json.dumps({'contents': [[{
            'text': '刄', 'boundingBox': [[1, 2], [3, 2], [3, 8], [1, 8]]}]]}))
        calls.append(output)
    monkeypatch.setattr(ndl.subprocess, 'run', run)
    assert [(r['box'],r['text']) for r in ndl.NDLOCR({}).lines(b'pixels', (10, 10), {})] == [([1,2,3,8],'刄')]
    assert len(calls) == 1 and not calls[0].exists()


def test_outside_line_is_explicit_unresolved_without_invented_box():
    valid={'text':'國光','boundingBox':[[1,1],[5,1],[5,8],[1,8]]}
    outside={'text':'原文保持','boundingBox':[[30,1],[35,1],[35,8],[30,8]]}
    raw={'contents':[[outside,valid]]};diagnostics=[]
    assert [(r['text'],r['box']) for r in ndl.decode_lines(raw,[20,20],diagnostics=diagnostics)]==[('國光',[1,1,5,8])]
    assert diagnostics[0]['text']=='原文保持'
    assert diagnostics[0]['original_geometry']==outside['boundingBox']
    assert diagnostics[0]['geometry'] is None and not diagnostics[0]['coverage_eligible']
    with pytest.raises(ValueError,match='outside the image'):ndl.decode_lines(raw,[20,20])
    # A partially overlapping box is still invalid; clipping would invent evidence.
    outside['boundingBox']=[[-1,1],[5,1],[5,8],[-1,8]]
    diagnostics=[]
    assert len(ndl.decode_lines(raw,[20,20],diagnostics=diagnostics))==1
    assert diagnostics[0]['original_geometry'][0]==[-1,1]
    valid['tile_bbox']=[10,5,20,20]
    assert ndl.decode_lines({'contents':[[valid]]},[30,30])[0]['box']==[11,6,15,13]
    valid['boundingBox'][0][0]=11
    with pytest.raises(ValueError,match='outside NDLOCR tile'):ndl.decode_lines({'contents':[[valid]]},[30,30])


def test_page_preserves_unlocated_text_identity_and_cache(tmp_path,monkeypatch):
    import json
    from pathlib import Path
    image=Image.new('RGB',(100,100),'white');ImageDraw.Draw(image).rectangle((1,1,5,8),fill='black')
    path=tmp_path/'image.png';image.save(path)
    monkeypatch.setattr(ndl,'runtime',lambda config:('fixture',{'engine':'fixture'}))
    calls=[]
    def execute(argv,**kwargs):
        calls.append(argv)
        output=Path(argv[argv.index('--output')+1])
        (output/'page.json').write_text(json.dumps({'contents':[[
            {'text':'國光','boundingBox':[[1,1],[5,1],[5,8],[1,8]]},
            {'text':'原文保持','boundingBox':[[130,1],[135,1],[135,8],[130,8]]}]]}))
    monkeypatch.setattr(ndl.subprocess,'run',execute)
    request={'kind':'image','path':str(path),'sha256':digest(path.read_bytes()),'cache_dir':str(tmp_path/'cache'),
             'lexical_config':{'enabled':False},'local_ocr':True}
    first=parse(request);again=parse(request)
    assert first['regions'][0]['reading_text']=='國光'
    evidence=first['native_payload']['unlocated_ocr_regions'][0]
    assert evidence['text']=='原文保持' and evidence['identity']['source_sha256']==request['sha256']
    assert evidence['original_geometry']==[[130,1],[135,1],[135,8],[130,8]]
    assert evidence['geometry'] is None and not evidence['crop_created']
    assert first['native_payload']['region_inventory_state']=='requires_review'
    assert again['native_payload']['unlocated_ocr_regions']==first['native_payload']['unlocated_ocr_regions']
    assert len(calls)==1
    page=ndl.NDLOCR({}).read(image,'page')
    assert page['text']=='國光\n原文保持' and len(page['lines'])==1
    assert page['geometry_diagnostics'][0]['geometry'] is None


def test_english_route_is_explicit_and_preserves_tsv_words(tmp_path,monkeypatch):
    from types import SimpleNamespace
    from kanji_translator.readers import ocr
    assert ocr.backend({})=='ndl' and ocr.backend({'language':'mixed'})=='ndl'
    assert ocr.backend({'language':'en'})=='english'
    with pytest.raises(ValueError):ocr.backend({'backend':'english','language':'ja'})
    binary=tmp_path/'engine';binary.write_bytes(b'synthetic binary');(tmp_path/'eng.traineddata').write_bytes(b'synthetic model')
    monkeypatch.setattr(ocr.shutil,'which',lambda _:str(binary))
    tsv='level\tpage_num\tblock_num\tpar_num\tline_num\tword_num\tleft\ttop\twidth\theight\tconf\ttext\n'
    tsv+='5\t1\t1\t1\t1\t1\t1\t2\t10\t8\t92.5\tNorifusa\n'
    tsv+='5\t1\t1\t1\t1\t2\t13\t2\t8\t8\t80\tutsuri\n'
    tsv+='5\t1\t1\t1\t2\t1\t-1\t2\t10\t8\t20\tunlocated\n'
    def execute(argv,**kwargs):
        return SimpleNamespace(stdout='synthetic version\n' if '--version' in argv else tsv)
    monkeypatch.setattr(ocr.subprocess,'run',execute)
    engine=ocr.local_engine({'language':'en','tessdata':str(tmp_path)})
    rows=engine.lines(b'pixels',(100,100),{})
    assert rows[0]['text']=='Norifusa utsuri' and rows[0]['box']==[1,2,21,10]
    assert rows[0]['words'][0]['confidence']==92.5
    assert engine.geometry_diagnostics[0]['text']=='unlocated'
    assert not engine.prediction(rows[0]['text'])['accuracy_qualified']
