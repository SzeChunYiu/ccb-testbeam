# S00f: dynamic-only baseline-excursion pile-up support map

- **Ticket:** `1781033578.541.73575b7f`
- **Worker:** `testbeam-laptop-3`
- **Command:** `/home/billy/anaconda3/bin/python scripts/s00f_1781033578_541_73575b7f_dynamic_pileup_support.py`
- **Input:** raw B-stack `HRDv` ROOT files under `data/root/root`

## Abstract

This study tests whether the dynamic-range-only selector excess, restricted to the dominant baseline-excursion morphology, is a useful pile-up support region or a selector artifact. The raw ROOT reproduction gate returns **65,636** dynamic-only pulses, exactly matching the S00a/S00d value of 65,636. After exact matching to S00 controls by run, current label, stave, dynamic-amplitude bin, and P02-style downstream topology proxy, the physics-facing verdict is **selector_artifact_region**. The benchmark winner recorded in `result.json` is **new_shape_residual_fusion**.

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
(\mathrm{run},\mathrm{current},\mathrm{stave},\mathrm{dynamic\ amplitude\ bin},\mathrm{topology}).
\]

The topology is the raw-root downstream/stave multiplicity proxy used here for P02-style support matching. Exact matched coverage is **0.977**: 59,275 dynamic baseline-excursion pulses and 59,275 S00 controls.

Top support strata:

| match_key                                    |   dynamic_n |   control_n |   matched_n |
|:---------------------------------------------|------------:|------------:|------------:|
| 37\|high_20nA\|B2\|(3000.0, 4500.0]\|B2_only |        1824 |        5332 |        1824 |
| 45\|high_20nA\|B2\|(3000.0, 4500.0]\|B2_only |        1731 |        5133 |        1731 |
| 41\|high_20nA\|B2\|(3000.0, 4500.0]\|B2_only |        1229 |        3745 |        1229 |
| 40\|high_20nA\|B2\|(3000.0, 4500.0]\|B2_only |        1204 |        3559 |        1204 |
| 42\|high_20nA\|B2\|(3000.0, 4500.0]\|B2_only |        1203 |        3536 |        1203 |
| 39\|high_20nA\|B2\|(3000.0, 4500.0]\|B2_only |        1151 |        3345 |        1151 |
| 48\|high_20nA\|B2\|(3000.0, 4500.0]\|B2_only |        1142 |        3562 |        1142 |
| 49\|high_20nA\|B2\|(3000.0, 4500.0]\|B2_only |        1135 |        3572 |        1135 |
| 57\|high_20nA\|B2\|(3000.0, 4500.0]\|B2_only |        1121 |        3499 |        1121 |
| 32\|high_20nA\|B2\|(3000.0, 4500.0]\|B2_only |         970 |        3676 |         970 |
| 31\|high_20nA\|B2\|(3000.0, 4500.0]\|B2_only |         851 |        3344 |         851 |
| 35\|high_20nA\|B2\|(3000.0, 4500.0]\|B2_only |         835 |        3301 |         835 |

## Primary Pile-up and Artifact Metrics

The secondary-fraction proxy is a frozen two-peak waveform rubric: a post-peak maximum at least 0.28 of the normalized dynamic amplitude, separated by at least 20 ns, with an intervening dip of at least 0.08 and no strong early/noisy pathology. Timing-tail fraction is \(I[\Delta t_{\rm downstream}>5\,\mathrm{ns}]\), where \(\Delta t_{\rm downstream}\) is the event-level B4/B6/B8 CFD20 span. Charge bias is reported with the signed waveform area.

| metric                  |    dynamic_value |   matched_control_value |          delta |         ci_low |        ci_high | unit               |
|:------------------------|-----------------:|------------------------:|---------------:|---------------:|---------------:|:-------------------|
| secondary_fraction      |      1.68705e-05 |                0.101189 |     -0.101173  |     -0.106827  |     -0.0947382 | fraction           |
| timing_tail_fraction    |      0.0920962   |                0.129684 |     -0.0375875 |     -0.0496003 |     -0.0279432 | fraction           |
| median_amp_adc          |    374.5         |             3120        |  -2745.5       |  -2822.76      |  -2656.83      | ADC or ADC-samples |
| dynamic_amp_adc         |   3265           |             3260        |      5         |     -6         |     13.525     | ADC or ADC-samples |
| signed_area_adc_samples | -27759           |            23246        | -51005         | -52412.9       | -49011.7       | ADC or ADC-samples |
| baseline_excursion_adc  |    896           |               23        |    873         |    834         |    944.625     | ADC or ADC-samples |

Matched strata summary:

| population                 | current_group   | dynamic_topology       |     n |   secondary_fraction |   timing_tail_fraction |   median_dynamic_amp_adc |
|:---------------------------|:----------------|:-----------------------|------:|---------------------:|-----------------------:|-------------------------:|
| dynamic_baseline_excursion | high_20nA       | B2_only                | 37531 |          2.66446e-05 |               0        |                   3512   |
| dynamic_baseline_excursion | high_20nA       | B2_plus_one_downstream | 10387 |          0           |               0        |                   3165   |
| dynamic_baseline_excursion | high_20nA       | B2_plus_ge2_downstream |  5938 |          0           |               0.773324 |                   2891   |
| dynamic_baseline_excursion | high_20nA       | all_four               |  3849 |          0           |               0.207067 |                   2531   |
| dynamic_baseline_excursion | high_20nA       | B4_only                |   550 |          0           |               0        |                   1572.5 |
| dynamic_baseline_excursion | low_2nA         | B2_only                |   360 |          0           |               0        |                   3459   |
| dynamic_baseline_excursion | high_20nA       | B6_only                |   283 |          0           |               0        |                   1804   |
| dynamic_baseline_excursion | high_20nA       | B8_only                |   253 |          0           |               0        |                   1611   |
| dynamic_baseline_excursion | high_20nA       | downstream_ge2         |    81 |          0           |               0.765432 |                   2430   |
| dynamic_baseline_excursion | low_2nA         | B2_plus_one_downstream |    17 |          0           |               0        |                   3470   |
| dynamic_baseline_excursion | high_20nA       | all_downstream         |     8 |          0           |               0        |                   1661.5 |
| dynamic_baseline_excursion | low_2nA         | B2_plus_ge2_downstream |     8 |          0           |               1        |                   3012.5 |
| dynamic_baseline_excursion | low_2nA         | all_four               |     6 |          0           |               0        |                   2441.5 |
| dynamic_baseline_excursion | low_2nA         | B6_only                |     2 |          0           |               0        |                   2267   |

## Model Benchmark

All models use the same train/held-out split by run; held-out runs are `[42, 57, 64, 65]`. Learned features exclude run, event number, current label, median amplitude, dynamic amplitude, dynamic-minus-median, and baseline-excursion ADC. The traditional fixed-secondary score is included as a non-learned reference. The ML/NN panel contains ridge, histogram gradient-boosted trees, MLP, 1D-CNN, and a new shape-residual fusion ExtraTrees architecture using train-only PCA waveform coordinates plus non-selector shape summaries. The target is dynamic baseline-excursion membership versus exact matched S00 controls.

| method                            |   roc_auc |   roc_auc_ci_low |   roc_auc_ci_high |   average_precision |   balanced_accuracy |     brier | eligible_winner   |
|:----------------------------------|----------:|-----------------:|------------------:|--------------------:|--------------------:|----------:|:------------------|
| new_shape_residual_fusion         |  0.999307 |         0.998992 |          0.999713 |            0.999305 |              0.987  | 0.0101491 | True              |
| mlp                               |  0.999229 |         0.999022 |          0.999516 |            0.999213 |              0.9855 | 0.0102835 | True              |
| gradient_boosted_trees            |  0.999133 |         0.998779 |          0.999644 |            0.999124 |              0.9855 | 0.0109763 | True              |
| ridge                             |  0.996567 |         0.995744 |          0.997793 |            0.996368 |              0.97   | 0.0286276 | True              |
| cnn_1d                            |  0.994917 |         0.993441 |          0.997004 |            0.994328 |              0.973  | 0.107403  | True              |
| traditional_fixed_secondary_score |  0.45375  |         0.44425  |          0.463    |            0.5      |              0.5    | 0.54625   | True              |
| shuffled_label_fusion_control     |  0.462468 |         0.432909 |          0.487541 |            0.462559 |              0.4745 | 0.258874  | False             |

Leakage and control checks:

| check                                         |    value | pass   | note                                                                               |
|:----------------------------------------------|---------:|:-------|:-----------------------------------------------------------------------------------|
| train_heldout_run_overlap                     | 0        | True   | split unit is run                                                                  |
| forbidden_feature_columns_absent              | 0        | True   | run,event,current,selector amplitudes,baseline excursion excluded from ML matrices |
| shuffled_label_fusion_control_auc_near_chance | 0.462468 | True   | within-train shuffled labels should not identify held-out dynamic membership       |

## Interpretation

The matched dynamic baseline-excursion population does not behave like clean pile-up support. A true pile-up support region would show a positive secondary-fraction excess without a large negative charge-area displacement. Instead, the dominant stable effect is a baseline/signed-area displacement, while the exact matched control removes much of the current/topology ambiguity. This makes the dynamic-only baseline-excursion region useful as an exclusion/provenance atom, not as an adopted pile-up training sample.

The model benchmark is diagnostic rather than physics-adopting. High dynamic-vs-control separability means the baseline-excursion support remains morphologically distinct after matching; it does not convert the region into a pile-up truth label. The winner is therefore named for predictive discrimination, while the physics verdict follows the run-block matched deltas.

## Systematics and Caveats

- **Topology proxy:** matching uses raw B-stave multiplicity topology rather than a full external P02 latent label for every dynamic-only pulse. This is the only topology available directly at raw-root scan time for the strict dynamic-only rows.
- **Control support:** exact matching discards unmatched dynamic rows. Coverage and support tables are therefore part of the result, not bookkeeping.
- **Pile-up proxy:** the two-peak rubric is intentionally conservative and deterministic; it is not a truth label.
- **Timing tails:** CFD20 spans are undefined for events without at least two downstream dynamic-selected staves, so timing-tail fractions are support-conditional.
- **ML interpretation:** ML/NN methods are leakage guarded, but they target selector-excess membership, not physical pile-up.

## Artifacts

Main tables are `reproduction_match_table.csv`, `selector_counts_by_run.csv`, `matched_support_summary.csv`, `primary_delta_metrics.csv`, `matched_strata_summary.csv`, `model_benchmark.csv`, `heldout_model_scores.csv.gz`, `leakage_checks.csv`, `input_sha256.csv`, `manifest.json`, and `result.json`.
