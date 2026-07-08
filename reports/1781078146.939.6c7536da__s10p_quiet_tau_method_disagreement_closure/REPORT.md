# S10p: quiet-tau method-disagreement closure

- **Ticket:** `1781078146.939.6c7536da`
- **Worker:** `testbeam-laptop-4`
- **Raw data:** B-stack HRD ROOT files for runs 44-57 from `data/root/root`.
- **Primary split:** source run held out. High-current runs are scored by templates and ML/NN models trained only from low-current runs 46 and 47; low-current controls leave their own run out.
- **Primary metric:** matched high-current minus low-current residual secondary-fraction delta with source-run bootstrap 95% confidence intervals.

## Abstract

The S10p question is whether the S10e/S10f quiet-tau method disagreement is better explained by beam pile-up, baseline pathology, charge support drift, topology composition, or the P09 anomaly taxon itself. The raw ROOT reproduction gate passes, with downstream selected-event fractions 0.02312 at 2 nA and 0.03341 at 20 nA. The operational winner is **traditional** under the predeclared rule: rank secondary-fraction delta; promote an ML/NN method only if leakage checks pass and its ML-minus-traditional run-bootstrap CI is wholly positive.

## Reproduction From Raw ROOT

Events are read from the `h101` tree. Each event is reshaped to eight HRD channels by eighteen samples; B-stack staves B2/B4/B6/B8 are selected, a four-sample median pedestal is subtracted, and selected pulses require amplitude above 1000 ADC. This reproduces the documented S10 topology quantities before any model is trained.

| quantity                                 |   report_value |   reproduced |    delta |   tolerance | pass   |
|:-----------------------------------------|---------------:|-------------:|---------:|------------:|:-------|
| low_2nA multi_stave_per_selected_event   |        0.01560 |      0.01559 | -0.00001 |     0.00150 | True   |
| low_2nA three_stave_per_selected_event   |        0.00410 |      0.00411 |  0.00001 |     0.00150 | True   |
| low_2nA downstream_per_selected_event    |        0.02310 |      0.02312 |  0.00002 |     0.00150 | True   |
| high_20nA multi_stave_per_selected_event |        0.02680 |      0.02681 |  0.00001 |     0.00150 | True   |
| high_20nA three_stave_per_selected_event |        0.00850 |      0.00854 |  0.00004 |     0.00150 | True   |
| high_20nA downstream_per_selected_event  |        0.03340 |      0.03341 |  0.00001 |     0.00150 | True   |

## Methods

### Strata and Estimand

The support cells are the Cartesian product of amplitude bin, adaptive-lowering bin, and P02-style topology. Let \(s\) index matched strata and \(w_s = \min(n_{s,L}, n_{s,H}) / \sum_j \min(n_{j,L}, n_{j,H})\). For a method output \(m_i\), the estimand is

\[ \Delta_m = \sum_s w_s \left( \bar m_{s,H} - \bar m_{s,L} \right). \]

Run-bootstrap intervals resample low-current and high-current source runs separately, preserving all scored events from a sampled run. This treats run-to-run current/composition variability as the uncertainty unit.

For the truth split, atom labels \(a\) are introduced one axis at a time while keeping the same \(w_s\). The atom-specific residual contribution is

\[ \Delta_{m,a} = \sum_s w_s \{ E(m \mid H,s,a)-E(m \mid L,s,a) \}, \]

and the composition drift term is \(\sum_s w_s[P(a\mid H,s)-P(a\mid L,s)]\). This separates response changes within matched support from high-current migration among atom levels.

### Traditional Method

The traditional comparator is the bounded two-pulse template fit. For each held-out run, empirical templates are built from low-current training pulses only. A one-pulse model and a two-pulse model are fitted by least squares over a bounded grid of first-pulse shifts and separations. With waveform \(y(t)\), normalized template \(q(t)\), amplitudes \(a_1,a_2\), baseline \(b\), and delay \(\tau\), the two-pulse objective is

\[ \min_{a_1,a_2,b,t_1,\tau} \sum_t \{y(t)-a_1 q(t-t_1)-a_2 q(t-t_1-\tau)-b\}^2, \]

subject to positive amplitudes, bounded baseline, and a finite secondary-to-primary ratio. The reported secondary fraction is \(a_2/(a_1+a_2)\), attenuated when the two-pulse SSE improvement is below the nominal threshold. Stability is tested by scanning the SSE-improvement threshold and by restricting to the dominant matched support cells.

### ML and Neural Methods

All learned models use synthetic overlays generated only from training-run low-current pulses. The synthetic target is independent of the real-current label: clean pulses have class 0 and fraction 0; injected overlays have class 1 and known secondary fraction. Feature models use normalized 18-sample waveform values plus transparent shape and one-pulse residual summaries. Neural models consume the normalized 18-sample sequence.

- `ridge`: standardized logistic regression for overlap and ridge regression for secondary fraction.
- `gradient_boosted_trees`: histogram gradient-boosted classifier/regressor.
- `mlp`: two-layer fully connected classifier/regressor.
- `cnn1d`: compact 1D convolutional multitask network.
- `residual_tcn`: a small dilated residual temporal CNN, included as the new sequence architecture because the pulse has ordered samples but only eighteen time bins.

A robust support mask uses a robust z-distance to train-fold feature medians and accepts real events inside the 95th percentile of training support. Identifier, run, current, group, downstream label, and stratum labels are excluded from model inputs.

The residual-current diagnostic panel trains run-heldout classifiers for full, taxon-knockout, charge-knockout, topology-only, amplitude-only, run-only, and shuffled-current variants. These are not promoted as physics truth labels; they are falsification and attribution stress tests for the atom decomposition.

### Quiet-Tau Closure Metrics

The ticket-specific closure panel compares the bounded-template quiet-tau gate against each learned tau-like overlap score. The traditional positive gate is `secondary_fraction >= 0.03` or SSE-improvement `>= 0.015`; learned scores are thresholded at their low-current 90th percentile. The reported quiet-disagreement rate is the high-minus-low rate of events where the learned method is positive while the traditional gate is quiet.

## Results

8 matched support strata pass the low/high count floor. The dominant three cells carry 0.949 of the matched support weight.

### Method Benchmark

| method                 |   secondary_fraction_delta | secondary_fraction_ci   |   overlap_score_delta | overlap_score_ci     |   support_accept_fraction |   synthetic_auc |   synthetic_brier |   secondary_fraction_mae |
|:-----------------------|---------------------------:|:------------------------|----------------------:|:---------------------|--------------------------:|----------------:|------------------:|-------------------------:|
| traditional            |                    0.01307 | [-0.01927, 0.04506]     |               0.01220 | [-0.02353, 0.05259]  |                   1.00000 |       nan       |         nan       |                nan       |
| ridge                  |                    0.01640 | [0.00733, 0.02658]      |               0.02757 | [-0.00023, 0.05639]  |                   0.55913 |         0.82493 |           0.16472 |                  0.11925 |
| gradient_boosted_trees |                    0.00782 | [0.00543, 0.01019]      |               0.03152 | [0.02544, 0.03817]   |                   0.55913 |         0.92523 |           0.10865 |                  0.07623 |
| mlp                    |                    0.00118 | [-0.00282, 0.01085]     |              -0.01036 | [-0.02900, 0.00084]  |                   0.55913 |         0.90749 |           0.11533 |                  0.09321 |
| cnn1d                  |                    0.01176 | [-0.00702, 0.02506]     |               0.01677 | [-0.03182, 0.05596]  |                   0.55913 |         0.73867 |           0.21437 |                  0.13666 |
| residual_tcn           |                   -0.01876 | [-0.03487, -0.00009]    |              -0.06787 | [-0.13075, -0.00199] |                   0.55913 |         0.74310 |           0.21443 |                  0.13802 |

### ML Minus Traditional

| method_metric                             |    delta |   ci_low |   ci_high |   n_bootstrap |
|:------------------------------------------|---------:|---------:|----------:|--------------:|
| ridge_secondary_fraction                  |  0.00333 | -0.03196 |   0.03723 |           520 |
| gradient_boosted_trees_secondary_fraction | -0.00524 | -0.03950 |   0.02551 |           520 |
| mlp_secondary_fraction                    | -0.01188 | -0.03939 |   0.02033 |           520 |
| cnn1d_secondary_fraction                  | -0.00130 | -0.05047 |   0.03632 |           520 |
| residual_tcn_secondary_fraction           | -0.03182 | -0.07401 |   0.01401 |           520 |

### Residual Truth Split

Dominant atom by component, ranked by support-preserving secondary-fraction excess:

| component            | dominant_atom    |   secondary_fraction_delta |   ci_low |   ci_high |   share_of_total_effect |   support_fraction |
|:---------------------|:-----------------|---------------------------:|---------:|----------:|------------------------:|-------------------:|
| topology_composition | p02_broad_late   |                    0.01352 | -0.01853 |   0.04685 |                 1.03484 |            0.64904 |
| baseline_pathology   | s16_no_lowering  |                    0.01324 | -0.01959 |   0.04324 |                 1.01295 |            0.46279 |
| anomaly_taxonomy     | p09_broad_late   |                    0.01316 | -0.01983 |   0.04631 |                 1.00719 |            0.53079 |
| charge_support_drift | amp_ge_4500      |                    0.01056 | -0.00774 |   0.02908 |                 0.80826 |            0.36839 |
| beam_pileup          | pileup_like_high |                    0.01032 |  0.00364 |   0.01745 |                 0.79020 |            0.43465 |

Top atom-level contributions:

| component            | atom_level             |   n_events |   composition_delta |   secondary_fraction_delta |   ci_low |   ci_high |   charge_log_shift |   timing_tail_delta |
|:---------------------|:-----------------------|-----------:|--------------------:|---------------------------:|---------:|----------:|-------------------:|--------------------:|
| topology_composition | p02_broad_late         |       8189 |             0.00000 |                    0.01352 | -0.01853 |   0.04685 |            0.02064 |             0.00000 |
| baseline_pathology   | s16_no_lowering        |       5839 |             0.00000 |                    0.01324 | -0.01959 |   0.04324 |            0.02004 |             0.00000 |
| anomaly_taxonomy     | p09_broad_late         |       6697 |             0.00000 |                    0.01316 | -0.01983 |   0.04631 |            0.02041 |             0.00000 |
| charge_support_drift | amp_ge_4500            |       4648 |             0.00000 |                    0.01056 | -0.00774 |   0.02908 |            0.01798 |            -0.00018 |
| beam_pileup          | pileup_like_high       |       5484 |             0.00947 |                    0.01032 |  0.00364 |   0.01745 |            0.02388 |            -0.00012 |
| charge_support_drift | amp_2500_4500          |       3423 |             0.00000 |                    0.00185 | -0.01544 |   0.01887 |            0.00314 |            -0.00047 |
| charge_support_drift | amp_1000_2500          |       4546 |             0.00000 |                    0.00066 |  0.00005 |   0.00124 |           -0.00128 |             0.00011 |
| beam_pileup          | pileup_not_supported   |       7003 |            -0.00995 |                    0.00001 |  0.00000 |   0.00002 |            0.02726 |             0.00021 |
| baseline_pathology   | s16_mild_lowering      |        858 |             0.00000 |                   -0.00008 | -0.00016 |   0.00005 |            0.00037 |             0.00000 |
| baseline_pathology   | s16_large_lowering     |       5920 |             0.00000 |                   -0.00009 | -0.00026 |   0.00005 |           -0.00058 |            -0.00053 |
| anomaly_taxonomy     | p09_baseline_pathology |       5920 |             0.00000 |                   -0.00009 | -0.00027 |   0.00006 |           -0.00058 |            -0.00053 |
| topology_composition | p02_early_pathology    |       4428 |             0.00000 |                   -0.00046 | -0.00076 |  -0.00037 |           -0.00081 |            -0.00053 |
| beam_pileup          | pileup_like_low        |        130 |             0.00048 |                   -0.03064 | -0.04537 |  -0.00153 |           -0.08970 |             0.00000 |

### Quiet-Tau Disagreement Closure

| method                 |   candidate_rate_delta |   candidate_rate_ci_low |   candidate_rate_ci_high |   quiet_disagreement_rate_delta |   quiet_disagreement_ci_low |   quiet_disagreement_ci_high |   method_traditional_jaccard |   support_shift_energy_distance |   brier_improvement_vs_025 |
|:-----------------------|-----------------------:|------------------------:|-------------------------:|--------------------------------:|----------------------------:|-----------------------------:|-----------------------------:|--------------------------------:|---------------------------:|
| traditional            |               -0.11841 |                -0.17316 |                 -0.08385 |                         0.00000 |                     0.00000 |                      0.00000 |                      1.00000 |                         0.13154 |                  nan       |
| ridge                  |                0.07705 |                 0.05500 |                  0.10807 |                         0.05902 |                     0.03648 |                      0.09158 |                      0.09433 |                         0.09101 |                    0.08528 |
| gradient_boosted_trees |                0.06703 |                 0.01247 |                  0.15054 |                         0.05142 |                     0.00009 |                      0.12908 |                      0.04170 |                         0.16867 |                    0.14135 |
| mlp                    |                0.03029 |                 0.00888 |                  0.05682 |                         0.03100 |                     0.00989 |                      0.05919 |                      0.05084 |                         0.07712 |                    0.13467 |
| cnn1d                  |                0.06577 |                -0.04280 |                  0.13835 |                         0.07026 |                     0.01212 |                      0.11177 |                      0.08983 |                         0.08871 |                    0.03563 |
| residual_tcn           |               -0.00546 |                -0.04812 |                  0.04812 |                        -0.01037 |                    -0.06474 |                      0.06702 |                      0.03851 |                         0.08152 |                    0.03557 |

### Residual-Current Knockouts and Sentinels

| variant                   |   n_features |   current_auc |   current_ap |   brier |   predicted_high_minus_low | interpretation                                                 |
|:--------------------------|-------------:|--------------:|-------------:|--------:|---------------------------:|:---------------------------------------------------------------|
| full                      |           23 |       0.36708 |      0.86276 | 0.08754 |                   -0.02896 | all non-identifier residual atoms and waveform summaries       |
| taxon_knockout            |           21 |       0.36708 |      0.86276 | 0.08754 |                   -0.02896 | full model with P09/anomaly taxon indicators removed           |
| charge_knockout           |           17 |       0.37150 |      0.86245 | 0.08743 |                   -0.02911 | full model with amplitude and charge-support variables removed |
| topology_only             |            5 |       0.58895 |      0.90538 | 0.24503 |                    0.01628 | composition/topology stress test                               |
| amplitude_only            |            3 |       0.58414 |      0.91215 | 0.25012 |                   -0.00797 | charge-support-only stress test                                |
| run_only_sentinel         |            1 |       0.84625 |      0.98623 | 0.19122 |                    0.40621 | run-number leakage sentinel                                    |
| shuffled_current_sentinel |           23 |       0.54818 |      0.92594 | 0.24906 |                    0.00558 | permuted-current falsification sentinel                        |

### Traditional Threshold and Support Stability

| support_choice   |   n_strata |   trad_score_threshold |   secondary_fraction_delta |   ci_low |   ci_high |
|:-----------------|-----------:|-----------------------:|---------------------------:|---------:|----------:|
| all_matched      |          8 |                0.00000 |                    0.01307 | -0.01783 |   0.04632 |
| all_matched      |          8 |                0.00500 |                    0.01304 | -0.01811 |   0.04560 |
| all_matched      |          8 |                0.01500 |                    0.01337 | -0.02041 |   0.04685 |
| all_matched      |          8 |                0.03000 |                    0.01401 | -0.01820 |   0.04783 |
| all_matched      |          8 |                0.06000 |                    0.01386 | -0.01847 |   0.04846 |
| dominant_three   |          3 |                0.00000 |                    0.01324 | -0.01871 |   0.04522 |
| dominant_three   |          3 |                0.00500 |                    0.01324 | -0.01824 |   0.04598 |
| dominant_three   |          3 |                0.01500 |                    0.01367 | -0.02077 |   0.04530 |
| dominant_three   |          3 |                0.03000 |                    0.01428 | -0.02038 |   0.04881 |
| dominant_three   |          3 |                0.06000 |                    0.01415 | -0.02043 |   0.04903 |
| dominant_one     |          1 |                0.00000 |                    0.01063 | -0.00791 |   0.03010 |
| dominant_one     |          1 |                0.00500 |                    0.01063 | -0.00595 |   0.02729 |
| dominant_one     |          1 |                0.01500 |                    0.01063 | -0.00766 |   0.02960 |
| dominant_one     |          1 |                0.03000 |                    0.01063 | -0.00564 |   0.02976 |
| dominant_one     |          1 |                0.06000 |                    0.01060 | -0.00625 |   0.02781 |

| diagnostic                              |   value | unit                                                   |
|:----------------------------------------|--------:|:-------------------------------------------------------|
| traditional_threshold_sensitivity_slope | 0.01536 | secondary_fraction_delta_per_sse_improvement_threshold |
| traditional_threshold_range             | 0.00097 | secondary_fraction_delta                               |

### Fold Diagnostics

| method                 |   synthetic_auc |   synthetic_ap |   synthetic_brier |   secondary_fraction_mae |   support_accept_fraction |
|:-----------------------|----------------:|---------------:|------------------:|-------------------------:|--------------------------:|
| cnn1d                  |         0.73867 |        0.77675 |           0.21437 |                  0.13666 |                   0.55913 |
| gradient_boosted_trees |         0.92523 |        0.93362 |           0.10865 |                  0.07623 |                   0.55913 |
| mlp                    |         0.90749 |        0.90658 |           0.11533 |                  0.09321 |                   0.55913 |
| residual_tcn           |         0.74310 |        0.77384 |           0.21443 |                  0.13802 |                   0.55913 |
| ridge                  |         0.82493 |        0.83178 |           0.16472 |                  0.11925 |                   0.55913 |

## Systematics and Caveats

- The real-current endpoint is a waveform diagnostic, not truth-labelled beam pile-up. Synthetic overlays validate method response but do not prove the physical secondary rate.
- Atom names are mechanistic hypotheses. The beam-pileup atom is based on two-pulse support from the traditional fit, not a hidden Monte Carlo truth field.
- The anomaly taxon split is rule-based from the same waveform summaries used by P09-style audits; it should not be reified as a causal truth label.
- Only runs 46 and 47 provide low-current training support for high-current scoring, so run-bootstrap intervals remain broad even with many events.
- The threshold scan shows how sensitive the traditional excess is to the two-pulse SSE-improvement gate; adoption should prefer stable sign and magnitude over point estimates.
- Support acceptance is model-feature support, not detector acceptance. It catches gross extrapolation but cannot identify all hidden DAQ/current confounds.
- The timing-tail and charge rows are proxy deltas weighted by method secondary fractions; they are risk indicators, not calibrated timing or energy biases.

## Leakage and Falsification Checks

| check                                                      |   value | flag   | note                                                                                                 |
|:-----------------------------------------------------------|--------:|:-------|:-----------------------------------------------------------------------------------------------------|
| heldout_run_excluded_from_template_and_ml_training         | 1.00000 | False  | Every fold uses low-current source runs only and removes the held-out low-current run from controls. |
| identifier_features_excluded                               | 1.00000 | False  | ML features exclude run, event number, current, group, downstream label, and stratum labels.         |
| mean_shuffled_label_synthetic_auc                          | 0.48067 | False  | The permuted-label control should stay near chance on held-out synthetic overlays.                   |
| ridge_current_auc_from_secondary_fraction                  | 0.59038 | False  | Flagged if the method nearly identifies beam current from the secondary-fraction output.             |
| gradient_boosted_trees_current_auc_from_secondary_fraction | 0.65204 | False  | Flagged if the method nearly identifies beam current from the secondary-fraction output.             |
| mlp_current_auc_from_secondary_fraction                    | 0.55421 | False  | Flagged if the method nearly identifies beam current from the secondary-fraction output.             |
| cnn1d_current_auc_from_secondary_fraction                  | 0.60350 | False  | Flagged if the method nearly identifies beam current from the secondary-fraction output.             |
| residual_tcn_current_auc_from_secondary_fraction           | 0.40331 | False  | Flagged if the method nearly identifies beam current from the secondary-fraction output.             |

## Conclusion

The raw-ROOT S10 topology reproduction passes before model fitting. The traditional bounded two-pulse fit gives a matched high-minus-low secondary-fraction delta of 0.01307 [-0.01927, 0.04506]. The largest support-preserving residual atom is topology_composition/p02_broad_late with delta 0.01352 [-0.01853, 0.04685]. The point-estimate winner is ridge, but the operational winner recorded for this ticket is traditional because the promotion rule requires clean leakage checks and an ML-minus-traditional CI wholly above zero. The selected winner has secondary-fraction delta 0.01307 [-0.01927, 0.04506], support acceptance 1.000, and overlap-score delta 0.01220. The largest learned quiet-tau disagreement rate delta is cnn1d at 0.07026.

## Artifacts

`result.json`, `manifest.json`, `input_sha256.csv`, `reproduction_match_table.csv`, `method_summary.csv`, `method_deltas_vs_traditional.csv`, `quiet_tau_closure.csv`, `truth_split_decomposition.csv`, `truth_split_component_summary.csv`, `residual_current_ml_panel.csv`, `traditional_stability_scan.csv`, `sampled_event_scores.csv.gz`, `fold_diagnostics.csv`, `leakage_checks.csv`, and figures are in this report directory.
