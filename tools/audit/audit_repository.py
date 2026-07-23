#!/usr/bin/env python3
"""Repository-wide static scientific audit for ccb-testbeam.

This tool is deliberately conservative. Findings are candidates for human triage;
P0 patterns should block publication until resolved. It does not alter the repo.

Detected patterns
-----------------
P0  AMPLITUDE_SCHEMA_DOUBLE_SUBTRACTION  amplitude_adc/baseline_adc subtracted (schema ambiguity)
P0  EVENTNO_ONLY_JOIN                    event-level merge on eventno without run
P0  MC_WEIGHT_NOT_DECLARED               MC truth reader with no PrimaryWeight/justification
P0  INDEX_PARITY_SPLIT                   index-parity train/test split leaks correlated rows
P0  VALIDATED_WITH_BLOCKING_UNCERTAINTY  REPORT.md claims validation w/ blocking uncertainty
P0  CLAIM_VALIDATED_CI_MISSING           claim ledger row VALIDATED but CI/uncertainty missing
P0  CLAIM_SOURCE_MISSING                 claim ledger source_* path does not exist
P1  UNSEEDED_RANDOMNESS                  random sampling without a fixed seed
P1  ABSOLUTE_PATH / ABSOLUTE_PATH_JSON   committed absolute path reduces portability
P1  UNUSED_ARGUMENT                      argparse option declared but never referenced
P1  REPORT_SECTION_MISSING               REPORT.md lacks a required section
P1  DUPLICATE_STUDY_ID                   same study id claimed by multiple reports
P1  READ_ERROR / JSON_INVALID / PYTHON_SYNTAX_ERROR
P2  AUTO_GENERATED_DISCLOSURE            auto-generated report needs independent review

Language coverage (AUD-002)
---------------------------
The auditor fully covers Python (source + AST), REPORT.md, JSON, and the claim
ledger CSV. Other languages present in a scientific HEP repo (C++/Geant4,
CMake, YAML configs, Jupyter notebooks, shell) are INVENTORIED (path + sha256)
and reported as explicitly *unaudited* via ``summarize_coverage`` rather than
silently skipped. Each unaudited language has a suppression record in
``COVERAGE_SUPPRESSIONS`` documenting why it is out of scope and where its
review lives. Adding a new Python check (AST-based) is the path to expand
coverage; do not widen the regex layer for non-Python files.
"""
from __future__ import annotations
import argparse, ast, csv, hashlib, json, os, re
from pathlib import Path
from collections import Counter, defaultdict

REQ_SECTIONS = ["reproduction", "method", "result", "provenance"]
MC_BRANCH_HINTS = ("Sci_bar_", "hibeam", "PrimaryPDG", "output_krakow")
# Directory names always skipped during the walk (VCS / caches / virtualenvs).
DEFAULT_SKIP_PARTS = {'.git', '.venv', 'venv', '__pycache__'}

# --- AUD-002: explicit language coverage policy ----------------------------
# Suffixes (and special filenames) that receive a real static check here.
# Everything else is inventoried for provenance but recorded as unaudited.
AUDITED_SUFFIXES = {'.py'}
AUDITED_NAMES = {'REPORT.md'}      # prose report structural check
AUDITED_JSON = {'.json'}           # absolute-path + validity check
AUDITED_LEDGER = 'docs/claim_ledger.csv'

# Suppression records: WHY each unaudited language is not statically checked
# here and WHERE its authoritative review lives. Surfaced in every coverage
# report so "not covered" is an explicit, documented decision — never silent.
COVERAGE_SUPPRESSIONS = {
    'cpp':   ('Geant4 / VGM C++ (.cc/.cpp/.hh/.hpp): no C++ static analysis in this '
              'tool. Geometry/optics/physics code is covered by the Geant4 ctest '
              'suite (geant4/single_stave) + the single_stave build.'),
    'cmake': ('CMake / CTestLists (.cmake/CMakeLists.txt): build-config review is '
              'manual; no schema/semantics to audit here.'),
    'yaml':  ('YAML configs (.yaml/.yml): validated by their consumers (pydantic / '
              'config loaders) at load time, not statically here.'),
    'shell': ('Shell scripts (.sh/.bash): injection-surface scripts are reviewed by '
              'the dedicated shell-safety review (e.g. SEC tickets); not regex-audited.'),
    'notebook': ('Jupyter notebooks (.ipynb): executed outputs are validated by the '
                 'report provenance / ccbprov manifest layer; static NB lint is out of scope.'),
    'markdown': ('Plain Markdown (non-REPORT): documentation; no scientific claim to audit.'),
    'text':  ('Plain text / data tables (.txt/.dat/.csv data): content is hashed for '
              'provenance; semantic audit belongs to the relevant study tool.'),
    'other': ('Binary / build artifacts / other: inventoried (sha256) for provenance only.'),
}

def _language_of(rel: Path) -> str:
    """Coarse language bucket for coverage reporting (AUD-002)."""
    name = rel.name
    if name == 'CMakeLists.txt' or rel.suffix == '.cmake':
        return 'cmake'
    if rel.suffix in {'.cc', '.cpp', '.cxx', '.hh', '.hpp', '.hxx', '.c', '.h'}:
        return 'cpp'
    if rel.suffix in {'.yaml', '.yml'}:
        return 'yaml'
    if rel.suffix in {'.sh', '.bash'}:
        return 'shell'
    if rel.suffix == '.ipynb':
        return 'notebook'
    if rel.suffix == '.py':
        return 'python'
    if name == 'REPORT.md':
        return 'report'
    if rel.suffix == '.md':
        return 'markdown'
    if rel.suffix == '.json':
        return 'json'
    if rel.suffix in {'.txt', '.dat', '.csv'}:
        return 'text'
    return 'other'

def sha256(path: Path) -> str:
    h=hashlib.sha256()
    with path.open('rb') as f:
        for b in iter(lambda:f.read(1<<20), b''): h.update(b)
    return h.hexdigest()

def add(rows, severity, code, path, line, message, evidence=""):
    rows.append(dict(severity=severity, code=code, path=str(path), line=line or 0, message=message, evidence=evidence))

def line_of(text, needle):
    i=text.find(needle)
    return 1 if i<0 else text[:i].count('\n')+1

def audit_python(path: Path, rows):
    try: text=path.read_text(errors='replace')
    except Exception as e:
        add(rows,'P1','READ_ERROR',path,0,str(e)); return
    # ambiguous/double baseline subtraction
    if re.search(r"amplitude_adc[^\n]{0,80}-[^\n]{0,80}baseline_adc|baseline_adc[^\n]{0,80}-[^\n]{0,80}amplitude_adc", text):
        add(rows,'P0','AMPLITUDE_SCHEMA_DOUBLE_SUBTRACTION',path,line_of(text,'amplitude_adc'),'amplitude_adc and baseline_adc are subtracted; verify PulseTableContract')
    # eventno-only merges
    for m in re.finditer(r"\.(?:merge|join)\s*\([^\n]{0,240}(?:on\s*=\s*['\"]eventno['\"]|on\s*=\s*\[['\"]eventno['\"]\])", text):
        add(rows,'P0','EVENTNO_ONLY_JOIN',path,text[:m.start()].count('\n')+1,'Event-level join appears to use eventno without run')
    # MC readers without weight policy
    if any(h in text for h in MC_BRANCH_HINTS) and ('uproot.open' in text or 'iterate(' in text):
        if 'PrimaryWeight' not in text and 'weight_policy' not in text and 'UNWEIGHTED_MC_JUSTIFICATION' not in text:
            add(rows,'P0','MC_WEIGHT_NOT_DECLARED',path,1,'MC truth reader has no PrimaryWeight or explicit unweighted justification')
    # index parity split
    if re.search(r"(?:index|idx|np\.arange\([^\)]*\))\s*%\s*2", text) or 'legacy_parity' in text:
        add(rows,'P0','INDEX_PARITY_SPLIT',path,line_of(text,'legacy_parity'),'Index-parity split may leak correlated rows/events')
    # unseeded random choices/samples
    if ('np.random.choice' in text or '.sample(' in text) and not any(x in text for x in ('default_rng(', 'np.random.seed(', 'random_state=')):
        add(rows,'P1','UNSEEDED_RANDOMNESS',path,1,'Random sampling found without an obvious fixed seed')
    # hard-coded absolute paths
    for m in re.finditer(r"['\"]/(?:home|projects|scratch|tmp)/[^'\"]+", text):
        add(rows,'P1','ABSOLUTE_PATH',path,text[:m.start()].count('\n')+1,'Committed absolute path reduces portability',m.group(0)[:160])
    # parser options referenced only once (definition only) — AST-based (AUD-002: Python AST coverage)
    try:
        tree=ast.parse(text)
        opts=[]
        for n in ast.walk(tree):
            if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute) and n.func.attr=='add_argument' and n.args:
                if isinstance(n.args[0], ast.Constant) and isinstance(n.args[0].value,str) and n.args[0].value.startswith('--'):
                    opts.append(n.args[0].value[2:].replace('-','_'))
        for opt in opts:
            if len(re.findall(rf"\b{re.escape(opt)}\b", text)) <= 1:
                add(rows,'P1','UNUSED_ARGUMENT',path,line_of(text,opt),f'Argument --{opt.replace("_","-")} appears declared but unused')
    except SyntaxError as e:
        add(rows,'P1','PYTHON_SYNTAX_ERROR',path,e.lineno or 0,str(e))

def audit_report(path: Path, rows):
    text=path.read_text(errors='replace')
    low=text.lower()
    for s in REQ_SECTIONS:
        if s not in low: add(rows,'P1','REPORT_SECTION_MISSING',path,1,f'Report lacks recognizable {s} section')
    if re.search(r'\bvalidated\b', low) and ('ci_missing_blocking' in low or 'no uncertainty' in low):
        add(rows,'P0','VALIDATED_WITH_BLOCKING_UNCERTAINTY',path,1,'Report claims validation while uncertainty is blocking/missing')
    if re.search(r'generated.*claude|generated.*codex', low):
        add(rows,'P2','AUTO_GENERATED_DISCLOSURE',path,1,'Auto-generated report requires independent scientific critic review')

def audit_json(path: Path, rows):
    try: obj=json.loads(path.read_text())
    except Exception as e: add(rows,'P1','JSON_INVALID',path,0,str(e)); return
    blob=json.dumps(obj)
    if re.search(r'/(?:home|projects|scratch)/', blob): add(rows,'P1','ABSOLUTE_PATH_JSON',path,1,'JSON contains absolute artifact/data paths')

def audit_claim_ledger(path: Path, repo: Path, rows):
    with path.open(newline='') as f:
        for i,row in enumerate(csv.DictReader(f),2):
            cid=row.get('claim_id','')
            status=(row.get('status') or '').upper()
            if 'VALIDATED' in status and any('CI_MISSING' in (row.get(k) or '') for k in ('stat_unc','syst_unc','total_unc','ci_low','ci_high','ci_status')):
                add(rows,'P0','CLAIM_VALIDATED_CI_MISSING',path,i,f'{cid}: VALIDATED but CI/uncertainty is missing/blocking')
            for field in ('source_report','source_script','source_data','source_config','source_manifest'):
                p=(row.get(field) or '').strip()
                if p and p not in {'NA','N/A','SOURCE_DATA_MISSING'} and not (repo/p).exists():
                    add(rows,'P0','CLAIM_SOURCE_MISSING',path,i,f'{cid}: {field} does not exist',p)

def _skip(rel: Path, extra_excludes) -> bool:
    """True if a repo-relative path lives under a skipped/vendored/excluded dir."""
    parts = rel.parts
    if any(p in DEFAULT_SKIP_PARTS for p in parts):
        return True
    relposix = rel.as_posix()
    for ex in extra_excludes:
        ex = ex.strip('/').strip()
        if not ex:
            continue
        if relposix == ex or relposix.startswith(ex + '/'):
            return True
    return False

def collect(repo: Path, extra_excludes=None, *, hash_files=True):
    """Walk ``repo`` and return (rows, inventory). Pure; writes nothing.

    ``extra_excludes`` is a list of repo-relative directory prefixes to skip
    (in addition to the always-skipped .git/.venv/__pycache__).

    Each inventory row is enriched (AUD-002) with ``language`` and ``audited``
    so coverage is explicit: unaudited languages are recorded, never silently
    dropped. Use ``summarize_coverage(inventory)`` for the coverage report.
    """
    repo = Path(repo).resolve()
    extra_excludes = list(extra_excludes or [])
    rows, inventory = [], []
    for path in sorted(repo.rglob('*')):
        if not path.is_file():
            continue
        rel = path.relative_to(repo)
        if _skip(rel, extra_excludes):
            continue
        size = path.stat().st_size
        language = _language_of(rel)
        audited = (language == 'python' or rel.name in AUDITED_NAMES
                   or rel.suffix in AUDITED_JSON
                   or rel.as_posix() == AUDITED_LEDGER)
        inventory.append({'path': str(rel), 'bytes': size, 'language': language,
                          'audited': audited,
                          'sha256': sha256(path) if (hash_files and size < 100_000_000) else ''})
        if language == 'python': audit_python(path, rows)
        elif rel.name == 'REPORT.md': audit_report(path, rows)
        elif rel.suffix == '.json': audit_json(path, rows)
    ledger = repo/AUDITED_LEDGER
    if ledger.exists() and not _skip(Path(AUDITED_LEDGER), extra_excludes):
        audit_claim_ledger(ledger, repo, rows)
    # Duplicate study IDs based on report headers/directory prefixes
    ids = defaultdict(list)
    for p in repo.rglob('REPORT.md'):
        rel = p.relative_to(repo)
        if _skip(rel, extra_excludes):
            continue
        try:
            t=p.read_text(errors='replace')[:4000]
            m=re.search(r'(?:Study ID|study_id|#\s*)(?:\*\*)?[:\s-]*([A-Z]+\d+[a-zA-Z0-9.-]*)',t,re.I)
            if m: ids[m.group(1).upper()].append(str(rel))
        except Exception: pass
    for sid,paths in ids.items():
        if len(paths)>1: add(rows,'P1','DUPLICATE_STUDY_ID',Path(paths[0]),1,f'{sid} appears in {len(paths)} reports',';'.join(paths[:10]))
    return rows, inventory

def summarize_coverage(inventory):
    """AUD-002: explicit per-language coverage report.

    Returns a dict with the count of files actually checked vs. files that were
    only inventoried, broken down by language, plus the suppression rationale
    for every unaudited language. This makes "not covered" an explicit, recorded
    decision instead of a silent gap.
    """
    covered = Counter()
    uncovered = Counter()
    for row in inventory:
        lang = row.get('language', 'other')
        if row.get('audited'):
            covered[lang] += 1
        else:
            uncovered[lang] += 1
    return {
        'covered_by_language': dict(covered.most_common()),
        'uncovered_by_language': dict(uncovered.most_common()),
        'covered_files': int(sum(covered.values())),
        'uncovered_files': int(sum(uncovered.values())),
        'uncovered_suppressions': COVERAGE_SUPPRESSIONS,
    }

def write_outputs(out: Path, repo: Path, rows, inventory):
    out.mkdir(parents=True, exist_ok=True)
    fields=['severity','code','path','line','message','evidence']
    with (out/'findings.csv').open('w',newline='') as f: w=csv.DictWriter(f,fieldnames=fields); w.writeheader(); w.writerows(rows)
    inv_fields=['path','bytes','language','audited','sha256']
    with (out/'inventory.csv').open('w',newline='') as f: w=csv.DictWriter(f,fieldnames=inv_fields); w.writeheader(); w.writerows(inventory)
    counts=Counter(r['severity'] for r in rows)
    coverage=summarize_coverage(inventory)
    summary={'repo':str(repo),'files':len(inventory),'findings':len(rows),
             'severity_counts':dict(counts),'coverage':coverage}
    (out/'summary.json').write_text(json.dumps(summary,indent=2))
    (out/'coverage.json').write_text(json.dumps(coverage,indent=2))
    md=['# Repository re-audit findings','',f"Files inventoried: {len(inventory)}",
        f"Findings: {len(rows)}",'', '## Severity counts','']+[f"- {k}: {v}" for k,v in sorted(counts.items())]+['','## Findings','']
    md += [f"- **{r['severity']} {r['code']}** `{r['path']}:{r['line']}` — {r['message']}" for r in rows]
    (out/'REPORT.md').write_text('\n'.join(md)+'\n')
    return summary

def main(argv=None):
    ap=argparse.ArgumentParser(description='Repository-wide static scientific audit for ccb-testbeam. Findings are candidates for human triage; P0 patterns should block publication.')
    ap.add_argument('--repo',type=Path,default=Path('.'),help='Repository root to audit (default: current directory).')
    ap.add_argument('--out',type=Path,required=True,help='Output directory for findings.csv, inventory.csv, summary.json, REPORT.md.')
    ap.add_argument('--exclude',action='append',default=[],metavar='REL_DIR',help='Repo-relative directory prefix to skip (repeatable).')
    args=ap.parse_args(argv)
    repo=args.repo.resolve()
    if not repo.is_dir():
        raise SystemExit(f'--repo does not exist or is not a directory: {repo}')
    out=args.out.resolve()
    rows, inventory = collect(repo, args.exclude)
    summary = write_outputs(out, repo, rows, inventory)
    print(json.dumps(summary,indent=2))
    counts=Counter(r['severity'] for r in rows)
    raise SystemExit(1 if counts.get('P0',0) else 0)

if __name__=='__main__': main()
