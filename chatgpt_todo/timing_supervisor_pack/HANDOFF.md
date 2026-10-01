# Timing-study handoff and atomic work queue

## Current scientific state

The Issue #1320 sub-nanosecond result is **not an intrinsic stave resolution**. It is a B4--B6
pair-core diagnostic whose source map is now marked
`RETRACTED_20260816_TRUNCATED_STAGING_DESYNC`. The result is also strongly non-Gaussian and one
pair cannot identify two stave resolutions plus covariance. The correct fail-closed state is:

```text
pair_residual_authorized = false for physical detector performance
single_stave_resolution_authorized = false
publication_headline_authorized = false
```

## Session protocol

Every follow-on AI or human session must begin by reading, in order:

1. `configs/channel_polarity_v2.json` and its retraction object;
2. `publication/chapters/06_timing.tex`;
3. `reports/issue_1320_timing/result.json`;
4. `docs/validation/real_data_cfd_single_stave_inference_audit.md`;
5. this folder's `TIMING_STUDY_STEP_BY_STEP.md` and `diagnostic_plot_manifest.csv`.

No session may quote a detector or stave resolution before recording the pass/fail state of all
manifest rows marked required for resolution.

## Expert review roles

- **Detector-timing physicist:** owns pulse identity, timewalk, TOF, and the physical definition of
  the timestamp.
- **DAQ/waveform specialist:** owns frame length, channel order, polarity, sample timebase, trigger
  phase, and boundary/truncation diagnostics.
- **Statistician:** owns estimand choice, train/test separation, block bootstrap, non-Gaussian tails,
  covariance, deconvolution, and uncertainty coverage.
- **Reconstruction/software reviewer:** owns unique event keys, cut flow, unit tests, provenance,
  fail-closed guards, and exact reproduction.

A finding is promoted only after all four roles record whether it changes the physical conclusion.

## Atomic queue

### T0 — fail closed on retracted calibration objects

**Change:** make `scripts/issue_1320_timing_residual.py` abort when a consumed map status contains
`RETRACTED`, unless an explicit audit-only flag is provided. The audit-only mode must watermark all
outputs `NON_PHYSICAL_RETRACTED_INPUT`.

**Tests:** active map passes; retracted map raises; missing status raises; audit-only output cannot set
`individual_stave_authorized=true`.

### T1 — raw frame contract on the exact laptop source

**Change:** read the header and event vectors from the immutable 144-word source. Plot vector-length
counts and verify the exact `(8,18)` reshape. Bind file hashes and event counts.

**Acceptance:** one stable frame length; no truncation; event-key equality across any converted
products; no inferred shape from a staging filename.

### T2 — channel/pulse identity atlas

**Change:** produce WAVEFORM-001 through PULSE-ID-001 for all eight channels and every run family.

**Acceptance:** B4/B6/B8 must show localized detector-pulse morphology under the correct frame. If
only B2/B2-duplicate carries pulses, stop: this dataset cannot measure downstream pair timing.

### T3 — event-level timing table

**Change:** write one row per unique `(run,event,stave)` with raw waveform hash/index, baseline,
baseline RMS/slope, global and selected component properties, CFD brackets, slope, phase, amplitude,
and failure reason.

**Acceptance:** no duplicate keys; cut-flow totals reconcile; component amplitude, not an unrelated
global peak, controls timing acceptance.

### T4 — held-out pair diagnostics

**Change:** pre-register run splits. Choose component selector, fraction, amplitude/timewalk model on
training/validation runs only. Freeze and evaluate on untouched test runs. Generate manifest plots
8--17 and report sigma68, RMS, tail fractions, fit quality, median, and block-bootstrap intervals.

**Acceptance:** the complete test-set vector is immutable after model selection; no IID event bootstrap
when run/block dependence is present.

### T5 — individual stave inference

**Change:** obtain at least three connected physical staves or an independently calibrated reference.
Fit a covariance-aware model and validate it by parameter injection/recovery.

**Acceptance:** non-negative parameters, pair closure on held-out data, coverage closure on simulation,
and a machine-readable `single_stave_inference.authorized` gate. Until then, publish pair residuals
only.

### T6 — manuscript and wiki correction

**Change:** replace the current v2-polarity description in `publication/chapters/06_timing.tex` with
an explicit retraction/provenance paragraph and link the final validated producer once T1--T5 close.
Expand `docs/04_timing_calibration.md`, `docs/05_timing_resolution.md`, and the wiki with the diagnostic
sequence.

**Acceptance:** no 0.096/0.138/0.146 ns beam-data performance number appears without the words
`RETRACTED ANALYSIS ARTIFACT`; no single-stave number appears without its covariance model and
closure evidence.
