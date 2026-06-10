# S02f: class-conditioned dynamic selector timing

- **Ticket:** `1781032398.9095.04982d52`
- **Worker:** `testbeam-laptop-4`
- **Date:** 2026-06-10
- **Config:** `configs/s02f_1781032398_9095_04982d52_class_conditioned_dynamic_selector_timing.json`
- **Raw input:** B-stack ROOT files under `data/root/root`
- **Source residual models:** `reports/1781030650.597.5d382001__s03j_selector_timewalk_support`
- **Source taxonomy:** `reports/1781014251.574.7a497937`

## Reproduction First

The first executable step reran the raw ROOT selector anchors, before joining taxonomy or timing residuals. The median-first-four gate is

\[
A_{\mathrm{med4}}=\max_t\left(x_t-\operatorname{median}(x_0,x_1,x_2,x_3)\right)>1000\ \mathrm{ADC},
\]

and the dynamic-range gate is

\[
A_{\mathrm{dyn}}=\max_t x_t-\min_t x_t>1000\ \mathrm{ADC}.
\]

S00 median-first-four reproduction:

| quantity                           |   report_value |   reproduced |   delta |   tolerance | pass   |
|:-----------------------------------|---------------:|-------------:|--------:|------------:|:-------|
| total selected B-stave pulses      |         640737 |       640737 |       0 |           0 | True   |
| sample_ii_analysis selected_pulses |         125096 |       125096 |       0 |           0 | True   |
| sample_ii_analysis B2              |          88213 |        88213 |       0 |           0 | True   |
| sample_ii_analysis B4              |          21229 |        21229 |       0 |           0 | True   |
| sample_ii_analysis B6              |          11148 |        11148 |       0 |           0 | True   |
| sample_ii_analysis B8              |           4506 |         4506 |       0 |           0 | True   |

S00a dynamic-range reproduction:

| quantity                              |   report_value |   reproduced |   delta |   tolerance | pass   |
|:--------------------------------------|---------------:|-------------:|--------:|------------:|:-------|
| S00 median-first-four selected pulses |         640737 |       640737 |       0 |           0 | True   |
| S00a dynamic-range equivalent count   |         706373 |       706373 |       0 |           0 | True   |
| Dynamic-only excess pulses            |          65636 |        65636 |       0 |           0 | True   |
| Median-only pulses                    |              0 |            0 |       0 |           0 | True   |

## Class Construction

The S00d pulse taxonomy is eventized on downstream staves B4/B6/B8. For dynamic-range-extra events, the event class is the priority/majority class among downstream pulses that are dynamic-only. For median-first-four controls, the class is the priority/majority class among selected downstream pulses. The priority order is `baseline_excursion, poor_template_match, large_downstream_timing_span, low_median_amp_dynamic_only, late_tail_or_delayed_peak, saturation_proxy, clean_template_like`.

Event support after joining S03j residuals to S00d taxonomy:

| selector_gate       | taxonomy_class               |   n_events |   n_runs |
|:--------------------|:-----------------------------|-----------:|---------:|
| dynamic_range_extra | baseline_excursion           |        661 |        7 |
| dynamic_range_extra | large_downstream_timing_span |         10 |        5 |
| dynamic_range_extra | poor_template_match          |          1 |        1 |
| dynamic_range_full  | large_downstream_timing_span |       1766 |        7 |
| dynamic_range_full  | baseline_excursion           |       1536 |        7 |
| dynamic_range_full  | late_tail_or_delayed_peak    |        909 |        7 |
| dynamic_range_full  | clean_template_like          |        161 |        7 |
| dynamic_range_full  | poor_template_match          |        120 |        7 |
| matched_control     | baseline_excursion           |         43 |        7 |
| matched_control     | large_downstream_timing_span |         28 |        6 |
| matched_control     | late_tail_or_delayed_peak    |         11 |        5 |
| matched_control     | clean_template_like          |          4 |        3 |
| matched_control     | poor_template_match          |          1 |        1 |
| median_first_four   | large_downstream_timing_span |       1756 |        7 |
| median_first_four   | late_tail_or_delayed_peak    |        909 |        7 |
| median_first_four   | baseline_excursion           |        875 |        7 |
| median_first_four   | clean_template_like          |        161 |        7 |
| median_first_four   | poor_template_match          |        119 |        7 |

## Methods

All timing residuals come from S03j leave-one-run-out fits. In every fold the held-out run is excluded before template building, timewalk closure, and ML/NN training. The corrected pair residual for staves \(i,j\) is

\[
r_{ij} = \left(t_i - z_i/v\right)-\left(t_j-z_j/v\right),\qquad v^{-1}=0.078\ \mathrm{ns/cm}.
\]

The robust timing width is \(\sigma_{68}=(Q_{0.84}-Q_{0.16})/2\). Full RMS is the ordinary centered RMS, and the tail fraction is \(P(|r-\operatorname{median} r|>5\ \mathrm{ns})\).

The strong traditional baseline is `signed_physics_prior` (strong traditional signed timewalk prior). It is benchmarked against:

| method                     | description                              |
|:---------------------------|:-----------------------------------------|
| signed_physics_prior       | strong traditional signed timewalk prior |
| ridge_ml                   | ridge residual regressor                 |
| gradient_boosted_trees_hgb | histogram gradient-boosted trees         |
| mlp_waveform               | waveform MLP                             |
| cnn_1d_waveform            | 1D-CNN waveform regressor                |
| hybrid_residual_ensemble   | new residual-ensemble architecture       |

The new architecture is `hybrid_residual_ensemble`, a residual ensemble over Ridge, HGB, MLP, and CNN residual predictions. It is treated as a candidate architecture, not as an oracle.

## Dynamic-Only Class Results

Primary dynamic-range-extra event-bootstrap summaries:

| taxonomy_class               | method                     |   n_events |   sigma68_ns |   sigma68_ci_low |   sigma68_ci_high |   full_rms_ns |   tail_frac_abs_gt5ns |   delta_sigma68_vs_traditional_ns |
|:-----------------------------|:---------------------------|-----------:|-------------:|-----------------:|------------------:|--------------:|----------------------:|----------------------------------:|
| large_downstream_timing_span | gradient_boosted_trees_hgb |         10 |      2.02982 |         0.856097 |          13.0569  |       7.91065 |              0.133333 |                        -12.1728   |
| baseline_excursion           | signed_physics_prior       |        661 |      2.08448 |         1.59283  |           2.6469  |       7.26569 |              0.193646 |                          0        |
| baseline_excursion           | hybrid_residual_ensemble   |        661 |      2.24483 |         1.84584  |           2.62295 |       6.12604 |              0.172466 |                          0.160349 |
| baseline_excursion           | gradient_boosted_trees_hgb |        661 |      2.3863  |         2.10262  |           2.64193 |       5.05197 |              0.15885  |                          0.301825 |
| baseline_excursion           | mlp_waveform               |        661 |      2.51982 |         2.15212  |           3.13023 |       7.30289 |              0.199697 |                          0.435347 |
| baseline_excursion           | cnn_1d_waveform            |        661 |      2.63761 |         2.23846  |           3.19103 |       7.31993 |              0.200706 |                          0.553134 |
| baseline_excursion           | ridge_ml                   |        661 |      3.15942 |         2.88644  |           3.51479 |       5.90072 |              0.203732 |                          1.07495  |
| large_downstream_timing_span | ridge_ml                   |         10 |      5.50335 |         2.04446  |          11.8296  |       6.8635  |              0.2      |                         -8.69922  |
| large_downstream_timing_span | hybrid_residual_ensemble   |         10 |     10.126   |         0.868366 |          13.6437  |       9.34649 |              0.2      |                         -4.0766   |
| large_downstream_timing_span | signed_physics_prior       |         10 |     14.2026  |         0.767091 |          15.0557  |      11.6104  |              0.2      |                          0        |
| large_downstream_timing_span | mlp_waveform               |         10 |     15.1518  |         1.27283  |          15.7726  |      12.1471  |              0.2      |                          0.949268 |
| large_downstream_timing_span | cnn_1d_waveform            |         10 |     15.2059  |         1.3854   |          15.6636  |      12.1533  |              0.2      |                          1.00333  |

Run-block bootstrap summaries by dynamic-only class:

| taxonomy_class               | method                     |   n_runs |   run_mean_sigma68_ns |   run_mean_sigma68_ci_low |   run_mean_sigma68_ci_high |   run_mean_full_rms_ns |   run_mean_tail_frac |
|:-----------------------------|:---------------------------|---------:|----------------------:|--------------------------:|---------------------------:|-----------------------:|---------------------:|
| baseline_excursion           | signed_physics_prior       |        7 |              1.93992  |                  1.26373  |                   2.55563  |               6.54806  |             0.173526 |
| baseline_excursion           | hybrid_residual_ensemble   |        7 |              2.03903  |                  1.52379  |                   2.47987  |               5.67523  |             0.15593  |
| baseline_excursion           | gradient_boosted_trees_hgb |        7 |              2.24179  |                  1.81673  |                   2.60232  |               4.88973  |             0.145943 |
| baseline_excursion           | mlp_waveform               |        7 |              2.31083  |                  1.71679  |                   2.88767  |               6.64492  |             0.172267 |
| baseline_excursion           | cnn_1d_waveform            |        7 |              2.40981  |                  1.80909  |                   2.97673  |               6.6696   |             0.172617 |
| baseline_excursion           | ridge_ml                   |        7 |              3.04643  |                  2.50271  |                   3.52726  |               5.53275  |             0.196198 |
| large_downstream_timing_span | gradient_boosted_trees_hgb |        5 |              3.82137  |                  0.779098 |                   8.61206  |               4.61969  |             0.1      |
| large_downstream_timing_span | ridge_ml                   |        5 |              5.03764  |                  1.37684  |                   9.08173  |               4.91999  |             0.166667 |
| large_downstream_timing_span | hybrid_residual_ensemble   |        5 |              5.68759  |                  1.18524  |                  10.2908   |               6.40489  |             0.166667 |
| large_downstream_timing_span | signed_physics_prior       |        5 |              6.84014  |                  1.26826  |                  12.412    |               7.85437  |             0.166667 |
| large_downstream_timing_span | mlp_waveform               |        5 |              7.38569  |                  1.71281  |                  12.8867   |               8.43717  |             0.166667 |
| large_downstream_timing_span | cnn_1d_waveform            |        5 |              7.44638  |                  1.78658  |                  13.1062   |               8.47631  |             0.166667 |
| poor_template_match          | gradient_boosted_trees_hgb |        1 |              0.372106 |                  0.372106 |                   0.372106 |               0.485871 |             0        |
| poor_template_match          | signed_physics_prior       |        1 |              0.528966 |                  0.528966 |                   0.528966 |               0.691578 |             0        |
| poor_template_match          | hybrid_residual_ensemble   |        1 |              0.789583 |                  0.789583 |                   0.789583 |               1.02836  |             0        |
| poor_template_match          | mlp_waveform               |        1 |              1.03765  |                  1.03765  |                   1.03765  |               1.28202  |             0        |
| poor_template_match          | cnn_1d_waveform            |        1 |              1.10319  |                  1.10319  |                   1.10319  |               1.35666  |             0        |
| poor_template_match          | ridge_ml                   |        1 |              1.34123  |                  1.34123  |                   1.34123  |               1.75873  |             0        |

Selector/class deltas are in `selector_class_deltas.csv`; positive values mean the dynamic-range-extra population is broader or more tailed than the comparison gate/control.

| taxonomy_class               | method                     | comparison                                  |   delta_sigma68_ns |   delta_full_rms_ns |   delta_tail_frac |
|:-----------------------------|:---------------------------|:--------------------------------------------|-------------------:|--------------------:|------------------:|
| baseline_excursion           | cnn_1d_waveform            | dynamic_range_extra_minus_matched_control   |         -0.200203  |          2.47673    |         0.123187  |
| baseline_excursion           | cnn_1d_waveform            | dynamic_range_extra_minus_median_first_four |         -0.0213284 |          3.73654    |         0.187754  |
| baseline_excursion           | gradient_boosted_trees_hgb | dynamic_range_extra_minus_matched_control   |          0.547465  |          0.00239941 |         0.127842  |
| baseline_excursion           | gradient_boosted_trees_hgb | dynamic_range_extra_minus_median_first_four |          1.30105   |          2.20653    |         0.144374  |
| baseline_excursion           | hybrid_residual_ensemble   | dynamic_range_extra_minus_matched_control   |          1.00173   |          1.48817    |         0.141458  |
| baseline_excursion           | hybrid_residual_ensemble   | dynamic_range_extra_minus_median_first_four |          1.50544   |          3.32479    |         0.159133  |
| baseline_excursion           | mlp_waveform               | dynamic_range_extra_minus_matched_control   |         -0.27067   |          2.47406    |         0.12993   |
| baseline_excursion           | mlp_waveform               | dynamic_range_extra_minus_median_first_four |          0.141643  |          3.87381    |         0.186745  |
| baseline_excursion           | ridge_ml                   | dynamic_range_extra_minus_matched_control   |          1.74855   |          0.800165   |         0.164972  |
| baseline_excursion           | ridge_ml                   | dynamic_range_extra_minus_median_first_four |          1.99778   |          2.86914    |         0.190398  |
| baseline_excursion           | signed_physics_prior       | dynamic_range_extra_minus_matched_control   |          0.647669  |          2.22089    |         0.147134  |
| baseline_excursion           | signed_physics_prior       | dynamic_range_extra_minus_median_first_four |          0.847864  |          4.1939     |         0.180313  |
| large_downstream_timing_span | cnn_1d_waveform            | dynamic_range_extra_minus_matched_control   |         12.1718    |          6.75681    |         0.116667  |
| large_downstream_timing_span | cnn_1d_waveform            | dynamic_range_extra_minus_median_first_four |         12.041     |          8.71301    |         0.0976841 |
| large_downstream_timing_span | gradient_boosted_trees_hgb | dynamic_range_extra_minus_matched_control   |          0.547621  |          3.13992    |         0.109524  |
| large_downstream_timing_span | gradient_boosted_trees_hgb | dynamic_range_extra_minus_median_first_four |          0.543903  |          5.63541    |         0.118147  |
| large_downstream_timing_span | hybrid_residual_ensemble   | dynamic_range_extra_minus_matched_control   |          8.90851   |          4.50203    |         0.17619   |
| large_downstream_timing_span | hybrid_residual_ensemble   | dynamic_range_extra_minus_median_first_four |          8.58064   |          6.9875     |         0.185004  |
| large_downstream_timing_span | mlp_waveform               | dynamic_range_extra_minus_matched_control   |         12.1489    |          6.75465    |         0.116667  |
| large_downstream_timing_span | mlp_waveform               | dynamic_range_extra_minus_median_first_four |         12.3248    |          8.91761    |         0.121792  |
| large_downstream_timing_span | ridge_ml                   | dynamic_range_extra_minus_matched_control   |          4.12154   |          1.90072    |         0.152381  |
| large_downstream_timing_span | ridge_ml                   | dynamic_range_extra_minus_median_first_four |          3.90341   |          4.48699    |         0.184244  |
| large_downstream_timing_span | signed_physics_prior       | dynamic_range_extra_minus_matched_control   |         12.7526    |          6.6995     |         0.152381  |
| large_downstream_timing_span | signed_physics_prior       | dynamic_range_extra_minus_median_first_four |         12.5573    |          9.13575    |         0.182346  |

## Winner

The ticket-level winner for the dynamic-range-extra class-conditioned benchmark is `signed_physics_prior` with pooled dynamic-extra \(\sigma_{68}=2.093\) ns. The best traditional baseline is `signed_physics_prior`. On the dynamic-only classes, the traditional signed prior remains the most defensible winner because the apparent ML/NN gains do not dominate across the sparse classes and because dynamic-only support is baseline-excursion dominated.

## Leakage And Oracle Checks

| check                                          |   value |   baseline_value | pass   | note                                                                   |
|:-----------------------------------------------|--------:|-----------------:|:-------|:-----------------------------------------------------------------------|
| forbidden_dynamic_class_pair_median_oracle     | 1.75    |          2.09283 | False  | uses held-out class/pair residual medians; diagnostic upper bound only |
| source_s03j_split_by_run                       | 1       |        nan       | True   | source timing residual models were fit in leave-one-run-out folds      |
| source_s03j_event_id_overlap_total             | 0       |          0       | True   | source train/held-out event-id overlap check                           |
| source_s03j_hgb_shuffled_target_min_sigma68_ns | 1.70896 |        nan       | True   | source shuffled-target leakage guard                                   |
| taxonomy_join_unmatched_fraction               | 0       |          0       | True   | S03j event ids map to S00d run/event_index taxonomy rows               |

Non-oracle leakage checks pass: `True`. The forbidden class/pair-median oracle is deliberately marked failing because it uses held-out class residual medians; it bounds the possible class-offset gain but is not a deployable method.

## Systematics And Caveats

The dominant systematic is class support: S00d found the dynamic-only population to be mostly baseline excursion, not a balanced physics sample. Sparse classes such as `clean_template_like` and `late_tail_or_delayed_peak` have wide class-conditioned intervals and can be driven by one or two runs. The analysis inherits S03j model fits rather than retraining them here; this is intentional provenance reuse, and the source run-split/leakage checks are carried into `leakage_checks.csv`.

Because class assignment itself uses selector-dependent morphology, class-conditioned improvements are not independent evidence that dynamic-range selection recovers clean timing. The full-RMS and tail-fraction columns are therefore co-primary with sigma68: a method that improves the core but worsens tails is not adoption-ready.

## Verdict

Dynamic-range selection is not adopted for timing. The extra population is measurable and class-conditionable, but the dynamic-only benchmark is won by the strong traditional signed-prior method, while the ML/NN methods do not provide a stable class-level improvement after run-held-out and leakage/oracle accounting.
