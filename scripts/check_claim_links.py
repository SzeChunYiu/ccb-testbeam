#!/usr/bin/env python3
"""Check that source paths in claim ledger exist in the local repo checkout.

Usage:
  python scripts/check_claim_links.py docs/claim_ledger.csv
Run from repository root.
"""
import csv, sys, pathlib
if len(sys.argv) != 2:
    print("Usage: check_claim_links.py docs/claim_ledger.csv")
    sys.exit(2)

root = pathlib.Path(".")
# source_data is intentionally excluded: it documents where input data lives
# (often large binaries or LUNARC-hosted paths), not a path that must exist in
# the repository checkout. The other four fields are repo-relative text artifacts.
fields = ["source_report", "source_script", "source_config", "source_manifest"]
missing = []
with open(sys.argv[1], newline="") as f:
    for i, row in enumerate(csv.DictReader(f), start=2):
        for field in fields:
            p = (row.get(field) or "").strip()
            if not p or p in {"NA", "N/A", "SOURCE_DATA_MISSING"}:
                continue
            if not (root / p).exists():
                missing.append((i, row.get("claim_id",""), field, p))

if missing:
    print("FAIL: missing claim source paths")
    for item in missing:
        print(f"line {item[0]} {item[1]} {item[2]} missing: {item[3]}")
    sys.exit(1)
print("OK: all claim source paths exist")
