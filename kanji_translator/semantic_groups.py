"""Literal, source-supported span matching and contextual semantic selection.

No fuzzy spelling or character rewriting. Overlaps remain reviewable; weighted
interval scheduling chooses a compatible set rather than blindly taking longest.
"""
import bisect
import re
import unicodedata
from functools import lru_cache
from .request_contracts import canonical, digest
from .text_normalization import forms_with_offsets
from .sword_library import bundle, lookup
from .meaning_selection import english_quality
from .semantic_roles import role_facts, role_records

VERSION = 'literal-semantic-groups-v7-native-entries'
CATEGORIES = ('technical_sword_term', 'swordsmith_artisan', 'sword_school',
              'sword_tradition',
              'measurement_dimension', 'historical_person', 'family_clan',
              'place_province', 'era_date', 'ordinary_language', 'unresolved')
JAPANESE = re.compile(r'[ぁ-ゖァ-ヶ㐀-䶿一-鿿豈-﫿]')
QUANTITY = r'[〇零一二三四五六七八九十百千壱弐参拾\d０-９]+(?:[・.．][\d０-９]+)?'
MEASUREMENT = re.compile(r'(?:(?:'+QUANTITY+r')(?:尺|寸|分|厘|匁|貫|粍|糎|センチ|ミリ))+')
ERA_GLOSS = re.compile(r'\bera\b[^()]*\(\d{3,4}[.\-/]',re.I)
DATE_SUFFIX = re.compile(r'(?:元|'+QUANTITY+r')年(?:(?:'+QUANTITY+r')月)?(?:(?:'+QUANTITY+r')日)?')




def era_sense(sense):
    return any(ERA_GLOSS.search(gloss) for gloss in sense.get('english',[]))


def authority(source):
    if source in ('primary_reference', 'primary_reference-register'): return 'primary_reference'
    if source.startswith(('club', 'supporting_reference', 'nwatch')): return 'scholarly_supplement'
    if source.startswith('dealer'): return 'dealer_supplement'
    if source in ('jmdict', 'jmnedict', 'kanjidic2'): return 'general_dictionary'
    return 'untyped_source'


@lru_cache(maxsize=1)
def trie():
    data, _ = bundle(); root = {}
    forms = set()
    for kind in ('terms','spellings','names','forms'):
        forms.update(r['literal'] for r in data[kind] if r.get('literal'))
    forms.update(r['form'] for r in data['aliases'] if r.get('language')=='ja')
    forms.update(r['label_ja'] for r in data['concepts'] if r.get('label_ja'))
    single_attested={r['literal'] for r in role_facts() if len(r['literal'])==1}
    single_attested.update(r['literal'] for r in data['terms'] if r.get('literal') and len(r['literal'])==1 and r.get('bridge') and r.get('role')=='technical_sword_term')
    for record in role_facts():
        forms.add(record['literal'])
        suffixes = ('派', '一派', '一門', '流') if record['role']=='sword_school' else ('伝', '傳') if record['role']=='sword_tradition' else ()
        forms.update(record['literal']+s for s in suffixes)
    for form in forms:
        normalized, _ = forms_with_offsets(form)
        if not (2<=len(normalized)<=48 or form in single_attested) or not JAPANESE.search(normalized) or re.search(r'\s',normalized):
            continue
        node=root
        for char in normalized: node=node.setdefault(char,{})
        node.setdefault('',[]).append(form)
    return root


def matched_spans(text):
    normalized, offsets = forms_with_offsets(text)
    root=trie(); found=set()
    for start in range(len(normalized)):
        node=root
        for end in range(start,min(len(normalized),start+48)):
            node=node.get(normalized[end])
            if node is None:break
            if '' in node:
                # Offsets are original codepoint offsets; source remains untouched.
                first=offsets[start]; last=offsets[end]
                a=first['start'] if isinstance(first,dict) else first
                b=last['end'] if isinstance(last,dict) else last+1
                if '\n' not in text[a:b]:found.add((a,b))
    return found


def _candidate(category, reading=None, english=None, source=None, support=None, prior=1., name=None):
    return {'category':category,'reading':reading,'english':english,'name':name,
            'authority':authority(source or ''),'source':source,'support':support or [],
            'prior':prior,'identity_accepted':False}


def candidates(text, start, end, lexical_spans=()):
    literal=text[start:end]; domain=lookup(literal); result=[]
    normalized,_=forms_with_offsets(literal);node=trie()
    for char in normalized:node=node.get(char,{})
    for source_form in node.get('',[]):
        if source_form==literal:continue
        variant=lookup(source_form)
        for kind in ('assertions','concepts','smith_name_candidates'):
            domain[kind].extend({**row,'lookup_derivative':{'printed':literal,'attested_form':source_form,'basis':'documented historical search-form mapping; literal preserved'}} for row in variant[kind])
    technical=bool(domain['concepts'])
    known_smith=bool(domain['smith_name_candidates'])
    for record in domain['assertions']+domain['smith_name_candidates']+domain['semantic_role_assertions']:
        source=record.get('source','unknown'); role=record.get('role',record.get('category',''))
        name=(record in domain['smith_name_candidates'] or role in ('smith_name_candidate','swordsmith_artisan')
              or (known_smith and source=='primary_reference' and bool(record.get('printed_romaji'))))
        school=role in ('sword_school','school') or (literal.endswith('派') and source.startswith(('club','supporting_reference','primary_reference','dealer')))
        category=role if role in ('sword_school','sword_tradition') else 'sword_school' if school else 'swordsmith_artisan' if name else 'technical_sword_term' if role=='technical_sword_term' or technical or record.get('concept_ids') else 'unresolved'
        # A source's inclusion in PrimaryReference does not make a person a technical term.
        english=record.get('english')
        english=english if english_quality(english)['eligible'] else None
        reading=record.get('printed_romaji')
        if category=='unresolved' and not (reading or english):continue
        result.append(_candidate(category,reading,english,source,[record],
                      3. if source=='primary_reference' else 2. if name or technical or school else .3,
                      reading if name else None))
    for concept in domain['concepts']:
        record=concept['source_concept']
        # The concept ID is an internal key; never turn it into invented English.
        sources=concept.get('source_senses',[])
        source=next((s['source'] for s in sources if s.get('source')=='primary_reference'),None)
        source=source or next((s['source'] for s in sources if s.get('source')),None)
        if not source:
            source=next((s.get('source_id') for s in concept.get('aliases',[]) if s.get('form')==literal),'concept_inventory')
        result.append(_candidate('technical_sword_term',record.get('label_en'),None,source,[concept],2.5))
    for span in lexical_spans:
        exact=(span['start'],span['end'])==(start,end)
        dated=span['start']==start and span['end']<end and DATE_SUFFIX.fullmatch(text[span['end']:end])
        if not exact and not dated:continue
        for entry in span.get('candidates',[]):
            for sense in entry.get('senses',[]):
                era=era_sense(sense)
                if dated and not era:continue
                tags=set(sense.get('name_types',[])); category='ordinary_language'
                labels=' '.join(tags).casefold()
                if era:category='era_date'
                elif any('former province' in g.casefold() for g in sense.get('english',[])):category='place_province'
                elif 'surname' in labels or 'family' in labels:category='family_clan'
                elif 'full name' in labels or 'given name' in labels or 'person' in labels:category='historical_person'
                elif 'place' in labels or 'station' in labels:category='place_province'
                elif tags:category='unresolved'
                glosses=sense.get('english',[]); roman=entry.get('romaji') or {}
                reading=roman.get('hepburn-expanded-v1',roman.get('hepburn')) if isinstance(roman,dict) else None
                support={'source':entry.get('source'),'entry_id':entry.get('entry_id'),
                         'kana':entry.get('kana'),'sense':sense.get('ordinal'),'name_types':sense.get('name_types',[]),'variant_path':entry.get('variant_path',[])}
                if dated:
                    support.update(era_literal=text[start:span['end']],era_reading=reading,era_gloss=glosses[0],printed_date=text[span['end']:end])
                result.append(_candidate(category,None if dated else reading,None if dated else glosses[0] if glosses and not tags else None,
                              entry.get('source'),[support],3. if dated else 2. if era else .5,name=(glosses[0] if glosses else reading) if tags else None))
    if MEASUREMENT.fullmatch(literal):
        components=[{'quantity':m.group(1),'unit':m.group(2),'start':start+m.start(),'end':start+m.end()}
                    for m in re.finditer('('+QUANTITY+')(尺|寸|分|厘|匁|貫|粍|糎|センチ|ミリ)',literal)]
        preceding=text[max(0,start-10):start]
        dimension=next((word for word in ('刃長','長さ','反り','重ね','身幅','重量','長') if word in preceding),None)
        result.append({**_candidate('measurement_dimension',source='printed_quantity_unit',prior=3.,
                       support=[{'literal':literal,'basis':'explicit printed quantity/unit expression','start':start,'end':end}]),
                       'components':components,'dimension':dimension,'authority':'literal_measurement'})
    unique={}
    for row in result:
        key=(row['category'],row['reading'],row['english'],row['source'])
        if key in unique:unique[key]['support']+=row['support']
        else:unique[key]=row
    return list(unique.values())


def compatible(rows):
    ordered=sorted(rows,key=lambda r:(r['end'],r['start']))
    ends=[r['end'] for r in ordered]; scores=[0.]; selections=[[]]
    for index,row in enumerate(ordered):
        before=bisect.bisect_right(ends,row['start'],0,index)
        # Modest coverage credit permits supported whole names to beat fragments.
        value=max(0.,row['selection']['score']) + .15*(row['end']-row['start'])
        if scores[before]+value>scores[-1]:
            scores.append(scores[before]+value);selections.append(selections[before]+[row])
        else:scores.append(scores[-1]);selections.append(selections[-1])
    return sorted(selections[-1],key=lambda r:r['start'])


def evidence_rank(text, start, end, options, role):
    """Rank documented meanings first; retain untyped/homophonous alternatives."""
    ranked = []
    for option in options:
        category = option['category']
        source = option.get('source') or ''
        score = -1.
        reasons = []
        if category == 'technical_sword_term':
            bridges = [r for r in option['support'] if r.get('bridge') and r.get('citations')]
            score = 12. if bridges else 5. if source == 'primary_reference' else 4.
            reasons.append('cited_glossary_bridge' if bridges else 'documented_sword_concept')
        elif category == 'swordsmith_artisan':
            score = 8. if source in ('primary_reference', 'primary_reference-register') else 6.
            reasons.append('documented_smith_spelling')
            # A register fragment is not evidence that a grammatical/calendar word is a smith here.
            if re.fullmatch(QUANTITY + r'(?:年|月|日|歳|歲)?', text[start:end]):
                score = -1.; reasons.append('calendar_or_number_conflict')
            if re.search(r'[ぁ-ゖ]', text[start:end]):
                score = -1.; reasons.append('untyped_kana_fragment')
        elif category in ('measurement_dimension', 'sword_school', 'sword_tradition', 'era_date'):
            score = 9. if category == 'measurement_dimension' else 6.
            reasons.append('supported_complete_expression')
        elif category == 'place_province':
            former=any('former province' in (option.get('english') or '').casefold() for _ in [0])
            score = 10. if former else 3.; reasons.append('dictionary_province' if former else 'dictionary_place')
        # Dictionary names remain alternatives without evidence of a historical person.
        if role in ('page_number', 'running_header', 'unresolved_ink'):
            score = -1.; reasons.append('page_furniture_or_unread_ink')
        if category=='technical_sword_term' and re.match(r'銘[盡尽]|大鑑|圖鑑|図鑑|全集',text[end:]):
            score=-1.;reasons.append('part_of_book_title')
        ranked.append({**option, 'score': score, 'selection_evidence': reasons})
    ranked.sort(key=lambda c: (-c['score'], -len(c.get('english') or ''),
                             0 if c.get('source')=='primary_reference' else 1,
                             len(c.get('reading') or ''),str(c.get('reading'))))
    return ranked, {'version': 'source-evidence-priority-v1', 'threshold': 1.,
                    'score_kind': 'fixed_evidence_priority', 'calibrated': False}


def _ideograph(char):
    return bool(char) and (unicodedata.name(char, '').startswith('CJK ') or char in '々〆〇')


def _separator(char):
    return not char or char.isspace() or unicodedata.category(char)[0] in 'PZ'


def _cited_technical(row):
    choice = row['selection']
    return (choice['category'] == 'technical_sword_term' and bool(choice.get('english'))
            and any(s.get('bridge') and s.get('citations') for s in choice['support']))


def sequence_boundary(text, row, rows):
    """Explain a complete span without treating Japanese prose as space-delimited.

    Kana and adjacent cited terms can bound a multi-character technical mapping.
    A following inflected kanji word can start a predicate. Bare kanji extensions,
    size prefixes, and attested larger expressions remain unresolved candidates.
    These are selection rules, not grammatical or sense-accuracy probabilities.
    """
    start, end = row['start'], row['end']
    before, after = text[start-1:start] if start else '', text[end:end+1]
    technical = row['selection']['category'] == 'technical_sword_term'
    if row.get('entry_evidence'):
        return {'eligible': True, 'basis': 'explicit_entry_field', 'evidence': row['entry_evidence']}
    if row['selection']['category'] == 'swordsmith_artisan':
        containing = [other for other in rows if other is not row
                      and other['start'] <= start and end <= other['end']
                      and (other['start'],other['end']) != (start,end)
                      and other['selection']['category']=='swordsmith_artisan'
                      and other['selection']['score'] >= 1]
        if containing:
            whole=max(containing,key=lambda r:r['end']-r['start'])
            return {'eligible':False,'basis':'inside_attested_longer_name','complete_candidate':whole['literal']}
        # Era names also occur in registers. Keep the calendar alternative unless
        # an explicit name/entry construction supplies evidence for this use.
        era=any(o['category']=='era_date' for o in [row['selection']]+row['alternatives'])
        left=not _ideograph(before) and not (before and before.isascii() and before.isalnum())
        generation=re.search(r'(?:初|先|[一二三四五六七八九十]+)代$',text[:start])
        named=re.search(r'(?:初銘|改銘|後銘)$',text[:start])
        if generation or named:left=True
        right=_separator(after) or bool(re.match(r'(?:は|が|を|に|の|と|も|より|とも|門(?:人|下)?|弟子|子|弟|兄|父|孫|一族|作(?:と|な|で|。|、|$))',text[end:]))
        return {'eligible':left and right and not era,'basis':'japanese_attested_name',
                'left_confirmed':left,'right_confirmed':right,'calendar_conflict':era,
                'preceding_name_label':generation[0] if generation else named[0] if named else None}
    if not technical:
        bounded=(start==0 or before in '「『【〔 、。，,') and (end==len(text) or after in '」』】〕 、。，,')
        return {'eligible': bounded, 'basis': 'explicit_delimiters' if bounded else 'complete_sequence_boundary_unconfirmed'}
    if technical:
        containing = [(other['start'], other['end']) for other in rows
                      if other is not row and _cited_technical(other)
                      and other['start'] <= start and end <= other['end']
                      and (other['start'], other['end']) != (start, end)]
        if containing:
            a, b = max(containing, key=lambda span: span[1]-span[0])
            return {'eligible': False, 'basis': 'inside_attested_longer_expression',
                    'complete_candidate': text[a:b], 'start': a, 'end': b}
        if before in ('大', '中', '小'):
            return {'eligible': False, 'basis': 'unmapped_size_compound',
                    'complete_candidate': text[start-1:end], 'start': start-1, 'end': end}
    if _separator(before) and _separator(after):
        return {'eligible': True, 'basis': 'explicit_delimiters'}
    if not (_cited_technical(row) and end-start >= 2):
        return {'eligible': False, 'basis': 'complete_sequence_boundary_unconfirmed'}
    left = not _ideograph(before) and not (before and before.isascii() and before.isalnum())
    right = not _ideograph(after) and not (after and after.isascii() and after.isalnum())
    evidence = ['cited_complete_technical_mapping']
    for other in rows:
        if other is row or not _cited_technical(other) or other['end']-other['start'] < 2:
            continue
        if other['end'] == start:
            left = True; evidence.append('preceding_cited_term')
        if other['start'] == end:
            right = True; evidence.append('following_cited_term')
    # A noun plus a particle (e.g. 尻の) is not evidence of an inflection.
    if not right and re.match(r'[㐀-䶿一-鿿豈-﫿]{1,2}[いきぎくぐけげさしじすずせたちぢつてでとびぴぶぷべぺまみむめもやゆよらりるれろわんっ]', text[end:]):
        right = True; evidence.append('following_inflected_word')
    return {'eligible': left and right, 'basis': 'japanese_technical_sequence',
            'left_confirmed': left, 'right_confirmed': right, 'evidence': evidence}


def interpret(text, lexical=None, context=None, config=None):
    lexical=lexical or {}; context=context or {}; config=config or {}
    domain_spans=matched_spans(text)
    spans=set(domain_spans)
    spans.update((m.start(),m.end()) for m in MEASUREMENT.finditer(text))
    # Dictionary words can contribute contextual entities, without characters.
    spans.update((s['start'],s['end']) for s in lexical.get('spans',[]) if len(s['literal'])>=2)
    dates=[]
    for span in lexical.get('spans',[]):
        if any(era_sense(sense) for entry in span.get('candidates',[]) for sense in entry.get('senses',[])):
            suffix=DATE_SUFFIX.match(text,span['end'])
            if suffix:dates.append((span['start'],suffix.end()))
    spans.update(dates)
    from .entry_structure import extract, PERIOD, GRADE
    period_fields=[m for m in PERIOD.finditer(text) if GRADE.match(text,m.end())]
    spans.update((m.start(),m.end()) for m in period_fields)
    measurements=[(m.start(),m.end()) for m in MEASUREMENT.finditer(text)]
    # Quantity/unit parts belong to their one primary expression, never inflated
    # into several detections. Components remain separately exposed and scored.
    spans={span for span in spans if not any(a<=span[0]<span[1]<=b and span!=(a,b) for a,b in measurements+dates)}
    rows=[]; model=None
    for start,end in sorted(spans):
        options=candidates(text,start,end,lexical.get('spans',[]))
        if (start,end) in {(m.start(),m.end()) for m in period_fields}:
            options.append(_candidate('technical_sword_term',source='printed_entry_structure',prior=4.,
                support=[{'literal':text[start:end],'basis':'printed_sword_period_followed_by_grade','start':start,'end':end}]))
        if not options:continue
        if config.get('profile','contextual')=='exact':
            ranked=sorted(options,key=lambda c:-c['prior'])
            ranked=[{**c,'score':c['prior']} for c in ranked]
            model={'version':'exact-authority-baseline-v1','threshold':1.,'score_kind':'fixed_evidence_priority'}
        else:
            ranked,model=evidence_rank(text,start,end,options,context.get('role','unknown'))
        selected=ranked[0]
        uncertain=selected['category']=='unresolved' or selected['score']<model['threshold']
        rows.append({'start':start,'end':end,'literal':text[start:end],
                     'selection':selected,'alternatives':ranked[1:],'abstained':uncertain,
                     'model':model,'identity_accepted':False,'review_state':'model_proposal',
                     'links':{k:context.get(k) for k in ('document_id','source_page','group_id','section_id','figure_candidates')},
                     'uncertainty':['identity_not_established'] if selected['category'] in ('swordsmith_artisan','historical_person','family_clan') else []})
    structure=extract(text,rows,context.get('entry_index_names',()))
    for entry in structure['entries']:
        for field,category in (('era','era_date'),('province','place_province')):
            value=entry['fields'].get(field)
            if not value:continue
            evidence={'basis':'explicit_entry_bracket_'+field,'head':entry['head']}
            choice={**_candidate(category,source='printed_entry_structure',support=[{**value,**evidence}]),
                    'score':11.,'selection_evidence':['explicit_entry_field']}
            existing=next((r for r in rows if (r['start'],r['end'])==(value['start'],value['end'])),None)
            if existing:
                matching=next((c for c in [existing['selection']]+existing['alternatives'] if c['category']==category),None)
                if matching:choice={**matching,'score':11.,'selection_evidence':['explicit_entry_field']}
                existing['alternatives']=[c for c in [existing['selection']]+existing['alternatives'] if c is not matching]
                existing.update(selection=choice,entry_evidence=evidence,abstained=False,uncertainty=[])
            else:
                rows.append({**value,'selection':choice,'alternatives':[],'abstained':False,'entry_evidence':evidence,
                             'model':{'version':VERSION,'score_kind':'fixed_evidence_priority','calibrated':False},
                             'identity_accepted':False,'review_state':'model_proposal','links':{},'uncertainty':[]})
        name=entry['name']
        if not name:continue
        evidence={'basis':name['basis'],'head':entry['head'],'fields':entry['fields'],
                  'index_witnesses':[r for r in context.get('entry_index_evidence',[]) if r['literal']==name['literal']]}
        row=next((r for r in rows if (r['start'],r['end'])==(name['start'],name['end'])),None)
        if row is None:
            option={**_candidate('swordsmith_artisan',source='printed_entry_structure',
                     support=[{'literal':name['literal'],**evidence}]),'score':6.,'selection_evidence':['explicit_entry_name']}
            row={'start':name['start'],'end':name['end'],'literal':name['literal'],'selection':option,
                 'alternatives':[],'abstained':False,'model':{'version':VERSION,'score_kind':'fixed_evidence_priority','calibrated':False},
                 'identity_accepted':False,'review_state':'model_proposal','links':{},'uncertainty':['identity_not_established']}
            rows.append(row)
        if row['selection']['category']=='swordsmith_artisan':row['entry_evidence']=evidence
    for row in rows:
        if any((row['start'],row['end'])==(m.start(),m.end()) for m in period_fields):
            row['entry_evidence']={'basis':'printed_sword_period_followed_by_grade'}
        # A suffix after an established headword is an entry qualifier. Preserve
        # it as a field until its school/place/title role is actually supported.
        for entry in structure['entries']:
            suffix=entry['unresolved_head_suffix']
            if suffix and suffix['start'] <= row['start'] < row['end'] <= suffix['end']:
                choices=[o for o in [row['selection']]+row['alternatives'] if o['category'] in ('sword_school','place_province')]
                if choices and (row['start'],row['end'])==(suffix['start'],suffix['end']):
                    choice=choices[0]
                    row.update(selection=choice,alternatives=[o for o in [row['selection']]+row['alternatives'] if o is not choice],
                               entry_evidence={'basis':'attested_role_in_printed_entry_qualifier'},abstained=False,uncertainty=[])
                elif row['selection']['category'] in ('swordsmith_artisan','historical_person','sword_tradition'):
                    row['abstained']=True;row['uncertainty'].append('unresolved_entry_qualifier_role')
        if (context.get('role','unknown') not in ('unknown','heading') and not row.get('entry_evidence')
            and row['selection']['category']=='swordsmith_artisan'
            and any(o['category'] in ('sword_school','sword_tradition') and o.get('support') for o in row['alternatives'])):
            row['abstained']=True
            row['uncertainty'].append('person_or_collective_role_unresolved')
    if config.get('profile') == 'bert' and rows:
        from .bert_context import classify, examples, rerank
        decisions = classify(examples(text, [(r['start'],r['end']) for r in rows]), config)
        for row, decision in zip(rows, decisions):
            ranked, disambiguation = rerank([row['selection']]+row['alternatives'], decision)
            if MEASUREMENT.fullmatch(row['literal']):
                literal_choice=next((r for r in [row['selection']]+row['alternatives'] if r['category']=='measurement_dimension'),None)
                if literal_choice:
                    ranked=[literal_choice]+[r for r in ranked if r is not literal_choice]
                    disambiguation={**disambiguation,'state':'context_selected','reason':'explicit_printed_quantity_and_units'}
            row.update(selection=ranked[0], alternatives=ranked[1:], disambiguation=disambiguation,
                       model={**row['model'], 'context_encoder':decision['version'],
                              'base_revision':decision['base_revision'],'head_sha256':decision['head_sha256']})
            row['abstained'] = ranked[0]['score']<1. or disambiguation['state'] != 'context_selected'
            meanings={(r.get('reading'),r.get('english')) for r in ranked
                      if r['category']==ranked[0]['category'] and (r.get('reading') or r.get('english'))}
            row['sense_state']='competing_source_mappings' if len(meanings)>1 else 'source_supported_proposal'
            if disambiguation['state'] != 'context_selected':
                row['uncertainty'].append(disambiguation['reason'])
            if row['selection']['category'] in ('swordsmith_artisan','historical_person','family_clan'):
                if 'identity_not_established' not in row['uncertainty']:row['uncertainty'].append('identity_not_established')
            else:
                row['uncertainty']=[v for v in row['uncertainty'] if v!='identity_not_established']
        model=rows[0]['model']
    if config.get('profile')=='jev' and rows:
        from .jev_context import disambiguate
        disambiguate(text,rows,context,config)
        model=next((r['model'] for r in rows if r['model'].get('context_encoder')),model)
    full_names=[row for row in rows if any('full name' in tag for support in row['selection'].get('support',[]) for tag in support.get('name_types',[]))]
    eligible=[row for row in rows if not row['abstained'] and not any(full['start']<=row['start']<row['end']<=full['end'] and row is not full and row['selection']['category'] in ('family_clan','historical_person','swordsmith_artisan') for full in full_names)]
    if config.get('profile')!='exact':
        for row in eligible:
            boundary=sequence_boundary(text,row,rows)
            row['boundary']=boundary
            bounded=boundary['eligible']
            # Preserve heading/name behavior. Compound ownership still applies
            # to technical terms in headings and untyped text.
            if context.get('role','unknown') in ('unknown','heading') and boundary['basis'] not in ('inside_attested_longer_expression','inside_attested_longer_name','unmapped_size_compound') and not (row['selection']['category']=='technical_sword_term' and len(row['literal'])==1 and (_ideograph(text[row['start']-1:row['start']]) or _ideograph(text[row['end']:row['end']+1]))):
                bounded=True
            row['primary_eligible']=bounded
            if not bounded:row['uncertainty'].append(boundary['basis'])
        eligible=[r for r in eligible if r['primary_eligible']]
    # An attested whole name/technical compound owns its nested component spans.
    eligible=[row for row in eligible if not any(
        other is not row and other['start']<=row['start'] and row['end']<=other['end']
        and (other['start'],other['end'])!=(row['start'],row['end'])
        and other['selection']['category']==row['selection']['category']
        and other['selection']['category'] in ('swordsmith_artisan','technical_sword_term')
        for other in eligible)]
    # A complete source-mapped smith name owns a nested school prefix as well
    # as its given-name fragment. Both alternatives remain in candidates.
    eligible=[row for row in eligible if not any(
        other is not row and other['start']<=row['start'] and row['end']<=other['end']
        and (other['start'],other['end'])!=(row['start'],row['end'])
        and other['selection']['category']=='swordsmith_artisan'
        and any(r.get('meaning_origin')=='explicit_complete_name_mapping' for r in other['selection']['support'])
        and row['selection']['category'] in ('sword_school','swordsmith_artisan','historical_person','family_clan')
        for other in eligible)]
    selected=compatible(eligible)
    keys={(r['start'],r['end']) for r in selected}
    for row in rows:row['selected_group']=(row['start'],row['end']) in keys
    # One whole name owns its family/given-name components; never infer a member.
    for row in selected:
        if row['literal'].startswith(('徳川','德川')):
            row['name_parts']=[{'role':'family','literal':row['literal'][:2],'start':row['start'],'end':row['start']+2}]
            if len(row['literal'])>2:row['name_parts'].append({'role':'given_name','literal':row['literal'][2:],'start':row['start']+2,'end':row['end']})
    from .japanese_clauses import analyze
    return {'version':VERSION,'state':'proposals','mentions':selected,'candidates':rows,
            'interpretation':analyze(text,selected),
            'entry_structure':structure,'model':model,'changes_characters':False,'automatic_promotion':False}
