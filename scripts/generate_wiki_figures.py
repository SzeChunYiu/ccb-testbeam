#!/usr/bin/env python3
"""
Generate publication-quality figures for the CCB Test-Beam wiki.

This script creates:
1.  Experimental setup schematic (beamline → detectors)
2.  Analysis pipeline flowchart
3.  Per-stave timing resolution comparison
4.  MC vs Data comparison: timing, pile-up live-time
5.  PCA explained variance and AE vs PCA MSE comparison
6.  C12 anomaly waveform example
7.  Systematic uncertainty budget

All figures are saved to docs/figures/ as PNG files.
Requires: matplotlib, numpy (standard scientific Python stack).
"""

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from matplotlib.patches import FancyBboxPatch, FancyArrowPatch, Arc, Rectangle
import numpy as np
import os
import sys

# ── Configuration ──────────────────────────────────────────────────────────
OUTPUT_DIR = "docs/figures"
DPI = 150
STYLE = "seaborn-v0_8-darkgrid"

# ── Data (from FINDINGS_SYNTHESIS.md and reports) ──────────────────────────

# Per-stave timing resolution
STAVE_TIMING = {
    "B2": 2.8,       # ~2.5-3.5 ns (topology-dominated)
    "B4": 1.45,      # ~1.4-1.5 ns
    "B6": 0.72,      # ~0.68-0.75 ns (best)
    "B8": 0.93,      # ~0.93 ns
    "B4+B6+B8": 0.55, # combined
}

# PCA vs AE comparison
PCA_AE_DATA = {
    "latent_dim": [2, 3, 4, 8],
    "pca_mse": [0.02622, 0.01416, 0.00880, 0.00166],
    "ae_mse": [0.01294, 0.00841, 0.00527, 0.00292],
}

# MC vs Data comparison
MC_VS_DATA = {
    "timing_raw": {"mc": 1.744, "mc_err": 0.007, "data": 1.85, "label": "Timing σ68 raw (ns)"},
    "timing_corrected": {"mc": 1.770, "mc_err": 0.010, "data": 1.50, "label": "Timing σ68 corrected (ns)"},
    "pileup_rmax": {"mc": 3.044, "mc_err": 0.005, "data": 3.05, "label": "Pile-up R_max (MHz)"},
    "pileup_taueff": {"mc": 124.8, "mc_err": 1.0, "data": 124.79, "label": "Pile-up τ_eff (ns)"},
}

# Stopping-depth profile
STOPPING_DEPTH = {
    "staves": ["B2", "B4", "B6", "B8"],
    "mc": [47.0, 18.2, 12.5, 22.3],
    "data": [87.6, 6.3, 3.9, 2.3],
}

# PID AUC
PID_AUC = {
    "methods": ["Single-cut ΔE", "Logistic Reg.", "HGB (MC truth)"],
    "auc": [0.8910, 0.9629, 0.9860],
    "purity": [0.8910, 0.9489, 0.9644],
}

# Systematic uncertainties
SYST_BUDGET = {
    "sources": ["Gain (MV0)\n±30%", "Stopping-depth\n(MV3)", "Timing\n(MV4)", "C12 anomaly\n(MV6)", "Pile-up\n(MV5)"],
    "magnitudes": [30.0, 5.0, 3.0, 0.1, 0.0],
    "colors": ["#e74c3c", "#e67e22", "#f39c12", "#2ecc71", "#3498db"],
}

# C12 anomaly waveform (mock based on MV6 description)
def mock_c12_waveform():
    """Generate representative normal and C12-recoil waveforms."""
    t = np.arange(18) * 10  # 10 ns spacing
    # Normal proton pulse: peaks at sample ~5 (50 ns)
    normal = np.exp(-0.5 * ((t - 55) / 15)**2) * 1.0 + 0.02 * np.random.randn(18)
    # C12 recoil: peaks at sample ~1-2 (10-20 ns), very narrow
    c12 = np.exp(-0.5 * ((t - 15) / 5)**2) * 0.8 + 0.01 * np.random.randn(18)
    # Set baseline
    normal[:3] += 0.0
    c12[:3] += 0.0
    return t, normal, c12


# ── Plotting Functions ──────────────────────────────────────────────────────

def setup_style():
    """Apply consistent styling."""
    plt.style.use(STYLE)
    matplotlib.rcParams.update({
        "figure.facecolor": "white",
        "axes.facecolor": "#f8f9fa",
        "font.size": 11,
        "axes.titlesize": 13,
        "axes.labelsize": 11,
        "legend.fontsize": 10,
        "figure.dpi": DPI,
        "savefig.dpi": DPI,
        "savefig.bbox": "tight",
        "savefig.pad_inches": 0.1,
    })


def fig_experimental_setup():
    """Figure 1: Experimental setup schematic."""
    fig, ax = plt.subplots(1, 1, figsize=(12, 5))
    ax.set_xlim(0, 14)
    ax.set_ylim(0, 6)
    ax.axis("off")
    ax.set_title("CCB Test-Beam Experimental Setup", fontweight="bold", pad=20)

    # Beam line
    ax.annotate("", xy=(12.5, 3), xytext=(0.5, 3),
                arrowprops=dict(arrowstyle="->", color="#e74c3c", lw=3))
    ax.text(6.5, 3.7, "190 MeV protons", ha="center", fontweight="bold", color="#e74c3c")

    # Target
    target = Rectangle((2.5, 2.2), 0.8, 1.6, facecolor="#f39c12", edgecolor="black", lw=2, alpha=0.8)
    ax.add_patch(target)
    ax.text(2.9, 3.0, "CD₂\nTarget", ha="center", va="center", fontsize=9, fontweight="bold")

    # Trigger scintillators
    trig = Rectangle((4.0, 2.4), 0.6, 1.2, facecolor="#3498db", edgecolor="black", lw=1.5, alpha=0.7)
    ax.add_patch(trig)
    ax.text(4.3, 3.0, "Trigger\nScints", ha="center", va="center", fontsize=8)

    # TPC
    tpc = Rectangle((5.2, 2.0), 1.2, 2.0, facecolor="#9b59b6", edgecolor="black", lw=1.5, alpha=0.6)
    ax.add_patch(tpc)
    ax.text(5.8, 3.0, "TPC\n(tracking)", ha="center", va="center", fontsize=8)

    # A-Stack
    a_stack = Rectangle((7.5, 1.5), 1.5, 3.0, facecolor="#1abc9c", edgecolor="black", lw=2, alpha=0.7)
    ax.add_patch(a_stack)
    ax.text(8.25, 4.3, "A-Stack (HRD)", ha="center", fontsize=9, fontweight="bold")
    ax.text(8.25, 3.0, "A1 A3 A5 A7\n~100 cm", ha="center", fontsize=8)

    # B-Stack
    b_stack = Rectangle((9.8, 1.5), 1.5, 3.0, facecolor="#2ecc71", edgecolor="black", lw=2, alpha=0.7)
    ax.add_patch(b_stack)
    ax.text(10.55, 4.3, "B-Stack (HRD)", ha="center", fontsize=9, fontweight="bold")
    ax.text(10.55, 3.0, "B2 B4 B6 B8\n~100 cm", ha="center", fontsize=8)
    ax.text(10.55, 1.8, "★ Primary analysis", ha="center", fontsize=7, color="#2ecc71", fontweight="bold")

    # Distance annotations
    ax.annotate("", xy=(7.5, 5.0), xytext=(3.3, 5.0),
                arrowprops=dict(arrowstyle="<->", color="gray", lw=1))
    ax.text(5.4, 5.2, "~100 cm", ha="center", fontsize=8, color="gray")

    # Waveform inset arrow
    ax.annotate("18-sample\nwaveform", xy=(11.3, 1.0), xytext=(11.3, 0.2),
                fontsize=8, ha="center", color="#2ecc71",
                arrowprops=dict(arrowstyle="->", color="#2ecc71", lw=1.5))

    # Legend-like annotations
    ax.text(0.5, 0.5, "Beam: proton, T_p = 190 MeV", fontsize=8, color="gray")
    ax.text(0.5, 0.2, "Target: deuterated polyethylene (CD₂)", fontsize=8, color="gray")

    plt.tight_layout()
    path = os.path.join(OUTPUT_DIR, "01_experimental_setup.png")
    fig.savefig(path)
    plt.close(fig)
    print(f"  ✓ {path}")
    return path


def fig_analysis_pipeline():
    """Figure 2: Analysis pipeline flowchart."""
    fig, ax = plt.subplots(1, 1, figsize=(14, 6))
    ax.set_xlim(0, 16)
    ax.set_ylim(0, 6)
    ax.axis("off")
    ax.set_title("Analysis Pipeline", fontweight="bold", pad=20)

    boxes = [
        (1, 3.5, 3, 1.5, "#34495e", "Raw ROOT Files\n(110 files, ~810 MB)\nhrdb_run_NNNN.root", "white"),
        (5.5, 3.5, 3, 1.5, "#2980b9", "Pulse Table\n640,737 selected pulses\nbaseline median(samples 0-3)\nA > 1000 ADC", "white"),
        (10, 3.5, 4.5, 1.5, "#27ae60", "Analysis Branches", "white"),
        (10, 5.0, 1.3, 0.7, "#e74c3c", "Timing\nCFD→Timewalk", "white"),
        (11.6, 5.0, 1.3, 0.7, "#e67e22", "Pile-up\nLive-time→R", "white"),
        (13.2, 5.0, 1.3, 0.7, "#9b59b6", "PID\nΔE-E→AUC", "white"),
    ]

    for x, y, w, h, color, label, textcolor in boxes:
        rect = FancyBboxPatch((x, y), w, h, boxstyle="round,pad=0.1",
                              facecolor=color, edgecolor="black", lw=1.5, alpha=0.85)
        ax.add_patch(rect)
        ax.text(x + w/2, y + h/2, label, ha="center", va="center",
                fontsize=8, color=textcolor, fontweight="bold")

    # Arrows
    for (x1, x2, y) in [(4, 5.5, 4.25), (8.5, 10, 4.25)]:
        ax.annotate("", xy=(x2, y), xytext=(x1, y),
                    arrowprops=dict(arrowstyle="->", color="black", lw=2))

    # Branch arrows from main box
    for x in [10.65, 12.25, 13.85]:
        ax.annotate("", xy=(x, 5.0), xytext=(x, 5.0),
                    arrowprops=dict(arrowstyle="->", color="gray", lw=1))

    # MC validation pipeline (bottom)
    ax.text(8, 1.2, "MC Validation Pipeline", fontsize=10, fontweight="bold", ha="center", color="#8e44ad")
    mc_boxes = [
        (3.5, 0.3, 1.8, 0.6, "#8e44ad", "MV0: Digitizer\nGain 92 ADC/MeV"),
        (5.8, 0.3, 1.8, 0.6, "#8e44ad", "MV1: PID\nAUC 0.986 ✅"),
        (8.1, 0.3, 1.8, 0.6, "#8e44ad", "MV3: Stopping\n⛔ FAIL χ²=68269"),
        (10.4, 0.3, 1.8, 0.6, "#8e44ad", "MV5: Pile-up\nR_max=3.04 MHz ✅"),
    ]
    for x, y, w, h, color, label in mc_boxes:
        rect = FancyBboxPatch((x, y), w, h, boxstyle="round,pad=0.05",
                              facecolor=color, edgecolor="black", lw=1, alpha=0.7)
        ax.add_patch(rect)
        ax.text(x + w/2, y + h/2, label, ha="center", va="center", fontsize=6, color="white")

    plt.tight_layout()
    path = os.path.join(OUTPUT_DIR, "02_analysis_pipeline.png")
    fig.savefig(path)
    plt.close(fig)
    print(f"  ✓ {path}")
    return path


def fig_timing_resolution():
    """Figure 3: Per-stave timing resolution comparison."""
    fig, ax = plt.subplots(1, 1, figsize=(9, 5))
    staves = list(STAVE_TIMING.keys())
    values = list(STAVE_TIMING.values())
    colors = ["#e74c3c", "#e67e22", "#2ecc71", "#3498db", "#9b59b6"]

    bars = ax.bar(staves, values, color=colors, edgecolor="black", linewidth=1.2, alpha=0.85)

    # Annotate bars
    for bar, val in zip(bars, values):
        ax.text(bar.get_x() + bar.get_width()/2, bar.get_height() + 0.05,
                f"{val:.2f} ns", ha="center", va="bottom", fontweight="bold", fontsize=11)

    ax.set_ylabel("σ₆₈ (ns)", fontweight="bold")
    ax.set_title("Per-Stave Timing Resolution", fontweight="bold", pad=15)
    ax.set_ylim(0, max(values) * 1.25)

    # Add annotation for B2
    ax.annotate("Topology-dominated\n(excluded from\nprecision timing)",
                xy=(0, STAVE_TIMING["B2"]), xytext=(0.5, STAVE_TIMING["B2"] * 1.3),
                fontsize=8, ha="center", color="#e74c3c",
                arrowprops=dict(arrowstyle="->", color="#e74c3c", lw=1))

    # Add annotation for combined
    ax.annotate("Multi-stave\ncombination",
                xy=(4, STAVE_TIMING["B4+B6+B8"]), xytext=(4.8, STAVE_TIMING["B4+B6+B8"] * 1.5),
                fontsize=8, ha="center", color="#9b59b6",
                arrowprops=dict(arrowstyle="->", color="#9b59b6", lw=1))

    ax.grid(axis="y", alpha=0.3)
    plt.tight_layout()
    path = os.path.join(OUTPUT_DIR, "03_timing_resolution.png")
    fig.savefig(path)
    plt.close(fig)
    print(f"  ✓ {path}")
    return path


def fig_mc_vs_data():
    """Figure 4: MC vs Data comparison for timing and pile-up."""
    fig, axes = plt.subplots(2, 2, figsize=(12, 9))

    comparisons = [
        ("timing_raw", 0, 0),
        ("timing_corrected", 0, 1),
        ("pileup_rmax", 1, 0),
        ("pileup_taueff", 1, 1),
    ]

    verdict_colors = {
        "timing_raw": "#2ecc71",        # PASS
        "timing_corrected": "#e67e22",   # TENSION
        "pileup_rmax": "#2ecc71",        # PASS
        "pileup_taueff": "#2ecc71",      # PASS
    }

    verdicts = {
        "timing_raw": "✅ PASS (pull = −1.05σ)",
        "timing_corrected": "🔶 TENSION (pull = +2.68σ)",
        "pileup_rmax": "✅ PASS (0.2% agreement)",
        "pileup_taueff": "✅ PASS (<0.01% agreement)",
    }

    for key, row, col in comparisons:
        ax = axes[row, col]
        d = MC_VS_DATA[key]
        color = verdict_colors[key]

        ax.bar(["MC (GEANT4)", "Data"], [d["mc"], d["data"]],
               yerr=[d["mc_err"], 0],
               color=[color, "#3498db"], edgecolor="black", linewidth=1.2,
               alpha=0.8, capsize=8)

        ax.set_title(d["label"], fontweight="bold")
        ax.set_ylabel("Value")
        ax.text(0.5, 0.95, verdicts[key], transform=ax.transAxes,
                ha="center", fontsize=9, fontweight="bold",
                bbox=dict(boxstyle="round,pad=0.3", facecolor="white", alpha=0.8))

    plt.suptitle("MC Validation: Key Comparisons", fontweight="bold", fontsize=14, y=1.01)
    plt.tight_layout()
    path = os.path.join(OUTPUT_DIR, "04_mc_vs_data.png")
    fig.savefig(path)
    plt.close(fig)
    print(f"  ✓ {path}")
    return path


def fig_pca_vs_ae():
    """Figure 5: PCA vs AE pulse shape compression."""
    fig, ax = plt.subplots(1, 1, figsize=(8, 5))

    dims = PCA_AE_DATA["latent_dim"]
    pca = PCA_AE_DATA["pca_mse"]
    ae = PCA_AE_DATA["ae_mse"]

    x = np.arange(len(dims))
    width = 0.35

    bars1 = ax.bar(x - width/2, pca, width, label="PCA", color="#3498db",
                   edgecolor="black", linewidth=1, alpha=0.85)
    bars2 = ax.bar(x + width/2, ae, width, label="Autoencoder", color="#e74c3c",
                   edgecolor="black", linewidth=1, alpha=0.85)

    # Annotate winner
    winners = ["AE +50.6%", "AE +40.6%", "AE +40.1%", "PCA +75.9%"]
    for i, (b1, b2, w) in enumerate(zip(bars1, bars2, winners)):
        winner_bar = b1 if "PCA" in w else b2
        ax.text(winner_bar.get_x() + winner_bar.get_width()/2, max(b1.get_height(), b2.get_height()) + 0.002,
                w, ha="center", fontsize=8, fontweight="bold", color="#2c3e50")

    ax.set_xticks(x)
    ax.set_xticklabels([f"d={d}" for d in dims])
    ax.set_ylabel("MSE", fontweight="bold")
    ax.set_xlabel("Latent Dimension", fontweight="bold")
    ax.set_title("Pulse Shape Compression: PCA vs Autoencoder", fontweight="bold", pad=15)
    ax.legend(loc="upper right")
    ax.grid(axis="y", alpha=0.3)

    plt.tight_layout()
    path = os.path.join(OUTPUT_DIR, "05_pca_vs_ae.png")
    fig.savefig(path)
    plt.close(fig)
    print(f"  ✓ {path}")
    return path


def fig_stopping_depth():
    """Figure 6: MC vs Data stopping-depth profile (MV3 failure)."""
    fig, axes = plt.subplots(1, 2, figsize=(12, 5))

    staves = STOPPING_DEPTH["staves"]
    mc = STOPPING_DEPTH["mc"]
    data = STOPPING_DEPTH["data"]

    # Side-by-side bar chart
    x = np.arange(len(staves))
    width = 0.35

    ax = axes[0]
    ax.bar(x - width/2, mc, width, label="MC (GEANT4)", color="#8e44ad",
           edgecolor="black", linewidth=1, alpha=0.8)
    ax.bar(x + width/2, data, width, label="Data", color="#2ecc71",
           edgecolor="black", linewidth=1, alpha=0.8)
    ax.set_xticks(x)
    ax.set_xticklabels(staves)
    ax.set_ylabel("Fraction of selected pulses (%)", fontweight="bold")
    ax.set_title("Stopping-Depth Profile", fontweight="bold")
    ax.legend()
    ax.grid(axis="y", alpha=0.3)

    # Ratio plot
    ax2 = axes[1]
    ratios = [d/m if m > 0 else 0 for d, m in zip(data, mc)]
    colors = ["#2ecc71" if 0.5 < r < 2 else "#e74c3c" for r in ratios]
    ax2.bar(staves, ratios, color=colors, edgecolor="black", linewidth=1, alpha=0.8)
    ax2.axhline(y=1.0, color="black", linestyle="--", alpha=0.5, label="Agreement")
    ax2.set_ylabel("Data / MC Ratio", fontweight="bold")
    ax2.set_title("Data/MC Ratio (1.0 = perfect agreement)", fontweight="bold")
    ax2.set_ylim(0, max(ratios) * 1.3)

    # Annotate B8
    ax2.annotate(f"B8: {ratios[3]:.2f}×\n(MC 10× too many\nat B8)",
                xy=(3, ratios[3]), xytext=(3.3, ratios[3] + 0.3),
                fontsize=9, ha="center", color="#e74c3c", fontweight="bold",
                arrowprops=dict(arrowstyle="->", color="#e74c3c", lw=1.5))

    plt.suptitle("MV3: Stopping-Depth Profile — ⛔ STRUCTURAL FAIL (χ²/ndf = 68,269)",
                 fontweight="bold", fontsize=13, y=1.02, color="#e74c3c")
    plt.tight_layout()
    path = os.path.join(OUTPUT_DIR, "06_stopping_depth.png")
    fig.savefig(path)
    plt.close(fig)
    print(f"  ✓ {path}")
    return path


def fig_pid_roc():
    """Figure 7: PID classifier performance."""
    fig, ax = plt.subplots(1, 1, figsize=(8, 5))

    methods = PID_AUC["methods"]
    aucs = PID_AUC["auc"]
    purities = PID_AUC["purity"]

    x = np.arange(len(methods))
    width = 0.35

    bars1 = ax.bar(x - width/2, aucs, width, label="AUC", color="#3498db",
                   edgecolor="black", linewidth=1, alpha=0.85)
    bars2 = ax.bar(x + width/2, purities, width, label="Purity @ 90% eff",
                   color="#2ecc71", edgecolor="black", linewidth=1, alpha=0.85)

    for bar, val in zip(bars1, aucs):
        ax.text(bar.get_x() + bar.get_width()/2, bar.get_height() + 0.01,
                f"{val:.4f}", ha="center", fontsize=9, fontweight="bold")
    for bar, val in zip(bars2, purities):
        ax.text(bar.get_x() + bar.get_width()/2, bar.get_height() + 0.01,
                f"{val:.4f}", ha="center", fontsize=9, fontweight="bold")

    ax.set_xticks(x)
    ax.set_xticklabels(methods, fontsize=9)
    ax.set_ylabel("Score", fontweight="bold")
    ax.set_title("Proton/Deuteron PID: MC Truth Validation (MV1)", fontweight="bold", pad=15)
    ax.legend(loc="lower right")
    ax.set_ylim(0.80, 1.02)
    ax.grid(axis="y", alpha=0.3)

    # MC ceiling annotation
    ax.axhline(y=0.9860, color="#e74c3c", linestyle="--", alpha=0.6, linewidth=1.5)
    ax.text(2.5, 0.988, "MC truth ceiling\n(AUC = 0.9860)", fontsize=8, color="#e74c3c", ha="center")

    plt.tight_layout()
    path = os.path.join(OUTPUT_DIR, "07_pid_auc.png")
    fig.savefig(path)
    plt.close(fig)
    print(f"  ✓ {path}")
    return path


def fig_c12_anomaly():
    """Figure 8: C12 anomaly waveform comparison."""
    t, normal, c12 = mock_c12_waveform()

    fig, axes = plt.subplots(1, 2, figsize=(12, 4.5))

    # Normal pulse
    ax = axes[0]
    ax.plot(t, normal, "o-", color="#3498db", markersize=6, linewidth=2, label="Normal proton pulse")
    ax.fill_between(t, 0, normal, alpha=0.2, color="#3498db")
    ax.axvline(x=55, color="#3498db", linestyle="--", alpha=0.4)
    ax.text(57, max(normal)*0.9, "Peak at\nsample ~5", fontsize=8, color="#3498db")
    ax.set_xlabel("Time (ns)", fontweight="bold")
    ax.set_ylabel("ADC (normalized)", fontweight="bold")
    ax.set_title("Normal Proton Pulse", fontweight="bold")
    ax.set_xlim(0, 170)
    ax.grid(alpha=0.3)

    # C12 recoil
    ax2 = axes[1]
    ax2.plot(t, c12, "s-", color="#e74c3c", markersize=6, linewidth=2, label="C12 recoil pulse")
    ax2.fill_between(t, 0, c12, alpha=0.2, color="#e74c3c")
    ax2.axvline(x=15, color="#e74c3c", linestyle="--", alpha=0.4)
    ax2.text(17, max(c12)*0.9, "Peak at\nsample ~1-2", fontsize=8, color="#e74c3c")
    ax2.set_xlabel("Time (ns)", fontweight="bold")
    ax2.set_ylabel("ADC (normalized)", fontweight="bold")
    ax2.set_title("C12 Nuclear Recoil (Anomaly Class)", fontweight="bold")
    ax2.set_xlim(0, 170)
    ax2.grid(alpha=0.3)

    plt.suptitle("MV6: Waveform Comparison — Normal vs C12 Recoil",
                 fontweight="bold", fontsize=13)
    plt.tight_layout()
    path = os.path.join(OUTPUT_DIR, "08_c12_anomaly.png")
    fig.savefig(path)
    plt.close(fig)
    print(f"  ✓ {path}")
    return path


def fig_systematic_budget():
    """Figure 9: Systematic uncertainty budget."""
    fig, ax = plt.subplots(1, 1, figsize=(10, 5))

    sources = SYST_BUDGET["sources"]
    magnitudes = SYST_BUDGET["magnitudes"]
    colors = SYST_BUDGET["colors"]

    bars = ax.barh(sources, magnitudes, color=colors, edgecolor="black", linewidth=1.2, alpha=0.85)

    for bar, mag in zip(bars, magnitudes):
        if mag > 0:
            ax.text(bar.get_width() + 0.5, bar.get_y() + bar.get_height()/2,
                    f"{mag:.1f}%", va="center", fontweight="bold", fontsize=10)
        else:
            ax.text(bar.get_width() + 0.5, bar.get_y() + bar.get_height()/2,
                    "Negligible", va="center", fontsize=9)

    ax.set_xlabel("Systematic Uncertainty (%)", fontweight="bold")
    ax.set_title("Systematic Uncertainty Budget (Deuteron Fraction)", fontweight="bold", pad=15)

    # Quadrature sum annotation
    quad_sum = np.sqrt(sum(m*m for m in magnitudes))
    ax.text(0.95, 0.05, f"Quadrature total: ~{quad_sum:.0f}%\nDominant: MV0 gain ±30%",
            transform=ax.transAxes, ha="right", fontsize=10, fontweight="bold",
            bbox=dict(boxstyle="round,pad=0.5", facecolor="#f8f9fa", edgecolor="gray"))

    ax.set_xlim(0, max(magnitudes) * 1.5)
    ax.grid(axis="x", alpha=0.3)
    plt.tight_layout()
    path = os.path.join(OUTPUT_DIR, "09_systematic_budget.png")
    fig.savefig(path)
    plt.close(fig)
    print(f"  ✓ {path}")
    return path


def fig_ml_landscape():
    """Figure 10: ML win/loss/tie summary."""
    fig, ax = plt.subplots(1, 1, figsize=(10, 5))

    domains = [
        "Saturation\nRecovery",
        "Duplicate\nReadout",
        "Two-Pulse\nTime RMS",
        "Timewalk\nCorrection",
        "Pile-up\nPoisson Rate",
        "Deep Net\nTiming",
        "PID\n(Data-only)",
        "Representation\nSuperiority",
    ]
    verdicts = [
        ("ML Wins", "#2ecc71", "3-7× better"),
        ("ML Wins", "#2ecc71", "res68 0.003 vs 0.12"),
        ("ML Wins RMS\n⚠️ Higher failure", "#f39c12", "0.295 vs 0.168"),
        ("Tie/Loss", "#3498db", "Analytic optimal"),
        ("Tie/Loss", "#3498db", "Analytic optimal"),
        ("ML Loses", "#e74c3c", "CNN < analytic"),
        ("Leakage", "#e74c3c", "Self-referential"),
        ("CORRECTED", "#e74c3c", "Failed LORO"),
    ]

    y_pos = range(len(domains))
    colors = [v[1] for v in verdicts]
    labels = [f"{v[0]}\n{v[2]}" for v in verdicts]

    ax.barh(y_pos, [1]*len(domains), color=colors, edgecolor="black", linewidth=1, alpha=0.7, height=0.7)
    for i, (domain, label) in enumerate(zip(domains, labels)):
        ax.text(0.5, i, f"{domain}: {label}", ha="center", va="center", fontsize=9, fontweight="bold")

    ax.set_yticks([])
    ax.set_xlim(0, 1)
    ax.axis("off")
    ax.set_title("ML Performance Landscape: Where ML Wins, Ties, or Loses", fontweight="bold", pad=15)

    # Legend
    legend_elements = [
        mpatches.Patch(color="#2ecc71", label="✅ ML Wins (truth independent, shape signal)"),
        mpatches.Patch(color="#f39c12", label="⚠️ ML Wins partially (higher failure rate)"),
        mpatches.Patch(color="#3498db", label="Tie/Loss (analytic model already optimal)"),
        mpatches.Patch(color="#e74c3c", label="❌ ML Loses / CORRECTED (leakage artifact)"),
    ]
    ax.legend(handles=legend_elements, loc="lower center", ncol=2, fontsize=8,
              bbox_to_anchor=(0.5, -0.25))

    plt.tight_layout()
    path = os.path.join(OUTPUT_DIR, "10_ml_landscape.png")
    fig.savefig(path)
    plt.close(fig)
    print(f"  ✓ {path}")
    return path


# ── Main ────────────────────────────────────────────────────────────────────

def main():
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    setup_style()
    print(f"Generating figures in {OUTPUT_DIR}/ ...")

    fig_experimental_setup()
    fig_analysis_pipeline()
    fig_timing_resolution()
    fig_mc_vs_data()
    fig_pca_vs_ae()
    fig_stopping_depth()
    fig_pid_roc()
    fig_c12_anomaly()
    fig_systematic_budget()
    fig_ml_landscape()

    print(f"\n✓ All figures generated successfully in {OUTPUT_DIR}/")
    return 0


if __name__ == "__main__":
    sys.exit(main())
