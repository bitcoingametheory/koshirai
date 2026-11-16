"""Single owner of cited school, tradition and complete-name role assertions."""
import json
from functools import lru_cache
from importlib.resources import files
from .text_normalization import forms_with_offsets


@lru_cache(maxsize=1)
def role_facts():
    data = json.loads(files('kanji_translator').joinpath('resources/semantic_roles.json').read_text())
    return data['records']


@lru_cache(maxsize=1)
def _role_index():
    index={}
    for record in role_facts():
        stem, _ = forms_with_offsets(record['literal'])
        suffixes = ('派', '一派', '一門', '流') if record['role']=='sword_school' else ('伝', '傳') if record['role']=='sword_tradition' else ()
        index.setdefault(stem,[]).append((record,False))
        for suffix in {forms_with_offsets(s)[0] for s in suffixes}:index.setdefault(stem+suffix,[]).append((record,True))
    return index

def role_records(literal):
    return [{**r,'literal':literal,'printed_romaji':None,'english':None,'printed_stem':r['literal'],
             'derivation':'cited_role_stem_with_explicit_printed_organizational_suffix'} if derived else r
            for r,derived in _role_index().get(forms_with_offsets(literal)[0],())]

