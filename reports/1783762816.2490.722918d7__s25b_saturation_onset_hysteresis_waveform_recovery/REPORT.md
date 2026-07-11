# S25b: saturation-onset hysteresis waveform recovery bakeoff

## Abstract

This study reproduces the S00 B-stave selected-pulse number directly from raw ROOT and then benchmarks a traditional saturation-aware waveform correction against ridge, gradient-boosted trees, MLP, 1D-CNN, and a new gated residual CNN. The winner is **mlp** under held-out-run res68 with run-block bootstrap confidence intervals.

## Raw ROOT Reproduction

Raw files are read from `data/root/root`. The decoded `HRDv` array is reshaped to 8 channels by 18 samples; per-channel baseline is the median of samples 0--3. A selected B-stave pulse is an even channel in B2/B4/B6/B8 above 1000 ADC.

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

Let \(w_{ejs}\) be the baseline-corrected even-channel waveform for event \(e\), stave \(j\), and sample \(s\), and let \(q'_e\) be the duplicate odd-readout positive charge. The target hysteresis score is

\[ h_e = \operatorname{clip}_{[-4,4]}\left(1 - \frac{\sum_j Q_{ej}}{\max(\sum_j Q'_{ej},1)}\right) + 0.18\,\frac{\sum_{j,s\ge 9}\max(w_{ejs},0)}{\max(\sum_j Q_{ej},1)} + 0.015\,(\bar{s}_{peak,e}-5). \]

The first term measures charge lost to clipping relative to the independent duplicate readout, the second term measures delayed recovery after saturation onset, and the third term captures peak-sample timing displacement. Inputs to learned models exclude odd charges, event identifiers, and run labels.

The traditional clipped-template method fits a run-held-out robust calibration from log even charge, saturation count, knee count, recovery-tail fraction, and onset sharpness to \(h_e\), then clips predictions to the calibrated target range to prevent extrapolated nonphysical charge recovery. Charge-tail integration uses the calibrated late-charge fraction. The Birks/Huber method is a robust linear correction using saturation and onset terms. The ML panel is ridge regression, gradient-boosted trees, a tabular MLP, a 1D-CNN over the four B-stave waveforms, and the new gated residual CNN. The new architecture multiplies learned convolutional channels by a sigmoid gate from the maximum pooled waveform context before residual regression.

## Split and Bootstrap

Training uses `sample_i_calib` and `sample_ii_calib` runs; all analysis runs are held out. Confidence intervals resample held-out runs with replacement, preserving run-level correlations and current-family composition.

## Head-to-Head Benchmark

| method                       |      n |        bias | bias_ci95                                       |     res68 | res68_ci95                                   |       mae | mae_ci95                                   |
|:-----------------------------|-------:|------------:|:------------------------------------------------|----------:|:---------------------------------------------|----------:|:-------------------------------------------|
| mlp                          | 167683 |  0.00680348 | [0.003941129997372629, 0.009108501434326165]    | 0.0232743 | [0.020997278735041605, 0.027212719138860697] | 0.0776993 | [0.06305568617366364, 0.0935096269902873]  |
| gradient_boosted_trees       | 167683 | -0.0123365  | [-0.013382697531265156, -0.011373290266254868]  | 0.0313697 | [0.029430484475913593, 0.03437786541387658]  | 0.087949  | [0.07126430138037423, 0.10548288750065586] |
| traditional_clipped_template | 167683 |  0.00186671 | [-0.002460259980460939, 0.007192061182467721]   | 0.0403935 | [0.0323276690959302, 0.0496450439461025]     | 0.197345  | [0.14628081310509547, 0.2517579665202935]  |
| charge_tail_integration      | 167683 |  0.00382681 | [-0.0055180851850210825, 0.012641397166535888]  | 0.0482599 | [0.04355560229268362, 0.053582388067677574]  | 0.205711  | [0.1541255282490798, 0.25526635116998736]  |
| birks_huber_saturation       | 167683 | -0.00835227 | [-0.014149162394341091, -0.0039765794816713305] | 0.050402  | [0.04308824944601026, 0.058156388811403996]  | 0.235151  | [0.17567817150905077, 0.3021244214861927]  |
| 1d_cnn                       | 167683 | -0.0128017  | [-0.022105235755443587, 0.0007488435506820333]  | 0.0710811 | [0.06481012371420859, 0.07860750805586576]   | 0.142224  | [0.11785226125946474, 0.16480850739400474] |
| gated_residual_cnn           | 167683 |  0.0114011  | [-0.008816091120243086, 0.0445697509497404]     | 0.125784  | [0.11159855403870346, 0.14231502955138686]   | 0.165504  | [0.13907497869858296, 0.1916677768099763]  |
| ridge                        | 167683 | -0.0435215  | [-0.07293827634109357, 3.9171911279942736e-05]  | 0.228457  | [0.19856980290855802, 0.2572259383987512]    | 0.279669  | [0.23495168230228025, 0.32046737374750095] |

## Saturation and Pile-Up Strata

| stratum                 | method                       |      n |         bias |     res68 | res68_ci95                                   |       mae |
|:------------------------|:-----------------------------|-------:|-------------:|----------:|:---------------------------------------------|----------:|
| all_heldout             | mlp                          | 167683 |  0.00680348  | 0.0232743 | [0.02064499836683273, 0.028806627684831606]  | 0.0776993 |
| all_heldout             | traditional_clipped_template | 167683 |  0.00186671  | 0.0403935 | [0.03390679215697531, 0.049748334991572093]  | 0.197345  |
| all_heldout             | gradient_boosted_trees       | 167683 | -0.0123365   | 0.0313697 | [0.028839863854503957, 0.03434524443034958]  | 0.087949  |
| all_heldout             | gated_residual_cnn           | 167683 |  0.0114011   | 0.125784  | [0.1132740214970708, 0.1423226558631659]     | 0.165504  |
| near_knee               | mlp                          |  58040 |  0.014709    | 0.0207866 | [0.02000411466509103, 0.02285410965085029]   | 0.0332858 |
| near_knee               | traditional_clipped_template |  58040 | -0.00151958  | 0.0240016 | [0.022222028844649692, 0.027065270159896147] | 0.0509686 |
| near_knee               | gradient_boosted_trees       |  58040 | -0.0182757   | 0.0319973 | [0.02950680939968294, 0.03727567922084498]   | 0.0431882 |
| near_knee               | gated_residual_cnn           |  58040 | -0.0199468   | 0.0920602 | [0.0846693049106002, 0.10245071508586409]    | 0.0920908 |
| hard_saturated          | mlp                          |  42426 |  0.0147775   | 0.0214167 | [0.020138637721538545, 0.02346961183607578]  | 0.0316819 |
| hard_saturated          | traditional_clipped_template |  42426 | -0.000787198 | 0.0263065 | [0.024520581729010144, 0.028590297963566103] | 0.0468607 |
| hard_saturated          | gradient_boosted_trees       |  42426 | -0.023681    | 0.0337495 | [0.03155958834814397, 0.039944323201698426]  | 0.0440624 |
| hard_saturated          | gated_residual_cnn           |  42426 | -0.0138191   | 0.0864786 | [0.07607259330898523, 0.09974042465597391]   | 0.0819969 |
| pileup_multiplicity_ge2 | mlp                          |  18863 | -0.0383512   | 0.150973  | [0.1450913377690316, 0.15526593139857056]    | 0.17417   |
| pileup_multiplicity_ge2 | traditional_clipped_template |  18863 |  0.0384513   | 0.110057  | [0.09972003132675382, 0.12990374068079685]   | 0.404873  |
| pileup_multiplicity_ge2 | gradient_boosted_trees       |  18863 | -0.0160429   | 0.0930125 | [0.0803135712998618, 0.11454442172101731]    | 0.160026  |
| pileup_multiplicity_ge2 | gated_residual_cnn           |  18863 |  0.15128     | 0.251383  | [0.2478114357173443, 0.2567908110779524]     | 0.256636  |
| high_recovery_tail      | mlp                          |  52370 |  0.00505899  | 0.0184007 | [0.015477352142333988, 0.022781074826419348] | 0.0258352 |
| high_recovery_tail      | traditional_clipped_template |  52370 |  0.0245975   | 0.0421473 | [0.0379521765136904, 0.04574596339767923]    | 0.0424573 |
| high_recovery_tail      | gradient_boosted_trees       |  52370 | -0.0224689   | 0.0306432 | [0.02996001471013428, 0.0315372624131869]    | 0.0372435 |
| high_recovery_tail      | gated_residual_cnn           |  52370 |  0.078313    | 0.122999  | [0.1076096076667309, 0.13953639797747136]    | 0.118105  |

## PID Side Diagnostic

The winner's waveform recovery score is accompanied by a PID separability diagnostic: held-out AUC=0.3880, AP=0.3175. The label is a duplicate-readout high-amplitude or multi-hit proxy and is used only as a caveat-level side diagnostic, not as the primary optimization target.

## Systematics and Caveats

* The target is duplicate-readout anchored and clips rare zero-duplicate charge closures before adding recovery and timing terms; it is appropriate for readout-closure hysteresis but not an absolute deposited-energy measurement.
* Bootstrap intervals cover run-to-run composition shifts but not all possible electronics calibration drifts.
* Saturation is approximated by an ADC knee and by charge-tail recovery. True front-end hysteresis may include nonlocal baseline memory extending outside the 18-sample window.
* Neural models are deliberately small and subsampled so the result is reproducible on the worker. The MLP win over the robust clipped-template baseline should be read as a modest context-learning gain on top of engineered hysteresis observables, not as evidence for a deployable calibration without a broader electronics systematic campaign.
