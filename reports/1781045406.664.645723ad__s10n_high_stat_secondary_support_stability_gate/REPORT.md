# S10n: high-stat secondary support stability gate

- **Ticket:** `1781045406.664.645723ad`
- **Worker:** `testbeam-laptop-3`
- **Raw data:** B-stack HRD ROOT files for runs 44-57 from `data/root/root`.
- **Primary split:** source run held out. High-current runs are scored by templates and ML/NN models trained only from low-current runs 46 and 47; low-current controls leave their own run out.
- **Primary metric:** matched high-current minus low-current secondary-fraction delta with source-run bootstrap 95% confidence intervals.

## Abstract

The S10n question is whether the S10e/S11b high-current two-pulse-like excess is a stable measured waveform support effect or a threshold/model artifact. The raw ROOT reproduction gate passes, with downstream selected-event fractions 0.02312 at 2 nA and 0.03341 at 20 nA. The operational winner is **traditional** under the predeclared rule: rank secondary-fraction delta; promote an ML/NN method only if leakage checks pass and its ML-minus-traditional run-bootstrap CI is wholly positive.

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

## Results

8 matched support strata pass the low/high count floor. The dominant three cells carry 0.949 of the matched support weight.

### Method Benchmark

| method                 |   secondary_fraction_delta | secondary_fraction_ci   |   overlap_score_delta | overlap_score_ci     |   support_accept_fraction |   synthetic_auc |   synthetic_brier |   secondary_fraction_mae |
|:-----------------------|---------------------------:|:------------------------|----------------------:|:---------------------|--------------------------:|----------------:|------------------:|-------------------------:|
| traditional            |                    0.01751 | [-0.00908, 0.04335]     |               0.00918 | [-0.02132, 0.03666]  |                   1.00000 |       nan       |         nan       |                nan       |
| ridge                  |                    0.01590 | [0.01006, 0.02213]      |               0.03491 | [0.01333, 0.05749]   |                   0.55628 |         0.82531 |           0.16267 |                  0.11734 |
| gradient_boosted_trees |                    0.00672 | [0.00193, 0.01020]      |               0.02210 | [0.01153, 0.03225]   |                   0.55628 |         0.92724 |           0.10623 |                  0.07539 |
| mlp                    |                   -0.00212 | [-0.01064, 0.01420]     |              -0.01440 | [-0.06506, 0.03503]  |                   0.55628 |         0.91162 |           0.11292 |                  0.09055 |
| cnn1d                  |                   -0.01071 | [-0.05649, 0.03242]     |              -0.05304 | [-0.17391, 0.06919]  |                   0.55628 |         0.75447 |           0.21094 |                  0.13666 |
| residual_tcn           |                   -0.02537 | [-0.04003, -0.01090]    |              -0.13942 | [-0.19889, -0.08048] |                   0.55628 |         0.76350 |           0.20903 |                  0.13386 |

### ML Minus Traditional

| method_metric                             |    delta |   ci_low |   ci_high |   n_bootstrap |
|:------------------------------------------|---------:|---------:|----------:|--------------:|
| ridge_secondary_fraction                  | -0.00161 | -0.02640 |   0.02042 |           700 |
| gradient_boosted_trees_secondary_fraction | -0.01079 | -0.03174 |   0.00755 |           700 |
| mlp_secondary_fraction                    | -0.01963 | -0.03440 |   0.00017 |           700 |
| cnn1d_secondary_fraction                  | -0.02823 | -0.05619 |   0.00063 |           700 |
| residual_tcn_secondary_fraction           | -0.04289 | -0.06341 |  -0.02184 |           700 |

### Traditional Threshold and Support Stability

| support_choice   |   n_strata |   trad_score_threshold |   secondary_fraction_delta |   ci_low |   ci_high |
|:-----------------|-----------:|-----------------------:|---------------------------:|---------:|----------:|
| all_matched      |          8 |                0.00000 |                    0.01751 | -0.00717 |   0.04124 |
| all_matched      |          8 |                0.00500 |                    0.01749 | -0.00690 |   0.04119 |
| all_matched      |          8 |                0.01500 |                    0.01764 | -0.00857 |   0.03989 |
| all_matched      |          8 |                0.03000 |                    0.01804 | -0.00880 |   0.04445 |
| all_matched      |          8 |                0.06000 |                    0.01766 | -0.00673 |   0.04107 |
| dominant_three   |          3 |                0.00000 |                    0.01761 | -0.00896 |   0.04168 |
| dominant_three   |          3 |                0.00500 |                    0.01761 | -0.00471 |   0.04223 |
| dominant_three   |          3 |                0.01500 |                    0.01786 | -0.00599 |   0.04164 |
| dominant_three   |          3 |                0.03000 |                    0.01822 | -0.00646 |   0.04402 |
| dominant_three   |          3 |                0.06000 |                    0.01790 | -0.00475 |   0.04218 |
| dominant_one     |          1 |                0.00000 |                    0.01777 |  0.00317 |   0.03272 |
| dominant_one     |          1 |                0.00500 |                    0.01777 |  0.00360 |   0.03141 |
| dominant_one     |          1 |                0.01500 |                    0.01777 |  0.00367 |   0.03217 |
| dominant_one     |          1 |                0.03000 |                    0.01777 |  0.00359 |   0.03282 |
| dominant_one     |          1 |                0.06000 |                    0.01773 |  0.00342 |   0.03272 |

| diagnostic                              |   value | unit                                                   |
|:----------------------------------------|--------:|:-------------------------------------------------------|
| traditional_threshold_sensitivity_slope | 0.00398 | secondary_fraction_delta_per_sse_improvement_threshold |
| traditional_threshold_range             | 0.00054 | secondary_fraction_delta                               |

### Fold Diagnostics

| method                 |   synthetic_auc |   synthetic_ap |   synthetic_brier |   secondary_fraction_mae |   support_accept_fraction |
|:-----------------------|----------------:|---------------:|------------------:|-------------------------:|--------------------------:|
| cnn1d                  |         0.75447 |        0.79533 |           0.21094 |                  0.13666 |                   0.55628 |
| gradient_boosted_trees |         0.92724 |        0.93322 |           0.10623 |                  0.07539 |                   0.55628 |
| mlp                    |         0.91162 |        0.90728 |           0.11292 |                  0.09055 |                   0.55628 |
| residual_tcn           |         0.76350 |        0.79563 |           0.20903 |                  0.13386 |                   0.55628 |
| ridge                  |         0.82531 |        0.84282 |           0.16267 |                  0.11734 |                   0.55628 |

## Systematics and Caveats

- The real-current endpoint is a waveform diagnostic, not truth-labelled beam pile-up. Synthetic overlays validate method response but do not prove the physical secondary rate.
- Only runs 46 and 47 provide low-current training support for high-current scoring, so run-bootstrap intervals remain broad even with many events.
- The threshold scan shows how sensitive the traditional excess is to the two-pulse SSE-improvement gate; adoption should prefer stable sign and magnitude over point estimates.
- Support acceptance is model-feature support, not detector acceptance. It catches gross extrapolation but cannot identify all hidden DAQ/current confounds.
- The timing-tail and charge rows are proxy deltas weighted by method secondary fractions; they are risk indicators, not calibrated timing or energy biases.

## Leakage and Falsification Checks

| check                                                      |   value | flag   | note                                                                                                 |
|:-----------------------------------------------------------|--------:|:-------|:-----------------------------------------------------------------------------------------------------|
| heldout_run_excluded_from_template_and_ml_training         | 1.00000 | False  | Every fold uses low-current source runs only and removes the held-out low-current run from controls. |
| identifier_features_excluded                               | 1.00000 | False  | ML features exclude run, event number, current, group, downstream label, and stratum labels.         |
| mean_shuffled_label_synthetic_auc                          | 0.48858 | False  | The permuted-label control should stay near chance on held-out synthetic overlays.                   |
| ridge_current_auc_from_secondary_fraction                  | 0.59230 | False  | Flagged if the method nearly identifies beam current from the secondary-fraction output.             |
| gradient_boosted_trees_current_auc_from_secondary_fraction | 0.64924 | False  | Flagged if the method nearly identifies beam current from the secondary-fraction output.             |
| mlp_current_auc_from_secondary_fraction                    | 0.52979 | False  | Flagged if the method nearly identifies beam current from the secondary-fraction output.             |
| cnn1d_current_auc_from_secondary_fraction                  | 0.53355 | False  | Flagged if the method nearly identifies beam current from the secondary-fraction output.             |
| residual_tcn_current_auc_from_secondary_fraction           | 0.36827 | False  | Flagged if the method nearly identifies beam current from the secondary-fraction output.             |

## Conclusion

The raw-ROOT S10 topology reproduction passes before model fitting. The traditional bounded two-pulse fit gives a matched high-minus-low secondary-fraction delta of 0.01751 [-0.00908, 0.04335]. The point-estimate winner is traditional, but the operational winner recorded for this ticket is traditional because the promotion rule requires clean leakage checks and an ML-minus-traditional CI wholly above zero. The selected winner has secondary-fraction delta 0.01751 [-0.00908, 0.04335], support acceptance 1.000, and overlap-score delta 0.00918.

## Artifacts

`result.json`, `manifest.json`, `input_sha256.csv`, `reproduction_match_table.csv`, `method_summary.csv`, `method_deltas_vs_traditional.csv`, `traditional_stability_scan.csv`, `sampled_event_scores.csv.gz`, `fold_diagnostics.csv`, `leakage_checks.csv`, and figures are in this report directory.
