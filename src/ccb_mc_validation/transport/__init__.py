"""Fail-closed Geant4 / DAQ transport contracts (Wave B Lane 06).

Issues: #1009 (DAQ digitizer schema), #1095 (step convergence),
#1091 (QGSP_BIC neutron tracking-time cut).
"""

from ccb_mc_validation.transport.daq_digitizer_schema import (
    SCHEMA_VERSION as DAQ_DIGITIZER_SCHEMA_VERSION,
    authorize_production_daq_digitizer,
    load_daq_digitizer_registry,
)
from ccb_mc_validation.transport.neutron_timecut import (
    QGSP_BIC_DEFAULT_NEUTRON_TIME_CUT_US,
    POLICY_VERSION as NEUTRON_TIMECUT_POLICY_VERSION,
    authorize_neutron_timecut_sensitivity_claim,
    require_neutron_timecut_policy,
)
from ccb_mc_validation.transport.step_policy import (
    POLICY_VERSION as STEP_POLICY_VERSION,
    authorize_step_convergence_claim,
    require_step_policy,
)

__all__ = [
    "DAQ_DIGITIZER_SCHEMA_VERSION",
    "NEUTRON_TIMECUT_POLICY_VERSION",
    "QGSP_BIC_DEFAULT_NEUTRON_TIME_CUT_US",
    "STEP_POLICY_VERSION",
    "authorize_neutron_timecut_sensitivity_claim",
    "authorize_production_daq_digitizer",
    "authorize_step_convergence_claim",
    "load_daq_digitizer_registry",
    "require_neutron_timecut_policy",
    "require_step_policy",
]
