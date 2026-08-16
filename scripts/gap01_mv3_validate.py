#!/usr/bin/env python3
"""
GAP-01 MV3 validation: before/after stopping-depth comparison.

Compares the original Krakau MC (output_krakow_1M.root, no upstream material)
against the GAP-01 fix MC (with inter-stave dead material + upstream absorber),
both against the CCB test-beam data.  Uses the identical MV3 v3 threshold-corrected
methodology (scripts/mv3_stopping_v3.py).
"""
import argparse, json, os, sys
from datetime import datetime, timezone
import numpy as np
import pandas as pd

STAVES = ["B2", "B4", "B6", "B8"]
LAYER_TO_STAVE_IDX = {0:0, 1:0, 2:1, 3:1, 4:2, 5:2, 6:3, 7:3}
B_ARM = 1
CHARGED_PDGS = {2212, 1000010020, 11, 13, 211, 321}
GAIN = 92.0
PEAK_FRAC = 0.7330
THRESHOLD = 1000.0


def mc_stopping(mc_path, tree="hibeam", max_events=0, label=""):
    import uproot
    br = ["Sci_bar_TrackID","Sci_bar_LayerID1","Sci_bar_PDG","Sci_bar_EDep","Sci_bar_LayerID"]
    t = uproot.open(mc_path)[tree]
    stop = max_events if max_events > 0 else None
    last_staves = []; n_below = 0; ev_count = 0
    for ch in t.iterate(br, step_size="200 MB", library="np", entry_stop=stop):
        TID, L1, PD, ED, LY = (ch[k] for k in br)
        for i in range(len(L1)):
            ev_count += 1
            l1 = L1[i]
            if len(l1) == 0: continue
            isB = l1 == B_ARM
            if not isB.any(): continue
            tid, pd, ed, ly = TID[i], PD[i], ED[i], LY[i]
            for tr in np.unique(tid[isB]):
                m = isB & (tid == tr)
                if abs(int(pd[m][0])) not in CHARGED_PDGS: continue
                edep_hits = ed[m].astype(float)
                if edep_hits.sum() <= 0: continue
                layer_hits = ly[m].astype(int)
                edep_stave = np.zeros(4)
                for lyr, e in zip(layer_hits, edep_hits):
                    si = LAYER_TO_STAVE_IDX.get(int(lyr), -1)
                    if si >= 0: edep_stave[si] += e
                peak_adc = edep_stave * GAIN * PEAK_FRAC
                above = np.where(peak_adc > THRESHOLD)[0]
                if above.size == 0:
                    n_below += 1; continue
                last_staves.append(STAVES[int(above.max())])
    counts = {s: last_staves.count(s) for s in STAVES}
    total = sum(counts.values())
    fracs = {s: counts[s]/total if total > 0 else 0 for s in STAVES}
    print(f"[{label}] events={ev_count} above_threshold={total} below={n_below}")
    print(f"[{label}] fracs: " + "  ".join(f"{s}={fracs[s]:.3f}" for s in STAVES))
    return {"counts":counts, "fractions":fracs, "n_above":total, "n_below":n_below}


def data_stopping(data_csv):
    df = pd.read_csv(data_csv)
    df["net_adc"] = (df["amplitude_adc"] - df["baseline_adc"]).abs()
    df = df[df["net_adc"] > THRESHOLD]
    rank = {"B2":0,"B4":1,"B6":2,"B8":3}
    df["rank"] = df["stave"].map(rank)
    ev_deep = df.groupby(["run","evt"])["rank"].max().reset_index()
    r2s = {v:k for k,v in rank.items()}
    ev_deep["last"] = ev_deep["rank"].map(r2s)
    counts = {s: int((ev_deep["last"]==s).sum()) for s in STAVES}
    total = sum(counts.values())
    fracs = {s: counts[s]/total if total > 0 else 0 for s in STAVES}
    print(f"[data] n={total} fracs: " + "  ".join(f"{s}={fracs[s]:.3f}" for s in STAVES))
    return {"counts":counts, "fractions":fracs, "n":total}


def chi2(mc_res, data_res):
    mc_f = np.array([mc_res["fractions"][s] for s in STAVES])
    observed = np.array([data_res["counts"].get(s,0) for s in STAVES], float)
    expected = mc_f * data_res["n"]
    with np.errstate(invalid="ignore", divide="ignore"):
        chi2_val = float(np.nansum((observed - expected)**2 / np.where(expected>0, expected, np.nan)))
    ndf = int(sum(mc_f > 0)) - 1
    return chi2_val, ndf


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--mc-old", required=True)
    ap.add_argument("--mc-new", required=True)
    ap.add_argument("--data", required=True)
    ap.add_argument("--out", required=True)
    args = ap.parse_args()
    os.makedirs(args.out, exist_ok=True)

    print("=== GAP-01 MV3 Stopping-Depth Validation ===")
    old = mc_stopping(args.mc_old, label="MC_OLD")
    new = mc_stopping(args.mc_new, label="MC_NEW")
    data = data_stopping(args.data)

    chi2_old, ndf_old = chi2(old, data)
    chi2_new, ndf_new = chi2(new, data)

    print(f"\n=== RESULTS ===")
    print(f"OLD MC chi2/ndf = {chi2_old:.1f}/{ndf_old} = {chi2_old/max(ndf_old,1):.1f}")
    print(f"NEW MC chi2/ndf = {chi2_new:.1f}/{ndf_new} = {chi2_new/max(ndf_new,1):.1f}")
    improvement = chi2_old/max(ndf_old,1) / max(chi2_new/max(ndf_new,1), 1e-10)
    print(f"Improvement factor: {improvement:.1f}x")

    summary = {
        "study": "GAP-01 MV3 validation",
        "generated_utc": datetime.now(timezone.utc).isoformat(),
        "mc_old": args.mc_old, "mc_new": args.mc_new,
        "old_chi2_ndf": chi2_old/max(ndf_old,1),
        "new_chi2_ndf": chi2_new/max(ndf_new,1),
        "improvement_factor": improvement,
        "old_fractions": old["fractions"], "new_fractions": new["fractions"],
        "data_fractions": data["fractions"],
    }
    with open(os.path.join(args.out, "gap01_mv3_summary.json"), "w") as f:
        json.dump(summary, f, indent=2)

    # Plot
    import matplotlib; matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    x = np.arange(4); w = 0.25
    fig, ax = plt.subplots(figsize=(8,5))
    ax.bar(x - w, [data["fractions"][s] for s in STAVES], w, label="Data", color="#2ecc71")
    ax.bar(x,     [old["fractions"][s] for s in STAVES], w, label=f"MC old (χ²/ndf={chi2_old/max(ndf_old,1):.0f})", color="#e74c3c")
    ax.bar(x + w, [new["fractions"][s] for s in STAVES], w, label=f"MC GAP-01 (χ²/ndf={chi2_new/max(ndf_new,1):.0f})", color="#3498db")
    ax.set_xticks(x); ax.set_xticklabels(STAVES)
    ax.set_xlabel("Deepest stave fired (B-arm stopping depth)")
    ax.set_ylabel("Fraction of tracks")
    ax.set_title("GAP-01: Stopping-depth before/after upstream material fix")
    ax.legend()
    plt.tight_layout()
    plt.savefig(os.path.join(args.out, "gap01_stopping_depth_comparison.png"), dpi=150)
    print(f"Plot saved to {args.out}/gap01_stopping_depth_comparison.png")

if __name__ == "__main__":
    main()
