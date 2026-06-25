"""ROOT truth array conversion tests."""

from __future__ import annotations

import numpy as np

from ccb_mc_validation.io.root_truth import _records_from_truth_arrays


def test_records_from_truth_arrays_computes_features_and_sample_labels() -> None:
    arrays = {
        "Sci_bar_LayerID": np.array([np.array([0, 0]), np.array([0])], dtype=object),
        "Sci_bar_LayerID1": np.array([np.array([1, 2]), np.array([1])], dtype=object),
        "Sci_bar_PDG": np.array([np.array([2212, 2212]), np.array([1000010020])], dtype=object),
        "Sci_bar_EDep": np.array([np.array([1.5, 2.5]), np.array([3.0])], dtype=object),
        "Sci_bar_Time": np.array([np.array([10.0, 12.0]), np.array([4.0])], dtype=object),
        "Sci_bar_TrackLength": np.array([np.array([11.0]), np.array([22.0])], dtype=object),
        "Sci_bar_Momentum_X": np.array([np.array([100.0]), np.array([200.0])], dtype=object),
        "Sci_bar_Momentum_Y": np.array([np.array([0.0]), np.array([0.0])], dtype=object),
        "Sci_bar_Momentum_Z": np.array([np.array([0.0]), np.array([0.0])], dtype=object),
    }

    records = _records_from_truth_arrays(arrays, coinc_ns=15.0)

    np.testing.assert_array_equal(records["pdg"], np.array([2212, 1000010020]))
    np.testing.assert_allclose(records["edep_l0"], [4.0, 3.0])
    np.testing.assert_allclose(records["edep_l1"], [0.0, 0.0])
    np.testing.assert_allclose(records["edep_tot"], [4.0, 3.0])
    np.testing.assert_array_equal(records["stop_layer"], [0, 0])
    np.testing.assert_array_equal(records["sample_label"], np.array(["I", "II"], dtype=object))
    assert records["ekin"][0] > 0.0
