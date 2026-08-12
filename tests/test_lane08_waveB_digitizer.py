"""Lane 08 Wave B: digitizer fail-closed config/domain/stage-graph (#1075/#1076/#1077/#1080)."""

from __future__ import annotations

import numpy as np
import pytest

from ccb_mc_validation.digitizer.config_types import parse_strict_bool, resolve_stage_graph
from ccb_mc_validation.digitizer.electronics import ElectronicsConfig
from ccb_mc_validation.digitizer.pipeline import DigitizerPipeline
from ccb_mc_validation.digitizer.sampling import integrate_samples
from ccb_mc_validation.digitizer.scintillation import (
    exponential_kernel_cdf,
    exponential_kernel_pdf,
)


# ---------------------------------------------------------------------------
# #1076 strict boolean parsing
# ---------------------------------------------------------------------------
@pytest.mark.parametrize(
    "raw,expected",
    [
        (False, False),
        (True, True),
        (0, False),
        (1, True),
        ("false", False),
        ("true", True),
        ("FALSE", False),
        ("True", True),
        ("0", False),
        ("1", True),
        ("no", False),
        ("yes", True),
        ("off", False),
        ("on", True),
    ],
)
def test_1076_parse_strict_bool_accepted(raw, expected):
    assert parse_strict_bool(raw, field_name="apply_birks") is expected


@pytest.mark.parametrize("raw", ["flase", "maybe", "", None, 2, 0.5, [], {}])
def test_1076_parse_strict_bool_rejects_ambiguous(raw):
    with pytest.raises(ValueError, match="apply_birks"):
        parse_strict_bool(raw, field_name="apply_birks")


def test_1076_from_config_string_false_disables_birks():
    # Regression: bool("false") is True in Python; must NOT enable Birks.
    pipe = DigitizerPipeline.from_config({"apply_birks": "false"})
    assert pipe.apply_birks is False
    # Without step info, Birks-off must still run (would fail if Birks were on).
    out = pipe.run([{"edep_mev": 1.0, "time_ns": 0.0}], event_id=1)
    assert out["adc"].shape == (18,)


def test_1076_from_config_typo_rejected():
    with pytest.raises(ValueError, match="apply_birks"):
        DigitizerPipeline.from_config({"apply_birks": "flase"})


def test_1076_effective_birks_in_resolved_config():
    pipe = DigitizerPipeline.from_config({
        "apply_birks": "true",
        "birks_kB_cm_per_MeV": 0.008,
    })
    assert pipe.resolved_config()["apply_birks"]["effective"] is True


# ---------------------------------------------------------------------------
# #1075 reject nonphysical tau (no silent clamp)
# ---------------------------------------------------------------------------
@pytest.mark.parametrize("tau", [0.0, -1.0, float("nan"), float("inf")])
def test_1075_kernel_rejects_invalid_tau_rise(tau):
    with pytest.raises(ValueError, match="tau_rise_ns"):
        exponential_kernel_pdf(np.linspace(0, 10, 5), tau, 35.0)


@pytest.mark.parametrize("tau", [0.0, -1e-9, float("-inf")])
def test_1075_kernel_rejects_invalid_tau_decay(tau):
    with pytest.raises(ValueError, match="tau_decay_ns"):
        exponential_kernel_cdf(np.array([1.0]), 2.0, tau)


def test_1075_from_config_rejects_zero_tau():
    with pytest.raises(ValueError, match="tau_rise_ns"):
        DigitizerPipeline.from_config({"tau_rise_ns": 0.0})


def test_1075_nominal_taus_still_match_unit_integral():
    t = np.linspace(0, 2000, 400001)
    pdf = exponential_kernel_pdf(t, 2.0, 35.0)
    trap = getattr(np, "trapezoid", None) or np.trapz
    assert trap(pdf, t) == pytest.approx(1.0, abs=1e-6)


# ---------------------------------------------------------------------------
# #1080 scalar domain preflight
# ---------------------------------------------------------------------------
def test_1080_rejects_n_samples_zero():
    with pytest.raises(ValueError, match="n_samples"):
        DigitizerPipeline(n_samples=0)


def test_1080_rejects_sample_spacing_zero():
    with pytest.raises(ValueError, match="sample_spacing_ns"):
        DigitizerPipeline(sample_spacing_ns=0.0)


def test_1080_rejects_negative_sample_spacing():
    with pytest.raises(ValueError, match="sample_spacing_ns"):
        DigitizerPipeline.from_config({"sample_spacing_ns": -1.0})


def test_1080_rejects_negative_transport_sigma():
    with pytest.raises(ValueError, match="transport_sigma_ns"):
        DigitizerPipeline(transport_sigma_ns=-0.1)


def test_1080_zero_transport_sigma_is_valid_control():
    pipe = DigitizerPipeline(
        transport_sigma_ns=0.0,
        electronics=ElectronicsConfig(noise_adc_rms=0.0),
    )
    out = pipe.run([{"edep_mev": 1.0, "time_ns": 0.0}], event_id=1)
    assert out["adc"].shape == (18,)


def test_1080_rejects_negative_noise():
    with pytest.raises(ValueError, match="noise_adc_rms"):
        ElectronicsConfig(noise_adc_rms=-1.0)


def test_1080_rejects_nonfinite_gain():
    with pytest.raises(ValueError, match="gain_adc_per_mev"):
        ElectronicsConfig(gain_adc_per_mev=float("nan"))


def test_1080_integrate_samples_rejects_zero_spacing():
    with pytest.raises(ValueError, match="sample_spacing_ns"):
        integrate_samples(1.0, 0.0, sample_spacing_ns=0.0)


# ---------------------------------------------------------------------------
# #1077 stage graph requested == effective (no hidden fallbacks)
# ---------------------------------------------------------------------------
def test_1077_electronics_stage_rejected():
    with pytest.raises(ValueError, match="electronics"):
        DigitizerPipeline(stages=["birks", "scintillation", "transport", "sampling", "electronics"])


def test_1077_duplicate_stages_rejected():
    with pytest.raises(ValueError, match="duplicate"):
        resolve_stage_graph(["birks", "birks", "sampling"])


def test_1077_out_of_order_rejected():
    with pytest.raises(ValueError, match="order"):
        resolve_stage_graph(["sampling", "transport"])


def test_1077_missing_sampling_is_mandatory_inserted():
    pipe = DigitizerPipeline(stages=["birks", "scintillation", "transport"])
    assert "sampling" in pipe.effective_stages
    assert pipe.stage_graph_meta["mandatory_inserted"] == ["sampling"]
    # And sampling actually executes (no silent-only path): waveform finite.
    out = pipe.run([{"edep_mev": 1.0, "time_ns": 0.0}], event_id=2)
    assert np.all(np.isfinite(out["adc"]))
    assert out["stage_graph"]["mandatory_final"] == "daq_observation_once"
    # Run provenance must match construction graph (not re-resolve effective list).
    assert out["stage_graph"]["requested_stages"] == pipe.requested_stages
    assert out["stage_graph"]["effective_stages"] == pipe.effective_stages
    assert out["stage_graph"]["mandatory_inserted"] == ["sampling"]
    assert pipe.stages == pipe.effective_stages


def test_1077_run_rejects_hidden_integrate_samples_fallback():
    pipe = DigitizerPipeline(stages=["birks", "scintillation", "transport", "sampling"])
    # Simulate a corrupted executor list that skips sampling without updating graph.
    pipe.stages = ["birks", "scintillation", "transport"]
    with pytest.raises(ValueError, match="hidden integrate_samples"):
        pipe.run([{"edep_mev": 1.0, "time_ns": 0.0}], event_id=3)


def test_1077_unknown_stage_rejected():
    with pytest.raises(ValueError, match="unknown"):
        DigitizerPipeline(stages=["birks", "magic"])


def test_1077_default_graph_identity():
    pipe = DigitizerPipeline()
    assert pipe.requested_stages == ["birks", "scintillation", "transport", "sampling"]
    assert pipe.effective_stages == pipe.requested_stages
    assert pipe.stage_graph_meta["mandatory_inserted"] == []
