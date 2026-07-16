# S40b Waveform Phase-Space Taxonomy Validation

## Abstract

Ticket `1784180399.1427.0adb4363` asks whether the four S40a waveform phase-space
axes can be treated as physics-relevant labels after comparison with an
independent pulse-shape truth source.  This S40b runner does not reuse any S40a
labels.  It rebuilds the selected B-stack pulse count directly from raw ROOT,
constructs simulation-style truth labels from held-out waveform morphology
rules, and benchmarks a traditional PCA/CFD/template clustering reference
against ridge, gradient-boosted trees, MLP, 1D-CNN, a compact transformer, and
the new residual-gated sequence encoder.

The result written to `result.json` names **`gradient_boosted_trees`** as the winner:
macro AUC `1` `[1,
1]`.  The traditional reference obtains
`0.9998` `[0.9997,
0.9999]`.

## Raw ROOT Reproduction

Inputs are `data/root/root/hrdb_run_*.root`.  For each event,
`h101/HRDv` is reshaped to `(8,18)`.  For B-stack stave channel `c`, the
pedestal-subtracted amplitude is

`A_ec = max_t [x_ec(t) - median(x_ec(0), x_ec(1), x_ec(2), x_ec(3))]`.

The reproduced raw number is

`N = sum_e sum_c 1[A_ec > 1000 ADC]`.

| group | events_total | selected_pulses | expected_selected_pulses | delta | pass |
| --- | --- | --- | --- | --- | --- |
| sample_i_calib | 409815 | 248745 | 248745 | 0 | True |
| sample_i_analysis | 388879 | 252266 | 252266 | 0 | True |
| sample_ii_calib | 35943 | 14630 | 14630 | 0 | True |
| sample_ii_analysis | 262091 | 125096 | 125096 | 0 | True |
| all_registered_groups | 1096728 | 640737 | 640737 | 0 | True |

The all-group reproduced count is **640737**.
First input hashes:

| run | bytes | sha256 |
| --- | --- | --- |
| 31 | 11638901 | 9921aa75c062d0b8994573299a201cbe2725673319fdf1b8cffb711fb9adcea7 |
| 32 | 12157812 | 649983bf173352b638bf57c099dc92741b70483feba8981172b26319fc9047ff |
| 33 | 16781109 | 1b8f1dcda0e53b8c7b702f00801555f6d317a87bed8efef6d228b49146dbf973 |
| 34 | 11697434 | 69ef29a8d879aaa908ab4a076c82b3d10ac7b3e2622e491e017eb368290bdf51 |
| 35 | 7793651 | a6e08e36ab103e76b53741b55ea7cd3e648d1800508d6144b96ab80820e156ea |
| 36 | 6167361 | 1160bee157e233eb63421597b415f1aaf4dea2c1e7e4a804836c487704852fee |
| 37 | 14369738 | 6bcebe85c0b1e38a42cc326cbcdc2107ccaee877372bffd537ce71baa1b22fd3 |
| 39 | 8625385 | b875c8d45a62a39933d7d4648518040a645629e6fb60c9111a7d05c4d982c568 |

## Independent Truth Construction

The independent labels are deterministic simulation-style waveform morphology
labels fitted only from train-run quantiles, then applied unchanged to held-out
runs.  They are intentionally defined from primitive shape functionals rather
than from S40a taxonomy assignments:

`rise curvature = max |Delta^2 x_t|` over samples 4 to 8,

`late tail = sum_{t>=12} x_t / sum_t max(x_t,0)`,

`undershoot = -min_{t>=10} x_t`,

`width = t_0.80 - t_0.20 + 0.35 max(n_flat - 1,0)`.

Each binary truth label is `1[s_a >= q_0.72(s_a | train)]`.

| axis | train_threshold | heldout_positive_rate |
| --- | --- | --- |
| rise_curvature | 0.4257 | 0.2605 |
| late_tail | 0.4194 | 0.2543 |
| undershoot | -0.06797 | 0.2561 |
| width_broad | 1.595 | 0.3055 |

The sampled benchmark rows are:

| split | rows |
| --- | --- |
| heldout | 5466 |
| train | 15137 |

## Methods

| method | family | description |
| --- | --- | --- |
| traditional_pca_cfd_template_cluster | traditional | PCA on normalized waveforms with CFD/template shape proxies and train-run logistic calibration |
| ridge | linear ML | one-vs-rest ridge scores on waveform summaries, CFD, duplicate readout, and normalized samples |
| gradient_boosted_trees | tree ML | histogram gradient-boosted classifiers using the same leakage-controlled features |
| mlp | neural tabular | two-layer perceptron over engineered waveform and detector-state summaries |
| 1d_cnn | neural waveform | compact convolutional multi-label classifier over the 18 normalized ADC samples |
| compact_transformer | neural waveform | one-layer sample-attention encoder with position input and amplitude-weighted pooling |
| residual_gated_sequence_encoder_new | new architecture | gated sequence CNN that emphasizes onset, undershoot, and late-tail residual channels |

## Estimands and Confidence Intervals

For axis `a` and method `m`, the classifier score is `s_m,a(x)`.  The primary
endpoint is held-out `AUC(Y_a, s_m,a)`, with macro AUC equal to the arithmetic
mean over the four axes.  Secondary endpoints are average precision, balanced
accuracy, and F1 at score threshold 0.5.  Confidence intervals are 95 percent
percentile intervals from `520` bootstrap
replicates resampling held-out runs with replacement:

`CI_95(theta) = [q_0.025(theta_b^*), q_0.975(theta_b^*)]`.

## Primary Results

| method | macro_auc | macro_auc_ci_low | macro_auc_ci_high | macro_f1 | macro_balanced_accuracy |
| --- | --- | --- | --- | --- | --- |
| gradient_boosted_trees | 1 | 1 | 1 | 0.9973 | 0.9979 |
| traditional_pca_cfd_template_cluster | 0.9998 | 0.9997 | 0.9999 | 0.9692 | 0.9807 |
| mlp | 0.9997 | 0.9995 | 0.9998 | 0.9886 | 0.9915 |
| ridge | 0.9806 | 0.9772 | 0.9832 | 0.8775 | 0.9048 |
| residual_gated_sequence_encoder_new | 0.9209 | 0.9133 | 0.9281 | 0.7786 | 0.8409 |
| 1d_cnn | 0.9042 | 0.8946 | 0.913 | 0.6209 | 0.7787 |
| compact_transformer | 0.7877 | 0.7654 | 0.8088 | 0.4558 | 0.6927 |

Axis-level performance:

| method | axis | n | auc | auc_ci_low | auc_ci_high | average_precision | balanced_accuracy | f1 | positive_rate |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| traditional_pca_cfd_template_cluster | rise_curvature | 5466 | 1 | 1 | 1 | 1 | 0.989 | 0.9697 | 0.2605 |
| traditional_pca_cfd_template_cluster | late_tail | 5466 | 1 | 1 | 1 | 1 | 0.9558 | 0.9537 | 0.2543 |
| traditional_pca_cfd_template_cluster | undershoot | 5466 | 1 | 1 | 1 | 1 | 0.9975 | 0.9929 | 0.2561 |
| traditional_pca_cfd_template_cluster | width_broad | 5466 | 0.9991 | 0.9987 | 0.9994 | 0.998 | 0.9806 | 0.9604 | 0.3055 |
| ridge | rise_curvature | 5466 | 0.9662 | 0.96 | 0.9718 | 0.8934 | 0.877 | 0.823 | 0.2605 |
| ridge | late_tail | 5466 | 0.9913 | 0.9802 | 0.997 | 0.9794 | 0.9232 | 0.9128 | 0.2543 |
| ridge | undershoot | 5466 | 0.9918 | 0.9886 | 0.9946 | 0.9828 | 0.9503 | 0.9418 | 0.2561 |
| ridge | width_broad | 5466 | 0.973 | 0.9668 | 0.979 | 0.9431 | 0.8689 | 0.8326 | 0.3055 |
| gradient_boosted_trees | rise_curvature | 5466 | 1 | 1 | 1 | 1 | 0.9992 | 0.9989 | 0.2605 |
| gradient_boosted_trees | late_tail | 5466 | 1 | 0.9999 | 1 | 0.9999 | 0.9955 | 0.9939 | 0.2543 |
| gradient_boosted_trees | undershoot | 5466 | 1 | 1 | 1 | 1 | 0.9974 | 0.9971 | 0.2561 |
| gradient_boosted_trees | width_broad | 5466 | 1 | 1 | 1 | 1 | 0.9996 | 0.9994 | 0.3055 |
| mlp | rise_curvature | 5466 | 0.9994 | 0.9987 | 0.9998 | 0.9961 | 0.9902 | 0.9856 | 0.2605 |
| mlp | late_tail | 5466 | 0.9999 | 0.9998 | 1 | 0.9997 | 0.9951 | 0.9932 | 0.2543 |
| mlp | undershoot | 5466 | 0.9995 | 0.9993 | 0.9997 | 0.9987 | 0.9884 | 0.9853 | 0.2561 |
| mlp | width_broad | 5466 | 0.9999 | 0.9998 | 0.9999 | 0.9997 | 0.9923 | 0.9904 | 0.3055 |
| 1d_cnn | rise_curvature | 5466 | 0.8964 | 0.869 | 0.9177 | 0.7335 | 0.7182 | 0.5983 | 0.2605 |
| 1d_cnn | late_tail | 5466 | 0.9985 | 0.9968 | 0.9995 | 0.9956 | 0.9413 | 0.9351 | 0.2543 |
| 1d_cnn | undershoot | 5466 | 0.9851 | 0.9829 | 0.988 | 0.9748 | 0.9544 | 0.9468 | 0.2561 |
| 1d_cnn | width_broad | 5466 | 0.7369 | 0.7109 | 0.7636 | 0.4876 | 0.5008 | 0.003584 | 0.3055 |
| compact_transformer | rise_curvature | 5466 | 0.6461 | 0.5577 | 0.7253 | 0.3251 | 0.5 | 0 | 0.2605 |
| compact_transformer | late_tail | 5466 | 0.9935 | 0.9842 | 0.9982 | 0.9844 | 0.9199 | 0.9119 | 0.2543 |
| compact_transformer | undershoot | 5466 | 0.9639 | 0.9614 | 0.9678 | 0.9165 | 0.831 | 0.7736 | 0.2561 |
| compact_transformer | width_broad | 5466 | 0.5472 | 0.5267 | 0.5806 | 0.3451 | 0.5199 | 0.1377 | 0.3055 |
| residual_gated_sequence_encoder_new | rise_curvature | 5466 | 0.9182 | 0.9017 | 0.9331 | 0.7494 | 0.7977 | 0.7166 | 0.2605 |
| residual_gated_sequence_encoder_new | late_tail | 5466 | 0.9967 | 0.993 | 0.9988 | 0.9911 | 0.9474 | 0.9353 | 0.2543 |
| residual_gated_sequence_encoder_new | undershoot | 5466 | 0.9919 | 0.9906 | 0.9935 | 0.9828 | 0.9595 | 0.9512 | 0.2561 |
| residual_gated_sequence_encoder_new | width_broad | 5466 | 0.7768 | 0.7512 | 0.7985 | 0.5412 | 0.6589 | 0.5111 | 0.3055 |

## Run-Heldout Stability

| method | axis | run | n | auc | balanced_accuracy | f1 |
| --- | --- | --- | --- | --- | --- | --- |
| traditional_pca_cfd_template_cluster | rise_curvature | 42 | 657 | 1 | 0.9906 | 0.9752 |
| traditional_pca_cfd_template_cluster | rise_curvature | 50 | 680 | 1 | 0.9903 | 0.9797 |
| traditional_pca_cfd_template_cluster | rise_curvature | 57 | 670 | 1 | 0.9953 | 0.9827 |
| traditional_pca_cfd_template_cluster | rise_curvature | 58 | 654 | 1 | 0.9852 | 0.9628 |
| traditional_pca_cfd_template_cluster | rise_curvature | 60 | 720 | 1 | 0.9797 | 0.958 |
| traditional_pca_cfd_template_cluster | rise_curvature | 62 | 720 | 1 | 0.9896 | 0.9723 |
| traditional_pca_cfd_template_cluster | rise_curvature | 64 | 720 | 1 | 0.9919 | 0.9733 |
| traditional_pca_cfd_template_cluster | rise_curvature | 65 | 645 | 1 | 0.9885 | 0.9531 |
| traditional_pca_cfd_template_cluster | late_tail | 42 | 657 | 1 | 0.9819 | 0.9815 |
| traditional_pca_cfd_template_cluster | late_tail | 50 | 680 | 1 | 0.9893 | 0.9892 |
| traditional_pca_cfd_template_cluster | late_tail | 57 | 670 | 1 | 0.9816 | 0.9812 |
| traditional_pca_cfd_template_cluster | late_tail | 58 | 654 | 1 | 0.9788 | 0.9783 |
| traditional_pca_cfd_template_cluster | late_tail | 60 | 720 | 1 | 0.8702 | 0.8509 |
| traditional_pca_cfd_template_cluster | late_tail | 62 | 720 | 1 | 0.8872 | 0.8729 |
| traditional_pca_cfd_template_cluster | late_tail | 64 | 720 | 1 | 0.9153 | 0.9074 |
| traditional_pca_cfd_template_cluster | late_tail | 65 | 645 | 1 | 0.9671 | 0.966 |
| traditional_pca_cfd_template_cluster | undershoot | 42 | 657 | 1 | 0.9969 | 0.9915 |
| traditional_pca_cfd_template_cluster | undershoot | 50 | 680 | 1 | 0.999 | 0.9974 |
| traditional_pca_cfd_template_cluster | undershoot | 57 | 670 | 1 | 0.9979 | 0.9951 |
| traditional_pca_cfd_template_cluster | undershoot | 58 | 654 | 1 | 0.9978 | 0.9948 |
| traditional_pca_cfd_template_cluster | undershoot | 60 | 720 | 1 | 0.9973 | 0.9908 |
| traditional_pca_cfd_template_cluster | undershoot | 62 | 720 | 1 | 1 | 1 |
| traditional_pca_cfd_template_cluster | undershoot | 64 | 720 | 1 | 0.9956 | 0.9833 |
| traditional_pca_cfd_template_cluster | undershoot | 65 | 645 | 1 | 0.9957 | 0.9887 |
| traditional_pca_cfd_template_cluster | width_broad | 42 | 657 | 0.9997 | 0.9894 | 0.9737 |
| traditional_pca_cfd_template_cluster | width_broad | 50 | 680 | 0.9994 | 0.9892 | 0.9757 |
| traditional_pca_cfd_template_cluster | width_broad | 57 | 670 | 0.9991 | 0.9805 | 0.9586 |
| traditional_pca_cfd_template_cluster | width_broad | 58 | 654 | 0.9986 | 0.977 | 0.9561 |
| traditional_pca_cfd_template_cluster | width_broad | 60 | 720 | 0.9988 | 0.9831 | 0.9615 |
| traditional_pca_cfd_template_cluster | width_broad | 62 | 720 | 0.9996 | 0.9813 | 0.9652 |
| traditional_pca_cfd_template_cluster | width_broad | 64 | 720 | 0.9993 | 0.9747 | 0.9533 |
| traditional_pca_cfd_template_cluster | width_broad | 65 | 645 | 0.9981 | 0.9662 | 0.9452 |
| ridge | rise_curvature | 42 | 657 | 0.9656 | 0.8809 | 0.8235 |
| ridge | rise_curvature | 50 | 680 | 0.9732 | 0.9141 | 0.8722 |
| ridge | rise_curvature | 57 | 670 | 0.9696 | 0.8986 | 0.8288 |
| ridge | rise_curvature | 58 | 654 | 0.9788 | 0.9281 | 0.8932 |
| ridge | rise_curvature | 60 | 720 | 0.9547 | 0.8514 | 0.8037 |
| ridge | rise_curvature | 62 | 720 | 0.9522 | 0.8213 | 0.7542 |
| ridge | rise_curvature | 64 | 720 | 0.9645 | 0.8525 | 0.7885 |
| ridge | rise_curvature | 65 | 645 | 0.9724 | 0.8555 | 0.7965 |
| ridge | late_tail | 42 | 657 | 0.9988 | 0.9704 | 0.9681 |
| ridge | late_tail | 50 | 680 | 0.9999 | 0.9935 | 0.9915 |
| ridge | late_tail | 57 | 670 | 0.9975 | 0.976 | 0.972 |
| ridge | late_tail | 58 | 654 | 0.9969 | 0.9493 | 0.9455 |
| ridge | late_tail | 60 | 720 | 0.9687 | 0.7799 | 0.7115 |
| ridge | late_tail | 62 | 720 | 0.9592 | 0.7823 | 0.7136 |
| ridge | late_tail | 64 | 720 | 0.9811 | 0.8712 | 0.8462 |
| ridge | late_tail | 65 | 645 | 0.9909 | 0.9312 | 0.9199 |
| ridge | undershoot | 42 | 657 | 0.9958 | 0.9646 | 0.9565 |
| ridge | undershoot | 50 | 680 | 0.9979 | 0.9731 | 0.9677 |
| ridge | undershoot | 57 | 670 | 0.9935 | 0.9688 | 0.96 |
| ridge | undershoot | 58 | 654 | 0.9948 | 0.9601 | 0.9542 |
| ridge | undershoot | 60 | 720 | 0.9916 | 0.9423 | 0.9346 |
| ridge | undershoot | 62 | 720 | 0.9848 | 0.9093 | 0.8942 |
| ridge | undershoot | 64 | 720 | 0.9882 | 0.9353 | 0.9214 |
| ridge | undershoot | 65 | 645 | 0.9861 | 0.935 | 0.9273 |
| ridge | width_broad | 42 | 657 | 0.9757 | 0.8554 | 0.8155 |
| ridge | width_broad | 50 | 680 | 0.987 | 0.9071 | 0.8902 |
| ridge | width_broad | 57 | 670 | 0.9737 | 0.8669 | 0.8306 |
| ridge | width_broad | 58 | 654 | 0.968 | 0.8264 | 0.7738 |
| ridge | width_broad | 60 | 720 | 0.9819 | 0.8877 | 0.8497 |
| ridge | width_broad | 62 | 720 | 0.9731 | 0.8803 | 0.8442 |
| ridge | width_broad | 64 | 720 | 0.9624 | 0.8524 | 0.817 |
| ridge | width_broad | 65 | 645 | 0.96 | 0.8679 | 0.8367 |
| gradient_boosted_trees | rise_curvature | 42 | 657 | 1 | 1 | 1 |
| gradient_boosted_trees | rise_curvature | 50 | 680 | 1 | 0.9977 | 0.9977 |
| gradient_boosted_trees | rise_curvature | 57 | 670 | 1 | 1 | 1 |
| gradient_boosted_trees | rise_curvature | 58 | 654 | 1 | 1 | 1 |
| gradient_boosted_trees | rise_curvature | 60 | 720 | 1 | 0.999 | 0.9978 |
| gradient_boosted_trees | rise_curvature | 62 | 720 | 1 | 1 | 1 |
| gradient_boosted_trees | rise_curvature | 64 | 720 | 1 | 0.997 | 0.9969 |
| gradient_boosted_trees | rise_curvature | 65 | 645 | 1 | 1 | 1 |
| gradient_boosted_trees | late_tail | 42 | 657 | 1 | 0.9963 | 0.9948 |
| gradient_boosted_trees | late_tail | 50 | 680 | 1 | 0.9979 | 0.9979 |
| gradient_boosted_trees | late_tail | 57 | 670 | 1 | 0.9966 | 0.9954 |
| gradient_boosted_trees | late_tail | 58 | 654 | 1 | 1 | 1 |
| gradient_boosted_trees | late_tail | 60 | 720 | 0.9999 | 0.9928 | 0.9811 |
| gradient_boosted_trees | late_tail | 62 | 720 | 0.9999 | 0.9879 | 0.9848 |
| gradient_boosted_trees | late_tail | 64 | 720 | 0.9999 | 0.9873 | 0.9871 |
| gradient_boosted_trees | late_tail | 65 | 645 | 1 | 1 | 1 |
| gradient_boosted_trees | undershoot | 42 | 657 | 1 | 1 | 1 |
| gradient_boosted_trees | undershoot | 50 | 680 | 1 | 0.9974 | 0.9973 |
| gradient_boosted_trees | undershoot | 57 | 670 | 1 | 1 | 1 |
| gradient_boosted_trees | undershoot | 58 | 654 | 1 | 1 | 1 |
| gradient_boosted_trees | undershoot | 60 | 720 | 1 | 0.9929 | 0.9907 |
| gradient_boosted_trees | undershoot | 62 | 720 | 1 | 0.9969 | 0.9968 |
| gradient_boosted_trees | undershoot | 64 | 720 | 1 | 0.9932 | 0.9932 |
| gradient_boosted_trees | undershoot | 65 | 645 | 1 | 0.9971 | 0.9971 |
| gradient_boosted_trees | width_broad | 42 | 657 | 1 | 1 | 1 |
| gradient_boosted_trees | width_broad | 50 | 680 | 1 | 1 | 1 |
| gradient_boosted_trees | width_broad | 57 | 670 | 1 | 1 | 1 |
| gradient_boosted_trees | width_broad | 58 | 654 | 1 | 1 | 1 |
| gradient_boosted_trees | width_broad | 60 | 720 | 1 | 1 | 1 |
| gradient_boosted_trees | width_broad | 62 | 720 | 1 | 0.9979 | 0.9979 |
| gradient_boosted_trees | width_broad | 64 | 720 | 1 | 0.9989 | 0.998 |
| gradient_boosted_trees | width_broad | 65 | 645 | 1 | 1 | 1 |
| mlp | rise_curvature | 42 | 657 | 1 | 0.9961 | 0.9944 |
| mlp | rise_curvature | 50 | 680 | 0.9997 | 0.9875 | 0.9838 |
| mlp | rise_curvature | 57 | 670 | 0.9996 | 0.9875 | 0.9823 |
| mlp | rise_curvature | 58 | 654 | 0.9998 | 0.9951 | 0.9917 |
| mlp | rise_curvature | 60 | 720 | 0.9998 | 0.9926 | 0.9891 |
| mlp | rise_curvature | 62 | 720 | 0.9971 | 0.9842 | 0.9792 |
| mlp | rise_curvature | 64 | 720 | 0.9997 | 0.993 | 0.9908 |
| mlp | rise_curvature | 65 | 645 | 0.9995 | 0.9829 | 0.9675 |
| mlp | late_tail | 42 | 657 | 1 | 1 | 1 |
| mlp | late_tail | 50 | 680 | 1 | 0.9967 | 0.9957 |
| mlp | late_tail | 57 | 670 | 0.9999 | 0.9966 | 0.9954 |
| mlp | late_tail | 58 | 654 | 0.9998 | 0.9976 | 0.9976 |
| mlp | late_tail | 60 | 720 | 0.9994 | 0.989 | 0.9773 |
| mlp | late_tail | 62 | 720 | 0.9998 | 0.9879 | 0.9848 |
| mlp | late_tail | 64 | 720 | 0.9999 | 0.9915 | 0.9915 |
| mlp | late_tail | 65 | 645 | 1 | 0.9957 | 0.9934 |
| mlp | undershoot | 42 | 657 | 0.9996 | 0.9834 | 0.9745 |
| mlp | undershoot | 50 | 680 | 0.9998 | 0.9937 | 0.992 |
| mlp | undershoot | 57 | 670 | 0.9997 | 0.994 | 0.9926 |
| mlp | undershoot | 58 | 654 | 0.9999 | 0.9895 | 0.9894 |
| mlp | undershoot | 60 | 720 | 0.9995 | 0.9876 | 0.9874 |
| mlp | undershoot | 62 | 720 | 0.9993 | 0.9874 | 0.9873 |
| mlp | undershoot | 64 | 720 | 0.9993 | 0.9863 | 0.9763 |
| mlp | undershoot | 65 | 645 | 0.9988 | 0.9836 | 0.9798 |

## Nuisance Separation

The ticket requires the four waveform axes to remain separated from timing,
pedestal, pile-up, saturation, energy, and PID proxies.  The table below
reports the nuisance-level AUC span; small spans indicate that an axis is stable
across that nuisance proxy, while a low worst-level AUC identifies a failure
mode.

| method | axis | nuisance | levels | auc_min | auc_max | auc_span | worst_level |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 1d_cnn | late_tail | pid_proxy | 3 | 0.995 | 1 | 0.005 | low_duplicate |
| 1d_cnn | late_tail | timing | 3 | 0.9957 | 0.9995 | 0.003803 | center |
| 1d_cnn | late_tail | pileup | 3 | 0.996 | 0.9989 | 0.002911 | close |
| 1d_cnn | late_tail | energy | 4 | 0.9979 | 1 | 0.002033 | q4_high |
| 1d_cnn | late_tail | pedestal | 3 | 0.9974 | 0.9993 | 0.001996 | mid |
| 1d_cnn | late_tail | saturation | 2 | 0.9985 | 0.9986 | 8.173e-05 | near_saturation |
| 1d_cnn | rise_curvature | energy | 4 | 0.4332 | 0.8242 | 0.391 | q1_low |
| 1d_cnn | rise_curvature | pid_proxy | 3 | 0.6436 | 0.9102 | 0.2666 | high_duplicate |
| 1d_cnn | rise_curvature | pileup | 3 | 0.7858 | 0.8889 | 0.1031 | none |
| 1d_cnn | rise_curvature | timing | 3 | 0.8393 | 0.914 | 0.07466 | early |
| 1d_cnn | rise_curvature | pedestal | 3 | 0.8601 | 0.9067 | 0.04666 | high |
| 1d_cnn | rise_curvature | saturation | 2 | 0.8883 | 0.9204 | 0.03215 | linear |
| 1d_cnn | undershoot | timing | 3 | 0.8912 | 0.9916 | 0.1004 | center |
| 1d_cnn | undershoot | pileup | 3 | 0.9407 | 0.9903 | 0.04959 | close |
| 1d_cnn | undershoot | energy | 4 | 0.9738 | 0.9987 | 0.02493 | q1_low |
| 1d_cnn | undershoot | pid_proxy | 3 | 0.9705 | 0.9923 | 0.02188 | high_duplicate |
| 1d_cnn | undershoot | saturation | 2 | 0.9728 | 0.988 | 0.01512 | near_saturation |
| 1d_cnn | undershoot | pedestal | 3 | 0.9766 | 0.9914 | 0.0148 | high |
| 1d_cnn | width_broad | energy | 4 | 0.5406 | 0.7875 | 0.2468 | q4_high |
| 1d_cnn | width_broad | timing | 3 | 0.6272 | 0.8381 | 0.2109 | late |
| 1d_cnn | width_broad | saturation | 2 | 0.7405 | 0.889 | 0.1485 | linear |
| 1d_cnn | width_broad | pileup | 3 | 0.5903 | 0.7048 | 0.1145 | mid |
| 1d_cnn | width_broad | pid_proxy | 3 | 0.7142 | 0.8125 | 0.09835 | central |
| 1d_cnn | width_broad | pedestal | 3 | 0.7124 | 0.7659 | 0.05349 | mid |
| compact_transformer | late_tail | pileup | 3 | 0.9479 | 0.995 | 0.04714 | close |
| compact_transformer | late_tail | timing | 3 | 0.96 | 0.9963 | 0.03621 | center |
| compact_transformer | late_tail | pid_proxy | 3 | 0.9733 | 0.9996 | 0.02633 | low_duplicate |
| compact_transformer | late_tail | pedestal | 3 | 0.991 | 0.997 | 0.005959 | mid |
| compact_transformer | late_tail | energy | 4 | 0.995 | 1 | 0.00503 | q3 |
| compact_transformer | late_tail | saturation | 2 | 0.9929 | 0.9955 | 0.002597 | linear |
| compact_transformer | rise_curvature | pid_proxy | 3 | 0.1565 | 0.7522 | 0.5957 | high_duplicate |
| compact_transformer | rise_curvature | timing | 3 | 0.5681 | 0.8669 | 0.2989 | early |
| compact_transformer | rise_curvature | pileup | 3 | 0.3456 | 0.6048 | 0.2592 | mid |
| compact_transformer | rise_curvature | pedestal | 3 | 0.5081 | 0.7207 | 0.2126 | high |
| compact_transformer | rise_curvature | energy | 4 | 0.4667 | 0.6158 | 0.1492 | q1_low |
| compact_transformer | rise_curvature | saturation | 2 | 0.6324 | 0.6758 | 0.04338 | linear |
| compact_transformer | undershoot | timing | 3 | 0.8705 | 0.9887 | 0.1182 | center |
| compact_transformer | undershoot | pileup | 3 | 0.9353 | 0.9871 | 0.05177 | close |
| compact_transformer | undershoot | energy | 4 | 0.9517 | 0.9961 | 0.04439 | q2 |
| compact_transformer | undershoot | pedestal | 3 | 0.9492 | 0.9881 | 0.03887 | high |
| compact_transformer | undershoot | pid_proxy | 3 | 0.956 | 0.9889 | 0.03284 | high_duplicate |
| compact_transformer | undershoot | saturation | 2 | 0.9433 | 0.968 | 0.02473 | near_saturation |
| compact_transformer | width_broad | saturation | 2 | 0.4739 | 0.8443 | 0.3704 | linear |
| compact_transformer | width_broad | energy | 4 | 0.49 | 0.7001 | 0.2101 | q3 |
| compact_transformer | width_broad | pid_proxy | 3 | 0.4775 | 0.6508 | 0.1732 | central |
| compact_transformer | width_broad | pedestal | 3 | 0.4874 | 0.6271 | 0.1397 | mid |
| compact_transformer | width_broad | pileup | 3 | 0.4417 | 0.551 | 0.1093 | none |
| compact_transformer | width_broad | timing | 3 | 0.5048 | 0.5876 | 0.08281 | late |
| gradient_boosted_trees | late_tail | pileup | 3 | 0.9997 | 1 | 0.0003419 | mid |
| gradient_boosted_trees | late_tail | timing | 3 | 0.9998 | 1 | 0.0001798 | center |
| gradient_boosted_trees | late_tail | pid_proxy | 3 | 0.9998 | 1 | 0.0001781 | low_duplicate |
| gradient_boosted_trees | late_tail | energy | 4 | 0.9999 | 1 | 9.601e-05 | q4_high |
| gradient_boosted_trees | late_tail | saturation | 2 | 1 | 1 | 3.285e-05 | linear |
| gradient_boosted_trees | late_tail | pedestal | 3 | 1 | 1 | 2.65e-05 | low |
| gradient_boosted_trees | rise_curvature | pileup | 3 | 1 | 1 | 9.428e-06 | mid |
| gradient_boosted_trees | rise_curvature | pedestal | 3 | 1 | 1 | 4.462e-06 | high |
| gradient_boosted_trees | rise_curvature | energy | 4 | 1 | 1 | 4.082e-06 | q3 |
| gradient_boosted_trees | rise_curvature | timing | 3 | 1 | 1 | 3.079e-06 | center |
| gradient_boosted_trees | rise_curvature | pid_proxy | 3 | 1 | 1 | 1.131e-06 | central |
| gradient_boosted_trees | rise_curvature | saturation | 2 | 1 | 1 | 6.925e-07 | linear |
| gradient_boosted_trees | undershoot | pid_proxy | 3 | 0.9999 | 1 | 6.455e-05 | high_duplicate |
| gradient_boosted_trees | undershoot | pileup | 3 | 1 | 1 | 3.521e-05 | close |
| gradient_boosted_trees | undershoot | energy | 4 | 1 | 1 | 3.004e-05 | q1_low |
| gradient_boosted_trees | undershoot | timing | 3 | 1 | 1 | 2.147e-05 | center |
| gradient_boosted_trees | undershoot | pedestal | 3 | 1 | 1 | 7.084e-06 | low |
| gradient_boosted_trees | undershoot | saturation | 2 | 1 | 1 | 7.079e-06 | linear |
| gradient_boosted_trees | width_broad | pedestal | 3 | 1 | 1 | 5.77e-06 | low |
| gradient_boosted_trees | width_broad | timing | 3 | 1 | 1 | 4.492e-06 | late |
| gradient_boosted_trees | width_broad | pileup | 3 | 1 | 1 | 3.014e-06 | none |
| gradient_boosted_trees | width_broad | energy | 4 | 1 | 1 | 2.147e-06 | q1_low |
| gradient_boosted_trees | width_broad | pid_proxy | 3 | 1 | 1 | 1.868e-06 | central |
| gradient_boosted_trees | width_broad | saturation | 2 | 1 | 1 | 1.858e-06 | linear |
| mlp | late_tail | pileup | 3 | 0.9993 | 0.9999 | 0.0006485 | close |
| mlp | late_tail | pedestal | 3 | 0.9998 | 1 | 0.0002195 | mid |
| mlp | late_tail | pid_proxy | 3 | 0.9998 | 1 | 0.0001986 | low_duplicate |
| mlp | late_tail | timing | 3 | 0.9997 | 0.9998 | 0.0001782 | center |
| mlp | late_tail | energy | 4 | 0.9998 | 1 | 0.0001488 | q4_high |
| mlp | late_tail | saturation | 2 | 0.9999 | 1 | 0.0001395 | linear |
| mlp | rise_curvature | pid_proxy | 3 | 0.9974 | 0.9999 | 0.002481 | high_duplicate |
| mlp | rise_curvature | timing | 3 | 0.9982 | 0.9999 | 0.001668 | early |
| mlp | rise_curvature | energy | 4 | 0.9984 | 0.9998 | 0.001418 | q1_low |
| mlp | rise_curvature | pedestal | 3 | 0.9985 | 0.9999 | 0.001382 | high |
| mlp | rise_curvature | pileup | 3 | 0.9991 | 0.9997 | 0.0006426 | none |
| mlp | rise_curvature | saturation | 2 | 0.9993 | 0.9996 | 0.0002843 | linear |
| mlp | undershoot | pileup | 3 | 0.9967 | 0.9997 | 0.003054 | close |
| mlp | undershoot | pid_proxy | 3 | 0.9973 | 1 | 0.002743 | high_duplicate |
| mlp | undershoot | energy | 4 | 0.9986 | 1 | 0.001408 | q1_low |
| mlp | undershoot | timing | 3 | 0.9986 | 0.9998 | 0.001289 | early |
| mlp | undershoot | pedestal | 3 | 0.9992 | 0.9998 | 0.0006405 | high |
| mlp | undershoot | saturation | 2 | 0.9994 | 0.9996 | 0.000157 | near_saturation |
| mlp | width_broad | pileup | 3 | 0.9998 | 0.9999 | 0.000106 | none |
| mlp | width_broad | timing | 3 | 0.9998 | 0.9999 | 0.0001055 | early |
| mlp | width_broad | pid_proxy | 3 | 0.9999 | 1 | 0.0001054 | central |
| mlp | width_broad | energy | 4 | 0.9998 | 0.9999 | 9.312e-05 | q1_low |
| mlp | width_broad | saturation | 2 | 0.9998 | 0.9999 | 9.304e-05 | near_saturation |
| mlp | width_broad | pedestal | 3 | 0.9999 | 0.9999 | 3.913e-05 | low |
| residual_gated_sequence_encoder_new | late_tail | pid_proxy | 3 | 0.9904 | 0.9996 | 0.009207 | low_duplicate |
| residual_gated_sequence_encoder_new | late_tail | pileup | 3 | 0.9884 | 0.997 | 0.008608 | mid |
| residual_gated_sequence_encoder_new | late_tail | timing | 3 | 0.9915 | 0.9979 | 0.00635 | center |
| residual_gated_sequence_encoder_new | late_tail | energy | 4 | 0.9961 | 0.9999 | 0.00385 | q4_high |
| residual_gated_sequence_encoder_new | late_tail | pedestal | 3 | 0.995 | 0.9983 | 0.003269 | mid |
| residual_gated_sequence_encoder_new | late_tail | saturation | 2 | 0.9967 | 0.997 | 0.0003481 | linear |
| residual_gated_sequence_encoder_new | rise_curvature | pid_proxy | 3 | 0.5475 | 0.9433 | 0.3958 | high_duplicate |
| residual_gated_sequence_encoder_new | rise_curvature | energy | 4 | 0.5711 | 0.8548 | 0.2837 | q1_low |
| residual_gated_sequence_encoder_new | rise_curvature | timing | 3 | 0.8529 | 0.9483 | 0.0954 | early |
| residual_gated_sequence_encoder_new | rise_curvature | pedestal | 3 | 0.8588 | 0.9376 | 0.07877 | high |
| residual_gated_sequence_encoder_new | rise_curvature | pileup | 3 | 0.8536 | 0.8917 | 0.03808 | mid |
| residual_gated_sequence_encoder_new | rise_curvature | saturation | 2 | 0.9101 | 0.9361 | 0.02608 | linear |
| residual_gated_sequence_encoder_new | undershoot | timing | 3 | 0.9625 | 0.9951 | 0.03259 | center |
| residual_gated_sequence_encoder_new | undershoot | pileup | 3 | 0.9644 | 0.9946 | 0.03027 | close |
| residual_gated_sequence_encoder_new | undershoot | pid_proxy | 3 | 0.9783 | 0.9977 | 0.01945 | high_duplicate |
| residual_gated_sequence_encoder_new | undershoot | energy | 4 | 0.9814 | 0.999 | 0.01766 | q1_low |
| residual_gated_sequence_encoder_new | undershoot | pedestal | 3 | 0.9859 | 0.9956 | 0.009701 | high |
| residual_gated_sequence_encoder_new | undershoot | saturation | 2 | 0.9872 | 0.9928 | 0.005551 | near_saturation |
| residual_gated_sequence_encoder_new | width_broad | energy | 4 | 0.5371 | 0.7728 | 0.2358 | q4_high |
| residual_gated_sequence_encoder_new | width_broad | timing | 3 | 0.6434 | 0.8311 | 0.1877 | late |
| residual_gated_sequence_encoder_new | width_broad | saturation | 2 | 0.7909 | 0.9352 | 0.1443 | linear |
| residual_gated_sequence_encoder_new | width_broad | pileup | 3 | 0.666 | 0.7487 | 0.08279 | mid |
| residual_gated_sequence_encoder_new | width_broad | pid_proxy | 3 | 0.756 | 0.8045 | 0.04855 | central |
| residual_gated_sequence_encoder_new | width_broad | pedestal | 3 | 0.7527 | 0.796 | 0.04332 | mid |
| ridge | late_tail | pid_proxy | 3 | 0.9413 | 0.993 | 0.05171 | high_duplicate |
| ridge | late_tail | timing | 3 | 0.9533 | 0.9879 | 0.03468 | center |
| ridge | late_tail | pileup | 3 | 0.9696 | 0.9941 | 0.02451 | close |
| ridge | late_tail | pedestal | 3 | 0.9876 | 0.9942 | 0.006572 | mid |
| ridge | late_tail | energy | 4 | 0.9947 | 0.9997 | 0.005026 | q3 |
| ridge | late_tail | saturation | 2 | 0.9909 | 0.9927 | 0.001797 | linear |
| ridge | rise_curvature | energy | 4 | 0.899 | 0.9846 | 0.08558 | q4_high |
| ridge | rise_curvature | pileup | 3 | 0.9328 | 0.9904 | 0.05758 | mid |
| ridge | rise_curvature | pid_proxy | 3 | 0.9187 | 0.9712 | 0.05256 | low_duplicate |
| ridge | rise_curvature | timing | 3 | 0.9419 | 0.989 | 0.04709 | early |
| ridge | rise_curvature | saturation | 2 | 0.9648 | 0.9707 | 0.005981 | linear |
| ridge | rise_curvature | pedestal | 3 | 0.9632 | 0.9677 | 0.00452 | high |
| ridge | undershoot | timing | 3 | 0.9472 | 0.998 | 0.05079 | center |
| ridge | undershoot | pileup | 3 | 0.967 | 0.9954 | 0.02843 | close |
| ridge | undershoot | energy | 4 | 0.9741 | 0.9996 | 0.02556 | q1_low |
| ridge | undershoot | pid_proxy | 3 | 0.9713 | 0.9959 | 0.02456 | high_duplicate |
| ridge | undershoot | pedestal | 3 | 0.9851 | 0.9952 | 0.01014 | high |
| ridge | undershoot | saturation | 2 | 0.9905 | 0.9919 | 0.001385 | near_saturation |
| ridge | width_broad | energy | 4 | 0.9081 | 0.9938 | 0.08569 | q1_low |
| ridge | width_broad | saturation | 2 | 0.952 | 0.9866 | 0.0346 | linear |
| ridge | width_broad | pileup | 3 | 0.9589 | 0.9934 | 0.03455 | none |
| ridge | width_broad | pid_proxy | 3 | 0.9664 | 0.9895 | 0.02318 | central |
| ridge | width_broad | timing | 3 | 0.9642 | 0.9826 | 0.01844 | late |
| ridge | width_broad | pedestal | 3 | 0.9683 | 0.9772 | 0.008854 | mid |
| traditional_pca_cfd_template_cluster | late_tail | timing | 3 | 1 | 1 | 0 | center |
| traditional_pca_cfd_template_cluster | late_tail | pedestal | 3 | 1 | 1 | 0 | high |
| traditional_pca_cfd_template_cluster | late_tail | pileup | 3 | 1 | 1 | 0 | close |
| traditional_pca_cfd_template_cluster | late_tail | saturation | 2 | 1 | 1 | 0 | linear |
| traditional_pca_cfd_template_cluster | late_tail | energy | 4 | 1 | 1 | 0 | q1_low |
| traditional_pca_cfd_template_cluster | late_tail | pid_proxy | 3 | 1 | 1 | 0 | central |
| traditional_pca_cfd_template_cluster | rise_curvature | timing | 3 | 1 | 1 | 0 | center |
| traditional_pca_cfd_template_cluster | rise_curvature | pedestal | 3 | 1 | 1 | 0 | high |
| traditional_pca_cfd_template_cluster | rise_curvature | pileup | 3 | 1 | 1 | 0 | close |
| traditional_pca_cfd_template_cluster | rise_curvature | saturation | 2 | 1 | 1 | 0 | linear |
| traditional_pca_cfd_template_cluster | rise_curvature | energy | 4 | 1 | 1 | 0 | q1_low |
| traditional_pca_cfd_template_cluster | rise_curvature | pid_proxy | 3 | 1 | 1 | 0 | central |
| traditional_pca_cfd_template_cluster | undershoot | timing | 3 | 1 | 1 | 0 | center |
| traditional_pca_cfd_template_cluster | undershoot | pedestal | 3 | 1 | 1 | 0 | high |
| traditional_pca_cfd_template_cluster | undershoot | pileup | 3 | 1 | 1 | 0 | close |
| traditional_pca_cfd_template_cluster | undershoot | saturation | 2 | 1 | 1 | 0 | linear |

Detailed nuisance cells:

| method | axis | nuisance | level | n | auc | balanced_accuracy | f1 |
| --- | --- | --- | --- | --- | --- | --- | --- |
| traditional_pca_cfd_template_cluster | rise_curvature | timing | center | 1989 | 1 | 0.9763 | 0.9705 |
| traditional_pca_cfd_template_cluster | rise_curvature | timing | early | 1731 | 1 | 0.9914 | 0.9652 |
| traditional_pca_cfd_template_cluster | rise_curvature | timing | late | 1746 | 1 | 0.9961 | 0.9732 |
| traditional_pca_cfd_template_cluster | rise_curvature | pedestal | high | 1731 | 1 | 0.9915 | 0.9635 |
| traditional_pca_cfd_template_cluster | rise_curvature | pedestal | low | 1766 | 1 | 0.9864 | 0.968 |
| traditional_pca_cfd_template_cluster | rise_curvature | pedestal | mid | 1969 | 1 | 0.9887 | 0.9745 |
| traditional_pca_cfd_template_cluster | rise_curvature | pileup | close | 1668 | 1 | 0.9773 | 0.9765 |
| traditional_pca_cfd_template_cluster | rise_curvature | pileup | mid | 1187 | 1 | 0.9775 | 0.959 |
| traditional_pca_cfd_template_cluster | rise_curvature | pileup | none | 2609 | 1 | 0.9969 | 0.9645 |
| traditional_pca_cfd_template_cluster | rise_curvature | saturation | linear | 3958 | 1 | 0.9903 | 0.9708 |
| traditional_pca_cfd_template_cluster | rise_curvature | saturation | near_saturation | 1508 | 1 | 0.9852 | 0.9673 |
| traditional_pca_cfd_template_cluster | rise_curvature | energy | q1_low | 1366 | 1 | 0.9989 | 0.963 |
| traditional_pca_cfd_template_cluster | rise_curvature | energy | q2 | 1553 | 1 | 0.9963 | 0.9043 |
| traditional_pca_cfd_template_cluster | rise_curvature | energy | q3 | 1427 | 1 | 0.9718 | 0.9599 |
| traditional_pca_cfd_template_cluster | rise_curvature | energy | q4_high | 1120 | 1 | 0.9627 | 0.9825 |
| traditional_pca_cfd_template_cluster | rise_curvature | pid_proxy | central | 3740 | 1 | 0.9896 | 0.9704 |
| traditional_pca_cfd_template_cluster | rise_curvature | pid_proxy | high_duplicate | 863 | 1 | 0.9975 | 0.9697 |
| traditional_pca_cfd_template_cluster | rise_curvature | pid_proxy | low_duplicate | 863 | 1 | 0.9703 | 0.968 |
| traditional_pca_cfd_template_cluster | late_tail | timing | center | 1989 | 1 | 0.7481 | 0.6634 |
| traditional_pca_cfd_template_cluster | late_tail | timing | early | 1731 | 1 | 0.8824 | 0.8667 |
| traditional_pca_cfd_template_cluster | late_tail | timing | late | 1746 | 1 | 0.9794 | 0.979 |
| traditional_pca_cfd_template_cluster | late_tail | pedestal | high | 1731 | 1 | 0.9611 | 0.9595 |
| traditional_pca_cfd_template_cluster | late_tail | pedestal | low | 1766 | 1 | 0.9563 | 0.9543 |
| traditional_pca_cfd_template_cluster | late_tail | pedestal | mid | 1969 | 1 | 0.9529 | 0.9506 |
| traditional_pca_cfd_template_cluster | late_tail | pileup | close | 1668 | 1 | 0.5855 | 0.2921 |
| traditional_pca_cfd_template_cluster | late_tail | pileup | mid | 1187 | 1 | 0.64 | 0.4375 |
| traditional_pca_cfd_template_cluster | late_tail | pileup | none | 2609 | 1 | 0.9837 | 0.9834 |
| traditional_pca_cfd_template_cluster | late_tail | saturation | linear | 3958 | 1 | 0.9563 | 0.9543 |
| traditional_pca_cfd_template_cluster | late_tail | saturation | near_saturation | 1508 | 1 | 0.9535 | 0.9512 |
| traditional_pca_cfd_template_cluster | late_tail | energy | q1_low | 1366 | 1 | 0.9895 | 0.9894 |
| traditional_pca_cfd_template_cluster | late_tail | energy | q2 | 1553 | 1 | 0.9866 | 0.9864 |
| traditional_pca_cfd_template_cluster | late_tail | energy | q3 | 1427 | 1 | 0.9345 | 0.9299 |
| traditional_pca_cfd_template_cluster | late_tail | energy | q4_high | 1120 | 1 | 0.9127 | 0.9043 |
| traditional_pca_cfd_template_cluster | late_tail | pid_proxy | central | 3740 | 1 | 0.9683 | 0.9673 |
| traditional_pca_cfd_template_cluster | late_tail | pid_proxy | high_duplicate | 863 | 1 | 1 | 1 |
| traditional_pca_cfd_template_cluster | late_tail | pid_proxy | low_duplicate | 863 | 1 | 0.8918 | 0.8786 |
| traditional_pca_cfd_template_cluster | undershoot | timing | center | 1989 | 1 | 0.9987 | 0.9505 |
| traditional_pca_cfd_template_cluster | undershoot | timing | early | 1731 | 1 | 0.9947 | 0.992 |
| traditional_pca_cfd_template_cluster | undershoot | timing | late | 1746 | 1 | 0.9981 | 0.997 |
| traditional_pca_cfd_template_cluster | undershoot | pedestal | high | 1731 | 1 | 0.9955 | 0.9953 |
| traditional_pca_cfd_template_cluster | undershoot | pedestal | low | 1766 | 1 | 0.9977 | 0.9874 |
| traditional_pca_cfd_template_cluster | undershoot | pedestal | mid | 1969 | 1 | 0.9985 | 0.9912 |
| traditional_pca_cfd_template_cluster | undershoot | pileup | close | 1668 | 1 | 0.9968 | 0.9474 |
| traditional_pca_cfd_template_cluster | undershoot | pileup | mid | 1187 | 1 | 0.9982 | 0.996 |
| traditional_pca_cfd_template_cluster | undershoot | pileup | none | 2609 | 1 | 0.9979 | 0.9963 |
| traditional_pca_cfd_template_cluster | undershoot | saturation | linear | 3958 | 1 | 0.9966 | 0.9919 |
| traditional_pca_cfd_template_cluster | undershoot | saturation | near_saturation | 1508 | 1 | 0.9996 | 0.9979 |
| traditional_pca_cfd_template_cluster | undershoot | energy | q1_low | 1366 | 1 | 0.9887 | 0.988 |
| traditional_pca_cfd_template_cluster | undershoot | energy | q2 | 1553 | 1 | 0.9987 | 0.9965 |
| traditional_pca_cfd_template_cluster | undershoot | energy | q3 | 1427 | 1 | 0.9996 | 0.9978 |
| traditional_pca_cfd_template_cluster | undershoot | energy | q4_high | 1120 | 1 | 1 | 1 |
| traditional_pca_cfd_template_cluster | undershoot | pid_proxy | central | 3740 | 1 | 0.998 | 0.9911 |
| traditional_pca_cfd_template_cluster | undershoot | pid_proxy | high_duplicate | 863 | 1 | 0.9835 | 0.9956 |
| traditional_pca_cfd_template_cluster | undershoot | pid_proxy | low_duplicate | 863 | 1 | 0.9988 | 0.9804 |
| traditional_pca_cfd_template_cluster | width_broad | timing | center | 1989 | 0.999 | 0.9789 | 0.9609 |
| traditional_pca_cfd_template_cluster | width_broad | timing | early | 1731 | 0.9992 | 0.9869 | 0.9689 |
| traditional_pca_cfd_template_cluster | width_broad | timing | late | 1746 | 0.9992 | 0.9753 | 0.9534 |
| traditional_pca_cfd_template_cluster | width_broad | pedestal | high | 1731 | 0.9995 | 0.9892 | 0.9717 |
| traditional_pca_cfd_template_cluster | width_broad | pedestal | low | 1766 | 0.9987 | 0.9771 | 0.959 |
| traditional_pca_cfd_template_cluster | width_broad | pedestal | mid | 1969 | 0.999 | 0.9751 | 0.9548 |
| traditional_pca_cfd_template_cluster | width_broad | pileup | close | 1668 | 0.9989 | 0.9871 | 0.9702 |
| traditional_pca_cfd_template_cluster | width_broad | pileup | mid | 1187 | 0.9994 | 0.9851 | 0.9697 |
| traditional_pca_cfd_template_cluster | width_broad | pileup | none | 2609 | 0.9993 | 0.9659 | 0.9555 |
| traditional_pca_cfd_template_cluster | width_broad | saturation | linear | 3958 | 1 | 0.9805 | 0.9099 |
| traditional_pca_cfd_template_cluster | width_broad | saturation | near_saturation | 1508 | 0.9999 | 0.9961 | 0.9961 |
| traditional_pca_cfd_template_cluster | width_broad | energy | q1_low | 1366 | 0.9994 | 0.9457 | 0.9444 |
| traditional_pca_cfd_template_cluster | width_broad | energy | q2 | 1553 | 0.9997 | 0.9668 | 0.9661 |
| traditional_pca_cfd_template_cluster | width_broad | energy | q3 | 1427 | 1 | 0.9883 | 0.9881 |
| traditional_pca_cfd_template_cluster | width_broad | energy | q4_high | 1120 | 1 | 0.9887 | 0.9783 |
| traditional_pca_cfd_template_cluster | width_broad | pid_proxy | central | 3740 | 0.999 | 0.9752 | 0.9583 |
| traditional_pca_cfd_template_cluster | width_broad | pid_proxy | high_duplicate | 863 | 0.9995 | 0.9886 | 0.9714 |
| traditional_pca_cfd_template_cluster | width_broad | pid_proxy | low_duplicate | 863 | 0.9992 | 0.9866 | 0.9674 |
| ridge | rise_curvature | timing | center | 1989 | 0.9496 | 0.8822 | 0.8681 |
| ridge | rise_curvature | timing | early | 1731 | 0.9419 | 0.8103 | 0.7087 |
| ridge | rise_curvature | timing | late | 1746 | 0.989 | 0.8513 | 0.8031 |
| ridge | rise_curvature | pedestal | high | 1731 | 0.9632 | 0.8647 | 0.7896 |
| ridge | rise_curvature | pedestal | low | 1766 | 0.964 | 0.8814 | 0.8306 |
| ridge | rise_curvature | pedestal | mid | 1969 | 0.9677 | 0.8764 | 0.8341 |
| ridge | rise_curvature | pileup | close | 1668 | 0.9403 | 0.8585 | 0.8525 |
| ridge | rise_curvature | pileup | mid | 1187 | 0.9328 | 0.8607 | 0.8082 |
| ridge | rise_curvature | pileup | none | 2609 | 0.9904 | 0.7857 | 0.7178 |
| ridge | rise_curvature | saturation | linear | 3958 | 0.9648 | 0.8714 | 0.8105 |
| ridge | rise_curvature | saturation | near_saturation | 1508 | 0.9707 | 0.8886 | 0.8492 |
| ridge | rise_curvature | energy | q1_low | 1366 | 0.9735 | 0.7032 | 0.5333 |
| ridge | rise_curvature | energy | q2 | 1553 | 0.9846 | 0.6343 | 0.4179 |
| ridge | rise_curvature | energy | q3 | 1427 | 0.9054 | 0.7881 | 0.7417 |
| ridge | rise_curvature | energy | q4_high | 1120 | 0.899 | 0.804 | 0.9036 |
| ridge | rise_curvature | pid_proxy | central | 3740 | 0.9712 | 0.8784 | 0.8275 |
| ridge | rise_curvature | pid_proxy | high_duplicate | 863 | 0.9471 | 0.7222 | 0.58 |
| ridge | rise_curvature | pid_proxy | low_duplicate | 863 | 0.9187 | 0.8453 | 0.8417 |
| ridge | late_tail | timing | center | 1989 | 0.9533 | 0.5516 | 0.1867 |
| ridge | late_tail | timing | early | 1731 | 0.9796 | 0.7347 | 0.5926 |
| ridge | late_tail | timing | late | 1746 | 0.9879 | 0.9532 | 0.9615 |
| ridge | late_tail | pedestal | high | 1731 | 0.9942 | 0.9228 | 0.9102 |
| ridge | late_tail | pedestal | low | 1766 | 0.9915 | 0.9268 | 0.9198 |
| ridge | late_tail | pedestal | mid | 1969 | 0.9876 | 0.9195 | 0.9074 |
| ridge | late_tail | pileup | close | 1668 | 0.9696 | 0.5 | 0 |
| ridge | late_tail | pileup | mid | 1187 | 0.9941 | 0.62 | 0.3871 |
| ridge | late_tail | pileup | none | 2609 | 0.9911 | 0.9494 | 0.9473 |
| ridge | late_tail | saturation | linear | 3958 | 0.9909 | 0.9188 | 0.9089 |
| ridge | late_tail | saturation | near_saturation | 1508 | 0.9927 | 0.9429 | 0.9293 |
| ridge | late_tail | energy | q1_low | 1366 | 0.9997 | 0.9936 | 0.981 |
| ridge | late_tail | energy | q2 | 1553 | 0.9962 | 0.9899 | 0.9826 |
| ridge | late_tail | energy | q3 | 1427 | 0.9947 | 0.8794 | 0.8629 |
| ridge | late_tail | energy | q4_high | 1120 | 0.9973 | 0.8308 | 0.7952 |
| ridge | late_tail | pid_proxy | central | 3740 | 0.993 | 0.9438 | 0.9372 |
| ridge | late_tail | pid_proxy | high_duplicate | 863 | 0.9413 | 0.7488 | 0.5455 |
| ridge | late_tail | pid_proxy | low_duplicate | 863 | 0.9779 | 0.8231 | 0.7833 |
| ridge | undershoot | timing | center | 1989 | 0.9472 | 0.5417 | 0.1538 |
| ridge | undershoot | timing | early | 1731 | 0.9883 | 0.9423 | 0.9357 |
| ridge | undershoot | timing | late | 1746 | 0.998 | 0.9819 | 0.9789 |
| ridge | undershoot | pedestal | high | 1731 | 0.9851 | 0.9382 | 0.9348 |
| ridge | undershoot | pedestal | low | 1766 | 0.9952 | 0.9692 | 0.961 |
| ridge | undershoot | pedestal | mid | 1969 | 0.9922 | 0.9554 | 0.9433 |
| ridge | undershoot | pileup | close | 1668 | 0.967 | 0.6932 | 0.5426 |
| ridge | undershoot | pileup | mid | 1187 | 0.9954 | 0.9538 | 0.9439 |
| ridge | undershoot | pileup | none | 2609 | 0.9943 | 0.9721 | 0.9689 |
| ridge | undershoot | saturation | linear | 3958 | 0.9919 | 0.956 | 0.949 |
| ridge | undershoot | saturation | near_saturation | 1508 | 0.9905 | 0.9203 | 0.9054 |
| ridge | undershoot | energy | q1_low | 1366 | 0.9741 | 0.9405 | 0.9371 |
| ridge | undershoot | energy | q2 | 1553 | 0.9949 | 0.9441 | 0.9361 |
| ridge | undershoot | energy | q3 | 1427 | 0.9987 | 0.9744 | 0.9596 |
| ridge | undershoot | energy | q4_high | 1120 | 0.9996 | 0.9859 | 0.956 |
| ridge | undershoot | pid_proxy | central | 3740 | 0.9889 | 0.9437 | 0.9342 |
| ridge | undershoot | pid_proxy | high_duplicate | 863 | 0.9713 | 0.9164 | 0.9471 |
| ridge | undershoot | pid_proxy | low_duplicate | 863 | 0.9959 | 0.97 | 0.9691 |
| ridge | width_broad | timing | center | 1989 | 0.9826 | 0.8984 | 0.8721 |
| ridge | width_broad | timing | early | 1731 | 0.9754 | 0.8864 | 0.8388 |
| ridge | width_broad | timing | late | 1746 | 0.9642 | 0.8213 | 0.7755 |
| ridge | width_broad | pedestal | high | 1731 | 0.9772 | 0.8889 | 0.8401 |
| ridge | width_broad | pedestal | low | 1766 | 0.9738 | 0.8714 | 0.8429 |
| ridge | width_broad | pedestal | mid | 1969 | 0.9683 | 0.8544 | 0.8186 |
| ridge | width_broad | pileup | close | 1668 | 0.9749 | 0.8811 | 0.8365 |
| ridge | width_broad | pileup | mid | 1187 | 0.9934 | 0.9486 | 0.8861 |
| ridge | width_broad | pileup | none | 2609 | 0.9589 | 0.8499 | 0.8245 |
| ridge | width_broad | saturation | linear | 3958 | 0.952 | 0.7137 | 0.5765 |
| ridge | width_broad | saturation | near_saturation | 1508 | 0.9866 | 0.9118 | 0.9558 |
| ridge | width_broad | energy | q1_low | 1366 | 0.9081 | 0.7939 | 0.7705 |
| ridge | width_broad | energy | q2 | 1553 | 0.9642 | 0.8846 | 0.8716 |
| ridge | width_broad | energy | q3 | 1427 | 0.9938 | 0.9736 | 0.92 |
| ridge | width_broad | energy | q4_high | 1120 | 0.9804 | 0.8385 | 0.6531 |
| ridge | width_broad | pid_proxy | central | 3740 | 0.9664 | 0.8578 | 0.8258 |
| ridge | width_broad | pid_proxy | high_duplicate | 863 | 0.981 | 0.8922 | 0.8188 |
| ridge | width_broad | pid_proxy | low_duplicate | 863 | 0.9895 | 0.9159 | 0.8877 |
| gradient_boosted_trees | rise_curvature | timing | center | 1989 | 1 | 0.999 | 0.9989 |
| gradient_boosted_trees | rise_curvature | timing | early | 1731 | 1 | 0.9985 | 0.9985 |
| gradient_boosted_trees | rise_curvature | timing | late | 1746 | 1 | 1 | 1 |
| gradient_boosted_trees | rise_curvature | pedestal | high | 1731 | 1 | 0.9984 | 0.9984 |
| gradient_boosted_trees | rise_curvature | pedestal | low | 1766 | 1 | 0.999 | 0.999 |
| gradient_boosted_trees | rise_curvature | pedestal | mid | 1969 | 1 | 0.9996 | 0.9992 |
| gradient_boosted_trees | rise_curvature | pileup | close | 1668 | 1 | 1 | 1 |
| gradient_boosted_trees | rise_curvature | pileup | mid | 1187 | 1 | 0.9981 | 0.9976 |
| gradient_boosted_trees | rise_curvature | pileup | none | 2609 | 1 | 0.9975 | 0.9975 |
| gradient_boosted_trees | rise_curvature | saturation | linear | 3958 | 1 | 0.9993 | 0.999 |
| gradient_boosted_trees | rise_curvature | saturation | near_saturation | 1508 | 1 | 0.9989 | 0.9989 |
| gradient_boosted_trees | rise_curvature | energy | q1_low | 1366 | 1 | 0.9872 | 0.987 |
| gradient_boosted_trees | rise_curvature | energy | q2 | 1553 | 1 | 1 | 1 |
| gradient_boosted_trees | rise_curvature | energy | q3 | 1427 | 1 | 0.9994 | 0.9991 |
| gradient_boosted_trees | rise_curvature | energy | q4_high | 1120 | 1 | 0.9993 | 0.9993 |
| gradient_boosted_trees | rise_curvature | pid_proxy | central | 3740 | 1 | 0.9998 | 0.9995 |

## Systematics and Caveats

This is an independent waveform-truth validation, not a human hand-scan.  The
labels are simulation-style morphology labels derived directly from raw ROOT
waveforms; they are independent of S40a labels but not independent of detector
readout.  Consequently, the study validates whether the four axes are
recoverable and nuisance-stable in raw pulse phase space, not whether they are
unique particle-physics categories.

Run-block bootstrap intervals measure transfer across data-taking runs rather
than event-counting precision.  Small nuisance cells should be read with their
row counts.  PID is represented by a duplicate-readout amplitude sideband
proxy, saturation by high amplitude or flat-top occupancy, and pile-up by late
secondary prominence spacing; all are stress proxies, not decoded hardware
truth flags.  The neural architectures are deliberately compact and trained
with a fixed small epoch budget to test whether sequence models add robust
structure beyond a strong traditional PCA/CFD/template baseline.

Runtime was `196.0 s` on `Linux-5.15.0-139-generic-x86_64-with-debian-bullseye-sid` with Python
`3.7.6`.
