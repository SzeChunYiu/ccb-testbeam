from __future__ import annotations

import hashlib
import importlib.util
import json
from pathlib import Path

import numpy as np
import pandas as pd
import pytest


SCRIPT = Path(__file__).parents[1] / "tools" / "audit" / "amplitude_convention_audit.py"
SPEC = importlib.util.spec_from_file_location("amplitude_convention_audit", SCRIPT)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def write_csv(
    path: Path,
    amplitude: list[float | str],
    baseline: list[float] | None = None,
    **extra_columns: list[float | str],
) -> None:
    data: dict[str, list[float | str]] = {"amplitude_adc": amplitude}
    if baseline is not None:
        data["baseline_adc"] = baseline
    data.update(extra_columns)
    pd.DataFrame(data).to_csv(path, index=False)


def test_absolute_classification_records_provenance(tmp_path: Path) -> None:
    path = tmp_path / "absolute.csv"
    write_csv(path, [6700, 6750, 6800], [6752, 6752, 6752])

    result = MODULE.audit(path, None, 3500.0, 5000.0)

    assert result["convention"] == "ABSOLUTE"
    assert result["classification_scope"] == "FULL_TABLE"
    assert result["input_truncated"] is False
    assert result["subtract_baseline_correct"] is True
    assert result["median_abs_amplitude_minus_baseline"] == pytest.approx(48.0)
    assert result["finite_amplitude_baseline_pairs"] == 3
    assert result["size_bytes"] == path.stat().st_size
    assert result["sha256"] == hashlib.sha256(path.read_bytes()).hexdigest()


def test_baseline_rms_is_not_used_as_pedestal_level(tmp_path: Path) -> None:
    path = tmp_path / "rms_only.csv"
    write_csv(
        path,
        [6700, 6750, 6800],
        baseline_rms_adc=[2.0, 2.1, 2.2],
    )

    result = MODULE.audit(path, None, 3500.0, 5000.0)

    assert result["convention"] == "ABSOLUTE"
    assert result["baseline_column"] is None
    assert result["baseline_candidate_count"] == 0
    assert result["auxiliary_baseline_columns"] == ["baseline_rms_adc"]
    assert result["subtract_baseline_correct"] is None
    assert result["warning_baseline"] == "AMPLITUDE_CONVENTION_WITHOUT_BASELINE_LEVEL"
    assert "median_abs_amplitude_minus_baseline" not in result


def test_pedestal_level_selected_when_rms_is_also_present(tmp_path: Path) -> None:
    path = tmp_path / "level_and_rms.csv"
    write_csv(
        path,
        [6700, 6750, 6800],
        [6752, 6752, 6752],
        baseline_rms_adc=[2.0, 2.1, 2.2],
    )

    result = MODULE.audit(path, None, 3500.0, 5000.0)

    assert result["baseline_column"] == "baseline_adc"
    assert result["baseline_candidates"] == ["baseline_adc"]
    assert result["auxiliary_baseline_columns"] == ["baseline_rms_adc"]
    assert result["subtract_baseline_correct"] is True
    assert result["median_abs_amplitude_minus_baseline"] == pytest.approx(48.0)


def test_multiple_baseline_levels_are_not_chosen_implicitly(tmp_path: Path) -> None:
    path = tmp_path / "multiple_levels.csv"
    write_csv(
        path,
        [6700, 6750, 6800],
        [6752, 6752, 6752],
        baseline_mean_adc=[6751, 6751, 6751],
    )

    result = MODULE.audit(path, None, 3500.0, 5000.0)

    assert result["baseline_column"] is None
    assert result["baseline_candidate_count"] == 2
    assert result["subtract_baseline_correct"] is None
    assert result["warning_baseline"] == "MULTIPLE_BASELINE_LEVEL_COLUMNS"


def test_net_and_ambiguous_are_distinct(tmp_path: Path) -> None:
    net = tmp_path / "net.csv"
    ambiguous = tmp_path / "ambiguous.csv"
    write_csv(net, [100, 200, 300])
    write_csv(ambiguous, [4000, 4200, 4400])

    assert MODULE.audit(net, None, 3500.0, 5000.0)["convention"] == "NET"
    assert MODULE.audit(ambiguous, None, 3500.0, 5000.0)["convention"] == "AMBIGUOUS"


def test_full_table_default_avoids_prefix_order_bias(tmp_path: Path) -> None:
    path = tmp_path / "ordered.csv"
    write_csv(path, [100, 200, 6700, 6800, 6900])

    full = MODULE.audit(path, None, 3500.0, 5000.0)
    prefix = MODULE.audit(path, 2, 3500.0, 5000.0)

    assert full["convention"] == "ABSOLUTE"
    assert full["classification_scope"] == "FULL_TABLE"
    assert prefix["convention"] == "NET"
    assert prefix["classification_scope"] == "PREFIX_SAMPLE"
    assert prefix["input_truncated"] is True
    assert "PREFIX_SAMPLE_ROW_ORDER_DEPENDENT" in prefix["warnings"]


def test_prefix_mode_is_non_accepting(tmp_path: Path) -> None:
    path = tmp_path / "input.csv"
    output = tmp_path / "audit.json"
    write_csv(path, [100, 200, 300])

    code = MODULE.main([
        str(path), "--output", str(output), "--max-rows", "2"
    ])
    payload = json.loads(output.read_text(encoding="utf-8"))

    assert code == 1
    assert payload["n_partial"] == 1
    assert payload["tables"][0]["classification_scope"] == "PREFIX_SAMPLE"


def test_nonfinite_amplitudes_are_excluded_and_fail_gate(tmp_path: Path) -> None:
    path = tmp_path / "nonfinite.csv"
    output = tmp_path / "audit.json"
    write_csv(path, [100.0, 200.0, np.inf, -np.inf])

    result = MODULE.audit(path, None, 3500.0, 5000.0)
    code = MODULE.main([str(path), "--output", str(output)])
    payload = json.loads(output.read_text(encoding="utf-8"))

    assert result["convention"] == "NET"
    assert result["finite_amplitude_rows"] == 2
    assert result["nonfinite_amplitude_rows"] == 2
    assert "NONFINITE_AMPLITUDE_VALUES_EXCLUDED" in result["warnings"]
    assert code == 1
    assert payload["n_nonfinite_tables"] == 1


def test_nonnumeric_amplitudes_are_excluded_and_fail_gate(tmp_path: Path) -> None:
    path = tmp_path / "nonnumeric.csv"
    output = tmp_path / "audit.json"
    write_csv(path, [100.0, "bad-adc", 300.0])

    result = MODULE.audit(path, None, 3500.0, 5000.0)
    code = MODULE.main([str(path), "--output", str(output)])
    payload = json.loads(output.read_text(encoding="utf-8"))

    assert result["convention"] == "NET"
    assert result["finite_amplitude_rows"] == 2
    assert result["nonnumeric_amplitude_rows"] == 1
    assert "NONNUMERIC_AMPLITUDE_VALUES_EXCLUDED" in result["warnings"]
    assert code == 1
    assert payload["n_nonnumeric_tables"] == 1


def test_only_nonnumeric_values_are_rejected(tmp_path: Path) -> None:
    path = tmp_path / "only_nonnumeric.csv"
    write_csv(path, ["bad", "missing"])

    with pytest.raises(ValueError, match="no finite numeric values"):
        MODULE.audit(path, None, 3500.0, 5000.0)


def test_nonfinite_baseline_pairs_do_not_corrupt_diagnostics(tmp_path: Path) -> None:
    path = tmp_path / "baseline_nonfinite.csv"
    write_csv(path, [6700.0, 6800.0, np.inf], [6752.0, np.inf, 6752.0])

    result = MODULE.audit(path, None, 3500.0, 5000.0)

    assert result["convention"] == "ABSOLUTE"
    assert result["finite_amplitude_baseline_pairs"] == 1
    assert result["baseline_median"] == pytest.approx(6752.0)
    assert result["median_abs_amplitude_minus_baseline"] == pytest.approx(52.0)


def test_only_nonfinite_values_are_rejected(tmp_path: Path) -> None:
    path = tmp_path / "only_nonfinite.csv"
    write_csv(path, [np.inf, -np.inf])

    with pytest.raises(ValueError, match="no finite numeric values"):
        MODULE.audit(path, None, 3500.0, 5000.0)


def test_missing_amplitude_is_explicit_skip(tmp_path: Path) -> None:
    path = tmp_path / "other.csv"
    pd.DataFrame({"value": [1]}).to_csv(path, index=False)

    result = MODULE.audit(path, None, 3500.0, 5000.0)

    assert result["status"] == "SKIPPED"
    assert result["reason"] == "NO_AMPLITUDE_ADC"


def test_main_records_read_errors_and_returns_nonzero(tmp_path: Path) -> None:
    good = tmp_path / "good.csv"
    bad = tmp_path / "bad.csv"
    output = tmp_path / "audit.json"
    write_csv(good, [100, 200])
    bad.write_text('amplitude_adc\n"unterminated', encoding="utf-8")

    code = MODULE.main([str(good), str(bad), "--output", str(output)])
    payload = json.loads(output.read_text(encoding="utf-8"))

    assert code == 1
    assert payload["n_classified"] == 1
    assert payload["n_errors"] == 1
    assert payload["errors"][0]["path"] == str(bad)


def test_invalid_threshold_gap_is_rejected() -> None:
    with pytest.raises(ValueError, match="net_max"):
        MODULE.classify(100.0, 3000.0, 3000.0)


def test_nonfinite_classification_value_is_rejected() -> None:
    with pytest.raises(ValueError, match="must be finite"):
        MODULE.classify(np.inf, 3500.0, 5000.0)
