# S32a: Pulse-Shape Manifold Alignment for Timing, PID, and Energy Transfer

## Abstract

Ticket `1783886867.733.26397352` tests whether aligned 18-sample B-stave pulse-shape manifolds explain timing, PID, and energy transfer beyond charge-depth summaries when pile-up, saturation, and pedestal strata are held fixed. The selected winner in `result.json` is **mlp**. Its held-out timing res68 is 0.020963 with run-bootstrap 95% CI [0.018973, 0.023774]; energy-transfer res68 is 0.034986 with CI [0.029214, 0.039404]; PID AUC is 0.56253 with CI [0.54658, 0.57955]. The traditional CFD/timewalk plus DeltaE-E lookup comparator has timing res68 0.029813, energy res68 0.04329, and PID AUC 0.60976.

## Raw ROOT Reproduction

The analysis reads raw B-stack ROOT files from `/home/billy/ccb-data/extracted/root/root`. Each `h101/HRDv` vector is reshaped to eight channels by 18 samples. For channel `c`, the pedestal is

\[ b_{ec}=\operatorname{median}\{x_{ec0},x_{ec1},x_{ec2},x_{ec3}\}. \]

B2/B4/B6/B8 even channels are selected when `max_s(x_ecs-b_ec)>1000 ADC`. This direct raw-ROOT reproduction is performed before any model fit.

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

Total reproduced selected pulses: **640737**; registered expectation: **640737**; delta: **0**.

## Estimands

Let `w_ejs` be the baseline-corrected waveform for event `e`, B-stave `j`, and sample `s`; `Q_ej=sum_s max(w_ejs,0)`; and `Q'_ej` the independent odd-channel duplicate charge. The timing/manifold target is

\[ h_e = \operatorname{clip}_{[-4,4]}\left(1-\frac{\sum_j Q_{ej}}{\max(\sum_j Q'_{ej},1)}\right)+0.18\frac{\sum_{j,s\ge9}\max(w_{ejs},0)}{\max(\sum_j Q_{ej},1)}+0.015(\bar{s}_{peak,e}-5). \]

The first term is duplicate-readout charge closure, the second is late-tail/pile-up recovery, and the third is a sample-level timing displacement. The energy-transfer target is the charge-closure component `c_e=clip(1-sum_j Q_ej/max(sum_j Q'_ej,1),-4,4)`. PID transfer uses the duplicate-readout high-amplitude or multi-hit proxy already used by frontier studies; PID probabilities are calibrated from each method's training-run manifold score by a one-dimensional logistic calibrator, then scored on held-out runs.

The main robust scales are

\[ R_{68}(a,b)=Q_{0.68}(|a-b|), \quad \operatorname{ECE}=\sum_k \frac{n_k}{n}|\bar p_k-\bar y_k|. \]

## Methods

The traditional comparator is a pedestal-subtracted CFD/timewalk plus DeltaE-E charge-depth lookup proxy: a Huber-calibrated model on log charge, saturation count, ADC knee count, late recovery fraction, onset sharpness, and pedestal sidebands. It is deliberately bounded to the calibrated target range. The ML/NN panel consists of ridge regression, gradient-boosted trees, a tabular MLP, a 1D-CNN over the four aligned B-stave waveforms, a compact waveform transformer with attention across 18 sample tokens, and a new manifold-gated residual CNN. The new architecture is sensible here because manifold alignment can be locally morphological: convolutional channels are gated by pooled waveform context before the residual head.

## Split and Confidence Intervals

Runs `31--42` and `64` are calibration/training. Runs `44--63` and `65` are held out as complete runs. Confidence intervals resample held-out runs with replacement, preserving run-block correlations, current-family shifts, and event multiplicity structure.

## Head-to-Head Transfer Table

| method                                 |      n |   timing_res68 | timing_res68_ci95    |   shape_mae |   energy_bias | energy_bias_ci95        |   energy_res68 | energy_res68_ci95    |   pid_auc | pid_auc_ci95       |   pid_ece | pid_ece_ci95        |   winner_score |
|:---------------------------------------|-------:|---------------:|:---------------------|------------:|--------------:|:------------------------|---------------:|:---------------------|----------:|:-------------------|----------:|:--------------------|---------------:|
| mlp                                    | 167683 |       0.020963 | [0.018973, 0.023774] |    0.058457 |     0.003812  | [-0.0076672, 0.013552]  |       0.034986 | [0.029214, 0.039404] |   0.56253 | [0.54658, 0.57955] |   0.12329 | [0.091821, 0.17309] |             11 |
| traditional_cfd_timewalk_deltae_lookup | 167683 |       0.029813 | [0.027235, 0.032584] |    0.14068  |     0.0047646 | [-0.00070456, 0.010029] |       0.04329  | [0.038764, 0.048731] |   0.60976 | [0.59162, 0.62659] |   0.12886 | [0.08068, 0.1747]   |             13 |
| compact_waveform_transformer           | 167683 |       0.039846 | [0.034081, 0.048557] |    0.096643 |     0.0047444 | [-0.00065315, 0.013122] |       0.05504  | [0.046922, 0.063109] |   0.57029 | [0.55147, 0.58916] |   0.12128 | [0.085692, 0.16566] |             14 |
| gradient_boosted_trees                 | 167683 |       0.031752 | [0.029522, 0.034715] |    0.078104 |     0.0023886 | [-0.0034248, 0.0072367] |       0.027634 | [0.024841, 0.030812] |   0.54242 | [0.4893, 0.5898]   |   0.12561 | [0.078054, 0.1617]  |             16 |
| manifold_gated_residual_cnn_new        | 167683 |       0.067521 | [0.055303, 0.079277] |    0.11714  |     0.0051947 | [-0.0048302, 0.017468]  |       0.067173 | [0.053365, 0.080118] |   0.58466 | [0.55823, 0.60923] |   0.12266 | [0.082267, 0.1631]  |             18 |
| 1d_cnn                                 | 167683 |       0.056566 | [0.049571, 0.063652] |    0.10649  |     0.0023036 | [-0.0084256, 0.014514]  |       0.046392 | [0.040182, 0.054153] |   0.55453 | [0.54086, 0.56862] |   0.12346 | [0.095196, 0.1718]  |             19 |
| ridge                                  | 167683 |       0.16097  | [0.13519, 0.20032]   |    0.20925  |     0.0079833 | [-0.00091167, 0.018741] |       0.066084 | [0.05642, 0.08055]   |   0.6566  | [0.62236, 0.68756] |   0.16665 | [0.14949, 0.18612]  |             21 |

Lower timing/energy res68 and ECE are better; higher PID AUC is better. `winner_score` is the rank sum of timing res68, energy res68, `1-PID AUC`, and PID ECE.

## Strata and Systematics

| stratum                 | method                                 |      n |   timing_res68 |   energy_res68 |   pid_auc |   pid_ece |
|:------------------------|:---------------------------------------|-------:|---------------:|---------------:|----------:|----------:|
| all_heldout             | mlp                                    | 167683 |       0.020963 |       0.034986 |   0.56253 |  0.12329  |
| all_heldout             | traditional_cfd_timewalk_deltae_lookup | 167683 |       0.029813 |       0.04329  |   0.60976 |  0.12886  |
| all_heldout             | gradient_boosted_trees                 | 167683 |       0.031752 |       0.027634 |   0.54242 |  0.12561  |
| all_heldout             | compact_waveform_transformer           | 167683 |       0.039846 |       0.05504  |   0.57029 |  0.12128  |
| all_heldout             | 1d_cnn                                 | 167683 |       0.056566 |       0.046392 |   0.55453 |  0.12346  |
| all_heldout             | manifold_gated_residual_cnn_new        | 167683 |       0.067521 |       0.067173 |   0.58466 |  0.12266  |
| all_heldout             | ridge                                  | 167683 |       0.16097  |       0.066084 |   0.6566  |  0.16665  |
| hard_saturated          | mlp                                    |  42389 |       0.021158 |       0.031625 |   0.67395 |  0.17046  |
| hard_saturated          | compact_waveform_transformer           |  42389 |       0.028384 |       0.037181 |   0.57864 |  0.17089  |
| hard_saturated          | gradient_boosted_trees                 |  42389 |       0.031018 |       0.033738 |   0.4929  |  0.1717   |
| hard_saturated          | 1d_cnn                                 |  42389 |       0.031704 |       0.038107 |   0.69997 |  0.17137  |
| hard_saturated          | manifold_gated_residual_cnn_new        |  42389 |       0.032103 |       0.034094 |   0.73196 |  0.17018  |
| hard_saturated          | traditional_cfd_timewalk_deltae_lookup |  42389 |       0.034634 |       0.039135 |   0.50998 |  0.17712  |
| hard_saturated          | ridge                                  |  42389 |       0.11225  |       0.045986 |   0.53549 |  0.16567  |
| high_pedestal_drift     | mlp                                    |  41042 |       0.079858 |       0.085594 |   0.56637 |  0.13679  |
| high_pedestal_drift     | gradient_boosted_trees                 |  41042 |       0.12776  |       0.095049 |   0.56065 |  0.13559  |
| high_pedestal_drift     | 1d_cnn                                 |  41042 |       0.13818  |       0.13836  |   0.55413 |  0.12908  |
| high_pedestal_drift     | compact_waveform_transformer           |  41042 |       0.1795   |       0.16114  |   0.56155 |  0.12468  |
| high_pedestal_drift     | manifold_gated_residual_cnn_new        |  41042 |       0.20614  |       0.18857  |   0.58333 |  0.12559  |
| high_pedestal_drift     | traditional_cfd_timewalk_deltae_lookup |  41042 |       0.25473  |       0.24303  |   0.55393 |  0.16827  |
| high_pedestal_drift     | ridge                                  |  41042 |       0.36395  |       0.18792  |   0.60536 |  0.1695   |
| high_recovery_tail      | mlp                                    |  52523 |       0.018557 |       0.037325 |   0.56185 |  0.05881  |
| high_recovery_tail      | traditional_cfd_timewalk_deltae_lookup |  52523 |       0.021226 |       0.042523 |   0.65122 |  0.054574 |
| high_recovery_tail      | compact_waveform_transformer           |  52523 |       0.03239  |       0.054002 |   0.5911  |  0.063641 |
| high_recovery_tail      | gradient_boosted_trees                 |  52523 |       0.03279  |       0.019483 |   0.65676 |  0.052058 |
| high_recovery_tail      | 1d_cnn                                 |  52523 |       0.064129 |       0.053724 |   0.54887 |  0.063355 |
| high_recovery_tail      | manifold_gated_residual_cnn_new        |  52523 |       0.075219 |       0.079336 |   0.54531 |  0.072982 |
| high_recovery_tail      | ridge                                  |  52523 |       0.18108  |       0.085187 |   0.75452 |  0.18577  |
| pileup_multiplicity_ge2 | gradient_boosted_trees                 |  18886 |       0.085245 |       0.081521 | nan       |  0.53635  |
| pileup_multiplicity_ge2 | mlp                                    |  18886 |       0.089355 |       0.11513  | nan       |  0.53148  |
| pileup_multiplicity_ge2 | compact_waveform_transformer           |  18886 |       0.11378  |       0.12591  | nan       |  0.52956  |
| pileup_multiplicity_ge2 | 1d_cnn                                 |  18886 |       0.11427  |       0.11466  | nan       |  0.53567  |
| pileup_multiplicity_ge2 | manifold_gated_residual_cnn_new        |  18886 |       0.12137  |       0.11887  | nan       |  0.52065  |
| pileup_multiplicity_ge2 | traditional_cfd_timewalk_deltae_lookup |  18886 |       0.18138  |       0.14683  | nan       |  0.54347  |
| pileup_multiplicity_ge2 | ridge                                  |  18886 |       0.4798   |       0.20794  | nan       |  0.50804  |

Pile-up is proxied by selected B-stave multiplicity, saturation by ADC knee crossings, and pedestal drift by the pretrigger IQR sideband. These are held fixed in the sense that every method is scored in identical strata after the run-heldout split. The bootstrap covers observed run-to-run variation but not unobserved electronics modes. The PID label is a detector proxy rather than external particle truth. The energy target is duplicate-readout charge closure, not an absolute MeV calibration. Neural models are compact and subsampled for worker reproducibility; a neural win should therefore be interpreted as evidence for waveform-context transfer, not final deployment without a broader electronics systematic campaign.

## Recommendation

`mlp` is the S32a winner. Use it for pulse-shape manifold transfer studies only with run-block uncertainty propagation and explicit high-tail/high-pedestal sideband reporting. The traditional `traditional_cfd_timewalk_deltae_lookup` baseline remains the interpretable fallback when bounded extrapolation is more important than the multimetric rank gain.

## Artifact Index

`result.json`, `REPORT.md`, `transfer_summary.csv`, `strata_summary.csv`, `event_prediction_sample.csv`, `run_counts.csv`, `input_sha256.csv`, `manifest.json`, and `claimed_ticket.txt` are written in this report directory.
