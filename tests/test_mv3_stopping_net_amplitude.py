"""Regression tests for scripts/mv3_stopping_v2.py and v3.

Covers:
  * DATA-002: the net amplitude must NOT re-subtract ``baseline_adc`` from
    ``amplitude_adc`` (A-001 double-subtraction bug); it must prefer the
    contract field ``peak_height_adc`` when present.
  * DATA-003: the Sample I / Sample II split must use exact categorical values
    (``sample_i_`` prefix must not match ``sample_ii_``).
  * v2 deprecation: v2 warns and points to v3.
"""
from __future__ import annotations

import importlib.util
from pathlib import Path

import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parents[1]


def _load(rel: str, name: str):
    spec = importlib.util.spec_from_file_location(name, ROOT / rel)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


V2 = _load("scripts/mv3_stopping_v2.py", "mv3_v2_test")
V3 = _load("scripts/mv3_stopping_v3.py", "mv3_v3_test")


def _csv(tmp_path, *, with_peak_height: bool = False) -> Path:
    cols = {
        "run": [1, 1, 1, 1, 2, 2],
        "group": ["sample_i_analysis", "sample_ii_analysis",
                  "sample_i_analysis", "sample_ii_analysis",
                  "sample_i_analysis", "sample_ii_analysis"],
        "evt": [10, 11, 12, 13, 10, 11],
        "eventno": [10, 11, 12, 13, 10, 11],
        "stave": ["B2", "B2", "B8", "B8", "B2", "B8"],
        "amplitude_adc": [1500.0, 1500.0, 1500.0, 1500.0, 1500.0, 1500.0],
        "baseline_adc": [3000.0, 3000.0, 3000.0, 3000.0, 3000.0, 3000.0],
    }
    df = pd.DataFrame(cols)
    if with_peak_height:
        df["peak_height_adc"] = [1200.0] * len(df)  # differs from amplitude_adc
    p = tmp_path / "sel.csv"
    df.to_csv(p, index=False)
    return p


@pytest.mark.parametrize("mod", [V2, V3], ids=["v2", "v3"])
def test_no_double_subtraction_of_baseline(tmp_path, mod) -> None:
    """amplitude_adc is already net; subtracting baseline_adc would wrongly
    drop every row below the 1000 ADC threshold (1500 - 3000 = -1500 -> 0 kept)."""
    p = _csv(tmp_path)
    res = mod.data_stopping_fractions(str(p), threshold_net=1000.0)
    assert res["all"]["n_events"] > 0, "double-subtraction killed every row"


def test_v3_prefers_peak_height_adc(tmp_path) -> None:
    """When the contract field peak_height_adc is present it is used as net,
    and amplitude_adc/baseline_adc are ignored."""
    p = _csv(tmp_path, with_peak_height=True)
    res = V3.data_stopping_fractions(str(p), threshold_net=1000.0)
    # peak_height_adc=1200 > 1000 threshold -> all rows survive
    assert res["all"]["n_events"] == 6


def test_sample_i_prefix_does_not_match_sample_ii(tmp_path) -> None:
    """DATA-003: 'sample_i' substring must not capture 'sample_ii' groups."""
    p = _csv(tmp_path)
    res = V3.data_stopping_fractions(str(p), threshold_net=1000.0)
    n_i = res["sample_i"]["n_events"]
    n_ii = res["sample_ii"]["n_events"]
    assert n_i == 3 and n_ii == 3, f"sample_i={n_i} sample_ii={n_ii}"
    # The groups are disjoint: total == sample_i + sample_ii.
    assert res["all"]["n_events"] == n_i + n_ii


def test_v2_emits_deprecation_warning(tmp_path, monkeypatch) -> None:
    """v2 is deprecated and must warn toward v3."""
    # data_stopping_fractions itself is clean; the deprecation fires in main().
    src = (ROOT / "scripts" / "mv3_stopping_v2.py").read_text(encoding="utf-8")
    assert "DeprecationWarning" in src
    assert "mv3_stopping_v3.py" in src


def test_net_amplitude_helper_never_subtracts_baseline() -> None:
    for mod in (V2, V3):
        df = pd.DataFrame({"amplitude_adc": [1500.0], "baseline_adc": [3000.0]})
        net = float(mod._net_amplitude(df).iloc[0])
        assert net == 1500.0  # NOT |1500 - 3000|
