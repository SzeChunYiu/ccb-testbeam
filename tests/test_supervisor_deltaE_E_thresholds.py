"""Tests for supervisor_deltaE_E.py threshold handling (#1038, #1039).

Verifies:
- deepest_edep_layer() implements the requested D(T) = max{k : E_k > T}
  family with an explicit NO_LAYER_PASSES sentinel.
- A tiny downstream deposit cannot move the inferred depth beyond its
  threshold, and monotonic reach fractions decrease as threshold rises.
- The DATA per-threshold reach uses args.data_thresholds (not a hard-coded
  1000 ADC cut).
"""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import numpy as np
import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPT_PATH = REPO_ROOT / "scripts" / "supervisor_deltaE_E.py"


def _load():
    spec = importlib.util.spec_from_file_location("supervisor_deltaE_E", SCRIPT_PATH)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


pytestmark = pytest.mark.skipif(not SCRIPT_PATH.exists(), reason=f"{SCRIPT_PATH} not found")


@pytest.fixture(scope="module")
def m():
    return _load()


# ---------------------------------------------------------------------------
# deepest_edep_layer()
# ---------------------------------------------------------------------------


class TestDeepestEdepLayer:
    def test_deepest_layer_above_threshold(self, m):
        # 10 MeV in B2 (layer 0), 1 eV in B8 (layer 7). D(0.02) must be 0, not 7.
        el = {0: 10.0, 7: 0.001}
        assert m.deepest_edep_layer(el, 0.02) == 0

    def test_tiny_deepest_deposit_below_threshold(self, m):
        # deposit at layer 5 = 0.01, below 0.02 threshold -> layer 5 not reached
        el = {0: 5.0, 5: 0.01}
        assert m.deepest_edep_layer(el, 0.02) == 0

    def test_exactly_threshold_strict_greater(self, m):
        # strict=True uses '>', so a deposit exactly equal to threshold does not
        # pass the layer.
        el = {3: 0.02}
        assert m.deepest_edep_layer(el, 0.02, strict=True) == -1
        assert m.deepest_edep_layer(el, 0.02, strict=False) == 3

    def test_no_layer_passes_sentinel(self, m):
        el = {0: 0.001, 2: 0.005}
        assert m.deepest_edep_layer(el, 0.02) == -1

    def test_empty_deposits(self, m):
        assert m.deepest_edep_layer({}, 0.02) == -1

    def test_deeper_layer_wins(self, m):
        el = {0: 1.0, 3: 0.5, 6: 2.0}
        assert m.deepest_edep_layer(el, 0.02) == 6

    def test_secondary_only_downstream_deposit(self, m):
        # deposit only in a downstream layer from a secondary; the primary leaves
        # nothing above threshold in B2.
        el = {0: 0.0, 4: 3.0}
        assert m.deepest_edep_layer(el, 0.02) == 4


# ---------------------------------------------------------------------------
# Monotonic reach vs threshold (discriminating test from #1039)
# ---------------------------------------------------------------------------


class TestMonotonicReach:
    def test_reach_fraction_decreases_with_threshold(self, m):
        # Synthetic layer-deposit maps. As threshold rises, deep reach must fall.
        maps = [
            {0: 3.0, 1: 0.5, 2: 0.1},
            {0: 2.0, 1: 0.03, 2: 0.0},
            {0: 1.0, 1: 0.01, 2: 0.0},
            {0: 0.5, 1: 0.0, 2: 0.0},
        ]
        reaches = []
        for th in (0.0, 0.02, 0.05, 0.1, 0.5):
            deep = np.array([m.deepest_edep_layer(el, th) for el in maps])
            reach_b6 = float((deep >= 2).mean())
            reaches.append(reach_b6)
        # Non-increasing as threshold rises.
        assert all(a >= b for a, b in zip(reaches, reaches[1:])), reaches


# ---------------------------------------------------------------------------
# DATA per-threshold reach uses args.data_thresholds (not hard-coded 1000)
# ---------------------------------------------------------------------------


def test_data_thresholds_used_in_source(m):
    """The DATA reach computation must reference args.data_thresholds, not a
    hard-coded 1000 constant."""
    src = SCRIPT_PATH.read_text(encoding="utf-8")
    assert "args.data_thresholds" in src, (
        "DATA reach must loop over args.data_thresholds (#1038)"
    )
    # The old hard-coded 1000 cut must be gone from the reach computation.
    assert ">1000" not in src, (
        "hard-coded 1000 ADC cut must be removed from DATA reach (#1038)"
    )


def test_stop_thresholds_used_in_source(m):
    """The MC stop-layer computation must use args.stop_thresholds."""
    src = SCRIPT_PATH.read_text(encoding="utf-8")
    assert "args.stop_thresholds" in src, (
        "MC stop_layer must loop over args.stop_thresholds (#1039)"
    )
    assert "deepest_edep_layer" in src, (
        "MC stop_layer must call deepest_edep_layer (#1039)"
    )