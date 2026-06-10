# S03j: selector-specific timewalk support map

- **Ticket:** 1781030650.597.5d382001
- **Worker:** testbeam-laptop-3
- **Date:** 2026-06-10
- **Config:** `configs/s03j_1781030650_597_5d382001_selector_timewalk_support.yaml`
- **Input:** raw B-stack ROOT files under `data/root/root`
- **Split:** leave-one-run-out over Sample-II analysis runs 58, 59, 60, 61, 62, 63, and 65

## 1. Raw-ROOT reproduction gate

The S00 median-first-four selected-pulse count and the S00a dynamic-range count were recomputed directly from raw ROOT before any model fitting.

| quantity                           |   report_value |   reproduced |   delta |   tolerance | pass   |
|:-----------------------------------|---------------:|-------------:|--------:|------------:|:-------|
| total selected B-stave pulses      |         640737 |       640737 |       0 |           0 | True   |
| sample_ii_analysis selected_pulses |         125096 |       125096 |       0 |           0 | True   |
| sample_ii_analysis B2              |          88213 |        88213 |       0 |           0 | True   |
| sample_ii_analysis B4              |          21229 |        21229 |       0 |           0 | True   |
| sample_ii_analysis B6              |          11148 |        11148 |       0 |           0 | True   |
| sample_ii_analysis B8              |           4506 |         4506 |       0 |           0 | True   |

| quantity                              |   report_value |   reproduced |   delta |   tolerance | pass   |
|:--------------------------------------|---------------:|-------------:|--------:|------------:|:-------|
| S00 median-first-four selected pulses |         640737 |       640737 |       0 |           0 | True   |
| S00a dynamic-range equivalent count   |         706373 |       706373 |       0 |           0 | True   |
| Dynamic-only excess pulses            |          65636 |        65636 |       0 |           0 | True   |
| Median-only pulses                    |              0 |            0 |       0 |           0 | True   |

## 2. Strata and support

The median-selected stratum contains events whose B4, B6, and B8 baseline-subtracted amplitudes all exceed 1000 ADC. The dynamic-only stratum contains the additional events admitted by dynamic-range selection but not by median-first-four. The matched-control stratum is a deterministic run- and amplitude-binned subsample of median-selected events with the same target bin counts as the dynamic-only support whenever enough median events exist.

| stratum         |   total_events |   min_run_events |   median_amp_adc |
|:----------------|---------------:|-----------------:|-----------------:|
| dynamic_only    |            672 |               17 |              705 |
| matched_control |             87 |                1 |             1935 |
| median_selected |           3820 |               66 |             2717 |

| stratum         |   run |   n_events |   n_pulses |   event_amp_median_adc |   event_amp_p10_adc |   event_amp_p90_adc |   min_stave_amp_median_adc |   max_dynamic_amp_median_adc |
|:----------------|------:|-----------:|-----------:|-----------------------:|--------------------:|--------------------:|---------------------------:|-----------------------------:|
| dynamic_only    |    58 |         17 |         51 |                464.833 |             154.433 |             610.333 |                     256    |                       3150   |
| dynamic_only    |    59 |        137 |        411 |                835.5   |             224.767 |            1504.17  |                     433    |                       3178   |
| dynamic_only    |    60 |        147 |        441 |                688.667 |             288.667 |            1528.13  |                     439.5  |                       3299   |
| dynamic_only    |    61 |        142 |        426 |                713.083 |             233.717 |            1372.25  |                     423.25 |                       3228.5 |
| dynamic_only    |    62 |        134 |        402 |                728.5   |             233.1   |            1418.12  |                     428.75 |                       3223.5 |
| dynamic_only    |    63 |         71 |        213 |                705     |             301.167 |            1334.67  |                     426    |                       3267   |
| dynamic_only    |    65 |         24 |         72 |                515     |             232.1   |            1149.37  |                     338.75 |                       3194   |
| matched_control |    58 |          1 |          3 |               1247.5   |            1247.5   |            1247.5   |                    1103    |                       1830   |
| matched_control |    59 |         22 |         66 |               1935     |            1360.28  |            2478.23  |                    1399    |                       2751   |
| matched_control |    60 |         21 |         63 |               2393.67  |            1446.17  |            2491.33  |                    1671    |                       3116   |
| matched_control |    61 |         19 |         57 |               2059.5   |            1394.53  |            2539.23  |                    1645    |                       3080   |
| matched_control |    62 |         16 |         48 |               1892.5   |            1345.33  |            2525.75  |                    1327.75 |                       3152   |
| matched_control |    63 |          5 |         15 |               1999.5   |            1362.97  |            2326.13  |                    1227.5  |                       3012   |
| matched_control |    65 |          3 |          9 |               1396     |            1332.53  |            2207.6   |                    1191.5  |                       2403   |
| median_selected |    58 |         73 |        219 |               2781.83  |            2119.83  |            3373.33  |                    2138.5  |                       3438   |
| median_selected |    59 |        763 |       2289 |               2570.67  |            1944.23  |            3272.87  |                    1967    |                       3312   |
| median_selected |    60 |        808 |       2424 |               2954.5   |            2290.58  |            3659.4   |                    2398.25 |                       3717   |
| median_selected |    61 |        933 |       2799 |               2809.5   |            2087.37  |            3499.63  |                    2235.5  |                       3535   |
| median_selected |    62 |        807 |       2421 |               2717     |            2079.67  |            3381.77  |                    2140    |                       3453   |
| median_selected |    63 |        370 |       1110 |               2606.17  |            1905.82  |            3181.27  |                    1955.25 |                       3420   |
| median_selected |    65 |         66 |        198 |               2446.17  |            1899.08  |            3104.5   |                    1868.25 |                       3317.5 |

## 3. Methods

For each held-out run and each stratum, templates and all residual-correction models are fit only on the other runs. The base time is template phase,

\[ t_i^{(0)} = \Delta t_{\mathrm{template}}(x_i), \qquad r_i = t_i^{(0)} - \frac{1}{2}\sum_{j\neq i} t_j^{(0)}. \]

The strong traditional models are S03a amplitude Ridge and the S03d signed physics prior. The signed prior solves

\[ \min_\beta \lVert X\beta-r\rVert_2^2, \qquad \beta_{s,k}\ge 0 \text{ for inverse-amplitude terms}, \]

where the sign constraint encodes the lower-amplitude-later timewalk prior. ML/NN comparators are a Ridge residual model, histogram gradient-boosted trees, a heteroskedastic MLP on normalized 18-sample waveforms, a 1D CNN on the same samples plus stave one-hot, and a new hybrid residual ensemble that averages the Ridge, HGB, MLP, and CNN residual predictions. No model receives run id, event id, event order, pair residuals, other-stave timing, or held-out labels.

The primary metric is held-out pairwise sigma68 after time-of-flight correction. Bootstrap intervals inside a held-out run resample events; pooled intervals resample held-out runs. The support-map bias metric is the linear slope of pair residual versus log(1 + pair amplitude).

## 4. Results

Per-run event-bootstrap results:

| stratum         |   heldout_run | method                     |   sigma68_ns |   ci_low |   ci_high |   full_rms_ns |   tail_frac_abs_gt5ns |   bias_vs_logamp_slope_ns |   bias_slope_ci_low |   bias_slope_ci_high |   delta_vs_traditional_ns |
|:----------------|--------------:|:---------------------------|-------------:|---------:|----------:|--------------:|----------------------:|--------------------------:|--------------------:|---------------------:|--------------------------:|
| median_selected |            58 | hybrid_residual_ensemble   |     0.914723 | 0.830571 |  1.14908  |      2.61539  |            0.0182648  |               1.8919      |          0.118636   |           5.29531    |               -0.315951   |
| median_selected |            58 | gradient_boosted_trees_hgb |     1.22067  | 1.11488  |  1.44859  |      2.56017  |            0.0136986  |               0.107254    |         -1.78349    |           3.08115    |               -0.010006   |
| median_selected |            58 | signed_physics_prior       |     1.23067  | 1.18001  |  1.35023  |      2.71942  |            0.0228311  |               0.0804512   |         -1.83477    |           3.12033    |                0          |
| median_selected |            58 | s03a_amp_only_ridge        |     1.23348  | 1.14983  |  1.51072  |      2.66817  |            0.0182648  |               0.380671    |         -1.60144    |           3.31692    |                0.00280354 |
| median_selected |            58 | ridge_ml                   |     1.30605  | 1.17967  |  1.45254  |      2.81854  |            0.0228311  |               0.451347    |         -1.68094    |           3.78054    |                0.0753795  |
| median_selected |            58 | mlp_waveform               |     2.3522   | 2.31387  |  2.45494  |      3.25575  |            0.0547945  |               3.25601     |          1.33237    |           6.85158    |                1.12153    |
| median_selected |            58 | template_phase_base        |     2.6428   | 2.6428   |  2.77317  |      3.54397  |            0.0776256  |               3.68782     |          1.73174    |           7.53752    |                1.41213    |
| median_selected |            58 | cnn_1d_waveform            |     2.64393  | 2.61888  |  2.69263  |      3.53794  |            0.0593607  |               3.75299     |          1.77821    |           7.63554    |                1.41325    |
| median_selected |            59 | hybrid_residual_ensemble   |     1.23459  | 1.19154  |  1.29899  |      2.36316  |            0.013543   |               0.710823    |          0.0835166  |           1.19983    |               -0.224914   |
| median_selected |            59 | gradient_boosted_trees_hgb |     1.33363  | 1.26682  |  1.38948  |      2.4153   |            0.0131062  |              -1.63531     |         -2.27742    |          -1.20428    |               -0.125879   |
| median_selected |            59 | s03a_amp_only_ridge        |     1.43822  | 1.38667  |  1.50238  |      2.53694  |            0.0144168  |              -1.15756     |         -1.80219    |          -0.642895   |               -0.0212848  |
| median_selected |            59 | signed_physics_prior       |     1.4595   | 1.37301  |  1.57021  |      2.56143  |            0.0157274  |              -1.09927     |         -1.77373    |          -0.605651   |                0          |
| median_selected |            59 | ridge_ml                   |     1.52944  | 1.4563   |  1.59256  |      2.5186   |            0.0139799  |              -1.34126     |         -1.9802     |          -0.875371   |                0.0699333  |
| median_selected |            59 | mlp_waveform               |     2.74207  | 2.59957  |  2.7935   |      3.16304  |            0.0498034  |               2.67297     |          1.99805    |           3.21695    |                1.28257    |
| median_selected |            59 | cnn_1d_waveform            |     2.96711  | 2.89585  |  3.13794  |      3.34622  |            0.0677152  |               3.14689     |          2.49551    |           3.6838     |                1.50761    |
| median_selected |            59 | template_phase_base        |     2.99232  | 2.87333  |  3.12333  |      3.34278  |            0.0677152  |               3.06363     |          2.40789    |           3.60207    |                1.53281    |
| median_selected |            60 | hybrid_residual_ensemble   |     1.15712  | 1.09029  |  1.21403  |      2.2203   |            0.0127888  |               1.58044     |          1.13572    |           1.9952     |               -0.224423   |
| median_selected |            60 | gradient_boosted_trees_hgb |     1.32779  | 1.23733  |  1.36695  |      2.14528  |            0.0165017  |              -1.27626     |         -1.69555    |          -0.972344   |               -0.0537566  |
| median_selected |            60 | s03a_amp_only_ridge        |     1.35394  | 1.304    |  1.39311  |      2.39579  |            0.0144389  |              -0.353081    |         -0.863931   |           0.0811787  |               -0.0276     |
| median_selected |            60 | ridge_ml                   |     1.35655  | 1.30307  |  1.40407  |      2.30124  |            0.0140264  |              -0.186359    |         -0.641816   |           0.194373   |               -0.0249889  |
| median_selected |            60 | signed_physics_prior       |     1.38154  | 1.28372  |  1.45393  |      2.41653  |            0.0148515  |               0.0301271   |         -0.468508   |           0.467734   |                0          |
| median_selected |            60 | mlp_waveform               |     2.43007  | 2.38876  |  2.47821  |      3.08422  |            0.070132   |               3.63665     |          3.08398    |           4.17927    |                1.04853    |
| median_selected |            60 | cnn_1d_waveform            |     2.64198  | 2.62884  |  2.72499  |      3.27595  |            0.0932343  |               4.14771     |          3.57719    |           4.68861    |                1.26043    |
| median_selected |            60 | template_phase_base        |     2.66393  | 2.66393  |  2.7113   |      3.279    |            0.0944719  |               4.08159     |          3.51031    |           4.6229     |                1.28239    |
| median_selected |            61 | hybrid_residual_ensemble   |     1.21515  | 1.14423  |  1.2776   |      2.46549  |            0.0150054  |               1.673       |          1.18001    |           2.25748    |               -0.952193   |
| median_selected |            61 | gradient_boosted_trees_hgb |     1.93983  | 1.86855  |  2.01882  |      2.70649  |            0.0232226  |              -0.938012    |         -1.37198    |          -0.520413   |               -0.227514   |
| median_selected |            61 | ridge_ml                   |     2.00867  | 1.91225  |  2.13382  |      2.95021  |            0.0271526  |              -0.610088    |         -1.1746     |          -0.00804714 |               -0.158671   |
| median_selected |            61 | s03a_amp_only_ridge        |     2.08935  | 2.00323  |  2.22224  |      3.01209  |            0.0307253  |              -0.674894    |         -1.23199    |          -0.056673   |               -0.0779996  |
| median_selected |            61 | signed_physics_prior       |     2.16735  | 2.01674  |  2.2942   |      3.03031  |            0.0350125  |              -0.291853    |         -0.906856   |           0.328768   |                0          |
| median_selected |            61 | mlp_waveform               |     2.41629  | 2.3918   |  2.43857  |      3.06391  |            0.0335834  |               3.88554     |          3.34266    |           4.51174    |                0.248947   |
| median_selected |            61 | template_phase_base        |     2.70351  | 2.70351  |  2.70351  |      3.20716  |            0.0428725  |               4.29511     |          3.74442    |           4.92609    |                0.536167   |
| median_selected |            61 | cnn_1d_waveform            |     2.71987  | 2.712    |  2.72234  |      3.21     |            0.0425152  |               4.35454     |          3.80265    |           4.98401    |                0.552527   |
| median_selected |            62 | hybrid_residual_ensemble   |     1.21342  | 1.17053  |  1.26774  |      2.34354  |            0.00991326 |               1.31393     |          0.484874   |           2.1518     |               -0.286817   |
| median_selected |            62 | gradient_boosted_trees_hgb |     1.35997  | 1.30424  |  1.4208   |      2.29922  |            0.00950021 |              -1.16197     |         -1.93343    |          -0.287587   |               -0.140266   |
| median_selected |            62 | s03a_amp_only_ridge        |     1.43805  | 1.37468  |  1.48748  |      2.60643  |            0.0119785  |              -0.760175    |         -1.76703    |           0.246182   |               -0.0621839  |
| median_selected |            62 | ridge_ml                   |     1.47149  | 1.41676  |  1.53715  |      2.51141  |            0.0123916  |              -0.780256    |         -1.64189    |           0.177821   |               -0.0287406  |
| median_selected |            62 | signed_physics_prior       |     1.50023  | 1.43186  |  1.54879  |      2.60639  |            0.0140438  |              -0.670067    |         -1.64467    |           0.326312   |                0          |
| median_selected |            62 | mlp_waveform               |     2.61552  | 2.57814  |  2.75719  |      3.16131  |            0.0516316  |               3.33759     |          2.43536    |           4.1793     |                1.11528    |
| median_selected |            62 | template_phase_base        |     2.90117  | 2.90117  |  3.02631  |      3.35891  |            0.0929368  |               3.78351     |          2.85251    |           4.64922    |                1.40094    |
| median_selected |            62 | cnn_1d_waveform            |     2.90906  | 2.90206  |  2.98169  |      3.35781  |            0.0698059  |               3.86035     |          2.93665    |           4.74003    |                1.40883    |
| median_selected |            63 | hybrid_residual_ensemble   |     1.24393  | 1.15529  |  1.33769  |      2.35777  |            0.018018   |               1.08314     |          0.0541546  |           2.01443    |               -0.0985401  |
| median_selected |            63 | signed_physics_prior       |     1.34247  | 1.2734   |  1.49203  |      2.63509  |            0.0198198  |              -0.9571      |         -2.17492    |           0.0975676  |                0          |
| median_selected |            63 | gradient_boosted_trees_hgb |     1.3495   | 1.25005  |  1.44678  |      2.20532  |            0.0171171  |              -1.18766     |         -2.13765    |          -0.364879   |                0.0070251  |
| median_selected |            63 | ridge_ml                   |     1.39069  | 1.31457  |  1.48002  |      2.53956  |            0.018018   |              -0.923672    |         -1.96382    |           0.10064    |                0.0482157  |
| median_selected |            63 | s03a_amp_only_ridge        |     1.40435  | 1.3364   |  1.48931  |      2.62266  |            0.018018   |              -1.07206     |         -2.27872    |          -0.0381595  |                0.0618737  |
| median_selected |            63 | mlp_waveform               |     2.56258  | 2.49747  |  2.74513  |      3.16787  |            0.0567568  |               2.92964     |          1.77756    |           3.94576    |                1.2201     |
| median_selected |            63 | template_phase_base        |     2.87872  | 2.87872  |  3.01249  |      3.38179  |            0.0963964  |               3.41413     |          2.23585    |           4.46519    |                1.53624    |
| median_selected |            63 | cnn_1d_waveform            |     2.89897  | 2.88586  |  2.97807  |      3.37561  |            0.0774775  |               3.51426     |          2.32743    |           4.56718    |                1.5565     |
| median_selected |            65 | hybrid_residual_ensemble   |     1.2953   | 0.978973 |  1.53852  |      1.33925  |            0          |               1.14574     |          0.440776   |           2.03151    |               -0.259999   |
| median_selected |            65 | gradient_boosted_trees_hgb |     1.38795  | 1.17645  |  1.6405   |      1.56574  |            0.00505051 |              -0.495402    |         -1.50559    |           0.390567   |               -0.167342   |
| median_selected |            65 | s03a_amp_only_ridge        |     1.40929  | 1.25454  |  1.70663  |      1.71721  |            0.00505051 |              -0.81915     |         -1.87295    |           0.244687   |               -0.146      |
| median_selected |            65 | ridge_ml                   |     1.41576  | 1.27129  |  1.63106  |      1.68708  |            0.00505051 |              -0.69606     |         -1.65492    |           0.154996   |               -0.139533   |
| median_selected |            65 | signed_physics_prior       |     1.55529  | 1.29263  |  1.68189  |      1.72047  |            0.00505051 |              -1.01338     |         -2.04652    |          -0.112046   |                0          |
| median_selected |            65 | mlp_waveform               |     2.48076  | 2.34168  |  2.79621  |      2.28044  |            0.0151515  |               2.5836      |          1.68972    |           3.62325    |                0.925463   |
| median_selected |            65 | cnn_1d_waveform            |     2.88256  | 2.63749  |  3.17765  |      2.55955  |            0.0252525  |               3.1908      |          2.21223    |           4.24131    |                1.32727    |
| median_selected |            65 | template_phase_base        |     2.88915  | 2.63915  |  3.2072   |      2.57669  |            0.0505051  |               3.11219     |          2.1213     |           4.17345    |                1.33386    |
| dynamic_only    |            58 | signed_physics_prior       |     0.630019 | 0.630019 |  1.63927  |      6.1418   |            0.0784314  |              -0.519471    |         -1.48972    |           0.022527   |                0          |
| dynamic_only    |            58 | hybrid_residual_ensemble   |     0.858621 | 0.648621 |  2.05574  |      6.12795  |            0.0784314  |              -0.364648    |         -1.33801    |           0.476074   |                0.228602   |
| dynamic_only    |            58 | gradient_boosted_trees_hgb |     1.11668  | 0.755103 |  1.57531  |      6.14848  |            0.117647   |              -0.452239    |         -1.57198    |           0.293218   |                0.486657   |
| dynamic_only    |            58 | mlp_waveform               |     1.22409  | 1.19406  |  1.65876  |      6.42168  |            0.0588235  |              -0.320813    |         -1.36435    |           0.336312   |                0.594068   |
| dynamic_only    |            58 | template_phase_base        |     1.27148  | 1.27148  |  1.42855  |      6.44666  |            0.0588235  |              -0.406262    |         -1.47814    |           0.25506    |                0.641458   |
| dynamic_only    |            58 | cnn_1d_waveform            |     1.30517  | 1.2999   |  1.44222  |      6.45316  |            0.0588235  |              -0.405551    |         -1.47385    |           0.257128   |                0.675153   |
| dynamic_only    |            58 | ridge_ml                   |     1.70863  | 1.23471  |  4.28981  |      6.02109  |            0.176471   |              -0.279989    |         -1.70284    |           1.32986    |                1.07861    |
| dynamic_only    |            58 | s03a_amp_only_ridge        |     1.86678  | 0.929352 |  2.45822  |      5.68962  |            0.0784314  |              -0.0646208   |         -1.22784    |           0.702656   |                1.23677    |
| dynamic_only    |            59 | gradient_boosted_trees_hgb |     2.49154  | 1.95023  |  3.05058  |      5.21646  |            0.13382    |              -0.240666    |         -1.11049    |           0.523208   |               -0.258458   |
| dynamic_only    |            59 | hybrid_residual_ensemble   |     2.62177  | 1.55726  |  3.45323  |      6.50313  |            0.177616   |              -0.364663    |         -1.3138     |           0.659431   |               -0.128233   |
| dynamic_only    |            59 | signed_physics_prior       |     2.75     | 1.30811  |  4.07864  |      7.88121  |            0.209246   |              -1.11906     |         -2.31266    |           0.205492   |                0          |
| dynamic_only    |            59 | s03a_amp_only_ridge        |     3.0486   | 2.62818  |  4.03145  |      6.46776  |            0.184915   |              -0.0042842   |         -0.92389    |           1.10693    |                0.298597   |
| dynamic_only    |            59 | mlp_waveform               |     3.30618  | 2.20633  |  4.30387  |      7.90689  |            0.22871    |              -0.829075    |         -1.95291    |           0.418047   |                0.556176   |
| dynamic_only    |            59 | template_phase_base        |     3.39146  | 2.24474  |  4.39246  |      7.92002  |            0.231144   |              -0.83082     |         -1.95277    |           0.412526   |                0.641458   |
| dynamic_only    |            59 | cnn_1d_waveform            |     3.42862  | 2.25048  |  4.42942  |      7.92398  |            0.231144   |              -0.823715    |         -1.94591    |           0.418596   |                0.67862    |
| dynamic_only    |            59 | ridge_ml                   |     3.49712  | 2.7459   |  4.33307  |      6.29094  |            0.206813   |               0.434804    |         -0.61002    |           1.53978    |                0.747122   |
| dynamic_only    |            60 | signed_physics_prior       |     1.67367  | 1.30535  |  2.55591  |      6.443    |            0.165533   |              -0.0239139   |         -1.05517    |           0.960019   |                0          |
| dynamic_only    |            60 | hybrid_residual_ensemble   |     1.96437  | 1.54052  |  2.74238  |      5.58332  |            0.154195   |               0.267444    |         -0.595256   |           1.04067    |                0.290696   |
| dynamic_only    |            60 | gradient_boosted_trees_hgb |     2.1507   | 1.8091   |  2.98516  |      4.93702  |            0.160998   |               0.319317    |         -0.407072   |           1.01096    |                0.477032   |
| dynamic_only    |            60 | mlp_waveform               |     2.34747  | 1.60542  |  3.03281  |      6.64688  |            0.185941   |               0.15763     |         -0.859534   |           1.06524    |                0.673797   |
| dynamic_only    |            60 | template_phase_base        |     2.42081  | 1.67081  |  3.11913  |      6.66321  |            0.188209   |               0.144278    |         -0.866896   |           1.05225    |                0.747143   |
| dynamic_only    |            60 | cnn_1d_waveform            |     2.43528  | 1.68537  |  3.15476  |      6.67082  |            0.185941   |               0.149401    |         -0.860721   |           1.05746    |                0.761609   |
| dynamic_only    |            60 | ridge_ml                   |     2.71192  | 2.37406  |  3.19016  |      4.95748  |            0.160998   |               0.443427    |         -0.257234   |           1.18157    |                1.03825    |
| dynamic_only    |            60 | s03a_amp_only_ridge        |     2.79687  | 2.52965  |  3.47213  |      5.39411  |            0.172336   |               0.675086    |         -0.119848   |           1.39055    |                1.1232     |
| dynamic_only    |            61 | template_phase_base        |     2        | 1.25492  |  3        |      8.45503  |            0.187793   |              -0.462501    |         -1.71347    |           1.11806    |               -0.506939   |
| dynamic_only    |            61 | cnn_1d_waveform            |     2.01765  | 1.29435  |  2.99982  |      8.45771  |            0.183099   |              -0.45918     |         -1.71266    |           1.12305    |               -0.48929    |
| dynamic_only    |            61 | mlp_waveform               |     2.02466  | 1.23439  |  2.99395  |      8.45627  |            0.183099   |              -0.449247    |         -1.69582    |           1.13146    |               -0.482279   |
| dynamic_only    |            61 | hybrid_residual_ensemble   |     2.14629  | 1.63471  |  3.06915  |      7.06025  |            0.176056   |              -0.0712635   |         -0.981375   |           1.15425    |               -0.360644   |
| dynamic_only    |            61 | signed_physics_prior       |     2.50694  | 1.3375   |  3.50017  |      8.50763  |            0.213615   |              -0.675909    |         -1.98292    |           0.904966   |                0          |
| dynamic_only    |            61 | gradient_boosted_trees_hgb |     2.58173  | 2.10925  |  3.64936  |      5.50903  |            0.190141   |               0.276476    |         -0.330349   |           0.970374   |                0.0747891  |
| dynamic_only    |            61 | s03a_amp_only_ridge        |     3.31488  | 2.69492  |  3.98227  |      7.32711  |            0.206573   |               0.128097    |         -0.860534   |           1.41505    |                0.807937   |
| dynamic_only    |            61 | ridge_ml                   |     3.33639  | 2.90971  |  4.07521  |      6.7154   |            0.223005   |               0.346897    |         -0.577025   |           1.47962    |                0.829455   |
| dynamic_only    |            62 | gradient_boosted_trees_hgb |     1.91997  | 1.48644  |  2.55343  |      5.08458  |            0.121891   |              -0.0323904   |         -0.613771   |           0.617099   |               -0.436397   |
| dynamic_only    |            62 | signed_physics_prior       |     2.35637  | 1.25     |  3.29473  |      7.17996  |            0.19403    |              -0.550518    |         -1.38764    |           0.466813   |                0          |
| dynamic_only    |            62 | hybrid_residual_ensemble   |     2.38943  | 1.64747  |  3.05214  |      6.11695  |            0.174129   |              -0.02625     |         -0.683662   |           0.85469    |                0.0330664  |
| dynamic_only    |            62 | mlp_waveform               |     2.81682  | 1.56548  |  3.79182  |      7.22593  |            0.216418   |              -0.276194    |         -1.1054     |           0.769769   |                0.460456   |
| dynamic_only    |            62 | template_phase_base        |     2.90932  | 1.66328  |  3.88467  |      7.23943  |            0.218905   |              -0.2679      |         -1.0951     |           0.769285   |                0.55295    |
| dynamic_only    |            62 | cnn_1d_waveform            |     2.9439   | 1.70213  |  3.90009  |      7.24369  |            0.216418   |              -0.254568    |         -1.07703    |           0.775911   |                0.587529   |
| dynamic_only    |            62 | s03a_amp_only_ridge        |     3.12244  | 2.36157  |  3.79563  |      6.17037  |            0.18408    |               0.390353    |         -0.41217    |           1.22102    |                0.766069   |
| dynamic_only    |            62 | ridge_ml                   |     3.22572  | 2.67622  |  4.01944  |      6.16951  |            0.20398    |               0.458152    |         -0.448973   |           1.50089    |                0.869352   |
| dynamic_only    |            63 | gradient_boosted_trees_hgb |     2.85016  | 2.01592  |  4.17718  |      4.72535  |            0.220657   |               0.310377    |         -0.472508   |           1.65006    |               -0.0106653  |
| dynamic_only    |            63 | signed_physics_prior       |     2.86083  | 1.10295  |  4.61436  |      7.26461  |            0.253521   |              -0.569531    |         -2.39172    |           1.1597     |                0          |
| dynamic_only    |            63 | hybrid_residual_ensemble   |     2.8875   | 1.42844  |  4.41752  |      5.93955  |            0.230047   |               0.0453906   |         -1.13305    |           1.4409     |                0.0266695  |
| dynamic_only    |            63 | mlp_waveform               |     3.23338  | 1.99316  |  4.55207  |      7.32383  |            0.244131   |              -0.288095    |         -2.01602    |           1.29911    |                0.372554   |
| dynamic_only    |            63 | template_phase_base        |     3.35071  | 2.08901  |  4.64847  |      7.3422   |            0.248826   |              -0.2965      |         -2.01291    |           1.2982     |                0.489882   |
| dynamic_only    |            63 | cnn_1d_waveform            |     3.38571  | 2.12366  |  4.63144  |      7.3473   |            0.244131   |              -0.291464    |         -2.00561    |           1.30207    |                0.524885   |
| dynamic_only    |            63 | s03a_amp_only_ridge        |     3.53422  | 2.34091  |  4.93562  |      6.14514  |            0.244131   |               0.489212    |         -0.790943   |           1.798      |                0.673392   |
| dynamic_only    |            63 | ridge_ml                   |     4.08199  | 2.74564  |  4.91577  |      5.46229  |            0.267606   |               0.450745    |         -0.569439   |           1.73774    |                1.22116    |
| dynamic_only    |            65 | signed_physics_prior       |     0.755372 | 0.755372 |  3.50537  |      2.90797  |            0.0972222  |              -0.477507    |         -1.76203    |           0.486077   |                0          |
| dynamic_only    |            65 | hybrid_residual_ensemble   |     1.29534  | 0.798767 |  3.11506  |      2.71618  |            0.0972222  |               0.370914    |         -0.763368   |           1.34766    |                0.539968   |
| dynamic_only    |            65 | mlp_waveform               |     1.29852  | 1.27688  |  3.85615  |      3.07794  |            0.0833333  |              -0.304633    |         -1.56338    |           0.679129   |                0.543149   |
| dynamic_only    |            65 | template_phase_base        |     1.34755  | 1.34755  |  3.93243  |      3.12069  |            0.0833333  |              -0.353591    |         -1.6177     |           0.617543   |                0.592178   |
| dynamic_only    |            65 | cnn_1d_waveform            |     1.38276  | 1.38078  |  3.95299  |      3.13169  |            0.0833333  |              -0.348958    |         -1.60246    |           0.622074   |                0.627387   |
| dynamic_only    |            65 | s03a_amp_only_ridge        |     2.07701  | 1.31735  |  3.27627  |      2.91415  |            0.0833333  |               1.0408      |          0.00264861 |           2.11003    |                1.32164    |
| dynamic_only    |            65 | gradient_boosted_trees_hgb |     2.23265  | 1.50767  |  3.55928  |      2.85545  |            0.0833333  |               0.873689    |         -0.434508   |           2.29318    |                1.47728    |
| dynamic_only    |            65 | ridge_ml                   |     2.66996  | 1.35995  |  3.72562  |      3.16653  |            0.125      |               1.26356     |         -0.427192   |           2.67869    |                1.91459    |
| matched_control |            58 | gradient_boosted_trees_hgb |     0.502627 | 0.502627 |  0.502627 |      0.632329 |            0          |             nan           |        nan          |         nan          |               -0.438129   |
| matched_control |            58 | hybrid_residual_ensemble   |     0.738605 | 0.738605 |  0.738605 |      0.93506  |            0          |             nan           |        nan          |         nan          |               -0.202152   |
| matched_control |            58 | ridge_ml                   |     0.920975 | 0.920975 |  0.920975 |      1.27663  |            0          |             nan           |        nan          |         nan          |               -0.0197818  |
| matched_control |            58 | signed_physics_prior       |     0.940756 | 0.940756 |  0.940756 |      1.13405  |            0          |             nan           |        nan          |         nan          |                0          |
| matched_control |            58 | s03a_amp_only_ridge        |     0.997891 | 0.997891 |  0.997891 |      1.37545  |            0          |             nan           |        nan          |         nan          |                0.0571351  |
| matched_control |            58 | mlp_waveform               |     1.97639  | 1.97639  |  1.97639  |      2.65721  |            0.333333   |             nan           |        nan          |         nan          |                1.03563    |
| matched_control |            58 | template_phase_base        |     2.00012  | 2.00012  |  2.00012  |      2.69193  |            0.333333   |             nan           |        nan          |         nan          |                1.05936    |
| matched_control |            58 | cnn_1d_waveform            |     2.01382  | 2.01382  |  2.01382  |      2.72002  |            0.333333   |             nan           |        nan          |         nan          |                1.07306    |
| matched_control |            59 | hybrid_residual_ensemble   |     0.778494 | 0.667812 |  1.29892  |      5.29806  |            0.030303   |              -0.201884    |         -1.30893    |           1.12187    |               -0.401302   |
| matched_control |            59 | s03a_amp_only_ridge        |     1.05049  | 0.879517 |  1.83053  |      5.32934  |            0.0454545  |               0.421131    |         -0.98215    |           2.10968    |               -0.129303   |
| matched_control |            59 | signed_physics_prior       |     1.1798   | 1.01387  |  1.69576  |      5.40088  |            0.0606061  |              -0.13551     |         -1.60088    |           1.45347    |                0          |
| matched_control |            59 | ridge_ml                   |     1.28666  | 0.970262 |  1.57002  |      5.46971  |            0.0454545  |              -0.910235    |         -2.53402    |           0.881347   |                0.106863   |
| matched_control |            59 | gradient_boosted_trees_hgb |     1.48971  | 1.16051  |  1.93805  |      5.33258  |            0.030303   |               0.509776    |         -0.876604   |           1.73901    |                0.309915   |
| matched_control |            59 | mlp_waveform               |     2.03213  | 1.99821  |  2.24105  |      5.53625  |            0.0454545  |              -0.257547    |         -1.29654    |           1.07544    |                0.85233    |
| matched_control |            59 | template_phase_base        |     2.04602  | 2.04602  |  2.29602  |      5.52684  |            0.0454545  |              -0.188635    |         -1.23872    |           1.17453    |                0.866222   |
| matched_control |            59 | cnn_1d_waveform            |     2.06479  | 2.06468  |  2.31526  |      5.52426  |            0.0454545  |              -0.149529    |         -1.20266    |           1.22096    |                0.884991   |
| matched_control |            60 | s03a_amp_only_ridge        |     1.21556  | 0.934809 |  2.16962  |      1.86439  |            0.031746   |              -0.995502    |         -2.11105    |           0.331872   |               -0.460937   |
| matched_control |            60 | ridge_ml                   |     1.2872   | 0.948756 |  1.97042  |      1.81328  |            0.031746   |              -0.0657771   |         -1.44774    |           1.40534    |               -0.389297   |
| matched_control |            60 | hybrid_residual_ensemble   |     1.36047  | 0.648268 |  2.1025   |      1.77507  |            0.015873   |               0.228662    |         -0.764254   |           1.2601     |               -0.316028   |
| matched_control |            60 | signed_physics_prior       |     1.6765   | 1.20514  |  2.41956  |      1.95168  |            0.031746   |              -1.44304     |         -2.44486    |          -0.390055   |                0          |
| matched_control |            60 | gradient_boosted_trees_hgb |     1.82128  | 1.53119  |  2.0651   |      1.71558  |            0          |               0.549798    |         -1.20571    |           2.01329    |                0.144783   |
| matched_control |            60 | mlp_waveform               |     2.46248  | 1.86084  |  3.60824  |      2.80986  |            0.0952381  |               0.179517    |         -0.833239   |           1.30902    |                0.785988   |
| matched_control |            60 | template_phase_base        |     2.48552  | 1.87283  |  3.62283  |      2.8341   |            0.0952381  |               0.231928    |         -0.758074   |           1.36017    |                0.809021   |
| matched_control |            60 | cnn_1d_waveform            |     2.52455  | 1.89317  |  3.6417   |      2.8562   |            0.111111   |               0.251111    |         -0.751891   |           1.39144    |                0.848053   |
| matched_control |            61 | hybrid_residual_ensemble   |     0.96807  | 0.771961 |  1.79946  |      3.94981  |            0.0350877  |               0.629298    |         -2.43992    |           2.70848    |               -0.431281   |
| matched_control |            61 | s03a_amp_only_ridge        |     1.33582  | 1.11803  |  1.70993  |      4.17625  |            0.0350877  |              -0.323671    |         -3.27921    |           1.75076    |               -0.0635316  |
| matched_control |            61 | ridge_ml                   |     1.38921  | 1.10762  |  1.88491  |      4.25332  |            0.0350877  |              -0.000300308 |         -2.76005    |           2.37364    |               -0.0101444  |
| matched_control |            61 | signed_physics_prior       |     1.39935  | 1.2965   |  1.78126  |      4.35547  |            0.0350877  |              -1.43356     |         -4.51215    |           0.623882   |                0          |
| matched_control |            61 | gradient_boosted_trees_hgb |     1.95347  | 1.44869  |  2.36065  |      4.34339  |            0.0526316  |              -0.684579    |         -3.90679    |           1.98032    |                0.554124   |
| matched_control |            61 | mlp_waveform               |     2.7623   | 2.74192  |  2.78119  |      4.36202  |            0.0526316  |               1.54439     |         -1.51223    |           3.72552    |                1.36295    |
| matched_control |            61 | template_phase_base        |     2.79153  | 2.79153  |  2.79153  |      4.3533   |            0.0526316  |               1.62498     |         -1.40067    |           3.77298    |                1.39218    |
| matched_control |            61 | cnn_1d_waveform            |     2.81112  | 2.81035  |  2.81288  |      4.36164  |            0.0526316  |               1.65769     |         -1.36126    |           3.8046     |                1.41177    |
| matched_control |            62 | hybrid_residual_ensemble   |     0.652424 | 0.461308 |  1.67173  |      6.07635  |            0.0416667  |               5.38579     |         -0.516704   |          12.4143     |               -0.472383   |
| matched_control |            62 | gradient_boosted_trees_hgb |     1.05104  | 0.735793 |  1.39837  |      6.14586  |            0.0416667  |               5.08312     |         -1.22439    |          12.9357     |               -0.0737703  |
| matched_control |            62 | s03a_amp_only_ridge        |     1.11296  | 1.01251  |  1.84991  |      6.1138   |            0.0416667  |               3.49571     |         -2.8645     |          10.4145     |               -0.011846   |
| matched_control |            62 | signed_physics_prior       |     1.12481  | 1.05487  |  1.70997  |      6.10703  |            0.0416667  |               3.68213     |         -2.64055    |          10.5491     |                0          |
| matched_control |            62 | ridge_ml                   |     1.33478  | 1.20156  |  1.95171  |      6.43995  |            0.0416667  |               4.81125     |         -2.11662    |          12.6173     |                0.209976   |
| matched_control |            62 | mlp_waveform               |     1.77354  | 1.76257  |  3.2682   |      6.14473  |            0.0625     |               5.75996     |          0.00299725 |          12.2931     |                0.648733   |
| matched_control |            62 | template_phase_base        |     1.79558  | 1.79558  |  3.29558  |      6.16096  |            0.0625     |               5.85448     |          0.0796288  |          12.4109     |                0.670773   |
| matched_control |            62 | cnn_1d_waveform            |     1.83654  | 1.835    |  3.33559  |      6.16742  |            0.0625     |               5.88885     |          0.115736   |          12.4519     |                0.711729   |
| matched_control |            63 | s03a_amp_only_ridge        |     1.11826  | 0.734807 |  2.17039  |      1.44429  |            0          |             nan           |        nan          |         nan          |               -0.488391   |
| matched_control |            63 | gradient_boosted_trees_hgb |     1.18182  | 0.891932 |  2.21751  |      1.46734  |            0          |             nan           |        nan          |         nan          |               -0.42483    |
| matched_control |            63 | ridge_ml                   |     1.31937  | 1.06952  |  1.56382  |      1.25559  |            0          |             nan           |        nan          |         nan          |               -0.287282   |
| matched_control |            63 | signed_physics_prior       |     1.60665  | 0.882216 |  1.78591  |      1.32265  |            0          |             nan           |        nan          |         nan          |                0          |
| matched_control |            63 | hybrid_residual_ensemble   |     1.9786   | 0.953428 |  3.01821  |      1.88497  |            0          |             nan           |        nan          |         nan          |                0.371952   |
| matched_control |            63 | mlp_waveform               |     3.79685  | 3.02905  |  4.68513  |      3.56208  |            0.333333   |             nan           |        nan          |         nan          |                2.1902     |
| matched_control |            63 | template_phase_base        |     3.83103  | 3.03175  |  4.72175  |      3.58522  |            0.333333   |             nan           |        nan          |         nan          |                2.22438    |
| matched_control |            63 | cnn_1d_waveform            |     3.86635  | 3.07124  |  4.76301  |      3.61493  |            0.333333   |             nan           |        nan          |         nan          |                2.2597     |
| matched_control |            65 | signed_physics_prior       |     0.726864 | 0.605524 |  0.984015 |      0.899251 |            0          |             nan           |        nan          |         nan          |                0          |
| matched_control |            65 | ridge_ml                   |     0.994688 | 0.191047 |  1.0708   |      0.942929 |            0          |             nan           |        nan          |         nan          |                0.267824   |
| matched_control |            65 | s03a_amp_only_ridge        |     0.998629 | 0.333228 |  1.17393  |      0.875901 |            0          |             nan           |        nan          |         nan          |                0.271765   |
| matched_control |            65 | hybrid_residual_ensemble   |     1.19641  | 0.678368 |  1.71352  |      1.1136   |            0          |             nan           |        nan          |         nan          |                0.469547   |
| matched_control |            65 | gradient_boosted_trees_hgb |     1.38145  | 0.662693 |  2.38746  |      1.56177  |            0          |             nan           |        nan          |         nan          |                0.654587   |
| matched_control |            65 | mlp_waveform               |     3.31037  | 2.77541  |  3.54454  |      2.9074   |            0.333333   |             nan           |        nan          |         nan          |                2.58351    |
| matched_control |            65 | template_phase_base        |     3.33071  | 2.81689  |  3.56689  |      2.93191  |            0.333333   |             nan           |        nan          |         nan          |                2.60385    |
| matched_control |            65 | cnn_1d_waveform            |     3.35482  | 2.85636  |  3.60702  |      2.95922  |            0.333333   |             nan           |        nan          |         nan          |                2.62795    |

Pooled run-bootstrap results:

| stratum         | method                     |   sigma68_ns |   ci_low |   ci_high |   full_rms_ns |   tail_frac_abs_gt5ns |   bias_vs_logamp_slope_ns |   bias_slope_ci_low |   bias_slope_ci_high |   delta_vs_traditional_ns |
|:----------------|:---------------------------|-------------:|---------:|----------:|--------------:|----------------------:|--------------------------:|--------------------:|---------------------:|--------------------------:|
| dynamic_only    | signed_physics_prior       |      2.09283 | 1.56787  |   2.5336  |       7.37117 |             0.193452  |                -0.614635  |          -0.958777  |           -0.260597  |                 0         |
| dynamic_only    | hybrid_residual_ensemble   |      2.23851 | 1.87938  |   2.55171 |       6.20246 |             0.172123  |                -0.0542627 |          -0.263296  |            0.163765  |                 0.145675  |
| dynamic_only    | gradient_boosted_trees_hgb |      2.36873 | 2.05158  |   2.61255 |       5.11609 |             0.15873   |                 0.0892413 |          -0.12197   |            0.323199  |                 0.275903  |
| dynamic_only    | mlp_waveform               |      2.54311 | 2.03113  |   3.05661 |       7.42133 |             0.199405  |                -0.360941  |          -0.67105   |           -0.0356191 |                 0.450275  |
| dynamic_only    | template_phase_base        |      2.60091 | 2.10472  |   3.14146 |       7.43286 |             0.199901  |                -0.370319  |          -0.682939  |           -0.0549381 |                 0.50808   |
| dynamic_only    | cnn_1d_waveform            |      2.63764 | 2.10504  |   3.17837 |       7.43756 |             0.200397  |                -0.363681  |          -0.679813  |           -0.0394821 |                 0.544813  |
| dynamic_only    | s03a_amp_only_ridge        |      2.95074 | 2.71143  |   3.12994 |       6.24562 |             0.188988  |                 0.309066  |           0.0823062 |            0.558816  |                 0.857914  |
| dynamic_only    | ridge_ml                   |      3.16309 | 2.86888  |   3.52337 |       5.92328 |             0.203373  |                 0.41833   |           0.339512  |            0.50995   |                 1.07026   |
| matched_control | hybrid_residual_ensemble   |      1.20601 | 0.970447 |   1.42172 |       4.29611 |             0.0229885 |                 1.25701   |           0.138122  |            3.29088   |                -0.356151  |
| matched_control | s03a_amp_only_ridge        |      1.24173 | 1.19037  |   1.52279 |       4.48694 |             0.0383142 |                 0.403848  |          -0.864489  |            1.94218   |                -0.320436  |
| matched_control | ridge_ml                   |      1.37785 | 1.22564  |   1.54764 |       4.59929 |             0.0383142 |                 0.720822  |          -0.539089  |            2.75941   |                -0.184311  |
| matched_control | signed_physics_prior       |      1.56216 | 1.1865   |   1.6901  |       4.56008 |             0.0421456 |                -0.0926168 |          -1.51684   |            1.73333   |                 0         |
| matched_control | gradient_boosted_trees_hgb |      1.69803 | 1.38134  |   1.90037 |       4.52129 |             0.0229885 |                 1.1379    |          -0.185047  |            3.11054   |                 0.135869  |
| matched_control | mlp_waveform               |      2.9635  | 2.43302  |   3.70087 |       4.70607 |             0.0689655 |                 1.53748   |           0.272433  |            3.76549   |                 1.40133   |
| matched_control | template_phase_base        |      3.01086 | 2.38592  |   3.7461  |       4.71068 |             0.0689655 |                 1.60287   |           0.291548  |            3.80622   |                 1.44869   |
| matched_control | cnn_1d_waveform            |      3.02962 | 2.448    |   3.79649 |       4.71841 |             0.0766284 |                 1.63183   |           0.367662  |            3.98653   |                 1.46745   |
| median_selected | hybrid_residual_ensemble   |      1.17544 | 1.13513  |   1.22763 |       2.36352 |             0.0136126 |                 1.35642   |           0.969439  |            1.61497   |                -0.428917  |
| median_selected | gradient_boosted_trees_hgb |      1.45088 | 1.32319  |   1.74937 |       2.40224 |             0.0158813 |                -1.09425   |          -1.37939   |           -0.809727  |                -0.153478  |
| median_selected | s03a_amp_only_ridge        |      1.55619 | 1.3715   |   1.92959 |       2.67112 |             0.0184119 |                -0.629304  |          -0.967168  |           -0.472145  |                -0.0481647 |
| median_selected | ridge_ml                   |      1.56448 | 1.38393  |   1.85259 |       2.60461 |             0.0177138 |                -0.606033  |          -1.00793   |           -0.382241  |                -0.0398738 |
| median_selected | signed_physics_prior       |      1.60436 | 1.38503  |   1.9535  |       2.68732 |             0.0205934 |                -0.418203  |          -0.9291    |           -0.20698   |                 0         |
| median_selected | mlp_waveform               |      2.49629 | 2.42083  |   2.67713 |       3.12303 |             0.0530541 |                 3.32058   |           2.85462   |            3.66871   |                 0.891936  |
| median_selected | cnn_1d_waveform            |      2.73224 | 2.7125   |   2.95215 |       3.30689 |             0.0747818 |                 3.80537   |           3.3798    |            4.14951   |                 1.12789   |
| median_selected | template_phase_base        |      2.74141 | 2.68081  |   2.99232 |       3.30837 |             0.0813264 |                 3.74095   |           3.25838   |            4.08958   |                 1.13706   |

Winners named in `result.json`:

| stratum         | method                   |   sigma68_ns |   ci_low |   ci_high |   beats_traditional_ns |
|:----------------|:-------------------------|-------------:|---------:|----------:|-----------------------:|
| dynamic_only    | signed_physics_prior     |      2.09283 | 1.56787  |   2.5336  |               0        |
| matched_control | hybrid_residual_ensemble |      1.20601 | 0.970447 |   1.42172 |               0.356151 |
| median_selected | hybrid_residual_ensemble |      1.17544 | 1.13513  |   1.22763 |               0.428917 |

## 5. Systematics and leakage checks

| stratum         | check                                       |   min_value |   max_value |
|:----------------|:--------------------------------------------|------------:|------------:|
| dynamic_only    | feature_audit_no_run_event_cross_stave_time |     1       |     1       |
| dynamic_only    | hgb_shuffled_target_sigma68_ns              |     1.70896 |     4.12062 |
| dynamic_only    | train_heldout_event_id_overlap              |     0       |     0       |
| matched_control | feature_audit_no_run_event_cross_stave_time |     1       |     1       |
| matched_control | hgb_shuffled_target_sigma68_ns              |     2.8343  |     3.61974 |
| matched_control | train_heldout_event_id_overlap              |     0       |     0       |
| median_selected | feature_audit_no_run_event_cross_stave_time |     1       |     1       |
| median_selected | hgb_shuffled_target_sigma68_ns              |     2.6736  |     3.03532 |
| median_selected | train_heldout_event_id_overlap              |     0       |     0       |

The dynamic-only support is a selector-induced population shift, not a random split of the median-selected support; its wider intervals and altered amplitude slope therefore measure both timing closure and changed physical support. The matched-control stratum partially isolates mixture effects, but it cannot guarantee perfect topology matching because only downstream waveform observables are available in this reduced table. Shuffled-target HGB sentinels are deliberately retained as a high-sensitivity leakage check for the strongest non-neural ML comparator.

## 6. Verdict

The global winner is `hybrid_residual_ensemble` in stratum `median_selected` with pooled sigma68 `1.175` ns. The ticket verdict is `selector_support_ml_winner_no_leakage_flag`.

## 7. Reproducibility

Generated by:

```bash
/home/billy/anaconda3/bin/python scripts/s03j_1781030650_597_5d382001_selector_timewalk_support.py --config configs/s03j_1781030650_597_5d382001_selector_timewalk_support.yaml
```

Artifacts include `reproduction_match_table.csv`, `selector_reproduction_match_table.csv`, `stratum_support_counts.csv`, `per_run_benchmark.csv`, `pooled_run_bootstrap.csv`, `pairwise_residuals.csv`, `model_choices.csv`, `model_diagnostics.csv`, `leakage_checks.csv`, figures, `input_sha256.csv`, `result.json`, and `manifest.json`.
