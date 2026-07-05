#!/usr/bin/env python3
"""
Generate 30+ publication-quality figures for the CCB Test-Beam wiki.

Every chapter gets multiple figures: schematics, data plots, MC comparisons,
and annotated illustrations. Focus on visual clarity and self-contained captions.

Figures:
  01_experimental_setup.png       - Detector layout schematic
  02_analysis_pipeline.png        - Full analysis pipeline flowchart
  03_waveform_annotated.png       - Annotated waveform showing all extracted quantities
  04_detector_cross_section.png   - Cross-section of HRD stave stack
  05_timing_chain.png             - Step-by-step timing extraction chain
  06_timing_resolution_per_stave.png - Per-stave timing bar chart
  07_timewalk_explanation.png     - What timewalk is and how we fix it
  08_timewalk_data_vs_mc.png      - Data vs MC timewalk comparison
  09_b2_covariance.png            - B2 vs downstream covariance visual
  10_astack_cross_check.png       - A-stack vs B-stack comparison
  11_pileup_cartoon.png           - Cartoon of pile-up: normal vs overlapping pulses
  12_livetime_measurement.png     - How we measure tau_eff
  13_rmax_correction.png          - R_max correction: 4.22 → 3.05 MHz
  14_twopulse_recovery.png        - Two-pulse decomposition comparison
  15_current_excess.png           - Current-dependent vs current-independent pile-up
  16_pca_vs_ae.png                - PCA vs AE compression (improved)
  17_ml_landscape.png             - Where ML wins/ties/loses
  18_saturation_recovery.png      - Saturation recovery: ML vs template
  19_duplicate_readout.png        - Duplicate-readout closure
  20_c12_discovery.png            - How C12 anomaly was discovered and identified
  21_c12_waveform_comparison.png  - Normal vs C12 waveform overlay
  22_stopping_depth_failure.png   - MV3 stopping-depth catastrophic failure
  23_pid_auc_roc.png              - PID ROC curves with MC ceiling
  24_gain_calibration.png         - MV0 digitizer gain calibration
  25_pedestal_comparison.png      - Adaptive vs learned pedestal
  26_systematic_budget.png        - Systematic uncertainty budget (horizontal bar)
  27_methodology_leakage.png      - Three leakage controls diagram
  28_physics_motivation.png       - Why this experiment matters
  29_wiki_reading_guide.png       - Visual table of contents
  30_study_coverage_map.png       - Which studies cover which physics questions
"""
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from matplotlib.patches import FancyBboxPatch, FancyArrowPatch, Arc, Rectangle, Polygon, FancyArrow
import numpy as np
import os, sys

OUTPUT_DIR = "docs/figures"
DPI = 150

os.makedirs(OUTPUT_DIR, exist_ok=True)

# ── Style ───────────────────────────────────────────────────────────────────
plt.style.use("seaborn-v0_8-darkgrid")
matplotlib.rcParams.update({
    "figure.facecolor": "white", "axes.facecolor": "#fafafa",
    "font.size": 10, "axes.titlesize": 12, "axes.labelsize": 10,
    "legend.fontsize": 8, "figure.dpi": DPI,
    "savefig.dpi": DPI, "savefig.bbox": "tight", "savefig.pad_inches": 0.1,
})

# ── Color Palette ───────────────────────────────────────────────────────────
C_DATA   = "#3498db"  # blue - real data
C_MC     = "#e74c3c"  # red - MC simulation
C_PASS   = "#2ecc71"  # green - validated
C_FAIL   = "#e74c3c"  # red - failed/tension
C_TENSION = "#f39c12" # orange - tension
C_B2     = "#e74c3c"  # red
C_B4     = "#e67e22"  # orange
C_B6     = "#2ecc71"  # green
C_B8     = "#3498db"  # blue
C_COMB   = "#9b59b6"  # purple
C_ML     = "#e74c3c"  # red
C_TRAD   = "#3498db"  # blue
C_ASTACK = "#1abc9c"  # teal

def save(fig, name):
    path = os.path.join(OUTPUT_DIR, name)
    fig.savefig(path)
    plt.close(fig)
    print(f"  ✓ {name}")

# ═══════════════════════════════════════════════════════════════════════════════
# FIGURE 01: Experimental Setup Schematic
# ═══════════════════════════════════════════════════════════════════════════════
def fig_01_experimental_setup():
    fig, ax = plt.subplots(figsize=(14, 6))
    ax.set_xlim(0, 16); ax.set_ylim(0, 7); ax.axis("off")
    ax.set_title("CCB Test-Beam: How the Experiment Works", fontweight="bold", fontsize=14, pad=15)

    # Beam
    ax.annotate("190 MeV\nprotons", xy=(1, 3.5), fontsize=9, ha="center", fontweight="bold", color="#e74c3c")
    ax.annotate("", xy=(8, 3.5), xytext=(1.5, 3.5), arrowprops=dict(arrowstyle="->", color="#e74c3c", lw=3))

    # Target
    target = Rectangle((2.5, 2.5), 1, 2, facecolor="#f39c12", edgecolor="black", lw=2, alpha=0.8)
    ax.add_patch(target)
    ax.text(3, 3.5, "CD₂\nTarget", ha="center", va="center", fontsize=9, fontweight="bold")

    # Scattered particles
    ax.annotate("", xy=(6, 5.5), xytext=(3.5, 4), arrowprops=dict(arrowstyle="->", color="gray", lw=1.5))
    ax.annotate("", xy=(6, 1.5), xytext=(3.5, 3), arrowprops=dict(arrowstyle="->", color="gray", lw=1.5))
    ax.text(5, 5.8, "scattered\nparticles", fontsize=8, ha="center", color="gray")

    # Trigger + TPC
    trig = Rectangle((6.5, 2.7), 0.8, 1.6, facecolor="#3498db", edgecolor="black", lw=1.5, alpha=0.6)
    ax.add_patch(trig); ax.text(6.9, 3.5, "Trigger\nScints", ha="center", va="center", fontsize=7)
    tpc = Rectangle((7.8, 2.3), 1.4, 2.4, facecolor="#9b59b6", edgecolor="black", lw=1.5, alpha=0.5)
    ax.add_patch(tpc); ax.text(8.5, 3.5, "TPC\n(tracking)", ha="center", va="center", fontsize=7)

    # A-Stack
    a = Rectangle((10, 2), 1.8, 3, facecolor="#1abc9c", edgecolor="black", lw=2, alpha=0.6)
    ax.add_patch(a)
    ax.text(10.9, 4.8, "A-Stack", ha="center", fontsize=9, fontweight="bold")
    ax.text(10.9, 3.5, "A1 A3 A5 A7\n(cross-check)", ha="center", fontsize=7)
    ax.text(10.9, 2.3, "~100 cm", ha="center", fontsize=7, color="gray")

    # B-Stack (highlighted)
    b = Rectangle((12.5, 2), 1.8, 3, facecolor="#2ecc71", edgecolor="black", lw=3, alpha=0.75)
    ax.add_patch(b)
    ax.text(13.4, 4.8, "★ B-Stack", ha="center", fontsize=9, fontweight="bold", color="#1a7a3a")
    ax.text(13.4, 3.8, "B2 B4 B6 B8", ha="center", fontsize=7)
    ax.text(13.4, 3.3, "Primary", ha="center", fontsize=7, fontweight="bold")
    ax.text(13.4, 2.8, "analysis", ha="center", fontsize=7)
    ax.text(13.4, 2.3, "~100 cm", ha="center", fontsize=7, color="gray")

    # Annotations
    ax.text(0.5, 6.5, "The CCB Test-Beam Experiment", fontsize=12, fontweight="bold")
    ax.text(0.5, 6.1, "190 MeV protons → CD₂ target → scattered particles measured by HRD scintillator stacks", fontsize=9)
    ax.text(0.5, 5.7, "Goal: measure timing resolution & pile-up of scintillator staves", fontsize=9, color="gray")

    # Waveform callout
    rect = FancyBboxPatch((13, 0.3), 2.5, 1.2, boxstyle="round,pad=0.1", facecolor="white", edgecolor="#2ecc71", lw=2)
    ax.add_patch(rect)
    ax.text(14.25, 1.2, "Each stave records:", ha="center", fontsize=7, fontweight="bold")
    ax.text(14.25, 0.9, "18 samples × 10 ns", ha="center", fontsize=7)
    ax.text(14.25, 0.65, "= 180 ns waveform", ha="center", fontsize=7)
    ax.annotate("", xy=(13, 0.9), xytext=(14.3, 2), arrowprops=dict(arrowstyle="->", color="#2ecc71", lw=1))

    plt.tight_layout()
    save(fig, "01_experimental_setup.png")


# ═══════════════════════════════════════════════════════════════════════════════
# FIGURE 02: Physics Motivation
# ═══════════════════════════════════════════════════════════════════════════════
def fig_02_physics_motivation():
    fig, axes = plt.subplots(1, 3, figsize=(14, 4.5))
    fig.suptitle("Why This Experiment Matters", fontweight="bold", fontsize=13)

    # Panel 1: The NNBAR context
    ax = axes[0]
    ax.set_xlim(0, 6); ax.set_ylim(0, 6); ax.axis("off")
    ax.set_title("1. The Big Picture:\nNNBAR Experiment", fontweight="bold", fontsize=10)

    rect = FancyBboxPatch((0.5, 1), 5, 4, boxstyle="round,pad=0.3", facecolor="#f0f4ff", edgecolor="#3498db", lw=2)
    ax.add_patch(rect)
    ax.text(3, 4.5, "Search for neutron→antineutron\noscillations", ha="center", fontsize=9, fontweight="bold")
    ax.text(3, 3.2, "Needs detectors that can\ntell protons from deuterons\nAND measure timing precisely", ha="center", fontsize=8)
    ax.text(3, 1.5, "→ We need to characterize\nthe HRD scintillator stacks", ha="center", fontsize=8, color="#e74c3c", fontweight="bold")

    # Panel 2: The Questions
    ax = axes[1]
    ax.set_xlim(0, 6); ax.set_ylim(0, 6); ax.axis("off")
    ax.set_title("2. The Two Questions", fontweight="bold", fontsize=10)

    rect = FancyBboxPatch((0.5, 1), 5, 4, boxstyle="round,pad=0.3", facecolor="#fff8f0", edgecolor="#e67e22", lw=2)
    ax.add_patch(rect)
    ax.text(3, 4.5, "Q1: Timing Resolution", ha="center", fontsize=9, fontweight="bold")
    ax.text(3, 3.8, "How precisely can each stave\ntimestamp a passing particle?", ha="center", fontsize=8)
    ax.text(3, 2.8, "Q2: Pile-up Tolerance", ha="center", fontsize=9, fontweight="bold")
    ax.text(3, 2.1, "How many particles per second\nbefore overlapping pulses\nruin the measurement?", ha="center", fontsize=8)

    # Panel 3: The Answers
    ax = axes[2]
    ax.set_xlim(0, 6); ax.set_ylim(0, 6); ax.axis("off")
    ax.set_title("3. What We Found", fontweight="bold", fontsize=10)

    rect = FancyBboxPatch((0.5, 1), 5, 4, boxstyle="round,pad=0.3", facecolor="#f0fff0", edgecolor="#2ecc71", lw=2)
    ax.add_patch(rect)
    ax.text(3, 4.5, "Timing: σ ≈ 0.68 ns (B6)", ha="center", fontsize=9, fontweight="bold", color="#2ecc71")
    ax.text(3, 3.8, "3-stave: σ ≈ 0.55 ns", ha="center", fontsize=8)
    ax.text(3, 2.8, "Pile-up: R_max ≈ 3 MHz", ha="center", fontsize=9, fontweight="bold", color="#2ecc71")
    ax.text(3, 2.1, "PID: AUC = 0.986", ha="center", fontsize=8)
    ax.text(3, 1.4, "Anomaly: C12 recoils (0.32%)", ha="center", fontsize=7, color="gray")

    plt.tight_layout()
    save(fig, "02_physics_motivation.png")


# ═══════════════════════════════════════════════════════════════════════════════
# FIGURE 03: Annotated Waveform
# ═══════════════════════════════════════════════════════════════════════════════
def fig_03_waveform_annotated():
    t = np.arange(18) * 10
    y = np.zeros(18)
    y[2:14] = np.exp(-0.5 * ((t[2:14] - 55) / 18)**2) * 8000
    y += np.random.randn(18) * 50
    baseline = np.mean(y[:4])

    fig, axes = plt.subplots(1, 2, figsize=(14, 5))
    fig.suptitle("What We Measure from Each Waveform", fontweight="bold", fontsize=13)

    # Left: full waveform
    ax = axes[0]
    ax.plot(t, y, "o-", color=C_DATA, markersize=5, lw=2)
    ax.fill_between(t[:4], 0, y[:4], alpha=0.15, color="gray")
    ax.text(np.mean(t[:4]), max(y)*0.15, "Baseline\n(samples 0-3)", ha="center", fontsize=8, color="gray")

    ax.axvline(x=t[np.argmax(y)], color=C_PASS, linestyle="--", alpha=0.6)
    ax.annotate(f"Amplitude A\n({y.max()-baseline:.0f} ADC)", xy=(t[np.argmax(y)], y.max()),
                xytext=(t[np.argmax(y)]+25, y.max()*0.7), fontsize=9, color=C_PASS,
                arrowprops=dict(arrowstyle="->", color=C_PASS, lw=2), fontweight="bold")

    ax.axhline(y=0.2*y.max(), xmin=0.3, xmax=0.7, color=C_B2, linestyle="--", alpha=0.5)
    ax.text(t[9], 0.2*y.max()+200, "CFD20 time", fontsize=8, color=C_B2)

    ax.set_xlabel("Time (ns)", fontweight="bold")
    ax.set_ylabel("ADC", fontweight="bold")
    ax.set_title("Raw Waveform + Extracted Quantities", fontweight="bold")
    ax.grid(alpha=0.2)

    # Right: zoom on key features
    ax2 = axes[1]
    ax2.set_xlim(0, 16); ax2.set_ylim(0, 7); ax2.axis("off")
    ax2.set_title("Extracted Per-Pulse Quantities", fontweight="bold")

    items = [
        (0.5, 6.3, "Amplitude A", "Peak ADC - baseline\nUsed for: threshold, energy proxy", C_PASS),
        (0.5, 5.0, "CFD Time t", "Constant-fraction (20%) crossing\nUsed for: timing seed", C_B2),
        (0.5, 3.7, "Template Phase φ", "Best-fit shift to amplitude-adaptive template\nUsed for: refined timing, shape quality", C_B4),
        (0.5, 2.4, "Pulse Shape q", "Template agreement metric\nUsed for: quality cuts, anomaly detection", C_B6),
        (0.5, 1.1, "Tail/Late Fraction", "ADC after peak / before peak\nUsed for: pile-up detection, pathology flags", C_B8),
    ]
    for x, ypos, title, desc, color in items:
        dot = Rectangle((x, ypos-0.15), 0.15, 0.3, facecolor=color, edgecolor="black", lw=1)
        ax2.add_patch(dot)
        ax2.text(x+0.4, ypos, title, fontsize=9, fontweight="bold", color=color, va="center")
        ax2.text(x+0.4, ypos-0.35, desc, fontsize=7, color="gray", va="center")

    plt.tight_layout()
    save(fig, "03_waveform_annotated.png")


# ═══════════════════════════════════════════════════════════════════════════════
# FIGURE 04: Detector Cross-Section
# ═══════════════════════════════════════════════════════════════════════════════
def fig_04_detector_cross_section():
    fig, ax = plt.subplots(figsize=(10, 7))
    ax.set_xlim(0, 12); ax.set_ylim(0, 10); ax.axis("off")
    ax.set_title("HRD B-Stack: How Particles Are Detected", fontweight="bold", fontsize=13)

    # B-Stack staves
    staves = [
        (2, "B2", "Stops\ndeuterons", C_B2, 3),
        (5, "B4", "Stops some\nprotons", C_B4, 7),
        (8, "B6", "Clean timing\nreference", C_B6, 9),
        (11, "B8", "Penetrating\nonly", C_B8, 5),
    ]

    for x, label, desc, color, height in staves:
        rect = Rectangle((x-0.8, 1), 1.6, height*0.5, facecolor=color, edgecolor="black", lw=2, alpha=0.7)
        ax.add_patch(rect)
        ax.text(x, 1+height*0.25+0.3, label, ha="center", fontsize=11, fontweight="bold", color=color)
        ax.text(x, 1+height*0.25-0.6, desc, ha="center", fontsize=7, color="gray")

    # Beam direction
    ax.annotate("beam\ndirection →", xy=(12, 5.5), xytext=(0.5, 5.5),
                fontsize=9, ha="center", va="center", fontweight="bold",
                arrowprops=dict(arrowstyle="->", color="#e74c3c", lw=3))

    # Particle tracks
    # Deuteron: stops at B2
    ax.annotate("", xy=(2, 6.5), xytext=(0, 6.5), arrowprops=dict(arrowstyle="->", color=C_B2, lw=2, ls="--"))
    ax.annotate("deuteron\n(stops at B2)", xy=(3, 6.5), fontsize=8, color=C_B2)

    # Proton: goes through to B6
    ax.annotate("", xy=(8, 7), xytext=(0, 7), arrowprops=dict(arrowstyle="->", color=C_B6, lw=2, ls="--"))
    ax.annotate("proton\n(reaches B6)", xy=(9, 7), fontsize=8, color=C_B6)

    # Fast proton: goes through all
    ax.annotate("", xy=(11, 8), xytext=(0, 8), arrowprops=dict(arrowstyle="->", color=C_B8, lw=2, ls="--"))
    ax.annotate("fast proton\n(reaches B8)", xy=(12, 8), fontsize=8, color=C_B8)

    # WLS fibre annotation
    ax.text(6, 9.3, "Each stave: scintillator slab + WLS fibre readout → SiPM", ha="center", fontsize=9, fontweight="bold")
    ax.text(6, 8.8, "18 samples @ 10 ns = 180 ns waveform captured per stave per event", ha="center", fontsize=8, color="gray")

    # Key insight
    rect = FancyBboxPatch((1, 0.1), 10, 0.7, boxstyle="round,pad=0.1", facecolor="#fff3cd", edgecolor="#f39c12", lw=1.5)
    ax.add_patch(rect)
    ax.text(6, 0.45, "Key: Heavier particles (deuterons) stop earlier → range acts as a particle ID", ha="center", fontsize=9, fontweight="bold")

    plt.tight_layout()
    save(fig, "04_detector_cross_section.png")


# ═══════════════════════════════════════════════════════════════════════════════
# FIGURE 05: Timing Chain
# ═══════════════════════════════════════════════════════════════════════════════
def fig_05_timing_chain():
    fig, ax = plt.subplots(figsize=(14, 5))
    ax.set_xlim(0, 16); ax.set_ylim(0, 5); ax.axis("off")
    ax.set_title("How We Extract Timing: The Full Chain", fontweight="bold", fontsize=13)

    steps = [
        (0.5, 3, "Raw\nWaveform", "180 ns\n18 samples", "#34495e"),
        (3.5, 3, "Pedestal\nSubtraction", "median(samples\n0-3)", "#7f8c8d"),
        (6.5, 3, "CFD20\nTiming", "20% constant\nfraction", "#3498db"),
        (9.5, 3, "Template\nPhase Fit", "best-fit shift\nto template", "#2ecc71"),
        (12.5, 3, "Timewalk\nCorrection", "t_corr = t - B/A\n(amplitude-dependent)", "#e74c3c"),
    ]

    for x, y, title, desc, color in steps:
        rect = FancyBboxPatch((x-1, y-0.8), 2, 2.2, boxstyle="round,pad=0.1",
                              facecolor=color, edgecolor="black", lw=1.5, alpha=0.85)
        ax.add_patch(rect)
        ax.text(x, y+0.6, title, ha="center", fontsize=8, fontweight="bold", color="white")
        ax.text(x, y, desc, ha="center", fontsize=7, color="white", alpha=0.9)

    # Arrows between steps
    for x1, x2 in [(2.5, 2.7), (5.5, 5.7), (8.5, 8.7), (11.5, 11.7)]:
        ax.annotate("→", xy=(x2, 3), xytext=(x1, 3), fontsize=20, ha="center", va="center")

    # Output values
    ax.text(12.5, 4.5, "Result:", ha="center", fontsize=8, fontweight="bold")
    ax.text(12.5, 4.2, "σ₆₈(B6) ≈ 0.72 ns", ha="center", fontsize=8, color="#2ecc71", fontweight="bold")
    ax.text(12.5, 3.9, "σ₆₈(B4+B6+B8) ≈ 0.55 ns", ha="center", fontsize=8, color="#2ecc71")

    # Key insight
    ax.text(8, 0.3, "The dominant correction is amplitude timewalk: bigger pulses appear to arrive earlier", ha="center", fontsize=9, fontweight="bold", color="#e74c3c")

    plt.tight_layout()
    save(fig, "05_timing_chain.png")


# ═══════════════════════════════════════════════════════════════════════════════
# FIGURE 06: Timewalk Explained
# ═══════════════════════════════════════════════════════════════════════════════
def fig_06_timewalk_explained():
    fig, axes = plt.subplots(1, 3, figsize=(14, 4.5))
    fig.suptitle("What Is Timewalk and How Do We Fix It?", fontweight="bold", fontsize=13)

    # Panel 1: Two pulses at same true time
    ax = axes[0]
    t = np.linspace(0, 60, 100)
    ax.plot(t, 8000*(1-np.exp(-(t-2)/2.5)) * (t>2), color=C_DATA, lw=2, label="Large pulse (8000 ADC)")
    ax.plot(t, 2000*(1-np.exp(-(t-2)/2.5)) * (t>2), color=C_MC, lw=2, label="Small pulse (2000 ADC)")
    ax.axvline(x=8, color="gray", ls=":", alpha=0.5, label="CFD threshold")
    ax.axhline(y=1600, color="gray", ls=":", alpha=0.5)
    ax.axvline(x=4.5, color=C_DATA, ls="--", alpha=0.7)
    ax.axvline(x=12, color=C_MC, ls="--", alpha=0.7)
    ax.annotate("Δt ≈ 7.5 ns", xy=(8, 7000), fontsize=9, fontweight="bold", color="#e74c3c",
                bbox=dict(boxstyle="round", facecolor="white", alpha=0.8))
    ax.set_xlabel("Time (ns)"); ax.set_ylabel("ADC")
    ax.set_title("The Problem", fontweight="bold")
    ax.legend(fontsize=7)
    ax.set_ylim(0, 9000)

    # Panel 2: Timewalk curve
    ax2 = axes[1]
    amps = np.logspace(2.8, 4, 50)
    twalk_phys = 125 / amps  # B_phys = tau_rise * V_th ≈ 125 ns*ADC
    twalk_toy = -23 / np.sqrt(amps)  # B < 0: unphysical

    ax2.plot(amps, twalk_phys, lw=2, color=C_PASS, label="Physical: B/A (B>0)")
    ax2.plot(amps, twalk_toy, lw=2, color=C_FAIL, ls="--", label="Toy MV4: B/√A (B<0)")
    ax2.axhline(y=0, color="gray", ls=":")
    ax2.set_xscale("log")
    ax2.set_xlabel("Amplitude (ADC)"); ax2.set_ylabel("Timewalk Δt (ns)")
    ax2.set_title("The Correction", fontweight="bold")
    ax2.legend(fontsize=7)

    # Panel 3: Before vs After
    ax3 = axes[2]
    ax3.set_xlim(0, 6); ax3.set_ylim(0, 6); ax3.axis("off")
    ax3.set_title("The Fix (MV4b)", fontweight="bold")

    rect1 = FancyBboxPatch((0.5, 3.5), 5, 2, boxstyle="round", facecolor="#ffe0e0", edgecolor=C_FAIL, lw=1.5)
    ax3.add_patch(rect1)
    ax3.text(3, 5, "MV4 (toy): σ₆₈_corr pull = +2.68σ", ha="center", fontsize=9, fontweight="bold")
    ax3.text(3, 4.5, "B = -23 ns·√ADC — unphysical!\nOver-corrects timing; MC disagrees", ha="center", fontsize=8)

    rect2 = FancyBboxPatch((0.5, 0.5), 5, 2, boxstyle="round", facecolor="#e0ffe0", edgecolor=C_PASS, lw=1.5)
    ax3.add_patch(rect2)
    ax3.text(3, 2, "MV4b (1/A): σ₆₈_corr pull → ~0σ", ha="center", fontsize=9, fontweight="bold")
    ax3.text(3, 1.5, "B_phys = 125 ns·ADC — physical!\nMC and data agree after fix", ha="center", fontsize=8)

    plt.tight_layout()
    save(fig, "06_timewalk_explained.png")


# ═══════════════════════════════════════════════════════════════════════════════
# FIGURE 07: B2 Covariance
# ═══════════════════════════════════════════════════════════════════════════════
def fig_07_b2_covariance():
    fig, axes = plt.subplots(1, 2, figsize=(13, 5))
    fig.suptitle("The B2 Problem: Why B2 Is Excluded from Precision Timing", fontweight="bold", fontsize=13)

    # Left: covariance comparison
    ax = axes[0]
    pairs = ["B2-B4", "B2-B6", "B2-B8", "B4-B6", "B4-B8", "B6-B8"]
    covs = [1042, 980, 1050, 16, 18, 14]
    colors = [C_B2 if "B2" in p else C_PASS for p in pairs]
    bars = ax.bar(pairs, covs, color=colors, edgecolor="black", linewidth=1)
    for bar, val in zip(bars, covs):
        ax.text(bar.get_x()+bar.get_width()/2, bar.get_height()+20, str(val), ha="center", fontweight="bold", fontsize=10)
    ax.set_ylabel("Covariance (ns²)", fontweight="bold")
    ax.set_title("Pairwise Timing Covariance", fontweight="bold")
    ax.grid(axis="y", alpha=0.2)

    # Right: explanation
    ax2 = axes[1]
    ax2.set_xlim(0, 6); ax2.set_ylim(0, 6); ax2.axis("off")
    ax2.set_title("What This Means", fontweight="bold")

    ax2.text(3, 5.5, "B2 covariance is ~65× larger", ha="center", fontsize=10, fontweight="bold", color=C_B2)
    ax2.text(3, 5.0, "than downstream pairs", ha="center", fontsize=10, color=C_B2)

    rect = FancyBboxPatch((0.5, 1.5), 5, 3, boxstyle="round", facecolor="#f0f8ff", edgecolor="#3498db", lw=1.5)
    ax2.add_patch(rect)
    ax2.text(3, 4.2, "Why?", ha="center", fontsize=9, fontweight="bold")
    ax2.text(3, 3.5, "B2 is the most upstream stave — it stops\ndeuterons. Terminal deuterons create a\nshared topology fluctuation that correlates\nB2 timing with all other staves.", ha="center", fontsize=8)

    ax2.text(3, 2.0, "Action: Exclude B2 from precision\nevent-time estimates.", ha="center", fontsize=9, fontweight="bold", color="#e74c3c")
    ax2.text(3, 1.5, "Use B4+B6+B8 for combined timing.", ha="center", fontsize=8)

    plt.tight_layout()
    save(fig, "07_b2_covariance.png")


# ═══════════════════════════════════════════════════════════════════════════════
# FIGURE 08: Pile-up Cartoon
# ═══════════════════════════════════════════════════════════════════════════════
def fig_08_pileup_cartoon():
    fig, axes = plt.subplots(1, 3, figsize=(14, 4))
    fig.suptitle("What Is Pile-up?", fontweight="bold", fontsize=13)

    t = np.arange(18) * 10

    # Normal pulse
    ax = axes[0]
    y1 = np.exp(-0.5*((t-55)/15)**2) * 1.0 + 0.01*np.random.randn(18)
    ax.plot(t, y1, "o-", color=C_PASS, markersize=5, lw=2)
    ax.fill_between(t, 0, y1, alpha=0.2, color=C_PASS)
    ax.set_xlabel("Time (ns)"); ax.set_ylabel("ADC")
    ax.set_title("✅ Normal: One Particle", fontweight="bold")
    ax.set_ylim(-0.05, 1.2)
    ax.grid(alpha=0.2)

    # Pile-up
    ax2 = axes[1]
    y2a = np.exp(-0.5*((t-40)/12)**2) * 0.8
    y2b = np.exp(-0.5*((t-80)/10)**2) * 0.6
    y2 = y2a + y2b + 0.01*np.random.randn(18)
    ax2.plot(t, y2, "o-", color=C_FAIL, markersize=5, lw=2)
    ax2.fill_between(t, 0, y2a, alpha=0.15, color=C_DATA)
    ax2.fill_between(t, y2a, y2, alpha=0.15, color=C_MC)
    ax2.set_xlabel("Time (ns)")
    ax2.set_title("⚠️ Pile-up: Two Overlapping Particles", fontweight="bold")
    ax2.set_ylim(-0.05, 1.3)
    ax2.grid(alpha=0.2)

    # Consequences
    ax3 = axes[2]
    ax3.set_xlim(0, 6); ax3.set_ylim(0, 6); ax3.axis("off")
    ax3.set_title("Consequences", fontweight="bold")

    consequences = [
        (3, 5.3, "Timing degraded", "2nd pulse shifts CFD crossing → wrong time"),
        (3, 4.2, "Amplitude wrong", "Overlap adds to peak → overestimated energy"),
        (3, 3.1, "Limits beam rate", "R_max ≈ 3 MHz before pile-up becomes unacceptable"),
        (3, 2.0, "~9% excess at 20 nA", "Genuine beam pile-up (after subtracting baseline)"),
        (3, 0.9, "91% of 'pile-up score'\nis NOT beam pile-up", "Scintillator tails, waveform pathologies"),
    ]
    for x, ypos, title, desc in consequences:
        ax3.text(x, ypos, f"• {title}: {desc}", fontsize=8)

    plt.tight_layout()
    save(fig, "08_pileup_cartoon.png")


# ═══════════════════════════════════════════════════════════════════════════════
# FIGURE 09: Live-time Measurement & R_max Correction
# ═══════════════════════════════════════════════════════════════════════════════
def fig_09_rmax_correction():
    fig, axes = plt.subplots(1, 2, figsize=(12, 4.5))
    fig.suptitle("The R_max Correction: 4.22 → 3.05 MHz", fontweight="bold", fontsize=13)

    ax = axes[0]
    categories = ["Analysis Note\n(τ=90 ns assumed)", "Measured\n(τ=124.8 ns)", "MC Validated\n(τ=124.8 ns)"]
    values = [4.22, 3.05, 3.044]
    colors = [C_FAIL, C_DATA, C_PASS]
    bars = ax.bar(categories, values, color=colors, edgecolor="black", linewidth=1.5)
    for bar, val in zip(bars, values):
        ax.text(bar.get_x()+bar.get_width()/2, bar.get_height()+0.05, f"{val:.2f} MHz", ha="center", fontweight="bold")
    ax.set_ylabel("R_max (MHz)", fontweight="bold")
    ax.set_title("Pile-up Rate Limit", fontweight="bold")
    ax.grid(axis="y", alpha=0.2)

    ax2 = axes[1]
    ax2.set_xlim(0, 6); ax2.set_ylim(0, 6); ax2.axis("off")
    ax2.set_title("How We Measured τ_eff", fontweight="bold")
    ax2.text(3, 5.5, "10% tail-crossing method:", fontsize=9, fontweight="bold")
    ax2.text(3, 5.0, "Measure time for pulse to decay to 10% of peak", fontsize=8)
    ax2.text(3, 4.5, "Bootstrap CI: [123.33, 126.36] ns", fontsize=8)
    ax2.text(3, 3.8, "MC confirmation (MV5):", fontsize=9, fontweight="bold", color=C_PASS)
    ax2.text(3, 3.3, "MC τ_eff = 124.8 ns → R_max = 3.044 MHz", fontsize=8, color=C_PASS)
    ax2.text(3, 2.8, "Agreement: 0.2% — ✅ validated", fontsize=8, color=C_PASS)
    ax2.text(3, 2.0, "⚠️ The note's 4.22 MHz is WRONG", fontsize=9, fontweight="bold", color=C_FAIL)
    ax2.text(3, 1.5, "Root cause: wrong τ_eff assumption (90 ns)", fontsize=8, color=C_FAIL)

    plt.tight_layout()
    save(fig, "09_rmax_correction.png")


# ═══════════════════════════════════════════════════════════════════════════════
# FIGURE 10: C12 Anomaly Discovery Story
# ═══════════════════════════════════════════════════════════════════════════════
def fig_10_c12_discovery_story():
    fig, axes = plt.subplots(1, 3, figsize=(14, 4.5))
    fig.suptitle("The C12 Anomaly: From Discovery to Identification", fontweight="bold", fontsize=13)

    # Step 1: Discovery
    ax = axes[0]
    ax.set_xlim(0, 6); ax.set_ylim(0, 6); ax.axis("off")
    ax.set_title("Step 1: Discovery (P02/P09)", fontweight="bold", color="#9b59b6")
    rect = FancyBboxPatch((0.3, 1), 5.4, 4.5, boxstyle="round", facecolor="#f8f0ff", edgecolor="#9b59b6", lw=2)
    ax.add_patch(rect)
    ax.text(3, 5.2, "Unsupervised learning on\n640k pulse waveforms", ha="center", fontsize=9, fontweight="bold")
    ax.text(3, 4.2, "Found: ~4% of pulses form an\nanomalous cluster with:", ha="center", fontsize=8)
    ax.text(3, 3.3, "• Very early peak (sample 1-2)\n• Near-zero area\n• Confined to B2 only", ha="center", fontsize=8)
    ax.text(3, 2.0, "Question: What is this?", ha="center", fontsize=9, fontweight="bold", color="#e74c3c")

    # Step 2: Investigation
    ax2 = axes[1]
    ax2.set_xlim(0, 6); ax2.set_ylim(0, 6); ax2.axis("off")
    ax2.set_title("Step 2: Investigation (MV6)", fontweight="bold", color="#3498db")
    rect2 = FancyBboxPatch((0.3, 1), 5.4, 4.5, boxstyle="round", facecolor="#f0f4ff", edgecolor="#3498db", lw=2)
    ax2.add_patch(rect2)
    ax2.text(3, 5.2, "GEANT4 MC with digitizer\nidentifies the anomaly:", ha="center", fontsize=9, fontweight="bold")
    ax2.text(3, 4.0, "• True fraction: 0.32% (not 4%)\n• 55% C12 nuclear recoils\n• 15% protons, 13% electrons\n• 9% alphas, 7% heavy ions", ha="center", fontsize=8)
    ax2.text(3, 2.5, "Physical mechanism:", ha="center", fontsize=9, fontweight="bold")
    ax2.text(3, 1.8, "190 MeV protons scatter off C12\nin CD₂ target → recoiling C12\nions deposit all energy in first\n~25 μm of scintillator", ha="center", fontsize=7)

    # Step 3: Resolution
    ax3 = axes[2]
    ax3.set_xlim(0, 6); ax3.set_ylim(0, 6); ax3.axis("off")
    ax3.set_title("Step 3: Resolution", fontweight="bold", color="#2ecc71")
    rect3 = FancyBboxPatch((0.3, 1), 5.4, 4.5, boxstyle="round", facecolor="#f0fff0", edgecolor="#2ecc71", lw=2)
    ax3.add_patch(rect3)
    ax3.text(3, 5.2, "GMM Cluster 2 veto:", ha="center", fontsize=9, fontweight="bold")
    ax3.text(3, 4.5, ">99% capture of C12 anomalies", ha="center", fontsize=8, color="#2ecc71")
    ax3.text(3, 3.5, "Impact on physics:", ha="center", fontsize=9, fontweight="bold")
    ax3.text(3, 2.8, "<0.1% systematic on deuteron\ncount after morphology cut", ha="center", fontsize=8)

    rect4 = FancyBboxPatch((1, 0.8), 4, 1, boxstyle="round", facecolor="#fff3cd", edgecolor="#f39c12", lw=1.5)
    ax3.add_patch(rect4)
    ax3.text(3, 1.3, "✅ Anomaly IDENTIFIED & VETOED\nThis is what MC validation is for.", ha="center", fontsize=8, fontweight="bold")

    plt.tight_layout()
    save(fig, "10_c12_discovery_story.png")


# ═══════════════════════════════════════════════════════════════════════════════
# FIGURE 11: Leakage Controls
# ═══════════════════════════════════════════════════════════════════════════════
def fig_11_leakage_controls():
    fig, axes = plt.subplots(1, 3, figsize=(14, 4))
    fig.suptitle("How We Prevent ML from Cheating: The Three Leakage Controls", fontweight="bold", fontsize=13)

    controls = [
        ("1. Target Shuffle", "Shuffle labels randomly.\nIf ML still 'wins',\nthe features carry\nno real signal.\n\nCatches: self-referential\nlabels, data leakage.",
         "#e74c3c", "AUC → 0.50"),
        ("2. Leave-One-Run-Out", "Train on runs 31-57,\ntest on runs 58-65.\nIf it breaks, the signal\nis run-specific,\nnot general.\n\nCatches: calibration drift,\nrun-period artifacts.",
         "#e67e22", "σ₆₈ → degrades"),
        ("3. Event-Block Shuffle", "Shuffle training data\nin blocks of events.\nIf it breaks, there's\nwithin-run temporal\nleakage.\n\nCatches: waveform\ncorrelations, trigger\ntiming artifacts.",
         "#9b59b6", "AUC → 0.50"),
    ]

    for ax, (title, desc, color, result) in zip(axes, controls):
        ax.set_xlim(0, 6); ax.set_ylim(0, 6); ax.axis("off")
        ax.set_title(title, fontweight="bold", color=color, fontsize=11)
        rect = FancyBboxPatch((0.3, 0.3), 5.4, 5.2, boxstyle="round",
                              facecolor="white", edgecolor=color, lw=2.5)
        ax.add_patch(rect)
        ax.text(3, 4.5, desc, ha="center", fontsize=8)
        ax.text(3, 0.8, f"If leaked → {result}", ha="center", fontsize=9, fontweight="bold", color=color)

    plt.tight_layout()
    save(fig, "11_leakage_controls.png")



# ═══════════════════════════════════════════════════════════════════════════════
# FIGURE 12: Stopping Depth — MC vs Data Catastrophic Failure
# ═══════════════════════════════════════════════════════════════════════════════
def fig_12_stopping_depth_failure():
    fig, axes = plt.subplots(1, 2, figsize=(13, 5))
    fig.suptitle("MV3: Stopping-Depth Tension — the trigger, not missing material (real Trig_bar sim)", fontweight="bold", fontsize=12, color="#3498db")

    staves = ["B2", "B4", "B6", "B8"]
    mc_frac = [47.0, 18.2, 12.5, 22.3]
    data_frac = [87.6, 6.3, 3.9, 2.3]
    x = np.arange(len(staves))

    ax = axes[0]
    w = 0.35
    ax.bar(x-w/2, mc_frac, w, label="MC (GEANT4)", color=C_MC, edgecolor="black", alpha=0.8)
    ax.bar(x+w/2, data_frac, w, label="Data", color=C_DATA, edgecolor="black", alpha=0.8)
    ax.set_xticks(x); ax.set_xticklabels(staves)
    ax.set_ylabel("Fraction of pulses (%)")
    ax.set_title("Stopping-Depth Profile", fontweight="bold")
    ax.legend()
    ax.annotate("10× too many\nat B8!", xy=(3, mc_frac[3]), xytext=(3.5, 25),
                fontsize=9, color=C_FAIL, fontweight="bold",
                arrowprops=dict(arrowstyle="->", color=C_FAIL, lw=2))

    ax2 = axes[1]
    ax2.set_xlim(0, 6); ax2.set_ylim(0, 6); ax2.axis("off")
    ax2.set_title("Root Cause — CORRECTED", fontweight="bold")

    ax2.text(3, 5.5, "χ²/ndf = 68,269 (untriggered)", ha="center", fontsize=11, fontweight="bold", color=C_FAIL)
    ax2.text(3, 5.0, "Re-graded FAIL → TENSION (2026-07-05)", ha="center", fontsize=9, color="#3498db")

    rect = FancyBboxPatch((0.3, 1), 5.4, 3.5, boxstyle="round", facecolor="#eef4ff", edgecolor="#3498db", lw=2)
    ax2.add_patch(rect)
    ax2.text(3, 4.2, "Mechanism: the two-arm coincidence TRIGGER", ha="center", fontsize=9, fontweight="bold")
    ax2.text(3, 3.4, "'Missing ~8-10 g/cm² material' is FALSIFIED:\n≤0.8 g/cm² exists vs ≥10.5 g/cm² required (×13).\nReal Trig_bar sim: B2 45.9% → 99.7% (over-purifies\nvs data 93.3%). No new GEANT4 production needed.", ha="center", fontsize=8)
    ax2.text(3, 1.6, "See Fig 33 (hero) / Fig 25 — postreview set", ha="center", fontsize=9, fontweight="bold", color="#3498db")

    plt.tight_layout()
    save(fig, "12_stopping_depth_failure.png")


# ═══════════════════════════════════════════════════════════════════════════════
# FIGURE 13: Data vs MC Timing Comparison
# ═══════════════════════════════════════════════════════════════════════════════
def fig_13_timing_mc_vs_data():
    fig, axes = plt.subplots(2, 2, figsize=(12, 9))
    fig.suptitle("MV4: Timing — Data vs MC Comparison", fontweight="bold", fontsize=13)

    vals = [
        (0, 0, "σ₆₈ Raw (ns)", (1.744, 0.007), 1.85, "✅ PASS\npull = −1.05σ", C_PASS),
        (0, 1, "σ₆₈ Corrected (ns)", (1.770, 0.010), 1.50, "🔶 TENSION\npull = +2.68σ", C_TENSION),
        (1, 0, "R_max (MHz)", (3.044, 0.005), 3.05, "✅ PASS\ndiff = 0.2%", C_PASS),
        (1, 1, "τ_eff (ns)", (124.8, 1.0), 124.79, "✅ PASS\ndiff < 0.01%", C_PASS),
    ]

    for row, col, label, mc, data_val, verdict, color in vals:
        ax = axes[row, col]
        ax.bar(["MC", "Data"], [mc[0], data_val], yerr=[mc[1], 0],
               color=[C_MC, C_DATA], edgecolor="black", linewidth=1.5, capsize=8)
        ax.set_ylabel(label, fontweight="bold")
        ax.set_title(label, fontweight="bold")

        # Verdict box
        rect = FancyBboxPatch((0.15, 0.72), 0.7, 0.25, boxstyle="round,pad=0.05",
                              facecolor="white", edgecolor=color, lw=1.5, transform=ax.transAxes)
        ax.add_patch(rect)
        ax.text(0.5, 0.845, verdict, transform=ax.transAxes, ha="center", fontsize=8, fontweight="bold", color=color)

    plt.tight_layout()
    save(fig, "13_timing_mc_vs_data.png")


# ═══════════════════════════════════════════════════════════════════════════════
# FIGURE 14: Saturation Recovery
# ═══════════════════════════════════════════════════════════════════════════════
def fig_14_saturation_recovery():
    fig, axes = plt.subplots(1, 2, figsize=(12, 4.5))
    fig.suptitle("Saturation Recovery: Where ML Decisively Wins", fontweight="bold", fontsize=13)

    # Left: comparison
    methods = ["Template\n(shape fit)", "ML\n(ExtraTrees)", "ML\n(HGB)"]
    values = [0.186, 0.038, 0.032]
    colors = [C_TRAD, C_ML, C_ML]

    ax = axes[0]
    bars = ax.bar(methods, values, color=colors, edgecolor="black", linewidth=1.5)
    for bar, val in zip(bars, values):
        ax.text(bar.get_x()+bar.get_width()/2, bar.get_height()+0.005, f"{val:.3f}",
                ha="center", fontweight="bold")
    ax.set_ylabel("res68 (fractional)", fontweight="bold")
    ax.set_title("Saturation Recovery Accuracy", fontweight="bold")
    ax.grid(axis="y", alpha=0.2)

    # Right: why ML wins
    ax2 = axes[1]
    t = np.arange(18) * 10
    y_sat = np.minimum(np.exp(-0.5*((t-55)/15)**2)*1.2, 0.8)
    ax2.plot(t, np.exp(-0.5*((t-55)/15)**2)*1.2, "--", color="gray", alpha=0.5, label="True pulse")
    ax2.plot(t, y_sat, "o-", color=C_ML, markersize=5, lw=2, label="Saturated (clipped)")
    ax2.fill_between(t[:8], 0, y_sat[:8], alpha=0.2, color=C_ML)
    ax2.text(t[4], 0.95, "ML uses the\nUNSATURATED\nrising edge\nto recover\ntrue amplitude", ha="center", fontsize=9, fontweight="bold", color=C_ML)
    ax2.set_xlabel("Time (ns)"); ax2.set_ylabel("ADC (norm.)")
    ax2.set_title("How ML Recovers Saturated Pulses", fontweight="bold")
    ax2.legend(fontsize=8)
    ax2.grid(alpha=0.2)

    plt.tight_layout()
    save(fig, "14_saturation_recovery.png")


# ═══════════════════════════════════════════════════════════════════════════════
# FIGURE 15: Study Coverage Map
# ═══════════════════════════════════════════════════════════════════════════════
def fig_15_study_coverage_map():
    fig, ax = plt.subplots(figsize=(14, 7))
    ax.set_xlim(0, 14); ax.set_ylim(0, 8); ax.axis("off")
    ax.set_title("Which Studies Cover Which Physics Questions", fontweight="bold", fontsize=13)

    domains = [
        ("Data Pipeline", [(0.5, 6.5, 2.5, 1, "#34495e", "S00, S01\nS00a-f")]),
        ("Timing", [(0.5, 4.5, 2.5, 1.5, "#3498db", "S02, S03a-p\nS05a-n\nMV4, MV4b")]),
        ("Pile-up", [(3.5, 4.5, 2.5, 1.5, "#e67e22", "S10a-o\nS11a-k\nMV5")]),
        ("Pulse Shape", [(6.5, 4.5, 2.5, 1.5, "#9b59b6", "P01a-l, P02a-h\nP09a-i, P10a-l\nMV6")]),
        ("Amplitude/Energy", [(9.5, 4.5, 2.5, 1.5, "#2ecc71", "P04a-x, P07a-k\nS14a-i, S15a-b\nMV0, MV2")]),
        ("PID", [(0.5, 2.5, 2.5, 1.5, "#1abc9c", "S07a-o, S13a-f\nMV1, MV3")]),
        ("Pedestal", [(3.5, 2.5, 2.5, 1.5, "#f39c12", "S16a-o\nS17a-b")]),
        ("A-Stack", [(6.5, 2.5, 2.5, 1.5, "#e74c3c", "S05a, S18a-j")]),
        ("MC Validation", [(9.5, 2.5, 2.5, 1.5, "#8e44ad", "MV0-MV6\nMV3b, MV4b")]),
    ]

    for title, rects in domains:
        for x, y, w, h, color, text in rects:
            rect = FancyBboxPatch((x, y), w, h, boxstyle="round,pad=0.1",
                                  facecolor=color, edgecolor="black", lw=1.5, alpha=0.8)
            ax.add_patch(rect)
            ax.text(x+w/2, y+h-0.25, title, ha="center", fontsize=9, fontweight="bold", color="white")
            ax.text(x+w/2, y+h/2-0.2, text, ha="center", fontsize=8, color="white", alpha=0.9)

    ax.text(7, 1.2, "~230 studies organized across 9 physics domains", ha="center", fontsize=10, fontweight="bold", color="gray")
    ax.text(7, 0.8, "Each study: reproduce-first, ML-vs-traditional benchmark, 3 leakage controls", ha="center", fontsize=8, color="gray")

    plt.tight_layout()
    save(fig, "15_study_coverage_map.png")


# ═══════════════════════════════════════════════════════════════════════════════
# FIGURE 16: Data Pipeline — Before/After Selection
# ═══════════════════════════════════════════════════════════════════════════════
def fig_16_data_pipeline_before_after():
    fig, axes = plt.subplots(1, 2, figsize=(12, 4.5))
    fig.suptitle("Data Selection: From Raw Waveforms to Analysis-Ready Pulses", fontweight="bold", fontsize=13)

    # Step-by-step
    ax = axes[0]
    ax.set_xlim(0, 10); ax.set_ylim(0, 8); ax.axis("off")
    ax.set_title("Selection Pipeline", fontweight="bold")

    steps = [
        (5, 7.3, "Raw ROOT files", "110 files, ~810 MB\nhrdb_run_NNNN.root", "#34495e"),
        (5, 5.7, "Read HRDv tree", "Extract all waveforms\nacross all channels", "#7f8c8d"),
        (5, 4.1, "Even B-stack only", "Keep B2, B4, B6, B8\n(Discard odd channels)", "#3498db"),
        (5, 2.5, "Baseline subtraction", "median(ADC samples 0-3)\nper waveform", "#e67e22"),
        (5, 0.9, "Amplitude cut", "A > 1000 ADC\n→ 640,737 selected pulses", "#2ecc71"),
    ]
    for x, y, title, desc, color in steps:
        rect = FancyBboxPatch((x-4, y-0.25), 8, 0.6, boxstyle="round,pad=0.05",
                              facecolor=color, edgecolor="black", lw=1, alpha=0.85)
        ax.add_patch(rect)
        ax.text(x, y+0.15, title, ha="center", fontsize=8, fontweight="bold", color="white")
        ax.text(x, y-0.1, desc, ha="center", fontsize=7, color="white", alpha=0.8)

    # Right: result
    ax2 = axes[1]
    ax2.set_xlim(0, 10); ax2.set_ylim(0, 8); ax2.axis("off")
    ax2.set_title("Reproducibility Guarantee", fontweight="bold")
    ax2.text(5, 7, "640,737 pulses", ha="center", fontsize=18, fontweight="bold", color="#2ecc71")
    ax2.text(5, 6.3, "Reproduced exactly (zero delta)\nfrom the original analysis note", ha="center", fontsize=9, color="gray")
    ax2.text(5, 5.3, "This is the entry condition\nfor every downstream claim.", ha="center", fontsize=9, fontweight="bold")

    rect = FancyBboxPatch((1.5, 2), 7, 2.5, boxstyle="round", facecolor="#f0fff0", edgecolor="#2ecc71", lw=2)
    ax2.add_patch(rect)
    ax2.text(5, 4.2, "Deterministic pipeline:", ha="center", fontsize=9, fontweight="bold")
    ax2.text(5, 3.5, "No fitted parameters\nNo statistical sampling\nNo random seeds", ha="center", fontsize=8)
    ax2.text(5, 2.3, "→ Different people, different machines,\nsame 640,737 count. Every time.", ha="center", fontsize=8, fontweight="bold")

    plt.tight_layout()
    save(fig, "16_data_pipeline.png")


# ═══════════════════════════════════════════════════════════════════════════════
# FIGURE 17: PID How It Works
# ═══════════════════════════════════════════════════════════════════════════════
def fig_17_pid_how_it_works():
    fig, axes = plt.subplots(1, 2, figsize=(13, 5))
    fig.suptitle("Particle ID Without Truth Labels: How We Tell Protons from Deuterons", fontweight="bold", fontsize=13)

    ax = axes[0]
    ax.set_xlim(0, 8); ax.set_ylim(0, 8); ax.axis("off")
    ax.set_title("Physics Approach", fontweight="bold")

    ax.text(4, 7.5, "Key Fact: Deuterons are heavier than protons", ha="center", fontsize=10, fontweight="bold")

    items = [
        (4, 6.3, "1. ΔE–E Method", "Heavier particles lose more energy\nper unit length → higher dE/dx"),
        (4, 4.8, "2. Range Separation", "Deuterons stop in B2/B4\nProtons reach B6/B8"),
        (4, 3.3, "3. Sample Enrichment", "Sample I = D-enriched (trigger\nselects early-stopping particles)\nSample II = p-enriched"),
        (4, 1.8, "4. MC Truth: GEANT4", "400,369 truth tracks:\n150,130 protons, 146,842 deuterons"),
    ]
    for x, y, title, desc in items:
        ax.text(x, y, title, ha="center", fontsize=9, fontweight="bold", color=C_DATA)
        ax.text(x, y-0.5, desc, ha="center", fontsize=8)

    ax2 = axes[1]
    categories = ["HGB (best)", "Logistic Regression", "Single-cut ΔE"]
    aucs = [0.9860, 0.9629, 0.8910]
    purities = [0.9644, 0.9489, 0.8910]
    x = np.arange(len(categories))
    w = 0.35
    ax2.bar(x-w/2, aucs, w, label="AUC", color=C_DATA, edgecolor="black")
    ax2.bar(x+w/2, purities, w, label="Purity @ 90% eff", color=C_PASS, edgecolor="black")
    for i, (a, p) in enumerate(zip(aucs, purities)):
        ax2.text(i-w/2, a+0.005, f"{a:.4f}", ha="center", fontsize=9, fontweight="bold")
        ax2.text(i+w/2, p+0.005, f"{p:.4f}", ha="center", fontsize=9, fontweight="bold")
    ax2.set_xticks(x); ax2.set_xticklabels(categories, fontsize=8)
    ax2.set_ylabel("Score"); ax2.set_title("PID Performance (MV1 MC Truth)", fontweight="bold")
    ax2.legend(fontsize=8); ax2.set_ylim(0.80, 1.02)
    ax2.axhline(y=0.9860, color=C_MC, ls="--", alpha=0.5)
    ax2.text(2.5, 0.988, "MC truth ceiling", fontsize=8, color=C_MC, ha="center")

    plt.tight_layout()
    save(fig, "17_pid_how_it_works.png")


# ═══════════════════════════════════════════════════════════════════════════════
# FIGURE 18: Gain Calibration
# ═══════════════════════════════════════════════════════════════════════════════
def fig_18_gain_calibration():
    fig, axes = plt.subplots(1, 2, figsize=(12, 4.5))
    fig.suptitle("MV0: Digitizer Gain Calibration", fontweight="bold", fontsize=13)

    ax = axes[0]
    versions = ["v1 (WRONG)", "v2 (CORRECTED)"]
    gains = [246, 92]
    errors = [50, 28]
    colors = [C_FAIL, C_PASS]
    bars = ax.bar(versions, gains, yerr=errors, color=colors, edgecolor="black", linewidth=2, capsize=10)
    for bar, val, err in zip(bars, gains, errors):
        ax.text(bar.get_x()+bar.get_width()/2, bar.get_height()+err+8, f"{val}±{err}", ha="center", fontweight="bold")
    ax.set_ylabel("Gain (ADC/MeV)", fontweight="bold")
    ax.set_title("Digitizer Gain", fontweight="bold")
    ax.grid(axis="y", alpha=0.2)

    ax2 = axes[1]
    ax2.set_xlim(0, 6); ax2.set_ylim(0, 6); ax2.axis("off")
    ax2.set_title("Why v1 Was Wrong", fontweight="bold")
    ax2.text(3, 5.3, "v1: 246 ADC/MeV", fontsize=10, fontweight="bold", color=C_FAIL)
    ax2.text(3, 4.8, "Used raw amplitude (not baseline-subtracted)", fontsize=8, color=C_FAIL)
    ax2.text(3, 4.3, "Compared against wrong MC convention", fontsize=8, color=C_FAIL)
    ax2.text(3, 3.5, "v2: 92 ± 28 ADC/MeV", fontsize=10, fontweight="bold", color=C_PASS)
    ax2.text(3, 3.0, "Uses net_ADC = amplitude − baseline", fontsize=8, color=C_PASS)
    ax2.text(3, 2.5, "Correct MC energy scale matching", fontsize=8, color=C_PASS)
    ax2.text(3, 1.5, "⚠️ ±30% uncertainty dominates\nthe deuteron-fraction budget", fontsize=8, fontweight="bold", color=C_TENSION)

    plt.tight_layout()
    save(fig, "18_gain_calibration.png")


# ═══════════════════════════════════════════════════════════════════════════════
# FIGURE 19: Pedestal Comparison
# ═══════════════════════════════════════════════════════════════════════════════
def fig_19_pedestal_comparison():
    fig, ax = plt.subplots(figsize=(9, 5))
    methods = ["Adaptive\n(legacy)", "HGBR\n(learned)"]
    values = [341, 49]
    colors = [C_FAIL, C_PASS]
    bars = ax.bar(methods, values, color=colors, edgecolor="black", linewidth=2, width=0.5)
    for bar, val in zip(bars, values):
        ax.text(bar.get_x()+bar.get_width()/2, bar.get_height()+8, f"{val} ADC", ha="center", fontweight="bold", fontsize=12)
    ax.set_ylabel("MAE vs pretrigger-median (ADC)", fontweight="bold")
    ax.set_title("S16: Pedestal Accuracy — Adaptive vs Learned", fontweight="bold")
    ax.grid(axis="y", alpha=0.2)

    ax.text(0.5, 0.95, "⚠️ Caveat: No true forced-trigger\npedestal data exists.\nAll validation is proxy-based.", transform=ax.transAxes, ha="center", fontsize=8, color=C_TENSION,
            bbox=dict(boxstyle="round", facecolor="#fff3cd", alpha=0.8))

    plt.tight_layout()
    save(fig, "19_pedestal_comparison.png")


# ═══════════════════════════════════════════════════════════════════════════════
# FIGURE 20: Reading Guide / Visual TOC
# ═══════════════════════════════════════════════════════════════════════════════
def fig_20_reading_guide():
    fig, ax = plt.subplots(figsize=(14, 8))
    ax.set_xlim(0, 16); ax.set_ylim(0, 10); ax.axis("off")
    ax.set_title("How to Read This Wiki — Visual Guide", fontweight="bold", fontsize=14, pad=20)

    sections = [
        (0.5, 8, "§2 Setup", "The experiment\n& detector", "#34495e", "→"),
        (4, 8, "§3 Pipeline", "From raw data\nto analysis", "#7f8c8d", "→"),
        (7.5, 8, "§4 Timing", "Resolution,\ntimewalk, B2", C_DATA, "→"),
        (11, 8, "§5 Pile-up", "R_max, live-time,\noverlaps", "#e67e22", ""),

        (0.5, 4.5, "§6 ML", "Where ML helps\n(and doesn't)", "#9b59b6", "→"),
        (4, 4.5, "§7 Energy", "Amplitude, charge,\nsaturation", "#2ecc71", "→"),
        (7.5, 4.5, "§8 PID", "Proton vs deuteron\nAUC = 0.986", "#1abc9c", "→"),
        (11, 4.5, "§9 Pedestal", "Baseline, gain,\ndigitizer", "#f39c12", ""),

        (0.5, 1, "§10 Systematics", "Budget, priorities,\nopen items", C_FAIL, "→"),
        (4, 1, "§11 Open Questions", "What's next,\nwhat's blocked", C_TENSION, "→"),
        (7.5, 1, "§12 Methodology", "Leakage controls,\nreport rules", "#8e44ad", "→"),
        (11, 1, "Study Catalogue", "Every study with\nproper name + link", "#2c3e50", ""),
    ]

    for x, y, title, desc, color, arrow in sections:
        rect = FancyBboxPatch((x, y), 2.8, 1.5, boxstyle="round,pad=0.1",
                              facecolor=color, edgecolor="black", lw=1.5, alpha=0.85)
        ax.add_patch(rect)
        ax.text(x+1.4, y+1.0, title, ha="center", fontsize=9, fontweight="bold", color="white")
        ax.text(x+1.4, y+0.4, desc, ha="center", fontsize=7, color="white", alpha=0.9)
        if arrow:
            ax.text(x+2.8, y+0.75, arrow, fontsize=15, color="gray", ha="center", va="center")

    ax.text(8, 6.8, "Start anywhere — each section is self-contained", ha="center", fontsize=9, fontweight="bold", color="gray")
    ax.text(8, 6.3, "Or read §1→§12 for the full story", ha="center", fontsize=8, color="gray")

    plt.tight_layout()
    save(fig, "20_reading_guide.png")


# ═══════════════════════════════════════════════════════════════════════════════
# FIGURE 21: Two-Pulse Recovery
# ═══════════════════════════════════════════════════════════════════════════════
def fig_21_twopulse_recovery():
    fig, axes = plt.subplots(1, 2, figsize=(12, 4.5))
    fig.suptitle("Two-Pulse Decomposition: ML Wins RMS But Higher Failure Rate", fontweight="bold", fontsize=13)

    ax = axes[0]
    methods = ["Template\n(constrained)", "ML\n(MLP/CNN)", "ML\n(amp-binned)"]
    rms = [13.30, 10.67, 9.28]
    failures = [0.168, 0.295, 0.295]
    x = np.arange(len(methods))
    w = 0.35
    ax.bar(x-w/2, rms, w, label="Time RMS (ns)", color=C_TRAD, edgecolor="black")
    ax2_ax = ax.twinx()
    ax2_ax.bar(x+w/2, failures, w, label="Failure Rate", color=C_FAIL, edgecolor="black", alpha=0.7)
    for i, (r, f) in enumerate(zip(rms, failures)):
        ax.text(i-w/2, r+0.3, f"{r:.1f}", ha="center", fontsize=9, fontweight="bold")
        ax2_ax.text(i+w/2, f+0.01, f"{f:.3f}", ha="center", fontsize=9, fontweight="bold", color=C_FAIL)
    ax.set_xticks(x); ax.set_xticklabels(methods)
    ax.set_ylabel("Time RMS (ns)", color=C_TRAD)
    ax2_ax.set_ylabel("Failure Rate", color=C_FAIL)
    ax.set_title("S11: Two-Pulse Recovery Performance", fontweight="bold")
    lines1, labels1 = ax.get_legend_handles_labels()
    lines2, labels2 = ax2_ax.get_legend_handles_labels()
    ax.legend(lines1+lines2, labels1+labels2, fontsize=7)

    ax2 = axes[1]
    ax2.set_xlim(0, 6); ax2.set_ylim(0, 6); ax2.axis("off")
    ax2.set_title("Adoption Decision", fontweight="bold")
    ax2.text(3, 5.3, "ML recovers shorter separations", fontsize=9, color=C_PASS)
    ax2.text(3, 4.8, "and lower timing RMS", fontsize=9, color=C_PASS)
    ax2.text(3, 3.8, "BUT: higher failure rate (0.295 vs 0.168)", fontsize=9, color=C_FAIL, fontweight="bold")
    ax2.text(3, 3.0, "→ Conventional template fit is", fontsize=9)
    ax2.text(3, 2.5, "SAFER at the accepted", fontsize=9, fontweight="bold")
    ax2.text(3, 2.0, "operating point", fontsize=9, fontweight="bold")
    ax2.text(3, 1.2, "ML adoption GATED on", fontsize=8, color=C_TENSION)
    ax2.text(3, 0.7, "MC overlay study (MV5 extension)", fontsize=8, color=C_TENSION)

    plt.tight_layout()
    save(fig, "21_twopulse_recovery.png")


# ═══════════════════════════════════════════════════════════════════════════════
# FIGURE 22: ML Landscape Detail
# ═══════════════════════════════════════════════════════════════════════════════
def fig_22_ml_landscape_detail():
    fig, ax = plt.subplots(figsize=(11, 6))

    tasks = [
        "Saturation Recovery",
        "Duplicate Readout",
        "Two-Pulse Time RMS",
        "Timewalk Correction",
        "Pile-up Rate (Poisson)",
        "Deep Net Timing",
        "PID (Data-only)",
        "Representation",
    ]
    statuses = [
        ("ML Wins (3-7×)", C_PASS, "✅"),
        ("ML Wins (res68 0.003)", C_PASS, "✅"),
        ("Better RMS, worse fail", C_TENSION, "⚠️"),
        ("Tie/Loss", C_TRAD, "="),
        ("Tie/Loss", C_TRAD, "="),
        ("ML Loses", C_FAIL, "❌"),
        ("Leakage artifact", C_FAIL, "❌"),
        ("CORRECTED (LORO fail)", C_FAIL, "❌"),
    ]

    y = np.arange(len(tasks))
    for i, (task, (verdict, color, symbol)) in enumerate(zip(tasks, statuses)):
        ax.barh(i, 1, color=color, edgecolor="black", linewidth=1, alpha=0.6, height=0.6)
        ax.text(0.05, i, f"{symbol} {task}: {verdict}", va="center", fontsize=10, fontweight="bold")

    ax.set_yticks([])
    ax.set_xlim(0, 1.5)
    ax.set_title("ML Performance Across All Domains", fontweight="bold", fontsize=13)
    ax.text(0.75, -0.8, "✅ = ML helps  |  = = ML ties traditional  |  ❌ = ML loses / leaked  |  ⚠️ = partially helps",
            ha="center", fontsize=9, transform=ax.get_xaxis_transform())

    # Legend
    from matplotlib.patches import Patch
    legend_elements = [
        Patch(facecolor=C_PASS, alpha=0.6, label="ML Wins (signal in waveform shape)"),
        Patch(facecolor=C_TENSION, alpha=0.6, label="ML Partially Wins (gated)"),
        Patch(facecolor=C_TRAD, alpha=0.6, label="Tie/Loss (analytic optimal)"),
        Patch(facecolor=C_FAIL, alpha=0.6, label="ML Loses / Leakage / Corrected"),
    ]
    ax.legend(handles=legend_elements, loc="lower center", ncol=2, fontsize=8, bbox_to_anchor=(0.5, -0.3))

    plt.tight_layout()
    save(fig, "22_ml_landscape_detail.png")


# ═══════════════════════════════════════════════════════════════════════════════
# FIGURE 23: Per-Stave Timing Breakdown
# ═══════════════════════════════════════════════════════════════════════════════
def fig_23_per_stave_timing():
    fig, ax = plt.subplots(figsize=(10, 5))
    staves = ["B2\n(excluded)", "B4", "B6\n(best)", "B8", "B4+B6+B8\n(combined)"]
    values = [2.8, 1.45, 0.72, 0.93, 0.55]
    colors = [C_FAIL, C_B4, C_PASS, C_B8, C_COMB]
    bars = ax.bar(staves, values, color=colors, edgecolor="black", linewidth=1.5)
    for bar, val in zip(bars, values):
        ax.text(bar.get_x()+bar.get_width()/2, bar.get_height()+0.05, f"{val:.2f} ns", ha="center", fontweight="bold", fontsize=11)
    ax.set_ylabel("σ₆₈ (ns)", fontweight="bold")
    ax.set_title("Per-Stave Timing Resolution", fontweight="bold")
    ax.grid(axis="y", alpha=0.2)
    ax.annotate("B2 excluded:\nterminal deuteron\ntopology dominates", xy=(0, 2.8), xytext=(1.5, 3.5),
                fontsize=8, color=C_FAIL, arrowprops=dict(arrowstyle="->", color=C_FAIL))
    ax.annotate("Best single stave:\ncleanest timing,\nno topology bias", xy=(2, 0.72), xytext=(3.5, 1.8),
                fontsize=8, color=C_PASS, arrowprops=dict(arrowstyle="->", color=C_PASS))

    plt.tight_layout()
    save(fig, "23_per_stave_timing.png")


# ═══════════════════════════════════════════════════════════════════════════════
# MAIN
# ═══════════════════════════════════════════════════════════════════════════════
if __name__ == "__main__":
    print(f"Generating figures in {OUTPUT_DIR}/ ...\n")

    fig_01_experimental_setup()
    fig_02_physics_motivation()
    fig_03_waveform_annotated()
    fig_04_detector_cross_section()
    fig_05_timing_chain()
    fig_06_timewalk_explained()
    fig_07_b2_covariance()
    fig_08_pileup_cartoon()
    fig_09_rmax_correction()
    fig_10_c12_discovery_story()
    fig_11_leakage_controls()
    fig_12_stopping_depth_failure()
    fig_13_timing_mc_vs_data()
    fig_14_saturation_recovery()
    fig_15_study_coverage_map()
    fig_16_data_pipeline_before_after()
    fig_17_pid_how_it_works()
    fig_18_gain_calibration()
    fig_19_pedestal_comparison()
    fig_20_reading_guide()
    fig_21_twopulse_recovery()
    fig_22_ml_landscape_detail()
    fig_23_per_stave_timing()

    print(f"\n✅ All 23 figures generated in {OUTPUT_DIR}/")
