"""Finite public request validation and deterministic serialization."""
import hashlib,json
SCHEMA='kanji-pipeline-v1'
def digest(data):return hashlib.sha256(data).hexdigest()
def canonical(value):return json.dumps(value,ensure_ascii=False,sort_keys=True,separators=(',',':')).encode('utf-8')
def require_hash(value,label='sha256'):
    if not isinstance(value,str) or len(value)!=64 or any(c not in '0123456789abcdef' for c in value):raise ValueError('Invalid '+label)
    return value

ENRICHMENT_SCHEMA='kanji-enrichment-v1'
def validate_request(request):
    for key in ('lexical_config','semantic_config','ocr_config','image_config'):
        if not isinstance(request.get(key,{}),dict):raise ValueError(key+' must be an object')
    retired = bool(request.get('vision_config') or request.get('vision_limit',0) or request.get('experimental_proposals'))
    retired |= request.get('enhancement_config',{}).get('profile','disabled')!='disabled'
    retired |= bool(request.get('translation_config',{}).get('enabled'))
    if retired:
        raise ValueError('Character rewriting, generative translation and legacy enhancement profiles are retired. Use native NDLOCR followed by semantic_config.profile=contextual; retain source-reviewed corrections separately.')
    if request.get('semantic_config',{}).get('profile','contextual') not in ('contextual','exact','bert','jev'):
        raise ValueError('Semantic profile must be contextual, exact, bert or jev')
    if request.get('ocr_config',{}).get('backend','ndl')!='ndl':
        raise ValueError('The current scan pipeline uses NDLOCR; the Tesseract route is retired')
