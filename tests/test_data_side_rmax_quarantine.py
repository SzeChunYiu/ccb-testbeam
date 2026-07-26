from __future__ import annotations

import importlib.util
import math
import sys
import types
from pathlib import Path

import pandas as pd


SCRIPT = Path(__file__).parents[1] / "scripts/studies/data_side_real_beam.py"


def load_module():
    sys.modules.setdefault("uproot", types.SimpleNamespace())
    spec = importlib.util.spec_from_file_location("data_side_real_beam", SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_rmax_is_blocked_and_reports_only_model_sensitivity(tmp_path):
    module = load_module()
    module.OUT = tmp_path
    selected = pd.DataFrame(
        {
            "run": [31, 31, 31, 32, 32],
            "eventno": [1, 1, 2, 1, 1],
        }
    )

    result = module.rmax(selected)

    assert result["rmax_authorized"] is False
    assert result["rmax_status"] == "BLOCKED"
    assert result["accepted_rmax_mhz"] is None
    assert result["blocked_by"] == "S-STAT-003"
    assert result["measured_occupancy_role"] == (
        "DESCRIPTIVE_SELECTED_PULSE_MULTIPLICITY_ONLY"
    )
    expected = 0.38 / (124.79018394263471e-9) / 1e6
    assert math.isclose(
        result["model_sensitivity_only_mhz"], expected, rel_tol=0, abs_tol=1e-15
    )
    assert (tmp_path / "VIS-PU-DATA_occupancy_rmax.png").is_file()


def test_producer_contains_no_data_derived_rmax_authorization():
    text = SCRIPT.read_text(encoding="utf-8")
    prohibited = (
        "Rmax from real occupancy",
        "tau_eff_ns = ACQ_WINDOW_NS - 30.0",
        "Rmax_data_derived_Hz",
        "Rmax(data-derived)",
        "Rmax_derived=",
    )
    assert all(phrase not in text for phrase in prohibited)
