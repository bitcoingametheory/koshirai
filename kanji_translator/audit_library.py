"""Count retained mappings and inspect every stored English pair reproducibly."""
import argparse
from collections import Counter, defaultdict
import json
from pathlib import Path
import re
from .meaning_selection import english_quality
from .sword_library import bundle


def audit():
    data, manifest = bundle()
    forms = set()
    pairs = defaultdict(list)
    both = set()
    source_counts = defaultdict(Counter)
    for kind in ('terms', 'forms', 'names'):
        for row in data[kind]:
            literal = row.get('literal')
            if not literal or not re.fullmatch('[\u3400-\u9fff\U00020000-\U000323af]+', literal):
                continue
            forms.add(literal)
            english = row.get('english')
            source_counts[row['source']]['forms'] += 1
            if not english:
                continue
            quality = english_quality(english)
            source_counts[row['source']][quality['state']] += 1
            pairs[literal, english].append({'source': row['source'], 'kind': kind,
                                           'reading': row.get('printed_romaji')})
            if row.get('printed_romaji'):
                both.add(literal)
    rows = [{'literal': literal, 'english': english, 'length': len(literal),
             **english_quality(english), 'sources': sources}
            for (literal, english), sources in sorted(pairs.items())]
    lengths = []
    for n in (1, 2, 3, 4, 5, '6–12'):
        include = lambda s: len(s) == n if isinstance(n, int) else len(s) >= 6
        selected = [row for row in rows if include(row['literal'])]
        lengths.append({'length': n, 'spellings': sum(include(s) for s in forms),
                        'with_direct_english': len({row['literal'] for row in selected}),
                        'stored_pairs': len(selected),
                        'lexical_candidates': sum(row['eligible'] for row in selected),
                        'quarantined_pairs': sum(not row['eligible'] for row in selected),
                        'same_record_reading_and_english': sum(include(s) for s in both),
                        'verified_pair_count': None})
    return {'schema': 'library-mapping-audit-v1', 'bundle_sha256': manifest['sha256'],
            'rule': 'Distinct all-kanji literal fields in terms, names and forms; no alias-table inflation.',
            'qualification': 'Every stored pair is screened; screening does not verify source alignment or semantic accuracy.',
            'lengths': lengths, 'source_counts': dict(source_counts),
            'pairs': rows, 'verified_english_accuracy': None}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    args.output.write_text(json.dumps(audit(), ensure_ascii=False, indent=2) + '\n')


if __name__ == '__main__':
    main()
