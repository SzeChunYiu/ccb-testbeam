# S16f: event-display audit of large-lowering selected pulses

- **Ticket:** 1781017317.1162.6f117818
- **Author:** testbeam-laptop-2
- **Date:** 2026-06-09
- **Input checksum(s):** `input_sha256.csv`
- **Git commit:** `49e398f9e7bd5946487545e5aecfd077d7f25e6b`
- **Config:** `s16f_1781017317_1162_6f117818_event_display_audit.json`

## Question

For held-out `s16_large_lowering` selected pulses, is the adaptive-pedestal lowering source most consistent with pre-trigger contamination, post-trigger undershoot, pile-up, or electronics baseline drift?

## Raw-ROOT Reproduction First

The script starts from `h101/HRDv` raw ROOT, using B2/B4/B6/B8 even channels, median samples 0-3, and `A > 1000 ADC`. The S00 selected-pulse gate is reproduced before any gallery or classifier work.

| Quantity | Report value | Reproduced | Delta | Pass? |
|---|---:|---:|---:|---|
| total selected B-stave pulses | 640737 | 640737 | 0 | yes |
| sample_i_analysis selected_pulses | 252266 | 252266 | 0 | yes |
| sample_i_analysis B2 | 241422 | 241422 | 0 | yes |
| sample_i_analysis B4 | 6451 | 6451 | 0 | yes |
| sample_i_analysis B6 | 3094 | 3094 | 0 | yes |
| sample_i_analysis B8 | 1299 | 1299 | 0 | yes |

The ticket-specific reproduced number is the held-out count of selected pulses with adaptive lowering >= `200 ADC`: **5250** pulses in runs [54, 55, 56, 57]. Train runs [44, 45, 46, 47, 48, 49, 50, 51, 52, 53] contain **10752** such pulses.

## Blinded Gallery

`fig_blinded_waveform_gallery.png` and `blinded_waveform_gallery.csv` contain 48 held-out large-lowering pulses identified only by `blind_id`. The keyed classifications are separated into `waveform_gallery_key.csv`.

## Methods

Traditional method: a fixed scorecard over raw waveform morphology, using pre-trigger pedestal displacement, post-peak negative area, secondary maxima/tail width, and smooth baseline slope. It assigns one of four source labels.

ML method: a random-forest classifier trained only on train-run large-lowering pulses and the traditional labels, then evaluated on complete held-out runs. Features exclude run, event number, stave identity, labels, and classifier outputs. Because no human labels exist, ML agreement is a transfer/stability test of the morphology taxonomy, not independent truth.

Bootstrap CIs resample held-out runs, then pulses within sampled runs.

## Held-out Classification

| Method | Category | n | fraction [95% CI] |
|---|---|---:|---:|
| traditional_rules | pre_trigger_contamination | 2850 | 0.543 [0.459, 0.624] |
| traditional_rules | post_trigger_undershoot | 396 | 0.075 [0.062, 0.091] |
| traditional_rules | pile_up | 1729 | 0.329 [0.265, 0.402] |
| traditional_rules | electronics_baseline_drift | 275 | 0.052 [0.040, 0.068] |
| ml_random_forest | pre_trigger_contamination | 2516 | 0.479 [0.375, 0.581] |
| ml_random_forest | post_trigger_undershoot | 607 | 0.116 [0.090, 0.143] |
| ml_random_forest | pile_up | 1780 | 0.339 [0.266, 0.425] |
| ml_random_forest | electronics_baseline_drift | 347 | 0.066 [0.050, 0.085] |

| Metric | Value [95% CI] |
|---|---:|
| ml_vs_traditional_accuracy | 0.909 [0.884, 0.933] |
| ml_vs_traditional_balanced_accuracy | 0.941 [0.925, 0.954] |
| ml_vs_traditional_macro_f1 | 0.871 [0.852, 0.890] |
| shuffled_label_accuracy | 0.250 [0.235, 0.270] |

Top RF features: `late_mean_seedcorr_adc, peak_sample, undershoot_samples, raw_baseline_slope_adc_per_sample, seed_minus_late_median_raw_adc, w_norm_06, w_norm_17, w_norm_15`. Mean run-CV macro-F1 on train runs: `0.875`.

## Leakage Checks

| Check | Value | Pass? |
|---|---:|---|
| split_by_run_train_heldout_disjoint |  | yes |
| ml_features_exclude_ids_run_stave_and_labels |  | yes |
| rounded_waveform_hash_train_heldout_overlap_zero | 0 | yes |
| shuffled_label_control_worse_than_actual | 0.6215022680391955 | yes |
| row_cv_not_substantially_better_than_run_cv | 0.0012970022627084576 | yes |
| run_cv_macro_f1_not_perfect | 0.8746661285197306 | yes |
| heldout_ml_confidence_finite | 5250 | yes |

## Verdict

The blinded held-out gallery is dominated by pre trigger contamination (54.3%), with pile up next (32.9%). The RF transfer model closely follows the traditional taxonomy on held-out runs, so the classification is stable under run splitting, but it remains an algorithmic morphology audit rather than human truth labels.

## Reproducibility

```bash
/home/billy/anaconda3/bin/python scripts/s16f_1781017317_1162_6f117818_event_display_audit.py --config configs/s16f_1781017317_1162_6f117818_event_display_audit.json --out-dir reports/1781017317.1162.6f117818
```

Primary artifacts: `REPORT.md`, `result.json`, `manifest.json`, `input_sha256.csv`, `reproduction_match_table.csv`, `large_lowering_counts_by_run.csv`, `heldout_classifications.csv`, `category_fraction_summary.csv`, `method_agreement_summary.csv`, `ml_run_cv_summary.csv`, `ml_feature_importance.csv`, `leakage_checks.csv`, `blinded_waveform_gallery.csv`, `waveform_gallery_key.csv`, and PNG diagnostics.
