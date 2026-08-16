"""DAQ/S00 provenance contracts for Wave A Lane 08.

Modules here encode fail-closed registries and contracts for event identity,
ADC saturation worlds, raw→sorted closure, and run-ledger roles. They do not
invent hardware identities when evidence is contradictory (#1014/#1073).
"""

from ccb_mc_validation.daq.adc_saturation_registry import (
    AdcSaturationContractError,
    authorising_saturation_threshold,
    diagnostic_saturation_flag,
    registry_snapshot as adc_saturation_registry_snapshot,
)
from ccb_mc_validation.daq.event_key_contract import (
    CANONICAL_EVENT_KEY,
    EventKeyContractError,
    event_key_contract_snapshot,
    validate_join_keys,
)
from ccb_mc_validation.daq.raw_sorted_closure import (
    RawSortedClosureError,
    compare_waveform_words,
    closure_report,
)

__all__ = [
    "AdcSaturationContractError",
    "CANONICAL_EVENT_KEY",
    "EventKeyContractError",
    "RawSortedClosureError",
    "adc_saturation_registry_snapshot",
    "authorising_saturation_threshold",
    "closure_report",
    "compare_waveform_words",
    "diagnostic_saturation_flag",
    "event_key_contract_snapshot",
    "validate_join_keys",
]
