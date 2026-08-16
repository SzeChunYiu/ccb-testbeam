from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import numpy as np
import pytest

SCRIPT = Path(__file__).resolve().parents[1] / "tools" / "audit" / "mc01_measure_closure.py"
spec = importlib.util.spec_from_file_location("mc01_measure_closure", SCRIPT)
assert spec and spec.loader
mod = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = mod
spec.loader.exec_module(mod)


def test_equal_weights_make_weighted_and_unweighted_identical():
    summary = mod.layer_summary_from_counts(
        edep=[10.0, 20.0, 30.0],
        edep_w=[1.0, 1.0, 1.0],
        pid_counts={"p": 2, "d": 1},
        pid_w={"p": 2.0, "d": 1.0},
        wsum=3.0,
        large_mev=15.0,
        apply_weight=True,
    )
    assert summary["measure"] == mod.MEASURE_PRIMARY_WEIGHT
    assert summary["mean_edep_MeV"] == pytest.approx(20.0)
    assert summary["frac_large"] == pytest.approx(2.0 / 3.0)
    assert summary["pid_fraction"]["d"] == pytest.approx(1.0 / 3.0, abs=1e-4)
    assert summary["unweighted_diagnostic"]["mean_edep_MeV"] == pytest.approx(20.0)


def test_unequal_weights_change_authorising_not_unweighted_diagnostic():
    summary = mod.layer_summary_from_counts(
        edep=[10.0, 20.0],
        edep_w=[1.0, 9.0],
        pid_counts={"p": 1, "d": 1},
        pid_w={"p": 1.0, "d": 9.0},
        wsum=10.0,
        large_mev=15.0,
        apply_weight=True,
    )
    assert summary["mean_edep_MeV"] == pytest.approx(19.0)
    assert summary["pid_fraction"]["d"] == pytest.approx(0.9, abs=1e-4)
    assert summary["unweighted_diagnostic"]["mean_edep_MeV"] == pytest.approx(15.0)
    assert summary["unweighted_diagnostic"]["pid_fraction"]["d"] == pytest.approx(0.5, abs=1e-4)
    assert summary["weight_diagnostics"]["ess"] == pytest.approx(100.0 / 82.0)


def test_no_weight_mode_is_explicitly_diagnostic():
    summary = mod.layer_summary_from_counts(
        edep=[10.0, 20.0],
        edep_w=[1.0, 9.0],
        pid_counts={"p": 1, "d": 1},
        pid_w={"p": 1.0, "d": 9.0},
        wsum=10.0,
        large_mev=15.0,
        apply_weight=False,
    )
    assert summary["measure"] == mod.MEASURE_UNWEIGHTED
    assert summary["mean_edep_MeV"] == pytest.approx(15.0)
    headline = mod.build_headline_first_b_layer(summary, summary, apply_weight=False)
    assert headline["measure_status"] == mod.MEASURE_STATUS_DIAGNOSTIC
    assert "unweighted_diagnostic" not in headline


def test_headline_leads_with_weighted_measure_when_enabled():
    weighted = mod.layer_summary_from_counts(
        edep=[10.0, 20.0],
        edep_w=[1.0, 9.0],
        pid_counts={"p": 1, "d": 1},
        pid_w={"p": 1.0, "d": 9.0},
        wsum=10.0,
        large_mev=15.0,
        apply_weight=True,
    )
    headline = mod.build_headline_first_b_layer(weighted, weighted, apply_weight=True)
    assert headline["measure"] == mod.MEASURE_PRIMARY_WEIGHT
    assert headline["measure_status"] == mod.MEASURE_STATUS_AUTHORISING
    assert headline["sampleI_d_fraction"] == pytest.approx(0.9, abs=1e-4)
    assert headline["unweighted_diagnostic"]["sampleI_d_fraction"] == pytest.approx(0.5, abs=1e-4)


def test_scatter_subsample_is_deterministic_and_weight_aware():
    w = np.array([1.0, 1.0, 100.0, 1.0, 1.0])
    idx_a = mod.choose_scatter_indices(5, 3, w, seed=7)
    idx_b = mod.choose_scatter_indices(5, 3, w, seed=7)
    assert np.array_equal(idx_a, idx_b)
    assert 2 in idx_a  # dominant weight row is retained under weight-aware draw
