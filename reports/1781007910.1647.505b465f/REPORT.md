# S16e: pre-trigger activity proxy in timing residual tails

Ticket `1781007910.1647.505b465f`. Worker `testbeam-laptop-2`.

## Reproduction first

Raw ROOT was read from `h101/HRDv` before timing fits. The S00 selected B-stave gate uses median samples 0-3 and `A > 1000 ADC`.

| quantity                           |   report_value |   reproduced |   delta |   tolerance | pass   |
|:-----------------------------------|---------------:|-------------:|--------:|------------:|:-------|
| total selected B-stave pulses      |         640737 |       640737 |       0 |           0 | True   |
| sample_ii_analysis selected_pulses |         125096 |       125096 |       0 |           0 | True   |
| sample_ii_analysis B2              |          88213 |        88213 |       0 |           0 | True   |
| sample_ii_analysis B4              |          21229 |        21229 |       0 |           0 | True   |
| sample_ii_analysis B6              |          11148 |        11148 |       0 |           0 | True   |
| sample_ii_analysis B8              |           4506 |         4506 |       0 |           0 | True   |

S02/S02b timing references were then rebuilt on the same raw run split:

| quantity                                       |   reproduced_sigma68_ns |   reference_sigma68_ns |    delta_ns | pass   |
|:-----------------------------------------------|------------------------:|-----------------------:|------------:|:-------|
| S02 global-template traditional template_phase |                 2.88915 |                2.88915 | 0           | True   |
| S02b global-template timewalk                  |                 1.63542 |                1.63542 | 2.20047e-09 | True   |

## Method

The S16b proxy is computed per pulse from baseline-subtracted pre-trigger samples 0-3. The primary proxy is the maximum absolute leave-one-sample `line3_predict` closure residual; supporting proxy terms are the pre-trigger range, RMS line residual, early-sample standard deviation, slope, and minimum. Timing uses B4/B6/B8 events, train runs `[58, 59, 60, 61, 62, 63]`, and held-out run `[65]`.

The traditional extension is a train-only linear Ridge residual correction on top of the S02b global-template/timewalk method using only hand-built timewalk and pre-trigger proxy features. The ML extension is a Ridge residual corrector on S02 normalized waveform features plus the same proxy terms. Both are evaluated only on held-out run 65 with event bootstrap CIs.

## Held-out benchmark

| method                          |   value |   ci_low |   ci_high |   tail_frac_abs_gt5ns |   tail_ci_low |   tail_ci_high |   n_heldout_events |   n_pair_residuals |
|:--------------------------------|--------:|---------:|----------:|----------------------:|--------------:|---------------:|-------------------:|-------------------:|
| S02_global_template_phase       | 2.88915 |  2.63915 |   3.27718 |            0.0505051  |     0.0151515 |      0.0808081 |                 66 |                198 |
| S02b_global_template_timewalk   | 1.63542 |  1.49126 |   1.90991 |            0.00505051 |     0         |      0.0151515 |                 66 |                198 |
| S16e_traditional_proxy_timewalk | 1.44513 |  1.17372 |   1.69363 |            0          |     0         |      0.0102273 |                 66 |                198 |
| S16e_ml_proxy_ridge             | 1.38749 |  1.24726 |   1.62387 |            0.00505051 |     0         |      0.020202  |                 66 |                198 |

Traditional proxy delta versus S02b timewalk: `-0.190 ns`; tail-fraction delta `-0.0051`. ML proxy delta versus S02b timewalk: `-0.248 ns`; tail-fraction delta `+0.0000`.

## Tail study

Held-out event residual tails by pre-trigger proxy bin:

| method                          | proxy_bin   |   n_pair_residuals |   n_events |   event_pre_line_absmax_adc_mean |   sigma68_ns |   tail_frac_abs_gt5ns |
|:--------------------------------|:------------|-------------------:|-----------:|---------------------------------:|-------------:|----------------------:|
| S02b_global_template_timewalk   | low         |                 66 |         22 |                          12.4567 |      1.83097 |             0         |
| S02b_global_template_timewalk   | mid         |                 66 |         22 |                          20.6797 |      1.64377 |             0.0151515 |
| S02b_global_template_timewalk   | high        |                 66 |         22 |                         212.818  |      1.46735 |             0         |
| S16e_traditional_proxy_timewalk | low         |                 66 |         22 |                          12.4567 |      1.71193 |             0         |
| S16e_traditional_proxy_timewalk | mid         |                 66 |         22 |                          20.6797 |      1.46251 |             0         |
| S16e_traditional_proxy_timewalk | high        |                 66 |         22 |                         212.818  |      1.16245 |             0         |
| S16e_ml_proxy_ridge             | low         |                 66 |         22 |                          12.4567 |      1.72504 |             0         |
| S16e_ml_proxy_ridge             | mid         |                 66 |         22 |                          20.6797 |      1.41552 |             0.0151515 |
| S16e_ml_proxy_ridge             | high        |                 66 |         22 |                         212.818  |      1.13603 |             0         |

The held-out tail count is small, so the proxy-bin table should be read as a diagnostic stratification rather than a discovery test. The high-proxy bin has a distinct residual-width pattern, but the `>5 ns` tail fraction is not consistently higher. Adding the proxy as a correction feature does not decisively erase timing tails: the traditional proxy sigma68 is `1.445 [1.174, 1.694] ns` versus the S02b baseline `1.635 [1.491, 1.910] ns`, with overlapping CIs.

## Leakage checks

| check                                           |   value | pass   |    actual |
|:------------------------------------------------|--------:|:-------|----------:|
| train_heldout_run_overlap                       | 0       | True   | nan       |
| train_heldout_event_id_overlap                  | 0       | True   | nan       |
| normalized_waveform_exact_hash_overlap          | 0       | True   | nan       |
| features_exclude_run_event_target_pair_residual | 0       | True   | nan       |
| traditional_shuffled_target_not_better          | 1.66736 | True   |   1.44513 |
| ml_shuffled_target_not_better                   | 2.74866 | True   |   1.38749 |

The split is by run and the proxy features exclude run id, event id, pair residuals, target residuals, and other-stave timing values. Shuffled-target controls were rerun for both proxy corrections.

## Conclusion

The S16b pre-trigger proxy is useful as a diagnostic tail tag but is not adopted as a timing correction. On held-out run 65, the proxy traditional fit changes sigma68 by `-0.190 ns` relative to S02b and the ML proxy changes it by `-0.248 ns`; neither provides a clean leakage-aware improvement.

## Follow-up tickets

- S16f: build a per-event pre-trigger contamination veto using B2/B4/B6/B8 and test efficiency versus S02 timing tails with leave-one-run-out Sample-II splits.
- S02d: leave-one-run-out S02b timing plus S16e proxy terms over all Sample-II analysis runs, not only held-out run 65.
