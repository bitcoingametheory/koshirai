"""Read a hash-bound library OCR snapshot without OCR calls or line joining."""
import copy
import json
import math
from pathlib import Path
from ...request_contracts import digest, require_hash


def read(request):
    """Select one explicit source/PDF page from a saved {source, pages} export.

    Line boxes use the saved render's pixel coordinates. No DPI, edition, image
    identity, review status or reading order is inferred from a page number.
    Corrected/ordered/alternate outputs stay in the payload, separate from raw.
    """
    raw = Path(request['path']).read_bytes()
    if digest(raw) != require_hash(request['sha256'], 'snapshot sha256'):
        raise ValueError('Retained OCR snapshot hash mismatch')
    snapshot = json.loads(raw)
    source = snapshot['source']
    source_sha = require_hash(source['sha256'], 'retained source sha256')
    page_number = request.get('page')
    if type(page_number) is not int or page_number < 1:
        raise ValueError('Retained OCR page is a one-based PDF page number')
    if request.get('source_id') != source['id']:
        raise ValueError('Retained OCR source_id must match the snapshot')
    pages = [p for p in snapshot['pages'] if p['source_id'] == source['id'] and p['page'] == page_number]
    if len(pages) != 1:
        raise ValueError('Retained OCR needs exactly one matching source/page')
    page = pages[0]
    if not isinstance(page.get('text_raw'), str) or not isinstance(page.get('lines'), list) or not page.get('engine'):
        raise ValueError('Retained OCR requires raw text, native lines and engine provenance')
    regions = []
    for index, line in enumerate(page['lines']):
        text, points = line.get('t'), line.get('b')
        if not isinstance(text, str) or not isinstance(points, list) or len(points) != 4:
            raise ValueError('Invalid retained OCR line text or polygon')
        if any(not isinstance(p, list) or len(p) != 2 or any(type(v) not in (int, float) or not math.isfinite(v) or v < 0 for v in p) for p in points):
            raise ValueError('Invalid retained OCR geometry')
        box = [min(p[0] for p in points), min(p[1] for p in points), max(p[0] for p in points), max(p[1] for p in points)]
        if box[0] >= box[2] or box[1] >= box[3]:
            raise ValueError('Empty retained OCR geometry')
        region_id = f'source:{source["id"]}:pdf:{page_number}:line:{index}'
        regions.append({'region_id': region_id, 'text': text, 'geometry': box,
                        'role': 'text_line', 'origin': 'retained_library_ocr',
                        'orientation': 'vertical' if line.get('v') is True else 'horizontal' if line.get('v') is False else 'unknown',
                        'identity': {'source_sha256': source_sha, 'snapshot_sha256': request['sha256'],
                                     'source_id': source['id'], 'pdf_page': page_number,
                                     'printed_page': page.get('printed_page'), 'locator': region_id,
                                     'engine': copy.deepcopy(page['engine']), 'native_polygon': copy.deepcopy(points)},
                        'page_ocr': {'text': text, 'confidence': line.get('c'),
                                     'state': 'retained_proposal', 'accuracy_qualified': False,
                                     'engine_pin': copy.deepcopy(page['engine'])}})
    from ...entry_structure import retained_witnesses
    payload = {'origin': 'retained_library_ocr', 'source': copy.deepcopy(source),
               'entry_witnesses':retained_witnesses(page),
               'snapshot_sha256': request['sha256'], 'page': copy.deepcopy(page),
               'raw_transcript': page['text_raw'], 'line_transcript': '\n'.join(r['text'] for r in regions),
               'reading_order_policy': 'Native line order retained; ordered/corrected text is a separate source field',
               'geometry_scope': 'Saved render pixels; no inferred cross-edition coordinates',
               'page_ocr_metrics': {'ocr_calls': 0, 'ocr_cache_hits': 0}}
    return regions, payload
