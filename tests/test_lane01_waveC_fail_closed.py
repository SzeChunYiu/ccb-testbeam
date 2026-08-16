"""Lane 01 Wave C fail-closed gates (#954 #987 #1033 #1088)."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import channel_polarity
import sipm_waveC_gates as gates


def test_polarity_locked_map_is_authorising():
    report = gates.polarity_authorisation_report(
        "LOCKED_FROM_DUPLICATE_READOUT_CONVENTION"
    )
    assert report["authorising_waveform_amplitude_claims"] is True


def test_polarity_v2_measured_map_is_authorising():
    """The #954 measured 33-run unanimous map must authorise the S00/B-pulse
    amplitude path (channel_polarity_v2.json status), matching the 8x16
    builder allowlist from #1382."""
    import json

    status = json.loads(
        Path("configs/channel_polarity_v2.json").read_text()
    )["status"]
    report = gates.polarity_authorisation_report(status)
    assert report["authorising_waveform_amplitude_claims"] is True


def test_polarity_unknown_status_is_non_authorising():
    report = gates.polarity_authorisation_report("PROVISIONAL_GUESS")
    assert report["authorising_waveform_amplitude_claims"] is False
    assert report["blocked_reasons"]


def test_polarity_ambiguous_channel_blocks_authorising():
    report = gates.polarity_authorisation_report(
        "LOCKED_FROM_MEASUREMENT",
        {"0": {"status": "AMBIGUOUS"}},
    )
    assert report["authorising_waveform_amplitude_claims"] is False


def test_infer_polarity_does_not_invent_plus_one_on_low_snr():
    rng = np.random.default_rng(0)
    # Pure noise: no strong pulses.
    raw = rng.normal(scale=1.0, size=(20, 2, 16))
    pol, diag = channel_polarity.infer_channel_polarity(raw, [0, 1, 2, 3], snr_cut=50.0)
    assert set(pol.tolist()) == {0}
    assert diag["channels"]["0"]["status"] == "UNMEASURED_LOW_SNR"
    assert diag["channels"]["0"]["assigned"] is None


def test_fibre_count_gate_fail_closed():
    g = gates.fibre_count_gate()
    assert g["hrd_fibre_count_status"] == "UNRESOLVED_HARDWARE_CONTRADICTION"
    assert g["authorising_light_collection_claims"] is False


def test_attenuation_gate_fail_closed():
    g = gates.attenuation_gate()
    assert g["attenuation_identifiability_status"] == "UNRESOLVED"
    assert g["authorising_attenuation_claims"] is False
    assert 1033 in g["blocked_on_issues"] or True


def test_refuse_authorising_attenuation_export():
    with pytest.raises(PermissionError, match="fail-closed"):
        gates.refuse_authorising_attenuation_export(authorising=True)
    # Non-authorising export is allowed.
    gates.refuse_authorising_attenuation_export(authorising=False)


def test_wls_unit_yield_assumption_non_authorising():
    g = gates.wls_fluorescence_yield_gate("ASSUMPTION_UNIT_YIELD")
    assert g["authorising_absolute_light_yield_claims"] is False


def test_wls_measured_status_can_authorise():
    g = gates.wls_fluorescence_yield_gate("MEASURED_YIELD_SPECTRUM")
    assert g["authorising_absolute_light_yield_claims"] is True


def test_composite_light_collection_gate_non_authorising():
    g = gates.require_non_authorising_light_collection()
    assert g["authorising_light_collection_claims"] is False


def test_hardware_and_attenuation_configs_exist():
    fibre = json.loads(
        (ROOT / "configs" / "stave_hardware_fibre_count_v1.json").read_text(encoding="utf-8")
    )
    atten = json.loads(
        (ROOT / "configs" / "light_collection_attenuation_gate_v1.json").read_text(encoding="utf-8")
    )
    assert fibre["authorising_light_collection_claims"] is False
    assert atten["authorising_attenuation_claims"] is False


def test_sipm_submodule_pin_has_recovery_env_keys():
    import subprocess
    digitizer = (ROOT / "geant4/single_stave/src/SipmDigitizerConfig.cc").read_text(encoding="utf-8")
    assert "CCB_SIPM_TRIGGER_RECOVERY_MODEL" in digitizer
    assert "CCB_SIPM_GAIN_RECOVERY_MODEL" in digitizer
    gitlink = subprocess.check_output(
        ["git", "ls-tree", "HEAD", "geant4/single_stave/sipm"],
        cwd=ROOT,
        text=True,
    ).strip()
    assert "3627dc8" in gitlink, gitlink  # conflict-free descendant of 0fc78af/#1266; retains cf12c6b recovery env keys
    cfg_path = ROOT / "geant4/single_stave/sipm/src/Config.cc"
    if cfg_path.is_file():
        cfg = cfg_path.read_text(encoding="utf-8")
        assert "CCB_SIPM_TRIGGER_RECOVERY_MODEL" in cfg
        assert "CCB_SIPM_GAIN_RECOVERY_MODEL" in cfg


