"""Wave D Lane 03: analysed-stave spacing remains non-authorising for TOF (#992)."""

from __future__ import annotations

import pytest

from ccb_mc_validation.exceptions import ConfigurationError
from ccb_mc_validation.geometry import require_spacing_hypothesis_for_tof


@pytest.mark.parametrize(
    "profile_id",
    [
        "hyp_bstack_spacing_4cm_newer_report",
        "hyp_bstack_spacing_2cm_timing_note",
    ],
)
def test_spacing_profiles_block_authorising_tof(profile_id: str) -> None:
    with pytest.raises(ConfigurationError, match="BLOCKED|claims_authorized=false"):
        require_spacing_hypothesis_for_tof({"geometry_profile_id": profile_id})


def test_non_spacing_profile_rejected_for_tof_gate() -> None:
    with pytest.raises(ConfigurationError, match="analysed_stave_spacing_cm"):
        require_spacing_hypothesis_for_tof(
            {"geometry_profile_id": "hyp_mc_single_stave_50cm_2fibre"}
        )
