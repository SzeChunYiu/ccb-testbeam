# P03h: stave-aware residual support map by pulse atoms

- **Ticket:** `1781035058.850.43a47da0`
- **Worker:** `testbeam-laptop-4`
- **Input:** raw B-stack ROOT files from `/home/billy/ccb-data/extracted/root/root`
- **Primary source benchmark:** `reports/1781034623.1381.12086ef0__p03f_loro_feature_multimodel`
- **Detector-label permutation source:** `reports/1781034623.1447.4a243444`
- **Run split:** leave-one-run-out over Sample-II runs `[58, 59, 60, 61, 62, 63, 65]`

## Question

P03e found that a stave-aware waveform/amplitude/shape residual corrector can beat
the S03 analytic timewalk correction. P03h asks whether that improvement is
supported in actual pulse-shape regions or whether it is mainly a detector/run
identity artifact. The estimand is the downstream pair residual

`r_ab(e;m) = [t_a(e;m) - z_a / v] - [t_b(e;m) - z_b / v]`,

with `v^-1 = 0.078 ns/cm`, evaluated for B4/B6/B8 pairs.
The robust width is

`sigma68(m) = (Q84({r_ab}) - Q16({r_ab})) / 2`.

The atom-level delta is `Delta_atom(m) = sigma68_atom(m) -
sigma68_atom(analytic_timewalk)`. Confidence intervals resample runs first and
events within sampled runs; single-run atoms fall back to event bootstrap and are
flagged as such.

## Raw-ROOT Reproduction Gate

The selected-pulse count gate was rerun from raw ROOT in this P03h script before
building any support table.

| quantity                           |   report_value |   reproduced |   delta |   tolerance | pass   |
|:-----------------------------------|---------------:|-------------:|--------:|------------:|:-------|
| total selected B-stave pulses      |         640737 |       640737 |       0 |           0 | True   |
| sample_ii_analysis selected_pulses |         125096 |       125096 |       0 |           0 | True   |
| sample_ii_analysis B2              |          88213 |        88213 |       0 |           0 | True   |
| sample_ii_analysis B4              |          21229 |        21229 |       0 |           0 | True   |
| sample_ii_analysis B6              |          11148 |        11148 |       0 |           0 | True   |
| sample_ii_analysis B8              |           4506 |         4506 |       0 |           0 | True   |

## Head-to-Head Benchmark

The traditional method is the fold-local S03/P03 analytic timewalk correction.
The ML/NN benchmark comes from the full P03f LORO residual table: ridge,
histogram gradient-boosted trees, heteroskedastic MLP, compact 1D-CNN, and the
new `feature_gated` architecture. All learners exclude run id, event id, event
order, other-stave timings, and pair residuals. Hyperparameters and templates
are fold-local to the non-held-out runs.

| family                         | best_method                            |   sigma68_ns |   ci_low |   ci_high |   delta_vs_traditional_ns |   delta_ci_low |   delta_ci_high |
|:-------------------------------|:---------------------------------------|-------------:|---------:|----------:|--------------------------:|---------------:|----------------:|
| gradient_boosted_trees         | hgb_waveform_amp_shape_stave           |      1.10742 |  1.07531 |   1.15879 |                 -0.443675 |      -0.84233  |      -0.241182  |
| mlp                            | mlp_waveform_amp_shape_stave           |      1.1621  |  1.1062  |   1.23525 |                 -0.388989 |      -0.818401 |      -0.166956  |
| ridge                          | ridge_waveform_stave_onehot            |      1.24442 |  1.17293 |   1.32178 |                 -0.306677 |      -0.738723 |      -0.0892062 |
| feature_gated_new_architecture | feature_gated_waveform_amp_shape_stave |      1.25349 |  1.21334 |   1.30812 |                 -0.297601 |      -0.6712   |      -0.094782  |
| cnn1d                          | cnn1d_waveform_amp_shape_stave         |      1.26387 |  1.21204 |   1.34277 |                 -0.287227 |      -0.685886 |      -0.0859247 |

The overall winner is **`hgb_waveform_amp_shape_stave`** with `sigma68 =
1.1074 ns` and run-block CI
`[1.0753, 1.1588] ns`.

### Feature Knockouts and Shuffled Sentinel

The P03e feature groups are audited as knockouts/add-backs: waveform-only,
waveform plus stave labels, waveform plus amplitude/shape summaries, and the
full waveform/amplitude/shape/stave model. The stave-only guardrail and the
winner's shuffled-target sentinel are included as leakage controls.

| feature_policy                            | best_method                           |   sigma68_ns |   ci_low |   ci_high |   delta_vs_traditional_ns |
|:------------------------------------------|:--------------------------------------|-------------:|---------:|----------:|--------------------------:|
| waveform_only                             | hgb_waveform_only                     |      1.51056 |  1.42749 |   1.65844 |                -0.0405306 |
| waveform_stave_onehot                     | hgb_waveform_stave_onehot             |      1.12607 |  1.08906 |   1.18473 |                -0.425027  |
| waveform_amp_shape                        | hgb_waveform_amp_shape                |      1.47412 |  1.38648 |   1.58286 |                -0.0769733 |
| waveform_amp_shape_stave                  | hgb_waveform_amp_shape_stave          |      1.10742 |  1.07531 |   1.15879 |                -0.443675  |
| amplitude_shape_plus_stave_only_guardrail | hgb_stave_offset_guardrail            |      1.15156 |  1.11007 |   1.2069  |                -0.39953   |
| winner_shuffled_target_sentinel           | hgb_waveform_amp_shape_stave_shuffled |      1.63164 |  1.42769 |   1.94109 |                 0.0805464 |

## Pulse-Atom Construction

Each held-out pair residual is matched to atom labels computed directly from
the raw-pulse table: stave pair, mean-amplitude bin, peak-sample phase,
area-over-amplitude `q_template` tercile, saturation flag, anomaly taxon, and
run family. Anomaly labels use only same-pulse waveform shape: edge peaks,
high late-tail fraction, flat/dropout-like normalized peak, and saturation.

The empirical pull-width column in `support_atom_summary.csv` is
`sigma68(r / sigma68_traditional_atom)`. It is not a calibrated model
uncertainty. Calibrated neural-network pull widths from P03g are reported below
for the MLP, CNN, and new gated architecture.

## Supported Winner Atoms

The table below is restricted to atoms with at least 50 events and a winner
delta CI whose upper endpoint is below zero. Full atom-level rows, including
small or inconclusive atoms, are in `support_atom_summary.csv`.

| support_category   | support_atom                            |   n_runs |   n_events |   sigma68_ns |   sigma68_ci_low |   sigma68_ci_high |   full_rms_ns |   tail_frac_abs_gt5ns |   pull_width68_empirical |   delta_vs_traditional_ns |   delta_ci_low |   delta_ci_high |
|:-------------------|:----------------------------------------|---------:|-----------:|-------------:|-----------------:|------------------:|--------------:|----------------------:|-------------------------:|--------------------------:|---------------:|----------------:|
| amplitude_bin      | 4000_6500_adc                           |        7 |        302 |     1.36516  |         1.17627  |          1.63903  |      3.3723   |            0.0609756  |                 0.534427 |                 -1.18928  |      -1.92253  |     -0.731505   |
| run_family         | sample_ii_run_61                        |        1 |        933 |     1.08935  |         1.03521  |          1.13673  |      2.42827  |            0.0217935  |                 0.511441 |                 -1.04061  |      -1.14417  |     -0.875846   |
| peak_sample_phase  | same_nominal_peak_9_11                  |        7 |        851 |     1.32321  |         1.21382  |          1.43044  |      1.80781  |            0.011236   |                 0.657068 |                 -0.690601 |      -1.09431  |     -0.174548   |
| peak_sample_phase  | mixed_early_peak_le5_rising_peak_6_8    |        7 |        385 |     0.60734  |         0.563463 |          0.650885 |      1.73498  |            0.0170604  |                 0.50198  |                 -0.60255  |      -0.662943 |     -0.538939   |
| peak_sample_phase  | mixed_nominal_peak_9_11_rising_peak_6_8 |        7 |       1345 |     1.40682  |         1.32635  |          1.49605  |      1.91635  |            0.0112275  |                 0.702286 |                 -0.596382 |      -1.00101  |     -0.210547   |
| q_template         | mid_q_template                          |        7 |       2611 |     1.19477  |         1.14561  |          1.25934  |      1.38393  |            0.00345304 |                 0.67554  |                 -0.573842 |      -0.889352 |     -0.301377   |
| peak_sample_phase  | same_early_peak_le5                     |        7 |        654 |     0.623501 |         0.580873 |          0.662631 |      0.655069 |            0          |                 0.525408 |                 -0.563197 |      -0.613745 |     -0.514882   |
| q_template         | high_q_template                         |        7 |       2180 |     1.16313  |         1.11212  |          1.22511  |      2.1857   |            0.0226784  |                 0.674977 |                 -0.560083 |      -0.934721 |     -0.206179   |
| peak_sample_phase  | same_rising_peak_6_8                    |        7 |       2034 |     1.17248  |         1.11296  |          1.22645  |      1.38028  |            0.00517891 |                 0.685085 |                 -0.538956 |      -0.879569 |     -0.267893   |
| anomaly            | any_late_tail_high                      |        7 |       3423 |     1.17028  |         1.13446  |          1.22078  |      2.01695  |            0.0118414  |                 0.690371 |                 -0.524866 |      -0.882393 |     -0.228583   |
| anomaly            | both_nominal                            |        7 |        496 |     0.65316  |         0.611565 |          0.689519 |      0.61914  |            0          |                 0.563021 |                 -0.506939 |      -0.552843 |     -0.453151   |
| saturation         | unsaturated_pair                        |        7 |       3820 |     1.10641  |         1.07279  |          1.1604   |      2.10751  |            0.0135442  |                 0.714115 |                 -0.442934 |      -0.82885  |     -0.223551   |
| amplitude_bin      | 2500_4000_adc                           |        7 |       3099 |     1.13278  |         1.08938  |          1.18029  |      2.12754  |            0.0149758  |                 0.725403 |                 -0.428805 |      -0.815625 |     -0.15537    |
| run_family         | sample_ii_run_59                        |        1 |        763 |     1.0669   |         1.01577  |          1.13075  |      2.10433  |            0.0117955  |                 0.731398 |                 -0.391812 |      -0.483463 |     -0.297025   |
| q_template         | low_q_template                          |        7 |       1532 |     0.864306 |         0.794707 |          0.969028 |      2.84268  |            0.017424   |                 0.712881 |                 -0.348107 |      -0.4411   |     -0.215743   |
| run_family         | sample_ii_run_62                        |        1 |        807 |     1.1568   |         1.09825  |          1.20433  |      2.09572  |            0.00908715 |                 0.787469 |                 -0.312208 |      -0.390597 |     -0.239904   |
| amplitude_bin      | 1500_2500_adc                           |        7 |       2372 |     1.05425  |         0.962661 |          1.13905  |      1.89314  |            0.00743399 |                 0.779576 |                 -0.298087 |      -0.681943 |     -0.101742   |
| run_family         | sample_ii_run_60                        |        1 |        808 |     1.09797  |         1.04135  |          1.16407  |      1.90232  |            0.0136139  |                 0.81712  |                 -0.245737 |      -0.331306 |     -0.15635    |
| run_family         | sample_ii_run_63                        |        1 |        370 |     1.17366  |         1.0908   |          1.27199  |      1.92326  |            0.00990991 |                 0.843555 |                 -0.217666 |      -0.331811 |     -0.0782132  |
| stave_pair         | B4-B8                                   |        7 |       3820 |     1.034    |         0.942498 |          1.10161  |      2.34492  |            0.0172775  |                 0.859563 |                 -0.168937 |      -0.290563 |     -0.002568   |
| peak_sample_phase  | same_late_peak_ge12                     |        7 |        262 |     1.01024  |         0.887196 |          1.15478  |      2.94924  |            0.0236111  |                 0.87201  |                 -0.148279 |      -0.266775 |     -0.00834456 |

## Detector-Label and Stave-Only Controls

P03g explicitly permuted detector labels in training and held-out partitions.
The real-stave advantage is largest against held-out label permutation, but the
P03f stave-offset guardrail remains close to the winner; this is why the result
is a support-map statement rather than a causal adoption claim.

| comparison                                                                               |   mean_delta_sigma68_ns |   run_bootstrap_ci_low |   run_bootstrap_ci_high |
|:-----------------------------------------------------------------------------------------|------------------------:|-----------------------:|------------------------:|
| gradient_boosted_trees_real_stave_minus_gradient_boosted_trees_heldout_label_permutation |               -1.39808  |              -1.58515  |               -1.23197  |
| label_offset_real_stave_minus_label_offset_heldout_label_permutation                     |               -1.34361  |              -1.54298  |               -1.16702  |
| ridge_real_stave_minus_ridge_heldout_label_permutation                                   |               -1.21779  |              -1.39271  |               -1.07246  |
| mlp_real_stave_minus_mlp_heldout_label_permutation                                       |               -1.17792  |              -1.41874  |               -0.98132  |
| gated_label_fusion_real_stave_minus_gated_label_fusion_heldout_label_permutation         |               -1.12931  |              -1.43377  |               -0.753815 |
| cnn_real_stave_minus_cnn_heldout_label_permutation                                       |               -1.10194  |              -1.36509  |               -0.861191 |
| mlp_real_stave_minus_mlp_no_stave                                                        |               -0.44378  |              -0.618999 |               -0.305888 |
| cnn_real_stave_minus_cnn_train_label_permutation                                         |               -0.434326 |              -0.624854 |               -0.300286 |
| ridge_real_stave_minus_ridge_no_stave                                                    |               -0.430409 |              -0.600124 |               -0.301305 |
| ridge_real_stave_minus_ridge_train_label_permutation                                     |               -0.428072 |              -0.602376 |               -0.297207 |
| gated_label_fusion_real_stave_minus_gated_label_fusion_no_stave                          |               -0.394314 |              -0.566975 |               -0.262132 |
| mlp_real_stave_minus_mlp_train_label_permutation                                         |               -0.386027 |              -0.542265 |               -0.239801 |
| cnn_real_stave_minus_cnn_no_stave                                                        |               -0.372196 |              -0.584989 |               -0.207834 |
| gradient_boosted_trees_real_stave_minus_gradient_boosted_trees_no_stave                  |               -0.367581 |              -0.536367 |               -0.233943 |
| gradient_boosted_trees_real_stave_minus_gradient_boosted_trees_train_label_permutation   |               -0.360744 |              -0.511784 |               -0.235068 |
| gated_label_fusion_real_stave_minus_gated_label_fusion_train_label_permutation           |               -0.335867 |              -0.524206 |               -0.171358 |

Neural calibration checks:

|   heldout_run | method                        |   pred_sigma_median_ns |   abs_error_median_ns |   pull_width_sigma68 |   pull_rms |
|--------------:|:------------------------------|-----------------------:|----------------------:|---------------------:|-----------:|
|            58 | mlp_real_stave                |                1.89179 |              0.842339 |             0.42261  |   0.985835 |
|            58 | cnn_real_stave                |                2.06204 |              0.641188 |             0.431856 |   0.863602 |
|            58 | gated_label_fusion_real_stave |                2.21846 |              0.588555 |             0.415156 |   0.83537  |
|            59 | mlp_real_stave                |                1.55616 |              0.641565 |             0.614583 |   0.972825 |
|            59 | cnn_real_stave                |                1.60542 |              0.600051 |             0.585343 |   1.02785  |
|            59 | gated_label_fusion_real_stave |                2.11191 |              1.00796  |             0.691827 |   0.928918 |
|            60 | mlp_real_stave                |                1.49908 |              0.65234  |             0.59217  |   0.867297 |
|            60 | cnn_real_stave                |                1.68556 |              0.620535 |             0.543907 |   0.846505 |
|            60 | gated_label_fusion_real_stave |                1.90864 |              0.66807  |             0.51754  |   0.8091   |
|            61 | mlp_real_stave                |                1.44931 |              0.699496 |             0.724551 |   1.19893  |
|            61 | cnn_real_stave                |                1.5922  |              0.703817 |             0.703359 |   1.08345  |
|            61 | gated_label_fusion_real_stave |                1.87949 |              0.995013 |             0.716869 |   0.999601 |
|            62 | mlp_real_stave                |                1.48047 |              0.585937 |             0.607417 |   1.06388  |
|            62 | cnn_real_stave                |                1.62373 |              0.599624 |             0.571586 |   1.11171  |
|            62 | gated_label_fusion_real_stave |                1.91524 |              0.753034 |             0.567309 |   0.954859 |
|            63 | mlp_real_stave                |                1.40705 |              0.635956 |             0.639718 |   1.07063  |
|            63 | cnn_real_stave                |                1.61423 |              0.63504  |             0.559285 |   1.05114  |
|            63 | gated_label_fusion_real_stave |                1.82346 |              0.667758 |             0.5308   |   0.956434 |
|            65 | mlp_real_stave                |                1.57194 |              0.827179 |             0.660428 |   0.750616 |
|            65 | cnn_real_stave                |                1.61899 |              0.643408 |             0.573525 |   0.735    |
|            65 | gated_label_fusion_real_stave |                2.02893 |              0.666621 |             0.509149 |   0.58998  |

## Systematics and Caveats

- Atom labels are derived from downstream B-stack pulse records only; they are
  support diagnostics, not truth labels for the beam particle or absolute time.
- `q_template` is implemented as an area-over-amplitude pulse-shape tercile. It
  is a compact template-charge proxy rather than a full waveform template fit.
- Single-run atoms use event-only bootstrap and should not be overinterpreted as
  run-generalized effects.
- Stave-aware features intentionally encode detector identity. The label
  permutation and stave-offset controls show that identity is predictive, but
  they do not prove a purely causal waveform mechanism.
- The P03h script does not retrain the P03f/P03g neural networks; it audits
  their frozen event-level residual outputs by raw-pulse support atom after
  rerunning the raw-ROOT reproduction gate.

## Verdict

Winner in `result.json`: **`hgb_waveform_amp_shape_stave`**.

The stave-aware gain is real at the predictive-support level: 21 winner atoms have run/event-bootstrap deltas below zero, and the pooled winner beats analytic timewalk by -0.444 ns. However, the stave-offset guardrail at 1.152 ns and the P03g real-stave/no-stave gap show that detector identity explains a substantial share of the lift; this is not a standalone causal waveform adoption result.

## Reproducibility

```bash
/home/billy/anaconda3/bin/python scripts/p03h_1781035058_850_43a47da0_support_map.py --config configs/p03h_1781035058_850_43a47da0_support_map.json
```

Key artifacts: `reproduction_match_table.csv`, `benchmark_pooled_summary.csv`,
`detector_label_policy_gaps.csv`, `nn_pull_calibration.csv`,
`pair_support_atoms.csv`, `support_atom_summary.csv`, `result.json`, and
`manifest.json`.
