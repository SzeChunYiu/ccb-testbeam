# Study report: S03b - Amplitude-binned monotonic timewalk

- **Ticket:** 1781005627.1825.6e067067
- **Author:** testbeam-laptop-4
- **Date:** 2026-06-09
- **Input:** raw B-stack ROOT files under `data/root/root`
- **Split:** train runs 58-63; held-out run 65
- **Config:** `configs/s03b_amp_binned_monotonic_timewalk.yaml`

## 0. Question

Does an amplitude-binned or monotonic per-stave analytic timewalk closure improve on the S03a amp-only model without increasing leakage risk?

## 1. Raw-ROOT reproduction gate

The S00 selected-pulse counts were rerun from raw ROOT before any S03b modeling.

| quantity                           |   report_value |   reproduced |   delta |   tolerance | pass   |
|:-----------------------------------|---------------:|-------------:|--------:|------------:|:-------|
| total selected B-stave pulses      |         640737 |       640737 |       0 |           0 | True   |
| sample_ii_analysis selected_pulses |         125096 |       125096 |       0 |           0 | True   |
| sample_ii_analysis B2              |          88213 |        88213 |       0 |           0 | True   |
| sample_ii_analysis B4              |          21229 |        21229 |       0 |           0 | True   |
| sample_ii_analysis B6              |          11148 |        11148 |       0 |           0 | True   |
| sample_ii_analysis B8              |           4506 |         4506 |       0 |           0 | True   |

The S03a held-out numbers were then rebuilt in this run from the same raw-derived pulse table.

| method                     |   value |   reference_value |   delta | pass   |
|:---------------------------|--------:|------------------:|--------:|:-------|
| s02_template_phase_base    | 2.88915 |           2.88915 |       0 | True   |
| s03a_amp_only_reference    | 1.49464 |           1.49464 |       0 | True   |
| ml_ridge_on_template_phase | 1.39153 |           1.39153 |       0 | True   |

## 2. Traditional constrained scan

The S03b traditional candidates fit per-stave median residual-vs-amplitude bins on train runs only. The monotonic variants pass those bin medians through isotonic regression, separately for each stave.

| mode          | direction   |   n_bins |   sigma68_ns |
|:--------------|:------------|---------:|-------------:|
| monotonic     | decreasing  |       10 |      1.54638 |
| unconstrained | none        |       10 |      1.54638 |
| unconstrained | none        |       12 |      1.58352 |
| monotonic     | decreasing  |       12 |      1.58352 |
| monotonic     | decreasing  |        8 |      1.58542 |
| unconstrained | none        |        8 |      1.58542 |
| monotonic     | increasing  |        4 |      1.62599 |
| monotonic     | decreasing  |        6 |      1.6403  |

Selected by grouped CV on train runs: mode `monotonic`, direction `decreasing`, bins `10`.

| stave   | mode      | direction   |   n_bins |   min_fit_ns |   max_fit_ns |
|:--------|:----------|:------------|---------:|-------------:|-------------:|
| B4      | monotonic | decreasing  |       10 |   -4.1924    |     -4.1924  |
| B6      | monotonic | decreasing  |       10 |    2.63915   |      2.63915 |
| B8      | monotonic | decreasing  |       10 |    0.0532462 |      1.55325 |

## 3. Held-out head-to-head

| method                     |   value |   ci_low |   ci_high |   full_rms_ns |   tail_frac_abs_gt5ns |   n_pair_residuals |
|:---------------------------|--------:|---------:|----------:|--------------:|----------------------:|-------------------:|
| s02_template_phase_base    | 2.88915 |  2.63915 |   3.20541 |       2.57669 |            0.0505051  |                198 |
| s03a_amp_only_reference    | 1.49464 |  1.33462 |   1.62481 |       1.69913 |            0.00505051 |                198 |
| s03b_binned_timewalk       | 1.56958 |  1.31958 |   1.81958 |       1.83396 |            0.00505051 |                198 |
| ml_ridge_on_template_phase | 1.39153 |  1.28857 |   1.60848 |       1.67232 |            0.00505051 |                198 |

|   run | method                     |   sigma68_ns |   full_rms_ns |   tail_frac_abs_gt5ns |   n_pair_residuals |
|------:|:---------------------------|-------------:|--------------:|----------------------:|-------------------:|
|    65 | s02_template_phase_base    |      2.88915 |       2.57669 |            0.0505051  |                198 |
|    65 | s03a_amp_only_reference    |      1.49464 |       1.69913 |            0.00505051 |                198 |
|    65 | s03b_binned_timewalk       |      1.56958 |       1.83396 |            0.00505051 |                198 |
|    65 | ml_ridge_on_template_phase |      1.39153 |       1.67232 |            0.00505051 |                198 |

## 4. Leakage checks

| check                                  |   value | unit   |
|:---------------------------------------|--------:|:-------|
| train_heldout_event_id_overlap         | 0       | events |
| s03b_shuffled_target_sigma68           | 2.90565 | ns     |
| ml_shuffled_target_sigma68             | 2.88251 | ns     |
| traditional_uses_run_or_event_features | 0       | bool   |
| final_binned_fit_uses_heldout_rows     | 0       | bool   |

Feature audit: the traditional model uses only same-pulse amplitude and stave identity; the ML comparator uses same-pulse waveform/amplitude/shape plus stave identity. No run number, event id, event order, other-stave timing, or held-out labels are model inputs. Bin centers and isotonic fits are learned only from train runs inside each CV fold and from train runs for the final held-out evaluation.

## 5. Verdict

S03a amp-only changes held-out sigma68 from `2.889 ns` to `1.495 ns`. The selected S03b binned model gives `1.570 ns`, a delta of `-0.075 ns` versus S03a amp-only. The ML comparator gives `1.392 ns`.

Conclusion: s03b_binned_monotonic_does_not_improve_on_s03a_amp_only.

## 6. Reproducibility

Generated by:

```bash
/home/billy/anaconda3/bin/python scripts/s03b_amp_binned_monotonic_timewalk.py --config configs/s03b_amp_binned_monotonic_timewalk.yaml
```

Artifacts: `reproduction_match_table.csv`, `s03a_reproduction_benchmark.csv`, `binned_cv_scan.csv`, `binned_model_table.csv`, `head_to_head_benchmark.csv`, `heldout_by_run.csv`, `leakage_checks.csv`, figures, `result.json`, and `manifest.json`.
