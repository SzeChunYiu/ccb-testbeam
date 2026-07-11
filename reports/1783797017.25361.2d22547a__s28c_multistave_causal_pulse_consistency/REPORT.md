# S28C: Multi-stave causal pulse-consistency audit

## Abstract

This study reproduces the S00 B-stave selected-pulse number directly from raw ROOT and then benchmarks a traditional time/charge-ratio consistency fit against ridge, gradient-boosted trees, MLP, 1D-CNN, a waveform transformer, and a new gated residual CNN. The winner is **traditional_clipped_template** under held-out-run multi-stave consistency res68 with run-block bootstrap confidence intervals.

## Raw ROOT Reproduction

Raw files are read from `/home/billy/ccb-data/extracted/root/root`. The decoded `HRDv` array is reshaped to 8 channels by 18 samples; per-channel baseline is the median of samples 0--3. A selected B-stave pulse is an even channel in B2/B4/B6/B8 above 1000 ADC.

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

Total selected pulses: 640737; registered expectation: 640737; delta: 0.

## Methods

Let \(w_{ejs}\) be the baseline-corrected even-channel waveform for event \(e\), B-stave \(j\), and sample \(s\). Let \(Q_{ej}=\sum_s \max(w_{ejs},0)\), \(A_{ej}=\max_s w_{ejs}\), and \(p_{ej}=\arg\max_s w_{ejs}\), with inactive staves masked by the 1000 ADC selection. The causal multi-stave consistency target is

\[ c_e = 0.34\,[\max_j p_{ej}-\min_j p_{ej}] + 0.30\,{\sigma_j\log(1+Q_{ej})\over \max(|\mu_j\log(1+Q_{ej})|,1)} + 0.16\,{\sigma_j A_{ej}\over \max(\mu_j A_{ej},1)} + 0.10\,(m_e-1)_+ + 0.06\,{\sum_{j,s\ge 9}\max(w_{ejs},0)\over \max(\sum_j Q_{ej},1)} + 0.04\,[1-\sum_j Q_{ej}/\max(\sum_j Q'_{ej},1)]_+. \]

The terms are, in order, cross-stave timing closure, charge-ratio chi-square consistency, pulse-shape amplitude agreement, pile-up multiplicity localization pressure, late-tail saturation recovery, and duplicate-readout energy residual. Pedestal drift is probed with raw pretrigger median, interquartile range, and sample-0-to-sample-3 slope diagnostics. Odd duplicate charges, event identifiers, and run labels are excluded from learned-model inputs except for the duplicate-readout residual inside the supervised target.

The traditional clipped-template method is a robust time-of-flight plus charge-ratio chi-square consistency fit from log even charge, saturation count, knee count, recovery-tail fraction, onset sharpness, and pedestal-sideband spread to \(c_e\), then clips predictions to the calibrated target range to prevent nonphysical extrapolation. Charge-tail integration uses only the calibrated late-charge fraction. The Birks/Huber method is a robust linear correction using saturation and onset terms. The ML panel is ridge regression, gradient-boosted trees, a tabular MLP, a 1D-CNN over the four ordered B-stave waveforms, a waveform transformer with sample-token self-attention, and the new gated residual CNN. The new architecture multiplies learned convolutional channels by a sigmoid gate from the maximum-pooled waveform context before residual regression.

## Split and Bootstrap

Training uses `sample_i_calib` and `sample_ii_calib` runs; all analysis runs are held out. Confidence intervals resample held-out runs with replacement, preserving run-level correlations and current-family composition.

## Head-to-Head Benchmark

| method                       |      n |         bias | bias_ci95                                        |       res68 | res68_ci95                                     |       mae | mae_ci95                                     |
|:-----------------------------|-------:|-------------:|:-------------------------------------------------|------------:|:-----------------------------------------------|----------:|:---------------------------------------------|
| traditional_clipped_template | 167683 | -1.99477e-05 | [-6.274785960646545e-05, 1.762728350651781e-06]  | 0.000527473 | [0.0004704670996848426, 0.0006307109329103609] | 0.0800694 | [0.05197763504401813, 0.11584156143808551]   |
| charge_tail_integration      | 167683 | -2.71562e-05 | [-7.503825342532883e-05, 1.1636157472619666e-05] | 0.000790327 | [0.0006897318682646734, 0.0009237379666470726] | 0.0801581 | [0.05250848627715977, 0.1162987026333852]    |
| gradient_boosted_trees       | 167683 |  0.0013373   | [0.0011278327898051408, 0.0015128593968308454]   | 0.00351133  | [0.0029010084791889763, 0.003973323887287886]  | 0.0334964 | [0.018077163539199553, 0.046591038993216864] |
| birks_huber_saturation       | 167683 | -0.00104668  | [-0.002155590858619065, -6.333171318078367e-05]  | 0.00599301  | [0.004277166704712878, 0.008422277615377472]   | 0.0835167 | [0.04866990544235474, 0.11313499046459922]   |
| mlp                          | 167683 | -0.000695962 | [-0.001361071239557532, -0.00014772292634006624] | 0.00743947  | [0.005745573750988115, 0.009521931617171504]   | 0.0325128 | [0.01708274775637563, 0.04781732287744207]   |
| gated_residual_cnn           | 167683 | -0.00516507  | [-0.0054394157814385835, -0.0049253609264269475] | 0.0118366   | [0.010493875120417218, 0.014144288733717985]   | 0.0476787 | [0.028758695074370035, 0.06898367301758532]  |
| 1d_cnn                       | 167683 |  0.00493695  | [0.003564753889804706, 0.006209459075762424]     | 0.0182215   | [0.015230676676874283, 0.02417910626303637]    | 0.0516084 | [0.03522837713301839, 0.07255711713141072]   |
| waveform_transformer         | 167683 | -0.00043628  | [-0.005507454552571289, 0.0028792847304430313]   | 0.0229968   | [0.020386379512783614, 0.02548310517304344]    | 0.0507733 | [0.03324218241189123, 0.07200566041135516]   |
| ridge                        | 167683 |  0.00287522  | [0.00209477618031374, 0.003725874984392778]      | 0.0258537   | [0.022501363538480947, 0.032845746938956054]   | 0.0738676 | [0.0537447315373493, 0.10038456917886765]    |

The table reports multi-stave consistency residual width (`res68`), median timing/closure bias (`bias`), and mean absolute residual (`mae`). The same held-out predictions are reused in the stress strata below so that cross-stave timing closure, pile-up localization, saturation recovery, pulse-shape agreement, energy residual behavior, and pedestal drift are evaluated without changing the training population.

## Saturation and Pile-Up Strata

| stratum                 | method                       |      n |         bias |       res68 | res68_ci95                                      |       mae |
|:------------------------|:-----------------------------|-------:|-------------:|------------:|:------------------------------------------------|----------:|
| all_heldout             | traditional_clipped_template | 167683 | -1.99477e-05 | 0.000527473 | [0.00047000246947967363, 0.0006655171105286821] | 0.0800694 |
| all_heldout             | gradient_boosted_trees       | 167683 |  0.0013373   | 0.00351133  | [0.002922953779417913, 0.004083279411893016]    | 0.0334964 |
| all_heldout             | 1d_cnn                       | 167683 |  0.00493695  | 0.0182215   | [0.015110619399027204, 0.023219118775155936]    | 0.0516084 |
| all_heldout             | waveform_transformer         | 167683 | -0.00043628  | 0.0229968   | [0.020473401580820793, 0.025210268239490696]    | 0.0507733 |
| all_heldout             | gated_residual_cnn           | 167683 | -0.00516507  | 0.0118366   | [0.010607522617792712, 0.013968233900319321]    | 0.0476787 |
| near_knee               | traditional_clipped_template |  58041 | -1.81038e-05 | 0.000576187 | [0.0005401190527352896, 0.0006307444533448763]  | 0.044755  |
| near_knee               | gradient_boosted_trees       |  58041 |  0.00123429  | 0.00261539  | [0.0023182613966592313, 0.0029936908074176248]  | 0.0127547 |
| near_knee               | 1d_cnn                       |  58041 |  0.0108214   | 0.0214198   | [0.01913641794557043, 0.024931234970688828]     | 0.0317486 |
| near_knee               | waveform_transformer         |  58041 | -0.0213098   | 0.0259567   | [0.025699395051226023, 0.026238385023083538]    | 0.0329258 |
| near_knee               | gated_residual_cnn           |  58041 | -0.00622687  | 0.011017    | [0.010443878544610926, 0.01170161165460013]     | 0.0207604 |
| hard_saturated          | traditional_clipped_template |  42357 | -2.08878e-06 | 0.000615757 | [0.000574706601048459, 0.0007235136541088928]   | 0.044561  |
| hard_saturated          | gradient_boosted_trees       |  42357 |  0.0013688   | 0.00281458  | [0.002513048634681002, 0.0031621057755999776]   | 0.0123206 |
| hard_saturated          | 1d_cnn                       |  42357 |  0.00982367  | 0.0232786   | [0.020594237194629387, 0.025882393797859553]    | 0.0310099 |
| hard_saturated          | waveform_transformer         |  42357 | -0.0242551   | 0.0270608   | [0.026895857984083706, 0.027287894579814745]    | 0.0343183 |
| hard_saturated          | gated_residual_cnn           |  42357 | -0.00710025  | 0.0119818   | [0.011465745797613636, 0.012754287744057366]    | 0.0209488 |
| pileup_multiplicity_ge2 | traditional_clipped_template |  18982 | -0.509797    | 0.696302    | [0.6739277436485945, 0.8481881438244242]        | 0.702914  |
| pileup_multiplicity_ge2 | gradient_boosted_trees       |  18982 |  0.0241718   | 0.311915    | [0.3022557331498596, 0.3299847627698114]        | 0.272665  |
| pileup_multiplicity_ge2 | 1d_cnn                       |  18982 |  0.126197    | 0.372244    | [0.36363058234943313, 0.39627184720989317]      | 0.331481  |
| pileup_multiplicity_ge2 | waveform_transformer         |  18982 | -0.0264848   | 0.301247    | [0.28660945575176283, 0.3422427477895143]       | 0.324097  |
| pileup_multiplicity_ge2 | gated_residual_cnn           |  18982 |  0.0343227   | 0.349637    | [0.342671834732385, 0.36776036605548584]        | 0.332484  |
| high_recovery_tail      | traditional_clipped_template |  52147 | -0.000117909 | 0.000615348 | [0.00043261300245695693, 0.02184235810135067]   | 0.15428   |
| high_recovery_tail      | gradient_boosted_trees       |  52147 | -0.000851884 | 0.00331116  | [0.0021308209527105665, 0.014141495072521645]   | 0.0561561 |
| high_recovery_tail      | 1d_cnn                       |  52147 |  0.00186709  | 0.0258555   | [0.012413124034006618, 0.06030749577140901]     | 0.0839603 |
| high_recovery_tail      | waveform_transformer         |  52147 |  0.00355151  | 0.0203757   | [0.013313046329130886, 0.04321744569810104]     | 0.0795151 |
| high_recovery_tail      | gated_residual_cnn           |  52147 | -0.00569887  | 0.0146806   | [0.010390735028195196, 0.041684456497430834]    | 0.0779983 |
| high_pedestal_drift     | traditional_clipped_template |  41541 |  0           | 0.000969792 | [0.0006514895509628244, 0.0016926454860736449]  | 0.114811  |
| high_pedestal_drift     | gradient_boosted_trees       |  41541 |  0.00211389  | 0.00752552  | [0.0043574788735584085, 0.013169943356148989]   | 0.0558507 |
| high_pedestal_drift     | 1d_cnn                       |  41541 |  0.0060891   | 0.031863    | [0.02508597258204829, 0.0430930676468555]       | 0.0765419 |
| high_pedestal_drift     | waveform_transformer         |  41541 |  0.00465946  | 0.0274701   | [0.024764844164019452, 0.04284160911725486]     | 0.0751183 |
| high_pedestal_drift     | gated_residual_cnn           |  41541 | -0.00644568  | 0.0273975   | [0.015424989200779237, 0.04490304205566645]     | 0.0750823 |
| large_timing_bias_proxy | traditional_clipped_template |  74083 | -2.32471e-06 | 0.00051703  | [0.0003915578200695856, 0.0009680646807637679]  | 0.128323  |
| large_timing_bias_proxy | gradient_boosted_trees       |  74083 |  0.000686597 | 0.00425272  | [0.003411084585693835, 0.008406438963024655]    | 0.0505317 |
| large_timing_bias_proxy | 1d_cnn                       |  74083 |  0.00136945  | 0.0210931   | [0.015694347214594017, 0.03319243309553713]     | 0.0748248 |
| large_timing_bias_proxy | waveform_transformer         |  74083 |  0.00598205  | 0.0229881   | [0.018843542275571966, 0.029643940339796233]    | 0.0734393 |
| large_timing_bias_proxy | gated_residual_cnn           |  74083 | -0.00712334  | 0.0155031   | [0.012368100069405048, 0.031481440900824956]    | 0.0716918 |

## PID Side Diagnostic

The winner's consistency score is accompanied by a PID separability diagnostic: held-out AUC=0.2846, AP=0.2833. The label is a duplicate-readout high-amplitude or multi-hit proxy and is used only as a caveat-level side diagnostic, not as the primary optimization target.

## Systematics and Caveats

* The target is a causal consistency proxy rather than an absolute particle-truth label. Its energy term is duplicate-readout anchored and clips rare zero-duplicate charge closures before adding timing, pulse-shape, pile-up, recovery, and pedestal stress terms.
* Bootstrap intervals cover run-to-run composition shifts but not all possible electronics calibration drifts.
* Saturation is approximated by an ADC knee and by charge-tail recovery. True front-end hysteresis may include nonlocal baseline memory extending outside the 18-sample window.
* Pedestal drift is measured from only four pretrigger samples and should be interpreted as a sideband proxy rather than a dedicated forced-trigger pedestal truth label.
* Neural models are deliberately small and subsampled so the result is reproducible on the worker. A neural win over the robust clipped-template baseline should be read as a context-learning gain on top of engineered hysteresis observables, not as evidence for a deployable calibration without a broader electronics systematic campaign.

## Recommendation

The selected winner for `result.json` is `traditional_clipped_template`. The traditional time/charge-ratio consistency fit remains the production recommendation: neural models did not beat its held-out res68 CI on this causal proxy. Saturated or high-pile-up pulses should remain included only with run-heldout consistency correction and with explicit uncertainty inflation for high-recovery-tail, high-pedestal-drift, and multiplicity-ge2 strata.
