"""Inventory every release file, its purpose, hash and critical-path role."""
import argparse
import ast
import hashlib
import json
from pathlib import Path
import re
from urllib.parse import unquote

ROOT = Path(__file__).resolve().parents[1]
INVENTORY = ROOT/'docs/file_inventory.json'
GUIDE = ROOT/'docs/file_guide.md'


def purpose(path):
    relative=path.relative_to(ROOT)
    if relative.parts[0]=='kanji_translator':
        if path.suffix=='.py':
            tree=ast.parse(path.read_text())
            description=(ast.get_docstring(tree) or 'Package integration and public imports.').splitlines()[0]
            if path.stem.startswith('install_'):return 'installation',description
            if path.stem in ('build_sword_library','audit_library'):return 'library maintenance',description
            return 'application',description
        return 'runtime data',{
            'sword_library.json.gz':'Source-supported term/name facts used by literal span matching.',
            'sword_library_manifest.json':'Checks bundled library hashes, counts and source licensing.',
            'semantic_roles.json':'Cited private-reference school, tradition and complete-name role facts.',
            'bert_base_manifest.json':'Pinned Japanese BERT encoder file identities and hashes.',
            'bert_head.json.gz':'Trained contextual role classifier parameters; no source prose.',
            'bert_head_manifest.json':'Classifier checksum, encoder revision and training provenance.',
            'data_licenses.txt':'Required attribution for bundled derived facts.'}[path.name]
    if relative.parts[0]=='tests':return 'verification','Verifies '+path.stem.removeprefix('test_').replace('_',' ')+' behavior and its current source/evidence contract.'
    if relative.parts[0]=='benchmarks':
        if path.suffix=='.py':return 'evaluation',(ast.get_docstring(ast.parse(path.read_text())) or 'Reproducible benchmark operation.').splitlines()[0]
        return 'evaluation evidence',{
            'historical_evidence.json':'Sole consolidated original/corrected annotations and compact negative results preserved independently of Git history.',
            'sample_manifest.json':'Public sample frame identities, hashes and reuse rights used by downloader/release checks.',
            'scan_rights.json':'Original public-scan rights receipts supporting redistributable examples.',
            'index.json':'Maps immutable public frame IDs to researcher-readable image filenames.',
            'README.md':'Canonical counting, annotation, supervision and evaluation interpretation rules.',
            'semantic_references.json':'Frozen source-only declared-region annotations, public frame identities and reuse citations.',
            'semantic_predictions.jsonl.gz':'Same-scan general, exact and contextual predictions needed to reproduce published grouping scores.',
            'bert_training.json.gz':'Frozen public OCR labels and synthetic teaching cases used for classifier reproduction.',
            'bert_evaluation.json':'BERT training, same-source comparison, installed inference and reproduction receipts.',
            'bert_predictions.jsonl.gz':'Frozen BERT page predictions with pseudonymous provenance and local paths removed.',
            'bert_source_priority_predictions.jsonl.gz':'Paired source-priority page predictions for the BERT comparison.',
            'jev_evaluation.json':'Live Jev, conditional-role, page, layout and offline-replay evidence.',
            'jev_predictions.jsonl.gz':'Frozen Jev page predictions without local cache paths.',
            'jev_decisions.jsonl.gz':'Checksum-verified provider decisions for credential-free offline replay.',
            'boundary_predictions.jsonl.gz':'Frozen same-OCR predictions for the Japanese technical-boundary repair.',
            'boundary_evaluation.json':'Paired complete-group counts, failed first pass and bounded retained-OCR evidence.',
            'native_semantics_predictions.jsonl.gz':'Frozen same-OCR native-entry predictions without machine-local cache paths.',
            'native_semantics_evaluation.json':'Native entry/clause evidence, paired location policies, failed passes and pending model comparison.',
            'semantic_evaluation.json':'Current measured workflow/evaluation receipt with unscored limitations.'}.get(path.name,'Public original scan '+path.stem+' for repository-only workflow validation; hash/rights in sample manifest.')
    if relative.parts[0]=='tools':return 'maintenance','Rebuilds the complete file inventory and checks syntax without changing source data.'
    if relative.parts[0]=='docs':return 'researcher documentation','Documents installation, evidence interpretation, contribution, source coverage, licenses or this audit.'
    return 'installation and entry points',{
        'setup.sh':'One-command external-environment installation.',
        'pyproject.toml':'Package metadata, pinned dependencies and executable entry points.',
        'README.md':'Researcher starting point and accurate capability statement.',
        'LICENSE':'Permissions for original project contributions.',
        'llms.txt':'Repository-only instructions for researcher agents.',
        '.gitignore':'Keeps private inputs, caches and environments out of releases.'}[path.name]


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--check',action='store_true');args=parser.parse_args()
    paths=sorted(p for p in ROOT.rglob('*') if p.is_file() and '.git' not in p.relative_to(ROOT).parts)
    generated=[p.relative_to(ROOT).as_posix() for p in paths
               if p.suffix in ('.pyc','.pyo') or '__pycache__' in p.parts
               or '.pytest_cache' in p.parts or any(part.endswith('.egg-info') for part in p.parts)]
    if generated:
        raise ValueError('Generated caches/build metadata are not release files: '+', '.join(generated))
    # Include the inventory itself on the first run; omit its self-referential hash.
    if INVENTORY not in paths:paths.append(INVENTORY)
    if GUIDE not in paths:paths.append(GUIDE)
    rows=[]
    for path in sorted(paths):
        category,reason=purpose(path)
        if path.suffix=='.py':compile(path.read_text(),str(path),'exec')
        if path.suffix=='.json' and path.exists():json.loads(path.read_text())
        if path.suffix in ('.md','.txt') and path.exists() and path != GUIDE:
            for target in re.findall(r'\[[^\]]*\]\(([^)]+)\)',path.read_text()):
                if '://' in target or target.startswith(('#','mailto:')):continue
                destination=unquote(target.split('#')[0])
                if destination and not (path.parent/destination).exists():
                    raise ValueError(f'Broken local link in {path.relative_to(ROOT)}: {target}')
        rows.append({'path':path.relative_to(ROOT).as_posix(),'role':category,'reason_retained':reason,
                     'runtime_required':category in ('application','runtime data'),
                     'sha256':hashlib.sha256(path.read_bytes()).hexdigest() if path.exists() and path not in (INVENTORY,GUIDE) else None})
    if args.check:
        existing=json.loads(INVENTORY.read_text())
        if existing['files']!=rows:raise ValueError('File inventory is stale; regenerate after inspecting changes')
        print(json.dumps({'files_checked':len(rows),'inventory_matches':True}));return
    INVENTORY.parent.mkdir(exist_ok=True)
    INVENTORY.write_text(json.dumps({'schema':'release-file-inventory-v1','files':rows,
        'policy':'Every file has a runtime, installation, verification, evidence, legal or researcher role. Supporting evidence is essential to reproducibility, not loaded for every scan.',
        'self_hash_policy':'Inventory and generated guide are listed without recursive self hashes.'},indent=2)+'\n')
    GUIDE.write_text('# File guide\n\nThe package has one implementation. Standard Python and packaging names are retained where tools require them. Data IDs stay immutable while scan filenames describe the edition.\n\nRuntime files support scanning and lookup; the other categories support installation, reproducibility, review and licensing. Historical benchmark receipts remain evidence, not a second implementation.\n\n| File | Role | Why retained |\n| --- | --- | --- |\n'+''.join(f"| [{r['path']}](../{r['path']}) | {r['role']} | {r['reason_retained'].replace('|','/')} |\n" for r in rows))
    print(json.dumps({'files_checked':len(rows),'python_syntax':'passed','inventory':str(INVENTORY.relative_to(ROOT))}))


if __name__=='__main__':main()
