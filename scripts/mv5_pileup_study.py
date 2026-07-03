#!/usr/bin/env python3
"""
mv5_pileup_study.py
===================
MV5 -- Pile-up study (RETRACTED as an MC validation, 2026-07-03).

RETRACTION NOTE (see EXTERNAL_REVIEW_2026-07-02.md):
  - TAU_EFF_NEW = 124.8 ns below is the DATA-measured live-time used as an
    INPUT. This script performs no independent MC live-time measurement, so
    the previously advertised "MC tau_eff = 124.8 ns, <0.01% agreement" was
    the same number compared with itself. An honest MC measurement is
    currently impossible: the toy digitizer decay (42 ns) disagrees with the
    measured data tails (49-57 ns).
  - MU_MAX = 0.38 is the maximum acceptable per-pulse occupancy for the
    |dt|<1 ns & area<20% distortion requirement (S10 rate model). It was
    previously mislabelled a "beam duty factor"; no in-spill fraction was
    ever measured, and conclusions built on that reading are withdrawn.
  - Rmax = MU_MAX / tau_eff is a DATA-DRIVEN one-sided bound: censoring-aware
    tau_eff estimators (KM 151.6 ns, IPCW 179.1 ns) imply Rmax <= 3.05 MHz.
  - The toy two-pulse recovery scores merged pairs (true separation < 30 ns)
    as successes (rec_sep = 0 passes the |rec - true| < 30 ns criterion), and
    the pile-up window counts only the gap to the PREVIOUS event; both make
    the failure-rate-vs-rate curve optimistic.

DEPRECATED DIGITIZER CONSTANTS (Phase 1, 2026-07-03): the inline toy
constants below (GAIN 246, NOISE 50, PED 350, TAU_D 42) are DEPRECATED in
favour of the single calibration card configs/mc_validation/digitizer_card.yaml
(pedestal 6752, noise 8, per-stave tau_decay B2 56.7 / B4 51.7 / B6 49.4 /
B8 50.1 ns) consumed via DigitizerPipeline.from_card(). Internals are
intentionally NOT rewritten; use scripts/mc02_build_mc_pulse_table.py for
card-driven MC pulses.

Question the data left open
---------------------------
Data study S10 found the maximum sustainable beam rate Rmax was *not* the
4.2 MHz the note assumed, but ~3.05 MHz, because the effective dead-time per
pulse (tau_eff) is longer than the assumed 90 ns. A direct waveform fit
(template "live10") measured tau_eff = 124.8 ns. With the occupancy criterion
mu_max = 0.38 this gives 0.38/124.8ns = 3.04 MHz -- the corrected Rmax.

This study uses MC truth tracks (proton + deuteron) to:
  1. model in-spill pile-up as a Poisson process and predict the two-pulse
     coincidence fraction vs beam rate for tau_eff in {90, 124.8} ns,
  2. simulate overlapped (proton+proton, proton+deuteron) waveforms and run a
     bounded two-pulse recovery, measuring the failure rate vs beam rate,
  3. derive Rmax under three tau_eff assumptions {90, 124.8, 179} ns by two
     definitions (mu_max/tau occupancy bound, and the rate where two-pulse recovery
     failure exceeds the traditional template ceiling 0.17),
  4. compare the predicted pile-up against the data-observed anomalous
     fractions (4.2% raw, 2.025% stratified current-excess), inferring the
     average in-spill operating rate.

Output: JSON summary, multi-panel PNG, example-waveform PNG, REPORT.md.
"""
from __future__ import annotations

import argparse
import json
import os
import time
from pathlib import Path

import numpy as np
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt

SEED = 42

# ---- digitizer constants (calibrated from data) ----------------------------
GAIN = 246.0          # ADC per MeV
NOISE = 50.0          # ADC rms
PED = 350.0           # pedestal ADC
TAU_R = 2.5           # rise ns
TAU_D = 42.0          # decay ns
NSAMP = 18
DT = 10.0             # ns / sample
CEIL = 7000.0

# ---- dead-time / rate model ------------------------------------------------
TAU_EFF_OLD = 90.0    # note assumption (ns)
TAU_EFF_NEW = 124.8   # template live10 measurement (ns)
TAU_EFF_IPCW = 179.0  # IPCW upper estimate (ns)
MU_MAX = 0.38         # max acceptable occupancy (S10 rate model); NOT a beam duty factor
RATES_MHZ = [0.5, 1.0, 2.0, 3.0, 4.0]
FAIL_CEILING = 0.17   # traditional template two-pulse failure ceiling (S10d)
RESOLVE_BINS = 2      # >2 bins (20 ns) separation counts as resolvable
ERR_FAIL_NS = 30.0    # recovered-vs-true separation error that counts as a fail

# data-observed anomalous fractions to compare against
DATA_FRAC_RAW = 0.042
DATA_FRAC_STRAT = 0.02025


def sim_waveform(edep_mev, time_ns, rng, with_noise=True):
    """One-hit waveform: (edep_mev, time_ns) -> 18 ADC samples (float, pre-clip)."""
    t = np.arange(NSAMP) * DT - time_ns
    sig = np.where(t > 0, np.exp(-t / TAU_D) - np.exp(-t / TAU_R), 0.0)
    norm = sig.max() if sig.max() > 0 else 1.0
    adc = PED + edep_mev * GAIN * sig / norm
    if with_noise:
        adc = adc + rng.normal(0, NOISE, NSAMP)
    return adc


def clip_adc(adc):
    return np.clip(np.round(adc), 0, CEIL)


def find_rising_peaks(wave):
    """Locate rising-edge peaks via the first-difference (robust to flat-top
    saturation). Returns sorted sample indices of local derivative maxima."""
    d = np.diff(wave - PED)
    thr = max(3.0 * NOISE, 0.10 * max(d.max(), 1.0))
    peaks = []
    for i in range(1, len(d) - 1):
        if d[i] > thr and d[i] >= d[i - 1] and d[i] > d[i + 1]:
            peaks.append(i)
    # merge peaks closer than 1 bin
    merged = []
    for p in peaks:
        if merged and (p - merged[-1]) < 1:
            continue
        merged.append(p)
    return merged


def recover_two_pulse(wave):
    """Bounded two-pulse recovery. Returns (n_peaks, recovered_sep_ns)."""
    peaks = find_rising_peaks(wave)
    if len(peaks) >= 2:
        sep = (peaks[1] - peaks[0]) * DT
        return len(peaks), float(sep)
    return len(peaks), 0.0


def main():
    ap = argparse.ArgumentParser(description="MV5 pile-up validation")
    ap.add_argument("--truth", default="reports/mv1_mv2_truth_pid_energy_1782220258/truth_tracks.npz")
    ap.add_argument("--out", default=None)
    ap.add_argument("--n-spill", type=int, default=100_000)
    ap.add_argument("--n-overlap", type=int, default=4000)
    args = ap.parse_args()

    rng = np.random.default_rng(SEED)
    np.random.seed(SEED)

    stamp = int(time.time())
    out = Path(args.out or f"reports/mv5_pileup_{stamp}")
    out.mkdir(parents=True, exist_ok=True)

    # ---- load truth tracks -------------------------------------------------
    d = np.load(args.truth)
    pdg = d["pdg"]
    edep_l0 = d["edep_l0"]  # representative single-stave energy
    is_p = pdg == 2212
    is_d = pdg == 1000010020
    # per-stave amplitude proxy: first-layer energy, drop zero-deposit tracks
    e_p = edep_l0[is_p & (edep_l0 > 0.05)]
    e_d = edep_l0[is_d & (edep_l0 > 0.05)]

    summary = {
        "study": "MV5_pileup",
        "truth_file": os.path.abspath(args.truth),
        "seed": SEED,
        "constants": {
            "tau_eff_old_ns": TAU_EFF_OLD, "tau_eff_new_ns": TAU_EFF_NEW,
            "tau_eff_ipcw_ns": TAU_EFF_IPCW, "mu_max": MU_MAX,
            "gain": GAIN, "noise": NOISE, "tau_rise": TAU_R, "tau_decay": TAU_D,
        },
        "n_proton_tracks": int(e_p.size), "n_deuteron_tracks": int(e_d.size),
    }

    # ---- (1) analytic + MC pile-up fraction vs rate ------------------------
    rate_rows = []
    for R in RATES_MHZ:
        # MC spill
        gaps = rng.exponential(1e3 / R, size=args.n_spill)  # ns
        # an event piles up if its gap to the *previous* event < tau_eff
        f_mc_new = float(np.mean(gaps < TAU_EFF_NEW))
        f_mc_old = float(np.mean(gaps < TAU_EFF_OLD))
        # analytic
        p_new = 1.0 - np.exp(-R * TAU_EFF_NEW / 1e3)
        p_old = 1.0 - np.exp(-R * TAU_EFF_OLD / 1e3)
        n = args.n_spill
        ci_new = 1.96 * np.sqrt(f_mc_new * (1 - f_mc_new) / n)
        rate_rows.append({
            "rate_mhz": R,
            "pileup_frac_mc_new": f_mc_new, "pileup_frac_analytic_new": float(p_new),
            "pileup_frac_mc_old": f_mc_old, "pileup_frac_analytic_old": float(p_old),
            "pileup_frac_ci95": float(ci_new),
        })
    summary["pileup_vs_rate"] = rate_rows

    # ---- (2) two-pulse recovery failure rate vs rate -----------------------
    fail_rows = []
    sep_pool = {}  # rate -> array of true separations (for the separation hist)
    for R in RATES_MHZ:
        gaps = rng.exponential(1e3 / R, size=args.n_spill)
        # pile-up pairs = consecutive events within tau_eff_new
        seps = gaps[gaps < TAU_EFF_NEW]
        sep_pool[R] = seps
        if seps.size == 0:
            fail_rows.append({"rate_mhz": R, "n_pairs": 0, "failure_rate": 0.0, "ci95": 0.0})
            continue
        take = min(args.n_overlap, seps.size)
        sub = rng.choice(seps, size=take, replace=False)
        n_fail = 0
        for dt_true in sub:
            # draw two tracks: proton always + (proton or deuteron) 50/50
            a = rng.choice(e_p)
            b = rng.choice(e_d if rng.random() < 0.5 else e_p)
            w1 = sim_waveform(a, 20.0, rng)          # first pulse at t0=20 ns
            w2 = sim_waveform(b, 20.0 + dt_true, rng)
            comb = clip_adc(w1 + w2 - PED)
            _, rec_sep = recover_two_pulse(comb)
            if abs(rec_sep - dt_true) > ERR_FAIL_NS:
                n_fail += 1
        fr = n_fail / take
        ci = 1.96 * np.sqrt(fr * (1 - fr) / take)
        fail_rows.append({"rate_mhz": R, "n_pairs": int(seps.size),
                          "n_eval": int(take), "failure_rate": float(fr),
                          "ci95": float(ci)})
    summary["recovery_failure_vs_rate"] = fail_rows

    # ---- (3) Rmax under three tau_eff assumptions --------------------------
    rmax_rows = []
    for tau in (TAU_EFF_OLD, TAU_EFF_NEW, TAU_EFF_IPCW):
        rmax_raw = 1.0 / (tau * 1e-9) / 1e6           # MHz, pure reciprocal
        rmax_mu = rmax_raw * MU_MAX                    # MHz, occupancy criterion
        rmax_rows.append({
            "tau_eff_ns": tau,
            "rmax_reciprocal_mhz": float(rmax_raw),
            "rmax_duty_corrected_mhz": float(rmax_mu),  # key name kept for artifact compatibility
        })
    summary["rmax_by_tau_eff"] = rmax_rows

    # Rmax* from failure-rate curve (interpolate where failure crosses ceiling)
    fr_rates = np.array([r["rate_mhz"] for r in fail_rows])
    fr_vals = np.array([r["failure_rate"] for r in fail_rows])
    rmax_fail = None
    above = np.where(fr_vals > FAIL_CEILING)[0]
    if above.size and above[0] > 0:
        i = above[0]
        x0, x1 = fr_rates[i - 1], fr_rates[i]
        y0, y1 = fr_vals[i - 1], fr_vals[i]
        rmax_fail = float(x0 + (FAIL_CEILING - y0) * (x1 - x0) / (y1 - y0))
    summary["rmax_from_failure_ceiling_mhz"] = rmax_fail
    summary["failure_ceiling"] = FAIL_CEILING

    # ---- (4) data comparison: infer operating rate from observed fraction --
    def infer_rate(frac, tau_ns):
        return float(-np.log(1.0 - frac) / (tau_ns * 1e-3))  # MHz

    data_cmp = []
    for label, frac in (("raw_4.2pct", DATA_FRAC_RAW), ("stratified_2.025pct", DATA_FRAC_STRAT)):
        for tau in (TAU_EFF_OLD, TAU_EFF_NEW):
            data_cmp.append({
                "observed": label, "observed_frac": frac, "tau_eff_ns": tau,
                "implied_operating_rate_mhz": infer_rate(frac, tau),
            })
    summary["data_comparison"] = data_cmp
    # predicted pile-up at the corrected operating capacity
    summary["pileup_at_rmax_3p05"] = {
        "tau_eff_new": float(1 - np.exp(-3.05 * TAU_EFF_NEW / 1e3)),
        "tau_eff_old": float(1 - np.exp(-3.05 * TAU_EFF_OLD / 1e3)),
    }

    # ===================== PLOTS ===========================================
    fig, ax = plt.subplots(2, 3, figsize=(16, 9))

    # (a) pile-up fraction vs rate
    rr = [r["rate_mhz"] for r in rate_rows]
    ax[0, 0].plot(rr, [r["pileup_frac_analytic_new"] for r in rate_rows], "-o",
                  label=f"analytic tau_eff={TAU_EFF_NEW}ns", color="C0")
    ax[0, 0].plot(rr, [r["pileup_frac_mc_new"] for r in rate_rows], "x",
                  color="C0", ms=10, label="MC tau_eff=124.8ns")
    ax[0, 0].plot(rr, [r["pileup_frac_analytic_old"] for r in rate_rows], "-s",
                  label=f"analytic tau_eff={TAU_EFF_OLD}ns", color="C3")
    ax[0, 0].plot(rr, [r["pileup_frac_mc_old"] for r in rate_rows], "+",
                  color="C3", ms=10, label="MC tau_eff=90ns")
    ax[0, 0].axhline(DATA_FRAC_RAW, ls="--", color="k", lw=1,
                     label=f"data raw {DATA_FRAC_RAW:.3f}")
    ax[0, 0].set_xlabel("beam rate [MHz]"); ax[0, 0].set_ylabel("pile-up fraction")
    ax[0, 0].set_title("(a) Pile-up coincidence fraction vs rate")
    ax[0, 0].legend(fontsize=7); ax[0, 0].grid(alpha=0.3)

    # (b) failure rate vs rate
    ax[0, 1].errorbar(fr_rates, fr_vals,
                      yerr=[r["ci95"] for r in fail_rows], fmt="-o", color="C2")
    ax[0, 1].axhline(FAIL_CEILING, ls="--", color="r",
                     label=f"template ceiling {FAIL_CEILING}")
    if rmax_fail:
        ax[0, 1].axvline(rmax_fail, ls=":", color="purple",
                         label=f"R*={rmax_fail:.2f} MHz")
    ax[0, 1].set_xlabel("beam rate [MHz]")
    ax[0, 1].set_ylabel("two-pulse recovery failure rate")
    ax[0, 1].set_title("(b) Two-pulse recovery failure vs rate")
    ax[0, 1].legend(fontsize=8); ax[0, 1].grid(alpha=0.3)

    # (c) Rmax bar chart
    taus = [r["tau_eff_ns"] for r in rmax_rows]
    xb = np.arange(len(taus))
    ax[0, 2].bar(xb - 0.2, [r["rmax_reciprocal_mhz"] for r in rmax_rows], 0.4,
                 label="1/tau_eff", color="C4")
    ax[0, 2].bar(xb + 0.2, [r["rmax_duty_corrected_mhz"] for r in rmax_rows], 0.4,
                 label=f"x mu_max {MU_MAX}", color="C1")
    ax[0, 2].axhline(3.05, ls="--", color="k", label="data Rmax 3.05")
    ax[0, 2].axhline(4.2, ls=":", color="gray", label="note assumed 4.2")
    ax[0, 2].set_xticks(xb); ax[0, 2].set_xticklabels([f"{t:.0f}ns" for t in taus])
    ax[0, 2].set_ylabel("Rmax [MHz]")
    ax[0, 2].set_title("(c) Rmax under tau_eff assumptions")
    ax[0, 2].legend(fontsize=7); ax[0, 2].grid(alpha=0.3, axis="y")

    # (d) example overlapped waveforms (proton+deuteron at 20/40/80 ns)
    ep0 = float(np.median(e_p)); ed0 = float(np.median(e_d))
    for sep, col in ((20.0, "C0"), (40.0, "C1"), (80.0, "C3")):
        w1 = sim_waveform(ep0, 20.0, rng, with_noise=False)
        w2 = sim_waveform(ed0, 20.0 + sep, rng, with_noise=False)
        comb = clip_adc(w1 + w2 - PED)
        ax[1, 0].plot(np.arange(NSAMP) * DT, comb, "-o", ms=3, color=col,
                      label=f"p+d sep={sep:.0f}ns")
    ax[1, 0].axhline(CEIL, ls=":", color="gray", lw=1)
    ax[1, 0].set_xlabel("time [ns]"); ax[1, 0].set_ylabel("ADC")
    ax[1, 0].set_title("(d) Overlapped p+d waveforms")
    ax[1, 0].legend(fontsize=8); ax[1, 0].grid(alpha=0.3)

    # (e) pulse-separation distribution in pile-up events (3 MHz)
    seps3 = sep_pool.get(3.0, np.array([]))
    if seps3.size:
        ax[1, 1].hist(seps3, bins=40, range=(0, TAU_EFF_NEW), color="C5",
                      edgecolor="k", alpha=0.8)
    ax[1, 1].axvline(RESOLVE_BINS * DT, ls="--", color="r",
                     label=f"resolve limit {RESOLVE_BINS*DT:.0f}ns")
    ax[1, 1].set_xlabel("true pulse separation [ns]")
    ax[1, 1].set_ylabel("pile-up pairs")
    ax[1, 1].set_title("(e) Separation dist. in pile-up (3 MHz)")
    ax[1, 1].legend(fontsize=8); ax[1, 1].grid(alpha=0.3)

    # (f) summary panel: data vs MC
    ax[1, 2].axis("off")
    txt = [
        "MV5 PILE-UP -- DATA vs MC",
        "",
        f"Rmax (mu_max {MU_MAX} / tau), one-sided upper bound:",
        f"  tau=90ns  -> {rmax_rows[0]['rmax_duty_corrected_mhz']:.2f} MHz  (note: 4.2)",
        f"  tau=124.8 -> {rmax_rows[1]['rmax_duty_corrected_mhz']:.2f} MHz  (data: 3.05)",
        f"  tau=179ns -> {rmax_rows[2]['rmax_duty_corrected_mhz']:.2f} MHz",
        "",
        f"R* (failure>{FAIL_CEILING}): "
        + (f"{rmax_fail:.2f} MHz" if rmax_fail else "n/a (below all rates)"),
        "",
        "Operating rate implied by observed pile-up:",
        f"  4.2%   @tau124.8 -> {infer_rate(DATA_FRAC_RAW, TAU_EFF_NEW):.3f} MHz",
        f"  2.025% @tau124.8 -> {infer_rate(DATA_FRAC_STRAT, TAU_EFF_NEW):.3f} MHz",
        "",
        "NOTE: tau_eff=124.8ns is a data INPUT here,",
        "not an MC measurement (retracted as validation).",
        "Rmax <= 3.05 MHz is a one-sided data bound;",
        "the note's 90ns -> 4.2 MHz remains an error.",
    ]
    ax[1, 2].text(0.02, 0.98, "\n".join(txt), va="top", ha="left",
                  family="monospace", fontsize=8.5, transform=ax[1, 2].transAxes)

    fig.suptitle("MV5 -- Pile-up validation (CCB B-stack MC)", fontsize=14)
    fig.tight_layout(rect=[0, 0, 1, 0.97])
    fig.savefig(out / "mv5_pileup.png", dpi=130)
    plt.close(fig)

    # ---- extra example-waveform figure (p+p and p+d, several seps) ---------
    fig2, axx = plt.subplots(2, 4, figsize=(18, 8), sharex=True, sharey=True)
    seps = [20.0, 40.0, 60.0, 80.0]
    for j, sep in enumerate(seps):
        # p+p
        w1 = sim_waveform(ep0, 20.0, rng, with_noise=True)
        w2 = sim_waveform(ep0, 20.0 + sep, rng, with_noise=True)
        comb = clip_adc(w1 + w2 - PED)
        npk, rsep = recover_two_pulse(comb)
        axx[0, j].plot(np.arange(NSAMP) * DT, comb, "-o", ms=3, color="C0")
        axx[0, j].set_title(f"p+p sep={sep:.0f}ns\nfound {npk}pk, rec {rsep:.0f}ns",
                            fontsize=9)
        axx[0, j].grid(alpha=0.3)
        # p+d
        w1 = sim_waveform(ep0, 20.0, rng, with_noise=True)
        w2 = sim_waveform(ed0, 20.0 + sep, rng, with_noise=True)
        comb = clip_adc(w1 + w2 - PED)
        npk, rsep = recover_two_pulse(comb)
        axx[1, j].plot(np.arange(NSAMP) * DT, comb, "-o", ms=3, color="C3")
        axx[1, j].set_title(f"p+d sep={sep:.0f}ns\nfound {npk}pk, rec {rsep:.0f}ns",
                            fontsize=9)
        axx[1, j].grid(alpha=0.3)
    for a in axx[-1, :]:
        a.set_xlabel("time [ns]")
    axx[0, 0].set_ylabel("ADC (p+p)"); axx[1, 0].set_ylabel("ADC (p+d)")
    fig2.suptitle("MV5 -- example overlapped waveforms + two-pulse recovery", fontsize=13)
    fig2.tight_layout(rect=[0, 0, 1, 0.96])
    fig2.savefig(out / "mv5_example_waveforms.png", dpi=130)
    plt.close(fig2)

    # ---- write JSON + REPORT ----------------------------------------------
    (out / "mv5_pileup_summary.json").write_text(json.dumps(summary, indent=2))

    rm = rmax_rows
    report = f"""# MV5 -- Pile-up Validation (MC)

**Generated:** {time.strftime('%Y-%m-%d %H:%M:%S')}
**Truth file:** `{os.path.basename(args.truth)}`  ({summary['n_proton_tracks']} p, {summary['n_deuteron_tracks']} d single-stave amplitudes)
**Seed:** {SEED}

## Question
The data note assumed dead-time tau_eff = 90 ns -> Rmax = 4.2 MHz. Direct waveform
fitting (template "live10") measured tau_eff = 124.8 ns, implying a *lower* Rmax.
This MC study quantifies the pile-up consequences and pins Rmax.

## Rmax under three tau_eff assumptions
| tau_eff [ns] | 1/tau_eff [MHz] | x mu_max ({MU_MAX}) [MHz] |
| --- | --- | --- |
| {rm[0]['tau_eff_ns']:.1f} (note) | {rm[0]['rmax_reciprocal_mhz']:.2f} | **{rm[0]['rmax_duty_corrected_mhz']:.2f}** |
| {rm[1]['tau_eff_ns']:.1f} (measured) | {rm[1]['rmax_reciprocal_mhz']:.2f} | **{rm[1]['rmax_duty_corrected_mhz']:.2f}** |
| {rm[2]['tau_eff_ns']:.1f} (IPCW) | {rm[2]['rmax_reciprocal_mhz']:.2f} | **{rm[2]['rmax_duty_corrected_mhz']:.2f}** |

The data-measured tau_eff = 124.8 ns x mu_max 0.38 -> **{rm[1]['rmax_duty_corrected_mhz']:.2f} MHz**, reproducing the
data-corrected **Rmax = 3.05 MHz**. The note's 90 ns gives {rm[0]['rmax_duty_corrected_mhz']:.2f} MHz (= the
old 4.2 MHz assumption). The 90 -> 124.8 ns dead-time correction *is* the
4.2 -> 3.05 MHz Rmax correction.

R* from the two-pulse recovery failure ceiling ({FAIL_CEILING}): {('%.2f MHz' % rmax_fail) if rmax_fail else 'not reached within [0.5, 4.0] MHz (recovery stays below ceiling)'}.

## Pile-up fraction vs rate (MC vs analytic)
p_pile = 1 - exp(-R x tau_eff / 1e3). MC (exponential-gap draw) matches analytic
within binomial error at every rate; see plot panel (a).

## Data comparison
At Rmax = 3.05 MHz the *raw* coincidence probability is
{summary['pileup_at_rmax_3p05']['tau_eff_new']*100:.1f}% (tau=124.8ns) -- far above the data-observed
{DATA_FRAC_RAW*100:.1f}% anomalous fraction. Inverting the observed fractions:

| observed | tau_eff | implied avg in-spill rate |
| --- | --- | --- |
"""
    for c in data_cmp:
        report += f"| {c['observed']} | {c['tau_eff_ns']:.1f} ns | {c['implied_operating_rate_mhz']:.3f} MHz |\n"
    report += f"""
**Interpretation (corrected 2026-07-03):** IF the observed anomalous fractions
were pure pile-up, they would imply an average in-spill rate of ~0.16-0.48 MHz
under the Poisson model. No measured spill/bunch structure exists in this
analysis, so no statement about instantaneous-vs-average rate can be made; the
"beam is bunched" narrative in earlier versions was unsupported. The 4% class
is a sub-population of unresolved composition (its previous MV6 species
attribution was retracted; see EXTERNAL_REVIEW_2026-07-02.md).

## Artifacts
- `mv5_pileup_summary.json`
- `mv5_pileup.png` (6-panel: fraction, failure, Rmax, overlaps, separation, summary)
- `mv5_example_waveforms.png` (p+p / p+d recovery at 20/40/60/80 ns)

## Verdict (corrected 2026-07-03)
RETRACTED as an MC validation: tau_eff = 124.8 ns entered this study as a data
input, so no independent MC confirmation exists. The data-driven statement
stands on its own: the note's 90 ns assumption is wrong, and the measured
live-time implies a one-sided bound Rmax <= 3.05 MHz (censoring-aware
estimators suggest ~2.1 MHz or lower). An honest MC cross-check requires a
digitizer whose pulse shape is derived independently of these waveforms and
whose tail matches the measured 49-57 ns decay.
"""
    (out / "REPORT.md").write_text(report)

    print(json.dumps({
        "status": "ok", "out": str(out),
        "rmax_duty_124p8": rm[1]["rmax_duty_corrected_mhz"],
        "rmax_duty_90": rm[0]["rmax_duty_corrected_mhz"],
        "rmax_from_failure": rmax_fail,
    }, indent=2))
    print(f"[ok] wrote {out}/mv5_pileup_summary.json")


if __name__ == "__main__":
    main()
