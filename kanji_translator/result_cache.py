"""Content-addressed optional derived cache; every routing dependency is explicit."""
import json
from pathlib import Path
from .request_contracts import canonical,digest
DEPENDENCIES=('source_sha256','crop_sha256','geometry','orientation','style','normalization_rules','lexicon_sha256','review_sha256','ocr_config','adapter_version')
def cache_key(identity):
    missing=[k for k in DEPENDENCIES if k not in identity]
    if missing:raise ValueError('Incomplete cache identity: '+','.join(missing))
    return digest(canonical(identity))
def read_cache(root,identity):
    path=Path(root)/(cache_key(identity)+'.json')
    if not path.exists():return None
    envelope=json.loads(path.read_bytes())
    if envelope.get('key')!=cache_key(identity) or digest(canonical(envelope['result']))!=envelope.get('result_sha256'):raise ValueError('Corrupt cache')
    return envelope['result']
def write_cache(root,identity,result):
    root=Path(root);root.mkdir(parents=True,exist_ok=True);key=cache_key(identity)
    path=root/(key+'.json');data=canonical({'key':key,'result_sha256':digest(canonical(result)),'result':result})
    temp=path.with_suffix('.partial');temp.write_bytes(data);temp.replace(path)


def stage_identity(stage,identity,dependencies):
    if stage not in ('reading','translation','lexical'):raise ValueError('Unknown enrichment cache stage')
    return {**{key:None for key in DEPENDENCIES},**identity,'stage':stage,'stage_schema':'kanji-stage-cache-v1','dependencies':dependencies}
