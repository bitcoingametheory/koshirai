"""Read explicit Japanese dictionary-entry fields without inventing name splits.

Index tabs, entry marks and printed brackets are structural evidence. They are
not accepted people, OCR corrections, or permission to join unrelated lines.
"""
import re

VERSION = 'native-entry-fields-v1'
KANJI = r'[㐀-䶿一-鿿豈-﫿々〆]'
TAB = re.compile(r'【[ぁ-ゖァ-ヶ]】\s*([^\n。]{1,60})')
MARK = re.compile(r'(?:^|\n)[ \t]*[◇◆▽◊○◯]\s*')
BRACKET = re.compile(r'[〔（(]([^〕）)\n]{2,30})[〕）)]')
PERIOD = re.compile(r'新々刀|新新刀|中古刀|末古刀|現代刀|新刀|古刀')
GRADE = re.compile(r'最上大業物|大業物|良業物|業物|最上作|上々作|中上作|上作|中作|下作')
SIGNATURE = re.compile(r'(?:刻銘|銘文|銘)\s*[「『]([^」』\n]{1,80})[」』]')


def span(text, start, end, **fields):
    return {'literal': text[start:end], 'start': start, 'end': end, **fields}


def tabs(text):
    result = []
    for match in TAB.finditer(text):
        for name in re.finditer(KANJI+r'{2,16}', match[1]):
            value = name[0]
            # Trailing printed folios are furniture, never extra name characters.
            value = re.sub(r'[〇一二三四五六七八九十百]+$', '', value)
            if len(value) >= 2:
                start = match.start(1)+name.start()
                result.append(span(text, start, start+len(value), basis='printed_index_tab'))
    return result


def extract(text, candidates=(), index_names=()):
    """Return only within-region fields with native codepoint offsets."""
    names = set(index_names) | {r['literal'] for r in tabs(text)}
    known = {r['literal'] for r in candidates
             if r['selection']['category']=='swordsmith_artisan' and r['selection']['score'] >= 1}
    entries = []
    marks = list(MARK.finditer(text))
    for i, mark in enumerate(marks):
        end = marks[i+1].start() if i+1 < len(marks) else len(text)
        stop = min([m.start() for regex in (BRACKET, PERIOD, GRADE)
                    for m in regex.finditer(text, mark.end(), end)] +
                   [text.find('\n', mark.end(), end) if '\n' in text[mark.end():end] else end, end])
        head_end = stop
        while head_end > mark.end() and text[head_end-1].isspace():
            head_end -= 1
        head = text[mark.end():head_end]
        exact = sorted((n for n in names if head.startswith(n)), key=len, reverse=True)
        # Source-backed whole heading is usable; a two-character fallback is not.
        if not exact and head in known:
            exact = [head]
        if not exact:
            suffixes={r['literal'] for r in candidates if r['selection']['category'] in ('sword_school','place_province')
                      and r['selection']['score'] >= 1}
            exact=sorted((n for n in known if len(n)>=2 and head.startswith(n) and head[len(n):] in suffixes),key=len,reverse=True)
        name = span(text, mark.end(), mark.end()+len(exact[0]),
                    basis='printed_index_tab' if exact[0] in names else 'attested_complete_heading') if exact else None
        bracket = BRACKET.search(text, head_end, end)
        fields = {}
        if bracket and bracket.start()-head_end < 4:
            split = re.search(r'[-—―－ー‐|｜]', bracket[1])
            if split:
                for key, a, b in (('era', bracket.start(1), bracket.start(1)+split.start()),
                                  ('province', bracket.start(1)+split.end(), bracket.end(1))):
                    while a < b and text[a].isspace(): a += 1
                    while b > a and text[b-1].isspace(): b -= 1
                    if a < b: fields[key] = span(text, a, b)
        for key, regex in (('period', PERIOD), ('grade', GRADE)):
            field = regex.search(text, head_end, end)
            if field and field.start()-head_end < 45:
                fields[key] = span(text, field.start(), field.end())
        entries.append({'start':mark.start(), 'end':end,
                        'head':span(text, mark.end(), head_end), 'name':name,
                        'unresolved_head_suffix':span(text, name['end'], head_end) if name and name['end'] < head_end else None,
                        'fields':fields, 'identity_accepted':False,
                        'state':'source_structure_proposal' if name else 'unresolved_name_boundary',
                        'scope':'same_native_region_or_explicit_native_textblock'})
    return {'version':VERSION, 'entries':entries, 'index_names':tabs(text),
            'signatures':[span(text,m.start(1),m.end(1),basis='explicit_signature_label') for m in SIGNATURE.finditer(text)],
            'changes_characters':False, 'identity_accepted':False}


def retained_witnesses(page):
    """Compare saved OCR passes without aligning or merging their characters."""
    from .request_contracts import digest
    result=[]
    for field,engine in (('text_raw','engine'),('text_alt_raw','alt_engine')):
        text=page.get(field)
        if not isinstance(text,str) or not text:continue
        names=[r['literal'] for r in tabs(text)];entries=[];offset=0
        for line in text.splitlines(keepends=True):
            parsed=extract(line.rstrip('\r\n'),index_names=names)
            for entry in parsed['entries']:
                entries.append({'line_offset':offset,'entry':entry})
            offset+=len(line)
        result.append({'field':field,'engine':page.get(engine),'text_sha256':digest(text.encode()),
                       'entries':entries,'geometry':None,'state':'unaligned_OCR_witness',
                       'automatic_promotion':False})
    return {'passes':result,'policy':'No fuzzy name merge, invented alignment, or replacement of the primary reading.'}
