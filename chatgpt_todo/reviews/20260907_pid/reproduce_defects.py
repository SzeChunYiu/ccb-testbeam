#!/usr/bin/env python3
"""Focused CCB PID audit, 2026-09-07. No raw-data or MC-production rerun.

Default: execute small source excerpts transcribed from reviewed main
cec9edc28257e0699c70c17fa9b2e8d806a3d42a. With --repo PATH, extract the actual
functions using AST, without importing the study's top-level production code.

Exit status 1 means scientific invariants failed; this is an intentional RED
regression at the reviewed revision. A successful process is NOT a beam-data
validation. Requires Python, numpy and pandas. Does not modify input files.
"""
from __future__ import annotations
import argparse
import ast
import json
import re
from pathlib import Path
import numpy as np
import pandas as pd

BASE = 'cec9edc28257e0699c70c17fa9b2e8d806a3d42a'
CORE_PATH = 'scripts/single_stave/_deltaE_E_core.py'
PID_PATH = 'scripts/studies/clusterA_dE_PID_stopping.py'
# Functions reproduced from CORE_PATH and PID_PATH at BASE. Constants are
# supplied explicitly to the namespace below. Whitespace/comments shortened.
CORE_EXCERPT = r'''
def mc_layer_columns(df):
    found = []
    for c in df.columns:
        m = re.fullmatch(r"edep_B(\d+)", str(c))
        if m:
            found.append((int(m.group(1)), c))
    return [c for _, c in sorted(found)]

def derive_mc_columns(df):
    df = df.copy()
    df["deltaE_mc_mev"] = df[f"edep_{DELTAE_LAYER}"].astype(float)
    df["E_mc_4layer_mev"] = df[[f"edep_{b}" for b in E_LAYERS_4]].sum(axis=1).astype(float)
    full_cols = [c for c in mc_layer_columns(df) if c != f"edep_{DELTAE_LAYER}"]
    df["E_mc_full_mev"] = (
        df[full_cols].sum(axis=1).astype(float) if full_cols else 0.0
    )
    return df
'''
PID_EXCERPT = r'''
def roc_pr(y,s,w):
    y=np.asarray(y); s=np.asarray(s); w=np.asarray(w,float)
    o=np.argsort(-s); y,s,w=y[o],s[o],w[o]
    P=w[y==1].sum(); N=w[y==0].sum()
    if P<=0 or N<=0: return None
    tp=np.cumsum(w*y); fp=np.cumsum(w*(1-y))
    tpr=np.concatenate([[0.],tp/P,[1.]]); fpr=np.concatenate([[0.],fp/N,[1.]])
    prec=tp/(tp+fp+1e-30); rec=tp/P
    return dict(fpr=fpr,tpr=tpr,prec=prec,rec=rec,
                auc=float(np.trapezoid(tpr,fpr)),
                ap=float(np.sum((rec[1:]-rec[:-1])*prec[1:])))
'''

def extract_functions(path: Path, names: list[str]) -> ast.Module:
    tree = ast.parse(path.read_text(encoding='utf-8'), filename=str(path))
    lookup = {n.name: n for n in tree.body if isinstance(n, ast.FunctionDef)}
    missing = set(names) - set(lookup)
    if missing:
        raise ValueError(f'{path}: missing functions {sorted(missing)}')
    return ast.fix_missing_locations(ast.Module(body=[lookup[n] for n in names], type_ignores=[]))

def check(checks: list[dict], name: str, observed: float, expected: float) -> None:
    checks.append({'invariant': name, 'observed': float(observed),
                   'expected': float(expected),
                   'pass': bool(np.isclose(observed, expected, rtol=0, atol=1e-12))})

def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--repo', type=Path, help='Read actual source functions from this checkout')
    ap.add_argument('--out', type=Path, default=Path('regression_results.json'))
    args = ap.parse_args()
    ns = {'np': np, 'pd': pd, 're': re, 'DELTAE_LAYER': 'B2',
          'E_LAYERS_4': ('B4', 'B6', 'B8')}
    if args.repo:
        exec(compile(extract_functions(args.repo / CORE_PATH, ['mc_layer_columns', 'derive_mc_columns']), str(args.repo / CORE_PATH), 'exec'), ns)
        exec(compile(extract_functions(args.repo / PID_PATH, ['roc_pr']), str(args.repo / PID_PATH), 'exec'), ns)
        mode = 'actual_checkout_functions_ast_extracted'
    else:
        exec(CORE_EXCERPT, ns)
        exec(PID_EXCERPT, ns)
        mode = 'reviewed_source_excerpts_NOT_full_repository_execution'
    checks: list[dict] = []
    row = {f'edep_layer_{i}': float(i + 1) for i in range(8)}
    for b, layer in zip(('B2','B4','B6','B8'), (1,3,5,7)):
        row[f'edep_{b}'] = row[f'edep_layer_{layer}']
    result = ns['derive_mc_columns'](pd.DataFrame([row])).iloc[0]
    check(checks, 'Full E includes each physical layer downstream of mapped B2 once', result['E_mc_full_mev'], sum(row[f'edep_layer_{i}'] for i in range(2,8)))
    check(checks, 'Sparse E equals mapped downstream readouts (control)', result['E_mc_4layer_mev'], 18.)
    legacy = pd.DataFrame([{'edep_B1':100.,'edep_B2':2.,'edep_B4':4.,'edep_B6':6.,'edep_B8':8.}])
    check(checks, 'Legacy full-downstream E excludes upstream B1', ns['derive_mc_columns'](legacy).iloc[0]['E_mc_full_mev'], 18.)
    for labels in ([1,0], [0,1]):
        metric = ns['roc_pr'](labels, [.5,.5], [1.,1.])
        check(checks, f'AUC of tied scores is 0.5 for labels {labels}', metric['auc'], .5)
    perfect = ns['roc_pr']([1,0], [.9,.1], [1.,1.])
    check(checks, 'Average precision for a perfect two-event ranking is 1', perfect['ap'], 1.)
    illustrative = {
        'not_raw_data': True,
        'prethreshold_amplitudes_B2_B4_B6_B8_adc': [2000,800,600,400],
        'prethreshold_E_adc': 1800,
        'after_pulse_cut_gt_1000_and_zero_fill_E_adc': 0,
        'first_stored_entrance_hit_pdg_under_two_hit_permutations': [2212,1000010020],
        'label_permutation_note': 'Same two entrance hits, different storage order; illustrates the reviewed first-index label rule, not a rerun of the full MC reader.'
    }
    report = {'reviewed_base': BASE, 'mode': mode,
              'evidence_class': 'SYNTHETIC_UNIT_FIXTURES_NOT_PHYSICS_MC',
              'n_checks': len(checks), 'n_failed': sum(not c['pass'] for c in checks),
              'checks': checks, 'illustrative_mechanisms': illustrative,
              'scope': 'No raw-data bytes, ROOT, full producer, full repository test suite, or production metrics rerun.'}
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(report, indent=2) + '\n', encoding='utf-8')
    print(json.dumps(report, indent=2))
    return 1 if report['n_failed'] else 0

if __name__ == '__main__':
    raise SystemExit(main())
