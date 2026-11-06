"""Install the pinned Japanese BERT encoder into an external directory."""
import argparse
import json
from importlib.resources import files
from pathlib import Path
import urllib.request

from .data_paths import external
from .request_contracts import digest


def install(target):
    target = external(target)
    target.mkdir(parents=True, exist_ok=True)
    manifest = json.loads(files('kanji_translator').joinpath('resources/bert_base_manifest.json').read_text())
    for name, sha in manifest['files'].items():
        path = target/name
        if path.exists() and digest(path.read_bytes()) == sha:
            continue
        url = f"https://huggingface.co/{manifest['model_id']}/resolve/{manifest['revision']}/{name}"
        partial = path.with_suffix('.partial')
        try:
            with urllib.request.urlopen(url, timeout=120) as response, partial.open('wb') as stream:
                while block := response.read(1024*1024):
                    stream.write(block)
            if digest(partial.read_bytes()) != sha:
                raise ValueError('Downloaded BERT file hash mismatch: '+name)
            partial.replace(path)
        finally:
            partial.unlink(missing_ok=True)
    (target/'koshirai_base.json').write_text(json.dumps(manifest, indent=2)+'\n')
    return manifest


def main():
    from .bert_context import base_path
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--target', type=Path)
    args = parser.parse_args()
    manifest = install(args.target or base_path())
    print(json.dumps({'state':'installed','model':manifest['model_id'],'revision':manifest['revision']}))


if __name__ == '__main__':
    main()
