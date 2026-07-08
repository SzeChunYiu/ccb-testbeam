# S02l: dynamic-only timing quarantine boundary

Ticket `1781081167.631.051f65df`. Worker `testbeam-laptop-2`.

## Abstract

This study asks whether pulses admitted only by the dynamic-range selector can be safely quarantined, or whether such an abstention erodes legitimate timing support.  The analysis starts from raw B-stack ROOT, reproduces the S00c selector count including the `dynamic_only` count, and then performs a leave-one-run-out Sample-II timing benchmark.  The compared methods are a strong traditional median-first template/timewalk refit, a transparent dynamic-boundary traditional quarantine proxy, ridge regression, histogram gradient-boosted trees, MLP, 1D-CNN, and a new gated proxy network.  Confidence intervals are run-block bootstraps across held-out runs.

## Raw ROOT Reproduction

The script reads `data/root/root` directly before model fitting.  The accepted selector is

`max(HRDv - median(HRDv[0:4])) > 1000 ADC`,

and the dynamic-only comparator is

`max(HRDv) - min(HRDv) > 1000 ADC` while the median-first selector is false.

| quantity                           |   report_value |   reproduced |   delta |   tolerance | pass   |
|:-----------------------------------|---------------:|-------------:|--------:|------------:|:-------|
| total selected B-stave pulses      |         640737 |       640737 |       0 |           0 | True   |
| sample_ii_analysis selected_pulses |         125096 |       125096 |       0 |           0 | True   |
| sample_ii_analysis B2              |          88213 |        88213 |       0 |           0 | True   |
| sample_ii_analysis B4              |          21229 |        21229 |       0 |           0 | True   |
| sample_ii_analysis B6              |          11148 |        11148 |       0 |           0 | True   |
| sample_ii_analysis B8              |           4506 |         4506 |       0 |           0 | True   |
| dynamic_only                       |          65636 |        65636 |       0 |           0 | True   |

Reference timing anchors were also rebuilt from raw-derived pulses:

| quantity                      |   heldout_run |   reproduced_sigma68_ns |   reference_sigma68_ns |    delta_ns | pass   |
|:------------------------------|--------------:|------------------------:|-----------------------:|------------:|:-------|
| S02b global-template timewalk |            65 |                 1.63542 |                1.63542 | 2.20047e-09 | True   |
| S02b binned-template timewalk |            65 |                 3.4037  |                3.4037  | 2.08709e-10 | True   |

## Estimands and Equations

For event `e`, method `m`, and downstream staves `a,b in {B4,B6,B8}`, the paired timing residual is

`r_ab(e;m) = [t_a(e;m) - z_a/v] - [t_b(e;m) - z_b/v]`,

where `z` is the 2 cm stave coordinate and `1/v = 0.078 ns/cm`.  The robust width is

`sigma68(m) = (Q_0.84(r_ab) - Q_0.16(r_ab)) / 2`.

The full RMS and tail metric are

`RMS(m) = sqrt(mean((r_ab - mean(r_ab))^2))`,

`T_5(m) = mean(|r_ab - median(r_ab)| > 5 ns)`.

The quarantine lift is defined as

`L(m) = sigma68(traditional_global_no_proxy) - sigma68(m)`;

positive lift means the method narrows the downstream timing closure relative to the strong traditional baseline.

## Split and Features

Runs `58, 59, 60, 61, 62, 63, 65` are held out one at a time.  Fold-local preprocessing never sees the held-out run.  Features are pre-label ROOT/run summaries and downstream stave indicators; event ids, pair residuals, target timing labels, and held-out rows are excluded from fitting.

Pre-label run covariates:

|   run |   current_nA |   trigger_entry_density |   entries_per_eventno |   selected_multiplicity_per_event |   downstream_allhit_fraction |
|------:|-------------:|------------------------:|----------------------:|----------------------------------:|-----------------------------:|
|    58 |           20 |                0.997808 |              0.997808 |                          0.49152  |                   0.00213819 |
|    59 |           20 |                1        |              1        |                          0.505331 |                   0.0180365  |
|    60 |           20 |                1        |              1        |                          0.472057 |                   0.0223984  |
|    61 |           20 |                0.999945 |              0.999945 |                          0.519091 |                   0.0255372  |
|    62 |           20 |                1        |              1        |                          0.507902 |                   0.0214719  |
|    63 |           20 |                0.999973 |              0.999973 |                          0.508156 |                   0.0099919  |
|    65 |           20 |                1        |              1        |                          0.339319 |                   0.00171768 |

## Methods

The strong traditional method is `traditional_global_no_proxy`, the established global template/timewalk refit without dynamic quarantine.  The primary traditional quarantine comparator is `traditional_proxy_dynamic_boundary`, which uses trigger-density, selected-multiplicity, and all-hit topology covariates as a matched dynamic-boundary abstention/refit proxy.  Additional traditional nuisance refits are included as systematics.

ML/NN models use the same allowed pre-label feature family:

- `ml_ridge_all_root_proxies`: standardized ridge regression with grouped-run CV over alpha.
- `ml_hgb_all_root_proxies`: histogram gradient-boosted trees.
- `ml_mlp_all_root_proxies`: feed-forward MLP.
- `ml_cnn1d_proxy_all_root_proxies`: compact 1D-CNN over the ordered proxy vector.
- `ml_gated_proxy_all_root_proxies`: new gated architecture combining linear and nonlinear branches.

Model audit:

|   heldout_run | model       | proxy_family     |   n_train_pulses |   n_features | feature_policy                                                                                                                                       |
|--------------:|:------------|:-----------------|-----------------:|-------------:|:-----------------------------------------------------------------------------------------------------------------------------------------------------|
|            58 | ridge       | all_root_proxies |            11241 |           10 | ROOT-only run/event proxies plus downstream stave indicator; excludes waveform samples, event id, downstream timing labels, and held-out target rows |
|            58 | hgb         | all_root_proxies |            11241 |           10 | ROOT-only run/event proxies plus downstream stave indicator; excludes waveform samples, event id, downstream timing labels, and held-out target rows |
|            58 | mlp         | all_root_proxies |            11241 |           10 | ROOT-only run/event proxies plus downstream stave indicator; excludes waveform samples, event id, downstream timing labels, and held-out target rows |
|            58 | cnn1d_proxy | all_root_proxies |            11241 |           10 | ROOT-only run/event proxies plus downstream stave indicator; excludes waveform samples, event id, downstream timing labels, and held-out target rows |
|            58 | gated_proxy | all_root_proxies |            11241 |           10 | ROOT-only run/event proxies plus downstream stave indicator; excludes waveform samples, event id, downstream timing labels, and held-out target rows |
|            59 | ridge       | all_root_proxies |             9171 |           10 | ROOT-only run/event proxies plus downstream stave indicator; excludes waveform samples, event id, downstream timing labels, and held-out target rows |
|            59 | hgb         | all_root_proxies |             9171 |           10 | ROOT-only run/event proxies plus downstream stave indicator; excludes waveform samples, event id, downstream timing labels, and held-out target rows |
|            59 | mlp         | all_root_proxies |             9171 |           10 | ROOT-only run/event proxies plus downstream stave indicator; excludes waveform samples, event id, downstream timing labels, and held-out target rows |
|            59 | cnn1d_proxy | all_root_proxies |             9171 |           10 | ROOT-only run/event proxies plus downstream stave indicator; excludes waveform samples, event id, downstream timing labels, and held-out target rows |
|            59 | gated_proxy | all_root_proxies |             9171 |           10 | ROOT-only run/event proxies plus downstream stave indicator; excludes waveform samples, event id, downstream timing labels, and held-out target rows |
|            60 | ridge       | all_root_proxies |             9036 |           10 | ROOT-only run/event proxies plus downstream stave indicator; excludes waveform samples, event id, downstream timing labels, and held-out target rows |
|            60 | hgb         | all_root_proxies |             9036 |           10 | ROOT-only run/event proxies plus downstream stave indicator; excludes waveform samples, event id, downstream timing labels, and held-out target rows |
|            60 | mlp         | all_root_proxies |             9036 |           10 | ROOT-only run/event proxies plus downstream stave indicator; excludes waveform samples, event id, downstream timing labels, and held-out target rows |
|            60 | cnn1d_proxy | all_root_proxies |             9036 |           10 | ROOT-only run/event proxies plus downstream stave indicator; excludes waveform samples, event id, downstream timing labels, and held-out target rows |
|            60 | gated_proxy | all_root_proxies |             9036 |           10 | ROOT-only run/event proxies plus downstream stave indicator; excludes waveform samples, event id, downstream timing labels, and held-out target rows |
|            61 | ridge       | all_root_proxies |             8661 |           10 | ROOT-only run/event proxies plus downstream stave indicator; excludes waveform samples, event id, downstream timing labels, and held-out target rows |
|            61 | hgb         | all_root_proxies |             8661 |           10 | ROOT-only run/event proxies plus downstream stave indicator; excludes waveform samples, event id, downstream timing labels, and held-out target rows |
|            61 | mlp         | all_root_proxies |             8661 |           10 | ROOT-only run/event proxies plus downstream stave indicator; excludes waveform samples, event id, downstream timing labels, and held-out target rows |
|            61 | cnn1d_proxy | all_root_proxies |             8661 |           10 | ROOT-only run/event proxies plus downstream stave indicator; excludes waveform samples, event id, downstream timing labels, and held-out target rows |
|            61 | gated_proxy | all_root_proxies |             8661 |           10 | ROOT-only run/event proxies plus downstream stave indicator; excludes waveform samples, event id, downstream timing labels, and held-out target rows |
|            62 | ridge       | all_root_proxies |             9039 |           10 | ROOT-only run/event proxies plus downstream stave indicator; excludes waveform samples, event id, downstream timing labels, and held-out target rows |
|            62 | hgb         | all_root_proxies |             9039 |           10 | ROOT-only run/event proxies plus downstream stave indicator; excludes waveform samples, event id, downstream timing labels, and held-out target rows |
|            62 | mlp         | all_root_proxies |             9039 |           10 | ROOT-only run/event proxies plus downstream stave indicator; excludes waveform samples, event id, downstream timing labels, and held-out target rows |
|            62 | cnn1d_proxy | all_root_proxies |             9039 |           10 | ROOT-only run/event proxies plus downstream stave indicator; excludes waveform samples, event id, downstream timing labels, and held-out target rows |
|            62 | gated_proxy | all_root_proxies |             9039 |           10 | ROOT-only run/event proxies plus downstream stave indicator; excludes waveform samples, event id, downstream timing labels, and held-out target rows |
|            63 | ridge       | all_root_proxies |            10350 |           10 | ROOT-only run/event proxies plus downstream stave indicator; excludes waveform samples, event id, downstream timing labels, and held-out target rows |
|            63 | hgb         | all_root_proxies |            10350 |           10 | ROOT-only run/event proxies plus downstream stave indicator; excludes waveform samples, event id, downstream timing labels, and held-out target rows |
|            63 | mlp         | all_root_proxies |            10350 |           10 | ROOT-only run/event proxies plus downstream stave indicator; excludes waveform samples, event id, downstream timing labels, and held-out target rows |
|            63 | cnn1d_proxy | all_root_proxies |            10350 |           10 | ROOT-only run/event proxies plus downstream stave indicator; excludes waveform samples, event id, downstream timing labels, and held-out target rows |
|            63 | gated_proxy | all_root_proxies |            10350 |           10 | ROOT-only run/event proxies plus downstream stave indicator; excludes waveform samples, event id, downstream timing labels, and held-out target rows |
|            65 | ridge       | all_root_proxies |            11262 |           10 | ROOT-only run/event proxies plus downstream stave indicator; excludes waveform samples, event id, downstream timing labels, and held-out target rows |
|            65 | hgb         | all_root_proxies |            11262 |           10 | ROOT-only run/event proxies plus downstream stave indicator; excludes waveform samples, event id, downstream timing labels, and held-out target rows |
|            65 | mlp         | all_root_proxies |            11262 |           10 | ROOT-only run/event proxies plus downstream stave indicator; excludes waveform samples, event id, downstream timing labels, and held-out target rows |
|            65 | cnn1d_proxy | all_root_proxies |            11262 |           10 | ROOT-only run/event proxies plus downstream stave indicator; excludes waveform samples, event id, downstream timing labels, and held-out target rows |
|            65 | gated_proxy | all_root_proxies |            11262 |           10 | ROOT-only run/event proxies plus downstream stave indicator; excludes waveform samples, event id, downstream timing labels, and held-out target rows |

## Results

Run-block benchmark:

| method                             | family            |   mean_sigma68_ns |   ci_low |   ci_high |   delta_vs_traditional_ns |   delta_ci_low |   delta_ci_high |   mean_full_rms_ns |   mean_tail_frac_abs_gt5ns |
|:-----------------------------------|:------------------|------------------:|---------:|----------:|--------------------------:|---------------:|----------------:|-------------------:|---------------------------:|
| ml_gated_proxy_all_root_proxies    | ml                |           1.2874  |  1.21972 |   1.34948 |                 -0.367762 |   -0.547248    |       -0.2349   |            2.26035 |                  0.0132062 |
| ml_cnn1d_proxy_all_root_proxies    | ml                |           1.33864 |  1.25927 |   1.41369 |                 -0.316523 |   -0.531864    |       -0.156785 |            2.312   |                  0.0138818 |
| ml_hgb_all_root_proxies            | ml                |           1.36421 |  1.28808 |   1.46253 |                 -0.290954 |   -0.502834    |       -0.101939 |            2.29144 |                  0.0139153 |
| ml_ridge_all_root_proxies          | ml                |           1.37114 |  1.32771 |   1.42492 |                 -0.284025 |   -0.509746    |       -0.135788 |            2.3163  |                  0.0139227 |
| ml_mlp_all_root_proxies            | ml                |           1.44857 |  1.25582 |   1.72335 |                 -0.206599 |   -0.526871    |        0.149767 |            2.35091 |                  0.0146906 |
| traditional_global_no_proxy        | traditional       |           1.65516 |  1.53023 |   1.8471  |                  0        |    0           |        0        |            2.46445 |                  0.0152938 |
| traditional_binned_no_proxy        | traditional       |           3.14849 |  2.79819 |   3.47813 |                  1.49333  |    1.11945     |        1.86745  |            3.6679  |                  0.122116  |
| traditional_proxy_baseline_rate    | traditional_proxy |           5.09628 |  1.56025 |  11.9713  |                  3.44112  |   -0.0049703   |       10.33     |            5.47418 |                  0.0642764 |
| traditional_proxy_dynamic_boundary | traditional_proxy |           5.18079 |  1.67862 |  11.4538  |                  3.52563  |   -0.0155401   |        9.80358  |            5.48366 |                  0.111961  |
| traditional_proxy_all_root_proxies | traditional_proxy |           5.18079 |  1.65787 |  11.3321  |                  3.52563  |   -0.000547911 |        9.75949  |            5.48366 |                  0.111961  |

Dynamic quarantine ranking:

| method                                   | policy                                                 |   mean_sigma68_ns |   ci_low |   ci_high |   lift_vs_traditional_ns |   lift_ci_low |   lift_ci_high |
|:-----------------------------------------|:-------------------------------------------------------|------------------:|---------:|----------:|-------------------------:|--------------:|---------------:|
| ml_gated_proxy_all_root_proxies          | run-heldout calibrated selector-risk timing-tail refit |           1.2874  |  1.21972 |   1.34948 |               0.367762   |    0.2349     |    0.547248    |
| ml_cnn1d_proxy_all_root_proxies          | run-heldout calibrated selector-risk timing-tail refit |           1.33864 |  1.25927 |   1.41369 |               0.316523   |    0.156785   |    0.531864    |
| ml_hgb_all_root_proxies                  | run-heldout calibrated selector-risk timing-tail refit |           1.36421 |  1.28808 |   1.46253 |               0.290954   |    0.101939   |    0.502834    |
| ml_ridge_all_root_proxies                | run-heldout calibrated selector-risk timing-tail refit |           1.37114 |  1.32771 |   1.42492 |               0.284025   |    0.135788   |    0.509746    |
| ml_mlp_all_root_proxies                  | run-heldout calibrated selector-risk timing-tail refit |           1.44857 |  1.25582 |   1.72335 |               0.206599   |   -0.149767   |    0.526871    |
| ml_mlp_all_root_proxies_shuffled         | negative control: shuffled residual target             |           1.62757 |  1.51799 |   1.78126 |               0.0275946  |   -0.0077603  |    0.0725274   |
| ml_gated_proxy_all_root_proxies_shuffled | negative control: shuffled residual target             |           1.63848 |  1.52068 |   1.79301 |               0.016682   |   -0.0195321  |    0.0503875   |
| ml_ridge_all_root_proxies_shuffled       | negative control: shuffled residual target             |           1.64095 |  1.53053 |   1.80232 |               0.014212   |   -0.0100289  |    0.0463926   |
| traditional_global_no_proxy              | median-first timing refit, no dynamic quarantine       |           1.65516 |  1.53023 |   1.8471  |               0          |   -0          |   -0           |
| ml_cnn1d_proxy_all_root_proxies_shuffled | negative control: shuffled residual target             |           1.65629 |  1.53075 |   1.83269 |              -0.00112352 |   -0.00231494 |   -3.57297e-05 |
| ml_hgb_all_root_proxies_shuffled         | negative control: shuffled residual target             |           1.66461 |  1.53434 |   1.86946 |              -0.00944391 |   -0.0218147  |    0.00165607  |
| traditional_binned_no_proxy              | traditional nuisance refit comparator                  |           3.14849 |  2.79819 |   3.47813 |              -1.49333    |   -1.86745    |   -1.11945     |
| traditional_proxy_baseline_rate          | traditional nuisance refit comparator                  |           5.09628 |  1.56025 |  11.9713  |              -3.44112    |  -10.33       |    0.0049703   |
| traditional_proxy_dynamic_boundary       | transparent matched dynamic-boundary abstention/refit  |           5.18079 |  1.67862 |  11.4538  |              -3.52563    |   -9.80358    |    0.0155401   |
| traditional_proxy_all_root_proxies       | traditional nuisance refit comparator                  |           5.18079 |  1.65787 |  11.3321  |              -3.52563    |   -9.75949    |    0.000547911 |

Per-run event-bootstrap metrics:

|   heldout_run | method                             | family            |   sigma68_ns |   ci_low |   ci_high |   full_rms_ns |   tail_frac_abs_gt5ns |
|--------------:|:-----------------------------------|:------------------|-------------:|---------:|----------:|--------------:|----------------------:|
|            58 | ml_ridge_all_root_proxies          | ml                |      1.35072 |  1.1515  |   1.52043 |       2.78318 |            0.0182648  |
|            58 | ml_cnn1d_proxy_all_root_proxies    | ml                |      1.36338 |  1.18465 |   1.61554 |       2.81146 |            0.0228311  |
|            58 | ml_gated_proxy_all_root_proxies    | ml                |      1.42029 |  1.17977 |   1.756   |       2.71659 |            0.0228311  |
|            58 | traditional_global_no_proxy        | traditional       |      1.52279 |  1.28673 |   1.8531  |       2.75002 |            0.0228311  |
|            58 | ml_hgb_all_root_proxies            | ml                |      1.62688 |  1.43317 |   1.81974 |       2.91217 |            0.0228311  |
|            58 | ml_mlp_all_root_proxies            | ml                |      2.26076 |  2.04304 |   2.43921 |       3.21491 |            0.0319635  |
|            58 | traditional_binned_no_proxy        | traditional       |      3.63484 |  3.21937 |   4.08849 |       4.61474 |            0.191781   |
|            58 | traditional_proxy_dynamic_boundary | traditional_proxy |     23.4087  | 23.2122  |  23.5971  |      21.6942  |            0.365297   |
|            58 | traditional_proxy_all_root_proxies | traditional_proxy |     23.4087  | 23.2194  |  23.6066  |      21.6942  |            0.365297   |
|            58 | traditional_proxy_baseline_rate    | traditional_proxy |     25.6288  | 25.473   |  25.8165  |      23.8418  |            0.365297   |
|            59 | ml_cnn1d_proxy_all_root_proxies    | ml                |      1.23277 |  1.16738 |   1.28964 |       2.3034  |            0.0117955  |
|            59 | ml_mlp_all_root_proxies            | ml                |      1.29719 |  1.22791 |   1.3775  |       2.33537 |            0.0122324  |
|            59 | ml_hgb_all_root_proxies            | ml                |      1.30322 |  1.22739 |   1.38283 |       2.31599 |            0.0126693  |
|            59 | ml_gated_proxy_all_root_proxies    | ml                |      1.32477 |  1.26383 |   1.40303 |       2.33542 |            0.0122324  |
|            59 | ml_ridge_all_root_proxies          | ml                |      1.36017 |  1.30274 |   1.43997 |       2.35102 |            0.0126693  |
|            59 | traditional_proxy_baseline_rate    | traditional_proxy |      1.59401 |  1.53641 |   1.64492 |       2.48192 |            0.0126693  |
|            59 | traditional_global_no_proxy        | traditional       |      1.59676 |  1.55008 |   1.6526  |       2.48616 |            0.0126693  |
|            59 | traditional_proxy_dynamic_boundary | traditional_proxy |      1.6297  |  1.57029 |   1.68519 |       2.49493 |            0.013543   |
|            59 | traditional_proxy_all_root_proxies | traditional_proxy |      1.6297  |  1.57062 |   1.68216 |       2.49493 |            0.013543   |
|            59 | traditional_binned_no_proxy        | traditional       |      3.63793 |  3.48602 |   3.76966 |       4.00546 |            0.158148   |
|            60 | ml_mlp_all_root_proxies            | ml                |      1.16556 |  1.10997 |   1.22381 |       2.1336  |            0.0107261  |
|            60 | ml_gated_proxy_all_root_proxies    | ml                |      1.22646 |  1.15171 |   1.29664 |       2.16364 |            0.0107261  |
|            60 | ml_hgb_all_root_proxies            | ml                |      1.32654 |  1.25196 |   1.40297 |       2.21295 |            0.0103135  |
|            60 | traditional_proxy_all_root_proxies | traditional_proxy |      1.35265 |  1.30218 |   1.39909 |       2.2095  |            0.0107261  |
|            60 | traditional_proxy_dynamic_boundary | traditional_proxy |      1.35265 |  1.31033 |   1.40252 |       2.2095  |            0.0107261  |
|            60 | ml_ridge_all_root_proxies          | ml                |      1.41665 |  1.35738 |   1.48622 |       2.26218 |            0.0103135  |
|            60 | ml_cnn1d_proxy_all_root_proxies    | ml                |      1.44309 |  1.37507 |   1.52729 |       2.26347 |            0.0107261  |
|            60 | traditional_proxy_baseline_rate    | traditional_proxy |      1.46242 |  1.42106 |   1.51019 |       2.26615 |            0.0107261  |
|            60 | traditional_global_no_proxy        | traditional       |      1.4719  |  1.4265  |   1.52502 |       2.27149 |            0.0107261  |
|            60 | traditional_binned_no_proxy        | traditional       |      2.12741 |  2.03974 |   2.19892 |       2.5748  |            0.0383663  |
|            61 | ml_cnn1d_proxy_all_root_proxies    | ml                |      1.27377 |  1.22468 |   1.3337  |       2.49322 |            0.0160772  |
|            61 | ml_ridge_all_root_proxies          | ml                |      1.277   |  1.21043 |   1.3349  |       2.4529  |            0.0150054  |
|            61 | ml_mlp_all_root_proxies            | ml                |      1.28196 |  1.22682 |   1.3478  |       2.45571 |            0.0150054  |
|            61 | ml_hgb_all_root_proxies            | ml                |      1.30288 |  1.25435 |   1.38421 |       2.47648 |            0.0153626  |
|            61 | ml_gated_proxy_all_root_proxies    | ml                |      1.30764 |  1.25323 |   1.36058 |       2.46008 |            0.0146481  |
|            61 | traditional_proxy_dynamic_boundary | traditional_proxy |      2.1821  |  2.08301 |   2.26822 |       2.93649 |            0.0271526  |
|            61 | traditional_proxy_all_root_proxies | traditional_proxy |      2.1821  |  2.09767 |   2.26284 |       2.93649 |            0.0271526  |
|            61 | traditional_proxy_baseline_rate    | traditional_proxy |      2.18716 |  2.08175 |   2.27819 |       2.93562 |            0.0275098  |
|            61 | traditional_global_no_proxy        | traditional       |      2.18842 |  2.10008 |   2.26784 |       2.93618 |            0.0275098  |
|            61 | traditional_binned_no_proxy        | traditional       |      3.06904 |  2.93762 |   3.19482 |       3.72776 |            0.110397   |
|            62 | ml_hgb_all_root_proxies            | ml                |      1.25112 |  1.17903 |   1.3146  |       2.30645 |            0.00991326 |
|            62 | ml_ridge_all_root_proxies          | ml                |      1.33562 |  1.27642 |   1.39366 |       2.35998 |            0.0107394  |
|            62 | ml_gated_proxy_all_root_proxies    | ml                |      1.34376 |  1.29354 |   1.42058 |       2.36083 |            0.0107394  |
|            62 | ml_cnn1d_proxy_all_root_proxies    | ml                |      1.40103 |  1.34236 |   1.4522  |       2.37755 |            0.0103263  |
|            62 | ml_mlp_all_root_proxies            | ml                |      1.52073 |  1.4543  |   1.5876  |       2.42747 |            0.0107394  |
|            62 | traditional_proxy_all_root_proxies | traditional_proxy |      1.57629 |  1.52458 |   1.6333  |       2.46912 |            0.0111524  |
|            62 | traditional_proxy_dynamic_boundary | traditional_proxy |      1.57629 |  1.52408 |   1.62222 |       2.46912 |            0.0111524  |
|            62 | traditional_proxy_baseline_rate    | traditional_proxy |      1.62774 |  1.57448 |   1.67362 |       2.49613 |            0.0115655  |
|            62 | traditional_global_no_proxy        | traditional       |      1.62995 |  1.58092 |   1.67255 |       2.50074 |            0.0111524  |
|            62 | traditional_binned_no_proxy        | traditional       |      2.962   |  2.82935 |   3.09788 |       3.44045 |            0.0912846  |
|            63 | ml_gated_proxy_all_root_proxies    | ml                |      1.12958 |  1.03476 |   1.27085 |       2.33618 |            0.0162162  |
|            63 | ml_cnn1d_proxy_all_root_proxies    | ml                |      1.16704 |  1.02822 |   1.2719  |       2.35615 |            0.0153153  |
|            63 | ml_mlp_all_root_proxies            | ml                |      1.27495 |  1.1427  |   1.35063 |       2.36971 |            0.0171171  |
|            63 | ml_hgb_all_root_proxies            | ml                |      1.29105 |  1.17848 |   1.40151 |       2.37341 |            0.0162162  |
|            63 | ml_ridge_all_root_proxies          | ml                |      1.35337 |  1.27128 |   1.4535  |       2.42486 |            0.0153153  |
|            63 | traditional_proxy_baseline_rate    | traditional_proxy |      1.53855 |  1.46733 |   1.59964 |       2.53171 |            0.0171171  |
|            63 | traditional_global_no_proxy        | traditional       |      1.54092 |  1.48468 |   1.61275 |       2.53459 |            0.0171171  |
|            63 | traditional_proxy_dynamic_boundary | traditional_proxy |      1.8826  |  1.79945 |   1.95247 |       2.70696 |            0.0225225  |
|            63 | traditional_proxy_all_root_proxies | traditional_proxy |      1.8826  |  1.80313 |   1.95085 |       2.70696 |            0.0225225  |
|            63 | traditional_binned_no_proxy        | traditional       |      3.20453 |  2.99604 |   3.40707 |       3.58591 |            0.123423   |
|            65 | ml_gated_proxy_all_root_proxies    | ml                |      1.25931 |  1.08706 |   1.52209 |       1.44967 |            0.00505051 |
|            65 | ml_mlp_all_root_proxies            | ml                |      1.3388  |  1.10154 |   1.55497 |       1.51957 |            0.00505051 |
|            65 | ml_hgb_all_root_proxies            | ml                |      1.44777 |  1.16438 |   1.59304 |       1.44264 |            0.010101   |
|            65 | ml_cnn1d_proxy_all_root_proxies    | ml                |      1.4894  |  1.28973 |   1.69391 |       1.57876 |            0.010101   |
|            65 | ml_ridge_all_root_proxies          | ml                |      1.50445 |  1.3525  |   1.7317  |       1.57998 |            0.0151515  |
|            65 | traditional_proxy_baseline_rate    | traditional_proxy |      1.63527 |  1.44676 |   1.89203 |       1.76599 |            0.00505051 |
|            65 | traditional_global_no_proxy        | traditional       |      1.63542 |  1.46759 |   1.93419 |       1.77195 |            0.00505051 |
|            65 | traditional_binned_no_proxy        | traditional       |      3.4037  |  2.8627  |   4.1408  |       3.72618 |            0.141414   |
|            65 | traditional_proxy_dynamic_boundary | traditional_proxy |      4.23354 |  3.9903  |   4.43655 |       3.87439 |            0.333333   |
|            65 | traditional_proxy_all_root_proxies | traditional_proxy |      4.23354 |  3.98959 |   4.43779 |       3.87439 |            0.333333   |

ML/NN-only ranking:

| method                          |   mean_sigma68_ns |   ci_low |   ci_high |   delta_vs_traditional_ns |   delta_ci_low |   delta_ci_high |
|:--------------------------------|------------------:|---------:|----------:|--------------------------:|---------------:|----------------:|
| ml_gated_proxy_all_root_proxies |           1.2874  |  1.21972 |   1.34948 |                 -0.367762 |      -0.547248 |       -0.2349   |
| ml_cnn1d_proxy_all_root_proxies |           1.33864 |  1.25927 |   1.41369 |                 -0.316523 |      -0.531864 |       -0.156785 |
| ml_hgb_all_root_proxies         |           1.36421 |  1.28808 |   1.46253 |                 -0.290954 |      -0.502834 |       -0.101939 |
| ml_ridge_all_root_proxies       |           1.37114 |  1.32771 |   1.42492 |                 -0.284025 |      -0.509746 |       -0.135788 |
| ml_mlp_all_root_proxies         |           1.44857 |  1.25582 |   1.72335 |                 -0.206599 |      -0.526871 |        0.149767 |

Traditional/systematic ranking:

| method                             | family            |   mean_sigma68_ns |   ci_low |   ci_high |   delta_vs_traditional_ns |   delta_ci_low |   delta_ci_high |
|:-----------------------------------|:------------------|------------------:|---------:|----------:|--------------------------:|---------------:|----------------:|
| traditional_global_no_proxy        | traditional       |           1.65516 |  1.53023 |   1.8471  |                   0       |    0           |         0       |
| traditional_binned_no_proxy        | traditional       |           3.14849 |  2.79819 |   3.47813 |                   1.49333 |    1.11945     |         1.86745 |
| traditional_proxy_baseline_rate    | traditional_proxy |           5.09628 |  1.56025 |  11.9713  |                   3.44112 |   -0.0049703   |        10.33    |
| traditional_proxy_dynamic_boundary | traditional_proxy |           5.18079 |  1.67862 |  11.4538  |                   3.52563 |   -0.0155401   |         9.80358 |
| traditional_proxy_all_root_proxies | traditional_proxy |           5.18079 |  1.65787 |  11.3321  |                   3.52563 |   -0.000547911 |         9.75949 |

Retained-fraction and support-shift ledger:

| method                                   | family                  |   mean_retained_fraction |   min_retained_fraction |   support_shift_energy_distance_adc |   mean_full_rms_ns |   mean_tail_frac_abs_gt5ns |
|:-----------------------------------------|:------------------------|-------------------------:|------------------------:|------------------------------------:|-------------------:|---------------------------:|
| ml_cnn1d_proxy_all_root_proxies          | ml                      |                        1 |                       1 |                                   0 |            2.312   |                  0.0138818 |
| ml_gated_proxy_all_root_proxies          | ml                      |                        1 |                       1 |                                   0 |            2.26035 |                  0.0132062 |
| ml_hgb_all_root_proxies                  | ml                      |                        1 |                       1 |                                   0 |            2.29144 |                  0.0139153 |
| ml_mlp_all_root_proxies                  | ml                      |                        1 |                       1 |                                   0 |            2.35091 |                  0.0146906 |
| ml_ridge_all_root_proxies                | ml                      |                        1 |                       1 |                                   0 |            2.3163  |                  0.0139227 |
| ml_cnn1d_proxy_all_root_proxies_shuffled | shuffled_target_control |                        1 |                       1 |                                   0 |            2.46564 |                  0.0153562 |
| ml_gated_proxy_all_root_proxies_shuffled | shuffled_target_control |                        1 |                       1 |                                   0 |            2.46082 |                  0.0148661 |
| ml_hgb_all_root_proxies_shuffled         | shuffled_target_control |                        1 |                       1 |                                   0 |            2.47674 |                  0.0158235 |
| ml_mlp_all_root_proxies_shuffled         | shuffled_target_control |                        1 |                       1 |                                   0 |            2.44767 |                  0.0147437 |
| ml_ridge_all_root_proxies_shuffled       | shuffled_target_control |                        1 |                       1 |                                   0 |            2.45547 |                  0.0149365 |
| traditional_binned_no_proxy              | traditional             |                        1 |                       1 |                                   0 |            3.6679  |                  0.122116  |
| traditional_global_no_proxy              | traditional             |                        1 |                       1 |                                   0 |            2.46445 |                  0.0152938 |
| traditional_proxy_all_root_proxies       | traditional_proxy       |                        1 |                       1 |                                   0 |            5.48366 |                  0.111961  |
| traditional_proxy_baseline_rate          | traditional_proxy       |                        1 |                       1 |                                   0 |            5.47418 |                  0.0642764 |
| traditional_proxy_dynamic_boundary       | traditional_proxy       |                        1 |                       1 |                                   0 |            5.48366 |                  0.111961  |

## Controls, Systematics, and Caveats

Leakage ledger:

|   heldout_run | check                                                     |      value | pass   |
|--------------:|:----------------------------------------------------------|-----------:|:-------|
|            58 | train_heldout_run_overlap                                 |  0         | True   |
|            58 | train_heldout_event_id_overlap                            |  0         | True   |
|            58 | covariate_basis_contains_run_one_hot                      |  0         | True   |
|            58 | covariates_derived_before_timing_labels                   |  1         | True   |
|            58 | ml_features_exclude_waveform_event_id_downstream_labels   |  1         | True   |
|            58 | final_fit_train_rows_only                                 |  1         | True   |
|            58 | shuffled_target_no_better:ml_mlp_all_root_proxies         | -0.792324  | False  |
|            58 | shuffled_target_no_better:ml_gated_proxy_all_root_proxies |  0.0854508 | True   |
|            58 | shuffled_target_no_better:ml_cnn1d_proxy_all_root_proxies |  0.159912  | True   |
|            58 | shuffled_target_no_better:ml_hgb_all_root_proxies         | -0.0924582 | False  |
|            58 | shuffled_target_no_better:ml_ridge_all_root_proxies       |  0.19716   | True   |
|            59 | train_heldout_run_overlap                                 |  0         | True   |
|            59 | train_heldout_event_id_overlap                            |  0         | True   |
|            59 | covariate_basis_contains_run_one_hot                      |  0         | True   |
|            59 | covariates_derived_before_timing_labels                   |  1         | True   |
|            59 | ml_features_exclude_waveform_event_id_downstream_labels   |  1         | True   |
|            59 | final_fit_train_rows_only                                 |  1         | True   |
|            59 | shuffled_target_no_better:ml_gated_proxy_all_root_proxies |  0.217793  | True   |
|            59 | shuffled_target_no_better:ml_ridge_all_root_proxies       |  0.231028  | True   |
|            59 | shuffled_target_no_better:ml_cnn1d_proxy_all_root_proxies |  0.366612  | True   |
|            59 | shuffled_target_no_better:ml_hgb_all_root_proxies         |  0.302691  | True   |
|            59 | shuffled_target_no_better:ml_mlp_all_root_proxies         |  0.318821  | True   |
|            60 | train_heldout_run_overlap                                 |  0         | True   |
|            60 | train_heldout_event_id_overlap                            |  0         | True   |
|            60 | covariate_basis_contains_run_one_hot                      |  0         | True   |
|            60 | covariates_derived_before_timing_labels                   |  1         | True   |
|            60 | ml_features_exclude_waveform_event_id_downstream_labels   |  1         | True   |
|            60 | final_fit_train_rows_only                                 |  1         | True   |
|            60 | shuffled_target_no_better:ml_gated_proxy_all_root_proxies |  0.208686  | True   |
|            60 | shuffled_target_no_better:ml_ridge_all_root_proxies       |  0.0213654 | True   |
|            60 | shuffled_target_no_better:ml_mlp_all_root_proxies         |  0.281817  | True   |
|            60 | shuffled_target_no_better:ml_hgb_all_root_proxies         |  0.129836  | True   |
|            60 | shuffled_target_no_better:ml_cnn1d_proxy_all_root_proxies |  0.0308117 | True   |
|            61 | train_heldout_run_overlap                                 |  0         | True   |
|            61 | train_heldout_event_id_overlap                            |  0         | True   |
|            61 | covariate_basis_contains_run_one_hot                      |  0         | True   |
|            61 | covariates_derived_before_timing_labels                   |  1         | True   |
|            61 | ml_features_exclude_waveform_event_id_downstream_labels   |  1         | True   |
|            61 | final_fit_train_rows_only                                 |  1         | True   |
|            61 | shuffled_target_no_better:ml_mlp_all_root_proxies         |  0.762084  | True   |
|            61 | shuffled_target_no_better:ml_ridge_all_root_proxies       |  0.82368   | True   |
|            61 | shuffled_target_no_better:ml_gated_proxy_all_root_proxies |  0.796306  | True   |
|            61 | shuffled_target_no_better:ml_cnn1d_proxy_all_root_proxies |  0.913742  | True   |
|            61 | shuffled_target_no_better:ml_hgb_all_root_proxies         |  0.920026  | True   |
|            62 | train_heldout_run_overlap                                 |  0         | True   |
|            62 | train_heldout_event_id_overlap                            |  0         | True   |
|            62 | covariate_basis_contains_run_one_hot                      |  0         | True   |
|            62 | covariates_derived_before_timing_labels                   |  1         | True   |
|            62 | ml_features_exclude_waveform_event_id_downstream_labels   |  1         | True   |
|            62 | final_fit_train_rows_only                                 |  1         | True   |
|            62 | shuffled_target_no_better:ml_ridge_all_root_proxies       |  0.273985  | True   |
|            62 | shuffled_target_no_better:ml_gated_proxy_all_root_proxies |  0.266812  | True   |
|            62 | shuffled_target_no_better:ml_cnn1d_proxy_all_root_proxies |  0.228915  | True   |
|            62 | shuffled_target_no_better:ml_hgb_all_root_proxies         |  0.405715  | True   |
|            62 | shuffled_target_no_better:ml_mlp_all_root_proxies         |  0.13912   | True   |
|            63 | train_heldout_run_overlap                                 |  0         | True   |
|            63 | train_heldout_event_id_overlap                            |  0         | True   |
|            63 | covariate_basis_contains_run_one_hot                      |  0         | True   |
|            63 | covariates_derived_before_timing_labels                   |  1         | True   |
|            63 | ml_features_exclude_waveform_event_id_downstream_labels   |  1         | True   |
|            63 | final_fit_train_rows_only                                 |  1         | True   |
|            63 | shuffled_target_no_better:ml_hgb_all_root_proxies         |  0.249329  | True   |
|            63 | shuffled_target_no_better:ml_cnn1d_proxy_all_root_proxies |  0.373823  | True   |
|            63 | shuffled_target_no_better:ml_mlp_all_root_proxies         |  0.27811   | True   |
|            63 | shuffled_target_no_better:ml_ridge_all_root_proxies       |  0.212132  | True   |
|            63 | shuffled_target_no_better:ml_gated_proxy_all_root_proxies |  0.487468  | True   |
|            65 | train_heldout_run_overlap                                 |  0         | True   |
|            65 | train_heldout_event_id_overlap                            |  0         | True   |
|            65 | covariate_basis_contains_run_one_hot                      |  0         | True   |
|            65 | covariates_derived_before_timing_labels                   |  1         | True   |
|            65 | ml_features_exclude_waveform_event_id_downstream_labels   |  1         | True   |
|            65 | final_fit_train_rows_only                                 |  1         | True   |
|            65 | shuffled_target_no_better:ml_mlp_all_root_proxies         |  0.2654    | True   |
|            65 | shuffled_target_no_better:ml_ridge_all_root_proxies       |  0.129338  | True   |
|            65 | shuffled_target_no_better:ml_hgb_all_root_proxies         |  0.187647  | True   |
|            65 | shuffled_target_no_better:ml_cnn1d_proxy_all_root_proxies |  0.149708  | True   |
|            65 | shuffled_target_no_better:ml_gated_proxy_all_root_proxies |  0.395045  | True   |

Shuffled-target controls:

| method                                   |   mean_sigma68_ns |   ci_low |   ci_high |   delta_vs_traditional_ns |
|:-----------------------------------------|------------------:|---------:|----------:|--------------------------:|
| ml_mlp_all_root_proxies_shuffled         |           1.62757 |  1.51799 |   1.78126 |               -0.0275946  |
| ml_gated_proxy_all_root_proxies_shuffled |           1.63848 |  1.52068 |   1.79301 |               -0.016682   |
| ml_ridge_all_root_proxies_shuffled       |           1.64095 |  1.53053 |   1.80232 |               -0.014212   |
| ml_cnn1d_proxy_all_root_proxies_shuffled |           1.65629 |  1.53075 |   1.83269 |                0.00112352 |
| ml_hgb_all_root_proxies_shuffled         |           1.66461 |  1.53434 |   1.86946 |                0.00944391 |

Systematics:

- Dynamic-only is a selector-semantics label, not a hardware truth label; the quarantine boundary is therefore evaluated as a timing-support decision, not as particle identification.
- The dynamic-boundary traditional comparator uses pre-label run/topology covariates to approximate matched abstention.  It is intentionally transparent but cannot prove causal removal of all dynamic-only pathologies.
- The 1D-CNN is applied to ordered proxy features, not raw waveform samples; this prevents leakage from downstream timing labels but limits architecture expressivity.
- Run 65 remains sparse; the run-block CI is the headline interval and pooled event CIs are treated as secondary diagnostics.
- A method that wins while its shuffled-target control is competitive should be considered a false-improvement warning.

## Verdict

Winner named in `result.json`: `ml_gated_proxy_all_root_proxies` with run-block mean `sigma68 = 1.287 ns` and 95% CI `[1.220, 1.349] ns`.

The strong traditional baseline has mean sigma68 1.655 ns. The dynamic-boundary traditional quarantine proxy has mean sigma68 5.181 ns (lift -3.526 ns). The best ML/NN method is ml_gated_proxy_all_root_proxies at 1.287 ns. An ML/NN method wins numerically; adoption should remain conditional on the shuffled-target and leakage controls. 2 shuffled-target control checks are warnings.

No novel follow-up ticket is appended.  The remaining uncertainty is systematic interpretation of the selector boundary, not a missing computational benchmark.
