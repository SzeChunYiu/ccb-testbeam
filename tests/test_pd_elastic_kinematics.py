from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parents[1] / "tools" / "physics" / "pd_elastic_kinematics.py"
spec = importlib.util.spec_from_file_location("pd_elastic_kinematics", SCRIPT)
assert spec and spec.loader
mod = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = mod
spec.loader.exec_module(mod)


def test_190_mev_proton_recoil_deuteron_at_38_deg():
    sol = mod.solve_pd_elastic_recoil_deuteron(190.0, 38.0)
    # Independent relativistic two-body solution.  The tolerance is deliberately
    # much wider than floating-point error but narrow enough to catch use of the
    # non-relativistic approximation or the wrong outgoing-particle angle.
    assert sol.recoil_kinetic_MeV == pytest.approx(104.18, abs=0.05)
    assert sol.projectile_kinetic_out_MeV == pytest.approx(85.82, abs=0.05)
    assert sol.projectile_lab_angle_deg == pytest.approx(71.94, abs=0.05)
    assert sol.recoil_beta == pytest.approx(0.3201, abs=5e-4)


def test_four_momentum_closure_is_numerical_roundoff():
    sol = mod.solve_pd_elastic_recoil_deuteron(190.0, 38.0)
    assert abs(sol.energy_closure_MeV) < 1e-8
    assert abs(sol.momentum_closure_MeV_c) < 1e-8


def test_tof_scales_linearly_with_distance():
    sol = mod.solve_pd_elastic_recoil_deuteron(190.0, 38.0)
    t2 = mod.tof_ns(2.0, sol.recoil_beta)
    t4 = mod.tof_ns(4.0, sol.recoil_beta)
    assert t2 > 0
    assert t4 == pytest.approx(2.0 * t2, rel=1e-14)


def test_slow_deuteron_has_longer_tof_than_elastic_recoil():
    elastic = mod.solve_pd_elastic_recoil_deuteron(190.0, 38.0)
    beta_15p8 = mod.beta_from_kinetic(15.8, mod.DEFAULT_DEUTERON_MASS_MEV)
    assert 0 < beta_15p8 < elastic.recoil_beta
    assert mod.tof_ns(4.0, beta_15p8) > mod.tof_ns(4.0, elastic.recoil_beta)


def test_invalid_inputs_fail_closed():
    with pytest.raises(ValueError):
        mod.solve_pd_elastic_recoil_deuteron(0.0, 38.0)
    with pytest.raises(ValueError):
        mod.solve_pd_elastic_recoil_deuteron(190.0, 0.0)
    with pytest.raises(ValueError):
        mod.solve_pd_elastic_recoil_deuteron(190.0, 180.0)
    with pytest.raises(ValueError):
        mod.tof_ns(-1.0, 0.5)
    with pytest.raises(ValueError):
        mod.tof_ns(1.0, 1.0)


def test_momentum_and_beta_helpers_are_relativistically_consistent():
    mass = mod.DEFAULT_DEUTERON_MASS_MEV
    kinetic = 104.18
    p = mod.momentum_from_kinetic(kinetic, mass)
    energy = mass + kinetic
    assert energy * energy - p * p == pytest.approx(mass * mass, rel=1e-13)
    assert mod.beta_from_kinetic(kinetic, mass) == pytest.approx(p / energy, rel=1e-15)
