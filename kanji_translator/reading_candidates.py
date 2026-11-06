"""Optional literal-aligned reading evidence; no inferred historical-name readings."""
import re,unicodedata
from .request_contracts import canonical,digest
VERSION='dictionary-kana-evidence-hepburn-v2'
_ROWS=[('あいうえお','a i u e o'),('かきくけこ','ka ki ku ke ko'),('がぎぐげご','ga gi gu ge go'),('さしすせそ','sa shi su se so'),('ざじずぜぞ','za ji zu ze zo'),('たちつてと','ta chi tsu te to'),('だぢづでど','da ji zu de do'),('なにぬねの','na ni nu ne no'),('はひふへほ','ha hi fu he ho'),('ばびぶべぼ','ba bi bu be bo'),('ぱぴぷぺぽ','pa pi pu pe po'),('まみむめも','ma mi mu me mo'),('やゆよ','ya yu yo'),('らりるれろ','ra ri ru re ro'),('わゐゑをんゔ','wa wi we o n vu'),('ぁぃぅぇぉ','a i u e o')]
TABLE={c:r for chars,roman in _ROWS for c,r in zip(chars,roman.split())}
for head,stem in [('き','ky'),('ぎ','gy'),('し','sh'),('じ','j'),('ち','ch'),('ぢ','j'),('に','ny'),('ひ','hy'),('び','by'),('ぴ','py'),('み','my'),('り','ry')]:
    for tail,vowel in zip('ゃゅょ','auo'):TABLE[head+tail]=stem+vowel

def romaji(kana):
    """Explicit Hepburn derivative, long vowels expanded, kana original retained."""
    hira=''.join(chr(ord(c)-96) if 'ァ'<=c<='ヶ' else c for c in unicodedata.normalize('NFC',kana))
    result=[];i=0;double=False
    while i<len(hira):
        char=hira[i]
        if char=='っ':double=True;i+=1;continue
        if char=='ー':
            if not result or result[-1][-1] not in 'aeiou':return None
            result.append(result[-1][-1]);i+=1;continue
        size=2 if hira[i:i+2] in TABLE else 1;part=TABLE.get(hira[i:i+size])
        if part is None:return None
        if double:
            if part[0] in 'aeioun':return None
            part=('t' if part.startswith('ch') else part[0])+part;double=False
        if result and result[-1]=='n' and part[0] in 'aeiouy':result[-1]="n'"
        result.append(part);i+=size
    return None if double else ''.join(result)

def readings(text,config,lexical=None):
    alternatives=[]
    for entry in config.get('entries',[]):
        start=entry.get('start');end=entry.get('end');evidence=entry.get('evidence',{})
        if type(start) is not int or type(end) is not int or not 0<=start<end<=len(text):raise ValueError('Invalid reading literal span')
        if entry.get('literal')!=text[start:end]:raise ValueError('Reading entry literal mismatch')
        # A caller assertion is retained as a proposal, never as authenticated gold.
        kana=entry.get('kana');roman=romaji(kana) if isinstance(kana,str) else None
        alternatives.append({'start':start,'end':end,'literal':text[start:end],'kana':kana,'romaji':roman,'evidence':evidence,'state':'proposed','oov':roman is None})
    if text and re.fullmatch('[ぁ-ゖァ-ヶー]+',text):
        alternatives.append({'start':0,'end':len(text),'literal':text,'kana':text,'romaji':romaji(text),'state':'source_kana','evidence':{'method':'literal_kana'},'oov':False})
    for span in (lexical or {}).get('spans',[]):
        for candidate in span['candidates']:
            alternatives.append({'start':span['start'],'end':span['end'],'literal':span['literal'],'kana':candidate['kana'],'romaji':candidate['romaji'].get('hepburn-expanded-v1'),'romaji_forms':candidate['romaji'],'evidence':{'source':candidate['source'],'entry_id':candidate['entry_id'],'variant_path':candidate['variant_path']},'state':'dictionary_candidate','oov':False})
    covered={i for row in alternatives if row['romaji'] is not None for i in range(row['start'],row['end'])}
    required={i for i,c in enumerate(text) if re.match('[ぁ-ゖァ-ヶ一-鿿㐀-䶿\U00020000-\U000323af]',c)}
    return {'version':VERSION,'scheme':'hepburn-v1','long_vowels':'expanded','alternatives':alternatives,'abstained':bool(required-covered),'oov_spans':[i for i in sorted(required-covered)],'literal_sha256':digest(text.encode()),'review_state':'proposed' if alternatives else 'unresolved'}


def roman_forms(kana):
    """Bounded search derivatives; historical kana is spelling, not pronunciation.

    hepburn-expanded preserves vowel spelling; display contracts common Japanese
    long-vowel sequences. Neither is independent printed-romaji evidence.
    """
    expanded=romaji(kana)
    if not expanded:return {}
    display=expanded
    for a,b in [('aa','ā'),('ii','ī'),('uu','ū'),('ee','ē'),('oo','ō'),('ou','ō')]:display=display.replace(a,b)
    plain=display.translate(str.maketrans('āīūēō','aiueo'))
    return {'hepburn-expanded-v1':expanded,'hepburn-macron-v1':display,'hepburn-ascii-lossy-v1':plain}
