"""Derive bounded school/tradition facts from hash-selected PrimaryReference headings."""
import argparse
import gzip
import json
from pathlib import Path
import re
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from kanji_translator.request_contracts import canonical, digest
from kanji_translator.text_normalization import normalized


def build(selected, library):
    rows = []
    seen = set()
    for item in json.loads(selected.read_text())['pages']:
        raw = Path(item['path']).read_bytes()
        if digest(raw) != item['sha256']:
            raise ValueError('Selected PrimaryReference page hash mismatch')
        page = json.loads(raw)
        if page['leaf'] <= 100:
            continue
        for paragraph in page['paragraphs']:
            text = paragraph.get('reading_text', paragraph.get('literal_text', ''))
            heading = re.fullmatch(r'\s*(?:THE\s*)?([A-Z -]+)\s*\(([\u3400-\u9fff]+)\)\s*(SCHOOL|TRADITION)\s*', text.replace('\n', ' '))
            if not heading:
                continue
            reading, literal, kind = heading.groups()
            category = 'sword_school' if kind == 'SCHOOL' else 'sword_tradition'
            key = (normalized(literal), category)
            if key in seen:
                continue
            seen.add(key)
            rows.append({'literal': literal, 'printed_romaji': reading.strip().title(),
                         'role': category, 'source': 'primary_reference',
                         'english': reading.strip().title() + (' sword school' if kind == 'SCHOOL' else ' sword tradition'),
                         'entry_id': f"role:{page['leaf']}:{paragraph['paragraph_id']}",
                         'review_state': 'source_linked_editorial_role',
                         'citations': [{'source': 'primary_reference', 'work': 'Private Japanese–English sword reference A',
                                        'leaf': page['leaf'], 'page': page['label'], 'locator': paragraph['paragraph_id'],
                                        'source_sha256': page['source']['sha256'],
                                        'selected_payload_sha256': item['sha256'], 'passage_sha256': digest(text.encode())}],
                         'meaning_origin': 'explicit_source_heading'})
    # Bare Ichimonji and Ohara have explicit prose school descriptions, plus
    # independently retained literal/romanized records. Both links are required.
    explicit = [('一文字', 'Ichimonji', 43, 'i043_para_04'), ('大原', 'Ohara', 39, 'i039_para_01')]
    selected_rows = json.loads(selected.read_text())['pages']
    for literal, reading, leaf, locator in explicit:
        item = next(r for r in selected_rows if r['leaf'] == leaf)
        page = json.loads(Path(item['path']).read_text())
        paragraph = next(p for p in page['paragraphs'] if p['paragraph_id'] == locator)
        text = paragraph.get('reading_text', paragraph.get('literal_text', ''))
        if reading + ' school' not in text and reading + ' (' + literal + ') school' not in text:
            raise ValueError('School prose anchor absent')
        witnesses = [r for kind in ('terms', 'forms', 'names') for r in library[kind]
                     if normalized(r.get('literal') or '') == normalized(literal)
                     and re.sub('[^a-z]', '', (r.get('printed_romaji') or '').lower()) == reading.lower()]
        if not witnesses:
            raise ValueError('Literal/romanized school bridge absent: ' + literal)
        witness = min(witnesses, key=lambda r: 0 if r['source']=='primary_reference' else 1)
        rows.append({'literal': literal, 'printed_romaji': reading, 'role': 'sword_school', 'source': 'primary_reference',
                     'english': reading+' sword school', 'entry_id': f'role:{leaf}:{locator}:{literal}',
                     'review_state': 'source_linked_editorial_role', 'meaning_origin': 'explicit_school_prose_and_attested_literal',
                     'citations': [{'source': 'primary_reference', 'work': 'Private Japanese–English sword reference A',
                                    'leaf': leaf, 'page': page['label'], 'locator': locator,
                                    'source_sha256': page['source']['sha256'], 'selected_payload_sha256': item['sha256'],
                                    'passage_sha256': digest(text.encode())}],
                     'bridge': [{'source': witness['source'], 'entry_id': witness.get('entry_id', witness.get('form_id', witness.get('name_id'))),
                                 'literal': witness['literal'], 'reading': witness['printed_romaji'],
                                 'citations': witness.get('citations', [])}]})
    # Complete personal names have their own source mappings. A school prefix
    # alone must not establish the rest of a person's name.
    people = [('一文字助真','Ichimonji Sukezane',42,'i042_para_06'),
              ('当麻国行','Taima Kuniyuki',43,'i043_para_11'),
              ('手搔包永','Tegai Kanenaga',43,'i043_para_11'),
              ('保昌貞宗','Hosho Sadamune',43,'i043_para_11')]
    for literal, reading, leaf, locator in people:
        item=next(r for r in selected_rows if r['leaf']==leaf)
        page=json.loads(Path(item['path']).read_text())
        paragraph=next(p for p in page['paragraphs'] if p['paragraph_id']==locator)
        text=paragraph.get('reading_text',paragraph.get('literal_text',''))
        if reading+' ('+literal+')' not in text:
            raise ValueError('Complete personal-name source mapping absent: '+literal)
        rows.append({'literal':literal,'printed_romaji':reading,'role':'swordsmith_artisan',
                     'source':'primary_reference','english':None,'entry_id':f'role:{leaf}:{locator}:{literal}',
                     'review_state':'source_linked_personal_name','meaning_origin':'explicit_complete_name_mapping',
                     'citations':[{'source':'primary_reference','work':'Private Japanese–English sword reference A',
                                   'leaf':leaf,'page':page['label'],'locator':locator,
                                   'source_sha256':page['source']['sha256'],'selected_payload_sha256':item['sha256'],
                                   'passage_sha256':digest(text.encode())}]})
    return {'schema': 'source-semantic-role-facts-v1', 'records': rows,
            'source_selection_sha256': digest(selected.read_bytes()),
            'policy': 'Explicit headings or exact school prose plus attested literal/romanized bridge. No person identity is inferred.'}


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--selected', type=Path, required=True)
    p.add_argument('--output', type=Path, required=True)
    args = p.parse_args()
    library = json.loads(gzip.decompress((ROOT/'kanji_translator/resources/sword_library.json.gz').read_bytes()))
    result = build(args.selected, library)
    args.output.write_bytes(canonical(result)+b'\n')
    print(json.dumps({'role_facts': len(result['records'])}))
