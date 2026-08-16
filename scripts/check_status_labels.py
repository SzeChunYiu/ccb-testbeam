#!/usr/bin/env python3
"""Check status labels in docs/claim_ledger.csv.

Usage:
  python scripts/check_status_labels.py docs/claim_ledger.csv
"""
import csv, sys
allowed = {
    "VALIDATED", "DONE_DATA_ONLY", "TRUTH_LEVEL_MC_ONLY", "TENSION", "FAIL",
    "CORRECTED", "BLOCKED", "GATED", "SUPERSEDED",
    # Honest audit-downgrade labels (claim honestly downgraded by the audit):
    "REVIEW", "FLAWED",
}

if len(sys.argv) != 2:
    print("Usage: check_status_labels.py docs/claim_ledger.csv")
    sys.exit(2)

fail = []
with open(sys.argv[1], newline="") as f:
    for i, row in enumerate(csv.DictReader(f), start=2):
        status = (row.get("status") or "").strip()
        if status and status not in allowed:
            fail.append((i, row.get("claim_id",""), status))

if fail:
    print("FAIL: invalid status labels")
    for i, cid, status in fail:
        print(f"line {i} {cid}: {status}")
    sys.exit(1)
print("OK: all statuses allowed")
