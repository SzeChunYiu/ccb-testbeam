from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import numpy as np
import pytest

MODULE_PATH = Path(__file__).parents[1] / "scripts" / "studies" / "clusterA_data_side.py"
spec = importlib.util.spec_from_file_location("clusterA_data_side", MODULE_PATH)
assert spec and spec.loader
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


def write_csv(path: Path, rows: list[list[str]]) -> None:
    header = (
        "run,evt,eventno,source_file_id,amp_B2,amp_B4,amp_B6,amp_B8,"
        "deltaE_data_adc,E_data_adc,stopping_layer,category\n"
    )
    path.write_text(header + "\n".join(",".join(row) for row in rows) + "\n")


def test_nonfinite_and_nonnumeric_rows_fail_closed(tmp_path: Path) -> None:
    base = ["1", "2", "3", "file", "10", "20", "30", "40", "10", "90", "B2", "x"]
    for bad in ("nan", "inf", "not-a-number"):
        row = base.copy()
        row[8] = bad
        path = tmp_path / f"{bad}.csv"
        write_csv(path, [row])
        with pytest.raises(module.InputError):
            module.load_data_rows(path)


def test_summary_is_explicitly_row_level(tmp_path: Path) -> None:
    path = tmp_path / "rows.csv"
    write_csv(
        path,
        [
            ["1", "10", "100", "fileA", "10", "20", "30", "40", "10", "90", "B2", "x"],
            ["1", "10", "101", "fileA", "11", "21", "31", "41", "11", "93", "B4", "y"],
            ["1", "11", "100", "fileA", "12", "22", "32", "42", "12", "96", "B2", "x"],
        ],
    )
    arrays, provenance = module.load_data_rows(path)
    result = module.summarize_data(arrays, 200.0)
    assert provenance["rows"] == 3
    assert result["n_unique_composite_keys"] == 2
    assert result["n_rows_beyond_first_per_composite_key"] == 1
    assert result["event_level_claims_authorized"] is False
    assert "row" in next(iter(result["stopping_layer_row_counts"]), "").lower() or (
        "stopping_layer_row_counts" in result
    )
    assert "corrupt" not in json.dumps(result).lower()


def test_summary_rejects_no_selected_rows(tmp_path: Path) -> None:
    path = tmp_path / "zero.csv"
    write_csv(
        path,
        [["1", "10", "100", "fileA", "0", "0", "0", "0", "0", "0", "", ""]],
    )
    arrays, _ = module.load_data_rows(path)
    with pytest.raises(module.InputError, match="no data rows"):
        module.summarize_data(arrays, 200.0)


def test_primary_weight_alignment_is_exact() -> None:
    event_indices = np.array([100, 102, 103])
    weights = np.array([1.0, 2.0, 3.0, 4.0])
    np.testing.assert_allclose(
        module.align_primary_weights(event_indices, 100, weights),
        np.array([1.0, 3.0, 4.0]),
    )


def test_primary_weight_alignment_rejects_invalid_contracts() -> None:
    with pytest.raises(module.InputError):
        module.align_primary_weights(np.array([9]), 10, np.array([1.0]))
    with pytest.raises(module.InputError):
        module.align_primary_weights(np.array([10]), 10, np.array([np.inf]))
    with pytest.raises(module.InputError):
        module.align_primary_weights(np.array([10]), 10, np.array([[-1.0]]))


def test_weighted_hexbin_passes_primary_weights() -> None:
    class FakeAxes:
        def __init__(self) -> None:
            self.kwargs = None

        def hexbin(self, *args, **kwargs):
            self.kwargs = kwargs
            return "image"

    axes = FakeAxes()
    result = module.weighted_hexbin(
        axes,
        np.array([1.0, 2.0]),
        np.array([3.0, 4.0]),
        np.array([1.0, 100.0]),
    )
    assert result == "image"
    np.testing.assert_allclose(axes.kwargs["C"], np.array([1.0, 100.0]))
    assert axes.kwargs["reduce_C_function"] is np.sum
    assert axes.kwargs["bins"] == "log"


def test_atomic_json_replaces_complete_document(tmp_path: Path) -> None:
    path = tmp_path / "result.json"
    module.atomic_json(path, {"status": "VALIDATED", "finding_count": 0})
    assert json.loads(path.read_text()) == {"finding_count": 0, "status": "VALIDATED"}
    assert not list(tmp_path.glob(".*.tmp"))
