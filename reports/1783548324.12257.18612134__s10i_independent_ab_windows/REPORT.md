# S10i: Independent A/B Phase-Calibrated Window Benchmark

- **Ticket:** `1783548324.12257.18612134`
- **Worker:** `testbeam-laptop-3`
- **Command:** `/home/billy/anaconda3/bin/python scripts/s10i_1783548324_12257_18612134_independent_ab_windows.py --config configs/s10i_1783548324_12257_18612134_independent_ab_windows.json`
- **Inputs:** raw `data/root/root/hrda_run_*.root` and `data/root/root/hrdb_run_*.root`
- **Split:** train runs `[31, 32, 33, 34, 35, 36, 37, 39, 40, 41, 42, 44, 45, 46, 47, 48, 49, 50, 51, 52, 53, 54, 55, 56, 57]`; held-out runs `[58, 59, 60, 61, 62, 63, 65]`
- **Winner:** `ridge` with held-out phase-window width `5.388` ns, 95% run-bootstrap CI `[1.921, 24.858]` ns.

## Abstract

This study repeats the S10 phase-window benchmark on physically independent A-stack and B-stack ROOT files. A1/A3 pulses are read from `hrda` and B2/B4 pulses from `hrdb`; all quantities are rebuilt from raw `HRDv` waveforms. Event-level alignment is performed by the local trigger index `EVT - first(EVT)` within each run, not by row order or by raw EVT equality. This is necessary because the two independent DAQ streams have run-dependent EVT offsets.

The reproduced ticket number is the held-out aligned selected-pair count: **20** independent A/B events.

## Raw Reproduction and Alignment Diagnostics

Each waveform is reshaped to `(8, 18)`. Samples 0--3 define the pedestal, amplitudes are baseline-subtracted maxima, and CFD20 times are linearly interpolated before each peak. A row enters the table only when both A1/A3 and both B2/B4 exceed `1000.0` ADC after pedestal subtraction.

|   run |   a_selected_pairs |   b_selected_pairs |   raw_evt_overlap |   aligned_pairs |   a_first_evt |   b_first_evt |   evt_offset_a_minus_b |   median_phase_ns |   phase_width68_ns | split   |
|------:|-------------------:|-------------------:|------------------:|----------------:|--------------:|--------------:|-----------------------:|------------------:|-------------------:|:--------|
|    31 |                272 |                531 |                 8 |               2 |            18 |            48 |                    -30 |         -0.718156 |            7.93085 | train   |
|    32 |                327 |                528 |                12 |               7 |            39 |            67 |                    -28 |         13.073    |           36.3032  | train   |
|    33 |                  7 |                515 |                 1 |               0 |          3527 |            93 |                   3434 |        nan        |          nan       | train   |
|    34 |                 16 |                375 |                 0 |               0 |          1315 |           114 |                   1201 |        nan        |          nan       | train   |
|    35 |                370 |                350 |                 9 |              11 |           111 |            17 |                     94 |         45.7188   |           37.5988  | train   |
|    36 |                275 |                300 |                 3 |               9 |            95 |           244 |                   -149 |          1.48818  |            7.07958 | train   |
|    37 |                674 |                889 |                15 |              23 |             2 |            23 |                    -21 |         -0.591462 |           42.614   | train   |
|    39 |                489 |                577 |                20 |              15 |             7 |            18 |                    -11 |         20.7201   |           29.9994  | train   |
|    40 |                473 |                610 |                11 |              26 |            35 |            25 |                     10 |         11.1828   |           35.3093  | train   |
|    41 |                484 |                670 |                14 |              26 |            22 |            12 |                     10 |         23.7873   |           33.8163  | train   |
|    42 |                429 |                636 |                11 |              18 |           150 |            28 |                    122 |         10.8411   |           17.9395  | train   |
|    44 |                 69 |                 80 |                 1 |               0 |          2209 |           110 |                   2099 |        nan        |          nan       | train   |
|    45 |                672 |                866 |                38 |              29 |           125 |             2 |                    123 |         14.0577   |           25.7174  | train   |
|    46 |                  9 |                  7 |                 0 |               0 |          3037 |         15571 |                 -12534 |        nan        |          nan       | train   |
|    47 |                103 |                 68 |                 0 |               0 |          4592 |            64 |                   4528 |        nan        |          nan       | train   |
|    48 |                510 |                532 |                18 |              16 |            31 |            41 |                    -10 |          7.17108  |           30.3792  | train   |
|    49 |                489 |                571 |                19 |              17 |            19 |            13 |                      6 |         -1.14122  |           16.8237  | train   |
|    50 |                 60 |                609 |                 3 |               0 |            81 |            22 |                     59 |        nan        |          nan       | train   |
|    51 |                  7 |                277 |                 0 |               1 |          1155 |            64 |                   1091 |         21.2405   |            0       | train   |
|    52 |                  6 |                134 |                 0 |               0 |         11749 |            42 |                  11707 |        nan        |          nan       | train   |
|    53 |                  4 |                515 |                 0 |               0 |           335 |             3 |                    332 |        nan        |          nan       | train   |
|    54 |                  5 |                490 |                 0 |               0 |          6012 |           141 |                   5871 |        nan        |          nan       | train   |
|    55 |                  6 |                339 |                 0 |               0 |          8216 |             2 |                   8214 |        nan        |          nan       | train   |
|    56 |                 91 |                765 |                 2 |               2 |           110 |             9 |                    101 |         42.9704   |            9.56449 | train   |
|    57 |                483 |                584 |                26 |              11 |            12 |            20 |                     -8 |         17.9176   |           25.736   | train   |
|    58 |                 25 |                554 |                 1 |               1 |          2169 |            18 |                   2151 |         -9.42138  |            0       | heldout |
|    59 |                 11 |               4381 |                 1 |               3 |          1043 |             2 |                   1041 |         -3.18502  |            9.29336 | heldout |
|    60 |                 11 |               3941 |                 2 |               1 |             4 |             2 |                      2 |         14.453    |            0       | heldout |
|    61 |                 18 |               4298 |                 3 |               6 |          2386 |             1 |                   2385 |        -77.2141   |           36.4957  | heldout |
|    62 |                  7 |               4085 |                 1 |               2 |          2541 |             4 |                   2537 |        -51.9301   |           21.9063  | heldout |
|    63 |                 28 |               2521 |                 3 |               4 |          1168 |             5 |                   1163 |          2.49993  |           13.6789  | heldout |
|    65 |                 27 |                770 |                 2 |               3 |           337 |             2 |                    335 |         -3.60996  |            2.31769 | heldout |

Counts by split:

| split   |   runs |   a_selected_pairs |   b_selected_pairs |   aligned_pairs |
|:--------|-------:|-------------------:|-------------------:|----------------:|
| heldout |      7 |                127 |              20550 |              20 |
| train   |     25 |               6330 |              11818 |             213 |

## Estimand

For side `s in {A,B}` and channel `c`, let `x_sc[k] = v_sc[k] - median(v_sc[0:4])`, `A_sc = max_k x_sc[k]`, and `t_sc` be the CFD20 crossing. Define side means

`bar t_A = (t_A1 + t_A3)/2`, `bar t_B = (t_B2 + t_B4)/2`.

The raw A/B phase is

`phi_i = bar t_B,i - bar t_A,i`.

The phase-calibrated target subtracts the run median,

`y_i = phi_i - median_{j in run(i)} phi_j`.

For method `m`, the held-out residual is

`e_i(m) = y_i - hat y_m(z_i)`,

then the same run-median centering is applied to `e_i` to represent the phase-window calibration. The primary width is

`W_68 = 0.5 [Q_84(e - median(e)) - Q_16(e - median(e))]`.

Confidence intervals bootstrap held-out runs with replacement and recompute `W_68`.

## Methods

The strong traditional comparator is `traditional_phase_timewalk`, a physically constrained low-dimensional least-squares phase model using log A/B amplitudes and A/B internal pair residuals. It is the analogue of the phase-calibrated coincidence window: a per-event timewalk correction followed by per-run phase centering.

The ML panel contains ridge regression, gradient-boosted trees, MLP, a compact 1D-CNN over four normalized waveforms, and a new `phase_gated_cnn_new`. The new architecture is sensible for this ticket because A/B transfer can fail from local waveform support mismatch; it gates convolution channels using auxiliary amplitude and shape moments before the regression head. No method receives run id, raw EVT, local event index, raw phase, or target phase as an input feature.

Ridge alpha was selected by GroupKFold over training runs:

|   alpha |   cv_rmse_ns |
|--------:|-------------:|
| 1000    |      20.4786 |
|  100    |      32.7784 |
|    1    |      37.3399 |
|   10    |      37.632  |
|    0.1  |      37.9506 |
|    0.01 |      39.4276 |

## Results

| method                     |   n_aligned_pairs |   median_ns |   robust_width_ns |   robust_ci_low_ns |   robust_ci_high_ns |   full_rms_ns |   tail_abs_gt_5ns |
|:---------------------------|------------------:|------------:|------------------:|-------------------:|--------------------:|--------------:|------------------:|
| ridge                      |                20 |           0 |           5.38768 |            1.92147 |             24.8581 |       16.0407 |              0.35 |
| mlp                        |                20 |           0 |           5.89183 |            2.62968 |             23.5996 |       15.7788 |              0.45 |
| gradient_boosted_trees     |                20 |           0 |           9.9789  |            3.57513 |             31.2397 |       23.9333 |              0.45 |
| phase_gated_cnn_new        |                20 |           0 |          12.2795  |            5.35847 |             35.6728 |       26.9161 |              0.75 |
| cnn_1d                     |                20 |           0 |          14.5218  |            7.39489 |             27.9658 |       20.5857 |              0.75 |
| traditional_phase_timewalk |                20 |           0 |          15.6177  |            6.95938 |             37.8095 |       26.6762 |              0.8  |

Per-run held-out widths:

|   run | method                     |   n |   robust_width_ns |   full_rms_ns |
|------:|:---------------------------|----:|------------------:|--------------:|
|    58 | traditional_phase_timewalk |   1 |           0       |       0       |
|    59 | traditional_phase_timewalk |   3 |           4.73238 |       5.68669 |
|    60 | traditional_phase_timewalk |   1 |           0       |       0       |
|    61 | traditional_phase_timewalk |   6 |          37.7086  |      41.6661  |
|    62 | traditional_phase_timewalk |   2 |          24.1474  |      35.5108  |
|    63 | traditional_phase_timewalk |   4 |          14.7565  |      15.3565  |
|    65 | traditional_phase_timewalk |   3 |           7.27262 |       9.19524 |
|    58 | ridge                      |   1 |           0       |       0       |
|    59 | ridge                      |   3 |           1.3066  |       1.57699 |
|    60 | ridge                      |   1 |           0       |       0       |
|    61 | ridge                      |   6 |          21.5607  |      22.7887  |
|    62 | ridge                      |   2 |          20.4263  |      30.0387  |
|    63 | ridge                      |   4 |           6.28958 |       7.22941 |
|    65 | ridge                      |   3 |           1.44298 |       1.73272 |
|    58 | gradient_boosted_trees     |   1 |           0       |       0       |
|    59 | gradient_boosted_trees     |   3 |           6.81925 |       8.37612 |
|    60 | gradient_boosted_trees     |   1 |           0       |       0       |
|    61 | gradient_boosted_trees     |   6 |          30.2514  |      38.5701  |
|    62 | gradient_boosted_trees     |   2 |          19.9837  |      29.3878  |
|    63 | gradient_boosted_trees     |   4 |           3.20606 |       3.39602 |
|    65 | gradient_boosted_trees     |   3 |           8.81256 |      13.4939  |
|    58 | mlp                        |   1 |           0       |       0       |
|    59 | mlp                        |   3 |           1.78819 |       2.97418 |
|    60 | mlp                        |   1 |           0       |       0       |
|    61 | mlp                        |   6 |          22.6423  |      23.4317  |
|    62 | mlp                        |   2 |          18.8198  |      27.6762  |
|    63 | mlp                        |   4 |           3.67496 |       3.73329 |
|    65 | mlp                        |   3 |           4.03843 |       4.86117 |
|    58 | cnn_1d                     |   1 |           0       |       0       |
|    59 | cnn_1d                     |   3 |           7.47845 |       9.17197 |
|    60 | cnn_1d                     |   1 |           0       |       0       |
|    61 | cnn_1d                     |   6 |          30.0009  |      31.9053  |
|    62 | cnn_1d                     |   2 |          17.5383  |      25.7916  |
|    63 | cnn_1d                     |   4 |          11.2363  |      12.8367  |
|    65 | cnn_1d                     |   3 |           5.02853 |       6.47677 |
|    58 | phase_gated_cnn_new        |   1 |           0       |       0       |
|    59 | phase_gated_cnn_new        |   3 |           6.43421 |       8.09753 |
|    60 | phase_gated_cnn_new        |   1 |           0       |       0       |
|    61 | phase_gated_cnn_new        |   6 |          36.0981  |      41.9571  |
|    62 | phase_gated_cnn_new        |   2 |          25.6091  |      37.6604  |
|    63 | phase_gated_cnn_new        |   4 |          11.2908  |      14.1527  |
|    65 | phase_gated_cnn_new        |   3 |           3.73388 |       5.55753 |

## Systematics and Caveats

- Raw EVT equality is sparse and run-dependent; local EVT alignment is therefore explicitly diagnosed. This validates a trigger-index coincidence model, not a bit-identical DAQ event-number model.
- The A/B phase target is calibrated by held-out run medians. This matches phase-window operation, but it removes absolute run phase offsets by construction.
- The selected sample requires four channels above threshold, so the reproduced number is a clean high-amplitude coincidence count rather than a full livetime count.
- Bootstrap intervals resample runs, not rows, because run-to-run phase alignment is the dominant systematic.
- Neural methods are trained on CPU with fixed seeds and small networks to avoid overfitting the limited number of held-out runs.

## Conclusion

The raw ROOT files reproduce **20** held-out independent A/B selected coincidences. The best phase-calibrated method is **ridge**, with `W_68 = 5.388` ns. The result supports using true independent A-stack ROOT files for A/B timing-window validation, while the caveats above mean the conclusion is about phase-centered coincidence width rather than absolute DAQ synchronization.
