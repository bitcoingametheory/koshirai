"""Publish frozen prediction evidence without machine-local crop cache paths."""
import argparse
import gzip
import json
from pathlib import Path


def export(source, output):
    rows=[json.loads(line) for line in source.read_text().splitlines()]
    omitted=0
    for row in rows:
        for node in row.get('supporting',{}).get('document_groups',{}).get('nodes',[]):
            fields=node.get('source_fields') or {}
            if 'crop' in fields:
                del fields['crop']
                omitted+=1
    encoded=('\n'.join(json.dumps(row,ensure_ascii=False,separators=(',',':')) for row in rows)+'\n').encode()
    output.write_bytes(gzip.compress(encoded,mtime=0))
    return {'pages':len(rows),'omitted_local_crop_paths':omitted,
            'policy':'Only source_fields.crop cache paths are omitted. Source hashes, geometry, text, candidates and decisions are retained.'}


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args()
    print(json.dumps(export(args.source,args.output)))
