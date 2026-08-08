#!/usr/bin/env python3
"""
supervisor_deltaE_E.py
======================
Correct Delta-E vs E analysis per supervisor specifications (Issue #618).

Definitions (Dave, 2026-07-09):
  MC:
    Delta E = Edep(B2) = energy deposited in first B-stack layer
    E_residual = Edep(B4) + Edep(B6) + Edep(B8)
    Also: E_full = sum of all downstream layers (B4 through B14 if available)
    Data-matched: E_4layer = Edep(B4) + Edep(B6) + Edep(B8)
  Data:
    Delta E = amplitude(B2)
    E_residual = amplitude(B4) + amplitude(B6) + amplitude(B8)
    (amplitude proxies, NOT calibrated energy)

  Stopping layer: deepest layer with Edep > threshold (default 0.02 MeV)
  Check stability at 0, 0.05, 0.1, 0.5 MeV

Output per supervisor spec:
  - MC Delta E vs E per sample, per species (p only, d only, p+d color-coded, all)
  - Data Delta E vs E amplitude proxies per sample
  - Penetration plots per sample, per species, with cumulative P(reaches layer)
  - Summary tables for MC (per species) and data (per sample)
"""
import argparse, json, os, sys
import numpy as np

B_ARM, A_ARM = 1, 2
NB_LAYERS = 8  # B-stack: layers 0-7 (B2 through B14)

PDG_NAME = {2212: "p", 1000010020: "d", 1000010030: "t",
            1000020030: "He3", 1000020040: "alpha",
            2112: "n", 22: "gamma", 11: "e-", -11: "e+"}

def species_label(pdg):
    pdg = int(pdg)
    if pdg in PDG_NAME: return PDG_NAME[pdg]
    if abs(pdg) > 1_000_000_000:
        Z = (abs(pdg) // 10_000) % 1000
        if Z >= 6: return "heavy"
        return f"Z{Z}"
    return "other"

def is_charged(pdg):
    pdg = int(pdg); a = abs(pdg)
    if a > 1_000_000_000: return ((a // 10_000) % 1000) > 0
    return a in (2212, 11, 13, 211, 321) or (a > 1e9 and a <= 1e10)


def deepest_edep_layer(layer_edep: dict[int, float], threshold: float,
                        strict: bool = True) -> int:
    """Deepest layer with Edep > threshold (strict=True) or >= threshold.

    Returns the deepest layer index whose deposited energy exceeds the
    threshold.  Returns -1 when no layer passes (NO_LAYER_PASSES sentinel).
    """
    deepest = -1
    for lay, e in layer_edep.items():
        if (e > threshold) if strict else (e >= threshold):
            if int(lay) > deepest:
                deepest = int(lay)
    return deepest

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--mc", required=True)
    ap.add_argument("--data-table", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--coinc-ns", type=float, default=15.0)
    ap.add_argument("--stop-thresholds", type=float, nargs="*",
                    default=[0, 0.02, 0.05, 0.1, 0.5])
    ap.add_argument("--data-thresholds", type=float, nargs="*",
                    default=[500, 750, 1000, 1500])
    args = ap.parse_args()
    os.makedirs(args.out, exist_ok=True)

    import uproot
    import pandas as pd

    # ═══════════════════════════════════════════════════════════════════
    # MC ANALYSIS
    # ═══════════════════════════════════════════════════════════════════
    branches = ["Sci_bar_LayerID", "Sci_bar_LayerID1", "Sci_bar_PDG",
                "Sci_bar_EDep", "Sci_bar_Time", "Sci_bar_TrackID"]

    # Accumulators: per sample, per track
    mc_data = {"I": {"deltaE": [], "E_res": [], "E_full": [], "E_4layer": [],
                     "pdg": [], "nlayers": []},
               "II": {"deltaE": [], "E_res": [], "E_full": [], "E_4layer": [],
                      "pdg": [], "nlayers": []}}
    # Per-threshold stop_layer accumulators (issue #1039)
    mc_stop_layers: dict[str, dict[str, list]] = {
        "I": {}, "II": {}
    }
    for th in args.stop_thresholds:
        for s in ("I", "II"):
            mc_stop_layers[s][th] = []

    n_enterB = n_enterA = n_coinc = n_total = 0

    fobj = uproot.open(args.mc)
    tree = fobj["hibeam"]
    for chunk in tree.iterate(branches, step_size="200 MB", library="np"):
        L = chunk["Sci_bar_LayerID"]; L1 = chunk["Sci_bar_LayerID1"]
        PD = chunk["Sci_bar_PDG"]; ED = chunk["Sci_bar_EDep"]
        TM = chunk["Sci_bar_Time"]; TID = chunk["Sci_bar_TrackID"]
        for i in range(len(L)):
            n_total += 1
            l, l1, pdg_arr, ed, tm = L[i], L1[i], PD[i], ED[i], TM[i]
            if len(l) == 0: continue
            charged = np.array([is_charged(p) for p in pdg_arr], dtype=bool)
            isB = (l1 == B_ARM); isA = (l1 == A_ARM)
            firstB = isB & (l == 0) & charged
            firstA = isA & (l == 0) & charged
            enterB = firstB.any(); enterA = firstA.any()
            tB = tm[firstB].min() if enterB else np.nan
            tA = tm[firstA].min() if enterA else np.nan
            if enterB: n_enterB += 1
            if enterA: n_enterA += 1
            coinc = enterB and enterA and abs(tA - tB) < args.coinc_ns
            if coinc: n_coinc += 1

            belongs = []
            if enterB: belongs.append("II")
            if coinc: belongs.append("I")

            tid_arr = TID[i]
            for s in belongs:
                # Per-track: group B-stack hits by TrackID
                b_hits = isB & charged
                if not b_hits.any(): continue
                b_tids = tid_arr[b_hits]
                for trk in np.unique(b_tids):
                    trk_mask = b_hits & (tid_arr == trk)
                    p0 = int(pdg_arr[trk_mask][0])
                    if not is_charged(p0): continue
                    layers = l[trk_mask]; eds = ed[trk_mask]
                    el = {}
                    for lay, e in zip(layers, eds):
                        el[int(lay)] = el.get(int(lay), 0.0) + float(e)

                    deltaE = el.get(0, 0.0)
                    E_res = sum(el.get(l, 0.0) for l in [1, 2, 3])  # B4, B6, B8
                    E_full = sum(el.get(l, 0.0) for l in range(1, NB_LAYERS))
                    E_4layer = E_res  # same as data-matched

                    # stop_layer per threshold (issue #1039)
                    stop_layers = {
                        th: deepest_edep_layer(el, th, strict=True)
                        for th in args.stop_thresholds
                    }
                    D = mc_data[s]
                    D["deltaE"].append(deltaE)
                    D["E_res"].append(E_res)
                    D["E_full"].append(E_full)
                    D["E_4layer"].append(E_4layer)
                    D["pdg"].append(p0)
                    D["nlayers"].append(int(len(set(layers.tolist()))))
                    # Per-threshold stop_layer (issue #1039)
                    for th, sl in stop_layers.items():
                        mc_stop_layers[s][th].append(sl)

    for s in ("I", "II"):
        for k in mc_data[s]:
            mc_data[s][k] = np.asarray(mc_data[s][k])
        for th in args.stop_thresholds:
            mc_stop_layers[s][th] = np.asarray(mc_stop_layers[s][th], dtype=int)

    # ── MC Summary Tables ──────────────────────────────────────────────
    mc_summary = {}
    for s in ("I", "II"):
        D = mc_data[s]
        sp_labels = np.array([species_label(p) for p in D["pdg"]])
        mc_summary[s] = {}
        for sp in ["p", "d", "alpha", "heavy", "other", "all"]:
            if sp == "all":
                mask = np.ones(len(D["pdg"]), dtype=bool)
            else:
                mask = sp_labels == sp
            if mask.sum() < 5:
                mc_summary[s][sp] = {"n_events": int(mask.sum()), "note": "<5 events"}
                continue
            de = D["deltaE"][mask]; er = D["E_res"][mask]
            # Per-threshold stopping statistics (issue #1039)
            stop_stats = {}
            for th in args.stop_thresholds:
                sl = mc_stop_layers[s][th][mask]
                reach = {
                    "median_stop_layer": float(np.median(sl)),
                    "frac_stop_B2": float((sl == 0).mean()),
                    "frac_reach_B4": float((sl >= 1).mean()),
                    "frac_reach_B6": float((sl >= 2).mean()),
                    "frac_reach_B8": float((sl >= 3).mean()),
                    "frac_no_layer_pass": float((sl < 0).mean()),
                    "comparison_rule": ">",
                    "threshold_MeV": float(th),
                }
                stop_stats[str(th)] = reach
            mc_summary[s][sp] = {
                "n_events": int(mask.sum()),
                "deltaE_median_MeV": float(np.median(de)),
                "deltaE_p16_MeV": float(np.percentile(de, 16)),
                "deltaE_p84_MeV": float(np.percentile(de, 84)),
                "Eres_median_MeV": float(np.median(er)),
                "Eres_p16_MeV": float(np.percentile(er, 16)),
                "Eres_p84_MeV": float(np.percentile(er, 84)),
                "stop_threshold_stats": stop_stats,
            }

    # ═══════════════════════════════════════════════════════════════════
    # DATA ANALYSIS
    # ═══════════════════════════════════════════════════════════════════
    df = pd.read_csv(args.data_table)
    df["sample"] = np.where(df["group"].str.startswith("sample_i_"), "I",
                     np.where(df["group"].str.startswith("sample_ii_"), "II", "other"))
    df = df[df["group"].str.endswith("_analysis")].copy()

    data_summary = {}
    s00_amplitude_cut = 1000.0  # S00 selection gate
    min_data_threshold = min(args.data_thresholds) if args.data_thresholds else s00_amplitude_cut
    if min_data_threshold < s00_amplitude_cut:
        print(f"[warn] --data-thresholds includes {min_data_threshold} ADC which is below the "
              f"S00 selection cut ({s00_amplitude_cut} ADC). Pulses below the cut are "
              f"not present in the selected-pulse table; reach fractions at thresholds "
              f"below {s00_amplitude_cut} ADC are left-censored and not identifiable.",
              file=sys.stderr)
    for s in ("I", "II"):
        sub = df[df["sample"] == s]
        # Per-event: match B2, B4, B6, B8 amplitudes
        b2 = sub[sub["stave"]=="B2"][["eventno","amplitude_adc"]].rename(columns={"amplitude_adc":"amp_B2"})
        b4 = sub[sub["stave"]=="B4"][["eventno","amplitude_adc"]].rename(columns={"amplitude_adc":"amp_B4"})
        b6 = sub[sub["stave"]=="B6"][["eventno","amplitude_adc"]].rename(columns={"amplitude_adc":"amp_B6"})
        b8 = sub[sub["stave"]=="B8"][["eventno","amplitude_adc"]].rename(columns={"amplitude_adc":"amp_B8"})
        merged = b2.merge(b4, on="eventno", how="left").merge(b6, on="eventno", how="left").merge(b8, on="eventno", how="left")
        merged = merged.fillna(0)
        deltaE_data = merged["amp_B2"].values
        E_res_data = merged["amp_B4"].values + merged["amp_B6"].values + merged["amp_B8"].values
        sat_B2 = (deltaE_data >= 7000)

        # Per-threshold deepest active stave (issue #1038: use args.data_thresholds)
        per_threshold_reach = {}
        for th in args.data_thresholds:
            stave_presence = np.column_stack([
                merged["amp_B2"] > th,
                merged["amp_B4"] > th,
                merged["amp_B6"] > th,
                merged["amp_B8"] > th,
            ])
            deepest = np.argmax(stave_presence[:, ::-1], axis=1)
            deepest = 3 - deepest  # invert: 0=B2, 1=B4, 2=B6, 3=B8
            # When no stave passes, argmax returns 0 (first reverse index), so
            # deepest becomes 3 — correct that: if no stave passes, set to -1.
            no_pass = ~stave_presence.any(axis=1)
            deepest[no_pass] = -1
            per_threshold_reach[str(th)] = {
                "threshold_ADC": float(th),
                "frac_reach_B4": float((deepest >= 1).mean()),
                "frac_reach_B6": float((deepest >= 2).mean()),
                "frac_reach_B8": float((deepest >= 3).mean()),
                "deepest_stave_fracs": {
                    "B2": float((deepest == 0).mean()),
                    "B4": float((deepest == 1).mean()),
                    "B6": float((deepest == 2).mean()),
                    "B8": float((deepest == 3).mean()),
                    "NO_LAYER_PASSES": float((deepest == -1).mean()),
                },
            }

        data_summary[s] = {
            "n_events": int(len(merged)),
            "deltaE_median_ADC": float(np.median(deltaE_data)),
            "deltaE_p16_ADC": float(np.percentile(deltaE_data, 16)),
            "deltaE_p84_ADC": float(np.percentile(deltaE_data, 84)),
            "Eres_median_ADC": float(np.median(E_res_data)),
            "Eres_p16_ADC": float(np.percentile(E_res_data, 16)),
            "Eres_p84_ADC": float(np.percentile(E_res_data, 84)),
            "frac_saturated_B2": float(sat_B2.mean()),
            "s00_amplitude_cut_ADC": s00_amplitude_cut,
            "per_threshold_reach": per_threshold_reach,
        }

    # ═══════════════════════════════════════════════════════════════════
    # PLOTS
    # ═══════════════════════════════════════════════════════════════════
    try:
        import matplotlib; matplotlib.use("Agg"); import matplotlib.pyplot as plt
        CAT = ["#2a78d6", "#1baf7a", "#eda100", "#008300", "#4a3aa7", "#e34948"]
        plt.rcParams.update({"figure.facecolor":"white","axes.facecolor":"white",
                             "axes.grid":True,"grid.color":"#e8e8e8","grid.linewidth":0.5,
                             "font.family":"sans-serif","font.sans-serif":["DejaVu Sans"],
                             "savefig.dpi":300,"savefig.bbox":"tight"})

        # ── MC Delta E vs E per sample, per species ───────────────────
        for s, slabel in (("I","Sample I"), ("II","Sample II")):
            D = mc_data[s]
            sp_labels = np.array([species_label(p) for p in D["pdg"]])
            for sp, sp_label, color in (("p","Proton truth only",CAT[0]),
                                         ("d","Deuteron truth only",CAT[5]),
                                         ("all","All species (color-coded)","multi")):
                fig, ax = plt.subplots(figsize=(8, 7))
                if sp == "all":
                    for species, c, lbl in (("p",CAT[0],"proton"),("d",CAT[5],"deuteron"),
                                             ("alpha",CAT[1],"alpha"),("heavy",CAT[3],"heavy/C12"),
                                             ("other",CAT[2],"other")):
                        m = sp_labels == species
                        if m.sum() > 10:
                            n_pts = min(5000, m.sum())
                            idx = np.random.choice(np.where(m)[0], n_pts, replace=False)
                            ax.scatter(D["deltaE"][idx], D["E_4layer"][idx], s=2, alpha=0.35,
                                      color=c, label=lbl, rasterized=True)
                    ax.legend(fontsize=8, markerscale=3)
                else:
                    m = sp_labels == sp
                    n_pts = min(5000, m.sum())
                    if n_pts > 0:
                        idx = np.random.choice(np.where(m)[0], n_pts, replace=False)
                        ax.scatter(D["deltaE"][idx], D["E_4layer"][idx], s=3, alpha=0.4,
                                  color=color, rasterized=True)
                ax.set_xlabel("Delta E = Edep(B2) [MeV]", fontsize=11)
                ax.set_ylabel("Residual E = Edep(B4+B6+B8) [MeV]", fontsize=11)
                ax.set_title(f"MC {slabel} — Delta E vs Residual E\n{sp_label} (n={m.sum() if sp!='all' else len(D['pdg']):,})",
                            fontsize=12, fontweight="bold")
                fig.tight_layout()
                fig.savefig(f"{args.out}/mc_{s}_deltaE_E_{sp}.png", dpi=300)
                plt.close(fig)

        # ── Data Delta E vs E amplitude proxies ────────────────────────
        for s, slabel in (("I","Sample I"), ("II","Sample II")):
            sub = df[df["sample"]==s]
            b2 = sub[sub["stave"]=="B2"][["eventno","amplitude_adc"]].rename(columns={"amplitude_adc":"amp_B2"})
            b4 = sub[sub["stave"]=="B4"][["eventno","amplitude_adc"]].rename(columns={"amplitude_adc":"amp_B4"})
            b6 = sub[sub["stave"]=="B6"][["eventno","amplitude_adc"]].rename(columns={"amplitude_adc":"amp_B6"})
            b8 = sub[sub["stave"]=="B8"][["eventno","amplitude_adc"]].rename(columns={"amplitude_adc":"amp_B8"})
            merged = b2.merge(b4,on="eventno",how="left").merge(b6,on="eventno",how="left").merge(b8,on="eventno",how="left").fillna(0)
            de = merged["amp_B2"].values
            er = merged["amp_B4"].values + merged["amp_B6"].values + merged["amp_B8"].values

            fig, ax = plt.subplots(figsize=(8, 7))
            n_pts = min(8000, len(de))
            idx = np.random.choice(len(de), n_pts, replace=False)
            ax.scatter(de[idx], er[idx], s=2, alpha=0.3, color=CAT[0], rasterized=True)
            ax.axvline(7000, color="gray", linestyle=":", linewidth=1.2, alpha=0.6)
            ax.text(7200, ax.get_ylim()[1]*0.85, "B2 saturation\n(7000 ADC)", fontsize=8, color="gray")
            ax.set_xlabel("Delta E proxy = amplitude(B2) [ADC]", fontsize=11)
            ax.set_ylabel("Residual E proxy = amplitude(B4+B6+B8) [ADC]", fontsize=11)
            ax.set_title(f"DATA {slabel} — Delta E vs Residual E\n(amplitude proxies, NOT calibrated energy)\nn={len(merged):,} events", fontsize=12, fontweight="bold")
            ax.set_xlim(0, 14000); ax.set_ylim(0, max(er.max(), 8000))
            fig.tight_layout()
            fig.savefig(f"{args.out}/data_{s}_deltaE_E_proxy.png", dpi=300)
            plt.close(fig)

        # ── MC Penetration plots (default threshold = args.stop_thresholds[0]) ──
        default_mc_th = args.stop_thresholds[0]
        for s, slabel in (("I","Sample I"), ("II","Sample II")):
            D = mc_data[s]; sp_labels = np.array([species_label(p) for p in D["pdg"]])
            sl_pen = mc_stop_layers[s][default_mc_th]
            # Proton + deuteron overlaid, normalized
            fig, ax = plt.subplots(figsize=(8, 5))
            for sp, color, label in (("p",CAT[0],"proton"),("d",CAT[5],"deuteron")):
                m = sp_labels == sp
                if m.sum() > 10:
                    sl = sl_pen[m]
                    layers = np.arange(8)
                    frac = [(sl == l).sum()/m.sum() for l in layers]
                    ax.plot(layers, frac, "o-", color=color, linewidth=2, markersize=6, label=label)
            ax.set_xlabel("Stopping layer (0=B2, 1=B4, 2=B6, 3=B8, ...)", fontsize=11)
            ax.set_ylabel("Fraction of tracks", fontsize=11)
            ax.set_title(f"MC {slabel} — Penetration Depth: Proton vs Deuteron\n(threshold={default_mc_th} MeV)", fontsize=12, fontweight="bold")
            ax.legend(); ax.grid(True, alpha=0.3)
            fig.tight_layout(); fig.savefig(f"{args.out}/mc_{s}_penetration_p_d.png", dpi=300); plt.close(fig)

            # Cumulative P(reaches layer)
            fig, ax = plt.subplots(figsize=(8, 5))
            for sp, color, label in (("p",CAT[0],"proton"),("d",CAT[5],"deuteron"),("all","#333","all particles")):
                m = sp_labels == sp if sp != "all" else np.ones(len(D["pdg"]),dtype=bool)
                if m.sum() > 10:
                    sl = sl_pen[m] if sp != "all" else sl_pen
                    layers = np.arange(8)
                    cumul = [(sl >= l).sum()/m.sum() for l in layers]
                    ax.plot(layers, cumul, "o-", color=color, linewidth=2, markersize=6, label=label)
            ax.set_xlabel("Layer L", fontsize=11)
            ax.set_ylabel("P(reaches layer L)", fontsize=11)
            ax.set_title(f"MC {slabel} — Cumulative Penetration Probability\n(threshold={default_mc_th} MeV)", fontsize=12, fontweight="bold")
            ax.legend(); ax.grid(True, alpha=0.3)
            fig.tight_layout(); fig.savefig(f"{args.out}/mc_{s}_cumulative_penetration.png", dpi=300); plt.close(fig)

        # ── Data penetration overlay ────────────────────────────────────
        fig, ax = plt.subplots(figsize=(8, 5))
        for s, color, label in (("I",CAT[0],"Sample I"),("II",CAT[5],"Sample II")):
            ds = data_summary[s]
            fracs = [ds["deepest_stave_fracs"][st] for st in ["B2","B4","B6","B8"]]
            ax.plot(range(4), fracs, "o-", color=color, linewidth=2, markersize=8, label=label)
        ax.set_xticks(range(4)); ax.set_xticklabels(["B2","B4","B6","B8"])
        ax.set_xlabel("Deepest active stave"); ax.set_ylabel("Fraction of events")
        ax.set_title("DATA — Deepest Active Stave Distribution\nSample I vs Sample II (normalized)", fontsize=12, fontweight="bold")
        ax.legend(); ax.grid(True, alpha=0.3)
        fig.tight_layout(); fig.savefig(f"{args.out}/data_penetration_overlay.png", dpi=300); plt.close(fig)

    except Exception as e:
        print(f"[plot_error] {e}", file=sys.stderr)

    # ── Save all results ───────────────────────────────────────────────
    out_data = {
        "mc_file": os.path.abspath(args.mc),
        "data_table": os.path.abspath(args.data_table),
        "trigger_counts": {"enter_B": n_enterB, "enter_A": n_enterA, "coincidence_AB": n_coinc},
        "mc_summary": mc_summary,
        "data_summary": data_summary,
        "note": "MC: Delta E = Edep(B2), Residual E = Edep(B4+B6+B8). Data: amplitude proxies, NOT calibrated energy. Per Dave's spec (Issue #618).",
    }
    with open(f"{args.out}/supervisor_deltaE_E_summary.json", "w") as f:
        json.dump(out_data, f, indent=2, default=str)

    print(f"[ok] {args.out}/supervisor_deltaE_E_summary.json")
    for s in ("I","II"):
        ds = data_summary[s]
        print(f"  DATA {s}: n={ds['n_events']}, deltaE_med={ds['deltaE_median_ADC']:.0f}, "
              f"Eres_med={ds['Eres_median_ADC']:.0f}, sat_B2={ds['frac_saturated_B2']:.1%}")
    for s in ("I","II"):
        for sp in ["p","d","all"]:
            if sp in mc_summary[s] and "n_events" in mc_summary[s][sp]:
                ms = mc_summary[s][sp]
                st = ms["stop_threshold_stats"][str(args.stop_thresholds[0])]
                print(f"  MC {s} {sp}: n={ms['n_events']}, deltaE_med={ms['deltaE_median_MeV']:.1f}, "
                      f"stop_B2={st['frac_stop_B2']:.1%}, reach_B8={st['frac_reach_B8']:.1%}")

if __name__ == "__main__":
    main()
