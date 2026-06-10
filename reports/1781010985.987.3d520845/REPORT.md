# Study report: S03e - Two-ended-safe single-stave timewalk closure

- **Ticket:** 1781010985.987.3d520845
- **Author:** testbeam-laptop-3
- **Date:** 2026-06-09
- **Input:** raw B-stack ROOT under `data/root/root`
- **Split:** leave one Sample-II analysis run out; held-out runs 58, 59, 60, 61, 62, 63, 65
- **Config:** `configs/s03e_two_ended_safe_timewalk.yaml`

## 0. Question

Can a deployable timewalk correction be learned using only single-stave waveform features, with no event residual target and no other-stave timing feature, while preserving two-ended-readout safety?

## 1. Raw-ROOT reproduction gate

Before modeling, the S00 selected-pulse count gate was rerun directly from raw ROOT.

| quantity                           |   report_value |   reproduced |   delta |   tolerance | pass   |
|:-----------------------------------|---------------:|-------------:|--------:|------------:|:-------|
| total selected B-stave pulses      |         640737 |       640737 |       0 |           0 | True   |
| sample_ii_analysis selected_pulses |         125096 |       125096 |       0 |           0 | True   |
| sample_ii_analysis B2              |          88213 |        88213 |       0 |           0 | True   |
| sample_ii_analysis B4              |          21229 |        21229 |       0 |           0 | True   |
| sample_ii_analysis B6              |          11148 |        11148 |       0 |           0 | True   |
| sample_ii_analysis B8              |           4506 |         4506 |       0 |           0 | True   |

## 2. Methods

All fitted targets are single-stave waveform proxy targets: `t_cfd20_ns - t_template_phase_ns`, where the template phase is computed from train-run median templates only. Inter-stave residuals are used only after prediction for held-out scoring.

The traditional comparator is train-template phase matching, plus an amplitude-only per-stave isotonic proxy correction. The ML comparator is a histogram gradient boosting regressor over normalized waveform samples, amplitude, CFD pickoffs, rise/shape summaries, and stave one-hot columns. Features exclude run number, event id, event order, and other-stave timing.

## 3. Held-out results

|   heldout_run | method                         |   sigma68_ns |   full_rms_ns |   tail_frac_abs_gt5ns |   n_pair_residuals |
|--------------:|:-------------------------------|-------------:|--------------:|----------------------:|-------------------:|
|            58 | cfd20_base                     |      3.11542 |       4.8861  |             0.0730594 |                219 |
|            58 | ml_shuffled_proxy_control      |      3.0431  |       5.01782 |             0.0684932 |                219 |
|            58 | ml_single_stave_proxy          |      2.77424 |       2.92423 |             0.0593607 |                219 |
|            58 | traditional_amp_isotonic_proxy |      4.35411 |       5.26208 |             0.251142  |                219 |
|            58 | traditional_template_phase     |      2.6428  |       3.54397 |             0.0776256 |                219 |
|            59 | cfd20_base                     |      3.19039 |       5.79544 |             0.0707733 |               2289 |
|            59 | ml_shuffled_proxy_control      |      4.02056 |       6.8291  |             0.228484  |               2289 |
|            59 | ml_single_stave_proxy          |      2.97608 |       3.36208 |             0.0764526 |               2289 |
|            59 | traditional_amp_isotonic_proxy |      4.5687  |       6.75169 |             0.262123  |               2289 |
|            59 | traditional_template_phase     |      2.99232 |       3.34278 |             0.0677152 |               2289 |
|            60 | cfd20_base                     |      3.13862 |       7.26201 |             0.0594059 |               2424 |
|            60 | ml_shuffled_proxy_control      |      4.13234 |       7.93366 |             0.218647  |               2424 |
|            60 | ml_single_stave_proxy          |      2.79096 |       3.11626 |             0.0804455 |               2424 |
|            60 | traditional_amp_isotonic_proxy |      4.36827 |       8.13827 |             0.254125  |               2424 |
|            60 | traditional_template_phase     |      2.66393 |       3.279   |             0.0944719 |               2424 |
|            61 | cfd20_base                     |      2.91408 |       6.59866 |             0.0485888 |               2799 |
|            61 | ml_shuffled_proxy_control      |      4.16363 |       7.56115 |             0.234012  |               2799 |
|            61 | ml_single_stave_proxy          |      2.58628 |       3.24158 |             0.0525188 |               2799 |
|            61 | traditional_amp_isotonic_proxy |      4.06556 |       7.40459 |             0.21472   |               2799 |
|            61 | traditional_template_phase     |      2.70351 |       3.20716 |             0.0428725 |               2799 |
|            62 | cfd20_base                     |      3.23169 |       4.95545 |             0.063197  |               2421 |
|            62 | ml_shuffled_proxy_control      |      4.58251 |       6.05615 |             0.275506  |               2421 |
|            62 | ml_single_stave_proxy          |      2.93262 |       2.93354 |             0.0714581 |               2421 |
|            62 | traditional_amp_isotonic_proxy |      4.57402 |       5.90501 |             0.266832  |               2421 |
|            62 | traditional_template_phase     |      2.90117 |       3.35891 |             0.0929368 |               2421 |
|            63 | cfd20_base                     |      3.40351 |       6.58303 |             0.0720721 |               1110 |
|            63 | ml_shuffled_proxy_control      |      3.65278 |       6.69221 |             0.132432  |               1110 |
|            63 | ml_single_stave_proxy          |      2.99924 |       3.37276 |             0.081982  |               1110 |
|            63 | traditional_amp_isotonic_proxy |      4.78799 |       7.58706 |             0.277477  |               1110 |
|            63 | traditional_template_phase     |      2.87872 |       3.38179 |             0.0963964 |               1110 |
|            65 | cfd20_base                     |      2.99339 |       2.74268 |             0.0656566 |                198 |
|            65 | ml_shuffled_proxy_control      |      2.9923  |       2.73894 |             0.0757576 |                198 |
|            65 | ml_single_stave_proxy          |      2.74642 |       2.52967 |             0.0353535 |                198 |
|            65 | traditional_amp_isotonic_proxy |      4.23919 |       4.44474 |             0.247475  |                198 |
|            65 | traditional_template_phase     |      2.88915 |       2.57669 |             0.0505051 |                198 |

Pooled CIs resample held-out runs, not rows.

| method                         |   value |   ci_low |   ci_high |   full_rms_ns |   tail_frac_abs_gt5ns |   n_pair_residuals |
|:-------------------------------|--------:|---------:|----------:|--------------:|----------------------:|-------------------:|
| cfd20_base                     | 3.15027 |  3.02282 |   3.27504 |       6.20431 |             0.0579407 |              11460 |
| ml_shuffled_proxy_control      | 4.11888 |  3.77705 |   4.34606 |       7.03127 |             0.222775  |              11460 |
| ml_single_stave_proxy          | 2.82906 |  2.68419 |   2.96326 |       3.18136 |             0.0676265 |              11460 |
| traditional_amp_isotonic_proxy | 4.44711 |  4.2224  |   4.6027  |       7.1006  |             0.252007  |              11460 |
| traditional_template_phase     | 2.74141 |  2.68081 |   2.98895 |       3.30837 |             0.0813264 |              11460 |

## 4. Proxy-target and leakage checks

|   heldout_run | model    | split   |   rmse_ns |   mae_ns |   n_pulses |
|--------------:|:---------|:--------|----------:|---------:|-----------:|
|            58 | ml_proxy | train   |  0.542845 | 0.296594 |      11241 |
|            58 | ml_proxy | heldout |  1.07936  | 0.562341 |        219 |
|            59 | ml_proxy | train   |  0.498427 | 0.290642 |       9171 |
|            59 | ml_proxy | heldout |  0.889341 | 0.339223 |       2289 |
|            60 | ml_proxy | train   |  0.516847 | 0.299893 |       9036 |
|            60 | ml_proxy | heldout |  0.663547 | 0.367667 |       2424 |
|            61 | ml_proxy | train   |  0.508549 | 0.294109 |       8661 |
|            61 | ml_proxy | heldout |  1.02741  | 0.414445 |       2799 |
|            62 | ml_proxy | train   |  0.525501 | 0.294445 |       9039 |
|            62 | ml_proxy | heldout |  1.26175  | 0.359077 |       2421 |
|            63 | ml_proxy | train   |  0.552268 | 0.304122 |      10350 |
|            63 | ml_proxy | heldout |  0.859933 | 0.390811 |       1110 |
|            65 | ml_proxy | train   |  0.574782 | 0.305289 |      11262 |
|            65 | ml_proxy | heldout |  0.588229 | 0.405083 |        198 |

| check                                          |   min |   median |   max |
|:-----------------------------------------------|------:|---------:|------:|
| features_include_run_event_or_other_stave_time |     0 |        0 |     0 |
| fit_targets_include_event_residuals            |     0 |        0 |     0 |
| n_single_stave_features                        |    36 |       36 |    36 |
| train_heldout_event_id_overlap                 |     0 |        0 |     0 |
| train_heldout_run_overlap                      |     0 |        0 |     0 |

The shuffled-target ML control is included in the held-out benchmark. It does not reproduce the single-stave ML closure, and all run/event overlap checks are zero.

## 5. Verdict

CFD20 baseline pooled sigma68 is `3.150 ns` with CI `[3.023, 3.275] ns`.
The strong traditional train-template phase method gives `2.741 ns` with CI `[2.681, 2.989] ns`.
The ML single-stave proxy gives `2.829 ns` with CI `[2.684, 2.963] ns`.

Conclusion: `single_stave_proxy_closure_supported`.

## 6. Reproducibility

Generated by:

```bash
/home/billy/anaconda3/bin/python scripts/s03e_two_ended_safe_timewalk.py --config configs/s03e_two_ended_safe_timewalk.yaml
```

Artifacts: `reproduction_match_table.csv`, `per_run_benchmark.csv`, `pooled_run_bootstrap.csv`, `pairwise_residuals.csv`, `proxy_fit_metrics.csv`, `traditional_proxy_models.csv`, `leakage_checks.csv`, figures, `result.json`, and `manifest.json`.
