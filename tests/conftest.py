"""Pytest path setup and shared fixtures for ccb_mc_validation."""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pytest

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

FIXTURES = Path(__file__).parent / "fixtures"


def _write_truth_mini_npz(path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    layer = np.array(
        [np.array([0, 0], dtype=np.int32), np.array([0], dtype=np.int32)],
        dtype=object,
    )
    layer1 = np.array(
        [np.array([1, 2], dtype=np.int32), np.array([1], dtype=np.int32)],
        dtype=object,
    )
    pdg = np.array(
        [np.array([2212, 2212], dtype=np.int32), np.array([2212], dtype=np.int32)],
        dtype=object,
    )
    time = np.array(
        [np.array([0.0, 5.0], dtype=np.float64), np.array([10.0], dtype=np.float64)],
        dtype=object,
    )
    np.savez(
        path,
        Sci_bar_LayerID=layer,
        Sci_bar_LayerID1=layer1,
        Sci_bar_PDG=pdg,
        Sci_bar_Time=time,
        coinc_ns=np.array(15.0),
        expected_sample_I=np.array([True, False]),
        expected_sample_II=np.array([True, True]),
    )
    return path


@pytest.fixture(scope="session")
def truth_mini_npz() -> Path:
    path = FIXTURES / "truth_mini.npz"
    # Always refresh this tiny deterministic fixture so stale local/CI artifacts
    # cannot change the expected trigger classification population.
    _write_truth_mini_npz(path)
    return path

