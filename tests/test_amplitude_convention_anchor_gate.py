from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pandas as pd

SCRIPT = Path(__file__).parents[1] / "tools" / "audit" / "amplitude_convention_audit.py"
SPEC = importlib.util.spec_from_file_location("amplitude_convention_audit", SCRIPT)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def write(path: Path, amplitude: list[float], baseline: list[float] | None = None) -> None:
    data = {"amplitude_adc": amplitude}
    if baseline is not None:
        data["baseline_adc"] = baseline
    pd.DataFrame(data).to_csv(path, index=False)


def test_raw_median_net_label_without_pedestal_is_non_accepting(tmp_path: Path) -> None:
    path = tmp_path / "unanchored_net.csv"
    output = tmp_path / "audit.json"
    write(path, [2600.0, 2625.0, 2650.0])

    result = MODULE.audit(path, None, 3500.0, 5000.0)
    code = MODULE.main([str(path), "--output", str(output)])
    payload = json.loads(output.read_text(encoding="utf-8"))

    assert result["convention"] == "NET"
    assert result["convention_evidence"] == "RAW_MEDIAN_HEURISTIC"
    assert result["convention_acceptance"] == "UNANCHORED"
    assert result["subtract_baseline_correct"] is None
    assert "UNANCHORED_AMPLITUDE_CONVENTION" in result["warnings"]
    assert payload["n_unanchored_conventions"] == 1
    assert code == 1


def test_raw_median_absolute_label_without_pedestal_is_non_accepting(tmp_path: Path) -> None:
    path = tmp_path / "unanchored_absolute.csv"
    output = tmp_path / "audit.json"
    write(path, [6700.0, 6750.0, 6800.0])

    code = MODULE.main([str(path), "--output", str(output)])
    payload = json.loads(output.read_text(encoding="utf-8"))

    assert payload["tables"][0]["convention"] == "ABSOLUTE"
    assert payload["tables"][0]["convention_acceptance"] == "UNANCHORED"
    assert payload["n_unresolved_absolute_baselines"] == 1
    assert payload["n_unanchored_conventions"] == 1
    assert code == 1


def test_unique_pedestal_anchor_allows_acceptance(tmp_path: Path) -> None:
    path = tmp_path / "anchored.csv"
    output = tmp_path / "audit.json"
    write(path, [6700.0, 6750.0, 6800.0], [6752.0, 6752.0, 6752.0])

    code = MODULE.main([str(path), "--output", str(output)])
    payload = json.loads(output.read_text(encoding="utf-8"))
    result = payload["tables"][0]

    assert result["convention_evidence"] == "PEDESTAL_ANCHORED"
    assert result["convention_acceptance"] == "ACCEPTABLE"
    assert result["baseline_resolution"] == "RESOLVED"
    assert payload["n_unanchored_conventions"] == 0
    assert code == 0
