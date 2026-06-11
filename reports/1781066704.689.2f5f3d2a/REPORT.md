# P10k: minority-stave conditional-template failure map

- **Ticket:** `1781066704.689.2f5f3d2a`
- **Worker:** `testbeam-laptop-3`
- **Input:** raw B-stack ROOT under `data/root/root`
- **Monte Carlo:** none

## Abstract

This study tests whether the P10g conditional-template failure on minority staves B4/B6/B8 is a model-class failure or a support/handle confound. The selected pulse table is rebuilt from raw ROOT first, then S01 empirical templates are compared with ridge, gradient-boosted trees, MLP, an early-sample 1D-CNN, and a support-gated conditional mixture under family-heldout run splits. The primary endpoint is held-out CFD20-aligned normalized-template residual MSE with run-block bootstrap 95% confidence intervals.

The winner named in `result.json` is **cnn_early_1d** with pooled run-bootstrap q-MSE `0.0389887`. The result is interpreted as `an ML/NN method beats the empirical template on the capped held-out benchmark`.

## Raw ROOT Reproduction

For every configured B-stack ROOT file, `HRDv` is baseline-subtracted with samples 0-3, four B-stack channels are extracted, and pulses with amplitude above 1000 ADC are selected. This exactly repeats the S00/S01 selected-pulse gate before any model is fit.

| quantity                        |   expected |   reproduced |   delta | pass   |
|:--------------------------------|-----------:|-------------:|--------:|:-------|
| S00/S01 selected B-stave pulses |     640737 |       640737 |       0 | True   |
| analysis selected rows          |     377362 |       377362 |       0 | True   |

## Data and Splits

Let a selected pulse be indexed by `i`, with aligned normalized waveform `y_i(t)` on relative sample grid `t in {-3,...,14}`. Two run-family folds are used: `holdout_sample_i` trains on Sample-II calibration run 64 and evaluates Sample-I analysis runs 44-57; `holdout_sample_ii` trains on Sample-I calibration runs 31-37 and 39-42 and evaluates Sample-II analysis runs 58-63 and 65. To keep the neural and tree benchmarks reproducible on the local laptop, each fold uses stratified run-stave caps for model fitting and evaluation; the uncapped raw reproduction count is still exact and is reported above.

## Methods

The traditional baseline is the frozen S01 empirical median template `m_{s,b}(t)` for stave `s` and amplitude bin `b`, with a train-fold stave median fallback when a bin has fewer than 30 training pulses:

```text
m_{s,b}(t) = median{ y_i(t) : stave_i=s, ampbin_i=b, i in train }.
```

The ridge, gradient-boosted tree, and MLP models use only transparent pulse handles available from the same selected pulse record: log amplitude, peak sample, rise width, CFD phase, tail summaries, stave, amplitude bin, saturation proxy, and current family. Run id, event id, event order, and held-out labels are excluded. The gradient-boosted model predicts a 6-component PCA compression of the waveform target and reconstructs back to sample space.

The 1D-CNN is a handle-like neural model: it convolves only early aligned samples through relative sample +1 plus the same tabular handles, then predicts the full aligned template. This makes it a stronger same-pulse shape method, but also less portable than a pure conditional template; it is therefore explicitly caveated in the systematics.

The new architecture is a support-gated mixture: it uses the gradient-boosted prediction only in support cells with at least the configured train-fold occupancy and otherwise falls back to the empirical template. This tests whether a support-aware abstention layer rescues minority-stave failures.

For method `a`, the primary residual is

```text
MSE_a(i) = |T_i|^{-1} sum_{t in T_i} (y_i(t) - yhat_{a,i}(t))^2,
Delta q_a(i) = MSE_a(i) - MSE_empirical(i).
```

The timing-transfer proxy fits a sample shift `delta` in a fixed grid by minimizing template MSE and reports `10 ns * delta`; per-run `sigma68` is `(q84-q16)/2` of those fitted shifts. Minority false-support rate is the B4/B6/B8 fraction in accepted support where a method is worse than empirical by more than the configured MSE margin.

## Run-Block Bootstrap Results

| fold              | method                  |   n_runs |   n_eval |   n_minority | q_mse_ci_text                    | q_shift_ci_text                       | timing_ci_text               |   accepted_support_fraction | false_support_ci_text               |
|:------------------|:------------------------|---------:|---------:|-------------:|:---------------------------------|:--------------------------------------|:-----------------------------|----------------------------:|:------------------------------------|
| holdout_sample_i  | cnn_early_1d            |       14 |    31253 |        10844 | 0.0493565 [0.0406059, 0.0572799] | -0.0607716 [-0.0726975, -0.0504099]   | 1.42857 [1.25, 1.69643]      |                    0.664461 | 0.0209803 [0.0169999, 0.0241091]    |
| holdout_sample_i  | ridge                   |       14 |    31253 |        10844 | 0.0507889 [0.0406508, 0.0601392] | -0.0593391 [-0.07071, -0.049632]      | 0.982143 [0.625, 1.33929]    |                    0.664461 | 0.00526514 [0.00366579, 0.0068174]  |
| holdout_sample_i  | gradient_boosted_trees  |       14 |    31253 |        10844 | 0.0545329 [0.0420601, 0.0666816] | -0.0555952 [-0.0664154, -0.0451689]   | 0.803571 [0.446429, 1.16071] |                    0.664461 | 0.00761161 [0.00526985, 0.00995564] |
| holdout_sample_i  | mlp                     |       14 |    31253 |        10844 | 0.0580153 [0.0467889, 0.0681176] | -0.0521128 [-0.0637233, -0.0415376]   | 1.25 [0.982143, 1.51786]     |                    0.664461 | 0.146658 [0.131291, 0.160452]       |
| holdout_sample_i  | support_gated_mixture   |       14 |    31253 |        10844 | 0.077274 [0.0608849, 0.0934433]  | -0.0328541 [-0.043126, -0.0231089]    | 1.33929 [0.935268, 1.69643]  |                    0.664461 | 0.00761161 [0.00533857, 0.0098314]  |
| holdout_sample_i  | shuffled_template_ridge |       14 |    31253 |        10844 | 0.104468 [0.0879309, 0.12097]    | -0.00566036 [-0.0077178, -0.00329212] | 1.96429 [1.60714, 2.41071]   |                    0.664461 | 0.050624 [0.0415015, 0.0571186]     |
| holdout_sample_i  | empirical               |       14 |    31253 |        10844 | 0.110128 [0.0944943, 0.127137]   | 0 [0, 0]                              | 1.71071 [1.42857, 2.05357]   |                    1        | 0 [0, 0]                            |
| holdout_sample_ii | cnn_early_1d            |        7 |    53128 |        31876 | 0.028621 [0.0254983, 0.0318948]  | -0.0612054 [-0.0715704, -0.053449]    | 1.25 [1.25, 1.25]            |                    0.83101  | 0.00674164 [0.00518081, 0.00845948] |
| holdout_sample_ii | gradient_boosted_trees  |        7 |    53128 |        31876 | 0.0380691 [0.0330156, 0.04318]   | -0.0517573 [-0.0606745, -0.0447665]   | 1.25 [1.25, 1.25]            |                    0.83101  | 0.129648 [0.116703, 0.146633]       |
| holdout_sample_ii | ridge                   |        7 |    53128 |        31876 | 0.0404838 [0.0366531, 0.04461]   | -0.0493426 [-0.0583302, -0.0425688]   | 1.25 [1.25, 1.25]            |                    0.83101  | 0.142053 [0.133722, 0.150326]       |
| holdout_sample_ii | mlp                     |        7 |    53128 |        31876 | 0.0406527 [0.036542, 0.0449014]  | -0.0491737 [-0.0588418, -0.0417076]   | 1.25 [1.25, 1.25]            |                    0.83101  | 0.468708 [0.421865, 0.506122]       |
| holdout_sample_ii | support_gated_mixture   |        7 |    53128 |        31876 | 0.0510013 [0.0462374, 0.0557284] | -0.0388251 [-0.0468708, -0.0330738]   | 1.25 [1.25, 1.25]            |                    0.83101  | 0.129648 [0.116794, 0.147009]       |
| holdout_sample_ii | shuffled_template_ridge |        7 |    53128 |        31876 | 0.0836877 [0.0766313, 0.0906721] | -0.00613867 [-0.0177203, 0.00256727]  | 1.96429 [1.42857, 2.32143]   |                    0.83101  | 0.62468 [0.57239, 0.662707]         |
| holdout_sample_ii | empirical               |        7 |    53128 |        31876 | 0.0898264 [0.0807797, 0.101866]  | 0 [0, 0]                              | 1.25 [1.25, 1.25]            |                    1        | 0 [0, 0]                            |

## Minority-Stave Breakdown

| fold              | stave   | method                  |   n_eval |     q_mse |   q_template_shift |   timing_sigma68_ns |   accepted_support_fraction |   minority_false_support_rate |
|:------------------|:--------|:------------------------|---------:|----------:|-------------------:|--------------------:|----------------------------:|------------------------------:|
| holdout_sample_i  | B4      | cnn_early_1d            |     6451 | 0.125432  |       -0.113333    |                5    |                    0.269416 |                    0.0350333  |
| holdout_sample_i  | B4      | ridge                   |     6451 | 0.144823  |       -0.0939418   |                6.25 |                    0.269416 |                    0.00604557 |
| holdout_sample_i  | B4      | mlp                     |     6451 | 0.158441  |       -0.0803242   |                7.5  |                    0.269416 |                    0.183227   |
| holdout_sample_i  | B4      | gradient_boosted_trees  |     6451 | 0.167997  |       -0.070768    |                6.25 |                    0.269416 |                    0.00325531 |
| holdout_sample_i  | B4      | shuffled_template_ridge |     6451 | 0.200038  |       -0.0387269   |                8.75 |                    0.269416 |                    0.0767323  |
| holdout_sample_i  | B4      | support_gated_mixture   |     6451 | 0.236131  |       -0.00263407  |                6.25 |                    0.269416 |                    0.00325531 |
| holdout_sample_i  | B4      | empirical               |     6451 | 0.238765  |        0           |                6.25 |                    1        |                    0          |
| holdout_sample_i  | B6      | cnn_early_1d            |     3094 | 0.091844  |       -0.0625279   |                3.75 |                    0.163219 |                    0.00872657 |
| holdout_sample_i  | B6      | ridge                   |     3094 | 0.106669  |       -0.0477025   |                3.75 |                    0.163219 |                    0.00711054 |
| holdout_sample_i  | B6      | mlp                     |     3094 | 0.121141  |       -0.0332305   |                6.25 |                    0.163219 |                    0.133807   |
| holdout_sample_i  | B6      | gradient_boosted_trees  |     3094 | 0.129574  |       -0.0247976   |                6.25 |                    0.163219 |                    0.0206852  |
| holdout_sample_i  | B6      | shuffled_template_ridge |     3094 | 0.151105  |       -0.00326671  |                6.25 |                    0.163219 |                    0.0316742  |
| holdout_sample_i  | B6      | empirical               |     3094 | 0.154372  |        0           |                6.25 |                    1        |                    0          |
| holdout_sample_i  | B6      | support_gated_mixture   |     3094 | 0.155134  |        0.000762306 |                6.25 |                    0.163219 |                    0.0206852  |
| holdout_sample_i  | B8      | cnn_early_1d            |     1299 | 0.103898  |       -0.0886229   |                5    |                    0        |                    0          |
| holdout_sample_i  | B8      | ridge                   |     1299 | 0.120908  |       -0.0716131   |                6.25 |                    0        |                    0          |
| holdout_sample_i  | B8      | mlp                     |     1299 | 0.12666   |       -0.0658605   |                6.25 |                    0        |                    0          |
| holdout_sample_i  | B8      | gradient_boosted_trees  |     1299 | 0.136977  |       -0.0555441   |                6.25 |                    0        |                    0          |
| holdout_sample_i  | B8      | shuffled_template_ridge |     1299 | 0.163353  |       -0.0291675   |                7.5  |                    0        |                    0          |
| holdout_sample_i  | B8      | empirical               |     1299 | 0.192521  |        0           |                6.25 |                    1        |                    0          |
| holdout_sample_i  | B8      | support_gated_mixture   |     1299 | 0.192521  |        0           |                6.25 |                    0        |                    0          |
| holdout_sample_ii | B4      | cnn_early_1d            |    16222 | 0.0335658 |       -0.0540111   |                1.25 |                    0.903403 |                    0.00573296 |
| holdout_sample_ii | B4      | gradient_boosted_trees  |    16222 | 0.0472059 |       -0.040371    |                1.25 |                    0.903403 |                    0.0816792  |
| holdout_sample_ii | B4      | mlp                     |    16222 | 0.0478481 |       -0.0397289   |                1.25 |                    0.903403 |                    0.533966   |
| holdout_sample_ii | B4      | ridge                   |    16222 | 0.0496358 |       -0.0379411   |                1.25 |                    0.903403 |                    0.119899   |
| holdout_sample_ii | B4      | support_gated_mixture   |    16222 | 0.0511712 |       -0.0364058   |                1.25 |                    0.903403 |                    0.0816792  |
| holdout_sample_ii | B4      | empirical               |    16222 | 0.0875769 |        0           |                1.25 |                    1        |                    0          |
| holdout_sample_ii | B4      | shuffled_template_ridge |    16222 | 0.0941248 |        0.00654786  |                1.25 |                    0.903403 |                    0.724633   |
| holdout_sample_ii | B6      | cnn_early_1d            |    11148 | 0.0280695 |       -0.0440656   |                1.25 |                    0.772605 |                    0.00358809 |
| holdout_sample_ii | B6      | gradient_boosted_trees  |    11148 | 0.0438206 |       -0.0283146   |                1.25 |                    0.772605 |                    0.197973   |
| holdout_sample_ii | B6      | mlp                     |    11148 | 0.0438628 |       -0.0282723   |                1.25 |                    0.772605 |                    0.501346   |
| holdout_sample_ii | B6      | ridge                   |    11148 | 0.0443917 |       -0.0277434   |                1.25 |                    0.772605 |                    0.190079   |
| holdout_sample_ii | B6      | support_gated_mixture   |    11148 | 0.0669057 |       -0.00522941  |                1.25 |                    0.772605 |                    0.197973   |
| holdout_sample_ii | B6      | empirical               |    11148 | 0.0721351 |        0           |                1.25 |                    1        |                    0          |
| holdout_sample_ii | B6      | shuffled_template_ridge |    11148 | 0.0847774 |        0.0126423   |                1.25 |                    0.772605 |                    0.643882   |
| holdout_sample_ii | B8      | cnn_early_1d            |     4506 | 0.0327242 |       -0.0497231   |                1.25 |                    0.470706 |                    0.0246338  |
| holdout_sample_ii | B8      | gradient_boosted_trees  |     4506 | 0.045955  |       -0.0364924   |                1.25 |                    0.470706 |                    0.0927652  |
| holdout_sample_ii | B8      | mlp                     |     4506 | 0.0467269 |       -0.0357204   |                1.25 |                    0.470706 |                    0.34798    |
| holdout_sample_ii | B8      | ridge                   |     4506 | 0.0486936 |       -0.0337537   |                1.25 |                    0.470706 |                    0.108522   |
| holdout_sample_ii | B8      | support_gated_mixture   |     4506 | 0.0791665 |       -0.00328088  |                1.25 |                    0.470706 |                    0.0927652  |
| holdout_sample_ii | B8      | empirical               |     4506 | 0.0824474 |        0           |                1.25 |                    1        |                    0          |
| holdout_sample_ii | B8      | shuffled_template_ridge |     4506 | 0.0869444 |        0.00449704  |                2.5  |                    0.470706 |                    0.405681   |

## Failure-Map Highlights

Rows below are the worst support cells for gradient-boosted trees relative to the empirical template. Positive deltas indicate a conditional-template failure despite using stronger handles.

| fold              | stave   | amp_region   | rise_width_region   | cfd_phase_region   | tail_shape_region   | saturation_region   | current_family   |   n_eval |   empirical_q_mse |   gradient_boosted_trees_q_mse |   gbt_minus_empirical_q_mse | best_method   |
|:------------------|:--------|:-------------|:--------------------|:-------------------|:--------------------|:--------------------|:-----------------|---------:|------------------:|-------------------------------:|----------------------------:|:--------------|
| holdout_sample_i  | B6      | a1000_1500   | rise_narrow         | phase_early        | tail_compact        | unsaturated         | high_20nA        |       46 |         1.30182   |                      1.3561    |                  0.0542819  | cnn_early_1d  |
| holdout_sample_i  | B4      | a1500_2200   | rise_narrow         | phase_early        | tail_compact        | unsaturated         | high_20nA        |       54 |         1.27324   |                      1.317     |                  0.043762   | cnn_early_1d  |
| holdout_sample_i  | B6      | a1500_2200   | rise_mid            | phase_mid          | tail_compact        | unsaturated         | high_20nA        |       74 |         0.198608  |                      0.228487  |                  0.0298788  | cnn_early_1d  |
| holdout_sample_ii | B4      | a1500_2200   | rise_narrow         | phase_early        | tail_compact        | unsaturated         | sample_ii        |       32 |         1.08058   |                      1.10792   |                  0.0273384  | cnn_early_1d  |
| holdout_sample_i  | B6      | a1500_2200   | rise_mid            | phase_early        | tail_compact        | unsaturated         | high_20nA        |      106 |         0.217028  |                      0.242063  |                  0.0250353  | cnn_early_1d  |
| holdout_sample_ii | B6      | a2200_3200   | rise_mid            | phase_late         | tail_compact        | unsaturated         | sample_ii        |      100 |         0.16478   |                      0.188627  |                  0.0238465  | cnn_early_1d  |
| holdout_sample_ii | B4      | a1500_2200   | rise_mid            | phase_mid          | tail_compact        | unsaturated         | sample_ii        |       66 |         0.306086  |                      0.327295  |                  0.0212089  | cnn_early_1d  |
| holdout_sample_ii | B6      | a2200_3200   | rise_mid            | phase_mid          | tail_compact        | unsaturated         | sample_ii        |      203 |         0.204288  |                      0.223384  |                  0.0190952  | cnn_early_1d  |
| holdout_sample_i  | B4      | a1500_2200   | rise_mid            | phase_mid          | tail_compact        | unsaturated         | high_20nA        |       91 |         0.417467  |                      0.431721  |                  0.0142534  | cnn_early_1d  |
| holdout_sample_ii | B2      | a2200_3200   | rise_mid            | phase_mid          | tail_compact        | unsaturated         | sample_ii        |      103 |         0.218085  |                      0.23133   |                  0.0132455  | cnn_early_1d  |
| holdout_sample_ii | B6      | a2200_3200   | rise_mid            | phase_early        | tail_compact        | unsaturated         | sample_ii        |      664 |         0.0777351 |                      0.0889688 |                  0.0112336  | cnn_early_1d  |
| holdout_sample_ii | B2      | a2200_3200   | rise_mid            | phase_late         | tail_compact        | unsaturated         | sample_ii        |       62 |         0.105175  |                      0.115092  |                  0.009917   | cnn_early_1d  |
| holdout_sample_i  | B6      | a2200_3200   | rise_mid            | phase_mid          | tail_compact        | unsaturated         | high_20nA        |      183 |         0.248868  |                      0.258386  |                  0.00951886 | cnn_early_1d  |
| holdout_sample_i  | B6      | a1500_2200   | rise_mid            | phase_late         | tail_compact        | unsaturated         | high_20nA        |       33 |         0.0828066 |                      0.0921355 |                  0.00932895 | cnn_early_1d  |

## Leakage and Negative Controls

| fold              | train_group     | eval_group         |   n_train_runs |   n_eval_runs | train_eval_run_overlap   |   train_eval_key_overlap | uses_run_or_event_features   | same_pulse_waveform_used_by_cnn                                                                                  |
|:------------------|:----------------|:-------------------|---------------:|--------------:|:-------------------------|-------------------------:|:-----------------------------|:-----------------------------------------------------------------------------------------------------------------|
| holdout_sample_i  | sample_ii_calib | sample_i_analysis  |              1 |            14 |                          |                        0 | False                        | early samples only, target includes full aligned template; caveated as handle-like not pure conditional template |
| holdout_sample_ii | sample_i_calib  | sample_ii_analysis |             11 |             7 |                          |                        0 | False                        | early samples only, target includes full aligned template; caveated as handle-like not pure conditional template |

The shuffled-template ridge sentinel is included in the benchmark table. It is not allowed to win; it measures how much apparent structure remains when train targets are destroyed. No model uses run id or event id as an input feature, and train/evaluation run and `(run,eventno,evt,stave)` key overlap are zero by construction.

## Systematics and Caveats

- The ROOT reproduction is uncapped and exact; the benchmark is capped by run and stave for local runtime, so small support cells should be read as a failure map rather than a final production training recipe.
- The timing result is a template-shift proxy, not a full downstream pairwise time-of-flight refit. It is appropriate for detecting harmful template phase shifts but should not replace S02/S03 timing closure.
- The 1D-CNN uses early same-pulse samples. That is useful for diagnosing whether shape handles can explain the failure, but it is less portable than amplitude/stave-only conditional templates.
- Minority false support depends on the pre-registered MSE harm margin; tightening the margin changes rates but not the sign of the worst B4/B6/B8 support cells.
- Current family and saturation boundaries are ROOT-derived proxies. They diagnose likely support mechanisms but do not prove an electronics or beam-current cause.

## Conclusion

At least one stronger method improves the capped held-out q-MSE, but the failure map and systematics should be checked before promoting it to downstream q_template consumers.

Artifacts in this directory: `result.json`, `REPORT.md`, `manifest.json`, `input_sha256.csv`, `method_summary.csv`, `by_run_metrics.csv`, `by_stave_metrics.csv`, `support_failure_map.csv`, `model_fit_meta.csv`, `leakage_checks.csv`, and `reproduction_match_table.csv`.

## Reproduce

```bash
/home/billy/anaconda3/bin/python scripts/p10k_1781066704_689_2f5f3d2a_minority_stave_failure_map.py --config configs/p10k_1781066704_689_2f5f3d2a_minority_stave_failure_map.yaml
```
