# S25A: pedestal-saturation pulse-shape frontier

## Abstract

This study reproduces the S00 B-stave selected-pulse number directly from raw ROOT and then benchmarks a traditional robust pedestal plus clipped-template saturation correction against ridge, gradient-boosted trees, MLP, 1D-CNN, a waveform transformer, and a new gated residual CNN. The winner is **mlp** under held-out-run pulse-shape residual res68 with run-block bootstrap confidence intervals.

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

Let \(w_{ejs}\) be the baseline-corrected even-channel waveform for event \(e\), stave \(j\), and sample \(s\), and let \(q'_e\) be the duplicate odd-readout positive charge. The pulse-shape residual target is

\[ h_e = \operatorname{clip}_{[-4,4]}\left(1 - \frac{\sum_j Q_{ej}}{\max(\sum_j Q'_{ej},1)}\right) + 0.18\,\frac{\sum_{j,s\ge 9}\max(w_{ejs},0)}{\max(\sum_j Q_{ej},1)} + 0.015\,(\bar{s}_{peak,e}-5). \]

The first term measures charge lost to clipping relative to the independent duplicate readout, the second term measures delayed saturation recovery, and the third term captures peak-sample timing displacement. Pedestal drift is probed with raw pretrigger median, interquartile range, and sample-0-to-sample-3 slope diagnostics, but odd duplicate charges, event identifiers, and run labels are excluded from learned-model inputs.

The traditional clipped-template method fits a robust pedestal-aware calibration from log even charge, saturation count, knee count, recovery-tail fraction, onset sharpness, and pedestal-sideband spread to \(h_e\), then clips predictions to the calibrated target range to prevent extrapolated nonphysical charge recovery. Charge-tail integration uses the calibrated late-charge fraction. The Birks/Huber method is a robust linear correction using saturation and onset terms. The ML panel is ridge regression, gradient-boosted trees, a tabular MLP, a 1D-CNN over the four B-stave waveforms, a waveform transformer with sample-token self-attention, and the new gated residual CNN. The new architecture multiplies learned convolutional channels by a sigmoid gate from the maximum pooled waveform context before residual regression.

## Split and Bootstrap

Training uses `sample_i_calib` and `sample_ii_calib` runs; all analysis runs are held out. Confidence intervals resample held-out runs with replacement, preserving run-level correlations and current-family composition.

## Head-to-Head Benchmark

| method                       |      n |         bias | bias_ci95                                        |     res68 | res68_ci95                                   |       mae | mae_ci95                                    |
|:-----------------------------|-------:|-------------:|:-------------------------------------------------|----------:|:---------------------------------------------|----------:|:--------------------------------------------|
| mlp                          | 167683 | -0.000251173 | [-0.00049141846597196, 4.679268598557032e-05]    | 0.0159647 | [0.013523441382646566, 0.018961805856227875] | 0.051622  | [0.04146822730690501, 0.062348648252296274] |
| traditional_clipped_template | 167683 |  0.00116275  | [-0.00017297738323740277, 0.0025326164483023828] | 0.0299608 | [0.027511029857142204, 0.03303475614542952]  | 0.141024  | [0.11116764640502595, 0.17108123335358097]  |
| gradient_boosted_trees       | 167683 | -0.0136946   | [-0.015822824996310908, -0.011690478889581852]   | 0.0332068 | [0.02984716186433946, 0.037954409174035676]  | 0.0783139 | [0.06222091537900172, 0.0948179139665819]   |
| 1d_cnn                       | 167683 | -0.0095124   | [-0.010568653196096433, -0.008108760748058566]   | 0.0385764 | [0.0352931073100865, 0.042278885729908955]   | 0.0942664 | [0.07738540283465561, 0.11061839473359782]  |
| charge_tail_integration      | 167683 |  0.00382681  | [-0.0055180851850210825, 0.012641397166535888]   | 0.0482599 | [0.04355560229268362, 0.053582388067677574]  | 0.205711  | [0.1541255282490798, 0.25526635116998736]   |
| birks_huber_saturation       | 167683 | -0.00835227  | [-0.014149162394341091, -0.0039765794816713305]  | 0.050402  | [0.04308824944601026, 0.058156388811403996]  | 0.235151  | [0.17567817150905077, 0.3021244214861927]   |
| gated_residual_cnn           | 167683 |  0.0227181   | [0.02040526939183473, 0.026324028000235544]      | 0.0620691 | [0.05279361670196057, 0.07380660544693472]   | 0.113529  | [0.09090577171366793, 0.13554186987700267]  |
| waveform_transformer         | 167683 |  0.0403892   | [0.03756075784564017, 0.043359984844923025]      | 0.0730861 | [0.0667771150121093, 0.08059666297584772]    | 0.109517  | [0.09213072729095051, 0.12504913034804818]  |
| ridge                        | 167683 |  0.0180394   | [0.004502312697528382, 0.033863064859206364]     | 0.163625  | [0.13384319840125594, 0.20764489538537206]   | 0.210551  | [0.17467821138023276, 0.24780456005356713]  |

The table reports pulse-shape residual width (`res68`), median timing/closure bias (`bias`), and mean absolute residual (`mae`). The same held-out predictions are reused in the stress strata below so that saturation recovery and pedestal drift are evaluated without changing the training population.

## Saturation and Pile-Up Strata

| stratum                 | method                       |      n |         bias |      res68 | res68_ci95                                   |       mae |
|:------------------------|:-----------------------------|-------:|-------------:|-----------:|:---------------------------------------------|----------:|
| all_heldout             | mlp                          | 167683 | -0.000251173 | 0.0159647  | [0.013441076641976836, 0.020182740032374833] | 0.051622  |
| all_heldout             | traditional_clipped_template | 167683 |  0.00116275  | 0.0299608  | [0.027577743158255376, 0.032707602004430514] | 0.141024  |
| all_heldout             | gradient_boosted_trees       | 167683 | -0.0136946   | 0.0332068  | [0.02975635918258972, 0.03780412276745063]   | 0.0783139 |
| all_heldout             | 1d_cnn                       | 167683 | -0.0095124   | 0.0385764  | [0.035173504896461955, 0.04215739671260121]  | 0.0942664 |
| all_heldout             | waveform_transformer         | 167683 |  0.0403892   | 0.0730861  | [0.06709481196761131, 0.07992908304184675]   | 0.109517  |
| all_heldout             | gated_residual_cnn           | 167683 |  0.0227181   | 0.0620691  | [0.052853789620697506, 0.07520942192673685]  | 0.113529  |
| near_knee               | mlp                          |  58040 | -8.58971e-05 | 0.00986575 | [0.009317002172768119, 0.01136802557110785]  | 0.0161639 |
| near_knee               | traditional_clipped_template |  58040 |  0.00122759  | 0.032328   | [0.03000926870815052, 0.035396550687023715]  | 0.0555435 |
| near_knee               | gradient_boosted_trees       |  58040 | -0.0161058   | 0.0278999  | [0.0257759465698495, 0.031893557514154715]   | 0.0353238 |
| near_knee               | 1d_cnn                       |  58040 | -0.0105745   | 0.0330723  | [0.031193929312378178, 0.036802397557497035] | 0.042781  |
| near_knee               | waveform_transformer         |  58040 |  0.0301546   | 0.0547811  | [0.053125537655353536, 0.05761216482043265]  | 0.0582452 |
| near_knee               | gated_residual_cnn           |  58040 |  0.0219311   | 0.040144   | [0.038268912702798835, 0.043100885412395]    | 0.0463829 |
| hard_saturated          | mlp                          |  42426 |  0.000195165 | 0.00786957 | [0.007275991722941399, 0.008852223142981534] | 0.0140591 |
| hard_saturated          | traditional_clipped_template |  42426 |  0.000991751 | 0.0346581  | [0.032437102751570655, 0.0372759966300057]   | 0.054171  |
| hard_saturated          | gradient_boosted_trees       |  42426 | -0.0192889   | 0.028791   | [0.027360376702491532, 0.03139739384767778]  | 0.0358303 |
| hard_saturated          | 1d_cnn                       |  42426 | -0.0106296   | 0.0347344  | [0.03273380518496038, 0.038638366695195436]  | 0.0414585 |
| hard_saturated          | waveform_transformer         |  42426 |  0.024042    | 0.0481017  | [0.04596338142454623, 0.05162722654700281]   | 0.0526524 |
| hard_saturated          | gated_residual_cnn           |  42426 |  0.0238994   | 0.0408029  | [0.03958458865374326, 0.04349731687307356]   | 0.0445691 |
| pileup_multiplicity_ge2 | mlp                          |  18863 | -0.0174778   | 0.0717851  | [0.06944654896527537, 0.07574387806743385]   | 0.101162  |
| pileup_multiplicity_ge2 | traditional_clipped_template |  18863 | -0.013145    | 0.182837   | [0.1540943050114244, 0.22777024010749372]    | 0.277268  |
| pileup_multiplicity_ge2 | gradient_boosted_trees       |  18863 | -0.0300086   | 0.0889092  | [0.07554256125337537, 0.11472209174341082]   | 0.161934  |
| pileup_multiplicity_ge2 | 1d_cnn                       |  18863 | -0.0156224   | 0.0940916  | [0.08121439414381983, 0.11333720042467119]   | 0.140287  |
| pileup_multiplicity_ge2 | waveform_transformer         |  18863 |  0.0661865   | 0.139103   | [0.13549806243181228, 0.1440277555716038]    | 0.175216  |
| pileup_multiplicity_ge2 | gated_residual_cnn           |  18863 |  0.0484266   | 0.133146   | [0.12817854641318321, 0.14331641701519487]   | 0.168464  |
| high_recovery_tail      | mlp                          |  52370 | -0.000270365 | 0.0171719  | [0.014517464715242397, 0.02111070651113987]  | 0.0211826 |
| high_recovery_tail      | traditional_clipped_template |  52370 |  0.00855929  | 0.0214439  | [0.020882118883487167, 0.022057242262496363] | 0.0377838 |
| high_recovery_tail      | gradient_boosted_trees       |  52370 | -0.0300023   | 0.038017   | [0.037100177981376964, 0.039211806526537836] | 0.0448005 |
| high_recovery_tail      | 1d_cnn                       |  52370 | -0.00938367  | 0.0367123  | [0.03552085264801979, 0.03794558140635492]   | 0.0403834 |
| high_recovery_tail      | waveform_transformer         |  52370 |  0.0447747   | 0.0693975  | [0.06329914511740209, 0.07535464545786381]   | 0.0669718 |
| high_recovery_tail      | gated_residual_cnn           |  52370 |  0.03862     | 0.0714604  | [0.06705357608139516, 0.07536192736029626]   | 0.0645286 |
| high_pedestal_drift     | mlp                          |  41243 | -0.00400741  | 0.0775891  | [0.03509310953587293, 0.12358252225548033]   | 0.160782  |
| high_pedestal_drift     | traditional_clipped_template |  41243 |  0.00638658  | 0.258659   | [0.09402553197165968, 0.4746365527986266]    | 0.455682  |
| high_pedestal_drift     | gradient_boosted_trees       |  41243 | -0.0136015   | 0.127255   | [0.057353936012671594, 0.2344513688981033]   | 0.213874  |
| high_pedestal_drift     | 1d_cnn                       |  41243 | -0.00047349  | 0.165764   | [0.07523021938174965, 0.267119173488617]     | 0.268905  |
| high_pedestal_drift     | waveform_transformer         |  41243 |  0.0426591   | 0.162096   | [0.10219298347085722, 0.2510038075160982]    | 0.258657  |
| high_pedestal_drift     | gated_residual_cnn           |  41243 |  0.0265267   | 0.172369   | [0.09433436200767757, 0.2831789436960221]    | 0.291548  |
| large_timing_bias_proxy | mlp                          |  74071 | -0.00166907  | 0.0209379  | [0.017789806427061555, 0.02465309388935566]  | 0.0714399 |
| large_timing_bias_proxy | traditional_clipped_template |  74071 |  0.000449678 | 0.0255014  | [0.023716768290787983, 0.027682026432201544] | 0.171777  |
| large_timing_bias_proxy | gradient_boosted_trees       |  74071 | -0.024483    | 0.0401268  | [0.03827204323780568, 0.04217120074720527]   | 0.0911822 |
| large_timing_bias_proxy | 1d_cnn                       |  74071 | -0.00314548  | 0.0413909  | [0.039148510831594485, 0.04426848198294639]  | 0.115561  |
| large_timing_bias_proxy | waveform_transformer         |  74071 |  0.0562134   | 0.0867978  | [0.08209246948361398, 0.09131167304873467]   | 0.129515  |
| large_timing_bias_proxy | gated_residual_cnn           |  74071 |  0.0291122   | 0.0735658  | [0.06832174237072469, 0.07988136816740038]   | 0.143288  |

## PID Side Diagnostic

The winner's waveform recovery score is accompanied by a PID separability diagnostic: held-out AUC=0.4966, AP=0.3961. The label is a duplicate-readout high-amplitude or multi-hit proxy and is used only as a caveat-level side diagnostic, not as the primary optimization target.

## Systematics and Caveats

* The target is duplicate-readout anchored and clips rare zero-duplicate charge closures before adding recovery and timing terms; it is appropriate for readout-closure hysteresis but not an absolute deposited-energy measurement.
* Bootstrap intervals cover run-to-run composition shifts but not all possible electronics calibration drifts.
* Saturation is approximated by an ADC knee and by charge-tail recovery. True front-end hysteresis may include nonlocal baseline memory extending outside the 18-sample window.
* Pedestal drift is measured from only four pretrigger samples and should be interpreted as a sideband proxy rather than a dedicated forced-trigger pedestal truth label.
* Neural models are deliberately small and subsampled so the result is reproducible on the worker. A neural win over the robust clipped-template baseline should be read as a context-learning gain on top of engineered hysteresis observables, not as evidence for a deployable calibration without a broader electronics systematic campaign.

## Recommendation

The selected winner for `result.json` is `mlp`. Saturated pulses should remain included only with a run-heldout pedestal/saturation correction and with explicit uncertainty inflation for high-recovery-tail and high-pedestal-drift strata; uncorrected saturated pulses should not be promoted into precision timing or energy closure tables.
