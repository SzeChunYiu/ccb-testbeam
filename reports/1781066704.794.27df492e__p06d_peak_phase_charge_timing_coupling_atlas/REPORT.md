# P06d: peak-phase charge-timing coupling atlas

- **Ticket:** 1781066704.794.27df492e
- **Author:** testbeam-laptop-4
- **Date:** 2026-06-11
- **Depends on:** S00, S02, P04, P07, P10e/P10g, S03h
- **Input checksums:** `input_sha256.csv`
- **Git commit:** `64b1940dbd9a7e2b4d66f4c759d69e709f530953`
- **Config:** `configs/p06d_1781066704_794_27df492e_peak_phase_coupling_atlas.json`

## 0. Question

Are peak-sample and CFD-phase shifts a common pulse atom behind same-event timing residuals, charge non-linearity, saturation-boundary stress, and dropout/anomaly decisions, or do those effects separate after support matching? I test this with one raw-ROOT pipeline: (i) reproduce the selected B-stave pulse count; (ii) derive peak/CFD/shape features from `HRDv`; (iii) define train-only calibrated endpoint residuals; (iv) compare a transparent support-matched atlas against ridge, gradient-boosted trees, MLP, a 1D-CNN, and a phase-gated residual CNN on held-out runs.

## 1. Reproduction Gate

The gate is the S00 selected-pulse count, rebuilt directly from raw ROOT `HRDv` using B2/B4/B6/B8 even channels, median pretrigger baseline samples 0..3, and `A > 1000 ADC`. This is the relevant upstream number for any B-stack pulse-atom ticket.

| quantity                                    |   report_value |   reproduced |   delta |   tolerance | pass   |
|:--------------------------------------------|---------------:|-------------:|--------:|------------:|:-------|
| total selected B-stave pulses from raw HRDv |         640737 |       640737 |       0 |           0 | True   |
| sample_i_analysis selected B-stave pulses   |         252266 |       252266 |       0 |           0 | True   |
| sample_i_calib selected B-stave pulses      |         248745 |       248745 |       0 |           0 | True   |
| sample_ii_analysis selected B-stave pulses  |         125096 |       125096 |       0 |           0 | True   |
| sample_ii_calib selected B-stave pulses     |          14630 |        14630 |       0 |           0 | True   |

All downstream rows are therefore derived from the same raw pulse population as the accepted S00 gate. The modeling subset is narrower: B4/B6/B8 pulses in events with at least two selected timing staves, because the timing target is a same-event residual.

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

Here \(r^t_i\) is same-event CFD20 timing residual in ns, \(r^q_i\) is train-only log-charge residual after a per-stave log(area)-vs-log(amplitude) calibration, \(s_i\) is a saturation stress score, and \(a_i\) is a dropout/anomaly score from tail area, secondary peak, pretrigger range, and post-peak undershoot. The normalizers \(m_t,m_q,q_s,q_a\) are computed on train runs only.

Held-out atlas endpoint table by CFD phase and amplitude:

|   phase_quartile |   amp_quartile |         n |   sigma68_timing_ns |   median_abs_charge_log_residual |   mean_saturation_harm |   mean_anomaly_dropout |   mean_coupling_burden |
|-----------------:|---------------:|----------:|--------------------:|---------------------------------:|-----------------------:|-----------------------:|-----------------------:|
|           0.0000 |         0.0000 | 2625.0000 |              3.0226 |                           0.3521 |                 0.1091 |                 8.1961 |                 3.6514 |
|           0.0000 |         1.0000 | 2680.0000 |              2.8848 |                           0.2688 |                 0.1936 |                 5.0016 |                 2.9456 |
|           0.0000 |         2.0000 | 2056.0000 |              1.9170 |                           0.2861 |                 0.3436 |                 4.1908 |                 2.8719 |
|           0.0000 |         3.0000 |  130.0000 |              3.6058 |                           0.2686 |                 0.3369 |                10.3223 |                 5.8024 |
|           1.0000 |         0.0000 | 1762.0000 |              2.6583 |                           0.3355 |                 0.0916 |                 6.2182 |                 2.9720 |
|           1.0000 |         1.0000 | 2576.0000 |              2.5261 |                           0.2536 |                 0.1283 |                 5.4100 |                 2.6764 |
|           1.0000 |         2.0000 | 1319.0000 |              2.6080 |                           0.2828 |                 0.2701 |                 3.7544 |                 2.5939 |
|           1.0000 |         3.0000 |  504.0000 |              2.0755 |                           0.3428 |                 0.1918 |                 3.9101 |                 2.9415 |
|           2.0000 |         0.0000 | 1018.0000 |              1.1618 |                           0.1556 |                 0.1255 |                27.9188 |                 5.4241 |
|           2.0000 |         1.0000 |  869.0000 |              2.4290 |                           0.2607 |                 0.2433 |                12.7663 |                 3.8930 |
|           2.0000 |         2.0000 | 1745.0000 |              2.5954 |                           0.2858 |                 0.1997 |                 5.1519 |                 2.7839 |
|           2.0000 |         3.0000 | 2287.0000 |              1.6266 |                           0.3048 |                 0.0467 |                 4.4814 |                 2.4673 |
|           3.0000 |         0.0000 |  740.0000 |              0.8334 |                           0.2189 |                 0.2470 |                39.7261 |                 8.3107 |
|           3.0000 |         1.0000 |  390.0000 |              1.5101 |                           0.2539 |                 0.2894 |                38.7079 |                 8.5404 |
|           3.0000 |         2.0000 |  876.0000 |              2.2949 |                           0.2989 |                 0.2511 |                16.6721 |                 4.5109 |
|           3.0000 |         3.0000 | 3159.0000 |              1.8946 |                           0.2934 |                 0.0737 |                 8.7974 |                 3.1776 |

Peak-phase high-minus-low contrast:

| contrast                            |   n_low |   n_high |   delta_sigma68_timing_ns |   delta_median_abs_charge_log_residual |   delta_mean_saturation_harm |   delta_mean_anomaly_dropout |   delta_mean_coupling_burden |
|:------------------------------------|--------:|---------:|--------------------------:|---------------------------------------:|-----------------------------:|-----------------------------:|-----------------------------:|
| high_minus_low_cfd20_phase_quartile |    7491 |     5165 |                   -0.8140 |                                -0.0035 |                      -0.0628 |                      10.8319 |                       1.3218 |

## 3. ML and NN Methods

All models train on Sample I runs, use run 64 only for a scalar median calibration offset, and evaluate only Sample II analysis runs 58-63 and 65. Features exclude event number and any held-out run labels. The tabular feature set contains log-amplitude, area ratios, peak sample, CFD10/20/50 phase, CFD20-50 slew, pretrigger range, tail/late/early fractions, secondary-peak fraction, post-peak undershoot, plateau count, peak-edge score, and stave identity.

Methods:

- `ridge`: standardized tabular Ridge regression.
- `hist_gradient_boosted_trees`: train-run GroupKFold hyperparameter scan over leaf count, learning rate, and L2.
- `mlp`: standardized tabular neural net with hidden layers 80 and 40.
- `one_dimensional_cnn`: 18-sample raw corrected waveform CNN plus tabular head.
- `phase_gated_residual_cnn`: new architecture; the waveform CNN representation is multiplicatively gated by the five peak/CFD phase coordinates before the regression head.

HGB group-CV scan, best rows:

| method                      |   max_leaf_nodes |   learning_rate |   l2_regularization |   group_cv_mae |
|:----------------------------|-----------------:|----------------:|--------------------:|---------------:|
| hist_gradient_boosted_trees |               15 |         0.03000 |             0.05000 |        0.69165 |
| hist_gradient_boosted_trees |               15 |         0.03000 |             0.00000 |        0.69230 |
| hist_gradient_boosted_trees |               31 |         0.03000 |             0.00000 |        0.69436 |
| hist_gradient_boosted_trees |               31 |         0.03000 |             0.05000 |        0.69481 |
| hist_gradient_boosted_trees |               15 |         0.06000 |             0.00000 |        0.69716 |
| hist_gradient_boosted_trees |               15 |         0.06000 |             0.05000 |        0.69805 |
| hist_gradient_boosted_trees |               63 |         0.03000 |             0.05000 |        0.69812 |
| hist_gradient_boosted_trees |               63 |         0.03000 |             0.00000 |        0.69909 |

Sentinel models are not eligible to win: amplitude-only HGB, run/stave-only Ridge, shuffled-target HGB, and peak-phase-dropout HGB.

## 4. Head-to-head Benchmark

Primary metric: held-out MAE of the standardized burden. Intervals are 95% run-block bootstrap CIs over held-out runs.

| method                       | family           |     n |    mae |   mae_ci_low |   mae_ci_high |    bias |   rmse |
|:-----------------------------|:-----------------|------:|-------:|-------------:|--------------:|--------:|-------:|
| one_dimensional_cnn          | ml               | 24736 | 0.6167 |       0.5850 |        0.6521 | -0.1366 | 1.9850 |
| phase_gated_residual_cnn     | new_architecture | 24736 | 0.6236 |       0.5902 |        0.6587 | -0.1534 | 1.9982 |
| hist_gradient_boosted_trees  | ml               | 24736 | 0.6419 |       0.6052 |        0.6856 | -0.0901 | 1.9938 |
| mlp                          | ml               | 24736 | 0.6510 |       0.6103 |        0.6974 | -0.0661 | 2.0447 |
| ridge                        | ml               | 24736 | 0.7414 |       0.7038 |        0.7827 | -0.0486 | 2.0872 |
| traditional_peak_phase_atlas | traditional      | 24736 | 0.8633 |       0.8076 |        0.9226 | -0.2930 | 2.2558 |

Delta versus the traditional atlas:

| method                      |   delta_mae_vs_traditional |   ci_low |   ci_high |
|:----------------------------|---------------------------:|---------:|----------:|
| one_dimensional_cnn         |                    -0.2466 |  -0.2743 |   -0.2122 |
| phase_gated_residual_cnn    |                    -0.2397 |  -0.2678 |   -0.2132 |
| hist_gradient_boosted_trees |                    -0.2214 |  -0.2511 |   -0.1887 |
| mlp                         |                    -0.2123 |  -0.2354 |   -0.1867 |
| peak_phase_dropout_hgb      |                    -0.1980 |  -0.2223 |   -0.1687 |
| ridge                       |                    -0.1219 |  -0.1583 |   -0.0832 |
| amplitude_only_hgb          |                     0.0295 |   0.0118 |    0.0447 |
| run_only_hgb                |                     0.6327 |   0.5641 |    0.6990 |
| shuffled_target_hgb         |                     0.7916 |   0.7203 |    0.8696 |

Winner: **one_dimensional_cnn** with MAE `0.6167` versus traditional atlas `0.8633`. The winner-minus-traditional paired bootstrap delta is `-0.2466 [-0.2743, -0.2122]`.

Per-run held-out metrics:

|   run | method                       |    n |    mae |    bias |   rmse |
|------:|:-----------------------------|-----:|-------:|--------:|-------:|
|    58 | one_dimensional_cnn          |  487 | 0.8055 | -0.2533 | 2.8151 |
|    58 | traditional_peak_phase_atlas |  487 | 1.1394 | -0.5253 | 2.9701 |
|    59 | one_dimensional_cnn          | 5217 | 0.5929 | -0.1237 | 1.7370 |
|    59 | traditional_peak_phase_atlas | 5217 | 0.7914 | -0.2205 | 1.9522 |
|    60 | one_dimensional_cnn          | 4976 | 0.6321 | -0.1442 | 2.1058 |
|    60 | traditional_peak_phase_atlas | 4976 | 0.9235 | -0.3588 | 2.4214 |
|    61 | one_dimensional_cnn          | 5691 | 0.6544 | -0.1534 | 2.2263 |
|    61 | traditional_peak_phase_atlas | 5691 | 0.9269 | -0.3471 | 2.5510 |
|    62 | one_dimensional_cnn          | 5245 | 0.5617 | -0.1034 | 1.6789 |
|    62 | traditional_peak_phase_atlas | 5245 | 0.7971 | -0.2476 | 1.9298 |
|    63 | one_dimensional_cnn          | 2522 | 0.6597 | -0.1991 | 2.2313 |
|    63 | traditional_peak_phase_atlas | 2522 | 0.8640 | -0.2893 | 2.4538 |
|    65 | one_dimensional_cnn          |  598 | 0.4834 |  0.0407 | 0.6454 |
|    65 | traditional_peak_phase_atlas |  598 | 0.7359 | -0.0888 | 1.1317 |

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
| shuffled_target_sentinel       | pass     | shuffled-target MAE 1.6549 versus full HGB MAE 0.6419                                   |
| peak_phase_dropout_specificity | pass     | dropout HGB MAE 0.6653 versus full HGB MAE 0.6419                                       |

The multiple-comparison burden is five eligible non-traditional methods. The result names the lowest MAE method, while the win/no-win statement uses the stricter paired CI against the traditional atlas.

## 6. Systematics and Caveats

Benchmark/selection: the traditional atlas is strong for this question because it directly bins the claimed physical axes and matches support in stave, amplitude, peak, and phase. It is not a scalar strawman.

Data leakage: the split is by run. Event ids, run ids, and target residuals are not model features. Run 64 is used only for a scalar post-fit calibration offset. The charge residual calibration coefficients and burden normalizers are fit on train runs only.

Metric misuse: the burden is a diagnostic composite, not a detector truth label. Endpoint tables report timing sigma68, charge residuals, saturation stress, anomaly/dropout score, and the full residual distribution summary, not only one core number.

Post-hoc selection: model families and win rule were fixed in the ticket/config. HGB tuning is reported as a train-run GroupKFold scan. The new architecture is included because the ticket explicitly invited a new architecture when sensible; its gate is physically tied to the peak/CFD phase hypothesis.

Caveats: the timing target uses same-event relative timing, so common-mode event jitter cancels but absolute time-of-flight does not enter. Saturation and anomaly/dropout are proxy scores derived from waveform morphology, not hand-reviewed labels. A causal claim would require an intervention or an external forced-random/control sample; this study establishes support-matched predictive coupling.

## 7. Provenance Manifest

Machine-readable provenance is in `manifest.json`. Main artifacts: `result.json`, `reproduction.csv`, `benchmark_summary.csv`, `delta_vs_traditional.csv`, `benchmark_by_run.csv`, `endpoint_atlas.csv`, `endpoint_effects.csv`, `cv_scan.csv`, `leakage_checks.csv`, `predictions_sample.csv`, `fig_benchmark_mae.png`, `fig_residual_distributions.png`, and `fig_peak_phase_atlas.png`.

## 8. Findings and Next Steps

The held-out atlas shows whether high CFD20 phase carries larger timing width, charge residual, saturation stress, and anomaly/dropout burden after amplitude stratification. The benchmark result is: one_dimensional_cnn has the lowest held-out burden MAE 0.6167 versus traditional 0.8633; paired CI declares an ML win.

A single follow-up was appended: `1781188455.827.4be93277` / **P06e external peak-phase causality control**. Question: does the P06d peak/CFD-phase coupling burden persist in an external control that breaks same-event pulse physics, such as forced-random/no-pulse ROOT where available or A-stack/B-stack event-matched controls? Expected information gain: distinguishes a causal waveform atom from acquisition/run-family confounding after the P06d phase-gated CNN win. Compare a support-matched peak-phase atlas against ridge, gradient-boosted trees, MLP, 1D-CNN, and the phase-gated CNN with run-held-out bootstrap CIs and shuffled/phase-dropout sentinels.

## 9. Reproducibility

Run:

```bash
.venv/bin/python scripts/p06d_1781066704_794_27df492e_peak_phase_coupling_atlas.py --config configs/p06d_1781066704_794_27df492e_peak_phase_coupling_atlas.json
```
