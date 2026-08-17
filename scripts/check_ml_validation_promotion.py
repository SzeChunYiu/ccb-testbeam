#!/usr/bin/env python3
"""Fail closed if an ML/model-selection row is promoted without validation gates."""
from __future__ import annotations

import csv
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
LEDGER = ROOT / "chatgpt_todo/ML_VALIDATION_LEDGER.csv"
PROMOTED = {"SUPPORTED", "VALIDATED", "PRODUCTION", "VALIDATED_TRANSFER"}
REQUIRED_PASS = (
    "label_independence",
    "leakage_controls",
    "split_independence",
    "multiplicity_policy",
    "untouched_validation",
    "strong_baseline",
    "uncertainty_dependence",
    "transfer_slice_review",
)


def main() -> int:
    errors: list[str] = []
    with LEDGER.open(newline="", encoding="utf-8") as fh:
        reader = csv.DictReader(fh)
        required_columns = {
            "ml_id",
            "study_or_claim",
            "status",
            "provenance",
            *REQUIRED_PASS,
        }
        missing = required_columns - set(reader.fieldnames or [])
        if missing:
            print(f"ML_VALIDATION_PROMOTION: FAIL\n- missing columns: {sorted(missing)}")
            return 1
        for row in reader:
            status = (row.get("status") or "").strip().upper()
            if status not in PROMOTED:
                continue
            ident = row.get("ml_id", "<unknown>")
            for field in REQUIRED_PASS:
                if (row.get(field) or "").strip().upper() != "PASS":
                    errors.append(
                        f"{ident}: promoted status {status} requires {field}=PASS; "
                        f"got {(row.get(field) or '').strip()!r}"
                    )
            if (row.get("provenance") or "").strip().upper() != "COMPLETE":
                errors.append(f"{ident}: promoted status {status} requires provenance=COMPLETE")

    if errors:
        print("ML_VALIDATION_PROMOTION: FAIL")
        for error in errors:
            print(f"- {error}")
        return 1
    print("ML_VALIDATION_PROMOTION: PASS")
    print("No promoted ML/model-selection row bypasses untouched-validation/multiplicity gates.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
