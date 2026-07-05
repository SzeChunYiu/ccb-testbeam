#!/usr/bin/env python3
"""
Generate post-external-review publication figures for the CCB Test-Beam wiki.

Backend: Python / matplotlib (nature-figure skill; PYTHON was pre-selected).

Standards applied (nature-figure skill: contract.md, stance.md, api.md, qa-contract.md):
- one shared rcParams block: sans-serif, editable SVG/PDF text, font.size 7,
  no top/right spines;
- ONE restrained, colorblind-safe palette per figure — one neutral family
  (greys) + one signal family (blue) + green/red reserved strictly for
  gains / drops / struck-out (retracted) quantities;
- hero panel + subordinate evidence panels (fig 25);
- every axis labelled with units; error bars / CIs drawn wherever the source
  artifact provides them and their definition stated in the wiki caption;
- NO figure asserts a retracted claim; retracted numbers are shown struck out.

Every number is loaded at run time from a reports/<id>/ artifact (paths in
SOURCES) or is quoted from the report cited in that figure's header comment.

Each figure is written as PNG (600 dpi, for the wiki), SVG and PDF (editable)
into docs/figures/.

Run:
  /home/billy/anaconda3/envs/nnbar_env/bin/python scripts/generate_postreview_figures.py
"""

import csv
import json
import os
import sys

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import matplotlib.patches as mpatches  # noqa: E402
import numpy as np  # noqa: E402

# ── Shared style (nature-figure Python quick-start) ─────────────────────────
plt.rcParams.update({
    "font.family": "sans-serif",
    "font.sans-serif": ["Arial", "DejaVu Sans", "Liberation Sans"],
    "svg.fonttype": "none",     # editable text in SVG
    "pdf.fonttype": 42,         # editable TrueType text in PDF
    "font.size": 7,
    "axes.titlesize": 8,
    "axes.labelsize": 7,
    "legend.fontsize": 6.2,
    "xtick.labelsize": 6.5,
    "ytick.labelsize": 6.5,
    "axes.spines.right": False,
    "axes.spines.top": False,
    "axes.linewidth": 0.8,
    "legend.frameon": False,
    "figure.facecolor": "white",
    "axes.facecolor": "white",
    "savefig.bbox": "tight",
    "savefig.pad_inches": 0.05,
    "lines.linewidth": 1.1,
})

# Colorblind-safe palette (nature-figure PALETTE)
PAL = {
    "blue_main": "#0F4D92",
    "blue_secondary": "#3775BA",
    "blue_soft": "#B4C0E4",
    "red_strong": "#B64342",
    "teal": "#42949E",
    "violet": "#9A4D8E",
    "gold": "#C9A227",
    "green_up": "#2E9E44",
    "red_down": "#E53935",
    "n_light": "#CFCECE",
    "n_mid": "#767676",
    "n_dark": "#4D4D4D",
    "n_black": "#272727",
}

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUTPUT_DIR = os.path.join(REPO, "docs/figures")
STAVES = ["B2", "B4", "B6", "B8"]

SOURCES = {
    "grid":  "reports/phase2_geometry_1783108797/mv3v4_grid.json",
    "s21":   "reports/s21_sample12_trigger_truth_1783077969/s21_summary.json",
    "s23":   "reports/s23_sample12_data_mc_1783108675/s23_summary.json",
    "s22":   "reports/s22_timing_vs_amplitude_1783108999/s22_summary.json",
    "mc03":  "reports/mc03_overlay_1783180480/result.json",
    "rc":    "reports/mc03_overlay_1783180480/risk_coverage_curves.csv",
    "mv7":   "reports/mc02_pulse_table_1783107862/mv7_pedestal_validation.json",
}


def load(key):
    with open(os.path.join(REPO, SOURCES[key])) as fh:
        return json.load(fh)


def save_pub(fig, basenames, close=True):
    """Save PNG (600 dpi) + SVG + PDF for one or more basenames. Returns paths."""
    if isinstance(basenames, str):
        basenames = [basenames]
    paths = []
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    for base in basenames:
        for ext, kw in (("png", {"dpi": 600}), ("svg", {}), ("pdf", {})):
            p = os.path.join(OUTPUT_DIR, f"{base}.{ext}")
            fig.savefig(p, **kw)
            paths.append(p)
    if close:
        plt.close(fig)
    for p in paths:
        print(f"  wrote {os.path.relpath(p, REPO)}")
    return paths


def _strike(ax, x, y, val_text, color=PAL["red_down"]):
    """Draw a struck-through (retracted) value label."""
    t = ax.text(x, y, val_text, color=PAL["n_mid"], fontsize=6.5,
                ha="center", va="center")
    return t


# ══════════════════════════════════════════════════════════════════════════
# Fig 25 — HERO: the trigger, not missing material, is the MV3 root cause.
#   Archetype: asymmetric mixed-modality (hero ladder + subordinate profiles).
#   Source: reports/phase2_geometry_1783108797/mv3v4_grid.json + grid_table.md
#           (published untriggered ref χ²/ndf = 68,269 quoted in the MV3 report).
# ══════════════════════════════════════════════════════════════════════════
def fig25_mv3_hero():
    grid = load("grid")["grid"]

    def pick(basis, species, mapping, gain):
        for g in grid:
            if (g["basis"] == basis and g["species"] == species
                    and g["mapping"] == mapping and g["gain"] == gain
                    and g["trigger"] == "acoinc"):
                return g
        raise KeyError((basis, species, mapping, gain))

    trig_g92 = pick("track", "inclusive", "paired", 92.0)   # A·B trigger proxy
    even_g92 = pick("track", "inclusive", "even_read", 92.0)
    odd_g92 = pick("track", "inclusive", "odd_read", 92.0)
    best_g60 = pick("track", "inclusive", "paired", 60.0)    # best grid point
    evt_g60 = pick("event", "inclusive", "paired", 60.0)     # +event+species-incl

    # Hero ladder: (label, chi2/ndf, colour-role)
    ladder = [
        ("odd-read map\n(disfavoured, gain 92)", odd_g92["chi2_ndf_all"], "grey"),
        ("Untriggered MC\n(MV3 published ref, gain 92)", 68269.0, "fail"),
        ("even-read map\n(disfavoured, gain 92)", even_g92["chi2_ndf_all"], "grey"),
        ("+ A·B trigger proxy\n(gain 92)", trig_g92["chi2_ndf_all"], "fix"),
        ("+ event basis + species-inclusive\n(gain 60)", evt_g60["chi2_ndf_all"], "fix"),
        ("Best grid point\n(trigger, gain 60)", best_g60["chi2_ndf_all"], "fixbest"),
    ]
    role_c = {"grey": PAL["n_light"], "fail": PAL["red_strong"],
              "fix": PAL["blue_secondary"], "fixbest": PAL["blue_main"]}

    fig = plt.figure(figsize=(7.2, 5.6))
    gs = fig.add_gridspec(2, 1, height_ratios=[1.35, 1.0], hspace=0.42)
    axh = fig.add_subplot(gs[0])
    axs = fig.add_subplot(gs[1])

    # Hero: horizontal log lollipop of chi2/ndf
    order = sorted(range(len(ladder)), key=lambda i: ladder[i][1])  # best->worst
    ypos = np.arange(len(ladder))
    for y, i in zip(ypos, order):
        lab, val, role = ladder[i]
        c = role_c[role]
        axh.hlines(y, 1, val, color=c, lw=2.4, zorder=2)
        axh.plot(val, y, "o", color=c, markersize=6.5, zorder=3,
                 markeredgecolor="black", markeredgewidth=0.5)
        axh.text(val * 1.35, y, f"{val:,.0f}", va="center", ha="left",
                 fontsize=6.8, color=PAL["n_black"])
        axh.text(0.6, y, lab, va="center", ha="right", fontsize=6.3,
                 color=PAL["n_dark"])
    axh.set_yticks([])
    axh.set_xscale("log")
    axh.set_xlim(0.5, 3e6)
    axh.set_xlabel("Stopping-depth profile agreement,  χ²/ndf  (log scale; lower = better)")
    axh.spines["left"].set_visible(False)
    # Annotate the decisive drop
    yi_untrig = int(np.where(np.array(order) == 1)[0][0])
    yi_trig = int(np.where(np.array(order) == 3)[0][0])
    axh.annotate("A·B coincidence trigger\napplied: ×22 drop",
                 xy=(trig_g92["chi2_ndf_all"], yi_trig),
                 xytext=(2.5e4, (yi_untrig + yi_trig) / 2 + 0.35),
                 fontsize=6.4, color=PAL["blue_main"], ha="left", va="center",
                 arrowprops=dict(arrowstyle="->", color=PAL["blue_main"], lw=0.9))
    axh.set_title("a   The trigger — not missing material — is the root cause of the MV3 stopping-depth failure",
                  loc="left", fontsize=8.2)

    # Subordinate: stave-fraction profiles vs data
    data_all = load("grid")["data"]["all"]["fractions"]
    prof = {
        "Data (all)": [data_all[s] for s in STAVES],
        "Untriggered MC (MV3)": [0.470, 0.182, 0.125, 0.223],
        "Trigger-proxy MC (gain 60)": [best_g60["fractions"][s] for s in STAVES],
    }
    pcol = {"Data (all)": PAL["n_black"],
            "Untriggered MC (MV3)": PAL["red_strong"],
            "Trigger-proxy MC (gain 60)": PAL["blue_main"]}
    x = np.arange(len(STAVES))
    w = 0.26
    for k, (name, vals) in enumerate(prof.items()):
        axs.bar(x + (k - 1) * w, vals, w, label=name, color=pcol[name],
                edgecolor="black", linewidth=0.5)
    axs.set_yscale("log")
    axs.set_ylim(8e-3, 1.3)
    axs.set_xticks(x)
    axs.set_xticklabels(STAVES)
    axs.set_xlabel("B-arm stave (increasing depth →)")
    axs.set_ylabel("Fraction of selected pulses")
    axs.legend(loc="upper center", ncol=3, fontsize=6.0, columnspacing=1.0,
               handletextpad=0.4, bbox_to_anchor=(0.5, 1.02))
    axs.set_title("b   Untriggered MC over-predicts deep-stave (B8) penetration ×10; the trigger proxy tracks the data",
                  loc="left", fontsize=8.2)
    axs.annotate("×10 excess", xy=(3.0, 0.20), xytext=(2.45, 0.055),
                 fontsize=6.3, color=PAL["red_strong"], ha="center", va="center",
                 arrowprops=dict(arrowstyle="->", color=PAL["red_strong"], lw=0.8))
    return save_pub(fig, "25_mv3_trigger_rootcause")


# ══════════════════════════════════════════════════════════════════════════
# Fig 26 (+ alias 08) — C12 recoils cannot be the data early-peak class.
#   Archetype: quantitative grid (two bar panels).
#   Source: reports/phase4_1783180742/REPORT.md (MV6b quenched vs unquenched
#           twin; A>1000 net ADC; early-peak = peak_sample<=3; data 4.4%).
# ══════════════════════════════════════════════════════════════════════════
def fig26_c12():
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(7.2, 3.2),
                                   gridspec_kw={"wspace": 0.42})

    # Panel a: early-peak A>1000 fraction (%)
    labels = ["MC quenched\n(Birks ON)", "MC unquenched\n(twin)", "Data\n(P02/P09)"]
    vals = [0.0, 0.0, 4.4]
    cols = [PAL["blue_main"], PAL["blue_soft"], PAL["red_strong"]]
    x = np.arange(3)
    ax1.bar(x, vals, 0.6, color=cols, edgecolor="black", linewidth=0.6)
    ax1.axhline(4.4, color=PAL["red_strong"], ls="--", lw=0.9)
    ax1.text(0.5, 4.6, "data 4.4%", color=PAL["red_strong"], fontsize=6.5,
             ha="center")
    for xi, v in zip(x, vals):
        if v == 0:
            ax1.text(xi, v + 0.12, "0.000%", ha="center", fontsize=6.5)
    ax1.set_xticks(x)
    ax1.set_xticklabels(labels)
    ax1.set_ylabel("Early-peak fraction of A>1000 pulses (%)")
    ax1.set_ylim(0, 5.4)
    ax1.set_title("a   MC early-peak fraction = 0.000% everywhere",
                  loc="left", fontsize=7.4)

    # Panel b: C12 records passing A>1000 (out of 1,656), gain 297
    labels2 = ["Quenched\n(Birks ON)", "Unquenched\ntwin"]
    passed = [0, 3]
    x2 = np.arange(2)
    bars = ax2.bar(x2, passed, 0.55, color=[PAL["blue_main"], PAL["blue_soft"]],
                   edgecolor="black", linewidth=0.6)
    for xi, v in zip(x2, passed):
        ax2.text(xi, v + 0.08, f"{v} / 1,656", ha="center", fontsize=6.6)
    ax2.set_xticks(x2)
    ax2.set_xticklabels(labels2)
    ax2.set_ylabel("C12-dominant records passing A>1000\n(gain 297; 0 at gains 60–297)")
    ax2.set_ylim(0, 4.0)
    ax2.set_title("b   0 of 1,656 C12 records reach A>1000 (quenched)",
                  loc="left", fontsize=7.4)
    ax2.text(0.5, 3.5, "C12 recoil light  ÷  quench ~60–100\n→ sits at the noise floor",
             ha="center", fontsize=6.0, color=PAL["n_dark"])

    fig.suptitle("MV6b — the retracted “C12” attribution is ruled out: the 4.4% early-peak class is not a species/scintillation effect",
                 fontsize=7.8, y=1.03)
    return save_pub(fig, ["26_mv6b_c12_ruled_out", "08_c12_anomaly"])


# ══════════════════════════════════════════════════════════════════════════
# Fig 27 — Honest +8% MC/data pile-up live-time disagreement (not agreement).
#   Archetype: quantitative grid (per-stave forest + reference bands).
#   Source: reports/mc03_overlay_1783180480/result.json (tau_eff by_stave,
#           pooled, data_live10_ns). Data-side CI [123.33,126.36] ns from S10.
# ══════════════════════════════════════════════════════════════════════════
def fig27_taueff():
    mc03 = load("mc03")["tau_eff"]
    by = {r["stave"]: r for r in mc03["by_stave"]}
    pooled = mc03["pooled"]

    fig, ax = plt.subplots(figsize=(5.4, 3.3))
    x = np.arange(len(STAVES))
    vals = [by[s]["live10_ns"] for s in STAVES]
    lo = [by[s]["live10_ci_low"] for s in STAVES]
    hi = [by[s]["live10_ci_high"] for s in STAVES]
    ax.errorbar(x, vals, yerr=[np.array(vals) - lo, np.array(hi) - vals],
                fmt="o", color=PAL["blue_main"], markersize=6, capsize=2.5,
                lw=1.0, label="MC per-stave τ_eff  (bootstrap 95% CI)")
    for xi, v in zip(x, vals):
        ax.text(xi, v + 1.3, f"{v:.1f}", ha="center", fontsize=6.3,
                color=PAL["blue_main"])

    # pooled MC band
    ax.axhline(pooled["live10_ns"], color=PAL["blue_secondary"], ls="-", lw=1.0)
    ax.axhspan(pooled["ci_low"], pooled["ci_high"], color=PAL["blue_soft"], alpha=0.5)
    ax.text(3.35, pooled["live10_ns"] + 0.4,
            f"MC pooled {pooled['live10_ns']:.2f} ns", fontsize=6.2,
            color=PAL["blue_secondary"], ha="right")

    # data band (value from result.json; CI from S10 waveform bootstrap)
    dv = pooled["data_live10_ns"]
    ax.axhline(dv, color=PAL["red_strong"], ls="--", lw=1.1)
    ax.axhspan(123.33, 126.36, color=PAL["red_strong"], alpha=0.12)
    ax.text(3.35, dv - 1.9, f"data {dv:.2f} ns  [123.3, 126.4] (S10)",
            fontsize=6.2, color=PAL["red_strong"], ha="right")

    ax.annotate("", xy=(1.5, pooled["live10_ns"]), xytext=(1.5, dv),
                arrowprops=dict(arrowstyle="<->", color=PAL["n_mid"], lw=0.9))
    ax.text(1.6, (pooled["live10_ns"] + dv) / 2,
            f"+{pooled['delta_ns']:.1f} ns  (+8%)\nhonest disagreement",
            fontsize=6.3, color=PAL["n_dark"], va="center", ha="left")
    ax.set_xticks(x)
    ax.set_xticklabels(STAVES)
    ax.set_xlabel("B-arm stave")
    ax.set_ylabel("Effective live-time τ_eff (ns)")
    ax.set_ylim(120, 145)
    ax.legend(loc="upper left", fontsize=6.0)
    ax.set_title("MC03 first independent MC live-time vs data — a +8% disagreement\n(replaces the retracted MV5 “MC confirms R_max”)",
                 loc="left", fontsize=7.4)
    return save_pub(fig, "27_mc_taueff_vs_data")


# ══════════════════════════════════════════════════════════════════════════
# Fig 28 (+ alias 18) — No precision digitizer gain yet; honest 60–80 band.
#   Archetype: schematic-led composite (number line + gain-scan inset).
#   Source: v1 246 / v2 92±28 retracted (External Review 2026-07-02; Phase 2);
#           gain-scan χ²/ndf from mv3v4_grid.json (track/incl/paired/acoinc).
# ══════════════════════════════════════════════════════════════════════════
def fig28_gain():
    grid = load("grid")["grid"]
    scan = sorted(
        [g for g in grid if g["basis"] == "track" and g["species"] == "inclusive"
         and g["mapping"] == "paired" and g["trigger"] == "acoinc"],
        key=lambda g: g["gain"])
    gains = [g["gain"] for g in scan]
    chi2 = [g["chi2_ndf_all"] for g in scan]

    fig, (ax, ax2) = plt.subplots(1, 2, figsize=(7.4, 2.9),
                                  gridspec_kw={"width_ratios": [1.25, 1.0],
                                               "wspace": 0.32})

    # Panel a: number line of gain hypotheses
    ax.set_xlim(0, 320)
    ax.set_ylim(0, 1)
    ax.axhline(0.5, color=PAL["n_mid"], lw=1.0)
    ax.axvspan(60, 80, ymin=0.30, ymax=0.70, color=PAL["green_up"], alpha=0.18)
    ax.text(70, 0.80, "trigger-consistent\nband ≈ 60–80", ha="center",
            fontsize=6.4, color=PAL["green_up"])
    ax.plot([60, 80], [0.5, 0.5], color=PAL["green_up"], lw=4, solid_capstyle="butt")
    # struck-out retracted values
    for gx, txt in [(92, "v2  92 ± 28\nRETRACTED"), (246, "v1  ~246\nRETRACTED")]:
        ax.plot(gx, 0.5, "x", color=PAL["red_down"], markersize=8, markeredgewidth=1.6)
        ax.text(gx, 0.24, txt, ha="center", va="top", fontsize=6.0,
                color=PAL["red_down"])
    ax.plot(297, 0.5, "s", color=PAL["n_light"], markersize=6,
            markeredgecolor=PAL["n_mid"])
    ax.text(297, 0.30, "297\nplaceholder", ha="right", va="top", fontsize=5.8,
            color=PAL["n_mid"])
    ax.set_yticks([])
    ax.spines["left"].set_visible(False)
    ax.set_xlabel("Digitizer gain (ADC / MeV)")
    ax.set_title("a   No precision gain yet — both published values retracted",
                 loc="left", fontsize=7.4)

    # Panel b: gain-scan chi2/ndf (trigger-consistent scan is monotonic, min @60)
    ax2.plot(gains, chi2, "o-", color=PAL["blue_main"], markersize=4)
    imin = int(np.argmin(chi2))
    ax2.plot(gains[imin], chi2[imin], "o", color=PAL["green_up"], markersize=7,
             zorder=4)
    ax2.text(gains[imin] + 8, chi2[imin], f"min @ gain {gains[imin]:.0f}\nχ²/ndf {chi2[imin]:.0f}",
             fontsize=6.0, color=PAL["green_up"], va="center")
    ax2.set_yscale("log")
    ax2.set_xlabel("Digitizer gain (ADC / MeV)")
    ax2.set_ylabel("MV3 stopping-depth χ²/ndf")
    ax2.set_title("b   Trigger-consistent scan prefers ~60 (quenched re-scan → ~70–80)",
                  loc="left", fontsize=7.4)
    fig.suptitle("Digitizer gain: an honest band, not a number", fontsize=7.8, y=1.02)
    return save_pub(fig, ["28_gain_honest_band", "18_gain_calibration"])


# ══════════════════════════════════════════════════════════════════════════
# Fig 29 — Multiplicity control is necessary, not sufficient.
#   Archetype: quantitative grid (paired census bars + falsified-survivor callout).
#   Source: reports/stats01_program_fdr_20260703_220116/REPORT.md (family table;
#           BH q=0.05 within family; S03k survives BH yet falsified by S03p/S03r).
# ══════════════════════════════════════════════════════════════════════════
def fig29_fdr():
    # (family, nominal CI-excludes-zero, survive BH)
    fam = [
        ("representation", 372, 372),
        ("pedestal",       231, 225),
        ("amplitude-charge", 462, 419),
        ("timing",         221, 200),
        ("pileup",         131, 129),
        ("pid",             18,  17),
    ]
    fam = sorted(fam, key=lambda r: r[1])
    names = [f[0] for f in fam]
    nom = np.array([f[1] for f in fam])
    surv = np.array([f[2] for f in fam])
    drop = nom - surv

    fig, (ax, ax2) = plt.subplots(1, 2, figsize=(7.2, 3.2),
                                  gridspec_kw={"width_ratios": [1.5, 1.0]})
    y = np.arange(len(fam))
    ax.barh(y, nom, 0.62, color=PAL["n_light"], edgecolor="black",
            linewidth=0.5, label="Nominal (CI excludes 0)")
    ax.barh(y, surv, 0.62, color=PAL["blue_main"], edgecolor="black",
            linewidth=0.5, label="Survives BH (q = 0.05)")
    for yi, n, s, d in zip(y, nom, surv, drop):
        ax.text(n + 6, yi, f"{s}/{n}" + (f"  (−{d})" if d else ""), va="center",
                fontsize=6.0, color=PAL["n_dark"])
    ax.set_yticks(y)
    ax.set_yticklabels(names)
    ax.set_xlim(0, 520)
    ax.set_xlabel("Delta-with-CI claims")
    ax.legend(loc="lower right", fontsize=6.0)
    ax.set_title("a   Per-family Benjamini–Hochberg census (nominal vs surviving)",
                 loc="left", fontsize=7.4)

    # Panel b: scoreboard + falsified-survivor callout
    ax2.axis("off")
    ax2.set_xlim(0, 1)
    ax2.set_ylim(0, 1)
    ax2.text(0.0, 0.96, "17 scoreboard “bold wins”", fontsize=7.2,
             fontweight="bold", va="top")
    # stacked win bar
    parts = [(11, PAL["blue_main"], "11 survive BH"),
             (6, PAL["n_light"], "6 prose/derived only"),
             (0, PAL["red_down"], "0 fail BH")]
    xoff = 0.0
    for val, c, lab in parts:
        if val == 0:
            continue
        ax2.add_patch(mpatches.Rectangle((xoff, 0.72), val / 17.0, 0.12,
                                         facecolor=c, edgecolor="black", lw=0.5,
                                         transform=ax2.transAxes))
        ax2.text(xoff + val / 34.0, 0.78, str(val), ha="center", va="center",
                 fontsize=6.2, color="white" if c == PAL["blue_main"] else "black",
                 transform=ax2.transAxes)
        xoff += val / 17.0
    ax2.text(0.0, 0.64, "■ 11 survive BH   ■ 6 prose/derived only   (0 fail)",
             fontsize=5.8, va="top", color=PAL["n_dark"])
    # falsified-despite-BH callout
    ax2.add_patch(mpatches.FancyBboxPatch((0.0, 0.06), 1.0, 0.42,
                                          boxstyle="round,pad=0.02",
                                          facecolor=PAL["red_strong"], alpha=0.10,
                                          edgecolor=PAL["red_strong"], lw=0.9,
                                          transform=ax2.transAxes))
    ax2.text(0.5, 0.40, "Necessary, not sufficient", ha="center", fontsize=7.0,
             fontweight="bold", color=PAL["red_strong"], transform=ax2.transAxes)
    ax2.text(0.5, 0.28,
             "S03k SURVIVES BH\n(Δ = −0.44 ns, CI [−0.84, −0.24])\nyet was FALSIFIED by the S03p/S03r\nfeature-leakage null grids.\nBH cannot detect leakage.",
             ha="center", va="center", fontsize=5.9, color=PAL["n_black"],
             transform=ax2.transAxes)
    ax2.set_title("b   A survivor can still be wrong", loc="left", fontsize=7.4)

    fig.suptitle("STATS01 program-level FDR: multiplicity control is necessary but not sufficient",
                 fontsize=7.8, y=1.02)
    return save_pub(fig, "29_fdr_census")


# ══════════════════════════════════════════════════════════════════════════
# Fig 30 — Two-pulse: traditional wins at matched coverage, ML at full coverage.
#   Archetype: quantitative grid (risk-coverage curves + summary bars).
#   Source: reports/mc03_overlay_1783180480/risk_coverage_curves.csv,
#           result.json (failure_at_coverage, common_subset_sigma68).
# ══════════════════════════════════════════════════════════════════════════
def fig30_riskcov():
    rows = list(csv.DictReader(open(os.path.join(REPO, SOURCES["rc"]))))
    mc03 = load("mc03")
    fac = {(r["method"], float(r["rate_mhz"])): r for r in mc03["failure_at_coverage"]}
    css = {float(r["rate_mhz"]): r for r in mc03["common_subset_sigma68"]}

    fig, (ax, ax2) = plt.subplots(1, 2, figsize=(7.2, 3.2),
                                  gridspec_kw={"width_ratios": [1.35, 1.0]})

    mcol = {"trad": PAL["blue_main"], "ml": PAL["red_strong"]}
    mlab = {"trad": "Template fit (traditional)", "ml": "Compact ML"}
    for method in ("trad", "ml"):
        for rate, alpha, lw in (("0.5", 1.0, 1.4), ("1.5", 0.4, 0.9),
                                ("3.0", 0.4, 0.9)):
            cur = [(float(r["coverage"]), float(r["risk"])) for r in rows
                   if r["method"] == method and r["rate_mhz"] == rate]
            cur.sort()
            cov = [c for c, _ in cur]
            rk = [k for _, k in cur]
            ax.plot(cov, rk, color=mcol[method], alpha=alpha, lw=lw,
                    label=(mlab[method] if rate == "0.5" else None))
    ax.axvline(0.80, color=PAL["n_mid"], ls=":", lw=0.9)
    ax.text(0.80, ax.get_ylim()[1] * 0.94, " matched\n 80% coverage", fontsize=5.8,
            color=PAL["n_dark"], ha="left", va="top")
    ax.set_xlabel("Coverage (fraction answered)")
    ax.set_ylabel("Risk (failure rate on answered)")
    ax.set_xlim(0, 1.02)
    ax.set_ylim(0, 0.06)
    ax.legend(loc="upper left", fontsize=6.0)
    ax.set_title("a   Risk–coverage (bold = 0.5 MHz; faint = 1.5 / 3.0 MHz)",
                 loc="left", fontsize=7.4)

    # Panel b: summary metrics, trad vs ML at 0.5 MHz
    metrics = ["Failure @\nfull coverage", "Failure @\n80% coverage", "Common-subset\nΔt σ₆₈ (ns)"]
    trad = [float(fac[("trad", 0.5)]["failure_rate_full"]),
            float(fac[("trad", 0.5)]["failure_at_80pct_coverage"]),
            css[0.5]["sigma68_trad_ns"]]
    ml = [float(fac[("ml", 0.5)]["failure_rate_full"]),
          float(fac[("ml", 0.5)]["failure_at_80pct_coverage"]),
          css[0.5]["sigma68_ml_ns"]]
    # normalise each metric to its own max for a shared axis, annotate real values
    x = np.arange(len(metrics))
    w = 0.36
    maxes = [max(t, m) if max(t, m) > 0 else 1 for t, m in zip(trad, ml)]
    tn = [t / mx for t, mx in zip(trad, maxes)]
    mn = [m / mx for m, mx in zip(ml, maxes)]
    ax2.bar(x - w / 2, tn, w, color=PAL["blue_main"], edgecolor="black",
            linewidth=0.5, label="Traditional")
    ax2.bar(x + w / 2, mn, w, color=PAL["red_strong"], edgecolor="black",
            linewidth=0.5, label="Compact ML")
    for xi, t, m in zip(x, trad, ml):
        ax2.text(xi - w / 2, t / max(t, m, 1e-9) + 0.03,
                 (f"{t:.3f}" if t >= 0.001 or t == 0 else f"{t:.1e}"),
                 ha="center", fontsize=5.6, rotation=90, va="bottom")
        ax2.text(xi + w / 2, m / max(t, m, 1e-9) + 0.03,
                 (f"{m:.3f}" if m >= 0.001 else f"{m:.1e}"),
                 ha="center", fontsize=5.6, rotation=90, va="bottom")
    ax2.set_xticks(x)
    ax2.set_xticklabels(metrics, fontsize=5.8)
    ax2.set_ylim(0, 1.45)
    ax2.set_yticks([])
    ax2.spines["left"].set_visible(False)
    ax2.legend(loc="upper right", fontsize=6.0)
    ax2.set_title("b   Split verdict (0.5 MHz; bars scaled per metric)",
                  loc="left", fontsize=7.4)
    fig.suptitle("Honest two-pulse benchmark (MC03/S24): traditional wins at matched coverage, ML at full coverage",
                 fontsize=7.6, y=1.02)
    return save_pub(fig, "30_twopulse_riskcoverage")


# ══════════════════════════════════════════════════════════════════════════
# Fig 31 — σ68 improves with amplitude following a 1/A timewalk law.
#   Archetype: quantitative grid (two sample panels, per-pair curves).
#   Source: reports/s22_timing_vs_amplitude_1783108999/s22_curves.csv (per-bin
#           σ68 + bootstrap CIs) and s22_summary.json scaling_fits inv_A
#           (model σ(A) = √(c² + k²(1000/A)²)).
# ══════════════════════════════════════════════════════════════════════════
def fig31_s22():
    s22 = load("s22")
    fits = s22["scaling_fits"]
    curve_rows = list(csv.DictReader(
        open(os.path.join(REPO,
                          "reports/s22_timing_vs_amplitude_1783108999/s22_curves.csv"))))
    pairs = ["B4-B6", "B4-B8", "B6-B8"]
    pcol = {"B4-B6": PAL["blue_main"], "B4-B8": PAL["teal"], "B6-B8": PAL["violet"]}

    def pts(samp, pair):
        A, s, lo, hi = [], [], [], []
        for r in curve_rows:
            if (r["sample"] == samp and r["pair"] == pair
                    and r["stage"] == "raw_cfd20" and r["sigma68_ns"]):
                A.append(float(r["amp_median"]))
                s.append(float(r["sigma68_ns"]))
                lo.append(float(r["ci_low_ns"]))
                hi.append(float(r["ci_high_ns"]))
        return map(np.array, (A, s, lo, hi))

    fig, axes = plt.subplots(1, 2, figsize=(7.2, 3.2), sharey=True)
    for ax, samp, stag in zip(axes, ["sample_I", "sample_II"], ["I", "II"]):
        for pair in pairs:
            A, s, lo, hi = pts(samp, pair)
            fit = fits[f"{samp}|{pair}|raw_cfd20"]["inv_A"]
            c, k = fit["floor_c_ns"], fit["coeff_k_ns"]
            xx = np.linspace(A.min(), A.max(), 120)
            ax.plot(xx, np.sqrt(c**2 + k**2 * (1000.0 / xx)**2),
                    color=pcol[pair], lw=1.1, zorder=2)
            ax.errorbar(A, s, yerr=[s - lo, hi - s], fmt="o", color=pcol[pair],
                        markersize=3.4, markeredgecolor="black",
                        markeredgewidth=0.3, capsize=1.6, lw=0.7, zorder=3)
            ax.text(A.max() * 1.01, np.sqrt(c**2 + k**2 * (1000.0 / A.max())**2),
                    f" {pair}  (χ²/ndf {fit['chi2_ndf']:.2f})", fontsize=5.6,
                    color=pcol[pair], va="center")
        ax.set_xlabel("Min-pair amplitude (ADC)")
        ax.set_xlim(900, 4300)
        ax.set_title(f"Sample {stag}", loc="left", fontsize=7.6)
    axes[0].set_ylabel("Pair-difference σ₆₈ (ns)")
    axes[0].set_ylim(0, 3.3)
    axes[0].text(0.03, 0.05,
                 "curves: σ(A) = √(c² + k²(1000/A)²)  (1/A timewalk law)\n"
                 "points: per-bin σ₆₈, bars = bootstrap 95% CI",
                 transform=axes[0].transAxes, fontsize=5.5, color=PAL["n_dark"])
    fig.suptitle("S22 — pair-difference timing sharpens with amplitude along a 1/A law (raw CFD20; per-run-centred, 200 bootstraps)",
                 fontsize=7.2, y=1.02)
    return save_pub(fig, "31_s22_timing_vs_amplitude")


# ══════════════════════════════════════════════════════════════════════════
# Fig 32 — The Sample-I deuteron enrichment is present in the DATA.
#   Archetype: quantitative grid (data fractions + data/MC double ratios).
#   Source: reports/s23_sample12_data_mc_1783108675/s23_summary.json.
# ══════════════════════════════════════════════════════════════════════════
def fig32_s23():
    s23 = load("s23")
    fig, (ax, ax2) = plt.subplots(1, 2, figsize=(7.2, 3.2))

    # Panel a: data high-amplitude fraction per stave, Sample I vs II
    x = np.arange(len(STAVES))
    w = 0.36
    for off, samp, col, lab in ((-w / 2, "I", PAL["blue_main"], "Sample I (A·B trigger)"),
                                (+w / 2, "II", PAL["teal"], "Sample II (B-only)")):
        f = np.array([s23["data"][samp]["staves"][s]["frac_high"] for s in STAVES])
        ci = np.array([s23["data"][samp]["staves"][s]["frac_high_ci"] for s in STAVES])
        ax.bar(x + off, f, w, color=col, edgecolor="black", linewidth=0.5,
               yerr=[f - ci[:, 0], ci[:, 1] - f], capsize=2.5, label=lab,
               error_kw=dict(ecolor="black", lw=0.8))
    ax.set_xticks(x)
    ax.set_xticklabels(STAVES)
    ax.set_ylabel("Data fraction with A > 5000 ADC")
    ax.set_ylim(0, 0.82)
    ax.legend(loc="upper right", fontsize=6.0)
    ax.set_title("a   Sample-I B2 spectrum is markedly harder (data)",
                 loc="left", fontsize=7.4)
    ax.annotate("ratio 3.45\n[3.41, 3.50]", xy=(0 - w / 2, 0.71),
                xytext=(0.8, 0.6), fontsize=6.2, color=PAL["blue_main"],
                arrowprops=dict(arrowstyle="->", color=PAL["blue_main"], lw=0.8))

    # Panel b: data/MC double ratios per stave (occupancy) + B2 high-frac DR
    dr = s23["double_ratio"]["occupancy"]
    vals = [dr[s]["dr"] for s in STAVES]
    lo = [dr[s]["dr_lo"] for s in STAVES]
    hi = [dr[s]["dr_hi"] for s in STAVES]
    ax2.errorbar(x, vals, yerr=[np.array(vals) - lo, np.array(hi) - vals],
                 fmt="s", color=PAL["violet"], markersize=5, capsize=2.5, lw=1.0,
                 label="Occupancy double ratio")
    ax2.axhline(1.0, color=PAL["n_mid"], ls="--", lw=0.9)
    ax2.text(3.4, 1.02, "MC = data", fontsize=6.0, color=PAL["n_mid"], ha="right")
    hf = s23["double_ratio"]["high_frac_b2"]
    ax2.errorbar([0], [hf["dr"]], yerr=[[hf["dr"] - hf["dr_lo"]], [hf["dr_hi"] - hf["dr"]]],
                 fmt="D", color=PAL["gold"], markersize=6, capsize=2.5, lw=1.0,
                 label="B2 high-amp double ratio")
    ax2.text(0.12, hf["dr"], f" {hf['dr']:.2f}", fontsize=6.2, color=PAL["gold"],
             va="center")
    ax2.set_xticks(x)
    ax2.set_xticklabels(STAVES)
    ax2.set_ylabel("Double ratio  (data I/II) / (MC I/II)")
    ax2.set_ylim(0.2, 1.85)
    ax2.legend(loc="upper right", fontsize=6.0)
    ax2.set_title("b   MC under-predicts the between-sample contrast (missing trigger sim)",
                  loc="left", fontsize=7.4)
    fig.suptitle("S23 — the trigger-driven Sample-I enrichment is confirmed in the data (error bars: 95% bootstrap CI)",
                 fontsize=7.4, y=1.02)
    return save_pub(fig, "32_s23_data_enrichment")


# ══════════════════════════════════════════════════════════════════════════
# Fig 09 (rebuild) — R_max is a one-sided upper bound, not 4.22 MHz.
#   Archetype: schematic-led composite (tau estimators + resulting R_max).
#   Source: WIKI §5.2 / S10 (tau estimators); mc03 result.json (MC tau_eff);
#           R_max = 0.380 / tau_eff. MV5 retracted.
# ══════════════════════════════════════════════════════════════════════════
def fig09_rmax():
    # (label, tau_eff ns, colour, note)
    taus = [
        ("note assumption\n(τ = 90 ns)", 90.0, PAL["red_down"], "struck"),
        ("10%-crossing\n(data, τ = 124.8)", 124.79, PAL["blue_main"], "ok"),
        ("Kaplan–Meier\n(τ = 151.6)", 151.6, PAL["teal"], "ok"),
        ("IPCW\n(τ = 179.1)", 179.1, PAL["violet"], "ok"),
    ]
    fig, (ax, ax2) = plt.subplots(1, 2, figsize=(7.2, 3.0))
    x = np.arange(len(taus))
    for xi, (lab, tau, col, note) in zip(x, taus):
        ax.bar(xi, tau, 0.6, color=col, edgecolor="black", linewidth=0.5,
               hatch="//" if note == "struck" else None,
               alpha=0.6 if note == "struck" else 1.0)
        ax.text(xi, tau + 3, f"{tau:.1f}", ha="center", fontsize=6.2)
    ax.set_xticks(x)
    ax.set_xticklabels([t[0] for t in taus], fontsize=5.7)
    ax.set_ylabel("Effective live-time τ_eff (ns)")
    ax.set_ylim(0, 200)
    ax.text(0, 40, "WRONG", ha="center", color=PAL["red_down"], fontsize=6.0,
            rotation=90, fontweight="bold")
    ax.set_title("a   τ_eff estimators (the note's 90 ns is an error)",
                 loc="left", fontsize=7.4)

    # Panel b: resulting R_max = 0.380 / tau
    MU = 0.380
    rmax = [(lab, MU / (tau * 1e-9) / 1e6, col, note) for lab, tau, col, note in taus]
    for xi, (lab, r, col, note) in zip(x, rmax):
        ax2.bar(xi, r, 0.6, color=col, edgecolor="black", linewidth=0.5,
                hatch="//" if note == "struck" else None,
                alpha=0.6 if note == "struck" else 1.0)
        ax2.text(xi, r + 0.08, f"{r:.2f}", ha="center", fontsize=6.2)
    ax2.axhline(3.05, color=PAL["blue_main"], ls="--", lw=1.0)
    ax2.text(3.4, 3.14, "R_max ≤ 3.05 MHz\n(one-sided bound)", fontsize=6.0,
             color=PAL["blue_main"], ha="right")
    ax2.set_xticks(x)
    ax2.set_xticklabels([t[0] for t in taus], fontsize=5.7)
    ax2.set_ylabel("R_max = μ_max / τ_eff  (MHz)")
    ax2.set_ylim(0, 4.8)
    ax2.text(0, 0.9, "note's 4.22 MHz\nRETRACTED as a value", ha="center",
             fontsize=5.6, color=PAL["red_down"], rotation=90, va="bottom")
    ax2.set_title("b   Censoring-aware τ → R_max ≈ 2.1 MHz or lower",
                  loc="left", fontsize=7.4)
    fig.suptitle("Pile-up R_max — an upper bound, not 4.22 MHz  (MV5 “MC confirms R_max” retracted; slot refilled by MC03)",
                 fontsize=7.2, y=1.02)
    return save_pub(fig, "09_rmax_correction")


# ══════════════════════════════════════════════════════════════════════════
# Fig 19 (rebuild) — MV7 zero-signal MC pedestal closure (real numbers).
#   Archetype: quantitative grid (two-estimator bars).
#   Source: reports/mc02_pulse_table_1783107862/mv7_pedestal_validation.json.
# ══════════════════════════════════════════════════════════════════════════
def fig19_pedestal():
    mv7 = load("mv7")
    a, l = mv7["adaptive_estimator"], mv7["learned_estimator"]
    fig, ax = plt.subplots(figsize=(4.8, 3.2))
    labels = ["Adaptive\n(median samples 0–3)", "Learned\n(ridge, 18 samples)"]
    mae = [a["mae_adc"], l["mae_adc"]]
    rmse = [a["rmse_adc"], l["rmse_adc"]]
    x = np.arange(2)
    w = 0.36
    ax.bar(x - w / 2, mae, w, color=PAL["blue_main"], edgecolor="black",
           linewidth=0.5, label="MAE")
    ax.bar(x + w / 2, rmse, w, color=PAL["blue_soft"], edgecolor="black",
           linewidth=0.5, label="RMSE")
    for xi, v in zip(x - w / 2, mae):
        ax.text(xi, v + 0.06, f"{v:.2f}", ha="center", fontsize=6.4)
    for xi, v in zip(x + w / 2, rmse):
        ax.text(xi, v + 0.06, f"{v:.2f}", ha="center", fontsize=6.4)
    ax.set_xticks(x)
    ax.set_xticklabels(labels)
    ax.set_ylabel("Pedestal error vs absolute truth (ADC)")
    ax.set_ylim(0, 5.2)
    ax.legend(loc="upper right", fontsize=6.2)
    ax.annotate(f"×{a['mae_adc'] / l['mae_adc']:.1f} lower MAE",
                xy=(1 - w / 2, l["mae_adc"]), xytext=(0.9, 3.4),
                fontsize=6.3, color=PAL["green_up"],
                arrowprops=dict(arrowstyle="->", color=PAL["green_up"], lw=0.8))
    ax.set_title("MV7 — zero-signal MC pedestal closure\n(n = 100,000 records; lower bounds — see caveat)",
                 loc="left", fontsize=7.4)
    ax.text(0.0, -0.30,
            "White-Gaussian noise + uniform pedestal jitter [6737, 7029] ADC; correlated\n"
            "noise / drift / signal contamination not modelled → MAEs are lower bounds.",
            transform=ax.transAxes, fontsize=5.4, color=PAL["n_mid"], va="top")
    return save_pub(fig, "19_pedestal_comparison")


def main():
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    print(f"Generating post-review figures into {os.path.relpath(OUTPUT_DIR, REPO)}/ ...")
    all_paths = []
    for fn in (fig25_mv3_hero, fig26_c12, fig27_taueff, fig28_gain, fig29_fdr,
               fig30_riskcov, fig31_s22, fig32_s23, fig09_rmax, fig19_pedestal):
        print(f"[{fn.__name__}]")
        all_paths.extend(fn())
    print(f"\nDONE — {len(all_paths)} files written "
          f"({len(all_paths)//3} figures × PNG/SVG/PDF).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
