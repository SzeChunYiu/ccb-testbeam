#!/usr/bin/env python3
"""S22 — Per-stave timing resolution vs amplitude from raw B-stack waveforms.

Physics deliverable (owner request + EXTERNAL_REVIEW_2026-07-02.md):
  * Selection: baseline-subtracted amplitude A > 1000 ADC (standard anchor).
  * Observable: per-PAIR CFD20 timing residuals for the downstream pairs
    B4-B6, B4-B8, B6-B8, PER-PAIR-PER-RUN centered (subtract the per-pair
    median within each run; the review found that pooling uncentered pair
    residuals mixes cable-delay offsets into sigma).  sigma68 = (q84-q16)/2.
  * Binning: bins of the MIN amplitude of the two pulses in the pair,
    1000 ADC to overflow, >= 6 usable bins.
  * Sample I (runs 44-57) and Sample II (runs 58-63, 65) are DISJOINT run
    sets and are analysed separately (docs/02_data_and_runs.md).
  * B2-containing pairs are computed separately and flagged: B2 saturates
    (30-40% of selected B2 pulses above ~7000 ADC).
  * Errors: event-level bootstrap within run (never an iid bootstrap over
    the three linearly dependent pair residuals pooled together — review
    finding on the core timing bootstrap); run-to-run spread quoted
    separately.
  * Stages: raw rising-edge-constrained CFD20 (fix pattern from
    scripts/mv4_timing_study.py / s05c: last prev<thr<=cur crossing at or
    before the peak sample, linear interpolation), and after an analytic
    AMP-ONLY timewalk correction (s03a amp_only feature basis:
    1000/A, sqrt(1000/A), log1p(A/1000) per stave), fit on training runs
    and evaluated leave-one-run-out within each sample.
  * Per-stave estimate: sigma_stave = sigma_pair / sqrt(2), which ASSUMES
    the two staves of the pair contribute independent, equal-variance
    timing errors.  A three-pair triangle decomposition is reported as a
    cross-check where all three downstream pairs populate the bin.

The script is self-contained (no repo imports), reads the raw ROOT files
chunked, keeps data read-only, and is deterministic (fixed seed, sorted
iteration order).

Usage:
  python scripts/s22_timing_vs_amplitude.py --raw-dir data/root/root \
      --out reports/s22_timing_vs_amplitude_<stamp> [--max-events N]
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import subprocess
import sys
import time
from pathlib import Path
from typing import Dict, Iterable, List, Sequence, Tuple

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import uproot

# --------------------------------------------------------------------------
# Fixed analysis constants (kept in-file: the script is self-contained)
# --------------------------------------------------------------------------
STAVE_CHANNELS = {"B2": 0, "B4": 2, "B6": 4, "B8": 6}  # of 8 channels
SAMPLES_PER_CHANNEL = 18
BASELINE_SAMPLES = [0, 1, 2, 3]
SAMPLE_PERIOD_NS = 10.0
AMPLITUDE_CUT_ADC = 1000.0
CFD_FRACTION = 0.20
TOF_PER_CM_NS = 0.078
SPACING_CM = 2.0  # nominal inter-stave spacing used across S02/S03/S05c
STAVE_ORDER = {"B2": 0, "B4": 1, "B6": 2, "B8": 3}

SAMPLE_RUNS = {
    # docs/02_data_and_runs.md — analysis runs; disjoint run sets
    "sample_I": [44, 45, 46, 47, 48, 49, 50, 51, 52, 53, 54, 55, 56, 57],
    "sample_II": [58, 59, 60, 61, 62, 63, 65],
}

DOWNSTREAM_PAIRS = [("B4", "B6"), ("B4", "B8"), ("B6", "B8")]
B2_PAIRS = [("B2", "B4"), ("B2", "B6"), ("B2", "B8")]
ALL_PAIRS = DOWNSTREAM_PAIRS + B2_PAIRS

# Amplitude bins of min(A_left, A_right); last bin is the >= 8000 overflow.
# Edges are finer below ~3.5 kADC where the downstream min-pair-amplitude
# spectrum lives (both pulses of a downstream pair rarely exceed ~4 kADC),
# while still covering 1000-8000+ ADC; B2-containing pairs populate the
# upper bins.
AMP_BIN_EDGES = [1000.0, 1250.0, 1550.0, 1900.0, 2300.0, 2800.0, 3400.0, 4200.0, 5200.0, 6500.0, 8000.0, np.inf]
MIN_BIN_COUNT = 50          # pair residuals needed to quote a sigma68
MIN_RUN_BIN_COUNT = 20      # per-run residuals needed for the run spread
N_BOOTSTRAP = 200
RANDOM_SEED = 20260703
B2_SATURATION_ADC = 7000.0
RIDGE_ALPHA = 1.0e-3        # tiny ridge to keep the normal equations stable
CHUNK_EVENTS = 20000


# --------------------------------------------------------------------------
# Small utilities
# --------------------------------------------------------------------------
def git_commit() -> str:
    try:
        return subprocess.check_output(
            ["git", "rev-parse", "HEAD"], text=True, cwd=str(Path(__file__).resolve().parent)
        ).strip()
    except Exception:
        return "unknown"


def sha256_file(path: Path, block_size: int = 1024 * 1024) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(block_size), b""):
            digest.update(block)
    return digest.hexdigest()


def sigma68(values: np.ndarray) -> float:
    """Half-width of the central 68% interval: (q84 - q16) / 2.

    Shift-invariant; NaNs and infs are dropped.  Returns NaN for empty input.
    """
    values = np.asarray(values, dtype=float)
    values = values[np.isfinite(values)]
    if len(values) == 0:
        return float("nan")
    q16, q84 = np.percentile(values, [16.0, 84.0])
    return float(0.5 * (q84 - q16))


def amp_bin_edges() -> np.ndarray:
    return np.asarray(AMP_BIN_EDGES, dtype=float)


def assign_amp_bins(min_amp: np.ndarray, edges: np.ndarray | None = None) -> np.ndarray:
    """Bin index of each min-amplitude value; -1 if below the first edge.

    Bin i covers [edges[i], edges[i+1]); the last bin is open-ended when the
    final edge is +inf.
    """
    if edges is None:
        edges = amp_bin_edges()
    min_amp = np.asarray(min_amp, dtype=float)
    idx = np.searchsorted(edges, min_amp, side="right") - 1
    idx[min_amp < edges[0]] = -1
    idx[idx > len(edges) - 2] = len(edges) - 2
    return idx


def center_per_group(values: np.ndarray, group_keys: Sequence[np.ndarray]) -> np.ndarray:
    """Subtract the median of `values` within each group defined by key arrays.

    Used for per-(pair, run) centering: a constant cable-delay/run offset per
    pair is removed before any pooling.  sigma68 within a single group is
    unchanged (shift invariance); pooled quantiles no longer mix offsets.
    """
    values = np.asarray(values, dtype=float)
    out = np.array(values, dtype=float, copy=True)
    df = pd.DataFrame({"v": values})
    for i, key in enumerate(group_keys):
        df[f"k{i}"] = np.asarray(key)
    med = df.groupby([f"k{i}" for i in range(len(group_keys))])["v"].transform("median")
    out -= med.to_numpy()
    return out


def b_position_cm(stave: str) -> float:
    return SPACING_CM * STAVE_ORDER[stave]


# --------------------------------------------------------------------------
# Waveform processing (rising-edge-constrained CFD, vectorised)
# --------------------------------------------------------------------------
def cfd20_rising_edge(corrected: np.ndarray, amplitude: np.ndarray, period_ns: float = SAMPLE_PERIOD_NS) -> Tuple[np.ndarray, np.ndarray]:
    """Rising-edge-constrained CFD time (ns) for baseline-subtracted waveforms.

    corrected: (n_pulses, n_samples); amplitude: (n_pulses,).
    Threshold = CFD_FRACTION * amplitude.  Find the LAST sample j (1 <= j <=
    peak) with corrected[j-1] < thr <= corrected[j] and linearly interpolate.
    Scanning backward from the peak (mv4 fix, 2026-07-03) rejects pre-signal
    noise crossings that a forward-from-sample-0 scan latches onto; the
    constraint j <= peak (s05c) keeps the pick on the rising edge.
    Pulses with no such crossing fall back to the peak-sample time and are
    flagged False in the returned validity mask.
    """
    corrected = np.asarray(corrected, dtype=float)
    amplitude = np.asarray(amplitude, dtype=float)
    n, nsamp = corrected.shape
    peak = corrected.argmax(axis=1)
    threshold = amplitude * CFD_FRACTION
    ge = corrected[:, 1:] >= threshold[:, None]
    prev_lt = corrected[:, :-1] < threshold[:, None]
    sample_index = np.arange(1, nsamp)[None, :]
    eligible = ge & prev_lt & (sample_index <= peak[:, None])
    has = eligible.any(axis=1)
    # last eligible crossing: argmax over the reversed axis
    rev = eligible[:, ::-1]
    crossing = (nsamp - 1) - rev.argmax(axis=1)  # index into 1..nsamp-1
    crossing = np.where(has, crossing, 1)
    rows = np.arange(n)
    y0 = corrected[rows, crossing - 1]
    y1 = corrected[rows, crossing]
    denom = y1 - y0
    frac = np.divide(threshold - y0, denom, out=np.zeros_like(threshold), where=np.abs(denom) > 1e-12)
    t = np.where(has, (crossing - 1 + frac) * period_ns, peak * period_ns)
    return t, has


def pulse_quantities(waveforms: np.ndarray) -> Dict[str, np.ndarray]:
    """Baseline-subtract and extract amplitude / CFD20 time per pulse.

    waveforms: (n_events, n_staves, n_samples) raw ADC.
    """
    baseline = np.median(waveforms[..., BASELINE_SAMPLES], axis=-1)
    corrected = waveforms - baseline[..., None]
    amplitude = corrected.max(axis=-1)
    n_ev, n_st, nsamp = corrected.shape
    flat = corrected.reshape(-1, nsamp)
    t, valid = cfd20_rising_edge(flat, amplitude.reshape(-1))
    return {
        "amplitude": amplitude,
        "time_ns": t.reshape(n_ev, n_st),
        "cfd_valid": valid.reshape(n_ev, n_st),
    }


# --------------------------------------------------------------------------
# Chunked raw loading -> per-pair table
# --------------------------------------------------------------------------
def raw_file(raw_dir: Path, run: int) -> Path:
    return raw_dir / f"hrdb_run_{run:04d}.root"


def iter_raw(path: Path, branches: List[str], step_size: int = CHUNK_EVENTS) -> Iterable[dict]:
    tree = uproot.open(path)["h101"]
    yield from tree.iterate(branches, step_size=step_size, library="np")


def load_run_pairs(raw_dir: Path, run: int, sample: str, max_events: int = 0) -> Tuple[pd.DataFrame, dict]:
    """Per-pair rows (both pulses selected) for one run; chunked and vectorised."""
    stave_names = list(STAVE_CHANNELS.keys())
    channels = np.asarray([STAVE_CHANNELS[s] for s in stave_names])
    rows: List[pd.DataFrame] = []
    n_seen = 0
    n_selected_by_stave = {s: 0 for s in stave_names}
    n_saturated_b2 = 0
    n_cfd_fallback = 0
    for batch in iter_raw(raw_file(raw_dir, run), ["EVENTNO", "HRDv"]):
        eventno = np.asarray(batch["EVENTNO"]).astype(np.int64)
        flat = np.stack(batch["HRDv"]).astype(np.float64)
        if flat.shape[1] != 8 * SAMPLES_PER_CHANNEL:
            raise RuntimeError(
                f"run {run}: HRDv length {flat.shape[1]} != 8*{SAMPLES_PER_CHANNEL} "
                "(wrong/truncated reduction — use the canonical 144-value files)"
            )
        events = flat.reshape(-1, 8, SAMPLES_PER_CHANNEL)[:, channels, :]
        q = pulse_quantities(events)
        selected = q["amplitude"] > AMPLITUDE_CUT_ADC
        n_cfd_fallback += int((selected & ~q["cfd_valid"]).sum())
        for i, s in enumerate(stave_names):
            n_selected_by_stave[s] += int(selected[:, i].sum())
        i_b2 = stave_names.index("B2")
        n_saturated_b2 += int((selected[:, i_b2] & (q["amplitude"][:, i_b2] >= B2_SATURATION_ADC)).sum())
        for left, right in ALL_PAIRS:
            i = stave_names.index(left)
            j = stave_names.index(right)
            mask = selected[:, i] & selected[:, j]
            if not mask.any():
                continue
            amp_l = q["amplitude"][mask, i]
            amp_r = q["amplitude"][mask, j]
            tof = (b_position_cm(right) - b_position_cm(left)) * TOF_PER_CM_NS
            resid = q["time_ns"][mask, j] - q["time_ns"][mask, i] - tof
            rows.append(
                pd.DataFrame(
                    {
                        "run": np.full(mask.sum(), run, dtype=np.int32),
                        "sample": sample,
                        "eventno": eventno[mask] if len(eventno) == len(mask) else np.flatnonzero(mask),
                        "pair": f"{left}-{right}",
                        "left": left,
                        "right": right,
                        "has_b2": left == "B2" or right == "B2",
                        "amp_left": amp_l,
                        "amp_right": amp_r,
                        "min_amp": np.minimum(amp_l, amp_r),
                        "raw_residual_ns": resid,
                    }
                )
            )
        n_seen += len(events)
        if max_events and n_seen >= max_events:
            break
    meta = {
        "run": run,
        "sample": sample,
        "n_events": n_seen,
        "n_cfd_fallback_selected": n_cfd_fallback,
        "n_selected_b2_saturated_ge7000": n_saturated_b2,
        **{f"n_selected_{s}": n_selected_by_stave[s] for s in stave_names},
    }
    if rows:
        return pd.concat(rows, ignore_index=True), meta
    return pd.DataFrame(), meta


# --------------------------------------------------------------------------
# Analytic amp-only timewalk correction (s03a amp_only basis, pair-difference fit)
# --------------------------------------------------------------------------
TIMEWALK_FEATURES = ["inv_amp_1000", "inv_sqrt_amp_1000", "log1p_amp_1000"]


def timewalk_phi(amp: np.ndarray) -> np.ndarray:
    """Per-pulse amp-only feature basis (s03a amp_only, MV4b 1/A form leading)."""
    a = np.maximum(np.asarray(amp, dtype=float), 1.0)
    return np.column_stack([1000.0 / a, np.sqrt(1000.0 / a), np.log1p(a / 1000.0)])


def fit_timewalk(pairs: pd.DataFrame, train_runs: Sequence[int]) -> Dict[str, np.ndarray]:
    """Fit per-stave f_s(A) so that corrected pair residuals are amp-flat.

    Model: E[centered residual (right-left)] = f_right(A_right) - f_left(A_left)
    with f_s(A) = beta_s . phi(A), phi constant-free (per-(pair,run) centering
    absorbs all constant offsets).  Solved by ridge-regularised normal
    equations; deterministic.  B2 gets its own parameters but B2-containing
    pairs are flagged downstream (saturation).
    """
    sub = pairs[pairs["run"].isin(list(train_runs))]
    if len(sub) == 0:
        return {s: np.zeros(len(TIMEWALK_FEATURES)) for s in STAVE_CHANNELS}
    y = center_per_group(sub["raw_residual_ns"].to_numpy(), [sub["pair"].to_numpy(), sub["run"].to_numpy()])
    staves = sorted(STAVE_CHANNELS.keys())
    k = len(TIMEWALK_FEATURES)
    X = np.zeros((len(sub), k * len(staves)))
    phi_l = timewalk_phi(sub["amp_left"].to_numpy())
    phi_r = timewalk_phi(sub["amp_right"].to_numpy())
    left = sub["left"].to_numpy()
    right = sub["right"].to_numpy()
    for si, s in enumerate(staves):
        cols = slice(si * k, (si + 1) * k)
        X[left == s, cols] -= phi_l[left == s]
        X[right == s, cols] += phi_r[right == s]
    # standardise columns for a scale-meaningful ridge, then unwind
    mu = X.mean(axis=0)
    sd = X.std(axis=0)
    sd[sd == 0.0] = 1.0
    Xs = (X - mu) / sd
    A = Xs.T @ Xs + RIDGE_ALPHA * len(sub) * np.eye(Xs.shape[1])
    b = Xs.T @ (y - y.mean())
    beta_s = np.linalg.solve(A, b)
    beta = beta_s / sd
    return {s: beta[si * k : (si + 1) * k] for si, s in enumerate(staves)}


def apply_timewalk(pairs: pd.DataFrame, betas: Dict[str, np.ndarray]) -> np.ndarray:
    """Corrected residual = raw - (f_right(A_right) - f_left(A_left))."""
    phi_l = timewalk_phi(pairs["amp_left"].to_numpy())
    phi_r = timewalk_phi(pairs["amp_right"].to_numpy())
    pred = np.zeros(len(pairs))
    left = pairs["left"].to_numpy()
    right = pairs["right"].to_numpy()
    for s, beta in betas.items():
        pred[right == s] += phi_r[right == s] @ beta
        pred[left == s] -= phi_l[left == s] @ beta
    return pairs["raw_residual_ns"].to_numpy() - pred


def loro_corrected_residuals(pairs: pd.DataFrame, sample: str) -> Tuple[np.ndarray, Dict[str, list]]:
    """Leave-one-run-out corrected residuals within one sample.

    For each run r, the timewalk model is fit on all OTHER runs of the same
    sample and applied to run r — every corrected residual is out-of-sample
    at run level.  Returns the corrected column plus the per-fold betas.
    """
    out = np.full(len(pairs), np.nan)
    fold_betas: Dict[str, list] = {}
    runs = sorted(pairs.loc[pairs["sample"] == sample, "run"].unique().tolist())
    for r in runs:
        train = [x for x in runs if x != r]
        betas = fit_timewalk(pairs[pairs["sample"] == sample], train)
        mask = (pairs["sample"] == sample) & (pairs["run"] == r)
        out[mask.to_numpy()] = apply_timewalk(pairs[mask], betas)
        fold_betas[str(r)] = {s: [float(v) for v in b] for s, b in betas.items()}
    return out, fold_betas


# --------------------------------------------------------------------------
# sigma68 vs amplitude curves with event-level bootstrap within run
# --------------------------------------------------------------------------
def bootstrap_sigma68_by_run(values: np.ndarray, runs: np.ndarray, rng: np.random.Generator, n_boot: int = N_BOOTSTRAP) -> Tuple[float, float]:
    """95% CI of the pooled sigma68 from an event-level bootstrap within run.

    Residuals are resampled with replacement independently within each run
    (each entry is one event for a single pair — the three pair residuals of
    an event are never pooled here, so no iid bootstrap over linearly
    dependent residuals occurs).  Pooled values are re-centered per run on
    each replica.
    """
    values = np.asarray(values, dtype=float)
    runs = np.asarray(runs)
    order = np.argsort(runs, kind="stable")
    values = values[order]
    runs = runs[order]
    unique_runs, starts = np.unique(runs, return_index=True)
    bounds = list(starts) + [len(runs)]
    stats = []
    for _ in range(n_boot):
        rep = []
        for i in range(len(unique_runs)):
            seg = values[bounds[i] : bounds[i + 1]]
            draw = seg[rng.integers(0, len(seg), size=len(seg))]
            rep.append(draw - np.median(draw))
        stats.append(sigma68(np.concatenate(rep)))
    return float(np.percentile(stats, 2.5)), float(np.percentile(stats, 97.5))


def curves_table(pairs: pd.DataFrame, stage_cols: Dict[str, str], rng: np.random.Generator) -> Tuple[pd.DataFrame, pd.DataFrame]:
    """sigma68 vs min-amplitude bin per (sample, pair, stage) + run spread table."""
    edges = amp_bin_edges()
    pairs = pairs.copy()
    pairs["amp_bin"] = assign_amp_bins(pairs["min_amp"].to_numpy(), edges)
    rows = []
    spread_rows = []
    for sample in sorted(pairs["sample"].unique()):
        for pair in sorted(pairs["pair"].unique()):
            sel_pair = pairs[(pairs["sample"] == sample) & (pairs["pair"] == pair)]
            if len(sel_pair) == 0:
                continue
            for stage, col in stage_cols.items():
                vals_all = sel_pair[col].to_numpy()
                centered = center_per_group(vals_all, [sel_pair["run"].to_numpy()])
                for b in range(len(edges) - 1):
                    m = (sel_pair["amp_bin"] == b).to_numpy() & np.isfinite(centered)
                    n = int(m.sum())
                    lo, hi = edges[b], edges[b + 1]
                    row = {
                        "sample": sample,
                        "pair": pair,
                        "has_b2": bool(sel_pair["has_b2"].iloc[0]),
                        "stage": stage,
                        "amp_bin": b,
                        "amp_lo": float(lo),
                        "amp_hi": float(hi) if np.isfinite(hi) else None,
                        "n": n,
                        "amp_median": float(np.median(sel_pair.loc[m, "min_amp"])) if n else float("nan"),
                        "sigma68_ns": float("nan"),
                        "ci_low_ns": float("nan"),
                        "ci_high_ns": float("nan"),
                        "run_spread_std_ns": float("nan"),
                        "n_runs_used": 0,
                    }
                    if n >= MIN_BIN_COUNT:
                        v = centered[m]
                        r = sel_pair.loc[m, "run"].to_numpy()
                        row["sigma68_ns"] = sigma68(v)
                        row["ci_low_ns"], row["ci_high_ns"] = bootstrap_sigma68_by_run(v, r, rng)
                        per_run = []
                        for run in sorted(np.unique(r)):
                            vr = v[r == run]
                            if len(vr) >= MIN_RUN_BIN_COUNT:
                                s_r = sigma68(vr)
                                per_run.append(s_r)
                                spread_rows.append(
                                    {
                                        "sample": sample,
                                        "pair": pair,
                                        "stage": stage,
                                        "amp_bin": b,
                                        "run": int(run),
                                        "n": int(len(vr)),
                                        "sigma68_ns": s_r,
                                    }
                                )
                        row["n_runs_used"] = len(per_run)
                        if len(per_run) >= 2:
                            row["run_spread_std_ns"] = float(np.std(per_run, ddof=1))
                    rows.append(row)
    return pd.DataFrame(rows), pd.DataFrame(spread_rows)


def triangle_decomposition(curves: pd.DataFrame) -> pd.DataFrame:
    """Per-stave sigma from the three downstream pairs, bin by bin.

    sigma_pair(a,b)^2 = sigma_a^2 + sigma_b^2 under independence; solve the
    triangle.  Negative solutions are clipped to 0 and flagged.
    """
    rows = []
    key = ["sample", "stage", "amp_bin"]
    down = curves[~curves["has_b2"] & np.isfinite(curves["sigma68_ns"])]
    for (sample, stage, b), grp in down.groupby(key):
        if set(grp["pair"]) != {"B4-B6", "B4-B8", "B6-B8"}:
            continue
        s = {p: float(grp.loc[grp["pair"] == p, "sigma68_ns"].iloc[0]) ** 2 for p in grp["pair"]}
        v46, v48, v68 = s["B4-B6"], s["B4-B8"], s["B6-B8"]
        est = {
            "B4": (v46 + v48 - v68) / 2.0,
            "B6": (v46 + v68 - v48) / 2.0,
            "B8": (v48 + v68 - v46) / 2.0,
        }
        amp_median = float(grp["amp_median"].median())
        for stave, var in est.items():
            rows.append(
                {
                    "sample": sample,
                    "stage": stage,
                    "amp_bin": int(b),
                    "amp_median": amp_median,
                    "stave": stave,
                    "sigma68_ns": math.sqrt(max(var, 0.0)),
                    "negative_variance_clipped": bool(var < 0),
                }
            )
    return pd.DataFrame(rows)


# --------------------------------------------------------------------------
# Scaling-law fits: sigma(A) with 1/A vs 1/sqrt(A) noise term
# --------------------------------------------------------------------------
def fit_scaling(amp: np.ndarray, sig: np.ndarray, err: np.ndarray) -> Dict[str, Dict[str, float]]:
    """Weighted fits of sigma(A) = sqrt(c^2 + (k*1000/A)^p') for p'=2 (1/A)
    and sigma(A) = sqrt(c^2 + k^2*(1000/A)) (1/sqrt(A) noise term).

    Returns per-model {c, k, chi2, ndf, chi2_ndf}.  Fitting is done on a
    deterministic coarse-to-fine grid (no RNG, no fragile optimiser).
    """
    amp = np.asarray(amp, dtype=float)
    sig = np.asarray(sig, dtype=float)
    err = np.asarray(err, dtype=float)
    good = np.isfinite(amp) & np.isfinite(sig) & np.isfinite(err) & (err > 0)
    amp, sig, err = amp[good], sig[good], err[good]
    out: Dict[str, Dict[str, float]] = {}
    if len(amp) < 3:
        return out

    def model(c, k, power):
        u = 1000.0 / amp
        return np.sqrt(c**2 + (k**2) * (u**power))

    for name, power in [("inv_A", 2.0), ("inv_sqrtA", 1.0)]:
        best = (math.inf, 0.0, 0.0)
        c_hi = float(np.max(sig)) * 1.2 + 1e-6
        k_hi = float(np.max(sig)) * float(np.max(amp) / 1000.0) ** (power / 2.0) * 1.5 + 1e-6
        cs = np.linspace(0.0, c_hi, 60)
        ks = np.linspace(0.0, k_hi, 60)
        for _ in range(3):
            for c in cs:
                for k in ks:
                    chi2 = float(np.sum(((sig - model(c, k, power)) / err) ** 2))
                    if chi2 < best[0]:
                        best = (chi2, c, k)
            dc = (cs[1] - cs[0]) if len(cs) > 1 else c_hi / 60
            dk = (ks[1] - ks[0]) if len(ks) > 1 else k_hi / 60
            cs = np.linspace(max(best[1] - 2 * dc, 0.0), best[1] + 2 * dc, 25)
            ks = np.linspace(max(best[2] - 2 * dk, 0.0), best[2] + 2 * dk, 25)
        ndf = max(len(amp) - 2, 1)
        out[name] = {
            "floor_c_ns": float(best[1]),
            "coeff_k_ns": float(best[2]),
            "chi2": float(best[0]),
            "ndf": int(ndf),
            "chi2_ndf": float(best[0] / ndf),
            "n_points": int(len(amp)),
        }
    return out


# --------------------------------------------------------------------------
# Figure (nature-figure skill: quantitative grid, hero panel first)
# --------------------------------------------------------------------------
PAIR_COLORS = {
    "B4-B6": "#2f5f8a",  # blue family for downstream pairs
    "B4-B8": "#4f8fbf",
    "B6-B8": "#8ab6d6",
    "B2-B4": "#a63d40",  # warm family flags B2 (saturation-affected)
    "B2-B6": "#c9776f",
    "B2-B8": "#e0a89e",
}


def _style():
    matplotlib.rcParams.update(
        {
            "font.family": "sans-serif",
            "font.sans-serif": ["Arial", "Helvetica", "DejaVu Sans", "sans-serif"],
            "pdf.fonttype": 42,
            "svg.fonttype": "none",
            "font.size": 7,
            "axes.titlesize": 7.5,
            "axes.spines.right": False,
            "axes.spines.top": False,
            "axes.linewidth": 0.8,
            "legend.frameon": False,
        }
    )


def _plot_curve(ax, grp, color, label, marker, linestyle):
    g = grp[np.isfinite(grp["sigma68_ns"])]
    if len(g) == 0:
        return
    x = g["amp_median"].to_numpy()
    y = g["sigma68_ns"].to_numpy()
    ylo = y - g["ci_low_ns"].to_numpy()
    yhi = g["ci_high_ns"].to_numpy() - y
    ax.errorbar(
        x, y, yerr=[np.clip(ylo, 0, None), np.clip(yhi, 0, None)],
        color=color, label=label, marker=marker, linestyle=linestyle,
        markersize=3, linewidth=0.9, capsize=1.5, markerfacecolor="white" if linestyle == "--" else color,
    )


def make_figure(curves: pd.DataFrame, fits: dict, b2_sat: pd.DataFrame, out_dir: Path) -> None:
    """Six-panel quantitative grid.

    Core conclusion the figure defends: pair timing resolution improves with
    the smaller amplitude of the pair, follows a noise-over-slope 1/A term
    over a constant floor, is only mildly changed by the amp-only timewalk
    correction, and B2-containing pairs are saturation-limited above ~7 kADC.
    Hero panel (a): Sample II downstream pairs, raw vs corrected.
    """
    _style()
    fig, axes = plt.subplots(2, 3, figsize=(7.2, 4.6))
    (ax_a, ax_b, ax_c), (ax_d, ax_e, ax_f) = axes

    # (a)+(b) hero panels: downstream pairs per sample, raw vs corrected
    for ax, sample, title in [
        (ax_a, "sample_II", "a  Sample II (penetrating), downstream pairs"),
        (ax_b, "sample_I", "b  Sample I (B2-stoppers), downstream pairs"),
    ]:
        for pair in ["B4-B6", "B4-B8", "B6-B8"]:
            for stage, ls, mk in [("raw_cfd20", "--", "o"), ("timewalk_corrected", "-", "s")]:
                grp = curves[(curves["sample"] == sample) & (curves["pair"] == pair) & (curves["stage"] == stage)]
                _plot_curve(ax, grp, PAIR_COLORS[pair], None, mk, ls)
        ax.set_title(title, loc="left")
        ax.set_xlabel("min pair amplitude (ADC)")
        ax.set_ylabel(r"pair $\sigma_{68}$ (ns)")
        ax.set_xscale("log")
    from matplotlib.lines import Line2D

    ax_a.legend(
        handles=[Line2D([], [], color=PAIR_COLORS[p], lw=1.2, label=p) for p in ["B4-B6", "B4-B8", "B6-B8"]]
        + [
            Line2D([], [], color="0.3", ls="--", marker="o", markerfacecolor="white", markersize=3, lw=0.9, label="raw CFD20"),
            Line2D([], [], color="0.3", ls="-", marker="s", markersize=3, lw=0.9, label="timewalk corr (LORO)"),
        ],
        fontsize=5.2,
        loc="upper right",
        ncol=2,
    )

    # (c) per-stave sqrt(2)-derived estimates, corrected stage
    for sample, ls in [("sample_II", "-"), ("sample_I", "--")]:
        for pair in ["B4-B6", "B4-B8", "B6-B8"]:
            grp = curves[(curves["sample"] == sample) & (curves["pair"] == pair) & (curves["stage"] == "timewalk_corrected")].copy()
            grp = grp[np.isfinite(grp["sigma68_ns"])]
            if len(grp) == 0:
                continue
            ax_c.plot(
                grp["amp_median"], grp["sigma68_ns"] / math.sqrt(2.0),
                color=PAIR_COLORS[pair], linestyle=ls, marker="o", markersize=2.5, linewidth=0.9,
                label=f"{pair}/√2 {sample.replace('sample_', 'S')}" if sample == "sample_II" else None,
            )
    ax_c.set_title("c  per-stave σ_pair/√2 (corr;\n    solid SII, dashed SI)", loc="left")
    ax_c.set_xlabel("min pair amplitude (ADC)")
    ax_c.set_ylabel(r"per-stave $\sigma_{68}$ (ns)")
    ax_c.set_xscale("log")
    ax_c.legend(fontsize=5.2)

    # (d) B2-containing pairs, flagged, + B2 saturation fraction
    for pair in ["B2-B4", "B2-B6", "B2-B8"]:
        for stage, ls, mk in [("raw_cfd20", "--", "o"), ("timewalk_corrected", "-", "s")]:
            grp = curves[(curves["sample"] == "sample_II") & (curves["pair"] == pair) & (curves["stage"] == stage)]
            _plot_curve(ax_d, grp, PAIR_COLORS[pair], f"{pair} {'raw' if 'raw' in stage else 'corr'}", mk, ls)
    ax_d.axvspan(B2_SATURATION_ADC, ax_d.get_xlim()[1] if ax_d.get_xlim()[1] > B2_SATURATION_ADC else 12000, color="#a63d40", alpha=0.08)
    ax_d.set_title("d  B2 pairs, Sample II (flagged: B2 sat.)", loc="left")
    ax_d.set_xlabel("min pair amplitude (ADC)")
    ax_d.set_ylabel(r"pair $\sigma_{68}$ (ns)")
    ax_d.set_xscale("log")
    ax_d.legend(ncol=2, fontsize=5.0)

    # (e) scaling-law adequacy: chi2/ndf of 1/A vs 1/sqrt(A) noise term
    labels, x1, x2 = [], [], []
    for key, models in sorted(fits.items()):
        if "inv_A" in models and "inv_sqrtA" in models:
            labels.append(key.replace("|timewalk_corrected", "").replace("|raw_cfd20", " raw").replace("sample_", "S").replace("|", "\n"))
            x1.append(models["inv_A"]["chi2_ndf"])
            x2.append(models["inv_sqrtA"]["chi2_ndf"])
    xpos = np.arange(len(labels))
    ax_e.bar(xpos - 0.18, x1, width=0.36, color="#2f5f8a", label=r"noise $\propto 1/A$")
    ax_e.bar(xpos + 0.18, x2, width=0.36, color="#c9776f", label=r"noise $\propto 1/\sqrt{A}$")
    ax_e.axhline(1.0, color="0.4", lw=0.7, ls=":")
    ax_e.set_xticks(xpos)
    ax_e.set_xticklabels(labels, fontsize=4.6)
    ax_e.set_ylabel(r"fit $\chi^2$/ndf")
    ax_e.set_title("e  σ(A) model χ²/ndf (corrected)", loc="left")
    ax_e.legend(fontsize=5.2)

    # (f) B2 saturation fraction per sample
    if len(b2_sat):
        for sample, color in [("sample_I", "#a63d40"), ("sample_II", "#2f5f8a")]:
            g = b2_sat[b2_sat["sample"] == sample]
            if len(g):
                ax_f.bar(
                    [f"{sample.replace('sample_', 'S')}"],
                    [100.0 * g["frac_b2_ge7000"].iloc[0]],
                    color=color, width=0.5,
                )
    ax_f.set_ylabel("selected B2 pulses ≥ 7000 ADC (%)")
    ax_f.set_title("f  B2 saturation occupancy", loc="left")

    fig.tight_layout()
    fig.savefig(out_dir / "fig_s22_sigma_vs_amplitude.png", dpi=400)
    fig.savefig(out_dir / "fig_s22_sigma_vs_amplitude.pdf")
    plt.close(fig)


# --------------------------------------------------------------------------
# Report
# --------------------------------------------------------------------------
def df_to_markdown(df: pd.DataFrame, floatfmt: str = ".3f") -> str:
    """Minimal markdown table (avoids the optional `tabulate` dependency)."""

    def fmt(v):
        if isinstance(v, float):
            return "nan" if not np.isfinite(v) else format(v, floatfmt)
        return "" if v is None else str(v)

    cols = list(df.columns)
    lines = ["| " + " | ".join(cols) + " |", "|" + "|".join(["---"] * len(cols)) + "|"]
    for _, row in df.iterrows():
        lines.append("| " + " | ".join(fmt(row[c]) for c in cols) + " |")
    return "\n".join(lines)


def write_report(out_dir: Path, summary: dict, curves: pd.DataFrame, tri: pd.DataFrame) -> None:
    lines = [
        "# S22 — Per-stave timing resolution vs amplitude",
        "",
        f"- Generated: {time.strftime('%Y-%m-%d %H:%M:%S UTC', time.gmtime())}",
        f"- Git commit: `{summary['git_commit']}`",
        f"- Runs: Sample I {SAMPLE_RUNS['sample_I']} / Sample II {SAMPLE_RUNS['sample_II']} (disjoint sets)",
        "- Selection: baseline-subtracted amplitude A > 1000 ADC (standard anchor)",
        "- Pickoff: CFD20, rising-edge constrained (last below->above crossing at or before the peak,",
        "  linear interpolation; mv4/s05c fix pattern)",
        "- Residuals: per-pair (right - left - TOF), centered by the per-(pair, run) median before pooling",
        "  (review: uncentered pooling mixes cable-delay offsets into sigma). sigma68 = (q84-q16)/2.",
        "- Binning: min(A_left, A_right); edges "
        + ", ".join(str(int(e)) for e in AMP_BIN_EDGES[:-1])
        + ", inf ADC; bins quoted only with n >= " + str(MIN_BIN_COUNT) + ".",
        "- Errors: event-level bootstrap within run (95% CI); run-to-run spread quoted separately.",
        "  No pooled iid bootstrap over the three linearly dependent pair residuals is performed.",
        "- Timewalk: analytic AMP-ONLY correction (features 1000/A, sqrt(1000/A), log1p(A/1000) per stave;",
        "  s03a amp_only basis, MV4b 1/A-leading form), fit as a pair-difference model on per-(pair,run)-",
        "  centered residuals, evaluated LEAVE-ONE-RUN-OUT within each sample (every corrected number is",
        "  out-of-sample at run level).",
        "- Per-stave: sigma_pair/sqrt(2) under the ASSUMPTION of independent equal-variance stave errors;",
        "  triangle decomposition cross-check where all three downstream pairs populate a bin.",
        "",
        "## Key numbers",
        "",
    ]
    for sample in ["sample_II", "sample_I"]:
        lines.append(f"### {sample}")
        lines.append("")
        sub = curves[(curves["sample"] == sample) & np.isfinite(curves["sigma68_ns"])]
        cols = ["pair", "stage", "amp_lo", "amp_hi", "n", "amp_median", "sigma68_ns", "ci_low_ns", "ci_high_ns", "run_spread_std_ns", "n_runs_used"]
        if len(sub):
            lines.append(df_to_markdown(sub[cols]))
        else:
            lines.append("(no populated bins)")
        lines.append("")
    lines.append("## Scaling-law fits (sigma(A) = sqrt(c^2 + k^2 (1000/A)^p), p=2 vs p=1)")
    lines.append("")
    lines.append("```json")
    lines.append(json.dumps(summary["scaling_fits"], indent=2))
    lines.append("```")
    lines.append("")
    if len(tri):
        lines.append("## Triangle per-stave decomposition (cross-check)")
        lines.append("")
        lines.append(df_to_markdown(tri))
        lines.append("")
    lines.extend(
        [
            "## Caveats (honest)",
            "",
            "- The sqrt(2) per-stave conversion assumes independent, equal-variance stave errors; any",
            "  common-mode jitter (clock, trigger, correlated pickup) makes it an underestimate of the",
            "  true single-stave resolution and the triangle decomposition can return negative variances",
            "  (flagged where clipped).",
            "- B2-containing pairs are saturation-contaminated: 30-40% of selected B2 pulses sit above",
            "  ~7000 ADC where the amplitude (and hence both the CFD threshold and the timewalk feature)",
            "  is compressed. B2 curves are flagged and excluded from headline per-stave claims.",
            "- Binning by min pair amplitude attributes the resolution to the smaller pulse; the partner",
            "  amplitude is unconstrained above it (2D profiling would sharpen the attribution and is a",
            "  natural follow-up).",
            "- Sample I downstream statistics are intrinsically low (B2-stopper topology): several bins do",
            "  not reach n >= " + str(MIN_BIN_COUNT) + " and are left empty rather than quoted.",
            "- The timewalk fit target is the pair difference itself; with per-(pair,run) centering this",
            "  is free of the other-stave-mean attenuation bias flagged in the review for s03a, but it",
            "  still attributes shared amplitude-correlated effects to the individual staves.",
            "- The 10 ns sampling period is coarse relative to the sub-ns corrected resolution: sigma68",
            "  values inherit interpolation/quantisation structure, and bins are not fully independent of",
            "  the CFD phase.",
            "- This study reuses the same runs as earlier S02/S03 timing work (no fresh confirmation",
            "  partition); treat small raw-vs-corrected differences with the program-level multiplicity",
            "  caution from the external review.",
        ]
    )
    (out_dir / "REPORT.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


# --------------------------------------------------------------------------
# Main
# --------------------------------------------------------------------------
def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--raw-dir", default="data/root/root", help="dir with hrdb_run_NNNN.root")
    parser.add_argument("--out", default=None, help="output dir (default reports/s22_timing_vs_amplitude_<stamp>)")
    parser.add_argument("--max-events", type=int, default=0, help="cap events per run (0 = all)")
    parser.add_argument("--n-bootstrap", type=int, default=N_BOOTSTRAP)
    args = parser.parse_args()
    t0 = time.time()

    raw_dir = Path(args.raw_dir)
    out_dir = Path(args.out) if args.out else Path("reports") / f"s22_timing_vs_amplitude_{int(time.time())}"
    out_dir.mkdir(parents=True, exist_ok=True)
    rng = np.random.default_rng(RANDOM_SEED)

    # ---- load ----
    tables = []
    run_meta = []
    input_hashes = {}
    for sample, runs in sorted(SAMPLE_RUNS.items()):
        for run in sorted(runs):
            path = raw_file(raw_dir, run)
            if not path.exists():
                raise FileNotFoundError(path)
            input_hashes[str(path)] = sha256_file(path)
            tab, meta = load_run_pairs(raw_dir, run, sample, max_events=args.max_events)
            run_meta.append(meta)
            if len(tab):
                tables.append(tab)
            print(f"[s22] run {run} ({sample}): events={meta['n_events']} pair_rows={len(tab)}", flush=True)
    pairs = pd.concat(tables, ignore_index=True)
    meta_df = pd.DataFrame(run_meta)
    meta_df.to_csv(out_dir / "s22_run_meta.csv", index=False)

    # ---- timewalk correction, leave-one-run-out per sample ----
    corrected = np.full(len(pairs), np.nan)
    loro_betas = {}
    for sample in sorted(SAMPLE_RUNS):
        col, betas = loro_corrected_residuals(pairs, sample)
        mask = (pairs["sample"] == sample).to_numpy()
        corrected[mask] = col[mask]
        loro_betas[sample] = betas
    pairs["corrected_residual_ns"] = corrected

    # ---- curves ----
    stage_cols = {"raw_cfd20": "raw_residual_ns", "timewalk_corrected": "corrected_residual_ns"}
    curves, spread = curves_table(pairs, stage_cols, rng)
    curves["sigma68_per_stave_sqrt2_ns"] = curves["sigma68_ns"] / math.sqrt(2.0)
    curves.to_csv(out_dir / "s22_curves.csv", index=False)
    spread.to_csv(out_dir / "s22_run_spread.csv", index=False)
    tri = triangle_decomposition(curves)
    tri.to_csv(out_dir / "s22_triangle_decomposition.csv", index=False)

    # ---- scaling fits (downstream pairs, both stages, per sample) ----
    fits = {}
    for (sample, pair, stage), grp in curves[~curves["has_b2"]].groupby(["sample", "pair", "stage"]):
        g = grp[np.isfinite(grp["sigma68_ns"])]
        err = 0.5 * (g["ci_high_ns"] - g["ci_low_ns"]).to_numpy()
        res = fit_scaling(g["amp_median"].to_numpy(), g["sigma68_ns"].to_numpy(), err)
        if res:
            fits[f"{sample}|{pair}|{stage}"] = res

    # ---- B2 saturation bookkeeping ----
    b2_rows = []
    for sample in sorted(SAMPLE_RUNS):
        m = meta_df[meta_df["sample"] == sample]
        n_b2 = int(m["n_selected_B2"].sum())
        n_sat = int(m["n_selected_b2_saturated_ge7000"].sum())
        b2_rows.append(
            {
                "sample": sample,
                "n_selected_b2": n_b2,
                "n_b2_ge7000": n_sat,
                "frac_b2_ge7000": (n_sat / n_b2) if n_b2 else float("nan"),
            }
        )
    b2_sat = pd.DataFrame(b2_rows)
    b2_sat.to_csv(out_dir / "s22_b2_saturation.csv", index=False)

    # ---- figure ----
    fit_view = {k: v for k, v in fits.items() if k.endswith("timewalk_corrected")}
    make_figure(curves, fit_view, b2_sat, out_dir)

    # ---- summary ----
    def stage_anchor(sample: str, stage: str) -> dict:
        sub = curves[(curves["sample"] == sample) & (curves["stage"] == stage) & ~curves["has_b2"] & np.isfinite(curves["sigma68_ns"])]
        out = {}
        for pair, grp in sub.groupby("pair"):
            lo = grp.sort_values("amp_bin").iloc[0]
            hi = grp.sort_values("amp_bin").iloc[-1]
            out[pair] = {
                "lowest_bin": {"amp_median": float(lo["amp_median"]), "sigma68_ns": float(lo["sigma68_ns"])},
                "highest_bin": {"amp_median": float(hi["amp_median"]), "sigma68_ns": float(hi["sigma68_ns"])},
                "per_stave_sqrt2_highest_bin_ns": float(hi["sigma68_ns"]) / math.sqrt(2.0),
            }
        return out

    preferred = {}
    for key, models in fits.items():
        if "inv_A" in models and "inv_sqrtA" in models:
            preferred[key] = "inv_A" if models["inv_A"]["chi2_ndf"] <= models["inv_sqrtA"]["chi2_ndf"] else "inv_sqrtA"

    summary = {
        "study": "S22",
        "title": "per-stave timing resolution vs amplitude (raw CFD20 + amp-only timewalk, LORO)",
        "git_commit": git_commit(),
        "random_seed": RANDOM_SEED,
        "n_bootstrap": int(args.n_bootstrap),
        "selection": {"amplitude_cut_adc": AMPLITUDE_CUT_ADC, "cfd_fraction": CFD_FRACTION},
        "runs": SAMPLE_RUNS,
        "amp_bin_edges": [e if np.isfinite(e) else None for e in AMP_BIN_EDGES],
        "centering": "per-(pair, run) median subtracted before pooling",
        "bootstrap": "event-level within run; no pooled iid bootstrap over dependent pair residuals",
        "per_stave_assumption": "sigma_pair/sqrt(2) assumes independent equal-variance stave errors",
        "timewalk": {
            "basis": TIMEWALK_FEATURES,
            "evaluation": "leave-one-run-out within sample",
            "ridge_alpha": RIDGE_ALPHA,
            "loro_betas": loro_betas,
        },
        "anchors": {
            sample: {stage: stage_anchor(sample, stage) for stage in stage_cols}
            for sample in sorted(SAMPLE_RUNS)
        },
        "scaling_fits": fits,
        "scaling_preferred_model": preferred,
        "b2_saturation": b2_rows,
        "n_pair_rows": int(len(pairs)),
        "inputs_sha256": input_hashes,
        "runtime_sec": round(time.time() - t0, 1),
    }
    (out_dir / "s22_summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    write_report(out_dir, summary, curves, tri)
    print(json.dumps({"out_dir": str(out_dir), "n_pair_rows": int(len(pairs)), "runtime_sec": summary["runtime_sec"]}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
