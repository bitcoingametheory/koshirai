"""Credential-free HTTPS downloads and repeatable external public-data build."""
import argparse,contextlib,json,os,shutil,tempfile,subprocess,urllib.parse,urllib.request
from datetime import datetime,timezone
from pathlib import Path
from .dictionary_sources import build,sha256
from .data_paths import data_dir,external
SOURCES={
    'jmdict':('JMdict_e.gz','https://www.edrdg.org/pub/Nihongo/JMdict_e.gz'),
    'jmnedict':('JMnedict.xml.gz','https://www.edrdg.org/pub/Nihongo/JMnedict.xml.gz'),
    'kanjidic2':('kanjidic2.xml.gz','https://www.edrdg.org/kanjidic/kanjidic2.xml.gz'),
}
TERMS='https://www.edrdg.org/edrdg/licence.html'
class PublicRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self,req,fp,code,msg,headers,newurl):
        parsed=urllib.parse.urlparse(newurl)
        if parsed.scheme!='https' or parsed.hostname not in ('www.edrdg.org','edrdg.org') or parsed.username or parsed.password:
            raise ValueError('Refusing download redirect outside the public HTTPS source')
        return super().redirect_request(req,fp,code,msg,headers,newurl)

def download(url,destination,limit=128_000_000):
    destination=Path(destination);destination.parent.mkdir(parents=True,exist_ok=True)
    fd,temp=tempfile.mkstemp(prefix='download-',dir=destination.parent);os.close(fd);temp=Path(temp)
    try:
        request=urllib.request.Request(url,headers={'User-Agent':'kanji-translator/0.1 (public dictionary setup)'})
        with urllib.request.build_opener(PublicRedirect).open(request,timeout=60) as response,temp.open('wb') as stream:
            total=0
            while block:=response.read(1024*1024):
                total+=len(block)
                if total>limit:raise ValueError('Public download exceeds size bound')
                stream.write(block)
        if not total:raise ValueError('Empty public download')
        os.replace(temp,destination)
    finally:temp.unlink(missing_ok=True)

def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    ocr=parser.add_mutually_exclusive_group()
    ocr.add_argument('--install-ocr',action='store_true',help='Install pinned NDLOCR-Lite in a separate external environment (CPU, no sudo)')
    parser.add_argument('--install-bert',action='store_true',help='Install the pinned Japanese BERT encoder outside the checkout')
    parser.add_argument('--update',action='store_true',help='Download current snapshots and atomically rebuild')
    parser.add_argument('--source-dir',type=Path,help='Offline upstream gzip files; source URLs and hashes still recorded')
    args=parser.parse_args(argv);root=external(data_dir());root.mkdir(parents=True,exist_ok=True)
    try:
        import fcntl
        with (root/'setup.lock').open('w') as lock:
            fcntl.flock(lock,fcntl.LOCK_EX)
            snapshot=root/'sources';snapshot.mkdir(exist_ok=True)
            inputs={};manifests={}
            for name,(filename,url) in SOURCES.items():
                dest=snapshot/filename
                if args.source_dir:
                    origin=args.source_dir/filename
                    if not origin.is_file():raise ValueError('Offline source missing: '+filename)
                    if not dest.exists() or sha256(origin)!=sha256(dest):
                        temp=dest.with_suffix('.partial');shutil.copyfile(origin,temp);temp.replace(dest)
                elif args.update or not dest.exists():download(url,dest)
                inputs[name]=dest
                manifests[name]={'url':url,'license':'CC-BY-SA-4.0','terms':TERMS,'attribution':'JMdict, JMnedict and KANJIDIC2: Copyright James William Breen and the Electronic Dictionary Research and Development Group','transformation':'XML spellings, readings, restricted senses and character payloads in SQLite; derived roman aliases and attested variant edges'}
            result=build(inputs,root/'lexicon.sqlite3',manifests)
            from .sword_library import install
            result['sword_library']=install(root/'lexicon.sqlite3')
            # Attribution follows the generated data outside the checkout.
            from importlib.resources import files
            sword_notice=files('kanji_translator').joinpath('resources/data_licenses.txt').read_text(encoding='utf-8')
            (root/'NOTICE.txt').write_text(manifests['jmdict']['attribution']+'\nData and derived database: CC BY-SA 4.0\n'+TERMS+'\nhttps://creativecommons.org/licenses/by-sa/4.0/\n'+sword_notice,encoding='utf-8')
            if result['state']=='built':
                (root/'release.json').write_text(json.dumps({'retrieved_at':datetime.now(timezone.utc).isoformat(),'result':result,'sources':manifests},indent=2)+'\n')
            from .install_ocr import install as install_ocr,readiness
            result['ocr']=install_ocr() if args.install_ocr else readiness()
            if args.install_bert:
                from .install_bert import install as install_bert
                from .bert_context import base_path
                result['bert']=install_bert(base_path())
            print(json.dumps({'data_dir':str(root),**result},ensure_ascii=False))
        return 0
    except (OSError,ValueError,ImportError,RuntimeError,subprocess.SubprocessError) as error:
        parser.exit(2,'Setup failed: '+str(error)+'\nCheck HTTPS access, free disk space, Python venv support, or use --source-dir with complete upstream files.\n')
if __name__=='__main__':raise SystemExit(main())
