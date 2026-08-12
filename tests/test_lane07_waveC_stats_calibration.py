"""Lane 07 Wave C regressions for issues #1007 #1079 #986 #1095."""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]


def _load(name: str, rel: str):
    if str(REPO) not in sys.path:
        sys.path.insert(0, str(REPO))
    if str(REPO / "scripts") not in sys.path:
        sys.path.insert(0, str(REPO / "scripts"))
    path = REPO / rel
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture(scope="module")
def scope():
    return _load("lane07_scope", "scripts/lane07/stopping_power_track_scope.py")


@pytest.fixture(scope="module")
def birks():
    return _load("lane07_birks", "scripts/lane07/birks_parameter_contract.py")


@pytest.fixture(scope="module")
def prov():
    return _load("lane07_prov", "scripts/lane07/provenance_digests.py")


@pytest.fixture(scope="module")
def stepc():
    return _load("lane07_step", "scripts/lane07/step_convergence_contract.py")


# --- #1007 ---

def test_1007_legacy_missing_scope_is_not_pstar_comparable(scope):
    meta = scope.resolve_table_track_scope({})
    assert meta["track_scope"] == scope.SCOPE_LEGACY_UNDECLARED
    assert meta["primary_pstar_scope_comparable"] is False
    assert meta["pstar_acceptance_gate"] == "BLOCKED_NON_PRIMARY_OR_UNDECLARED_SCOPE"


def test_1007_primary_scope_opens_gate(scope):
    meta = scope.resolve_table_track_scope({"track_scope": "PRIMARY_PROJECTILE"})
    assert meta["primary_pstar_scope_comparable"] is True
    assert meta["pstar_acceptance_gate"] == "OPEN_FOR_SCOPE"


def test_1007_event_total_blocked(scope):
    meta = scope.resolve_table_track_scope({"track_scope": "EVENT_TOTAL_NON_OPTICAL"})
    assert meta["primary_pstar_scope_comparable"] is False


def test_1007_unknown_scope_fails_closed(scope):
    with pytest.raises(scope.TrackScopeError, match="unknown track_scope"):
        scope.normalize_track_scope("NOT_A_REAL_SCOPE", missing_is_legacy=False)


def _load_csp():
    path = REPO / "scripts" / "single_stave" / "compare_stopping_power.py"
    spec = importlib.util.spec_from_file_location("compare_stopping_power_waveC", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_1007_compare_marks_undeclared_noncomparable(tmp_path):
    import csv

    csp = _load_csp()
    ref = tmp_path / "pstar.csv"
    ref.write_text(
        "energy_MeV,electronic_MeV_cm2_g,nuclear_MeV_cm2_g,total_MeV_cm2_g\n"
        "1,9,1,10\n2,4,1,5\n"
    )
    sim = tmp_path / "sim.csv"
    with sim.open("w", newline="") as handle:
        w = csv.writer(handle)
        # Event-total columns => not PSTAR-primary-comparable (#1007 on main).
        w.writerow(["particle", "ke_MeV", "edep_scint_raw_MeV", "track_len_scint_mm"])
        w.writerow(["proton", 1.0, 1.0, 1.0])
    results, _ = csp.run_compare(sim, ref, rho=1.06, out_path=None, tol_pct=50.0)
    assert results[0]["track_length_scope"] == "EVENT_TOTAL_ALL_NON_OPTICAL"
    assert results[0]["pstar_primary_identity_ok"] is False
    assert "NONCOMPARABLE" in results[0]["acceptance_status"]


def test_1007_compare_primary_scope_comparable_without_uncertainty(tmp_path):
    import csv

    csp = _load_csp()
    ref = tmp_path / "pstar.csv"
    ref.write_text(
        "energy_MeV,electronic_MeV_cm2_g,nuclear_MeV_cm2_g,total_MeV_cm2_g\n"
        "1,9,1,10\n2,4,1,5\n"
    )
    sim = tmp_path / "sim.csv"
    with sim.open("w", newline="") as handle:
        w = csv.writer(handle)
        w.writerow(
            [
                "particle",
                "ke_MeV",
                "primary_edep_scint_raw_MeV",
                "primary_track_len_scint_mm",
            ]
        )
        w.writerow(["proton", 1.0, 1.0, 1.0])
    results, _ = csp.run_compare(sim, ref, rho=1.0, out_path=None, tol_pct=1.0)
    assert results[0]["track_length_scope"] == "PRIMARY_TRACK"
    assert results[0]["pstar_primary_identity_ok"] is True
    assert results[0]["acceptance_status"] == "NOT_ACCEPTED_NO_UNCERTAINTY"
    assert results[0]["within_tolerance"] is False  # uncertainty gate still closed


# --- #1079 ---

def test_1079_worlds_remain_distinct(birks):
    birks.assert_worlds_remain_distinct()
    assert birks.HYPOTHESES["H2_PYTHON_DIGITIZER_LEGACY_DEFAULT"]["k_b_cm_per_mev"] == 0.008
    assert birks.HYPOTHESES["H3_GEANT4_SINGLE_STAVE_DEFAULT"]["k_b_cm_per_mev"] == 0.0126


def test_1079_require_explicit_kb_when_enabled(birks):
    with pytest.raises(birks.BirksContractError, match="#1079"):
        birks.require_explicit_k_b(apply_birks=True, k_b_cm_per_mev=None)


def test_1079_hypothesis_id_resolves_kb(birks):
    out = birks.require_explicit_k_b(
        apply_birks=True, k_b_cm_per_mev=None, hypothesis_id="H3_GEANT4_SINGLE_STAVE_DEFAULT"
    )
    assert out["k_b_cm_per_mev"] == pytest.approx(0.0126)
    assert out["canonical_default"] is False


def test_1079_pipeline_fails_without_kb():
    from ccb_mc_validation.digitizer.pipeline import DigitizerPipeline

    pipe = DigitizerPipeline(apply_birks=True)
    with pytest.raises(ValueError, match="#1079|birks_kB_cm_per_MeV"):
        pipe.run([{"edep_mev": 1.0, "time_ns": 0.0, "step_length_cm": 1.0}], event_id=1)


def test_1079_pipeline_accepts_hypothesis(birks):
    from ccb_mc_validation.digitizer.electronics import ElectronicsConfig
    from ccb_mc_validation.digitizer.pipeline import DigitizerPipeline

    # Main DigitizerPipeline takes explicit unit-tagged kB (#1079); hypothesis
    # worlds remain in scripts/lane07/birks_parameter_contract.py.
    kb = birks.require_explicit_k_b(
        apply_birks=True,
        k_b_cm_per_mev=None,
        hypothesis_id="H2_PYTHON_DIGITIZER_LEGACY_DEFAULT",
    )["k_b_cm_per_mev"]
    pipe = DigitizerPipeline(
        apply_birks=True,
        birks_kB_cm_per_MeV=kb,
        transport_sigma_ns=0.0,
        electronics=ElectronicsConfig(noise_adc_rms=0.0, gain_adc_per_mev=1.0, pedestal_adc=0.0),
    )
    out = pipe.run([{"edep_mev": 1.0, "time_ns": 0.0, "step_length_cm": 1.0}], event_id=1)
    assert out["adc"].shape[0] > 0


# --- #986 ---

def test_986_birks_change_does_not_change_geometry_digest(prov):
    base = dict(
        stave_half_x_mm=250.0,
        stave_half_y_mm=25.9,
        stave_half_z_mm=10.0,
        hole_radius_mm=1.0,
        fibre_radius_mm=0.9,
        fibre_half_x_mm=250.0,
        fibre_sep_mm=20.0,
        coating_thk_mm=0.25,
        sensor_thk_mm=0.10,
        far_end_mode="instrumented",
    )
    g1 = prov.geometry_config_sha256(**base)
    g2 = prov.geometry_config_sha256(**base)
    assert g1 == g2
    p1 = prov.physics_config_sha256(birks_kB_mm_per_MeV=0.126, optical_interface_model="UNKNOWN_EXTERNAL")
    p2 = prov.physics_config_sha256(birks_kB_mm_per_MeV=0.08, optical_interface_model="UNKNOWN_EXTERNAL")
    assert p1 != p2
    # geometry digest API has no birks kw — changing physics must not require geometry change
    assert "birks" not in prov.geometry_config_payload(**base)


def test_986_far_end_and_coating_change_geometry(prov):
    base = dict(
        stave_half_x_mm=250.0,
        stave_half_y_mm=25.9,
        stave_half_z_mm=10.0,
        hole_radius_mm=1.0,
        fibre_radius_mm=0.9,
        fibre_half_x_mm=250.0,
        fibre_sep_mm=20.0,
        coating_thk_mm=0.25,
        sensor_thk_mm=0.10,
        far_end_mode="instrumented",
    )
    g0 = prov.geometry_config_sha256(**base)
    g_far = prov.geometry_config_sha256(**{**base, "far_end_mode": "mirror"})
    g_coat = prov.geometry_config_sha256(**{**base, "coating_thk_mm": 0.50})
    g_sens = prov.geometry_config_sha256(**{**base, "sensor_thk_mm": 0.20})
    assert len({g0, g_far, g_coat, g_sens}) == 4


# --- #1095 ---

def test_1095_default_application_undeclared(stepc):
    pol = stepc.current_application_status()
    assert pol["status"] == stepc.STATUS_UNDECLARED
    assert pol["authorising_bragg_birks_claims"] is False


def test_1095_authorising_claim_blocked_without_study(stepc):
    gate = stepc.gate_authorising_bragg_claim()
    assert gate["decision"] == "BLOCKED"
    assert gate["authorising"] is False
    assert "STEP_CONVERGENCE" in gate["reason"]


def test_1095_study_artifact_opens_gate(stepc):
    pol = stepc.current_application_status(study_artifact_id="step-conv-study-001")
    gate = stepc.gate_authorising_bragg_claim(pol)
    assert gate["decision"] == "OK"
    assert gate["authorising"] is True


def test_1095_declared_without_study_still_non_authorising(stepc):
    pol = stepc.current_application_status(has_user_limits=True)
    assert pol["status"] == stepc.STATUS_DECLARED
    gate = stepc.gate_authorising_bragg_claim(pol)
    assert gate["decision"] == "BLOCKED"
