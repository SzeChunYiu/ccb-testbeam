"""Lane 06: MC step-policy gate (#1095) + digitizer stage-graph execution (#1077)."""

from __future__ import annotations

import pytest

from ccb_mc_validation.digitizer.pipeline import DigitizerPipeline
from ccb_mc_validation.exceptions import ConfigurationError, StudyBlockedError
from ccb_mc_validation.transport import (
    authorize_step_convergence_claim,
    require_step_policy,
    STEP_POLICY_VERSION,
)


def test_1095_step_policy_gate_fail_closed_without_id():
    with pytest.raises(ConfigurationError, match="step_policy_id is unset"):
        require_step_policy({})


def test_1095_step_policy_pin_documents_blocked_convergence():
    bound = require_step_policy(
        {"step_policy_id": "pin_qgsp_bic_inherited_em_stepfunction"}
    )
    assert bound["policy_version"] == STEP_POLICY_VERSION
    assert bound["claims_authorized"] is False
    with pytest.raises(StudyBlockedError, match="step-convergence claim BLOCKED"):
        authorize_step_convergence_claim(
            {"step_policy_id": "pin_qgsp_bic_inherited_em_stepfunction"}
        )


def test_1077_execution_graph_matches_effective_stages():
    pipe = DigitizerPipeline(
        stages=["birks", "scintillation", "transport", "sampling"]
    )
    assert pipe.stages == pipe.effective_stages == pipe.requested_stages
    out = pipe.run([{"edep_mev": 1.0, "time_ns": 0.0}], event_id=1)
    sg = out["stage_graph"]
    assert sg["requested_stages"] == sg["effective_stages"]
    assert sg["mandatory_inserted"] == []
    assert sg["resolved_stages"][-1] == "daq_observation"
