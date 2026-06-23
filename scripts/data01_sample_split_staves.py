#!/usr/bin/env python3
"""
data01_sample_split_staves.py
=============================
DATA side of the Sample I / Sample II comparison (CCB test beam, B-stack).

In DATA the trigger is the *hardware* trigger, already encoded by run range in
the `group` column of the selected-pulse table:
    sample_i_*   -> coincidence trigger (A & B)   [Sample I]
    sample_ii_*  -> single B trigger              [Sample II]
We use the *_analysis groups (calibration runs excluded) by default.

Per the supervisor's task (1): study the differences between stave outputs for
Sample I and II.  The headline is the first B layer (stave B2): Sample I should
show large pulses (early stopping / Bragg, deuteron-enriched per MC) that Sample
II does not.

Columns: run, group, eventno, evt, stave, channel, baseline_adc,
         amplitude_adc, peak_sample, area_adc_samples

Usage:
  python3 data01_sample_split_staves.py --table s00_selected_b_pulses.csv.gz --out <dir>
"""
import argparse, json, os
import numpy as np
import pandas as pd

STAVES = ["B2", "B4", "B6", "B8"]   # B2 = first (upstream) layer

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--table", required=True, help="s00_selected_b_pulses.csv.gz")
    ap.add_argument("--out", required=True)
    ap.add_argument("--include-calib", action="store_true",
                    help="include *_calib groups (default: analysis only)")
    ap.add_argument("--large-adc", type=float, default=6000.0,
                    help="amplitude threshold defining a 'large pulse'")
    ap.add_argument("--sat-adc", type=float, default=7000.0,
                    help="approximate B2 saturation ceiling")
    args = ap.parse_args()
    os.makedirs(args.out, exist_ok=True)

    df = pd.read_csv(args.table)
    df["sample"] = np.where(df["group"].str.startswith("sample_i_"), "I",
                     np.where(df["group"].str.startswith("sample_ii_"), "II", "other"))
    if not args.include_calib:
        df = df[df["group"].str.endswith("_analysis")].copy()

    out = {"table": os.path.abspath(args.table),
           "include_calib": args.include_calib,
           "large_adc": args.large_adc, "sat_adc": args.sat_adc,
           "n_pulses": int(len(df)),
           "per_sample": {}}

    for s in ("I", "II"):
        sub = df[df["sample"] == s]
        rec = {"n_pulses": int(len(sub)),
               "runs": sorted(int(r) for r in sub["run"].unique()),
               "staves": {}}
        for st in STAVES:
            a = sub.loc[sub["stave"] == st, "amplitude_adc"].to_numpy(dtype=float)
            if a.size == 0:
                rec["staves"][st] = {"n": 0}
                continue
            rec["staves"][st] = {
                "n": int(a.size),
                "mean_adc": float(a.mean()),
                "median_adc": float(np.median(a)),
                "p95_adc": float(np.percentile(a, 95)),
                "frac_large": float((a > args.large_adc).mean()),
                "frac_saturated": float((a >= args.sat_adc).mean()),
            }
        # depth profile (fraction of this sample's pulses in each stave)
        tot = len(sub) or 1
        rec["depth_fraction"] = {st: round(int((sub["stave"] == st).sum()) / tot, 4)
                                 for st in STAVES}
        out["per_sample"][s] = rec

    # headline: first B layer (B2)
    b2I = out["per_sample"]["I"]["staves"]["B2"]
    b2II = out["per_sample"]["II"]["staves"]["B2"]
    out["headline_first_B_layer_B2"] = {
        "sampleI_n": b2I.get("n", 0), "sampleII_n": b2II.get("n", 0),
        "sampleI_mean_adc": b2I.get("mean_adc", 0.0),
        "sampleII_mean_adc": b2II.get("mean_adc", 0.0),
        "sampleI_frac_large": b2I.get("frac_large", 0.0),
        "sampleII_frac_large": b2II.get("frac_large", 0.0),
        "sampleI_frac_saturated": b2I.get("frac_saturated", 0.0),
        "sampleII_frac_saturated": b2II.get("frac_saturated", 0.0),
    }

    with open(os.path.join(args.out, "data_sample_split_summary.json"), "w") as fh:
        json.dump(out, fh, indent=2)

    # save B2 amplitude arrays for the data/MC overlay
    np.savez_compressed(
        os.path.join(args.out, "first_B_layer_B2_amplitude.npz"),
        sampleI=df[(df["sample"] == "I") & (df["stave"] == "B2")]["amplitude_adc"].to_numpy(np.float32),
        sampleII=df[(df["sample"] == "II") & (df["stave"] == "B2")]["amplitude_adc"].to_numpy(np.float32),
    )

    print(json.dumps(out["headline_first_B_layer_B2"], indent=2))
    print(f"[ok] wrote {args.out}/data_sample_split_summary.json")

if __name__ == "__main__":
    main()
