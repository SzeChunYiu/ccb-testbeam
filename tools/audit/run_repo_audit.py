#!/usr/bin/env python3
"""Inventory + regression-gate wrapper around audit_repository (AUD-001).

Runs the repo-wide static auditor over ``--root`` (default: repository root),
skipping .git, the auditor's own tools/audit tree, and vendored/ignored dirs,
then writes ``findings.csv``, ``findings.json`` and ``summary.json`` (counts by
severity AND code) plus ``coverage.json`` (AUD-002 language coverage) to ``--out``.

Two modes
---------
* **Inventory** (default, no ``--baseline``): an inventory of triage candidates;
  always exits 0 while printing the P0 count for visibility. Use this for ad-hoc
  exploration.

* **Regression gate** (``--baseline FILE``): a fail-closed CI gate. Exits
  non-zero (1) if any **new or unwaived P0/P1** finding appears whose
  ``(severity, code, path)`` signature is not present in the triaged baseline.
  Pre-existing findings are grandfathered by the baseline; P2/informational
  findings never fail the gate. Use ``--update-baseline FILE`` after triage to
  accept the current finding set as the new baseline.

The baseline file is the waiver/suppression mechanism: every signature it lists
is an accepted, triaged item. Add a ``reason`` alongside a signature to document
the waiver rationale.
"""
from __future__ import annotations
import argparse, csv, json, subprocess, sys
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

# Findings at these severities fail the gate when they are NEW (not in baseline).
GATE_SEVERITIES = {'P0', 'P1'}
BASELINE_VERSION = 1


def _sig(severity: str, code: str, path: str) -> str:
    """Stable signature for a finding: severity|code|repo-relative-path.

    Line numbers are intentionally excluded — they shift under harmless edits,
    which would cause flaky gate failures. A finding for the same code in the
    same file is the same triage unit.
    """
    return f"{severity}|{code}|{path}"


def load_baseline(path: Path) -> tuple[set[str], dict]:
    """Load a triaged baseline. Returns (signature_set, raw_dict)."""
    data = json.loads(path.read_text())
    sigs: set[str] = set()
    for entry in data.get('signatures', []):
        # Entry is ["severity","code","path"] or {"severity":..,"code":..,"path":..}
        if isinstance(entry, list):
            severity, code, p = entry[0], entry[1], entry[2]
        else:
            severity, code, p = entry['severity'], entry['code'], entry['path']
        sigs.add(_sig(severity, code, p))
    return sigs, data


def write_baseline(path: Path, rows: list[dict], repo: Path) -> None:
    """Write current findings as a triaged baseline (sorted, deduplicated)."""
    seen: dict[str, list] = {}
    for r in rows:
        key = _sig(r['severity'], r['code'], r['path'])
        if key not in seen:
            seen[key] = [r['severity'], r['code'], r['path']]
    signatures = sorted(seen.values(), key=lambda t: (t[0], t[1], t[2]))
    commit = "unknown"
    try:
        commit = subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=repo, text=True, stderr=subprocess.DEVNULL
        ).strip()
    except Exception:
        pass
    doc = {
        "version": BASELINE_VERSION,
        "generated_from_commit": commit,
        "description": (
            "Triaged baseline of known static-audit findings. The regression gate "
            "(run_repo_audit --baseline <this file>) exits non-zero only on P0/P1 "
            "findings whose (severity, code, path) signature is NOT present here. "
            "Pre-existing findings are grandfathered; the gate fails closed on "
            "regressions (new P0/P1). To accept new findings after triage, re-run "
            "with --update-baseline."
        ),
        "policy": "Grandfather pre-existing findings; fail closed on new P0/P1.",
        "signatures": signatures,
    }
    path.write_text(json.dumps(doc, indent=2) + "\n")


def run(root: Path, out: Path, excludes):
    rows, inventory = audit_repository.collect(root, excludes)
    out.mkdir(parents=True, exist_ok=True)
    fields = ['severity', 'code', 'path', 'line', 'message', 'evidence']
    with (out/'findings.csv').open('w', newline='') as f:
        w = csv.DictWriter(f, fieldnames=fields); w.writeheader(); w.writerows(rows)
    (out/'findings.json').write_text(json.dumps(rows, indent=2))
    coverage = audit_repository.summarize_coverage(inventory)
    (out/'coverage.json').write_text(json.dumps(coverage, indent=2))
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
        'coverage': coverage,
    }
    (out/'summary.json').write_text(json.dumps(summary, indent=2))
    return summary, rows


def _gate(rows, baseline_sigs):
    """Split findings into (suppressed, new_blocking). New = not in baseline."""
    suppressed, new_blocking = [], []
    for r in rows:
        sig = _sig(r['severity'], r['code'], r['path'])
        if sig in baseline_sigs:
            suppressed.append(r)
        elif r['severity'] in GATE_SEVERITIES:
            new_blocking.append(r)
    return suppressed, new_blocking


def main(argv=None):
    ap = argparse.ArgumentParser(
        description='Inventory/regression-gate wrapper over audit_repository. '
                    'Without --baseline it is an inventory (exits 0). With --baseline '
                    'it is a fail-closed gate on NEW/unwaived P0/P1 findings.')
    ap.add_argument('--root', type=Path, default=DEFAULT_ROOT, help='Repository root to audit (default: the ccb-pr repo root).')
    ap.add_argument('--out', type=Path, required=True, help='Output directory for findings.csv, findings.json, summary.json, coverage.json.')
    ap.add_argument('--exclude', action='append', default=[], metavar='REL_DIR', help='Extra repo-relative directory prefix to skip (repeatable).')
    gate = ap.add_mutually_exclusive_group()
    gate.add_argument('--baseline', type=Path, metavar='BASELINE.json',
                      help='Regression-gate mode: exit non-zero on NEW/unwaived P0/P1 findings not present in this triaged baseline.')
    gate.add_argument('--update-baseline', type=Path, metavar='BASELINE.json',
                      help='Write the current finding set as a triaged baseline file (for re-triage), then exit 0.')
    args = ap.parse_args(argv)
    root = args.root.resolve()
    if not root.is_dir():
        raise SystemExit(f'--root does not exist or is not a directory: {root}')
    excludes = DEFAULT_EXCLUDES + list(args.exclude)

    summary, rows = run(root, args.out.resolve(), excludes)

    if args.update_baseline is not None:
        write_baseline(args.update_baseline.resolve(), rows, root)
        print(f"Wrote baseline with {len({ _sig(r['severity'], r['code'], r['path']) for r in rows })} "
              f"triaged signatures -> {args.update_baseline}")
        print(json.dumps({k: summary[k] for k in ('files_inventoried', 'findings', 'p0_count')}, indent=2))
        return 0

    if args.baseline is not None:
        baseline_path = args.baseline.resolve()
        if not baseline_path.is_file():
            raise SystemExit(f'--baseline not found: {baseline_path}')
        baseline_sigs, _ = load_baseline(baseline_path)
        suppressed, new_blocking = _gate(rows, baseline_sigs)
        (args.out.resolve()/'new_blocking_findings.json').write_text(json.dumps(new_blocking, indent=2))
        print(json.dumps(summary, indent=2))
        print(f"\nBaseline signatures: {len(baseline_sigs)}")
        print(f"Suppressed (grandfathered): {len(suppressed)}")
        print(f"NEW/unwaived blocking (P0/P1): {len(new_blocking)}")
        if new_blocking:
            print("\nFAIL-CLOSED: new blocking findings introduced:")
            for r in new_blocking[:50]:
                print(f"  [{r['severity']}] {r['code']} {r['path']}:{r['line']} — {r['message']}")
            if len(new_blocking) > 50:
                print(f"  ... and {len(new_blocking) - 50} more (see new_blocking_findings.json)")
            return 1
        print("Gate: PASS (no new blocking findings).")
        return 0

    # Inventory mode (default): never a gate.
    print(json.dumps(summary, indent=2))
    print(f"\nP0 findings: {summary['p0_count']}  (inventory only; use --baseline to gate)")
    return 0

if __name__ == '__main__':
    raise SystemExit(main())
