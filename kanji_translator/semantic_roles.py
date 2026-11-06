"""Single owner of cited school, tradition and complete-name role assertions."""
import json
from functools import lru_cache
from importlib.resources import files
from .text_normalization import forms_with_offsets


@lru_cache(maxsize=1)
def role_facts():
    data = json.loads(files('kanji_translator').joinpath('resources/semantic_roles.json').read_text())
    return data['records']


def role_records(literal):
    value, _ = forms_with_offsets(literal)
    matches = []
    for record in role_facts():
        stem, _ = forms_with_offsets(record['literal'])
        suffixes = ('派', '一派', '一門', '流') if record['role']=='sword_school' else ('伝', '傳') if record['role']=='sword_tradition' else ()
        if value == stem:
            matches.append(record)
        elif any(value == stem + forms_with_offsets(suffix)[0] for suffix in suffixes):
            matches.append({**record, 'literal': literal, 'printed_romaji': None,
                            'english': None, 'printed_stem': record['literal'],
                            'derivation': 'cited_role_stem_with_explicit_printed_organizational_suffix'})
    return matches

