# S16f: Sample-I high-lowering residual-tail mechanism

- **Ticket:** 1781015168.1090.5b553d2a
- **Author:** testbeam-laptop-1
- **Date:** 2026-06-09
- **Input checksum(s):** `input_sha256.csv`
- **Git commit:** `583b53564f65443bbfdaa859a7e1ecc5ebff4bb3`
- **Config:** `s16f_1781015168_1090_5b553d2a.json`

## Question

Why do Sample-I B4/B6/B8 pairs in the train-selected high adaptive-lowering bin have elevated held-out residual-tail fraction even though lowering-based corrections barely improve sigma68?

## Raw-ROOT Reproduction First

The script starts from `h101/HRDv` raw ROOT, using B2/B4/B6/B8 even channels, median samples 0-3, and `A > 1000 ADC`.

| Quantity | Report value | Reproduced | Delta | Pass? |
|---|---:|---:|---:|---|
| total selected B-stave pulses | 640737 | 640737 | 0 | yes |
| adaptive post-correction violations | 0 | 0 | 0 | yes |
| sample_i_analysis selected_pulses | 252266 | 252266 | 0 | yes |
| sample_i_analysis B2 | 241422 | 241422 | 0 | yes |
| sample_i_analysis B4 | 6451 | 6451 | 0 | yes |
| sample_i_analysis B6 | 3094 | 3094 | 0 | yes |
| sample_i_analysis B8 | 1299 | 1299 | 0 | yes |

The S16d high-vs-low tail number is also reproduced before mechanism work:

| Quantity | Prior value | Reproduced | Delta | Pass? |
|---|---:|---:|---:|---|
| s16d high_lowering_tail_fraction | 0.130435 | 0.130435 | 0 | yes |
| s16d low_lowering_tail_fraction | 0.0123796 | 0.0123796 | 0 | yes |
| s16d heldout_events | 250 | 250 | 0 | yes |
| s16d heldout_pair_residuals | 750 | 750 | 0 | yes |

Timing subset: train runs [44, 45, 46, 47, 48, 49, 50, 51, 52, 53] contain `400` events / `1200` pair residuals; held-out runs [54, 55, 56, 57] contain `250` events / `750` pair residuals.

## Methods

The target is the S02 `CFD20` pair residual after the 2 cm TOF correction, pair-centered and tailed at `|residual| > 5 ns`. The high-lowering threshold is selected on train runs only.

Traditional method: Ridge residual correction using lowering, amplitude, peak-sample, area/amp, and pre/late anomaly terms plus pair identity.

ML method: fixed random-forest residual corrector plus a random-forest tail classifier for mechanism ranking. Splits are by run. Features exclude run, event id, labels, residuals, and other-stave timing labels.

## Held-out Benchmark

Bootstrap CIs resample held-out runs, then events within each sampled run.

| Method | sigma68 ns [95% CI] | tail frac | full RMS ns | n pairs |
|---|---:|---:|---:|---:|
| raw_cfd20 | 3.110 [2.955, 3.302] | 0.065 [0.044, 0.095] | 5.656 | 750 |
| traditional_ridge_lowering | 3.116 [2.934, 3.326] | 0.084 [0.052, 0.110] | 5.320 | 750 |
| ml_rf_lowering | 2.760 [2.593, 2.937] | 0.052 [0.032, 0.074] | 5.021 | 750 |
| ml_shuffled_target_control | 3.105 [2.963, 3.322] | 0.071 [0.050, 0.097] | 5.708 | 750 |

Train-selected high-lowering threshold: `817.67 ADC`. Held-out high-bin tail fraction `0.130` [0.000, 0.378], low-bin tail fraction `0.012` [0.000, 0.026].

## Mechanism Diagnostics

| Bin | n pairs | tail fraction [95% CI] | sigma68 ns | median peak sample | median area/amp | median pretrigger abs ADC | median late abs ADC | median tail-area frac |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| low | 727 | 0.012 [0.000, 0.026] | 1.608 | 10.0 | 7.04 | 18.0 | 2336.5 | 0.513 |
| high | 23 | 0.130 [0.000, 0.378] | 2.185 | 4.0 | 1.21 | 1690.5 | 1290.5 | 0.512 |

High-bin tails concentrate in run 56 B4-B8 (tail 0.400, n=5). RF tail classifier held-out AUC is `0.907` with shuffled-target AUC `0.611`; top RF features are `delta_positive_area_over_amp, delta_width20_samples, delta_area_over_amp, delta_late_abs_adc, abs_delta_lowering_adc`.

## Leakage Checks

| Check | Value | Pass? |
|---|---:|---|
| split_by_run_heldout_runs_match_config | 54,55,56,57 | yes |
| ml_features_exclude_run_event_and_residual |  | yes |
| shuffled_target_not_better_than_actual_ml | 0.34514670951594484 | yes |
| intentional_oracle_is_obviously_leaky | 2.568940518633896 | yes |
| row_cv_not_much_better_than_run_cv | 0.011936957676284665 | yes |
| actual_ml_improvement_under_raw_one_ns | 0.35029063309184894 | yes |
| heldout_predictions_finite | 750 | yes |
| tail_classifier_shuffled_auc_not_too_high | 0.6106594399277325 | yes |

## Verdict

The elevated high-lowering tail rate is real on held-out runs but still behaves more like a proxy than a fixable pedestal-lowering error. Traditional correction improves sigma68 by -0.006 ns and RF correction by 0.350 ns, while the high-minus-low tail gap is 0.118. High-bin pairs have pretrigger medians 93.92x low-bin, late-window medians 0.55x low-bin, and tail-area-fraction medians 1.00x low-bin; the mechanism is most consistent with pileup/shape pathologies or residual timewalk correlated with lowering, not lowering propagation alone.

## Reproducibility

```bash
/home/billy/anaconda3/bin/python scripts/s16f_1781015168_1090_5b553d2a_tail_mechanism.py --config configs/s16f_1781015168_1090_5b553d2a.json --out-dir reports/1781015168.1090.5b553d2a
```

Artifacts: `reproduction_match_table.csv`, `reproduction_target_match_table.csv`, `pair_residuals_train.csv`, `pair_residuals_heldout.csv`, `mechanism_high_low_summary.csv`, `mechanism_by_run_pair.csv`, `mechanism_by_stave.csv`, `ml_tail_classifier_summary.csv`, `leakage_checks.csv`, `input_sha256.csv`, `result.json`, and `manifest.json`.
