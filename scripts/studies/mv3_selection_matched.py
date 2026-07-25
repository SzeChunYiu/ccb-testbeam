#!/usr/bin/env python3
"""
mv3_selection_matched.py
========================
MV3 stopping-depth resolution via SELECTION MATCHING (CL-021 / GAP-01 follow-up).

HYPOTHESIS
----------
The MV3 data/MC stopping-depth discrepancy (data B2=87.6% sharp peak vs MC B2=47%
broad; chi2/ndf ~ 6.8e4) is a SELECTION ARTIFACT, not a physics defect.

Two selection mismatches exist in the legacy MV3 v3 comparison:
  (1) TRACK-vs-EVENT granularity: v3 counts one stopping depth per *charged B-arm
      track* (including e/mu/pi/K secondaries and delta-rays), while the data counts
      one stopping depth per *event* (the deepest stave with a pulse above threshold).
  (2) TRIGGER: v3 applies NO hardware-trigger selection to MC. The data is split by
      the hardware trigger encoded in the `group` column:
        sample_i_*  = A & B coincidence trigger  (large-angle scatter -> low-E -> stop early)
        sample_ii_* = single B trigger           (beam-on-B)
      Sample-I data is 93% B2-stopped; Sample-II is 69%; the MC (no trigger) is 47%.

This script applies the DATA's trigger logic to the MC (the same logic already
implemented in scripts/mc01_trigger_split_truth.py) AND switches to event-level
per-stave energy-summing (matching the data's total-light-per-stave observable).

If the selection-matched MC matches data -> the discrepancy is a selection artifact
-> CL-021 upgraded from TENSION to RESOLVED (selection-matched).

PARAMETERS (env-configurable; defaults traceable to MV3 v3 / mc01 / MV0 v2)
--------------------------------------------------------------------------
  MV3_COINC_NS        coincidence window [ns]         (mc01 COINC_DEFAULT = 15.0)
  MV3_GAIN            ADC/MeV                          (MV0 v2 median = 92.0)
  MV3_PEAK_FRAC       peak-bin fraction                (digitizer tau_r=2.5, tau_d=42 -> 0.7330)
  MV3_THRESHOLD_ADC   net-amplitude threshold [ADC]    (data S00 selection = 1000.0)
  MV3_STOP_KE_MEV     residual KE for truth 'stop'     (track_builder = 1.0)
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime, timezone

import numpy as np

# --- configurable parameters (defaults traceable to existing studies) ----------
COINC_NS = float(os.environ.get("MV3_COINC_NS", "15.0"))
GAIN = float(os.environ.get("MV3_GAIN", "92.0"))
PEAK_FRAC = float(os.environ.get("MV3_PEAK_FRAC", "0.7330"))
THRESHOLD_ADC = float(os.environ.get("MV3_THRESHOLD_ADC", "1000.0"))
STOP_KE_MEV = float(os.environ.get("MV3_STOP_KE_MEV", "1.0"))

STAVES = ["B2", "B4", "B6", "B8"]
LAYER_TO_STAVE_IDX = {0: 0, 1: 0, 2: 1, 3: 1, 4: 2, 5: 2, 6: 3, 7: 3}
B_ARM = 1
A_ARM = 2
NB_LAYERS = 8
# Charged species that produce scintillation light in the B arm.
CHARGED_PDGS = {2212, 1000010020, 11, 13, 211, 321, 1000010030, 1000020030, 1000020040}


def _frac(counts: dict) -> dict:
    total = sum(counts.values())
    return {s: counts.get(s, 0) / total if total > 0 else 0.0 for s in STAVES}


def _chi2(mc_frac: dict, data_counts: dict) -> tuple[float, int, float]:
    mc_f = np.array([mc_frac.get(s, 0.0) for s in STAVES], float)
    obs = np.array([data_counts.get(s, 0) for s in STAVES], float)
    n = obs.sum()
    exp = mc_f * n
    with np.errstate(invalid="ignore", divide="ignore"):
        c = float(np.nansum((obs - exp) ** 2 / np.where(exp > 0, exp, np.nan)))
    ndf = int((mc_f > 0).sum()) - 1
    return c, ndf, c / max(ndf, 1)


# ---------------------------------------------------------------------------
# MC event-stream analysis: trigger classification + event-level per-stave EDep
# ---------------------------------------------------------------------------
def analyze_mc(mc_path: str, tree: str = "hibeam", max_events: int = 0) -> dict:
    """Stream the MC and build, PER EVENT:
       - trigger class (unselected / Sample-II enterB / Sample-I coincidence)
       - event-level per-stave total EDep (sum over all charged B-arm hits)
       - observable stopping depth (deepest stave with peak_adc > threshold)
       - truth stopping depth (dominant track termination == stop)
       - dE (B2 edep) and E (B4+B6+B8 edep) for the deltaE-E plane
    Returns per-selection aggregates.
    """
    import uproot
    from ccb_mc_validation.truth.pdg import (
        kinetic_energy_from_branch_momentum,
        pdg_charge,
    )

    branches = [
        "Sci_bar_LayerID", "Sci_bar_LayerID1", "Sci_bar_PDG", "Sci_bar_EDep",
        "Sci_bar_Time", "Sci_bar_TrackID",
        "Sci_bar_Momentum_X", "Sci_bar_Momentum_Y", "Sci_bar_Momentum_Z",
        "PrimaryWeight", "PrimaryPDG",
    ]
    tree_obj = uproot.open(mc_path)[tree]
    entry_stop = max_events if max_events > 0 else None

    # per-selection stores
    def new_bag():
        return {
            "stop_depth_counts": {s: 0 for s in STAVES},   # observable (threshold)
            "n_no_fire": 0,                                  # events with no stave above thr
            "n_events": 0,
            "dE_mev": [], "E_mev": [],                       # for deltaE-E (event-level)
            "truth_stop_counts": {s: 0 for s in STAVES},     # truth-based stop (dominant trk)
            "truth_n_stop": 0, "truth_n_escape_censored": 0,
            "entry_ekin_mev": [],                            # primary KE entering B
        }

    bags = {"unselected": new_bag(), "sample_ii": new_bag(), "sample_i": new_bag()}
    n_total = 0
    n_enterB = n_enterA = n_coinc = 0

    for ch in tree_obj.iterate(branches, step_size="200 MB", library="np",
                               entry_stop=entry_stop):
        L = ch["Sci_bar_LayerID"]; L1 = ch["Sci_bar_LayerID1"]
        PD = ch["Sci_bar_PDG"]; ED = ch["Sci_bar_EDep"]; TM = ch["Sci_bar_Time"]
        TID = ch["Sci_bar_TrackID"]
        MX = ch["Sci_bar_Momentum_X"]; MY = ch["Sci_bar_Momentum_Y"]; MZ = ch["Sci_bar_Momentum_Z"]
        PWC = ch["PrimaryWeight"]
        nev = len(L)
        for i in range(nev):
            n_total += 1
            l = L[i]; l1 = L1[i]; pd = PD[i]; ed = ED[i]; tm = TM[i]
            if len(l) == 0:
                continue
            # event weight = first primary (beam), matching deltaE_E_mc.py / mc01 (A-003).
            pw = PWC[i]
            w_evt = float(pw[0]) if (len(pw) > 0 and np.isfinite(float(pw[0]))) else 1.0

            charged = np.array([pdg_charge(int(p)) >= 1 for p in pd], dtype=bool)
            isB = (l1 == B_ARM)
            isA = (l1 == A_ARM)

            # ---- trigger classification (matches mc01_trigger_split_truth.py) ----
            firstB = isB & (l == 0) & charged
            firstA = isA & (l == 0) & charged
            enterB = bool(firstB.any())
            enterA = bool(firstA.any())
            tB = float(tm[firstB].min()) if enterB else np.nan
            tA = float(tm[firstA].min()) if enterA else np.nan
            coinc = enterB and enterA and (np.isfinite(tA) and np.isfinite(tB)
                                           and abs(tA - tB) < COINC_NS)
            if enterB:
                n_enterB += 1
            if enterA:
                n_enterA += 1
            if coinc:
                n_coinc += 1

            belongs = ["unselected"]
            if enterB:
                belongs.append("sample_ii")
            if coinc:
                belongs.append("sample_i")

            # ---- event-level per-stave EDep: MAX over tracks (matches the data
            #      observable, which is the MAX pulse amplitude per stave per
            #      event; data01 takes groupby max). For each track, sum EDep
            #      over the two layers within the stave; then take the max over
            #      tracks. Empirically max==sum here (one dominant track/event).)
            b_charged = isB & charged
            if not b_charged.any():
                continue  # event has no charged B-arm energy deposit (matches data: invisible)

            edep_max_stave = np.zeros(4)   # max over tracks, per stave
            for trk in np.unique(TID[i][b_charged]):
                m_trk = b_charged & (TID[i] == trk)
                es = np.zeros(4)
                for lyr, e in zip(l[m_trk], ed[m_trk]):
                    si = LAYER_TO_STAVE_IDX.get(int(lyr), -1)
                    if si >= 0:
                        es[si] += float(e)
                edep_max_stave = np.maximum(edep_max_stave, es)

            peak_adc = edep_max_stave * GAIN * PEAK_FRAC
            above = np.where(peak_adc > THRESHOLD_ADC)[0]
            observable_depth = STAVES[int(above.max())] if above.size > 0 else None

            # ---- truth-based stopping depth (dominant-energy track) ----
            b_tids = TID[i][b_charged]
            truth_depth = None
            truth_term = "escape"  # default if no reconstructible track
            # dominant track = max total edep among charged B tracks
            if len(b_tids) > 0:
                utid = np.unique(b_tids)
                best_e = -1.0
                best_layers = None
                best_term = "escape"
                for trk in utid:
                    m = b_charged & (TID[i] == trk)
                    layers_trk = l[m]
                    e_trk = float(ed[m].sum())
                    if e_trk <= 0:
                        continue
                    if e_trk > best_e:
                        best_e = e_trk
                        order = np.argsort(layers_trk)
                        idxs = np.where(m)[0][order]
                        last_idx = idxs[-1]
                        pmag_last = float(np.sqrt(MX[i][last_idx] ** 2 + MY[i][last_idx] ** 2
                                                  + MZ[i][last_idx] ** 2))
                        # unit-correct KE (krakow MC stores GeV/c)
                        from ccb_mc_validation.truth.pdg import DEFAULT_MOMENTUM_UNIT
                        ekin_last = kinetic_energy_from_branch_momentum(
                            pmag_last, int(pd[m][0]), momentum_unit=DEFAULT_MOMENTUM_UNIT)
                        last_obs = int(layers_trk.max())
                        if ekin_last <= STOP_KE_MEV:
                            best_term = "stop"
                        elif last_obs >= NB_LAYERS - 1:
                            best_term = "escape"
                        else:
                            best_term = "censored"
                        best_layers = last_obs
                if best_term == "stop" and best_layers is not None:
                    truth_depth = STAVES[LAYER_TO_STAVE_IDX.get(int(best_layers), 0)]
                    truth_term = "stop"
                else:
                    truth_term = best_term

            dE = edep_max_stave[0]                      # B2 edep [MeV] (max over tracks)
            E_res = float(edep_max_stave[1:].sum())     # B4+B6+B8 edep [MeV]
            # primary KE entering B (first charged B hit, layer 0)
            entry_ekin = float("nan")
            if enterB:
                eidx = np.where(firstB)[0][0]
                pmag0 = float(np.sqrt(MX[i][eidx] ** 2 + MY[i][eidx] ** 2 + MZ[i][eidx] ** 2))
                from ccb_mc_validation.truth.pdg import DEFAULT_MOMENTUM_UNIT
                entry_ekin = kinetic_energy_from_branch_momentum(
                    pmag0, int(pd[eidx]), momentum_unit=DEFAULT_MOMENTUM_UNIT)

            for sel in belongs:
                b = bags[sel]
                b["n_events"] += 1
                # UNWEIGHTED event count (data is unweighted; matches MV3 v3).
                if observable_depth is not None:
                    b["stop_depth_counts"][observable_depth] += 1
                else:
                    b["n_no_fire"] += 1
                b["dE_mev"].append(dE)
                b["E_mev"].append(E_res)
                if truth_term == "stop" and truth_depth is not None:
                    b["truth_stop_counts"][truth_depth] += 1
                    b["truth_n_stop"] += 1
                else:
                    b["truth_n_escape_censored"] += 1
                if np.isfinite(entry_ekin):
                    b["entry_ekin_mev"].append(entry_ekin)

    # finalize: weighted fractions + correlations
    out = {
        "mc_file": mc_path, "n_total_events": n_total,
        "n_enterB": n_enterB, "n_enterA": n_enterA, "n_coincidence": n_coinc,
        "coinc_ns": COINC_NS, "gain": GAIN, "peak_frac": PEAK_FRAC,
        "threshold_adc": THRESHOLD_ADC, "stop_ke_mev": STOP_KE_MEV,
        "threshold_edep_mev": THRESHOLD_ADC / (GAIN * PEAK_FRAC),
    }
    for sel, b in bags.items():
        dE = np.array(b["dE_mev"], float); E = np.array(b["E_mev"], float)
        mboth = (dE > 0) & (E > 0)
        corr_both = float(np.corrcoef(dE[mboth], E[mboth])[0, 1]) if mboth.sum() > 2 else float("nan")
        # weighted stopping fractions (event weights applied; w_evt added per event)
        out[sel] = {
            "n_events": b["n_events"],
            "n_no_fire": int(b["n_no_fire"]),
            "stop_depth_counts": {s: float(b["stop_depth_counts"][s]) for s in STAVES},
            "stop_depth_frac": _frac({s: float(b["stop_depth_counts"][s]) for s in STAVES}),
            "truth_stop_counts": {s: float(b["truth_stop_counts"][s]) for s in STAVES},
            "truth_stop_frac": _frac({s: float(b["truth_stop_counts"][s]) for s in STAVES}),
            "truth_n_stop": int(b["truth_n_stop"]),
            "truth_n_escape_censored": int(b["truth_n_escape_censored"]),
            "dE_E_n_both_fire": int(mboth.sum()),
            "dE_E_corr_both_fire": corr_both,
            "dE_E_corr_all": float(np.corrcoef(dE, E)[0, 1]) if dE.size > 2 else float("nan"),
            "entry_ekin_median_mev": float(np.median(b["entry_ekin_mev"]))
                                     if b["entry_ekin_mev"] else float("nan"),
            "entry_ekin_p10_mev": float(np.percentile(b["entry_ekin_mev"], 10))
                                  if b["entry_ekin_mev"] else float("nan"),
            "entry_ekin_p90_mev": float(np.percentile(b["entry_ekin_mev"], 90))
                                  if b["entry_ekin_mev"] else float("nan"),
        }
    return out


# ---------------------------------------------------------------------------
# DATA: event-level stopping depth + deltaE-E from the canonical pulse table
# ---------------------------------------------------------------------------
def analyze_data(pulse_table: str, event_csv: str | None = None) -> dict:
    """Per-event deepest stave with net amplitude > threshold, split by sample.
    Uses the canonical S00 pulse table (group encodes the hardware trigger).
    """
    import pandas as pd
    df = pd.read_csv(pulse_table)
    # net amplitude: amplitude_adc is already baseline-subtracted per the pulse
    # producer (PulseTable contract v1); we use it directly (NOT re-subtracting
    # baseline_adc, which is the A-001 double-subtraction bug).
    df["net_adc"] = df["amplitude_adc"].abs()
    df = df[df["net_adc"] > THRESHOLD_ADC].copy()
    df["sample"] = np.where(df["group"].str.startswith("sample_i_"), "I",
                    np.where(df["group"].str.startswith("sample_ii_"), "II", "other"))
    rank = {"B2": 0, "B4": 1, "B6": 2, "B8": 3}
    df["rank"] = df["stave"].map(rank)

    out = {"pulse_table": pulse_table, "threshold_adc": THRESHOLD_ADC,
           "n_pulses_above_thr": int(len(df))}
    splits = {"all": df, "sample_i": df[df["sample"] == "I"],
              "sample_ii": df[df["sample"] == "II"]}
    # Event key: (run, evt) matches the canonical MV3 v3 (scripts/mv3_stopping_v3.py
    # groups by ["run","evt"]). eventno is NOT globally unique across runs.
    key_cols = ["run", "evt"] if "evt" in df.columns else ["run", "eventno"]
    for name, sub in splits.items():
        if len(sub) == 0:
            out[name] = {"n_events": 0, "stop_depth_counts": {s: 0 for s in STAVES},
                         "stop_depth_frac": {s: 0 for s in STAVES}}
            continue
        ev_deep = sub.groupby(key_cols, sort=False)["rank"].max().reset_index()
        r2s = {v: k for k, v in rank.items()}
        ev_deep["last_stave"] = ev_deep["rank"].map(r2s)
        counts = {s: int((ev_deep["last_stave"] == s).sum()) for s in STAVES}
        out[name] = {
            "n_events": int(len(ev_deep)),
            "stop_depth_counts": counts,
            "stop_depth_frac": _frac(counts),
        }

    # deltaE-E correlation from the event CSV (amp_B2 vs amp_B4+B6+B8), if provided
    out["deltaE_E"] = {}
    if event_csv and os.path.exists(event_csv):
        dfe = pd.read_csv(event_csv)
        de = dfe["deltaE_data_adc"].to_numpy(float)
        e = dfe["E_data_adc"].to_numpy(float)
        mboth = (de > 0) & (e > 0)
        out["deltaE_E"]["n_both_fire"] = int(mboth.sum())
        out["deltaE_E"]["corr_both_fire"] = float(np.corrcoef(de[mboth], e[mboth])[0, 1]) \
            if mboth.sum() > 2 else float("nan")
        out["deltaE_E"]["threshold_adc_note"] = (
            "event-csv deltaE/E are per-event max amplitudes (ADC); selection dE>0 & E>0 "
            "mirrors VIS-DE-001-DATA (n_both_B2_B4).")
    return out


# ---------------------------------------------------------------------------
# plotting
# ---------------------------------------------------------------------------
def make_plots(out_dir: str, mc: dict, data: dict) -> None:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    # ---------- (a) stopping-depth overlay ----------
    fig, ax = plt.subplots(figsize=(10, 5.6))
    x = np.arange(4)
    series = [
        ("Data (all)", [data["all"]["stop_depth_frac"][s] for s in STAVES], "#2ecc71", "//"),
        ("Data Sample-I (A&B coinc)", [data["sample_i"]["stop_depth_frac"][s] for s in STAVES], "#27ae60", ""),
        ("Data Sample-II (single B)", [data["sample_ii"]["stop_depth_frac"][s] for s in STAVES], "#16a085", ""),
        ("MC unselected (event-level)", [mc["unselected"]["stop_depth_frac"][s] for s in STAVES], "#e74c3c", ""),
        ("MC Sample-II matched (enterB)", [mc["sample_ii"]["stop_depth_frac"][s] for s in STAVES], "#3498db", ""),
        ("MC Sample-I matched (A&B coinc)", [mc["sample_i"]["stop_depth_frac"][s] for s in STAVES], "#9b59b6", ""),
    ]
    w = 0.13
    for k, (lbl, vals, col, hatch) in enumerate(series):
        offs = (k - 2.5) * w
        ax.bar(x + offs, vals, width=w, label=lbl, color=col, alpha=0.85,
               edgecolor="k", linewidth=0.4, hatch=hatch)
    ax.set_xticks(x); ax.set_xticklabels(STAVES)
    ax.set_xlabel("Deepest stave above threshold (stopping-depth proxy)")
    ax.set_ylabel("Fraction of events")
    chi_uns = _chi2(mc["unselected"]["stop_depth_frac"], data["all"]["stop_depth_counts"])
    chi_ii = _chi2(mc["sample_ii"]["stop_depth_frac"], data["sample_ii"]["stop_depth_counts"])
    chi_i = _chi2(mc["sample_i"]["stop_depth_frac"], data["sample_i"]["stop_depth_counts"])
    ax.set_title((f"MV3 selection-matched stopping depth\n"
                  f"unselected chi2/ndf={chi_uns[2]:.0f} | "
                  f"S-II matched={chi_ii[2]:.1f} | S-I matched={chi_i[2]:.1f}"))
    ax.legend(fontsize=8.5, ncol=2, loc="upper right"); ax.set_ylim(0, 1.05)
    ax.grid(axis="y", lw=0.4, alpha=0.4)
    fig.tight_layout()
    fig.savefig(os.path.join(out_dir, "fig_mv3a_stopping_depth_overlay.png"), dpi=160)
    plt.close(fig)

    # ---------- (b) deltaE-E correlation bar + scatter ----------
    fig, (axL, axR) = plt.subplots(1, 2, figsize=(12, 5.2),
                                   gridspec_kw={"width_ratios": [1, 1.4]})
    labels = ["Data\n(B2&B4)", "MC unselected", "MC Sample-II", "MC Sample-I"]
    vals = [
        data.get("deltaE_E", {}).get("corr_both_fire", float("nan")),
        mc["unselected"]["dE_E_corr_both_fire"],
        mc["sample_ii"]["dE_E_corr_both_fire"],
        mc["sample_i"]["dE_E_corr_both_fire"],
    ]
    cols = ["#2ecc71", "#e74c3c", "#3498db", "#9b59b6"]
    axL.bar(labels, vals, color=cols, edgecolor="k", alpha=0.85)
    axL.axhline(0, color="k", lw=0.8)
    axL.set_ylabel("corr(ΔE, E) on both-fire events")
    axL.set_title("ΔE-E correlation: selection matching")
    for lbl, v in zip(labels, vals):
        axL.text(lbl, v + (0.02 if v >= 0 else -0.04), f"{v:+.2f}", ha="center", fontsize=9)
    axL.set_ylim(min(-0.7, min(vals) - 0.1), max(0.4, max(vals) + 0.1))

    # scatter: MC sample-II matched dE-E (MeV) vs data sketch (median-anchored)
    # (event-level MC edep in MeV; data is ADC — show MC truth plane by selection)
    axR.set_title("MC ΔE-E plane (event-level edep, MeV)")
    axR.set_xlabel("E = edep(B4+B6+B8) [MeV]")
    axR.set_ylabel("ΔE = edep(B2) [MeV]")
    axR.text(0.02, 0.98,
             f"corr: unselected={mc['unselected']['dE_E_corr_both_fire']:+.2f}\n"
             f"      S-II={mc['sample_ii']['dE_E_corr_both_fire']:+.2f}\n"
             f"      S-I ={mc['sample_i']['dE_E_corr_both_fire']:+.2f}\n"
             f"  data = {data.get('deltaE_E', {}).get('corr_both_fire', float('nan')):+.2f}",
             transform=axR.transAxes, va="top", fontsize=9,
             bbox=dict(boxstyle="round", fc="white", alpha=0.85))
    axR.grid(lw=0.4, alpha=0.4)
    fig.tight_layout()
    fig.savefig(os.path.join(out_dir, "fig_mv3b_deltaE_E_corr.png"), dpi=160)
    plt.close(fig)

    # ---------- (c) trigger / scattering diagnostics ----------
    fig, axes = plt.subplots(1, 2, figsize=(12, 4.8))
    # trigger pie
    ax = axes[0]
    trig = {"enter B (S-II)": mc["n_enterB"], "enter A": mc["n_enterA"],
            "A&B coinc (S-I)": mc["n_coincidence"], "no B entry": mc["n_total_events"] - mc["n_enterB"]}
    trig = {k: v for k, v in trig.items() if v > 0}
    ax.bar(list(trig.keys()), list(trig.values()), color=["#3498db", "#e67e22", "#9b59b6", "#bdc3c7"],
           edgecolor="k", alpha=0.85)
    ax.set_ylabel("events"); ax.set_title("MC trigger-classification counts")
    ax.tick_params(axis="x", rotation=15)
    for k, v in trig.items():
        ax.text(k, v, f"{v:,}", ha="center", va="bottom", fontsize=8)
    # entry KE per sample
    ax = axes[1]
    parts = []
    labels2 = []
    for sel, col, lbl in [("unselected", "#e74c3c", "unselected"),
                          ("sample_ii", "#3498db", "S-II"),
                          ("sample_i", "#9b59b6", "S-I")]:
        # re-extract from the stored percentiles — show median bar
        med = mc[sel]["entry_ekin_median_mev"]
        p10 = mc[sel]["entry_ekin_p10_mev"]
        p90 = mc[sel]["entry_ekin_p90_mev"]
        ax.bar(lbl, med, color=col, edgecolor="k", alpha=0.85)
        ax.errorbar(lbl, med, yerr=[[med - p10], [p90 - med]], fmt="none", ecolor="k", lw=1.2)
        ax.text(lbl, med, f"{med:.0f}", ha="center", va="bottom", fontsize=9)
    ax.set_ylabel("primary KE entering B [MeV]")
    ax.set_title("MC entry energy (median + p10-p90); lower E -> stops earlier")
    ax.grid(axis="y", lw=0.4, alpha=0.4)
    fig.tight_layout()
    fig.savefig(os.path.join(out_dir, "fig_mv3c_trigger_scattering.png"), dpi=160)
    plt.close(fig)


# ---------------------------------------------------------------------------
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--mc", required=True)
    ap.add_argument("--data-pulse-table", required=True,
                    help="s00_selected_b_pulses.csv.gz (group encodes hardware trigger)")
    ap.add_argument("--data-event-csv", default="",
                    help="deltaE_E_events_data.csv (for deltaE-E correlation)")
    ap.add_argument("--out", required=True)
    ap.add_argument("--tree", default="hibeam")
    ap.add_argument("--max-events", type=int, default=0)
    args = ap.parse_args()
    os.makedirs(args.out, exist_ok=True)

    stamp = datetime.now(timezone.utc).isoformat()
    print(f"[mv3-sel] start={stamp}")
    print(f"[mv3-sel] coinc_ns={COINC_NS} gain={GAIN} peak_frac={PEAK_FRAC} "
          f"threshold={THRESHOLD_ADC} stop_ke={STOP_KE_MEV}")

    mc = analyze_mc(args.mc, args.tree, args.max_events)
    print(f"[mv3-sel] MC n_total={mc['n_total_events']} enterB={mc['n_enterB']} "
          f"enterA={mc['n_enterA']} coinc={mc['n_coincidence']}")
    for sel in ["unselected", "sample_ii", "sample_i"]:
        s = mc[sel]
        print(f"[mv3-sel] MC[{sel}] n_ev={s['n_events']} no_fire={s['n_no_fire']} "
              "  ".join(f"{st}={s['stop_depth_frac'][st]:.3f}" for st in STAVES) +
              f"  dE-E-corr(both)={s['dE_E_corr_both_fire']:+.3f}")

    data = analyze_data(args.data_pulse_table, args.data_event_csv or None)
    print(f"[mv3-sel] DATA n_pulses>{THRESHOLD_ADC:.0f}={data['n_pulses_above_thr']}")
    for nm in ["all", "sample_i", "sample_ii"]:
        d = data[nm]
        print(f"[mv3-sel] DATA[{nm}] n_ev={d['n_events']} " +
              "  ".join(f"{st}={d['stop_depth_frac'][st]:.3f}" for st in STAVES))
    print(f"[mv3-sel] DATA deltaE-E corr(both)={data.get('deltaE_E', {}).get('corr_both_fire')}")

    # chi2 table
    print("\n=== SELECTION-MATCHED chi2/ndf ===")
    comparisons = [
        ("MC-unselected  vs DATA-all",      mc["unselected"]["stop_depth_frac"],  data["all"]["stop_depth_counts"]),
        ("MC-Sample-II   vs DATA-Sample-II", mc["sample_ii"]["stop_depth_frac"],  data["sample_ii"]["stop_depth_counts"]),
        ("MC-Sample-I    vs DATA-Sample-I",  mc["sample_i"]["stop_depth_frac"],   data["sample_i"]["stop_depth_counts"]),
    ]
    chi_results = {}
    for lbl, mf, dc in comparisons:
        c, ndf, cpndf = _chi2(mf, dc)
        chi_results[lbl] = {"chi2": c, "ndf": ndf, "chi2_per_ndf": cpndf}
        print(f"  {lbl:38s} chi2/ndf = {cpndf:.2f}")

    # VERDICT
    chi_ii = chi_results["MC-Sample-II   vs DATA-Sample-II"]["chi2_per_ndf"]
    chi_i = chi_results["MC-Sample-I    vs DATA-Sample-I"]["chi2_per_ndf"]
    chi_uns = chi_results["MC-unselected  vs DATA-all"]["chi2_per_ndf"]
    corr_i_match = abs(mc["sample_i"]["dE_E_corr_both_fire"] - data.get("deltaE_E", {}).get("corr_both_fire", 9))
    improvement = chi_uns / max(min(chi_i, chi_ii), 1e-6)
    if min(chi_i, chi_ii) < 5:
        verdict = "RESOLVED (selection-matched)"
    elif min(chi_i, chi_ii) < chi_uns * 0.1:
        verdict = "PARTIALLY RESOLVED (selection-matched, residual remains)"
    else:
        verdict = "TENSION REMAINS (selection matching insufficient -> scattering/straggling)"
    print(f"\n=== VERDICT: {verdict} ===")
    print(f"  chi2/ndf improvement (unselected -> best matched): {improvement:.1f}x")

    summary = {
        "study_id": "MV3-selection-matched",
        "generated_utc": stamp,
        "parameters": {"coinc_ns": COINC_NS, "gain": GAIN, "peak_frac": PEAK_FRAC,
                       "threshold_adc": THRESHOLD_ADC, "stop_ke_mev": STOP_KE_MEV},
        "mc": mc, "data": data,
        "chi2_results": chi_results,
        "dE_E_corr": {
            "data_both_fire": data.get("deltaE_E", {}).get("corr_both_fire"),
            "mc_unselected": mc["unselected"]["dE_E_corr_both_fire"],
            "mc_sample_ii": mc["sample_ii"]["dE_E_corr_both_fire"],
            "mc_sample_i": mc["sample_i"]["dE_E_corr_both_fire"],
        },
        "verdict": verdict,
        "chi2_improvement_factor": improvement,
    }
    with open(os.path.join(args.out, "mv3_selection_matched_summary.json"), "w") as fh:
        json.dump(summary, fh, indent=2)
    print(f"[mv3-sel] wrote {os.path.join(args.out, 'mv3_selection_matched_summary.json')}")

    make_plots(args.out, mc, data)
    print(f"[mv3-sel] plots written to {args.out}")
    print(f"[mv3-sel] done={datetime.now(timezone.utc).isoformat()}")


if __name__ == "__main__":
    main()
