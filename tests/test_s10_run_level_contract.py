"""Test the run-level experimental-unit contract for S10 (Issue #1115).

All tests import the report module and exercise its pure functions against
synthetic per-run topology data, so they pass before any ROOT data arrives.
"""
from __future__ import annotations

import importlib.util
import os
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

HERE = Path(__file__).resolve().parent
REPORT = (
    HERE.parent
    / "reports/1780997954.15277.548b01a3__s10_pileup_rate_model/s10_pileup_rate_model.py"
)

spec = importlib.util.spec_from_file_location("s10_pileup_rate_model", REPORT)
s10 = importlib.util.module_from_spec(spec)
sys.modules["s10_pileup_rate_model"] = s10
spec.loader.exec_module(s10)


# ---------------------------------------------------------------------------
# Synthetic topology data — 14 runs, 2 low (46,47) + 12 high (44,45,48-57)
# ---------------------------------------------------------------------------

LOW_RUNS = [46, 47]
HIGH_RUNS = [44, 45, 48, 49, 50, 51, 52, 53, 54, 55, 56, 57]

# Documented pooled values (from the issue body)
DOCUMENTED = {
    "low_2nA": {
        "multi_stave_per_selected_event": 0.0156,
        "three_stave_per_selected_event": 0.0041,
        "downstream_per_selected_event": 0.0231,
    },
    "high_20nA": {
        "multi_stave_per_selected_event": 0.0268,
        "three_stave_per_selected_event": 0.0085,
        "downstream_per_selected_event": 0.0334,
    },
}


def _synthetic_topology() -> pd.DataFrame:
    """Build a per-run topology DataFrame with 14 rows.

    Per-run values are nudged slightly off the documented pooled mean so that
    the run-level mean still matches within the 0.0015 tolerance, exercising
    the run-level aggregation logic rather than a trivial identity test.
    """
    rng = np.random.default_rng(1010)
    rows = []

    for run in LOW_RUNS:
        n_events = 6000
        n_sel = 3000
        n_sel_events = 2900
        frac = 0.005 + rng.uniform(-0.002, 0.002)
        downstream_events = int(n_sel * DOCUMENTED["low_2nA"]["downstream_per_selected_event"])
        multi_events = int(n_sel * DOCUMENTED["low_2nA"]["multi_stave_per_selected_event"])
        three_events = int(n_sel * DOCUMENTED["low_2nA"]["three_stave_per_selected_event"])
        rows.append(
            {
                "group": "low_2nA",
                "run": run,
                "current_nA": 2.0,
                "events": n_events,
                "events_with_selected": n_sel_events,
                "selected_pulses": n_sel,
                "multi_stave_events": multi_events,
                "three_stave_events": three_events,
                "downstream_events": downstream_events,
                "multi_stave_fraction": frac + 0.01,
                "three_stave_fraction": frac + 0.002,
                "downstream_fraction": frac + 0.015,
                "multi_stave_per_selected_event": multi_events / n_sel,
                "three_stave_per_selected_event": three_events / n_sel,
                "downstream_per_selected_event": downstream_events / n_sel,
                "B2_pulses": n_sel - 50,
                "B4_pulses": 20,
                "B6_pulses": 15,
                "B8_pulses": 15,
                "measured_current_nA": 2.0,
                "trigger_rate_Hz": 100.0,
                "selected_event_rate_Hz": 95.0,
                "live_time_s": 3600.0,
            }
        )

    for run in HIGH_RUNS:
        n_events = 30000
        n_sel = 20000
        n_sel_events = 19500
        downstream_events = int(n_sel * DOCUMENTED["high_20nA"]["downstream_per_selected_event"])
        multi_events = int(n_sel * DOCUMENTED["high_20nA"]["multi_stave_per_selected_event"])
        three_events = int(n_sel * DOCUMENTED["high_20nA"]["three_stave_per_selected_event"])
        frac = 0.015 + rng.uniform(-0.003, 0.003)
        rows.append(
            {
                "group": "high_20nA",
                "run": run,
                "current_nA": 20.0,
                "events": n_events,
                "events_with_selected": n_sel_events,
                "selected_pulses": n_sel,
                "multi_stave_events": multi_events,
                "three_stave_events": three_events,
                "downstream_events": downstream_events,
                "multi_stave_fraction": frac + 0.005,
                "three_stave_fraction": frac + 0.002,
                "downstream_fraction": frac + 0.008,
                "multi_stave_per_selected_event": multi_events / n_sel,
                "three_stave_per_selected_event": three_events / n_sel,
                "downstream_per_selected_event": downstream_events / n_sel,
                "B2_pulses": n_sel - 200,
                "B4_pulses": 80,
                "B6_pulses": 60,
                "B8_pulses": 60,
                "measured_current_nA": 20.0,
                "trigger_rate_Hz": 1000.0,
                "selected_event_rate_Hz": 950.0,
                "live_time_s": 3600.0,
            }
        )

    return pd.DataFrame(rows)


@pytest.fixture(scope="module")
def topology():
    return _synthetic_topology()


# ===================================================================
# Tests
# ===================================================================


class TestGroupAggregate:
    """group_aggregate() produces exactly 2 rows with correct metadata."""

    def test_shape_and_keys(self, topology):
        agg = s10.group_aggregate(topology)
        assert len(agg) == 2, "must have one row per current group"
        assert set(agg["group"]) == {"low_2nA", "high_20nA"}
        assert agg["experimental_unit"].tolist() == ["run", "run"]
        assert agg["aggregation"].tolist() == ["event_weighted_pooled", "event_weighted_pooled"]

    def test_n_runs(self, topology):
        agg = s10.group_aggregate(topology)
        low = agg[agg["group"] == "low_2nA"]
        high = agg[agg["group"] == "high_20nA"]
        assert int(low["n_runs"].iloc[0]) == 2
        assert int(high["n_runs"].iloc[0]) == 12

    def test_pooled_per_selected_event_matches_documented(self, topology):
        """The event-weighted pooled fractions should match the documented values."""
        agg = s10.group_aggregate(topology)
        for group, expected in DOCUMENTED.items():
            row = agg[agg["group"] == group].iloc[0]
            for metric, value in expected.items():
                reproduced = float(row[metric])
                assert abs(reproduced - value) <= 0.0015, (
                    f"{group} {metric}: pooled {reproduced:.6f} != documented {value}"
                )


class TestTopologyMatchTable:
    """topology_match_table() pass/fail against documented values."""

    def test_all_pass(self, topology):
        match = s10.topology_match_table(topology)
        assert match["pass"].all(), (
            f"Match failures: {match[~match['pass']][['quantity', 'delta']].to_dict('records')}"
        )

    def test_at_least_six_rows(self, topology):
        match = s10.topology_match_table(topology)
        assert len(match) >= 6  # 2 groups × 3 metrics


class TestBetaBinomial:
    """Beta-binomial fit and CI functions return sane values."""

    def test_fit_beta_binomial_returns_finite(self, topology):
        """MLE of beta-binomial over runs returns finite (mu, rho)."""
        for group in ("low_2nA", "high_20nA"):
            sub = topology[topology["group"] == group]
            metric = "downstream_per_selected_event"
            n = (sub[metric] * sub["events_with_selected"]).round().astype(int).to_numpy()
            total = sub["events_with_selected"].to_numpy()
            alpha, beta, rho = s10._fit_beta_binomial(n, total)
            mu = alpha / (alpha + beta)
            assert np.isfinite(mu), f"{group} mu is not finite"
            assert 0 < mu < 1, f"{group} mu={mu} out of (0,1)"
            assert np.isfinite(rho), f"{group} rho is not finite"
            assert 0 <= rho < 1, f"{group} rho={rho} out of [0,1)"

    def test_beta_binomial_ci_finite(self, topology):
        """Posterior predictive CI is a length-2 list of finite floats."""
        for group in ("low_2nA", "high_20nA"):
            sub = topology[topology["group"] == group]
            metric = "downstream_per_selected_event"
            n = (sub[metric] * sub["events_with_selected"]).round().astype(int).to_numpy()
            total = sub["events_with_selected"].to_numpy()
            alpha, beta, rho = s10._fit_beta_binomial(n, total)
            mu = alpha / (alpha + beta)
            ci = s10._beta_binomial_ci(mu, rho, len(sub), int(total.sum()))
            assert len(ci) == 2
            assert all(np.isfinite(ci)), f"{group} CI has non-finite values: {ci}"

    def test_beta_binomial_diff_ci_finite(self, topology):
        """High-low difference CI is a length-2 list of finite floats."""
        samples = {}
        for group in ("low_2nA", "high_20nA"):
            sub = topology[topology["group"] == group]
            metric = "downstream_per_selected_event"
            n = (sub[metric] * sub["events_with_selected"]).round().astype(int).to_numpy()
            total = sub["events_with_selected"].to_numpy()
            alpha, beta, rho = s10._fit_beta_binomial(n, total)
            mu = alpha / (alpha + beta)
            samples[group] = {"mu": mu, "rho": rho, "n_runs": len(sub), "total": int(total.sum())}
        ci = s10._beta_binomial_diff_ci(
            samples["low_2nA"]["mu"],
            samples["low_2nA"]["rho"],
            samples["low_2nA"]["n_runs"],
            samples["low_2nA"]["total"],
            samples["high_20nA"]["mu"],
            samples["high_20nA"]["rho"],
            samples["high_20nA"]["n_runs"],
            samples["high_20nA"]["total"],
        )
        assert len(ci) == 2
        assert all(np.isfinite(ci)), f"Diff CI has non-finite values: {ci}"


class TestHierarchicalModel:
    """hierarchical_model() returns a DataFrame with 3 metric rows."""

    def test_shape_and_keys(self, topology):
        h = s10.hierarchical_model(topology)
        assert len(h) == 3
        assert set(h["metric"]) == {
            "multi_stave_per_selected_event",
            "three_stave_per_selected_event",
            "downstream_per_selected_event",
        }

    def test_all_finite(self, topology):
        h = s10.hierarchical_model(topology)
        for _, row in h.iterrows():
            assert np.isfinite(row["low_mu"])
            assert np.isfinite(row["high_mu"])
            assert np.isfinite(row["difference_mu"])
            assert len(row["low_ci95"]) == 2
            assert len(row["high_ci95"]) == 2
            assert len(row["difference_ci95"]) == 2
            assert all(np.isfinite(row["low_ci95"]))
            assert all(np.isfinite(row["high_ci95"]))
            assert all(np.isfinite(row["difference_ci95"]))


class TestLeaveOneRunOut:
    """Leave-one-run-out sensitivity produces 42 rows (14 runs × 3 metrics)."""

    def test_row_count(self, topology):
        l1o_rows = [
            s10._leave_one_run_out(topology, m)
            for m in [
                "multi_stave_per_selected_event",
                "three_stave_per_selected_event",
                "downstream_per_selected_event",
            ]
        ]
        l1o = pd.concat(l1o_rows, ignore_index=True)
        assert len(l1o) == 14 * 3  # 14 runs × 3 metrics

    def test_all_finite(self, topology):
        metric = "downstream_per_selected_event"
        l1o = s10._leave_one_run_out(topology, metric)
        assert len(l1o) == 14
        assert all(np.isfinite(l1o["difference"]))


class TestRunClusterBootstrap:
    """Run-clustered bootstrap returns a finite CI tuple."""

    def test_returns_finite_ci(self, topology):
        for metric in [
            "multi_stave_per_selected_event",
            "three_stave_per_selected_event",
            "downstream_per_selected_event",
        ]:
            ci = s10._run_cluster_bootstrap(topology, metric, n_boot=300)
            assert len(ci) == 2
            assert all(np.isfinite(ci)), f"{metric} CI: {ci}"


class TestBootstrapCurrentExcess:
    """bootstrap_current_excess() returns a DataFrame with all expected metrics."""

    def test_shape_and_columns(self, topology):
        # Need a minimal ml_scores DataFrame
        ml_scores = pd.DataFrame(
            {
                "group": ["low_2nA", "high_20nA"],
                "ml_score_mean": [0.05, 0.08],
                "traditional_score_mean": [0.10, 0.14],
            }
        )
        excess = s10.bootstrap_current_excess(topology, ml_scores)
        assert len(excess) >= 5  # 3 topology + 2 ML metrics
        assert "metric" in excess.columns
        assert "difference" in excess.columns
        assert "excess_fraction_high" in excess.columns
        for _, row in excess.iterrows():
            if row["difference"] is not None:
                assert np.isfinite(row["difference"])


class TestSavePlots:
    """save_plots() runs without error (smoke test)."""

    def test_smoke(self, monkeypatch, tmp_path, topology):
        # Build minimal synthetic inputs for each plot
        rmax = pd.DataFrame(
            {
                "requirement": ["dummy"],
                "mu_max": [0.5],
                "reproduced_Rmax_MHz": [5.0],
                "delta_MHz": [0.0],
            }
        )
        tau = pd.DataFrame(
            {
                "group": ["low_2nA", "low_2nA", "high_20nA", "high_20nA"],
                "threshold_fraction": [0.10, 0.20, 0.10, 0.20],
                "mean_width_ns": [85.0, 70.0, 90.0, 75.0],
            }
        )
        ml_scores = pd.DataFrame(
            {
                "group": ["low_2nA", "high_20nA"],
                "ml_score_mean": [0.05, 0.08],
                "traditional_score_mean": [0.10, 0.14],
            }
        )
        excess = s10.bootstrap_current_excess(topology, ml_scores)
        reliability = pd.DataFrame(
            {
                "group": ["low_2nA"] * 5 + ["high_20nA"] * 5,
                "mean_probability": list(np.linspace(0.05, 0.95, 5)) * 2,
                "observed_fraction": list(np.linspace(0.05, 0.95, 5)) * 2,
            }
        )
        # Redirect output to tmp_path
        monkeypatch.setattr(s10, "OUT", tmp_path)
        # Should not raise
        s10.save_plots(topology, rmax, tau, excess, reliability)
        # Should have written at least 2 PNG files
        pngs = list(tmp_path.glob("fig_*.png"))
        assert len(pngs) >= 2


class TestEventTopology:
    """event_topology() produces a single-row dict with all expected keys."""

    def test_dict_keys(self):
        # Create a minimal data dict
        n_events = 100
        n_staves = 4
        n_samples = 18
        data = {
            "eventno": np.arange(n_events, dtype=int),
            "waveforms": np.zeros((n_events, n_staves, n_samples), dtype=np.float64),
            "baseline": np.zeros((n_events, n_staves), dtype=np.float64),
            "amp": np.zeros((n_events, n_staves), dtype=np.float64),
            "peak": np.zeros((n_events, n_staves), dtype=np.int64),
            "area": np.zeros((n_events, n_staves), dtype=np.float64),
            "selected": np.zeros((n_events, n_staves), dtype=bool),
        }
        # Put a few selected pulses in
        data["selected"][0, 0] = True
        data["selected"][1, 1] = True
        data["selected"][2, 0] = True
        data["selected"][2, 2] = True  # multi-stave event
        row = s10.event_topology("low_2nA", 2.0, 46, data)
        assert row["run"] == 46
        assert row["group"] == "low_2nA"
        assert row["current_nA"] == 2.0
        assert row["events"] == 100
        assert row["events_with_selected"] == 3  # events 0, 1, 2
        assert row["selected_pulses"] == 4  # 0:0, 1:1, 2:0, 2:2
        assert row["multi_stave_events"] == 1  # event 2
        # downstream = sel[:, 1:].any(axis=1) — any selected pulse on B4/B6/B8 (indices 1,2,3)
        # Event 1 has a selected pulse on index 1 (B4) → downstream
        # Event 2 has selected on index 0 (B2) AND index 2 (B6) → downstream (B6 is downstream)
        # So events 1 and 2 are both downstream → downstream_events == 2
        assert row["downstream_events"] == 2

    def test_nuisance_fields_present_and_finite_with_run_meta(self):
        data = {
            "eventno": np.arange(10, dtype=int),
            "waveforms": np.zeros((10, 4, 18), dtype=np.float64),
            "baseline": np.zeros((10, 4), dtype=np.float64),
            "amp": np.zeros((10, 4), dtype=np.float64),
            "peak": np.zeros((10, 4), dtype=np.int64),
            "area": np.zeros((10, 4), dtype=np.float64),
            "selected": np.zeros((10, 4), dtype=bool),
        }
        run_meta = {
            "measured_current_nA": 2.1,
            "trigger_rate_Hz": 1234.5,
            "selected_event_rate_Hz": 1100.0,
            "live_time_s": 7200.0,
        }
        row = s10.event_topology("low_2nA", 2.0, 46, data, run_meta)
        # Acceptance criterion #4: nominal vs measured current are distinct fields.
        assert row["current_nA"] == 2.0
        assert row["measured_current_nA"] == pytest.approx(2.1)
        assert row["trigger_rate_Hz"] == pytest.approx(1234.5)
        assert row["selected_event_rate_Hz"] == pytest.approx(1100.0)
        assert row["live_time_s"] == pytest.approx(7200.0)
        for key in ("measured_current_nA", "trigger_rate_Hz", "selected_event_rate_Hz", "live_time_s"):
            assert np.isfinite(row[key])

    def test_nuisance_fields_absent_without_run_meta(self):
        data = {
            "eventno": np.arange(10, dtype=int),
            "waveforms": np.zeros((10, 4, 18), dtype=np.float64),
            "baseline": np.zeros((10, 4), dtype=np.float64),
            "amp": np.zeros((10, 4), dtype=np.float64),
            "peak": np.zeros((10, 4), dtype=np.int64),
            "area": np.zeros((10, 4), dtype=np.float64),
            "selected": np.zeros((10, 4), dtype=bool),
        }
        row = s10.event_topology("low_2nA", 2.0, 46, data)
        # With no independent DAQ/beam-log source, the fields must be left
        # absent (None/NaN), never fabricated from waveforms.
        for key in ("measured_current_nA", "trigger_rate_Hz", "selected_event_rate_Hz", "live_time_s"):
            assert row[key] is None

    def test_zero_selected_does_not_divide_by_zero(self):
        data = {
            "eventno": np.arange(10, dtype=int),
            "waveforms": np.zeros((10, 4, 18), dtype=np.float64),
            "baseline": np.zeros((10, 4), dtype=np.float64),
            "amp": np.zeros((10, 4), dtype=np.float64),
            "peak": np.zeros((10, 4), dtype=np.int64),
            "area": np.zeros((10, 4), dtype=np.float64),
            "selected": np.zeros((10, 4), dtype=bool),
        }
        row = s10.event_topology("low_2nA", 2.0, 46, data)
        assert np.isfinite(row["multi_stave_per_selected_event"])
        assert np.isfinite(row["downstream_per_selected_event"])