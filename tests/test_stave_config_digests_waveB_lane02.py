"""Wave B Lane 02: quenching hypothesis + I885 phase-space probe contracts."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

from ccb_mc_validation.geometry.provenance_hashes import digests_for_nominal


def _load_i885_maker():
    path = (
        Path(__file__).resolve().parents[1]
        / "geant4"
        / "single_stave"
        / "slurm"
        / "make_i885_campaign.py"
    )
    spec = importlib.util.spec_from_file_location("make_i885_campaign", path)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    return mod


def test_birks_changes_physics_not_geometry() -> None:
    a = digests_for_nominal({"birks_kB_mm_per_MeV": 0.126})
    b = digests_for_nominal({"birks_kB_mm_per_MeV": 0.22})
    assert a["geometry_hash"] == b["geometry_hash"]
    assert a["physics_hash"] != b["physics_hash"]


def test_far_end_mode_changes_geometry() -> None:
    a = digests_for_nominal({"far_end_mode": "instrumented"})
    b = digests_for_nominal({"far_end_mode": "mirror"})
    assert a["geometry_hash"] != b["geometry_hash"]
    assert a["physics_hash"] == b["physics_hash"]


def test_quenching_defaults_are_hypothesis_not_truth() -> None:
    hh = (
        Path(__file__).resolve().parents[1]
        / "geant4/single_stave/include/AppConfig.hh"
    ).read_text(encoding="utf-8")
    assert "quenching_model_status = \"HYPOTHESIS\"" in hh
    assert "quenching_claims_authorized = false" in hh
    assert "quenching_model_id = \"birks_geant4\"" in hh


def test_i885_campaign_samples_fibre_y_positions(tmp_path: Path) -> None:
    mod = _load_i885_maker()
    assert mod.FIBRE_Y_CM == (-1.0, 1.0)
    rows = mod.build_rows()
    ys = {r[3] for r in rows}
    assert 0.0 in ys and -1.0 in ys and 1.0 in ys
    out = tmp_path / "points.csv"
    mod.main_with_out(str(out))
    text = out.read_text(encoding="utf-8")
    assert "NORMAL_INCIDENCE_ONLY" in text
    assert "phase_space_status=" in text
    assert "DATA_Y_DISTRIBUTION_UNKNOWN" in text
    assert "DATA_ANGLE_DISTRIBUTION_UNKNOWN" in text
    data_lines = [ln for ln in text.splitlines() if ln.strip() and not ln.startswith("#")]
    assert any(len(ln.split(",")) == 8 for ln in data_lines)
    assert any(len(ln.split(",")) == 6 for ln in data_lines)


def test_i885_angular_probe_is_sensitivity_not_data_truth() -> None:
    mod = _load_i885_maker()
    assert mod.ANGULAR_PROBE_THETA_DEG == (0.0, 10.0)
    assert mod.ANGULAR_PROBE_PHI_DEG == (0.0, 90.0)
    assert mod.ANGULAR_PROBE_STATUS == "MC_SENSITIVITY_GRID_DATA_ANGLE_UNKNOWN"
