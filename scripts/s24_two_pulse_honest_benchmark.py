#!/usr/bin/env python3
"""
s24_two_pulse_honest_benchmark.py
=================================
Honest two-pulse benchmark on the mc03 truth-labelled overlay sample
(Phase 3, deliverable 2) + the first honest MC live-time (deliverable 3).

Fixes every rigging channel called out for the old S11a benchmark
(EXTERNAL_REVIEW_2026-07-02.md P8):
  1. Injection dt is CONTINUOUS (mc03, exponential law); the fit hypothesis
     grid is an independent fixed grid — no injection/fit grid identity.
  2. Fit templates come from the DIGITIZER CARD kernel (single-delta pulse
     shape of configs/mc_validation/digitizer_card.yaml), NOT from the
     injection sample. Circularity note: the card also drives the mc03
     generator, so the template shares the kernel FAMILY with the truth
     pulses by construction; what is broken relative to S11a is (i) templates
     are never fit to / averaged from the injected waveforms, (ii) injected
     pulses are multi-hit truth groups with per-hit transport smearing —
     genuinely off-template — and (iii) the ML method never sees templates.
  3. SINGLE failure definition for BOTH methods (``failure_flags``):
     missed detection OR |dt_rec - dt_true| > 15 ns.
  4. MATCHED evaluation: detection thresholds are set by the same procedure
     for both methods (score quantile at fixed false-positive rate on the
     TRAIN-split negatives); risk-coverage curves are swept on each method's
     own confidence, failure rates are compared at the SAME coverage (80%),
     and dt resolution (sigma68) is computed on the COMMON accepted subset.

Methods:
  (a) constrained two-pulse template fit — fit logic ported from
      scripts/s10d_two_pulse_resolvability_livetime.py (one-pulse vs two-pulse
      LSQ over a (t1, t2) hypothesis grid, amplitudes+baseline solved in
      closed form, positivity + baseline constraints; score = fractional SSE
      improvement), vectorized over records via precomputed 3x3 normal
      equations.
  (b) compact ML: sklearn HistGradientBoosting classifier (detection) +
      regressor (dt) on the raw 18 samples, trained on the mc03 train split
      (disjoint source events from eval by construction).

Deliverable 3: independent MC tau_eff on the digitized single-pulse records
with the S10b-style estimator (aligned median template, exponential tail fit,
10% crossing relative to CFD20 — ported from
reports/1781000867.546870.5c124aaf/s10b_tau_eff_template_fit.py), per stave
and pooled with bootstrap CIs, compared with the data value 124.79 ns. This
replaces the retracted MV5 "MC tau_eff" (review I2) with a number actually
measured on digitized MC pulses.

Outputs (in --out): REPORT.md, result.json, manifest.json,
risk_coverage_curves.csv, failure_at_coverage.csv, common_subset_sigma68.csv,
detection_metrics.csv, tau_eff_by_stave.csv, per-record predictions
(predictions_rate*.csv.gz), fig_mc03_benchmark.(png|svg|pdf).
"""
from __future__ import annotations

import argparse
import gzip
import hashlib
import json
import math
import sys
import time
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib as mpl
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

ROOT_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT_DIR / "src"))

from ccb_mc_validation.digitizer.pipeline import DEFAULT_CARD_PATH, load_digitizer_card
from ccb_mc_validation.digitizer.scintillation import exponential_kernel_cdf

# ----------------------------------------------------------------------------
# Shared benchmark contract (tested for symmetry in tests/test_mc03_overlay.py)
# ----------------------------------------------------------------------------
FAILURE_DT_TOL_NS = 15.0          # single tolerance, both methods
TARGET_COVERAGE = 0.80            # headline matched coverage
TRAIN_NEG_FPR = 0.10              # detection threshold: score quantile at this
                                  # false-positive rate on TRAIN-split negatives
DATA_TAU_EFF_NS = 124.79          # measured data live10 (S10b)
SEED = 2404
N_SAMPLES = 18
SPACING_NS = 10.0
STAVES = ("B2", "B4", "B6", "B8")

# Fit hypothesis grids — deliberately independent of the (continuous) mc03
# injection law (review P8). t1 near the 50 ns trigger phase; t2 anywhere.
T1_GRID = np.arange(38.0, 66.001, 0.5)
T2_GRID = np.arange(40.0, 176.001, 1.0)
T1P_GRID = np.arange(38.0, 170.001, 1.0)  # one-pulse fit grid
MIN_SEP_NS = 2.0
BASELINE_HALF_RANGE_ADC = 60.0


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def sigma68(values: np.ndarray) -> float:
    values = np.asarray(values, dtype=float)
    values = values[np.isfinite(values)]
    if len(values) == 0:
        return float("nan")
    q16, q84 = np.percentile(values, [16, 84])
    return float((q84 - q16) / 2.0)


def failure_flags(
    score: np.ndarray,
    theta: float,
    dt_rec: np.ndarray,
    dt_true: np.ndarray,
    tol_ns: float = FAILURE_DT_TOL_NS,
) -> np.ndarray:
    """THE single failure definition, applied identically to both methods.

    A true-overlap record fails when the method misses the detection
    (score < theta at the method's matched operating point) OR its recovered
    dt is absent/NaN OR off by more than ``tol_ns``.
    """
    score = np.asarray(score, dtype=float)
    dt_rec = np.asarray(dt_rec, dtype=float)
    dt_true = np.asarray(dt_true, dtype=float)
    detected = score >= theta
    dt_ok = np.isfinite(dt_rec) & (np.abs(dt_rec - dt_true) <= tol_ns)
    return ~(detected & dt_ok)


def detection_threshold(train_negative_scores: np.ndarray, fpr: float = TRAIN_NEG_FPR) -> float:
    """Matched operating point: identical procedure for both methods."""
    s = np.asarray(train_negative_scores, dtype=float)
    s = s[np.isfinite(s)]
    return float(np.quantile(s, 1.0 - fpr))


def risk_coverage_curve(conf: np.ndarray, failed: np.ndarray) -> pd.DataFrame:
    """Sweep the abstention threshold on the method's confidence.

    coverage(k) = fraction of positives kept when abstaining below the k-th
    highest confidence; risk(k) = failure fraction among the kept records.
    """
    conf = np.asarray(conf, dtype=float)
    conf = np.where(np.isfinite(conf), conf, -np.inf)
    order = np.argsort(-conf, kind="stable")
    f = np.asarray(failed, dtype=float)[order]
    n = len(f)
    coverage = np.arange(1, n + 1) / n
    risk = np.cumsum(f) / np.arange(1, n + 1)
    return pd.DataFrame({"coverage": coverage, "risk": risk})


def risk_at_coverage(conf: np.ndarray, failed: np.ndarray, coverage: float) -> float:
    curve = risk_coverage_curve(conf, failed)
    k = max(int(math.ceil(coverage * len(curve))) - 1, 0)
    return float(curve["risk"].iloc[k])


def evaluate_method(
    method: str,
    conf: np.ndarray,
    dt_rec: np.ndarray,
    dt_true: np.ndarray,
    theta: float,
    coverage: float = TARGET_COVERAGE,
    rng: np.random.Generator | None = None,
    n_boot: int = 500,
) -> dict:
    """Matched-coverage evaluation of ONE method on true-overlap records.

    Identical code path for both methods (symmetry requirement, review P8):
    the method name is a label only and enters no branch.
    """
    failed = failure_flags(conf, theta, dt_rec, dt_true)
    out = {
        "method": method,
        "n_positive": int(len(conf)),
        "theta": float(theta),
        "failure_rate_full": float(np.mean(failed)),
        f"failure_at_{int(coverage * 100)}pct_coverage": risk_at_coverage(conf, failed, coverage),
    }
    if rng is not None and n_boot > 0:
        vals = []
        idx = np.arange(len(conf))
        for _ in range(n_boot):
            b = rng.choice(idx, size=len(idx), replace=True)
            vals.append(risk_at_coverage(conf[b], failed[b], coverage))
        out["failure_ci_low"] = float(np.percentile(vals, 2.5))
        out["failure_ci_high"] = float(np.percentile(vals, 97.5))
    return out


# ----------------------------------------------------------------------------
# Constrained two-pulse template fit (ported from s10d, card-kernel templates)
# ----------------------------------------------------------------------------
def kernel_template_rows(
    t0_values: np.ndarray,
    tau_rise_ns: float,
    tau_decay_ns: float,
    n_samples: int = N_SAMPLES,
    spacing_ns: float = SPACING_NS,
) -> np.ndarray:
    """Unit-peak sampled pulse shape of the CARD kernel at continuous onsets."""
    t0 = np.asarray(t0_values, dtype=np.float64)
    edges = np.arange(n_samples + 1, dtype=np.float64) * spacing_ns
    cdf = exponential_kernel_cdf(edges[None, :] - t0[:, None], tau_rise_ns, tau_decay_ns)
    rows = np.diff(cdf, axis=1)
    peak = rows.max(axis=1)
    rows = rows / np.maximum(peak, 1e-12)[:, None]
    return rows


class TwoPulseFitter:
    """Vectorized constrained one/two-pulse LSQ fit against card templates.

    Design matrix per hypothesis (t1, t2): [template(t1), template(t2), 1].
    Amplitudes and baseline are solved by 3x3 normal equations (precomputed
    inverse per hypothesis pair); constraints a1>0, a2>0 and baseline within
    pedestal +- BASELINE_HALF_RANGE_ADC — the s10d constraint set MINUS the
    amplitude-ratio bounds (the mc03 injection has no ratio restriction, so
    the fit must not assume one).
    """

    def __init__(self, tau_rise_ns: float, tau_decay_ns: float, pedestal_adc: float):
        self.pedestal_adc = float(pedestal_adc)
        self.blo = self.pedestal_adc - BASELINE_HALF_RANGE_ADC
        self.bhi = self.pedestal_adc + BASELINE_HALF_RANGE_ADC
        self.T1 = kernel_template_rows(T1_GRID, tau_rise_ns, tau_decay_ns)
        self.T2 = kernel_template_rows(T2_GRID, tau_rise_ns, tau_decay_ns)
        self.T1p = kernel_template_rows(T1P_GRID, tau_rise_ns, tau_decay_ns)
        n = float(N_SAMPLES)

        pair_ok = T2_GRID[None, :] >= (T1_GRID[:, None] + MIN_SEP_NS)
        self.pair_i, self.pair_j = np.where(pair_ok)
        g11 = (self.T1 ** 2).sum(axis=1)
        g22 = (self.T2 ** 2).sum(axis=1)
        s1 = self.T1.sum(axis=1)
        s2 = self.T2.sum(axis=1)
        G12 = self.T1 @ self.T2.T
        a = g11[self.pair_i]
        b = G12[self.pair_i, self.pair_j]
        c = s1[self.pair_i]
        d = g22[self.pair_j]
        e = s2[self.pair_j]
        det = a * (d * n - e * e) - b * (b * n - e * c) + c * (b * e - d * c)
        good = np.abs(det) > 1e-8
        self.pair_i = self.pair_i[good]
        self.pair_j = self.pair_j[good]
        a, b, c, d, e, det = (x[good] for x in (a, b, c, d, e, det))
        self.i11 = (d * n - e * e) / det
        self.i12 = (c * e - b * n) / det
        self.i13 = (b * e - c * d) / det
        self.i22 = (a * n - c * c) / det
        self.i23 = (b * c - a * e) / det
        self.i33 = (a * d - b * b) / det

        g1p = (self.T1p ** 2).sum(axis=1)
        s1p = self.T1p.sum(axis=1)
        det1 = g1p * n - s1p * s1p
        self.op = {"g": g1p, "s": s1p, "det": det1, "n": n}

    def fit_one_pulse(self, Y: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
        yy = (Y * Y).sum(axis=1)
        py = Y.sum(axis=1)
        P = self.T1p @ Y.T  # (n_grid, B)
        g, s, det, n = self.op["g"], self.op["s"], self.op["det"], self.op["n"]
        a1 = (n * P - s[:, None] * py[None, :]) / det[:, None]
        bl = (g[:, None] * py[None, :] - s[:, None] * P) / det[:, None]
        sse = yy[None, :] - (a1 * P + bl * py[None, :])
        # s10d's one-pulse null model constrains ONLY the amplitude sign: a
        # baseline bound would make the null model infeasible on strong
        # overlaps (baseline absorbs the unmodeled second pulse) and turn the
        # score into a failed-fit flag instead of an SSE-improvement measure.
        valid = a1 > 0
        sse = np.where(valid, sse, np.inf)
        best = np.argmin(sse, axis=0)
        cols = np.arange(Y.shape[0])
        return sse[best, cols], T1P_GRID[best]

    def fit_two_pulse(self, Y: np.ndarray) -> dict[str, np.ndarray]:
        yy = (Y * Y).sum(axis=1)
        py = Y.sum(axis=1)
        P1 = self.T1 @ Y.T
        P2 = self.T2 @ Y.T
        p1 = P1[self.pair_i]  # (n_pairs, B)
        p2 = P2[self.pair_j]
        pyb = py[None, :]
        a1 = self.i11[:, None] * p1 + self.i12[:, None] * p2 + self.i13[:, None] * pyb
        a2 = self.i12[:, None] * p1 + self.i22[:, None] * p2 + self.i23[:, None] * pyb
        bl = self.i13[:, None] * p1 + self.i23[:, None] * p2 + self.i33[:, None] * pyb
        sse = yy[None, :] - (a1 * p1 + a2 * p2 + bl * pyb)
        valid = (a1 > 0) & (a2 > 0) & (bl >= self.blo) & (bl <= self.bhi)
        sse = np.where(valid, sse, np.inf)
        best = np.argmin(sse, axis=0)
        cols = np.arange(Y.shape[0])
        best_sse = sse[best, cols]
        ok = np.isfinite(best_sse)
        return {
            "sse": best_sse,
            "t1": np.where(ok, T1_GRID[self.pair_i[best]], np.nan),
            "t2": np.where(ok, T2_GRID[self.pair_j[best]], np.nan),
            "a1": np.where(ok, a1[best, cols], np.nan),
            "a2": np.where(ok, a2[best, cols], np.nan),
            "ok": ok,
        }


def run_traditional_fit(df: pd.DataFrame, waveforms: np.ndarray, card: dict, chunk: int = 256) -> pd.DataFrame:
    dig = card["digitizer"]
    out = {
        "trad_score": np.full(len(df), -np.inf),
        "trad_dt_ns": np.full(len(df), np.nan),
        "trad_t1_ns": np.full(len(df), np.nan),
        "trad_a1": np.full(len(df), np.nan),
        "trad_a2": np.full(len(df), np.nan),
        "trad_ok": np.zeros(len(df), dtype=bool),
    }
    stave_arr = df["stave"].to_numpy()
    for stave in STAVES:
        idx = np.flatnonzero(stave_arr == stave)
        if len(idx) == 0:
            continue
        over = dig.get("staves", {}).get(stave, {})
        fitter = TwoPulseFitter(
            tau_rise_ns=float(over.get("tau_rise_ns", dig["tau_rise_ns"])),
            tau_decay_ns=float(over.get("tau_decay_ns", dig["tau_decay_ns"])),
            pedestal_adc=float(dig["pedestal_adc"]),
        )
        for lo in range(0, len(idx), chunk):
            sel = idx[lo : lo + chunk]
            Y = waveforms[sel].astype(np.float64)
            sse1, _t1p = fitter.fit_one_pulse(Y)
            two = fitter.fit_two_pulse(Y)
            score = (sse1 - two["sse"]) / np.maximum(sse1, 1.0)
            score = np.where(two["ok"] & np.isfinite(sse1), score, -np.inf)
            out["trad_score"][sel] = score
            out["trad_dt_ns"][sel] = two["t2"] - two["t1"]
            out["trad_t1_ns"][sel] = two["t1"]
            out["trad_a1"][sel] = two["a1"]
            out["trad_a2"][sel] = two["a2"]
            out["trad_ok"][sel] = two["ok"]
    return pd.DataFrame(out, index=df.index)


# ----------------------------------------------------------------------------
# Compact ML: HGB on the raw 18 samples
# ----------------------------------------------------------------------------
def run_ml(df: pd.DataFrame, waveforms: np.ndarray) -> pd.DataFrame:
    from sklearn.ensemble import (
        HistGradientBoostingClassifier,
        HistGradientBoostingRegressor,
    )

    X = waveforms.astype(np.float32)
    train = (df["split"] == "train").to_numpy()
    y_class = df["is_overlap"].to_numpy(dtype=int)
    clf = HistGradientBoostingClassifier(max_iter=300, random_state=SEED)
    clf.fit(X[train], y_class[train])
    ml_score = clf.predict_proba(X)[:, 1]

    pos_train = train & (y_class == 1)
    reg = HistGradientBoostingRegressor(max_iter=400, random_state=SEED + 1)
    reg.fit(X[pos_train], df.loc[pos_train, "dt_true_ns"].to_numpy(dtype=float))
    ml_dt = reg.predict(X)
    return pd.DataFrame({"ml_score": ml_score, "ml_dt_ns": ml_dt}, index=df.index)


# ----------------------------------------------------------------------------
# Independent MC tau_eff (S10b-style estimator, ported from
# reports/1781000867.546870.5c124aaf/s10b_tau_eff_template_fit.py)
# ----------------------------------------------------------------------------
TAU_GRID_NS = np.arange(-30.0, 165.1, 5.0)
TAU_AMP_CUT = 1000.0


def cfd_time_samples(waveforms: np.ndarray, amplitudes: np.ndarray, fraction: float = 0.20) -> np.ndarray:
    threshold = amplitudes * float(fraction)
    ge = waveforms >= threshold[:, None]
    first = np.argmax(ge, axis=1)
    valid = ge.any(axis=1)
    out = np.full(len(waveforms), np.nan, dtype=float)
    for i in np.where(valid)[0]:
        j = int(first[i])
        if j <= 0:
            out[i] = float(j)
            continue
        y0, y1 = float(waveforms[i, j - 1]), float(waveforms[i, j])
        denom = y1 - y0
        out[i] = float(j) if denom <= 0 else (j - 1) + (float(threshold[i]) - y0) / denom
    return out


def exp_tail(t: np.ndarray, c: float, a: float, tau: float) -> np.ndarray:
    return c + a * np.exp(-t / tau)


def fit_template_live_time(grid_ns: np.ndarray, y: np.ndarray, threshold: float) -> dict:
    from scipy.optimize import curve_fit

    valid = np.isfinite(y)
    if valid.sum() < 8:
        return {"peak_t_ns": np.nan, "cross_ns": np.nan, "decay_tau_ns": np.nan, "fit_ok": False}
    peak_i = int(np.nanargmax(y))
    peak_t = float(grid_ns[peak_i])
    tail = valid & (grid_ns >= peak_t) & (grid_ns <= 155.0)
    if tail.sum() < 6:
        return {"peak_t_ns": peak_t, "cross_ns": np.nan, "decay_tau_ns": np.nan, "fit_ok": False}
    x = grid_ns[tail] - peak_t
    yy = y[tail]
    try:
        popt, _ = curve_fit(
            exp_tail, x, yy,
            p0=(0.01, max(float(np.nanmax(yy)), 0.2), 55.0),
            bounds=([-0.1, 0.0, 5.0], [0.2, 2.0, 500.0]),
            maxfev=20000,
        )
        c, a, tau = [float(v) for v in popt]
        cross = np.nan if (threshold <= c or a <= 0) else peak_t + tau * math.log(a / (threshold - c))
        return {"peak_t_ns": peak_t, "cross_ns": float(cross), "decay_tau_ns": tau, "fit_ok": bool(np.isfinite(cross))}
    except Exception:
        return {"peak_t_ns": peak_t, "cross_ns": np.nan, "decay_tau_ns": np.nan, "fit_ok": False}


def tau_eff_mc(
    df_neg: pd.DataFrame,
    waveforms_neg: np.ndarray,
    rng: np.random.Generator,
    n_boot: int = 300,
    max_align_per_stave: int = 6000,
) -> tuple[pd.DataFrame, dict]:
    """S10b 10% tail-crossing live-time on digitized MC single pulses.

    Per pulse: s00 baseline (median samples 0-3), A>1000 selection, CFD20
    alignment; per stave: median template on TAU_GRID_NS, exponential tail
    fit, 10% crossing. Pooled value = stave-composition-weighted mean
    (weights = the selected single-pulse composition, the MC analogue of
    S10b's per-run stave weights). Bootstrap resamples the aligned pulses.
    """
    base = np.median(waveforms_neg[:, :4], axis=1)
    corr = waveforms_neg - base[:, None]
    amp = corr.max(axis=1)
    sel = amp > TAU_AMP_CUT
    stave_arr = df_neg["stave"].to_numpy()

    rows = []
    aligned_by_stave: dict[str, np.ndarray] = {}
    weights: dict[str, float] = {}
    for stave in STAVES:
        m = sel & (stave_arr == stave)
        n_sel = int(m.sum())
        weights[stave] = float(n_sel)
        if n_sel < 80:
            rows.append({"stave": stave, "n_selected": n_sel, "live10_ns": np.nan})
            continue
        wf = corr[m]
        a = amp[m]
        cfd = cfd_time_samples(wf, a, 0.20)
        good = np.isfinite(cfd)
        wf, a, cfd = wf[good], a[good], cfd[good]
        # empirical per-pulse live10 (cross-check, as in S10b)
        norm = wf / np.maximum(a, 1.0)[:, None]
        last10 = np.where(norm >= 0.10, np.arange(N_SAMPLES)[None, :], -1).max(axis=1)
        live10_emp = (last10 - cfd) * SPACING_NS
        live10_emp = live10_emp[live10_emp >= 0]

        take = min(len(wf), max_align_per_stave)
        pick = rng.choice(len(wf), size=take, replace=False)
        aligned = np.empty((take, len(TAU_GRID_NS)))
        for r, i in enumerate(pick):
            sample_t = (np.arange(N_SAMPLES, dtype=float) - cfd[i]) * SPACING_NS
            aligned[r] = np.interp(TAU_GRID_NS, sample_t, norm[i], left=np.nan, right=np.nan)
        aligned_by_stave[stave] = aligned
        template = np.nanmedian(aligned, axis=0)
        fit = fit_template_live_time(TAU_GRID_NS, template, 0.10)
        boots = []
        for _ in range(n_boot):
            b = rng.integers(0, take, size=take)
            f = fit_template_live_time(TAU_GRID_NS, np.nanmedian(aligned[b], axis=0), 0.10)
            if np.isfinite(f["cross_ns"]):
                boots.append(f["cross_ns"])
        rows.append({
            "stave": stave,
            "n_selected": n_sel,
            "n_aligned": take,
            "live10_ns": fit["cross_ns"],
            "live10_ci_low": float(np.percentile(boots, 2.5)) if boots else np.nan,
            "live10_ci_high": float(np.percentile(boots, 97.5)) if boots else np.nan,
            "decay_tau_ns": fit["decay_tau_ns"],
            "empirical_mean_live10_ns": float(np.mean(live10_emp)) if len(live10_emp) else np.nan,
            "fit_ok": bool(fit["fit_ok"]),
        })
    by_stave = pd.DataFrame(rows)

    w = np.asarray([weights[s] for s in STAVES], dtype=float)
    vals = by_stave.set_index("stave").reindex(list(STAVES))["live10_ns"].to_numpy(dtype=float)
    finite = np.isfinite(vals) & (w > 0)
    pooled = float(np.average(vals[finite], weights=w[finite])) if finite.any() else float("nan")
    pooled_boots = []
    for _ in range(n_boot):
        stave_vals = []
        stave_w = []
        for k, stave in enumerate(STAVES):
            if stave not in aligned_by_stave:
                continue
            aligned = aligned_by_stave[stave]
            b = rng.integers(0, len(aligned), size=len(aligned))
            f = fit_template_live_time(TAU_GRID_NS, np.nanmedian(aligned[b], axis=0), 0.10)
            if np.isfinite(f["cross_ns"]):
                stave_vals.append(f["cross_ns"])
                stave_w.append(w[k])
        if stave_vals:
            pooled_boots.append(float(np.average(stave_vals, weights=stave_w)))
    pooled_result = {
        "live10_ns": pooled,
        "ci_low": float(np.percentile(pooled_boots, 2.5)) if pooled_boots else float("nan"),
        "ci_high": float(np.percentile(pooled_boots, 97.5)) if pooled_boots else float("nan"),
        "n_boot": len(pooled_boots),
        "data_live10_ns": DATA_TAU_EFF_NS,
        "delta_ns": pooled - DATA_TAU_EFF_NS if np.isfinite(pooled) else float("nan"),
        "stave_weights": {s: weights[s] for s in STAVES},
    }
    return by_stave, pooled_result


# ----------------------------------------------------------------------------
# Figure (nature-figure contract: quantitative grid; hero = risk-coverage row)
# ----------------------------------------------------------------------------
COL_TRAD = "#5D6D7E"   # neutral family: constrained template fit
COL_ML = "#D55E00"     # signal family: compact ML
COL_DATA = "#000000"


def make_figure(
    out_dir: Path,
    curves: pd.DataFrame,
    fail_tab: pd.DataFrame,
    common_tab: pd.DataFrame,
    tau_by_stave: pd.DataFrame,
    tau_pooled: dict,
    rates: list[float],
) -> None:
    mpl.rcParams.update({
        "font.family": "sans-serif",
        "font.sans-serif": ["Arial", "Helvetica", "DejaVu Sans", "sans-serif"],
        "svg.fonttype": "none",
        "pdf.fonttype": 42,
        "font.size": 7,
        "axes.spines.right": False,
        "axes.spines.top": False,
        "axes.linewidth": 0.8,
        "legend.frameon": False,
    })
    fig = plt.figure(figsize=(7.2, 4.6))
    gs = fig.add_gridspec(2, 3, hspace=0.55, wspace=0.42)

    # hero row: risk-coverage per rate
    for k, rate in enumerate(rates):
        ax = fig.add_subplot(gs[0, k])
        for method, color, label in (("trad", COL_TRAD, "template fit"), ("ml", COL_ML, "compact ML")):
            sub = curves[(curves["rate_mhz"] == rate) & (curves["method"] == method)]
            ax.plot(sub["coverage"], sub["risk"], color=color, lw=1.2, label=label)
        ax.axvline(TARGET_COVERAGE, color="0.6", lw=0.7, ls=":")
        ax.set_xlim(0.05, 1.0)
        ax.set_ylim(0, max(0.05, float(curves["risk"].max()) * 1.05))
        ax.set_title(f"R = {rate:g} MHz", fontsize=7)
        ax.set_xlabel("coverage")
        if k == 0:
            ax.set_ylabel("failure risk\n(missed or |Δdt| > 15 ns)")
            ax.legend(fontsize=6, loc="upper left")
        ax.text(-0.18, 1.12, "abc"[k], transform=ax.transAxes, fontsize=8, fontweight="bold")

    # d: failure @ 80% coverage
    ax = fig.add_subplot(gs[1, 0])
    x = np.arange(len(rates))
    for off, (method, color, label) in zip((-0.17, 0.17), (("trad", COL_TRAD, "template fit"), ("ml", COL_ML, "compact ML"))):
        sub = fail_tab[fail_tab["method"] == method].sort_values("rate_mhz")
        vals = sub["failure_at_80pct_coverage"].to_numpy()
        lo = vals - sub["failure_ci_low"].to_numpy()
        hi = sub["failure_ci_high"].to_numpy() - vals
        ax.bar(x + off, vals, width=0.32, color=color, label=label)
        ax.errorbar(x + off, vals, yerr=[lo, hi], fmt="none", ecolor="black", elinewidth=0.7, capsize=1.5)
    ax.set_xticks(x, [f"{r:g}" for r in rates])
    ax.set_xlabel("rate (MHz)")
    ax.set_ylabel("failure @ 80% coverage")
    ax.text(-0.18, 1.12, "d", transform=ax.transAxes, fontsize=8, fontweight="bold")

    # e: sigma68 on the common accepted subset
    ax = fig.add_subplot(gs[1, 1])
    for method, color, label in (("trad", COL_TRAD, "template fit"), ("ml", COL_ML, "compact ML")):
        sub = common_tab.sort_values("rate_mhz")
        ax.plot(sub["rate_mhz"], sub[f"sigma68_{method}_ns"], "o-", color=color, lw=1.0, ms=3, label=label)
    ax.set_xlabel("rate (MHz)")
    ax.set_ylabel("dt σ68 (ns), common accepted subset")
    ax.text(-0.18, 1.12, "e", transform=ax.transAxes, fontsize=8, fontweight="bold")

    # f: independent MC tau_eff vs data
    ax = fig.add_subplot(gs[1, 2])
    xs = np.arange(len(STAVES) + 1)
    vals = list(tau_by_stave.set_index("stave").reindex(list(STAVES))["live10_ns"]) + [tau_pooled["live10_ns"]]
    los = list(tau_by_stave.set_index("stave").reindex(list(STAVES))["live10_ci_low"]) + [tau_pooled["ci_low"]]
    his = list(tau_by_stave.set_index("stave").reindex(list(STAVES))["live10_ci_high"]) + [tau_pooled["ci_high"]]
    vals = np.asarray(vals, dtype=float)
    yerr = np.vstack([vals - np.asarray(los, float), np.asarray(his, float) - vals])
    ax.errorbar(xs, vals, yerr=np.abs(yerr), fmt="o", ms=3.5, color=COL_TRAD, ecolor=COL_TRAD, elinewidth=0.8, capsize=2)
    ax.axhline(DATA_TAU_EFF_NS, color=COL_DATA, ls="--", lw=0.9)
    ax.text(0.02, DATA_TAU_EFF_NS + 1.0, f"data {DATA_TAU_EFF_NS} ns", fontsize=6)
    ax.set_xticks(xs, list(STAVES) + ["pooled"])
    ax.set_ylabel("MC live10 (ns)")
    ax.text(-0.18, 1.12, "f", transform=ax.transAxes, fontsize=8, fontweight="bold")

    for ext, kw in (("png", {"dpi": 600}), ("svg", {}), ("pdf", {})):
        fig.savefig(out_dir / f"fig_mc03_benchmark.{ext}", bbox_inches="tight", **kw)
    plt.close(fig)


# ----------------------------------------------------------------------------
# Driver
# ----------------------------------------------------------------------------
def load_overlays(overlay_dir: Path) -> tuple[pd.DataFrame, np.ndarray, list[float]]:
    manifest = json.loads((overlay_dir / "manifest.json").read_text(encoding="utf-8"))
    frames = []
    for meta in manifest["rates"]:
        path = overlay_dir / Path(meta["path"]).name
        frames.append(pd.read_csv(path))
    df = pd.concat(frames, ignore_index=True)
    sample_cols = [f"s{j:02d}" for j in range(N_SAMPLES)]
    waveforms = df[sample_cols].to_numpy(dtype=np.float64)
    df = df.drop(columns=sample_cols)
    rates = sorted(float(m["rate_mhz"]) for m in manifest["rates"])
    return df, waveforms, rates


def json_ready(value):
    if isinstance(value, dict):
        return {str(k): json_ready(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [json_ready(v) for v in value]
    if isinstance(value, (np.bool_, bool)):
        return bool(value)
    if isinstance(value, np.integer):
        return int(value)
    if isinstance(value, (np.floating, float)):
        value = float(value)
        return value if np.isfinite(value) else None
    return value


def write_report(out_dir: Path, ctx: dict) -> None:
    rates = ctx["rates"]
    fail_tab = ctx["fail_tab"]
    common_tab = ctx["common_tab"]
    det_tab = ctx["det_tab"]
    tau_by_stave = ctx["tau_by_stave"]
    tau_pooled = ctx["tau_pooled"]

    def frow(rate, method):
        r = fail_tab[(fail_tab["rate_mhz"] == rate) & (fail_tab["method"] == method)].iloc[0]
        return (f"{r['failure_at_80pct_coverage']:.4f} "
                f"[{r['failure_ci_low']:.4f}, {r['failure_ci_high']:.4f}]")

    fail_lines = "\n".join(
        f"| {rate:g} | {frow(rate, 'trad')} | {frow(rate, 'ml')} | "
        f"{int(fail_tab[(fail_tab['rate_mhz'] == rate) & (fail_tab['method'] == 'trad')].iloc[0]['n_positive'])} |"
        for rate in rates
    )
    common_lines = "\n".join(
        f"| {r['rate_mhz']:g} | {r['sigma68_trad_ns']:.3f} | {r['sigma68_ml_ns']:.3f} | "
        f"{r['bias_trad_ns']:+.3f} | {r['bias_ml_ns']:+.3f} | {int(r['n_common'])} |"
        for _, r in common_tab.sort_values("rate_mhz").iterrows()
    )
    det_lines = "\n".join(
        f"| {r['rate_mhz']:g} | {r['method']} | {r['auc']:.4f} | {r['ap']:.4f} | {r['neg_fpr_at_theta']:.4f} |"
        for _, r in det_tab.sort_values(["rate_mhz", "method"]).iterrows()
    )
    tau_lines = "\n".join(
        f"| {r['stave']} | {int(r['n_selected'])} | {r['live10_ns']:.2f} "
        f"[{r['live10_ci_low']:.2f}, {r['live10_ci_high']:.2f}] | {r['decay_tau_ns']:.2f} | "
        f"{r['empirical_mean_live10_ns']:.2f} |"
        for _, r in tau_by_stave.iterrows() if np.isfinite(r.get("live10_ns", np.nan))
    )

    text = f"""# MC03 — truth-labelled pile-up overlays and the honest two-pulse benchmark (S24)

- **Date:** {time.strftime('%Y-%m-%d')}
- **Inputs:** {ctx['overlay_dir']} (manifest sha256 in `manifest.json`)
- **Scripts:** `scripts/mc03_build_overlay_sample.py`, `scripts/s24_two_pulse_honest_benchmark.py`
- **Digitizer card:** `{ctx['card_path']}` (sha256 `{ctx['card_sha'][:16]}…`)

## 0. Question

What is the truth-labelled two-pulse failure rate versus pile-up rate for the
constrained template fit and a compact ML model, under a benchmark that fixes
every rigging channel of the retracted S11a comparison (review P8)? And what
live-time (tau_eff) does the tuned digitizer actually produce, measured
independently on digitized MC single pulses (replacing the retracted MV5
"MC tau_eff", review I2)?

## 1. How this benchmark differs from the rigged S11a (review P8)

| S11a defect | This benchmark |
|---|---|
| injection separation grid == fit hypothesis grid | injection dt CONTINUOUS (exponential, inverse-CDF); fit grid independent (t1 step 0.5 ns, t2 step 1 ns) |
| injected waveforms generated from the fit's own templates | injected waveforms are digitized PAIRS of real truth hit groups (multi-hit, per-hit transport smear, per-record noise); fit templates are the card kernel |
| failure definitions differ per method | ONE definition for both: missed detection OR |dt_rec − dt_true| > {FAILURE_DT_TOL_NS:.0f} ns (`failure_flags`, unit-tested for symmetry) |
| unmatched coverage / own accepted subsets | detection thresholds set by the SAME procedure (score quantile at {TRAIN_NEG_FPR:.0%} FPR on train-split negatives); risk-coverage swept for both; headline at the SAME {TARGET_COVERAGE:.0%} coverage; σ68 on the COMMON accepted subset |

Residual circularity, stated honestly: the fit template is the digitizer-card
kernel, and the same card drives the mc03 generator — the template shares the
kernel *family* with the truth pulses by construction. It is NOT built from
the injection sample (no fitting/averaging of injected waveforms), and the
injected pulses are multi-hit truth groups with transport smearing, so they
are genuinely off-template; the ML method never sees a template at all. A
data-side template mismatch stress (real-template fits) remains future work.

## 2. Sample

{ctx['n_records_total']} records ({', '.join(f"{r:g} MHz" for r in rates)}), each rate ~{ctx['n_records_per_rate']}
records, {ctx['overlap_fraction']:.0%} two-pulse overlaps + {1 - ctx['overlap_fraction']:.0%} single-pulse negatives.
Pulse 1 at the nominal 50 ns trigger offset; pulse 2 at 50 + dt,
dt ~ Exp(1/R) truncated to ≤ {ctx['dt_max_ns']:.0f} ns, CONTINUOUS ({ctx['n_unique_dt']} unique dt values
across rates — no grid). Constituents drawn independently from the truth
population (per-constituent noise-free amplitude > {ctx['min_true_amp_adc']:.0f} ADC; no ratio
restriction). Train/eval split by source-event parity (both constituents).

## 3. Failure rate at matched 80% coverage (truth-labelled, per rate) — MV5 open sub-item

| rate (MHz) | template fit — failure@80% [95% CI] | compact ML — failure@80% [95% CI] | n eval positives |
|---:|---|---|---:|
{fail_lines}

Full curves: `risk_coverage_curves.csv`, figure panels a–c. Failure at full
coverage and threshold sensitivity: `result.json`.

## 4. dt resolution on the COMMON accepted subset

| rate (MHz) | σ68 trad (ns) | σ68 ML (ns) | bias trad (ns) | bias ML (ns) | n common |
|---:|---:|---:|---:|---:|---:|
{common_lines}

## 5. Detection sanity (eval split)

| rate (MHz) | method | ROC AUC | AP | realized FPR at θ (eval negatives) |
|---:|---|---:|---:|---:|
{det_lines}

## 6. Independent MC tau_eff (S10b 10% tail-crossing estimator on digitized single pulses)

| stave | n selected | live10 (ns) [95% CI] | tail τ (ns) | empirical mean live10 (ns) |
|---|---:|---|---:|---:|
{tau_lines}

**Pooled (stave-composition weighted): {tau_pooled['live10_ns']:.2f} ns
[{tau_pooled['ci_low']:.2f}, {tau_pooled['ci_high']:.2f}] vs data {DATA_TAU_EFF_NS} ns
(Δ = {tau_pooled['delta_ns']:+.2f} ns).** This is the FIRST honest MC live-time:
measured by the S10b estimator on digitized MC pulses with the per-stave
data-tuned tail decays — unlike the retracted MV5 number, which was a
hardcoded copy of the data value (review I2).

## 7. Caveats (honest limits of this closure)

- **Gain placeholder**: the card gain (297 ADC/MeV) is an UNKNOWN placeholder;
  all amplitudes are in arbitrary scale. Phase 2 attributes the MV3 spectrum
  discrepancy to the unsimulated two-arm coincidence trigger (not missing
  material) and prefers **gain ≈ 60** as the trigger-consistent estimate; the
  A>1000-equivalent selection boundary of this sample therefore corresponds
  to a different physical energy than in data.
- **Population weights**: stave occupancy and the amplitude spectrum are taken
  from the un-triggered MC truth population and inherit the MV3 spectrum
  discrepancy (χ²/ndf = 68269; Phase 2 root cause: unsimulated trigger).
- **Single-stave overlays only**: both constituents land on one stave/channel;
  no cross-stave topology, no A-arm.
- **Fixed trigger phase**: pulse 1 always at 50 ns (nominal mc02 convention);
  data pulses have phase jitter. The fit's t1 grid and the ML model both
  exploit this — absolute failure rates are optimistic on this axis.
- **Kernel-family circularity** (see §1): fit templates share the card kernel
  family with the generator; template-mismatch stress not included.
- **tau_eff comparison**: MC single pulses are clean by construction; the data
  124.79 ns was measured on A>1000 data pulses including real pathologies.

## 8. Reproduce

```bash
python scripts/mc03_build_overlay_sample.py --mc <truth.root> --out <overlays>
python scripts/s24_two_pulse_honest_benchmark.py --overlay-dir <overlays> --out <this dir>
```

Runtime {ctx['runtime_sec']:.0f} s. Artifacts: `result.json`, `manifest.json`,
`risk_coverage_curves.csv`, `failure_at_coverage.csv`, `common_subset_sigma68.csv`,
`detection_metrics.csv`, `tau_eff_by_stave.csv`, `predictions_rate*.csv.gz`,
`fig_mc03_benchmark.(png|svg|pdf)`.
"""
    (out_dir / "REPORT.md").write_text(text, encoding="utf-8")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--overlay-dir", required=True, help="mc03 output directory")
    ap.add_argument("--out", required=True, help="report output directory")
    ap.add_argument("--card", default=str(DEFAULT_CARD_PATH))
    ap.add_argument("--n-boot", type=int, default=500)
    ap.add_argument("--tau-boot", type=int, default=300)
    ap.add_argument("--chunk", type=int, default=256)
    args = ap.parse_args()

    from sklearn.metrics import average_precision_score, roc_auc_score

    t_start = time.time()
    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)
    overlay_dir = Path(args.overlay_dir)
    card = load_digitizer_card(args.card)
    rng = np.random.default_rng(SEED)

    df, waveforms, rates = load_overlays(overlay_dir)
    print(f"[s24] loaded {len(df)} records, rates {rates} ({time.time() - t_start:.0f}s)", flush=True)

    trad = run_traditional_fit(df, waveforms, card, chunk=args.chunk)
    print(f"[s24] traditional fit done ({time.time() - t_start:.0f}s)", flush=True)
    ml = run_ml(df, waveforms)
    print(f"[s24] ML done ({time.time() - t_start:.0f}s)", flush=True)
    df = pd.concat([df, trad, ml], axis=1)

    # matched detection operating points (identical procedure per method)
    train_neg = (df["split"] == "train") & (df["is_overlap"] == 0)
    thetas = {
        "trad": detection_threshold(df.loc[train_neg, "trad_score"].to_numpy()),
        "ml": detection_threshold(df.loc[train_neg, "ml_score"].to_numpy()),
    }

    eval_mask = df["split"] == "eval"
    curves_rows, fail_rows, common_rows, det_rows = [], [], [], []
    sens_rows = []
    for rate in rates:
        r_eval = eval_mask & (df["rate_mhz"] == rate)
        pos = df[r_eval & (df["is_overlap"] == 1)]
        neg = df[r_eval & (df["is_overlap"] == 0)]
        dt_true = pos["dt_true_ns"].to_numpy(dtype=float)
        conf = {
            "trad": pos["trad_score"].to_numpy(dtype=float),
            "ml": pos["ml_score"].to_numpy(dtype=float),
        }
        dt_rec = {
            "trad": pos["trad_dt_ns"].to_numpy(dtype=float),
            "ml": pos["ml_dt_ns"].to_numpy(dtype=float),
        }
        for method in ("trad", "ml"):
            res = evaluate_method(
                method, conf[method], dt_rec[method], dt_true, thetas[method],
                rng=rng, n_boot=args.n_boot,
            )
            res["rate_mhz"] = rate
            fail_rows.append(res)
            failed = failure_flags(conf[method], thetas[method], dt_rec[method], dt_true)
            curve = risk_coverage_curve(conf[method], failed)
            step = max(len(curve) // 200, 1)
            sub = curve.iloc[::step].copy()
            sub["method"], sub["rate_mhz"] = method, rate
            curves_rows.append(sub)
            # detection sanity on eval split
            labels = np.r_[np.ones(len(pos), dtype=int), np.zeros(len(neg), dtype=int)]
            scores = np.r_[conf[method], neg[f"{method}_score"].to_numpy(dtype=float)]
            scores = np.where(np.isfinite(scores), scores, -1e12)
            det_rows.append({
                "rate_mhz": rate,
                "method": method,
                "auc": float(roc_auc_score(labels, scores)),
                "ap": float(average_precision_score(labels, scores)),
                "neg_fpr_at_theta": float(np.mean(
                    np.where(np.isfinite(neg[f"{method}_score"].to_numpy(dtype=float)),
                             neg[f"{method}_score"].to_numpy(dtype=float), -np.inf) >= thetas[method])),
            })
            # threshold-choice sensitivity of the headline number
            for fpr in (0.05, 0.20):
                th = detection_threshold(df.loc[train_neg, f"{method}_score"].to_numpy(), fpr)
                fl = failure_flags(conf[method], th, dt_rec[method], dt_true)
                sens_rows.append({
                    "rate_mhz": rate, "method": method, "train_neg_fpr": fpr,
                    "failure_at_80pct_coverage": risk_at_coverage(conf[method], fl, TARGET_COVERAGE),
                })
        # common accepted subset at matched 80% coverage
        tau_t = np.quantile(np.where(np.isfinite(conf["trad"]), conf["trad"], -np.inf), 1 - TARGET_COVERAGE)
        tau_m = np.quantile(conf["ml"], 1 - TARGET_COVERAGE)
        common = (
            (np.where(np.isfinite(conf["trad"]), conf["trad"], -np.inf) >= tau_t)
            & (conf["ml"] >= tau_m)
            & (conf["trad"] >= thetas["trad"]) & (conf["ml"] >= thetas["ml"])
            & np.isfinite(dt_rec["trad"]) & np.isfinite(dt_rec["ml"])
        )
        err_t = dt_rec["trad"][common] - dt_true[common]
        err_m = dt_rec["ml"][common] - dt_true[common]
        common_rows.append({
            "rate_mhz": rate,
            "n_common": int(common.sum()),
            "sigma68_trad_ns": sigma68(err_t),
            "sigma68_ml_ns": sigma68(err_m),
            "bias_trad_ns": float(np.median(err_t)) if common.any() else np.nan,
            "bias_ml_ns": float(np.median(err_m)) if common.any() else np.nan,
        })

    curves = pd.concat(curves_rows, ignore_index=True)
    fail_tab = pd.DataFrame(fail_rows)
    common_tab = pd.DataFrame(common_rows)
    det_tab = pd.DataFrame(det_rows)
    sens_tab = pd.DataFrame(sens_rows)

    # deliverable 3: independent MC tau_eff on ALL single-pulse records
    neg_all = df["is_overlap"] == 0
    tau_by_stave, tau_pooled = tau_eff_mc(
        df[neg_all], waveforms[neg_all.to_numpy()], rng, n_boot=args.tau_boot
    )
    print(f"[s24] tau_eff done: pooled {tau_pooled['live10_ns']:.2f} ns "
          f"({time.time() - t_start:.0f}s)", flush=True)

    curves.to_csv(out_dir / "risk_coverage_curves.csv", index=False)
    fail_tab.to_csv(out_dir / "failure_at_coverage.csv", index=False)
    common_tab.to_csv(out_dir / "common_subset_sigma68.csv", index=False)
    det_tab.to_csv(out_dir / "detection_metrics.csv", index=False)
    sens_tab.to_csv(out_dir / "threshold_sensitivity.csv", index=False)
    tau_by_stave.to_csv(out_dir / "tau_eff_by_stave.csv", index=False)
    for rate in rates:
        sub = df[df["rate_mhz"] == rate]
        cols = [c for c in sub.columns if not c.startswith("s0") and not c.startswith("s1")]
        sub[cols].to_csv(out_dir / f"predictions_rate{rate:g}MHz.csv.gz", index=False, compression="gzip")

    make_figure(out_dir, curves, fail_tab, common_tab, tau_by_stave, tau_pooled, rates)

    overlay_manifest = json.loads((overlay_dir / "manifest.json").read_text(encoding="utf-8"))
    ctx = {
        "rates": rates,
        "fail_tab": fail_tab,
        "common_tab": common_tab,
        "det_tab": det_tab,
        "tau_by_stave": tau_by_stave,
        "tau_pooled": tau_pooled,
        "overlay_dir": str(overlay_dir),
        "card_path": str(Path(args.card).resolve()),
        "card_sha": sha256_file(Path(args.card)),
        "n_records_total": int(len(df)),
        "n_records_per_rate": int(overlay_manifest["rates"][0]["n_records"]),
        "overlap_fraction": float(overlay_manifest["overlap_fraction"]),
        "dt_max_ns": float(overlay_manifest["dt_max_ns"]),
        "min_true_amp_adc": float(overlay_manifest["min_true_amp_adc"]),
        "n_unique_dt": int(sum(m["n_unique_dt"] for m in overlay_manifest["rates"])),
        "runtime_sec": time.time() - t_start,
    }
    write_report(out_dir, ctx)

    result = {
        "study": "S24/mc03",
        "title": "Honest two-pulse benchmark on truth-labelled overlays + independent MC tau_eff",
        "failure_definition": f"missed detection OR |dt_rec - dt_true| > {FAILURE_DT_TOL_NS} ns (single, both methods)",
        "matched_coverage": TARGET_COVERAGE,
        "detection_thresholds": thetas,
        "train_negative_fpr": TRAIN_NEG_FPR,
        "failure_at_coverage": fail_tab.to_dict(orient="records"),
        "threshold_sensitivity": sens_tab.to_dict(orient="records"),
        "common_subset_sigma68": common_tab.to_dict(orient="records"),
        "detection_metrics": det_tab.to_dict(orient="records"),
        "tau_eff": {
            "by_stave": tau_by_stave.to_dict(orient="records"),
            "pooled": tau_pooled,
            "estimator": "S10b 10% tail-crossing (aligned median template + exp tail fit), ported",
            "data_value_ns": DATA_TAU_EFF_NS,
        },
        "circularity_note": (
            "fit templates from the digitizer-card kernel, never from the injection sample; "
            "injection dt continuous vs independent fit grid; kernel FAMILY shared with the "
            "generator by construction (documented in REPORT.md section 1)"
        ),
        "runtime_sec": round(time.time() - t_start, 2),
    }
    (out_dir / "result.json").write_text(json.dumps(json_ready(result), indent=2) + "\n", encoding="utf-8")

    manifest = {
        "script": "scripts/s24_two_pulse_honest_benchmark.py",
        "generated_utc": time.strftime("%Y-%m-%dT%H:%M:%S+00:00", time.gmtime()),
        "overlay_dir": str(overlay_dir.resolve()),
        "overlay_manifest_sha256": sha256_file(overlay_dir / "manifest.json"),
        "card_sha256": ctx["card_sha"],
        "seed": SEED,
        "fit_grids": {
            "t1_ns": [float(T1_GRID[0]), float(T1_GRID[-1]), 0.5],
            "t2_ns": [float(T2_GRID[0]), float(T2_GRID[-1]), 1.0],
            "min_sep_ns": MIN_SEP_NS,
            "note": "independent of the continuous injection law (review P8)",
        },
        "outputs": {p.name: sha256_file(p) for p in sorted(out_dir.iterdir())
                    if p.is_file() and p.name != "manifest.json"},
    }
    (out_dir / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")

    print(json.dumps(json_ready({
        "failure_at_80pct_coverage": {
            f"{r['rate_mhz']:g}MHz_{r['method']}": r["failure_at_80pct_coverage"] for r in fail_rows
        },
        "tau_eff_pooled_ns": tau_pooled["live10_ns"],
        "runtime_sec": result["runtime_sec"],
    }), indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
