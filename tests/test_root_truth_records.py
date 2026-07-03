"""ROOT truth array conversion tests.

Updated 2026-07-03: the previous fixture asserted cross-arm energy sums
(edep_l0 = B-arm 1.5 + A-arm 2.5), enshrining the arm-contamination bug fixed
in _records_from_truth_arrays. Aggregates are now B-arm only, pdg is the
dominant-deposit species, and momenta are GeV/c converted to MeV/c.
"""

from __future__ import annotations

import numpy as np
import pytest

from ccb_mc_validation.io.root_truth import _records_from_truth_arrays


def _fixture_arrays() -> dict:
    return {
        # event 0: one B-arm hit (layer 0) + one A-arm hit (layer 0)
        # event 1: single B-arm deuteron hit
        "Sci_bar_LayerID": np.array([np.array([0, 0]), np.array([0])], dtype=object),
        "Sci_bar_LayerID1": np.array([np.array([1, 2]), np.array([1])], dtype=object),
        "Sci_bar_PDG": np.array([np.array([2212, 2212]), np.array([1000010020])], dtype=object),
        "Sci_bar_EDep": np.array([np.array([1.5, 2.5]), np.array([3.0])], dtype=object),
        "Sci_bar_Time": np.array([np.array([10.0, 12.0]), np.array([4.0])], dtype=object),
        "Sci_bar_TrackLength": np.array([np.array([11.0, 99.0]), np.array([22.0])], dtype=object),
        # momenta in GeV/c (as stored in the truth tree)
        "Sci_bar_Momentum_X": np.array([np.array([0.25, 0.30]), np.array([0.40])], dtype=object),
        "Sci_bar_Momentum_Y": np.array([np.array([0.0, 0.0]), np.array([0.0])], dtype=object),
        "Sci_bar_Momentum_Z": np.array([np.array([0.0, 0.0]), np.array([0.0])], dtype=object),
    }


def test_records_are_b_arm_only_with_physical_ekin() -> None:
    records = _records_from_truth_arrays(_fixture_arrays(), coinc_ns=15.0)

    np.testing.assert_array_equal(records["pdg"], np.array([2212, 1000010020]))
    # B-arm only: the A-arm 2.5 MeV hit must NOT contaminate event 0
    np.testing.assert_allclose(records["edep_l0"], [1.5, 3.0])
    np.testing.assert_allclose(records["edep_l1"], [0.0, 0.0])
    np.testing.assert_allclose(records["edep_tot"], [1.5, 3.0])
    np.testing.assert_array_equal(records["stop_layer"], [0, 0])
    np.testing.assert_array_equal(records["sample_label"], np.array(["I", "II"], dtype=object))

    # tracklen from B-arm hits of the dominant species (not the A-arm 99.0)
    np.testing.assert_allclose(records["tracklen"], [11.0, 22.0])

    # proton with p = 250 MeV/c: T = sqrt(p^2 + m^2) - m ~ 32.8 MeV
    assert records["ekin"][0] == pytest.approx(32.8, abs=0.5)
    # deuteron with p = 400 MeV/c: T ~ 42.2 MeV
    assert records["ekin"][1] == pytest.approx(42.2, abs=0.5)
    # eV-scale values would betray a GeV/MeV unit regression
    assert records["ekin"].min() > 1.0


def test_dominant_species_wins_pdg_label() -> None:
    arrays = _fixture_arrays()
    # event 0: add a small-electron first hit in the B arm; proton still dominates
    arrays["Sci_bar_LayerID"] = np.array([np.array([0, 0, 0]), np.array([0])], dtype=object)
    arrays["Sci_bar_LayerID1"] = np.array([np.array([1, 1, 2]), np.array([1])], dtype=object)
    arrays["Sci_bar_PDG"] = np.array([np.array([11, 2212, 2212]), np.array([1000010020])], dtype=object)
    arrays["Sci_bar_EDep"] = np.array([np.array([0.1, 1.5, 2.5]), np.array([3.0])], dtype=object)
    arrays["Sci_bar_Time"] = np.array([np.array([9.0, 10.0, 12.0]), np.array([4.0])], dtype=object)
    arrays["Sci_bar_TrackLength"] = np.array([np.array([1.0, 11.0, 99.0]), np.array([22.0])], dtype=object)
    arrays["Sci_bar_Momentum_X"] = np.array([np.array([0.01, 0.25, 0.30]), np.array([0.40])], dtype=object)
    arrays["Sci_bar_Momentum_Y"] = np.array([np.array([0.0, 0.0, 0.0]), np.array([0.0])], dtype=object)
    arrays["Sci_bar_Momentum_Z"] = np.array([np.array([0.0, 0.0, 0.0]), np.array([0.0])], dtype=object)

    records = _records_from_truth_arrays(arrays, coinc_ns=15.0)
    assert records["pdg"][0] == 2212  # not the first-hit electron
    np.testing.assert_allclose(records["edep_tot"][0], 1.6)  # B-arm hits only
