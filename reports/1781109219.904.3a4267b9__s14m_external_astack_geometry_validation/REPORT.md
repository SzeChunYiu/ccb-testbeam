# S14m: external A-stack geometry validation of S14f saturation stress bands

## Abstract

This study asks whether the S14f geometry-stable saturated B-stack correction bands transfer to an external A-stack detector handle. The B-stack raw ROOT reproduction gate passes exactly at 640,737 selected B2/B4/B6/B8 pulses. The external-transfer winner is **gradient_boosted_trees**, with score 0.028004 and run-bootstrap 95% CI [0.023907923437978453, 0.03373965555862854]. The score combines held-out saturated B-stack energy-proxy resolution with the absolute run-level correlation to A-stack charge instability, so a method wins only if it remains accurate and does not track an external A-stack nuisance.

## 1. Raw ROOT Reproduction

The B-stack count was rebuilt directly from `h101/HRDv` in `data/root/root`. For each configured run and B channel, the baseline is the median of samples 0--3; a pulse is selected when the baseline-subtracted maximum exceeds 1000 ADC.

| Quantity | Expected | Reproduced | Delta | Pass |
|---|---:|---:|---:|:---|
| B-stack selected pulses | 640,737 | 640,737 | +0 | true |

Per-run reproduction excerpt:

| run | events_total | selected_pulses |
| --- | --- | --- |
| 31  | 39990        | 27871           |
| 32  | 41921        | 28240           |
| 33  | 57173        | 48737           |
| 34  | 39765        | 34118           |
| 35  | 27786        | 11667           |
| 36  | 21764        | 10391           |
| 37  | 50513        | 24537           |
| 39  | 30321        | 14218           |
| 40  | 32613        | 14708           |
| 41  | 33997        | 16146           |
| 42  | 33972        | 18112           |
| 44  | 4294         | 2038            |
| 45  | 48181        | 24333           |
| 46  | 1441         | 687             |
| 47  | 10970        | 5276            |
| 48  | 31713        | 14000           |
| 49  | 32354        | 14815           |
| 50  | 44804        | 35217           |
| 51  | 20569        | 14740           |
| 52  | 10005        | 7152            |
| 53  | 39612        | 32200           |
| 54  | 37413        | 30440           |
| 55  | 24416        | 17387           |
| 56  | 51823        | 40148           |
| 57  | 31284        | 13833           |
| 58  | 34141        | 16781           |
| 59  | 42303        | 21377           |
| 60  | 36074        | 17029           |
| 61  | 36535        | 18965           |
| 62  | 37584        | 19089           |
| 63  | 37030        | 18817           |
| 64  | 35943        | 14630           |
| 65  | 38424        | 13038           |

## 2. External A-stack Handle

The A-stack handle is independently rebuilt from `hrda_run_*.root` using channels A1 and A3. The external nuisance variable is the run-level fractional interquartile width of selected A-stack charge,

\[
I_A(r)=\frac{Q_{75}(Q_A\mid r)-Q_{25}(Q_A\mid r)}{\operatorname{median}(Q_A\mid r)} ,
\]

with the selected-event support and A1/A3 balance retained as diagnostics. This handle is not used to train any S14f method; it is an external transfer stress variable.

| run | current_family | a_events | a_both_fraction | a_charge_median | a_charge_iqr_frac | a_asym_abs_median |
| --- | --- | --- | --- | --- | --- | --- |
| 31  | high_20nA      | 900      | 0.30222         | 18754           | 0.714             | 0.95228           |
| 32  | high_20nA      | 964      | 0.33921         | 18626           | 0.78619           | 0.94735           |
| 33  | high_20nA      | 54       | 0.12963         | 15616           | 0.7319            | 0.98312           |
| 34  | high_20nA      | 52       | 0.30769         | 21018           | 0.78497           | 0.94327           |
| 35  | high_20nA      | 1111     | 0.33303         | 19000           | 0.77258           | 0.94707           |
| 36  | high_20nA      | 844      | 0.32583         | 19296           | 0.76171           | 0.95292           |
| 37  | high_20nA      | 1973     | 0.34161         | 19899           | 0.77054           | 0.95178           |
| 39  | high_20nA      | 1297     | 0.37702         | 20696           | 0.74468           | 0.93414           |
| 40  | high_20nA      | 1313     | 0.36024         | 20441           | 0.77809           | 0.94357           |
| 41  | high_20nA      | 1330     | 0.36391         | 19910           | 0.83828           | 0.94034           |
| 42  | high_20nA      | 1229     | 0.34906         | 19560           | 0.76815           | 0.94139           |
| 44  | high_20nA      | 188      | 0.36702         | 19764           | 0.81403           | 0.93533           |
| 45  | high_20nA      | 1906     | 0.35257         | 19734           | 0.79664           | 0.94182           |
| 46  | low_2nA        | 37       | 0.24324         | 20997           | 0.70477           | 0.96864           |
| 47  | low_2nA        | 384      | 0.26823         | 17859           | 0.68933           | 0.96622           |
| 48  | high_20nA      | 1315     | 0.38783         | 20584           | 0.80473           | 0.92771           |
| 49  | high_20nA      | 1308     | 0.37385         | 20183           | 0.82628           | 0.93693           |
| 50  | high_20nA      | 221      | 0.27149         | 17333           | 0.958             | 0.96649           |
| 51  | high_20nA      | 60       | 0.11667         | 19366           | 0.73475           | 0.97618           |
| 52  | high_20nA      | 20       | 0.3             | 23132           | 0.8209            | 0.95068           |
| 53  | high_20nA      | 43       | 0.093023        | 12796           | 0.84102           | 0.96526           |
| 54  | high_20nA      | 54       | 0.092593        | 12266           | 0.75291           | 0.96738           |
| 55  | high_20nA      | 62       | 0.096774        | 15345           | 1.2463            | 0.96534           |
| 56  | high_20nA      | 296      | 0.30743         | 19931           | 0.93918           | 0.96189           |
| 57  | high_20nA      | 1274     | 0.37912         | 20112           | 0.84892           | 0.92309           |
| 58  | high_20nA      | 146      | 0.17123         | 17564           | 0.62611           | 0.9574            |
| 59  | high_20nA      | 52       | 0.21154         | 19278           | 0.73609           | 0.97295           |
| 60  | high_20nA      | 66       | 0.16667         | 17135           | 0.67676           | 0.95307           |
| 61  | high_20nA      | 68       | 0.26471         | 19996           | 0.49137           | 0.96322           |
| 62  | high_20nA      | 54       | 0.12963         | 15726           | 0.65423           | 0.95849           |
| 63  | high_20nA      | 200      | 0.14            | 19090           | 0.3736            | 0.97623           |
| 64  | high_20nA      | 161      | 0.099379        | 16776           | 0.6458            | 0.97843           |
| 65  | high_20nA      | 181      | 0.14917         | 17356           | 0.66732           | 0.97272           |

## 3. Benchmark Panel

The method panel is inherited from the S14f run-held-out saturated geometry benchmark: observed even charge, a strong traditional rising-edge template/range lookup, ridge regression, gradient-boosted trees, MLP, 1D-CNN, and the new template-residual MLP architecture. The S14f outputs supply per-run saturated energy-proxy resolution and method families; this study joins those per-run rows to the raw A-stack run summaries.

For method \(m\) and held-out run \(r\), let \(R_m(r)\) be S14f saturated energy-proxy \(R_{68}\) and \(I_A(r)\) the A-stack charge-width handle above. The external-transfer score is

\[
S_m=\bar R_m\left(1+\left|\rho_R(R_m(r),I_A(r))\right|\right),
\qquad
\bar R_m=\frac{\sum_r n_{m,r}R_m(r)}{\sum_r n_{m,r}} .
\]

The bootstrap resamples held-out runs with replacement and recomputes both terms. This penalizes a method whose apparent B-stack correction strength is coupled to independent A-stack charge instability.

| method                         | family                           | n_runs | n_saturated | mean_b_saturated_res68 | mean_b_saturated_res68_ci95 | abs_corr_b_res68_vs_astack_iqr | abs_corr_b_res68_vs_astack_iqr_ci95 | external_transfer_score | external_transfer_score_ci95 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| gradient_boosted_trees         | ml_tree                          | 21     | 106217      | 0.018767               | [0.017484, 0.021287]        | 0.49219                        | [0.26839, 0.72285]                  | 0.028004                | [0.023908, 0.03374]          |
| observed_even_charge           | traditional_observed             | 21     | 106217      | 0.021896               | [0.019835, 0.026769]        | 0.50591                        | [0.21488, 0.70522]                  | 0.032973                | [0.027717, 0.040704]         |
| p07_p04_corrected              | ml_p07_p04_duplicate             | 21     | 106217      | 0.027289               | [0.026681, 0.028691]        | 0.47215                        | [0.29834, 0.67999]                  | 0.040174                | [0.035825, 0.046136]         |
| template_residual_mlp          | neural_template_residual         | 21     | 106217      | 0.030977               | [0.029431, 0.035406]        | 0.63285                        | [0.48822, 0.77507]                  | 0.050581                | [0.044976, 0.05899]          |
| mlp                            | neural_tabular                   | 21     | 106217      | 0.04593                | [0.04325, 0.050006]         | 0.44452                        | [0.19414, 0.74411]                  | 0.066347                | [0.056379, 0.079827]         |
| ridge                          | ml_linear                        | 21     | 106217      | 0.054535               | [0.052175, 0.060162]        | 0.57534                        | [0.41904, 0.80896]                  | 0.085911                | [0.075765, 0.10104]          |
| traditional_template_corrected | traditional_rising_edge_template | 21     | 106217      | 0.081877               | [0.079983, 0.084922]        | 0.084696                       | [0.0082837, 0.49513]                | 0.088812                | [0.081875, 0.12263]          |
| 1d_cnn                         | neural_waveform                  | 21     | 106217      | 0.15232                | [0.14498, 0.16185]          | 0.38081                        | [0.051105, 0.65116]                 | 0.21032                 | [0.16483, 0.25089]           |

## 4. Run-Level Join Diagnostics

| run | current_family | method                 | n_saturated | saturated_energy_res68 | a_charge_iqr_frac | a_both_fraction |
| --- | --- | --- | --- | --- | --- | --- |
| 44  | high_20nA      | 1d_cnn                 | 334         | 0.17052                | 0.81403           | 0.36702         |
| 45  | high_20nA      | 1d_cnn                 | 5472        | 0.18237                | 0.79664           | 0.35257         |
| 46  | low_2nA        | 1d_cnn                 | 144         | 0.17528                | 0.70477           | 0.24324         |
| 47  | low_2nA        | 1d_cnn                 | 1268        | 0.18047                | 0.68933           | 0.26823         |
| 48  | high_20nA      | 1d_cnn                 | 1991        | 0.18386                | 0.80473           | 0.38783         |
| 49  | high_20nA      | 1d_cnn                 | 2154        | 0.18939                | 0.82628           | 0.37385         |
| 50  | high_20nA      | 1d_cnn                 | 19492       | 0.15375                | 0.958             | 0.27149         |
| 51  | high_20nA      | 1d_cnn                 | 7248        | 0.1544                 | 0.73475           | 0.11667         |
| 52  | high_20nA      | 1d_cnn                 | 3625        | 0.15383                | 0.8209            | 0.3             |
| 53  | high_20nA      | 1d_cnn                 | 13961       | 0.1362                 | 0.84102           | 0.093023        |
| 54  | high_20nA      | 1d_cnn                 | 13282       | 0.13644                | 0.75291           | 0.092593        |
| 55  | high_20nA      | 1d_cnn                 | 8330        | 0.14481                | 1.2463            | 0.096774        |
| 56  | high_20nA      | 1d_cnn                 | 21645       | 0.14899                | 0.93918           | 0.30743         |
| 57  | high_20nA      | 1d_cnn                 | 1843        | 0.18358                | 0.84892           | 0.37912         |
| 58  | high_20nA      | 1d_cnn                 | 1618        | 0.14992                | 0.62611           | 0.17123         |
| 59  | high_20nA      | 1d_cnn                 | 809         | 0.20897                | 0.73609           | 0.21154         |
| 60  | high_20nA      | 1d_cnn                 | 382         | 0.1671                 | 0.67676           | 0.16667         |
| 61  | high_20nA      | 1d_cnn                 | 420         | 0.19487                | 0.49137           | 0.26471         |
| 62  | high_20nA      | 1d_cnn                 | 513         | 0.18428                | 0.65423           | 0.12963         |
| 63  | high_20nA      | 1d_cnn                 | 1232        | 0.17449                | 0.3736            | 0.14            |
| 65  | high_20nA      | 1d_cnn                 | 454         | 0.1592                 | 0.66732           | 0.14917         |
| 44  | high_20nA      | gradient_boosted_trees | 334         | 0.027419               | 0.81403           | 0.36702         |
| 45  | high_20nA      | gradient_boosted_trees | 5472        | 0.023598               | 0.79664           | 0.35257         |
| 46  | low_2nA        | gradient_boosted_trees | 144         | 0.02473                | 0.70477           | 0.24324         |
| 47  | low_2nA        | gradient_boosted_trees | 1268        | 0.023598               | 0.68933           | 0.26823         |
| 48  | high_20nA      | gradient_boosted_trees | 1991        | 0.027108               | 0.80473           | 0.38783         |
| 49  | high_20nA      | gradient_boosted_trees | 2154        | 0.02795                | 0.82628           | 0.37385         |
| 50  | high_20nA      | gradient_boosted_trees | 19492       | 0.01748                | 0.958             | 0.27149         |
| 51  | high_20nA      | gradient_boosted_trees | 7248        | 0.01805                | 0.73475           | 0.11667         |
| 52  | high_20nA      | gradient_boosted_trees | 3625        | 0.018549               | 0.8209            | 0.3             |
| 53  | high_20nA      | gradient_boosted_trees | 13961       | 0.015283               | 0.84102           | 0.093023        |
| 54  | high_20nA      | gradient_boosted_trees | 13282       | 0.015147               | 0.75291           | 0.092593        |
| 55  | high_20nA      | gradient_boosted_trees | 8330        | 0.01748                | 1.2463            | 0.096774        |
| 56  | high_20nA      | gradient_boosted_trees | 21645       | 0.018533               | 0.93918           | 0.30743         |
| 57  | high_20nA      | gradient_boosted_trees | 1843        | 0.026928               | 0.84892           | 0.37912         |
| 58  | high_20nA      | gradient_boosted_trees | 1618        | 0.022864               | 0.62611           | 0.17123         |
| 59  | high_20nA      | gradient_boosted_trees | 809         | 0.035709               | 0.73609           | 0.21154         |
| 60  | high_20nA      | gradient_boosted_trees | 382         | 0.033702               | 0.67676           | 0.16667         |
| 61  | high_20nA      | gradient_boosted_trees | 420         | 0.032386               | 0.49137           | 0.26471         |
| 62  | high_20nA      | gradient_boosted_trees | 513         | 0.035869               | 0.65423           | 0.12963         |
| 63  | high_20nA      | gradient_boosted_trees | 1232        | 0.025962               | 0.3736            | 0.14            |
| 65  | high_20nA      | gradient_boosted_trees | 454         | 0.033014               | 0.66732           | 0.14917         |
| 44  | high_20nA      | mlp                    | 334         | 0.057079               | 0.81403           | 0.36702         |
| 45  | high_20nA      | mlp                    | 5472        | 0.044684               | 0.79664           | 0.35257         |
| 46  | low_2nA        | mlp                    | 144         | 0.048274               | 0.70477           | 0.24324         |
| 47  | low_2nA        | mlp                    | 1268        | 0.046401               | 0.68933           | 0.26823         |
| 48  | high_20nA      | mlp                    | 1991        | 0.052898               | 0.80473           | 0.38783         |
| 49  | high_20nA      | mlp                    | 2154        | 0.05175                | 0.82628           | 0.37385         |
| 50  | high_20nA      | mlp                    | 19492       | 0.040296               | 0.958             | 0.27149         |
| 51  | high_20nA      | mlp                    | 7248        | 0.042046               | 0.73475           | 0.11667         |
| 52  | high_20nA      | mlp                    | 3625        | 0.044749               | 0.8209            | 0.3             |
| 53  | high_20nA      | mlp                    | 13961       | 0.050728               | 0.84102           | 0.093023        |
| 54  | high_20nA      | mlp                    | 13282       | 0.049811               | 0.75291           | 0.092593        |
| 55  | high_20nA      | mlp                    | 8330        | 0.04484                | 1.2463            | 0.096774        |
| 56  | high_20nA      | mlp                    | 21645       | 0.042256               | 0.93918           | 0.30743         |
| 57  | high_20nA      | mlp                    | 1843        | 0.053946               | 0.84892           | 0.37912         |
| 58  | high_20nA      | mlp                    | 1618        | 0.051747               | 0.62611           | 0.17123         |
| 59  | high_20nA      | mlp                    | 809         | 0.059107               | 0.73609           | 0.21154         |
| 60  | high_20nA      | mlp                    | 382         | 0.089765               | 0.67676           | 0.16667         |
| 61  | high_20nA      | mlp                    | 420         | 0.074766               | 0.49137           | 0.26471         |
| 62  | high_20nA      | mlp                    | 513         | 0.069057               | 0.65423           | 0.12963         |
| 63  | high_20nA      | mlp                    | 1232        | 0.051014               | 0.3736            | 0.14            |
| 65  | high_20nA      | mlp                    | 454         | 0.059606               | 0.66732           | 0.14917         |
| 44  | high_20nA      | observed_even_charge   | 334         | 0.033083               | 0.81403           | 0.36702         |
| 45  | high_20nA      | observed_even_charge   | 5472        | 0.034247               | 0.79664           | 0.35257         |
| 46  | low_2nA        | observed_even_charge   | 144         | 0.042431               | 0.70477           | 0.24324         |
| 47  | low_2nA        | observed_even_charge   | 1268        | 0.03555                | 0.68933           | 0.26823         |
| 48  | high_20nA      | observed_even_charge   | 1991        | 0.038675               | 0.80473           | 0.38783         |
| 49  | high_20nA      | observed_even_charge   | 2154        | 0.037252               | 0.82628           | 0.37385         |
| 50  | high_20nA      | observed_even_charge   | 19492       | 0.018035               | 0.958             | 0.27149         |
| 51  | high_20nA      | observed_even_charge   | 7248        | 0.019875               | 0.73475           | 0.11667         |
| 52  | high_20nA      | observed_even_charge   | 3625        | 0.019498               | 0.8209            | 0.3             |
| 53  | high_20nA      | observed_even_charge   | 13961       | 0.0173                 | 0.84102           | 0.093023        |
| 54  | high_20nA      | observed_even_charge   | 13282       | 0.016851               | 0.75291           | 0.092593        |
| 55  | high_20nA      | observed_even_charge   | 8330        | 0.019293               | 1.2463            | 0.096774        |
| 56  | high_20nA      | observed_even_charge   | 21645       | 0.020915               | 0.93918           | 0.30743         |
| 57  | high_20nA      | observed_even_charge   | 1843        | 0.037637               | 0.84892           | 0.37912         |
| 58  | high_20nA      | observed_even_charge   | 1618        | 0.02861                | 0.62611           | 0.17123         |
| 59  | high_20nA      | observed_even_charge   | 809         | 0.049206               | 0.73609           | 0.21154         |
| 60  | high_20nA      | observed_even_charge   | 382         | 0.043603               | 0.67676           | 0.16667         |
| 61  | high_20nA      | observed_even_charge   | 420         | 0.042764               | 0.49137           | 0.26471         |
| 62  | high_20nA      | observed_even_charge   | 513         | 0.04494                | 0.65423           | 0.12963         |
| 63  | high_20nA      | observed_even_charge   | 1232        | 0.03414                | 0.3736            | 0.14            |
| 65  | high_20nA      | observed_even_charge   | 454         | 0.040983               | 0.66732           | 0.14917         |
| 44  | high_20nA      | p07_p04_corrected      | 334         | 0.029063               | 0.81403           | 0.36702         |
| 45  | high_20nA      | p07_p04_corrected      | 5472        | 0.027697               | 0.79664           | 0.35257         |
| 46  | low_2nA        | p07_p04_corrected      | 144         | 0.030488               | 0.70477           | 0.24324         |
| 47  | low_2nA        | p07_p04_corrected      | 1268        | 0.026671               | 0.68933           | 0.26823         |
| 48  | high_20nA      | p07_p04_corrected      | 1991        | 0.032321               | 0.80473           | 0.38783         |
| 49  | high_20nA      | p07_p04_corrected      | 2154        | 0.031675               | 0.82628           | 0.37385         |
| 50  | high_20nA      | p07_p04_corrected      | 19492       | 0.025927               | 0.958             | 0.27149         |
| 51  | high_20nA      | p07_p04_corrected      | 7248        | 0.027127               | 0.73475           | 0.11667         |
| 52  | high_20nA      | p07_p04_corrected      | 3625        | 0.026833               | 0.8209            | 0.3             |
| 53  | high_20nA      | p07_p04_corrected      | 13961       | 0.025851               | 0.84102           | 0.093023        |
| 54  | high_20nA      | p07_p04_corrected      | 13282       | 0.025525               | 0.75291           | 0.092593        |
| 55  | high_20nA      | p07_p04_corrected      | 8330        | 0.026728               | 1.2463            | 0.096774        |
| 56  | high_20nA      | p07_p04_corrected      | 21645       | 0.027248               | 0.93918           | 0.30743         |
| 57  | high_20nA      | p07_p04_corrected      | 1843        | 0.033111               | 0.84892           | 0.37912         |
| 58  | high_20nA      | p07_p04_corrected      | 1618        | 0.029469               | 0.62611           | 0.17123         |
| 59  | high_20nA      | p07_p04_corrected      | 809         | 0.041334               | 0.73609           | 0.21154         |
| 60  | high_20nA      | p07_p04_corrected      | 382         | 0.044099               | 0.67676           | 0.16667         |
| 61  | high_20nA      | p07_p04_corrected      | 420         | 0.039836               | 0.49137           | 0.26471         |
| 62  | high_20nA      | p07_p04_corrected      | 513         | 0.04308                | 0.65423           | 0.12963         |
| 63  | high_20nA      | p07_p04_corrected      | 1232        | 0.032765               | 0.3736            | 0.14            |
| 65  | high_20nA      | p07_p04_corrected      | 454         | 0.036815               | 0.66732           | 0.14917         |
| 44  | high_20nA      | ridge                  | 334         | 0.056245               | 0.81403           | 0.36702         |
| 45  | high_20nA      | ridge                  | 5472        | 0.054138               | 0.79664           | 0.35257         |
| 46  | low_2nA        | ridge                  | 144         | 0.050642               | 0.70477           | 0.24324         |
| 47  | low_2nA        | ridge                  | 1268        | 0.049356               | 0.68933           | 0.26823         |
| 48  | high_20nA      | ridge                  | 1991        | 0.060382               | 0.80473           | 0.38783         |
| 49  | high_20nA      | ridge                  | 2154        | 0.060442               | 0.82628           | 0.37385         |
| 50  | high_20nA      | ridge                  | 19492       | 0.050002               | 0.958             | 0.27149         |
| 51  | high_20nA      | ridge                  | 7248        | 0.050906               | 0.73475           | 0.11667         |
| 52  | high_20nA      | ridge                  | 3625        | 0.050173               | 0.8209            | 0.3             |
| 53  | high_20nA      | ridge                  | 13961       | 0.052735               | 0.84102           | 0.093023        |
| 54  | high_20nA      | ridge                  | 13282       | 0.05192                | 0.75291           | 0.092593        |
| 55  | high_20nA      | ridge                  | 8330        | 0.051369               | 1.2463            | 0.096774        |
| 56  | high_20nA      | ridge                  | 21645       | 0.049901               | 0.93918           | 0.30743         |
| 57  | high_20nA      | ridge                  | 1843        | 0.060562               | 0.84892           | 0.37912         |
| 58  | high_20nA      | ridge                  | 1618        | 0.10376                | 0.62611           | 0.17123         |

## 5. Systematics and Caveats

The A-stack handle is external but run-level: it tests whether S14f saturated B-stack performance transfers across independent A-stack charge/topology conditions, not event-by-event calorimetric truth. Matching by run avoids inventing an unverified cross-detector event identity beyond shared run/DAQ context. The S14f target remains duplicate-readout closure mapped to a range-order proxy, so Birks quenching, particle identity, and material survey uncertainties remain outside this validation. The correlation penalty is intentionally conservative: it treats strong dependence on A-stack charge width as a transfer risk even when the B-stack point estimate is good.

## 6. Finding

gradient_boosted_trees has the best external-transfer score (0.028004), combining mean held-out saturated B-stack R68 0.018767 with absolute A-stack instability correlation 0.49219. The result supports S14f transfer only as a run-level external validation; it is not an event-level absolute energy calibration.

## 7. Reproducibility

```bash
/home/billy/anaconda3/bin/python scripts/s14m_1781109219_904_3a4267b9_external_astack_geometry_validation.py --config configs/s14m_1781109219_904_3a4267b9_external_astack_geometry_validation.yaml
```

Artifacts: `result.json`, `REPORT.md`, `reproduction_match_table.csv`, `astack_run_summary.csv`, `method_external_transfer_scores.csv`, `method_run_external_panel.csv`, `input_sha256.csv`, and `manifest.json`.
