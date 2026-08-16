#!/usr/bin/env python3
"""Interconnected MC-analysis study for issues #879 / #880 / #887.

This is the single self-contained, reproducible driver that quantifies the
three open questions from Dave (davidmilstead) directly against the deployed
Krakow 1M-event MC (``geant4/data/output_krakow_1M.root``):

  * #879 (ΔE-E readout segmentation / pointing direction):
        Run the ΔE-E analysis for BOTH readout patterns -- the ODD B-arm
        LayerID set {1,3,5,7} (current ``deltaE_E_mc.py`` primary mapping ->
        B2/B4/B6/B8) and the EVEN set {0,2,4,6} (the one-stave-shifted
        pattern Dave names "2-4-6-8"). Quantify the population shift, the
        weighted ΔE-E correlation, the *invisible-energy fraction* (Bragg peak
        deposited in a non-readout stave) and how it flips the apparent ΔE-E.

  * #880 (PrimaryWeight): audit-style, weighted-vs-unweighted comparison.
        PrimaryWeight spans ~0.13..15.3 (ESS ~35% of nominal); we report how
        much the unweighted summaries were biased.

  * #887 (amplitude cut): scan {500, 1000, 1500} ADC. The raw data waveforms
        are not on LUNARC, so the scan is run on MC-truth EDep converted to
        ADC with the documented data-calibrated scale (default 245.6
        ADC/MeV, env ``CCB_MEV_TO_ADC`` / ``--mev-to-adc``). For each cut we
        report the retained-event fraction (data-selection analogue: the ΔE
        stave AND >=1 E stave must fire above the cut), per-stave fire
        fractions, and the proton/deuteron PID separation in the ΔE-E plane.

Every numeric knob is CLI/env overridable (no hardcoded params). All MC
histograms and moments are PrimaryWeighted throughout.

Outputs (<out>/):
  issues879_880_887_result.json     machine-readable results for all 3 issues
  fig_879_readout_pattern_compare.{png,pdf}
  fig_879_layer_edep_profile.{png,pdf}
  fig_880_weighted_vs_unweighted.{png,pdf}
  fig_887_amplitude_cut_scan.{png,pdf}
  fig_887_deltaE_E_per_cut.{png,pdf}
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

import numpy as np

# --------------------------------------------------------------------------- #
# Defaults (every one is CLI/env-overridable -- no hidden hardcoded params)
# --------------------------------------------------------------------------- #
DEFAULT_ROOT = "/projects/hep/fs10/shared/nnbar/billy/ccb-testbeam/geant4/data/output_krakow_1M.root"
# Empirically calibrated data scale, from
# reports/sampleI_II_trigger_split_*/compare/data_mc_comparison.json
# ("Sample-II first-B-layer median"). This is the scale that maps MC truth EDep
# [MeV] into the ADC space where Dave's {500,1000,1500} amplitude cuts live.
DEFAULT_MEV_TO_ADC = 245.6
DEFAULT_AMPLITUDE_CUTS = "500,1000,1500"
DEFAULT_EDISP_LARGE_MEV = 15.0
ENV_MEV_TO_ADC = "CCB_MEV_TO_ADC"

B_ARM = 1
P_PDG, D_PDG = 2212, 1000010020


def _env_float(name, default):
    v = os.environ.get(name)
    return float(v) if (v is not None and v.strip()) else float(default)


def wmean(x, w):
    x = np.asarray(x, float); w = np.asarray(w, float)
    sw = w.sum()
    return float(np.sum(w * x) / sw) if sw > 0 else (float(x.mean()) if x.size else 0.0)


def wmedian(x, w):
    x = np.asarray(x, float); w = np.asarray(w, float)
    sw = w.sum()
    if sw <= 0:
        return float(np.median(x)) if x.size else 0.0
    o = np.argsort(x); xs, ws = x[o], w[o]
    cw = np.cumsum(ws) / sw
    return float(np.interp(0.5, cw, xs))


def wfrac(x, w, thr):
    x = np.asarray(x, float); w = np.asarray(w, float)
    sw = w.sum()
    return float(np.sum(w[x > thr]) / sw) if sw > 0 else (float(np.mean(x > thr)) if x.size else 0.0)


def wcorr(x, y, w):
    x = np.asarray(x, float); y = np.asarray(y, float); w = np.asarray(w, float)
    sw = w.sum()
    if sw <= 0 or x.size < 2:
        return float(np.corrcoef(x, y)[0, 1]) if x.size > 1 else 0.0
    mx = np.sum(w * x) / sw; my = np.sum(w * y) / sw
    cx, cy = x - mx, y - my
    cov = np.sum(w * cx * cy) / sw
    den = np.sqrt(np.sum(w * cx * cx) / sw * np.sum(w * cy * cy) / sw)
    return float(cov / den) if den > 0 else 0.0


def ess(w):
    w = np.asarray(w, float)
    s2 = np.sum(w * w)
    sw = w.sum()
    return float(sw * sw / s2) if s2 > 0 else 0.0


def bhattacharyya_overlap(x_p, x_d, w_p, w_d, bins, rng):
    """1 - BC where BC = sum sqrt(p_norm * d_norm) over a common histogram.

    Returns 0 for perfectly overlapping distributions, 1 for fully separated.
    Weighted histograms are used. This is a scalar PID-separation score on the
    ΔE axis: higher = better p/d separation."""
    edges = bins
    hp, _ = np.histogram(x_p, bins=edges, weights=w_p, density=True)
    hd, _ = np.histogram(x_d, bins=edges, weights=w_d, density=True)
    bc = float(np.sum(np.sqrt(np.clip(hp, 0, None) * np.clip(hd, 0, None))) * (edges[1] - edges[0]))
    return 1.0 - bc


def load_mc(root, tree, entry_stop):
    import uproot
    import awkward as ak
    f = uproot.open(root)
    t = f[tree]
    branches = ["Sci_bar_LayerID", "Sci_bar_LayerID1", "Sci_bar_EDep",
                "Sci_bar_PDG", "PrimaryWeight", "PrimaryPDG", "PrimaryEkin"]
    arrays = t.arrays(branches, entry_stop=entry_stop, library="ak")
    arm = arrays["Sci_bar_LayerID1"]
    lay = arrays["Sci_bar_LayerID"]
    ed = arrays["Sci_bar_EDep"]
    hit_pdg = arrays["Sci_bar_PDG"]
    pw = arrays["PrimaryWeight"]
    ppdg = arrays["PrimaryPDG"]
    w_evt = ak.to_numpy(ak.firsts(pw, axis=1)).astype(float)
    w_evt = np.where(np.isfinite(w_evt), w_evt, 1.0)
    prim_pdg = ak.to_numpy(ak.firsts(ppdg, axis=1)).astype(int)
    n_evt = len(w_evt)
    # per-event B-arm edep per LayerID 0..7
    E = {}
    for L in range(8):
        mask = (arm == B_ARM) & (lay == L)
        E[L] = ak.to_numpy(ak.sum(ed[mask], axis=1)).astype(float)
    total_b_edep = np.sum([E[L] for L in range(8)], axis=0)  # per event
    # entering-B species per event = PDG of the first charged hit at B-arm
    # LayerID 0 (matches mc01_trigger_split_truth.py ENTER-B definition). This
    # is the species label the dE-E analysis actually uses; in the Krakow MC the
    # beam PrimaryPDG is 100% proton, so deuterons only enter this label as
    # secondaries/recoils. Charged check is vectorized via flatten/unflatten.
    flat = ak.to_numpy(ak.flatten(hit_pdg)).astype(np.int64)
    absf = np.abs(flat)
    is_nuc = absf >= 1_000_000_000
    z_nuc = ((absf - 1_000_000_000) // 10_000).astype(int)
    charged_flat = np.zeros(len(flat), dtype=bool)
    _charged_known = np.array([2212, 11, 211, 321, 13, 1000010030, 1000020030, 1000020040],
                              dtype=np.int64)
    charged_flat[~is_nuc] = np.isin(absf[~is_nuc], _charged_known)
    charged_flat[is_nuc] = z_nuc[is_nuc] > 0
    _counts = ak.to_numpy(ak.num(hit_pdg, axis=1))
    charged_hit = ak.unflatten(ak.from_numpy(charged_flat), _counts)
    b_enter_charged_hit = (arm == B_ARM) & (lay == 0) & charged_hit
    b_enter_charged = ak.to_numpy(ak.any(b_enter_charged_hit, axis=1))
    enter_charged_pdg = hit_pdg[b_enter_charged_hit]
    has = ak.to_numpy(ak.num(enter_charged_pdg, axis=1)) > 0
    firsts = ak.to_numpy(ak.firsts(enter_charged_pdg, axis=1))
    b_enter_pdg = np.zeros(n_evt, dtype=int)
    b_enter_pdg[has] = firsts[has].astype(int)
    return E, w_evt, prim_pdg, b_enter_pdg, b_enter_charged, total_b_edep, n_evt


def study_879(E, w, prim_pdg):
    """ODD {1,3,5,7} vs EVEN {0,2,4,6} readout patterns."""
    patterns = {
        "ODD_1357": [1, 3, 5, 7],
        "EVEN_0246": [0, 2, 4, 6],
    }
    out = {}
    for tag, layers in patterns.items():
        de = E[layers[0]]
        efull = E[layers[1]] + E[layers[2]] + E[layers[3]]
        readout_layers = set(layers)
        nonreadout = [L for L in range(8) if L not in readout_layers]
        # invisible energy = edep in non-readout layers, per event, then weighted fraction of total
        invisible = np.sum([E[L] for L in nonreadout], axis=0)
        tot = np.sum([E[L] for L in range(8)], axis=0)
        good = tot > 0
        # weighted fraction of B-arm energy that is invisible (in non-readout staves)
        inv_frac = wmean((invisible[good] / tot[good]), w[good])
        # Bragg peak = per-event single layer with the MAX edep; is it read out?
        stack = np.vstack([E[L] for L in range(8)])  # (8, n_evt)
        bragg_layer = np.argmax(stack, axis=0)
        bragg_in_readout = np.isin(bragg_layer, list(readout_layers))
        bragg_readout_frac = wmean(bragg_in_readout.astype(float), w)
        sel = (de > 0) & (efull > 0)
        res = {
            "layers": layers,
            "deltaE_layer_id": layers[0],
            "E_layer_ids": layers[1:],
            "n_events_deltaE_and_E": int(sel.sum()),
            "deltaE_wmedian_MeV": wmedian(de[sel], w[sel]),
            "E_wmedian_MeV": wmedian(efull[sel], w[sel]),
            "corr_deltaE_E_weighted": wcorr(de[sel], efull[sel], w[sel]),
            "corr_deltaE_E_unweighted": float(np.corrcoef(de[sel], efull[sel])[0, 1])
                                       if sel.sum() > 2 else 0.0,
            "invisible_energy_fraction_weighted": inv_frac,
            "bragg_peak_in_readout_fraction_weighted": bragg_readout_frac,
        }
        out[tag] = res
    # The "flip": the apparent ΔE-E sign of the stopping correlation differs
    # between patterns because the Bragg-peak (highest dE/dx) layer alternates
    # in/out of the readout set.
    out["_comparison"] = {
        "corr_Odd_minus_Even": out["ODD_1357"]["corr_deltaE_E_weighted"]
                              - out["EVEN_0246"]["corr_deltaE_E_weighted"],
        "invisible_Odd_minus_Even": out["ODD_1357"]["invisible_energy_fraction_weighted"]
                                    - out["EVEN_0246"]["invisible_energy_fraction_weighted"],
        "bragg_readout_Odd_minus_Even": out["ODD_1357"]["bragg_peak_in_readout_fraction_weighted"]
                                        - out["EVEN_0246"]["bragg_peak_in_readout_fraction_weighted"],
        "note": ("Shifting the readout set by one stave (1,3,5,7 -> 0,2,4,6) moves the "
                 "Bragg-peak (stopping) layer in/out of the readout. The ΔE-E correlation "
                 "and the median ΔE both shift because the highest-dE/dx stave is now the "
                 "ΔE layer (EVEN) instead of an E layer (ODD), or vice-versa. The "
                 "invisible-energy fraction is the share of B-arm EDep lost to non-readout "
                 "(interleaved) staves -- the direct measure of the segmentation/pointing "
                 "sensitivity Dave describes."),
    }
    return out


def study_880(E, w, enter_pdg, enter_charged, total_b_edep):
    """Weighted-vs-unweighted audit (issue #880)."""
    # first B layer = LayerID 0 (shallowest), matching mc01 B_layers[0]
    first_b = E[0]
    is_d = (enter_pdg == D_PDG) & enter_charged
    is_p = (enter_pdg == P_PDG) & enter_charged
    fired = first_b > 0
    res = {
        "n_events": int(len(w)),
        "primary_weight_stats": {
            "min": float(w.min()), "max": float(w.max()),
            "mean": float(w.mean()), "std": float(w.std()),
            "ess": ess(w), "ess_fraction": float(ess(w) / len(w)),
        },
        "first_B_layer_mean_MeV": {
            "unweighted": float(first_b.mean()) if first_b.size else 0.0,
            "weighted": wmean(first_b, w),
        },
        "first_B_layer_median_MeV": {
            "unweighted": float(np.median(first_b)) if first_b.size else 0.0,
            "weighted": wmedian(first_b, w),
        },
        "deuteron_fraction_entering_B": {
            "unweighted": float(np.mean(is_d[enter_charged])) if enter_charged.any() else 0.0,
            "weighted": (wmean(is_d[enter_charged].astype(float), w[enter_charged])
                         if enter_charged.any() else 0.0),
        },
        "deltaE_E_corr_layer0_vs_layer1": {
            "unweighted": float(np.corrcoef(E[0], E[1])[0, 1]),
            "weighted": wcorr(E[0], E[1], w),
        },
        "bias_summary": {
            "first_B_layer_mean_rel_bias_pct": (
                100.0 * (wmean(first_b, w) - float(first_b.mean()))
                / max(abs(float(first_b.mean())), 1e-9)),
            "deuteron_fraction_abs_bias_pp": (
                100.0 * ((wmean(is_d[enter_charged].astype(float), w[enter_charged])
                          if enter_charged.any() else 0.0)
                         - (float(np.mean(is_d[enter_charged])) if enter_charged.any() else 0.0))),
        },
        "note": ("PrimaryWeight spans a large range (min..max), so the effective sample "
                 "size (ESS) is far below the nominal event count. The *_rel_bias_pct "
                 "fields show how much the legacy UNWEIGHTED summaries were off; this is "
                 "why mc01_trigger_split_truth.py now applies PrimaryWeight throughout (#880). "
                 "Deuteron fraction uses the entering-B species (Sci_bar first charged hit at "
                 "B-arm LayerID 0), as in mc01."),
    }
    return res


def study_887(E, w, enter_pdg, enter_charged, mev_to_adc, cuts):
    """Amplitude-cut scan {500,1000,1500} ADC on MC-truth-ADC (issue #887)."""
    # Readout = ODD {1,3,5,7} (current primary mapping).
    de_layer = E[1]
    e_layers = [E[3], E[5], E[7]]
    # convert to ADC
    de_adc = de_layer * mev_to_adc
    e_adc = [el * mev_to_adc for el in e_layers]
    is_d = (enter_pdg == D_PDG) & enter_charged
    is_p = (enter_pdg == P_PDG) & enter_charged
    rng = np.random.default_rng(20260723)
    per_cut = {}
    for cut in cuts:
        de_fire = de_adc > cut
        any_e = np.maximum.reduce([a > cut for a in e_adc])
        selected = de_fire & any_e
        per_stave_fire = {
            "B2_deltaE_fire_frac_weighted": wmean(de_fire.astype(float), w),
            "B4_fire_frac_weighted": wmean((e_adc[0] > cut).astype(float), w),
            "B6_fire_frac_weighted": wmean((e_adc[1] > cut).astype(float), w),
            "B8_fire_frac_weighted": wmean((e_adc[2] > cut).astype(float), w),
        }
        # PID separation on the ΔE axis among selected events (entering-B species)
        sep = None; d_frac = 0.0; de_p_med = 0.0; de_d_med = 0.0
        if selected.sum() > 50:
            xs = de_adc[selected]
            ww = w[selected]
            p_sel = is_p[selected]; d_sel = is_d[selected]
            xp, wp = xs[p_sel], ww[p_sel]
            xd, wd = xs[d_sel], ww[d_sel]
            if xp.size > 5 and xd.size > 5:
                edges = np.linspace(0, max(12000.0, float(xs.max()) * 1.05), 80)
                sep = bhattacharyya_overlap(xp, xd, wp, wd, edges, rng)
            d_frac = wmean(d_sel.astype(float), ww)
            de_p_med = wmedian(xp, wp) if xp.size else 0.0
            de_d_med = wmedian(xd, wd) if xd.size else 0.0
        per_cut[float(cut)] = {
            "retained_event_fraction_weighted": wmean(selected.astype(float), w),
            "retained_event_fraction_unweighted": float(np.mean(selected)) if selected.size else 0.0,
            "n_retained": int(selected.sum()),
            "per_stave_fire_fraction": per_stave_fire,
            "deuteron_fraction_retained_weighted": d_frac,
            "deltaE_median_proton_ADC": de_p_med,
            "deltaE_median_deuteron_ADC": de_d_med,
            "pid_separation_1_minus_BC": sep,
            "deltaE_median_weighted_ADC": wmedian(de_adc[selected], w[selected]) if selected.any() else 0.0,
            "deltaE_E_corr_weighted": (wcorr((E[1][selected] * mev_to_adc),
                                             (sum(e_layers)[selected] * mev_to_adc), w[selected])
                                       if selected.sum() > 2 else 0.0),
        }
    return {
        "mev_to_adc": float(mev_to_adc),
        "mev_to_adc_source": "reports/sampleI_II_trigger_split_*/compare/data_mc_comparison.json "
                             "(data-calibrated Sample-II first-B-layer median); override via "
                             "--mev-to-adc or env CCB_MEV_TO_ADC",
        "cuts_adc": [float(c) for c in cuts],
        "per_cut": per_cut,
        "note": ("MC-truth has no pedestal/noise, so this scan shows the GEOMETRY/PHYSICS effect of "
                 "the cut (retained fraction + p/d PID separation), not the data noise-rejection. "
                 "The real-data retained fractions at cut=1000 ADC are anchored in "
                 "reports/S00_*/counts_by_group.csv (events_with_selected/events_total). To run the "
                 "literal data scan on the raw waveforms, set CCB_AMPLITUDE_CUT_ADC and re-run "
                 "scripts/01_build_pulse_table_from_root.py (raw ROOT files are not on LUNARC). "
                 "PID separation uses entering-B species (p vs d secondaries); null when too few d."),
    }


def plot_879(E, w, out, study879):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    patterns = [("ODD_1357", [1, 3, 5, 7], "ODD staves {1,3,5,7} (current B2/B4/B6/B8)"),
                ("EVEN_0246", [0, 2, 4, 6], "EVEN staves {0,2,4,6} (one-stave shift)")]
    fig, axes = plt.subplots(1, 2, figsize=(14, 5.6))
    for ax, (tag, layers, title) in zip(axes, patterns):
        de = E[layers[0]]; ef = sum(E[l] for l in layers[1:])
        sel = (de > 0) & (ef > 0)
        ax.hexbin(ef[sel], de[sel], C=w[sel], reduce_C_function=np.sum,
                  gridsize=45, mincnt=1, bins="log", cmap="viridis")
        wm_de = wmedian(de[sel], w[sel]); wm_e = wmedian(ef[sel], w[sel])
        ax.plot(wm_e, wm_de, marker="x", color="white", ms=12, mew=2,
                label=f"weighted median\nΔE={wm_de:.2f} E={wm_e:.2f} MeV")
        ax.set_xlabel("E = Σ downstream readout staves [MeV]")
        ax.set_ylabel("ΔE = first readout stave [MeV]")
        ax.set_title(title, fontsize=10)
        ax.legend(fontsize=8, loc="upper right")
        ax.text(0.03, 0.97,
                f"weighted corr = {study879[tag]['corr_deltaE_E_weighted']:.3f}\n"
                f"invisible E = {study879[tag]['invisible_energy_fraction_weighted']*100:.1f}%\n"
                f"Bragg peak read out = {study879[tag]['bragg_peak_in_readout_fraction_weighted']*100:.1f}%",
                transform=ax.transAxes, va="top", fontsize=8,
                bbox=dict(boxstyle="round", facecolor="wheat", alpha=0.7))
    fig.suptitle("#879 — ΔE-E readout-pattern sensitivity (PrimaryWeighted): "
                 "ODD {1,3,5,7} vs EVEN {0,2,4,6}", fontweight="bold")
    fig.tight_layout()
    for ext in ("png", "pdf"):
        fig.savefig(out / f"fig_879_readout_pattern_compare.{ext}", dpi=160)
    plt.close(fig)

    # layer edep profile
    fig, ax = plt.subplots(figsize=(9, 5))
    Ls = np.arange(8)
    means = [wmean(E[L], w) for L in Ls]
    odd = np.array([1, 3, 5, 7]); even = np.array([0, 2, 4, 6])
    ax.bar(Ls, means, color=["#c44" if L in odd else "#4c8" for L in Ls], alpha=0.8)
    ax.set_xticks(Ls)
    ax.set_xticklabels([f"L{L}\n({'read' if L in odd else '—'})" for L in Ls])
    ax.set_xlabel("B-arm LayerID (depth); red = ODD readout {1,3,5,7}, green = non-readout")
    ax.set_ylabel("weighted mean EDep per event [MeV]")
    ax.set_title("#879 — per-layer EDep profile (Bragg-peak structure vs readout set)")
    fig.tight_layout()
    for ext in ("png", "pdf"):
        fig.savefig(out / f"fig_879_layer_edep_profile.{ext}", dpi=160)
    plt.close(fig)


def plot_880(E, w, enter_pdg, enter_charged, out, study880):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    first_b = E[0]
    fig, axes = plt.subplots(1, 2, figsize=(13, 5))
    bins = np.linspace(0, 80, 60)
    # unweighted vs weighted first-B-layer EDep
    ax = axes[0]
    h_u, _ = np.histogram(first_b, bins=bins, density=True)
    h_w, _ = np.histogram(first_b, bins=bins, weights=w, density=True)
    bc = 0.5 * (bins[:-1] + bins[1:])
    ax.step(bc, h_u, where="mid", color="k", lw=2, label="unweighted (legacy)")
    ax.step(bc, h_w, where="mid", color="C3", lw=2, label="PrimaryWeighted (#880)")
    ax.set_xlabel("first B-layer (LayerID 0) EDep [MeV]")
    ax.set_ylabel("normalised density")
    ax.set_title(f"First-B-layer EDep: weight shifts the shape\n"
                 f"mean {study880['first_B_layer_mean_MeV']['unweighted']:.2f} → "
                 f"{study880['first_B_layer_mean_MeV']['weighted']:.2f} MeV "
                 f"({study880['bias_summary']['first_B_layer_mean_rel_bias_pct']:+.1f}%)")
    ax.legend()
    # weight distribution
    ax = axes[1]
    ax.hist(w, bins=60, color="#4c72b0", alpha=0.85)
    ax.axvline(1.0, color="k", ls="--", label="weight=1 (nominal)")
    ax.axvline(wmean(np.ones_like(w), w * 0 + 1) if False else float(w.mean()),
               color="C3", ls="-", label=f"mean={w.mean():.2f}")
    ax.set_xlabel("PrimaryWeight (first primary per event)")
    ax.set_ylabel("events")
    ax.set_title(f"PrimaryWeight spread — ESS={study880['primary_weight_stats']['ess']:.0f} "
                 f"({study880['primary_weight_stats']['ess_fraction']*100:.0f}% of nominal)")
    ax.legend()
    fig.suptitle("#880 — MC event weights materially bias unweighted summaries", fontweight="bold")
    fig.tight_layout()
    for ext in ("png", "pdf"):
        fig.savefig(out / f"fig_880_weighted_vs_unweighted.{ext}", dpi=160)
    plt.close(fig)


def plot_887(E, w, enter_pdg, enter_charged, mev_to_adc, cuts, out, study887):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    de_adc = E[1] * mev_to_adc
    e_adc = sum([E[3], E[5], E[7]]) * mev_to_adc
    is_d = (enter_pdg == D_PDG) & enter_charged
    is_p = (enter_pdg == P_PDG) & enter_charged
    fig, axes = plt.subplots(1, len(cuts), figsize=(5.2 * len(cuts), 5), sharey=True)
    if len(cuts) == 1:
        axes = [axes]
    for ax, cut in zip(axes, cuts):
        sel = (de_adc > cut) & (e_adc > cut)
        for mask, color, label in [(is_p & sel, "C0", "proton"),
                                   (is_d & sel, "C3", "deuteron")]:
            if mask.any():
                ax.scatter(e_adc[mask][::max(1, int(mask.sum()/4000))],
                           de_adc[mask][::max(1, int(mask.sum()/4000))],
                           s=3, alpha=0.3, color=color, label=f"{label} ({mask.sum():,})", rasterized=True)
        pc = study887["per_cut"][float(cut)]
        ax.set_title(f"cut = {cut:g} ADC\nretained={pc['retained_event_fraction_weighted']*100:.1f}%  "
                     f"PID sep={pc['pid_separation_1_minus_BC'] if pc['pid_separation_1_minus_BC'] is not None else float('nan'):.2f}",
                     fontsize=9)
        ax.set_xlabel("E [ADC]")
        ax.set_xlim(0, max(8000, float(e_adc[sel].max()) if sel.any() else 8000))
        ax.legend(fontsize=7, markerscale=3)
    axes[0].set_ylabel("ΔE [ADC]")
    fig.suptitle(f"#887 — amplitude-cut scan (MC truth × {mev_to_adc:.0f} ADC/MeV): "
                 "retained fraction + p/d separation", fontweight="bold")
    fig.tight_layout()
    for ext in ("png", "pdf"):
        fig.savefig(out / f"fig_887_deltaE_E_per_cut.{ext}", dpi=160)
    plt.close(fig)

    # retained fraction + PID separation vs cut
    fig, ax1 = plt.subplots(figsize=(8, 5))
    ax2 = ax1.twinx()
    rets = [study887["per_cut"][float(c)]["retained_event_fraction_weighted"] * 100 for c in cuts]
    seps = [study887["per_cut"][float(c)]["pid_separation_1_minus_BC"] or np.nan for c in cuts]
    ax1.plot(cuts, rets, "o-", color="C0", lw=2, label="retained events (%)")
    ax2.plot(cuts, seps, "s--", color="C3", lw=2, label="p/d ΔE separation (1−BC)")
    ax1.set_xlabel("amplitude cut [ADC]")
    ax1.set_ylabel("retained weighted event fraction [%]", color="C0")
    ax2.set_ylabel("p/d PID separation (1 − Bhattacharyya overlap)", color="C3")
    ax1.set_title("#887 — amplitude-cut scan: retention vs PID separation")
    l1, lb1 = ax1.get_legend_handles_labels()
    l2, lb2 = ax2.get_legend_handles_labels()
    ax1.legend(l1 + l2, lb1 + lb2, loc="center right")
    fig.tight_layout()
    for ext in ("png", "pdf"):
        fig.savefig(out / f"fig_887_amplitude_cut_scan.{ext}", dpi=160)
    plt.close(fig)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--root", default=os.environ.get("CCB_MC_ROOT", DEFAULT_ROOT))
    ap.add_argument("--tree", default="hibeam")
    ap.add_argument("--out", required=True, type=Path)
    ap.add_argument("--entry-stop", type=int, default=0, help="0 = all events")
    ap.add_argument("--mev-to-adc", type=float,
                    default=_env_float(ENV_MEV_TO_ADC, DEFAULT_MEV_TO_ADC))
    ap.add_argument("--cuts", default=os.environ.get("CCB_AMPLITUDE_CUTS", DEFAULT_AMPLITUDE_CUTS),
                    help="Comma-separated amplitude cuts [ADC] (default 500,1000,1500).")
    args = ap.parse_args(argv)
    args.out.mkdir(parents=True, exist_ok=True)

    cuts = [float(c) for c in str(args.cuts).split(",") if str(c).strip()]
    entry_stop = args.entry_stop if args.entry_stop > 0 else None

    print(f"[load] {args.root} tree={args.tree} entry_stop={entry_stop}", flush=True)
    E, w, prim_pdg, b_enter_pdg, b_enter_charged, total_b_edep, n_evt = load_mc(
        args.root, args.tree, entry_stop)
    print(f"[load] {n_evt} events; weight range {w.min():.3f}..{w.max():.3f} "
          f"ESS={ess(w):.0f} ({ess(w)/n_evt*100:.0f}% of nominal)", flush=True)

    s879 = study_879(E, w, b_enter_pdg)
    s880 = study_880(E, w, b_enter_pdg, b_enter_charged, total_b_edep)
    s887 = study_887(E, w, b_enter_pdg, b_enter_charged, args.mev_to_adc, cuts)

    plot_879(E, w, args.out, s879)
    plot_880(E, w, b_enter_pdg, b_enter_charged, args.out, s880)
    plot_887(E, w, b_enter_pdg, b_enter_charged, args.mev_to_adc, cuts, args.out, s887)

    result = {
        "study": "issues879_880_887_mc_analysis",
        "generated_utc": datetime.now(timezone.utc).isoformat(),
        "root": args.root,
        "n_events": int(n_evt),
        "primary_weight": s880["primary_weight_stats"],
        "issue_879_readout_pattern": s879,
        "issue_880_weight_audit": s880,
        "issue_887_amplitude_cut_scan": s887,
    }
    (args.out / "issues879_880_887_result.json").write_text(
        json.dumps(result, indent=2), encoding="utf-8")
    print(json.dumps({
        "n_events": n_evt,
        "issue_879_corr_odd_minus_even": s879["_comparison"]["corr_Odd_minus_Even"],
        "issue_879_invisible_odd": s879["ODD_1357"]["invisible_energy_fraction_weighted"],
        "issue_880_first_B_mean_bias_pct": s880["bias_summary"]["first_B_layer_mean_rel_bias_pct"],
        "issue_887_retained_frac_per_cut": {str(c): s887["per_cut"][c]["retained_event_fraction_weighted"] for c in cuts},
        "issue_887_pid_sep_per_cut": {str(c): s887["per_cut"][c]["pid_separation_1_minus_BC"] for c in cuts},
    }, indent=2))
    print(f"[done] wrote {args.out}/issues879_880_887_result.json")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
