#!/usr/bin/env python3
"""Prove event-key uniqueness and safe join cardinality before physics merging.

Given two tables (parquet or csv), attempt a strict ``one_to_one`` inner merge on
a composite key (default ``run evt``). Exits nonzero (P0) if the join is not
one-to-one, i.e. duplicate composite keys exist on either side and rows would fan
out. Reproducible physics merges must key on the full composite event identifier,
never eventno alone.
"""
from __future__ import annotations
import argparse, json
from pathlib import Path
import pandas as pd

def load(p: Path):
    return pd.read_parquet(p) if p.suffix == '.parquet' else pd.read_csv(p)

def validate(left: Path, right: Path, keys):
    """Return a result dict; ``one_to_one`` is False when the merge fans out."""
    l, r = load(left), load(right)
    for name, df in [('left', l), ('right', r)]:
        miss = [k for k in keys if k not in df]
        if miss:
            raise SystemExit(f'{name} missing keys {miss}')
    ldup = int(l.duplicated(keys, keep=False).sum())
    rdup = int(r.duplicated(keys, keep=False).sum())
    # Use validate one_to_one as the strict default; callers can aggregate first.
    ok = True; err = ''
    try:
        m = l.merge(r, on=keys, how='inner', validate='one_to_one', suffixes=('_l', '_r'))
    except Exception as e:
        ok = False; err = str(e); m = l.merge(r, on=keys, how='inner', suffixes=('_l', '_r'))
    return {'keys': keys, 'left_rows': len(l), 'right_rows': len(r),
            'left_duplicate_rows': ldup, 'right_duplicate_rows': rdup,
            'joined_rows': len(m), 'one_to_one': ok, 'error': err}

def main(argv=None):
    ap = argparse.ArgumentParser(description='Prove composite-key one_to_one join cardinality between two event tables before merging physics.')
    ap.add_argument('left', type=Path, help='Left table (.parquet or .csv).')
    ap.add_argument('right', type=Path, help='Right table (.parquet or .csv).')
    ap.add_argument('--keys', nargs='+', default=['run', 'evt'], help='Composite join key columns (default: run evt).')
    ap.add_argument('--out', type=Path, required=True, help='Output JSON path for the cardinality report.')
    args = ap.parse_args(argv)
    for label, p in [('left', args.left), ('right', args.right)]:
        if not p.is_file():
            raise SystemExit(f'{label} table does not exist: {p}')
    res = validate(args.left, args.right, list(args.keys))
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(res, indent=2))
    print(json.dumps(res, indent=2))
    raise SystemExit(0 if res['one_to_one'] else 1)

if __name__ == '__main__': main()
