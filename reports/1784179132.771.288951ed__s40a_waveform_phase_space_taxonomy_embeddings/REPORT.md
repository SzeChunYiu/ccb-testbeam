# S40a Waveform Phase-Space Pulse-Shape Taxonomy Versus Sequence Embeddings

## Abstract

Ticket `1784179132.771.288951ed` asks for a pulse-shape taxonomy that separates
rise curvature, late tail, undershoot, and width changes from timing, pedestal,
pile-up, saturation, energy, and PID proxies.  This study rebuilds the
registered selected-pulse count directly from raw ROOT, samples B-stack
waveforms by run/stave, defines an interpretable four-axis phase-space
taxonomy, and compares a strong traditional PCA/CFD/template-clustering
baseline against ridge, gradient-boosted trees, MLP, 1D-CNN, a
contrastive-style sequence encoder, a compact transformer, and a new
residual-gated shape CNN.

The result written to `result.json` names **`gradient_boosted_trees`** as the winner by
held-out run-bootstrap `selection_score = macro_F1 - 0.15 max_proxy_NMI`.
It obtains macro-F1 `0.985`
`[0.9821, 0.9872]` and maximum
proxy coupling `0.1768`
`[0.1505, 0.2223]`.

## Raw ROOT Reproduction

Input files are `data/root/root/hrdb_run_*.root`.  The branch
`h101/HRDv` is reshaped as `(8, 18)`.  For each B-stack channel `c`,

`b_c = median(x_c[0], x_c[1], x_c[2], x_c[3])`,

`A_c = max_t (x_c(t) - b_c)`.

The reproduced count is

`N = sum_e sum_{c in B2,B4,B6,B8} 1[A_{e,c} > 1000 ADC]`.

| group | events_total | selected_pulses | expected_selected_pulses | delta | pass |
| --- | --- | --- | --- | --- | --- |
| sample_i_calib | 409815 | 248745 | 248745 | 0 | True |
| sample_i_analysis | 388879 | 252266 | 252266 | 0 | True |
| sample_ii_calib | 35943 | 14630 | 14630 | 0 | True |
| sample_ii_analysis | 262091 | 125096 | 125096 | 0 | True |
| all_registered_groups | 1096728 | 640737 | 640737 | 0 | True |

The all-group reproduced count is **640737**.
Input hashes are stored in `input_sha256.csv`; first rows:

| run | path | bytes | sha256 |
| --- | --- | --- | --- |
| 31 | data/root/root/hrdb_run_0031.root | 11638901 | 9921aa75c062d0b8994573299a201cbe2725673319fdf1b8cffb711fb9adcea7 |
| 32 | data/root/root/hrdb_run_0032.root | 12157812 | 649983bf173352b638bf57c099dc92741b70483feba8981172b26319fc9047ff |
| 33 | data/root/root/hrdb_run_0033.root | 16781109 | 1b8f1dcda0e53b8c7b702f00801555f6d317a87bed8efef6d228b49146dbf973 |
| 34 | data/root/root/hrdb_run_0034.root | 11697434 | 69ef29a8d879aaa908ab4a076c82b3d10ac7b3e2622e491e017eb368290bdf51 |
| 35 | data/root/root/hrdb_run_0035.root | 7793651 | a6e08e36ab103e76b53741b55ea7cd3e648d1800508d6144b96ab80820e156ea |
| 36 | data/root/root/hrdb_run_0036.root | 6167361 | 1160bee157e233eb63421597b415f1aaf4dea2c1e7e4a804836c487704852fee |
| 37 | data/root/root/hrdb_run_0037.root | 14369738 | 6bcebe85c0b1e38a42cc326cbcdc2107ccaee877372bffd537ce71baa1b22fd3 |
| 39 | data/root/root/hrdb_run_0039.root | 8625385 | b875c8d45a62a39933d7d4648518040a645629e6fb60c9111a7d05c4d982c568 |

## Taxonomy Estimand

For each baseline-subtracted waveform `y_t = x_t - b`, we normalize
`u_t = y_t / max(A, 1)`.  The four phase-space coordinates are

`z_rise = robust_z[(u_6 - u_4) - 0.5 (u_8 - u_2)]`,

`z_tail = robust_z[sum_{t>=12} y_t / sum_t max(y_t, 0)]`,

`z_under = robust_z[-min_{t>=10} u_t]`,

`z_width = robust_z[t_0.80 - t_0.20]`.

Robust centering and scaling use training runs only.  The taxonomy label is
`argmax_a |z_a|`, giving one dominant interpretable shape axis per pulse.  This
is deliberately a waveform phase-space label, not a PID, energy, or timing
label.

| taxonomy_label | n | axis_z_rise_curvature_median | axis_z_late_tail_median | axis_z_undershoot_median | axis_z_width_change_median |
| --- | --- | --- | --- | --- | --- |
| late_tail | 3586 | -0.02577 | 1.926 | 0.8591 | 0.1136 |
| rise_curvature | 6993 | 1.081 | -0.01957 | -0.464 | -0.1372 |
| undershoot | 4984 | -0.08206 | 0.01369 | -0.9805 | -0.1937 |
| width_change | 5040 | 0.1103 | -0.1822 | 0.2505 | 1.155 |

Coupling of the taxonomy itself to nuisance/proxy axes:

| axis | nmi_with_taxonomy |
| --- | --- |
| pileup_separation_bin | 0.2051 |
| energy_bin | 0.1513 |
| pid_sideband | 0.04368 |
| stave | 0.03737 |
| run | 0.0107 |
| pedestal_drift_bin | 0.009875 |
| saturation_onset_bin | 0.008535 |

## Split, Uncertainty, and Controls

The split unit is the run.  Held-out runs are `[42, 50, 57, 58, 60, 62, 64, 65]`.
Sampled rows are:

| split | rows |
| --- | --- |
| heldout | 5466 |
| train | 15137 |

Confidence intervals use `500` percentile
bootstrap replicates resampling held-out runs with replacement:

`CI_95(theta) = [q_0.025(theta_b^*), q_0.975(theta_b^*)]`.

No method receives run number, event number, or split indicator.  The nuisance
audit reports normalized mutual information between predicted shape label and
energy, pedestal, pile-up, saturation, and duplicate-readout PID-sideband
proxies; the primary selection score penalizes the largest of these couplings.

## Methods

| method | family | description |
| --- | --- | --- |
| traditional_pca_cfd_dtw_cluster | traditional | normalized-template PCA with CFD/width/tail features and k-means cluster-to-label calibration |
| ridge | linear ML | standardized ridge classifier on engineered pulse-shape and normalized waveform features |
| gradient_boosted_trees | tree ML | histogram gradient-boosted classifier on the same leakage-controlled feature matrix |
| mlp | neural tabular | two-layer perceptron over engineered phase-space features |
| 1d_cnn | neural waveform | compact convolutional classifier over the 18-sample normalized waveform |
| contrastive_sequence_encoder | self-supervised proxy | PCA encoder of waveform, derivative, and smoothing-residual augmentations with ridge head |
| compact_transformer | sequence NN | single-layer sample-attention encoder with position input and absolute-amplitude pooling |
| residual_gated_shape_cnn_new | new architecture | gated CNN using waveform residual channels to emphasize shape deviations from local baseline |

## Primary Held-Out Results

| method | n | macro_f1 | macro_f1_ci_low | macro_f1_ci_high | accuracy | balanced_accuracy | adjusted_rand | proxy_coupling_max_nmi | selection_score | selection_score_ci_low | selection_score_ci_high |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| gradient_boosted_trees | 5466 | 0.985 | 0.9821 | 0.9872 | 0.9835 | 0.9851 | 0.9531 | 0.1768 | 0.9585 | 0.9526 | 0.9622 |
| mlp | 5466 | 0.9732 | 0.9703 | 0.976 | 0.9715 | 0.9726 | 0.9207 | 0.1739 | 0.9471 | 0.9396 | 0.951 |
| residual_gated_shape_cnn_new | 5466 | 0.7465 | 0.7131 | 0.7738 | 0.725 | 0.7487 | 0.4145 | 0.2785 | 0.7047 | 0.6748 | 0.7294 |
| 1d_cnn | 5466 | 0.6705 | 0.6446 | 0.6939 | 0.6497 | 0.6734 | 0.2802 | 0.2753 | 0.6292 | 0.6055 | 0.6517 |
| contrastive_sequence_encoder | 5466 | 0.6438 | 0.6108 | 0.6689 | 0.6098 | 0.6487 | 0.2383 | 0.272 | 0.6031 | 0.5679 | 0.6274 |
| ridge | 5466 | 0.4943 | 0.4562 | 0.5243 | 0.5276 | 0.5563 | 0.2063 | 0.1155 | 0.477 | 0.4407 | 0.5044 |
| traditional_pca_cfd_dtw_cluster | 5466 | 0.4514 | 0.4421 | 0.4611 | 0.5203 | 0.5457 | 0.2261 | 0.2109 | 0.4198 | 0.4056 | 0.4297 |
| compact_transformer | 5466 | 0.4013 | 0.3797 | 0.4215 | 0.4874 | 0.5139 | 0.2084 | 0.2071 | 0.3703 | 0.3556 | 0.3845 |

## Run-Heldout Stability

| method | run | n | macro_f1 | accuracy | balanced_accuracy | adjusted_rand | proxy_coupling_max_nmi |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 1d_cnn | 42 | 657 | 0.6209 | 0.6514 | 0.6456 | 0.3252 | 0.3398 |
| 1d_cnn | 50 | 680 | 0.6607 | 0.7103 | 0.6658 | 0.4228 | 0.3993 |
| 1d_cnn | 57 | 670 | 0.6824 | 0.7075 | 0.6966 | 0.4307 | 0.3116 |
| 1d_cnn | 58 | 654 | 0.6945 | 0.7049 | 0.6893 | 0.3893 | 0.3122 |
| 1d_cnn | 60 | 720 | 0.5966 | 0.5486 | 0.6184 | 0.1405 | 0.2242 |
| 1d_cnn | 62 | 720 | 0.6321 | 0.5792 | 0.6183 | 0.1559 | 0.1921 |
| 1d_cnn | 64 | 720 | 0.6844 | 0.6389 | 0.6875 | 0.2244 | 0.2357 |
| 1d_cnn | 65 | 645 | 0.6958 | 0.6713 | 0.707 | 0.3005 | 0.2991 |
| compact_transformer | 42 | 657 | 0.4066 | 0.5266 | 0.5183 | 0.2467 | 0.3393 |
| compact_transformer | 50 | 680 | 0.4247 | 0.5824 | 0.5158 | 0.3215 | 0.3545 |
| compact_transformer | 57 | 670 | 0.4432 | 0.5672 | 0.5282 | 0.3214 | 0.29 |
| compact_transformer | 58 | 654 | 0.4325 | 0.5612 | 0.5207 | 0.2976 | 0.2545 |
| compact_transformer | 60 | 720 | 0.339 | 0.4111 | 0.4948 | 0.0755 | 0.12 |
| compact_transformer | 62 | 720 | 0.3703 | 0.4278 | 0.4855 | 0.103 | 0.1035 |
| compact_transformer | 64 | 720 | 0.3675 | 0.4097 | 0.5064 | 0.154 | 0.1256 |
| compact_transformer | 65 | 645 | 0.3748 | 0.4279 | 0.5073 | 0.2334 | 0.1709 |
| contrastive_sequence_encoder | 42 | 657 | 0.6352 | 0.6104 | 0.6416 | 0.2671 | 0.3097 |
| contrastive_sequence_encoder | 50 | 680 | 0.6659 | 0.6721 | 0.6684 | 0.3803 | 0.3521 |
| contrastive_sequence_encoder | 57 | 670 | 0.6756 | 0.6642 | 0.6792 | 0.3413 | 0.324 |
| contrastive_sequence_encoder | 58 | 654 | 0.6829 | 0.6743 | 0.6893 | 0.353 | 0.3167 |
| contrastive_sequence_encoder | 60 | 720 | 0.5559 | 0.4931 | 0.5756 | 0.1122 | 0.3343 |
| contrastive_sequence_encoder | 62 | 720 | 0.5745 | 0.5264 | 0.5719 | 0.1284 | 0.3576 |
| contrastive_sequence_encoder | 64 | 720 | 0.6272 | 0.5972 | 0.6267 | 0.1957 | 0.3056 |
| contrastive_sequence_encoder | 65 | 645 | 0.6654 | 0.6589 | 0.6625 | 0.305 | 0.23 |
| gradient_boosted_trees | 42 | 657 | 0.9883 | 0.9878 | 0.9887 | 0.9661 | 0.2108 |
| gradient_boosted_trees | 50 | 680 | 0.9886 | 0.9882 | 0.9872 | 0.967 | 0.2856 |
| gradient_boosted_trees | 57 | 670 | 0.9863 | 0.9866 | 0.9866 | 0.9651 | 0.2202 |
| gradient_boosted_trees | 58 | 654 | 0.9813 | 0.9801 | 0.9809 | 0.9438 | 0.2358 |
| gradient_boosted_trees | 60 | 720 | 0.9875 | 0.9847 | 0.9875 | 0.9558 | 0.1686 |
| gradient_boosted_trees | 62 | 720 | 0.9767 | 0.9764 | 0.9768 | 0.9336 | 0.1603 |
| gradient_boosted_trees | 64 | 720 | 0.9866 | 0.9847 | 0.986 | 0.9569 | 0.1799 |
| gradient_boosted_trees | 65 | 645 | 0.9802 | 0.9798 | 0.9793 | 0.9464 | 0.176 |
| mlp | 42 | 657 | 0.9758 | 0.9741 | 0.9746 | 0.9274 | 0.2101 |
| mlp | 50 | 680 | 0.973 | 0.9721 | 0.9727 | 0.923 | 0.2725 |
| mlp | 57 | 670 | 0.968 | 0.9687 | 0.9676 | 0.9195 | 0.2272 |
| mlp | 58 | 654 | 0.9707 | 0.9694 | 0.9694 | 0.9156 | 0.2354 |
| mlp | 60 | 720 | 0.9657 | 0.9708 | 0.961 | 0.9215 | 0.1767 |
| mlp | 62 | 720 | 0.9691 | 0.9722 | 0.9735 | 0.9249 | 0.1596 |
| mlp | 64 | 720 | 0.982 | 0.9778 | 0.9806 | 0.9332 | 0.1823 |
| mlp | 65 | 645 | 0.9659 | 0.9659 | 0.9666 | 0.9122 | 0.179 |
| residual_gated_shape_cnn_new | 42 | 657 | 0.758 | 0.7397 | 0.7608 | 0.439 | 0.3296 |
| residual_gated_shape_cnn_new | 50 | 680 | 0.7597 | 0.7662 | 0.7595 | 0.5232 | 0.3849 |
| residual_gated_shape_cnn_new | 57 | 670 | 0.7867 | 0.7776 | 0.7883 | 0.5062 | 0.3179 |
| residual_gated_shape_cnn_new | 58 | 654 | 0.7745 | 0.7676 | 0.7735 | 0.4943 | 0.3348 |
| residual_gated_shape_cnn_new | 60 | 720 | 0.655 | 0.6042 | 0.6821 | 0.2451 | 0.2357 |
| residual_gated_shape_cnn_new | 62 | 720 | 0.6841 | 0.6486 | 0.6756 | 0.3023 | 0.2089 |
| residual_gated_shape_cnn_new | 64 | 720 | 0.7589 | 0.7486 | 0.753 | 0.4551 | 0.2518 |
| residual_gated_shape_cnn_new | 65 | 645 | 0.7618 | 0.7628 | 0.7559 | 0.4936 | 0.2685 |
| ridge | 42 | 657 | 0.4195 | 0.4338 | 0.481 | 0.1032 | 0.09608 |
| ridge | 50 | 680 | 0.3866 | 0.4074 | 0.4598 | 0.07965 | 0.1009 |
| ridge | 57 | 670 | 0.4649 | 0.4776 | 0.5091 | 0.1334 | 0.09636 |
| ridge | 58 | 654 | 0.534 | 0.5474 | 0.585 | 0.1994 | 0.1386 |
| ridge | 60 | 720 | 0.5158 | 0.5931 | 0.6278 | 0.3089 | 0.1354 |
| ridge | 62 | 720 | 0.5067 | 0.5722 | 0.617 | 0.2522 | 0.1512 |
| ridge | 64 | 720 | 0.5262 | 0.6097 | 0.609 | 0.3535 | 0.1464 |
| ridge | 65 | 645 | 0.4871 | 0.5674 | 0.5313 | 0.2891 | 0.1475 |
| traditional_pca_cfd_dtw_cluster | 42 | 657 | 0.4446 | 0.5556 | 0.545 | 0.2584 | 0.3419 |
| traditional_pca_cfd_dtw_cluster | 50 | 680 | 0.4322 | 0.5941 | 0.5264 | 0.3139 | 0.3706 |
| traditional_pca_cfd_dtw_cluster | 57 | 670 | 0.4821 | 0.5955 | 0.5606 | 0.3374 | 0.2966 |
| traditional_pca_cfd_dtw_cluster | 58 | 654 | 0.4622 | 0.578 | 0.5418 | 0.3052 | 0.2585 |
| traditional_pca_cfd_dtw_cluster | 60 | 720 | 0.4288 | 0.4694 | 0.5302 | 0.09261 | 0.2142 |
| traditional_pca_cfd_dtw_cluster | 62 | 720 | 0.4468 | 0.4722 | 0.5141 | 0.1292 | 0.2241 |
| traditional_pca_cfd_dtw_cluster | 64 | 720 | 0.4415 | 0.4528 | 0.5485 | 0.1878 | 0.2095 |
| traditional_pca_cfd_dtw_cluster | 65 | 645 | 0.4333 | 0.4558 | 0.5416 | 0.249 | 0.1744 |

## Proxy-Coupling Systematics

Lower NMI means the predicted shape taxonomy is less reducible to a nuisance
proxy.

| proxy_axis | method | nmi |
| --- | --- | --- |
| energy_bin | residual_gated_shape_cnn_new | 0.2047 |
| energy_bin | mlp | 0.1556 |
| energy_bin | gradient_boosted_trees | 0.151 |
| energy_bin | ridge | 0.1155 |
| energy_bin | 1d_cnn | 0.1006 |
| energy_bin | contrastive_sequence_encoder | 0.06199 |
| energy_bin | traditional_pca_cfd_dtw_cluster | 0.05594 |
| energy_bin | compact_transformer | 0.02708 |
| pedestal_drift_bin | traditional_pca_cfd_dtw_cluster | 0.08877 |
| pedestal_drift_bin | contrastive_sequence_encoder | 0.08236 |
| pedestal_drift_bin | residual_gated_shape_cnn_new | 0.04158 |
| pedestal_drift_bin | 1d_cnn | 0.03778 |
| pedestal_drift_bin | compact_transformer | 0.0283 |
| pedestal_drift_bin | mlp | 0.01183 |
| pedestal_drift_bin | gradient_boosted_trees | 0.01171 |
| pedestal_drift_bin | ridge | 0.007428 |
| pid_sideband | contrastive_sequence_encoder | 0.2251 |
| pid_sideband | traditional_pca_cfd_dtw_cluster | 0.1842 |
| pid_sideband | residual_gated_shape_cnn_new | 0.1176 |
| pid_sideband | 1d_cnn | 0.09968 |
| pid_sideband | compact_transformer | 0.0646 |
| pid_sideband | mlp | 0.05077 |
| pid_sideband | gradient_boosted_trees | 0.05034 |
| pid_sideband | ridge | 0.03378 |
| pileup_separation_bin | residual_gated_shape_cnn_new | 0.2785 |
| pileup_separation_bin | 1d_cnn | 0.2753 |
| pileup_separation_bin | contrastive_sequence_encoder | 0.272 |
| pileup_separation_bin | traditional_pca_cfd_dtw_cluster | 0.2109 |
| pileup_separation_bin | compact_transformer | 0.2071 |
| pileup_separation_bin | gradient_boosted_trees | 0.1768 |
| pileup_separation_bin | mlp | 0.1739 |
| pileup_separation_bin | ridge | 0.05507 |
| saturation_onset_bin | compact_transformer | 0.02403 |
| saturation_onset_bin | ridge | 0.0195 |
| saturation_onset_bin | traditional_pca_cfd_dtw_cluster | 0.01947 |
| saturation_onset_bin | contrastive_sequence_encoder | 0.01377 |
| saturation_onset_bin | 1d_cnn | 0.01178 |
| saturation_onset_bin | residual_gated_shape_cnn_new | 0.01155 |
| saturation_onset_bin | gradient_boosted_trees | 0.007461 |
| saturation_onset_bin | mlp | 0.007305 |

## Confusion Structure

| method | truth_label | pred_label | count |
| --- | --- | --- | --- |
| 1d_cnn | rise_curvature | rise_curvature | 1567 |
| 1d_cnn | rise_curvature | late_tail | 0 |
| 1d_cnn | rise_curvature | undershoot | 78 |
| 1d_cnn | rise_curvature | width_change | 137 |
| 1d_cnn | late_tail | rise_curvature | 33 |
| 1d_cnn | late_tail | late_tail | 744 |
| 1d_cnn | late_tail | undershoot | 2 |
| 1d_cnn | late_tail | width_change | 0 |
| 1d_cnn | undershoot | rise_curvature | 678 |
| 1d_cnn | undershoot | late_tail | 26 |
| 1d_cnn | undershoot | undershoot | 647 |
| 1d_cnn | undershoot | width_change | 14 |
| 1d_cnn | width_change | rise_curvature | 799 |
| 1d_cnn | width_change | late_tail | 62 |
| 1d_cnn | width_change | undershoot | 86 |
| 1d_cnn | width_change | width_change | 593 |
| compact_transformer | rise_curvature | rise_curvature | 1779 |
| compact_transformer | rise_curvature | late_tail | 0 |
| compact_transformer | rise_curvature | undershoot | 3 |
| compact_transformer | rise_curvature | width_change | 0 |
| compact_transformer | late_tail | rise_curvature | 33 |
| compact_transformer | late_tail | late_tail | 746 |
| compact_transformer | late_tail | undershoot | 0 |
| compact_transformer | late_tail | width_change | 0 |
| compact_transformer | undershoot | rise_curvature | 951 |
| compact_transformer | undershoot | late_tail | 209 |
| compact_transformer | undershoot | undershoot | 115 |
| compact_transformer | undershoot | width_change | 90 |
| compact_transformer | width_change | rise_curvature | 1441 |
| compact_transformer | width_change | late_tail | 69 |
| compact_transformer | width_change | undershoot | 6 |
| compact_transformer | width_change | width_change | 24 |
| contrastive_sequence_encoder | rise_curvature | rise_curvature | 892 |
| contrastive_sequence_encoder | rise_curvature | late_tail | 1 |
| contrastive_sequence_encoder | rise_curvature | undershoot | 305 |
| contrastive_sequence_encoder | rise_curvature | width_change | 584 |
| contrastive_sequence_encoder | late_tail | rise_curvature | 32 |
| contrastive_sequence_encoder | late_tail | late_tail | 718 |
| contrastive_sequence_encoder | late_tail | undershoot | 23 |
| contrastive_sequence_encoder | late_tail | width_change | 6 |
| contrastive_sequence_encoder | undershoot | rise_curvature | 223 |
| contrastive_sequence_encoder | undershoot | late_tail | 8 |
| contrastive_sequence_encoder | undershoot | undershoot | 643 |
| contrastive_sequence_encoder | undershoot | width_change | 491 |
| contrastive_sequence_encoder | width_change | rise_curvature | 251 |
| contrastive_sequence_encoder | width_change | late_tail | 70 |
| contrastive_sequence_encoder | width_change | undershoot | 139 |
| contrastive_sequence_encoder | width_change | width_change | 1080 |
| gradient_boosted_trees | rise_curvature | rise_curvature | 1757 |
| gradient_boosted_trees | rise_curvature | late_tail | 1 |
| gradient_boosted_trees | rise_curvature | undershoot | 11 |
| gradient_boosted_trees | rise_curvature | width_change | 13 |
| gradient_boosted_trees | late_tail | rise_curvature | 0 |
| gradient_boosted_trees | late_tail | late_tail | 778 |
| gradient_boosted_trees | late_tail | undershoot | 0 |
| gradient_boosted_trees | late_tail | width_change | 1 |
| gradient_boosted_trees | undershoot | rise_curvature | 22 |
| gradient_boosted_trees | undershoot | late_tail | 0 |
| gradient_boosted_trees | undershoot | undershoot | 1333 |
| gradient_boosted_trees | undershoot | width_change | 10 |
| gradient_boosted_trees | width_change | rise_curvature | 17 |
| gradient_boosted_trees | width_change | late_tail | 4 |
| gradient_boosted_trees | width_change | undershoot | 11 |
| gradient_boosted_trees | width_change | width_change | 1508 |
| mlp | rise_curvature | rise_curvature | 1745 |
| mlp | rise_curvature | late_tail | 4 |
| mlp | rise_curvature | undershoot | 15 |
| mlp | rise_curvature | width_change | 18 |
| mlp | late_tail | rise_curvature | 0 |
| mlp | late_tail | late_tail | 768 |
| mlp | late_tail | undershoot | 2 |
| mlp | late_tail | width_change | 9 |
| mlp | undershoot | rise_curvature | 41 |
| mlp | undershoot | late_tail | 2 |
| mlp | undershoot | undershoot | 1310 |
| mlp | undershoot | width_change | 12 |
| mlp | width_change | rise_curvature | 33 |
| mlp | width_change | late_tail | 5 |
| mlp | width_change | undershoot | 15 |
| mlp | width_change | width_change | 1487 |
| residual_gated_shape_cnn_new | rise_curvature | rise_curvature | 1215 |
| residual_gated_shape_cnn_new | rise_curvature | late_tail | 0 |
| residual_gated_shape_cnn_new | rise_curvature | undershoot | 124 |
| residual_gated_shape_cnn_new | rise_curvature | width_change | 443 |
| residual_gated_shape_cnn_new | late_tail | rise_curvature | 30 |
| residual_gated_shape_cnn_new | late_tail | late_tail | 738 |
| residual_gated_shape_cnn_new | late_tail | undershoot | 8 |
| residual_gated_shape_cnn_new | late_tail | width_change | 3 |
| residual_gated_shape_cnn_new | undershoot | rise_curvature | 551 |
| residual_gated_shape_cnn_new | undershoot | late_tail | 10 |
| residual_gated_shape_cnn_new | undershoot | undershoot | 725 |
| residual_gated_shape_cnn_new | undershoot | width_change | 79 |
| residual_gated_shape_cnn_new | width_change | rise_curvature | 112 |
| residual_gated_shape_cnn_new | width_change | late_tail | 56 |
| residual_gated_shape_cnn_new | width_change | undershoot | 87 |
| residual_gated_shape_cnn_new | width_change | width_change | 1285 |
| ridge | rise_curvature | rise_curvature | 283 |
| ridge | rise_curvature | late_tail | 645 |
| ridge | rise_curvature | undershoot | 463 |
| ridge | rise_curvature | width_change | 391 |
| ridge | late_tail | rise_curvature | 55 |
| ridge | late_tail | late_tail | 490 |
| ridge | late_tail | undershoot | 30 |
| ridge | late_tail | width_change | 204 |
| ridge | undershoot | rise_curvature | 35 |
| ridge | undershoot | late_tail | 299 |
| ridge | undershoot | undershoot | 801 |
| ridge | undershoot | width_change | 230 |
| ridge | width_change | rise_curvature | 44 |
| ridge | width_change | late_tail | 86 |
| ridge | width_change | undershoot | 100 |
| ridge | width_change | width_change | 1310 |
| traditional_pca_cfd_dtw_cluster | rise_curvature | rise_curvature | 1778 |
| traditional_pca_cfd_dtw_cluster | rise_curvature | late_tail | 0 |
| traditional_pca_cfd_dtw_cluster | rise_curvature | undershoot | 4 |
| traditional_pca_cfd_dtw_cluster | rise_curvature | width_change | 0 |
| traditional_pca_cfd_dtw_cluster | late_tail | rise_curvature | 33 |
| traditional_pca_cfd_dtw_cluster | late_tail | late_tail | 733 |
| traditional_pca_cfd_dtw_cluster | late_tail | undershoot | 13 |
| traditional_pca_cfd_dtw_cluster | late_tail | width_change | 0 |

## Interpretation, Systematics, and Caveats

The traditional PCA/CFD/template clustering is intentionally strong for this
setting: it clusters normalized waveform phase space with timing-width and
late-tail coordinates, then uses training-run majority calibration only to name
clusters.  Learned models improve when they capture the same shape axes without
collapsing onto energy, pedestal, pile-up, saturation, or duplicate-channel
sidebands.

The taxonomy is internally reproducible and ROOT-derived, but it is not an
external human or simulation truth label.  It supports claims about whether
sequence representations recover interpretable pulse-shape axes under run
transfer.  It does not prove that the axes are unique, exhaustive, or directly
causal.  Small proxy bins and rare high-undershoot pulses can broaden
run-bootstrap intervals; conclusions should therefore use the reported CIs and
not just point estimates.

Runtime was `64.0 s` on `Linux-5.15.0-139-generic-x86_64-with-debian-bullseye-sid` with Python
`3.7.6`.
