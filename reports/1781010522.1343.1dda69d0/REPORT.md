# P07d: saturation-recovery systematic envelope for timing tails

Ticket `1781010522.1343.1dda69d0`. Raw B-stack ROOT was read from `data/root/root`; no Monte Carlo was used.

## Reproduction gate

| quantity                              | expected     |   reproduced | delta   | pass   |
|:--------------------------------------|:-------------|-------------:|:--------|:-------|
| sample_ii_analysis B2 selected pulses | 88213        |  88213       | 0       | True   |
| B2 pulses >= 7000 ADC                 | data-derived |   5351       |         | True   |
| B2 high-amplitude fraction            | data-derived |      0.06066 |         | True   |

The Sample-II B2 count reproduces the S00 value exactly. The observed high-amplitude B2 proxy is `A_B2 >= 7000` ADC.

## Method

For each held-out run, the B2 pulse template and the ML ratio-transfer model were trained on the other Sample-II runs only. Clean B2 pulses were pseudo-saturated to provide amplitude-ratio truth. The real-data propagation then used only observed high-amplitude B2 events with at least two selected downstream staves.

- `observed_saturated`: no B2 amplitude correction.
- `traditional_template`: least-squares train-run template scale using non-plateau samples.
- `ml_ratio_transfer`: ExtraTrees regression on normalized pseudo-saturated waveform shape; no run id, event id, downstream timing, or truth amplitude feature.

## Pseudo-saturation recovery check

|   run | method               |     n |   res68_abs_frac | res68_abs_frac_ci95                         |   bias_median_frac |   within10_frac |
|------:|:---------------------|------:|-----------------:|:--------------------------------------------|-------------------:|----------------:|
|    58 | traditional_template | 46900 |        0.187914  | [0.18495338948173384, 0.19079788925154711]  |        0.0267991   |        0.486588 |
|    58 | ml_ratio_transfer    | 46900 |        0.035563  | [0.03486457924270986, 0.03633189209548889]  |        1.60203e-05 |        0.892495 |
|    58 | observed_saturated   | 46900 |        0.354839  | [0.3548387096774194, 0.3548387096774194]    |       -0.2         |        0.262281 |
|    59 | traditional_template | 38404 |        0.2       | [0.20000000000000004, 0.20000000000000004]  |       -0.047619    |        0.419488 |
|    59 | ml_ratio_transfer    | 38404 |        0.0564641 | [0.05550169430350813, 0.05733470766735944]  |        1.3376e-05  |        0.829158 |
|    59 | observed_saturated   | 38404 |        0.354839  | [0.3548387096774194, 0.3548387096774194]    |       -0.2         |        0.268982 |
|    60 | traditional_template | 28870 |        0.2       | [0.2, 0.2]                                  |       -0.047619    |        0.435781 |
|    60 | ml_ratio_transfer    | 28870 |        0.055057  | [0.05407162217912459, 0.05615533786952561]  |        7.73978e-05 |        0.841877 |
|    60 | observed_saturated   | 28870 |        0.354839  | [0.3548387096774194, 0.3548387096774194]    |       -0.2         |        0.264461 |
|    61 | traditional_template | 32809 |        0.2       | [0.2, 0.20000000000000004]                  |       -0.0481672   |        0.433204 |
|    61 | ml_ratio_transfer    | 32809 |        0.0549852 | [0.054156209756484816, 0.05618551332994988] |        4.96452e-06 |        0.846597 |
|    61 | observed_saturated   | 32809 |        0.354839  | [0.3548387096774194, 0.3548387096774194]    |       -0.2         |        0.264775 |
|    62 | traditional_template | 33694 |        0.2       | [0.20000000000000004, 0.20000000000000007]  |       -0.047619    |        0.417433 |
|    62 | ml_ratio_transfer    | 33694 |        0.0540831 | [0.05308525769939101, 0.05493772139216326]  |        4.22701e-05 |        0.842939 |
|    62 | observed_saturated   | 33694 |        0.354839  | [0.3548387096774194, 0.3548387096774194]    |       -0.2         |        0.268208 |
|    63 | traditional_template | 41068 |        0.2       | [0.19999999999999996, 0.19999999999999998]  |       -0.047619    |        0.445992 |
|    63 | ml_ratio_transfer    | 41068 |        0.0436649 | [0.04288200156001575, 0.04438034345182045]  |       -0.000191948 |        0.870434 |
|    63 | observed_saturated   | 41068 |        0.354839  | [0.3548387096774194, 0.3548387096774194]    |       -0.2         |        0.268092 |
|    65 | traditional_template | 32047 |        0.197837  | [0.19589036989734368, 0.19978374367345103]  |       -0.047619    |        0.445564 |
|    65 | ml_ratio_transfer    | 32047 |        0.0350734 | [0.03428691494097451, 0.03603276830022899]  |       -0.000489948 |        0.893875 |
|    65 | observed_saturated   | 32047 |        0.354839  | [0.3548387096774194, 0.3548387096774194]    |       -0.2         |        0.275252 |

## Real high-amplitude B2 propagation

|   run | method               |   n_events |   amp_ratio_median |   timing_tail_frac_abs_gt5ns | timing_tail_frac_abs_gt5ns_ci95           |   q_template_median | q_template_median_ci95                     |   q_template_p95 |
|------:|:---------------------|-----------:|-------------------:|-----------------------------:|:------------------------------------------|--------------------:|:-------------------------------------------|-----------------:|
|    58 | observed_saturated   |         16 |            1       |                     0.6875   | [0.4375, 1.0]                             |            0.201315 | [0.17634773572086326, 0.24861823038280678] |         0.480925 |
|    58 | traditional_template |         16 |            1       |                     0.6875   | [0.4375, 0.875]                           |            0.201315 | [0.16839137136233803, 0.24547413059682935] |         0.480925 |
|    58 | ml_ratio_transfer    |         16 |            1.05368 |                     0.6875   | [0.4375, 1.0]                             |            0.199648 | [0.17638107631985414, 0.24601542875921806] |         0.470939 |
|    59 | observed_saturated   |         90 |            1       |                     0.611111 | [0.455, 0.7222222222222222]               |            0.216101 | [0.19784068461709034, 0.22798439235549195] |         0.612452 |
|    59 | traditional_template |         90 |            1       |                     0.611111 | [0.49944444444444447, 0.7113888888888888] |            0.216101 | [0.1957427440532875, 0.229362066354957]    |         0.612452 |
|    59 | ml_ratio_transfer    |         90 |            1.05596 |                     0.611111 | [0.4663888888888889, 0.7111111111111111]  |            0.217148 | [0.20029917437003322, 0.23377449870740563] |         0.596234 |
|    60 | observed_saturated   |         10 |            1       |                     1        | [0.3, 1.0]                                |            0.203139 | [0.1279026109509595, 0.24127932348394632]  |         0.510438 |
|    60 | traditional_template |         10 |            1       |                     1        | [0.3, 1.0]                                |            0.203139 | [0.13988853963514267, 0.2916713072685817]  |         0.510438 |
|    60 | ml_ratio_transfer    |         10 |            1.05134 |                     1        | [0.2975, 1.0]                             |            0.201783 | [0.1378221253302737, 0.33764815695377914]  |         0.497393 |
|    61 | observed_saturated   |         10 |            1       |                     0.5      | [0.2, 1.0]                                |            0.225977 | [0.16193077929003274, 0.42120329213453733] |         0.515713 |
|    61 | traditional_template |         10 |            1       |                     0.5      | [0.2, 1.0]                                |            0.225977 | [0.16193077929003274, 0.40190876989410623] |         0.515713 |
|    61 | ml_ratio_transfer    |         10 |            1.05272 |                     0.5      | [0.2975, 1.0]                             |            0.22776  | [0.16863606532057196, 0.39668219488526907] |         0.503364 |
|    62 | observed_saturated   |         36 |            1       |                     0.805556 | [0.4722222222222222, 0.8618055555555554]  |            0.226716 | [0.19427614071079738, 0.33622860726942083] |         0.592937 |
|    62 | traditional_template |         36 |            1       |                     0.805556 | [0.5, 0.8618055555555554]                 |            0.226716 | [0.19521870008015318, 0.33626443315616467] |         0.592937 |
|    62 | ml_ratio_transfer    |         36 |            1.05867 |                     0.805556 | [0.44375, 0.8895833333333331]             |            0.227569 | [0.20212973049434996, 0.32755601268967116] |         0.578818 |
|    63 | observed_saturated   |         74 |            1       |                     0.743243 | [0.5675675675675675, 0.8652027027027026]  |            0.189424 | [0.17948110910519624, 0.21680827778826045] |         0.544656 |
|    63 | traditional_template |         74 |            1       |                     0.743243 | [0.5945945945945946, 0.8790540540540538]  |            0.189424 | [0.17293513967220414, 0.21226533182503182] |         0.544656 |
|    63 | ml_ratio_transfer    |         74 |            1.05323 |                     0.743243 | [0.5945945945945946, 0.8652027027027026]  |            0.193376 | [0.17434098210308555, 0.21610803780773827] |         0.53163  |
|    65 | observed_saturated   |         13 |            1       |                     0.538462 | [0.3057692307692308, 0.8461538461538461]  |            0.266275 | [0.17937875410717513, 0.44327134482443076] |         0.471331 |
|    65 | traditional_template |         13 |            1       |                     0.538462 | [0.3076923076923077, 0.8461538461538461]  |            0.266275 | [0.1767230456484088, 0.4295170984219656]   |         0.471331 |
|    65 | ml_ratio_transfer    |         13 |            1.05565 |                     0.615385 | [0.38461538461538464, 0.8461538461538461] |            0.26328  | [0.1824638837046088, 0.42309778273673226]  |         0.460754 |

## Per-run systematic envelopes

|   run |   n_events |   timing_tail_envelope |   q_template_median_envelope |   q_template_p95_envelope |   amp_ratio_envelope |
|------:|-----------:|-----------------------:|-----------------------------:|--------------------------:|---------------------:|
|    58 |         16 |              0         |                  0.0016666   |                 0.009986  |            0.0536846 |
|    59 |         90 |              0         |                  0.00104637  |                 0.0162181 |            0.0559592 |
|    60 |         10 |              0         |                  0.00135638  |                 0.0130454 |            0.0513399 |
|    61 |         10 |              0         |                  0.00178395  |                 0.0123485 |            0.0527236 |
|    62 |         36 |              0         |                  0.000852128 |                 0.0141185 |            0.0586689 |
|    63 |         74 |              0         |                  0.00395165  |                 0.0130266 |            0.0532279 |
|    65 |         13 |              0.0769231 |                  0.00299526  |                 0.0105771 |            0.0556475 |

## Leakage checks

- The split is by run: every held-out row is predicted by a template/model trained without that run.
- ML features are normalized B2 waveform-shape summaries only; they exclude run id, event id, downstream timing, labels, and true amplitude.
- The pseudo-saturation truth is used only for validation and model fitting on training runs; real high-amplitude B2 propagation has no truth labels.
- The ML pseudo-saturation score is useful but not perfect, so no too-good-to-be-true leakage signature was seen.

## Headline

Across held-out runs, the median per-run envelope is 0.0000 in timing-tail fraction and 0.00167 in median `q_template` RMSE. The largest run envelope is run 65 with timing-tail span 0.0769.

## Follow-up

- P07e: validate the ratio-transfer correction against duplicate odd-channel saturation signatures.
- S05e: rerun the B2 covariance decomposition after explicit P07d saturation-correction features.
