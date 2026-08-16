#!/usr/bin/env python3
"""
mv3_stopping_v3.py
==================
MV3 v3 -- per-stave stopping-fraction comparison with MC amplitude threshold applied.

Corrects v2: v2 counted all MC tracks regardless of predicted amplitude.
In data, only staves with net_adc > 1000 are visible. Through-going protons
deposit ~1-2 MeV per stave → predicted peak_adc ≈ 80-160 ADC (below threshold),
making them invisible in data. v3 applies the threshold in MC:
  peak_adc_stave = gain * edep_stave * peak_frac; include stave only if > threshold.

Layer→stave: {0,1}→B2, {2,3}→B4, {4,5}→B6, {6,7}→B8.
"""
import argparse, json, os
from datetime import datetime, timezone

import numpy as np
import pandas as pd

LAYER_TO_STAVE_IDX = {0: 0, 1: 0, 2: 1, 3: 1, 4: 2, 5: 2, 6: 3, 7: 3}
STAVES = ["B2", "B4", "B6", "B8"]
B_ARM = 1
CHARGED_PDGS = {2212, 1000010020, 11, 13, 211, 321}
# Digitizer defaults
GAIN_DEFAULT = 92.0      # ADC/MeV (from MV0 v2 median matching)
PEAK_FRAC = 0.7330       # peak bin fraction: tau_r=2.5ns, tau_d=42ns
THRESHOLD_NET = 1000.0   # ADC (same as data selection)


def mc_stopping_fractions_threshold(mc_path, tree="hibeam", max_events=0,
                                     gain=GAIN_DEFAULT, peak_frac=PEAK_FRAC,
                                     threshold=THRESHOLD_NET):
    """
    MC stopping fraction with amplitude threshold applied per-stave.
    Only staves where predicted peak_adc > threshold are counted as 'fired'.
    last_stave = deepest fired stave. Tracks with no stave above threshold are excluded.
    """
    import uproot
    br = ["Sci_bar_TrackID", "Sci_bar_LayerID1", "Sci_bar_PDG",
          "Sci_bar_EDep", "Sci_bar_LayerID"]
    tree_obj = uproot.open(mc_path)[tree]
    stop = max_events if max_events > 0 else None

    ev_count = 0
    last_staves = []
    n_below_threshold = 0

    for ch in tree_obj.iterate(br, step_size="200 MB", library="np", entry_stop=stop):
        TID = ch["Sci_bar_TrackID"]
        L1 = ch["Sci_bar_LayerID1"]
        PD = ch["Sci_bar_PDG"]
        ED = ch["Sci_bar_EDep"]
        LY = ch["Sci_bar_LayerID"]

        for i in range(len(L1)):
            ev_count += 1
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

                # per-stave EDep: sum over both layers
                edep_stave = np.zeros(4)
                for lyr, e in zip(layer_hits, edep_hits):
                    si = LAYER_TO_STAVE_IDX.get(int(lyr), -1)
                    if si >= 0:
                        edep_stave[si] += e

                # predicted peak ADC per stave
                peak_adc = edep_stave * gain * peak_frac

                # staves above threshold
                above = np.where(peak_adc > threshold)[0]
                if above.size == 0:
                    n_below_threshold += 1
                    continue
                # last (deepest) stave above threshold
                last_si = int(above.max())
                last_staves.append(STAVES[last_si])

    n_tot = len(last_staves) + n_below_threshold
    print(f"[mc_v3] events={ev_count}, charged_B_tracks={n_tot}, "
          f"above_threshold={len(last_staves)} ({100*len(last_staves)/max(n_tot,1):.1f}%), "
          f"below_threshold={n_below_threshold}")

    counts = {s: last_staves.count(s) for s in STAVES}
    total = sum(counts.values())
    fracs = {s: counts[s] / total if total > 0 else 0 for s in STAVES}
    return {
        "counts": counts, "fractions": fracs,
        "n_above_threshold": total, "n_below_threshold": n_below_threshold,
        "n_total_charged": n_tot, "threshold_adc": threshold,
        "gain_adc_per_mev": gain, "peak_frac": peak_frac
    }


def _net_amplitude(df: pd.DataFrame) -> pd.Series:
    """Return the baseline-subtracted (net) pulse amplitude per row.

    Per docs/contracts/PULSE_TABLE_CONTRACT.md the canonical net field is
    ``peak_height_adc``; the legacy ``amplitude_adc`` is ALREADY produced as
    ``max(waveform - baseline)`` by scripts/01_build_pulse_table_from_root.py
    (baseline already removed). Subtracting ``baseline_adc`` again is the
    A-001 double-subtraction bug. This helper NEVER subtracts baseline_adc.
    """
    if "peak_height_adc" in df.columns:
        return df["peak_height_adc"].abs()
    # amplitude_adc is net per producer code (PulseTable contract v1).
    return df["amplitude_adc"].abs()


def data_stopping_fractions(data_csv, threshold_net=THRESHOLD_NET):
    """Per-event deepest stave with net_adc > threshold.

    ``net_adc`` is the contract net amplitude (peak_height_adc if present,
    else the already-baseline-subtracted amplitude_adc). It is NOT re-derived
    by subtracting baseline_adc (that is the A-001 double-subtraction bug).
    """
    df = pd.read_csv(data_csv)
    df["net_adc"] = _net_amplitude(df)
    df = df[df["net_adc"] > threshold_net]

    stave_rank = {"B2": 0, "B4": 1, "B6": 2, "B8": 3}
    df["stave_rank"] = df["stave"].map(stave_rank)

    results = {}
    # Exact categorical match: "sample_i_" prefix must NOT match "sample_ii_".
    sample = np.where(df["group"].str.startswith("sample_i_"), "I",
                      np.where(df["group"].str.startswith("sample_ii_"), "II", "other"))
    df = df.assign(sample=sample)
    groups = [
        ("all", df),
        ("sample_i",  df[df["sample"] == "I"]),
        ("sample_ii", df[df["sample"] == "II"]),
    ]
    for group_name, sub_group in groups:
        if len(sub_group) == 0:
            results[group_name] = {"fractions": {s: 0 for s in STAVES}, "n_events": 0}
            continue
        ev_deepest = sub_group.groupby(["run", "evt"])["stave_rank"].max().reset_index()
        rank_to_stave = {v: k for k, v in stave_rank.items()}
        ev_deepest["last_stave"] = ev_deepest["stave_rank"].map(rank_to_stave)
        counts = ev_deepest["last_stave"].value_counts().to_dict()
        counts = {s: counts.get(s, 0) for s in STAVES}
        total = sum(counts.values())
        fracs = {s: counts[s] / total if total > 0 else 0 for s in STAVES}
        results[group_name] = {"fractions": fracs, "n_events": total, "counts": counts}
        print(f"[data:{group_name}] n_events={total}  " +
              "  ".join(f"{s}={fracs[s]:.3f}" for s in STAVES))
    return results


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--mc", required=True)
    ap.add_argument("--data", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--tree", default="hibeam")
    ap.add_argument("--max-events", type=int, default=0)
    ap.add_argument("--gain", type=float, default=GAIN_DEFAULT)
    ap.add_argument("--peak-frac", type=float, default=PEAK_FRAC)
    ap.add_argument("--net-threshold", type=float, default=THRESHOLD_NET)
    args = ap.parse_args()
    os.makedirs(args.out, exist_ok=True)

    stamp = datetime.now(timezone.utc).isoformat()
    print(f"[mv3v3] start={stamp}")
    print(f"[mv3v3] gain={args.gain} ADC/MeV, peak_frac={args.peak_frac}, threshold={args.net_threshold} ADC")

    mc_res = mc_stopping_fractions_threshold(
        args.mc, args.tree, args.max_events,
        args.gain, args.peak_frac, args.net_threshold)
    data_res = data_stopping_fractions(args.data, args.net_threshold)

    mc_f = np.array([mc_res["fractions"][s] for s in STAVES])
    data_f = np.array([data_res["all"]["fractions"][s] for s in STAVES])
    n_data = data_res["all"]["n_events"]
    observed = np.array([data_res["all"]["counts"].get(s, 0) for s in STAVES], dtype=float)
    expected = mc_f * n_data
    with np.errstate(invalid="ignore", divide="ignore"):
        chi2 = float(np.nansum((observed - expected)**2 / np.where(expected > 0, expected, np.nan)))
    ndf = int(sum(mc_f > 0)) - 1

    print(f"[mv3v3] chi2={chi2:.1f} ndf={ndf} chi2/ndf={chi2/max(ndf,1):.2f}")
    print(f"[mv3v3] MC fracs: " + "  ".join(f"{s}={mc_res['fractions'][s]:.3f}" for s in STAVES))
    print(f"[mv3v3] Data(all): " + "  ".join(f"{s}={data_res['all']['fractions'][s]:.3f}" for s in STAVES))
    print(f"[mv3v3] Data(s_ii): " + "  ".join(f"{s}={data_res['sample_ii']['fractions'][s]:.3f}" for s in STAVES))

    verdict = "PASS" if chi2 / max(ndf, 1) < 5 else ("TENSION" if chi2 / max(ndf, 1) < 50 else "FAIL")
    summary = {
        "study_id": "MV3v3",
        "generated_utc": stamp,
        "mc_file": args.mc,
        "mc": mc_res,
        "data": data_res,
        "chi2_mc_vs_data_all": chi2,
        "chi2_ndf": ndf,
        "chi2_per_ndf": chi2 / max(ndf, 1),
        "verdict": verdict,
    }
    jpath = os.path.join(args.out, "mv3_summary.json")
    with open(jpath, "w") as fh:
        json.dump(summary, fh, indent=2)
    print(f"[mv3v3] wrote {jpath}")

    # Plot
    try:
        import matplotlib; matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        fig, ax = plt.subplots(figsize=(9, 5))
        x = np.arange(4); w = 0.2
        datasets = [
            ("MC (threshold applied)", [mc_res["fractions"][s] for s in STAVES], "C0"),
            ("Data (all)", [data_res["all"]["fractions"][s] for s in STAVES], "C1"),
            ("Data Sample-I", [data_res["sample_i"]["fractions"][s] for s in STAVES], "C2"),
            ("Data Sample-II", [data_res["sample_ii"]["fractions"][s] for s in STAVES], "C3"),
        ]
        for k, (label, vals, color) in enumerate(datasets):
            ax.bar(x + (k - 1.5) * w, vals, width=w, label=label, color=color, alpha=0.82, edgecolor="k", linewidth=0.5)
        ax.set_xticks(x); ax.set_xticklabels(STAVES)
        ax.set_xlabel("Last stave above threshold (stopping depth proxy)", fontsize=12)
        ax.set_ylabel("Fraction of tracks / events", fontsize=12)
        ax.set_title(f"MV3v3 — Stopping depth (χ²/ndf={chi2/max(ndf,1):.1f}, gain={args.gain:.0f} ADC/MeV)", fontsize=12)
        ax.legend(fontsize=10); ax.set_ylim(0, 1.05)
        for sp in ax.spines.values(): sp.set_linewidth(0.5)
        ax.grid(axis="y", lw=0.4, alpha=0.4)
        ppath = os.path.join(args.out, "mv3_stop_frac.png")
        fig.savefig(ppath, dpi=150, bbox_inches="tight"); plt.close(fig)
        print(f"[mv3v3] wrote {ppath}")
    except Exception as e:
        print(f"[mv3v3] plot: {e}")

    # REPORT.md
    rpath = os.path.join(args.out, "REPORT.md")
    with open(rpath, "w") as fh:
        fh.write(f"""# MV3 v3 — Stopping-Depth Fraction (threshold-corrected)

- status: **PRODUCTION (v3)**
- generated: {stamp}
- MC file: `{args.mc}`
- Data: `{os.path.basename(args.data)}`
- MC tracks above threshold: {mc_res["n_above_threshold"]}
  (below threshold: {mc_res["n_below_threshold"]} = {100*mc_res["n_below_threshold"]/max(mc_res["n_total_charged"],1):.1f}%)
- Data events: {data_res["all"]["n_events"]}
- **χ²/ndf = {chi2/max(ndf,1):.1f} → {verdict}**

## Methodology

For each event/track, the "stopping depth" is the deepest stave where the predicted
(MC) or measured (data) amplitude exceeds the selection threshold of {args.net_threshold:.0f} ADC net.

**MC threshold rule:**
`peak_adc = gain × edep_stave × peak_frac`; stave counted if `peak_adc > {args.net_threshold:.0f} ADC`.
- gain = {args.gain:.1f} ADC/MeV (from MV0 v2)
- peak_frac = {args.peak_frac:.4f} (digitizer model, τ_r=2.5 ns, τ_d=42 ns)
- Threshold EDep ≈ {args.net_threshold/(args.gain*args.peak_frac):.1f} MeV per stave

**v3 vs v2 correction:** v2 used all MC hits regardless of predicted amplitude.
Through-going protons deposit ~1.2 MeV in 2 × 3 mm of scintillator → peak ≈ {1.2*args.gain*args.peak_frac:.0f} ADC
(below threshold). v2 incorrectly counted these as "stopping" in the deepest traversed stave.
v3 removes {mc_res["n_below_threshold"]} such tracks ({100*mc_res["n_below_threshold"]/max(mc_res["n_total_charged"],1):.1f}% of all charged tracks) from the comparison.

## Stopping Fractions

| Stave | MC (v3) | Data (all) | Data S-I | Data S-II |
|-------|---------|-----------|---------|---------|
""")
        for s in STAVES:
            fh.write(f"| {s} | {mc_res['fractions'][s]:.3f} | "
                     f"{data_res['all']['fractions'][s]:.3f} | "
                     f"{data_res['sample_i']['fractions'][s]:.3f} | "
                     f"{data_res['sample_ii']['fractions'][s]:.3f} |\n")
        fh.write(f"""
## Physical Interpretation

The threshold removes all through-going protons from the MC comparison (they deposit
< {args.net_threshold/(args.gain*args.peak_frac):.1f} MeV per stave). The remaining MC tracks are:
- Stopping protons/deuterons in each stave (Bragg peak deposits all remaining KE)
- Near-stopping tracks with high dE/dx (approaching end of range)

Remaining χ²/ndf = {chi2/max(ndf,1):.1f} discrepancy sources:
1. Sample I/II trigger not simulated in MC (Sample II data has deeper stopping profile)
2. Gain uncertainty ±30% shifts all MC fractions
3. Data B2 includes pile-up events (extra B2 pulses inflate B2 stopping fraction)
4. CD₂ target thickness and upstream material budget uncertainty

## MC Verdict

**{verdict}**: {
"MC stopping-depth distribution with threshold applied is broadly consistent with data." if verdict=="PASS"
else "Moderate tension remains after threshold correction. Dominant source: trigger simulation and pile-up." if verdict=="TENSION"
else "Significant discrepancy persists. Possible: CD2 geometry or material budget error in MC."
}
""")
    print(f"[mv3v3] wrote {rpath}")
    print(f"[mv3v3] done={datetime.now(timezone.utc).isoformat()}")


if __name__ == "__main__":
    main()
