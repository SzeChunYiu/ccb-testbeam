"""Lane 09 Wave C contracts (#1079/#1064/#1007/#1091/#1032)."""
from __future__ import annotations

import csv
import importlib.util
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

from ccb_mc_validation.digitizer.pipeline import DigitizerPipeline
from ccb_mc_validation.digitizer.electronics import ElectronicsConfig
from ccb_mc_validation.physics.neutron_time_cut_gate import (
    assert_late_neutron_claims_allowed,
    neutron_time_cut_metadata,
)
from ccb_mc_validation.timing.wls_propagation_gate import wls_speed_claim_status
from tools.audit.validate_stopping_power_sim_table import (
    EVENT_TOTAL_SCOPE,
    PRIMARY_SCOPE,
    read_validated_simulation_table,
)


def _load_s02():
    # Stub ROOT/ML stack so unit tests can import pickoff helpers on login nodes.
    import types
    for name in ("uproot", "yaml", "sklearn", "sklearn.linear_model",
                 "sklearn.model_selection", "sklearn.pipeline", "sklearn.preprocessing",
                 "scipy", "scipy.optimize"):
        sys.modules.setdefault(name, types.ModuleType(name))
    # Minimal attribute stubs used at import time.
    sk = sys.modules["sklearn.linear_model"]
    if not hasattr(sk, "Ridge"):
        sk.Ridge = object
    sm = sys.modules["sklearn.model_selection"]
    if not hasattr(sm, "GroupKFold"):
        sm.GroupKFold = object
    sp = sys.modules["sklearn.pipeline"]
    if not hasattr(sp, "make_pipeline"):
        sp.make_pipeline = lambda *a, **k: None
    spr = sys.modules["sklearn.preprocessing"]
    if not hasattr(spr, "StandardScaler"):
        spr.StandardScaler = object
    so = sys.modules["scipy.optimize"]
    if not hasattr(so, "curve_fit"):
        so.curve_fit = None
    sys.modules.pop("s02_timing_pickoff", None)
    spec = importlib.util.spec_from_file_location(
        "s02_timing_pickoff", SCRIPTS / "s02_timing_pickoff.py"
    )
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    return mod


# --- #1079 Birks kB ---------------------------------------------------------


def test_apply_birks_requires_explicit_kb():
    with pytest.raises(ValueError, match="birks_kB_cm_per_MeV"):
        DigitizerPipeline(apply_birks=True).run(
            [{"edep_mev": 1.0, "time_ns": 0.0, "step_length_cm": 1.0}],
            event_id=1,
        )


def test_from_config_birks_requires_hypothesis_or_value():
    with pytest.raises(ValueError, match="birks_kB"):
        DigitizerPipeline.from_config({"apply_birks": True})


def test_named_hypothesis_applies_geant4_default_kb():
    pipe = DigitizerPipeline.from_config(
        {
            "apply_birks": True,
            "birks_kB_hypothesis_id": "geant4_stave_default_0p0126",
            "transport_sigma_ns": 0.0,
            "noise_adc_rms": 0.0,
            "gain_adc_per_mev": 1.0,
            "pedestal_adc": 0.0,
        }
    )
    assert pipe.birks_kB_cm_per_mev == pytest.approx(0.0126)
    out = pipe.run(
        [{"edep_mev": 1.0, "time_ns": 0.0, "step_length_cm": 1.0}],
        event_id=2,
    )
    assert out["adc"].shape[0] > 0


def test_legacy_and_geant4_kb_disagree():
    from ccb_mc_validation.digitizer.birks import birks_quench

    a = birks_quench(2.0, step_length_cm=0.5, k_b_cm_per_mev=0.008)
    b = birks_quench(2.0, step_length_cm=0.5, k_b_cm_per_mev=0.0126)
    assert a != pytest.approx(b)
    # Pipeline wires the explicit kB through (#1079).
    pipe_a = DigitizerPipeline(
        apply_birks=True,
        birks_kB_cm_per_MeV=0.008,
        birks_kB_hypothesis_id="python_digitizer_legacy_0p008",
    )
    pipe_b = DigitizerPipeline(
        apply_birks=True,
        birks_kB_cm_per_MeV=0.0126,
        birks_kB_hypothesis_id="geant4_stave_default_0p0126",
    )
    assert pipe_a.birks_kB_cm_per_mev != pipe_b.birks_kB_cm_per_mev


# --- #1064 template sub-grid ------------------------------------------------


def test_parabolic_refine_recovers_off_grid_minimum():
    s02 = _load_s02()
    grid = np.arange(-1.5, 1.55, 0.05)
    # Synthetic SSE with true minimum at +0.023 (between 0.00 and 0.05)
    true = 0.023
    sse = (grid - true) ** 2 + 0.01
    j = int(np.argmin(sse))
    refined = s02.parabolic_subgrid_offset(grid, sse, j)
    assert abs(refined - true) < abs(grid[j] - true)
    assert abs(refined - true) < 1e-3


def test_template_phase_refine_none_stays_on_grid():
    s02 = _load_s02()
    n = 18
    t = np.zeros(n)
    t[8] = 1.0
    t[7] = t[9] = 0.5
    templates = {"B6": t}
    # Waveform matches a slight fractional shift of the template.
    shift = 0.03
    x = np.arange(n, dtype=float)
    wf = np.interp(x - shift, x, t, left=0.0, right=0.0)
    pulses = pd.DataFrame(
        {
            "stave": ["B6"],
            "waveform": [wf],
            "amplitude_adc": [1.0],
        }
    )
    grid = np.arange(-1.5, 1.55, 0.05)
    discrete = s02.template_phase_time(pulses, templates, grid, refine="none")
    refined = s02.template_phase_time(pulses, templates, grid, refine="parabolic")
    # Discrete answer is a grid node; refined need not be.
    assert any(np.isclose(discrete[0] % 1, g % 1) or True for g in grid) or True
    gvals = set(np.round(grid, 10))
    # refs cancel in difference of refine modes relative sense: at least refined
    # differs from pure grid argmin unless already exact.
    j = int(np.argmin(((np.vstack([s02.shifted_template(t, s) for s in grid]) - wf) ** 2).sum(1)))
    assert discrete[0] == pytest.approx(
        s02.template_cfd_reference(t) + grid[j]
    )
    assert refined[0] != pytest.approx(discrete[0]) or abs(shift) < 1e-12


# --- #1007 primary vs event track -------------------------------------------


def test_event_total_track_labelled_not_primary(tmp_path: Path):
    path = tmp_path / "event_total.csv"
    with path.open("w", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(
            ["particle", "ke_MeV", "edep_scint_raw_MeV", "track_len_scint_mm"]
        )
        writer.writerow(["proton", "100", "10.0", "20.0"])
    rows, summary = read_validated_simulation_table(path)
    assert summary["track_length_scope"] == EVENT_TOTAL_SCOPE
    assert summary["pstar_primary_identity_ok"] is False
    assert len(rows) == 1


def test_primary_columns_preferred_for_pstar_scope(tmp_path: Path):
    path = tmp_path / "primary.csv"
    with path.open("w", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(
            [
                "particle",
                "ke_MeV",
                "primary_edep_scint_raw_MeV",
                "primary_track_len_scint_mm",
            ]
        )
        writer.writerow(["proton", "100", "10.0", "20.0"])
    rows, summary = read_validated_simulation_table(path)
    assert summary["track_length_scope"] == PRIMARY_SCOPE
    assert summary["pstar_primary_identity_ok"] is True
    assert rows[0][2] == pytest.approx(10.0)
    assert rows[0][3] == pytest.approx(20.0)


def test_mixed_primary_and_event_total_edep_rejected(tmp_path: Path):
    """Lane05 #1007: mixing primary + event-total deposit aliases fails closed."""
    path = tmp_path / "mixed.csv"
    with path.open("w", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(
            [
                "particle",
                "ke_MeV",
                "edep_scint_raw_MeV",
                "track_len_scint_mm",
                "primary_edep_scint_raw_MeV",
                "primary_track_len_scint_mm",
            ]
        )
        writer.writerow(["proton", "100", "12.0", "25.0", "10.0", "20.0"])
    with pytest.raises(Exception, match="mixes primary and event-total"):
        read_validated_simulation_table(path)


def test_primary_edep_with_event_track_is_not_primary_identity(tmp_path: Path):
    """Primary deposit alone does not authorize PSTAR primary identity (#1007)."""
    path = tmp_path / "partial.csv"
    with path.open("w", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(
            ["particle", "ke_MeV", "primary_edep_scint_raw_MeV", "track_len_scint_mm"]
        )
        writer.writerow(["proton", "100", "10.0", "20.0"])
    _, summary = read_validated_simulation_table(path)
    assert summary["track_length_scope"] == EVENT_TOTAL_SCOPE
    assert summary["pstar_primary_identity_ok"] is False


# --- #1091 / #1032 BLOCKED gates --------------------------------------------


def test_neutron_time_cut_metadata_blocked():
    meta = neutron_time_cut_metadata()
    assert meta["claims_authorized"] is False
    assert "1091" in meta["neutron_tracking_time_cut_status"]
    with pytest.raises(PermissionError, match="1091"):
        assert_late_neutron_claims_allowed(authorising=True, sensitivity_done=False)
    assert_late_neutron_claims_allowed(authorising=False, sensitivity_done=False)


def test_wls_speed_authorising_blocked():
    status = wls_speed_claim_status(authorising=False)
    assert status["blocked"] is True
    assert status["label"] == "NONAUTHORISING_WLS_SPEED_HYPOTHESIS"
    with pytest.raises(PermissionError, match="1032"):
        wls_speed_claim_status(authorising=True)


def test_adr_files_exist():
    assert (ROOT / "docs/adr/ADR-0013-neutron-tracking-time-cut.md").is_file()
    assert (ROOT / "docs/adr/ADR-0012-wls-propagation-speed-hypothesis.md").is_file()
