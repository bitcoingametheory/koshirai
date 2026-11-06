"""Local pages -> regions -> OCR -> core Japanese -> sword facts -> review files."""
import argparse,json,re,hashlib,os
from pathlib import Path
from .data_paths import data_dir,external

SUPPORTED={'.png','.jpg','.jpeg','.tif','.tiff','.pdf'}
def natural(path):
    return tuple((1,int(part)) if part.isdigit() else (0,part.casefold()) for part in re.split(r'(\d+)',path.as_posix()))

def scan(folder,output,*,config=None,max_pages=None):
    from . import parse
    folder=Path(folder).expanduser().resolve();output=external(output)
    if not folder.is_dir():raise ValueError('Input must be a local folder')
    if output==folder or output.is_relative_to(folder):raise ValueError('Output must be outside the input folder')
    if output.exists() and any(output.iterdir()):raise ValueError('Choose an empty output folder for this run')
    output.mkdir(parents=True,exist_ok=True)
    config=dict(config or {});root=external(data_dir())
    config.setdefault('cache_dir',str(root/'cache'))
    config.setdefault('lexical_config',{'path':str(root/'lexicon.sqlite3')})
    paths=sorted((p for p in folder.rglob('*') if p.is_file() and p.suffix.lower() in SUPPORTED),key=lambda p:natural(p.relative_to(folder)))
    if not paths:raise ValueError('No supported PNG, JPEG, TIFF or PDF files found')
    summary={'schema':'folder-results-v1','pages':0,'regions':0,'unresolved_regions':0,'unlocated_ocr_regions':0,'errors':0,'stopped_at_limit':False,'automatic_promotion':False,'pipeline':['source','structure and reading order','literal NDLOCR','supported span grouping','contextual semantic selection','linked results and corrections'],'semantic_mentions':0}
    def write(stream,row):stream.write(json.dumps(row,ensure_ascii=False)+'\n');stream.flush()
    summary['relation_proposals']=0
    with (output/'results.jsonl').open('w',encoding='utf-8') as results,(output/'unresolved.jsonl').open('w',encoding='utf-8') as unresolved,(output/'text.txt').open('w',encoding='utf-8') as text,(output/'raw_ndl.txt').open('w',encoding='utf-8') as raw_text,(output/'terms.jsonl').open('w',encoding='utf-8') as terms,(output/'interpretations.jsonl').open('w',encoding='utf-8') as interpretations:
        for path in paths:
            raw=path.read_bytes();sha=hashlib.sha256(raw).hexdigest();kind='pdf' if path.suffix.lower()=='.pdf' else 'image'
            try:
                if kind=='pdf':
                    import pymupdf
                    with pymupdf.open(path) as doc:count=len(doc)
                else:
                    from PIL import Image
                    with Image.open(path) as image:count=getattr(image,'n_frames',1)
            except Exception as error:
                summary['errors']+=1;write(unresolved,{'file':str(path.relative_to(folder)),'error':str(error),'state':'unresolved'});continue
            for page in range(count):
                if max_pages is not None and summary['pages']>=max_pages:
                    summary['stopped_at_limit']=True;break
                label={'file':str(path.relative_to(folder)),'page':page+1,'source_sha256':sha}
                try:
                    result=parse({**config,'kind':kind,'path':str(path),'sha256':sha,'page':page})
                    write(results,{**label,'result':result})
                    summary['pages']+=1;summary['regions']+=len(result['regions'])
                    summary['semantic_mentions']+=len(result.get('semantic_mentions',[]))
                    for mention in result.get('semantic_mentions',[]):write(terms,{**label,**mention})
                    for unit in result.get('japanese_interpretations',[]):
                        write(interpretations,{**label,**unit})
                        summary['relation_proposals']+=len(unit['claims'])
                    heading='\n'+label['file']+' page '+str(page+1)+'\n'
                    raw_text.write(heading+result['raw_ndl_transcript']+'\n')
                    text.write('\n'+label['file']+' page '+str(page+1)+'\n')
                    unlocated=(result.get('native_payload') or {}).get('unlocated_ocr_regions',[])
                    summary['unlocated_ocr_regions']+=len(unlocated)
                    summary['unresolved_regions']+=len(unlocated)
                    for item in unlocated:
                        write(unresolved,{**label,'state':'requires_review','reason':'ndlocr_box_outside_image','region':item})
                    for row in result['enrichment']['regions']:
                        text.write(row['literal_text']+'\n')
                        if row['abstained'] or row['lexical'].get('unknown_offsets') or row['lexical'].get('state')=='unavailable':
                            summary['unresolved_regions']+=1;write(unresolved,{**label,'region':row,'state':'requires_review'})
                except (ValueError,OSError,RuntimeError,ImportError) as error:
                    summary['errors']+=1;summary['pages']+=1
                    write(unresolved,{**label,'error':str(error),'state':'unresolved'})
            if summary['stopped_at_limit']:break
    (output/'summary.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    return summary

def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('input',type=Path,help='Any local folder of page images and PDFs (searched recursively)')
    parser.add_argument('--output',type=Path,help='Empty external result folder')
    parser.add_argument('--data-dir',type=Path,help='One external application home for dictionaries, environment, reviews, cache and outputs')
    parser.add_argument('--config',type=Path,help='External private JSON with OCR/image/lexical configuration')
    parser.add_argument('--semantic-profile',choices=('contextual','exact','bert','jev'),help='Use cited source priority, local BERT or opt-in Jev disambiguation')
    parser.add_argument('--max-pages',type=int,help='Optional bounded run')
    args=parser.parse_args(argv)
    try:
        if args.data_dir:os.environ['KANJI_DATA_DIR']=str(external(args.data_dir))
        if args.max_pages is not None and args.max_pages<1:raise ValueError('max-pages must be positive')
        config=json.loads(args.config.read_text(encoding='utf-8')) if args.config else {}
        if args.semantic_profile:
            config['semantic_config']={**config.get('semantic_config',{}),'profile':args.semantic_profile}
        from datetime import datetime,timezone
        output=args.output or data_dir()/'outputs'/datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')
        summary=scan(args.input,output,config=config,max_pages=args.max_pages)
        print(json.dumps({'output':str(output),**summary},ensure_ascii=False));return 2 if summary['errors'] else 0
    except (ValueError,OSError,ImportError,RuntimeError) as error:parser.exit(2,str(error)+'\n')
