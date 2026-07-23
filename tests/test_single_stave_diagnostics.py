from pathlib import Path
import importlib.util
import sys

import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = ROOT / "scripts" / "single_stave_diagnostics.py"
spec = importlib.util.spec_from_file_location("single_stave_diagnostics", MODULE_PATH)
mod = importlib.util.module_from_spec(spec)
assert spec and spec.loader
sys.modules[spec.name] = mod
spec.loader.exec_module(mod)


def test_current_geant4_schema_normalization():
    df = pd.DataFrame(
        {
            "event": [0, 1],
            "particle": ["proton", "deuteron"],
            "ke_MeV": [100.0, 70.0],
            "edep_scint_MeV": [16.0, 50.0],
            "edep_scint_raw_MeV": [17.0, 54.0],
            "n_scint_generated": [160000, 500000],
            "n_wls_generated": [10000, 30000],
            "n_cerenkov_generated": [0, 0],
            "arrival_readout": [580, 1430],
            "detected_readout": [176, 432],
            "_run_file": ["a", "a"],
        }
    )
    out = mod.normalize_events(df)
    assert list(out["event_id"]) == [0, 1]
    assert list(out["n_end_selected"]) == [580, 1430]
    assert list(out["n_detected_pe"]) == [176, 432]
    assert list(out["particle_pdg"]) == [2212, 1000010020]


def test_validation_rejects_detected_greater_than_arrived():
    df = pd.DataFrame(
        {
            "run_id": ["r"],
            "event_id": [0],
            "species": ["proton"],
            "kinetic_energy_MeV": [100.0],
            "edep_scint_MeV": [10.0],
            "n_scint_generated": [100],
            "n_wls_generated": [0],
            "n_cerenkov_generated": [0],
            "n_end_selected": [5],
            "n_detected_pe": [6],
        }
    )
    result = mod.validate_events(df)
    assert not result["passed"]
    assert any("exceeds" in x for x in result["failures"])


def test_raw_visible_equality_is_warning_not_fake_quenching():
    df = pd.DataFrame(
        {
            "run_id": ["r"] * 3,
            "event_id": [0, 1, 2],
            "species": ["proton"] * 3,
            "kinetic_energy_MeV": [100.0] * 3,
            "edep_scint_MeV": [10.0, 11.0, 12.0],
            "edep_scint_raw_MeV": [10.0, 11.0, 12.0],
            "n_scint_generated": [100, 110, 120],
            "n_wls_generated": [0, 0, 0],
            "n_cerenkov_generated": [0, 0, 0],
            "n_end_selected": [10, 11, 12],
            "n_detected_pe": [3, 3, 4],
        }
    )
    result = mod.validate_events(df)
    assert result["passed"]
    assert any("exactly equal" in x for x in result["warnings"])
