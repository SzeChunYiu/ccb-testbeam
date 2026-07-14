#!/usr/bin/env python3
"""Verify every quantitative claim in academic chapters has a claim_ledger.csv entry."""
import csv
import re
import sys
from pathlib import Path

# Patterns that indicate a quantitative claim
CLAIM_PATTERNS = [
    r'\b(\d+\.?\d*)\s*(ns|MHz|ADC|MeV|ADC/MeV|mm|cm|g/cm²|%|fraction)\b',
    r'\b(σ|σ₆₈|σ\s*≈|≈)\s*(\d+\.?\d*)',
    r'\b(AUC|RMS|χ²)\s*[=≈]\s*(\d+\.?\d*)',
]

def load_ledger_values(ledger_path):
    """Extract all values from claim ledger for fuzzy matching."""
    values = set()
    with open(ledger_path) as f:
        for row in csv.DictReader(f):
            if row.get('value'):
                values.add(row['value'].strip())
    return values

def main():
    repo = Path(__file__).resolve().parent.parent
    os.chdir(repo)
    
    ledger_path = repo / 'docs' / 'claim_ledger.csv'
    if not ledger_path.exists():
        print("SKIP: claim_ledger.csv not found")
        sys.exit(0)
    
    ledger_values = load_ledger_values(ledger_path)
    
    chapters_dir = repo / 'docs' / 'academic_chapters'
    if not chapters_dir.exists():
        print("SKIP: academic_chapters not found")
        sys.exit(0)
    
    warnings = 0
    for chapter in sorted(chapters_dir.glob('*.md')):
        with open(chapter) as f:
            text = f.read()
        for pattern in CLAIM_PATTERNS:
            for m in re.finditer(pattern, text):
                val = m.group(0)
                # Check if this value (or close variant) is in ledger
                found = False
                for lv in ledger_values:
                    if val[:10] in lv or lv[:10] in val:
                        found = True
                        break
                if not found:
                    print(f"WARNING: {chapter.name}: possible unregistered claim: '{val}'")
                    warnings += 1
    
    if warnings:
        print(f"\n{warnings} potential unregistered claim(s). Review and add to claim_ledger.csv if needed.")
        sys.exit(1)
    print("✓ All detectable claims appear in claim ledger.")
    sys.exit(0)

if __name__ == '__main__':
    main()
