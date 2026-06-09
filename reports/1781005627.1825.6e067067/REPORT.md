# Study report: S03b - amplitude-binned monotone analytic template timewalk

- **Ticket:** 1781005627.1825.6e067067
- **Author:** testbeam-laptop-3
- **Date:** 2026-06-09
- **Input:** raw B-stack ROOT files under `data/root/root`
- **Split:** train runs 58-63; held-out run 65
- **Config:** `reports/1781005627.1825.6e067067/s03b_config.yaml`

## 0. Question

Does an amplitude-binned, per-stave monotone analytic residual template improve on the S03a amplitude-only correction without adding leakage risk?

## 1. Raw-ROOT reproduction gate

The S00 selected-pulse counts were rerun from raw ROOT before any correction work.

| quantity                           |   report_value |   reproduced |   delta |   tolerance | pass   |
|:-----------------------------------|---------------:|-------------:|--------:|------------:|:-------|
| total selected B-stave pulses      |         640737 |       640737 |       0 |           0 | True   |
| sample_ii_analysis selected_pulses |         125096 |       125096 |       0 |           0 | True   |
| sample_ii_analysis B2              |          88213 |        88213 |       0 |           0 | True   |
| sample_ii_analysis B4              |          21229 |        21229 |       0 |           0 | True   |
| sample_ii_analysis B6              |          11148 |        11148 |       0 |           0 | True   |
| sample_ii_analysis B8              |           4506 |         4506 |       0 |           0 | True   |

The S03a/S02 held-out timing numbers were then rebuilt from the same raw pass.

| method                  |   value |   ci_low |   ci_high |   n_pair_residuals |
|:------------------------|--------:|---------:|----------:|-------------------:|
| s02_template_phase_base | 2.88915 |  2.63915 |   3.20541 |                198 |
| s02_cfd20_reference     | 2.99339 |  2.61485 |   3.35138 |                198 |
| s02_ml_ridge_on_cfd20   | 1.84611 |  1.52116 |   2.01422 |                198 |
| s03a_amp_only_analytic  | 1.49464 |  1.34177 |   1.64319 |                198 |

## 2. Traditional method

The traditional method bins log-amplitude by stave on train runs, takes the median event-residual target in each bin, and projects those bin medians through a per-stave isotonic constraint. The bin count and monotone direction policy are selected only by grouped CV on train runs.

|   n_bins | direction   |   sigma68_ns |
|---------:|:------------|-------------:|
|        8 | decreasing  |      1.58499 |
|        8 | auto        |      1.58499 |
|        4 | increasing  |      1.62602 |
|        5 | increasing  |      1.63427 |
|        6 | decreasing  |      1.64032 |
|        6 | auto        |      1.64032 |
|        6 | increasing  |      1.64814 |
|        8 | increasing  |      1.65034 |

Selected setting: `8` bins with `decreasing` direction policy. The model uses only same-pulse amplitude and stave identity.

| stave   | direction   |   n_bins |   correction_span_ns |
|:--------|:------------|---------:|---------------------:|
| B4      | decreasing  |        8 |          0           |
| B6      | decreasing  |        8 |          6.66134e-15 |
| B8      | decreasing  |        8 |          1.25        |

## 3. ML method

The ML method is a run-held-out histogram-gradient-boosted residual regressor using normalized 18-sample waveform shape, amplitude transforms, rise-time summaries, peak sample, area/amp, and stave one-hot features. It receives no run number, event id, event order, other-stave timing, or held-out label.

Selected ML model by grouped CV: `hgb_regularized`.

## 4. Held-out head-to-head

| method                   |   value |   ci_low |   ci_high |   full_rms_ns |   tail_frac_abs_gt5ns |   n_pair_residuals |
|:-------------------------|--------:|---------:|----------:|--------------:|----------------------:|-------------------:|
| s03a_template_phase_base | 2.88915 |  2.63915 |   3.13935 |       2.57669 |            0.0505051  |                198 |
| monotone_binned_timewalk | 1.56958 |  1.33548 |   1.81958 |       1.83025 |            0.00505051 |                198 |
| ml_hgb_waveform_residual | 1.47171 |  1.29394 |   1.68245 |       1.62149 |            0.00505051 |                198 |

## 5. Leakage checks

| check                           |   heldout_sigma68_ns |   n_pair_residuals |
|:--------------------------------|---------------------:|-------------------:|
| template_phase                  |              2.88915 |                198 |
| monotone_binned_shuffled_target |              2.89184 |                198 |
| ml_hgb_shuffled_target          |              2.87696 |                198 |
| train_heldout_event_id_overlap  |              0       |                  0 |

The split is by run. Training and held-out event-id overlap is zero. Shuffled-target controls for both the monotone template and ML regressor do not reproduce the nominal improvement.

## 6. Verdict

Template-phase starts at `2.889 ns`; the S03a amp-only reproduction is `1.495 ns`. The S03b monotone-binned analytic correction gives `1.570 ns` (gain `1.320 ns`), while ML gives `1.472 ns` (gain `1.417 ns`).

Conclusion: `monotone_binned_does_not_improve_s03a_amp_only__ml_narrower_than_traditional`.

## 7. Reproducibility

Generated by:

```bash
/home/billy/anaconda3/bin/python reports/1781005627.1825.6e067067/s03b_timewalk.py --config reports/1781005627.1825.6e067067/s03b_config.yaml
```

Artifacts: `reproduction_match_table.csv`, `s03a_reproduction_benchmark.csv`, `monotone_cv_scan.csv`, `monotone_bin_table.csv`, `ml_hgb_cv.csv`, `head_to_head_benchmark.csv`, `calibration_table.csv`, `leakage_checks.csv`, figures, `input_sha256.csv`, `result.json`, and `manifest.json`.
