# P04f Baseline-Excursion Charge-Bias Closure

- **Ticket:** `1781012700.777.722653c1`
- **Worker:** `testbeam-laptop-3`
- **Input:** raw `data/root/root/hrdb_run_*.root`; no Monte Carlo.
- **Target:** P04 paired odd-channel duplicate-readout positive charge.
- **Split:** leave-one-run-out over every P04 B-stack run; intervals are run-block bootstraps.

## Raw Reproduction Gate

P04 selected-pulse count was rebuilt from raw ROOT before fitting: `640,737` vs expected `640,737` (delta `+0`).
The valid duplicate-charge table has `640,482` rows after removing `255` invalid odd-target rows.

## Methods

- **Traditional:** P04 peak-to-charge, integral-to-charge, robust pretrigger-corrected integral, and amplitude-binned template-scale calibrators, all trained without the held-out run.
- **P04 ML reference:** compact MLP on the frozen P04 even-waveform feature set, retrained leave-one-run-out; the stored P04 HGB number is reported in the leakage audit.
- **P04f ML:** compact MLP residual model on even waveform samples plus P09a score/labels and S16-style baseline summaries.
- **S16 anchor:** prior S16 held-out pedestal MAE was `341.0` ADC traditional vs `48.9` ADC ML.

## Charge Bias By Stratum

| stratum                                   | method                   |      n |   bias_median_frac | bias_ci95                                       |   res68_abs_frac | res68_ci95                                 |   high_bias_tail_fraction | high_bias_tail_ci95                         |
|:------------------------------------------|:-------------------------|-------:|-------------------:|:------------------------------------------------|-----------------:|:-------------------------------------------|--------------------------:|:--------------------------------------------|
| all_valid                                 | integral_calibrated      | 640482 |       -0.0315953   | [-0.058142075353021044, -0.029415940182415137]  |        0.119626  | [0.11102063154619361, 0.15825173812345616] |                 0.116976  | [0.11046563603372833, 0.1604319356956366]   |
| all_valid                                 | robust_pretrigger_charge | 640482 |       -0.0315952   | [-0.057924113309617144, -0.028881643900599642]  |        0.119626  | [0.10843047062484353, 0.15751538294552572] |                 0.116974  | [0.1103205212716017, 0.16170984575262032]   |
| all_valid                                 | p04_frozen_mlp           | 640482 |       -0.40337     | [-0.535990574791422, -0.39307901728763606]      |        0.971805  | [0.9667217169803954, 0.9824465724923207]   |                 0.860789  | [0.8555369249559859, 0.8853759702439832]    |
| all_valid                                 | p04f_residual_mlp        | 640482 |       -0.000517695 | [-0.0020316610434120935, 0.0006624508645687194] |        0.0564025 | [0.05301865164759104, 0.06803397533696219] |                 0.0490771 | [0.04471489546259888, 0.06598400444236144]  |
| all_valid                                 | shuffled_residual_mlp    | 640482 |       -0.0403956   | [-0.05883716053965368, -0.03557854662834263]    |        0.167387  | [0.15984506874083076, 0.2293868920148792]  |                 0.209277  | [0.1919498942346479, 0.2913043433792182]    |
| baseline_excursion                        | integral_calibrated      |   4763 |        5.72626     | [5.510409622128606, 5.961456033687462]          |        7.05017   | [6.886551604408696, 7.2326921725621425]    |                 0.95801   | [0.9506660500306923, 0.9656060544028983]    |
| baseline_excursion                        | robust_pretrigger_charge |   4763 |        5.72625     | [5.503630700571137, 5.96258014918142]           |        7.05016   | [6.88252266514554, 7.23267638859202]       |                 0.95801   | [0.9499071439903, 0.9656740069871835]       |
| baseline_excursion                        | p04_frozen_mlp           |   4763 |        0.997601    | [0.6427972663956797, 1.7384483257252898]        |        3.07778   | [2.212416758580708, 4.915086529227546]     |                 0.900693  | [0.8793024511485857, 0.9199601312153306]    |
| baseline_excursion                        | p04f_residual_mlp        |   4763 |        0.0703155   | [0.041446800325130866, 0.09437426489254365]     |        0.453336  | [0.40907981013332145, 0.5084486399394974]  |                 0.56498   | [0.5285934541315229, 0.6089403744869383]    |
| baseline_excursion                        | shuffled_residual_mlp    |   4763 |        5.88371     | [5.365708836579957, 6.416646519398269]          |        8.28407   | [7.664035266359571, 9.174881838658674]     |                 0.961789  | [0.9558925274328142, 0.9682215160863784]    |
| novel_early_pretrigger                    | integral_calibrated      |  17232 |        2.32239     | [1.0304225577805979, 3.1718358351830975]        |        4.53256   | [3.854968067730017, 5.058416383802842]     |                 0.84227   | [0.8195761519700384, 0.8632213337530196]    |
| novel_early_pretrigger                    | robust_pretrigger_charge |  17232 |        2.32241     | [1.0408589955524266, 3.166798772498514]         |        4.53254   | [3.9214874184870316, 5.016474280822628]    |                 0.84227   | [0.821328780605039, 0.862395756310164]      |
| novel_early_pretrigger                    | p04_frozen_mlp           |  17232 |        4.39034     | [2.9389934979186387, 7.094879005131659]         |       22.954     | [10.101273474788236, 81.59178633353866]    |                 0.918988  | [0.9060876015877808, 0.9308004941581585]    |
| novel_early_pretrigger                    | p04f_residual_mlp        |  17232 |       -0.015748    | [-0.03338319754863423, 0.001509530075638098]    |        0.374023  | [0.3552504638377107, 0.3956058377169596]   |                 0.518048  | [0.49228227894136745, 0.5432154508725727]   |
| novel_early_pretrigger                    | shuffled_residual_mlp    |  17232 |        1.85504     | [0.9999248744911545, 2.918568229824177]         |        4.92781   | [3.926687558925836, 5.7883132856571935]    |                 0.863278  | [0.8346620123027136, 0.8872021486178816]    |
| matched_normal_for_baseline_excursion     | integral_calibrated      |   4762 |       -0.0771848   | [-0.08343122794330485, -0.07243728632596383]    |        0.150186  | [0.14482282769999333, 0.1549805484539701]  |                 0.108778  | [0.09383544479357164, 0.12229127401256959]  |
| matched_normal_for_baseline_excursion     | robust_pretrigger_charge |   4762 |       -0.0771818   | [-0.08446356195976316, -0.07289723572007534]    |        0.150184  | [0.14552638620347888, 0.15668585458509177] |                 0.108778  | [0.09487713711763024, 0.12454455432985617]  |
| matched_normal_for_baseline_excursion     | p04_frozen_mlp           |   4762 |       -0.805505    | [-0.8411418917779254, -0.7501160079633103]      |        0.974352  | [0.9678798887354368, 0.9790484135024934]   |                 0.907602  | [0.8934333854470847, 0.918643109363237]     |
| matched_normal_for_baseline_excursion     | p04f_residual_mlp        |   4762 |        0.000899615 | [-0.0018432943184535603, 0.0041950797983969085] |        0.057951  | [0.05221146705886259, 0.06453734515739111] |                 0.0312894 | [0.023954871121168685, 0.03792674953226266] |
| matched_normal_for_baseline_excursion     | shuffled_residual_mlp    |   4762 |       -0.0749075   | [-0.09200847085784543, -0.06294616836986228]    |        0.192953  | [0.16906521890687634, 0.21605026992147355] |                 0.216716  | [0.16723442899906213, 0.26746868696706605]  |
| matched_normal_for_novel_early_pretrigger | integral_calibrated      |  17232 |       -0.206343    | [-0.2098585289123097, -0.20162295887512877]     |        0.253452  | [0.2507083058873131, 0.2567605087911228]   |                 0.336235  | [0.324054197133839, 0.3500218307898184]     |
| matched_normal_for_novel_early_pretrigger | robust_pretrigger_charge |  17232 |       -0.206344    | [-0.20960145563095026, -0.20304292967570056]    |        0.253451  | [0.2505374360986967, 0.25624913633055996]  |                 0.336235  | [0.3224585947833383, 0.34886179792705246]   |
| matched_normal_for_novel_early_pretrigger | p04_frozen_mlp           |  17232 |        0.113465    | [-0.04400442760188067, 0.3359361744832391]      |        1.48136   | [1.106695698584921, 1.998326832768996]     |                 0.885388  | [0.875679538828446, 0.8941371090543466]     |
| matched_normal_for_novel_early_pretrigger | p04f_residual_mlp        |  17232 |       -0.0035599   | [-0.007989309423635262, 0.0011792335587492114]  |        0.07594   | [0.06695367434145122, 0.08836745808180078] |                 0.0788649 | [0.07001402436888356, 0.08617983184812796]  |
| matched_normal_for_novel_early_pretrigger | shuffled_residual_mlp    |  17232 |       -0.182286    | [-0.20623859046018359, -0.1559484148882611]     |        0.317062  | [0.29112062235224084, 0.3511282679387661]  |                 0.473131  | [0.4099546002162936, 0.5394781806705355]    |

## Matched-Stratum Deltas

Controls are sampled within the same run, stave, amplitude bin, and saturation bin.

| anomaly_stratum        | control_stratum                           | method                                           |   n_anomaly |   n_control |   delta_bias_median_frac |   delta_res68_abs_frac |   delta_high_bias_tail_fraction | delta_res68_ci95                          |
|:-----------------------|:------------------------------------------|:-------------------------------------------------|------------:|------------:|-------------------------:|-----------------------:|--------------------------------:|:------------------------------------------|
| baseline_excursion     | matched_normal_for_baseline_excursion     | peak_charge_calibrated                           |        4763 |        4762 |               11.5489    |              13.3204   |                      0.701596   | [13.100593235626006, 13.609335221404308]  |
| baseline_excursion     | matched_normal_for_baseline_excursion     | integral_calibrated                              |        4763 |        4762 |                5.80344   |               6.89999  |                      0.849232   | [6.750562649852688, 7.08250298323667]     |
| baseline_excursion     | matched_normal_for_baseline_excursion     | robust_pretrigger_charge                         |        4763 |        4762 |                5.80343   |               6.89998  |                      0.849232   | [6.727043055505714, 7.071913307798538]    |
| baseline_excursion     | matched_normal_for_baseline_excursion     | template_fit_calibrated                          |        4763 |        4762 |                6.22373   |               9.92251  |                      0.581059   | [9.434122107725635, 10.561681001737648]   |
| baseline_excursion     | matched_normal_for_baseline_excursion     | p04_frozen_mlp                                   |        4763 |        4762 |                1.80311   |               2.10343  |                     -0.00690901 | [1.1172651256797563, 3.909377718004566]   |
| baseline_excursion     | matched_normal_for_baseline_excursion     | p04f_residual_mlp                                |        4763 |        4762 |                0.0694159 |               0.395385 |                      0.533691   | [0.35155155940269966, 0.4505445162376692] |
| baseline_excursion     | matched_normal_for_baseline_excursion     | shuffled_residual_mlp                            |        4763 |        4762 |                5.95862   |               8.09112  |                      0.745073   | [7.482531284438346, 8.842417119759281]    |
| baseline_excursion     | best_traditional_same_stratum             | p04_frozen_mlp_minus_robust_pretrigger_charge    |        4763 |        4763 |               -4.72865   |              -3.97238  |                     -0.0573168  | [None, None]                              |
| baseline_excursion     | best_traditional_same_stratum             | p04f_residual_mlp_minus_robust_pretrigger_charge |        4763 |        4763 |               -5.65593   |              -6.59683  |                     -0.39303    | [None, None]                              |
| novel_early_pretrigger | matched_normal_for_novel_early_pretrigger | peak_charge_calibrated                           |       17232 |       17232 |                5.76198   |               7.7107   |                      0.223015   | [7.500161315136071, 7.913941320326002]    |
| novel_early_pretrigger | matched_normal_for_novel_early_pretrigger | integral_calibrated                              |       17232 |       17232 |                2.52873   |               4.2791   |                      0.506035   | [3.65952732482999, 4.873444358898346]     |
| novel_early_pretrigger | matched_normal_for_novel_early_pretrigger | robust_pretrigger_charge                         |       17232 |       17232 |                2.52875   |               4.27909  |                      0.506035   | [3.5921982524342266, 4.794970639475039]   |
| novel_early_pretrigger | matched_normal_for_novel_early_pretrigger | template_fit_calibrated                          |       17232 |       17232 |               -1.0898    |               1.78953  |                     -0.0142758  | [-0.27524495724692544, 4.66780563653868]  |
| novel_early_pretrigger | matched_normal_for_novel_early_pretrigger | p04_frozen_mlp                                   |       17232 |       17232 |                4.27688   |              21.4727   |                      0.0336003  | [7.575363801516609, 69.37428283249307]    |
| novel_early_pretrigger | matched_normal_for_novel_early_pretrigger | p04f_residual_mlp                                |       17232 |       17232 |               -0.0121881 |               0.298083 |                      0.439183   | [0.28144759493837, 0.3198935708236726]    |
| novel_early_pretrigger | matched_normal_for_novel_early_pretrigger | shuffled_residual_mlp                            |       17232 |       17232 |                2.03733   |               4.61075  |                      0.390146   | [3.746400468400283, 5.360362884504537]    |
| novel_early_pretrigger | best_traditional_same_stratum             | p04_frozen_mlp_minus_template_fit_calibrated     |       17232 |       17232 |                4.54982   |              19.9974   |                      0.0512999  | [None, None]                              |
| novel_early_pretrigger | best_traditional_same_stratum             | p04f_residual_mlp_minus_template_fit_calibrated  |       17232 |       17232 |                0.143732  |              -2.58257  |                     -0.34964    | [None, None]                              |

## Leakage Audit

- Leave-one-run-out overlap count: `0`.
- Feature matrices exclude run id, event ids, odd-channel target samples, and target charge.
- Shuffled-residual MLP all-valid res68: `0.1674` vs P04f residual MLP `0.0564`.
- P04 original heldout duplicate-charge ML res68 was `0.0151`; the very small duplicate-readout ML errors are therefore treated as electronics closure, not deposited-energy truth.

## Finding

Baseline-excursion rows do shift traditional robust-charge closure: matched-control res68 delta is 6.9000 and high-bias-tail delta is 0.8492. Early-pretrigger rows show res68 delta 4.2791. Across all valid rows the best traditional method is robust_pretrigger_charge at res68 0.1196; P04f residual MLP is 0.0564. Within baseline-excursion rows, P04f residual MLP minus best traditional res68 is -6.5968. The anomaly strata are therefore not harmless for traditional charge closure, but the ML gain remains a duplicate-readout electronics closure.

## Artifacts

`result.json`, `manifest.json`, `input_sha256.csv`, `charge_bias_summary.csv`, `stratum_deltas.csv`, `by_run_metrics.csv`, `fold_audit.csv`, `counts_by_run.csv`, and `predictions_sample.csv`.
