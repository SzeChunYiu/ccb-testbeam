# S00g: dynamic-only topology proxy replacement with joined P02 latent labels

- **Ticket:** `1781108434.1606.7f9f3ead`
- **Worker:** `testbeam-laptop-2`
- **Command:** `.venv/bin/python scripts/s00g_1781108434_1606_7f9f3ead_dynamic_latent_topology_replacement.py`
- **Input:** raw B-stack `HRDv` ROOT files under `data/root/root`
- **Latent artifact:** `reports/1781032398.9027.3d275e75__s00e_dynamic_embedding_release/s00e_dynamic_embedding_latents.npz`

## Abstract

This study reruns the S00f dynamic-only baseline-excursion analysis after replacing the raw multiplicity topology proxy with a joined P02/S00e latent topology label for every selected row. The raw ROOT reproduction gate returns **65,636** dynamic-only pulses, exactly matching the frozen S00a/S00d value of 65,636. After exact matching to S00 controls by run, current label, stave, dynamic-amplitude bin, and joined latent topology, the physics-facing verdict is **selector_artifact_region**. The benchmark winner recorded in `result.json` is **new_shape_residual_fusion**.

## Reproduction Gate

The selected-pulse rules are

\[
A_{\rm med} = \max_t(x_t - {\rm median}(x_0,x_1,x_2,x_3)), \qquad
A_{\rm dyn} = \max_t x_t - \min_t x_t .
\]

S00 selects B2/B4/B6/B8 pulses with \(A_{\rm med}>1000\) ADC. The dynamic selector uses \(A_{\rm dyn}>1000\) ADC. The dynamic-only set is \(D \setminus S\).

| quantity                   |   expected |   reproduced |   delta |   tolerance | pass   |
|:---------------------------|-----------:|-------------:|--------:|------------:|:-------|
| median_first_four_selected |     640737 |       640737 |       0 |           0 | True   |
| dynamic_range_selected     |     706373 |       706373 |       0 |           0 | True   |
| dynamic_only               |      65636 |        65636 |       0 |           0 | True   |
| median_only                |          0 |            0 |       0 |           0 | True   |

## Matched Design

The target cohort is dynamic-only pulses satisfying the frozen baseline-excursion cut

\[
\max(x_0,x_1,x_2,x_3)-\min(x_0,x_1,x_2,x_3) \ge 250\;{\rm ADC}.
\]

Controls are S00 pulses sampled without replacement from the same exact stratum:

\[
(\mathrm{run},\mathrm{current},\mathrm{stave},\mathrm{dynamic\ amplitude\ bin},\mathrm{latent\ topology}).
\]

The latent topology is constructed by joining the S00e embedding release on `(run,event_index,stave_index,dynamic_only)` and clustering the four-dimensional latent vector `z` into 8 unsupervised MiniBatchKMeans labels `p02_latent_cXX`. The old raw `dynamic_topology` remains in the pulse table for diagnostics, but it is not part of the S00g exact matching key. Exact matched coverage is **0.251**: 15,220 dynamic baseline-excursion pulses and 15,220 S00 controls.

Latent topology occupancy:

| latent_topology   |   latent_cluster |   dynamic_only |   rows |   runs |   median_dynamic_amp_adc |   raw_dynamic_topologies |
|:------------------|-----------------:|---------------:|-------:|-------:|-------------------------:|-------------------------:|
| p02_latent_c00    |                0 |              0 | 108382 |     33 |                   5567   |                        9 |
| p02_latent_c00    |                0 |              1 |  16622 |     33 |                   2409.5 |                        9 |
| p02_latent_c01    |                1 |              0 | 220052 |     33 |                   7334   |                        9 |
| p02_latent_c01    |                1 |              1 |    111 |     28 |                   1012   |                        6 |
| p02_latent_c02    |                2 |              1 |   6450 |     33 |                   3484   |                        9 |
| p02_latent_c03    |                3 |              0 |  85423 |     33 |                   4603   |                        9 |
| p02_latent_c03    |                3 |              1 |    109 |     25 |                   1008   |                        5 |
| p02_latent_c04    |                4 |              0 |  54117 |     33 |                   3753   |                        9 |
| p02_latent_c04    |                4 |              1 |     33 |     15 |                   1009   |                        8 |
| p02_latent_c05    |                5 |              0 |    757 |     33 |                   6997   |                        4 |
| p02_latent_c05    |                5 |              1 |  42148 |     33 |                   3333   |                        9 |
| p02_latent_c06    |                6 |              0 |  69459 |     33 |                   3608   |                        9 |
| p02_latent_c06    |                6 |              1 |     58 |     19 |                   1010   |                        7 |
| p02_latent_c07    |                7 |              0 | 102547 |     33 |                   5338   |                        9 |
| p02_latent_c07    |                7 |              1 |    105 |     27 |                   1008   |                        4 |

Top support strata:

| match_key                                           |   dynamic_n |   control_n |   matched_n |
|:----------------------------------------------------|------------:|------------:|------------:|
| 45\|high_20nA\|B2\|(3000.0, 4500.0]\|p02_latent_c00 |         219 |         911 |         219 |
| 37\|high_20nA\|B2\|(3000.0, 4500.0]\|p02_latent_c00 |         195 |         983 |         195 |
| 62\|high_20nA\|B2\|(3000.0, 4500.0]\|p02_latent_c00 |         182 |        1062 |         182 |
| 59\|high_20nA\|B2\|(3000.0, 4500.0]\|p02_latent_c00 |         179 |        1216 |         179 |
| 61\|high_20nA\|B2\|(3000.0, 4500.0]\|p02_latent_c00 |         179 |        1086 |         179 |
| 60\|high_20nA\|B2\|(3000.0, 4500.0]\|p02_latent_c00 |         168 |        1029 |         168 |
| 39\|high_20nA\|B2\|(3000.0, 4500.0]\|p02_latent_c00 |         152 |         609 |         152 |
| 57\|high_20nA\|B2\|(3000.0, 4500.0]\|p02_latent_c00 |         148 |         632 |         148 |
| 42\|high_20nA\|B2\|(3000.0, 4500.0]\|p02_latent_c00 |         146 |         620 |         146 |
| 40\|high_20nA\|B2\|(3000.0, 4500.0]\|p02_latent_c00 |         144 |         638 |         144 |
| 59\|high_20nA\|B4\|(2000.0, 3000.0]\|p02_latent_c00 |         143 |         524 |         143 |
| 63\|high_20nA\|B2\|(3000.0, 4500.0]\|p02_latent_c00 |         142 |         754 |         142 |

## Primary Pile-up and Artifact Metrics

The secondary-fraction proxy is a frozen two-peak waveform rubric: a post-peak maximum at least 0.28 of the normalized dynamic amplitude, separated by at least 20 ns, with an intervening dip of at least 0.08 and no strong early/noisy pathology. Timing-tail fraction is \(I[\Delta t_{\rm downstream}>5\,\mathrm{ns}]\), where \(\Delta t_{\rm downstream}\) is the event-level B4/B6/B8 CFD20 span. Charge bias is reported with the signed waveform area.

| metric                  |   dynamic_value |   matched_control_value |          delta |         ci_low |        ci_high | unit               |
|:------------------------|----------------:|------------------------:|---------------:|---------------:|---------------:|:-------------------|
| secondary_fraction      |      6.5703e-05 |               0.0316032 |     -0.0315375 |     -0.0351266 |     -0.0282658 | fraction           |
| timing_tail_fraction    |      0.119251   |               0.177135  |     -0.0578844 |     -0.0716061 |     -0.0443864 | fraction           |
| median_amp_adc          |    740.5        |            1896.75      |  -1156.25      |  -1190.69      |  -1111.97      | ADC or ADC-samples |
| dynamic_amp_adc         |   2713          |            2798         |    -85         |   -106         |    -50.2375    | ADC or ADC-samples |
| signed_area_adc_samples | -15804.5        |            8673         | -24477.5       | -24894.7       | -24008.5       | ADC or ADC-samples |
| baseline_excursion_adc  |   1436          |            1100         |    336         |    298.475     |    395         | ADC or ADC-samples |

Matched strata summary by joined latent topology:

| population                 | current_group   | match_topology   |     n |   secondary_fraction |   timing_tail_fraction |   median_dynamic_amp_adc |
|:---------------------------|:----------------|:-----------------|------:|---------------------:|-----------------------:|-------------------------:|
| dynamic_baseline_excursion | high_20nA       | p02_latent_c00   | 14673 |          6.81524e-05 |             0.122811   |                   2667   |
| dynamic_baseline_excursion | high_20nA       | p02_latent_c05   |   412 |          0           |             0.00970874 |                   5092   |
| dynamic_baseline_excursion | low_2nA         | p02_latent_c00   |    68 |          0           |             0.0441176  |                   2830.5 |
| dynamic_baseline_excursion | high_20nA       | p02_latent_c01   |    31 |          0           |             0.0967742  |                   1481   |
| dynamic_baseline_excursion | high_20nA       | p02_latent_c07   |    13 |          0           |             0          |                   1130   |
| dynamic_baseline_excursion | high_20nA       | p02_latent_c03   |    12 |          0           |             0.166667   |                   1330   |
| dynamic_baseline_excursion | high_20nA       | p02_latent_c06   |     6 |          0           |             0          |                   1038.5 |
| dynamic_baseline_excursion | low_2nA         | p02_latent_c05   |     4 |          0           |             0          |                   5664   |
| dynamic_baseline_excursion | high_20nA       | p02_latent_c04   |     1 |          0           |             1          |                   1691   |
| matched_s00_control        | high_20nA       | p02_latent_c00   | 14673 |          0.0325087   |             0.182853   |                   2757   |
| matched_s00_control        | high_20nA       | p02_latent_c05   |   412 |          0           |             0.00970874 |                   6574.5 |
| matched_s00_control        | low_2nA         | p02_latent_c00   |    68 |          0.0588235   |             0.0441176  |                   2890.5 |
| matched_s00_control        | high_20nA       | p02_latent_c01   |    31 |          0           |             0.0967742  |                   1468   |
| matched_s00_control        | high_20nA       | p02_latent_c07   |    13 |          0           |             0          |                   1321   |

## Model Benchmark

All models use the same train/held-out split by run; held-out runs are `[42, 57, 64, 65]`. Learned features exclude run, event number, current label, median amplitude, dynamic amplitude, dynamic-minus-median, and baseline-excursion ADC. The traditional fixed-secondary score is included as a non-learned reference. The ML/NN panel contains ridge, histogram gradient-boosted trees, MLP, 1D-CNN, and a new shape-residual fusion ExtraTrees architecture using train-only PCA waveform coordinates plus non-selector shape summaries. The `cnn_1d` implementation recorded in `result.json` is `fixed_1d_convolution_filter_bank_hist_gradient_boosting_fallback`. The target is dynamic baseline-excursion membership versus exact matched S00 controls.

| method                            |   roc_auc |   roc_auc_ci_low |   roc_auc_ci_high |   average_precision |   balanced_accuracy |     brier | eligible_winner   |
|:----------------------------------|----------:|-----------------:|------------------:|--------------------:|--------------------:|----------:|:------------------|
| new_shape_residual_fusion         |  0.991807 |         0.991097 |          0.992466 |            0.99193  |            0.957739 | 0.0339654 | True              |
| mlp                               |  0.990523 |         0.989708 |          0.991574 |            0.990326 |            0.954041 | 0.0355316 | True              |
| gradient_boosted_trees            |  0.989822 |         0.988803 |          0.990853 |            0.989544 |            0.952985 | 0.0363054 | True              |
| cnn_1d                            |  0.986502 |         0.984601 |          0.988483 |            0.986251 |            0.941891 | 0.042727  | True              |
| ridge                             |  0.963597 |         0.954266 |          0.976526 |            0.958832 |            0.904913 | 0.0840278 | True              |
| traditional_fixed_secondary_score |  0.481511 |         0.477327 |          0.48615  |            0.5      |            0.5      | 0.518489  | True              |
| shuffled_label_fusion_control     |  0.50003  |         0.471713 |          0.523805 |            0.479086 |            0.500792 | 0.25524   | False             |

Leakage and control checks:

| check                                         |   value | pass   | note                                                                               |
|:----------------------------------------------|--------:|:-------|:-----------------------------------------------------------------------------------|
| train_heldout_run_overlap                     | 0       | True   | split unit is run                                                                  |
| forbidden_feature_columns_absent              | 0       | True   | run,event,current,selector amplitudes,baseline excursion excluded from ML matrices |
| shuffled_label_fusion_control_auc_near_chance | 0.50003 | True   | within-train shuffled labels should not identify held-out dynamic membership       |

## Interpretation

The matched dynamic baseline-excursion population does not behave like clean pile-up support. A true pile-up support region would show a positive secondary-fraction excess without a large negative charge-area displacement. Instead, the dominant stable effect is a baseline/signed-area displacement, while the exact matched control removes much of the current/topology ambiguity. This makes the dynamic-only baseline-excursion region useful as an exclusion/provenance atom, not as an adopted pile-up training sample.

The model benchmark is diagnostic rather than physics-adopting. High dynamic-vs-control separability means the baseline-excursion support remains morphologically distinct after latent-topology matching; it does not convert the region into a pile-up truth label. The winner is therefore named for predictive discrimination, while the physics verdict follows the run-block matched deltas.

## Systematics and Caveats

- **Latent topology:** labels are unsupervised clusters of a prior S00e/P02-style four-dimensional embedding release. They are not external physics truth labels.
- **Join key:** the latent join uses `(run,event_index,stave_index,dynamic_only)` and aborts on any missing selected row; this verifies coverage but inherits the S00e release's row identity conventions.
- **Control support:** exact matching discards unmatched dynamic rows. Coverage and support tables are therefore part of the result, not bookkeeping.
- **Pile-up proxy:** the two-peak rubric is intentionally conservative and deterministic; it is not a truth label.
- **Timing tails:** CFD20 spans are undefined for events without at least two downstream dynamic-selected staves, so timing-tail fractions are support-conditional.
- **ML interpretation:** ML/NN methods are leakage guarded, but they target selector-excess membership, not physical pile-up.

## Artifacts

Main tables are `reproduction_match_table.csv`, `selector_counts_by_run.csv`, `latent_topology_summary.csv`, `matched_support_summary.csv`, `primary_delta_metrics.csv`, `matched_strata_summary.csv`, `model_benchmark.csv`, `heldout_model_scores.csv.gz`, `leakage_checks.csv`, `input_sha256.csv`, `manifest.json`, and `result.json`.
