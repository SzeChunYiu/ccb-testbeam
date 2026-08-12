"""Atomic tests for the S00 saturation field authorization boundary (#1073)."""

from __future__ import annotations

import numpy as np
import pytest

from ccb_mc_validation.daq.adc_saturation_registry import AdcSaturationContractError
from ccb_mc_validation.daq.s00_saturation_field import (
    LEGACY_DIAGNOSTIC_WORLD,
    STATUS_DIAGNOSTIC_ONLY,
    field_contract,
    legacy_world_a_diagnostic,
    require_authorising_saturation_contract,
)


def test_field_contract_is_explicitly_non_authorising():
    contract = field_contract()
    assert contract["schema"] == "ccb-s00-saturation-field/1"
    assert contract["field_name"] == "saturation"
    assert contract["semantic_class"] == STATUS_DIAGNOSTIC_ONLY
    assert contract["diagnostic_world_id"] == LEGACY_DIAGNOSTIC_WORLD == "A"
    assert contract["authorising"] is False
    assert contract["hardware_censoring_claim"] is False
    assert contract["registry_status"] == "BLOCKED_HARDWARE_EVIDENCE"
    assert contract["parent_issue"] == 1014
    assert contract["issue"] == 1073


def test_legacy_world_a_diagnostic_preserves_numerical_map_but_not_claim_status():
    values = np.array([0, 4095, 6999, 7000, 16382, 16383, 20000], dtype=float)
    flags, meta = legacy_world_a_diagnostic(values)

    # Numerical backward-compatibility with the historical S00 map is deliberate.
    assert flags.tolist() == [False, False, False, False, False, True, True]
    assert meta["threshold_adc_code"] == 16383
    assert meta["diagnostic_world_id"] == "A"
    assert meta["registry_authorising"] is False
    assert meta["authorising"] is False
    assert meta["hardware_censoring_claim"] is False


def test_named_world_a_diagnostic_does_not_choose_between_incompatible_worlds():
    values = np.array([4094, 4095, 6999, 7000, 16382, 16383], dtype=float)
    flags, meta = legacy_world_a_diagnostic(values)

    # The helper is not a detector oracle: it answers only the named World-A
    # counterfactual.  Values at the other repository boundaries stay ordinary
    # under World A and therefore cannot be promoted to statements about DATA.
    assert flags.tolist() == [False, False, False, False, False, True]
    assert meta["semantic_class"] == "DIAGNOSTIC_ONLY_ADC_WORLD_UNRESOLVED"


def test_physical_saturation_claim_fails_closed_while_registry_is_blocked():
    with pytest.raises(AdcSaturationContractError, match="1073"):
        require_authorising_saturation_contract()
