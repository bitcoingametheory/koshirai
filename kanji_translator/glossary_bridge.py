"""Join reviewed PrimaryReference glossary headwords to attested SupportingReference kanji forms.

Labels are short editorial summaries of the cited definitions. They are not
new source quotations, expert attestations, or identity assertions. An explicit
literal allowlist prevents homophonous personal names from acquiring a gloss.
"""
import hashlib
import json
from pathlib import Path
import re
import unicodedata


def build_aligned_terms(path):
    """Export bounded facts from an external image-reviewed bilingual alignment.

    Private passages, paths and page images never enter the release. Japanese
    PDF pages and English printed pages describe distinct editions of one work.
    The review remains provisional and is not an independent expert attestation.
    """
    from .build_sword_library import literal, roman
    from .meaning_selection import english_quality
    from .request_contracts import require_hash
    result = []
    for line in Path(path).read_text(encoding='utf-8').splitlines():
        row = json.loads(line)
        if row.get('raw_ocr_changed') is not False or row.get('review_status') != 'AI_source_image_reviewed_provisional_not_expert':
            raise ValueError('Bilingual alignment requires explicit unchanged OCR and image review')
        form, reading, gloss = row['literal'], row['reading_printed'], row['english_summary']
        if literal(form) != form or roman(reading) != reading or not english_quality(gloss)['eligible']:
            raise ValueError('Alignment must contain a bounded literal, reading and lexical gloss')
        if row.get('unicode_codepoints') != [f'U+{ord(c):04X}' for c in form]:
            raise ValueError('Alignment codepoints differ from its literal')
        jp, en = row['japanese'], row['english']
        label_match = re.fullmatch(r'[●◎○・\s]*(' + re.escape(form) + r')[\s]*', jp['raw_label'])
        if not label_match:
            raise ValueError('Alignment Japanese label differs from its complete literal')
        for number in (jp['pdf_page'], jp['printed_page'], en['label_printed_page'], en['definition_printed_page']):
            if type(number) is not int or number < 1:
                raise ValueError('Alignment page locators must be positive integers')
        if type(en['edition']) is not int or not 1000 <= en['edition'] <= 9999:
            raise ValueError('Alignment English edition must be a four-digit year')
        if type(jp['label_line_id']) is not int or jp['label_line_id'] < 0:
            raise ValueError('Alignment label line must be a nonnegative integer')
        citations = [
            {'source': 'primary_reference', 'edition': 'Japanese',
             'pdf_page': jp['pdf_page'], 'printed_page': jp['printed_page'],
             'locator': 'line:' + str(jp['label_line_id']),
             'literal_span': list(label_match.span(1)),
             'source_sha256': require_hash(jp['source_sha256']),
             'image_sha256': require_hash(jp['image_sha256'])},
            {'source': 'primary_reference', 'edition': str(en['edition']) + ' English',
             'printed_page': en['definition_printed_page'],
             'label_printed_page': en['label_printed_page'],
             'source_sha256': require_hash(en['definition_payload_sha256']),
             'image_sha256': require_hash(en['definition_image_sha256']),
             'label_image_sha256': require_hash(en['label_image_sha256'])}]
        key = hashlib.sha256(json.dumps([form, reading, gloss, citations], ensure_ascii=False, sort_keys=True).encode()).hexdigest()
        result.append({'source': 'primary_reference', 'entry_id': 'bilingual:' + key,
                       'literal': form, 'printed_romaji': reading, 'english': gloss,
                       'role': 'technical_sword_term', 'concept_ids': [],
                       'review_state': row['review_status'], 'citations': citations,
                       'bridge': True, 'alignment': 'image_reviewed_bilingual_labels_and_definitions',
                       'meaning_origin': 'editorial_summary_of_cited_definition',
                       'independence': 'Two editions of one work, not independent corroboration'})
    keys = [r['entry_id'] for r in result]
    if len(keys) != len(set(keys)):
        raise ValueError('Duplicate bilingual alignment')
    return result

# Editorial lexical summaries; the build must find both source records.
SUMMARIES = [['choji ashi', '丁子足', 'clove-shaped temper legs'], ['boshi', '帽子', 'tip temper pattern'], ['itame-hada', '板目肌', 'wood grain pattern'], ['mokume-hada', '杢目肌', 'burl grain pattern'], ['masame-hada', '柾目肌', 'straight grain pattern'], ['suguha', '直刃|直刄', 'straight temper pattern'], ['ko-maru', '小丸', 'small rounded tip return'], ['hamon', '刃文|刄文', 'temper boundary pattern'], ['jigane', '地鉄|地鐵|地金', 'blade steel'], ['jihada', '地肌', 'forged surface grain'], ['Shinto', '新刀', 'swords dated 1596-1781'], ['Shinshinto', '新々刀', 'late eighteenth-century onward swords'], ['Koto', '古刀', 'swords through 1595'], ['horimono', '彫物', 'blade carving'], ['kinsuji', '金筋', 'bright linear crystalline activity'], ['sunagashi', '砂流し', 'streaming crystalline activity'], ['nagasa', '長さ', 'blade length'], ['kasane', '重ね', 'blade thickness'], ['sori', '反り', 'blade curvature'], ['yokote', '横手|橫手', 'tip boundary line'], ['nakago', '茎|中心', 'sword tang'], ['mei', '銘', 'sword signature'], ['mumei', '無銘', 'unsigned blade'], ['katana', '刀', 'edge-up curved sword'], ['tachi', '太刀', 'suspended curved sword'], ['tanto', '短刀', 'blade under thirty centimetres'], ['wakizashi', '脇指|脇差', 'intermediate length sword'], ['nie', '沸', 'visible crystalline particles'], ['kaeri', '返り', 'tip temper return'], ['utsuri', '映り', 'surface reflection pattern'], ['sugata', '姿', 'overall sword shape'], ['ko-itame', '小板目', 'fine wood grain'], ['ko-mokume', '小杢目', 'fine burl grain'], ['ko-nie', '小沸', 'small crystalline particles'], ['ko-midare', '小乱れ|小亂', 'small irregular temper pattern'], ['ko-notare', '小湾れ|小灣れ', 'gently waving temper pattern'], ['ko-gunome', '小互の目', 'small rounded temper undulations'], ['midareba', '乱刃|亂刄|乱れ刃', 'irregular temper pattern'], ['notare', '湾れ|灣れ', 'waving temper pattern'], ['hitatsura', '皆焼|皆燒', 'scattered full temper pattern'], ['gimei', '偽銘', 'false sword signature'], ['daimei', '代銘', 'authorized substitute signature'], ['daisaku', '代作', 'authorized substitute production'], ['yasurime', '鑢目', 'tang file marks'], ['tobiyaki', '飛焼|飛燒', 'detached tempered spots'], ['hakikake', '掃掛け|掃掛', 'brushlike tip activity'], ['yakiire', '焼入れ|燒入', 'blade hardening'], ['yakitsume', '焼詰|燒詰', 'tip temper without return'], ['kiri', '切', 'square tang end'], ['kurijiri', '栗尻', 'rounded tang end'], ['habaki', '鎺', 'blade retaining collar'], ['fukura', 'ふくら', 'curved tip edge'], ['hataraki', '働き', 'visible steel activity'], ['hada', '肌', 'blade surface grain'], ['fukure', '膨れ', 'forging blister'], ['hagire', '刃切れ|刄切', 'edge crack'], ['bo-bi', '棒樋', 'wide straight groove'], ['soe-bi', '添樋', 'smaller accompanying groove'], ['bonji', '梵字', 'sacred Sanskrit carving'], ['tsuka', '柄', 'sword hilt'], ['saya', '鞘', 'sword scabbard'], ['mekugi ana', '目釘穴', 'tang retaining hole'], ['zaimei', '在銘', 'original signature retained']]


def roman_key(value):
    value = unicodedata.normalize('NFKD', value.casefold())
    return re.sub('[^a-z]', '', ''.join(c for c in value if not unicodedata.combining(c)))


def build_bridges(pages, data):
    glossary = {}
    selected = json.loads(Path(pages).read_text())['pages'] if Path(pages).is_file() else []
    if not selected:
        manifest = json.loads((Path(pages).parent / 'manifest.json').read_text())
        selected = [{**r, 'path': str(Path(pages).parent / r['page'])} for r in manifest['pages']]
    for selection in selected:
        path = Path(selection['path'])
        raw = path.read_bytes()
        if hashlib.sha256(raw).hexdigest() != selection['sha256']:
            raise ValueError('Glossary source payload differs from selected hash')
        page = json.loads(raw)
        if not 358 <= page.get('leaf', -1) <= 369:
            continue
        paragraphs = {p['paragraph_id']: p for p in page['paragraphs']}
        for group in page.get('display_groups', []):
            first = paragraphs.get(group[0], {})
            text = first.get('reading_text', first.get('literal_text', ''))
            runs = first.get('style_runs', [])
            # Corrections explicitly own reviewed bold-headword boundaries.
            for correction in page.get('scoped_corrections', {}).get('text_corrections', []):
                if correction.get('kind') == 'paragraph_style' and correction.get('paragraph_id') == group[0]:
                    runs = correction.get('style_runs', runs)
            bold = [r for r in runs if r.get('bold') and r.get('start') == 0]
            if not bold:
                continue
            headword = text[:bold[0]['end']]
            passage = ' '.join(paragraphs[k].get('reading_text', paragraphs[k].get('literal_text', '')) for k in group)
            citation = {'source': 'primary_reference', 'work': 'Private Japanese–English sword reference A',
                        'page': page['label'], 'leaf': page['leaf'], 'locator': group[0],
                        'source_sha256': page['source']['sha256'],
                        'selected_payload_sha256': selection['sha256'],
                        'passage_sha256': hashlib.sha256(passage.encode()).hexdigest(),
                        'headword': headword, 'paragraph_ids': group}
            glossary.setdefault(roman_key(headword), []).append((citation, passage))
    result = []
    for headword, literals, summary in SUMMARIES:
        for literal in literals.split('|'):
            witnesses = []
            for row in data['terms'] + data['forms']:
                if not row['source'].startswith('supporting_reference') or not row.get('printed_romaji'):
                    continue
                # Middle dots and slashes here are explicit source spelling lists.
                forms = re.split(r'[・／/]', row.get('literal') or '')
                if literal not in [f.strip() for f in forms] or roman_key(row['printed_romaji']) != roman_key(headword):
                    continue
                witnesses.append({'source': row['source'], 'literal': row['literal'],
                                  'reading': row['printed_romaji'], 'entry_id': row.get('entry_id'),
                                  'citations': row.get('citations', [])})
            if not witnesses:
                continue
            definitions = glossary.get(roman_key(headword), [])
            # Tachi has two different printed Japanese headwords; preserve that distinction.
            definitions = [(c, p) for c, p in definitions
                           if headword != 'tachi' or '(' + literal + ')' in p]
            for citation, passage in definitions:
                result.append({'source': 'primary_reference',
                               'entry_id': 'glossary:' + str(citation['leaf']) + ':' + citation['locator'] + ':' + literal,
                               'literal': literal, 'printed_romaji': headword,
                               'english': summary, 'role': 'technical_sword_term', 'concept_ids': [],
                               'review_state': 'source_linked_editorial_summary',
                               'citations': [citation], 'bridge': witnesses,
                               'alignment': 'explicit_literal_and_exact_normalized_romanized_headword',
                               'meaning_origin': 'editorial_summary_of_cited_definition'})
    return result
