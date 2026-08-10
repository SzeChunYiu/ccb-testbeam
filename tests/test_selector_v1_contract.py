"""Adversarial contract tests for the frozen S00 selector v1 (Issue #1135)."""

from __future__ import annotations

import numpy as np
import pytest

from ccb_mc_validation.selector import (
    S00_SELECTOR_V1_BASELINE_INDICES,
    S00_SELECTOR_V1_ID,
    SelectorInputError,
    estimate_pedestal_v1,
    estimate_pedestal_v1_batched,
)


def _quiet_waveform(n_samples: int = 18) -> np.ndarray:
    wave = np.full(n_samples, 100.0, dtype=float)
    if n_samples > 8:
        wave[8] = 3000.0
    return wave


def test_v1_identity_binds_exact_first_four_tuple() -> None:
    assert S00_SELECTOR_V1_ID == "v1_first_four_median"
    assert S00_SELECTOR_V1_BASELINE_INDICES == (0, 1, 2, 3)


@pytest.mark.parametrize(
    "indices",
    [
        [2, 3, 4, 5],
        [3, 2, 1, 0],
        [0, 1, 2],
        [0, 1, 2, 3, 4],
        [0, 0, 1, 2],
        [-1, 0, 1, 2],
        [0, 1, 2, 18],
        ["0", "1", "2", "3"],
        [0.0, 1.0, 2.0, 3.0],
        [False, True, 2, 3],
    ],
)
def test_batched_v1_rejects_any_noncanonical_baseline_indices(
    indices: list[object],
) -> None:
    waveforms = np.stack([_quiet_waveform(), _quiet_waveform()])
    with pytest.raises(SelectorInputError, match="baseline indices"):
        estimate_pedestal_v1_batched(waveforms, indices)


def test_batched_v1_accepts_integral_numpy_indices() -> None:
    waveforms = np.stack([_quiet_waveform(), _quiet_waveform() + 10.0])
    indices = np.asarray([0, 1, 2, 3], dtype=np.int64)
    expected = estimate_pedestal_v1_batched(waveforms)
    actual = estimate_pedestal_v1_batched(waveforms, indices)
    np.testing.assert_array_equal(actual, expected)


def test_batched_v1_accepts_none_list_and_tuple_as_same_identity() -> None:
    waveforms = np.stack([_quiet_waveform(), _quiet_waveform() + 10.0])
    implicit = estimate_pedestal_v1_batched(waveforms)
    explicit_list = estimate_pedestal_v1_batched(waveforms, [0, 1, 2, 3])
    explicit_tuple = estimate_pedestal_v1_batched(waveforms, (0, 1, 2, 3))
    np.testing.assert_array_equal(implicit, explicit_list)
    np.testing.assert_array_equal(implicit, explicit_tuple)


@pytest.mark.parametrize("n_samples", [0, 1, 2, 3])
def test_scalar_v1_rejects_waveforms_shorter_than_first_four(n_samples: int) -> None:
    with pytest.raises(SelectorInputError, match="at least four samples"):
        estimate_pedestal_v1(np.full(n_samples, 100.0))


def test_scalar_v1_rejects_non_1d_input() -> None:
    with pytest.raises(SelectorInputError, match="scalar input must be 1-D"):
        estimate_pedestal_v1(np.zeros((2, 18), dtype=float))


@pytest.mark.parametrize("bad_value", [np.nan, np.inf, -np.inf])
def test_scalar_v1_rejects_nonfinite_samples_anywhere(bad_value: float) -> None:
    wave = _quiet_waveform()
    wave[-1] = bad_value
    with pytest.raises(SelectorInputError, match="finite waveform samples"):
        estimate_pedestal_v1(wave)


@pytest.mark.parametrize("bad_value", [np.nan, np.inf, -np.inf])
def test_batched_v1_rejects_nonfinite_samples_anywhere(bad_value: float) -> None:
    waveforms = np.stack([_quiet_waveform(), _quiet_waveform()])
    waveforms[1, -1] = bad_value
    with pytest.raises(SelectorInputError, match="finite waveform samples"):
        estimate_pedestal_v1_batched(waveforms)


def test_batched_v1_rejects_scalar_without_sample_axis() -> None:
    with pytest.raises(SelectorInputError, match="needs a sample axis"):
        estimate_pedestal_v1_batched(np.asarray(100.0))


def test_scalar_and_batched_v1_are_exactly_identical_on_valid_domain() -> None:
    rng = np.random.default_rng(1135)
    waveforms = rng.integers(20, 8000, size=(64, 18)).astype(float)
    batched = estimate_pedestal_v1_batched(waveforms)
    scalar = np.asarray(
        [estimate_pedestal_v1(wave).pedestal_adc for wave in waveforms]
    )
    np.testing.assert_array_equal(batched, scalar)


def test_batched_v1_equals_direct_first_four_median_randomized() -> None:
    rng = np.random.default_rng(1135001)
    waveforms = rng.normal(500.0, 20.0, size=(7, 4, 18))
    expected = np.median(waveforms[..., 0:4], axis=-1)
    actual = estimate_pedestal_v1_batched(waveforms)
    np.testing.assert_array_equal(actual, expected)


def test_issue_1135_selection_flip_counterexample_is_now_rejected() -> None:
    wave = np.asarray(
        [
            100,
            100,
            100,
            100,
            1500,
            1600,
            1800,
            100,
            100,
            100,
            100,
            100,
            100,
            100,
            100,
            100,
            100,
            100,
        ],
        dtype=float,
    )
    canonical = estimate_pedestal_v1_batched(wave[None, :], [0, 1, 2, 3])
    assert canonical[0] == 100.0
    assert float(np.max(wave) - canonical[0]) == 1700.0

    with pytest.raises(SelectorInputError):
        estimate_pedestal_v1_batched(wave[None, :], [2, 3, 4, 5])
    with pytest.raises(SelectorInputError):
        estimate_pedestal_v1_batched(wave[None, :], [4, 5, 6, 7])
