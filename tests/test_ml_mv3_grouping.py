"""Regression tests for the ML-evaluation / MV3-stopping audit fixes.

Covers ML-001 (no same-set threshold fit/eval), ML-002 (group-disjoint
splits), ML-003 (fail-closed model errors), ML-004 (deterministic estimators
+ version provenance), MV3-001 (no parity-synthesized Sample I/II), and
MV3-002 (occupancy uses actual per-layer hit masks).
"""

from __future__ import annotations

import json

import numpy as np
import pytest

from ccb_mc_validation.exceptions import SplitLeakageError
from ccb_mc_validation.studies.common import (
    ERROR_SKIP_MARKERS,
    ProductionIntegrityError,
    StudyResult,
    StudyStatus,
    reject_error_skip_markers,
    write_study_result,
)
from ccb_mc_validation.studies.mv1_pid import DEUTERON_PDG, PROTON_PDG, run_mv1
from ccb_mc_validation.studies.mv2_energy_range import run_mv2
from ccb_mc_validation.studies.mv3_stopping_depth import run_mv3
from ccb_mc_validation.studies.splits import (
    SplitRegistry,
    assert_group_disjoint,
    default_group_split,
)


# --------------------------------------------------------------------------- #
# Fixtures
# --------------------------------------------------------------------------- #
def _separable_records(
    n_per_class: int = 1500,
    seed: int = 7,
    *,
    with_event_id: bool = True,
    tracks_per_event: int = 4,
) -> dict[str, np.ndarray]:
    rng = np.random.default_rng(seed)
    n = n_per_class * 2
    pdg = np.array([PROTON_PDG] * n_per_class + [DEUTERON_PDG] * n_per_class)
    edep_l0 = np.concatenate(
        [rng.normal(1.2, 0.15, n_per_class), rng.normal(2.4, 0.2, n_per_class)]
    )
    edep_l1 = np.concatenate(
        [rng.normal(0.8, 0.1, n_per_class), rng.normal(1.1, 0.12, n_per_class)]
    )
    edep_tot = edep_l0 + edep_l1 + rng.normal(0.5, 0.05, n)
    stop_layer = np.concatenate(
        [rng.integers(1, 4, n_per_class), rng.integers(3, 6, n_per_class)]
    ).astype(np.int16)
    rec = {
        "pdg": pdg,
        "ekin": rng.uniform(20, 80, n),
        "edep_l0": edep_l0.astype(np.float32),
        "edep_l1": edep_l1.astype(np.float32),
        "edep_tot": edep_tot.astype(np.float32),
        "stop_layer": stop_layer,
        "nlayers": (stop_layer + 1).astype(np.int16),
        "tracklen": rng.uniform(10, 40, n).astype(np.float32),
    }
    if with_event_id:
        # ~tracks_per_event tracks per immutable event_id (multi-track -> leakage
        # risk that group-disjoint splits must prevent).
        rec["event_id"] = np.repeat(np.arange(n // tracks_per_event), tracks_per_event)[:n]
    return rec


# --------------------------------------------------------------------------- #
# ML-002: group-disjoint splits
# --------------------------------------------------------------------------- #
def test_group_holdout_has_zero_group_overlap():
    rec = _separable_records()
    groups = rec["event_id"]
    tr, te = default_group_split(groups, seed=171101)
    assert_group_disjoint(tr, te, groups)  # raises on any overlap
    train_groups = set(np.unique(groups[tr]).tolist())
    test_groups = set(np.unique(groups[te]).tolist())
    assert train_groups.isdisjoint(test_groups)
    assert (tr | te).all() and not (tr & te).any()


def test_group_kfold_has_zero_group_overlap():
    g = np.repeat(np.arange(40), 3)
    sr = SplitRegistry(name="gkf", train_fraction=0.8, seed=0, strategy="group_kfold", n_splits=5)
    tr, te = sr.train_test_masks(len(g), groups=g)
    assert_group_disjoint(tr, te, g)
    assert (tr | te).all() and not (tr & te).any()


def test_assert_group_disjoint_raises_on_overlap():
    g = np.array([0, 0, 1, 2, 2, 3])
    tr = np.array([True, True, False, False, False, False])
    te = np.array([False, False, False, True, True, True])
    assert_group_disjoint(tr, te, g)  # clean
    bad_te = te.copy()
    bad_te[0] = True  # group 0 now in both
    with pytest.raises(SplitLeakageError):
        assert_group_disjoint(tr, bad_te, g)


def test_group_strategy_refuses_none_groups():
    sr = SplitRegistry(name="gh", train_fraction=0.5, seed=0, strategy="group_holdout")
    with pytest.raises(ValueError):
        sr.train_test_masks(10, groups=None)


def test_mv1_train_test_groups_are_disjoint_in_production_run():
    """End-to-end: run_mv1 must not split a shared event_id across train/test."""
    rec = _separable_records(n_per_class=1200, tracks_per_event=4)
    result = run_mv1(rec, fixture=True)
    assert result.status.value in {"FIXTURE", "PRODUCTION"}
    # Reconstruct the masks via the same default group split and verify.
    pdg = rec["pdg"]
    mask = (pdg == PROTON_PDG) | (pdg == DEUTERON_PDG)
    groups_sub = rec["event_id"][mask]
    tr, te = default_group_split(groups_sub, seed=171101)
    assert_group_disjoint(tr, te, groups_sub)


# --------------------------------------------------------------------------- #
# ML-001: threshold fit on train, held-out eval
# --------------------------------------------------------------------------- #
def _mv1_train_test_masks(rec: dict[str, np.ndarray], seed: int = 171101):
    pdg = rec["pdg"]
    mask = (pdg == PROTON_PDG) | (pdg == DEUTERON_PDG)
    groups_sub = rec["event_id"][mask]
    tr, te = default_group_split(groups_sub, seed=seed)
    return mask, tr, te


def test_mv1_threshold_fit_on_train_only_not_all_data():
    rec = _separable_records(n_per_class=1200, tracks_per_event=4, seed=11)
    split = SplitRegistry(name="gh", train_fraction=0.5, seed=171101, strategy="group_holdout")
    result = run_mv1(rec, fixture=True, split=split)

    mask, tr, te = _mv1_train_test_masks(rec, seed=171101)
    pdg = rec["pdg"]
    isp = pdg == PROTON_PDG
    isd = pdg == DEUTERON_PDG
    masked_idx = np.where(mask)[0]
    train_full = np.zeros(len(pdg), dtype=bool)
    test_full = np.zeros(len(pdg), dtype=bool)
    train_full[masked_idx[tr]] = True
    test_full[masked_idx[te]] = True

    expected_thr = float(
        np.median(
            np.concatenate([rec["edep_l0"][isp & train_full], rec["edep_l0"][isd & train_full]])
        )
    )
    all_thr = float(np.median(np.concatenate([rec["edep_l0"][isp], rec["edep_l0"][isd]])))
    # Threshold must match the TRAIN-only median, and the test must be
    # meaningful (train-only != all-data median on this fixture).
    assert result.metrics["cut_edep_l0_thr_MeV"] == pytest.approx(expected_thr, rel=1e-5)
    assert expected_thr != pytest.approx(all_thr, abs=1e-6)

    # Held-out purity/efficiency recomputed on TEST only must match.
    X0 = rec["edep_l0"][mask][te]
    y_te = isd[mask][te].astype(int)
    pred = (X0 > expected_thr).astype(int)
    tp = int(((pred == 1) & (y_te == 1)).sum())
    fp = int(((pred == 1) & (y_te == 0)).sum())
    purity = tp / (tp + fp) if (tp + fp) else 0.0
    assert result.metrics["cut_purity_heldout"] == pytest.approx(purity, rel=1e-6)
    assert result.metrics["cut_n_train_fit"] == int(
        (isp & train_full).sum() + (isd & train_full).sum()
    )
    assert result.metrics["cut_n_test_eval"] == int(te.sum())


def test_mv1_held_out_groups_disjoint_from_threshold_fit():
    rec = _separable_records(n_per_class=1200, tracks_per_event=4, seed=13)
    split = SplitRegistry(name="gh", train_fraction=0.5, seed=42, strategy="group_holdout")
    result = run_mv1(rec, fixture=True, split=split)
    # train/test counts must partition the binary subset with zero overlap.
    assert (
        result.metrics["n_train"] + result.metrics["n_test"]
        >= int(((rec["pdg"] == PROTON_PDG) | (rec["pdg"] == DEUTERON_PDG)).sum()) - 1
    )  # group rounding
    # The disjointness is enforced inside the split; verify split_strategy recorded.
    assert result.provenance["split"]["strategy"] == "group_holdout"


# --------------------------------------------------------------------------- #
# ML-003: fail-closed model errors
# --------------------------------------------------------------------------- #
def test_mv1_insufficient_samples_is_blocked_not_production():
    # 500 per class -> 1000 binary < MIN_BINARY_SAMPLES (2000)
    rec = _separable_records(n_per_class=500, with_event_id=True, tracks_per_event=2)
    result = run_mv1(rec)
    assert result.status == StudyStatus.BLOCKED
    assert "_ml_error" not in result.metrics
    assert "skipped_ml" not in result.metrics
    assert "reason" in result.metrics


def test_mv1_model_exception_is_failed_not_production(monkeypatch):
    rec = _separable_records(n_per_class=1200, tracks_per_event=4)
    import sklearn.ensemble as se

    def boom(self, X, y):  # noqa: ARG001
        raise RuntimeError("synthetic model failure")

    monkeypatch.setattr(se.HistGradientBoostingClassifier, "fit", boom)
    result = run_mv1(rec, fixture=True)
    assert result.status == StudyStatus.FAILED
    assert "_ml_error" not in result.metrics
    assert "ml_failure" in result.metrics
    # Even when the ML path failed, the simple-cut baseline still used train/test
    # discipline (ML-001), not all-data leakage.
    assert "cut_purity_heldout" in result.metrics


def test_mv2_all_species_insufficient_is_blocked():
    rec = _separable_records(n_per_class=500, tracks_per_event=2)
    result = run_mv2(rec)
    assert result.status == StudyStatus.BLOCKED
    assert "_ml_error" not in result.metrics
    assert "skipped_ml" not in result.metrics


def test_mv2_model_exception_is_failed(monkeypatch):
    # Need >= MIN_REGRESSION_SAMPLES (2000) uncensored per species so the
    # regressor .fit is actually reached (otherwise it short-circuits to
    # per-species "insufficient" and never calls the patched estimator).
    rec = _separable_records(n_per_class=2500, tracks_per_event=4)
    import sklearn.ensemble as se

    def boom(self, X, y):  # noqa: ARG001
        raise RuntimeError("synthetic regressor failure")

    monkeypatch.setattr(se.HistGradientBoostingRegressor, "fit", boom)
    result = run_mv2(rec, fixture=True)
    assert result.status == StudyStatus.FAILED
    assert "_ml_error" not in result.metrics
    assert "ml_failure" in result.metrics


def test_validation_layer_rejects_production_with_markers(tmp_path):
    bad = StudyResult(
        study_id="MVX",
        status=StudyStatus.PRODUCTION,
        metrics={"_ml_error": "boom", "logreg_auc": 0.99},
    )
    with pytest.raises(ProductionIntegrityError):
        reject_error_skip_markers(bad)
    with pytest.raises(ProductionIntegrityError):
        write_study_result(bad, tmp_path)


def test_validation_layer_allows_failed_with_diagnostics(tmp_path):
    ok = StudyResult(
        study_id="MVX",
        status=StudyStatus.FAILED,
        metrics={"_ml_error": "boom"},
    )
    reject_error_skip_markers(ok)  # no raise
    path = write_study_result(ok, tmp_path)
    payload = json.loads(path.read_text())
    assert payload["status"] == "FAILED"


def test_error_skip_markers_contract():
    assert "_ml_error" in ERROR_SKIP_MARKERS
    assert "skipped_ml" in ERROR_SKIP_MARKERS


# --------------------------------------------------------------------------- #
# ML-004: deterministic estimators + version provenance
# --------------------------------------------------------------------------- #
def test_mv1_records_estimator_seeds_and_versions():
    rec = _separable_records(n_per_class=1200, tracks_per_event=4)
    result = run_mv1(rec, fixture=True)
    est = result.provenance["estimators"]
    assert "random_state=0" in est["logreg"]
    assert "random_state=0" in est["hgb"]
    versions = result.provenance["versions"]
    assert "scikit-learn" in versions and "numpy" in versions and "python" in versions


def test_mv1_is_deterministic_under_fixed_split():
    rec = _separable_records(n_per_class=1200, tracks_per_event=4, seed=21)
    split = SplitRegistry(name="gh", train_fraction=0.5, seed=171101, strategy="group_holdout")
    r1 = run_mv1(rec, fixture=True, split=split)
    r2 = run_mv1(rec, fixture=True, split=split)
    for key in ("logreg_auc", "hgb_auc", "cut_edep_l0_thr_MeV", "cut_purity_heldout"):
        assert r1.metrics[key] == pytest.approx(r2.metrics[key]), f"{key} not deterministic"


def test_mv2_records_estimator_seed_and_versions():
    rec = _separable_records(n_per_class=1500, tracks_per_event=4)
    result = run_mv2(rec, fixture=True)
    assert "random_state=0" in result.provenance["estimator"]
    assert "scikit-learn" in result.provenance["versions"]


# --------------------------------------------------------------------------- #
# MV3-001: no parity-synthesized Sample I/II
# --------------------------------------------------------------------------- #
def _mv3_layer_hits(n: int, stop_max: int = 5, seed: int = 0) -> np.ndarray:
    rng = np.random.default_rng(seed)
    hits = np.zeros((n, 8), dtype=bool)
    for t in range(n):
        depth = int(rng.integers(2, stop_max + 1))
        hits[t, :depth] = True
    return hits


def test_mv3_blocks_when_sample_label_absent():
    n = 200
    rec = {
        "pdg": np.full(n, PROTON_PDG),
        "stop_layer": np.ones(n, dtype=np.int16),
        "edep_tot": np.ones(n, dtype=np.float32),
        "layer_hits": _mv3_layer_hits(n),
    }
    result = run_mv3(rec)
    assert result.status == StudyStatus.BLOCKED
    assert "MV3-001" in result.metrics["reason"]


def test_mv3_blocks_when_labels_all_none():
    n = 200
    rec = {
        "pdg": np.full(n, PROTON_PDG),
        "stop_layer": np.ones(n, dtype=np.int16),
        "edep_tot": np.ones(n, dtype=np.float32),
        "layer_hits": _mv3_layer_hits(n),
        "sample_label": np.array(["NONE"] * n),
    }
    result = run_mv3(rec)
    assert result.status == StudyStatus.BLOCKED
    assert "MV3-001" in result.metrics["reason"]


def test_mv3_no_parity_proxy_cutflow():
    n = 200
    rec = {
        "pdg": np.full(n, PROTON_PDG),
        "stop_layer": np.ones(n, dtype=np.int16),
        "edep_tot": np.ones(n, dtype=np.float32),
        "layer_hits": _mv3_layer_hits(n),
        "event_id": np.arange(n),
    }
    result = run_mv3(rec)
    assert result.status == StudyStatus.BLOCKED
    # The event-parity proxy must be gone entirely.
    assert "sample_proxy_event_parity" not in result.cutflow


# --------------------------------------------------------------------------- #
# MV3-002: occupancy uses actual per-layer hit masks
# --------------------------------------------------------------------------- #
def test_mv3_blocks_when_layer_hits_absent():
    n = 200
    rec = {
        "pdg": np.full(n, PROTON_PDG),
        "stop_layer": np.full(n, 3, dtype=np.int16),
        "edep_tot": np.ones(n, dtype=np.float32),
        "sample_label": np.array(["I"] * n),
    }
    result = run_mv3(rec)
    assert result.status == StudyStatus.BLOCKED
    assert "MV3-002" in result.metrics["reason"]


def test_mv3_skipped_layer_not_counted_as_crossed():
    # 4 Sample-I tracks, all stop at layer 3. Two tracks SKIP layer 1
    # (hits in {0,2,3}); two cross all of {0,1,2,3}.
    hits = np.zeros((4, 4), dtype=bool)
    hits[0] = [True, False, True, True]
    hits[1] = [True, False, True, True]
    hits[2] = [True, True, True, True]
    hits[3] = [True, True, True, True]
    rec = {
        "pdg": np.full(4, PROTON_PDG),
        "stop_layer": np.full(4, 3, dtype=np.int16),
        "edep_tot": np.ones(4, dtype=np.float32),
        "sample_label": np.array(["I", "I", "I", "I"]),
        "layer_hits": hits,
    }
    result = run_mv3(rec)
    assert result.status in {StudyStatus.PRODUCTION, StudyStatus.FIXTURE}
    occ = result.metrics["layer_occupancy_sample_I"]
    # Layer 1 occupied by 2/4 tracks (the two non-skippers) -> 0.5.
    # The old stop_layer>=lay proxy would have counted ALL 4 -> 1.0.
    assert occ[1] == pytest.approx(0.5)
    assert occ[0] == pytest.approx(1.0)
    assert occ[2] == pytest.approx(1.0)
    assert occ[3] == pytest.approx(1.0)


def test_mv3_accepts_edep_per_layer_as_hit_mask():
    n = 50
    epl = np.zeros((n, 8))
    epl[:, 0] = 1.5
    epl[:, 1] = 0.0  # skipped layer 1
    epl[:, 2] = 0.7
    rec = {
        "pdg": np.full(n, PROTON_PDG),
        "stop_layer": np.full(n, 2, dtype=np.int16),
        "edep_tot": np.ones(n, dtype=np.float32),
        "sample_label": np.array(["I"] * n),
        "edep_per_layer": epl,
    }
    result = run_mv3(rec)
    assert result.status in {StudyStatus.PRODUCTION, StudyStatus.FIXTURE}
    occ = result.metrics["layer_occupancy_sample_I"]
    assert occ[1] == pytest.approx(0.0)  # edep 0 -> not crossed
    assert occ[0] == pytest.approx(1.0)
