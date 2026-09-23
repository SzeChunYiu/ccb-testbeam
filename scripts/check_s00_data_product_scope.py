#!/usr/bin/env python3
"""Validate that the S00 exact-count gate is bound to one explicit waveform product.

This does not prove the archive lineage. It prevents the historical 640,737
expected count from silently acquiring meaning for a different HRDv width/product.
"""
from __future__ import annotations

from pathlib import Path
import sys

import yaml

ROOT = Path(__file__).resolve().parents[1]
CONFIG = ROOT / "configs/s00_reproduction.yaml"


def main() -> int:
    cfg = yaml.safe_load(CONFIG.read_text(encoding="utf-8"))
    contract = cfg.get("data_product_contract")
    errors: list[str] = []
    if not isinstance(contract, dict):
        errors.append("missing data_product_contract mapping")
    else:
        samples = int(cfg.get("samples_per_channel", -1))
        contract_samples = int(contract.get("samples_per_channel", -2))
        n_channels = int(contract.get("n_channels", -1))
        expected_words = int(contract.get("expected_words_per_event", -1))
        if samples != contract_samples:
            errors.append(
                f"samples_per_channel={samples} disagrees with data-product contract {contract_samples}"
            )
        if expected_words != n_channels * contract_samples:
            errors.append(
                f"expected_words_per_event={expected_words} != n_channels*samples={n_channels * contract_samples}"
            )
        if contract.get("expected_counts_scope") != "THIS_EXACT_8X18_PRODUCT_ONLY":
            errors.append("expected_counts_scope must remain THIS_EXACT_8X18_PRODUCT_ONLY")
        if bool(contract.get("authorising_detector_claims", True)):
            errors.append(
                "historical S00 data-product contract must remain non-authorising until archive lineage is independently bound"
            )
        if contract_samples != 18 or n_channels != 8:
            errors.append(
                "the historical S00 expected-count table is only registered for the explicit 8x18 product"
            )
    baseline = cfg.get("baseline_samples", [])
    if not isinstance(baseline, list) or any(int(i) < 0 or int(i) >= int(cfg.get("samples_per_channel", 0)) for i in baseline):
        errors.append("baseline_samples fall outside the configured waveform width")
    if "expected_counts" not in cfg:
        errors.append("historical S00 config unexpectedly lacks expected_counts")

    if errors:
        print("S00_DATA_PRODUCT_SCOPE: FAIL")
        for error in errors:
            print(f"- {error}")
        return 1
    print("S00_DATA_PRODUCT_SCOPE: PASS")
    print("The exact-count gate is scoped to HRDv_8x18_S00_HISTORICAL only.")
    print("PASS does not establish archive lineage or authorize detector claims.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
