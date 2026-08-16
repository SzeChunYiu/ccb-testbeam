"""Tests for the refactored MV4 toy-diagnostic timing study.

Covers: pure metric functions, --strict / fallback calibration behaviour,
a deterministic synthetic end-to-end run, and --data-anchors override.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys

import numpy as np
import pytest

SCRIPTS = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "scripts")
if SCRIPTS not in sys.path:
    sys.path.insert(0, SCRIPTS)

import mv4_timing_study as mv4  # noqa: E402

SCRIPT = os.path.join(SCRIPTS, "mv4_timing_study.py")


# --------------------------------------------------------------------------
# Metric pure functions
# --------------------------------------------------------------------------
def test_sigma68_known_array():
    # symmetric spread: p16=-1, p84=+1 -> sigma68 = 1.0
    x = np.linspace(-3, 3, 10001)
    lo, hi = np.percentile(x, [16, 84])
    s = mv4.sigma68(x)
    assert s == pytest.approx((hi - lo) / 2.0)
    assert abs(s - 2.04) < 0.02
    # exact small case
    arr = np.array([-2.0, -1.0, 0.0, 1.0, 2.0, -1.0, 1.0])
    lo, hi = np.percentile(arr, [16, 84])
    assert mv4.sigma68(arr) == pytest.approx((hi - lo) / 2.0)
    assert np.isnan(mv4.sigma68([1.0, 2.0]))  # too few


def test_gaussian_core_sigma_recovers_clean_gaussian():
    rng = np.random.default_rng(7)
    x = rng.normal(0.0, 2.5, 40000)
    sig = mv4.gaussian_core_sigma(x)
    assert abs(sig - 2.5) < 0.15


def test_rms_matches_std():
    rng = np.random.default_rng(3)
    x = rng.normal(1.0, 4.0, 20000)
    assert mv4.rms(x) == pytest.approx(np.std(x), rel=1e-9)


def test_tail_fraction_increases_with_outliers():
    rng = np.random.default_rng(11)
    clean = rng.normal(0.0, 1.0, 20000)
    base = mv4.tail_fraction(clean, n_sigma=3.0)
    # inject heavy outliers at +/-12 sigma
    outliers = np.concatenate([clean, rng.uniform(10, 15, 800) * rng.choice([-1, 1], 800)])
    with_out = mv4.tail_fraction(outliers, n_sigma=3.0)
    assert with_out > base
    assert with_out > 0.02


def test_chi2_ndf_sane_for_gaussian():
    rng = np.random.default_rng(5)
    x = rng.normal(0.0, 1.5, 50000)
    chi2, ndf, cn = mv4.chi2_ndf(x)
    assert np.isfinite(chi2) and ndf > 0
    assert np.isfinite(cn) and 0.0 < cn < 5.0


def test_loro_spread_structure():
    rng = np.random.default_rng(9)
    x = rng.normal(0, 1, 5000)
    runs = rng.choice(["r0", "r1", "r2", "r3"], size=5000)
    out = mv4.loro_spread(x, runs)
    assert out["n_runs"] == 4
    assert len(out["per_run"]) == 4
    assert np.isfinite(out["leave_one_run_out"]["std_ns"])


# --------------------------------------------------------------------------
# --strict / fallback calibration behaviour
# --------------------------------------------------------------------------
def _run(args, cwd):
    return subprocess.run([sys.executable, SCRIPT, *args], cwd=cwd,
                          capture_output=True, text=True)


def test_strict_no_calibration_errors(tmp_path):
    out = tmp_path / "strict_out"
    r = _run(["--synthetic", "300", "--out", str(out), "--strict"], tmp_path)
    assert r.returncode != 0, r.stdout + r.stderr
    # must NOT have silently produced a result using the 246 fallback
    assert not (out / "result.json").exists()
    assert "STRICT ERROR" in (r.stdout + r.stderr)


def test_nonstrict_warns_and_flags_fallback(tmp_path):
    out = tmp_path / "fb_out"
    r = _run(["--synthetic", "600", "--out", str(out), "--seed", "20260720"], tmp_path)
    assert r.returncode == 0, r.stdout + r.stderr
    assert "WARNING" in r.stderr
    res = json.loads((out / "result.json").read_text())
    assert res["calibration_source"] == "fallback"
    assert res["data_anchors_source"] == "fallback"
    assert res["digitizer_params"]["gain_adc_per_mev"] == mv4.DEFAULT_GAIN_ADC_PER_MEV


# --------------------------------------------------------------------------
# Synthetic end-to-end + determinism + slices
# --------------------------------------------------------------------------
def test_synthetic_end_to_end_and_determinism(tmp_path):
    common = ["--synthetic", "800", "--seed", "424242", "--slice-by", "species,amplitude,run"]
    out1 = tmp_path / "e2e1"
    out2 = tmp_path / "e2e2"
    r1 = _run([*common, "--out", str(out1)], tmp_path)
    r2 = _run([*common, "--out", str(out2)], tmp_path)
    assert r1.returncode == 0, r1.stdout + r1.stderr
    assert r2.returncode == 0, r2.stdout + r2.stderr

    res1 = json.loads((out1 / "result.json").read_text())
    res2 = json.loads((out2 / "result.json").read_text())

    # raw + corrected sigma68 present
    assert res1["status"] == "TOY_DIAGNOSTIC"
    assert np.isfinite(res1["metrics_global"]["raw"]["sigma68_ns"])
    assert np.isfinite(res1["metrics_global"]["corrected_test_half"]["sigma68_ns"])

    # at least one slice table with rows
    assert res1["slices"], "no slices produced"
    assert any(len(v) > 0 for v in res1["slices"].values())

    # slice CSV written with a header + rows
    csv_txt = (out1 / "mv4_slice_metrics.csv").read_text().strip().splitlines()
    assert csv_txt[0].startswith("slice_dim,slice_value,n")
    assert len(csv_txt) > 1

    # deterministic: same seed -> identical key metrics
    assert res1["metrics_global"]["raw"]["sigma68_ns"] == res2["metrics_global"]["raw"]["sigma68_ns"]
    assert res1["sigma68_ns"]["corrected_test_half"] == res2["sigma68_ns"]["corrected_test_half"]
    assert res1["timewalk_fit"]["B_ns_ADC"] == res2["timewalk_fit"]["B_ns_ADC"]

    # LORO present (synthetic has multiple runs)
    assert res1["loro_raw"] is not None
    assert res1["loro_raw"]["n_runs"] >= 2


def test_data_anchors_override(tmp_path):
    anchors = {
        "S02_raw": {"sigma68_ns": 2.22, "unc_ns": 0.05, "ci68": [2.17, 2.27]},
        "S03_corrected": {"sigma68_ns": 1.11, "unc_ns": 0.04, "ci68": [1.07, 1.15]},
    }
    apath = tmp_path / "anchors.json"
    apath.write_text(json.dumps(anchors))
    out = tmp_path / "anch_out"
    r = _run(["--synthetic", "600", "--out", str(out), "--data-anchors", str(apath)], tmp_path)
    assert r.returncode == 0, r.stdout + r.stderr
    res = json.loads((out / "result.json").read_text())
    assert res["data_anchors_source"] == os.path.abspath(str(apath))
    assert res["data_anchors"]["S02_raw_sigma68_ns"] == 2.22
    assert res["data_anchors"]["S03_corrected_sigma68_ns"] == 1.11
    # the loaded anchors (not the 1.85/1.50 fallback) drive the pull
    assert res["data_anchors"]["S02_raw_sigma68_ns"] != mv4.FALLBACK_DATA_ANCHORS["S02_raw_sigma68_ns"]


def test_calibration_loaded_source_and_gain(tmp_path):
    calib = {"study_id": "MV0", "calibration": {"gain_adc_per_mev": 300.0,
             "gain_adc_per_mev_unc": 12.0}}
    cpath = tmp_path / "calibration.json"
    cpath.write_text(json.dumps(calib))
    out = tmp_path / "cal_out"
    r = _run(["--synthetic", "600", "--out", str(out), "--calibration", str(cpath)], tmp_path)
    assert r.returncode == 0, r.stdout + r.stderr
    res = json.loads((out / "result.json").read_text())
    assert res["calibration_source"] == "loaded"
    assert res["digitizer_params"]["gain_adc_per_mev"] == 300.0
    assert res["calibration"]["gain_adc_per_mev_unc"] == 12.0
    # gain uncertainty propagated
    assert res["gain_propagation"] is not None
    assert "gain_lo" in res["gain_propagation"] and "gain_hi" in res["gain_propagation"]


def test_cli_help_runs():
    r = subprocess.run([sys.executable, SCRIPT, "--help"], capture_output=True, text=True)
    assert r.returncode == 0
    for flag in ["--calibration", "--data-anchors", "--strict", "--slice-by",
                 "--synthetic", "--bootstrap-blocks"]:
        assert flag in r.stdout
