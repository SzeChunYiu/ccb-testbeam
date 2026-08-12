#!/usr/bin/env python3
"""
data01_sample_split_staves.py  (v2 — extended with supervisor deliverables)
==========================================================================
DATA side of the Sample I / Sample II comparison (CCB test beam, B-stack).

In DATA the trigger is the *hardware* trigger, already encoded by run range in
the `group` column of the selected-pulse table:
    sample_i_*   -> coincidence trigger (A & B)   [Sample I]
    sample_ii_*  -> single B trigger              [Sample II]
We use the *_analysis groups (calibration runs excluded) by default.

v2 NEW — per supervisor request:
  - Per-stave amplitude spectra plots
  - Depth profile (fraction of pulses per stave) plot
  - ΔE-E style plot: B2 amplitude vs B4 amplitude per sample
  - Per-stave per-sample amplitude distributions saved as arrays
  - Cumulative amplitude distributions per stave

Columns: run, group, eventno, evt, stave, channel, baseline_adc,
         amplitude_adc, peak_sample, area_adc_samples

Usage:
  python3 data01_sample_split_staves.py --table s00_selected_b_pulses.csv.gz --out <dir>
"""
import argparse
import json
import os
import sys
import traceback

import numpy as np
import pandas as pd

STAVES = ["B2", "B4", "B6", "B8"]
_CLUSTER_KEY_COLUMNS = ("run", "eventno")


def _require_cluster_key_columns(df: pd.DataFrame) -> None:
    """Fail closed before cluster-ID export when composite key columns are absent (#1164)."""
    missing = [col for col in _CLUSTER_KEY_COLUMNS if col not in df.columns]
    if missing:
        raise RuntimeError(
            f"cluster export requires columns {list(_CLUSTER_KEY_COLUMNS)}; missing {missing}"
        )


def _per_event_stave_amplitude(df, sample, stave):
    """One row per (run, eventno) carrying a single amplitude for this stave.

    Aggregates multiple pulses per (run, eventno, stave) to the max amplitude
    (deterministic), then asserts one row per (run, eventno). Downstream
    B2<->B4 merges MUST key on the composite (run, eventno) — joining on
    eventno alone collides across runs (eventno is NOT globally unique; see
    docs/contracts/PULSE_TABLE_CONTRACT.md).
    """
    sub = df[(df["sample"] == sample) & (df["stave"] == stave)]
    if sub.empty:
        return pd.DataFrame(columns=["run", "eventno", "amp"])
    agg = (sub.groupby(["run", "eventno"], sort=False)["amplitude_adc"]
              .max()
              .reset_index()
              .rename(columns={"amplitude_adc": "amp"}))
    if agg.duplicated(["run", "eventno"]).any():
        raise RuntimeError(
            f"cardinality violation: duplicate (run,eventno) for {sample}/{stave}")
    return agg


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
    ap.add_argument("--seed", type=int,
                    default=int(os.environ.get("CCB_PLOT_SEED", "12345")),
                    help="RNG seed for plot subsampling (env: CCB_PLOT_SEED)")
    args = ap.parse_args()
    os.makedirs(args.out, exist_ok=True)

    df = pd.read_csv(args.table)
    _require_cluster_key_columns(df)
    df["sample"] = np.where(df["group"].str.startswith("sample_i_"), "I",
                     np.where(df["group"].str.startswith("sample_ii_"), "II", "other"))
    if not args.include_calib:
        df = df[df["group"].str.endswith("_analysis")].copy()

    out = {"table": os.path.abspath(args.table),
           "include_calib": args.include_calib,
           "large_adc": args.large_adc, "sat_adc": args.sat_adc,
           "plot_seed": int(args.seed),
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
        tot = len(sub) or 1
        rec["depth_fraction"] = {st: round(int((sub["stave"] == st).sum()) / tot, 4)
                                 for st in STAVES}
        out["per_sample"][s] = rec

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

    # Save arrays
    # Pulse-row export retains amplitudes; cluster IDs are required for any
    # weighted-null calibration (#1164). statistical_unit remains pulse_row
    # until an event-aggregated DATA product is selected by the consumer.
    _require_cluster_key_columns(df)
    sI = df.loc[(df["sample"] == "I") & (df["stave"] == "B2")]
    sII = df.loc[(df["sample"] == "II") & (df["stave"] == "B2")]
    sample_i_cluster = (
        sI["run"].astype(str) + ":" + sI["eventno"].astype(str)
    ).to_numpy()
    sample_ii_cluster = (
        sII["run"].astype(str) + ":" + sII["eventno"].astype(str)
    ).to_numpy()
    if sample_i_cluster.size != sI.shape[0] or sample_ii_cluster.size != sII.shape[0]:
        raise RuntimeError(
            "cluster export incomplete: cluster_id length mismatch with pulse rows"
        )
    np.savez_compressed(
        os.path.join(args.out, "first_B_layer_B2_amplitude.npz"),
        sampleI=sI["amplitude_adc"].to_numpy(np.float32),
        sampleII=sII["amplitude_adc"].to_numpy(np.float32),
        sampleI_run=sI["run"].to_numpy(np.int64),
        sampleII_run=sII["run"].to_numpy(np.int64),
        sampleI_eventno=sI["eventno"].to_numpy(np.int64),
        sampleII_eventno=sII["eventno"].to_numpy(np.int64),
        sampleI_cluster_id=sample_i_cluster,
        sampleII_cluster_id=sample_ii_cluster,
        statistical_unit=np.asarray(["pulse_row"]),
        cluster_key=np.asarray(["run:eventno"]),
        weight_semantics=np.asarray(["unit_data_pulse"]),
    )
    per_stave_amp = {}
    for s in ("I", "II"):
        for st in STAVES:
            mask = (df["sample"] == s) & (df["stave"] == st)
            arr = df.loc[mask, "amplitude_adc"].to_numpy(np.float32)
            per_stave_amp[f"{s}_{st}"] = arr
    np.savez_compressed(os.path.join(args.out, "per_stave_amplitude.npz"), **per_stave_amp)

    # B2 vs B4 per-event — composite key (run, eventno) with 1:1 cardinality
    for s, label in (("I", "Sample I"), ("II", "Sample II")):
        b2 = _per_event_stave_amplitude(df, s, "B2").rename(columns={"amp": "amp_B2"})
        b4 = _per_event_stave_amplitude(df, s, "B4").rename(columns={"amp": "amp_B4"})
        merged = b2.merge(b4, on=["run", "eventno"], how="inner", validate="1:1")
        if len(merged) > 0:
            np.savez_compressed(
                os.path.join(args.out, f"B2_vs_B4_{s}.npz"),
                amp_B2=merged["amp_B2"].to_numpy(np.float32),
                amp_B4=merged["amp_B4"].to_numpy(np.float32),
            )

    # ═══════════════════════════════════════════════════════════════════════
    #  PLOTS
    # ═══════════════════════════════════════════════════════════════════════
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt

        # Figure 1: First B layer (B2) amplitude spectrum
        fig, ax = plt.subplots(figsize=(10, 5.5))
        colors = {"I": "C0", "II": "C3"}
        for s, label, ls in (("I", "Sample I (coincidence)", "-"),
                              ("II", "Sample II (single-B)", "--")):
            a = df[(df["sample"] == s) & (df["stave"] == "B2")]["amplitude_adc"].to_numpy(float)
            ax.hist(a, bins=80, range=(0, 15000), histtype="step", linewidth=2,
                    color=colors[s], linestyle=ls, label=label, density=True)
        ax.set_xlabel("Amplitude B2 [ADC]")
        ax.set_ylabel("Normalised counts")
        ax.set_title("DATA: First B-Layer (B2) Pulse Amplitude — Sample I vs Sample II")
        ax.legend()
        ax.set_xlim(0, 14000)
        fig.tight_layout()
        fig.savefig(os.path.join(args.out, "first_B_layer_B2_amplitude_spectrum.png"), dpi=150)
        plt.close(fig)

        # Figure 2: Depth profile
        fig, ax = plt.subplots(figsize=(9, 5))
        x = np.arange(len(STAVES))
        for s, label, marker in (("I", "Sample I", "o"), ("II", "Sample II", "s")):
            fracs = [out["per_sample"][s]["depth_fraction"][st] for st in STAVES]
            ax.plot(x, fracs, marker=marker, linewidth=2, label=label)
        ax.set_xticks(x)
        ax.set_xticklabels(STAVES)
        ax.set_xlabel("B-stack stave")
        ax.set_ylabel("Fraction of pulses")
        ax.set_title("DATA: Depth Profile — Pulse Fraction per Stave")
        ax.legend()
        ax.grid(True, alpha=0.3)
        fig.tight_layout()
        fig.savefig(os.path.join(args.out, "depth_profile_data.png"), dpi=150)
        plt.close(fig)

        # Figure 3: Per-stave amplitude spectra
        fig, axes = plt.subplots(2, 2, figsize=(14, 10))
        for idx, st in enumerate(STAVES):
            ax = axes[idx // 2][idx % 2]
            for s, label, color, ls in (("I", "Sample I", "C0", "-"),
                                         ("II", "Sample II", "C3", "--")):
                a = df[(df["sample"] == s) & (df["stave"] == st)]["amplitude_adc"].to_numpy(float)
                if a.size > 0:
                    ax.hist(a, bins=60, range=(0, 8000), histtype="step", linewidth=2,
                            color=color, linestyle=ls, label=f"{label} (n={a.size})",
                            density=True)
            ax.set_xlabel(f"Amplitude {st} [ADC]")
            ax.set_ylabel("Normalised counts")
            ax.set_title(f"DATA: {st} Pulse Amplitude — Sample I vs Sample II")
            ax.legend(fontsize=8)
            ax.set_xlim(0, 7000)
        fig.suptitle("DATA: Per-Stave Pulse Amplitude Spectra — Sample I vs Sample II",
                     fontsize=14, fontweight="bold")
        fig.tight_layout()
        fig.savefig(os.path.join(args.out, "per_stave_amplitude_spectra.png"), dpi=150)
        plt.close(fig)

        # Figure 4: B2 vs B4 scatter (ΔE-E analogue)
        fig, axes = plt.subplots(1, 2, figsize=(14, 6))
        for si, (s, lbl) in enumerate((("I", "Sample I"), ("II", "Sample II"))):
            ax = axes[si]
            b2 = _per_event_stave_amplitude(df, s, "B2").rename(columns={"amp": "amp_B2"})
            b4 = _per_event_stave_amplitude(df, s, "B4").rename(columns={"amp": "amp_B4"})
            merged = b2.merge(b4, on=["run", "eventno"], how="inner", validate="1:1")
            if len(merged) > 0:
                # Deterministic subsample: stable row order + recorded seed.
                merged = merged.sort_values(["run", "eventno"]).reset_index(drop=True)
                n_pts = min(8000, len(merged))
                if len(merged) > n_pts:
                    rng = np.random.default_rng(args.seed)
                    idx = np.sort(rng.choice(len(merged), n_pts, replace=False))
                else:
                    idx = np.arange(len(merged))
                ax.scatter(merged["amp_B2"].iloc[idx], merged["amp_B4"].iloc[idx],
                           s=2, alpha=0.3, color="C0" if s == "I" else "C3", rasterized=True)
                corr = merged["amp_B2"].corr(merged["amp_B4"])
                ax.set_title(f"DATA {lbl} — B2 vs B4 Amplitude (r={corr:.3f}, n={len(merged):,})")
            ax.set_xlabel("B2 Amplitude [ADC]")
            ax.set_ylabel("B4 Amplitude [ADC]")
            ax.set_xlim(0, 14000)
            ax.set_ylim(0, 5000)
        fig.suptitle("DATA ΔE-E Analogue: B2 vs B4 Pulse Amplitude — Sample I vs Sample II",
                     fontsize=13, fontweight="bold")
        fig.tight_layout()
        fig.savefig(os.path.join(args.out, "B2_vs_B4_scatter.png"), dpi=150)
        plt.close(fig)

        # Figure 5: Cumulative amplitude distributions
        fig, axes = plt.subplots(2, 2, figsize=(14, 10))
        for idx, st in enumerate(STAVES):
            ax = axes[idx // 2][idx % 2]
            for s, label, color, ls in (("I", "Sample I", "C0", "-"),
                                         ("II", "Sample II", "C3", "--")):
                a = df[(df["sample"] == s) & (df["stave"] == st)]["amplitude_adc"].to_numpy(float)
                if a.size > 0:
                    a_sorted = np.sort(a)
                    cdf = np.arange(1, len(a_sorted) + 1) / len(a_sorted)
                    ax.plot(a_sorted, cdf, color=color, linestyle=ls, linewidth=2, label=label)
            ax.set_xlabel(f"Amplitude {st} [ADC]")
            ax.set_ylabel("Cumulative fraction")
            ax.set_title(f"DATA: {st} Cumulative Amplitude Distribution")
            ax.legend(fontsize=8)
            ax.grid(True, alpha=0.3)
            ax.set_xlim(0, 12000)
        fig.suptitle("DATA: Cumulative Amplitude Distributions — Sample I vs Sample II",
                     fontsize=14, fontweight="bold")
        fig.tight_layout()
        fig.savefig(os.path.join(args.out, "cumulative_amplitude_per_stave.png"), dpi=150)
        plt.close(fig)

        print("[plots] All 5 DATA figures generated.")
    except Exception:
        print("[plot_error] plotting failed; re-raising (fail-closed).",
              file=sys.stderr)
        traceback.print_exc()
        raise

    print(json.dumps(out["headline_first_B_layer_B2"], indent=2))
    print(f"[ok] wrote {args.out}/data_sample_split_summary.json")


if __name__ == "__main__":
    main()
