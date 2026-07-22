from __future__ import annotations

import hashlib
import importlib.util
import json
from pathlib import Path

import pandas as pd
import pytest


SCRIPT = Path(__file__).parents[1] / "tools" / "audit" / "amplitude_convention_audit.py"
SPEC = importlib.util.spec_from_file_location("amplitude_convention_audit", SCRIPT)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def write_csv(
    path: Path,
    amplitude: list[float],
    baseline: list[float] | None = None,
) -> None:
    data: dict[str, list[float]] = {"amplitude_adc": amplitude}
    if baseline is not None:
        data["baseline_adc"] = baseline
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
    assert result["size_bytes"] == path.stat().st_size
    assert result["sha256"] == hashlib.sha256(path.read_bytes()).hexdigest()


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
    assert prefix["warning"] == "PREFIX_SAMPLE_ROW_ORDER_DEPENDENT"


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
