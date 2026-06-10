# P04g External Charge-Proxy Validation of P04f Anomaly Bias

- **Ticket:** `1781033470.1723.1a366adc`
- **Worker:** `testbeam-laptop-3`
- **Input:** raw HRD ROOT files through the repo `data/root/root` symlink; no Monte Carlo.
- **External targets:** P04b downstream `B4+B6+B8` charge and P04c event-matched selected `A1/A3` charge.
- **Anomaly labels:** frozen P09a/P04f `baseline_excursion` and `novel_early_pretrigger` labels on the source B2 pulse.
- **Split:** leave-one-run-out; every prediction for a run is made by a model fit without that run.

## 1. Raw Reproduction Gates

The shared P04/S00 B-stack gate reproduced `640,737` selected pulses vs expected `640,737` (delta `+0`).
P04b downstream rows reproduced `3,774` vs expected `3,774` (delta `+0`).
P04c A/B rows reproduced `4,055` vs expected `4,055` (delta `+0`), after reproducing the A-stack analysis gates.

## 2. Estimands And Metrics

For target charge $y_i$ and prediction $\hat y_i$, the residual is

$$ r_i = \frac{\hat y_i-y_i}{\max(y_i,1)}. $$

The primary score is $\operatorname{res68}=Q_{0.68}(|r_i|)$, with median bias, RMS, the fraction $|r_i|>0.25$, and within-10/25% rates as diagnostics. Intervals are percentile bootstrap intervals over run blocks. Matched anomaly deltas use

$$ \Delta_m = m(\mathcal A)-m(\mathcal C), $$

where controls $\mathcal C$ are sampled without replacement within the same run, source stave, B2 amplitude bin, and saturation bin.

## 3. Methods

- **traditional_strong:** log-linear hand-engineered charge-transfer model using B2 charge/amplitude terms for P04b and B-stack charge-transfer summaries for P04c.
- **ridge:** standardized Ridge regression on waveform summaries, B2/P04c charge features, P09a continuous anomaly scores, and anomaly flags.
- **gradient_boosted_trees:** histogram gradient-boosted trees on the same engineered feature matrix.
- **mlp:** two-layer standardized MLP on the engineered feature matrix.
- **cnn1d:** compact convolutional network on raw source waveform channels plus engineered metadata.
- **residual_cnn_meta:** new residual architecture that predicts a log-residual correction to the strong traditional model using the same CNN+metadata backbone.
- **shuffled_target_gbt:** leakage sentinel trained on permuted training labels.

All model features exclude target charge columns, A-stack charge columns for P04c, downstream charge columns for P04b, run id, event id, and held-out run rows.

## 4. Run-Held-Out Benchmark

| dataset         | method                 |    n |   bias_median_frac | bias_ci95                                     |   res68_abs_frac | res68_ci95                                 |   high_bias_tail_fraction | high_bias_tail_ci95                        |   within_25pct |
|:----------------|:-----------------------|-----:|-------------------:|:----------------------------------------------|-----------------:|:-------------------------------------------|--------------------------:|:-------------------------------------------|---------------:|
| p04b_downstream | cnn1d                  | 3774 |        -0.0109682  | [-0.04924706018218123, 0.036652198691421424]  |         0.210349 | [0.20134169578326827, 0.22748408767432823] |                  0.231849 | [0.20963794112776193, 0.2654758238373884]  |       0.768151 |
| p04b_downstream | residual_cnn_meta      | 3774 |        -0.00796388 | [-0.04868193982820087, 0.04494989233530227]   |         0.211108 | [0.197342194642834, 0.22872889782566386]   |                  0.233969 | [0.20371767000822674, 0.27797954463210856] |       0.766031 |
| p04b_downstream | ridge                  | 3774 |        -0.0193371  | [-0.058076282764545545, 0.0371450791013085]   |         0.212581 | [0.19998522886854153, 0.22820651203756614] |                  0.246688 | [0.2210968450163646, 0.2826385873306714]   |       0.753312 |
| p04b_downstream | gradient_boosted_trees | 3774 |        -0.015913   | [-0.06082104463862961, 0.03204723334732168]   |         0.214038 | [0.20353999929036265, 0.2281500331666475]  |                  0.233704 | [0.2100951374207188, 0.2699282527944092]   |       0.766296 |
| p04b_downstream | traditional_strong     | 3774 |        -0.0251516  | [-0.08268156368034876, 0.03624820004818334]   |         0.226884 | [0.21549737708049552, 0.24614758667024444] |                  0.268945 | [0.23487906296154745, 0.3117601392011263]  |       0.731055 |
| p04b_downstream | mlp                    | 3774 |        -0.0223702  | [-0.060966438000521386, 0.019945123110475457] |         0.362412 | [0.33668428580279947, 0.39121074010911827] |                  0.481187 | [0.4523563560220191, 0.5253587908857232]   |       0.518813 |
| p04c_ab_charge  | residual_cnn_meta      | 4055 |        -0.0293865  | [-0.04833765167410106, 0.010418391985253116]  |         0.519886 | [0.5092753396248144, 0.5375332080942349]   |                  0.65672  | [0.6364589525986398, 0.6779406440216172]   |       0.34328  |
| p04c_ab_charge  | traditional_strong     | 4055 |        -0.0503827  | [-0.06914079360047849, -0.021971053600521942] |         0.519957 | [0.506358428579855, 0.5376437211658739]    |                  0.65746  | [0.6369469224936015, 0.676299301022314]    |       0.34254  |
| p04c_ab_charge  | cnn1d                  | 4055 |        -0.0227858  | [-0.04506896134084488, 0.005218497883942536]  |         0.520756 | [0.5088950206919604, 0.5388377032852657]   |                  0.654254 | [0.6375856703201079, 0.6710529308941142]   |       0.345746 |
| p04c_ab_charge  | ridge                  | 4055 |        -0.0490899  | [-0.06685451454576777, -0.01724816528702865]  |         0.525019 | [0.5086584696319832, 0.539386742458176]    |                  0.660419 | [0.6423655308363841, 0.678419341242831]    |       0.339581 |
| p04c_ab_charge  | gradient_boosted_trees | 4055 |        -0.0357279  | [-0.06396012345332178, -0.01030588604103068]  |         0.530661 | [0.5167002830639024, 0.5494719733782073]   |                  0.666091 | [0.6477603342686692, 0.6847911650852099]   |       0.333909 |
| p04c_ab_charge  | mlp                    | 4055 |        -0.0292612  | [-0.05386774254712109, 0.009369246129831033]  |         0.629949 | [0.6117997582267115, 0.6450265610851914]   |                  0.72947  | [0.7166342696634758, 0.7434942027398593]   |       0.27053  |

The overall winner by mean rank across the two external targets is `residual_cnn_meta`. Its per-target res68 values are recorded in `result.json`; the single best target-specific result is `p04b_downstream` / `cnn1d` at res68 `0.2103`.

## 5. Matched Anomaly Deltas

Positive deltas mean the anomaly stratum has worse residual behavior than matched normal controls.

| dataset         | anomaly_stratum        | control_stratum                           | method                 |   n_anomaly |   n_control |   delta_bias_median_frac |   delta_res68_abs_frac | delta_res68_ci95                             |   delta_high_bias_tail_fraction | delta_high_bias_tail_ci95                    |
|:----------------|:-----------------------|:------------------------------------------|:-----------------------|------------:|------------:|-------------------------:|-----------------------:|:---------------------------------------------|--------------------------------:|:---------------------------------------------|
| p04b_downstream | baseline_excursion     | matched_normal_for_baseline_excursion     | cnn1d                  |          18 |          18 |              0.0233925   |            -0.0203177  | [-0.07318991206978062, 0.06120406421322677]  |                      -0.0555556 | [-0.19999999999999998, 0.15384615384615385]  |
| p04b_downstream | baseline_excursion     | matched_normal_for_baseline_excursion     | gradient_boosted_trees |          18 |          18 |             -0.00403585  |            -0.0411853  | [-0.12409503890831398, 0.06375833496673386]  |                      -0.111111  | [-0.40909090909090906, 0.4004166666666663]   |
| p04b_downstream | baseline_excursion     | matched_normal_for_baseline_excursion     | mlp                    |          18 |          18 |             -0.25809     |             0.42056    | [0.049112610313772564, 2.8570443411554023]   |                       0         | [-0.20000000000000007, 0.10374668435013244]  |
| p04b_downstream | baseline_excursion     | matched_normal_for_baseline_excursion     | residual_cnn_meta      |          18 |          18 |              0.00661405  |             0.0119193  | [-0.1213015980382432, 0.21095198175857297]   |                       0.0555556 | [-0.30000000000000004, 0.5833333333333334]   |
| p04b_downstream | baseline_excursion     | matched_normal_for_baseline_excursion     | ridge                  |          18 |          18 |             -0.0514917   |             0.104126   | [0.0234951933819737, 0.2018578173670604]     |                       0.222222  | [0.09999999999999998, 0.2692307692307693]    |
| p04b_downstream | baseline_excursion     | matched_normal_for_baseline_excursion     | shuffled_target_gbt    |          18 |          18 |              0.174242    |            -0.0527606  | [-0.07815259018642465, 0.04433172056803336]  |                      -0.111111  | [-0.22222222222222224, 0.0]                  |
| p04b_downstream | baseline_excursion     | matched_normal_for_baseline_excursion     | traditional_strong     |          18 |          18 |             -0.157373    |             0.0302522  | [-0.10386345822757254, 0.28921271105288976]  |                       0         | [-0.5, 0.26086956521739135]                  |
| p04b_downstream | novel_early_pretrigger | matched_normal_for_novel_early_pretrigger | cnn1d                  |          74 |          74 |              0.000329167 |            -0.00137271 | [-0.05717962627365647, 0.07149801790392243]  |                      -0.027027  | [-0.1204918575400503, 0.08893939393939386]   |
| p04b_downstream | novel_early_pretrigger | matched_normal_for_novel_early_pretrigger | gradient_boosted_trees |          74 |          74 |             -0.00252075  |            -0.0238909  | [-0.0601193904394134, 0.04335234555406385]   |                      -0.027027  | [-0.11363636363636367, 0.14609374999999974]  |
| p04b_downstream | novel_early_pretrigger | matched_normal_for_novel_early_pretrigger | mlp                    |          74 |          74 |             -0.0376157   |             0.296582   | [0.10669488768856628, 0.4458483847704035]    |                       0.162162  | [0.02777777777777779, 0.3079545454545452]    |
| p04b_downstream | novel_early_pretrigger | matched_normal_for_novel_early_pretrigger | residual_cnn_meta      |          74 |          74 |             -0.0121963   |            -0.0304784  | [-0.09505297079622085, 0.04095565623360481]  |                      -0.0405405 | [-0.15479910714285713, 0.14893617021276595]  |
| p04b_downstream | novel_early_pretrigger | matched_normal_for_novel_early_pretrigger | ridge                  |          74 |          74 |              0.0504913   |             0.0604246  | [0.012541667479679462, 0.15989932151553418]  |                       0.0405405 | [-0.15294117647058825, 0.21822727272727271]  |
| p04b_downstream | novel_early_pretrigger | matched_normal_for_novel_early_pretrigger | shuffled_target_gbt    |          74 |          74 |              0.59948     |             0.543633   | [0.3540929206656761, 0.9206778073077886]     |                       0.297297  | [0.12495192307692303, 0.458494718309859]     |
| p04b_downstream | novel_early_pretrigger | matched_normal_for_novel_early_pretrigger | traditional_strong     |          74 |          74 |              0.164693    |             0.0820911  | [-0.04922830658895016, 0.3292740518308867]   |                       0.175676  | [-0.06073926073926068, 0.500186567164179]    |
| p04c_ab_charge  | baseline_excursion     | matched_normal_for_baseline_excursion     | cnn1d                  |          54 |          53 |              0.0207485   |             0.154764   | [-0.06941224618384455, 0.393836720182178]    |                       0.080014  | [-0.0700502828409804, 0.18967569786535307]   |
| p04c_ab_charge  | baseline_excursion     | matched_normal_for_baseline_excursion     | gradient_boosted_trees |          54 |          53 |              0.130742    |             0.0906592  | [-0.03521154968301979, 0.43329287101831154]  |                       0.0426275 | [-0.09999999999999998, 0.17555263157894727]  |
| p04c_ab_charge  | baseline_excursion     | matched_normal_for_baseline_excursion     | mlp                    |          54 |          53 |             -0.150387    |             0.307481   | [-0.0514858995373234, 1.7054337260228094]    |                       0.0782669 | [-0.05999999999999994, 0.20314891581632652]  |
| p04c_ab_charge  | baseline_excursion     | matched_normal_for_baseline_excursion     | residual_cnn_meta      |          54 |          53 |              0.0484995   |             0.132602   | [-0.024926121218675996, 0.3965998762496679]  |                       0.0803634 | [-0.07147212543554014, 0.2131790421086467]   |
| p04c_ab_charge  | baseline_excursion     | matched_normal_for_baseline_excursion     | ridge                  |          54 |          53 |              0.0494539   |             0.096965   | [-0.027047551862843505, 0.3792378401339743]  |                       0.0988819 | [-0.08695652173913038, 0.2325581395348837]   |
| p04c_ab_charge  | baseline_excursion     | matched_normal_for_baseline_excursion     | shuffled_target_gbt    |          54 |          53 |              0.0480364   |             0.192696   | [-0.1006608876235448, 0.39119253265409737]   |                       0.136268  | [0.0, 0.29999999999999993]                   |
| p04c_ab_charge  | baseline_excursion     | matched_normal_for_baseline_excursion     | traditional_strong     |          54 |          53 |              0.0650373   |             0.141583   | [-0.04501923075633151, 0.48600546178238263]  |                       0.0611461 | [-0.11649709302325578, 0.21314402810304447]  |
| p04c_ab_charge  | novel_early_pretrigger | matched_normal_for_novel_early_pretrigger | cnn1d                  |         182 |         179 |              0.0556684   |            -0.0380032  | [-0.12147579649189298, 0.016041028651840768] |                      -0.01059   | [-0.09149471006299474, 0.08876776090151886]  |
| p04c_ab_charge  | novel_early_pretrigger | matched_normal_for_novel_early_pretrigger | gradient_boosted_trees |         182 |         179 |             -0.00155817  |            -0.0813585  | [-0.154846106207533, -0.010416978464325856]  |                      -0.0772607 | [-0.16668918918918915, 0.039805551641538595] |
| p04c_ab_charge  | novel_early_pretrigger | matched_normal_for_novel_early_pretrigger | mlp                    |         182 |         179 |              0.217217    |             0.116766   | [0.020513243297147748, 0.2947905146325516]   |                       0.0655964 | [-0.02129716703890916, 0.15351384800642223]  |
| p04c_ab_charge  | novel_early_pretrigger | matched_normal_for_novel_early_pretrigger | residual_cnn_meta      |         182 |         179 |              0.024933    |            -0.0399774  | [-0.12191355367603834, 0.05091319969791546]  |                      -0.0382467 | [-0.12420343137254902, 0.07503472222222225]  |
| p04c_ab_charge  | novel_early_pretrigger | matched_normal_for_novel_early_pretrigger | ridge                  |         182 |         179 |              0.0872089   |            -0.0335615  | [-0.11485623362505212, 0.01051473624060383]  |                      -0.049604  | [-0.1214984844657742, 0.03429620806035336]   |
| p04c_ab_charge  | novel_early_pretrigger | matched_normal_for_novel_early_pretrigger | shuffled_target_gbt    |         182 |         179 |             -0.056909    |            -0.0482505  | [-0.10974460818526427, 0.002193117352545447] |                      -0.0438333 | [-0.12618303277609588, 0.05716056670602115]  |
| p04c_ab_charge  | novel_early_pretrigger | matched_normal_for_novel_early_pretrigger | traditional_strong     |         182 |         179 |             -0.0246308   |            -0.0394314  | [-0.10423750109899042, 0.00985346011378194]  |                      -0.0218552 | [-0.10494126659856996, 0.07488226059654635]  |

## 6. Run-Level Stability

| dataset         |   run | method                 |   n |   bias_median_frac |   res68_abs_frac |   high_bias_tail_fraction |   baseline_excursion_n |   novel_early_pretrigger_n |
|:----------------|------:|:-----------------------|----:|-------------------:|-----------------:|--------------------------:|-----------------------:|---------------------------:|
| p04b_downstream |    58 | traditional_strong     |  72 |         0.0533977  |         0.321119 |                  0.416667 |                      0 |                          2 |
| p04b_downstream |    58 | ridge                  |  72 |        -0.0427426  |         0.227378 |                  0.305556 |                      0 |                          2 |
| p04b_downstream |    58 | gradient_boosted_trees |  72 |        -0.0285476  |         0.265876 |                  0.347222 |                      0 |                          2 |
| p04b_downstream |    58 | mlp                    |  72 |        -0.00900823 |         0.37101  |                  0.486111 |                      0 |                          2 |
| p04b_downstream |    58 | cnn1d                  |  72 |        -0.0132161  |         0.234058 |                  0.236111 |                      0 |                          2 |
| p04b_downstream |    58 | residual_cnn_meta      |  72 |         0.0133214  |         0.237716 |                  0.291667 |                      0 |                          2 |
| p04b_downstream |    59 | traditional_strong     | 749 |         0.0482103  |         0.234639 |                  0.288385 |                      4 |                         14 |
| p04b_downstream |    59 | ridge                  | 749 |         0.0425587  |         0.235712 |                  0.301736 |                      4 |                         14 |
| p04b_downstream |    59 | gradient_boosted_trees | 749 |         0.049352   |         0.225002 |                  0.271028 |                      4 |                         14 |
| p04b_downstream |    59 | mlp                    | 749 |         0.0184454  |         0.38673  |                  0.457944 |                      4 |                         14 |
| p04b_downstream |    59 | cnn1d                  | 749 |         0.0506805  |         0.233348 |                  0.277704 |                      4 |                         14 |
| p04b_downstream |    59 | residual_cnn_meta      | 749 |         0.0571801  |         0.237971 |                  0.29773  |                      4 |                         14 |
| p04b_downstream |    60 | traditional_strong     | 802 |        -0.120921   |         0.245368 |                  0.310474 |                      0 |                         21 |
| p04b_downstream |    60 | ridge                  | 802 |        -0.10079    |         0.220686 |                  0.239401 |                      0 |                         21 |
| p04b_downstream |    60 | gradient_boosted_trees | 802 |        -0.0952943  |         0.219032 |                  0.216958 |                      0 |                         21 |
| p04b_downstream |    60 | mlp                    | 802 |        -0.0848686  |         0.386186 |                  0.546135 |                      0 |                         21 |
| p04b_downstream |    60 | cnn1d                  | 802 |        -0.0968489  |         0.217077 |                  0.220698 |                      0 |                         21 |
| p04b_downstream |    60 | residual_cnn_meta      | 802 |        -0.0902562  |         0.211501 |                  0.216958 |                      0 |                         21 |
| p04b_downstream |    61 | traditional_strong     | 925 |        -0.0624561  |         0.212556 |                  0.232432 |                      1 |                         19 |
| p04b_downstream |    61 | ridge                  | 925 |        -0.0412999  |         0.197501 |                  0.207568 |                      1 |                         19 |
| p04b_downstream |    61 | gradient_boosted_trees | 925 |        -0.0382961  |         0.198721 |                  0.196757 |                      1 |                         19 |
| p04b_downstream |    61 | mlp                    | 925 |        -0.0639034  |         0.323742 |                  0.446486 |                      1 |                         19 |
| p04b_downstream |    61 | cnn1d                  | 925 |        -0.0333295  |         0.200635 |                  0.202162 |                      1 |                         19 |
| p04b_downstream |    61 | residual_cnn_meta      | 925 |        -0.0381953  |         0.193056 |                  0.195676 |                      1 |                         19 |
| p04b_downstream |    62 | traditional_strong     | 798 |        -0.00535587 |         0.210872 |                  0.210526 |                      4 |                         12 |
| p04b_downstream |    62 | ridge                  | 798 |         0.0116479  |         0.194928 |                  0.219298 |                      4 |                         12 |
| p04b_downstream |    62 | gradient_boosted_trees | 798 |         0.00774913 |         0.200986 |                  0.20802  |                      4 |                         12 |
| p04b_downstream |    62 | mlp                    | 798 |         0.0187868  |         0.331632 |                  0.449875 |                      4 |                         12 |
| p04b_downstream |    62 | cnn1d                  | 798 |         0.0205512  |         0.194503 |                  0.199248 |                      4 |                         12 |
| p04b_downstream |    62 | residual_cnn_meta      | 798 |         0.0197607  |         0.197403 |                  0.195489 |                      4 |                         12 |
| p04b_downstream |    63 | traditional_strong     | 365 |         0.0451732  |         0.225109 |                  0.29863  |                      7 |                          6 |
| p04b_downstream |    63 | ridge                  | 365 |         0.0329105  |         0.232085 |                  0.290411 |                      7 |                          6 |
| p04b_downstream |    63 | gradient_boosted_trees | 365 |         0.0179946  |         0.228232 |                  0.293151 |                      7 |                          6 |
| p04b_downstream |    63 | mlp                    | 365 |         0.0261007  |         0.410157 |                  0.531507 |                      7 |                          6 |
| p04b_downstream |    63 | cnn1d                  | 365 |         0.0313083  |         0.227548 |                  0.287671 |                      7 |                          6 |
| p04b_downstream |    63 | residual_cnn_meta      | 365 |         0.0369921  |         0.224743 |                  0.284932 |                      7 |                          6 |
| p04b_downstream |    65 | traditional_strong     |  63 |         0.155393   |         0.316    |                  0.444444 |                      2 |                          0 |
| p04b_downstream |    65 | ridge                  |  63 |         0.096749   |         0.225986 |                  0.285714 |                      2 |                          0 |
| p04b_downstream |    65 | gradient_boosted_trees |  63 |         0.12828    |         0.266174 |                  0.396825 |                      2 |                          0 |
| p04b_downstream |    65 | mlp                    |  63 |         0.0208365  |         0.386747 |                  0.539683 |                      2 |                          0 |
| p04b_downstream |    65 | cnn1d                  |  63 |         0.142745   |         0.257635 |                  0.349206 |                      2 |                          0 |
| p04b_downstream |    65 | residual_cnn_meta      |  63 |         0.119847   |         0.26311  |                  0.380952 |                      2 |                          0 |
| p04c_ab_charge  |    31 | traditional_strong     | 229 |        -0.0479888  |         0.565173 |                  0.694323 |                      4 |                          9 |
| p04c_ab_charge  |    31 | ridge                  | 229 |        -0.054034   |         0.562397 |                  0.672489 |                      4 |                          9 |
| p04c_ab_charge  |    31 | gradient_boosted_trees | 229 |        -0.0443655  |         0.581809 |                  0.694323 |                      4 |                          9 |
| p04c_ab_charge  |    31 | mlp                    | 229 |        -0.0427846  |         0.615715 |                  0.724891 |                      4 |                          9 |
| p04c_ab_charge  |    31 | cnn1d                  | 229 |        -0.0336272  |         0.55996  |                  0.681223 |                      4 |                          9 |
| p04c_ab_charge  |    31 | residual_cnn_meta      | 229 |        -0.0329564  |         0.571411 |                  0.689956 |                      4 |                          9 |
| p04c_ab_charge  |    32 | traditional_strong     | 207 |         0.010101   |         0.574806 |                  0.681159 |                      1 |                          4 |
| p04c_ab_charge  |    32 | ridge                  | 207 |         0.0496274  |         0.549587 |                  0.661836 |                      1 |                          4 |
| p04c_ab_charge  |    32 | gradient_boosted_trees | 207 |         0.0420982  |         0.564183 |                  0.68599  |                      1 |                          4 |
| p04c_ab_charge  |    32 | mlp                    | 207 |         0.0421469  |         0.669485 |                  0.768116 |                      1 |                          4 |
| p04c_ab_charge  |    32 | cnn1d                  | 207 |         0.0691083  |         0.572723 |                  0.661836 |                      1 |                          4 |
| p04c_ab_charge  |    32 | residual_cnn_meta      | 207 |         0.0511108  |         0.571812 |                  0.695652 |                      1 |                          4 |
| p04c_ab_charge  |    33 | traditional_strong     |   8 |         0.225773   |         0.44218  |                  0.75     |                      0 |                          0 |
| p04c_ab_charge  |    33 | ridge                  |   8 |         0.195441   |         0.357781 |                  0.625    |                      0 |                          0 |
| p04c_ab_charge  |    33 | gradient_boosted_trees |   8 |         0.188576   |         0.302181 |                  0.625    |                      0 |                          0 |
| p04c_ab_charge  |    33 | mlp                    |   8 |         0.099525   |         0.64952  |                  0.625    |                      0 |                          0 |
| p04c_ab_charge  |    33 | cnn1d                  |   8 |         0.24588    |         0.458382 |                  0.625    |                      0 |                          0 |
| p04c_ab_charge  |    33 | residual_cnn_meta      |   8 |         0.217724   |         0.468899 |                  0.625    |                      0 |                          0 |
| p04c_ab_charge  |    34 | traditional_strong     |  16 |         0.0552262  |         0.527202 |                  0.75     |                      0 |                          0 |
| p04c_ab_charge  |    34 | ridge                  |  16 |         0.0205884  |         0.541533 |                  0.6875   |                      0 |                          0 |
| p04c_ab_charge  |    34 | gradient_boosted_trees |  16 |        -0.00958498 |         0.578427 |                  0.6875   |                      0 |                          0 |
| p04c_ab_charge  |    34 | mlp                    |  16 |         0.177278   |         0.675426 |                  0.875    |                      0 |                          0 |
| p04c_ab_charge  |    34 | cnn1d                  |  16 |         0.0952705  |         0.524879 |                  0.625    |                      0 |                          0 |
| p04c_ab_charge  |    34 | residual_cnn_meta      |  16 |         0.0888939  |         0.553179 |                  0.6875   |                      0 |                          0 |
| p04c_ab_charge  |    35 | traditional_strong     | 221 |         0.0310727  |         0.521107 |                  0.669683 |                      4 |                         10 |
| p04c_ab_charge  |    35 | ridge                  | 221 |         0.036815   |         0.522538 |                  0.665158 |                      4 |                         10 |
| p04c_ab_charge  |    35 | gradient_boosted_trees | 221 |         0.0325796  |         0.531133 |                  0.674208 |                      4 |                         10 |
| p04c_ab_charge  |    35 | mlp                    | 221 |        -0.00501183 |         0.635788 |                  0.696833 |                      4 |                         10 |
| p04c_ab_charge  |    35 | cnn1d                  | 221 |         0.0575461  |         0.5144   |                  0.692308 |                      4 |                         10 |
| p04c_ab_charge  |    35 | residual_cnn_meta      | 221 |         0.0648077  |         0.519422 |                  0.665158 |                      4 |                         10 |
| p04c_ab_charge  |    36 | traditional_strong     | 295 |        -0.0231662  |         0.488188 |                  0.613559 |                      5 |                         13 |
| p04c_ab_charge  |    36 | ridge                  | 295 |        -0.0178767  |         0.50406  |                  0.637288 |                      5 |                         13 |
| p04c_ab_charge  |    36 | gradient_boosted_trees | 295 |        -0.0148089  |         0.510345 |                  0.613559 |                      5 |                         13 |
| p04c_ab_charge  |    36 | mlp                    | 295 |        -0.0774953  |         0.611439 |                  0.698305 |                      5 |                         13 |
| p04c_ab_charge  |    36 | cnn1d                  | 295 |         0.00461691 |         0.482383 |                  0.6      |                      5 |                         13 |
| p04c_ab_charge  |    36 | residual_cnn_meta      | 295 |        -0.0392856  |         0.498014 |                  0.610169 |                      5 |                         13 |
| p04c_ab_charge  |    37 | traditional_strong     | 292 |        -0.0710267  |         0.490427 |                  0.60274  |                      3 |                         17 |
| p04c_ab_charge  |    37 | ridge                  | 292 |        -0.0824699  |         0.47725  |                  0.626712 |                      3 |                         17 |
| p04c_ab_charge  |    37 | gradient_boosted_trees | 292 |        -0.103184   |         0.49918  |                  0.626712 |                      3 |                         17 |
| p04c_ab_charge  |    37 | mlp                    | 292 |        -0.0296068  |         0.601312 |                  0.674658 |                      3 |                         17 |
| p04c_ab_charge  |    37 | cnn1d                  | 292 |        -0.0782484  |         0.484883 |                  0.613014 |                      3 |                         17 |
| p04c_ab_charge  |    37 | residual_cnn_meta      | 292 |        -0.0791557  |         0.483032 |                  0.616438 |                      3 |                         17 |
| p04c_ab_charge  |    39 | traditional_strong     | 324 |        -0.0910064  |         0.475078 |                  0.660494 |                      5 |                         20 |
| p04c_ab_charge  |    39 | ridge                  | 324 |        -0.0911302  |         0.474085 |                  0.638889 |                      5 |                         20 |
| p04c_ab_charge  |    39 | gradient_boosted_trees | 324 |        -0.0965638  |         0.486064 |                  0.645062 |                      5 |                         20 |
| p04c_ab_charge  |    39 | mlp                    | 324 |        -0.00432923 |         0.603565 |                  0.719136 |                      5 |                         20 |
| p04c_ab_charge  |    39 | cnn1d                  | 324 |        -0.0891875  |         0.47194  |                  0.651235 |                      5 |                         20 |
| p04c_ab_charge  |    39 | residual_cnn_meta      | 324 |        -0.0803371  |         0.478927 |                  0.641975 |                      5 |                         20 |
| p04c_ab_charge  |    40 | traditional_strong     | 265 |        -0.0586491  |         0.487576 |                  0.611321 |                      6 |                         18 |
| p04c_ab_charge  |    40 | ridge                  | 265 |        -0.0667891  |         0.490078 |                  0.622642 |                      6 |                         18 |
| p04c_ab_charge  |    40 | gradient_boosted_trees | 265 |        -0.0449943  |         0.509635 |                  0.630189 |                      6 |                         18 |
| p04c_ab_charge  |    40 | mlp                    | 265 |         0.0601438  |         0.601826 |                  0.713208 |                      6 |                         18 |
| p04c_ab_charge  |    40 | cnn1d                  | 265 |        -0.0185338  |         0.509532 |                  0.615094 |                      6 |                         18 |
| p04c_ab_charge  |    40 | residual_cnn_meta      | 265 |        -0.0263862  |         0.490675 |                  0.607547 |                      6 |                         18 |
| p04c_ab_charge  |    41 | traditional_strong     | 295 |        -0.116571   |         0.532217 |                  0.698305 |                      8 |                         15 |
| p04c_ab_charge  |    41 | ridge                  | 295 |        -0.110574   |         0.525496 |                  0.722034 |                      8 |                         15 |
| p04c_ab_charge  |    41 | gradient_boosted_trees | 295 |        -0.0904022  |         0.523729 |                  0.715254 |                      8 |                         15 |
| p04c_ab_charge  |    41 | mlp                    | 295 |        -0.0616853  |         0.659582 |                  0.728814 |                      8 |                         15 |
| p04c_ab_charge  |    41 | cnn1d                  | 295 |        -0.0952678  |         0.532502 |                  0.701695 |                      8 |                         15 |
| p04c_ab_charge  |    41 | residual_cnn_meta      | 295 |        -0.0903261  |         0.531878 |                  0.691525 |                      8 |                         15 |
| p04c_ab_charge  |    42 | traditional_strong     | 279 |        -0.0513541  |         0.509521 |                  0.641577 |                      1 |                         11 |
| p04c_ab_charge  |    42 | ridge                  | 279 |        -0.0483227  |         0.521909 |                  0.645161 |                      1 |                         11 |
| p04c_ab_charge  |    42 | gradient_boosted_trees | 279 |        -0.0495631  |         0.508887 |                  0.663082 |                      1 |                         11 |
| p04c_ab_charge  |    42 | mlp                    | 279 |        -0.0247509  |         0.612694 |                  0.734767 |                      1 |                         11 |
| p04c_ab_charge  |    42 | cnn1d                  | 279 |        -0.0056642  |         0.506036 |                  0.630824 |                      1 |                         11 |
| p04c_ab_charge  |    42 | residual_cnn_meta      | 279 |        -0.0111352  |         0.511016 |                  0.637993 |                      1 |                         11 |
| p04c_ab_charge  |    44 | traditional_strong     |  30 |        -0.154071   |         0.474463 |                  0.7      |                      0 |                          3 |
| p04c_ab_charge  |    44 | ridge                  |  30 |        -0.105266   |         0.474208 |                  0.733333 |                      0 |                          3 |
| p04c_ab_charge  |    44 | gradient_boosted_trees |  30 |        -0.106361   |         0.50338  |                  0.766667 |                      0 |                          3 |
| p04c_ab_charge  |    44 | mlp                    |  30 |        -0.197075   |         0.547472 |                  0.833333 |                      0 |                          3 |
| p04c_ab_charge  |    44 | cnn1d                  |  30 |        -0.0892509  |         0.516298 |                  0.7      |                      0 |                          3 |
| p04c_ab_charge  |    44 | residual_cnn_meta      |  30 |        -0.104743   |         0.511495 |                  0.733333 |                      0 |                          3 |
| p04c_ab_charge  |    45 | traditional_strong     | 302 |         0.00794836 |         0.518141 |                  0.692053 |                      4 |                         12 |
| p04c_ab_charge  |    45 | ridge                  | 302 |         0.00509987 |         0.538507 |                  0.68543  |                      4 |                         12 |
| p04c_ab_charge  |    45 | gradient_boosted_trees | 302 |         0.016892   |         0.539338 |                  0.662252 |                      4 |                         12 |
| p04c_ab_charge  |    45 | mlp                    | 302 |         0.0373613  |         0.637644 |                  0.754967 |                      4 |                         12 |
| p04c_ab_charge  |    45 | cnn1d                  | 302 |         0.0181921  |         0.525052 |                  0.682119 |                      4 |                         12 |
| p04c_ab_charge  |    45 | residual_cnn_meta      | 302 |         0.0144887  |         0.520106 |                  0.708609 |                      4 |                         12 |
| p04c_ab_charge  |    47 | traditional_strong     |  92 |        -0.0178565  |         0.497456 |                  0.663043 |                      0 |                          4 |
| p04c_ab_charge  |    47 | ridge                  |  92 |         0.00147175 |         0.513741 |                  0.630435 |                      0 |                          4 |
| p04c_ab_charge  |    47 | gradient_boosted_trees |  92 |         0.00190228 |         0.502764 |                  0.619565 |                      0 |                          4 |
| p04c_ab_charge  |    47 | mlp                    |  92 |        -0.142933   |         0.522439 |                  0.73913  |                      0 |                          4 |
| p04c_ab_charge  |    47 | cnn1d                  |  92 |         0.0101097  |         0.487714 |                  0.673913 |                      0 |                          4 |
| p04c_ab_charge  |    47 | residual_cnn_meta      |  92 |         0.0295217  |         0.506784 |                  0.663043 |                      0 |                          4 |
| p04c_ab_charge  |    48 | traditional_strong     | 260 |        -0.101639   |         0.477157 |                  0.626923 |                      5 |                         14 |
| p04c_ab_charge  |    48 | ridge                  | 260 |        -0.119955   |         0.483903 |                  0.630769 |                      5 |                         14 |
| p04c_ab_charge  |    48 | gradient_boosted_trees | 260 |        -0.119447   |         0.478106 |                  0.657692 |                      5 |                         14 |
| p04c_ab_charge  |    48 | mlp                    | 260 |        -0.0622222  |         0.621133 |                  0.742308 |                      5 |                         14 |
| p04c_ab_charge  |    48 | cnn1d                  | 260 |        -0.095586   |         0.472078 |                  0.638462 |                      5 |                         14 |
| p04c_ab_charge  |    48 | residual_cnn_meta      | 260 |        -0.100663   |         0.480027 |                  0.611538 |                      5 |                         14 |
| p04c_ab_charge  |    49 | traditional_strong     | 288 |        -0.095307   |         0.538044 |                  0.694444 |                      3 |                          7 |
| p04c_ab_charge  |    49 | ridge                  | 288 |        -0.103186   |         0.53643  |                  0.711806 |                      3 |                          7 |
| p04c_ab_charge  |    49 | gradient_boosted_trees | 288 |        -0.104933   |         0.565595 |                  0.722222 |                      3 |                          7 |
| p04c_ab_charge  |    49 | mlp                    | 288 |        -0.032641   |         0.662818 |                  0.746528 |                      3 |                          7 |
| p04c_ab_charge  |    49 | cnn1d                  | 288 |        -0.0531404  |         0.533533 |                  0.684028 |                      3 |                          7 |
| p04c_ab_charge  |    49 | residual_cnn_meta      | 288 |        -0.0776611  |         0.536438 |                  0.701389 |                      3 |                          7 |
| p04c_ab_charge  |    50 | traditional_strong     |  61 |         0.0801952  |         0.591995 |                  0.672131 |                      0 |                          2 |
| p04c_ab_charge  |    50 | ridge                  |  61 |         0.0489992  |         0.603929 |                  0.672131 |                      0 |                          2 |
| p04c_ab_charge  |    50 | gradient_boosted_trees |  61 |         0.098161   |         0.636141 |                  0.655738 |                      0 |                          2 |
| p04c_ab_charge  |    50 | mlp                    |  61 |         0.161295   |         0.919536 |                  0.754098 |                      0 |                          2 |
| p04c_ab_charge  |    50 | cnn1d                  |  61 |         0.0601596  |         0.629347 |                  0.672131 |                      0 |                          2 |
| p04c_ab_charge  |    50 | residual_cnn_meta      |  61 |         0.105157   |         0.624099 |                  0.672131 |                      0 |                          2 |
| p04c_ab_charge  |    51 | traditional_strong     |  25 |        -0.0298263  |         0.6815   |                  0.72     |                      0 |                          1 |
| p04c_ab_charge  |    51 | ridge                  |  25 |        -0.0369061  |         0.72152  |                  0.8      |                      0 |                          1 |
| p04c_ab_charge  |    51 | gradient_boosted_trees |  25 |         0.0472187  |         0.667311 |                  0.68     |                      0 |                          1 |
| p04c_ab_charge  |    51 | mlp                    |  25 |         0.0571936  |         0.742985 |                  0.76     |                      0 |                          1 |
| p04c_ab_charge  |    51 | cnn1d                  |  25 |         0.0282864  |         0.686927 |                  0.72     |                      0 |                          1 |
| p04c_ab_charge  |    51 | residual_cnn_meta      |  25 |        -0.0262916  |         0.67123  |                  0.72     |                      0 |                          1 |
| p04c_ab_charge  |    52 | traditional_strong     |   6 |        -0.227168   |         0.362723 |                  0.666667 |                      0 |                          0 |
| p04c_ab_charge  |    52 | ridge                  |   6 |        -0.220444   |         0.368556 |                  0.5      |                      0 |                          0 |
| p04c_ab_charge  |    52 | gradient_boosted_trees |   6 |        -0.273497   |         0.422904 |                  0.833333 |                      0 |                          0 |
| p04c_ab_charge  |    52 | mlp                    |   6 |         0.034579   |         0.357861 |                  0.5      |                      0 |                          0 |
| p04c_ab_charge  |    52 | cnn1d                  |   6 |        -0.192844   |         0.348812 |                  0.5      |                      0 |                          0 |
| p04c_ab_charge  |    52 | residual_cnn_meta      |   6 |        -0.20657    |         0.354843 |                  0.5      |                      0 |                          0 |
| p04c_ab_charge  |    53 | traditional_strong     |  17 |         0.43117    |         1.04931  |                  0.764706 |                      0 |                          0 |
| p04c_ab_charge  |    53 | ridge                  |  17 |         0.445518   |         1.2458   |                  0.823529 |                      0 |                          0 |
| p04c_ab_charge  |    53 | gradient_boosted_trees |  17 |         0.625811   |         0.902658 |                  0.823529 |                      0 |                          0 |
| p04c_ab_charge  |    53 | mlp                    |  17 |         0.586592   |         1.41352  |                  0.823529 |                      0 |                          0 |
| p04c_ab_charge  |    53 | cnn1d                  |  17 |         0.540208   |         1.03705  |                  0.823529 |                      0 |                          0 |
| p04c_ab_charge  |    53 | residual_cnn_meta      |  17 |         0.432987   |         1.15797  |                  0.764706 |                      0 |                          0 |
| p04c_ab_charge  |    54 | traditional_strong     |  18 |         0.406206   |         0.652067 |                  0.777778 |                      0 |                          0 |
| p04c_ab_charge  |    54 | ridge                  |  18 |         0.385174   |         0.615944 |                  0.777778 |                      0 |                          0 |
| p04c_ab_charge  |    54 | gradient_boosted_trees |  18 |         0.505431   |         0.630307 |                  0.722222 |                      0 |                          0 |
| p04c_ab_charge  |    54 | mlp                    |  18 |         0.684001   |         0.954802 |                  0.777778 |                      0 |                          0 |
| p04c_ab_charge  |    54 | cnn1d                  |  18 |         0.428153   |         0.782943 |                  0.833333 |                      0 |                          0 |
| p04c_ab_charge  |    54 | residual_cnn_meta      |  18 |         0.450485   |         0.717541 |                  0.777778 |                      0 |                          0 |
| p04c_ab_charge  |    55 | traditional_strong     |  27 |        -0.115898   |         0.472104 |                  0.703704 |                      0 |                          1 |
| p04c_ab_charge  |    55 | ridge                  |  27 |        -0.0813558  |         0.580825 |                  0.740741 |                      0 |                          1 |
| p04c_ab_charge  |    55 | gradient_boosted_trees |  27 |        -0.122757   |         0.565712 |                  0.814815 |                      0 |                          1 |
| p04c_ab_charge  |    55 | mlp                    |  27 |        -0.122068   |         0.690243 |                  0.777778 |                      0 |                          1 |
| p04c_ab_charge  |    55 | cnn1d                  |  27 |        -0.10495    |         0.505094 |                  0.740741 |                      0 |                          1 |
| p04c_ab_charge  |    55 | residual_cnn_meta      |  27 |        -0.11492    |         0.54542  |                  0.666667 |                      0 |                          1 |
| p04c_ab_charge  |    56 | traditional_strong     |  68 |         0.0682087  |         0.646608 |                  0.720588 |                      0 |                          0 |
| p04c_ab_charge  |    56 | ridge                  |  68 |         0.0636433  |         0.666947 |                  0.676471 |                      0 |                          0 |
| p04c_ab_charge  |    56 | gradient_boosted_trees |  68 |         0.129169   |         0.708523 |                  0.705882 |                      0 |                          0 |
| p04c_ab_charge  |    56 | mlp                    |  68 |         0.0366375  |         0.603188 |                  0.705882 |                      0 |                          0 |
| p04c_ab_charge  |    56 | cnn1d                  |  68 |         0.0740361  |         0.636681 |                  0.720588 |                      0 |                          0 |
| p04c_ab_charge  |    56 | residual_cnn_meta      |  68 |         0.0647454  |         0.647285 |                  0.720588 |                      0 |                          0 |
| p04c_ab_charge  |    57 | traditional_strong     | 276 |        -0.134414   |         0.540519 |                  0.699275 |                      2 |                         18 |
| p04c_ab_charge  |    57 | ridge                  | 276 |        -0.102762   |         0.541108 |                  0.692029 |                      2 |                         18 |
| p04c_ab_charge  |    57 | gradient_boosted_trees | 276 |        -0.0692644  |         0.537397 |                  0.706522 |                      2 |                         18 |
| p04c_ab_charge  |    57 | mlp                    | 276 |        -0.135861   |         0.639162 |                  0.742754 |                      2 |                         18 |
| p04c_ab_charge  |    57 | cnn1d                  | 276 |        -0.105661   |         0.510408 |                  0.695652 |                      2 |                         18 |
| p04c_ab_charge  |    57 | residual_cnn_meta      | 276 |        -0.0897678  |         0.513435 |                  0.699275 |                      2 |                         18 |
| p04c_ab_charge  |    58 | traditional_strong     |  34 |         0.00191955 |         0.505011 |                  0.647059 |                      0 |                          0 |
| p04c_ab_charge  |    58 | ridge                  |  34 |         0.0214929  |         0.560568 |                  0.647059 |                      0 |                          0 |
| p04c_ab_charge  |    58 | gradient_boosted_trees |  34 |         0.0944312  |         0.580384 |                  0.676471 |                      0 |                          0 |
| p04c_ab_charge  |    58 | mlp                    |  34 |        -0.0724584  |         0.397577 |                  0.676471 |                      0 |                          0 |
| p04c_ab_charge  |    58 | cnn1d                  |  34 |         0.0482421  |         0.511603 |                  0.588235 |                      0 |                          0 |
| p04c_ab_charge  |    58 | residual_cnn_meta      |  34 |         0.0342687  |         0.571639 |                  0.647059 |                      0 |                          0 |
| p04c_ab_charge  |    59 | traditional_strong     |   9 |        -0.113883   |         0.312046 |                  0.444444 |                      0 |                          0 |
| p04c_ab_charge  |    59 | ridge                  |   9 |        -0.101717   |         0.246014 |                  0.333333 |                      0 |                          0 |
| p04c_ab_charge  |    59 | gradient_boosted_trees |   9 |        -0.0997859  |         0.272067 |                  0.333333 |                      0 |                          0 |
| p04c_ab_charge  |    59 | mlp                    |   9 |        -0.188967   |         0.528779 |                  0.666667 |                      0 |                          0 |
| p04c_ab_charge  |    59 | cnn1d                  |   9 |         0.040225   |         0.25778  |                  0.333333 |                      0 |                          0 |
| p04c_ab_charge  |    59 | residual_cnn_meta      |   9 |        -0.0937549  |         0.350413 |                  0.555556 |                      0 |                          0 |
| p04c_ab_charge  |    60 | traditional_strong     |  10 |         1.45644    |         1.91759  |                  0.9      |                      0 |                          0 |
| p04c_ab_charge  |    60 | ridge                  |  10 |         1.36785    |         1.92324  |                  0.9      |                      0 |                          0 |
| p04c_ab_charge  |    60 | gradient_boosted_trees |  10 |         1.18548    |         1.5586   |                  0.9      |                      0 |                          0 |
| p04c_ab_charge  |    60 | mlp                    |  10 |         1.09656    |         1.86792  |                  0.7      |                      0 |                          0 |
| p04c_ab_charge  |    60 | cnn1d                  |  10 |         1.68505    |         2.18852  |                  0.9      |                      0 |                          0 |
| p04c_ab_charge  |    60 | residual_cnn_meta      |  10 |         1.2407     |         2.09921  |                  0.9      |                      0 |                          0 |
| p04c_ab_charge  |    61 | traditional_strong     |   6 |        -0.064633   |         0.535324 |                  0.333333 |                      0 |                          1 |
| p04c_ab_charge  |    61 | ridge                  |   6 |        -0.17682    |         0.331338 |                  0.666667 |                      0 |                          1 |
| p04c_ab_charge  |    61 | gradient_boosted_trees |   6 |         0.0510907  |         0.457042 |                  0.5      |                      0 |                          1 |
| p04c_ab_charge  |    61 | mlp                    |   6 |         0.118994   |         1.30733  |                  0.666667 |                      0 |                          1 |
| p04c_ab_charge  |    61 | cnn1d                  |   6 |         0.0792356  |         0.866986 |                  0.333333 |                      0 |                          1 |
| p04c_ab_charge  |    61 | residual_cnn_meta      |   6 |        -0.0388304  |         0.691405 |                  0.5      |                      0 |                          1 |
| p04c_ab_charge  |    62 | traditional_strong     |   8 |         0.192227   |         0.441917 |                  0.5      |                      1 |                          0 |
| p04c_ab_charge  |    62 | ridge                  |   8 |         0.208574   |         0.689911 |                  0.625    |                      1 |                          0 |
| p04c_ab_charge  |    62 | gradient_boosted_trees |   8 |         0.495765   |         0.691923 |                  0.875    |                      1 |                          0 |
| p04c_ab_charge  |    62 | mlp                    |   8 |        -0.211882   |         1.06476  |                  0.875    |                      1 |                          0 |
| p04c_ab_charge  |    62 | cnn1d                  |   8 |         0.236542   |         0.528077 |                  0.625    |                      1 |                          0 |
| p04c_ab_charge  |    62 | residual_cnn_meta      |   8 |         0.208824   |         0.50733  |                  0.625    |                      1 |                          0 |
| p04c_ab_charge  |    63 | traditional_strong     |  39 |        -0.0714605  |         0.243628 |                  0.307692 |                      1 |                          2 |
| p04c_ab_charge  |    63 | ridge                  |  39 |        -0.0699128  |         0.291945 |                  0.358974 |                      1 |                          2 |
| p04c_ab_charge  |    63 | gradient_boosted_trees |  39 |         0.0136681  |         0.291021 |                  0.410256 |                      1 |                          2 |
| p04c_ab_charge  |    63 | mlp                    |  39 |        -0.253368   |         0.650518 |                  0.846154 |                      1 |                          2 |
| p04c_ab_charge  |    63 | cnn1d                  |  39 |        -0.0449498  |         0.232242 |                  0.307692 |                      1 |                          2 |
| p04c_ab_charge  |    63 | residual_cnn_meta      |  39 |        -0.059744   |         0.238817 |                  0.307692 |                      1 |                          2 |
| p04c_ab_charge  |    64 | traditional_strong     |  35 |         0.105521   |         0.749615 |                  0.514286 |                      1 |                          0 |
| p04c_ab_charge  |    64 | ridge                  |  35 |         0.075629   |         0.65781  |                  0.571429 |                      1 |                          0 |
| p04c_ab_charge  |    64 | gradient_boosted_trees |  35 |         0.192647   |         0.617949 |                  0.571429 |                      1 |                          0 |
| p04c_ab_charge  |    64 | mlp                    |  35 |         0.252717   |         0.534301 |                  0.714286 |                      1 |                          0 |
| p04c_ab_charge  |    64 | cnn1d                  |  35 |         0.143128   |         0.63656  |                  0.514286 |                      1 |                          0 |
| p04c_ab_charge  |    64 | residual_cnn_meta      |  35 |         0.109578   |         0.750609 |                  0.514286 |                      1 |                          0 |
| p04c_ab_charge  |    65 | traditional_strong     |  13 |         0.0528137  |         0.510149 |                  0.461538 |                      0 |                          0 |
| p04c_ab_charge  |    65 | ridge                  |  13 |         0.0597202  |         0.500015 |                  0.461538 |                      0 |                          0 |
| p04c_ab_charge  |    65 | gradient_boosted_trees |  13 |         0.15378    |         0.503629 |                  0.384615 |                      0 |                          0 |
| p04c_ab_charge  |    65 | mlp                    |  13 |         0.758509   |         1.16581  |                  0.846154 |                      0 |                          0 |
| p04c_ab_charge  |    65 | cnn1d                  |  13 |         0.0642688  |         0.571279 |                  0.461538 |                      0 |                          0 |
| p04c_ab_charge  |    65 | residual_cnn_meta      |  13 |         0.0639389  |         0.565239 |                  0.461538 |                      0 |                          0 |

## 7. Leakage, Systematics, And Caveats

- Train/held-out run overlap across all folds: `0`.
- P04b shuffled-target GBT all-row res68: `0.2806`.
- P04c shuffled-target GBT all-row res68: `0.5230`.
- P04b label-join misses: `0`; P04c label-join misses: `0`.
- Bootstrap CIs are run-block intervals, so they capture run-to-run instability but not uncertainty from the deterministic P09a label thresholds.
- The external charge proxies are still same-event detector correlations, not beam truth. P04c is topology-limited by the small event-matched A-stack sample; P04b is restricted to penetrating B2/B4/B6/B8 events.
- The residual CNN may overfit rare strata when an anomaly is nearly confined to one run. The fold audit and shuffled-target sentinel are therefore treated as mandatory controls.

## 8. Finding

cnn1d is best on p04b_downstream with res68 0.2103 [0.2013, 0.2275]; residual_cnn_meta is best on p04c_ab_charge with res68 0.5199 [0.5093, 0.5375]. The cross-target winner is residual_cnn_meta. Matched anomaly effects for that method: p04b_downstream baseline_excursion delta res68 0.0119 [-0.1213, 0.2110]; p04b_downstream novel_early_pretrigger delta res68 -0.0305 [-0.0951, 0.0410]; p04c_ab_charge baseline_excursion delta res68 0.1326 [-0.0249, 0.3966]; p04c_ab_charge novel_early_pretrigger delta res68 -0.0400 [-0.1219, 0.0509]. Thus the P04f anomaly-bias signal is tested outside the duplicate-readout target; any surviving positive deltas are external-proxy effects, while null or unstable deltas bound the same-event electronics interpretation.

## 9. Reproducibility

```bash
/home/billy/anaconda3/bin/python scripts/p04g_1781033470_1723_1a366adc_external_anomaly_charge_proxy_validation.py --config configs/p04g_1781033470_1723_1a366adc_external_anomaly_charge_proxy_validation.json
```

Primary artifacts: `result.json`, `manifest.json`, `input_sha256.csv`, `external_model_summary.csv`, `external_stratum_deltas.csv`, `external_by_run.csv`, `matched_strata_metrics.csv`, `fold_audit.csv`, `p04b_external_predictions.csv`, `p04c_external_predictions.csv`, and raw gate count CSVs.
