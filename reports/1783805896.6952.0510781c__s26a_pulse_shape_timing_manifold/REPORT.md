# S26A: Pulse-shape timing manifold

## Abstract

This study reproduces the S00 B-stave selected-pulse number directly from raw ROOT and then benchmarks a traditional constant-fraction plus analytic timewalk/template-residual baseline against ridge, gradient-boosted trees, MLP, 1D-CNN, a compact waveform transformer, and a new gated residual CNN. The winner is **mlp** under held-out-run timing-manifold residual res68 with run-block bootstrap confidence intervals.

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

Let \(w_{ejs}\) be the baseline-corrected even-channel waveform for event \(e\), stave \(j\), and sample \(s\). For each selected B-stave pulse, a constant-fraction crossing time \(t_{ej}^{CFD}\) is linearly interpolated at fraction \(f=0.45\) of the pulse maximum before the peak. The supervised timing-manifold residual target is

\[ r_e = \operatorname{clip}_{[-15,15]}\left(\sqrt{\frac{\sum_j m_{ej}(t_{ej}^{CFD}-\bar{t}_{e})^2}{\max(\sum_j m_{ej},1)}} + 10\,(T_e-E_e) + 0.28\,S_e + 0.04\,D_e\right), \]

Here \(m_{ej}\) marks selected staves, \(\bar{t}_e\) is the amplitude-weighted CFD time, \(T_e\) is the late positive charge fraction, \(E_e\) is the early positive charge fraction, \(S_e\) is the saturated-stave count, and \(D_e\) is the pretrigger sample-0-to-sample-3 pedestal excursion. The target is therefore a timing-width observable with explicit pulse-shape, saturation-edge, and pedestal terms. Odd duplicate charges, event identifiers, and run labels are excluded from learned-model inputs.

The traditional CFD/timewalk-template method fits a robust pedestal-aware calibration from log even charge, saturation count, knee count, recovery-tail fraction, onset sharpness, and pedestal-sideband spread to \(r_e\), then clips predictions to the calibrated target range to prevent nonphysical extrapolation. A tail-shape timing baseline uses calibrated early/late charge fractions, and an analytic saturation-timewalk baseline uses saturation and onset terms. The ML panel is ridge regression, gradient-boosted trees, a tabular MLP, a 1D-CNN over the four B-stave waveforms, a waveform transformer with sample-token self-attention, and the new gated residual CNN. The new architecture multiplies learned convolutional channels by a sigmoid gate from the maximum pooled waveform context before residual regression.

## Split and Bootstrap

Training uses `sample_i_calib` and `sample_ii_calib` runs; all analysis runs are held out. Confidence intervals resample held-out runs with replacement, preserving run-level correlations and current-family composition.

## Head-to-Head Benchmark

| method                            |      n |       bias | bias_ci95                                        |    res68 | res68_ci95                               |      mae | mae_ci95                                 |
|:----------------------------------|-------:|-----------:|:-------------------------------------------------|---------:|:-----------------------------------------|---------:|:-----------------------------------------|
| mlp                               | 167683 | -0.010931  | [-0.019207456707954408, -0.00020842477679253537] | 0.369961 | [0.3194833109974863, 0.4540676560616499] | 0.612133 | [0.5221370829940412, 0.7032995891407097] |
| gradient_boosted_trees            | 167683 |  0.0164426 | [-0.01261902965843883, 0.044550136350526987]     | 0.402749 | [0.3683445696482977, 0.4357922094266886] | 0.454997 | [0.40308534726306244, 0.511396937515081] |
| traditional_cfd_timewalk_template | 167683 | -0.0330969 | [-0.10251013086777397, 0.0]                      | 0.548538 | [0.4825756817222639, 0.6385077271397555] | 0.999616 | [0.8550926263234851, 1.1246097832928237] |
| gated_residual_cnn                | 167683 | -0.0295075 | [-0.13188612991571433, 0.07093397057056403]      | 0.985399 | [0.8583285830283167, 1.2248848998248578] | 1.35089  | [1.1708683440528835, 1.5361522001260906] |
| waveform_transformer              | 167683 |  0.0465847 | [-0.09262487453222287, 0.15986843544244747]      | 1.12146  | [0.9707129472208026, 1.4301586535260238] | 1.43124  | [1.2459281565328195, 1.6453440166576419] |
| ridge                             | 167683 |  0.330237  | [0.1542959363469577, 0.4864764858476832]         | 1.1546   | [1.060687704529943, 1.2900278873917537]  | 1.36666  | [1.2093214880642715, 1.5283936173219947] |
| 1d_cnn                            | 167683 |  0.011201  | [-0.14311612512813576, 0.1343411739915609]       | 1.18419  | [0.9976422053027155, 1.591990833334206]  | 1.51452  | [1.3106098284914791, 1.7625172588837323] |
| analytic_saturation_timewalk      | 167683 | -0.110446  | [-0.3913344435372634, 0.12176314261899791]       | 1.59888  | [1.232270340389334, 2.1889789397212485]  | 2.39932  | [1.9732692816330657, 2.818294959593873]  |
| tail_shape_timing                 | 167683 | -0.208127  | [-0.763618474437406, 0.3295675042828166]         | 1.93786  | [1.6667645415188734, 2.477450713090319]  | 2.49281  | [2.135504279337203, 2.90366947892214]    |

The table reports timing-manifold residual width (`res68`, ns), median timing bias (`bias`, ns), and mean absolute residual (`mae`, ns). The same held-out predictions are reused in the stress strata below so shape atoms, pedestal excursions, saturation edge, and pile-up sidebands are evaluated without changing the training population.

## Saturation and Pile-Up Strata

| stratum                 | method                            |      n |         bias |    res68 | res68_ci95                                 |      mae |
|:------------------------|:----------------------------------|-------:|-------------:|---------:|:-------------------------------------------|---------:|
| all_heldout             | mlp                               | 167683 | -0.010931    | 0.369961 | [0.31832678861379626, 0.4532410472631454]  | 0.612133 |
| all_heldout             | traditional_cfd_timewalk_template | 167683 | -0.0330969   | 0.548538 | [0.4931709239649182, 0.6312413514419937]   | 0.999616 |
| all_heldout             | gradient_boosted_trees            | 167683 |  0.0164426   | 0.402749 | [0.36322961072492177, 0.4364701972986418]  | 0.454997 |
| all_heldout             | 1d_cnn                            | 167683 |  0.011201    | 1.18419  | [0.9932825086164474, 1.526279346644878]    | 1.51452  |
| all_heldout             | waveform_transformer              | 167683 |  0.0465847   | 1.12146  | [0.9532763907313347, 1.437726739522438]    | 1.43124  |
| all_heldout             | gated_residual_cnn                | 167683 | -0.0295075   | 0.985399 | [0.8461468880176547, 1.2656975984573362]   | 1.35089  |
| shape_atom_edge         | mlp                               |  74183 |  0.00929016  | 0.386876 | [0.3230885938388109, 0.4991146588568956]   | 0.653802 |
| shape_atom_edge         | traditional_cfd_timewalk_template |  74183 | -0.156176    | 0.548436 | [0.42593928032203454, 0.7274046735333819]  | 0.990999 |
| shape_atom_edge         | gradient_boosted_trees            |  74183 | -0.0162564   | 0.480576 | [0.42803394187658395, 0.5574781571489033]  | 0.590675 |
| shape_atom_edge         | 1d_cnn                            |  74183 | -0.324967    | 1.47302  | [1.1759527717232705, 1.917848354072571]    | 1.61871  |
| shape_atom_edge         | waveform_transformer              |  74183 | -0.267406    | 1.31179  | [1.055684191048146, 1.6802984578907478]    | 1.44658  |
| shape_atom_edge         | gated_residual_cnn                |  74183 | -0.231357    | 1.04915  | [0.8235966980869692, 1.3732584701180457]   | 1.33365  |
| saturation_edge         | mlp                               |  58257 | -0.0330934   | 0.311209 | [0.28731790769100174, 0.3527743918085098]  | 0.476799 |
| saturation_edge         | traditional_cfd_timewalk_template |  58257 |  0.0207305   | 0.539275 | [0.5005814018574921, 0.5952773850895955]   | 0.874599 |
| saturation_edge         | gradient_boosted_trees            |  58257 |  0.0629783   | 0.351398 | [0.33594782514589294, 0.36322961072492177] | 0.361789 |
| saturation_edge         | 1d_cnn                            |  58257 |  0.0774247   | 0.865566 | [0.7810448626780514, 0.9793536056429147]   | 1.13285  |
| saturation_edge         | waveform_transformer              |  58257 |  0.169249    | 0.912167 | [0.8426311914789677, 1.0314615027034284]   | 1.12367  |
| saturation_edge         | gated_residual_cnn                |  58257 |  0.040837    | 0.887203 | [0.7912000992298128, 1.0474421325826646]   | 1.09774  |
| hard_saturated          | mlp                               |  42396 | -0.0431702   | 0.333178 | [0.30474799408018616, 0.37761848127841946] | 0.484569 |
| hard_saturated          | traditional_cfd_timewalk_template |  42396 |  0.0348033   | 0.569985 | [0.5283587649882182, 0.6223840622408772]   | 0.91729  |
| hard_saturated          | gradient_boosted_trees            |  42396 |  0.069991    | 0.36279  | [0.3454517597105018, 0.3764312061208169]   | 0.37327  |
| hard_saturated          | 1d_cnn                            |  42396 |  0.071511    | 0.93445  | [0.8522421312332151, 1.0452006158232685]   | 1.15657  |
| hard_saturated          | waveform_transformer              |  42396 |  0.178258    | 0.98281  | [0.9053372987163066, 1.0927842965888979]   | 1.15259  |
| hard_saturated          | gated_residual_cnn                |  42396 |  0.0536724   | 0.960997 | [0.8681200489079955, 1.1076668213903904]   | 1.12852  |
| pileup_multiplicity_ge2 | mlp                               |  18918 |  0.403873    | 1.83925  | [1.743565833304773, 2.1067893427346465]    | 1.58605  |
| pileup_multiplicity_ge2 | traditional_cfd_timewalk_template |  18918 | -2.09334     | 3.04722  | [2.8254985567570574, 3.7576843535116917]   | 2.75838  |
| pileup_multiplicity_ge2 | gradient_boosted_trees            |  18918 | -0.164507    | 1.3907   | [1.299949524849906, 1.600383202764843]     | 1.25796  |
| pileup_multiplicity_ge2 | 1d_cnn                            |  18918 |  2.49798     | 4.26406  | [4.081570888622826, 4.390581225228262]     | 3.35433  |
| pileup_multiplicity_ge2 | waveform_transformer              |  18918 |  2.07859     | 3.73239  | [3.626695113006717, 3.8502978710815783]    | 2.97614  |
| pileup_multiplicity_ge2 | gated_residual_cnn                |  18918 |  1.99199     | 3.64669  | [3.5606389399833227, 3.7158789431893937]   | 2.90473  |
| high_recovery_tail      | mlp                               |  52244 | -0.000965029 | 0.342567 | [0.2793872249424458, 0.44630384571251946]  | 0.512721 |
| high_recovery_tail      | traditional_cfd_timewalk_template |  52244 | -0.243147    | 0.52491  | [0.3729765340180283, 0.885314134051999]    | 0.917272 |
| high_recovery_tail      | gradient_boosted_trees            |  52244 | -0.0325312   | 0.453554 | [0.35996130061500714, 0.6293736106964525]  | 0.597273 |
| high_recovery_tail      | 1d_cnn                            |  52244 | -0.478606    | 1.40237  | [1.0147430237107078, 2.0220833945033903]   | 1.47302  |
| high_recovery_tail      | waveform_transformer              |  52244 | -0.340177    | 1.24459  | [0.911036495873929, 1.8105217651104926]    | 1.28308  |
| high_recovery_tail      | gated_residual_cnn                |  52244 | -0.313334    | 0.974579 | [0.7314802200198176, 1.39063361404391]     | 1.1811   |
| pedestal_excursion      | mlp                               |  40785 |  0.0320163   | 0.96732  | [0.6610302987051014, 1.193754368050836]    | 1.18963  |
| pedestal_excursion      | traditional_cfd_timewalk_template |  40785 |  0           | 0.869196 | [0.6762087658349244, 1.1483566777900283]   | 1.40893  |
| pedestal_excursion      | gradient_boosted_trees            |  40785 | -0.178829    | 0.460091 | [0.4392572971853356, 0.518270618768831]    | 0.565852 |
| pedestal_excursion      | 1d_cnn                            |  40785 | -0.174965    | 2.54935  | [1.7778104839324955, 3.1204874277114865]   | 2.33026  |
| pedestal_excursion      | waveform_transformer              |  40785 | -0.121956    | 2.4665   | [1.7827859304571156, 3.1070694233292264]   | 2.23025  |
| pedestal_excursion      | gated_residual_cnn                |  40785 | -0.17837     | 2.38673  | [1.6974512493324294, 2.901834416389465]    | 2.1984   |
| large_timing_bias_proxy | mlp                               |  74183 |  0.00929016  | 0.386876 | [0.32613488696515563, 0.50132654386248]    | 0.653802 |
| large_timing_bias_proxy | traditional_cfd_timewalk_template |  74183 | -0.156176    | 0.548436 | [0.4325864642417297, 0.748961728860506]    | 0.990999 |
| large_timing_bias_proxy | gradient_boosted_trees            |  74183 | -0.0162564   | 0.480576 | [0.427321722495461, 0.573069609245985]     | 0.590675 |
| large_timing_bias_proxy | 1d_cnn                            |  74183 | -0.324967    | 1.47302  | [1.1650957903265957, 1.8843230936524045]   | 1.61871  |
| large_timing_bias_proxy | waveform_transformer              |  74183 | -0.267406    | 1.31179  | [1.0636634439229966, 1.6649071144895053]   | 1.44658  |
| large_timing_bias_proxy | gated_residual_cnn                |  74183 | -0.231357    | 1.04915  | [0.843056745827198, 1.3919830881287836]    | 1.33365  |

## PID Side Diagnostic

The winner's waveform recovery score is accompanied by a PID separability diagnostic: held-out AUC=0.4096, AP=0.3446. The label is a duplicate-readout high-amplitude or multi-hit proxy and is used only as a caveat-level side diagnostic, not as the primary optimization target.

## Systematics and Caveats

* The target is a CFD timing-manifold residual, not an external hodoscope or RF-clock truth time. It is appropriate for ranking correction models on internal B-stave timing consistency, not for claiming an absolute beam time resolution.
* Bootstrap intervals cover run-to-run composition shifts but not all possible electronics calibration drifts.
* Saturation is approximated by an ADC knee and by charge-tail recovery. True front-end recovery may include nonlocal baseline memory extending outside the 18-sample window.
* Pedestal drift is measured from only four pretrigger samples and should be interpreted as a sideband proxy rather than a dedicated forced-trigger pedestal truth label.
* Neural models are deliberately small and subsampled so the result is reproducible on the worker. A neural win over the robust CFD/timewalk baseline should be read as a context-learning gain on top of engineered timing observables, not as evidence for a deployable calibration without a broader electronics systematic campaign.

## Recommendation

The selected winner for `result.json` is `mlp`. Saturated and high-pedestal-excursion pulses should remain included only with a run-heldout timing-manifold correction and explicit uncertainty inflation in the affected strata; uncorrected saturated pulses should not be promoted into precision timing closure tables.
