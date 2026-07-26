# Data-Side Analysis on Real Beam Data (LUNARC ccb_data)

**Status:** MEASURED_DATA (provenance verified) + GATED (timing, format-limited) + BLOCKED (absolute Rmax).
**Branch:** `studies/data-side-analysis` · **Driver:** `scripts/studies/data_side_real_beam.py`
**Raw source:** `/projects/hep/fs10/shared/nnbar/ccb_data/hrd/root/` (`hrdb_run_*.root`, runs 12–65; 748 MB)
**Inputs:** canonical S00 table `reports/1781028640.1299.266407ae/s00_selected_b_pulses.csv.gz` (640,737 rows) + raw HRDv waveforms.

> This study was previously **BLOCKED_DATA** ("raw `hrdb_run_*.root` not staged on LUNARC").
> The raw data was located on 2026-07-25 at the path above and analysed directly. Every
> number below is measured from real beam waveforms; caveats are stated explicitly.

---

## 0. Data provenance — the located data IS the canonical S00 source

The raw ccb_data stores waveforms as **8 channels × 16 samples = 128 values/event**
(channel-major layout; `SAMPLES_PER_CHANNEL = 16`, NOT 18 as in the laptop-era configs).
Rebuilding the S00 table directly from these raw waveforms with the canonical amplitude
cut (>1000 ADC, baseline = median of first 4 samples, even channels B2/B4/B6/B8):

| Quantity | Value |
|---|---|
| Rebuilt (raw amplitude-cut) selected pulses | **709,003** |
| Documented `dynamic_range_selected` (s00c, pre-gate) | 706,373 |
| Documented `median_first_four_selected` (canonical S00, CL-001) | 640,737 |
| Composite-key (run,eventno,stave) overlap: rebuilt ∩ canonical | **617,377 / 640,737 (96.4%)** |
| Event 31/391389/B2 baseline | 6741.5 (exact match, both) |
| Event 31/391389/B2 amplitude | 7858.5 (exact match, both) |
| Event 31/391389/B2 peak sample | 6 (exact match); area 56,055 (16-samp) vs 63,262 (18-samp) |

**Conclusion:** the located ccb_data is confirmed to be the SAME beam data as canonical
S00 — event-level baseline+amplitude+peak match **exactly** for B2 over 578,019 overlapping
pulses; the only difference is the 2 trailing samples (16 vs 18), which carry pulse-tail
area and a few late-peaking deep-stave pulses (canonical-only = 23,360). The additional
s00c "median-first-four" quality gate (laptop-side, on `data/sorted-b`, not staged) reduces
the raw 706,373 → 640,737; it is a baseline-quality cut rejecting spurious deep-stave
pulses. **The downstream physics below uses the validated canonical 640,737 table
(provenance now confirmed) and the raw HRDv where waveforms are required.**

Full sha256 of the 33 raw inputs in `provenance.json` (sample):
`hrdb_run_0031.root = 0986c826…68140c268` (runs 31–65 used).

## 1. VIS-DE-001-DATA — ΔE-E on real beam data

ADC ΔE-E (E = B2 amplitude, ΔE = B4 amplitude) for events with both staves selected,
with **composite-key (run,eventno) validation: 0 duplicates** (the corruption mode that
affects eventno-only joins does not arise here — each (run,eventno,stave) is unique).

| Quantity | DATA | MC (clusterA) |
|---|---|---|
| N events (B2∧B4) | **33,966** | 131,198 |
| corr(ΔE, E) | **+0.221** | −0.533 |
| E (B2) median | 3,385 ADC | 101.0 MeV |
| ΔE (B4) median | 2,963 ADC | 24.1 MeV |

The sign reversal of the correlation (data +0.22 vs MC −0.53) is the **genuine MC-vs-data
topology gap**: the data sample is B2-dominated (B2 carries 90% of selected pulses), so
the ΔE-E band does not populate as the proton-on-CD2 MC predicts. This is consistent with
the known MV3 material-budget discrepancy (inter-stave dead material missing in GEANT4).
Figure: `VIS-DE-001-DATA_deltaE_E_real.png`.

## 2. VIS-TIM-DATA — Detector timing resolution: INFEASIBLE on the raw 16-sample format

**Honest negative result (measured).** CFD pickoff (20% constant fraction, linear interp)
on the raw 8×16 @ 100 MS/s (10 ns/sample) waveforms, on the B4∧B6 coincidence sample
(n = 5,207 with valid times):

| Quantity | Value |
|---|---|
| B4–B6 residual σ₆₈ (ToF-subtracted) | **38.0 ns** (sampling-limited) |
| Clean in-window-peak subset (both argmax ∈ [3,11]) | 334 evts → σ₆₈ 42.9 ns (worse) |
| B4 peak-sample mode | 3 |
| B6 peak-sample modes | **0, 7, 15** (bimodal/multi-modal) |
| MC combined σ₆₈ (clusterB, for reference) | 0.089 ns |
| Canonical CL-002 "B6 σ₆₈ = 0.68 ns" | toy-digitizer MC (`mv4_timing_study.py`) |

The B4 and B6 pulse-times are essentially **uncorrelated event-by-event**: B6 peaks either
at sample 0 (rising edge outside the window), sample 7, or sample 15, while B4 spreads over
samples 3–15. The ~38 ns residual is dominated by the 10 ns sampling quantisation +
arbitrary trigger phase + the missing samples 16–17. **This is a measured data-format
limitation, not detector resolution.** A real-data timing resolution needs the median-gated
18-sample waveforms plus a template/optimal-filter pickoff. Figure:
`VIS-TIM-DATA_sampling_limited.png`.

## 3. VIS-PU-DATA — selected-pulse occupancy; absolute Rmax is withheld

The selected table contains 640,737 B-stave pulses grouped into 584,602 composite events.
It measures selected-pulse multiplicity only:

| Quantity | Value |
|---|---|
| Mean selected pulses / event | **1.096** |
| Fraction of events with ≥3 selected pulses | 2.55% |
| Measured arrival-rate exposure | **absent** |
| Accepted `mu_max` quality threshold | **unresolved** |
| Accepted absolute Rmax | **withheld** |

Rmax is withheld because this occupancy does not measure event-arrival rate, live exposure,
luminosity, an independently determined pile-up ceiling, or a detector-wide live window.
The value `mu_max = 0.38` is a legacy duty-factor convention, not an occupancy measurement.
Using it with the exact CL-011 estimand gives
`0.38 / 124.79018394263471 ns = 3.045111305987686 MHz`; this is a **model sensitivity
only**, not a data-derived rate. The former `0.38 / 130 ns = 2.923076923076923 MHz` is a
second convention-dependent sensitivity. CL-010 remains BLOCKED under `S-STAT-003`.
Figure: `VIS-PU-DATA_occupancy_rmax.png` is descriptive occupancy evidence only.

## 4. Data/MC closure summary

| Observable | DATA (this study) | MC | Verdict |
|---|---|---|---|
| ΔE-E corr(ΔE,E) | +0.221 | −0.533 | **TENSION** (B2-dominated data; material budget) |
| Combined timing σ₆₈ | ≥38 ns (format-limited) | 0.089 ns | **INFEASIBLE** on raw 16-sample |
| Absolute Rmax | withheld | model sensitivities only | **BLOCKED** (`S-STAT-003`) |

## 5. Claim status

| Claim | Status | Evidence |
|---|---|---|
| CL-001 (S00 pulses) | VALIDATED (+ raw provenance confirmed) | event-level exact match, 617,377/640,737 |
| CL-002..004 (timing σ₆₈) | GATED / data-format-limited | sampling-limited raw-format residual; no detector resolution |
| CL-005..006 (timing combination/covariance) | BLOCKED | source-bound covariance and uncertainty absent |
| CL-010 (Rmax) | **BLOCKED** (`S-STAT-003`) | occupancy is descriptive; rate exposure and accepted quality criterion absent |

Artifacts: `metrics.json`, `provenance.json`, `VIS-DE-001-DATA_deltaE_E_real.png`,
`VIS-TIM-DATA_sampling_limited.png`, `VIS-PU-DATA_occupancy_rmax.png`,
`s00_rebuild/` (rebuilt raw table, 709,003 rows, for audit).
