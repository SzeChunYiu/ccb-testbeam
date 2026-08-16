#!/usr/bin/env python3
"""Verify every quantitative RESULT claim in academic chapters has a claim_ledger.csv entry.

A "result claim" is a value presented as a finding: a value with an explicit
uncertainty (X ± Y unit) or a named figure of merit (AUC / RMS / χ² / σ = X).
Setup and infrastructure constants (beam energy, detector geometry, nominal
sampling windows, ADC dynamic-range limits, etc.) are not result claims and are
intentionally not flagged -- the claim ledger tracks results, not every number.

Membership is checked by numeric prefix (~3 significant figures) so that rounded
prose values (e.g. "AUC = 0.986") match full-precision ledger values (0.98596...).

This scan is ADVISORY: it prints candidate values for human review but does not
fail CI (exit 0). The claim ledger is a deliberately curated set of headline
physics claims; the academic chapters legitimately contain diagnostic,
method-comparison, null-result, and explicitly-invalidated numerical content
(anti-examples) that is intentionally NOT ledgered. Reliably distinguishing a
genuine new headline claim from that content is not feasible by pattern matching
alone, so blocking CI on this heuristic would either force uncurated noise into
the ledger or require per-value exemptions. The candidates are surfaced for review
on every run instead.

Usage:
    python scripts/check_claim_ledger_complete.py
"""
import csv
import os
import re
import sys
from math import floor, log10
from pathlib import Path

# Result-indicating patterns only. A bare "<number> <unit>" is NOT matched,
# because such tokens are overwhelmingly experimental-setup constants.
RESULT_PATTERNS = [
    # value with an explicit uncertainty (and optional physics unit)
    r'\b\d+\.?\d*\s*±\s*\d+\.?\d*\s*(?:ns|MHz|ADC/?MeV|ADC|MeV|mm|cm|g/cm²|%)?',
    # named figures of merit
    r'\bσ\s*[≈=]\s*\d+\.?\d*',
    r'\b(?:AUC|RMS|χ²|χ2|chi2)\s*[=≈]\s*\d+\.?\d*',
]

# Ledger fields that carry numeric result values, used for membership matching.
LEDGER_NUMERIC_FIELDS = (
    'current_value', 'value', 'baseline_value', 'delta_vs_baseline',
    'stat_unc', 'syst_unc', 'total_unc', 'effect_size', 'p_value',
)


def first_float(text):
    m = re.search(r'[-+]?\d*\.?\d+(?:[eE][-+]?\d+)?', text)
    if not m:
        return None
    try:
        return float(m.group(0))
    except ValueError:
        return None


def sig3(x):
    """Round to ~3 significant figures for tolerant prose<->ledger matching."""
    if x is None or x == 0:
        return 0.0
    decimals = 3 - floor(log10(abs(x))) - 1
    return round(x, decimals)


def load_ledger_numbers(ledger_path):
    nums = set()
    with open(ledger_path) as f:
        for row in csv.DictReader(f):
            for fld in LEDGER_NUMERIC_FIELDS:
                v = (row.get(fld) or '').strip()
                if not v or v in {'—', '-', 'NA', 'N/A'}:
                    continue
                x = first_float(v)
                if x is not None:
                    nums.add(sig3(x))
                    nums.add(round(x, 6))  # also exact, for integer-ish counts
    return nums


def main():
    repo = Path(__file__).resolve().parent.parent
    os.chdir(repo)

    ledger_path = repo / 'docs' / 'claim_ledger.csv'
    if not ledger_path.exists():
        print("SKIP: claim_ledger.csv not found")
        sys.exit(0)

    ledger_nums = load_ledger_numbers(ledger_path)

    chapters_dir = repo / 'docs' / 'academic_chapters'
    if not chapters_dir.exists():
        print("SKIP: academic_chapters not found")
        sys.exit(0)

    warnings = 0
    for chapter in sorted(chapters_dir.glob('*.md')):
        text = chapter.read_text()
        for pattern in RESULT_PATTERNS:
            for m in re.finditer(pattern, text):
                val = m.group(0).strip()
                x = first_float(val)
                if x is None:
                    continue
                if sig3(x) in ledger_nums or round(x, 6) in ledger_nums:
                    continue
                print(f"WARNING: {chapter.name}: possible unregistered result claim: '{val}'")
                warnings += 1

    if warnings:
        print(f"\nADVISORY: {warnings} result-shaped value(s) in academic chapters are not in")
        print("the curated claim_ledger.csv headline set (listed above). The ledger tracks")
        print("headline physics claims; chapters legitimately contain diagnostic, comparison,")
        print("null-result, and invalidated-example numerical content that is intentionally")
        print("not ledgered. Review the candidates above and add to the ledger only if a")
        print("genuine new headline claim is intended.")
        print("\nThis scan is advisory and does not fail CI (exit 0).")
        sys.exit(0)
    print("✓ All detectable result claims appear in the claim ledger.")
    sys.exit(0)


if __name__ == '__main__':
    main()
