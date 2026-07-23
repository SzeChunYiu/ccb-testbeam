from pathlib import Path
import importlib.util
import sys

import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = ROOT / "scripts" / "single_stave" / "single_stave_diagnostics.py"
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


def test_calibration_reports_uncertainties_and_model_comparison():
    # Synthetic PE = 10*Edep + 0.5*x + noise across 4 runs / 2 species so that
    # run-held-out, species-aware and position-aware models are all exercisable.
    rng = np.random.default_rng(42)
    n = 240
    edep = rng.uniform(2.0, 40.0, n)
    xpos = rng.uniform(-10.0, 10.0, n)
    pe = 10.0 * edep + 0.5 * xpos + rng.normal(0.0, 1.0, n)
    df = pd.DataFrame(
        {
            "run_id": np.array(["r0", "r1", "r2", "r3"])[np.arange(n) % 4],
            "event_id": np.arange(n),
            "species": np.where(np.arange(n) % 2 == 0, "proton", "deuteron"),
            "kinetic_energy_MeV": 100.0,
            "edep_scint_MeV": edep,
            "edep_scint_raw_MeV": edep * 1.05,
            "n_detected_pe": pe,
            "entry_x_cm": xpos,
            "n_scint_generated": (edep * 10000).astype(int),
            "n_wls_generated": (edep * 500).astype(int),
            "n_cerenkov_generated": 0,
            "n_end_selected": (pe * 3).astype(int),
        }
    )
    _, res = mod.heldout_calibration(df)
    assert res["status"] == "ok"
    assert res["split"] == "run-held-out"  # >=4 runs -> whole runs held out
    u = res["unconstrained"]
    assert np.isfinite(u["slope_se"]) and u["slope_se"] > 0
    assert np.isfinite(u["intercept_se"]) and u["intercept_se"] > 0
    assert abs(u["slope_pe_per_MeV"] - 10.0) < 1.0
    o = res["through_origin"]
    assert np.isfinite(o["slope_se"]) and o["slope_se"] > 0
    assert res["model_comparison"]["line"]
    assert "pooled_linear" in res["model_comparison"]["models"]
    assert len(res["species_aware"]["per_species"]) == 2
    assert res["position_aware"]["edep_slope_pe_per_MeV"] > 0


def test_n_end_bound_uses_total_optical_categories():
    # n_end_selected exceeds scintillation-only but is below the total over all
    # generated optical-track categories -> must pass the defensible bound.
    base = {
        "run_id": ["r", "r"],
        "event_id": [0, 1],
        "species": ["proton", "proton"],
        "kinetic_energy_MeV": [100.0, 100.0],
        "edep_scint_MeV": [10.0, 10.0],
        "n_scint_generated": [100, 100],
        "n_wls_generated": [200, 200],
        "n_cerenkov_generated": [50, 50],
        "n_detected_pe": [10, 10],
    }
    ok = pd.DataFrame(base | {"n_end_selected": [150, 300]})  # both < 350 total
    res_ok = mod.validate_events(ok)
    assert res_ok["passed"]
    assert res_ok["metrics"]["optical_bound_categories"] == [
        "n_scint_generated",
        "n_wls_generated",
        "n_cerenkov_generated",
    ]

    bad = pd.DataFrame(base | {"n_end_selected": [150, 400]})  # 400 > 350 total
    res_bad = mod.validate_events(bad)
    assert not res_bad["passed"]
    assert any("total generated optical" in f for f in res_bad["failures"])

    # Only scintillation recorded -> an excess is not a hard failure (WLS/
    # Cerenkov unrecorded), it is a warning.
    scint_only = pd.DataFrame(
        {
            "run_id": ["r"],
            "event_id": [0],
            "species": ["proton"],
            "kinetic_energy_MeV": [100.0],
            "edep_scint_MeV": [10.0],
            "n_scint_generated": [100],
            "n_end_selected": [150],
            "n_detected_pe": [10],
        }
    )
    res_partial = mod.validate_events(scint_only)
    assert res_partial["passed"]
    assert any("bound is partial" in w for w in res_partial["warnings"])
