"""Bounded Japanese relation proposals and evidence-linked English presentation.

The Japanese clause and codepoint spans are authoritative. English renders only
recognized relations between cited mentions; it is not a sentence translator.
Unrecognized scope, quotations and complex negation remain visible for review.
"""
import re
from .request_contracts import canonical, digest

VERSION = 'native-japanese-relations-v1'
TECHNICAL = {'technical_sword_term','measurement_dimension'}
NAMES = {'swordsmith_artisan','historical_person','family_clan'}
MODAL = re.compile(r'(?:と(?:も)?(?:伝[えへ]られ|言われ|云われ|され|いわれ)|(?:かもしれ|かも知れ)|であろう|であらう|と思[わは]れ|と(?:み|見)られ)')
COMPLEX = re.compile(r'(?:ないこと[もは]ない|なくはない|とは限ら|に限ら|わけでは|訳では|なければ|ならば|たら|ても|とすれば|かどうか|見ないわけ|ぬわけ)')
MIX = re.compile(r'(?:交[じり]|混[じり])(?:らない|らず|らぬ|る|り|って|じる)?|交る|混る')
OBSERVED = re.compile(r'(?:見られ(?:ない|ず|ぬ|る)|認め(?:られ)?(?:ない|ず|ぬ|る)|(?:現|表)[れは](?:ない|ず|ぬ|る)|(?:つ|付)(?:かない|かず|かぬ|く|き|いて)|(?:有|あ)(?:る|り)|(?:無|な)(?:い|く)|なし)')
NEGATIVE = re.compile(r'(?:ない|ず|ぬ|なし|無い|無く|なく)$')


def source_span(text, start, end):
    return {'start':start,'end':end,'literal':text[start:end]}


def _label(mention):
    selection=mention['selection']
    if selection['category'] in NAMES:
        # A reading is a name spelling, never a resolved historical individual.
        return selection.get('reading')
    return selection.get('english')


def _render(kind, labels, polarity, modality):
    if not all(labels):return None
    a=labels[0];b=labels[1] if len(labels)>1 else None
    negative=polarity=='negative'
    wording={
        'mixed_with':f'{a} '+('does not mix with ' if negative else 'is mixed with ')+str(b),
        'described_as':f'{a} '+('is not described as ' if negative else 'is described as ')+str(b),
        'resembles':f'{a} '+('does not resemble ' if negative else 'resembles ')+str(b),
        'observed':('Not observed: ' if negative else 'Present: ')+a,
        'child_of':f'{a} '+('is not stated to be a child of ' if negative else 'is stated to be a child of ')+str(b),
        'student_of':f'{a} '+('is not stated to be a student of ' if negative else 'is stated to be a student of ')+str(b),
        'more_frequent_than':f'{a} '+('is not more frequent than ' if negative else 'is more frequent than ')+str(b),
    }[kind]
    if modality=='reported':wording='The passage reports: '+wording
    if modality=='possible':wording='The passage suggests: '+wording
    return wording+'.'


def analyze(text, mentions):
    """Recognize closed constructions; never turn a bag of terms into a claim."""
    clauses=[];claims=[]
    # Do not cross native newlines, punctuation or entry markers.
    for boundary in re.finditer(r'[^。！？!?\n◇◆▽]+[。！？!?]?',text):
        start,end=boundary.span();value=text[start:end]
        members=[m for m in mentions if start<=m['start']<m['end']<=end]
        members.sort(key=lambda m:(m['start'],m['end']))
        clause_id=digest(canonical([VERSION,start,end,value]))
        clause={'clause_id':clause_id,**source_span(text,start,end),'mention_spans':[[m['start'],m['end']] for m in members],
                'claim_ids':[],'status':'unparsed','unresolved':['No supported complete construction recognized.']}
        if any(c in value for c in '「」『』') or COMPLEX.search(value):
            clause['unresolved']=['Quotation, conditional or complex negation requires scope review.']
            clauses.append(clause);continue

        def emit(kind,arguments,cue_start,cue_end,polarity='positive'):
            # A bare connective predicate does not justify a complete assertion
            # if later clause text can change its scope. Keep only a local claim.
            tail=text[cue_end:end]
            modal=MODAL.match(tail)
            if re.search(r'とは(?:思|考|言[えへ]|云[えへ]|い[えへ])|こと(?:は|も|が)?(?:ない|なく|なか)|わけ|訳|限ら|なかった|なかつた|ありません|おらず|ゐない|いない',tail):return
            modality='reported' if modal and re.match(r'と(?:も)?(?:伝|言|云|され|いわれ)',modal[0]) else 'possible' if modal else 'asserted'
            evidence=[]
            for m in arguments:
                selected=m['selection']
                evidence.append({'span':source_span(text,m['start'],m['end']),
                                 'category':selected['category'],'reading':selected.get('reading'),
                                 'english':selected.get('english'),'support':selected.get('support',[]),
                                 'identity_accepted':False})
            labels=[_label(m) for m in arguments]
            claim={'relation':kind,'arguments':[source_span(text,m['start'],m['end']) for m in arguments],
                   'cue':source_span(text,cue_start,cue_end),'polarity':polarity,'modality':modality,
                   'modality_evidence':source_span(text,cue_end+modal.start(),cue_end+modal.end()) if modal else None,
                   'evidence':evidence,'english':_render(kind,labels,polarity,modality),
                   'state':'rule_proposal','identity_accepted':False,'clause_id':clause_id,
                   'unresolved':[] if all(labels) else ['An argument lacks a supported English gloss or reading.']}
            claim['claim_id']=digest(canonical([VERSION,clause_id,kind,claim['arguments'],claim['cue'],polarity,modality]))
            if claim['claim_id'] not in clause['claim_ids']:
                claims.append(claim);clause['claim_ids'].append(claim['claim_id'])

        for i,a in enumerate(members):
            category=a['selection']['category'];after=text[a['end']:end]
            if category in TECHNICAL:
                obs=re.match(r'(?:が|は|も)?\s*',after)
                predicate=OBSERVED.match(after,obs.end())
                if predicate:
                    stop=a['end']+predicate.end();tail=text[stop:end]
                    if not re.match(r'(?:よう|もの|こと|筈|はず|べき|とは|な|ず)',tail):
                        emit('observed',[a],a['end'],stop,'negative' if NEGATIVE.search(predicate[0]) else 'positive')
            if i+1>=len(members):continue
            b=members[i+1];gap=text[a['end']:b['start']];after=text[b['end']:end]
            if category in TECHNICAL and b['selection']['category'] in TECHNICAL:
                if re.fullmatch(r'\s*(?:に|と)\s*',gap):
                    lead=re.match(r'(?:が|は|も)?\s*',after);predicate=MIX.match(after,lead.end())
                    if predicate:
                        emit('mixed_with',[a,b],a['end'],b['end']+predicate.end(),'negative' if NEGATIVE.search(predicate[0]) else 'positive')
                if re.fullmatch(r'\s*は\s*',gap):
                    similar=re.match(r'に似(?:ない|ず|ぬ|る|ている|てゐる)',after)
                    if similar:
                        emit('resembles',[a,b],a['end'],b['end']+similar.end(),'negative' if NEGATIVE.search(similar[0]) else 'positive')
                    else:
                        predicate=re.match(r'(?:ではない|でない|である|なり|で|だ)?(?=[、，,。！？!?]|$)',after)
                        if predicate:emit('described_as',[a,b],a['end'],b['end']+predicate.end(),'negative' if 'ない' in predicate[0] else 'positive')
                if re.fullmatch(r'\s*より\s*',gap):
                    more=re.match(r'が多(?:くない|い)',after)
                    if more:emit('more_frequent_than',[b,a],a['end'],b['end']+more.end(),'negative' if 'ない' in more[0] else 'positive')
            if category in NAMES and b['selection']['category'] in NAMES and gap in ('は','が'):
                relation=re.match(r'の(子|弟子|門人)(ではない|でない|である|なり|だ)?(?=[、，,。！？!?]|$)',after)
                if relation:emit('child_of' if relation[1]=='子' else 'student_of',[a,b],a['end'],b['end']+relation.end(),'negative' if 'ない' in relation[0] else 'positive')
        if clause['claim_ids']:
            clause['status']='partial_interpretation'
            clause['unresolved']=['Only the listed constructions are interpreted; remaining wording is not translated.']
        clauses.append(clause)
    return {'version':VERSION,'language':'ja','clauses':clauses,'claims':claims,
            'english_scope':'Evidence-linked relation summaries, not a full passage translation',
            'changes_characters':False,'automatic_promotion':False}
