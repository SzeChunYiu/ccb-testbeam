# Non-ML raw-timing five-event comparison contract

## Purpose

Provide one transparent classical timing pipeline that starts from immutable `h101/HRDv` rows and exposes every numerical step required to compare two implementations event-by-event. Exactly five events are selected for comparison, but **five events are never used as the timing-resolution estimate**. Widths come from the complete selected pair population.

## Current source/status boundary

The located LUNARC beam product is the 8-channel × 16-sample (`128` words/event, 10 ns/sample) schema documented by `reports/studies/data_side/REPORT.md` and `configs/data_side_s00_rebuild.yaml`. The current data-side study measures a sampling/window-limited B4–B6 timing diagnostic (~38 ns under its legacy CFD edge policy) and explicitly withholds detector/single-stave timing resolution. The 16↔18 waveform lineage remains quarantined by #993.

Therefore the script/result contract must write:

```text
pair_residual_diagnostic = true
five_event_resolution_authorized = false
single_stave_resolution_authorized = false
absolute_detector_resolution_authorized = false
```

## Raw-to-residual chain

1. Read each `HRDv` row separately; validate exactly `n_channels * samples_per_channel` scalar words **before reshape**.
2. Reshape channel-major only after the event passes the frame-length gate.
3. Use B-stack channels `{B2:0, B4:2, B6:4, B8:6}` unless a source-bound map supersedes them.
4. Baseline = median(samples 0,1,2,3); record baseline RMS and slope.
5. Record amplitude, area, and peak sample before timing.
6. Require the raw-source amplitude cut (`>1000 ADC`) on every stave entering a pair.
7. Compute a fixed-threshold leading edge and CFD fractions 0.10–0.60.
8. Default CFD is 0.20 with linear interpolation between the two bracketing samples.
9. Build pairs only with composite `(run,eventno,stave)` identities; reject duplicates.
10. Save both raw pair difference and constant-TOF-shifted residual. Verify numerically that a constant TOF changes the median but not sigma68/std for an unchanged event population.
11. Report N, mean, median, Q16/Q84, sigma68, sample std, RMS, >2/>5/>10 ns tails, descriptive Gaussian-core fit/chi2-ndf, and whole-run bootstrap interval.
12. Plot timestamp correlation, peak-sample lattice, full/log residual, CFD fraction scan, residual-vs-amplitude ratio, and run stability.
13. Fit any analytic amplitude-timewalk correction on training runs only and evaluate it on untouched test runs.
14. If B4/B6/B8 deconvolution is attempted, enforce one **common complete three-stave event population** and use pair variances (not sigma68²). Keep the result conditional/unauthorized until covariance and closure are validated.

## Two CFD policies must remain explicit

### `strict` (preferred)

Match the canonical censoring principle in `scripts/digital_cfd.py`:

- waveform already above CFD threshold at sample 0 → `NO_CROSSING_IN_WINDOW`, timestamp `NaN`;
- non-positive interpolation bracket → invalid/NaN;
- no fabricated zero timestamps.

### `legacy_data_side` (comparison-only)

Reproduce `scripts/studies/data_side_real_beam.py` exactly where needed:

- first sample already above threshold → timestamp `0 ns`;
- non-positive denominator → fractional phase forced to zero.

This mode exists to locate differences with older work; it is not the preferred physics policy.

## Deterministic five-event selection

From the complete valid B4–B6 population, rank unique `(run,eventno)` by

```text
SHA256(comparison_seed + ':' + run + ':' + eventno)
```

and keep the first five (default seed `20260907`). This is deterministic and independent of ROOT iteration ordering.

For each of the five events export:

- raw ADC value for every sample;
- baseline and corrected ADC value;
- amplitude, area, peak sample;
- CFD fraction and threshold;
- bracket-low/high sample indices and ADC values;
- fractional phase and local slope;
- CFD timestamp;
- B4–B6 raw difference and TOF-corrected residual;
- annotated waveform figure.

The comparison procedure is intentionally ordered:

```text
run,eventno
→ raw samples
→ baseline
→ corrected samples
→ amplitude/peak
→ threshold
→ bracket
→ phase/slope
→ timestamp
→ pair residual
→ full-sample width
```

The first mismatch identifies the implementation divergence.

## Recommended commands

Source-valid Sample-II diagnostic:

```bash
python ccb_nonml_timing_5event.py \
  --raw-dir /projects/hep/fs10/shared/nnbar/ccb_data/hrd/root \
  --runs 58-63,65 \
  --selection-mode raw \
  --cfd-policy strict \
  --cfd-fraction 0.20 \
  --spacing-cm 4.0 \
  --out reports/nonml_timing_sampleII_strict
```

Current data-side compatibility check:

```bash
python ccb_nonml_timing_5event.py \
  --raw-dir /projects/hep/fs10/shared/nnbar/ccb_data/hrd/root \
  --runs canonical \
  --selection-mode canonical \
  --canonical-table reports/1781028640.1299.266407ae/s00_selected_b_pulses.csv.gz \
  --cfd-policy legacy_data_side \
  --cfd-fraction 0.20 \
  --spacing-cm 0.78 \
  --out reports/nonml_timing_dataside_reproduction
```

## Required outputs

```text
input_manifest.json
pulse_timing_rows.csv.gz
B4_B6_pair_events.csv.gz
B4_B8_pair_events.csv.gz
B6_B8_pair_events.csv.gz
comparison_event_ids.csv
comparison_event_pair_summary.csv
comparison_event_waveform_samples.csv
comparison_event_*.png
cfd_fraction_scan.csv
cfd_fraction_scan.png
run_stability.csv
run_stability.png
heldout_timewalk_events.csv (when available)
timing_summary.json
README_COMPARISON.md
```

## Validation already performed on the standalone implementation

Pure-numpy self-tests cover:

- known-answer CFD interpolation;
- strict left-censor handling;
- legacy `t=0` compatibility handling;
- sigma68/std translation invariance under constant TOF;
- deterministic five-event selection independent of row order;
- known-answer three-stave variance decomposition;
- baseline subtraction.

The script compiles with Python and its self-test passes. Real ROOT execution still has to be run on the data host because the raw files are not available inside the chat runtime.
