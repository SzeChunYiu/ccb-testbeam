"""Tests for scripts/compare_data_mc.py v7 (OOB cluster-bootstrap null with scale refit, #1164)."""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pytest

_REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_REPO / "scripts"))
import compare_data_mc as cmc

# ── Fixtures ──────────────────────────────────────────────────────────────────


@pytest.fixture
def mock_data_dir(tmp_path: Path) -> Path:
    """Create a minimal data-side output directory with B2-amplitude arrays."""
    d = tmp_path / "data"
    d.mkdir()
    # Write data_sample_split_summary.json
    summ = {
        "headline_first_B_layer_B2": {
            "sampleI_frac_saturated": 0.03,
            "sampleII_frac_saturated": 0.12,
            "sampleI_frac_large": 0.4,
            "sampleII_frac_large": 0.2,
            "sampleI_n": 500,
            "sampleII_n": 2000,
            "sampleI_mean_adc": 2000.0,
            "sampleII_mean_adc": 2500.0,
        },
        "per_sample": {
            "I": {"depth_fraction": {"B2": 0.5, "B4": 0.3, "B6": 0.15, "B8": 0.05}},
            "II": {"depth_fraction": {"B2": 0.4, "B4": 0.3, "B6": 0.2, "B8": 0.1}},
        },
    }
    (d / "data_sample_split_summary.json").write_text(json.dumps(summ), encoding="utf-8")
    # B2 amplitude arrays with source-event cluster IDs (run:eventno key, #1164)
    rng = np.random.default_rng(42)
    nI, nII = 200, 400
    np.savez_compressed(
        d / "first_B_layer_B2_amplitude.npz",
        sampleI=rng.exponential(2000, nI).astype(np.float32),
        sampleII=rng.exponential(2500, nII).astype(np.float32),
        sampleI_cluster_id=np.arange(nI, dtype=np.int64),
        sampleII_cluster_id=np.arange(nII, dtype=np.int64),
    )
    return d


@pytest.fixture
def mock_mc_dir(tmp_path: Path) -> Path:
    """Create a minimal MC-side output directory with event-level EDep arrays + weights + cluster IDs (#1164)."""
    d = tmp_path / "mc"
    d.mkdir()
    # Write mc_trigger_split_summary.json
    summ = {
        "samples": {
            "I": {
                "n_events": 5000,
                "B_layers": [
                    {"pid_fraction": {"p": 0.3, "d": 0.7}, "frac_large": 0.4,
                     "mean_edep_MeV": 3.5, "hits": 5000},
                ],
                "enter_B_pid_fraction": {"p": 0.3, "d": 0.7},
                "enter_A_pid_fraction": {"p": 0.5, "d": 0.5},
            },
            "II": {
                "n_events": 10000,
                "B_layers": [
                    {"pid_fraction": {"p": 0.8, "d": 0.2}, "frac_large": 0.2,
                     "mean_edep_MeV": 2.5, "hits": 10000},
                ],
                "enter_B_pid_fraction": {"p": 0.8, "d": 0.2},
                "enter_A_pid_fraction": {"p": 0.9, "d": 0.1},
            },
        },
    }
    (d / "mc_trigger_split_summary.json").write_text(json.dumps(summ), encoding="utf-8")
    # Event-level EDep arrays (#1052) with weights and cluster IDs (#1164)
    rng = np.random.default_rng(42)
    nI, nII = 200, 400
    np.savez_compressed(
        d / "first_B_layer_event_edep.npz",
        sampleI=rng.exponential(3.0, nI).astype(np.float32),
        sampleII=rng.exponential(2.0, nII).astype(np.float32),
        sampleI_weights=np.ones(nI, dtype=np.float32),
        sampleII_weights=np.ones(nII, dtype=np.float32),
        sampleI_cluster_id=np.arange(nI, dtype=np.int64),
        sampleII_cluster_id=np.arange(nII, dtype=np.int64),
        sampleI_in_sample_i=np.ones(nI, dtype=bool),
        sampleI_in_sample_ii=np.ones(nI, dtype=bool),
        sampleII_in_sample_i=np.zeros(nII, dtype=bool),
        sampleII_in_sample_ii=np.ones(nII, dtype=bool),
        statistical_unit=np.asarray(["event_stave_edep"]),
        cluster_key=np.asarray(["generator_event_index"]),
        weight_semantics=np.asarray(["PrimaryWeight_first_primary"]),
    )
    return d


@pytest.fixture
def mock_mc_dir_legacy(tmp_path: Path) -> Path:
    """MC dir without weight arrays (legacy producer)."""
    d = tmp_path / "mc_legacy"
    d.mkdir()
    rng = np.random.default_rng(42)
    nI, nII = 100, 200
    np.savez_compressed(
        d / "first_B_layer_edep.npz",
        sampleI=rng.exponential(3.0, nI).astype(np.float32),
        sampleII=rng.exponential(2.0, nII).astype(np.float32),
        # no sampleI_weights / sampleII_weights
    )
    # Stub a minimal JSON to avoid import errors
    summ = {
        "samples": {
            "I": {"n_events": nI, "B_layers": [{"pid_fraction": {"p": 0.5, "d": 0.5},
                                                 "frac_large": 0.3, "mean_edep_MeV": 3.0, "hits": nI}],
                   "enter_B_pid_fraction": {"p": 0.5, "d": 0.5},
                   "enter_A_pid_fraction": {"p": 0.5, "d": 0.5}},
            "II": {"n_events": nII, "B_layers": [{"pid_fraction": {"p": 0.5, "d": 0.5},
                                                   "frac_large": 0.2, "mean_edep_MeV": 2.0, "hits": nII}],
                   "enter_B_pid_fraction": {"p": 0.5, "d": 0.5},
                   "enter_A_pid_fraction": {"p": 0.5, "d": 0.5}},
        },
    }
    (d / "mc_trigger_split_summary.json").write_text(json.dumps(summ), encoding="utf-8")
    return d


# ── Tests ─────────────────────────────────────────────────────────────────────


class TestWeightedMedian:
    def test_weighted_median_uniform(self):
        assert cmc._wmedian([1, 2, 3], [1, 1, 1]) == pytest.approx(2.0)

    def test_weighted_median_skewed(self):
        assert cmc._wmedian([1, 2, 10], [1, 1, 10]) == pytest.approx(10.0)

    def test_weighted_median_raises_on_none(self):
        with pytest.raises(ValueError, match="requires a weight"):
            cmc._wmedian([1, 2, 3], None)

    def test_weighted_median_raises_on_zero_sum(self):
        with pytest.raises(ValueError, match="not positive"):
            cmc._wmedian([1, 2, 3], [0, 0, 0])


class TestWeightedECDF:
    def test_uniform_weights_match_ecdf(self):
        x = np.array([1.0, 2.0, 3.0, 4.0])
        w = np.ones(4)
        xs, cdf = cmc._weighted_ecdf(x, w)
        np.testing.assert_array_equal(xs, x)
        np.testing.assert_array_almost_equal(cdf, [0.25, 0.5, 0.75, 1.0])

    def test_skewed_weights(self):
        x = np.array([1.0, 2.0, 10.0])
        w = np.array([1.0, 1.0, 8.0])
        xs, cdf = cmc._weighted_ecdf(x, w)
        # At xs=10, cumulative weight = 10/10 = 1.0
        assert cdf[-1] == pytest.approx(1.0)
        # At xs=2, cumulative weight = 2/10 = 0.2
        assert cdf[1] == pytest.approx(0.2)


class TestWeightedKS:
    def test_identical_samples(self):
        rng = np.random.default_rng(42)
        x = rng.normal(size=100)
        w = np.ones(100)
        result = cmc._weighted_ks_stat(x, x, w, w, n_bootstrap=50)
        assert result["D"] <= 0.2  # should be close to 0
        assert result["p_value"] >= 0.01  # legacy diagnostic only
        assert result["p_value_status"] == "NONAUTHORISING_LEGACY_UNIT_WEIGHT_PERMUTATION"

    def test_different_means(self):
        rng = np.random.default_rng(42)
        x = rng.normal(0, 1, 100)
        y = rng.normal(5, 1, 100)
        w = np.ones(100)
        result = cmc._weighted_ks_stat(x, y, w, w, n_bootstrap=50)
        assert result["D"] > 0.5
        assert result["p_value"] < 0.05  # legacy diagnostic only
        assert result["p_value_status"] == "NONAUTHORISING_LEGACY_UNIT_WEIGHT_PERMUTATION"

    def test_insufficient_data(self):
        result = cmc._weighted_ks_stat(np.array([1.0]), np.array([2.0]),
                                        np.ones(1), np.ones(1))
        assert result["D"] == 0.0
        assert result["p_value"] == 1.0
        assert result["p_value_status"] == "NONAUTHORISING_LEGACY_UNIT_WEIGHT_PERMUTATION"


class TestWeightValidation:
    def test_unit_weights_pass(self):
        audit = cmc._validate_weight_vector(np.ones(100), "test")
        assert audit.absolute_effective_sample_size == pytest.approx(100.0)

    def test_dominant_weight_fails(self):
        with pytest.raises(ValueError, match="WEIGHT_DOMINANCE_LIMIT"):
            cmc._validate_weight_vector([1.0, 1.0, 98.0], "test")

    def test_negative_weight_fails(self):
        with pytest.raises(ValueError, match="NEGATIVE_WEIGHT_FORBIDDEN"):
            cmc._validate_weight_vector([1.0, -1.0, 1.0], "test")

    def test_nonfinite_weight_fails(self):
        with pytest.raises(ValueError, match="NONFINITE_WEIGHT"):
            cmc._validate_weight_vector([1.0, np.nan, 1.0], "test")

    def test_zero_sum_fails(self):
        with pytest.raises(ValueError, match="ZERO_SIGNED_SUM"):
            cmc._validate_weight_vector([1.0, -1.0], "test")


class TestWeightDiagnostics:
    def test_diagnostics_dict_shape(self):
        audit = cmc._weight_diagnostics(
            cmc._validate_weight_vector(np.ones(100), "test"))
        assert audit["n"] == 100
        assert audit["absolute_effective_sample_size"] == 100.0
        assert audit["all_unit_weights"] is True
        assert "cancellation_fraction" in audit
        assert "coefficient_of_variation_abs" in audit


class TestEndToEnd:
    def test_happy_path(self, mock_mc_dir, mock_data_dir, tmp_path):
        out = tmp_path / "out"
        cmc.main([
            "--mc-dir", str(mock_mc_dir),
            "--data-dir", str(mock_data_dir),
            "--out", str(out),
        ])
        assert (out / "data_mc_comparison.json").exists()
        comp = json.loads((out / "data_mc_comparison.json").read_text(encoding="utf-8"))
        assert comp["version"] == "v7"
        assert "spectrum_contract" in comp
        assert "scale_topology" in comp
        assert comp["scale_topology"]["nuisance_mode_default"] == "refit_inside_replicate"
        assert comp["mc_primary_weight_applied"] is True
        assert "mc_weight_diagnostics" in comp
        assert "sampleI" in comp["mc_weight_diagnostics"]
        assert "sampleII" in comp["mc_weight_diagnostics"]
        assert "ks_tests" in comp
        for s in ("Sample I", "Sample II"):
            ks = comp["ks_tests"][s]
            assert ks["weighted"] is True
            assert ks["D"] >= 0
            assert ks["cdf_convention"] == "right_continuous"
            assert ks["ecdf_support"] == "unique_tie_aggregated"
            assert ks["p_value_status"] == "NONAUTHORISING_LEGACY_UNIT_WEIGHT_PERMUTATION"
        # OOB cluster-bootstrap null with per-replicate scale refit (#1164)
        oob = comp["oob_null"]
        assert oob["status"] == "OK"
        assert oob["method"] == "oob_cluster_bootstrap_scale_refit"
        assert oob["fit_sample"] == "II"
        assert oob["statistical_unit_contract"]["mc_cluster_key"] == "generator_event_index"
        assert oob["statistical_unit_contract"]["data_cluster_key"] == "run:eventno"
        for s in ("I", "II"):
            assert oob[s]["n_boot_success"] >= 500
            assert oob[s]["n_boot_failure"] == 0
            assert oob[s]["D_obs"] == pytest.approx(comp["ks_tests"][
                "Sample I" if s == "I" else "Sample II"]["D"])
            assert 0.0 <= oob[s]["p_value"] <= 1.0

    def test_legacy_missing_weights_fails_closed(self, mock_mc_dir_legacy,
                                                  mock_data_dir, tmp_path):
        out = tmp_path / "out"
        with pytest.raises(ValueError, match="missing sampleI_weights"):
            cmc.main([
                "--mc-dir", str(mock_mc_dir_legacy),
                "--data-dir", str(mock_data_dir),
                "--out", str(out),
            ])
        assert not (out / "data_mc_comparison.json").exists()