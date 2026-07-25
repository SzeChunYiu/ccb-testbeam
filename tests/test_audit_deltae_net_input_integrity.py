from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pytest

MODULE_PATH = Path(__file__).parents[1] / "tools" / "audit" / "audit_deltae_net_input_integrity.py"
SPEC = importlib.util.spec_from_file_location("deltae_net_audit", MODULE_PATH)
assert SPEC and SPEC.loader
AUDIT = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(AUDIT)

VULNERABLE = '''
import numpy as np
import pandas as pd
LAYERS = ("B2", "B4", "B6", "B8")
def build_event_table(pulses, *, source_file_id, threshold_adc=200.0,
                      amplitude_column=None, amplitude_convention=None):
    ampcol = amplitude_column
    df = pulses[["run", "evt", "eventno", "stave", ampcol]].copy()
    signal_column = "_signal_height_adc"
    df[signal_column] = df[ampcol]
    n_comp = int(df.groupby(["run", "evt"], dropna=False).size().size)
    agg = (df.groupby(["run", "evt", "stave"], dropna=False)[signal_column]
             .max().reset_index())
    wide = (agg.pivot_table(index=["run", "evt"], columns="stave",
                            values=signal_column, aggfunc="max").reset_index())
    wide.insert(0, "source_file_id", source_file_id)
    for layer in LAYERS:
        wide[f"amp_{layer}"] = wide[layer].fillna(0.0) if layer in wide.columns else 0.0
    wide["deltaE_data_adc"] = wide["amp_B2"]
    wide["E_data_adc"] = wide["amp_B4"] + wide["amp_B6"] + wide["amp_B8"]
    amplitudes = wide[[f"amp_{layer}" for layer in LAYERS]].to_numpy(dtype=float)
    passed = amplitudes > float(threshold_adc)
    deepest = np.where(passed, np.arange(len(LAYERS)), -1).max(axis=1)
    wide["stopping_layer"] = np.where(deepest >= 0,
        np.asarray(LAYERS, dtype=object)[np.maximum(deepest, 0)], "none")
    wide["category"] = np.where(wide["E_data_adc"] + wide["deltaE_data_adc"] <= 0,
                                 "all_zero", "ok")
    if len(wide) != n_comp:
        raise RuntimeError("cardinality mismatch")
    distribution = {str(k): int(v) for k, v in wide["stopping_layer"].value_counts().items()}
    return wide, {"stopping_distribution": distribution}
'''

STRICT = VULNERABLE.replace(
    'df[signal_column] = df[ampcol]',
    '''numeric = pd.to_numeric(df[ampcol], errors="coerce")
    if not np.isfinite(numeric.to_numpy(dtype=float, na_value=np.nan)).all():
        raise ValueError("net amplitude requires finite numeric values")
    df[signal_column] = numeric''',
)


def _write(tmp_path: Path, text: str, name: str = "bridge.py") -> Path:
    path = tmp_path / name
    path.write_text(text, encoding="utf-8")
    return path


def test_vulnerable_source_exposes_nan_zero_fill_and_infinity(tmp_path: Path) -> None:
    payload = AUDIT.audit_source(_write(tmp_path, VULNERABLE))
    assert payload["status"] == "FLAWED"
    codes = {item["code"] for item in payload["issues"]}
    assert "NONFINITE_NET_ROW_NOT_REJECTED" in codes
    assert "NONFINITE_NET_ROW_BECAME_ZERO" in codes
    assert "INFINITE_NET_ROW_NOT_REJECTED" in codes
    assert payload["synthetic_controls"]["nan"]["amp_B2"] == ["0.0"]


def test_strict_source_validates(tmp_path: Path) -> None:
    payload = AUDIT.audit_source(_write(tmp_path, STRICT))
    assert payload["status"] == "VALIDATED"
    assert payload["issue_count"] == 0
    assert payload["synthetic_controls"]["finite"]["rejected"] is False
    assert payload["synthetic_controls"]["nan"]["rejected"] is True
    assert payload["synthetic_controls"]["positive_infinity"]["rejected"] is True


def test_cli_returns_one_and_publishes_machine_readable_flaw(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    source = _write(tmp_path, VULNERABLE)
    output = tmp_path / "audit.json"
    assert AUDIT.main(["--source", str(source), "--out", str(output)]) == 1
    assert json.loads(output.read_text(encoding="utf-8"))["status"] == "FLAWED"
    assert json.loads(capsys.readouterr().out)["issue_count"] == 3


def test_invalid_utf8_returns_controlled_error(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    source = tmp_path / "bridge.py"
    source.write_bytes(b"x = 1\n\xff")
    assert AUDIT.main(["--source", str(source)]) == 2
    payload = json.loads(capsys.readouterr().out)
    assert payload["status"] == "ERROR"
    assert "UTF-8" in payload["error"]


def test_output_alias_is_rejected(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    source = _write(tmp_path, STRICT)
    original = source.read_bytes()
    assert AUDIT.main(["--source", str(source), "--out", str(source)]) == 2
    assert source.read_bytes() == original
    assert "alias" in json.loads(capsys.readouterr().out)["error"]
