# Data-Side Analysis on Real Beam Data (LUNARC ccb_data)

**Status:** MEASURED_DATA + GATED (waveform lineage/timing) + BLOCKED (absolute Rmax).
**Branch:** `studies/data-side-analysis` · **Driver:** `scripts/studies/data_side_real_beam.py`
**Raw source:** `/projects/hep/fs10/shared/nnbar/ccb_data/hrd/root/` (`hrdb_run_*.root`, runs 12–65; 748 MB)
**Inputs:** canonical S00 table `reports/1781028640.1299.266407ae/s00_selected_b_pulses.csv.gz` (640,737 rows) + raw HRDv waveforms.

> This study was previously **BLOCKED_DATA** ("raw `hrdb_run_*.root` not staged").
> The raw data was located on 2026-07-25 at the path above and analysed directly. Every
> number below is measured from real beam waveforms; caveats are stated explicitly.

---

## 0. Data provenance — located raw data overlaps canonical S00, but 16↔18 lineage is gated

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

**Interpretation:** the located ccb_data has strong event-level correspondence with the
canonical S00 product: baseline+amplitude+peak match exactly for B2 over 578,019 overlapping
pulses. These feature-level agreements are consistent with a product that shares the first
16 samples and differs in a two-sample tail, but they do **not** prove that mechanism. The
exact 8×16↔8×18 producer lineage, channel/sample mapping, and disputed two-sample origin remain
open under #993. Competing possibilities include a separate acquisition/conversion product,
padding/reconstruction, or another transformation that preserves early-sample features. The
canonical-only population is 23,360 records, so the product/tail distinction can matter
for selection or downstream observables.

The additional s00c "median-first-four" quality gate (laptop-side, on `data/sorted-b`, not
staged) reduces the raw 706,373 → 640,737. The downstream physics below uses the canonical
640,737 table as its fixed input. **CL-001 is VALIDATED (2026-08-16)**: the corrected 144-word
staging reproduces all 17 documented quantities at delta=0/tolerance=0 (total 640,737), and the
new cell-exact `sorted_waveform_identity` gate verifies `baseline + polarity*sample == raw HRDv`
word-for-word with EVT numbers aligned 1:1 on every configured run — the detector that would
have caught the #952 truncation desync. The width/closure/polarity gates #952/#953/#954 and the
lineage gate #993 are all CLOSED; the authorising manifest
(`s00_rebuild/manifest.json`, `claim_status: canonical-authorising`) records all four gates PASS.

**Provenance correction:** the tracked `provenance.json` currently reports
`raw_input_sha256_count: 33` but serializes only three digest records because the historical
producer wrote `digests[:3]`. It is therefore not a complete 33-file digest manifest. The
producer repair is tracked under #993; the real artifact must be regenerated on the data host
before full raw-input provenance is claimed.

## 1. VIS-DE-001-DATA — Two-channel B2–B4 amplitude correlation (NOT ΔE–E) **[RELABELLED per #956]**

**FIXED (2026-08-14):** This section was previously labeled "ΔE-E on real beam data" but
describes only a two-channel B2-vs-B4 amplitude correlation. The supervisor contract (#618)
defines the correct ΔE–E observable as `ΔE = A(B2)`, `E = A(B4)+A(B6)+A(B8)`. The
B2-vs-B4 plot below is a **diagnostic two-channel correlation**, not the authorising ΔE–E
observable. See issue #956 for the corrected producer.

ADC B2–B4 correlation (X = B4 amplitude, Y = B2 amplitude) for events with both staves
selected, with **composite-key (run,eventno) validation: 0 duplicates** (the corruption
mode that affects eventno-only joins does not arise here — each (run,eventno,stave) is unique).

| Quantity | Value (B2–B4 correlation) |
|---|---|
| N events (B2∧B4) | **33,966** |
| corr(A(B2), A(B4)) | **+0.221** |
| A(B2) median | 3,385 ADC |
| A(B4) median | 2,963 ADC |

**Interpretation:** This two-channel correlation shows moderate positive correlation
(+0.22) between the B2 and B4 ADC amplitudes. This is **not** a ΔE–E particle identification
observable. The authorising ΔE–E observable (`ΔE = A(B2)`, `E = A(B4)+A(B6)+A(B8)`)
must be computed from the corrected producer (#956) which includes B6 and B8 contributions.
The sign reversal versus MC reported below refers to this historical two-channel product
and does not represent a comparison of the corrected ΔE–E observables.

| For reference (historical MC comparison) | DATA | MC (clusterA) |
|---|---|---|
| corr(ΔE, E) [old definition] | +0.221 | −0.533 |

The historical comparison used `E = B2 amplitude, ΔE = B4 amplitude` (a two-channel product)
and showed a sign reversal versus MC. This comparison is **not authorising** for the corrected
ΔE–E observable defined in #618. Figure: `VIS-DE-001-DATA_deltaE_E_real.png` (label retained
for provenance; represents B2–B4 correlation, not ΔE–E).

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
arbitrary trigger phase + the unavailable/disputed samples 16–17. **This is a measured
data-format limitation, not detector resolution.** A real-data timing resolution requires
an authorising waveform product with resolved provenance plus a validated timing pickoff.
Figure: `VIS-TIM-DATA_sampling_limited.png`.

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
| B2–B4 corr(A(B2), A(B4)) | +0.221 | −0.533 (old MC) | **Two-channel diagnostic only**; corrected ΔE–E pending #956 |
| Combined timing σ₆₈ | ≥38 ns (format-limited) | 0.089 ns | **INFEASIBLE** on raw 16-sample |
| Absolute Rmax | withheld | model sensitivities only | **BLOCKED** (`S-STAT-003`) |

## 5. Claim status

| Claim | Status | Evidence |
|---|---|---|
| CL-001 (S00 pulses) | **VALIDATED** (2026-08-16) | deterministic 640,737 reproduced at delta=0 on the corrected 144-word staging; cell-exact sorted-waveform identity gate PASS; gates #952/#953/#954/#993 closed; manifest `canonical-authorising` |
| CL-002..004 (timing σ₆₈) | GATED / data-format-limited | sampling-limited raw-format residual; no detector resolution |
| CL-005..006 (timing combination/covariance) | BLOCKED | source-bound covariance and uncertainty absent |
| CL-010 (Rmax) | **BLOCKED** (`S-STAT-003`) | occupancy is descriptive; rate exposure and accepted quality criterion absent |
| CL-030 (ΔE–E DATA observable) | **GATED** (2026-08-14) | Relabelled B2–B4 as two-channel diagnostic; corrected ΔE–E producer #956 P0-1 fixes applied; pending MC provenance #1311 |
| CL-031 (ΔE–E MC observable) | **GATED** (2026-08-14) | P0-1 producer fixes applied; disjoint MC samples; entrance-primary species; pending MC provenance #1311 |
| CL-032 (ΔE–E figures) | **GATED** (2026-08-14) | Pending #1321 final figure package after corrected DATA + MC producers |
| CL-033 (ΔE–E MC material-budget attribution) | **GATED** (2026-08-14) | Pending corrected observable + nuisance scans + MC provenance |

Artifacts: `metrics.json`, `provenance.json`, `VIS-DE-001-DATA_deltaE_E_real.png`
(two-channel B2–B4 correlation, NOT ΔE–E),
`VIS-TIM-DATA_sampling_limited.png`, `VIS-PU-DATA_occupancy_rmax.png`,
`s00_rebuild/` (corrected-staging rebuilt raw table, 640,737 rows, all gates PASS,
`claim_status: canonical-authorising`).
