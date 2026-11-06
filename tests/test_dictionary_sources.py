"""Synthetic fixtures verify restriction handling and atomic public builds."""
import gzip,json,sqlite3
from pathlib import Path
import pytest
from kanji_translator.dictionary_sources import build
from kanji_translator.dictionary_lookup import LexicalReader,read

@pytest.fixture
def public_db(tmp_path):
    content={
        'jmdict':'''<JMdict><entry><ent_seq>1</ent_seq><k_ele><keb>学校</keb></k_ele><k_ele><keb>学交</keb></k_ele><r_ele><reb>がっこう</reb><re_restr>学校</re_restr></r_ele><r_ele><reb>がくこう</reb><re_restr>学交</re_restr></r_ele><sense><stagk>学校</stagk><stagr>がっこう</stagr><pos>synthetic noun</pos><gloss>synthetic school</gloss></sense><sense><stagk>学交</stagk><stagr>がくこう</stagr><gloss>synthetic alternative</gloss></sense></entry><entry><ent_seq>2</ent_seq><r_ele><reb>ありがとう</reb><re_nokanji/></r_ele><sense><gloss>synthetic thanks</gloss></sense></entry></JMdict>''',
        'jmnedict':'''<JMnedict><entry><ent_seq>3</ent_seq><k_ele><keb>東京</keb></k_ele><r_ele><reb>とうきょう</reb></r_ele><trans><name_type>place</name_type><trans_det>synthetic place</trans_det></trans></entry></JMnedict>''',
        'kanjidic2':'''<kanjidic2><character><literal>学</literal><codepoint><cp_value cp_type="jis208">1-19-56</cp_value></codepoint><misc><variant var_type="ucs">5b78</variant></misc><reading_meaning><rmgroup><reading r_type="ja_on">ガク</reading><meaning>synthetic study</meaning></rmgroup></reading_meaning></character><character><literal>學</literal><misc><variant var_type="jis208">1-19-56</variant></misc></character></kanjidic2>''',
    }
    inputs={}
    for source,xml in content.items():
        path=tmp_path/(source+'.gz');path.write_bytes(gzip.compress(xml.encode()));inputs[source]=path
    manifests={name:{'url':'https://example.org/'+name,'license':'synthetic test fixture'} for name in content}
    path=tmp_path/'public.sqlite3'
    result=build(inputs,path,manifests)
    assert result['state']=='built'
    return path,inputs,manifests

def test_restrictions_variants_names_and_kana(public_db):
    path,_,_=public_db;reader=LexicalReader(path)
    try:
        exact=reader.lookup('学校')['candidates']
        assert {c['kana'] for c in exact}=={'がっこう'}
        assert exact[0]['senses'][0]['english']==['synthetic school']
        assert reader.lookup('學校')['candidates'][0]['match']=='attested_variant'
        assert reader.lookup('gakkō')['candidates'][0]['spelling']=='学校'
        assert reader.lookup('ありがとう')['candidates'][0]['spelling'] is None
        names=reader.lookup('東京')['candidates']
        assert names[0]['senses'][0]['name_types']==['place']
        assert reader.domain('学校')['assertions']==[]
        assert reader.lookup('龘龘')['candidates']==[]
    finally:reader.close()
    result=read('學校',{'path':str(path),'profile':'unavailable'})
    assert result['literal_text']=='學校'
    assert result['unknown_offsets']==[]
    assert read('𠮷',{'path':str(path),'profile':'unavailable'})['unknown_offsets']==[0]
    assert result['translation'] is None

def test_repeatable_build_and_failed_replacement(public_db):
    path,inputs,manifests=public_db
    before=path.read_bytes()
    assert build(inputs,path,manifests)['state']=='unchanged'
    inputs['jmnedict'].write_bytes(gzip.compress(b'<wrong/>'))
    with pytest.raises(ValueError,match='root'):build(inputs,path,manifests)
    assert path.read_bytes()==before
    assert not list(path.parent.glob('dictionary-*.sqlite3'))

def test_candidates_need_no_private_tables(public_db):
    from kanji_translator import candidates
    path,_,_=public_db
    result=candidates({'pattern':'学校','lexicon_path':str(path)})
    assert result['state']=='exact_evidence'
    assert result['dictionary']['candidates']
    assert result['candidates']==[]
    assert candidates({'pattern':'学□','lexicon_path':str(path)})['state']=='abstain'
