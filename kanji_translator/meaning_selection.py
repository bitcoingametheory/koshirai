"""Separate source English fragments, lexical candidates and selected meanings.

Shape screening is never semantic verification. Human-reviewed local mappings
remain explicit attestations; dictionary selections remain dictionary proposals.
"""
import re

VERSION = 'meaning-selection-v1'


def english_quality(value):
    if not isinstance(value, str) or not value.strip():
        return {'state': 'absent', 'eligible': False, 'verified': False}
    text = value.strip()
    words = re.findall(r"[A-Za-z]+", text)
    reason = None
    if len(text) > 80 or len(words) > 8:
        reason = 'prose_or_oversized'
    elif text.endswith(('-', '/', '(')) or re.search(r'[a-z][A-Z]', text):
        reason = 'fragment_or_joined_words'
    elif re.search(r'\b(?:he|his|her|they|their|occasionally|generally|including|includes?|found|lived|studied|worked|having|predating|son|father|grandson|nephew|brother)\b', text, re.I):
        reason = 'contextual_prose_or_biography'
    elif re.search(r'\bunder\b',text,re.I) and not re.search(r'\bunder (?:\d+(?:\.\d+)?|one|two|three|ten|twenty|thirty|forty|fifty|sixty) (?:centimetres?|centimeters?|millimetres?|millimeters?|inches?|feet)\b',text,re.I):
        reason = 'contextual_prose_or_biography'
    elif re.search(r'\b(?:fam|family|school|province|line|period|group)\b', text, re.I):
        reason = 'name_or_historical_context'
    elif text.casefold() in {'cm', 'mm', 'm', 'in', 'inch', 'inches'}:
        reason = 'unit_without_aligned_value'
    elif re.fullmatch(r'[A-Z] [a-z][a-z -]+', text):
        reason = 'alphabetical_index_fragment'
    elif not words or not re.fullmatch(r"[A-Za-z][A-Za-z0-9 '’()/\-]*\.?", text):
        reason = 'unsupported_form'
    return {'state': 'quarantined_candidate' if reason else 'lexical_candidate',
            'eligible': reason is None, 'verified': False,
            'reason': reason or 'source_alignment_and_sense_require_review'}


def source_glosses(domain):
    result = []
    seen = set()
    for item in domain.get('assertions', []) + domain.get('smith_name_candidates', []):
        value = item.get('english')
        if not value:
            continue
        key = (item.get('source'), item.get('entry_id'), item.get('literal'), value)
        if key in seen:
            continue
        seen.add(key)
        result.append({'english': value, 'source': item.get('source'),
                       'entry_id': item.get('entry_id'),
                       'literal': item.get('literal'), **english_quality(value)})
    return result


def select(span):
    """Select only a unique supported lexical sense; otherwise explicitly abstain.

    This deliberately does not convert a printed person's name into a gloss,
    collapse conflicting identities, or let a filtered source string become a
    reviewed translation. Synonymous glosses in one dictionary sense stay grouped.
    """
    domain = span.get('domain', {})
    result = {'version': VERSION, 'reading': None, 'english': None,
              'state': 'abstained', 'reason': 'ambiguous_or_unsupported',
              'verified': False, 'identity_accepted': False,
              'source_english_candidates': source_glosses(domain)}
    local = [row for row in domain.get('local_mappings', [])
             if row.get('decision') == 'accept' and row.get('english')]
    local_values = {(r.get('reading'), r['english']) for r in local}
    if len(local_values) == 1:
        reading, english = next(iter(local_values))
        return {**result, 'reading': reading, 'english': english,
                'state': 'local_review_attestation', 'reason': 'one_local_mapping',
                'support': local}
    if len(local_values) > 1:
        return {**result, 'reason': 'conflicting_local_reviews'}
    source_readings = {r['printed_romaji'] for r in
                       domain.get('assertions', []) + domain.get('smith_name_candidates', [])
                       if r.get('printed_romaji')}
    if len(source_readings) == 1:
        result['reading'] = next(iter(source_readings))
    senses = {}
    for candidate in span.get('candidates', []):
        for sense in candidate.get('senses', []):
            if sense.get('name_types') or sense.get('role') == 'trans':
                continue
            glosses = [g for g in sense.get('english', []) if isinstance(g, str) and g.strip()]
            if not glosses:
                continue
            key = (candidate.get('source'), candidate.get('entry_id'),
                   candidate.get('kana'), sense.get('ordinal'))
            senses[key] = (candidate, glosses)
    if len(senses) > 1:
        supported = {r['english'].casefold() for r in result['source_english_candidates']
                     if r['eligible']}
        agreeing = {key: value for key, value in senses.items()
                    if supported.intersection(g.casefold() for g in value[1])}
        if len(agreeing) == 1:
            senses = agreeing
            result['domain_sense_agreement'] = True
    if len(senses) != 1:
        result['sense_count'] = len(senses)
        return result
    candidate, glosses = next(iter(senses.values()))
    roman = candidate.get('romaji') or {}
    reading = roman.get('hepburn-expanded-v1', roman.get('hepburn')) if isinstance(roman, dict) else None
    result.update(english=glosses[0], english_alternatives=glosses,
                  reading=(result['reading'] or reading) if len(source_readings)<=1 else None, state='dictionary_proposal',
                  reason='one_applicable_dictionary_sense',
                  support={'source': candidate.get('source'), 'entry_id': candidate.get('entry_id'),
                           'kana': candidate.get('kana'), 'variant_path': candidate.get('variant_path', [])})
    return result
