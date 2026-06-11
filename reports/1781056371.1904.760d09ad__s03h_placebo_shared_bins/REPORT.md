# S03h: blinded placebo stress test for shared-bin shrinkage

- **Ticket:** 1781056371.1904.760d09ad
- **Worker:** testbeam-laptop-3
- **Input:** raw B-stack ROOT under `/home/billy/ccb-data/extracted/root/root`
- **Config:** `configs/s03h_1781056371_1904_760d09ad_placebo_shared_bins.yaml`
- **Split:** leave-one-run-out over Sample-II analysis runs 58, 59, 60, 61, 62, 63, and 65; CIs resample held-out runs as blocks.

## Abstract

The predecessor S03f analysis reported a surprisingly narrow pooled pairwise timing width of 1.1673 ns for a shared monotone run-level amplitude-bin correction. This follow-up freezes the raw-ROOT construction and the run-held-out split, then asks whether placebo perturbations that preserve event and stave support destroy the gain. It also benchmarks the frozen traditional method against ridge regression, gradient-boosted trees, an MLP, a compact 1D-CNN, and a gated residual CNN.

## Raw-ROOT reproduction

| quantity                           |   report_value |   reproduced |   delta |   tolerance | pass   |
|:-----------------------------------|---------------:|-------------:|--------:|------------:|:-------|
| total selected B-stave pulses      |         640737 |       640737 |       0 |           0 | True   |
| sample_ii_analysis selected_pulses |         125096 |       125096 |       0 |           0 | True   |
| sample_ii_analysis B2              |          88213 |        88213 |       0 |           0 | True   |
| sample_ii_analysis B4              |          21229 |        21229 |       0 |           0 | True   |
| sample_ii_analysis B6              |          11148 |        11148 |       0 |           0 | True   |
| sample_ii_analysis B8              |           4506 |         4506 |       0 |           0 | True   |

The S03a/S03b run-65 anchor was rerun from the same raw downstream-pulse table before opening the S03h model panel.

| method               |   value |   reference_value |   delta | pass   |
|:---------------------|--------:|------------------:|--------:|:-------|
| template_phase_base  | 2.88915 |           2.88915 |       0 | True   |
| s03a_amp_only        | 1.49464 |           1.49464 |       0 | True   |
| s03b_monotone_binned | 1.56958 |           1.56958 |       0 | True   |

## Estimand and equations

For each selected downstream pulse in stave \(s\), the baseline-subtracted waveform is \(w_{is}(t)=H_{is}(t)-\operatorname{median}_{t\in\{0,1,2,3\}}H_{is}(t)\), with selection \(\max_t w_{is}(t)>1000\) ADC. Template phase gives the uncorrected time \(t^{(0)}_{is}\). After subtracting the fixed time-of-flight term \(z_s v^{-1}\), the train target for a pulse is

\[ y_{is}=\left(t^{(0)}_{is}-z_s v^{-1}\right)-\frac{1}{2}\sum_{u\ne s}\left(t^{(0)}_{iu}-z_u v^{-1}\right). \]

The S03f traditional correction fits a decreasing isotonic curve in \(\log(1+A)\). Population, stave, and train-run/stave bin medians are successively shrunk, and the deployed held-out curve is the average of train-run curves plus the selected population weight. Held-out rows never fit a curve. Learned comparators estimate \(\hat y_{is}=f(x_{is})\) from the same single-pulse waveform, amplitude, peak, area, and stave indicators; corrected time is \(t_{is}=t^{(0)}_{is}-\hat y_{is}\).

## Model panel

| method                 |   value |   ci_low |   ci_high |   n_pair_residuals |   tail_frac_abs_gt5ns |
|:-----------------------|--------:|---------:|----------:|-------------------:|----------------------:|
| runlevel_shared_bins   | 1.16729 |  1.00506 |   1.28056 |              11460 |             0.0166667 |
| gradient_boosted_trees | 1.54199 |  1.39693 |   1.73717 |              11460 |             0.0155323 |
| s03a_amp_only          | 1.55109 |  1.37425 |   1.91412 |              11460 |             0.0191099 |
| ridge                  | 1.56448 |  1.36941 |   1.81552 |              11460 |             0.0177138 |
| cnn1d                  | 1.56791 |  1.3459  |   1.97725 |              11460 |             0.0206806 |
| gated_residual_cnn     | 1.60642 |  1.41283 |   1.96213 |              11460 |             0.0192845 |
| s03b_monotone_binned   | 1.64515 |  1.3214  |   1.93536 |              11460 |             0.019459  |
| mlp                    | 1.65782 |  1.44959 |   1.94371 |              11460 |             0.0150087 |
| template_phase_base    | 2.74141 |  2.6867  |   2.98207 |              11460 |             0.0813264 |

Winner named in `result.json`: **runlevel_shared_bins**.

Run 61 behavior:

| method                 |   value |   ci_low |   ci_high |   n_pair_residuals |
|:-----------------------|--------:|---------:|----------:|-------------------:|
| runlevel_shared_bins   | 1.26146 |  1.24949 |   1.33093 |               2799 |
| gradient_boosted_trees | 1.93696 |  1.86576 |   1.99147 |               2799 |
| ridge                  | 2.00867 |  1.93925 |   2.11535 |               2799 |
| mlp                    | 2.08467 |  2.02775 |   2.13343 |               2799 |
| s03b_monotone_binned   | 2.10176 |  2.10176 |   2.24895 |               2799 |
| s03a_amp_only          | 2.12996 |  1.99824 |   2.20573 |               2799 |
| cnn1d                  | 2.17288 |  2.06841 |   2.26472 |               2799 |
| gated_residual_cnn     | 2.20372 |  2.12728 |   2.2759  |               2799 |
| template_phase_base    | 2.70351 |  2.70351 |   2.70351 |               2799 |

## Placebo controls

Placebos preserve the row support and train/held-out split while breaking specific causal links: within-run amplitude permutation by stave breaks the amplitude-timewalk relation, the sign flip uses the learned curve in the wrong physical direction, and deployment-curve run-label permutation scrambles train-run membership before building the deployment average. I skipped no S03h control as a duplicate of the earlier S03g/HGB monotonicity audit; these tests are specific to the S03f shared-bin mechanism.

| control                                   |   value |   min_sigma68_ns |   max_sigma68_ns |   n_runs |
|:------------------------------------------|--------:|-----------------:|-----------------:|---------:|
| deployment_curve_run_label_permutation    | 1.02788 |         0.565276 |          1.26326 |        7 |
| train_run_curve_sign_flip                 | 5.31817 |         5.00877  |          5.8883  |        7 |
| within_run_amplitude_permutation_by_stave | 1.03804 |         0.60766  |          1.28541 |        7 |

## Sample-II-to-Sample-I transfer check

The predeclared transfer check trains the shared-bin curve on all Sample-II analysis runs and deploys it unchanged to Sample-I analysis runs 44-57. This is not used to select the winner; it is a domain-shift stress test for whether the curve is a portable detector effect or a Sample-II-local shrinkage accident.

| method                                |    value |   min_sigma68_ns |   max_sigma68_ns |   n_runs |
|:--------------------------------------|---------:|-----------------:|-----------------:|---------:|
| sample_ii_to_sample_i_runlevel_shared | 0.269425 |        0.0466371 |         0.689403 |       14 |
| template_phase_base                   | 2.63685  |        2.30306   |         2.63685  |       14 |

## Leakage and systematics

|   heldout_run | check                                             |   value | unit   |
|--------------:|:--------------------------------------------------|--------:|:-------|
|            58 | train_heldout_event_id_overlap                    |       0 | events |
|            58 | features_exclude_run_event_order_cross_stave_time |       1 | bool   |
|            58 | heldout_run_curve_not_fit                         |       1 | bool   |
|            58 | final_models_use_heldout_rows                     |       0 | bool   |
|            59 | train_heldout_event_id_overlap                    |       0 | events |
|            59 | features_exclude_run_event_order_cross_stave_time |       1 | bool   |
|            59 | heldout_run_curve_not_fit                         |       1 | bool   |
|            59 | final_models_use_heldout_rows                     |       0 | bool   |
|            60 | train_heldout_event_id_overlap                    |       0 | events |
|            60 | features_exclude_run_event_order_cross_stave_time |       1 | bool   |
|            60 | heldout_run_curve_not_fit                         |       1 | bool   |
|            60 | final_models_use_heldout_rows                     |       0 | bool   |
|            61 | train_heldout_event_id_overlap                    |       0 | events |
|            61 | features_exclude_run_event_order_cross_stave_time |       1 | bool   |
|            61 | heldout_run_curve_not_fit                         |       1 | bool   |
|            61 | final_models_use_heldout_rows                     |       0 | bool   |
|            62 | train_heldout_event_id_overlap                    |       0 | events |
|            62 | features_exclude_run_event_order_cross_stave_time |       1 | bool   |
|            62 | heldout_run_curve_not_fit                         |       1 | bool   |
|            62 | final_models_use_heldout_rows                     |       0 | bool   |
|            63 | train_heldout_event_id_overlap                    |       0 | events |
|            63 | features_exclude_run_event_order_cross_stave_time |       1 | bool   |
|            63 | heldout_run_curve_not_fit                         |       1 | bool   |
|            63 | final_models_use_heldout_rows                     |       0 | bool   |
|            65 | train_heldout_event_id_overlap                    |       0 | events |
|            65 | features_exclude_run_event_order_cross_stave_time |       1 | bool   |
|            65 | heldout_run_curve_not_fit                         |       1 | bool   |
|            65 | final_models_use_heldout_rows                     |       0 | bool   |

Feature leakage controls are structural: run id, event id, event order, other-stave timing, and the held-out target are not model inputs. Bootstrap uncertainty is conditional on seven held-out runs and is therefore sensitive to run 61. The neural networks are CPU-sized diagnostics rather than exhaustive architecture searches. No Monte Carlo truth label is used, and the metric remains an internal downstream-pair closure width rather than an external absolute timing resolution.

## Verdict

The point-estimate winner is runlevel_shared_bins with pooled sigma68 1.167 ns (95% run-bootstrap CI 1.005-1.281). The frozen shared-bin method gives 1.167 ns, run 61 gives 1.261 ns, and the best placebo remains at 0.565 ns. Verdict: shared_bin_gain_not_promoted.

## Reproducibility

```bash
/home/billy/anaconda3/bin/python scripts/s03h_1781056371_1904_760d09ad_placebo_shared_bins.py --config configs/s03h_1781056371_1904_760d09ad_placebo_shared_bins.yaml
```
