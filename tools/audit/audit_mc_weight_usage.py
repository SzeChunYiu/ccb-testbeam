#!/usr/bin/env python3
"""Audit PrimaryWeight usage and summarize weighted effective sample size.

Opens a ROOT tree and looks for a weight branch (PrimaryWeight/weight/EventWeight).
If none exists, status is P0_NO_WEIGHT_BRANCH (nonzero exit): an MC truth reader
that ignores event weights biases every downstream physics number. Otherwise it
reports the effective sample size ESS = (sum w)^2 / sum(w^2).
"""
from __future__ import annotations
import argparse, json
from pathlib import Path
import numpy as np

WEIGHT_CANDIDATES = ('PrimaryWeight', 'weight', 'EventWeight')

def audit(root: Path, tree: str):
    """Return the weight-usage result dict for ``tree`` inside ROOT file ``root``."""
    import uproot
    t = uproot.open(root)[tree]
    keys = set(k.split(';')[0] for k in t.keys())
    candidates = [k for k in WEIGHT_CANDIDATES if k in keys]
    if not candidates:
        return {'status': 'P0_NO_WEIGHT_BRANCH', 'tree': tree, 'tree_keys_sample': sorted(keys)[:100]}
    name = candidates[0]
    w = np.asarray(t[name].array(library='np'), dtype=float).reshape(-1)
    w = w[np.isfinite(w)]
    sw = float(w.sum()); sw2 = float(np.square(w).sum())
    ess = sw * sw / sw2 if sw2 else 0.0
    return {'status': 'OK', 'tree': tree, 'branch': name, 'n': len(w), 'sum_w': sw,
            'ess': ess, 'ess_fraction': ess / len(w) if len(w) else 0.0,
            'min': float(w.min()) if len(w) else 0.0, 'max': float(w.max()) if len(w) else 0.0,
            'quantiles': {str(q): float(np.quantile(w, q)) for q in (0, .01, .5, .99, 1)} if len(w) else {}}

def main(argv=None):
    ap = argparse.ArgumentParser(description='Check a ROOT MC tree for an event-weight branch and report the effective sample size (ESS).')
    ap.add_argument('root', type=Path, help='ROOT file to inspect.')
    ap.add_argument('--tree', default='hibeam', help='Tree name inside the ROOT file (default: hibeam).')
    ap.add_argument('--out', type=Path, required=True, help='Output JSON path for the weight-usage report.')
    args = ap.parse_args(argv)
    if not args.root.is_file():
        raise SystemExit(f'ROOT file does not exist: {args.root}')
    res = audit(args.root, args.tree)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(res, indent=2))
    print(json.dumps(res, indent=2))
    raise SystemExit(0 if res['status'] == 'OK' else 1)

if __name__ == '__main__': main()
