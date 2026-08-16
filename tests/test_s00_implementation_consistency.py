"""Regression tests for the S00 implementation-consistency audit findings.

S00-001 (P0): the ML target is ``selected = amplitude > cut`` while
``amplitude_adc`` was a feature -> circular / perfect-by-construction metrics.
Fix: the feature set must exclude the target-defining column, exposed via
``resolve_ml_features`` with a fail-closed leakage guard.

S00-002 (P1): case-control subsampling (20% selected / 5% rejected) distorts
calibration/prevalence. Fix: carry an inverse-probability ``sampling_weight``
per row so a weighted held-out evaluation restores population prevalence, and
document prevalence.

STAT-002: the S00 accuracy interval must use a ``(run, event)`` cluster
bootstrap (rows from one DAQ event move together), not a row bootstrap. The
``eventno`` column is carried for that purpose.

These tests exercise the PURE helpers only -- they do not require the raw ROOT
data that ``scan_raw`` / ``run_ml_check`` need.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import numpy as np
import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPT_PATH = REPO_ROOT / "scripts" / "01_build_pulse_table_from_root.py"


def _load_s00_module():
    spec = importlib.util.spec_from_file_location("s00_impl_consistency", SCRIPT_PATH)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)  # type: ignore[union-attr]
    return module


@pytest.fixture(scope="module")
def s00():
    if not SCRIPT_PATH.exists():
        pytest.skip(f"{SCRIPT_PATH} not found")
    return _load_s00_module()


# ---------------------------------------------------------------------------
# S00-001: feature-target leakage guard
# ---------------------------------------------------------------------------


def test_target_defining_column_is_amplitude(s00):
    assert s00.TARGET_DEFINING_COLUMN == "amplitude_adc"


def test_default_features_exclude_target_defining_column(s00):
    """The label is amplitude>cut, so amplitude_adc must NOT be a feature."""
    features = s00.resolve_ml_features({})
    assert "amplitude_adc" not in features
    # And the default still carries the physically-independent pulse quantities.
    assert set(features) <= {"area_adc_samples", "peak_sample", "baseline_adc"}


def test_leakage_guard_rejects_amplitude_as_feature(s00):
    with pytest.raises(ValueError, match="leakage"):
        s00.resolve_ml_features(
            {"ml_check": {"features": ["amplitude_adc", "area_adc_samples"]}}
        )


def test_leakage_guard_rejects_partial_amplitude_request(s00):
    with pytest.raises(ValueError, match="amplitude_adc"):
        s00.resolve_ml_features(
            {"ml_check": {"features": ["peak_sample", "amplitude_adc"]}}
        )


# ---------------------------------------------------------------------------
# S00-002: inverse-probability weights restore population prevalence
# ---------------------------------------------------------------------------


def test_case_control_weights_are_inverse_probabilities(s00):
    """selected rows -> 1/0.20 (=5); rejected rows -> 1/0.05 (=20)."""
    sel = np.array([True, False, True, False])
    w = s00.case_control_sampling_weight(sel, keep_selected=0.20, keep_rejected=0.05)
    assert w.tolist() == [5.0, 20.0, 5.0, 20.0]


def test_weighted_evaluation_restores_population_prevalence(s00):
    """Build a known 10%-prevalence population, draw a case-control subsample,
    and verify that the inverse-probability weighted prevalence recovers the
    population prevalence while the raw case-control prevalence is inflated."""
    rng = np.random.default_rng(0)
    pop_selected = np.concatenate([np.ones(100), np.zeros(900)]).astype(int)
    rng.shuffle(pop_selected)
    population_prevalence = pop_selected.mean()  # 0.10

    keep_sel, keep_rej = 0.20, 0.05
    keep_p = np.where(pop_selected.astype(bool), keep_sel, keep_rej)
    kept = rng.random(len(pop_selected)) < keep_p
    kept_selected = pop_selected[kept].astype(bool)
    weights = s00.case_control_sampling_weight(kept_selected, keep_sel, keep_rej)

    raw_prevalence = float(np.mean(kept_selected.astype(int)))
    weighted_prevalence = float(np.sum(weights * kept_selected.astype(int)) / np.sum(weights))

    assert abs(weighted_prevalence - population_prevalence) < 0.02  # restored
    assert raw_prevalence > population_prevalence + 0.10  # case-control inflated


def test_resolve_case_control_keep_precedence(s00, monkeypatch):
    """Env override beats the documented default."""
    monkeypatch.setenv("CCB_ML_CASE_CONTROL_KEEP_SELECTED", "0.30")
    monkeypatch.setenv("CCB_ML_CASE_CONTROL_KEEP_REJECTED", "0.10")
    sel, rej = s00.resolve_case_control_keep({})
    assert sel == 0.30 and rej == 0.10


def test_resolve_case_control_keep_rejects_invalid_rate(s00, monkeypatch):
    monkeypatch.setenv("CCB_ML_CASE_CONTROL_KEEP_SELECTED", "1.5")
    with pytest.raises(ValueError, match="keep_selected"):
        s00.resolve_case_control_keep({})


# ---------------------------------------------------------------------------
# STAT-002: (run, event) cluster plumbing for the S00 accuracy interval
# ---------------------------------------------------------------------------


def test_make_run_event_clusters_groups_by_run_and_event(s00):
    runs = np.array([57, 57, 57, 65, 65])
    events = np.array([100, 100, 101, 200, 200])
    clusters = s00.make_run_event_clusters(runs, events)
    # rows 0,1 share cluster (57,100); row 2 is (57,101); rows 3,4 share (65,200)
    assert clusters[0] == clusters[1]
    assert clusters[3] == clusters[4]
    assert clusters[0] != clusters[2]
    assert clusters[0] != clusters[3]
    assert len(np.unique(clusters)) == 3


def test_make_run_event_clusters_rejects_length_mismatch(s00):
    with pytest.raises(ValueError, match="shape"):
        s00.make_run_event_clusters(np.array([1, 2, 3]), np.array([10, 11]))


def test_build_ml_rows_for_batch_carries_eventno_and_weight(s00):
    """The ml frame must carry eventno (cluster key) + sampling_weight (S00-002)
    and keep rows from the same event labelled together (STAT-002)."""
    amplitude = np.array([[10.0, 2000.0]])  # 1 event x 2 staves; stave B4 selected
    area = np.array([[100.0, 5000.0]])
    peak = np.array([[3, 5]])
    baseline = np.array([[1.0, 2.0]])
    peak_code_adc = np.array([[20.0, 3000.0]])  # absolute peak (raw max)
    saturation = peak_code_adc >= 16383
    selected_mask = amplitude > 1000.0
    keep_mask = np.array([True, True])
    df = s00.build_ml_rows_for_batch(
        run=57,
        group="sample_i",
        event_numbers=np.array([123]),
        stave_grid=np.array(["B2", "B4"]),
        amplitude=amplitude,
        area=area,
        peak_sample=peak,
        baseline=baseline,
        peak_code_adc=peak_code_adc,
        saturation=saturation,
        selected_mask=selected_mask,
        keep_mask=keep_mask,
        keep_selected=0.20,
        keep_rejected=0.05,
    )
    assert set(["eventno", "sampling_weight", "selected"]).issubset(df.columns)
    assert df["eventno"].tolist() == [123, 123]  # same event -> same cluster
    # selected B4 pulse carries weight 1/0.20=5; rejected B2 carries 1/0.05=20
    assert df["sampling_weight"].tolist() == [20.0, 5.0]
    assert df["selected"].tolist() == [0, 1]
    # v1 schema columns
    assert "peak_height_adc" in df.columns
    assert "peak_code_adc" in df.columns
    assert "saturation" in df.columns
    assert df["peak_height_adc"].tolist() == [10.0, 2000.0]
    assert df["peak_code_adc"].tolist() == [20.0, 3000.0]
    assert df["saturation"].tolist() == [False, False]


def test_build_ml_rows_for_batch_keeps_two_pulses_of_one_event_together(s00):
    """STAT-002 invariant: two pulses from one event must share a cluster label
    so the cluster bootstrap moves them together."""
    # 1 event, 2 staves, both above cut
    amplitude = np.array([[1500.0, 2200.0]])
    area = np.array([[4000.0, 6000.0]])
    peak = np.array([[4, 6]])
    baseline = np.array([[1.0, 2.0]])
    peak_code_adc = np.array([[2500.0, 3200.0]])
    saturation = peak_code_adc >= 16383
    selected_mask = amplitude > 1000.0
    keep_mask = np.array([True, True])
    df = s00.build_ml_rows_for_batch(
        run=65,
        group="sample_ii",
        event_numbers=np.array([999]),
        stave_grid=np.array(["B2", "B4"]),
        amplitude=amplitude,
        area=area,
        peak_sample=peak,
        baseline=baseline,
        peak_code_adc=peak_code_adc,
        saturation=saturation,
        selected_mask=selected_mask,
        keep_mask=keep_mask,
        keep_selected=0.20,
        keep_rejected=0.05,
    )
    clusters = s00.make_run_event_clusters(df["run"].to_numpy(), df["eventno"].to_numpy())
    assert clusters[0] == clusters[1]  # same (run,event) -> one resampling unit


# ---------------------------------------------------------------------------
# Regression: scan_raw now returns population_prevalence (S00-002 plumbing)
# ---------------------------------------------------------------------------


def test_scan_raw_signature_includes_population_prevalence(s00):
    """scan_raw is only callable on real ROOT data, but its return arity is
    fixed at the source level -- this guards the 6-element unpacking contract
    used by main() to pass population prevalence into run_ml_check."""
    import inspect

    src = inspect.getsource(s00.scan_raw)
    assert "population_prevalence" in src
    assert "pop_selected" in src and "pop_total" in src


def test_run_ml_check_uses_cluster_bootstrap_and_features_guard(s00):
    """run_ml_check must (a) call resolve_ml_features (leakage guard) and (b)
    use the (run,event) cluster_bootstrap for the accuracy CI. Source-level
    check so we don't need real ROOT data to run it."""
    import inspect

    body = inspect.getsource(s00.run_ml_check)
    assert "resolve_ml_features" in body
    assert "weighted_cluster_bootstrap" in body
    assert "StratifiedGroupKFold" in body
    assert "unweighted fallback" in body
    assert "make_run_event_clusters" in body
    assert "implementation_consistency" in body
    # The amplitude-leakage feature list must be gone.
    assert '"amplitude_adc", "area_adc_samples", "peak_sample", "baseline_adc"' not in body
