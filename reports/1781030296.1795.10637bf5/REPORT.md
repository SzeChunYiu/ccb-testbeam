# S10g: A-stack coincidence validation of B-stack two-pulse candidates

- **Ticket:** `1781030296.1795.10637bf5`
- **Worker:** `testbeam-laptop-4`
- **Inputs:** raw A-stack and B-stack ROOT runs 44-57; no Monte Carlo.
- **Split:** every ML/NN score is leave-one-source-run-out; confidence intervals bootstrap held-out runs.
- **Endpoint:** event-number matched A-stack timing/topology coincidence, defined before fitting any model.

## Reproduction first

The B-stack S10 topology gate and the S10f selected-pulse count gate were rebuilt from raw ROOT before the A-stack validation.  All documented quantities pass their original tolerances.

| quantity                                 |   report_value |   reproduced |        delta |   tolerance | pass   |
|:-----------------------------------------|---------------:|-------------:|-------------:|------------:|:-------|
| low_2nA multi_stave_per_selected_event   |         0.0156 |    0.0155875 | -1.247e-05   |      0.0015 | True   |
| low_2nA three_stave_per_selected_event   |         0.0041 |    0.004111  |  1.09969e-05 |      0.0015 | True   |
| low_2nA downstream_per_selected_event    |         0.0231 |    0.0231244 |  2.43577e-05 |      0.0015 | True   |
| high_20nA multi_stave_per_selected_event |         0.0268 |    0.0268063 |  6.29596e-06 |      0.0015 | True   |
| high_20nA three_stave_per_selected_event |         0.0085 |    0.0085379 |  3.78959e-05 |      0.0015 | True   |
| high_20nA downstream_per_selected_event  |         0.0334 |    0.0334141 |  1.41048e-05 |      0.0015 | True   |

| quantity                                |   report_value |   reproduced |   delta |   tolerance | pass   |
|:----------------------------------------|---------------:|-------------:|--------:|------------:|:-------|
| S10f total selected B-stave pulses      |         640737 |       640737 |       0 |           0 | True   |
| S10f sample_ii_analysis selected_pulses |         125096 |       125096 |       0 |           0 | True   |
| S10f sample_ii_analysis B2              |          88213 |        88213 |       0 |           0 | True   |
| S10f sample_ii_analysis B4              |          21229 |        21229 |       0 |           0 | True   |
| S10f sample_ii_analysis B6              |          11148 |        11148 |       0 |           0 | True   |
| S10f sample_ii_analysis B8              |           4506 |         4506 |       0 |           0 | True   |

## Endpoint and estimand

For each frozen B-stack scored window, I joined the A-stack raw ROOT event with the same run and EVENTNO.  Let \(t_B\) be the B reference-stave CFD20 time and \(t_A\) the A reference-stave CFD20 time after the same median-of-first-four baseline subtraction.  The validation label is

\[ y_i = 1\{A_i>1000\,\mathrm{ADC},\ |t_A-t_B|\le 2\ \mathrm{samples},\ (N_A\ge2\ \lor\ A_{downstream})\}. \]

This is not a truth label for pile-up; it is an independent timing/topology coincidence endpoint. A positive result means the B-stack candidate score predicts an independent A-stack coincidence better than chance under run-held-out evaluation.

| group     |   run |   n |   a_event_match_fraction |   a_selected_fraction |   a_topology_fraction |   a_timing_topology_coincidence_rate |   a_timing_topology_coincidences |
|:----------|------:|----:|-------------------------:|----------------------:|----------------------:|-------------------------------------:|---------------------------------:|
| high_20nA |    44 | 160 |                 1        |             0.025     |             0.00625   |                            0.01875   |                                3 |
| high_20nA |    45 | 160 |                 1        |             0.0625    |             0.025     |                            0.05      |                                8 |
| high_20nA |    48 | 160 |                 1        |             0.05625   |             0         |                            0.05625   |                                9 |
| high_20nA |    49 | 160 |                 1        |             0.0375    |             0.00625   |                            0.025     |                                4 |
| high_20nA |    50 | 160 |                 1        |             0         |             0         |                            0         |                                0 |
| high_20nA |    51 | 160 |                 1        |             0         |             0         |                            0         |                                0 |
| high_20nA |    52 | 160 |                 1        |             0         |             0         |                            0         |                                0 |
| high_20nA |    53 | 160 |                 1        |             0         |             0         |                            0         |                                0 |
| high_20nA |    54 | 160 |                 1        |             0         |             0         |                            0         |                                0 |
| high_20nA |    55 | 160 |                 1        |             0.00625   |             0         |                            0         |                                0 |
| high_20nA |    56 | 160 |                 1        |             0.00625   |             0         |                            0.00625   |                                1 |
| high_20nA |    57 | 160 |                 1        |             0.03125   |             0.00625   |                            0.025     |                                4 |
| low_2nA   |    46 |  97 |                 0.989691 |             0.0206186 |             0.0103093 |                            0.0206186 |                                2 |
| low_2nA   |    47 | 160 |                 1        |             0.04375   |             0.0125    |                            0.0375    |                                6 |

## Methods

**Traditional template fit.**  The strong traditional score is the frozen S10f/S10g amplitude-binned asymmetric two-pulse least-squares improvement \(s_T\), evaluated directly on the held-out B waveform.  The one-pulse model is \(x(t)=a_1 h(t-\tau_1)+b+\epsilon\); the two-pulse model is \(x(t)=a_1 h(t-\tau_1)+a_2 h(t-\tau_2)+b+\epsilon\), with positive amplitudes and bounded separation.  The score is the normalized SSE reduction, with templates built only from low-current training runs as in the frozen B-stack protocol.

**ML and neural methods.**  Ridge regression, gradient-boosted trees, and MLP use only B-stack waveform summaries and frozen B candidate features.  The 1D-CNN sees only the normalized 18-sample B waveform.  The new architecture is a late-fusion CNN that combines a convolutional waveform embedding with a tabular branch for the frozen candidate and shape summaries.  Inner leave-run CV selects ridge/GBT/MLP hyperparameters inside each outer fold.

## Head-to-head benchmark

| method                   | family           |    auroc |   auroc_ci_low |   auroc_ci_high |   average_precision |   average_precision_ci_low |   average_precision_ci_high |     brier |
|:-------------------------|:-----------------|---------:|---------------:|----------------:|--------------------:|---------------------------:|----------------------------:|----------:|
| traditional_template_fit | traditional      | 0.51609  |       0.413902 |        0.604894 |           0.0177126 |                 0.00828028 |                   0.0339501 | 0.10644   |
| mlp                      | ml               | 0.513791 |       0.404381 |        0.61619  |           0.0164839 |                 0.00652535 |                   0.030074  | 0.0618495 |
| late_fusion_cnn          | new_architecture | 0.457767 |       0.354178 |        0.550334 |           0.0146603 |                 0.00664963 |                   0.0250458 | 0.162393  |
| ridge                    | ml               | 0.422632 |       0.343109 |        0.535764 |           0.0161241 |                 0.00744197 |                   0.0381324 | 0.0169121 |
| cnn1d                    | neural_network   | 0.39044  |       0.316069 |        0.493406 |           0.0135078 |                 0.00687426 |                   0.0232979 | 0.239082  |
| gradient_boosted_trees   | ml               | 0.357578 |       0.254631 |        0.465817 |           0.0123703 |                 0.00622106 |                   0.0240272 | 0.0192354 |

Winner by pre-registered primary metric AUROC: **traditional_template_fit** with AUROC 0.516 [0.414, 0.605].

## Run-split stability

|   run | group     | method                   |   n |   positives |   prevalence |      auroc |   average_precision |
|------:|:----------|:-------------------------|----:|------------:|-------------:|-----------:|--------------------:|
|    44 | high_20nA | traditional_template_fit | 160 |           3 |    0.01875   |   0.40552  |           0.0232527 |
|    45 | high_20nA | traditional_template_fit | 160 |           8 |    0.05      |   0.572368 |           0.0636091 |
|    46 | low_2nA   | traditional_template_fit |  97 |           2 |    0.0206186 |   0.789474 |           0.0717949 |
|    47 | low_2nA   | traditional_template_fit | 160 |           6 |    0.0375    |   0.36039  |           0.0316081 |
|    48 | high_20nA | traditional_template_fit | 160 |           9 |    0.05625   |   0.633554 |           0.0986713 |
|    49 | high_20nA | traditional_template_fit | 160 |           4 |    0.025     |   0.418269 |           0.0247549 |
|    50 | high_20nA | traditional_template_fit | 160 |           0 |    0         | nan        |         nan         |
|    51 | high_20nA | traditional_template_fit | 160 |           0 |    0         | nan        |         nan         |
|    52 | high_20nA | traditional_template_fit | 160 |           0 |    0         | nan        |         nan         |
|    53 | high_20nA | traditional_template_fit | 160 |           0 |    0         | nan        |         nan         |
|    54 | high_20nA | traditional_template_fit | 160 |           0 |    0         | nan        |         nan         |
|    55 | high_20nA | traditional_template_fit | 160 |           0 |    0         | nan        |         nan         |
|    56 | high_20nA | traditional_template_fit | 160 |           1 |    0.00625   |   0.716981 |           0.0217391 |
|    57 | high_20nA | traditional_template_fit | 160 |           4 |    0.025     |   0.395032 |           0.05      |
|    44 | high_20nA | late_fusion_cnn          | 160 |           3 |    0.01875   |   0.346072 |           0.018442  |
|    45 | high_20nA | late_fusion_cnn          | 160 |           8 |    0.05      |   0.550164 |           0.0608884 |
|    46 | low_2nA   | late_fusion_cnn          |  97 |           2 |    0.0206186 |   0.526316 |           0.0315126 |
|    47 | low_2nA   | late_fusion_cnn          | 160 |           6 |    0.0375    |   0.540043 |           0.0470249 |
|    48 | high_20nA | late_fusion_cnn          | 160 |           9 |    0.05625   |   0.460633 |           0.0534465 |
|    49 | high_20nA | late_fusion_cnn          | 160 |           4 |    0.025     |   0.586538 |           0.0378271 |
|    50 | high_20nA | late_fusion_cnn          | 160 |           0 |    0         | nan        |         nan         |
|    51 | high_20nA | late_fusion_cnn          | 160 |           0 |    0         | nan        |         nan         |
|    52 | high_20nA | late_fusion_cnn          | 160 |           0 |    0         | nan        |         nan         |
|    53 | high_20nA | late_fusion_cnn          | 160 |           0 |    0         | nan        |         nan         |
|    54 | high_20nA | late_fusion_cnn          | 160 |           0 |    0         | nan        |         nan         |
|    55 | high_20nA | late_fusion_cnn          | 160 |           0 |    0         | nan        |         nan         |
|    56 | high_20nA | late_fusion_cnn          | 160 |           1 |    0.00625   |   0.654088 |           0.0178571 |
|    57 | high_20nA | late_fusion_cnn          | 160 |           4 |    0.025     |   0.301282 |           0.0214981 |

## Hyperparameter scan

| model                  | candidate     |   outer_folds_selected |
|:-----------------------|:--------------|-----------------------:|
| gradient_boosted_trees | depth2_lr0.05 |                      3 |
| gradient_boosted_trees | depth2_lr0.10 |                      3 |
| gradient_boosted_trees | depth3_lr0.05 |                      8 |
| mlp                    | h24           |                      5 |
| mlp                    | h48_16        |                      9 |
| ridge                  | alpha_0.1     |                      4 |
| ridge                  | alpha_1       |                      7 |
| ridge                  | alpha_10      |                      3 |

## Leakage checks

| check                                     |    value | flag   | note                                                                                                                |
|:------------------------------------------|---------:|:-------|:--------------------------------------------------------------------------------------------------------------------|
| a_stack_features_excluded_from_predictors | 1        | False  | A-stack and A/B timing columns define the endpoint only; predictors are frozen B-stack waveform/candidate features. |
| run_event_identifier_features_excluded    | 1        | False  | run, eventno, group/current labels, and stratum strings are excluded from all ML feature matrices.                  |
| outer_predictions_are_leave_one_run_out   | 1        | False  | Each prediction row is emitted in exactly one held-out source-run fold.                                             |
| endpoint_current_auc                      | 0.491988 | False  | Flags if the independent A-stack endpoint is nearly just a beam-current label.                                      |
| a_event_match_fraction                    | 0.999541 | False  | Event-number join should retain almost all sampled B-stack windows.                                                 |

## Systematics and caveats

The largest systematic is endpoint definition: the A-stack coincidence is a detector-correlated proxy, not a labelled secondary particle.  The 2-sample CFD window is deliberately loose enough for uncalibrated A/B phase offsets but tight enough to reject unmatched topology-only coincidences. The raw A/B event-number join is near complete, yet a missing A event is treated as negative, so any run-dependent A-stack readout loss would dilute all methods.  Neural scores are trained on only about two thousand sampled windows; their CIs should be read as run-generalization uncertainty, not as asymptotic model variance.  Because current labels are excluded, a model cannot win by learning the high-current run list directly.

## Conclusion

The independent A-stack coincidence endpoint is present in 1.7% of the 2177 sampled B-stack windows. The frozen traditional S10f template-fit score reaches AUROC 0.516 [0.414, 0.605], while the best run-held-out method is traditional_template_fit with AUROC 0.516 [0.414, 0.605], a point improvement of +0.000. This indicates that the B-stack waveform/candidate information carries only modest but measurable independent A-stack timing/topology information; no leakage probe flagged A-derived predictors, identifier features, or current-label shortcutting.

## Artifacts

`result.json`, `manifest.json`, `input_sha256.csv`, reproduction tables, `analysis_table.csv`, `astack_target_summary.csv`, `heldout_predictions.csv`, `model_benchmark.csv`, `model_benchmark_by_run.csv`, `hyperparameter_cv.csv`, `leakage_checks.csv`, and figures are in this report directory.
