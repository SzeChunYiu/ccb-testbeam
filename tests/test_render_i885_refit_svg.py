from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pandas as pd
import pytest

SCRIPT = Path(__file__).parents[1] / "scripts" / "single_stave" / "render_i885_refit_svg.py"
SPEC = importlib.util.spec_from_file_location("render_i885_refit_svg", SCRIPT)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(MODULE)


def bundle() -> tuple[dict, pd.DataFrame]:
    fits = {
        "fits": {},
        "fit_rejections": {
            "pe_sat_readout_vs_KE_proton": {
                "fit_status": "LINEAR_MODEL_REJECTED",
                "slope": 2.0,
                "intercept": 1.0,
                "energy_min_MeV": 2.0,
                "energy_max_MeV": 20.0,
                "goodness_of_fit_p_value": 1.62e-232,
                "goodness_of_fit_p_value_underflow": False,
            },
            "edep_scint_MeV_vs_KE_proton": {
                "fit_status": "LINEAR_MODEL_REJECTED",
                "slope": 0.4,
                "intercept": 0.1,
                "energy_min_MeV": 2.0,
                "energy_max_MeV": 20.0,
                "goodness_of_fit_p_value": 0.0,
                "goodness_of_fit_p_value_underflow": True,
            },
        },
        "fit_skips": {
            "pe_sat_readout_vs_KE_deuteron": {
                "status": "SKIPPED_INSUFFICIENT_ENERGY_POINTS",
                "n_energy_points": 2,
                "minimum_energy_points": 3,
            },
            "edep_scint_MeV_vs_KE_deuteron": {
                "status": "SKIPPED_INSUFFICIENT_ENERGY_POINTS",
                "n_energy_points": 2,
                "minimum_energy_points": 3,
            },
        },
        "n_configs": 4,
        "n_events_total": 2000,
    }
    rows = []
    for metric, value in [
        ("pe_sat_readout_vs_KE", 5.0),
        ("edep_scint_MeV_vs_KE", 0.5),
    ]:
        for particle, energy in [("proton", 2.0), ("deuteron", 5.0)]:
            rows.append(
                {
                    "particle": particle,
                    "metric": metric,
                    "energy_MeV": energy,
                    "value": value,
                    "uncertainty": 0.1,
                    "n_files": 2,
                }
            )
    return fits, pd.DataFrame(rows)


def test_svg_records_rejections_skips_and_nondata_scope() -> None:
    fits, points = bundle()
    svg = MODULE.render_svg(fits, points)
    assert "p = 1.62×10⁻²³²" in svg
    assert "p below floating-point range" in svg
    assert "deuteron fit skipped: 2 &lt; 3 energies" in svg
    assert "No accepted calibration function" in svg
    assert "not detector data" in svg


def test_renderer_is_deterministic() -> None:
    fits, points = bundle()
    assert MODULE.render_svg(fits, points) == MODULE.render_svg(fits, points)


def test_accepted_fit_bundle_is_rejected(tmp_path: Path) -> None:
    fits, points = bundle()
    fits["fits"] = {"unsafe": {"accepted": True}}
    fits_path = tmp_path / "fits.json"
    points_path = tmp_path / "points.csv"
    fits_path.write_text(json.dumps(fits))
    points.to_csv(points_path, index=False)
    with pytest.raises(MODULE.RenderError, match="expects no accepted"):
        MODULE.load_inputs(fits_path, points_path)
