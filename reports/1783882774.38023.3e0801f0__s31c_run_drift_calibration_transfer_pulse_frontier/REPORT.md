# S31c: Run-Drift Calibration Transfer Pulse Frontier

## Abstract

This study reproduces the B-stack selected-pulse number from raw ROOT and benchmarks a strong traditional spline/run-family calibration proxy against ridge, gradient-boosted trees, MLP, 1D-CNN, waveform transformer, and a new gated residual CNN.  The run-heldout winner is **mlp**, with primary held-out residual width 0.014765 and 95% run-bootstrap CI [0.011687, 0.020603].

## Raw ROOT Reproduction

The analysis reads reduced HRD ROOT files directly from `/home/billy/ccb-data/extracted/root/root`.  For each B-stack file, `HRDv` is reshaped to 8 channels by 18 samples.  The pedestal for each channel is the median of samples 0--3; B2, B4, B6, and B8 even channels are selected when their baseline-subtracted amplitude exceeds 1000 ADC.  This exactly matches the registered B-stack selected-pulse anchor.

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

Total selected pulses are **640737**, expected **640737**, delta **0**.

## Statistical Design

Training uses complete calibration runs (`sample_i_calib` and `sample_ii_calib`).  Evaluation uses complete held-out analysis runs (`sample_i_analysis` and `sample_ii_analysis`).  No row from an evaluation run is used for fitting.  Confidence intervals resample held-out runs with replacement, preserving run-level correlations and making the interval sensitive to run-family drift rather than only event counting noise.

The primary metric is

\[ R_{68}(m)=Q_{0.68}\left(|\hat h_{e,m}-h_e|\right), \]

where \(h_e\) is the duplicate-readout anchored pulse-shape/timing-transfer target and \(m\) is the method.  The target is

\[ h_e = \operatorname{clip}_{[-4,4]}\left(1 - \frac{\sum_j Q_{ej}}{\max(\sum_j Q'_{ej},1)}\right) + 0.18\frac{\sum_{j,s\ge9}\max(w_{ejs},0)}{\max(\sum_j Q_{ej},1)} + 0.015(\bar{s}_{peak,e}-5). \]

The first term measures energy-linearity closure against duplicate odd readout, the second term measures late recovery tail and pile-up contamination, and the third term is a peak-sample timing-drift proxy.  Pedestal baseline drift enters through pretrigger median/IQR/slope sidebands, while run labels and event identifiers are excluded from model inputs.

## Methods

The traditional comparator is a robust spline/run-family calibration proxy implemented as a clipped Huber template on log charge, saturation count, knee count, recovery-tail fraction, onset sharpness, and pedestal sidebands.  It represents the conservative calibration-transfer method: explicit pedestal subtraction, charge integration, bounded extrapolation, and low-variance linear correction for saturation and onset.  The learned panel consists of ridge regression, gradient-boosted trees, a tabular MLP, a compact 1D-CNN over the four B-stave waveforms, a sample-token waveform transformer, and a new gated residual CNN.  The gated residual CNN is sensible for S31c because run drift can alter local waveform morphology and the architecture gates convolutional channels by global waveform context before residual regression.

## Head-to-Head Benchmark

| method                       |      n |   timing_residual_res68 | timing_residual_res68_ci95   |   shape_error_mae | shape_error_mae_ci95   |   energy_proxy_bias | energy_proxy_bias_ci95   |   saturation_sensitivity | saturation_sensitivity_ci95   |   pid_leakage_abs_delta | pid_leakage_abs_delta_ci95   |
|:-----------------------------|-------:|------------------------:|:-----------------------------|------------------:|:-----------------------|--------------------:|:-------------------------|-------------------------:|:------------------------------|------------------------:|:-----------------------------|
| mlp                          | 167683 |                0.014765 | [0.011687, 0.020603]         |          0.051026 | [0.039393, 0.063702]   |          0.00039229 | [-0.00053687, 0.0014337] |               -0.0078435 | [-0.013641, -0.0036276]       |               0.014414  | [0.0092719, 0.021733]        |
| traditional_clipped_template | 167683 |                0.028693 | [0.026157, 0.031077]         |          0.14169  | [0.11058, 0.17418]     |          0.00076296 | [-0.00028941, 0.0019524] |                0.0069258 | [0.0048325, 0.0092886]        |               0.13639   | [0.097844, 0.17153]          |
| gradient_boosted_trees       | 167683 |                0.032439 | [0.029946, 0.035563]         |          0.077153 | [0.061945, 0.093238]   |         -0.012313   | [-0.013844, -0.010964]   |               -0.0024324 | [-0.0044007, 0.00078537]      |               0.037006  | [0.029945, 0.04475]          |
| 1d_cnn                       | 167683 |                0.036791 | [0.03228, 0.043417]          |          0.087046 | [0.07089, 0.10349]     |         -0.0032301  | [-0.0098682, 0.0022571]  |               -0.0048828 | [-0.01126, 0.00013359]        |               0.011213  | [0.00086233, 0.021192]       |
| charge_tail_integration      | 167683 |                0.047064 | [0.042578, 0.053219]         |          0.20781  | [0.15541, 0.26438]     |          0.0035979  | [-0.005135, 0.011762]    |                0.0047805 | [-0.0036964, 0.011967]        |               0.085122  | [0.033754, 0.1482]           |
| waveform_transformer         | 167683 |                0.050061 | [0.04399, 0.056793]          |          0.092357 | [0.077884, 0.10825]    |         -0.020318   | [-0.023932, -0.016964]   |               -0.018458  | [-0.022316, -0.013103]        |               0.0099701 | [0.002654, 0.015609]         |
| birks_huber_saturation       | 167683 |                0.050396 | [0.042661, 0.057834]         |          0.23756  | [0.17622, 0.30144]     |         -0.0080883  | [-0.013891, -0.0041538]  |               -0.020279  | [-0.02558, -0.01324]          |               0.11195   | [0.05464, 0.185]             |
| gated_residual_cnn           | 167683 |                0.063782 | [0.056096, 0.072783]         |          0.11552  | [0.094353, 0.13535]    |          0.011387   | [0.0077925, 0.014449]    |               -0.021041  | [-0.028441, -0.012524]        |               0.016236  | [0.0068236, 0.026335]        |
| ridge                        | 167683 |                0.15651  | [0.12853, 0.18877]           |          0.20698  | [0.16811, 0.24008]     |          0.017675   | [0.004144, 0.031756]     |               -0.063583  | [-0.10312, -0.033033]         |               0.036866  | [0.007843, 0.057128]         |

## Drift Effects

| effect                   | contrast                                         |       value | ci95                             | interpretation                                                                         |
|:-------------------------|:-------------------------------------------------|------------:|:---------------------------------|:---------------------------------------------------------------------------------------|
| pulse_shape_residual     | winner held-out res68                            |  0.014765   | [0.011687, 0.020603]             | primary pulse-shape/timing-transfer residual width                                     |
| timing_bias_proxy        | winner median residual                           |  0.00039229 | [-0.00053687, 0.0014337]         | signed residual on charge-loss plus peak-sample proxy scale                            |
| saturation_knee          | saturated minus unsaturated res68                | -0.0078435  | [-0.013641, -0.0036276]          | extra residual width when any stave crosses the ADC saturation knee                    |
| pid_stability            | absolute PID-proxy residual shift                |  0.014414   | [0.0092719, 0.021733]            | residual dependence on duplicate-readout high-amplitude or multi-hit PID proxy         |
| ml_gain_over_traditional | mlp minus traditional_clipped_template res68     | -0.013929   | not paired; see method table CIs | negative values favor the S31c winner over the traditional calibration baseline        |
| pile_up_rate             | pileup_multiplicity_ge2 minus all held-out res68 |  0.058575   | [0.0711, 0.078148]               | stratum-local run-bootstrap CI; contrast uses all-held-out point estimate as reference |
| pedestal_baseline        | high_pedestal_drift minus all held-out res68     |  0.054663   | [0.032373, 0.11366]              | stratum-local run-bootstrap CI; contrast uses all-held-out point estimate as reference |
| energy_linearity         | high_recovery_tail minus all held-out res68      |  0.001854   | [0.012708, 0.020891]             | stratum-local run-bootstrap CI; contrast uses all-held-out point estimate as reference |
| timing_drift_tail        | large_timing_bias_proxy minus all held-out res68 |  0.0080266  | [0.019083, 0.027087]             | stratum-local run-bootstrap CI; contrast uses all-held-out point estimate as reference |

## Held-Out Run Strata

| stratum                 | method                       |      n |        bias |     res68 | res68_ci95            |      mae |
|:------------------------|:-----------------------------|-------:|------------:|----------:|:----------------------|---------:|
| all_heldout             | mlp                          | 167683 |  0.00039229 | 0.014765  | [0.011339, 0.019939]  | 0.051026 |
| all_heldout             | traditional_clipped_template | 167683 |  0.00076296 | 0.028693  | [0.026171, 0.031241]  | 0.14169  |
| all_heldout             | gradient_boosted_trees       | 167683 | -0.012313   | 0.032439  | [0.029781, 0.035564]  | 0.077153 |
| all_heldout             | 1d_cnn                       | 167683 | -0.0032301  | 0.036791  | [0.032339, 0.042749]  | 0.087046 |
| all_heldout             | waveform_transformer         | 167683 | -0.020318   | 0.050061  | [0.043514, 0.057111]  | 0.092357 |
| all_heldout             | gated_residual_cnn           | 167683 |  0.011387   | 0.063782  | [0.055709, 0.072761]  | 0.11552  |
| near_knee               | mlp                          |  58021 | -0.0021625  | 0.0092969 | [0.0086116, 0.010532] | 0.016622 |
| near_knee               | traditional_clipped_template |  58021 |  0.0010475  | 0.031233  | [0.029419, 0.033888]  | 0.055788 |
| near_knee               | gradient_boosted_trees       |  58021 | -0.017173   | 0.029815  | [0.027516, 0.034055]  | 0.036771 |
| near_knee               | 1d_cnn                       |  58021 |  0.0091956  | 0.029743  | [0.027337, 0.034586]  | 0.036682 |
| near_knee               | waveform_transformer         |  58021 | -0.014406   | 0.035651  | [0.032441, 0.041878]  | 0.046215 |
| near_knee               | gated_residual_cnn           |  58021 |  0.020444   | 0.047829  | [0.044867, 0.052849]  | 0.052318 |
| hard_saturated          | mlp                          |  42254 | -0.0024122  | 0.010166  | [0.009365, 0.011756]  | 0.016492 |
| hard_saturated          | traditional_clipped_template |  42254 |  0.00083372 | 0.033494  | [0.031186, 0.036105]  | 0.054183 |
| hard_saturated          | gradient_boosted_trees       |  42254 | -0.021126   | 0.030966  | [0.029293, 0.034088]  | 0.037798 |
| hard_saturated          | 1d_cnn                       |  42254 |  0.013795   | 0.033622  | [0.031474, 0.037988]  | 0.037867 |
| hard_saturated          | waveform_transformer         |  42254 | -0.014794   | 0.03692   | [0.033679, 0.042075]  | 0.044372 |
| hard_saturated          | gated_residual_cnn           |  42254 |  0.023873   | 0.050129  | [0.047139, 0.054183]  | 0.05061  |
| pileup_multiplicity_ge2 | mlp                          |  18979 | -0.031411   | 0.073339  | [0.0711, 0.078148]    | 0.10689  |
| pileup_multiplicity_ge2 | traditional_clipped_template |  18979 | -0.014253   | 0.18645   | [0.15203, 0.22355]    | 0.27534  |
| pileup_multiplicity_ge2 | gradient_boosted_trees       |  18979 | -0.026789   | 0.082813  | [0.068267, 0.10987]   | 0.16136  |
| pileup_multiplicity_ge2 | 1d_cnn                       |  18979 | -0.033075   | 0.10901   | [0.1052, 0.11137]     | 0.13397  |
| pileup_multiplicity_ge2 | waveform_transformer         |  18979 |  0.018211   | 0.08094   | [0.075343, 0.091864]  | 0.13298  |
| pileup_multiplicity_ge2 | gated_residual_cnn           |  18979 |  0.023538   | 0.12744   | [0.12316, 0.13863]    | 0.18355  |
| high_recovery_tail      | mlp                          |  52336 |  0.0010906  | 0.016619  | [0.012708, 0.020891]  | 0.020565 |
| high_recovery_tail      | traditional_clipped_template |  52336 |  0.0072722  | 0.020142  | [0.01958, 0.020814]   | 0.037228 |
| high_recovery_tail      | gradient_boosted_trees       |  52336 | -0.02623    | 0.034226  | [0.033225, 0.035261]  | 0.041632 |
| high_recovery_tail      | 1d_cnn                       |  52336 | -0.017961   | 0.036768  | [0.032101, 0.041811]  | 0.042563 |
| high_recovery_tail      | waveform_transformer         |  52336 | -0.026223   | 0.04781   | [0.045065, 0.050251]  | 0.048816 |
| high_recovery_tail      | gated_residual_cnn           |  52336 |  0.014556   | 0.063942  | [0.056695, 0.070266]  | 0.061799 |
| high_pedestal_drift     | mlp                          |  41524 | -0.00088614 | 0.069428  | [0.032373, 0.11366]   | 0.15866  |
| high_pedestal_drift     | traditional_clipped_template |  41524 |  0.0047839  | 0.26108   | [0.089167, 0.48974]   | 0.45908  |
| high_pedestal_drift     | gradient_boosted_trees       |  41524 | -0.012588   | 0.12641   | [0.053554, 0.23915]   | 0.21266  |
| high_pedestal_drift     | 1d_cnn                       |  41524 |  0.0035208  | 0.13309   | [0.064002, 0.2152]    | 0.2479   |
| high_pedestal_drift     | waveform_transformer         |  41524 | -0.012957   | 0.15004   | [0.079926, 0.22212]   | 0.23375  |
| high_pedestal_drift     | gated_residual_cnn           |  41524 |  0.005742   | 0.20476   | [0.10358, 0.30549]    | 0.29429  |
| large_timing_bias_proxy | mlp                          |  74184 |  0.0031867  | 0.022791  | [0.019083, 0.027087]  | 0.068958 |
| large_timing_bias_proxy | traditional_clipped_template |  74184 | -0.00018793 | 0.024144  | [0.022557, 0.026266]  | 0.17231  |
| large_timing_bias_proxy | gradient_boosted_trees       |  74184 | -0.020537   | 0.036302  | [0.034491, 0.038815]  | 0.088067 |
| large_timing_bias_proxy | 1d_cnn                       |  74184 | -0.016926   | 0.045149  | [0.039424, 0.051057]  | 0.11245  |
| large_timing_bias_proxy | waveform_transformer         |  74184 | -0.023513   | 0.054025  | [0.049585, 0.058301]  | 0.10258  |
| large_timing_bias_proxy | gated_residual_cnn           |  74184 |  0.0096846  | 0.071165  | [0.063833, 0.077841]  | 0.1387   |

## Systematics

* The run-block bootstrap covers observed run-family composition changes but not unseen electronics settings outside runs 31--65.
* Pedestal baseline drift is inferred from four pretrigger samples, so slow memory outside the 18-sample acquisition window remains a caveat.
* Pile-up rate is represented by selected-pulse multiplicity and recovery-tail sidebands, not by an external beam-current truth counter.
* Energy linearity is duplicate-readout closure after clipping pathological near-zero duplicate denominators; it is not an absolute calorimetric calibration.
* PID stability is a side diagnostic based on high-amplitude/multi-hit duplicate-readout proxies and is not used for model selection.
* Neural methods are compact and subsampled to keep the study reproducible on the worker; a neural win should be interpreted as evidence of waveform-context transfer, not as a final production calibration without additional electronics validation.

## Caveats and Recommendation

The selected S31c winner is `mlp`.  It should be used as the preferred analysis model for run-drift pulse-shape transfer only with run-family held-out uncertainty propagation.  The traditional clipped calibration remains the conservative fallback where bounded extrapolation and interpretability dominate over small residual-width gains.

## Artifact Index

`result.json`, `manifest.json`, `method_summary.csv`, `strata_summary.csv`, `run_drift_effects.csv`, `run_counts.csv`, `input_sha256.csv`, and `claimed_ticket.txt` are in this report directory.
