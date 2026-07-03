#!/usr/bin/env python3
"""
Generate publication-quality figures for the CCB Test-Beam wiki (docs/figures/).

Standards applied (nature-figure skill):
- sans-serif (Arial/DejaVu), editable-text settings, no top/right spines
- one restrained colorblind-safe palette across all figures
- every axis labelled with units; error bars / CIs drawn wherever the source
  artifact provides them; no fabricated uncertainties
- every number traceable to a reports/<id>/ artifact (JSON read at run time
  where available; otherwise the source report is cited next to the constant)

Figures regenerated (WIKI-referenced):
  03_timing_resolution.png   per-stave timing summary (S02/S03/S05 + external note)
  04_mc_vs_data.png          MV4 honest rerun (reports/mv4_timing_1783077795)
  05_pca_vs_ae.png           P01 PCA vs autoencoder compression
  06_stopping_depth.png      MV3 stopping-depth FAIL
  07_pid_auc.png             MV1 PID validation (reports/mv1_mv2_truth_pid_energy_1783077795)
  08_c12_anomaly.png         early-peak anomaly SCHEMATIC (illustrative only; MV6 retracted)
  09_systematic_budget.png   MC-validation status chart (no fabricated magnitudes)
  10_ml_landscape.png        ML win/loss landscape
  24_s21_denrichment.png     S21 Sample I/II deuteron enrichment
                             (reports/s21_sample12_trigger_truth_1783077969)

Output: PNG at 200 dpi (the wiki is a screen deliverable; font sizes are chosen
for ~800 px display width rather than the 7 pt print rule).

Run with: /home/billy/anaconda3/envs/nnbar_env/bin/python scripts/generate_wiki_figures.py
"""

import json
import os
import sys

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import matplotlib.patches as mpatches  # noqa: E402
import numpy as np  # noqa: E402

# ── Global style (nature-figure quick-start, adapted for wiki PNG) ──────────
plt.rcParams.update({
    "font.family": "sans-serif",
    "font.sans-serif": ["Arial", "DejaVu Sans", "Liberation Sans"],
    "svg.fonttype": "none",
    "pdf.fonttype": 42,
    "font.size": 9,
    "axes.titlesize": 10,
    "axes.labelsize": 9,
    "legend.fontsize": 8,
    "xtick.labelsize": 8.5,
    "ytick.labelsize": 8.5,
    "axes.spines.right": False,
    "axes.spines.top": False,
    "axes.linewidth": 0.8,
    "legend.frameon": False,
    "figure.facecolor": "white",
    "axes.facecolor": "white",
    "savefig.bbox": "tight",
    "savefig.pad_inches": 0.08,
})

# Colorblind-safe palette (nature-figure PALETTE)
PALETTE = {
    "blue_main": "#0F4D92",
    "blue_secondary": "#3775BA",
    "red_strong": "#B64342",
    "teal": "#42949E",
    "violet": "#9A4D8E",
    "green_3": "#8BCF8B",
    "neutral_light": "#CFCECE",
    "neutral_mid": "#767676",
    "neutral_dark": "#4D4D4D",
}

OUTPUT_DIR = "docs/figures"
DPI = 200
REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

S21_JSON = os.path.join(REPO, "reports/s21_sample12_trigger_truth_1783077969/s21_summary.json")
MV4_JSON = os.path.join(REPO, "reports/mv4_timing_1783077795/mv4_summary.json")
MV12_JSON = os.path.join(REPO, "reports/mv1_mv2_truth_pid_energy_1783077795/mv1_mv2_truth_summary.json")

STAVES = ["B2", "B4", "B6", "B8"]


def load_json(path):
    with open(path) as fh:
        return json.load(fh)


def save(fig, name):
    path = os.path.join(OUTPUT_DIR, name)
    fig.savefig(path, dpi=DPI)
    plt.close(fig)
    print(f"  written {path}")
    return path


# ── Figure 24: S21 Sample I/II deuteron enrichment (NEW, hero figure) ───────
def fig_s21_enrichment():
    s21 = load_json(S21_JSON)
    kt = s21["key_table"]["staves"]
    samples = s21["samples"]

    fig, axes = plt.subplots(1, 3, figsize=(11.4, 3.5))

    # Panel a: deuteron fraction per stave, Sample I vs Sample II, 95% CI
    ax = axes[0]
    x = np.arange(len(STAVES))
    w = 0.34
    for off, key, color, label in [
        (-w / 2, "sample_I", PALETTE["blue_main"], "Sample I (A·B coincidence)"),
        (+w / 2, "sample_II", PALETTE["teal"], "Sample II (B-only, inclusive)"),
    ]:
        f = np.array([kt[s][key]["fraction"] for s in STAVES])
        lo = np.array([kt[s][key]["ci95"][0] for s in STAVES])
        hi = np.array([kt[s][key]["ci95"][1] for s in STAVES])
        ax.bar(x + off, f, w, color=color, edgecolor="black", linewidth=0.8,
               yerr=[f - lo, hi - f], capsize=3, label=label,
               error_kw=dict(ecolor="black", lw=0.9))
    ax.set_xticks(x)
    ax.set_xticklabels(STAVES)
    ax.set_ylabel("Deuteron fraction of charged B-arm tracks")
    ax.set_ylim(0, 0.85)
    ax.legend(loc="upper right", fontsize=7.5)
    ax.set_title("a  Truth deuteron fraction per stave", loc="left")

    # Panel b: enrichment ratio I/II per stave (inclusive and exclusive)
    ax2 = axes[1]
    for off, key, color, marker, label in [
        (-0.10, "enrichment_I_over_II_inclusive", PALETTE["blue_main"], "o", "I / II (inclusive)"),
        (+0.10, "enrichment_I_over_II_exclusive", PALETTE["violet"], "s", "I / (II\\I) (exclusive)"),
    ]:
        r = np.array([kt[s][key]["ratio"] for s in STAVES])
        lo = np.array([kt[s][key]["ci_low"] for s in STAVES])
        hi = np.array([kt[s][key]["ci_high"] for s in STAVES])
        ax2.errorbar(x + off, r, yerr=[r - lo, hi - r], fmt=marker, markersize=6,
                     color=color, capsize=3, lw=1.1, label=label)
    ax2.axhline(1.0, color=PALETTE["neutral_mid"], linestyle="--", lw=0.9)
    ax2.text(3.42, 1.03, "no enrichment", fontsize=7, color=PALETTE["neutral_mid"],
             ha="right")
    ax2.set_xticks(x)
    ax2.set_xticklabels(STAVES)
    ax2.set_ylabel("Deuteron-fraction ratio, Sample I / Sample II")
    ax2.set_yscale("log")
    ax2.set_yticks([0.25, 0.5, 1.0, 2.0])
    ax2.set_yticklabels(["0.25", "0.5", "1", "2"])
    ax2.legend(loc="lower left", fontsize=7.5)
    ax2.set_title("b  Enrichment fades with depth", loc="left")

    # Panel c: median energy deposit per stave (Sample I), deuteron vs proton,
    # whiskers = 16-84% quantile span from the S21 artifact
    ax3 = axes[2]
    for off, sp, color, label in [
        (-w / 2, "d", PALETTE["blue_main"], "deuteron"),
        (+w / 2, "p", PALETTE["red_strong"], "proton"),
    ]:
        med = np.array([samples["I"]["stave_occupancy"][s]["edep_stats"][sp]["median_MeV"]
                        for s in STAVES])
        q16 = np.array([samples["I"]["stave_occupancy"][s]["edep_stats"][sp]["q16_MeV"]
                        for s in STAVES])
        q84 = np.array([samples["I"]["stave_occupancy"][s]["edep_stats"][sp]["q84_MeV"]
                        for s in STAVES])
        ax3.bar(x + off, med, w, color=color, edgecolor="black", linewidth=0.8,
                yerr=[med - q16, q84 - med], capsize=3, label=label,
                error_kw=dict(ecolor="black", lw=0.9))
    ax3.set_xticks(x)
    ax3.set_xticklabels(STAVES)
    ax3.set_ylabel("Median energy deposit (MeV)")
    ax3.legend(loc="upper right", fontsize=7.5)
    ax3.set_title("c  Sample I energy deposits (16–84% span)", loc="left")

    fig.suptitle(
        "S21 — GEANT4 trigger-truth: the A·B coincidence enriches deuterons in the upstream B staves",
        fontsize=10, y=1.04)
    return save(fig, "24_s21_denrichment.png")


# ── Figure 04: MV4 honest rerun, MC vs data ─────────────────────────────────
def fig_mc_vs_data():
    mv4 = load_json(MV4_JSON)
    mc_pair = mv4["mc_pair_equivalent_ns"]
    ratio = mv4["mc_over_data_ratio"]
    data_raw = mv4["data_reference"]["S02_raw_cfd20_pair_sigma68"]
    data_corr = mv4["data_reference"]["S03_corrected_pair_sigma68"]

    fig, axes = plt.subplots(1, 2, figsize=(8.8, 3.5))

    # Panel a: pair-difference sigma68, MC vs data anchors
    ax = axes[0]
    stages = ["raw CFD20", "timewalk-corrected"]
    mc_vals = [mc_pair["raw"], mc_pair["corrected"]]
    mc_errs = [mc_pair["raw_unc"], mc_pair["corrected_unc"]]
    data_vals = [data_raw, data_corr]
    x = np.arange(2)
    w = 0.34
    ax.bar(x - w / 2, mc_vals, w, yerr=mc_errs, capsize=4,
           color=PALETTE["blue_main"], edgecolor="black", linewidth=0.9,
           label="MC pair-equivalent (single-trace × √2)",
           error_kw=dict(ecolor="black", lw=1.0))
    ax.bar(x + w / 2, data_vals, w,
           color=PALETTE["red_strong"], edgecolor="black", linewidth=0.9,
           label="data pair-difference (S02 / S03)")
    for xi, v, e in zip(x - w / 2, mc_vals, mc_errs):
        ax.text(xi, v + e + 0.07, f"{v:.3f}", ha="center", fontsize=8)
    for xi, v in zip(x + w / 2, data_vals):
        ax.text(xi, v + 0.07, f"{v:.2f}", ha="center", fontsize=8)
    ax.set_xticks(x)
    ax.set_xticklabels(stages)
    ax.set_ylabel("Pair-difference σ₆₈ (ns)")
    ax.set_ylim(0, 3.7)
    ax.legend(loc="upper right", fontsize=7.2)
    ax.set_title("a  MV4 rerun vs data anchors", loc="left")

    # Panel b: MC/data ratio; error bars are MC bootstrap only
    ax2 = axes[1]
    r_vals = [ratio["raw"], ratio["corrected"]]
    r_errs = [ratio["raw_unc_mc_only"], ratio["corrected_unc_mc_only"]]
    ax2.errorbar(x, r_vals, yerr=r_errs, fmt="o", markersize=7,
                 color=PALETTE["blue_main"], capsize=4, lw=1.2)
    ax2.axhline(1.0, color=PALETTE["neutral_mid"], linestyle="--", lw=0.9)
    for xi, v in zip(x, r_vals):
        ax2.text(xi + 0.06, v, f"{v:.3f}", fontsize=8.5, va="center")
    ax2.set_xticks(x)
    ax2.set_xticklabels(stages)
    ax2.set_xlim(-0.5, 1.5)
    ax2.set_ylabel("σ₆₈ ratio, MC / data")
    ax2.set_ylim(0.55, 1.55)
    ax2.set_title("b  Agreement scale (not a hypothesis test)", loc="left")
    ax2.text(0.5, 0.05,
             "data σ₆₈ uncertainty unmeasured → no pull computed;\n"
             "error bars are the MC bootstrap component only",
             transform=ax2.transAxes, ha="center", fontsize=7,
             color=PALETTE["neutral_dark"])

    fig.suptitle("MV4 timing validation, honest rerun 2026-07-03 — status: REVIEW (unmatched comparison)",
                 fontsize=10, y=1.04)
    return save(fig, "04_mc_vs_data.png")


# ── Figure 03: per-stave timing resolution ──────────────────────────────────
# Sources: S03 (B4/B8, analytic timewalk), external-note Gaussian core (B6,
# UNDER REVIEW: not sigma68), S05 combination (UNDER REVIEW: covariance
# validation withdrawn 2026-07-03). Error bars are half-widths of the quoted
# ranges in WIKI section 4.4, not fitted CIs.
def fig_timing_resolution():
    labels = ["B2", "B4", "B6*", "B8", "B4+B6+B8*"]
    vals = np.array([2.8, 1.45, 0.715, 0.93, 0.55])
    errs = np.array([0.0, 0.05, 0.035, 0.0, 0.01])
    under_review = [False, False, True, False, True]

    fig, ax = plt.subplots(figsize=(6.6, 3.6))
    x = np.arange(len(labels))
    for i, (v, e, ur) in enumerate(zip(vals, errs, under_review)):
        color = PALETTE["neutral_light"] if ur else PALETTE["blue_main"]
        edge = PALETTE["neutral_mid"] if ur else "black"
        ax.bar(i, v, 0.62, color=color, edgecolor=edge, linewidth=0.9,
               hatch="//" if ur else None,
               yerr=e if e > 0 else None, capsize=4,
               error_kw=dict(ecolor=PALETTE["neutral_dark"], lw=1.0))
        ax.text(i, v + e + 0.09, f"{v:.2f}", ha="center", fontsize=8.5)

    ax.set_xticks(x)
    ax.set_xticklabels(labels)
    ax.set_ylabel("Timing resolution σ₆₈ (ns)")
    ax.set_ylim(0, 3.7)
    ax.annotate("topology-dominated;\nexcluded from precision timing",
                xy=(0, 2.85), xytext=(0.85, 3.25), fontsize=7.5,
                color=PALETTE["neutral_dark"], ha="center",
                arrowprops=dict(arrowstyle="->", color=PALETTE["neutral_dark"], lw=0.8))
    legend = [
        mpatches.Patch(facecolor=PALETTE["blue_main"], edgecolor="black",
                       label="quoted range (S03)"),
        mpatches.Patch(facecolor=PALETTE["neutral_light"], edgecolor=PALETTE["neutral_mid"],
                       hatch="//", label="under review (2026-07-03)"),
    ]
    ax.legend(handles=legend, loc="upper right", fontsize=7.5)
    fig.text(0.99, -0.04,
             "*B6 is the external note's Gaussian-core σ (not σ₆₈); the B4+B6+B8 combination assumes\n"
             "independent stave errors — its covariance validation was withdrawn 2026-07-03.",
             ha="right", fontsize=7, color=PALETTE["neutral_dark"])
    return save(fig, "03_timing_resolution.png")


# ── Figure 05: PCA vs AE pulse-shape compression (P01) ──────────────────────
# Source: reports/1780997954.15517.0cbc248c__p01_self_supervised_waveform_representation/
def fig_pca_vs_ae():
    dims = np.array([2, 3, 4, 8])
    pca = np.array([0.02622, 0.01416, 0.00880, 0.00166])
    ae = np.array([0.01294, 0.00841, 0.00527, 0.00292])

    fig, ax = plt.subplots(figsize=(5.6, 3.4))
    ax.plot(dims, pca, "o-", color=PALETTE["blue_main"], markersize=6, lw=1.4, label="PCA")
    ax.plot(dims, ae, "s-", color=PALETTE["red_strong"], markersize=6, lw=1.4, label="Autoencoder")
    ax.set_yscale("log")
    ax.set_xticks(dims)
    ax.set_xlabel("Latent dimension")
    ax.set_ylabel("Reconstruction MSE (normalized ADC²)")
    ax.legend(loc="upper right")
    ax.annotate("AE better at d ≤ 4", xy=(3, 0.0084), xytext=(4.4, 0.02),
                fontsize=8, color=PALETTE["neutral_dark"],
                arrowprops=dict(arrowstyle="->", color=PALETTE["neutral_dark"], lw=0.8))
    ax.annotate("PCA overtakes at d = 8", xy=(8, 0.00166), xytext=(5.8, 0.0008),
                fontsize=8, color=PALETTE["neutral_dark"],
                arrowprops=dict(arrowstyle="->", color=PALETTE["neutral_dark"], lw=0.8))
    return save(fig, "05_pca_vs_ae.png")


# ── Figure 06: MV3 stopping-depth profile FAIL ──────────────────────────────
# Source: reports/mv3_stopping_depth/ (fractions in %; chi2/ndf = 68,269)
def fig_stopping_depth():
    mc = np.array([47.0, 18.2, 12.5, 22.3])
    data = np.array([87.6, 6.3, 3.9, 2.3])

    fig, axes = plt.subplots(1, 2, figsize=(8.8, 3.5))
    x = np.arange(len(STAVES))
    w = 0.34

    ax = axes[0]
    ax.bar(x - w / 2, mc, w, label="MC (GEANT4)", color=PALETTE["violet"],
           edgecolor="black", linewidth=0.8)
    ax.bar(x + w / 2, data, w, label="Data", color=PALETTE["teal"],
           edgecolor="black", linewidth=0.8)
    ax.set_xticks(x)
    ax.set_xticklabels(STAVES)
    ax.set_ylabel("Fraction of selected pulses (%)")
    ax.legend(loc="upper right")
    ax.set_title("a  Stopping-depth profile", loc="left")

    ax2 = axes[1]
    ratios = data / mc
    ax2.plot(x, ratios, "o", markersize=7, color=PALETTE["red_strong"])
    ax2.axhline(1.0, color=PALETTE["neutral_mid"], linestyle="--", lw=0.9)
    for xi, r in zip(x, ratios):
        ax2.text(xi + 0.08, r, f"{r:.2f}", fontsize=8.5, va="center")
    ax2.set_xticks(x)
    ax2.set_xticklabels(STAVES)
    ax2.set_xlim(-0.5, 3.7)
    ax2.set_yscale("log")
    ax2.set_ylabel("Data / MC ratio")
    ax2.set_title("b  MC overpredicts B8 penetration ×10", loc="left")

    fig.suptitle("MV3 stopping-depth — FAIL (χ²/ndf = 68,269; root cause not established)",
                 fontsize=10, y=1.04, color=PALETTE["red_strong"])
    return save(fig, "06_stopping_depth.png")


# ── Figure 07: MV1 PID validation ───────────────────────────────────────────
def fig_pid_auc():
    mv1 = load_json(MV12_JSON)["MV1_pid"]
    methods = ["Single-cut ΔE", "Logistic regression", "HGB"]
    aucs = [None, mv1["logreg_auc"], mv1["hgb_auc"]]
    purities = [mv1["cut_purity"], mv1["logreg_purity_at_90eff"], mv1["hgb_purity_at_90eff"]]

    fig, ax = plt.subplots(figsize=(6.2, 3.5))
    x = np.arange(len(methods))
    w = 0.34
    auc_x = [xi - w / 2 for xi, a in zip(x, aucs) if a is not None]
    auc_v = [a for a in aucs if a is not None]
    ax.bar(auc_x, auc_v, w, label="AUC", color=PALETTE["blue_main"],
           edgecolor="black", linewidth=0.8)
    ax.bar(x + w / 2, purities, w, label="Purity at 90% efficiency",
           color=PALETTE["teal"], edgecolor="black", linewidth=0.8)
    for xi, v in zip(auc_x, auc_v):
        ax.text(xi, v + 0.004, f"{v:.4f}", ha="center", fontsize=8)
    for xi, v in zip(x + w / 2, purities):
        ax.text(xi, v + 0.004, f"{v:.4f}", ha="center", fontsize=8)
    ax.set_xticks(x)
    ax.set_xticklabels(methods)
    ax.set_ylabel("Score (dimensionless)")
    ax.set_ylim(0.80, 1.03)
    ax.legend(loc="lower right", fontsize=8)
    ax.text(0 - w / 2, 0.81, "no AUC\n(hard cut)", ha="center", fontsize=7,
            color=PALETTE["neutral_dark"])
    ax.set_title("MV1 proton/deuteron PID on GEANT4 truth (400,369 tracks) — MC truth ceiling",
                 loc="left", fontsize=9.5)
    return save(fig, "07_pid_auc.png")


# ── Figure 08: early-peak anomaly schematic (ILLUSTRATIVE ONLY) ─────────────
# The species attribution (MV6 "C12 recoils") is RETRACTED 2026-07-03.
# The waveforms below are drawn shapes, not measured pulses; they illustrate
# the early-peak signature of the P09a anomaly class only.
def fig_anomaly_schematic():
    rng = np.random.default_rng(7)
    t = np.arange(18) * 10.0
    normal = np.exp(-0.5 * ((t - 55) / 15) ** 2) + 0.015 * rng.standard_normal(18)
    early = 0.8 * np.exp(-0.5 * ((t - 15) / 5) ** 2) + 0.01 * rng.standard_normal(18)

    fig, ax = plt.subplots(figsize=(6.2, 3.3))
    ax.plot(t, normal, "o-", color=PALETTE["blue_main"], markersize=5, lw=1.3,
            label="typical pulse (peak ≈ sample 5)")
    ax.plot(t, early, "s-", color=PALETTE["red_strong"], markersize=5, lw=1.3,
            label="early-peak anomaly class (peak ≈ sample 1–2)")
    ax.set_xlabel("Time (ns)")
    ax.set_ylabel("Amplitude (arbitrary units)")
    ax.set_xlim(0, 175)
    ax.legend(loc="upper right", fontsize=7.5)
    ax.set_title("Early-peak anomaly signature — SCHEMATIC (drawn shapes, not data)",
                 loc="left", fontsize=9.5)
    ax.text(0.99, 0.62, "species attribution (MV6 \"C12\")\nretracted 2026-07-03",
            transform=ax.transAxes, ha="right", fontsize=7.5,
            color=PALETTE["red_strong"])
    return save(fig, "08_c12_anomaly.png")


# ── Figure 09: MC-validation status (no fabricated magnitudes) ──────────────
def fig_validation_status():
    rows = [
        ("MV0 gain", "RETRACTED", "gain UNKNOWN (v1 and v2 both retracted)"),
        ("MV1 PID", "PASS", "AUC 0.986 on GEANT4 truth (rerun 2026-07-03)"),
        ("MV2 energy/range", "RERUN OK", "MeV-scale after unit fix; containment p 0.70 / d 0.84"),
        ("MV3 stopping depth", "FAIL", "χ²/ndf = 68,269; root cause not established"),
        ("MV4 timing", "REVIEW", "MC pair-equiv 2.09 ns between data 2.99 (raw) and 1.50 (corr)"),
        ("MV5 pile-up", "RETRACTED", "MC τ_eff was a copy of the data value; R_max is data-only"),
        ("MV6 anomaly ID", "RETRACTED", "C12 attribution unsupported; species open"),
        ("S21 trigger truth", "CONFIRMED", "Sample I d-enrichment in B2: ratio 1.519 [1.510, 1.528]"),
    ]
    status_color = {
        "PASS": PALETTE["blue_main"],
        "CONFIRMED": PALETTE["blue_main"],
        "RERUN OK": PALETTE["teal"],
        "REVIEW": PALETTE["neutral_mid"],
        "FAIL": PALETTE["red_strong"],
        "RETRACTED": PALETTE["red_strong"],
    }

    fig, ax = plt.subplots(figsize=(8.6, 3.8))
    ax.set_xlim(0, 10)
    ax.set_ylim(-0.5, len(rows) - 0.5)
    ax.axis("off")
    for i, (name, status, note) in enumerate(reversed(rows)):
        c = status_color[status]
        ax.text(0.0, i, name, fontsize=9, va="center", fontweight="bold")
        ax.add_patch(mpatches.FancyBboxPatch((2.55, i - 0.28), 1.5, 0.56,
                                             boxstyle="round,pad=0.02",
                                             facecolor=c, edgecolor="none", alpha=0.9))
        ax.text(3.3, i, status, fontsize=8, va="center", ha="center",
                color="white", fontweight="bold")
        ax.text(4.35, i, note, fontsize=8, va="center", color=PALETTE["neutral_dark"])
    ax.set_title("MC-validation status after the 2026-07-02 external review and 2026-07-03 reruns",
                 loc="left", fontsize=9.5, pad=12)
    return save(fig, "09_systematic_budget.png")


# ── Figure 10: ML performance landscape ─────────────────────────────────────
def fig_ml_landscape():
    rows = [
        ("Saturation recovery", "ML wins", "res68 0.032–0.046 vs 0.104–0.286 (P07)"),
        ("Duplicate-readout amplitude", "ML wins", "res68 0.003–0.009 vs 0.12–0.20 (P04)"),
        ("Two-pulse recovery", "Traditional favoured", "matched risk-coverage P05f; S11 table superseded"),
        ("Timewalk correction", "Tie / loss", "analytic B/A model 1.49–1.55 ns ≈ ML 1.39–1.47 ns (S03)"),
        ("Pile-up rate model", "Tie / loss", "analytic Poisson model already optimal (S10)"),
        ("Deep-net timing", "ML loses", "CNN/MLP on raw waveform < analytic timewalk (P03)"),
        ("PID (data-only)", "Leakage", "label = f(input); AUC ≈ 1.0 is self-referential (S07)"),
        ("Representation superiority", "CORRECTED", "failed run-family and event-block controls (P01/P02)"),
    ]
    cat_color = {
        "ML wins": PALETTE["blue_main"],
        "Traditional favoured": PALETTE["teal"],
        "Tie / loss": PALETTE["neutral_mid"],
        "ML loses": PALETTE["neutral_mid"],
        "Leakage": PALETTE["red_strong"],
        "CORRECTED": PALETTE["red_strong"],
    }

    fig, ax = plt.subplots(figsize=(8.8, 3.8))
    ax.set_xlim(0, 10)
    ax.set_ylim(-0.5, len(rows) - 0.5)
    ax.axis("off")
    for i, (domain, verdict, note) in enumerate(reversed(rows)):
        c = cat_color[verdict]
        ax.text(0.0, i, domain, fontsize=9, va="center", fontweight="bold")
        ax.add_patch(mpatches.FancyBboxPatch((3.35, i - 0.28), 2.0, 0.56,
                                             boxstyle="round,pad=0.02",
                                             facecolor=c, edgecolor="none", alpha=0.9))
        ax.text(4.35, i, verdict, fontsize=8, va="center", ha="center",
                color="white", fontweight="bold")
        ax.text(5.6, i, note, fontsize=7.5, va="center", color=PALETTE["neutral_dark"])
    ax.set_title("Where ML helps — and where it does not (verdicts after leakage controls)",
                 loc="left", fontsize=9.5, pad=12)
    return save(fig, "10_ml_landscape.png")


# ── Main ────────────────────────────────────────────────────────────────────
def main():
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    print(f"Generating figures in {OUTPUT_DIR}/ ...")
    fig_s21_enrichment()
    fig_mc_vs_data()
    fig_timing_resolution()
    fig_pca_vs_ae()
    fig_stopping_depth()
    fig_pid_auc()
    fig_anomaly_schematic()
    fig_validation_status()
    fig_ml_landscape()
    print("done")
    return 0


if __name__ == "__main__":
    sys.exit(main())
