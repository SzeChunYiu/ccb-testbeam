#!/usr/bin/env python3
"""
mv4_timing_study.py
===================
MV4 -- timing-resolution MC validation for the CCB test-beam B-stack.

Pipeline (per B-arm truth track):
  1. group hits by Sci_bar_TrackID; collect (time_ns, EDep, LayerID, PDG)
  2. simulate the 18-sample ADC waveform from the calibrated digitizer model
     (gain, noise, pedestal, tau_rise, tau_decay), integrating the unit-peak
     scintillation shape over each 10 ns sample bin, with a deterministic
     sub-sample phase + noise seeded by event_id (no global RNG state)
  3. CFD20 pick-off (20% of peak), rising-edge constrained: find the peak
     sample, scan BACKWARD from the peak for the last prev < thr <= cur
     crossing, linear interpolation -> t_cfd (fixed 2026-07-03: the old
     forward-from-sample-0 scan latched onto pre-signal noise crossings)
  4. truth time = earliest hit time of the track (placed at a known window offset)
  5. residual  delta_t = t_cfd - t_truth ; sigma68 = (p84-p16)/2
  6. analytic amplitude timewalk correction  delta_t = A + B/amp (1/A form,
     fixed 2026-07-01 per MV4b; see reports/mv4b_timewalk_model/REPORT.md --
     was 1/sqrt(amp), which gave an unphysical negative B),
     fit on half the tracks, applied to the other half;
     report corrected sigma68
  7. compare to data: the MC residual is SINGLE-TRACE; the data anchors are
     pooled two-stave PAIR-DIFFERENCE sigma68s (raw CFD20 ~ 2.993 ns from
     S02 head_to_head_benchmark cfd20_reference; ML-corrected ~ 1.50 ns).
     MC is converted to pair-equivalent via *sqrt(2) (independent staves)
     and the MC/data RATIO is reported with the MC bootstrap error only.
     No pull-based PASS/TENSION verdict is emitted: the comparison is
     unmatched (merged-track MC vs per-stave data, unmatched selection).

===========================================================================
NOTE (EXTERNAL_REVIEW_2026-07-02.md): ALL digitizer ADC/MeV gains are
RETRACTED. The default gain used here only sets the amplitude/noise scale
of the toy digitizer; no ADC/MeV physics claim is made or implied.

DEPRECATED DIGITIZER CONSTANTS (Phase 1, 2026-07-03): the inline toy
digitizer below (DEFAULTS: gain 246, noise 50, pedestal 350, tau 2.5/42)
is DEPRECATED in favour of the single calibration card
configs/mc_validation/digitizer_card.yaml (data-anchored: pedestal 6752,
noise 8, per-stave tau_decay B2 56.7 / B4 51.7 / B6 49.4 / B8 50.1 ns)
consumed via DigitizerPipeline.from_card(). This script's internals are
intentionally NOT rewritten; treat its absolute numbers as toy-scale only
and use scripts/mc02_build_mc_pulse_table.py for card-driven MC pulses.
===========================================================================

Outputs (reports/mv4_timing_STAMP/):
  mv4_summary.json
  mv4_waveform_examples.png   proton + deuteron simulated waveforms w/ CFD
  mv4_residuals.png           residual before/after timewalk
  mv4_sigma_vs_amp.png        sigma68 vs amplitude (timewalk validation)
  mv4_data_vs_mc.png          pair-equivalent MC vs data sigma68
  mv4_ratio.png               MC/data ratio (MC bootstrap error only)
  REPORT.md

Usage:
  mv4_timing_study.py --mc <root> --out <dir> [--calib calibration.json]
      [--max-tracks N] [--max-events N]
"""
import argparse
import json
import os
from datetime import datetime, timezone
from functools import lru_cache

import numpy as np

B_ARM = 1
PROTON, DEUTERON = 2212, 1000010020

# ---------------------------------------------------------------------------
# Data anchors: pooled two-stave PAIR-DIFFERENCE sigma68s [ns].
#
# DATA_SIGMA_RAW is the true raw CFD20 pooled pair-difference sigma68 from
#   reports/1780997954.15157.07ef03cf__s02_timing_pickoff/head_to_head_benchmark.csv
#   row `cfd20_reference` (2.9933861916712807 ns).
# The previous value here (1.85, commented "S02 raw CFD20") was WRONG: 1.85 is
# the ML-ridge-CORRECTED number (`ml_ridge` row, 1.846 ns), not the raw CFD20.
#
# DATA_SIGMA_CORRECTED (1.50, S03) is kept for reference only.
#
# NOTE: these are PAIR-DIFFERENCE numbers; the MC residual below is
# single-trace, so MC must be multiplied by sqrt(2) before comparing.
# ---------------------------------------------------------------------------
DATA_SIGMA_RAW = 2.993
DATA_SIGMA_CORRECTED = 1.50

DEFAULTS = dict(gain_adc_per_mev=246.0, noise_adc_rms=50.0, pedestal_adc=350.0,
                tau_rise_ns=2.5, tau_decay_ns=42.0, n_samples=18, sample_spacing_ns=10.0,
                adc_ceiling=7000.0)
PRE_OFFSET_NS = 40.0   # window offset where the earliest hit is placed
N_SUBPOINTS = 5        # sub-bin integration points


@lru_cache(maxsize=None)
def charge(pdg):
    pdg = int(pdg); a = abs(pdg)
    if a > 1_000_000_000:
        return (a // 10_000) % 1000
    return {2212: 1, 2112: 0, 22: 0, 11: 1, 13: 1, 211: 1, 321: 1}.get(a, 0)


def sigma68(x):
    x = np.asarray(x, dtype=float)
    if x.size < 5:
        return float("nan")
    lo, hi = np.percentile(x, [16, 84])
    return float((hi - lo) / 2.0)


def boot_sigma68(x, n_boot=200, seed=12345):
    x = np.asarray(x, dtype=float)
    if x.size < 20:
        return float("nan")
    rng = np.random.default_rng(seed)
    vals = [sigma68(rng.choice(x, size=x.size, replace=True)) for _ in range(n_boot)]
    return float(np.std(vals))


class Digitizer:
    def __init__(self, p):
        self.gain = p["gain_adc_per_mev"]
        self.noise = p["noise_adc_rms"]
        self.ped = p["pedestal_adc"]
        self.tr = p["tau_rise_ns"]
        self.td = p["tau_decay_ns"]
        self.ns = int(p["n_samples"])
        self.dt = p["sample_spacing_ns"]
        self.ceiling = p["adc_ceiling"]
        # unit-peak normalization of (exp(-t/td)-exp(-t/tr))
        t_peak = (self.tr * self.td / (self.td - self.tr)) * np.log(self.td / self.tr)
        self.norm = np.exp(-t_peak / self.td) - np.exp(-t_peak / self.tr)
        # sample-center times and sub-bin integration offsets
        self.centers = np.arange(self.ns) * self.dt
        self.suboff = np.linspace(-self.dt / 2, self.dt / 2, N_SUBPOINTS)
        # sub-point time grid: shape (ns, nsub)
        self.subgrid = self.centers[:, None] + self.suboff[None, :]

    def _unit_shape(self, t):
        out = np.zeros_like(t)
        m = t > 0
        out[m] = (np.exp(-t[m] / self.td) - np.exp(-t[m] / self.tr)) / self.norm
        return out

    def waveform(self, hit_times, hit_amps, rng):
        """hit_times: arrival times (ns, window coords); hit_amps: ADC peak amplitudes."""
        wf = np.full(self.ns, self.ped, dtype=float)
        # integrate unit-peak shape over each sample bin (mean over sub-points)
        for a, amp in zip(hit_times, hit_amps):
            contrib = self._unit_shape(self.subgrid - a).mean(axis=1)  # (ns,)
            wf += amp * contrib
        wf += rng.normal(0.0, self.noise, self.ns)
        np.clip(wf, None, self.ceiling, out=wf)
        return wf

    def cfd20(self, wf):
        """Rising-edge-constrained CFD at 20% of peak.

        FIX (2026-07-03, external review): the old implementation took the
        FIRST sample >= threshold scanning forward from sample 0. Since the
        threshold (0.2*peak) can be ~1 sigma of noise at low amplitude,
        pre-signal noise crossings fired ~50% of the time, corrupting t_cfd.
        Now: find the peak sample first, then scan BACKWARD from the peak for
        the last crossing where prev < thr <= cur, and linearly interpolate
        (same pattern as s05c_hierarchical_bstack_covariance.cfd_quantities,
        which constrains the crossing to sample_index <= peak).
        """
        w = wf - self.ped
        jp = int(np.argmax(w))
        peak = float(w[jp])
        if peak <= 0:
            return float("nan"), peak
        thr = 0.20 * peak
        for j in range(jp, 0, -1):
            if w[j - 1] < thr <= w[j]:
                # prev < thr <= cur guarantees w[j] > w[j-1]
                frac = (thr - w[j - 1]) / (w[j] - w[j - 1])
                return float(self.centers[j - 1] + frac * self.dt), peak
        # no rising-edge crossing before the peak (e.g. peak at sample 0)
        return float(self.centers[jp]), peak


def load_digitizer_params(calib_path):
    p = dict(DEFAULTS)
    if calib_path and os.path.exists(calib_path):
        try:
            with open(calib_path) as fh:
                cj = json.load(fh)
            c = cj.get("calibration", {})
            if c.get("gain_adc_per_mev"):
                p["gain_adc_per_mev"] = float(c["gain_adc_per_mev"])
            # NOTE: only the gain is data-driven. The MV0 "pedestal" is the data
            # DAQ baseline (~6758 ADC), a raw offset specific to the readout; it
            # must NOT be used as the toy-digitizer DC level (it sits at the ADC
            # ceiling and would clip all signal). Timing resolution depends on
            # SNR, not the absolute pedestal, so we keep the digitizer's own.
            print(f"[mv4] loaded calibration: gain={p['gain_adc_per_mev']:.1f} "
                  f"(pedestal kept at digitizer default {p['pedestal_adc']:.0f})")
        except Exception as e:
            print(f"[mv4] WARN could not read calib ({e}); using defaults")
    else:
        print("[mv4] no calibration card; using default digitizer params")
    return p


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--mc", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--tree", default="hibeam")
    ap.add_argument("--calib", default=None)
    ap.add_argument("--max-tracks", type=int, default=80000)
    ap.add_argument("--max-events", type=int, default=0)
    args = ap.parse_args()
    os.makedirs(args.out, exist_ok=True)
    print(f"[mv4] start={datetime.now(timezone.utc).isoformat()}")
    print(f"[mv4] mc={args.mc}")

    params = load_digitizer_params(args.calib)
    dig = Digitizer(params)

    import uproot
    br = ["Sci_bar_TrackID", "Sci_bar_LayerID1", "Sci_bar_PDG", "Sci_bar_EDep", "Sci_bar_Time"]

    residual, amp_adc, pdg_arr = [], [], []
    examples = {}  # pdg -> (centers, wf, t_cfd, t_truth, peak)
    tree = uproot.open(args.mc)[args.tree]
    stop = args.max_events if args.max_events and args.max_events > 0 else None
    ev_global = 0
    n_tracks = 0
    done = False
    for ch in tree.iterate(br, step_size="200 MB", library="np", entry_stop=stop):
        TID = ch["Sci_bar_TrackID"]; L1 = ch["Sci_bar_LayerID1"]
        PD = ch["Sci_bar_PDG"]; ED = ch["Sci_bar_EDep"]; TM = ch["Sci_bar_Time"]
        for i in range(len(L1)):
            eid = ev_global; ev_global += 1
            l1 = L1[i]
            if len(l1) == 0:
                continue
            isB = l1 == B_ARM
            if not isB.any():
                continue
            tid = TID[i]; pd = PD[i]; ed = ED[i]; tm = TM[i]
            for tr in np.unique(tid[isB]):
                m = isB & (tid == tr)
                p0 = int(pd[m][0])
                if charge(p0) < 1:
                    continue
                times = tm[m].astype(float)
                edeps = ed[m].astype(float)
                if edeps.sum() <= 0 or not np.isfinite(times).all():
                    continue
                t0 = float(times.min())
                rng = np.random.default_rng(eid * 100003 + (int(tr) & 0xFFFF))
                phase = float(rng.uniform(0.0, dig.dt))
                t_truth = PRE_OFFSET_NS + phase
                arr = (times - t0) + t_truth            # hit arrivals in window coords
                amps = edeps * dig.gain                 # per-hit ADC peak amplitude
                wf = dig.waveform(arr, amps, rng)
                t_cfd, peak = dig.cfd20(wf)
                if not np.isfinite(t_cfd) or peak < 5 * dig.noise:
                    continue
                residual.append(t_cfd - t_truth)
                amp_adc.append(peak)
                pdg_arr.append(p0)
                n_tracks += 1
                if p0 in (PROTON, DEUTERON) and p0 not in examples and peak > 8 * dig.noise:
                    examples[p0] = (dig.centers.copy(), wf.copy(), t_cfd, t_truth, peak)
                if n_tracks >= args.max_tracks:
                    done = True
                    break
            if done:
                break
        if done:
            break

    residual = np.asarray(residual); amp_adc = np.asarray(amp_adc); pdg_arr = np.asarray(pdg_arr)
    print(f"[mv4] tracks used={residual.size} (events scanned={ev_global})")
    if residual.size < 100:
        raise SystemExit("[mv4] too few tracks; aborting")

    # raw sigma68
    raw_sigma = sigma68(residual)
    raw_unc = boot_sigma68(residual)

    # ---- analytic timewalk: dt = A + B/amp, fit on half, apply to other ----
    # FIX (2026-07-01, MV4b follow-up -- see reports/mv4b_timewalk_model/REPORT.md
    # and docs/09_open_questions.md "MV4 residual: timewalk B coefficient"):
    # this previously fit dt = A + B/sqrt(amp). For a leading-edge discriminator
    # on an exponential-rise pulse V(t) = A*(1-exp(-(t-t0)/tau_rise)), the
    # threshold-crossing time is t_cross = t0 + tau_rise*ln(A/(A-V_th)), which
    # for A >> V_th expands to dt_tw ~= tau_rise*V_th/A -- a 1/A functional
    # form, not 1/sqrt(A). The 1/sqrt(A) form belongs to PMT-style
    # photoelectron-counting statistics (sigma ~ sqrt(N)), which does not apply
    # here: this digitizer integrates the full waveform, not photon counts.
    # Fitting the wrong functional form previously produced an unphysical
    # negative B (B = -23.00 ns*sqrt(ADC), meaning larger pulses got MORE
    # correction added instead of less) and an MV4-corrected-path pull of
    # +2.68 (TENSION) against a raw-path pull of only -1.05 (PASS). [Historical
    # note: pull-based verdicts have since been removed entirely -- the data
    # uncertainty was an assumption and the comparison is unmatched; the report
    # now emits only the MC/data ratio with MC bootstrap error.] Switching to
    # the physical 1/A form must be confirmed by re-running on LUNARC, not
    # assumed from this comment alone.
    #
    # Robust fit: the walk curve is fit to MEDIAN residual per amplitude bin on
    # the training half (per-track OLS in 1/amp is dominated by low-amp
    # noise leverage and overcorrects). This honours the train/test split while
    # giving a stable, physical walk curve.
    x = 1.0 / np.clip(amp_adc, 1.0, None)
    n = residual.size
    fit_mask = np.arange(n) % 2 == 0
    app_mask = ~fit_mask
    af, rf, xf = amp_adc[fit_mask], residual[fit_mask], x[fit_mask]
    edges = np.unique(np.percentile(af, np.linspace(0, 100, 11)))
    bx, by = [], []
    for a, b in zip(edges[:-1], edges[1:]):
        mb = (af >= a) & (af < b)
        if mb.sum() >= 30:
            bx.append(float(np.median(1.0 / np.clip(af[mb], 1.0, None))))
            by.append(float(np.median(rf[mb])))
    if len(bx) >= 2:
        B, A = np.polyfit(np.asarray(bx), np.asarray(by), 1)  # median_residual = B*x + A
    else:
        B, A = 0.0, float(np.median(rf))
    pred = A + B * x
    corrected = residual - pred
    corr_sigma_test = sigma68(corrected[app_mask])
    corr_unc = boot_sigma68(corrected[app_mask])
    corr_sigma_all = sigma68(corrected)
    print(f"[mv4] timewalk fit: A={A:.3f} ns  B={B:.2f} ns*ADC (1/A form; was ns*sqrt(ADC) pre-MV4b-fix)")
    print(f"[mv4] sigma68 raw={raw_sigma:.3f}+/-{raw_unc:.3f}  "
          f"corrected(test)={corr_sigma_test:.3f}+/-{corr_unc:.3f}")

    # ---- sigma68 vs amplitude (before/after) ----
    qs = np.percentile(amp_adc, np.linspace(0, 100, 9))
    qs = np.unique(qs)
    centers_amp, sig_raw_bin, sig_corr_bin, sig_raw_err, sig_corr_err = [], [], [], [], []
    for a, b in zip(qs[:-1], qs[1:]):
        mb = (amp_adc >= a) & (amp_adc < b)
        if mb.sum() < 30:
            continue
        centers_amp.append(float(0.5 * (a + b)))
        sig_raw_bin.append(sigma68(residual[mb]))
        sig_corr_bin.append(sigma68(corrected[mb]))
        sig_raw_err.append(boot_sigma68(residual[mb], n_boot=100))
        sig_corr_err.append(boot_sigma68(corrected[mb], n_boot=100))

    # ---- pair-equivalent MC vs data (RATIO only; no pull, no PASS/TENSION) ----
    # The MC residual is single-trace (t_cfd - t_truth), while the data anchors
    # are pooled two-stave PAIR-DIFFERENCE sigma68s. Assuming INDEPENDENT stave
    # errors, a pair difference carries sqrt(2) x the single-stave sigma, so
    # the pair-equivalent MC number is mc_sigma * sqrt(2).
    # The data sigma68 uncertainty is not measured (the old 0.10 ns was an
    # assumption), so no pull is computed: we report the MC/data RATIO with the
    # MC bootstrap error only.
    SQRT2 = float(np.sqrt(2.0))
    raw_pair, raw_pair_unc = raw_sigma * SQRT2, raw_unc * SQRT2
    corr_pair, corr_pair_unc = corr_sigma_test * SQRT2, corr_unc * SQRT2
    ratio_raw = raw_pair / DATA_SIGMA_RAW
    ratio_raw_unc = raw_pair_unc / DATA_SIGMA_RAW
    ratio_corr = corr_pair / DATA_SIGMA_CORRECTED
    ratio_corr_unc = corr_pair_unc / DATA_SIGMA_CORRECTED
    VERDICT = ("REVIEW — unmatched comparison (merged-track MC vs per-stave data; "
               "selection unmatched; gain retracted); matched per-stave rerun "
               "pending Phase 1 digitizer")

    summary = {
        "study_id": "MV4",
        "generated_utc": datetime.now(timezone.utc).isoformat(),
        "mc_file": os.path.abspath(args.mc),
        "n_tracks": int(residual.size),
        "n_events_scanned": int(ev_global),
        "digitizer_params": params,
        "timewalk_fit": {"A_ns": float(A), "B_ns_ADC": float(B), "timewalk_functional_form": "1/A (MV4b-fixed 2026-07-01, was 1/sqrt(A))"},
        "sigma68_ns": {
            "raw": raw_sigma, "raw_unc": raw_unc,
            "corrected_test_half": corr_sigma_test, "corrected_unc": corr_unc,
            "corrected_all": corr_sigma_all,
        },
        "residual_median_ns": float(np.median(residual)),
        "gain_retraction_note": ("all digitizer ADC/MeV gains RETRACTED per "
                                 "EXTERNAL_REVIEW_2026-07-02.md; gain here only sets the "
                                 "toy amplitude/noise scale, no ADC/MeV claim"),
        "data_reference": {
            "S02_raw_cfd20_pair_sigma68": DATA_SIGMA_RAW,
            "S02_raw_source": ("reports/1780997954.15157.07ef03cf__s02_timing_pickoff/"
                               "head_to_head_benchmark.csv row cfd20_reference"),
            "S03_corrected_pair_sigma68": DATA_SIGMA_CORRECTED,
            "semantics": "pooled two-stave pair-difference sigma68; data unc not measured",
        },
        "mc_pair_equivalent_ns": {
            "raw": raw_pair, "raw_unc": raw_pair_unc,
            "corrected": corr_pair, "corrected_unc": corr_pair_unc,
            "conversion": "mc_sigma * sqrt(2), assuming independent stave errors",
        },
        "mc_over_data_ratio": {
            "raw": ratio_raw, "raw_unc_mc_only": ratio_raw_unc,
            "corrected": ratio_corr, "corrected_unc_mc_only": ratio_corr_unc,
        },
        "verdict": VERDICT,
        "improvement_factor": float(raw_sigma / corr_sigma_test) if corr_sigma_test else None,
        "n_proton": int((pdg_arr == PROTON).sum()),
        "n_deuteron": int((pdg_arr == DEUTERON).sum()),
    }
    with open(os.path.join(args.out, "mv4_summary.json"), "w") as fh:
        json.dump(summary, fh, indent=2)
    print(f"[mv4] wrote {args.out}/mv4_summary.json")

    # ---- plots ----
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    # 1. example waveforms
    fig, axs = plt.subplots(1, 2, figsize=(12, 4.8))
    for ax, (p0, lab) in zip(axs, [(PROTON, "proton"), (DEUTERON, "deuteron")]):
        if p0 in examples:
            c, wf, t_cfd, t_truth, peak = examples[p0]
            ax.plot(c, wf, "o-", color="C0", ms=4, label="ADC samples")
            ax.axhline(dig.ped + 0.20 * peak, color="C2", ls=":", label="20% CFD thr")
            ax.axvline(t_cfd, color="C3", ls="--", label=f"t_cfd={t_cfd:.1f}")
            ax.axvline(t_truth, color="k", ls="-.", lw=1, label=f"t_truth={t_truth:.1f}")
            ax.set_title(f"{lab}  peak={peak:.0f} ADC")
        else:
            ax.set_title(f"{lab} (no example)")
        ax.set_xlabel("time [ns]"); ax.set_ylabel("ADC")
        ax.legend(fontsize=8)
    fig.suptitle("MV4 simulated waveforms with CFD20 pick-off")
    fig.tight_layout(); fig.savefig(os.path.join(args.out, "mv4_waveform_examples.png"), dpi=130)
    plt.close(fig)

    # 2. residual before/after
    fig, ax = plt.subplots(figsize=(8, 5))
    rng_lo, rng_hi = np.percentile(residual, [1, 99])
    bins = np.linspace(rng_lo, rng_hi, 70)
    ax.hist(residual, bins=bins, histtype="step", color="C0", lw=1.8,
            label=f"raw  sigma68={raw_sigma:.2f} ns")
    ax.hist(corrected + np.median(residual), bins=bins, histtype="step", color="C3", lw=1.8,
            label=f"timewalk-corr  sigma68={corr_sigma_test:.2f} ns")
    ax.set_xlabel("t_cfd - t_truth [ns]"); ax.set_ylabel("tracks")
    ax.set_title("MV4 timing residual"); ax.legend()
    fig.tight_layout(); fig.savefig(os.path.join(args.out, "mv4_residuals.png"), dpi=130)
    plt.close(fig)

    # 3. sigma68 vs amplitude
    fig, ax = plt.subplots(figsize=(8, 5))
    if centers_amp:
        ax.errorbar(centers_amp, sig_raw_bin, yerr=sig_raw_err, fmt="o-", color="C0", label="raw", capsize=3)
        ax.errorbar(centers_amp, sig_corr_bin, yerr=sig_corr_err, fmt="s-", color="C3", label="timewalk-corr", capsize=3)
    ax.set_xlabel("pulse amplitude [ADC]"); ax.set_ylabel("sigma68 [ns]")
    ax.set_title("MV4 sigma68 vs amplitude (timewalk validation)"); ax.legend()
    fig.tight_layout(); fig.savefig(os.path.join(args.out, "mv4_sigma_vs_amp.png"), dpi=130)
    plt.close(fig)

    # 4. data vs MC sigma comparison (MC converted to pair-equivalent, *sqrt(2))
    fig, ax = plt.subplots(figsize=(7, 5))
    labels = ["raw CFD20", "timewalk-corr"]
    mc_vals = [raw_pair, corr_pair]; mc_errs = [raw_pair_unc, corr_pair_unc]
    data_vals = [DATA_SIGMA_RAW, DATA_SIGMA_CORRECTED]
    xpos = np.arange(len(labels)); w = 0.35
    ax.bar(xpos - w / 2, mc_vals, w, yerr=mc_errs, capsize=4, color="C0",
           label="MC pair-equivalent (sigma*sqrt(2))")
    ax.bar(xpos + w / 2, data_vals, w, color="C1",
           label="data pair-diff sigma68 (unc not measured)")
    ax.set_xticks(xpos); ax.set_xticklabels(labels)
    ax.set_ylabel("pair-difference sigma68 [ns]")
    ax.set_title("MV4 pair-equivalent MC vs data (unmatched comparison)"); ax.legend()
    fig.tight_layout(); fig.savefig(os.path.join(args.out, "mv4_data_vs_mc.png"), dpi=130)
    plt.close(fig)

    # 5. ratio plot (MC bootstrap error only; no pull -- data unc not measured)
    fig, ax = plt.subplots(figsize=(7, 4.5))
    ratios = [ratio_raw, ratio_corr]
    ratio_errs = [ratio_raw_unc, ratio_corr_unc]
    ax.bar(labels, ratios, yerr=ratio_errs, capsize=4, color=["C0", "C3"])
    ax.axhline(1.0, color="k", lw=1, ls="--")
    ax.set_ylabel("MC(pair-equiv) / data")
    ax.set_title("MV4 MC/data ratio (MC bootstrap error only; unmatched comparison)")
    fig.tight_layout(); fig.savefig(os.path.join(args.out, "mv4_ratio.png"), dpi=130)
    plt.close(fig)

    # ---- REPORT.md ----
    lines = []
    lines.append("# MV4 -- Timing-Resolution MC Validation\n")
    lines.append("> **NOTE (EXTERNAL_REVIEW_2026-07-02.md):** all digitizer ADC/MeV gains are "
                 "**RETRACTED**. The default gain used here only sets the amplitude/noise scale "
                 "of the toy digitizer; **no ADC/MeV physics claim is made**.\n")
    lines.append("- status: **REVIEW**")
    lines.append(f"- generated: {summary['generated_utc']}")
    lines.append(f"- MC: `{summary['mc_file']}`")
    lines.append(f"- tracks used: {residual.size} (proton {summary['n_proton']}, deuteron {summary['n_deuteron']})")
    lines.append(f"- digitizer: gain={params['gain_adc_per_mev']:.0f} ADC/MeV, noise={params['noise_adc_rms']:.0f} ADC, "
                 f"ped={params['pedestal_adc']:.0f}, tau_rise={params['tau_rise_ns']}, tau_decay={params['tau_decay_ns']} ns\n")
    lines.append("## Reproduce")
    lines.append("```")
    lines.append(f"{os.path.basename(__file__)} --mc <root> --out <dir> "
                 f"--calib <mv0 calibration.json> --max-tracks {args.max_tracks}")
    lines.append("```\n")
    lines.append("## Key metrics")
    lines.append("| quantity | value |")
    lines.append("|---|---|")
    lines.append(f"| raw CFD20 sigma68 | {raw_sigma:.3f} +/- {raw_unc:.3f} ns |")
    lines.append(f"| timewalk-corrected sigma68 | {corr_sigma_test:.3f} +/- {corr_unc:.3f} ns |")
    lines.append(f"| improvement factor | {summary['improvement_factor']:.2f}x |")
    lines.append(f"| timewalk fit A | {A:.3f} ns |")
    lines.append(f"| timewalk fit B | {B:.2f} ns*ADC (1/A form) |")
    lines.append(f"| residual median | {np.median(residual):.3f} ns |\n")
    lines.append("## Methodology")
    lines.append("- Per B-arm charged truth track: 18-sample ADC waveform from the unit-peak scintillation "
                 "shape (integrated over each 10 ns bin), per-hit amp = EDep*gain, plus Gaussian noise.")
    lines.append("- Deterministic sub-sample phase + noise seeded by `event_id` (no global RNG) so the run is reproducible.")
    lines.append("- CFD20: rising-edge constrained -- find the peak sample, scan backward from the peak for the "
                 "last prev < thr <= cur crossing (thr = 20% of peak), linear interpolation -> t_cfd. "
                 "(Fixed 2026-07-03: the old forward-from-sample-0 scan fired on pre-signal noise crossings.)")
    lines.append("- Truth time = earliest hit time, placed at a fixed window offset; residual = t_cfd - t_truth.")
    lines.append("- Timewalk model dt = A + B/amp (physical 1/A leading-edge form, MV4b fix 2026-07-01): "
                 "fit on even-index tracks, applied to odd-index tracks; sigma68 reported on the held-out half.\n")
    lines.append("## Comparison to data (unmatched -- see verdict)")
    lines.append("- The MC residual is **single-trace** (t_cfd - t_truth); the data anchors are pooled "
                 "two-stave **pair-difference** sigma68s. MC is converted to pair-equivalent via "
                 "`mc_sigma * sqrt(2)` (assumes independent stave errors).")
    lines.append("- Data anchor: raw CFD20 pair-difference sigma68 = "
                 f"{DATA_SIGMA_RAW:.3f} ns (S02 head_to_head_benchmark.csv, row cfd20_reference); "
                 f"ML-corrected reference = {DATA_SIGMA_CORRECTED:.2f} ns (S03).")
    lines.append("- The data sigma68 uncertainty is not measured, so **no pull is computed**; the ratio "
                 "error below is the MC bootstrap error only.\n")
    lines.append("| stage | MC single-trace [ns] | MC pair-equiv [ns] | data pair-diff [ns] | MC/data ratio |")
    lines.append("|---|---|---|---|---|")
    lines.append(f"| raw CFD20 | {raw_sigma:.3f}+/-{raw_unc:.3f} | {raw_pair:.3f}+/-{raw_pair_unc:.3f} | "
                 f"{DATA_SIGMA_RAW:.3f} (S02) | {ratio_raw:.3f}+/-{ratio_raw_unc:.3f} |")
    lines.append(f"| timewalk-corr | {corr_sigma_test:.3f}+/-{corr_unc:.3f} | {corr_pair:.3f}+/-{corr_pair_unc:.3f} | "
                 f"{DATA_SIGMA_CORRECTED:.2f} (S03) | {ratio_corr:.3f}+/-{ratio_corr_unc:.3f} |\n")
    lines.append("## MC verdict")
    lines.append(f"- **{VERDICT}**")
    lines.append("- The ratio quantifies agreement scale only; it is not a hypothesis test. A matched "
                 "comparison requires a per-stave MC digitization with the data selection applied.\n")
    lines.append("## Open questions")
    lines.append("- Absolute residual offset is set by the (arbitrary) window placement; only the spread (sigma68) "
                 "is physical. A common global time reference would let MC reproduce the data offset too.")
    lines.append("- Noise RMS and tau values are taken from the digitizer card; an MV0-style data-driven fit of "
                 "the pulse shape (rise/decay) would remove the remaining modeling freedom.")
    lines.append("- Multi-hit pile-up within a track is included; cross-track pile-up in a stave (MV5) is not.")
    with open(os.path.join(args.out, "REPORT.md"), "w") as fh:
        fh.write("\n".join(lines) + "\n")
    print(f"[mv4] wrote {args.out}/REPORT.md")
    print(f"[mv4] done={datetime.now(timezone.utc).isoformat()}")


if __name__ == "__main__":
    main()
