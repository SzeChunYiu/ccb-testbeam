"""Wave D Lane 05: chord TOF surrogate cannot authorise claims (#1127)."""

from __future__ import annotations

import pytest

from ccb_mc_validation.exceptions import ConfigurationError
from ccb_mc_validation.timing.tof_surrogate_contract import (
    TOF_PREDICTOR_SURROGATE,
    require_authorising_tof_predictor,
    surrogate_tof_metadata,
)


def test_surrogate_metadata_is_non_authorising() -> None:
    meta = surrogate_tof_metadata()
    assert meta["predictor_id"] == TOF_PREDICTOR_SURROGATE
    assert meta["claims_authorized"] == "false"


def test_authorising_surrogate_fails_closed() -> None:
    with pytest.raises(ConfigurationError, match="SURROGATE|#1127|BLOCKED"):
        require_authorising_tof_predictor(TOF_PREDICTOR_SURROGATE)
