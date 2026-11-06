"""The sole public executable parser entry point; JSON in, deterministic JSON out."""
import argparse,json,sys
from . import parse,candidate_lookup as candidates,read_retained
from .request_contracts import canonical
from .source_evidence import export_reviewed
from .reviewed_readings import record_review

def main(argv=None,*,operations=None):
    args_list=list(sys.argv[1:] if argv is None else argv)
    if args_list and args_list[0]=='scan':
        from .scan_folder import main as scan_main
        return scan_main(args_list[1:])
    parser=argparse.ArgumentParser(description='Canonical native/retained kanji parser and evidence proposals')
    parser.add_argument('operation',choices=('parse','candidates','read-retained','export-reviewed','record-review','corpus-ingest','corpus-inspect','corpus-review','lookup'))
    parser.add_argument('--request',default='-',help='JSON request path, or - for stdin')
    args=parser.parse_args(argv)
    try:
        request=json.load(sys.stdin if args.request=='-' else open(args.request,encoding='utf-8'))
        handlers={'parse':parse,'candidates':candidates,'read-retained':read_retained,'export-reviewed':export_reviewed,'record-review':record_review}
        from . import research_corpus as corpus,sword_library as sword
        handlers.update({'corpus-ingest':corpus.ingest,'corpus-inspect':corpus.inspect,'corpus-review':corpus.review,'lookup':lambda r:sword.lookup(r['text'])})
        handlers.update(operations or {})
        result=handlers[args.operation](request)
        sys.stdout.buffer.write(canonical(result)+b'\n');return 0
    except (ValueError,KeyError,OSError,ImportError,TypeError,RuntimeError) as error:
        sys.stderr.write(type(error).__name__+': '+str(error)+'\n');return 2
