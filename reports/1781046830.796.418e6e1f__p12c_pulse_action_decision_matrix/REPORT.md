# P12c Pulse-Action Decision Matrix

- **Study ID:** `P12c`
- **Ticket:** `1781046830.796.418e6e1f`
- **Author:** `testbeam-laptop-3`
- **Date:** 2026-06-11
- **Input checksum(s):** raw ROOT hashes are listed in `input_sha256.csv`.
- **Git commit:** `68d50bf01f516aee92eec30b9e5463d6fdeedefe`
- **Config:** `configs/p12c_1781046830_796_418e6e1f_pulse_action_decision_matrix.json`

## 0. Question

Which current pulse atoms should be passed through, corrected, abstained, or vetoed for timing, amplitude, saturation, pile-up, baseline, dropout, PID, energy, and covariance consumers, and can an ML decision model improve calibrated unsafe-action risk over a strong empirical action table?

## 1. Reproduction

The gate is a direct raw-ROOT scan of `h101/HRDv`. The script subtracts the median of samples 0--3 per channel, selects B2/B4/B6/B8, and requires peak amplitude above 1000 ADC. All action and model outputs are skipped unless this exact-count gate passes.

| quantity                                      |   report_value |   reproduced |   delta |   tolerance | pass   |
|:----------------------------------------------|---------------:|-------------:|--------:|------------:|:-------|
| total selected B-stave pulses                 |         640737 |       640737 |       0 |           0 | True   |
| sample_i_calib events with selected pulse     |         239559 |       239559 |       0 |           0 | True   |
| sample_i_calib selected pulses                |         248745 |       248745 |       0 |           0 | True   |
| sample_i_analysis events with selected pulse  |         243133 |       243133 |       0 |           0 | True   |
| sample_i_analysis selected pulses             |         252266 |       252266 |       0 |           0 | True   |
| sample_i_analysis B2 selected pulses          |         241422 |       241422 |       0 |           0 | True   |
| sample_i_analysis B4 selected pulses          |           6451 |         6451 |       0 |           0 | True   |
| sample_i_analysis B6 selected pulses          |           3094 |         3094 |       0 |           0 | True   |
| sample_i_analysis B8 selected pulses          |           1299 |         1299 |       0 |           0 | True   |
| sample_ii_calib events with selected pulse    |          12103 |        12103 |       0 |           0 | True   |
| sample_ii_calib selected pulses               |          14630 |        14630 |       0 |           0 | True   |
| sample_ii_analysis events with selected pulse |          89807 |        89807 |       0 |           0 | True   |
| sample_ii_analysis selected pulses            |         125096 |       125096 |       0 |           0 | True   |
| sample_ii_analysis B2 selected pulses         |          88213 |        88213 |       0 |           0 | True   |
| sample_ii_analysis B4 selected pulses         |          21229 |        21229 |       0 |           0 | True   |
| sample_ii_analysis B6 selected pulses         |          11148 |        11148 |       0 |           0 | True   |
| sample_ii_analysis B8 selected pulses         |           4506 |         4506 |       0 |           0 | True   |

## 2. Estimand and Action Algebra

For pulse `i`, let `a_i` be the vector of predeclared P12 atoms: shape, timing, amplitude, saturation, pile-up, baseline, dropout/anomaly, q-template, covariance, and charge-transfer support. The consumer action is a deterministic map

`A_c(i) = f_c(a_i) in {pass, correct, abstain, veto}`,

where `c` is a downstream consumer. The benchmark target is an operational unsafe indicator

`y_i = 1{charge_bad or timing_tail or pileup_like or baseline_harm or dropout_harm or covariance_harm}`.

This is not particle truth. It is a frozen consumer-risk label from raw-derived pulse atoms and the P12 charge-transfer closure residual. Charge-transfer, event id, pulse id, and run id are not model features.

## 3. Traditional Method

The strong traditional method is `empirical_bayes_action_table`. For a predictor atom cell `c`, with `s_c` unsafe pulses in `n_c` training pulses and train-fold global unsafe rate `pi`, it predicts

`p(y=1|c) = (s_c + k pi)/(n_c + k)`, with `k = 30`.

Unseen fine cells fall back to a coarse stave-amplitude-shape-timing-pileup-baseline table and then to the global rate. This makes the baseline a regularized action table rather than a strawman threshold.

## 4. ML and Neural Methods

The ML comparators are ridge logistic regression, histogram gradient-boosted trees, an MLP, a 1D-CNN over the standardized feature vector, and the new `action_prior_residual_cnn_new_arch`. The new architecture appends the empirical action-table logit as a prior to a small convolutional residual learner, so it can only win by learning departures from the traditional action prior. Training excludes the held-out Sample-II analysis runs 58, 59, 60, 61, 62, 63, and 65; uncertainty is a run-block bootstrap.

## 5. Head-to-head Benchmark

| method                             | family           |      n |   unsafe_rate |      auc | auc_ci95                                 |   average_precision |      brier | brier_ci95                                     |        ece | ece_ci95                                      |   pass_coverage_at_risk10 |   unsafe_rate_at_risk10 |   charge_res68_at_risk10 |   timing_sigma68_at_risk10 |
|:-----------------------------------|:-----------------|-------:|--------------:|---------:|:-----------------------------------------|--------------------:|-----------:|:-----------------------------------------------|-----------:|:----------------------------------------------|--------------------------:|------------------------:|-------------------------:|---------------------------:|
| mlp                                | nn               | 125096 |      0.823975 | 0.999806 | [0.9996363134319489, 0.9998944147502445] |            0.999961 | 0.00167791 | [0.0010057325894396465, 0.002659213694568593]  | 0.0012593  | [0.0005993886223126766, 0.002289455785757392] |                 0.176904  |             0.00858563  |                 1.10499  |                   0.824644 |
| gradient_boosted_trees             | ml               | 125096 |      0.823975 | 0.999877 | [0.9998372183860208, 0.9999210376069412] |            0.999977 | 0.00169079 | [0.0008819095574157756, 0.002654600947594115]  | 0.00248058 | [0.001830815763151143, 0.00358775340898764]   |                 0.176129  |             0.0077157   |                 1.10001  |                   0.823443 |
| ridge                              | ml               | 125096 |      0.823975 | 0.999499 | [0.9991013217037881, 0.99976331471666]   |            0.999903 | 0.00171716 | [0.0010448589893186859, 0.0027069952454477956] | 0.0015959  | [0.0008520496445747458, 0.002623236059845815] |                 0.177072  |             0.00862264  |                 1.1061   |                   0.824866 |
| action_prior_residual_cnn_new_arch | new_architecture | 125096 |      0.823975 | 0.999708 | [0.9995213399458575, 0.9998111124927945] |            0.999941 | 0.0183     | [0.0157459331451039, 0.020234980861923924]     | 0.0951541  | [0.08643719014505563, 0.10216944056372886]    |                 0.0935681 |             0.000512601 |                 0.854441 |                   0.822236 |
| empirical_bayes_action_table       | traditional      | 125096 |      0.823975 | 0.999687 | [0.9995435505597233, 0.9997902385767384] |            0.999927 | 0.0271025  | [0.019636056169280585, 0.03219893270612079]    | 0.11071    | [0.08814587000947602, 0.12535464061566143]    |                 0.14895   |             0.00311276  |                 1.00852  |                   0.800496 |
| 1d_cnn                             | nn               | 125096 |      0.823975 | 0.888499 | [0.8762658006152866, 0.9012384268642758] |            0.969791 | 0.106471   | [0.0944745539544087, 0.11891849930481169]      | 0.148152   | [0.11663848279674013, 0.18742010077486004]    |                 0         |           nan           |               nan        |                 nan        |

Winner by the preregistered primary metric, minimum held-out Brier score for unsafe-action risk, is `mlp` (`nn`), Brier `0.001678` with 95 percent CI `[0.0010057325894396465, 0.002659213694568593]`.

Run-level Brier scores:
|   run |    1d_cnn |   action_prior_residual_cnn_new_arch |   empirical_bayes_action_table |   gradient_boosted_trees |         mlp |       ridge |
|------:|----------:|-------------------------------------:|-------------------------------:|-------------------------:|------------:|------------:|
|    58 | 0.132558  |                            0.0110361 |                      0.0103796 |              0.000491883 | 0.000803446 | 0.000809074 |
|    59 | 0.100078  |                            0.0212216 |                      0.033687  |              0.00165984  | 0.00149527  | 0.00153955  |
|    60 | 0.0855367 |                            0.018754  |                      0.0319653 |              0.00160267  | 0.00158622  | 0.00161372  |
|    61 | 0.0914709 |                            0.0219389 |                      0.0344219 |              0.00434037  | 0.00431536  | 0.00437527  |
|    62 | 0.094401  |                            0.020398  |                      0.0331456 |              0.00145576  | 0.00142428  | 0.00146472  |
|    63 | 0.116067  |                            0.0175    |                      0.0243845 |              0.00103202  | 0.00103143  | 0.00110782  |
|    65 | 0.136361  |                            0.0150562 |                      0.0159078 |              0.000840534 | 0.000690611 | 0.000694794 |

## 6. Consumer Action Matrix

The table below is the deliverable action matrix. CIs are run-block bootstraps over the same held-out evaluation runs. `pass` means no consumer-specific action; `correct` means a correction can be attempted but should carry the listed systematics; `abstain` means do not use the pulse for that consumer; `veto` means remove it from that consumer's sample.

| consumer   | action   |     n |   support_fraction | support_fraction_ci95                         |   timing_sigma68_ns |   timing_full_rms_ns |   timing_tail_rate |   charge_bias_median |   charge_res68 |   charge_failure_rate |   pileup_candidate_fraction |   baseline_harm_rate |   covariance_coverage |   pid_energy_proxy_degradation |
|:-----------|:---------|------:|-------------------:|:----------------------------------------------|--------------------:|---------------------:|-------------------:|---------------------:|---------------:|----------------------:|----------------------------:|---------------------:|----------------------:|-------------------------------:|
| timing     | pass     | 20718 |         0.165617   | [0.1405073983848999, 0.19546633068524658]     |            0.811341 |              0.96578 |         0          |           -0.620388  |       1.09393  |             0.0085433 |                    0        |           0.018245   |             0         |                      0.0085433 |
| timing     | correct  |  5187 |         0.0414642  | [0.03245394019851279, 0.04859236940692845]    |            0.863811 |              3.91551 |         0.557933   |           -0.74371   |       1.53384  |             0.0379796 |                    0        |           0.0728745  |             0         |                      0.0379796 |
| timing     | abstain  | 48819 |         0.390252   | [0.37364193161183096, 0.41639105420754563]    |            1.51246  |              7.30461 |         0.127082   |           -0.0539619 |       1.30594  |             0.0191729 |                    0.987874 |           0.0214261  |             0.231836  |                      0.238186  |
| timing     | veto     | 50372 |         0.402667   | [0.3519522549114672, 0.4432670944880992]      |            2.12244  |              8.55432 |         0.0836774  |            2.01641   |       1.96056  |             0.15997   |                    0.811542 |           0.42071    |             0.451302  |                      0.473894  |
| amplitude  | pass     | 58910 |         0.470918   | [0.42777963628628185, 0.520098469079364]      |            1.28385  |              2.3057  |         0.0479036  |           -0.115736  |       1.14571  |             0         |                    0.631319 |           0.0116958  |             0         |                      0         |
| amplitude  | correct  |  3812 |         0.0304726  | [0.016857598927089892, 0.047831287981530704]  |            0.994576 |              1.14169 |         0          |           -1.33901   |       0.754886 |             0         |                    0        |           0          |             0         |                      0         |
| amplitude  | abstain  | 12233 |         0.0977889  | [0.07344213227222388, 0.11449243907414768]    |            1.14074  |              9.87625 |         0.532903   |           -0.655417  |       2.07617  |             0.107414  |                    0.910815 |           0.110766   |             0.944086  |                      1         |
| amplitude  | veto     | 50141 |         0.40082    | [0.34290628780058846, 0.4408332661053185]     |            2.11068  |              8.32794 |         0.0792166  |            2.01986   |       1.96055  |             0.160627  |                    0.813167 |           0.417822   |             0.448774  |                      0.47147   |
| saturation | pass     | 42039 |         0.336054   | [0.2929972736358945, 0.3901507808746808]      |            1.31847  |              2.01904 |         0.0445777  |           -0.0896147 |       0.973344 |             0         |                    0.633673 |           0.0120127  |             0         |                      0         |
| saturation | correct  | 20683 |         0.165337   | [0.14765745455568652, 0.18338836309558673]    |            1.22255  |              2.69769 |         0.0458347  |           -0.478787  |       1.45867  |             0         |                    0.510177 |           0.00889619 |             0         |                      0         |
| saturation | abstain  | 12246 |         0.0978928  | [0.07718891641960382, 0.11562200642881681]    |            1.14074  |              9.87567 |         0.532419   |           -0.657784  |       2.07927  |             0.108362  |                    0.910338 |           0.110812   |             0.944145  |                      1         |
| saturation | veto     | 50128 |         0.400716   | [0.35498656227684494, 0.4381252998279875]     |            2.11065  |              8.32816 |         0.0792172  |            2.02047   |       1.95984  |             0.160409  |                    0.813258 |           0.41789    |             0.448632  |                      0.471333  |
| pileup     | pass     |  5469 |         0.0437184  | [0.031283230478569825, 0.06289223478546709]   |            1.41021  |              3.40518 |         0.0563174  |           -1.44973   |       0.847757 |             0.0305357 |                    0        |           0.0111538  |             0         |                      0.0305357 |
| pileup     | correct  | 20436 |         0.163363   | [0.14245446023648087, 0.18851842248521133]    |            1.49672  |              3.12182 |         0.126541   |           -0.298361  |       1.10934  |             0.0101292 |                    0        |           0.0340086  |             0         |                      0.0101292 |
| pileup     | abstain  | 42822 |         0.342313   | [0.31287069423337266, 0.3877045369464547]     |            0.894049 |              2.65937 |         0.00483396 |           -0.0203121 |       1.26656  |             0.0176078 |                    0.983093 |           0.0275092  |             0.124259  |                      0.131498  |
| pileup     | veto     | 56369 |         0.450606   | [0.3893001114073048, 0.5031982169191466]      |            2.22638  |              9.1978  |         0.181163   |            1.75808   |       2.12257  |             0.14618   |                    0.833934 |           0.37361    |             0.509677  |                      0.529866  |
| baseline   | pass     | 72922 |         0.582928   | [0.5436445028997027, 0.6327272325718096]      |            1.52136  |              6.44879 |         0.124763   |           -0.230682  |       1.29264  |             0.0158114 |                    0.649968 |           0          |             0.140863  |                      0.149324  |
| baseline   | correct  |     0 |         0          | [0.0, 0.0]                                    |          nan        |            nan       |       nan          |          nan         |     nan        |           nan         |                  nan        |         nan          |           nan         |                    nan         |
| baseline   | abstain  |  1872 |         0.0149645  | [0.011761174251693794, 0.017959007126123912]  |            1.42639  |              6.60579 |         0.121261   |            1.27513   |       1.81881  |             0         |                    0.477564 |           1          |             0.631944  |                      0.631944  |
| baseline   | veto     | 50302 |         0.402107   | [0.3514180661298955, 0.43988050224994196]     |            2.11155  |              8.49019 |         0.0792811  |            2.01631   |       1.96992  |             0.163314  |                    0.811399 |           0.419904   |             0.449207  |                      0.473162  |
| dropout    | pass     | 26629 |         0.212869   | [0.18545273225814987, 0.24077634759000782]    |            1.51418  |              4.17881 |         0.116452   |           -0.663805  |       1.18405  |             0.0164482 |                    0        |           0.0414586  |             0.0271884 |                      0.0412332 |
| dropout    | correct  | 48339 |         0.386415   | [0.36998797613088646, 0.4123317254749132]     |            1.51466  |              7.41027 |         0.129109   |           -0.0415974 |       1.29018  |             0.0183909 |                    1        |           0.0194874  |             0.224208  |                      0.230621  |
| dropout    | abstain  |     0 |         0          | [0.0, 0.0]                                    |          nan        |            nan       |       nan          |          nan         |     nan        |           nan         |                  nan        |         nan          |           nan         |                    nan         |
| dropout    | veto     | 50128 |         0.400716   | [0.35524904595580276, 0.43989238710618683]    |            2.11065  |              8.32816 |         0.0792172  |            2.02047   |       1.95984  |             0.160409  |                    0.813258 |           0.41789    |             0.448632  |                      0.471333  |
| pid        | pass     | 50959 |         0.407359   | [0.3622572339674564, 0.46299706237527943]     |            1.26272  |              2.1364  |         0.0525521  |           -0.201919  |       1.21821  |             0         |                    0.544359 |           0.00737848 |             0         |                      0         |
| pid        | correct  | 11763 |         0.0940318  | [0.08374776906144502, 0.11242224661544091]    |            1.14019  |              3.32296 |         0.0122418  |           -0.107744  |       1.09647  |             0         |                    0.803452 |           0.0266089  |             0         |                      0         |
| pid        | abstain  | 12213 |         0.097629   | [0.0737141885145819, 0.11410341469654071]     |            1.14059  |              9.73989 |         0.532793   |           -0.655398  |       2.07665  |             0.10759   |                    0.910178 |           0.10931    |             0.943994  |                      1         |
| pid        | veto     | 50161 |         0.40098    | [0.35211184755106967, 0.43660020960649687]    |            2.11005  |              8.4223  |         0.0794243  |            2.01928   |       1.96162  |             0.160563  |                    0.813361 |           0.418054   |             0.448994  |                      0.471681  |
| energy     | pass     | 58910 |         0.470918   | [0.4281470191276549, 0.5182066486788649]      |            1.28385  |              2.3057  |         0.0479036  |           -0.115736  |       1.14571  |             0         |                    0.631319 |           0.0116958  |             0         |                      0         |
| energy     | correct  |  3812 |         0.0304726  | [0.016166655774077592, 0.04961645392533805]   |            0.994576 |              1.14169 |         0          |           -1.33901   |       0.754886 |             0         |                    0        |           0          |             0         |                      0         |
| energy     | abstain  | 12233 |         0.0977889  | [0.07388933964533416, 0.11672933658925566]    |            1.14074  |              9.87625 |         0.532903   |           -0.655417  |       2.07617  |             0.107414  |                    0.910815 |           0.110766   |             0.944086  |                      1         |
| energy     | veto     | 50141 |         0.40082    | [0.357922151108577, 0.4402621633316462]       |            2.11068  |              8.32794 |         0.0792166  |            2.01986   |       1.96055  |             0.160627  |                    0.813167 |           0.417822   |             0.448774  |                      0.47147   |
| covariance | pass     | 91045 |         0.727801   | [0.669397880165481, 0.8009077209131188]       |            1.2268   |              2.12674 |         0.0317865  |            0.225675  |       1.67316  |             0.0200121 |                    0.693778 |           0.0299962  |             0         |                      0.0200121 |
| covariance | correct  |     0 |         0          | [0.0, 0.0]                                    |          nan        |            nan       |       nan          |          nan         |     nan        |           nan         |                  nan        |         nan          |           nan         |                    nan         |
| covariance | abstain  | 33745 |         0.269753   | [0.18589279410476806, 0.3234319299694683]     |            2.31298  |              9.08803 |         0.304015   |            0.683028  |       3.20397  |             0.219173  |                    0.760113 |           0.591732   |             1         |                      1         |
| covariance | veto     |   306 |         0.00244612 | [0.001560480833744237, 0.0032960132495865554] |            5.42128  |             43.4735  |         0.522876   |           -2.57785   |       6.76282  |             0.490196  |                    0.95098  |           0.964052   |             1         |                      1         |

## 7. Action-knockout Falsification

The explicit falsification test is an action knockout: if `pass+correct` did not reduce charge/timing degradation relative to all events, or if the empirical action table were matched by shuffled/domain-sentinel behavior, the action matrix would be rejected. The retained pulses improve charge and timing support at the cost of coverage; the full benchmark table keeps all methods, including weak CNN cases.

| policy                   |      n |   support_fraction |   timing_sigma68_ns |   timing_full_rms_ns |   timing_tail_rate |   charge_bias_median |   charge_res68 |   charge_failure_rate |   pileup_candidate_fraction |   baseline_harm_rate |   covariance_coverage |   pid_energy_proxy_degradation |
|:-------------------------|-------:|-------------------:|--------------------:|---------------------:|-------------------:|---------------------:|---------------:|----------------------:|----------------------------:|---------------------:|----------------------:|-------------------------------:|
| no_action_all_events     | 125096 |          1         |            1.87646  |             7.37499  |           0.106422 |            0.282355  |       2.07315  |             0.0748865 |                    0.712301 |            0.183811  |              0.272199 |                       0.286764 |
| oracle_pass_only         |  16607 |          0.132754  |            0.799187 |             0.962406 |           0        |           -0.377192  |       0.999133 |             0         |                    0        |            0         |              0        |                       0        |
| oracle_correct_only      |   8235 |          0.0658294 |            0.864045 |             3.72235  |           0.342684 |           -1.12564   |       1.15657  |             0         |                    0        |            0         |              0        |                       0        |
| oracle_abstain_only      |  49816 |          0.398222  |            1.50927  |             7.12351  |           0.12506  |           -0.0440568 |       1.32786  |             0.0208166 |                    0.965814 |            0.0403284 |              0.227317 |                       0.239602 |
| oracle_veto_only         |  50438 |          0.403194  |            2.13252  |             8.63902  |           0.08448  |            2.00597   |       1.98159  |             0.165173  |                    0.81274  |            0.416055  |              0.450593 |                       0.474583 |
| oracle_pass_plus_correct |  24842 |          0.198583  |            1.48255  |             3.09344  |           0.113598 |           -0.64974   |       1.11743  |             0         |                    0        |            0         |              0        |                       0        |
| oracle_all_but_veto      |  74658 |          0.596806  |            1.51944  |             6.28414  |           0.121246 |           -0.213616  |       1.32336  |             0.01389   |                    0.644445 |            0.0269094 |              0.151678 |                       0.159876 |

## 8. Systematics, Caveats, and Threats to Validity

- **Benchmark/selection:** the baseline is a regularized empirical action table over the same atom cells used to define downstream actions; it is the relevant conventional comparator.
- **Data leakage:** all splits are by run; run, event, pulse identifiers, and the unsafe target are excluded from model features. Charge-transfer labels are evaluation targets, not predictors.
- **Metric misuse:** the report gives support fraction, robust timing width, full RMS, tail rate, charge bias/res68, pile-up fraction, baseline harm, covariance coverage, and PID/energy degradation, rather than only a core width.
- **Post-hoc selection:** actions, risk threshold, held-out runs, and the minimum-Brier winner criterion are fixed in the config/script before tables are generated.
- **Truth limitation:** `unsafe_for_consumer` is an operational risk label. It is not absolute energy, PID, or pile-up truth; downstream users should treat abstain/veto cells as support boundaries until independent truth confirms them.

Leakage checks:
| check                                             | value                                                                                                                                                                                                                                                                                                                                                                                                        | pass   |
|:--------------------------------------------------|:-------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|:-------|
| heldout_runs_excluded_from_training               | 58,59,60,61,62,63,65                                                                                                                                                                                                                                                                                                                                                                                         | True   |
| model_features_exclude_event_ids                  | log_amp,amplitude_adc,area_over_amp,peak_sample,width035_samples,width050_samples,plateau_count,secondary_peak_rel,late_fraction,seed_baseline_adc,pre_rms_adc,pre_max_exc_adc,adaptive_lowering_adc,event_timing_abs_resid_ns_filled,active_atom_count_no_charge,stave,amplitude_atom,shape_atom,timing_atom,saturation_atom,pileup_atom,baseline_atom,dropout_anomaly_atom,q_template_atom,covariance_atom | True   |
| target_unsafe_for_consumer_excluded_from_features | unsafe_for_consumer                                                                                                                                                                                                                                                                                                                                                                                          | True   |
| charge_label_excluded_from_features               | charge_transfer_error                                                                                                                                                                                                                                                                                                                                                                                        | True   |
| evaluation_runs_present                           | 7                                                                                                                                                                                                                                                                                                                                                                                                            | True   |
| training_rows_after_cap                           | 30000                                                                                                                                                                                                                                                                                                                                                                                                        | True   |
| evaluation_rows                                   | 125096                                                                                                                                                                                                                                                                                                                                                                                                       | True   |

## 9. Findings and Next Steps

The winning method is `mlp`. The scientific result is that action-table regularization is strong, but calibrated ML can improve the unsafe-risk surface when it lowers Brier score without collapsing pass coverage. The action matrix suggests a concrete hypothesis: most downstream harm is not a single pathology but coupled charge, timing, pile-up, and covariance support. The next decisive test is to freeze this matrix and measure whether downstream PID/energy calibration improves when unsupported cells are abstained rather than reweighted.

Queued follow-up candidate: `P12d: test whether the P12c pass/correct/abstain/veto matrix improves downstream PID and energy calibration when frozen before fitting consumer models`. Its expected information gain is direct: it tests whether the P12c matrix is a useful consumer policy or merely a descriptive risk table.

## 10. Reproducibility

```bash
/home/billy/anaconda3/bin/python scripts/p12c_1781046830_796_418e6e1f_pulse_action_decision_matrix.py --config configs/p12c_1781046830_796_418e6e1f_pulse_action_decision_matrix.json
```

Runtime: 492.7 s.
