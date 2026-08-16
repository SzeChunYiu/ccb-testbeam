from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import numpy as np
import pandas as pd


SCRIPT = Path(__file__).parents[1] / "tools" / "audit" / "amplitude_convention_audit.py"
SPEC = importlib.util.spec_from_file_location("amplitude_convention_audit_baseline_quality", SCRIPT)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def test_empty_baseline_column_is_non_accepting(tmp_path: Path) -> None:
    path = tmp_path / "empty_baseline.csv"
    output = tmp_path / "audit.json"
    pd.DataFrame({
        "amplitude_adc": [6700.0, 6750.0, 6800.0],
        "baseline_adc": [np.nan, np.nan, np.nan],
    }).to_csv(path, index=False)

    result = MODULE.audit(path, None, 3500.0, 5000.0)
    code = MODULE.main([str(path), "--output", str(output)])
    payload = json.loads(output.read_text(encoding="utf-8"))

    assert result["convention"] == "ABSOLUTE"
    assert result["baseline_resolution"] == "RESOLVED"
    assert result["baseline_data_quality"] == "INCOMPLETE"
    assert result["finite_amplitude_baseline_pairs"] == 0
    assert result["finite_amplitude_rows_without_finite_baseline"] == 3
    assert result["baseline_pair_coverage"] == 0.0
    assert result["convention_acceptance"] == "BASELINE_DATA_INVALID"
    assert result["subtract_baseline_correct"] is None
    assert "INCOMPLETE_BASELINE_FOR_FINITE_AMPLITUDES" in result["warnings"]
    assert code == 1
    assert payload["n_invalid_baseline_data_tables"] == 1


def test_partial_baseline_coverage_is_non_accepting(tmp_path: Path) -> None:
    path = tmp_path / "partial_baseline.csv"
    pd.DataFrame({
        "amplitude_adc": [6700.0, 6750.0, 6800.0],
        "baseline_adc": [6752.0, "bad", 6752.0],
    }).to_csv(path, index=False)

    result = MODULE.audit(path, None, 3500.0, 5000.0)

    assert result["finite_amplitude_baseline_pairs"] == 2
    assert result["finite_amplitude_rows_without_finite_baseline"] == 1
    assert result["baseline_pair_coverage"] == 2 / 3
    assert result["baseline_data_quality"] == "INCOMPLETE"
    assert result["convention_acceptance"] == "BASELINE_DATA_INVALID"
    assert result["subtract_baseline_correct"] is None


def test_complete_baseline_coverage_remains_acceptable(tmp_path: Path) -> None:
    path = tmp_path / "complete_baseline.csv"
    pd.DataFrame({
        "amplitude_adc": [6700.0, 6750.0, 6800.0],
        "baseline_adc": [6752.0, 6752.0, 6752.0],
    }).to_csv(path, index=False)

    result = MODULE.audit(path, None, 3500.0, 5000.0)

    assert result["baseline_data_quality"] == "COMPLETE"
    assert result["finite_amplitude_rows_without_finite_baseline"] == 0
    assert result["baseline_pair_coverage"] == 1.0
    assert result["convention_acceptance"] == "ACCEPTABLE"
    assert result["subtract_baseline_correct"] is True
