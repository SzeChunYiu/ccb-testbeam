"""MV1 fixture: separable synthetic tracks must yield AUC > 0.5."""

from __future__ import annotations

import numpy as np

from ccb_mc_validation.studies.mv1_pid import PROTON_PDG, DEUTERON_PDG, run_mv1


def _synthetic_separable_tracks(n_per_class: int = 1500, seed: int = 7) -> dict[str, np.ndarray]:
    rng = np.random.default_rng(seed)
    n_per_class = int(n_per_class)
    pdg = np.array([PROTON_PDG] * n_per_class + [DEUTERON_PDG] * n_per_class)
    edep_l0 = np.concatenate(
        [
            rng.normal(1.2, 0.15, n_per_class),
            rng.normal(2.4, 0.2, n_per_class),
        ]
    )
    edep_l1 = np.concatenate(
        [
            rng.normal(0.8, 0.1, n_per_class),
            rng.normal(1.1, 0.12, n_per_class),
        ]
    )
    edep_tot = edep_l0 + edep_l1 + rng.normal(0.5, 0.05, n_per_class * 2)
    stop_layer = np.concatenate(
        [
            rng.integers(1, 4, n_per_class),
            rng.integers(3, 6, n_per_class),
        ]
    ).astype(np.int16)
    n = n_per_class * 2
    return {
        "pdg": pdg,
        "ekin": rng.uniform(20, 80, n),
        "edep_l0": edep_l0.astype(np.float32),
        "edep_l1": edep_l1.astype(np.float32),
        "edep_tot": edep_tot.astype(np.float32),
        "stop_layer": stop_layer,
        "nlayers": (stop_layer + 1).astype(np.int16),
        "tracklen": rng.uniform(10, 40, n).astype(np.float32),
    }


def test_mv1_fixture_auc_above_chance():
    records = _synthetic_separable_tracks()
    result = run_mv1(records, fixture=True)
    assert result.status.value == "FIXTURE"
    auc = result.metrics.get("logreg_auc") or result.metrics.get("hgb_auc")
    assert auc is not None, f"expected computed AUC, got metrics={result.metrics}"
    assert auc > 0.5, f"AUC {auc} not above chance on separable fixture"
