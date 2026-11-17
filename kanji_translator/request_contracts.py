"""Finite public request validation and deterministic serialization."""
import hashlib,json
SCHEMA='kanji-pipeline-v1'
def digest(data):return hashlib.sha256(data).hexdigest()
def canonical(value):return json.dumps(value,ensure_ascii=False,sort_keys=True,separators=(',',':')).encode('utf-8')
def require_hash(value,label='sha256'):
    if not isinstance(value,str) or len(value)!=64 or any(c not in '0123456789abcdef' for c in value):raise ValueError('Invalid '+label)
    return value

ENRICHMENT_SCHEMA='kanji-enrichment-v1'
def reference_request(request):
    text=request.get('text');limit=request.get('limit',12);max_bytes=request.get('max_bytes',16384)
    if not isinstance(text,str) or not 1<=len(text.strip())<=200 or '\x00' in text:raise ValueError('Use a bounded literal reference query')
    if type(limit) is not int or not 1<=limit<=50 or type(max_bytes) is not int or not 1024<=max_bytes<=65536:
        raise ValueError('Reference limits must be 1–50 hits and 1024–65536 passage bytes')
    return {**request,'text':text,'limit':limit,'max_bytes':max_bytes}

def validate_request(request):
    for key in ('lexical_config','semantic_config','ocr_config','image_config','reference_config'):
        if not isinstance(request.get(key,{}),dict):raise ValueError(key+' must be an object')
    queries=request.get('reference_queries',[])
    if not isinstance(queries,list) or len(queries)>8 or any(not isinstance(q,str) or not 1<=len(q.strip())<=200 or '\x00' in q for q in queries):
        raise ValueError('Use at most eight bounded literal reference queries')
    for query in queries:reference_request({**request.get('reference_config',{}),'text':query})
    retired = bool(request.get('vision_config') or request.get('vision_limit',0) or request.get('experimental_proposals'))
    retired |= request.get('enhancement_config',{}).get('profile','disabled')!='disabled'
    retired |= bool(request.get('translation_config',{}).get('enabled'))
    if retired:
        raise ValueError('Character rewriting, generative translation and legacy enhancement profiles are retired. Use native NDLOCR followed by semantic_config.profile=contextual; retain source-reviewed corrections separately.')
    if request.get('semantic_config',{}).get('profile','contextual') not in ('contextual','exact','bert','jev'):
        raise ValueError('Semantic profile must be contextual, exact, bert or jev')
    from .readers.ocr import backend
    backend(request.get('ocr_config',{}))
