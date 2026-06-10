# P06b: amplitude-stratified timing bias ledger

- **Ticket:** `1781042379.490.2f714bdc`
- **Worker:** `testbeam-laptop-4`
- **Input:** raw B-stack ROOT files under `data/root/root`; no Monte Carlo or sorted-table shortcut
- **Primary split:** leave-one-run-out over Sample-II analysis runs 58, 59, 60, 61, 62, 63, and 65
- **Primary metric:** pooled downstream-pair residual `sigma68` in ns; lower is better
- **Bootstrap:** event-paired run-block bootstrap, 400 replicates unless stated otherwise

## Abstract

This study reproduces the selected-pulse count exactly from raw ROOT, rebuilds the P06a/S03 analytic baseline, and benchmarks five residual-correction models against it. The winner by pre-registered pooled pairwise sigma68 is **atom_gated_cnn** with sigma68 **1.4741 ns** and bootstrap 95% CI **[1.3868, 1.6066] ns**.

The main physics product is an atom-level ledger of signed residual bias, robust width, full RMS, and tail rates across amplitude, charge-proxy, peak-phase, saturation, q-template mismatch, baseline, dropout/anomaly, and topology strata.

## Reproduction Gate

All benchmark rows are conditional on the raw ROOT reproduction gate below. The count is recomputed by reading `HRDv` from every configured B-stack ROOT file, subtracting the median of samples 0-3, applying amplitude > 1000 ADC, and summing the selected B-stave pulses.

| quantity                           |   report_value |   reproduced |   delta |   tolerance | pass   |
|:-----------------------------------|---------------:|-------------:|--------:|------------:|:-------|
| total selected B-stave pulses      |         640737 |       640737 |       0 |           0 | True   |
| sample_ii_analysis selected_pulses |         125096 |       125096 |       0 |           0 | True   |
| sample_ii_analysis B2              |          88213 |        88213 |       0 |           0 | True   |
| sample_ii_analysis B4              |          21229 |        21229 |       0 |           0 | True   |
| sample_ii_analysis B6              |          11148 |        11148 |       0 |           0 | True   |
| sample_ii_analysis B8              |           4506 |         4506 |       0 |           0 | True   |

The S03a analytic closure is also rerun before the P06b fold study:

| method                  |   value |   ci_low |   ci_high |   n_pair_residuals | best_candidate   |   best_alpha |
|:------------------------|--------:|---------:|----------:|-------------------:|:-----------------|-------------:|
| s02_template_phase_base | 2.88915 |  2.63915 |   3.27718 |                198 | amp_only         |          100 |
| s03a_analytic_timewalk  | 1.49464 |  1.34645 |   1.63468 |                198 | amp_only         |          100 |

## Estimands And Equations

For event `e`, stave `s`, and method `m`, the geometry-corrected timestamp is

`tau_{e,s,m} = t_{e,s,m} - x_s v_TOF`, with `v_TOF = 0.078 ns/cm` and `x_s` spaced by 2 cm.

Pair residuals are `r_{e,a,b,m} = tau_{e,a,m} - tau_{e,b,m}`. Single-stave residuals use the other two downstream staves as an event clock: `u_{e,s,m} = tau_{e,s,m} - mean_{k != s} tau_{e,k,m}`.

The robust width is `sigma68(r) = (Q84(r) - Q16(r)) / 2`. Signed bias is the arithmetic mean residual; the ledger also records the median, full RMS around the mean, and tail fractions after subtracting the stratum median.

## Methods

Traditional baseline: fold-local S02 template-phase pickoff plus S03a amplitude-only analytic timewalk (`amp_only`, Ridge alpha 100). The analytic model is trained only on the six non-held-out runs in each leave-one-run-out fold.

ML/NN methods: each model predicts the same per-pulse residual target used by S03a, then subtracts that prediction from the template-phase timestamp. Ridge, HistGradientBoosting, MLP, 1D-CNN, and the new atom-gated residual CNN all use only waveform shape, charge/amplitude summaries, q-template residuals, baseline summaries, peak phase, and stave one-hot features. No model receives run id, event id, event order, pair residuals, or held-out labels.

The new architecture is an atom-gated residual CNN: a 1D waveform encoder with local and wider residual convolution blocks. A gate derived from pooled waveform features and atom/tabular summaries modulates channels before mean/max pooling, allowing rare q-template, baseline, and anomaly atoms to change the effective waveform representation without hard-coding a stratum-specific correction.

## Head-To-Head Benchmark

| method                 | method_label                    |     n |   sigma68_ns |   sigma68_ci_low_ns |   sigma68_ci_high_ns |   bias_ns |   full_rms_ns |   tail_frac_abs_gt5ns |
|:-----------------------|:--------------------------------|------:|-------------:|--------------------:|---------------------:|----------:|--------------:|----------------------:|
| atom_gated_cnn         | Atom-gated residual CNN         | 11460 |      1.47415 |             1.38683 |              1.60661 |   1.24448 |       2.38588 |             0.0122164 |
| cnn1d                  | 1D-CNN residual                 | 11460 |      1.5343  |             1.44498 |              1.68164 |   1.25132 |       2.41586 |             0.0121291 |
| traditional            | S02/S03 analytic template-phase | 11460 |      1.55109 |             1.36344 |              1.92986 |   1.24417 |       2.66699 |             0.0191099 |
| gradient_boosted_trees | HistGradientBoosting residual   | 11460 |      1.55187 |             1.42191 |              1.76825 |   1.26219 |       2.33244 |             0.0151832 |
| ridge                  | Ridge residual                  | 11460 |      1.57319 |             1.41855 |              1.87315 |   1.24693 |       2.54659 |             0.0161431 |
| mlp                    | MLP residual                    | 11460 |      1.65328 |             1.53158 |              1.77725 |   1.32453 |       2.43879 |             0.0137871 |

Per-pair scores:

| scope   | method                 |    n |   sigma68_ns |   sigma68_ci_low_ns |   sigma68_ci_high_ns |   bias_ns |   tail_frac_abs_gt5ns |
|:--------|:-----------------------|-----:|-------------:|--------------------:|---------------------:|----------:|----------------------:|
| B4-B6   | atom_gated_cnn         | 3820 |     0.828528 |            0.7631   |             0.881984 |  2.23177  |            0.0115183  |
| B4-B6   | cnn1d                  | 3820 |     0.953609 |            0.858775 |             1.03706  |  2.26651  |            0.0125654  |
| B4-B6   | gradient_boosted_trees | 3820 |     1.06322  |            0.93923  |             1.16539  |  2.17686  |            0.0151832  |
| B4-B6   | mlp                    | 3820 |     1.0653   |            0.96777  |             1.15558  |  2.25867  |            0.0146597  |
| B4-B6   | ridge                  | 3820 |     1.14434  |            0.920599 |             1.32989  |  2.1823   |            0.0125654  |
| B4-B6   | traditional            | 3820 |     1.19699  |            0.995255 |             1.31878  |  2.17497  |            0.0149215  |
| B4-B8   | atom_gated_cnn         | 3820 |     0.820604 |            0.731527 |             0.870083 |  1.86672  |            0.0143979  |
| B4-B8   | cnn1d                  | 3820 |     0.925641 |            0.823739 |             0.968792 |  1.87698  |            0.0151832  |
| B4-B8   | gradient_boosted_trees | 3820 |     1.06164  |            0.963172 |             1.14726  |  1.89328  |            0.017801   |
| B4-B8   | mlp                    | 3820 |     1.13685  |            1.06344  |             1.17896  |  1.9868   |            0.0172775  |
| B4-B8   | ridge                  | 3820 |     1.18352  |            1.0635   |             1.30521  |  1.87039  |            0.0191099  |
| B4-B8   | traditional            | 3820 |     1.20294  |            0.992283 |             1.34886  |  1.86625  |            0.0196335  |
| B6-B8   | atom_gated_cnn         | 3820 |     0.754341 |            0.705853 |             0.800035 | -0.365056 |            0.00680628 |
| B6-B8   | cnn1d                  | 3820 |     0.808652 |            0.743261 |             0.858447 | -0.389528 |            0.00759162 |
| B6-B8   | gradient_boosted_trees | 3820 |     0.948378 |            0.890511 |             1.00744  | -0.283579 |            0.00837696 |
| B6-B8   | mlp                    | 3820 |     0.99744  |            0.927318 |             1.06512  | -0.271869 |            0.0091623  |
| B6-B8   | traditional            | 3820 |     1.0236   |            0.940849 |             1.08414  | -0.308718 |            0.0091623  |
| B6-B8   | ridge                  | 3820 |     1.03717  |            0.980571 |             1.09531  | -0.311908 |            0.00890052 |

Per-run pooled-pair scores:

|   run | method                 |    n |   sigma68_ns |   bias_ns |   full_rms_ns |   tail_frac_abs_gt5ns |
|------:|:-----------------------|-----:|-------------:|----------:|--------------:|----------------------:|
|    58 | atom_gated_cnn         |  219 |      1.49633 |  1.17495  |       2.54202 |            0.0182648  |
|    58 | cnn1d                  |  219 |      1.42243 |  1.15786  |       2.5786  |            0.0182648  |
|    58 | gradient_boosted_trees |  219 |      1.44403 |  1.27012  |       2.63146 |            0.0182648  |
|    58 | mlp                    |  219 |      1.57389 |  1.40193  |       2.27138 |            0.0182648  |
|    58 | ridge                  |  219 |      1.34327 |  1.11122  |       2.09235 |            0.0182648  |
|    58 | traditional            |  219 |      1.18748 |  1.00415  |       2.67793 |            0.0182648  |
|    59 | atom_gated_cnn         | 2289 |      1.39215 |  1.10365  |       2.38235 |            0.0100481  |
|    59 | cnn1d                  | 2289 |      1.49025 |  1.05748  |       2.43631 |            0.0113587  |
|    59 | gradient_boosted_trees | 2289 |      1.4494  |  1.13424  |       2.18516 |            0.0100481  |
|    59 | mlp                    | 2289 |      1.54595 |  1.12541  |       2.45147 |            0.0100481  |
|    59 | ridge                  | 2289 |      1.50617 |  1.01929  |       2.44132 |            0.0113587  |
|    59 | traditional            | 2289 |      1.45871 |  0.935037 |       2.54019 |            0.0144168  |
|    60 | atom_gated_cnn         | 2424 |      1.39249 |  1.12731  |       2.14461 |            0.0144389  |
|    60 | cnn1d                  | 2424 |      1.43579 |  1.05977  |       2.22281 |            0.0144389  |
|    60 | gradient_boosted_trees | 2424 |      1.41223 |  1.0923   |       2.15058 |            0.0193894  |
|    60 | mlp                    | 2424 |      1.53612 |  1.1479   |       2.21858 |            0.0173267  |
|    60 | ridge                  | 2424 |      1.40425 |  1.10009  |       2.32938 |            0.0177393  |
|    60 | traditional            | 2424 |      1.3437  |  1.09513  |       2.39529 |            0.015264   |
|    61 | atom_gated_cnn         | 2799 |      1.69298 |  1.49996  |       2.66399 |            0.0150054  |
|    61 | cnn1d                  | 2799 |      1.80015 |  1.58987  |       2.59891 |            0.0142908  |
|    61 | gradient_boosted_trees | 2799 |      1.91066 |  1.60144  |       2.60147 |            0.0203644  |
|    61 | mlp                    | 2799 |      1.84386 |  1.60339  |       2.70164 |            0.0175063  |
|    61 | ridge                  | 2799 |      2.06807 |  1.76511  |       2.8774  |            0.0217935  |
|    61 | traditional            | 2799 |      2.12996 |  1.879    |       3.00806 |            0.0314398  |
|    62 | atom_gated_cnn         | 2421 |      1.38391 |  1.23532  |       2.33358 |            0.00743494 |
|    62 | cnn1d                  | 2421 |      1.46872 |  1.29318  |       2.38607 |            0.0086741  |
|    62 | gradient_boosted_trees | 2421 |      1.45832 |  1.22909  |       2.38842 |            0.0115655  |
|    62 | mlp                    | 2421 |      1.67701 |  1.4193   |       2.42355 |            0.0111524  |
|    62 | ridge                  | 2421 |      1.50026 |  1.14478  |       2.49143 |            0.0115655  |
|    62 | traditional            | 2421 |      1.469   |  1.09408  |       2.58419 |            0.0128046  |
|    63 | atom_gated_cnn         | 1110 |      1.50209 |  1.19223  |       2.31065 |            0.0126126  |
|    63 | cnn1d                  | 1110 |      1.45584 |  1.14241  |       2.3631  |            0.0144144  |
|    63 | gradient_boosted_trees | 1110 |      1.43549 |  1.11166  |       2.1166  |            0.0126126  |
|    63 | mlp                    | 1110 |      1.50124 |  1.1881   |       2.27576 |            0.0126126  |
|    63 | ridge                  | 1110 |      1.43923 |  1.01575  |       2.48261 |            0.018018   |
|    63 | traditional            | 1110 |      1.39132 |  1.01917  |       2.62807 |            0.0207207  |
|    65 | atom_gated_cnn         |  198 |      1.4019  |  1.17704  |       1.48861 |            0          |
|    65 | cnn1d                  |  198 |      1.4605  |  1.25353  |       1.52951 |            0          |
|    65 | gradient_boosted_trees |  198 |      1.45491 |  1.26523  |       1.59705 |            0          |
|    65 | mlp                    |  198 |      1.53866 |  1.36737  |       1.61559 |            0          |
|    65 | ridge                  |  198 |      1.44215 |  1.04611  |       1.5945  |            0.00505051 |
|    65 | traditional            |  198 |      1.49464 |  1.03035  |       1.69913 |            0.00505051 |

## Atomic Timing-Risk Ledger

Largest traditional pairwise timing-risk atoms with at least eight residuals:

| dimension         | stratum                       | pair   |    n |   bias_ns |   bias_ci_low_ns |   bias_ci_high_ns |   sigma68_ns |   sigma68_ci_low_ns |   sigma68_ci_high_ns |   full_rms_ns |   tail_frac_abs_gt5ns |
|:------------------|:------------------------------|:-------|-----:|----------:|-----------------:|------------------:|-------------:|--------------------:|---------------------:|--------------:|----------------------:|
| p09_anomaly_class | novel_broad_template_mismatch | B4-B6  |    8 |  2.24022  |      -10.4604    |          13.077   |     10.4985  |           1.7054    |             22.0823  |      13.7472  |             0.625     |
| p09_anomaly_class | novel_broad_template_mismatch | B4-B8  |   12 | -1.30652  |      -15.214     |           8.31775 |     10.3374  |           1.25961   |             22.7892  |      14.4583  |             0.5       |
| amplitude_bin     | amp_adc[4000,7000)            | B4-B6  |   19 |  5.65949  |       -1.27413   |          11.1454  |      8.23939 |           2.58238   |             18.6392  |      11.9818  |             0.526316  |
| charge_bin        | charge[40000,80000)           | B4-B8  |   15 |  5.54433  |       -2.54681   |          13.3498  |      7.43592 |           0.832956  |             23.0193  |      12.945   |             0.533333  |
| p09_anomaly_class | dropout                       | B4-B8  |   13 | -2.12264  |       -9.0187    |           2.63282 |      3.51709 |           0.0887802 |             15.0928  |       9.96555 |             0.230769  |
| amplitude_bin     | amp_adc[4000,7000)            | B4-B8  |  213 |  4.04915  |        2.71182   |           5.54433 |      2.39596 |           1.7412    |              3.21829 |       5.46402 |             0.103286  |
| charge_bin        | charge[40000,80000)           | B4-B6  |    8 |  3.1245   |        0.0384572 |           8.10427 |      2.32291 |           0.0507563 |              7.21737 |       4.64753 |             0.125     |
| q_template_bin    | q_template[0.12,0.2)          | B4-B8  |  528 |  2.27618  |        1.40357   |           3.02245 |      1.87098 |           1.36214   |              2.09667 |       3.61783 |             0.0549242 |
| q_template_bin    | q_template[0.08,0.12)         | B4-B6  |  595 |  2.28105  |        1.63074   |           3.15996 |      1.85702 |           1.38911   |              2.03614 |       2.10506 |             0.0151261 |
| amplitude_bin     | amp_adc[4000,7000)            | B6-B8  |  260 |  0.910402 |        0.31824   |           1.24601 |      1.81079 |           1.5707    |              2.01296 |       2.36394 |             0.0307692 |
| q_template_bin    | q_template[0.05,0.08)         | B4-B6  |  593 |  2.08415  |        1.44168   |           2.83741 |      1.80506 |           1.32528   |              2.03286 |       1.84797 |             0.0084317 |
| baseline_bin      | baseline_rms[32,64)           | B4-B6  |  106 |  2.76912  |        1.69323   |           3.62984 |      1.76692 |           1.12551   |              2.26308 |       4.28933 |             0.0283019 |
| q_template_bin    | q_template[0.05,0.08)         | B4-B8  |  700 |  1.79949  |        1.29359   |           2.55668 |      1.70471 |           1.43988   |              1.91018 |       1.73786 |             0.01      |
| q_template_bin    | q_template[0.08,0.12)         | B4-B8  |  696 |  1.7942   |        1.13549   |           2.53101 |      1.69253 |           1.42323   |              1.95135 |       1.81833 |             0.0143678 |
| baseline_bin      | baseline_rms[16,32)           | B4-B8  |  311 |  1.71407  |        1.10046   |           2.41974 |      1.69112 |           1.26493   |              1.96705 |       2.0219  |             0.0192926 |
| q_template_bin    | q_template[0.12,0.2)          | B4-B6  |  424 |  2.43897  |        1.77872   |           3.05917 |      1.68997 |           1.28406   |              1.89172 |       3.00197 |             0.0306604 |
| charge_bin        | charge[24000,40000)           | B4-B6  |  362 |  2.83928  |        1.82575   |           3.79674 |      1.5847  |           1.16263   |              2.03445 |       4.94893 |             0.0745856 |
| baseline_bin      | baseline_rms[0,8)             | B4-B8  | 1310 |  1.95134  |        1.37453   |           2.59843 |      1.56881 |           1.28943   |              1.74949 |       2.11332 |             0.0167939 |

Best nontraditional improvements over the traditional row in matched pairwise strata are listed below. Negative delta means the model narrows sigma68 relative to the analytic baseline in that stratum; these are exploratory atoms, not adoption claims unless support and run stability are adequate.

| dimension         | stratum                       | pair   | method                 |   traditional_sigma68_ns |   method_sigma68_ns |   delta_sigma68_ns |   traditional_bias_ns |   method_bias_ns |   delta_bias_ns |
|:------------------|:------------------------------|:-------|:-----------------------|-------------------------:|--------------------:|-------------------:|----------------------:|-----------------:|----------------:|
| saturation_flag   | True                          | B4-B8  | mlp                    |                  5.14988 |            1.87102  |          -3.27886  |              8.22778  |        10.0696   |        1.84178  |
| amplitude_bin     | amp_adc[4000,7000)            | B4-B6  | atom_gated_cnn         |                  8.23939 |            5.33002  |          -2.90938  |              5.65949  |         3.16217  |       -2.49731  |
| amplitude_bin     | amp_adc[4000,7000)            | B4-B6  | mlp                    |                  8.23939 |            5.35295  |          -2.88644  |              5.65949  |         2.83776  |       -2.82172  |
| amplitude_bin     | amp_adc[4000,7000)            | B4-B6  | cnn1d                  |                  8.23939 |            5.79697  |          -2.44243  |              5.65949  |         2.81343  |       -2.84605  |
| saturation_flag   | True                          | B6-B8  | mlp                    |                  3.55519 |            1.18508  |          -2.37011  |              2.80756  |         4.87226  |        2.0647   |
| saturation_flag   | True                          | B4-B8  | gradient_boosted_trees |                  5.14988 |            2.91115  |          -2.23873  |              8.22778  |         5.75501  |       -2.47277  |
| saturation_flag   | True                          | B6-B8  | gradient_boosted_trees |                  3.55519 |            1.38225  |          -2.17294  |              2.80756  |         0.458605 |       -2.34895  |
| amplitude_bin     | amp_adc[4000,7000)            | B4-B6  | ridge                  |                  8.23939 |            6.12885  |          -2.11055  |              5.65949  |         5.21041  |       -0.449079 |
| amplitude_bin     | amp_adc[4000,7000)            | B4-B6  | gradient_boosted_trees |                  8.23939 |            6.26282  |          -1.97657  |              5.65949  |         0.940527 |       -4.71896  |
| p09_anomaly_class | dropout                       | B4-B8  | gradient_boosted_trees |                  3.51709 |            1.74383  |          -1.77326  |             -2.12264  |        -1.40148  |        0.721157 |
| p09_anomaly_class | novel_broad_template_mismatch | B4-B8  | gradient_boosted_trees |                 10.3374  |            8.68034  |          -1.65711  |             -1.30652  |        -2.74323  |       -1.43671  |
| charge_bin        | charge[40000,80000)           | B4-B8  | atom_gated_cnn         |                  7.43592 |            5.7921   |          -1.64382  |              5.54433  |         3.10866  |       -2.43567  |
| saturation_flag   | True                          | B6-B8  | cnn1d                  |                  3.55519 |            1.99206  |          -1.56313  |              2.80756  |         0.761455 |       -2.0461   |
| amplitude_bin     | amp_adc[4000,7000)            | B4-B8  | atom_gated_cnn         |                  2.39596 |            1.19884  |          -1.19712  |              4.04915  |         2.31522  |       -1.73393  |
| amplitude_bin     | amp_adc[4000,7000)            | B4-B8  | gradient_boosted_trees |                  2.39596 |            1.28186  |          -1.1141   |              4.04915  |         1.90437  |       -2.14479  |
| saturation_flag   | True                          | B4-B8  | cnn1d                  |                  5.14988 |            4.06498  |          -1.0849   |              8.22778  |         6.36347  |       -1.86431  |
| amplitude_bin     | amp_adc[4000,7000)            | B4-B8  | cnn1d                  |                  2.39596 |            1.37752  |          -1.01844  |              4.04915  |         2.28005  |       -1.7691   |
| amplitude_bin     | amp_adc[4000,7000)            | B6-B8  | atom_gated_cnn         |                  1.81079 |            0.855519 |          -0.955271 |              0.910402 |        -0.373458 |       -1.28386  |
| amplitude_bin     | amp_adc[4000,7000)            | B4-B8  | mlp                    |                  2.39596 |            1.45319  |          -0.942771 |              4.04915  |         2.44713  |       -1.60202  |
| charge_bin        | charge[40000,80000)           | B4-B6  | gradient_boosted_trees |                  2.32291 |            1.44652  |          -0.876396 |              3.1245   |         2.89088  |       -0.23362  |

Single-stave overall rows:

| stave   | method                 |    n |   bias_ns |   sigma68_ns |   sigma68_ci_low_ns |   sigma68_ci_high_ns |   full_rms_ns |
|:--------|:-----------------------|-----:|----------:|-------------:|--------------------:|---------------------:|--------------:|
| B4      | atom_gated_cnn         | 3820 |  2.04924  |     0.727302 |            0.658534 |             0.784803 |       2.03687 |
| B6      | atom_gated_cnn         | 3820 | -1.29841  |     0.679934 |            0.621212 |             0.719317 |       1.45365 |
| B8      | atom_gated_cnn         | 3820 | -0.75083  |     0.670381 |            0.611922 |             0.719672 |       1.89251 |
| B4      | cnn1d                  | 3820 |  2.07175  |     0.842244 |            0.753567 |             0.893942 |       2.05613 |
| B6      | cnn1d                  | 3820 | -1.32802  |     0.773867 |            0.685658 |             0.823392 |       1.49706 |
| B8      | cnn1d                  | 3820 | -0.743727 |     0.74533  |            0.681068 |             0.78072  |       1.89135 |
| B4      | gradient_boosted_trees | 3820 |  2.03507  |     0.95686  |            0.863338 |             1.05586  |       1.94646 |
| B6      | gradient_boosted_trees | 3820 | -1.23022  |     0.894088 |            0.791869 |             0.978607 |       1.54273 |
| B8      | gradient_boosted_trees | 3820 | -0.80485  |     0.88647  |            0.81081  |             0.928818 |       1.83132 |
| B4      | mlp                    | 3820 |  2.12273  |     0.973463 |            0.916669 |             1.03411  |       2.11404 |
| B6      | mlp                    | 3820 | -1.26527  |     0.901228 |            0.815811 |             0.971682 |       1.54722 |
| B8      | mlp                    | 3820 | -0.857464 |     0.913365 |            0.860972 |             0.981437 |       1.9038  |
| B4      | ridge                  | 3820 |  2.02635  |     1.03102  |            0.862564 |             1.21434  |       2.23121 |
| B6      | ridge                  | 3820 | -1.2471   |     0.954211 |            0.822338 |             1.0454   |       1.63274 |
| B8      | ridge                  | 3820 | -0.779242 |     0.983046 |            0.915898 |             1.02202  |       2.04381 |
| B4      | traditional            | 3820 |  2.02061  |     1.06758  |            0.885235 |             1.21975  |       2.39972 |
| B6      | traditional            | 3820 | -1.24184  |     0.955571 |            0.854623 |             1.04428  |       1.71689 |
| B8      | traditional            | 3820 | -0.778768 |     0.940059 |            0.818369 |             1.03832  |       2.13281 |

## Model Selection And Sentinels

Fold-local CV summaries for tabular models:

|   heldout_run | method                 |   best_config |   feature_count |   config_index |   fold |   sigma68_target_residual_ns |    alpha |   l2_regularization |   max_iter |   max_leaf_nodes |   learning_rate | hidden_layer_sizes   |
|--------------:|:-----------------------|--------------:|----------------:|---------------:|-------:|-----------------------------:|---------:|--------------------:|-----------:|-----------------:|----------------:|:---------------------|
|            58 | gradient_boosted_trees |           nan |             nan |              0 |     -1 |                     0.990504 | nan      |                 0   |        180 |               15 |            0.05 | nan                  |
|            58 | gradient_boosted_trees |           nan |             nan |              1 |     -1 |                     0.996686 | nan      |                 0.1 |        180 |               15 |            0.05 | nan                  |
|            58 | mlp                    |           nan |             nan |              0 |     -1 |                     1.02516  |   0.0001 |               nan   |        220 |              nan |          nan    | [64, 32]             |
|            58 | ridge                  |           nan |             nan |              3 |     -1 |                     1.05547  | 100      |               nan   |        nan |              nan |          nan    | nan                  |
|            58 | ridge                  |           nan |             nan |              2 |     -1 |                     1.08028  |  10      |               nan   |        nan |              nan |          nan    | nan                  |
|            58 | ridge                  |           nan |             nan |              1 |     -1 |                     1.08496  |   1      |               nan   |        nan |              nan |          nan    | nan                  |
|            58 | ridge                  |           nan |             nan |              0 |     -1 |                     1.08686  |   0.1    |               nan   |        nan |              nan |          nan    | nan                  |
|            59 | gradient_boosted_trees |           nan |             nan |              1 |     -1 |                     1.00671  | nan      |                 0.1 |        180 |               15 |            0.05 | nan                  |
|            59 | gradient_boosted_trees |           nan |             nan |              0 |     -1 |                     1.01511  | nan      |                 0   |        180 |               15 |            0.05 | nan                  |
|            59 | mlp                    |           nan |             nan |              0 |     -1 |                     1.03301  |   0.0001 |               nan   |        220 |              nan |          nan    | [64, 32]             |
|            59 | ridge                  |           nan |             nan |              3 |     -1 |                     1.0506   | 100      |               nan   |        nan |              nan |          nan    | nan                  |
|            59 | ridge                  |           nan |             nan |              2 |     -1 |                     1.0783   |  10      |               nan   |        nan |              nan |          nan    | nan                  |
|            59 | ridge                  |           nan |             nan |              1 |     -1 |                     1.08963  |   1      |               nan   |        nan |              nan |          nan    | nan                  |
|            59 | ridge                  |           nan |             nan |              0 |     -1 |                     1.09189  |   0.1    |               nan   |        nan |              nan |          nan    | nan                  |
|            60 | gradient_boosted_trees |           nan |             nan |              1 |     -1 |                     1.0435   | nan      |                 0.1 |        180 |               15 |            0.05 | nan                  |
|            60 | gradient_boosted_trees |           nan |             nan |              0 |     -1 |                     1.04817  | nan      |                 0   |        180 |               15 |            0.05 | nan                  |
|            60 | mlp                    |           nan |             nan |              0 |     -1 |                     1.04055  |   0.0001 |               nan   |        220 |              nan |          nan    | [64, 32]             |
|            60 | ridge                  |           nan |             nan |              3 |     -1 |                     1.08943  | 100      |               nan   |        nan |              nan |          nan    | nan                  |
|            60 | ridge                  |           nan |             nan |              2 |     -1 |                     1.11623  |  10      |               nan   |        nan |              nan |          nan    | nan                  |
|            60 | ridge                  |           nan |             nan |              1 |     -1 |                     1.12406  |   1      |               nan   |        nan |              nan |          nan    | nan                  |
|            60 | ridge                  |           nan |             nan |              0 |     -1 |                     1.12789  |   0.1    |               nan   |        nan |              nan |          nan    | nan                  |
|            61 | gradient_boosted_trees |           nan |             nan |              0 |     -1 |                     0.926602 | nan      |                 0   |        180 |               15 |            0.05 | nan                  |
|            61 | gradient_boosted_trees |           nan |             nan |              1 |     -1 |                     0.92779  | nan      |                 0.1 |        180 |               15 |            0.05 | nan                  |
|            61 | mlp                    |           nan |             nan |              0 |     -1 |                     0.953163 |   0.0001 |               nan   |        220 |              nan |          nan    | [64, 32]             |
|            61 | ridge                  |           nan |             nan |              3 |     -1 |                     0.980734 | 100      |               nan   |        nan |              nan |          nan    | nan                  |
|            61 | ridge                  |           nan |             nan |              2 |     -1 |                     0.996955 |  10      |               nan   |        nan |              nan |          nan    | nan                  |
|            61 | ridge                  |           nan |             nan |              1 |     -1 |                     1.01096  |   1      |               nan   |        nan |              nan |          nan    | nan                  |
|            61 | ridge                  |           nan |             nan |              0 |     -1 |                     1.01533  |   0.1    |               nan   |        nan |              nan |          nan    | nan                  |
|            62 | gradient_boosted_trees |           nan |             nan |              0 |     -1 |                     1.00244  | nan      |                 0   |        180 |               15 |            0.05 | nan                  |
|            62 | gradient_boosted_trees |           nan |             nan |              1 |     -1 |                     1.00305  | nan      |                 0.1 |        180 |               15 |            0.05 | nan                  |

Leakage and bookkeeping checks:

| check                          | value                                                             | pass   | note                                                                                  |
|:-------------------------------|:------------------------------------------------------------------|:-------|:--------------------------------------------------------------------------------------|
| raw_root_reproduction_gate     | 1                                                                 | True   | reproduction_match_table.csv is exact before model fitting                            |
| train_heldout_event_id_overlap | 0                                                                 | True   | event_id includes run and ROOT event counters                                         |
| forbidden_feature_audit        | 0                                                                 | True   | models exclude run id, event id, event order, pair residuals, and held-out labels     |
| methods_present                | atom_gated_cnn,cnn1d,gradient_boosted_trees,mlp,ridge,traditional | True   | required traditional, ridge, gradient-boosted trees, MLP, 1D-CNN, and novel gated CNN |

## Systematics

- The bootstrap resamples runs and events but does not model alternative electronics calibrations, ROOT branch corruption, or unobserved beam composition changes.
- Baseline atoms are derived from baseline-subtracted pre-trigger samples because the reduced ROOT path supplies `HRDv` waveforms used by the existing S00/P06 loaders; this captures residual baseline structure, not the absolute pedestal before subtraction.
- Rare anomaly strata can have large sigma68 and unstable bias intervals. The report therefore uses support counts and run-block intervals as first-class outputs rather than treating the most extreme atom as a discovery by itself.
- Neural methods are intentionally compact CPU-scale models. A larger GPU model could change the ranking but would also need the same leave-one-run and leakage controls.
- The traditional method remains the reference because it is interpretable, fold-local, and already reproduces S03a exactly. ML wins are judged only on the same held-out residual rows.

## Caveats And Interpretation

The result is a timing-risk ledger, not a new absolute detector calibration. The winner named in `result.json` is `atom_gated_cnn`. The most consequential atoms are the high-amplitude/high-charge, q-template-mismatched, baseline-wide, and anomaly-tagged cells where full RMS and tail rates rise faster than the central sigma68. These atoms should be propagated as uncertainty inflation or abstention regions in PID, energy, pile-up, and covariance consumers.

## Artifacts

`method_summary.csv`, `per_run_metrics.csv`, `pairwise_atom_ledger.csv`, `single_stave_atom_ledger.csv`, `pairwise_delta_vs_traditional.csv`, `heldout_pulse_predictions.pkl`, `pairwise_residual_rows.csv.gz`, `single_stave_residual_rows.csv.gz`, `model_cv_and_fold_meta.csv`, `leakage_checks.csv`, `reproduction_match_table.csv`, `s03a_reproduction_benchmark.csv`, `input_sha256.csv`, `fig_method_sigma68_ci.png`, `result.json`, and `manifest.json` are in this report directory.

