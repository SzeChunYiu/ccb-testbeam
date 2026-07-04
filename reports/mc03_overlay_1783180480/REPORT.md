# MC03 — truth-labelled pile-up overlays and the honest two-pulse benchmark (S24)

- **Date:** 2026-07-04
- **Inputs:** /projects/hep/fs10/shared/nnbar/billy/ccb-testbeam/reports/mc03_overlay_1783180480/overlays (manifest sha256 in `manifest.json`)
- **Scripts:** `scripts/mc03_build_overlay_sample.py`, `scripts/s24_two_pulse_honest_benchmark.py`
- **Digitizer card:** `/projects/hep/fs10/shared/nnbar/billy/ccb-testbeam/configs/mc_validation/digitizer_card.yaml` (sha256 `65e00bf470583639…`)

## 0. Question

What is the truth-labelled two-pulse failure rate versus pile-up rate for the
constrained template fit and a compact ML model, under a benchmark that fixes
every rigging channel of the retracted S11a comparison (review P8)? And what
live-time (tau_eff) does the tuned digitizer actually produce, measured
independently on digitized MC single pulses (replacing the retracted MV5
"MC tau_eff", review I2)?

## 1. How this benchmark differs from the rigged S11a (review P8)

| S11a defect | This benchmark |
|---|---|
| injection separation grid == fit hypothesis grid | injection dt CONTINUOUS (exponential, inverse-CDF); fit grid independent (t1 step 0.5 ns, t2 step 1 ns) |
| injected waveforms generated from the fit's own templates | injected waveforms are digitized PAIRS of real truth hit groups (multi-hit, per-hit transport smear, per-record noise); fit templates are the card kernel |
| failure definitions differ per method | ONE definition for both: missed detection OR |dt_rec − dt_true| > 15 ns (`failure_flags`, unit-tested for symmetry) |
| unmatched coverage / own accepted subsets | detection thresholds set by the SAME procedure (score quantile at 10% FPR on train-split negatives); risk-coverage swept for both; headline at the SAME 80% coverage; σ68 on the COMMON accepted subset |

Residual circularity, stated honestly: the fit template is the digitizer-card
kernel, and the same card drives the mc03 generator — the template shares the
kernel *family* with the truth pulses by construction. It is NOT built from
the injection sample (no fitting/averaging of injected waveforms), and the
injected pulses are multi-hit truth groups with transport smearing, so they
are genuinely off-template; the ML method never sees a template at all. A
data-side template mismatch stress (real-template fits) remains future work.

## 2. Sample

600000 records (0.5 MHz, 1.5 MHz, 3 MHz), each rate ~200000
records, 70% two-pulse overlaps + 30% single-pulse negatives.
Pulse 1 at the nominal 50 ns trigger offset; pulse 2 at 50 + dt,
dt ~ Exp(1/R) truncated to ≤ 130 ns, CONTINUOUS (419981 unique dt values
across rates — no grid). Constituents drawn independently from the truth
population (per-constituent noise-free amplitude > 1000 ADC; no ratio
restriction). Train/eval split by source-event parity (both constituents).

## 3. Failure rate at matched 80% coverage (truth-labelled, per rate) — MV5 open sub-item

| rate (MHz) | template fit — failure@80% [95% CI] | compact ML — failure@80% [95% CI] | n eval positives |
|---:|---|---|---:|
| 0.5 | 0.0000 [0.0000, 0.0000] | 0.0001 [0.0000, 0.0002] | 70100 |
| 1.5 | 0.0000 [0.0000, 0.0001] | 0.0002 [0.0001, 0.0004] | 70174 |
| 3 | 0.0000 [0.0000, 0.0001] | 0.0001 [0.0000, 0.0002] | 69582 |

Full curves: `risk_coverage_curves.csv`, figure panels a–c. Failure at full
coverage and threshold sensitivity: `result.json`.

## 4. dt resolution on the COMMON accepted subset

| rate (MHz) | σ68 trad (ns) | σ68 ML (ns) | bias trad (ns) | bias ML (ns) | n common |
|---:|---:|---:|---:|---:|---:|
| 0.5 | 0.646 | 0.893 | -0.037 | +0.015 | 49111 |
| 1.5 | 0.644 | 0.891 | -0.037 | +0.014 | 49211 |
| 3 | 0.639 | 0.897 | -0.027 | +0.014 | 48993 |

## 5. Detection sanity (eval split)

| rate (MHz) | method | ROC AUC | AP | realized FPR at θ (eval negatives) |
|---:|---|---:|---:|---:|
| 0.5 | ml | 0.9972 | 0.9990 | 0.1074 |
| 0.5 | trad | 0.9805 | 0.9929 | 0.1026 |
| 1.5 | ml | 0.9974 | 0.9991 | 0.1037 |
| 1.5 | trad | 0.9804 | 0.9929 | 0.1006 |
| 3 | ml | 0.9973 | 0.9990 | 0.1034 |
| 3 | trad | 0.9802 | 0.9928 | 0.0995 |

## 6. Independent MC tau_eff (S10b 10% tail-crossing estimator on digitized single pulses)

| stave | n selected | live10 (ns) [95% CI] | tail τ (ns) | empirical mean live10 (ns) |
|---|---:|---|---:|---:|
| B2 | 76650 | 141.35 [141.31, 141.40] | 65.64 | 127.73 |
| B4 | 48392 | 132.15 [132.11, 132.19] | 59.19 | 127.74 |
| B6 | 32273 | 127.72 [127.68, 127.76] | 56.38 | 127.36 |
| B8 | 19876 | 129.16 [129.12, 129.21] | 57.09 | 127.64 |

**Pooled (stave-composition weighted): 134.99 ns
[134.96, 135.01] vs data 124.79 ns
(Δ = +10.20 ns).** This is the FIRST honest MC live-time:
measured by the S10b estimator on digitized MC pulses with the per-stave
data-tuned tail decays — unlike the retracted MV5 number, which was a
hardcoded copy of the data value (review I2).

## 7. Caveats (honest limits of this closure)

- **Gain placeholder**: the card gain (297 ADC/MeV) is an UNKNOWN placeholder;
  all amplitudes are in arbitrary scale. Phase 2 attributes the MV3 spectrum
  discrepancy to the unsimulated two-arm coincidence trigger (not missing
  material) and prefers **gain ≈ 60** as the trigger-consistent estimate; the
  A>1000-equivalent selection boundary of this sample therefore corresponds
  to a different physical energy than in data.
- **Population weights**: stave occupancy and the amplitude spectrum are taken
  from the un-triggered MC truth population and inherit the MV3 spectrum
  discrepancy (χ²/ndf = 68269; Phase 2 root cause: unsimulated trigger).
- **Single-stave overlays only**: both constituents land on one stave/channel;
  no cross-stave topology, no A-arm.
- **Fixed trigger phase**: pulse 1 always at 50 ns (nominal mc02 convention);
  data pulses have phase jitter. The fit's t1 grid and the ML model both
  exploit this — absolute failure rates are optimistic on this axis.
- **Kernel-family circularity** (see §1): fit templates share the card kernel
  family with the generator; template-mismatch stress not included.
- **tau_eff comparison**: MC single pulses are clean by construction; the data
  124.79 ns was measured on A>1000 data pulses including real pathologies.

## 8. Reproduce

```bash
python scripts/mc03_build_overlay_sample.py --mc <truth.root> --out <overlays>
python scripts/s24_two_pulse_honest_benchmark.py --overlay-dir <overlays> --out <this dir>
```

Runtime 150 s. Artifacts: `result.json`, `manifest.json`,
`risk_coverage_curves.csv`, `failure_at_coverage.csv`, `common_subset_sigma68.csv`,
`detection_metrics.csv`, `tau_eff_by_stave.csv`, `predictions_rate*.csv.gz`,
`fig_mc03_benchmark.(png|svg|pdf)`.
