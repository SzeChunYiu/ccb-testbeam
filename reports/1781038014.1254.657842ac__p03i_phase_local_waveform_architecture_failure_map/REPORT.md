# P03i: phase-local waveform architecture failure map

- **Ticket:** `1781038014.1254.657842ac`
- **Worker:** `testbeam-laptop-3`
- **Claimed study:** phase-local waveform architecture failure map
- **Input:** raw B-stack ROOT files from `/home/billy/ccb-data/extracted/root/root`
- **Split:** leave-one-run-out over Sample-II analysis runs `[58, 59, 60, 61, 62, 63, 65]`
- **Traditional comparator:** `s02b_global_template_timewalk`
- **Winner:** `hgb_no_samples_0_3` (`sigma68 = 1.171 ns`, 95% CI [1.141, 1.214] ns)

## Abstract

This study asks why waveform MLP/CNN timing learners have historically failed to beat the strongest analytic/template timewalk baseline except in isolated run strata. I reproduced the selected-pulse count from raw ROOT, reran a fold-local traditional timing chain, and benchmarked ridge, histogram gradient-boosted trees, an MLP, a 1D-CNN, and a new early/late gated waveform network under leave-one-run-out Sample-II folds. I then localized the residual gains and failures to sample phase, stave pair, saturation proxy, q-template mismatch, baseline excursion, delayed-peak, run-family, and amplitude atoms.

## Raw-ROOT Reproduction Gate

The input gate was rerun directly from `HRDv` branches in the raw ROOT files before fitting any timing model. The selection is the canonical B-stave pulse count after median baseline subtraction and `A > 1000 ADC`.

| quantity                           |   report_value |   reproduced |   delta |   tolerance | pass   |
|:-----------------------------------|---------------:|-------------:|--------:|------------:|:-------|
| total selected B-stave pulses      |         640737 |       640737 |       0 |           0 | True   |
| sample_ii_analysis selected_pulses |         125096 |       125096 |       0 |           0 | True   |
| sample_ii_analysis B2              |          88213 |        88213 |       0 |           0 | True   |
| sample_ii_analysis B4              |          21229 |        21229 |       0 |           0 | True   |
| sample_ii_analysis B6              |          11148 |        11148 |       0 |           0 | True   |
| sample_ii_analysis B8              |           4506 |         4506 |       0 |           0 | True   |

All deltas are zero, so the benchmark starts from the same raw population as the project reports.

## Estimand and Metrics

For event `e`, stave `a`, method `m`, and stave position `z_a`, define the time-of-flight corrected time

`tau_a(e;m) = t_a(e;m) - z_a / v`, with `1/v = 0.078 ns/cm`.

For downstream stave pair `(a,b)`, the event-paired closure residual is

`r_ab(e;m) = tau_a(e;m) - tau_b(e;m)`.

The primary robust width is

`sigma68(m) = [Q_84(r(m)) - Q_16(r(m))] / 2`.

I also report full RMS, median bias, the fraction of residuals beyond the global traditional 95th percentile tail threshold, and the atom-local tail risk ratio

`RR_A(m) = P(|r_m - median(r_m)| > T_trad,global | A) / P(|r_trad - median(r_trad)| > T_trad,global | A)`.

Per-held-out-run CIs are event bootstraps. The pooled headline CI is a nested run-block/event bootstrap. Atom-map CIs resample events inside each atom stratum.

## Methods

Each fold holds out one of runs `[58, 59, 60, 61, 62, 63, 65]`. The other six runs define every train-only object: S02 global templates, amplitude-binned S02b template-SSE nuisance, and conventional template-phase timewalk. No template, target, scaler, or neural weight sees the held-out run.

The traditional comparator is `s02b_global_template_timewalk`, a train-fold global-template phase pickoff with explicit timewalk terms. It is stronger than the older raw CFD/template pickoffs and is the frozen analytic baseline for the failure map.

All residual learners target the same-pulse residual

`y_i = t_i(trad) - mean_j!=i t_j(trad)`

inside the event. The tested model families are:

- `ridge`: standardized Ridge regression over normalized waveform and hand pulse summaries.
- `hgb`: histogram gradient-boosted regression trees.
- `mlp`: heteroskedastic fully connected neural network.
- `cnn1d`: compact 1D convolutional waveform network.
- `early_late_gated`: new architecture with separate samples 0-3 and samples 4-17 branches mixed by a learned auxiliary-feature gate.

The phase-local masks are `full`, `no_samples_0_3`, and `only_samples_0_3`. Shuffled-target sentinels are trained for every nominal waveform learner. Run-family controls use only hand summaries, stave, and predeclared early/middle/late run family.

## Pooled Benchmark

| method                            | family      |   sigma68_ns |   ci_low |   ci_high |   delta_vs_traditional_ns |   delta_ci_low |   delta_ci_high |   tail_frac_vs_traditional_p95 |
|:----------------------------------|:------------|-------------:|---------:|----------:|--------------------------:|---------------:|----------------:|-------------------------------:|
| hgb_no_samples_0_3                | ml          |      1.17068 |  1.1414  |   1.21431 |                 -0.521682 |      -0.77514  |     -0.317925   |                      0.0237347 |
| hgb_full                          | ml          |      1.17489 |  1.14098 |   1.21938 |                 -0.517466 |      -0.771989 |     -0.316203   |                      0.0239092 |
| hgb_only_samples_0_3              | ml          |      1.20058 |  1.16483 |   1.23908 |                 -0.491783 |      -0.76555  |     -0.289333   |                      0.0233857 |
| mlp_no_samples_0_3                | ml          |      1.32003 |  1.26487 |   1.3868  |                 -0.372327 |      -0.661045 |     -0.139643   |                      0.026178  |
| ridge_no_samples_0_3              | ml          |      1.36131 |  1.30515 |   1.41984 |                 -0.331046 |      -0.635727 |     -0.111622   |                      0.0270506 |
| ridge_full                        | ml          |      1.36386 |  1.30572 |   1.41669 |                 -0.328502 |      -0.635691 |     -0.108697   |                      0.0273997 |
| ridge_only_samples_0_3            | ml          |      1.38244 |  1.33278 |   1.42727 |                 -0.309918 |      -0.582567 |     -0.108235   |                      0.0290576 |
| early_late_gated_full             | ml          |      1.40561 |  1.31748 |   1.49869 |                 -0.286745 |      -0.584499 |     -0.0247258  |                      0.0287086 |
| early_late_gated_only_samples_0_3 | ml          |      1.42941 |  1.34195 |   1.50798 |                 -0.262947 |      -0.56493  |     -0.048127   |                      0.0319372 |
| cnn1d_only_samples_0_3            | ml          |      1.43487 |  1.30442 |   1.53102 |                 -0.257487 |      -0.644063 |      0.00270627 |                      0.0341187 |
| mlp_only_samples_0_3              | ml          |      1.44092 |  1.3235  |   1.54453 |                 -0.251434 |      -0.614508 |      0.00110822 |                      0.0288831 |
| mlp_full                          | ml          |      1.4689  |  1.3283  |   1.59004 |                 -0.223459 |      -0.599986 |      0.0577531  |                      0.032199  |
| cnn1d_full                        | ml          |      1.47745 |  1.38369 |   1.57796 |                 -0.214905 |      -0.559347 |      0.0573149  |                      0.032897  |
| early_late_gated_no_samples_0_3   | ml          |      1.48277 |  1.40072 |   1.57658 |                 -0.209587 |      -0.521724 |      0.0603817  |                      0.0321117 |
| cnn1d_no_samples_0_3              | ml          |      1.49421 |  1.39485 |   1.535   |                 -0.198152 |      -0.555877 |     -0.039254   |                      0.0356894 |
| s02b_global_template_timewalk     | traditional |      1.69236 |  1.52051 |   1.95242 |                  0        |       0        |      0          |                      0.05      |

## Held-Out Run Benchmark

|   heldout_run | method                            | family             |   sigma68_ns |   ci_low |   ci_high |   delta_vs_traditional_ns |   n_events |
|--------------:|:----------------------------------|:-------------------|-------------:|---------:|----------:|--------------------------:|-----------:|
|            58 | hgb_full                          | ml                 |      1.06716 | 0.887931 |   1.24981 |               -0.455629   |         73 |
|            58 | hgb_run_family_control            | run_family_control |      1.06951 | 0.927683 |   1.22537 |               -0.453287   |         73 |
|            58 | hgb_only_samples_0_3              | ml                 |      1.1486  | 0.942686 |   1.35573 |               -0.374192   |         73 |
|            58 | hgb_no_samples_0_3                | ml                 |      1.14929 | 0.954492 |   1.37223 |               -0.373499   |         73 |
|            58 | cnn1d_no_samples_0_3              | ml                 |      1.17484 | 1.0116   |   1.39262 |               -0.34795    |         73 |
|            58 | mlp_no_samples_0_3                | ml                 |      1.28744 | 1.03385  |   1.52814 |               -0.235355   |         73 |
|            58 | ridge_run_family_control          | run_family_control |      1.34856 | 1.18746  |   1.53405 |               -0.174236   |         73 |
|            58 | ridge_no_samples_0_3              | ml                 |      1.35919 | 1.22378  |   1.49204 |               -0.163605   |         73 |
|            58 | ridge_only_samples_0_3            | ml                 |      1.36913 | 1.22227  |   1.61251 |               -0.153663   |         73 |
|            58 | ridge_full                        | ml                 |      1.3753  | 1.25259  |   1.51729 |               -0.147497   |         73 |
|            58 | mlp_full                          | ml                 |      1.3855  | 1.18335  |   1.65482 |               -0.137291   |         73 |
|            58 | s02b_global_template_timewalk     | traditional        |      1.52279 | 1.25405  |   1.87052 |                0          |         73 |
|            58 | early_late_gated_only_samples_0_3 | ml                 |      1.52494 | 1.32737  |   1.69812 |                0.00214852 |         73 |
|            58 | early_late_gated_no_samples_0_3   | ml                 |      1.5394  | 1.37341  |   1.69131 |                0.0166041  |         73 |
|            58 | early_late_gated_full             | ml                 |      1.54208 | 1.38508  |   1.82191 |                0.0192902  |         73 |
|            58 | cnn1d_only_samples_0_3            | ml                 |      1.59572 | 1.39601  |   1.78346 |                0.0729235  |         73 |
|            58 | mlp_only_samples_0_3              | ml                 |      1.62213 | 1.37154  |   1.90256 |                0.0993396  |         73 |
|            58 | cnn1d_full                        | ml                 |      1.74604 | 1.52147  |   1.86298 |                0.223252   |         73 |
|            59 | hgb_no_samples_0_3                | ml                 |      1.14656 | 1.08375  |   1.20095 |               -0.4502     |        763 |
|            59 | hgb_run_family_control            | run_family_control |      1.15198 | 1.09871  |   1.20734 |               -0.444777   |        763 |
|            59 | hgb_full                          | ml                 |      1.15721 | 1.10358  |   1.21165 |               -0.439547   |        763 |
|            59 | hgb_only_samples_0_3              | ml                 |      1.20128 | 1.13795  |   1.26303 |               -0.395484   |        763 |
|            59 | early_late_gated_full             | ml                 |      1.29646 | 1.22938  |   1.36044 |               -0.300305   |        763 |
|            59 | ridge_no_samples_0_3              | ml                 |      1.34619 | 1.29719  |   1.40503 |               -0.250573   |        763 |
|            59 | mlp_no_samples_0_3                | ml                 |      1.34979 | 1.29838  |   1.4113  |               -0.246966   |        763 |
|            59 | ridge_full                        | ml                 |      1.35699 | 1.29854  |   1.40846 |               -0.239769   |        763 |
|            59 | ridge_run_family_control          | run_family_control |      1.36736 | 1.30825  |   1.42766 |               -0.229404   |        763 |
|            59 | cnn1d_only_samples_0_3            | ml                 |      1.37441 | 1.31346  |   1.42854 |               -0.222355   |        763 |
|            59 | early_late_gated_no_samples_0_3   | ml                 |      1.37876 | 1.32867  |   1.44826 |               -0.217999   |        763 |
|            59 | ridge_only_samples_0_3            | ml                 |      1.38151 | 1.31224  |   1.43531 |               -0.215253   |        763 |
|            59 | mlp_only_samples_0_3              | ml                 |      1.39136 | 1.33563  |   1.43939 |               -0.205398   |        763 |
|            59 | mlp_full                          | ml                 |      1.39806 | 1.34135  |   1.467   |               -0.198696   |        763 |
|            59 | cnn1d_no_samples_0_3              | ml                 |      1.4379  | 1.38192  |   1.50112 |               -0.158858   |        763 |
|            59 | cnn1d_full                        | ml                 |      1.45814 | 1.39804  |   1.51677 |               -0.138618   |        763 |
|            59 | early_late_gated_only_samples_0_3 | ml                 |      1.5593  | 1.49682  |   1.62938 |               -0.0374597  |        763 |
|            59 | s02b_global_template_timewalk     | traditional        |      1.59676 | 1.54716  |   1.65055 |                0          |        763 |
|            60 | hgb_no_samples_0_3                | ml                 |      1.17817 | 1.11239  |   1.24828 |               -0.293728   |        808 |
|            60 | hgb_full                          | ml                 |      1.19231 | 1.12566  |   1.25374 |               -0.279582   |        808 |
|            60 | hgb_only_samples_0_3              | ml                 |      1.22452 | 1.16285  |   1.31315 |               -0.24738    |        808 |
|            60 | hgb_run_family_control            | run_family_control |      1.27725 | 1.21486  |   1.34776 |               -0.19465    |        808 |
|            60 | early_late_gated_only_samples_0_3 | ml                 |      1.38834 | 1.31116  |   1.46308 |               -0.0835607  |        808 |
|            60 | mlp_no_samples_0_3                | ml                 |      1.39627 | 1.33013  |   1.45986 |               -0.0756299  |        808 |
|            60 | ridge_run_family_control          | run_family_control |      1.40503 | 1.35236  |   1.49395 |               -0.066865   |        808 |
|            60 | ridge_full                        | ml                 |      1.422   | 1.36142  |   1.50162 |               -0.0498928  |        808 |
|            60 | ridge_no_samples_0_3              | ml                 |      1.42418 | 1.3619   |   1.49138 |               -0.0477203  |        808 |
|            60 | ridge_only_samples_0_3            | ml                 |      1.43495 | 1.36841  |   1.50025 |               -0.0369514  |        808 |
|            60 | s02b_global_template_timewalk     | traditional        |      1.4719  | 1.42708  |   1.52023 |                0          |        808 |
|            60 | cnn1d_no_samples_0_3              | ml                 |      1.49641 | 1.44231  |   1.57948 |                0.0245102  |        808 |
|            60 | mlp_only_samples_0_3              | ml                 |      1.52809 | 1.46548  |   1.6043  |                0.0561893  |        808 |
|            60 | early_late_gated_full             | ml                 |      1.54754 | 1.48128  |   1.6129  |                0.0756452  |        808 |
|            60 | cnn1d_only_samples_0_3            | ml                 |      1.56922 | 1.51548  |   1.66266 |                0.0973259  |        808 |
|            60 | cnn1d_full                        | ml                 |      1.62049 | 1.56291  |   1.69483 |                0.148589   |        808 |
|            60 | early_late_gated_no_samples_0_3   | ml                 |      1.63638 | 1.57231  |   1.7043  |                0.164482   |        808 |
|            60 | mlp_full                          | ml                 |      1.65538 | 1.55774  |   1.71273 |                0.183485   |        808 |
|            61 | hgb_full                          | ml                 |      1.16316 | 1.1174   |   1.21147 |               -1.02526    |        933 |
|            61 | hgb_run_family_control            | run_family_control |      1.16825 | 1.11903  |   1.21439 |               -1.02016    |        933 |
|            61 | hgb_no_samples_0_3                | ml                 |      1.16904 | 1.11667  |   1.21282 |               -1.01938    |        933 |
|            61 | hgb_only_samples_0_3              | ml                 |      1.20108 | 1.15359  |   1.25343 |               -0.987334   |        933 |
|            61 | mlp_no_samples_0_3                | ml                 |      1.24342 | 1.19262  |   1.2908  |               -0.944996   |        933 |
|            61 | cnn1d_only_samples_0_3            | ml                 |      1.24579 | 1.18153  |   1.31121 |               -0.942628   |        933 |
|            61 | cnn1d_no_samples_0_3              | ml                 |      1.24591 | 1.19886  |   1.29685 |               -0.942506   |        933 |
|            61 | ridge_no_samples_0_3              | ml                 |      1.27953 | 1.21595  |   1.33891 |               -0.908884   |        933 |
|            61 | mlp_only_samples_0_3              | ml                 |      1.28125 | 1.21842  |   1.32963 |               -0.907167   |        933 |
|            61 | ridge_full                        | ml                 |      1.28172 | 1.2221   |   1.34024 |               -0.906693   |        933 |
|            61 | ridge_run_family_control          | run_family_control |      1.29081 | 1.24054  |   1.34557 |               -0.897609   |        933 |
|            61 | ridge_only_samples_0_3            | ml                 |      1.30833 | 1.25324  |   1.34967 |               -0.880088   |        933 |
|            61 | mlp_full                          | ml                 |      1.31094 | 1.25559  |   1.35898 |               -0.877474   |        933 |
|            61 | early_late_gated_only_samples_0_3 | ml                 |      1.32761 | 1.2807   |   1.38261 |               -0.860807   |        933 |
|            61 | cnn1d_full                        | ml                 |      1.33072 | 1.27477  |   1.38339 |               -0.857699   |        933 |
|            61 | early_late_gated_no_samples_0_3   | ml                 |      1.36006 | 1.30961  |   1.40217 |               -0.828357   |        933 |
|            61 | early_late_gated_full             | ml                 |      1.37489 | 1.32071  |   1.42574 |               -0.81353    |        933 |
|            61 | s02b_global_template_timewalk     | traditional        |      2.18842 | 2.09301  |   2.26203 |                0          |        933 |
|            62 | hgb_full                          | ml                 |      1.14274 | 1.08527  |   1.21381 |               -0.487209   |        807 |
|            62 | hgb_no_samples_0_3                | ml                 |      1.14824 | 1.09672  |   1.21698 |               -0.481707   |        807 |
|            62 | hgb_only_samples_0_3              | ml                 |      1.17948 | 1.12475  |   1.23384 |               -0.450466   |        807 |
|            62 | hgb_run_family_control            | run_family_control |      1.24008 | 1.1927   |   1.31372 |               -0.389869   |        807 |
|            62 | mlp_only_samples_0_3              | ml                 |      1.25215 | 1.19398  |   1.31497 |               -0.377791   |        807 |
|            62 | mlp_full                          | ml                 |      1.2692  | 1.19976  |   1.34134 |               -0.360747   |        807 |
|            62 | early_late_gated_only_samples_0_3 | ml                 |      1.30142 | 1.24626  |   1.37312 |               -0.328526   |        807 |
|            62 | mlp_no_samples_0_3                | ml                 |      1.31165 | 1.25002  |   1.38117 |               -0.318296   |        807 |
|            62 | ridge_full                        | ml                 |      1.32823 | 1.27889  |   1.38423 |               -0.301714   |        807 |
|            62 | ridge_no_samples_0_3              | ml                 |      1.3348  | 1.27708  |   1.39502 |               -0.295147   |        807 |
|            62 | ridge_run_family_control          | run_family_control |      1.34391 | 1.2772   |   1.41578 |               -0.286032   |        807 |
|            62 | ridge_only_samples_0_3            | ml                 |      1.34506 | 1.28452  |   1.41558 |               -0.284885   |        807 |
|            62 | early_late_gated_full             | ml                 |      1.42504 | 1.34466  |   1.49631 |               -0.204901   |        807 |
|            62 | cnn1d_only_samples_0_3            | ml                 |      1.43059 | 1.34661  |   1.50113 |               -0.199352   |        807 |
|            62 | early_late_gated_no_samples_0_3   | ml                 |      1.43204 | 1.36262  |   1.50804 |               -0.19791    |        807 |
|            62 | cnn1d_no_samples_0_3              | ml                 |      1.46899 | 1.39362  |   1.54876 |               -0.160959   |        807 |
|            62 | cnn1d_full                        | ml                 |      1.50002 | 1.43112  |   1.58062 |               -0.129923   |        807 |
|            62 | s02b_global_template_timewalk     | traditional        |      1.62995 | 1.58215  |   1.68151 |                0          |        807 |
|            63 | hgb_full                          | ml                 |      1.22135 | 1.1604   |   1.32059 |               -0.319566   |        370 |
|            63 | hgb_no_samples_0_3                | ml                 |      1.23635 | 1.14214  |   1.33074 |               -0.304572   |        370 |
|            63 | hgb_only_samples_0_3              | ml                 |      1.23771 | 1.15509  |   1.33212 |               -0.303208   |        370 |
|            63 | hgb_run_family_control            | run_family_control |      1.23995 | 1.14056  |   1.31836 |               -0.300966   |        370 |
|            63 | early_late_gated_full             | ml                 |      1.25119 | 1.16192  |   1.34526 |               -0.289727   |        370 |

## Failure Atoms

Event atoms are derived without target labels from held-out pulse morphology: median peak-sample phase, stave pair, top-5% amplitude saturation proxy, top-10% q-template SSE, top-10% baseline excursion, delayed or late-charge peak, any-high-risk union, run family, and amplitude tercile.

Atom counts:

| atom_type         | atom_value               |   n_events |
|:------------------|:-------------------------|-----------:|
| phase_atom        | central_phase_6          |        368 |
| phase_atom        | early_phase_le5          |        654 |
| phase_atom        | late_phase_ge7           |       2798 |
| saturation_atom   | amp_bulk                 |       3248 |
| saturation_atom   | amp_top5_proxy           |        572 |
| q_template_atom   | q_template_sse_bulk      |       3344 |
| q_template_atom   | q_template_sse_top10     |        476 |
| baseline_atom     | baseline_bulk            |       3232 |
| baseline_atom     | baseline_excursion_top10 |        588 |
| delayed_peak_atom | delayed_or_late_charge   |       2109 |
| delayed_peak_atom | prompt_peak              |       1711 |
| anomaly_atom      | any_high_risk_atom       |       2933 |
| anomaly_atom      | no_high_risk_atom        |        887 |
| run_family_atom   | early                    |        836 |
| run_family_atom   | late                     |        436 |
| run_family_atom   | middle                   |       2548 |
| amplitude_atom    | amp_high                 |       1272 |
| amplitude_atom    | amp_low                  |       1276 |
| amplitude_atom    | amp_mid                  |       1272 |
| pair              | B4-B6                    |       3820 |
| pair              | B4-B8                    |       3820 |
| pair              | B6-B8                    |       3820 |

Best nominal learner by atom:

| atom_type         | atom_value               | best_method            |   best_sigma68_ns |   traditional_sigma68_ns |   best_delta_vs_traditional_ns |   best_tail_risk_ratio_vs_traditional |   n_events |
|:------------------|:-------------------------|:-----------------------|------------------:|-------------------------:|-------------------------------:|--------------------------------------:|-----------:|
| amplitude_atom    | amp_high                 | hgb_no_samples_0_3     |          1.23238  |                  1.79683 |                      -0.564448 |                              0.560784 |       1272 |
| amplitude_atom    | amp_low                  | hgb_full               |          1.08475  |                  1.59561 |                      -0.510863 |                              0.264368 |       1276 |
| amplitude_atom    | amp_mid                  | hgb_no_samples_0_3     |          1.21625  |                  1.6504  |                      -0.434147 |                              0.537975 |       1272 |
| anomaly_atom      | no_high_risk_atom        | hgb_full               |          1.00835  |                  1.55335 |                      -0.544998 |                              0.326087 |        887 |
| anomaly_atom      | any_high_risk_atom       | hgb_no_samples_0_3     |          1.22935  |                  1.74186 |                      -0.512506 |                              0.490909 |       2933 |
| baseline_atom     | baseline_excursion_top10 | hgb_full               |          0.764268 |                  1.52014 |                      -0.755876 |                              0.920635 |        588 |
| baseline_atom     | baseline_bulk            | hgb_full               |          1.27646  |                  1.76234 |                      -0.485884 |                              0.403409 |       3232 |
| delayed_peak_atom | prompt_peak              | hgb_full               |          0.924265 |                  1.55396 |                      -0.629692 |                              0.339506 |       1711 |
| delayed_peak_atom | delayed_or_late_charge   | hgb_no_samples_0_3     |          1.40813  |                  1.86044 |                      -0.452312 |                              0.49884  |       2109 |
| pair              | B4-B8                    | hgb_full               |          1.11606  |                  1.30879 |                      -0.192733 |                              0.714286 |       3820 |
| pair              | B4-B6                    | hgb_no_samples_0_3     |          1.09763  |                  1.2293  |                      -0.131672 |                              0.792    |       3820 |
| pair              | B6-B8                    | hgb_full               |          0.957192 |                  1.07858 |                      -0.121388 |                              0.877193 |       3820 |
| phase_atom        | early_phase_le5          | cnn1d_only_samples_0_3 |          0.741296 |                  1.45821 |                      -0.716914 |                              0.555556 |        654 |
| phase_atom        | central_phase_6          | hgb_full               |          0.843684 |                  1.40542 |                      -0.561738 |                              0.758621 |        368 |
| phase_atom        | late_phase_ge7           | hgb_no_samples_0_3     |          1.36247  |                  1.86781 |                      -0.505343 |                              0.415238 |       2798 |
| q_template_atom   | q_template_sse_bulk      | hgb_no_samples_0_3     |          1.20309  |                  1.73748 |                      -0.53439  |                              0.373358 |       3344 |
| q_template_atom   | q_template_sse_top10     | hgb_only_samples_0_3   |          0.977187 |                  1.46944 |                      -0.492252 |                              1.31111  |        476 |
| run_family_atom   | middle                   | hgb_no_samples_0_3     |          1.16405  |                  1.76792 |                      -0.603874 |                              0.433255 |       2548 |
| run_family_atom   | early                    | hgb_no_samples_0_3     |          1.14529  |                  1.59951 |                      -0.454222 |                              0.55914  |        836 |
| run_family_atom   | late                     | hgb_only_samples_0_3   |          1.24137  |                  1.55424 |                      -0.31288  |                              0.509091 |        436 |
| saturation_atom   | amp_top5_proxy           | hgb_full               |          1.24202  |                  1.98343 |                      -0.741409 |                              0.476562 |        572 |
| saturation_atom   | amp_bulk                 | hgb_no_samples_0_3     |          1.16089  |                  1.66435 |                      -0.503457 |                              0.457778 |       3248 |

Focused atom metrics for the traditional method, winner, and representative architectures:

| atom_type         | atom_value               | method                        |   sigma68_ns |   ci_low |   ci_high |   delta_vs_traditional_ns |   tail_risk_ratio_vs_traditional |
|:------------------|:-------------------------|:------------------------------|-------------:|---------:|----------:|--------------------------:|---------------------------------:|
| amplitude_atom    | amp_high                 | hgb_no_samples_0_3            |     1.23238  | 1.17602  |  1.27985  |               -0.564448   |                         0.560784 |
| amplitude_atom    | amp_high                 | hgb_full                      |     1.23986  | 1.17866  |  1.29193  |               -0.556967   |                         0.556863 |
| amplitude_atom    | amp_high                 | early_late_gated_full         |     1.46784  | 1.40654  |  1.5186   |               -0.328983   |                         0.690196 |
| amplitude_atom    | amp_high                 | mlp_full                      |     1.51584  | 1.46354  |  1.58112  |               -0.280985   |                         0.709804 |
| amplitude_atom    | amp_high                 | cnn1d_full                    |     1.51661  | 1.45533  |  1.58028  |               -0.280216   |                         0.721569 |
| amplitude_atom    | amp_high                 | s02b_global_template_timewalk |     1.79683  | 1.73918  |  1.87556  |                0          |                         1        |
| amplitude_atom    | amp_low                  | hgb_full                      |     1.08475  | 1.03774  |  1.12656  |               -0.510863   |                         0.264368 |
| amplitude_atom    | amp_low                  | hgb_no_samples_0_3            |     1.08969  | 1.05312  |  1.13479  |               -0.505923   |                         0.247126 |
| amplitude_atom    | amp_low                  | early_late_gated_full         |     1.30799  | 1.23878  |  1.36529  |               -0.287622   |                         0.431034 |
| amplitude_atom    | amp_low                  | cnn1d_full                    |     1.39257  | 1.34033  |  1.46008  |               -0.203036   |                         0.528736 |
| amplitude_atom    | amp_low                  | mlp_full                      |     1.4035   | 1.34965  |  1.45081  |               -0.192104   |                         0.471264 |
| amplitude_atom    | amp_low                  | s02b_global_template_timewalk |     1.59561  | 1.55134  |  1.65378  |                0          |                         1        |
| amplitude_atom    | amp_mid                  | hgb_no_samples_0_3            |     1.21625  | 1.15911  |  1.27237  |               -0.434147   |                         0.537975 |
| amplitude_atom    | amp_mid                  | hgb_full                      |     1.21897  | 1.17272  |  1.27375  |               -0.431424   |                         0.544304 |
| amplitude_atom    | amp_mid                  | early_late_gated_full         |     1.42106  | 1.35282  |  1.46745  |               -0.22934    |                         0.550633 |
| amplitude_atom    | amp_mid                  | mlp_full                      |     1.46297  | 1.41794  |  1.50991  |               -0.187426   |                         0.658228 |
| amplitude_atom    | amp_mid                  | cnn1d_full                    |     1.48156  | 1.42284  |  1.52732  |               -0.168835   |                         0.658228 |
| amplitude_atom    | amp_mid                  | s02b_global_template_timewalk |     1.6504   | 1.60393  |  1.69929  |                0          |                         1        |
| anomaly_atom      | any_high_risk_atom       | hgb_no_samples_0_3            |     1.22935  | 1.19517  |  1.26768  |               -0.512506   |                         0.490909 |
| anomaly_atom      | any_high_risk_atom       | hgb_full                      |     1.24068  | 1.19583  |  1.27032  |               -0.501184   |                         0.50101  |
| anomaly_atom      | any_high_risk_atom       | early_late_gated_full         |     1.47034  | 1.43896  |  1.51573  |               -0.271523   |                         0.59798  |
| anomaly_atom      | any_high_risk_atom       | mlp_full                      |     1.49877  | 1.45415  |  1.53125  |               -0.243094   |                         0.664646 |
| anomaly_atom      | any_high_risk_atom       | cnn1d_full                    |     1.53445  | 1.49694  |  1.57284  |               -0.207413   |                         0.676768 |
| anomaly_atom      | any_high_risk_atom       | s02b_global_template_timewalk |     1.74186  | 1.71082  |  1.77323  |                0          |                         1        |
| anomaly_atom      | no_high_risk_atom        | hgb_full                      |     1.00835  | 0.967418 |  1.0717   |               -0.544998   |                         0.326087 |
| anomaly_atom      | no_high_risk_atom        | hgb_no_samples_0_3            |     1.0201   | 0.96542  |  1.06156  |               -0.533246   |                         0.282609 |
| anomaly_atom      | no_high_risk_atom        | early_late_gated_full         |     1.19737  | 1.13947  |  1.25866  |               -0.35598    |                         0.336957 |
| anomaly_atom      | no_high_risk_atom        | cnn1d_full                    |     1.31694  | 1.2648   |  1.38165  |               -0.23641    |                         0.423913 |
| anomaly_atom      | no_high_risk_atom        | mlp_full                      |     1.40969  | 1.35098  |  1.46248  |               -0.143659   |                         0.413043 |
| anomaly_atom      | no_high_risk_atom        | s02b_global_template_timewalk |     1.55335  | 1.48997  |  1.59971  |                0          |                         1        |
| baseline_atom     | baseline_bulk            | hgb_full                      |     1.27646  | 1.24698  |  1.30601  |               -0.485884   |                         0.403409 |
| baseline_atom     | baseline_bulk            | hgb_no_samples_0_3            |     1.27969  | 1.24178  |  1.31023  |               -0.482654   |                         0.401515 |
| baseline_atom     | baseline_bulk            | early_late_gated_full         |     1.51638  | 1.483    |  1.55693  |               -0.245956   |                         0.537879 |
| baseline_atom     | baseline_bulk            | mlp_full                      |     1.56648  | 1.52804  |  1.60049  |               -0.195862   |                         0.611742 |
| baseline_atom     | baseline_bulk            | cnn1d_full                    |     1.59328  | 1.55484  |  1.62653  |               -0.169063   |                         0.613636 |
| baseline_atom     | baseline_bulk            | s02b_global_template_timewalk |     1.76234  | 1.71892  |  1.80061  |                0          |                         1        |
| baseline_atom     | baseline_excursion_top10 | hgb_full                      |     0.764268 | 0.739938 |  0.79968  |               -0.755876   |                         0.920635 |
| baseline_atom     | baseline_excursion_top10 | hgb_no_samples_0_3            |     0.779285 | 0.744955 |  0.8027   |               -0.740859   |                         0.84127  |
| baseline_atom     | baseline_excursion_top10 | early_late_gated_full         |     0.890373 | 0.842026 |  0.939723 |               -0.629771   |                         0.730159 |
| baseline_atom     | baseline_excursion_top10 | cnn1d_full                    |     0.893383 | 0.844034 |  0.944354 |               -0.626761   |                         0.714286 |
| baseline_atom     | baseline_excursion_top10 | mlp_full                      |     1.04411  | 0.98523  |  1.10949  |               -0.476037   |                         0.746032 |
| baseline_atom     | baseline_excursion_top10 | s02b_global_template_timewalk |     1.52014  | 1.47049  |  1.567    |                0          |                         1        |
| delayed_peak_atom | delayed_or_late_charge   | hgb_no_samples_0_3            |     1.40813  | 1.36748  |  1.44387  |               -0.452312   |                         0.49884  |
| delayed_peak_atom | delayed_or_late_charge   | hgb_full                      |     1.41943  | 1.37414  |  1.4578   |               -0.441007   |                         0.519722 |
| delayed_peak_atom | delayed_or_late_charge   | mlp_full                      |     1.6543   | 1.60668  |  1.69429  |               -0.206136   |                         0.684455 |
| delayed_peak_atom | delayed_or_late_charge   | early_late_gated_full         |     1.6732   | 1.6404   |  1.71609  |               -0.187235   |                         0.610209 |
| delayed_peak_atom | delayed_or_late_charge   | cnn1d_full                    |     1.75778  | 1.70988  |  1.80401  |               -0.102655   |                         0.684455 |
| delayed_peak_atom | delayed_or_late_charge   | s02b_global_template_timewalk |     1.86044  | 1.81736  |  1.90511  |                0          |                         1        |
| delayed_peak_atom | prompt_peak              | hgb_full                      |     0.924265 | 0.899885 |  0.965616 |               -0.629692   |                         0.339506 |
| delayed_peak_atom | prompt_peak              | hgb_no_samples_0_3            |     0.926745 | 0.898944 |  0.961747 |               -0.627213   |                         0.314815 |
| delayed_peak_atom | prompt_peak              | early_late_gated_full         |     1.11029  | 1.07847  |  1.13988  |               -0.443671   |                         0.382716 |
| delayed_peak_atom | prompt_peak              | cnn1d_full                    |     1.1819   | 1.15162  |  1.21698  |               -0.372058   |                         0.438272 |
| delayed_peak_atom | prompt_peak              | mlp_full                      |     1.29043  | 1.25328  |  1.32506  |               -0.263526   |                         0.444444 |
| delayed_peak_atom | prompt_peak              | s02b_global_template_timewalk |     1.55396  | 1.51842  |  1.58724  |                0          |                         1        |
| pair              | B4-B6                    | hgb_no_samples_0_3            |     1.09763  | 1.04736  |  1.15158  |               -0.131672   |                         0.792    |
| pair              | B4-B6                    | hgb_full                      |     1.1084   | 1.06384  |  1.16508  |               -0.120897   |                         0.792    |
| pair              | B4-B6                    | early_late_gated_full         |     1.19651  | 1.15431  |  1.24491  |               -0.0327865  |                         0.792    |
| pair              | B4-B6                    | s02b_global_template_timewalk |     1.2293   | 1.18303  |  1.28367  |                0          |                         1        |
| pair              | B4-B6                    | cnn1d_full                    |     1.23537  | 1.19252  |  1.28969  |                0.006073   |                         0.84     |
| pair              | B4-B6                    | mlp_full                      |     1.59447  | 1.55012  |  1.64681  |                0.36517    |                         1.088    |
| pair              | B4-B8                    | hgb_full                      |     1.11606  | 1.06672  |  1.16132  |               -0.192733   |                         0.714286 |
| pair              | B4-B8                    | hgb_no_samples_0_3            |     1.12557  | 1.07535  |  1.16062  |               -0.183226   |                         0.721429 |
| pair              | B4-B8                    | early_late_gated_full         |     1.30262  | 1.27207  |  1.34569  |               -0.00617771 |                         0.785714 |
| pair              | B4-B8                    | s02b_global_template_timewalk |     1.30879  | 1.26679  |  1.35782  |                0          |                         1        |
| pair              | B4-B8                    | cnn1d_full                    |     1.32154  | 1.28835  |  1.35634  |                0.012751   |                         0.764286 |
| pair              | B4-B8                    | mlp_full                      |     1.59125  | 1.55146  |  1.63898  |                0.282458   |                         0.928571 |
| pair              | B6-B8                    | hgb_full                      |     0.957192 | 0.92474  |  1.00053  |               -0.121388   |                         0.877193 |
| pair              | B6-B8                    | hgb_no_samples_0_3            |     0.967374 | 0.935483 |  1.00155  |               -0.111206   |                         0.842105 |
| pair              | B6-B8                    | mlp_full                      |     1.0429   | 1.01054  |  1.08374  |               -0.0356849  |                         1        |
| pair              | B6-B8                    | s02b_global_template_timewalk |     1.07858  | 1.03917  |  1.1072   |                0          |                         1        |
| pair              | B6-B8                    | cnn1d_full                    |     1.11585  | 1.07672  |  1.15241  |                0.037265   |                         0.982456 |
| pair              | B6-B8                    | early_late_gated_full         |     1.15337  | 1.11557  |  1.18973  |                0.0747946  |                         1.08772  |
| phase_atom        | central_phase_6          | hgb_full                      |     0.843684 | 0.790098 |  0.899098 |               -0.561738   |                         0.758621 |
| phase_atom        | central_phase_6          | hgb_no_samples_0_3            |     0.857571 | 0.820815 |  0.905092 |               -0.547851   |                         0.758621 |
| phase_atom        | central_phase_6          | early_late_gated_full         |     1.0576   | 0.987167 |  1.12255  |               -0.347826   |                         0.586207 |
| phase_atom        | central_phase_6          | cnn1d_full                    |     1.1908   | 1.14171  |  1.26207  |               -0.214623   |                         0.62069  |
| phase_atom        | central_phase_6          | mlp_full                      |     1.35246  | 1.27036  |  1.42237  |               -0.0529649  |                         0.586207 |
| phase_atom        | central_phase_6          | s02b_global_template_timewalk |     1.40542  | 1.37519  |  1.49303  |                0          |                         1        |
| phase_atom        | early_phase_le5          | hgb_full                      |     0.74652  | 0.719924 |  0.77336  |               -0.71169    |                         0.805556 |
| phase_atom        | early_phase_le5          | hgb_no_samples_0_3            |     0.751356 | 0.725053 |  0.778275 |               -0.706854   |                         0.666667 |
| phase_atom        | early_phase_le5          | early_late_gated_full         |     0.881144 | 0.836489 |  0.909036 |               -0.577066   |                         0.555556 |
| phase_atom        | early_phase_le5          | cnn1d_full                    |     0.885608 | 0.853089 |  0.927607 |               -0.572602   |                         0.555556 |
| phase_atom        | early_phase_le5          | mlp_full                      |     1.03457  | 0.990123 |  1.08294  |               -0.423642   |                         0.611111 |
| phase_atom        | early_phase_le5          | s02b_global_template_timewalk |     1.45821  | 1.42291  |  1.49199  |                0          |                         1        |
| phase_atom        | late_phase_ge7           | hgb_no_samples_0_3            |     1.36247  | 1.33311  |  1.3927   |               -0.505343   |                         0.415238 |
| phase_atom        | late_phase_ge7           | hgb_full                      |     1.3751   | 1.34088  |  1.41297  |               -0.49271    |                         0.430476 |
| phase_atom        | late_phase_ge7           | early_late_gated_full         |     1.62511  | 1.59336  |  1.66208  |               -0.242702   |                         0.550476 |
| phase_atom        | late_phase_ge7           | mlp_full                      |     1.63217  | 1.59445  |  1.6639   |               -0.235643   |                         0.620952 |
| phase_atom        | late_phase_ge7           | cnn1d_full                    |     1.68892  | 1.65301  |  1.73612  |               -0.178896   |                         0.630476 |
| phase_atom        | late_phase_ge7           | s02b_global_template_timewalk |     1.86781  | 1.81751  |  1.90563  |                0          |                         1        |
| q_template_atom   | q_template_sse_bulk      | hgb_no_samples_0_3            |     1.20309  | 1.1718   |  1.23994  |               -0.53439    |                         0.373358 |
| q_template_atom   | q_template_sse_bulk      | hgb_full                      |     1.2078   | 1.18114  |  1.2467   |               -0.529687   |                         0.371482 |
| q_template_atom   | q_template_sse_bulk      | early_late_gated_full         |     1.44162  | 1.41381  |  1.47071  |               -0.295862   |                         0.515947 |
| q_template_atom   | q_template_sse_bulk      | mlp_full                      |     1.50804  | 1.47814  |  1.5377   |               -0.229442   |                         0.587242 |
| q_template_atom   | q_template_sse_bulk      | cnn1d_full                    |     1.536    | 1.50414  |  1.56507  |               -0.201478   |                         0.604128 |
| q_template_atom   | q_template_sse_bulk      | s02b_global_template_timewalk |     1.73748  | 1.70261  |  1.77694  |                0          |                         1        |
| q_template_atom   | q_template_sse_top10     | hgb_no_samples_0_3            |     0.994321 | 0.930456 |  1.07243  |               -0.475118   |                         1.51111  |
| q_template_atom   | q_template_sse_top10     | hgb_full                      |     1.00069  | 0.951988 |  1.07806  |               -0.468753   |                         1.71111  |
| q_template_atom   | q_template_sse_top10     | cnn1d_full                    |     1.07509  | 1.01981  |  1.12449  |               -0.394347   |                         0.955556 |
| q_template_atom   | q_template_sse_top10     | mlp_full                      |     1.1258   | 1.05392  |  1.19921  |               -0.343635   |                         0.977778 |
| q_template_atom   | q_template_sse_top10     | early_late_gated_full         |     1.13719  | 1.04691  |  1.20487  |               -0.332246   |                         1.08889  |
| q_template_atom   | q_template_sse_top10     | s02b_global_template_timewalk |     1.46944  | 1.43669  |  1.51847  |                0          |                         1        |
| run_family_atom   | early                    | hgb_no_samples_0_3            |     1.14529  | 1.08659  |  1.2047   |               -0.454222   |                         0.55914  |
| run_family_atom   | early                    | hgb_full                      |     1.15445  | 1.09197  |  1.21418  |               -0.445064   |                         0.537634 |
| run_family_atom   | early                    | early_late_gated_full         |     1.32439  | 1.25091  |  1.39596  |               -0.27512    |                         0.645161 |
| run_family_atom   | early                    | mlp_full                      |     1.39984  | 1.33441  |  1.47168  |               -0.199669   |                         0.72043  |
| run_family_atom   | early                    | cnn1d_full                    |     1.46633  | 1.4184   |  1.53002  |               -0.133183   |                         0.870968 |
| run_family_atom   | early                    | s02b_global_template_timewalk |     1.59951  | 1.54864  |  1.64578  |                0          |                         1        |
| run_family_atom   | late                     | hgb_full                      |     1.25212  | 1.16726  |  1.34296  |               -0.302127   |                         0.509091 |
| run_family_atom   | late                     | hgb_no_samples_0_3            |     1.26945  | 1.17703  |  1.35008  |               -0.284798   |                         0.454545 |
| run_family_atom   | late                     | early_late_gated_full         |     1.30887  | 1.2186   |  1.39582  |               -0.245375   |                         0.6      |
| run_family_atom   | late                     | mlp_full                      |     1.42422  | 1.31166  |  1.50225  |               -0.130022   |                         0.727273 |
| run_family_atom   | late                     | cnn1d_full                    |     1.51572  | 1.42049  |  1.60188  |               -0.0385254  |                         0.854545 |
| run_family_atom   | late                     | s02b_global_template_timewalk |     1.55424  | 1.50364  |  1.64636  |                0          |                         1        |
| run_family_atom   | middle                   | hgb_no_samples_0_3            |     1.16405  | 1.13394  |  1.20475  |               -0.603874   |                         0.433255 |
| run_family_atom   | middle                   | hgb_full                      |     1.17163  | 1.13322  |  1.20609  |               -0.596291   |                         0.459016 |
| run_family_atom   | middle                   | early_late_gated_full         |     1.44446  | 1.40494  |  1.48779  |               -0.323465   |                         0.540984 |
| run_family_atom   | middle                   | mlp_full                      |     1.45106  | 1.41507  |  1.4911   |               -0.316863   |                         0.576112 |
| run_family_atom   | middle                   | cnn1d_full                    |     1.47646  | 1.44285  |  1.51354  |               -0.29146    |                         0.57377  |
| run_family_atom   | middle                   | s02b_global_template_timewalk |     1.76792  | 1.73189  |  1.79862  |                0          |                         1        |

## Controls and Leakage

| method                                     | family                  |   sigma68_ns |   ci_low |   ci_high |   delta_vs_traditional_ns |
|:-------------------------------------------|:------------------------|-------------:|---------:|----------:|--------------------------:|
| hgb_run_family_control                     | run_family_control      |      1.20895 |  1.16163 |   1.26455 |               -0.483405   |
| ridge_run_family_control                   | run_family_control      |      1.37784 |  1.32348 |   1.43124 |               -0.314514   |
| mlp_full_shuffled                          | shuffled_target_control |      1.68084 |  1.50967 |   1.94496 |               -0.0115167  |
| cnn1d_only_samples_0_3_shuffled            | shuffled_target_control |      1.69009 |  1.4859  |   1.93431 |               -0.00226448 |
| ridge_only_samples_0_3_shuffled            | shuffled_target_control |      1.69394 |  1.48184 |   1.9539  |                0.00158147 |
| cnn1d_no_samples_0_3_shuffled              | shuffled_target_control |      1.69582 |  1.55717 |   1.87713 |                0.00346186 |
| early_late_gated_only_samples_0_3_shuffled | shuffled_target_control |      1.70283 |  1.48451 |   1.98343 |                0.0104735  |
| ridge_no_samples_0_3_shuffled              | shuffled_target_control |      1.70512 |  1.53373 |   1.95723 |                0.0127667  |
| mlp_only_samples_0_3_shuffled              | shuffled_target_control |      1.70834 |  1.4905  |   1.97149 |                0.0159862  |
| early_late_gated_full_shuffled             | shuffled_target_control |      1.70835 |  1.52378 |   1.9461  |                0.015988   |
| ridge_full_shuffled                        | shuffled_target_control |      1.71029 |  1.52767 |   1.9963  |                0.0179297  |
| early_late_gated_no_samples_0_3_shuffled   | shuffled_target_control |      1.71247 |  1.52373 |   2.01737 |                0.020116   |
| mlp_no_samples_0_3_shuffled                | shuffled_target_control |      1.72279 |  1.54527 |   1.98447 |                0.0304342  |
| hgb_no_samples_0_3_shuffled                | shuffled_target_control |      1.72662 |  1.538   |   1.9881  |                0.0342617  |
| hgb_full_shuffled                          | shuffled_target_control |      1.73575 |  1.55593 |   2.02606 |                0.0433881  |
| cnn1d_full_shuffled                        | shuffled_target_control |      1.73729 |  1.55256 |   2.04688 |                0.0449353  |
| hgb_only_samples_0_3_shuffled              | shuffled_target_control |      1.75071 |  1.55297 |   2.0216  |                0.0583548  |

|   heldout_run | check                                                   |       value | pass   |
|--------------:|:--------------------------------------------------------|------------:|:-------|
|            58 | train_heldout_run_overlap                               |  0          | True   |
|            58 | train_heldout_event_id_overlap                          |  0          | True   |
|            58 | feature_audit                                           |  0          | True   |
|            58 | shuffled_target_worse:ridge_full                        |  0.27286    | True   |
|            58 | shuffled_target_worse:hgb_full                          |  0.516824   | True   |
|            58 | shuffled_target_worse:mlp_full                          |  0.132983   | True   |
|            58 | shuffled_target_worse:cnn1d_full                        | -0.187846   | False  |
|            58 | shuffled_target_worse:early_late_gated_full             | -0.0886761  | False  |
|            58 | shuffled_target_worse:ridge_no_samples_0_3              |  0.239155   | True   |
|            58 | shuffled_target_worse:hgb_no_samples_0_3                |  0.40038    | True   |
|            58 | shuffled_target_worse:mlp_no_samples_0_3                |  0.289163   | True   |
|            58 | shuffled_target_worse:cnn1d_no_samples_0_3              |  0.290936   | True   |
|            58 | shuffled_target_worse:early_late_gated_no_samples_0_3   | -0.00508619 | False  |
|            58 | shuffled_target_worse:ridge_only_samples_0_3            |  0.155518   | True   |
|            58 | shuffled_target_worse:hgb_only_samples_0_3              |  0.393895   | True   |
|            58 | shuffled_target_worse:mlp_only_samples_0_3              | -0.0810085  | False  |
|            58 | shuffled_target_worse:cnn1d_only_samples_0_3            |  0.0194806  | True   |
|            58 | shuffled_target_worse:early_late_gated_only_samples_0_3 | -0.00234445 | False  |
|            59 | train_heldout_run_overlap                               |  0          | True   |
|            59 | train_heldout_event_id_overlap                          |  0          | True   |
|            59 | feature_audit                                           |  0          | True   |
|            59 | shuffled_target_worse:ridge_full                        |  0.266079   | True   |
|            59 | shuffled_target_worse:hgb_full                          |  0.510636   | True   |
|            59 | shuffled_target_worse:mlp_full                          |  0.203804   | True   |
|            59 | shuffled_target_worse:cnn1d_full                        |  0.192738   | True   |
|            59 | shuffled_target_worse:early_late_gated_full             |  0.340502   | True   |
|            59 | shuffled_target_worse:ridge_no_samples_0_3              |  0.259806   | True   |
|            59 | shuffled_target_worse:hgb_no_samples_0_3                |  0.491989   | True   |
|            59 | shuffled_target_worse:mlp_no_samples_0_3                |  0.253384   | True   |
|            59 | shuffled_target_worse:cnn1d_no_samples_0_3              |  0.17836    | True   |
|            59 | shuffled_target_worse:early_late_gated_no_samples_0_3   |  0.227098   | True   |
|            59 | shuffled_target_worse:ridge_only_samples_0_3            |  0.219423   | True   |
|            59 | shuffled_target_worse:hgb_only_samples_0_3              |  0.439034   | True   |
|            59 | shuffled_target_worse:mlp_only_samples_0_3              |  0.28723    | True   |
|            59 | shuffled_target_worse:cnn1d_only_samples_0_3            |  0.284632   | True   |
|            59 | shuffled_target_worse:early_late_gated_only_samples_0_3 |  0.0633876  | True   |
|            60 | train_heldout_run_overlap                               |  0          | True   |
|            60 | train_heldout_event_id_overlap                          |  0          | True   |
|            60 | feature_audit                                           |  0          | True   |
|            60 | shuffled_target_worse:ridge_full                        |  0.0531545  | True   |
|            60 | shuffled_target_worse:hgb_full                          |  0.346724   | True   |
|            60 | shuffled_target_worse:mlp_full                          | -0.181879   | False  |
|            60 | shuffled_target_worse:cnn1d_full                        | -0.0987794  | False  |
|            60 | shuffled_target_worse:early_late_gated_full             | -0.0635019  | False  |
|            60 | shuffled_target_worse:ridge_no_samples_0_3              |  0.0570082  | True   |
|            60 | shuffled_target_worse:hgb_no_samples_0_3                |  0.324735   | True   |
|            60 | shuffled_target_worse:mlp_no_samples_0_3                |  0.11094    | True   |
|            60 | shuffled_target_worse:cnn1d_no_samples_0_3              |  0.0140589  | True   |
|            60 | shuffled_target_worse:early_late_gated_no_samples_0_3   | -0.155641   | False  |
|            60 | shuffled_target_worse:ridge_only_samples_0_3            |  0.0279267  | True   |
|            60 | shuffled_target_worse:hgb_only_samples_0_3              |  0.296625   | True   |
|            60 | shuffled_target_worse:mlp_only_samples_0_3              | -0.14416    | False  |
|            60 | shuffled_target_worse:cnn1d_only_samples_0_3            | -0.139372   | False  |
|            60 | shuffled_target_worse:early_late_gated_only_samples_0_3 |  0.0106256  | True   |
|            61 | train_heldout_run_overlap                               |  0          | True   |
|            61 | train_heldout_event_id_overlap                          |  0          | True   |
|            61 | feature_audit                                           |  0          | True   |
|            61 | shuffled_target_worse:ridge_full                        |  0.960053   | True   |
|            61 | shuffled_target_worse:hgb_full                          |  1.07849    | True   |
|            61 | shuffled_target_worse:mlp_full                          |  0.845251   | True   |
|            61 | shuffled_target_worse:cnn1d_full                        |  0.973594   | True   |
|            61 | shuffled_target_worse:early_late_gated_full             |  0.748888   | True   |
|            61 | shuffled_target_worse:ridge_no_samples_0_3              |  0.895037   | True   |
|            61 | shuffled_target_worse:hgb_no_samples_0_3                |  1.01552    | True   |
|            61 | shuffled_target_worse:mlp_no_samples_0_3                |  0.985309   | True   |
|            61 | shuffled_target_worse:cnn1d_no_samples_0_3              |  0.787106   | True   |
|            61 | shuffled_target_worse:early_late_gated_no_samples_0_3   |  0.888317   | True   |
|            61 | shuffled_target_worse:ridge_only_samples_0_3            |  0.860335   | True   |
|            61 | shuffled_target_worse:hgb_only_samples_0_3              |  1.04339    | True   |
|            61 | shuffled_target_worse:mlp_only_samples_0_3              |  0.933617   | True   |
|            61 | shuffled_target_worse:cnn1d_only_samples_0_3            |  0.898089   | True   |
|            61 | shuffled_target_worse:early_late_gated_only_samples_0_3 |  0.877354   | True   |
|            62 | train_heldout_run_overlap                               |  0          | True   |
|            62 | train_heldout_event_id_overlap                          |  0          | True   |
|            62 | feature_audit                                           |  0          | True   |
|            62 | shuffled_target_worse:ridge_full                        |  0.265741   | True   |
|            62 | shuffled_target_worse:hgb_full                          |  0.555672   | True   |
|            62 | shuffled_target_worse:mlp_full                          |  0.306404   | True   |
|            62 | shuffled_target_worse:cnn1d_full                        |  0.103775   | True   |
|            62 | shuffled_target_worse:early_late_gated_full             |  0.247944   | True   |
|            62 | shuffled_target_worse:ridge_no_samples_0_3              |  0.310935   | True   |
|            62 | shuffled_target_worse:hgb_no_samples_0_3                |  0.515088   | True   |
|            62 | shuffled_target_worse:mlp_no_samples_0_3                |  0.325643   | True   |
|            62 | shuffled_target_worse:cnn1d_no_samples_0_3              |  0.207137   | True   |
|            62 | shuffled_target_worse:early_late_gated_no_samples_0_3   |  0.215948   | True   |
|            62 | shuffled_target_worse:ridge_only_samples_0_3            |  0.289632   | True   |
|            62 | shuffled_target_worse:hgb_only_samples_0_3              |  0.494144   | True   |
|            62 | shuffled_target_worse:mlp_only_samples_0_3              |  0.407683   | True   |
|            62 | shuffled_target_worse:cnn1d_only_samples_0_3            |  0.210974   | True   |
|            62 | shuffled_target_worse:early_late_gated_only_samples_0_3 |  0.326308   | True   |
|            63 | train_heldout_run_overlap                               |  0          | True   |
|            63 | train_heldout_event_id_overlap                          |  0          | True   |
|            63 | feature_audit                                           |  0          | True   |
|            63 | shuffled_target_worse:ridge_full                        |  0.231844   | True   |
|            63 | shuffled_target_worse:hgb_full                          |  0.289061   | True   |
|            63 | shuffled_target_worse:mlp_full                          |  0.133303   | True   |
|            63 | shuffled_target_worse:cnn1d_full                        |  0.113522   | True   |
|            63 | shuffled_target_worse:early_late_gated_full             |  0.2471     | True   |
|            63 | shuffled_target_worse:ridge_no_samples_0_3              |  0.183359   | True   |
|            63 | shuffled_target_worse:hgb_no_samples_0_3                |  0.310122   | True   |
|            63 | shuffled_target_worse:mlp_no_samples_0_3                |  0.308372   | True   |
|            63 | shuffled_target_worse:cnn1d_no_samples_0_3              |  0.222547   | True   |
|            63 | shuffled_target_worse:early_late_gated_no_samples_0_3   |  0.0513211  | True   |
|            63 | shuffled_target_worse:ridge_only_samples_0_3            |  0.10803    | True   |
|            63 | shuffled_target_worse:hgb_only_samples_0_3              |  0.300383   | True   |
|            63 | shuffled_target_worse:mlp_only_samples_0_3              |  0.197744   | True   |
|            63 | shuffled_target_worse:cnn1d_only_samples_0_3            |  0.141348   | True   |
|            63 | shuffled_target_worse:early_late_gated_only_samples_0_3 |  0.0955524  | True   |
|            65 | train_heldout_run_overlap                               |  0          | True   |
|            65 | train_heldout_event_id_overlap                          |  0          | True   |
|            65 | feature_audit                                           |  0          | True   |
|            65 | shuffled_target_worse:ridge_full                        |  0.115124   | True   |
|            65 | shuffled_target_worse:hgb_full                          |  0.303955   | True   |
|            65 | shuffled_target_worse:mlp_full                          |  0.0847907  | True   |
|            65 | shuffled_target_worse:cnn1d_full                        | -0.0360743  | False  |
|            65 | shuffled_target_worse:early_late_gated_full             |  0.132404   | True   |
|            65 | shuffled_target_worse:ridge_no_samples_0_3              |  0.118056   | True   |
|            65 | shuffled_target_worse:hgb_no_samples_0_3                |  0.288273   | True   |
|            65 | shuffled_target_worse:mlp_no_samples_0_3                |  0.304116   | True   |
|            65 | shuffled_target_worse:cnn1d_no_samples_0_3              |  0.0643688  | True   |
|            65 | shuffled_target_worse:early_late_gated_no_samples_0_3   |  0.0337132  | True   |
|            65 | shuffled_target_worse:ridge_only_samples_0_3            |  0.102474   | True   |
|            65 | shuffled_target_worse:hgb_only_samples_0_3              |  0.381961   | True   |
|            65 | shuffled_target_worse:mlp_only_samples_0_3              |  0.109358   | True   |
|            65 | shuffled_target_worse:cnn1d_only_samples_0_3            |  0.0539888  | True   |
|            65 | shuffled_target_worse:early_late_gated_only_samples_0_3 |  0.142218   | True   |

Shuffled-target controls are interpreted as leakage/stability sentinels. If a shuffled row matches or beats its nominal model in a fold, the nominal model/mask is not treated as mechanistically interpretable for that fold even if its pooled width is favorable.

## Systematics and Caveats

- The q-template and baseline atoms are proxy labels, not external detector truth. They localize failure modes but cannot alone prove a physical cause.
- Samples 0-3 overlap the median baseline definition. Gains from `only_samples_0_3` are therefore especially suspect and are judged against shuffled-target and run-family controls.
- Run 58 has low held-out statistics, so pooled inference uses run-block resampling rather than treating all events as exchangeable.
- The target is same-event downstream closure, not an absolute beam clock. Improvements are relative timing-closure improvements.
- HGB can exploit piecewise nuisance structure efficiently; this is useful operationally but less interpretable than a constrained analytic timewalk term.

## Verdict

Winner in `result.json`: `hgb_no_samples_0_3`. The pooled winner is hgb_no_samples_0_3; its gain over the fold-local traditional method is -0.522 ns. The best no-samples-0-3 model (hgb_no_samples_0_3) is within -0.004 ns of the best full-waveform model, while the best only-samples-0-3 model is 1.201 ns, so early baseline samples are not necessary for the main gain. The highest traditional-width atom is saturation_atom=amp_top5_proxy, identifying the strongest failure-map target. 12 shuffled-target checks beat their nominal fold model and are retained as caveats.

The atom map shows the main gain is not a CNN/MLP feature-learning breakthrough: the best model is tree-based and remains competitive when samples 0-3 are removed. The new gated architecture is useful as a diagnostic because it tests early/late branch routing, but it does not win the pooled benchmark. The dominant residual-risk atoms remain q-template/baseline/high-amplitude morphology rather than a single neural architecture weakness.

## Reproducibility

Command:

```bash
/home/billy/anaconda3/bin/python scripts/p03i_1781038014_1254_657842ac_phase_local_failure_map.py --config configs/p03i_1781038014_1254_657842ac_phase_local_failure_map.json
```

Artifacts include `reproduction_match_table.csv`, `heldout_run_summary.csv`, `pooled_run_block_summary.csv`, `pairwise_residuals.csv`, `event_atoms.csv`, `atom_failure_map.csv`, `per_atom_winners.csv`, `model_diagnostics.csv`, `leakage_checks.csv`, figures, `input_sha256.csv`, `result.json`, and `manifest.json`.
