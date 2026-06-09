# S00d: dynamic-selector pulse taxonomy audit

- **Ticket:** `1781014251.574.7a497937`
- **Worker:** `testbeam-laptop-1`
- **Date:** 2026-06-09
- **Command:** `/home/billy/anaconda3/bin/python reports/1781014251.574.7a497937/s00d_dynamic_selector_taxonomy.py`
- **Config:** `configs/s00d_1781014251_574_7a497937.json`

## Reproduction first

Raw B-stack ROOT was scanned before any taxonomy or ML step. The selector anchors reproduce exactly:

| quantity                   |   expected |   reproduced |   delta |   tolerance | pass   |
|:---------------------------|-----------:|-------------:|--------:|------------:|:-------|
| median_first_four_selected |     640737 |       640737 |       0 |           0 | True   |
| dynamic_range_selected     |     706373 |       706373 |       0 |           0 | True   |
| dynamic_only               |      65636 |        65636 |       0 |           0 | True   |
| median_only                |          0 |            0 |       0 |           0 | True   |

## Traditional taxonomy

The traditional method applies fixed cuts to peak sample, early/late fraction, train-run S00 control `q_template` RMSE, baseline excursion, saturation proxy count, and downstream CFD20 timing span. Held-out runs are `42, 57, 64, 65` and CIs are run-block bootstraps.

Top dynamic-only classes:

| taxonomy_class               | population   |    fraction |      ci_low |     ci_high |    n |
|:-----------------------------|:-------------|------------:|------------:|------------:|-----:|
| baseline_excursion           | dynamic_only | 0.924167    | 0.918555    | 0.937742    | 8466 |
| poor_template_match          | dynamic_only | 0.0627215   | 0.0352082   | 0.0731628   | 8466 |
| large_downstream_timing_span | dynamic_only | 0.00685093  | 0.00516794  | 0.0107342   | 8466 |
| low_median_amp_dynamic_only  | dynamic_only | 0.00401606  | 0.00162946  | 0.0103049   | 8466 |
| late_tail_or_delayed_peak    | dynamic_only | 0.00200803  | 0.000651784 | 0.00558179  | 8466 |
| clean_template_like          | dynamic_only | 0.000236239 | 0           | 0.000617761 | 8466 |
| saturation_proxy             | dynamic_only | 0           | 0           | 0           | 8466 |

Largest dynamic-only versus S00-control enrichment odds ratios:

| taxonomy_class               |   odds_ratio_dynamic_vs_control |        ci_low |       ci_high |
|:-----------------------------|--------------------------------:|--------------:|--------------:|
| low_median_amp_dynamic_only  |                   487.795       | 194.691       | 1164.22       |
| baseline_excursion           |                    56.1601      |  48.0862      |   76.8871     |
| poor_template_match          |                     2.24033     |   1.00177     |    3.55357    |
| large_downstream_timing_span |                     0.144163    |   0.117217    |    0.211001   |
| late_tail_or_delayed_peak    |                     0.00266626  |   0.000870541 |    0.00583236 |
| clean_template_like          |                     0.00138495  |   0.000282353 |    0.00245578 |
| saturation_proxy             |                     0.000382313 |   0.000124901 |    0.00230263 |

Charge-proxy and shape bias on held-out runs:

| metric                 |   dynamic_only_median |   s00_control_median |   dynamic_minus_control_median |       ci_low |     ci_high |
|:-----------------------|----------------------:|---------------------:|-------------------------------:|-------------:|------------:|
| median_amp_adc         |             361.5     |          3621.5      |                    -3260       |  -4041       |  -2574      |
| dynamic_amp_adc        |            3264       |          3901        |                     -637       |  -1360       |   -269      |
| area_adc_samples       |          -28015.5     |         29490        |                   -57505.5     | -67404       | -42742.5    |
| q_template_rmse        |               4.96432 |             0.187675 |                        4.77664 |      3.10379 |      5.6299 |
| baseline_excursion_adc |             843.5     |            23        |                      820.5     |    752       |   1011      |

Timing deltas use downstream B4/B6/B8 all-hit CFD20 pair residuals:

| selector      | metric      |   value |   ci_low |   ci_high |   n_pairs |
|:--------------|:------------|--------:|---------:|----------:|----------:|
| median_first4 | sigma68_ns  | 3.18845 |  3.11408 |   3.30807 |      1224 |
| median_first4 | full_rms_ns | 4.79825 |  2.78415 |   5.84433 |      1224 |
| dynamic_range | sigma68_ns  | 3.07203 |  2.86892 |   3.185   |      1599 |
| dynamic_range | full_rms_ns | 5.34023 |  2.96957 |   6.71719 |      1599 |

## ML morphology summary

The ML method uses a train-run-only P01-style four-dimensional denoising autoencoder embedding plus non-selector morphology features. It excludes median amplitude, dynamic amplitude, dynamic-minus-median, baseline excursion, run id, and event id from the primary classifier. P01b release latents are used only as S00-control provenance telemetry because that release artifact has no dynamic-only rows.

| model                             |      auc |   auc_ci_low |   auc_ci_high |   average_precision |   average_precision_ci_low |   average_precision_ci_high |   accuracy |   n_test |   positive_test |
|:----------------------------------|---------:|-------------:|--------------:|--------------------:|---------------------------:|----------------------------:|-----------:|---------:|----------------:|
| p01_style_ae_shape_logistic       | 0.994328 |     0.991687 |       0.99606 |            0.990825 |                   0.985421 |                    0.994424 |   0.969324 |    16332 |            5834 |
| leaky_selector_amplitude_logistic | 0.99996  |   nan        |     nan       |            0.999929 |                 nan        |                  nan        |   0.995775 |    16332 |            5834 |
| stave_only_control                | 0.609211 |   nan        |     nan       |            0.423156 |                 nan        |                  nan        |   0.585048 |    16332 |            5834 |
| within_run_label_shuffle_control  | 0.950903 |   nan        |     nan       |            0.934084 |                 nan        |                  nan        |   0.874602 |    16332 |            5834 |

Leakage checks:

| check                                | value                | pass   | note                                                                                           |
|:-------------------------------------|:---------------------|:-------|:-----------------------------------------------------------------------------------------------|
| train_heldout_run_overlap            | 0                    | True   | split key is run                                                                               |
| primary_excludes_selector_amplitudes | 1                    | True   | median_amp, dynamic_amp, dynamic-minus-median, baseline excursion absent from primary features |
| leaky_sentinel_auc_minus_primary_auc | 0.005632821126677845 | True   | large positive gap confirms direct selector variables are leakage                              |
| within_run_shuffle_auc               | 0.9509034582423359   | False  | shuffled-label morphology control                                                              |
| p01b_release_controls_only_status    | matched              | True   | P01b release rows match S00 controls and have no dynamic-only rows                             |

The primary classifier AUC is `0.994` [0.992, 0.996], while the leaky selector-amplitude sentinel reaches `1.000`. The within-run shuffled-label control remains high and fails the leakage/confounding check, so the ML result is reported only as morphology telemetry and a failed leakage stress test, not as evidence for a recoverable physics class or an adoption-ready selector.

## Verdict

Dynamic range adds `65,636` records and is a strict superset of S00 (`median_only = 0`). On held-out runs the largest dynamic-only class is `baseline_excursion` at `0.924`. The excess is mostly selector/baseline semantics and low-median-amplitude morphology, not a clean recoverable-physics population. Timing widths are not identical, but the decisive effect is population composition and charge-proxy bias.

## Reproducibility

`manifest.json` records raw input hashes, output hashes, environment, command, and the P01b release artifact status. Main tables are `reproduction_match_table.csv`, `taxonomy_class_fractions.csv`, `taxonomy_enrichment_odds.csv`, `charge_proxy_bias.csv`, `timing_summary.csv`, `ml_benchmark.csv`, and `leakage_checks.csv`.
