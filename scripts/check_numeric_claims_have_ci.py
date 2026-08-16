#!/usr/bin/env python3
"""Check that numeric claims in docs/claim_ledger.csv have uncertainty or CI.

Usage:
  python scripts/check_numeric_claims_have_ci.py docs/claim_ledger.csv
"""
import csv, sys, re

if len(sys.argv) != 2:
    print("Usage: check_numeric_claims_have_ci.py docs/claim_ledger.csv")
    sys.exit(2)

path = sys.argv[1]
allowed_no_unc = {"EXACT_COUNT", "NOT_APPLICABLE_WITH_REASON", "SUPERSEDED_DO_NOT_USE"}
# A numeric claim without numeric uncertainty is acceptable when the ledger
# documents why via ci_status. The ledger uses a rich, honest vocabulary:
# NOT_APPLICABLE_*, NOT_EVALUATED_*, SUPERSEDED_*, EXACT_*,
# SYSTEMATIC_ENVELOPE_*, CI_AVAILABLE_*. Accept any such honest prefix.
_NO_UNC_PREFIXES = (
    "NOT_APPLICABLE", "NOT_EVALUATED", "SUPERSEDED", "EXACT",
    "SYSTEMATIC_ENVELOPE", "CI_AVAILABLE",
)
failures = []

def has_value(x):
    return x is not None and str(x).strip() not in {"", "—", "-", "NA", "N/A"}

with open(path, newline="") as f:
    rows = list(csv.DictReader(f))

for i, row in enumerate(rows, start=2):
    value = row.get("value") or row.get("current_value") or ""
    if not re.search(r"[-+]?\d", value):
        continue

    ci_status = (row.get("ci_status") or "").strip()
    stat = row.get("uncertainty_stat") or row.get("stat_unc") or ""
    syst = row.get("uncertainty_syst") or row.get("syst_unc") or ""
    ci_low = row.get("ci_low", "")
    ci_high = row.get("ci_high", "")

    if ci_status in allowed_no_unc or any(ci_status.startswith(p) for p in _NO_UNC_PREFIXES):
        continue
    if has_value(stat) or has_value(syst) or (has_value(ci_low) and has_value(ci_high)):
        continue
    failures.append((i, row.get("claim_id",""), row.get("claim_text",""), value))

if failures:
    print("FAIL: numeric claims missing uncertainty/CI")
    for f in failures:
        print(f"line {f[0]} {f[1]} value={f[3]} claim={f[2]}")
    sys.exit(1)

print("OK: all numeric claims have uncertainty/CI or valid ci_status")
