# S29B: Forced-trigger pedestal drift truth cross-check

## Abstract

Ticket `1783828686.21844.219b682b` asks for a forced-trigger or low-threshold pedestal-truth cross-check of whether four-sample pedestal IQR/slope proxies under-cover slow baseline memory in saturated B-stave timing extraction. I rescanned the accessible B-stack raw ROOT mirror, reproduced the canonical selected-pulse count directly from `h101/HRDv`, and then benchmarked a strong traditional four-sample proxy against ridge, gradient-boosted trees, MLP, 1D-CNN, and a new pretrigger-gated residual CNN under run-heldout splitting with run-block bootstrap confidence intervals.

The direct non-beam truth audit found `0` entries with `TRIGGER != 1`, `0` forced/random/pedestal filename-token hits, and `53` files with an exact `TRIGGER` branch. Therefore the direct electronics-pedestal estimand is not identifiable in the mounted mirror; the benchmark below is explicitly a raw-pretrigger fallback stress test, not a proof from true forced-trigger pedestal rows. The winner written to `result.json` is **mlp**.

## Raw ROOT Reproduction

The reproduction gate reads raw files from `/home/billy/ccb-data/extracted/root/root`, reshapes `HRDv` into 8 channels by 18 samples, subtracts the median of samples 0--3 channel-by-channel, and counts B2/B4/B6/B8 even-channel pulses with corrected maximum amplitude above 1000 ADC.

|   run | group              |   events_total |   events_selected |   selected_pulses |
|------:|:-------------------|---------------:|------------------:|------------------:|
|    31 | sample_i_calib     |          39990 |             27078 |             27871 |
|    32 | sample_i_calib     |          41921 |             27461 |             28240 |
|    33 | sample_i_calib     |          57173 |             47911 |             48737 |
|    34 | sample_i_calib     |          39765 |             33500 |             34118 |
|    35 | sample_i_calib     |          27786 |             11141 |             11667 |
|    36 | sample_i_calib     |          21764 |              9930 |             10391 |
|    37 | sample_i_calib     |          50513 |             23174 |             24537 |
|    39 | sample_i_calib     |          30321 |             13329 |             14218 |
|    40 | sample_i_calib     |          32613 |             13763 |             14708 |
|    41 | sample_i_calib     |          33997 |             15140 |             16146 |
|    42 | sample_i_calib     |          33972 |             17132 |             18112 |
|    44 | sample_i_analysis  |           4294 |              1912 |              2038 |
|    45 | sample_i_analysis  |          48181 |             23013 |             24333 |
|    46 | sample_i_analysis  |           1441 |               677 |               687 |
|    47 | sample_i_analysis  |          10970 |              5161 |              5276 |
|    48 | sample_i_analysis  |          31713 |             13185 |             14000 |
|    49 | sample_i_analysis  |          32354 |             13937 |             14815 |
|    50 | sample_i_analysis  |          44804 |             34257 |             35217 |
|    51 | sample_i_analysis  |          20569 |             14295 |             14740 |
|    52 | sample_i_analysis  |          10005 |              6933 |              7152 |
|    53 | sample_i_analysis  |          39612 |             31386 |             32200 |
|    54 | sample_i_analysis  |          37413 |             29665 |             30440 |
|    55 | sample_i_analysis  |          24416 |             16841 |             17387 |
|    56 | sample_i_analysis  |          51823 |             38932 |             40148 |
|    57 | sample_i_analysis  |          31284 |             12939 |             13833 |
|    58 | sample_ii_analysis |          34141 |             15920 |             16781 |
|    59 | sample_ii_analysis |          42303 |             13863 |             21377 |
|    60 | sample_ii_analysis |          36074 |             10140 |             17029 |
|    61 | sample_ii_analysis |          36535 |             11287 |             18965 |
|    62 | sample_ii_analysis |          37584 |             11912 |             19089 |
|    63 | sample_ii_analysis |          37030 |             14781 |             18817 |
|    64 | sample_ii_calib    |          35943 |             12103 |             14630 |
|    65 | sample_ii_analysis |          38424 |             11904 |             13038 |

Total selected pulses: `640737`; registered expectation: `640737`; delta: `0`.

## Pedestal-Truth Availability Audit

| quantity | value |
|---|---:|
| B-stack raw ROOT files scanned | 53 |
| files with exact `TRIGGER` branch | 53 |
| entries with `TRIGGER != 1` | 0 |
| forced/random/pedestal filename-token hits | 0 |
| trigger-like branch-name files | 53 |

The machine-readable audit is `pedestal_truth_source_audit.csv`. Since no direct forced/random or low-threshold B-stack pedestal truth source is present, the estimand is demoted to an operational fallback label built entirely from raw physics-event pretrigger and duplicate-readout sidebands.

## Estimands and Equations

Let \(w_{ejs}\) be the baseline-subtracted even-channel waveform for event \(e\), B-stave \(j\), sample \(s\), and \(Q'_{ej}\) the positive charge of the duplicate odd readout. The S29A timing/shape stress target is

\[ h_e = \operatorname{clip}_{[-4,4]}\left(1 - \frac{\sum_j Q_{ej}}{\max(\sum_j Q'_{ej},1)}\right) + 0.18\frac{\sum_{j,s\ge9}\max(w_{ejs},0)}{\max(\sum_j Q_{ej},1)} + 0.015(\bar{s}_{\mathrm{peak},e}-5). \]

A saturated/near-knee event is assigned the fallback slow-memory truth label when

\[ Y_e = \mathbb{1}\{ S_e=1, |h_e| \ge q_{0.80}(|h|\mid S=1, R\in\mathcal{R}_{train}) \}. \]

The four-sample pedestal proxy is

\[ P_e = \mathbb{1}\{ \mathrm{IQR}(x_{0:3}) \ge q_{0.75}^{train}(\mathrm{IQR}) \lor |x_3-x_0| \ge q_{0.75}^{train}(|x_3-x_0|) \}. \]

The under-coverage stress set is \(U_e=Y_e(1-P_e)\): saturated events with a large timing/shape stress target that the four pretrigger samples would not flag.

## Split, Models, and Bootstrap

Calibration runs train the models; all Sample-I and Sample-II analysis runs are held out as complete run blocks. Confidence intervals resample held-out runs with replacement. The traditional comparator uses only saturation counts plus the four-sample IQR and slope proxies in a robust Huber model. Learned comparators are ridge, gradient-boosted trees, MLP, 1D-CNN, and the new pretrigger-gated residual CNN. Run IDs, event IDs, and duplicate odd-readout charges are excluded from learned inputs.

## Head-to-Head Benchmark

| method                        |      n |     res68 | res68_ci95                                  |       mae | mae_ci95                                   |        bias | bias_ci95                                      |
|:------------------------------|-------:|----------:|:--------------------------------------------|----------:|:-------------------------------------------|------------:|:-----------------------------------------------|
| mlp                           | 159183 | 0.0269746 | [0.023879964834414423, 0.03065680029809475] | 0.0639799 | [0.0505099352432859, 0.07495372108235988]  | -0.0124358  | [-0.013412954933941368, -0.011498404815793051] |
| gradient_boosted_trees        | 159183 | 0.0302681 | [0.026755614498205748, 0.03365643650560508] | 0.0733704 | [0.056754751522651144, 0.0885738698561195] | -0.00973759 | [-0.011348136837543649, -0.007933113372251577] |
| traditional_four_sample_proxy | 159183 | 0.0342991 | [0.029370847398731265, 0.04302141213876286] | 0.152528  | [0.12091294898235944, 0.18948060157625465] | -0.00411795 | [-0.00926883660805406, -0.0003679175036879694] |
| 1d_cnn                        | 159183 | 0.0594873 | [0.05048299193382262, 0.07170663591250778]  | 0.124475  | [0.10538050787661105, 0.14771343027072922] |  0.00263645 | [-0.0008430989682674465, 0.005142256438732139] |
| pretrigger_gated_residual_cnn | 159183 | 0.0818015 | [0.07084517055749893, 0.09660209924146536]  | 0.132829  | [0.11240897209907647, 0.15683530557763659] |  0.0435511  | [0.03873167110234498, 0.04982085484266282]     |
| ridge                         | 159183 | 0.15642   | [0.12963460172739902, 0.19654428822689665]  | 0.206292  | [0.17009030808226033, 0.24715199848800118] |  0.0181798  | [0.003983650111418844, 0.03294166479590017]    |

Primary score is held-out \(\sigma_{68}(|\hat h-h|)\); lower is better.

## Four-Sample Under-Coverage Stress Test

| method                        |   heldout_n |   saturated_n |   truth_n |   four_sample_proxy_flagged_truth_n |   undercovered_truth_n |   undercovered_truth_fraction |   undercovered_res68 | undercovered_res68_ci95                      |   undercovered_mae |
|:------------------------------|------------:|--------------:|----------:|------------------------------------:|-----------------------:|------------------------------:|---------------------:|:---------------------------------------------|-------------------:|
| mlp                           |      159183 |         55543 |     10562 |                                3527 |                   7035 |                      0.666067 |            0.0242441 | [0.022497670993208888, 0.026273606792688357] |          0.0246296 |
| 1d_cnn                        |      159183 |         55543 |     10562 |                                3527 |                   7035 |                      0.666067 |            0.0428311 | [0.04105959987044334, 0.04498219618439675]   |          0.0529145 |
| traditional_four_sample_proxy |      159183 |         55543 |     10562 |                                3527 |                   7035 |                      0.666067 |            0.0467777 | [0.03392978406723592, 0.10384821271923289]   |          0.0596248 |
| gradient_boosted_trees        |      159183 |         55543 |     10562 |                                3527 |                   7035 |                      0.666067 |            0.0487105 | [0.04661329844761315, 0.0512204247318955]    |          0.050989  |
| pretrigger_gated_residual_cnn |      159183 |         55543 |     10562 |                                3527 |                   7035 |                      0.666067 |            0.0604992 | [0.05891251683235166, 0.06264133918941021]   |          0.0618174 |
| ridge                         |      159183 |         55543 |     10562 |                                3527 |                   7035 |                      0.666067 |            0.230265  | [0.20620513406562474, 0.26837248673210623]   |          0.205621  |

The four-sample proxy flags `3527` of `10562` held-out slow-memory truth events. The unflagged fraction is `0.6661`, so the proxy materially under-covers this fallback stress label in saturated/near-knee timing extraction.

## Systematics and Caveats

* The strongest caveat is structural: no direct forced/random B-stack pedestal truth row is visible in the mounted ROOT mirror. The fallback label is a physics-event sideband, not an electronics pedestal label.
* The target is anchored by duplicate odd readout and by late-tail timing/shape stress; it is suitable for finding under-covered saturated timing pathologies, not for absolute energy calibration.
* Four pretrigger samples cannot observe baseline recovery outside the 180 ns digitizer window. The under-coverage fraction therefore measures a lower bound on slow-memory risk, not the complete electronics impulse response.
* Bootstrap intervals cover held-out run composition but not future detector operating modes, threshold settings, or front-end recovery constants.
* Neural models are intentionally compact for laptop reproducibility. A learned-model win should be interpreted as evidence that waveform context carries missing nuisance information, not as an adoption recommendation without dedicated forced-trigger data.

## Recommendation

Do not treat four-sample pedestal IQR/slope cuts as a complete saturation-memory truth veto. The selected winner is `mlp` for the machine-readable result, but the scientific conclusion is that a dedicated forced-trigger/low-threshold B-stack pedestal run remains required before saturated pulses can be promoted into precision timing tables without an explicit slow-baseline-memory systematic.
