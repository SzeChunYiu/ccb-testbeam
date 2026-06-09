# Study report: S02 - Timing pickoff, CFD vs OF vs template

- **Study ID:** S02
- **Ticket:** 1780997954.15157.07ef03cf
- **Author (worker label):** testbeam-laptop-3
- **Date:** 2026-06-09
- **Depends on:** S00, S01b selected-table manifest
- **Input checksum(s):** see `manifest.json`; aggregate raw ROOT sha256 digest `b5547ac7f2452361c1fc85b20ae7107c8fb6df54af22b152c2ef8e983fe38ee4`
- **Git commit:** recorded in `manifest.json`
- **Config:** `configs/s02_timing_pickoff.yaml`

## 0. Question

Which raw-waveform timing pickoff gives the narrowest same-particle downstream timing residual on reproduced S00 pulses, and does a run-split ML residual corrector beat a strong traditional pickoff on the same held-out data?

Atomic steps:

- Reproduce the S00 raw-ROOT selected-pulse counts exactly before timing work.
- Build downstream B4/B6/B8 three-stave Sample-II events with all three staves above 1000 ADC.
- Pre-register and scan fixed traditional candidates: leading edge at 500 ADC, CFD fractions 10-50%, derivative optimal-filter windows, and a full template-phase grid fit.
- Evaluate both 2 cm and 4 cm spacing corrections using `0.078 ns/cm`.
- Train only on runs 58-63 and evaluate only on held-out run 65.

## 1. Reproduction

The S00 count gate was rerun from raw ROOT, not from processed tables. Exact reproduction passed:

| Quantity | Report value | Reproduced | Delta | Tolerance | Pass? |
|---|---:|---:|---:|---:|---|
| total selected B-stave pulses | 640737 | 640737 | 0 | 0 | yes |
| sample_ii_analysis selected_pulses | 125096 | 125096 | 0 | 0 | yes |
| sample_ii_analysis B2 | 88213 | 88213 | 0 | 0 | yes |
| sample_ii_analysis B4 | 21229 | 21229 | 0 | 0 | yes |
| sample_ii_analysis B6 | 11148 | 11148 | 0 | 0 | yes |
| sample_ii_analysis B8 | 4506 | 4506 | 0 | 0 | yes |

The timing benchmark uses the stricter downstream all-hit subset. Held-out run 65 has 66 B4/B6/B8 events, hence 198 pairwise residuals.

## 2. Traditional Method

All methods use baseline-subtracted raw `HRDv` waveforms, median baseline samples `[0,1,2,3]`, amplitude `max(waveform)`, and the S00 `A > 1000 ADC` selection. The primary metric is held-out pairwise robust width, `sigma68 = (q84 - q16) / 2`, after subtracting the geometry TOF correction.

Best traditional method by train-run sigma68 at 2 cm spacing was `template_phase`. Held-out results:

| Method | Spacing | Held-out sigma68 (ns) | 95% bootstrap CI | Full RMS (ns) | Core sigma (ns) | chi2/ndf |
|---|---:|---:|---:|---:|---:|---:|
| template_phase | 2 cm | 2.889 | [2.639, 3.205] | 2.577 | 0.443 | 3.214 |
| CFD20 reference | 2 cm | 2.993 | [2.615, 3.351] | 2.743 | 1.080 | 0.915 |

The 4 cm correction changed medians/tails more than sigma68; it did not change the best-method conclusion. The Gaussian core fit is not a sufficient resolution summary here: for `template_phase`, core sigma is much smaller than sigma68, so the distribution has structure/tails that matter.

The variance-decomposition cross-check on held-out run 65 gives approximate single-stave sigma68:

| Method | B4 | B6 | B8 |
|---|---:|---:|---:|
| template_phase | 1.078 ns | 0.402 ns | 0.633 ns |
| ML ridge | 1.355 ns | 0.856 ns | 0.784 ns |

This decomposition is unstable with only 66 events and should not be treated as a final Table-19 reproduction.

## 3. ML Method

The ML method is a Ridge residual corrector on CFD20, not a truth-level timing model. For each train-run pulse, the target is the stave's CFD20 residual relative to the mean of the other two downstream staves in the same event after geometry correction. Features are the 18 amplitude-normalized waveform samples, log amplitude, peak sample, area/amplitude, and stave one-hot encoding. No held-out run labels are used for fitting.

Run-grouped CV over runs 58-63 selected `alpha=100`:

| Alpha | Mean CV sigma68 (ns) |
|---:|---:|
| 0.01 | 2.041 |
| 0.10 | 2.041 |
| 1.00 | 2.039 |
| 10.00 | 2.027 |
| 100.00 | 1.976 |

Held-out residual calibration is imperfect at the extremes: the largest positive predicted residual bin averages `4.56 ns` predicted vs `2.57 ns` observed. This is a warning that the Ridge output should be treated as a correction score, not a calibrated per-pulse timing truth.

## 4. Head-to-head Benchmark

Same held-out run, same B4/B6/B8 events, same pairwise sigma68 metric:

| Method | Metric | Value +/- CI | Notes |
|---|---|---:|---|
| template_phase | heldout pairwise sigma68 | 2.889 ns [2.639, 3.205] | best fixed traditional scan on train runs |
| CFD20 | heldout pairwise sigma68 | 2.993 ns [2.615, 3.351] | documented reference |
| ML ridge | heldout pairwise sigma68 | 1.846 ns [1.521, 2.014] | run-split residual correction on CFD20 |

Verdict: ML beats the best traditional scan by `1.043 ns` on the pre-registered held-out pairwise metric. The result is promising but not adoption-ready because the held-out set is small and the target is self-supervised from inter-stave consistency rather than an external timing truth.

## 5. Falsification

- **Pre-registration:** before inspecting timing results, the metric was fixed as held-out Sample-II B4/B6/B8 pairwise sigma68 on run 65, with full RMS and core-fit chi2/ndf also reported. The candidate scan was fixed in `configs/s02_timing_pickoff.yaml`.
- **Falsification test:** ML would fail the S02 claim if its held-out sigma68 CI overlapped or exceeded the best traditional CI, or if the S00 raw-count gate did not reproduce exactly.
- **Result:** the ML CI `[1.521, 2.014] ns` is below the best traditional CI `[2.639, 3.205] ns`. No discovery p-value is claimed; the manifest records 27 fixed candidate/hyperparameter tries.

## 6. Threats to Validity

- **Benchmark/selection:** the traditional baseline includes CFD scan, leading edge, OF windows, and template-phase fit, but the template is global per stave. It is not yet amplitude-binned or timewalk-closed, so S02b should strengthen it before final adoption.
- **Data leakage:** split is by run. The ML target is derived from the other staves' CFD20 times, so it can learn inter-stave consistency but not external truth. Features exclude event-level residuals and other-stave timings.
- **Metric misuse:** sigma68, full RMS, tail fraction, Gaussian core sigma, and chi2/ndf are all written. Core sigma alone is misleading for `template_phase`.
- **Post-hoc selection:** method/hyperparameter candidates were fixed in the config before the run; the report does not tune cuts after seeing held-out results.

## 7. Provenance Manifest

`manifest.json` contains input ROOT sha256s, config path, command, random seed, runtime, output hashes, and the git commit reported by the script. Every table/figure in this report is generated by:

```bash
python scripts/s02_timing_pickoff.py --config configs/s02_timing_pickoff.yaml
```

## 8. Findings & Next Steps

The immediate finding is that S02 timing pickoff is not yet limited by CFD fraction choice alone: a simple run-split waveform residual corrector removes a large part of the held-out pairwise spread. The scientific hypothesis is that amplitude/shape-dependent timewalk and residual electronics response are still present in the raw CFD/template times, and waveform shape carries enough information to correct some of it without event-level leakage.

This agrees with the fleet summary that S00 is closed and downstream timing studies should now attack timewalk and full residual distributions. It does not conflict with existing merged reports because no S02 result existed yet.

Queued follow-ups:

- **S02b: template alignment with amplitude-binned templates and timewalk closure.** Question: does a stronger conventional template/timewalk method erase the ML gain? Expected information gain: separates a real ML advantage from a weak global-template baseline.
- **S03a: run-held-out analytic timewalk correction using S02 best pickoff.** Question: can an explicit analytic amplitude/shape correction reproduce the Ridge residual gain with interpretable parameters? Expected information gain: establishes whether the ML correction is physics-like timewalk or an opaque run-dependent artifact.

## 9. Reproducibility

Artifacts written:

- `reproduction_match_table.csv`
- `traditional_scan_metrics.csv`
- `head_to_head_benchmark.csv`
- `ml_ridge_cv.csv`
- `ml_residual_calibration.csv`
- `single_stave_variance_decomposition.csv`
- `fig_traditional_scan.png`
- `fig_heldout_residuals.png`
- `fig_ml_residual_calibration.png`
- `result.json`
- `manifest.json`
