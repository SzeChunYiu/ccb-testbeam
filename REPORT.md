# S61a: Cross-talk-aware pulse-shape timing and PID calibration benchmark

## Abstract

Ticket #2522 asks whether neighboring-channel pulse shape, timing skew, pile-up shoulder, saturation onset, and pedestal state improve B-stave energy, timing, and PID closure. The raw ROOT reproduction gate exactly reproduces 640,737 selected pulses. The held-out winner by primary energy width is **gradient_boosted_trees**, with energy res68=0.02987 and run-block bootstrap 95% CI [0.02479, 0.03821].

## Data and Reproduction

The analysis reads the raw `h101` ROOT tree branches `HRDv`, `EVENTNO`, and `EVT` for runs 31--65 listed in the configuration. The baseline is the median of samples 0--3. A selected pulse is an even B-stave channel B2/B4/B6/B8 with peak amplitude above 1000 ADC after baseline subtraction. Odd duplicate channels are reserved as closure targets and are never used as learned-model features.

| quantity | expected | reproduced | delta | pass |
|---|---:|---:|---:|:---|
| selected B-stave pulses | 640,737 | 640,737 | +0 | true |

## Estimands and Equations

For event \(i\), the closure energy target is the duplicate-readout charge sum

\[ y_i^{E}=\sum_{s\in\{B2,B4,B6,B8\}} Q^{odd}_{is} I(A^{even}_{is}>1000). \]

The primary energy residual is

\[ r_i = (\hat y_i^{E}-y_i^{E})/\max(y_i^{E},1). \]

Energy resolution is `res68`, the 68th percentile of \(|r_i|\). The timing target is the odd-charge-weighted selected-pulse peak sample, and timing resolution is the robust 68% half-width of prediction-induced timing residuals. The PID label is an internal high-deposit proxy \(1[y_i^E \ge median(y^E_{train})]\); AUC and average precision are therefore closure diagnostics, not particle-identification truth.

## Methods

The traditional comparator is a coupled-template generalized least-squares surrogate. It predicts the four odd duplicate charges from same-stave even charge, left/right neighboring even charge, and saturation indicators, then sums the four predicted odd charges. The coefficient matrix is fitted on train runs only and is interpretable as a first-order cross-talk response.

The learned panel uses the same run split and even-readout feature contract: ridge regression, gradient-boosted trees, tabular MLP, 1D-CNN over the four aligned 18-sample stave waveforms, compact transformer over stave tokens, and a new cross-talk residual-fusion architecture. The residual-fusion model adds a transformer correction to the traditional prediction and is included because the ticket explicitly asks whether cross-talk residual structure remains after a strong traditional fit.

## Split and Bootstrap

Train runs are [31, 32, 33, 34, 35, 36, 37, 39, 40, 41, 42, 64]; held-out runs are [44, 45, 46, 47, 48, 49, 50, 51, 52, 53, 54, 55, 56, 57, 58, 59, 60, 61, 62, 63, 65]. Confidence intervals are percentile intervals from 200 held-out run-block bootstrap resamples. All model selection and target clipping use train-run quantities only.

## Head-to-Head Metrics

| method                           | family                           | n      | energy_bias_frac | energy_res68_frac | energy_res68_ci95                           | timing_sigma68_samples | timing_sigma68_ci95                          | pid_auc | pid_auc_ci95                             | pid_average_precision |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| gradient_boosted_trees           | ml_tree                          | 332852 | -0.0057419       | 0.029871          | [0.024789876925105956, 0.03821286913147435] | 0.0054455              | [0.004217690283019132, 0.006980758208378375] | 0.99575 | [0.9947118701561544, 0.9965048822505018] | 0.99447               |
| coupled_template_gls_traditional | traditional_coupled_template_gls | 332852 | -0.024182        | 0.048214          | [0.03508341341888524, 0.07041258723278963]  | 0.0079153              | [0.005557586201898777, 0.010164996403773996] | 0.98664 | [0.98269811096789, 0.9899653194784453]   | 0.97422               |
| ridge                            | ml_linear                        | 332852 | -0.026341        | 0.098072          | [0.08180805271609541, 0.133726163160843]    | 0.016213               | [0.01276284889734177, 0.022558225717927174]  | 0.96957 | [0.9644161308257942, 0.9740466446352348] | 0.94646               |
| cross_talk_residual_fusion_new   | new_residual_fusion              | 332852 | -0.027629        | 0.12815           | [0.1084103123184722, 0.1612228337881244]    | 0.021575               | [0.01964148154430808, 0.025709685492838884]  | 0.9878  | [0.9860542707176871, 0.9896355721187801] | 0.98325               |
| compact_transformer              | neural_sequence                  | 332852 | -0.050781        | 0.14687           | [0.1296598300026663, 0.242854531059412]     | 0.023024               | [0.014763778238056097, 0.04483011464563437]  | 0.98337 | [0.9791047505710022, 0.9880846316662845] | 0.96982               |
| 1d_cnn                           | neural_waveform                  | 332852 | -0.11888         | 0.20884           | [0.19531646157065327, 0.3497590164350289]   | 0.0364                 | [0.018468085097009226, 0.06085585239015219]  | 0.96069 | [0.9478648180929952, 0.9714712689848146] | 0.91613               |
| mlp                              | neural_tabular                   | 332852 | -0.26328         | 0.3463            | [0.3389678822961532, 0.36832213477312015]   | 0.038704               | [0.017362928351052385, 0.06551211467817558]  | 0.96993 | [0.9591685297418606, 0.9789879357986639] | 0.93631               |

## Cross-Talk Coefficients

| target_stave_idx | self_coef | left_roll_coef | right_roll_coef | saturation_coef |
| --- | --- | --- | --- | --- |
| 0                | 6352.3    | 0.9083         | -43.116         | 814.08          |
| 1                | 1405.5    | -1.7593        | -2.601          | 1.2585          |
| 2                | 837.48    | 4.4089         | -0.42451        | 9.8843          |
| 3                | 551       | -1.4781        | 0.167           | 19.619          |

## Nuisance Ablations

| ablation                  | baseline_res68 | ablated_res68 | delta_res68 | delta_res68_ci95                               |
| --- | --- | --- | --- | --- |
| neighboring_channel_terms | 0.035635       | 0.035061      | -0.0005748  | [-0.005377345454069009, 0.009119353924809143]  |
| timing_skew_terms         | 0.035635       | 0.039659      | 0.0040239   | [-0.002412258775123864, 0.014840211152764926]  |
| pileup_shoulder_terms     | 0.035635       | 0.032637      | -0.0029981  | [-0.0068796636849819985, 0.005670445796977144] |
| saturation_onset_terms    | 0.035635       | 0.036068      | 0.00043302  | [-0.0052148347706554585, 0.010913608704450057] |
| pedestal_state_terms      | 0.035635       | 0.036319      | 0.00068411  | [-0.005478419426117641, 0.01181348550748553]   |

## Negative Control

Shuffling stave labels within each run gives energy res68=0.03961 with 95% CI [0.03683344514859904, 0.04627005608030595]. This control preserves run occupancy and charge scale while destroying the physical neighbor topology.

## Per-Run Held-Out Summary

| run | method                           | n     | energy_bias_frac | energy_res68_frac | pid_auc |
| --- | --- | --- | --- | --- | --- |
| 44  | coupled_template_gls_traditional | 1911  | -0.030867        | 0.069842          | 0.9854  |
| 44  | gradient_boosted_trees           | 1911  | -0.0031075       | 0.038774          | 0.99332 |
| 45  | coupled_template_gls_traditional | 22999 | -0.028462        | 0.063606          | 0.9877  |
| 45  | gradient_boosted_trees           | 22999 | -0.003175        | 0.038537          | 0.99519 |
| 46  | coupled_template_gls_traditional | 676   | -0.026275        | 0.051256          | 0.99093 |
| 46  | gradient_boosted_trees           | 676   | -0.0028623       | 0.031985          | 0.99395 |
| 47  | coupled_template_gls_traditional | 5160  | -0.021515        | 0.047711          | 0.99196 |
| 47  | gradient_boosted_trees           | 5160  | -0.0014455       | 0.03103           | 0.99692 |
| 48  | coupled_template_gls_traditional | 13175 | -0.031115        | 0.071761          | 0.98664 |
| 48  | gradient_boosted_trees           | 13175 | 0.00015241       | 0.039229          | 0.99452 |
| 49  | coupled_template_gls_traditional | 13921 | -0.030811        | 0.071146          | 0.9872  |
| 49  | gradient_boosted_trees           | 13921 | -0.00083861      | 0.039226          | 0.99439 |
| 50  | coupled_template_gls_traditional | 34254 | -0.011681        | 0.029973          | 0.99198 |
| 50  | gradient_boosted_trees           | 34254 | -0.0093871       | 0.023807          | 0.9967  |
| 51  | coupled_template_gls_traditional | 14294 | -0.013079        | 0.032307          | 0.99109 |
| 51  | gradient_boosted_trees           | 14294 | -0.0079487       | 0.024965          | 0.99644 |
| 52  | coupled_template_gls_traditional | 6933  | -0.012369        | 0.032235          | 0.99061 |
| 52  | gradient_boosted_trees           | 6933  | -0.0086657       | 0.024943          | 0.99698 |
| 53  | coupled_template_gls_traditional | 31382 | -0.015452        | 0.029498          | 0.99232 |
| 53  | gradient_boosted_trees           | 31382 | -0.0081559       | 0.017951          | 0.99659 |
| 54  | coupled_template_gls_traditional | 29664 | -0.015461        | 0.029367          | 0.99327 |
| 54  | gradient_boosted_trees           | 29664 | -0.007968        | 0.01798           | 0.99738 |
| 55  | coupled_template_gls_traditional | 16836 | -0.012723        | 0.031766          | 0.98823 |
| 55  | gradient_boosted_trees           | 16836 | -0.0079565       | 0.023693          | 0.99638 |
| 56  | coupled_template_gls_traditional | 38925 | -0.010197        | 0.03104           | 0.99066 |
| 56  | gradient_boosted_trees           | 38925 | -0.0086799       | 0.024764          | 0.99672 |
| 57  | coupled_template_gls_traditional | 12928 | -0.031398        | 0.071925          | 0.98764 |
| 57  | gradient_boosted_trees           | 12928 | -0.00033912      | 0.039271          | 0.99442 |
| 58  | coupled_template_gls_traditional | 15919 | -0.036358        | 0.046537          | 0.99633 |
| 58  | gradient_boosted_trees           | 15919 | 0.0010299        | 0.026403          | 0.99862 |
| 59  | coupled_template_gls_traditional | 13861 | -0.041451        | 0.12185           | 0.97543 |
| 59  | gradient_boosted_trees           | 13861 | 0.0044365        | 0.074378          | 0.98971 |
| 60  | coupled_template_gls_traditional | 10133 | -0.052668        | 0.10893           | 0.97538 |
| 60  | gradient_boosted_trees           | 10133 | -0.0065174       | 0.079262          | 0.9949  |
| 61  | coupled_template_gls_traditional | 11287 | -0.051192        | 0.10254           | 0.97922 |
| 61  | gradient_boosted_trees           | 11287 | -0.0059114       | 0.075663          | 0.99392 |
| 62  | coupled_template_gls_traditional | 11911 | -0.047978        | 0.10859           | 0.97996 |
| 62  | gradient_boosted_trees           | 11911 | -0.0007054       | 0.06898           | 0.99319 |
| 63  | coupled_template_gls_traditional | 14779 | -0.03991         | 0.091441          | 0.9836  |
| 63  | gradient_boosted_trees           | 14779 | 0.0077039        | 0.046533          | 0.99293 |
| 65  | coupled_template_gls_traditional | 11904 | -0.044998        | 0.10262           | 0.99046 |
| 65  | gradient_boosted_trees           | 11904 | 0.012947         | 0.04064           | 0.99557 |

## Systematics and Caveats

The PID target is a duplicate-readout high-deposit proxy rather than an external particle label, so PID AUC is a closure metric. Timing is measured in sample units and inherits the 18-sample waveform granularity. Odd/even duplicate electronics can differ nonlinearly, especially near saturation. The bootstrap treats runs as the exchangeable unit; with the available run count it captures run-scale drift but cannot prove stability under unseen beamline configurations. The cross-talk coefficients are first-order linear responses and should not be interpreted as a full electronics transfer matrix outside the selected-pulse support.

## Finding

The held-out primary winner is gradient_boosted_trees with energy res68=0.02987; the traditional coupled-template GLS comparator has res68=0.04821. Cross-talk/nuisance terms are useful only where ablation deltas are positive and their run-block intervals exclude zero; PID and timing are duplicate-readout closure diagnostics, not external particle truth.

## Reproducibility

```bash
/home/billy/anaconda3/bin/python scripts/ticket_2522_s61a_cross_talk_pulse_shape_pid.py --config configs/ticket_2522_s61a_cross_talk_pulse_shape_pid.yaml
```
