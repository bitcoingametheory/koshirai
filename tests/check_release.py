"""Check the checkout, index and reachable history without disclosing matched content."""
from pathlib import Path
import gzip,hashlib,json,os,re,subprocess,sys
ROOT=Path(__file__).resolve().parents[1]
LIMIT=500_000_000
ROOT_FILES={'.gitignore','README.md','llms.txt','setup.sh','pyproject.toml','LICENSE'}
PRIVATE_LABEL_HASHES={'43f91d0db76d28bc903550f2dd87e963ae2bf488088b27237bb30ab119813c57',
                      '7b3d203c72816e54cdace429f12b3cd65dd3ae152ea7d80995f060a019a209d0'}
PATTERNS=[
    re.compile(rb'(?i)'+rb'(?:drive|docs)'+rb'\.google\.com/(?:file|drive|open|uc|document|spreadsheets)'),
    re.compile(rb'/(?:home|Users)/[A-Za-z0-9_.-]+/'),
    re.compile(rb'/'+rb'media/[^\s\"\x27]+'),
    re.compile(rb'-----BEGIN (?:RSA |OPENSSH |EC )?PRIVATE KEY-----'),
    re.compile(rb'\b(?:AKIA|ASIA)[A-Z0-9]{16}\b'),
    re.compile(rb'\b(?:ghp_|github_pat_|sk-proj-)[A-Za-z0-9_-]{20,}'),
    re.compile(rb'(?i)(?:api[_-]?key|access[_-]?token|password|cookie)\s*[=:]\s*[\"\x27][A-Za-z0-9_/+=.-]{16,}'),
    re.compile(rb'\b[A-Za-z0-9_.+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b'),
]
def allowed(rel):
    parts=rel.parts
    if rel in (Path('benchmarks/native_semantics_evaluation.json'),Path('benchmarks/native_semantics_predictions.jsonl.gz')):return True
    if rel==Path('docs/evaluation.html'):return True
    if len(parts)==1:return rel.name in ROOT_FILES
    if rel.parent==Path('kanji_translator/resources'):return rel.name in {'sword_library_manifest.json','sword_library.json.gz','data_licenses.txt','semantic_roles.json','bert_base_manifest.json','bert_head.json.gz','bert_head_manifest.json'}
    if rel.parent==Path('benchmarks') and rel.suffix=='.py':return True
    if rel.parent==Path('benchmarks'):return rel.name in {'README.md','sample_manifest.json','scan_rights.json','historical_evidence.json','semantic_evaluation.json','semantic_references.json','semantic_predictions.jsonl.gz','bert_training.json.gz','bert_evaluation.json','bert_predictions.jsonl.gz','bert_source_priority_predictions.jsonl.gz','jev_evaluation.json','jev_predictions.jsonl.gz','jev_decisions.jsonl.gz','boundary_predictions.jsonl.gz','boundary_evaluation.json'}
    if rel==Path('benchmarks/sample_scans/index.json'):return True
    if rel.parent==Path('benchmarks/sample_scans') and rel.suffix=='.jpg':
        try:
            cohort=json.loads((ROOT/'benchmarks/sample_manifest.json').read_text())
            index=json.loads((ROOT/'benchmarks/sample_scans/index.json').read_text())
            return rel.name in {index[row['id']] for row in cohort['examples'] if row.get('public_image') is True}
        except (OSError,ValueError,KeyError):return False
    if rel in (Path('docs/file_inventory.json'),Path('docs/library_coverage.json')):return True
    return parts[0] in {'kanji_translator','tests','docs','tools'} and rel.suffix in {'.py','.md','.txt'}
def scan(rel,data,failures):
    if rel.parent==Path('benchmarks/sample_scans') and rel.suffix=='.jpg':
        try:
            cohort=json.loads((ROOT/'benchmarks/sample_manifest.json').read_text())
            index=json.loads((ROOT/'benchmarks/sample_scans/index.json').read_text())
            expected=next(row['source']['sha256'] for row in cohort['examples'] if index[row['id']]==rel.name and row.get('public_image') is True)
            if hashlib.sha256(data).hexdigest()!=expected:failures.add('benchmark image hash mismatch: '+str(rel))
        except (OSError,ValueError,KeyError,StopIteration):failures.add('benchmark image not in frozen public subset: '+str(rel))
    if rel.suffix=='.gz':
        try:data=gzip.decompress(data)
        except (OSError,EOFError):failures.add('invalid compressed library');return
    if any(pattern.search(data) for pattern in PATTERNS):failures.add('privacy pattern: '+str(rel))
    if rel.suffix!='.jpg' and any(hashlib.sha256(word).hexdigest() in PRIVATE_LABEL_HASHES
            for word in set(re.findall(rb'[a-z]+',data.lower()))):
        failures.add('private source identity: '+str(rel))
def check_git_content(git,failures):
    """Scan each path/blob once, including deleted historical files and staged content."""
    seen={}
    def blob(mode,oid,name):
        rel=Path(os.fsdecode(name))
        if mode not in (b'100644',b'100755') or not allowed(rel):
            failures.add('unapproved committed path: '+str(rel));return 0
        key=(name,oid)
        if key not in seen:
            data=git('cat-file','blob',oid.decode())
            scan(rel,data,failures);seen[key]=len(data)
        return seen[key]
    commits=git('rev-list','HEAD').splitlines()
    for commit in commits:
        total=0
        for record in git('ls-tree','-r','-z',commit.decode()).split(b'\0'):
            if not record:continue
            metadata,name=record.split(b'\t',1);mode,kind,oid=metadata.split()
            total+=blob(mode,oid,name)
        if total>LIMIT:failures.add('committed public files exceed 500MB')
    total=0
    for record in git('ls-files','--stage','-z').split(b'\0'):
        if not record:continue
        metadata,name=record.split(b'\t',1);mode,oid,stage=metadata.split()
        if stage!=b'0':failures.add('unmerged index: '+os.fsdecode(name));continue
        total+=blob(mode,oid,name)
    if total>LIMIT:failures.add('staged public files exceed 500MB')
    return len(commits)

def check(published=False):
    failures=set();size=0;files=0
    for path in ROOT.rglob('*'):
        if '.git' in path.relative_to(ROOT).parts:continue
        if path.is_symlink():failures.add('symlink: '+str(path.relative_to(ROOT)));continue
        if not path.is_file():continue
        rel=path.relative_to(ROOT);files+=1;size+=path.stat().st_size
        if not allowed(rel):failures.add('unapproved artifact: '+str(rel))
        scan(rel,path.read_bytes(),failures)
    if size>LIMIT:failures.add('public files exceed 500MB')
    def git(*args):return subprocess.check_output(['git','-C',str(ROOT),*args])
    commits=check_git_content(git,failures)
    if published:
        if git('status','--porcelain'):failures.add('published tree is not clean')
        if git('branch','--show-current').strip()!=b'main':failures.add('expected main branch')
        if git('remote','get-url','origin').strip()!=b'https://github.com/bitcoingametheory/koshirai.git':failures.add('unexpected publication target')
    audit=subprocess.run([sys.executable,'-B',str(ROOT/'tools/audit_repository.py'),'--check'],capture_output=True,text=True)
    if audit.returncode:failures.add('file inventory or local-link check failed')
    return {'passed':not failures,'files':files,'public_bytes':size,'commits_checked':commits,'published_checks':published,'failures':sorted(failures)}
if __name__=='__main__':
    import argparse
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--published',action='store_true');args=parser.parse_args()
    result=check(args.published);print(json.dumps(result));raise SystemExit(0 if result['passed'] else 1)
