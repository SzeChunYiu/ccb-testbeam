"""Tests for the Phase-3 overlay production (mc03) and honest benchmark (s24).

Review-driven assertions (EXTERNAL_REVIEW_2026-07-02.md P8):
  * overlaying two known hit groups produces two pulses at the right samples,
  * the injected dt is CONTINUOUS (no grid quantization),
  * single-pulse negatives carry no second pulse,
  * the failure definition is a single shared function, symmetric between the
    traditional fit and the ML method.
"""
from __future__ import annotations

import gzip
import importlib.util
import sys
from pathlib import Path

import numpy as np
import pytest

ROOT = Path(__file__).resolve().parents[1]


def _load_script(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


mc03 = _load_script("mc03_build_overlay_sample", ROOT / "scripts" / "mc03_build_overlay_sample.py")
s24 = _load_script("s24_two_pulse_honest_benchmark", ROOT / "scripts" / "s24_two_pulse_honest_benchmark.py")

from ccb_mc_validation.digitizer.pipeline import DigitizerPipeline, load_digitizer_card

CARD = load_digitizer_card(ROOT / "configs" / "mc_validation" / "digitizer_card.yaml")


def _noiseless_pipeline(stave: str = "B2") -> DigitizerPipeline:
    pipe = DigitizerPipeline.from_config(CARD, stave=stave)
    pipe.electronics.noise_adc_rms = 0.0
    pipe.transport_sigma_ns = 0.0
    return pipe


def _local_maxima(net: np.ndarray, min_frac: float = 0.05) -> list[int]:
    """Indices of strict local maxima above min_frac of the global peak."""
    peaks = []
    thresh = min_frac * net.max()
    for i in range(1, len(net) - 1):
        if net[i] > thresh and net[i] >= net[i - 1] and net[i] > net[i + 1]:
            peaks.append(i)
    if len(net) >= 2 and net[-1] > thresh and net[-1] > net[-2]:
        peaks.append(len(net) - 1)
    return peaks


def _group(edep, trel, src_event=0, stave="B2"):
    return {
        "src_event": src_event,
        "stave": stave,
        "edep": np.asarray(edep, dtype=float),
        "trel": np.asarray(trel, dtype=float),
        "edep_tot_mev": float(np.sum(edep)),
        "amp_nom_adc": 0.0,
        "n_hits": len(edep),
        "sample_I": 1,
        "sample_II": 1,
    }


def test_two_pulse_overlay_produces_two_peaks_at_right_samples():
    """Overlay of two known single-hit groups shows local maxima exactly where
    each pulse alone peaks (this is the observable the Phase-1 sampling fix
    restored: hit-time offsets must shift the sampled pulse)."""
    pipe = _noiseless_pipeline("B2")
    ped = pipe.electronics.pedestal_adc
    g1 = _group([20.0], [0.0])
    g2 = _group([20.0], [0.0])
    dt = 70.0  # second pulse at 120 ns

    alone1 = np.asarray(
        pipe.run(mc03.group_hits(g1, mc03.T1_NS), event_id=0, channel=0)["adc"], float
    ) - ped
    alone2 = np.asarray(
        pipe.run(mc03.group_hits(g2, mc03.T1_NS + dt), event_id=0, channel=0)["adc"], float
    ) - ped
    both = np.asarray(
        mc03.digitize_record(pipe, g1, g2, dt, record_id=0, channel=0, seed_salt=0)["adc"],
        float,
    ) - ped

    p1, p2 = int(alone1.argmax()), int(alone2.argmax())
    assert p1 != p2, "constituent pulses must peak at different samples"
    # expected phases: onset 50 ns -> peak in samples 5-7; onset 120 ns -> 12-14
    assert 5 <= p1 <= 7
    assert 12 <= p2 <= 14
    peaks = _local_maxima(both)
    assert p1 in peaks, f"first pulse peak {p1} missing from overlay maxima {peaks}"
    assert p2 in peaks, f"second pulse peak {p2} missing from overlay maxima {peaks}"
    # linearity of the analog overlay (noise off): sum of constituents
    np.testing.assert_allclose(both, alone1 + alone2, atol=1.0)


def test_dt_is_continuous_no_grid_quantization():
    rng = np.random.default_rng(123)
    for rate_mhz in (0.5, 1.5, 3.0):
        dt = mc03.draw_truncated_exponential(rng, 1000.0 / rate_mhz, 130.0, size=5000)
        assert np.all(dt > 0.0) and np.all(dt <= 130.0)
        assert np.unique(dt).size >= 4995, "dt draws must be continuous"
        for grid in (2.5, 5.0, 10.0):  # the old S11a-style separation grids
            on_grid = np.isclose(dt % grid, 0.0, atol=1e-9) | np.isclose(dt % grid, grid, atol=1e-9)
            assert on_grid.sum() < 5, f"dt clustered on a {grid} ns grid"


def test_single_pulse_negative_has_no_second_peak():
    pipe = _noiseless_pipeline("B4")
    ped = pipe.electronics.pedestal_adc
    g1 = _group([15.0], [0.0], stave="B4")
    rec = mc03.digitize_record(pipe, g1, None, float("nan"), record_id=1, channel=1, seed_salt=0)
    net = np.asarray(rec["adc"], float) - ped
    peaks = _local_maxima(net)
    assert len(peaks) == 1, f"negative record must have exactly one pulse, got maxima {peaks}"
    peak = peaks[0]
    tail = net[peak:]
    assert np.all(np.diff(tail) <= 1.0), "single pulse must decay monotonically after its peak"


def test_generate_rate_sample_schema_and_negatives(tmp_path):
    """End-to-end mini production from a synthetic pool: schema, overlap
    fraction, continuous dt in the file, and blank truth for negatives."""
    rng = np.random.default_rng(7)
    pools = {s: [[], []] for s in mc03.STAVES}
    for s in mc03.STAVES:
        for parity in (0, 1):
            for i in range(12):
                pools[s][parity].append(
                    _group([10.0 + 5.0 * rng.random()], [0.0], src_event=2 * i + parity, stave=s)
                )
    pipelines = {s: DigitizerPipeline.from_config(CARD, stave=s) for s in mc03.STAVES}
    dig_params = mc03.stave_digitizer_params(CARD)
    weights = {s: 1.0 for s in mc03.STAVES}
    out = tmp_path / "mc03_overlay_rate1.5MHz.csv.gz"
    meta = mc03.generate_rate_sample(
        rate_mhz=1.5, n_records=400, overlap_fraction=0.7, pools=pools,
        stave_weights=weights, pipelines=pipelines, dig_params=dig_params,
        out_path=out, rate_index=0, dt_max_ns=130.0,
    )
    assert meta["n_records"] == 400
    assert 0.60 < meta["overlap_fraction_realized"] < 0.80
    with gzip.open(out, "rt") as handle:
        header = handle.readline().strip().split(",")
        rows = [line.strip().split(",") for line in handle]
    assert header[: len(mc03.META_COLUMNS.split(","))] == mc03.META_COLUMNS.split(",")
    assert header[-1] == "s17"
    col = {name: k for k, name in enumerate(header)}
    dts = []
    for r in rows:
        if r[col["is_overlap"]] == "1":
            dts.append(float(r[col["dt_true_ns"]]))
            assert float(r[col["amp2_true_adc"]]) > 0.0
        else:
            assert r[col["dt_true_ns"]] == ""
            assert r[col["src_event2"]] == "-1"
            assert float(r[col["amp2_true_adc"]]) == 0.0
        assert r[col["split"]] in ("train", "eval")
    dts = np.asarray(dts)
    assert np.unique(dts).size == len(dts), "file dt values must be continuous (all unique)"
    assert dts.max() <= 130.0


def test_failure_definition_is_single_and_symmetric():
    """Review P8: the old benchmark used different failure definitions per
    method. Here both methods must flow through the SAME function with the
    SAME tolerance, and evaluate_method must be method-name-blind."""
    assert s24.FAILURE_DT_TOL_NS == 15.0
    rng = np.random.default_rng(42)
    n = 400
    score = rng.normal(0.5, 0.2, size=n)
    dt_true = rng.uniform(0.0, 130.0, size=n)
    dt_rec = dt_true + rng.normal(0.0, 8.0, size=n)
    theta = 0.4

    flags = s24.failure_flags(score, theta, dt_rec, dt_true)
    # definition: miss OR |err| > 15, nothing method-specific
    expected = ~((score >= theta) & (np.abs(dt_rec - dt_true) <= 15.0))
    np.testing.assert_array_equal(flags, expected)
    # NaN dt is always a failure even when detected
    f_nan = s24.failure_flags(np.array([1.0]), theta, np.array([np.nan]), np.array([50.0]))
    assert bool(f_nan[0])

    res_a = s24.evaluate_method("trad", score, dt_rec, dt_true, theta, rng=None)
    res_b = s24.evaluate_method("ml", score, dt_rec, dt_true, theta, rng=None)
    res_a.pop("method"), res_b.pop("method")
    assert res_a == res_b, "evaluation must be identical for identical inputs regardless of method label"


def test_risk_coverage_and_threshold_are_shared_machinery():
    rng = np.random.default_rng(3)
    conf = rng.random(1000)
    failed = rng.random(1000) < 0.2
    curve = s24.risk_coverage_curve(conf, failed)
    assert len(curve) == 1000
    assert curve["coverage"].iloc[-1] == pytest.approx(1.0)
    assert curve["risk"].iloc[-1] == pytest.approx(failed.mean())
    # identical matched-operating-point procedure for any method's scores
    neg = rng.normal(0.0, 1.0, size=5000)
    th = s24.detection_threshold(neg, fpr=0.10)
    assert 0.05 < np.mean(neg >= th) < 0.15


def test_card_kernel_template_peaks_track_onset():
    """The fit template must move with the hypothesis time (the C1 regression
    made hit time a no-op; the fitter depends on the fixed behaviour)."""
    rows = s24.kernel_template_rows(np.array([50.0, 90.0, 130.0]), 2.5, 56.7)
    assert rows.shape == (3, 18)
    peaks = rows.argmax(axis=1)
    assert peaks[0] < peaks[1] < peaks[2]
    np.testing.assert_allclose(rows.max(axis=1), 1.0)
