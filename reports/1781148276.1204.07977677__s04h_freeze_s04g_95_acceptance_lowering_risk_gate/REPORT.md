# S04h: freeze S04g 95%-acceptance lowering-risk gate

Ticket `1781148276.1204.07977677` asks whether the S04g per-pulse uncertainty winner preserves charge, current, and topology support when used as a 95% timing-acceptance ledger rather than as a timing correction.

## Abstract

The raw ROOT selected-pulse reproduction gate passes, and the frozen S04g run-heldout benchmark names `gated_waveform_tabular_cnn` as the point-score winner.  Its primary score is 0.0552 with run-block 95% CI [0.0446, 0.2951], compared with the traditional lowering-aware robust-width map at 0.1833.  The retained fixed-95%-acceptance summaries do not show a large accepted-tail-rate excursion across lowering strata: the range is 0.0197.  The adoption verdict is `conditional_summary_level_risk_ledger_with_large_lowering_watch`: use the S04g winner as a risk ledger, not as an unqualified event-removal rule or timing correction.

## Raw ROOT Reproduction

| quantity                           |   report_value |   reproduced |   delta |   tolerance | pass   |
|:-----------------------------------|---------------:|-------------:|--------:|------------:|:-------|
| total selected B-stave pulses      |         640737 |       640737 |       0 |           0 | True   |
| sample_ii_analysis selected_pulses |         125096 |       125096 |       0 |           0 | True   |
| sample_ii_analysis B2              |          88213 |        88213 |       0 |           0 | True   |
| sample_ii_analysis B4              |          21229 |        21229 |       0 |           0 | True   |
| sample_ii_analysis B6              |          11148 |        11148 |       0 |           0 | True   |
| sample_ii_analysis B8              |           4506 |         4506 |       0 |           0 | True   |

The reproduction gate reads B-stack `h101/HRDv` ROOT files, subtracts the baseline from samples 0-3, applies the established `A > 1000 ADC` selected-pulse rule, and verifies the Sample-II B2/B4/B6/B8 counts before model conclusions are used.

## Estimand

Let `r_es` be the S03 analytic-timewalk downstream closure residual for event `e` and stave `s`, and let method `m` predict location `mu_esm` and uncertainty `sigma_esm`.  The standardized pull is

`p_esm = (r_es - mu_esm) / max(sigma_esm, sigma_floor)`.

The S04g score minimized by the frozen benchmark is

`S_m = |sigma68(p_m)-1| + |C_68.27-0.6827| + |C_90-0.90| + |C_95-0.95| + 0.01 median(sigma_m)`.

For the 95%-acceptance ledger, the tail probability is

`P(|epsilon| > 5 ns) = erfc(5 / (sqrt(2) sigma))`,

and the accepted set is the lowest-risk 95% of pulses in the held-out fold.  This S04h audit asks whether that accepted-set rule sculpts available support proxies.

## Frozen Benchmark

| method                              | family                         |   primary_score |   primary_score_ci_low |   primary_score_ci_high |   pull_sigma68 |   coverage95 |   tail_probability_ece |   tail_capture_at_95_acceptance |
|:------------------------------------|:-------------------------------|----------------:|-----------------------:|------------------------:|---------------:|-------------:|-----------------------:|--------------------------------:|
| gated_waveform_tabular_cnn          | new_gated_waveform_tabular_cnn |       0.0551598 |              0.0446109 |                0.295115 |       1.00095  |     0.934206 |             0.00953242 |                        0.286996 |
| ridge_conformal                     | ridge                          |       0.0556123 |              0.0467751 |                0.195404 |       0.990248 |     0.931239 |             0.0115633  |                        0.35443  |
| mlp_heteroskedastic                 | mlp                            |       0.0762874 |              0.0635458 |                0.345539 |       0.997205 |     0.921815 |             0.00981872 |                        0.375    |
| gradient_boosted_trees_conformal    | gradient_boosted_trees         |       0.101548  |              0.0655747 |                0.32106  |       1.01832  |     0.917627 |             0.0100654  |                        0.505952 |
| cnn_1d_heteroskedastic              | cnn_1d                         |       0.13228   |              0.111709  |                0.335681 |       1.01006  |     0.896248 |             0.0115707  |                        0.390533 |
| traditional_stratified_robust_width | traditional                    |       0.183315  |              0.10626   |                0.405176 |       1.04072  |     0.891449 |             0.0122487  |                        0.205882 |

The method panel covers the requested traditional comparator, ridge, gradient-boosted trees, MLP, 1D-CNN, and a new gated waveform-tabular CNN architecture.  The new architecture is sensible here because waveform samples and tabular lowering/template-quality covariates carry complementary information; the gate lets the tabular branch modulate waveform residual scale.

The confidence intervals above are inherited from the frozen S04g held-out-run block bootstrap.  Each bootstrap draw resamples the seven held-out runs, recomputes pooled metrics over the selected draw, and reports the 2.5% and 97.5% quantiles.  Leakage checks for train/held-out run overlap, event-id overlap, and feature audit all pass in the frozen benchmark (`True`).

## Tail-Probability Ledger

| method                              |   tail_rate_abs_error_gt5ns |   tail_rate_abs_error_gt5ns_ci_low |   tail_rate_abs_error_gt5ns_ci_high |   mean_tail_probability_gt5ns |   tail_probability_ece |   tail_probability_ece_ci_low |   tail_probability_ece_ci_high |   accepted_tail_rate_at_95_acceptance |   accepted_tail_rate_at_95_acceptance_ci_low |   accepted_tail_rate_at_95_acceptance_ci_high |
|:------------------------------------|----------------------------:|-----------------------------------:|------------------------------------:|------------------------------:|-----------------------:|------------------------------:|-------------------------------:|--------------------------------------:|---------------------------------------------:|----------------------------------------------:|
| gated_waveform_tabular_cnn          |                   0.019459  |                          0.014532  |                           0.0250631 |                    0.00992657 |             0.00953242 |                    0.00574464 |                      0.0184098 |                            0.0146046  |                                   0.00974676 |                                    0.0210011  |
| ridge_conformal                     |                   0.0137871 |                          0.0122693 |                           0.0154983 |                    0.00222374 |             0.0115633  |                    0.0103487  |                      0.0133898 |                            0.00936897 |                                   0.00753762 |                                    0.011203   |
| mlp_heteroskedastic                 |                   0.0167539 |                          0.0135279 |                           0.0205241 |                    0.00693521 |             0.00981872 |                    0.00764807 |                      0.0117756 |                            0.0110223  |                                   0.00776173 |                                    0.0158965  |
| gradient_boosted_trees_conformal    |                   0.0146597 |                          0.0119967 |                           0.0173544 |                    0.00459424 |             0.0100654  |                    0.00823818 |                      0.0118378 |                            0.00762377 |                                   0.00641551 |                                    0.00909523 |
| cnn_1d_heteroskedastic              |                   0.0147469 |                          0.0125175 |                           0.0170627 |                    0.00317621 |             0.0115707  |                    0.010347   |                      0.0126272 |                            0.00946082 |                                   0.00730396 |                                    0.0114633  |
| traditional_stratified_robust_width |                   0.0148342 |                          0.0128205 |                           0.0169299 |                    0.00398931 |             0.0122487  |                    0.0102143  |                      0.0148626 |                            0.0122783  |                                   0.00997459 |                                    0.0146563  |

## Lowering-Axis Gate Audit

| lowering_axis   |    n |   tail_rate_abs_error_gt5ns |   mean_tail_probability_gt5ns |   tail_probability_ece |   tail_capture_at_95_acceptance |   accepted_tail_rate_at_95_acceptance | bias_flag   |
|:----------------|-----:|----------------------------:|------------------------------:|-----------------------:|--------------------------------:|--------------------------------------:|:------------|
| large           |  465 |                   0.0322581 |                    0.0528209  |             0.0284059  |                        0.2      |                            0.0272109  | watch       |
| medium          |  706 |                   0.0169972 |                    0.00873527 |             0.00984972 |                        0.583333 |                            0.00746269 | ok          |
| none            | 9240 |                   0.0181818 |                    0.00701573 |             0.0111661  |                        0.261905 |                            0.0141262  | ok          |
| small           | 1049 |                   0.0266921 |                    0.017354   |             0.0110197  |                        0.214286 |                            0.0220884  | ok          |

The large-lowering stratum has `n=465` in the frozen retained summary.  Its support is not absent, but it remains the important adoption caveat because it is exactly the physics/pathology axis the gate is meant to protect.

## Charge, Current, and Topology Proxies

The retained S04g artifacts do not include the per-pulse accepted/rejected ledger or per-pulse amplitude/current/topology fields.  A full local S04h rerun was attempted but interrupted during the first heavy gradient-boosted fold, so this audit uses the auditable support denominator retained in `downstream_counts_by_run.csv`: selected downstream pulse counts by run, stave, and lowering axis.  In this dataset, run is the current/rate proxy, stave is the topology proxy, and selected-pulse support is the charge-population proxy.

|   run | stave   | lowering_axis   |   selected_downstream_pulses |   run_fraction | support_flag   |
|------:|:--------|:----------------|-----------------------------:|---------------:|:---------------|
|    63 | B4      | medium          |                           25 |      0.0225225 | ok             |
|    61 | B6      | large           |                           28 |      0.0100036 | ok             |
|    62 | B8      | medium          |                           33 |      0.0136307 | ok             |
|    59 | B4      | large           |                           37 |      0.0161643 | ok             |
|    63 | B6      | small           |                           38 |      0.0342342 | ok             |
|    60 | B8      | large           |                           40 |      0.0165017 | ok             |
|    62 | B8      | large           |                           40 |      0.0165221 | ok             |
|    59 | B8      | medium          |                           41 |      0.0179118 | ok             |
|    59 | B6      | medium          |                           42 |      0.0183486 | ok             |
|    62 | B6      | medium          |                           43 |      0.0177613 | ok             |
|    61 | B8      | large           |                           45 |      0.0160772 | ok             |
|    63 | B4      | small           |                           45 |      0.0405405 | ok             |
|    60 | B8      | medium          |                           46 |      0.0189769 | ok             |
|    61 | B8      | medium          |                           47 |      0.0167917 | ok             |
|    62 | B4      | large           |                           47 |      0.0194135 | ok             |
|    60 | B6      | medium          |                           51 |      0.0210396 | ok             |
|    61 | B4      | large           |                           53 |      0.0189353 | ok             |
|    61 | B6      | medium          |                           53 |      0.0189353 | ok             |
|    60 | B4      | large           |                           55 |      0.0226898 | ok             |
|    62 | B8      | small           |                           55 |      0.0227179 | ok             |

## Systematics and Caveats

- The fixed-acceptance audit is based on retained S04g summaries, not a newly retained per-pulse accept/reject table.
- Charge is represented by selected-pulse support, not by per-pulse amplitude quantiles.
- Current is represented by held-out run identity; no external scaler current was joined in this ticket.
- Topology is represented by stave and lowering-axis support, not full event-level multi-stave patterns.
- The S04g winner and traditional intervals overlap; the result supports a calibrated risk ledger rather than a decisive replacement claim.

## Verdict

`gated_waveform_tabular_cnn` is the named winner in `result.json`.  S04h freezes that winner as the S04g 95%-acceptance lowering-risk ledger and finds no retained-summary evidence for gross lowering-axis support sculpting, but the absence of a per-pulse accepted ledger means the adoption should remain conditional.

## Reproducibility

```bash
/home/billy/anaconda3/bin/python scripts/s04h_1781148276_1204_07977677_freeze_gate_audit.py
```
