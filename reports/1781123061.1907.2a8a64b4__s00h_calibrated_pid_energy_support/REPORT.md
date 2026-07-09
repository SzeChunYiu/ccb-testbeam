# S00h: selector-edge atom ledger with joined calibrated PID-energy support

- **Ticket:** `1781123061.1907.2a8a64b4`
- **Worker:** `testbeam-laptop-1`
- **Command:** `/home/billy/anaconda3/bin/python scripts/s00h_1781123061_1907_2a8a64b4_calibrated_pid_energy_support.py`
- **Input:** raw B-stack `HRDv` ROOT files under `/home/billy/Desktop/test_beam/data/root/root`

## Abstract

This study tests the S00g selector-edge atoms after replacing raw PID and energy proxy interpretation with joined calibrated support labels. The raw ROOT reproduction gate returns **640,737** S00 median-first-four pulses and **65,636** dynamic-only pulses, exactly matching the S00/S00c/S00d anchors. Each dynamic-selected record is assigned calibrated PID residual support and calibrated charge/energy support from frozen downstream artifacts before exact matching. After matching selector-edge atoms to S00 non-edge controls by run, current label, stave, dynamic-amplitude bin, topology, calibrated PID support, and calibrated energy support, the physics-facing verdict is **selector_systematic_atom**. The predictive benchmark winner recorded in `result.json` is **new_shape_residual_fusion**.

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

Early peak, late tail, saturation, and dropout are deliberately not control-excluding atom definitions; they are propagation columns used to test whether the selector edge leaks into timing, amplitude, saturation, pile-up, baseline, or dropout support. PID and energy enter this S00h pass through joined calibrated support labels rather than the S00g raw proxy columns.

## Calibrated Support Join

The event-level calibrated PID support is not particle truth. It is a deterministic residual support label:

\[
r_i = w(\mathrm{topology}_i) + 0.015(d_i-1.5) + 0.002\log(1+Q_i),
\]

where \(d_i\) is the B-stave depth index and \(Q_i\) is positive waveform area. Run/depth residual thresholds from the P08d calibrated-label artifact assign low, middle, and high residual support. The charge/energy support label bins \(\log(1+Q_i)\) into run-global quartiles and records the S14g truth-energy bin table as a reference. The S17a GEANT4 PID/depth table is summarized to document downstream PID/depth support, but no simulated event identity is joined to raw data rows.

Calibration sources are written to `calibrated_support_sources.csv`, with GEANT4 PID/depth summaries in `g4_pid_depth_reference.csv` and energy-bin references in `calibrated_energy_bin_reference.csv`.

The S00c honest-summary selector mistakes are reproduced with the same S00c sampling rule and honest logistic features (`wave_max`, `wave_min`, `pre4_mean/std`, `post_mean/std`, `dynamic_amp`, and `stave_idx`; no `median_amp`, run id, or event id). On held-out runs `[57, 65]`, the reproduced S00c-like model has 556 false positives and 78 false negatives.

| primary_atom          |      n |   fraction_of_edge |   runs |   median_amp_adc |   dynamic_amp_adc |   baseline_excursion_adc |   secondary_fraction |   timing_tail_fraction |   saturation_fraction |   dropout_proxy_fraction |   calibrated_deuteron_like_fraction |   calibrated_ambiguous_pid_fraction | dominant_calibrated_energy_support   |
|:----------------------|-------:|-------------------:|-------:|-----------------:|------------------:|-------------------------:|---------------------:|-----------------------:|----------------------:|-------------------------:|------------------------------------:|------------------------------------:|:-------------------------------------|
| baseline_excursion    | 119017 |          0.608761  |     33 |           4895.5 |              5896 |                      843 |          0.0503626   |              0.0764513 |                     1 |                 0.245536 |                            0.279943 |                            0.46127  | energy_q4                            |
| dynamic_only          |  65636 |          0.335722  |     33 |            351.5 |              3255 |                      831 |          1.52355e-05 |              0.0946737 |                     1 |                 0.992565 |                            0.371458 |                            0.529618 | energy_q1                            |
| median_threshold_edge |  10854 |          0.0555172 |     33 |           1074.5 |              1138 |                       40 |          0.000368528 |              0.0648609 |                     1 |                 0.402893 |                            0.401419 |                            0.507647 | energy_q1                            |

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
(\mathrm{run},\mathrm{current},\mathrm{stave},\mathrm{dynamic\ amplitude\ bin},\mathrm{topology},\mathrm{calibrated\ PID\ support},\mathrm{calibrated\ energy\ support}).
\]

Topology remains the raw-root B-stave multiplicity because the ticket requested the same topology matching, while PID and energy support are the calibrated downstream labels. Exact matched coverage is **0.637**: 124,581 edge pulses and 124,581 S00 core controls.

Top support strata:

| match_key                                                                          |   edge_n |   control_n |   matched_n |
|:-----------------------------------------------------------------------------------|---------:|------------:|------------:|
| 56\|high_20nA\|B2\|(7000.0, 12000.0]\|B2_only\|proton_like_low_residual\|energy_q4 |     4898 |       14557 |        4898 |
| 50\|high_20nA\|B2\|(7000.0, 12000.0]\|B2_only\|proton_like_low_residual\|energy_q4 |     3621 |       13822 |        3621 |
| 31\|high_20nA\|B2\|(7000.0, 12000.0]\|B2_only\|ambiguous_mid_residual\|energy_q4   |     2788 |        7724 |        2788 |
| 32\|high_20nA\|B2\|(7000.0, 12000.0]\|B2_only\|ambiguous_mid_residual\|energy_q4   |     2671 |        7548 |        2671 |
| 55\|high_20nA\|B2\|(7000.0, 12000.0]\|B2_only\|proton_like_low_residual\|energy_q4 |     1625 |        5870 |        1625 |
| 53\|high_20nA\|B2\|(7000.0, 12000.0]\|B2_only\|proton_like_low_residual\|energy_q4 |     1561 |       10970 |        1561 |
| 51\|high_20nA\|B2\|(7000.0, 12000.0]\|B2_only\|proton_like_low_residual\|energy_q4 |     1498 |        4988 |        1498 |
| 54\|high_20nA\|B2\|(7000.0, 12000.0]\|B2_only\|proton_like_low_residual\|energy_q4 |     1468 |       10418 |        1468 |
| 56\|high_20nA\|B2\|(4500.0, 7000.0]\|B2_only\|proton_like_low_residual\|energy_q3  |     1405 |        8236 |        1405 |
| 45\|high_20nA\|B2\|(7000.0, 12000.0]\|B2_only\|ambiguous_mid_residual\|energy_q4   |     1177 |        2988 |        1177 |
| 34\|high_20nA\|B2\|(7000.0, 12000.0]\|B2_only\|proton_like_low_residual\|energy_q4 |     1102 |       12858 |        1102 |
| 37\|high_20nA\|B2\|(7000.0, 12000.0]\|B2_only\|ambiguous_mid_residual\|energy_q4   |     1069 |        2655 |        1069 |

## Propagation Metrics

The secondary-fraction proxy is a frozen two-peak waveform rubric: a post-peak maximum at least 0.28 of the normalized dynamic amplitude, separated by at least 20 ns, with an intervening dip of at least 0.08 and no strong early/noisy pathology. Timing-tail fraction is \(I[\Delta t_{\rm downstream}>5\,\mathrm{ns}]\), where \(\Delta t_{\rm downstream}\) is the event-level B4/B6/B8 CFD20 span. Charge bias is reported with the signed waveform area.

The run-block bootstrap resamples whole runs with replacement and recomputes the edge-minus-control statistic. The interval is therefore a run-stability interval, not an event-level binomial interval.

| metric                  |    edge_value |   matched_control_value |         delta |        ci_low |      ci_high | unit               |
|:------------------------|--------------:|------------------------:|--------------:|--------------:|-------------:|:-------------------|
| secondary_fraction      |     0.0448704 |               0.0617992 |    -0.0169287 |    -0.019465  |   -0.0144053 | fraction           |
| timing_tail_fraction    |     0.0816657 |               0.115371  |    -0.033705  |    -0.0468281 |   -0.0209027 | fraction           |
| median_amp_adc          |  4214.5       |            4555         |  -340.5       |  -385.025     |   -1.2125    | ADC or ADC-samples |
| dynamic_amp_adc         |  4636         |            4569         |    67         |     3.475     |  301.05      | ADC or ADC-samples |
| signed_area_adc_samples | 35936         |           39434         | -3498         | -3850.74      | -607.113     | ADC or ADC-samples |
| baseline_excursion_adc  |   631         |              20         |   611         |   525.275     |  729.2       | ADC or ADC-samples |

Propagation by atom/current/topology/calibrated support:

| primary_atom          | current_group   | dynamic_topology       | calibrated_pid_support      | calibrated_energy_support   |     n |   secondary_fraction |   timing_tail_fraction |   charge_area_median |   baseline_excursion_median |   saturation_fraction |   dropout_proxy_fraction |
|:----------------------|:----------------|:-----------------------|:----------------------------|:----------------------------|------:|---------------------:|-----------------------:|---------------------:|----------------------------:|----------------------:|-------------------------:|
| baseline_excursion    | high_20nA       | B2_only                | proton_like_low_residual    | energy_q4                   | 18947 |          0.00823349  |               0        |              64266   |                       370   |                     1 |              0.000686124 |
| baseline_excursion    | high_20nA       | B2_only                | ambiguous_mid_residual      | energy_q4                   | 14878 |          0.0246673   |               0        |              63858   |                       468   |                     1 |              0.00080656  |
| baseline_excursion    | high_20nA       | B2_only                | ambiguous_mid_residual      | energy_q2                   | 10060 |          0.165805    |               0        |              30497   |                      1172   |                     1 |              0.122167    |
| baseline_excursion    | high_20nA       | B2_only                | ambiguous_mid_residual      | energy_q3                   |  9889 |          0.0477298   |               0        |              50516   |                       583   |                     1 |              0.000910102 |
| dynamic_only          | high_20nA       | B2_only                | ambiguous_mid_residual      | energy_q1                   |  9589 |          0           |               0        |             -18299   |                       741   |                     1 |              0.980081    |
| baseline_excursion    | high_20nA       | B2_only                | proton_like_low_residual    | energy_q3                   |  6061 |          0.0212836   |               0        |              53228   |                       360   |                     1 |              0.000659957 |
| baseline_excursion    | high_20nA       | B2_plus_one_downstream | deuteron_like_high_residual | energy_q2                   |  5146 |          0.170035    |               0        |              28516.5 |                      1363   |                     1 |              0.0907501   |
| dynamic_only          | high_20nA       | B2_plus_one_downstream | deuteron_like_high_residual | energy_q1                   |  3579 |          0           |               0        |             -19600   |                       906   |                     1 |              0.991618    |
| baseline_excursion    | high_20nA       | B2_plus_ge2_downstream | deuteron_like_high_residual | energy_q2                   |  3435 |          0.137991    |               0.917613 |              25017   |                      1179   |                     1 |              0.0681223   |
| dynamic_only          | high_20nA       | B2_plus_ge2_downstream | deuteron_like_high_residual | energy_q1                   |  3324 |          0           |               0.755716 |             -21037   |                       992   |                     1 |              0.996089    |
| median_threshold_edge | high_20nA       | B2_only                | ambiguous_mid_residual      | energy_q1                   |  3119 |          0.000320616 |               0        |               7407   |                        20   |                     1 |              0.118628    |
| baseline_excursion    | high_20nA       | B2_only                | ambiguous_mid_residual      | energy_q1                   |  3042 |          0.000657462 |               0        |               9759   |                      1231.5 |                     1 |              0.468113    |
| dynamic_only          | high_20nA       | all_four               | deuteron_like_high_residual | energy_q1                   |  2872 |          0           |               0.200905 |             -18241   |                      1015   |                     1 |              0.997911    |
| baseline_excursion    | high_20nA       | B2_only                | deuteron_like_high_residual | energy_q2                   |  2659 |          0.1478      |               0        |              29037   |                      2334   |                     1 |              0.156074    |
| baseline_excursion    | high_20nA       | all_four               | deuteron_like_high_residual | energy_q1                   |  2414 |          0.0008285   |               0.139188 |              10277.5 |                      1657.5 |                     1 |              0.547225    |
| baseline_excursion    | high_20nA       | B2_only                | proton_like_low_residual    | energy_q2                   |  2372 |          0.113406    |               0        |              30100.5 |                      1044.5 |                     1 |              0.106239    |
| dynamic_only          | high_20nA       | B2_only                | proton_like_low_residual    | energy_q1                   |  2037 |          0.000490918 |               0        |             -17922   |                       725   |                     1 |              0.979872    |
| baseline_excursion    | high_20nA       | B2_plus_ge2_downstream | deuteron_like_high_residual | energy_q1                   |  1910 |          0.0026178   |               0.857592 |               9003.5 |                      1982   |                     1 |              0.636649    |

Matched strata summary:

| population       | current_group   | dynamic_topology       | calibrated_pid_support      | calibrated_energy_support   |     n |   secondary_fraction |   timing_tail_fraction |   median_dynamic_amp_adc |
|:-----------------|:----------------|:-----------------------|:----------------------------|:----------------------------|------:|---------------------:|-----------------------:|-------------------------:|
| matched_s00_core | high_20nA       | B2_only                | proton_like_low_residual    | energy_q4                   | 18947 |          0.0172059   |               0        |                   8017   |
| matched_s00_core | high_20nA       | B2_only                | ambiguous_mid_residual      | energy_q1                   | 15750 |          0.000571429 |               0        |                   1881.5 |
| matched_s00_core | high_20nA       | B2_only                | ambiguous_mid_residual      | energy_q4                   | 14878 |          0.0557199   |               0        |                   8137   |
| matched_s00_core | high_20nA       | B2_only                | ambiguous_mid_residual      | energy_q2                   | 10060 |          0.209245    |               0        |                   4019.5 |
| matched_s00_core | high_20nA       | B2_only                | ambiguous_mid_residual      | energy_q3                   |  9889 |          0.0687633   |               0        |                   5986   |
| matched_s00_core | high_20nA       | B2_only                | proton_like_low_residual    | energy_q3                   |  6061 |          0.0404224   |               0        |                   6255   |
| matched_s00_core | high_20nA       | B2_plus_ge2_downstream | deuteron_like_high_residual | energy_q1                   |  5612 |          0.0067712   |               0.982181 |                   2403   |
| matched_s00_core | high_20nA       | all_four               | deuteron_like_high_residual | energy_q1                   |  5588 |          0.00250537  |               0.570687 |                   2264   |
| matched_s00_core | high_20nA       | B2_plus_one_downstream | deuteron_like_high_residual | energy_q1                   |  5408 |          0.0112796   |               0        |                   2384   |
| matched_s00_core | high_20nA       | B2_plus_one_downstream | deuteron_like_high_residual | energy_q2                   |  5146 |          0.16129     |               0        |                   3652   |
| matched_s00_core | high_20nA       | B2_only                | deuteron_like_high_residual | energy_q1                   |  3864 |          0.000776398 |               0        |                   1467   |
| matched_s00_core | high_20nA       | B2_plus_ge2_downstream | deuteron_like_high_residual | energy_q2                   |  3435 |          0.133333    |               0.980495 |                   3277   |
| matched_s00_core | high_20nA       | B2_only                | proton_like_low_residual    | energy_q1                   |  3339 |          0.000299491 |               0        |                   1860   |
| matched_s00_core | high_20nA       | B2_only                | deuteron_like_high_residual | energy_q2                   |  2659 |          0.180519    |               0        |                   4086   |

## Model Benchmark

All models use the same train/held-out split by run; held-out runs are `[42, 57, 64, 65]`. Learned features exclude run, event number, current label, median amplitude, dynamic amplitude, dynamic-minus-median, baseline-excursion ADC, atom labels, and the calibrated PID/energy support labels. The calibrated labels are used only for matching and stratification. The traditional fixed-secondary waveform rubric is included as a non-learned reference. The ML/NN panel contains ridge, gradient-boosted trees, MLP, 1D-CNN, and a new shape-residual fusion ExtraTrees architecture using train-only PCA waveform coordinates plus non-selector shape summaries. The target is selector-edge atom membership versus exact matched S00 core controls.

| method                            |   roc_auc |   roc_auc_ci_low |   roc_auc_ci_high |   average_precision |   balanced_accuracy |     brier | eligible_winner   |
|:----------------------------------|----------:|-----------------:|------------------:|--------------------:|--------------------:|----------:|:------------------|
| new_shape_residual_fusion         |  0.988338 |         0.984335 |          0.993619 |            0.990216 |             0.94    | 0.0405773 | True              |
| gradient_boosted_trees            |  0.9819   |         0.970293 |          0.989365 |            0.984758 |             0.92375 | 0.0512732 | True              |
| mlp                               |  0.980219 |         0.970156 |          0.989763 |            0.984132 |             0.9225  | 0.0480237 | True              |
| ridge                             |  0.933263 |         0.906981 |          0.958131 |            0.952751 |             0.8825  | 0.134973  | True              |
| cnn_1d                            |  0.621475 |         0.575788 |          0.687056 |            0.715308 |             0.575   | 0.248289  | True              |
| traditional_fixed_secondary_score |  0.48875  |         0.47     |          0.50875  |            0.495452 |             0.5     | 0.51125   | True              |
| shuffled_label_fusion_control     |  0.551694 |         0.527388 |          0.56701  |            0.551696 |             0.545   | 0.251774  | False             |

Leakage and control checks:

| check                                         |    value | pass   | note                                                                               |
|:----------------------------------------------|---------:|:-------|:-----------------------------------------------------------------------------------|
| train_heldout_run_overlap                     | 0        | True   | split unit is run                                                                  |
| forbidden_feature_columns_absent              | 0        | True   | run,event,current,selector amplitudes,baseline excursion excluded from ML matrices |
| shuffled_label_fusion_control_auc_near_chance | 0.551694 | True   | within-train shuffled labels should not identify held-out dynamic membership       |

## Interpretation

The selector-edge population does not behave like a single clean physics class. A true pile-up-like edge population would show a positive secondary-fraction excess without large baseline or charge-area displacement. Instead, the calibrated-support ledger separates several mechanisms: dynamic-only and baseline-excursion atoms carry the strongest selector-systematic signature, while near-threshold median/dynamic atoms quantify how much of the edge support is ordinary threshold geometry. The calibrated PID and energy columns are support labels, not event-level particle identity or deposited-energy truth.

The model benchmark is diagnostic rather than selector-adopting. High edge-vs-core separability means the edge support remains morphologically distinct after exact matching; it does not convert the edge population into a truth label. The winner is therefore named for predictive discrimination, while the physics verdict follows the run-block matched deltas and atom ledger.

## Hypothesis Test

The working hypothesis is that most selector-edge records are readout/selector-support atoms rather than recoverable physics categories. S00h directly tests the S00g follow-up: if the edge signature were merely a raw proxy artifact, then joining calibrated PID/energy support into the matching key should remove or strongly reduce the selector-systematic deltas. The observed matched deltas retain the verdict **selector_systematic_atom**, so the calibrated-label pass supports a detector/selector support shift rather than a pure raw-proxy artifact.

## Systematics and Caveats

- **Calibrated support is not truth:** PID support is a residual-threshold label calibrated from frozen downstream artifacts, and energy support is a charge-bin support label documented against truth-energy bins. Neither is event-level particle truth.
- **Topology remains raw:** topology is intentionally retained as the raw B-stave multiplicity term from S00g so the calibrated PID/energy join is the isolated change.
- **Control support:** exact matching discards unmatched edge rows. Coverage and support tables are therefore part of the result, not bookkeeping.
- **Pile-up proxy:** the two-peak rubric is intentionally conservative and deterministic; it is not a truth label.
- **Timing tails:** CFD20 spans are undefined for events without at least two downstream dynamic-selected staves, so timing-tail fractions are support-conditional.
- **ML interpretation:** ML/NN methods are leakage guarded, but they target selector-edge membership, not physical pile-up or particle identity.
- **Priority labels:** each row receives one primary atom by priority. Overlapping flags remain available in `selector_edge_table.csv.gz` for downstream multi-label analyses.

## Artifacts

Main tables are `reproduction_match_table.csv`, `selector_counts_by_run.csv`, `calibrated_support_sources.csv`, `g4_pid_depth_reference.csv`, `calibrated_energy_bin_reference.csv`, `selector_atom_ledger.csv`, `s00c_mistake_atom_ledger.csv`, `atom_propagation_ledger.csv`, `matched_support_summary.csv`, `primary_delta_metrics.csv`, `matched_strata_summary.csv`, `model_benchmark.csv`, `heldout_model_scores.csv.gz`, `selector_edge_table.csv.gz`, `matched_pulse_table.csv.gz`, `leakage_checks.csv`, `input_sha256.csv`, `manifest.json`, and `result.json`.
