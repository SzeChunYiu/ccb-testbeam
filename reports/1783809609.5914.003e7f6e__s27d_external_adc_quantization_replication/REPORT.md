# Study report: S27d - External run-block replication of ADC quantization timing correction

- **Ticket:** `1783809609.5914.003e7f6e`
- **Worker:** `testbeam-laptop-4`
- **Date:** 2026-07-12
- **Input:** raw B-stack ROOT files under `data/root/root`
- **Config:** `configs/s27d_1783809609_5914_003e7f6e_external_adc_quantization_replication.yaml`
- **Git commit at run time:** `c0f2171b94c5dcf99f4c838098bde214dc144f79`

## Abstract

S27d is an external run-block replication of the S27a ADC-quantization timing correction. The raw selected-pulse count is first reproduced from ROOT. The S27a benchmark design is frozen: the strong traditional timing pickoff is selected only on the original Sample-II training runs, the S27a winning ridge family is fixed at alpha=10, and the same ridge, gradient-boosted trees, MLP, 1D-CNN, and compact quantization-aware attention comparators are trained only on runs [58, 59, 60, 61, 62]. Generalization is evaluated on the independent Sample-I analysis block [44, 45, 46, 47, 48, 49, 50, 51, 52, 53, 54, 55, 56, 57] with paired event bootstrap confidence intervals. The winner recorded in `result.json` is `cnn`.

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

The exact `640737` count and Sample-II stave counts are recovered before any modeling, so the external replication is tied to the same raw-data surface as the established timing reports while reserving Sample-I analysis runs for the independent benchmark.

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

The strong traditional candidate is selected on the frozen S27a training runs only from leading edge, CFD fractions, template phase, and optimal-filter windows. The selected baseline is `template_phase`. External-block traditional diagnostics are:

| method         |   sigma68_ns |   full_rms_ns |   tail_frac_abs_gt5ns |   core_sigma_ns |   chi2_ndf |
|:---------------|-------------:|--------------:|----------------------:|----------------:|-----------:|
| template_phase |      2.64399 |       2.97978 |             0.0476923 |        1.03198  |   39.969   |
| of_4_12        |      2.96871 |       3.45023 |             0.14      |        7.67107  |    9.82429 |
| cfd20          |      3.14881 |       6.28467 |             0.0687179 |      310.004    |    4.11538 |
| cfd30          |      3.2066  |       5.99387 |             0.0979487 |      231.511    |    4.24705 |
| cfd10          |      3.28654 |       6.96215 |             0.0492308 |      224.151    |    5.72666 |
| cfd40          |      3.35064 |       4.3871  |             0.12      |      236.205    |    3.74065 |
| of_3_11        |      3.48693 |       3.47125 |             0.197436  |        1.24397  |    6.26954 |
| cfd50          |      3.54233 |       4.35306 |             0.139487  |        1.85572  |    2.50463 |
| of_1_9         |      3.76662 |       3.53346 |             0.18359   |        0.672056 |    5.9048  |
| of_2_10        |      4.07439 |       3.78369 |             0.207179  |        0.635211 |    6.06122 |
| le500          |      4.20316 |       6.73249 |             0.225128  |      215.132    |    1.31452 |

### Quantization Features

ADC quantization is represented at two levels: per-sample normalized waveforms plus fractional ADC residuals `q_k = w_k - round(w_k)`, and scalar summaries including `rms(q)`, mean absolute `q`, peak-sample `q`, near-integer fraction, tail fraction, late maximum, area/amplitude, pretrigger RMS, and stave one-hot. The feature vector contains 32 features.

The new architecture is `attention_quant`: a compact single-head self-attention encoder over the two-channel sequence `[normalized waveform, ADC fractional residual]`. It is intentionally small so that any gain can be attributed to the quantization-aware representation rather than a large capacity jump. In S27d this architecture is used as a replication stress test, not as a new architecture search.

## 3. Frozen Run-Blocked Model Selection

Hyperparameters are selected by GroupKFold over the original S27a training runs. For the S27a winning ridge correction the candidate list is intentionally frozen to `alpha=10.0`; the other families retain their S27a candidate grids so the external block still contains the requested multi-method benchmark. The table below reports mean validation `sigma68` rows (`fold=-1`); full fold rows are in `architecture_cv.csv`.

| model                  |   sigma68_ns |
|:-----------------------|-------------:|
| gradient_boosted_trees |      1.57361 |
| ridge                  |      1.61031 |
| gradient_boosted_trees |      1.63237 |
| mlp                    |      1.69475 |
| mlp                    |      1.7118  |
| attention_quant        |      2.14894 |
| cnn                    |      2.22248 |

## 4. Held-Out Results with Bootstrap CIs

Confidence intervals are paired event bootstraps over held-out events. Each bootstrap resamples event ids and evaluates every method on the identical resampled event set, preserving the within-event three-pair correlation.

| model                      |   sigma68_ns |   ci_low |   ci_high |   delta_vs_traditional_template_phase_ns |   delta_ci_low |   delta_ci_high |   full_rms_ns |   n_pair_residuals |
|:---------------------------|-------------:|---------:|----------:|-----------------------------------------:|---------------:|----------------:|--------------:|-------------------:|
| cnn                        |     0.636606 | 0.618894 |  0.661711 |                                 -2.00739 |       -2.0251  |        -1.98228 |       1.87533 |               1950 |
| attention_quant            |     0.914131 | 0.901183 |  0.929856 |                                 -1.72986 |       -1.74281 |        -1.71414 |       1.96324 |               1950 |
| ridge                      |     1.17734  | 1.15194  |  1.20734  |                                 -1.46665 |       -1.49205 |        -1.43665 |       2.0007  |               1950 |
| mlp                        |     1.38793  | 1.33996  |  1.45208  |                                 -1.25607 |       -1.30403 |        -1.19191 |       2.07467 |               1950 |
| gradient_boosted_trees     |     1.53929  | 1.49052  |  1.60085  |                                 -1.10471 |       -1.15347 |        -1.04314 |       2.1947  |               1950 |
| traditional_template_phase |     2.64399  | 2.64399  |  2.64399  |                                  0       |        0       |         0       |       2.97978 |               1950 |

The point-estimate winner is `cnn` with sigma68 `0.6366` ns, 95% CI `[0.6189, 0.6617]` ns. The selected traditional baseline gives `2.6440` ns, 95% CI `[2.6440, 2.6440]` ns.

Per-run held-out metrics are:

|   run | model                      |   n_pair_residuals |   sigma68_ns |   full_rms_ns |
|------:|:---------------------------|-------------------:|-------------:|--------------:|
|    44 | cnn                        |                 21 |     0.61178  |      1.26881  |
|    44 | attention_quant            |                 21 |     0.880186 |      1.40643  |
|    44 | mlp                        |                 21 |     1.21394  |      1.31186  |
|    44 | ridge                      |                 21 |     1.23451  |      1.12681  |
|    44 | gradient_boosted_trees     |                 21 |     1.76178  |      3.51859  |
|    44 | traditional_template_phase |                 21 |     2.64399  |      2.81822  |
|    45 | cnn                        |                282 |     0.636285 |      1.60406  |
|    45 | attention_quant            |                282 |     0.910839 |      1.7277   |
|    45 | ridge                      |                282 |     1.18342  |      1.66811  |
|    45 | mlp                        |                282 |     1.3996   |      1.8855   |
|    45 | gradient_boosted_trees     |                282 |     1.51406  |      2.02564  |
|    45 | traditional_template_phase |                282 |     2.64399  |      2.86408  |
|    46 | gradient_boosted_trees     |                  3 |     0.179746 |      0.216512 |
|    46 | ridge                      |                  3 |     0.247417 |      0.297596 |
|    46 | mlp                        |                  3 |     0.326616 |      0.39759  |
|    46 | cnn                        |                  3 |     0.942151 |      1.29349  |
|    46 | attention_quant            |                  3 |     1.06094  |      1.44856  |
|    46 | traditional_template_phase |                  3 |     2.30792  |      3.14817  |
|    47 | cnn                        |                 27 |     0.60389  |      0.810222 |
|    47 | attention_quant            |                 27 |     0.844168 |      0.885242 |
|    47 | mlp                        |                 27 |     1.21239  |      1.25593  |
|    47 | ridge                      |                 27 |     1.21868  |      1.10606  |
|    47 | gradient_boosted_trees     |                 27 |     1.51182  |      1.3363   |
|    47 | traditional_template_phase |                 27 |     2.64399  |      2.30462  |
|    48 | cnn                        |                174 |     0.628211 |      0.976073 |
|    48 | attention_quant            |                174 |     0.914335 |      1.14524  |
|    48 | ridge                      |                174 |     1.16564  |      1.21597  |
|    48 | mlp                        |                174 |     1.31449  |      1.39298  |
|    48 | gradient_boosted_trees     |                174 |     1.56657  |      1.53329  |
|    48 | traditional_template_phase |                174 |     2.64399  |      2.55941  |
|    49 | cnn                        |                168 |     0.775873 |      1.50345  |
|    49 | attention_quant            |                168 |     0.936919 |      1.62035  |
|    49 | ridge                      |                168 |     1.17261  |      1.59803  |
|    49 | mlp                        |                168 |     1.42179  |      1.73075  |
|    49 | gradient_boosted_trees     |                168 |     1.58372  |      2.10127  |
|    49 | traditional_template_phase |                168 |     2.64399  |      2.83537  |
|    50 | cnn                        |                180 |     0.84405  |      1.19795  |
|    50 | attention_quant            |                180 |     1.0198   |      1.32376  |
|    50 | ridge                      |                180 |     1.20128  |      1.30508  |
|    50 | mlp                        |                180 |     1.40112  |      1.41873  |
|    50 | gradient_boosted_trees     |                180 |     1.54261  |      1.64081  |
|    50 | traditional_template_phase |                180 |     2.64399  |      2.67258  |
|    51 | cnn                        |                102 |     0.662485 |      4.37811  |
|    51 | attention_quant            |                102 |     0.892925 |      4.47597  |
|    51 | ridge                      |                102 |     1.19551  |      4.20698  |
|    51 | mlp                        |                102 |     1.5922   |      4.31086  |
|    51 | gradient_boosted_trees     |                102 |     1.66728  |      3.92695  |
|    51 | traditional_template_phase |                102 |     2.64399  |      5.18526  |
|    52 | cnn                        |                 66 |     0.59904  |      0.680541 |
|    52 | attention_quant            |                 66 |     0.890823 |      0.881579 |
|    52 | ridge                      |                 66 |     1.00056  |      1.02386  |
|    52 | mlp                        |                 66 |     1.16149  |      1.08668  |
|    52 | gradient_boosted_trees     |                 66 |     1.30187  |      1.32954  |
|    52 | traditional_template_phase |                 66 |     2.64399  |      2.41505  |
|    53 | cnn                        |                177 |     0.616936 |      2.03652  |
|    53 | attention_quant            |                177 |     0.90312  |      2.07333  |
|    53 | ridge                      |                177 |     1.15673  |      2.11038  |
|    53 | mlp                        |                177 |     1.34097  |      1.99219  |
|    53 | gradient_boosted_trees     |                177 |     1.54863  |      2.25294  |
|    53 | traditional_template_phase |                177 |     2.64399  |      2.98534  |
|    54 | cnn                        |                150 |     0.607866 |      0.850499 |
|    54 | attention_quant            |                150 |     0.912846 |      0.989998 |
|    54 | ridge                      |                150 |     1.21518  |      1.22917  |
|    54 | mlp                        |                150 |     1.45644  |      1.38089  |
|    54 | gradient_boosted_trees     |                150 |     1.51638  |      1.64999  |
|    54 | traditional_template_phase |                150 |     2.64399  |      2.39401  |
|    55 | cnn                        |                132 |     0.614091 |      1.06626  |
|    55 | attention_quant            |                132 |     0.902838 |      1.19126  |
|    55 | ridge                      |                132 |     1.17989  |      1.285    |
|    55 | mlp                        |                132 |     1.22228  |      1.30415  |
|    55 | gradient_boosted_trees     |                132 |     1.43493  |      1.40366  |
|    55 | traditional_template_phase |                132 |     2.64399  |      2.50098  |
|    56 | cnn                        |                276 |     0.64797  |      2.64269  |
|    56 | attention_quant            |                276 |     0.912659 |      2.69911  |
|    56 | ridge                      |                276 |     1.16872  |      2.97522  |
|    56 | mlp                        |                276 |     1.45501  |      2.97681  |
|    56 | gradient_boosted_trees     |                276 |     1.59315  |      2.97431  |
|    56 | traditional_template_phase |                276 |     2.64399  |      3.34476  |
|    57 | cnn                        |                192 |     0.670605 |      1.24102  |
|    57 | attention_quant            |                192 |     0.923068 |      1.35175  |
|    57 | ridge                      |                192 |     1.19061  |      1.37171  |
|    57 | mlp                        |                192 |     1.44125  |      1.46084  |
|    57 | gradient_boosted_trees     |                192 |     1.5567   |      1.57445  |
|    57 | traditional_template_phase |                192 |     2.64399  |      2.63703  |

## 5. Strata and Bias Mechanisms

S27d maps the external-block benchmark across quantization, pulse-shape, timing-phase, pile-up proxy, saturation proxy, pedestal, energy, and PID-proxy strata. These are diagnostic strata, not independent labels: quantization is the observed integer versus half-step ADC grid after median-baseline subtraction, pile-up is approximated by late activity, saturation by the top amplitude tail, energy by area, and PID by stave/charge proxy.

Quantization-stratum summary:

| stratum        | model                      |   n_pair_residuals |   sigma68_ns |   median_abs_residual_ns |
|:---------------|:---------------------------|-------------------:|-------------:|-------------------------:|
| half_step_grid | cnn                        |               1692 |     0.630214 |                 0.464517 |
| half_step_grid | attention_quant            |               1692 |     0.919249 |                 0.722152 |
| half_step_grid | ridge                      |               1692 |     1.1683   |                 1.74318  |
| half_step_grid | mlp                        |               1692 |     1.37961  |                 1.74506  |
| half_step_grid | gradient_boosted_trees     |               1692 |     1.53608  |                 1.91531  |
| half_step_grid | traditional_template_phase |               1692 |     2.64399  |                 3.8378   |
| integer_grid   | cnn                        |               1719 |     0.637616 |                 0.465977 |
| integer_grid   | attention_quant            |               1719 |     0.915117 |                 0.718209 |
| integer_grid   | ridge                      |               1719 |     1.17869  |                 1.74397  |
| integer_grid   | mlp                        |               1719 |     1.3989   |                 1.7774   |
| integer_grid   | gradient_boosted_trees     |               1719 |     1.55284  |                 1.91807  |
| integer_grid   | traditional_template_phase |               1719 |     2.64399  |                 3.8378   |

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
- Bootstrap intervals cover external-block event statistics but not the full model-selection uncertainty. S27d addresses the most important S27a caveat by using a disjoint acquisition block, but it does not make the timing proxy an external time-truth measurement.
- The compact attention model tests whether a new sequence representation is sensible for this ticket. It is not a broad transformer scaling study.

## 7. Verdict

The held-out winner is cnn with pairwise sigma68 0.6366 ns (95% CI 0.6189-0.6617) versus the training-selected traditional baseline traditional_template_phase at 2.6440 ns (95% CI 2.6440-2.6440). The frozen S27a ridge correction also transfers to the independent Sample-I block at 1.1773 ns (95% CI 1.1519-1.2073), but it is not the external-block winner; the result should be read as timing-proxy evidence, not external time truth.

The practical interpretation is that the S27a ADC quantization correction is externally stable only if the frozen ridge-family correction improves the traditional baseline outside paired-CI overlap and remains stable across both observed ADC-grid modes in this Sample-I block. If another model wins or the ridge gain collapses, quantization should remain a mapped systematic rather than a promoted correction.

## 8. Reproducibility

```bash
/home/billy/anaconda3/bin/python scripts/s27d_1783809609_5914_003e7f6e_external_adc_quantization_replication.py --config configs/s27d_1783809609_5914_003e7f6e_external_adc_quantization_replication.yaml
```

Runtime in this execution was `63.35` s. Primary artifacts: `REPORT.md`, `result.json`, `manifest.json`, `reproduction_match_table.csv`, `traditional_timing_scan.csv`, `architecture_cv.csv`, `method_summary.csv`, `per_run_metrics.csv`, `strata_summary.csv`, `heldout_pair_residuals.csv`, `leakage_checks.csv`, figures, and input/output SHA256 manifests.
