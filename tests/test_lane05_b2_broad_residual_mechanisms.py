"""Lane05 mechanism-neutral B2 broad-residual contract tests (#968)."""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pytest

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

import digital_cfd
from ccb_mc_validation.timing.b2_broad_residual_mechanisms import (
    AUTHORISING_PILEUP_LIKE,
    BroadResidualMechanism,
    DiscriminantEvidence,
    PileupLikeAuthorizationError,
    REQUIRED_DISCRIMINANTS,
    assert_pileup_like_authorized,
    authorize_pileup_like_wording,
    classify_b2_broad_residual_support,
    compute_mechanism_neutral_observables,
    mechanism_neutral_class_label,
    rank_mechanism_support,
    select_leading_mechanisms,
)


def test_pileup_like_wording_is_fail_closed_by_default():
    assert AUTHORISING_PILEUP_LIKE is False
    decision = authorize_pileup_like_wording(
        {name: DiscriminantEvidence.SATISFIED for name in REQUIRED_DISCRIMINANTS}
    )
    assert decision.authorized is False
    assert decision.status == "BLOCKED_MECHANISM_UNDISCRIMINATED"
    with pytest.raises(PileupLikeAuthorizationError, match="blocked"):
        assert_pileup_like_authorized(
            {name: DiscriminantEvidence.SATISFIED for name in REQUIRED_DISCRIMINANTS}
        )


def test_missing_discriminants_are_enumerated():
    decision = authorize_pileup_like_wording({})
    assert set(decision.missing_discriminants) == set(REQUIRED_DISCRIMINANTS)


def test_mechanism_neutral_label_never_defaults_to_pileup_like():
    wave = np.asarray([0.0, 20.0, 40.0, 20.0, 0.0, 0.0, 500.0, 1000.0, 500.0])
    selector = digital_cfd.first_local_peak_diagnostics(wave[None, :])
    table = classify_b2_broad_residual_support(wave, selector_diagnostics=selector)
    label = mechanism_neutral_class_label(table)
    assert label != "pileup_like"
    assert label in {"b2_broad_residual_unresolved", "b2_broad_residual_mechanism_ambiguous"}


def test_duplicate_parity_mismatch_supports_mapping_not_pileup():
    wave = np.asarray([0.0, 50.0, 100.0, 50.0, 0.0])
    observables = compute_mechanism_neutral_observables(
        wave,
        duplicate_parity_mismatch=True,
    )
    support = rank_mechanism_support(observables)
    assert support[BroadResidualMechanism.POLARITY_MAPPING] > support[
        BroadResidualMechanism.TWO_PARTICLE_PILEUP
    ]
    leaders = select_leading_mechanisms(support)
    assert leaders == (BroadResidualMechanism.POLARITY_MAPPING,)


def test_equal_top_scores_collapse_to_unresolved():
    support = {
        BroadResidualMechanism.TWO_PARTICLE_PILEUP: 0.5,
        BroadResidualMechanism.SIPM_AFTERPULSE_RECOVERY: 0.5,
        BroadResidualMechanism.UNRESOLVED: 0.0,
    }
    assert select_leading_mechanisms(support) == (BroadResidualMechanism.UNRESOLVED,)


def test_producer_contract_exposes_selector_diagnostics_token():
    source = (SCRIPTS / "real_data_cfd_timing.py").read_text(encoding="utf-8")
    assert "first_local_peak_diagnostics" in source
    assert "first_local_peak_selector" in source
