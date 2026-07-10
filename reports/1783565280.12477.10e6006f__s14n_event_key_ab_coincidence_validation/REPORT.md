# S14n: event-key A/B coincidence validation for saturation transfer

## Abstract

This study validates whether A-stack and B-stack raw ROOT event counters support event-key coincidence joins for the S14 saturation-transfer stress test. The raw B-stack reproduction gate is rebuilt from `h101/HRDv` and passes at 640,737 selected B2/B4/B6/B8 pulses. Among the candidate counters, `EVENTNO` is accepted as the event join key because it matches 0.97637--1.00000 of selected B events on the held-out runs with no duplicate keys in either stack. `EVT` is rejected because it is not duplicate-free in these files and gives many-to-many joins. Replacing the S14m run-level A-stack handle with event-key matched A-stack charge leaves **gradient_boosted_trees** as the best transfer method, with score 0.021719 and run-bootstrap 95% CI [0.018614016737551854, 0.028678244888524974].

## 1. Raw ROOT Reproduction

For each B-stack raw file `hrdb_run_*.root`, the waveform branch is reshaped as events by eight channels by 18 samples. The baseline is the channel-wise median of samples 0--3. A B pulse is counted when

\[
\max_t \left(x_{i,c,t}-\operatorname{median}(x_{i,c,0:3})\right) > 1000\,\mathrm{ADC},
\]

for one of B2/B4/B6/B8. This exactly reproduces the S14f/S14m ticket number from raw ROOT:

| Quantity | Expected | Reproduced | Delta | Pass |
|---|---:|---:|---:|:---|
| B-stack selected pulses | 640,737 | 640,737 | +0 | true |

Per-run reproduction:

| run | events_total | events_with_selected | selected_pulses |
| --- | --- | --- | --- |
| 31  | 39990        | 27078                | 27871           |
| 32  | 41921        | 27461                | 28240           |
| 33  | 57173        | 47911                | 48737           |
| 34  | 39765        | 33500                | 34118           |
| 35  | 27786        | 11141                | 11667           |
| 36  | 21764        | 9930                 | 10391           |
| 37  | 50513        | 23174                | 24537           |
| 39  | 30321        | 13329                | 14218           |
| 40  | 32613        | 13763                | 14708           |
| 41  | 33997        | 15140                | 16146           |
| 42  | 33972        | 17132                | 18112           |
| 44  | 4294         | 1912                 | 2038            |
| 45  | 48181        | 23013                | 24333           |
| 46  | 1441         | 677                  | 687             |
| 47  | 10970        | 5161                 | 5276            |
| 48  | 31713        | 13185                | 14000           |
| 49  | 32354        | 13937                | 14815           |
| 50  | 44804        | 34257                | 35217           |
| 51  | 20569        | 14295                | 14740           |
| 52  | 10005        | 6933                 | 7152            |
| 53  | 39612        | 31386                | 32200           |
| 54  | 37413        | 29665                | 30440           |
| 55  | 24416        | 16841                | 17387           |
| 56  | 51823        | 38932                | 40148           |
| 57  | 31284        | 12939                | 13833           |
| 58  | 34141        | 15920                | 16781           |
| 59  | 42303        | 13863                | 21377           |
| 60  | 36074        | 10140                | 17029           |
| 61  | 36535        | 11287                | 18965           |
| 62  | 37584        | 11912                | 19089           |
| 63  | 37030        | 14781                | 18817           |
| 64  | 35943        | 12103                | 14630           |
| 65  | 38424        | 11904                | 13038           |

## 2. Event-Key Coincidence Test

The ticket asks whether A-stack and B-stack counters can be joined at event-key level. For each run, A and B event tables were independently rebuilt from their raw ROOT files using the candidate counters `EVT` and `EVENTNO`. The selected-event coincidence fraction is

\[
f_k(r)=N_{AB,\mathrm{sel}}(r,k)/N_{B,\mathrm{sel}}(r),
\]

where membership is evaluated under key \(k\). A key is acceptable only if it has no duplicate keys in either stack and produces stable high selected-B coincidence over the held-out runs.

Held-out `EVENTNO` summary: minimum selected-B match fraction 0.976366, median 0.999161, maximum 1.000000. Held-out `EVT` summary: minimum 0.000000, median 2.201874, maximum 3.162668; its maximum duplicate counts are 35446 in A and 35440 in B, so it is not a valid one-to-one key.

Accepted-key table:

| run | key     | a_events | b_events | selected_b_events | selected_b_matched_events | selected_b_match_fraction | a_duplicate_keys | b_duplicate_keys |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 44  | EVENTNO | 4299     | 4294     | 1912              | 1912                      | 1                         | 0                | 0                |
| 45  | EVENTNO | 48208    | 48181    | 23013             | 23004                     | 0.99961                   | 0                | 0                |
| 46  | EVENTNO | 1444     | 1441     | 677               | 661                       | 0.97637                   | 0                | 0                |
| 47  | EVENTNO | 10982    | 10970    | 5161              | 5141                      | 0.99612                   | 0                | 0                |
| 48  | EVENTNO | 31671    | 31713    | 13185             | 13167                     | 0.99863                   | 0                | 0                |
| 49  | EVENTNO | 32325    | 32354    | 13937             | 13919                     | 0.99871                   | 0                | 0                |
| 50  | EVENTNO | 44824    | 44804    | 34257             | 34251                     | 0.99982                   | 0                | 0                |
| 51  | EVENTNO | 20566    | 20569    | 14295             | 14291                     | 0.99972                   | 0                | 0                |
| 52  | EVENTNO | 10010    | 10005    | 6933              | 6933                      | 1                         | 0                | 0                |
| 53  | EVENTNO | 39621    | 39612    | 31386             | 31385                     | 0.99997                   | 0                | 0                |
| 54  | EVENTNO | 37385    | 37413    | 29665             | 29638                     | 0.99909                   | 0                | 0                |
| 55  | EVENTNO | 24409    | 24416    | 16841             | 16820                     | 0.99875                   | 0                | 0                |
| 56  | EVENTNO | 51829    | 51823    | 38932             | 38913                     | 0.99951                   | 0                | 0                |
| 57  | EVENTNO | 31275    | 31284    | 12939             | 12925                     | 0.99892                   | 0                | 0                |
| 58  | EVENTNO | 34178    | 34141    | 15920             | 15890                     | 0.99812                   | 0                | 0                |
| 59  | EVENTNO | 42314    | 42303    | 13863             | 13863                     | 1                         | 0                | 0                |
| 60  | EVENTNO | 36089    | 36074    | 10140             | 10139                     | 0.9999                    | 0                | 0                |
| 61  | EVENTNO | 36550    | 36535    | 11287             | 11282                     | 0.99956                   | 0                | 0                |
| 62  | EVENTNO | 37589    | 37584    | 11912             | 11902                     | 0.99916                   | 0                | 0                |
| 63  | EVENTNO | 37040    | 37030    | 14781             | 14756                     | 0.99831                   | 0                | 0                |
| 65  | EVENTNO | 38429    | 38424    | 11904             | 11875                     | 0.99756                   | 0                | 0                |

Rejected/diagnostic candidate excerpt:

| run | key | selected_b_events | selected_b_matched_events | selected_b_match_fraction | a_duplicate_keys | b_duplicate_keys |
| --- | --- | --- | --- | --- | --- | --- |
| 44  | EVT | 1912              | 707                       | 0.36977                   | 209              | 328              |
| 45  | EVT | 23013             | 67172                     | 2.9189                    | 31825            | 31798            |
| 46  | EVT | 677               | 0                         | 0                         | 49               | 119              |
| 47  | EVT | 5161              | 3035                      | 0.58806                   | 494              | 783              |
| 48  | EVT | 13185             | 25094                     | 1.9032                    | 15288            | 15361            |
| 49  | EVT | 13937             | 27300                     | 1.9588                    | 15944            | 16033            |
| 50  | EVT | 34257             | 91843                     | 2.681                     | 28441            | 28421            |
| 51  | EVT | 14295             | 17631                     | 1.2334                    | 4232             | 4360             |
| 52  | EVT | 6933              | 2008                      | 0.28963                   | 484              | 721              |
| 53  | EVT | 31386             | 78517                     | 2.5017                    | 23238            | 23228            |
| 54  | EVT | 29665             | 68358                     | 2.3043                    | 21002            | 21029            |
| 55  | EVT | 16841             | 27208                     | 1.6156                    | 8093             | 8081             |
| 56  | EVT | 38932             | 123129                    | 3.1627                    | 35446            | 35440            |
| 57  | EVT | 12939             | 24681                     | 1.9075                    | 14954            | 14932            |
| 58  | EVT | 15920             | 33235                     | 2.0876                    | 17795            | 17759            |
| 59  | EVT | 13863             | 35854                     | 2.5863                    | 25931            | 25919            |
| 60  | EVT | 10140             | 22327                     | 2.2019                    | 19706            | 19691            |
| 61  | EVT | 11287             | 25149                     | 2.2281                    | 20167            | 20152            |
| 62  | EVT | 11912             | 27164                     | 2.2804                    | 21206            | 21200            |
| 63  | EVT | 14781             | 33377                     | 2.2581                    | 20657            | 20649            |
| 65  | EVT | 11904             | 27681                     | 2.3254                    | 22046            | 22043            |

## 3. Event-Level A-Stack Charge Handle

For each selected B event, the matched A event is retrieved by `EVENTNO`. The A-stack event charge is computed from channels A1 and A3 as positive baseline-subtracted waveform area,

\[
Q_A(e)=\sum_{c\in C_A}\sum_t \max\left(x_{e,c,t}-\operatorname{median}(x_{e,c,0:3}),0\right),\quad C_A=(A1,A3).
\]

The event-level transfer nuisance for run \(r\) is the fractional interquartile width of this matched charge distribution,

\[
I_A^\mathrm{evt}(r)=\frac{Q_{75}(Q_A(e)\mid e\in B_r^\mathrm{sel})-Q_{25}(Q_A(e)\mid e\in B_r^\mathrm{sel})}{\operatorname{median}(Q_A(e)\mid e\in B_r^\mathrm{sel})}.
\]

This differs from S14m by conditioning the A charge on the same event keys as selected B activity rather than summarizing all selected A-stack activity at run level.

| run | current_family | b_selected_events | event_matched_a_events | event_matched_fraction | a_charge_median_event_matched | a_charge_iqr_frac_event_matched | a_selected_fraction_event_matched |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 31  | high_20nA      | 27078             | 26332                  | 0.97245                | 282                           | 1.266                           | 0.022672                          |
| 32  | high_20nA      | 27461             | 26662                  | 0.9709                 | 285                           | 1.2667                          | 0.022016                          |
| 33  | high_20nA      | 47911             | 46844                  | 0.97773                | 277.75                        | 1.2295                          | 0.00089659                        |
| 34  | high_20nA      | 33500             | 32409                  | 0.96743                | 276                           | 1.2337                          | 0.0013576                         |
| 35  | high_20nA      | 11141             | 10648                  | 0.95575                | 297.5                         | 1.2403                          | 0.040477                          |
| 36  | high_20nA      | 9930              | 9408                   | 0.94743                | 298.5                         | 1.2764                          | 0.040179                          |
| 37  | high_20nA      | 23174             | 22655                  | 0.9776                 | 294                           | 1.2874                          | 0.036725                          |
| 39  | high_20nA      | 13329             | 12824                  | 0.96211                | 290.5                         | 1.3115                          | 0.041095                          |
| 40  | high_20nA      | 13763             | 13303                  | 0.96658                | 296                           | 1.2796                          | 0.040818                          |
| 41  | high_20nA      | 15140             | 14592                  | 0.9638                 | 303                           | 1.2855                          | 0.039268                          |
| 42  | high_20nA      | 17132             | 16310                  | 0.95202                | 301.5                         | 1.2716                          | 0.0355                            |
| 44  | high_20nA      | 1912              | 1912                   | 1                      | 296                           | 1.2568                          | 0.039226                          |
| 45  | high_20nA      | 23013             | 23004                  | 0.99961                | 306                           | 1.2778                          | 0.039254                          |
| 46  | low_2nA        | 677               | 661                    | 0.97637                | 296                           | 1.2652                          | 0.028744                          |
| 47  | low_2nA        | 5161              | 5141                   | 0.99612                | 295                           | 1.2814                          | 0.035596                          |
| 48  | high_20nA      | 13185             | 13167                  | 0.99863                | 308                           | 1.2906                          | 0.042455                          |
| 49  | high_20nA      | 13937             | 13919                  | 0.99871                | 305                           | 1.2934                          | 0.039514                          |
| 50  | high_20nA      | 34257             | 34251                  | 0.99982                | 292                           | 1.2295                          | 0.0047882                         |
| 51  | high_20nA      | 14295             | 14291                  | 0.99972                | 286                           | 1.2343                          | 0.0029389                         |
| 52  | high_20nA      | 6933              | 6933                   | 1                      | 288                           | 1.2083                          | 0.0014424                         |
| 53  | high_20nA      | 31386             | 31385                  | 0.99997                | 291                           | 1.2457                          | 0.001147                          |
| 54  | high_20nA      | 29665             | 29638                  | 0.99909                | 296.5                         | 1.2327                          | 0.0016195                         |
| 55  | high_20nA      | 16841             | 16820                  | 0.99875                | 299                           | 1.2408                          | 0.0026754                         |
| 56  | high_20nA      | 38932             | 38913                  | 0.99951                | 303                           | 1.231                           | 0.0055765                         |
| 57  | high_20nA      | 12939             | 12925                  | 0.99892                | 327                           | 1.2661                          | 0.041006                          |
| 58  | high_20nA      | 15920             | 15890                  | 0.99812                | 305.5                         | 1.2422                          | 0.0043424                         |
| 59  | high_20nA      | 13863             | 13863                  | 1                      | 305                           | 1.2311                          | 0.0015148                         |
| 60  | high_20nA      | 10140             | 10139                  | 0.9999                 | 310.5                         | 1.2271                          | 0.0019726                         |
| 61  | high_20nA      | 11287             | 11282                  | 0.99956                | 309.75                        | 1.2264                          | 0.0022159                         |
| 62  | high_20nA      | 11912             | 11902                  | 0.99916                | 305                           | 1.2443                          | 0.0015124                         |
| 63  | high_20nA      | 14781             | 14756                  | 0.99831                | 311                           | 1.2428                          | 0.0054215                         |
| 64  | high_20nA      | 12103             | 12071                  | 0.99736                | 303                           | 1.2343                          | 0.0057162                         |
| 65  | high_20nA      | 11904             | 11875                  | 0.99756                | 307                           | 1.2508                          | 0.0050526                         |

## 4. Benchmark and Bootstrap

The fixed S14f method panel is re-scored against the event-matched A-stack handle. The benchmark includes observed even charge, a rising-edge template/range lookup traditional correction, ridge regression, gradient-boosted trees, MLP, 1D-CNN, and the new template-residual MLP architecture. The split unit remains run: training runs are [31, 32, 33, 34, 35, 36, 37, 39, 40, 41, 42, 64] and held-out runs are [44, 45, 46, 47, 48, 49, 50, 51, 52, 53, 54, 55, 56, 57, 58, 59, 60, 61, 62, 63, 65]. No event from a held-out run contributes to model training.

For method \(m\), held-out run \(r\), S14f saturated energy-proxy resolution \(R_m(r)\), and event-matched A-stack nuisance \(I_A^\mathrm{evt}(r)\), the primary score is

\[
S_m^\mathrm{evt}=\bar R_m\left(1+\left|\rho_R(R_m(r),I_A^\mathrm{evt}(r))\right|\right),
\qquad
\bar R_m=\frac{\sum_r n_{m,r}R_m(r)}{\sum_r n_{m,r}} .
\]

The bootstrap resamples held-out runs with replacement and recomputes both the weighted resolution and the A-charge correlation. Lower scores are better.

| method                         | family                           | n_runs | n_saturated | mean_b_saturated_res68 | mean_b_saturated_res68_ci95 | abs_corr_b_res68_vs_event_astack_iqr | abs_corr_b_res68_vs_event_astack_iqr_ci95 | event_astack_transfer_score | event_astack_transfer_score_ci95 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| gradient_boosted_trees         | ml_tree                          | 21     | 106217      | 0.018767               | [0.017464, 0.021362]        | 0.1573                               | [0.011055, 0.53084]                       | 0.021719                    | [0.018614, 0.028678]             |
| observed_even_charge           | traditional_observed             | 21     | 106217      | 0.021896               | [0.019602, 0.026562]        | 0.34437                              | [0.043831, 0.69791]                       | 0.029436                    | [0.022914, 0.038266]             |
| p07_p04_corrected              | ml_p07_p04_duplicate             | 21     | 106217      | 0.027289               | [0.026589, 0.028606]        | 0.11458                              | [0.0044709, 0.47694]                      | 0.030416                    | [0.027246, 0.041729]             |
| template_residual_mlp          | neural_template_residual         | 21     | 106217      | 0.030977               | [0.029231, 0.034575]        | 0.065233                             | [0.0053692, 0.42205]                      | 0.032998                    | [0.030267, 0.047494]             |
| mlp                            | neural_tabular                   | 21     | 106217      | 0.04593                | [0.043382, 0.04984]         | 0.16787                              | [0.012823, 0.5069]                        | 0.05364                     | [0.045186, 0.071861]             |
| ridge                          | ml_linear                        | 21     | 106217      | 0.054535               | [0.052228, 0.060263]        | 0.28109                              | [0.014736, 0.58982]                       | 0.069865                    | [0.054323, 0.09335]              |
| traditional_template_corrected | traditional_rising_edge_template | 21     | 106217      | 0.081877               | [0.079813, 0.084564]        | 0.47556                              | [0.24363, 0.75074]                        | 0.12081                     | [0.10244, 0.14338]               |
| 1d_cnn                         | neural_waveform                  | 21     | 106217      | 0.15232                | [0.14628, 0.16242]          | 0.40453                              | [0.075911, 0.80016]                       | 0.21394                     | [0.16399, 0.27616]               |

## 5. Run-Level Transfer Panel

| run | current_family | method                 | n_saturated | saturated_energy_res68 | a_charge_iqr_frac_event_matched | event_matched_fraction |
| --- | --- | --- | --- | --- | --- | --- |
| 44  | high_20nA      | 1d_cnn                 | 334         | 0.17052                | 1.2568                          | 1                      |
| 45  | high_20nA      | 1d_cnn                 | 5472        | 0.18237                | 1.2778                          | 0.99961                |
| 46  | low_2nA        | 1d_cnn                 | 144         | 0.17528                | 1.2652                          | 0.97637                |
| 47  | low_2nA        | 1d_cnn                 | 1268        | 0.18047                | 1.2814                          | 0.99612                |
| 48  | high_20nA      | 1d_cnn                 | 1991        | 0.18386                | 1.2906                          | 0.99863                |
| 49  | high_20nA      | 1d_cnn                 | 2154        | 0.18939                | 1.2934                          | 0.99871                |
| 50  | high_20nA      | 1d_cnn                 | 19492       | 0.15375                | 1.2295                          | 0.99982                |
| 51  | high_20nA      | 1d_cnn                 | 7248        | 0.1544                 | 1.2343                          | 0.99972                |
| 52  | high_20nA      | 1d_cnn                 | 3625        | 0.15383                | 1.2083                          | 1                      |
| 53  | high_20nA      | 1d_cnn                 | 13961       | 0.1362                 | 1.2457                          | 0.99997                |
| 54  | high_20nA      | 1d_cnn                 | 13282       | 0.13644                | 1.2327                          | 0.99909                |
| 55  | high_20nA      | 1d_cnn                 | 8330        | 0.14481                | 1.2408                          | 0.99875                |
| 56  | high_20nA      | 1d_cnn                 | 21645       | 0.14899                | 1.231                           | 0.99951                |
| 57  | high_20nA      | 1d_cnn                 | 1843        | 0.18358                | 1.2661                          | 0.99892                |
| 58  | high_20nA      | 1d_cnn                 | 1618        | 0.14992                | 1.2422                          | 0.99812                |
| 59  | high_20nA      | 1d_cnn                 | 809         | 0.20897                | 1.2311                          | 1                      |
| 60  | high_20nA      | 1d_cnn                 | 382         | 0.1671                 | 1.2271                          | 0.9999                 |
| 61  | high_20nA      | 1d_cnn                 | 420         | 0.19487                | 1.2264                          | 0.99956                |
| 62  | high_20nA      | 1d_cnn                 | 513         | 0.18428                | 1.2443                          | 0.99916                |
| 63  | high_20nA      | 1d_cnn                 | 1232        | 0.17449                | 1.2428                          | 0.99831                |
| 65  | high_20nA      | 1d_cnn                 | 454         | 0.1592                 | 1.2508                          | 0.99756                |
| 44  | high_20nA      | gradient_boosted_trees | 334         | 0.027419               | 1.2568                          | 1                      |
| 45  | high_20nA      | gradient_boosted_trees | 5472        | 0.023598               | 1.2778                          | 0.99961                |
| 46  | low_2nA        | gradient_boosted_trees | 144         | 0.02473                | 1.2652                          | 0.97637                |
| 47  | low_2nA        | gradient_boosted_trees | 1268        | 0.023598               | 1.2814                          | 0.99612                |
| 48  | high_20nA      | gradient_boosted_trees | 1991        | 0.027108               | 1.2906                          | 0.99863                |
| 49  | high_20nA      | gradient_boosted_trees | 2154        | 0.02795                | 1.2934                          | 0.99871                |
| 50  | high_20nA      | gradient_boosted_trees | 19492       | 0.01748                | 1.2295                          | 0.99982                |
| 51  | high_20nA      | gradient_boosted_trees | 7248        | 0.01805                | 1.2343                          | 0.99972                |
| 52  | high_20nA      | gradient_boosted_trees | 3625        | 0.018549               | 1.2083                          | 1                      |
| 53  | high_20nA      | gradient_boosted_trees | 13961       | 0.015283               | 1.2457                          | 0.99997                |
| 54  | high_20nA      | gradient_boosted_trees | 13282       | 0.015147               | 1.2327                          | 0.99909                |
| 55  | high_20nA      | gradient_boosted_trees | 8330        | 0.01748                | 1.2408                          | 0.99875                |
| 56  | high_20nA      | gradient_boosted_trees | 21645       | 0.018533               | 1.231                           | 0.99951                |
| 57  | high_20nA      | gradient_boosted_trees | 1843        | 0.026928               | 1.2661                          | 0.99892                |
| 58  | high_20nA      | gradient_boosted_trees | 1618        | 0.022864               | 1.2422                          | 0.99812                |
| 59  | high_20nA      | gradient_boosted_trees | 809         | 0.035709               | 1.2311                          | 1                      |
| 60  | high_20nA      | gradient_boosted_trees | 382         | 0.033702               | 1.2271                          | 0.9999                 |
| 61  | high_20nA      | gradient_boosted_trees | 420         | 0.032386               | 1.2264                          | 0.99956                |
| 62  | high_20nA      | gradient_boosted_trees | 513         | 0.035869               | 1.2443                          | 0.99916                |
| 63  | high_20nA      | gradient_boosted_trees | 1232        | 0.025962               | 1.2428                          | 0.99831                |
| 65  | high_20nA      | gradient_boosted_trees | 454         | 0.033014               | 1.2508                          | 0.99756                |
| 44  | high_20nA      | mlp                    | 334         | 0.057079               | 1.2568                          | 1                      |
| 45  | high_20nA      | mlp                    | 5472        | 0.044684               | 1.2778                          | 0.99961                |
| 46  | low_2nA        | mlp                    | 144         | 0.048274               | 1.2652                          | 0.97637                |
| 47  | low_2nA        | mlp                    | 1268        | 0.046401               | 1.2814                          | 0.99612                |
| 48  | high_20nA      | mlp                    | 1991        | 0.052898               | 1.2906                          | 0.99863                |
| 49  | high_20nA      | mlp                    | 2154        | 0.05175                | 1.2934                          | 0.99871                |
| 50  | high_20nA      | mlp                    | 19492       | 0.040296               | 1.2295                          | 0.99982                |
| 51  | high_20nA      | mlp                    | 7248        | 0.042046               | 1.2343                          | 0.99972                |
| 52  | high_20nA      | mlp                    | 3625        | 0.044749               | 1.2083                          | 1                      |
| 53  | high_20nA      | mlp                    | 13961       | 0.050728               | 1.2457                          | 0.99997                |
| 54  | high_20nA      | mlp                    | 13282       | 0.049811               | 1.2327                          | 0.99909                |
| 55  | high_20nA      | mlp                    | 8330        | 0.04484                | 1.2408                          | 0.99875                |
| 56  | high_20nA      | mlp                    | 21645       | 0.042256               | 1.231                           | 0.99951                |
| 57  | high_20nA      | mlp                    | 1843        | 0.053946               | 1.2661                          | 0.99892                |
| 58  | high_20nA      | mlp                    | 1618        | 0.051747               | 1.2422                          | 0.99812                |
| 59  | high_20nA      | mlp                    | 809         | 0.059107               | 1.2311                          | 1                      |
| 60  | high_20nA      | mlp                    | 382         | 0.089765               | 1.2271                          | 0.9999                 |
| 61  | high_20nA      | mlp                    | 420         | 0.074766               | 1.2264                          | 0.99956                |
| 62  | high_20nA      | mlp                    | 513         | 0.069057               | 1.2443                          | 0.99916                |
| 63  | high_20nA      | mlp                    | 1232        | 0.051014               | 1.2428                          | 0.99831                |
| 65  | high_20nA      | mlp                    | 454         | 0.059606               | 1.2508                          | 0.99756                |
| 44  | high_20nA      | observed_even_charge   | 334         | 0.033083               | 1.2568                          | 1                      |
| 45  | high_20nA      | observed_even_charge   | 5472        | 0.034247               | 1.2778                          | 0.99961                |
| 46  | low_2nA        | observed_even_charge   | 144         | 0.042431               | 1.2652                          | 0.97637                |
| 47  | low_2nA        | observed_even_charge   | 1268        | 0.03555                | 1.2814                          | 0.99612                |
| 48  | high_20nA      | observed_even_charge   | 1991        | 0.038675               | 1.2906                          | 0.99863                |
| 49  | high_20nA      | observed_even_charge   | 2154        | 0.037252               | 1.2934                          | 0.99871                |
| 50  | high_20nA      | observed_even_charge   | 19492       | 0.018035               | 1.2295                          | 0.99982                |
| 51  | high_20nA      | observed_even_charge   | 7248        | 0.019875               | 1.2343                          | 0.99972                |
| 52  | high_20nA      | observed_even_charge   | 3625        | 0.019498               | 1.2083                          | 1                      |
| 53  | high_20nA      | observed_even_charge   | 13961       | 0.0173                 | 1.2457                          | 0.99997                |
| 54  | high_20nA      | observed_even_charge   | 13282       | 0.016851               | 1.2327                          | 0.99909                |
| 55  | high_20nA      | observed_even_charge   | 8330        | 0.019293               | 1.2408                          | 0.99875                |
| 56  | high_20nA      | observed_even_charge   | 21645       | 0.020915               | 1.231                           | 0.99951                |
| 57  | high_20nA      | observed_even_charge   | 1843        | 0.037637               | 1.2661                          | 0.99892                |
| 58  | high_20nA      | observed_even_charge   | 1618        | 0.02861                | 1.2422                          | 0.99812                |
| 59  | high_20nA      | observed_even_charge   | 809         | 0.049206               | 1.2311                          | 1                      |
| 60  | high_20nA      | observed_even_charge   | 382         | 0.043603               | 1.2271                          | 0.9999                 |
| 61  | high_20nA      | observed_even_charge   | 420         | 0.042764               | 1.2264                          | 0.99956                |
| 62  | high_20nA      | observed_even_charge   | 513         | 0.04494                | 1.2443                          | 0.99916                |
| 63  | high_20nA      | observed_even_charge   | 1232        | 0.03414                | 1.2428                          | 0.99831                |
| 65  | high_20nA      | observed_even_charge   | 454         | 0.040983               | 1.2508                          | 0.99756                |
| 44  | high_20nA      | p07_p04_corrected      | 334         | 0.029063               | 1.2568                          | 1                      |
| 45  | high_20nA      | p07_p04_corrected      | 5472        | 0.027697               | 1.2778                          | 0.99961                |
| 46  | low_2nA        | p07_p04_corrected      | 144         | 0.030488               | 1.2652                          | 0.97637                |
| 47  | low_2nA        | p07_p04_corrected      | 1268        | 0.026671               | 1.2814                          | 0.99612                |
| 48  | high_20nA      | p07_p04_corrected      | 1991        | 0.032321               | 1.2906                          | 0.99863                |
| 49  | high_20nA      | p07_p04_corrected      | 2154        | 0.031675               | 1.2934                          | 0.99871                |
| 50  | high_20nA      | p07_p04_corrected      | 19492       | 0.025927               | 1.2295                          | 0.99982                |
| 51  | high_20nA      | p07_p04_corrected      | 7248        | 0.027127               | 1.2343                          | 0.99972                |
| 52  | high_20nA      | p07_p04_corrected      | 3625        | 0.026833               | 1.2083                          | 1                      |
| 53  | high_20nA      | p07_p04_corrected      | 13961       | 0.025851               | 1.2457                          | 0.99997                |
| 54  | high_20nA      | p07_p04_corrected      | 13282       | 0.025525               | 1.2327                          | 0.99909                |
| 55  | high_20nA      | p07_p04_corrected      | 8330        | 0.026728               | 1.2408                          | 0.99875                |
| 56  | high_20nA      | p07_p04_corrected      | 21645       | 0.027248               | 1.231                           | 0.99951                |
| 57  | high_20nA      | p07_p04_corrected      | 1843        | 0.033111               | 1.2661                          | 0.99892                |
| 58  | high_20nA      | p07_p04_corrected      | 1618        | 0.029469               | 1.2422                          | 0.99812                |
| 59  | high_20nA      | p07_p04_corrected      | 809         | 0.041334               | 1.2311                          | 1                      |
| 60  | high_20nA      | p07_p04_corrected      | 382         | 0.044099               | 1.2271                          | 0.9999                 |
| 61  | high_20nA      | p07_p04_corrected      | 420         | 0.039836               | 1.2264                          | 0.99956                |
| 62  | high_20nA      | p07_p04_corrected      | 513         | 0.04308                | 1.2443                          | 0.99916                |
| 63  | high_20nA      | p07_p04_corrected      | 1232        | 0.032765               | 1.2428                          | 0.99831                |
| 65  | high_20nA      | p07_p04_corrected      | 454         | 0.036815               | 1.2508                          | 0.99756                |
| 44  | high_20nA      | ridge                  | 334         | 0.056245               | 1.2568                          | 1                      |
| 45  | high_20nA      | ridge                  | 5472        | 0.054138               | 1.2778                          | 0.99961                |
| 46  | low_2nA        | ridge                  | 144         | 0.050642               | 1.2652                          | 0.97637                |
| 47  | low_2nA        | ridge                  | 1268        | 0.049356               | 1.2814                          | 0.99612                |
| 48  | high_20nA      | ridge                  | 1991        | 0.060382               | 1.2906                          | 0.99863                |
| 49  | high_20nA      | ridge                  | 2154        | 0.060442               | 1.2934                          | 0.99871                |
| 50  | high_20nA      | ridge                  | 19492       | 0.050002               | 1.2295                          | 0.99982                |
| 51  | high_20nA      | ridge                  | 7248        | 0.050906               | 1.2343                          | 0.99972                |
| 52  | high_20nA      | ridge                  | 3625        | 0.050173               | 1.2083                          | 1                      |
| 53  | high_20nA      | ridge                  | 13961       | 0.052735               | 1.2457                          | 0.99997                |
| 54  | high_20nA      | ridge                  | 13282       | 0.05192                | 1.2327                          | 0.99909                |
| 55  | high_20nA      | ridge                  | 8330        | 0.051369               | 1.2408                          | 0.99875                |
| 56  | high_20nA      | ridge                  | 21645       | 0.049901               | 1.231                           | 0.99951                |
| 57  | high_20nA      | ridge                  | 1843        | 0.060562               | 1.2661                          | 0.99892                |
| 58  | high_20nA      | ridge                  | 1618        | 0.10376                | 1.2422                          | 0.99812                |
| 59  | high_20nA      | ridge                  | 809         | 0.084359               | 1.2311                          | 1                      |
| 60  | high_20nA      | ridge                  | 382         | 0.15567                | 1.2271                          | 0.9999                 |
| 61  | high_20nA      | ridge                  | 420         | 0.15638                | 1.2264                          | 0.99956                |
| 62  | high_20nA      | ridge                  | 513         | 0.10345                | 1.2443                          | 0.99916                |
| 63  | high_20nA      | ridge                  | 1232        | 0.089368               | 1.2428                          | 0.99831                |
| 65  | high_20nA      | ridge                  | 454         | 0.13624                | 1.2508                          | 0.99756                |
| 44  | high_20nA      | template_residual_mlp  | 334         | 0.037082               | 1.2568                          | 1                      |
| 45  | high_20nA      | template_residual_mlp  | 5472        | 0.033797               | 1.2778                          | 0.99961                |
| 46  | low_2nA        | template_residual_mlp  | 144         | 0.031238               | 1.2652                          | 0.97637                |
| 47  | low_2nA        | template_residual_mlp  | 1268        | 0.032252               | 1.2814                          | 0.99612                |
| 48  | high_20nA      | template_residual_mlp  | 1991        | 0.040912               | 1.2906                          | 0.99863                |
| 49  | high_20nA      | template_residual_mlp  | 2154        | 0.04117                | 1.2934                          | 0.99871                |
| 50  | high_20nA      | template_residual_mlp  | 19492       | 0.027626               | 1.2295                          | 0.99982                |
| 51  | high_20nA      | template_residual_mlp  | 7248        | 0.028674               | 1.2343                          | 0.99972                |
| 52  | high_20nA      | template_residual_mlp  | 3625        | 0.028402               | 1.2083                          | 1                      |
| 53  | high_20nA      | template_residual_mlp  | 13961       | 0.029236               | 1.2457                          | 0.99997                |
| 54  | high_20nA      | template_residual_mlp  | 13282       | 0.029062               | 1.2327                          | 0.99909                |
| 55  | high_20nA      | template_residual_mlp  | 8330        | 0.028628               | 1.2408                          | 0.99875                |
| 56  | high_20nA      | template_residual_mlp  | 21645       | 0.028012               | 1.231                           | 0.99951                |
| 57  | high_20nA      | template_residual_mlp  | 1843        | 0.040363               | 1.2661                          | 0.99892                |

## 6. Systematics and Caveats

The event-key join validates DAQ-level coincidence, not a particle-truth association. A and B entries can differ slightly by run, so the accepted key is judged by selected-B coverage and duplicate-free uniqueness rather than requiring equal tree lengths. The A-stack charge is a nuisance/stress variable; it is not an independent absolute energy label and cannot remove S14f's duplicate-readout closure assumptions. The benchmark predictions themselves are inherited from S14f to isolate the ticket's requested change from run-level A handles to event-matched A charge; retraining every model with A-stack charge as an input would answer a different leakage-prone question. The bootstrap treats runs as exchangeable held-out units, so CIs reflect run-to-run transfer variation, not ROOT waveform calibration uncertainty within a run.

## 7. Finding

`EVENTNO` is the accepted duplicate-free A/B event key for this transfer study: selected-B match fractions over held-out runs span 0.97637 to 1.00000. `EVT` is rejected because it has held-out duplicate counts up to A=35446, B=35440. Replacing S14m's run-level A-stack handle with event-matched A charge keeps gradient_boosted_trees as the best method (score 0.021719, 95% CI [0.018614016737551854, 0.028678244888524974]).

## 8. Reproducibility

```bash
/home/billy/anaconda3/bin/python scripts/s14n_1783565280_12477_10e6006f_event_key_ab_coincidence_validation.py --config configs/s14n_1783565280_12477_10e6006f_event_key_ab_coincidence_validation.yaml
```

Artifacts: `result.json`, `REPORT.md`, `event_key_validation.csv`, `event_matched_astack_run_summary.csv`, `method_event_astack_transfer_scores.csv`, `method_run_event_astack_panel.csv`, `b_reproduction_counts_by_run.csv`, `input_sha256.csv`, and `manifest.json`.
