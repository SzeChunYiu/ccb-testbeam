# S15 follow-up #2428: true multi-run PID truth split artifact

## Abstract

Ticket `#2428` follows PR `#1429`, where the p/d deltaE-E PID bakeoff was limited
by an MC event table with degenerate `run_id=0`.  This artifact exposes a PID
truth event table with non-degenerate raw acquisition grouping and reruns the
traditional/ridge/gradient-boosted-tree/MLP/1D-CNN/new-architecture panel with
literal leave-one-source-run-out evaluation.  The worker is `testbeam-laptop-2`.

The winner is **`gradient_boosted_trees`**.  Its leave-one-run-out balanced accuracy
is `0.9428` with 95% run-bootstrap CI
[`0.9337`, `0.9513`],
and its PID AUC is `0.9868`.

## Raw ROOT reproduction gate

The upstream waveform/truth table is the S29a raw-ROOT-reproduced GEANT4-aligned
truth table at `reports/1783809265.5764.0f2a2dda__s29a_digitized_g4_multitask_truth_benchmark`.  Its B-stack selected-pulse count is
reproduced from raw `h101/HRDv` ROOT files, not from a processed summary:

| quantity                           |   report_value |   reproduced |   delta | pass   |
|:-----------------------------------|---------------:|-------------:|--------:|:-------|
| total selected B-stave pulses      |         640737 |       640737 |       0 | True   |
| sample_ii_analysis selected_pulses |         125096 |       125096 |       0 | True   |
| sample_ii_analysis B2              |          88213 |        88213 |       0 | True   |
| sample_ii_analysis B4              |          21229 |        21229 |       0 | True   |
| sample_ii_analysis B6              |          11148 |        11148 |       0 | True   |
| sample_ii_analysis B8              |           4506 |         4506 |       0 | True   |

The raw selection is `max_t(x_c(t)-median(x_c[0:4])) > 1000 ADC` on B2/B4/B6/B8.
The total selected-pulse reproduction is exactly 640,737/640,737, delta 0.

## Truth event table and grouping

The ticket-specific `pid_truth_event_table.csv` contains one row per scored
truth event and makes the acquisition grouping explicit through `source_run`,
`acquisition_run`, `source_file_id`, `acquisition_id`, `source_group`, and
`run_id`.  These columns are excluded from model features and used only for
leave-one-run-out splitting, audit, and bootstrap resampling.

| quantity         |   value |
|:-----------------|--------:|
| truth_rows       |    1396 |
| acquisition_runs |      13 |
| proton_rows      |     702 |
| deuteron_rows    |     694 |
| min_rows_per_run |      92 |
| max_rows_per_run |     132 |

GEANT4 truth supplies the p/d label: `pid_label=0` is proton and `pid_label=1`
is deuteron, defined by dominant B-stack Sci_bar PDG.  Raw waveform morphology,
pedestal, pile-up, saturation, and source-run grouping are inherited from the
raw B-stack digitized event construction.

## Methods

The traditional comparator is `traditional_deltae_depth_likelihood`.  It is a
diagonal Gaussian likelihood ratio in standardized
`(dE/dx proxy, depth index, B-stack layer multiplicity, pulse-shape area, energy)`
space:

`log p(z | y) = -1/2 sum_j ((z_j - mu_yj)^2 / sigma_yj^2 + log sigma_yj^2) + log pi_y`.

The ML/NN panel contains ridge logistic regression, histogram gradient-boosted
trees, MLP, a compact 1D-CNN proxy over ordered waveform/truth-shape summaries,
and `hybrid_polynomial_residual_new`, a new residualized polynomial-logistic
architecture that allows cross terms between energy loss, depth, timing, and
waveform-shape summaries.

For each acquisition run `r`, the estimator is fit on all rows with
`acquisition_run != r` and scored only on run `r`.  The pooled predictions across
all held-out runs form the primary estimate.  Confidence intervals are percentile
95% intervals from `1000` bootstrap resamples of the held-out
run set.

The ranking score is

`C_m = (1 - BAcc_m) + 0.25 Brier_m + 0.10 (1 - AUC_m)`,

so lower is better.

## Primary results

| method                              |   winner_score |   balanced_accuracy |   balanced_accuracy_ci95_low |   balanced_accuracy_ci95_high |   pid_auc |   pid_auc_ci95_low |   pid_auc_ci95_high |   average_precision |   brier |   purity |   efficiency |     f1 |
|:------------------------------------|---------------:|--------------------:|-----------------------------:|------------------------------:|----------:|-------------------:|--------------------:|--------------------:|--------:|---------:|-------------:|-------:|
| gradient_boosted_trees              |        0.06922 |              0.9428 |                       0.9337 |                        0.9513 |    0.9868 |             0.9851 |              0.9891 |              0.9856 | 0.04278 |   0.9276 |       0.9597 | 0.9433 |
| ridge                               |        0.09382 |              0.9236 |                       0.9136 |                        0.934  |    0.975  |             0.9702 |              0.9796 |              0.9642 | 0.05961 |   0.8908 |       0.964  | 0.926  |
| hybrid_polynomial_residual_new      |        0.109   |              0.9106 |                       0.8918 |                        0.9276 |    0.9694 |             0.9622 |              0.9755 |              0.9589 | 0.06608 |   0.8903 |       0.9352 | 0.9122 |
| mlp                                 |        0.1235  |              0.8979 |                       0.8782 |                        0.9164 |    0.9644 |             0.9524 |              0.9738 |              0.9558 | 0.0711  |   0.8583 |       0.951  | 0.9023 |
| 1d_cnn                              |        0.1487  |              0.8793 |                       0.8619 |                        0.8941 |    0.9441 |             0.9272 |              0.9578 |              0.9323 | 0.08989 |   0.8327 |       0.9467 | 0.886  |
| traditional_deltae_depth_likelihood |        0.2154  |              0.8364 |                       0.816  |                        0.8553 |    0.8451 |             0.8205 |              0.869  |              0.7388 | 0.1451  |   0.7925 |       0.9078 | 0.8462 |

## Leave-one-run-out stability

| method                              |   heldout_run |   balanced_accuracy |   pid_auc |   average_precision |   brier |   purity |   efficiency |     f1 |
|:------------------------------------|--------------:|--------------------:|----------:|--------------------:|--------:|---------:|-------------:|-------:|
| 1d_cnn                              |            50 |              0.9125 |    0.9778 |              0.9741 | 0.05065 |   0.898  |       0.9362 | 0.9167 |
| 1d_cnn                              |            51 |              0.9183 |    0.9678 |              0.9703 | 0.0626  |   0.9091 |       0.9615 | 0.9346 |
| 1d_cnn                              |            52 |              0.8883 |    0.9612 |              0.9618 | 0.08389 |   0.8519 |       0.9583 | 0.902  |
| 1d_cnn                              |            53 |              0.8529 |    0.9274 |              0.873  | 0.1074  |   0.7843 |       0.9302 | 0.8511 |
| 1d_cnn                              |            54 |              0.831  |    0.8889 |              0.8502 | 0.1302  |   0.7647 |       0.907  | 0.8298 |
| 1d_cnn                              |            55 |              0.8662 |    0.951  |              0.938  | 0.08862 |   0.7843 |       0.9524 | 0.8602 |
| 1d_cnn                              |            56 |              0.8948 |    0.9252 |              0.9185 | 0.109   |   0.8596 |       0.98   | 0.9159 |
| 1d_cnn                              |            57 |              0.8996 |    0.9813 |              0.9773 | 0.06766 |   0.8163 |       0.9756 | 0.8889 |
| 1d_cnn                              |            58 |              0.8939 |    0.95   |              0.9412 | 0.07821 |   0.8714 |       0.9242 | 0.8971 |
| 1d_cnn                              |            60 |              0.9115 |    0.9641 |              0.9507 | 0.06931 |   0.8676 |       0.9516 | 0.9077 |
| 1d_cnn                              |            62 |              0.8606 |    0.9226 |              0.8951 | 0.1142  |   0.7945 |       0.9355 | 0.8593 |
| 1d_cnn                              |            64 |              0.8764 |    0.9625 |              0.9602 | 0.0808  |   0.8353 |       0.9861 | 0.9045 |
| 1d_cnn                              |            65 |              0.8333 |    0.9031 |              0.8937 | 0.1202  |   0.7895 |       0.9091 | 0.8451 |
| gradient_boosted_trees              |            50 |              0.956  |    0.9943 |              0.9948 | 0.03705 |   0.9388 |       0.9787 | 0.9583 |
| gradient_boosted_trees              |            51 |              0.9115 |    0.9827 |              0.9863 | 0.05666 |   0.9231 |       0.9231 | 0.9231 |
| gradient_boosted_trees              |            52 |              0.9214 |    0.9834 |              0.9843 | 0.05893 |   0.8868 |       0.9792 | 0.9307 |
| gradient_boosted_trees              |            53 |              0.9257 |    0.9896 |              0.9883 | 0.04425 |   0.8913 |       0.9535 | 0.9213 |
| gradient_boosted_trees              |            54 |              0.9359 |    0.9815 |              0.9764 | 0.04993 |   0.9111 |       0.9535 | 0.9318 |
| gradient_boosted_trees              |            55 |              0.96   |    0.9905 |              0.9885 | 0.04162 |   0.913  |       1      | 0.9545 |
| gradient_boosted_trees              |            56 |              0.9243 |    0.9838 |              0.9844 | 0.04698 |   0.9388 |       0.92   | 0.9293 |
| gradient_boosted_trees              |            57 |              0.9486 |    0.9857 |              0.979  | 0.04246 |   0.9091 |       0.9756 | 0.9412 |
| gradient_boosted_trees              |            58 |              0.9545 |    0.9885 |              0.9891 | 0.03807 |   0.9545 |       0.9545 | 0.9545 |
| gradient_boosted_trees              |            60 |              0.9454 |    0.9892 |              0.9817 | 0.03687 |   0.9661 |       0.9194 | 0.9421 |
| gradient_boosted_trees              |            62 |              0.9624 |    0.9882 |              0.9856 | 0.03893 |   0.9524 |       0.9677 | 0.96   |
| gradient_boosted_trees              |            64 |              0.9597 |    0.9917 |              0.9916 | 0.02393 |   0.9467 |       0.9861 | 0.966  |
| gradient_boosted_trees              |            65 |              0.9318 |    0.991  |              0.9914 | 0.05124 |   0.9014 |       0.9697 | 0.9343 |
| hybrid_polynomial_residual_new      |            50 |              0.9565 |    0.9787 |              0.9719 | 0.04511 |   0.9574 |       0.9574 | 0.9574 |
| hybrid_polynomial_residual_new      |            51 |              0.8865 |    0.9611 |              0.9757 | 0.07777 |   0.8889 |       0.9231 | 0.9057 |
| hybrid_polynomial_residual_new      |            52 |              0.911  |    0.9678 |              0.9691 | 0.06921 |   0.8846 |       0.9583 | 0.92   |
| hybrid_polynomial_residual_new      |            53 |              0.9025 |    0.9786 |              0.9745 | 0.05771 |   0.8864 |       0.907  | 0.8966 |
| hybrid_polynomial_residual_new      |            54 |              0.8835 |    0.9563 |              0.9449 | 0.08664 |   0.8333 |       0.9302 | 0.8791 |
| hybrid_polynomial_residual_new      |            55 |              0.8724 |    0.9514 |              0.9426 | 0.09532 |   0.8261 |       0.9048 | 0.8636 |
| hybrid_polynomial_residual_new      |            56 |              0.8667 |    0.9481 |              0.9086 | 0.08591 |   0.8654 |       0.9    | 0.8824 |
| hybrid_polynomial_residual_new      |            57 |              0.9608 |    0.9871 |              0.9827 | 0.03948 |   0.9111 |       1      | 0.9535 |
| hybrid_polynomial_residual_new      |            58 |              0.9394 |    0.975  |              0.9671 | 0.0528  |   0.9394 |       0.9394 | 0.9394 |
| hybrid_polynomial_residual_new      |            60 |              0.9463 |    0.9871 |              0.9852 | 0.04895 |   0.9508 |       0.9355 | 0.9431 |
| hybrid_polynomial_residual_new      |            62 |              0.9177 |    0.9634 |              0.9489 | 0.07061 |   0.8923 |       0.9355 | 0.9134 |
| hybrid_polynomial_residual_new      |            64 |              0.9111 |    0.9803 |              0.9835 | 0.05767 |   0.8861 |       0.9722 | 0.9272 |
| hybrid_polynomial_residual_new      |            65 |              0.8636 |    0.9669 |              0.9688 | 0.08054 |   0.8429 |       0.8939 | 0.8676 |
| mlp                                 |            50 |              0.9671 |    0.9891 |              0.9899 | 0.04235 |   0.9583 |       0.9787 | 0.9684 |
| mlp                                 |            51 |              0.9212 |    0.9808 |              0.9852 | 0.0573  |   0.9245 |       0.9423 | 0.9333 |
| mlp                                 |            52 |              0.8902 |    0.9716 |              0.9743 | 0.07399 |   0.88   |       0.9167 | 0.898  |
| mlp                                 |            53 |              0.9067 |    0.962  |              0.9505 | 0.07268 |   0.84   |       0.9767 | 0.9032 |
| mlp                                 |            54 |              0.8733 |    0.9468 |              0.9332 | 0.08354 |   0.8163 |       0.9302 | 0.8696 |
| mlp                                 |            55 |              0.8781 |    0.9538 |              0.9402 | 0.08366 |   0.7885 |       0.9762 | 0.8723 |
| mlp                                 |            56 |              0.8829 |    0.9486 |              0.9074 | 0.07979 |   0.8448 |       0.98   | 0.9074 |
| mlp                                 |            57 |              0.9486 |    0.9923 |              0.9907 | 0.03987 |   0.9091 |       0.9756 | 0.9412 |
| mlp                                 |            58 |              0.9015 |    0.9715 |              0.9693 | 0.065   |   0.8732 |       0.9394 | 0.9051 |
| mlp                                 |            60 |              0.9329 |    0.98   |              0.9753 | 0.05595 |   0.9077 |       0.9516 | 0.9291 |
| mlp                                 |            62 |              0.8892 |    0.9514 |              0.9306 | 0.07844 |   0.8406 |       0.9355 | 0.8855 |
| mlp                                 |            64 |              0.8806 |    0.9743 |              0.9776 | 0.06728 |   0.8608 |       0.9444 | 0.9007 |
| mlp                                 |            65 |              0.8258 |    0.9162 |              0.9111 | 0.1137  |   0.7654 |       0.9394 | 0.8435 |
| ridge                               |            50 |              0.9232 |    0.9905 |              0.9921 | 0.04839 |   0.9    |       0.9574 | 0.9278 |
| ridge                               |            51 |              0.9212 |    0.9659 |              0.9688 | 0.06627 |   0.9245 |       0.9423 | 0.9333 |
| ridge                               |            52 |              0.9006 |    0.9735 |              0.9738 | 0.06477 |   0.8824 |       0.9375 | 0.9091 |
| ridge                               |            53 |              0.9476 |    0.9843 |              0.9814 | 0.05207 |   0.913  |       0.9767 | 0.9438 |
| ridge                               |            54 |              0.9082 |    0.9597 |              0.9467 | 0.07296 |   0.8269 |       1      | 0.9053 |
| ridge                               |            55 |              0.9081 |    0.969  |              0.9615 | 0.07051 |   0.8367 |       0.9762 | 0.9011 |
| ridge                               |            56 |              0.9562 |    0.9671 |              0.9229 | 0.05565 |   0.96   |       0.96   | 0.96   |
| ridge                               |            57 |              0.9486 |    0.9876 |              0.9826 | 0.0429  |   0.9091 |       0.9756 | 0.9412 |
| ridge                               |            58 |              0.947  |    0.978  |              0.9741 | 0.05739 |   0.9275 |       0.9697 | 0.9481 |
| ridge                               |            60 |              0.9311 |    0.9864 |              0.9845 | 0.04875 |   0.9344 |       0.9194 | 0.9268 |
| ridge                               |            62 |              0.9106 |    0.965  |              0.9532 | 0.06945 |   0.8788 |       0.9355 | 0.9062 |
| ridge                               |            64 |              0.8931 |    0.9759 |              0.9763 | 0.05988 |   0.8554 |       0.9861 | 0.9161 |
| ridge                               |            65 |              0.9167 |    0.9736 |              0.9699 | 0.06494 |   0.8571 |       1      | 0.9231 |
| traditional_deltae_depth_likelihood |            50 |              0.8348 |    0.8634 |              0.8076 | 0.1404  |   0.7857 |       0.9362 | 0.8544 |
| traditional_deltae_depth_likelihood |            51 |              0.8327 |    0.8269 |              0.8128 | 0.1537  |   0.8491 |       0.8654 | 0.8571 |
| traditional_deltae_depth_likelihood |            52 |              0.8333 |    0.8423 |              0.8052 | 0.1502  |   0.8    |       0.9167 | 0.8544 |
| traditional_deltae_depth_likelihood |            53 |              0.8659 |    0.8643 |              0.738  | 0.1315  |   0.7778 |       0.9767 | 0.866  |
| traditional_deltae_depth_likelihood |            54 |              0.7976 |    0.7897 |              0.6492 | 0.184   |   0.74   |       0.8605 | 0.7957 |
| traditional_deltae_depth_likelihood |            55 |              0.8205 |    0.8129 |              0.6526 | 0.1666  |   0.7551 |       0.881  | 0.8132 |
| traditional_deltae_depth_likelihood |            56 |              0.8429 |    0.8481 |              0.7748 | 0.1379  |   0.8333 |       0.9    | 0.8654 |
| traditional_deltae_depth_likelihood |            57 |              0.8482 |    0.8623 |              0.8029 | 0.1431  |   0.75   |       0.9512 | 0.8387 |
| traditional_deltae_depth_likelihood |            58 |              0.8712 |    0.8875 |              0.8263 | 0.1241  |   0.8551 |       0.8939 | 0.8741 |
| traditional_deltae_depth_likelihood |            60 |              0.8963 |    0.9205 |              0.8622 | 0.09749 |   0.8529 |       0.9355 | 0.8923 |
| traditional_deltae_depth_likelihood |            62 |              0.8535 |    0.8818 |              0.8296 | 0.1276  |   0.7838 |       0.9355 | 0.8529 |
| traditional_deltae_depth_likelihood |            64 |              0.7639 |    0.772  |              0.6924 | 0.1839  |   0.7561 |       0.8611 | 0.8052 |
| traditional_deltae_depth_likelihood |            65 |              0.8106 |    0.8099 |              0.6854 | 0.1599  |   0.7595 |       0.9091 | 0.8276 |

## Systematics and caveats

This closes the specific #2385 split caveat: there are now multiple literal
source/acquisition runs and every run is held out once.  It does not claim that
the mounted GEANT4 generator ROOT itself contains DAQ acquisition IDs; the IDs
come from the raw waveform digitization bridge and are exposed in the truth event
table for leakage control.  The feature set contains GEANT4 truth-derived energy
and timing summaries because this ticket asks for a truth-split artifact; it is
therefore a method-comparison closure test, not a deployable online PID
classifier.  Bootstrap CIs measure transfer across the available acquisition
runs and do not include GEANT4 physics-list or detector-material uncertainty.

Runtime was `76.0` s on `Linux-5.15.0-139-generic-x86_64-with-glibc2.35`.
