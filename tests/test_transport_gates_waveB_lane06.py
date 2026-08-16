"""Wave B Lane 06: DAQ digitizer / step / neutron transport gates."""

from __future__ import annotations

import pytest

from ccb_mc_validation.exceptions import ConfigurationError, StudyBlockedError
from ccb_mc_validation.transport import (
    DAQ_DIGITIZER_SCHEMA_VERSION,
    NEUTRON_TIMECUT_POLICY_VERSION,
    QGSP_BIC_DEFAULT_NEUTRON_TIME_CUT_US,
    STEP_POLICY_VERSION,
    authorize_production_daq_digitizer,
    authorize_step_convergence_claim,
    load_daq_digitizer_registry,
    require_neutron_timecut_policy,
    require_step_policy,
)
from ccb_mc_validation.transport.neutron_timecut import (
    authorize_neutron_timecut_sensitivity_claim,
)


def test_daq_registry_loads_and_marks_legacy_bridges():
    reg = load_daq_digitizer_registry()
    assert reg["schema_version"] == DAQ_DIGITIZER_SCHEMA_VERSION
    assert reg["default_schema_id"] is None
    assert reg["fail_closed_when_unset"] is True
    legacy_ids = {b["id"] for b in reg["legacy_parametric_bridges"]}
    assert "s17c_digitized_g4_waveform_bridge" in legacy_ids
    schema = reg["schemas"]["hyp_hrd_8x16_nominal_10ns_unmeasured"]
    assert schema["status"] == "BLOCKED"
    assert schema["measured_transfer_function"]["evidence_digest"] is None
    assert schema["sample_interval_ns"] is None  # must not invent a clock


def test_daq_authorize_unset_fails_closed():
    with pytest.raises(StudyBlockedError, match="daq_digitizer_schema_id unset"):
        authorize_production_daq_digitizer({})
    with pytest.raises(StudyBlockedError, match="daq_digitizer_schema_id unset"):
        authorize_production_daq_digitizer(None)


def test_daq_blocked_schema_without_measured_tf():
    with pytest.raises(StudyBlockedError, match="APPROVED|measured"):
        authorize_production_daq_digitizer(
            {"daq_digitizer_schema_id": "hyp_hrd_8x16_nominal_10ns_unmeasured"}
        )


def test_daq_unknown_schema_fails():
    with pytest.raises(StudyBlockedError, match="unknown"):
        authorize_production_daq_digitizer(
            {"daq_digitizer_schema_id": "invented_clock_schema"}
        )


def test_daq_rejects_invented_clock_override_even_if_approved_fixture():
    """Caller may not invent sample_interval_ns against a measured schema."""
    registry = {
        "schema_version": DAQ_DIGITIZER_SCHEMA_VERSION,
        "legacy_parametric_bridges": [],
        "required_evidence": [],
        "schemas": {
            "approved_fixture": {
                "status": "APPROVED",
                "n_channels": 8,
                "samples_per_channel": 16,
                "sample_interval_ns": 10.0,
                "measured_transfer_function": {
                    "evidence_digest": "sha256:fixture-only-not-for-production",
                },
            }
        },
    }
    ok = authorize_production_daq_digitizer(
        {"daq_digitizer_schema_id": "approved_fixture"},
        registry=registry,
    )
    assert ok["claims_authorized"] is True
    with pytest.raises(StudyBlockedError, match="invented clocks"):
        authorize_production_daq_digitizer(
            {
                "daq_digitizer_schema_id": "approved_fixture",
                "sample_interval_ns": 0.5,  # invented
            },
            registry=registry,
        )


def test_step_policy_unset_fails_closed():
    with pytest.raises(ConfigurationError, match="step_policy_id is unset"):
        require_step_policy({})


def test_step_policy_pin_loads_but_convergence_blocked():
    bound = require_step_policy(
        {"step_policy_id": "pin_qgsp_bic_inherited_em_stepfunction"}
    )
    assert bound["policy_version"] == STEP_POLICY_VERSION
    assert bound["claims_authorized"] is False
    with pytest.raises(StudyBlockedError, match="step-convergence claim BLOCKED"):
        authorize_step_convergence_claim(
            {"step_policy_id": "pin_qgsp_bic_inherited_em_stepfunction"}
        )


def test_neutron_timecut_unset_fails_closed():
    with pytest.raises(ConfigurationError, match="neutron_timecut_policy_id is unset"):
        require_neutron_timecut_policy({})


def test_neutron_timecut_pins_documented_10us_default():
    bound = require_neutron_timecut_policy(
        {"neutron_timecut_policy_id": "pin_qgsp_bic_default_10us"}
    )
    assert bound["policy_version"] == NEUTRON_TIMECUT_POLICY_VERSION
    assert bound["neutron_time_cut_us"] == pytest.approx(
        QGSP_BIC_DEFAULT_NEUTRON_TIME_CUT_US
    )
    assert bound["neutron_time_cut_us"] == pytest.approx(10.0)
    assert bound["claims_authorized"] is False
    with pytest.raises(StudyBlockedError, match="sensitivity claim BLOCKED"):
        authorize_neutron_timecut_sensitivity_claim(
            {"neutron_timecut_policy_id": "pin_qgsp_bic_default_10us"}
        )


def test_neutron_timecut_rejects_invented_cut_override():
    with pytest.raises(ConfigurationError, match="disagrees"):
        require_neutron_timecut_policy(
            {
                "neutron_timecut_policy_id": "pin_qgsp_bic_default_10us",
                "neutron_time_cut_us": 99.0,
            }
        )
