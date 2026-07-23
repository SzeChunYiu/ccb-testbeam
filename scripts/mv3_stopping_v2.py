#!/usr/bin/env python3
"""
mv3_stopping_v2.py
==================
MV3 v2 -- per-stave stopping-fraction comparison (MC vs data).

Metric definition
-----------------
Both MC and data express the "stopping depth" as the FRACTION of tracks/events
whose deepest energy deposit is in stave X (B2/B4/B6/B8).

MC:  last_stave = stave containing the deepest layer hit (max LayerID among all
     B-arm hits for that track).  Layer→stave: {0,1}→B2, {2,3}→B4, {4,5}→B6, {6,7}→B8.
     Since MC has no trigger, all B-arm charged tracks are used.

Data: per EVENT, find the deepest stave with a net_adc pulse above threshold.
     last_stave = stave with the highest stave index (B8 > B6 > B4 > B2) that
     fired in that event.  Events where no stave fired are excluded.

This corrects v1 which reported cumulative layer occupancy (fraction of tracks
that ENTER each layer), giving 100% in B2 by construction -- not comparable to data.

Outputs (reports/mv3_stopping_v2_STAMP/):
  mv3_stop_frac.png   bar chart: stopping fraction per stave (MC / data / Sample I / Sample II)
  mv3_summary.json    all fractions + chi2 comparison
  REPORT.md
"""
import argparse, json, os
from datetime import datetime, timezone

import numpy as np
import pandas as pd

LAYER_TO_STAVE = {0: "B2", 1: "B2", 2: "B4", 3: "B4", 4: "B6", 5: "B6", 6: "B8", 7: "B8"}
STAVES = ["B2", "B4", "B6", "B8"]
STAVE_ORDER = {s: i for i, s in enumerate(STAVES)}

B_ARM = 1
CHARGED_PDGS = {2212, 1000010020, 11, 13, 211, 321}  # p, d, e, mu, pi, K


def stave_of(layer_id: int) -> str:
    return LAYER_TO_STAVE.get(int(layer_id), "unknown")


def mc_stopping_fractions(mc_path: str, tree: str = "hibeam", max_events: int = 0) -> dict:
    """Read MC ROOT tree; compute per-stave stopping fraction for B-arm charged tracks."""
    import uproot
    br = ["Sci_bar_TrackID", "Sci_bar_LayerID1", "Sci_bar_PDG",
          "Sci_bar_EDep", "Sci_bar_LayerID"]
    tree_obj = uproot.open(mc_path)[tree]
    stop = max_events if max_events > 0 else None

    ev_count = 0
    last_staves = []  # one entry per track: which stave is the deepest hit

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
                edep = ed[m]
                if edep.sum() <= 0:
                    continue
                layers = ly[m]
                # deepest layer with nonzero EDep
                has_edep = edep > 0
                if not has_edep.any():
                    continue
                max_layer = int(layers[has_edep].max())
                last_staves.append(stave_of(max_layer))

    print(f"[mc] events scanned={ev_count}, B-arm charged tracks={len(last_staves)}")
    counts = {s: last_staves.count(s) for s in STAVES}
    total = sum(counts.values())
    fracs = {s: counts[s] / total if total > 0 else 0 for s in STAVES}
    return {"counts": counts, "fractions": fracs, "n_tracks": total}


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


def data_stopping_fractions(data_csv: str, threshold_net: float = 1000.0) -> dict:
    """
    For each event (by eventno/evt), find the deepest stave with net_adc > threshold.
    Return stopping fraction per stave.

    ``net_adc`` is the contract net amplitude (peak_height_adc if present,
    else the already-baseline-subtracted amplitude_adc). It is NOT re-derived
    by subtracting baseline_adc (A-001 double-subtraction bug).
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
    for group_name, sub_group in [("all", df),
                                  ("sample_i", df[df["sample"] == "I"]),
                                  ("sample_ii", df[df["sample"] == "II"])]:
        if len(sub_group) == 0:
            results[group_name] = {"fractions": {s: 0 for s in STAVES}, "n_events": 0}
            continue
        # group by event: find deepest stave
        ev_deepest = sub_group.groupby(["run", "evt"])["stave_rank"].max().reset_index()
        rank_to_stave = {v: k for k, v in stave_rank.items()}
        ev_deepest["last_stave"] = ev_deepest["stave_rank"].map(rank_to_stave)

        counts = ev_deepest["last_stave"].value_counts().to_dict()
        counts = {s: counts.get(s, 0) for s in STAVES}
        total = sum(counts.values())
        fracs = {s: counts[s] / total if total > 0 else 0 for s in STAVES}
        results[group_name] = {"fractions": fracs, "n_events": total, "counts": counts}
        print(f"[data:{group_name}] n_events={total}  stopping fractions: " +
              "  ".join(f"{s}={fracs[s]:.3f}" for s in STAVES))

    return results


def main():
    import warnings
    warnings.warn(
        "mv3_stopping_v2.py is DEPRECATED: it counts all MC tracks regardless "
        "of predicted amplitude, so through-going protons are misclassified as "
        "stopping. Use scripts/mv3_stopping_v3.py, which applies the per-stave "
        "amplitude threshold. v2 is retained only for historical comparison.",
        DeprecationWarning,
        stacklevel=2,
    )
    ap = argparse.ArgumentParser()
    ap.add_argument("--mc", required=True)
    ap.add_argument("--data", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--tree", default="hibeam")
    ap.add_argument("--max-events", type=int, default=0)
    ap.add_argument("--net-threshold", type=float, default=1000.0,
                    help="min net_adc to count a stave as fired")
    args = ap.parse_args()
    os.makedirs(args.out, exist_ok=True)

    stamp = datetime.now(timezone.utc).isoformat()
    print(f"[mv3v2] start={stamp}")

    mc_res = mc_stopping_fractions(args.mc, args.tree, args.max_events)
    data_res = data_stopping_fractions(args.data, args.net_threshold)

    # chi2 comparison: MC vs data (all)
    mc_f = np.array([mc_res["fractions"][s] for s in STAVES])
    data_f = np.array([data_res["all"]["fractions"][s] for s in STAVES])
    n_data = data_res["all"]["n_events"]
    # Pearson chi2 with expected = mc_f * n_data
    expected = mc_f * n_data
    observed = np.array([data_res["all"]["counts"].get(s, 0) for s in STAVES], dtype=float)
    with np.errstate(invalid="ignore", divide="ignore"):
        chi2 = float(np.nansum((observed - expected)**2 / np.where(expected > 0, expected, np.nan)))
    ndf = sum(mc_f > 0) - 1
    print(f"[mv3v2] chi2={chi2:.1f} ndf={ndf} chi2/ndf={chi2/max(ndf,1):.2f}")
    print(f"[mv3v2] MC fracs: " + "  ".join(f"{s}={mc_res['fractions'][s]:.3f}" for s in STAVES))
    print(f"[mv3v2] Data(all) fracs: " + "  ".join(f"{s}={data_res['all']['fractions'][s]:.3f}" for s in STAVES))

    summary = {
        "study_id": "MV3v2",
        "generated_utc": stamp,
        "mc_file": args.mc,
        "mc_n_tracks": mc_res["n_tracks"],
        "mc_stopping_fractions": mc_res["fractions"],
        "mc_stopping_counts": mc_res["counts"],
        "data": data_res,
        "chi2_mc_vs_data_all": chi2,
        "chi2_ndf": ndf,
        "chi2_per_ndf": chi2 / max(ndf, 1),
        "net_threshold_adc": args.net_threshold,
        "verdict": "PASS" if chi2 / max(ndf, 1) < 5 else "TENSION" if chi2 / max(ndf, 1) < 20 else "FAIL"
    }

    jpath = os.path.join(args.out, "mv3_summary.json")
    with open(jpath, "w") as fh:
        json.dump(summary, fh, indent=2)
    print(f"[mv3v2] wrote {jpath}")

    # Plot
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt

        fig, ax = plt.subplots(figsize=(8, 5))
        x = np.arange(len(STAVES))
        w = 0.22
        datasets = [
            ("MC (truth)", [mc_res["fractions"][s] for s in STAVES], "C0"),
            ("Data (all)", [data_res["all"]["fractions"][s] for s in STAVES], "C1"),
            ("Data sample_i", [data_res["sample_i"]["fractions"][s] for s in STAVES], "C2"),
            ("Data sample_ii", [data_res["sample_ii"]["fractions"][s] for s in STAVES], "C3"),
        ]
        for k, (label, vals, color) in enumerate(datasets):
            ax.bar(x + (k - 1.5) * w, vals, width=w, label=label, color=color, alpha=0.8)

        ax.set_xticks(x)
        ax.set_xticklabels(STAVES)
        ax.set_xlabel("Last stave (stopping depth)", fontsize=12)
        ax.set_ylabel("Fraction of tracks/events", fontsize=12)
        ax.set_title(f"MV3v2 — Stopping-depth fraction (χ²/ndf = {chi2/max(ndf,1):.1f})", fontsize=13)
        ax.legend(fontsize=10)
        ax.set_ylim(0, 1.0)
        for spine in ax.spines.values():
            spine.set_linewidth(0.5)

        ppath = os.path.join(args.out, "mv3_stop_frac.png")
        fig.savefig(ppath, dpi=150, bbox_inches="tight")
        plt.close(fig)
        print(f"[mv3v2] wrote {ppath}")
    except Exception as e:
        print(f"[mv3v2] plot failed: {e}")

    # REPORT.md
    rpath = os.path.join(args.out, "REPORT.md")
    with open(rpath, "w") as fh:
        fh.write(f"""# MV3 v2 — Stopping-Depth Fraction (corrected metric)

- status: **PRODUCTION (v2)**
- generated: {stamp}
- MC: `{args.mc}`
- data: `{os.path.basename(args.data)}`
- MC tracks: {mc_res["n_tracks"]}
- Data events (all): {data_res["all"]["n_events"]}
- χ²/ndf: {chi2/max(ndf,1):.2f}  →  **{summary["verdict"]}**

## Reproduce

```
python3 scripts/mv3_stopping_v2.py \\
  --mc geant4/data/output_krakow_1M.root \\
  --data <path to s00_selected_b_pulses.csv.gz> \\
  --out reports/mv3_stopping_v2/
```

## Metric Definition (corrected from v1)

**MC:** for each B-arm charged track, the _last stave_ = stave containing the deepest layer with nonzero EDep:
`layer→stave: {{0,1}}→B2, {{2,3}}→B4, {{4,5}}→B6, {{6,7}}→B8`.

**Data:** per event, group all stave pulses with `net_adc > {args.net_threshold:.0f} ADC`
(net_adc = |amplitude_adc − baseline_adc|); the last stave = the deepest-ranked stave that fired.

v1 error: reported cumulative layer occupancy (fraction of tracks _entering_ each layer),
which is 100% for B2 by construction — not comparable to data.

## Stopping Fractions

| Stave | MC | Data (all) | Data (S-I) | Data (S-II) |
|-------|-----|-----------|-----------|------------|
""")
        for s in STAVES:
            fh.write(f"| {s} | {mc_res['fractions'][s]:.3f} | "
                     f"{data_res['all']['fractions'][s]:.3f} | "
                     f"{data_res['sample_i']['fractions'][s]:.3f} | "
                     f"{data_res['sample_ii']['fractions'][s]:.3f} |\n")
        fh.write(f"""
## MC Verdict

χ²/ndf = {chi2/max(ndf,1):.1f} → **{summary["verdict"]}**.
{
"MC and data stopping-depth distributions are consistent." if summary["verdict"]=="PASS"
else "Moderate tension in the stopping-depth distribution. Likely causes: trigger-selection differences (Sample I vs II split not simulated in MC), pile-up effects in data B2 stave, or CD2 target geometry uncertainty." if summary["verdict"]=="TENSION"
else "Significant MC-data discrepancy in stopping-depth distribution. Review MC geometry and trigger model."
}

## Open Questions

- MC has no trigger simulation → Sample I/II split not modeled. Expected to shift MC stopping
  distribution toward deeper staves (Sample I enriches deuterons which have shorter range).
- Data pile-up events may produce spurious B2-only stopping classifications.
""")
    print(f"[mv3v2] wrote {rpath}")
    print(f"[mv3v2] done={datetime.now(timezone.utc).isoformat()}")


if __name__ == "__main__":
    main()
