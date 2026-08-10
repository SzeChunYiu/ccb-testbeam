"""Deterministic tests for the no-I/O S00 selector config contract (#1141)."""

from __future__ import annotations

import numpy as np
import pytest

from ccb_mc_validation.s00_selector_contract import (
    S00SelectorConfigError,
    s00_selector_model_identity,
    validate_s00_selector_contract,
)
from ccb_mc_validation.selector import (
    S00_SELECTOR_V1_BASELINE_INDICES,
    S00_SELECTOR_V1_ID,
)


def test_canonical_selector_contract_is_accepted() -> None:
    assert validate_s00_selector_contract({"baseline_samples": [0, 1, 2, 3]}) == (
        0,
        1,
        2,
        3,
    )


def test_numpy_integral_aliases_are_accepted_as_discrete_indices() -> None:
    config = {"baseline_samples": [np.int64(0), np.int32(1), np.int16(2), np.int8(3)]}
    assert validate_s00_selector_contract(config) == S00_SELECTOR_V1_BASELINE_INDICES


@pytest.mark.parametrize(
    "bad",
    [
        [2, 3, 4, 5],
        [3, 2, 1, 0],
        [0, 1, 2],
        [0, 1, 2, 3, 4],
        [0, 1, 1, 3],
        [-1, 1, 2, 3],
        ["0", 1, 2, 3],
        [0.0, 1.0, 2.0, 3.0],
        [False, True, 2, 3],
        123,
        None,
    ],
)
def test_hostile_baseline_mutations_fail_closed(bad: object) -> None:
    with pytest.raises(S00SelectorConfigError):
        validate_s00_selector_contract({"baseline_samples": bad})


def test_missing_baseline_samples_fails_closed() -> None:
    with pytest.raises(S00SelectorConfigError):
        validate_s00_selector_contract({})


def test_non_mapping_config_fails_closed() -> None:
    with pytest.raises(S00SelectorConfigError):
        validate_s00_selector_contract([0, 1, 2, 3])  # type: ignore[arg-type]


def test_manifest_identity_fragment_is_exact_and_self_describing() -> None:
    identity = s00_selector_model_identity()
    assert identity == {
        "selector_id": S00_SELECTOR_V1_ID,
        "baseline_indices": [0, 1, 2, 3],
    }


def test_identity_fragment_returns_fresh_mutable_container() -> None:
    first = s00_selector_model_identity()
    first["baseline_indices"].append(99)  # type: ignore[union-attr]
    second = s00_selector_model_identity()
    assert second["baseline_indices"] == [0, 1, 2, 3]
