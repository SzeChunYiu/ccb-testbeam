# S28A: Sub-sample pulse phase-transfer benchmark

## Abstract

This study reproduces the S00 B-stave selected-pulse number directly from raw ROOT and then benchmarks sub-sample phase-transfer calibration. The traditional comparator combines fractional-delay constant-fraction timing, parabolic peak phase, and normalized cross-correlation template alignment; the learned panel contains ridge, gradient-boosted trees, MLP, 1D-CNN, waveform transformer, and a new gated residual phase CNN. The winner written to `result.json` is **gradient_boosted_trees** under complete-run-heldout res68 of duplicate-readout phase-transfer residuals with run-block bootstrap confidence intervals.

## Raw ROOT Reproduction

Raw files are read from `/home/billy/ccb-data/extracted/root/root`. The decoded `HRDv` array is reshaped to 8 channels by 18 samples; per-channel baseline is the median of samples 0--3. A selected B-stave pulse is an even channel in B2/B4/B6/B8 above 1000 ADC. The duplicate odd channel is inverted to positive polarity and used only as an external phase-transfer target, never as a learned input.

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

Let \(w_{ejs}\) be the baseline-corrected even-channel waveform for event \(e\), stave \(j\), sample \(s\), and let \(w'_{ejs}\) be the positive-polarity duplicate odd readout. The primary stave \(j^*(e)\) is the selected B stave with maximum even-channel amplitude. For a waveform \(u_s\), the constant-fraction time at fraction \(f=0.5\) is

\[ t_f(u)=k-1+\frac{f\max_s u_s-u_{k-1}}{u_k-u_{k-1}}, \quad k=\min\{s:u_s\ge f\max_r u_r\}. \]

The supervised phase-transfer target in sample units is

\[ y_e = \operatorname{clip}_{[-3,3]}\left[t_{0.5}(w'_{ej^*})-t_{0.5}(w_{ej^*})\right] + 0.04\ell_e + 0.02\left(t_{peak,e}-t_{0.5}(w_{ej^*})\right), \]

where \(\ell_e\) is the best small-lag normalized cross-correlation phase against the event-run proxy template and \(t_{peak,e}\) is a parabolic peak interpolation. The first term is the duplicate-readout phase-transfer closure, while the small deterministic terms stabilize ambiguous flat-topped pulses without using run or event identifiers.

Pedestal drift is probed with raw pretrigger median, interquartile range, and sample-0-to-sample-3 slope diagnostics. Pile-up, saturation phase walk, energy residual transfer, and PID stability are evaluated as stress strata using multiplicity, ADC knee/saturation counts, duplicate-readout charge loss, and a duplicate high-amplitude/multi-hit PID proxy.

The strong traditional method is a Huber-regressed fractional-delay template alignment using log charge, saturation/knee counts, recovery tail, constant-fraction phase, parabolic peak phase, cross-correlation lag, pedestal spread, and onset slope, with predictions clipped to the training target range. Additional traditional controls use tail-only charge integration and a Birks-style saturation Huber correction. The ML panel is ridge regression, gradient-boosted trees, a tabular MLP, a 1D-CNN over the four B-stave waveforms, a waveform transformer with sample-token self-attention, and the new gated residual phase CNN. The new architecture multiplies learned convolutional channels by a sigmoid gate from maximum-pooled waveform context before residual phase regression.

## Split and Bootstrap

Training uses `sample_i_calib` and `sample_ii_calib` runs; all analysis runs are held out. Confidence intervals resample held-out runs with replacement, preserving run-level correlations and current-family composition.

## Head-to-Head Benchmark

| method                                |     n |         bias | bias_ci95                                       |     res68 | res68_ci95                                   |       mae | mae_ci95                                     |
|:--------------------------------------|------:|-------------:|:------------------------------------------------|----------:|:---------------------------------------------|----------:|:---------------------------------------------|
| gradient_boosted_trees                | 88089 |  0.00332514  | [0.0024946861670774546, 0.004306044867853479]   | 0.0156926 | [0.012043406547890073, 0.019924458890556232] | 0.0279172 | [0.022805848289224825, 0.033649105321987866] |
| traditional_fractional_delay_template | 88089 | -0.00210459  | [-0.0031474716236049457, -0.001185950889042672] | 0.01816   | [0.016483277054745213, 0.020346939045237974] | 0.0386929 | [0.03162862143450207, 0.045401288811583736]  |
| charge_tail_integration               | 88089 |  0.000739409 | [-0.0005262658810993859, 0.002646680366709064]  | 0.0246053 | [0.018327049069111045, 0.03018890117260721]  | 0.06132   | [0.04771591833225684, 0.07423505728981324]   |
| birks_huber_saturation                | 88089 | -0.000973394 | [-0.003675721049291403, 0.0027101429940665387]  | 0.0267844 | [0.020670770476014563, 0.03205393958581623]  | 0.060547  | [0.049379577921226755, 0.07313203149882601]  |
| mlp                                   | 88089 | -0.00300497  | [-0.006915169954299927, 0.0017186209559440628]  | 0.0450149 | [0.04015351366996765, 0.04903064131736759]   | 0.0516019 | [0.045733859549553876, 0.0567303397330835]   |
| waveform_transformer                  | 88089 |  0.0096131   | [0.0014200225472450257, 0.015448093414306642]   | 0.0458503 | [0.04343169766664507, 0.04869784766435623]   | 0.053896  | [0.047420468717696895, 0.06045166477829686]  |
| ridge                                 | 88089 | -0.00878149  | [-0.014750031636344548, -0.003831509945911894]  | 0.0473186 | [0.04047792501981823, 0.05523039611567644]   | 0.0558542 | [0.04890336087049925, 0.06342473873879581]   |
| 1d_cnn                                | 88089 | -0.0116366   | [-0.018881963193416597, -0.0038875401020050013] | 0.0590373 | [0.0543318548202515, 0.06441608709096909]    | 0.0719403 | [0.06301626451007446, 0.0805266296151102]    |
| gated_residual_cnn                    | 88089 |  0.0114539   | [0.0026996612548828127, 0.022164343297481535]   | 0.0765435 | [0.06954538005590438, 0.08692556446790696]   | 0.0837803 | [0.07568670710784191, 0.09262941990016302]   |

The table reports sub-sample phase-transfer residual width (`res68`), median timing bias (`bias`), and mean absolute residual (`mae`) in sample units. At 10 ns/sample, a res68 of 0.10 corresponds to approximately 1 ns. The same held-out predictions are reused in the stress strata below so that pulse-shape residuals, pedestal-phase coupling, pile-up false alignment, saturation phase walk, energy residual transfer, and PID stability are evaluated without changing the training population.

## Saturation and Pile-Up Strata

| stratum                       | method                                |     n |         bias |     res68 | res68_ci95                                   |       mae |
|:------------------------------|:--------------------------------------|------:|-------------:|----------:|:---------------------------------------------|----------:|
| all_heldout                   | gradient_boosted_trees                | 88089 |  0.00332514  | 0.0156926 | [0.011691021924171716, 0.020432441653896072] | 0.0279172 |
| all_heldout                   | traditional_fractional_delay_template | 88089 | -0.00210459  | 0.01816   | [0.01648783118428804, 0.020478559988897884]  | 0.0386929 |
| all_heldout                   | ridge                                 | 88089 | -0.00878149  | 0.0473186 | [0.04002293482964126, 0.056994734287893326]  | 0.0558542 |
| all_heldout                   | mlp                                   | 88089 | -0.00300497  | 0.0450149 | [0.04066560715436936, 0.04995241117477419]   | 0.0516019 |
| all_heldout                   | 1d_cnn                                | 88089 | -0.0116366   | 0.0590373 | [0.05398872530460358, 0.06480894088745118]   | 0.0719403 |
| all_heldout                   | waveform_transformer                  | 88089 |  0.0096131   | 0.0458503 | [0.04287093436717989, 0.049203260242939]     | 0.053896  |
| all_heldout                   | gated_residual_cnn                    | 88089 |  0.0114539   | 0.0765435 | [0.06963563114404678, 0.0845651713013649]    | 0.0837803 |
| high_pulse_shape_residual     | gradient_boosted_trees                | 21773 | -0.00778551  | 0.0550464 | [0.048269578341039905, 0.06194672688859169]  | 0.0793645 |
| high_pulse_shape_residual     | traditional_fractional_delay_template | 21773 |  0.00358588  | 0.0710179 | [0.0534753285618894, 0.0811926729014596]     | 0.116834  |
| high_pulse_shape_residual     | ridge                                 | 21773 |  0.0155147   | 0.10112   | [0.09405376784661552, 0.10639752053659474]   | 0.126889  |
| high_pulse_shape_residual     | mlp                                   | 21773 |  0.0225009   | 0.0987568 | [0.08798350507020951, 0.10726556330919265]   | 0.114761  |
| high_pulse_shape_residual     | 1d_cnn                                | 21773 |  0.0332093   | 0.132467  | [0.118266838490963, 0.1432821959257126]      | 0.161707  |
| high_pulse_shape_residual     | waveform_transformer                  | 21773 |  0.0377207   | 0.100803  | [0.09050781828165055, 0.11246148869395256]   | 0.131836  |
| high_pulse_shape_residual     | gated_residual_cnn                    | 21773 |  0.0587361   | 0.173549  | [0.16838796246051788, 0.17871971136331558]   | 0.180195  |
| high_energy_transfer_residual | gradient_boosted_trees                | 22048 |  0.000599188 | 0.0488    | [0.0362794970168093, 0.062133997914321164]   | 0.0724565 |
| high_energy_transfer_residual | traditional_fractional_delay_template | 22048 | -0.0117654   | 0.0670058 | [0.04430022242606969, 0.0857527912201227]    | 0.108009  |
| high_energy_transfer_residual | ridge                                 | 22048 | -0.0230346   | 0.0967274 | [0.08171322937554944, 0.10647215707644762]   | 0.118144  |
| high_energy_transfer_residual | mlp                                   | 22048 |  0.00280207  | 0.088243  | [0.07224695533514022, 0.10269310057163243]   | 0.106819  |
| high_energy_transfer_residual | 1d_cnn                                | 22048 |  0.0171044   | 0.123586  | [0.10553464502096178, 0.14071365827322008]   | 0.150513  |
| high_energy_transfer_residual | waveform_transformer                  | 22048 |  0.00558618  | 0.0895227 | [0.06853066980838776, 0.10915320217609406]   | 0.113052  |
| high_energy_transfer_residual | gated_residual_cnn                    | 22048 |  0.034975    | 0.153399  | [0.13782334327697762, 0.165448135137558]     | 0.157017  |
| pid_proxy_positive            | gradient_boosted_trees                | 33900 |  0.00637078  | 0.021599  | [0.014798910190167361, 0.026506330832118664] | 0.0277165 |
| pid_proxy_positive            | traditional_fractional_delay_template | 33900 | -0.00326416  | 0.0227189 | [0.020142537863467348, 0.02516182990868295]  | 0.0310296 |
| pid_proxy_positive            | ridge                                 | 33900 | -0.0266325   | 0.0620879 | [0.04669433971886569, 0.07083110267596458]   | 0.0615872 |
| pid_proxy_positive            | mlp                                   | 33900 |  0.00152543  | 0.0550123 | [0.05139678120613098, 0.05980979591608049]   | 0.0551917 |
| pid_proxy_positive            | 1d_cnn                                | 33900 | -0.006026    | 0.0628247 | [0.05671471095085144, 0.06963723421096803]   | 0.071858  |
| pid_proxy_positive            | waveform_transformer                  | 33900 |  0.0076654   | 0.0467629 | [0.04202635270357132, 0.051682578027248384]  | 0.0497973 |
| pid_proxy_positive            | gated_residual_cnn                    | 33900 |  0.00465843  | 0.0765839 | [0.06498019248247147, 0.08904221653938293]   | 0.0829704 |
| near_knee                     | gradient_boosted_trees                | 30517 |  0.0052363   | 0.0107899 | [0.008507575752425884, 0.0204077398672723]   | 0.0162535 |
| near_knee                     | traditional_fractional_delay_template | 30517 | -0.0028792   | 0.0169398 | [0.01547135547158936, 0.020800353545286965]  | 0.018361  |
| near_knee                     | ridge                                 | 30517 | -0.0139593   | 0.0384246 | [0.03570038423758317, 0.045744486697956194]  | 0.0398873 |
| near_knee                     | mlp                                   | 30517 | -0.00773305  | 0.0430366 | [0.03922638708353045, 0.05040902853012085]   | 0.0396328 |
| near_knee                     | 1d_cnn                                | 30517 | -0.017138    | 0.0498678 | [0.044634410917758945, 0.05944377470016482]  | 0.049897  |
| near_knee                     | waveform_transformer                  | 30517 |  0.0157858   | 0.0400961 | [0.03737707436084747, 0.045064054369926464]  | 0.0339987 |
| near_knee                     | gated_residual_cnn                    | 30517 |  0.0161005   | 0.0581766 | [0.051106431365013125, 0.07104603052139283]  | 0.0593032 |
| hard_saturated                | gradient_boosted_trees                | 22275 |  0.00532791  | 0.0108576 | [0.008276864464005905, 0.02282555975330123]  | 0.0160687 |
| hard_saturated                | traditional_fractional_delay_template | 22275 | -0.00372557  | 0.0175068 | [0.0162925965844663, 0.02150533272763794]    | 0.0187559 |
| hard_saturated                | ridge                                 | 22275 | -0.0192292   | 0.0390855 | [0.03697547273117843, 0.043785759223283635]  | 0.0419031 |
| hard_saturated                | mlp                                   | 22275 | -0.0107485   | 0.0440353 | [0.03962661921977997, 0.05029297405481339]   | 0.0393584 |
| hard_saturated                | 1d_cnn                                | 22275 | -0.0167275   | 0.0499588 | [0.044192948043346406, 0.058804011881351474] | 0.0487956 |
| hard_saturated                | waveform_transformer                  | 22275 |  0.0170968   | 0.0406352 | [0.03769339054822922, 0.045707748770713805]  | 0.0334434 |
| hard_saturated                | gated_residual_cnn                    | 22275 |  0.0101554   | 0.0591979 | [0.05093587243556979, 0.0739837909936905]    | 0.0612117 |
| pileup_multiplicity_ge2       | gradient_boosted_trees                |  9645 | -0.00116973  | 0.0306742 | [0.028510996724541736, 0.03267239785681747]  | 0.0468845 |
| pileup_multiplicity_ge2       | traditional_fractional_delay_template |  9645 |  0.00161315  | 0.0373619 | [0.03472100310750852, 0.04280155880806445]   | 0.0544259 |
| pileup_multiplicity_ge2       | ridge                                 |  9645 | -0.0441291   | 0.0904593 | [0.0884297402572449, 0.09739160504318344]    | 0.0942302 |
| pileup_multiplicity_ge2       | mlp                                   |  9645 |  0.0146727   | 0.0868154 | [0.0803850776553154, 0.09383639132976535]    | 0.0847422 |
| pileup_multiplicity_ge2       | 1d_cnn                                |  9645 |  0.0108042   | 0.102237  | [0.09750345909595495, 0.11385728567838674]   | 0.102961  |
| pileup_multiplicity_ge2       | waveform_transformer                  |  9645 |  0.0162035   | 0.0864138 | [0.08312803268432618, 0.09797947132587433]   | 0.0879626 |
| pileup_multiplicity_ge2       | gated_residual_cnn                    |  9645 | -0.0131084   | 0.150173  | [0.14442817610502245, 0.15957667231559752]   | 0.135092  |
| high_recovery_tail            | gradient_boosted_trees                | 26800 | -0.00304487  | 0.0121035 | [0.011603337824870332, 0.012561561448635142] | 0.0169055 |
| high_recovery_tail            | traditional_fractional_delay_template | 26800 | -0.00663757  | 0.0161467 | [0.014832920160821366, 0.01731824972332783]  | 0.0199761 |
| high_recovery_tail            | ridge                                 | 26800 | -0.0317084   | 0.0600947 | [0.048186962004621456, 0.06644992215364659]  | 0.0573116 |
| high_recovery_tail            | mlp                                   | 26800 | -0.00210533  | 0.0389186 | [0.03377784168720245, 0.043006009638309486]  | 0.0398577 |
| high_recovery_tail            | 1d_cnn                                | 26800 | -0.0182889   | 0.056047  | [0.051929428040981294, 0.060483195543289195] | 0.0708274 |
| high_recovery_tail            | waveform_transformer                  | 26800 | -0.00597763  | 0.0439188 | [0.03985232710838318, 0.051041883826255796]  | 0.0427015 |
| high_recovery_tail            | gated_residual_cnn                    | 26800 | -0.000642568 | 0.0744717 | [0.0640482314825058, 0.09273663520812991]    | 0.0785928 |
| high_pedestal_drift           | gradient_boosted_trees                | 21481 |  0.00328169  | 0.0356057 | [0.024072890494062794, 0.049552400604651624] | 0.0675908 |
| high_pedestal_drift           | traditional_fractional_delay_template | 21481 | -0.00386224  | 0.0443117 | [0.028065083682539148, 0.07695136708250694]  | 0.104107  |
| high_pedestal_drift           | ridge                                 | 21481 | -0.00891976  | 0.070174  | [0.05536874617810068, 0.0839366623700274]    | 0.102528  |
| high_pedestal_drift           | mlp                                   | 21481 |  0.00624329  | 0.0739756 | [0.06103915029764177, 0.08871669322252274]   | 0.0991366 |
| high_pedestal_drift           | 1d_cnn                                | 21481 |  3.42727e-05 | 0.101561  | [0.08182589757442477, 0.12485348600894214]   | 0.13039   |
| high_pedestal_drift           | waveform_transformer                  | 21481 |  0.00914186  | 0.0747699 | [0.058155216574668885, 0.0951744701564313]   | 0.110056  |
| high_pedestal_drift           | gated_residual_cnn                    | 21481 |  0.0160083   | 0.125236  | [0.10326873850822449, 0.14346275538206102]   | 0.146071  |
| large_timing_bias_proxy       | gradient_boosted_trees                | 38386 | -0.00172393  | 0.0156091 | [0.014351872550131003, 0.017329903370757693] | 0.0355144 |
| large_timing_bias_proxy       | traditional_fractional_delay_template | 38386 | -0.00506068  | 0.0203329 | [0.019229978246345678, 0.021675956157116753] | 0.0522587 |
| large_timing_bias_proxy       | ridge                                 | 38386 | -0.017191    | 0.0654037 | [0.059096380518510294, 0.07044678823926336]  | 0.0788272 |
| large_timing_bias_proxy       | mlp                                   | 38386 | -0.00316063  | 0.0490205 | [0.04214667093753815, 0.05468528926372528]   | 0.0618442 |
| large_timing_bias_proxy       | 1d_cnn                                | 38386 | -0.00779927  | 0.07366   | [0.06570091658830643, 0.08058269453048707]   | 0.0940903 |
| large_timing_bias_proxy       | waveform_transformer                  | 38386 | -0.00839451  | 0.0512759 | [0.04657787448167801, 0.059709801733493814]  | 0.0682498 |
| large_timing_bias_proxy       | gated_residual_cnn                    | 38386 |  0.00282615  | 0.100874  | [0.0886367268562317, 0.11816916972398758]    | 0.108248  |

## PID Stability Side Diagnostic

The winner's phase residual score is accompanied by a PID stability diagnostic: held-out AUC=0.4282, AP=0.3453. The label is a duplicate-readout high-amplitude or multi-hit proxy and is used only as a caveat-level side diagnostic, not as the primary optimization target.

## Systematics and Caveats

* The target is duplicate-readout anchored; it measures phase-transfer closure between even and odd readouts, not an absolute beam time.
* Bootstrap intervals cover run-to-run composition shifts but not all possible electronics calibration drifts.
* Saturation phase walk is approximated by an ADC knee, hard saturation count, and late-tail recovery. True front-end hysteresis may include nonlocal baseline memory extending outside the 18-sample window.
* Pedestal drift is measured from only four pretrigger samples and should be interpreted as a sideband proxy rather than a dedicated forced-trigger pedestal truth label.
* Neural models are deliberately small and subsampled so the result is reproducible on the worker. A neural win over the robust fractional-delay template baseline should be read as a context-learning gain on top of engineered phase observables, not as evidence for a deployable timing calibration without a broader electronics systematic campaign.

## Recommendation

The selected winner for `result.json` is `gradient_boosted_trees`. Sub-sample phase transfer should be carried forward only with run-heldout uncertainty inflation for high-recovery-tail, high-pedestal-drift, pile-up, and saturated strata; uncorrected saturated or multi-hit pulses should not be promoted into precision timing, energy-transfer, or PID-stability closure tables.
