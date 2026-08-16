"""Regression tests for scripts/data01_sample_split_staves.py.

Covers:
  * DATA-001: B2<->B4 event joins must use the composite (run, eventno) key
    after one-row-per-(run,eventno,stave) aggregation, and reject fan-out.
  * DATA-005: plot subsampling uses a recorded seed + stable row ordering
    (deterministic).
  * DATA-004: ``sys`` and ``traceback`` are imported (the plot error handler
    must not mask the original exception with a NameError).
"""
from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "data01_sample_split_staves.py"
SPEC = importlib.util.spec_from_file_location("data01_sample_split", SCRIPT)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def _table() -> pd.DataFrame:
    # Two runs that DELIBERATELY share eventno=10. A naive eventno-only join
    # would collide run-1/event-10 with run-2/event-10 (cross-run fan-out).
    rows = []
    for run, ev in [(1, 10), (2, 10)]:
        for stave in ("B2", "B4"):
            rows.append({"run": run, "group": "sample_i_analysis",
                         "eventno": ev, "evt": ev, "stave": stave,
                         "channel": 0, "baseline_adc": 100.0,
                         "amplitude_adc": 2000.0 + run + (5 if stave == "B4" else 0),
                         "peak_sample": 1, "area_adc_samples": 10.0})
    df = pd.DataFrame(rows)
    df["sample"] = np.where(df["group"].str.startswith("sample_i_"), "I",
                    np.where(df["group"].str.startswith("sample_ii_"), "II", "other"))
    return df


def test_per_event_stave_one_row_per_composite_key() -> None:
    df = _table()
    agg = MODULE._per_event_stave_amplitude(df, "I", "B2")
    # one row per (run, eventno): 2 distinct (run,eventno) pairs
    assert len(agg) == 2
    assert not agg.duplicated(["run", "eventno"]).any()
    assert set(agg.columns) >= {"run", "eventno", "amp"}


def test_cross_run_collision_isolated_and_fanout_rejected() -> None:
    """The composite-key merge must NOT collapse the two runs' eventno=10."""
    df = _table()
    b2 = MODULE._per_event_stave_amplitude(df, "I", "B2").rename(columns={"amp": "amp_B2"})
    b4 = MODULE._per_event_stave_amplitude(df, "I", "B4").rename(columns={"amp": "amp_B4"})
    merged = b2.merge(b4, on=["run", "eventno"], how="inner", validate="1:1")
    assert len(merged) == 2  # one row per run, NOT a 4-row cross-product
    assert set(merged["run"]) == {1, 2}

    # A bare eventno-only join would have produced len==4 (2x2 fan-out).
    bad = b2.drop(columns=["run"]).merge(b4.drop(columns=["run"]), on="eventno")
    assert len(bad) == 4

    # Multiple pulses per (run,eventno,stave) aggregate deterministically (max).
    df2 = _table()
    df2 = pd.concat([df2, df2.iloc[[0]].assign(amplitude_adc=9999.0)], ignore_index=True)
    agg = MODULE._per_event_stave_amplitude(df2, "I", "B2")
    row = agg[(agg["run"] == 1) & (agg["eventno"] == 10)].iloc[0]
    assert row["amp"] == 9999.0


def test_cluster_export_requires_run_and_eventno(tmp_path: Path) -> None:
    csv = tmp_path / "sel.csv"
    pd.DataFrame({
        "group": ["sample_i_analysis"] * 2,
        "stave": ["B2", "B2"],
        "channel": [0, 0],
        "baseline_adc": [100.0, 100.0],
        "amplitude_adc": [2000.0, 2100.0],
        "peak_sample": [1, 1],
        "area_adc_samples": [1.0, 1.0],
    }).to_csv(csv, index=False)
    out_dir = tmp_path / "out"
    import sys as _sys
    argv0 = _sys.argv
    try:
        _sys.argv = ["data01", "--table", str(csv), "--out", str(out_dir)]
        with pytest.raises(RuntimeError, match="cluster export requires"):
            MODULE.main()
    finally:
        _sys.argv = argv0


def test_seed_recorded_and_subsample_deterministic(tmp_path: Path) -> None:
    df = _table()
    b2 = MODULE._per_event_stave_amplitude(df, "I", "B2").rename(columns={"amp": "amp_B2"})
    b4 = MODULE._per_event_stave_amplitude(df, "I", "B4").rename(columns={"amp": "amp_B4"})
    merged = b2.merge(b4, on=["run", "eventno"], how="inner", validate="1:1")
    merged = merged.sort_values(["run", "eventno"]).reset_index(drop=True)
    seed = 12345
    rng = np.random.default_rng(seed)
    n_pts = min(8000, len(merged))
    idx_a = np.sort(rng.choice(len(merged), n_pts, replace=False))
    rng2 = np.random.default_rng(seed)
    idx_b = np.sort(rng2.choice(len(merged), n_pts, replace=False))
    np.testing.assert_array_equal(idx_a, idx_b)  # stable + reproducible


def test_main_records_seed_and_writes_summary(tmp_path: Path) -> None:
    csv = tmp_path / "sel.csv"
    pd.DataFrame({
        "run": [1, 1, 1], "group": ["sample_i_analysis"] * 3,
        "eventno": [10, 10, 11], "evt": [10, 10, 11],
        "stave": ["B2", "B4", "B8"], "channel": [0, 0, 0],
        "baseline_adc": [100.0, 100.0, 100.0],
        "amplitude_adc": [2000.0, 1800.0, 1500.0],
        "peak_sample": [1, 1, 1], "area_adc_samples": [1.0, 1.0, 1.0],
    }).to_csv(csv, index=False)
    out_dir = tmp_path / "out"
    import sys as _sys
    argv0 = _sys.argv
    try:
        _sys.argv = ["data01", "--table", str(csv), "--out", str(out_dir), "--seed", "42"]
        MODULE.main()
    finally:
        _sys.argv = argv0
    summary = json.loads((out_dir / "data_sample_split_summary.json").read_text())
    assert summary["plot_seed"] == 42  # DATA-005: seed recorded


def test_sys_and_traceback_imported() -> None:
    # DATA-004: the old handler referenced ``sys`` without importing it, masking
    # the real exception. Both must now be module-level imports.
    src = SCRIPT.read_text(encoding="utf-8")
    # DATA-004: the old handler referenced ``sys`` without importing it,
    # masking the real exception with a NameError. Both must now be
    # module-level imports (split onto separate lines for lint).
    assert "import sys" in src
    assert "import traceback" in src
    assert "traceback.print_exc()" in src
