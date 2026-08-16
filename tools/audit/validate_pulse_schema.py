#!/usr/bin/env python3
"""Validate a selected-pulse table against an explicit pulse schema.

REQUIRED columns: run, evt, stave, baseline_adc. Flags:
  P0 MISSING_REQUIRED_COLUMNS  a required column is absent
  P0 AMBIGUOUS_AMPLITUDE_ADC   amplitude_adc present without explicit peak_height_adc/peak_code_adc
  P0 DUPLICATE_PULSE_KEY       duplicate (run,evt,stave) pulse rows
Exits nonzero when any P0 finding is present.
"""
from __future__ import annotations
import argparse, hashlib, json
from pathlib import Path
import pandas as pd

REQUIRED = ['run', 'evt', 'stave', 'baseline_adc']
TOOL_VERSION = '1.1.0'

def validate(df: pd.DataFrame, schema_version: str):
    """Return the schema-validation stats dict (findings list is P0-gated)."""
    missing = [c for c in REQUIRED if c not in df]
    amplitude_cols = [c for c in df if c in {'amplitude_adc', 'peak_height_adc', 'peak_code_adc', 'net_adc'}]
    findings = []
    if missing:
        findings.append({'severity': 'P0', 'code': 'MISSING_REQUIRED_COLUMNS', 'detail': missing})
    if 'amplitude_adc' in df and not {'peak_height_adc', 'peak_code_adc'} & set(df):
        findings.append({'severity': 'P0', 'code': 'AMBIGUOUS_AMPLITUDE_ADC',
                         'detail': 'Replace or accompany amplitude_adc with explicit peak_height_adc/peak_code_adc'})
    key = ['run', 'evt', 'stave'] if 'evt' in df else ['run', 'eventno', 'stave']
    if all(c in df for c in key):
        ndups = int(df.duplicated(key, keep=False).sum())
        if ndups:
            findings.append({'severity': 'P0', 'code': 'DUPLICATE_PULSE_KEY', 'detail': {'key': key, 'rows': ndups}})
    return {'rows': len(df), 'columns': list(df.columns), 'schema_version': schema_version,
            'amplitude_columns': amplitude_cols, 'findings': findings}

def sha256_file(path: Path):
    """Hash a validation input without loading the full file into memory."""
    digest = hashlib.sha256()
    with path.open('rb') as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b''):
            digest.update(block)
    return digest.hexdigest()

def main(argv=None):
    ap = argparse.ArgumentParser(description='Validate a selected-pulse table against the required pulse schema (run,evt,stave,baseline_adc).')
    ap.add_argument('table', type=Path, help='Pulse table (.parquet, .csv, or compressed CSV).')
    ap.add_argument('--out', type=Path, required=True, help='Output JSON path for the validation report.')
    ap.add_argument('--schema-version', required=True, help='Schema version tag recorded in the report.')
    args = ap.parse_args(argv)
    if not args.table.is_file():
        raise SystemExit(f'table does not exist: {args.table}')
    df = pd.read_parquet(args.table) if args.table.suffix == '.parquet' else pd.read_csv(args.table)
    stats = validate(df, args.schema_version)
    stats['provenance'] = {
        'input_path': str(args.table),
        'input_size_bytes': args.table.stat().st_size,
        'input_sha256': sha256_file(args.table),
        'tool': 'tools/audit/validate_pulse_schema.py',
        'tool_version': TOOL_VERSION,
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(stats, indent=2) + '\n')
    print(json.dumps(stats, indent=2))
    raise SystemExit(1 if any(x['severity'] == 'P0' for x in stats['findings']) else 0)

if __name__ == '__main__': main()
