"""Tests for Sample I/II trigger semantics."""

from __future__ import annotations

import numpy as np

from ccb_mc_validation.truth.trigger import classify_event, process_chunk


def test_sample_ii_is_every_charged_b_entry() -> None:
    flags = classify_event(True, False, float("nan"), 10.0, 15.0)
    assert flags["sample_II"] is True
    assert flags["sample_I"] is False


def test_sample_i_requires_coincidence_strict_less_than() -> None:
    flags = classify_event(True, True, 0.0, 10.0, 15.0)
    assert flags["sample_I"] is True
    assert flags["sample_II"] is True


def test_sample_i_ii_overlap_when_coincident() -> None:
    flags = classify_event(True, True, 5.0, 10.0, 15.0)
    assert flags["sample_I"] is True
    assert flags["sample_II"] is True


def test_boundary_at_exactly_coinc_ns_is_exclusive() -> None:
    coinc_ns = 15.0
    flags = classify_event(True, True, 0.0, coinc_ns, coinc_ns)
    assert flags["sample_II"] is True
    assert flags["sample_I"] is False


def test_process_chunk_from_fixture(truth_mini_npz) -> None:
    data = np.load(truth_mini_npz, allow_pickle=True)
    flags = process_chunk(
        data["Sci_bar_LayerID"],
        data["Sci_bar_LayerID1"],
        data["Sci_bar_PDG"],
        data["Sci_bar_Time"],
        float(data["coinc_ns"]),
    )
    expected_i = data["expected_sample_I"].astype(bool)
    expected_ii = data["expected_sample_II"].astype(bool)
    np.testing.assert_array_equal(flags["sample_I"], expected_i)
    np.testing.assert_array_equal(flags["sample_II"], expected_ii)
