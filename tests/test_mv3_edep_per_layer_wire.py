import numpy as np
from ccb_mc_validation.studies.mv3_stopping_depth import _resolve_layer_hits

def test_edep_per_layer_resolves_to_hit_mask():
    records = {"edep_per_layer": np.array([[1.0, 0.0, 2.5, 0.0, 0.0, 0.0, 0.0, 0.0],
                                           [0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0]])}
    mask = _resolve_layer_hits(records, n_tracks=2)
    assert mask is not None
    assert mask.shape == (2, 8)
    assert mask[0, 0] and mask[0, 2] and not mask[0, 1]
    assert not mask[1].any()
