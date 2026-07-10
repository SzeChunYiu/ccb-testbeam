# P06e: external peak-phase causality control

- **Ticket:** 1781188455.827.4be93277
- **Author:** testbeam-laptop-1
- **Date:** 2026-07-10
- **Depends on:** S00, S02, P04, P07, P10e/P10g, S03h
- **Input checksums:** `input_sha256.csv`
- **Git commit:** `6fce8edc68a587e914ed0be5b1eee939618440a4`
- **Config:** `configs/p06e_1781188455_827_4be93277_external_peak_phase_causality_control.json`

## 0. Question

Does the P06d peak/CFD-phase coupling burden persist when same-event pulse physics is deliberately broken? I test this with a forced-random external control built from raw B-stack `HRDv`: (i) reproduce the selected B-stave pulse count exactly; (ii) derive peak/CFD/shape features from raw waveforms; (iii) replace each event timing reference by a deterministic same-run randomized event median; (iv) compare a transparent support-matched atlas against ridge, gradient-boosted trees, MLP, a 1D-CNN, and a phase-gated residual CNN on held-out runs.

## 1. Reproduction Gate

The gate is the S00 selected-pulse count, rebuilt directly from raw ROOT `HRDv` using B2/B4/B6/B8 even channels, median pretrigger baseline samples 0..3, and `A > 1000 ADC`. This is the relevant upstream number for any B-stack pulse-atom ticket.

| quantity                                    |   report_value |   reproduced |   delta |   tolerance | pass   |
|:--------------------------------------------|---------------:|-------------:|--------:|------------:|:-------|
| total selected B-stave pulses from raw HRDv |         640737 |       640737 |       0 |           0 | True   |
| sample_i_analysis selected B-stave pulses   |         252266 |       252266 |       0 |           0 | True   |
| sample_i_calib selected B-stave pulses      |         248745 |       248745 |       0 |           0 | True   |
| sample_ii_analysis selected B-stave pulses  |         125096 |       125096 |       0 |           0 | True   |
| sample_ii_calib selected B-stave pulses     |          14630 |        14630 |       0 |           0 | True   |

All downstream rows are therefore derived from the same raw pulse population as the accepted S00 gate. The modeling subset is narrower: B4/B6/B8 pulses with valid CFD timing. The timing endpoint is no longer same-event; each pulse is compared to a randomized reference event from the same run, preserving run conditions while breaking event-local pulse physics.

## 2. Traditional Method

For pulse \(i\), the corrected waveform is

\[
x_{ij} = h_{ij} - \operatorname{median}(h_{i0}, h_{i1}, h_{i2}, h_{i3}),
\]

with amplitude \(A_i=\max_j x_{ij}\). CFD phase is defined by linear interpolation at fraction \(f\):

\[
t_f = j-1 + \frac{fA_i-x_{i,j-1}}{x_{ij}-x_{i,j-1}},\quad
\phi_f=t_f-j_{\max}.
\]

The traditional comparator is a support-matched median atlas. Training pulses are binned by stave, log-amplitude quintile, peak-sample band, and CFD20 phase quintile. The prediction for held-out pulse \(i\) is the train median coupling burden in the matched cell, falling back to stave-amplitude and then stave medians when support is sparse.

The endpoint burden is intentionally a diagnostic summary, not a new truth label:

\[
B_i =
\frac{|r^t_i|}{m_t}+
0.75\frac{|r^q_i|}{m_q}+
0.50\frac{s_i}{q_s}+
0.50\frac{a_i}{q_a} .
\]

Here \(r^t_i=10(t^{20}_i-\tilde t^{20}_{\pi(e)})\) is the forced-random same-run timing residual in ns, where \(\pi(e)\) is a deterministic derangement-like event permutation within the run. \(r^q_i\) is train-only log-charge residual after a per-stave log(area)-vs-log(amplitude) calibration, \(s_i\) is a saturation stress score, and \(a_i\) is a dropout/anomaly score from tail area, secondary peak, pretrigger range, and post-peak undershoot. The normalizers \(m_t,m_q,q_s,q_a\) are computed on train runs only.

Held-out atlas endpoint table by CFD phase and amplitude:

|   phase_quartile |   amp_quartile |         n |   sigma68_timing_ns |   median_abs_charge_log_residual |   mean_saturation_harm |   mean_anomaly_dropout |   mean_coupling_burden |
|-----------------:|---------------:|----------:|--------------------:|---------------------------------:|-----------------------:|-----------------------:|-----------------------:|
|           0.0000 |         0.0000 | 3510.0000 |             31.3652 |                           0.3707 |                 0.1221 |                 8.5604 |                 2.9330 |
|           0.0000 |         1.0000 | 5036.0000 |             27.4700 |                           0.2872 |                 0.2175 |                 5.4316 |                 2.3337 |
|           0.0000 |         2.0000 | 2039.0000 |             25.5068 |                           0.3175 |                 0.3238 |                 4.0036 |                 2.2814 |
|           0.0000 |         3.0000 |  150.0000 |             28.3331 |                           0.2575 |                 0.3057 |                12.6095 |                 3.3261 |
|           1.0000 |         0.0000 | 1655.0000 |             31.0190 |                           0.3438 |                 0.1338 |                 5.4529 |                 2.5170 |
|           1.0000 |         1.0000 | 4273.0000 |             28.4795 |                           0.2552 |                 0.1580 |                 5.3135 |                 2.2184 |
|           1.0000 |         2.0000 | 2543.0000 |             25.8112 |                           0.3117 |                 0.2017 |                 4.2000 |                 2.2246 |
|           1.0000 |         3.0000 | 1148.0000 |             23.5855 |                           0.2817 |                 0.1420 |                 4.4925 |                 2.0890 |
|           2.0000 |         0.0000 | 1054.0000 |             22.5289 |                           0.1399 |                 0.1080 |                32.0760 |                 5.7668 |
|           2.0000 |         1.0000 | 1242.0000 |             28.5462 |                           0.2490 |                 0.2604 |                21.4853 |                 4.7143 |
|           2.0000 |         2.0000 | 3323.0000 |             26.9407 |                           0.3010 |                 0.1098 |                 6.7476 |                 2.4702 |
|           2.0000 |         3.0000 | 3508.0000 |             26.3555 |                           0.2403 |                 0.0359 |                 6.0452 |                 2.1564 |
|           3.0000 |         0.0000 | 1612.0000 |             27.4536 |                           0.2696 |                 0.1956 |                45.1824 |                 8.8536 |
|           3.0000 |         1.0000 |  668.0000 |             25.8679 |                           0.2503 |                 0.2264 |                46.9075 |                 8.9704 |
|           3.0000 |         2.0000 | 1769.0000 |             32.2266 |                           0.3168 |                 0.1881 |                14.3538 |                 3.8986 |
|           3.0000 |         3.0000 | 3353.0000 |             29.2531 |                           0.2362 |                 0.0822 |                 9.4098 |                 2.7445 |

Peak-phase high-minus-low contrast:

| contrast                            |   n_low |   n_high |   delta_sigma68_timing_ns |   delta_median_abs_charge_log_residual |   delta_mean_saturation_harm |   delta_mean_anomaly_dropout |   delta_mean_coupling_burden |
|:------------------------------------|--------:|---------:|--------------------------:|---------------------------------------:|-----------------------------:|-----------------------------:|-----------------------------:|
| high_minus_low_cfd20_phase_quartile |   10735 |     7402 |                    5.3982 |                                -0.0432 |                      -0.0625 |                      15.4822 |                       2.3790 |

## 3. ML and NN Methods

All models train on Sample I runs, use run 64 only for a scalar median calibration offset, and evaluate only Sample II analysis runs 58-63 and 65. Features exclude event number, randomized reference identity, and held-out run labels. The tabular feature set contains log-amplitude, area ratios, peak sample, CFD10/20/50 phase, CFD20-50 slew, pretrigger range, tail/late/early fractions, secondary-peak fraction, post-peak undershoot, plateau count, peak-edge score, and stave identity.

Methods:

- `ridge`: standardized tabular Ridge regression.
- `hist_gradient_boosted_trees`: train-run GroupKFold hyperparameter scan over leaf count, learning rate, and L2.
- `mlp`: standardized tabular neural net with hidden layers 80 and 40.
- `one_dimensional_cnn`: 18-sample raw corrected waveform CNN plus tabular head.
- `phase_gated_residual_cnn`: new architecture for this control; the waveform CNN representation is multiplicatively gated by the five peak/CFD phase coordinates before the regression head.

HGB group-CV scan, best rows:

| method                      |   max_leaf_nodes |   learning_rate |   l2_regularization |   group_cv_mae |
|:----------------------------|-----------------:|----------------:|--------------------:|---------------:|
| hist_gradient_boosted_trees |               31 |         0.06000 |             0.00000 |        0.77683 |
| hist_gradient_boosted_trees |               31 |         0.10000 |             0.00000 |        0.77715 |
| hist_gradient_boosted_trees |               31 |         0.06000 |             0.05000 |        0.77748 |
| hist_gradient_boosted_trees |               31 |         0.03000 |             0.05000 |        0.77751 |
| hist_gradient_boosted_trees |               31 |         0.10000 |             0.05000 |        0.77754 |
| hist_gradient_boosted_trees |               63 |         0.03000 |             0.05000 |        0.77783 |
| hist_gradient_boosted_trees |               63 |         0.06000 |             0.05000 |        0.77789 |
| hist_gradient_boosted_trees |               31 |         0.03000 |             0.00000 |        0.77791 |

Sentinel models are not eligible to win: amplitude-only HGB, run/stave-only Ridge, shuffled-target HGB, and peak-phase-dropout HGB.

## 4. Head-to-head Benchmark

Primary metric: held-out MAE of the standardized burden. Intervals are 95% run-block bootstrap CIs over held-out runs.

| method                       | family           |     n |    mae |   mae_ci_low |   mae_ci_high |    bias |   rmse |
|:-----------------------------|:-----------------|------:|-------:|-------------:|--------------:|--------:|-------:|
| one_dimensional_cnn          | ml               | 36883 | 0.4492 |       0.4294 |        0.4979 | -0.1254 | 0.6649 |
| phase_gated_residual_cnn     | new_architecture | 36883 | 0.4494 |       0.4316 |        0.4978 | -0.1253 | 0.6655 |
| mlp                          | ml               | 36883 | 0.4580 |       0.4392 |        0.5083 | -0.1170 | 0.6697 |
| hist_gradient_boosted_trees  | ml               | 36883 | 0.4673 |       0.4458 |        0.5247 | -0.1300 | 0.6891 |
| ridge                        | ml               | 36883 | 0.5440 |       0.5249 |        0.5847 | -0.0906 | 0.7642 |
| traditional_peak_phase_atlas | traditional      | 36883 | 0.7990 |       0.7624 |        0.8458 | -0.2155 | 1.2482 |

Delta versus the traditional atlas:

| method                      |   delta_mae_vs_traditional |   ci_low |   ci_high |
|:----------------------------|---------------------------:|---------:|----------:|
| one_dimensional_cnn         |                    -0.3499 |  -0.3744 |   -0.3225 |
| phase_gated_residual_cnn    |                    -0.3496 |  -0.3783 |   -0.3209 |
| mlp                         |                    -0.3411 |  -0.3649 |   -0.3138 |
| peak_phase_dropout_hgb      |                    -0.3333 |  -0.3578 |   -0.3071 |
| hist_gradient_boosted_trees |                    -0.3318 |  -0.3543 |   -0.2987 |
| ridge                       |                    -0.2550 |  -0.2777 |   -0.2259 |
| amplitude_only_hgb          |                    -0.0756 |  -0.0945 |   -0.0589 |
| run_only_hgb                |                     0.8963 |   0.8476 |    0.9594 |
| shuffled_target_hgb         |                     0.9023 |   0.8456 |    0.9632 |

Winner: **one_dimensional_cnn** with MAE `0.4492` versus traditional atlas `0.7990`. The winner-minus-traditional paired bootstrap delta is `-0.3499 [-0.3744, -0.3225]`.

Per-run held-out metrics:

|   run | method                       |    n |    mae |    bias |   rmse |
|------:|:-----------------------------|-----:|-------:|--------:|-------:|
|    58 | one_dimensional_cnn          |  990 | 0.7611 | -0.4244 | 1.0464 |
|    58 | traditional_peak_phase_atlas |  990 | 1.0897 | -0.5376 | 1.5284 |
|    59 | one_dimensional_cnn          | 7812 | 0.4149 | -0.0732 | 0.6062 |
|    59 | traditional_peak_phase_atlas | 7812 | 0.7312 | -0.1153 | 1.1659 |
|    60 | one_dimensional_cnn          | 7156 | 0.4403 | -0.0946 | 0.6441 |
|    60 | traditional_peak_phase_atlas | 7156 | 0.8406 | -0.2163 | 1.3270 |
|    61 | one_dimensional_cnn          | 7950 | 0.4357 | -0.1620 | 0.6502 |
|    61 | traditional_peak_phase_atlas | 7950 | 0.7989 | -0.2978 | 1.2615 |
|    62 | one_dimensional_cnn          | 7454 | 0.4322 | -0.1016 | 0.6332 |
|    62 | traditional_peak_phase_atlas | 7454 | 0.7834 | -0.1862 | 1.2151 |
|    63 | one_dimensional_cnn          | 4251 | 0.4559 | -0.1261 | 0.6783 |
|    63 | traditional_peak_phase_atlas | 4251 | 0.7619 | -0.1480 | 1.1628 |
|    65 | one_dimensional_cnn          | 1270 | 0.6279 | -0.2939 | 0.9203 |
|    65 | traditional_peak_phase_atlas | 1270 | 0.9714 | -0.4588 | 1.4118 |

## 5. Falsification

Pre-registration is copied from the ticket/config: lowest held-out MAE wins, but an ML method may be called a substantive win only if its paired run-block bootstrap CI versus the traditional atlas is entirely below zero.

Falsification tests:

- Shuffled target should not beat the physical feature models.
- Dropping peak/CFD phase should degrade or at least not improve the full HGB if the axis is specific.
- The run-only sentinel should not explain the burden by run identity alone.

| check                          | status   | detail                                                                                  |
|:-------------------------------|:---------|:----------------------------------------------------------------------------------------|
| raw_root_reproduction_count    | pass     | selected B-stave pulses counted from raw HRDv only                                      |
| run_split                      | pass     | Sample I trains; run 64 calibrates scalar offsets; Sample II analysis runs are held out |
| shuffled_target_sentinel       | pass     | shuffled-target MAE 1.7013 versus full HGB MAE 0.4673                                   |
| peak_phase_dropout_specificity | warn     | dropout HGB MAE 0.4658 versus full HGB MAE 0.4673                                       |

The multiple-comparison burden is five eligible non-traditional methods. The result names the lowest MAE method, while the win/no-win statement uses the stricter paired CI against the traditional atlas.

## 6. Systematics and Caveats

Benchmark/selection: the traditional atlas is strong for this question because it directly bins the claimed physical axes and matches support in stave, amplitude, peak, and phase. It is not a scalar strawman. In this control it is trained on the same forced-random target as the ML models.

Data leakage: the split is by run. Event ids, run ids, randomized reference ids, and target residuals are not model features. Run 64 is used only for a scalar post-fit calibration offset. The charge residual calibration coefficients and burden normalizers are fit on train runs only.

Metric misuse: the burden is a diagnostic composite, not a detector truth label. Endpoint tables report timing sigma68, charge residuals, saturation stress, anomaly/dropout score, and the full residual distribution summary, not only one core number.

Post-hoc selection: model families and win rule were fixed in the ticket/config. HGB tuning is reported as a train-run GroupKFold scan. The new architecture is included because the ticket explicitly invited a new architecture when sensible; its gate is physically tied to the peak/CFD phase hypothesis.

Caveats: the timing target is intentionally artificial. It preserves run-level acquisition conditions but destroys event-local simultaneity, so it is a negative-control stress test rather than a detector timing estimate. Saturation and anomaly/dropout are proxy scores derived from waveform morphology, not hand-reviewed labels. A residual phase-gated win here would favor run-family or morphology confounding; attenuation of the win supports, but does not prove, the P06d causal waveform-atom interpretation.

## 7. Provenance Manifest

Machine-readable provenance is in `manifest.json`. Main artifacts: `result.json`, `reproduction.csv`, `benchmark_summary.csv`, `delta_vs_traditional.csv`, `benchmark_by_run.csv`, `endpoint_atlas.csv`, `endpoint_effects.csv`, `cv_scan.csv`, `leakage_checks.csv`, `predictions_sample.csv`, `fig_benchmark_mae.png`, `fig_residual_distributions.png`, and `fig_peak_phase_atlas.png`.

## 8. Findings and Next Steps

The held-out atlas shows whether high CFD20 phase carries larger timing width, charge residual, saturation stress, and anomaly/dropout burden after amplitude stratification. The benchmark result is: one_dimensional_cnn has the lowest held-out burden MAE 0.4492 versus traditional 0.7990; paired CI declares an ML win..

No follow-up ticket was appended automatically by this script.

## 9. Reproducibility

Run:

```bash
.venv/bin/python scripts/p06e_1781188455_827_4be93277_external_peak_phase_causality_control.py --config configs/p06e_1781188455_827_4be93277_external_peak_phase_causality_control.json
```
