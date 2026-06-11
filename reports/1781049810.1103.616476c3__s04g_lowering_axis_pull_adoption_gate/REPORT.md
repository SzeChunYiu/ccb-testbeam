# Study report: S04g - lowering-axis pull calibration adoption gate

- **Study ID:** S04g
- **Ticket:** 1781049810.1103.616476c3
- **Author:** testbeam-laptop-3
- **Date:** 2026-06-11
- **Depends on:** S04c lowering-axis tail separation and S04f pull-width calibration map
- **Input:** raw B-stack ROOT files under `data/root/root`
- **Config:** `configs/s04g_1781049810_1103_616476c3_lowering_axis_pull_adoption_gate.yaml`
- **Git commit:** `2b724bab9ebf6876347fa8c7a7cf26fe9d0b00e4`

## 0. Question

Does the S04c/S16 adaptive-lowering axis provide a run-transportable per-pulse timing uncertainty ledger without replacing the S03 central time model?

Pre-registered metrics from the ticket are held-out pull width, expected calibration error for `P(|error| > 5 ns)`, tail capture after rejecting the highest-risk 5% of pulses, and delta sigma68. All headline intervals below are run-block bootstrap confidence intervals across held-out Sample-II runs.

## 1. Reproduction from raw ROOT

The gate independently reopens `h101/HRDv`, reshapes each event to `(8, 18)`, subtracts the median of samples 0--3, and counts B-stave pulses with amplitude above 1000 ADC before fitting any model.

| quantity                           |   report_value |   reproduced |   delta |   tolerance | pass   |
|:-----------------------------------|---------------:|-------------:|--------:|------------:|:-------|
| total selected B-stave pulses      |         640737 |       640737 |       0 |           0 | True   |
| sample_ii_analysis selected_pulses |         125096 |       125096 |       0 |           0 | True   |
| sample_ii_analysis B2              |          88213 |        88213 |       0 |           0 | True   |
| sample_ii_analysis B4              |          21229 |        21229 |       0 |           0 | True   |
| sample_ii_analysis B6              |          11148 |        11148 |       0 |           0 | True   |
| sample_ii_analysis B8              |           4506 |         4506 |       0 |           0 | True   |

## 2. Estimand and equations

The central point-time model is unchanged from S03. For event `e` and downstream stave `s`, `u_es = t^S03_es - z_s v_TOF`, with `v_TOF = 0.078 ns/cm`. The self-supervised residual target is `r_es = u_es - (1/2) sum_{q != s} u_eq`. A method predicts residual location `mu_es` and scale `sigma_es`; evaluation uses `epsilon_es = r_es - mu_es` and pull `p_es = epsilon_es / sigma_es`.

The adaptive-lowering scalar is recomputed from each raw-selected corrected waveform. Since lowering is invariant to the unknown additive pedestal seed, the script applies the S16 adaptive-pedestal rule to the median-subtracted waveform with seed zero. The S04c bins are `none <= 0 ADC`, `small <= 250 ADC`, `medium <= 800 ADC`, and `large > 800 ADC`.

The primary calibration score is `|sigma68(p)-1| + |C68-0.6827| + |C90-0.90| + |C95-0.95| + 0.01 median(sigma)`. Tail probability is `P(|epsilon| > 5 ns) = erfc(5/(sqrt(2) sigma))`; ECE uses decile bins of this probability.

## 3. Methods

Traditional method: a hierarchical robust width map trained only on the training runs. It stratifies by `(stave, lowering_axis, amplitude quartile, q_template tertile, peak-phase bin)` with fallback through coarser lowering-aware strata. Its location is the train median residual and its uncertainty is train sigma68.

ML/NN methods: ridge and histogram gradient-boosted trees train residual means and conformal log-absolute-residual scales. The MLP, 1D-CNN, and new gated waveform-tabular CNN train heteroskedastic Gaussian residual heads. All receive train-run conformal scaling. Features are same-pulse waveform, amplitude/shape/stave/template-quality, and lowering-axis variables; no event id, run id, target residual, or other-stave time is supplied.

## 4. Head-to-head benchmark

| method                              | family                         |   primary_score |   primary_score_ci_low |   primary_score_ci_high |   pull_sigma68 |   pull_sigma68_ci_low |   pull_sigma68_ci_high |   coverage95 |   tail_probability_ece |   tail_probability_ece_ci_low |   tail_probability_ece_ci_high |   tail_capture_at_95_acceptance |   tail_capture_at_95_acceptance_ci_low |   tail_capture_at_95_acceptance_ci_high |
|:------------------------------------|:-------------------------------|----------------:|-----------------------:|------------------------:|---------------:|----------------------:|-----------------------:|-------------:|-----------------------:|------------------------------:|-------------------------------:|--------------------------------:|---------------------------------------:|----------------------------------------:|
| cnn_1d_heteroskedastic              | cnn_1d                         |       0.13228   |              0.111709  |                0.335681 |       1.01006  |              0.921365 |                1.10735 |     0.896248 |             0.0115707  |                    0.010347   |                      0.0126272 |                        0.390533 |                               0.323795 |                                0.474519 |
| gated_waveform_tabular_cnn          | new_gated_waveform_tabular_cnn |       0.0551598 |              0.0446109 |                0.295115 |       1.00095  |              0.908561 |                1.11116 |     0.934206 |             0.00953242 |                    0.00574464 |                      0.0184098 |                        0.286996 |                               0.201881 |                                0.378278 |
| gradient_boosted_trees_conformal    | gradient_boosted_trees         |       0.101548  |              0.0655747 |                0.32106  |       1.01832  |              0.940888 |                1.12676 |     0.917627 |             0.0100654  |                    0.00823818 |                      0.0118378 |                        0.505952 |                               0.475728 |                                0.529412 |
| mlp_heteroskedastic                 | mlp                            |       0.0762874 |              0.0635458 |                0.345539 |       0.997205 |              0.9073   |                1.14422 |     0.921815 |             0.00981872 |                    0.00764807 |                      0.0117756 |                        0.375    |                               0.266635 |                                0.474896 |
| ridge_conformal                     | ridge                          |       0.0556123 |              0.0467751 |                0.195404 |       0.990248 |              0.924794 |                1.06722 |     0.931239 |             0.0115633  |                    0.0103487  |                      0.0133898 |                        0.35443  |                               0.284722 |                                0.435065 |
| traditional_stratified_robust_width | traditional                    |       0.183315  |              0.10626   |                0.405176 |       1.04072  |              0.973226 |                1.14972 |     0.891449 |             0.0122487  |                    0.0102143  |                      0.0148626 |                        0.205882 |                               0.161677 |                                0.26816  |

Winner named in `result.json`: **gated_waveform_tabular_cnn**. Traditional comparison: `winner_and_traditional_ci_overlap`. The adoption verdict is `lowering_axis_ml_point_winner_ci_overlaps_traditional`.

## 5. Lowering-axis diagnostics

| method                              | lowering_axis   |    n |   tail_rate_abs_error_gt5ns |   mean_tail_probability_gt5ns |   tail_probability_ece |   tail_capture_at_95_acceptance |
|:------------------------------------|:----------------|-----:|----------------------------:|------------------------------:|-----------------------:|--------------------------------:|
| cnn_1d_heteroskedastic              | large           |  465 |                   0.0301075 |                   0.0290262   |             0.02236    |                       0.285714  |
| cnn_1d_heteroskedastic              | medium          |  706 |                   0.0184136 |                   0.00621361  |             0.0122007  |                       0.538462  |
| cnn_1d_heteroskedastic              | none            | 9240 |                   0.0124459 |                   0.00128479  |             0.0111611  |                       0.391304  |
| cnn_1d_heteroskedastic              | small           | 1049 |                   0.0257388 |                   0.00633363  |             0.0194111  |                       0.37037   |
| gated_waveform_tabular_cnn          | large           |  465 |                   0.0322581 |                   0.0528209   |             0.0284059  |                       0.2       |
| gated_waveform_tabular_cnn          | medium          |  706 |                   0.0169972 |                   0.00873527  |             0.00984972 |                       0.583333  |
| gated_waveform_tabular_cnn          | none            | 9240 |                   0.0181818 |                   0.00701573  |             0.0111661  |                       0.261905  |
| gated_waveform_tabular_cnn          | small           | 1049 |                   0.0266921 |                   0.017354    |             0.0110197  |                       0.214286  |
| gradient_boosted_trees_conformal    | large           |  465 |                   0.0344086 |                   0.00795772  |             0.0264509  |                       0.5625    |
| gradient_boosted_trees_conformal    | medium          |  706 |                   0.0212465 |                   0.00868726  |             0.0125592  |                       0.666667  |
| gradient_boosted_trees_conformal    | none            | 9240 |                   0.0117965 |                   0.00377099  |             0.00802555 |                       0.431193  |
| gradient_boosted_trees_conformal    | small           | 1049 |                   0.0266921 |                   0.00760005  |             0.019092   |                       0.607143  |
| mlp_heteroskedastic                 | large           |  465 |                   0.0322581 |                   0.0173496   |             0.016391   |                       0.6       |
| mlp_heteroskedastic                 | medium          |  706 |                   0.0169972 |                   0.00735946  |             0.00977455 |                       0.5       |
| mlp_heteroskedastic                 | none            | 9240 |                   0.0150433 |                   0.00533999  |             0.0097033  |                       0.359712  |
| mlp_heteroskedastic                 | small           | 1049 |                   0.0247855 |                   0.0160845   |             0.0117607  |                       0.269231  |
| ridge_conformal                     | large           |  465 |                   0.0322581 |                   0.0164823   |             0.0157757  |                       0.733333  |
| ridge_conformal                     | medium          |  706 |                   0.0155807 |                   0.00724331  |             0.00833742 |                       0.545455  |
| ridge_conformal                     | none            | 9240 |                   0.0114719 |                   0.00108988  |             0.010382   |                       0.311321  |
| ridge_conformal                     | small           | 1049 |                   0.0247855 |                   0.00251231  |             0.0222732  |                       0.269231  |
| traditional_stratified_robust_width | large           |  465 |                   0.0322581 |                   3.90721e-62 |             0.0322581  |                       0.0666667 |
| traditional_stratified_robust_width | medium          |  706 |                   0.0169972 |                   3.50341e-56 |             0.0169972  |                       0.0833333 |
| traditional_stratified_robust_width | none            | 9240 |                   0.0127706 |                   0.00494773  |             0.00994556 |                       0.29661   |
| traditional_stratified_robust_width | small           | 1049 |                   0.0238322 |                   4.37737e-07 |             0.0238318  |                       0.08      |

## 6. Negative controls and leakage checks

| method                        | family                  |   primary_score |   primary_score_ci_low |   primary_score_ci_high |   pull_sigma68 |   coverage95 |
|:------------------------------|:------------------------|----------------:|-----------------------:|------------------------:|---------------:|-------------:|
| control_shuffled_target_ridge | control_shuffled_target |       0.0689091 |              0.0644158 |                0.483093 |       0.991874 |     0.935777 |
| control_amplitude_only_ridge  | control_amplitude_only  |       0.0874665 |              0.0805328 |                0.508081 |       0.99893  |     0.916405 |
| control_run_only_width        | control_run_only        |       0.133744  |              0.0920973 |                0.475523 |       1.00375  |     0.92164  |
| control_sample_permuted_cnn   | control_sample_permuted |       0.172444  |              0.107841  |                0.420176 |       1.02705  |     0.89363  |
| control_phase_scrambled_cnn   | control_phase_scrambled |       0.178247  |              0.105966  |                0.445725 |       1.02826  |     0.893717 |

|   heldout_run | check                          |   value | pass   | detail                                                                                                                                                            |
|--------------:|:-------------------------------|--------:|:-------|:------------------------------------------------------------------------------------------------------------------------------------------------------------------|
|            58 | feature_audit                  |      39 | True   | features are same-pulse waveform/shape/amplitude/stave/template-quality quantities; no event id, target residual, other-stave time, or held-out-run label is used |
|            58 | train_heldout_event_id_overlap |       0 | True   | nan                                                                                                                                                               |
|            58 | train_heldout_run_overlap      |       0 | True   | nan                                                                                                                                                               |
|            59 | feature_audit                  |      39 | True   | features are same-pulse waveform/shape/amplitude/stave/template-quality quantities; no event id, target residual, other-stave time, or held-out-run label is used |
|            59 | train_heldout_event_id_overlap |       0 | True   | nan                                                                                                                                                               |
|            59 | train_heldout_run_overlap      |       0 | True   | nan                                                                                                                                                               |
|            60 | feature_audit                  |      39 | True   | features are same-pulse waveform/shape/amplitude/stave/template-quality quantities; no event id, target residual, other-stave time, or held-out-run label is used |
|            60 | train_heldout_event_id_overlap |       0 | True   | nan                                                                                                                                                               |
|            60 | train_heldout_run_overlap      |       0 | True   | nan                                                                                                                                                               |
|            61 | feature_audit                  |      39 | True   | features are same-pulse waveform/shape/amplitude/stave/template-quality quantities; no event id, target residual, other-stave time, or held-out-run label is used |
|            61 | train_heldout_event_id_overlap |       0 | True   | nan                                                                                                                                                               |
|            61 | train_heldout_run_overlap      |       0 | True   | nan                                                                                                                                                               |
|            62 | feature_audit                  |      39 | True   | features are same-pulse waveform/shape/amplitude/stave/template-quality quantities; no event id, target residual, other-stave time, or held-out-run label is used |
|            62 | train_heldout_event_id_overlap |       0 | True   | nan                                                                                                                                                               |
|            62 | train_heldout_run_overlap      |       0 | True   | nan                                                                                                                                                               |
|            63 | feature_audit                  |      39 | True   | features are same-pulse waveform/shape/amplitude/stave/template-quality quantities; no event id, target residual, other-stave time, or held-out-run label is used |
|            63 | train_heldout_event_id_overlap |       0 | True   | nan                                                                                                                                                               |
|            63 | train_heldout_run_overlap      |       0 | True   | nan                                                                                                                                                               |
|            65 | feature_audit                  |      39 | True   | features are same-pulse waveform/shape/amplitude/stave/template-quality quantities; no event id, target residual, other-stave time, or held-out-run label is used |
|            65 | train_heldout_event_id_overlap |       0 | True   | nan                                                                                                                                                               |
|            65 | train_heldout_run_overlap      |       0 | True   | nan                                                                                                                                                               |

Falsifier: if a destroyed-signal control beat the best production method, or if the production winner did not improve the lowering-aware traditional width map even as a point estimate, the ML adoption claim would be rejected. The best control is recorded in `result.json`; the conclusion remains cautious because the winner and traditional intervals overlap.

## 7. Per-run held-out metrics

|   heldout_run | method                              |   primary_score |   pull_sigma68 |   coverage68 |   coverage90 |   coverage95 |   pred_sigma_median_ns |   pairwise_sigma68_ns |   n_pulses |
|--------------:|:------------------------------------|----------------:|---------------:|-------------:|-------------:|-------------:|-----------------------:|----------------------:|-----------:|
|            58 | control_shuffled_target_ridge       |       0.0923837 |       0.972571 |     0.675799 |     0.926941 |     0.96347  |               1.76428  |              1.20576  |        219 |
|            58 | gradient_boosted_trees_conformal    |       0.102156  |       0.978605 |     0.666667 |     0.858447 |     0.936073 |               0.924814 |              1.11953  |        219 |
|            58 | control_amplitude_only_ridge        |       0.161847  |       0.933578 |     0.707763 |     0.940639 |     0.96347  |               1.62531  |              1.48382  |        219 |
|            58 | traditional_stratified_robust_width |       0.173464  |       0.911892 |     0.684932 |     0.876712 |     0.894977 |               0.481439 |              0.848037 |        219 |
|            58 | control_run_only_width              |       0.179824  |       0.931474 |     0.616438 |     0.926941 |     0.949772 |               1.78669  |              1.18748  |        219 |
|            58 | mlp_heteroskedastic                 |       0.32797   |       0.788934 |     0.762557 |     0.922374 |     0.949772 |               1.44439  |              1.18633  |        219 |
|            58 | ridge_conformal                     |       0.338448  |       0.783751 |     0.757991 |     0.931507 |     0.954338 |               1.10636  |              1.11288  |        219 |
|            58 | gated_waveform_tabular_cnn          |       0.354871  |       0.819534 |     0.794521 |     0.936073 |     0.958904 |               1.76071  |              1.18502  |        219 |
|            58 | cnn_1d_heteroskedastic              |       0.402282  |       0.748798 |     0.785388 |     0.931507 |     0.954338 |               1.25474  |              0.824603 |        219 |
|            58 | control_sample_permuted_cnn         |       0.490449  |       0.665843 |     0.803653 |     0.922374 |     0.949772 |               1.27362  |              1.03162  |        219 |
|            58 | control_phase_scrambled_cnn         |       0.495246  |       0.670808 |     0.803653 |     0.926941 |     0.945205 |               1.33653  |              0.961575 |        219 |
|            59 | cnn_1d_heteroskedastic              |       0.0518112 |       0.982744 |     0.681957 |     0.915247 |     0.958497 |               1.00682  |              1.13557  |       2289 |
|            59 | control_phase_scrambled_cnn         |       0.0544461 |       1.01648  |     0.668851 |     0.910441 |     0.953692 |               0.998063 |              1.18059  |       2289 |
|            59 | ridge_conformal                     |       0.0688158 |       0.976698 |     0.692879 |     0.912189 |     0.961118 |               1.20275  |              1.31492  |       2289 |
|            59 | control_sample_permuted_cnn         |       0.072313  |       0.968077 |     0.67453  |     0.913936 |     0.957623 |               1.06605  |              1.19251  |       2289 |
|            59 | control_run_only_width              |       0.079969  |       0.954441 |     0.669288 |     0.903014 |     0.949323 |               1.73063  |              1.45871  |       2289 |
|            59 | mlp_heteroskedastic                 |       0.0980725 |       0.959787 |     0.696811 |     0.922237 |     0.960245 |               1.1267   |              1.34614  |       2289 |
|            59 | traditional_stratified_robust_width |       0.111776  |       0.965585 |     0.69419  |     0.878113 |     0.918305 |               1.22894  |              1.21914  |       2289 |
|            59 | gated_waveform_tabular_cnn          |       0.129488  |       0.947029 |     0.70817  |     0.927042 |     0.958497 |               1.55081  |              1.43545  |       2289 |
|            59 | gradient_boosted_trees_conformal    |       0.149393  |       0.90889  |     0.707733 |     0.91481  |     0.95806  |               1.03799  |              1.03754  |       2289 |
|            59 | control_shuffled_target_ridge       |       0.18544   |       0.915589 |     0.716033 |     0.931411 |     0.968545 |               1.77393  |              1.49653  |       2289 |
|            59 | control_amplitude_only_ridge        |       0.267429  |       0.878612 |     0.746614 |     0.944954 |     0.970293 |               1.688    |              1.64155  |       2289 |
|            60 | control_amplitude_only_ridge        |       0.0670039 |       0.975799 |     0.689356 |     0.910891 |     0.960396 |               1.48593  |              1.47623  |       2424 |
|            60 | traditional_stratified_robust_width |       0.105655  |       0.991616 |     0.686881 |     0.865099 |     0.903053 |               1.12417  |              1.22443  |       2424 |
|            60 | gradient_boosted_trees_conformal    |       0.105739  |       0.933723 |     0.70297  |     0.903465 |     0.944719 |               1.0446   |              1.11837  |       2424 |
|            60 | control_sample_permuted_cnn         |       0.118367  |       0.928812 |     0.686469 |     0.920792 |     0.961634 |               1.0984   |              1.23931  |       2424 |
|            60 | control_run_only_width              |       0.11983   |       0.934774 |     0.653465 |     0.89934  |     0.942244 |               1.69542  |              1.3437   |       2424 |
|            60 | ridge_conformal                     |       0.157005  |       0.908516 |     0.721947 |     0.912954 |     0.948845 |               1.21652  |              1.3298   |       2424 |
|            60 | cnn_1d_heteroskedastic              |       0.178455  |       0.88867  |     0.699257 |     0.924092 |     0.965759 |               1.0716   |              1.14719  |       2424 |
|            60 | gated_waveform_tabular_cnn          |       0.18671   |       0.903362 |     0.704208 |     0.932343 |     0.969472 |               1.67485  |              1.37855  |       2424 |
|            60 | control_phase_scrambled_cnn         |       0.187179  |       0.889329 |     0.70462  |     0.929455 |     0.963696 |               1.14365  |              1.11549  |       2424 |
|            60 | mlp_heteroskedastic                 |       0.20999   |       0.893747 |     0.730198 |     0.927805 |     0.965759 |               1.26749  |              1.17215  |       2424 |
|            60 | control_shuffled_target_ridge       |       0.227357  |       0.891712 |     0.732261 |     0.931931 |     0.970297 |               1.72807  |              1.29837  |       2424 |
|            61 | ridge_conformal                     |       0.26454   |       1.11255  |     0.618435 |     0.853876 |     0.919257 |               1.08544  |              1.26411  |       2799 |
|            61 | cnn_1d_heteroskedastic              |       0.407891  |       1.19274  |     0.600572 |     0.825295 |     0.902465 |               1.07867  |              1.30788  |       2799 |
|            61 | gradient_boosted_trees_conformal    |       0.433367  |       1.20293  |     0.598785 |     0.822079 |     0.890675 |               0.927317 |              1.06998  |       2799 |
|            61 | mlp_heteroskedastic                 |       0.503833  |       1.26023  |     0.576277 |     0.819936 |     0.905681 |               1.27985  |              1.31476  |       2799 |
|            61 | control_sample_permuted_cnn         |       0.533469  |       1.27685  |     0.562701 |     0.824223 |     0.899964 |               1.08087  |              1.23988  |       2799 |
|            61 | gated_waveform_tabular_cnn          |       0.562082  |       1.24229  |     0.566988 |     0.784209 |     0.876742 |               1.50346  |              1.54409  |       2799 |
|            61 | traditional_stratified_robust_width |       0.585079  |       1.24258  |     0.589139 |     0.773848 |     0.838156 |               1.09405  |              1.25157  |       2799 |
|            61 | control_phase_scrambled_cnn         |       0.594026  |       1.29829  |     0.552697 |     0.80493  |     0.890675 |               1.13399  |              1.26736  |       2799 |
|            61 | control_run_only_width              |       0.773677  |       1.35524  |     0.52483  |     0.770275 |     0.837442 |               1.82864  |              2.12996  |       2799 |
|            61 | control_shuffled_target_ridge       |       0.797776  |       1.36887  |     0.499821 |     0.7592   |     0.863165 |               1.839    |              2.08256  |       2799 |
|            61 | control_amplitude_only_ridge        |       0.828873  |       1.44927  |     0.522687 |     0.773848 |     0.872812 |               1.62497  |              2.21564  |       2799 |
|            62 | control_sample_permuted_cnn         |       0.0226584 |       0.996367 |     0.679471 |     0.904998 |     0.95126  |               0.953876 |              1.20531  |       2421 |
|            62 | gradient_boosted_trees_conformal    |       0.0429803 |       0.984485 |     0.685254 |     0.893846 |     0.941347 |               1.01036  |              1.11662  |       2421 |
|            62 | control_phase_scrambled_cnn         |       0.0612825 |       0.97075  |     0.675341 |     0.908715 |     0.954977 |               1.09803  |              1.24044  |       2421 |
|            62 | cnn_1d_heteroskedastic              |       0.0685593 |       0.969928 |     0.69145  |     0.911194 |     0.957869 |               1.0675   |              1.17056  |       2421 |
|            62 | mlp_heteroskedastic                 |       0.0965115 |       0.965536 |     0.692276 |     0.924411 |     0.963651 |               1.44084  |              1.31305  |       2421 |
|            62 | ridge_conformal                     |       0.100917  |       0.955304 |     0.704667 |     0.913259 |     0.959108 |               1.18862  |              1.30781  |       2421 |
|            62 | control_run_only_width              |       0.103524  |       0.948317 |     0.654688 |     0.903346 |     0.952912 |               1.75718  |              1.469    |       2421 |
|            62 | traditional_stratified_robust_width |       0.121089  |       0.981135 |     0.690624 |     0.859975 |     0.907476 |               1.1751   |              1.23559  |       2421 |
|            62 | gated_waveform_tabular_cnn          |       0.136873  |       0.935762 |     0.690624 |     0.930194 |     0.968195 |               1.63227  |              1.50253  |       2421 |
|            62 | control_shuffled_target_ridge       |       0.190384  |       0.916357 |     0.704254 |     0.940933 |     0.976456 |               1.77972  |              1.4914   |       2421 |
|            62 | control_amplitude_only_ridge        |       0.192484  |       0.919871 |     0.720777 |     0.934325 |     0.973565 |               1.63894  |              1.65042  |       2421 |
|            63 | gradient_boosted_trees_conformal    |       0.0274847 |       0.996315 |     0.681081 |     0.895495 |     0.942342 |               1.00188  |              1.1246   |       1110 |
|            63 | ridge_conformal                     |       0.0364868 |       0.987745 |     0.682883 |     0.908108 |     0.945946 |               1.18866  |              1.3934   |       1110 |
|            63 | control_phase_scrambled_cnn         |       0.0809908 |       0.94909  |     0.681081 |     0.906306 |     0.937838 |               0.999367 |              1.1824   |       1110 |
|            63 | control_sample_permuted_cnn         |       0.113357  |       0.932205 |     0.709009 |     0.904505 |     0.945946 |               1.06945  |              1.29967  |       1110 |
|            63 | control_run_only_width              |       0.114109  |       0.908922 |     0.68018  |     0.902703 |     0.95045  |               1.73583  |              1.39132  |       1110 |
|            63 | cnn_1d_heteroskedastic              |       0.117846  |       0.934754 |     0.70991  |     0.912613 |     0.952252 |               1.05251  |              1.06862  |       1110 |
|            63 | traditional_stratified_robust_width |       0.126984  |       0.971312 |     0.691892 |     0.864865 |     0.908108 |               1.20775  |              1.28876  |       1110 |
|            63 | mlp_heteroskedastic                 |       0.158281  |       0.913601 |     0.718919 |     0.921622 |     0.952252 |               1.17886  |              1.25171  |       1110 |
|            63 | gated_waveform_tabular_cnn          |       0.162464  |       0.920017 |     0.718919 |     0.922523 |     0.958559 |               1.51817  |              1.25263  |       1110 |
|            63 | control_shuffled_target_ridge       |       0.180531  |       0.916891 |     0.711712 |     0.933333 |     0.967568 |               1.75094  |              1.41854  |       1110 |
|            63 | control_amplitude_only_ridge        |       0.357589  |       0.81139  |     0.778378 |     0.936937 |     0.969369 |               1.69944  |              1.58226  |       1110 |
|            65 | gradient_boosted_trees_conformal    |       0.0750614 |       1.02733  |     0.666667 |     0.888889 |     0.939394 |               0.998417 |              1.12403  |        198 |
|            65 | control_sample_permuted_cnn         |       0.108283  |       1.02746  |     0.671717 |     0.924242 |     0.984848 |               1.07508  |              1.2331   |        198 |
|            65 | control_run_only_width              |       0.117451  |       0.933363 |     0.686869 |     0.914141 |     0.964646 |               1.78577  |              1.49464  |        198 |
|            65 | traditional_stratified_robust_width |       0.125255  |       1.01555  |     0.666667 |     0.868687 |     0.89899  |               1.13464  |              1.2563   |        198 |
|            65 | control_shuffled_target_ridge       |       0.141497  |       0.965098 |     0.70202  |     0.944444 |     0.974747 |               1.80833  |              1.48228  |        198 |
|            65 | ridge_conformal                     |       0.182018  |       0.943536 |     0.722222 |     0.939394 |     0.984848 |               1.17891  |              1.39367  |        198 |
|            65 | control_phase_scrambled_cnn         |       0.18676   |       0.876785 |     0.717172 |     0.90404  |     0.964646 |               1.03862  |              1.30561  |        198 |
|            65 | cnn_1d_heteroskedastic              |       0.251227  |       0.817832 |     0.722222 |     0.90404  |     0.964646 |               1.08502  |              1.26171  |        198 |
|            65 | mlp_heteroskedastic                 |       0.2642    |       0.851098 |     0.732323 |     0.929293 |     0.969697 |               1.66846  |              1.47473  |        198 |
|            65 | control_amplitude_only_ridge        |       0.316792  |       0.860043 |     0.757576 |     0.949495 |     0.984848 |               1.7615   |              1.68934  |        198 |
|            65 | gated_waveform_tabular_cnn          |       0.341769  |       0.793325 |     0.737374 |     0.944444 |     0.969697 |               1.62786  |              1.4215   |        198 |

## 8. Systematics and caveats

The target is a downstream closure residual, not an external timing truth; common event-time motion is invisible. The seven-run bootstrap is a stability interval, not a guarantee for future beam conditions. Tail probability comes from calibrated residual sigma under a Gaussian residual approximation, so it is a risk ledger rather than a physical tail generator. The lowering axis is recomputed from selected downstream pulses only; B2-only high-lowering pathologies can still require separate support checks. Multiple production methods are compared, so the CI-overlap verdict is intentionally more conservative than the point-score ranking.

## 9. Findings and next step

The lowering-aware benchmark names gated_waveform_tabular_cnn as the point-score winner (primary score 0.0552, CI [0.0446, 0.2951]) against the traditional lowering-aware robust width map at 0.1833. The CI relation is winner_and_traditional_ci_overlap; therefore S04g supports a calibrated uncertainty ledger, not an unconditional central-time replacement.

Hypothesis: large adaptive lowering is better treated as a heteroskedastic timing-risk axis than as evidence for a universal residual correction.

Queued follow-up in `result.json` and the ticket queue: a support-preserving lowering-axis adoption test that freezes the winner and measures downstream charge/current/topology bias under the same 95% acceptance rule.

## 10. Reproducibility

```bash
python3 -m venv --system-site-packages .venv-s04g-sys
PYTHON_KEYRING_BACKEND=keyring.backends.null.Keyring .venv-s04g-sys/bin/python -m pip install --disable-pip-version-check --no-input uproot tabulate
MPLCONFIGDIR=/tmp/matplotlib-s04g .venv-s04g-sys/bin/python scripts/s04g_1781049810_1103_616476c3_lowering_axis_pull_adoption_gate.py --config configs/s04g_1781049810_1103_616476c3_lowering_axis_pull_adoption_gate.yaml
```

Artifacts: `result.json`, `manifest.json`, `reproduction_match_table.csv`, `downstream_counts_by_run.csv`, `heldout_run_summary.csv`, `pooled_method_summary.csv`, `tail_probability_summary.csv`, `lowering_axis_tail_summary.csv`, `heldout_pulse_predictions.csv.gz`, `stratified_width_map.csv`, `leakage_checks.csv`, `input_sha256.csv`, and PNG figures.
