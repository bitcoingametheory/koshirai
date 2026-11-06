"""Cache the single literal lexical stage; semantic interpretation follows it."""
from .result_cache import stage_identity,read_cache,write_cache

def cached(stage,identity,dependencies,request,metrics,compute):
    dep=stage_identity(stage,identity,dependencies);root=request.get('cache_dir')
    value=read_cache(root,dep) if root else None
    if value is not None:metrics[stage+'_cache_hits']+=1;return value
    value=compute();metrics[stage+'_calls']+=int(value.get('executed',True))
    if root and value.get('reason')!='local_runtime_failure':write_cache(root,dep,value)
    return value

def lookup_lexical(literal,identity,context,request,metrics):
    from .dictionary_lookup import read,identity as lexical_identity,MASTER
    lc=request.get('lexical_config',{})
    if not lc.get('enabled',True):return {'state':'disabled','spans':[]}
    li=lexical_identity(lc.get('path',MASTER),lc.get('profile','modern'))
    return cached('lexical',identity,{'literal':literal,'identity':li,'config':lc,'document_context':context},request,metrics,lambda:read(literal,lc))
