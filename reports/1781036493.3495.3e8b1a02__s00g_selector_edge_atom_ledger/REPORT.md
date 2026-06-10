# S00g: selector-edge waveform atom ledger

- **Ticket:** `1781036493.3495.3e8b1a02`
- **Worker:** `testbeam-laptop-4`
- **Command:** `/home/billy/anaconda3/bin/python scripts/s00g_1781036493_3495_3e8b1a02_selector_edge_atom_ledger.py`
- **Input:** raw B-stack `HRDv` ROOT files under `data/root/root`

## Abstract

This study builds an atom ledger for waveform records that sit on selector boundaries: dynamic-only rows, near-threshold median rows, near-threshold dynamic rows, and baseline-excursion rows. Early-peak, late-tail, saturation, dropout, PID-support, and energy-range proxies are then measured as propagation outcomes within those atoms. The raw ROOT reproduction gate returns **640,737** S00 median-first-four pulses and **65,636** dynamic-only pulses, exactly matching the S00/S00c/S00d anchors. After exact matching to S00 non-edge controls by run, current label, stave, dynamic-amplitude bin, and raw topology proxy, the physics-facing verdict is **selector_systematic_atom**. The predictive benchmark winner recorded in `result.json` is **new_shape_residual_fusion**.

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

## Atom Definitions

For each dynamic-selected record the script assigns the first matching selector-boundary atom in this priority order:

1. dynamic-only: \(A_{\rm dyn}>1000\) and \(A_{\rm med}\le1000\);
2. median-threshold edge: S00-selected and \(|A_{\rm med}-1000|\le150\) ADC;
3. dynamic-threshold edge: \(|A_{\rm dyn}-1000|\le150\) ADC;
4. baseline excursion: \(\max(x_0,\ldots,x_3)-\min(x_0,\ldots,x_3)\ge250\) ADC.

Early peak, late tail, saturation, dropout, PID support, and deepest-stave energy-range proxies are deliberately not control-excluding atom definitions; they are propagation columns used to test whether the selector edge leaks into timing, amplitude, saturation, pile-up, baseline, dropout, PID, or energy support.

The S00c honest-summary selector mistakes are reproduced with the same S00c sampling rule and honest logistic features (`wave_max`, `wave_min`, `pre4_mean/std`, `post_mean/std`, `dynamic_amp`, and `stave_idx`; no `median_amp`, run id, or event id). On held-out runs `[57, 65]`, the reproduced S00c-like model has 556 false positives and 78 false negatives.

| primary_atom          |      n |   fraction_of_edge |   runs |   median_amp_adc |   dynamic_amp_adc |   baseline_excursion_adc |   secondary_fraction |   timing_tail_fraction |   saturation_fraction |   dropout_proxy_fraction |   pid_support_proxy_fraction |   median_energy_range_proxy |
|:----------------------|-------:|-------------------:|-------:|-----------------:|------------------:|-------------------------:|---------------------:|-----------------------:|----------------------:|-------------------------:|-----------------------------:|----------------------------:|
| baseline_excursion    | 119017 |          0.608761  |     33 |           4895.5 |              5896 |                      843 |          0.0503626   |              0.0764513 |                     1 |                 0.245536 |                     0.12263  |                           2 |
| dynamic_only          |  65636 |          0.335722  |     33 |            351.5 |              3255 |                      831 |          1.52355e-05 |              0.0946737 |                     1 |                 0.992565 |                     0.167637 |                           2 |
| median_threshold_edge |  10854 |          0.0555172 |     33 |           1074.5 |              1138 |                       40 |          0.000368528 |              0.0648609 |                     1 |                 0.402893 |                     0.101253 |                           2 |

S00c honest-mistake atom ledger:

| mistake_type   | primary_atom           |   dynamic_selected |   median_selected |   n |   runs |   median_amp_adc |   dynamic_amp_adc |   baseline_excursion_adc |   mean_honest_prob |
|:---------------|:-----------------------|-------------------:|------------------:|----:|-------:|-----------------:|------------------:|-------------------------:|-------------------:|
| false_negative | median_threshold_edge  |                  1 |                 1 |  64 |      2 |          1055    |            2080.5 |                   1310.5 |           0.266398 |
| false_negative | baseline_excursion     |                  1 |                 1 |  14 |      2 |          1216.75 |            4245.5 |                   2751.5 |           0.123604 |
| false_positive | dynamic_threshold_edge |                  0 |                 0 | 316 |      2 |           951.75 |             959.5 |                     14   |           0.704436 |
| false_positive | dynamic_only           |                  1 |                 0 | 237 |      2 |           924.5  |            4412   |                   3635   |           0.789026 |
| false_positive | non_edge_shape         |                  0 |                 0 |   3 |      2 |           821.5  |             839   |                      9   |           0.551093 |

## Matched Design

The target cohort is every selector-edge atom row. Controls are S00 pulses in the same dynamic-selected population with no selector-boundary atom flag. Controls are sampled without replacement from the same exact stratum:

\[
(\mathrm{run},\mathrm{current},\mathrm{stave},\mathrm{dynamic\ amplitude\ bin},\mathrm{topology}).
\]

The topology is the raw-root B-stave multiplicity proxy. Exact matched coverage is **0.954**: 186,532 edge pulses and 186,532 S00 core controls.

Top support strata:

| match_key                                     |   edge_n |   control_n |   matched_n |
|:----------------------------------------------|---------:|------------:|------------:|
| 56\|high_20nA\|B2\|(7000.0, 12000.0]\|B2_only |     5087 |       15315 |        5087 |
| 50\|high_20nA\|B2\|(7000.0, 12000.0]\|B2_only |     3793 |       14562 |        3793 |
| 37\|high_20nA\|B2\|(3000.0, 4500.0]\|B2_only  |     3121 |        4305 |        3121 |
| 31\|high_20nA\|B2\|(7000.0, 12000.0]\|B2_only |     3006 |        8277 |        3006 |
| 45\|high_20nA\|B2\|(3000.0, 4500.0]\|B2_only  |     2950 |        4160 |        2950 |
| 32\|high_20nA\|B2\|(7000.0, 12000.0]\|B2_only |     2885 |        8127 |        2885 |
| 45\|high_20nA\|B2\|(4500.0, 7000.0]\|B2_only  |     2700 |        5034 |        2700 |
| 37\|high_20nA\|B2\|(4500.0, 7000.0]\|B2_only  |     2690 |        5005 |        2690 |
| 56\|high_20nA\|B2\|(4500.0, 7000.0]\|B2_only  |     2282 |        9283 |        2282 |
| 32\|high_20nA\|B2\|(4500.0, 7000.0]\|B2_only  |     2236 |        6553 |        2236 |
| 41\|high_20nA\|B2\|(3000.0, 4500.0]\|B2_only  |     2094 |        3053 |        2094 |
| 31\|high_20nA\|B2\|(4500.0, 7000.0]\|B2_only  |     2089 |        6593 |        2089 |

## Propagation Metrics

The secondary-fraction proxy is a frozen two-peak waveform rubric: a post-peak maximum at least 0.28 of the normalized dynamic amplitude, separated by at least 20 ns, with an intervening dip of at least 0.08 and no strong early/noisy pathology. Timing-tail fraction is \(I[\Delta t_{\rm downstream}>5\,\mathrm{ns}]\), where \(\Delta t_{\rm downstream}\) is the event-level B4/B6/B8 CFD20 span. Charge bias is reported with the signed waveform area.

The run-block bootstrap resamples whole runs with replacement and recomputes the edge-minus-control statistic. The interval is therefore a run-stability interval, not an event-level binomial interval.

| metric                  |   edge_value |   matched_control_value |          delta |         ci_low |        ci_high | unit               |
|:------------------------|-------------:|------------------------:|---------------:|---------------:|---------------:|:-------------------|
| secondary_fraction      |    0.0304452 |               0.0954635 |     -0.0650183 |     -0.070833  |     -0.0597468 | fraction           |
| timing_tail_fraction    |    0.0763837 |               0.1067    |     -0.0303165 |     -0.0425832 |     -0.0204968 | fraction           |
| median_amp_adc          | 2331         |            4228         |  -1897         |  -2198.89      |  -1658.63      | ADC or ADC-samples |
| dynamic_amp_adc         | 4202         |            4241         |    -39         |    -56.7625    |     -5.425     | ADC or ADC-samples |
| signed_area_adc_samples | 9055.5       |           37031.5       | -27976         | -30117.4       | -22333.3       | ADC or ADC-samples |
| baseline_excursion_adc  |  822         |              19         |    803         |    673.275     |    933.3       | ADC or ADC-samples |

Propagation by atom/current/topology:

| primary_atom          | current_group   | dynamic_topology       |     n |   secondary_fraction |   timing_tail_fraction |   charge_area_median |   baseline_excursion_median |   saturation_fraction |   dropout_proxy_fraction |   pid_support_proxy_fraction |   median_energy_range_proxy |
|:----------------------|:----------------|:-----------------------|------:|---------------------:|-----------------------:|---------------------:|----------------------------:|----------------------:|-------------------------:|-----------------------------:|----------------------------:|
| baseline_excursion    | high_20nA       | B2_only                | 88118 |          0.0422729   |               0        |              50571.5 |                       628   |                     1 |                 0.214145 |                            0 |                           2 |
| dynamic_only          | high_20nA       | B2_only                | 40869 |          2.44684e-05 |               0        |             -30343   |                       785   |                     1 |                 0.991632 |                            0 |                           2 |
| baseline_excursion    | high_20nA       | B2_plus_one_downstream | 12840 |          0.0872274   |               0        |              25107   |                      1713   |                     1 |                 0.320872 |                            0 |                           2 |
| dynamic_only          | high_20nA       | B2_plus_one_downstream |  8953 |          0           |               0        |             -26006   |                       956   |                     1 |                 0.997096 |                            0 |                           4 |
| baseline_excursion    | high_20nA       | B2_plus_ge2_downstream |  8010 |          0.0686642   |               0.887391 |              19194   |                      1734.5 |                     1 |                 0.372285 |                            1 |                           4 |
| median_threshold_edge | high_20nA       | B2_only                |  7845 |          0.000382409 |               0        |               7093   |                        31   |                     1 |                 0.354111 |                            0 |                           2 |
| dynamic_only          | high_20nA       | B2_plus_ge2_downstream |  5818 |          0           |               0.779993 |             -24038   |                      1021   |                     1 |                 0.997594 |                            1 |                           4 |
| baseline_excursion    | high_20nA       | all_four               |  5385 |          0.0352832   |               0.206314 |              15460   |                      1605   |                     1 |                 0.387744 |                            1 |                           4 |
| dynamic_only          | high_20nA       | all_four               |  3755 |          0           |               0.222903 |             -20007   |                      1005   |                     1 |                 0.998935 |                            1 |                           4 |
| baseline_excursion    | low_2nA         | B2_only                |  1139 |          0.0570676   |               0        |              51269   |                       549   |                     1 |                 0.130817 |                            0 |                           2 |
| median_threshold_edge | high_20nA       | B2_plus_one_downstream |   859 |          0           |               0        |             -11444   |                      1733   |                     1 |                 0.752037 |                            0 |                           4 |
| median_threshold_edge | high_20nA       | B2_plus_ge2_downstream |   555 |          0           |               0.854054 |              -7867   |                      1919   |                     1 |                 0.751351 |                            1 |                           4 |
| dynamic_only          | high_20nA       | B4_only                |   414 |          0           |               0        |             -16338.5 |                       811   |                     1 |                 0.985507 |                            0 |                           4 |
| dynamic_only          | low_2nA         | B2_only                |   411 |          0           |               0        |             -30264   |                       675   |                     1 |                 0.985401 |                            0 |                           2 |
| median_threshold_edge | high_20nA       | all_four               |   362 |          0           |               0.196133 |              -6452.5 |                      2104.5 |                     1 |                 0.80663  |                            1 |                           6 |
| dynamic_only          | high_20nA       | B6_only                |   257 |          0           |               0        |             -17447   |                       738   |                     1 |                 0.984436 |                            0 |                           6 |
| dynamic_only          | high_20nA       | B8_only                |   191 |          0           |               0        |             -16501   |                       753   |                     1 |                 0.963351 |                            0 |                           8 |
| baseline_excursion    | high_20nA       | B4_only                |   117 |          0.0598291   |               0        |              23959   |                      1366   |                     1 |                 0.316239 |                            0 |                           4 |

Matched strata summary:

| population       | current_group   | dynamic_topology       |      n |   secondary_fraction |   timing_tail_fraction |   median_dynamic_amp_adc |
|:-----------------|:----------------|:-----------------------|-------:|---------------------:|-----------------------:|-------------------------:|
| matched_s00_core | high_20nA       | B2_only                | 136832 |            0.0950801 |               0        |                   5050   |
| matched_s00_core | high_20nA       | B2_plus_one_downstream |  22652 |            0.122682  |               0        |                   3635   |
| matched_s00_core | high_20nA       | B2_plus_ge2_downstream |  14383 |            0.0890635 |               0.982201 |                   3103   |
| matched_s00_core | high_20nA       | all_four               |   9502 |            0.0509366 |               0.593349 |                   2750   |
| matched_s00_core | low_2nA         | B2_only                |   1659 |            0.102471  |               0        |                   4996   |
| matched_s00_core | high_20nA       | B4_only                |    588 |            0.0391156 |               0        |                   2179.5 |
| matched_s00_core | high_20nA       | B6_only                |    414 |            0.0652174 |               0        |                   2499   |
| matched_s00_core | high_20nA       | B8_only                |    294 |            0.0646259 |               0        |                   2057   |
| matched_s00_core | high_20nA       | downstream_ge2         |    112 |            0.0535714 |               0.901786 |                   2606.5 |
| matched_s00_core | low_2nA         | B2_plus_one_downstream |     45 |            0.133333  |               0        |                   3531   |
| matched_s00_core | low_2nA         | B2_plus_ge2_downstream |     21 |            0.047619  |               1        |                   3255   |
| matched_s00_core | high_20nA       | all_downstream         |     13 |            0         |               0.769231 |                   1789   |
| matched_s00_core | low_2nA         | all_four               |     10 |            0         |               0.6      |                   2771.5 |
| matched_s00_core | low_2nA         | B6_only                |      4 |            0.25      |               0        |                   1788   |

## Model Benchmark

All models use the same train/held-out split by run; held-out runs are `[42, 57, 64, 65]`. Learned features exclude run, event number, current label, median amplitude, dynamic amplitude, dynamic-minus-median, baseline-excursion ADC, and atom labels. The traditional fixed-secondary waveform rubric is included as a non-learned reference. The ML/NN panel contains ridge, histogram gradient-boosted trees, MLP, 1D-CNN, and a new shape-residual fusion ExtraTrees architecture using train-only PCA waveform coordinates plus non-selector shape summaries. The target is selector-edge atom membership versus exact matched S00 core controls.

| method                            |   roc_auc |   roc_auc_ci_low |   roc_auc_ci_high |   average_precision |   balanced_accuracy |     brier | eligible_winner   |
|:----------------------------------|----------:|-----------------:|------------------:|--------------------:|--------------------:|----------:|:------------------|
| new_shape_residual_fusion         |  0.989331 |         0.981542 |          0.995395 |            0.991093 |              0.9475 | 0.036121  | True              |
| gradient_boosted_trees            |  0.986297 |         0.977351 |          0.994297 |            0.988147 |              0.9325 | 0.045376  | True              |
| mlp                               |  0.982106 |         0.971175 |          0.993593 |            0.985379 |              0.92   | 0.0466338 | True              |
| ridge                             |  0.949084 |         0.928135 |          0.971328 |            0.962615 |              0.8825 | 0.120083  | True              |
| cnn_1d                            |  0.768841 |         0.737551 |          0.828626 |            0.83631  |              0.72   | 0.24424   | True              |
| traditional_fixed_secondary_score |  0.4725   |         0.445    |          0.5      |            0.492552 |              0.5    | 0.5275    | True              |
| shuffled_label_fusion_control     |  0.478762 |         0.460549 |          0.5006   |            0.489776 |              0.495  | 0.264329  | False             |

Leakage and control checks:

| check                                         |    value | pass   | note                                                                               |
|:----------------------------------------------|---------:|:-------|:-----------------------------------------------------------------------------------|
| train_heldout_run_overlap                     | 0        | True   | split unit is run                                                                  |
| forbidden_feature_columns_absent              | 0        | True   | run,event,current,selector amplitudes,baseline excursion excluded from ML matrices |
| shuffled_label_fusion_control_auc_near_chance | 0.478762 | True   | within-train shuffled labels should not identify held-out dynamic membership       |

## Interpretation

The selector-edge population does not behave like a single clean physics class. A true pile-up-like edge population would show a positive secondary-fraction excess without large baseline or charge-area displacement. Instead, the ledger separates several mechanisms: dynamic-only and baseline-excursion atoms carry the strongest selector-systematic signature, while near-threshold median/dynamic atoms quantify how much of the edge support is ordinary threshold geometry. The PID and energy columns are proxies: raw B-stave topology and deepest selected stave are support indicators, not calibrated particle identity or deposited energy.

The model benchmark is diagnostic rather than selector-adopting. High edge-vs-core separability means the edge support remains morphologically distinct after exact matching; it does not convert the edge population into a truth label. The winner is therefore named for predictive discrimination, while the physics verdict follows the run-block matched deltas and atom ledger.

## Hypothesis and Next Test

The working hypothesis is that most selector-edge records are readout/selector-support atoms rather than recoverable physics categories: dynamic-only and baseline-excursion rows carry large negative signed-area shifts and large baseline excursions even after exact run/current/stave/amplitude/topology matching. A falsifying result would be a calibrated PID/energy join showing that these same atoms occupy the same particle and energy support as S00 non-edge controls while retaining a positive secondary or timing-tail excess. The single follow-up proposed in `result.json` therefore replaces the raw topology, PID, and energy proxies used here with calibrated downstream labels.

## Systematics and Caveats

- **Topology/PID/energy proxies:** matching uses raw B-stave multiplicity topology, and PID/energy support are proxy columns. They are useful for propagation screening but cannot replace calibrated PID or energy reconstruction.
- **Control support:** exact matching discards unmatched edge rows. Coverage and support tables are therefore part of the result, not bookkeeping.
- **Pile-up proxy:** the two-peak rubric is intentionally conservative and deterministic; it is not a truth label.
- **Timing tails:** CFD20 spans are undefined for events without at least two downstream dynamic-selected staves, so timing-tail fractions are support-conditional.
- **ML interpretation:** ML/NN methods are leakage guarded, but they target selector-edge membership, not physical pile-up or particle identity.
- **Priority labels:** each row receives one primary atom by priority. Overlapping flags remain available in `selector_edge_table.csv.gz` for downstream multi-label analyses.

## Artifacts

Main tables are `reproduction_match_table.csv`, `selector_counts_by_run.csv`, `selector_atom_ledger.csv`, `s00c_mistake_atom_ledger.csv`, `atom_propagation_ledger.csv`, `matched_support_summary.csv`, `primary_delta_metrics.csv`, `matched_strata_summary.csv`, `model_benchmark.csv`, `heldout_model_scores.csv.gz`, `selector_edge_table.csv.gz`, `leakage_checks.csv`, `input_sha256.csv`, `manifest.json`, and `result.json`.
