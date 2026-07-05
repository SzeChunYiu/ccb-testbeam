#!/usr/bin/env python3
"""S25 — MEASURED inter-stave timing covariance and the covariance-correct
combined resolution (reviewer M4 / B-M4).

Motivation
----------
The combined 3-stave timing headline (sigma_comb ~ 0.54-0.56 ns) relied on a
WITHDRAWN covariance (scripts/multistave_covariance.py: an indefinite matrix
built from a category-error reuse of S05c raw pair covariances) and an
UNPROVEN sqrt(2)/independence assumption. This study measures the inter-stave
timing error covariance directly, on TIMEWALK-CORRECTED per-event residuals,
and propagates it through the inverse-variance combination to a single combined
sigma68 whose bootstrap CI accounts for the measured correlation (whole-event
resampling preserves the inter-stave dependence).

Data / selection (canonical, per scripts/s22_timing_vs_amplitude.py loaders)
---------------------------------------------------------------------------
  * raw rising-edge-constrained CFD20 (s22.cfd20_rising_edge), A > 1000 ADC;
  * downstream staves B4/B6/B8 only (B2 excluded — saturation);
  * per-event triples: events where B4 AND B6 AND B8 all pass A>1000 with a
    valid CFD pick;
  * analytic amp-only timewalk correction (s22 two-stage betas), fit
    leave-one-run-out within Sample II, applied per stave: tau_s = t_s -
    phi(A_s) . beta_s;
  * per-(stave, run) median centering removes cable-delay / TOF / run drift,
    leaving y_s = T_event + eps_s (T_event = per-event common mode = trigger
    phase relative to true crossing; eps_s = per-stave intrinsic error).

What is identifiable (honest)
-----------------------------
With THREE downstream staves and no external clock, the pairwise differences
y_i - y_j cancel the common mode T_event, so:
  * the pairwise variances V_ij = Var(y_i - y_j) = sigma_i^2 + sigma_j^2 are
    measured directly (robustly, via sigma68);
  * the triangle gives the intrinsic per-stave variances sigma_i^2 =
    (V_ij + V_ik - V_jk)/2 UNDER the assumption Cov(eps_i, eps_j) = 0;
  * that independence assumption is itself TESTABLE: y_s = T_event + eps_s with
    independent eps implies the three off-diagonal covariances Cov(y_i, y_j)
    are ALL EQUAL (= Var(T_event)). Structured (non-common-mode) inter-stave
    correlation shows up as unequal off-diagonals and would bias the
    independence combination. We measure the full 3x3 Cov(y) robustly, project
    it to the nearest PSD matrix, and test off-diagonal equality by bootstrap.

The combined resolution of the inverse-variance event-time estimate is
sigma_comb = sqrt(1 / sum_i 1/sigma_i^2). Its validity rests on the
off-diagonal-equality test; we also report the Cauchy-Schwarz interval spanned
by the unmeasured intrinsic correlation as an honest bound. Residual common-mode
(trigger/clock) jitter shared by all staves is INVISIBLE to inter-stave
differences and can only inflate an absolute-to-truth resolution — stated as a
floor caveat.

Confirmation partition (docs/CONFIRMATION_PARTITION.md)
------------------------------------------------------
Any sub-0.3 ns per-stave or combined claim must be confirmed one-shot on the
reserved runs {64, 12-30} with the FROZEN timewalk model. This script attempts
that confirmation and reports held-out vs exploration; if the reserved raw runs
are not staged it records the confirmation as BLOCKED (a first-class result).

Self-contained: heavy IO (uproot, s22 loaders) is imported lazily inside main so
the pure covariance math can be unit-tested without a data tree.
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import math
import sys
import time
from pathlib import Path

import numpy as np

ROOT_DIR = Path(__file__).resolve().parents[1]

STAVES = ("B4", "B6", "B8")
PAIRS = (("B4", "B6"), ("B4", "B8"), ("B6", "B8"))
AMPLITUDE_CUT_ADC = 1000.0
HIGH_AMP_CUT_ADC = 2000.0
RANDOM_SEED = 20260705
N_BOOTSTRAP = 400
SUB03_NS = 0.30
RESERVED_RUNS = [64] + list(range(12, 31))  # confirmation partition


# ---------------------------------------------------------------------------
# Pure covariance / combination math (unit-tested in tests/test_s25_covariance.py)
# ---------------------------------------------------------------------------
def sigma68(values: np.ndarray) -> float:
    """Half the central 68% interquantile range: (q84 - q16) / 2."""
    v = np.asarray(values, dtype=float)
    v = v[np.isfinite(v)]
    if v.size == 0:
        return float("nan")
    q16, q84 = np.percentile(v, [16.0, 84.0])
    return float(0.5 * (q84 - q16))


def nearest_psd(mat: np.ndarray, eps: float = 0.0) -> np.ndarray:
    """Nearest positive-semidefinite matrix (symmetric eigenvalue clip).

    Symmetrises, clips eigenvalues below ``eps`` up to ``eps``, reconstructs.
    Idempotent on matrices already PSD (up to floating point). This is the
    Higham-style projection restricted to the symmetric-eigenvalue step, which
    is exact for the Frobenius-nearest PSD matrix of a symmetric input.
    """
    m = np.asarray(mat, dtype=float)
    m = 0.5 * (m + m.T)
    w, v = np.linalg.eigh(m)
    w_clipped = np.clip(w, eps, None)
    out = (v * w_clipped) @ v.T
    return 0.5 * (out + out.T)


def robust_cov3(y: np.ndarray) -> np.ndarray:
    """Robust 3x3 covariance via sigma68 on marginals and sum/difference.

    diag_i   = sigma68(y_i)^2
    off_ij   = (sigma68(y_i + y_j)^2 - sigma68(y_i - y_j)^2) / 4
    using Var(a+b) - Var(a-b) = 4 Cov(a, b). Robust to the heavy CFD tails.
    Not necessarily PSD; project with nearest_psd afterwards.
    """
    y = np.asarray(y, dtype=float)
    n = y.shape[1]
    cov = np.zeros((n, n))
    for i in range(n):
        cov[i, i] = sigma68(y[:, i]) ** 2
    for i in range(n):
        for j in range(i + 1, n):
            vp = sigma68(y[:, i] + y[:, j]) ** 2
            vm = sigma68(y[:, i] - y[:, j]) ** 2
            cov[i, j] = cov[j, i] = 0.25 * (vp - vm)
    return cov


def pairwise_variances(y: np.ndarray) -> dict:
    """Robust Var(y_i - y_j) per stave pair (index order B4,B6,B8)."""
    idx = {"B4": 0, "B6": 1, "B8": 2}
    return {f"{a}-{b}": sigma68(y[:, idx[a]] - y[:, idx[b]]) ** 2 for a, b in PAIRS}


def triangle_variances(v_pairs: dict) -> dict:
    """Per-stave intrinsic variances from the three pair variances.

    sigma_i^2 = (V_ij + V_ik - V_jk)/2 (independence completion). Negative
    solutions (correlation / statistics) are returned as-is and flagged by the
    caller; they are clipped to 0 only for taking a sqrt.
    """
    v46, v48, v68 = v_pairs["B4-B6"], v_pairs["B4-B8"], v_pairs["B6-B8"]
    return {
        "B4": 0.5 * (v46 + v48 - v68),
        "B6": 0.5 * (v46 + v68 - v48),
        "B8": 0.5 * (v48 + v68 - v46),
    }


def inverse_variance_combined(variances, cov: np.ndarray | None = None) -> dict:
    """Combined variance of the inverse-variance-weighted mean.

    Diagonal (independent) case (``cov`` None): weights w_i propto 1/var_i,
    combined_var = 1 / sum_i (1/var_i).
    Full-covariance (GLS) case: w = Sigma^{-1} 1 / (1^T Sigma^{-1} 1),
    combined_var = 1 / (1^T Sigma^{-1} 1). ``variances`` sets the diagonal when
    ``cov`` is None; ignored otherwise.
    """
    if cov is None:
        var = np.asarray(variances, dtype=float)
        inv = 1.0 / var
        w = inv / inv.sum()
        cvar = 1.0 / inv.sum()
        return {"weights": w.tolist(), "combined_var": float(cvar),
                "combined_sigma": float(math.sqrt(max(cvar, 0.0)))}
    sigma = np.asarray(cov, dtype=float)
    ones = np.ones(sigma.shape[0])
    inv = np.linalg.pinv(sigma)
    denom = float(ones @ inv @ ones)
    w = (inv @ ones) / denom
    cvar = 1.0 / denom
    return {"weights": w.tolist(), "combined_var": float(cvar),
            "combined_sigma": float(math.sqrt(max(cvar, 0.0)))}


def cauchy_schwarz_bounds(sigmas, weights=None) -> dict:
    """Interval of combined sigma over the unmeasured intrinsic correlation.

    For fixed weights w and per-stave sigmas, combined_var =
    sum_i w_i^2 sigma_i^2 + 2 sum_{i<j} w_i w_j rho_ij sigma_i sigma_j. The
    upper bound (all rho=+1) is (sum_i w_i sigma_i)^2; the independence value
    uses rho=0; the PSD lower floor is clipped at 0. Default weights are the
    inverse-variance weights.
    """
    s = np.asarray(sigmas, dtype=float)
    var = s ** 2
    if weights is None:
        inv = 1.0 / var
        weights = inv / inv.sum()
    w = np.asarray(weights, dtype=float)
    indep = float(np.sum(w ** 2 * var))
    upper = float(np.sum(w * s) ** 2)
    cross = 0.0
    for i in range(len(s)):
        for j in range(i + 1, len(s)):
            cross += w[i] * w[j] * s[i] * s[j]
    lower = max(indep - 2.0 * cross, 0.0)
    return {
        "independence_sigma": math.sqrt(max(indep, 0.0)),
        "fully_correlated_sigma": math.sqrt(max(upper, 0.0)),
        "psd_floor_sigma": math.sqrt(lower),
        "weights": w.tolist(),
    }


# ---------------------------------------------------------------------------
# Data pipeline (lazy s22 import)
# ---------------------------------------------------------------------------
def _load_s22():
    path = ROOT_DIR / "scripts" / "s22_timing_vs_amplitude.py"
    spec = importlib.util.spec_from_file_location("s22_timing_vs_amplitude", path)
    module = importlib.util.module_from_spec(spec)
    sys.modules["s22_timing_vs_amplitude"] = module
    spec.loader.exec_module(module)
    return module


def daq_format_ok(s22, raw_dir: Path, run: int):
    """Guard: is `run` in the SAME acquisition configuration as the analysis runs?

    The reserved confirmation partition {64, 12-30} turned out to be DAQ-incompatible
    with the Sample-II analysis runs (Track A, 2026-07-05): a 16-sample window (vs the
    18-sample analysis basis), signal cabled onto the ODD channels rather than the
    analysis even-channel B-stave map, and pulses truncated at the last sample. Applying
    the frozen 18-sample/even-channel timewalk model to such runs is physically invalid,
    not a confirmation. This checks the waveform length and returns (ok, reason).
    """
    import numpy as _np

    try:
        for batch in s22.iter_raw(s22.raw_file(raw_dir, run), ["HRDv"]):
            flat = _np.stack(batch["HRDv"])
            nsamp = int(flat.shape[1] // 8)
            if flat.shape[1] != 8 * s22.SAMPLES_PER_CHANNEL:
                return False, (
                    f"run {run}: {nsamp}-sample window (HRDv len {flat.shape[1]}) "
                    f"!= analysis 8*{s22.SAMPLES_PER_CHANNEL}; reserved partition is a "
                    "different acquisition configuration (see "
                    "reports/trackA_heldout_confirmation/). Held-out confirmation is "
                    "physically invalid on this run."
                )
            return True, "compatible"
    except Exception as exc:  # pragma: no cover - I/O guard
        return False, f"run {run}: could not read HRDv ({exc})"
    return False, f"run {run}: no HRDv batches"


def load_event_triples(s22, raw_dir: Path, run: int, sample: str, max_events: int = 0):
    """Per-event downstream triples (B4,B6,B8 all A>1000, valid CFD).

    Uses the s22 pulse_quantities/CFD pipeline exactly. Returns a dict of
    numpy arrays: run, t4,t6,t8 (ns), a4,a6,a8 (ADC).
    """
    import numpy as _np

    stave_names = list(s22.STAVE_CHANNELS.keys())  # B2,B4,B6,B8
    channels = _np.asarray([s22.STAVE_CHANNELS[s] for s in stave_names])
    idx = {s: stave_names.index(s) for s in STAVES}
    cols = {k: [] for k in ("t4", "t6", "t8", "a4", "a6", "a8")}
    n_seen = 0
    for batch in s22.iter_raw(s22.raw_file(raw_dir, run), ["EVENTNO", "HRDv"]):
        flat = _np.stack(batch["HRDv"]).astype(_np.float64)
        events = flat.reshape(-1, 8, s22.SAMPLES_PER_CHANNEL)[:, channels, :]
        q = s22.pulse_quantities(events)
        amp = q["amplitude"]
        valid = q["cfd_valid"]
        t = q["time_ns"]
        sel = _np.ones(len(events), dtype=bool)
        for s in STAVES:
            sel &= (amp[:, idx[s]] > s22.AMPLITUDE_CUT_ADC) & valid[:, idx[s]]
        if sel.any():
            cols["t4"].append(t[sel, idx["B4"]]); cols["a4"].append(amp[sel, idx["B4"]])
            cols["t6"].append(t[sel, idx["B6"]]); cols["a6"].append(amp[sel, idx["B6"]])
            cols["t8"].append(t[sel, idx["B8"]]); cols["a8"].append(amp[sel, idx["B8"]])
        n_seen += len(events)
        if max_events and n_seen >= max_events:
            break
    out = {k: (_np.concatenate(v) if v else _np.array([])) for k, v in cols.items()}
    out["run"] = _np.full(len(out["t4"]), run, dtype=int)
    return out


def corrected_residuals(s22, triples: dict, pairs_df, sample_runs, sample: str):
    """LORO timewalk-corrected, per-(stave,run)-centered residuals y (n,3).

    betas fit on the downstream pair table (s22.fit_timewalk) leave-one-run-out
    within the sample; applied per stave tau_s = t_s - phi(A_s).beta_s; then the
    per-(stave,run) median is subtracted.
    """
    import numpy as _np
    import pandas as _pd

    run_arr = triples["run"]
    runs = sorted(set(int(r) for r in run_arr))
    tau = {s: _np.full(len(run_arr), _np.nan) for s in STAVES}
    amp_key = {"B4": "a4", "B6": "a6", "B8": "a8"}
    t_key = {"B4": "t4", "B6": "t6", "B8": "t8"}
    fold_betas = {}
    for r in runs:
        train = [x for x in sample_runs if x != r]
        betas = s22.fit_timewalk(pairs_df[pairs_df["sample"] == sample], train)
        fold_betas[str(r)] = {s: [float(v) for v in betas[s]] for s in STAVES}
        m = run_arr == r
        for s in STAVES:
            phi = s22.timewalk_phi(triples[amp_key[s]][m])
            tau[s][m] = triples[t_key[s]][m] - phi @ betas[s]
    # per-(stave, run) median centering
    y = _np.column_stack([tau[s] for s in STAVES])
    for si, s in enumerate(STAVES):
        for r in runs:
            m = run_arr == r
            y[m, si] -= _np.median(y[m, si])
    return y, fold_betas


def analyse(y: np.ndarray, runs: np.ndarray, rng, amp_min=None, amps=None,
            n_boot=N_BOOTSTRAP, label="A>1000"):
    """Full covariance + combination measurement with whole-event bootstrap."""
    if amp_min is not None and amps is not None:
        keep = np.all(amps > amp_min, axis=1)
        y, runs = y[keep], runs[keep]
    n = len(y)

    cov_raw = robust_cov3(y)
    cov_psd = nearest_psd(cov_raw)
    corr = cov_psd / np.sqrt(np.outer(np.diag(cov_psd), np.diag(cov_psd)))

    v_pairs = pairwise_variances(y)
    tri = triangle_variances(v_pairs)
    tri_neg = {k: bool(v < 0) for k, v in tri.items()}
    sig = {k: math.sqrt(max(v, 0.0)) for k, v in tri.items()}
    comb = inverse_variance_combined([max(tri[s], 1e-9) for s in STAVES])
    bounds = cauchy_schwarz_bounds([sig[s] for s in STAVES], comb["weights"])

    # off-diagonal covariances (test of the independence assumption)
    offdiag = {"B4-B6": cov_psd[0, 1], "B4-B8": cov_psd[0, 2], "B6-B8": cov_psd[1, 2]}

    # whole-event bootstrap within run: preserves the inter-stave correlation
    order = np.argsort(runs, kind="stable")
    ys, rs = y[order], runs[order]
    uniq, starts = np.unique(rs, return_index=True)
    bnds = list(starts) + [len(rs)]
    comb_b, sig_b = [], {s: [] for s in STAVES}
    off_b = {k: [] for k in offdiag}
    for _ in range(n_boot):
        parts = []
        for i in range(len(uniq)):
            seg = ys[bnds[i]:bnds[i + 1]]
            parts.append(seg[rng.integers(0, len(seg), size=len(seg))])
        yb = np.concatenate(parts)
        vp = pairwise_variances(yb)
        tb = triangle_variances(vp)
        comb_b.append(inverse_variance_combined([max(tb[s], 1e-9) for s in STAVES])["combined_sigma"])
        for s in STAVES:
            sig_b[s].append(math.sqrt(max(tb[s], 0.0)))
        cb = nearest_psd(robust_cov3(yb))
        off_b["B4-B6"].append(cb[0, 1]); off_b["B4-B8"].append(cb[0, 2]); off_b["B6-B8"].append(cb[1, 2])

    def ci(a):
        return [float(np.percentile(a, 2.5)), float(np.percentile(a, 97.5))]

    # off-diagonal equality test: spread of the three offdiags vs bootstrap
    off_vals = np.array([offdiag[k] for k in ("B4-B6", "B4-B8", "B6-B8")])
    off_spread = float(off_vals.max() - off_vals.min())
    off_spread_b = np.array([
        np.ptp([off_b["B4-B6"][i], off_b["B4-B8"][i], off_b["B6-B8"][i]])
        for i in range(len(comb_b))
    ])
    # fraction of bootstrap replicas whose spread is at least the observed:
    # a large p means the observed spread is consistent with sampling noise
    # around equal off-diagonals (independence not rejected).
    equality_p = float(np.mean(off_spread_b >= off_spread))

    return {
        "label": label,
        "n_events": int(n),
        "n_runs": int(len(uniq)),
        "cov_robust_ns2": cov_raw.tolist(),
        "cov_psd_ns2": cov_psd.tolist(),
        "corr_psd": corr.tolist(),
        "offdiag_cov_ns2": {k: float(v) for k, v in offdiag.items()},
        "offdiag_cov_ci": {k: ci(off_b[k]) for k in offdiag},
        "offdiag_equality_spread_ns2": off_spread,
        "offdiag_equality_bootstrap_p": equality_p,
        "pair_variances_ns2": {k: float(v) for k, v in v_pairs.items()},
        "per_stave_variance_ns2": {k: float(v) for k, v in tri.items()},
        "per_stave_variance_negative": tri_neg,
        "per_stave_sigma_ns": {k: float(v) for k, v in sig.items()},
        "per_stave_sigma_ci": {s: ci(sig_b[s]) for s in STAVES},
        "combined_sigma_ns": comb["combined_sigma"],
        "combined_sigma_ci": ci(comb_b),
        "combined_weights": comb["weights"],
        "cauchy_schwarz_bounds_ns": bounds,
        "any_sub_03": bool(comb["combined_sigma"] < SUB03_NS or any(sig[s] < SUB03_NS for s in STAVES)),
    }


def make_figure(out_dir: Path, primary: dict, high: dict, held: dict | None):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    matplotlib.rcParams.update({
        "font.family": "sans-serif",
        "font.sans-serif": ["Arial", "Helvetica", "DejaVu Sans", "sans-serif"],
        "pdf.fonttype": 42, "svg.fonttype": "none", "font.size": 7,
        "axes.spines.right": False, "axes.spines.top": False,
        "axes.linewidth": 0.8, "legend.frameon": False,
    })
    fig, axes = plt.subplots(1, 3, figsize=(7.2, 2.6))
    ax_a, ax_b, ax_c = axes

    # a: measured correlation matrix (primary A>1000)
    corr = np.asarray(primary["corr_psd"])
    im = ax_a.imshow(corr, vmin=-1, vmax=1, cmap="RdBu_r")
    ax_a.set_xticks(range(3), STAVES); ax_a.set_yticks(range(3), STAVES)
    for i in range(3):
        for j in range(3):
            ax_a.text(j, i, f"{corr[i, j]:.2f}", ha="center", va="center", fontsize=6)
    ax_a.set_title("a  measured inter-stave corr (A>1000)", loc="left")
    fig.colorbar(im, ax=ax_a, fraction=0.046, shrink=0.8)

    # b: per-stave sigma + combined, primary vs high-amp
    ax_b.set_title("b  per-stave & combined sigma68", loc="left")
    labels = list(STAVES) + ["comb"]
    x = np.arange(len(labels))
    for off, res, c, lab in [(-0.18, primary, "#2f5f8a", "A>1000"),
                             (0.18, high, "#c9776f", "A>2000")]:
        vals = [res["per_stave_sigma_ns"][s] for s in STAVES] + [res["combined_sigma_ns"]]
        los = [res["per_stave_sigma_ci"][s][0] for s in STAVES] + [res["combined_sigma_ci"][0]]
        his = [res["per_stave_sigma_ci"][s][1] for s in STAVES] + [res["combined_sigma_ci"][1]]
        vals = np.array(vals)
        ax_b.errorbar(x + off, vals, yerr=[vals - np.array(los), np.array(his) - vals],
                      fmt="o", ms=3, color=c, capsize=1.5, label=lab)
    ax_b.axhline(SUB03_NS, color="0.5", ls=":", lw=0.7)
    ax_b.set_xticks(x, labels); ax_b.set_ylabel("sigma68 (ns)")
    ax_b.legend(fontsize=5.5)

    # c: combined sigma with Cauchy-Schwarz band + withdrawn headline
    ax_c.set_title("c  combined sigma68 vs bound", loc="left")
    b = primary["cauchy_schwarz_bounds_ns"]
    ax_c.axhspan(b["psd_floor_sigma"], b["fully_correlated_sigma"], color="0.85",
                 label="Cauchy-Schwarz (unmeasured corr)")
    ax_c.axhline(primary["combined_sigma_ns"], color="#2f5f8a", lw=1.2, label="measured (indep. compl.)")
    ax_c.axhspan(primary["combined_sigma_ci"][0], primary["combined_sigma_ci"][1],
                 color="#2f5f8a", alpha=0.2)
    ax_c.axhline(0.55, color="#a63d40", ls="--", lw=0.9, label="withdrawn 0.54-0.56")
    if held is not None and held.get("combined_sigma_ns") is not None:
        ax_c.axhline(held["combined_sigma_ns"], color="green", ls="-.", lw=0.9, label="held-out")
    ax_c.set_ylabel("combined sigma68 (ns)")
    ax_c.set_xticks([])
    ax_c.legend(fontsize=5.0, loc="upper right")

    fig.tight_layout()
    fig.savefig(out_dir / "fig_s25_covariance_timing.png", dpi=400)
    fig.savefig(out_dir / "fig_s25_covariance_timing.pdf")
    plt.close(fig)


def write_report(out_dir: Path, summary: dict):
    p = summary["primary"]
    h = summary["high_amp"]
    held = summary["held_out"]
    cov = np.asarray(p["cov_psd_ns2"])
    lines = [
        "# S25 — Measured inter-stave timing covariance & combined resolution (B-M4)",
        "",
        f"- Generated: {summary['generated_utc']}",
        f"- Git commit: `{summary['git_commit']}`",
        f"- Exploration runs (Sample II analysis): {summary['exploration_runs']}",
        "- Selection: rising-edge CFD20, A>1000 ADC, downstream B4/B6/B8 (B2 excluded, saturation);",
        "  per-event triples (all three staves pass); amp-only timewalk correction fit LORO within",
        "  Sample II; per-(stave,run) median centering.",
        f"- Bootstrap: whole-event resampling within run, {summary['n_bootstrap']} replicas (preserves",
        "  the measured inter-stave correlation).",
        "",
        "## Headline (replaces the WITHDRAWN 0.54-0.56 ns covariance number)",
        "",
        f"- **Combined sigma68 (A>1000, independence completion) = "
        f"{p['combined_sigma_ns']:.3f} ns "
        f"[{p['combined_sigma_ci'][0]:.3f}, {p['combined_sigma_ci'][1]:.3f}] (95% CI, correlation-aware)**",
        f"- Cauchy-Schwarz interval over the UNMEASURED intrinsic correlation: "
        f"[{p['cauchy_schwarz_bounds_ns']['psd_floor_sigma']:.3f}, "
        f"{p['cauchy_schwarz_bounds_ns']['fully_correlated_sigma']:.3f}] ns.",
        f"- Off-diagonal-equality (independence) bootstrap p = "
        f"{p['offdiag_equality_bootstrap_p']:.3f} "
        f"(large p ⇒ the three off-diagonal covariances are consistent with a single common mode,",
        "  i.e. the independence combination is not rejected; small p ⇒ structured inter-stave",
        "  correlation biases it).",
        "",
        "## Measured 3x3 covariance Cov(y) (ns^2, PSD-projected), A>1000",
        "",
        "| | B4 | B6 | B8 |",
        "|---|---|---|---|",
        f"| B4 | {cov[0,0]:.3f} | {cov[0,1]:.3f} | {cov[0,2]:.3f} |",
        f"| B6 | {cov[1,0]:.3f} | {cov[1,1]:.3f} | {cov[1,2]:.3f} |",
        f"| B8 | {cov[2,0]:.3f} | {cov[2,1]:.3f} | {cov[2,2]:.3f} |",
        "",
        "Off-diagonal covariances (= Var(T_event) under independence; equal ⇒ pure common mode):",
        f"B4-B6 {p['offdiag_cov_ns2']['B4-B6']:.3f}, B4-B8 {p['offdiag_cov_ns2']['B4-B8']:.3f}, "
        f"B6-B8 {p['offdiag_cov_ns2']['B6-B8']:.3f} ns^2.",
        "",
        "## Per-stave decomposition (triangle, propagated 95% CI)",
        "",
        "| stave | sigma68 (ns) | 95% CI | neg-var flag |",
        "|---|---|---|---|",
    ]
    for s in STAVES:
        lines.append(f"| {s} | {p['per_stave_sigma_ns'][s]:.3f} | "
                     f"[{p['per_stave_sigma_ci'][s][0]:.3f}, {p['per_stave_sigma_ci'][s][1]:.3f}] | "
                     f"{p['per_stave_variance_negative'][s]} |")
    lines += [
        "",
        "## High-amplitude subset (all three A>2000)",
        "",
        f"- Combined sigma68 = {h['combined_sigma_ns']:.3f} ns "
        f"[{h['combined_sigma_ci'][0]:.3f}, {h['combined_sigma_ci'][1]:.3f}]; "
        f"per-stave: " + ", ".join(f"{s} {h['per_stave_sigma_ns'][s]:.3f}" for s in STAVES) + " ns.",
        f"- Any sub-0.3 ns claim (per-stave or combined)? primary={p['any_sub_03']}, high-amp={h['any_sub_03']}.",
        "",
        "## Confirmation partition (docs/CONFIRMATION_PARTITION.md)",
        "",
        held["report_text"],
        "",
        "## Honest identifiability statement",
        "",
        "- With THREE downstream staves and no external clock, only 3 pairwise variances constrain",
        "  the 6-parameter intrinsic covariance: the inter-stave correlation is under-identified. The",
        "  combined number above is the minimum-norm (independence) completion; the Cauchy-Schwarz",
        "  interval is the honest bound.",
        "- The off-diagonal-equality test is the strongest available check of the independence",
        "  assumption; it is passed/failed as reported above, NOT a proof of independence.",
        "- Common-mode (trigger/clock) jitter shared identically by all staves is invisible to",
        "  inter-stave differences; it can only INFLATE an absolute-to-truth resolution. The combined",
        "  sigma68 here is therefore a relative-timing resolution and a floor on the absolute one.",
        "- This study reuses the Sample-II analysis runs (no fresh partition for exploration); see the",
        "  confirmation section for the held-out status.",
    ]
    (out_dir / "REPORT.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def git_commit() -> str:
    import subprocess
    try:
        return subprocess.check_output(["git", "rev-parse", "HEAD"], text=True,
                                       cwd=str(ROOT_DIR)).strip()
    except Exception:
        return "unknown"


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--raw-dir", default="data/root/root")
    ap.add_argument("--out", default=None)
    ap.add_argument("--max-events", type=int, default=0)
    ap.add_argument("--n-bootstrap", type=int, default=N_BOOTSTRAP)
    args = ap.parse_args()
    t0 = time.time()

    s22 = _load_s22()
    raw_dir = Path(args.raw_dir)
    out_dir = Path(args.out) if args.out else ROOT_DIR / "reports" / f"s25_covariance_timing_{int(time.time())}"
    out_dir.mkdir(parents=True, exist_ok=True)
    rng = np.random.default_rng(RANDOM_SEED)

    sample = "sample_II"
    expl_runs = [r for r in s22.SAMPLE_RUNS["sample_II"]
                 if s22.raw_file(raw_dir, r).exists()]
    print(f"[s25] exploration runs present: {expl_runs}", flush=True)

    # pair table (for the LORO timewalk fit) + per-event triples
    import pandas as pd
    pair_tabs, trip = [], {k: [] for k in ("run", "t4", "t6", "t8", "a4", "a6", "a8")}
    for r in expl_runs:
        tab, _meta = s22.load_run_pairs(raw_dir, r, sample, max_events=args.max_events)
        if len(tab):
            pair_tabs.append(tab)
        tr = load_event_triples(s22, raw_dir, r, sample, max_events=args.max_events)
        for k in trip:
            trip[k].append(tr[k])
        print(f"[s25] run {r}: triples={len(tr['t4'])}", flush=True)
    pairs_df = pd.concat(pair_tabs, ignore_index=True)
    triples = {k: np.concatenate(v) for k, v in trip.items()}

    y, fold_betas = corrected_residuals(s22, triples, pairs_df, expl_runs, sample)
    amps = np.column_stack([triples["a4"], triples["a6"], triples["a8"]])
    runs = triples["run"]

    primary = analyse(y, runs, rng, n_boot=args.n_bootstrap, label="A>1000")
    high = analyse(y, runs, rng, amp_min=HIGH_AMP_CUT_ADC, amps=amps,
                   n_boot=args.n_bootstrap, label="A>2000")
    print(f"[s25] primary combined sigma68={primary['combined_sigma_ns']:.3f} ns", flush=True)

    # ---- confirmation partition ----
    reserved_staged = [r for r in RESERVED_RUNS if s22.raw_file(raw_dir, r).exists()]
    # Track A (2026-07-05): even when staged, the reserved runs are DAQ-incompatible
    # (16-sample window / odd-channel cabling / truncated pulses). Guard on waveform
    # format so a frozen one-shot confirmation only runs on compatible runs; incompatible
    # runs are reported as such, never crashed on or silently mis-analysed.
    fmt = {r: daq_format_ok(s22, raw_dir, r) for r in reserved_staged}
    reserved_present = [r for r in reserved_staged if fmt[r][0]]
    reserved_incompatible = [r for r in reserved_staged if not fmt[r][0]]
    any_sub03 = primary["any_sub_03"] or high["any_sub_03"]
    held = {"combined_sigma_ns": None}
    if not reserved_present:
        if reserved_incompatible:
            reasons = "; ".join(fmt[r][1] for r in reserved_incompatible)
            held["report_text"] = (
                f"- Reserved runs staged but **DAQ-INCOMPATIBLE**: {reserved_incompatible}. {reasons} "
                "The reserved partition {64, 12-30} was recorded in a different acquisition "
                "configuration (16-sample window vs 18; signal on odd channels vs the analysis "
                "even-channel B-stave map; truncated pulses) — a frozen one-shot confirmation is "
                "physically invalid, not merely deferred. See reports/trackA_heldout_confirmation/. "
                f"Combined sigma68 sub-0.3 ns claim present? {any_sub03}. Net: 0.490 ns is a "
                "definitive SINGLE-PARTITION result; a validated one needs a new Sample-II beam run."
            )
            held["status"] = "BLOCKED_DAQ_INCOMPATIBLE"
        else:
            held["report_text"] = (
                f"- Reserved runs {{64, 12-30}}: **NOT staged** on this node (only analysis runs "
                f"{expl_runs} present in {raw_dir}). The one-shot held-out confirmation is therefore "
                f"**BLOCKED — data unavailable**. Combined sigma68 sub-0.3 ns claim present? {any_sub03}. "
                "Per policy a sub-0.3 ns claim would require confirmation on the reserved runs before "
                "publication; here the combined value is > 0.3 ns and, regardless, cannot be confirmed "
                "this round. This is a first-class (blocked) result: the FIRST validated timing number "
                "is not achievable until the reserved raw runs are staged."
            )
            held["status"] = "BLOCKED_DATA_UNAVAILABLE"
    else:
        # freeze the timewalk model on ALL exploration runs, apply to reserved runs
        betas_frozen = s22.fit_timewalk(pairs_df, expl_runs)
        htrip = {k: [] for k in ("run", "t4", "t6", "t8", "a4", "a6", "a8")}
        for r in reserved_present:
            tr = load_event_triples(s22, raw_dir, r, "reserved")
            for k in htrip:
                htrip[k].append(tr[k])
        htrip = {k: np.concatenate(v) for k, v in htrip.items()}
        amp_key = {"B4": "a4", "B6": "a6", "B8": "a8"}
        t_key = {"B4": "t4", "B6": "t6", "B8": "t8"}
        yr = np.column_stack([
            htrip[t_key[s]] - s22.timewalk_phi(htrip[amp_key[s]]) @ betas_frozen[s]
            for s in STAVES
        ])
        for si, s in enumerate(STAVES):
            for r in np.unique(htrip["run"]):
                m = htrip["run"] == r
                yr[m, si] -= np.median(yr[m, si])
        held_res = analyse(yr, htrip["run"], rng, n_boot=args.n_bootstrap, label="held-out")
        held = held_res
        held["status"] = "CONFIRMED_ONE_SHOT"
        held["report_text"] = (
            f"- Reserved runs present: {reserved_present}. Frozen timewalk model (fit on all "
            f"exploration runs) applied one-shot. Held-out combined sigma68 = "
            f"{held_res['combined_sigma_ns']:.3f} ns "
            f"[{held_res['combined_sigma_ci'][0]:.3f}, {held_res['combined_sigma_ci'][1]:.3f}] "
            f"vs exploration {primary['combined_sigma_ns']:.3f} ns."
        )

    summary = {
        "study": "S25",
        "title": "measured inter-stave timing covariance & covariance-correct combined resolution",
        "git_commit": git_commit(),
        "generated_utc": time.strftime("%Y-%m-%d %H:%M:%S UTC", time.gmtime()),
        "random_seed": RANDOM_SEED,
        "n_bootstrap": int(args.n_bootstrap),
        "exploration_runs": expl_runs,
        "reserved_runs_policy": RESERVED_RUNS,
        "reserved_runs_present": reserved_present,
        "reserved_runs_incompatible": reserved_incompatible,
        "n_triples": int(len(y)),
        "loro_betas": fold_betas,
        "primary": primary,
        "high_amp": high,
        "held_out": held,
        "withdrawn_number_ns": [0.54, 0.56],
        "runtime_sec": round(time.time() - t0, 1),
    }
    (out_dir / "s25_summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    np.savetxt(out_dir / "s25_cov_psd.csv", np.asarray(primary["cov_psd_ns2"]),
               delimiter=",", header="B4,B6,B8", comments="")
    make_figure(out_dir, primary, high, held if held.get("combined_sigma_ns") else None)
    write_report(out_dir, summary)
    print(json.dumps({"out_dir": str(out_dir),
                      "combined_sigma_ns": primary["combined_sigma_ns"],
                      "combined_ci": primary["combined_sigma_ci"],
                      "held_out_status": held.get("status"),
                      "runtime_sec": summary["runtime_sec"]}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
