#!/usr/bin/env python3
"""
s23_sample12_data_mc_comparison.py
==================================
Data-side closure of the Sample I/II study (S21 truth-level companion).

Inputs
------
DATA : the canonical selected-pulse table ``s00_selected_b_pulses.csv.gz``
    (one row per selected B-stave pulse, baseline-subtracted net
    ``amplitude_adc`` with A>1000 already applied; ``group`` column encodes
    the run->sample mapping from docs/02_data_and_runs.md). Sample I and
    Sample II are DISJOINT run sets with different hardware triggers
    (I: A AND B coincidence, runs 44-57 analysis; II: B only, runs 58-63,65
    analysis). Calibration runs (31-42, 64) are EXCLUDED from the headline
    and reported separately as a robustness variant.
MC   : the mc02 digitized per-stave pulse table (A>1000 companion), with
    truth trigger mimics ``sample_I``/``sample_II`` (INCLUSIVE: I is a
    subset of II) and dominant ``pdg``. The digitizer gain is an UNKNOWN
    PLACEHOLDER (297 ADC/MeV, geometry-poisoned anchor), so absolute ADC
    scales are NOT comparable between data and MC — only spectrum SHAPES
    (median-scaled) and BETWEEN-SAMPLE RATIOS are meaningful.

What it computes
----------------
(a) DATA per-stave pulse counts/occupancy fractions and amplitude spectra
    (median, q16/q84, histograms) for Sample I vs Sample II, plus the
    Matthias signature check in data: fraction of B2 pulses above
    ``--high-adc`` (default 5000) per sample with Wilson binomial CIs.
(b) MC: the same for the trigger mimics sample_I, sample_II (inclusive),
    sample_II\\I (exclusive) and UNTRIGGERED (all A>1000 rows, no mimic).
(c) Three-way data-vs-MC comparison per data sample: occupancy chi2 over
    the four staves and a scale-free KS distance on median-scaled B2
    amplitude spectra, for MC untriggered / sample_II mimic / sample_I
    mimic — does trigger mimicking move MC *toward* the data?
(d) Between-sample DOUBLE RATIOS (robust to the unknown gain and largely
    to the geometry defect, which are common to both MC samples):
        R = f(B2, I) / f(B2, II)   computed in data and in MC,
    for per-stave occupancy shares and for the high-amplitude fraction
    (MC threshold quantile-matched to the data threshold so the placeholder
    gain cancels to first order). DR = R_data / R_mc with log-normal CIs.

Outputs (in --out)
------------------
s23_summary.json   all tables, metrics, thresholds, provenance
s23_overview.png   multi-panel figure (nature-figure standards)
REPORT.md          three-way comparison tables + double-ratio verdict
"""
from __future__ import annotations

import argparse
import json
import math
import sys
import time
from pathlib import Path

import numpy as np

STAVES = ("B2", "B4", "B6", "B8")
Z95 = 1.959963984540054

DATA_GROUPS = {
    "I": "sample_i_analysis",
    "II": "sample_ii_analysis",
}
DATA_CALIB_GROUPS = {
    "I": "sample_i_calib",
    "II": "sample_ii_calib",
}
PDG_LABELS = {2212: "p", 1000010020: "d"}


# ----------------------------------------------------------------------
# statistics helpers (pure functions; unit-tested in tests/test_s23_double_ratio.py)
# ----------------------------------------------------------------------
def wilson_ci(k: float, n: float, z: float = Z95) -> tuple[float, float]:
    """Wilson score interval for a binomial proportion k/n."""
    if n <= 0:
        return (float("nan"), float("nan"))
    p = k / n
    denom = 1.0 + z * z / n
    centre = (p + z * z / (2 * n)) / denom
    half = (z / denom) * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n))
    return (max(0.0, centre - half), min(1.0, centre + half))


def log_frac_var(k: float, n: float) -> float:
    """Approximate variance of log(k/n) for binomial k out of n: (1-p)/k."""
    if k <= 0 or n <= 0:
        return float("inf")
    return (1.0 - k / n) / k


def ratio_ci(k1: float, n1: float, k2: float, n2: float,
             z: float = Z95) -> tuple[float, float, float]:
    """Ratio of two binomial proportions (k1/n1)/(k2/n2) with log-normal CI."""
    if min(k1, n1, k2, n2) <= 0:
        return (float("nan"), float("nan"), float("nan"))
    r = (k1 / n1) / (k2 / n2)
    s = math.sqrt(log_frac_var(k1, n1) + log_frac_var(k2, n2))
    return (r, r * math.exp(-z * s), r * math.exp(z * s))


def double_ratio(kI_d: float, nI_d: float, kII_d: float, nII_d: float,
                 kI_m: float, nI_m: float, kII_m: float, nII_m: float,
                 z: float = Z95) -> dict:
    """DOUBLE ratio [f_I/f_II]_data / [f_I/f_II]_mc with log-normal CI.

    Gain-robust and geometry-robust by construction: any multiplicative
    factor common to both samples WITHIN data or WITHIN MC (unknown gain,
    common geometry acceptance) cancels exactly in each inner ratio.
    Returns the inner ratios, the double ratio, its 95% CI, and the
    z-score of log(DR) against 0 (DR = 1 <=> data and MC agree).
    """
    r_d = ratio_ci(kI_d, nI_d, kII_d, nII_d, z)
    r_m = ratio_ci(kI_m, nI_m, kII_m, nII_m, z)
    counts = ((kI_d, nI_d), (kII_d, nII_d), (kI_m, nI_m), (kII_m, nII_m))
    if any(min(k, n) <= 0 for k, n in counts) or not (r_d[0] > 0 and r_m[0] > 0):
        return {"ratio_data": r_d, "ratio_mc": r_m, "dr": float("nan"),
                "dr_lo": float("nan"), "dr_hi": float("nan"), "z_vs_1": float("nan")}
    dr = r_d[0] / r_m[0]
    s = math.sqrt(sum(log_frac_var(k, n) for k, n in counts))
    return {
        "ratio_data": r_d,
        "ratio_mc": r_m,
        "dr": dr,
        "dr_lo": dr * math.exp(-z * s),
        "dr_hi": dr * math.exp(z * s),
        "z_vs_1": math.log(dr) / s if s > 0 else float("inf"),
    }


def occupancy_chi2(counts_a: dict[str, int], counts_b: dict[str, int]) -> dict:
    """Chi2 distance between two per-stave occupancy-share vectors.

    chi2 = sum_staves (f_a - f_b)^2 / (var_a + var_b), binomial variances.
    The four shares sum to 1 so effective dof ~ 3. Also returns per-stave
    pulls (signed sqrt contributions, a - b).
    """
    n_a = sum(counts_a.values())
    n_b = sum(counts_b.values())
    chi2, pulls = 0.0, {}
    for s in STAVES:
        fa, fb = counts_a.get(s, 0) / n_a, counts_b.get(s, 0) / n_b
        var = fa * (1 - fa) / n_a + fb * (1 - fb) / n_b
        pull = (fa - fb) / math.sqrt(var) if var > 0 else float("inf")
        pulls[s] = pull
        chi2 += pull * pull
    return {"chi2": chi2, "dof": len(STAVES) - 1, "pulls": pulls}


def ks_distance(x: np.ndarray, y: np.ndarray) -> float:
    """Two-sample Kolmogorov-Smirnov statistic (D only; n >> 1 here so
    p-values are meaningless — D is used as a shape-distance metric)."""
    x = np.sort(np.asarray(x, dtype=np.float64))
    y = np.sort(np.asarray(y, dtype=np.float64))
    grid = np.concatenate([x, y])
    cdf_x = np.searchsorted(x, grid, side="right") / x.size
    cdf_y = np.searchsorted(y, grid, side="right") / y.size
    return float(np.abs(cdf_x - cdf_y).max())


# ----------------------------------------------------------------------
# per-sample summaries
# ----------------------------------------------------------------------
def spectra_stats(amp_by_stave: dict[str, np.ndarray], high_adc_by_stave: dict[str, float],
                  bins: np.ndarray) -> dict:
    """Per-stave counts, occupancy shares, amplitude quantiles, histograms
    and high-amplitude fractions for one sample."""
    counts = {s: int(amp_by_stave.get(s, np.empty(0)).size) for s in STAVES}
    n_tot = sum(counts.values())
    out = {"n_pulses": n_tot, "staves": {}}
    for s in STAVES:
        a = amp_by_stave.get(s, np.empty(0))
        k = counts[s]
        lo, hi = wilson_ci(k, n_tot)
        rec = {
            "n": k,
            "occupancy_share": k / n_tot if n_tot else float("nan"),
            "occupancy_ci": [lo, hi],
        }
        if k:
            q16, q50, q84 = np.percentile(a, [15.865, 50.0, 84.135])
            thr = high_adc_by_stave[s]
            k_hi = int((a > thr).sum())
            lo_h, hi_h = wilson_ci(k_hi, k)
            rec.update({
                "amp_median": float(q50),
                "amp_q16": float(q16),
                "amp_q84": float(q84),
                "amp_sigma68": float((q84 - q16) / 2.0),
                "high_thr_adc": float(thr),
                "n_high": k_hi,
                "frac_high": k_hi / k,
                "frac_high_ci": [lo_h, hi_h],
                "hist": np.histogram(a, bins=bins)[0].tolist(),
            })
        out["staves"][s] = rec
    return out


def split_amp(df, mask) -> dict[str, np.ndarray]:
    sub = df[mask]
    return {s: sub.loc[sub["stave"] == s, "amplitude_adc"].to_numpy(dtype=np.float64)
            for s in STAVES}


# ----------------------------------------------------------------------
# figure
# ----------------------------------------------------------------------
def make_figure(out_png: Path, D: dict, bins: np.ndarray, amp: dict, high_adc: float) -> None:
    """Multi-panel overview.

    Contract — core conclusion: 'The data show the Sample-I B2 hard-spectrum
    (deuteron-stopper) signature; trigger-mimicked MC reproduces the
    between-sample double ratio despite the uncalibrated gain.'
    Archetype: quantitative grid, hero panel (a). Backend: Python/matplotlib.
    """
    import matplotlib as mpl
    mpl.use("Agg")
    import matplotlib.pyplot as plt

    mpl.rcParams.update({
        "font.family": "sans-serif",
        "font.sans-serif": ["Arial", "Helvetica", "DejaVu Sans", "sans-serif"],
        "font.size": 7,
        "axes.titlesize": 7.5,
        "axes.linewidth": 0.8,
        "axes.spines.right": False,
        "axes.spines.top": False,
        "legend.frameon": False,
        "svg.fonttype": "none",
        "pdf.fonttype": 42,
    })
    C_I, C_II = "#B2182B", "#2166AC"        # data Sample I (signal) / II (reference)
    C_MCI, C_MCII, C_MCU = "#E08214", "#7FBC41", "#878787"  # MC mimics / untriggered

    fig = plt.figure(figsize=(7.09, 7.6))   # 180 mm double column
    gs = fig.add_gridspec(3, 2, hspace=0.52, wspace=0.30,
                          left=0.09, right=0.98, top=0.95, bottom=0.06)
    centers = 0.5 * (bins[:-1] + bins[1:])

    def norm_hist(h):
        h = np.asarray(h, dtype=np.float64)
        tot = h.sum()
        return h / tot if tot else h

    # (a) HERO — data B2 amplitude spectra, Sample I vs II
    ax = fig.add_subplot(gs[0, 0])
    for key, c, lbl in (("I", C_I, "Sample I (A·B coinc., runs 44–57)"),
                        ("II", C_II, "Sample II (B only, runs 58–63,65)")):
        h = norm_hist(D["data"][key]["staves"]["B2"]["hist"])
        ax.stairs(h, bins, color=c, lw=1.1, label=lbl)
    ax.axvline(high_adc, color="0.3", lw=0.7, ls=":")
    ax.text(high_adc * 1.03, ax.get_ylim()[1] * 0.55, f"A = {high_adc:.0f}",
            rotation=90, va="center", fontsize=6, color="0.3")
    ax.set_yscale("log")
    ax.set_xlabel("B2 net amplitude (ADC)")
    ax.set_ylabel("Fraction of pulses / bin")
    fI = D["data"]["I"]["staves"]["B2"]
    fII = D["data"]["II"]["staves"]["B2"]
    ax.set_title("a  DATA: B2 spectrum is harder in Sample I", loc="left", fontweight="bold")
    ax.legend(loc="upper right", fontsize=6)
    ax.text(0.02, 0.06,
            f"f(A>{high_adc:.0f}): I = {fI['frac_high']:.3f}, II = {fII['frac_high']:.3f}",
            transform=ax.transAxes, fontsize=6)

    # (b) MC B2 spectra by trigger mimic (median-scaled x: placeholder gain)
    ax = fig.add_subplot(gs[0, 1])
    med_ref = D["mc"]["II"]["staves"]["B2"]["amp_median"]
    mc_bins = None
    for key, c, lbl in (("I", C_MCI, "MC sample I mimic"),
                        ("II", C_MCII, "MC sample II mimic (incl.)"),
                        ("untrig", C_MCU, "MC untriggered (A>1000)")):
        a = amp["mc"][key]["B2"] / med_ref
        if mc_bins is None:
            mc_bins = np.linspace(0.0, np.percentile(a, 99.8), 61)
        h, _ = np.histogram(a, bins=mc_bins)
        ax.stairs(norm_hist(h), mc_bins, color=c, lw=1.0, label=lbl)
    ax.set_yscale("log")
    ax.set_xlabel("B2 amplitude / MC sample-II median (gain placeholder)")
    ax.set_ylabel("Fraction of pulses / bin")
    ax.set_title("b  MC: trigger mimic hardens B2 the same way", loc="left", fontweight="bold")
    ax.legend(loc="upper right", fontsize=6)

    # (c) per-stave occupancy shares, data vs MC mimics
    ax = fig.add_subplot(gs[1, 0])
    x = np.arange(len(STAVES))
    series = [("data I", D["data"]["I"], C_I, -0.30), ("MC I", D["mc"]["I"], C_MCI, -0.10),
              ("data II", D["data"]["II"], C_II, 0.10), ("MC II", D["mc"]["II"], C_MCII, 0.30)]
    for lbl, rec, c, off in series:
        y = [rec["staves"][s]["occupancy_share"] for s in STAVES]
        yerr = np.array([[rec["staves"][s]["occupancy_share"] - rec["staves"][s]["occupancy_ci"][0],
                          rec["staves"][s]["occupancy_ci"][1] - rec["staves"][s]["occupancy_share"]]
                         for s in STAVES]).T
        ax.bar(x + off, y, width=0.18, color=c, label=lbl,
               yerr=yerr, error_kw={"lw": 0.6, "capsize": 1.2})
    ax.set_yscale("log")
    ax.set_ylim(3e-4, 2.0)
    ax.set_xticks(x, STAVES)
    ax.set_ylabel("Occupancy share of pulses")
    ax.set_title("c  Per-stave occupancy: data vs trigger-mimicked MC", loc="left", fontweight="bold")
    ax.legend(ncols=4, loc="upper right", fontsize=6, columnspacing=0.9)

    # (d) shape/occupancy metric matrix: does mimicking help?
    ax = fig.add_subplot(gs[1, 1])
    pair_order = ["untrig", "II", "I"]
    pair_lbl = ["untriggered", "sample II mimic", "sample I mimic"]
    xm = np.arange(3)
    for dkey, c in (("I", C_I), ("II", C_II)):
        ks = [D["comparison"][dkey][m]["ks_b2_median_scaled"] for m in pair_order]
        ax.plot(xm, ks, "o-", color=c, lw=1.0, ms=3.5, label=f"data {dkey}: KS(B2 shape)")
    ax2 = ax.twinx()
    ax2.spines["top"].set_visible(False)
    for dkey, c in (("I", C_I), ("II", C_II)):
        ch = [D["comparison"][dkey][m]["occupancy_chi2"] for m in pair_order]
        ax2.plot(xm, ch, "s--", color=c, lw=0.8, ms=3.0, alpha=0.55)
    ax2.set_yscale("log")
    ax2.set_ylabel(r"occupancy $\chi^2$ (squares, dashed)", fontsize=6.5)
    ax.set_xticks(xm, pair_lbl)
    ax.set_ylabel("KS distance, median-scaled B2 spectrum")
    ax.set_ylim(0, None)
    ax.set_title("d  MC-vs-data distance under trigger mimicking", loc="left", fontweight="bold")
    ax.legend(loc="upper right", fontsize=6)

    # (e) between-sample ratios R = f(I)/f(II): data vs MC, per stave occupancy
    ax = fig.add_subplot(gs[2, 0])
    for i, s in enumerate(STAVES):
        rec = D["double_ratio"]["occupancy"][s]
        for r, c, off, lbl in ((rec["ratio_data"], "0.15", -0.12, "data"),
                               (rec["ratio_mc"], C_MCII, 0.04, "MC (incl.)"),
                               (rec["ratio_mc_excl"], C_MCI, 0.20, "MC (excl. II\\I)")):
            ax.errorbar(i + off, r[0], yerr=[[r[0] - r[1]], [r[2] - r[0]]],
                        fmt="o", color=c, ms=3.2, lw=0.9, capsize=1.5,
                        label=lbl if i == 0 else None)
    ax.axhline(1.0, color="0.6", lw=0.6, ls="--")
    ax.set_yscale("log")
    ax.set_xticks(range(len(STAVES)), STAVES)
    ax.set_ylabel("R = occupancy share I / II")
    ax.set_title("e  Between-sample occupancy ratio, data vs MC", loc="left", fontweight="bold")
    ax.legend(loc="upper right", fontsize=6)

    # (f) the double-ratio verdict panel
    ax = fig.add_subplot(gs[2, 1])
    items = [(f"occ {s}", D["double_ratio"]["occupancy"][s]) for s in STAVES]
    items += [("B2 f(high)", D["double_ratio"]["high_frac_b2"]),
              ("B2 f(high)\nexcl.", D["double_ratio"]["high_frac_b2_excl"])]
    ypos = np.arange(len(items))[::-1]
    for y, (lbl, rec) in zip(ypos, items):
        dr, lo, hi = rec["dr"], rec["dr_lo"], rec["dr_hi"]
        if not np.isfinite(dr):
            continue
        ax.errorbar(dr, y, xerr=[[dr - lo], [hi - dr]], fmt="o", color="#4D004B",
                    ms=3.5, lw=1.0, capsize=1.8)
    ax.axvline(1.0, color="#B2182B", lw=0.8, ls="--")
    ax.set_yticks(ypos, [lbl for lbl, _ in items], fontsize=6.5)
    ax.set_xscale("log")
    ax.set_xlabel("Double ratio  [f$_I$/f$_{II}$]$_{data}$ / [f$_I$/f$_{II}$]$_{MC}$")
    ax.set_title("f  Gain/geometry-robust double ratios (=1: MC matches)",
                 loc="left", fontweight="bold")

    fig.text(0.01, 0.005,
             "Data: s00 selected pulses (A>1000), analysis runs only; disjoint run sets. "
             "MC: mc02 A>1000, placeholder gain — shapes/ratios only. Error bars: 95% CI.",
             fontsize=5.5, color="0.35")
    fig.savefig(out_png, dpi=600, bbox_inches="tight")
    fig.savefig(out_png.with_suffix(".svg"), bbox_inches="tight")
    plt.close(fig)


# ----------------------------------------------------------------------
# report
# ----------------------------------------------------------------------
def fmt_ci(v, lo, hi, nd=3):
    if not np.isfinite(v):
        return "n/a"
    return f"{v:.{nd}f} [{lo:.{nd}f}, {hi:.{nd}f}]"


def write_report(out_dir: Path, D: dict, args, high_adc: float, mc_thr: dict) -> None:
    d_I, d_II = D["data"]["I"], D["data"]["II"]
    fI, fII = d_I["staves"]["B2"], d_II["staves"]["B2"]
    r_high = ratio_ci(fI["n_high"], fI["n"], fII["n_high"], fII["n"])
    dr_occ = D["double_ratio"]["occupancy"]["B2"]
    dr_hi = D["double_ratio"]["high_frac_b2"]
    dr_hi_x = D["double_ratio"]["high_frac_b2_excl"]

    L = []
    L.append("# S23 — Sample I vs Sample II: data-side closure and data–MC comparison (B arm)\n")
    L.append(f"- DATA: `{args.data}` (analysis runs only: Sample I = 44–57, Sample II = 58–63,65; "
             "calibration runs 31–42/64 excluded, reported as variant)")
    L.append(f"- MC: `{args.mc}` (mc02 digitized table, A>1000 companion; trigger mimics inclusive)")
    L.append(f"- Generated: {time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())} "
             "by `scripts/s23_sample12_data_mc_comparison.py`\n")

    L.append("## Verdicts\n")
    sig = fI["frac_high_ci"][0] > fII["frac_high_ci"][1]
    L.append(f"1. **Matthias signature in DATA: {'YES' if sig else 'NO'}** — the Sample-I B2 spectrum "
             f"is harder: f(A>{high_adc:.0f}) = {fmt_ci(fI['frac_high'], *fI['frac_high_ci'])} (I) vs "
             f"{fmt_ci(fII['frac_high'], *fII['frac_high_ci'])} (II), ratio "
             f"{fmt_ci(*r_high)}; B2 median {fI['amp_median']:.0f} vs {fII['amp_median']:.0f} ADC.")
    imp = D["comparison"]["improvement_verdict"]
    L.append(f"2. **Trigger mimicking moves MC toward the data: {imp['verdict']}** — {imp['detail']}")
    L.append(f"3. **Double ratio (gain/geometry-robust): B2 occupancy DR = "
             f"{fmt_ci(dr_occ['dr'], dr_occ['dr_lo'], dr_occ['dr_hi'])} "
             f"(z vs 1: {dr_occ['z_vs_1']:.1f}); B2 high-amplitude DR = "
             f"{fmt_ci(dr_hi['dr'], dr_hi['dr_lo'], dr_hi['dr_hi'])} "
             f"(z: {dr_hi['z_vs_1']:.1f}; exclusive-MC variant "
             f"{fmt_ci(dr_hi_x['dr'], dr_hi_x['dr_lo'], dr_hi_x['dr_hi'])}).**\n")

    L.append("## (a) DATA per-stave summary (analysis runs, A>1000)\n")
    L.append("| Stave | n_I | share_I (95% CI) | med_I | σ68_I | f(A>thr)_I | n_II | share_II (95% CI) | med_II | σ68_II | f(A>thr)_II |")
    L.append("|---|---|---|---|---|---|---|---|---|---|---|")
    for s in STAVES:
        a, b = d_I["staves"][s], d_II["staves"][s]
        L.append(f"| {s} | {a['n']:,} | {fmt_ci(a['occupancy_share'], *a['occupancy_ci'], nd=4)} | "
                 f"{a.get('amp_median', float('nan')):.0f} | {a.get('amp_sigma68', float('nan')):.0f} | "
                 f"{fmt_ci(a.get('frac_high', float('nan')), *a.get('frac_high_ci', [0, 0]))} | "
                 f"{b['n']:,} | {fmt_ci(b['occupancy_share'], *b['occupancy_ci'], nd=4)} | "
                 f"{b.get('amp_median', float('nan')):.0f} | {b.get('amp_sigma68', float('nan')):.0f} | "
                 f"{fmt_ci(b.get('frac_high', float('nan')), *b.get('frac_high_ci', [0, 0]))} |")
    L.append("")

    L.append("## (b) MC per-stave summary (mc02 A>1000, trigger mimics)\n")
    L.append(f"MC high-amplitude thresholds are QUANTILE-MATCHED per stave to the data threshold "
             f"({high_adc:.0f} ADC in data; matched on the pooled sample-II spectra so the placeholder "
             f"gain cancels to first order): " +
             ", ".join(f"{s}: {mc_thr[s]:.0f} ADC" for s in STAVES) + "\n")
    L.append("| Stave | variant | n | share (95% CI) | med (ADC) | σ68 | f(A>thr_mc) (95% CI) |")
    L.append("|---|---|---|---|---|---|---|")
    for s in STAVES:
        for key, lbl in (("I", "sample_I mimic"), ("II", "sample_II mimic (incl.)"),
                         ("II_excl", "sample_II \\ I (excl.)"), ("untrig", "untriggered")):
            r = D["mc"][key]["staves"][s]
            L.append(f"| {s} | {lbl} | {r['n']:,} | {fmt_ci(r['occupancy_share'], *r['occupancy_ci'], nd=4)} | "
                     f"{r.get('amp_median', float('nan')):.0f} | {r.get('amp_sigma68', float('nan')):.0f} | "
                     f"{fmt_ci(r.get('frac_high', float('nan')), *r.get('frac_high_ci', [0, 0]))} |")
    L.append("")

    L.append("## (c) Three-way data-vs-MC comparison (does trigger mimicking help?)\n")
    L.append("Metrics: occupancy χ² over the 4 staves (dof≈3; binomial variances) and the "
             "two-sample KS distance on **median-scaled** B2 amplitude spectra (scale-free, "
             "so the placeholder gain drops out; raw-ADC KS is reported in the JSON but is "
             "BLOCKED as a comparison by the unknown gain).\n")
    L.append("| Data sample | MC variant | occupancy χ² | per-stave pulls (B2/B4/B6/B8) | KS(B2, median-scaled) |")
    L.append("|---|---|---|---|---|")
    for dkey in ("I", "II"):
        for m, lbl in (("untrig", "untriggered"), ("II", "sample_II mimic"), ("I", "sample_I mimic")):
            c = D["comparison"][dkey][m]
            pulls = "/".join(f"{c['occupancy_pulls'][s]:+.0f}" for s in STAVES)
            L.append(f"| data {dkey} | {lbl} | {c['occupancy_chi2']:.0f} | {pulls} | "
                     f"{c['ks_b2_median_scaled']:.4f} |")
    L.append("")
    L.append(f"**Reading:** {imp['detail']}\n")

    L.append("## (d) Double ratios — the cleanest test of the enrichment mechanism\n")
    L.append("DR = [f(·,I)/f(·,II)]_data / [f(·,I)/f(·,II)]_MC. Any factor common to both samples "
             "within data or within MC (unknown gain, common geometry acceptance) cancels in each "
             "inner ratio. DR = 1 ⇔ MC reproduces the between-sample enrichment.\n")
    L.append("| Observable | R_data (95% CI) | R_MC incl. (95% CI) | R_MC excl. II\\I (95% CI) | DR (data/MC incl.) | z vs 1 | DR (data/MC excl.) |")
    L.append("|---|---|---|---|---|---|---|")
    for s in STAVES:
        rec = D["double_ratio"]["occupancy"][s]
        rex = rec["excl"]
        L.append(f"| occupancy {s} | {fmt_ci(*rec['ratio_data'])} | {fmt_ci(*rec['ratio_mc'])} | "
                 f"{fmt_ci(*rec['ratio_mc_excl'])} | {fmt_ci(rec['dr'], rec['dr_lo'], rec['dr_hi'])} | "
                 f"{rec['z_vs_1']:.1f} | {fmt_ci(rex['dr'], rex['dr_lo'], rex['dr_hi'])} |")
    for lbl, rec in (("B2 f(A>thr)", dr_hi),):
        rex = dr_hi_x
        L.append(f"| {lbl} | {fmt_ci(*rec['ratio_data'])} | {fmt_ci(*rec['ratio_mc'])} | "
                 f"{fmt_ci(*rex['ratio_mc'])} | {fmt_ci(rec['dr'], rec['dr_lo'], rec['dr_hi'])} | "
                 f"{rec['z_vs_1']:.1f} | {fmt_ci(rex['dr'], rex['dr_lo'], rex['dr_hi'])} |")
    L.append("")

    L.append("## MC species mechanism (dominant-pdg composition of B2 pulses)\n")
    L.append("| variant | f_d(B2) | f_p(B2) | f_other(B2) |")
    L.append("|---|---|---|---|")
    for key, lbl in (("I", "sample_I mimic"), ("II", "sample_II mimic"),
                     ("II_excl", "II \\ I"), ("untrig", "untriggered")):
        comp = D["mc"][key].get("b2_species", {})
        L.append(f"| {lbl} | {comp.get('d', float('nan')):.3f} | {comp.get('p', float('nan')):.3f} | "
                 f"{comp.get('other', float('nan')):.3f} |")
    L.append("")

    L.append("## Robustness variant — calibration runs included\n")
    v = D["variants"]["calib_included"]
    L.append(f"- data B2 f(A>{high_adc:.0f}): I = {v['I_frac_high_b2']:.4f}, II = {v['II_frac_high_b2']:.4f} "
             f"(headline: {fI['frac_high']:.4f} / {fII['frac_high']:.4f}); B2 occupancy DR = "
             f"{fmt_ci(v['dr_occ_b2']['dr'], v['dr_occ_b2']['dr_lo'], v['dr_occ_b2']['dr_hi'])}.\n")

    L.append("## Caveats (honest limits of this comparison)\n")
    L.append("- **Gain placeholder**: the mc02 digitizer gain (297 ADC/MeV) is an UNKNOWN placeholder "
             "anchored on geometry-poisoned MC (review P1/P2). NO absolute ADC comparison is made; "
             "MC high-amplitude thresholds are quantile-matched and the shape metric is median-scaled. "
             "Residual gain nonlinearity/saturation differences are NOT removed by scaling.")
    L.append("- **Geometry poisoning**: the MC geometry lacks upstream beamline material (MV3, "
             "χ²/ndf=68,269), diluting stoppers with through-goers. Absolute occupancy χ² values are "
             "therefore expected to stay large even for a perfect trigger mimic; only the *ordering* "
             "(untriggered → II → I) and the between-sample double ratios are decision-grade.")
    L.append("- **Disjoint-runs vs inclusive-MC asymmetry**: data Samples I/II are disjoint run sets "
             "with different hardware triggers; the MC mimics are inclusive (I ⊂ II). The exclusive "
             "MC variant (II\\I) is reported alongside everywhere; it is the closer analogue of the "
             "data Sample II run set *only if* the hardware B-trigger runs contain the same pd-pair "
             "phase space (they do, untagged), so inclusive is the physically correct default and "
             "exclusive is the bracketing variant.")
    L.append("- **Beam/rate differences between run sets** (currents, pile-up, drift across runs "
             "44–65) are NOT modelled in MC and are absorbed into the data ratios.")
    L.append("- **Data saturation**: the data amplitude spectrum clips at the ADC ceiling in B2; the "
             "MC pipeline saturates differently. The high-amplitude fraction uses a threshold well "
             "below the ceiling, but the KS shape distance retains a tail-shape systematic.")
    L.append("- **LayerID→stave mapping** ('paired') is UNDER REVIEW (P4); MC occupancy shares would "
             "change under the 'odd' mapping, the data does not.")
    L.append("")
    L.append("## Artifacts\n")
    L.append("- `s23_summary.json` — every number in this report plus raw-ADC KS and histograms")
    L.append("- `s23_overview.png` / `.svg` — multi-panel overview figure")
    L.append("")
    L.append("Reproduce:")
    L.append("```")
    L.append(f"python3 scripts/s23_sample12_data_mc_comparison.py --data {args.data} \\")
    L.append(f"    --mc {args.mc} --high-adc {high_adc:.0f} --out {args.out}")
    L.append("```")
    (out_dir / "REPORT.md").write_text("\n".join(L) + "\n", encoding="utf-8")


# ----------------------------------------------------------------------
def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--data", required=True, help="s00_selected_b_pulses.csv.gz")
    ap.add_argument("--mc", required=True, help="mc02_pulse_table_a1000.csv.gz")
    ap.add_argument("--out", required=True, help="output directory")
    ap.add_argument("--high-adc", type=float, default=5000.0,
                    help="data high-amplitude threshold (ADC); MC threshold is quantile-matched")
    ap.add_argument("--bin-max", type=float, default=16000.0)
    ap.add_argument("--n-bins", type=int, default=60)
    args = ap.parse_args()

    import pandas as pd

    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)
    t0 = time.time()

    data = pd.read_csv(args.data, usecols=["run", "group", "eventno", "stave", "amplitude_adc"])
    mc = pd.read_csv(args.mc, usecols=["eventno", "stave", "amplitude_adc", "pdg",
                                       "sample_I", "sample_II"])
    print(f"[s23] data rows={len(data):,} mc rows={len(mc):,} ({time.time()-t0:.0f}s)", flush=True)

    bins = np.linspace(1000.0, args.bin_max, args.n_bins + 1)
    high_adc = float(args.high_adc)

    # ---------- amplitude arrays per selection ----------
    amp = {"data": {}, "mc": {}}
    data_masks = {
        "I": data["group"] == DATA_GROUPS["I"],
        "II": data["group"] == DATA_GROUPS["II"],
        "I_all": data["group"].isin([DATA_GROUPS["I"], DATA_CALIB_GROUPS["I"]]),
        "II_all": data["group"].isin([DATA_GROUPS["II"], DATA_CALIB_GROUPS["II"]]),
    }
    for k, m in data_masks.items():
        amp["data"][k] = split_amp(data, m)
    mc_masks = {
        "I": mc["sample_I"] == 1,
        "II": mc["sample_II"] == 1,
        "II_excl": (mc["sample_II"] == 1) & (mc["sample_I"] == 0),
        "untrig": pd.Series(True, index=mc.index),
    }
    for k, m in mc_masks.items():
        amp["mc"][k] = split_amp(mc, m)

    # ---------- quantile-matched MC high thresholds ----------
    # q = P(A <= high_adc) in the pooled data sample-II spectrum per stave;
    # MC threshold = q-quantile of the MC sample-II (inclusive) spectrum.
    mc_thr = {}
    for s in STAVES:
        a_d = amp["data"]["II"][s]
        a_m = amp["mc"]["II"][s]
        if a_d.size and a_m.size:
            q = float((a_d <= high_adc).mean())
            mc_thr[s] = float(np.quantile(a_m, q))
        else:
            mc_thr[s] = float("nan")
    data_thr = {s: high_adc for s in STAVES}

    # ---------- per-sample summaries ----------
    D: dict = {"data": {}, "mc": {}}
    for k in ("I", "II"):
        D["data"][k] = spectra_stats(amp["data"][k], data_thr, bins)
    for k in ("I", "II", "II_excl", "untrig"):
        D["mc"][k] = spectra_stats(amp["mc"][k], mc_thr, bins)
        # dominant-pdg composition of B2 rows
        sub = mc[mc_masks[k] & (mc["stave"] == "B2")]
        n = len(sub)
        if n:
            lab = sub["pdg"].map(PDG_LABELS).fillna("other")
            comp = (lab.value_counts() / n).to_dict()
            D["mc"][k]["b2_species"] = {c: float(comp.get(c, 0.0)) for c in ("p", "d", "other")}

    # ---------- (c) three-way comparison ----------
    D["comparison"] = {}
    for dkey in ("I", "II"):
        d_counts = {s: D["data"][dkey]["staves"][s]["n"] for s in STAVES}
        med_d = D["data"][dkey]["staves"]["B2"]["amp_median"]
        a_d_scaled = amp["data"][dkey]["B2"] / med_d
        row = {}
        for m in ("untrig", "II", "I"):
            m_counts = {s: D["mc"][m]["staves"][s]["n"] for s in STAVES}
            chi = occupancy_chi2(d_counts, m_counts)
            med_m = D["mc"][m]["staves"]["B2"]["amp_median"]
            a_m_scaled = amp["mc"][m]["B2"] / med_m
            row[m] = {
                "occupancy_chi2": chi["chi2"],
                "occupancy_dof": chi["dof"],
                "occupancy_pulls": chi["pulls"],
                "ks_b2_median_scaled": ks_distance(a_d_scaled, a_m_scaled),
                "ks_b2_raw_adc_BLOCKED_BY_GAIN": ks_distance(amp["data"][dkey]["B2"],
                                                             amp["mc"][m]["B2"]),
            }
        D["comparison"][dkey] = row

    # improvement verdict: matched mimic must beat untriggered on BOTH metrics
    cI, cII = D["comparison"]["I"], D["comparison"]["II"]
    ks_ok_I = cI["I"]["ks_b2_median_scaled"] < cI["untrig"]["ks_b2_median_scaled"]
    ks_ok_II = cII["II"]["ks_b2_median_scaled"] < cII["untrig"]["ks_b2_median_scaled"]
    occ_ok_I = cI["I"]["occupancy_chi2"] < cI["untrig"]["occupancy_chi2"]
    occ_ok_II = cII["II"]["occupancy_chi2"] < cII["untrig"]["occupancy_chi2"]
    match_I = cI["I"]["ks_b2_median_scaled"] < cI["II"]["ks_b2_median_scaled"]
    n_pass = sum([ks_ok_I, ks_ok_II, occ_ok_I, occ_ok_II])
    verdict = "YES" if n_pass == 4 else ("PARTIALLY" if n_pass >= 2 else "NO")
    detail = (
        f"data I: KS {cI['untrig']['ks_b2_median_scaled']:.4f} (untrig) → "
        f"{cI['II']['ks_b2_median_scaled']:.4f} (II mimic) → {cI['I']['ks_b2_median_scaled']:.4f} (I mimic); "
        f"χ² {cI['untrig']['occupancy_chi2']:.0f} → {cI['II']['occupancy_chi2']:.0f} → "
        f"{cI['I']['occupancy_chi2']:.0f}. "
        f"data II: KS {cII['untrig']['ks_b2_median_scaled']:.4f} → {cII['II']['ks_b2_median_scaled']:.4f} "
        f"(II mimic; I mimic {cII['I']['ks_b2_median_scaled']:.4f}); "
        f"χ² {cII['untrig']['occupancy_chi2']:.0f} → {cII['II']['occupancy_chi2']:.0f} "
        f"(I mimic {cII['I']['occupancy_chi2']:.0f}). "
        f"The matched mimic is {'also the closest' if match_I else 'NOT the closest'} MC variant "
        f"for data I in B2 shape. Absolute χ² remains far from statistical agreement "
        f"(geometry poisoning + unmodelled beam conditions) — the claim is the *direction* of "
        f"improvement, not agreement."
    )
    D["comparison"]["improvement_verdict"] = {
        "verdict": verdict, "detail": detail,
        "checks": {"ks_data_I": ks_ok_I, "ks_data_II": ks_ok_II,
                   "chi2_data_I": occ_ok_I, "chi2_data_II": occ_ok_II,
                   "matched_mimic_closest_for_I": match_I},
    }

    # ---------- (d) double ratios ----------
    def occ_counts(rec):
        return {s: rec["staves"][s]["n"] for s in STAVES}

    n_d = {k: D["data"][k]["n_pulses"] for k in ("I", "II")}
    n_m = {k: D["mc"][k]["n_pulses"] for k in ("I", "II", "II_excl")}
    D["double_ratio"] = {"occupancy": {}}
    for s in STAVES:
        kI_d = D["data"]["I"]["staves"][s]["n"]
        kII_d = D["data"]["II"]["staves"][s]["n"]
        kI_m = D["mc"]["I"]["staves"][s]["n"]
        kII_m = D["mc"]["II"]["staves"][s]["n"]
        kIIx_m = D["mc"]["II_excl"]["staves"][s]["n"]
        rec = double_ratio(kI_d, n_d["I"], kII_d, n_d["II"],
                           kI_m, n_m["I"], kII_m, n_m["II"])
        rec["ratio_mc_excl"] = ratio_ci(kI_m, n_m["I"], kIIx_m, n_m["II_excl"])
        rec["excl"] = double_ratio(kI_d, n_d["I"], kII_d, n_d["II"],
                                   kI_m, n_m["I"], kIIx_m, n_m["II_excl"])
        D["double_ratio"]["occupancy"][s] = rec

    def high_dr(mc_key):
        fI_d = D["data"]["I"]["staves"]["B2"]
        fII_d = D["data"]["II"]["staves"]["B2"]
        fI_m = D["mc"]["I"]["staves"]["B2"]
        fII_m = D["mc"][mc_key]["staves"]["B2"]
        return double_ratio(fI_d["n_high"], fI_d["n"], fII_d["n_high"], fII_d["n"],
                            fI_m["n_high"], fI_m["n"], fII_m["n_high"], fII_m["n"])

    D["double_ratio"]["high_frac_b2"] = high_dr("II")
    D["double_ratio"]["high_frac_b2_excl"] = high_dr("II_excl")

    # fixed-ADC (naive) MC variant for the record
    def high_fixed(mask_key):
        a = amp["mc"][mask_key]["B2"]
        return int((a > high_adc).sum()), int(a.size)

    kI, nI = high_fixed("I")
    kII, nII = high_fixed("II")
    fI_d = D["data"]["I"]["staves"]["B2"]
    fII_d = D["data"]["II"]["staves"]["B2"]
    D["double_ratio"]["high_frac_b2_fixed_adc_naive"] = double_ratio(
        fI_d["n_high"], fI_d["n"], fII_d["n_high"], fII_d["n"], kI, nI, kII, nII)

    # ---------- robustness variant: calibration runs included ----------
    var = {}
    stats_Iall = spectra_stats(amp["data"]["I_all"], data_thr, bins)
    stats_IIall = spectra_stats(amp["data"]["II_all"], data_thr, bins)
    var["I_frac_high_b2"] = stats_Iall["staves"]["B2"]["frac_high"]
    var["II_frac_high_b2"] = stats_IIall["staves"]["B2"]["frac_high"]
    var["dr_occ_b2"] = double_ratio(
        stats_Iall["staves"]["B2"]["n"], stats_Iall["n_pulses"],
        stats_IIall["staves"]["B2"]["n"], stats_IIall["n_pulses"],
        D["mc"]["I"]["staves"]["B2"]["n"], n_m["I"],
        D["mc"]["II"]["staves"]["B2"]["n"], n_m["II"])
    D["variants"] = {"calib_included": var}

    # ---------- provenance + outputs ----------
    D["provenance"] = {
        "script": "scripts/s23_sample12_data_mc_comparison.py",
        "generated_utc": time.strftime("%Y-%m-%dT%H:%M:%S+00:00", time.gmtime()),
        "data_file": str(Path(args.data).resolve()),
        "mc_file": str(Path(args.mc).resolve()),
        "data_definition": {
            "sample_I": "group == sample_i_analysis (runs 44-57; A AND B hardware trigger)",
            "sample_II": "group == sample_ii_analysis (runs 58-63,65; B-only hardware trigger)",
            "calibration_runs_excluded": "31-42 (sample_i_calib), 64 (sample_ii_calib)",
        },
        "mc_definition": {
            "sample_I": "sample_I == 1 (inclusive truth mimic: A+B entry within 15 ns)",
            "sample_II": "sample_II == 1 (inclusive: B entry; superset of sample_I)",
            "sample_II_excl": "sample_II == 1 AND sample_I == 0",
            "untrig": "all A>1000 rows (no trigger mimic)",
        },
        "high_adc_data": high_adc,
        "mc_high_thresholds_quantile_matched": mc_thr,
        "hist_bins_adc": bins.tolist(),
        "n_rows": {"data": int(len(data)), "mc": int(len(mc))},
        "caveats": [
            "mc02 gain is an UNKNOWN placeholder — shapes and between-sample ratios only",
            "MC geometry lacks upstream material (MV3): absolute occupancy chi2 stays large",
            "data samples are disjoint run sets; MC mimics inclusive (exclusive II\\I reported)",
            "LayerID->stave mapping 'paired' UNDER REVIEW",
        ],
    }

    (out_dir / "s23_summary.json").write_text(
        json.dumps(D, indent=2, default=float) + "\n", encoding="utf-8")
    make_figure(out_dir / "s23_overview.png", D, bins, amp, high_adc)
    write_report(out_dir, D, args, high_adc, mc_thr)
    print(f"[s23] done in {time.time()-t0:.0f}s -> {out_dir}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
