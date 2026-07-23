from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

SCRIPT = Path(__file__).parents[1] / "scripts" / "single_stave" / "refit_i885_campaign.py"
SPEC = importlib.util.spec_from_file_location("refit_i885_campaign", SCRIPT)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(MODULE)


def make_rows() -> pd.DataFrame:
    rows = []
    for particle, energies in {"proton": [2, 5, 8, 12, 20], "deuteron": [2, 5]}.items():
        for energy in energies:
            for seed, offset in [(101, -0.2), (102, 0.2)]:
                rows.append(
                    {
                        "particle": particle,
                        "energy_MeV": energy,
                        "hit_x_cm": 0.0,
                        "seed": seed,
                        "n_events": 500,
                        "pe_sat_readout_mean": 4.0 * energy + offset,
                        "pe_sat_readout_sem": 0.1,
                        "edep_scint_MeV_mean": 0.5 * energy + offset / 10.0,
                        "edep_scint_MeV_sem": 0.01,
                    }
                )
    return pd.DataFrame(rows)


def test_seed_averaged_fit_counts_independent_energies() -> None:
    result, points = MODULE.analyze(make_rows())
    proton = result["fits"]["pe_sat_readout_vs_KE_proton"]
    assert proton["fit_basis"] == MODULE.FIT_BASIS
    assert proton["n"] == proton["n_energy_points"] == 5
    assert proton["n_files"] == 10
    assert proton["residual_dof"] == 3
    assert proton["slope"] == pytest.approx(4.0)
    assert set(points[points.particle == "proton"].n_files) == {2}


def test_two_energy_species_is_skipped_not_fitted() -> None:
    result, _ = MODULE.analyze(make_rows())
    assert "pe_sat_readout_vs_KE_deuteron" not in result["fits"]
    skip = result["fit_skips"]["pe_sat_readout_vs_KE_deuteron"]
    assert skip["status"] == "SKIPPED_INSUFFICIENT_ENERGY_POINTS"
    assert skip["n_energy_points"] == 2
    assert result["status"] == "PARTIAL"


def test_fit_uses_energy_means_not_seed_row_weighting() -> None:
    frame = make_rows()
    extra = frame[(frame.particle == "proton") & (frame.energy_MeV == 2)].copy()
    extra["seed"] = [103, 104]
    extra["pe_sat_readout_mean"] = [0.0, 0.0]
    frame = pd.concat([frame, extra], ignore_index=True)
    result, points = MODULE.analyze(frame)
    fit = (
        result["fits"].get("pe_sat_readout_vs_KE_proton")
        or result["fit_rejections"]["pe_sat_readout_vs_KE_proton"]
    )
    averaged = points[
        (points.particle == "proton") & (points.metric == "pe_sat_readout_vs_KE")
    ]
    raw = frame[frame.particle == "proton"]
    expected = MODULE.linear_fit(averaged, n_files=len(raw))["slope"]
    legacy = np.polyfit(raw.energy_MeV, raw.pe_sat_readout_mean, 1)[0]
    assert fit["slope"] == pytest.approx(expected)
    assert fit["slope"] != pytest.approx(legacy)


def test_nonlinear_response_is_diagnostic_not_accepted() -> None:
    frame = make_rows()
    mask = (frame.particle == "proton") & (frame.energy_MeV == 20)
    frame.loc[mask, "pe_sat_readout_mean"] += 20.0
    result, _ = MODULE.analyze(frame)
    name = "pe_sat_readout_vs_KE_proton"
    assert name not in result["fits"]
    assert result["fit_rejections"][name]["fit_status"] == "LINEAR_MODEL_REJECTED"
    assert result["fit_rejections"][name]["goodness_of_fit_p_value"] < 0.01


def test_duplicate_configuration_is_rejected(tmp_path: Path) -> None:
    frame = make_rows()
    frame = pd.concat([frame, frame.iloc[[0]]], ignore_index=True)
    path = tmp_path / "observed.csv"
    frame.to_csv(path, index=False)
    with pytest.raises(MODULE.CampaignFitError, match="duplicate configuration"):
        MODULE.read_observed(path)


def test_cli_writes_traceable_partial_outputs(tmp_path: Path) -> None:
    observed = tmp_path / "observed.csv"
    output_json = tmp_path / "fits.json"
    output_svg = tmp_path / "fits.svg"
    output_points = tmp_path / "points.csv"
    make_rows().to_csv(observed, index=False)

    status = MODULE.main(
        [
            "--observed",
            str(observed),
            "--output-json",
            str(output_json),
            "--output-svg",
            str(output_svg),
            "--output-points",
            str(output_points),
        ]
    )
    assert status == 0
    payload = json.loads(output_json.read_text())
    assert payload["input"]["sha256"] == MODULE.sha256_file(observed)
    assert payload["fits"]["pe_sat_readout_vs_KE_proton"]["n_energy_points"] == 5
    assert payload["fits"]["pe_sat_readout_vs_KE_proton"]["accepted"] is True
    assert payload["fit_skips"]["pe_sat_readout_vs_KE_deuteron"]["n_energy_points"] == 2
    assert "not detector data" in output_svg.read_text()
    assert len(pd.read_csv(output_points)) == 14
