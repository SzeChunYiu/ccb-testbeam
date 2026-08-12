"""Lane 09 Wave B regressions for #1010, #963, #1074, #1092."""

from __future__ import annotations

import importlib.util
from pathlib import Path

import numpy as np
import pytest

from ccb_mc_validation.baseline_identifiable import (
    BASELINE_UNIDENTIFIABLE,
    BaselineIdentifiability,
    estimate_quiet_pretrigger_baseline,
    positivity_forced_zero_violation_is_not_evidence,
    synthetic_baseline_bias_table,
)
from ccb_mc_validation.digitizer.electronics import ElectronicsConfig
from ccb_mc_validation.digitizer.electronics_response_authority import (
    ElectronicsResponseAuthorityError,
    ElectronicsResponseClass,
    ElectronicsResponseProvenance,
    assert_detector_claim_authorized,
    claim_gate_status,
    default_unmeasured_provenance,
)
from ccb_mc_validation.digitizer.pipeline import (
    DIGITIZER_RNG_SCHEMA,
    DigitizerPipeline,
)


def test_1010_default_generic_crrc_is_blocked_for_detector_claims():
    status = claim_gate_status()
    assert status["status"] == "BLOCKED"
    assert status["adr"] == "ADR-0010"
    assert (
        status["response_class"]
        == ElectronicsResponseClass.ASSUMPTION_GENERIC_CRRC_NOT_MEASURED.value
    )
    with pytest.raises(ElectronicsResponseAuthorityError, match="BLOCKED"):
        assert_detector_claim_authorized(
            default_unmeasured_provenance(),
            claim="sub_ns_timing_closure",
        )


def test_1010_measured_digest_authorizes_claims():
    prov = ElectronicsResponseProvenance(
        response_class=ElectronicsResponseClass.BENCH_MEASURED,
        impulse_digest="sha256:deadbeef",
        source_id="bench/channel-3",
    )
    out = assert_detector_claim_authorized(prov, claim="waveform_closure")
    assert out.impulse_digest.startswith("sha256:")
    assert claim_gate_status(prov)["status"] == "AUTHORIZED"


def test_1010_data_fit_without_digest_still_blocked():
    prov = ElectronicsResponseProvenance(
        response_class=ElectronicsResponseClass.DATA_FIT,
        impulse_digest=None,
    )
    with pytest.raises(ElectronicsResponseAuthorityError):
        assert_detector_claim_authorized(prov, claim="pileup_resolvability")


def test_963_quiet_pretrigger_recovers_baseline():
    wave = np.full(18, 300.0)
    wave[6] = 2300.0
    est = estimate_quiet_pretrigger_baseline(wave)
    assert est.identifiable
    assert est.baseline_adc == pytest.approx(300.0)
    assert est.identifiability == BaselineIdentifiability.QUIET_IDENTIFIABLE


def test_963_early_active_is_baseline_unidentifiable():
    wave = np.linspace(500.0, 2500.0, 18)
    est = estimate_quiet_pretrigger_baseline(wave, quiet_spread_frac=0.15)
    assert est.identifiability == BASELINE_UNIDENTIFIABLE
    assert not est.identifiable
    assert np.isnan(est.baseline_adc)


def test_963_positivity_zero_violation_rejected_as_evidence():
    verdict = positivity_forced_zero_violation_is_not_evidence(
        fraction_below_tolerance=0.0,
        estimator_enforces_nonnegative=True,
    )
    assert verdict["accepted_as_validation_evidence"] is False
    assert verdict["status"] == "REJECTED_BY_CONSTRUCTION"


def test_963_synthetic_bias_table_covers_pathologies():
    rows = synthetic_baseline_bias_table(seed=7)
    names = {r["pathology"] for r in rows}
    assert names == {"quiet", "early_pulse", "undershoot"}
    quiet = next(r for r in rows if r["pathology"] == "quiet")
    assert quiet["identifiable"] is True
    assert abs(quiet["baseline_bias_adc"]) < 20.0


def test_1074_rng_schema_is_hit_keyed():
    assert DIGITIZER_RNG_SCHEMA == "hit_keyed_v1"


def test_1074_permutation_invariance_with_hit_identity():
    pipe = DigitizerPipeline(
        global_seed=42,
        transport_sigma_ns=5.0,
        electronics=ElectronicsConfig(noise_adc_rms=0.0),
    )
    hits = [
        {"edep_mev": 10.0, "time_ns": 5.0, "track_id": 7, "step_id": 1},
        {"edep_mev": 1.0, "time_ns": 75.0, "track_id": 9, "step_id": 2},
    ]
    a = pipe.run(hits, event_id=123, channel_id=0)
    b = pipe.run(list(reversed(hits)), event_id=123, channel_id=0)
    np.testing.assert_array_equal(a["adc"], b["adc"])
    assert a["digitizer_rng_schema"] == DIGITIZER_RNG_SCHEMA


def test_1074_multi_hit_without_identity_fails_closed():
    pipe = DigitizerPipeline(global_seed=42, transport_sigma_ns=5.0)
    hits = [
        {"edep_mev": 10.0, "time_ns": 5.0},
        {"edep_mev": 1.0, "time_ns": 75.0},
    ]
    with pytest.raises(ValueError, match="stable identity"):
        pipe.run(hits, event_id=123)


def test_1074_single_hit_without_identity_still_runs():
    pipe = DigitizerPipeline(
        global_seed=1,
        transport_sigma_ns=0.5,
        electronics=ElectronicsConfig(noise_adc_rms=0.0),
    )
    out = pipe.run([{"edep_mev": 2.0, "time_ns": 3.0}], event_id=5)
    assert out["adc"].shape == (18,)


def test_1092_campaign_includes_fibre_y_positions():
    mod_path = (
        Path(__file__).resolve().parents[1]
        / "geant4"
        / "single_stave"
        / "slurm"
        / "make_i885_campaign.py"
    )
    spec = importlib.util.spec_from_file_location("make_i885_campaign", mod_path)
    mod = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(mod)
    assert mod.TRANSVERSE_Y_CM == [-1.0, 0.0, 1.0]
    rows = mod.build_rows()
    ys = {
        float(r[3])
        for r in rows
        if float(r[2]) == mod.DEFAULT_HIT_X_CM
        and r[1] in mod.TRANSVERSE_ENERGIES_MEV
    }
    assert -1.0 in ys and 0.0 in ys and 1.0 in ys
    assert mod.PHASE_SPACE_SUPPORT == "central_track_plus_transverse_y_map"

