#!/usr/bin/env python3
"""validate_scatter_fix.py -- CL-021 MV3 scattering-model validation.

Compares stopping-depth fractions + dE-E correlation for:
  - MC control (uniform CM sampling, GAP-01 inter-stave geometry)
  - MC fix     (cross-section-weighted CM sampling, same geometry)
  - Data       (Sample-I trigger matching)

The primary metric is the B2 stopping fraction (data ~0.93-0.94). The residual
under the OLD uniform sampling was the identified MV3 gap; this script measures
whether sampling theta_cm from p(theta) ~ sigma(theta)*sin(theta) closes it.
"""
import argparse, json, os
from datetime import datetime, timezone
import numpy as np
import pandas as pd

LAYER_TO_STAVE_IDX = {0: 0, 1: 0, 2: 1, 3: 1, 4: 2, 5: 2, 6: 3, 7: 3}
STAVES = ["B2", "B4", "B6", "B8"]
B_ARM = 1
CHARGED_PDGS = {2212, 1000010020, 11, 13, 211, 321}
GAIN = 92.0           # ADC/MeV (MV0 v2 median matching)
PEAK_FRAC = 0.7330    # peak-bin fraction (tau_r=2.5ns, tau_d=42ns)
THRESHOLD = 1000.0    # ADC (data selection)


def mc_fractions_and_dEe(mc_path, tree="hibeam"):
    import uproot
    br = ["Sci_bar_TrackID", "Sci_bar_LayerID1", "Sci_bar_PDG",
          "Sci_bar_EDep", "Sci_bar_LayerID"]
    t = uproot.open(mc_path)[tree]
    last_staves = []
    dE_list, E_list = [], []
    n_below = 0
    for ch in t.iterate(br, step_size="200 MB", library="np"):
        TID = ch["Sci_bar_TrackID"]; L1 = ch["Sci_bar_LayerID1"]
        PD = ch["Sci_bar_PDG"]; ED = ch["Sci_bar_EDep"]; LY = ch["Sci_bar_LayerID"]
        for i in range(len(L1)):
            l1 = L1[i]
            if len(l1) == 0:
                continue
            isB = l1 == B_ARM
            if not isB.any():
                continue
            tid = TID[i]; pd = PD[i]; ed = ED[i]; ly = LY[i]
            for tr in np.unique(tid[isB]):
                m = isB & (tid == tr)
                pdg0 = abs(int(pd[m][0]))
                if pdg0 not in CHARGED_PDGS:
                    continue
                edep_hits = ed[m].astype(float)
                if edep_hits.sum() <= 0:
                    continue
                layer_hits = ly[m].astype(int)
                edep_stave = np.zeros(4)
                edep_layer = {}
                for lyr, e in zip(layer_hits, edep_hits):
                    si = LAYER_TO_STAVE_IDX.get(int(lyr), -1)
                    if si >= 0:
                        edep_stave[si] += e
                    edep_layer[int(lyr)] = edep_layer.get(int(lyr), 0.0) + e
                peak_adc = edep_stave * GAIN * PEAK_FRAC
                above = np.where(peak_adc > THRESHOLD)[0]
                if above.size == 0:
                    n_below += 1
                    continue
                last_si = int(above.max())
                last_staves.append(STAVES[last_si])
                # dE-E: dE = edep in layer 0 (first stave, thin dE detector);
                #        E  = residual edep in layers 1-7 (rest of range telescope).
                dE_list.append(edep_layer.get(0, 0.0))
                E_list.append(sum(edep_layer.get(k, 0.0) for k in range(1, 8)))
    counts = {s: last_staves.count(s) for s in STAVES}
    total = sum(counts.values())
    fracs = {s: counts[s] / total if total > 0 else 0 for s in STAVES}
    if len(dE_list) > 10:
        dEe = float(np.corrcoef(dE_list, E_list)[0, 1])
    else:
        dEe = float("nan")
    print(f"  n_above={total}  n_below={n_below}  dE-E corr={dEe:+.3f} (n={len(dE_list)})  "
          + "  ".join(f"{s}={fracs[s]:.3f}" for s in STAVES))
    return {"counts": counts, "fractions": fracs, "n_above": total,
            "n_below": n_below, "dEe_corr": dEe, "n_dEe": len(dE_list)}


def data_fractions(data_csv):
    df = pd.read_csv(data_csv)
    df["net_adc"] = (df["amplitude_adc"] - df["baseline_adc"]).abs()
    df = df[df["net_adc"] > THRESHOLD]
    stave_rank = {"B2": 0, "B4": 1, "B6": 2, "B8": 3}
    df["stave_rank"] = df["stave"].map(stave_rank)
    out = {}
    for name, sub in [
        ("all", df),
        ("sample_i", df[df["group"].str.contains("sample_i") & ~df["group"].str.contains("sample_ii")]),
    ]:
        if len(sub) == 0:
            out[name] = {"fractions": {s: 0 for s in STAVES}, "counts": {s: 0 for s in STAVES}, "n_events": 0}
            continue
        ev = sub.groupby(["run", "evt"])["stave_rank"].max().reset_index()
        r2s = {v: k for k, v in stave_rank.items()}
        ev["last_stave"] = ev["stave_rank"].map(r2s)
        counts = {s: int((ev["last_stave"] == s).sum()) for s in STAVES}
        total = sum(counts.values())
        fracs = {s: counts[s] / total if total > 0 else 0 for s in STAVES}
        out[name] = {"fractions": fracs, "counts": counts, "n_events": total}
        print(f"  data[{name}] n={total}  " + "  ".join(f"{s}={fracs[s]:.3f}" for s in STAVES))
    return out


def chi2_vs(mc_res, data_res):
    mc_f = np.array([mc_res["fractions"][s] for s in STAVES])
    n_data = data_res["n_events"]
    obs = np.array([data_res["counts"].get(s, 0) for s in STAVES], dtype=float)
    exp = mc_f * n_data
    with np.errstate(invalid="ignore", divide="ignore"):
        chi2 = float(np.nansum((obs - exp) ** 2 / np.where(exp > 0, exp, np.nan)))
    ndf = int(sum(mc_f > 0)) - 1
    return chi2, ndf


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--mc-control", required=True, help="uniform-sampling MC (GAP-01 geometry)")
    ap.add_argument("--mc-fix", required=True, help="CS-weighted-sampling MC (same geometry)")
    ap.add_argument("--data", required=True)
    ap.add_argument("--out", required=True)
    args = ap.parse_args()
    os.makedirs(args.out, exist_ok=True)
    stamp = datetime.now(timezone.utc).isoformat()

    print("[control] uniform CM sampling:")
    ctrl = mc_fractions_and_dEe(args.mc_control)
    print("[fix] cross-section-weighted CM sampling:")
    fix = mc_fractions_and_dEe(args.mc_fix)
    print("[data] Sample-I trigger matching:")
    data = data_fractions(args.data)

    ctrl_chi2, ctrl_ndf = chi2_vs(ctrl, data["sample_i"])
    fix_chi2, fix_ndf = chi2_vs(fix, data["sample_i"])

    b2_ctrl = ctrl["fractions"]["B2"]
    b2_fix = fix["fractions"]["B2"]
    b2_data = data["sample_i"]["fractions"]["B2"]

    print("\n=== SUMMARY (vs Data Sample-I) ===")
    print(f"  B2:  control={b2_ctrl:.3f}  fix={b2_fix:.3f}  data={b2_data:.3f}")
    print(f"  B2 deficit: control={100*(b2_data-b2_ctrl):+.1f} pp  fix={100*(b2_data-b2_fix):+.1f} pp")
    print(f"  chi2/ndf:   control={ctrl_chi2/max(ctrl_ndf,1):.1f}  fix={fix_chi2/max(fix_ndf,1):.1f}")
    print(f"  dE-E corr:  control={ctrl['dEe_corr']:+.3f}  fix={fix['dEe_corr']:+.3f}")

    summary = {
        "study": "CL-021 MV3 scattering-model fix validation",
        "generated_utc": stamp,
        "mc_control": args.mc_control, "mc_fix": args.mc_fix,
        "control": ctrl, "fix": fix, "data": data,
        "chi2_control_vs_sample_i": ctrl_chi2, "chi2_fix_vs_sample_i": fix_chi2,
        "b2_control": b2_ctrl, "b2_fix": b2_fix, "b2_data_sample_i": b2_data,
        "b2_deficit_pp_control": 100 * (b2_data - b2_ctrl),
        "b2_deficit_pp_fix": 100 * (b2_data - b2_fix),
        "dEe_corr_control": ctrl["dEe_corr"], "dEe_corr_fix": fix["dEe_corr"],
    }
    with open(os.path.join(args.out, "scatter_validation_summary.json"), "w") as fh:
        json.dump(summary, fh, indent=2)

    # Combined bar plot
    try:
        import matplotlib; matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(14, 5.5))
        x = np.arange(4); w = 0.25
        sets = [
            ("MC control (uniform)", [ctrl["fractions"][s] for s in STAVES], "#d62728"),
            ("MC fix (CS-weighted)", [fix["fractions"][s] for s in STAVES], "#2ca02c"),
            ("Data Sample-I", [data["sample_i"]["fractions"][s] for s in STAVES], "#1f77b4"),
        ]
        for k, (lbl, vals, c) in enumerate(sets):
            ax1.bar(x + (k - 1) * w, vals, width=w, label=lbl, color=c, alpha=0.85, edgecolor="k", linewidth=0.5)
        ax1.set_xticks(x); ax1.set_xticklabels(STAVES)
        ax1.set_xlabel("Last stave above threshold (stopping depth)")
        ax1.set_ylabel("Fraction of tracks / events")
        ax1.set_title(f"Stopping-depth fractions\nB2: ctrl={b2_ctrl:.3f} fix={b2_fix:.3f} data={b2_data:.3f}")
        ax1.legend(fontsize=9); ax1.set_ylim(0, 1.05); ax1.grid(axis="y", lw=0.4, alpha=0.4)

        # dE-E correlation bars
        ax2.bar(["control\n(uniform)", "fix\n(CS-weighted)", "data\n(target)"],
                [ctrl["dEe_corr"], fix["dEe_corr"], 0.18],
                color=["#d62728", "#2ca02c", "#1f77b4"], alpha=0.85, edgecolor="k", linewidth=0.5)
        ax2.axhline(0, color="k", lw=0.8)
        ax2.axhline(0.18, color="#1f77b4", ls="--", lw=1, alpha=0.6, label="data ~+0.18")
        ax2.set_ylabel("Pearson r(dE, E)")
        ax2.set_title(f"dE-E correlation\ndE=layer0 edep, E=layers1-7 edep")
        ax2.legend(fontsize=9); ax2.grid(axis="y", lw=0.4, alpha=0.4)

        fig.suptitle("CL-021: p+CD2 cross-section-weighted CM scattering (inverse-CDF) vs uniform",
                     fontsize=12, y=1.02)
        fig.tight_layout()
        pp = os.path.join(args.out, "scatter_validation.png")
        fig.savefig(pp, dpi=150, bbox_inches="tight"); plt.close(fig)
        print(f"\n[plot] wrote {pp}")
    except Exception as e:
        print(f"[plot] failed: {e}")


if __name__ == "__main__":
    main()
