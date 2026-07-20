#!/usr/bin/env python3
"""Thin inventory wrapper around audit_repository (never a gate).

Runs the repo-wide static auditor over ``--root`` (default: repository root),
skipping .git, the auditor's own tools/audit tree, and vendored/ignored dirs,
then writes ``findings.csv``, ``findings.json`` and ``summary.json`` (counts by
severity AND code) to ``--out``. This is an *inventory* of triage candidates, so
it always exits 0 while printing the P0 count for visibility.
"""
from __future__ import annotations
import argparse, csv, json, sys
from collections import Counter
from pathlib import Path

# Make sibling auditor importable whether run as a script or a module.
_HERE = Path(__file__).resolve().parent
if str(_HERE) not in sys.path:
    sys.path.insert(0, str(_HERE))
import audit_repository  # noqa: E402

# Auditor lives at <repo>/tools/audit/run_repo_audit.py -> parents[2] is the repo root.
DEFAULT_ROOT = _HERE.parents[1]
# Skip the auditor itself plus common vendored / cache / tooling dirs so the
# harness never audits its own source or non-project artifacts.
DEFAULT_EXCLUDES = [
    'tools/audit',
    '.code-review-graph',
    '.pytest_cache', '.mypy_cache', '.ruff_cache',
    'node_modules', 'site-packages', 'data',
]

def run(root: Path, out: Path, excludes):
    rows, inventory = audit_repository.collect(root, excludes)
    out.mkdir(parents=True, exist_ok=True)
    fields = ['severity', 'code', 'path', 'line', 'message', 'evidence']
    with (out/'findings.csv').open('w', newline='') as f:
        w = csv.DictWriter(f, fieldnames=fields); w.writeheader(); w.writerows(rows)
    (out/'findings.json').write_text(json.dumps(rows, indent=2))
    sev = Counter(r['severity'] for r in rows)
    code = Counter(r['code'] for r in rows)
    sev_code = Counter((r['severity'], r['code']) for r in rows)
    summary = {
        'root': str(root),
        'files_inventoried': len(inventory),
        'findings': len(rows),
        'severity_counts': dict(sev),
        'code_counts': dict(code.most_common()),
        'severity_code_counts': {f'{s}:{c}': n for (s, c), n in sev_code.most_common()},
        'p0_count': sev.get('P0', 0),
    }
    (out/'summary.json').write_text(json.dumps(summary, indent=2))
    return summary

def main(argv=None):
    ap = argparse.ArgumentParser(description='Inventory wrapper over audit_repository: writes findings.csv/json + summary.json. Always exits 0 (not a gate).')
    ap.add_argument('--root', type=Path, default=DEFAULT_ROOT, help='Repository root to audit (default: the ccb-pr repo root).')
    ap.add_argument('--out', type=Path, required=True, help='Output directory for findings.csv, findings.json, summary.json.')
    ap.add_argument('--exclude', action='append', default=[], metavar='REL_DIR', help='Extra repo-relative directory prefix to skip (repeatable).')
    args = ap.parse_args(argv)
    root = args.root.resolve()
    if not root.is_dir():
        raise SystemExit(f'--root does not exist or is not a directory: {root}')
    excludes = DEFAULT_EXCLUDES + list(args.exclude)
    summary = run(root, args.out.resolve(), excludes)
    print(json.dumps(summary, indent=2))
    print(f'\nP0 findings: {summary["p0_count"]}  (inventory only; not a gate)')
    return 0

if __name__ == '__main__':
    raise SystemExit(main())
