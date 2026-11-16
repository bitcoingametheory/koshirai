"""Single text representation and literal-offset owner."""
import hashlib,json,re,unicodedata
from functools import lru_cache
HISTORIC_PAIRS=('国國', '円圓', '広廣', '応應', '应應', '為爲', '真眞', '経經', '沢澤', '辺邊', '斎齋', '斉齊', '会會', '万萬', '仏佛', '伝傳', '学學', '宝寶', '実實', '寿壽', '専專', '条條', '桜櫻', '楽樂', '様樣', '権權', '気氣', '浜濱', '満滿', '変變', '団團', '図圖', '塩鹽', '売賣', '声聲', '姫姬', '将將', '旧舊', '尽盡', '昼晝', '来來', '栄榮', '検檢', '残殘', '毎每', '浄淨', '浅淺', '済濟', '渋澁', '湾灣', '湿濕', '滝瀧', '滞滯', '灯燈', '焼燒', '獣獸', '状狀', '独獨', '画畫', '発發', '県縣', '礼禮', '称稱', '穂穗', '竜龍', '総總', '緑綠', '縁緣', '縦縱', '聴聽', '脳腦', '芸藝', '蔵藏', '虫蟲', '蚕蠶', '覚覺', '観觀', '訳譯', '証證', '説說', '読讀', '譲讓', '豊豐', '転轉', '軽輕', '辞辭', '遅遲', '郷鄉', '釈釋', '鉄鐵', '銭錢', '鋳鑄', '録錄', '関關', '険險', '随隨', '隠隱', '雑雜', '霊靈', '静靜', '頼賴', '顔顏', '顕顯', '駅驛', '駆驅', '験驗', '髪髮', '麦麥', '黄黃', '黒黑', '黙默', '齢齡', '亀龜', '与與', '両兩', '乗乘', '乱亂', '亜亞', '仮假', '体體', '余餘', '児兒', '党黨', '写寫', '処處', '剤劑', '労勞', '効效', '勧勸', '区區', '医醫', '単單', '厳嚴', '参參', '収收', '号號', '営營', '囲圍', '圧壓', '壮壯', '奥奧', '奨獎', '嬢孃', '対對', '属屬', '岳嶽', '峡峽', '巻卷', '帯帶', '帰歸', '庁廳', '廃廢', '弾彈', '当當', '径徑', '従從', '徳德', '恋戀', '恒恆', '恵惠', '悩惱', '悪惡', '戦戰', '戯戲', '払拂', '抜拔', '択擇', '担擔', '拝拜', '拠據', '拡擴', '挙舉', '挟挾', '捜搜', '掲揭', '揺搖', '摂攝', '撃擊', '断斷', '暁曉', '暦曆', '曽曾', '枢樞', '桟棧', '横橫', '歩步', '歯齒', '歴歷', '殴毆', '殻殼', '涙淚', '渇渴', '渉涉', '渓溪', '温溫', '瀬瀨', '献獻', '狭狹', '猟獵', '畳疊', '砕碎', '禅禪', '秘祕', '穏穩', '窃竊', '粋粹', '粛肅', '絵繪', '継繼', '続續', '縄繩', '繊纖', '胆膽', '臓臟', '荘莊', '虚虛', '蛍螢', '蛮蠻', '装裝', '覧覽', '触觸', '誉譽', '謡謠', '賛贊', '酔醉', '醸釀', '鉱鑛', '陥陷', '隣鄰', '鶏鷄', '郎郞', '歳歲', '寛寬', '戸戶', '青靑', '内內', '即卽', '麹麴', '錬鍊', '強强', '掻搔', '寳寶', '刃刄', '彦彥', '衛衞', '既旣', '協恊') # Stable search-key derivative only; dictionary variant evidence is in lexical.py.
VARIANTS=dict(HISTORIC_PAIRS)
TRANSLATION=str.maketrans(VARIANTS)
RULE_SHA=hashlib.sha256(json.dumps(HISTORIC_PAIRS,ensure_ascii=False).encode()).hexdigest()
@lru_cache(maxsize=2048)
def character_forms(char):
    canonical=VARIANTS.get(char,char)
    return ''.join(sorted({char,canonical,*[c for c,target in VARIANTS.items() if target==canonical]}))

@lru_cache(maxsize=2048)
def search_pattern(text,escaped_json=False):
    """Literal regex with documented character variants; no name/meaning equivalence."""
    out=[]
    for char in text:
        forms=character_forms(char)
        values=[json.dumps(c,ensure_ascii=True)[1:-1] if escaped_json else c for c in forms]
        out.append('('+ '|'.join(re.escape(v) for v in values)+')' if len(values)>1 else re.escape(values[0]))
    return ''.join(out)
def normalized(text):
    return unicodedata.normalize('NFC',text).translate(TRANSLATION)
def forms(text):
    return {'raw_text':text,'normalized_unicode':unicodedata.normalize('NFC',text),'search_normalized':normalized(text),'search_rule_sha256':RULE_SHA}
def forms_with_offsets(text):
    if not any(unicodedata.combining(c) or '\ufe00'<=c<='\ufe0f' or '\U000e0100'<=c<='\U000e01ef' for c in text) and unicodedata.normalize('NFC',text)==text:
        return normalized(text),list(range(len(text)))
    clusters=[]
    for index,char in enumerate(text):
        # Some composable vowel signs and Hangul jamo have combining class zero.
        if clusters and (unicodedata.combining(char) or '\ufe00'<=char<='\ufe0f' or '\U000e0100'<=char<='\U000e01ef'
                or unicodedata.normalize('NFC',clusters[-1][0]+char)!=unicodedata.normalize('NFC',clusters[-1][0])+unicodedata.normalize('NFC',char)):clusters[-1][0]+=char
        else:clusters.append([char,index])
    result=[];offsets=[]
    for value,index in clusters:
        folded=normalized(value);result.append(folded)
        offsets.extend([index if len(value)==1 else dict(start=index,end=index+len(value))]*len(folded))
    search=''.join(result)
    if search!=normalized(text):raise ValueError('Unsupported normalization offset composition')
    return search,offsets

def query_normalized(value):
    """Casefolded NFKC query keys; separate from literal-preserving kanji forms."""
    import re
    return re.sub(r"\s+", " ", unicodedata.normalize("NFKC", value).casefold()).strip()

def compact_query_normalized(text):
    import re
    text=unicodedata.normalize('NFKC',text).casefold()
    return re.sub(r'\s+', '', text.replace('ō','o').replace('ū','u'))
