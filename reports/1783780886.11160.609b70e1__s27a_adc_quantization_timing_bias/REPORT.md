# Study report: S27a - ADC quantization pulse-shape timing bias map

- **Ticket:** `1783780886.11160.609b70e1`
- **Worker:** `testbeam-laptop-3`
- **Date:** 2026-07-12
- **Input:** raw B-stack ROOT files under `data/root/root`
- **Config:** `configs/s27a_1783780886_11160_609b70e1_adc_quantization_timing.yaml`
- **Git commit at run time:** `16a1d3947329bdaa1ff4e87073562c67f3c62841`

## Abstract

S27a tests whether ADC quantization structure in short B-stack waveforms is a measurable timing-bias mechanism. The raw selected-pulse count is first reproduced from ROOT. A training-run-selected traditional timing pickoff is then compared with ridge, gradient-boosted trees, MLP, 1D-CNN, and a compact quantization-aware attention model. Models are trained only on runs [58, 59, 60, 61, 62] and evaluated on held-out runs [63, 65] with paired event bootstrap confidence intervals. The winner recorded in `result.json` is `ridge`.

## 1. Raw ROOT Reproduction

The reproduction gate rebuilds the S00 selected-pulse count directly from the `HRDv` branch in every configured raw B-stack ROOT file. For each event, channels B2/B4/B6/B8 are baseline-subtracted with the median of samples 0-3 and selected when the channel maximum exceeds 1000 ADC.

| quantity                           |   report_value |   reproduced |   delta |   tolerance | pass   |
|:-----------------------------------|---------------:|-------------:|--------:|------------:|:-------|
| total selected B-stave pulses      |         640737 |       640737 |       0 |           0 | True   |
| sample_ii_analysis selected_pulses |         125096 |       125096 |       0 |           0 | True   |
| sample_ii_analysis B2              |          88213 |        88213 |       0 |           0 | True   |
| sample_ii_analysis B4              |          21229 |        21229 |       0 |           0 | True   |
| sample_ii_analysis B6              |          11148 |        11148 |       0 |           0 | True   |
| sample_ii_analysis B8              |           4506 |         4506 |       0 |           0 | True   |

The exact `640737` count and Sample-II stave counts are recovered before any modeling, so the benchmark is tied to the same raw-data surface as the established timing reports.

## 2. Timing Observable and Estimators

For downstream stave `i` in event `e`, each raw pickoff is corrected for nominal flight time:

`t'_{i,e,m} = t_{i,e,m} - x_i v^{-1}`, with `v^{-1}=0.078 ns cm^{-1}`.

The pairwise residual set for method `m` is

`R_m = {t'_{a,e,m} - t'_{b,e,m}: (a,b) in {(B4,B6),(B4,B8),(B6,B8)}}`.

The primary width is the robust central scale

`sigma68(R_m) = (Q_84(R_m) - Q_16(R_m))/2`.

ML models predict a residual correction to the training-selected traditional base method. The supervised target for pulse `i` is

`y_{i,e}=t'_{i,e,base} - 1/2 sum_{j != i} t'_{j,e,base}`.

The corrected prediction is `t_hat = t_base - f(x_i)`. No model receives run id, event id, event order, other-stave times, or any held-out residual.

### Traditional Baseline

The strong traditional candidate is selected on training runs only from leading edge, CFD fractions, template phase, and optimal-filter windows. The selected baseline is `template_phase`. Held-out traditional diagnostics are:

| method         |   sigma68_ns |   full_rms_ns |   tail_frac_abs_gt5ns |   core_sigma_ns |   chi2_ndf |
|:---------------|-------------:|--------------:|----------------------:|----------------:|-----------:|
| template_phase |      3.01495 |       3.28149 |             0.088685  |        0.773569 |   22.8418  |
| cfd10          |      3.30275 |       6.21808 |             0.0519878 |      263.455    |    3.87851 |
| cfd20          |      3.36691 |       6.1578  |             0.0718654 |      285.587    |    4.04518 |
| of_4_12        |      3.37502 |       3.86647 |             0.165138  |      106.023    |    3.30086 |
| cfd30          |      3.44672 |       6.1583  |             0.0993884 |      299.144    |    3.55269 |
| cfd40          |      3.54097 |       6.26878 |             0.127676  |        1.29176  |    2.43102 |
| of_3_11        |      3.54267 |       3.76089 |             0.174312  |        1.39292  |    4.06129 |
| of_1_9         |      3.56215 |       3.75481 |             0.163609  |        1.09156  |    2.77414 |
| of_2_10        |      3.58812 |       3.80691 |             0.165138  |        0.939206 |    2.75975 |
| cfd50          |      3.71825 |       7.67163 |             0.150612  |        1.41255  |    1.36432 |
| le500          |      4.48226 |       6.97034 |             0.253823  |      146.994    |    1.46842 |

### Quantization Features

ADC quantization is represented at two levels: per-sample normalized waveforms plus fractional ADC residuals `q_k = w_k - round(w_k)`, and scalar summaries including `rms(q)`, mean absolute `q`, peak-sample `q`, near-integer fraction, tail fraction, late maximum, area/amplitude, pretrigger RMS, and stave one-hot. The feature vector contains 32 features.

The new architecture is `attention_quant`: a compact single-head self-attention encoder over the two-channel sequence `[normalized waveform, ADC fractional residual]`. It is intentionally small so that any gain can be attributed to the quantization-aware representation rather than a large capacity jump.

## 3. Run-Blocked Model Selection

Hyperparameters are selected by GroupKFold over training runs. The table below reports mean validation `sigma68` rows (`fold=-1`); full fold rows are in `architecture_cv.csv`.

| model                  |   sigma68_ns |
|:-----------------------|-------------:|
| gradient_boosted_trees |      1.57361 |
| ridge                  |      1.61031 |
| ridge                  |      1.62274 |
| ridge                  |      1.62378 |
| gradient_boosted_trees |      1.63237 |
| mlp                    |      1.70271 |
| mlp                    |      1.70311 |
| attention_quant        |      1.97654 |
| cnn                    |      2.0657  |

## 4. Held-Out Results with Bootstrap CIs

Confidence intervals are paired event bootstraps over held-out events. Each bootstrap resamples event ids and evaluates every method on the identical resampled event set, preserving the within-event three-pair correlation.

| model                      |   sigma68_ns |   ci_low |   ci_high |   delta_vs_traditional_template_phase_ns |   delta_ci_low |   delta_ci_high |   full_rms_ns |   n_pair_residuals |
|:---------------------------|-------------:|---------:|----------:|-----------------------------------------:|---------------:|----------------:|--------------:|-------------------:|
| ridge                      |      1.409   |  1.33007 |   1.47592 |                                -1.60596  |      -1.69262  |        -1.42462 |       2.42686 |               1308 |
| mlp                        |      1.49301 |  1.42202 |   1.55073 |                                -1.52194  |      -1.61592  |        -1.35817 |       2.30232 |               1308 |
| gradient_boosted_trees     |      1.49535 |  1.40065 |   1.57472 |                                -1.5196   |      -1.63965  |        -1.31927 |       2.10782 |               1308 |
| cnn                        |      1.685   |  1.63214 |   1.74729 |                                -1.32996  |      -1.34927  |        -1.20286 |       2.56975 |               1308 |
| attention_quant            |      2.36209 |  2.16144 |   2.38745 |                                -0.652858 |      -0.739624 |        -0.51943 |       2.88824 |               1308 |
| traditional_template_phase |      3.01495 |  2.89399 |   3.03145 |                                 0        |       0        |         0       |       3.28149 |               1308 |

The point-estimate winner is `ridge` with sigma68 `1.4090` ns, 95% CI `[1.3301, 1.4759]` ns. The selected traditional baseline gives `3.0150` ns, 95% CI `[2.8940, 3.0314]` ns.

Per-run held-out metrics are:

|   run | model                      |   n_pair_residuals |   sigma68_ns |   full_rms_ns |
|------:|:---------------------------|-------------------:|-------------:|--------------:|
|    63 | ridge                      |               1110 |      1.41754 |       2.53928 |
|    63 | gradient_boosted_trees     |               1110 |      1.49149 |       2.17947 |
|    63 | mlp                        |               1110 |      1.50844 |       2.40484 |
|    63 | cnn                        |               1110 |      1.68864 |       2.70282 |
|    63 | attention_quant            |               1110 |      2.37498 |       3.01291 |
|    63 | traditional_template_phase |               1110 |      3.03145 |       3.3943  |
|    65 | ridge                      |                198 |      1.3458  |       1.66001 |
|    65 | mlp                        |                198 |      1.42097 |       1.61069 |
|    65 | gradient_boosted_trees     |                198 |      1.48709 |       1.6469  |
|    65 | cnn                        |                198 |      1.62231 |       1.63125 |
|    65 | attention_quant            |                198 |      2.14425 |       2.05197 |
|    65 | traditional_template_phase |                198 |      2.83547 |       2.55748 |

## 5. Strata and Bias Mechanisms

S27a maps the benchmark across quantization, pulse-shape, timing-phase, pile-up proxy, saturation proxy, pedestal, energy, and PID-proxy strata. These are diagnostic strata, not independent labels: quantization is the observed integer versus half-step ADC grid after median-baseline subtraction, pile-up is approximated by late activity, saturation by the top amplitude tail, energy by area, and PID by stave/charge proxy.

Quantization-stratum summary:

| stratum        | model                      |   n_pair_residuals |   sigma68_ns |   median_abs_residual_ns |
|:---------------|:---------------------------|-------------------:|-------------:|-------------------------:|
| half_step_grid | ridge                      |               1158 |      1.41242 |                  1.60474 |
| half_step_grid | mlp                        |               1158 |      1.4964  |                  1.48717 |
| half_step_grid | gradient_boosted_trees     |               1158 |      1.50384 |                  1.59308 |
| half_step_grid | cnn                        |               1158 |      1.69347 |                  1.36068 |
| half_step_grid | attention_quant            |               1158 |      2.36259 |                  1.7866  |
| half_step_grid | traditional_template_phase |               1158 |      3.03145 |                  3.8378  |
| integer_grid   | ridge                      |               1152 |      1.41403 |                  1.57697 |
| integer_grid   | mlp                        |               1152 |      1.48241 |                  1.48717 |
| integer_grid   | gradient_boosted_trees     |               1152 |      1.48287 |                  1.59308 |
| integer_grid   | cnn                        |               1152 |      1.68267 |                  1.3556  |
| integer_grid   | attention_quant            |               1152 |      2.36223 |                  1.78605 |
| integer_grid   | traditional_template_phase |               1152 |      2.89399 |                  3.8378  |

All stratum families are written to `strata_summary.csv` for systematic review.

## 6. Leakage, Systematics, and Caveats

| check                     |   value | pass   | detail                                                                                                                                |
|:--------------------------|--------:|:-------|:--------------------------------------------------------------------------------------------------------------------------------------|
| train_heldout_run_overlap |       0 | True   | nan                                                                                                                                   |
| feature_audit             |       0 | True   | features are same-pulse waveform samples, ADC quantization residual summaries, amplitude/area/shape summaries, and stave one-hot only |
| target_audit              |       0 | True   | models predict residuals left by the training-selected traditional pickoff; no run id, event id, or other-stave time is included      |

- The timing target is a same-event downstream consistency proxy, not external time truth. A method can reduce pairwise spread while still sharing a common event-level offset.
- ADC quantization residuals are computed after median-baseline subtraction; the observed integer/half-step grid can therefore arise from the baseline estimator as well as the front-end ADC.
- The pile-up, saturation, energy, and PID labels used here are proxies intended for systematic slicing. They do not replace dedicated truth labels or external PID/energy calibration.
- Bootstrap intervals cover held-out event statistics but not the full model-selection uncertainty. The report names a held-out point-estimate winner and gives paired CIs; production adoption should require replication on an external run block.
- The compact attention model tests whether a new sequence representation is sensible for this ticket. It is not a broad transformer scaling study.

## 7. Verdict

The held-out winner is ridge with pairwise sigma68 1.4090 ns (95% CI 1.3301-1.4759) versus the training-selected traditional baseline traditional_template_phase at 3.0150 ns (95% CI 2.8940-3.0314). ADC quantization residual features are mapped as a systematic across pulse-shape, timing, pile-up, saturation, pedestal, energy, and PID-proxy strata; the result should be read as run-held-out timing-bias evidence, not external time truth.

The practical interpretation is that ADC quantization features are useful only if the winning ML/NN method improves the traditional baseline outside the paired CI overlap and remains stable across both observed ADC-grid modes. Otherwise, quantization remains a mapped systematic rather than a correction to promote.

## 8. Reproducibility

```bash
/home/billy/anaconda3/bin/python scripts/s27a_1783780886_11160_609b70e1_adc_quantization_timing.py --config configs/s27a_1783780886_11160_609b70e1_adc_quantization_timing.yaml
```

Runtime in this execution was `50.77` s. Primary artifacts: `REPORT.md`, `result.json`, `manifest.json`, `reproduction_match_table.csv`, `traditional_timing_scan.csv`, `architecture_cv.csv`, `method_summary.csv`, `per_run_metrics.csv`, `strata_summary.csv`, `heldout_pair_residuals.csv`, `leakage_checks.csv`, figures, and input/output SHA256 manifests.
