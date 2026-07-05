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
    # ── post-review round: real Trig_bar simulation + measured systematics ──
    "mv3v5": "reports/mv3_v5_realtrigger_1783242005/mv3v5_grid.json",
    "gainq": "reports/mv3_gain_quenched_1783240619/mv3_gain_quenched.json",
    "s25":   "reports/s25_covariance_timing_1783241582/s25_summary.json",
    "s26":   "reports/s26_overlay_realism_1783241582/s26_summary.json",
    "s27":   "reports/s27_earlypeak_budget_1783241582/s27_summary.json",
    # ── audit-gap round (figs 38–44): reconciliation / provenance / FDR ──
    "bm6":   "reports/bm6_runset_confound_20260705_202638/bm6_summary.json",
    "new04": "reports/new04_trigger_residual_1783275727/new04_summary.json",
    "s10g":  "reports/1781028280.978.1e517fd7/result.json",
    "bm3fdr": "reports/bm3_p04p07_fdr_20260705_203249/stats02_delta_ci_summary.json",
    "census": "reports/stats01_program_fdr_20260705_203905/claims.csv",
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


# ── helper: locate an entry in the real-trigger (mv3 v5) grid ───────────────
def _v5(basis, species, trigger, gain):
    for g in load("mv3v5")["grid"]:
        if (g["basis"] == basis and g["species"] == species
                and g["trigger"] == trigger and g["gain"] == gain):
            return g
    raise KeyError((basis, species, trigger, gain))


# ══════════════════════════════════════════════════════════════════════════
# Fig 25 (REBUILT 2026-07-05) — the trigger MOVES the B2 fraction the right way
#   (45.9% → 99.7%) but over-purifies; the Phase-2 proxy χ²/ndf ≈ 625 is RETIRED.
#   Core conclusion: a real Trig_bar simulation establishes the trigger as the
#   mechanism (untriggered B2 45.9% → real-trigger 99.7%, vs data 93.3%); the
#   over-optimistic proxy χ² 625 is retired — see Fig 33 for the hero profiles.
#   Archetype: asymmetric mixed-modality (B2-movement lollipop + retire card).
#   Source: reports/mv3_v5_realtrigger_1783242005/mv3v5_grid.json.
#   NOTE: a χ²/ndf ladder is deliberately NOT used — the ideal trigger over-
#   purifies, so its χ² vs data is LARGER, not smaller; the honest axis is the
#   B2 fraction, which moves toward (and past) the data.
# ══════════════════════════════════════════════════════════════════════════
def fig25_mv3_hero():
    d = load("mv3v5")
    untrig = _v5("track", "filtered", "none", 92.0)["fractions"]["B2"]     # 0.469
    proxy = _v5("track", "inclusive", "proxy_ahrd", 60.0)["fractions"]["B2"]  # 0.872
    real = _v5("event", "inclusive", "real_coinc", 92.0)["fractions"]["B2"]   # 0.997
    data_si = d["data"]["sample_i"]["fractions"]["B2"]                     # 0.933
    data_all = d["data"]["all"]["fractions"]["B2"]                         # 0.876

    # (label, B2 fraction, colour-role, struck?)
    ladder = [
        ("Untriggered MC\n(real 1M production, gain 92)", untrig, "fail", False),
        ("Retired Phase-2 A-HRD proxy\n(gain 60; χ²/ndf 625 RETIRED)", proxy, "grey", True),
        ("Real Trig_bar coincidence\n(A·B EDep, gain 92)", real, "fix", False),
    ]
    role_c = {"fail": PAL["red_strong"], "grey": PAL["n_mid"],
              "fix": PAL["blue_main"]}

    fig = plt.figure(figsize=(7.2, 3.4))
    ax = fig.add_subplot(111)
    y = np.arange(len(ladder))[::-1]
    for yi, (lab, val, role, struck) in zip(y, ladder):
        c = role_c[role]
        ax.hlines(yi, 0, val * 100, color=c, lw=2.6, zorder=2,
                  alpha=0.45 if struck else 1.0)
        ax.plot(val * 100, yi, "o", color=c, markersize=7, zorder=3,
                markeredgecolor="black", markeredgewidth=0.5,
                alpha=0.45 if struck else 1.0)
        txt = f"{val * 100:.1f}%"
        ax.text(val * 100 + 2.2, yi, txt, va="center", ha="left",
                fontsize=7.2, color=PAL["n_black"],
                fontweight="bold" if not struck else "normal")
        ax.text(-2, yi, lab, va="center", ha="right", fontsize=6.4,
                color=PAL["n_dark"])
        if struck:  # strike the retired proxy bar
            ax.plot([0, val * 100], [yi, yi], color=PAL["red_down"], lw=0.9,
                    zorder=4)

    # data reference lines
    ax.axvline(data_si * 100, color=PAL["n_black"], ls="--", lw=1.0, zorder=1)
    ax.text(data_si * 100, len(ladder) - 0.35, f"data Sample I {data_si*100:.1f}%",
            fontsize=6.4, color=PAL["n_black"], ha="center", va="bottom")
    ax.axvline(data_all * 100, color=PAL["n_mid"], ls=":", lw=0.9, zorder=1)
    ax.text(data_all * 100, -0.72, f"data all {data_all*100:.1f}%",
            fontsize=6.0, color=PAL["n_mid"], ha="center", va="top")

    # the decisive movement + the honest over-purification
    ax.annotate("", xy=(real * 100, y[2]), xytext=(untrig * 100, y[0]),
                arrowprops=dict(arrowstyle="->", color=PAL["blue_main"], lw=1.0,
                                connectionstyle="arc3,rad=-0.15"))
    ax.text(20, 0.52, "trigger established as\nthe mechanism\n45.9% → 99.7%",
            fontsize=6.4, color=PAL["blue_main"], ha="left", va="center")
    ax.text(101, 0.52, "over-purifies\n(> data 93.3%)", fontsize=6.0,
            color=PAL["n_dark"], ha="left", va="center")

    ax.set_yticks([])
    ax.set_xlim(0, 118)
    ax.set_ylim(-1.1, len(ladder) - 0.1)
    ax.set_xlabel("B2 (shallowest stave) fraction of the selected B-arm sample (%)")
    ax.spines["left"].set_visible(False)
    ax.set_title("The real Trig_bar trigger establishes the MV3 mechanism (B2 45.9% → 99.7%) "
                 "and retires the proxy χ²/ndf 625",
                 loc="left", fontsize=7.6)
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


# ══════════════════════════════════════════════════════════════════════════
# Fig 33 — HERO (round hero): a REAL two-arm trigger simulation establishes the
#   trigger — not missing material — as the MV3 mechanism, while over-purifying
#   vs the data (B2 45.9%→99.7% vs data 93.3%; quantitative closure open).
#   Archetype: asymmetric mixed-modality (hero per-stave profiles + subordinate
#   deep-proton veto mechanism).  This RETIRES the proxy χ²/ndf 625.
#   Source: reports/mv3_v5_realtrigger_1783242005/mv3v5_grid.json (profiles,
#           n, data fractions); mechanism fractions (31.1% / 0.06%) quoted from
#           that report's REPORT.md "The mechanism, made explicit" table.
# ══════════════════════════════════════════════════════════════════════════
def fig33_realtrigger():
    d = load("mv3v5")
    untrig_e = _v5("track", "filtered", "none", 92.0)
    real_e = _v5("event", "inclusive", "real_coinc", 92.0)
    data_si = d["data"]["sample_i"]
    untrig = [untrig_e["fractions"][s] for s in STAVES]
    real = [real_e["fractions"][s] for s in STAVES]
    dsi = [data_si["fractions"][s] for s in STAVES]

    fig = plt.figure(figsize=(7.2, 3.5))
    gs = fig.add_gridspec(1, 2, width_ratios=[1.65, 1.0], wspace=0.34)
    axa = fig.add_subplot(gs[0])
    axb = fig.add_subplot(gs[1])

    # Panel a: per-stave grouped bars, log-y (real-trigger B4–B8 ~0.001)
    prof = [
        ("Untriggered MC", untrig, PAL["red_strong"]),
        ("Real Trig_bar coincidence", real, PAL["blue_main"]),
        ("Data (Sample I)", dsi, PAL["n_black"]),
    ]
    x = np.arange(len(STAVES))
    w = 0.26
    for k, (name, vals, col) in enumerate(prof):
        axa.bar(x + (k - 1) * w, vals, w, label=name, color=col,
                edgecolor="black", linewidth=0.5)
    axa.set_yscale("log")
    axa.set_ylim(5e-4, 1.6)
    axa.set_xticks(x)
    axa.set_xticklabels(STAVES)
    axa.set_xlabel("B-arm stave (increasing stopping depth →)")
    axa.set_ylabel("Fraction of selected B-arm sample")
    axa.legend(loc="upper center", ncol=1, fontsize=6.0, bbox_to_anchor=(0.72, 1.03))
    # B2 movement callout
    axa.annotate(f"B2  45.9% → 99.7%\n(data Sample I 93.3%:\nover-purifies)",
                 xy=(0 + w, real[0]), xytext=(0.55, 0.30),
                 fontsize=6.2, color=PAL["blue_main"], ha="left", va="center",
                 arrowprops=dict(arrowstyle="->", color=PAL["blue_main"], lw=0.8))
    axa.set_title("a   Real trigger drives the shallow-stave (B2) concentration",
                  loc="left", fontsize=7.6)

    # Panel b: deep-proton veto mechanism (fractions that fire the A-paddle)
    # From REPORT.md: shallow B2 deuteron events fire A-paddle 31.1%; deep
    # B6/B8 proton events fire it 0.06% ⇒ deep-proton veto 99.94%.
    frac_deut, frac_prot = 31.1, 0.06
    cats = ["Shallow B2 deuteron\nevents\n(conjugate ~85 MeV p\nreaches A-paddle)",
            "Deep B6/B8 proton\nevents\n(conjugate ~37 MeV d\ndies before A-paddle)"]
    vals = [frac_deut, frac_prot]
    cols = [PAL["blue_main"], PAL["n_mid"]]
    xb = np.arange(2)
    axb.bar(xb, vals, 0.55, color=cols, edgecolor="black", linewidth=0.6)
    axb.set_yscale("log")
    axb.set_ylim(0.03, 100)
    for xi, v in zip(xb, vals):
        axb.text(xi, v * 1.35, f"{v:.2f}%", ha="center", fontsize=6.6,
                 color=PAL["n_black"])
    axb.set_xticks(xb)
    axb.set_xticklabels(cats, fontsize=5.5)
    axb.set_ylabel("Conjugate particle fires the A-paddle (%)")
    axb.annotate("deep-proton\nveto 99.94%", xy=(1, frac_prot),
                 xytext=(1.0, 3.0), fontsize=6.2, color=PAL["red_strong"],
                 ha="center", va="center",
                 arrowprops=dict(arrowstyle="->", color=PAL["red_strong"], lw=0.8))
    axb.set_title("b   Two-arm coincidence keeps B2 deuterons, vetoes deep protons",
                  loc="left", fontsize=7.6)

    fig.suptitle("MV3 v5 — a REAL GEANT4 two-arm-trigger simulation establishes the trigger (not missing "
                 "material) as the mechanism; the ideal trigger over-purifies (closure open)\n"
                 f"n = {untrig_e['n']:,} untriggered / {real_e['n']:,} real-coincidence MC events; "
                 f"{data_si['n_events']:,} data Sample-I pulses; exact fractions (no CIs); proxy χ²/ndf 625 retired",
                 fontsize=6.9, y=1.10)
    return save_pub(fig, "33_mv3_realtrigger")


# ══════════════════════════════════════════════════════════════════════════
# Fig 34 — Quenched trigger-consistent gain ≈ 65 ADC/MeV (band 60–70): the χ²/ndf
#   well and the B2 amplitude scale point to the same window; 297 is a placeholder.
#   Archetype: quantitative grid (χ² scan + amplitude cross-check).
#   Source: reports/mv3_gain_quenched_1783240619/mv3_gain_quenched.json.
# ══════════════════════════════════════════════════════════════════════════
def fig34_gain_quenched():
    gq = load("gainq")
    acoinc = {g["gain"]: g for g in gq["grid"] if g["trigger"] == "acoinc"}
    # the report's presented curve (skips low-gain threshold-boundary points 40,50)
    report_gains = [45, 55, 60, 65, 70, 75, 80, 90, 100, 297]
    gains = [g for g in report_gains if float(g) in acoinc]
    chi2 = [acoinc[float(g)]["chi2_ndf_all"] for g in gains]
    amp = [acoinc[float(g)]["b2_amp_median_adc"] for g in gains]
    data_amp = gq["data"]["b2_net_median_adc"]           # 2576 ADC
    gopt = int(gq["best_acoinc_all"]["gain"])            # 65
    chi2_opt = gq["best_acoinc_all"]["chi2_ndf_all"]     # 322

    fig, (ax, ax2) = plt.subplots(1, 2, figsize=(7.2, 3.1),
                                  gridspec_kw={"wspace": 0.34})

    # Panel a: chi2/ndf vs gain (log y)
    ax.plot(gains, chi2, "o-", color=PAL["blue_main"], markersize=4, zorder=2)
    ax.plot(gopt, chi2_opt, "o", color=PAL["green_up"], markersize=8, zorder=4)
    ax.annotate(f"quenched optimum\ngain ≈ {gopt}\nχ²/ndf {chi2_opt:.0f}",
                xy=(gopt, chi2_opt), xytext=(95, 470),
                fontsize=6.1, color=PAL["green_up"], va="center", ha="left",
                arrowprops=dict(arrowstyle="->", color=PAL["green_up"], lw=0.7))
    # unquenched-60 reference (Phase-2 = 625) and placeholder-297
    ax.axhline(625.0, color=PAL["n_mid"], ls="--", lw=0.9)
    ax.text(150, 625 * 1.08, "unquenched-60 (Phase 2) = 625", fontsize=5.8,
            color=PAL["n_mid"], ha="center", va="bottom")
    g297 = acoinc[297.0]["chi2_ndf_all"]
    ax.annotate(f"297 placeholder\nχ²/ndf {g297:.0f} (~24×)", xy=(297, g297),
                xytext=(180, g297 * 0.9), fontsize=5.8, color=PAL["n_dark"],
                ha="center", va="center",
                arrowprops=dict(arrowstyle="->", color=PAL["n_mid"], lw=0.7))
    ax.axvspan(60, 70, color=PAL["green_up"], alpha=0.10, zorder=0)
    ax.set_yscale("log")
    ax.set_xlabel("Digitizer gain (ADC / MeV)")
    ax.set_ylabel("MV3 stopping-depth χ²/ndf (vs data all)")
    ax.set_title("a   Quenched (Birks-on) χ² well: optimum ≈ 65, band 60–70",
                 loc="left", fontsize=7.4)

    # Panel b: B2 amplitude median vs gain, crossing the data line
    ax2.plot(gains, amp, "s-", color=PAL["blue_secondary"], markersize=4, zorder=2)
    ax2.axhline(data_amp, color=PAL["red_strong"], ls="--", lw=1.0)
    ax2.text(44, data_amp * 0.90, f"data B2 net median {data_amp:.0f} ADC",
             fontsize=6.0, color=PAL["red_strong"], ha="left", va="top")
    for g in (60, 65, 70):
        a = acoinc[float(g)]["b2_amp_median_adc"]
        ax2.plot(g, a, "o", color=PAL["green_up"] if g == 65 else PAL["n_mid"],
                 markersize=6 if g == 65 else 4, zorder=3)
    ax2.axvspan(60, 70, color=PAL["green_up"], alpha=0.10, zorder=0)
    ax2.annotate("gain 60–70 brackets\nthe data amplitude\n(2,696 / 2,917 / 3,140 ADC)",
                 xy=(70, acoinc[70.0]["b2_amp_median_adc"]), xytext=(150, 4600),
                 fontsize=5.9, color=PAL["green_up"], ha="center", va="center",
                 arrowprops=dict(arrowstyle="->", color=PAL["green_up"], lw=0.7))
    ax2.set_yscale("log")
    ax2.set_xlabel("Digitizer gain (ADC / MeV)")
    ax2.set_ylabel("MC B2 amplitude median (ADC)")
    ax2.set_title("b   Independent amplitude-scale cross-check confirms 60–70",
                  loc="left", fontsize=7.4)
    fig.suptitle("MV3 B-M5 — quenched trigger-consistent gain ≈ 65 ADC/MeV (band 60–70); χ² point values "
                 "(ndf 3, systematics-dominated — no sub-unit CI)",
                 fontsize=7.2, y=1.03)
    return save_pub(fig, "34_gain_quenched_scan")


# ══════════════════════════════════════════════════════════════════════════
# Fig 35 — A properly MEASURED combined inter-stave timing σ68 = 0.490 ns
#   [0.470, 0.508], replacing the withdrawn 0.54–0.56; not yet held-out-validated.
#   Archetype: quantitative grid (covariance heatmap + per-stave/combined forest).
#   Source: reports/s25_covariance_timing_1783241582/s25_summary.json (primary).
# ══════════════════════════════════════════════════════════════════════════
def fig35_covariance():
    s25 = load("s25")
    p = s25["primary"]
    cov = np.array(p["cov_psd_ns2"])
    st = ["B4", "B6", "B8"]
    comb = p["combined_sigma_ns"]
    comb_ci = p["combined_sigma_ci"]
    pval = p["offdiag_equality_bootstrap_p"]
    withdrawn = s25["withdrawn_number_ns"]           # [0.54, 0.56]

    fig, (ax, ax2) = plt.subplots(1, 2, figsize=(7.2, 3.2),
                                  gridspec_kw={"width_ratios": [1.0, 1.15],
                                               "wspace": 0.42})

    # Panel a: 3x3 covariance heatmap (single neutral→blue sequential ramp)
    im = ax.imshow(cov, cmap="Blues", aspect="equal")
    ax.set_xticks(range(3)); ax.set_xticklabels(st)
    ax.set_yticks(range(3)); ax.set_yticklabels(st)
    vmax = cov.max()
    for (i, j), v in np.ndenumerate(cov):
        ax.text(j, i, f"{v:.0f}", ha="center", va="center", fontsize=6.6,
                color="white" if v > 0.62 * vmax else PAL["n_black"])
    ax.set_frame_on(False)
    cb = fig.colorbar(im, ax=ax, fraction=0.046, pad=0.04)
    cb.set_label("Cov (ns²)", fontsize=6.2)
    cb.ax.tick_params(labelsize=5.8)
    ax.set_title(f"a   Measured 3×3 inter-stave covariance (A>1000, n={p['n_events']:,})",
                 loc="left", fontsize=7.1)

    # Panel b: per-stave σ68 with CIs + combined vs withdrawn
    labels = st + ["Combined\n(indep. completion)"]
    y = np.arange(len(labels))[::-1]
    sig = [p["per_stave_sigma_ns"][s] for s in st] + [comb]
    ci = [p["per_stave_sigma_ci"][s] for s in st] + [comb_ci]
    cols = [PAL["blue_secondary"]] * 3 + [PAL["blue_main"]]
    for yi, s, c, col in zip(y, sig, ci, cols):
        ax2.plot([c[0], c[1]], [yi, yi], color=col, lw=1.4)
        ax2.plot(s, yi, "o", color=col, markersize=6,
                 markeredgecolor="black", markeredgewidth=0.4)
        ax2.text(c[1] + 0.03, yi, f"{s:.2f} [{c[0]:.2f}, {c[1]:.2f}]",
                 va="center", fontsize=6.0, color=PAL["n_black"])
    # withdrawn 0.54–0.56 band, struck (shown as a retracted row below Combined)
    ax2.axvspan(withdrawn[0], withdrawn[1], color=PAL["red_down"], alpha=0.10)
    ywd = y[-1] - 0.55
    ax2.plot([withdrawn[0], withdrawn[1]], [ywd, ywd], color=PAL["red_down"], lw=1.0)
    ax2.plot(np.mean(withdrawn), ywd, "x", color=PAL["red_down"],
             markersize=6, markeredgewidth=1.3)
    ax2.text(withdrawn[1] + 0.06, ywd,
             f"withdrawn {withdrawn[0]:.2f}–{withdrawn[1]:.2f} ns (retracted)",
             fontsize=5.8, color=PAL["red_down"], ha="left", va="center")
    ax2.set_yticks(y)
    ax2.set_yticklabels(labels, fontsize=6.2)
    ax2.set_xlim(0, 1.9)
    ax2.set_ylim(y[-1] - 1.75, y[0] + 0.6)
    ax2.set_xlabel("Timing σ₆₈ (ns)")
    ax2.text(0.02, y[-1] - 1.05,
             f"independence not rejected (off-diagonal-equality p = {pval:.2f});\n"
             "single-partition — held-out confirmation BLOCKED (reserved runs unstaged)",
             fontsize=5.6, color=PAL["n_dark"], va="top")
    ax2.set_title("b   Combined σ₆₈ = 0.490 ns [0.470, 0.508] (correlation-aware)",
                  loc="left", fontsize=7.1)

    fig.suptitle("S25 (B-M4) — a properly measured combined inter-stave timing σ₆₈ (0.490 ns), "
                 "replacing the withdrawn 0.54–0.56; error bars = 95% bootstrap CI (400 replicas)",
                 fontsize=7.0, y=1.03)
    return save_pub(fig, "35_covariance_timing")


# ══════════════════════════════════════════════════════════════════════════
# Fig 36 — The traditional-fit two-pulse verdict is robust: it wins at matched
#   80% coverage across pinned / +phase-jitter / +cross-stave realism configs.
#   Archetype: quantitative grid (failure@80% bars + Δt σ68 bars, three configs).
#   Source: reports/s26_overlay_realism_1783241582/s26_summary.json.
# ══════════════════════════════════════════════════════════════════════════
def fig36_overlay_realism():
    s26 = load("s26")
    order = ["pinned_same", "jitter_same", "jitter_cross"]
    nice = {"pinned_same": "pinned\n(single-stave)",
            "jitter_same": "+ phase\njitter",
            "jitter_cross": "+ cross-stave\noverlay"}
    res = s26["results"]

    def mean_sigma(cfg, key):
        rows = res[cfg]["benchmark"]["common_subset"]
        return float(np.mean([r[key] for r in rows]))

    trad_fail = [res[c]["verdict"]["trad_mean_failure"] for c in order]  # all 0
    ml_fail = [res[c]["verdict"]["ml_mean_failure"] for c in order]
    trad_sig = [mean_sigma(c, "sigma68_trad_ns") for c in order]
    ml_sig = [mean_sigma(c, "sigma68_ml_ns") for c in order]

    fig, (ax, ax2) = plt.subplots(1, 2, figsize=(7.2, 3.1),
                                  gridspec_kw={"wspace": 0.36})
    x = np.arange(len(order))
    w = 0.36

    # Panel a: failure @ matched 80% coverage (trad vs ML)
    ax.bar(x - w / 2, trad_fail, w, color=PAL["blue_main"], edgecolor="black",
           linewidth=0.5, label="Template fit (traditional)")
    ax.bar(x + w / 2, ml_fail, w, color=PAL["red_strong"], edgecolor="black",
           linewidth=0.5, label="Compact ML")
    for xi, t, m in zip(x, trad_fail, ml_fail):
        ax.text(xi - w / 2, 4e-5, f"{t:.4f}", ha="center", fontsize=5.6,
                rotation=90, va="bottom", color=PAL["n_dark"])
        ax.text(xi + w / 2, m + 4e-5, f"{m:.4f}", ha="center", fontsize=5.6,
                rotation=90, va="bottom", color=PAL["n_dark"])
    ax.set_xticks(x); ax.set_xticklabels([nice[c] for c in order], fontsize=6.0)
    ax.set_ylabel("Failure rate @ matched 80% coverage")
    ax.set_ylim(0, 0.00145)
    ax.legend(loc="upper left", fontsize=5.8)
    ax.set_title("a   Trad = 0.0000 in all three configs (wins)",
                 loc="left", fontsize=7.3)

    # Panel b: common-subset Δt σ68 (trad vs ML), mean over rates
    ax2.bar(x - w / 2, trad_sig, w, color=PAL["blue_main"], edgecolor="black",
            linewidth=0.5, label="Template fit")
    ax2.bar(x + w / 2, ml_sig, w, color=PAL["red_strong"], edgecolor="black",
            linewidth=0.5, label="Compact ML")
    for xi, t, m in zip(x, trad_sig, ml_sig):
        ax2.text(xi - w / 2, t + 0.03, f"{t:.2f}", ha="center", fontsize=6.0)
        ax2.text(xi + w / 2, m + 0.03, f"{m:.2f}", ha="center", fontsize=6.0)
    ax2.set_xticks(x); ax2.set_xticklabels([nice[c] for c in order], fontsize=6.0)
    ax2.set_ylabel("Common-subset Δt σ₆₈ (ns)")
    ax2.set_ylim(0, 1.7)
    ax2.legend(loc="upper left", fontsize=5.8)
    ax2.set_title("b   Trad σ₆₈ 0.33–0.41 vs ML 1.07–1.47 ns",
                  loc="left", fontsize=7.3)
    fig.suptitle("S26 (B-M7) — the traditional two-pulse verdict is STABLE across phase-jitter and "
                 "cross-stave realism (30,000 overlays/config × 3 rates; CIs in the report)",
                 fontsize=7.0, y=1.03)
    return save_pub(fig, "36_overlay_realism")


# ══════════════════════════════════════════════════════════════════════════
# Fig 37 — The early-peak class (3.41% of A>1000) leakage footprint per headline
#   observable: timing +0.058 ns, τ_eff −13.2 ns, pile-up/area −1.2%.
#   Archetype: quantitative grid (per-observable forest of fractional shifts).
#   Source: reports/s27_earlypeak_budget_1783241582/s27_summary.json.
# ══════════════════════════════════════════════════════════════════════════
def fig37_earlypeak_budget():
    s27 = load("s27")
    tm = s27["timing"]
    te = s27["tau_eff"]
    pc = s27["pileup_current"]["overall"]
    count_share = pc["early_count_fraction"] * 100.0   # 3.41 %
    area_share = pc["early_area_fraction"] * 100.0      # -1.25 %

    # fractional shift (%) when the early-peak class is EXCLUDED, per observable
    tim_base = tm["sigma68_early_excluded_ns"]
    tim_rel = tm["shift_ns"] / tim_base * 100.0                    # +3.5 %
    tim_rel_ci = [tm["shift_ci_ns"][0] / tim_base * 100.0,
                  tm["shift_ci_ns"][1] / tim_base * 100.0]
    tau_base = te["tau_eff_early_excluded_ns"]
    tau_rel = te["shift_ns"] / tau_base * 100.0                    # -9.1 %

    rows = [
        ("Downstream pair σ₆₈", tim_rel, tim_rel_ci,
         f"+{tm['shift_ns']:.3f} ns  [+{tm['shift_ci_ns'][0]:.3f}, +{tm['shift_ci_ns'][1]:.3f}]"),
        ("live10 τ_eff", tau_rel, None,
         f"{te['shift_ns']:.1f} ns  (131.6 with → 144.9 excl.)"),
        ("Integrated pulse area", area_share, None,
         f"{area_share:.2f}% of area  ({count_share:.2f}% of counts)"),
    ]

    fig, ax = plt.subplots(figsize=(6.2, 3.1))
    y = np.arange(len(rows))[::-1]
    for yi, (name, rel, ci, lab) in zip(y, rows):
        col = PAL["blue_main"]
        ax.barh(yi, rel, 0.52, color=col, edgecolor="black", linewidth=0.5)
        if ci is not None:
            ax.plot(ci, [yi, yi], color=PAL["n_black"], lw=1.1)
            ax.plot([ci[0], ci[0]], [yi - 0.08, yi + 0.08], color=PAL["n_black"], lw=1.1)
            ax.plot([ci[1], ci[1]], [yi - 0.08, yi + 0.08], color=PAL["n_black"], lw=1.1)
        ha = "left" if rel >= 0 else "right"
        off = 0.4 if rel >= 0 else -0.4
        ax.text(rel + off, yi + 0.30, lab, va="center", ha=ha, fontsize=6.0,
                color=PAL["n_black"])
    ax.axvline(0, color=PAL["n_mid"], lw=1.0)
    ax.set_yticks(y)
    ax.set_yticklabels([r[0] for r in rows], fontsize=6.6)
    ax.set_xlim(-12, 8)
    ax.set_xlabel("Fractional shift when the early-peak class is excluded (%)")
    ax.text(-11.5, y[1] - 0.46,
            "τ_eff shift (−13.2 ns) is OPPOSITE in sign to the MC–data +8% τ_eff offset\n"
            "(so the class cannot explain that offset)",
            fontsize=5.7, color=PAL["red_strong"], va="top")
    ax.set_title(f"S27 (B-M8) — early-peak class = {count_share:.2f}% of A>1000 pulses "
                 f"(n = {tm['n_pairs']:,} pairs); its per-observable leakage bound\n"
                 "error bar (timing) = 95% bootstrap CI; τ_eff / area are point shifts",
                 loc="left", fontsize=6.9)
    return save_pub(fig, "37_earlypeak_budget")


# ══════════════════════════════════════════════════════════════════════════
# Fig 12 (REBUILT 2026-07-05) — the "missing material" root cause is FALSIFIED;
#   the two-arm trigger is the established mechanism (see Fig 33/25). Filename
#   kept so legacy links resolve; content corrected — no retracted claim remains.
#   Archetype: quantitative grid (profile bars + corrected root-cause card).
#   Source: reports/mv3_v5_realtrigger_1783242005/mv3v5_grid.json.
# ══════════════════════════════════════════════════════════════════════════
def fig12_stopping_depth_rebuilt():
    d = load("mv3v5")
    untrig = _v5("track", "filtered", "none", 92.0)["fractions"]
    dsi = d["data"]["sample_i"]["fractions"]
    real = _v5("event", "inclusive", "real_coinc", 92.0)["fractions"]

    fig, (ax, ax2) = plt.subplots(1, 2, figsize=(7.2, 3.2),
                                  gridspec_kw={"width_ratios": [1.15, 1.0],
                                               "wspace": 0.30})
    x = np.arange(len(STAVES))
    w = 0.26
    for k, (name, frac, col) in enumerate([
            ("Untriggered MC", untrig, PAL["red_strong"]),
            ("Real Trig_bar trigger", real, PAL["blue_main"]),
            ("Data (Sample I)", dsi, PAL["n_black"])]):
        ax.bar(x + (k - 1) * w, [frac[s] for s in STAVES], w, label=name,
               color=col, edgecolor="black", linewidth=0.5)
    ax.set_yscale("log")
    ax.set_ylim(5e-4, 1.6)
    ax.set_xticks(x); ax.set_xticklabels(STAVES)
    ax.set_xlabel("B-arm stave (increasing depth →)")
    ax.set_ylabel("Fraction of selected pulses")
    ax.legend(loc="upper right", fontsize=5.8)
    ax.set_title("a   Stopping-depth profile (real-trigger corrected)",
                 loc="left", fontsize=7.4)

    # Panel b: corrected root-cause card (no missing-material claim)
    ax2.axis("off"); ax2.set_xlim(0, 1); ax2.set_ylim(0, 1)
    ax2.text(0.0, 0.98, "Root cause — CORRECTED", fontsize=7.6,
             fontweight="bold", va="top", color=PAL["blue_main"])
    ax2.add_patch(mpatches.FancyBboxPatch(
        (0.0, 0.06), 1.0, 0.82, boxstyle="round,pad=0.02",
        facecolor=PAL["blue_soft"], alpha=0.18, edgecolor=PAL["blue_main"],
        lw=0.9, transform=ax2.transAxes))
    ax2.text(0.5, 0.74,
             "Mechanism: the two-arm coincidence TRIGGER\n"
             "(established by a real Trig_bar GEANT4 simulation)",
             ha="center", va="center", fontsize=6.4, color=PAL["n_black"])
    ax2.text(0.5, 0.50,
             "'Missing ~8–10 g/cm² of material' is FALSIFIED:\n"
             "≤ 0.8 g/cm² exists vs ≥ 10.5 g/cm² required (×13).",
             ha="center", va="center", fontsize=6.2, color=PAL["red_strong"])
    ax2.text(0.5, 0.26,
             "Untriggered B2 45.9% → real-trigger 99.7%\n"
             "(over-purifies vs data 93.3%; closure open).\n"
             "See Fig 33 (hero) / Fig 25.",
             ha="center", va="center", fontsize=6.2, color=PAL["n_dark"])
    ax2.set_title("b   Not missing material — the trigger", loc="left", fontsize=7.4)
    fig.suptitle("MV3 stopping-depth 'failure' re-graded to TENSION — the trigger, not missing material, "
                 "is the mechanism (real Trig_bar simulation)",
                 fontsize=7.0, y=1.02)
    return save_pub(fig, "12_stopping_depth_failure")


# ══════════════════════════════════════════════════════════════════════════
# Fig 38 — reconcile the two deuteron-enrichment headline ratios that look
#   inconsistent (S21 truth species-fraction ratio 1.519 vs S23 data amplitude-
#   tail ratio 3.45). They measure DIFFERENT observables; the double ratio
#   (data I/II)/(MC I/II) = 0.738 [0.733,0.742], z=−99, is the reconciled cross-
#   check, with the B-M6 run-set/beam-drift confound bounded ≤~29% (central ~3%).
#   Archetype: quantitative grid (two per-stave ratio panels + reconciliation card).
#   Source: reports/s21_.../s21_summary.json (key_table inclusive ratios),
#           reports/s23_.../s23_summary.json (high_frac_b2, occupancy DR),
#           reports/bm6_.../bm6_summary.json (linear-drift central; 29% prose).
# ══════════════════════════════════════════════════════════════════════════
def fig38_enrichment_reconciliation():
    s21 = load("s21")["key_table"]["staves"]
    s23 = load("s23")
    bm6 = load("bm6")

    # Left: S21 truth species-fraction ratio f_d(I)/f_d(II), inclusive, per stave
    s21r = {s: s21[s]["enrichment_I_over_II_inclusive"] for s in STAVES}
    # Right: S23 data amplitude-tail ratio f(A>5000)_I / f(A>5000)_II  (B2 only
    # has the headline; ratio_data = [central, lo, hi])
    b2_tail = s23["double_ratio"]["high_frac_b2"]["ratio_data"]  # [3.452,3.407,3.498]
    # Reconciliation: the B2 double ratio (data I/II)/(MC I/II) — occupancy
    dr = s23["double_ratio"]["occupancy"]["B2"]                  # 0.738, z=-99
    # B-M6 drift: central linear-drift attributable fraction of the gap
    drift_central = abs(bm6["linear_drift_model"]["drift_attributable_fraction_of_gap"])  # 0.031
    drift_band = 0.29  # conservative 1-SD bound; REPORT.md prose (1 SD / 3.5x gap)
    r_ci_runcluster = bm6["run_clustered_ratio"]["R_ci95_runcluster"]  # [2.52,4.64]

    fig = plt.figure(figsize=(7.4, 3.5))
    gs = fig.add_gridspec(1, 3, width_ratios=[1.15, 1.0, 1.05], wspace=0.42)
    axL = fig.add_subplot(gs[0])
    axR = fig.add_subplot(gs[1])
    axC = fig.add_subplot(gs[2])

    # Panel a: S21 truth species-fraction ratio per stave
    x = np.arange(len(STAVES))
    vals = [s21r[s]["ratio"] for s in STAVES]
    lo = [s21r[s]["ci_low"] for s in STAVES]
    hi = [s21r[s]["ci_high"] for s in STAVES]
    axL.bar(x, vals, 0.62, color=PAL["blue_main"], edgecolor="black", linewidth=0.5,
            yerr=[np.array(vals) - lo, np.array(hi) - vals], capsize=2.5,
            error_kw=dict(ecolor="black", lw=0.8))
    axL.axhline(1.0, color=PAL["n_mid"], ls="--", lw=0.9)
    for xi, v in zip(x, vals):
        axL.text(xi, v + 0.05, f"{v:.3f}", ha="center", fontsize=6.2,
                 color=PAL["n_black"])
    axL.set_xticks(x); axL.set_xticklabels(STAVES)
    axL.set_ylabel("MC truth deuteron-fraction ratio  f_d(I) / f_d(II)")
    axL.set_ylim(0, 1.75)
    axL.set_title("a   S21 truth species-fraction ratio\n(B2 1.519; falls with depth)",
                  loc="left", fontsize=7.2)

    # Panel b: S23 data amplitude-tail ratio f(A>5000) I/II — B2 headline
    axR.bar([0], [b2_tail[0]], 0.5, color=PAL["teal"], edgecolor="black",
            linewidth=0.5,
            yerr=[[b2_tail[0] - b2_tail[1]], [b2_tail[2] - b2_tail[0]]],
            capsize=3.0, error_kw=dict(ecolor="black", lw=0.9))
    axR.axhline(1.0, color=PAL["n_mid"], ls="--", lw=0.9)
    axR.text(0, b2_tail[0] + 0.12, f"{b2_tail[0]:.2f}\n[{b2_tail[1]:.2f}, {b2_tail[2]:.2f}]",
             ha="center", fontsize=6.4, color=PAL["n_black"])
    axR.set_xticks([0]); axR.set_xticklabels(["B2"])
    axR.set_xlim(-0.9, 0.9)
    axR.set_ylabel("Data amplitude-tail ratio  f(A>5000)_I / f(A>5000)_II")
    axR.set_ylim(0, 4.1)
    axR.set_title("b   S23 data amplitude-tail ratio\n(B2 3.45 — a DIFFERENT observable)",
                  loc="left", fontsize=7.2)

    # Panel c: reconciliation card — double ratio + drift bound
    axC.axis("off"); axC.set_xlim(0, 1); axC.set_ylim(0, 1)
    axC.text(0.0, 0.99, "Reconciliation", fontsize=7.8, fontweight="bold",
             va="top", color=PAL["blue_main"])
    axC.add_patch(mpatches.FancyBboxPatch(
        (0.0, 0.50), 1.0, 0.42, boxstyle="round,pad=0.02",
        facecolor=PAL["blue_soft"], alpha=0.18, edgecolor=PAL["blue_main"],
        lw=0.9, transform=axC.transAxes))
    axC.text(0.5, 0.855, "3.45  ≠  1.519  because they are\n"
             "DIFFERENT observables:\namplitude-tail (data)  vs  species-fraction (MC truth)",
             ha="center", va="top", fontsize=6.0, color=PAL["n_black"])
    axC.text(0.5, 0.605,
             f"gain/geometry-robust cross-check:\ndouble ratio (data I/II)/(MC I/II)\n"
             f"= {dr['dr']:.3f} [{dr['dr_lo']:.3f}, {dr['dr_hi']:.3f}],  z = {dr['z_vs_1']:.0f}",
             ha="center", va="top", fontsize=6.0, color=PAL["blue_main"])
    axC.add_patch(mpatches.FancyBboxPatch(
        (0.0, 0.06), 1.0, 0.36, boxstyle="round,pad=0.02",
        facecolor=PAL["n_light"], alpha=0.35, edgecolor=PAL["n_mid"],
        lw=0.8, transform=axC.transAxes))
    axC.text(0.5, 0.385, "B-M6 run-set / beam-drift confound", ha="center",
             va="top", fontsize=6.2, fontweight="bold", color=PAL["n_dark"])
    axC.text(0.5, 0.265,
             f"bounded ≤ ~{drift_band*100:.0f}% of the effect\n"
             f"(conservative 1-SD; central ~{drift_central*100:.0f}%);\n"
             f"run-clustered R CI [{r_ci_runcluster[0]:.1f}, {r_ci_runcluster[1]:.1f}] excludes 1",
             ha="center", va="top", fontsize=5.8, color=PAL["n_dark"])
    axC.text(0.5, -0.03, "≤29% & central 3%: bm6 REPORT.md prose / linear_drift_model",
             ha="center", va="top", fontsize=5.0, color=PAL["n_mid"],
             style="italic")

    fig.suptitle("Deuteron-enrichment reconciliation — the S23 amplitude-tail ratio (3.45) and the S21 "
                 "species-fraction ratio (1.519) measure DIFFERENT observables;\nthe MC-anchored double ratio "
                 "0.738 (z=−99) is the reconciled cross-check, run-set drift bounded ≤~29%  "
                 "(error bars: 95% bootstrap CI)",
                 fontsize=6.9, y=1.08)
    return save_pub(fig, "38_enrichment_reconciliation")


# ══════════════════════════════════════════════════════════════════════════
# Fig 39 — NEW-04 budget of the 6.4-pt MC-vs-data trigger over-purification
#   residual: accidentals ~2.0 + paddle fidelity ~1.5 + ~2.9 unexplained (no
#   forced closure), with a ±2 pt B-M6 run-set band and the S10 data anchor
#   +1.03 pt [0.64,1.42] overlaid.
#   Archetype: waterfall / stacked contribution bars with ranges.
#   Source: reports/new04_trigger_residual_1783275727/new04_summary.json.
# ══════════════════════════════════════════════════════════════════════════
def fig39_new04_residual_waterfall():
    n04 = load("new04")
    bp = n04["budget_points"]
    total = bp["total"]                                  # 6.4
    acc_c, acc_r = bp["accidentals_central"], bp["accidentals_range"]      # 2.0 [1.3,2.6]
    pad_c, pad_r = bp["paddle_fidelity_central"], bp["paddle_fidelity_range"]  # 1.5 [0.5,3.0]
    unx_c, unx_r = bp["unexplained_central"], bp["unexplained_range"]      # 2.9 [0.0,4.0]
    anchor = n04["data_anchor_S10"]                      # 1.03 [0.64,1.42]
    an_c = anchor["current_excess_pts"]
    an_ci = anchor["current_excess_CI"]

    # waterfall stacking of the three contributions up to the 6.4-pt total
    comps = [
        ("Accidentals", acc_c, acc_r, PAL["blue_main"], "first-\nprinciples;\nR_max-\nbounded"),
        ("Paddle / selection\nfidelity", pad_c, pad_r, PAL["blue_secondary"],
         "deep-p\nA-fire\n>0.06%\ntruth"),
        ("Unexplained\n(no forced closure)", unx_c, unx_r, PAL["n_mid"],
         "genuinely open"),
    ]

    fig, ax = plt.subplots(figsize=(7.0, 3.6))
    # total reference bar
    ax.bar([-0.8], [total], 0.55, color=PAL["n_light"], edgecolor="black",
           linewidth=0.6, zorder=1)
    ax.text(-0.8, total + 0.12, f"{total:.1f} pt\ntotal", ha="center",
            fontsize=6.4, color=PAL["n_black"], fontweight="bold")
    # stacked waterfall
    base = 0.0
    x = np.arange(len(comps))
    for xi, (name, c, r, col, note) in zip(x, comps):
        ax.bar(xi, c, 0.55, bottom=base, color=col, edgecolor="black",
               linewidth=0.5, zorder=2)
        # range as an error bar on the cumulative top
        top = base + c
        ax.plot([xi, xi], [base + r[0], base + r[1]], color=PAL["n_black"],
                lw=1.1, zorder=3)
        for yy in (base + r[0], base + r[1]):
            ax.plot([xi - 0.08, xi + 0.08], [yy, yy], color=PAL["n_black"],
                    lw=1.1, zorder=3)
        ax.text(xi, top + 0.10, f"{c:.1f} pt\n[{r[0]:.1f}, {r[1]:.1f}]",
                ha="center", fontsize=6.0, color=PAL["n_black"])
        ax.text(xi, base + c / 2, note, ha="center", va="center", fontsize=5.4,
                color="white" if col != PAL["n_mid"] else PAL["n_black"])
        # connector to next
        if xi < len(comps) - 1:
            ax.plot([xi + 0.275, xi + 1 - 0.275], [top, top], color=PAL["n_mid"],
                    ls=":", lw=0.8, zorder=1)
        base = top

    # B-M6 run-set ±2 pt systematic band around the total
    ax.axhspan(total - 2, total + 2, color=PAL["gold"], alpha=0.10, zorder=0)
    ax.text(-1.32, total + 1.7, "B-M6 run-set\nband ±2 pt", fontsize=5.6,
            color=PAL["gold"], ha="left", va="center")

    # S10 data anchor +1.03 [0.64,1.42] overlaid
    ax.errorbar([3.05], [an_c], yerr=[[an_c - an_ci[0]], [an_ci[1] - an_c]],
                fmt="D", color=PAL["green_up"], markersize=6, capsize=3.0, lw=1.1,
                zorder=4)
    ax.text(3.05, an_c + 1.55, f"S10 data anchor\n+{an_c:.2f} pt\n[{an_ci[0]:.2f}, {an_ci[1]:.2f}]",
            ha="center", fontsize=5.8, color=PAL["green_up"])
    ax.annotate("independent DATA\ncurrent-excess evidence\n(brackets accidentals)",
                xy=(3.05, an_c), xytext=(2.35, 0.4), fontsize=5.5,
                color=PAL["green_up"], ha="center", va="center",
                arrowprops=dict(arrowstyle="->", color=PAL["green_up"], lw=0.7))

    ax.axhline(total, color=PAL["n_dark"], ls="--", lw=0.8, zorder=0)
    ax.set_xticks(list(x) + [-0.8])
    ax.set_xticklabels([c[0] for c in comps] + ["6.4-pt\nresidual"], fontsize=6.0)
    ax.set_ylabel("Contribution to the Sample-I non-B2 residual (percentage points)")
    ax.set_ylim(0, 8.9)
    ax.set_xlim(-1.4, 3.6)
    ax.set_title("NEW-04 — the 6.4-pt MC-vs-data trigger over-purification residual is only PARTLY explained; "
                 "~2.9 pt remain unexplained (no forced closure)\n"
                 "MC ideal 0.3% vs data 6.7% Sample-I non-B2; ranges are first-principles bounds, "
                 "S10 anchor error bar = 95% CI",
                 loc="left", fontsize=6.6)
    return save_pub(fig, "39_new04_residual_waterfall")


# ══════════════════════════════════════════════════════════════════════════
# Fig 40 — basis-explicit MV3 stopping-depth closure: the untriggered B2
#   "stopping" fraction quoted on THREE selection bases (event 45.9% / track
#   46.9% / track-inclusive 47.2%) → real Trig_bar 99.7% → data Sample I 93.3%.
#   Fixes a basis-mix where 45.9% (event) was quoted next to a track-basis χ².
#   Archetype: quantitative grid (basis-labelled ladder of bars).
#   Source: reports/mv3_v5_realtrigger_1783242005/mv3v5_grid.json.
# ══════════════════════════════════════════════════════════════════════════
def fig40_mv3_closure_basis():
    d = load("mv3v5")
    ev = _v5("event", "filtered", "none", 92.0)["fractions"]["B2"]     # 0.4589
    tr = _v5("track", "filtered", "none", 92.0)["fractions"]["B2"]     # 0.4685
    tri = _v5("track", "inclusive", "none", 92.0)["fractions"]["B2"]   # 0.4719
    real = _v5("event", "inclusive", "real_coinc", 92.0)["fractions"]["B2"]  # 0.9974
    data_si = d["data"]["sample_i"]["fractions"]["B2"]                 # 0.9326

    bars = [
        ("Untriggered MC\n(event basis)", ev, PAL["red_strong"], "event"),
        ("Untriggered MC\n(track basis)", tr, PAL["red_strong"], "track"),
        ("Untriggered MC\n(track, inclusive)", tri, PAL["red_strong"], "track incl"),
        ("Real Trig_bar\ncoincidence (event)", real, PAL["blue_main"], ""),
        ("Data Sample I", data_si, PAL["n_black"], ""),
    ]
    fig, ax = plt.subplots(figsize=(7.2, 3.5))
    x = np.arange(len(bars))
    for xi, (lab, v, col, basis) in zip(x, bars):
        ax.bar(xi, v * 100, 0.62, color=col, edgecolor="black", linewidth=0.5)
        ax.text(xi, v * 100 + 1.4, f"{v*100:.1f}%", ha="center", fontsize=6.6,
                fontweight="bold", color=PAL["n_black"])
        if basis:  # label the selection BASIS on each untriggered bar
            ax.text(xi, v * 100 / 2, f"basis:\n{basis}", ha="center", va="center",
                    fontsize=5.8, color="white")
    # data reference line
    ax.axhline(data_si * 100, color=PAL["n_black"], ls="--", lw=0.9, zorder=0)
    ax.set_xticks(x)
    ax.set_xticklabels([b[0] for b in bars], fontsize=6.0)
    ax.set_ylabel("B2 (shallowest stave) 'stopping' fraction of the B-arm sample (%)")
    ax.set_ylim(0, 118)
    # over-purification annotation (empty upper-middle region)
    ax.annotate("real trigger over-purifies\npast the data\n(99.7% > 93.3%)",
                xy=(3, real * 100), xytext=(2.05, 88), fontsize=6.0,
                color=PAL["blue_main"], ha="center", va="center",
                arrowprops=dict(arrowstyle="->", color=PAL["blue_main"], lw=0.8))
    ax.text(1.5, 63,
            "basis-mix fixed:\n45.9% is the EVENT basis;\na track-basis χ²\nmust use 46.9 / 47.2%",
            fontsize=5.8, color=PAL["red_strong"], ha="center", va="center")
    ax.set_xlim(-0.7, 4.7)
    ax.set_title("MV3 stopping-depth closure, basis-explicit — untriggered B2 (event 45.9% / track 46.9% / "
                 "track-incl 47.2%)\n→ real trigger 99.7% → data 93.3%",
                 loc="left", fontsize=7.0)
    fig.text(0.5, -0.02, "proxy χ² ≈ 625 retired (event/track basis-mix); closure judged on the B2 "
             "fraction, not χ²    [source: reports/mv3_v5_realtrigger_1783242005/mv3v5_grid.json]",
             ha="center", fontsize=5.2, color=PAL["n_mid"], style="italic")
    return save_pub(fig, "40_mv3_closure_basis")


# ══════════════════════════════════════════════════════════════════════════
# Fig 41 — why is B4's per-stave timing σ68 (1.52 ns) 2.2× worse than B6/B8
#   despite similar amplitude? (a) per-stave σ68 with 95% CI; (b) per-stave
#   median amplitude — B4≈B6 amplitude yet B4 is 2.2× worse ⇒ the excess is
#   INTRINSIC (B4 is the most-upstream downstream stave), not timewalk/amplitude.
#   Archetype: quantitative grid (σ68 forest + amplitude bars).
#   Source: reports/s25_.../s25_summary.json (per_stave_sigma_ns + CIs);
#           per-stave median amplitude computed on the SAME S25 selection
#           (s00 selected-B-pulse table, downstream triples runs 58-63,65,
#           A>1000, n=3,820 — reproduces the S25 n_events exactly).
# ══════════════════════════════════════════════════════════════════════════
def fig41_b4_outlier_diagnostic():
    s25 = load("s25")["primary"]
    st = ["B4", "B6", "B8"]
    sig = {s: s25["per_stave_sigma_ns"][s] for s in st}
    ci = {s: s25["per_stave_sigma_ci"][s] for s in st}
    # per-stave median amplitude on the S25 selection (computed at build time
    # from the s00 selected-B-pulse table; see header — n=3,820 triples each).
    amp_median = {"B4": 2367.8, "B6": 2468.0, "B8": 3344.0}
    amp_src = ("reports/1780917628.449525.085b2dc0__s01b_s00_selected_table_manifest/"
               "s00_selected_b_pulses.csv.gz")

    fig, (ax, ax2) = plt.subplots(1, 2, figsize=(7.2, 3.3),
                                  gridspec_kw={"wspace": 0.36})
    x = np.arange(len(st))
    scol = {"B4": PAL["red_strong"], "B6": PAL["blue_main"], "B8": PAL["blue_secondary"]}

    # Panel a: per-stave σ68 with 95% CI
    for xi, s in zip(x, st):
        c = ci[s]
        ax.bar(xi, sig[s], 0.6, color=scol[s], edgecolor="black", linewidth=0.5,
               yerr=[[sig[s] - c[0]], [c[1] - sig[s]]], capsize=3.0,
               error_kw=dict(ecolor="black", lw=0.9))
        ax.text(xi, c[1] + 0.05, f"{sig[s]:.2f}\n[{c[0]:.2f}, {c[1]:.2f}]",
                ha="center", fontsize=6.0, color=PAL["n_black"])
    ax.set_xticks(x); ax.set_xticklabels(st)
    ax.set_ylabel("Per-stave timing σ₆₈ (ns)")
    ax.set_ylim(0, 1.85)
    ratio = sig["B4"] / sig["B6"]
    ax.annotate(f"B4 is {ratio:.1f}× worse\nthan B6", xy=(0, sig["B4"]),
                xytext=(1.1, 1.45), fontsize=6.2, color=PAL["red_strong"],
                ha="center", va="center",
                arrowprops=dict(arrowstyle="->", color=PAL["red_strong"], lw=0.8))
    ax.set_title("a   Per-stave timing σ₆₈ (S25; n = 3,820, 95% CI)",
                 loc="left", fontsize=7.2)

    # Panel b: per-stave median amplitude
    for xi, s in zip(x, st):
        ax2.bar(xi, amp_median[s], 0.6, color=scol[s], edgecolor="black",
                linewidth=0.5)
        ax2.text(xi, amp_median[s] + 45, f"{amp_median[s]:.0f}", ha="center",
                 fontsize=6.4, color=PAL["n_black"])
    ax2.set_xticks(x); ax2.set_xticklabels(st)
    ax2.set_ylabel("Per-stave median amplitude (ADC)")
    ax2.set_ylim(0, 3800)
    # B4 ~ B6 amplitude bracket
    ax2.annotate("", xy=(0, amp_median["B4"] + 250), xytext=(1, amp_median["B6"] + 250),
                 arrowprops=dict(arrowstyle="<->", color=PAL["n_mid"], lw=0.9))
    ax2.text(0.5, amp_median["B6"] + 470, "B4 ≈ B6 amplitude\n(within ~4%)",
             ha="center", fontsize=6.0, color=PAL["n_dark"])
    ax2.set_title("b   Per-stave median amplitude (same S25 selection)",
                  loc="left", fontsize=7.2)

    fig.suptitle("B4 timing outlier — B4 and B6 have ~equal amplitude yet B4's σ₆₈ is 2.2× worse: the excess is "
                 "INTRINSIC (B4 is the most-upstream downstream stave, most exposed to the B2/beam topology), "
                 "NOT a timewalk/amplitude effect",
                 fontsize=6.6, y=1.04)
    fig.text(0.5, -0.02, f"amplitude medians computed on {amp_src} (downstream triples, "
             "runs 58-63,65, A>1000; n=3,820 — reproduces S25 n_events)",
             ha="center", fontsize=5.0, color=PAL["n_mid"], style="italic")
    return save_pub(fig, "41_b4_outlier_diagnostic")


# ══════════════════════════════════════════════════════════════════════════
# Fig 42 — the pile-up τ_eff → R_max ladder, killing the retracted 4.22 MHz.
#   Points: data τ_eff estimators (10%-cross 124.79 [123.35,126.31], KM 151.64,
#   IPCW 179.05, retracted note 90 ns struck) + MC03 135.0, each mapped to
#   R_max = 0.380/τ. Annotates the ≤3.05 MHz upper bound and ≈2.1 MHz censoring-aware.
#   Archetype: schematic-led composite (τ estimators + resulting R_max).
#   Source: reports/1781028280.978.1e517fd7/result.json (S10g 10% thresholds),
#           reports/mc03_.../result.json (MC pooled), reports/mv5_.../REPORT.md
#           (retracted 90 ns / 4.22 MHz), new04 R_max_MHz_upper.
# ══════════════════════════════════════════════════════════════════════════
def fig42_taueff_rmax_ladder():
    s10g = load("s10g")["thresholds"]["10pct"]
    mc03 = load("mc03")["tau_eff"]["pooled"]
    n04 = load("new04")
    MU = 0.380
    rmax_upper = n04["inputs"]["R_max_MHz_upper"]   # 3.045

    # (label, tau_ns, ci [lo,hi] or None, colour, struck?)
    est = [
        ("note\n(90 ns)", 90.0, None, PAL["red_down"], True),
        ("10%-cross\n(data)", s10g["template_exponential_cross_ns"],
         [s10g["template_ci95_low_ns"], s10g["template_ci95_high_ns"]],
         PAL["blue_main"], False),
        ("MC03\nlive10", mc03["live10_ns"],
         [mc03["ci_low"], mc03["ci_high"]], PAL["teal"], False),
        ("Kaplan–\nMeier", s10g["km_restricted_mean_ns"],
         [s10g["km_ci95_low_ns"], s10g["km_ci95_high_ns"]], PAL["violet"], False),
        ("IPCW\nAFT", s10g["ml_ipcw_mean_ns"],
         [s10g["ml_ipcw_ci95_low_ns"], s10g["ml_ipcw_ci95_high_ns"]],
         PAL["gold"], False),
    ]

    fig, (ax, ax2) = plt.subplots(1, 2, figsize=(7.4, 3.3),
                                  gridspec_kw={"wspace": 0.30})
    x = np.arange(len(est))

    # Panel a: tau_eff estimators
    for xi, (lab, tau, ci, col, struck) in zip(x, est):
        ax.bar(xi, tau, 0.62, color=col, edgecolor="black", linewidth=0.5,
               hatch="///" if struck else None, alpha=0.5 if struck else 1.0)
        if ci is not None:
            ax.plot([xi, xi], ci, color=PAL["n_black"], lw=1.0)
            for yy in ci:
                ax.plot([xi - 0.08, xi + 0.08], [yy, yy], color=PAL["n_black"], lw=1.0)
        ax.text(xi, tau + 5, f"{tau:.1f}", ha="center", fontsize=6.2,
                color=PAL["n_mid"] if struck else PAL["n_black"])
        if struck:
            ax.plot([xi - 0.31, xi + 0.31], [tau, tau], color=PAL["red_down"], lw=1.4)
    ax.set_xticks(x); ax.set_xticklabels([e[0] for e in est], fontsize=6.0)
    ax.set_ylabel("Effective live-time τ_eff (ns)")
    ax.set_ylim(0, 205)
    ax.text(0, 40, "RETRACTED", ha="center", color=PAL["red_down"], fontsize=6.0,
            rotation=90, fontweight="bold")
    ax.set_title("a   τ_eff estimators (data + MC03; 95% CI)",
                 loc="left", fontsize=7.2)

    # Panel b: R_max = 0.380 / tau
    def rmax(tau):
        return MU / (tau * 1e-9) / 1e6
    for xi, (lab, tau, ci, col, struck) in zip(x, est):
        r = rmax(tau)
        ax2.bar(xi, r, 0.62, color=col, edgecolor="black", linewidth=0.5,
                hatch="///" if struck else None, alpha=0.5 if struck else 1.0)
        if ci is not None:
            rc = [rmax(ci[1]), rmax(ci[0])]  # note inversion
            ax2.plot([xi, xi], rc, color=PAL["n_black"], lw=1.0)
        ax2.text(xi, r + 0.09, f"{r:.2f}", ha="center", fontsize=6.2,
                 color=PAL["n_mid"] if struck else PAL["n_black"])
        if struck:
            ax2.plot([xi - 0.31, xi + 0.31], [r, r], color=PAL["red_down"], lw=1.4)
    ax2.axhline(rmax_upper, color=PAL["blue_main"], ls="--", lw=1.0)
    ax2.text(2.5, rmax_upper + 0.12, f"R_max ≤ {rmax(s10g['template_exponential_cross_ns']):.2f} MHz "
             "(one-sided upper bound)",
             fontsize=5.8, color=PAL["blue_main"], ha="center", va="bottom")
    ax2.axhline(rmax(s10g["ml_ipcw_mean_ns"]), color=PAL["gold"], ls=":", lw=1.0)
    ax2.annotate("≈2.1 MHz\ncensoring-aware", xy=(4, rmax(s10g["ml_ipcw_mean_ns"])),
                 xytext=(2.6, 3.55), fontsize=5.8, color=PAL["gold"], ha="center",
                 va="center", arrowprops=dict(arrowstyle="->", color=PAL["gold"], lw=0.7))
    ax2.set_xticks(x); ax2.set_xticklabels([e[0] for e in est], fontsize=6.0)
    ax2.set_ylabel("R_max = μ_max / τ_eff  (MHz)")
    ax2.set_ylim(0, 4.8)
    ax2.text(0, 0.9, "4.22 MHz RETRACTED", ha="center", color=PAL["red_down"],
             fontsize=5.8, rotation=90, va="bottom", fontweight="bold")
    ax2.set_title("b   R_max = 0.380 / τ_eff  (upper bound, not 4.22 MHz)",
                  loc="left", fontsize=7.2)

    fig.suptitle("Pile-up τ_eff → R_max ladder — the retracted 90 ns / 4.22 MHz is struck; every measured "
                 "estimator gives R_max ≤ 3.05 MHz (≈2.1 MHz censoring-aware)\n"
                 "μ_max = 0.380; τ estimators from S10g (10% threshold) + MC03 pooled",
                 fontsize=6.7, y=1.06)
    return save_pub(fig, "42_taueff_rmax_ladder")


# ══════════════════════════════════════════════════════════════════════════
# Fig 43 — the certified ML-win delta-CI forest with BH-FDR. Forest of the
#   P04/P07 amplitude+charge win deltas (event-clustered CIs + z), all surviving BH.
#   Archetype: quantitative grid (delta-CI forest).
#   Source: reports/bm3_p04p07_fdr_20260705_203249/stats02_delta_ci_summary.json.
# ══════════════════════════════════════════════════════════════════════════
def fig43_fdr_delta_forest():
    wins = load("bm3fdr")["wins"]

    # (short label, delta, ci95, z)  in a readable order
    rows = []
    for grp in ("P04", "P04c", "P04d", "P04e", "P07"):
        for r in wins[grp]:
            comp = r["comparison"]
            if grp == "P04":
                tag = "amp (peak−ML)" if comp.startswith("amp") else "charge (integral−ML)"
                short = f"P04 {tag}"
            elif grp == "P07":
                ceil = comp.split("ceiling=")[1].split(":")[0]
                short = f"P07 sat. ceiling {ceil}"
            else:
                short = {"P04c": "P04c amp (adaptive-ridge−ML)",
                         "P04d": "P04d amp (huber−extratrees)",
                         "P04e": "P04e amp B2-holdout (run-block)"}[grp]
            rows.append((short, r["res68_delta"], r["res68_delta_ci95"],
                         r["z_approx"]))

    fig, ax = plt.subplots(figsize=(7.2, 3.8))
    y = np.arange(len(rows))[::-1]
    for yi, (lab, d, ci, z) in zip(y, rows):
        col = PAL["blue_main"] if "P04" in lab and "P07" not in lab else PAL["teal"]
        ax.plot(ci, [yi, yi], color=col, lw=1.6, zorder=2)
        ax.plot(d, yi, "o", color=col, markersize=6, markeredgecolor="black",
                markeredgewidth=0.4, zorder=3)
        ax.text(ci[1] + 0.004, yi, f"Δ={d:.3f}  z={z:.0f}  ✓BH", va="center",
                fontsize=5.9, color=PAL["n_black"])
    ax.axvline(0.0, color=PAL["red_down"], ls="--", lw=1.0)
    ax.text(0.002, y[0] + 0.5, "Δ = 0 (no win)", color=PAL["red_down"],
            fontsize=5.8, va="bottom")
    ax.set_yticks(y)
    ax.set_yticklabels([r[0] for r in rows], fontsize=6.0)
    ax.set_xlabel("Traditional − ML residual-σ₆₈ advantage  Δ  (larger = traditional wins)")
    ax.set_xlim(-0.02, 0.30)
    ax.set_ylim(y[-1] - 0.7, y[0] + 1.0)
    ax.set_title("B-M3 — the certified traditional-fit wins: every P04/P07 amplitude+charge Δ excludes 0 and "
                 "survives BH-FDR\nevent-clustered 95% CIs (P04e run-block); z from the CI SE; q = 0.05",
                 loc="left", fontsize=6.7)
    return save_pub(fig, "43_fdr_delta_forest")


# ══════════════════════════════════════════════════════════════════════════
# Fig 44 (SUPERSEDES Fig 29) — the REFRESHED program-level FDR census: 1,957
#   claims / 157 studies; BH q=0.05 within family; 14/15 scoreboard bold wins
#   survive, 0 fail, 1 prose-only. (a) sorted-p vs BH-threshold plot;
#   (b) per-family survive/nominal breakdown + scoreboard headline.
#   Archetype: quantitative grid (BH p-value plot + family census bars).
#   Source: reports/stats01_program_fdr_20260705_203905/claims.csv (+ REPORT.md
#           prose for the 14/15 scoreboard headline).
# ══════════════════════════════════════════════════════════════════════════
def fig44_fdr_census_refly():
    rows = list(csv.DictReader(open(os.path.join(REPO, SOURCES["census"]))))
    n_claims = len(rows)
    studies = sorted({r["study_id"] for r in rows})
    # per-family census from the claim rows
    fams = {}
    for r in rows:
        f = r["family"]
        d = fams.setdefault(f, {"n": 0, "nominal": 0, "survive": 0})
        d["n"] += 1
        if r["nominal_ci_excludes_zero"].strip().lower() == "true":
            d["nominal"] += 1
        if r["bh_pass"].strip().lower() == "true":
            d["survive"] += 1
    order = sorted(fams, key=lambda f: fams[f]["nominal"])
    total_nominal = sum(d["nominal"] for d in fams.values())
    total_surv = sum(d["survive"] for d in fams.values())

    # BH p-value plot inputs (sorted p, BH line i/m*q)
    q = 0.05
    ps = np.array(sorted(float(r["p"]) for r in rows if r["p"] not in ("", "nan")))
    m = len(ps)
    idx = np.arange(1, m + 1)
    bh_line = idx / m * q
    # largest i with p(i) <= i/m q  (BH survivor count)
    below = ps <= bh_line
    k = int(np.max(np.where(below)[0]) + 1) if below.any() else 0
    # floor exact zeros / astronomically small p for a readable log axis
    FLOOR = 1e-30
    ps_disp = np.clip(ps, FLOOR, None)

    fig, (ax, ax2) = plt.subplots(1, 2, figsize=(7.4, 3.3),
                                  gridspec_kw={"width_ratios": [1.05, 1.15],
                                               "wspace": 0.40})

    # Panel a: sorted p vs BH threshold (log-y); points below FLOOR sit on the floor
    ax.plot(idx, ps_disp, ".", color=PAL["blue_main"], markersize=2.0,
            label=f"sorted claim p-values (floored at {FLOOR:.0e})", zorder=2)
    ax.plot(idx, bh_line, "-", color=PAL["red_strong"], lw=1.2,
            label=f"BH threshold  i/m·q  (q={q})", zorder=3)
    if k:
        ax.axvline(k, color=PAL["n_mid"], ls=":", lw=0.9, zorder=1)
        ax.annotate(f"k = {k}\nsurvive BH\n(reject H₀ left of here)",
                    xy=(k, q * 0.5), xytext=(k * 0.60, 3e-4),
                    fontsize=5.8, color=PAL["n_dark"], ha="center", va="center",
                    arrowprops=dict(arrowstyle="->", color=PAL["n_mid"], lw=0.7))
    ax.set_yscale("log")
    ax.set_ylim(FLOOR * 0.4, 3.0)
    ax.set_xlim(0, m)
    ax.set_xlabel("Rank i of claim p-value (ascending)")
    ax.set_ylabel("p-value  (floored at 1e−30)")
    ax.legend(loc="lower right", fontsize=5.6)
    ax.set_title(f"a   Global BH view (m = {m:,} claims with p)",
                 loc="left", fontsize=7.1)

    # Panel b: per-family survive/nominal bars + headline card
    y = np.arange(len(order))
    nom = np.array([fams[f]["nominal"] for f in order])
    sur = np.array([fams[f]["survive"] for f in order])
    ax2.barh(y, nom, 0.62, color=PAL["n_light"], edgecolor="black", linewidth=0.5,
             label="Nominal (CI excludes 0)")
    ax2.barh(y, sur, 0.62, color=PAL["blue_main"], edgecolor="black", linewidth=0.5,
             label="Survives BH (q = 0.05)")
    for yi, f in zip(y, order):
        d = fams[f]
        drop = d["nominal"] - d["survive"]
        ax2.text(d["nominal"] + 5, yi, f"{d['survive']}/{d['nominal']}"
                 + (f" (−{drop})" if drop else ""), va="center", fontsize=5.6,
                 color=PAL["n_dark"])
    ax2.set_yticks(y); ax2.set_yticklabels(order, fontsize=6.0)
    ax2.set_xlim(0, max(nom) * 1.28)
    ax2.set_xlabel("Delta-with-CI claims")
    ax2.legend(loc="lower right", fontsize=5.6)
    ax2.set_title("b   Per-family BH census (refreshed)", loc="left", fontsize=7.1)

    fig.suptitle(f"STATS01 program-level FDR census (REFRESHED) — {n_claims:,} delta-CI claims across "
                 f"{len(studies)} studies; {total_surv:,}/{total_nominal:,} nominal survive BH;\n"
                 "of 15 scoreboard bold wins 14 survive BH, 0 fail, 1 prose-only "
                 "(amplitude-charge family 432/471) — SUPERSEDES Fig 29",
                 fontsize=6.6, y=1.06)
    fig.text(0.5, -0.02, "14/15 scoreboard & 1 prose-only headline: "
             "reports/stats01_program_fdr_20260705_203905/REPORT.md prose",
             ha="center", fontsize=5.0, color=PAL["n_mid"], style="italic")
    return save_pub(fig, "44_fdr_census_refly")


def main():
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    print(f"Generating post-review figures into {os.path.relpath(OUTPUT_DIR, REPO)}/ ...")
    all_paths = []
    for fn in (fig25_mv3_hero, fig26_c12, fig27_taueff, fig28_gain, fig29_fdr,
               fig30_riskcov, fig31_s22, fig32_s23, fig09_rmax, fig19_pedestal,
               fig33_realtrigger, fig34_gain_quenched, fig35_covariance,
               fig36_overlay_realism, fig37_earlypeak_budget,
               fig12_stopping_depth_rebuilt,
               fig38_enrichment_reconciliation, fig39_new04_residual_waterfall,
               fig40_mv3_closure_basis, fig41_b4_outlier_diagnostic,
               fig42_taueff_rmax_ladder, fig43_fdr_delta_forest,
               fig44_fdr_census_refly):
        print(f"[{fn.__name__}]")
        all_paths.extend(fn())
    print(f"\nDONE — {len(all_paths)} files written "
          f"({len(all_paths)//3} figures × PNG/SVG/PDF).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
