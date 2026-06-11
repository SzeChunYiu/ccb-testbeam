# S10o: anomaly-residual current excess truth split

- **Ticket:** `1781052597.584.1a7d14cf`
- **Worker:** `testbeam-laptop-4`
- **Raw data:** B-stack HRD ROOT files for runs 44-57 from `data/root/root`.
- **Primary split:** source run held out. High-current runs are scored by templates and ML/NN models trained only from low-current runs 46 and 47; low-current controls leave their own run out.
- **Primary metric:** matched high-current minus low-current residual secondary-fraction delta with source-run bootstrap 95% confidence intervals.

## Abstract

The S10o question is whether the S10e/S10f anomaly-residual current excess is better explained by beam pile-up, baseline pathology, charge support drift, topology composition, or the P09 anomaly taxon itself. The raw ROOT reproduction gate passes, with downstream selected-event fractions 0.02312 at 2 nA and 0.03341 at 20 nA. The operational winner is **traditional** under the predeclared rule: rank secondary-fraction delta; promote an ML/NN method only if leakage checks pass and its ML-minus-traditional run-bootstrap CI is wholly positive.

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

## Results

8 matched support strata pass the low/high count floor. The dominant three cells carry 0.949 of the matched support weight.

### Method Benchmark

| method                 |   secondary_fraction_delta | secondary_fraction_ci   |   overlap_score_delta | overlap_score_ci    |   support_accept_fraction |   synthetic_auc |   synthetic_brier |   secondary_fraction_mae |
|:-----------------------|---------------------------:|:------------------------|----------------------:|:--------------------|--------------------------:|----------------:|------------------:|-------------------------:|
| traditional            |                    0.01972 | [-0.00739, 0.04813]     |               0.01540 | [-0.01911, 0.04910] |                   1.00000 |       nan       |         nan       |                nan       |
| ridge                  |                    0.02344 | [0.01467, 0.03179]      |               0.05178 | [0.02967, 0.07557]  |                   0.55832 |         0.81780 |           0.16957 |                  0.11912 |
| gradient_boosted_trees |                    0.01133 | [0.00789, 0.01440]      |               0.02627 | [0.01863, 0.03438]  |                   0.55832 |         0.92164 |           0.11299 |                  0.07565 |
| mlp                    |                   -0.00239 | [-0.00845, 0.00518]     |               0.03920 | [0.02184, 0.05576]  |                   0.55832 |         0.90194 |           0.12098 |                  0.09330 |
| cnn1d                  |                    0.00974 | [0.00043, 0.01981]      |               0.00444 | [-0.02739, 0.03513] |                   0.55832 |         0.74108 |           0.21350 |                  0.13875 |
| residual_tcn           |                    0.00094 | [-0.01991, 0.02551]     |              -0.00695 | [-0.06232, 0.04496] |                   0.55832 |         0.74017 |           0.21309 |                  0.13947 |

### ML Minus Traditional

| method_metric                             |    delta |   ci_low |   ci_high |   n_bootstrap |
|:------------------------------------------|---------:|---------:|----------:|--------------:|
| ridge_secondary_fraction                  |  0.00371 | -0.02593 |   0.03155 |           520 |
| gradient_boosted_trees_secondary_fraction | -0.00839 | -0.03425 |   0.01670 |           520 |
| mlp_secondary_fraction                    | -0.02211 | -0.04239 |  -0.00081 |           520 |
| cnn1d_secondary_fraction                  | -0.00999 | -0.04128 |   0.01874 |           520 |
| residual_tcn_secondary_fraction           | -0.01878 | -0.03430 |  -0.00278 |           520 |

### Residual Truth Split

Dominant atom by component, ranked by support-preserving secondary-fraction excess:

| component            | dominant_atom        |   secondary_fraction_delta |   ci_low |   ci_high |   share_of_total_effect |   support_fraction |
|:---------------------|:---------------------|---------------------------:|---------:|----------:|------------------------:|-------------------:|
| topology_composition | p02_broad_late       |                    0.02011 | -0.00643 |   0.04727 |                 1.01969 |            0.64904 |
| baseline_pathology   | s16_no_lowering      |                    0.01980 | -0.00769 |   0.04837 |                 1.00379 |            0.46279 |
| anomaly_taxonomy     | p09_broad_late       |                    0.01974 | -0.00902 |   0.04786 |                 1.00078 |            0.53079 |
| charge_support_drift | amp_ge_4500          |                    0.01832 |  0.00619 |   0.03339 |                 0.92907 |            0.36839 |
| beam_pileup          | pileup_not_supported |                    0.00001 |  0.00000 |   0.00002 |                 0.00037 |            0.55504 |

Top atom-level contributions:

| component            | atom_level             |   n_events |   composition_delta |   secondary_fraction_delta |   ci_low |   ci_high |   charge_log_shift |   timing_tail_delta |
|:---------------------|:-----------------------|-----------:|--------------------:|---------------------------:|---------:|----------:|-------------------:|--------------------:|
| topology_composition | p02_broad_late         |       8189 |             0.00000 |                    0.02011 | -0.00643 |   0.04727 |            0.01143 |             0.00000 |
| baseline_pathology   | s16_no_lowering        |       5839 |             0.00000 |                    0.01980 | -0.00769 |   0.04837 |            0.01085 |             0.00000 |
| anomaly_taxonomy     | p09_broad_late         |       6697 |             0.00000 |                    0.01974 | -0.00902 |   0.04786 |            0.01121 |             0.00000 |
| charge_support_drift | amp_ge_4500            |       4648 |             0.00000 |                    0.01832 |  0.00619 |   0.03339 |            0.01264 |            -0.00011 |
| charge_support_drift | amp_2500_4500          |       3423 |             0.00000 |                    0.00119 | -0.01819 |   0.01963 |           -0.00243 |            -0.00056 |
| charge_support_drift | amp_1000_2500          |       4546 |             0.00000 |                    0.00021 | -0.00037 |   0.00081 |            0.00009 |             0.00008 |
| beam_pileup          | pileup_not_supported   |       7003 |            -0.03717 |                    0.00001 |  0.00000 |   0.00002 |           -0.11192 |             0.00007 |
| baseline_pathology   | s16_large_lowering     |       5920 |             0.00000 |                   -0.00002 | -0.00019 |   0.00013 |           -0.00091 |            -0.00060 |
| anomaly_taxonomy     | p09_baseline_pathology |       5920 |             0.00000 |                   -0.00002 | -0.00018 |   0.00012 |           -0.00091 |            -0.00060 |
| baseline_pathology   | s16_mild_lowering      |        858 |             0.00000 |                   -0.00006 | -0.00016 |   0.00007 |            0.00035 |             0.00000 |
| topology_composition | p02_early_pathology    |       4428 |             0.00000 |                   -0.00039 | -0.00071 |  -0.00029 |           -0.00113 |            -0.00060 |
| beam_pileup          | pileup_like_high       |       5496 |             0.03847 |                   -0.00861 | -0.01659 |   0.00123 |            0.03756 |            -0.00012 |
| beam_pileup          | pileup_like_low        |        118 |            -0.00130 |                   -0.02220 | -0.04598 |   0.00154 |           -0.06815 |             0.00000 |

### Residual-Current Knockouts and Sentinels

| variant                   |   n_features |   current_auc |   current_ap |   brier |   predicted_high_minus_low | interpretation                                                 |
|:--------------------------|-------------:|--------------:|-------------:|--------:|---------------------------:|:---------------------------------------------------------------|
| full                      |           23 |       0.38902 |      0.86628 | 0.08695 |                   -0.02297 | all non-identifier residual atoms and waveform summaries       |
| taxon_knockout            |           21 |       0.38902 |      0.86628 | 0.08695 |                   -0.02297 | full model with P09/anomaly taxon indicators removed           |
| charge_knockout           |           17 |       0.38649 |      0.86759 | 0.08708 |                   -0.02523 | full model with amplitude and charge-support variables removed |
| topology_only             |            5 |       0.58912 |      0.90678 | 0.24462 |                    0.01913 | composition/topology stress test                               |
| amplitude_only            |            3 |       0.58691 |      0.91230 | 0.25030 |                   -0.00884 | charge-support-only stress test                                |
| run_only_sentinel         |            1 |       0.84625 |      0.98623 | 0.19122 |                    0.40621 | run-number leakage sentinel                                    |
| shuffled_current_sentinel |           23 |       0.48233 |      0.91772 | 0.24947 |                    0.00009 | permuted-current falsification sentinel                        |

### Traditional Threshold and Support Stability

| support_choice   |   n_strata |   trad_score_threshold |   secondary_fraction_delta |   ci_low |   ci_high |
|:-----------------|-----------:|-----------------------:|---------------------------:|---------:|----------:|
| all_matched      |          8 |                0.00000 |                    0.01972 | -0.00605 |   0.04796 |
| all_matched      |          8 |                0.00500 |                    0.01969 | -0.00676 |   0.04697 |
| all_matched      |          8 |                0.01500 |                    0.02002 | -0.00701 |   0.04692 |
| all_matched      |          8 |                0.03000 |                    0.02056 | -0.00706 |   0.04822 |
| all_matched      |          8 |                0.06000 |                    0.02060 | -0.00684 |   0.04885 |
| dominant_three   |          3 |                0.00000 |                    0.01980 | -0.00588 |   0.04561 |
| dominant_three   |          3 |                0.00500 |                    0.01979 | -0.00713 |   0.04671 |
| dominant_three   |          3 |                0.01500 |                    0.02023 | -0.00899 |   0.04684 |
| dominant_three   |          3 |                0.03000 |                    0.02074 | -0.00718 |   0.04866 |
| dominant_three   |          3 |                0.06000 |                    0.02082 | -0.00593 |   0.04891 |
| dominant_one     |          1 |                0.00000 |                    0.01836 |  0.00668 |   0.03022 |
| dominant_one     |          1 |                0.00500 |                    0.01836 |  0.00660 |   0.03195 |
| dominant_one     |          1 |                0.01500 |                    0.01836 |  0.00736 |   0.03105 |
| dominant_one     |          1 |                0.03000 |                    0.01836 |  0.00574 |   0.03238 |
| dominant_one     |          1 |                0.06000 |                    0.01836 |  0.00557 |   0.02966 |

| diagnostic                              |   value | unit                                                   |
|:----------------------------------------|--------:|:-------------------------------------------------------|
| traditional_threshold_sensitivity_slope | 0.01650 | secondary_fraction_delta_per_sse_improvement_threshold |
| traditional_threshold_range             | 0.00091 | secondary_fraction_delta                               |

### Fold Diagnostics

| method                 |   synthetic_auc |   synthetic_ap |   synthetic_brier |   secondary_fraction_mae |   support_accept_fraction |
|:-----------------------|----------------:|---------------:|------------------:|-------------------------:|--------------------------:|
| cnn1d                  |         0.74108 |        0.78593 |           0.21350 |                  0.13875 |                   0.55832 |
| gradient_boosted_trees |         0.92164 |        0.92737 |           0.11299 |                  0.07565 |                   0.55832 |
| mlp                    |         0.90194 |        0.90528 |           0.12098 |                  0.09330 |                   0.55832 |
| residual_tcn           |         0.74017 |        0.77826 |           0.21309 |                  0.13947 |                   0.55832 |
| ridge                  |         0.81780 |        0.82673 |           0.16957 |                  0.11912 |                   0.55832 |

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
| mean_shuffled_label_synthetic_auc                          | 0.51902 | False  | The permuted-label control should stay near chance on held-out synthetic overlays.                   |
| ridge_current_auc_from_secondary_fraction                  | 0.58759 | False  | Flagged if the method nearly identifies beam current from the secondary-fraction output.             |
| gradient_boosted_trees_current_auc_from_secondary_fraction | 0.65964 | False  | Flagged if the method nearly identifies beam current from the secondary-fraction output.             |
| mlp_current_auc_from_secondary_fraction                    | 0.52715 | False  | Flagged if the method nearly identifies beam current from the secondary-fraction output.             |
| cnn1d_current_auc_from_secondary_fraction                  | 0.61727 | False  | Flagged if the method nearly identifies beam current from the secondary-fraction output.             |
| residual_tcn_current_auc_from_secondary_fraction           | 0.46846 | False  | Flagged if the method nearly identifies beam current from the secondary-fraction output.             |

## Conclusion

The raw-ROOT S10 topology reproduction passes before model fitting. The traditional bounded two-pulse fit gives a matched high-minus-low secondary-fraction delta of 0.01972 [-0.00739, 0.04813]. The largest support-preserving residual atom is topology_composition/p02_broad_late with delta 0.02011 [-0.00643, 0.04727]. The point-estimate winner is ridge, but the operational winner recorded for this ticket is traditional because the promotion rule requires clean leakage checks and an ML-minus-traditional CI wholly above zero. The selected winner has secondary-fraction delta 0.01972 [-0.00739, 0.04813], support acceptance 1.000, and overlap-score delta 0.01540.

## Artifacts

`result.json`, `manifest.json`, `input_sha256.csv`, `reproduction_match_table.csv`, `method_summary.csv`, `method_deltas_vs_traditional.csv`, `truth_split_decomposition.csv`, `truth_split_component_summary.csv`, `residual_current_ml_panel.csv`, `traditional_stability_scan.csv`, `sampled_event_scores.csv.gz`, `fold_diagnostics.csv`, `leakage_checks.csv`, and figures are in this report directory.
