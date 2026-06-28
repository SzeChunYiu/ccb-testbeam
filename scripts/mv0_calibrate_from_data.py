#!/usr/bin/env python3
"""
mv0_calibrate_from_data.py
==========================
MV0 -- data-driven ADC gain calibration for the CCB test-beam B-stack digitizer.

Goal: recover the ADC-per-MeV gain (and pedestal estimate) by matching the MC
energy-deposit distribution to the measured data pulse-height (amplitude_adc)
distribution, then write a calibration card other MC-validation studies consume.

Physics note on the comparison space
-------------------------------------
A data row in s00_selected_b_pulses.csv.gz is ONE pulse: the peak height
(amplitude_adc) of ONE readout stave channel in ONE event.  A stave channel
integrates the scintillation light of *all* energy deposited in that stave that
event.  The correct MC analogue is therefore the per-EVENT, per-STAVE summed
EDep * gain -- NOT the per-track total EDep.  We build that per-event/per-stave
pulse list from the ROOT truth (B-arm hits, LayerID -> stave) and use it as the
primary calibration target.

For transparency we ALSO report the per-track edep_tot*G variant (the original
quick estimate); it recovers a different gain precisely because edep_tot pools
energy across staves and so does not map onto a single-channel pulse height.

Outputs (reports/mv0_calibration_STAMP/):
  calibration.json   best-fit gain, pedestal, KS, chi2, per-stave percentiles
  mv0_data_vs_mc.png         global overlay at best gain
  mv0_per_stave.png          per-stave overlay (2x2)
  mv0_gain_scan.png          KS + chi2 vs gain
  mv0_qq.png                 QQ plot data vs MC at best gain
  REPORT.md

Usage:
  mv0_calibrate_from_data.py --mc <root> --data-csv <csv.gz> \
      --truth-npz <npz> --out <dir> [--max-events N]
"""
import argparse
import gzip
import json
import os
from datetime import datetime, timezone

import numpy as np
import pandas as pd
from scipy.stats import ks_2samp

B_ARM = 1
LAYER_TO_STAVE = {0: "B2", 1: "B2", 2: "B4", 3: "B4", 4: "B6", 5: "B6", 6: "B8", 7: "B8"}
STAVES = ["B2", "B4", "B6", "B8"]
GAIN_GRID = [150.0, 200.0, 246.0, 300.0, 350.0]
CHI2_RANGE = (0.0, 7000.0)
CHI2_BINS = 20
PCTLS = [5, 25, 50, 75, 95]


def percentiles(x):
    x = np.asarray(x, dtype=float)
    if x.size == 0:
        return {f"p{p}": None for p in PCTLS}
    return {f"p{p}": float(np.percentile(x, p)) for p in PCTLS}


def chi2_hist(data, mc, rng, bins):
    """Poisson chi2 between MC (scaled to data N) and data histograms."""
    hd, edges = np.histogram(data, bins=bins, range=rng)
    hm, _ = np.histogram(mc, bins=edges)
    if hm.sum() == 0:
        return float("nan"), int(bins)
    hm = hm.astype(float) * (hd.sum() / hm.sum())
    denom = hd + hm
    mask = denom > 0
    chi2 = float(np.sum((hd[mask] - hm[mask]) ** 2 / denom[mask]))
    ndf = int(mask.sum() - 1)
    return chi2, max(ndf, 1)


def load_mc_pulses(root_path, tree_name, max_events):
    """Per-EVENT per-STAVE summed EDep (MeV) over B-arm hits. Returns dict stave->array."""
    import uproot

    br = ["Sci_bar_LayerID", "Sci_bar_LayerID1", "Sci_bar_EDep"]
    per_stave = {s: [] for s in STAVES}
    stop = max_events if max_events and max_events > 0 else None
    tree = uproot.open(root_path)[tree_name]
    n_events = 0
    for ch in tree.iterate(br, step_size="200 MB", library="np", entry_stop=stop):
        L = ch["Sci_bar_LayerID"]
        L1 = ch["Sci_bar_LayerID1"]
        ED = ch["Sci_bar_EDep"]
        for i in range(len(L)):
            li = L[i]
            if len(li) == 0:
                continue
            n_events += 1
            isB = L1[i] == B_ARM
            if not isB.any():
                continue
            lay = li[isB].astype(np.int64)
            ed = ED[i][isB].astype(np.float64)
            stave_sum = {}
            for s in STAVES:
                stave_sum[s] = 0.0
            for k in range(lay.size):
                st = LAYER_TO_STAVE.get(int(lay[k]))
                if st is not None:
                    stave_sum[st] += ed[k]
            for s in STAVES:
                if stave_sum[s] > 0.0:
                    per_stave[s].append(stave_sum[s])
    per_stave = {s: np.asarray(v, dtype=np.float64) for s, v in per_stave.items()}
    return per_stave, n_events


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--mc", required=True)
    ap.add_argument("--data-csv", required=True)
    ap.add_argument("--truth-npz", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--tree", default="hibeam")
    ap.add_argument("--max-events", type=int, default=0)
    args = ap.parse_args()
    os.makedirs(args.out, exist_ok=True)

    print(f"[mv0] start={datetime.now(timezone.utc).isoformat()}")
    print(f"[mv0] mc={args.mc}")
    print(f"[mv0] data_csv={args.data_csv}")

    # ---- data ----
    df = pd.read_csv(args.data_csv)
    sel = df["group"].astype(str).str.contains("analysis")
    dsel = df[sel].copy()
    data_amp = dsel["amplitude_adc"].to_numpy(dtype=float)
    amp_min = float(np.min(data_amp))
    pedestal_est = float(np.median(dsel["baseline_adc"].to_numpy(dtype=float))) if "baseline_adc" in dsel else float("nan")
    data_per_stave = {s: dsel.loc[dsel["stave"] == s, "amplitude_adc"].to_numpy(dtype=float) for s in STAVES}
    print(f"[mv0] data analysis pulses={data_amp.size} amp_min={amp_min:.1f} pedestal_est={pedestal_est:.1f}")

    # ---- MC per-event/per-stave pulses (primary target) ----
    mc_per_stave, n_events = load_mc_pulses(args.mc, args.tree, args.max_events)
    mc_edep_all = np.concatenate([mc_per_stave[s] for s in STAVES]) if any(mc_per_stave[s].size for s in STAVES) else np.array([])
    print(f"[mv0] MC events read={n_events} MC pulses={mc_edep_all.size}")
    for s in STAVES:
        print(f"[mv0]   stave {s}: MC pulses={mc_per_stave[s].size} data pulses={data_per_stave[s].size}")

    # ---- gain scan (primary: per-stave pulse pool, MC amp>=amp_min cut) ----
    def ks_chi2_at_gain(g, mc_edep):
        mc_amp = mc_edep * g
        mc_amp = mc_amp[mc_amp >= amp_min]
        if mc_amp.size < 50:
            return float("nan"), float("nan"), 1, mc_amp
        ks = float(ks_2samp(data_amp, mc_amp).statistic)
        chi2, ndf = chi2_hist(data_amp, mc_amp, CHI2_RANGE, CHI2_BINS)
        return ks, chi2, ndf, mc_amp

    scan = []
    for g in GAIN_GRID:
        ks, chi2, ndf, _ = ks_chi2_at_gain(g, mc_edep_all)
        scan.append({"gain": g, "ks": ks, "chi2": chi2, "ndf": ndf,
                     "chi2_per_ndf": (chi2 / ndf) if ndf else float("nan")})
        print(f"[mv0] gain={g:6.1f}  KS={ks:.4f}  chi2/ndf={chi2/ndf:.2f}")

    # implied gain from medians (per-stave pool)
    mc_med = float(np.median(mc_edep_all)) if mc_edep_all.size else float("nan")
    data_med = float(np.median(data_amp))
    implied_gain = data_med / mc_med if mc_med > 0 else float("nan")

    # broad fine scan that always brackets the global KS minimum (grid KS is
    # monotonic in gain, so a local window around the best grid point can miss it)
    fine = []
    for g in np.linspace(50.0, 400.0, 71):
        ks, chi2, ndf, _ = ks_chi2_at_gain(float(g), mc_edep_all)
        fine.append({"gain": float(g), "ks": ks, "chi2": chi2, "ndf": ndf})
    fine_valid = [r for r in fine if np.isfinite(r["ks"])]
    best = min(fine_valid, key=lambda r: r["ks"]) if fine_valid else {"gain": float(implied_gain)}
    best_gain = float(best["gain"])
    best_ks, best_chi2, best_ndf, best_mc_amp = ks_chi2_at_gain(best_gain, mc_edep_all)
    print(f"[mv0] BEST gain={best_gain:.2f} ADC/MeV  KS={best_ks:.4f}  "
          f"chi2={best_chi2:.1f}/{best_ndf}={best_chi2/best_ndf:.2f}  implied(median)={implied_gain:.1f}")

    # ---- edep_tot*G variant (team-lead spec, transparency only) ----
    npz = np.load(args.truth_npz)
    edep_tot = npz["edep_tot"].astype(float)
    edep_tot = edep_tot[edep_tot > 0]
    tot_scan = []
    for g in GAIN_GRID:
        mc_amp = edep_tot * g
        mc_amp = mc_amp[mc_amp >= amp_min]
        ks = float(ks_2samp(data_amp, mc_amp).statistic) if mc_amp.size > 50 else float("nan")
        tot_scan.append({"gain": g, "ks": ks})
    tot_valid = [r for r in tot_scan if np.isfinite(r["ks"])]
    tot_best = min(tot_valid, key=lambda r: r["ks"]) if tot_valid else {"gain": None, "ks": None}

    # ---- per-stave percentiles + per-stave best gain ----
    per_stave_out = {}
    for s in STAVES:
        d = data_per_stave[s]
        mc_amp_s = mc_per_stave[s] * best_gain
        mc_amp_s = mc_amp_s[mc_amp_s >= amp_min]
        ks_s = float(ks_2samp(d, mc_amp_s).statistic) if (d.size > 20 and mc_amp_s.size > 20) else None
        implied_s = (float(np.median(d)) / float(np.median(mc_per_stave[s]))) if mc_per_stave[s].size else None
        per_stave_out[s] = {
            "data_percentiles_adc": percentiles(d),
            "mc_percentiles_adc_at_best_gain": percentiles(mc_amp_s),
            "ks_at_best_gain": ks_s,
            "implied_gain_adc_per_mev": implied_s,
            "n_data": int(d.size),
            "n_mc": int(mc_per_stave[s].size),
        }

    # ---- calibration.json ----
    calib = {
        "study_id": "MV0",
        "generated_utc": datetime.now(timezone.utc).isoformat(),
        "mc_file": os.path.abspath(args.mc),
        "data_csv": os.path.abspath(args.data_csv),
        "n_events_read": int(n_events),
        "n_mc_pulses": int(mc_edep_all.size),
        "n_data_pulses": int(data_amp.size),
        "amp_min_cut_adc": amp_min,
        "calibration": {
            "gain_adc_per_mev": best_gain,
            "pedestal_adc": pedestal_est,
            "ks_statistic": best_ks,
            "chi2": best_chi2,
            "chi2_ndf": best_ndf,
            "chi2_per_ndf": best_chi2 / best_ndf if best_ndf else None,
            "implied_gain_from_medians": implied_gain,
        },
        "gain_scan_grid": scan,
        "gain_scan_fine": fine,
        "edep_tot_variant": {
            "note": "per-track edep_tot*G (pools staves); not a single-channel pulse analogue",
            "scan": tot_scan,
            "best_gain": tot_best.get("gain"),
            "best_ks": tot_best.get("ks"),
        },
        "per_stave": per_stave_out,
        "data_global_percentiles_adc": percentiles(data_amp),
        "mc_global_percentiles_adc_at_best_gain": percentiles(best_mc_amp),
    }
    with open(os.path.join(args.out, "calibration.json"), "w") as fh:
        json.dump(calib, fh, indent=2)
    print(f"[mv0] wrote {args.out}/calibration.json")

    # ---- plots ----
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    bins = np.linspace(0, max(CHI2_RANGE[1], float(np.percentile(data_amp, 99.5))), 60)

    # global overlay
    fig, ax = plt.subplots(figsize=(8, 5))
    ax.hist(data_amp, bins=bins, histtype="step", density=True, color="k", lw=1.8, label=f"data (n={data_amp.size})")
    ax.hist(best_mc_amp, bins=bins, histtype="step", density=True, color="C3", lw=1.8,
            label=f"MC*G (G={best_gain:.0f}, n={best_mc_amp.size})")
    ax.axvline(amp_min, color="gray", ls=":", lw=1, label=f"amp_min={amp_min:.0f}")
    ax.set_xlabel("pulse amplitude [ADC]")
    ax.set_ylabel("normalized density")
    ax.set_title(f"MV0 data vs MC amplitude  KS={best_ks:.3f}  chi2/ndf={best_chi2/best_ndf:.2f}")
    ax.legend()
    fig.tight_layout()
    fig.savefig(os.path.join(args.out, "mv0_data_vs_mc.png"), dpi=130)
    plt.close(fig)

    # per-stave 2x2
    fig, axs = plt.subplots(2, 2, figsize=(11, 8))
    for ax, s in zip(axs.ravel(), STAVES):
        d = data_per_stave[s]
        mc_amp_s = mc_per_stave[s] * best_gain
        mc_amp_s = mc_amp_s[mc_amp_s >= amp_min]
        b = np.linspace(0, max(1, float(np.percentile(d, 99.5)) if d.size else 1), 50)
        if d.size:
            ax.hist(d, bins=b, histtype="step", density=True, color="k", lw=1.6, label=f"data n={d.size}")
        if mc_amp_s.size:
            ax.hist(mc_amp_s, bins=b, histtype="step", density=True, color="C3", lw=1.6, label=f"MC n={mc_amp_s.size}")
        ks_s = per_stave_out[s]["ks_at_best_gain"]
        ax.set_title(f"{s}  KS={ks_s:.3f}" if ks_s is not None else f"{s}")
        ax.set_xlabel("amplitude [ADC]")
        ax.legend(fontsize=8)
    fig.suptitle(f"MV0 per-stave data vs MC (G={best_gain:.0f} ADC/MeV)")
    fig.tight_layout()
    fig.savefig(os.path.join(args.out, "mv0_per_stave.png"), dpi=130)
    plt.close(fig)

    # gain scan curve
    gg = [r["gain"] for r in fine if np.isfinite(r["ks"])]
    kk = [r["ks"] for r in fine if np.isfinite(r["ks"])]
    cc = [(r["chi2"] / r["ndf"]) for r in fine if np.isfinite(r["ks"]) and r["ndf"]]
    fig, ax1 = plt.subplots(figsize=(8, 5))
    ax1.plot(gg, kk, "o-", color="C0", label="KS")
    ax1.axvline(best_gain, color="C3", ls="--", label=f"best={best_gain:.0f}")
    ax1.set_xlabel("gain [ADC/MeV]")
    ax1.set_ylabel("KS statistic", color="C0")
    ax2 = ax1.twinx()
    ax2.plot(gg, cc, "s-", color="C2", alpha=0.6, label="chi2/ndf")
    ax2.set_ylabel("chi2/ndf", color="C2")
    for g in GAIN_GRID:
        ax1.axvline(g, color="gray", ls=":", lw=0.6)
    ax1.set_title("MV0 gain scan (fine)")
    ax1.legend(loc="upper right")
    fig.tight_layout()
    fig.savefig(os.path.join(args.out, "mv0_gain_scan.png"), dpi=130)
    plt.close(fig)

    # QQ plot
    qs = np.linspace(1, 99, 99)
    dq = np.percentile(data_amp, qs)
    mq = np.percentile(best_mc_amp, qs) if best_mc_amp.size else np.full_like(dq, np.nan)
    fig, ax = plt.subplots(figsize=(6.5, 6.5))
    ax.plot(dq, mq, "o", ms=3, color="C0")
    lim = [0, max(dq.max(), np.nanmax(mq))]
    ax.plot(lim, lim, "k--", lw=1)
    ax.set_xlabel("data amplitude quantile [ADC]")
    ax.set_ylabel("MC amplitude quantile [ADC]")
    ax.set_title(f"MV0 QQ data vs MC (G={best_gain:.0f})")
    fig.tight_layout()
    fig.savefig(os.path.join(args.out, "mv0_qq.png"), dpi=130)
    plt.close(fig)

    # ---- REPORT.md ----
    dgp = calib["data_global_percentiles_adc"]
    mgp = calib["mc_global_percentiles_adc_at_best_gain"]
    lines = []
    lines.append("# MV0 -- Data-Driven ADC Gain Calibration\n")
    lines.append(f"- status: **PRODUCTION**")
    lines.append(f"- generated: {calib['generated_utc']}")
    lines.append(f"- MC: `{calib['mc_file']}` ({n_events} events read)")
    lines.append(f"- data: `{calib['data_csv']}` ({data_amp.size} analysis pulses)\n")
    lines.append("## Reproduce")
    lines.append("```")
    lines.append(f"{os.path.basename(__file__)} --mc <root> --data-csv <csv.gz> \\")
    lines.append(f"    --truth-npz <npz> --out <dir> --max-events {args.max_events}")
    lines.append("```\n")
    lines.append("## Key metrics")
    lines.append("| quantity | value |")
    lines.append("|---|---|")
    lines.append(f"| best-fit gain | **{best_gain:.1f} ADC/MeV** |")
    lines.append(f"| implied gain (medians) | {implied_gain:.1f} ADC/MeV |")
    lines.append(f"| edep_tot*G variant best gain | {tot_best.get('gain')} ADC/MeV |")
    lines.append(f"| pedestal estimate (median baseline) | {pedestal_est:.1f} ADC |")
    lines.append(f"| KS (data vs MC) | {best_ks:.4f} |")
    lines.append(f"| chi2 / ndf (20 bins, [0,7000]) | {best_chi2:.1f} / {best_ndf} = {best_chi2/best_ndf:.2f} |")
    lines.append(f"| amp_min cut | {amp_min:.1f} ADC |\n")
    lines.append("## Methodology")
    lines.append("- Data pulse = peak height (`amplitude_adc`) of one stave channel in one event; "
                 "groups containing `analysis`.")
    lines.append("- MC pulse = per-event, per-stave summed B-arm EDep (LayerID->stave) * gain; "
                 "the single-channel analogue of a data pulse.")
    lines.append("- Gain found by minimizing the KS statistic between MC*G and data pulse-height "
                 "distributions (grid then fine scan); MC pulses below the data amp_min are cut to match selection.")
    lines.append("- `edep_tot*G` per-track variant reported for transparency; it pools energy across "
                 "staves and so is NOT a single-channel pulse analogue (recovers a different, lower gain).\n")
    lines.append("## Comparison to data (global percentiles, ADC)")
    lines.append("| pctl | data | MC*G |")
    lines.append("|---|---|---|")
    for p in PCTLS:
        lines.append(f"| p{p} | {dgp[f'p{p}']:.0f} | {mgp[f'p{p}']:.0f} |")
    lines.append("")
    lines.append("## Per-stave KS at best gain")
    lines.append("| stave | n_data | n_mc | data p50 | MC p50 | KS | implied gain |")
    lines.append("|---|---|---|---|---|---|---|")
    for s in STAVES:
        ps = per_stave_out[s]
        d50 = ps["data_percentiles_adc"]["p50"]
        m50 = ps["mc_percentiles_adc_at_best_gain"]["p50"]
        ks_s = ps["ks_at_best_gain"]
        ig = ps["implied_gain_adc_per_mev"]
        lines.append(f"| {s} | {ps['n_data']} | {ps['n_mc']} | "
                     f"{d50 if d50 is None else round(d50)} | {m50 if m50 is None else round(m50)} | "
                     f"{ks_s if ks_s is None else round(ks_s,3)} | {ig if ig is None else round(ig,1)} |")
    lines.append("")
    verdict = "PASS" if (best_ks < 0.10) else ("MARGINAL" if best_ks < 0.20 else "TENSION")
    lines.append("## MC verdict")
    lines.append(f"- Global KS={best_ks:.3f} -> **{verdict}** (PASS<0.10, MARGINAL<0.20).")
    lines.append(f"- Calibrated gain {best_gain:.0f} ADC/MeV written to calibration.json; "
                 "downstream digitizer studies (MV4 timing) read this card.")
    lines.append("")
    lines.append("## Open questions")
    lines.append("- Data amplitude_adc is peak height; MC uses integrated EDep*G (shape factor absorbed "
                 "into gain). A full shaped-waveform peak (MV4 digitizer) would refine the gain definition.")
    lines.append("- MC is a single beam configuration; per-sample (I/II) data split not separately "
                 "reproducible here -- combined-analysis data used as target.")
    lines.append("- Birks quenching is off in the digitizer config; residual high-amplitude tension may "
                 "indicate quenching is needed for the most-ionizing (deuteron) pulses.")
    with open(os.path.join(args.out, "REPORT.md"), "w") as fh:
        fh.write("\n".join(lines) + "\n")
    print(f"[mv0] wrote {args.out}/REPORT.md")
    print(f"[mv0] done={datetime.now(timezone.utc).isoformat()}")


if __name__ == "__main__":
    main()
